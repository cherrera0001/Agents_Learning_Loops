"""La estructura simulada del chequeo previo adjunta la variante del modelo que declara el notebook.

Antes del 2026-10-18 el simulador fijaba siempre el directorio del 31B: la guardia de un brazo con otra
variante (12B) se detenía en la simulación aunque en Kaggle encontraría su modelo. Ahora la variante se
lee de ``model_sources`` del ``kernel-metadata.json`` (una sola por envío, regla oficial).
"""

from __future__ import annotations

from pathlib import Path

from scripts.kaggle_preflight import MODELO, arbol_de_entrada, modelo_de_metadatos

M12B = "gemma-4-12b-it-qat-w4a16-ct"


def test_sin_model_sources_usa_la_variante_por_defecto() -> None:
    assert modelo_de_metadatos({}) == MODELO
    assert modelo_de_metadatos({"model_sources": []}) == MODELO
    assert modelo_de_metadatos({"model_sources": "no es lista"}) == MODELO
    assert modelo_de_metadatos("no es dict") == MODELO


def test_una_variante_declarada_se_lee_del_kernel_metadata() -> None:
    assert modelo_de_metadatos({"model_sources": [f"google/gemma-4/Other/{M12B}/2"]}) == M12B
    assert modelo_de_metadatos({"model_sources": [f"google/gemma-4/Other/{MODELO}/2"]}) == MODELO


def test_dos_variantes_o_una_forma_ajena_caen_al_valor_por_defecto() -> None:
    dos = [f"google/gemma-4/Other/{M12B}/2", f"google/gemma-4/Other/{MODELO}/2"]
    assert modelo_de_metadatos({"model_sources": dos}) == MODELO
    assert modelo_de_metadatos({"model_sources": ["otro/modelo/x/y/1"]}) == MODELO


def test_el_arbol_simulado_crea_el_directorio_de_la_variante(tmp_path: Path) -> None:
    arbol_de_entrada(tmp_path / "a", "lotes", modelo=M12B)
    assert (tmp_path / "a" / "models" / "google" / "gemma-4" / "other" / M12B / "2" / "config.json").exists()
    assert not (tmp_path / "a" / "models" / "google" / "gemma-4" / "other" / MODELO).exists()
    arbol_de_entrada(tmp_path / "b", "plana")
    por_defecto = tmp_path / "b" / "models" / "google" / "gemma-4" / "other" / MODELO / "2"
    assert (por_defecto / "config.json").exists()
