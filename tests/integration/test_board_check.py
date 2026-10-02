"""Chequeo del tablero: cada regla tiene un caso rojo y un control verde; sin red."""

from __future__ import annotations

import io
import json
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from scripts import devlog
from scripts.board_check import (
    REPO,
    BoardReadError,
    Finding,
    check_board,
    cited_issues,
    not_evaluated,
    read_github,
    run_board,
)

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "board-2026-10-02"
COMPLETE = {
    "talla": "S",
    "puntos": 2,
    "incertidumbre": "2",
    "riesgo": "1",
    "verificación": "Verificada",
    "modelo usado": "Sonnet 5.5",
    "escaló": "No",
}


def issue(
    n: int, state: str = "CLOSED", reason: str = "COMPLETED", labels: Sequence[str] = ()
) -> dict[str, Any]:
    return {
        "number": n,
        "state": state,
        "stateReason": reason if state == "CLOSED" else "",
        "labels": [{"name": x} for x in labels],
    }


def card(n: int, status: str, **fields: Any) -> dict[str, Any]:
    content = {"number": n, "type": "Issue", "repository": REPO}
    return {"content": content, "status": status, **fields}


def episode(ref: str, **extra: Any) -> dict[str, Any]:
    return {"seq": 1, "id": "ep", "ref": ref, **extra}


def rules(findings: list[Finding]) -> list[tuple[int, int]]:
    return [(f.rule, f.issue) for f in findings]


# --- Regla 1 -------------------------------------------------------------------------------


def test_rule1_closed_issue_with_card_not_done():
    found = check_board([issue(5)], [card(5, "In Progress")], [])
    assert rules(found) == [(1, 5)]


def test_rule1_open_issue_with_card_done():
    assert rules(check_board([issue(5, "OPEN")], [card(5, "Done")], [])) == [(1, 5)]


def test_rule1_control_consistent_states():
    issues = [issue(5), issue(6, "OPEN")]
    cards = [card(5, "Done"), card(6, "In Progress")]
    assert check_board(issues, cards, []) == []


# --- Regla 2 -------------------------------------------------------------------------------


def test_rule2_missing_estimate_fields_in_progress_and_done():
    cards = [card(80, "In Progress", talla="S"), card(81, "Done", **{**COMPLETE, "riesgo": ""})]
    found = check_board([issue(80, "OPEN"), issue(81)], cards, [episode("#81")], since=76)
    by_issue = {f.issue: f.message for f in found if f.rule == 2}
    assert "puntos, incertidumbre, riesgo" in by_issue[80]
    assert by_issue[81].endswith("sin riesgo")


def test_rule2_controls_complete_below_since_epic_and_no_since():
    incomplete = card(80, "In Progress")
    assert check_board([issue(80, "OPEN")], [card(80, "In Progress", **COMPLETE)], [], since=76) == []
    assert check_board([issue(70, "OPEN")], [card(70, "In Progress")], [], since=76) == []
    epic = card(80, "In Progress")
    assert check_board([issue(80, "OPEN", labels=["epic"])], [epic], [], since=76) == []
    assert check_board([issue(80, "OPEN")], [incomplete], [], since=None) == []
    assert rules(check_board([issue(80, "OPEN")], [incomplete], [], since=76)) == [(2, 80)]


# --- Regla 3 -------------------------------------------------------------------------------


def test_rule3_done_without_verification_model_used_or_escalated():
    bare = {k: v for k, v in COMPLETE.items() if k not in ("modelo usado", "escaló")}
    found = check_board(
        [issue(80)], [card(80, "Done", **{**bare, "verificación": "Pendiente"})], [episode("#80")], since=76
    )
    assert rules(found) == [(3, 80)]
    msg = found[0].message
    assert "Pendiente" in msg and "Modelo usado" in msg and "Escaló" in msg


def test_rule3_controls_complete_and_epic_only_needs_verification():
    assert check_board([issue(80)], [card(80, "Done", **COMPLETE)], [episode("#80")], since=76) == []
    epic_issue = issue(80, labels=["epic"])
    assert (
        check_board(
            [epic_issue], [card(80, "Done", **{"verificación": "Verificada"})], [], since=76, subissues={}
        )
        == []
    )
    red = check_board([epic_issue], [card(80, "Done")], [], since=76)
    assert rules(red) == [(3, 80)] and "Modelo usado" not in red[0].message


# --- Regla 4 -------------------------------------------------------------------------------


def test_rule4_completed_issue_without_citing_episode():
    assert rules(check_board([issue(80)], [], [], since=76)) == [(4, 80)]


def test_rule4_exact_number_only():
    for ref in ("#8", "#800", "PR #80", "otro/repo#80", "vinculaterritorio/vt-landing#80"):
        assert rules(check_board([issue(80)], [], [episode(ref)], since=76)) == [(4, 80)], ref
    for ref in ("#80", "#79, #80", "#80, PR #81", "(#80)"):
        assert check_board([issue(80)], [], [episode(ref)], since=76) == [], ref


