"""Pruebas de scripts/kaggle_ensayo.py con dobles: ni servidores, ni Docker, ni GPU, ni red.

Todo es sintetico e inventado. Los textos «envenenados» simulan lo que traeria un log, un cuerpo de
error, un ``tasks.jsonl`` o un resultado del arnes, y sirven para comprobar que no llegan a los dos
archivos versionables (el registro de la compuerta y el informe de sondas).
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import math
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from scripts import kaggle_ensayo as ke
from scripts import kaggle_prereg, kaggle_replicas

AHORA = datetime(2026, 10, 6, 23, 30, 0, tzinfo=UTC)
POISON_LOG = "LINEA_DE_LOG_PRIVADA_QWERTY"
POISON_ERROR = "texto-del-error-que-no-debe-guardarse-777"
POISON_PARCHE = "PARCHE_DORADO_SECRETO_42"
POISON_PRUEBA = "test_secreto_nombre_de_prueba_xyz"
POISON_ENUNCIADO = "ENUNCIADO_PRIVADO_ASDF"
POISON_RESPUESTA = "RESPUESTA_DEL_MODELO_ZXCV"
POISON_TODOS = (POISON_LOG, POISON_ERROR, POISON_PARCHE, POISON_PRUEBA, POISON_ENUNCIADO, POISON_RESPUESTA)
RECHAZO_400 = (
    "This model's maximum context length is 32768 tokens. However, you requested 16384 output tokens "
    f"and your prompt contains at least 16385 input tokens. {POISON_ERROR}"
)
IDS_REQUESTS = ("requests_0900", "requests_1000", "requests_2000", "requests_3000")
ID_HTTPX = "httpx_0001"
ELEGIDAS = ["requests_0900", "requests_1000", "requests_2000", ID_HTTPX]
RUTA_REGISTRO = "experiments/gemma_developer_agent/preregistro/ensayo_notebook_v1.json"


# ---------------------------------------------------------------------------
# Dobles
# ---------------------------------------------------------------------------


class ProcesoFalso:
    """Proceso de mentira: anota lo que se le pide y muere solo si esta configurado para obedecer."""

    def __init__(
        self,
        pid: int = 4242,
        *,
        obedece_terminar: bool = True,
        obedece_matar: bool = True,
        muere_tras: int | None = None,
        vivo_lanza: bool = False,
        hijos: bool = True,
    ) -> None:
        self.pid = pid
        self.esta_vivo = True
        self.hijos_vivos = hijos  # el resto del grupo: solo muere con ``matar``
        self.eventos: list[str] = []
        self.consultas = 0
        self.obedece_terminar = obedece_terminar
        self.obedece_matar = obedece_matar
        self.muere_tras = muere_tras
        self.vivo_lanza = vivo_lanza

    def vivo(self) -> bool:
        if self.vivo_lanza:
            raise RuntimeError(POISON_LOG)
        self.consultas += 1
        if self.muere_tras is not None and self.consultas > self.muere_tras:
            self.esta_vivo = False
        return self.esta_vivo

    def terminar(self) -> None:
        self.eventos.append("terminar")
        if self.obedece_terminar:
            self.esta_vivo = False

    def matar(self) -> None:
        self.eventos.append("matar")
        if self.obedece_matar:
            self.esta_vivo = False
            self.hijos_vivos = False

    def esperar(self, segundos: float) -> bool:
        self.eventos.append(f"esperar:{segundos:g}")
        return not self.esta_vivo and not self.hijos_vivos

    def grupo_vivo(self) -> bool:
        return self.hijos_vivos


class Doble:
    """Sistema de mentira. Cada pieza se puede cambiar por prueba; por defecto todo sale bien."""

    def __init__(self) -> None:
        self.t = 100.0
        self.comandos: list[list[str]] = []
        self.variables_de: dict[str, dict[str, str] | None] = {}
        self.peticiones: list[tuple[str, str, bytes | None]] = []
        self.procesos: list[ProcesoFalso] = []
        self.lanzados: list[tuple[list[str], Path, dict[str, str]]] = []
        self.proceso = ProcesoFalso()
        self.lanzar_falla = False
        self.salud_tras = 3  # la tercera consulta de /health responde 200
        self.consultas_salud = 0
        self.latencia = 10.0
        self.tokens_generados = 500
        self.rechazos_agente: dict[int, int] = {16384: 0, 8192: 0}
        self.turnos: dict[int, list[int]] = {16384: [7, 3, 12, 9], 8192: [6, 6, 6, 6]}
        self.error_extra: dict[int, str | None] = {16384: None, 8192: None}
        self.paquetes: dict[str, str | None] = {
            "vllm": "0.19.1",
            "swegemma": "0.2.7",
            "adk-submission": "0.2.12",
            "adk-eval-core": "0.1.0",
            "google-adk": "1.36.1",
            "docker": None,
        }
        self.meminfo: str | None = f"MemTotal:       32000000 kB\nMemFree: 1 kB\n{POISON_LOG}\n"
        self.disco: int | None = 50 * 1024 * 1024 * 1024
        self.n_cpus: int | None = 8
        self.manejadores: dict[str, Callable[[list[str]], ke.Salida]] = {}
        self.http_manejador: Callable[[str, str, bytes | None], ke.Respuesta | None] | None = None
        self.ahora_falla = False
        self.tokens_vistos: list[int] = []
        self.esperas: list[tuple[str, float]] = []
        self.esperas_http: list[tuple[str, float]] = []
        self.puerto_ocupado: ke.Respuesta | None = None  # lo que contesta /health antes de lanzar nada
        self.tokens_por_palabra = 2
        self.sobrecarga = 20
        self.log_peticiones = True  # el servidor anota cada peticion de chat en su registro
        self.log_400_por_rechazo = 1
        self.log_400_extra = 0

    # -- reloj: solo avanza al dormir y con la latencia de cada peticion al modelo
    def reloj(self) -> float:
        return self.t

    def dormir(self, segundos: float) -> None:
        self.t += segundos

    def ahora(self) -> datetime:
        if self.ahora_falla:
            raise RuntimeError(POISON_LOG)
        return AHORA

    # -- comandos
    @staticmethod
    def tipo(argv: Sequence[str]) -> str:
        if argv[0] == "nvidia-smi":
            return "nvidia_apps" if any("compute-apps" in a for a in argv) else "nvidia_gpu"
        if argv[0] == "docker":
            return {"--version": "docker_version", "info": "docker_info", "image": "docker_imagen"}.get(
                argv[1], "docker_run"
            )
        if argv[0] == "git":
            return "git"
        if "-c" in argv:
            return "compila"
        if "swegemma.cli" in argv:
            return "agente"
        raise AssertionError(f"comando inesperado: {argv[:3]}")

    def ejecutar(self, argv: Sequence[str], espera: float, variables: Any) -> ke.Salida:
        lista = list(argv)
        tipo = self.tipo(lista)
        self.comandos.append(lista)
        self.variables_de[tipo] = dict(variables) if variables is not None else None
        self.esperas.append((tipo, espera))
        assert espera > 0
        if tipo in self.manejadores:
            return self.manejadores[tipo](lista)
        return getattr(self, f"_{tipo}")(lista)

    @staticmethod
    def ok(stdout: str = "", codigo: int = 0) -> ke.Salida:
        return ke.Salida("ok", codigo, stdout, f"aviso {POISON_LOG}")

    def _nvidia_gpu(self, argv: list[str]) -> ke.Salida:
        return self.ok("NVIDIA L4, 23034\nNVIDIA L4, 23034\nNVIDIA L4, 23034\nNVIDIA L4, 23034\n")

    def _nvidia_apps(self, argv: list[str]) -> ke.Salida:
        return self.ok("")

    def _docker_version(self, argv: list[str]) -> ke.Salida:
        return ke.Salida("ausente", None, "", "")

    def _docker_info(self, argv: list[str]) -> ke.Salida:
        return self.ok("27.0.1\n")

    def _docker_imagen(self, argv: list[str]) -> ke.Salida:
        return self.ok("sha256:abc\n")

    def _docker_run(self, argv: list[str]) -> ke.Salida:
        return self.ok("")

    def _git(self, argv: list[str]) -> ke.Salida:
        return ke.Salida("ok", 0, "", "")

    def _compila(self, argv: list[str]) -> ke.Salida:
        return self.ok(f"compilado {POISON_LOG}")

    def filas(self, ids: Sequence[str], tokens: int) -> list[dict[str, Any]]:
        filas: list[dict[str, Any]] = []
        for i, (iid, turnos) in enumerate(zip(ids, self.turnos[tokens], strict=True)):
            error: str | None = f"Agent exceeded session timeout (5.0 min) {POISON_ERROR}" if i == 0 else None
            if i < self.rechazos_agente[tokens]:
                error = f"Sandbox execution error: litellm.ContextWindowExceededError {RECHAZO_400}"
            if i == 3 and self.error_extra[tokens] is not None:
                error = self.error_extra[tokens]
            filas.append(
                {
                    "instance_id": iid,
                    "repo": "psf/requests",
                    "resolved": POISON_RESPUESTA,
                    "agent_patch_size": 123,
                    "test_exit_code": 1,
                    "duration_seconds": 301.5,
                    "error": error,
                    "tool_calls": 4,
                    "total_llm_calls": turnos,
                }
            )
        return filas

    def _agente(self, argv: list[str]) -> ke.Salida:
        resultados = Path(argv[argv.index("--results-dir") + 1])
        envio = Path(argv[argv.index("--submission-dir") + 1])
        inicio = argv.index("--task-ids") + 1
        ids = argv[inicio : argv.index("--concurrency")]
        muestreo = (envio / ke.ARCHIVO_MUESTREO).read_text(encoding="utf-8")
        tokens = 16384 if "max_output_tokens: 16384" in muestreo else 8192
        self.tokens_vistos.append(tokens)
        resultados.mkdir(parents=True)
        lineas = [json.dumps(f) for f in self.filas(ids, tokens)]
        (resultados / "task_results.jsonl").write_text("\n".join(lineas) + "\n", encoding="utf-8")
        # lo que el servidor anotaria en su registro de accesos durante la corrida
        acceso = 'INFO:     127.0.0.1:50000 - "POST /v1/chat/completions HTTP/1.1" '
        anotado: list[str] = []
        if self.log_peticiones:
            anotado += [f"{acceso}200 OK"] * sum(self.turnos[tokens])
            anotado += [f"{acceso}400 Bad Request"] * (
                self.rechazos_agente[tokens] * self.log_400_por_rechazo
            )
        anotado += [f"{acceso}400 Bad Request"] * self.log_400_extra
        with (resultados.parent / ke.REGISTRO_SERVIDOR).open("a", encoding="utf-8") as f:
            f.write("".join(f"{linea}\n{POISON_LOG}\n" for linea in anotado))
        return self.ok(f"Evaluation complete {POISON_LOG}")

    # -- procesos
    def lanzar(self, argv: Sequence[str], registro: Path, variables: Any) -> ke.Proceso:
        if self.lanzar_falla:
            raise OSError(POISON_LOG)
        registro.write_text(f"vllm arrancando\n{POISON_LOG}\n", encoding="utf-8")
        self.lanzados.append((list(argv), registro, dict(variables)))
        self.procesos.append(self.proceso)
        return self.proceso

    # -- HTTP
    def http(self, metodo: str, url: str, cuerpo: bytes | None, espera: float) -> ke.Respuesta:
        assert url.startswith("http://127.0.0.1:")
        self.peticiones.append((metodo, url, cuerpo))
        self.esperas_http.append((url.rsplit("/", 1)[-1], espera))
        assert espera > 0
        if url.endswith("/health") and not self.lanzados:
            # antes de lanzar nada: el puerto esta libre salvo que la prueba diga otra cosa
            return self.puerto_ocupado or ke.Respuesta("sin_conexion", None, b"")
        if self.http_manejador is not None:
            r = self.http_manejador(metodo, url, cuerpo)
            if r is not None:
                return r
        if url.endswith("/health"):
            self.consultas_salud += 1
            return ke.Respuesta("ok", 200 if self.consultas_salud >= self.salud_tras else 503, b"")
        if url.endswith("/v1/models"):
            datos = [{"id": ke.MODELO}, {"id": "main_lora"}, {"id": "tool_lora", "nota": POISON_LOG}]
            return ke.Respuesta("ok", 200, json.dumps({"data": datos}).encode())
        assert metodo == "POST" and cuerpo is not None
        peticion = json.loads(cuerpo)
        contenido = peticion["messages"][0]["content"]
        # un servidor de mentira que cuenta tokens: tantos por palabra de relleno mas la plantilla
        en_prompt = self.sobrecarga + self.tokens_por_palabra * contenido.count(ke.PALABRA_RELLENO.strip())
        if en_prompt + peticion["max_tokens"] > ke.CONTEXTO_MAXIMO:
            error = {"error": {"message": RECHAZO_400, "type": "BadRequestError", "code": 400}}
            return ke.Respuesta("ok", 400, json.dumps(error).encode())
        self.t += self.latencia
        respuesta = {
            "choices": [{"message": {"content": POISON_RESPUESTA}}],
            "usage": {"prompt_tokens": en_prompt, "completion_tokens": self.tokens_generados},
        }
        return ke.Respuesta("ok", 200, json.dumps(respuesta).encode())

    def entorno(self) -> ke.Entorno:
        return ke.Entorno(
            ejecutar=self.ejecutar,
            lanzar=self.lanzar,
            http=self.http,
            reloj=self.reloj,
            dormir=self.dormir,
            ahora=self.ahora,
            version_paquete=lambda p: self.paquetes[p],
            leer_texto=lambda ruta: self.meminfo if ruta == "/proc/meminfo" else None,
            disco_libre=lambda ruta: self.disco,
            cpus=lambda: self.n_cpus,
            variables={"PATH": "/usr/bin", "MODEL_PROXY_URL": "https://proxy.invalid/models"},
            python="/usr/bin/python3",
            version_python="3.12.3",
        )


MUESTREO = "temperature: 0.2\ntop_p: 0.95\nmax_output_tokens: 16384\n"


class Escenario:
    """Directorios sinteticos de un notebook y los argumentos de la CLI que los usan."""

    def __init__(self, tmp_path: Path) -> None:
        self.raiz = tmp_path
        self.modelo = tmp_path / "kaggle" / "input" / "models" / "gemma" / "2"
        self.modelo.mkdir(parents=True)
        self.envio = tmp_path / "kaggle" / "input" / "competencia" / "sample_submission"
        archivos = {
            "agent.yaml": "name: agente_inventado\n",
            ke.ARCHIVO_MUESTREO: MUESTREO,
            "adapters/main_lora/adapter_config.json": "{}",
            "adapters/main_lora/adapter_model.safetensors": "pesos inventados",
            "adapters/tool_lora/adapter_config.json": "{}",
        }
        for rel, texto in archivos.items():
            ruta = self.envio / rel
            ruta.parent.mkdir(parents=True, exist_ok=True)
            ruta.write_bytes(texto.encode())
        self.manifiesto = tmp_path / "manifest.json"
        self.manifiesto.write_text(
            json.dumps(
                {
                    "files": [
                        {"path": rel, "sha256": hashlib.sha256(texto.encode()).hexdigest()}
                        for rel, texto in archivos.items()
                    ]
                }
            ),
            encoding="utf-8",
        )
        self.tasks = tmp_path / "kaggle" / "input" / "competencia" / "tasks.jsonl"
        tareas = [(iid, "psf/requests") for iid in reversed(IDS_REQUESTS)]
        tareas += [
            (ID_HTTPX, "encode/httpx"),
            ("fastapi_0001", "fastapi/fastapi"),
            ("rich_0001", "Textualize/rich"),
        ]
        self.escribir_tareas(tareas)
        self.snapshots = tmp_path / "kaggle" / "input" / "competencia" / "snapshots"
        self.snapshots.mkdir()
        self.trabajo = tmp_path / "kaggle" / "working"
        self.trabajo.mkdir(parents=True)
        self.crudo = self.trabajo / "ensayo_crudo"
        self.salida = self.trabajo / "ensayo_notebook_v1.json"
        self.informe = self.trabajo / "ensayo_notebook_v1.sondas.json"

    def escribir_tareas(self, tareas: Sequence[tuple[str, str]]) -> None:
        lineas = [
            json.dumps(
                {
                    "instance_id": iid,
                    "repo": repo,
                    "base_commit": "0" * 40,
                    "problem_statement": POISON_ENUNCIADO,
                    "hints_text": "",
                    "patch": f"+    return {POISON_PARCHE}",
                    "test_patch": f"+def {POISON_PRUEBA}(): ...",
                    "created_at": "2026-01-01T00:00:00Z",
                }
            )
            for iid, repo in tareas
        ]
        self.tasks.write_text("\n".join(lineas) + "\n", encoding="utf-8")

    def args(self, *extra: str, sin: Sequence[str] = ()) -> list[str]:
        base: dict[str, str] = {
            "--modelo": str(self.modelo),
            "--envio": str(self.envio),
            "--manifiesto": str(self.manifiesto),
            "--tasks": str(self.tasks),
            "--snapshots-dir": str(self.snapshots),
            "--notebook": "cherrera0001/ensayo-a0 v1",
            "--sesion-max-horas": "12",
            "--sesion-fuente": "documentacion de Kaggle leida el 2026-10-06",
            "--crudo": str(self.crudo),
            "--salida": str(self.salida),
            "--informe": str(self.informe),
        }
        out: list[str] = []
        for k, v in base.items():
            if k not in sin:
                out.extend([k, v])
        return [*out, *extra]

    def versionables(self) -> str:
        """Texto de los archivos versionables que existan."""
        return "".join(p.read_text(encoding="utf-8") for p in (self.salida, self.informe) if p.exists())

    def crudos(self) -> str:
        return "".join(
            p.read_text(encoding="utf-8", errors="replace")
            for p in sorted(self.crudo.rglob("*"))
            if p.is_file()
        )

    def sondas(self) -> dict[str, dict[str, Any]]:
        informe = json.loads(self.informe.read_text(encoding="utf-8"))
        return {s["sonda"]: s for s in informe["sondas"]}


@pytest.fixture
def esc(tmp_path: Path) -> Escenario:
    return Escenario(tmp_path)


@pytest.fixture
def doble() -> Doble:
    return Doble()


@pytest.fixture
def crudo(tmp_path: Path) -> ke.Crudo:
    c = ke.Crudo(tmp_path / "crudo")
    c.crear()
    return c


def correr_main(esc: Escenario, doble: Doble, *extra: str, sin: Sequence[str] = ()) -> int:
    return ke.main(esc.args(*extra, sin=sin), entorno=doble.entorno())


def cfg_de(esc: Escenario, **cambios: Any) -> ke.ConfigServidor:
    base: dict[str, Any] = {
        "modelo_dir": esc.modelo,
        "adaptadores": ke.descubrir_adaptadores(esc.envio),
        "puerto": 8000,
        "extra": (),
    }
    return ke.ConfigServidor(**{**base, **cambios})


def compuerta(tmp_path: Path, datos: bytes) -> kaggle_prereg.Resultado:
    """Cierra ``ensayo_notebook`` con ``datos`` en un repositorio sintetico y lo contrasta."""
    raiz = tmp_path / "repo"
    destino = raiz / RUTA_REGISTRO
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(datos)
    params = kaggle_prereg.load_params(kaggle_prereg.DEFAULT_PARAMS)
    params["abiertos"]["ensayo_notebook"]["valor"] = {
        "ruta": RUTA_REGISTRO,
        "sha256": hashlib.sha256(datos).hexdigest(),
    }
    assert kaggle_prereg.check_structure(params) == []
    return kaggle_prereg.check_closed(params, raiz)


# ---------------------------------------------------------------------------
# Lo fijado por el pre-registro y por los otros guiones
# ---------------------------------------------------------------------------


def test_constantes_coinciden_con_el_preregistro() -> None:
    fijos = kaggle_prereg.load_params(kaggle_prereg.DEFAULT_PARAMS)["fijos"]
    assert list(ke.CANDIDATOS_TOKENS) == fijos["max_output_tokens_candidatos"]
    assert fijos["max_tool_calls"] == ke.MAX_TOOL_CALLS
    assert fijos["max_turns"] == ke.MAX_TURNS
    assert fijos["timeout_seconds"] == ke.TIMEOUT_SECONDS
    assert ke.MAX_TIME_MINUTES == 5  # A.0: --max-time-minutes 5
    assert ke.ESQUEMA_REGISTRO == kaggle_prereg.ESQUEMA_ENSAYO
    assert ke.BACKENDS == kaggle_prereg.BACKENDS
    assert ke.ARCHIVO_MUESTREO == kaggle_prereg.SAMPLING_REL
    assert set(ke.ESQUEMA) == set(kaggle_prereg.ENSAYO)
    assert (ke.REPO_TRES_PRIMERAS, ke.REPO_UNICA, ke.TAREAS_DEL_PRIMERO) == (
        "psf/requests",
        "encode/httpx",
        3,
    )
    assert (ke.EXIT_OK, ke.EXIT_INCOMPLETO, ke.EXIT_INVALIDO, ke.EXIT_INESPERADO) == (0, 1, 2, 3)


def test_listas_de_errores_coinciden_con_kaggle_replicas() -> None:
    assert ke.CONTEXT_ERROR_PREFIX == kaggle_replicas.CONTEXT_ERROR_PREFIX
    assert ke.CONTEXT_ERROR_MARKERS == kaggle_replicas.CONTEXT_ERROR_MARKERS
    assert tuple(p for p, _ in kaggle_replicas.AGENT_ERROR_PREFIXES) == ke.AGENT_ERROR_PREFIXES
    infra = {p for p, _ in kaggle_replicas.INFRA_ERROR_PREFIXES}
    assert set(ke.INFRA_FASE_AGENTE) | set(ke.INFRA_FASE_VERIFICACION) == infra
    assert not set(ke.INFRA_FASE_AGENTE) & set(ke.INFRA_FASE_VERIFICACION)


# ---------------------------------------------------------------------------
# Resultado tipado
# ---------------------------------------------------------------------------


def test_un_resultado_sin_medir_no_lleva_valores() -> None:
    with pytest.raises(ValueError, match="no lleva valores"):
        ke.Parcial(ke.ERROR, {"segundos": 0}, "tiempo_agotado")
    with pytest.raises(ValueError, match="no lleva valores"):
        ke.Parcial(ke.NO_DISPONIBLE, {"x": 1}, "comando_ausente")


def test_un_resultado_medido_no_lleva_nulos_ni_categoria() -> None:
    with pytest.raises(ValueError, match="ninguno nulo"):
        ke.medido({"carga_segundos": None})
    with pytest.raises(ValueError, match="ninguno nulo"):
        ke.medido({"lista": [1, {"x": None}]})
    with pytest.raises(ValueError, match="ninguno nulo"):
        ke.medido({})
    with pytest.raises(ValueError, match="no lleva categoria"):
        ke.Parcial(ke.MEDIDO, {"x": 1}, "tiempo_agotado")


def test_categoria_y_estado_son_de_lista_cerrada() -> None:
    with pytest.raises(ValueError, match="lista cerrada"):
        ke.sin_valor(ke.ERROR, "algo_nuevo")
    with pytest.raises(ValueError, match="lista cerrada"):
        ke.Parcial(ke.ERROR, {}, None)
    with pytest.raises(ValueError, match="desconocido"):
        ke.Parcial("quiza", {"x": 1})
    assert len(set(ke.CATEGORIAS)) == len(ke.CATEGORIAS)


def test_correr_mide_el_tiempo_y_convierte_una_excepcion_en_error(doble: Doble) -> None:
    def lenta() -> ke.Parcial:
        doble.dormir(2.5)
        return ke.medido({"x": 1})

    r = ke.correr("lenta", lenta, doble.entorno())
    assert (r.sonda, r.estado, r.segundos) == ("lenta", ke.MEDIDO, 2.5)

    def rota() -> ke.Parcial:
        doble.dormir(1.0)
        raise RuntimeError(POISON_LOG)

    r = ke.correr("rota", rota, doble.entorno())
    assert (r.estado, r.categoria, r.segundos, dict(r.valores)) == (ke.ERROR, "error_inesperado", 1.0, {})
    assert POISON_LOG not in json.dumps(r.versionable())
    assert r.parcial.privado == {"excepcion": "RuntimeError"}


def test_correr_deja_pasar_una_interrupcion(doble: Doble) -> None:
    def interrumpida() -> ke.Parcial:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        ke.correr("x", interrumpida, doble.entorno())


# ---------------------------------------------------------------------------
# Sondas del anfitrion: medido / no_disponible / error
# ---------------------------------------------------------------------------


def test_sonda_python_tres_resultados(doble: Doble) -> None:
    ent = doble.entorno()
    assert ke.sonda_python(ent).valores == {"version": "3.12.3"}
    vacia = ke.sonda_python(ke.Entorno(**{**ent.__dict__, "version_python": ""}))
    assert (vacia.estado, vacia.categoria) == (ke.NO_DISPONIBLE, "fuente_ausente")
    rara = ke.sonda_python(ke.Entorno(**{**ent.__dict__, "version_python": f"3.12 {POISON_LOG}"}))
    assert (rara.estado, rara.categoria) == (ke.ERROR, "salida_ilegible")


@pytest.mark.parametrize(
    ("n", "estado", "categoria", "valores"),
    [
        (8, ke.MEDIDO, None, {"cpus": 8}),
        (None, ke.NO_DISPONIBLE, "fuente_ausente", {}),
        (0, ke.ERROR, "salida_ilegible", {}),
        (True, ke.ERROR, "salida_ilegible", {}),
    ],
)
def test_sonda_cpu(doble: Doble, n: Any, estado: str, categoria: str | None, valores: dict[str, Any]) -> None:
    doble.n_cpus = n
    r = ke.sonda_cpu(doble.entorno())
    assert (r.estado, r.categoria, dict(r.valores)) == (estado, categoria, valores)


@pytest.mark.parametrize(
    ("texto", "estado", "categoria", "valores"),
    [
        ("MemFree: 5 kB\nMemTotal:   2097152 kB\n", ke.MEDIDO, None, {"total_mib": 2048}),
        (None, ke.NO_DISPONIBLE, "fuente_ausente", {}),
        ("MemTotal: muchos kB\n", ke.ERROR, "salida_ilegible", {}),
        ("SwapMemTotal: 2097152 kB\n", ke.ERROR, "salida_ilegible", {}),
    ],
)
def test_sonda_memoria(doble: Doble, texto: Any, estado: str, categoria: str | None, valores: Any) -> None:
    doble.meminfo = texto
    r = ke.sonda_memoria(doble.entorno())
    assert (r.estado, r.categoria, dict(r.valores)) == (estado, categoria, valores)


@pytest.mark.parametrize(
    ("libre", "estado", "categoria", "valores"),
    [
        (3 * 1024 * 1024 + 5, ke.MEDIDO, None, {"libre_mib": 3}),
        (0, ke.MEDIDO, None, {"libre_mib": 0}),
        (None, ke.NO_DISPONIBLE, "fuente_ausente", {}),
        (-1, ke.ERROR, "salida_ilegible", {}),
    ],
)
def test_sonda_disco(doble: Doble, libre: Any, estado: str, categoria: str | None, valores: Any) -> None:
    doble.disco = libre
    r = ke.sonda_disco(doble.entorno(), Path("."))
    assert (r.estado, r.categoria, dict(r.valores)) == (estado, categoria, valores)


@pytest.mark.parametrize(
    ("version", "estado", "categoria", "valores"),
    [
        ("0.19.1", ke.MEDIDO, None, {"version": "0.19.1"}),
        ("2.8.0+cu128", ke.MEDIDO, None, {"version": "2.8.0+cu128"}),
        (None, ke.NO_DISPONIBLE, "paquete_ausente", {}),
        (f"0.1 {POISON_LOG}", ke.ERROR, "salida_ilegible", {}),
        ("", ke.ERROR, "salida_ilegible", {}),
        ("/kaggle/input/x", ke.ERROR, "salida_ilegible", {}),
    ],
)
def test_sonda_version(doble: Doble, version: Any, estado: str, categoria: str | None, valores: Any) -> None:
    doble.paquetes["vllm"] = version
    r = ke.sonda_version(doble.entorno(), "vllm")
    assert (r.estado, r.categoria, dict(r.valores)) == (estado, categoria, valores)


@pytest.mark.parametrize(
    ("salida", "estado", "categoria"),
    [
        (ke.Salida("ok", 0, "NVIDIA L4, 23034\n\nTesla T4, 15360\n", ""), ke.MEDIDO, None),
        (ke.Salida("ausente", None, "", ""), ke.NO_DISPONIBLE, "comando_ausente"),
        (ke.Salida("sin_permiso", None, "", ""), ke.NO_DISPONIBLE, "sin_permiso"),
        (ke.Salida("tiempo_agotado", None, "NVIDIA L4, 23034\n", ""), ke.ERROR, "tiempo_agotado"),
        (ke.Salida("ok", 9, "NVIDIA L4, 23034\n", POISON_LOG), ke.ERROR, "comando_fallo"),
        (ke.Salida("ok", 0, "", ""), ke.ERROR, "salida_ilegible"),
        (ke.Salida("ok", 0, f"{POISON_LOG}!, 23034\n", ""), ke.ERROR, "salida_ilegible"),
        (ke.Salida("ok", 0, "NVIDIA L4, mucha\n", ""), ke.ERROR, "salida_ilegible"),
        (ke.Salida("ok", 0, "NVIDIA L4, 1, 2\n", ""), ke.ERROR, "salida_ilegible"),
    ],
)
def test_sonda_gpu(
    doble: Doble, crudo: ke.Crudo, salida: ke.Salida, estado: str, categoria: str | None
) -> None:
    doble.manejadores["nvidia_gpu"] = lambda argv: salida
    r = ke.sonda_gpu(doble.entorno(), crudo)
    assert (r.estado, r.categoria) == (estado, categoria)
    assert r.comandos == (("nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"),)
    if estado == ke.MEDIDO:
        assert r.valores == {
            "cantidad": 2,
            "modelos": ["NVIDIA L4", "Tesla T4"],
            "memoria_total_mib": [23034, 15360],
        }
    else:
        assert r.valores == {}


def docker_con(doble: Doble, **pasos: ke.Salida) -> None:
    for nombre, salida in pasos.items():
        doble.manejadores[f"docker_{nombre}"] = lambda argv, s=salida: s


def test_sonda_docker_sin_binario_es_un_valor_medido(doble: Doble, crudo: ke.Crudo) -> None:
    r = ke.sonda_docker(doble.entorno(), crudo, "swebench-sandbox:latest")
    assert r.valores == {"disponible": False, "motivo": "binario_ausente", "backend": "subprocess"}
    assert [c[:2] for c in doble.comandos] == [["docker", "--version"]]


def test_sonda_docker_demonio_inaccesible_es_un_valor_medido(doble: Doble, crudo: ke.Crudo) -> None:
    docker_con(doble, version=Doble.ok("Docker 27"), info=ke.Salida("ok", 1, "", POISON_LOG))
    r = ke.sonda_docker(doble.entorno(), crudo, "img:1")
    assert r.valores == {"disponible": False, "motivo": "demonio_inaccesible", "backend": "subprocess"}
    assert len(doble.comandos) == 2


@pytest.mark.parametrize(
    ("imagen", "sdk", "contenedor", "backend"),
    [
        (0, "7.1.0", 0, "docker"),
        (1, "7.1.0", 0, "subprocess"),
        (0, None, 0, "subprocess"),
        (0, "7.1.0", 125, "subprocess"),
    ],
)
def test_sonda_docker_backend(
    doble: Doble, crudo: ke.Crudo, imagen: int, sdk: str | None, contenedor: int, backend: str
) -> None:
    doble.paquetes["docker"] = sdk
    docker_con(
        doble,
        version=Doble.ok("Docker 27"),
        imagen=Doble.ok("sha256:abc", imagen),
        run=Doble.ok("", contenedor),
    )
    r = ke.sonda_docker(doble.entorno(), crudo, "/kaggle/input/tercero/imagen:1")
    assert r.valores == {
        "disponible": True,
        "imagen_presente": imagen == 0,
        "sdk_python": sdk is not None,
        "contenedor_arranca": imagen == 0 and contenedor == 0,
        "backend": backend,
    }
    # sin imagen no se intenta arrancar un contenedor
    assert len(doble.comandos) == (4 if imagen == 0 else 3)
    if imagen == 0:
        assert doble.comandos[3] == [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "/kaggle/input/tercero/imagen:1",
            "true",
        ]
    assert "tercero" not in json.dumps(r.comandos)
    assert r.comandos[2] == ("docker", "image", "inspect", "--format", "{{.Id}}", "<imagen>")


@pytest.mark.parametrize("paso", ["version", "info", "imagen", "run"])
@pytest.mark.parametrize(
    ("estado_salida", "estado", "categoria"),
    [("tiempo_agotado", ke.ERROR, "tiempo_agotado"), ("sin_permiso", ke.NO_DISPONIBLE, "sin_permiso")],
)
def test_sonda_docker_no_da_valor_si_un_paso_no_termina(
    doble: Doble, crudo: ke.Crudo, paso: str, estado_salida: str, estado: str, categoria: str
) -> None:
    doble.paquetes["docker"] = "7.1.0"
    docker_con(doble, version=Doble.ok("Docker 27"))
    docker_con(doble, **{paso: ke.Salida(estado_salida, None, "", "")})
    r = ke.sonda_docker(doble.entorno(), crudo, "img:1")
    assert (r.estado, r.categoria, dict(r.valores)) == (estado, categoria, {})


def test_sonda_docker_binario_ausente_a_mitad_no_es_un_valor(doble: Doble, crudo: ke.Crudo) -> None:
    docker_con(doble, version=Doble.ok("Docker 27"), info=ke.Salida("ausente", None, "", ""))
    r = ke.sonda_docker(doble.entorno(), crudo, "img:1")
    assert (r.estado, r.categoria) == (ke.NO_DISPONIBLE, "comando_ausente")


@pytest.mark.parametrize(
    ("horas", "fuente", "estado", "categoria"),
    [
        (12.0, "documentacion de Kaggle", ke.MEDIDO, None),
        (None, "documentacion de Kaggle", ke.NO_DISPONIBLE, "no_declarada"),
        (12.0, None, ke.NO_DISPONIBLE, "no_declarada"),
        (0.0, "x", ke.ERROR, "valor_no_admitido"),
        (-3.0, "x", ke.ERROR, "valor_no_admitido"),
        (48.5, "x", ke.ERROR, "valor_no_admitido"),
        (float("nan"), "x", ke.ERROR, "valor_no_admitido"),
        (float("inf"), "x", ke.ERROR, "valor_no_admitido"),
        (12.0, f"segun {POISON_LOG}; rm -rf", ke.ERROR, "valor_no_admitido"),
        (12.0, "/kaggle/input/tercero/notas", ke.ERROR, "valor_no_admitido"),
    ],
)
def test_sonda_sesion(horas: Any, fuente: Any, estado: str, categoria: str | None) -> None:
    r = ke.sonda_sesion(horas, fuente)
    assert (r.estado, r.categoria) == (estado, categoria)
    if estado == ke.MEDIDO:
        assert r.valores == {"horas": 12.0, "origen": "declarada", "fuente": "documentacion de Kaggle"}
    else:
        assert r.valores == {}


def test_sonda_sesion_admite_el_limite_de_48_horas() -> None:
    assert ke.sonda_sesion(48.0, "x").estado == ke.MEDIDO


def test_sonda_envio_kit_original(esc: Escenario) -> None:
    r = ke.sonda_envio(esc.envio, esc.manifiesto)
    assert r.valores == {
        "archivos_del_manifiesto": 5,
        "faltan": 0,
        "distintos": 0,
        "sobran": 0,
        "coincide": True,
    }


@pytest.mark.parametrize(
    ("cambio", "clave"),
    [("modificar", "distintos"), ("borrar", "faltan"), ("anadir", "sobran")],
)
def test_sonda_envio_detecta_un_kit_alterado(esc: Escenario, cambio: str, clave: str) -> None:
    if cambio == "modificar":
        (esc.envio / "agent.yaml").write_text("name: otro\n", encoding="utf-8")
    elif cambio == "borrar":
        (esc.envio / "agent.yaml").unlink()
    else:
        (esc.envio / "skills").mkdir()
        (esc.envio / "skills" / "SKILL.md").write_text("propia", encoding="utf-8")
    r = ke.sonda_envio(esc.envio, esc.manifiesto)
    esperado = {"archivos_del_manifiesto": 5, "faltan": 0, "distintos": 0, "sobran": 0, "coincide": False}
    assert r.valores == {**esperado, clave: 1}


def test_sonda_envio_no_disponible_y_error(esc: Escenario, tmp_path: Path) -> None:
    r = ke.sonda_envio(tmp_path / "no_existe", esc.manifiesto)
    assert (r.estado, r.categoria) == (ke.NO_DISPONIBLE, "entrada_ausente")
    r = ke.sonda_envio(esc.envio, tmp_path / "no_existe.json")
    assert (r.estado, r.categoria) == (ke.NO_DISPONIBLE, "entrada_ausente")
    for malo in ("{", "[]", '{"files": []}', '{"files": [{"path": "a", "sha256": "corto"}]}', '{"files": 3}'):
        esc.manifiesto.write_text(malo, encoding="utf-8")
        r = ke.sonda_envio(esc.envio, esc.manifiesto)
        assert (r.estado, r.categoria, dict(r.valores)) == (ke.ERROR, "entrada_ilegible", {}), malo


@pytest.mark.parametrize(
    ("salida", "estado", "categoria", "valores"),
    [
        (ke.Salida("ok", 0, POISON_LOG, ""), ke.MEDIDO, None, {"compila": True}),
        (ke.Salida("ok", 4, "", f"Traceback {POISON_LOG}"), ke.MEDIDO, None, {"compila": False}),
        (ke.Salida("ok", 3, "", ""), ke.NO_DISPONIBLE, "dependencia_ausente", {}),
        (ke.Salida("ausente", None, "", ""), ke.NO_DISPONIBLE, "comando_ausente", {}),
        (ke.Salida("tiempo_agotado", None, "", ""), ke.ERROR, "tiempo_agotado", {}),
        (ke.Salida("ok", 1, "", POISON_LOG), ke.ERROR, "comando_fallo", {}),
        (ke.Salida("ok", -9, "", ""), ke.ERROR, "comando_fallo", {}),
    ],
)
def test_sonda_compila(
    doble: Doble,
    crudo: ke.Crudo,
    esc: Escenario,
    salida: ke.Salida,
    estado: str,
    categoria: Any,
    valores: Any,
) -> None:
    doble.manejadores["compila"] = lambda argv: salida
    r = ke.sonda_compila(doble.entorno(), crudo, esc.envio)
    assert (r.estado, r.categoria, dict(r.valores)) == (estado, categoria, valores)
    assert doble.comandos[0] == ["/usr/bin/python3", "-c", ke.PROGRAMA_COMPILAR, str(esc.envio)]
    assert r.comandos == (("<python>", "-c", "<programa de compilacion>", "<envio>"),)
    variables = doble.variables_de["compila"]
    assert variables is not None and variables["HF_HUB_OFFLINE"] == "1"


def test_programa_de_compilacion_es_python_valido_y_distingue_sus_salidas() -> None:
    compile(ke.PROGRAMA_COMPILAR, "<compilar>", "exec")
    assert "sys.exit(3)" in ke.PROGRAMA_COMPILAR and "sys.exit(4)" in ke.PROGRAMA_COMPILAR
    for herramienta in ke.HERRAMIENTAS_ARNES:
        assert repr(herramienta) in ke.PROGRAMA_COMPILAR
    assert len(ke.HERRAMIENTAS_ARNES) == 9


def test_programa_de_compilacion_sale_con_3_si_falta_el_arnes(tmp_path: Path) -> None:
    """Corre el programa real en este interprete, que no tiene el arnes instalado."""
    r = ke.ejecutar_real([sys.executable, "-c", ke.PROGRAMA_COMPILAR, str(tmp_path)], 60.0, None)
    assert (r.estado, r.codigo) == ("ok", 3)


def test_sonda_tareas_elige_las_de_a0_y_no_conserva_nada_mas(esc: Escenario) -> None:
    r = ke.sonda_tareas(esc.tasks)
    assert r.valores == {"tareas": 4}
    assert r.privado == {"ids": ELEGIDAS}
    todo = json.dumps([dict(r.valores), dict(r.privado)])
    assert not any(p in todo for p in POISON_TODOS)


@pytest.mark.parametrize(
    "tareas",
    [
        [("requests_1", "psf/requests"), ("requests_2", "psf/requests"), ("httpx_1", "encode/httpx")],
        [(f"requests_{i}", "psf/requests") for i in range(3)],
        [(f"requests_{i}", "psf/requests") for i in range(3)]
        + [("httpx_1", "encode/httpx"), ("httpx_2", "encode/httpx")],
        [(f"requests_{i}", "psf/requests") for i in range(3)] + [("requests_0", "encode/httpx")],
    ],
)
def test_sonda_tareas_rechaza_un_archivo_que_no_da_las_cuatro(esc: Escenario, tareas: Any) -> None:
    esc.escribir_tareas(tareas)
    r = ke.sonda_tareas(esc.tasks)
    assert (r.estado, r.categoria, dict(r.privado)) == (ke.ERROR, "entrada_inesperada", {})


def test_sonda_tareas_no_disponible_e_ilegible(esc: Escenario, tmp_path: Path) -> None:
    r = ke.sonda_tareas(tmp_path / "no_existe.jsonl")
    assert (r.estado, r.categoria) == (ke.NO_DISPONIBLE, "entrada_ausente")
    for malo in (
        "{no es json\n",
        "[1, 2]\n",
        '{"repo": "psf/requests"}\n',
        '{"instance_id": "../x", "repo": "a"}\n',
    ):
        esc.tasks.write_text(malo, encoding="utf-8")
        r = ke.sonda_tareas(esc.tasks)
        assert (r.estado, r.categoria) == (ke.ERROR, "entrada_ilegible"), malo


# ---------------------------------------------------------------------------
# Servidor: comando, arranque y parada
# ---------------------------------------------------------------------------


def test_comando_servidor_lleva_los_parametros_de_harness_3_1(esc: Escenario) -> None:
    cfg = cfg_de(esc)
    assert ke.real(ke.comando_servidor("/usr/bin/python3", cfg)) == [
        "/usr/bin/python3",
        "-m",
        "vllm.entrypoints.openai.api_server",
        "--model",
        str(esc.modelo),
        "--served-model-name",
        "gemma-4-31b-it-qat-w4a16-ct",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
        "--max-model-len",
        "32768",
        "--dtype",
        "bfloat16",
        "--gpu-memory-utilization",
        "0.9",
        "--tensor-parallel-size",
        "4",
        "--enable-auto-tool-choice",
        "--tool-call-parser",
        "gemma4",
        "--reasoning-parser",
        "gemma4",
        "--reasoning-config",
        '{"reasoning_start_str": "<|channel>", "reasoning_end_str": "<channel|>"}',
        "--no-scheduler-reserve-full-isl",
        "--enable-lora",
        "--max-loras",
        "2",
        "--max-lora-rank",
        "128",
        "--lora-modules",
        f"main_lora={esc.envio / 'adapters' / 'main_lora'}",
        f"tool_lora={esc.envio / 'adapters' / 'tool_lora'}",
    ]


def test_comando_servidor_sin_adaptadores_no_activa_lora(esc: Escenario) -> None:
    argv = ke.real(ke.comando_servidor("python", cfg_de(esc, adaptadores=(), extra=("--dtype=bfloat16",))))
    assert "--enable-lora" not in argv and "--lora-modules" not in argv
    assert argv[-1] == "--dtype=bfloat16"


def test_forma_publica_del_comando_del_servidor_no_trae_rutas(esc: Escenario) -> None:
    cfg = cfg_de(esc, extra=("--chat-template=/kaggle/input/tercero/plantilla.jinja", "/kaggle/input/otro"))
    pub = ke.publico(ke.comando_servidor("/opt/python", cfg))
    assert pub[0] == "<python>" and pub[4] == "<modelo>"
    assert pub[-4:] == (
        "main_lora=<envio>:adapters:main_lora",
        "tool_lora=<envio>:adapters:tool_lora",
        "<oculto>",
        "<oculto>",
    )
    texto = json.dumps(pub)
    assert str(esc.raiz) not in texto and "kaggle" not in texto and "tercero" not in texto


def test_descubrir_adaptadores(esc: Escenario) -> None:
    assert [n for n, _ in ke.descubrir_adaptadores(esc.envio)] == ["main_lora", "tool_lora"]
    (esc.envio / "adapters" / "sin_config").mkdir()
    assert len(ke.descubrir_adaptadores(esc.envio)) == 2
    assert ke.descubrir_adaptadores(esc.raiz) == ()
    malo = esc.envio / "adapters" / "nombre con espacio"
    malo.mkdir()
    (malo / "adapter_config.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ke.EnsayoError):
        ke.descubrir_adaptadores(esc.envio)


def test_hash_del_guion_no_depende_de_rutas_y_cambia_con_los_parametros(
    esc: Escenario, tmp_path: Path
) -> None:
    base = ke.hash_guion_servidor(cfg_de(esc))
    assert ke.SHA_RE.fullmatch(base)
    otra_ruta = cfg_de(
        esc,
        modelo_dir=tmp_path / "otro" / "sitio",
        adaptadores=tuple((n, tmp_path / n) for n, _ in ke.descubrir_adaptadores(esc.envio)),
    )
    assert ke.hash_guion_servidor(otra_ruta) == base
    assert ke.hash_guion_servidor(cfg_de(esc, puerto=8001)) != base
    assert ke.hash_guion_servidor(cfg_de(esc, extra=("--dtype=bfloat16",))) != base
    assert ke.hash_guion_servidor(cfg_de(esc, adaptadores=())) != base
    assert ke.hash_guion_servidor(cfg_de(esc, adaptadores=cfg_de(esc).adaptadores[:1])) != base


def test_variables_de_los_hijos_cortan_la_red_y_apuntan_al_servidor(doble: Doble, esc: Escenario) -> None:
    sin_servidor = ke._variables_hijo(doble.entorno(), None)
    assert sin_servidor["MODEL_PROXY_URL"] == "https://proxy.invalid/models"  # no se toca sin servidor
    for nombre, valor in ke.VARIABLES_SIN_RED:
        assert sin_servidor[nombre] == valor
    assert dict(ke.VARIABLES_SIN_RED)["HF_HUB_OFFLINE"] == "1"
    assert dict(ke.VARIABLES_SIN_RED)["TRANSFORMERS_OFFLINE"] == "1"
    con = ke._variables_hijo(doble.entorno(), cfg_de(esc, puerto=8123))
    for nombre in ("MODEL_PROXY_URL", "LITELLM_API_BASE", "LOCAL_INFERENCE_URL", "OPENAI_BASE_URL"):
        assert con[nombre] == "http://127.0.0.1:8123/v1"
    assert con["PATH"] == "/usr/bin"
    assert con["OPENAI_API_KEY"] == "EMPTY"


def test_sonda_servidor_proceso_que_termina_es_un_valor_medido_sin_tiempo(
    doble: Doble, crudo: ke.Crudo, esc: Escenario
) -> None:
    doble.salud_tras = 10**9
    doble.proceso = ProcesoFalso(muere_tras=2)
    guardia = ke.Guardia()
    r = ke.sonda_servidor(doble.entorno(), crudo, cfg_de(esc), guardia, 60.0)
    assert r.estado == ke.MEDIDO
    assert (r.valores["arranca"], r.valores["motivo"]) == (False, "proceso_termino")
    assert "carga_segundos" not in r.valores
    assert guardia.detener() is True


def test_sonda_servidor_espera_agotada_es_un_valor_medido_sin_tiempo(
    doble: Doble, crudo: ke.Crudo, esc: Escenario
) -> None:
    doble.salud_tras = 10**9
    guardia = ke.Guardia()
    r = ke.sonda_servidor(doble.entorno(), crudo, cfg_de(esc), guardia, 7.0)
    assert (r.valores["arranca"], r.valores["motivo"]) == (False, "tiempo_agotado")
    assert "carga_segundos" not in r.valores
    assert doble.consultas_salud == 4  # t = 0, 2, 4 y 6 s; a los 8 s ya paso la espera de 7
    assert guardia.proceso is doble.proceso  # sigue vivo: lo detiene la guardia
    assert guardia.detener() is True
    assert doble.proceso.eventos[0] == "terminar"


def test_sonda_servidor_respuesta_no_200_no_cuenta_como_arranque(
    doble: Doble, crudo: ke.Crudo, esc: Escenario
) -> None:
    doble.http_manejador = lambda m, u, c: ke.Respuesta("ok", 404, b"")
    r = ke.sonda_servidor(doble.entorno(), crudo, cfg_de(esc), ke.Guardia(), 5.0)
    assert r.valores["arranca"] is False
    doble.http_manejador = lambda m, u, c: ke.Respuesta("sin_conexion", None, b"")
    doble.t = 100.0
    crudo2 = ke.Crudo(crudo.raiz / "otro")
    crudo2.crear()
    r = ke.sonda_servidor(doble.entorno(), crudo2, cfg_de(esc), ke.Guardia(), 5.0)
    assert r.valores["arranca"] is False


def test_sonda_servidor_fallo_al_lanzar_es_error_sin_proceso(
    doble: Doble, crudo: ke.Crudo, esc: Escenario
) -> None:
    doble.lanzar_falla = True
    guardia = ke.Guardia()
    r = ke.sonda_servidor(doble.entorno(), crudo, cfg_de(esc), guardia, 60.0)
    assert (r.estado, r.categoria, dict(r.valores)) == (ke.ERROR, "lanzamiento_fallo", {})
    assert guardia.proceso is None and guardia.lanzados == 0


def test_la_guardia_tiene_el_proceso_aunque_la_espera_reviente(
    doble: Doble, crudo: ke.Crudo, esc: Escenario
) -> None:
    """Una excepcion a mitad del arranque no deja el servidor huerfano."""

    def revienta(metodo: str, url: str, cuerpo: bytes | None) -> ke.Respuesta:
        raise RuntimeError(POISON_LOG)

    doble.http_manejador = revienta
    guardia = ke.Guardia()
    ent = doble.entorno()
    r = ke.correr("servidor", lambda: ke.sonda_servidor(ent, crudo, cfg_de(esc), guardia, 60.0), ent)
    assert (r.estado, r.categoria) == (ke.ERROR, "error_inesperado")
    assert guardia.proceso is doble.proceso and doble.proceso.esta_vivo
    assert guardia.detener() is True
    assert not doble.proceso.esta_vivo and guardia.proceso is None


def test_guardia_mata_si_terminar_no_basta() -> None:
    guardia = ke.Guardia()
    p = ProcesoFalso(obedece_terminar=False)
    guardia.asignar(p)
    assert guardia.detener() is True
    assert p.eventos == [
        "terminar",
        f"esperar:{ke.GRACIA_TERMINAR:g}",
        "matar",
        f"esperar:{ke.GRACIA_MATAR:g}",
    ]
    assert not p.esta_vivo


def test_guardia_informa_si_el_proceso_no_muere() -> None:
    guardia = ke.Guardia()
    p = ProcesoFalso(obedece_terminar=False, obedece_matar=False)
    guardia.asignar(p)
    assert guardia.detener() is False
    assert "matar" in p.eventos and guardia.proceso is p  # lo conserva para poder reintentar
    p.obedece_matar = True
    assert guardia.detener() is True


def test_guardia_no_da_por_muerto_lo_que_no_puede_comprobar() -> None:
    class Roto(ProcesoFalso):
        def terminar(self) -> None:
            raise RuntimeError(POISON_LOG)

        def esperar(self, segundos: float) -> bool:
            raise RuntimeError(POISON_LOG)

    guardia = ke.Guardia()
    p = Roto(vivo_lanza=True)
    guardia.asignar(p)
    assert guardia.detener() is False
    assert "matar" in p.eventos


@pytest.mark.parametrize(
    ("salida", "valores"),
    [
        (ke.Salida("ok", 0, "", ""), {"servidor_detenido": True, "procesos_en_gpu": 0}),
        (ke.Salida("ok", 0, "4242\n4243\n", ""), {"servidor_detenido": True, "procesos_en_gpu": 2}),
        (ke.Salida("ausente", None, "", ""), {"servidor_detenido": True}),
        (ke.Salida("ok", 1, "4242\n", ""), {"servidor_detenido": True}),
        (ke.Salida("ok", 0, f"4242\n{POISON_LOG}\n", ""), {"servidor_detenido": True}),
    ],
)
def test_sonda_limpieza(doble: Doble, crudo: ke.Crudo, salida: ke.Salida, valores: dict[str, Any]) -> None:
    doble.manejadores["nvidia_apps"] = lambda argv: salida
    r = ke.sonda_limpieza(doble.entorno(), crudo, True)
    assert r.valores == valores
    assert ke.sonda_limpieza(doble.entorno(), crudo, False).valores["servidor_detenido"] is False


# ---------------------------------------------------------------------------
# Sondas contra el servidor
# ---------------------------------------------------------------------------


def http_fijo(doble: Doble, respuesta: ke.Respuesta, *, solo: str = "") -> None:
    doble.http_manejador = lambda m, u, c: respuesta if solo in u else None


def test_sonda_modelo_medido(doble: Doble, crudo: ke.Crudo, esc: Escenario) -> None:
    r = ke.sonda_modelo(doble.entorno(), crudo, cfg_de(esc), "2")
    assert r.valores == {"id": "gemma-4-31b-it-qat-w4a16-ct", "version": "2", "adaptadores_servidos": 2}
    assert doble.peticiones == [("GET", "http://127.0.0.1:8000/v1/models", None)]


@pytest.mark.parametrize(
    ("version", "respuesta", "estado", "categoria"),
    [
        (None, None, ke.NO_DISPONIBLE, "no_declarada"),
        (f"2 {POISON_LOG}", None, ke.ERROR, "valor_no_admitido"),
        ("2", ke.Respuesta("sin_conexion", None, b""), ke.ERROR, "sin_conexion"),
        ("2", ke.Respuesta("tiempo_agotado", None, b""), ke.ERROR, "tiempo_agotado"),
        ("2", ke.Respuesta("ok", 500, POISON_LOG.encode()), ke.ERROR, "respuesta_inesperada"),
        ("2", ke.Respuesta("ok", 200, b"no es json"), ke.ERROR, "salida_ilegible"),
        ("2", ke.Respuesta("ok", 200, b'{"data": "x"}'), ke.ERROR, "salida_ilegible"),
        ("2", ke.Respuesta("ok", 200, b'{"data": [3]}'), ke.ERROR, "salida_ilegible"),
        (
            "2",
            ke.Respuesta("ok", 200, b'{"data": [{"id": "otro-modelo"}]}'),
            ke.ERROR,
            "respuesta_inesperada",
        ),
    ],
)
def test_sonda_modelo_sin_valor(
    doble: Doble, crudo: ke.Crudo, esc: Escenario, version: Any, respuesta: Any, estado: str, categoria: str
) -> None:
    if respuesta is not None:
        http_fijo(doble, respuesta)
    r = ke.sonda_modelo(doble.entorno(), crudo, cfg_de(esc), version)
    assert (r.estado, r.categoria, dict(r.valores)) == (estado, categoria, {})


def test_sonda_rendimiento_es_la_mediana_de_tres_peticiones(
    doble: Doble, crudo: ke.Crudo, esc: Escenario
) -> None:
    latencias = iter([10.0, 5.0, 20.0])

    def lento(metodo: str, url: str, cuerpo: bytes | None) -> ke.Respuesta | None:
        doble.latencia = next(latencias)
        return None

    doble.http_manejador = lento
    r = ke.sonda_rendimiento(doble.entorno(), crudo, cfg_de(esc))
    assert r.valores == {
        "tokens_por_segundo": 50.0,  # 500/10, 500/5 y 500/20: la mediana es 50
        "muestras": [
            {"tokens": 500, "segundos": 10.0},
            {"tokens": 500, "segundos": 5.0},
            {"tokens": 500, "segundos": 20.0},
        ],
        "max_tokens": 512,
        "incluye_lectura_del_prompt": True,
    }
    assert len(doble.peticiones) == ke.MUESTRAS_RENDIMIENTO == 3
    metodo, url, cuerpo = doble.peticiones[0]
    assert (metodo, url) == ("POST", "http://127.0.0.1:8000/v1/chat/completions")
    assert cuerpo is not None
    peticion = json.loads(cuerpo)
    assert peticion == {
        "model": ke.MODELO,
        "messages": [{"role": "user", "content": ke.PROMPT_RENDIMIENTO}],
        "max_tokens": 512,
        "temperature": 0,
    }
    assert POISON_RESPUESTA in (crudo.raiz / "001_rendimiento_1.txt").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("respuesta", "categoria"),
    [
        (ke.Respuesta("sin_conexion", None, b""), "sin_conexion"),
        (ke.Respuesta("tiempo_agotado", None, b""), "tiempo_agotado"),
        (ke.Respuesta("ok", 503, b"{}"), "respuesta_inesperada"),
        (ke.Respuesta("ok", 200, b"<html>"), "salida_ilegible"),
        (ke.Respuesta("ok", 200, b'{"usage": {}}'), "salida_ilegible"),
        (ke.Respuesta("ok", 200, b'{"usage": {"completion_tokens": "muchos"}}'), "salida_ilegible"),
        (ke.Respuesta("ok", 200, b'{"usage": {"completion_tokens": true}}'), "salida_ilegible"),
        (ke.Respuesta("ok", 200, b'{"usage": {"completion_tokens": 63}}'), "respuesta_corta"),
    ],
)
def test_sonda_rendimiento_sin_valor(
    doble: Doble, crudo: ke.Crudo, esc: Escenario, respuesta: ke.Respuesta, categoria: str
) -> None:
    def con_latencia(metodo: str, url: str, cuerpo: bytes | None) -> ke.Respuesta:
        doble.t += 1.0
        return respuesta

    doble.http_manejador = con_latencia
    r = ke.sonda_rendimiento(doble.entorno(), crudo, cfg_de(esc))
    assert (r.estado, r.categoria, dict(r.valores)) == (ke.ERROR, categoria, {})


def test_sonda_rendimiento_acepta_el_minimo_de_tokens_y_falla_si_falla_la_ultima(
    doble: Doble, crudo: ke.Crudo, esc: Escenario
) -> None:
    doble.tokens_generados = ke.MIN_TOKENS_RENDIMIENTO
    assert ke.sonda_rendimiento(doble.entorno(), crudo, cfg_de(esc)).estado == ke.MEDIDO
    n = 0

    def tercera_falla(metodo: str, url: str, cuerpo: bytes | None) -> ke.Respuesta | None:
        nonlocal n
        n += 1
        return ke.Respuesta("ok", 500, b"") if n == 3 else None

    doble.http_manejador = tercera_falla
    r = ke.sonda_rendimiento(doble.entorno(), crudo, cfg_de(esc))
    assert (r.estado, r.categoria, dict(r.valores)) == (ke.ERROR, "respuesta_inesperada", {})


def test_sonda_rendimiento_sin_tiempo_medido_no_inventa_una_tasa(
    doble: Doble, crudo: ke.Crudo, esc: Escenario
) -> None:
    doble.latencia = 0.0
    r = ke.sonda_rendimiento(doble.entorno(), crudo, cfg_de(esc))
    assert (r.estado, r.categoria) == (ke.ERROR, "salida_ilegible")


@pytest.mark.parametrize("max_tokens", [16384, 8192])
def test_sonda_rechazo_registra_codigo_marcadores_y_hash_pero_no_el_texto(
    doble: Doble, crudo: ke.Crudo, esc: Escenario, max_tokens: int
) -> None:
    r = ke.sonda_rechazo(doble.entorno(), crudo, cfg_de(esc), max_tokens)
    cuerpo = json.dumps({"error": {"message": RECHAZO_400, "type": "BadRequestError", "code": 400}}).encode()
    assert r.valores == {
        "max_tokens": max_tokens,
        "http_control": 200,
        "http": 400,
        "marcadores": {"contextwindowexceedederror": False, "maximum_context_length": True},
        "rechazado": True,
        "cuerpo_sha256": hashlib.sha256(cuerpo).hexdigest(),
        "cuerpo_bytes": len(cuerpo),
    }
    assert POISON_ERROR not in json.dumps(dict(r.valores))
    (_, _, control), (_, _, largo) = doble.peticiones
    assert control is not None and largo is not None
    p_control, p_largo = json.loads(control), json.loads(largo)
    assert p_control["messages"][0]["content"] == ke.PROMPT_CONTROL
    assert p_control["max_tokens"] == p_largo["max_tokens"] == max_tokens
    # el prompt largo tiene mas palabras que tokens caben en el contexto
    assert len(p_largo["messages"][0]["content"].split()) == ke.PALABRAS_RELLENO > ke.CONTEXTO_MAXIMO
    # el texto exacto queda en el volcado crudo
    assert RECHAZO_400 in (crudo.raiz / f"002_rechazo_{max_tokens}_cuerpo.txt").read_text(encoding="utf-8")


def respuestas_de_rechazo(doble: Doble, control: ke.Respuesta | None, largo: ke.Respuesta | None) -> None:
    def manejar(metodo: str, url: str, cuerpo: bytes | None) -> ke.Respuesta | None:
        assert cuerpo is not None
        es_largo = len(cuerpo) > 100_000
        return largo if es_largo else control

    doble.http_manejador = manejar


@pytest.mark.parametrize(
    ("codigo", "cuerpo", "rechazado", "marcadores"),
    [
        (400, b"litellm.ContextWindowExceededError: demasiado", True, (True, False)),
        (400, b"MAXIMUM CONTEXT LENGTH is 32768", True, (False, True)),
        (400, b'{"error": "otra cosa"}', False, (False, False)),
        (200, b'{"choices": []}', False, (False, False)),
        (413, b"maximum context length", False, (False, True)),
        (500, b"", False, (False, False)),
    ],
)
def test_sonda_rechazo_solo_llama_rechazo_a_un_400_con_marcador(
    doble: Doble,
    crudo: ke.Crudo,
    esc: Escenario,
    codigo: int,
    cuerpo: bytes,
    rechazado: bool,
    marcadores: Any,
) -> None:
    respuestas_de_rechazo(doble, None, ke.Respuesta("ok", codigo, cuerpo))
    r = ke.sonda_rechazo(doble.entorno(), crudo, cfg_de(esc), 16384)
    assert r.estado == ke.MEDIDO
    assert (r.valores["http"], r.valores["rechazado"]) == (codigo, rechazado)
    assert tuple(r.valores["marcadores"].values()) == marcadores


@pytest.mark.parametrize(
    ("control", "largo", "categoria", "peticiones"),
    [
        (ke.Respuesta("ok", 400, RECHAZO_400.encode()), None, "control_fallo", 1),
        (ke.Respuesta("ok", 500, b""), None, "control_fallo", 1),
        (ke.Respuesta("sin_conexion", None, b""), None, "sin_conexion", 1),
        (ke.Respuesta("tiempo_agotado", None, b""), None, "tiempo_agotado", 1),
        (None, ke.Respuesta("sin_conexion", None, b""), "sin_conexion", 2),
        (None, ke.Respuesta("tiempo_agotado", None, b""), "tiempo_agotado", 2),
    ],
)
def test_sonda_rechazo_sin_valor(
    doble: Doble, crudo: ke.Crudo, esc: Escenario, control: Any, largo: Any, categoria: str, peticiones: int
) -> None:
    respuestas_de_rechazo(doble, control, largo)
    r = ke.sonda_rechazo(doble.entorno(), crudo, cfg_de(esc), 16384)
    assert (r.estado, r.categoria, dict(r.valores)) == (ke.ERROR, categoria, {})
    assert len(doble.peticiones) == peticiones


# ---------------------------------------------------------------------------
# Sonda del agente
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("error", "clase"),
    [
        (None, "ninguno"),
        ("Agent exceeded session timeout (5.0 min)", "agente"),
        ("Agent completed execution without calling submit_patch.", "agente"),
        ("Failed to apply agent patch: x", "agente"),
        ("Test failures/errors recorded in JUnit XML (2)", "agente"),
        ("Sandbox execution error: litellm.ContextWindowExceededError: x", "rechazo_contexto"),
        ("Sandbox execution error: This model's MAXIMUM context length is 32768", "rechazo_contexto"),
        ("Sandbox execution error: AdapterNotFoundError", "infraestructura"),
        ("Snapshot file not found: /kaggle/x.tgz", "infraestructura"),
        ("Evaluation error: x", "infraestructura"),
        ("Unexpected evaluation worker error: x", "infraestructura"),
        ("Missing test specification", "verificacion"),
        ("Failed to apply test_patch: x", "verificacion"),
        ("maximum context length", "sin_categoria"),  # sin el prefijo del sandbox no es un rechazo
        ("Evaluation error: maximum context length", "infraestructura"),
        ("texto nuevo del arnes", "sin_categoria"),
        ("", "sin_categoria"),
        (7, "sin_categoria"),
    ],
)
def test_clasificar_error(error: Any, clase: str) -> None:
    assert ke.clasificar_error(error) == clase


def test_comando_agente_lleva_los_limites_de_a0(doble: Doble, crudo: ke.Crudo, esc: Escenario) -> None:
    r = agente(doble, crudo, esc)
    assert doble.comandos[0] == [
        "/usr/bin/python3",
        "-m",
        "swegemma.cli",
        "eval",
        "--tasks",
        str(esc.tasks),
        "--snapshots-dir",
        str(esc.snapshots),
        "--results-dir",
        str(crudo.raiz / "agente_16384"),
        "--submission-dir",
        str(esc.envio),
        "--sandbox",
        "subprocess",
        "--task-ids",
        *ELEGIDAS,
        "--concurrency",
        "1",
        "--max-time-minutes",
        "5",
        "--max-tool-calls",
        "40",
        "--max-turns",
        "100",
        "--timeout-seconds",
        "60",
        "--display",
        "quiet",
    ]
    publico = r.comandos[0]
    assert publico.count("<tarea>") == 4
    assert not any(i in json.dumps(publico) for i in ELEGIDAS)
    assert str(esc.raiz) not in json.dumps(publico)
    variables = doble.variables_de["agente"]
    assert variables is not None
    assert variables["MODEL_PROXY_URL"] == "http://127.0.0.1:8000/v1"
    assert variables["LITELLM_LOCAL_MODEL_COST_MAP"] == "True"


def test_comando_agente_con_docker_pasa_la_imagen(esc: Escenario) -> None:
    tokens = ke.comando_agente(
        "python",
        tasks=esc.tasks,
        snapshots=esc.snapshots,
        resultados=esc.crudo,
        envio=esc.envio,
        backend="docker",
        imagen="tercero/imagen:1",
        ids=ELEGIDAS,
    )
    argv = ke.real(tokens)
    assert argv[argv.index("--sandbox") + 1 : argv.index("--task-ids")] == [
        "docker",
        "--image",
        "tercero/imagen:1",
    ]
    assert "tercero" not in json.dumps(ke.publico(tokens))


@pytest.mark.parametrize(
    ("error", "categoria"),
    [
        ("Sandbox execution error: AdapterNotFoundError main_lora", "infraestructura_arnes"),
        ("Snapshot file not found: x", "infraestructura_arnes"),
        ("Evaluation error: x", "infraestructura_arnes"),
        (f"texto nuevo {POISON_ERROR}", "error_sin_categoria"),
    ],
)
def test_sonda_agente_no_da_turnos_si_el_agente_no_corrio(
    doble: Doble, crudo: ke.Crudo, esc: Escenario, error: str, categoria: str
) -> None:
    doble.error_extra[16384] = error
    r = agente(doble, crudo, esc)
    assert (r.estado, r.categoria, dict(r.valores)) == (ke.ERROR, categoria, {})


@pytest.mark.parametrize(
    ("salida", "estado", "categoria"),
    [
        (ke.Salida("ausente", None, "", ""), ke.NO_DISPONIBLE, "comando_ausente"),
        (ke.Salida("tiempo_agotado", None, "", ""), ke.ERROR, "tiempo_agotado"),
        (ke.Salida("ok", 1, "", POISON_LOG), ke.ERROR, "comando_fallo"),
        (ke.Salida("ok", 0, "", ""), ke.ERROR, "salida_ilegible"),  # termino sin dejar resultados
    ],
)
def test_sonda_agente_sin_valor_si_el_comando_no_sirve(
    doble: Doble, crudo: ke.Crudo, esc: Escenario, salida: ke.Salida, estado: str, categoria: str
) -> None:
    doble.manejadores["agente"] = lambda argv: salida
    r = agente(doble, crudo, esc)
    assert (r.estado, r.categoria, dict(r.valores)) == (estado, categoria, {})


def test_leer_turnos_exige_una_fila_por_tarea(tmp_path: Path) -> None:
    ruta = tmp_path / "task_results.jsonl"

    def escribir(filas: list[Any]) -> None:
        ruta.write_text("\n".join(json.dumps(f) for f in filas) + "\n\n", encoding="utf-8")

    fila = {"instance_id": "a", "total_llm_calls": 4, "error": None, "resolved": True}
    escribir([fila, {**fila, "instance_id": "b", "total_llm_calls": 0}])
    assert ke.leer_turnos(ruta, ["a", "b"]) == ([0, 4], {"ninguno": 2})
    assert ke.leer_turnos(ruta, ["a", "b", "c"]) is None  # falta una
    assert ke.leer_turnos(ruta, ["a"]) is None  # sobra una
    escribir([fila, fila])
    assert ke.leer_turnos(ruta, ["a"]) is None  # repetida
    for malo in (-1, 2.0, True, None, "4"):
        escribir([{**fila, "total_llm_calls": malo}])
        assert ke.leer_turnos(ruta, ["a"]) is None, malo
    escribir([{"total_llm_calls": 4}])
    assert ke.leer_turnos(ruta, ["a"]) is None
    escribir([[1, 2]])
    assert ke.leer_turnos(ruta, ["a"]) is None
    ruta.write_text("{no es json\n", encoding="utf-8")
    assert ke.leer_turnos(ruta, ["a"]) is None
    assert ke.leer_turnos(tmp_path / "no_existe", ["a"]) is None


def test_leer_turnos_no_conserva_resolved() -> None:
    fila = ke._solo_turnos(
        [("instance_id", "a"), ("resolved", True), ("total_llm_calls", 3), ("error", None)]
    )
    assert fila == {"instance_id": "a", "total_llm_calls": 3, "error": None}
    assert ke._solo_identidad([("instance_id", "a"), ("patch", POISON_PARCHE), ("repo", "r")]) == {
        "instance_id": "a",
        "repo": "r",
    }


def test_segundo_candidato_corre_sobre_una_copia_con_ese_unico_cambio(
    doble: Doble, crudo: ke.Crudo, esc: Escenario
) -> None:
    r = agente(doble, crudo, esc, 8192)
    assert r.valores["max_output_tokens"] == 8192 and r.valores["turnos_por_tarea"] == [6, 6, 6, 6]
    copia = crudo.raiz / "envio_8192"
    assert doble.comandos[0][doble.comandos[0].index("--submission-dir") + 1] == str(copia)
    assert (copia / ke.ARCHIVO_MUESTREO).read_text(encoding="utf-8") == MUESTREO.replace("16384", "8192")
    assert (esc.envio / ke.ARCHIVO_MUESTREO).read_text(encoding="utf-8") == MUESTREO  # el kit no se toca
    otros = sorted(p.relative_to(esc.envio).as_posix() for p in esc.envio.rglob("*") if p.is_file())
    assert sorted(p.relative_to(copia).as_posix() for p in copia.rglob("*") if p.is_file()) == otros
    assert (copia / "agent.yaml").read_bytes() == (esc.envio / "agent.yaml").read_bytes()


@pytest.mark.parametrize(
    "muestreo",
    [
        "temperature: 0.2\n",
        "max_output_tokens: 16384\nmax_output_tokens: 16384\n",
        "max_output_tokens: 4096\n",
    ],
)
def test_segundo_candidato_exige_el_valor_del_kit_una_sola_vez(
    doble: Doble, crudo: ke.Crudo, esc: Escenario, muestreo: str
) -> None:
    (esc.envio / ke.ARCHIVO_MUESTREO).write_text(muestreo, encoding="utf-8")
    r = agente(doble, crudo, esc, 8192)
    assert (r.estado, r.categoria) == (ke.ERROR, "entrada_inesperada")
    assert doble.comandos == []  # no se corre nada con un envio que no se pudo construir


def test_preparar_envio_sin_archivo_de_muestreo(crudo: ke.Crudo, esc: Escenario) -> None:
    (esc.envio / ke.ARCHIVO_MUESTREO).unlink()
    assert ke.preparar_envio(esc.envio, crudo, 8192) is None
    assert ke.preparar_envio(esc.envio, crudo, 16384) == esc.envio


# ---------------------------------------------------------------------------
# Lo versionable: argumentos, cadenas y la ultima barrera
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "arg",
    [
        "/kaggle/input/x",
        "/usr/bin/python3",
        "C:\\Users\\x",
        "c:/datos",
        "~/modelo",
        "\\\\servidor\\x",
        "--model=/kaggle/input/tercero",
        "x=/tmp/y",
        "datos/kaggle/input",
        "uno\ndos",
        "uno\rdos",
        "a" * 201,
    ],
)
def test_argumento_que_parece_ruta_no_se_publica(arg: str) -> None:
    assert not ke.argumento_publicable(arg)
    assert ke.publico([arg]) == ("<oculto>",)
    assert ke.publico([ke.Oculto("valor", arg)]) == ("<oculto>",)


@pytest.mark.parametrize(
    "arg",
    [
        "--port",
        "8000",
        '{"reasoning_start_str": "<|channel>", "reasoning_end_str": "<channel|>"}',
        "{{.Id}}",
        "a" * 200,
        "0.9",
    ],
)
def test_argumento_literal_se_publica(arg: str) -> None:
    assert ke.argumento_publicable(arg)
    assert ke.publico([arg]) == (arg,)


def test_oculto_publica_la_etiqueta_y_ejecuta_el_valor() -> None:
    tokens: list[ke.Token] = ["cmd", ke.Oculto("/kaggle/input/secreto", "<modelo>")]
    assert ke.real(tokens) == ["cmd", "/kaggle/input/secreto"]
    assert ke.publico(tokens) == ("cmd", "<modelo>")


@pytest.mark.parametrize(
    "texto",
    [
        POISON_LOG + "!",
        "linea uno\nlinea dos",
        "/kaggle/input/tercero",
        "datos/kaggle/tercero",
        "a" * 81,
        "",
        " espacio al inicio",
        "ruta\\con\\barras",
        "comilla'simple",
        'comilla"doble',
        "subir/../salir",
        "doble//barra",
        "punto;coma",
        "Traceback (most recent call last):\n  File",
        3,
        None,
    ],
)
def test_texto_no_seguro(texto: Any) -> None:
    assert not ke.texto_seguro(texto)


@pytest.mark.parametrize(
    "texto",
    ["0.19.1", "NVIDIA L4", "cherrera0001/ensayo-a0 v1", "gemma-4-31b-it-qat-w4a16-ct@2", "a" * 80, "f" * 64],
)
def test_texto_seguro(texto: str) -> None:
    assert ke.texto_seguro(texto)


@pytest.mark.parametrize(
    "obj",
    [
        {"x": "linea\nde log"},
        {"x": [1, {"y": "/kaggle/input/tercero"}]},
        {"x": float("nan")},
        {"x": float("inf")},
        {"clave con\nsalto": 1},
        {3: 1},
        {"x": b"bytes"},
        {"x": {1, 2}},
        {"comandos": [["docker", "run", "/kaggle/input/tercero"]]},
        {"comandos": "docker run"},
        {"comandos": ["docker"]},
        {"comandos": [["docker", 3]]},
        "Traceback (most recent call last)\n",
    ],
)
def test_comprobar_versionable_detiene_lo_que_no_puede_versionarse(obj: Any) -> None:
    with pytest.raises(RuntimeError):
        ke.comprobar_versionable(obj)


def test_comprobar_versionable_admite_lo_tipado() -> None:
    ke.comprobar_versionable(
        {
            "a": True,
            "b": 3,
            "c": 2.5,
            "d": None,
            "e": ["0.19.1", {"f": "NVIDIA L4"}],
            "comandos": [["docker", "info", "--format", "{{.ServerVersion}}"], ["<python>", "-c"]],
        }
    )


# ---------------------------------------------------------------------------
# Archivos
# ---------------------------------------------------------------------------


def test_escribir_sin_sobrescribir(tmp_path: Path) -> None:
    destino = tmp_path / "sub" / "registro.json"
    ke.escribir_sin_sobrescribir(destino, b"uno")
    with pytest.raises(ke.EnsayoError, match="no sobrescribe"):
        ke.escribir_sin_sobrescribir(destino, b"dos")
    assert destino.read_bytes() == b"uno"
    assert [p.name for p in destino.parent.iterdir()] == ["registro.json"]  # sin temporales


def test_escribir_sin_sobrescribir_sin_enlaces_duros(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def sin_enlaces(origen: Any, destino: Any) -> None:
        raise OSError("este sistema de archivos no enlaza")

    monkeypatch.setattr(ke.os, "link", sin_enlaces)
    destino = tmp_path / "registro.json"
    ke.escribir_sin_sobrescribir(destino, b"uno")
    assert destino.read_bytes() == b"uno"
    assert [p.name for p in tmp_path.iterdir()] == ["registro.json"]


def test_a_json_usa_saltos_lf_y_termina_en_salto() -> None:
    datos = ke.a_json({"a": [1, 2], "ñ": "x"})
    assert b"\r" not in datos and datos.endswith(b"}\n") and "ñ".encode() in datos


def test_crudo_no_sobrescribe_y_numera(tmp_path: Path) -> None:
    c = ke.Crudo(tmp_path / "crudo")
    c.crear()
    c.guardar("a.txt", "uno")
    c.guardar("a.txt", b"dos")
    assert sorted(p.name for p in c.raiz.iterdir()) == ["001_a.txt", "002_a.txt"]
    with pytest.raises(FileExistsError):
        c.crear()


def test_crudo_existente_o_versionable_se_rechaza(tmp_path: Path, doble: Doble) -> None:
    ent = doble.entorno()
    ke.comprobar_crudo(tmp_path / "nuevo", ent)  # fuera de todo repositorio: sin consultar a git
    assert doble.comandos == []
    (tmp_path / "ya").mkdir()
    with pytest.raises(ke.EnsayoError, match="Ya existe"):
        ke.comprobar_crudo(tmp_path / "ya", ent)
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    ke.comprobar_crudo(repo / "data" / "crudo", ent)  # git dice que esta ignorada (codigo 0)
    assert doble.comandos[-1][:4] == ["git", "-C", str(repo.resolve()), "check-ignore"]
    doble.manejadores["git"] = lambda argv: ke.Salida("ok", 1, "", "")
    with pytest.raises(ke.EnsayoError, match="no la ignora"):
        ke.comprobar_crudo(repo / "crudo", ent)
    for salida in (ke.Salida("ok", 128, "", ""), ke.Salida("ausente", None, "", "")):
        doble.manejadores["git"] = lambda argv, s=salida: s
        with pytest.raises(ke.EnsayoError, match="No se pudo comprobar"):
            ke.comprobar_crudo(repo / "crudo", ent)
    (tmp_path / "archivo").write_text("x", encoding="utf-8")
    with pytest.raises(ke.EnsayoError, match="no es un directorio"):
        ke.comprobar_crudo(tmp_path / "archivo" / "crudo", ent)


# ---------------------------------------------------------------------------
# Registro de la compuerta
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# La compuerta acepta el registro producido y rechaza uno alterado
# ---------------------------------------------------------------------------


def test_la_compuerta_acepta_el_registro_de_una_corrida_sintetica(
    esc: Escenario, doble: Doble, tmp_path: Path
) -> None:
    assert correr_main(esc, doble) == ke.EXIT_OK
    res = compuerta(tmp_path, esc.salida.read_bytes())
    assert res.problemas == []
    assert res.pendientes == ["no se comprobo el versionado en git (--sin-git)"]


def alterar(datos: bytes, **cambios: Any) -> bytes:
    registro = json.loads(datos)
    for k, v in cambios.items():
        if v is ...:
            del registro[k]
        else:
            registro[k] = v
    return ke.a_json(registro)


def test_la_compuerta_acepta_el_minimo_viable(esc: Escenario, doble: Doble, tmp_path: Path) -> None:
    """Control de la prueba anterior: 5 turnos en la mitad de las tareas todavia es viable."""
    assert correr_main(esc, doble) == ke.EXIT_OK
    datos = alterar(esc.salida.read_bytes(), turnos_por_tarea=[0, 0, 5, 5])
    assert compuerta(tmp_path, datos).problemas == []


def test_la_compuerta_rechaza_un_registro_cuyo_hash_no_coincide(
    esc: Escenario, doble: Doble, tmp_path: Path
) -> None:
    assert correr_main(esc, doble) == ke.EXIT_OK
    datos = esc.salida.read_bytes()
    assert compuerta(tmp_path, datos).problemas == []
    (tmp_path / "repo" / RUTA_REGISTRO).write_bytes(
        datos.replace(b'"turnos_por_tarea"', b'"turnos_por_tarea" ')
    )
    params = kaggle_prereg.load_params(kaggle_prereg.DEFAULT_PARAMS)
    params["abiertos"]["ensayo_notebook"]["valor"] = {
        "ruta": RUTA_REGISTRO,
        "sha256": hashlib.sha256(datos).hexdigest(),
    }
    res = kaggle_prereg.check_closed(params, tmp_path / "repo")
    assert len(res.problemas) == 1 and "SHA-256" in res.problemas[0]


# ---------------------------------------------------------------------------
# main() de punta a punta
# ---------------------------------------------------------------------------


def test_ninguna_cadena_envenenada_llega_a_lo_versionable(esc: Escenario, doble: Doble) -> None:
    doble.rechazos_agente[16384] = 1
    doble.paquetes["docker"] = "7.1.0"
    docker_con(doble, version=Doble.ok(f"Docker {POISON_LOG}"))
    assert correr_main(esc, doble, "--imagen", "tercero/imagen-privada:1") == ke.EXIT_OK
    crudos = esc.crudos()
    for veneno in POISON_TODOS:
        # control: el veneno si paso por el guion (esta en el volcado crudo o en tasks.jsonl)...
        assert veneno in crudos or veneno in esc.tasks.read_text(encoding="utf-8"), veneno
        # ...y no llego a ningun archivo versionable
        assert veneno not in esc.versionables(), veneno
    for veneno in (POISON_LOG, POISON_ERROR, POISON_RESPUESTA):
        assert veneno in crudos, veneno
    versionables = esc.versionables()
    for privado in (
        str(esc.raiz),
        esc.raiz.name,
        "kaggle/input",
        "tercero",
        "maximum context length is",
        *IDS_REQUESTS,
        ID_HTTPX,
    ):
        assert privado not in versionables, privado
    assert "<tarea>" in versionables and "<modelo>" in versionables and "<imagen>" in versionables
    ke.comprobar_versionable(json.loads(esc.informe.read_text(encoding="utf-8")))


def test_plan_y_corrida_nombran_las_mismas_sondas(esc: Escenario, doble: Doble) -> None:
    assert correr_main(esc, doble) == ke.EXIT_OK
    args = ke._parser().parse_args(esc.args())
    assert [p.sonda for p in ke.plan(args)] == list(esc.sondas())
    assert len({p.sonda for p in ke.plan(args)}) == len(ke.plan(args))


def test_plan_no_ejecuta_nada(esc: Escenario, capsys: pytest.CaptureFixture[str]) -> None:
    def prohibido(*a: Any, **k: Any) -> Any:
        raise AssertionError("--plan no debe tocar el sistema")

    ent = ke.Entorno(
        ejecutar=prohibido,
        lanzar=prohibido,
        http=prohibido,
        reloj=prohibido,
        dormir=prohibido,
        ahora=prohibido,
        version_paquete=prohibido,
        leer_texto=prohibido,
        disco_libre=prohibido,
        cpus=prohibido,
        variables={},
        python="python",
        version_python="3.12.3",
    )
    codigo = ke.main(esc.args("--plan", sin=("--crudo", "--salida", "--informe")), entorno=ent)
    assert codigo == ke.EXIT_OK
    salida = capsys.readouterr().out
    assert "no se ha ejecutado nada" in salida
    for nombre in ("docker", "servidor", "rendimiento", "rechazo_sintetico:8192", "agente:16384", "limpieza"):
        assert f". {nombre} [" in salida
    assert "vllm.entrypoints.openai.api_server" in salida and "--gpu-memory-utilization 0.9" in salida
    assert "--max-time-minutes 5 --max-tool-calls 40 --max-turns 100 --timeout-seconds 60" in salida
    assert str(esc.raiz) not in salida and "kaggle/input" not in salida
    assert not esc.crudo.exists() and not esc.salida.exists() and not esc.informe.exists()


def test_plan_solo_anfitrion_y_sin_agente(esc: Escenario) -> None:
    anfitrion = ke.plan(ke._parser().parse_args(esc.args("--solo-anfitrion")))
    assert not any(p.usa_gpu for p in anfitrion) and anfitrion[-1].sonda == "tareas"
    sin_agente = [p.sonda for p in ke.plan(ke._parser().parse_args(esc.args("--sin-agente")))]
    assert "agente:16384" not in sin_agente and "servidor" in sin_agente and sin_agente[-1] == "limpieza"


def test_main_sin_agente_no_escribe_registro_y_detiene_el_servidor(esc: Escenario, doble: Doble) -> None:
    assert correr_main(esc, doble, "--sin-agente") == ke.EXIT_INCOMPLETO
    assert not esc.salida.exists()
    sondas = esc.sondas()
    assert sondas["agente:16384"]["categoria"] == sondas["agente:8192"]["categoria"] == "no_solicitada"
    assert sondas["rendimiento"]["estado"] == ke.MEDIDO
    assert doble.tokens_vistos == [] and not doble.proceso.esta_vivo


def test_main_sin_directorio_del_modelo(esc: Escenario, doble: Doble) -> None:
    esc.modelo.rmdir()
    assert correr_main(esc, doble) == ke.EXIT_INCOMPLETO
    assert esc.sondas()["servidor"]["categoria"] == "entrada_ausente" and doble.lanzados == []


@pytest.mark.parametrize(
    "romper",
    ["kit_alterado", "compila_sin_medir", "tareas_ilegibles", "docker_sin_medir"],
)
def test_main_no_corre_el_agente_si_falta_una_condicion_de_a0(
    esc: Escenario, doble: Doble, romper: str
) -> None:
    if romper == "kit_alterado":
        (esc.envio / "agent.yaml").write_text("name: otro\n", encoding="utf-8")
    elif romper == "compila_sin_medir":
        doble.manejadores["compila"] = lambda argv: ke.Salida("tiempo_agotado", None, "", "")
    elif romper == "tareas_ilegibles":
        esc.tasks.write_text("{\n", encoding="utf-8")
    else:
        doble.manejadores["docker_version"] = lambda argv: ke.Salida("tiempo_agotado", None, "", "")
    assert correr_main(esc, doble) == ke.EXIT_INCOMPLETO
    assert doble.tokens_vistos == [] and not esc.salida.exists()
    assert esc.sondas()["agente:16384"]["categoria"] == "dependencia_no_medida"
    assert esc.sondas()["rendimiento"]["estado"] == ke.MEDIDO  # las demas sondas siguen
    assert not doble.proceso.esta_vivo


def test_main_con_sandbox_forzado_no_depende_de_la_sonda_de_docker(esc: Escenario, doble: Doble) -> None:
    doble.manejadores["docker_version"] = lambda argv: ke.Salida("tiempo_agotado", None, "", "")
    assert correr_main(esc, doble, "--sandbox", "subprocess") == ke.EXIT_INCOMPLETO  # falta docker_disponible
    assert doble.tokens_vistos == [16384]
    assert esc.sondas()["agente:16384"]["valores"]["backend"] == "subprocess"


def test_main_con_docker_utilizable_usa_el_backend_docker(
    esc: Escenario, doble: Doble, tmp_path: Path
) -> None:
    doble.paquetes["docker"] = "7.1.0"
    docker_con(doble, version=Doble.ok("Docker 27"))
    assert correr_main(esc, doble) == ke.EXIT_OK
    registro = json.loads(esc.salida.read_text(encoding="utf-8"))
    assert (registro["docker_disponible"], registro["backend"]) == (True, "docker")
    comando = next(c for c in doble.comandos if Doble.tipo(c) == "agente")
    assert comando[comando.index("--sandbox") + 1] == "docker"
    assert comando[comando.index("--image") + 1] == "swebench-sandbox:latest"
    assert compuerta(tmp_path, esc.salida.read_bytes()).problemas == []


def test_main_una_sonda_que_falla_no_aborta_las_demas(esc: Escenario, doble: Doble) -> None:
    def revienta(argv: list[str]) -> ke.Salida:
        raise RuntimeError(POISON_LOG)

    doble.manejadores["nvidia_gpu"] = revienta
    doble.meminfo = None
    assert correr_main(esc, doble) == ke.EXIT_OK  # ni la GPU ni la memoria estan en el registro
    sondas = esc.sondas()
    assert (sondas["gpu"]["estado"], sondas["gpu"]["categoria"]) == (ke.ERROR, "error_inesperado")
    assert (sondas["memoria"]["estado"], sondas["memoria"]["categoria"]) == (
        ke.NO_DISPONIBLE,
        "fuente_ausente",
    )
    assert sondas["agente:16384"]["estado"] == ke.MEDIDO and esc.salida.exists()
    assert POISON_LOG not in esc.versionables()


def test_main_infraestructura_en_el_agente_no_da_registro(esc: Escenario, doble: Doble) -> None:
    doble.error_extra[16384] = "Sandbox execution error: AdapterNotFoundError"
    assert correr_main(esc, doble) == ke.EXIT_INCOMPLETO
    assert not esc.salida.exists()
    sondas = esc.sondas()
    assert (sondas["agente:16384"]["estado"], sondas["agente:16384"]["categoria"]) == (
        ke.ERROR,
        "infraestructura_arnes",
    )
    assert sondas["agente:8192"]["categoria"] == "dependencia_no_medida"
    assert not doble.proceso.esta_vivo


def test_main_rechazos_con_segundo_candidato_fallido_no_da_registro(esc: Escenario, doble: Doble) -> None:
    doble.rechazos_agente[16384] = 1
    doble.error_extra[8192] = "Evaluation error: x"
    assert correr_main(esc, doble) == ke.EXIT_INCOMPLETO
    assert doble.tokens_vistos == [16384, 8192] and not esc.salida.exists()


# -- limpieza del servidor en caminos de error


def test_main_detiene_el_servidor_si_una_sonda_revienta(esc: Escenario, doble: Doble) -> None:
    def revienta(argv: list[str]) -> ke.Salida:
        raise RuntimeError(POISON_LOG)

    doble.manejadores["agente"] = revienta
    assert correr_main(esc, doble) == ke.EXIT_INCOMPLETO
    assert doble.proceso.eventos[0] == "terminar" and not doble.proceso.esta_vivo
    assert esc.sondas()["agente:16384"]["categoria"] == "error_inesperado"


def test_main_detiene_el_servidor_si_se_interrumpe(esc: Escenario, doble: Doble) -> None:
    def interrumpe(argv: list[str]) -> ke.Salida:
        raise KeyboardInterrupt

    doble.manejadores["agente"] = interrumpe
    with pytest.raises(KeyboardInterrupt):
        correr_main(esc, doble)
    assert doble.proceso.eventos[0] == "terminar" and not doble.proceso.esta_vivo
    assert not esc.salida.exists() and not esc.informe.exists()


def test_main_detiene_el_servidor_si_la_interrupcion_llega_durante_el_arranque(
    esc: Escenario, doble: Doble
) -> None:
    def interrumpe(metodo: str, url: str, cuerpo: bytes | None) -> ke.Respuesta:
        raise SystemExit(143)

    doble.http_manejador = interrumpe
    with pytest.raises(SystemExit):
        correr_main(esc, doble)
    assert len(doble.lanzados) == 1 and not doble.proceso.esta_vivo


def test_main_detiene_el_servidor_si_falla_la_escritura_final(
    esc: Escenario, doble: Doble, capsys: pytest.CaptureFixture[str]
) -> None:
    doble.ahora_falla = True
    assert correr_main(esc, doble) == ke.EXIT_INESPERADO
    assert not doble.proceso.esta_vivo
    err = capsys.readouterr().err
    assert "ERROR INESPERADO (RuntimeError) en test_kaggle_ensayo.py" in err and POISON_LOG not in err
    assert not esc.salida.exists() and not esc.informe.exists()


# -- salida 2: nada se sobrescribe y nada se lanza


@pytest.mark.parametrize("existente", ["salida", "informe", "crudo"])
def test_main_se_niega_a_sobrescribir(
    esc: Escenario, doble: Doble, existente: str, capsys: pytest.CaptureFixture[str]
) -> None:
    ruta: Path = getattr(esc, existente)
    if existente == "crudo":
        ruta.mkdir()
        (ruta / "previo.txt").write_text("previo", encoding="utf-8")
    else:
        ruta.write_text("previo", encoding="utf-8")
    assert correr_main(esc, doble) == ke.EXIT_INVALIDO
    assert doble.lanzados == [] and doble.comandos == [] and doble.peticiones == []
    if existente == "crudo":
        assert [p.name for p in ruta.iterdir()] == ["previo.txt"]
    else:
        assert ruta.read_text(encoding="utf-8") == "previo"
        assert not esc.crudo.exists()
    assert "ERROR: Ya existe" in capsys.readouterr().err


@pytest.mark.parametrize("cual", ["salida", "informe"])
def test_main_no_pisa_un_archivo_que_aparece_durante_el_ensayo(
    esc: Escenario, doble: Doble, cual: str
) -> None:
    """La comprobacion inicial no basta: la escritura final tampoco sobrescribe."""
    ruta: Path = getattr(esc, cual)
    original = doble._agente

    def aparece(argv: list[str]) -> ke.Salida:
        ruta.write_text("de otra sesion", encoding="utf-8")
        return original(argv)

    doble.manejadores["agente"] = aparece
    assert correr_main(esc, doble) == ke.EXIT_INVALIDO
    assert ruta.read_text(encoding="utf-8") == "de otra sesion"
    assert not doble.proceso.esta_vivo


def test_sigterm_se_convierte_en_una_salida_ordenada() -> None:
    import signal

    anterior = signal.getsignal(signal.SIGTERM)
    with pytest.raises(SystemExit) as info, ke._senales(True):
        assert signal.getsignal(signal.SIGTERM) is not anterior
        signal.raise_signal(signal.SIGTERM)
    assert info.value.code == 128 + signal.SIGTERM
    assert signal.getsignal(signal.SIGTERM) is anterior
    with ke._senales(False):
        assert signal.getsignal(signal.SIGTERM) is anterior


@pytest.mark.parametrize("falta", ["--salida", "--informe", "--crudo"])
def test_main_exige_las_tres_rutas_fuera_del_plan(esc: Escenario, doble: Doble, falta: str) -> None:
    assert correr_main(esc, doble, sin=(falta,)) == ke.EXIT_INVALIDO
    assert doble.lanzados == [] and doble.comandos == []


def test_main_rechaza_rutas_incoherentes(esc: Escenario, doble: Doble) -> None:
    dentro = str(esc.crudo / "registro.json")
    casos = [
        esc.args("--informe", str(esc.salida)),
        esc.args("--salida", dentro),
        esc.args("--informe", dentro),
        esc.args("--salida", str(esc.crudo)),
        esc.args("--puerto", "0"),
        esc.args("--puerto", "70000"),
        esc.args("--espera-servidor", "0"),
        esc.args("--espera-agente-min", "-1"),
    ]
    for argv in casos:
        assert ke.main(argv, entorno=doble.entorno()) == ke.EXIT_INVALIDO, argv[-2:]
    assert doble.lanzados == [] and not esc.crudo.exists()


def test_main_rechaza_un_crudo_versionable(
    esc: Escenario, doble: Doble, capsys: pytest.CaptureFixture[str]
) -> None:
    (esc.trabajo / ".git").mkdir()
    doble.manejadores["git"] = lambda argv: ke.Salida("ok", 1, "", "")
    assert correr_main(esc, doble) == ke.EXIT_INVALIDO
    assert "git no la ignora" in capsys.readouterr().err
    assert doble.lanzados == [] and not esc.crudo.exists()


def test_main_rechaza_un_adaptador_con_nombre_no_admitido(esc: Escenario, doble: Doble) -> None:
    malo = esc.envio / "adapters" / "nombre con espacio"
    malo.mkdir()
    (malo / "adapter_config.json").write_text("{}", encoding="utf-8")
    assert correr_main(esc, doble) == ke.EXIT_INVALIDO
    assert doble.lanzados == [] and not esc.crudo.exists()


def test_main_version_del_modelo(esc: Escenario, doble: Doble) -> None:
    assert correr_main(esc, doble, "--modelo-version", "7") == ke.EXIT_OK
    assert json.loads(esc.salida.read_text(encoding="utf-8"))["modelo"] == "gemma-4-31b-it-qat-w4a16-ct@7"


def test_main_sin_version_del_modelo_no_hay_registro(esc: Escenario, doble: Doble) -> None:
    otro = esc.modelo.parent / "ultima"
    esc.modelo.rename(otro)
    esc.modelo = otro
    assert correr_main(esc, doble) == ke.EXIT_INCOMPLETO
    assert esc.sondas()["modelo"]["categoria"] == "no_declarada" and not esc.salida.exists()


@pytest.mark.parametrize("sin", ["--notebook", "--sesion-max-horas", "--sesion-fuente"])
def test_main_sin_un_dato_declarado_no_hay_registro(esc: Escenario, doble: Doble, sin: str) -> None:
    assert correr_main(esc, doble, sin=(sin,)) == ke.EXIT_INCOMPLETO
    assert not esc.salida.exists() and esc.informe.exists()


def test_main_opcion_extra_del_servidor_cambia_el_hash_y_el_comando(esc: Escenario, doble: Doble) -> None:
    assert correr_main(esc, doble, "--servidor-arg=--dtype=bfloat16", "--puerto", "8123") == ke.EXIT_OK
    argv = doble.lanzados[0][0]
    assert argv[-1] == "--dtype=bfloat16" and argv[argv.index("--port") + 1] == "8123"
    registro = json.loads(esc.salida.read_text(encoding="utf-8"))
    cfg = cfg_de(esc, puerto=8123, extra=("--dtype=bfloat16",))
    assert (
        registro["guion_servidor_sha256"]
        == ke.hash_guion_servidor(cfg)
        != ke.hash_guion_servidor(cfg_de(esc))
    )
    assert all(u.startswith("http://127.0.0.1:8123/") for _, u, _ in doble.peticiones)


# ---------------------------------------------------------------------------
# Implementacion real: procesos triviales de Python, sin servidores ni red
# ---------------------------------------------------------------------------


def test_ejecutar_real() -> None:
    r = ke.ejecutar_real(
        [sys.executable, "-c", "import sys; print('hola'); sys.stderr.write('ay'); sys.exit(7)"], 60.0, None
    )
    assert (r.estado, r.codigo, r.stdout.strip(), r.stderr) == ("ok", 7, "hola", "ay")
    assert ke.ejecutar_real(["comando-que-no-existe-xyz"], 5.0, None) == ke.Salida("ausente", None, "", "")
    r = ke.ejecutar_real([sys.executable, "-c", "import time; time.sleep(60)"], 0.5, None)
    assert (r.estado, r.codigo) == ("tiempo_agotado", None)
    r = ke.ejecutar_real(
        [sys.executable, "-c", "import os; print(os.environ['ENSAYO_X'])"],
        60.0,
        {**ke.os.environ, "ENSAYO_X": "si"},
    )
    assert r.stdout.strip() == "si"


def test_proceso_real_se_detiene_con_la_guardia(tmp_path: Path) -> None:
    registro = tmp_path / "servidor.log"
    proceso = ke.lanzar_real(
        [sys.executable, "-c", "import time; print('arranco', flush=True); time.sleep(120)"],
        registro,
        dict(ke.os.environ),
    )
    guardia = ke.Guardia()
    guardia.asignar(proceso)
    try:
        assert proceso.vivo() and proceso.pid > 0
        assert guardia.detener() is True
        assert not proceso.vivo() and guardia.proceso is None
    finally:
        proceso.matar()
        proceso.esperar(10.0)
    assert registro.exists()
    with pytest.raises(FileExistsError):
        ke.lanzar_real([sys.executable, "-c", "pass"], registro, dict(ke.os.environ))  # el log no se pisa


def test_lanzar_real_sin_binario_no_deja_el_log_abierto(tmp_path: Path) -> None:
    with pytest.raises(OSError):
        ke.lanzar_real(["comando-que-no-existe-xyz"], tmp_path / "x.log", {})
    (tmp_path / "x.log").unlink()  # en Windows fallaria si el archivo siguiera abierto


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/health",
        "https://127.0.0.1:8000/health",
        "http://127.0.0.1.evil.test:80/",
        "http://localhost:8000/x",
    ],
)
def test_http_real_solo_habla_con_el_servidor_local(url: str) -> None:
    with pytest.raises(ValueError, match="servidor local"):
        ke.http_real("GET", url, None, 1.0)


def test_http_real_sin_servidor_es_sin_conexion() -> None:
    r = ke.http_real("GET", "http://127.0.0.1:9/health", None, 3.0)
    assert r.estado in ("sin_conexion", "tiempo_agotado") and r.codigo is None and r.cuerpo == b""


def test_entorno_real_lee_el_sistema(tmp_path: Path) -> None:
    ent = ke.entorno_real()
    assert ent.python == sys.executable
    assert ke.sonda_python(ent).estado == ke.MEDIDO
    assert ke.sonda_cpu(ent).estado == ke.MEDIDO
    assert ke.sonda_disco(ent, tmp_path).estado == ke.MEDIDO
    assert ent.disco_libre(str(tmp_path / "no" / "existe")) is None
    assert ent.leer_texto(str(tmp_path / "no_existe")) is None
    assert ent.version_paquete("paquete-que-no-existe-xyz") is None
    assert ke.sonda_version(ent, "pytest").estado == ke.MEDIDO
    assert math.isfinite(ent.reloj()) and ent.ahora().tzinfo is not None


def test_el_guion_es_un_solo_archivo_de_biblioteca_estandar() -> None:
    """Se sube suelto a un notebook: no puede importar nada del repositorio ni de terceros."""
    import ast

    arbol = ast.parse(Path(ke.__file__).read_text(encoding="utf-8"))
    modulos: set[str] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            modulos.update(a.name.split(".")[0] for a in nodo.names)
        elif isinstance(nodo, ast.ImportFrom):
            assert nodo.level == 0
            modulos.add((nodo.module or "").split(".")[0])
    assert modulos <= set(sys.stdlib_module_names), sorted(modulos - set(sys.stdlib_module_names))
    assert "scripts" not in modulos


# ===========================================================================
# Segunda ronda (revision del PR #119)
# ===========================================================================

# ---------------------------------------------------------------------------
# D1. Puerto ocupado: lo que contesta debe ser el servidor que lanzo el guion
# ---------------------------------------------------------------------------


def test_sonda_servidor_mide_los_segundos_hasta_la_primera_respuesta_200(
    doble: Doble, crudo: ke.Crudo, esc: Escenario
) -> None:
    doble.salud_tras = 4
    guardia = ke.Guardia()
    cfg = cfg_de(esc)
    r = ke.sonda_servidor(doble.entorno(), crudo, cfg, guardia, 60.0)
    # tres consultas fallidas, cada una seguida de una pausa de INTERVALO_SALUD, y la cuarta responde
    assert r.valores == {
        "arranca": True,
        "carga_segundos": 3 * ke.INTERVALO_SALUD,
        "guion_sha256": ke.hash_guion_servidor(cfg),
    }
    assert guardia.proceso is doble.proceso and guardia.lanzados == 1
    assert doble.proceso.eventos == []  # la sonda no lo detiene: lo usan las sondas siguientes
    argv, registro, variables = doble.lanzados[0]
    assert argv == ke.real(ke.comando_servidor("/usr/bin/python3", cfg))
    assert registro == crudo.ruta("servidor.log")
    assert variables["HF_HUB_OFFLINE"] == "1" and variables["VLLM_NO_USAGE_STATS"] == "1"
    assert variables["PYTHONUNBUFFERED"] == "1"  # el registro de accesos se lee con el servidor vivo
    # una consulta previa con el puerto libre y cuatro tras lanzar; todas con el tope de /health
    assert [u for _, u, _ in doble.peticiones] == ["http://127.0.0.1:8000/health"] * 5
    assert doble.esperas_http == [("health", ke.ESPERA_SALUD)] * 5
    assert r.comandos == (ke.publico(ke.comando_servidor("x", cfg)),)


@pytest.mark.parametrize(
    "previa",
    [
        ke.Respuesta("ok", 200, b""),
        ke.Respuesta("ok", 503, b""),
        ke.Respuesta("ok", 404, b""),
        ke.Respuesta("tiempo_agotado", None, b""),
        ke.Respuesta("protocolo", None, b""),
    ],
)
def test_sonda_servidor_con_el_puerto_ocupado_no_lanza_nada(
    doble: Doble, crudo: ke.Crudo, esc: Escenario, previa: ke.Respuesta
) -> None:
    """Si algo contesta ya en el puerto, un «arranca» posterior mediria a otro servidor."""
    doble.puerto_ocupado = previa
    doble.salud_tras = 1
    guardia = ke.Guardia()
    r = ke.sonda_servidor(doble.entorno(), crudo, cfg_de(esc), guardia, 60.0)
    assert (r.estado, r.categoria, dict(r.valores)) == (ke.ERROR, "puerto_ocupado", {})
    assert doble.lanzados == [] and guardia.proceso is None and guardia.lanzados == 0
    assert len(doble.peticiones) == 1


def test_sonda_servidor_no_cuenta_un_200_si_el_proceso_lanzado_ya_murio(
    doble: Doble, crudo: ke.Crudo, esc: Escenario
) -> None:
    """Doble del revisor: /health responde a la primera y el proceso muere justo entonces."""
    doble.salud_tras = 1
    doble.proceso = ProcesoFalso(muere_tras=1)
    guardia = ke.Guardia()
    r = ke.sonda_servidor(doble.entorno(), crudo, cfg_de(esc), guardia, 60.0)
    assert (r.estado, r.categoria, dict(r.valores)) == (ke.ERROR, "puerto_ocupado", {})
    assert guardia.proceso is doble.proceso  # lo lanzado queda a cargo de la guardia


def test_main_con_el_puerto_ocupado_no_da_registro(esc: Escenario, doble: Doble) -> None:
    doble.puerto_ocupado = ke.Respuesta("ok", 200, b"")
    doble.salud_tras = 1
    assert correr_main(esc, doble) == ke.EXIT_INCOMPLETO
    assert doble.lanzados == [] and not esc.salida.exists()
    sondas = esc.sondas()
    assert (sondas["servidor"]["estado"], sondas["servidor"]["categoria"]) == (ke.ERROR, "puerto_ocupado")
    assert sondas["rendimiento"]["categoria"] == "dependencia_no_medida"
    assert "limpieza" not in sondas


# ---------------------------------------------------------------------------
# D2. Parada: siempre se mata al grupo, y se comprueba el grupo
# ---------------------------------------------------------------------------

PARADA_COMPLETA = ["terminar", f"esperar:{ke.GRACIA_TERMINAR:g}", "matar", f"esperar:{ke.GRACIA_MATAR:g}"]


def test_guardia_mata_siempre_al_grupo_aunque_el_lider_termine() -> None:
    guardia = ke.Guardia()
    assert guardia.detener() is True  # sin proceso no hay nada que hacer
    p = ProcesoFalso()  # el lider obedece a ``terminar``; sus hijos solo mueren con ``matar``
    guardia.asignar(p)
    assert guardia.detener() is True
    assert p.eventos == PARADA_COMPLETA
    assert not p.hijos_vivos and guardia.proceso is None
    assert guardia.detener() is True and p.eventos == PARADA_COMPLETA  # idempotente


def test_guardia_no_da_por_detenido_un_grupo_con_hijos_vivos() -> None:
    guardia = ke.Guardia()
    p = ProcesoFalso(obedece_matar=False)  # el lider muere con ``terminar``, pero los hijos siguen
    guardia.asignar(p)
    assert guardia.detener() is False
    assert not p.esta_vivo and p.hijos_vivos and guardia.proceso is p


def test_main_detiene_al_grupo_entero(esc: Escenario, doble: Doble) -> None:
    assert correr_main(esc, doble) == ke.EXIT_OK
    assert doble.proceso.eventos == PARADA_COMPLETA
    assert not doble.proceso.esta_vivo and not doble.proceso.hijos_vivos


@pytest.mark.parametrize(
    ("proceso", "en_gpu", "aviso"),
    [
        (ProcesoFalso(pid=777, obedece_terminar=False, obedece_matar=False), "", "pid 777"),
        (ProcesoFalso(pid=778, obedece_matar=False), "", "pid 778"),  # lider muerto, hijos vivos
        (ProcesoFalso(), "901\n902\n903\n904\n", "quedan 4 procesos usando la GPU"),
    ],
)
def test_main_sin_limpieza_correcta_no_escribe_registro(
    esc: Escenario,
    doble: Doble,
    capsys: pytest.CaptureFixture[str],
    proceso: ProcesoFalso,
    en_gpu: str,
    aviso: str,
) -> None:
    """Un vLLM vivo o procesos en la GPU tras detener: ni salida 0 ni registro «completo»."""
    doble.proceso = proceso
    doble.manejadores["nvidia_apps"] = lambda argv: ke.Salida("ok", 0, en_gpu, "")
    assert correr_main(esc, doble) == ke.EXIT_INCOMPLETO
    assert not esc.salida.exists()
    err = capsys.readouterr().err
    assert aviso in err and "limpieza" in err
    informe = json.loads(esc.informe.read_text(encoding="utf-8"))
    assert informe["registro"] == {"clase": "ninguno", "faltan": 1}
    limpieza = esc.sondas()["limpieza"]["valores"]
    assert limpieza["procesos_en_gpu"] == len(en_gpu.split())
    assert limpieza["servidor_detenido"] is (en_gpu != "")
    assert informe["servidor_detenido"] is (en_gpu != "")
    assert esc.sondas()["agente:16384"]["estado"] == ke.MEDIDO  # lo medido queda en el informe


def test_limpieza_correcta() -> None:
    def con(**valores: Any) -> ke.Resultado:
        return ke.Resultado("limpieza", ke.medido(valores), 0.0)

    assert ke.limpieza_correcta(None) is True  # no se lanzo nada
    assert ke.limpieza_correcta(con(servidor_detenido=True, procesos_en_gpu=0)) is True
    assert ke.limpieza_correcta(con(servidor_detenido=True)) is True  # sin nvidia-smi no hay conteo
    assert ke.limpieza_correcta(con(servidor_detenido=True, procesos_en_gpu=1)) is False
    assert ke.limpieza_correcta(con(servidor_detenido=False, procesos_en_gpu=0)) is False
    roto = ke.Resultado("limpieza", ke.sin_valor(ke.ERROR, "error_inesperado"), 0.0)
    assert ke.limpieza_correcta(roto) is False


# Escribe un byte cada 50 ms durante dos minutos como mucho: si una prueba falla, no queda para siempre.
LATIDO = (
    "import sys, time\nfor _ in range(2400):\n    open(sys.argv[1], 'a').write('x')\n    time.sleep(0.05)\n"
)
PADRE = (
    "import subprocess, sys, time\n"
    f"subprocess.Popen([sys.executable, '-c', {LATIDO!r}, sys.argv[1]], "
    "stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
    "time.sleep(float(sys.argv[2]))\n"
)


def late(ruta: Path) -> bool:
    """Si el proceso que escribe en ``ruta`` sigue vivo: el archivo crece en medio segundo."""
    antes = ruta.stat().st_size if ruta.exists() else 0
    time.sleep(0.5)
    return (ruta.stat().st_size if ruta.exists() else 0) > antes


def esperar_latido(ruta: Path, segundos: float = 20.0) -> None:
    limite = time.monotonic() + segundos
    while not ruta.exists() or ruta.stat().st_size == 0:
        assert time.monotonic() < limite, "el proceso de prueba no llego a arrancar"
        time.sleep(0.05)


def test_ejecutar_real_mata_al_hijo_al_agotar_la_espera(tmp_path: Path) -> None:
    latido = tmp_path / "latido"
    inicio = time.monotonic()
    r = ke.ejecutar_real([sys.executable, "-c", LATIDO, str(latido)], 4.0, None)
    assert (r.estado, r.codigo) == ("tiempo_agotado", None)
    assert time.monotonic() - inicio < 30
    assert latido.exists() and not late(latido)


def test_ejecutar_real_mata_al_hijo_ante_una_interrupcion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``KeyboardInterrupt`` o ``SystemExit`` mientras se espera: el hijo no queda vivo."""
    latido = tmp_path / "latido"
    original = subprocess.Popen.communicate
    llamadas = 0

    def interrumpida(self: Any, *a: Any, **k: Any) -> Any:
        nonlocal llamadas
        llamadas += 1
        if llamadas == 1:
            esperar_latido(latido)
            raise KeyboardInterrupt
        return original(self, *a, **k)

    monkeypatch.setattr(subprocess.Popen, "communicate", interrumpida)
    with pytest.raises(KeyboardInterrupt):
        ke.ejecutar_real([sys.executable, "-c", LATIDO, str(latido)], 60.0, None)
    assert llamadas == 2  # tras matar se recoge la salida, con tope
    assert not late(latido)


