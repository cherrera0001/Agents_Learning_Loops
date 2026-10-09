"""Tests del tope por tarea y del mapa de hilos del núcleo (#164).

Cubren lo nuevo de `scripts/kaggle_registro_enganches.py` (vaciado del mapa, espera con tope, corte de una
tarea colgada, campos del latido) y de `scripts/kaggle_registro.py` (códigos 6 y 7, y las reglas que impiden
un 0 sobre una sesión colgada). No usan Docker, el arnés ni un núcleo de Jupyter: el núcleo es un doble con la
forma de `ipykernel` 6.29.5 (con el mapa `_thread_to_parent`) o de una versión sin él.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
import time
import types
from pathlib import Path
from typing import Any

import pytest

from scripts import kaggle_registro as kr
from scripts import kaggle_registro_enganches as ke

# ---------------------------------------------------------------------------
# Dobles
# ---------------------------------------------------------------------------


class _Flujo:
    """Un flujo con el mapa de hilo a padre, como `OutStream` de ipykernel 6.29.5."""

    def __init__(self, mapa: dict[int, int] | None = None) -> None:
        self._thread_to_parent = {} if mapa is None else mapa


def _nucleo(monkeypatch: pytest.MonkeyPatch, salida: Any, error: Any) -> types.SimpleNamespace:
    nucleo = types.SimpleNamespace(_stdout=salida, _stderr=error)
    monkeypatch.setattr(ke, "nucleo_de_jupyter", lambda: nucleo)
    return nucleo


def _eventos(registro: ke.Registro) -> list[dict[str, Any]]:
    return [json.loads(x) for x in registro.ruta_eventos.read_text(encoding="utf-8").splitlines()]


def _de_tipo(registro: ke.Registro, tipo: str) -> list[dict[str, Any]]:
    return [e for e in _eventos(registro) if e["evento"] == tipo]


# ---------------------------------------------------------------------------
# El mapa de hilos
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("mapa", "ciclo"),
    [
        ({}, False),
        ({1: 2, 2: 3}, False),
        ({1: 2, 2: 1}, True),
        ({1: 1}, True),
        ({5: 6, 1: 2, 2: 3, 3: 1}, True),
        ({1: 2, 3: 2, 4: 2}, False),
    ],
)
def test_hay_ciclo_dice_si_un_recorrido_del_mapa_no_termina(mapa: dict[int, int], ciclo: bool) -> None:
    assert ke.hay_ciclo(mapa) is ciclo


def test_sin_nucleo_de_jupyter_el_mapa_no_esta_disponible_y_nada_lanza() -> None:
    """Fuera de un núcleo `get_ipython` no existe: se anota y se sigue."""
    assert ke.nucleo_de_jupyter() is None
    estado = ke.mapa_de_hilos(vaciar=True)
    assert estado == {"disponible": False, "motivo": "sin núcleo de Jupyter", "vaciado": False}


def test_un_ipykernel_sin_el_mapa_se_anota_y_no_falla(monkeypatch: pytest.MonkeyPatch) -> None:
    """Como ipykernel 6.17.1 o 7.1.0: los flujos existen y no tienen `_thread_to_parent`."""
    _nucleo(monkeypatch, object(), object())
    estado = ke.mapa_de_hilos(vaciar=True)
    assert estado["disponible"] is False and estado["vaciado"] is False
    assert "no tiene el mapa _thread_to_parent" in estado["motivo"]
    # Un núcleo sin `_stdout` ni `_stderr` tampoco hace fallar nada
    monkeypatch.setattr(ke, "nucleo_de_jupyter", lambda: types.SimpleNamespace())
    assert ke.mapa_de_hilos(vaciar=True)["disponible"] is False


def test_vaciar_deja_vacios_los_dos_mapas_y_dice_lo_que_habia(monkeypatch: pytest.MonkeyPatch) -> None:
    salida, error = _Flujo({1: 2, 2: 1}), _Flujo({7: 8})
    mapa_de_salida = salida._thread_to_parent
    _nucleo(monkeypatch, salida, error)
    assert ke.mapa_de_hilos(vaciar=False) == {
        "disponible": True,
        "entradas": 3,
        "ciclo": True,
        "vaciado": False,
    }
    assert salida._thread_to_parent == {1: 2, 2: 1}, "mirar no debe vaciar"
    assert ke.mapa_de_hilos(vaciar=True) == {
        "disponible": True,
        "entradas": 3,
        "ciclo": True,
        "vaciado": True,
    }
    # Se vacía el mismo diccionario, no se cambia por otro: es el que recorre el hilo que gira
    assert (
        salida._thread_to_parent is mapa_de_salida and mapa_de_salida == {} and error._thread_to_parent == {}
    )
    assert ke.mapa_de_hilos(vaciar=True) == {
        "disponible": True,
        "entradas": 0,
        "ciclo": False,
        "vaciado": True,
    }


def test_el_ciclo_se_ve_aunque_solo_este_en_el_segundo_flujo(monkeypatch: pytest.MonkeyPatch) -> None:
    _nucleo(monkeypatch, _Flujo({1: 2}), _Flujo({3: 4, 4: 3}))
    assert ke.mapa_de_hilos(vaciar=False)["ciclo"] is True
    _nucleo(monkeypatch, _Flujo({3: 4, 4: 3}), _Flujo({1: 2}))
    assert ke.mapa_de_hilos(vaciar=False)["ciclo"] is True


def test_un_flujo_que_tambien_es_sys_stdout_se_cuenta_una_vez(monkeypatch: pytest.MonkeyPatch) -> None:
    flujo = _Flujo({1: 2})
    _nucleo(monkeypatch, flujo, flujo)
    monkeypatch.setattr(sys, "stdout", flujo)
    flujos, detalle = ke.flujos_con_mapa()
    assert flujos == [flujo] and detalle.startswith("1 flujos con mapa")
    assert ke.mapa_de_hilos(vaciar=False)["entradas"] == 1


def test_un_flujo_que_solo_esta_en_sys_stderr_tambien_se_vacia(monkeypatch: pytest.MonkeyPatch) -> None:
    """Si el núcleo no expone `_stdout`, quedan `sys.stdout` y `sys.stderr`."""
    flujo = _Flujo({1: 2, 2: 1})
    monkeypatch.setattr(ke, "nucleo_de_jupyter", lambda: types.SimpleNamespace())
    monkeypatch.setattr(sys, "stderr", flujo)
    assert ke.mapa_de_hilos(vaciar=True)["ciclo"] is True and flujo._thread_to_parent == {}


def test_un_fallo_al_mirar_el_mapa_se_anota_y_no_lanza(monkeypatch: pytest.MonkeyPatch) -> None:
    def roto() -> Any:
        raise RuntimeError("núcleo raro")

    monkeypatch.setattr(ke, "nucleo_de_jupyter", roto)
    estado = ke.mapa_de_hilos(vaciar=True)
    assert estado["disponible"] is False and estado["motivo"].startswith("RuntimeError")


def test_cada_tarea_empieza_con_el_mapa_vacio_y_lo_anota(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    salida = _Flujo({1: 2, 2: 1})
    _nucleo(monkeypatch, salida, _Flujo())
    registro = ke.Registro(tmp_path, "s")
    registro.tarea("E1", "t_1", 1)
    assert salida._thread_to_parent == {}
    salida._thread_to_parent[9] = 8
    registro.fin_tarea(clase="resuelta")
    registro.tarea("E1", "t_2", 2)
    primero, segundo = (e["mapa_de_hilos"] for e in _de_tipo(registro, "tarea_inicio"))
    assert primero == {"disponible": True, "entradas": 2, "ciclo": True, "vaciado": True}
    assert segundo == {"disponible": True, "entradas": 1, "ciclo": False, "vaciado": True}
    assert registro.ciclos_vaciados == 1 and registro.resumen()["ciclos_vaciados_del_mapa_de_hilos"] == 1


def test_con_el_vaciado_desactivado_el_mapa_queda_como_estaba(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    salida = _Flujo({1: 2, 2: 1})
    _nucleo(monkeypatch, salida, _Flujo())
    registro = ke.Registro(tmp_path, "s")
    registro.vaciar_mapa = False
    registro.tarea("E1", "t_1", 1)
    assert salida._thread_to_parent == {1: 2, 2: 1} and registro.ciclos_vaciados == 0
    (inicio,) = _de_tipo(registro, "tarea_inicio")
    assert inicio["mapa_de_hilos"]["vaciado"] is False and inicio["mapa_de_hilos"]["ciclo"] is True
    assert inicio["mapa_de_hilos"]["motivo"] == "vaciado desactivado"


def test_el_mapa_se_vacia_aunque_el_registro_este_inactivo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Quitar la causa no depende de que se escriban archivos."""
    salida = _Flujo({1: 2, 2: 1})
    _nucleo(monkeypatch, salida, _Flujo())
    registro = ke.Registro(tmp_path, "s", activo=False)
    registro.tarea("E1", "t_1", 1)
    assert salida._thread_to_parent == {} and list(tmp_path.iterdir()) == []