def test_rule4_controls_not_planned_epic_below_since_open():
    assert check_board([issue(80, reason="NOT_PLANNED")], [], [], since=76) == []
    assert check_board([issue(80, labels=["epic"])], [], [], since=76) == []
    assert check_board([issue(70)], [], [], since=76) == []
    assert check_board([issue(80, "OPEN")], [], [], since=76) == []


@pytest.mark.parametrize(
    ("ref", "expected"),
    [
        ("#65, PR #66", {65}),
        ("vinculaterritorio/vt-landing#18, PR vinculaterritorio/vt-landing#19", set()),
        ("#24-#36, #41, PR #40", {24, 36, 41}),
        ("PR#7", set()),
        ("pr: #7 y #8", {8}),
        ("#7", {7}),
        ("#77x", set()),
        ("", set()),
    ],
)
def test_cited_issues(ref, expected):
    assert cited_issues(ref) == expected


# --- Regla 5 -------------------------------------------------------------------------------


def test_rule5_estimate_size_differs_from_board():
    ep = episode("#80", estimate={"version": 1, "size": "M"})
    assert rules(check_board([issue(80)], [card(80, "Done", **COMPLETE)], [ep])) == [(5, 80)]


def test_rule5_controls_same_size_no_estimate_or_no_talla():
    cards = [card(80, "Done", **COMPLETE)]
    assert check_board([issue(80)], cards, [episode("#80", estimate={"size": "S"})]) == []
    assert check_board([issue(80)], cards, [episode("#80")]) == []
    assert check_board([issue(80)], [card(80, "Done")], [episode("#80", estimate={"size": "M"})]) == []
    assert check_board([issue(80)], cards, [episode("PR #80", estimate={"size": "M"})]) == []


# --- Regla 6 -------------------------------------------------------------------------------


def test_rule6_closed_epic_with_open_subissues():
    subs = {10: [{"number": 11, "state": "CLOSED"}, {"number": 12, "state": "OPEN"}]}
    found = check_board([issue(10, labels=["epic"])], [], [], subissues=subs)
    assert rules(found) == [(6, 10)] and "#12" in found[0].message


def test_rule6_controls():
    epic_closed = issue(10, labels=["epic"])
    assert check_board([epic_closed], [], [], subissues={10: [{"number": 11, "state": "CLOSED"}]}) == []
    open_epic = issue(10, "OPEN", labels=["epic"])
    assert check_board([open_epic], [], [], subissues={10: [{"number": 11, "state": "OPEN"}]}) == []
    assert check_board([epic_closed], [], [], subissues=None) == []
    assert not_evaluated(None, None) == [
        "reglas 2, 3 y 4 no evaluadas: falta --since",
        "regla 6 no evaluada: no hay datos de subissues",
    ]
    assert not_evaluated(76, {}) == []


def test_findings_are_sorted_and_cards_of_other_repos_or_prs_are_ignored():
    foreign = card(5, "In Progress")
    foreign["content"]["repository"] = "otro/repo"
    pr = card(6, "In Progress")
    pr["content"]["type"] = "PullRequest"
    cards = [card(9, "Todo"), card(3, "Todo"), foreign, pr]
    found = check_board([issue(9), issue(3), issue(5), issue(6)], cards, [])
    assert rules(found) == [(1, 3), (1, 9)]
    assert found[0].line().startswith("R1 #3: ")


# --- Instantánea real (2026-10-02T00:07Z, antes de corregir el tablero) ---------------------


def run(capsys, **kw: Any) -> tuple[int, str, str]:
    rc = run_board(episodes=kw.pop("episodes", []), **kw)
    cap = capsys.readouterr()
    return rc, cap.out, cap.err


def test_real_snapshot_rule1_flags_exactly_65_and_68(capsys):
    items = json.loads((FIXTURE / "items.json").read_text("utf-8"))
    assert len(items["items"]) == 38
    issues = json.loads((FIXTURE / "issues.json").read_text("utf-8"))
    assert rules(check_board(issues, items["items"], [])) == [(1, 65), (1, 68)]
    rc, out, err = run(capsys, since=None, snapshot=FIXTURE)
    assert rc == 1
    assert [line.split(":")[0] for line in out.splitlines()] == ["R1 #65", "R1 #68"]
    assert "falta --since" in err and "regla 6 no evaluada" in err


def test_coherent_snapshot_exits_zero(tmp_path, capsys):
    target = tmp_path / "snap"
    shutil.copytree(FIXTURE, target)
    path = target / "items.json"
    items = json.loads(path.read_text("utf-8"))
    for it in items["items"]:
        it["status"] = "Done"
    path.write_text(json.dumps(items), "utf-8")
    (target / "subissues.json").write_text("{}", "utf-8")
    rc, out, err = run(capsys, since=None, snapshot=target)
    assert (rc, out.strip()) == (0, "sin hallazgos")
    assert "regla 6" not in err


