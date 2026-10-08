"""Bordes de «Issues parecidos» en `recall` (#122): la línea no afirma lo que el dato no dice."""

import json
import sys

import pytest

from scripts import devlog
from scripts.board_check import REPO
from scripts.devlog import board_record, rebuild, recall, similar_issues

SECTION = "Issues parecidos (cómo se estimaron y cómo salieron):"
STEP = {"action": "edit_module", "success": True, "note": "hecho"}


def _episode(seq, ident, goal, ref, **blocks):
    return {"seq": seq, "id": ident, "goal": goal, "ref": ref, "steps": [STEP], "lessons": [], **blocks}


def _only_line(episode, query="verificador de datos"):
    out = recall(rebuild([episode]), query)
    return out.split(SECTION + "\n")[1].splitlines()[0]


@pytest.mark.parametrize(
    "ref",
    [
        "vinculaterritorio/vt-landing#3, PR vinculaterritorio/vt-landing#16 y #17, issue nuevo #18",
        "otro/repo#14",
    ],
)
def test_a_ref_that_cites_another_repository_is_not_attributed_to_an_issue_here(ref):
    assert board_record(_episode(1, "meta", "x", ref))["issue"] is None


def test_a_range_of_issues_is_attributed_to_the_first():
    assert board_record(_episode(1, "fase", "x", "#24-#36, #41"))["issue"] == 24


def test_missing_values_are_shown_as_unknown_not_as_a_claim():
    episode = _episode(
        1,
        "issue-7",
        "Verificador de datos",
        "#7",
        estimate={"size": "M", "risk": None},
        outcome={"used_model": "Opus 5.5"},
    )
    line = _only_line(episode)
    provenance = "(declarado en episodio; no leído de tarjeta)"
    assert f"estimado M · ? pts, I? R?, previsto ? {provenance}" in line
    assert f"usado Opus 5.5, escaló: ?, PR: ?, revisiones de estimación: ? {provenance}" in line
    assert "None" not in line


@pytest.mark.parametrize(("value", "shown"), [(True, "sí"), (False, "no"), ("no", "?"), (None, "?")])
def test_escalated_is_only_yes_or_no_when_the_episode_says_so(value, shown):
    line = _only_line(_episode(1, "issue-7", "Verificador de datos", "#7", outcome={"escalated": value}))
    assert f"escaló: {shown}," in line


def test_an_empty_planned_model_is_a_datum_and_a_missing_one_is_unknown():
    with_empty = _only_line(
        _episode(1, "issue-7", "Verificador de datos", "#7", estimate={"size": "S", "planned_model": ""})
    )
    assert "previsto ninguno" in with_empty
    assert "previsto ?" in _only_line(
        _episode(1, "issue-7", "Verificador de datos", "#7", estimate={"size": "S"})
    )


def test_a_missing_outcome_is_said_like_a_missing_estimate():
    line = _only_line(_episode(1, "issue-7", "Verificador de datos", "#7", estimate={"size": "S"}))
    assert "episodio sin resultado" in line and "sin estimación" not in line


def test_each_line_shows_its_activation():
    assert _only_line(_episode(1, "issue-7", "Verificador de datos", "#7")).startswith(
        "  #7 (issue-7): activación "
    )


def _three_goals():
    mg = rebuild(
        [_episode(seq, f"issue-{seq}", f"Verificador de datos {seq}", f"#{seq}") for seq in (1, 2, 3)]
    )
    return mg, sorted(mg.nodes_of_type(devlog.NodeType.GOAL))


def test_ties_are_broken_by_goal_id_whatever_the_order_of_the_activation_mapping():
    mg, goals = _three_goals()
    expected = [mg.node(g).metadata["ref"] for g in goals]
    for order in (goals, goals[::-1]):
        refs = [line.split("(")[1].split(")")[0] for line in similar_issues(mg, dict.fromkeys(order, 0.5))]
        assert refs == expected


def test_recall_honours_top_issues_and_the_cli_option(monkeypatch, capsys):
    episodes = [_episode(seq, f"issue-{seq}", f"Verificador de datos {seq}", f"#{seq}") for seq in (1, 2, 3)]
    full = recall(rebuild(episodes), "verificador de datos")
    assert len(full.split(SECTION + "\n")[1].splitlines()) == 3
    one = recall(rebuild(episodes), "verificador de datos", 5, None, None, 1)
    assert len(one.split(SECTION + "\n")[1].splitlines()) == 1
    none = recall(rebuild(episodes), "verificador de datos", 5, None, None, 0)
    assert none.endswith(SECTION + "\n  (ninguno)")
    monkeypatch.setattr(devlog, "load_episodes", lambda: episodes)
    monkeypatch.setattr(sys, "argv", ["devlog", "recall", "verificador de datos", "--issues", "1"])
    devlog.main()
    assert capsys.readouterr().out.rstrip("\n") == one


def test_negative_issues_limit_lists_no_episodes(monkeypatch, capsys):
    episodes = [_episode(seq, f"issue-{seq}", f"Verificador de datos {seq}", f"#{seq}") for seq in (1, 2, 3)]
    monkeypatch.setattr(devlog, "load_episodes", lambda: episodes)
    monkeypatch.setattr(sys, "argv", ["devlog", "recall", "verificador de datos", "--issues", "-1"])
    devlog.main()
    assert capsys.readouterr().out.rstrip("\n").endswith(SECTION + "\n  (ninguno)")


