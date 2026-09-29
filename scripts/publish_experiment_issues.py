# ruff: noqa: E501 -- issue body prose is kept together for author review
"""Idempotently publish the six tasks and seven scientific proposals.

Explicit CLI action; does not close issues or put solutions/private labels in
task bodies. gh authentication is required. Bodies use UTF-8 files.
"""

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = "cherrera0001/Agents_Learning_Loops"
# Misleading tasks of #45 are published in the repository only (public JSON,
# acceptance test and benchmark/issue-proposals/EXP-0x.md), tracked by #45;
# no dedicated GitHub issue is created and their receipts carry issue=null.
IN_REPOSITORY_ONLY = {"EXP-07", "EXP-08", "EXP-09"}


def gh(*args):
    return subprocess.check_output(["gh", *args], cwd=ROOT).decode("utf-8").strip()


def main():
    existing = {
        i["title"]: i
        for i in json.loads(
            gh(
                "issue",
                "list",
                "--repo",
                REPO,
                "--state",
                "all",
                "--limit",
                "1000",
                "--json",
                "number,title,url",
            )
        )
    }
    directory = ROOT / "benchmark/issue-proposals"
    directory.mkdir(parents=True, exist_ok=True)
    proposals = []
    for path in sorted((ROOT / "benchmark/public").glob("EXP-*.json")):
        task = json.loads(path.read_text("utf-8"))
        if task["id"] in IN_REPOSITORY_ONLY:
            continue
        title = f"[{task['id']}] {task['title']}"
        body = (
            f"## Context\n\n{task['context']}\n\n## Expected\n\n{task['expected']}\n\n"
            f"## Observed\n\n{task['observed']}\n\n## Reproduction\n\n"
            "On the experiment/software-learning-v02 branch, install `pip install -e '.[dev]'`, then:\n\n"
            f"```sh\n{task['reproduction']}\n```\n\nThe injected fixture should fail before repair.\n\n"
            f"## Acceptance criteria\n\n{task['acceptance_criteria']} Business regression tests must also pass.\n\n"
            "## Experimental metadata\n\n```yaml\nexperiment: software-learning-v1\n"
            f"task_id: {task['id']}\n```\n\nFamily, difficulty, split and hidden_cause_id are evaluator-only metadata in "
            "benchmark/private/tasks.json. They are excluded from the solver context. "
            "No solution is included here. This issue is a task, not learned memory.\n"
        )
        proposals.append((task["id"], title, body))
    science = [
        (
            "hypothesis",
            "[HYPOTHESIS] Does prior evidence reduce repeated failures across related tasks?",
            "Does experience change decisions on related but different software tasks?",
            "Relevant prior evidence reduces repeated failures compared with a fresh no-memory agent.",
            "Six tasks, three causal families; train on EXP-01..03, freeze memory, evaluate EXP-04..06 with paired A/B/C and three seeds. Retain negative outcomes.",
        ),
        (
            "experiment0",
            "[EXPERIMENT] Establish synthetic associative-memory baseline",
            "What does the existing deterministic benchmark actually demonstrate?",
            "The current graph supports associative action reuse under controlled simulated conditions.",
            "Preserve weather_scenario, flaky_scenario, MemoryGraph, reinforcement, decay and pruning. Run the original tests and compare two JSON benchmark outputs.",
        ),
        (
            "experiment1",
            "[EXPERIMENT] Cross-task learning in a real software project",
            "Does training on one entry point improve repair at a different entry point?",
            "Evidence-grounded memory changes first strategy and improves a measurable outcome.",
            "Bounded AST repair agent; real WSGI/SQLite project; fresh identical defective snapshots, equal strategy budgets, actual subprocess tests, immutable receipts before aggregation.",
        ),
        (
            "benchmark",
            "[BENCHMARK] Build causal task families for transfer evaluation",
            "Can the benchmark distinguish causal transfer from superficial symptom matching?",
            "AUTH, CONFIG and READINESS pairs plus a misleading None/AttributeError pair expose both relevant retrieval and false positives.",
            "Author six independent defects, public acceptance contracts and private causal labels. Distances L3/L4/L5 are annotations to validate, not findings.",
        ),
        (
            "schema",
            "[DESIGN] Extend MemoryGraph from action ranking to evidence-grounded learning",
            "How can typed causal claims carry evidence without breaking old memories?",
            "A separate versioned typed graph with explicit evidence references can reuse the existing propagation engine.",
            "Keep Experiment 0 schema version 2 unchanged. Add software-learning-memory/v1 and an explicit read-only projection. Validate referential integrity and reject unknown versions/actions.",
        ),
        (
            "receipts",
            "[EVIDENCE] Introduce immutable run receipts",
            "Can each claim be reconstructed from actual execution?",
            "Append-only receipts with source hashes, patches, test outputs, decisions and separate memory-update events provide an auditable chain.",
            "Atomic no-clobber publication, canonical SHA-256 verification, error receipts and tests for overwrite, tampering, and failed publication.",
        ),
        (
            "evaluation",
            "[EVALUATION] Define learning and retrieval metrics",
            "Which observations distinguish memory available, used and useful?",
            "Paired strategy/action/outcome changes and explicit denominators distinguish useful memory from retrieval alone.",
            "Generate metrics and LearningGain from sealed receipts; reject mismatched pairs; preserve undefined denominators as null; no significance claim from repeated deterministic runs.",
        ),
    ]
    for key, title, question, hypothesis, method in science:
        result = (
            (
                "Initial ca853fd baseline: 71 tests passed; two JSON runs identical. Packaged ce6bc76 baseline: 78 tests passed. "
                "These observations do not demonstrate autonomous software-engineering learning."
            )
            if key == "experiment0"
            else "Pending sealed experiment campaign; no learning-gain conclusion yet."
        )
        body = (
            f"## Question\n\n{question}\n\n## Hypothesis\n\n{hypothesis}\n\n## Method\n\n{method}\n\n"
            "## Evidence\n\nReceipts: evidence/runs/. Initial audit: evidence/baseline/. "
            "Implementation and reproducible commands will be linked through the experiment PR.\n\n"
            f"## Result\n\n{result}\n\n## Limitations\n\nSix authored tasks, one bounded deterministic agent, "
            "handwritten generic repair operators, and no untrusted-agent OS sandbox. Same-seed repetition tests reproducibility, not independent statistical significance.\n\n"
            "## Next action\n\nReview infrastructure, seal receipts, regenerate results, inspect misleading retrievals and replicate independently. Keep this issue open.\n"
        )
        proposals.append((key, title, body))
    mapping = {}
    for key, title, body in proposals:
        body_path = directory / f"{key}.md"
        body_path.write_text(body, encoding="utf-8")
        issue = existing.get(title)
        if issue is None:
            url = gh(
                "issue",
                "create",
                "--repo",
                REPO,
                "--title",
                title,
                "--body-file",
                str(body_path),
            )
            issue = {"number": int(url.rsplit("/", 1)[-1]), "url": url, "title": title}
        mapping[key] = issue
        print(f"{key}: {issue['url']}", flush=True)
    (ROOT / "benchmark/issues.json").write_text(json.dumps(mapping, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
