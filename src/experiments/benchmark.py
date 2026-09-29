"""Controller/evaluator-only task sets, private annotations and per-task report.

Never imported by the agent. ``benchmark/private/tasks.json`` is pinned by the
published software-learning-v1 receipts (the evaluator rejects any hash
change), so the misleading tasks of #45 keep their annotations in a separate
``tasks_misleading.json``. Both files are merged here for the controller.
"""

import json
from collections import Counter, defaultdict
from pathlib import Path

PRIMARY_ANNOTATIONS = "benchmark/private/tasks.json"
EXTRA_ANNOTATIONS = ("benchmark/private/tasks_misleading.json",)
TASK_SETS = {
    # Published campaign: default, unchanged.
    "v1": tuple(f"EXP-{i:02d}" for i in range(1, 7)),
    # v1 plus three misleading transfer tasks without lexical cues (#45).
    "misleading-v1": tuple(f"EXP-{i:02d}" for i in range(1, 10)),
}
ALL_TASKS = frozenset(TASK_SETS["misleading-v1"])
# Historical campaign of Experiment 1 (evidence/runs): seeds 7, 11, 23 cover only 2 of the
# 6 orders of the no-memory prior (7 and 23 give the same one). Kept as published.
HISTORICAL_CAMPAIGN = {"seeds": (7, 11, 23), "replicates": 2, "task_set": "v1"}
# Reference campaign v2 (#44): seeds 1 4 5 6 7 9 cover all 6 permutations of the three
# operators exactly once (enforced by tests/test_experiment_reference_campaign.py), all
# nine tasks, two same-seed replicates, the three conditions, receipt schema v2.
REFERENCE_CAMPAIGN = {
    "name": "reference-v2",
    "seeds": (1, 4, 5, 6, 7, 9),
    "replicates": 2,
    "task_set": "misleading-v1",
}


def private_metadata(root):
    metadata = {}
    for name in (PRIMARY_ANNOTATIONS, *EXTRA_ANNOTATIONS):
        path = Path(root) / name
        if not path.exists():
            continue
        for key, value in json.loads(path.read_text("utf-8")).items():
            if key in metadata:
                raise ValueError(f"duplicate private annotation for {key}")
            metadata[key] = value
    return metadata


def check_extra_annotations(runs, root, current_manifest):
    """Extra annotation files must match what each receipt executed with.

    ``current_manifest`` is the runner's source manifest of ``root`` (same text
    hashing as receipts). Receipts that predate a file (the published v1
    campaign) do not list it; a receipt for a task annotated in it must.
    """
    for name in EXTRA_ANNOTATIONS:
        path = Path(root) / name
        annotated = set(json.loads(path.read_text("utf-8"))) if path.exists() else set()
        for r in runs:
            manifest = r["provenance"]["source_manifest"]
            if (name in manifest or r["task"]["id"] in annotated) and manifest.get(
                name
            ) != current_manifest.get(name):
                raise ValueError("private annotations differ from the executed benchmark")


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def mean(values):
    return sum(values) / len(values) if values else None


