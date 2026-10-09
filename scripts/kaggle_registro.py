"""Sorteo de tareas y lectura del registro de una sesión del notebook de Kaggle (#160).

Tres órdenes, locales y sin red:

    python -m scripts.kaggle_registro sortear --validez <validez_ensayo.json> [--salida <lista.json>]
    python -m scripts.kaggle_registro diagnosticar --salida <carpeta o zip de salida de una sesión>
    python -m scripts.kaggle_registro comprobar --rescate <carpeta de un rescate> --notebook <pasada 1>
        --notebook <pasada 2>      (en la misma línea)

``sortear`` reproduce la lista de tareas de la iteración 08: universo = las tareas de clase ``discrimina``
del archivo de validez estricto, ordenadas por ``instance_id``; generador
``random.Random(int(sha256(semilla).hexdigest(), 16))``; lista = ``sample(universo, 60)``. Si el universo no
tiene el tamaño esperado se detiene: no se ajusta la semilla ni el tamaño. Si ``--salida`` ya existe con
otra lista, no la pisa.

``diagnosticar`` lee lo que dejaron los enganches de ``scripts/kaggle_registro_enganches.py`` y dice, sin la
consola: si el registro es de fiar, si la sesión se cerró o murió desde fuera, qué tope cortó cada tarea,
cuál era la petición en vuelo o cortada (su hora y el tamaño de su entrada) y qué diff dejó cada tarea al
cierre. No abre ningún archivo fuera de los del registro y no extrae nada de un zip.

``diagnosticar`` solo mira el registro: no ve, por ejemplo, que los logs por tarea de un zip pesen 0 bytes.
Para juzgar una corrida se usa ``comprobar``.

``comprobar`` corre ``scripts.kaggle_rescate --sin-red`` sobre la carpeta de un rescate y después
``diagnosticar`` sobre los archivos ``salida__registro_*`` de cada pasada esperada, que se nombra con
``--notebook`` (repetible: uno por pasada). Hace falta porque el rescate solo mira bytes: una sesión muerta
desde fuera deja un zip sano, empaquetado antes de morir. Para cada pasada nombrada, que falte su carpeta,
que falte su registro o que su diagnóstico no dé 0 es un hallazgo, y el JSON dice cuál y por qué. Sin
ninguna pasada nombrada la orden no puede afirmar que la corrida está completa y nunca sale con 0. Los
notebooks del rescate que no se nombraron solo se listan; si alguno no trae registro y sí trae archivos que
solo deja un notebook con registro, lleva además un aviso, que no cambia el código.

Salida:
    0  sin hallazgos: lista reproducida, o registro fiable y sesión completa
    1  la lista sorteada difiere de la guardada
    2  entrada inválida o ilegible (archivo ausente, JSON roto, acta o validez sin sus campos, un evento
       del registro con un campo de otro tipo); en ``comprobar``, además, no haber nombrado ninguna pasada
    3  sesión cortada por el notebook; la causa está en el registro
    4  registro no fiable: un enganche exigido no se instaló, hubo errores propios, hay tareas corridas y
       en toda la sesión no hay ninguna petición respondida, una tarea terminada no trae su ``agente_fin`` o
       su ``diff_cierre``, falta ``registro_instalado`` o una guardia detuvo el notebook; en ``comprobar``,
       además, una pasada esperada sin carpeta en el rescate o sin registro
    5  sesión muerta desde fuera: el registro no termina en ``cierre``
    6  sesión viva y detenida: el registro no termina en ``cierre`` ni anota un corte, y el latido siguió
       más de ``SILENCIO_DETENIDA_SEGUNDOS`` después del último evento (#164)
    7  sesión terminada con tareas colgadas: el notebook cortó al menos una tarea por su tope por tarea,
       comprobó que su hilo había terminado y siguió con las demás (#164)
Una sesión que el notebook terminó por una tarea colgada (``corte('tarea_colgada')``) sale con 3.
Precedencia en ``diagnosticar``: 4 gana a 3, y 3 gana a 7, a 6 y a 5 (un registro no fiable se dice aunque la
sesión esté cortada o muerta; un corte anotado por el notebook se dice aunque falte el cierre). El 7 exige
``cierre``; el 6 y el 5 son de un registro sin ``cierre`` y los separa el silencio antes del último latido.
El 0 de ``diagnosticar`` significa «registro fiable y sesión completa», no «todas las tareas completas»: una
tarea cortada por tiempo o por llamadas no cambia el código; su motivo está en ``agente_fin``.
Precedencia en ``comprobar``: el código del rescate, si no es 0; si lo es, el de la primera pasada nombrada,
en el orden en que se nombraron, cuyo código no sea 0; sin ninguna pasada nombrada, 2 si todo lo demás da 0.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import random
import sys
import zipfile
from collections import Counter
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from scripts.kaggle_registro_enganches import CLASE_TAREA_COLGADA, ENGANCHE_NO_EXIGIDO

SEMILLA_ITERACION_08 = "ALL-kaggle-iteracion-08-2026-10-08"
UNIVERSO_ESPERADO = 71
TAREAS_SORTEADAS = 60
CLASE_VALIDA = "discrimina"

EXIT_OK = 0
EXIT_DIFIERE = 1
EXIT_ENTRADA = 2
EXIT_CORTADA = 3
EXIT_REGISTRO = 4
EXIT_MUERTA = 5
EXIT_DETENIDA_VIVA = 6
EXIT_CON_COLGADAS = 7

# Enganche que solo declara un registro del #164 en adelante (el notebook con tope por tarea).
ENGANCHE_DEL_MAPA = "mapa de hilos del núcleo"

# Segundos de latido sin ningún evento a partir de los cuales una sesión sin cierre se llama «viva y
# detenida» y no «muerta desde fuera»: el tope por tarea del notebook (900 s), su margen tras el corte (30 s)
# y un latido (30 s). Con menos silencio, el notebook todavía no había tenido ocasión de cortar la tarea.
SILENCIO_DETENIDA_SEGUNDOS = 960.0

# Texto que el arnés pone en el error de una sesión del agente, y el tope que significa.
TOPES_DE_TAREA = (
    ("session timeout", "tope de tiempo de la tarea"),
    ("tool call budget", "tope de llamadas"),
    ("turns budget", "tope de turnos"),
    ("maximum allowed llm turns", "tope de turnos"),
    ("connection error", "el servidor del modelo dejó de responder"),
)
# Archivos de salida que solo deja un notebook con registro. Si están y falta el registro en un notebook que
# nadie nombró como pasada esperada, se avisa; la defensa de fondo es nombrar las pasadas esperadas.
SENALES_DE_PASADA = (
    "salida__latido_*",
    "salida__servidor_log_*",
    "salida__diff_en_curso_*",
    "salida__*iteracion_08*",
)
CORTES_DE_SESION = {
    "tareas": "tope de tiempo del conjunto de tareas (TOPE_SEGUNDOS)",
    "sesion": "tope de sesión del notebook (TOPE_SESION_SEGUNDOS menos el margen)",
    "servidor": "servidor del modelo caído (GET /health falló antes de la tarea)",
    CLASE_TAREA_COLGADA: "una tarea no volvió dentro del tope por tarea y el notebook terminó la sesión",
}


class RegistroError(ValueError):
    """Entrada inválida: archivo ausente, ilegible o con otro tamaño de universo."""


# ---------------------------------------------------------------------------
# Sorteo
# ---------------------------------------------------------------------------


def universo_valido(validez: dict[str, Any]) -> list[str]:
    """Tareas de clase ``discrimina`` del archivo de validez, ordenadas por ``instance_id``."""
    tareas = validez.get("tareas")
    if not isinstance(tareas, list):
        raise RegistroError("El archivo de validez no trae la lista «tareas».")
    try:
        return sorted(str(t["instance_id"]) for t in tareas if t.get("clase") == CLASE_VALIDA)
    except (KeyError, TypeError, AttributeError) as exc:
        raise RegistroError("El archivo de validez trae una tarea sin «instance_id» o mal formada.") from exc


def sortear(
    universo: Sequence[str],
    semilla: str = SEMILLA_ITERACION_08,
    n: int = TAREAS_SORTEADAS,
    esperado: int = UNIVERSO_ESPERADO,
) -> list[str]:
    """La lista sorteada. Se detiene si el universo no tiene ``esperado`` tareas o trae repetidas."""
    if len(universo) != esperado or len(set(universo)) != len(universo):
        raise RegistroError(
            f"El universo tiene {len(universo)} tareas ({len(set(universo))} distintas) y se esperaban "
            f"{esperado}: el sorteo se detiene y no se ajusta ni la semilla ni el tamaño."
        )
    generador = random.Random(int(hashlib.sha256(semilla.encode("utf-8")).hexdigest(), 16))
    return generador.sample(sorted(universo), n)


def huella_de_lista(lista: Sequence[str]) -> str:
    """SHA-256 de la lista en su orden, una tarea por línea."""
    return hashlib.sha256("\n".join(lista).encode("utf-8")).hexdigest()


def acta_del_sorteo(ruta_validez: Path, semilla: str = SEMILLA_ITERACION_08) -> dict[str, Any]:
    """Todo lo que hace falta para repetir el sorteo y comprobar que da lo mismo."""
    try:
        crudo = ruta_validez.read_bytes()
        validez = json.loads(crudo)
    except (OSError, ValueError) as exc:
        raise RegistroError(f"No se pudo leer el archivo de validez: {type(exc).__name__}") from exc
    universo = universo_valido(validez)
    lista = sortear(universo, semilla)
    return {
        "semilla": semilla,
        "generador": "random.Random(int(sha256(semilla).hexdigest(), 16)).sample(universo_ordenado, n)",
        "validez_sha256": hashlib.sha256(crudo).hexdigest(),
        "universo": len(universo),
        "n": len(lista),
        "lista_sha256": huella_de_lista(lista),
        "lista": lista,
        "fuera_del_sorteo": sorted(set(universo) - set(lista)),
    }


# ---------------------------------------------------------------------------
# Lectura del registro
# ---------------------------------------------------------------------------


def leer_jsonl(texto: str) -> tuple[list[dict[str, Any]], int]:
    """Líneas JSON de un registro. Devuelve también cuántas líneas no se pudieron leer.

    Una sesión que muere desde fuera puede dejar la última línea a medias: se cuenta y no detiene nada.
    """
    filas: list[dict[str, Any]] = []
    ilegibles = 0
    for linea in texto.splitlines():
        if not linea.strip():
            continue
        try:
            fila = json.loads(linea)
        except ValueError:
            ilegibles += 1
            continue
        if isinstance(fila, dict):
            filas.append(fila)
        else:
            ilegibles += 1
    return filas, ilegibles


def cargar_salida(ruta: Path) -> dict[str, Any]:
    """Lee el registro de una carpeta de salida o de un zip ``crudo_*.zip`` (miembros ``registro/``)."""
    textos: dict[str, str] = {}
    if ruta.is_dir():
        # En la carpeta de un rescate los archivos de salida llevan el prefijo «salida__».
        for patron, clave in (("registro_*.jsonl", "eventos"), ("latido_*.jsonl", "latidos")):
            halladas = sorted(ruta.glob(patron)) or sorted(ruta.glob("salida__" + patron))
            if halladas:
                textos[clave] = halladas[0].read_text(encoding="utf-8", errors="replace")
    elif ruta.is_file():
        try:
            with zipfile.ZipFile(ruta) as z:
                for info in z.infolist():
                    base = info.filename.replace("\\", "/").split("/")[-1]
                    if "registro/" not in info.filename.replace("\\", "/"):
                        continue
                    if base.startswith("registro_") and base.endswith(".jsonl"):
                        textos["eventos"] = z.read(info).decode("utf-8", "replace")
                    elif base.startswith("latido_") and base.endswith(".jsonl"):
                        textos["latidos"] = z.read(info).decode("utf-8", "replace")
        except (zipfile.BadZipFile, OSError) as exc:
            raise RegistroError(f"Zip ilegible: {type(exc).__name__}") from exc
    else:
        raise RegistroError("La salida no es una carpeta ni un zip.")
    if "eventos" not in textos:
        raise RegistroError("En la salida no hay ningún registro_*.jsonl.")
    eventos, ilegibles = leer_jsonl(textos["eventos"])
    latidos, latidos_ilegibles = leer_jsonl(textos.get("latidos", ""))
    return {
        "eventos": eventos,
        "latidos": latidos,
        "lineas_ilegibles": ilegibles + latidos_ilegibles,
        "hay_latido": "latidos" in textos,
    }


def validar_eventos(eventos: Sequence[dict[str, Any]]) -> None:
    """Lanza ``RegistroError`` si un evento trae un campo de otro tipo: es una entrada ilegible."""
    esperados: tuple[tuple[str, tuple[type, ...], tuple[str, ...]], ...] = (
        ("evento", (str,), ()),
        ("tarea", (str, type(None)), ()),
        ("peticion", (int,), ("peticion_inicio", "peticion_fin")),
        ("enganches", (dict,), ("registro_instalado",)),
        ("errores_del_registro", (int, type(None)), ("cierre",)),
        ("peticion_en_curso", (int, type(None)), ("cb_antes", "cb_exito", "cb_fallo")),
    )
    for numero, e in enumerate(eventos, start=1):
        for campo, tipos, solo_en in esperados:
            if solo_en and e.get("evento") not in solo_en:
                continue
            if campo == "tarea" and campo not in e:
                continue
            valor = e.get(campo)
            if not isinstance(valor, tipos) or isinstance(valor, bool):
                raise RegistroError(
                    f"Registro ilegible: en el evento {numero} ({str(e.get('evento'))[:40]}) el campo "
                    f"«{campo}» es de tipo {type(valor).__name__}."
                )


def emparejar(eventos: Iterable[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """Cada petición con su inicio, su fin (o ``None``) y las retrollamadas de litellm que disparó."""
    peticiones: dict[int, dict[str, Any]] = {}
    por_llamada: dict[str, int] = {}
    for e in eventos:
        tipo = e.get("evento")
        if tipo == "peticion_inicio" and isinstance(e.get("peticion"), int):
            peticiones[e["peticion"]] = {"inicio": e, "fin": None, "retrollamadas": Counter()}
        elif tipo == "peticion_fin" and e.get("peticion") in peticiones:
            peticiones[e["peticion"]]["fin"] = e
        elif tipo in ("cb_antes", "cb_exito", "cb_fallo"):
            llamada = str(e.get("llamada"))
            if tipo == "cb_antes" and e.get("peticion_en_curso") in peticiones:
                por_llamada[llamada] = e["peticion_en_curso"]
            numero = por_llamada.get(llamada)
            if numero is not None:
                peticiones[numero]["retrollamadas"][tipo] += 1
    return peticiones


def tope_de_tarea(error: str | None) -> str | None:
    """Qué cortó la sesión del agente, a partir del mensaje de error del arnés. ``None`` si nada la cortó."""
    texto = str(error or "").lower()
    for marca, nombre in TOPES_DE_TAREA:
        if marca in texto:
            return nombre
    return None


def _ficha(par: dict[str, Any]) -> dict[str, Any]:
    inicio, fin = par["inicio"], par["fin"]
    como = "sin fin" if fin is None else str(fin.get("motivo"))
    return {
        "peticion": inicio.get("peticion"),
        "tarea": inicio.get("tarea"),
        "hora_utc": inicio.get("hora_utc"),
        "caracteres_entrada": inicio.get("caracteres_entrada"),
        "n_mensajes": inicio.get("n_mensajes"),
        "como_termino": como,
        "segundos": None if fin is None else fin.get("segundos"),
        "error": None if fin is None else fin.get("error"),
        "retrollamadas": dict(par["retrollamadas"]),
    }


# «No respondida»: no terminó con una respuesta del modelo. «En vuelo» es solo la que no tiene fin.
NO_RESPONDIDAS = frozenset({"sin fin", "cancelada", "error"})


def ocurrencias_de_tarea(eventos: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Una entrada por cada ``tarea_inicio``, con lo que el registro anotó hasta su ``tarea_fin``.

    Se agrupa por posición y no por nombre: si una tarea se corre dos veces, cada corrida conserva sus
    peticiones, su motivo de fin, su diff y su fila.
    """
    ocurrencias: list[dict[str, Any]] = []
    actual: dict[str, Any] | None = None
    for e in eventos:
        tipo = e.get("evento")
        if tipo == "tarea_inicio":
            actual = {
                "inicio": e,
                "peticiones": [],
                "agente": None,
                "diff": None,
                "fin": None,
                "colgada": None,
            }
            ocurrencias.append(actual)
        elif actual is None or e.get("tarea") != actual["inicio"].get("tarea"):
            continue
        elif tipo == "peticion_inicio" and isinstance(e.get("peticion"), int):
            actual["peticiones"].append(e["peticion"])
        elif tipo == "agente_fin":
            actual["agente"] = e
        elif tipo == "diff_cierre":
            actual["diff"] = e
        elif tipo == "tarea_colgada":
            actual["colgada"] = e
        elif tipo == "tarea_fin":
            actual["fin"] = e
            actual = None
    return ocurrencias


