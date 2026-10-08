"""Criterios de aceptación de la hipótesis Zorzal.

Cada prueba lleva el identificador de la historia que comprueba (HU: historia de usuario; HD: historia de uso
de datos). La tabla que las relaciona está en ``experiments/gemma_developer_agent/zorzal/README.md``.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts import zorzal_perfil as z

RAIZ = Path(__file__).resolve().parents[2]
ZORZAL = RAIZ / "experiments/gemma_developer_agent/zorzal"
U = z.cargar_umbrales()
HUELLA_CONGELADA = "68eeb20a4b37dba8d00e6ad94f44fdc5ba2a2e975f38a6464b850c9fcaae1ba7"


def anatomia(**cambios):
    """Una sesión con perfil zorzal completo; los cambios la apartan de él."""
    base = {
        "herramientas": {"run_command": 3, "read_file": 2, "edit_file": 1, "submit_patch": 1},
        "errores_de_herramienta": {},
        "llamada_de_la_primera_edicion": 5,
        "segundos_hasta_la_primera_edicion": 20.0,
        "comandos_con_pytest": 1,
        "llamadas_repetidas": 0,
        "repetidas_tras_fallo": 0,
        "comandos_con_salida_distinta_de_cero": 1,
        "entregas": 1,
        "empujones_del_arnes": 0,
        "tokens_de_entrada": 1000,
        "tokens_generados": 100,
    }
    base.update(cambios)
    return base


def fila(resuelta, perfil, tiempo=False):
    return {"resuelta": resuelta, "perfil": perfil, "tiempo_agotado": tiempo, "rasgos": {}}


def pasada(resueltas, total, con_perfil=0, cortadas=0):
    return [fila(i < resueltas, i < con_perfil, i < cortadas) for i in range(total)]


# ---------- HU-1 · clasificar una sesión con los cinco rasgos ----------


def test_hu1_una_sesion_que_cumple_los_cinco_rasgos_tiene_perfil_completo():
    cumplidos = z.rasgos(anatomia(), 40, U)
    assert cumplidos == dict.fromkeys(z.RASGOS, True)
    assert z.tiene_perfil(cumplidos, U, "completo")


@pytest.mark.parametrize(
    ("rasgo", "cambios", "limite"),
    [
        ("busca", {"llamada_de_la_primera_edicion": 1}, 40),
        ("busca", {"llamada_de_la_primera_edicion": None}, 40),
        ("oye", {"comandos_con_pytest": 0}, 40),
        ("observa", {"repetidas_tras_fallo": 1}, 40),
        ("espera", {}, 8),
        ("acierta", {"herramientas": {"read_file": 2, "edit_file": 4, "submit_patch": 1}}, 40),
        ("acierta", {"herramientas": {"read_file": 2, "submit_patch": 1}}, 40),
        ("acierta", {"entregas": 2}, 40),
    ],
)
def test_hu1_cada_rasgo_falla_justo_al_cruzar_su_umbral(rasgo, cambios, limite):
    assert z.rasgos(anatomia(**cambios), limite, U)[rasgo] is False


def test_hu1_los_umbrales_tienen_borde_exacto():
    assert z.rasgos(anatomia(llamada_de_la_primera_edicion=2), 40, U)["busca"]
    assert z.rasgos(anatomia(herramientas={"read_file": 1, "edit_file": 3}), 40, U)["acierta"]
    siete_llamadas = anatomia()
    assert sum(siete_llamadas["herramientas"].values()) == 7
    assert z.rasgos(siete_llamadas, 9, U)["espera"]
    assert not z.rasgos(siete_llamadas, 8, U)["espera"]


# ---------- HU-2 · leer cada hipótesis con una regla fijada de antemano ----------


def test_hu2_hz1_se_apoya_cuando_el_perfil_resuelve_con_mas_frecuencia():
    filas = (
        [fila(True, True)] * 4 + [fila(False, True)] * 2 + [fila(True, False)] * 1 + [fila(False, False)] * 5
    )
    assert z.veredicto_hz1(filas, U)["veredicto"] == "apoyada"


def test_hu2_hz1_se_refuta_con_frecuencia_igual():
    filas = (
        [fila(True, True)] * 3 + [fila(False, True)] * 3 + [fila(True, False)] * 3 + [fila(False, False)] * 3
    )
    assert z.veredicto_hz1(filas, U)["veredicto"] == "refutada"


def test_hu2_hz1_no_se_evalua_con_un_grupo_pequeno():
    filas = [fila(True, True)] * 4 + [fila(False, False)] * 11
    assert z.veredicto_hz1(filas, U)["veredicto"] == "no evaluable"


def test_hu2_la_ventaja_exigida_supera_el_ruido_y_nunca_baja_de_dos():
    assert z.ventaja_exigida(0, U) == 2
    assert z.ventaja_exigida(1, U) == 2
    assert z.ventaja_exigida(3, U) == 4


def test_hu2_hz2_se_apoya_solo_si_gana_a_la_base_y_al_relleno():
    base_1, base_2 = pasada(3, 15, con_perfil=2), pasada(3, 15, con_perfil=2)
    candidata = pasada(6, 15, con_perfil=8)
    assert z.veredicto_hz2(base_1, base_2, candidata, pasada(3, 15), U)["veredicto"] == "apoyada"
    assert z.veredicto_hz2(base_1, base_2, candidata, pasada(5, 15), U)["veredicto"] == "refutada"


def test_hu2_hz2_no_cuenta_si_la_configuracion_no_cambio_el_perfil():
    base_1, base_2 = pasada(3, 15, con_perfil=4), pasada(3, 15, con_perfil=4)
    candidata = pasada(9, 15, con_perfil=5)
    assert z.veredicto_hz2(base_1, base_2, candidata, pasada(3, 15), U)["veredicto"] == "no puesta a prueba"


def test_hu2_hz2_no_se_declara_sin_el_texto_de_relleno():
    base_1, base_2 = pasada(3, 15, con_perfil=2), pasada(3, 15, con_perfil=2)
    salida = z.veredicto_hz2(base_1, base_2, pasada(8, 15, con_perfil=9), None, U)
    assert salida["veredicto"] == "no evaluable sin relleno"


def test_hu2_hz2_descuenta_el_ruido_medido():
    base_1 = [fila(i in (0, 1, 2), False) for i in range(15)]
    base_2 = [fila(i in (2, 3, 4), False) for i in range(15)]
    assert z.ruido(base_1, base_2) == 4
    candidata = pasada(7, 15, con_perfil=6)
    salida = z.veredicto_hz2(base_1, base_2, candidata, pasada(1, 15), U)
    assert salida["ventaja_exigida"] == 5
    assert salida["veredicto"] == "refutada"


def test_hu2_hz3_se_refuta_si_aumentan_las_tareas_cortadas_por_tiempo():
    base_1, base_2 = pasada(3, 15, cortadas=1), pasada(3, 15, cortadas=2)
    assert z.veredicto_hz3(base_1, base_2, pasada(5, 15, cortadas=2))["veredicto"] == "apoyada"
    assert z.veredicto_hz3(base_1, base_2, pasada(5, 15, cortadas=3))["veredicto"] == "refutada"


# ---------- HU-3 · operar como zorzal: el informe antes de actuar ----------

INFORME = """## Qué oí
- La corrida terminó. Fuente: log del notebook.

