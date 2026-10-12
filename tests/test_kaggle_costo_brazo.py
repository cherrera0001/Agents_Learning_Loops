"""Tests de `scripts/kaggle_costo_brazo.py` (#182): la cuenta de horas de cuota y la regla de parada."""

from __future__ import annotations

import math

import pytest

from scripts import kaggle_costo_brazo as kc


def test_con_el_maximo_observado_el_brazo_cuesta_de_11_1_a_13_3_horas() -> None:
    # 5 x 2 x (12 x 304 + carga) / 3600, con la carga menor y la mayor medidas
    assert round(kc.cuota_horas(kc.MAXIMO_OBSERVADO_S, kc.CARGA_MINIMA_S), 1) == 11.1
    assert round(kc.cuota_horas(kc.MAXIMO_OBSERVADO_S, kc.CARGA_MAXIMA_S), 1) == 13.3


def test_con_el_tope_por_tarea_el_brazo_cuesta_de_19_0_a_21_2_horas() -> None:
    assert kc.TOPE_POR_TAREA_S == 240 + 5 * 60
    assert round(kc.cuota_horas(kc.TOPE_POR_TAREA_S, kc.CARGA_MINIMA_S), 1) == 19.0
    assert round(kc.cuota_horas(kc.TOPE_POR_TAREA_S, kc.CARGA_MAXIMA_S), 1) == 21.2


def test_la_cuenta_mezclada_del_encargo_da_22_3_a_24_5_horas() -> None:
    # brazo con 2,0 y base de 5,6 h por pasada (que es de 2,25): no se usa para decidir
    mezclada = {
        c: kc.proyeccion_del_plan_h(kc.MAXIMO_OBSERVADO_S, c, base_h=11.2, factor=2.0)
        for c in (364.0, 1142.0)
    }
    assert round(mezclada[364.0], 1) == 22.3
    assert round(mezclada[1142.0], 1) == 24.5


def test_la_base_usa_el_mismo_factor_que_el_brazo() -> None:
    assert kc.pasadas_de_base_h(2.25) == pytest.approx(11.25)
    assert kc.pasadas_de_base_h(2.0) == pytest.approx(10.0)
    por_defecto = kc.proyeccion_del_plan_h(300.0, 500.0)
    assert por_defecto == pytest.approx(kc.cuota_horas(300.0, 500.0, factor=2.25) + 11.25)


def test_los_factores_coherentes_dan_21_1_a_23_3_h_con_2_0_y_23_8_a_26_2_h_con_2_25() -> None:
    # la base de 5,6 h es 2,5 h de sesión x 2,25; con 2,0 en ambos sería 2,5 x 2,0 por pasada
    for factor, esperado in ((2.0, (21.1, 23.3)), (2.25, (23.8, 26.2))):
        base = 2 * 2.5 * factor
        for carga, valor in zip((kc.CARGA_MINIMA_S, kc.CARGA_MAXIMA_S), esperado, strict=True):
            total = kc.proyeccion_del_plan_h(kc.MAXIMO_OBSERVADO_S, carga, base_h=base, factor=factor)
            assert round(total, 1) == valor


def test_la_cuenta_es_lineal_en_porciones_y_en_factor() -> None:
    una = kc.cuota_horas(200, 500, porciones=1)
    assert kc.cuota_horas(200, 500, porciones=5) == pytest.approx(5 * una)
    assert kc.cuota_horas(200, 500, factor=2.25) == pytest.approx(kc.cuota_horas(200, 500) * 2.25 / 2.0)
    assert kc.cuota_horas(200, 500, tareas=0) == pytest.approx(5 * 2.0 * 500 / 3600)


def test_la_regla_detiene_si_la_media_pasa_de_240_s() -> None:
    d = kc.tras_la_primera_porcion(240.1, kc.CARGA_MINIMA_S)
    assert not d.lanzar_el_resto and "240" in d.motivo and "media" in d.motivo


def test_una_media_apenas_sobre_240_s_detiene_y_una_de_240_no() -> None:
    # mata un umbral corrido hacia arriba (por ejemplo 240,05)
    assert not kc.tras_la_primera_porcion(240.01, kc.CARGA_MINIMA_S).lanzar_el_resto
    assert not kc.tras_la_primera_porcion(240.001, kc.CARGA_MINIMA_S).lanzar_el_resto
    assert kc.tras_la_primera_porcion(240.0, kc.CARGA_MINIMA_S).lanzar_el_resto


def test_el_tope_de_la_media_es_un_argumento_y_se_respeta() -> None:
    # mata ignorar `media_maxima_s`: con 100 s de tope, 150 s detiene aunque la proyección sea baja
    d = kc.tras_la_primera_porcion(150.0, kc.CARGA_MINIMA_S, media_maxima_s=100.0)
    assert not d.lanzar_el_resto and "100" in d.motivo
    assert kc.tras_la_primera_porcion(150.0, kc.CARGA_MINIMA_S, media_maxima_s=200.0).lanzar_el_resto


