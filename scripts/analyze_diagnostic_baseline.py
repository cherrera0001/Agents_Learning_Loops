"""Análisis pre-registrado de la línea base de diagnóstico público (#58).

Implementa ``docs/preregistration/diagnostic-baseline.md``, sección 7 (commit ``1ed70e0``): métricas,
denominadores y criterio de lectura fijados **antes** de la campaña. Lee los recibos directamente, sin
importar el paquete ``experiments``. La integridad (la decisión se repite desde el recibo, mismo
diagnóstico en A, B y C, una sola política) la verifica antes ``python -m experiments evaluate``.

Uso::

    python -m scripts.analyze_diagnostic_baseline --evidence evidence/diagnostic-baseline-v1
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

Receipt = dict[str, Any]
A, B, C = "NO_MEMORY", "TEXT_HISTORY", "ASSOCIATIVE_MEMORY"
AGENT = "bounded-ast-repair-v1+diagnostic-v1"
POLICY = "diagnostic-baseline/v1"
# Margen adoptado localmente de H4 por continuidad: criterio de lectura exploratorio, no significancia.
MARGIN = 3
PRIMARY_KINDS = ("original", "misleading")


def load(directory: Path) -> list[Receipt]:
    return [json.loads(p.read_text("utf-8")) for p in sorted(directory.glob("RUN-*.json"))]


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


def one_replicate(runs: list[Receipt]) -> tuple[list[Receipt], bool]:
    """Réplica 1 = la primera por ``batch_id``; las demás deben ser idénticas en comportamiento."""
    groups: dict[tuple[str, str, int], list[Receipt]] = defaultdict(list)
    for r in runs:
        groups[(r["memory_mode"], r["task"]["id"], r["seed"])].append(r)
    chosen, consistent = [], True
    for rs in groups.values():
        rs.sort(key=lambda r: r["batch_id"])
        chosen.append(rs[0])
        consistent &= all(behaviour(r) == behaviour(rs[0]) for r in rs[1:])
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


def analyze(runs: list[Receipt], private: dict[str, dict[str, Any]]) -> dict[str, Any]:
    tasks = [r for r in runs if r["kind"] == "task_run"]
    policies = {(r["agent"], r["decision"].get("policy")) for r in tasks}
    if policies != {(AGENT, POLICY)}:
        raise ValueError(
            f"solo recibos de la línea base de diagnóstico; encontrados: {sorted(map(str, policies))}"
        )
    selected, consistent = one_replicate(tasks)
    cells: dict[tuple[str, str], list[Receipt]] = defaultdict(list)
    for r in selected:
        cells[(kind_of(r, private), r["memory_mode"])].append(r)
    out: dict[str, Any] = {
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
    report = analyze(load(args.root / args.evidence), annotations(args.root))
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
