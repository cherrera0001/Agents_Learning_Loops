"""Parser compartido de trazas de réplica 1 (c7_20261016T0459Z).

Devuelve por tarea: secuencia de llamadas a herramientas, primera edición,
verificación tras edición, submit, errores, repeticiones, timeouts (log kernel).
Solo lectura; sin efectos fuera de quien lo importe.
"""
import json
import pathlib
import re

BASE = pathlib.Path(__file__).resolve().parents[3] / "experiments" / "gemma_developer_agent"
DIR_TRAZAS = BASE / "data/replicas_c7/replica_1/results/c7_20261016T0459Z/traces"
LOG_KERNEL = BASE / "data/replicas_c7/replica_1/c7-replica-condicion-7.log"

EDIT_TOOLS = {"edit_file", "write_file"}


def timeouts_del_log():
    tarea_timeout, tarea_sin_submit_explicito = set(), set()
    for line in open(LOG_KERNEL, errors="replace"):
        m = re.search(r"Task (rich_\d+) (agent timed out|completed without explicit submit_patch)", line)
        if m:
            (tarea_timeout if m.group(2).startswith("agent") else tarea_sin_submit_explicito).add(m.group(1))
    return tarea_timeout, tarea_sin_submit_explicito


def parsear_traza(path):
    d = json.load(open(path))
    llamadas = []  # (pos, nombre, status, error_type, pytest?, ts)
    for s in d["steps"]:
        if s.get("source") != "agent":
            continue
        for tc in s.get("tool_calls") or []:
            obs = s.get("observation") or {}
            try:
                contenido = json.loads(obs.get("content", "{}"))
            except Exception:
                contenido = {}
            extra = (tc.get("extra") or {})
            llamadas.append({
                "nombre": tc["function_name"],
                "args": tc.get("arguments", {}),
                "status": contenido.get("status", "?"),
                "error_type": contenido.get("error_type"),
                "patch_size": contenido.get("patch_size"),
                "files_changed": contenido.get("files_changed"),
                "es_pytest": "pytest" in str((tc.get("arguments") or {}).get("command", "")),
                "ts": extra.get("timestamp"),
            })
    primera_edicion = next((i for i, c in enumerate(llamadas) if c["nombre"] in EDIT_TOOLS), None)
    verifico_tras_editar = (
        primera_edicion is not None
        and any(c["nombre"] == "run_command" and i > primera_edicion for i, c in enumerate(llamadas))
    )
    pytest_tras_editar = (
        primera_edicion is not None
        and any(c["es_pytest"] and i > primera_edicion for i, c in enumerate(llamadas))
    )
    submits = [c for c in llamadas if c["nombre"] == "submit_patch"]
    repetidas = sum(
        1 for i in range(1, len(llamadas))
        if llamadas[i]["nombre"] == llamadas[i - 1]["nombre"]
        and llamadas[i]["args"] == llamadas[i - 1]["args"]
    )
    errores = [c for c in llamadas if c["status"] not in ("ok", "?")]
    return {
        "n_llamadas": len(llamadas),
        "llamadas": llamadas,
        "primera_edicion_pos": None if primera_edicion is None else primera_edicion + 1,  # 1-based, como el CSV
        "edito": primera_edicion is not None,
        "verifico_tras_editar": verifico_tras_editar,
        "pytest_tras_editar": pytest_tras_editar,
        "submit_ok": any(c["status"] == "ok" for c in submits),
        "submit_patch_size": next((c["patch_size"] for c in submits if c["status"] == "ok"), None),
        "submit_files_changed": next((c["files_changed"] for c in submits if c["status"] == "ok"), None),
        "n_errores": len(errores),
        "tipos_error": sorted({c["error_type"] for c in errores if c["error_type"]}),
        "n_repetidas_consecutivas": repetidas,
    }


def cargar_todas():
    tareas = {}
    timeouts, sin_submit = timeouts_del_log()
    for p in sorted(DIR_TRAZAS.glob("trace_*.json")):
        tid = p.stem.replace("trace_", "")
        info = parsear_traza(p)
        info["timeout_kernel"] = tid in timeouts
        info["sin_submit_explicito"] = tid in sin_submit
        tareas[tid] = info
    return tareas
