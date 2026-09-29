"""El verificador independiente debe poder fallar: se prueba con recibos sintéticos."""

import copy
import json

from scripts.verify_experiment1 import (
    check_integrity,
    check_leakage,
    receipt_hash,
    recompute_metrics,
)

PRIVATE = {
    "EXP-01": {"hidden_cause_id": "AUTH-01", "relevant_training_tasks": [], "split": "train"},
    "EXP-04": {"hidden_cause_id": "AUTH-01", "relevant_training_tasks": ["EXP-01"], "split": "transfer"},
}


def run(run_id, task, split, mode, *, selected="s1", without="s0", ok_first=True, memories=(), iterations=1):
    r = {
        "kind": "task_run",
        "run_id": run_id,
        "batch_id": "B",
        "seed": 1,
        "split": split,
        "memory_mode": mode,
        "task": {"id": task, "title": "t"},
        "memory_input": None,
        "initial_source": {"app/x.py": "pass\n"},
        "retrieval": {"memories": [{"id": f"lesson:{m}", "task": "EXP-01"} for m in memories]},
        "decision": {
            "memory_ids": [f"lesson:{m}" for m in memories],
            "selected": selected,
            "without_memory": without,
        },
        "outcome": {"success": True, "first_attempt_success": ok_first, "iterations": iterations},
    }
    r["receipt_sha256"] = receipt_hash(r)
    return r


def receipts():
    train = run("RUN-train", "EXP-01", "train", "ASSOCIATIVE_MEMORY")
    base = run("RUN-base", "EXP-04", "transfer", "NO_MEMORY", selected="s0", ok_first=False, iterations=2)
    mem = run("RUN-mem", "EXP-04", "transfer", "ASSOCIATIVE_MEMORY", memories=["RUN-train"])
    return {f"{r['run_id']}.json": r for r in (train, base, mem)}


def public_dir(tmp_path):
    for task in PRIVATE:
        (tmp_path / f"{task}.json").write_text(json.dumps({"id": task, "title": "t"}), "utf-8")
    return tmp_path


def test_integrity_passes_and_detects_tampering():
    rs = receipts()
    ok = check_integrity(rs, None)
    assert ok["hash_failures"] == [] and ok["tamper_detected"]

    tampered = copy.deepcopy(rs)
    tampered["RUN-mem.json"]["outcome"]["success"] = False  # sin recalcular el hash
    assert check_integrity(tampered, None)["hash_failures"] == ["RUN-mem.json"]


def test_leakage_detects_private_labels_and_frozen_memory_violations(tmp_path):
    pub = public_dir(tmp_path)
    assert all(v == [] for v in check_leakage(receipts(), PRIVATE, pub).values())

    leaked = receipts()
    leaked["RUN-mem.json"]["task"]["hint"] = "la causa es AUTH-01"
    result = check_leakage(leaked, PRIVATE, pub)
    assert any("AUTH-01" in x for x in result["solver_context_leaks"])
    assert any("no públicos" in x for x in result["solver_context_leaks"])

    from_transfer = receipts()
    from_transfer["RUN-u.json"] = {
        "kind": "memory_update",
        "run_id": "RUN-u",
        "source_receipt": "RUN-base.json",
    }
    assert check_leakage(from_transfer, PRIVATE, pub)["memory_updates_from_transfer"] == ["RUN-u"]


def test_metrics_follow_protocol_definitions():
    m = recompute_metrics(receipts(), PRIVATE)
    assert m["NO_MEMORY"]["IterationsPerTask"] == 2
    assert m["NO_MEMORY"]["MemoryRetrievalPrecision"] is None  # denominador indefinido → null
    assoc = m["ASSOCIATIVE_MEMORY"]
    assert assoc["MemoryRetrievalPrecision"] == 1.0
    assert assoc["MemoryUseRate"] == 1.0
    assert assoc["MemoryUtilityRate"] == 1.0  # cambió la decisión y redujo iteraciones frente al par