# ---------------------------------------------------------------------------
# La espera con tope
# ---------------------------------------------------------------------------


def test_correr_con_tope_devuelve_el_resultado_y_corre_en_un_hilo_demonio(tmp_path: Path) -> None:
    registro = ke.Registro(tmp_path, "s")
    registro.tarea("E1", "t_1", 1)
    visto: dict[str, Any] = {}

    async def tarea() -> str:
        hilo = threading.current_thread()
        visto.update(nombre=hilo.name, demonio=hilo.daemon, es_el_principal=hilo is threading.main_thread())
        await asyncio.sleep(0)
        return "hecho"

    assert registro.correr_con_tope(tarea, 30) == "hecho"
    assert visto == {"nombre": "tarea-del-notebook", "demonio": True, "es_el_principal": False}
    assert registro.hilo_de_tarea is not None and not registro.hilo_de_tarea.is_alive()
    registro.fin_tarea(clase="resuelta")
    assert _de_tipo(registro, "tarea_fin")[0]["con_tope"] is True and registro.tareas_con_tope == 1
    assert registro.hilo_de_tarea is None


def test_una_tarea_que_no_pasa_por_correr_con_tope_lo_deja_dicho(tmp_path: Path) -> None:
    registro = ke.Registro(tmp_path, "s")
    registro.tarea("E1", "t_1", 1)
    registro.fin_tarea(clase="resuelta")
    fin = _de_tipo(registro, "tarea_fin")[0]
    assert fin["con_tope"] is False and fin["par_faltante"] is False


def test_correr_con_tope_entrega_la_excepcion_de_la_tarea(tmp_path: Path) -> None:
    registro = ke.Registro(tmp_path, "s", activo=False)

    async def falla() -> None:
        raise KeyError("del arnés")

    with pytest.raises(KeyError, match="del arnés"):
        registro.correr_con_tope(falla, 30)

    async def cancelada() -> None:
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        registro.correr_con_tope(cancelada, 30)


def test_una_tarea_que_no_vuelve_se_deja_de_esperar_al_vencer_el_tope(tmp_path: Path) -> None:
    """Un bucle síncrono en el hilo de la tarea: ningún tope de asyncio lo interrumpe."""
    registro = ke.Registro(tmp_path, "s", activo=False)
    soltar = threading.Event()

    async def colgada() -> None:
        soltar.wait()  # bloquea el hilo y su bucle de eventos

    t0 = time.monotonic()
    with pytest.raises(ke.TareaColgada) as info:
        registro.correr_con_tope(colgada, 0.3)
    try:
        assert 0.3 <= time.monotonic() - t0 < 5, "debe volver al vencer el tope, no cuando el hilo termine"
        colgada_exc = info.value
        assert colgada_exc.tope_segundos == 0.3 and colgada_exc.segundos >= 0.3
        assert colgada_exc.hilo.is_alive() and colgada_exc.hilo.daemon
        assert "tope por tarea: 0.3 s" in str(colgada_exc)
        assert registro.hilo_de_tarea is colgada_exc.hilo and registro.con_tope is True
    finally:
        soltar.set()
        info.value.hilo.join(5)


