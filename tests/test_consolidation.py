"""Consolidación hebbiana, decaimiento explícito y poda (#5)."""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.agent.tools import ToolResult
from src.memory.consolidation import Consolidator
from src.memory.graph import MemoryGraph, NodeType, Relation

OK = ToolResult(True, output="ok")
FAIL = ToolResult(False, error="HTTP 500")


def setup_context():
    """Tres metas pasadas resueltas con action:x (w = 0.5) y una meta actual."""
    mg = MemoryGraph(decay_rate=0.0)
    c = Consolidator(mg, hebbian_rate=0.3)
    mg.add_node("action:x", NodeType.ACTION, "x")
    for g in ("goal:old_a", "goal:old_b", "goal:old_c"):
        mg.add_node(g, NodeType.GOAL, g)
        mg.add_edge(g, "action:x", Relation.RESOLVED_BY, weight=0.5)
    goal = c.record_goal("tarea actual", mg.tick())
    activation = {"goal:old_a": 0.8, "goal:old_b": 0.2}  # old_c no fue recuperada
    return mg, c, goal, activation


def w(mg, src, rel=Relation.RESOLVED_BY, dst="action:x"):
    return mg.edge(src, dst, rel).weight


def test_success_potentiates_routes_in_proportion_to_coactivation():
    mg, c, goal, act = setup_context()
    c.record_step(goal, "x", OK, 1, 0)
    c.consolidate_episode(goal, [("x", OK)], activation=act)

    delta_a = w(mg, "goal:old_a") - 0.5
    delta_b = w(mg, "goal:old_b") - 0.5
    assert delta_a == pytest.approx(0.3 * 0.8 * (1 - 0.5))  # 0.12
    assert delta_b == pytest.approx(0.3 * 0.2 * (1 - 0.5))  # 0.03
    assert delta_a / delta_b == pytest.approx(0.8 / 0.2)     # ∝ a_i · a_j
    assert w(mg, "goal:old_c") == 0.5                        # sin co-activación, sin cambio
    # Ruta de la meta actual: LEADS_TO (0.5 al registrarse) potenciada con a = 1.
    assert w(mg, goal, Relation.LEADS_TO) == pytest.approx(0.5 + 0.3 * 0.5)


def test_failure_strengthens_cause_and_depresses_routes():
    mg, c, goal, act = setup_context()
    c.record_step(goal, "x", FAIL, 1, 0)
    c.consolidate_episode(goal, [("x", FAIL)], activation=act)

    assert w(mg, "action:x", Relation.FAILED_DUE_TO, "concept:error:http_500") > 0
    assert w(mg, goal, Relation.LEADS_TO) == pytest.approx(0.5 - 0.3 * 0.5)  # desacople
    assert w(mg, "goal:old_a") == pytest.approx(0.5 - 0.3 * 0.8 * 0.5)
    assert w(mg, "goal:old_b") == pytest.approx(0.5 - 0.3 * 0.2 * 0.5)
    assert w(mg, "goal:old_c") == 0.5


def test_hebbian_step_does_not_touch_the_lesson_that_warned_about_the_failure():
    mg, c, goal, act = setup_context()
    c.record_step(goal, "x", FAIL, 1, 0)
    c.consolidate_episode(goal, [("x", FAIL)], activation=act)
    lesson = "concept:lesson:avoid:x:http_500"
    lesson_before = w(mg, lesson, Relation.ASSOCIATED_WITH)
    route_before = w(mg, "goal:old_a")

    # Solo el paso hebbiano (sin el refuerzo EMA posterior, que ocultaría el efecto).
    goal2 = c.record_goal("otra tarea", mg.tick())
    c._hebbian_step(goal2, "action:x", {lesson: 1.0, "goal:old_a": 1.0}, reward=-1)
    assert w(mg, lesson, Relation.ASSOCIATED_WITH) == lesson_before  # ASSOCIATED_WITH intacta
    assert w(mg, "goal:old_a") < route_before  # control: la ruta sí se deprimió


@settings(max_examples=30, deadline=None)
@given(
    st.lists(
        st.tuples(
            st.sampled_from(["a", "b", "c"]),
            st.booleans(),
            st.floats(min_value=0.0, max_value=1.0),
        ),
        min_size=1,
        max_size=25,
    )
)
def test_weights_stay_bounded_for_any_episode_sequence(episodes):
    mg = MemoryGraph()
    c = Consolidator(mg, learning_rate=0.9, penalty_rate=0.9, hebbian_rate=1.0)
    for i, (tool, success, a) in enumerate(episodes):
        goal = c.record_goal(f"tarea {tool}", mg.tick())
        result = OK if success else FAIL
        c.record_step(goal, tool, result, i, 0)
        activation = {n.id: a for n in mg.nodes()}
        c.consolidate_episode(goal, [(tool, result)], activation=activation)
    for edge in mg.edges():
        assert 0.0 <= edge.weight <= 1.0
        assert 0.0 <= mg.effective_weight(edge) <= 1.0


def test_explicit_decay_is_equivalent_to_lazy_effective_weight():
    mg = MemoryGraph(decay_rate=0.1)
    c = Consolidator(mg)
    goal = c.record_goal("clima Santiago", mg.tick())
    c.record_step(goal, "api", OK, 1, 0)
    c.consolidate_episode(goal, [("api", OK)])
    for _ in range(7):
        mg.tick()
    lazy = {(e.source, e.target, e.relation): mg.effective_weight(e) for e in mg.edges()}
    assert c.decay() == len(lazy)
    for e in mg.edges():
        assert e.weight == pytest.approx(lazy[(e.source, e.target, e.relation)])
        assert mg.recency_factor(e) == 1.0
    assert c.decay() == 0  # idempotente en el mismo tick


def test_prune_respects_max_edges_keeping_the_strongest():
    mg = MemoryGraph(decay_rate=0.0)
    c = Consolidator(mg, max_edges=3)
    mg.add_node("concept:hub", NodeType.CONCEPT, "hub")
    for i, weight in enumerate([0.9, 0.1, 0.5, 0.7, 0.3]):
        mg.add_node(f"concept:n{i}", NodeType.CONCEPT, f"n{i}")
        mg.add_edge("concept:hub", f"concept:n{i}", Relation.ASSOCIATED_WITH, weight=weight)
    removed_edges, removed_nodes = c.prune()
    assert removed_edges == 2 and removed_nodes == 2
    assert sorted(e.weight for e in mg.edges()) == [0.5, 0.7, 0.9]