def test_recoger_tras_matar_no_espera_para_siempre(monkeypatch: pytest.MonkeyPatch) -> None:
    """Un nieto con las tuberias abiertas no puede colgar al guion: ``communicate`` lleva tope."""
    topes: list[Any] = []

    class Colgado:
        pid = 1
        returncode = None

        def communicate(self, timeout: float | None = None) -> tuple[str, str]:
            topes.append(timeout)
            raise subprocess.TimeoutExpired("x", timeout or 0)

        def kill(self) -> None:
            topes.append("kill")

        def terminate(self) -> None:
            topes.append("terminate")

    monkeypatch.setattr(ke.os, "killpg", lambda pid, senal: topes.append("killpg"), raising=False)
    assert ke._matar_y_recoger(Colgado()) == ("", "")  # type: ignore[arg-type]
    assert topes == ["killpg", ke.GRACIA_MATAR]


@pytest.mark.skipif(os.name != "posix", reason="grupos de procesos: solo POSIX (lo ejercita el CI de Ubuntu)")
class TestArbolDeProcesosReal:
    """Un padre que lanza un hijo: el hijo no puede sobrevivir a la parada ni al tiempo agotado."""

    def test_tiempo_agotado_mata_tambien_al_nieto(self, tmp_path: Path) -> None:
        latido = tmp_path / "latido"
        r = ke.ejecutar_real([sys.executable, "-c", PADRE, str(latido), "120"], 5.0, None)
        assert r.estado == "tiempo_agotado"
        assert latido.exists() and not late(latido)

    def test_un_comando_que_termina_no_deja_hijos_atras(self, tmp_path: Path) -> None:
        latido = tmp_path / "latido"
        r = ke.ejecutar_real([sys.executable, "-c", PADRE, str(latido), "3"], 60.0, None)
        assert (r.estado, r.codigo) == ("ok", 0)
        assert latido.exists() and not late(latido)

    def test_detener_mata_al_hijo_del_servidor(self, tmp_path: Path) -> None:
        latido = tmp_path / "latido"
        proceso = ke.lanzar_real(
            [sys.executable, "-c", PADRE, str(latido), "120"], tmp_path / "s.log", dict(os.environ)
        )
        guardia = ke.Guardia()
        guardia.asignar(proceso)
        try:
            esperar_latido(latido)
            assert proceso.vivo() and proceso.grupo_vivo()
            assert guardia.detener() is True
            assert not proceso.vivo() and not proceso.grupo_vivo() and not late(latido)
        finally:
            proceso.matar()

    def test_detener_mata_al_hijo_aunque_el_lider_ya_haya_terminado(self, tmp_path: Path) -> None:
        latido = tmp_path / "latido"
        proceso = ke.lanzar_real(
            [sys.executable, "-c", PADRE, str(latido), "0"], tmp_path / "s.log", dict(os.environ)
        )
        guardia = ke.Guardia()
        guardia.asignar(proceso)
        try:
            esperar_latido(latido)
            limite = time.monotonic() + 20
            while proceso.vivo():
                assert time.monotonic() < limite
                time.sleep(0.05)
            assert proceso.grupo_vivo()  # el lider termino y el hijo sigue: mirar solo al lider engana
            assert guardia.detener() is True
            assert not proceso.grupo_vivo() and not late(latido)
        finally:
            proceso.matar()

    def test_el_proceso_lanzado_tiene_grupo_propio(self, tmp_path: Path) -> None:
        r = ke.ejecutar_real(
            [sys.executable, "-c", "import os; print(os.getpid(), os.getpgid(0), os.getsid(0))"], 60.0, None
        )
        pid, grupo, sesion = (int(x) for x in r.stdout.split())
        assert pid == grupo == sesion and grupo != os.getpgid(0)

    def test_grupo_vivo_no_cuenta_un_grupo_inexistente(self) -> None:
        r = ke.ejecutar_real([sys.executable, "-c", "import os; print(os.getpid())"], 60.0, None)
        assert ke.grupo_vivo(int(r.stdout)) is False
        assert ke.grupo_vivo(os.getpgid(0)) is True

    def test_sighup_tambien_es_una_salida_ordenada(self) -> None:
        with pytest.raises(SystemExit) as info, ke._senales(True):
            signal.raise_signal(signal.SIGHUP)
        assert info.value.code == 128 + signal.SIGHUP


