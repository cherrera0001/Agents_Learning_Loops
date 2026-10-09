"""Exención de las reglas 2, 3 y 9 para un issue cerrado sin trabajo (#169); sin red ni datos reales."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from scripts import session_guard as sg
from scripts.board_check import (
    REPO,
    BoardReadError,
    check_board,
    check_missing_cards,
    exempt_without_work,
    parse_timeline,
    read_pr_refs,
    read_snapshot_pr_refs,
    run_board,
)

SINCE = 150
COMPLETE = {
    "talla": "S",
    "puntos": 2,
    "incertidumbre": "2",
    "riesgo": "1",
    "verificación": "Verificada",
    "modelo usado": "Sonnet 5.5",
    "escaló": "No",
}


def issue(n: int, state: str = "CLOSED", reason: Any = "NOT_PLANNED", **extra: Any) -> dict[str, Any]:
    data: dict[str, Any] = {"number": n, "state": state, "labels": [], **extra}
    if reason is not ...:
        data["stateReason"] = reason
    return data


def card(n: int, status: str, **fields: Any) -> dict[str, Any]:
    return {"content": {"number": n, "type": "Issue", "repository": REPO}, "status": status, **fields}


def episode(ref: str) -> dict[str, Any]:
    return {"seq": 1, "id": "ep", "ref": ref}


def no_prs(issues: list[dict[str, Any]]) -> dict[int, list[int] | None]:
    """Lectura de PR hecha y sin ningún PR fusionado para cada issue."""
    return {int(i["number"]): [] for i in issues}


def found(
    issues: list[dict[str, Any]],
    cards: list[dict[str, Any]],
    episodes: list[dict[str, Any]],
    pr_refs: Any = "sin PR",
):
    refs = no_prs(issues) if pr_refs == "sin PR" else pr_refs
    out = check_board(issues, cards, episodes, since=SINCE, pr_refs=refs)
    out += check_missing_cards(issues, cards, SINCE, episodes=episodes, pr_refs=refs)
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
    assert exempt_without_work(issues, eps, no_prs(issues)) == {157: "no planeado"}


def test_ref_citing_a_pr_or_another_repo_does_not_remove_the_exemption():
    eps = [episode("PR #159"), episode("otro/repo#159"), episode("https://x/issues/159")]
    assert exempt_without_work([issue(159)], eps, {159: []}) == {159: "no planeado"}


def test_numbers_are_compared_as_numbers_not_text():
    assert exempt_without_work([issue(15)], [episode("#159")], {15: []}) == {15: "no planeado"}
    assert exempt_without_work([issue(159)], [episode("#15")], {159: []}) == {159: "no planeado"}


def test_below_since_nothing_changes():
    assert found([issue(10)], [card(10, "Done")], []) == []
    assert check_missing_cards([issue(10)], [], SINCE, episodes=[], pr_refs={10: []}) == []


def test_missing_cards_without_episodes_argument_exempts_nothing():
    assert [f.rule for f in check_missing_cards([issue(159)], [], SINCE)] == [9]


# --- Aviso por stderr y código de salida ----------------------------------------------------


def snapshot(
    tmp_path: Path, issues: list[dict[str, Any]], cards: list[dict[str, Any]], prs: Any = "sin PR"
) -> Path:
    refs = {str(n): v for n, v in no_prs(issues).items()} if prs == "sin PR" else prs
    if refs is not None:
        (tmp_path / "prs.json").write_text(json.dumps(refs), "utf-8")
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
    assert "aviso: #159 exento de las reglas 2, 3 y 9 (no planeado, sin episodio ni PR fusionado)\n" in err
    assert "aviso: #160 exento de las reglas 2, 3 y 9 (duplicado, sin episodio ni PR fusionado)\n" in err


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
    assert "exento de" not in run(capsys, d, episodes=[episode("#159")])[2]
    assert "exento" not in run(capsys, d, since=None)[2]


def test_session_guard_does_not_report_exempt_issue(tmp_path):
    d = snapshot(tmp_path, [issue(159), issue(160)], [card(159, "Done")])  # 160 sin tarjeta
    assert sg.informe(snapshot=d, episodes=[])[1] == 0
    assert sg.informe(snapshot=d, episodes=[episode("#159, #160")])[1] == 3  # R2, R3 del 159 y R9 del 160


def test_warning_boundary_is_inclusive_of_since(tmp_path, capsys):
    err = run(capsys, snapshot(tmp_path, [issue(SINCE), issue(SINCE - 1)], []))[2]
    assert f"aviso: #{SINCE} exento" in err and f"#{SINCE - 1} " not in err


# --- PR fusionados que referencian el issue antes de su cierre (enmienda del concilio) --------

MINE = f"https://api.github.com/repos/{REPO}"
CLOSED_AT = "2026-10-08T23:48:06Z"


def row(
    event: str, created: Any, number: Any = None, url: Any = None, is_pr: Any = False, merged: Any = False
):
    return [event, created, number, url, is_pr, merged]


def closed(at: Any = CLOSED_AT):
    return row("closed", at)


def ref(number: int, at: Any, merged: Any = True, url: str = MINE, is_pr: Any = True):
    return row("cross-referenced", at, number, url, is_pr, merged)


BEFORE = "2026-10-03T22:49:48Z"
AFTER = "2026-10-09T12:55:46Z"


def lines(rows: list[Any]) -> str:
    return "\n".join(json.dumps(r) for r in rows) + "\n"


def test_not_planned_referenced_by_a_merged_pr_keeps_rules_2_3_and_9():
    """El caso #104: sin episodio que lo cite, pero con trabajo fusionado."""
    refs = {159: [129, 135]}
    assert found([issue(159)], [card(159, "Done")], [], refs) == [(2, 159), (3, 159)]
    assert found([issue(159)], [], [], refs) == [(9, 159)]
    assert found([issue(159, reason="DUPLICATE")], [], [], refs) == [(9, 159)]