def task_breakdown(runs, metadata):
    """Per-task, per-condition observations plus MisleadingRetrievalRate.

    "Cited" lessons are the ones the solver's selection names
    (``decision.memory_ids``): the top-ranked lesson in TEXT_HISTORY (ranked by
    the agent) and ASSOCIATIVE_MEMORY (ranked by propagation). "Exposed"
    lessons are everything handed to the solver (``retrieval.memories``); the
    text history exposes every lesson, so exposure alone is uninformative there.
    """
    baseline = {
        (r["batch_id"], r["seed"], r["task"]["id"]): r for r in runs if r["memory_mode"] == "NO_MEMORY"
    }
    groups = defaultdict(list)
    for r in runs:
        groups[(r["memory_mode"], r["task"]["id"])].append(r)
    tasks = {}
    misleading = defaultdict(Counter)
    for (mode, task), items in sorted(groups.items()):
        meta = metadata[task]
        decoy = meta.get("decoy_family")
        exposed, cited, deltas = Counter(), Counter(), []
        for r in items:
            source = {m["id"]: m["task"] for m in r["retrieval"]["memories"]}
            exposed.update(source.values())
            cited.update(source[mid] for mid in r["decision"]["memory_ids"])
            pair = baseline.get((r["batch_id"], r["seed"], task))
            if mode != "NO_MEMORY" and pair is not None:
                deltas.append(r["iterations"] - pair["iterations"])
        cited_families = Counter()
        for source_task, n in cited.items():
            cited_families[metadata[source_task]["family"]] += n
        row = {
            "split": meta["split"],
            "family": meta["family"],
            "decoy_family": decoy,
            "runs": len(items),
            "TaskSuccessRate": mean([r["outcome"]["success"] for r in items]),
            "FirstAttemptSuccessRate": mean([r["outcome"]["first_attempt_success"] for r in items]),
            "IterationsPerTask": mean([r["iterations"] for r in items]),
            "IterationDeltaVsNoMemory": mean(deltas),
            "paired_runs": len(deltas),
            "first_strategy": dict(sorted(Counter(r["decision"]["selected"] for r in items).items())),
            "exposed_lessons_by_source_task": dict(sorted(exposed.items())),
            "cited_lessons_by_source_task": dict(sorted(cited.items())),
            "cited_lessons_by_source_family": dict(sorted(cited_families.items())),
        }
        if decoy is not None:
            decoy_exposed = sum(n for t, n in exposed.items() if metadata[t]["family"] == decoy)
            counts = {
                "runs": len(items),
                "cited": sum(cited.values()),
                "decoy_cited": cited_families[decoy],
                "correct_cited": cited_families[meta["family"]],
                "exposed": sum(exposed.values()),
                "decoy_exposed": decoy_exposed,
            }
            row["MisleadingRetrievalRate"] = ratio(counts["decoy_cited"], counts["cited"])
            row["misleading_counts"] = counts
            misleading[mode].update(counts)
        tasks.setdefault(task, {})[mode] = row
    summary = {
        mode: {
            "MisleadingRetrievalRate": ratio(c["decoy_cited"], c["cited"]),
            "CorrectFamilyRetrievalRate": ratio(c["correct_cited"], c["cited"]),
            "MisleadingExposureRate": ratio(c["decoy_exposed"], c["exposed"]),
            "counts": dict(sorted(c.items())),
        }
        for mode, c in sorted(misleading.items())
    }
    return {
        "schema_id": "software-learning-task-breakdown/v1",
        "misleading_tasks": sorted(t for t in tasks if metadata[t].get("decoy_family")),
        "MisleadingRetrievalRate": summary,
        "tasks": tasks,
        "definitions": {
            "MisleadingRetrievalRate": (
                "cited lessons whose source training task belongs to the task's decoy_family "
                "/ all cited lessons, over tasks annotated with decoy_family; null if no lesson was cited"
            ),
            "CorrectFamilyRetrievalRate": (
                "cited lessons from the task's true family / all cited lessons on misleading tasks"
            ),
            "MisleadingExposureRate": (
                "exposed decoy-family lessons / all exposed lessons on misleading tasks; "
                "TEXT_HISTORY exposes every lesson, so this is 1/3 by construction there"
            ),
            "cited": "lessons named by decision.memory_ids (what the selection actually used)",
            "exposed": "lessons in retrieval.memories (what the solver received)",
            "IterationDeltaVsNoMemory": (
                "mean(iterations - paired NO_MEMORY iterations); negative is favourable; null if unpaired"
            ),
        },
    }


