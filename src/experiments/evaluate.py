"""Generate metrics exclusively from sealed receipts plus evaluator annotations."""

import json
import re
from collections import defaultdict
from pathlib import Path

from .benchmark import (
    check_extra_annotations,
    private_metadata,
    write_breakdown,
    write_family_breakdown,
)
from .evidence import (
    SOURCE_HASH_NORMALIZATION,
    digest,
    hash_normalization,
    normalize_source,
    read_receipt,
    source_sha256,
)
from .runner import ROOT, source_manifest


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def signature(test):
    matches = re.findall(r"^(?:\w+\.)*\w*(?:Error|Exception): .+$", test["stderr"], flags=re.MULTILINE)
    return matches[-1] if matches else None


def comparable(baseline, treatment):
    return (
        all(
            baseline[k] == treatment[k]
            for k in (
                "seed",
                "agent",
                "budget",
                "initial_source_sha256",
                "acceptance_sha256",
            )
        )
        and baseline["provenance"] == treatment["provenance"]
    )


def semantic(record):
    """Explicit reproducibility projection, excluding UUIDs, time and OS paths.

    Source/test hashes are only comparable between receipts that share a
    normalization scheme; callers must enforce that with ``single_scheme``.
    """
    return {
        "hash_normalization": hash_normalization(record),
        "task": record["task"]["id"],
        "seed": record["seed"],
        "mode": record["memory_mode"],
        "source": record["initial_source_sha256"],
        "tests": record["acceptance_sha256"],
        "result": record["result"],
        "iterations": record["iterations"],
        "retrieved_tasks": [m["task"] for m in record["retrieval"]["memories"]],
        "decision": {k: v for k, v in record["decision"].items() if k != "memory_ids"},
        "actions": [{k: v for k, v in a.items() if k != "memory_ids"} for a in record["actions"]],
        "test_exit_codes": [t["returncode"] for t in record["tests"]],
    }


def single_scheme(receipts):
    """Refuse to compare source/test hashes across normalization schemes.

    A v1 (checkout-bytes/v0) and a v2 (lf/v1) receipt of the same tree may carry
    different hashes for identical content; comparing them would report a false
    difference, so mixing is an explicit error instead.
    """
    schemes = {hash_normalization(r) for r in receipts}
    if len(schemes) > 1:
        raise ValueError(
            "cannot compare source/test hashes across normalization schemes: " + ", ".join(sorted(schemes))
        )
    return schemes.pop() if schemes else None


def load_runs(evidence_dir):
    paths = sorted(Path(evidence_dir).glob("RUN-*.json"))
    receipts = [read_receipt(p) for p in paths]
    runs = [r for r in receipts if r["kind"] == "task_run"]
    # Fail closed. Excluding errors from denominator would bias the report.
    errors = [r["run_id"] for r in runs if r["result"] == "ERROR"]
    if errors:
        raise ValueError(f"Harness ERROR receipts require investigation; not a valid campaign: {errors}")
    return paths, receipts, runs


