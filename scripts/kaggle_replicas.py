"""Analisis de replicas de la linea base A (issue #103, experimento Kaggle Gemma 4).

Lee recibos por tarea y replica, comprueba su integridad y reporta la variacion de la
condicion A contra si misma: tasa por replica, tareas que cambian de resultado, acuerdo por
pares, desglose por repositorio y la diferencia minima significativa que impone el ruido
observado a una comparacion entre dos condiciones. Solo biblioteca estandar.

Dos subcomandos:

* ``convertir``: pasa el ``task_results.jsonl`` del arnes ``swegemma eval`` a recibos.
* ``analizar``: lee los recibos y escribe el reporte (JSON agregado + tabla en Markdown).

Que cuenta como resultado (la metrica de Kaggle es resueltas / total de tareas):

* ``resolved``: el arnes dijo ``resolved=True``.
* ``unresolved``: la tarea no se resolvio por algo del agente (parche vacio, timeout o presupuesto
  del agente agotados, parche que no aplica, pruebas que fallan). El motivo va en ``failure_reason``.
  Cuenta como no resuelta en tasas, pares y «cambia».
* ``infra_error``: fallo de infraestructura (sandbox, contenedor, snapshot, servidor del modelo). No
  es un resultado del agente: se excluye de los pares y impide la salida 0, porque la tarea hay que
  volver a correrla.

Codigos de salida de ``analizar``:

* 0  analisis completo.
* 1  el analisis se escribio, pero esta incompleto: faltan tareas del subconjunto en alguna replica
  o hay ``infra_error`` (se listan las tareas afectadas; el reporte dice ``completo: false``).
* 2  no se pudo analizar: recibo ilegible o invalido, hashes que no coinciden, tareas fuera del
  subconjunto, duplicados, menos de 2 replicas, etc. No queda ningun reporte (se borran los de una
  corrida anterior). «No pude leer» nunca equivale a «sin hallazgos».
* 3  error inesperado del propio script.

Frontera de fuga: el analisis no lee parches ni ``tasks.jsonl``; solo el hash de ese archivo, y del
subconjunto (salida de ``kaggle_split.py``) lee la lista ``test``. Los recibos guardan el hash del
parche, nunca el parche; una clave desconocida en un recibo (por ejemplo ``patch`` o ``test_patch``)
se rechaza.

El metodo estadistico y el formato de recibo estan descritos en
``experiments/gemma_developer_agent/docs/analisis_replicas.md``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import tempfile
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from fractions import Fraction
from itertools import combinations
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "kaggle-replica-receipt/2"
REPORT_VERSION = "kaggle-replica-analysis/2"

ST_RESOLVED = "resolved"
ST_UNRESOLVED = "unresolved"
ST_INFRA = "infra_error"
STATUS_ALL = (ST_RESOLVED, ST_UNRESOLVED, ST_INFRA)
MISSING = "missing"

FR_EMPTY = "empty_patch"
FR_AGENT_TIMEOUT = "agent_timeout"
FR_BUDGET = "budget_exhausted"
FR_APPLY = "patch_apply_failed"
FR_TESTS = "tests_failed"
FAILURE_REASONS = (FR_EMPTY, FR_AGENT_TIMEOUT, FR_BUDGET, FR_APPLY, FR_TESTS)

SHORT = {ST_RESOLVED: "R", ST_UNRESOLVED: "N", ST_INFRA: "I", MISSING: "-"}

# Lista cerrada de textos de ``error`` que escribe el arnes (HARNESS § 8.2 y § 9). Se compara por
# prefijo. Un texto que no figure aqui NO se clasifica: el conversor y el analisis salen con 2.
AGENT_ERROR_PREFIXES: tuple[tuple[str, str], ...] = (
    ("Agent exceeded session timeout (", FR_AGENT_TIMEOUT),
    ("Agent exceeded turns budget (", FR_BUDGET),
    ("Agent exceeded maximum allowed LLM turns", FR_BUDGET),
    ("Agent exceeded tool call budget (", FR_BUDGET),
    ("Agent completed execution without calling submit_patch.", FR_EMPTY),
    ("Failed to apply agent patch:", FR_APPLY),
    ("Missing or empty JUnit XML report", FR_TESTS),
    ("Malformed JUnit XML report:", FR_TESTS),
    ("No <testsuite> elements found in JUnit XML", FR_TESTS),
    ("No passing tests recorded in JUnit XML (", FR_TESTS),
    ("Test failures/errors recorded in JUnit XML (", FR_TESTS),
    ("Required test node did not pass:", FR_TESTS),
    ("Pytest stdout summary indicates zero or no passing tests", FR_TESTS),
    ("Missing JUnit XML report (possible premature os._exit(0))", FR_TESTS),
)
INFRA_ERROR_PREFIXES: tuple[tuple[str, str], ...] = (
    ("Snapshot file not found:", "snapshot_missing"),
    ("Sandbox execution error:", "sandbox_error"),
    ("Evaluation error:", "evaluation_error"),
    ("Unexpected evaluation worker error:", "worker_error"),
    ("Missing test specification", "missing_test_spec"),
    ("Failed to apply test_patch:", "test_patch_failed"),
)
# Sin ``error`` y con parche, el ``test_exit_code`` del comando de pruebas decide: estos codigos son
# de infraestructura (la tarea se vuelve a correr), no del agente.
INFRA_EXIT_CODES: dict[int, str] = {-1: "test_exec_failed", 124: "test_timeout", 137: "test_killed"}
INFRA_REASONS = (*(r for _, r in INFRA_ERROR_PREFIXES), *INFRA_EXIT_CODES.values())

REQUIRED_KEYS = (
    "schema_version",
    "instance_id",
    "repo",
    "condition",
    "replica",
    "status",
    "failure_reason",
    "infra_reason",
    "resolved",
    "tool_calls",
    "duration_seconds",
    "patch_sha256",
    "submission_sha256",
    "tasks_sha256",
    "subset_sha256",
    "harness_version",
    "sandbox_image",
    "converted_utc",
    "harness_raw",
)
OPTIONAL_KEYS = ("run_utc",)
RAW_KEYS = ("resolved", "error", "test_exit_code", "agent_patch_size", "total_llm_calls")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
UTC_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")
REPORT_MD_HEADER = "# Analisis de replicas de la linea base"
DEFAULT_ALPHA = 0.05
IGNORED_FILE_NAMES = frozenset({".DS_Store", "Thumbs.db", "desktop.ini"})
IGNORED_SUFFIXES = (".pyc", ".pyo")
IGNORED_DIRS = frozenset({"__pycache__"})

EXIT_OK, EXIT_INCOMPLETE, EXIT_INVALID, EXIT_UNEXPECTED = 0, 1, 2, 3


class ReplicasError(ValueError):
    """Entrada que no permite un analisis fiable (se informa con salida 2)."""


@dataclass(frozen=True)
class Recibo:
    """Un recibo validado: una tarea en una replica."""

    instance_id: str
    repo: str
    condition: str
    replica: int
    status: str
    failure_reason: str | None
    infra_reason: str | None
    tool_calls: int
    duration_seconds: float
    patch_sha256: str | None
    submission_sha256: str
    tasks_sha256: str
    subset_sha256: str
    harness_version: str
    sandbox_image: str
    converted_utc: str


# ---------------------------------------------------------------------------
# JSON estricto y hashes
# ---------------------------------------------------------------------------


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        if k in out:
            raise ValueError(f"clave duplicada {k!r}")
        out[k] = v
    return out


def loads_strict(text: str) -> Any:
    """``json.loads`` que rechaza claves duplicadas dentro de un objeto."""
    return json.loads(text, object_pairs_hook=_no_duplicates)


def sha256_file(path: Path) -> str:
    """SHA-256 de un archivo."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def submission_files(path: Path) -> list[tuple[str, str]]:
    """Archivos del envio con su SHA-256, ordenados por ruta POSIX relativa.

    Entran todos los archivos regulares bajo ``path``, salvo ``__pycache__``, ``*.pyc``/``*.pyo`` y
    los archivos de sistema ``.DS_Store``, ``Thumbs.db`` y ``desktop.ini``. Un directorio inexistente
    o sin archivos es un error: un hash del vacio no prueba nada.
    """
    if not path.is_dir():
        raise ReplicasError(f"El directorio del envio no existe: {path}")
    found: list[tuple[str, str]] = []
    for p in path.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(path)
        if (
            set(rel.parts[:-1]) & IGNORED_DIRS
            or p.name in IGNORED_FILE_NAMES
            or p.name.endswith(IGNORED_SUFFIXES)
        ):
            continue
        found.append((rel.as_posix(), sha256_file(p)))
    if not found:
        raise ReplicasError(f"El directorio del envio no tiene archivos que hashear: {path}")
    return sorted(found)


