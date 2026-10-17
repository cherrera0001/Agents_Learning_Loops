"""Tests del #215: el registro escribe el muestreo enviado, la causa del fin y las peticiones canceladas.

Tres huecos que el concilio 48 halló en seis sesiones reales: el registro no decía con qué temperatura,
`top_p` y tope de tokens salía cada petición; la clase del notebook llamaba «llamadas agotadas» a tareas
cortadas por tiempo; y de una petición cancelada solo quedaba que se canceló.

No usan el arnés ni litellm: el servidor del modelo es un servidor HTTP local que solo publica el contador
de tokens. Lo que solo se ve con las ruedas reales lo mide el ensayo local.
"""

from __future__ import annotations

import asyncio
import json
import threading
import types
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from scripts import kaggle_registro as kr
from scripts import kaggle_registro_enganches as ke
from scripts.kaggle_submission import SubmissionRecord

RAIZ = Path(__file__).resolve().parents[1]
REGISTRO_DE_ENVIOS = RAIZ / "experiments" / "gemma_developer_agent" / "submissions" / "registry.json"
MENSAJES = [{"role": "user", "content": "hola"}, {"role": "tool", "content": [{"text": "abc"}]}]
TIEMPO = "Agent exceeded session timeout (4.5 min)"
LLAMADAS = "Agent exceeded tool call budget (28 calls)"
# El cuerpo que el servidor falso del ensayo recibió del kit vigente (bloque R1, #205).
MUESTREO_DEL_KIT = {"temperature": 0.2, "top_p": 0.95, "max_completion_tokens": 8192}
RAZONAMIENTO_DEL_KIT = {"thinking_token_budget": 4096, "chat_template_kwargs": {"enable_thinking": True}}
MUESTREO_ESPERADO = {"temperatura": 0.2, "top_p": 0.95, "tope_tokens_salida": 8192}


def _eventos(registro: ke.Registro, tipo: str | None = None) -> list[dict[str, Any]]:
    lineas = registro.ruta_eventos.read_text(encoding="utf-8").splitlines()
    return [e for e in map(json.loads, lineas) if tipo is None or e["evento"] == tipo]


class _Respuesta:
    def __init__(self, motivo: str = "tool_calls", tokens: int = 3) -> None:
        self.choices = [types.SimpleNamespace(finish_reason=motivo)]
        self.usage = types.SimpleNamespace(prompt_tokens=11, completion_tokens=tokens)


class _Contador:
    """Servidor local que publica el contador de tokens como vLLM, y nada más."""

    def __init__(self, texto: str | None = None) -> None:
        self.tokens = 0
        self.lecturas = 0
        self.texto = texto
        contador = self

        class Manejador(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: Any) -> None:
                return

            def do_GET(self) -> None:
                contador.lecturas += 1
                cuerpo = contador.texto if contador.texto is not None else contador.metricas()
                datos = cuerpo.encode("utf-8")
                self.send_response(200 if self.path == "/metrics" else 404)
                self.send_header("Content-Length", str(len(datos)))
                self.end_headers()
                self.wfile.write(datos)

        self.http = ThreadingHTTPServer(("127.0.0.1", 0), Manejador)
        threading.Thread(target=self.http.serve_forever, daemon=True).start()
        self.servidor = types.SimpleNamespace(base_url=f"http://127.0.0.1:{self.http.server_address[1]}/v1")

    def metricas(self) -> str:
        return (
            "# HELP vllm:generation_tokens_total Number of generation tokens processed.\n"
            "# TYPE vllm:generation_tokens_total counter\n"
            f'vllm:generation_tokens_total{{engine="0",model_name="/m/2"}} {float(self.tokens)!r}\n'
            'vllm:generation_tokens_created{engine="0",model_name="/m/2"} 1.7918948e+09\n'
            'vllm:prompt_tokens_total{engine="0",model_name="/m/2"} 3.321204e+06\n'
        )


@pytest.fixture
def contador() -> Iterator[_Contador]:
    servidor = _Contador()
    yield servidor
    servidor.http.shutdown()
    servidor.http.server_close()


