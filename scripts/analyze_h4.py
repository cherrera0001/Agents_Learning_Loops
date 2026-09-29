"""Análisis confirmatorio de H4 (#46), tal como se pre-registró.

Implementa literalmente ``docs/preregistration/h4-associative-vs-history.md`` (commit ``6c9a1a3``):
métricas, denominadores y reglas de decisión fijados **antes** de conocer los resultados. Lee los
recibos directamente, sin importar el paquete ``experiments``.

Uso::

    python -m scripts.analyze_h4 --evidence evidence/reference-v2          # confirmatorio
    python -m scripts.analyze_h4 --evidence evidence/pilot/misleading-v1   # exploratorio
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

Receipt = dict[str, Any]
B, C, A = "TEXT_HISTORY", "ASSOCIATIVE_MEMORY", "NO_MEMORY"
DECISION_MARGIN = 3  # «al menos 3 ejecuciones / pares de diferencia» (pre-registro)


def load(directory: Path) -> list[Receipt]:
    return [json.loads(p.read_text("utf-8")) for p in sorted(directory.glob("RUN-*.json"))]


def annotations(root: Path) -> dict[str, dict[str, Any]]:
    private = json.loads((root / "benchmark/private/tasks.json").read_text("utf-8"))
    extra = root / "benchmark/private/tasks_misleading.json"
    if extra.exists():
        private.update(json.loads(extra.read_text("utf-8")))
    return private


def one_replicate(runs: list[Receipt]) -> tuple[list[Receipt], bool]:
    """El pre-registro cuenta 1 ejecución por (condición, tarea, semilla).

    Si hay réplicas, se usa la primera por orden de ``batch_id`` y se verifica que las demás
    sean idénticas en comportamiento; si no lo fueran, el análisis no es válido.
    """
    groups: dict[tuple[str, str, int], list[Receipt]] = defaultdict(list)
    for r in runs:
        groups[(r["memory_mode"], r["task"]["id"], r["seed"])].append(r)

    def behaviour(r: Receipt) -> tuple[Any, ...]:
        return (
            r["decision"]["selected"],
            tuple(r["decision"]["plan"]),
            json.dumps(r["outcome"], sort_keys=True),
            tuple(m["task"] for m in r["retrieval"]["memories"]),
        )

    chosen, consistent = [], True
    for rs in groups.values():
        rs.sort(key=lambda r: r["batch_id"])
        chosen.append(rs[0])
        consistent &= all(behaviour(r) == behaviour(rs[0]) for r in rs[1:])
    return chosen, consistent


def ratio(num: int, den: int) -> dict[str, Any]:
    return {"value": None if den == 0 else num / den, "numerator": num, "denominator": den}


def analyze(runs: list[Receipt], private: dict[str, dict[str, Any]]) -> dict[str, Any]:
    tasks = [r for r in runs if r["kind"] == "task_run"]
    selected, consistent = one_replicate(tasks)
    misleading = {t for t, a in private.items() if "decoy_family" in a}
    family = {t: a["family"] for t, a in private.items()}
    base = {(r["task"]["id"], r["seed"]): r for r in selected if r["memory_mode"] == A}

    out: dict[str, Any] = {"replicates_consistent": consistent, "conditions": {}}
    for mode in (A, B, C):
        rs = [r for r in selected if r["memory_mode"] == mode]
        mis = [r for r in rs if r["task"]["id"] in misleading]
        exposed = [(r, m) for r in mis for m in r["retrieval"]["memories"]]
        decoy = sum(family.get(m["task"]) == private[r["task"]["id"]]["decoy_family"] for r, m in exposed)
        train_pairs = [
            (r, base[(r["task"]["id"], r["seed"])])
            for r in rs
            if r["split"] == "train" and r["retrieval"]["memories"]
        ]
        neg = sum(
            not r["outcome"]["first_attempt_success"] and a["outcome"]["first_attempt_success"]
            for r, a in train_pairs
        )
        pos = sum(
            r["outcome"]["first_attempt_success"] and not a["outcome"]["first_attempt_success"]
            for r, a in train_pairs
        )
        out["conditions"][mode] = {
            "FirstAttemptSuccess_misleading": ratio(
                sum(r["outcome"]["first_attempt_success"] for r in mis), len(mis)
            ),
            "MisleadingRetrievalRate": ratio(decoy, len(exposed)),
            "NegativeTransferRate_train": ratio(neg, len(train_pairs)),
            "PositiveTransferRate_train": ratio(pos, len(train_pairs)),
            "per_misleading_task": {
                t: {
                    "first_attempt_success": sum(
                        r["outcome"]["first_attempt_success"] for r in mis if r["task"]["id"] == t
                    ),
                    "runs": sum(r["task"]["id"] == t for r in mis),
                    "recalled_from": sorted(
                        {m["task"] for r in mis if r["task"]["id"] == t for m in r["retrieval"]["memories"]}
                    ),
                }
                for t in sorted(misleading)
            },
        }

    fa = {m: out["conditions"][m]["FirstAttemptSuccess_misleading"] for m in (B, C)}
    nt = {m: out["conditions"][m]["NegativeTransferRate_train"] for m in (B, C)}
    diff_fa = fa[C]["numerator"] - fa[B]["numerator"]
    diff_nt = nt[B]["numerator"] - nt[C]["numerator"]
    out["decision"] = {
        "H4a": (
            "invalida (sin ejecuciones engañosas)"
            if fa[B]["denominator"] == 0
            else "apoyada"
            if diff_fa >= DECISION_MARGIN
            else "refutada"
            if diff_fa < 0
            else "sin diferencia"
        ),
        "H4a_difference_runs_C_minus_B": diff_fa,
        "H4b": "apoyada" if diff_nt >= DECISION_MARGIN else "no apoyada",
        "H4b_difference_pairs_B_minus_C": diff_nt,
        "H0_no_difference": diff_fa == 0 and diff_nt == 0,
    }
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
