"""Diagnostic baseline (#58) wiring: runner order, receipts, evaluator guards and CLI.

These tests run real tasks only to check structure (order, keys, replay,
identity across conditions, rejection of tampering). None of them asserts
which diagnosis a real task receives, and none requires a positive gain.
"""

import copy
import itertools
import json
import sys

import pytest

from experiments import __main__ as cli
from experiments import runner
from experiments.agent import STRATEGIES, BoundedRepairAgent, prior_order
from experiments.benchmark import DIAGNOSTIC_CAMPAIGN, REFERENCE_CAMPAIGN, TASK_SETS
from experiments.diagnostic import DiagnosticRepairAgent, diagnose, replay_decision
from experiments.evaluate import evaluate
from experiments.evidence import digest, publish, read_receipt
from experiments.memory import EvidenceMemory
from experiments.runner import ROOT, run_experiment, update_memory

DEFAULT_KEYS = {
    "considered",
    "selected",
    "plan",
    "without_memory",
    "influenced_by_memory",
    "memory_ids",
    "initial_hypothesis",
}
MODES = ("NO_MEMORY", "TEXT_HISTORY", "ASSOCIATIVE_MEMORY")
INJECTED = (
    "=" * 70
    + "\nERROR: test_x (m.K)\n"
    + "-" * 70
    + '\nTraceback (most recent call last):\n  File "<workspace>/x.py", line 1, in f\n    g()\n'
    + "tamper.Injected: not produced by any task\n\n"
)


def logged_execute_tests(monkeypatch, log):
    real = runner.execute_tests

    def execute(workspace, index, timeout=20):
        log.append(index)
        return real(workspace, index, timeout)

    monkeypatch.setattr(runner, "execute_tests", execute)


def test_default_path_keeps_its_order_keys_and_context(tmp_path, monkeypatch):
    log = []
    logged_execute_tests(monkeypatch, log)

    class Spy(BoundedRepairAgent):
        def plan(self, view):
            log.append("plan")
            return super().plan(view)

    receipt = read_receipt(run_experiment("EXP-01", Spy(), "NO_MEMORY", 7, evidence_dir=tmp_path))
    assert log[:2] == ["plan", 0]  # historical order: decide, then reproduce
    assert receipt["agent"] == "bounded-ast-repair-v1"
    assert set(receipt["decision"]) == DEFAULT_KEYS
    assert "decision_inputs" not in receipt
    assert receipt["agent_context_sha256"] == digest(
        {"task": receipt["task"], "files": receipt["initial_source"], "memories": []}
    )


def test_diagnostic_agent_decides_once_after_the_public_reproduction(tmp_path, monkeypatch):
    log, seen = [], []
    logged_execute_tests(monkeypatch, log)

    class Spy(DiagnosticRepairAgent):
        def plan(self, view):
            log.append("plan")
            seen.append(view.reproduction)
            return super().plan(view)

    receipt = read_receipt(run_experiment("EXP-01", Spy(), "NO_MEMORY", 7, evidence_dir=tmp_path))
    assert log[:2] == [0, "plan"] and log.count("plan") == 1 and log.count(0) == 1
    reproduction = receipt["tests"][0]
    assert seen == [{"returncode": reproduction["returncode"], "stderr": reproduction["stderr"]}]
    assert receipt["decision_inputs"] == {"order": ["RETRIEVE", "test-0", "plan"], "reproduction": "test-0"}
    assert receipt["agent"] == DIAGNOSTIC_CAMPAIGN["agent"] == DiagnosticRepairAgent.name
    assert set(receipt["decision"]) > DEFAULT_KEYS
    assert receipt["decision"]["plan"] in [list(p) for p in itertools.permutations(STRATEGIES)]
    assert replay_decision(receipt) == receipt["decision"]
    # Later test output cannot reach the decision; the reproduction does.
    later = copy.deepcopy(receipt)
    for test in later["tests"][1:]:
        test["stderr"], test["returncode"] = INJECTED, 1
    assert replay_decision(later) == receipt["decision"]
    earlier = copy.deepcopy(receipt)
    earlier["tests"][0]["stderr"] = INJECTED
    assert replay_decision(earlier)["diagnostic"] == diagnose(INJECTED)


@pytest.fixture(scope="module")
def cell(tmp_path_factory):
    """One seed, one batch: training EXP-01 then transfer EXP-04, in the three conditions."""
    evidence = tmp_path_factory.mktemp("diagnostic-cell")
    for mode in MODES:
        memory = EvidenceMemory()
        for task in ("EXP-01", "EXP-04"):
            path = run_experiment(
                task, DiagnosticRepairAgent(), mode, 7, memory=memory, evidence_dir=evidence, batch_id="cell"
            )
            if task == "EXP-01" and mode != "NO_MEMORY":
                update_memory(memory, path, evidence)
    return evidence


