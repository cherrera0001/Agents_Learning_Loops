"""``offline_calibration``: replay, métricas, selección y decisión sobre episodios FIJOS escritos aquí.

Nada depende de ``learning/episodes/`` (el conjunto real cambia con cada issue); los episodios
reales solo se usan en la corrida publicada, cuyo agregado va a ``results/offline-calibration-v1/``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts import offline_calibration as oc
from scripts.base_rates import load_classes

CLASSES_JSON = {
    "version": 1,
    "classes": [
        {"name": "Entorno", "patterns": ["heredoc"]},
        {"name": "Texto", "patterns": ["sin fuente"]},
    ],
}


def _step(action: str, ok: bool, text: str = "") -> dict[str, Any]:
    step: dict[str, Any] = {"action": action, "success": ok}
    if text:
        step["error"] = text
    return step


def _ep(seq: int, goal: str, steps: list[dict[str, Any]], lessons: list[str]) -> dict[str, Any]:
    return {"seq": seq, "id": f"ep-{seq}", "goal": goal, "steps": steps, "lessons": lessons}


# El 1 falla con un «heredoc» y deja lecciones que lo nombran; el 2 repite la causa con una meta
# sin tokens compartidos con la meta del 1 (la única vía de siembra es la similitud sobre las
# etiquetas de las lecciones/error, que con embedder léxico queda por debajo de τ_seed ≥ 0.25).
# El 3 falla sin clase; el 4 falla «sin fuente» antes de que exista lección de esa clase; el 5
# deja la lección «sin fuente»; el 6 la repite (mismo diseño de siembra que el 2). Con 10
# episodios y frac 0.7, la validación queda sin fallos; por eso el test de corrida usa frac 0.5.
EPISODES = [
    _ep(
        1,
        "arreglar script despliegue",
        [
            _step("edit_module", False, "heredoc largo en Git Bash rompe el script"),
            _step("write_tests", True),
        ],
        ["Evitar heredoc largo en Git Bash: escribir archivo temporal"],
    ),
    _ep(
        2,
        "reparar pipeline roto heredoc",
        [_step("edit_module", False, "otro heredoc en Git Bash"), _step("edit_module", True)],
        [],
    ),
    _ep(3, "tests modulo precios", [_step("write_tests", False, "fallo que ninguna clase nombra")], []),
    _ep(4, "redactar informe resultados", [_step("update_docs", False, "afirmó sin fuente")], []),
    _ep(
        5,
        "documentar evidencia experimento",
        [_step("update_docs", True)],
        ["No afirmar sin fuente: citar recibo o comando"],
    ),
    _ep(
        6,
        "acta final campaña afirmar",
        [_step("update_docs", False, "afirmó de nuevo sin fuente")],
        [],
    ),
    _ep(7, "ajuste menor readme", [_step("update_docs", True)], []),
    _ep(8, "seguimiento tablero", [_step("update_docs", True)], []),
    _ep(9, "cierre tarjeta", [_step("confirm_closure", True)], []),
    _ep(10, "apertura siguiente issue", [_step("estimate_issue", True)], []),
]


@pytest.fixture
def classes(tmp_path: Path) -> oc.Classes:
    path = tmp_path / "clases.json"
    path.write_text(json.dumps(CLASSES_JSON), encoding="utf-8")
    return load_classes(path)


def test_split_windows_is_temporal_and_parametric() -> None:
    cal, val = oc.split_windows(EPISODES, 0.7)
    assert [e["seq"] for e in cal] == [1, 2, 3, 4, 5, 6, 7]
    assert [e["seq"] for e in val] == [8, 9, 10]
    cal, val = oc.split_windows(EPISODES, 0.5)
    assert len(cal) == 5 and len(val) == 5
    with pytest.raises(ValueError):
        oc.split_windows(EPISODES, 1.0)


def test_replay_marks_known_hit_and_repeated(classes: oc.Classes) -> None:
    rows = oc.replay(EPISODES, classes, eta_h=0.3, alpha=0.7, tau_seed=0.25)
    by_seq = {r["seq"]: r for r in rows}
    # Con τ_seed = 0.25 la siembra por similitud no dispara (0.19 < 0.25): el fallo «heredoc»
    # del episodio 2 es causa conocida (lección del 1) pero no visible → repetido.
    assert by_seq[2]["class"] == "Entorno"
    assert by_seq[2]["known"] is True
    assert by_seq[2]["hit_visible"] is False
    assert by_seq[2]["repeated"] is True
    # El «sin clase» del 3 nunca cuenta como conocido.
    assert by_seq[3]["class"] is None
    assert by_seq[3]["known"] is False
    assert by_seq[3]["repeated"] is False
    # El «sin fuente» del 4 es anterior a la lección del 5: causa aún desconocida.
    assert by_seq[4]["class"] == "Texto"
    assert by_seq[4]["known"] is False
    # El «sin fuente» del 6 es posterior a la lección del 5: conocido, pero invisible a τ = 0.25.
    assert by_seq[6]["class"] == "Texto"
    assert by_seq[6]["known"] is True
    assert by_seq[6]["repeated"] is True


def test_visibility_depends_on_tau_seed_not_on_alpha(classes: oc.Classes) -> None:
    # Con τ_seed bajo la similitud (0.17–0.20) sí siembra las lecciones: dejan de repetirse.
    low = {r["seq"]: r for r in oc.replay(EPISODES, classes, eta_h=0.3, alpha=0.7, tau_seed=0.1)}
    assert low[2]["hit_visible"] is True and low[2]["repeated"] is False
    assert low[6]["hit_visible"] is True and low[6]["repeated"] is False
    # Con el embedder léxico, α no mueve nada: ambos canales computan el mismo coseno.
    a = oc.replay(EPISODES, classes, eta_h=0.3, alpha=0.5, tau_seed=0.25)
    b = oc.replay(EPISODES, classes, eta_h=0.3, alpha=0.9, tau_seed=0.25)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_summarize_exposes_all_denominators(classes: oc.Classes) -> None:
    rows = oc.replay(EPISODES, classes, eta_h=0.3, alpha=0.7, tau_seed=0.25)
    metrics = oc.summarize(rows, n_episodes=len(EPISODES))
    assert metrics["episodes"] == 10
    assert metrics["failures"] == 5  # seqs 1, 2, 3, 4, 6
    assert metrics["unclassified"]["failed"] == 1
    assert metrics["known_cause"] == 2  # seqs 2 y 6
    assert metrics["repeated_known_cause"]["failed"] == 2
    assert metrics["repeated_known_cause"]["total"] == 2
    assert metrics["repeated_all_failures"]["failed"] == 2
    assert metrics["repeated_all_failures"]["total"] == 5


def test_select_best_uses_calibration_window() -> None:
    def cfg(eta_h: float, cal_rate: float, cal_sens: float) -> dict[str, Any]:
        return {
            "eta_h": eta_h,
            "alpha": 0.7,
            "tau_seed": 0.25,
            "windows": {
                "calibration": {
                    "repeated_known_cause": {"rate": cal_rate},
                    "repeated_all_failures": {"rate": cal_sens},
                }
            },
        }

    # Gana la de menor tasa primaria en calibración aunque otra sea mejor en validación.
    configs = [cfg(0.3, 0.5, 0.4), cfg(0.1, 0.4, 0.9), cfg(0.5, 0.4, 0.5)]
    assert oc.select_best(configs)["eta_h"] == 0.5  # empate 0.4 primario, gana la sensibilidad
    assert oc.select_best(configs[:2])["eta_h"] == 0.1  # empate roto por |η_h−0.3|
    with pytest.raises(KeyError):
        oc.select_best([{**configs[0], "windows": {"validation": {}}}])


def test_decide_applies_the_preregistered_threshold() -> None:
    assert oc.decide(5.0) is True
    assert oc.decide(4.9) is False
    assert oc.decide(None) is False
    assert oc.decide(-2.0) is False


def test_replay_is_deterministic(classes: oc.Classes) -> None:
    first = oc.replay(EPISODES, classes, eta_h=0.1, alpha=0.9, tau_seed=0.4)
    second = oc.replay(EPISODES, classes, eta_h=0.1, alpha=0.9, tau_seed=0.4)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_run_calibration_selects_on_calibration_and_writes_report(
    tmp_path: Path, classes: oc.Classes
) -> None:
    aggregates = oc.run_calibration(EPISODES, classes, calibrate_frac=0.5)
    assert aggregates["episodes"] == 10
    assert len(aggregates["configs"]) == 27
    assert sum(c["is_default"] for c in aggregates["configs"]) == 1
    # En calibración τ_seed = 0.1 elimina los fallos repetidos; los desempates fijados en el
    # pre-registro eligen η_h = 0.3 y α = 0.7 (canales léxicos idénticos).
    assert aggregates["selection"]["winner"] == {"eta_h": 0.3, "alpha": 0.7, "tau_seed": 0.1}
    decision = aggregates["comparison"]["decision"]
    assert decision["note"].endswith("la decisión es del dueño.")
    out = tmp_path / "results"
    out.mkdir()
    target = out / "aggregates.json"
    target.write_text(json.dumps(aggregates, ensure_ascii=False, indent=2), encoding="utf-8")
    report = oc.format_report(aggregates)
    assert "## Denominadores por ventana" in report
    assert "McNemar" in report
    # La ganadora muestra su tasa de calibración junto a la de validación.
    assert "en calibración:" in report
