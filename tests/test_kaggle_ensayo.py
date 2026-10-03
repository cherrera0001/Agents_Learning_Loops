"""Pruebas de scripts/kaggle_ensayo.py con dobles: ni servidores, ni Docker, ni GPU, ni red.

Todo es sintetico e inventado. Los textos «envenenados» simulan lo que traeria un log, un cuerpo de
error, un ``tasks.jsonl`` o un resultado del arnes, y sirven para comprobar que no llegan a los dos
archivos versionables (el registro de la compuerta y el informe de sondas).
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
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
    ) -> None:
        self.pid = pid
        self.esta_vivo = True
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

    def esperar(self, segundos: float) -> bool:
        self.eventos.append(f"esperar:{segundos:g}")
        return not self.esta_vivo


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
        if len(contenido) > 100_000:
            error = {"error": {"message": RECHAZO_400, "type": "BadRequestError", "code": 400}}
            return ke.Respuesta("ok", 400, json.dumps(error).encode())
        self.t += self.latencia
        respuesta = {
            "choices": [{"message": {"content": POISON_RESPUESTA}}],
            "usage": {"prompt_tokens": 30, "completion_tokens": self.tokens_generados},
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
)


@pytest.mark.parametrize("clave", sorted(kaggle_prereg.ENSAYO))
def test_esquema_propio_decide_igual_que_el_de_la_compuerta(clave: str) -> None:
    for valor in VALORES_DE_PRUEBA:
        if clave == "fecha" and valor == "2026-13-40":
            continue  # la compuerta ademas interpreta la fecha; aqui solo se comprueba la forma
        assert bool(ke.ESQUEMA[clave](valor)) == bool(kaggle_prereg.ENSAYO[clave](valor)), (clave, valor)


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
        "--gpu-memory-utilization",
        "0.80",
        "--tensor-parallel-size",
        "4",
        "--enable-auto-tool-choice",
        "--tool-call-parser",
        "gemma4",
        "--reasoning-parser",
        "gemma4",
        "--default-chat-template-kwargs",
        '{"enable_thinking": true}',
        "--enable-lora",
        "--max-loras",
        "8",
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
    assert [u for _, u, _ in doble.peticiones] == ["http://127.0.0.1:8000/health"] * 4
    assert r.comandos == (ke.publico(ke.comando_servidor("x", cfg)),)


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


def test_guardia_termina_y_no_mata_si_basta() -> None:
    guardia = ke.Guardia()
    assert guardia.detener() is True  # sin proceso no hay nada que hacer
    p = ProcesoFalso()
    guardia.asignar(p)
    assert guardia.detener() is True
    assert p.eventos == ["terminar", f"esperar:{ke.GRACIA_TERMINAR:g}"]
    assert guardia.proceso is None
    assert guardia.detener() is True and p.eventos.count("terminar") == 1  # idempotente


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


def agente(
    doble: Doble, crudo: ke.Crudo, esc: Escenario, max_tokens: int = 16384, **cambios: Any
) -> ke.Parcial:
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
        "100",
        "--max-turns",
        "500",
        "--timeout-seconds",
        "300",
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
        "rechazos_por_contexto": 0,
        "errores_de_verificacion": 0,
        "max_time_minutes": 5,
    }
    texto = json.dumps([dict(r.valores), dict(r.privado), r.comandos])
    assert not any(p in texto for p in POISON_TODOS)
    assert not any(i in texto for i in ELEGIDAS)


def test_sonda_agente_cuenta_los_rechazos_por_contexto(doble: Doble, crudo: ke.Crudo, esc: Escenario) -> None:
    doble.rechazos_agente[16384] = 2
    doble.error_extra[16384] = "Failed to apply test_patch: x"
    r = agente(doble, crudo, esc)
    assert (r.valores["rechazos_por_contexto"], r.valores["errores_de_verificacion"]) == (2, 1)
    assert r.valores["turnos_por_tarea"] == [3, 7, 9, 12]


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


@pytest.mark.parametrize("arg", ["--port", "8000", '{"enable_thinking": true}', "{{.Id}}", "a" * 200, "0.80"])
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


def test_el_informe_no_se_construye_con_una_cadena_de_log() -> None:
    envenenado = ke.Resultado("gpu", ke.medido({"modelos": [f"NVIDIA L4\n{POISON_LOG}"]}), 0.1)
    with pytest.raises(RuntimeError):
        ke.construir_informe(
            [envenenado], fecha="2026-10-06", registro_sha256=None, faltan=[], servidor_detenido=True
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


def resultados_completos(**cambios: ke.Resultado) -> list[ke.Resultado]:
    base = {
        "docker": ke.medido({"disponible": False, "motivo": "binario_ausente", "backend": "subprocess"}),
        "sesion": ke.medido({"horas": 12.0, "origen": "declarada", "fuente": "x"}),
        "compila": ke.medido({"compila": True}),
        "servidor": ke.medido({"arranca": True, "carga_segundos": 480.5, "guion_sha256": "a" * 64}),
        "modelo": ke.medido({"id": ke.MODELO, "version": "2", "adaptadores_servidos": 2}),
        "rendimiento": ke.medido({"tokens_por_segundo": 34.0}),
        "agente:16384": ke.medido(
            {
                "backend": "subprocess",
                "turnos_por_tarea": [3, 7, 9, 12],
                "peticiones_al_modelo": 31,
                "rechazos_por_contexto": 0,
                "max_time_minutes": 5,
            }
        ),
        "agente:8192": ke.sin_valor(ke.NO_DISPONIBLE, "no_necesaria"),
    }
    out = [ke.Resultado(n, p, 1.0) for n, p in base.items()]
    return [cambios.get(r.sonda, r) for r in out]


REGISTRO_ESPERADO: dict[str, Any] = {
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
    "peticiones_al_modelo": 31,
    "rechazos_por_contexto": {"16384": 0},
}


def construir(resultados: Sequence[ke.Resultado], notebook: str | None = "cherrera0001/ensayo-a0 v1") -> Any:
    return ke.construir_registro(resultados, fecha="2026-10-06", notebook=notebook)


def test_registro_completo_tiene_exactamente_el_esquema_de_la_compuerta() -> None:
    registro, faltan = construir(resultados_completos())
    assert faltan == []
    assert registro == REGISTRO_ESPERADO
    assert list(registro) == list(REGISTRO_ESPERADO)
    assert set(registro) == set(kaggle_prereg.ENSAYO)
    assert all(ok(registro[k]) for k, ok in kaggle_prereg.ENSAYO.items())
    assert ke.validar_registro(registro) == []


@pytest.mark.parametrize(
    ("sonda", "campos"),
    [
        ("docker", ["docker_disponible"]),
        ("sesion", ["sesion_max_horas"]),
        ("compila", ["envio_compila"]),
        ("servidor", ["guion_servidor_sha256", "servidor_arranca", "carga_modelo_segundos"]),
        ("modelo", ["modelo", "modelo"]),
        ("rendimiento", ["tokens_por_segundo"]),
        (
            "agente:16384",
            [
                "backend",
                "max_time_minutes_ensayo",
                "turnos_por_tarea",
                "peticiones_al_modelo",
                "rechazos_por_contexto[16384]",
            ],
        ),
    ],
)
@pytest.mark.parametrize("estado", [ke.NO_DISPONIBLE, ke.ERROR, "ausente"])
def test_sin_una_medida_no_hay_registro(sonda: str, campos: list[str], estado: str) -> None:
    if estado == "ausente":
        resultados = [r for r in resultados_completos() if r.sonda != sonda]
    else:
        categoria = "dependencia_no_medida" if estado == ke.NO_DISPONIBLE else "tiempo_agotado"
        resultados = resultados_completos(
            **{sonda: ke.Resultado(sonda, ke.sin_valor(estado, categoria), 0.0)}
        )
    registro, faltan = construir(resultados)
    assert registro is None
    assert [f.split(" (")[0] for f in faltan] == campos
    assert all(f"sonda {sonda}: {estado}" in f for f in faltan)


def test_servidor_que_no_arranca_no_tiene_tiempo_de_carga_y_no_hay_registro() -> None:
    """El esquema exige un numero de segundos; sin arranque no existe y no se inventa un 0."""
    parado = ke.Resultado(
        "servidor", ke.medido({"arranca": False, "motivo": "tiempo_agotado", "guion_sha256": "a" * 64}), 9.0
    )
    registro, faltan = construir(resultados_completos(servidor=parado))
    assert registro is None
    assert faltan == ["carga_modelo_segundos (sonda servidor: sin ese valor)"]


@pytest.mark.parametrize("notebook", [None, "", f"nb {POISON_LOG}\n", "/kaggle/working/nb"])
def test_sin_notebook_declarado_no_hay_registro(notebook: str | None) -> None:
    registro, faltan = construir(resultados_completos(), notebook)
    assert registro is None and len(faltan) == 1 and faltan[0].startswith("notebook")


def con_rechazos(n_kit: int, segundo: ke.Parcial) -> list[ke.Resultado]:
    kit = ke.medido(
        {
            "backend": "subprocess",
            "turnos_por_tarea": [3, 7, 9, 12],
            "peticiones_al_modelo": 31,
            "rechazos_por_contexto": n_kit,
            "max_time_minutes": 5,
        }
    )
    return resultados_completos(
        **{
            "agente:16384": ke.Resultado("agente:16384", kit, 1.0),
            "agente:8192": ke.Resultado("agente:8192", segundo, 1.0),
        }
    )


def test_con_rechazos_el_registro_exige_el_segundo_candidato() -> None:
    registro, faltan = construir(con_rechazos(2, ke.sin_valor(ke.ERROR, "tiempo_agotado")))
    assert registro is None
    assert faltan == ["rechazos_por_contexto[8192] (sonda agente:8192: error)"]
    segundo = ke.medido({"rechazos_por_contexto": 0, "turnos_por_tarea": [1, 1, 1, 1]})
    registro, faltan = construir(con_rechazos(2, segundo))
    assert faltan == []
    assert registro["rechazos_por_contexto"] == {"16384": 2, "8192": 0}
    # turnos y peticiones son los del kit original, no los de la repeticion
    assert registro["turnos_por_tarea"] == [3, 7, 9, 12] and registro["peticiones_al_modelo"] == 31
    registro, _ = construir(con_rechazos(1, ke.medido({"rechazos_por_contexto": 3})))
    assert registro["rechazos_por_contexto"] == {"16384": 1, "8192": 3}


def test_sin_rechazos_no_se_lee_el_segundo_candidato() -> None:
    registro, faltan = construir(con_rechazos(0, ke.medido({"rechazos_por_contexto": 4})))
    assert faltan == [] and registro["rechazos_por_contexto"] == {"16384": 0}


def test_un_registro_que_no_pasa_su_esquema_no_se_devuelve() -> None:
    malo = ke.Resultado("rendimiento", ke.medido({"tokens_por_segundo": -1.0}), 0.0)
    with pytest.raises(RuntimeError, match="tokens_por_segundo"):
        construir(resultados_completos(rendimiento=malo))


def test_validar_registro() -> None:
    assert ke.validar_registro(REGISTRO_ESPERADO) == []
    assert ke.validar_registro([]) == ["el registro no es un objeto"]
    assert "claves" in ke.validar_registro({**REGISTRO_ESPERADO, "extra": 1})[0]
    sin_una = {k: v for k, v in REGISTRO_ESPERADO.items() if k != "backend"}
    assert "claves" in ke.validar_registro(sin_una)[0]
    assert ke.validar_registro({**REGISTRO_ESPERADO, "backend": "otro"}) == ["valor invalido en backend"]


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


@pytest.mark.parametrize(
    ("cambios", "fragmento"),
    [
        ({"turnos_por_tarea": [4, 4, 4, 9]}, "no es viable"),
        ({"servidor_arranca": False}, "no es viable"),
        ({"envio_compila": False}, "no es viable"),
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
    ],
)
def test_la_compuerta_rechaza_el_registro_alterado(
    esc: Escenario, doble: Doble, tmp_path: Path, cambios: dict[str, Any], fragmento: str
) -> None:
    assert correr_main(esc, doble) == ke.EXIT_OK
    res = compuerta(tmp_path, alterar(esc.salida.read_bytes(), **cambios))
    assert len(res.problemas) == 1 and fragmento in res.problemas[0]


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


def test_la_compuerta_acepta_la_repeticion_con_el_segundo_candidato(
    esc: Escenario, doble: Doble, tmp_path: Path
) -> None:
    doble.rechazos_agente[16384] = 1
    assert correr_main(esc, doble) == ke.EXIT_OK
    registro = json.loads(esc.salida.read_text(encoding="utf-8"))
    assert registro["rechazos_por_contexto"] == {"16384": 1, "8192": 0}
    assert registro["turnos_por_tarea"] == [3, 7, 9, 12]
    assert doble.tokens_vistos == [16384, 8192]
    assert compuerta(tmp_path, esc.salida.read_bytes()).problemas == []
    fijos = kaggle_prereg.load_params(kaggle_prereg.DEFAULT_PARAMS)["fijos"]
    assert kaggle_prereg.output_tokens(fijos, registro) == 8192


# ---------------------------------------------------------------------------
# main() de punta a punta
# ---------------------------------------------------------------------------


def test_main_de_punta_a_punta(esc: Escenario, doble: Doble, capsys: pytest.CaptureFixture[str]) -> None:
    assert correr_main(esc, doble) == ke.EXIT_OK
    registro = json.loads(esc.salida.read_text(encoding="utf-8"))
    cfg = cfg_de(esc)
    assert registro == {
        "schema_version": "kaggle-notebook-trial/1",
        "fecha": "2026-10-06",
        "notebook": "cherrera0001/ensayo-a0 v1",
        "modelo": "gemma-4-31b-it-qat-w4a16-ct@2",
        "guion_servidor_sha256": ke.hash_guion_servidor(cfg),
        "docker_disponible": False,
        "backend": "subprocess",
        "servidor_arranca": True,
        "envio_compila": True,
        "carga_modelo_segundos": 4.0,  # /health responde a la tercera consulta: dos pausas de 2 s
        "sesion_max_horas": 12.0,
        "tokens_por_segundo": 50.0,
        "max_time_minutes_ensayo": 5,
        "turnos_por_tarea": [3, 7, 9, 12],
        "peticiones_al_modelo": 31,
        "rechazos_por_contexto": {"16384": 0},
    }
    informe = json.loads(esc.informe.read_text(encoding="utf-8"))
    assert informe["schema_version"] == "kaggle-notebook-trial-probes/1"
    assert informe["fecha"] == "2026-10-06" and informe["servidor_detenido"] is True
    assert informe["registro"] == {
        "escrito": True,
        "faltan": 0,
        "sha256": hashlib.sha256(esc.salida.read_bytes()).hexdigest(),
    }
    sondas = esc.sondas()
    assert sondas["agente:8192"]["categoria"] == "no_necesaria"
    assert sondas["version:docker"]["categoria"] == "paquete_ausente"
    assert sondas["gpu"]["valores"]["cantidad"] == 4
    assert sondas["limpieza"]["valores"] == {"servidor_detenido": True, "procesos_en_gpu": 0}
    assert sondas["rechazo_sintetico:16384"]["valores"]["rechazado"] is True
    assert sondas["rechazo_sintetico:8192"]["valores"]["http"] == 400
    for s in sondas.values():
        assert s["estado"] in ke.ESTADOS
        assert (s["categoria"] is None) == (s["estado"] == ke.MEDIDO)
        assert bool(s["valores"]) == (s["estado"] == ke.MEDIDO)
        assert isinstance(s["segundos"], float) and s["segundos"] >= 0
    assert sondas["servidor"]["segundos"] == 4.0 and sondas["rendimiento"]["segundos"] == 30.0
    # el servidor se detuvo, una sola vez, y despues de la ultima sonda que lo usa
    assert doble.proceso.eventos == ["terminar", f"esperar:{ke.GRACIA_TERMINAR:g}"]
    assert len(doble.lanzados) == 1 and doble.tokens_vistos == [16384]
    assert Doble.tipo(doble.comandos[-1]) == "nvidia_apps"
    salida = capsys.readouterr()
    assert "Registro escrito: ensayo_notebook_v1.json" in salida.out
    assert not any(p in salida.out + salida.err for p in POISON_TODOS)


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


def test_el_volcado_crudo_guarda_el_detalle(esc: Escenario, doble: Doble) -> None:
    assert correr_main(esc, doble) == ke.EXIT_OK
    nombres = sorted(p.name for p in esc.crudo.iterdir())
    assert "servidor.log" in nombres and "agente_16384" in nombres
    sondas = json.loads(
        next(p for p in esc.crudo.iterdir() if p.name.endswith("_sondas.json")).read_text("utf-8")
    )
    tareas = next(r for r in sondas["resultados"] if r["sonda"] == "tareas")
    assert tareas["privado"] == {"ids": ELEGIDAS}
    assert sondas["faltan"] == []
    comando = json.loads(
        next(p for p in esc.crudo.iterdir() if p.name.endswith("_gpu.json")).read_text("utf-8")
    )
    assert comando["argv"][0] == "nvidia-smi" and POISON_LOG in comando["stderr"]


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
    assert "vllm.entrypoints.openai.api_server" in salida and "--gpu-memory-utilization 0.80" in salida
    assert "--max-time-minutes 5 --max-tool-calls 100 --max-turns 500 --timeout-seconds 300" in salida
    assert str(esc.raiz) not in salida and "kaggle/input" not in salida
    assert not esc.crudo.exists() and not esc.salida.exists() and not esc.informe.exists()


def test_plan_suma_el_caso_peor(esc: Escenario) -> None:
    args = ke._parser().parse_args(esc.args("--plan"))
    pasos = ke.plan(args)
    por_nombre = {p.sonda: p for p in pasos}
    assert por_nombre["servidor"].espera_segundos == ke.ESPERA_SERVIDOR == 1200.0
    assert por_nombre["agente:16384"].espera_segundos == 4 * 15 * 60
    assert por_nombre["servidor"].usa_gpu and not por_nombre["docker"].usa_gpu
    total = sum(p.espera_segundos for p in pasos)
    assert total == 60 + 240 + 300 + 1200 + 60 + 360 + 2 * 420 + 2 * 3600 + 90
    texto = ke.texto_del_plan(pasos)
    assert f"{total / 60:.0f} min de sesion" in texto
    corto = ke.plan(
        ke._parser().parse_args(esc.args("--plan", "--espera-agente-min", "8", "--espera-servidor", "600"))
    )
    assert {p.sonda: p for p in corto}["agente:8192"].espera_segundos == 4 * 8 * 60
    assert {p.sonda: p for p in corto}["servidor"].espera_segundos == 600


def test_plan_solo_anfitrion_y_sin_agente(esc: Escenario) -> None:
    anfitrion = ke.plan(ke._parser().parse_args(esc.args("--solo-anfitrion")))
    assert not any(p.usa_gpu for p in anfitrion) and anfitrion[-1].sonda == "tareas"
    sin_agente = [p.sonda for p in ke.plan(ke._parser().parse_args(esc.args("--sin-agente")))]
    assert "agente:16384" not in sin_agente and "servidor" in sin_agente and sin_agente[-1] == "limpieza"


def test_main_solo_anfitrion_no_lanza_el_servidor_ni_escribe_registro(esc: Escenario, doble: Doble) -> None:
    assert correr_main(esc, doble, "--solo-anfitrion") == ke.EXIT_INCOMPLETO
    assert doble.lanzados == [] and doble.peticiones == []
    assert not esc.salida.exists() and esc.informe.exists()
    sondas = esc.sondas()
    assert "servidor" not in sondas and "limpieza" not in sondas
    assert sondas["tareas"]["valores"] == {"tareas": 4}
    informe = json.loads(esc.informe.read_text(encoding="utf-8"))
    assert informe["registro"]["escrito"] is False and informe["registro"]["faltan"] > 0
    assert "sha256" not in informe["registro"]


def test_main_sin_agente_no_escribe_registro_y_detiene_el_servidor(esc: Escenario, doble: Doble) -> None:
    assert correr_main(esc, doble, "--sin-agente") == ke.EXIT_INCOMPLETO
    assert not esc.salida.exists()
    sondas = esc.sondas()
    assert sondas["agente:16384"]["categoria"] == sondas["agente:8192"]["categoria"] == "no_solicitada"
    assert sondas["rendimiento"]["estado"] == ke.MEDIDO
    assert doble.tokens_vistos == [] and not doble.proceso.esta_vivo


def test_main_sin_vllm_no_lanza_nada_y_no_inventa(
    esc: Escenario, doble: Doble, capsys: pytest.CaptureFixture[str]
) -> None:
    doble.paquetes["vllm"] = None
    assert correr_main(esc, doble) == ke.EXIT_INCOMPLETO
    assert doble.lanzados == [] and not esc.salida.exists()
    sondas = esc.sondas()
    for nombre in ("servidor", "modelo", "rendimiento", "rechazo_sintetico:16384", "agente:16384"):
        assert (sondas[nombre]["estado"], sondas[nombre]["categoria"]) == (
            ke.NO_DISPONIBLE,
            "dependencia_no_medida",
        )
        assert sondas[nombre]["valores"] == {}
    assert "limpieza" not in sondas
    err = capsys.readouterr().err
    assert "Registro NO escrito" in err and "carga_modelo_segundos" in err


def test_main_sin_directorio_del_modelo(esc: Escenario, doble: Doble) -> None:
    esc.modelo.rmdir()
    assert correr_main(esc, doble) == ke.EXIT_INCOMPLETO
    assert esc.sondas()["servidor"]["categoria"] == "entrada_ausente" and doble.lanzados == []


def test_main_servidor_que_no_arranca_no_da_registro_y_se_detiene(esc: Escenario, doble: Doble) -> None:
    doble.salud_tras = 10**9
    assert correr_main(esc, doble, "--espera-servidor", "10") == ke.EXIT_INCOMPLETO
    assert not esc.salida.exists()
    sondas = esc.sondas()
    assert sondas["servidor"]["valores"]["arranca"] is False
    assert sondas["rendimiento"]["categoria"] == "dependencia_no_medida"
    assert not doble.proceso.esta_vivo and doble.tokens_vistos == []
    assert sondas["limpieza"]["valores"]["servidor_detenido"] is True


@pytest.mark.parametrize(
    "romper",
    ["kit_alterado", "no_compila", "tareas_ilegibles", "docker_sin_medir"],
)
def test_main_no_corre_el_agente_si_falta_una_condicion_de_a0(
    esc: Escenario, doble: Doble, romper: str
) -> None:
    if romper == "kit_alterado":
        (esc.envio / "agent.yaml").write_text("name: otro\n", encoding="utf-8")
    elif romper == "no_compila":
        doble.manejadores["compila"] = lambda argv: ke.Salida("ok", 4, "", "")
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


def test_main_mata_al_servidor_que_no_obedece(esc: Escenario, doble: Doble) -> None:
    doble.proceso = ProcesoFalso(obedece_terminar=False)
    assert correr_main(esc, doble) == ke.EXIT_OK
    assert doble.proceso.eventos[:3] == ["terminar", f"esperar:{ke.GRACIA_TERMINAR:g}", "matar"]
    assert not doble.proceso.esta_vivo


def test_main_avisa_y_sale_con_1_si_el_servidor_sigue_vivo(
    esc: Escenario, doble: Doble, capsys: pytest.CaptureFixture[str]
) -> None:
    doble.proceso = ProcesoFalso(pid=777, obedece_terminar=False, obedece_matar=False)
    doble.manejadores["nvidia_apps"] = lambda argv: ke.Salida("ok", 0, "777\n778\n779\n780\n", "")
    assert correr_main(esc, doble) == ke.EXIT_INCOMPLETO
    assert doble.proceso.eventos.count("matar") >= 1
    assert "pid 777" in capsys.readouterr().err
    informe = json.loads(esc.informe.read_text(encoding="utf-8"))
    assert informe["servidor_detenido"] is False
    assert esc.sondas()["limpieza"]["valores"] == {"servidor_detenido": False, "procesos_en_gpu": 4}
    assert esc.salida.exists()  # lo medido vale; lo que falla es la limpieza


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
