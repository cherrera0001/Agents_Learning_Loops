"""Analisis de replicas de la linea base A (issue #103, experimento Kaggle Gemma 4).

Lee recibos por tarea y replica, comprueba su integridad y reporta la variacion de la
condicion A contra si misma: tasa por replica, tareas que cambian de resultado, acuerdo por
pares, desglose por repositorio y el margen que el ruido observado impone a una comparacion
entre dos condiciones. Solo biblioteca estandar.

Dos subcomandos:

* ``convertir``: pasa el ``task_results.jsonl`` del arnes ``swegemma eval`` a recibos.
* ``analizar``: lee los recibos y escribe el reporte (JSON agregado + tabla en Markdown).

Codigos de salida de ``analizar``:

* 0  analisis completo.
* 1  el analisis se escribio, pero faltan tareas del subconjunto en alguna replica
  (se listan como faltantes; el reporte lo declara con ``completo: false``).
* 2  no se pudo analizar: recibo ilegible o invalido, hashes que no coinciden, tareas
  fuera del subconjunto, duplicados, menos de 2 replicas, etc. No se escribe reporte.
  «No pude leer» nunca equivale a «sin hallazgos».

Frontera de fuga: el analisis no lee parches ni ``tasks.jsonl``; solo el hash de ese archivo,
y del subconjunto (salida de ``kaggle_split.py``) lee la lista ``test``. Los recibos guardan
el hash del parche, nunca el parche; una clave desconocida en un recibo (por ejemplo
``patch`` o ``test_patch``) se rechaza.

El metodo estadistico y el formato de recibo estan descritos en
``experiments/gemma_developer_agent/docs/analisis_replicas.md``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from fractions import Fraction
from itertools import combinations
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "kaggle-replica-receipt/1"
REPORT_VERSION = "kaggle-replica-analysis/1"

ST_RESOLVED = "resolved"
ST_UNRESOLVED = "unresolved"
ST_TIMEOUT = "timeout"
ST_INFRA = "infra_error"
ST_EMPTY = "empty_patch"
STATUS_VALID = (ST_RESOLVED, ST_UNRESOLVED)
STATUS_ERROR = (ST_TIMEOUT, ST_INFRA, ST_EMPTY)
STATUS_ALL = STATUS_VALID + STATUS_ERROR
MISSING = "missing"

SHORT = {
    ST_RESOLVED: "R",
    ST_UNRESOLVED: "N",
    ST_TIMEOUT: "T",
    ST_INFRA: "I",
    ST_EMPTY: "V",
    MISSING: "-",
}

REQUIRED_KEYS = (
    "schema_version",
    "instance_id",
    "repo",
    "condition",
    "replica",
    "status",
    "resolved",
    "tool_calls",
    "duration_seconds",
    "patch_sha256",
    "submission_sha256",
    "tasks_sha256",
    "subset_sha256",
    "harness_version",
    "sandbox_image",
    "created_utc",
)
OPTIONAL_KEYS = ("llm_calls",)
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
DEFAULT_ALPHA = 0.05


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
    tool_calls: int
    duration_seconds: float
    patch_sha256: str | None
    submission_sha256: str
    tasks_sha256: str
    subset_sha256: str
    harness_version: str
    sandbox_image: str
    created_utc: str


# ---------------------------------------------------------------------------
# Hashes
# ---------------------------------------------------------------------------


def sha256_file(path: Path) -> str:
    """SHA-256 de un archivo."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def sha256_directory(path: Path) -> str:
    """SHA-256 de un directorio: hash de las lineas ``ruta_posix<TAB>sha256_archivo\\n`` ordenadas.

    Incluye todos los archivos regulares bajo ``path``; el nombre del directorio raiz no cuenta.
    """
    if not path.is_dir():
        raise ReplicasError(f"No es un directorio: {path}")
    lines = sorted(
        f"{p.relative_to(path).as_posix()}\t{sha256_file(p)}\n" for p in path.rglob("*") if p.is_file()
    )
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()


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
    if not isinstance(v, str) or not SHA_RE.match(v):
        raise ReplicasError(f"{where}: '{key}' debe ser un SHA-256 hexadecimal en minusculas.")
    return v


