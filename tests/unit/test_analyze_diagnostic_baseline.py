"""El análisis pre-registrado de #58 debe poder llegar a cada lectura, con recibos sintéticos."""

import pytest

from scripts.analyze_diagnostic_baseline import AGENT, POLICY, analyze

PRIVATE = {
    "EXP-01": {"family": "authentication"},
    "EXP-04": {"family": "authentication"},
    "EXP-07": {"family": "authentication", "decoy_family": "readiness"},
}
PRIOR = ["initialize_storage", "validate_optional_identity", "normalize_environment"]


def run(mode, task, seed, *, first, status="partial", proposal=None, plan=None, batch="B1", split="transfer"):
    plan = plan or PRIOR
    iterations = 1 if first else 2
    return {
        "kind": "task_run",
        "agent": AGENT,
        "memory_mode": mode,
        "task": {"id": task},
        "seed": seed,
        "split": split,
        "batch_id": batch,
        "iterations": iterations,
        "duration_ms": 1.0,
        "tests": [{}] * (iterations + 1),
        "decision": {
            "policy": POLICY,
            "plan": plan,
            "memory_ids": ["m"] if proposal else [],
            "memory_proposal": proposal,
            "memory_effect": "no_proposal" if proposal is None else "changed_first",
            "diagnostic": {"status": status},
        },
        "outcome": {"success": True, "first_attempt_success": first, "iterations": iterations},
        "retrieval": {"memories": [{"id": "m", "task": "EXP-01"}] if proposal else []},
    }


def campaign(first_b, first_c, *, first_a=lambda s: s < 3, task="EXP-04", seeds=range(18)):
    runs = []
    for s in seeds:
        runs.append(run("NO_MEMORY", task, s, first=first_a(s)))
        runs.append(run("TEXT_HISTORY", task, s, first=first_b(s), proposal="p", plan=PRIOR[::-1]))
        runs.append(run("ASSOCIATIVE_MEMORY", task, s, first=first_c(s), proposal="p", plan=PRIOR[::-1]))
    return runs


def test_each_reading_is_reachable_and_uses_exact_counts():
    report = analyze(campaign(lambda s: s < 6, lambda s: s < 5), PRIVATE)
    comparison = report["kinds"]["original"]["comparisons"]["TEXT_HISTORY"]
    assert comparison["FirstAttemptSuccess"] == {"value": 6 / 18, "numerator": 6, "denominator": 18}
    assert comparison["FirstAttemptSuccess_NO_MEMORY"]["numerator"] == 3
    assert comparison["FirstAttemptDifference"] == {"runs": 3, "rate": 3 / 18}
    assert report["verdicts"]["original/TEXT_HISTORY"] == "aporta"
    assert report["verdicts"]["original/ASSOCIATIVE_MEMORY"] == "sin diferencia"  # +2 < 3
    worse = analyze(campaign(lambda s: False, lambda s: s < 1), PRIVATE)
    assert worse["verdicts"]["original/TEXT_HISTORY"] == "perjudica"  # 0 - 3 = -3
    assert worse["verdicts"]["original/ASSOCIATIVE_MEMORY"] == "sin diferencia"  # 1 - 3 = -2


def test_original_and_misleading_are_never_pooled():
    runs = campaign(lambda s: s < 6, lambda s: s < 6) + campaign(
        lambda s: False, lambda s: False, task="EXP-07"
    )
    report = analyze(runs, PRIVATE)
    assert report["verdicts"]["original/TEXT_HISTORY"] == "aporta"
    assert report["verdicts"]["misleading/TEXT_HISTORY"] == "perjudica"
    assert report["kinds"]["misleading"]["comparisons"]["TEXT_HISTORY"]["pairs"] == 18


def test_missing_denominator_is_invalid_not_zero():
    report = analyze(campaign(lambda s: s < 6, lambda s: s < 6), PRIVATE)
    assert report["verdicts"]["misleading/TEXT_HISTORY"] == "inválido"
    assert (
        report["kinds"]["misleading"]["comparisons"]["TEXT_HISTORY"]["FirstAttemptSuccess"]["value"] is None
    )