def _colgar(registro: ke.Registro, cuerpo: Any, tope: float = 0.2) -> ke.TareaColgada:
    with pytest.raises(ke.TareaColgada) as info:
        registro.correr_con_tope(cuerpo, tope)
    return info.value


def test_si_vaciar_el_mapa_suelta_al_hilo_la_tarea_se_cancela_y_el_notebook_sigue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """El caso del ciclo: el hilo gira hasta que se vacía el mapa; al soltarse no debe seguir con la tarea."""
    mapa = {1: 2, 2: 1}
    _nucleo(monkeypatch, _Flujo(mapa), _Flujo())
    registro = ke.Registro(tmp_path, "s")
    registro.vaciar_mapa = False
    registro.tarea("E1", "t_1", 1)
    despues: list[str] = []

    async def gira_en_el_mapa() -> None:
        while mapa:  # como OutStream.parent_header: no sale hasta que el mapa cambia
            time.sleep(0.01)
        despues.append("suelto")
        await asyncio.sleep(0)  # el primer punto en que la cancelación pedida puede entrar
        despues.append("siguió con la tarea vieja")

    colgada = _colgar(registro, gira_en_el_mapa)
    assert registro.tarea_colgada(colgada, 10, indice=1) is True
    assert not colgada.hilo.is_alive() and mapa == {}
    assert despues == ["suelto"], "la tarea cortada no debe seguir ejecutándose"
    (evento,) = _de_tipo(registro, "tarea_colgada")
    assert evento["tarea"] == "t_1" and evento["indice"] == 1
    assert evento["hilo_vivo"] is False and evento["sigue"] is True and evento["cancelacion"] == "pedida"
    assert evento["mapa_de_hilos"] == {"disponible": True, "entradas": 2, "ciclo": True, "vaciado": False}
    assert evento["tope_s"] == 0.2 and evento["segundos"] >= 0.2 and evento["segundos_hasta_terminar"] < 10
    assert evento["colgadas_seguidas"] == 1 and evento["hilos_vivos"] >= 1 and "carga" in evento
    # La pila quedó en un archivo de la salida y nombra la función que giraba
    assert (
        evento["pila"] == registro.ruta_pila.name
        and evento["pila_bytes"] == registro.ruta_pila.stat().st_size > 0
    )
    pila = registro.ruta_pila.read_text(encoding="utf-8")
    assert "gira_en_el_mapa" in pila and "tarea-del-notebook" in pila and "tarea t_1" in pila
    assert registro.ruta_pila in registro.archivos()
    assert registro.errores == 0 and registro.resumen()["tareas_colgadas"] == 1


