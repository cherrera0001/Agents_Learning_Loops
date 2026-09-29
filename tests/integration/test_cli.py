"""CLI en proceso (cubre main.py sin subprocess) (#7)."""

import json
import logging
import sys

import pytest

from associative_agent_loop import main as cli


def run_cli(monkeypatch, capsys, *args):
    monkeypatch.setattr(sys, "argv", ["aal-benchmark", *args])
    cli.main()
    return capsys.readouterr()


def test_text_report_shows_every_scenario(monkeypatch, capsys):
    out = run_cli(monkeypatch, capsys, "--episodes", "5").out
    for title in ("Escenario 1", "Escenario 2", "Escenario 3", "Escenario 4"):
        assert title in out
    assert "fallos repetidos tras el primer episodio: 0" in out
    assert "weather_api_v1✗ → weather_api_v2✓" in out


def test_json_report_matches_the_library(monkeypatch, capsys):
    out = run_cli(monkeypatch, capsys, "--json", "--episodes", "5", "--seed", "3").out
    report = json.loads(out)
    assert report == cli.benchmark(5, 3)
    assert set(report["scenarios"]) == {"same_goal", "paraphrase", "flaky", "cross_domain"}


@pytest.mark.parametrize("flag, level", [("-v", logging.INFO), ("-vv", logging.DEBUG)])
def test_verbose_flags_configure_logging(monkeypatch, capsys, flag, level):
    calls = []
    monkeypatch.setattr(logging, "basicConfig", lambda **kw: calls.append(kw))
    run_cli(monkeypatch, capsys, flag, "--json", "--episodes", "2")
    assert calls and calls[0]["level"] == level
