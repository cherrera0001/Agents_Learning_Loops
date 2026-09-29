import math

import pytest

from associative_agent_loop.memory.associative import (
    Retriever,
    action_id,
    cosine_similarity,
    tokenize,
    topic_id,
)
from associative_agent_loop.memory.consolidation import Consolidator
from associative_agent_loop.memory.graph import EdgeType, MemoryGraph, NodeType


@pytest.fixture
def mg():
    return MemoryGraph(decay_rate=0.1)


def test_add_node_is_idempotent(mg):
    mg.add_node("action:x", NodeType.ACTION, "x")
    mg.tick()
    mg.add_node("action:x", NodeType.ACTION, "x", extra=1)
    assert len(mg) == 1
    assert mg.node("action:x").created_at == 0
    assert mg.node("action:x").last_accessed_at == 1
    assert mg.node("action:x").metadata["extra"] == 1


def test_parallel_edges_are_keyed_by_type(mg):
    mg.add_node("goal:1", NodeType.GOAL, "g")
    mg.add_node("action:x", NodeType.ACTION, "x")
    mg.add_edge("goal:1", "action:x", EdgeType.LEADS_TO, weight=0.5)
    mg.add_edge("goal:1", "action:x", EdgeType.RESOLVED_BY, weight=0.9)
    mg.add_edge("goal:1", "action:x", EdgeType.LEADS_TO, weight=0.1)  # no duplica ni pisa el peso
    assert mg.g.number_of_edges() == 2
    assert mg.edge("goal:1", "action:x", EdgeType.LEADS_TO).weight == 0.5
    with pytest.raises(KeyError):
        mg.add_edge("goal:1", "missing", EdgeType.LEADS_TO)


def test_recency_factor_decays_with_logical_clock(mg):
    mg.add_node("concept:a", NodeType.CONCEPT, "a")
    mg.add_node("concept:b", NodeType.CONCEPT, "b")
    mg.add_edge("concept:a", "concept:b", EdgeType.ASSOCIATED_WITH, weight=0.8)
    data = mg.edge("concept:a", "concept:b", EdgeType.ASSOCIATED_WITH)
    assert mg.recency_factor(data) == 1.0
    for _ in range(5):
        mg.tick()
    assert mg.recency_factor(data) == pytest.approx(math.exp(-0.5))
    assert mg.effective_weight(data) == pytest.approx(0.8 * math.exp(-0.5))


def test_serialization_roundtrip(mg, tmp_path):
    c = Consolidator(mg)
    goal = c.record_goal("clima en Santiago", 1)
    mg.add_node(action_id("tool"), NodeType.ACTION, "tool")
    c.reinforce(goal, action_id("tool"), EdgeType.RESOLVED_BY, 1.0)
    mg.tick()
    path = tmp_path / "mem.json"
    mg.save(path)
    loaded = MemoryGraph.load(path)
    assert loaded.clock == mg.clock
    assert loaded.stats() == mg.stats()
    assert loaded.edge(goal, action_id("tool"), EdgeType.RESOLVED_BY) == mg.edge(
        goal, action_id("tool"), EdgeType.RESOLVED_BY
    )


def test_reinforce_is_bounded_and_converges(mg):
    c = Consolidator(mg, learning_rate=0.5)
    mg.add_node("action:a", NodeType.ACTION, "a")
    mg.add_node("concept:e", NodeType.CONCEPT, "e")
    weights = [c.reinforce("action:a", "concept:e", EdgeType.FAILED_DUE_TO, 1.0) for _ in range(10)]
    assert weights == sorted(weights)
    assert 0.99 < weights[-1] <= 1.0
    w = c.reinforce("action:a", "concept:e", EdgeType.FAILED_DUE_TO, 0.0)
    assert w < weights[-1]


def test_prune_removes_stale_edges_and_orphans_but_keeps_goals(mg):
    c = Consolidator(mg, prune_threshold=0.05)
    c.record_goal("clima Santiago", 1)
    for _ in range(100):  # las aristas envejecen hasta caer bajo el umbral
        mg.tick()
    removed_edges, removed_nodes = c.prune()
    assert removed_edges == 2
    assert removed_nodes == 2  # los dos Concept topic
    assert mg.nodes_of_type(NodeType.GOAL) == ["goal:1"]


def test_tokenize_normalizes_accents_and_stopwords():
    assert tokenize("Pronóstico del CLIMA en Concepción") == ["pronostico", "clima", "concepcion"]
    assert cosine_similarity("clima en Santiago", "clima en Madrid") == pytest.approx(0.5)
    assert cosine_similarity("clima", "bolsa") == 0.0


def test_spreading_activation_reaches_actions_through_shared_topics(mg):
    c = Consolidator(mg)
    goal = c.record_goal("clima Santiago", 1)
    mg.add_node(action_id("weather"), NodeType.ACTION, "weather")
    c.reinforce(goal, action_id("weather"), EdgeType.RESOLVED_BY, 1.0)

    r = Retriever(mg)
    seeds = r.seed("clima Lima")
    assert topic_id("clima") in seeds
    activation = r.spread(seeds)
    assert activation[goal] > 0
    assert activation[action_id("weather")] > 0

    unrelated = r.retrieve("precio acciones bolsa", ["weather"])
    assert unrelated.activation == {}
    assert unrelated.score_of("weather") == 0.0
