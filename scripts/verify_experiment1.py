"""Verificación independiente del Experimento 1 (software-learning-v1).

Reimplementa, a partir de ``specs/software_learning_protocol.md`` y **sin
importar el paquete ``experiments``**, las comprobaciones necesarias para
aceptar sus conclusiones:

- V2 integridad: cada recibo cumple ``sha256(canónico(recibo sin hash))``; una
  alteración deliberada se detecta; el reporte agregado cita exactamente los
  recibos existentes.
- V3 fuga: el contexto del solver no contiene etiquetas privadas; la memoria de
  entrenamiento no admite recibos de transferencia.
- V4 métricas: recalcula TaskSuccessRate, FirstAttemptSuccessRate,
  IterationsPerTask, recall/precisión/falsas recuperaciones y utilidad, y las
  compara con ``results/experiment1.json``.
- V7 tareas: cada defecto se reproduce antes de reparar y queda reparado.
- V8 par engañoso: qué lecciones se recuperaron en EXP-05 (síntoma parecido a
  EXP-01, causa distinta).

Uso::

    python -m scripts.verify_experiment1 --root <checkout con evidence/ y results/>
    python -m scripts.verify_experiment1 --root . --evidence evidence/replication \\
        --reference evidence/runs          # compara la proyección semántica (V5)
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

Receipt = dict[str, Any]
MODES = ("NO_MEMORY", "TEXT_HISTORY", "ASSOCIATIVE_MEMORY")
PRIVATE_KEYS = {"hidden_cause_id", "relevant_training_tasks", "mutation", "difficulty", "distance", "family"}


# --------------------------------------------------------------------- carga
def canonical(value: Any) -> bytes:
    """Forma canónica declarada por el protocolo (claves ordenadas, sin espacios, UTF-8)."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def receipt_hash(record: Receipt) -> str:
    body = {k: v for k, v in record.items() if k != "receipt_sha256"}
    return hashlib.sha256(canonical(body)).hexdigest()


def load(directory: Path) -> dict[str, Receipt]:
    return {p.name: json.loads(p.read_text("utf-8")) for p in sorted(directory.glob("RUN-*.json"))}


# ---------------------------------------------------------------- V2 integridad
def check_integrity(receipts: dict[str, Receipt], results: dict[str, Any] | None) -> dict[str, Any]:
    bad = [name for name, r in receipts.items() if receipt_hash(r) != r.get("receipt_sha256")]
    misnamed = [name for name, r in receipts.items() if name != f"{r['run_id']}.json"]
    # Control: una alteración mínima debe romper la verificación.
    sample = copy.deepcopy(next(iter(receipts.values())))
    if "outcome" in sample:
        sample["outcome"]["success"] = not sample["outcome"]["success"]
    else:
        sample["run_id"] += "x"
    tamper_detected = receipt_hash(sample) != sample["receipt_sha256"]
    out: dict[str, Any] = {
        "receipts": len(receipts),
        "hash_failures": bad,
        "misnamed": misnamed,
        "tamper_detected": tamper_detected,
    }
    if results is not None:
        cited = results.get("generated_from", {})
        out["results_cite_all_receipts"] = set(cited) == set(receipts)
        out["results_hash_mismatches"] = [
            n for n, h in cited.items() if n in receipts and h != receipts[n]["receipt_sha256"]
        ]
    return out


# ------------------------------------------------------------------- V3 fuga
def check_leakage(receipts: dict[str, Receipt], private: dict[str, Any], public_dir: Path) -> dict[str, Any]:
    runs = {r["run_id"]: r for r in receipts.values() if r["kind"] == "task_run"}
    private_values = {v["hidden_cause_id"] for v in private.values()}
    leaks: list[str] = []
    for r in runs.values():
        solver_view = {
            "task": r["task"],
            "memory_input": r["memory_input"],
            "initial_source": r["initial_source"],
        }
        text = json.dumps(solver_view, ensure_ascii=False)
        leaks += [f"{r['run_id']}: valor privado {v}" for v in private_values if v in text]
        leaks += [f"{r['run_id']}: clave privada {k}" for k in PRIVATE_KEYS if f'"{k}"' in text]
        public = json.loads((public_dir / f"{r['task']['id']}.json").read_text("utf-8"))
        extra = set(r["task"]) - set(public)
        if extra:
            leaks.append(f"{r['run_id']}: campos de tarea no públicos {sorted(extra)}")
    # La memoria solo puede provenir de entrenamiento.
    trained_from_transfer = [
        u["run_id"]
        for u in receipts.values()
        if u["kind"] == "memory_update"
        and runs.get(u["source_receipt"].removesuffix(".json"), {}).get("split") != "train"
    ]
    recalled_non_train = [
        f"{r['run_id']} ← {m}"
        for r in runs.values()
        for m in r["decision"]["memory_ids"]
        if runs.get(m.removeprefix("lesson:"), {}).get("split") != "train"
    ]
    return {
        "solver_context_leaks": leaks,
        "memory_updates_from_transfer": trained_from_transfer,
        "recalled_lessons_not_from_training": recalled_non_train,
    }