def parse_receipt(obj: object, where: str) -> Recibo:
    """Valida un objeto JSON como recibo; lanza ReplicasError con ``where`` si algo no cuadra."""
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
    resolved = obj["resolved"]
    if not isinstance(resolved, bool):
        raise ReplicasError(f"{where}: 'resolved' debe ser booleano.")
    if resolved != (status == ST_RESOLVED):
        raise ReplicasError(f"{where}: 'resolved'={resolved} contradice status={status!r}.")
    replica = obj["replica"]
    if not isinstance(replica, int) or isinstance(replica, bool) or replica < 1:
        raise ReplicasError(f"{where}: 'replica' debe ser un entero >= 1.")
    tool_calls = obj["tool_calls"]
    if not isinstance(tool_calls, int) or isinstance(tool_calls, bool) or tool_calls < 0:
        raise ReplicasError(f"{where}: 'tool_calls' debe ser un entero >= 0.")
    dur = obj["duration_seconds"]
    if isinstance(dur, bool) or not isinstance(dur, int | float) or not math.isfinite(dur) or dur < 0:
        raise ReplicasError(f"{where}: 'duration_seconds' debe ser un numero finito >= 0.")
    llm = obj.get("llm_calls")
    if llm is not None and (not isinstance(llm, int) or isinstance(llm, bool) or llm < 0):
        raise ReplicasError(f"{where}: 'llm_calls' debe ser un entero >= 0.")
    created = _text(obj, "created_utc", where)
    if not UTC_RE.match(created):
        raise ReplicasError(f"{where}: 'created_utc' debe ser YYYY-MM-DDTHH:MM:SSZ.")
    return Recibo(
        instance_id=_text(obj, "instance_id", where),
        repo=_text(obj, "repo", where),
        condition=_text(obj, "condition", where),
        replica=replica,
        status=status,
        tool_calls=tool_calls,
        duration_seconds=float(dur),
        patch_sha256=_sha(obj, "patch_sha256", where, nullable=True),
        submission_sha256=_sha(obj, "submission_sha256", where) or "",
        tasks_sha256=_sha(obj, "tasks_sha256", where) or "",
        subset_sha256=_sha(obj, "subset_sha256", where) or "",
        harness_version=_text(obj, "harness_version", where),
        sandbox_image=_text(obj, "sandbox_image", where),
        created_utc=created,
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
    """Lee y valida todos los recibos; cualquier linea ilegible o invalida detiene el analisis."""
    receipts: list[Recibo] = []
    for f in expand_receipt_paths(paths):
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise ReplicasError(f"No se pudo leer {f}: {exc}") from exc
        for numero, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            where = f"{f.name}:{numero}"
            try:
                obj = json.loads(line)
            except ValueError as exc:
                raise ReplicasError(f"{where}: no es JSON valido: {exc}") from exc
            receipts.append(parse_receipt(obj, where))
    return receipts


@dataclass(frozen=True)
class Subconjunto:
    """Subconjunto pre-registrado: ids de prueba y hash del archivo que lo fija."""

    ids: tuple[str, ...]
    sha256_file: str
    sha256_tasks: str | None


def load_subset(path: Path) -> Subconjunto:
    """Lee la salida de ``kaggle_split.py``: usa la lista ``test`` y el ``sha256_tasks`` declarado."""
    if not path.is_file():
        raise ReplicasError(f"Archivo de subconjunto no encontrado: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
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


def check_integrity(receipts: Sequence[Recibo], subset: Subconjunto) -> list[str]:
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
    if subset.sha256_tasks and {r.tasks_sha256 for r in receipts} - {subset.sha256_tasks}:
        problems.append(
            "El hash de tasks.jsonl en los recibos no es el que declara el subconjunto "
            f"({subset.sha256_tasks})."
        )
    en_subconjunto = set(subset.ids)
    fuera = sorted({r.instance_id for r in receipts} - en_subconjunto)
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
    if len({r.replica for r in receipts}) < 2:
        problems.append(
            "Se necesitan al menos 2 replicas distintas; hay " + str(len({r.replica for r in receipts})) + "."
        )
    return problems


# ---------------------------------------------------------------------------
# Estadistica exacta (stdlib)
# ---------------------------------------------------------------------------


def binom_cdf(k: int, n: int, p: float) -> float:
    """P(X <= k) para X ~ Binomial(n, p), con ``math.comb``."""
    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    return min(1.0, sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(k + 1)))


def clopper_pearson(x: int, n: int, alpha: float = DEFAULT_ALPHA) -> tuple[float, float]:
    """Intervalo exacto de Clopper-Pearson de nivel ``1 - alpha`` para x exitos en n (n >= 1).

    Se obtiene por biseccion sobre la funcion de distribucion binomial.
    """
    if n < 1 or not 0 <= x <= n:
        raise ValueError("Se requiere n >= 1 y 0 <= x <= n.")
    lo, hi = 0.0, 1.0
    if x > 0:
        a, b = 0.0, 1.0  # P(X >= x | p) = alpha/2, creciente en p
        for _ in range(200):
            m = (a + b) / 2
            if 1.0 - binom_cdf(x - 1, n, m) < alpha / 2:
                a = m
            else:
                b = m
        lo = (a + b) / 2
    if x < n:
        a, b = 0.0, 1.0  # P(X <= x | p) = alpha/2, decreciente en p
        for _ in range(200):
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
    return min(1.0, 2 * cola / 2**d)


def min_detectable_difference(d: int, n: int, alpha: float = DEFAULT_ALPHA) -> dict[str, Any]:
    """Menor diferencia de tasa que McNemar exacto declararia significativa con ``d`` pares discordantes.

    Entre ``d`` pares discordantes, una condicion gana ``g`` y la otra ``d - g`` (g > d - g).
    La diferencia de tasas es ``(2g - d) / n``; se busca el menor ``g`` con p <= alpha.
    ``alcanzable`` es falso si ni siquiera ``g = d`` alcanza ``alpha`` (muy pocos discordantes).
    """
    if n < 1 or d < 0 or d > n:
        raise ValueError("Se requiere n >= 1 y 0 <= d <= n.")
    umbral = Fraction(str(alpha))
    for g in range(d // 2 + 1, d + 1):
        c = d - g
        cola = sum(math.comb(d, i) for i in range(c + 1))
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


def analyze(receipts: Sequence[Recibo], subset: Subconjunto, alpha: float = DEFAULT_ALPHA) -> dict[str, Any]:
    """Calcula el reporte agregado. Supone recibos ya comprobados con ``check_integrity``."""
    replicas = sorted({r.replica for r in receipts})
    ids = list(subset.ids)
    by_key = {(r.instance_id, r.replica): r for r in receipts}
    repo_of = {r.instance_id: r.repo for r in receipts}

    def estado(iid: str, rep: int) -> str:
        r = by_key.get((iid, rep))
        return r.status if r else MISSING

    # Por replica
    por_replica: list[dict[str, Any]] = []
    for rep in replicas:
        cuentas = {s: 0 for s in (*STATUS_ALL, MISSING)}
        for iid in ids:
            cuentas[estado(iid, rep)] += 1
        validas = cuentas[ST_RESOLVED] + cuentas[ST_UNRESOLVED]
        por_replica.append(
            {
                "replica": rep,
                "tareas_subconjunto": len(ids),
                "resueltas": cuentas[ST_RESOLVED],
                "no_resueltas": cuentas[ST_UNRESOLVED],
                "validas": validas,
                "errores": {s: cuentas[s] for s in STATUS_ERROR},
                "errores_total": sum(cuentas[s] for s in STATUS_ERROR),
                "faltantes": cuentas[MISSING],
                "tasa_sobre_validas": _ratio(cuentas[ST_RESOLVED], validas),
                "tasa_sobre_subconjunto": _ratio(cuentas[ST_RESOLVED], len(ids)),
            }
        )

    # Por tarea
    tareas: list[dict[str, Any]] = []
    for iid in ids:
        res = {str(rep): estado(iid, rep) for rep in replicas}
        validos = [estado(iid, rep) for rep in replicas if estado(iid, rep) in STATUS_VALID]
        n_res = sum(1 for s in validos if s == ST_RESOLVED)
        cambia: bool | None = (0 < n_res < len(validos)) if len(validos) >= 2 else None
        tareas.append(
            {
                "instance_id": iid,
                "repo": repo_of.get(iid),
                "resultados": res,
                "validas": len(validos),
                "resueltas": n_res,
                "cambia": cambia,
            }
        )
    evaluables = [t for t in tareas if t["cambia"] is not None]
    cambian = [t for t in evaluables if t["cambia"]]

    # Pares de replicas
    pares: list[dict[str, Any]] = []
    for ra, rb in combinations(replicas, 2):
        a = b = c = d = 0
        for iid in ids:
            sa, sb = estado(iid, ra), estado(iid, rb)
            if sa not in STATUS_VALID or sb not in STATUS_VALID:
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
        if n:
            lo, hi = clopper_pearson(disc, n, alpha)
            ic: dict[str, float] | None = {"inferior": round(lo, 6), "superior": round(hi, 6)}
        else:
            ic = None
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

    # Desglose por repositorio
    por_repo: list[dict[str, Any]] = []
    for repo in sorted({str(t["repo"]) if t["repo"] is not None else "(sin recibos)" for t in tareas}):
        ts = [t for t in tareas if (t["repo"] if t["repo"] is not None else "(sin recibos)") == repo]
        fila_reps = []
        for rep in replicas:
            ests = [estado(t["instance_id"], rep) for t in ts]
            v = sum(1 for e in ests if e in STATUS_VALID)
            fila_reps.append(
                {
                    "replica": rep,
                    "resueltas": sum(1 for e in ests if e == ST_RESOLVED),
                    "validas": v,
                    "errores": sum(1 for e in ests if e in STATUS_ERROR),
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
    errores = [
        {"instance_id": iid, "replica": rep, "status": estado(iid, rep)}
        for iid in ids
        for rep in replicas
        if estado(iid, rep) in STATUS_ERROR
    ]
    validos_tasa = [p["tasa_sobre_validas"] for p in por_replica if p["tasa_sobre_validas"] is not None]
    primero = receipts[0]

    return {
        "version_reporte": REPORT_VERSION,
        "completo": not faltantes,
        "entrada": {
            "condicion": primero.condition,
            "tasks_sha256": primero.tasks_sha256,
            "envio_sha256": primero.submission_sha256,
            "subconjunto_sha256": primero.subset_sha256,
            "version_arnes": primero.harness_version,
            "imagen_sandbox": primero.sandbox_image,
            "recibos": len(receipts),
            "replicas": replicas,
            "tareas_subconjunto": len(ids),
            "fecha_utc_primer_recibo": min(r.created_utc for r in receipts),
            "fecha_utc_ultimo_recibo": max(r.created_utc for r in receipts),
        },
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
        "errores_de_infraestructura": errores,
        "faltantes": faltantes,
        "margen": _margin(pares, validos_tasa, alpha),
    }


def _margin(pares: list[dict[str, Any]], tasas: list[float], alpha: float) -> dict[str, Any]:
    """Margen que impone el ruido A-contra-A; ver el documento de metodo para supuestos."""
    base: dict[str, Any] = {
        "alfa": alpha,
        "metodo": (
            "Par de replicas con mayor tasa de discordancia; intervalo exacto de Clopper-Pearson para esa "
            "tasa; diferencia minima de tasa que una prueba de McNemar exacta bilateral declararia "
            "significativa si dos condiciones, una corrida cada una sobre las mismas tareas, produjeran "
            "ese numero de pares discordantes."
        ),
        "diferencia_observada_entre_replicas": (
            round(max(tasas) - min(tasas), 6) if len(tasas) >= 2 else None
        ),
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
    d_hi = min(n, math.ceil(hi * n - 1e-9))
    return {
        **base,
        "calculable": True,
        "par_base": peor["replicas"],
        "comparables": n,
        "discordantes_observados": d,
        "limite_superior_discordancia": round(hi, 6),
        "con_discordancia_observada": min_detectable_difference(d, n, alpha),
        "con_limite_superior": min_detectable_difference(d_hi, n, alpha),
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
    out: list[str] = ["# Analisis de replicas de la linea base", ""]
    if not report["completo"]:
        out += ["**INCOMPLETO: faltan recibos (ver «Faltantes»).**", ""]
    out += [
        f"- Condicion: `{e['condicion']}`; replicas: {e['replicas']}; recibos: {e['recibos']}; "
        f"tareas del subconjunto: {e['tareas_subconjunto']}",
        f"- `tasks.jsonl` sha256: `{e['tasks_sha256']}`",
        f"- Envio sha256: `{e['envio_sha256']}`",
        f"- Subconjunto sha256: `{e['subconjunto_sha256']}`",
        f"- Arnes: `{e['version_arnes']}`; imagen: `{e['imagen_sandbox']}`",
        f"- Recibos del {e['fecha_utc_primer_recibo']} al {e['fecha_utc_ultimo_recibo']}",
        "",
        "## Tasa de resolucion por replica",
        "",
        "| Replica | Resueltas | Validas | Tasa sobre validas | Tasa sobre subconjunto "
        "| Errores | Faltantes |",
        "|---|---|---|---|---|---|---|",
    ]
    for p in report["por_replica"]:
        out.append(
            f"| {p['replica']} | {p['resueltas']}/{p['validas']} | {p['validas']} | "
            f"{_f(p['tasa_sobre_validas'])} | {p['resueltas']}/{p['tareas_subconjunto']} = "
            f"{_f(p['tasa_sobre_subconjunto'])} | {p['errores_total']} | {p['faltantes']} |"
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
        out.append("")
        out.append("Cambian: " + ", ".join(f"`{t}`" for t in cd["tareas"]))
    if cd["no_evaluables"]:
        out.append("")
        out.append("No evaluables: " + ", ".join(f"`{t}`" for t in cd["no_evaluables"]))
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
    reps = e["replicas"]
    out += [
        "",
        "## Resultado por tarea",
        "",
        "R = resuelta, N = no resuelta, T = timeout, I = error de infraestructura, V = parche vacio, "
        "- = sin recibo.",
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
    out += ["", "## Errores (no cuentan como «no resuelta»)", ""]
    if report["errores_de_infraestructura"]:
        out += ["| Tarea | Replica | Estado |", "|---|---|---|"]
        out += [
            f"| `{x['instance_id']}` | {x['replica']} | {x['status']} |"
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
        "## Margen impuesto por el ruido A-contra-A",
        "",
        f"Alfa: {m['alfa']}. Metodo: {m['metodo']}",
        "",
    ]
    out.append(
        "- Diferencia observada entre la mayor y la menor tasa de replica: "
        f"{_f(m['diferencia_observada_entre_replicas'])}"
    )
    if not m["calculable"]:
        out.append(f"- No calculable: {m['motivo']}.")
    else:
        out.append(
            f"- Par base: {m['par_base']}; {m['discordantes_observados']}/{m['comparables']} discordantes; "
            f"limite superior de la discordancia: {_f(m['limite_superior_discordancia'])}."
        )
        for clave, etiqueta in (
            ("con_discordancia_observada", "Con la discordancia observada"),
            ("con_limite_superior", "Con el limite superior"),
        ):
            x = m[clave]
            if x["alcanzable"]:
                out.append(
                    f"- {etiqueta} ({x['discordantes']} discordantes): diferencia minima de "
                    f"{x['diferencia_pares']}/{m['comparables']} = {_f(x['diferencia_tasa'])} "
                    f"({x['ganadas_minimas']} pares ganados de {x['discordantes']})."
                )
            else:
                out.append(
                    f"- {etiqueta} ({x['discordantes']} discordantes): ninguna diferencia alcanza alfa "
                    "con tan pocos pares discordantes."
                )
    out.append("")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Conversor arnes -> recibos
# ---------------------------------------------------------------------------


def convert_harness_results(
    task_results: Path,
    *,
    patches_dir: Path | None,
    replica: int,
    condition: str,
    submission_sha256: str,
    tasks_sha256: str,
    subset_sha256: str,
    harness_version: str,
    sandbox_image: str,
    created_utc: str,
) -> list[dict[str, Any]]:
    """Convierte el ``task_results.jsonl`` de ``swegemma eval`` en recibos (diccionarios).

    Claves del arnes usadas: ``instance_id``, ``repo``, ``resolved``, ``agent_patch_size``,
    ``duration_seconds``, ``error``, ``tool_calls``, ``total_llm_calls``. El estado sale de
    ``error`` (si menciona «timeout» o «timed out»: ``timeout``; si no, ``infra_error``), luego de
    ``agent_patch_size == 0`` (``empty_patch``) y luego de ``resolved``. El hash del parche sale de
    ``<patches_dir>/<instance_id>.patch``; sin parche (tamano 0) queda ``null``.
    """
    try:
        lines = task_results.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise ReplicasError(f"No se pudo leer {task_results}: {exc}") from exc
    recibos: list[dict[str, Any]] = []
    for numero, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        where = f"{task_results.name}:{numero}"
        try:
            row = json.loads(line)
        except ValueError as exc:
            raise ReplicasError(f"{where}: no es JSON valido: {exc}") from exc
        if not isinstance(row, dict):
            raise ReplicasError(f"{where}: se esperaba un objeto JSON.")
        for k in ("instance_id", "repo", "resolved", "agent_patch_size", "duration_seconds", "tool_calls"):
            if k not in row:
                raise ReplicasError(f"{where}: falta la clave '{k}' del arnes.")
        iid = row["instance_id"]
        if not isinstance(iid, str) or not iid:
            raise ReplicasError(f"{where}: 'instance_id' invalido.")
        error = row.get("error")
        size = row["agent_patch_size"]
        if error:
            low = str(error).lower()
            status = ST_TIMEOUT if ("timeout" in low or "timed out" in low) else ST_INFRA
        elif size == 0:
            status = ST_EMPTY
        elif row["resolved"] is True:
            status = ST_RESOLVED
        else:
            status = ST_UNRESOLVED
        patch_sha: str | None = None
        if isinstance(size, int) and size > 0:
            patch_file = (patches_dir / f"{iid}.patch") if patches_dir else None
            if patch_file is None or not patch_file.is_file():
                raise ReplicasError(
                    f"{where}: el parche de {iid!r} tiene tamano {size} pero no se encontro "
                    f"{patch_file or '--patches-dir'}; no se puede calcular su hash."
                )
            patch_sha = sha256_file(patch_file)
        recibo: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "instance_id": iid,
            "repo": row["repo"],
            "condition": condition,
            "replica": replica,
            "status": status,
            "resolved": status == ST_RESOLVED,
            "tool_calls": row["tool_calls"],
            "duration_seconds": row["duration_seconds"],
            "patch_sha256": patch_sha,
            "submission_sha256": submission_sha256,
            "tasks_sha256": tasks_sha256,
            "subset_sha256": subset_sha256,
            "harness_version": harness_version,
            "sandbox_image": sandbox_image,
            "created_utc": created_utc,
        }
        if "total_llm_calls" in row:
            recibo["llm_calls"] = row["total_llm_calls"]
        parse_receipt(recibo, where)  # el conversor nunca emite un recibo que el analisis rechace
        recibos.append(recibo)
    if not recibos:
        raise ReplicasError(f"{task_results} no tiene filas.")
    return sorted(recibos, key=lambda r: r["instance_id"])


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def _cmd_analizar(args: argparse.Namespace) -> int:
    if not 0 < args.alfa < 1:
        raise ReplicasError("--alfa debe estar entre 0 y 1 (exclusivo).")
    receipts = load_receipts(args.recibos)
    subset = load_subset(args.subconjunto)
    problems = check_integrity(receipts, subset)
    if problems:
        raise ReplicasError("Integridad de los recibos:\n- " + "\n- ".join(problems))
    report = analyze(receipts, subset, args.alfa)
    if args.salida_json:
        _write(args.salida_json, render_json(report))
    md = render_markdown(report)
    if args.salida_md:
        _write(args.salida_md, md)
    if not args.salida_json and not args.salida_md:
        sys.stdout.write(md)
    if not report["completo"]:
        faltan = ", ".join(f"{x['instance_id']}{x['replicas']}" for x in report["faltantes"])
        print(f"INCOMPLETO: faltan recibos: {faltan}", file=sys.stderr)
        return 1
    return 0


def _cmd_convertir(args: argparse.Namespace) -> int:
    sub_sha = sha256_file(args.subconjunto)
    tasks_sha = sha256_file(args.tasks)
    envio = sha256_directory(args.envio)
    created = args.fecha_utc or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    recibos = convert_harness_results(
        args.task_results,
        patches_dir=args.patches,
        replica=args.replica,
        condition=args.condicion,
        submission_sha256=envio,
        tasks_sha256=tasks_sha,
        subset_sha256=sub_sha,
        harness_version=args.version_arnes,
        sandbox_image=args.imagen_sandbox,
        created_utc=created,
    )
    text = "".join(json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n" for r in recibos)
    _write(args.salida, text)
    print(f"{len(recibos)} recibos escritos en {args.salida}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada: ``analizar`` o ``convertir``; los errores de entrada salen con 2."""
    parser = argparse.ArgumentParser(description="Analisis de replicas de la linea base A (issue #103).")
    sub = parser.add_subparsers(dest="comando", required=True)

    a = sub.add_parser("analizar", help="Analiza recibos de replicas.")
    a.add_argument("--recibos", type=Path, nargs="+", required=True, help="Archivos .jsonl o directorios.")
    a.add_argument(
        "--subconjunto", type=Path, required=True, help="Salida de kaggle_split.py (lista 'test')."
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
    c.add_argument("--fecha-utc", default=None, help="YYYY-MM-DDTHH:MM:SSZ (por defecto, ahora).")
    c.add_argument("--salida", type=Path, required=True)
    c.set_defaults(func=_cmd_convertir)

    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (ReplicasError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