def _agente(registro: ke.Registro, error: str | None, entrego: bool | None, llamadas: int = 5) -> None:
    """Corre un `_run_agent_sandbox` envuelto que termina como el arnés: (parche, error, traza)."""

    class Evaluador:
        async def _run_agent_sandbox(self, task: Any, snapshot: Any, **kwargs: Any) -> Any:
            return ("parche", error, "traza")

    registro.envolver_evaluador(Evaluador)
    contexto = types.SimpleNamespace(
        patch_submitted=entrego, tool_calls_used=llamadas, llm_calls_used=llamadas
    )
    asyncio.run(Evaluador()._run_agent_sandbox("t", "s", context=contexto))


# ---------------------------------------------------------------------------
# Criterio 1: el muestreo que lleva la petición
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("opciones", "esperado"),
    [
        (MUESTREO_DEL_KIT, MUESTREO_ESPERADO),
        ({"extra_body": MUESTREO_DEL_KIT}, MUESTREO_ESPERADO),
        ({"temperature": 0, "max_tokens": 512}, {"temperatura": 0, "top_p": None, "tope_tokens_salida": 512}),
        # Suelto manda sobre `extra_body`; el tope con su primer nombre conocido
        (
            {"temperature": 0.7, "max_output_tokens": 64, "extra_body": {"temperature": 0.1, "top_p": 0.5}},
            {"temperatura": 0.7, "top_p": 0.5, "tope_tokens_salida": 64},
        ),
        (
            types.SimpleNamespace(temperature=1.0, top_p=1),
            {"temperatura": 1.0, "top_p": 1, "tope_tokens_salida": None},
        ),
        # Solo números: ni un texto ni un booleano se anotan
        (
            {"temperature": "0.2", "top_p": True},
            {"temperatura": None, "top_p": None, "tope_tokens_salida": None},
        ),
        ({}, {"temperatura": None, "top_p": None, "tope_tokens_salida": None}),
        (None, {"temperatura": None, "top_p": None, "tope_tokens_salida": None}),
        ({"extra_body": "roto"}, {"temperatura": None, "top_p": None, "tope_tokens_salida": None}),
    ],
)
def test_el_muestreo_sale_de_la_peticion_solo_con_numeros_y_nunca_lanza(
    opciones: Any, esperado: dict[str, Any]
) -> None:
    assert ke.muestreo_enviado(opciones) == esperado


def test_peticion_inicio_escribe_el_muestreo_y_el_presupuesto_que_lleva_la_peticion(tmp_path: Path) -> None:
    registro = ke.Registro(tmp_path, "s")
    recibido: dict[str, Any] = {}

    class Cliente:
        async def acompletion(self, model: Any, messages: Any, tools: Any, **kwargs: Any) -> Any:
            recibido.update(kwargs)
            return _Respuesta()

    registro.envolver_cliente(Cliente)
    opciones = {**MUESTREO_DEL_KIT, "extra_body": RAZONAMIENTO_DEL_KIT}
    asyncio.run(Cliente().acompletion(model="m", messages=MENSAJES, tools=None, **opciones))

    (inicio,) = _eventos(registro, "peticion_inicio")
    nuevos = {k: inicio[k] for k in (*MUESTREO_ESPERADO, "presupuesto_razonamiento")}
    assert nuevos == {**MUESTREO_ESPERADO, "presupuesto_razonamiento": 4096}
    assert all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in nuevos.values())
    assert inicio["pide_razonar"] is True
    # El envoltorio anota y no cambia nada de lo que llega al cliente
    assert recibido == opciones


def test_una_peticion_sin_muestreo_lo_dice_con_none_y_no_con_un_valor_por_defecto(tmp_path: Path) -> None:
    registro = ke.Registro(tmp_path, "s")
    registro.inicio_peticion("m", MENSAJES, None, {})
    (inicio,) = _eventos(registro, "peticion_inicio")
    assert [inicio[k] for k in MUESTREO_ESPERADO] == [None, None, None]
    assert registro.errores == 0


