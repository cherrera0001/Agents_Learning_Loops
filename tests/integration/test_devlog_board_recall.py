"""El tablero entra en `recall` (#122, primera entrega).

`rebuild` guarda en cada `Goal` cómo se estimó y cómo salió su issue (bloques `estimate` y `outcome` del
episodio, que copian los campos del Project #5), y `recall` lo muestra para los episodios más activados
por la consulta. Con una instantánea del tablero añade estado y verificación.
"""

import json
import sys

import pytest

from scripts import devlog
from scripts.board_check import REPO
from scripts.devlog import board_record, rebuild, recall, similar_issues

ESTIMATE = {
    "version": 1,
    "date": "2026-10-01",
    "size": "M",
    "points": 3,
    "uncertainty": 2,
    "risk": 3,
    "planned_model": "Sonnet 5.5",
    "planned_effort": "high",
}
OUTCOME = {
    "used_model": "Opus 5.5",
    "model_source": "self-reported",
    "escalated": True,
    "estimate_revisions": 1,
    "prs": 2,
}
SECTION = "Issues parecidos (cómo se estimaron y cómo salieron):"


def _episode(seq, ident, goal, ref, steps, **blocks):
    return {"seq": seq, "id": ident, "goal": goal, "ref": ref, "steps": steps, "lessons": [], **blocks}


OK = {"action": "edit_module", "success": True, "note": "hecho"}
KO = {"action": "run_tests", "success": False, "error": "AssertionError en el verificador"}
EPISODES = [
    _episode(
        1,
        "issue-7",
        "Verificador de datos aprueba en vacío",
        "#7",
        [KO, OK, OK],
        estimate=ESTIMATE,
        outcome=OUTCOME,
    ),
    _episode(2, "hito-x", "Partición de tareas por repositorio", "PR #66 sin issue", [OK]),
    _episode(3, "issue-9", "Verificador de datos con manifiesto corrupto", "#9 y #7", [OK, KO]),
]


def _line(out, prefix):
    return next(line for line in out.splitlines() if line.startswith(prefix))


def test_board_record_copies_the_blocks_and_counts_steps():
    assert board_record(EPISODES[0]) == {
        "issue": 7,
        "estimate": ESTIMATE,
        "outcome": OUTCOME,
        "steps": 3,
        "failed_steps": 1,
    }


def test_board_record_without_blocks_or_issue():
    assert board_record(EPISODES[1]) == {
        "issue": None,
        "estimate": None,
        "outcome": None,
        "steps": 1,
        "failed_steps": 0,
    }
    assert board_record(EPISODES[2])["issue"] == 9  # el primero citado; «PR #66» no cuenta como issue


def test_rebuild_stores_the_record_on_each_goal_and_nowhere_else():
    data = rebuild(EPISODES).to_dict()
    with_board = [n for n in data["nodes"] if "board" in n.get("metadata", {})]
    assert sorted(n["metadata"]["ref"] for n in with_board) == ["hito-x", "issue-7", "issue-9"]
    assert {n["type"] for n in with_board} == {"Goal"}
    by_ref = {n["metadata"]["ref"]: n["metadata"]["board"] for n in with_board}
    assert by_ref["issue-7"] == board_record(EPISODES[0])


def test_recall_lists_similar_issues_with_estimate_and_outcome():
    out = recall(rebuild(EPISODES), "verificador de datos")
    section = out.split(SECTION + "\n")[1]
    first = _line(section, "  #7 ")
    assert "estimado M · 3 pts, I2 R3, previsto Sonnet 5.5" in first
    assert "usado Opus 5.5, escaló: sí, PR: 2, revisiones de estimación: 1" in first
    assert "pasos fallidos 1/3" in first
    assert "tablero:" not in first  # sin instantánea no se inventa el estado del tablero
    other = _line(section, "  #9 ")
    assert "sin estimación" in other and "pasos fallidos 1/2" in other
    # la partición no se parece a la consulta: queda al final, detrás de los dos verificadores
    order = [line.split(" (")[0].strip() for line in section.splitlines()]
    assert order[-1] == "hito-x" and set(order[:2]) == {"#7", "#9"}


def test_recall_without_related_experience_lists_no_issue():
    assert recall(rebuild(EPISODES), "xyz").endswith(SECTION + "\n  (ninguno)")


def test_similar_issues_orders_by_activation_then_id_and_honours_top():
    mg = rebuild(EPISODES)
    goals = sorted(mg.nodes_of_type(devlog.NodeType.GOAL))
    activation = {goals[0]: 0.2, goals[1]: 0.9, goals[2]: 0.2, "no-es-goal": 1.0}
    refs = [line.split("(")[1].split(")")[0] for line in similar_issues(mg, activation, top=3)]
    assert refs == [mg.node(g).metadata["ref"] for g in (goals[1], goals[0], goals[2])]
    assert len(similar_issues(mg, activation, top=1)) == 1


def _snapshot(tmp_path, cards):
    items = [
        {"content": {"number": n, "type": "Issue", "repository": repo}, "status": s, "verificación": v}
        for n, s, v, repo in [(*card, REPO)[:4] for card in cards]
    ]
    (tmp_path / "items.json").write_text(json.dumps({"items": items, "totalCount": len(items)}), "utf-8")
    (tmp_path / "issues.json").write_text("[]", "utf-8")
    return tmp_path


def _main_recall(monkeypatch, capsys, snapshot):
    monkeypatch.setattr(devlog, "load_episodes", lambda: EPISODES)
    monkeypatch.setattr(
        sys, "argv", ["devlog", "recall", "verificador de datos", "--snapshot", str(snapshot)]
    )
    devlog.main()
    return capsys.readouterr().out


def test_recall_with_a_snapshot_adds_status_and_verification(tmp_path, monkeypatch, capsys):
    snapshot = _snapshot(tmp_path, [(7, "Done", "Verificada"), (9, "In Progress", None)])
    out = _main_recall(monkeypatch, capsys, snapshot)
    assert "tablero: Done, verificación Verificada" in _line(out, "  #7 ")
    assert "tablero: In Progress, verificación vacía" in _line(out, "  #9 ")


def test_recall_with_a_snapshot_reports_an_issue_without_card(tmp_path, monkeypatch, capsys):
    out = _main_recall(monkeypatch, capsys, _snapshot(tmp_path, [(9, "Todo", None)]))
    assert "tablero: sin tarjeta" in _line(out, "  #7 ")


def test_recall_with_an_unreadable_snapshot_exits_2_and_says_so(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(devlog, "load_episodes", lambda: EPISODES)
    monkeypatch.setattr(sys, "argv", ["devlog", "recall", "x", "--snapshot", str(tmp_path / "no_existe")])
    with pytest.raises(SystemExit) as exc:
        devlog.main()
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert "no se pudo leer la instantánea" in captured.err and captured.out == ""
