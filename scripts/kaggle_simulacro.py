"""Simulacro sin GPU de un envío: el arnés real de punta a punta contra un modelo falso con guion.

Responde, antes de gastar un envío o cuota de GPU, dos preguntas que compilar el zip no responde:

1. ¿El envío pierde tareas por una causa mecánica? Un «modelo» que siempre hace lo correcto (aplica
   el parche de referencia y entrega) debe resolver la tarea. Si no la resuelve, el fallo es del
   envío o del arnés, no del modelo.
2. ¿Qué parámetros recibe de verdad el modelo? El simulacro captura la petición que el arnés arma
   desde ``configs/sampling.yaml``: modelo, tope de tokens, temperatura y si el razonamiento queda
   activado (``chat_template_kwargs.enable_thinking``) y con qué presupuesto.

No mide al modelo: no dice cuántas tareas resolvería Gemma. El parche de referencia se lee de
``tasks.jsonl`` en esta máquina y solo viaja al sandbox local; el reporte lleva agregados y nunca
enunciados, parches, pruebas ni texto del arnés. Es un uso del evaluador (frontera de fuga del
pre-registro, sección A): quien lo corre no redacta skills ni señuelos.

Uso:
    python -m scripts.kaggle_simulacro --envio <dir> --tasks <tasks.jsonl> --snapshots-dir <dir> \
        --resultados <dir fuera de git> --task-ids <id> [<id> ...] [--python-arnes <python con swegemma>]

Salida: 0 si todos los desenlaces son los esperados, 1 si alguno no lo es, 2 si la entrada es inválida.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import threading
import time
from collections.abc import Sequence
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "kaggle-simulacro/1"
MODOS = ("directo", "subagente", "sin_submit", "mudo")
# Qué debe ocurrir en cada modo si el envío y el arnés no pierden tareas por una causa mecánica.
ESPERADO = {"directo": True, "subagente": True, "sin_submit": True, "mudo": False}
HERRAMIENTA_ENTREGA = "submit_patch"
HERRAMIENTA_COMANDO = "run_command"
# Las nueve herramientas del arnés (página «Model Selection, Budget, and Harness Rules»). Cualquier otra
# herramienta que aparezca en una petición es un subagente declarado por el envío.
HERRAMIENTAS_ARNES = frozenset(
    {
        "run_command",
        "submit_patch",
        "get_status",
        "read_file",
        "edit_file",
        "write_file",
        "get_code_neighbors",
        "search_similar_code",
        "get_code_subgraph",
    }
)

EXIT_OK = 0
EXIT_HALLAZGO = 1
EXIT_ENTRADA = 2


class SimulacroError(ValueError):
    """Entrada inválida o entorno que no permite correr el simulacro."""


def leer_parche(tasks: Path, tarea: str) -> str:
    """Parche de referencia de ``tarea``. No sale de este proceso salvo hacia el sandbox local."""
    with open(tasks, encoding="utf-8") as fh:
        for linea in fh:
            if not linea.strip():
                continue
            obj = json.loads(linea)
            if obj.get("instance_id") == tarea:
                parche = str(obj.get("patch") or "")
                if not parche.strip():
                    raise SimulacroError(f"La tarea {tarea} no trae parche de referencia.")
                return parche if parche.endswith("\n") else parche + "\n"
    raise SimulacroError(f"La tarea {tarea} no está en {tasks.name}.")


class ModeloFalso:
    """Modelo con guion fijo. Cada instancia sirve una corrida de una tarea en un modo.

    Guion del agente principal, según el modo:

    - ``directo``: aplica el parche con ``run_command`` y llama ``submit_patch``.
    - ``subagente``: antes llama a la primera herramienta que no es del arnés (el subagente).
    - ``sin_submit``: aplica el parche y termina sin entregar; el arnés debe rescatar el diff.
    - ``mudo``: no edita ni entrega; el arnés debe dar la tarea por no resuelta.

    Una petición sin ``submit_patch`` entre sus herramientas es de un subagente y recibe texto.
    """

    def __init__(self, parche: str, modo: str) -> None:
        if modo not in MODOS:
            raise SimulacroError(f"Modo desconocido: {modo}. Válidos: {', '.join(MODOS)}.")
        self.modo = modo
        self._b64 = base64.b64encode(parche.encode("utf-8")).decode("ascii")
        self._paso = 0
        self.peticiones: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    def _guion(self, herramientas: Sequence[str]) -> list[tuple[str, dict[str, Any]]]:
        guion: list[tuple[str, dict[str, Any]]] = []
        if self.modo == "subagente":
            propias = [h for h in herramientas if h not in HERRAMIENTAS_ARNES]
            if propias:
                guion.append((propias[0], {"request": "Locate the root cause of the issue."}))
        if self.modo != "mudo":
            orden = f"cd /workspace && echo {self._b64} | base64 -d | git apply --whitespace=nowarn -"
            guion.append((HERRAMIENTA_COMANDO, {"command": orden}))
        if self.modo in ("directo", "subagente"):
            guion.append((HERRAMIENTA_ENTREGA, {}))
        return guion

    def decidir(self, cuerpo: dict[str, Any]) -> tuple[dict[str, Any], str]:
        """Mensaje del asistente y motivo de fin para una petición ``chat/completions``."""
        herramientas = [t["function"]["name"] for t in cuerpo.get("tools") or []]
        with self._lock:
            self.peticiones.append(resumir_peticion(cuerpo, herramientas))
            numero = len(self.peticiones)
            if HERRAMIENTA_ENTREGA not in herramientas:
                return {"role": "assistant", "content": "Report: root cause located."}, "stop"
            guion = self._guion(herramientas)
            paso, self._paso = self._paso, self._paso + 1
        if paso >= len(guion):
            return {"role": "assistant", "content": "Done."}, "stop"
        nombre, args = guion[paso]
        llamada = {
            "id": f"call_{numero}",
            "type": "function",
            "function": {"name": nombre, "arguments": json.dumps(args)},
        }
        return {"role": "assistant", "content": None, "tool_calls": [llamada]}, "tool_calls"


def resumir_peticion(cuerpo: dict[str, Any], herramientas: Sequence[str]) -> dict[str, Any]:
    """Lo que se conserva de una petición: parámetros de generación y conteos. Nunca los mensajes."""
    plantilla = cuerpo.get("chat_template_kwargs") or {}
    return {
        "principal": HERRAMIENTA_ENTREGA in herramientas,
        "modelo": cuerpo.get("model"),
        "max_completion_tokens": cuerpo.get("max_completion_tokens", cuerpo.get("max_tokens")),
        "temperature": cuerpo.get("temperature"),
        "top_p": cuerpo.get("top_p"),
        "enable_thinking": plantilla.get("enable_thinking"),
        "thinking_token_budget": cuerpo.get("thinking_token_budget"),
        "herramientas": len(herramientas),
        "mensajes": len(cuerpo.get("messages") or []),
    }


def _manejador(modelo: ModeloFalso) -> type[BaseHTTPRequestHandler]:
    class Manejador(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:  # silencio: el log trae rutas
            return

        def _json(self, obj: dict[str, Any]) -> None:
            datos = json.dumps(obj).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(datos)))
            self.end_headers()
            self.wfile.write(datos)

        def do_GET(self) -> None:
            self._json({"object": "list", "data": [{"id": "modelo-falso", "object": "model"}]})

        def do_POST(self) -> None:
            largo = int(self.headers.get("Content-Length", 0))
            cuerpo = json.loads(self.rfile.read(largo) or b"{}")
            mensaje, fin = modelo.decidir(cuerpo)
            base = {"id": "chatcmpl-simulacro", "created": int(time.time()), "model": cuerpo.get("model", "")}
            uso = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            if not cuerpo.get("stream"):
                eleccion = {"index": 0, "message": mensaje, "finish_reason": fin}
                self._json({**base, "object": "chat.completion", "choices": [eleccion], "usage": uso})
                return
            delta = dict(mensaje)
            if "tool_calls" in delta:
                delta["tool_calls"] = [dict(tc, index=i) for i, tc in enumerate(delta["tool_calls"])]
            trozos = [
                {"choices": [{"index": 0, "delta": delta, "finish_reason": None}]},
                {"choices": [{"index": 0, "delta": {}, "finish_reason": fin}], "usage": uso},
            ]
            texto = "".join(
                f"data: {json.dumps({**base, 'object': 'chat.completion.chunk', **t})}\n\n" for t in trozos
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            self.wfile.write((texto + "data: [DONE]\n\n").encode("utf-8"))

    return Manejador


def servir(modelo: ModeloFalso) -> tuple[ThreadingHTTPServer, str]:
    """Arranca el modelo falso en un puerto libre de ``127.0.0.1``. Devuelve el servidor y su URL base."""
    servidor = ThreadingHTTPServer(("127.0.0.1", 0), _manejador(modelo))
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    return servidor, f"http://127.0.0.1:{servidor.server_address[1]}/v1"


def parametros_modelo(peticiones: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Parámetros de generación de la primera petición del agente principal y del subagente."""
    claves = (
        "modelo",
        "max_completion_tokens",
        "temperature",
        "top_p",
        "enable_thinking",
        "thinking_token_budget",
    )
    salida: dict[str, Any] = {}
    for nombre, principal in (("agente_principal", True), ("subagente", False)):
        primera = next((p for p in peticiones if p["principal"] is principal), None)
        salida[nombre] = None if primera is None else {k: primera[k] for k in claves}
    return salida