def test_la_retrollamada_de_antes_anota_el_muestreo_del_cuerpo_que_armo_litellm(tmp_path: Path) -> None:
    registro = ke.Registro(tmp_path, "s")
    litellm = types.SimpleNamespace(callbacks=[])
    registro.enganchar_retrollamadas(litellm, object)
    cuerpo = {
        **MUESTREO_DEL_KIT,
        **RAZONAMIENTO_DEL_KIT,
        "messages": [{"role": "user", "content": "secreto"}],
    }
    con_cuerpo = {"litellm_call_id": "a", "additional_args": {"complete_input_dict": cuerpo}}
    litellm.callbacks[0].log_pre_api_call("m", [], con_cuerpo)
    litellm.callbacks[0].log_pre_api_call("m", [], {"litellm_call_id": "b"})
    litellm.callbacks[0].log_success_event(con_cuerpo, None, None, None)

    con, sin, exito = _eventos(registro)
    assert con["muestreo_del_cuerpo"] == {
        **MUESTREO_ESPERADO,
        "pide_razonar": True,
        "presupuesto_razonamiento": 4096,
    }
    # Sin cuerpo no inventa nada, y solo la retrollamada de antes lo anota
    assert "muestreo_del_cuerpo" not in sin and "muestreo_del_cuerpo" not in exito
    assert "secreto" not in registro.ruta_eventos.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Criterio 2: la causa del fin, con una sola definición
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("agente", "causa"),
    [
        ({"error": TIEMPO, "entrego": False, "llamadas_herramientas": 27}, "tiempo"),
        ({"error": LLAMADAS, "entrego": False}, "llamadas"),
        ({"error": "Agent exceeded turns budget (100)", "entrego": False}, "turnos"),
        ({"error": "exceeded the maximum allowed LLM turns"}, "turnos"),
        ({"error": "litellm.InternalServerError: Connection error. LiteLLM Retried: 5 times"}, "servidor"),
        ({"error": "RuntimeError: otra cosa", "lanzo": True}, "otro_error"),
        ({"error": None, "entrego": True}, "entrega"),
        ({"error": None, "entrego": False}, "sin_entrega"),
        ({"error": None, "entrego": None}, "fin_sin_error"),
        (None, "sin_agente_fin"),
    ],
)
def test_la_causa_del_fin_sale_del_error_del_agente(agente: Any, causa: str) -> None:
    assert ke.causa_del_fin(agente) == causa
    assert ke.causa_del_fin(agente, colgada=True) == ke.CLASE_TAREA_COLGADA


@pytest.mark.parametrize(
    ("clase", "causa", "contradice"),
    [
        ("llamadas_agotadas_con_parche", "tiempo", True),
        ("llamadas_agotadas_sin_parche", "entrega", True),
        ("llamadas_agotadas_con_parche", "llamadas", False),
        ("tiempo_agotado_sin_parche", "tiempo", False),
        ("tiempo_agotado_sin_parche", "llamadas", True),
        ("turnos_agotados_con_parche", "tiempo", True),
        # Una clase que no nombra un tope no afirma ninguna causa
        ("resuelta", "tiempo", False),
        ("parche_no_pasa", "entrega", False),
        (None, "tiempo", False),
    ],
)
def test_la_clase_contradice_la_causa_solo_si_nombra_otro_tope(
    clase: Any, causa: str, contradice: bool
) -> None:
    assert ke.clase_contradice_la_causa(clase, causa) is contradice


def test_un_fin_por_tiempo_no_queda_como_fin_por_llamadas_en_tarea_fin(tmp_path: Path) -> None:
    """El caso del brazo de 6 minutos: cortada por tiempo a una llamada del tope de 28."""
    registro = ke.Registro(tmp_path, "s")
    registro.tarea("E1", "t_1", 1)
    _agente(registro, TIEMPO, entrego=False, llamadas=27)
    registro.fin_tarea(clase="llamadas_agotadas_con_parche", resuelta=False, error=TIEMPO)

    (fin,) = _eventos(registro, "tarea_fin")
    assert fin["causa_fin"] == "tiempo"
    assert fin["clase_contradice_causa"] is True
    # La clase del notebook no se reescribe: es la de las corridas ya medidas
    assert fin["clase"] == "llamadas_agotadas_con_parche"