@pytest.mark.skipif(os.name == "posix", reason="comportamiento fuera de POSIX")
def test_grupo_vivo_fuera_de_posix_es_falso() -> None:
    assert ke.grupo_vivo(os.getpid()) is False


def test_senales_cubre_sigterm_sigint_y_las_restaura() -> None:
    antes = {n: signal.getsignal(n) for n in (signal.SIGTERM, signal.SIGINT)}
    with pytest.raises(SystemExit) as info, ke._senales(True):
        assert all(signal.getsignal(n) is not antes[n] for n in antes)
        signal.raise_signal(signal.SIGTERM)
    assert info.value.code == 128 + signal.SIGTERM
    assert {n: signal.getsignal(n) for n in antes} == antes
    with pytest.raises(KeyboardInterrupt), ke._senales(True):
        signal.raise_signal(signal.SIGINT)
    assert {n: signal.getsignal(n) for n in antes} == antes
    with ke._senales(False):
        assert {n: signal.getsignal(n) for n in antes} == antes


# ---------------------------------------------------------------------------
# D3. Rechazo calibrado: el prompt que cabe en el contexto pero no deja sitio a la salida
# ---------------------------------------------------------------------------


def test_el_prompt_calibrado_separa_los_dos_candidatos() -> None:
    assert ke.TOKENS_OBJETIVO + 16384 > ke.CONTEXTO_MAXIMO > ke.TOKENS_OBJETIVO + 8192
    assert ke.esperado_calibrado(16384) == "rechazado" and ke.esperado_calibrado(8192) == "aceptado"
    assert ke.esperado_calibrado(ke.CONTEXTO_MAXIMO - ke.TOKENS_OBJETIVO) == "aceptado"  # cabe justo
    assert ke.esperado_calibrado(ke.CONTEXTO_MAXIMO - ke.TOKENS_OBJETIVO + 1) == "rechazado"
    assert ke.PALABRAS_CALIBRACION == (500, 2000)


