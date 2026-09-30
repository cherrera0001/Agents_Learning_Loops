import argparse
import json
import random
import tempfile
import uuid
from pathlib import Path

from .agent import BoundedRepairAgent
from .benchmark import DIAGNOSTIC_CAMPAIGN, HISTORICAL_CAMPAIGN, REFERENCE_CAMPAIGN, TASK_SETS
from .diagnostic import DiagnosticRepairAgent
from .evaluate import compare, evaluate
from .evidence import read_receipt
from .memory import EvidenceMemory
from .models import MemoryMode
from .runner import (
    ROOT,
    execute_tests,
    load_task,
    prepare,
    run_experiment,
    update_memory,
)

CAMPAIGNS = {c["name"]: c for c in (REFERENCE_CAMPAIGN, DIAGNOSTIC_CAMPAIGN)}


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


def main():
    parser = argparse.ArgumentParser(description="Reproducible software-learning laboratory")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument(
        "--campaign",
        choices=sorted(CAMPAIGNS),
        help=(
            "declared campaign: reference-v2 (#44) or the opt-in diagnostic-baseline-v1 (#58); "
            "fixes seeds, replicates and task set (and the agent for #58)"
        ),
    )
    run.add_argument("--seeds", nargs="+", type=int, help="default: historical 7 11 23")
    run.add_argument("--replicates", type=int, help="default: 2")
    run.add_argument(
        "--evidence-dir",
        type=Path,
        help="default: evidence/runs; diagnostic-baseline-v1 defaults to its own directory",
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