def test_tarea_fin_dice_la_causa_aunque_el_arnes_descarte_el_error_al_resolver(tmp_path: Path) -> None:
    """Nueve cortes de las seis sesiones tenían `tarea_fin.error` nulo: el parche de respaldo pasó."""
    registro = ke.Registro(tmp_path, "s")
    registro.tarea("E1", "t_1", 1)
    _agente(registro, TIEMPO, entrego=False)
    registro.fin_tarea(clase="resuelta", resuelta=True, error=None)
    registro.tarea("E1", "t_2", 2)
    _agente(registro, None, entrego=True)
    registro.fin_tarea(clase="llamadas_agotadas_sin_parche", resuelta=False, error=None)

    cortada, entregada = _eventos(registro, "tarea_fin")
    assert (cortada["causa_fin"], cortada["error"], cortada["clase_contradice_causa"]) == (
        "tiempo",
        None,
        False,
    )
    # La otra mitad de la clase mal rotulada: entregó y el notebook la llamó «llamadas agotadas»
    assert (entregada["causa_fin"], entregada["clase_contradice_causa"]) == ("entrega", True)


def test_una_tarea_no_hereda_la_causa_de_la_anterior(tmp_path: Path) -> None:
    registro = ke.Registro(tmp_path, "s")
    registro.tarea("E1", "t_1", 1)
    _agente(registro, TIEMPO, entrego=False)
    registro.fin_tarea(clase="tiempo_agotado_sin_parche")
    registro.tarea("E1", "t_2", 2)
    registro.fin_tarea(clase="otro_error_sin_parche")
    registro.tarea("E1", "t_3", 3)
    registro.fin_tarea(clase=ke.CLASE_TAREA_COLGADA, resuelta=False)

    assert [e["causa_fin"] for e in _eventos(registro, "tarea_fin")] == [
        "tiempo",
        "sin_agente_fin",
        ke.CLASE_TAREA_COLGADA,
    ]


def test_si_el_agente_lanza_la_causa_es_otro_error(tmp_path: Path) -> None:
    class Evaluador:
        async def _run_agent_sandbox(self, task: Any, snapshot: Any, **kwargs: Any) -> Any:
            raise RuntimeError("se cayó")

    registro = ke.Registro(tmp_path, "s")
    registro.tarea("E1", "t_1", 1)
    registro.envolver_evaluador(Evaluador)
    with pytest.raises(RuntimeError):
        asyncio.run(Evaluador()._run_agent_sandbox("t", "s"))
    registro.fin_tarea(clase="otro_error_sin_parche")
    assert _eventos(registro, "tarea_fin")[0]["causa_fin"] == "otro_error"


def test_el_lector_y_el_registro_comparten_la_tabla_de_causas() -> None:
    """Una sola definición: el lector no tiene su propia lista de textos del arnés."""
    del_registro = tuple((texto, nombre) for texto, _causa, nombre in ke.CAUSAS_POR_TEXTO)
    assert del_registro == kr.TOPES_DE_TAREA and len(del_registro) == 5
    for texto, causa, nombre in ke.CAUSAS_POR_TEXTO:
        assert kr.tope_de_tarea(f"Agent: {texto.upper()} x") == nombre
        assert ke.causa_del_fin({"error": f"Agent: {texto.upper()} x"}) == causa


# ---------------------------------------------------------------------------
# Criterio 3: el rastro de una petición cancelada
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ('vllm:generation_tokens_total{engine="0"} 90471.0\n', 90471),
        (
            'vllm:generation_tokens_total{engine="0"} 9.0471e+04\nvllm:generation_tokens_total{e="1"} 29\n',
            90500,
        ),
        ("vllm:generation_tokens_total 7\n", 7),
        # Ni el comentario, ni la marca de creación, ni otro contador que empieza igual
        ("# TYPE vllm:generation_tokens_total counter\nvllm:generation_tokens_total_created 5\n", None),
        ('vllm:prompt_tokens_total{engine="0"} 3.3e+06\n', None),
        ("vllm:generation_tokens_total{x} no_es_un_numero\n", None),
        ("", None),
    ],
)
def test_el_contador_del_servidor_se_lee_de_sus_metricas(texto: str, esperado: int | None) -> None:
    servidor = _Contador(texto)
    try:
        assert ke.tokens_generados_del_servidor(servidor.servidor.base_url) == esperado
    finally:
        servidor.http.shutdown()
        servidor.http.server_close()


@pytest.mark.parametrize("base", [None, "", "http://127.0.0.1:9/v1", "no es una url", 7])
def test_sin_servidor_el_contador_es_none_y_no_lanza(base: Any) -> None:
    assert ke.tokens_generados_del_servidor(base, espera=0.5) is None