def test_evaluator_accepts_a_consistent_diagnostic_campaign(cell):
    report = evaluate(cell)
    assert {p["mode"] for p in report["comparisons"]} == set(MODES)  # the evaluator also pairs A with itself
    runs = [read_receipt(p) for p in cell.glob("RUN-*.json")]
    runs = [r for r in runs if r["kind"] == "task_run"]
    for task in ("EXP-01", "EXP-04"):
        diagnoses = {json.dumps(r["decision"]["diagnostic"]) for r in runs if r["task"]["id"] == task}
        assert len(diagnoses) == 1  # A, B and C received the same diagnosis


def resealed(cell, target, change):
    """Copy a campaign, altering the EXP-04 TEXT_HISTORY receipt and resealing it as a
    privileged author could: hashes alone cannot detect this, the replay must."""
    target.mkdir()
    for path in cell.glob("RUN-*.json"):
        record = read_receipt(path)
        record.pop("receipt_sha256")
        if record["kind"] == "task_run" and (record["task"]["id"], record["memory_mode"]) == (
            "EXP-04",
            "TEXT_HISTORY",
        ):
            change(record)
        publish(target, record)
    return target


def test_evaluator_rejects_a_decision_that_does_not_replay(cell, tmp_path):
    def reverse_plan(record):
        record["decision"]["plan"] = list(reversed(record["decision"]["plan"]))

    def tamper_status(record):
        record["decision"]["diagnostic"]["status"] = "tampered"

    def tamper_reproduction(record):
        record["tests"][0]["stderr"] = INJECTED

    for name, change in (("plan", reverse_plan), ("status", tamper_status), ("repro", tamper_reproduction)):
        with pytest.raises(ValueError, match="does not replay"):
            evaluate(resealed(cell, tmp_path / name, change))


def test_evaluator_rejects_different_diagnoses_within_one_cell(cell, tmp_path):
    def consistent_but_different(record):
        record["tests"][0]["stderr"] = INJECTED
        record["decision"] = replay_decision(record)

    with pytest.raises(ValueError, match="different diagnoses"):
        evaluate(resealed(cell, tmp_path / "cell", consistent_but_different))


def test_evaluator_requires_the_recorded_prior_reproduction(cell, tmp_path):
    with pytest.raises(ValueError, match="prior reproduction"):
        evaluate(resealed(cell, tmp_path / "order", lambda record: record.pop("decision_inputs")))


def test_evaluator_rejects_mixed_agents_or_policies(cell, tmp_path):
    mixed = resealed(cell, tmp_path / "mixed", lambda record: None)
    run_experiment("EXP-01", BoundedRepairAgent(), "NO_MEMORY", 7, evidence_dir=mixed, batch_id="other")
    with pytest.raises(ValueError, match="mix of agents or decision policies"):
        evaluate(mixed)


def test_published_reference_v2_evaluation_is_unchanged():
    published = json.loads((ROOT / "results/reference-v2/experiment1.json").read_text("utf-8"))
    assert evaluate(ROOT / "evidence/reference-v2") == published


def test_diagnostic_campaign_is_the_reference_design_with_the_opt_in_agent():
    assert DIAGNOSTIC_CAMPAIGN["agent"] == DiagnosticRepairAgent.name
    assert DIAGNOSTIC_CAMPAIGN["seeds"] == REFERENCE_CAMPAIGN["seeds"]
    assert {prior_order(s) for s in DIAGNOSTIC_CAMPAIGN["seeds"]} == set(itertools.permutations(STRATEGIES))
    assert (DIAGNOSTIC_CAMPAIGN["replicates"], DIAGNOSTIC_CAMPAIGN["task_set"]) == (2, "misleading-v1")
    assert DIAGNOSTIC_CAMPAIGN["evidence_dir"] not in ("evidence/runs", "evidence/reference-v2")


def test_cli_diagnostic_campaign_fixes_configuration_agent_and_directory(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "campaign", lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setattr(sys, "argv", ["experiments", "run", "--campaign", "diagnostic-baseline-v1"])
    cli.main()
    (seeds, replicates, evidence_dir, tasks), kwargs = calls[0]
    assert (seeds, replicates, tasks) == ([1, 4, 5, 6, 7, 9], 2, TASK_SETS["misleading-v1"])
    assert evidence_dir == ROOT / "evidence/diagnostic-baseline-v1"
    assert kwargs == {"agent_factory": DiagnosticRepairAgent}
    monkeypatch.setattr(
        sys, "argv", ["experiments", "run", "--campaign", "diagnostic-baseline-v1", "--replicates", "1"]
    )
    with pytest.raises(SystemExit):
        cli.main()
    # Other recipes keep the historical default directory and the default agent.
    calls.clear()
    monkeypatch.setattr(sys, "argv", ["experiments", "run", "--campaign", "reference-v2"])
    cli.main()
    assert calls[0] == (
        (list(REFERENCE_CAMPAIGN["seeds"]), 2, ROOT / "evidence/runs", TASK_SETS["misleading-v1"]),
        {},
    )