def test_con_las_constantes_actuales_la_media_detiene_antes_que_las_24_horas() -> None:
    # a 240 s y con la carga mayor: 5 x 2,25 x (12 x 240 + 1142) / 3600 + 11,25 = 23,8 h, que no pasa de 24
    d = kc.tras_la_primera_porcion(240.0, kc.CARGA_MAXIMA_S)
    assert d.lanzar_el_resto and round(d.proyeccion_h, 2) == 23.82
    assert round(kc.tras_la_primera_porcion(240.0, kc.CARGA_MINIMA_S).proyeccion_h, 2) == 21.39


def test_a_240_s_la_proyeccion_pasa_de_24_h_con_una_base_de_mas_de_11_43_h() -> None:
    assert kc.tras_la_primera_porcion(240.0, kc.CARGA_MAXIMA_S, base_h=11.42).lanzar_el_resto
    d = kc.tras_la_primera_porcion(240.0, kc.CARGA_MAXIMA_S, base_h=11.44)
    assert not d.lanzar_el_resto and "proyección" in d.motivo


def test_a_240_s_la_proyeccion_pasa_de_24_h_con_una_carga_de_mas_de_1200_s() -> None:
    assert kc.tras_la_primera_porcion(240.0, 1199.0).lanzar_el_resto
    d = kc.tras_la_primera_porcion(240.0, 1201.0)
    assert not d.lanzar_el_resto and "proyección" in d.motivo


def test_con_el_factor_2_0_los_umbrales_a_240_s_son_2160_s_con_base_de_10_h_y_1728_s_con_11_2_h() -> None:
    # la lectura coherente con el supuesto 2,0: base de 10 h
    assert kc.tras_la_primera_porcion(240.0, 2159.0, factor=2.0).lanzar_el_resto
    assert not kc.tras_la_primera_porcion(240.0, 2161.0, factor=2.0).lanzar_el_resto
    # con la base mezclada del encargo (11,2 h) el umbral de carga es el 1 728 s
    assert kc.tras_la_primera_porcion(240.0, 1727.0, base_h=11.2, factor=2.0).lanzar_el_resto
    assert not kc.tras_la_primera_porcion(240.0, 1729.0, base_h=11.2, factor=2.0).lanzar_el_resto
    assert kc.tras_la_primera_porcion(240.0, kc.CARGA_MAXIMA_S, base_h=12.82, factor=2.0).lanzar_el_resto
    assert not kc.tras_la_primera_porcion(240.0, kc.CARGA_MAXIMA_S, base_h=12.84, factor=2.0).lanzar_el_resto


def test_la_regla_detiene_si_la_proyeccion_pasa_de_24_h_aunque_la_media_no() -> None:
    # media de 240 s (no la pasa) con unas pasadas de base de 14 h: 12,57 + 14 = 26,6 h
    d = kc.tras_la_primera_porcion(240.0, kc.CARGA_MAXIMA_S, base_h=14.0)
    assert d.proyeccion_h > 24.0
    assert not d.lanzar_el_resto and "proyección" in d.motivo


def test_la_regla_deja_lanzar_el_resto_con_la_media_de_la_base_y_la_carga_menor() -> None:
    d = kc.tras_la_primera_porcion(110.0, kc.CARGA_MINIMA_S)
    assert d.lanzar_el_resto
    assert d.proyeccion_h == pytest.approx(kc.cuota_horas(110.0, kc.CARGA_MINIMA_S, factor=2.25) + 11.25)


def test_pasar_es_estrictamente_mayor() -> None:
    # exactamente en el tope no detiene: media 240 s y proyección de exactamente el tope pasado como argumento
    proyeccion = kc.proyeccion_del_plan_h(240.0, 500.0)
    assert kc.tras_la_primera_porcion(240.0, 500.0, tope_h=proyeccion).lanzar_el_resto
    assert not kc.tras_la_primera_porcion(240.0, 500.0, tope_h=proyeccion - 0.001).lanzar_el_resto


@pytest.mark.parametrize(
    ("media", "carga"),
    [
        (math.nan, 500.0),  # la media de cero filas
        (240.0, math.nan),
        (math.inf, 500.0),
        (100.0, math.inf),
        (-1.0, 500.0),
        (100.0, -1.0),
        (-math.inf, 500.0),
    ],
)
def test_una_media_o_una_carga_que_no_es_finita_y_no_negativa_no_autoriza(media: float, carga: float) -> None:
    d = kc.tras_la_primera_porcion(media, carga)
    assert not d.lanzar_el_resto
    assert "no es un número finito" in d.motivo
    assert math.isnan(d.proyeccion_h)


def test_cero_es_un_valor_valido() -> None:
    assert kc.tras_la_primera_porcion(0.0, 0.0).lanzar_el_resto