# ----------------------------------------------------------------- utilidades
def source_task(runs: dict[str, Receipt], memory_id: str) -> str:
    return runs[memory_id.removeprefix("lesson:")]["task"]["id"]


def repair_tests(r: Receipt) -> list[dict[str, Any]]:
    return [t for t in r["tests"] if t["id"] != "test-0"]  # test-0 = reproducción obligatoria


def mean_or_null(values: list[float]) -> float | None:
    """Media; ``None`` si no hay datos (el protocolo exige null, no 0 ni error)."""
    return mean(values) if values else None


def ratio(num: float, den: float) -> float | None:
    return None if den == 0 else num / den


# ------------------------------------------------------ V4 métricas independientes
def recompute_metrics(receipts: dict[str, Receipt], private: dict[str, Any]) -> dict[str, dict[str, Any]]:
    runs = {r["run_id"]: r for r in receipts.values() if r["kind"] == "task_run"}
    transfer = [r for r in runs.values() if r["split"] == "transfer"]
    paired = {
        (r["batch_id"], r["seed"], r["task"]["id"]): r for r in transfer if r["memory_mode"] == "NO_MEMORY"
    }
    metrics: dict[str, dict[str, Any]] = {}
    for mode in MODES:
        rs = [r for r in transfer if r["memory_mode"] == mode]
        retrieved = relevant = with_retrieval = used = useful = 0
        for r in rs:
            # «Recuperadas» = lecciones EXPUESTAS al solver (el historial textual las expone
            # todas); «uso» = la selección cita memoria, aunque solo confirme la elección previa.
            exposed = r["retrieval"]["memories"]
            if not exposed:
                continue
            with_retrieval += 1
            relevant_tasks = set(private[r["task"]["id"]]["relevant_training_tasks"])
            retrieved += len(exposed)
            relevant += sum(m["task"] in relevant_tasks for m in exposed)
            used += bool(r["decision"]["memory_ids"])
            base = paired[(r["batch_id"], r["seed"], r["task"]["id"])]
            changed = r["decision"]["selected"] != base["decision"]["selected"]
            better = (r["outcome"]["success"] and not base["outcome"]["success"]) or (
                r["outcome"]["success"]
                and base["outcome"]["success"]
                and r["outcome"]["iterations"] < base["outcome"]["iterations"]
            )
            useful += changed and better
        eligible = sum(len(private[r["task"]["id"]]["relevant_training_tasks"]) for r in rs)
        metrics[mode] = {
            "runs": len(rs),
            "TaskSuccessRate": mean_or_null([r["outcome"]["success"] for r in rs]),
            "FirstAttemptSuccessRate": mean_or_null([r["outcome"]["first_attempt_success"] for r in rs]),
            "IterationsPerTask": mean_or_null([r["outcome"]["iterations"] for r in rs]),
            "MemoryRetrievalRecall": ratio(relevant if mode != "NO_MEMORY" else 0, eligible),
            "MemoryRetrievalPrecision": ratio(relevant, retrieved),
            "FalseRetrievalRate": ratio(retrieved - relevant, retrieved),
            "MemoryUseRate": ratio(used, with_retrieval),
            "MemoryUtilityRate": ratio(useful, with_retrieval),
        }
    return metrics


def compare_metrics(mine: dict[str, dict[str, Any]], published: dict[str, Any]) -> list[str]:
    diffs = []
    for mode, values in mine.items():
        for key, value in values.items():
            ref = published["metrics"][mode].get(key)
            same = (value is None and ref is None) or (
                value is not None and ref is not None and abs(float(value) - float(ref)) < 1e-9
            )
            if not same:
                diffs.append(f"{mode}.{key}: independiente={value} publicado={ref}")
    return diffs


# -------------------------------------------------------------- V7 tareas
def check_tasks(receipts: dict[str, Receipt]) -> dict[str, dict[str, Any]]:
    runs = [r for r in receipts.values() if r["kind"] == "task_run"]
    report: dict[str, dict[str, Any]] = {}
    for task in sorted({r["task"]["id"] for r in runs}):
        rs = [r for r in runs if r["task"]["id"] == task]
        report[task] = {
            "issue": rs[0]["issue"]["number"],
            "split": rs[0]["split"],
            "runs": len(rs),
            "reproduced_before_repair": all(r["tests"][0]["returncode"] != 0 for r in rs),
            "repaired_in_all_runs": all(r["outcome"]["success"] and r["result"] == "PASS" for r in rs),
            "final_attempt_passes": all(repair_tests(r)[-1]["returncode"] == 0 for r in rs),
            "nonempty_patch": all(r["actions"][-1]["patch"] for r in rs),
            "first_strategy": {
                m: sorted({r["decision"]["selected"] for r in rs if r["memory_mode"] == m}) for m in MODES
            },
            "iterations": {
                m: sorted({r["outcome"]["iterations"] for r in rs if r["memory_mode"] == m}) for m in MODES
            },
        }
    return report


