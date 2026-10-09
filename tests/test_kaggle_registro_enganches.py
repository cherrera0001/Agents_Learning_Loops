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
        if isinstance(salida, Exception):
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
