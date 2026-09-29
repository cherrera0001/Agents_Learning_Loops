"""Harness invariants, not a unit-test assertion that the scientific hypothesis wins."""

import json

import pytest
from pydantic import ValidationError

from experiments.agent import AgentView, BoundedRepairAgent
from experiments.evaluate import comparable, evaluate, semantic
from experiments.evidence import digest, publish, read_receipt
from experiments.memory import EvidenceMemory
from experiments.models import MemoryDocument, Reflection
from experiments.runner import (
    ROOT,
    app_files,
    execute_tests,
    load_task,
    prepare,
    run_experiment,
    update_memory,
)


def test_receipts_reject_overwrite_and_detect_tampering(tmp_path):
    path = publish(tmp_path, {"run_id": "RUN-test", "result": "FAIL"})
    original = path.read_bytes()
    with pytest.raises(FileExistsError):
        publish(tmp_path, {"run_id": "RUN-test", "result": "PASS"})
    assert path.read_bytes() == original
    data = json.loads(original)
    data["result"] = "PASS"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="integrity"):
        read_receipt(path)


@pytest.mark.parametrize("task_id", [f"EXP-{i:02d}" for i in range(1, 7)])
def test_each_defect_reproduces_and_original_app_passes(task_id, tmp_path):
    task = load_task(task_id)
    prepare(task, tmp_path)
    broken = execute_tests(tmp_path, 0)
    assert broken["returncode"] != 0
    metadata = json.loads((ROOT / "benchmark/private/tasks.json").read_text("utf-8"))[task_id]
    relative = metadata["mutation"]["path"]
    (tmp_path / relative).write_bytes((ROOT / "experiments/software_project" / relative).read_bytes())
    assert execute_tests(tmp_path, 1)["returncode"] == 0


def test_agent_boundary_excludes_private_data_and_future_tasks(tmp_path):
    task = load_task("EXP-01")
    prepare(task, tmp_path)
    names = [p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file()]
    assert all(n.startswith(("app/", "tests/")) for n in names)
    assert len([n for n in names if n.startswith("tests/")]) == 2
    view = AgentView(task.model_dump(), app_files(tmp_path), (), "NO_MEMORY", 7)
    serialized = json.dumps(view.__dict__)
    for forbidden in (
        "hidden_cause_id",
        "relevant_training_tasks",
        "golden_patch",
        "AUTH-01",
        "EXP-04",
    ):
        assert forbidden not in serialized


def test_prior_causal_experience_changes_future_strategy(tmp_path):
    agent = BoundedRepairAgent()
    baseline_path = run_experiment(
        "EXP-04", agent, "NO_MEMORY", 7, evidence_dir=tmp_path, batch_id="contract"
    )
    memory = EvidenceMemory()
    training = run_experiment(
        "EXP-01",
        agent,
        "ASSOCIATIVE_MEMORY",
        7,
        evidence_dir=tmp_path,
        batch_id="contract",
    )
    update_path = update_memory(memory, training, tmp_path)
    frozen = memory.fingerprint()
    treatment_path = run_experiment(
        "EXP-04",
        agent,
        "ASSOCIATIVE_MEMORY",
        7,
        memory=memory,
        evidence_dir=tmp_path,
        batch_id="contract",
    )
    baseline, treatment = read_receipt(baseline_path), read_receipt(treatment_path)
    assert comparable(baseline, treatment)
    assert [m["task"] for m in treatment["retrieval"]["memories"]] == ["EXP-01"]
    assert treatment["decision"]["influenced_by_memory"]
    assert treatment["decision"]["selected"] != baseline["decision"]["selected"]
    assert read_receipt(update_path)["memory_changes"][0]["action"] == "ADD"
    assert memory.fingerprint() == frozen  # transfer cannot train itself
    # Record the difference, deliberately no required improvement or success.
    report = evaluate(tmp_path)
    pair = next(p for p in report["comparisons"] if p["mode"] == "ASSOCIATIVE_MEMORY")
    assert pair["treatment_observations"]["iterations"] == treatment["iterations"]
    assert isinstance(pair["outcome_improved"], bool)


def test_cold_memory_matches_no_memory_and_replication(tmp_path):
    args = {"task": "EXP-06", "seed": 11, "evidence_dir": tmp_path}
    a = read_receipt(run_experiment(**args, memory_mode="NO_MEMORY", batch_id="a"))
    b = read_receipt(run_experiment(**args, memory_mode="ASSOCIATIVE_MEMORY", batch_id="a"))
    c = read_receipt(run_experiment(**args, memory_mode="NO_MEMORY", batch_id="b"))
    assert a["decision"] == b["decision"]
    assert a["outcome"] == b["outcome"]
    assert semantic(a) == semantic(c)
    assert a["run_id"] != c["run_id"]


