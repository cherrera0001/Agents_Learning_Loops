"""Direct tests for typed-graph and consolidation guards of Experiment 1."""

import pytest
from pydantic import ValidationError

from experiments.evidence import publish, read_receipt
from experiments.memory import EvidenceMemory
from experiments.models import MemoryDocument
from experiments.runner import run_experiment


def node(node_id, kind="Task"):
    return {"id": node_id, "type": kind, "label": node_id}


def edge(source, target):
    return {"source": source, "target": target, "relation": "related_to"}


def document(nodes, edges):
    return {"schema_id": "software-learning-memory/v1", "nodes": nodes, "edges": edges}


def test_valid_graph_is_accepted():
    doc = MemoryDocument.model_validate(document([node("a"), node("b")], [edge("a", "b")]))
    assert len(doc.nodes) == 2 and len(doc.edges) == 1


@pytest.mark.parametrize(
    "edges",
    [[edge("a", "missing")], [edge("missing", "a")]],
    ids=["dangling-target", "dangling-source"],
)
def test_dangling_edge_is_rejected(edges):
    with pytest.raises(ValidationError, match="dangling edge"):
        MemoryDocument.model_validate(document([node("a")], edges))


def test_duplicate_node_ids_are_rejected():
    with pytest.raises(ValidationError, match="duplicate node ids"):
        MemoryDocument.model_validate(document([node("a"), node("a", "Lesson")], []))


@pytest.mark.parametrize("action", ["UPDATE", "MERGE", "DEPRECATE"])
def test_unsupported_memory_actions_fail_and_leave_memory_unchanged(action, tmp_path):
    original = read_receipt(run_experiment("EXP-01", memory_mode="ASSOCIATIVE_MEMORY", evidence_dir=tmp_path))
    memory = EvidenceMemory()
    assert memory.consolidate(publish(tmp_path, {**_unsealed(original), "run_id": "RUN-base"}))
    before_snapshot, before_fingerprint = memory.snapshot(), memory.fingerprint()

    record = _unsealed(original)
    record["run_id"] = "RUN-" + action.lower()
    record["reflection"]["memory_action"] = action
    with pytest.raises(NotImplementedError, match=action):
        memory.consolidate(publish(tmp_path, record))
    assert memory.snapshot() == before_snapshot
    assert memory.fingerprint() == before_fingerprint


def _unsealed(receipt):
    record = {k: v for k, v in receipt.items() if k != "receipt_sha256"}
    record["reflection"] = dict(record["reflection"])
    return record