def es_colgada(ocurrencia: dict[str, Any]) -> bool:
    """La corrida de una tarea que el notebook cortó por su tope por tarea.

    Basta una de tres señales: el evento ``tarea_colgada``, la clase de la fila de fin o su marca
    ``par_faltante``. Si no coinciden, ``salud_del_registro`` lo da por un registro no fiable.
    """
    fin = ocurrencia["fin"]
    return ocurrencia["colgada"] is not None or (
        fin is not None and (fin.get("clase") == CLASE_TAREA_COLGADA or fin.get("par_faltante") is True)
    )


def silencio_antes_del_ultimo_latido(
    eventos: Sequence[dict[str, Any]], latidos: Sequence[dict[str, Any]]
) -> float | None:
    """Segundos entre el último evento del registro y el último latido. ``None`` si falta alguna hora."""
    if not eventos or not latidos:
        return None
    hora_evento, hora_latido = eventos[-1].get("hora"), latidos[-1].get("hora")
    for hora in (hora_evento, hora_latido):
        if isinstance(hora, bool) or not isinstance(hora, (int, float)):
            return None
    return round(float(hora_latido) - float(hora_evento), 1)  # type: ignore[arg-type]


def salud_del_registro(
    eventos: Sequence[dict[str, Any]], fichas: Sequence[dict[str, Any]], ocurrencias: Sequence[dict[str, Any]]
) -> list[str]:
    """Por qué no hay que fiarse de este registro. Lista vacía si no hay motivo.

    Un registro puede existir y no registrar: enganches que no se instalaron o que no surten efecto,
    errores propios al escribir, o una sesión con tareas corridas y ninguna petición respondida.
    """
    problemas: list[str] = []
    instalado = next((e for e in eventos if e.get("evento") == "registro_instalado"), None)
    if instalado is None:
        problemas.append("el registro no trae el evento «registro_instalado»")
    else:
        for nombre, estado in (instalado.get("enganches") or {}).items():
            if str(estado).startswith("FALLO") and nombre != ENGANCHE_NO_EXIGIDO:
                problemas.append(f"enganche sin instalar: {nombre}")
    cierre = next((e for e in eventos if e.get("evento") == "cierre"), None)
    if cierre is not None and cierre.get("errores_del_registro"):
        problemas.append(
            f"el registro tuvo {cierre['errores_del_registro']} errores propios: {cierre.get('ultimo_error')}"
        )
    respondidas = sum(f["como_termino"] not in NO_RESPONDIDAS for f in fichas)
    # Una tarea colgada puede no haber llegado a su primera petición: no cuenta como «corrida» para esto.
    if any(o["fin"] is not None and not es_colgada(o) for o in ocurrencias) and respondidas == 0:
        con_error = sum(f["como_termino"] in ("error", "cancelada") for f in fichas)
        problemas.append(
            f"hay tareas corridas y ninguna petición respondida en toda la sesión ({len(fichas)} iniciadas, "
            f"{con_error} con error o canceladas): o el enganche de peticiones no surte efecto, o el "
            "servidor nunca respondió"
        )
    # Una tarea terminada sin su motivo de fin o sin su diff: el enganche dice «instalado» y no surte efecto.
    hay_corte = any(e.get("evento") in ("corte", "guardia") for e in eventos)
    corte_por_colgada = any(
        e.get("evento") == "corte" and e.get("cortado_por") == CLASE_TAREA_COLGADA for e in eventos
    )
    # Un registro del #164 en adelante declara el mapa de hilos entre sus enganches: ese notebook lleva el
    # tope por tarea, así que cada tarea terminada debe decir «con_tope: true». Un registro anterior no trae
    # el campo y no se le exige.
    declara_el_tope = instalado is not None and ENGANCHE_DEL_MAPA in (instalado.get("enganches") or {})
    # Tras el cierre no debe haber nada: un evento posterior es de algo que siguió corriendo.
    if cierre is not None:
        posteriores = [e for e in eventos[eventos.index(cierre) + 1 :] if e.get("evento") != "cierre"]
        if posteriores:
            problemas.append(
                f"hay {len(posteriores)} eventos después del «cierre» (el primero, "
                f"{str(posteriores[0].get('evento'))[:40]}): algo siguió corriendo con el registro cerrado"
            )
    anterior_colgada = False
    for orden, o in enumerate(ocurrencias, start=1):
        nombre_de_tarea = o["inicio"].get("tarea")
        colgada = o["colgada"]
        era_seguida, anterior_colgada = anterior_colgada, o["fin"] is not None and es_colgada(o)
        if o["fin"] is None:
            # Con el registro cerrado y sin ningún corte, una tarea sin su fila de fin no tiene explicación.
            if cierre is not None and not hay_corte:
                problemas.append(
                    f"la tarea {nombre_de_tarea} (corrida {orden}) empezó, no tiene «tarea_fin» y la sesión "
                    "se cerró sin anotar ningún corte"
                )
            continue
        con_tope = o["fin"].get("con_tope")
        if con_tope is False or (declara_el_tope and con_tope is not True):
            problemas.append(f"la tarea {nombre_de_tarea} (corrida {orden}) no corrió bajo el tope por tarea")
        if es_colgada(o):
            if o["fin"].get("resuelta"):
                problemas.append(f"la tarea colgada {nombre_de_tarea} (corrida {orden}) figura como resuelta")
            if o["fin"].get("par_faltante") is not True:
                problemas.append(
                    f"la tarea colgada {nombre_de_tarea} (corrida {orden}) no está marcada como par faltante"
                )
            if colgada is None:
                problemas.append(
                    f"la tarea {nombre_de_tarea} (corrida {orden}) figura como colgada y no trae su evento "
                    "«tarea_colgada» (pila, hilo y decisión de seguir)"
                )
            elif not isinstance(colgada.get("sigue"), bool):
                # «sigue» decide si hubo dos tareas a la vez: un texto o un campo ausente no se interpreta.
                problemas.append(
                    f"el evento «tarea_colgada» de {nombre_de_tarea} (corrida {orden}) no dice con un "
                    f"booleano si el notebook siguió: {str(colgada.get('sigue'))[:40]!r}"
                )
            elif colgada["sigue"] and colgada.get("hilo_vivo") is not False:
                problemas.append(
                    f"tras la tarea colgada {nombre_de_tarea} (corrida {orden}) el notebook siguió sin "
                    "comprobar que su hilo había terminado: pudo haber dos tareas a la vez"
                )
            elif colgada["sigue"] and era_seguida:
                problemas.append(
                    f"la tarea colgada {nombre_de_tarea} (corrida {orden}) es la segunda seguida y el "
                    "notebook siguió: debía terminar la sesión"
                )
            elif not colgada["sigue"] and orden < len(ocurrencias):
                problemas.append(
                    f"tras la tarea colgada {nombre_de_tarea} (corrida {orden}) el notebook no debía seguir "
                    "y empezó otra tarea"
                )
            elif not colgada["sigue"] and cierre is not None and not corte_por_colgada:
                problemas.append(
                    f"tras la tarea colgada {nombre_de_tarea} (corrida {orden}) el notebook no podía seguir "
                    "y el registro se cerró sin anotar el corte de la sesión"
                )
            continue
        faltan = [
            nombre
            for nombre, evento in (("agente_fin", o["agente"]), ("diff_cierre", o["diff"]))
            if evento is None or (nombre == "diff_cierre" and "error" in evento)
        ]
        if faltan:
            problemas.append(
                f"la tarea {o['inicio'].get('tarea')} (corrida {orden}) terminó sin {' ni '.join(faltan)}"
            )
    # Un corte por tarea colgada que no queda dentro de la corrida de ninguna tarea (llegó tras su fila de
    # fin, o con otro nombre de tarea) no se puede atribuir: la sesión no puede darse por completa.
    sueltos = sum(e.get("evento") == "tarea_colgada" for e in eventos) - sum(
        o["colgada"] is not None for o in ocurrencias
    )
    if sueltos:
        problemas.append(
            f"hay {sueltos} eventos «tarea_colgada» que no pertenecen a la corrida de ninguna tarea"
        )
    for guardia in (e for e in eventos if e.get("evento") == "guardia"):
        problemas.append(f"la guardia detuvo el notebook {guardia.get('cuando')}: {guardia.get('problemas')}")
    return problemas