def sha256_directory(path: Path) -> str:
    """SHA-256 del envio: hash de las lineas ``ruta_posix<TAB>sha256_archivo\\n`` ordenadas.

    Se calcula sobre el kit descargado y verificado (``conditions/a_kit/`` se reconstruye con
    ``download_kit.py`` desde ``manifest.json``); el nombre del directorio raiz no cuenta.
    """
    lines = "".join(f"{rel}\t{h}\n" for rel, h in submission_files(path))
    return hashlib.sha256(lines.encode("utf-8")).hexdigest()


def parse_utc(value: object, where: str, key: str) -> str:
    """Valida ``YYYY-MM-DDTHH:MM:SSZ`` con relleno de ceros y fecha real (no solo un patron)."""
    if not isinstance(value, str) or not UTC_RE.fullmatch(value):
        raise ReplicasError(f"{where}: '{key}' debe ser texto YYYY-MM-DDTHH:MM:SSZ.")
    try:
        datetime.strptime(value, UTC_FORMAT)
    except ValueError as exc:
        raise ReplicasError(f"{where}: '{key}' no es una fecha UTC valida ({value!r}).") from exc
    return value


# ---------------------------------------------------------------------------
# Clasificacion de lo que escribe el arnes
# ---------------------------------------------------------------------------


def _int(v: object, where: str, key: str, *, minimum: int | None = None) -> int:
    if not isinstance(v, int) or isinstance(v, bool):
        raise ReplicasError(f"{where}: '{key}' debe ser un entero.")
    if minimum is not None and v < minimum:
        raise ReplicasError(f"{where}: '{key}' debe ser >= {minimum}.")
    return v


def classify_harness(raw: dict[str, Any], where: str) -> tuple[str, str | None, str | None]:
    """Clasifica una fila cruda del arnes en ``(status, failure_reason, infra_reason)``.

    ``resolved`` del arnes manda (tambien con parche vacio). Un ``error`` que no figure en la lista
    cerrada (``AGENT_ERROR_PREFIXES`` / ``INFRA_ERROR_PREFIXES``) o una combinacion incoherente lanzan
    ``ReplicasError``: no hay categoria por defecto. Sin ``error`` y con parche, el ``test_exit_code``
    decide: -1, 124 y 137 son infraestructura; otro negativo o mayor que 128 (senal) no se clasifica;
    el resto es ``tests_failed``.
    """
    resolved = raw.get("resolved")
    if not isinstance(resolved, bool):
        raise ReplicasError(f"{where}: 'resolved' del arnes debe ser booleano, no {resolved!r}.")
    size = _int(raw.get("agent_patch_size"), where, "agent_patch_size", minimum=0)
    exit_code = _int(raw.get("test_exit_code"), where, "test_exit_code")
    _int(raw.get("total_llm_calls"), where, "total_llm_calls", minimum=0)
    error = raw.get("error")
    if error is not None and not isinstance(error, str):
        raise ReplicasError(f"{where}: 'error' del arnes debe ser texto o null.")
    if resolved:
        if exit_code != 0:
            raise ReplicasError(
                f"{where}: combinacion incoherente: resolved=true con test_exit_code={exit_code}."
            )
        return ST_RESOLVED, None, None
    if not error:
        if exit_code == 0:
            raise ReplicasError(
                f"{where}: combinacion incoherente: resolved=false, sin error y test_exit_code=0."
            )
        if size == 0:
            return ST_UNRESOLVED, FR_EMPTY, None
        if exit_code in INFRA_EXIT_CODES:
            return ST_INFRA, None, INFRA_EXIT_CODES[exit_code]
        if exit_code < 0 or exit_code > 128:
            raise ReplicasError(
                f"{where}: test_exit_code={exit_code} sin error del arnes: no se clasifica "
                "(negativo distinto de -1 o senal distinta de 137)."
            )
        return ST_UNRESOLVED, FR_TESTS, None
    for prefix, reason in AGENT_ERROR_PREFIXES:
        if error.startswith(prefix):
            return ST_UNRESOLVED, reason, None
    for prefix, infra in INFRA_ERROR_PREFIXES:
        if error.startswith(prefix):
            return ST_INFRA, None, infra
    raise ReplicasError(
        f"{where}: texto de error del arnes fuera de la lista cerrada, no se clasifica: {error[:300]!r}"
    )


# ---------------------------------------------------------------------------
# Lectura y validacion de recibos
# ---------------------------------------------------------------------------


def _text(obj: dict[str, Any], key: str, where: str) -> str:
    v = obj.get(key)
    if not isinstance(v, str) or not v:
        raise ReplicasError(f"{where}: '{key}' debe ser texto no vacio.")
    return v


def _sha(obj: dict[str, Any], key: str, where: str, *, nullable: bool = False) -> str | None:
    v = obj.get(key)
    if v is None and nullable:
        return None
    if not isinstance(v, str) or not SHA_RE.fullmatch(v):
        raise ReplicasError(f"{where}: '{key}' debe ser un SHA-256 hexadecimal en minusculas.")
    return v


