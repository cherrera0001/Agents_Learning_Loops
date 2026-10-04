"""Reglas fijadas de la campana A/B/C/D, sin tareas reales y sin modelo."""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path

import pytest

from scripts.kaggle_campana import (
    EXIT_INVALID,
    EXIT_OPEN,
    FRASE_PLACEBO,
    HERRAMIENTAS_GRAFO,
    INSTRUCCION_D,
    buscar_fuga,
    corridas_d_g6,
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


def test_g6_no_reduce_por_debajo_del_minimo_de_b_y_c() -> None:
    from scripts.kaggle_campana import CampanaError

    with pytest.raises(CampanaError, match="no caben los mínimos"):
        corridas_d_g6(0, 1)
    with pytest.raises(CampanaError, match="no caben los mínimos"):
        corridas_d_g6(1, 1)
    assert corridas_d_g6(2, 1) == 0
    assert corridas_d_g6(3, 1) == 1


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
    tasks = tmp_path / "tasks.jsonl"
    tasks.write_text(
        json.dumps({"instance_id": "repo__repo-9", "problem_statement": "A" * 100}), encoding="utf-8"
    )
    assert main(["fuga", "--subconjunto", str(ruta), "--tasks", str(tasks), "--raiz", str(limpio)]) == 0
    assert (
        main(["fuga", "--subconjunto", str(ruta), "--tasks", str(tasks), "--raiz", str(sucio)])
        == EXIT_INVALID
    )


def test_fuga_detecta_enunciado_de_prueba_sin_id(tmp_path: Path) -> None:
    statement = (
        "This exact test task description is sufficiently long to distinguish it from ordinary shared "
        + "wording."
    )
    ids = ["repo__repo-9"]
    tasks = tmp_path / "tasks.jsonl"
    tasks.write_text(json.dumps({"instance_id": ids[0], "problem_statement": statement}), encoding="utf-8")
    from scripts.kaggle_campana import cargar_textos_test

    text = cargar_textos_test(tasks, ids)
    artifact = tmp_path / "episode.json"
    artifact.write_text(json.dumps({"notes": statement}), encoding="utf-8")
    assert buscar_fuga(ids, [artifact], text) == [(ids[0], artifact.as_posix())]


def test_fuga_falla_cerrada_si_archivo_revisado_tiene_utf8_invalido(tmp_path: Path) -> None:
    from scripts.kaggle_campana import CampanaError

    artifact = tmp_path / "corrupt.json"
    artifact.write_bytes(b"\xff")
    with pytest.raises(CampanaError, match="no se pudo revisar"):
        buscar_fuga(["repo__repo-9"], [artifact])


def test_fuga_falla_cerrada_si_no_puede_leer_archivo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from scripts.kaggle_campana import CampanaError

    artifact = tmp_path / "unreadable.md"
    artifact.write_text("contenido", encoding="utf-8")
    original = Path.read_text

    def fail_on_target(self: Path, *args: object, **kwargs: object) -> str:
        if self == artifact:
            raise PermissionError("simulated read failure")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fail_on_target)
    with pytest.raises(CampanaError, match="no se pudo revisar"):
        buscar_fuga(["repo__repo-9"], [artifact])


def test_cierre_rechaza_formato_y_procedencia_falsos_de_parametros(tmp_path: Path) -> None:
    from scripts.kaggle_campana import CampanaError, abiertos_pendientes, validar_fijos

    data = json.loads(PARAMS.read_text(encoding="utf-8"))
    validar_fijos(data)
    data["abiertos"]["subconjunto"]["valor"] = {"ruta": "missing.json", "sha256": "0" * 64}
    with pytest.raises(CampanaError, match=r"no se pudo leer|SHA-256|versionada y limpia"):
        abiertos_pendientes(data)
    data = json.loads(PARAMS.read_text(encoding="utf-8"))
    data["fijos"]["alfa"] = True
    with pytest.raises(CampanaError, match="alfa"):
        validar_fijos(data)


def test_fuente_hash_correcto_pero_no_versionada_se_rechaza(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import hashlib

    import scripts.kaggle_campana as campana

    artifact = tmp_path / "untracked.json"
    artifact.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(campana, "REPO_ROOT", tmp_path)
    citation = {"ruta": artifact.name, "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest()}
    with pytest.raises(campana.CampanaError, match="versionada y limpia"):
        campana._validar_cita(citation, "fixture")


def test_parametros_no_aceptan_etiquetas_g2_g6_escritas_sin_fuentes() -> None:
    from scripts.kaggle_campana import CampanaError, abiertos_pendientes

    data = json.loads(PARAMS.read_text(encoding="utf-8"))
    data["abiertos"]["corridas_por_condicion"]["valor"] = {
        "B": 1,
        "C": 1,
        "D": 0,
        "g2": "bajo",
        "g6": "D_fuera",
    }
    with pytest.raises(CampanaError, match=r"hashes fuente|evidencia G6"):
        abiertos_pendientes(data)


def test_readme_resumen_respeta_umbral_estricto_y_denominador_completo() -> None:
    readme = (ROOT / "experiments/gemma_developer_agent/README.md").read_text(encoding="utf-8")
    prereg = PREREG.read_text(encoding="utf-8")
    assert "≤ M*" in readme
    assert "denominador es el conjunto completo" in readme
    assert "alfa = 0.05" in readme
    assert "Definiciones en circulación" not in readme
    assert "denominador queda fijado antes de ver resultados" in prereg