def diagnosticar(eventos: Sequence[dict[str, Any]], latidos: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Qué pasó en la sesión, solo con lo que quedó en el registro."""
    validar_eventos(eventos)
    pares = emparejar(eventos)
    fichas = [_ficha(pares[n]) for n in sorted(pares)]
    por_numero = {f["peticion"]: f for f in fichas}
    cierre = next((e for e in eventos if e.get("evento") == "cierre"), None)
    instalado = next((e for e in eventos if e.get("evento") == "registro_instalado"), None)
    cortes = [e for e in eventos if e.get("evento") == "corte"]
    ocurrencias = ocurrencias_de_tarea(eventos)
    veces = Counter(o["inicio"].get("tarea") for o in ocurrencias)
    tareas = []
    for orden, o in enumerate(ocurrencias, start=1):
        nombre, fin, agente, diff = o["inicio"].get("tarea"), o["fin"], o["agente"], o["diff"]
        propias = [por_numero[n] for n in o["peticiones"] if n in por_numero]
        sin_fin = [f for f in propias if f["como_termino"] == "sin fin"]
        ultima = propias[-1] if propias else None
        # El motivo de fin del agente manda: el arnés lo descarta de la fila cuando el parche pasa.
        error_del_agente = None if agente is None else agente.get("error")
        error_de_la_fila = None if fin is None else fin.get("error")
        tareas.append(
            {
                "orden": orden,
                "tarea": nombre,
                "veces_en_la_sesion": veces[nombre],
                "terminada": fin is not None,
                "clase": None if fin is None else fin.get("clase"),
                "error": error_de_la_fila,
                "fin_del_agente": None
                if agente is None
                else {
                    k: agente.get(k)
                    for k in ("error", "entrego", "parche_caracteres", "llamadas_herramientas")
                },
                "tope_que_corto": "tope por tarea del notebook (tarea colgada)"
                if es_colgada(o)
                else tope_de_tarea(error_del_agente) or tope_de_tarea(error_de_la_fila),
                "colgada": None
                if o["colgada"] is None
                else {
                    k: o["colgada"].get(k)
                    for k in (
                        "tope_s",
                        "segundos",
                        "pila",
                        "pila_bytes",
                        "mapa_de_hilos",
                        "cancelacion",
                        "hilo_vivo",
                        "segundos_hasta_terminar",
                        "cpu_del_hilo_s",
                        "sigue",
                    )
                },
                "mapa_de_hilos_al_empezar": o["inicio"].get("mapa_de_hilos"),
                "peticiones": len(propias),
                "no_respondidas": sum(f["como_termino"] in NO_RESPONDIDAS for f in propias),
                # En vuelo: un inicio sin fin de ningún tipo. Solo puede quedar si la sesión murió.
                "peticion_en_vuelo": sin_fin[-1] if sin_fin else None,
                # Cortada: la última petición de la tarea, si no llegó a responderse.
                "peticion_cortada": ultima if ultima and ultima["como_termino"] in NO_RESPONDIDAS else None,
                "ultima_peticion": ultima,
                "diff_al_cierre": None
                if diff is None
                else {k: diff.get(k) for k in ("bytes", "sha256", "archivos", "error") if k in diff},
            }
        )
    ultimo_latido = latidos[-1] if latidos else None
    guardias = [e for e in eventos if e.get("evento") == "guardia"]
    colgadas = [t["tarea"] for t, o in zip(tareas, ocurrencias, strict=True) if es_colgada(o)]
    silencio = silencio_antes_del_ultimo_latido(eventos, latidos)
    # El corte por tarea colgada manda sobre el «fallo» con que la celda de tareas sale después.
    cortado_por = None
    if cortes:
        motivos = [str(c.get("cortado_por")) for c in cortes]
        cortado_por = CLASE_TAREA_COLGADA if CLASE_TAREA_COLGADA in motivos else motivos[-1]
    if guardias:
        # Una sesión que una guardia detuvo no es «completa» aunque su registro termine en «cierre».
        estado, veredicto = "detenida", f"detenida por una guardia {guardias[-1].get('cuando')}"
    elif cortado_por is not None:
        estado = "cortada"
        veredicto = "cortada por el notebook: " + CORTES_DE_SESION.get(cortado_por, cortado_por)
    elif cierre is not None and colgadas:
        estado = "con_colgadas"
        veredicto = (
            f"terminada con {len(colgadas)} tareas colgadas ({', '.join(map(str, colgadas))}): el notebook "
            "las cortó por su tope por tarea, comprobó que su hilo había terminado y siguió"
        )
    elif cierre is not None:
        estado, veredicto = "completa", "completa: el registro termina en «cierre» y no hay ningún corte"
    elif silencio is not None and silencio > SILENCIO_DETENIDA_SEGUNDOS:
        estado = "detenida_viva"
        veredicto = (
            f"viva y detenida: el registro no termina en «cierre» y el latido siguió {silencio} s después "
            f"del último evento (tarea en curso: {ultimo_latido.get('tarea') if ultimo_latido else None})"
        )
    else:
        estado, veredicto = "muerta", "muerta desde fuera: el registro no termina en «cierre»"
        if silencio is not None:
            veredicto += f" ({silencio} s de latido sin eventos antes del último latido)"
    problemas = salud_del_registro(eventos, fichas, ocurrencias)
    if problemas:
        veredicto = "registro no fiable (" + "; ".join(problemas) + "); sesión " + veredicto
    canales = Counter(e.get("evento") for e in eventos if str(e.get("evento", "")).startswith("cb_"))
    no_respondidas = [f for f in fichas if f["como_termino"] in NO_RESPONDIDAS]
    return {
        "sesion": {
            "veredicto": veredicto,
            "estado": estado,
            "registro_fiable": not problemas,
            "problemas_del_registro": problemas,
            "cerrada": cierre is not None,
            "cortado_por": cortado_por,
            # Una tarea cortada por el tope por tarea es un par faltante, no una tarea no resuelta: quien
            # compare dos pasadas la excluye de la cuenta de discordantes.
            "tareas_colgadas": colgadas,
            "pares_faltantes": colgadas,
            "segundos_de_latido_sin_eventos": silencio,
            "versiones": None if instalado is None else instalado.get("versiones"),
            "mapa_de_hilos": None if instalado is None else instalado.get("mapa_de_hilos"),
            "tareas_que_empezaron_con_un_ciclo_en_el_mapa": sum(
                bool((o["inicio"].get("mapa_de_hilos") or {}).get("ciclo")) for o in ocurrencias
            ),
            "ultimo_evento": eventos[-1].get("evento") if eventos else None,
            "ultimo_evento_utc": eventos[-1].get("hora_utc") if eventos else None,
            "ultimo_latido": None
            if ultimo_latido is None
            else {
                k: ultimo_latido.get(k)
                for k in ("hora_utc", "sesion_s", "tarea", "en_vuelo", "servidor_sano", "diff_en_curso")
            },
            # Lo que el latido dice de la tarea en curso y de la máquina (#164).
            "ultimo_latido_de_la_tarea": None
            if ultimo_latido is None
            else {
                k: ultimo_latido.get(k)
                for k in (
                    "ultimo_evento",
                    "segundos_sin_eventos",
                    "tarea_segundos",
                    "hilo_de_tarea",
                    "carga",
                    "cpus",
                    "cpus_utilizables",
                    "hilos_vivos",
                )
            },
            "latidos": len(latidos),
        },
        "peticiones": {
            "iniciadas": len(fichas),
            "con_fin": sum(f["como_termino"] != "sin fin" for f in fichas),
            "motivos": dict(Counter(f["como_termino"] for f in fichas)),
            "no_respondidas": no_respondidas,
        },
        "enganches": {
            "envoltorio_inicios": len(fichas),
            "envoltorio_fines": sum(f["como_termino"] != "sin fin" for f in fichas),
            "retrollamadas": dict(canales),
            "no_respondidas_por_retrollamada": [
                {"peticion": f["peticion"], "como_termino": f["como_termino"], **f["retrollamadas"]}
                for f in no_respondidas
            ],
        },
        "tareas": tareas,
    }


def codigo_de(informe: dict[str, Any]) -> int:
    """Código de salida de un diagnóstico: 0 solo si el registro es fiable y la sesión quedó completa."""
    sesion = informe["sesion"]
    if not sesion["registro_fiable"]:
        return EXIT_REGISTRO
    codigos = {
        "completa": EXIT_OK,
        "cortada": EXIT_CORTADA,
        "muerta": EXIT_MUERTA,
        "detenida": EXIT_REGISTRO,
        "detenida_viva": EXIT_DETENIDA_VIVA,
        "con_colgadas": EXIT_CON_COLGADAS,
    }
    return codigos[sesion["estado"]]


# ---------------------------------------------------------------------------
# Órdenes
# ---------------------------------------------------------------------------


def _orden_sortear(args: argparse.Namespace) -> int:
    acta = acta_del_sorteo(args.validez, args.semilla)
    if args.salida is not None:
        if args.salida.exists():
            try:
                guardada = json.loads(args.salida.read_text(encoding="utf-8"))["lista"]
            except (OSError, ValueError, KeyError, TypeError) as exc:
                raise RegistroError(f"El acta guardada no se puede leer: {type(exc).__name__}") from exc
            if guardada != acta["lista"]:
                print("LA LISTA GUARDADA DIFIERE DE LA SORTEADA: no se pisa.", file=sys.stderr)
                return EXIT_DIFIERE
        else:
            args.salida.write_text(json.dumps(acta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(acta, ensure_ascii=False, indent=1))
    return EXIT_OK


def _diagnostico_de(ruta: Path) -> dict[str, Any]:
    datos = cargar_salida(ruta)
    informe = diagnosticar(datos["eventos"], datos["latidos"])
    informe["lineas_ilegibles"] = datos["lineas_ilegibles"]
    informe["hay_latido"] = datos["hay_latido"]
    return informe


def _orden_diagnosticar(args: argparse.Namespace) -> int:
    informe = _diagnostico_de(args.salida)
    print(json.dumps(informe, ensure_ascii=False, indent=1))
    return codigo_de(informe)


def _pasada(carpeta: Path) -> dict[str, Any]:
    """Lo que se puede decir de una pasada esperada: su código y el motivo, con la carpeta que haya."""
    if not carpeta.is_dir():
        return {"codigo": EXIT_REGISTRO, "motivo": "no existe la carpeta de este notebook en el rescate"}
    if not list(carpeta.glob("salida__registro_*.jsonl")):
        salidas = sorted(p.name for p in carpeta.glob("salida__*"))
        return {
            "codigo": EXIT_REGISTRO,
            "motivo": "no trae salida__registro_*.jsonl: el notebook no llegó a instalar el registro",
            "salidas": salidas,
        }
    try:
        informe = _diagnostico_de(carpeta)
    except RegistroError as exc:
        return {"codigo": EXIT_ENTRADA, "motivo": str(exc)}
    return {"codigo": codigo_de(informe), "veredicto": informe["sesion"]["veredicto"]}


def _orden_comprobar(args: argparse.Namespace) -> int:
    """El rescate que mira bytes y el diagnóstico del registro de cada pasada esperada, en una sola orden."""
    from scripts import kaggle_rescate

    captura = io.StringIO()
    with contextlib.redirect_stdout(captura):
        codigo_rescate = kaggle_rescate.main(["--destino", str(args.rescate), "--sin-red"])
    try:
        faltantes = len(json.loads(captura.getvalue())["descarga_incompleta"])
    except (ValueError, KeyError, TypeError):
        faltantes = None
    esperadas: list[str] = list(dict.fromkeys(args.notebook or []))
    pasadas = {slug: _pasada(args.rescate / "notebooks" / slug) for slug in esperadas}
    no_nombrados: dict[str, Any] = {}
    for carpeta in sorted(p for p in (args.rescate / "notebooks").glob("*") if p.is_dir()):
        if carpeta.name in pasadas:
            continue
        ficha: dict[str, Any] = {"con_registro": bool(list(carpeta.glob("salida__registro_*.jsonl")))}
        senales = sorted({p.name for patron in SENALES_DE_PASADA for p in carpeta.glob(patron)})
        if senales and not ficha["con_registro"]:
            ficha["aviso"] = "sin registro y con archivos que solo deja un notebook con registro"
            ficha["senales"] = senales
        no_nombrados[carpeta.name] = ficha
    resumen = {
        "rescate": {"codigo": codigo_rescate, "faltantes": faltantes},
        "pasadas_esperadas": pasadas,
        "notebooks_no_nombrados": no_nombrados,
    }
    print(json.dumps(resumen, ensure_ascii=False, indent=1))
    # Gana el rescate; después, la primera pasada nombrada cuyo código no sea 0.
    codigo = next(
        (c for c in [codigo_rescate, *(p["codigo"] for p in pasadas.values())] if c != EXIT_OK), EXIT_OK
    )
    if codigo == EXIT_OK and not esperadas:
        print(
            "ENTRADA INVÁLIDA: no se nombró ninguna pasada con --notebook; sin saber cuántas se esperaban "
            "no se puede afirmar que la corrida está completa.",
            file=sys.stderr,
        )
        return EXIT_ENTRADA
    return codigo


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m scripts.kaggle_registro", description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="orden", required=True)
    s = sub.add_parser("sortear", help="Reproduce el sorteo de tareas de la iteración 08")
    s.add_argument("--validez", type=Path, required=True, help="validez_ensayo.json (archivo estricto)")
    s.add_argument("--semilla", default=SEMILLA_ITERACION_08)
    s.add_argument("--salida", type=Path, default=None, help="Guarda el acta; si existe, la compara")
    s.set_defaults(funcion=_orden_sortear)
    d = sub.add_parser("diagnosticar", help="Dice qué cortó una sesión, solo con su registro")
    d.add_argument("--salida", type=Path, required=True, help="Carpeta de salida o zip crudo_*.zip")
    d.set_defaults(funcion=_orden_diagnosticar)
    c = sub.add_parser("comprobar", help="Rescate que mira bytes y diagnóstico del registro, juntos")
    c.add_argument("--rescate", type=Path, required=True, help="Carpeta de un rescate ya bajado")
    c.add_argument(
        "--notebook",
        action="append",
        default=None,
        help="Slug de una pasada esperada; se repite, una por pasada. Sin ninguna, la orden no sale con 0",
    )
    c.set_defaults(funcion=_orden_comprobar)
    args = p.parse_args(argv)
    try:
        return int(args.funcion(args))
    except RegistroError as exc:
        print(f"ENTRADA INVÁLIDA: {exc}", file=sys.stderr)
        return EXIT_ENTRADA


if __name__ == "__main__":
    raise SystemExit(main())
