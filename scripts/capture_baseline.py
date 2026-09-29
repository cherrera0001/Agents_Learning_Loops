"""Capture actual test/benchmark output and provenance before a campaign."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def command(args):
    result = subprocess.run(args, cwd=ROOT, capture_output=True, check=False)
    return {
        "command": args,
        "returncode": result.returncode,
        "stdout": result.stdout.decode("utf-8", "replace"),
        "stderr": result.stderr.decode("utf-8", "replace"),
    }


def main():
    directory = ROOT / "evidence/baseline"
    directory.mkdir(parents=True, exist_ok=True)
    record = {
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip(),
        "python": sys.version,
        "original_suite": command(
            [sys.executable, "-m", "pytest", "-q", "--ignore=tests/test_experiment_harness.py"]
        ),
        "packages": command([sys.executable, "-m", "pip", "freeze"]),
    }
    args = [sys.executable, "-m", "associative_agent_loop.main", "--json"]
    first, second = command(args), command(args)
    if first["returncode"] or second["returncode"] or first["stdout"] != second["stdout"]:
        raise RuntimeError("Experiment 0 failed reproducibility")
    record["benchmark_runs"] = [first, second]
    record["benchmark_sha256"] = hashlib.sha256(first["stdout"].encode()).hexdigest()
    record["benchmark_repeat_identical"] = True
    reference = directory / "ca853fd-experiment0.json"
    if reference.exists():
        record["matches_original_ca853fd"] = json.loads(reference.read_text("utf-8")) == json.loads(
            first["stdout"]
        )
        if not record["matches_original_ca853fd"]:
            raise RuntimeError("Experiment 0 changed compared with original baseline")
    destination = directory / f"audit-{record['commit'][:8]}.json"
    with destination.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(record, indent=2) + "\n")
    print(record["original_suite"]["stdout"])
    print(f"Experiment 0 identical across runs; audit: {destination}")
    if record["original_suite"]["returncode"]:
        raise SystemExit(record["original_suite"]["returncode"])


if __name__ == "__main__":
    main()
