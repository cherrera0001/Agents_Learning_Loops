"""Análisis pre-registrado de la línea base de diagnóstico público (#58).

Implementa ``docs/preregistration/diagnostic-baseline.md``, secciones 6 y 7 (commit ``1ed70e0``):
campaña, métricas, denominadores y criterio de lectura fijados **antes** de la campaña. Lee los recibos
directamente, sin importar el paquete ``experiments``: verifica el sello SHA-256 de cada recibo con la
biblioteca estándar, cita ``generated_from`` y valida la forma exacta de la campaña declarada antes de
calcular cualquier veredicto. ``python -m experiments evaluate`` verifica además la repetición de cada
decisión, el mismo diagnóstico en A, B y C, las anotaciones privadas y una sola política.

Uso::

    python -m scripts.analyze_diagnostic_baseline --evidence evidence/diagnostic-baseline-v1
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

Receipt = dict[str, Any]
A, B, C = "NO_MEMORY", "TEXT_HISTORY", "ASSOCIATIVE_MEMORY"
MODES = (A, B, C)
AGENT = "bounded-ast-repair-v1+diagnostic-v1"
POLICY = "diagnostic-baseline/v1"
# Campaña declarada (experiments.benchmark.DIAGNOSTIC_CAMPAIGN); un test comprueba que coinciden.
TASKS = tuple(f"EXP-{i:02d}" for i in range(1, 10))
SEEDS = (1, 4, 5, 6, 7, 9)
REPLICATES = 2
KIND_SIZES = {"train": 3, "original": 3, "misleading": 3}
RECEIPT_SCHEMA = "software-learning-receipt/v2"
NORMALIZATION = "lf/v1"
# Margen adoptado localmente de H4 por continuidad: criterio de lectura exploratorio, no significancia.
MARGIN = 3
PRIMARY_KINDS = ("original", "misleading")


def canonical(value: Any) -> bytes:
    """El mismo JSON canónico que sella los recibos (``experiments.evidence.canonical``)."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def load(directory: Path) -> tuple[list[Receipt], dict[str, str]]:
    """Recibos con su sello verificado, y ``generated_from`` (archivo → sello) para trazabilidad."""
    receipts, generated_from = [], {}
    for path in sorted(directory.glob("RUN-*.json")):
        record = json.loads(path.read_text("utf-8"))
        checksum = record.pop("receipt_sha256", None)
        if checksum is None or hashlib.sha256(canonical(record)).hexdigest() != checksum:
            raise ValueError(f"sello del recibo ausente o que no coincide: {path.name}")
        if (record.get("schema_id"), record.get("source_hash_normalization")) != (
            RECEIPT_SCHEMA,
            NORMALIZATION,
        ):
            raise ValueError(f"esquema o normalización no previstos en {path.name}")
        if path.stem != record.get("run_id"):
            raise ValueError(f"el nombre del archivo no es el run_id sellado: {path.name}")
        record["receipt_sha256"] = checksum
        receipts.append(record)
        generated_from[path.name] = checksum
    return receipts, generated_from


def annotations(root: Path) -> dict[str, dict[str, Any]]:
    private = json.loads((root / "benchmark/private/tasks.json").read_text("utf-8"))
    extra = root / "benchmark/private/tasks_misleading.json"
    if extra.exists():
        private.update(json.loads(extra.read_text("utf-8")))
    return private


def kind_of(r: Receipt, private: dict[str, dict[str, Any]]) -> str:
    if r["split"] == "train":
        return "train"
    return "misleading" if private[r["task"]["id"]].get("decoy_family") else "original"


