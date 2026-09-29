"""Contrato formal (#2): modelos Pydantic, JSON Schema generado y migración v1."""

import json

import jsonschema
import pytest
from pydantic import ValidationError

from associative_agent_loop.agent.core import Agent
from associative_agent_loop.agent.tools import weather_scenario
from associative_agent_loop.memory.graph import MemoryGraph, migrate_v1
from associative_agent_loop.memory.models import Edge, Node, NodeType, Relation
from scripts.export_schema import SCHEMA_PATH, build_schema


def test_edge_weight_is_bounded_on_creation_and_assignment():
    with pytest.raises(ValidationError):
        Edge(
            source="goal:1",
            target="action:x",
            relation=Relation.LEADS_TO,
            weight=1.5,
            decay_factor=0.05,
            last_updated=0,
        )
    mg = MemoryGraph()
    mg.add_node("goal:1", NodeType.GOAL, "g")
    mg.add_node("action:x", NodeType.ACTION, "x")
    edge = mg.add_edge("goal:1", "action:x", Relation.LEADS_TO)
    with pytest.raises(ValidationError):
        edge.weight = -0.1
    assert edge.weight == 0.5  # la asignación inválida no se aplicó


def test_invalid_relation_and_node_id_are_rejected():
    mg = MemoryGraph()
    mg.add_node("goal:1", NodeType.GOAL, "g")
    mg.add_node("action:x", NodeType.ACTION, "x")
    with pytest.raises(ValueError):
        mg.add_edge("goal:1", "action:x", "CAUSES")
    with pytest.raises(ValidationError):
        Node(id="sin-prefijo", type=NodeType.GOAL, label="x", created_at=0, last_accessed_at=0)
    with pytest.raises(ValidationError):
        Node(
            id="goal:1", type=NodeType.GOAL, label="x", created_at=0, last_accessed_at=0, activation_level=2.0
        )


def test_per_edge_decay_factor():
    mg = MemoryGraph(decay_rate=0.1)
    for n in ("concept:a", "concept:b", "concept:c"):
        mg.add_node(n, NodeType.CONCEPT, n)
    fast = mg.add_edge("concept:a", "concept:b", Relation.ASSOCIATED_WITH, weight=1.0)
    slow = mg.add_edge("concept:a", "concept:c", Relation.ASSOCIATED_WITH, weight=1.0, decay_factor=0.01)
    for _ in range(10):
        mg.tick()
    assert fast.decay_factor == 0.1
    assert mg.effective_weight(slow) > mg.effective_weight(fast)


def _trained_memory() -> MemoryGraph:
    agent = Agent(weather_scenario())
    for goal in ["clima en Santiago", "clima en Lima"]:
        agent.run(goal)
    return agent.memory


def test_serialized_graph_validates_against_generated_schema():
    schema = json.loads(SCHEMA_PATH.read_text("utf-8"))
    jsonschema.validate(_trained_memory().to_dict(), schema)


def test_roundtrip_is_identical():
    doc = _trained_memory().to_dict()
    assert MemoryGraph.from_dict(doc).to_dict() == doc


def test_committed_schema_is_in_sync_with_models():
    assert SCHEMA_PATH.read_text("utf-8") == build_schema(), (
        "specs/memory_schema.json desactualizado: python -m scripts.export_schema"
    )


V1_DOC = {
    "clock": 3,
    "decay_rate": 0.1,
    "nodes": [
        {"id": "goal:1", "type": "Goal", "label": "clima", "created_at": 1, "last_seen": 1, "episode": 1},
        {"id": "action:api", "type": "Action", "label": "api", "created_at": 1, "last_seen": 2},
        {
            "id": "outcome:1:0",
            "type": "Outcome",
            "label": "failure: 410",
            "created_at": 1,
            "last_seen": 1,
            "success": False,
            "latency_ms": 40,
            "error": "410",
            "episode": 1,
            "step": 0,
        },
    ],
    "edges": [
        {
            "source": "goal:1",
            "target": "action:api",
            "type": "LEADS_TO",
            "weight": 0.5,
            "last_updated": 1,
            "count": 0,
            "step": 0,
            "recency_factor": 0.82,
        },
        {
            "source": "action:api",
            "target": "outcome:1:0",
            "type": "LEADS_TO",
            "weight": 1.0,
            "last_updated": 1,
            "count": 0,
            "recency_factor": 0.82,
        },
    ],
}


def test_v1_documents_are_migrated_on_load():
    mg = MemoryGraph.from_dict(V1_DOC)
    assert mg.clock == 3
    outcome = mg.node("outcome:1:0")
    assert outcome.metadata == {"success": False, "latency_ms": 40, "error": "410", "episode": 1, "step": 0}
    assert mg.node("action:api").last_accessed_at == 2
    edge = mg.edge("goal:1", "action:api", Relation.LEADS_TO)
    assert edge.decay_factor == 0.1  # λ global v1 → decay_factor por arista
    assert edge.metadata == {"step": 0}
    assert migrate_v1(V1_DOC)["schema_version"] == 2