def test_una_peticion_cancelada_deja_cuantos_tokens_llevaba_y_cuanto_tiempo(
    tmp_path: Path, contador: _Contador
) -> None:
    contador.tokens = 1000
    registro = ke.Registro(tmp_path, "s", contador.servidor)
    registro.tarea("E1", "t_1", 1)

    async def responder(model: Any, messages: Any, tools: Any, **kwargs: Any) -> Any:
        contador.tokens += 3  # el servidor genera lo que la respuesta dice
        return _Respuesta(tokens=3)

    async def colgar(model: Any, messages: Any, tools: Any, **kwargs: Any) -> Any:
        contador.tokens += 57  # lo generado hasta el corte: no hay respuesta que lo diga
        await asyncio.sleep(30)

    class Cliente:
        comportamiento: Any = responder

        async def acompletion(self, model: Any, messages: Any, tools: Any, **kwargs: Any) -> Any:
            return await type(self).comportamiento(model, messages, tools, **kwargs)

    registro.envolver_cliente(Cliente)

    async def sesion() -> None:
        await Cliente().acompletion(model="m", messages=MENSAJES, tools=None)
        Cliente.comportamiento = colgar
        async with asyncio.timeout(0.2):  # como el tope de tiempo del arnés
            await Cliente().acompletion(model="m", messages=MENSAJES, tools=None)

    with pytest.raises(TimeoutError):
        asyncio.run(sesion())
    _agente(registro, TIEMPO, entrego=False)
    registro.fin_tarea(clase="tiempo_agotado_sin_parche", resuelta=False, error=TIEMPO)

    (inicio,) = _eventos(registro, "tarea_inicio")
    (fin,) = _eventos(registro, "tarea_fin")
    assert inicio["servidor_tokens_generados"] == 1000 and fin["servidor_tokens_generados"] == 1060
    assert (fin["tokens_generados_en_la_tarea"], fin["tokens_respondidos"], fin["tokens_sin_respuesta"]) == (
        60,
        3,
        57,
    )
    (cancelada,) = fin["canceladas"]
    assert cancelada["peticion"] == 2 and cancelada["caracteres_entrada"] == 15
    assert 0.15 <= cancelada["segundos"] < 5
    # El tiempo es el mismo que ya traía el fin de la petición
    (fin_peticion,) = [e for e in _eventos(registro, "peticion_fin") if e["motivo"] == "cancelada"]
    assert fin_peticion["segundos"] == cancelada["segundos"]
    assert registro.errores == 0


def test_la_tarea_siguiente_empieza_su_cuenta_de_cero(tmp_path: Path, contador: _Contador) -> None:
    registro = ke.Registro(tmp_path, "s", contador.servidor)
    for tarea, generados in (("t_1", 40), ("t_2", 9)):
        registro.tarea("E1", tarea, 1)
        contador.tokens += generados
        registro.fin_peticion(
            registro.inicio_peticion("m", MENSAJES, None, {}), error=asyncio.CancelledError()
        )
        registro.fin_tarea(clase="tiempo_agotado_sin_parche")

    primera, segunda = _eventos(registro, "tarea_fin")
    assert (primera["tokens_sin_respuesta"], segunda["tokens_sin_respuesta"]) == (40, 9)
    assert [c["peticion"] for c in primera["canceladas"]] == [1]
    assert [c["peticion"] for c in segunda["canceladas"]] == [2]


def test_una_peticion_con_error_no_cuenta_como_cancelada(tmp_path: Path, contador: _Contador) -> None:
    registro = ke.Registro(tmp_path, "s", contador.servidor)
    registro.tarea("E1", "t_1", 1)
    registro.fin_peticion(registro.inicio_peticion("m", MENSAJES, None, {}), error=ConnectionError("x"))
    registro.fin_tarea(clase="otro_error_sin_parche")
    (fin,) = _eventos(registro, "tarea_fin")
    assert fin["canceladas"] == [] and fin["tokens_sin_respuesta"] == 0