def test_read_without_data_does_not_exempt():
    for refs in (None, {}, {159: None}, {160: []}):
        assert found([issue(159)], [], [], refs) == [(9, 159)]
        assert exempt_without_work([issue(159)], [], refs) == {}


def test_parse_timeline_reference_before_closing_of_a_merged_pr_counts():
    assert parse_timeline(lines([closed(), ref(129, BEFORE)])) == [129]


def test_parse_timeline_reference_after_closing_of_a_merged_pr_does_not_count():
    """El PR que entrega esta regla menciona al duplicado después de cerrado: no puede anularla."""
    assert parse_timeline(lines([closed(), ref(170, AFTER)])) == []


def test_parse_timeline_reference_before_closing_of_an_unmerged_pr_does_not_count():
    assert parse_timeline(lines([closed(), ref(129, BEFORE, merged=False)])) == []


def test_parse_timeline_ties_count_as_work_and_the_last_closing_is_used():
    assert parse_timeline(lines([closed(), ref(129, CLOSED_AT)])) == [129]
    twice = [closed("2026-10-01T00:00:00Z"), ref(7, "2026-10-02T00:00:00Z"), closed("2026-10-03T00:00:00Z")]
    assert parse_timeline(lines(twice)) == [7]  # con el primer cierre no contaría


def test_parse_timeline_compares_instants_not_text_nor_merge_date():
    # 00:00+02:00 del día 9 son las 22:00Z del día 8: anterior al cierre aunque el texto sea mayor
    assert parse_timeline(lines([closed(), ref(5, "2026-10-09T00:00:00+02:00")])) == [5]
    assert parse_timeline(lines([closed(), ref(5, "2026-10-08T23:49:00Z")])) == []  # un minuto después


def test_parse_timeline_reads_every_line_and_filters_by_event_kind():
    rows = [
        closed(),
        ref(7, BEFORE, url="https://api.github.com/repos/otro/repo"),
        row("labeled", BEFORE, 8, MINE, True, True),  # no es una referencia cruzada
        ref(9, BEFORE, merged=False),
        ref(10, BEFORE, is_pr=False),  # un issue, no un PR
        ref(129, BEFORE),
        ref(129, BEFORE),
    ]
    assert parse_timeline(lines(rows)) == [129]


