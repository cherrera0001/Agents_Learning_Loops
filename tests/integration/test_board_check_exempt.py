"""Exención de las reglas 2, 3 y 9 para un issue cerrado sin trabajo (#169); sin red ni datos reales."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts import session_guard as sg
from scripts.board_check import REPO, check_board, check_missing_cards, exempt_without_work, run_board

SINCE = 150


def issue(n: int, state: str = "CLOSED", reason: Any = "NOT_PLANNED", **extra: Any) -> dict[str, Any]:
    data: dict[str, Any] = {"number": n, "state": state, "labels": [], **extra}
    if reason is not ...:
        data["stateReason"] = reason
    return data


def card(n: int, status: str, **fields: Any) -> dict[str, Any]:
    return {"content": {"number": n, "type": "Issue", "repository": REPO}, "status": status, **fields}


def episode(ref: str) -> dict[str, Any]:
    return {"seq": 1, "id": "ep", "ref": ref}


def found(issues: list[dict[str, Any]], cards: list[dict[str, Any]], episodes: list[dict[str, Any]]):
    out = check_board(issues, cards, episodes, since=SINCE)
    out += check_missing_cards(issues, cards, SINCE, episodes=episodes)
    return sorted((f.rule, f.issue) for f in out if f.rule in (1, 2, 3, 9))  # la 4 no es de este issue


# --- Criterios de aceptación ------------------------------------------------------------------


def test_not_planned_without_episode_and_done_card_empty_skips_rules_2_and_3():
    assert found([issue(159)], [card(159, "Done")], []) == []


def test_not_planned_without_episode_and_without_card_skips_rule_9():
    assert found([issue(159)], [], []) == []


def test_duplicate_without_episode_is_exempt_too():
    assert found([issue(159, reason="DUPLICATE")], [], []) == []
    assert found([issue(159, reason="DUPLICATE")], [card(159, "Done")], []) == []


def test_not_planned_cited_by_an_episode_keeps_rules_2_and_3_and_9():
    eps = [episode("#159")]
    assert found([issue(159)], [card(159, "Done")], eps) == [(2, 159), (3, 159)]
    assert found([issue(159)], [], eps) == [(9, 159)]


def test_completed_done_empty_keeps_2_and_3_and_missing_card_keeps_9():
    assert found([issue(159, reason="COMPLETED")], [card(159, "Done")], []) == [(2, 159), (3, 159)]
    assert found([issue(159, reason="COMPLETED")], [], []) == [(9, 159)]
    assert found([issue(159, "OPEN", reason="")], [], []) == [(9, 159)]


@pytest.mark.parametrize("reason", ["", None, "WHATEVER", "not_planned", "Duplicate", ...])
def test_closed_with_empty_unknown_or_missing_reason_is_not_exempt(reason):
    assert found([issue(159, reason=reason)], [card(159, "Done")], []) == [(2, 159), (3, 159)]
    assert found([issue(159, reason=reason)], [], []) == [(9, 159)]


def test_open_with_exempt_reason_is_not_exempt():
    assert found([issue(159, "OPEN", reason="NOT_PLANNED")], [], []) == [(9, 159)]


def test_not_planned_in_progress_keeps_rule_1():
    assert found([issue(159)], [card(159, "In Progress")], []) == [(1, 159)]


def test_done_card_with_open_issue_still_rule_1():
    assert (1, 159) in found([issue(159, "OPEN", reason="")], [card(159, "Done")], [])


# --- Entradas raras ------------------------------------------------------------------------


def test_one_episode_citing_several_issues_removes_the_exemption_of_each():
    eps = [episode("#103, #156")]
    issues = [issue(103), issue(156), issue(157)]
    assert exempt_without_work(issues, eps) == {157: "no planeado"}


def test_ref_citing_a_pr_or_another_repo_does_not_remove_the_exemption():
    eps = [episode("PR #159"), episode("otro/repo#159"), episode("https://x/issues/159")]
    assert exempt_without_work([issue(159)], eps) == {159: "no planeado"}


def test_numbers_are_compared_as_numbers_not_text():
    assert exempt_without_work([issue(15)], [episode("#159")]) == {15: "no planeado"}
    assert exempt_without_work([issue(159)], [episode("#15")]) == {159: "no planeado"}


def test_below_since_nothing_changes():
    assert found([issue(10)], [card(10, "Done")], []) == []
    assert check_missing_cards([issue(10)], [], SINCE, episodes=[]) == []


def test_missing_cards_without_episodes_argument_exempts_nothing():
    assert [f.rule for f in check_missing_cards([issue(159)], [], SINCE)] == [9]


# --- Aviso por stderr y código de salida ----------------------------------------------------


def snapshot(tmp_path: Path, issues: list[dict[str, Any]], cards: list[dict[str, Any]]) -> Path:
    (tmp_path / "items.json").write_text(json.dumps({"items": cards}), "utf-8")
    (tmp_path / "issues.json").write_text(json.dumps(issues), "utf-8")
    return tmp_path


def run(capsys, directory: Path, since: int | None = SINCE, episodes=()):
    rc = run_board(since=since, snapshot=directory, episodes=list(episodes))
    cap = capsys.readouterr()
    return rc, cap.out, cap.err


def test_warning_goes_to_stderr_and_exit_code_stays_zero(tmp_path, capsys):
    d = snapshot(tmp_path, [issue(159), issue(160, reason="DUPLICATE")], [card(160, "Done")])
    rc, out, err = run(capsys, d)
    assert rc == 0 and out == "sin hallazgos\n"
    assert "aviso: #159 exento de las reglas 2, 3 y 9 (no planeado, sin episodio)\n" in err
    assert "aviso: #160 exento de las reglas 2, 3 y 9 (duplicado, sin episodio)\n" in err


def test_warning_does_not_change_exit_code_with_other_findings(tmp_path, capsys):
    other = issue(161, "OPEN", reason="")
    rc, out, err = run(capsys, snapshot(tmp_path, [issue(159), other], []))
    assert rc == 1 and out == "R9 #161: issue sin tarjeta en el tablero\n"
    assert "aviso: #159 exento" in err


def test_no_warning_when_cited_open_below_since_or_since_missing(tmp_path, capsys):
    d = snapshot(tmp_path, [issue(159), issue(10), issue(170, "OPEN", reason="")], [card(170, "Todo")])
    assert "exento" in run(capsys, d)[2]  # control: el 159 sí avisa
    assert "#10 " not in run(capsys, d)[2]
    assert "#170" not in run(capsys, d)[2]
    assert "exento" not in run(capsys, d, episodes=[episode("#159")])[2]
    assert "exento" not in run(capsys, d, since=None)[2]


def test_session_guard_does_not_report_exempt_issue(tmp_path):
    d = snapshot(tmp_path, [issue(159), issue(160)], [card(159, "Done")])  # 160 sin tarjeta
    assert sg.informe(snapshot=d, episodes=[])[1] == 0
    assert sg.informe(snapshot=d, episodes=[episode("#159, #160")])[1] == 3  # R2, R3 del 159 y R9 del 160


def test_warning_boundary_is_inclusive_of_since(tmp_path, capsys):
    err = run(capsys, snapshot(tmp_path, [issue(SINCE), issue(SINCE - 1)], []))[2]
    assert f"aviso: #{SINCE} exento" in err and f"#{SINCE - 1} " not in err
