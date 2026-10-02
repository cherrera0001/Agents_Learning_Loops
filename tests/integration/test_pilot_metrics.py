"""Lectura del piloto por comando: cada medida con numerador 0, mayor que 0 y denominador 0; sin red."""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from scripts import devlog
from scripts.board_check import REPO
from scripts.pilot_metrics import (
    NO_DATA,
    NOT_FOUND,
    NOT_MEASURED,
    Measure,
    TokenUsage,
    compute_measures,
    format_report,
    format_result,
    parse_map,
    parse_transcript,
    primary_issue,
    run_pilot,
    select_population,
    transcript_names,
)

COMPLETE = {
    "talla": "S",
    "puntos": 2,
    "incertidumbre": "2",
    "riesgo": "1",
    "verificación": "Verificada",
    "modelo": "Sonnet 5.5",
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


def card(n: int, status: str = "Done", **fields: Any) -> dict[str, Any]:
    content = {"number": n, "type": "Issue", "repository": REPO}
    return {"content": content, "status": status, **fields}


def full_card(n: int, status: str = "Done", **overrides: Any) -> dict[str, Any]:
    return card(n, status, **{**COMPLETE, **overrides})


def outcome(**over: Any) -> dict[str, Any]:
    base = {"used_model": "Sonnet 5.5", "model_source": "self-reported", "escalated": False}
    return {**base, "estimate_revisions": 0, "prs": 1, **over}


def episode(ref: str, seq: int = 1, steps: Sequence[bool] = (), **extra: Any) -> dict[str, Any]:
    return {
        "seq": seq,
        "id": f"ep{seq}",
        "ref": ref,
        "steps": [{"action": "write_code", "success": ok} for ok in steps],
        **extra,
    }


def measure(report, prefix: str) -> Measure:
    found = [m for m in report.measures if m.name.startswith(prefix)]
    assert len(found) == 1, prefix
    return found[0]


def pair(report, prefix: str) -> tuple[int, int]:
    m = measure(report, prefix)
    return m.numerator, m.denominator


def compute(issues, cards, episodes, **kw):
    return compute_measures(issues, cards, episodes, since=kw.pop("since", 1), **kw)


# --- Población ---------------------------------------------------------------------------------


def test_population_excludes_open_epics_not_planned_and_below_since():
    issues = [
        issue(5),
        issue(6, "OPEN"),
        issue(7, labels=["epic"]),
        issue(8, reason="NOT_PLANNED"),
        issue(3),  # < since
        issue(9),
        issue(10, reason="COMPLETED", labels=["bug"]),
    ]
    assert select_population(issues, [], since=5) == [5, 9, 10]


def test_population_since_is_inclusive_and_until_is_inclusive():
    issues = [issue(n) for n in (75, 76, 77, 78, 79, 80)]
    assert select_population(issues, [], since=76, until=79) == [76, 77, 78, 79]
    assert select_population(issues, [], since=76) == [76, 77, 78, 79, 80]
    assert select_population(issues, [], since=76, until=76) == [76]


def test_population_excludes_an_epic_marked_only_on_the_card():
    epic_card = card(7, labels=["epic"])
    assert select_population([issue(7), issue(8)], [epic_card], since=1) == [8]


def test_report_lists_the_population():
    report = compute([issue(5), issue(6, labels=["epic"])], [], [])
    assert report.population == (5,)
    assert "Población (n = 1): #5" in format_report(report)
    assert "ninguno" in format_report(compute([], [], []))


# --- Medida 1: estimación completa -------------------------------------------------------------


def test_measure1_estimation_complete_zero_and_positive():
    issues = [issue(5), issue(6)]
    none_complete = [card(5, talla="S"), card(6, **{**COMPLETE, "riesgo": ""})]
    assert pair(compute(issues, none_complete, []), "Estimación completa") == (0, 2)
    some = [full_card(5), card(6, talla="S")]
    assert pair(compute(issues, some, []), "Estimación completa") == (1, 2)
    assert pair(compute(issues, [], []), "Estimación completa") == (0, 2)  # sin tarjeta no es completa


def test_measure1_empty_population_prints_no_data():
    m = measure(compute([], [], []), "Estimación completa")
    assert format_result(m) == NO_DATA


# --- Medida 2: Done verificado -----------------------------------------------------------------


def test_measure2_done_verified_zero_and_positive():
    issues = [issue(5), issue(6), issue(7)]
    cards = [full_card(5, verificación="Pendiente"), full_card(6, "In Progress"), full_card(7, "Done")]
    assert pair(compute(issues, cards, []), "Done con Verificación") == (1, 2)
    cards = [full_card(5, verificación="Pendiente"), full_card(6, verificación="")]
    assert pair(compute(issues, cards, []), "Done con Verificación") == (0, 2)


def test_measure2_no_card_in_done_prints_no_data():
    report = compute([issue(5)], [full_card(5, "In Progress")], [])
    assert pair(report, "Done con Verificación") == (0, 0)
    assert format_result(measure(report, "Done con Verificación")) == NO_DATA


# --- Medida 3: escalamientos -------------------------------------------------------------------


def test_measure3_escalations_zero_and_positive():
    issues = [issue(5), issue(6), issue(7)]
    cards = [full_card(5, escaló="No"), full_card(6, escaló="No"), full_card(7, escaló="")]
    assert pair(compute(issues, cards, []), "Escalamientos") == (0, 2)
    cards = [full_card(5, escaló="Sí"), full_card(6, escaló="No"), full_card(7, escaló="")]
    assert pair(compute(issues, cards, []), "Escalamientos") == (1, 2)


def test_measure3_no_escalation_field_prints_no_data():
    report = compute([issue(5)], [full_card(5, escaló="")], [])
    assert format_result(measure(report, "Escalamientos")) == NO_DATA


# --- Medida 4: modelo previsto distinto del usado ----------------------------------------------


def test_measure4_planned_vs_used_zero_and_positive():
    issues = [issue(5), issue(6), issue(7)]
    cards = [full_card(5), full_card(6), full_card(7, **{"modelo usado": ""})]
    assert pair(compute(issues, cards, []), "Modelo previsto distinto") == (0, 2)
    cards = [full_card(5), full_card(6, **{"modelo usado": "Opus 5.5"}), full_card(7, modelo="")]
    assert pair(compute(issues, cards, []), "Modelo previsto distinto") == (1, 2)


def test_measure4_no_issue_with_both_fields_prints_no_data():
    report = compute([issue(5)], [full_card(5, modelo="")], [])
    assert format_result(measure(report, "Modelo previsto distinto")) == NO_DATA


# --- Medidas 5 y 6: PR adicionales y revisiones ------------------------------------------------


def test_measures5_and_6_extra_prs_and_revisions_zero_and_positive():
    issues = [issue(5), issue(6), issue(7)]
    quiet = [episode("#5", outcome=outcome()), episode("#6", 2, outcome=outcome())]
    report = compute(issues, [], quiet)
    assert pair(report, "PR adicionales") == (0, 2)
    assert pair(report, "Revisiones de estimación") == (0, 2)
    busy = [
        episode("#5", outcome=outcome(prs=3, estimate_revisions=1)),
        episode("#6", 2, outcome=outcome(prs=2, estimate_revisions=2)),
        episode("#7", 3),  # sin outcome: no cuenta en el denominador
    ]
    report = compute(issues, [], busy)
    assert pair(report, "PR adicionales") == (3, 2)
    assert pair(report, "Revisiones de estimación") == (3, 2)
    assert measure(report, "PR adicionales").detail == "#5: 2, #6: 1"


def test_measures5_and_6_without_outcome_print_no_data():
    report = compute([issue(5)], [], [episode("#5")])
    assert format_result(measure(report, "PR adicionales")) == NO_DATA
    assert format_result(measure(report, "Revisiones de estimación")) == NO_DATA


def test_extra_prs_never_print_a_percentage():
    m = Measure("x", 3, 20, rate=False)
    assert format_result(m) == "3 de 20"


# --- Medida 7: model_source --------------------------------------------------------------------


def test_measure7_model_source_zero_and_positive():
    issues = [issue(5), issue(6)]
    eps = [episode("#5", outcome=outcome()), episode("#6", 2, outcome=outcome())]
    assert pair(compute(issues, [], eps), "model_source") == (0, 2)
    eps = [episode("#5", outcome=outcome(model_source="transcript")), episode("#6", 2, outcome=outcome())]
    assert pair(compute(issues, [], eps), "model_source") == (1, 2)


def test_measure7_without_episodes_prints_no_data():
    assert format_result(measure(compute([issue(5)], [], []), "model_source")) == NO_DATA


# --- Medida 8: pasos fallidos por talla --------------------------------------------------------


def test_measure8_failed_steps_by_size_zero_and_positive():
    issues = [issue(5), issue(6), issue(7)]
    cards = [full_card(5, talla="XS"), full_card(6, talla="S"), full_card(7, talla="S")]
    eps = [
        episode("#5", steps=[True, True]),
        episode("#6", 2, steps=[False, True, True]),
        episode("#7", 3, steps=[False, False, True, True]),
    ]
    report = compute(issues, cards, eps)
    assert pair(report, "Pasos fallidos, talla XS") == (0, 2)
    assert pair(report, "Pasos fallidos, talla S") == (3, 7)
    assert "autoinformado" in measure(report, "Pasos fallidos, talla S").name
    assert measure(report, "Pasos fallidos, talla S").detail == "#6: 1 de 3, #7: 2 de 4"


def test_measure8_sizes_are_ordered_and_steps_of_repeated_episodes_are_summed():
    issues = [issue(5), issue(6)]
    cards = [full_card(5, talla="M"), full_card(6, talla="XS")]
    eps = [
        episode("#5", 1, steps=[False, True]),
        episode("#5", 2, steps=[False, True, True]),
        episode("#6", 3, steps=[True]),
    ]
    report = compute(issues, cards, eps)
    names = [m.name for m in report.measures if m.name.startswith("Pasos")]
    assert names[0].startswith("Pasos fallidos, talla XS") and names[1].startswith("Pasos fallidos, talla M")
    assert pair(report, "Pasos fallidos, talla M") == (2, 5)


def test_measure8_without_sizes_prints_no_data_and_never_a_percentage():
    report = compute([issue(5)], [], [])
    m = measure(report, "Pasos fallidos por talla")
    assert format_result(m) == NO_DATA
    big = compute(
        [issue(n) for n in range(1, 10)],
        [full_card(n, talla="S") for n in range(1, 10)],
        [episode(f"#{n}", n, steps=[False]) for n in range(1, 10)],
    )
    assert format_result(measure(big, "Pasos fallidos, talla S")) == "9 de 9"


# --- Formato: «sin datos» y porcentajes --------------------------------------------------------


def test_denominator_zero_prints_no_data_never_zero_percent():
    for rate in (True, False):
        text = format_result(Measure("x", 0, 0, rate=rate))
        assert text == NO_DATA and "%" not in text
    assert "sin datos" in format_report(compute([], [], []))
    assert "0 %" not in format_report(compute([], [], []))


def test_percentage_only_with_eight_or_more_in_the_denominator():
    assert format_result(Measure("x", 3, 7)) == "3 de 7"
    assert format_result(Measure("x", 0, 7)) == "0 de 7"
    assert format_result(Measure("x", 2, 8)) == "2 de 8 (25 %)"
    assert format_result(Measure("x", 0, 8)) == "0 de 8 (0 %)"


# --- Episodio de cada issue --------------------------------------------------------------------


def test_primary_issue_is_the_first_cited_in_ref():
    assert primary_issue("#79, épica #75") == 79
    assert primary_issue("PR #80, #79") == 79
    assert primary_issue("otro/repo#7, #9") == 9
    assert primary_issue("sin referencia") is None


def test_episode_cited_second_does_not_count_for_that_issue():
    eps = [episode("#79, épica #75", outcome=outcome(prs=5))]
    report = compute([issue(75), issue(79)], [], eps)
    assert pair(report, "PR adicionales") == (4, 1)  # solo #79; #75 no tiene episodio principal


def test_several_episodes_for_an_issue_take_the_outcome_of_the_highest_seq():
    eps = [
        episode("#5", 1, outcome=outcome(prs=1)),
        episode("#5", 7, outcome=outcome(prs=4)),
        episode("#5", 3, outcome=outcome(prs=2)),
    ]
    assert pair(compute([issue(5)], [], eps), "PR adicionales") == (3, 1)


# --- Tokens ------------------------------------------------------------------------------------


def line(message_id: str, model: str = "claude-sonnet-5-5", **usage: int) -> str:
    base = {"input_tokens": 0, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}
    message = {
        "id": message_id,
        "model": model,
        "role": "assistant",
        "usage": {**base, "output_tokens": 0, **usage},
    }
    return json.dumps({"type": "assistant", "message": message})


def write_jsonl(path: Path, lines: Sequence[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_transcript_takes_the_last_usage_of_each_message_id():
    lines = [
        json.dumps({"type": "user", "message": {"role": "user", "content": "hola"}}),
        line(
            "msg_1",
            input_tokens=3,
            cache_creation_input_tokens=100,
            cache_read_input_tokens=1000,
            output_tokens=1,
        ),
        line(
            "msg_1",
            input_tokens=3,
            cache_creation_input_tokens=100,
            cache_read_input_tokens=1000,
            output_tokens=40,
        ),
        line(
            "msg_1",
            input_tokens=3,
            cache_creation_input_tokens=100,
            cache_read_input_tokens=1000,
            output_tokens=90,
        ),
        line(
            "msg_2",
            model="claude-haiku-4-5",
            input_tokens=2,
            cache_creation_input_tokens=10,
            cache_read_input_tokens=500,
            output_tokens=7,
        ),
        "",
        "{linea rota",
        json.dumps({"type": "summary"}),
    ]
    usage = parse_transcript(lines)
    assert (usage.input, usage.cache_creation, usage.cache_read, usage.output) == (5, 110, 1500, 97)
    assert usage.models == {"claude-sonnet-5-5", "claude-haiku-4-5"}
    assert usage.skipped_lines == 1


def test_transcript_ignores_messages_without_usage_or_id():
    lines = [
        json.dumps({"message": {"id": "a", "role": "assistant"}}),
        json.dumps({"message": {"usage": {"output_tokens": 9}}}),
        json.dumps([1, 2]),
    ]
    assert parse_transcript(lines) == TokenUsage()


def test_tokens_per_issue_with_map_overriding_outcome_transcript(tmp_path):
    write_jsonl(tmp_path / "declared.jsonl", [line("a", output_tokens=1)])
    write_jsonl(tmp_path / "mapped.jsonl", [line("a", output_tokens=1), line("a", output_tokens=11)])
    issues = [issue(5), issue(6)]
    eps = [
        episode("#5", outcome=outcome(transcript="declared.jsonl")),
        episode("#6", 2, outcome=outcome()),
    ]
    names = transcript_names([5, 6], eps, {5: "mapped.jsonl", 6: "mapped.jsonl"})
    assert names == {5: "mapped.jsonl", 6: "mapped.jsonl"}
    assert transcript_names([5, 6], eps) == {5: "declared.jsonl"}
    tokens = {5: parse_transcript((tmp_path / "mapped.jsonl").read_text().splitlines())}
    report = compute(issues, [full_card(5)], eps, tokens=tokens)
    assert report.tokens is not None and [r.issue for r in report.tokens] == [5]
    assert report.tokens[0].usage is not None and report.tokens[0].usage.output == 11
    text = format_report(report)
    assert "| #5 | S | 0 | 0 | 0 | 11 | claude-sonnet-5-5 |" in text
    assert "#6" not in text.split("Tokens por issue")[1]  # sin transcripción declarada: sin fila


def test_map_for_an_issue_outside_the_population_is_ignored():
    assert transcript_names([5], [], {99: "x.jsonl"}) == {}


def test_missing_transcript_file_is_reported_not_zero_and_not_an_error(tmp_path):
    snap = write_snapshot(tmp_path / "snap", [issue(5)], [full_card(5)])
    eps = [episode("#5", outcome=outcome(transcript="no-existe.jsonl"))]
    out = run(snap, eps, transcripts=tmp_path)
    assert out[0] == 0
    assert NOT_FOUND in out[1] and "| #5 | S | 0 |" not in out[1]


def test_without_transcripts_tokens_row_says_not_measured():
    text = format_report(compute([issue(5)], [full_card(5)], []))
    assert NOT_MEASURED in text.split("Tokens por issue")[1]


def test_transcripts_given_but_none_declared_prints_no_data(tmp_path):
    text = format_report(compute([issue(5)], [full_card(5)], [], tokens={}))
    assert NO_DATA in text.split("Tokens por issue")[1]


def test_unreadable_lines_are_flagged_in_the_row(tmp_path):
    write_jsonl(tmp_path / "t.jsonl", [line("a", output_tokens=2), "{roto"])
    snap = write_snapshot(tmp_path / "snap", [issue(5)], [full_card(5)])
    out = run(snap, [], transcripts=tmp_path, mapping={5: "t.jsonl"})
    assert "líneas ilegibles: 1" in out[1]


# --- Lectura y subcomando ----------------------------------------------------------------------


def write_snapshot(directory: Path, issues, cards) -> Path:
    directory.mkdir(parents=True)
    (directory / "issues.json").write_text(json.dumps(issues), encoding="utf-8")
    (directory / "items.json").write_text(json.dumps({"items": cards}), encoding="utf-8")
    return directory


def run(snapshot: Path | None, eps, **kw):
    import io

    out, err = io.StringIO(), io.StringIO()
    code = run_pilot(since=5, snapshot=snapshot, episodes=eps, out=out, err=err, **kw)
    return code, out.getvalue(), err.getvalue()


def test_run_pilot_from_snapshot_exits_zero_and_prints_the_table(tmp_path):
    snap = write_snapshot(tmp_path / "snap", [issue(5), issue(9, "OPEN")], [full_card(5)])
    code, out, err = run(snap, [episode("#5", outcome=outcome())])
    assert code == 0 and err == ""
    assert "Población (n = 1): #5" in out and "| Medida |" in out and NOT_MEASURED in out


def test_run_pilot_never_interprets():
    text = format_report(compute([issue(5)], [full_card(5)], [episode("#5", outcome=outcome())]))
    for word in ("éxito", "validado", "validada", "conclusión", "confirma"):
        assert word not in text.lower()


def fake_gh(login: str = "cherrera0001", project_error: str | None = None):
    def runner(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
        def done(stdout: str = "", stderr: str = "", code: int = 0):
            return subprocess.CompletedProcess([], code, stdout, stderr)

        if args[:2] == ["api", "user"]:
            return done(login + "\n")
        if args[0] == "project":
            if project_error:
                return done(stderr=project_error, code=1)
            return done(json.dumps({"items": [full_card(5)]}))
        if args[0] == "issue":
            return done(json.dumps([issue(5)]))
        if args[:2] == ["api", "graphql"]:
            return done(json.dumps({"data": {"repository": {"issues": {"nodes": []}}}}))
        raise AssertionError(args)

    return runner


def test_failed_read_exits_two_with_the_board_message():
    import io

    out, err = io.StringIO(), io.StringIO()
    runner = fake_gh("vinculaterritorio", "GraphQL: Could not resolve to a ProjectV2")
    code = run_pilot(since=5, snapshot=None, episodes=[], runner=runner, out=out, err=err)
    assert code == 2 and out.getvalue() == ""
    assert "no se pudo leer la fuente" in err.getvalue() and "vinculaterritorio" in err.getvalue()


def test_incomplete_snapshot_exits_two(tmp_path):
    (tmp_path / "issues.json").write_text("[]", encoding="utf-8")
    code, out, err = run(tmp_path, [])
    assert code == 2 and out == "" and "instantánea incompleta" in err


def test_run_pilot_reads_github_with_a_fake_runner():
    import io

    out = io.StringIO()
    code = run_pilot(since=5, snapshot=None, episodes=[], runner=fake_gh(), out=out, err=io.StringIO())
    assert code == 0 and "Población (n = 1): #5" in out.getvalue()


def test_parse_map():
    assert parse_map(["77=agent-a.jsonl", "78 = b.jsonl"]) == {77: "agent-a.jsonl", 78: "b.jsonl"}
    for bad in ("77", "x=a.jsonl", "77="):
        with pytest.raises(ValueError):
            parse_map([bad])


def test_devlog_pilot_subcommand(tmp_path, monkeypatch, capsys):
    snap = write_snapshot(tmp_path / "snap", [issue(5)], [full_card(5)])
    monkeypatch.setattr(
        sys, "argv", ["devlog", "pilot", "--since", "5", "--until", "5", "--snapshot", str(snap)]
    )
    with pytest.raises(SystemExit) as exc:
        devlog.main()
    assert exc.value.code == 0
    assert "Población (n = 1): #5" in capsys.readouterr().out


def test_devlog_pilot_rejects_a_malformed_map(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["devlog", "pilot", "--since", "5", "--map", "77"])
    with pytest.raises(SystemExit) as exc:
        devlog.main()
    assert exc.value.code == 2
    assert "--map espera" in capsys.readouterr().err


def test_devlog_pilot_exit_two_when_unreadable(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["devlog", "pilot", "--since", "5", "--snapshot", str(tmp_path)])
    with pytest.raises(SystemExit) as exc:
        devlog.main()
    assert exc.value.code == 2