def test_sonda_calibracion_mide_tokens_por_palabra(doble: Doble, crudo: ke.Crudo, esc: Escenario) -> None:
    r = ke.sonda_calibracion(doble.entorno(), crudo, cfg_de(esc))
    # el servidor de mentira cuenta 2 tokens por palabra y 20 de plantilla: 20 + 2 * 9990 = 20 000
    assert r.valores == {
        "tokens_por_palabra": 2.0,
        "sobrecarga_tokens": 20,
        "tokens_objetivo": 20000,
        "palabras": 9990,
    }
    cuerpos = [json.loads(c) for _, _, c in doble.peticiones if c is not None]
    assert [len(c["messages"][0]["content"].split()) for c in cuerpos] == [500, 2000]
    assert [c["max_tokens"] for c in cuerpos] == [1, 1]
    assert doble.esperas_http == [("completions", ke.ESPERA_CALIBRACION)] * 2


@pytest.mark.parametrize(
    ("por_palabra", "sobrecarga", "palabras"), [(1, 0, 20000), (3, 500, 6500), (4, 20, 4995)]
)
def test_sonda_calibracion_con_otros_tokenizadores(
    doble: Doble, crudo: ke.Crudo, esc: Escenario, por_palabra: int, sobrecarga: int, palabras: int
) -> None:
    doble.tokens_por_palabra, doble.sobrecarga = por_palabra, sobrecarga
    r = ke.sonda_calibracion(doble.entorno(), crudo, cfg_de(esc))
    assert (r.valores["tokens_por_palabra"], r.valores["palabras"]) == (float(por_palabra), palabras)