def evaluate(evidence_dir=None, output=None, root=ROOT):
    evidence_dir = Path(evidence_dir or root / "evidence/runs")
    paths, receipts, runs = load_runs(evidence_dir)
    single_scheme(receipts)
    metadata = private_metadata(root)
    by_id = {r["run_id"]: r for r in runs}
    # Same normalization as the runner's source manifest. For v1 receipts it is
    # equivalent (universal-newline text) unless the file starts with a BOM.
    metadata_hash = source_sha256((root / "benchmark/private/tasks.json").read_bytes())
    for r in runs:
        if r["provenance"]["source_manifest"]["benchmark/private/tasks.json"] != metadata_hash:
            raise ValueError("private annotations differ from the executed benchmark")
        if digest(r["initial_source"]) != r["initial_source_sha256"]:
            raise ValueError("source snapshot mismatch")
        if hash_normalization(r) == SOURCE_HASH_NORMALIZATION and any(
            normalize_source(text) != text for text in r["initial_source"].values()
        ):
            raise ValueError("source snapshot is not normalized as declared")
        if r["memory_mode"] == "NO_MEMORY" and (r["retrieved_memories"] or r["memory_input"]):
            raise ValueError("no-memory contamination")
        for lesson in (r["memory_input"] or {}).get("lessons", []):
            prior = by_id.get(lesson["run_id"])
            if (
                prior is None
                or prior["split"] != "train"
                or prior["result"] != "PASS"
                or any(prior[k] != r[k] for k in ("batch_id", "seed", "memory_mode"))
                or prior["receipt_sha256"] != lesson["receipt_sha256"]
            ):
                raise ValueError("memory provenance/leakage violation")
            refs = {prior["run_id"] + "#" + t["id"] for t in prior["tests"]}
            if not lesson["evidence"] or not set(lesson["evidence"]) <= refs:
                raise ValueError("unresolvable memory evidence")
    check_extra_annotations(runs, root, source_manifest(root))
    index = {}
    for r in runs:
        key = (r["batch_id"], r["seed"], r["task"]["id"], r["memory_mode"])
        if key in index:
            raise ValueError("duplicate condition in batch; use distinct batch IDs")
        index[key] = r
    groups = defaultdict(list)
    comparisons = []
    for r in runs:
        if r["split"] != "transfer":
            continue
        groups[r["memory_mode"]].append(r)
        baseline = index.get((r["batch_id"], r["seed"], r["task"]["id"], "NO_MEMORY"))
        if baseline is None or not comparable(baseline, r):
            raise ValueError("missing or mismatched paired no-memory baseline")
        selected_changed = baseline["decision"]["selected"] != r["decision"]["selected"]
        action_changed = baseline["actions"][0]["strategy"] != r["actions"][0]["strategy"]
        influenced = bool(r["decision"]["influenced_by_memory"] and r["decision"]["memory_ids"])
        improved = (r["outcome"]["success"] and not baseline["outcome"]["success"]) or (
            r["outcome"]["success"]
            and baseline["outcome"]["success"]
            and r["iterations"] < baseline["iterations"]
        )
        relevant = set(metadata[r["task"]["id"]]["relevant_training_tasks"])
        retrieved = {m["id"]: m["task"] for m in r["retrieval"]["memories"]}
        used_relevant = any(retrieved.get(mid) in relevant for mid in r["decision"]["memory_ids"])

        def details(item):
            inspected = item["actions"][0]["inspected"]
            relevant_file = metadata[item["task"]["id"]]["mutation"]["path"]
            return {
                "success": item["outcome"]["success"],
                "first_hypothesis": item["initial_hypothesis"],
                "first_file_inspected": inspected[0] if inspected else None,
                "first_relevant_file_inspected": relevant_file if relevant_file in inspected else None,
                "relevant_file_position": inspected.index(relevant_file) + 1
                if relevant_file in inspected
                else None,
                "iterations": item["iterations"],
                "failed_attempts": item["outcome"]["failed_attempts"],
                "tests_executed": len(item["tests"]),
                "duration_ms": item["duration_ms"],
                "retrieved_tasks": [m["task"] for m in item["retrieval"]["memories"]],
            }

        comparisons.append(
            {
                "baseline": baseline["run_id"],
                "treatment": r["run_id"],
                "task": r["task"]["id"],
                "mode": r["memory_mode"],
                "seed": r["seed"],
                "batch_id": r["batch_id"],
                "memory_available": bool(retrieved),
                "memory_used": bool(r["decision"]["memory_ids"]),
                "decision_changed": selected_changed,
                "action_changed": action_changed,
                "outcome_improved": improved,
                "memory_useful": bool(
                    retrieved and influenced and selected_changed and action_changed and improved
                ),
                "causally_relevant_memory_used": used_relevant,
                "causal_chain_supported": bool(
                    used_relevant and influenced and selected_changed and action_changed and improved
                ),
                "baseline_observations": details(baseline),
                "treatment_observations": details(r),
            }
        )
    metrics = {}
    for mode, items in sorted(groups.items()):
        matched = [p for p in comparisons if p["mode"] == mode]
        retrieved_count = relevant_count = possible = failures = repeated = retrieved_runs = 0
        for r in items:
            relevant = set(metadata[r["task"]["id"]]["relevant_training_tasks"])
            retrieved = [m["task"] for m in r["retrieval"]["memories"]]
            possible += len(relevant)
            retrieved_count += len(retrieved)
            relevant_count += len(set(retrieved) & relevant)
            retrieved_runs += bool(retrieved)
            known = any(
                t["result"] == "PASS"
                and t["split"] == "train"
                and t["batch_id"] == r["batch_id"]
                and t["seed"] == r["seed"]
                and t["memory_mode"] == mode
                and metadata[t["task"]["id"]]["hidden_cause_id"]
                == metadata[r["task"]["id"]]["hidden_cause_id"]
                for t in runs
            )
            for test in r["tests"][1:]:
                if test["returncode"] != 0:
                    failures += 1
                    repeated += bool(
                        known and signature(test) and signature(test) == signature(r["tests"][0])
                    )
        metrics[mode] = {
            "runs": len(items),
            "TaskSuccessRate": ratio(sum(r["outcome"]["success"] for r in items), len(items)),
            "FirstAttemptSuccessRate": ratio(
                sum(r["outcome"]["first_attempt_success"] for r in items), len(items)
            ),
            "IterationsPerTask": ratio(sum(r["iterations"] for r in items), len(items)),
            "RepeatedFailureRate": ratio(repeated, failures),
            "MemoryRetrievalRecall": ratio(relevant_count, possible),
            "MemoryRetrievalPrecision": ratio(relevant_count, retrieved_count),
            "MemoryUseRate": ratio(sum(p["memory_used"] for p in matched), retrieved_runs),
            "MemoryUtilityRate": ratio(sum(p["memory_useful"] for p in matched), retrieved_runs),
            "FalseRetrievalRate": ratio(retrieved_count - relevant_count, retrieved_count),
            "counts": {
                "retrieved": retrieved_count,
                "relevant_retrieved": relevant_count,
                "relevant_possible": possible,
                "runs_with_retrieval": retrieved_runs,
                "failures": failures,
                "repeated_known_cause_failures": repeated,
            },
        }
    baseline_metrics = metrics.get("NO_MEMORY", {})
    gains = {
        mode: {
            k: (v - baseline_metrics[k] if v is not None and baseline_metrics.get(k) is not None else None)
            for k, v in row.items()
            if k not in ("runs", "counts")
        }
        for mode, row in metrics.items()
        if mode != "NO_MEMORY"
    }
    replicas = {key: [digest(p) for p in items] for key, items in projections(runs).items()}
    report = {
        "schema_id": "software-learning-results/v1",
        "generated_from": {p.name: r["receipt_sha256"] for p, r in zip(paths, receipts, strict=True)},
        "metrics": metrics,
        "LearningGain": gains,
        "comparisons": comparisons,
        "replication": {
            "groups": len(replicas),
            "replicated_groups": sum(len(v) > 1 for v in replicas.values()),
            "all_semantic_projections_equal": all(len(set(v)) == 1 for v in replicas.values()),
        },
        "interpretation": (
            "Descriptive bounded-agent experiment. No statistical significance "
            "or autonomous software-engineering learning claim."
        ),
        "definitions": {
            "RepeatedFailureRate": (
                "same reproduced exception signature and previously successful training cause "
                "/ all failed repair attempts; reproduction probes excluded"
            ),
            "MemoryUseRate": "runs explicitly citing memory in selection / runs with retrieval",
            "MemoryUtilityRate": (
                "retrieval changed first strategy and action and improved success or iterations "
                "vs paired baseline / runs with retrieval"
            ),
            "LearningGain": (
                "metric(memory) - metric(NO_MEMORY); negative IterationsPerTask is favorable; "
                "null means undefined"
            ),
            "time": "wall time is recorded but never used as proof of improvement",
            "replication": "same-seed determinism checks, not independent scientific samples",
        },
    }
    if output is not None:
        output = Path(output)
        output.mkdir(parents=True, exist_ok=True)
        (output / "experiment1.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        lines = [
            "# Generated Experiment 1 results",
            "",
            report["interpretation"],
            "",
            "Generated with `python -m experiments evaluate`. Do not edit by hand.",
            "",
        ]
        for mode, row in metrics.items():
            lines.append(f"## {mode}\n")
            lines.extend(f"- {k}: {v}" for k, v in row.items())
            lines.append("")
        lines.extend(
            [
                "## Replication",
                "",
                json.dumps(report["replication"]),
                "",
                "Full paired comparisons, denominators, receipt hashes and LearningGain: "
                "[experiment1.json](experiment1.json).",
            ]
        )
        (output / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        # Separate files so experiment1.json of the published campaign is unchanged (#45).
        write_breakdown(output, runs, metadata)
        write_family_breakdown(output, runs, metadata)
    return report


def projections(runs):
    """Semantic projections grouped by condition (seed, task, memory mode)."""
    single_scheme(runs)
    groups = defaultdict(list)
    for r in runs:
        groups[(r["seed"], r["task"]["id"], r["memory_mode"])].append(semantic(r))
    return groups


def compare(reference_dir, candidate_dir):
    """Compare two campaigns' semantic projections, source/test hashes included.

    Both directories must use one and the same normalization scheme (otherwise
    ValueError). Each condition must be internally deterministic and present in
    both campaigns with an identical projection.
    """
    _, _, reference_runs = load_runs(reference_dir)
    _, _, candidate_runs = load_runs(candidate_dir)
    if not reference_runs or not candidate_runs:
        raise ValueError("both campaigns must contain task_run receipts")
    scheme = single_scheme([*reference_runs, *candidate_runs])

    def unique(groups, label):
        out, unstable = {}, []
        for key, items in sorted(groups.items()):
            distinct = {digest(p): p for p in items}
            if len(distinct) > 1:
                unstable.append(f"{label}:{key[1]}/{key[2]}/seed={key[0]}")
            out[key] = next(iter(distinct.values()))
        return out, unstable

    reference, unstable_ref = unique(projections(reference_runs), "reference")
    candidate, unstable_cand = unique(projections(candidate_runs), "candidate")
    differences = []
    for key in sorted(reference.keys() & candidate.keys()):
        a, b = reference[key], candidate[key]
        fields = sorted(k for k in a.keys() | b.keys() if a.get(k) != b.get(k))
        if fields:
            differences.append({"seed": key[0], "task": key[1], "mode": key[2], "fields": fields})

    def fmt(keys):
        return [f"{k[1]}/{k[2]}/seed={k[0]}" for k in sorted(keys)]

    report = {
        "hash_normalization": scheme,
        "reference_groups": len(reference),
        "candidate_groups": len(candidate),
        "missing_in_candidate": fmt(reference.keys() - candidate.keys()),
        "extra_in_candidate": fmt(candidate.keys() - reference.keys()),
        "nondeterministic_groups": unstable_ref + unstable_cand,
        "differences": differences,
    }
    report["identical"] = not (
        report["missing_in_candidate"]
        or report["extra_in_candidate"]
        or report["nondeterministic_groups"]
        or differences
    )
    return report