def validate_campaign(receipts: list[Receipt], private: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Validación cerrada de la campaña declarada (pre-registro, sección 6), antes de cualquier veredicto.

    Exige exactamente 2 lotes (réplicas), cada uno con las 6 semillas × 9 tareas × 3 condiciones, sin
    duplicados; solo el agente y la política de diagnóstico; ninguna ejecución con error; particiones de
    3 tareas; lecciones solo de entrenamiento anterior del mismo lote, semilla y condición; y un
    ``memory_update`` por cada ejecución de entrenamiento de B y C. Cualquier desvío es un ``ValueError``.
    """
    runs = [r for r in receipts if r["kind"] == "task_run"]
    updates = [r for r in receipts if r["kind"] == "memory_update"]
    if len(runs) + len(updates) != len(receipts):
        raise ValueError("recibos de un tipo no previsto")
    for r in runs:
        if (r["agent"], r["decision"].get("policy")) != (AGENT, POLICY):
            raise ValueError(f"solo recibos de la línea base de diagnóstico; {r['run_id']} no lo es")
        if r["result"] not in ("PASS", "FAIL"):
            raise ValueError(f"ejecución con resultado {r['result']}: {r['run_id']}")
    keys = [(r["batch_id"], r["seed"], r["task"]["id"], r["memory_mode"]) for r in runs]
    if len(set(keys)) != len(keys):
        raise ValueError("celda duplicada (lote, semilla, tarea, condición)")
    batches = sorted({batch for batch, *_ in keys})
    if len(batches) != REPLICATES:
        raise ValueError(f"se esperaban {REPLICATES} réplicas (lotes) completas; hay {len(batches)}")
    expected = set(itertools.product(SEEDS, TASKS, MODES))
    for batch in batches:
        found = {(seed, task, mode) for b, seed, task, mode in keys if b == batch}
        if found != expected:
            raise ValueError(
                f"el lote {batch} no es la campaña declarada: faltan {len(expected - found)} celdas "
                f"y sobran {len(found - expected)}"
            )
    splits: dict[str, set[str]] = defaultdict(set)
    for r in runs:
        splits[r["task"]["id"]].add(r["split"])
    if any(len(s) != 1 for s in splits.values()):
        raise ValueError("una tarea tiene particiones distintas entre ejecuciones")
    kinds = [kind_of({"split": next(iter(splits[t])), "task": {"id": t}}, private) for t in TASKS]
    if (
        Counter(kinds) != Counter(KIND_SIZES)
        or kinds[: KIND_SIZES["train"]] != ["train"] * KIND_SIZES["train"]
    ):
        raise ValueError("las particiones no son 3 de entrenamiento (primero), 3 originales y 3 engañosas")
    by_id = {r["run_id"]: r for r in runs}
    order = {task: i for i, task in enumerate(TASKS)}
    for r in runs:
        lessons = (r["memory_input"] or {}).get("lessons", [])
        exposed = {m["id"] for m in r["retrieval"]["memories"]}
        if r["memory_mode"] == A and (lessons or exposed):
            raise ValueError(f"NO_MEMORY con memoria: {r['run_id']}")
        for lesson in lessons:
            prior = by_id.get(lesson["run_id"])
            if (
                prior is None
                or prior["split"] != "train"
                or prior["result"] != "PASS"
                or any(prior[k] != r[k] for k in ("batch_id", "seed", "memory_mode"))
                or order[prior["task"]["id"]] >= order[r["task"]["id"]]
                or prior["receipt_sha256"] != lesson["receipt_sha256"]
            ):
                raise ValueError(f"lección fuera de procedencia o de entrenamiento futuro en {r['run_id']}")
        if (
            not exposed <= {lesson["id"] for lesson in lessons}
            or not set(r["decision"]["memory_ids"]) <= exposed
        ):
            raise ValueError(f"recuperación fuera de la memoria elegible en {r['run_id']}")
    trained = sorted(r["run_id"] + ".json" for r in runs if r["split"] == "train" and r["memory_mode"] != A)
    if sorted(u["source_receipt"] for u in updates) != trained:
        raise ValueError("los memory_update no corresponden uno a uno con el entrenamiento de B y C")
    return {
        "task_runs": len(runs),
        "memory_updates": len(updates),
        "batches": batches,
        "primary_batch": batches[0],
    }


def cited_tasks(r: Receipt) -> list[str]:
    source = {m["id"]: m["task"] for m in r["retrieval"]["memories"]}
    return [source[i] for i in r["decision"]["memory_ids"]]


def behaviour(r: Receipt) -> str:
    """Comportamiento sin UUID ni tiempos: lo que debe coincidir entre réplicas."""
    d = r["decision"]
    return json.dumps(
        [
            d["plan"],
            d["diagnostic"],
            d["memory_effect"],
            r["outcome"],
            [m["task"] for m in r["retrieval"]["memories"]],
            cited_tasks(r),
        ],
        sort_keys=True,
    )


def replicates(runs: list[Receipt], batches: list[str]) -> tuple[list[Receipt], bool]:
    """Réplica 1 = el primer lote por ``batch_id``, el mismo para toda semilla y celda (los pares nunca
    mezclan lotes). La otra réplica debe ser idéntica en comportamiento celda a celda."""
    cells = {(r["batch_id"], r["seed"], r["task"]["id"], r["memory_mode"]): r for r in runs}
    primary, other = batches
    chosen = [r for r in runs if r["batch_id"] == primary]
    consistent = all(
        behaviour(r) == behaviour(cells[(other, r["seed"], r["task"]["id"], r["memory_mode"])])
        for r in chosen
    )
    return chosen, consistent


def ratio(num: int, den: int) -> dict[str, Any]:
    return {"value": None if den == 0 else num / den, "numerator": num, "denominator": den}


def first_action_forced(x: Receipt, y: Receipt) -> bool:
    """El primer intento coincide necesariamente: D decisivo o ninguna memoria propone."""
    decisive = x["decision"]["diagnostic"]["status"] == "decisive"
    return decisive or (x["decision"]["memory_proposal"] is None and y["decision"]["memory_proposal"] is None)


def classify(x: Receipt, y: Receipt) -> str:
    """Positivo, negativo o nulo de ``x`` frente a ``y``: primero éxito, después intentos (solo si ambos
    tuvieron éxito). Un nulo es «por construcción» si los planes son idénticos, o si el primer intento
    coincide necesariamente y tuvo éxito (pre-registro, sección 7)."""
    xs, ys = x["outcome"]["success"], y["outcome"]["success"]
    if xs != ys:
        return "positive" if xs else "negative"
    if xs and x["iterations"] != y["iterations"]:
        return "positive" if x["iterations"] < y["iterations"] else "negative"
    if x["decision"]["plan"] == y["decision"]["plan"] or (
        first_action_forced(x, y) and x["outcome"]["first_attempt_success"]
    ):
        return "null_by_construction"
    return "null_observed"


def condition_summary(rs: list[Receipt]) -> dict[str, Any]:
    n = len(rs)
    return {
        "runs": n,
        "TaskSuccess": ratio(sum(r["outcome"]["success"] for r in rs), n),
        "FirstAttemptSuccess": ratio(sum(r["outcome"]["first_attempt_success"] for r in rs), n),
        "IterationsPerTask": ratio(sum(r["iterations"] for r in rs), n),
        "cost": {
            "tests_executed_including_reproduction": sum(len(r["tests"]) for r in rs),
            "repair_attempts": sum(r["iterations"] for r in rs),
            "duration_ms_descriptive_only": round(sum(r["duration_ms"] for r in rs), 3),
        },
        "lessons": {
            "exposed": sum(len(r["retrieval"]["memories"]) for r in rs),
            "cited": sum(len(r["decision"]["memory_ids"]) for r in rs),
            "memory_effect": dict(sorted(Counter(r["decision"]["memory_effect"] for r in rs).items())),
        },
        "diagnostic_status": dict(sorted(Counter(r["decision"]["diagnostic"]["status"] for r in rs).items())),
    }


def compare(treatment: list[Receipt], baseline: dict[tuple[str, int], Receipt], label: str) -> dict[str, Any]:
    """Pares (semilla, tarea) de ``treatment`` frente a ``baseline``, con numeradores exactos."""
    pairs = []
    for x in treatment:
        key = (x["task"]["id"], x["seed"])
        if key not in baseline:
            raise ValueError(f"par sin {label} para {key}")
        pairs.append((x, baseline[key]))
    n = len(pairs)
    fx = sum(x["outcome"]["first_attempt_success"] for x, _ in pairs)
    fy = sum(y["outcome"]["first_attempt_success"] for _, y in pairs)
    ix = sum(x["iterations"] for x, _ in pairs)
    iy = sum(y["iterations"] for _, y in pairs)
    return {
        "pairs": n,
        "FirstAttemptSuccess": ratio(fx, n),
        f"FirstAttemptSuccess_{label}": ratio(fy, n),
        "FirstAttemptDifference": {"runs": fx - fy, "rate": None if n == 0 else (fx - fy) / n},
        "IterationsDifference": {"total": ix - iy, "per_task": None if n == 0 else (ix - iy) / n},
        "pair_classes": dict(sorted(Counter(classify(x, y) for x, y in pairs).items())),
        "headroom": {
            "first_action_forced": sum(first_action_forced(x, y) for x, y in pairs),
            "plan_identical": sum(x["decision"]["plan"] == y["decision"]["plan"] for x, y in pairs),
            "diagnostic_status": dict(
                sorted(Counter(x["decision"]["diagnostic"]["status"] for x, _ in pairs).items())
            ),
            "memory_effect": dict(sorted(Counter(x["decision"]["memory_effect"] for x, _ in pairs).items())),
        },
    }


def verdict(comparison: dict[str, Any], consistent: bool) -> str:
    if not consistent or comparison["pairs"] == 0:
        return "inválido"
    difference = comparison["FirstAttemptDifference"]["runs"]
    if difference >= MARGIN:
        return "aporta"
    if difference <= -MARGIN:
        return "perjudica"
    return "sin diferencia"


def analyze(receipts: list[Receipt], private: dict[str, dict[str, Any]]) -> dict[str, Any]:
    campaign = validate_campaign(receipts, private)  # antes de cualquier veredicto
    runs = [r for r in receipts if r["kind"] == "task_run"]
    selected, consistent = replicates(runs, campaign["batches"])
    cells: dict[tuple[str, str], list[Receipt]] = defaultdict(list)
    for r in selected:
        cells[(kind_of(r, private), r["memory_mode"])].append(r)
    out: dict[str, Any] = {
        "campaign": campaign,
        "replicates_consistent": consistent,
        "margin_runs": MARGIN,
        "kinds": {},
        "verdicts": {},
    }
    for kind in (*PRIMARY_KINDS, "train"):
        base = {(r["task"]["id"], r["seed"]): r for r in cells[(kind, A)]}
        text = {(r["task"]["id"], r["seed"]): r for r in cells[(kind, B)]}
        comparisons = {mode: compare(cells[(kind, mode)], base, A) for mode in (B, C)}
        comparisons["ASSOCIATIVE_MEMORY_vs_TEXT_HISTORY"] = compare(cells[(kind, C)], text, B)
        out["kinds"][kind] = {
            "conditions": {mode: condition_summary(cells[(kind, mode)]) for mode in (A, B, C)},
            "comparisons": comparisons,
        }
        if kind in PRIMARY_KINDS:
            for mode in (B, C):
                out["verdicts"][f"{kind}/{mode}"] = verdict(comparisons[mode], consistent)
    return out


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--evidence", required=True)
    args = parser.parse_args()
    receipts, generated_from = load(args.root / args.evidence)
    report = analyze(receipts, annotations(args.root))
    report["generated_from"] = generated_from
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