@pytest.mark.parametrize(
    ("respuesta", "categoria"),
    [
        (ke.Respuesta("sin_conexion", None, b""), "sin_conexion"),
        (ke.Respuesta("tiempo_agotado", None, b""), "tiempo_agotado"),
        (ke.Respuesta("protocolo", None, b""), "respuesta_http_invalida"),
        (ke.Respuesta("ok", 400, RECHAZO_400.encode()), "respuesta_inesperada"),
        (ke.Respuesta("ok", 200, b"{}"), "salida_ilegible"),
        (ke.Respuesta("ok", 200, b'{"usage": {"prompt_tokens": "muchos"}}'), "salida_ilegible"),
        (ke.Respuesta("ok", 200, b'{"usage": {"prompt_tokens": true}}'), "salida_ilegible"),
        (ke.Respuesta("ok", 200, b'{"usage": {"prompt_tokens": -3}}'), "salida_ilegible"),
        (
            ke.Respuesta("ok", 200, b'{"usage": {"prompt_tokens": 700}}'),
            "respuesta_inesperada",
        ),  # pendiente 0
    ],
)
def test_sonda_calibracion_sin_valor(
    doble: Doble, crudo: ke.Crudo, esc: Escenario, respuesta: ke.Respuesta, categoria: str
) -> None:
    doble.http_manejador = lambda m, u, c: respuesta
    r = ke.sonda_calibracion(doble.entorno(), crudo, cfg_de(esc))
    assert (r.estado, r.categoria, dict(r.valores)) == (ke.ERROR, categoria, {})


