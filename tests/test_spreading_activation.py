"""Activación propagada (#4) con valores calculados a mano.

Todas las aristas usan decay_factor = 0 (recency = 1) y peso 1 salvo que se
indique, así que cada salto multiplica exactamente por δ = 0.7 / norm(grado).
"""

import pytest
from pydantic import ValidationError

from scripts.devlog import load_episodes, rebuild
from associative_agent_loop.agent.core import Agent
from associative_agent_loop.agent.tools import weather_scenario
from associative_agent_loop.memory.associative import RetrievalConfig, Retriever
from associative_agent_loop.memory.graph import MemoryGraph, NodeType, Relation


def graph(*edges, weight=1.0):
    """Grafo de Concepts con aristas ASSOCIATED_WITH (ρ = 1 hacia atrás)."""
    mg = MemoryGraph(decay_rate=0.0)
    for src, dst in edges:
        for n in (src, dst):
            mg.add_node(f"concept:{n}", NodeType.CONCEPT, n)
        mg.add_edge(f"concept:{src}", f"concept:{dst}", Relation.ASSOCIATED_WITH, weight=weight)
    return mg


def spread(mg, seeds, **cfg):
    config = RetrievalConfig(**{"fan_out": "none", **cfg})
    act = Retriever(mg, config=config).spread({f"concept:{k}": v for k, v in seeds.items()})
    return {k.removeprefix("concept:"): v for k, v in act.items()}


def test_damping_per_hop_on_a_chain():
    mg = graph(("a", "b"), ("b", "c"), ("c", "d"))
    assert spread(mg, {"a": 1.0}) == pytest.approx({"a": 1.0, "b": 0.7, "c": 0.49, "d": 0.343})


@pytest.mark.parametrize(
    "hops, expected",
    [(0, {"a": 1.0}), (1, {"a": 1.0, "b": 0.7}), (2, {"a": 1.0, "b": 0.7, "c": 0.49})],
)
def test_max_hops_limits_propagation(hops, expected):
    mg = graph(("a", "b"), ("b", "c"), ("c", "d"))
    assert spread(mg, {"a": 1.0}, max_hops=hops) == pytest.approx(expected)


def test_firing_threshold_drops_weak_nodes():
    mg = graph(("a", "b"), ("b", "c"), ("c", "d"))
    assert spread(mg, {"a": 1.0}, firing_threshold=0.4) == pytest.approx(
        {"a": 1.0, "b": 0.7, "c": 0.49}
    )


def test_threshold_applies_to_accumulated_activation_not_to_each_increment():
    w = 0.006 / 0.7  # cada fuente aporta 0.006 < θ = 0.01
    mg = graph(("s1", "x"), ("s2", "x"), weight=w)
    both = spread(mg, {"s1": 1.0, "s2": 1.0}, max_hops=1)
    assert both["x"] == pytest.approx(0.012)  # 0.006 + 0.006 ≥ θ: dispara
    one = spread(mg, {"s1": 1.0}, max_hops=1)
    assert "x" not in one  # 0.006 < θ


def test_refraction_prevents_cycles_from_inflating_activation():
    chain = spread(graph(("a", "b"), ("b", "c")), {"a": 1.0})
    cycle = spread(graph(("a", "b"), ("b", "c"), ("c", "a")), {"a": 1.0})
    # Sin refracción, b y c devolverían activación a 'a' y se reforzarían entre sí.
    assert cycle["a"] == 1.0
    assert cycle["b"] == pytest.approx(chain["b"])
    assert cycle["c"] == pytest.approx(0.7)  # vecino directo de 'a' por la arista c→a
    assert all(v <= 1.0 for v in cycle.values())


@pytest.mark.parametrize("mode, norm", [("none", 1), ("sqrt", 2), ("linear", 4)])
def test_fan_out_normalization_on_a_hub(mode, norm):
    mg = graph(*[("hub", f"s{i}") for i in range(4)])
    act = spread(mg, {"hub": 1.0}, fan_out=mode, max_hops=1)
    for i in range(4):
        assert act[f"s{i}"] == pytest.approx(0.7 / norm)


def test_config_is_validated():
    with pytest.raises(ValidationError):
        RetrievalConfig(damping=0.0)
    with pytest.raises(ValidationError):
        RetrievalConfig(fan_out="log")


def test_retrieve_persists_activation_and_explains_paths():
    agent = Agent(weather_scenario())
    agent.run("clima en Santiago")
    mg = agent.memory
    mg.tick()
    result = Retriever(mg).retrieve("clima en Lima", ["weather_api_v1", "weather_api_v2"])

    for node in mg.nodes():
        assert node.activation_level == pytest.approx(result.activation.get(node.id, 0.0))
        if node.id in result.activation:
            assert node.last_accessed_at == mg.clock

    best = result.ranked_actions[0]
    assert best.action == "weather_api_v2"
    # La meta pasada es semilla (sim("clima en Lima", "clima en Santiago") = 0.5) y
    # resolvió directamente con v2: ese es el camino de mayor aporte.
    assert best.path == ["goal:1", "action:weather_api_v2"]


def test_dev_memory_relevance_is_discriminative():
    """Regresión del dogfooding: en la memoria real la relevancia estaba saturada en 1.0."""
    mg = rebuild(load_episodes())
    actions = [mg.node(n).label for n in mg.nodes_of_type(NodeType.ACTION)]
    result = Retriever(mg).retrieve(
        "Registrar el desarrollo del repo como episodios en la memoria asociativa", actions
    )
    relevances = [s.relevance for s in result.ranked_actions if s.relevance > 0]
    assert len(relevances) >= 3
    assert max(relevances) < 1.0
    assert len({round(r, 3) for r in relevances}) > 1
