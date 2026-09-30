import argparse
import json
import random
import tempfile
import uuid
from pathlib import Path

from .agent import BoundedRepairAgent
from .benchmark import (
    DIAGNOSTIC_CAMPAIGN,
    FAILURE_MEMORY_CAMPAIGN,
    HISTORICAL_CAMPAIGN,
    REFERENCE_CAMPAIGN,
    TASK_SETS,
)
from .diagnostic import DiagnosticRepairAgent
from .evaluate import compare, evaluate
from .evidence import read_receipt
from .failure_memory import CONDITIONS, FailureMemory, FailureMemoryRepairAgent
from .memory import EvidenceMemory
from .models import MemoryMode
from .runner import (
    ROOT,
    execute_tests,
    load_task,
    prepare,
    run_experiment,
    update_failure_memory,
    update_memory,
)

CAMPAIGNS = {c["name"]: c for c in (REFERENCE_CAMPAIGN, DIAGNOSTIC_CAMPAIGN, FAILURE_MEMORY_CAMPAIGN)}


def campaign(seeds, replicates, evidence_dir, tasks=TASK_SETS["v1"], agent_factory=BoundedRepairAgent):
    if replicates < 1 or len(set(seeds)) != len(seeds):
        raise ValueError("positive replication count and unique seeds required")
    for _ in range(replicates):
        batch = "BATCH-" + uuid.uuid4().hex
        for seed in seeds:
            modes = list(MemoryMode)
            random.Random(seed).shuffle(modes)
            for mode in modes:
                memory = EvidenceMemory()
                for task_id in tasks:
                    path = run_experiment(
                        task_id,
                        agent_factory(),
                        mode,
                        seed,
                        memory=memory,
                        evidence_dir=evidence_dir,
                        batch_id=batch,
                    )
                    receipt = read_receipt(path)
                    print(
                        f"{batch} seed={seed} {mode.value} {task_id}: "
                        f"{receipt['result']} iterations={receipt['iterations']}",
                        flush=True,
                    )
                    if receipt["result"] == "ERROR":
                        raise RuntimeError(receipt["error"])
                    if receipt["split"] == "train" and mode != MemoryMode.NO_MEMORY:
                        update_memory(memory, path, evidence_dir)


def failure_campaign(
    seeds,
    replicates,
    evidence_dir,
    train=FAILURE_MEMORY_CAMPAIGN["train"],
    transfer=FAILURE_MEMORY_CAMPAIGN["transfer"],
):
    """Memoria de fallos (#63), pre-registro sección 4: por (réplica, semilla, condición), memorias
    nuevas; entrenamiento, pasada 1 y pasada 2 de la transferencia en el mismo orden. Las lecciones solo
    se añaden en entrenamiento (quedan congeladas tras él); la memoria de fallos de A_N y C_N se
    actualiza en línea después de cada ejecución, en las tres fases."""
    if replicates < 1 or len(set(seeds)) != len(seeds):
        raise ValueError("positive replication count and unique seeds required")
    sequence = [(task, 1, "train") for task in train]
    sequence += [(task, 1, "transfer") for task in transfer] + [(task, 2, "transfer") for task in transfer]
    for _ in range(replicates):
        batch = "BATCH-" + uuid.uuid4().hex
        for seed in seeds:
            conditions = list(CONDITIONS)
            random.Random(seed).shuffle(conditions)
            for condition in conditions:
                mode, enabled = CONDITIONS[condition]
                memory = EvidenceMemory()
                failures = FailureMemory() if enabled else None
                for task_id, pass_number, split in sequence:
                    path = run_experiment(
                        task_id,
                        FailureMemoryRepairAgent(),
                        mode,
                        seed,
                        memory=memory,
                        evidence_dir=evidence_dir,
                        batch_id=batch,
                        failures=failures,
                        condition=condition,
                        pass_number=pass_number,
                    )
                    receipt = read_receipt(path)
                    print(
                        f"{batch} seed={seed} {condition} pass={pass_number} {task_id}: "
                        f"{receipt['result']} iterations={receipt['iterations']}",
                        flush=True,
                    )
                    if receipt["result"] == "ERROR":
                        raise RuntimeError(receipt["error"])
                    if receipt["split"] != split:
                        raise RuntimeError(f"{task_id} no pertenece a la partición declarada ({split})")
                    if split == "train" and mode != MemoryMode.NO_MEMORY:
                        update_memory(memory, path, evidence_dir)
                    if failures is not None:
                        update_failure_memory(failures, path, evidence_dir)