@pytest.mark.parametrize(("por_palabra", "sobrecarga"), [(0, 20), (9, 20), (2, -3000)])
def test_sonda_calibracion_rechaza_una_pendiente_o_una_plantilla_absurdas(
    doble: Doble, crudo: ke.Crudo, esc: Escenario, por_palabra: int, sobrecarga: int
) -> None:
    doble.tokens_por_palabra, doble.sobrecarga = por_palabra, sobrecarga
    doble.http_manejador = None

    def contar(metodo: str, url: str, cuerpo: bytes | None) -> ke.Respuesta:
        assert cuerpo is not None
        palabras = json.loads(cuerpo)["messages"][0]["content"].count("tornillo")
        uso = {"usage": {"prompt_tokens": max(0, sobrecarga + por_palabra * palabras)}}
        return ke.Respuesta("ok", 200, json.dumps(uso).encode())

    doble.http_manejador = contar
    r = ke.sonda_calibracion(doble.entorno(), crudo, cfg_de(esc))
    assert (r.estado, r.categoria) == (ke.ERROR, "respuesta_inesperada")


def test_sonda_rechazo_calibrado_distingue_16384_de_8192(
    doble: Doble, crudo: ke.Crudo, esc: Escenario
) -> None:
    """Lo que la sonda de exceso total no ve: el mismo prompt, rechazado con un tope y no con el otro."""
    ent, cfg = doble.entorno(), cfg_de(esc)
    con_kit = ke.sonda_rechazo_calibrado(ent, crudo, cfg, 16384, 9990)
    cuerpo = json.dumps({"error": {"message": RECHAZO_400, "type": "BadRequestError", "code": 400}}).encode()
    assert con_kit.valores == {
        "max_tokens": 16384,
        "palabras": 9990,
        "tokens_estimados": 20000,
        "http": 400,
        "resultado": "rechazado",
        "esperado": "rechazado",
        "coincide_con_lo_esperado": True,
        "marcadores": {"contextwindowexceedederror": False, "maximum_context_length": True},
        "cuerpo_sha256": hashlib.sha256(cuerpo).hexdigest(),
        "cuerpo_bytes": len(cuerpo),
    }
    con_menos = ke.sonda_rechazo_calibrado(ent, crudo, cfg, 8192, 9990)
    assert con_menos.valores["resultado"] == "aceptado" and con_menos.valores["http"] == 200
    assert con_menos.valores["prompt_tokens"] == 20000
    assert (
        con_menos.valores["esperado"] == "aceptado" and con_menos.valores["coincide_con_lo_esperado"] is True
    )
    for r in (con_kit, con_menos):
        assert not any(p in json.dumps(dict(r.valores)) for p in POISON_TODOS)
        assert r.valores["resultado"] in ke.RESULTADOS_CALIBRADO
    peticiones = [json.loads(c) for _, _, c in doble.peticiones if c is not None]
    assert [p["max_tokens"] for p in peticiones] == [16384, 8192]
    for p in peticiones:
        contenido = p["messages"][0]["content"]
        assert contenido.endswith(ke.PROMPT_CONTROL) and contenido.count("tornillo") == 9990
    assert doble.esperas_http == [("completions", ke.ESPERA_CALIBRADO)] * 2
    # el texto exacto del rechazo queda en el volcado crudo
    assert RECHAZO_400 in (crudo.raiz / "001_calibrado_16384_cuerpo.txt").read_text(encoding="utf-8")


def uso(prompt_tokens: Any) -> bytes:
    return json.dumps({"usage": {"prompt_tokens": prompt_tokens, "completion_tokens": 3}}).encode()


@pytest.mark.parametrize(
    ("respuesta", "resultado", "contados"),
    [
        (ke.Respuesta("ok", 400, b"litellm.ContextWindowExceededError"), "rechazado", None),
        (ke.Respuesta("ok", 400, b'{"error": "otra cosa"}'), "rechazo_sin_marcador", None),
        (ke.Respuesta("ok", 200, uso(20000)), "aceptado", 20000),
        (ke.Respuesta("ok", 200, uso(18000)), "aceptado", 18000),  # 0,9 del objetivo: todavia entero
        (ke.Respuesta("ok", 200, uso(17999)), "truncado", 17999),
        (ke.Respuesta("ok", 200, uso(4096)), "truncado", 4096),
        (ke.Respuesta("ok", 200, b'{"choices": []}'), "aceptado_sin_conteo", None),
        (ke.Respuesta("ok", 200, b"<html>"), "aceptado_sin_conteo", None),
        (ke.Respuesta("ok", 413, b"maximum context length"), "otro", None),
        (ke.Respuesta("ok", 500, b""), "otro", None),
    ],
)
def test_sonda_rechazo_calibrado_nombra_cada_desenlace(
    doble: Doble, crudo: ke.Crudo, esc: Escenario, respuesta: ke.Respuesta, resultado: str, contados: Any
) -> None:
    """Un servidor que trunca en vez de rechazar no se confunde con uno que acepta."""
    doble.http_manejador = lambda m, u, c: respuesta
    r = ke.sonda_rechazo_calibrado(doble.entorno(), crudo, cfg_de(esc), 16384, 9990)
    assert r.estado == ke.MEDIDO and r.valores["resultado"] == resultado
    assert r.valores.get("prompt_tokens") == contados
    assert r.valores["coincide_con_lo_esperado"] is (resultado == "rechazado")
    assert r.valores["http"] == respuesta.codigo


@pytest.mark.parametrize(
    ("respuesta", "categoria"),
    [
        (ke.Respuesta("sin_conexion", None, b""), "sin_conexion"),
        (ke.Respuesta("tiempo_agotado", None, b""), "tiempo_agotado"),
        (ke.Respuesta("protocolo", None, b""), "respuesta_http_invalida"),
    ],
)
def test_sonda_rechazo_calibrado_sin_valor(
    doble: Doble, crudo: ke.Crudo, esc: Escenario, respuesta: ke.Respuesta, categoria: str
) -> None:
    doble.http_manejador = lambda m, u, c: respuesta
    r = ke.sonda_rechazo_calibrado(doble.entorno(), crudo, cfg_de(esc), 8192, 9990)
    assert (r.estado, r.categoria, dict(r.valores)) == (ke.ERROR, categoria, {})


def test_la_sonda_de_exceso_total_no_distingue_los_candidatos(
    doble: Doble, crudo: ke.Crudo, esc: Escenario
) -> None:
    """Control: con 60 000 palabras los dos topes dan lo mismo; por eso existe la sonda calibrada."""
    ent, cfg = doble.entorno(), cfg_de(esc)
    a, b = ke.sonda_rechazo(ent, crudo, cfg, 16384), ke.sonda_rechazo(ent, crudo, cfg, 8192)
    assert a.valores["rechazado"] is True and b.valores["rechazado"] is True
    assert doble.esperas_http == [("completions", ke.ESPERA_CONTROL), ("completions", ke.ESPERA_RECHAZO)] * 2


def test_main_sin_calibracion_no_hay_registro(esc: Escenario, doble: Doble) -> None:
    def sin_uso(metodo: str, url: str, cuerpo: bytes | None) -> ke.Respuesta | None:
        if cuerpo is not None and json.loads(cuerpo)["max_tokens"] == 1:
            return ke.Respuesta("ok", 200, b'{"choices": []}')
        return None

    doble.http_manejador = sin_uso
    assert correr_main(esc, doble) == ke.EXIT_INCOMPLETO
    assert not esc.salida.exists()
    sondas = esc.sondas()
    assert (sondas["calibracion"]["estado"], sondas["calibracion"]["categoria"]) == (
        ke.ERROR,
        "salida_ilegible",
    )
    for t in (16384, 8192):
        assert sondas[f"rechazo_calibrado:{t}"]["categoria"] == "dependencia_no_medida"
    assert sondas["agente:16384"]["estado"] == ke.MEDIDO  # las demas sondas siguen


# ---------------------------------------------------------------------------
# D4. Los rechazos son peticiones rechazadas por el servidor, contrastadas con el arnes
# ---------------------------------------------------------------------------

ACCESO = 'INFO:     127.0.0.1:50000 - "POST /v1/chat/completions HTTP/1.1" '


def agente(
    doble: Doble, crudo: ke.Crudo, esc: Escenario, max_tokens: int = 16384, **cambios: Any
) -> ke.Parcial:
    registro = crudo.ruta(ke.REGISTRO_SERVIDOR)
    if not registro.exists() and not cambios.pop("sin_registro", False):
        registro.write_text(f"vllm arrancando\n{POISON_LOG}\n", encoding="utf-8")
    base: dict[str, Any] = {
        "max_tokens": max_tokens,
        "tasks": esc.tasks,
        "snapshots": esc.snapshots,
        "envio": esc.envio,
        "backend": "subprocess",
        "imagen": "swebench-sandbox:latest",
        "ids": ELEGIDAS,
        "espera": 3600.0,
    }
    return ke.sonda_agente(doble.entorno(), crudo, cfg_de(esc), **{**base, **cambios})


def test_contar_chat(tmp_path: Path) -> None:
    registro = tmp_path / "servidor.log"
    assert ke.contar_chat(registro) is None
    registro.write_bytes(
        (
            f"{ACCESO}200 OK\n"
            f"{ACCESO}400 Bad Request\n"
            f"{POISON_LOG} 400 maximum context length\n"
            'INFO: 127.0.0.1:1 - "GET /health HTTP/1.1" 400 Bad Request\n'
            'INFO: 127.0.0.1:1 - "POST /v1/completions HTTP/1.1" 400 Bad Request\n'
            'INFO: 127.0.0.1:1 - "POST /v1/chat/completions HTTP/1.1" 4000\n'
            f"{ACCESO}500 Internal Server Error\n"
            f"{ACCESO}400 Bad Request\n"
        ).encode()
        + b"\xff\xfe binario \n"
    )
    assert ke.contar_chat(registro) == (4, 2)
    registro.write_text("", encoding="utf-8")
    assert ke.contar_chat(registro) == (0, 0)


def test_sonda_agente_da_turnos_ordenados_sin_identificador_ni_resultado(
    doble: Doble, crudo: ke.Crudo, esc: Escenario
) -> None:
    r = agente(doble, crudo, esc)
    assert r.valores == {
        "max_output_tokens": 16384,
        "backend": "subprocess",
        "tareas": 4,
        "turnos_por_tarea": [3, 7, 9, 12],
        "peticiones_al_modelo": 31,
        "peticiones_en_el_registro_del_servidor": 31,
        "rechazos_por_contexto": 0,
        "tareas_con_rechazo": 0,
        "errores_de_verificacion": 0,
        "max_time_minutes": 5,
    }
    texto = json.dumps([dict(r.valores), dict(r.privado), r.comandos])
    assert not any(p in texto for p in POISON_TODOS)
    assert not any(i in texto for i in ELEGIDAS)
    assert doble.esperas == [("agente", 3600.0)]


def test_sonda_agente_cuenta_las_peticiones_rechazadas_no_las_tareas(
    doble: Doble, crudo: ke.Crudo, esc: Escenario
) -> None:
    doble.rechazos_agente[16384] = 2
    doble.log_400_por_rechazo = 3  # p. ej. reintentos: tres peticiones rechazadas por tarea
    doble.error_extra[16384] = "Failed to apply test_patch: x"
    r = agente(doble, crudo, esc)
    assert r.valores["rechazos_por_contexto"] == 6 and r.valores["tareas_con_rechazo"] == 2
    assert r.valores["peticiones_en_el_registro_del_servidor"] == 31 + 6
    assert r.valores["errores_de_verificacion"] == 1
    assert r.valores["turnos_por_tarea"] == [3, 7, 9, 12]


def test_sonda_agente_solo_cuenta_lo_anotado_durante_la_corrida(
    doble: Doble, crudo: ke.Crudo, esc: Escenario
) -> None:
    """Los 400 de las sondas sinteticas, anteriores a la corrida, no son rechazos del agente."""
    crudo.ruta(ke.REGISTRO_SERVIDOR).write_text(f"{ACCESO}400 Bad Request\n" * 5, encoding="utf-8")
    r = agente(doble, crudo, esc)
    assert r.valores["rechazos_por_contexto"] == 0
    assert r.valores["peticiones_en_el_registro_del_servidor"] == 31


@pytest.mark.parametrize(
    ("filas", "por_rechazo", "extra", "categoria"),
    [
        (0, 1, 1, "rechazos_incoherentes"),  # el servidor rechazo y el arnes no anoto ningun rechazo
        (0, 1, 7, "rechazos_incoherentes"),
        (1, 0, 0, "rechazos_incoherentes"),  # el arnes anota un rechazo y el servidor no rechazo nada
        (3, 0, 0, "rechazos_incoherentes"),
    ],
)
def test_sonda_agente_no_elige_entre_dos_conteos_que_se_contradicen(
    doble: Doble, crudo: ke.Crudo, esc: Escenario, filas: int, por_rechazo: int, extra: int, categoria: str
) -> None:
    doble.rechazos_agente[16384] = filas
    doble.log_400_por_rechazo, doble.log_400_extra = por_rechazo, extra
    r = agente(doble, crudo, esc)
    assert (r.estado, r.categoria, dict(r.valores)) == (ke.ERROR, categoria, {})


def test_sonda_agente_sin_peticiones_en_el_registro_no_da_valor(
    doble: Doble, crudo: ke.Crudo, esc: Escenario
) -> None:
    """Si el registro no anota peticiones, un cero de rechazos no significaria nada."""
    doble.log_peticiones = False
    r = agente(doble, crudo, esc)
    assert (r.estado, r.categoria, dict(r.valores)) == (ke.ERROR, "log_sin_peticiones", {})
    doble.turnos[8192] = [0, 0, 0, 0]  # sin turnos no hay peticiones que anotar: no es un error
    assert agente(doble, crudo, esc, 8192).estado == ke.MEDIDO


def test_sonda_agente_sin_registro_del_servidor_no_corre(
    doble: Doble, crudo: ke.Crudo, esc: Escenario
) -> None:
    r = agente(doble, crudo, esc, sin_registro=True)
    assert (r.estado, r.categoria) == (ke.ERROR, "salida_ilegible")
    assert doble.comandos == []


def test_sonda_agente_registro_que_encoge_no_da_valor(doble: Doble, crudo: ke.Crudo, esc: Escenario) -> None:
    registro = crudo.ruta(ke.REGISTRO_SERVIDOR)
    registro.write_text(f"{ACCESO}200 OK\n" * 50, encoding="utf-8")
    original = doble._agente

    def trunca(argv: list[str]) -> ke.Salida:
        salida = original(argv)
        registro.write_text(f"{ACCESO}200 OK\n", encoding="utf-8")
        return salida

    doble.manejadores["agente"] = trunca
    r = agente(doble, crudo, esc)
    assert (r.estado, r.categoria) == (ke.ERROR, "salida_ilegible")


# ---------------------------------------------------------------------------
# D5 y E1. Registro: completo, de fallo temprano o ninguno
# ---------------------------------------------------------------------------

INFORME_SHA = "c" * 64
AGENTE_KIT = {
    "backend": "subprocess",
    "turnos_por_tarea": [3, 7, 9, 12],
    "peticiones_al_modelo": 31,
    "rechazos_por_contexto": 0,
    "max_time_minutes": 5,
}


def resultados_completos(**cambios: Any) -> list[ke.Resultado]:
    """Sondas de un ensayo que llego al agente. ``cambios``: un ``Parcial``, o ``None`` para quitar."""
    base: dict[str, ke.Parcial] = {
        "docker": ke.medido({"disponible": False, "motivo": "binario_ausente", "backend": "subprocess"}),
        "sesion": ke.medido({"horas": 12.0, "origen": "declarada", "fuente": "x"}),
        "compila": ke.medido({"compila": True}),
        "servidor": ke.medido({"arranca": True, "carga_segundos": 480.5, "guion_sha256": "a" * 64}),
        "modelo": ke.medido({"id": ke.MODELO, "version": "2", "adaptadores_servidos": 2}),
        "rendimiento": ke.medido({"tokens_por_segundo": 34.0}),
        "rechazo_calibrado:16384": ke.medido({"resultado": "rechazado"}),
        "rechazo_calibrado:8192": ke.medido({"resultado": "aceptado"}),
        "agente:16384": ke.medido(AGENTE_KIT),
        "agente:8192": ke.sin_valor(ke.NO_DISPONIBLE, "no_necesaria"),
        "limpieza": ke.medido({"servidor_detenido": True, "procesos_en_gpu": 0}),
    }
    for nombre, cambio in cambios.items():
        nombre = nombre.replace("__", ":")
        if cambio is None:
            del base[nombre]
        else:
            base[nombre] = cambio.parcial if isinstance(cambio, ke.Resultado) else cambio
    return [ke.Resultado(n, p, 1.0) for n, p in base.items()]


CAMPOS_ESPERADOS: dict[str, Any] = {
    "schema_version": "kaggle-notebook-trial/1",
    "fecha": "2026-10-06",
    "notebook": "cherrera0001/ensayo-a0 v1",
    "modelo": "gemma-4-31b-it-qat-w4a16-ct@2",
    "guion_servidor_sha256": "a" * 64,
    "docker_disponible": False,
    "backend": "subprocess",
    "servidor_arranca": True,
    "envio_compila": True,
    "carga_modelo_segundos": 480.5,
    "sesion_max_horas": 12.0,
    "tokens_por_segundo": 34.0,
    "max_time_minutes_ensayo": 5,
    "turnos_por_tarea": [3, 7, 9, 12],
    "turnos_por_tarea_repeticion": None,
    "peticiones_al_modelo": 31,
    "rechazos_por_contexto": {"16384": 0},
}
REGISTRO_ESPERADO: dict[str, Any] = {**CAMPOS_ESPERADOS, "informe_sha256": INFORME_SHA}
FIJOS = kaggle_prereg.load_params(kaggle_prereg.DEFAULT_PARAMS)["fijos"]


