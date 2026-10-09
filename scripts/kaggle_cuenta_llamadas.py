"""Cuenta por llamada: qué hizo el agente con sus llamadas, leído de las trazas de un rescate de Kaggle.

El rescate baja los zips de salida de cada notebook; este guion los abre **solo para leer** (nada se extrae)
y cuenta, por sesión y en agregado, adónde se fue el presupuesto de llamadas. Sale de la bitácora del caso
(vuelta 42, «El dueño pregunta por qué Datito no lo vio»): el problema se había medido cuatro veces en cinco
días a mano y nunca como una cuenta que se repita sola.

Uso:
    python -m scripts.kaggle_cuenta_llamadas --rescate <carpeta del rescate>
    python -m scripts.kaggle_cuenta_llamadas --rescate <carpeta> --agregado a.json --detalle d.json

``<carpeta del rescate>`` es la que trae ``notebooks/``; si trae una sola subcarpeta con ``notebooks/``
dentro (el rescate anida su carpeta fechada cuando se le da un destino ya fechado), se usa esa. Se leen todos
los ``salida__crudo_*.zip``. Por defecto escribe ``cuenta_llamadas.json`` (agregado) y
``cuenta_llamadas_detalle.json`` (por sesión) en la carpeta del rescate.

Dos salidas con destinos distintos:

* **Agregado**: solo conteos. Ni identificadores de tareas, ni texto de la competencia, ni rutas de archivos
  de los repositorios de las tareas. Es lo que puede versionarse.
* **Detalle por sesión**: lleva el identificador de la tarea y debe quedar en una carpeta ignorada por git;
  el guion se niega si no lo está.

Salida del proceso: 0 si contó; 2 si la entrada no sirve (sin carpeta o sin zips); 4 si contó pero alguna
traza o algún zip no se pudo leer (el agregado lo dice en ``sesiones_sin_traza`` y ``zips_ilegibles``).

Definiciones (cada una tiene su prueba en ``tests/test_kaggle_cuenta_llamadas.py``)
------------------------------------------------------------------------------------
Una **llamada** es una entrada de ``tool_calls`` de un paso del agente en la traza. Su **autor** dice si es
del agente **principal** (``swe_baseline_agent``) o del **subagente** (``code_analyzer_agent``). La salida
(observación) está en el paso, no en la llamada. Regla de emparejamiento: con una llamada en el paso, es de
ella; con varias, es de la que tiene el ``tool_name`` de la observación (y su autor); las demás quedan
``sin_observacion``. Hay 5 pasos con la entrega al subagente y una búsqueda del subagente: la observación es
de la búsqueda. El autor se toma de la **llamada** (``tool_calls[].extra.author``), no del paso: en esos 5
pasos el paso es del principal (la entrega) y la búsqueda es del subagente. Por eso hay 198 llamadas del
subagente y no 193 (medido: 193 llamadas tienen el mismo autor que su paso, 5 no).
La única fuente de qué contó contra el tope es la traza; los logs por sesión (``logs/``) no se usan.
Cada agregado va también separado por el tope de llamadas de la sesión (``por_tope_de_llamadas``), leído del
enunciado de presupuesto de la propia traza: mezclarlos esconde lo que cambia entre 40 y 60 llamadas.

* ``registradas``: llamadas que quedan en la traza. ``contadas``: las que cuenta el arnés contra el tope,
  que son las registradas menos ``submit_patch``, ``get_status``, la llamada al subagente
  (``code_analyzer_agent``), las rechazadas por esquema y las rechazadas por presupuesto. Se compara con
  ``tool_calls`` de ``task_results.jsonl`` (``contadas_segun_el_arnes``).
* **Por lo que devolvieron**, clases excluyentes, probadas en este orden:
  ``rechazada_por_esquema`` (la salida contiene «mandatory input parameters»: el marco rechazó la llamada
  antes de ejecutarla; no cuenta contra el tope); ``rechazada_por_presupuesto`` («BudgetExceeded»);
  ``sin_observacion``; ``error`` (``status`` ``error``, incluida una orden con código de salida distinto de
  0); ``vacia`` (herramienta de grafo con ``status`` ``ok`` y ``count`` 0 o ``results`` vacío);
  ``lectura_truncada`` (``read_file`` ``ok`` con ``is_truncated``); ``orden_sin_salida`` (``run_command``
  ``ok`` con ``stdout`` y ``stderr`` vacíos); ``con_contenido`` (el resto).
* ``busquedas_por_similitud``: llamadas a ``search_similar_code``; ``vacias``, las de clase ``vacia``.
* **Argumento mal formado**: una llamada a ``read_file`` (o ``edit_file``) con algún nombre de argumento fuera
  de los que su herramienta declara (``filepath``, ``start_line``, ``end_line``; y ``filepath``,
  ``old_string``, ``new_string``, ``allow_multiple``). ``lecturas_..._repiten_rango``: la lectura mal formada
  cuyo ``filepath`` y cuyos demás argumentos (sin las comillas del nombre) ya se pidieron antes, en la misma
  sesión, en otra lectura con rango. **Rechazada por esquema** es otra cosa: la salida lo dice.
* **Repetida**, con tres definiciones, siempre sobre las llamadas del agente principal y contando solo las
  apariciones posteriores a la primera:
  ``repetida_por_nombre_y_argumentos`` (mismo nombre de herramienta y mismos argumentos en la sesión);
  ``repetida_sin_edicion_entre_medias`` (lo mismo, pero una edición aceptada de ``edit_file`` o
  ``write_file`` olvida lo visto hasta entonces);
  ``repetida_con_la_misma_salida`` (misma llamada y misma salida, textualmente, ya vistas).
  Cada definición se da sobre tres conjuntos: las llamadas del principal (sin sufijo), solo las del principal
  que cuentan contra el tope (``_solo_contadas``; es la del auditor) y principal y subagente juntos
  (``_con_subagente``).
* ``rechazadas_sin_ejecutar``: rechazadas por esquema más rechazadas por presupuesto.
* ``ediciones_ejecutadas``: ``edit_file`` o ``write_file`` con ``status`` ``ok``, en cualquier archivo.
  ``llamadas_antes_de_la_primera_edicion_ejecutada``: llamadas registradas hasta la primera; una sesión sin
  ninguna cuenta todas las suyas. ``registradas_tras_el_aviso``: llamadas registradas después de la primera
  respuesta con ``budget_warning``.
* ``sin_avance``: unión, sin doble conteo, de: repetida sin edición de por medio (sin contar la entrega ni el
  estado), búsqueda vacía, lectura con argumento mal formado, llamada del subagente y rechazada sin ejecutar.
  ``sobre_la_traza``: sobre todas las registradas. ``sobre_las_contadas``: solo las que cuentan contra el tope
  (rechazadas fuera por definición).
* ``antes_de_la_primera_edicion_de_fuente``: llamadas contadas hasta la primera edición aceptada de un
  archivo de fuente (no de prueba, no nuevo) que el **parche final** modifica. ``despues_del_aviso``:
  llamadas contadas desde que una respuesta trae ``budget_warning`` (el arnés lo pega con 10 o menos
  llamadas por usar).
* ``sin_edicion_de_fuente``: se cuenta **por el parche final** y no por heurística de llamadas: el parche no
  modifica ningún archivo preexistente que no sea de prueba (vacío, o solo archivos nuevos o de prueba).
* **Corte**: ``marca`` del arnés en ``task_results.jsonl`` (``tiempo``, ``llamadas`` o ``contexto``; el arnés
  borra la marca cuando la tarea se resuelve, ``verification.py:556``), **o** duración mayor o igual que el
  límite de la tarea, **o** llamadas contadas iguales o mayores que el tope sin ``submit_patch``. El límite y
  el tope se leen del enunciado de presupuesto de la propia traza. ``resueltas_que_pasaron_el_limite``: tarea
  resuelta con duración mayor o igual que el límite de tiempo.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import zipfile
from collections import Counter
from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path
from typing import Any

if __package__ in (None, ""):  # ejecutado como archivo
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.kaggle_rescate import RescateError, comprobar_destino_fuera_de_git

VERSION = 1
PRINCIPAL = "swe_baseline_agent"
SUBAGENTE = "code_analyzer_agent"
MARCA_ESQUEMA = "mandatory input parameters"
MARCA_PRESUPUESTO = "BudgetExceeded"
NO_CONTADAS = frozenset({"submit_patch", "get_status", "code_analyzer_agent"})
HERRAMIENTAS_DE_GRAFO = frozenset({"search_similar_code", "get_code_neighbors", "get_code_subgraph"})
ARGUMENTOS_DE_LECTURA = frozenset({"filepath", "start_line", "end_line"})
ARGUMENTOS_DE_EDICION = frozenset({"filepath", "old_string", "new_string", "allow_multiple"})
EDITORES = frozenset({"edit_file", "write_file"})
DEFINICIONES_DE_REPETIDA = (
    "repetida_por_nombre_y_argumentos",
    "repetida_sin_edicion_entre_medias",
    "repetida_con_la_misma_salida",
)
CLASES = (
    "con_contenido",
    "vacia",
    "error",
    "rechazada_por_esquema",
    "rechazada_por_presupuesto",
    "lectura_truncada",
    "orden_sin_salida",
    "sin_observacion",
)
TOPE_MIEMBRO_BYTES = 64 * 1024 * 1024
EXIT_OK = 0
EXIT_ENTRADA = 2
EXIT_PARCIAL = 4


# ---------------------------------------------------------------------------
# De la traza a una lista de llamadas
# ---------------------------------------------------------------------------


def _json_o_none(texto: Any) -> dict[str, Any] | None:
    if isinstance(texto, dict):
        return texto
    if not isinstance(texto, str):
        return None
    try:
        valor = json.loads(texto)
    except (ValueError, RecursionError):
        return None
    return valor if isinstance(valor, dict) else None


def _dueno_de_la_observacion(llamadas: list[Any], observacion: Any) -> int | None:
    """Índice de la llamada de un paso a la que pertenece su observación.

    Regla de emparejamiento: con una sola llamada en el paso, es esa. Con varias, la observación trae
    ``extra.tool_name`` (y ``extra.author``): es la primera llamada del paso con ese nombre y, si hay
    varias, la de ese autor. Si ninguna coincide, la observación no se asigna. Una llamada sin observación
    queda como ``sin_observacion`` (hay 5 pasos con la entrega al subagente y la búsqueda del subagente: la
    observación es de la búsqueda; la entrega, sin respuesta, no cuenta contra el tope de todos modos).
    """
    if not isinstance(observacion, dict) or observacion.get("content") is None:
        return None
    if len(llamadas) == 1:
        return 0
    extra = observacion.get("extra") if isinstance(observacion.get("extra"), dict) else {}
    nombre, autor = extra.get("tool_name"), extra.get("author")
    candidatas = [
        i for i, tc in enumerate(llamadas) if isinstance(tc, dict) and tc.get("function_name") == nombre
    ]
    if len(candidatas) > 1:
        del_autor = [
            i
            for i in candidatas
            if isinstance(llamadas[i].get("extra"), dict) and llamadas[i]["extra"].get("author") == autor
        ]
        candidatas = del_autor or candidatas
    return candidatas[0] if candidatas else None


def llamadas_de(traza: dict[str, Any]) -> list[dict[str, Any]]:
    """Las llamadas de una traza, en orden, cada una con la salida que le corresponde (ver arriba)."""
    out: list[dict[str, Any]] = []
    for paso in traza.get("steps") or []:
        if not isinstance(paso, dict) or paso.get("source") != "agent":
            continue
        tcs = paso.get("tool_calls") or []
        observacion = paso.get("observation")
        dueno = _dueno_de_la_observacion(tcs, observacion)
        for i, tc in enumerate(tcs):
            if not isinstance(tc, dict):
                continue
            args = tc.get("arguments")
            extra = tc.get("extra") if isinstance(tc.get("extra"), dict) else {}
            out.append(
                {
                    "nombre": str(tc.get("function_name") or ""),
                    "args": args if isinstance(args, dict) else {},
                    "obs": str(observacion["content"]) if i == dueno else None,
                    "autor": str(extra.get("author") or ""),
                }
            )
    return out


def limites_de(traza: dict[str, Any]) -> tuple[float | None, int | None]:
    """Límite de tiempo (segundos) y tope de llamadas, leídos del enunciado de presupuesto de la traza."""
    for paso in traza.get("steps") or []:
        extra = paso.get("extra") if isinstance(paso, dict) else None
        if isinstance(extra, dict) and extra.get("event_type") == "task_prompt":
            texto = str(paso.get("message") or "")
            t = re.search(r"Time allowance:\s*([\d.]+)\s*minutes", texto)
            n = re.search(r"Tool calls allowance:\s*(\d+)\s*calls", texto)
            return (float(t.group(1)) * 60 if t else None, int(n.group(1)) if n else None)
    return None, None


# ---------------------------------------------------------------------------
# Qué devolvió cada llamada
# ---------------------------------------------------------------------------


def clase_de(llamada: dict[str, Any]) -> str:
    """Clase excluyente de lo que devolvió la llamada (ver el docstring del módulo para el orden)."""
    obs = llamada["obs"]
    if obs is None:
        return "sin_observacion"
    if MARCA_ESQUEMA in obs:
        return "rechazada_por_esquema"
    if MARCA_PRESUPUESTO in obs:
        return "rechazada_por_presupuesto"
    datos = _json_o_none(obs)
    if datos is None:
        return "con_contenido" if obs.strip() else "orden_sin_salida"
    if datos.get("status") == "error":
        return "error"
    nombre = llamada["nombre"]
    if nombre in HERRAMIENTAS_DE_GRAFO and (
        datos.get("count") == 0 or ("results" in datos and not datos["results"])
    ):
        return "vacia"
    if nombre == "read_file" and datos.get("is_truncated"):
        return "lectura_truncada"
    if nombre == "run_command" and not datos.get("stdout") and not datos.get("stderr"):
        return "orden_sin_salida"
    return "con_contenido"


def cuenta_contra_el_tope(llamada: dict[str, Any], clase: str) -> bool:
    return (
        llamada["nombre"] not in NO_CONTADAS
        and clase != "rechazada_por_esquema"
        and clase != "rechazada_por_presupuesto"
    )


def _edicion_aceptada(llamada: dict[str, Any]) -> str | None:
    """El archivo que una edición aceptada tocó, o ``None``."""
    datos = _json_o_none(llamada["obs"])
    if llamada["nombre"] in EDITORES and datos is not None and datos.get("status") == "ok":
        return str(llamada["args"].get("filepath", "")).replace("/workspace/", "")
    return None


def _clave(llamada: dict[str, Any]) -> tuple[str, str]:
    return llamada["nombre"], json.dumps(llamada["args"], sort_keys=True, ensure_ascii=False)


def repetidas(llamadas: Sequence[dict[str, Any]], etiqueta: str = "") -> dict[str, int]:
    """Las tres definiciones de «repetida» sobre las llamadas dadas, en el orden de la sesión.

    ``etiqueta`` se añade al nombre de cada contador (para distinguir sobre qué llamadas se calculó).
    """
    vistas: Counter[tuple[str, str]] = Counter()
    desde_la_ultima_edicion: set[tuple[str, str]] = set()
    con_salida: set[tuple[tuple[str, str], str | None]] = set()
    por_nombre = sin_edicion = misma_salida = 0
    for ll in llamadas:
        clave = _clave(ll)
        if vistas[clave]:
            por_nombre += 1
        vistas[clave] += 1
        if clave in desde_la_ultima_edicion:
            sin_edicion += 1
        if (clave, ll["obs"]) in con_salida:
            misma_salida += 1
        desde_la_ultima_edicion.add(clave)
        con_salida.add((clave, ll["obs"]))
        if _edicion_aceptada(ll) is not None:
            desde_la_ultima_edicion = set()
    return {
        f"repetida_por_nombre_y_argumentos{etiqueta}": por_nombre,
        f"repetida_sin_edicion_entre_medias{etiqueta}": sin_edicion,
        f"repetida_con_la_misma_salida{etiqueta}": misma_salida,
    }


def repetidas_sin_edicion_marcadas(llamadas: Sequence[dict[str, Any]]) -> set[int]:
    """Posiciones repetidas sin edición de por medio; no se marcan la entrega ni el estado."""
    vistas: set[tuple[str, str]] = set()
    marcadas: set[int] = set()
    for i, ll in enumerate(llamadas):
        if ll["nombre"] not in ("submit_patch", "get_status"):
            clave = _clave(ll)
            if clave in vistas:
                marcadas.add(i)
            vistas.add(clave)
        if _edicion_aceptada(ll) is not None:
            vistas = set()
    return marcadas


def argumentos_mal_formados(llamadas: Sequence[dict[str, Any]]) -> dict[str, int]:
    """Lecturas y ediciones con el nombre de un argumento que su herramienta no declara."""
    lecturas = repiten = ediciones = 0
    pedidos: set[tuple[Any, ...]] = set()
    for ll in llamadas:
        args = ll["args"]
        if ll["nombre"] == "edit_file" and set(args) - ARGUMENTOS_DE_EDICION:
            ediciones += 1
        if ll["nombre"] != "read_file":
            continue
        resto = tuple(sorted((k.strip('"'), str(v)) for k, v in args.items() if k != "filepath"))
        peticion = (args.get("filepath"), resto)
        if set(args) - ARGUMENTOS_DE_LECTURA:
            lecturas += 1
            if peticion in pedidos:
                repiten += 1
        if resto:
            pedidos.add(peticion)
    return {
        "lecturas_con_argumento_mal_formado": lecturas,
        "lecturas_con_argumento_mal_formado_que_repiten_un_rango": repiten,
        "ediciones_con_argumento_mal_formado": ediciones,
    }


# ---------------------------------------------------------------------------
# El parche final
# ---------------------------------------------------------------------------


def es_prueba(ruta: str) -> bool:
    nombre = ruta.split("/")[-1]
    carpetas = {p.lower() for p in ruta.split("/")[:-1]}
    return (
        (nombre.startswith("test_") and nombre.endswith(".py"))
        or nombre.endswith("_test.py")
        or bool({"tests", "test", "testing"} & carpetas)
        or nombre == "conftest.py"
    )


def archivos_del_parche(parche: str | None) -> list[tuple[str, bool]]:
    """(ruta, es_nuevo) de cada archivo que toca un parche en formato ``git diff``."""
    out: list[tuple[str, bool]] = []
    for bloque in re.split(r"(?m)^diff --git ", parche or "")[1:]:
        m = re.match(r'"?a/(.*?)"? "?b/(.*?)"?\n', bloque)
        ruta = m.group(2) if m else "?"
        cabecera = bloque.split("\n@@")[0]
        out.append((ruta, "new file mode" in cabecera))
    return out


def fuente_modificada(parche: str | None) -> list[str]:
    """Archivos preexistentes, que no son de prueba, que modifica el parche final."""
    return [r for r, nuevo in archivos_del_parche(parche) if not nuevo and not es_prueba(r)]


# ---------------------------------------------------------------------------
# Una sesión
# ---------------------------------------------------------------------------


def marca_de_corte(error: str | None) -> str:
    """Tipo de corte que dice la marca del arnés en ``task_results.jsonl``; ``""`` si no hay marca."""
    if not error:
        return ""
    if "timeout" in error:
        return "tiempo"
    if "tool call budget" in error:
        return "llamadas"
    if "Context" in error:
        return "contexto"
    return "otra"


def contar_sesion(
    traza: dict[str, Any] | None, resultado: dict[str, Any], parche: str | None
) -> dict[str, Any]:
    """Todos los contadores de una sesión. ``traza`` ``None`` es una sesión sin traza legible."""
    llamadas = llamadas_de(traza) if traza else []
    clases = [clase_de(ll) for ll in llamadas]
    principal = [ll for ll in llamadas if ll["autor"] != SUBAGENTE]
    sub = [ll for ll in llamadas if ll["autor"] == SUBAGENTE]
    por_salida = {
        "principal": Counter(c for ll, c in zip(llamadas, clases, strict=True) if ll["autor"] != SUBAGENTE),
        "subagente": Counter(c for ll, c in zip(llamadas, clases, strict=True) if ll["autor"] == SUBAGENTE),
    }
    busquedas = {
        quien: [
            c
            for ll, c in zip(llamadas, clases, strict=True)
            if ll["nombre"] == "search_similar_code" and (ll["autor"] == SUBAGENTE) == (quien == "subagente")
        ]
        for quien in ("principal", "subagente")
    }
    fuente = set(fuente_modificada(parche))
    contadas = 0
    antes_de_la_edicion: int | None = None
    aviso_en: int | None = None
    posicion_aviso: int | None = None
    primera_edicion_ejecutada: int | None = None
    for i, (ll, c) in enumerate(zip(llamadas, clases, strict=True)):
        if cuenta_contra_el_tope(ll, c):
            contadas += 1
        archivo = _edicion_aceptada(ll)
        if archivo is not None and primera_edicion_ejecutada is None:
            primera_edicion_ejecutada = i
        if antes_de_la_edicion is None and archivo is not None and archivo in fuente:
            antes_de_la_edicion = contadas
        if aviso_en is None and "budget_warning" in (ll["obs"] or ""):
            aviso_en = contadas
            posicion_aviso = i
    despues = llamadas[posicion_aviso + 1 :] if posicion_aviso is not None else []
    cuentan = [cuenta_contra_el_tope(ll, c) for ll, c in zip(llamadas, clases, strict=True)]
    # Sin avance: unión, sin doble conteo, de cinco clases de llamada (ver el docstring del módulo).
    repetida_marcada = repetidas_sin_edicion_marcadas(principal)
    ids_repetidas = {id(principal[i]) for i in repetida_marcada}
    sin_avance = [
        id(ll) in ids_repetidas
        or c == "vacia"
        or (ll["nombre"] == "read_file" and bool(set(ll["args"]) - ARGUMENTOS_DE_LECTURA))
        or ll["autor"] == SUBAGENTE
        or c in ("rechazada_por_esquema", "rechazada_por_presupuesto")
        for ll, c in zip(llamadas, clases, strict=True)
    ]
    contadas_principal = [
        ll
        for ll, c in zip(llamadas, clases, strict=True)
        if ll["autor"] != SUBAGENTE and cuenta_contra_el_tope(ll, c)
    ]
    limite_s, tope = limites_de(traza) if traza else (None, None)
    duracion = float(resultado.get("duration_seconds") or 0.0)
    resuelta = bool(resultado.get("resolved"))
    marca = marca_de_corte(resultado.get("error_message"))
    paso_el_limite = limite_s is not None and duracion >= limite_s
    entrego = any(ll["nombre"] == "submit_patch" for ll in llamadas)
    llego_al_tope = tope is not None and contadas >= tope and not entrego
    return {
        "resuelta": resuelta,
        "tiene_traza": traza is not None,
        "registradas_principal": len(principal),
        "registradas_subagente": len(sub),
        "contadas": contadas,
        "contadas_segun_el_arnes": int(resultado.get("tool_calls") or 0),
        "por_salida_principal": {c: por_salida["principal"][c] for c in CLASES},
        "por_salida_subagente": {c: por_salida["subagente"][c] for c in CLASES},
        "busquedas_por_similitud_principal": len(busquedas["principal"]),
        "busquedas_por_similitud_subagente": len(busquedas["subagente"]),
        "busquedas_por_similitud_vacias_principal": busquedas["principal"].count("vacia"),
        "busquedas_por_similitud_vacias_subagente": busquedas["subagente"].count("vacia"),
        **argumentos_mal_formados(principal),
        "lecturas_con_argumento_mal_formado_subagente": argumentos_mal_formados(sub)[
            "lecturas_con_argumento_mal_formado"
        ],
        "ediciones_rechazadas_por_esquema": sum(
            1
            for ll, c in zip(llamadas, clases, strict=True)
            if c == "rechazada_por_esquema" and ll["nombre"] in EDITORES
        ),
        "rechazadas_sin_ejecutar": sum(
            1 for c in clases if c in ("rechazada_por_esquema", "rechazada_por_presupuesto")
        ),
        **repetidas(principal),
        **repetidas(contadas_principal, "_solo_contadas"),
        **repetidas(llamadas, "_con_subagente"),
        "sin_avance_sobre_la_traza": sum(sin_avance),
        "sin_avance_sobre_las_contadas": sum(
            1 for s, cuenta in zip(sin_avance, cuentan, strict=True) if s and cuenta
        ),
        "ediciones_ejecutadas": sum(1 for ll in llamadas if _edicion_aceptada(ll) is not None),
        "llamadas_antes_de_la_primera_edicion_ejecutada": (
            len(llamadas) if primera_edicion_ejecutada is None else primera_edicion_ejecutada
        ),
        "sin_edicion_ejecutada": primera_edicion_ejecutada is None,
        "registradas_tras_el_aviso": len(despues),
        "ediciones_ejecutadas_tras_el_aviso": sum(1 for ll in despues if _edicion_aceptada(ll) is not None),
        "registradas_mas_que_el_tope": tope is not None and len(llamadas) > tope,
        "antes_de_la_primera_edicion_de_fuente": antes_de_la_edicion,
        "aviso_de_presupuesto_en_la_llamada": aviso_en,
        "despues_del_aviso": None if aviso_en is None else contadas - aviso_en,
        "parche_vacio": not (parche or "").strip(),
        "sin_edicion_de_fuente": not fuente,
        "marca_de_corte": marca,
        "duracion_s": round(duracion, 1),
        "limite_s": limite_s,
        "tope_de_llamadas": tope,
        "paso_el_limite_de_tiempo": paso_el_limite,
        "llego_al_tope_sin_entrega": llego_al_tope,
        "corte": bool(marca) or paso_el_limite or llego_al_tope,
    }


# ---------------------------------------------------------------------------
# Un rescate
# ---------------------------------------------------------------------------


def _leer_miembro(z: zipfile.ZipFile, nombre: str) -> bytes | None:
    try:
        info = z.getinfo(nombre)
    except KeyError:
        return None
    if info.file_size > TOPE_MIEMBRO_BYTES:
        return None
    return z.read(info)


def sesiones_de_zip(ruta: Path) -> Iterator[tuple[str, dict[str, Any]]]:
    """(identificador de tarea, contadores de la sesión) por cada fila de ``task_results.jsonl``.

    Lanza ``zipfile.BadZipFile`` / ``KeyError`` si el zip no se puede leer o no trae ``task_results.jsonl``.
    """
    with zipfile.ZipFile(ruta) as z:
        crudo = _leer_miembro(z, "task_results.jsonl")
        if crudo is None:
            raise KeyError("task_results.jsonl")
        for linea in crudo.decode("utf-8", errors="replace").splitlines():
            if not linea.strip():
                continue
            try:
                fila = json.loads(linea)
            except ValueError:
                continue
            if not isinstance(fila, dict) or not fila.get("task_id"):
                continue
            tarea = str(fila["task_id"])
            bruto = _leer_miembro(z, f"traces/trace_{tarea}.json")
            try:
                traza = json.loads(bruto) if bruto is not None else None
            except ValueError:
                traza = None
            if not isinstance(traza, dict):
                traza = None
            parche_crudo = _leer_miembro(z, f"patches/{tarea}.patch")
            parche = parche_crudo.decode("utf-8", errors="replace") if parche_crudo is not None else None
            yield tarea, contar_sesion(traza, fila, parche)


def carpeta_de_notebooks(rescate: Path) -> Path | None:
    if (rescate / "notebooks").is_dir():
        return rescate / "notebooks"
    hijas = (
        [d for d in rescate.iterdir() if d.is_dir() and (d / "notebooks").is_dir()]
        if rescate.is_dir()
        else []
    )
    return hijas[0] / "notebooks" if len(hijas) == 1 else None


def _suma(sesiones: Iterable[dict[str, Any]], campo: str) -> int:
    return sum(int(s[campo] or 0) for s in sesiones)


def _suma_clases(sesiones: Sequence[dict[str, Any]], quien: str) -> dict[str, int]:
    return {c: sum(s[f"por_salida_{quien}"][c] for s in sesiones) for c in CLASES}


def agregar(sesiones: Sequence[dict[str, Any]], tareas: int) -> dict[str, Any]:
    """Agregado sin identificadores: solo conteos sobre ``sesiones``."""
    resueltas = [s for s in sesiones if s["resuelta"]]
    con_edicion = [s for s in sesiones if s["antes_de_la_primera_edicion_de_fuente"] is not None]
    con_aviso = [s for s in sesiones if s["aviso_de_presupuesto_en_la_llamada"] is not None]
    cortes = [s for s in sesiones if s["marca_de_corte"]]
    return {
        "sesiones": len(sesiones),
        "tareas": tareas,
        "resueltas": len(resueltas),
        "sesiones_sin_traza": sum(1 for s in sesiones if not s["tiene_traza"]),
        "llamadas": {
            "registradas_principal": _suma(sesiones, "registradas_principal"),
            "registradas_subagente": _suma(sesiones, "registradas_subagente"),
            "contadas": _suma(sesiones, "contadas"),
            "contadas_segun_el_arnes": _suma(sesiones, "contadas_segun_el_arnes"),
            "sesiones_donde_el_conteo_difiere_del_arnes": sum(
                1 for s in sesiones if s["contadas"] != s["contadas_segun_el_arnes"]
            ),
            "por_salida_principal": _suma_clases(sesiones, "principal"),
            "por_salida_subagente": _suma_clases(sesiones, "subagente"),
        },
        "busquedas_por_similitud": {
            "principal": _suma(sesiones, "busquedas_por_similitud_principal"),
            "subagente": _suma(sesiones, "busquedas_por_similitud_subagente"),
            "vacias_principal": _suma(sesiones, "busquedas_por_similitud_vacias_principal"),
            "vacias_subagente": _suma(sesiones, "busquedas_por_similitud_vacias_subagente"),
        },
        "argumento_mal_formado": {
            "lecturas": _suma(sesiones, "lecturas_con_argumento_mal_formado"),
            "sesiones_con_lecturas": sum(1 for s in sesiones if s["lecturas_con_argumento_mal_formado"]),
            "lecturas_que_repiten_un_rango": _suma(
                sesiones, "lecturas_con_argumento_mal_formado_que_repiten_un_rango"
            ),
            "lecturas_del_subagente": _suma(sesiones, "lecturas_con_argumento_mal_formado_subagente"),
            "ediciones": _suma(sesiones, "ediciones_con_argumento_mal_formado"),
            "ediciones_rechazadas_por_esquema": _suma(sesiones, "ediciones_rechazadas_por_esquema"),
        },
        "repetidas_del_principal": {
            "repetida_por_nombre_y_argumentos": _suma(sesiones, "repetida_por_nombre_y_argumentos"),
            "repetida_sin_edicion_entre_medias": _suma(sesiones, "repetida_sin_edicion_entre_medias"),
            "repetida_con_la_misma_salida": _suma(sesiones, "repetida_con_la_misma_salida"),
        },
        "repetidas_del_principal_solo_contadas": {
            nombre: _suma(sesiones, f"{nombre}_solo_contadas") for nombre in DEFINICIONES_DE_REPETIDA
        },
        "repetidas_de_principal_y_subagente": {
            nombre: _suma(sesiones, f"{nombre}_con_subagente") for nombre in DEFINICIONES_DE_REPETIDA
        },
        "rechazadas_sin_ejecutar": _suma(sesiones, "rechazadas_sin_ejecutar"),
        "ediciones_ejecutadas": {
            "total": _suma(sesiones, "ediciones_ejecutadas"),
            "sesiones_sin_ninguna": sum(1 for s in sesiones if s["sin_edicion_ejecutada"]),
            "llamadas_antes_de_la_primera_contando_las_sesiones_sin_edicion_con_todas_las_suyas": _suma(
                sesiones, "llamadas_antes_de_la_primera_edicion_ejecutada"
            ),
            "registradas_tras_el_aviso": _suma(sesiones, "registradas_tras_el_aviso"),
            "ejecutadas_tras_el_aviso": _suma(sesiones, "ediciones_ejecutadas_tras_el_aviso"),
        },
        "sin_avance": {
            "sobre_la_traza": _suma(sesiones, "sin_avance_sobre_la_traza"),
            "sobre_las_contadas": _suma(sesiones, "sin_avance_sobre_las_contadas"),
        },
        "sesiones_con_mas_llamadas_registradas_que_el_tope": sum(
            1 for s in sesiones if s["registradas_mas_que_el_tope"]
        ),
        "primera_edicion_de_fuente": {
            "sesiones_con_edicion_localizada": len(con_edicion),
            "mediana_de_llamadas_contadas_antes": (
                statistics.median(s["antes_de_la_primera_edicion_de_fuente"] for s in con_edicion)
                if con_edicion
                else None
            ),
        },
        "aviso_de_presupuesto": {
            "sesiones_con_aviso": len(con_aviso),
            "mediana_de_la_llamada_del_aviso": (
                statistics.median(s["aviso_de_presupuesto_en_la_llamada"] for s in con_aviso)
                if con_aviso
                else None
            ),
            "llamadas_contadas_despues_del_aviso": _suma(con_aviso, "despues_del_aviso"),
        },
        "sin_edicion_de_fuente": {
            "por_el_parche_final": sum(1 for s in sesiones if s["sin_edicion_de_fuente"]),
            "de_ellas_con_parche_vacio": sum(
                1 for s in sesiones if s["sin_edicion_de_fuente"] and s["parche_vacio"]
            ),
            "de_ellas_resueltas": sum(1 for s in resueltas if s["sin_edicion_de_fuente"]),
        },
        "cortes": {
            "con_marca_del_arnes": len(cortes),
            "marca_tiempo": sum(1 for s in cortes if s["marca_de_corte"] == "tiempo"),
            "marca_llamadas": sum(1 for s in cortes if s["marca_de_corte"] == "llamadas"),
            "marca_contexto": sum(1 for s in cortes if s["marca_de_corte"] == "contexto"),
            "marca_otra": sum(1 for s in cortes if s["marca_de_corte"] == "otra"),
            "resueltas_que_pasaron_el_limite": sum(1 for s in resueltas if s["paso_el_limite_de_tiempo"]),
            "no_resueltas_sin_marca_que_pasaron_el_limite": sum(
                1
                for s in sesiones
                if not s["resuelta"] and not s["marca_de_corte"] and s["paso_el_limite_de_tiempo"]
            ),
            "llegaron_al_tope_sin_entrega": sum(1 for s in sesiones if s["llego_al_tope_sin_entrega"]),
            "corte_por_cualquier_definicion": sum(1 for s in sesiones if s["corte"]),
        },
    }


def cuenta_rescate(rescate: Path) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, int]]:
    """(agregado, detalle por sesión, problemas) de todos los ``salida__crudo_*.zip`` de un rescate."""
    notebooks = carpeta_de_notebooks(rescate)
    if notebooks is None:
        raise RescateError("No encuentro la carpeta notebooks/ en el rescate.")
    zips = sorted(notebooks.glob("*/salida__crudo_*.zip"))
    if not zips:
        raise RescateError("El rescate no trae ningún salida__crudo_*.zip.")
    detalle: list[dict[str, Any]] = []
    problemas = {"zips": len(zips), "zips_ilegibles": 0}
    for ruta in zips:
        try:
            filas = list(sesiones_de_zip(ruta))
        except (zipfile.BadZipFile, KeyError, OSError, ValueError, EOFError, NotImplementedError):
            problemas["zips_ilegibles"] += 1
            continue
        for tarea, cuenta in filas:
            detalle.append({"cuaderno": ruta.parent.name, "zip": ruta.name, "tarea": tarea, **cuenta})
    agregado = agregar(detalle, len({d["tarea"] for d in detalle}))
    # Un agregado que mezcla topes distintos esconde lo que cambia entre ellos: también va separado.
    topes = sorted({d["tope_de_llamadas"] for d in detalle}, key=lambda t: (t is None, t or 0))
    agregado["por_tope_de_llamadas"] = {
        ("desconocido" if t is None else str(t)): agregar(
            [d for d in detalle if d["tope_de_llamadas"] == t],
            len({d["tarea"] for d in detalle if d["tope_de_llamadas"] == t}),
        )
        for t in topes
    }
    agregado = {
        "version": VERSION,
        "fuente_del_conteo": "traza de cada sesión (traces/) y task_results.jsonl; no se usan los logs",
        "zips": problemas["zips"],
        "zips_ilegibles": problemas["zips_ilegibles"],
        **agregado,
    }
    return agregado, detalle, problemas


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m scripts.kaggle_cuenta_llamadas", description=__doc__.split("\n")[0]
    )
    p.add_argument("--rescate", type=Path, required=True, help="Carpeta del rescate (la que trae notebooks/)")
    p.add_argument(
        "--agregado", type=Path, default=None, help="Dónde escribir el agregado (sin identificadores)"
    )
    p.add_argument(
        "--detalle", type=Path, default=None, help="Dónde escribir el detalle (carpeta ignorada por git)"
    )
    args = p.parse_args(argv)
    try:
        agregado, detalle, problemas = cuenta_rescate(args.rescate)
        destino_agregado = args.agregado or args.rescate / "cuenta_llamadas.json"
        destino_detalle = args.detalle or args.rescate / "cuenta_llamadas_detalle.json"
        comprobar_destino_fuera_de_git(destino_detalle)
        destino_detalle.parent.mkdir(parents=True, exist_ok=True)
        destino_detalle.write_text(json.dumps(detalle, ensure_ascii=False, indent=1), encoding="utf-8")
        destino_agregado.parent.mkdir(parents=True, exist_ok=True)
        destino_agregado.write_text(json.dumps(agregado, ensure_ascii=False, indent=1), encoding="utf-8")
    except (RescateError, OSError) as exc:
        print(f"ENTRADA INVÁLIDA: {exc}", file=sys.stderr)
        return EXIT_ENTRADA
    print(json.dumps(agregado, ensure_ascii=False, indent=2))
    return EXIT_PARCIAL if problemas["zips_ilegibles"] or agregado["sesiones_sin_traza"] else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