@pytest.mark.parametrize("servidor", [None, types.SimpleNamespace(base_url="http://127.0.0.1:9/v1")])
def test_sin_contador_los_tokens_son_none_y_el_tiempo_queda_igual(tmp_path: Path, servidor: Any) -> None:
    """Sin dato no es cero: el servidor falso del ensayo, o uno caído, no publica el contador."""
    registro = ke.Registro(tmp_path, "s", servidor)
    registro.tarea("E1", "t_1", 1)
    registro.fin_peticion(registro.inicio_peticion("m", MENSAJES, None, {}), error=asyncio.CancelledError())
    registro.fin_tarea(clase="tiempo_agotado_sin_parche")

    (fin,) = _eventos(registro, "tarea_fin")
    assert fin["tokens_sin_respuesta"] is None and fin["tokens_generados_en_la_tarea"] is None
    assert fin["tokens_respondidos"] == 0
    assert [c["peticion"] for c in fin["canceladas"]] == [1] and fin["canceladas"][0]["segundos"] >= 0
    assert registro.errores == 0


def test_el_contador_solo_se_lee_entre_tareas_y_nunca_durante_una(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Leerlo en cada petición le quitaría tiempo al agente, que corre contra un tope de minutos."""
    momentos: list[str] = []
    registro = ke.Registro(tmp_path, "s", types.SimpleNamespace(base_url="http://x/v1"))
    monkeypatch.setattr(ke, "tokens_generados_del_servidor", lambda base: momentos.append(registro.fase) or 5)
    registro.fase = "antes"  # type: ignore[attr-defined]
    registro.tarea("E1", "t_1", 1)
    registro.fase = "durante"  # type: ignore[attr-defined]
    for error in (None, asyncio.CancelledError(), ConnectionError("x")):
        numero = registro.inicio_peticion("m", MENSAJES, None, MUESTREO_DEL_KIT)
        registro.fin_peticion(numero, respuesta=None if error else _Respuesta(), error=error)
    _agente(registro, TIEMPO, entrego=False)
    registro.fase = "despues"  # type: ignore[attr-defined]
    registro.fin_tarea(clase="tiempo_agotado_sin_parche")
    assert momentos == ["antes", "despues"]


def test_un_registro_inactivo_no_lee_el_contador(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lecturas: list[Any] = []
    monkeypatch.setattr(ke, "tokens_generados_del_servidor", lambda base: lecturas.append(base))
    registro = ke.Registro(tmp_path, "s", types.SimpleNamespace(base_url="http://x/v1"), activo=False)
    registro.tarea("E1", "t_1", 1)
    registro.fin_tarea(clase="resuelta")
    assert lecturas == [] and not registro.ruta_eventos.exists()


def test_si_el_contador_falla_la_fila_de_fin_se_escribe_igual(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def romper(base: Any) -> int:
        raise OSError("sin red")

    monkeypatch.setattr(ke, "tokens_generados_del_servidor", romper)
    registro = ke.Registro(tmp_path, "s")
    registro.tarea("E1", "t_1", 1)
    _agente(registro, None, entrego=True)
    registro.fin_tarea(clase="resuelta", resuelta=True)
    (inicio,) = _eventos(registro, "tarea_inicio")
    (fin,) = _eventos(registro, "tarea_fin")
    assert inicio["servidor_tokens_generados"] is None
    assert (fin["clase"], fin["con_tope"], fin["causa_fin"]) == ("resuelta", False, "entrega")
    assert fin["tokens_sin_respuesta"] is None
    # El fallo se cuenta, como cualquier otro del registro, y no se calla
    assert registro.errores == 2 and "sin red" in str(registro.ultimo_error)


# ---------------------------------------------------------------------------
# El lector: lo mismo, leído de un registro
# ---------------------------------------------------------------------------


def _e(tipo: str, tarea: str | None = "t_1", **campos: Any) -> dict[str, Any]:
    return {"evento": tipo, "tarea": tarea, "hora_utc": "2026-10-13T00:00:00.000+00:00", **campos}


def _sesion(fin_1: dict[str, Any], muestreo: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Dos tareas: la primera cortada por tiempo a una llamada del tope; la segunda entrega."""
    m = muestreo if muestreo is not None else {**MUESTREO_ESPERADO, "presupuesto_razonamiento": 4096}
    return [
        _e("registro_instalado", None, enganches={"peticiones": "instalado"}),
        _e("tarea_inicio"),
        _e("peticion_inicio", peticion=1, pide_razonar=True, **m),
        _e("peticion_fin", peticion=1, motivo="tool_calls", segundos=1.0, completion_tokens=40),
        _e("peticion_inicio", peticion=2, pide_razonar=True, **m),
        _e("peticion_fin", peticion=2, motivo="cancelada", segundos=12.5),
        _e("agente_fin", error=TIEMPO, entrego=False, parche_caracteres=9, llamadas_herramientas=27),
        _e("diff_cierre", bytes=9, sha256="x", archivos=["a.py"]),
        _e("tarea_fin", clase="llamadas_agotadas_con_parche", error=TIEMPO, **fin_1),
        _e("tarea_inicio", "t_2"),
        _e(
            "peticion_inicio",
            "t_2",
            peticion=3,
            pide_razonar=True,
            **({**m, "temperatura": 0.0} if m else {}),
        ),
        _e("peticion_fin", "t_2", peticion=3, motivo="stop", segundos=1.0, completion_tokens=40),
        _e("agente_fin", "t_2", error=None, entrego=True, parche_caracteres=9),
        _e("diff_cierre", "t_2", bytes=9, sha256="y", archivos=["a.py"]),
        _e("tarea_fin", "t_2", clase="resuelta", error=None),
        _e("cierre", None, errores_del_registro=0, ultimo_error=None),
    ]


def test_el_diagnostico_dice_la_causa_y_donde_la_clase_la_contradice() -> None:
    cancelada = {"peticion": 2, "segundos": 12.5, "caracteres_entrada": 1000}
    nuevo = {
        "causa_fin": "tiempo",
        "clase_contradice_causa": True,
        "canceladas": [cancelada],
        "tokens_sin_respuesta": 410,
    }
    informe = kr.diagnosticar(_sesion(nuevo), [])

    assert kr.codigo_de(informe) == kr.EXIT_OK
    primera, segunda = informe["tareas"]
    assert (primera["causa_fin"], primera["clase"], primera["clase_contradice_causa"]) == (
        "tiempo",
        "llamadas_agotadas_con_parche",
        True,
    )
    assert primera["canceladas"] == [cancelada] and primera["tokens_sin_respuesta"] == 410
    assert (segunda["causa_fin"], segunda["clase_contradice_causa"]) == ("entrega", False)
    assert informe["sesion"]["causas_de_fin"] == {"tiempo": 1, "entrega": 1}
    assert informe["sesion"]["tareas_con_clase_que_contradice_la_causa"] == [
        {"orden": 1, "tarea": "t_1", "clase": "llamadas_agotadas_con_parche", "causa_fin": "tiempo"}
    ]


def test_un_registro_anterior_se_lee_con_la_misma_definicion_de_causa() -> None:
    """Las seis sesiones ya medidas no traen `causa_fin`: el lector la calcula de su `agente_fin`."""
    informe = kr.diagnosticar(_sesion({}), [])
    primera, segunda = informe["tareas"]
    assert (primera["causa_fin"], primera["clase_contradice_causa"]) == ("tiempo", True)
    assert primera["canceladas"] is None and primera["tokens_sin_respuesta"] is None
    assert segunda["causa_fin"] == "entrega"
    assert len(informe["sesion"]["tareas_con_clase_que_contradice_la_causa"]) == 1


def test_el_diagnostico_agrupa_el_muestreo_de_las_peticiones() -> None:
    informe = kr.diagnosticar(_sesion({}), [])
    base = {**MUESTREO_ESPERADO, "presupuesto_razonamiento": 4096, "pide_razonar": True}
    assert informe["muestreo"] == [{**base, "peticiones": 2}, {**base, "temperatura": 0.0, "peticiones": 1}]
    assert informe["peticiones"]["no_respondidas"][0]["temperatura"] == 0.2

    anterior = kr.diagnosticar(_sesion({}, muestreo={}), [])
    sin_dato = {campo: None for campo in MUESTREO_ESPERADO} | {"presupuesto_razonamiento": None}
    assert anterior["muestreo"] == [{**sin_dato, "pide_razonar": True, "peticiones": 3}]


def test_una_tarea_sin_fin_no_tiene_causa() -> None:
    eventos = _sesion({})[:8]
    (tarea,) = kr.diagnosticar(eventos, [])["tareas"]
    assert tarea["causa_fin"] is None and tarea["clase_contradice_causa"] is None


# ---------------------------------------------------------------------------
# Criterio 4: el registro de envíos
# ---------------------------------------------------------------------------


def test_el_registro_de_envios_refleja_las_lecturas_guardadas() -> None:
    datos = json.loads(REGISTRO_DE_ENVIOS.read_text(encoding="utf-8"))
    filas = {s["submission_id"]: s for s in datos["submissions"]}
    assert len(filas) == len(datos["submissions"]) == 19
    for fila in filas.values():
        SubmissionRecord(**fila)
    assert datos["last_updated"] == "2026-10-17"

    # El envío del 12: completo con nota, y la hora de la primera lectura que lo vio así
    leido = filas["sub-008"]
    assert (leido["status"], leido["public_score"], leido["date"]) == ("scored", 0.13, "2026-10-12")
    assert "57098570" in leido["notes"] and "2026-10-13 13:42 UTC" in leido["notes"]
    assert "2026-10-13 00:44 UTC" in leido["notes"] and "pendiente" in leido["notes"]
    assert leido["sha256"] == filas["sub-005"]["sha256"] == filas["sub-006"]["sha256"]

    # El envío del 14: enviado y pendiente, sin nota
    enviado = filas["sub-010"]
    assert (enviado["status"], enviado["public_score"], enviado["date"]) == ("submitted", None, "2026-10-14")
    assert enviado["sha256"].startswith("aa0750f0") and enviado["condition"] == "C2"
    assert "57160374" in enviado["notes"] and "2026-10-14 00:07:20 UTC" in enviado["notes"]
    assert "PENDING" in enviado["notes"] and "lectura, no mejora" in enviado["notes"]

    # El envío del 16: variante navegación, puntuado tras ~13,75 h; dentro de ruido
    nav = filas["sub-018"]
    assert (nav["status"], nav["public_score"], nav["date"]) == ("scored", 0.1, "2026-10-16")
    assert nav["sha256"].startswith("648d312c") and nav["condition"] == "NAV"
    assert "57274153" in nav["notes"] and "2026-10-16 15:30:14 UTC" in nav["notes"]
    assert "PENDING" in nav["notes"] and "submission.zip" in nav["notes"]
    assert "Score 0.10" in nav["notes"] and "RUIDO" in nav["notes"]

    # El kit v2 presupuesto-corregido: puntuado tras ~15,4 h; FUERA de ruido vs sub-018
    v2 = filas["sub-019"]
    assert (v2["status"], v2["public_score"], v2["date"]) == ("scored", 0.17, "2026-10-17")
    assert v2["sha256"].startswith("c08e5327") and v2["condition"] == "NAV-V2"
    assert "355f4954f50c" in v2["notes"] and "5.0" in v2["notes"] and "4.5" in v2["notes"]
    assert "57296502" in v2["notes"] and "0 submissions remaining" in v2["notes"]
    assert "REFUTADA" in v2["notes"]
    assert "Score 0.17" in v2["notes"] and "FUERA" in v2["notes"]
    assert "Prediccion sellada 0.10 [0.06,0.14]: FUERA" in v2["notes"]

    # Los cambios de estado quedan en los enviados: el resto de candidatos sigue sin enviar
    estados = {k: v["status"] for k, v in filas.items()}
    assert [k for k, v in estados.items() if v == "submitted"] == ["sub-010"]
    assert [k for k, v in estados.items() if v == "scored"] == [
        "sub-002",
        "sub-003",
        "sub-005",
        "sub-006",
        "sub-008",
        "sub-018",
        "sub-019",
    ]
    assert [k for k, v in estados.items() if v == "prepared"] == [
        "sub-001",
        "sub-004",
        "sub-007",
        "sub-009",
        "sub-011",
        "sub-012",
        "sub-013",
        "sub-014",
        "sub-015",
        "sub-016",
        "sub-017",
    ]
    assert {k: filas[k]["public_score"] for k in ("sub-002", "sub-003", "sub-005", "sub-006")} == {
        "sub-002": 0.06,
        "sub-003": 0.05,
        "sub-005": 0.08,
        "sub-006": 0.13,
    }