@pytest.mark.parametrize(
    "stdout",
    [
        "",  # salida vacía con código 0: no se distingue de «sin referencias»
        lines([ref(129, BEFORE)]),  # sin evento de cierre
        lines([closed(), {"a": 1, "b": 2, "c": 3, "d": 4}]),  # objeto de cuatro claves
        lines([closed(), "abcd"]),  # cadena de cuatro caracteres
        lines([closed(), ["x"] * 5]),  # lista de forma inesperada
        lines([closed(None), ref(129, BEFORE)]),  # cierre sin fecha
        lines([closed("ayer"), ref(129, BEFORE)]),  # cierre con fecha ilegible
        lines([closed(), closed(None), ref(129, BEFORE)]),  # un segundo cierre sin fecha
        lines([closed(), ref(129, None)]),  # referencia sin fecha
        lines([closed(), ref(129, "no es una fecha")]),  # referencia con fecha ilegible
        lines([closed(), ref(129, "2026-10-03T22:49:48")]),  # fecha sin zona horaria
        "esto no es JSON\n",
    ],
)
def test_parse_timeline_unreliable_reads_are_none(stdout):
    assert parse_timeline(stdout) is None


def fake_timeline(responses: dict[int, Any], calls: list[list[str]] | None = None):
    """Un ``gh api .../timeline`` de mentira: lista de filas, texto crudo, código de error o excepción."""

    def runner(args):
        if calls is not None:
            calls.append(list(args))
        n = int(args[1].split("/")[4])
        r = responses[n]
        if isinstance(r, Exception):
            raise r
        if isinstance(r, int):
            return subprocess.CompletedProcess(args, r, "", "boom")
        text = r if isinstance(r, str) else lines(r)
        return subprocess.CompletedProcess(args, 0, text, "")

    return runner


def test_read_pr_refs_reads_every_line_not_only_the_first():
    rows = [
        closed(),
        ref(7, AFTER),
        ref(8, BEFORE, merged=False),
        ref(129, BEFORE),
    ]  # el que cuenta es el último
    assert read_pr_refs([104], fake_timeline({104: rows})) == {104: [129]}
    assert read_pr_refs([159], fake_timeline({159: [closed()]})) == {159: []}


def test_read_pr_refs_failure_is_none_not_empty():
    runner = fake_timeline(
        {1: 1, 2: BoardReadError("sin respuesta"), 3: "", 4: [ref(1, BEFORE)], 5: ["x"], 6: [closed()]}
    )
    assert read_pr_refs([1, 2, 3, 4, 5, 6], runner) == {1: None, 2: None, 3: None, 4: None, 5: None, 6: []}


def test_read_pr_refs_paginates_and_reads_only_the_numbers_it_is_given():
    calls: list[list[str]] = []
    read_pr_refs([104, 159], fake_timeline({104: [closed()], 159: [closed()]}, calls))
    assert [c[1] for c in calls] == [
        f"repos/{REPO}/issues/104/timeline",
        f"repos/{REPO}/issues/159/timeline",
    ]
    assert all(c[0] == "api" and "--paginate" in c for c in calls)  # sin él, más de 30 eventos se pierden
    read_pr_refs([], fake_timeline({}, calls))
    assert len(calls) == 2


def test_issue_number_is_not_matched_by_prefix():
    """#104 y #1040: las referencias se leen por issue, no se buscan como texto."""
    both = [issue(104), issue(1040)]
    assert exempt_without_work(both, [], {104: [129], 1040: []}) == {1040: "no planeado"}
    assert exempt_without_work(both, [], {104: [], 1040: [129]}) == {104: "no planeado"}


