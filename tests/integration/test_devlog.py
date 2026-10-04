"""La bitácora del repo es a su vez una memoria asociativa: se prueba como tal."""

import json

import pytest

from associative_agent_loop.memory.graph import EdgeType, NodeType
from scripts.devlog import EPISODES_DIR, load_episodes, rebuild, recall

EPISODES = [
    {
        "seq": 1,
        "id": "a",
        "goal": "agregar dependencia pydantic",
        "steps": [
            {"action": "run_tests", "success": False, "error": "ImportError pydantic"},
            {"action": "add_dependency", "success": True},
            {"action": "run_tests", "success": True},
        ],
        "lessons": ["Instalar el extra dev antes de correr los tests"],
    },
    {
        "seq": 2,
        "id": "b",
        "goal": "agregar dependencia fastembed opcional",
        "steps": [{"action": "add_dependency", "success": True}],
    },
]


def test_rebuild_is_deterministic_and_order_independent():
    def dump(eps):
        return json.dumps(rebuild(eps).to_dict(), sort_keys=True)

    assert dump(EPISODES) == dump(EPISODES)
    assert dump(EPISODES) == dump(list(reversed(EPISODES)))  # se ordena por seq


def test_rebuild_maps_episode_to_graph():
    mg = rebuild(EPISODES)
    assert mg.stats()[NodeType.GOAL.value] == 2
    assert mg.has_edge("action:run_tests", "concept:error:importerror_pydantic", EdgeType.FAILED_DUE_TO)
    assert mg.node("goal:1").metadata["ref"] == "a"
    lessons = [n.label for n in mg.nodes() if n.metadata.get("kind") == "lesson"]
    assert "Instalar el extra dev antes de correr los tests" in lessons


ESTIMATE = {
    "version": 1,
    "date": "2026-10-02",
    "size": "S",
    "points": 2,
    "uncertainty": 2,
    "risk": 1,
    "planned_model": "Sonnet 5.5",
    "planned_effort": "medium",
}
OUTCOME = {
    "used_model": "Sonnet 5.5",
    "model_source": "self-reported",
    "escalated": False,
    "estimate_revisions": 0,
    "prs": 1,
}


def _dump(episodes):
    return json.dumps(rebuild(episodes).to_dict(), sort_keys=True)


def _dump_without_board(episodes):
    """El grafo sin el registro del tablero que #122 añade a la metadata de cada `Goal`."""
    data = rebuild(episodes).to_dict()
    for node in data["nodes"]:
        node.get("metadata", {}).pop("board", None)
    return json.dumps(data, sort_keys=True)


def test_estimate_and_outcome_blocks_only_change_the_board_record_of_the_goal():
    """Desde #122 `estimate` y `outcome` van en `metadata["board"]` del `Goal`, y en ningún otro sitio.

    No crean nodos ni aristas, no cambian pesos y no cambian lo que `recall` recupera.
    """
    annotated = [dict(ep, estimate=ESTIMATE, outcome=OUTCOME) for ep in EPISODES]
    assert annotated != EPISODES  # los episodios de entrada sí difieren
    assert _dump(annotated) != _dump(EPISODES)  # control: el registro del tablero sí entra en el grafo
    assert _dump_without_board(annotated) == _dump_without_board(EPISODES)
    # un episodio con los bloques y otro sin ellos conviven en el mismo historial
    mixed = [dict(EPISODES[0], estimate=ESTIMATE, outcome=OUTCOME), EPISODES[1]]
    assert _dump_without_board(mixed) == _dump_without_board(EPISODES)
    # la recuperación (acciones y lecciones) no depende de esos bloques
    query, cut = "agregar dependencia hypothesis", "Issues parecidos"
    assert recall(rebuild(annotated), query).split(cut)[0] == recall(rebuild(EPISODES), query).split(cut)[0]


def test_changing_a_step_does_change_the_graph():
    """Control: si `rebuild` ignorara todo, la prueba anterior sería tautológica."""
    changed = [dict(EPISODES[0], steps=EPISODES[0]["steps"][:-1]), EPISODES[1]]
    assert _dump(changed) != _dump(EPISODES)


def test_recall_returns_related_lessons_and_actions():
    out = recall(rebuild(EPISODES), "agregar dependencia hypothesis")
    assert "add_dependency" in out
    assert "Instalar el extra dev antes de correr los tests" in out
    assert "(sin experiencia relacionada)" in recall(rebuild(EPISODES), "xyz")


OPTIONAL_OUTCOME_KEYS = {"transcript"}


def check_episode(ep):
    """Validación de un episodio; `outcome.transcript` es opcional y cualquier otra clave sobra."""
    assert ep["goal"] and ep["steps"]
    assert all({"action", "success"} <= set(s) for s in ep["steps"])
    if "estimate" in ep:
        assert set(ep["estimate"]) == set(ESTIMATE)
    if "outcome" in ep:
        keys = set(ep["outcome"])
        assert set(OUTCOME) <= keys, f"faltan claves en outcome: {set(OUTCOME) - keys}"
        assert keys <= set(OUTCOME) | OPTIONAL_OUTCOME_KEYS, f"claves desconocidas: {keys - set(OUTCOME)}"
        assert ep["outcome"]["model_source"] in {"self-reported", "transcript"}
        if "transcript" in keys:
            assert isinstance(ep["outcome"]["transcript"], str) and ep["outcome"]["transcript"]


def test_committed_episodes_are_valid_and_ordered():
    episodes = load_episodes(EPISODES_DIR)
    assert episodes, "debe existir al menos el episodio retroactivo v0.1"
    seqs = [e["seq"] for e in episodes]
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)
    for ep in episodes:
        check_episode(ep)


def test_outcome_transcript_is_optional_but_other_keys_are_rejected():
    base = dict(EPISODES[0], estimate=ESTIMATE)
    check_episode(dict(base, outcome=OUTCOME))  # sin transcript
    check_episode(dict(base, outcome=dict(OUTCOME, transcript="agent-x.jsonl")))  # con transcript
    with pytest.raises(AssertionError, match="claves desconocidas"):
        check_episode(dict(base, outcome=dict(OUTCOME, transcripts="agent-x.jsonl")))
    with pytest.raises(AssertionError, match="claves desconocidas"):
        check_episode(dict(base, outcome=dict(OUTCOME, transcript="a.jsonl", extra=1)))
    with pytest.raises(AssertionError, match="faltan claves"):
        check_episode(dict(base, outcome={k: v for k, v in OUTCOME.items() if k != "prs"}))
    with pytest.raises(AssertionError):
        check_episode(dict(base, outcome=dict(OUTCOME, transcript="")))