def _run_with_snapshot(monkeypatch, capsys, directory, episode=None):
    episode = episode or _episode(1, "issue-114", "Verificador de datos", "#114")
    monkeypatch.setattr(devlog, "load_episodes", lambda: [episode])
    monkeypatch.setattr(
        sys, "argv", ["devlog", "recall", "verificador de datos", "--snapshot", str(directory)]
    )
    devlog.main()
    return capsys.readouterr()


def _write_snapshot(tmp_path, items):
    (tmp_path / "items.json").write_text(json.dumps({"items": items, "totalCount": len(items)}), "utf-8")
    (tmp_path / "issues.json").write_text("[]", "utf-8")
    return tmp_path


def test_a_card_of_another_repository_is_not_taken_for_this_issue(tmp_path, monkeypatch, capsys):
    mine = {"number": 114, "type": "Issue", "repository": REPO}
    other = {"number": 114, "type": "Issue", "repository": "otro/repo"}
    snapshot = _write_snapshot(
        tmp_path,
        [
            {"content": mine, "status": "Done", "verificación": "Verificada"},
            {"content": other, "status": "Todo", "verificación": None},
        ],
    )
    out = _run_with_snapshot(monkeypatch, capsys, snapshot).out
    assert "tablero: Done, verificación Verificada (snapshot)" in out and "estado Todo" not in out


def test_snapshot_marks_episode_provenance_and_warns_on_discrepancies(tmp_path, monkeypatch, capsys):
    episode = _episode(
        1,
        "issue-114",
        "Verificador de datos",
        "#114",
        estimate={"size": "S", "points": 2, "uncertainty": 1, "risk": 1, "planned_model": "Sonnet"},
        outcome={"used_model": "Sonnet", "escalated": True, "prs": 2},
    )
    snapshot = _write_snapshot(
        tmp_path,
        [
            {
                "content": {"number": 114, "type": "Issue", "repository": REPO},
                "status": "Done",
                "verificación": "Verificada",
                "talla": "M",
                "puntos": 2,
                "incertidumbre": 2,
                "riesgo": 2,
                "modelo": "Opus",
                "modelo usado": "Fable",
                "escaló": "No",
                "linked pull requests": ["https://github.com/example/repo/pull/1"],
            }
        ],
    )
    out = _run_with_snapshot(monkeypatch, capsys, snapshot, episode).out
    assert "estimado S · 2 pts" in out and "(declarado en episodio; no leído de tarjeta)" in out
    assert "usado Sonnet" in out
    assert "tablero: Done, verificación Verificada (snapshot)" in out
    assert "estimate.size=S; talla=M" in out
    assert "estimate.uncertainty=1; incertidumbre=2" in out
    assert "estimate.risk=1; riesgo=2" in out
    assert "estimate.planned_model=Sonnet; modelo=Opus" in out
    assert "outcome.used_model=Sonnet; modelo usado=Fable" in out
    assert "outcome.escalated=Sí; escaló=No" in out
    assert "outcome.prs=2; PR vinculados=1" in out
    assert "discrepancias episodio/snapshot" in out


def test_snapshot_does_not_report_matching_episode_and_card_values(tmp_path, monkeypatch, capsys):
    episode = _episode(
        1,
        "issue-114",
        "Verificador de datos",
        "#114",
        estimate={"size": "S", "points": 2, "uncertainty": 1, "risk": 1, "planned_model": "Sonnet"},
        outcome={"used_model": "Sonnet", "escalated": False, "prs": 1},
    )
    card = {
        "content": {"number": 114, "type": "Issue", "repository": REPO},
        "status": "Done",
        "verificación": "Verificada",
        "talla": "S",
        "puntos": 2,
        "incertidumbre": 1,
        "riesgo": 1,
        "modelo": "Sonnet",
        "modelo usado": "Sonnet",
        "escaló": "No",
        "linked pull requests": ["https://github.com/example/repo/pull/1"],
    }
    snapshot = _write_snapshot(tmp_path, [card])
    out = _run_with_snapshot(monkeypatch, capsys, snapshot, episode).out
    assert "tablero: Done, verificación Verificada (snapshot)" in out
    assert "discrepancias episodio/snapshot" not in out


def test_recall_without_snapshot_keeps_episode_provenance_and_no_board_claim():
    line = _only_line(
        _episode(
            1,
            "issue-7",
            "Verificador de datos",
            "#7",
            estimate={"size": "S"},
            outcome={"used_model": "Sonnet"},
        )
    )
    assert "estimado S" in line and "(declarado en episodio; no leído de tarjeta)" in line
    assert "usado Sonnet" in line
    assert "(snapshot)" not in line


def test_transcript_sourced_outcome_is_described_as_declared_not_self_reported():
    line = _only_line(
        _episode(
            1,
            "issue-7",
            "Verificador de datos",
            "#7",
            outcome={"used_model": "Opus", "model_source": "transcript"},
        )
    )
    assert "usado Opus" in line
    assert "(declarado en episodio; no leído de tarjeta)" in line
    assert "autoinformado" not in line


@pytest.mark.parametrize(
    "items",
    [
        b'{"items": [{"content": {"number": "abc", "type": "Issue"}}]}',
        b'{"items": ["x", null]}',
        b"\xff\xfe no es utf-8",
    ],
)
def test_a_malformed_snapshot_exits_2_without_a_traceback(tmp_path, monkeypatch, capsys, items):
    (tmp_path / "items.json").write_bytes(items)
    (tmp_path / "issues.json").write_text("[]", "utf-8")
    with pytest.raises(SystemExit) as exc:
        _run_with_snapshot(monkeypatch, capsys, tmp_path)
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert "no se pudo leer la instantánea" in captured.err and captured.out == ""
