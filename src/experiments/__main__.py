import argparse
import json
import random
import tempfile
import uuid
from pathlib import Path

from .agent import BoundedRepairAgent
from .evaluate import evaluate
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


def campaign(seeds, replicates, evidence_dir):
    if replicates < 1 or len(set(seeds)) != len(seeds):
        raise ValueError("positive replication count and unique seeds required")
    for _ in range(replicates):
        batch = "BATCH-" + uuid.uuid4().hex
        for seed in seeds:
            modes = list(MemoryMode)
            random.Random(seed).shuffle(modes)
            for mode in modes:
                memory = EvidenceMemory()
                for task_id in [f"EXP-{i:02d}" for i in range(1, 7)]:
                    path = run_experiment(
                        task_id,
                        BoundedRepairAgent(),
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
    run.add_argument("--seeds", nargs="+", type=int, default=[7, 11, 23])
    run.add_argument("--replicates", type=int, default=2)
    run.add_argument("--evidence-dir", type=Path, default=ROOT / "evidence/runs")
    ev = sub.add_parser("evaluate")
    ev.add_argument("--evidence-dir", type=Path, default=ROOT / "evidence/runs")
    ev.add_argument("--output", type=Path, default=ROOT / "results")
    repro = sub.add_parser("reproduce")
    repro.add_argument("task")
    args = parser.parse_args()
    if args.command == "run":
        campaign(args.seeds, args.replicates, args.evidence_dir)
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