def leer_resultado(resultados: Path, tarea: str) -> dict[str, Any] | None:
    """Fila de ``task_results.jsonl`` de ``tarea``, o ``None`` si el arnés no la escribió."""
    archivo = resultados / "task_results.jsonl"
    if not archivo.exists():
        return None
    for linea in archivo.read_text(encoding="utf-8").splitlines():
        if linea.strip():
            fila = json.loads(linea)
            if fila.get("instance_id") == tarea:
                return dict(fila)
    return None


def evaluar(modo: str, fila: dict[str, Any] | None) -> dict[str, Any]:
    """Compara el desenlace con el esperado. El texto del error del arnés no se conserva."""
    if fila is None:
        return {
            "modo": modo,
            "esperado": ESPERADO[modo],
            "resuelta": None,
            "coincide": False,
            "motivo": "sin_fila",
        }
    resuelta = bool(fila.get("resolved"))
    return {
        "modo": modo,
        "esperado": ESPERADO[modo],
        "resuelta": resuelta,
        "parche_no_vacio": int(fila.get("agent_patch_size") or 0) > 0,
        "llamadas_modelo": fila.get("total_llm_calls"),
        "llamadas_herramientas": fila.get("tool_calls"),
        "hubo_error_arnes": fila.get("error") is not None,
        "segundos": fila.get("duration_seconds"),
        "coincide": resuelta is ESPERADO[modo],
    }