def parse_receipt(obj: object, where: str) -> Recibo:
    """Valida un objeto JSON como recibo; lanza ReplicasError con ``where`` si algo no cuadra.

    Reclasifica ``harness_raw`` con la lista cerrada y exige que coincida con ``status``,
    ``failure_reason`` e ``infra_reason``: un recibo editado a mano no pasa.
    """
    if not isinstance(obj, dict):
        raise ReplicasError(f"{where}: el recibo debe ser un objeto JSON.")
    faltan = [k for k in REQUIRED_KEYS if k not in obj]
    if faltan:
        raise ReplicasError(f"{where}: faltan claves {faltan}.")
    sobran = sorted(set(obj) - set(REQUIRED_KEYS) - set(OPTIONAL_KEYS))
    if sobran:
        raise ReplicasError(
            f"{where}: claves desconocidas {sobran} (un recibo guarda hashes, nunca parches ni pruebas)."
        )
    if obj["schema_version"] != SCHEMA_VERSION:
        raise ReplicasError(
            f"{where}: schema_version {obj['schema_version']!r}, se esperaba {SCHEMA_VERSION!r}."
        )
    status = obj["status"]
    if status not in STATUS_ALL:
        raise ReplicasError(f"{where}: status {status!r} no es uno de {list(STATUS_ALL)}.")
    reason = obj["failure_reason"]
    if status == ST_UNRESOLVED:
        if reason not in FAILURE_REASONS:
            raise ReplicasError(f"{where}: failure_reason {reason!r} no es uno de {list(FAILURE_REASONS)}.")
    elif reason is not None:
        raise ReplicasError(f"{where}: failure_reason debe ser null salvo con status 'unresolved'.")
    resolved = obj["resolved"]
    if not isinstance(resolved, bool):
        raise ReplicasError(f"{where}: 'resolved' debe ser booleano.")
    if resolved != (status == ST_RESOLVED):
        raise ReplicasError(f"{where}: 'resolved'={resolved} contradice status={status!r}.")
    replica = _int(obj["replica"], where, "replica", minimum=1)
    tool_calls = _int(obj["tool_calls"], where, "tool_calls", minimum=0)
    dur = obj["duration_seconds"]
    if isinstance(dur, bool) or not isinstance(dur, int | float) or not math.isfinite(dur) or dur < 0:
        raise ReplicasError(f"{where}: 'duration_seconds' debe ser un numero finito >= 0.")
    raw = obj["harness_raw"]
    if not isinstance(raw, dict) or set(raw) != set(RAW_KEYS):
        raise ReplicasError(f"{where}: 'harness_raw' debe ser un objeto con exactamente {list(RAW_KEYS)}.")
    infra_reason = obj["infra_reason"]
    if status == ST_INFRA:
        if infra_reason not in INFRA_REASONS:
            raise ReplicasError(f"{where}: infra_reason {infra_reason!r} no es uno de {list(INFRA_REASONS)}.")
    elif infra_reason is not None:
        raise ReplicasError(f"{where}: infra_reason debe ser null salvo con status 'infra_error'.")
    if classify_harness(raw, where) != (status, reason, infra_reason):
        raise ReplicasError(f"{where}: status/failure_reason/infra_reason no corresponden a 'harness_raw'.")
    patch_sha = _sha(obj, "patch_sha256", where, nullable=True)
    if (patch_sha is None) != (raw["agent_patch_size"] == 0):
        raise ReplicasError(f"{where}: 'patch_sha256' debe ser null si y solo si agent_patch_size es 0.")
    if "run_utc" in obj and obj["run_utc"] is not None:
        parse_utc(obj["run_utc"], where, "run_utc")
    return Recibo(
        instance_id=_text(obj, "instance_id", where),
        repo=_text(obj, "repo", where),
        condition=_text(obj, "condition", where),
        replica=replica,
        status=status,
        failure_reason=reason,
        infra_reason=infra_reason,
        tool_calls=tool_calls,
        duration_seconds=float(dur),
        patch_sha256=patch_sha,
        submission_sha256=_sha(obj, "submission_sha256", where) or "",
        tasks_sha256=_sha(obj, "tasks_sha256", where) or "",
        subset_sha256=_sha(obj, "subset_sha256", where) or "",
        harness_version=_text(obj, "harness_version", where),
        sandbox_image=_text(obj, "sandbox_image", where),
        converted_utc=parse_utc(obj["converted_utc"], where, "converted_utc"),
    )


def expand_receipt_paths(paths: Iterable[Path]) -> list[Path]:
    """Archivos ``.jsonl`` de las rutas dadas (un directorio aporta sus ``*.jsonl``, ordenados)."""
    files: list[Path] = []
    for p in paths:
        if p.is_dir():
            found = sorted(p.glob("*.jsonl"))
            if not found:
                raise ReplicasError(f"El directorio de recibos {p} no contiene archivos .jsonl.")
            files.extend(found)
        elif p.is_file():
            files.append(p)
        else:
            raise ReplicasError(f"Ruta de recibos no encontrada: {p}")
    return files


def load_receipts(paths: Iterable[Path]) -> list[Recibo]:
    """Lee y valida todos los recibos; cualquier linea ilegible o invalida detiene el analisis.

    Un archivo sin recibos (vacio o solo lineas en blanco) tambien es un error.
    """
    receipts: list[Recibo] = []
    for f in expand_receipt_paths(paths):
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise ReplicasError(f"No se pudo leer {f}: {exc}") from exc
        antes = len(receipts)
        for numero, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            where = f"{f.name}:{numero}"
            try:
                obj = loads_strict(line)
            except ValueError as exc:
                raise ReplicasError(f"{where}: no es JSON valido: {exc}") from exc
            receipts.append(parse_receipt(obj, where))
        if len(receipts) == antes:
            raise ReplicasError(f"{f.name}: el archivo de recibos no tiene ningun recibo.")
    return receipts


@dataclass(frozen=True)
class Subconjunto:
    """Subconjunto pre-registrado: ids de prueba, hash del archivo y ``sha256_tasks`` declarado."""

    ids: tuple[str, ...]
    sha256_file: str
    sha256_tasks: str | None