def breakdown_markdown(breakdown):
    lines = [
        "# Per-task breakdown",
        "",
        "Generated with `python -m experiments evaluate`. Do not edit by hand.",
        "",
        "## MisleadingRetrievalRate",
        "",
        "| Condition | MisleadingRetrievalRate | decoy cited / cited | CorrectFamilyRetrievalRate |",
        "|---|---|---|---|",
    ]
    for mode, row in breakdown["MisleadingRetrievalRate"].items():
        c = row["counts"]
        lines.append(
            f"| {mode} | {row['MisleadingRetrievalRate']} | {c['decoy_cited']} / {c['cited']} "
            f"| {row['CorrectFamilyRetrievalRate']} |"
        )
    lines += [
        "",
        "## Tasks",
        "",
        "| Task | Split | Family | Decoy | Condition | Runs | Success | First attempt | Iterations "
        "| Delta vs A | Cited lessons by source task |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for task, modes in breakdown["tasks"].items():
        for mode, row in modes.items():
            lines.append(
                f"| {task} | {row['split']} | {row['family']} | {row['decoy_family'] or ''} | {mode} "
                f"| {row['runs']} | {row['TaskSuccessRate']} | {row['FirstAttemptSuccessRate']} "
                f"| {row['IterationsPerTask']} | {row['IterationDeltaVsNoMemory']} "
                f"| {json.dumps(row['cited_lessons_by_source_task'])} |"
            )
    return "\n".join(lines) + "\n"


def write_breakdown(output, runs, metadata):
    breakdown = task_breakdown(runs, metadata)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "task_breakdown.json").write_text(
        json.dumps(breakdown, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    (output / "task_breakdown.md").write_text(breakdown_markdown(breakdown), encoding="utf-8", newline="\n")
    return breakdown


def family_breakdown(runs, metadata):
    """Transfer results per family, condition and transfer kind (#44).

    ``original`` transfer tasks (no ``decoy_family``, EXP-04..06) reward following the
    lexical cue; ``misleading`` ones (EXP-07..09) have a decoy family and their
    interpretation is the opposite, so they are never pooled. Every cell carries its
    explicit numerators and denominators. LearningGain is metric(condition) minus
    metric(NO_MEMORY) in the same cell; negative iterations are favourable.
    """
    cells = defaultdict(list)
    for r in runs:
        if r["split"] != "transfer":
            continue
        meta = metadata[r["task"]["id"]]
        kind = "misleading" if meta.get("decoy_family") else "original"
        cells[(kind, meta["family"], r["memory_mode"])].append(r)
    report = {}
    for (kind, family, mode), items in sorted(cells.items()):
        n = len(items)
        first = sum(r["outcome"]["first_attempt_success"] for r in items)
        iterations = sum(r["iterations"] for r in items)
        report.setdefault(kind, {}).setdefault(family, {})[mode] = {
            "tasks": sorted({r["task"]["id"] for r in items}),
            "runs": n,
            "first_attempt_successes": first,
            "iterations_total": iterations,
            "FirstAttemptSuccessRate": ratio(first, n),
            "IterationsPerTask": ratio(iterations, n),
        }
    for families in report.values():
        for modes in families.values():
            base = modes.get("NO_MEMORY")
            for mode, cell in modes.items():
                if mode == "NO_MEMORY" or base is None:
                    continue
                cell["LearningGain"] = {
                    "IterationsPerTask": cell["IterationsPerTask"] - base["IterationsPerTask"],
                    "FirstAttemptSuccessRate": cell["FirstAttemptSuccessRate"]
                    - base["FirstAttemptSuccessRate"],
                }
    return {
        "schema_id": "software-learning-family-breakdown/v1",
        "partition": "transfer",
        "kinds": report,
        "definitions": {
            "original": (
                "transfer tasks without decoy_family (EXP-04..06): the public text is lexically "
                "closest to the correct family, so success does not show causal transfer over lexical cues"
            ),
            "misleading": (
                "transfer tasks with decoy_family (EXP-07..09): the public text imitates a decoy "
                "family; opposite interpretation, never pooled with original"
            ),
            "cell": (
                "runs = transfer runs of that family and condition over all seeds and replicates; "
                "rates = numerator / runs"
            ),
            "LearningGain": (
                "metric(condition) - metric(NO_MEMORY) in the same cell; negative IterationsPerTask "
                "is favourable, positive FirstAttemptSuccessRate is favourable"
            ),
        },
    }


def _signed(value):
    return "" if value is None else f"{value:+.3f}"


def family_markdown(breakdown):
    lines = [
        "# Transfer results per family",
        "",
        "Generated with `python -m experiments evaluate`. Do not edit by hand.",
        "Descriptive; original and misleading transfer tasks are interpreted oppositely and never pooled.",
    ]
    for kind, families in breakdown["kinds"].items():
        lines += [
            "",
            f"## {kind} transfer tasks",
            "",
            "| Family | Tasks | Condition | Runs | First attempt (n/runs) | Iterations (total/runs) "
            "| Gain first attempt | Gain iterations |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for family, modes in families.items():
            for mode, c in modes.items():
                gain = c.get("LearningGain", {})
                lines.append(
                    f"| {family} | {', '.join(c['tasks'])} | {mode} | {c['runs']} "
                    f"| {c['FirstAttemptSuccessRate']:.3f} ({c['first_attempt_successes']}/{c['runs']}) "
                    f"| {c['IterationsPerTask']:.3f} ({c['iterations_total']}/{c['runs']}) "
                    f"| {_signed(gain.get('FirstAttemptSuccessRate'))} "
                    f"| {_signed(gain.get('IterationsPerTask'))} |"
                )
    return "\n".join(lines) + "\n"


def write_family_breakdown(output, runs, metadata):
    breakdown = family_breakdown(runs, metadata)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "family_breakdown.json").write_text(
        json.dumps(breakdown, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    (output / "family_breakdown.md").write_text(family_markdown(breakdown), encoding="utf-8", newline="\n")
    return breakdown
