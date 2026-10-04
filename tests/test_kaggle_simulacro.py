"""Tests del simulacro sin GPU (`scripts/kaggle_simulacro.py`). No necesitan el arnés ni Docker."""

from __future__ import annotations

import base64
import json
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from scripts import kaggle_simulacro as ks

PARCHE = "--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-a\n+b\n"
ARNES = [{"type": "function", "function": {"name": n}} for n in sorted(ks.HERRAMIENTAS_ARNES)]
SUB = {"type": "function", "function": {"name": "mi_subagente"}}


def _tasks(tmp_path: Path, parche: str = PARCHE) -> Path:
    ruta = tmp_path / "tasks.jsonl"
    filas = [{"instance_id": "t_1", "patch": parche}, {"instance_id": "t_2", "patch": ""}]
    ruta.write_text("\n".join(json.dumps(f) for f in filas) + "\n", encoding="utf-8")
    return ruta


def _nombres(modelo: ks.ModeloFalso, herramientas: list[dict[str, Any]], n: int) -> list[str]:
    salida = []
    for _ in range(n):
        mensaje, fin = modelo.decidir({"model": "m", "tools": herramientas, "messages": []})
        llamadas = mensaje.get("tool_calls")
        salida.append(llamadas[0]["function"]["name"] if llamadas else f"texto:{fin}")
    return salida


def test_leer_parche_devuelve_el_parche_con_salto_final(tmp_path: Path) -> None:
    assert ks.leer_parche(_tasks(tmp_path, PARCHE.rstrip("\n")), "t_1") == PARCHE


@pytest.mark.parametrize("tarea", ["t_2", "no_existe"])
def test_leer_parche_rechaza_tarea_sin_parche_o_ausente(tmp_path: Path, tarea: str) -> None:
    with pytest.raises(ks.SimulacroError):
        ks.leer_parche(_tasks(tmp_path), tarea)


@pytest.mark.parametrize(
    ("modo", "esperado"),
    [
        ("directo", ["run_command", "submit_patch", "texto:stop"]),
        ("subagente", ["mi_subagente", "run_command", "submit_patch", "texto:stop"]),
        ("sin_submit", ["run_command", "texto:stop", "texto:stop"]),
        ("mudo", ["texto:stop", "texto:stop"]),
    ],
)
def test_el_guion_de_cada_modo(modo: str, esperado: list[str]) -> None:
    modelo = ks.ModeloFalso(PARCHE, modo)
    assert _nombres(modelo, [*ARNES, SUB], len(esperado)) == esperado


def test_modo_desconocido_se_rechaza() -> None:
    with pytest.raises(ks.SimulacroError):
        ks.ModeloFalso(PARCHE, "otro")


def test_modo_subagente_sin_subagente_declarado_no_inventa_una_herramienta() -> None:
    assert _nombres(ks.ModeloFalso(PARCHE, "subagente"), ARNES, 2) == ["run_command", "submit_patch"]


def test_la_peticion_de_un_subagente_recibe_texto_y_no_avanza_el_guion() -> None:
    modelo = ks.ModeloFalso(PARCHE, "directo")
    solo_lectura = [t for t in ARNES if t["function"]["name"] == "read_file"]
    assert _nombres(modelo, solo_lectura, 2) == ["texto:stop", "texto:stop"]
    assert _nombres(modelo, ARNES, 1) == ["run_command"]


def test_el_comando_aplica_exactamente_el_parche_de_referencia() -> None:
    mensaje, _ = ks.ModeloFalso(PARCHE, "directo").decidir({"tools": ARNES})
    orden = json.loads(mensaje["tool_calls"][0]["function"]["arguments"])["command"]
    codificado = orden.split("echo ")[1].split(" |")[0]
    assert base64.b64decode(codificado).decode("utf-8") == PARCHE
    assert "git apply" in orden


def test_resumir_peticion_conserva_parametros_y_no_los_mensajes() -> None:
    cuerpo = {
        "model": "gemma",
        "max_completion_tokens": 8192,
        "temperature": 0.2,
        "top_p": 0.95,
        "chat_template_kwargs": {"enable_thinking": False},
        "messages": [{"role": "user", "content": "ENUNCIADO SECRETO"}],
    }
    resumen = ks.resumir_peticion(cuerpo, ["submit_patch", "read_file"])
    assert resumen["enable_thinking"] is False
    assert resumen["thinking_token_budget"] is None
    assert resumen["max_completion_tokens"] == 8192
    assert resumen["principal"] is True
    assert resumen["mensajes"] == 1
    assert "ENUNCIADO SECRETO" not in json.dumps(resumen)