def test_read_failure_warns_not_exempt_and_exit_code_unchanged(tmp_path, capsys):
    d = snapshot(tmp_path, [issue(159)], [], prs={"159": None})
    rc, out, err = run(capsys, d)
    assert rc == 1 and out == "R9 #159: issue sin tarjeta en el tablero\n"
    assert "aviso: #159 no exento: no se pudieron comprobar los PR fusionados" in err


def test_snapshot_without_prs_json_exempts_nobody(tmp_path, capsys):
    rc, out, err = run(capsys, snapshot(tmp_path, [issue(159)], [], prs=None))
    assert rc == 1 and "R9 #159" in out and "no exento" in err and "exento de" not in err


def test_notice_says_which_merged_pr_gives_the_work(tmp_path, capsys):
    rc, out, err = run(capsys, snapshot(tmp_path, [issue(159)], [], prs={"159": [129]}))
    assert rc == 1 and "R9 #159" in out and "exento de" not in err
    assert "aviso: #159 no exento: PR fusionado #129 que lo referencia antes del cierre\n" in err
    (tmp_path / "dos").mkdir()
    err = run(capsys, snapshot(tmp_path / "dos", [issue(159)], [], prs={"159": [129, 135]}))[2]
    assert "aviso: #159 no exento: PR fusionados #129, #135 que lo referencian antes del cierre\n" in err


def test_notice_says_which_episode_cites_the_issue(tmp_path, capsys):
    ep = {"seq": 3, "id": "issue-9-x", "ref": "#9, #159"}
    err = run(capsys, snapshot(tmp_path, [issue(159)], [card(159, "Done")]), episodes=[ep])[2]
    assert "aviso: #159 no exento: lo cita el episodio issue-9-x\n" in err


def test_no_notice_for_issues_that_are_not_closed_without_work(tmp_path, capsys):
    d = snapshot(tmp_path, [issue(160, reason="COMPLETED"), issue(161, "OPEN", reason="")], [])
    assert "no exento" not in run(capsys, d)[2]


def test_snapshot_prs_json_malformed_is_a_read_error(tmp_path):
    (tmp_path / "prs.json").write_text("[1]", "utf-8")
    with pytest.raises(BoardReadError):
        read_snapshot_pr_refs(tmp_path)
    (tmp_path / "prs.json").write_text('{"x": [1]}', "utf-8")
    with pytest.raises(BoardReadError):
        read_snapshot_pr_refs(tmp_path)
    (tmp_path / "prs.json").write_text('{"159": null, "104": [1]}', "utf-8")
    assert read_snapshot_pr_refs(tmp_path) == {159: None, 104: [1]}


def test_session_guard_prints_the_notices(tmp_path):
    d = snapshot(tmp_path, [issue(159)], [card(159, "Done")])
    aviso = "aviso: #159 exento de las reglas 2, 3 y 9 (no planeado, sin episodio ni PR fusionado)"
    assert any(aviso in x for x in sg.informe(snapshot=d, episodes=[])[0])
    otro = tmp_path / "con_pr"
    otro.mkdir()
    d2 = snapshot(otro, [issue(159)], [card(159, "Done")], prs={"159": [129]})
    lineas, hallazgos = sg.informe(snapshot=d2, episodes=[])
    assert hallazgos == 2 and not any("exento de" in x for x in lineas)
    assert any("no exento: PR fusionado #129 que lo referencia antes del cierre" in x for x in lineas)


def github_runner(issues, cards, timelines, calls):
    def runner(args):
        if args[:2] == ["api", "user"]:
            return subprocess.CompletedProcess(args, 0, "cherrera0001\n", "")
        if args[0] == "project":
            return subprocess.CompletedProcess(args, 0, json.dumps({"items": cards}), "")
        if args[0] == "issue":
            return subprocess.CompletedProcess(args, 0, json.dumps(issues), "")
        if args[:2] == ["pr", "list"]:
            return subprocess.CompletedProcess(args, 0, "[]", "")
        if args[:2] == ["api", "graphql"]:
            empty = {"data": {"repository": {"issues": {"nodes": []}}}}
            return subprocess.CompletedProcess(args, 0, json.dumps(empty), "")
        calls.append(args[1])
        return fake_timeline(timelines)(args)

    return runner


