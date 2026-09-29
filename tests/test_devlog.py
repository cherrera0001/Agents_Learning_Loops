"""La bitácora del repo es a su vez una memoria asociativa: se prueba como tal."""

import json

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


def test_recall_returns_related_lessons_and_actions():
    out = recall(rebuild(EPISODES), "agregar dependencia hypothesis")
    assert "add_dependency" in out
    assert "Instalar el extra dev antes de correr los tests" in out
    assert "(sin experiencia relacionada)" in recall(rebuild(EPISODES), "xyz")


def test_committed_episodes_are_valid_and_ordered():
    episodes = load_episodes(EPISODES_DIR)
    assert episodes, "debe existir al menos el episodio retroactivo v0.1"
    seqs = [e["seq"] for e in episodes]
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)
    for ep in episodes:
        assert ep["goal"] and ep["steps"]
        assert all({"action", "success"} <= set(s) for s in ep["steps"])