def test_reflection_cannot_be_its_own_evidence():
    with pytest.raises(ValidationError):
        Reflection(
            goal="g",
            expected="e",
            observed="o",
            root_cause="guess",
            evidence=[],
            failed_strategy=[],
            successful_strategy="s",
            generalizable_rule="r",
            confidence=1,
            memory_action="ADD",
        )
    with pytest.raises(ValidationError):
        MemoryDocument.model_validate({"schema_id": "software-learning-memory/v999"})


def test_reject_fabricated_evidence_and_transfer_admission(tmp_path):
    path = run_experiment("EXP-01", memory_mode="ASSOCIATIVE_MEMORY", evidence_dir=tmp_path)
    record = read_receipt(path)
    record.pop("receipt_sha256")
    record["run_id"] = "RUN-forged"
    record["reflection"]["evidence"] = ["invented"]
    forged = publish(tmp_path, record)
    with pytest.raises(ValueError, match="missing evidence"):
        EvidenceMemory().consolidate(forged)
    record["run_id"] = "RUN-transfer"
    record["split"] = "transfer"
    with pytest.raises(ValueError, match="frozen"):
        EvidenceMemory().consolidate(publish(tmp_path, record))


def test_misleading_memory_and_budget_failure_are_retained(tmp_path):
    memory = EvidenceMemory()
    training = run_experiment("EXP-01", memory_mode="ASSOCIATIVE_MEMORY", evidence_dir=tmp_path)
    update_memory(memory, training, tmp_path)
    record = read_receipt(
        run_experiment(
            "EXP-05",
            memory_mode="TEXT_HISTORY",
            memory=memory,
            max_iterations=1,
            evidence_dir=tmp_path,
        )
    )
    assert record["retrieved_memories"]  # availability is not usefulness
    assert record["decision"]["memory_ids"]  # actually consulted
    assert record["result"] == "FAIL"  # the wrong causal strategy must not magically solve config
    assert record["tests"][-1]["returncode"] != 0
    assert record["reflection"]["memory_action"] == "IGNORE"


def test_agent_failure_seals_error_receipt(tmp_path):
    class BrokenAgent(BoundedRepairAgent):
        def plan(self, view):
            raise RuntimeError("controlled agent error")

    result = read_receipt(run_experiment("EXP-01", agent=BrokenAgent(), evidence_dir=tmp_path))
    assert result["result"] == "ERROR"
    assert result["error"]["message"] == "controlled agent error"
    with pytest.raises(ValueError, match="Harness ERROR"):
        evaluate(tmp_path)


def test_update_publication_failure_leaves_memory_unchanged(tmp_path, monkeypatch):
    from experiments import runner

    training = run_experiment("EXP-01", memory_mode="ASSOCIATIVE_MEMORY", evidence_dir=tmp_path)
    memory = EvidenceMemory()
    before = digest(memory.snapshot())

    def fail(*args):
        raise OSError("disk full")

    monkeypatch.setattr(runner, "publish", fail)
    with pytest.raises(OSError):
        update_memory(memory, training, tmp_path)
    assert memory.fingerprint() == before


def test_phase_table_rejects_skipping_retrieval():
    from experiments.runner import advance

    record = {"phases": ["ISSUE"]}
    with pytest.raises(ValueError, match="illegal"):
        advance(record, "CHANGE")
    advance(record, "RETRIEVE")
    advance(record, "INSPECT")


def test_evaluator_rejects_cross_condition_memory(tmp_path):
    train = run_experiment("EXP-01", memory_mode="ASSOCIATIVE_MEMORY", evidence_dir=tmp_path)
    memory = EvidenceMemory()
    update_memory(memory, train, tmp_path)
    # A caller passes associative-condition experiences into text history.
    # The solver cannot detect this; the controller/evaluator must reject it.
    run_experiment("EXP-04", memory_mode="TEXT_HISTORY", memory=memory, evidence_dir=tmp_path)
    with pytest.raises(ValueError, match="provenance/leakage"):
        evaluate(tmp_path)


def test_metric_arithmetic_on_actual_paired_runs(tmp_path):
    from experiments.evaluate import ratio

    baseline = read_receipt(run_experiment("EXP-04", memory_mode="NO_MEMORY", seed=7, evidence_dir=tmp_path))
    treatment = read_receipt(
        run_experiment("EXP-04", memory_mode="ASSOCIATIVE_MEMORY", seed=7, evidence_dir=tmp_path)
    )
    report = evaluate(tmp_path)
    a = report["metrics"]["NO_MEMORY"]
    c = report["metrics"]["ASSOCIATIVE_MEMORY"]
    assert a["TaskSuccessRate"] == int(baseline["result"] == "PASS")
    assert c["IterationsPerTask"] == treatment["iterations"]
    assert report["LearningGain"]["ASSOCIATIVE_MEMORY"]["IterationsPerTask"] == (
        treatment["iterations"] - baseline["iterations"]
    )
    assert c["MemoryUtilityRate"] is None
    assert ratio(2, 4) == 0.5 and ratio(0, 0) is None