def test_parametros_modelo_separa_agente_principal_y_subagente() -> None:
    peticiones = [
        ks.resumir_peticion({"model": "a", "thinking_token_budget": 4096}, ["submit_patch"]),
        ks.resumir_peticion({"model": "b"}, ["read_file"]),
        ks.resumir_peticion({"model": "c"}, ["submit_patch"]),
    ]
    vista = ks.parametros_modelo(peticiones)
    assert vista["agente_principal"]["modelo"] == "a"
    assert vista["agente_principal"]["thinking_token_budget"] == 4096
    assert vista["subagente"]["modelo"] == "b"
    assert ks.parametros_modelo([])["subagente"] is None


@pytest.mark.parametrize(
    ("modo", "resuelta", "coincide"),
    [("directo", True, True), ("directo", False, False), ("mudo", False, True), ("mudo", True, False)],
)
def test_evaluar_compara_con_lo_esperado(modo: str, resuelta: bool, coincide: bool) -> None:
    fila = {"resolved": resuelta, "agent_patch_size": 10, "error": "TEXTO DEL ARNES", "total_llm_calls": 3}
    desenlace = ks.evaluar(modo, fila)
    assert desenlace["coincide"] is coincide
    assert desenlace["hubo_error_arnes"] is True
    assert "TEXTO DEL ARNES" not in json.dumps(desenlace)


def test_evaluar_sin_fila_no_coincide() -> None:
    assert ks.evaluar("directo", None)["coincide"] is False


def test_leer_resultado(tmp_path: Path) -> None:
    assert ks.leer_resultado(tmp_path, "t_1") is None
    filas = [{"instance_id": "t_9"}, {"instance_id": "t_1", "resolved": True}]
    (tmp_path / "task_results.jsonl").write_text(
        "\n".join(json.dumps(f) for f in filas) + "\n", encoding="utf-8"
    )
    assert ks.leer_resultado(tmp_path, "t_1") == {"instance_id": "t_1", "resolved": True}
    assert ks.leer_resultado(tmp_path, "t_2") is None


def _post(url: str, cuerpo: dict[str, Any]) -> bytes:
    peticion = urllib.request.Request(
        url + "/chat/completions",
        data=json.dumps(cuerpo).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(peticion, timeout=10) as resp:
        return bytes(resp.read())


def test_servidor_responde_en_formato_openai_con_y_sin_stream() -> None:
    modelo = ks.ModeloFalso(PARCHE, "directo")
    servidor, url = ks.servir(modelo)
    try:
        with urllib.request.urlopen(url + "/models", timeout=10) as resp:
            assert json.loads(resp.read())["object"] == "list"
        primera = json.loads(_post(url, {"model": "m", "tools": ARNES, "messages": []}))
        eleccion = primera["choices"][0]
        assert eleccion["finish_reason"] == "tool_calls"
        assert eleccion["message"]["tool_calls"][0]["function"]["name"] == "run_command"
        flujo = _post(url, {"model": "m", "tools": ARNES, "messages": [], "stream": True}).decode()
        trozos = [json.loads(x[6:]) for x in flujo.split("\n\n") if x.startswith("data: {")]
        assert trozos[0]["choices"][0]["delta"]["tool_calls"][0]["function"]["name"] == "submit_patch"
        assert trozos[0]["choices"][0]["delta"]["tool_calls"][0]["index"] == 0
        assert trozos[-1]["choices"][0]["finish_reason"] == "tool_calls"
        assert flujo.rstrip().endswith("data: [DONE]")
        assert len(modelo.peticiones) == 2
    finally:
        servidor.shutdown()
        servidor.server_close()


def _args(tmp_path: Path, envio: Path, tarea: str) -> list[str]:
    return [
        "--envio",
        str(envio),
        "--tasks",
        str(_tasks(tmp_path)),
        "--snapshots-dir",
        str(tmp_path),
        "--resultados",
        str(tmp_path / "crudo"),
        "--task-ids",
        tarea,
    ]


def test_cli_rechaza_un_envio_sin_agent_yaml(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert ks.main(_args(tmp_path, tmp_path, "t_1")) == ks.EXIT_ENTRADA
    assert "agent.yaml" in capsys.readouterr().err


def test_cli_rechaza_una_tarea_sin_parche(tmp_path: Path) -> None:
    (tmp_path / "agent.yaml").write_text("name: x\n", encoding="utf-8")
    assert ks.main(_args(tmp_path, tmp_path, "t_2")) == ks.EXIT_ENTRADA