def load_subset(path: Path) -> Subconjunto:
    """Lee la salida de ``kaggle_split.py``: usa la lista ``test`` y el ``sha256_tasks`` declarado."""
    if not path.is_file():
        raise ReplicasError(f"Archivo de subconjunto no encontrado: {path}")
    try:
        data = loads_strict(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ReplicasError(f"No se pudo leer el subconjunto {path}: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("test"), list):
        raise ReplicasError(f"El subconjunto {path} debe ser un objeto JSON con la lista 'test'.")
    ids = data["test"]
    if not ids or not all(isinstance(i, str) and i for i in ids):
        raise ReplicasError(f"La lista 'test' de {path} debe tener ids de texto y no estar vacia.")
    if len(set(ids)) != len(ids):
        raise ReplicasError(f"La lista 'test' de {path} tiene ids repetidos.")
    declared = data.get("sha256_tasks")
    if declared is not None and not isinstance(declared, str):
        raise ReplicasError(f"'sha256_tasks' de {path} debe ser texto.")
    return Subconjunto(tuple(sorted(ids)), sha256_file(path), declared or None)


def resolve_tasks_sha(subset: Subconjunto, explicit: str | None) -> str:
    """Hash de ``tasks.jsonl`` de referencia: el del subconjunto, el explicito, o error."""
    if explicit is not None and not SHA_RE.fullmatch(explicit):
        raise ReplicasError("--tasks-sha256 debe ser un SHA-256 hexadecimal en minusculas.")
    declared = subset.sha256_tasks
    if declared is not None and not SHA_RE.fullmatch(declared):
        raise ReplicasError("El 'sha256_tasks' del subconjunto no es un SHA-256 hexadecimal en minusculas.")
    if declared and explicit and declared != explicit:
        raise ReplicasError("--tasks-sha256 contradice el 'sha256_tasks' que declara el subconjunto.")
    ref = declared or explicit
    if not ref:
        raise ReplicasError(
            "El subconjunto no declara 'sha256_tasks' y no se dio --tasks-sha256: "
            "no hay con que comparar el hash de tasks.jsonl de los recibos."
        )
    return ref


def check_integrity(receipts: Sequence[Recibo], subset: Subconjunto, tasks_sha_ref: str) -> list[str]:
    """Devuelve los problemas de integridad (lista vacia = recibos coherentes)."""
    problems: list[str] = []
    if not receipts:
        return ["No hay recibos."]
    for campo, etiqueta in (
        ("tasks_sha256", "tasks.jsonl"),
        ("submission_sha256", "envio"),
        ("subset_sha256", "subconjunto"),
        ("condition", "condicion"),
        ("harness_version", "version del arnes"),
        ("sandbox_image", "imagen del sandbox"),
    ):
        valores = sorted({getattr(r, campo) for r in receipts})
        if len(valores) > 1:
            problems.append(f"Los recibos mezclan {len(valores)} valores de {etiqueta}: {valores}")
    if {r.subset_sha256 for r in receipts} - {subset.sha256_file}:
        problems.append(
            f"El hash del subconjunto en los recibos no es el del archivo dado ({subset.sha256_file})."
        )
    if {r.tasks_sha256 for r in receipts} - {tasks_sha_ref}:
        problems.append(f"El hash de tasks.jsonl en los recibos no es el de referencia ({tasks_sha_ref}).")
    fuera = sorted({r.instance_id for r in receipts} - set(subset.ids))
    if fuera:
        problems.append(f"Tareas fuera del subconjunto pre-registrado: {fuera}")
    vistos: dict[tuple[str, int], int] = {}
    for r in receipts:
        vistos[(r.instance_id, r.replica)] = vistos.get((r.instance_id, r.replica), 0) + 1
    for (iid, rep), n in sorted(vistos.items()):
        if n > 1:
            problems.append(f"Recibo duplicado para la tarea {iid!r} en la replica {rep} ({n} veces).")
    repos: dict[str, set[str]] = {}
    for r in receipts:
        repos.setdefault(r.instance_id, set()).add(r.repo)
    for iid, rs in sorted(repos.items()):
        if len(rs) > 1:
            problems.append(f"La tarea {iid!r} aparece con repositorios distintos: {sorted(rs)}")
    n_rep = len({r.replica for r in receipts})
    if n_rep < 2:
        problems.append(f"Se necesitan al menos 2 replicas distintas; hay {n_rep}.")
    return problems


# ---------------------------------------------------------------------------
# Estadistica exacta (stdlib)
# ---------------------------------------------------------------------------


def binom_cdf(k: int, n: int, p: float) -> float:
    """P(X <= k) para X ~ Binomial(n, p). Calculo en logaritmos: sin desbordes con n grande."""
    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    if p <= 0.0:
        return 1.0
    if p >= 1.0:
        return 0.0
    lp, lq = math.log(p), math.log1p(-p)
    base = math.lgamma(n + 1)
    total = 0.0
    for i in range(k + 1):
        total += math.exp(base - math.lgamma(i + 1) - math.lgamma(n - i + 1) + i * lp + (n - i) * lq)
    return min(1.0, total)


def clopper_pearson(x: int, n: int, alpha: float = DEFAULT_ALPHA) -> tuple[float, float]:
    """Intervalo exacto de Clopper-Pearson de nivel ``1 - alpha`` para x exitos en n (n >= 1).

    Se obtiene por biseccion sobre la funcion de distribucion binomial.
    """
    if n < 1 or not 0 <= x <= n:
        raise ValueError("Se requiere n >= 1 y 0 <= x <= n.")
    lo, hi = 0.0, 1.0
    if x > 0:
        a, b = 0.0, 1.0  # P(X >= x | p) = alpha/2, creciente en p
        for _ in range(100):
            m = (a + b) / 2
            if 1.0 - binom_cdf(x - 1, n, m) < alpha / 2:
                a = m
            else:
                b = m
        lo = (a + b) / 2
    if x < n:
        a, b = 0.0, 1.0  # P(X <= x | p) = alpha/2, decreciente en p
        for _ in range(100):
            m = (a + b) / 2
            if binom_cdf(x, n, m) > alpha / 2:
                a = m
            else:
                b = m
        hi = (a + b) / 2
    return lo, hi


def mcnemar_exact_p(b: int, c: int) -> float:
    """p-valor bilateral exacto de McNemar: ``min(1, 2 * P(X <= min(b, c)))`` con X ~ Bin(b + c, 1/2)."""
    d = b + c
    if d == 0:
        return 1.0
    cola = sum(math.comb(d, i) for i in range(min(b, c) + 1))
    return float(min(1.0, 2 * cola / 2**d))


def discordance_floor(alpha: float = DEFAULT_ALPHA) -> int:
    """Menor numero de pares discordantes, todos a favor de una condicion, con p exacto <= alpha.

    Es ``min d`` con ``2 / 2**d <= alpha``: 6 con alpha = 0,05 (p = 0,03125; con 5 es 0,0625).
    """
    if not 0 < alpha < 1:
        raise ValueError("alpha debe estar entre 0 y 1 (exclusivo).")
    umbral = Fraction(str(alpha))
    d = 1
    while Fraction(2, 2**d) > umbral:
        d += 1
    return d


def min_significant_difference(d: int, n: int, alpha: float = DEFAULT_ALPHA) -> dict[str, Any]:
    """Menor diferencia de tasa que McNemar exacto declararia significativa con ``d`` discordantes.

    Entre ``d`` pares discordantes, una condicion gana ``g`` y la otra ``d - g`` (g > d - g).
    La diferencia de tasas es ``(2g - d) / n``; se busca el menor ``g`` con p <= alpha. Es un umbral
    de significacion, no de potencia. ``alcanzable`` es falso si ni ``g = d`` alcanza ``alpha``.
    """
    if n < 1 or d < 0 or d > n:
        raise ValueError("Se requiere n >= 1 y 0 <= d <= n.")
    umbral = Fraction(str(alpha))
    for g in range(d // 2 + 1, d + 1):
        cola = sum(math.comb(d, i) for i in range(d - g + 1))
        if Fraction(2 * cola, 2**d) <= umbral:
            dif = 2 * g - d
            return {
                "discordantes": d,
                "alcanzable": True,
                "ganadas_minimas": g,
                "diferencia_pares": dif,
                "diferencia_tasa": round(dif / n, 6),
            }
    return {
        "discordantes": d,
        "alcanzable": False,
        "ganadas_minimas": None,
        "diferencia_pares": None,
        "diferencia_tasa": None,
    }


# ---------------------------------------------------------------------------
# Analisis
# ---------------------------------------------------------------------------


def _ratio(num: int, den: int) -> float | None:
    return round(num / den, 6) if den else None


def analyze(
    receipts: Sequence[Recibo],
    subset: Subconjunto,
    alpha: float = DEFAULT_ALPHA,
    envio_archivos: Sequence[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    """Calcula el reporte agregado. Supone recibos ya comprobados con ``check_integrity``."""
    replicas = sorted({r.replica for r in receipts})
    ids = list(subset.ids)
    by_key = {(r.instance_id, r.replica): r for r in receipts}
    repo_of = {r.instance_id: r.repo for r in receipts}

    def estado(iid: str, rep: int) -> str:
        r = by_key.get((iid, rep))
        return r.status if r else MISSING

    def motivo(iid: str, rep: int) -> str | None:
        r = by_key.get((iid, rep))
        return r.failure_reason if r else None

    def valido(s: str) -> bool:
        return s in (ST_RESOLVED, ST_UNRESOLVED)

    por_replica: list[dict[str, Any]] = []
    for rep in replicas:
        cuentas = {s: 0 for s in (*STATUS_ALL, MISSING)}
        motivos = {m: 0 for m in FAILURE_REASONS}
        for iid in ids:
            cuentas[estado(iid, rep)] += 1
            m = motivo(iid, rep)
            if m:
                motivos[m] += 1
        validas = cuentas[ST_RESOLVED] + cuentas[ST_UNRESOLVED]
        por_replica.append(
            {
                "replica": rep,
                "tareas_subconjunto": len(ids),
                "resueltas": cuentas[ST_RESOLVED],
                "no_resueltas": cuentas[ST_UNRESOLVED],
                "no_resueltas_por_motivo": motivos,
                "infra_error": cuentas[ST_INFRA],
                "faltantes": cuentas[MISSING],
                "validas": validas,
                "tasa_sobre_subconjunto": _ratio(cuentas[ST_RESOLVED], len(ids)),
                "tasa_sobre_validas": _ratio(cuentas[ST_RESOLVED], validas),
            }
        )

    tareas: list[dict[str, Any]] = []
    for iid in ids:
        validos = [estado(iid, rep) for rep in replicas if valido(estado(iid, rep))]
        n_res = sum(1 for s in validos if s == ST_RESOLVED)
        cambia: bool | None = (0 < n_res < len(validos)) if len(validos) >= 2 else None
        tareas.append(
            {
                "instance_id": iid,
                "repo": repo_of.get(iid),
                "resultados": {str(rep): estado(iid, rep) for rep in replicas},
                "motivos": {str(rep): motivo(iid, rep) for rep in replicas},
                "validas": len(validos),
                "resueltas": n_res,
                "cambia": cambia,
            }
        )
    evaluables = [t for t in tareas if t["cambia"] is not None]
    cambian = [t for t in evaluables if t["cambia"]]

    pares: list[dict[str, Any]] = []
    for ra, rb in combinations(replicas, 2):
        a = b = c = d = 0
        for iid in ids:
            sa, sb = estado(iid, ra), estado(iid, rb)
            if not (valido(sa) and valido(sb)):
                continue
            if sa == ST_RESOLVED and sb == ST_RESOLVED:
                a += 1
            elif sa == ST_RESOLVED:
                b += 1
            elif sb == ST_RESOLVED:
                c += 1
            else:
                d += 1
        n = a + b + c + d
        disc = b + c
        ic: dict[str, float] | None = None
        if n:
            lo, hi = clopper_pearson(disc, n, alpha)
            ic = {"inferior": round(lo, 6), "superior": round(hi, 6)}
        pares.append(
            {
                "replicas": [ra, rb],
                "comparables": n,
                "ambas_resueltas": a,
                "solo_primera": b,
                "solo_segunda": c,
                "ninguna_resuelta": d,
                "discordantes": disc,
                "acuerdo": {"numerador": a + d, "denominador": n, "tasa": _ratio(a + d, n)},
                "tasa_discordancia": _ratio(disc, n),
                "intervalo_discordancia": ic,
                "mcnemar_p_exacto": round(mcnemar_exact_p(b, c), 6) if n else None,
            }
        )

    sin_recibos = "(sin recibos)"
    por_repo: list[dict[str, Any]] = []
    for repo in sorted({t["repo"] if t["repo"] is not None else sin_recibos for t in tareas}):
        ts = [t for t in tareas if (t["repo"] if t["repo"] is not None else sin_recibos) == repo]
        fila_reps = []
        for rep in replicas:
            ests = [estado(t["instance_id"], rep) for t in ts]
            fila_reps.append(
                {
                    "replica": rep,
                    "resueltas": sum(1 for e in ests if e == ST_RESOLVED),
                    "validas": sum(1 for e in ests if valido(e)),
                    "infra_error": sum(1 for e in ests if e == ST_INFRA),
                    "faltantes": sum(1 for e in ests if e == MISSING),
                }
            )
        ev = [t for t in ts if t["cambia"] is not None]
        por_repo.append(
            {
                "repo": repo,
                "tareas": len(ts),
                "por_replica": fila_reps,
                "cambian": {"numerador": sum(1 for t in ev if t["cambia"]), "denominador": len(ev)},
            }
        )

    faltantes = [
        {"instance_id": iid, "replicas": [rep for rep in replicas if (iid, rep) not in by_key]}
        for iid in ids
        if any((iid, rep) not in by_key for rep in replicas)
    ]
    infra = [
        {
            "instance_id": iid,
            "replica": rep,
            "status": ST_INFRA,
            "infra_reason": by_key[(iid, rep)].infra_reason,
        }
        for iid in ids
        for rep in replicas
        if estado(iid, rep) == ST_INFRA
    ]
    tasas = [p["tasa_sobre_subconjunto"] for p in por_replica]
    primero = receipts[0]
    # se ordena como fecha (datetime), no como texto
    fechas = sorted((r.converted_utc for r in receipts), key=lambda s: datetime.strptime(s, UTC_FORMAT))
    entrada: dict[str, Any] = {
        "condicion": primero.condition,
        "tasks_sha256": primero.tasks_sha256,
        "envio_sha256": primero.submission_sha256,
        "subconjunto_sha256": primero.subset_sha256,
        "version_arnes": primero.harness_version,
        "imagen_sandbox": primero.sandbox_image,
        "recibos": len(receipts),
        "replicas": replicas,
        "tareas_subconjunto": len(ids),
        "convertido_utc_primero": min(fechas),
        "convertido_utc_ultimo": max(fechas),
    }
    if envio_archivos is not None:
        entrada["envio_archivos"] = [{"ruta": rel, "sha256": h} for rel, h in envio_archivos]

    return {
        "version_reporte": REPORT_VERSION,
        "completo": not faltantes and not infra,
        "entrada": entrada,
        "por_replica": por_replica,
        "tareas": tareas,
        "cambian_de_resultado": {
            "numerador": len(cambian),
            "denominador": len(evaluables),
            "tareas": [t["instance_id"] for t in cambian],
            "no_evaluables": [t["instance_id"] for t in tareas if t["cambia"] is None],
        },
        "pares": pares,
        "por_repositorio": por_repo,
        "errores_de_infraestructura": infra,
        "infra_afectadas": sorted({x["instance_id"] for x in infra}),
        "faltantes": faltantes,
        "margen": _margin(pares, tasas, alpha),
    }


MARGIN_METHOD = (
    "Del par de replicas con mayor tasa de discordancia (discordantes / comparables) se toma el "
    "intervalo exacto de Clopper-Pearson. Para cada numero de discordantes d entre el observado y el "
    "del limite superior (ceil(limite * comparables)) se busca la menor diferencia de tasa que una "
    "prueba de McNemar exacta bilateral declararia significativa; la cota es el maximo sobre ese rango "
    "(la funcion no es monotona en d). Ademas se reporta el suelo: el menor numero de pares "
    "discordantes, todos a favor de una condicion, con p <= alfa."
)
MARGIN_NOTE = (
    "Es una diferencia minima significativa, no un calculo de potencia: un efecto real de ese tamano "
    "se declararia significativo aproximadamente la mitad de las veces."
)


def _margin(pares: list[dict[str, Any]], tasas: list[float | None], alpha: float) -> dict[str, Any]:
    """Diferencia minima significativa que impone el ruido A-contra-A; ver el documento de metodo."""
    reales = [t for t in tasas if t is not None]
    base: dict[str, Any] = {
        "alfa": alpha,
        "metodo": MARGIN_METHOD,
        "nota": MARGIN_NOTE,
        "diferencia_observada_entre_replicas": round(max(reales) - min(reales), 6) if reales else None,
    }
    con_datos = [p for p in pares if p["comparables"] > 0]
    if not con_datos:
        return {**base, "calculable": False, "motivo": "ningun par de replicas tiene tareas comparables"}
    peor = max(
        con_datos,
        key=lambda p: (Fraction(p["discordantes"], p["comparables"]), -p["replicas"][0], -p["replicas"][1]),
    )
    n, d = peor["comparables"], peor["discordantes"]
    _, hi = clopper_pearson(d, n, alpha)
    d_hi = max(d, min(n, math.ceil(hi * n - 1e-9)))
    piso = discordance_floor(alpha)
    tabla = [min_significant_difference(k, n, alpha) for k in range(d, d_hi + 1)]
    alcanzables = [x for x in tabla if x["alcanzable"]]
    maxima = (
        max(alcanzables, key=lambda x: (x["diferencia_pares"], -x["discordantes"])) if alcanzables else None
    )
    return {
        **base,
        "calculable": True,
        "par_base": peor["replicas"],
        "comparables": n,
        "discordantes_observados": d,
        "limite_superior_discordancia": round(hi, 6),
        "discordantes_limite_superior": d_hi,
        "suelo": {
            "pares_discordantes_unilaterales": piso,
            "alcanzable": n >= piso,
            "diferencia_tasa": round(piso / n, 6) if n >= piso else None,
        },
        "por_discordantes": tabla,
        "diferencia_minima_significativa": maxima["diferencia_tasa"] if maxima else None,
        "discordantes_de_la_maxima": maxima["discordantes"] if maxima else None,
    }


# ---------------------------------------------------------------------------
# Salida
# ---------------------------------------------------------------------------


def _f(x: float | None) -> str:
    return "n/d" if x is None else f"{x:.3f}"


def render_json(report: dict[str, Any]) -> str:
    """JSON canonico: claves ordenadas, sangria 2, salto final; mismo reporte, mismos bytes."""
    return json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def render_markdown(report: dict[str, Any]) -> str:
    """Tabla en Markdown del reporte; determinista."""
    e = report["entrada"]
    reps = e["replicas"]
    out: list[str] = ["# Analisis de replicas de la linea base", ""]
    if not report["completo"]:
        out += ["**INCOMPLETO: faltan recibos o hay errores de infraestructura; ver abajo.**", ""]
    out += [
        f"- Condicion: `{e['condicion']}`; replicas: {reps}; recibos: {e['recibos']}; "
        f"tareas del subconjunto: {e['tareas_subconjunto']}",
        f"- `tasks.jsonl` sha256: `{e['tasks_sha256']}`",
        f"- Envio sha256: `{e['envio_sha256']}`",
        f"- Subconjunto sha256: `{e['subconjunto_sha256']}`",
        f"- Arnes: `{e['version_arnes']}`; imagen: `{e['imagen_sandbox']}`",
        f"- Recibos convertidos del {e['convertido_utc_primero']} al {e['convertido_utc_ultimo']}",
        "",
        "## Tasa de resolucion por replica",
        "",
        "Tasa principal: resueltas / tareas del subconjunto (la metrica de Kaggle). "
        "Secundaria: resueltas / validas, sin las tareas con error de infraestructura ni faltantes.",
        "",
        "| Replica | Tasa principal (resueltas/subconjunto) | Secundaria (resueltas/validas) "
        "| No resueltas | Infra | Faltantes |",
        "|---|---|---|---|---|---|",
    ]
    for p in report["por_replica"]:
        out.append(
            f"| {p['replica']} | {p['resueltas']}/{p['tareas_subconjunto']} = "
            f"{_f(p['tasa_sobre_subconjunto'])} | {p['resueltas']}/{p['validas']} = "
            f"{_f(p['tasa_sobre_validas'])} | {p['no_resueltas']} | {p['infra_error']} | {p['faltantes']} |"
        )
    out += ["", "No resueltas por motivo:", ""]
    out += [
        "| Replica | " + " | ".join(FAILURE_REASONS) + " |",
        "|---|" + "---|" * len(FAILURE_REASONS),
    ]
    for p in report["por_replica"]:
        out.append(
            f"| {p['replica']} | "
            + " | ".join(str(p["no_resueltas_por_motivo"][m]) for m in FAILURE_REASONS)
            + " |"
        )
    cd = report["cambian_de_resultado"]
    out += [
        "",
        "## Tareas que cambian de resultado entre replicas",
        "",
        f"**{cd['numerador']}/{cd['denominador']}** tareas evaluables (con al menos 2 replicas validas) "
        "tienen resultados distintos entre replicas.",
    ]
    if cd["tareas"]:
        out += ["", "Cambian: " + ", ".join(f"`{t}`" for t in cd["tareas"])]
    if cd["no_evaluables"]:
        out += ["", "No evaluables: " + ", ".join(f"`{t}`" for t in cd["no_evaluables"])]
    out += ["", "## Acuerdo por pares de replicas", ""]
    out += [
        "| Par | Comparables | R/R | R/N | N/R | N/N | Acuerdo | Discordancia (IC) | p McNemar exacto |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for q in report["pares"]:
        ic = q["intervalo_discordancia"]
        ic_txt = (
            "n/d"
            if ic is None
            else f"{_f(q['tasa_discordancia'])} [{_f(ic['inferior'])}, {_f(ic['superior'])}]"
        )
        ac = q["acuerdo"]
        out.append(
            f"| {q['replicas'][0]}-{q['replicas'][1]} | {q['comparables']} | {q['ambas_resueltas']} | "
            f"{q['solo_primera']} | {q['solo_segunda']} | {q['ninguna_resuelta']} | "
            f"{ac['numerador']}/{ac['denominador']} = {_f(ac['tasa'])} | {ic_txt} | "
            f"{_f(q['mcnemar_p_exacto'])} |"
        )
    out += [
        "",
        "## Resultado por tarea",
        "",
        "R = resuelta, N = no resuelta (motivo en el JSON), I = error de infraestructura, - = sin recibo.",
        "",
        "| Tarea | Repositorio | " + " | ".join(f"Rep {r}" for r in reps) + " | Cambia |",
        "|---|---|" + "---|" * len(reps) + "---|",
    ]
    for t in report["tareas"]:
        cam = "n/d" if t["cambia"] is None else ("si" if t["cambia"] else "no")
        out.append(
            f"| `{t['instance_id']}` | {t['repo'] or '(sin recibos)'} | "
            + " | ".join(SHORT[t["resultados"][str(r)]] for r in reps)
            + f" | {cam} |"
        )
    out += ["", "## Desglose por repositorio", ""]
    out += [
        "| Repositorio | Tareas | " + " | ".join(f"Rep {r} (res/val)" for r in reps) + " | Cambian |",
        "|---|---|" + "---|" * len(reps) + "---|",
    ]
    for g in report["por_repositorio"]:
        out.append(
            f"| {g['repo']} | {g['tareas']} | "
            + " | ".join(f"{x['resueltas']}/{x['validas']}" for x in g["por_replica"])
            + f" | {g['cambian']['numerador']}/{g['cambian']['denominador']} |"
        )
    out += ["", "## Errores de infraestructura (hay que volver a correr estas tareas)", ""]
    if report["errores_de_infraestructura"]:
        out += ["| Tarea | Replica | Motivo |", "|---|---|---|"]
        out += [
            f"| `{x['instance_id']}` | {x['replica']} | {x['infra_reason']} |"
            for x in report["errores_de_infraestructura"]
        ]
    else:
        out.append("Ninguno.")
    out += ["", "## Faltantes (sin recibo)", ""]
    if report["faltantes"]:
        out += ["| Tarea | Replicas sin recibo |", "|---|---|"]
        out += [f"| `{x['instance_id']}` | {x['replicas']} |" for x in report["faltantes"]]
    else:
        out.append("Ninguno.")
    m = report["margen"]
    out += [
        "",
        "## Diferencia minima significativa impuesta por el ruido A-contra-A",
        "",
        f"Alfa: {m['alfa']}. Metodo: {m['metodo']}",
        "",
        m["nota"],
        "",
        "- Diferencia observada entre la mayor y la menor tasa de replica: "
        f"{_f(m['diferencia_observada_entre_replicas'])}",
    ]
    if not m["calculable"]:
        out.append(f"- No calculable: {m['motivo']}.")
    else:
        s = m["suelo"]
        out.append(
            f"- Par base: {m['par_base']}; {m['discordantes_observados']}/{m['comparables']} discordantes; "
            f"limite superior de la discordancia: {_f(m['limite_superior_discordancia'])} "
            f"({m['discordantes_limite_superior']} discordantes)."
        )
        if s["alcanzable"]:
            out.append(
                f"- Suelo: {s['pares_discordantes_unilaterales']} pares discordantes a favor de una "
                f"condicion alcanzan alfa; con {m['comparables']} tareas es una diferencia de "
                f"{s['pares_discordantes_unilaterales']}/{m['comparables']} = {_f(s['diferencia_tasa'])}."
            )
        else:
            out.append(
                f"- Suelo: se necesitan {s['pares_discordantes_unilaterales']} pares discordantes a favor de "
                f"una condicion y solo hay {m['comparables']} tareas comparables: no alcanzable."
            )
        out += [
            "",
            "| Discordantes | Pares ganados minimos | Diferencia (pares) | Diferencia de tasa |",
            "|---|---|---|---|",
        ]
        for x in m["por_discordantes"]:
            if x["alcanzable"]:
                out.append(
                    f"| {x['discordantes']} | {x['ganadas_minimas']} | {x['diferencia_pares']} | "
                    f"{_f(x['diferencia_tasa'])} |"
                )
            else:
                out.append(f"| {x['discordantes']} | n/a | n/a | n/a |")
        out.append("")
        if m["diferencia_minima_significativa"] is None:
            out.append("- Diferencia minima significativa: no calculable con esos discordantes (ver suelo).")
        else:
            out.append(
                f"- Diferencia minima significativa (maximo del rango, con {m['discordantes_de_la_maxima']} "
                f"discordantes): {_f(m['diferencia_minima_significativa'])}."
            )
    if "envio_archivos" in e:
        out += [
            "",
            "## Archivos del envio (para contrastar con el manifiesto)",
            "",
            "| Ruta | sha256 |",
            "|---|---|",
        ]
        out += [f"| `{x['ruta']}` | `{x['sha256']}` |" for x in e["envio_archivos"]]
    out.append("")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Conversor arnes -> recibos
# ---------------------------------------------------------------------------


def convert_harness_results(
    task_results: Path,
    *,
    patches_dir: Path | None,
    subset_ids: Iterable[str],
    replica: int,
    condition: str,
    submission_sha256: str,
    tasks_sha256: str,
    subset_sha256: str,
    harness_version: str,
    sandbox_image: str,
    converted_utc: str,
    run_utc: str | None = None,
) -> list[dict[str, Any]]:
    """Convierte el ``task_results.jsonl`` de ``swegemma eval`` en recibos (diccionarios).

    Claves del arnes usadas: ``instance_id``, ``repo``, ``resolved``, ``agent_patch_size``,
    ``test_exit_code``, ``duration_seconds``, ``error``, ``tool_calls`` y ``total_llm_calls`` (HARNESS
    § 9.2). El estado sale de ``classify_harness`` (``resolved`` del arnes manda; los textos de
    ``error`` se comparan con una lista cerrada, HARNESS § 8.2). El recibo conserva los campos crudos
    en ``harness_raw`` para poder reclasificar sin el ``task_results.jsonl``. El hash del parche sale
    de ``<patches_dir>/<instance_id>.patch`` con «/» sustituido por «__» como hace el arnes (HARNESS
    § 9.2). Antes de devolver nada comprueba que no
    haya tareas repetidas ni ajenas al subconjunto.
    """
    try:
        lines = task_results.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise ReplicasError(f"No se pudo leer {task_results}: {exc}") from exc
    permitidos = set(subset_ids)
    _int(replica, "convertir", "replica", minimum=1)
    parse_utc(converted_utc, "convertir", "converted_utc")
    if run_utc is not None:
        parse_utc(run_utc, "convertir", "run_utc")
    recibos: list[dict[str, Any]] = []
    for numero, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        where = f"{task_results.name}:{numero}"
        try:
            row = loads_strict(line)
        except ValueError as exc:
            raise ReplicasError(f"{where}: no es JSON valido: {exc}") from exc
        if not isinstance(row, dict):
            raise ReplicasError(f"{where}: se esperaba un objeto JSON.")
        for k in (*RAW_KEYS, "instance_id", "repo", "duration_seconds", "tool_calls"):
            if k not in row:
                raise ReplicasError(f"{where}: falta la clave '{k}' del arnes.")
        raw = {k: row[k] for k in RAW_KEYS}
        status, reason, infra_reason = classify_harness(raw, where)
        iid = row["instance_id"]
        if not isinstance(iid, str) or not iid:
            raise ReplicasError(f"{where}: 'instance_id' invalido.")
        patch_sha: str | None = None
        if raw["agent_patch_size"] > 0:
            # el arnes nombra el parche con el id y «/» sustituido por «__» (HARNESS § 9.2)
            patch_file = (patches_dir / f"{iid.replace('/', '__')}.patch") if patches_dir else None
            if patch_file is None or not patch_file.is_file():
                raise ReplicasError(
                    f"{where}: el parche de {iid!r} tiene tamano {raw['agent_patch_size']} pero no se "
                    f"encontro {patch_file or '--patches'}; no se puede calcular su hash."
                )
            patch_sha = sha256_file(patch_file)
        recibo: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "instance_id": iid,
            "repo": row["repo"],
            "condition": condition,
            "replica": replica,
            "status": status,
            "failure_reason": reason,
            "infra_reason": infra_reason,
            "resolved": status == ST_RESOLVED,
            "tool_calls": row["tool_calls"],
            "duration_seconds": row["duration_seconds"],
            "patch_sha256": patch_sha,
            "submission_sha256": submission_sha256,
            "tasks_sha256": tasks_sha256,
            "subset_sha256": subset_sha256,
            "harness_version": harness_version,
            "sandbox_image": sandbox_image,
            "converted_utc": converted_utc,
            "harness_raw": raw,
        }
        if run_utc is not None:
            recibo["run_utc"] = run_utc
        parse_receipt(recibo, where)  # el conversor nunca emite un recibo que el analisis rechace
        recibos.append(recibo)
    if not recibos:
        raise ReplicasError(f"{task_results} no tiene filas.")
    ids = [r["instance_id"] for r in recibos]
    repetidos = sorted({i for i in ids if ids.count(i) > 1})
    if repetidos:
        raise ReplicasError(f"{task_results.name}: tareas repetidas: {repetidos}")
    fuera = sorted(set(ids) - permitidos)
    if fuera:
        raise ReplicasError(f"{task_results.name}: tareas fuera del subconjunto pre-registrado: {fuera}")
    return sorted(recibos, key=lambda r: r["instance_id"])


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _write_all(items: Sequence[tuple[Path, str]]) -> None:
    """Escribe todos los archivos a temporales unicos del mismo directorio y los renombra al final.

    Si algo falla no queda ningun archivo nuevo (ni temporales). Un temporal tiene nombre unico
    (``tempfile``): nunca pisa un archivo ajeno.
    """
    temps: list[tuple[Path, Path]] = []
    done: list[Path] = []
    try:
        for path, text in items:
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
            temps.append((Path(name), path))
            with os.fdopen(fd, "wb") as f:
                f.write(text.encode("utf-8"))
        for tmp, path in temps:
            os.replace(tmp, path)
            done.append(path)
    except BaseException:
        for path in done:
            path.unlink(missing_ok=True)
        for tmp, _ in temps:
            tmp.unlink(missing_ok=True)
        raise


def _is_own_report(path: Path, kind: str) -> bool:
    """¿Es ``path`` un reporte propio? JSON con la version del reporte; Markdown con su encabezado."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    if kind == "md":
        return text.startswith(REPORT_MD_HEADER)
    try:
        data = loads_strict(text)
    except ValueError:
        return False
    version = data.get("version_reporte") if isinstance(data, dict) else None
    return isinstance(version, str) and version.startswith(REPORT_VERSION.split("/")[0] + "/")


def _check_outputs(args: argparse.Namespace) -> list[tuple[Path, str]]:
    """Valida las rutas de salida sin tocar nada; devuelve las que existen y son reportes propios.

    Rechaza (salida 2) una ruta que coincida con una entrada (subconjunto, recibos, directorios de
    recibos o de envio), que caiga dentro de un directorio de entrada, que sea un directorio, que
    sea la misma para JSON y Markdown, o que exista y no sea un reporte propio.
    """
    outs = [(p, k) for p, k in ((args.salida_json, "json"), (args.salida_md, "md")) if p]
    resueltas = [p.resolve() for p, _ in outs]
    if len(set(resueltas)) < len(resueltas):
        raise ReplicasError("--salida-json y --salida-md son la misma ruta.")
    entradas: set[Path] = {args.subconjunto.resolve()}
    dirs: list[Path] = []
    for p in args.recibos:
        entradas.add(p.resolve())
        if p.is_dir():
            dirs.append(p.resolve())
            entradas.update(q.resolve() for q in p.glob("*.jsonl"))
    if args.envio:
        dirs.append(args.envio.resolve())
        entradas.add(args.envio.resolve())
    previos: list[tuple[Path, str]] = []
    for (p, kind), r in zip(outs, resueltas, strict=True):
        if r in entradas or any(d in r.parents for d in dirs):
            raise ReplicasError(
                f"La ruta de salida {p} coincide con una entrada o esta dentro de una: no se toca."
            )
        if r.is_dir():
            raise ReplicasError(f"La ruta de salida {p} es un directorio.")
        if r.exists():
            if not _is_own_report(r, kind):
                raise ReplicasError(f"{p} ya existe y no es un reporte de este comando: no se borra.")
            previos.append((p, kind))
    return previos


def _cmd_analizar(args: argparse.Namespace) -> int:
    salidas: list[Path] = [p for p in (args.salida_json, args.salida_md) if p]
    if not 0 < args.alfa < 1:
        raise ReplicasError("--alfa debe estar entre 0 y 1 (exclusivo).")
    previos = _check_outputs(args)
    for p, _ in previos:  # una salida 2 no deja el reporte de una corrida anterior
        try:
            p.unlink()
        except OSError as exc:
            raise ReplicasError(
                f"No se pudo borrar el reporte anterior {p} ({exc}); sigue en disco y es obsoleto: "
                "no lo uses."
            ) from exc
    receipts = load_receipts(args.recibos)
    subset = load_subset(args.subconjunto)
    tasks_ref = resolve_tasks_sha(subset, args.tasks_sha256)
    problems = check_integrity(receipts, subset, tasks_ref)
    archivos: list[tuple[str, str]] | None = None
    if args.envio:
        archivos = submission_files(args.envio)
        calculado = hashlib.sha256("".join(f"{r}\t{h}\n" for r, h in archivos).encode("utf-8")).hexdigest()
        if {r.submission_sha256 for r in receipts} - {calculado}:
            problems.append(
                f"El hash del envio en los recibos no es el del directorio {args.envio} ({calculado})."
            )
    if problems:
        raise ReplicasError("Integridad de los recibos:\n- " + "\n- ".join(problems))
    report = analyze(receipts, subset, args.alfa, archivos)
    md = render_markdown(report)
    escribir: list[tuple[Path, str]] = []
    if args.salida_json:
        escribir.append((args.salida_json, render_json(report)))
    if args.salida_md:
        escribir.append((args.salida_md, md))
    _write_all(escribir)  # ambos o ninguno
    if not salidas:
        sys.stdout.write(md)
    if not report["completo"]:
        partes = []
        if report["faltantes"]:
            partes.append(
                "faltan recibos: "
                + ", ".join(f"{x['instance_id']}{x['replicas']}" for x in report["faltantes"])
            )
        if report["infra_afectadas"]:
            partes.append(
                "errores de infraestructura (volver a correr): " + ", ".join(report["infra_afectadas"])
            )
        print("INCOMPLETO: " + "; ".join(partes), file=sys.stderr)
        return EXIT_INCOMPLETE
    return EXIT_OK


def _cmd_convertir(args: argparse.Namespace) -> int:
    if args.salida.exists():
        raise ReplicasError(
            f"{args.salida} ya existe: un recibo no se sobrescribe (campana nueva, ruta nueva)."
        )
    subset = load_subset(args.subconjunto)
    created = args.convertido_utc or datetime.now(UTC).strftime(UTC_FORMAT)
    recibos = convert_harness_results(
        args.task_results,
        patches_dir=args.patches,
        subset_ids=subset.ids,
        replica=args.replica,
        condition=args.condicion,
        submission_sha256=sha256_directory(args.envio),
        tasks_sha256=sha256_file(args.tasks),
        subset_sha256=subset.sha256_file,
        harness_version=args.version_arnes,
        sandbox_image=args.imagen_sandbox,
        converted_utc=created,
        run_utc=args.run_utc,
    )
    text = "".join(json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n" for r in recibos)
    _write_all([(args.salida, text)])
    print(f"{len(recibos)} recibos escritos en {args.salida}")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada: ``analizar`` o ``convertir``; los errores de entrada salen con 2."""
    parser = argparse.ArgumentParser(description="Analisis de replicas de la linea base A (issue #103).")
    sub = parser.add_subparsers(dest="comando", required=True)

    a = sub.add_parser("analizar", help="Analiza recibos de replicas.")
    a.add_argument("--recibos", type=Path, nargs="+", required=True, help="Archivos .jsonl o directorios.")
    a.add_argument(
        "--subconjunto", type=Path, required=True, help="Salida de kaggle_split.py (lista 'test')."
    )
    a.add_argument(
        "--tasks-sha256", default=None, help="SHA-256 de tasks.jsonl si el subconjunto no lo declara."
    )
    a.add_argument(
        "--envio", type=Path, default=None, help="Directorio del kit: recalcula su hash y lista archivos."
    )
    a.add_argument("--alfa", type=float, default=DEFAULT_ALPHA, help="Nivel de las pruebas e intervalos.")
    a.add_argument("--salida-json", type=Path, default=None, help="Donde escribir el JSON agregado.")
    a.add_argument("--salida-md", type=Path, default=None, help="Donde escribir la tabla Markdown.")
    a.set_defaults(func=_cmd_analizar)

    c = sub.add_parser("convertir", help="Convierte task_results.jsonl del arnes en recibos.")
    c.add_argument("--task-results", type=Path, required=True)
    c.add_argument("--patches", type=Path, default=None, help="Directorio con <instance_id>.patch.")
    c.add_argument("--replica", type=int, required=True)
    c.add_argument("--condicion", required=True)
    c.add_argument("--envio", type=Path, required=True, help="Directorio de la condicion (se hashea).")
    c.add_argument("--tasks", type=Path, required=True, help="tasks.jsonl (solo se hashea).")
    c.add_argument("--subconjunto", type=Path, required=True)
    c.add_argument("--version-arnes", required=True)
    c.add_argument("--imagen-sandbox", required=True)
    c.add_argument(
        "--convertido-utc", default=None, help="YYYY-MM-DDTHH:MM:SSZ de la conversion (por defecto, ahora)."
    )
    c.add_argument("--run-utc", default=None, help="YYYY-MM-DDTHH:MM:SSZ de la corrida, si se conoce.")
    c.add_argument("--salida", type=Path, required=True)
    c.set_defaults(func=_cmd_convertir)

    args = parser.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):  # mensajes con acentos o flechas no deben romper en Windows
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")
    try:
        return int(args.func(args))
    except (ReplicasError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_INVALID
    except Exception as exc:  # error del propio script: nunca con el codigo de «incompleto»
        print(f"ERROR INESPERADO ({type(exc).__name__}): {exc}", file=sys.stderr)
        return EXIT_UNEXPECTED


if __name__ == "__main__":
    sys.exit(main())