## Qué vi
- Dos cifras no coinciden.

## Qué falta por oír
- El ruido entre pasadas.

## La única acción
- Esperar la segunda corrida.
"""


def test_hu3_un_informe_con_sus_cuatro_partes_y_una_accion_es_valido():
    assert z.validar_informe(INFORME) == []


def test_hu3_un_informe_que_no_propone_nada_es_valido():
    assert z.validar_informe(INFORME.replace("- Esperar la segunda corrida.", "Todavía nada.")) == []


def test_hu3_un_informe_con_dos_acciones_se_rechaza():
    problemas = z.validar_informe(INFORME + "- Subir otro notebook.\n")
    assert any("2 acciones" in p for p in problemas)


def test_hu3_un_informe_sin_una_parte_o_sin_fuentes_se_rechaza():
    assert any(
        "Qué vi" in p
        for p in z.validar_informe(INFORME.replace("## Qué vi\n- Dos cifras no coinciden.\n", ""))
    )
    assert any("fuente" in p for p in z.validar_informe(INFORME.replace(" Fuente: log del notebook.", "")))


# ---------- HU-4 · medir H-O con la bitácora de subidas ----------


def subida(fecha, util, visible=False):
    return {"fecha": fecha, "notebook": "n", "resultado_util": util, "fallo_visible_en_local": visible}


def test_hu4_ho_se_apoya_con_una_subida_por_resultado_util():
    bitacora = {"subidas": [subida("2026-10-06T10:00:00Z", True), subida("2026-10-08T10:00:00Z", True)]}
    assert z.veredicto_ho(bitacora, U)["veredicto"] == "apoyada"


def test_hu4_ho_se_refuta_con_una_resubida_o_un_fallo_visible_en_local():
    resubida = {"subidas": [subida("2026-10-06T10:00:00Z", False), subida("2026-10-06T12:00:00Z", True)]}
    assert z.veredicto_ho(resubida, U)["veredicto"] == "refutada"
    visible = {"subidas": [subida("2026-10-06T10:00:00Z", True, visible=True)]}
    assert z.veredicto_ho(visible, U)["veredicto"] == "refutada"


def test_hu4_ho_solo_cuenta_la_ventana_registrada():
    bitacora = {"subidas": [subida("2026-10-04T10:00:00Z", False), subida("2026-10-12T10:00:00Z", False)]}
    assert z.veredicto_ho(bitacora, U)["veredicto"] == "no evaluable"


def test_hu4_la_bitacora_versionada_tiene_la_forma_que_la_regla_lee():
    bitacora = json.loads((ZORZAL / "bitacora_operacion.json").read_text(encoding="utf-8"))
    assert isinstance(bitacora["subidas"], list)
    for fila_ in bitacora["subidas"]:
        assert {"fecha", "notebook", "resultado_util", "fallo_visible_en_local"} <= set(fila_)
    assert z.veredicto_ho(bitacora, U)["veredicto"] in {"no evaluable", "apoyada", "refutada"}


# ---------- HD-1 · solo conteos: ningún texto de la competencia ----------


def test_hd1_un_registro_con_un_campo_desconocido_se_rechaza():
    with pytest.raises(z.EntradaInvalida, match="no permitidos"):
        z.rasgos(anatomia(argumentos="texto"), 40, U)


def test_hd1_un_registro_con_texto_en_un_campo_conocido_se_rechaza():
    with pytest.raises(z.EntradaInvalida, match="texto"):
        z.rasgos(anatomia(entregas="una"), 40, U)
    with pytest.raises(z.EntradaInvalida, match="nombre corto"):
        z.rasgos(anatomia(herramientas={"x" * 80: 1}), 40, U)


def test_hd1_una_tarea_sin_traza_no_se_clasifica():
    with pytest.raises(z.EntradaInvalida, match="traza"):
        z.rasgos({"sin_traza": "FileNotFoundError"}, 40, U)


# ---------- HD-2 · solo tareas válidas ----------


def resultados(condiciones):
    corridas = {}
    for etiqueta, (condicion, filas) in condiciones.items():
        corridas[etiqueta] = {"condicion": condicion, "tareas": filas}
    return {"completo": True, "corridas": corridas}


def tarea(nombre, resuelta, **cambios):
    return {
        "instance_id": nombre,
        "resuelta": resuelta,
        "clase": "resuelta" if resuelta else "sin_parche",
        "anatomia": anatomia(**cambios),
    }


def test_hd2_las_tareas_no_validas_quedan_fuera_de_la_lectura():
    datos = resultados({"A1": ("A", [tarea("t1", True), tarea("t2", False), tarea("no_valida", True)])})
    salida = z.evaluar(datos, {"t1", "t2"}, {"A": 40}, "2026-10-05T00:00:00Z", U)
    assert salida["por_condicion"]["A"]["sesiones"] == 2
    assert salida["por_condicion"]["A"]["resueltas"] == [1]


# ---------- HD-3 · las reglas se congelan antes de leer los resultados ----------


def test_hd3_no_se_evaluan_resultados_leidos_antes_de_congelar_los_umbrales():
    datos = resultados({"A1": ("A", [tarea("t1", True)])})
    with pytest.raises(z.EntradaInvalida, match="antes de congelar"):
        z.evaluar(datos, {"t1"}, {"A": 40}, "2026-10-04T20:00:00Z", U)


def test_hd3_los_umbrales_congelados_no_cambiaron():
    assert z.huella_de_umbrales() == HUELLA_CONGELADA, (
        "umbrales.json cambió. Un cambio de umbrales es una enmienda: requiere aprobación del dueño, una "
        "versión nueva y actualizar esta huella en el mismo cambio."
    )


def test_hd3_el_umbral_de_ediciones_declara_de_que_dato_sale():
    assert "percentil 75" in U["rasgos"]["acierta"]["origen_del_maximo"]
    assert U["rasgos"]["acierta"]["ediciones_maximo"] == 3


# ---------- HD-4 · una medida incompleta se declara y no decide ----------


def test_hd4_mientras_oye_sea_incompleto_el_perfil_que_decide_lo_deja_fuera():
    assert z.perfil_primario(U) == "sin_oye"
    sin_pruebas = z.rasgos(anatomia(comandos_con_pytest=0), 40, U)
    assert z.tiene_perfil(sin_pruebas, U)
    assert not z.tiene_perfil(sin_pruebas, U, "completo")


def test_hd4_con_una_version_que_mida_bien_oye_manda_el_perfil_completo():
    nueva = copy.deepcopy(U)
    nueva["version"] = 2
    assert z.perfil_primario(nueva) == "completo"


def test_hd4_la_lectura_dice_que_perfil_uso():
    datos = resultados({"A1": ("A", [tarea("t1", True)])})
    salida = z.evaluar(datos, {"t1"}, {"A": 40}, "2026-10-05T00:00:00Z", U)
    assert salida["perfil_usado"] == "sin_oye"
    assert salida["oye_incompleto"] is True


# ---------- HD-5 · una comparación exige su control ----------


def test_hd5_la_comparacion_exige_dos_pasadas_de_la_base():
    datos = resultados({"A1": ("A", [tarea("t1", True)]), "Z1": ("Z", [tarea("t1", True)])})
    with pytest.raises(z.EntradaInvalida, match="dos pasadas"):
        z.evaluar(datos, {"t1"}, {"A": 40, "Z": 40}, "2026-10-05T00:00:00Z", U, base="A", candidata="Z")


def test_hd5_cada_condicion_declara_su_limite_de_llamadas():
    datos = resultados({"A1": ("A", [tarea("t1", True)])})
    with pytest.raises(z.EntradaInvalida, match="límite"):
        z.evaluar(datos, {"t1"}, {}, "2026-10-05T00:00:00Z", U)
