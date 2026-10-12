"""Tests de `scripts/kaggle_costo_brazo.py` (#182): la cuenta de horas de cuota y la regla de parada."""

from __future__ import annotations

import pytest

from scripts import kaggle_costo_brazo as kc


def test_al_tope_el_brazo_cuesta_de_11_1_a_13_3_horas() -> None:
    # 5 x 2 x (12 x 304 + carga) / 3600, con la carga menor y la mayor medidas
    assert round(kc.cuota_horas(kc.TAREA_MAS_LARGA_S, kc.CARGA_MINIMA_S), 1) == 11.1
    assert round(kc.cuota_horas(kc.TAREA_MAS_LARGA_S, kc.CARGA_MAXIMA_S), 1) == 13.3


def test_con_las_dos_pasadas_de_base_el_peor_caso_pasa_de_24_horas() -> None:
    peor = kc.proyeccion_del_plan_h(kc.TAREA_MAS_LARGA_S, kc.CARGA_MAXIMA_S)
    assert round(peor, 1) == 24.5
    assert peor > kc.TOPE_DEL_PLAN_H
    assert kc.proyeccion_del_plan_h(kc.TAREA_MAS_LARGA_S, kc.CARGA_MINIMA_S) < kc.TOPE_DEL_PLAN_H


def test_la_cuenta_es_lineal_en_porciones_y_en_factor() -> None:
    una = kc.cuota_horas(200, 500, porciones=1)
    assert kc.cuota_horas(200, 500, porciones=5) == pytest.approx(5 * una)
    assert kc.cuota_horas(200, 500, factor=2.25) == pytest.approx(kc.cuota_horas(200, 500) * 2.25 / 2.0)
    assert kc.cuota_horas(200, 500, tareas=0) == pytest.approx(5 * 2.0 * 500 / 3600)


def test_la_regla_detiene_si_la_media_pasa_de_240_s() -> None:
    d = kc.tras_la_primera_porcion(240.1, kc.CARGA_MINIMA_S)
    assert not d.lanzar_el_resto and "240" in d.motivo and "media" in d.motivo


def test_con_las_constantes_actuales_la_media_detiene_antes_que_las_24_horas() -> None:
    # a 240 s y con la carga mayor: 5 x 2 x (12 x 240 + 1142) / 3600 + 11,2 = 22,4 h, que no pasa de 24
    d = kc.tras_la_primera_porcion(240.0, kc.CARGA_MAXIMA_S)
    assert d.lanzar_el_resto and round(d.proyeccion_h, 1) == 22.4


def test_la_regla_detiene_si_la_proyeccion_pasa_de_24_h_aunque_la_media_no() -> None:
    # media de 240 s (no la pasa) con unas pasadas de base de 14 h: 11,2 + 14 = 25,2 h
    d = kc.tras_la_primera_porcion(240.0, kc.CARGA_MAXIMA_S, base_h=14.0)
    assert d.proyeccion_h > 24.0
    assert not d.lanzar_el_resto and "proyección" in d.motivo


def test_la_regla_deja_lanzar_el_resto_con_la_media_de_la_base_y_la_carga_menor() -> None:
    d = kc.tras_la_primera_porcion(110.0, kc.CARGA_MINIMA_S)
    assert d.lanzar_el_resto
    assert d.proyeccion_h == pytest.approx(kc.cuota_horas(110.0, kc.CARGA_MINIMA_S) + 11.2)


def test_pasar_es_estrictamente_mayor() -> None:
    # exactamente en el tope no detiene: media 240 s y proyección de exactamente el tope pasado como argumento
    proyeccion = kc.proyeccion_del_plan_h(240.0, 500.0)
    assert kc.tras_la_primera_porcion(240.0, 500.0, tope_h=proyeccion).lanzar_el_resto
    assert not kc.tras_la_primera_porcion(240.0, 500.0, tope_h=proyeccion - 0.001).lanzar_el_resto