def comprobar_arnes(python_arnes: str) -> str:
    """Versión de ``swegemma`` del intérprete dado; ``SimulacroError`` si no está instalado."""
    codigo = "import importlib.metadata as m;print(m.version('swegemma'))"
    try:
        salida = subprocess.run([python_arnes, "-c", codigo], capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SimulacroError(f"No se pudo ejecutar {python_arnes}: {type(exc).__name__}.") from None
    if salida.returncode != 0:
        raise SimulacroError(
            "El paquete 'swegemma' no está instalado en ese intérprete: pase --python-arnes con el del arnés."
        )
    return salida.stdout.strip()


def comprobar_resultados_fuera_de_git(resultados: Path) -> None:
    """Los resultados crudos del arnés traen salidas de pruebas: no pueden quedar versionables."""
    padre = resultados if resultados.exists() else resultados.parent
    try:
        dentro = subprocess.run(
            ["git", "-C", str(padre), "rev-parse", "--is-inside-work-tree"], capture_output=True, text=True
        )
    except OSError:
        return
    if dentro.returncode != 0:
        return
    ignorado = subprocess.run(["git", "-C", str(padre), "check-ignore", "-q", str(resultados)])
    if ignorado.returncode != 0:
        raise SimulacroError("--resultados está dentro de un repositorio git y no está ignorado.")


def correr_tarea(
    args: argparse.Namespace, tarea: str, modo: str
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Una corrida del arnés real sobre ``tarea`` contra el modelo falso en ``modo``."""
    modelo = ModeloFalso(leer_parche(args.tasks, tarea), modo)
    servidor, url = servir(modelo)
    destino = args.resultados / f"{tarea}__{modo}"
    entorno = {
        **os.environ,
        "LOCAL_INFERENCE_URL": url,
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "OTEL_SDK_DISABLED": "true",
        "LITELLM_LOCAL_MODEL_COST_MAP": "True",
    }
    for clave in ("MODEL_PROXY_URL", "LITELLM_API_BASE", "OPENAI_BASE_URL"):
        entorno.pop(clave, None)  # tienen prioridad sobre LOCAL_INFERENCE_URL en el arnés
    orden = [
        args.python_arnes,
        "-m",
        "swegemma.cli",
        "eval",
        "--tasks",
        str(args.tasks),
        "--snapshots-dir",
        str(args.snapshots_dir),
        "--results-dir",
        str(destino),
        "--submission-dir",
        str(args.envio),
        "--sandbox",
        args.sandbox,
        "--task-ids",
        tarea,
        "--concurrency",
        "1",
        "--display",
        "quiet",
    ]
    if args.imagen:
        orden += ["--image", args.imagen]
    try:
        with open(args.resultados / f"{tarea}__{modo}.log", "w", encoding="utf-8") as registro:
            subprocess.run(orden, env=entorno, stdout=registro, stderr=subprocess.STDOUT, timeout=args.tope)
    except subprocess.TimeoutExpired:
        pass
    finally:
        servidor.shutdown()
        servidor.server_close()
    return evaluar(modo, leer_resultado(destino, tarea)), modelo.peticiones


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m scripts.kaggle_simulacro", description=__doc__.split("\n")[0])
    p.add_argument(
        "--envio", type=Path, required=True, help="Directorio del envío (con agent.yaml en la raíz)"
    )
    p.add_argument("--tasks", type=Path, required=True, help="tasks.jsonl de la competencia (no versionado)")
    p.add_argument("--snapshots-dir", type=Path, required=True)
    p.add_argument("--resultados", type=Path, required=True, help="Directorio crudo, fuera de git o ignorado")
    p.add_argument("--task-ids", nargs="+", required=True)
    p.add_argument("--modos", nargs="+", default=list(MODOS), choices=MODOS)
    p.add_argument("--sandbox", default="docker", choices=("docker", "subprocess"))
    p.add_argument("--imagen", default=None, help="Imagen del sandbox Docker")
    p.add_argument("--python-arnes", default=sys.executable, help="Intérprete que tiene swegemma instalado")
    p.add_argument("--tope", type=int, default=900, help="Segundos máximos por corrida del arnés")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if not (args.envio / "agent.yaml").is_file():
            raise SimulacroError("--envio no es un directorio de envío: falta agent.yaml en su raíz.")
        if not args.tasks.is_file():
            raise SimulacroError("--tasks no existe.")
        if not args.snapshots_dir.is_dir():
            raise SimulacroError("--snapshots-dir no existe.")
        for tarea in args.task_ids:
            leer_parche(args.tasks, tarea)
        comprobar_resultados_fuera_de_git(args.resultados)
        version = comprobar_arnes(args.python_arnes)
    except SimulacroError as exc:
        print(f"ENTRADA INVÁLIDA: {exc}", file=sys.stderr)
        return EXIT_ENTRADA
    args.resultados.mkdir(parents=True, exist_ok=True)
    corridas: list[dict[str, Any]] = []
    peticiones: list[dict[str, Any]] = []
    for tarea in args.task_ids:
        for modo in args.modos:
            desenlace, vistas = correr_tarea(args, tarea, modo)
            corridas.append({"tarea": tarea, **desenlace})
            peticiones.extend(vistas)
    reporte = {
        "schema_version": SCHEMA_VERSION,
        "swegemma": version,
        "sandbox": args.sandbox,
        "parametros_modelo": parametros_modelo(peticiones),
        "corridas": corridas,
        "todas_coinciden": all(c["coincide"] for c in corridas),
    }
    print(json.dumps(reporte, ensure_ascii=False, indent=2))
    return EXIT_OK if reporte["todas_coinciden"] else EXIT_HALLAZGO


if __name__ == "__main__":
    raise SystemExit(main())
