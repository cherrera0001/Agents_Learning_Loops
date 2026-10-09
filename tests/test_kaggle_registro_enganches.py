"""Tests de los enganches de registro del notebook (`scripts/kaggle_registro_enganches.py`).

No necesitan el arnés, litellm ni Docker: cada enganche se prueba con un doble de lo que envuelve. Lo que
solo se ve con el arnés real (que el envoltorio está en la ruta por la que se llama al modelo, que el log
por tarea vuelve bajo un núcleo Jupyter) lo mide el ensayo local, no estos tests.
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import shutil
import subprocess
import sys
import types
from pathlib import Path
from typing import Any

import pytest

from scripts import kaggle_registro_enganches as ke


def _eventos(registro: ke.Registro) -> list[dict[str, Any]]:
    if not registro.ruta_eventos.exists():
        return []
    return [json.loads(x) for x in registro.ruta_eventos.read_text(encoding="utf-8").splitlines()]


def _tipos(registro: ke.Registro) -> list[str]:
    return [e["evento"] for e in _eventos(registro)]


class _Respuesta:
    def __init__(self, motivo: str) -> None:
        self.choices = [types.SimpleNamespace(finish_reason=motivo)]
        self.usage = types.SimpleNamespace(prompt_tokens=11, completion_tokens=3)


def _cliente(comportamiento: Any) -> type:
    class Cliente:
        async def acompletion(self, model: Any, messages: Any, tools: Any, **kwargs: Any) -> Any:
            return await comportamiento(model, messages, tools, **kwargs)

    return Cliente


MENSAJES = [{"role": "user", "content": "hola"}, {"role": "tool", "content": [{"text": "abc"}]}]


def test_caracteres_de_cuenta_el_texto_de_cualquier_estructura() -> None:
    class Modelo:
        def model_dump(self) -> dict[str, Any]:
            return {"content": "12345"}

    assert ke.caracteres_de(MENSAJES) == len("user") + len("hola") + len("tool") + len("abc")
    assert ke.caracteres_de([Modelo(), None, 7, True, ("ab",)]) == 5 + 2
    assert ke.caracteres_de(object()) > 0


def test_archivos_de_un_diff_no_repite_y_respeta_el_tope() -> None:
    diff = "diff --git a/x.py b/x.py\n+a\ndiff --git a/d/y.py b/d/y.py\ndiff --git a/x.py b/x.py\n"
    assert ke.archivos_de_un_diff(diff) == ["x.py", "d/y.py"]
    assert ke.archivos_de_un_diff(diff, tope=1) == ["x.py"]
    assert ke.archivos_de_un_diff("") == []


def test_una_peticion_respondida_deja_inicio_y_fin_con_su_motivo(tmp_path: Path) -> None:
    registro = ke.Registro(tmp_path, "s")
    registro.tarea("E1", "t_1", 1)

    async def responder(model: Any, messages: Any, tools: Any, **kwargs: Any) -> Any:
        return _Respuesta("tool_calls")

    clase = _cliente(responder)
    registro.envolver_cliente(clase)
    respuesta = asyncio.run(clase().acompletion(model="m", messages=MENSAJES, tools=[{"x": 1}], stream=False))

    assert respuesta.choices[0].finish_reason == "tool_calls"
    inicio, fin = (e for e in _eventos(registro) if e["evento"].startswith("peticion_"))
    assert (inicio["peticion"], inicio["tarea"], inicio["etiqueta"]) == (1, "t_1", "E1")
    assert (
        inicio["n_mensajes"] == 2
        and inicio["caracteres_entrada"] == 15
        and inicio["con_herramientas"] is True
    )
    assert inicio["hora_utc"].endswith("+00:00")
    assert (fin["peticion"], fin["motivo"], fin["prompt_tokens"]) == (1, "tool_calls", 11)
    assert registro.en_vuelo == {} and registro.motivos == {"tool_calls": 1}


def test_el_envoltorio_acepta_argumentos_posicionales(tmp_path: Path) -> None:
    registro = ke.Registro(tmp_path, "s")

    async def responder(model: Any, messages: Any, tools: Any, **kwargs: Any) -> Any:
        return {"choices": []}

    clase = _cliente(responder)
    registro.envolver_cliente(clase)
    asyncio.run(clase().acompletion("m", MENSAJES, None))
    inicio, fin = (e for e in _eventos(registro) if e["evento"].startswith("peticion_"))
    assert inicio["caracteres_entrada"] == 15 and inicio["con_herramientas"] is False
    assert fin["motivo"] == "sin_motivo"


def test_el_inicio_esta_en_disco_antes_de_llamar_al_modelo(tmp_path: Path) -> None:
    """Es lo que hace posible ver la petición en vuelo si la sesión muere durante la llamada."""
    registro = ke.Registro(tmp_path, "s")
    visto: list[list[str]] = []

    async def responder(model: Any, messages: Any, tools: Any, **kwargs: Any) -> Any:
        visto.append(_tipos(registro))
        assert registro.en_vuelo[1]["caracteres_entrada"] == 15
        return _Respuesta("stop")

    clase = _cliente(responder)
    registro.envolver_cliente(clase)
    asyncio.run(clase().acompletion(model="m", messages=MENSAJES, tools=None))
    assert visto == [["peticion_inicio"]]


def test_una_peticion_cancelada_por_un_tope_de_tiempo_deja_su_fin_como_cancelada(tmp_path: Path) -> None:
    registro = ke.Registro(tmp_path, "s")

    async def colgarse(model: Any, messages: Any, tools: Any, **kwargs: Any) -> Any:
        await asyncio.sleep(30)

    clase = _cliente(colgarse)
    registro.envolver_cliente(clase)

    async def con_tope() -> None:
        async with asyncio.timeout(0.05):
            await clase().acompletion(model="m", messages=MENSAJES, tools=None)

    with pytest.raises(TimeoutError):
        asyncio.run(con_tope())
    fin = _eventos(registro)[-1]
    assert (fin["evento"], fin["motivo"], fin["error"]) == ("peticion_fin", "cancelada", "CancelledError")
    assert fin["segundos"] >= 0.04 and registro.en_vuelo == {}


def test_un_error_del_modelo_se_anota_y_se_propaga(tmp_path: Path) -> None:
    registro = ke.Registro(tmp_path, "s")

    async def fallar(model: Any, messages: Any, tools: Any, **kwargs: Any) -> Any:
        raise ConnectionError("Connection error.")

    clase = _cliente(fallar)
    registro.envolver_cliente(clase)
    with pytest.raises(ConnectionError):
        asyncio.run(clase().acompletion(model="m", messages=MENSAJES, tools=None))
    fin = _eventos(registro)[-1]
    assert (fin["motivo"], fin["error"], fin["detalle"]) == ("error", "ConnectionError", "Connection error.")


def test_envolver_dos_veces_no_duplica_el_registro(tmp_path: Path) -> None:
    registro = ke.Registro(tmp_path, "s")

    async def responder(model: Any, messages: Any, tools: Any, **kwargs: Any) -> Any:
        return _Respuesta("stop")

    clase = _cliente(responder)
    registro.envolver_cliente(clase)
    registro.envolver_cliente(clase)
    asyncio.run(clase().acompletion(model="m", messages=MENSAJES, tools=None))
    assert _tipos(registro) == ["peticion_inicio", "peticion_fin"]


def test_un_registro_que_no_puede_escribir_no_detiene_la_llamada(tmp_path: Path) -> None:
    estorbo = tmp_path / "no_es_carpeta"
    estorbo.write_text("x", encoding="utf-8")
    registro = ke.Registro(estorbo, "s")

    async def responder(model: Any, messages: Any, tools: Any, **kwargs: Any) -> Any:
        return _Respuesta("stop")

    clase = _cliente(responder)
    registro.envolver_cliente(clase)
    respuesta = asyncio.run(clase().acompletion(model="m", messages=MENSAJES, tools=None))
    assert respuesta.choices[0].finish_reason == "stop"
    assert registro.errores == 2 and registro.ultimo_error is not None


def test_un_registro_inactivo_no_escribe_nada(tmp_path: Path) -> None:
    registro = ke.Registro(tmp_path, "s", activo=False)
    registro.tarea("E1", "t_1", 1)
    registro.fin_tarea(clase="resuelta")
    registro.corte("sesion")
    registro.latir()
    registro.arrancar_latido()
    registro.cerrar()
    assert list(tmp_path.iterdir()) == [] and registro.archivos() == []


def test_las_retrollamadas_anotan_la_llamada_y_conservan_las_ajenas(tmp_path: Path) -> None:
    registro = ke.Registro(tmp_path, "s")
    ajena = object()
    litellm = types.SimpleNamespace(callbacks=[ajena])
    registro.enganchar_retrollamadas(litellm, object)
    registro.enganchar_retrollamadas(litellm, object)
    assert len(litellm.callbacks) == 2 and litellm.callbacks[0] is ajena

    propia = litellm.callbacks[1]
    registro.en_vuelo[4] = {"hora": 0.0}
    propia.log_pre_api_call("m", [], {"litellm_call_id": "abc"})
    propia.log_failure_event({"litellm_call_id": "abc"}, None, None, None)
    asyncio.run(propia.async_log_success_event({"litellm_call_id": "abc"}, None, None, None))
    antes, fallo, exito = _eventos(registro)
    assert (antes["evento"], antes["llamada"], antes["peticion_en_curso"]) == ("cb_antes", "abc", 4)
    assert (fallo["evento"], fallo["canal"]) == ("cb_fallo", "sincrono")
    assert (exito["evento"], exito["canal"]) == ("cb_exito", "asincrono")
    assert registro.retrollamadas == {"cb_antes": 1, "cb_fallo": 1, "cb_exito": 1}


def _modulo_de_sandbox(llamadas: list[Any], salida: Any) -> Any:
    async def sandbox_start(docker: Any) -> str:
        llamadas.append("start")
        return "sb1"

    async def sandbox_stop(docker: Any, sandbox_id: str) -> str:
        llamadas.append(("stop", sandbox_id))
        return "parado"

    async def sandbox_exec(docker: Any, sandbox_id: str, orden: str) -> Any:
        llamadas.append(("exec", orden))
        if isinstance(salida, BaseException):
            raise salida
        return types.SimpleNamespace(stdout=salida, exit_code=0)

    return types.SimpleNamespace(
        sandbox_start=sandbox_start, sandbox_stop=sandbox_stop, sandbox_exec=sandbox_exec
    )


def test_el_diff_se_toma_antes_de_destruir_el_sandbox(tmp_path: Path) -> None:
    diff = "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-a\n+b\n"
    llamadas: list[Any] = []
    modulo = _modulo_de_sandbox(llamadas, diff)
    registro = ke.Registro(tmp_path, "s")
    registro.tarea("E1", "repo/t_1", 1)
    registro.envolver_sandbox(modulo)
    docker = types.SimpleNamespace(sandboxes={"sb1": {"workspace": tmp_path / "ws"}})

    async def sesion() -> Any:
        sandbox_id = await modulo.sandbox_start(docker)
        assert registro.espacio == tmp_path / "ws"
        return await modulo.sandbox_stop(docker, sandbox_id)

    assert asyncio.run(sesion()) == "parado"
    assert llamadas == ["start", ("exec", ke.DIFF_AL_CIERRE), ("stop", "sb1")]
    guardado = tmp_path / "results" / "E1" / "diffs_cierre" / "repo_t_1.diff"
    assert guardado.read_bytes() == diff.encode()
    evento = _eventos(registro)[-1]
    assert evento["evento"] == "diff_cierre" and evento["archivos"] == ["x.py"] and evento["guardado"] is True
    assert (evento["bytes"], evento["sha256"]) == (len(diff), hashlib.sha256(diff.encode()).hexdigest())
    assert registro.espacio is None


def test_si_el_diff_falla_el_sandbox_se_destruye_igual(tmp_path: Path) -> None:
    llamadas: list[Any] = []
    modulo = _modulo_de_sandbox(llamadas, RuntimeError("sin git"))
    registro = ke.Registro(tmp_path, "s")
    registro.tarea("E1", "t_1", 1)
    registro.envolver_sandbox(modulo)
    assert asyncio.run(modulo.sandbox_stop(object(), "sb9")) == "parado"
    assert llamadas[-1] == ("stop", "sb9")
    assert _eventos(registro)[-1]["error"] == "RuntimeError: sin git" and registro.errores == 1


def test_el_motivo_de_fin_del_agente_queda_aunque_el_arnes_lo_descarte(tmp_path: Path) -> None:
    class Evaluador:
        async def _run_agent_sandbox(self, task: Any, snapshot: Any, **kwargs: Any) -> Any:
            return ("parche", "Agent exceeded tool call budget (40 calls)", "traza")

    registro = ke.Registro(tmp_path, "s")
    registro.envolver_evaluador(Evaluador)
    # El arnés mira la firma para decidir qué argumentos pasa: el envoltorio debe aceptar cualquiera.
    parametros = inspect.signature(Evaluador._run_agent_sandbox).parameters.values()
    assert any(p.kind is inspect.Parameter.VAR_KEYWORD for p in parametros)
    contexto = types.SimpleNamespace(patch_submitted=False, tool_calls_used=40, llm_calls_used=46)
    resultado = asyncio.run(Evaluador()._run_agent_sandbox("t", "s", context=contexto, patch_path=None))
    assert resultado == ("parche", "Agent exceeded tool call budget (40 calls)", "traza")
    evento = _eventos(registro)[-1]
    assert evento["evento"] == "agente_fin" and evento["error"].startswith("Agent exceeded tool call budget")
    assert (evento["entrego"], evento["llamadas_herramientas"], evento["parche_caracteres"]) == (False, 40, 6)


def test_si_el_agente_lanza_el_evento_lo_dice_y_la_excepcion_sigue(tmp_path: Path) -> None:
    class Evaluador:
        async def _run_agent_sandbox(self, *args: Any, **kwargs: Any) -> Any:
            raise KeyError("snapshot")

    registro = ke.Registro(tmp_path, "s")
    registro.envolver_evaluador(Evaluador)
    with pytest.raises(KeyError):
        asyncio.run(Evaluador()._run_agent_sandbox())
    evento = _eventos(registro)[-1]
    assert evento["lanzo"] is True and evento["error"].startswith("KeyError")


def test_el_latido_copia_el_log_del_servidor_y_trae_la_peticion_en_vuelo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log = tmp_path / "vllm.log"
    log.write_text("INFO arranca\nINFO sirve\n", encoding="utf-8")
    proceso = types.SimpleNamespace(poll=lambda: -9)
    servidor = types.SimpleNamespace(log_path=str(log), base_url="", process=proceso)
    registro = ke.Registro(tmp_path / "w", "s", servidor)
    registro.carpeta.mkdir()
    registro.en_vuelo[7] = {"hora": 0.0, "caracteres_entrada": 99}

    def nvidia(orden: Any, **kwargs: Any) -> Any:
        assert tuple(orden) == ke.CONSULTA_GPU
        return types.SimpleNamespace(returncode=0, stdout="0, 37, 20312, 23034, 61\n1, 0, 3, 23034, 40\n")

    monkeypatch.setattr(ke.subprocess, "run", nvidia)
    registro.latir()
    (latido,) = [json.loads(x) for x in registro.ruta_latido.read_text(encoding="utf-8").splitlines()]
    assert latido["gpu"] == [["0", "37", "20312", "23034", "61"], ["1", "0", "3", "23034", "40"]]
    assert latido["servidor_log_bytes"] == log.stat().st_size == registro.ruta_servidor.stat().st_size
    assert registro.ruta_servidor.read_bytes() == log.read_bytes()
    assert latido["en_vuelo"][0]["peticion"] == 7 and latido["en_vuelo"][0]["caracteres_entrada"] == 99
    assert latido["servidor_codigo_de_salida"] == -9 and latido["servidor_sano"] is None
    assert latido["diff_en_curso"] is None and registro.errores == 0


def test_el_latido_no_falla_sin_gpu_ni_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def sin_nvidia(orden: Any, **kwargs: Any) -> Any:
        raise FileNotFoundError("nvidia-smi")

    monkeypatch.setattr(ke.subprocess, "run", sin_nvidia)
    registro = ke.Registro(tmp_path, "s", types.SimpleNamespace(log_path=str(tmp_path / "no_existe.log")))
    registro.latir()
    (latido,) = [json.loads(x) for x in registro.ruta_latido.read_text(encoding="utf-8").splitlines()]
    assert latido["gpu"] == {"error": "FileNotFoundError"} and latido["servidor_log_bytes"] is None
    assert not registro.ruta_servidor.exists() and registro.archivos() == [registro.ruta_latido]


@pytest.mark.skipif(shutil.which("git") is None, reason="necesita git")
def test_el_diff_en_curso_se_lee_sin_tocar_el_arbol(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    git = ["git", "-C", str(ws), "-c", "user.name=t", "-c", "user.email=t@t", "-c", "core.autocrlf=false"]
    subprocess.run([*git, "init", "-q"], check=True)
    (ws / "x.py").write_text("a\n", encoding="utf-8", newline="\n")
    subprocess.run([*git, "add", "."], check=True)
    subprocess.run([*git, "commit", "-q", "-m", "base"], check=True)
    subprocess.run([*git, "tag", "_swegemma_baseline"], check=True)
    (ws / "x.py").write_text("b\n", encoding="utf-8", newline="\n")
    (ws / "nuevo.py").write_text("c\n", encoding="utf-8", newline="\n")
    antes = subprocess.run([*git, "status", "--porcelain"], capture_output=True, check=True).stdout

    registro = ke.Registro(tmp_path / "w", "s")
    registro.carpeta.mkdir()
    registro.estado["tarea"] = "t_1"
    registro.espacio = ws
    registro.latir()
    (latido,) = [json.loads(x) for x in registro.ruta_latido.read_text(encoding="utf-8").splitlines()]
    en_curso = latido["diff_en_curso"]
    assert en_curso["tarea"] == "t_1" and en_curso["bytes"] > 0 and en_curso["sin_seguimiento"] == 1
    assert b"+b" in registro.ruta_diff_en_curso.read_bytes()
    assert subprocess.run([*git, "status", "--porcelain"], capture_output=True, check=True).stdout == antes


def test_tarea_corte_y_cierre_dejan_lo_que_estaba_en_vuelo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ke.Registro, "_gpu", lambda self: [])
    registro = ke.Registro(tmp_path, "s", latido_segundos=0.01)
    registro.arrancar_latido()
    registro.tarea("E1", "t_1", 1)
    registro.en_vuelo[3] = {"hora": 0.0}
    registro.fin_tarea(clase="tiempo_agotado_con_parche", error="x")
    registro.corte("servidor", indice=2)
    registro.cerrar()
    eventos = {e["evento"]: e for e in _eventos(registro)}
    assert list(eventos) == ["tarea_inicio", "tarea_fin", "corte", "cierre"]
    assert eventos["tarea_fin"]["en_vuelo"] == [3] and eventos["tarea_fin"]["tarea"] == "t_1"
    assert eventos["corte"]["cortado_por"] == "servidor" and eventos["corte"]["tarea"] is None
    assert eventos["cierre"]["latidos"] >= 2 and eventos["cierre"]["errores_del_registro"] == 0
    assert registro._hilo is not None and not registro._hilo.is_alive()
    assert set(registro.archivos()) == {registro.ruta_eventos, registro.ruta_latido}


def test_instalar_sin_el_arnes_no_lanza_y_dice_que_enganche_falta(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
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
    registro = ke.instalar_registro(tmp_path, "s", None, latido_segundos=60)
    registro.cerrar()
    fallos = [k for k, v in registro.enganches.items() if v.startswith("FALLO")]
    assert len(fallos) == 5 and all("Error" in registro.enganches[k] for k in fallos)
    instalado = _eventos(registro)[0]
    assert instalado["evento"] == "registro_instalado" and instalado["nucleo"] == "sin IPython"
    assert "REGISTRO enganche" in capsys.readouterr().out


def test_instalar_inactivo_no_toca_nada_y_un_modo_de_rich_desconocido_se_rechaza(tmp_path: Path) -> None:
    registro = ke.instalar_registro(tmp_path, "s", None, activo=False)
    assert registro.enganches == {} and registro._hilo is None and list(tmp_path.iterdir()) == []
    with pytest.raises(ValueError, match="parche_rich"):
        ke.instalar_registro(tmp_path, "s", None, parche_rich="todo")


# ---------------------------------------------------------------------------
# Pruebas añadidas tras la revisión independiente del PR #161
# ---------------------------------------------------------------------------


def test_dos_peticiones_llevan_numeros_distintos_y_cada_fin_el_de_su_inicio(tmp_path: Path) -> None:
    registro = ke.Registro(tmp_path, "s")
    motivos = iter(["tool_calls", "stop"])

    async def responder(model: Any, messages: Any, tools: Any, **kwargs: Any) -> Any:
        return _Respuesta(next(motivos))

    clase = _cliente(responder)
    registro.envolver_cliente(clase)

    async def dos() -> None:
        await clase().acompletion(model="m", messages=MENSAJES, tools=None)
        await clase().acompletion(
            model="m", messages=[*MENSAJES, {"role": "user", "content": "x"}], tools=None
        )

    asyncio.run(dos())
    eventos = [e for e in _eventos(registro) if e["evento"].startswith("peticion_")]
    assert [(e["evento"], e["peticion"]) for e in eventos] == [
        ("peticion_inicio", 1),
        ("peticion_fin", 1),
        ("peticion_inicio", 2),
        ("peticion_fin", 2),
    ]
    assert [e["motivo"] for e in eventos if e["evento"] == "peticion_fin"] == ["tool_calls", "stop"]
    assert eventos[2]["caracteres_entrada"] == eventos[0]["caracteres_entrada"] + 5
    assert registro.peticiones == 2 and registro.motivos == {"tool_calls": 1, "stop": 1}


def test_el_inicio_de_cada_peticion_se_sincroniza_a_disco_y_el_fin_no(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sincronizaciones: list[int] = []
    real = ke.os.fsync
    monkeypatch.setattr(ke.os, "fsync", lambda fd: (sincronizaciones.append(fd), real(fd))[1])
    registro = ke.Registro(tmp_path, "s")
    numero = registro.inicio_peticion("m", MENSAJES, None, {})
    assert len(sincronizaciones) == 1
    registro.fin_peticion(numero, respuesta=_Respuesta("stop"))
    registro.evento("cb_antes", llamada="x")
    assert len(sincronizaciones) == 1
    registro.tarea("E1", "t_1", 1)
    assert len(sincronizaciones) == 2


def test_la_retrollamada_anota_la_peticion_mas_reciente_de_las_que_estan_en_vuelo(tmp_path: Path) -> None:
    registro = ke.Registro(tmp_path, "s")
    litellm = types.SimpleNamespace(callbacks=None)
    registro.enganchar_retrollamadas(litellm, object)
    registro.en_vuelo.update({4: {"hora": 0.0}, 9: {"hora": 0.0}})
    litellm.callbacks[0].log_pre_api_call("m", [], {"litellm_call_id": "abc"})
    assert _eventos(registro)[-1]["peticion_en_curso"] == 9


def test_el_corte_anota_lo_que_estaba_en_vuelo(tmp_path: Path) -> None:
    registro = ke.Registro(tmp_path, "s")
    registro.en_vuelo.update({3: {"hora": 0.0}, 5: {"hora": 0.0}})
    registro.corte("sesion", indice=2)
    corte = _eventos(registro)[-1]
    assert (corte["evento"], corte["cortado_por"], corte["en_vuelo"], corte["indice"]) == (
        "corte",
        "sesion",
        [3, 5],
        2,
    )


def test_los_archivos_del_registro_incluyen_la_copia_del_log_del_servidor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ke.Registro, "_gpu", lambda self: [])
    log = tmp_path / "vllm.log"
    log.write_text("INFO\n", encoding="utf-8")
    registro = ke.Registro(tmp_path / "w", "s", types.SimpleNamespace(log_path=str(log)))
    registro.carpeta.mkdir()
    registro.evento("tarea_inicio")
    registro.latir()
    assert registro.archivos() == [registro.ruta_eventos, registro.ruta_latido, registro.ruta_servidor]
    assert all(p.stat().st_size > 0 for p in registro.archivos())


def _arnes_falso(monkeypatch: pytest.MonkeyPatch, *, sin_consola: bool = False) -> dict[str, Any]:
    """Módulos falsos con la forma de lo que `instalar_registro` importa del arnés, de litellm y de rich."""
    consolas: list[dict[str, Any]] = []

    def consola_original(*args: Any, **kwargs: Any) -> str:
        consolas.append(kwargs)
        return "consola"

    async def nada(*args: Any, **kwargs: Any) -> None:
        return None

    class Evaluator:
        async def _run_agent_sandbox(self, *args: Any, **kwargs: Any) -> Any:
            return ("", None, None)

    class LiteLLMClient:
        async def acompletion(self, *args: Any, **kwargs: Any) -> Any:
            return _Respuesta("stop")

    agent_runner = types.ModuleType("swegemma.harness.agent_runner")
    agent_runner.sandbox_start = agent_runner.sandbox_stop = agent_runner.sandbox_exec = nada  # type: ignore[attr-defined]
    if not sin_consola:
        agent_runner.Console = consola_original  # type: ignore[attr-defined]
    consola_de_rich = types.ModuleType("rich.console")
    consola_de_rich._is_jupyter = lambda: True  # type: ignore[attr-defined]
    modulos: dict[str, Any] = {
        "swegemma": types.ModuleType("swegemma"),
        "swegemma.harness": types.ModuleType("swegemma.harness"),
        "swegemma.harness.agent_runner": agent_runner,
        "swegemma.evaluate": types.ModuleType("swegemma.evaluate"),
        "google": types.ModuleType("google"),
        "google.adk": types.ModuleType("google.adk"),
        "google.adk.models": types.ModuleType("google.adk.models"),
        "google.adk.models.lite_llm": types.ModuleType("google.adk.models.lite_llm"),
        "litellm": types.ModuleType("litellm"),
        "litellm.integrations": types.ModuleType("litellm.integrations"),
        "litellm.integrations.custom_logger": types.ModuleType("litellm.integrations.custom_logger"),
        "rich": types.ModuleType("rich"),
        "rich.console": consola_de_rich,
    }
    modulos["swegemma.harness"].agent_runner = agent_runner
    modulos["swegemma.evaluate"].Evaluator = Evaluator
    modulos["google.adk.models.lite_llm"].LiteLLMClient = LiteLLMClient
    modulos["litellm"].callbacks = []
    modulos["litellm.integrations.custom_logger"].CustomLogger = object
    modulos["rich"].console = consola_de_rich
    for nombre, modulo in modulos.items():
        monkeypatch.setitem(sys.modules, nombre, modulo)
    monkeypatch.setattr(ke.Registro, "_gpu", lambda self: [])
    return {
        "agent_runner": agent_runner,
        "consolas": consolas,
        "original": consola_original,
        "rich": consola_de_rich,
    }


def test_el_parche_de_archivo_reemplaza_la_consola_del_arnes_y_fuerza_que_no_sea_jupyter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    arnes = _arnes_falso(monkeypatch)
    registro = ke.instalar_registro(tmp_path, "s", None, parche_rich="archivo", latido_segundos=60)
    registro.cerrar()
    assert registro.enganches_que_faltan() == [] and registro.parche_rich == "archivo"
    assert all(not v.startswith("FALLO") for v in registro.enganches.values()), registro.enganches
    registro.exigir_enganches()

    consola = arnes["agent_runner"].Console
    assert consola is not arnes["original"]
    assert consola(file="log", force_terminal=True, width=120) == "consola"
    assert arnes["consolas"] == [
        {"file": "log", "force_terminal": True, "width": 120, "force_jupyter": False}
    ]
    # La consola con que el arnés pinta en el notebook no se toca.
    assert arnes["rich"]._is_jupyter() is True


@pytest.mark.parametrize(("modo", "detecta_jupyter"), [("global", False), ("ninguno", True)])
def test_los_otros_modos_de_rich_no_reemplazan_la_consola_del_arnes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, modo: str, detecta_jupyter: bool
) -> None:
    arnes = _arnes_falso(monkeypatch)
    registro = ke.instalar_registro(tmp_path, "s", None, parche_rich=modo, latido_segundos=60)
    registro.cerrar()
    assert arnes["agent_runner"].Console is arnes["original"]
    assert arnes["rich"]._is_jupyter() is detecta_jupyter and registro.parche_rich == modo


def test_la_guardia_detiene_el_notebook_si_un_enganche_exigido_no_quedo_instalado(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _arnes_falso(monkeypatch, sin_consola=True)
    registro = ke.instalar_registro(tmp_path, "s", None, parche_rich="archivo", latido_segundos=60)
    registro.cerrar()
    assert registro.enganches_que_faltan() == ["logs por tarea (rich)"]
    with pytest.raises(RuntimeError, match=r"GUARDIA registro: no quedó instalado logs por tarea \(rich\)"):
        registro.exigir_enganches()
    guardia = next(e for e in _eventos(registro) if e["evento"] == "guardia")
    assert guardia["cuando"] == "antes de la primera tarea" and guardia["problemas"] == [
        "logs por tarea (rich)"
    ]


def test_la_guardia_no_exige_las_retrollamadas_ni_actua_con_el_registro_inactivo(tmp_path: Path) -> None:
    registro = ke.Registro(tmp_path, "s")
    registro.enganches = {ke.ENGANCHE_NO_EXIGIDO: "FALLO ImportError: x", "latido": "cada 30 s"}
    registro.exigir_enganches()
    inactivo = ke.Registro(tmp_path / "otro", "s", activo=False)
    inactivo.enganches = {"logs por tarea (rich)": "FALLO x"}
    inactivo.exigir_enganches()
    inactivo.comprobar_primera_tarea(tmp_path / "no_existe.log")


def _con_fin_de_agente_y_diff(registro: ke.Registro) -> ke.Registro:
    """Deja el registro como tras una primera tarea sana: una petición respondida, su agente_fin y su diff."""
    registro.fin_peticion(registro.inicio_peticion("m", MENSAJES, None, {}), respuesta=_Respuesta("stop"))
    registro.evento("agente_fin", error=None)
    registro.diffs_tomados = 1
    return registro


def test_la_guardia_tras_la_primera_tarea_mira_el_log_y_las_peticiones(tmp_path: Path) -> None:
    log = tmp_path / "t_1.log"
    registro = _con_fin_de_agente_y_diff(ke.Registro(tmp_path, "s"))

    with pytest.raises(RuntimeError, match=r"no existe el log por tarea t_1\.log"):
        registro.comprobar_primera_tarea(log)
    log.write_bytes(b"")
    with pytest.raises(RuntimeError, match=r"el log por tarea t_1\.log pesa 0 bytes"):
        registro.comprobar_primera_tarea(log)
    log.write_bytes(b"x")
    registro.comprobar_primera_tarea(log)
    guardias = [e for e in _eventos(registro) if e["evento"] == "guardia"]
    assert [g["cuando"] for g in guardias] == ["tras la primera tarea"] * 2


@pytest.mark.parametrize("error", [ConnectionError("x"), asyncio.CancelledError()])
def test_la_guardia_no_cuenta_como_respondida_una_peticion_con_error_ni_una_cancelada(
    tmp_path: Path, error: BaseException
) -> None:
    # El control sin parche no exige el log, pero sí las peticiones.
    registro = ke.Registro(tmp_path, "s")
    registro.parche_rich = "ninguno"
    registro.evento("agente_fin", error=None)
    registro.diffs_tomados = 1
    registro.fin_peticion(registro.inicio_peticion("m", MENSAJES, None, {}), error=error)
    patron = (
        r"ninguna petición respondida \(1 iniciadas, 1 con error o canceladas\): o el enganche de peticiones "
        r"no surte efecto, o el servidor no respondió"
    )
    with pytest.raises(RuntimeError, match=patron):
        registro.comprobar_primera_tarea(tmp_path / "no_existe.log")
    registro.fin_peticion(registro.inicio_peticion("m", MENSAJES, None, {}), respuesta=_Respuesta("stop"))
    registro.comprobar_primera_tarea(tmp_path / "no_existe.log")


def test_la_guardia_exige_que_la_primera_tarea_deje_su_fin_de_agente_y_su_diff(tmp_path: Path) -> None:
    log = tmp_path / "t_1.log"
    log.write_bytes(b"x")
    registro = ke.Registro(tmp_path, "s")
    registro.fin_peticion(registro.inicio_peticion("m", MENSAJES, None, {}), respuesta=_Respuesta("stop"))
    with pytest.raises(
        RuntimeError, match=r"no dejó su agente_fin .*; la primera tarea no dejó su diff_cierre"
    ):
        registro.comprobar_primera_tarea(log)
    registro.evento("agente_fin", error=None)
    with pytest.raises(RuntimeError, match=r"GUARDIA registro: la primera tarea no dejó su diff_cierre"):
        registro.comprobar_primera_tarea(log)
    # Un diff que falló no cuenta: el evento existe, pero el diff no se tomó.
    asyncio.run(
        registro.diff_al_cierre(_modulo_de_sandbox([], RuntimeError("sin git")).sandbox_exec, None, "sb")
    )
    with pytest.raises(RuntimeError, match="no dejó su diff_cierre"):
        registro.comprobar_primera_tarea(log)
    asyncio.run(registro.diff_al_cierre(_modulo_de_sandbox([], "diff").sandbox_exec, None, "sb"))
    registro.comprobar_primera_tarea(log)
    assert registro.vistos["agente_fin"] == 1 and registro.diffs_tomados == 1


class _Interrupcion(BaseException):
    """Una excepción que no hereda de Exception, como las que atraviesan el arnés al cancelar."""


@pytest.mark.parametrize("interrupcion", [asyncio.CancelledError(), _Interrupcion("x")])
def test_si_el_diff_se_interrumpe_el_sandbox_se_destruye_igual_y_la_interrupcion_sigue(
    tmp_path: Path, interrupcion: BaseException
) -> None:
    llamadas: list[Any] = []
    modulo = _modulo_de_sandbox(llamadas, interrupcion)
    registro = ke.Registro(tmp_path, "s")
    registro.tarea("E1", "t_1", 1)
    registro.envolver_sandbox(modulo)
    registro.espacio = tmp_path

    async def parar() -> None:
        await modulo.sandbox_stop(object(), "sb9")

    with pytest.raises(type(interrupcion)):
        asyncio.run(parar())
    assert llamadas == [("exec", ke.DIFF_AL_CIERRE), ("stop", "sb9")]
    assert registro.espacio is None and registro.diffs_tomados == 0


def test_con_el_registro_inactivo_el_cierre_del_sandbox_no_ejecuta_nada_mas(tmp_path: Path) -> None:
    llamadas: list[Any] = []
    modulo = _modulo_de_sandbox(llamadas, "diff")
    registro = ke.Registro(tmp_path, "s", activo=False)
    registro.estado.update(etiqueta="E1", tarea="t_1")
    registro.envolver_sandbox(modulo)
    assert asyncio.run(modulo.sandbox_stop(object(), "sb1")) == "parado"
    assert llamadas == [("stop", "sb1")] and list(tmp_path.iterdir()) == [] and registro.diffs_tomados == 0