def campos(resultados: Sequence[ke.Resultado], notebook: str | None = "cherrera0001/ensayo-a0 v1") -> Any:
    return ke.campos_del_registro(resultados, fecha="2026-10-06", notebook=notebook)


def test_registro_completo_tiene_exactamente_el_esquema_de_la_compuerta() -> None:
    obtenidos, faltan, clase = campos(resultados_completos())
    assert (obtenidos, faltan, clase) == (CAMPOS_ESPERADOS, [], "completo")
    registro = ke.cerrar_registro(obtenidos, INFORME_SHA)
    assert registro == REGISTRO_ESPERADO
    assert set(registro) == set(kaggle_prereg.ENSAYO)
    assert all(ok(registro[k]) for k, ok in kaggle_prereg.ENSAYO.items())
    assert ke.validar_registro(registro) == []
    assert kaggle_prereg.ensayo_viable(FIJOS, registro) == 16384


@pytest.mark.parametrize(
    ("sonda", "faltan_campos"),
    [
        ("docker", ["docker_disponible"]),
        ("sesion", ["sesion_max_horas"]),
        ("compila", ["envio_compila"]),
        ("servidor", ["guion_servidor_sha256", "servidor_arranca"]),
        ("modelo", ["modelo", "modelo"]),
        ("rendimiento", ["tokens_por_segundo"]),
        ("rechazo_calibrado__16384", ["rechazo calibrado con 16384"]),
        ("rechazo_calibrado__8192", ["rechazo calibrado con 8192"]),
        (
            "agente__16384",
            ["backend", "turnos_por_tarea", "peticiones_al_modelo", "rechazos_por_contexto[16384]"],
        ),
    ],
)
@pytest.mark.parametrize("estado", [ke.NO_DISPONIBLE, ke.ERROR, "ausente"])
def test_sin_una_sonda_necesaria_no_hay_registro(sonda: str, faltan_campos: list[str], estado: str) -> None:
    """D5: servidor, modelo, rendimiento, rechazo calibrado y agente; mas docker, sesion y compila."""
    if estado == "ausente":
        resultados = resultados_completos(**{sonda: None})
    else:
        categoria = "dependencia_no_medida" if estado == ke.NO_DISPONIBLE else "tiempo_agotado"
        resultados = resultados_completos(**{sonda: ke.sin_valor(estado, categoria)})
    obtenidos, faltan, clase = campos(resultados)
    assert (obtenidos, clase) == (None, "ninguno")
    assert [f.split(" (")[0] for f in faltan] == faltan_campos
    assert all(f"sonda {sonda.replace('__', ':')}: {estado}" in f for f in faltan)


@pytest.mark.parametrize(
    "sonda", ["gpu", "version__vllm", "version__docker", "memoria", "rechazo_sintetico__16384"]
)
def test_las_sondas_que_no_deciden_nada_no_bloquean_el_registro(sonda: str) -> None:
    resultados = resultados_completos(**{sonda: ke.sin_valor(ke.ERROR, "error_inesperado")})
    obtenidos, faltan, clase = campos(resultados)
    assert (obtenidos, faltan, clase) == (CAMPOS_ESPERADOS, [], "completo")
    informe = ke.construir_informe(
        resultados, fecha="2026-10-06", clase_registro=clase, faltan=[], servidor_detenido=True
    )
    # ...pero el informe las marca
    assert {"sonda": sonda.replace("__", ":"), "estado": "error", "categoria": "error_inesperado"} in informe[
        "sin_medir"
    ]


@pytest.mark.parametrize(
    "limpieza",
    [
        ke.medido({"servidor_detenido": False, "procesos_en_gpu": 0}),
        ke.medido({"servidor_detenido": True, "procesos_en_gpu": 2}),
        ke.sin_valor(ke.ERROR, "error_inesperado"),
    ],
)
def test_sin_limpieza_correcta_no_hay_registro(limpieza: ke.Parcial) -> None:
    obtenidos, faltan, clase = campos(resultados_completos(limpieza=limpieza))
    assert (obtenidos, clase) == (None, "ninguno")
    assert len(faltan) == 1 and faltan[0].startswith("limpieza")
    # tampoco un registro de fallo temprano
    parado = ke.medido({"arranca": False, "motivo": "tiempo_agotado", "guion_sha256": "a" * 64})
    assert campos(resultados_completos(limpieza=limpieza, servidor=parado))[0] is None


def test_sin_servidor_lanzado_no_hace_falta_limpieza() -> None:
    assert campos(resultados_completos(limpieza=None))[2] == "completo"


@pytest.mark.parametrize("notebook", [None, "", f"nb {POISON_LOG}\n", "/kaggle/working/nb"])
def test_sin_notebook_declarado_no_hay_registro(notebook: str | None) -> None:
    obtenidos, faltan, clase = campos(resultados_completos(), notebook)
    assert obtenidos is None and clase == "ninguno"
    assert len(faltan) == 1 and faltan[0].startswith("notebook")


def test_servidor_que_no_arranca_da_un_registro_con_nulos_no_con_ceros() -> None:
    """E1: las medidas que no existen van nulas, y la compuerta lo cierra como no viable."""
    parado = ke.medido({"arranca": False, "motivo": "tiempo_agotado", "guion_sha256": "a" * 64})
    saltada = ke.sin_valor(ke.NO_DISPONIBLE, "dependencia_no_medida")
    resultados = resultados_completos(
        servidor=parado,
        modelo=saltada,
        rendimiento=saltada,
        rechazo_calibrado__16384=saltada,
        rechazo_calibrado__8192=saltada,
        agente__16384=saltada,
        agente__8192=saltada,
    )
    obtenidos, faltan, clase = campos(resultados)
    assert (faltan, clase) == ([], "fallo_temprano")
    nulos = (
        "modelo",
        "backend",
        "carga_modelo_segundos",
        "tokens_por_segundo",
        "turnos_por_tarea",
        "turnos_por_tarea_repeticion",
        "peticiones_al_modelo",
        "rechazos_por_contexto",
    )
    assert obtenidos == {**CAMPOS_ESPERADOS, "servidor_arranca": False, **dict.fromkeys(nulos)}
    registro = ke.cerrar_registro(obtenidos, INFORME_SHA)
    assert all(ok(registro[k]) for k, ok in kaggle_prereg.ENSAYO.items())
    with pytest.raises(kaggle_prereg.PreregError) as info:
        kaggle_prereg.ensayo_viable(FIJOS, registro)
    assert "no es viable" in str(info.value) and "Ademas" not in str(info.value)


def test_envio_que_no_compila_conserva_lo_medido_del_servidor() -> None:
    saltada = ke.sin_valor(ke.NO_DISPONIBLE, "dependencia_no_medida")
    resultados = resultados_completos(
        compila=ke.medido({"compila": False}), agente__16384=saltada, agente__8192=saltada
    )
    obtenidos, faltan, clase = campos(resultados)
    assert (faltan, clase) == ([], "fallo_temprano")
    nulos = (
        "backend",
        "turnos_por_tarea",
        "turnos_por_tarea_repeticion",
        "peticiones_al_modelo",
        "rechazos_por_contexto",
    )
    assert obtenidos == {**CAMPOS_ESPERADOS, "envio_compila": False, **dict.fromkeys(nulos)}
    assert obtenidos["carga_modelo_segundos"] == 480.5 and obtenidos["modelo"] is not None
    with pytest.raises(kaggle_prereg.PreregError) as info:
        kaggle_prereg.ensayo_viable(FIJOS, ke.cerrar_registro(obtenidos, INFORME_SHA))
    assert "no es viable" in str(info.value) and "Ademas" not in str(info.value)


def test_fallo_temprano_no_rellena_lo_que_el_servidor_no_llego_a_medir() -> None:
    """Envio que no compila y, ademas, rendimiento con error: nulo, no un numero."""
    resultados = resultados_completos(
        compila=ke.medido({"compila": False}),
        rendimiento=ke.sin_valor(ke.ERROR, "tiempo_agotado"),
        modelo=ke.sin_valor(ke.ERROR, "sin_conexion"),
    )
    obtenidos, _, clase = campos(resultados)
    assert clase == "fallo_temprano"
    assert obtenidos["tokens_por_segundo"] is None and obtenidos["modelo"] is None
    assert obtenidos["turnos_por_tarea"] is None  # aunque la sonda del agente trajera valores


def con_rechazos(n_kit: int, segundo: ke.Parcial) -> list[ke.Resultado]:
    kit = ke.medido({**AGENTE_KIT, "rechazos_por_contexto": n_kit})
    return resultados_completos(agente__16384=kit, agente__8192=segundo)


def test_con_rechazos_el_registro_exige_la_repeticion_y_lleva_sus_turnos() -> None:
    obtenidos, faltan, clase = campos(con_rechazos(2, ke.sin_valor(ke.ERROR, "tiempo_agotado")))
    assert (obtenidos, clase) == (None, "ninguno")
    assert faltan == [
        "rechazos_por_contexto[8192] (sonda agente:8192: error)",
        "turnos_por_tarea_repeticion (sonda agente:8192: error)",
    ]
    segundo = ke.medido({"rechazos_por_contexto": 0, "turnos_por_tarea": [6, 6, 6, 6]})
    obtenidos, faltan, clase = campos(con_rechazos(2, segundo))
    assert (faltan, clase) == ([], "completo")
    assert obtenidos["rechazos_por_contexto"] == {"16384": 2, "8192": 0}
    assert obtenidos["turnos_por_tarea"] == [3, 7, 9, 12] and obtenidos["peticiones_al_modelo"] == 31
    assert obtenidos["turnos_por_tarea_repeticion"] == [6, 6, 6, 6]
    assert kaggle_prereg.ensayo_viable(FIJOS, ke.cerrar_registro(obtenidos, INFORME_SHA)) == 8192
    otro, _, _ = campos(
        con_rechazos(1, ke.medido({"rechazos_por_contexto": 3, "turnos_por_tarea": [1, 1, 1, 1]}))
    )
    assert otro["rechazos_por_contexto"] == {"16384": 1, "8192": 3}


def test_sin_rechazos_no_se_lee_la_repeticion() -> None:
    segundo = ke.medido({"rechazos_por_contexto": 4, "turnos_por_tarea": [1, 1, 1, 1]})
    obtenidos, faltan, _ = campos(con_rechazos(0, segundo))
    assert faltan == [] and obtenidos["rechazos_por_contexto"] == {"16384": 0}
    assert obtenidos["turnos_por_tarea_repeticion"] is None


def test_un_registro_que_no_pasa_su_esquema_no_se_cierra() -> None:
    obtenidos, _, _ = campos(resultados_completos(rendimiento=ke.medido({"tokens_por_segundo": -1.0})))
    with pytest.raises(RuntimeError, match="tokens_por_segundo"):
        ke.cerrar_registro(obtenidos, INFORME_SHA)
    with pytest.raises(RuntimeError, match="informe_sha256"):
        ke.cerrar_registro(CAMPOS_ESPERADOS, "abc")


def test_validar_registro() -> None:
    assert ke.validar_registro(REGISTRO_ESPERADO) == []
    assert ke.validar_registro([]) == ["el registro no es un objeto"]
    assert "claves" in ke.validar_registro({**REGISTRO_ESPERADO, "extra": 1})[0]
    sin_una = {k: v for k, v in REGISTRO_ESPERADO.items() if k != "informe_sha256"}
    assert "claves" in ke.validar_registro(sin_una)[0]
    assert ke.validar_registro({**REGISTRO_ESPERADO, "backend": "otro"}) == ["valor invalido en backend"]
    # un ensayo que llego al agente no puede traer nulas sus medidas
    for campo in ke.EXIGIDOS_SI_VIABLE:
        problemas = ke.validar_registro({**REGISTRO_ESPERADO, campo: None})
        assert problemas == [f"falta {campo} en un ensayo que llego al agente"]
    assert ke.validar_registro({**REGISTRO_ESPERADO, "servidor_arranca": False, "modelo": None}) == []
    assert ke.EXIGIDOS_SI_VIABLE == kaggle_prereg.ENSAYO_SI_VIABLE


VALORES_DE_PRUEBA: tuple[Any, ...] = (
    None,
    True,
    False,
    0,
    1,
    -1,
    0.0,
    0.5,
    -0.5,
    float("nan"),
    float("inf"),
    "",
    " ",
    "x",
    "docker",
    "subprocess",
    "otro",
    "2026-10-06",
    "2026-13-40",
    "a" * 64,
    "A" * 64,
    "g" * 64,
    ke.ESQUEMA_REGISTRO,
    [],
    [0],
    [5, 7],
    [-1],
    [True],
    [1.5],
    {},
    {"16384": 0},
    {"16384": 2, "8192": 0},
    {"x": 0},
    {"16384": -1},
    {"16384": True},
    {"16384": 1.0},
    {16384: 0},
)


@pytest.mark.parametrize("clave", sorted(kaggle_prereg.ENSAYO))
def test_esquema_propio_decide_igual_que_el_de_la_compuerta(clave: str) -> None:
    for valor in VALORES_DE_PRUEBA:
        if clave == "fecha" and valor == "2026-13-40":
            continue  # la compuerta ademas interpreta la fecha; aqui solo se comprueba la forma
        assert bool(ke.ESQUEMA[clave](valor)) == bool(kaggle_prereg.ENSAYO[clave](valor)), (clave, valor)


def test_el_informe_no_se_construye_con_una_cadena_de_log() -> None:
    envenenado = ke.Resultado("gpu", ke.medido({"modelos": [f"NVIDIA L4\n{POISON_LOG}"]}), 0.1)
    with pytest.raises(RuntimeError):
        ke.construir_informe(
            [envenenado], fecha="2026-10-06", clase_registro="ninguno", faltan=[], servidor_detenido=True
        )


def test_el_informe_explica_que_cuenta_cada_campo_dudoso() -> None:
    informe = ke.construir_informe(
        resultados_completos(),
        fecha="2026-10-06",
        clase_registro="completo",
        faltan=[],
        servidor_detenido=True,
    )
    assert informe["notas"] == {
        "peticiones_al_modelo": "turnos completados segun el arnes",
        "rechazos_por_contexto": "respuestas 400 a la ruta de chat en el registro del servidor",
    }
    assert informe["registro"] == {"clase": "completo", "faltan": 0}
    assert informe["sin_medir"] == [
        {"sonda": "agente:8192", "estado": "no_disponible", "categoria": "no_necesaria"}
    ]
    assert "sha256" not in json.dumps(informe["registro"])  # es el registro quien cita al informe


# ---------------------------------------------------------------------------
# E1. La compuerta: fallo temprano, informe citado y lista de turnos de la repeticion
# ---------------------------------------------------------------------------


def registro_de_una_corrida(esc: Escenario, doble: Doble) -> bytes:
    assert correr_main(esc, doble) == ke.EXIT_OK
    return esc.salida.read_bytes()


@pytest.mark.parametrize(
    ("cambios", "fragmento"),
    [
        ({"turnos_por_tarea": [4, 4, 4, 9]}, "no es viable"),
        ({"rechazos_por_contexto": {"16384": 1, "8192": 1}}, "rechazos por contexto con todos"),
        ({"rechazos_por_contexto": {"16384": 1}}, "falta el conteo de rechazos con 8192"),
        ({"backend": "docker"}, "el notebook no tiene Docker"),
        ({"fecha": "2026-10-02"}, "anterior"),
        ({"fecha": "2026-11-06"}, "posterior al corte"),
        ({"tokens_por_segundo": -1}, "valores invalidos"),
        ({"turnos_por_tarea": []}, "valores invalidos"),
        ({"guion_servidor_sha256": "abc"}, "valores invalidos"),
        ({"schema_version": "kaggle-notebook-trial/2"}, "valores invalidos"),
        ({"carga_modelo_segundos": ...}, "debe tener las claves"),
        ({"hardware": "NVIDIA L4"}, "debe tener las claves"),
        # Enmienda 1
        ({"informe_sha256": ...}, "debe tener las claves"),
        ({"informe_sha256": "abc"}, "valores invalidos"),
        ({"informe_sha256": None}, "valores invalidos"),
        ({"turnos_por_tarea_repeticion": ...}, "debe tener las claves"),
        ({"turnos_por_tarea_repeticion": []}, "valores invalidos"),
        ({"turnos_por_tarea_repeticion": [9, 9, 9, 9]}, "si y solo si"),  # sin rechazos no hay repeticion
        ({"rechazos_por_contexto": {"16384": 1, "8192": 0}}, "si y solo si"),  # con rechazos, debe haberla
        ({"carga_modelo_segundos": None}, "no pueden faltar ['carga_modelo_segundos']"),
        ({"modelo": None}, "no pueden faltar ['modelo']"),
        ({"backend": None}, "no pueden faltar ['backend']"),
        ({"tokens_por_segundo": None}, "no pueden faltar ['tokens_por_segundo']"),
        ({"turnos_por_tarea": None}, "no pueden faltar ['turnos_por_tarea']"),
        ({"peticiones_al_modelo": None}, "no pueden faltar ['peticiones_al_modelo']"),
        ({"rechazos_por_contexto": None}, "no pueden faltar ['rechazos_por_contexto']"),
        ({"sesion_max_horas": None}, "valores invalidos"),
        ({"docker_disponible": None}, "valores invalidos"),
        ({"servidor_arranca": None}, "valores invalidos"),
    ],
)
def test_la_compuerta_rechaza_el_registro_alterado(
    esc: Escenario, doble: Doble, tmp_path: Path, cambios: dict[str, Any], fragmento: str
) -> None:
    res = compuerta(tmp_path, alterar(registro_de_una_corrida(esc, doble), **cambios))
    assert len(res.problemas) == 1 and fragmento in res.problemas[0]


SIN_AGENTE: dict[str, Any] = dict.fromkeys(
    (
        "backend",
        "turnos_por_tarea",
        "turnos_por_tarea_repeticion",
        "peticiones_al_modelo",
        "rechazos_por_contexto",
    )
)
SIN_SERVIDOR: dict[str, Any] = {
    **SIN_AGENTE,
    **dict.fromkeys(("modelo", "carga_modelo_segundos", "tokens_por_segundo")),
}


@pytest.mark.parametrize(
    ("cambios", "imposibles"),
    [
        # el servidor no arranca: todo lo que depende de el va nulo
        ({"servidor_arranca": False, **SIN_SERVIDOR}, None),
        ({"servidor_arranca": False, "envio_compila": False, **SIN_SERVIDOR}, None),
        # el envio no compila: lo del servidor puede estar medido; lo del agente, no
        ({"envio_compila": False, **SIN_AGENTE}, None),
        ({"envio_compila": False, **SIN_SERVIDOR}, None),
        # medidas que no pueden existir: se nombran
        ({"servidor_arranca": False, **SIN_SERVIDOR, "carga_modelo_segundos": 0}, ["carga_modelo_segundos"]),
        ({"servidor_arranca": False, **SIN_SERVIDOR, "tokens_por_segundo": 0}, ["tokens_por_segundo"]),
        ({"servidor_arranca": False, **SIN_SERVIDOR, "modelo": "x@1"}, ["modelo"]),
        ({"servidor_arranca": False, **SIN_SERVIDOR, "turnos_por_tarea": [0, 0, 0, 0]}, ["turnos_por_tarea"]),
        ({"envio_compila": False, **SIN_AGENTE, "turnos_por_tarea": [9, 9, 9, 9]}, ["turnos_por_tarea"]),
        ({"envio_compila": False, **SIN_AGENTE, "peticiones_al_modelo": 0}, ["peticiones_al_modelo"]),
        ({"envio_compila": False, **SIN_AGENTE, "backend": "subprocess"}, ["backend"]),
        (
            {"envio_compila": False, **SIN_AGENTE, "rechazos_por_contexto": {"16384": 0}},
            ["rechazos_por_contexto"],
        ),
        (
            {"servidor_arranca": False},  # el registro completo de antes de la enmienda, con «arranca» falso
            sorted(set(SIN_SERVIDOR) - {"turnos_por_tarea_repeticion"}),
        ),
    ],
)
def test_la_compuerta_cierra_un_fallo_temprano_como_no_viable(
    esc: Escenario, doble: Doble, tmp_path: Path, cambios: dict[str, Any], imposibles: list[str] | None
) -> None:
    res = compuerta(tmp_path, alterar(registro_de_una_corrida(esc, doble), **cambios))
    assert len(res.problemas) == 1
    assert "no es viable" in res.problemas[0] and "'ensayo_no_viable'" in res.problemas[0]
    if imposibles is None:
        assert "Ademas" not in res.problemas[0]
    else:
        assert f"no pueden existir en ese caso: {imposibles}." in res.problemas[0]


@pytest.mark.parametrize(
    ("del_kit", "repeticion", "viable"),
    [
        ([9, 9, 9, 9], [5, 5, 0, 0], True),  # la mitad con 5 turnos, medida con 8192
        ([9, 9, 9, 9], [5, 4, 4, 4], False),
        ([0, 0, 0, 0], [5, 5, 5, 5], True),  # la lista del kit ya no decide: queda fijado 8192
        ([9, 9, 9, 9], [0, 0, 0, 0], False),
    ],
)
def test_la_viabilidad_se_juzga_con_la_lista_del_valor_que_queda_fijado(
    esc: Escenario, doble: Doble, tmp_path: Path, del_kit: list[int], repeticion: list[int], viable: bool
) -> None:
    datos = alterar(
        registro_de_una_corrida(esc, doble),
        rechazos_por_contexto={"16384": 2, "8192": 0},
        turnos_por_tarea=del_kit,
        turnos_por_tarea_repeticion=repeticion,
    )
    res = compuerta(tmp_path, datos)
    if viable:
        assert res.problemas == []
        assert kaggle_prereg.ensayo_viable(FIJOS, json.loads(datos)) == 8192
    else:
        assert len(res.problemas) == 1 and "no es viable" in res.problemas[0]


def test_sin_rechazos_la_viabilidad_se_juzga_con_la_lista_del_kit(
    esc: Escenario, doble: Doble, tmp_path: Path
) -> None:
    base = registro_de_una_corrida(esc, doble)
    assert compuerta(tmp_path, alterar(base, turnos_por_tarea=[5, 5, 0, 0])).problemas == []
    assert "no es viable" in compuerta(tmp_path, alterar(base, turnos_por_tarea=[5, 4, 0, 0])).problemas[0]


def test_la_compuerta_acepta_la_repeticion_con_el_segundo_candidato(
    esc: Escenario, doble: Doble, tmp_path: Path
) -> None:
    doble.rechazos_agente[16384] = 1
    assert correr_main(esc, doble) == ke.EXIT_OK
    registro = json.loads(esc.salida.read_text(encoding="utf-8"))
    assert registro["rechazos_por_contexto"] == {"16384": 1, "8192": 0}
    assert registro["turnos_por_tarea"] == [3, 7, 9, 12]
    assert registro["turnos_por_tarea_repeticion"] == [6, 6, 6, 6]
    assert doble.tokens_vistos == [16384, 8192]
    assert compuerta(tmp_path, esc.salida.read_bytes()).problemas == []
    assert kaggle_prereg.output_tokens(FIJOS, registro) == 8192


# ---------------------------------------------------------------------------
# main() de punta a punta, segunda ronda
# ---------------------------------------------------------------------------


