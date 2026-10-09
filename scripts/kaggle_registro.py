"""Sorteo de tareas y lectura del registro de una sesión del notebook de Kaggle (#160).

Dos órdenes, las dos locales y sin red:

    python -m scripts.kaggle_registro sortear --validez <validez_ensayo.json> [--salida <lista.json>]
    python -m scripts.kaggle_registro diagnosticar --salida <carpeta o zip de salida de una sesión>

``sortear`` reproduce la lista de tareas de la iteración 08: universo = las tareas de clase ``discrimina``
del archivo de validez estricto, ordenadas por ``instance_id``; generador
``random.Random(int(sha256(semilla).hexdigest(), 16))``; lista = ``sample(universo, 60)``. Si el universo no
tiene el tamaño esperado se detiene: no se ajusta la semilla ni el tamaño. Si ``--salida`` ya existe con
otra lista, no la pisa.

``diagnosticar`` lee lo que dejaron los enganches de ``scripts/kaggle_registro_enganches.py`` y dice, sin la
consola: si la sesión se cerró o murió desde fuera, qué tope cortó, cuál era la petición en vuelo (su hora
y el tamaño de su entrada) y qué diff dejó cada tarea al cierre. No abre ningún archivo fuera de los del
registro y no extrae nada de un zip.

Salida: 0 si todo se pudo leer; 1 si la lista sorteada difiere de la guardada; 2 si la entrada es inválida.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import zipfile
from collections import Counter
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

SEMILLA_ITERACION_08 = "ALL-kaggle-iteracion-08-2026-10-08"
UNIVERSO_ESPERADO = 71
TAREAS_SORTEADAS = 60
CLASE_VALIDA = "discrimina"

EXIT_OK = 0
EXIT_DIFIERE = 1
EXIT_ENTRADA = 2

# Texto que el arnés pone en el error de una sesión del agente, y el tope que significa.
TOPES_DE_TAREA = (
    ("session timeout", "tope de tiempo de la tarea"),
    ("tool call budget", "tope de llamadas"),
    ("turns budget", "tope de turnos"),
    ("maximum allowed llm turns", "tope de turnos"),
    ("connection error", "el servidor del modelo dejó de responder"),
)
CORTES_DE_SESION = {
    "tareas": "tope de tiempo del conjunto de tareas (TOPE_SEGUNDOS)",
    "sesion": "tope de sesión del notebook (TOPE_SESION_SEGUNDOS menos el margen)",
    "servidor": "servidor del modelo caído (GET /health falló antes de la tarea)",
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
    return sorted(str(t["instance_id"]) for t in tareas if t.get("clase") == CLASE_VALIDA)


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
        for patron, clave in (("registro_*.jsonl", "eventos"), ("latido_*.jsonl", "latidos")):
            halladas = sorted(ruta.glob(patron))
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


# Una petición «en vuelo» es la que no terminó con una respuesta del modelo.
NO_RESPONDIDAS = frozenset({"sin fin", "cancelada", "error"})


def diagnosticar(eventos: Sequence[dict[str, Any]], latidos: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Qué pasó en la sesión, solo con lo que quedó en el registro."""
    pares = emparejar(eventos)
    fichas = [_ficha(pares[n]) for n in sorted(pares)]
    cierre = next((e for e in eventos if e.get("evento") == "cierre"), None)
    cortes = [e for e in eventos if e.get("evento") == "corte"]
    diffs = {e.get("tarea"): e for e in eventos if e.get("evento") == "diff_cierre"}
    fines = {e.get("tarea"): e for e in eventos if e.get("evento") == "tarea_fin"}
    agentes = {e.get("tarea"): e for e in eventos if e.get("evento") == "agente_fin"}
    tareas = []
    for inicio in (e for e in eventos if e.get("evento") == "tarea_inicio"):
        nombre = inicio.get("tarea")
        fin = fines.get(nombre)
        propias = [f for f in fichas if f["tarea"] == nombre]
        en_vuelo = [f for f in propias if f["como_termino"] in NO_RESPONDIDAS]
        diff = diffs.get(nombre)
        agente = agentes.get(nombre)
        # El motivo de fin del agente manda: el arnés lo descarta de la fila cuando el parche pasa.
        error_del_agente = None if agente is None else agente.get("error")
        error_de_la_fila = None if fin is None else fin.get("error")
        tareas.append(
            {
                "tarea": nombre,
                "terminada": fin is not None,
                "clase": None if fin is None else fin.get("clase"),
                "error": error_de_la_fila,
                "fin_del_agente": None
                if agente is None
                else {
                    k: agente.get(k)
                    for k in ("error", "entrego", "parche_caracteres", "llamadas_herramientas")
                },
                "tope_que_corto": tope_de_tarea(error_del_agente) or tope_de_tarea(error_de_la_fila),
                "peticiones": len(propias),
                "peticion_en_vuelo": en_vuelo[-1] if en_vuelo else None,
                "ultima_peticion": propias[-1] if propias else None,
                "diff_al_cierre": None
                if diff is None
                else {k: diff.get(k) for k in ("bytes", "sha256", "archivos", "error") if k in diff},
            }
        )
    ultimo_latido = latidos[-1] if latidos else None
    if cortes:
        por = str(cortes[-1].get("cortado_por"))
        veredicto = "cortada por el notebook: " + CORTES_DE_SESION.get(por, por)
    elif cierre is not None:
        veredicto = "completa: el registro termina en «cierre» y no hay ningún corte"
    else:
        veredicto = "muerta desde fuera: el registro no termina en «cierre»"
    canales = Counter(e.get("evento") for e in eventos if str(e.get("evento", "")).startswith("cb_"))
    no_respondidas = [f for f in fichas if f["como_termino"] in NO_RESPONDIDAS]
    return {
        "sesion": {
            "veredicto": veredicto,
            "cerrada": cierre is not None,
            "cortado_por": cortes[-1].get("cortado_por") if cortes else None,
            "ultimo_evento": eventos[-1].get("evento") if eventos else None,
            "ultimo_evento_utc": eventos[-1].get("hora_utc") if eventos else None,
            "ultimo_latido": None
            if ultimo_latido is None
            else {
                k: ultimo_latido.get(k)
                for k in ("hora_utc", "sesion_s", "tarea", "en_vuelo", "servidor_sano", "diff_en_curso")
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


# ---------------------------------------------------------------------------
# Órdenes
# ---------------------------------------------------------------------------


def _orden_sortear(args: argparse.Namespace) -> int:
    acta = acta_del_sorteo(args.validez, args.semilla)
    if args.salida is not None:
        if args.salida.exists():
            guardada = json.loads(args.salida.read_text(encoding="utf-8")).get("lista")
            if guardada != acta["lista"]:
                print("LA LISTA GUARDADA DIFIERE DE LA SORTEADA: no se pisa.", file=sys.stderr)
                return EXIT_DIFIERE
        else:
            args.salida.write_text(json.dumps(acta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(acta, ensure_ascii=False, indent=1))
    return EXIT_OK


def _orden_diagnosticar(args: argparse.Namespace) -> int:
    datos = cargar_salida(args.salida)
    informe = diagnosticar(datos["eventos"], datos["latidos"])
    informe["lineas_ilegibles"] = datos["lineas_ilegibles"]
    informe["hay_latido"] = datos["hay_latido"]
    print(json.dumps(informe, ensure_ascii=False, indent=1))
    return EXIT_OK


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
    args = p.parse_args(argv)
    try:
        return int(args.funcion(args))
    except RegistroError as exc:
        print(f"ENTRADA INVÁLIDA: {exc}", file=sys.stderr)
        return EXIT_ENTRADA


if __name__ == "__main__":
    raise SystemExit(main())
