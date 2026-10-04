"""Reglas fijadas de la campana A/B/C/D, sin tareas reales y sin modelo."""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path

from scripts.kaggle_campana import (
    EXIT_INVALID,
    EXIT_OPEN,
    FRASE_PLACEBO,
    HERRAMIENTAS_GRAFO,
    INSTRUCCION_D,
    buscar_fuga,
    desenlace,
    ids_senuelo,
    main,
    resuelve_mayoria_estricta,
    texto_placebo,
)

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
PARAMS = ROOT / "experiments/gemma_developer_agent/preregistro/campana_abcd.json"
PREREG = ROOT / "docs/preregistration/kaggle-campaign-abcd.md"


def test_comprobar_sigue_abierto() -> None:
    assert main(["comprobar", "--parametros", str(PARAMS)]) == EXIT_OPEN


def test_la_instruccion_de_d_es_la_misma_en_el_json_y_en_el_documento() -> None:
    datos = json.loads(PARAMS.read_text(encoding="utf-8"))
    assert datos["fijos"]["instruccion_d"] == INSTRUCCION_D
    assert datos["fijos"]["frase_placebo"] == FRASE_PLACEBO
    assert INSTRUCCION_D in PREREG.read_text(encoding="utf-8")
    assert all(nombre in INSTRUCCION_D for nombre in HERRAMIENTAS_GRAFO)
    assert all(nombre not in FRASE_PLACEBO for nombre in HERRAMIENTAS_GRAFO)


def test_mayoria_estricta_exige_mas_aciertos_que_fallos() -> None:
    assert resuelve_mayoria_estricta([True]) is True
    assert resuelve_mayoria_estricta([False]) is False
    assert resuelve_mayoria_estricta([True, False]) is False
    assert resuelve_mayoria_estricta([True, True]) is True
    assert resuelve_mayoria_estricta([True, True, False]) is True
    assert resuelve_mayoria_estricta([True, False, False]) is False


def test_desenlace_cubre_igualdad_como_sin_diferencia() -> None:
    m = Fraction(6, 40)
    assert desenlace(7, 40, m) == "apoyada"
    assert desenlace(6, 40, m) == "sin_diferencia"
    assert desenlace(-7, 40, m) == "refutada"
    assert desenlace(0, 40, m) == "sin_diferencia"


def test_placebo_tiene_la_longitud_pedida_y_no_nombra_el_grafo() -> None:
    texto = texto_placebo(len(FRASE_PLACEBO) + 3)
    assert len(texto) == len(FRASE_PLACEBO) + 3
    assert texto.endswith("   ")
    assert all(nombre not in texto for nombre in HERRAMIENTAS_GRAFO)


def test_senuelos_toman_uno_de_cada_cinco_en_orden() -> None:
    ids = [f"repo__repo-{i:02d}" for i in range(12)]
    assert ids_senuelo(list(reversed(ids))) == [ids[0], ids[5], ids[10]]


def test_fuga_encuentra_un_instance_id_de_prueba_y_calla_si_no_esta(tmp_path: Path) -> None:
    subconjunto = {"train": ["repo__repo-1"], "test": ["repo__repo-9"]}
    limpio = tmp_path / "limpio"
    limpio.mkdir()
    (limpio / "episodio.json").write_text('{"instance_id": "repo__repo-1"}\n', encoding="utf-8")
    assert buscar_fuga(subconjunto["test"], [limpio]) == []

    sucio = tmp_path / "skills"
    sucio.mkdir()
    (sucio / "SKILL.md").write_text("visto en repo__repo-9\n", encoding="utf-8")
    assert buscar_fuga(subconjunto["test"], [sucio]) == [("repo__repo-9", (sucio / "SKILL.md").as_posix())]

    ruta = tmp_path / "subconjunto.json"
    ruta.write_text(json.dumps(subconjunto), encoding="utf-8")
    assert main(["fuga", "--subconjunto", str(ruta), "--raiz", str(limpio)]) == 0
    assert main(["fuga", "--subconjunto", str(ruta), "--raiz", str(sucio)]) == EXIT_INVALID
