"""``devlog base-rates``: cuentas sobre un conjunto de episodios FIJO escrito aquí, no sobre los reales.

La prueba de recall de ``main`` llegó a pasar con un margen de 0,01 sobre los episodios reales (#162):
nada de aquí depende de ``learning/episodes/``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from scripts import base_rates, devlog


def _step(action: str, ok: bool, text: str = "", key: str = "error") -> dict[str, Any]:
    step: dict[str, Any] = {"action": action, "success": ok}
    if text:
        step[key] = text
    return step


def _ep(seq: int, *steps: dict[str, Any]) -> dict[str, Any]:
    return {"seq": seq, "id": f"issue-{seq}", "goal": "g", "steps": list(steps), "lessons": []}


# 6 episodios, 14 pasos, 6 fallidos: 3 de «Entorno», 2 de «Texto» y 1 sin clase.
EPISODES = [
    _ep(
        1,
        _step("recall_memory", True),
        _step("edit_module", False, "heredoc largo en Git Bash"),
        _step("write_tests", True),
    ),
    _ep(
        2,
        _step("recall_memory", False, "afirmó sin fuente"),
        _step("edit_module", True),
        _step("write_tests", False, "algo que ninguna clase nombra"),
    ),
    _ep(3, _step("recall_memory", True), _step("edit_module", False, "un heredoc", key="note")),
    _ep(5, _step("recall_memory", True), _step("edit_module", True)),
    _ep(6, _step("recall_memory", False, "heredoc"), _step("edit_module", True)),
    _ep(9, _step("recall_memory", True), _step("write_tests", False, "afirmó de más")),
]

CLASSES = {
    "version": 1,
    "classes": [
        {"name": "Entorno", "patterns": ["heredoc"]},
        {"name": "Texto", "patterns": ["afirm"]},
    ],
}


@pytest.fixture
def classes_file(tmp_path: Path) -> Path:
    path = tmp_path / "clases.json"
    path.write_text(json.dumps(CLASSES), encoding="utf-8")
    return path


def _compute(hasta: int | None = None, episodes: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return base_rates.compute(EPISODES if episodes is None else episodes, _classes(), hasta)


def _classes() -> list[tuple[str, list[re.Pattern[str]]]]:
    return [(c["name"], [re.compile(p, re.IGNORECASE) for p in c["patterns"]]) for c in CLASSES["classes"]]


def test_counts_by_action() -> None:
    result = _compute()
    assert (result["episodes"], result["steps"], result["failed_steps"]) == (6, 14, 6)
    by_action = {r["action"]: (r["failed"], r["total"]) for r in result["by_action"]}
    assert by_action == {"recall_memory": (2, 6), "edit_module": (2, 5), "write_tests": (2, 3)}
    recall = next(r for r in result["by_action"] if r["action"] == "recall_memory")
    assert recall["rate"] == pytest.approx(1 / 3, abs=1e-4)
    assert recall["ci95"] == pytest.approx([0.0969, 0.7000], abs=2e-4)


def test_by_action_is_sorted_by_failures_then_name() -> None:
    names = [r["action"] for r in _compute()["by_action"]]
    assert names == ["edit_module", "recall_memory", "write_tests"]


def test_counts_by_class_and_unclassified() -> None:
    result = _compute()
    by_class = {c["class"]: (c["failed"], c["total"], c["episodes"]) for c in result["by_class"]}
    assert by_class == {"Entorno": (3, 6, 3), "Texto": (2, 6, 2)}
    assert (result["unclassified"]["failed"], result["unclassified"]["total"]) == (1, 6)
    assert result["unclassified"]["rate"] == pytest.approx(1 / 6, abs=1e-4)


def test_a_step_goes_to_the_first_matching_class_and_reads_error_and_note() -> None:
    both = _step("edit_module", False, "heredoc que afirmó algo")
    assert base_rates.classify(both, _classes()) == "Entorno"
    note_only = _step("edit_module", False, "afirmó", key="note")
    assert base_rates.classify(note_only, _classes()) == "Texto"
    assert base_rates.classify(_step("edit_module", False, "nada"), _classes()) is None
    assert base_rates.classify(_step("edit_module", False), _classes()) is None


def test_classification_ignores_case() -> None:
    assert base_rates.classify(_step("a", False, "HEREDOC"), _classes()) == "Entorno"


def test_thirds_split_the_history_in_three_consecutive_groups() -> None:
    thirds = _compute()["by_third"]
    assert [(t["third"], t["seq_from"], t["seq_to"], t["failed"], t["total"]) for t in thirds] == [
        (1, 1, 2, 3, 6),
        (2, 3, 5, 1, 4),
        (3, 6, 9, 2, 4),
    ]


def test_thirds_follow_seq_even_when_episodes_arrive_unordered() -> None:
    result = _compute(episodes=list(reversed(EPISODES)))
    assert [(t["seq_from"], t["seq_to"]) for t in result["by_third"]] == [(1, 2), (3, 5), (6, 9)]


def test_hasta_excludes_that_episode_and_the_later_ones() -> None:
    # El episodio 5 existe y no tiene fallos: con «<=» se contarían 10 pasos, con «<» ocho.
    result = _compute(hasta=5)
    assert (result["episodes"], result["steps"], result["failed_steps"]) == (3, 8, 4)
    assert result["hasta"] == 5
    by_action = {r["action"]: (r["failed"], r["total"]) for r in result["by_action"]}
    assert by_action == {"recall_memory": (1, 3), "edit_module": (2, 3), "write_tests": (1, 2)}
    # Un seq que no existe excluye igualmente los posteriores.
    assert _compute(hasta=4)["episodes"] == 3
    assert _compute(hasta=1)["episodes"] == 0
    assert _compute(hasta=10)["episodes"] == 6


def test_empty_history_does_not_crash() -> None:
    result = _compute(hasta=1)
    assert result["steps"] == 0
    assert result["unclassified"]["rate"] is None and result["unclassified"]["ci95"] is None
    assert [t["seq_from"] for t in result["by_third"]] == [None, None, None]
    text = base_rates.format_report(result)
    assert "0 episodios, 0 pasos, 0 fallidos" in text


def test_wilson_interval() -> None:
    assert base_rates.wilson(0, 0) is None
    low, high = base_rates.wilson(5, 10) or (0.0, 0.0)
    assert (low, high) == pytest.approx((0.2366, 0.7634), abs=1e-3)
    low0, high0 = base_rates.wilson(0, 10) or (1.0, 0.0)
    assert low0 == 0.0 and high0 == pytest.approx(0.2775, abs=1e-3)
    low1, high1 = base_rates.wilson(10, 10) or (0.0, 0.0)
    assert high1 == 1.0 and low1 == pytest.approx(0.7225, abs=1e-3)


def test_report_has_the_three_tables_and_says_what_is_not_countable() -> None:
    text = base_rates.format_report(_compute())
    for header in ("Por acción", "Por clase de fallo", "Por tercios de la historia"):
        assert header in text
    assert "sin clase" in text and "Entorno" in text
    assert "no contable" in text and "CI" in text


def test_cli_prints_tables_and_exits_zero(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    classes_file: Path,
) -> None:
    monkeypatch.setattr(devlog, "load_episodes", lambda *_a, **_k: EPISODES)
    monkeypatch.setattr("sys.argv", ["devlog", "base-rates", "--clases", str(classes_file)])
    with pytest.raises(SystemExit) as exit_info:
        devlog.main()
    assert exit_info.value.code == 0
    out = capsys.readouterr().out
    assert "6 episodios, 14 pasos, 6 fallidos" in out
    assert "recall_memory" in out and "Entorno" in out and "tercio 3" in out


def test_cli_json_and_hasta_match_compute(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    classes_file: Path,
) -> None:
    monkeypatch.setattr(devlog, "load_episodes", lambda *_a, **_k: EPISODES)
    argv = ["devlog", "base-rates", "--json", "--hasta", "5", "--clases", str(classes_file)]
    monkeypatch.setattr("sys.argv", argv)
    with pytest.raises(SystemExit) as exit_info:
        devlog.main()
    assert exit_info.value.code == 0
    assert json.loads(capsys.readouterr().out) == _compute(hasta=5)


def test_cli_reports_unreadable_classes_with_exit_two(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(devlog, "load_episodes", lambda *_a, **_k: EPISODES)
    for content in (None, "no es json", json.dumps({"classes": [{"name": "X", "patterns": ["("]}]})):
        path = tmp_path / "mala.json"
        path.unlink(missing_ok=True)
        if content is not None:
            path.write_text(content, encoding="utf-8")
        monkeypatch.setattr("sys.argv", ["devlog", "base-rates", "--clases", str(path)])
        with pytest.raises(SystemExit) as exit_info:
            devlog.main()
        assert exit_info.value.code == 2
        captured = capsys.readouterr()
        assert "no se pudo leer la clasificación" in captured.err
        assert captured.out == ""


def test_versioned_classification_file_is_well_formed() -> None:
    """Estructura del archivo real, sin contar nada sobre los episodios reales."""
    data = json.loads(base_rates.CLASSES_PATH.read_text("utf-8"))
    names = [c["name"] for c in data["classes"]]
    assert len(names) == len(set(names)) == 8
    assert {"Entorno", "Prueba frágil", "Defecto de lógica o de diseño propio"} <= set(names)
    classes = base_rates.load_classes()
    assert [n for n, _ in classes] == names
    assert all(patterns for _, patterns in classes)