def test_main_de_punta_a_punta(esc: Escenario, doble: Doble, capsys: pytest.CaptureFixture[str]) -> None:
    assert correr_main(esc, doble) == ke.EXIT_OK
    registro = json.loads(esc.salida.read_text(encoding="utf-8"))
    assert registro == {
        "schema_version": "kaggle-notebook-trial/1",
        "fecha": "2026-10-06",
        "notebook": "cherrera0001/ensayo-a0 v1",
        "modelo": "gemma-4-31b-it-qat-w4a16-ct@2",
        "guion_servidor_sha256": ke.hash_guion_servidor(cfg_de(esc)),
        "informe_sha256": hashlib.sha256(esc.informe.read_bytes()).hexdigest(),
        "docker_disponible": False,
        "backend": "subprocess",
        "servidor_arranca": True,
        "envio_compila": True,
        "carga_modelo_segundos": 4.0,  # /health responde a la tercera consulta: dos pausas de 2 s
        "sesion_max_horas": 12.0,
        "tokens_por_segundo": 50.0,
        "max_time_minutes_ensayo": 5,
        "turnos_por_tarea": [3, 7, 9, 12],
        "turnos_por_tarea_repeticion": None,
        "peticiones_al_modelo": 31,
        "rechazos_por_contexto": {"16384": 0},
    }
    informe = json.loads(esc.informe.read_text(encoding="utf-8"))
    assert informe["schema_version"] == "kaggle-notebook-trial-probes/1"
    assert informe["fecha"] == "2026-10-06" and informe["servidor_detenido"] is True
    assert informe["registro"] == {"clase": "completo", "faltan": 0}
    assert informe["sin_medir"] == [
        {"sonda": "version:docker", "estado": "no_disponible", "categoria": "paquete_ausente"},
        {"sonda": "agente:8192", "estado": "no_disponible", "categoria": "no_necesaria"},
    ]
    sondas = esc.sondas()
    assert sondas["gpu"]["valores"]["cantidad"] == 4
    assert sondas["limpieza"]["valores"] == {"servidor_detenido": True, "procesos_en_gpu": 0}
    assert sondas["rechazo_sintetico:16384"]["valores"]["rechazado"] is True
    assert sondas["rechazo_sintetico:8192"]["valores"]["rechazado"] is True
    assert sondas["calibracion"]["valores"]["palabras"] == 9990
    assert sondas["rechazo_calibrado:16384"]["valores"]["resultado"] == "rechazado"
    assert sondas["rechazo_calibrado:8192"]["valores"]["resultado"] == "aceptado"
    # los 400 de las sondas sinteticas no cuentan como rechazos del agente
    assert sondas["agente:16384"]["valores"]["rechazos_por_contexto"] == 0
    for s in sondas.values():
        assert s["estado"] in ke.ESTADOS
        assert (s["categoria"] is None) == (s["estado"] == ke.MEDIDO)
        assert bool(s["valores"]) == (s["estado"] == ke.MEDIDO)
        assert isinstance(s["segundos"], float) and s["segundos"] >= 0
    assert sondas["servidor"]["segundos"] == 4.0 and sondas["rendimiento"]["segundos"] == 30.0
    assert len(doble.lanzados) == 1 and doble.tokens_vistos == [16384]
    assert Doble.tipo(doble.comandos[-1]) == "nvidia_apps"
    salida = capsys.readouterr()
    assert "Registro escrito: ensayo_notebook_v1.json" in salida.out
    assert hashlib.sha256(esc.salida.read_bytes()).hexdigest() in salida.out
    assert not any(p in salida.out + salida.err for p in POISON_TODOS)


def test_el_volcado_crudo_guarda_el_detalle(esc: Escenario, doble: Doble) -> None:
    assert correr_main(esc, doble) == ke.EXIT_OK
    nombres = sorted(p.name for p in esc.crudo.iterdir())
    assert "servidor.log" in nombres and "agente_16384" in nombres
    sondas = json.loads(
        next(p for p in esc.crudo.iterdir() if p.name.endswith("_sondas.json")).read_text("utf-8")
    )
    tareas = next(r for r in sondas["resultados"] if r["sonda"] == "tareas")
    assert tareas["privado"] == {"ids": ELEGIDAS}
    assert sondas["faltan"] == [] and sondas["clase_del_registro"] == "completo"
    comando = json.loads(
        next(p for p in esc.crudo.iterdir() if p.name.endswith("_gpu.json")).read_text("utf-8")
    )
    assert comando["argv"][0] == "nvidia-smi" and POISON_LOG in comando["stderr"]
    assert any(p.name.endswith("_calibrado_16384_cuerpo.txt") for p in esc.crudo.iterdir())


def test_main_solo_anfitrion_no_lanza_el_servidor_ni_escribe_registro(esc: Escenario, doble: Doble) -> None:
    assert correr_main(esc, doble, "--solo-anfitrion") == ke.EXIT_INCOMPLETO
    assert doble.lanzados == [] and doble.peticiones == []
    assert not esc.salida.exists() and esc.informe.exists()
    sondas = esc.sondas()
    assert "servidor" not in sondas and "limpieza" not in sondas
    assert sondas["tareas"]["valores"] == {"tareas": 4}
    informe = json.loads(esc.informe.read_text(encoding="utf-8"))
    assert informe["registro"]["clase"] == "ninguno" and informe["registro"]["faltan"] > 0


def test_main_sin_vllm_no_lanza_nada_y_no_inventa(
    esc: Escenario, doble: Doble, capsys: pytest.CaptureFixture[str]
) -> None:
    """Sin vLLM no se sabe si el servidor arranca: ni registro completo ni de fallo temprano."""
    doble.paquetes["vllm"] = None
    assert correr_main(esc, doble) == ke.EXIT_INCOMPLETO
    assert doble.lanzados == [] and doble.peticiones == [] and not esc.salida.exists()
    sondas = esc.sondas()
    for nombre in (
        "servidor",
        "modelo",
        "rendimiento",
        "calibracion",
        "rechazo_calibrado:8192",
        "agente:16384",
    ):
        assert (sondas[nombre]["estado"], sondas[nombre]["categoria"]) == (
            ke.NO_DISPONIBLE,
            "dependencia_no_medida",
        )
        assert sondas[nombre]["valores"] == {}
    assert "limpieza" not in sondas
    err = capsys.readouterr().err
    assert "Registro NO escrito" in err and "servidor_arranca" in err


def test_main_servidor_que_no_arranca_deja_un_registro_de_fallo_temprano(
    esc: Escenario, doble: Doble, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    doble.salud_tras = 10**9
    assert correr_main(esc, doble, "--espera-servidor", "10") == ke.EXIT_INCOMPLETO  # hallazgo, no exito
    registro = json.loads(esc.salida.read_text(encoding="utf-8"))
    assert registro["servidor_arranca"] is False and registro["envio_compila"] is True
    for campo in SIN_SERVIDOR:
        assert registro[campo] is None, campo
    assert registro["informe_sha256"] == hashlib.sha256(esc.informe.read_bytes()).hexdigest()
    informe = json.loads(esc.informe.read_text(encoding="utf-8"))
    assert informe["registro"] == {"clase": "fallo_temprano", "faltan": 0}
    assert esc.sondas()["rendimiento"]["categoria"] == "dependencia_no_medida"
    assert not doble.proceso.esta_vivo and doble.tokens_vistos == []
    assert "HALLAZGO" in capsys.readouterr().err
    res = compuerta(tmp_path, esc.salida.read_bytes())
    assert len(res.problemas) == 1 and "no es viable" in res.problemas[0] and "Ademas" not in res.problemas[0]


def test_main_envio_que_no_compila_deja_un_registro_de_fallo_temprano(
    esc: Escenario, doble: Doble, tmp_path: Path
) -> None:
    doble.manejadores["compila"] = lambda argv: ke.Salida("ok", 4, "", "")
    assert correr_main(esc, doble) == ke.EXIT_INCOMPLETO
    registro = json.loads(esc.salida.read_text(encoding="utf-8"))
    assert registro["envio_compila"] is False and registro["servidor_arranca"] is True
    assert registro["carga_modelo_segundos"] == 4.0 and registro["tokens_por_segundo"] == 50.0
    for campo in SIN_AGENTE:
        assert registro[campo] is None, campo
    assert doble.tokens_vistos == []
    res = compuerta(tmp_path, esc.salida.read_bytes())
    assert len(res.problemas) == 1 and "no es viable" in res.problemas[0] and "Ademas" not in res.problemas[0]


# ---------------------------------------------------------------------------
# D6. Tope global y D7. Que tope recibe cada sonda
# ---------------------------------------------------------------------------


def test_plan_suma_el_caso_peor_y_da_el_tope_global(esc: Escenario) -> None:
    args = ke._parser().parse_args(esc.args("--plan"))
    pasos = ke.plan(args)
    por_nombre = {p.sonda: p for p in pasos}
    assert por_nombre["servidor"].espera_segundos == ke.ESPERA_SERVIDOR == 1200.0
    assert por_nombre["agente:16384"].espera_segundos == 4 * 15 * 60
    assert por_nombre["calibracion"].espera_segundos == 240
    assert por_nombre["rechazo_calibrado:8192"].espera_segundos == ke.ESPERA_CALIBRADO == 600.0
    assert por_nombre["servidor"].usa_gpu and not por_nombre["docker"].usa_gpu
    total = sum(p.espera_segundos for p in pasos)
    assert total == 60 + 240 + 300 + 1200 + 60 + 360 + 2 * 420 + 240 + 2 * 600 + 2 * 3600 + 90 == 11790
    assert ke.tope_global(args, pasos) == total + ke.MARGEN_TOPE_GLOBAL == 12390
    texto = ke.texto_del_plan(pasos, ke.tope_global(args, pasos))
    assert "196 min de sesion" in texto and "Tope global: 206 min" in texto
    corto = ke._parser().parse_args(
        esc.args("--plan", "--espera-agente-min", "8", "--espera-servidor", "600", "--tope-total-min", "90")
    )
    assert {p.sonda: p for p in ke.plan(corto)}["agente:8192"].espera_segundos == 4 * 8 * 60
    assert {p.sonda: p for p in ke.plan(corto)}["servidor"].espera_segundos == 600
    assert ke.tope_global(corto, ke.plan(corto)) == 5400


def test_con_tope_recorta_las_esperas_y_no_empieza_nada_tras_el_limite(doble: Doble) -> None:
    doble.puerto_ocupado = ke.Respuesta("ok", 200, b"")
    ent = ke.con_tope(doble.entorno(), doble.t + 30.0)
    assert ent.ejecutar(["nvidia-smi"], 60.0, None).estado == "ok"
    assert ent.ejecutar(["nvidia-smi"], 10.0, None).estado == "ok"
    assert ent.http("GET", "http://127.0.0.1:8000/health", None, 99.0).codigo == 200
    assert doble.esperas == [("nvidia_gpu", 30.0), ("nvidia_gpu", 10.0)]  # el menor de los dos
    assert doble.esperas_http == [("health", 30.0)]
    doble.t += 30.0
    assert ent.ejecutar(["nvidia-smi"], 60.0, None) == ke.Salida("tiempo_agotado", None, "", "")
    assert ent.http("GET", "http://127.0.0.1:8000/health", None, 5.0) == ke.Respuesta(
        "tiempo_agotado", None, b""
    )
    assert len(doble.esperas) == 2 and len(doble.esperas_http) == 1  # nada llego al sistema
    assert ent.reloj() == doble.t and ent.python == "/usr/bin/python3"


def test_main_con_el_tope_global_agotado_corta_y_detiene_todo(esc: Escenario, doble: Doble) -> None:
    """20 s de tope: el servidor arranca a los 4 s y el rendimiento agota el resto."""
    assert correr_main(esc, doble, "--tope-total-min", str(20 / 60)) == ke.EXIT_INCOMPLETO
    sondas = esc.sondas()
    assert sondas["servidor"]["valores"]["arranca"] is True
    assert (sondas["rendimiento"]["estado"], sondas["rendimiento"]["categoria"]) == (
        ke.ERROR,
        "tiempo_agotado",
    )
    for nombre in ("rechazo_sintetico:16384", "calibracion"):
        assert (sondas[nombre]["estado"], sondas[nombre]["categoria"]) == (ke.NO_DISPONIBLE, "tope_global")
    assert doble.tokens_vistos == [] and not esc.salida.exists()
    # la parada y la limpieza no dependen del tope
    assert doble.proceso.eventos == PARADA_COMPLETA
    assert sondas["limpieza"]["valores"] == {"servidor_detenido": True, "procesos_en_gpu": 0}


def test_main_el_tope_global_acorta_la_espera_del_servidor(esc: Escenario, doble: Doble) -> None:
    doble.salud_tras = 10**9
    assert correr_main(esc, doble, "--tope-total-min", "0.1") == ke.EXIT_INCOMPLETO  # 6 s
    assert doble.consultas_salud == 3  # a los 0, 2 y 4 s; a los 6 ya no
    assert esc.sondas()["servidor"]["valores"]["motivo"] == "tiempo_agotado"
    assert esc.sondas()["servidor"]["segundos"] == 6.0  # no sigue esperando los 1 200 s de la sonda
    assert not doble.proceso.esta_vivo


@pytest.mark.parametrize("valor", ["0", "-5", "nan"])
def test_main_rechaza_un_tope_global_que_no_es_positivo(esc: Escenario, doble: Doble, valor: str) -> None:
    assert correr_main(esc, doble, "--tope-total-min", valor) == ke.EXIT_INVALIDO
    assert doble.lanzados == [] and not esc.crudo.exists()


def test_cada_sonda_recibe_su_tope(esc: Escenario, doble: Doble) -> None:
    """D7: ni mas ni menos espera que la declarada en el plan, sonda por sonda."""
    doble.rechazos_agente[16384] = 1
    doble.paquetes["docker"] = "7.1.0"
    docker_con(doble, version=Doble.ok("Docker 27"))
    assert correr_main(esc, doble, "--espera-agente-min", "9") == ke.EXIT_OK
    assert doble.esperas == [
        ("nvidia_gpu", ke.ESPERA_COMANDO),
        ("docker_version", ke.ESPERA_COMANDO),
        ("docker_info", ke.ESPERA_COMANDO),
        ("docker_imagen", ke.ESPERA_COMANDO),
        ("docker_run", ke.ESPERA_COMANDO),
        ("compila", ke.ESPERA_COMPILAR),
        ("agente", 4 * 9 * 60.0),
        ("agente", 4 * 9 * 60.0),
        ("nvidia_apps", ke.ESPERA_COMANDO),
    ]
    assert (ke.ESPERA_COMANDO, ke.ESPERA_COMPILAR, ke.ESPERA_SALUD) == (60.0, 300.0, 5.0)
    assert doble.esperas_http == [
        *[("health", ke.ESPERA_SALUD)] * 4,
        ("models", ke.ESPERA_COMANDO),
        *[("completions", ke.ESPERA_RENDIMIENTO)] * 3,
        *[("completions", ke.ESPERA_CONTROL), ("completions", ke.ESPERA_RECHAZO)] * 2,
        *[("completions", ke.ESPERA_CALIBRACION)] * 2,
        *[("completions", ke.ESPERA_CALIBRADO)] * 2,
    ]
    assert (ke.ESPERA_RENDIMIENTO, ke.ESPERA_CONTROL, ke.ESPERA_RECHAZO) == (120.0, 300.0, 120.0)
    # y el plan declara esas mismas esperas
    plan = {
        p.sonda: p.espera_segundos
        for p in ke.plan(ke._parser().parse_args(esc.args("--espera-agente-min", "9")))
    }
    assert plan["compila"] == ke.ESPERA_COMPILAR and plan["agente:16384"] == 4 * 9 * 60.0
    assert plan["docker"] == 4 * ke.ESPERA_COMANDO and plan["gpu"] == ke.ESPERA_COMANDO


# ---------------------------------------------------------------------------
# D6. http_real: tope total por peticion y respuestas que no son HTTP
# ---------------------------------------------------------------------------


@pytest.fixture
def escucha() -> Any:
    """Un socket local que atiende una conexion con la funcion que se le pase. No es un servidor HTTP."""
    abiertos: list[socket.socket] = []
    hilos: list[threading.Thread] = []

    def abrir(atender: Callable[[socket.socket], None]) -> int:
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        abiertos.append(s)

        def trabajo() -> None:
            try:
                conexion, _ = s.accept()
            except OSError:
                return
            with conexion, contextlib.suppress(OSError):
                conexion.settimeout(0.3)
                with contextlib.suppress(TimeoutError):
                    while conexion.recv(65536):  # la peticion entera, llegue en los trozos que llegue
                        pass
                conexion.settimeout(None)
                atender(conexion)

        hilo = threading.Thread(target=trabajo, daemon=True)
        hilo.start()
        hilos.append(hilo)
        return int(s.getsockname()[1])

    yield abrir
    for s in abiertos:
        s.close()


def test_http_real_tiene_un_tope_total_y_no_solo_por_operacion(escucha: Any) -> None:
    """Un servidor que gotea un byte cada 0,2 s nunca agota el tope del socket; el total si."""

    def gotear(conexion: socket.socket) -> None:
        conexion.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 100000\r\n\r\n")
        for _ in range(100):
            conexion.sendall(b"x")
            time.sleep(0.2)

    puerto = escucha(gotear)
    inicio = time.monotonic()
    r = ke.http_real("GET", f"http://127.0.0.1:{puerto}/health", None, 1.5)
    assert r == ke.Respuesta("tiempo_agotado", None, b"")
    assert time.monotonic() - inicio < 6


def test_http_real_respuesta_que_no_es_http(escucha: Any) -> None:
    puerto = escucha(lambda conexion: conexion.sendall(b"esto no es HTTP\r\n\r\n"))
    r = ke.http_real("GET", f"http://127.0.0.1:{puerto}/health", None, 10.0)
    assert r == ke.Respuesta("protocolo", None, b"")
    assert ke._fallo_http(r) == ke.sin_valor(ke.ERROR, "respuesta_http_invalida")


def test_http_real_lee_el_codigo_y_el_cuerpo_tambien_de_un_400(escucha: Any) -> None:
    cuerpo = b'{"error": "maximum context length"}'
    cabecera = f"HTTP/1.1 400 Bad Request\r\nContent-Length: {len(cuerpo)}\r\nConnection: close\r\n\r\n"
    puerto = escucha(lambda conexion: conexion.sendall(cabecera.encode() + cuerpo))
    r = ke.http_real("POST", f"http://127.0.0.1:{puerto}/v1/chat/completions", b"{}", 10.0)
    assert r == ke.Respuesta("ok", 400, cuerpo)


def test_http_real_no_se_traga_un_error_del_propio_guion(monkeypatch: pytest.MonkeyPatch) -> None:
    def rota(*a: Any, **k: Any) -> ke.Respuesta:
        raise RuntimeError("defecto")

    monkeypatch.setattr(ke, "_peticion_http", rota)
    with pytest.raises(RuntimeError, match="defecto"):
        ke.http_real("GET", "http://127.0.0.1:9/health", None, 5.0)


# ---------------------------------------------------------------------------
# D10. Escritura exclusiva: la carrera entre comprobar y crear
# ---------------------------------------------------------------------------


def test_escritura_exclusiva_si_el_archivo_aparece_tras_la_comprobacion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destino = tmp_path / "registro.json"
    destino.write_bytes(b"de otra sesion")
    monkeypatch.setattr(Path, "exists", lambda self: False)  # la comprobacion previa no lo vio
    with pytest.raises(ke.EnsayoError, match="no sobrescribe"):
        ke.escribir_sin_sobrescribir(destino, b"mio")
    monkeypatch.undo()
    assert destino.read_bytes() == b"de otra sesion"
    assert [p.name for p in tmp_path.iterdir()] == ["registro.json"]


def test_escritura_exclusiva_sin_enlaces_duros_tampoco_pisa(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destino = tmp_path / "registro.json"
    destino.write_bytes(b"de otra sesion")

    def sin_enlaces(origen: Any, final: Any) -> None:
        raise OSError("este sistema de archivos no enlaza")

    monkeypatch.setattr(ke.os, "link", sin_enlaces)
    monkeypatch.setattr(Path, "exists", lambda self: False)
    with pytest.raises(ke.EnsayoError, match="no sobrescribe"):
        ke.escribir_sin_sobrescribir(destino, b"mio")
    monkeypatch.undo()
    assert destino.read_bytes() == b"de otra sesion"
    assert [p.name for p in tmp_path.iterdir()] == ["registro.json"]


def _adaptador(raiz: Path, nombre: str, config: str) -> tuple[str, Path]:
    directorio = raiz / "adapters" / nombre
    directorio.mkdir(parents=True)
    (directorio / "adapter_config.json").write_text(config, encoding="utf-8")
    return nombre, directorio


@pytest.mark.parametrize(
    ("configs", "esperado"),
    [
        (['{"r": 4}', '{"r": 4}'], ("2", "8")),
        (['{"r": 16}'], ("1", "16")),
        (['{"r": 20}', '{"r": 4}'], ("2", "32")),
        (['{"r": 4}', "no es json"], ("2", "128")),
        (['{"r": true}'], ("1", "128")),
    ],
)
def test_parametros_lora_reservan_lo_que_trae_el_envio(
    tmp_path: Path, configs: list[str], esperado: tuple[str, str]
) -> None:
    adaptadores = [_adaptador(tmp_path, f"a{i}", c) for i, c in enumerate(configs)]
    assert ke.parametros_lora(adaptadores) == (
        "--enable-lora",
        "--max-loras",
        esperado[0],
        "--max-lora-rank",
        esperado[1],
    )


def test_sin_adaptadores_el_servidor_no_activa_lora(tmp_path: Path) -> None:
    orden = ke.real(ke.comando_servidor("python", ke.ConfigServidor(tmp_path, (), 8000)))
    assert "--enable-lora" not in orden and "--lora-modules" not in orden
    assert orden[orden.index("--dtype") + 1] == "bfloat16"
    assert orden[orden.index("--gpu-memory-utilization") + 1] == "0.9"


def _opciones(orden: list[str]) -> dict[str, str | bool]:
    opciones: dict[str, str | bool] = {}
    i = 0
    while i < len(orden):
        if orden[i].startswith("--"):
            con_valor = i + 1 < len(orden) and not orden[i + 1].startswith("--")
            opciones[orden[i]] = orden[i + 1] if con_valor else True
            i += 2 if con_valor else 1
        else:
            i += 1
    return opciones


@pytest.mark.parametrize("rangos", [(), (4, 4), (16,)])
def test_la_orden_del_servidor_es_la_del_arnes(tmp_path: Path, rangos: tuple[int, ...]) -> None:
    """Con el arnés instalado, toda opción que arma ``VllmServer.build_cmd`` está igual en este guion."""
    adk = pytest.importorskip("adk_submission")
    envio = tmp_path / "envio"
    envio.mkdir()
    for i, r in enumerate(rangos):
        _nombre, directorio = _adaptador(envio, f"lora{i}", json.dumps({"r": r, "peft_type": "LORA"}))
        (directorio / "adapter_model.safetensors").write_bytes(b"")
    manifiesto = adk.discover_adapters(str(envio)) if rangos else None
    config = adk.VllmConfig(
        model="/modelo",
        port=8000,
        host="127.0.0.1",
        tool_call_parser="gemma4",
        reasoning_parser="gemma4",
        max_model_len=32768,
        dtype="bfloat16",
        gpu_memory_utilization=0.90,
        enable_auto_tool_choice=True,
        enable_lora=True,
        max_loras=8,
        max_lora_rank=128,
        tensor_parallel_size=4,
    )
    del_arnes = _opciones([str(x) for x in adk.VllmServer(config, adapter_manifest=manifiesto).build_cmd()])
    propio = _opciones(
        ke.real(
            ke.comando_servidor(
                "python", ke.ConfigServidor(Path("/modelo"), ke.descubrir_adaptadores(envio), 8000)
            )
        )
    )
    for opcion, valor in del_arnes.items():
        if opcion in ("--model", "--lora-modules"):
            continue
        assert propio.get(opcion) == valor, opcion
    assert set(propio) - set(del_arnes) == {"--served-model-name"}
