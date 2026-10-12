"""`recall` omite las lecciones «fallback» cuyo remedio es la misma acción (#187).

Conjunto de episodios FIJO escrito aquí, no los reales.
"""

import json
import sys

from scripts import devlog
from scripts.devlog import is_same_action_fallback, rebuild, recall

SAME = "Si 'run_tests' falla con 'timeout en la suite', usar 'run_tests'"
OTHER = "Si 'review_code' falla con 'revisión incompleta', usar 'edit_module'"
AVOID = "'run_tests' falló con 'timeout en la suite'"
NOTE = "Pasa la suite completa antes de pedir revisión"
QUERY = "suite timeout revisión"


def _ok(action):
    return {"action": action, "success": True, "note": "hecho"}


def _fail(action, error):
    return {"action": action, "success": False, "error": error}


EPISODES = [
    {
        "seq": 1,
        "id": "issue-1",
        "goal": "Suite timeout revisión uno",
        "ref": "#1",
        "steps": [_fail("run_tests", "timeout en la suite"), _ok("run_tests")],
        "lessons": [NOTE],
    },
    {
        "seq": 2,
        "id": "issue-2",
        "goal": "Suite timeout revisión dos",
        "ref": "#2",
        "steps": [_fail("review_code", "revisión incompleta"), _ok("edit_module")],
        "lessons": [],
    },
]


def _lesson_lines(out):
    body = out.split("Lecciones:\n")[1].split("\n\nIssues parecidos")[0]
    return [line for line in body.splitlines() if line.startswith("  - ")]


def test_the_fixed_episodes_generate_both_kinds_of_fallback():
    labels = {mg_label for mg_label in _all_labels(rebuild(EPISODES))}
    assert {SAME, OTHER, AVOID, NOTE} <= labels


def _all_labels(mg):
    return [n.label for n in mg.nodes() if n.metadata.get("kind") == "lesson"]


def test_a_same_action_lesson_disappears_and_another_action_one_stays():
    mg = rebuild(EPISODES)
    out = recall(mg, QUERY, 50)
    lines = "\n".join(_lesson_lines(out))
    assert SAME not in lines
    assert OTHER in lines and AVOID in lines and NOTE in lines


def test_the_list_is_filled_with_the_next_lessons_not_cut_after_filtering():
    mg = rebuild(EPISODES)
    everything = _lesson_lines(recall(mg, QUERY, 50))
    assert len(everything) >= 3
    # Con top=3 hay siempre 3 líneas: la degenerada no ocupa sitio y sube la siguiente.
    assert len(_lesson_lines(recall(mg, QUERY, 3))) == 3
    assert _lesson_lines(recall(mg, QUERY, 3)) == everything[:3]


def test_the_output_says_how_many_were_omitted():
    mg = rebuild(EPISODES)
    out = recall(mg, QUERY, 50)
    assert "omitidas por la regla de misma acción: 1;" in out
    only_note = rebuild([{**EPISODES[0], "steps": [_ok("run_tests")]}])
    assert "omitidas por la regla de misma acción: 0;" in recall(only_note, QUERY, 5)


def test_omitted_counts_only_the_positions_that_would_have_been_shown():
    mg = rebuild(EPISODES)
    activation = recall_activation(mg)
    shown, omitted = devlog.visible_lessons(mg, activation, 50)
    assert omitted == 1 and SAME not in shown
    _, omitted_none = devlog.visible_lessons(mg, activation, 0)
    assert omitted_none == 0


def recall_activation(mg):
    from associative_agent_loop.memory.associative import Retriever

    actions = [mg.node(n).label for n in mg.nodes_of_type(devlog.NodeType.ACTION)]
    return Retriever(mg).retrieve(QUERY, actions).activation


def test_the_visible_order_is_the_library_order_minus_the_omitted():
    from associative_agent_loop.memory.associative import Retriever

    mg = rebuild(EPISODES)
    actions = [mg.node(n).label for n in mg.nodes_of_type(devlog.NodeType.ACTION)]
    result = Retriever(mg).retrieve(QUERY, actions)
    shown, _ = devlog.visible_lessons(mg, result.activation, 50)
    assert shown == [lesson for lesson in result.lessons if lesson != SAME]


def test_identification_is_structural_not_by_the_text_of_a_lesson():
    prefix = "concept:lesson:fallback:"
    assert is_same_action_fallback(f"{prefix}run_tests:run_tests", SAME)
    assert not is_same_action_fallback(f"{prefix}review_code:edit_module", OTHER)
    assert not is_same_action_fallback("concept:lesson:avoid:run_tests:x", AVOID)
    # una nota a mano que imita la frase no se toca
    assert not is_same_action_fallback("concept:lesson:note:si_run_tests_falla", SAME)


def test_slugs_truncated_to_the_same_prefix_do_not_hide_a_different_action():
    long = "a" * 40
    node_id = f"concept:lesson:fallback:{long}:{long}"
    assert is_same_action_fallback(node_id, f"Si '{long}' falla con 'e', usar '{long}'")
    assert not is_same_action_fallback(node_id, f"Si '{long}x' falla con 'e', usar '{long}y'")


def test_rebuild_is_unchanged_and_deterministic(tmp_path):
    one, two = tmp_path / "one.json", tmp_path / "two.json"
    rebuild(EPISODES).save(one)
    rebuild(list(reversed(EPISODES))).save(two)
    assert one.read_text("utf-8") == two.read_text("utf-8")
    saved = json.loads(one.read_text("utf-8"))
    assert SAME in json.dumps(saved, ensure_ascii=False)  # el grafo guardado conserva la lección


def test_cli_recall_prints_the_omitted_count(monkeypatch, capsys):
    monkeypatch.setattr(devlog, "load_episodes", lambda: EPISODES)
    monkeypatch.setattr(sys, "argv", ["devlog", "recall", QUERY])
    devlog.main()
    out = capsys.readouterr().out
    assert SAME not in out and "omitidas por la regla de misma acción: 1;" in out