# ---------------------------------------------------------- V8 par engañoso
def check_misleading(receipts: dict[str, Receipt], task: str = "EXP-05") -> dict[str, Any]:
    runs = {r["run_id"]: r for r in receipts.values() if r["kind"] == "task_run"}
    out: dict[str, Any] = {}
    for mode in MODES:
        rs = [r for r in runs.values() if r["task"]["id"] == task and r["memory_mode"] == mode]
        recalled = defaultdict(int)
        for r in rs:
            for m in r["decision"]["memory_ids"]:
                recalled[source_task(runs, m)] += 1
        out[mode] = {
            "runs": len(rs),
            "lessons_recalled_by_source_task": dict(sorted(recalled.items())),
            "selected": sorted({r["decision"]["selected"] for r in rs}),
            "iterations": sorted({r["outcome"]["iterations"] for r in rs}),
        }
    return out


# --------------------------------------------------------- V5 replicación
def semantic_projection(r: Receipt, with_hashes: bool = False) -> tuple[Any, ...]:
    """Proyección semántica: comportamiento del agente, sin UUIDs, tiempos ni rutas.

    Con ``with_hashes`` incluye además los hashes de fuentes/tests del recibo. Esos
    hashes se calculan sobre los bytes del checkout, por lo que dependen de la
    configuración de fin de línea (CRLF/LF) de la máquina que ejecuta.
    """
    hashes = (r["initial_source_sha256"], r["acceptance_sha256"]) if with_hashes else ()
    return (
        *hashes,
        r["task"]["id"],
        r["memory_mode"],
        r["seed"],
        tuple(sorted(r["task"].items())),
        r["decision"]["selected"],
        tuple(r["decision"]["plan"]),
        tuple((a["strategy"], a["patch"], tuple(a["inspected"])) for a in r["actions"]),
        tuple(t["returncode"] for t in r["tests"]),
        json.dumps(r["outcome"], sort_keys=True),
        tuple(sorted(source_task_or_none(r, m) for m in r["decision"]["memory_ids"])),
    )


_TASK_OF_RUN: dict[str, str] = {}


def source_task_or_none(r: Receipt, memory_id: str) -> str:
    return _TASK_OF_RUN.get(memory_id.removeprefix("lesson:"), "?")


def compare_replication(new: dict[str, Receipt], reference: dict[str, Receipt]) -> dict[str, Any]:
    for rs in (new, reference):
        for r in rs.values():
            if r["kind"] == "task_run":
                _TASK_OF_RUN[r["run_id"]] = r["task"]["id"]

    def projections(rs: dict[str, Receipt], with_hashes: bool) -> set[tuple[Any, ...]]:
        return {semantic_projection(r, with_hashes) for r in rs.values() if r["kind"] == "task_run"}

    out: dict[str, Any] = {}
    for label, with_hashes in (("behaviour", False), ("behaviour_and_source_hashes", True)):
        a, b = projections(new, with_hashes), projections(reference, with_hashes)
        out[label] = {
            "distinct_new": len(a),
            "distinct_reference": len(b),
            "identical": a == b,
            "only_in_new": len(a - b),
        }
    return out


# --------------------------------------------------------------------- main
def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--evidence", default="evidence/runs")
    parser.add_argument("--reference", default=None, help="evidencia de referencia para V5")
    parser.add_argument("--results", default="results/experiment1.json")
    args = parser.parse_args()

    root = args.root
    receipts = load(root / args.evidence)
    private = json.loads((root / "benchmark/private/tasks.json").read_text("utf-8"))
    results_path = root / args.results
    results = json.loads(results_path.read_text("utf-8")) if results_path.exists() else None

    report: dict[str, Any] = {
        "V2_integrity": check_integrity(receipts, results if args.reference is None else None),
        "V3_leakage": check_leakage(receipts, private, root / "benchmark/public"),
        "V7_tasks": check_tasks(receipts),
        "V8_misleading_EXP05": check_misleading(receipts),
    }
    mine = recompute_metrics(receipts, private)
    report["V4_metrics_independent"] = mine
    if results is not None and args.reference is None:
        report["V4_metric_differences"] = compare_metrics(mine, results)
    if args.reference:
        report["V5_replication"] = compare_replication(receipts, load(root / args.reference))
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