def test_nulls_by_construction_are_marked_and_headroom_does_not_filter_denominators():
    runs = []
    for s in range(18):
        decisive = s < 6
        status = "decisive" if decisive else "partial"
        runs.append(run("NO_MEMORY", "EXP-04", s, first=decisive, status=status))
        for mode in ("TEXT_HISTORY", "ASSOCIATIVE_MEMORY"):
            plan = PRIOR if decisive else PRIOR[::-1]
            runs.append(run(mode, "EXP-04", s, first=decisive, status=status, proposal="p", plan=plan))
    comparison = analyze(runs, PRIVATE)["kinds"]["original"]["comparisons"]["TEXT_HISTORY"]
    assert comparison["pairs"] == 18  # decisive pairs stay in the denominator
    assert comparison["pair_classes"] == {"null_by_construction": 6, "null_observed": 12}
    assert comparison["headroom"]["first_action_forced"] == 6
    assert comparison["headroom"]["diagnostic_status"] == {"decisive": 6, "partial": 12}


def test_pairs_classify_success_before_iterations():
    runs = campaign(lambda s: True, lambda s: s < 3, first_a=lambda s: s < 3)
    classes = analyze(runs, PRIVATE)["kinds"]["original"]["comparisons"]
    assert classes["TEXT_HISTORY"]["pair_classes"] == {"null_observed": 3, "positive": 15}
    between = classes["ASSOCIATIVE_MEMORY_vs_TEXT_HISTORY"]
    assert between["pair_classes"] == {"negative": 15, "null_by_construction": 3}  # identical plans
    assert between["headroom"]["plan_identical"] == 18


def test_inconsistent_replicates_invalidate_every_verdict():
    runs = campaign(lambda s: s < 6, lambda s: s < 6)
    runs.append(run("TEXT_HISTORY", "EXP-04", 0, first=False, proposal="p", plan=PRIOR[::-1], batch="B2"))
    report = analyze(runs, PRIVATE)
    assert report["replicates_consistent"] is False
    assert set(report["verdicts"].values()) == {"inválido"}


def test_other_agents_or_policies_are_rejected():
    runs = campaign(lambda s: True, lambda s: True)
    runs[0] = {**runs[0], "agent": "bounded-ast-repair-v1"}
    with pytest.raises(ValueError, match="solo recibos"):
        analyze(runs, PRIVATE)


def test_training_is_reported_without_a_verdict():
    runs = campaign(lambda s: True, lambda s: True, task="EXP-01")
    for r in runs:
        r["split"] = "train"
    report = analyze(runs, PRIVATE)
    assert report["kinds"]["train"]["comparisons"]["TEXT_HISTORY"]["pairs"] == 18
    assert not any(key.startswith("train") for key in report["verdicts"])


def test_success_decides_before_iterations():
    runs = campaign(lambda s: False, lambda s: False, first_a=lambda s: False)
    for r in runs:
        if r["memory_mode"] == "TEXT_HISTORY" and r["seed"] < 2:
            r["outcome"] = {**r["outcome"], "success": False}  # fewer or equal iterations cannot help
        if r["memory_mode"] == "NO_MEMORY" and r["seed"] == 2:
            r["outcome"] = {**r["outcome"], "success": False}
    classes = analyze(runs, PRIVATE)["kinds"]["original"]["comparisons"]["TEXT_HISTORY"]["pair_classes"]
    assert (classes["negative"], classes["positive"]) == (2, 1)


def test_a_run_without_its_no_memory_pair_is_rejected():
    runs = [
        r
        for r in campaign(lambda s: True, lambda s: True)
        if (r["memory_mode"], r["seed"]) != ("NO_MEMORY", 0)
    ]
    with pytest.raises(ValueError, match="par sin NO_MEMORY"):
        analyze(runs, PRIVATE)