# --- Lectura fallida: código 2, nunca «sin hallazgos» ----------------------------------------


def test_snapshot_without_items_json_exits_2(tmp_path, capsys):
    shutil.copyfile(FIXTURE / "issues.json", tmp_path / "issues.json")
    rc, out, err = run(capsys, since=76, snapshot=tmp_path)
    assert rc == 2 and "sin hallazgos" not in out and "items.json" in err


def test_snapshot_without_issues_json_exits_2(tmp_path, capsys):
    shutil.copyfile(FIXTURE / "items.json", tmp_path / "items.json")
    rc, out, err = run(capsys, since=76, snapshot=tmp_path)
    assert rc == 2 and out == "" and "issues.json" in err


@pytest.mark.parametrize(
    ("items", "issues"),
    [
        ("no es json", "[]"),
        ('{"sin": "items"}', "[]"),
        ('{"items": [], "totalCount": 3}', "[]"),
        ('{"items": []}', "{}"),
    ],
)
def test_snapshot_malformed_exits_2(tmp_path, capsys, items, issues):
    (tmp_path / "items.json").write_text(items, "utf-8")
    (tmp_path / "issues.json").write_text(issues, "utf-8")
    rc, out, err = run(capsys, since=76, snapshot=tmp_path)
    assert rc == 2 and out == "" and err.startswith("error:")


def done(stdout: str = "", stderr: str = "", code: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], code, stdout, stderr)


def fake_gh(login: str = "cherrera0001", project_error: str | None = None, subs: str | None = None):
    items = (FIXTURE / "items.json").read_text("utf-8")
    issues = (FIXTURE / "issues.json").read_text("utf-8")
    graphql = subs or json.dumps({"data": {"repository": {"issues": {"nodes": []}}}})

    def runner(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
        if args[:2] == ["api", "user"]:
            return done(login + "\n")
        if args[0] == "project":
            return done(stderr=project_error, code=1) if project_error else done(items)
        if args[0] == "issue":
            return done(issues)
        if args[:2] == ["api", "graphql"]:
            return done(graphql)
        raise AssertionError(args)

    return runner


def test_gh_project_not_visible_exits_2_and_names_the_account(capsys):
    runner = fake_gh("vinculaterritorio", "GraphQL: Could not resolve to a ProjectV2")
    rc, out, err = run(capsys, since=76, snapshot=None, runner=runner)
    assert rc == 2 and "sin hallazgos" not in out
    assert "vinculaterritorio" in err and "no ve el Project #5" in err and "ProjectV2" in err


def test_gh_missing_exits_2(capsys):
    def runner(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
        raise BoardReadError("gh no está instalado o no está en el PATH")

    rc, out, err = run(capsys, since=76, snapshot=None, runner=runner)
    assert rc == 2 and out == "" and "gh no está instalado" in err


def test_gh_requires_since(capsys):
    rc, out, err = run(capsys, since=None, snapshot=None, runner=fake_gh())
    assert rc == 2 and out == "" and "--since es obligatorio" in err


def test_gh_issue_list_failure_and_truncation_exit_2(capsys):
    def failing(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
        return done(stderr="HTTP 502", code=1) if args[0] == "issue" else fake_gh()(args)

    rc, _, err = run(capsys, since=76, snapshot=None, runner=failing)
    assert rc == 2 and "HTTP 502" in err

    def truncated(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
        return done(json.dumps([issue(1)] * 1000)) if args[0] == "issue" else fake_gh()(args)

    rc, _, err = run(capsys, since=76, snapshot=None, runner=truncated)
    assert rc == 2 and "truncada" in err


def test_gh_success_reads_everything_and_reports_findings(capsys):
    rc, out, err = run(capsys, since=76, snapshot=None, runner=fake_gh())
    assert rc == 1 and "R1 #65" in out and "R1 #68" in out
    assert "no evaluada" not in err
    items, issues, subs = read_github(fake_gh())
    assert len(items) == 38 and len(issues) == 38 and subs == {}


def test_gh_subissues_come_from_graphql(capsys):
    node = {"number": 10, "state": "CLOSED", "subIssues": {"nodes": [{"number": 99, "state": "OPEN"}]}}
    graphql = json.dumps({"data": {"repository": {"issues": {"nodes": [node]}}}})
    _, _, subs = read_github(fake_gh(subs=graphql))
    assert subs == {10: [{"number": 99, "state": "OPEN"}]}


# --- Subcomando ------------------------------------------------------------------------------


def test_devlog_board_subcommand_exit_code(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["devlog", "board", "--snapshot", str(FIXTURE)])
    with pytest.raises(SystemExit) as exc:
        devlog.main()
    assert exc.value.code == 1
    assert "R1 #65" in capsys.readouterr().out


def test_run_board_defaults_to_standard_streams(monkeypatch):
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr(sys, "stderr", err)
    assert run_board(since=None, snapshot=FIXTURE, episodes=[]) == 1
    assert "R1 #65" in out.getvalue()
