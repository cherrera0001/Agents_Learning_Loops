"""Propiedades (hypothesis) de la memoria asociativa (#7).

Cada propiedad se verificó contra una mutación del código que debe romperla
(ver el episodio 013 en learning/episodes): no son tests tautológicos.
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from associative_agent_loop.agent.tools import ToolResult
from associative_agent_loop.memory.associative import RetrievalConfig, Retriever
from associative_agent_loop.memory.consolidation import Consolidator
from associative_agent_loop.memory.graph import MemoryGraph, NodeType, Relation

names = st.from_regex(r"[a-z]{1,8}", fullmatch=True)
unit = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)
# Sesgado hacia 1.0: los casos límite (varias semillas fuertes hacia el mismo nodo)
# son los que rompen la saturación; con floats uniformes casi no aparecen.
strong = st.one_of(st.just(1.0), st.floats(min_value=0.8, max_value=1.0), unit)
PROPS = settings(max_examples=40, deadline=None)


@PROPS
@given(st.lists(names, min_size=1, max_size=6, unique=True), st.text(max_size=40))
def test_empty_memory_preserves_candidate_order(tools, query):
    """Invariante 4: sin experiencia, el ranking respeta el orden del PLAN."""
    result = Retriever(MemoryGraph()).retrieve(query, tools)
    assert [s.action for s in result.ranked_actions] == tools
    assert all(s.score == 0 for s in result.ranked_actions)


@st.composite
def random_graphs(draw):
    n = draw(st.integers(min_value=2, max_value=8))
    mg = MemoryGraph(decay_rate=draw(st.sampled_from([0.0, 0.05, 0.3])))
    nodes = [f"concept:n{i}" for i in range(n)]
    for node in nodes:
        mg.add_node(node, NodeType.CONCEPT, node)
    for _ in range(draw(st.integers(min_value=1, max_value=20))):
        src, dst = draw(st.sampled_from(nodes)), draw(st.sampled_from(nodes))
        if src != dst:
            relation = draw(st.sampled_from(list(Relation)))
            mg.add_edge(src, dst, relation, weight=draw(strong))
    for _ in range(draw(st.integers(min_value=0, max_value=5))):
        mg.tick()
    seeds = draw(st.dictionaries(st.sampled_from(nodes), strong, min_size=1, max_size=4))
    return mg, seeds


@settings(max_examples=150, deadline=None)
@given(random_graphs(), st.sampled_from(["none", "sqrt", "linear"]))
def test_activation_is_bounded_and_respects_threshold(graph_and_seeds, fan_out):
    mg, seeds = graph_and_seeds
    cfg = RetrievalConfig(fan_out=fan_out, damping=1.0)  # δ = 1: el peor caso para la saturación
    activation = Retriever(mg, config=cfg).spread(seeds)
    for node, a in activation.items():
        assert cfg.firing_threshold <= a <= 1.0
        if node in seeds:
            assert a >= min(1.0, seeds[node])  # propagar nunca resta activación


@PROPS
@given(random_graphs())
def test_effective_weight_never_increases_with_time(graph_and_seeds):
    mg, _ = graph_and_seeds
    before = {(e.source, e.target, e.relation): mg.effective_weight(e) for e in mg.edges()}
    mg.tick()
    for e in mg.edges():
        assert mg.effective_weight(e) <= before[(e.source, e.target, e.relation)] + 1e-12


episodes = st.lists(
    st.tuples(st.sampled_from(["api_a", "api_b", "api_c"]), st.booleans(), names),
    min_size=1,
    max_size=12,
)


def build(history) -> MemoryGraph:
    mg = MemoryGraph()
    c = Consolidator(mg)
    for i, (tool, ok, topic) in enumerate(history):
        goal = c.record_goal(f"tarea {topic}", mg.tick())
        result = ToolResult(True, output="ok") if ok else ToolResult(False, error=f"error {tool}")
        c.record_step(goal, tool, result, i, 0)
        c.consolidate_episode(goal, [(tool, result)], activation={goal: 1.0})
    return mg


@PROPS
@given(episodes)
def test_serialization_roundtrip_for_any_history(history):
    mg = build(history)
    Retriever(mg).index()  # incluye embeddings en el documento
    doc = mg.to_dict()
    assert MemoryGraph.from_dict(doc).to_dict() == doc


@PROPS
@given(episodes, st.dictionaries(st.integers(min_value=1, max_value=12), unit, max_size=6))
def test_contextual_valence_is_bounded(history, goal_activation):
    mg = build(history)
    retriever = Retriever(mg)
    activation = {f"goal:{k}": a for k, a in goal_activation.items()}
    for action in mg.nodes_of_type(NodeType.ACTION):
        assert -1.0 <= retriever.valence(action, activation) <= 1.0