def run_via(capsys, runner, episodes=(), since=SINCE - 100):
    rc = run_board(since=since, snapshot=None, episodes=list(episodes), runner=runner)
    cap = capsys.readouterr()
    return rc, cap.out, cap.err


def test_github_mode_reads_prs_only_for_candidates_in_scope(capsys):
    issues = [
        issue(10),  # candidato bajo --since: no se lee
        issue(50),  # candidato justo en --since: se lee
        issue(104),  # candidato con PR fusionado anterior al cierre
        issue(159),  # candidato cuya única referencia es posterior al cierre
        issue(160, reason="COMPLETED"),  # no es candidato
        issue(161, "OPEN", reason=""),  # no es candidato
        issue(162),  # lo cita un episodio: no se lee
    ]
    cards = [card(104, "Done"), card(160, "Done"), card(161, "Todo"), card(162, "Done"), card(50, "Done")]
    timelines = {
        50: [closed()],
        104: [closed(), ref(129, BEFORE)],
        159: [closed(), ref(170, AFTER)],
    }
    calls: list[str] = []
    runner = github_runner(issues, cards, timelines, calls)
    _rc, out, err = run_via(capsys, runner, episodes=[episode("#162, #160")])
    assert calls == [f"repos/{REPO}/issues/{n}/timeline" for n in (50, 104, 159)]
    assert "R2 #104" in out and "R3 #104" in out and "R2 #159" not in out and "R9 #159" not in out
    assert "aviso: #159 exento" in err and "aviso: #50 exento" in err and "#104 exento" not in err
    assert "aviso: #104 no exento: PR fusionado #129 que lo referencia antes del cierre" in err


def test_the_day_after_the_merge_the_exemption_stays(capsys):
    """Simulación del día después: la fuente del PR de este cambio, fusionada y posterior al cierre."""
    issues = [issue(159)]
    timelines = {159: [closed(), ref(170, AFTER, merged=True)]}
    _rc, out, err = run_via(capsys, github_runner(issues, [card(159, "Done")], timelines, []), since=150)
    assert out == "sin hallazgos\n"
    assert "aviso: #159 exento de las reglas 2, 3 y 9" in err


def test_session_guard_reads_with_its_own_since(capsys):
    issues = [issue(sg.DESDE - 1), issue(sg.DESDE)]
    cards = [card(sg.DESDE, "Done"), card(sg.DESDE - 1, "Done")]
    calls: list[str] = []
    runner = github_runner(issues, cards, {sg.DESDE: [closed()]}, calls)
    sg.informe(snapshot=None, episodes=[], runner=runner)
    assert calls == [f"repos/{REPO}/issues/{sg.DESDE}/timeline"]


def test_unreadable_prs_leave_no_finding_and_exit_zero_with_a_complete_card(tmp_path, capsys):
    """El aviso «no exento» no cambia el código de salida: con la tarjeta completa no hay hallazgos."""
    d = snapshot(tmp_path, [issue(159)], [card(159, "Done", **COMPLETE)], prs={"159": None})
    rc, out, err = run(capsys, d)
    assert rc == 0 and out == "sin hallazgos\n" and "aviso: #159 no exento" in err


def test_session_guard_in_github_mode_reads_prs_and_prints_the_notice():
    issues = [issue(104), issue(159)]
    cards = [card(104, "Done"), card(159, "Done")]
    calls: list[str] = []
    timelines = {104: [closed(), ref(129, BEFORE)], 159: [closed(), ref(170, AFTER)]}
    lineas, hallazgos = sg.informe(
        snapshot=None, episodes=[], runner=github_runner(issues, cards, timelines, calls)
    )
    assert len(calls) == 2
    assert hallazgos == 2  # R2 y R3 del 104; el otro, exento
    assert any("aviso: #159 exento" in x for x in lineas) and not any("#104 exento" in x for x in lineas)