def main():
    parser = argparse.ArgumentParser(description="Reproducible software-learning laboratory")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument(
        "--campaign",
        choices=sorted(CAMPAIGNS),
        help=(
            "declared campaign: reference-v2 (#44), the opt-in diagnostic-baseline-v1 (#58) or the "
            "opt-in failure-memory-v1 (#63); fixes seeds, replicates and task set (and the agent, "
            "conditions and passes for the opt-in ones)"
        ),
    )
    run.add_argument("--seeds", nargs="+", type=int, help="default: historical 7 11 23")
    run.add_argument("--replicates", type=int, help="default: 2")
    run.add_argument(
        "--evidence-dir",
        type=Path,
        help=(
            "default: evidence/runs; diagnostic-baseline-v1 and failure-memory-v1 default to their "
            "own directories"
        ),
    )
    run.add_argument(
        "--task-set",
        choices=sorted(TASK_SETS),
        help="default v1: published EXP-01..06 campaign; misleading-v1: adds EXP-07..09 (#45)",
    )
    ev = sub.add_parser("evaluate")
    ev.add_argument("--evidence-dir", type=Path, default=ROOT / "evidence/runs")
    ev.add_argument("--output", type=Path, default=ROOT / "results")
    cmp = sub.add_parser(
        "compare",
        help="compare two campaigns' semantic projections, source/test hashes included",
    )
    cmp.add_argument("--reference", type=Path, required=True)
    cmp.add_argument("--candidate", type=Path, required=True)
    repro = sub.add_parser("reproduce")
    repro.add_argument("task")
    args = parser.parse_args()
    if args.command == "run":
        declared = CAMPAIGNS[args.campaign] if args.campaign else HISTORICAL_CAMPAIGN
        seeds = list(declared["seeds"]) if args.seeds is None else args.seeds
        replicates = declared["replicates"] if args.replicates is None else args.replicates
        task_set = declared["task_set"] if args.task_set is None else args.task_set
        if args.campaign and (
            seeds != list(declared["seeds"])
            or replicates != declared["replicates"]
            or task_set != declared["task_set"]
        ):
            parser.error(f"--campaign {args.campaign} fixes seeds, replicates and task set")
        evidence_dir = args.evidence_dir or ROOT / declared.get("evidence_dir", "evidence/runs")
        if declared is DIAGNOSTIC_CAMPAIGN:
            campaign(
                seeds, replicates, evidence_dir, TASK_SETS[task_set], agent_factory=DiagnosticRepairAgent
            )
        elif declared is FAILURE_MEMORY_CAMPAIGN:
            failure_campaign(
                seeds,
                replicates,
                evidence_dir,
                FAILURE_MEMORY_CAMPAIGN["train"],
                FAILURE_MEMORY_CAMPAIGN["transfer"],
            )
        else:
            campaign(seeds, replicates, evidence_dir, TASK_SETS[task_set])
    elif args.command == "compare":
        try:
            result = compare(args.reference, args.candidate)
        except ValueError as error:
            raise SystemExit(f"compare: {error}") from error
        print(json.dumps(result, indent=2))
        if not result["identical"]:
            raise SystemExit(
                "compare: candidate differs from reference. If the change in behaviour or "
                "benchmark is intended, regenerate the reference campaign and review it."
            )
    elif args.command == "evaluate":
        report = evaluate(args.evidence_dir, args.output)
        print(
            json.dumps(
                {"metrics": report["metrics"], "replication": report["replication"]},
                indent=2,
            )
        )
    else:
        with tempfile.TemporaryDirectory(prefix="aal-reproduce-") as directory:
            workspace = Path(directory)
            prepare(load_task(args.task), workspace)
            result = execute_tests(workspace, 0)
            print(result["stdout"] + result["stderr"])
            raise SystemExit(result["returncode"])


if __name__ == "__main__":
    main()