def test_si_el_hilo_sigue_vivo_el_notebook_no_puede_seguir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Un bucle síncrono que no depende del mapa: vaciarlo no lo suelta y no se le puede matar."""
    mapa = {1: 2}
    _nucleo(monkeypatch, _Flujo(mapa), _Flujo())
    registro = ke.Registro(tmp_path, "s")
    registro.tarea("E1", "t_1", 1)
    soltar = threading.Event()

    async def bucle_sincrono() -> None:
        soltar.wait()

    colgada = _colgar(registro, bucle_sincrono)
    try:
        t0 = time.monotonic()
        assert registro.tarea_colgada(colgada, 0.3) is False
        assert 0.3 <= time.monotonic() - t0 < 5, "espera el margen y no más"
        (evento,) = _de_tipo(registro, "tarea_colgada")
        assert evento["hilo_vivo"] is True and evento["sigue"] is False
        assert evento["segundos_hasta_terminar"] is None and evento["margen_s"] == 0.3
        assert "bucle_sincrono" in registro.ruta_pila.read_text(encoding="utf-8")
    finally:
        soltar.set()
        colgada.hilo.join(5)


def test_la_segunda_tarea_colgada_seguida_termina_la_sesion_aunque_su_hilo_muera(tmp_path: Path) -> None:
    registro = ke.Registro(tmp_path, "s")

    def colgar_y_cortar(nombre: str) -> bool:
        registro.tarea("E1", nombre, 1)
        soltar = threading.Event()

        async def espera() -> None:
            soltar.wait()
            await asyncio.sleep(0)

        colgada = _colgar(registro, espera)
        soltar.set()  # el hilo se suelta solo: lo que decide aquí es cuántas van seguidas
        sigue = registro.tarea_colgada(colgada, 10)
        assert not colgada.hilo.is_alive()
        registro.fin_tarea(clase=ke.CLASE_TAREA_COLGADA, resuelta=False)
        return sigue

    assert colgar_y_cortar("t_1") is True
    assert colgar_y_cortar("t_2") is False
    assert [e["colgadas_seguidas"] for e in _de_tipo(registro, "tarea_colgada")] == [1, 2]
    # Una tarea que termina bien entre dos colgadas vuelve a poner la cuenta a cero
    registro.tarea("E1", "t_3", 3)
    registro.fin_tarea(clase="resuelta")
    assert colgar_y_cortar("t_4") is True
    assert registro.colgadas == 3 and registro.ruta_pila.read_text(encoding="utf-8").count("=== ") == 3
    # Cada tarea cortada queda marcada como par faltante en su fila de fin; la que terminó bien, no
    marcas = {e["tarea"]: e["par_faltante"] for e in _de_tipo(registro, "tarea_fin")}
    assert marcas == {"t_1": True, "t_2": True, "t_3": False, "t_4": True}


def test_tarea_colgada_no_lanza_si_no_puede_pedir_la_cancelacion_ni_volcar_la_pila(tmp_path: Path) -> None:
    registro = ke.Registro(tmp_path / "no_existe", "s")  # la carpeta no existe: ni eventos ni pila
    hilo = threading.Thread(target=lambda: None)
    hilo.start()
    hilo.join()
    assert registro.tarea_colgada(ke.TareaColgada(1.0, 1.5, hilo, {}), 0) is True
    assert registro.errores >= 1 and registro.volcar_pila()["pila"] is None
    # Sin hilo que comprobar no se puede garantizar nada: no se sigue
    otro = ke.Registro(
        tmp_path, "s"
    )  # la primera colgada de este registro: lo único que impide seguir es el hilo
    assert otro.tarea_colgada(ke.TareaColgada(1.0, 1.5), 0) is False
    assert _de_tipo(otro, "tarea_colgada")[0]["hilo_vivo"] is True and otro.colgadas_seguidas == 1


def test_el_registro_inactivo_no_escribe_la_pila(tmp_path: Path) -> None:
    registro = ke.Registro(tmp_path, "s", activo=False)
    assert registro.volcar_pila() == {} and list(tmp_path.iterdir()) == [] and registro.archivos() == []


# ---------------------------------------------------------------------------
# El latido, el cierre y la instalación
# ---------------------------------------------------------------------------


def _latidos(registro: ke.Registro) -> list[dict[str, Any]]:
    return [json.loads(x) for x in registro.ruta_latido.read_text(encoding="utf-8").splitlines()]


def test_el_latido_dice_cuanto_lleva_la_tarea_sin_eventos_y_como_esta_la_maquina(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ke.Registro, "_gpu", lambda self: [])
    registro = ke.Registro(tmp_path, "s")
    registro.latir()
    registro.tarea("E1", "t_1", 1)
    assert registro.ultimo_evento is not None
    registro.ultimo_evento = ("tarea_inicio", time.time() - 100)
    registro.t_tarea = time.time() - 120
    soltar = threading.Event()
    registro.hilo_de_tarea = threading.Thread(target=soltar.wait, daemon=True)
    registro.hilo_de_tarea.start()
    registro.latir()
    soltar.set()
    antes, en_tarea = _latidos(registro)
    assert antes["ultimo_evento"] is None and antes["segundos_sin_eventos"] is None
    assert antes["tarea_segundos"] is None and antes["hilo_de_tarea"] is None
    assert en_tarea["ultimo_evento"] == "tarea_inicio" and 100 <= en_tarea["segundos_sin_eventos"] < 110
    assert 120 <= en_tarea["tarea_segundos"] < 130
    assert en_tarea["hilo_de_tarea"]["vivo"] is True and "cpu_s" in en_tarea["hilo_de_tarea"]
    assert en_tarea["cpus"] == os.cpu_count() and en_tarea["hilos_vivos"] >= 2
    assert isinstance(en_tarea["carga"], (list, dict))


def test_sin_getloadavg_la_carga_se_anota_como_error_y_el_latido_sigue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """En Windows `os.getloadavg` no existe."""

    def no_hay() -> Any:
        raise AttributeError("getloadavg")

    monkeypatch.setattr(os, "getloadavg", no_hay, raising=False)
    carga = ke.carga_del_sistema()
    assert carga["carga"] == {"error": "AttributeError"} and carga["hilos_vivos"] >= 1
    assert "cpus_utilizables" in carga  # la afinidad, o su error donde la plataforma no la da
    monkeypatch.setattr(os, "getloadavg", lambda: (1.234, 2.0, 3.0), raising=False)
    assert ke.carga_del_sistema()["carga"] == [1.23, 2.0, 3.0]


def test_la_cpu_de_un_hilo_que_no_se_puede_leer_es_none() -> None:
    assert ke.cpu_de_un_hilo(None) is None
    assert ke.cpu_de_un_hilo(types.SimpleNamespace(ident=None)) is None


def test_cerrar_dos_veces_deja_un_solo_cierre(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ke.Registro, "_gpu", lambda self: [])
    registro = ke.Registro(tmp_path, "s")
    registro.cerrar()
    latidos = len(_latidos(registro))
    registro.cerrar()
    assert len(_de_tipo(registro, "cierre")) == 1 and len(_latidos(registro)) == latidos


def test_las_versiones_traen_python_y_no_fallan_con_un_paquete_ausente() -> None:
    hallado = ke.versiones()
    assert hallado["python"] == sys.version.split()[0]
    assert set(hallado) == {"python", *ke.PAQUETES_CON_VERSION}
    assert hallado["papermill"] is None or isinstance(hallado["papermill"], str)


@pytest.mark.parametrize(
    ("vaciar", "texto"), [(True, "se vacía antes de cada tarea"), (False, "no se vacía (desactivado)")]
)
def test_instalar_anota_las_versiones_y_el_estado_del_mapa_sin_exigirlo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    vaciar: bool,
    texto: str,
) -> None:
    for modulo in (
        "litellm",
        "google.adk.models.lite_llm",
        "swegemma",
        "swegemma.harness",
        "swegemma.evaluate",
        "rich",
    ):
        monkeypatch.setitem(sys.modules, modulo, None)
    monkeypatch.setattr(ke.Registro, "_gpu", lambda self: [])
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    # Sin núcleo: el mapa no está disponible, y eso no es un enganche que falte
    sin_nucleo = ke.instalar_registro(tmp_path / "a", "s", None, latido_segundos=60, vaciar_mapa=vaciar)
    sin_nucleo.cerrar()
    assert sin_nucleo.enganches["mapa de hilos del núcleo"] == "no disponible: sin núcleo de Jupyter"
    assert (
        "mapa de hilos del núcleo" not in sin_nucleo.enganches_que_faltan()
        and sin_nucleo.vaciar_mapa is vaciar
    )
    # Con un núcleo que lo tiene
    _nucleo(monkeypatch, _Flujo({1: 2}), _Flujo())
    registro = ke.instalar_registro(tmp_path / "b", "s", None, latido_segundos=60, vaciar_mapa=vaciar)
    registro.cerrar()
    assert registro.enganches["mapa de hilos del núcleo"] == texto
    (instalado,) = _de_tipo(registro, "registro_instalado")
    assert (
        instalado["versiones"]["python"] == sys.version.split()[0] and "ipykernel" in instalado["versiones"]
    )
    assert instalado["mapa_de_hilos"] == {"disponible": True, "entradas": 1, "ciclo": False, "vaciado": False}
    assert instalado["hilos_vivos"] >= 1 and "carga" in instalado and "cpus" in instalado
    impreso = capsys.readouterr().out
    assert "REGISTRO enganche mapa de hilos del núcleo -> " + texto in impreso
    # Lo que hay que saber de la plataforma antes de la primera tarea, a la vista en el log de la sesión
    assert impreso.count("REGISTRO versiones {") == 2 and impreso.count("REGISTRO mapa de hilos {") == 2
    assert "| maquina {" in impreso and "cpus_utilizables" in impreso and "hilos_vivos" in impreso


# ---------------------------------------------------------------------------
# El diagnóstico: códigos 6 y 7, y lo que nunca debe salir con 0
# ---------------------------------------------------------------------------

ENGANCHES = {"peticiones": "instalado", "latido": "cada 30.0 s"}
T0 = 1_760_000_000.0


def _e(tipo: str, tarea: str | None, hora: float, **campos: Any) -> dict[str, Any]:
    return {"evento": tipo, "tarea": tarea, "hora": hora, "hora_utc": f"h{hora}", **campos}


def _tarea_bien(nombre: str, hora: float, numero: int, **fin: Any) -> list[dict[str, Any]]:
    return [
        _e(
            "tarea_inicio",
            nombre,
            hora,
            mapa_de_hilos={"disponible": True, "entradas": 0, "ciclo": False, "vaciado": True},
        ),
        _e("peticion_inicio", nombre, hora + 1, peticion=numero, caracteres_entrada=10),
        _e("peticion_fin", nombre, hora + 2, peticion=numero, motivo="stop"),
        _e("diff_cierre", nombre, hora + 3, bytes=5, sha256="x", archivos=[]),
        _e("agente_fin", nombre, hora + 4, error=None, entrego=True),
        _e("tarea_fin", nombre, hora + 5, clase="resuelta", resuelta=True, **{"con_tope": True, **fin}),
    ]


def _tarea_colgada(nombre: str, hora: float, **colgada: Any) -> list[dict[str, Any]]:
    campos = {
        "tope_s": 540,
        "segundos": 540.0,
        "pila": "pila.txt",
        "pila_bytes": 900,
        "hilo_vivo": False,
        "sigue": True,
    }
    return [
        _e("tarea_inicio", nombre, hora),
        _e("tarea_colgada", nombre, hora + 540, **{**campos, **colgada}),
        _e(
            "tarea_fin",
            nombre,
            hora + 541,
            clase="tarea_colgada",
            resuelta=False,
            con_tope=True,
            par_faltante=True,
        ),
    ]


INSTALADO = _e("registro_instalado", None, T0, enganches=ENGANCHES, versiones={"ipykernel": "6.29.5"})


def _cierre(hora: float, errores: int = 0) -> dict[str, Any]:
    return _e("cierre", None, hora, errores_del_registro=errores, ultimo_error=None)


def _codigo(
    eventos: list[dict[str, Any]], latidos: list[dict[str, Any]] | None = None
) -> tuple[int, dict[str, Any]]:
    informe = kr.diagnosticar(eventos, latidos or [])
    return kr.codigo_de(informe), informe["sesion"]


def test_los_codigos_nuevos_son_distintos_de_todos_los_demas() -> None:
    codigos = [
        kr.EXIT_OK,
        kr.EXIT_DIFIERE,
        kr.EXIT_ENTRADA,
        kr.EXIT_CORTADA,
        kr.EXIT_REGISTRO,
        kr.EXIT_MUERTA,
    ]
    assert (kr.EXIT_DETENIDA_VIVA, kr.EXIT_CON_COLGADAS) == (6, 7)
    assert len({*codigos, kr.EXIT_DETENIDA_VIVA, kr.EXIT_CON_COLGADAS}) == 8


def test_una_sesion_sin_ninguna_tarea_colgada_sigue_saliendo_con_0() -> None:
    eventos = [INSTALADO, *_tarea_bien("t_1", T0 + 10, 1), *_tarea_bien("t_2", T0 + 20, 2), _cierre(T0 + 30)]
    codigo, sesion = _codigo(eventos)
    assert codigo == kr.EXIT_OK and sesion["tareas_colgadas"] == [] and sesion["estado"] == "completa"
    assert sesion["versiones"] == {"ipykernel": "6.29.5"}
    assert sesion["tareas_que_empezaron_con_un_ciclo_en_el_mapa"] == 0


def test_cortar_una_tarea_y_seguir_sale_con_7_y_no_con_0() -> None:
    eventos = [
        INSTALADO,
        *_tarea_bien("t_1", T0 + 10, 1),
        *_tarea_colgada("t_2", T0 + 20, mapa_de_hilos={"ciclo": True}),
        *_tarea_bien("t_3", T0 + 600, 2),
        _cierre(T0 + 700),
    ]
    informe = kr.diagnosticar(eventos, [])
    assert kr.codigo_de(informe) == kr.EXIT_CON_COLGADAS == 7
    sesion = informe["sesion"]
    assert sesion["estado"] == "con_colgadas" and sesion["tareas_colgadas"] == ["t_2"]
    assert sesion["pares_faltantes"] == ["t_2"], "una tarea cortada es un par faltante, no una no resuelta"
    assert sesion["registro_fiable"] is True and "t_2" in sesion["veredicto"] and sesion["cerrada"] is True
    ficha = informe["tareas"][1]
    assert ficha["tope_que_corto"] == "tope por tarea del notebook (tarea colgada)"
    assert ficha["colgada"]["hilo_vivo"] is False and ficha["colgada"]["pila"] == "pila.txt"
    assert ficha["colgada"]["mapa_de_hilos"] == {"ciclo": True} and ficha["clase"] == "tarea_colgada"


def test_terminar_la_sesion_por_una_tarea_colgada_sale_con_3_aunque_la_celda_anote_despues_su_fallo() -> None:
    eventos = [
        INSTALADO,
        *_tarea_bien("t_1", T0 + 10, 1),
        *_tarea_colgada("t_2", T0 + 20, hilo_vivo=True, sigue=False),
        _e("corte", None, T0 + 562, cortado_por="tarea_colgada", tarea_cortada="t_2"),
        _e("corte", None, T0 + 563, cortado_por="fallo TareaColgada"),
        _cierre(T0 + 564),
    ]
    codigo, sesion = _codigo(eventos)
    assert codigo == kr.EXIT_CORTADA and sesion["cortado_por"] == "tarea_colgada"
    assert "no volvió dentro del tope por tarea" in sesion["veredicto"] and sesion["tareas_colgadas"] == [
        "t_2"
    ]
    # Sin el cierre sigue siendo un corte anotado por el notebook: 3 gana a 5 y a 6
    latidos = [{"hora": T0 + 5000, "tarea": None}]
    assert _codigo(eventos[:-1], latidos)[0] == kr.EXIT_CORTADA


def test_las_dos_ramas_del_corte_dan_codigos_distintos_entre_si_y_distintos_de_0_y_de_5() -> None:
    seguir = [INSTALADO, *_tarea_colgada("t_1", T0), *_tarea_bien("t_2", T0 + 600, 1), _cierre(T0 + 700)]
    terminar = [
        INSTALADO,
        *_tarea_colgada("t_1", T0, hilo_vivo=True, sigue=False),
        _e("corte", None, T0 + 542, cortado_por="tarea_colgada"),
        _cierre(T0 + 543),
    ]
    codigos = {_codigo(seguir)[0], _codigo(terminar)[0]}
    assert codigos == {kr.EXIT_CON_COLGADAS, kr.EXIT_CORTADA} and not codigos & {kr.EXIT_OK, kr.EXIT_MUERTA}


def test_viva_y_detenida_se_distingue_de_muerta_desde_fuera_por_el_silencio_del_latido() -> None:
    eventos = [INSTALADO, *_tarea_bien("t_1", T0 + 10, 1), _e("tarea_inicio", "t_2", T0 + 100)]
    umbral = kr.SILENCIO_DETENIDA_SEGUNDOS

    def latido(segundos: float) -> list[dict[str, Any]]:
        return [
            {"hora": T0 + 50, "tarea": "t_1"},
            {"hora": T0 + 100 + segundos, "tarea": "t_2", "en_vuelo": []},
        ]

    codigo, sesion = _codigo(eventos, latido(983.7))
    assert codigo == kr.EXIT_DETENIDA_VIVA == 6 and sesion["estado"] == "detenida_viva"
    assert sesion["veredicto"].startswith("viva y detenida") and "983.7 s" in sesion["veredicto"]
    assert "t_2" in sesion["veredicto"] and sesion["segundos_de_latido_sin_eventos"] == 983.7
    # Justo en el umbral, o con poco silencio, es una sesión muerta: el notebook aún no podía haber cortado
    for segundos in (umbral, 6.3):
        codigo, sesion = _codigo(eventos, latido(segundos))
        assert codigo == kr.EXIT_MUERTA and sesion["veredicto"].startswith("muerta desde fuera")
        assert f"{float(segundos)} s de latido sin eventos" in sesion["veredicto"]
    assert _codigo(eventos, latido(umbral + 0.1))[0] == kr.EXIT_DETENIDA_VIVA


def test_sin_latidos_o_con_horas_ilegibles_una_sesion_sin_cierre_es_muerta() -> None:
    eventos = [INSTALADO, _e("tarea_inicio", "t_1", T0)]
    assert _codigo(eventos)[0] == kr.EXIT_MUERTA
    for hora in (None, "tarde", True):
        codigo, sesion = _codigo(eventos, [{"hora": hora}])
        assert codigo == kr.EXIT_MUERTA and sesion["segundos_de_latido_sin_eventos"] is None
    sin_hora = [INSTALADO, {"evento": "tarea_inicio", "tarea": "t_1"}]
    assert _codigo(sin_hora, [{"hora": T0 + 9999}])[0] == kr.EXIT_MUERTA
    assert kr.silencio_antes_del_ultimo_latido([], [{"hora": 1.0}]) is None


def test_el_ultimo_latido_de_la_tarea_trae_lo_que_distingue_un_giro_de_un_bloqueo() -> None:
    eventos = [INSTALADO, _e("tarea_inicio", "t_1", T0)]
    latido = {
        "hora": T0 + 700,
        "tarea": "t_1",
        "ultimo_evento": "tarea_inicio",
        "segundos_sin_eventos": 700.0,
        "tarea_segundos": 700.0,
        "hilo_de_tarea": {"vivo": True, "cpu_s": 650.2},
        "carga": [1.0, 1.0, 1.0],
        "cpus": 4,
        "cpus_utilizables": 4,
        "hilos_vivos": 9,
    }
    primero = {"hora": T0 + 30, "tarea": "t_1", "ultimo_evento": "tarea_inicio", "segundos_sin_eventos": 30.0}
    sesion = kr.diagnosticar(eventos, [primero, latido])["sesion"]
    assert sesion["ultimo_latido_de_la_tarea"] == {
        k: v for k, v in latido.items() if k not in ("hora", "tarea")
    }


# -- entradas adversas: ninguna sesión colgada o cortada por el tope sale con 0 ---------------------


def test_adversa_registro_cerrado_con_una_tarea_sin_fin_y_sin_corte_no_sale_con_0() -> None:
    """El notebook dejó una tarea a medias y aun así cerró el registro sin anotar por qué."""
    eventos = [
        INSTALADO,
        *_tarea_bien("t_1", T0 + 10, 1),
        _e("tarea_inicio", "t_2", T0 + 20),
        _cierre(T0 + 600),
    ]
    codigo, sesion = _codigo(eventos)
    assert codigo == kr.EXIT_REGISTRO and "no tiene «tarea_fin»" in sesion["veredicto"]
    # Con un corte anotado, la tarea a medias tiene explicación y no es un problema del registro
    con_corte = [*eventos[:-1], _e("corte", None, T0 + 599, cortado_por="fallo KeyError"), _cierre(T0 + 600)]
    codigo, sesion = _codigo(con_corte)
    assert codigo == kr.EXIT_CORTADA and sesion["registro_fiable"] is True


def test_adversa_una_tarea_colgada_que_figura_como_resuelta_no_sale_con_7_sino_con_4() -> None:
    eventos = [INSTALADO, *_tarea_bien("t_1", T0, 1), *_tarea_colgada("t_2", T0 + 20), _cierre(T0 + 700)]
    eventos[-2]["resuelta"] = True
    codigo, sesion = _codigo(eventos)
    assert codigo == kr.EXIT_REGISTRO and "figura como resuelta" in sesion["veredicto"]


@pytest.mark.parametrize("marca", [False, None])
def test_adversa_una_tarea_colgada_sin_la_marca_de_par_faltante_no_sale_con_7(marca: Any) -> None:
    """Sin la marca, quien compare dos pasadas la contaría como una tarea no resuelta."""
    eventos = [INSTALADO, *_tarea_bien("t_1", T0, 1), *_tarea_colgada("t_2", T0 + 20), _cierre(T0 + 700)]
    eventos[-2]["par_faltante"] = marca
    codigo, sesion = _codigo(eventos)
    assert codigo == kr.EXIT_REGISTRO and "no está marcada como par faltante" in sesion["veredicto"]


def test_adversa_la_fila_dice_colgada_y_falta_el_evento_del_corte() -> None:
    """Sin el evento no hay pila ni constancia de que el hilo terminó."""
    eventos = [INSTALADO, *_tarea_bien("t_1", T0, 1), *_tarea_colgada("t_2", T0 + 20), _cierre(T0 + 700)]
    sin_evento = [e for e in eventos if e["evento"] != "tarea_colgada"]
    codigo, sesion = _codigo(sin_evento)
    assert codigo == kr.EXIT_REGISTRO and "no trae su evento «tarea_colgada»" in sesion["veredicto"]
    assert sesion["tareas_colgadas"] == ["t_2"]


def test_adversa_el_evento_del_corte_con_una_fila_que_dice_resuelta_no_sale_con_0() -> None:
    """La fila no dice «tarea_colgada» pero el registro sí trae el corte: sigue contando como colgada."""
    eventos = [INSTALADO, *_tarea_bien("t_1", T0, 1), *_tarea_colgada("t_2", T0 + 20), _cierre(T0 + 700)]
    eventos[-2].update(clase="resuelta", resuelta=True)
    codigo, sesion = _codigo(eventos)
    assert codigo == kr.EXIT_REGISTRO and sesion["tareas_colgadas"] == ["t_2"]
    eventos[-2].update(clase="parche_no_pasa", resuelta=False)
    assert _codigo(eventos)[0] == kr.EXIT_CON_COLGADAS


@pytest.mark.parametrize("hilo_vivo", [True, None])
def test_adversa_seguir_con_el_hilo_vivo_o_sin_comprobarlo_es_un_registro_no_fiable(hilo_vivo: Any) -> None:
    """Nunca dos tareas a la vez: si el registro no prueba que el hilo terminó, la sesión no vale."""
    eventos = [
        INSTALADO,
        *_tarea_colgada("t_1", T0, hilo_vivo=hilo_vivo, sigue=True),
        *_tarea_bien("t_2", T0 + 600, 1),
        _cierre(T0 + 700),
    ]
    codigo, sesion = _codigo(eventos)
    assert codigo == kr.EXIT_REGISTRO and "pudo haber dos tareas a la vez" in sesion["veredicto"]


def test_adversa_empezar_otra_tarea_tras_decidir_no_seguir_es_un_registro_no_fiable() -> None:
    eventos = [
        INSTALADO,
        *_tarea_colgada("t_1", T0, hilo_vivo=True, sigue=False),
        *_tarea_bien("t_2", T0 + 600, 1),
        _cierre(T0 + 700),
    ]
    codigo, sesion = _codigo(eventos)
    assert codigo == kr.EXIT_REGISTRO and "no debía seguir" in sesion["veredicto"]
    # Si es la última tarea de la lista y el registro se cierra sin corte, tampoco sale con 0
    solo = [INSTALADO, *_tarea_colgada("t_1", T0, hilo_vivo=True, sigue=False), _cierre(T0 + 700)]
    codigo, sesion = _codigo(solo)
    assert codigo == kr.EXIT_REGISTRO and "sin anotar el corte de la sesión" in sesion["veredicto"]


def test_adversa_una_tarea_terminada_que_no_corrio_bajo_el_tope_no_sale_con_0() -> None:
    eventos = [INSTALADO, *_tarea_bien("t_1", T0, 1, con_tope=False), _cierre(T0 + 30)]
    codigo, sesion = _codigo(eventos)
    assert codigo == kr.EXIT_REGISTRO and "no corrió bajo el tope por tarea" in sesion["veredicto"]
    # Un registro anterior al #164 no trae el campo: no se le exige
    viejo = [INSTALADO, *_tarea_bien("t_1", T0, 1), _cierre(T0 + 30)]
    del viejo[-2]["con_tope"]
    assert _codigo(viejo)[0] == kr.EXIT_OK


def test_adversa_una_tarea_colgada_no_necesita_agente_fin_ni_diff_pero_las_demas_si() -> None:
    eventos = [INSTALADO, *_tarea_bien("t_1", T0, 1), *_tarea_colgada("t_2", T0 + 20), _cierre(T0 + 700)]
    assert _codigo(eventos)[0] == kr.EXIT_CON_COLGADAS
    sin_diff = [e for e in eventos if e["evento"] != "diff_cierre"]
    codigo, sesion = _codigo(sin_diff)
    assert (
        codigo == kr.EXIT_REGISTRO and "t_1" in sesion["veredicto"] and "diff_cierre" in sesion["veredicto"]
    )


def test_adversa_un_corte_de_tarea_que_no_cae_en_ninguna_corrida_no_sale_con_0() -> None:
    """El evento llega tras la fila de fin, o sin nombre de tarea, y la fila dice que terminó bien."""
    bien = _tarea_bien("t_1", T0, 1)
    corte = _e("tarea_colgada", "t_1", T0 + 6, hilo_vivo=False, sigue=True)
    tras_el_fin = [INSTALADO, *bien, corte, _cierre(T0 + 30)]
    assert kr.codigo_de(kr.diagnosticar([INSTALADO, *bien, _cierre(T0 + 30)], [])) == kr.EXIT_OK
    codigo, sesion = _codigo(tras_el_fin)
    assert codigo == kr.EXIT_REGISTRO and "no pertenecen a la corrida de ninguna tarea" in sesion["veredicto"]
    sin_nombre = [INSTALADO, *bien[:3], {**corte, "tarea": None}, *bien[3:], _cierre(T0 + 30)]
    assert _codigo(sin_nombre)[0] == kr.EXIT_REGISTRO
    # Dentro de su corrida no es un evento suelto
    dentro = [INSTALADO, *_tarea_colgada("t_1", T0), *_tarea_bien("t_2", T0 + 600, 1), _cierre(T0 + 700)]
    assert "no pertenecen" not in _codigo(dentro)[1]["veredicto"]


def test_adversa_errores_del_registro_o_una_guardia_ganan_a_los_codigos_nuevos() -> None:
    base = [INSTALADO, *_tarea_bien("t_1", T0, 1), *_tarea_colgada("t_2", T0 + 20)]
    assert _codigo([*base, _cierre(T0 + 700, errores=1)])[0] == kr.EXIT_REGISTRO
    guardia = _e("guardia", None, T0 + 650, cuando="tras la primera tarea", problemas=["x"])
    assert _codigo([*base, guardia, _cierre(T0 + 700)])[0] == kr.EXIT_REGISTRO
    # Viva y detenida con un enganche sin instalar: 4 gana a 6
    roto = _e("registro_instalado", None, T0, enganches={"peticiones": "FALLO ImportError"})
    assert _codigo([roto, _e("tarea_inicio", "t_1", T0 + 1)], [{"hora": T0 + 5000}])[0] == kr.EXIT_REGISTRO


def test_adversa_todas_las_tareas_colgadas_y_ninguna_peticion_no_sale_con_0() -> None:
    eventos = [INSTALADO, *_tarea_colgada("t_1", T0), _cierre(T0 + 700)]
    codigo, _ = _codigo(eventos)
    assert codigo != kr.EXIT_OK


def test_comprobar_hereda_los_codigos_nuevos(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from scripts import kaggle_rescate

    monkeypatch.setattr(
        kaggle_rescate, "main", lambda argv: print(json.dumps({"descarga_incompleta": []})) or 0
    )

    def pasada(slug: str, eventos: list[dict[str, Any]], latidos: list[dict[str, Any]]) -> None:
        carpeta = tmp_path / "notebooks" / slug
        carpeta.mkdir(parents=True)
        (carpeta / "salida__registro_x.jsonl").write_text(
            "\n".join(json.dumps(e) for e in eventos), encoding="utf-8"
        )
        (carpeta / "salida__latido_x.jsonl").write_text(
            "\n".join(json.dumps(x) for x in latidos), encoding="utf-8"
        )

    pasada("p-bien", [INSTALADO, *_tarea_bien("t_1", T0, 1), _cierre(T0 + 30)], [])
    pasada(
        "p-sigue",
        [INSTALADO, *_tarea_colgada("t_1", T0), *_tarea_bien("t_2", T0 + 600, 1), _cierre(T0 + 700)],
        [],
    )
    pasada("p-detenida", [INSTALADO, _e("tarea_inicio", "t_1", T0)], [{"hora": T0 + 983.7, "tarea": "t_1"}])
    orden = ["comprobar", "--rescate", str(tmp_path)]
    assert kr.main([*orden, "--notebook", "p-bien", "--notebook", "p-sigue"]) == kr.EXIT_CON_COLGADAS
    resumen = json.loads(capsys.readouterr().out)
    assert resumen["pasadas_esperadas"]["p-sigue"]["codigo"] == 7
    assert kr.main([*orden, "--notebook", "p-bien", "--notebook", "p-detenida"]) == kr.EXIT_DETENIDA_VIVA
    assert (
        "viva y detenida"
        in json.loads(capsys.readouterr().out)["pasadas_esperadas"]["p-detenida"]["veredicto"]
    )
    assert kr.main([*orden, "--notebook", "p-bien"]) == kr.EXIT_OK
