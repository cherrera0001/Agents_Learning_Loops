"""Ensayo de notebook de la linea base A (issue #103, pre-registro, seccion A.0).

Guion de un solo archivo y solo biblioteca estandar: se sube tal cual a un notebook de Kaggle (Linux,
sin internet) y tambien se importa en las pruebas. Mide cosas que **no son resultados del agente**:
si hay Docker y que backend de sandbox queda, el hardware visible, las versiones, si el servidor del
modelo arranca con los parametros de HARNESS § 3.1 y cuanto tarda, el rendimiento bruto con un prompt
inventado, el observable del rechazo por contexto y, como delimita A.0, los turnos del modelo sobre
cuatro tareas que nunca seran de prueba (las tres primeras de requests por ``instance_id`` y la de
httpx), con el kit original y los limites de A.0. De esas cuatro tareas no se lee ni se guarda si se
resolvieron.

Cada medicion es una **sonda** independiente con un resultado tipado:

* ``medido``: hay valor. «No hay Docker» o «el servidor no arranca» son valores medidos.
* ``no_disponible``: lo que habia que medir no esta al alcance (comando ausente, paquete sin instalar,
  dato no declarado, una sonda previa de la que depende no dio valor).
* ``error``: se intento y fallo (tiempo agotado, salida ilegible, respuesta inesperada).

Los dos ultimos llevan una categoria de una lista cerrada y **ningun valor**: «no pude medir» nunca
se registra como un numero. Una sonda que falla no aborta las demas.

Salidas:

* ``--salida``: el registro ``kaggle-notebook-trial/1`` que valida ``scripts/kaggle_prereg.py``, con
  exactamente sus claves. Solo se escribe si **todas** sus medidas existen; si falta una, no se
  inventa y el guion sale con 1.
* ``--informe``: informe versionable de las sondas (``kaggle-notebook-trial-probes/1``): estado,
  categoria, segundos, valores tipados y la forma publica de cada comando (sin rutas).
* ``--crudo``: volcado crudo (log del servidor, salida de los comandos, cuerpos HTTP, resultados del
  arnes). No se versiona: debe quedar fuera de un repositorio git o en una ruta ignorada.

Ningun texto de log, de error ni de respuesta entra en los dos archivos versionables: solo booleanos,
numeros, hashes y cadenas cortas que pasan una lista blanca. Nada se sobrescribe.

Seguridad: no descarga ni instala nada; solo habla por HTTP con ``127.0.0.1``; de ``tasks.jsonl``
conserva solo ``instance_id`` y ``repo``; de los resultados del arnes, solo el identificador, los
turnos y el texto del error, que clasifica y descarta. El servidor que arranca se detiene siempre,
tambien si una sonda falla a mitad o se interrumpe el guion.

Codigos de salida:

* 0  registro escrito y servidor detenido (o ``--plan``).
* 1  ensayo terminado sin registro (falta alguna medida) o con un proceso del servidor aun vivo.
* 2  entrada invalida, archivo de salida existente o ``--crudo`` en una ruta versionable.
* 3  error inesperado del guion (se imprime el tipo y el punto, no el texto de la excepcion).

Documento de uso: ``experiments/gemma_developer_agent/docs/ensayo_notebook.md``.
"""

from __future__ import annotations

import argparse
import atexit
import contextlib
import hashlib
import json
import math
import os
import platform
import re
import shutil
import signal
import statistics
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import partial
from importlib import metadata
from pathlib import Path
from typing import Any, Protocol

ESQUEMA_REGISTRO = "kaggle-notebook-trial/1"
ESQUEMA_INFORME = "kaggle-notebook-trial-probes/1"

EXIT_OK = 0
EXIT_INCOMPLETO = 1
EXIT_INVALIDO = 2
EXIT_INESPERADO = 3

# --- Fijado por el pre-registro (A.0 y bloque ``fijos``); las pruebas lo cruzan con linea_base_a.json.
MODELO = "gemma-4-31b-it-qat-w4a16-ct"
CANDIDATOS_TOKENS: tuple[int, ...] = (16384, 8192)
MAX_TIME_MINUTES = 5
MAX_TOOL_CALLS = 100
MAX_TURNS = 500
TIMEOUT_SECONDS = 300
REPO_TRES_PRIMERAS = "psf/requests"
REPO_UNICA = "encode/httpx"
TAREAS_DEL_PRIMERO = 3
BACKENDS = ("docker", "subprocess")
ARCHIVO_MUESTREO = "configs/sampling.yaml"

# --- Parametros del servidor del modelo (HARNESS § 3.1), en la forma de opciones de vLLM.
CONTEXTO_MAXIMO = 32768
HOST = "127.0.0.1"
PARAMETROS_SERVIDOR: tuple[str, ...] = (
    "--max-model-len",
    str(CONTEXTO_MAXIMO),
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
)
PARAMETROS_LORA: tuple[str, ...] = ("--enable-lora", "--max-loras", "8", "--max-lora-rank", "128")
# Variables que el guion fija al servidor y al arnes para que nada salga a internet.
VARIABLES_SIN_RED: tuple[tuple[str, str], ...] = (
    ("HF_HUB_OFFLINE", "1"),
    ("TRANSFORMERS_OFFLINE", "1"),
    ("VLLM_NO_USAGE_STATS", "1"),
    ("DO_NOT_TRACK", "1"),
    ("LITELLM_LOCAL_MODEL_COST_MAP", "True"),
)

# --- Rechazo por contexto y errores del arnes: las mismas listas cerradas que scripts/kaggle_replicas.py
# (este archivo no puede importarlo en el notebook; las pruebas comprueban que coinciden).
CONTEXT_ERROR_PREFIX = "Sandbox execution error:"
CONTEXT_ERROR_MARKERS: tuple[str, ...] = ("contextwindowexceedederror", "maximum context length")
AGENT_ERROR_PREFIXES: tuple[str, ...] = (
    "Agent exceeded session timeout (",
    "Agent exceeded turns budget (",
    "Agent exceeded maximum allowed LLM turns",
    "Agent exceeded tool call budget (",
    "Agent completed execution without calling submit_patch.",
    "Failed to apply agent patch:",
    "Missing or empty JUnit XML report",
    "Malformed JUnit XML report:",
    "No <testsuite> elements found in JUnit XML",
    "No passing tests recorded in JUnit XML (",
    "Test failures/errors recorded in JUnit XML (",
    "Required test node did not pass:",
    "Pytest stdout summary indicates zero or no passing tests",
    "Missing JUnit XML report (possible premature os._exit(0))",
)
# Errores que impiden contar los turnos de una tarea: el agente no llego a correr.
INFRA_FASE_AGENTE: tuple[str, ...] = (
    "Snapshot file not found:",
    "Sandbox execution error:",
    "Evaluation error:",
    "Unexpected evaluation worker error:",
)
# Errores de la fase de verificacion: el agente ya corrio y sus turnos valen.
INFRA_FASE_VERIFICACION: tuple[str, ...] = ("Missing test specification", "Failed to apply test_patch:")

# --- Resultado de una sonda.
MEDIDO = "medido"
NO_DISPONIBLE = "no_disponible"
ERROR = "error"
ESTADOS = (MEDIDO, NO_DISPONIBLE, ERROR)
CATEGORIAS: tuple[str, ...] = (
    # no_disponible
    "comando_ausente",
    "paquete_ausente",
    "fuente_ausente",
    "entrada_ausente",
    "sin_permiso",
    "no_declarada",
    "no_solicitada",
    "no_necesaria",
    "dependencia_no_medida",
    "dependencia_ausente",
    # error
    "tiempo_agotado",
    "comando_fallo",
    "lanzamiento_fallo",
    "salida_ilegible",
    "entrada_ilegible",
    "entrada_inesperada",
    "valor_no_admitido",
    "sin_conexion",
    "respuesta_inesperada",
    "respuesta_corta",
    "control_fallo",
    "infraestructura_arnes",
    "error_sin_categoria",
    "error_inesperado",
)

# --- Esperas (segundos). ``--plan`` las suma para dar el caso peor.
ESPERA_COMANDO = 60.0
ESPERA_COMPILAR = 300.0
ESPERA_SERVIDOR = 1200.0
ESPERA_SALUD = 5.0
INTERVALO_SALUD = 2.0
ESPERA_RENDIMIENTO = 120.0
ESPERA_CONTROL = 300.0
ESPERA_RECHAZO = 120.0
ESPERA_AGENTE_MIN_POR_TAREA = 15.0  # 5 del agente mas montaje y verificacion
GRACIA_TERMINAR = 20.0
GRACIA_MATAR = 10.0

# --- Rendimiento bruto: prompt inventado, no una tarea.
MUESTRAS_RENDIMIENTO = 3
TOKENS_RENDIMIENTO = 512
MIN_TOKENS_RENDIMIENTO = 64
PROMPT_RENDIMIENTO = (
    "Escribe una lista numerada de doscientas frases cortas e inventadas sobre herramientas de "
    "carpinteria. Una frase por linea, sin introduccion ni cierre."
)
PROMPT_CONTROL = "Responde solo con la palabra: listo"
PALABRA_RELLENO = "tornillo "
PALABRAS_RELLENO = 60000  # muy por encima de CONTEXTO_MAXIMO aunque cada palabra fuera un solo token

PAQUETES: tuple[str, ...] = ("vllm", "swegemma", "adk-submission", "adk-eval-core", "google-adk", "docker")
HERRAMIENTAS_ARNES: tuple[str, ...] = (
    "run_command",
    "read_file",
    "edit_file",
    "write_file",
    "get_status",
    "submit_patch",
    "get_code_neighbors",
    "search_similar_code",
    "get_code_subgraph",
)
# Programa que compila el envio en un proceso aparte. Sale con 0 si compila, 3 si el arnes no se
# puede importar y 4 si la compilacion lanza. Su salida va al volcado crudo.
PROGRAMA_COMPILAR = (
    "import sys\n"
    "from pathlib import Path\n"
    "try:\n"
    "    from adk_submission import ToolRegistry, compile_submission\n"
    "    from swegemma.models import setup_gemma_model_registry\n"
    "except Exception:\n"
    "    sys.exit(3)\n"
    "tools = ToolRegistry()\n"
    f"for nombre in {HERRAMIENTAS_ARNES!r}:\n"
    "    tools.register(nombre, lambda **kwargs: None)\n"
    "try:\n"
    "    compile_submission(\n"
    "        submission_dir=Path(sys.argv[1]),\n"
    "        tool_registry=tools,\n"
    "        model_registry=setup_gemma_model_registry(),\n"
    "    )\n"
    "except Exception:\n"
    "    import traceback\n"
    "    traceback.print_exc()\n"
    "    sys.exit(4)\n"
)

SHA_RE = re.compile(r"^[0-9a-f]{64}$")
FECHA_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
ID_SEGURO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,200}$")
NOMBRE_ADAPTADOR = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
VERSION_RE = re.compile(r"^[0-9][0-9A-Za-z.+_-]{0,39}$")
# Lista blanca de toda cadena que entra en un archivo versionable.
TEXTO_SEGURO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._+()@:/=<>-]{0,79}$")
NOMBRE_GPU = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._-]{0,39}$")
RUTA_WINDOWS = re.compile(r"^[A-Za-z]:[\\/]")
ARGUMENTO_OCULTO = "<oculto>"


class EnsayoError(ValueError):
    """Entrada invalida, salida existente o ruta cruda versionable: salida 2."""


# ---------------------------------------------------------------------------
# Dependencias inyectables: todo lo que toca el sistema pasa por ``Entorno``
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Salida:
    """Lo que devolvio un comando. ``estado``: ``ok`` (termino; mirar ``codigo``), ``ausente``,
    ``sin_permiso`` o ``tiempo_agotado``."""

    estado: str
    codigo: int | None
    stdout: str
    stderr: str


@dataclass(frozen=True)
class Respuesta:
    """Respuesta HTTP. ``estado``: ``ok`` (hay ``codigo``), ``sin_conexion`` o ``tiempo_agotado``."""

    estado: str
    codigo: int | None
    cuerpo: bytes


class Proceso(Protocol):
    """Proceso lanzado en segundo plano (el servidor del modelo)."""

    pid: int

    def vivo(self) -> bool: ...

    def terminar(self) -> None: ...

    def matar(self) -> None: ...

    def esperar(self, segundos: float) -> bool: ...


@dataclass(frozen=True)
class Entorno:
    """Acceso al sistema. Las pruebas pasan dobles; ``entorno_real`` da la implementacion real."""

    ejecutar: Callable[[Sequence[str], float, Mapping[str, str] | None], Salida]
    lanzar: Callable[[Sequence[str], Path, Mapping[str, str]], Proceso]
    http: Callable[[str, str, bytes | None, float], Respuesta]
    reloj: Callable[[], float]
    dormir: Callable[[float], None]
    ahora: Callable[[], datetime]
    version_paquete: Callable[[str], str | None]
    leer_texto: Callable[[str], str | None]
    disco_libre: Callable[[str], int | None]
    cpus: Callable[[], int | None]
    variables: Mapping[str, str]
    python: str
    version_python: str


# ---------------------------------------------------------------------------
# Resultado tipado de una sonda
# ---------------------------------------------------------------------------


def _sin_nulos(obj: object) -> bool:
    if obj is None:
        return False
    if isinstance(obj, Mapping):
        return all(_sin_nulos(v) for v in obj.values())
    if isinstance(obj, list | tuple):
        return all(_sin_nulos(v) for v in obj)
    return True


@dataclass(frozen=True)
class Parcial:
    """Lo que devuelve una sonda antes de medirle el tiempo. ``privado`` nunca se versiona."""

    estado: str
    valores: Mapping[str, Any] = field(default_factory=dict)
    categoria: str | None = None
    comandos: tuple[tuple[str, ...], ...] = ()
    privado: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.estado not in ESTADOS:
            raise ValueError(f"estado de sonda desconocido: {self.estado!r}")
        if self.estado == MEDIDO:
            if self.categoria is not None:
                raise ValueError("una sonda medida no lleva categoria")
            if not self.valores or not _sin_nulos(self.valores):
                raise ValueError("una sonda medida lleva valores, y ninguno nulo")
        else:
            if self.categoria not in CATEGORIAS:
                raise ValueError(f"categoria fuera de la lista cerrada: {self.categoria!r}")
            if self.valores:
                raise ValueError("una sonda sin medir no lleva valores")


@dataclass(frozen=True)
class Resultado:
    """Resultado de una sonda: su ``Parcial`` mas el nombre y los segundos que tardo."""

    sonda: str
    parcial: Parcial
    segundos: float

    @property
    def estado(self) -> str:
        return self.parcial.estado

    @property
    def valores(self) -> Mapping[str, Any]:
        return self.parcial.valores

    @property
    def categoria(self) -> str | None:
        return self.parcial.categoria

    def versionable(self) -> dict[str, Any]:
        """Forma que entra en el informe versionable (sin ``privado``)."""
        return {
            "sonda": self.sonda,
            "estado": self.estado,
            "categoria": self.categoria,
            "segundos": self.segundos,
            "valores": _copia(self.valores),
            "comandos": [list(c) for c in self.parcial.comandos],
        }


def _copia(obj: Any) -> Any:
    if isinstance(obj, Mapping):
        return {str(k): _copia(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [_copia(v) for v in obj]
    return obj


def medido(
    valores: Mapping[str, Any],
    comandos: Sequence[Sequence[str]] = (),
    privado: Mapping[str, Any] | None = None,
) -> Parcial:
    return Parcial(MEDIDO, dict(valores), None, tuple(tuple(c) for c in comandos), dict(privado or {}))


def sin_valor(
    estado: str,
    categoria: str,
    comandos: Sequence[Sequence[str]] = (),
    privado: Mapping[str, Any] | None = None,
) -> Parcial:
    return Parcial(estado, {}, categoria, tuple(tuple(c) for c in comandos), dict(privado or {}))


def correr(nombre: str, sonda: Callable[[], Parcial], ent: Entorno) -> Resultado:
    """Ejecuta una sonda y le mide el tiempo. Una excepcion se vuelve ``error_inesperado``.

    Solo captura ``Exception``: una interrupcion (``KeyboardInterrupt``, ``SystemExit``) sigue hacia
    arriba para que el servidor se detenga.
    """
    inicio = ent.reloj()
    try:
        parcial = sonda()
    except Exception as exc:
        parcial = sin_valor(ERROR, "error_inesperado", privado={"excepcion": type(exc).__name__})
    return Resultado(nombre, parcial, round(max(0.0, ent.reloj() - inicio), 3))


def omitida(nombre: str, categoria: str = "dependencia_no_medida") -> Resultado:
    """Resultado de una sonda que no se ejecuto."""
    return Resultado(nombre, sin_valor(NO_DISPONIBLE, categoria), 0.0)


# ---------------------------------------------------------------------------
# Comandos: forma real y forma publica (sin rutas ni identificadores)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Oculto:
    """Argumento cuyo valor real no se versiona; ``etiqueta`` es lo que se publica."""

    valor: str
    etiqueta: str


Token = str | Oculto


def real(tokens: Sequence[Token]) -> list[str]:
    return [t.valor if isinstance(t, Oculto) else t for t in tokens]


def argumento_publicable(texto: str) -> bool:
    """Un argumento literal se publica solo si no parece una ruta ni trae saltos de linea."""
    return not (
        len(texto) > 200
        or "\n" in texto
        or "\r" in texto
        or texto.startswith(("/", "~", "\\"))
        or "/kaggle" in texto.lower()
        or RUTA_WINDOWS.match(texto) is not None
        or "=/" in texto
    )


def publico(tokens: Sequence[Token]) -> tuple[str, ...]:
    """Forma versionable de un comando: etiquetas en vez de rutas; lo dudoso queda ``<oculto>``."""
    out: list[str] = []
    for t in tokens:
        texto = t.etiqueta if isinstance(t, Oculto) else t
        out.append(texto if argumento_publicable(texto) else ARGUMENTO_OCULTO)
    return tuple(out)


def texto_seguro(valor: object) -> bool:
    """Cadena corta de la lista blanca, que no es una ruta."""
    return (
        isinstance(valor, str)
        and TEXTO_SEGURO.fullmatch(valor) is not None
        and "/kaggle" not in valor.lower()
        and ".." not in valor
        and "//" not in valor
    )


def comprobar_versionable(obj: object, *, en: str = "") -> None:
    """Lanza ``RuntimeError`` si ``obj`` contiene algo que no puede versionarse.

    Admite booleanos, numeros finitos, ``None`` y cadenas de la lista blanca. Las listas bajo la clave
    ``comandos`` se comprueban con la regla de los argumentos. Es la ultima barrera: una cadena de un
    log o de un error que llegara hasta aqui detiene la escritura.
    """
    if obj is None or isinstance(obj, bool | int):
        return
    if isinstance(obj, float):
        if not math.isfinite(obj):
            raise RuntimeError(f"valor no finito en {en or 'la raiz'}")
        return
    if isinstance(obj, str):
        if not texto_seguro(obj):
            raise RuntimeError(f"cadena no versionable en {en or 'la raiz'}")
        return
    if isinstance(obj, Mapping):
        for k, v in obj.items():
            if not isinstance(k, str) or not texto_seguro(k):
                raise RuntimeError(f"clave no versionable en {en or 'la raiz'}")
            if k == "comandos":
                _comprobar_comandos(v, f"{en}.{k}")
            else:
                comprobar_versionable(v, en=f"{en}.{k}")
        return
    if isinstance(obj, list | tuple):
        for i, v in enumerate(obj):
            comprobar_versionable(v, en=f"{en}[{i}]")
        return
    raise RuntimeError(f"tipo no versionable en {en or 'la raiz'}: {type(obj).__name__}")


def _comprobar_comandos(obj: object, en: str) -> None:
    if not isinstance(obj, list | tuple):
        raise RuntimeError(f"{en} no es una lista de comandos")
    for comando in obj:
        if not isinstance(comando, list | tuple):
            raise RuntimeError(f"{en} tiene un comando que no es una lista")
        for arg in comando:
            if not isinstance(arg, str) or not argumento_publicable(arg):
                raise RuntimeError(f"argumento no versionable en {en}")


# ---------------------------------------------------------------------------
# Archivos: sin sobrescribir, volcado crudo fuera de git
# ---------------------------------------------------------------------------


def sha256_bytes(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


def a_json(obj: object) -> bytes:
    """JSON estable con saltos de linea LF, en bytes."""
    return (json.dumps(obj, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def escribir_sin_sobrescribir(destino: Path, datos: bytes) -> None:
    """Crea ``destino`` con ``datos`` sin pisar nada: temporal mas enlace, o creacion exclusiva."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    existe = EnsayoError(f"Ya existe {destino.name}: este guion no sobrescribe resultados.")
    if destino.exists():
        raise existe
    fd, nombre = tempfile.mkstemp(dir=destino.parent, prefix=f".{destino.name}.", suffix=".tmp")
    temporal = Path(nombre)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(datos)
        try:
            os.link(temporal, destino)
        except FileExistsError:
            raise existe from None
        except OSError:
            try:
                with open(destino, "xb") as f:
                    f.write(datos)
            except FileExistsError:
                raise existe from None
    finally:
        temporal.unlink(missing_ok=True)


def comprobar_crudo(crudo: Path, ent: Entorno) -> None:
    """``crudo`` no debe existir, y debe quedar fuera de git o en una ruta que git ignore.

    Si no se puede comprobar (git ausente o con error) lanza ``EnsayoError``: «no pude comprobar» no
    es «esta ignorada».
    """
    if crudo.exists():
        raise EnsayoError(f"Ya existe --crudo ({crudo.name}): cada ensayo usa un directorio nuevo.")
    base = crudo.resolve()
    while not base.exists():
        if base.parent == base:
            raise EnsayoError("No hay ningun directorio existente sobre --crudo.")
        base = base.parent
    if not base.is_dir():
        raise EnsayoError("--crudo cuelga de algo que no es un directorio.")
    if not any((p / ".git").exists() for p in (base, *base.parents)):
        return
    sonda = crudo.resolve() / "sonda"
    r = ent.ejecutar(["git", "-C", str(base), "check-ignore", "-q", "--", str(sonda)], ESPERA_COMANDO, None)
    if r.estado == "ok" and r.codigo == 0:
        return
    if r.estado == "ok" and r.codigo == 1:
        raise EnsayoError(
            "--crudo esta dentro de un repositorio y git no la ignora: el volcado crudo no puede "
            "quedar en una ruta versionable."
        )
    raise EnsayoError("No se pudo comprobar con git que --crudo este ignorada.")


class Crudo:
    """Volcado crudo: un archivo por pieza, sin sobrescribir. Aqui si entra el texto de los logs."""

    def __init__(self, raiz: Path) -> None:
        self.raiz = raiz
        self._n = 0

    def crear(self) -> None:
        self.raiz.mkdir(parents=True, exist_ok=False)

    def ruta(self, nombre: str) -> Path:
        return self.raiz / nombre

    def guardar(self, nombre: str, datos: bytes | str) -> None:
        """Guarda una pieza con un prefijo numerico, para que dos piezas no choquen."""
        self._n += 1
        crudos = datos.encode("utf-8", errors="replace") if isinstance(datos, str) else datos
        escribir_sin_sobrescribir(self.raiz / f"{self._n:03d}_{nombre}", crudos)

    def comando(self, nombre: str, argv: Sequence[str], salida: Salida) -> None:
        self.guardar(
            f"{nombre}.json",
            a_json(
                {
                    "argv": list(argv),
                    "estado": salida.estado,
                    "codigo": salida.codigo,
                    "stdout": salida.stdout,
                    "stderr": salida.stderr,
                }
            ),
        )


# ---------------------------------------------------------------------------
# Sondas del anfitrion (no tocan la GPU)
# ---------------------------------------------------------------------------


def sonda_python(ent: Entorno) -> Parcial:
    """Version del interprete del notebook."""
    if not ent.version_python:
        return sin_valor(NO_DISPONIBLE, "fuente_ausente")
    if VERSION_RE.fullmatch(ent.version_python) is None:
        return sin_valor(ERROR, "salida_ilegible")
    return medido({"version": ent.version_python})


def sonda_cpu(ent: Entorno) -> Parcial:
    """Numero de CPU visibles."""
    n = ent.cpus()
    if n is None:
        return sin_valor(NO_DISPONIBLE, "fuente_ausente")
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        return sin_valor(ERROR, "salida_ilegible")
    return medido({"cpus": n})


def sonda_memoria(ent: Entorno) -> Parcial:
    """Memoria total del anfitrion, de ``/proc/meminfo``."""
    texto = ent.leer_texto("/proc/meminfo")
    if texto is None:
        return sin_valor(NO_DISPONIBLE, "fuente_ausente")
    m = re.search(r"^MemTotal:\s+([0-9]+)\s+kB\s*$", texto, re.MULTILINE)
    if m is None:
        return sin_valor(ERROR, "salida_ilegible")
    return medido({"total_mib": int(m.group(1)) // 1024})


def sonda_disco(ent: Entorno, directorio: Path) -> Parcial:
    """Espacio libre donde el ensayo escribe (el directorio que contendra ``--crudo``)."""
    libre = ent.disco_libre(str(directorio))
    if libre is None:
        return sin_valor(NO_DISPONIBLE, "fuente_ausente")
    if isinstance(libre, bool) or not isinstance(libre, int) or libre < 0:
        return sin_valor(ERROR, "salida_ilegible")
    return medido({"libre_mib": libre // (1024 * 1024)})


def sonda_version(ent: Entorno, paquete: str) -> Parcial:
    """Version instalada de un paquete, leida de sus metadatos (no se importa)."""
    version = ent.version_paquete(paquete)
    if version is None:
        return sin_valor(NO_DISPONIBLE, "paquete_ausente")
    if not isinstance(version, str) or VERSION_RE.fullmatch(version) is None:
        return sin_valor(ERROR, "salida_ilegible")
    return medido({"version": version})


def _fallo_de_comando(salida: Salida, comandos: Sequence[Sequence[str]]) -> Parcial | None:
    """``Parcial`` de un comando que no dio una salida utilizable; ``None`` si termino con 0."""
    if salida.estado == "ausente":
        return sin_valor(NO_DISPONIBLE, "comando_ausente", comandos)
    if salida.estado == "sin_permiso":
        return sin_valor(NO_DISPONIBLE, "sin_permiso", comandos)
    if salida.estado == "tiempo_agotado":
        return sin_valor(ERROR, "tiempo_agotado", comandos)
    if salida.estado != "ok" or salida.codigo != 0:
        return sin_valor(ERROR, "comando_fallo", comandos)
    return None


def sonda_gpu(ent: Entorno, crudo: Crudo) -> Parcial:
    """GPU visibles: cuantas, de que modelo y con cuanta memoria."""
    argv = ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"]
    salida = ent.ejecutar(argv, ESPERA_COMANDO, None)
    crudo.comando("gpu", argv, salida)
    comandos = [publico(argv)]
    fallo = _fallo_de_comando(salida, comandos)
    if fallo is not None:
        return fallo
    nombres: list[str] = []
    memorias: list[int] = []
    for linea in (ln.strip() for ln in salida.stdout.splitlines()):
        if not linea:
            continue
        partes = [p.strip() for p in linea.split(",")]
        if len(partes) != 2 or NOMBRE_GPU.fullmatch(partes[0]) is None or not partes[1].isdigit():
            return sin_valor(ERROR, "salida_ilegible", comandos)
        nombres.append(partes[0])
        memorias.append(int(partes[1]))
    if not nombres:
        return sin_valor(ERROR, "salida_ilegible", comandos)
    return medido(
        {"cantidad": len(nombres), "modelos": sorted(set(nombres)), "memoria_total_mib": memorias}, comandos
    )


def sonda_docker(ent: Entorno, crudo: Crudo, imagen: str) -> Parcial:
    """Si hay Docker utilizable para el sandbox, por pasos, y que backend queda.

    ``disponible`` es que el demonio responde. ``backend`` es ``docker`` solo si ademas esta la
    imagen del sandbox, el SDK de Python que usa el arnes y un contenedor sin red arranca; si no,
    ``subprocess``. Un binario ausente o un demonio que no responde son valores medidos.
    """
    comandos: list[tuple[str, ...]] = []

    def paso(nombre: str, tokens: Sequence[Token]) -> Salida:
        salida = ent.ejecutar(real(tokens), ESPERA_COMANDO, None)
        crudo.comando(f"docker_{nombre}", real(tokens), salida)
        comandos.append(publico(tokens))
        return salida

    version = paso("version", ["docker", "--version"])
    if version.estado == "ausente":
        return medido({"disponible": False, "motivo": "binario_ausente", "backend": "subprocess"}, comandos)
    if version.estado != "ok":
        return _fallo_de_comando(version, comandos) or sin_valor(ERROR, "comando_fallo", comandos)
    info = paso("info", ["docker", "info", "--format", "{{.ServerVersion}}"])
    if info.estado != "ok":
        return _fallo_de_comando(info, comandos) or sin_valor(ERROR, "comando_fallo", comandos)
    if info.codigo != 0:
        return medido(
            {"disponible": False, "motivo": "demonio_inaccesible", "backend": "subprocess"}, comandos
        )
    etiqueta = Oculto(imagen, "<imagen>")
    inspeccion = paso("imagen", ["docker", "image", "inspect", "--format", "{{.Id}}", etiqueta])
    if inspeccion.estado != "ok":
        return _fallo_de_comando(inspeccion, comandos) or sin_valor(ERROR, "comando_fallo", comandos)
    imagen_presente = inspeccion.codigo == 0
    sdk = ent.version_paquete("docker") is not None
    contenedor = False
    if imagen_presente:
        prueba = paso("contenedor", ["docker", "run", "--rm", "--network", "none", etiqueta, "true"])
        if prueba.estado != "ok":
            return _fallo_de_comando(prueba, comandos) or sin_valor(ERROR, "comando_fallo", comandos)
        contenedor = prueba.codigo == 0
    return medido(
        {
            "disponible": True,
            "imagen_presente": imagen_presente,
            "sdk_python": sdk,
            "contenedor_arranca": contenedor,
            "backend": "docker" if (imagen_presente and sdk and contenedor) else "subprocess",
        },
        comandos,
    )


def sonda_sesion(horas: float | None, fuente: str | None) -> Parcial:
    """Duracion maxima de una sesion: la declara quien ejecuta, con su fuente.

    Desde dentro del notebook no hay nada fiable de donde inferirla, asi que sin declaracion queda
    ``no_disponible``.
    """
    if horas is None or fuente is None:
        return sin_valor(NO_DISPONIBLE, "no_declarada")
    if isinstance(horas, bool) or not math.isfinite(horas) or not 0 < horas <= 48:
        return sin_valor(ERROR, "valor_no_admitido")
    if not texto_seguro(fuente):
        return sin_valor(ERROR, "valor_no_admitido")
    return medido({"horas": horas, "origen": "declarada", "fuente": fuente})


def _sin_claves_repetidas(pares: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pares:
        if k in out:
            raise ValueError("clave repetida")
        out[k] = v
    return out


def sonda_envio(envio: Path, manifiesto: Path) -> Parcial:
    """El envio es el kit original: mismos archivos y mismos SHA-256 que el manifiesto, ni uno mas."""
    if not envio.is_dir() or not manifiesto.is_file():
        return sin_valor(NO_DISPONIBLE, "entrada_ausente")
    try:
        datos = json.loads(manifiesto.read_text(encoding="utf-8"), object_pairs_hook=_sin_claves_repetidas)
        esperados = {str(f["path"]): str(f["sha256"]).lower() for f in datos["files"]}
    except (OSError, ValueError, KeyError, TypeError):
        return sin_valor(ERROR, "entrada_ilegible")
    if not esperados or not all(SHA_RE.fullmatch(h) for h in esperados.values()):
        return sin_valor(ERROR, "entrada_ilegible")
    presentes = {p.relative_to(envio).as_posix(): p for p in sorted(envio.rglob("*")) if p.is_file()}
    faltan = sum(1 for ruta in esperados if ruta not in presentes)
    sobran = sum(1 for ruta in presentes if ruta not in esperados)
    distintos = 0
    for ruta, esperado in esperados.items():
        if ruta in presentes and sha256_bytes(presentes[ruta].read_bytes()) != esperado:
            distintos += 1
    return medido(
        {
            "archivos_del_manifiesto": len(esperados),
            "faltan": faltan,
            "distintos": distintos,
            "sobran": sobran,
            "coincide": faltan == 0 and distintos == 0 and sobran == 0,
        }
    )


def sonda_compila(ent: Entorno, crudo: Crudo, envio: Path) -> Parcial:
    """Si el envio compila con el compilador del arnes, en un proceso aparte."""
    tokens: list[Token] = [
        Oculto(ent.python, "<python>"),
        "-c",
        Oculto(PROGRAMA_COMPILAR, "<programa de compilacion>"),
        Oculto(str(envio), "<envio>"),
    ]
    salida = ent.ejecutar(real(tokens), ESPERA_COMPILAR, _variables_hijo(ent, None))
    crudo.comando("compila", real(tokens), salida)
    comandos = [publico(tokens)]
    if salida.estado == "ok" and salida.codigo == 4:
        return medido({"compila": False}, comandos)
    if salida.estado == "ok" and salida.codigo == 3:
        return sin_valor(NO_DISPONIBLE, "dependencia_ausente", comandos)
    fallo = _fallo_de_comando(salida, comandos)
    if fallo is not None:
        return fallo
    return medido({"compila": True}, comandos)


def _solo_identidad(pares: list[tuple[str, Any]]) -> dict[str, Any]:
    """Conserva de cada tarea solo ``instance_id`` y ``repo``; lo demas se descarta al leer."""
    return {k: v for k, v in pares if k in ("instance_id", "repo")}


def sonda_tareas(tasks: Path) -> Parcial:
    """Las cuatro tareas de A.0: las tres primeras de requests por ``instance_id`` y la de httpx.

    De ``tasks.jsonl`` no se conserva nada mas que el identificador y el repositorio: el enunciado,
    el parche de referencia y las pruebas se descartan en el propio analizador de JSON.
    """
    if not tasks.is_file():
        return sin_valor(NO_DISPONIBLE, "entrada_ausente")
    por_repo: dict[str, list[str]] = {REPO_TRES_PRIMERAS: [], REPO_UNICA: []}
    try:
        with tasks.open(encoding="utf-8") as f:
            for linea in f:
                if not linea.strip():
                    continue
                obj = json.loads(linea, object_pairs_hook=_solo_identidad)
                iid, repo = obj["instance_id"], obj["repo"]
                if not isinstance(iid, str) or ID_SEGURO.fullmatch(iid) is None or not isinstance(repo, str):
                    return sin_valor(ERROR, "entrada_ilegible")
                if repo in por_repo:
                    por_repo[repo].append(iid)
    except (OSError, ValueError, KeyError, TypeError):
        return sin_valor(ERROR, "entrada_ilegible")
    primeras = sorted(set(por_repo[REPO_TRES_PRIMERAS]))[:TAREAS_DEL_PRIMERO]
    unica = sorted(set(por_repo[REPO_UNICA]))
    if len(primeras) != TAREAS_DEL_PRIMERO or len(unica) != 1 or len(set(primeras) | set(unica)) != 4:
        return sin_valor(ERROR, "entrada_inesperada")
    return medido({"tareas": 4}, privado={"ids": [*primeras, *unica]})


# ---------------------------------------------------------------------------
# Servidor del modelo: comando, arranque y parada garantizada
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConfigServidor:
    """Lo que varia del arranque del servidor: rutas, puerto y opciones extra del operador."""

    modelo_dir: Path
    adaptadores: tuple[tuple[str, Path], ...]
    puerto: int
    extra: tuple[str, ...] = ()

    @property
    def base(self) -> str:
        return f"http://{HOST}:{self.puerto}"


def descubrir_adaptadores(envio: Path) -> tuple[tuple[str, Path], ...]:
    """Adaptadores LoRA del envio: subdirectorios de ``adapters/`` con ``adapter_config.json``."""
    raiz = envio / "adapters"
    if not raiz.is_dir():
        return ()
    out: list[tuple[str, Path]] = []
    for sub in sorted(p for p in raiz.iterdir() if p.is_dir()):
        if (sub / "adapter_config.json").is_file():
            if NOMBRE_ADAPTADOR.fullmatch(sub.name) is None:
                raise EnsayoError("Un adaptador del envio tiene un nombre no admitido.")
            out.append((sub.name, sub))
    return tuple(out)


def comando_servidor(python: str, cfg: ConfigServidor) -> list[Token]:
    """Comando de arranque de vLLM con los parametros de HARNESS § 3.1."""
    tokens: list[Token] = [
        Oculto(python, "<python>"),
        "-m",
        "vllm.entrypoints.openai.api_server",
        "--model",
        Oculto(str(cfg.modelo_dir), "<modelo>"),
        "--served-model-name",
        MODELO,
        "--host",
        HOST,
        "--port",
        str(cfg.puerto),
        *PARAMETROS_SERVIDOR,
    ]
    if cfg.adaptadores:
        tokens.extend(PARAMETROS_LORA)
        tokens.append("--lora-modules")
        tokens.extend(
            Oculto(f"{nombre}={ruta}", f"{nombre}=<envio>:adapters:{nombre}")
            for nombre, ruta in cfg.adaptadores
        )
    tokens.extend(cfg.extra)
    return tokens


def hash_guion_servidor(cfg: ConfigServidor) -> str:
    """SHA-256 del guion de arranque: el comando en su forma publica y las variables que fija.

    No depende de las rutas de la maquina, asi que dos sesiones con los mismos parametros dan el
    mismo hash; cualquier parametro distinto (puerto, opcion extra, adaptador) lo cambia.
    """
    canon = {"argv": list(publico(comando_servidor("python", cfg))), "variables": dict(VARIABLES_SIN_RED)}
    return sha256_bytes(json.dumps(canon, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _variables_hijo(ent: Entorno, cfg: ConfigServidor | None) -> dict[str, str]:
    """Variables de un proceso hijo: las del notebook, sin red y, si hay servidor, apuntando a el."""
    variables = dict(ent.variables)
    variables.update(dict(VARIABLES_SIN_RED))
    if cfg is not None:
        for nombre in ("MODEL_PROXY_URL", "LITELLM_API_BASE", "LOCAL_INFERENCE_URL", "OPENAI_BASE_URL"):
            variables[nombre] = f"{cfg.base}/v1"
        for nombre in ("MODEL_PROXY_API_KEY", "LITELLM_API_KEY", "LOCAL_API_KEY", "OPENAI_API_KEY"):
            variables[nombre] = "EMPTY"
    return variables


class Guardia:
    """Dueno del proceso del servidor: lo que se le entrega se detiene pase lo que pase.

    El proceso se le asigna en cuanto existe, antes de esperar nada, para que una excepcion durante
    el arranque no lo deje huerfano. ``detener`` es idempotente y no lanza.
    """

    def __init__(self) -> None:
        self.proceso: Proceso | None = None
        self.lanzados = 0

    def asignar(self, proceso: Proceso) -> None:
        self.proceso = proceso
        self.lanzados += 1

    def detener(self) -> bool:
        """Termina el proceso; si no muere, lo mata. Devuelve ``True`` si no queda vivo."""
        p = self.proceso
        if p is None:
            return True
        with contextlib.suppress(Exception):
            p.terminar()
        if not self._termino(p, GRACIA_TERMINAR):
            with contextlib.suppress(Exception):
                p.matar()
            self._termino(p, GRACIA_MATAR)
        try:
            vivo = p.vivo()
        except Exception:
            vivo = True  # no se pudo comprobar: no se da por muerto
        if not vivo:
            self.proceso = None
        return not vivo

    @staticmethod
    def _termino(p: Proceso, segundos: float) -> bool:
        try:
            return p.esperar(segundos)
        except Exception:
            return False


def sonda_servidor(
    ent: Entorno, crudo: Crudo, cfg: ConfigServidor, guardia: Guardia, espera: float
) -> Parcial:
    """Si el servidor arranca con los parametros de HARNESS § 3.1 y cuantos segundos tarda.

    El tiempo va desde que se lanza el proceso hasta la primera respuesta 200 de ``/health``. Que el
    proceso termine o que se agote la espera son valores medidos (``arranca`` falso), sin tiempo.
    """
    tokens = comando_servidor(ent.python, cfg)
    comandos = [publico(tokens)]
    guion = hash_guion_servidor(cfg)
    inicio = ent.reloj()
    try:
        proceso = ent.lanzar(real(tokens), crudo.ruta("servidor.log"), _variables_hijo(ent, None))
    except OSError:
        return sin_valor(ERROR, "lanzamiento_fallo", comandos)
    guardia.asignar(proceso)
    while ent.reloj() - inicio < espera:
        if not proceso.vivo():
            return medido({"arranca": False, "motivo": "proceso_termino", "guion_sha256": guion}, comandos)
        r = ent.http("GET", f"{cfg.base}/health", None, ESPERA_SALUD)
        if r.estado == "ok" and r.codigo == 200:
            segundos = round(ent.reloj() - inicio, 1)
            return medido({"arranca": True, "carga_segundos": segundos, "guion_sha256": guion}, comandos)
        ent.dormir(INTERVALO_SALUD)
    return medido({"arranca": False, "motivo": "tiempo_agotado", "guion_sha256": guion}, comandos)


def sonda_limpieza(ent: Entorno, crudo: Crudo, detenido: bool) -> Parcial:
    """Tras detener el servidor: si el proceso murio y cuantos procesos siguen usando la GPU."""
    valores: dict[str, Any] = {"servidor_detenido": detenido}
    argv = ["nvidia-smi", "--query-compute-apps=pid", "--format=csv,noheader"]
    salida = ent.ejecutar(argv, ESPERA_COMANDO, None)
    crudo.comando("limpieza", argv, salida)
    if salida.estado == "ok" and salida.codigo == 0:
        lineas = [ln.strip() for ln in salida.stdout.splitlines() if ln.strip()]
        if all(ln.isdigit() for ln in lineas):
            valores["procesos_en_gpu"] = len(lineas)
    return medido(valores, [publico(argv)])


# ---------------------------------------------------------------------------
# Sondas contra el servidor (prompts inventados)
# ---------------------------------------------------------------------------


def _json_objeto(cuerpo: bytes) -> dict[str, Any] | None:
    try:
        obj = json.loads(cuerpo.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None
    return obj if isinstance(obj, dict) else None


def _fallo_http(r: Respuesta) -> Parcial | None:
    if r.estado == "tiempo_agotado":
        return sin_valor(ERROR, "tiempo_agotado")
    if r.estado != "ok" or r.codigo is None:
        return sin_valor(ERROR, "sin_conexion")
    return None


def sonda_modelo(ent: Entorno, crudo: Crudo, cfg: ConfigServidor, version: str | None) -> Parcial:
    """Identificador del modelo que sirve el servidor, y su version declarada."""
    if version is None:
        return sin_valor(NO_DISPONIBLE, "no_declarada")
    if VERSION_RE.fullmatch(version) is None:
        return sin_valor(ERROR, "valor_no_admitido")
    r = ent.http("GET", f"{cfg.base}/v1/models", None, ESPERA_COMANDO)
    crudo.guardar("modelos.txt", r.cuerpo)
    fallo = _fallo_http(r)
    if fallo is not None:
        return fallo
    if r.codigo != 200:
        return sin_valor(ERROR, "respuesta_inesperada")
    obj = _json_objeto(r.cuerpo)
    datos = obj.get("data") if obj is not None else None
    if not isinstance(datos, list) or not all(isinstance(d, dict) for d in datos):
        return sin_valor(ERROR, "salida_ilegible")
    ids = {d.get("id") for d in datos}
    if MODELO not in ids:
        return sin_valor(ERROR, "respuesta_inesperada")
    servidos = sum(1 for nombre, _ in cfg.adaptadores if nombre in ids)
    return medido({"id": MODELO, "version": version, "adaptadores_servidos": servidos})


def _peticion_chat(prompt: str, max_tokens: int) -> bytes:
    return json.dumps(
        {
            "model": MODELO,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0,
        }
    ).encode("utf-8")


def sonda_rendimiento(ent: Entorno, crudo: Crudo, cfg: ConfigServidor) -> Parcial:
    """Tokens de salida por segundo con un prompt inventado (incluye el tiempo de leer el prompt).

    Tres peticiones seguidas; el valor es la mediana. No es una tarea ni un resultado del agente.
    """
    cuerpo = _peticion_chat(PROMPT_RENDIMIENTO, TOKENS_RENDIMIENTO)
    muestras: list[dict[str, Any]] = []
    for i in range(MUESTRAS_RENDIMIENTO):
        inicio = ent.reloj()
        r = ent.http("POST", f"{cfg.base}/v1/chat/completions", cuerpo, ESPERA_RENDIMIENTO)
        segundos = ent.reloj() - inicio
        crudo.guardar(f"rendimiento_{i + 1}.txt", r.cuerpo)
        fallo = _fallo_http(r)
        if fallo is not None:
            return fallo
        if r.codigo != 200:
            return sin_valor(ERROR, "respuesta_inesperada")
        obj = _json_objeto(r.cuerpo)
        uso = obj.get("usage") if obj is not None else None
        tokens = uso.get("completion_tokens") if isinstance(uso, dict) else None
        if isinstance(tokens, bool) or not isinstance(tokens, int) or segundos <= 0:
            return sin_valor(ERROR, "salida_ilegible")
        if tokens < MIN_TOKENS_RENDIMIENTO:
            return sin_valor(ERROR, "respuesta_corta")
        muestras.append({"tokens": tokens, "segundos": round(segundos, 3)})
    tasas = [m["tokens"] / m["segundos"] for m in muestras]
    return medido(
        {
            "tokens_por_segundo": round(statistics.median(tasas), 2),
            "muestras": muestras,
            "max_tokens": TOKENS_RENDIMIENTO,
            "incluye_lectura_del_prompt": True,
        }
    )


def sonda_rechazo(ent: Entorno, crudo: Crudo, cfg: ConfigServidor, max_tokens: int) -> Parcial:
    """Observable del rechazo por contexto con ``max_tokens`` de salida y un prompt inventado.

    Primero un control: un prompt corto con el mismo ``max_tokens`` debe dar 200, para que un 400
    posterior no se pueda atribuir al valor de ``max_tokens``. Despues, un prompt que excede el
    contexto. Se versiona el codigo HTTP, que marcadores contiene el cuerpo y su hash; el texto
    exacto queda solo en el volcado crudo.
    """
    url = f"{cfg.base}/v1/chat/completions"
    control = ent.http("POST", url, _peticion_chat(PROMPT_CONTROL, max_tokens), ESPERA_CONTROL)
    crudo.guardar(f"rechazo_{max_tokens}_control.txt", control.cuerpo)
    fallo = _fallo_http(control)
    if fallo is not None:
        return fallo
    if control.codigo != 200:
        return sin_valor(ERROR, "control_fallo")
    largo = PALABRA_RELLENO * PALABRAS_RELLENO
    r = ent.http("POST", url, _peticion_chat(largo, max_tokens), ESPERA_RECHAZO)
    crudo.guardar(f"rechazo_{max_tokens}_cuerpo.txt", r.cuerpo)
    fallo = _fallo_http(r)
    if fallo is not None:
        return fallo
    assert r.codigo is not None
    texto = r.cuerpo.decode("utf-8", errors="replace").lower()
    marcadores = {m.replace(" ", "_"): m in texto for m in CONTEXT_ERROR_MARKERS}
    return medido(
        {
            "max_tokens": max_tokens,
            "http_control": control.codigo,
            "http": r.codigo,
            "marcadores": marcadores,
            "rechazado": r.codigo == 400 and any(marcadores.values()),
            "cuerpo_sha256": sha256_bytes(r.cuerpo),
            "cuerpo_bytes": len(r.cuerpo),
        }
    )


# ---------------------------------------------------------------------------
# Sonda del agente (A.0): cuatro tareas, kit original, limites de A.0
# ---------------------------------------------------------------------------


def clasificar_error(error: object) -> str:
    """Clase del ``error`` que escribe el arnes en ``task_results.jsonl``.

    ``ninguno``, ``agente``, ``rechazo_contexto``, ``verificacion`` (el agente ya corrio),
    ``infraestructura`` (el agente no llego a correr: sus turnos no valen) o ``sin_categoria``.
    """
    if error is None:
        return "ninguno"
    if not isinstance(error, str):
        return "sin_categoria"
    if error.startswith(CONTEXT_ERROR_PREFIX) and any(m in error.lower() for m in CONTEXT_ERROR_MARKERS):
        return "rechazo_contexto"
    if error.startswith(INFRA_FASE_AGENTE):
        return "infraestructura"
    if error.startswith(INFRA_FASE_VERIFICACION):
        return "verificacion"
    if error.startswith(AGENT_ERROR_PREFIXES):
        return "agente"
    return "sin_categoria"


def _solo_turnos(pares: list[tuple[str, Any]]) -> dict[str, Any]:
    """De cada resultado del arnes se conserva el identificador, los turnos y el error; ``resolved``
    y el resto se descartan al leer."""
    return {k: v for k, v in pares if k in ("instance_id", "total_llm_calls", "error")}


def leer_turnos(ruta: Path, esperadas: Sequence[str]) -> tuple[list[int], dict[str, int]] | None:
    """Turnos por tarea (ordenados, sin identificador) y conteo de clases de error.

    ``None`` si el archivo falta, no se puede leer o no trae exactamente una fila por tarea esperada.
    """
    try:
        lineas = ruta.read_text(encoding="utf-8").splitlines()
        filas = [json.loads(ln, object_pairs_hook=_solo_turnos) for ln in lineas if ln.strip()]
    except (OSError, ValueError):
        return None
    turnos: list[int] = []
    clases: dict[str, int] = {}
    vistos: set[str] = set()
    for fila in filas:
        if not isinstance(fila, dict):
            return None
        iid, llamadas = fila.get("instance_id"), fila.get("total_llm_calls")
        if not isinstance(iid, str) or iid in vistos or iid not in esperadas:
            return None
        if isinstance(llamadas, bool) or not isinstance(llamadas, int) or llamadas < 0:
            return None
        vistos.add(iid)
        turnos.append(llamadas)
        clase = clasificar_error(fila.get("error"))
        clases[clase] = clases.get(clase, 0) + 1
    if vistos != set(esperadas):
        return None
    return sorted(turnos), clases


def preparar_envio(envio: Path, crudo: Crudo, max_tokens: int) -> Path | None:
    """Envio para ``max_tokens``: el kit tal cual, o una copia con ese unico cambio en el muestreo.

    La copia solo se acepta si el archivo de muestreo declara el valor del kit exactamente una vez
    (la misma regla que aplica la compuerta). ``None`` si no se puede construir.
    """
    if max_tokens == CANDIDATOS_TOKENS[0]:
        return envio
    try:
        datos = (envio / ARCHIVO_MUESTREO).read_bytes()
    except OSError:
        return None
    aguja = f"max_output_tokens: {CANDIDATOS_TOKENS[0]}".encode("ascii")
    if datos.count(aguja) != 1:
        return None
    copia = crudo.ruta(f"envio_{max_tokens}")
    shutil.copytree(envio, copia)
    (copia / ARCHIVO_MUESTREO).write_bytes(
        datos.replace(aguja, f"max_output_tokens: {max_tokens}".encode("ascii"))
    )
    return copia


def comando_agente(
    python: str,
    *,
    tasks: Path,
    snapshots: Path,
    resultados: Path,
    envio: Path,
    backend: str,
    imagen: str,
    ids: Sequence[str],
) -> list[Token]:
    """``swegemma eval`` sobre las cuatro tareas, con los limites que fija A.0."""
    tokens: list[Token] = [
        Oculto(python, "<python>"),
        "-m",
        "swegemma.cli",
        "eval",
        "--tasks",
        Oculto(str(tasks), "<tasks>"),
        "--snapshots-dir",
        Oculto(str(snapshots), "<snapshots>"),
        "--results-dir",
        Oculto(str(resultados), "<crudo>:resultados"),
        "--submission-dir",
        Oculto(str(envio), "<envio>"),
        "--sandbox",
        backend,
    ]
    if backend == "docker":
        tokens.extend(["--image", Oculto(imagen, "<imagen>")])
    tokens.append("--task-ids")
    tokens.extend(Oculto(i, "<tarea>") for i in ids)
    tokens.extend(
        [
            "--concurrency",
            "1",
            "--max-time-minutes",
            str(MAX_TIME_MINUTES),
            "--max-tool-calls",
            str(MAX_TOOL_CALLS),
            "--max-turns",
            str(MAX_TURNS),
            "--timeout-seconds",
            str(TIMEOUT_SECONDS),
            "--display",
            "quiet",
        ]
    )
    return tokens


def sonda_agente(
    ent: Entorno,
    crudo: Crudo,
    cfg: ConfigServidor,
    *,
    max_tokens: int,
    tasks: Path,
    snapshots: Path,
    envio: Path,
    backend: str,
    imagen: str,
    ids: Sequence[str],
    espera: float,
) -> Parcial:
    """Turnos del modelo por tarea y rechazos por contexto, con ``max_tokens`` de salida.

    No lee ni guarda si las tareas se resolvieron. Si alguna tarea da un error de infraestructura en
    la fase del agente, sus turnos no significan nada y la sonda queda en ``error``.
    """
    preparado = preparar_envio(envio, crudo, max_tokens)
    if preparado is None:
        return sin_valor(ERROR, "entrada_inesperada")
    resultados = crudo.ruta(f"agente_{max_tokens}")
    tokens = comando_agente(
        ent.python,
        tasks=tasks,
        snapshots=snapshots,
        resultados=resultados,
        envio=preparado,
        backend=backend,
        imagen=imagen,
        ids=ids,
    )
    comandos = [publico(tokens)]
    salida = ent.ejecutar(real(tokens), espera, _variables_hijo(ent, cfg))
    crudo.comando(f"agente_{max_tokens}", real(tokens), salida)
    fallo = _fallo_de_comando(salida, comandos)
    if fallo is not None:
        return fallo
    leido = leer_turnos(resultados / "task_results.jsonl", ids)
    if leido is None:
        return sin_valor(ERROR, "salida_ilegible", comandos)
    turnos, clases = leido
    if clases.get("sin_categoria", 0):
        return sin_valor(ERROR, "error_sin_categoria", comandos)
    if clases.get("infraestructura", 0):
        return sin_valor(ERROR, "infraestructura_arnes", comandos)
    return medido(
        {
            "max_output_tokens": max_tokens,
            "backend": backend,
            "tareas": len(turnos),
            "turnos_por_tarea": turnos,
            "peticiones_al_modelo": sum(turnos),
            "rechazos_por_contexto": clases.get("rechazo_contexto", 0),
            "errores_de_verificacion": clases.get("verificacion", 0),
            "max_time_minutes": MAX_TIME_MINUTES,
        },
        comandos,
    )


# ---------------------------------------------------------------------------
# Registro de la compuerta e informe de sondas
# ---------------------------------------------------------------------------


def _es_entero(v: object, minimo: int) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v >= minimo


def _es_numero(v: object, minimo: float, *, estricto: bool = False) -> bool:
    if isinstance(v, bool) or not isinstance(v, int | float) or not math.isfinite(v):
        return False
    return v > minimo if estricto else v >= minimo


# El mismo esquema que ``ENSAYO`` en scripts/kaggle_prereg.py; las pruebas comprueban que coinciden.
ESQUEMA: dict[str, Callable[[Any], bool]] = {
    "schema_version": lambda v: v == ESQUEMA_REGISTRO,
    "fecha": lambda v: isinstance(v, str) and FECHA_RE.fullmatch(v) is not None,
    "notebook": lambda v: isinstance(v, str) and bool(v.strip()),
    "modelo": lambda v: isinstance(v, str) and bool(v.strip()),
    "guion_servidor_sha256": lambda v: isinstance(v, str) and SHA_RE.fullmatch(v) is not None,
    "docker_disponible": lambda v: isinstance(v, bool),
    "backend": lambda v: v in BACKENDS,
    "servidor_arranca": lambda v: isinstance(v, bool),
    "envio_compila": lambda v: isinstance(v, bool),
    "carga_modelo_segundos": lambda v: _es_numero(v, 0),
    "sesion_max_horas": lambda v: _es_numero(v, 0, estricto=True),
    "tokens_por_segundo": lambda v: _es_numero(v, 0),
    "max_time_minutes_ensayo": lambda v: _es_entero(v, 1),
    "turnos_por_tarea": lambda v: isinstance(v, list) and bool(v) and all(_es_entero(x, 0) for x in v),
    "peticiones_al_modelo": lambda v: _es_entero(v, 0),
    "rechazos_por_contexto": lambda v: (
        isinstance(v, dict)
        and bool(v)
        and all(isinstance(k, str) and k.isdigit() and _es_entero(n, 0) for k, n in v.items())
    ),
}


def validar_registro(obj: object) -> list[str]:
    """Problemas del registro frente al esquema de la compuerta (lista vacia = valido)."""
    if not isinstance(obj, dict):
        return ["el registro no es un objeto"]
    if set(obj) != set(ESQUEMA):
        return [f"claves distintas de las del esquema: {sorted(set(obj) ^ set(ESQUEMA))}"]
    return [f"valor invalido en {k}" for k, ok in ESQUEMA.items() if not ok(obj[k])]


def nombre_agente(max_tokens: int) -> str:
    return f"agente:{max_tokens}"


def construir_registro(
    resultados: Sequence[Resultado], *, fecha: str, notebook: str | None
) -> tuple[dict[str, Any] | None, list[str]]:
    """Registro de la compuerta a partir de las sondas, o ``None`` y la lista de lo que falta.

    Cada campo sale de una sonda ``medido``. Si una sola falta, no hay registro: ningun campo se
    rellena con un valor por defecto.
    """
    por_nombre = {r.sonda: r for r in resultados}
    faltan: list[str] = []

    def valor(sonda: str, clave: str, campo: str) -> Any:
        r = por_nombre.get(sonda)
        if r is None or r.estado != MEDIDO or clave not in r.valores:
            estado = "ausente" if r is None else r.estado if r.estado != MEDIDO else "sin ese valor"
            faltan.append(f"{campo} (sonda {sonda}: {estado})")
            return None
        return r.valores[clave]

    primero = CANDIDATOS_TOKENS[0]
    agente = nombre_agente(primero)
    registro: dict[str, Any] = {"schema_version": ESQUEMA_REGISTRO, "fecha": fecha}
    if notebook is None or not texto_seguro(notebook):
        faltan.append("notebook (no declarado o con caracteres no admitidos)")
    registro["notebook"] = notebook
    identificador, version = valor("modelo", "id", "modelo"), valor("modelo", "version", "modelo")
    registro["modelo"] = f"{identificador}@{version}"
    registro["guion_servidor_sha256"] = valor("servidor", "guion_sha256", "guion_servidor_sha256")
    registro["docker_disponible"] = valor("docker", "disponible", "docker_disponible")
    registro["backend"] = valor(agente, "backend", "backend")
    registro["servidor_arranca"] = valor("servidor", "arranca", "servidor_arranca")
    registro["envio_compila"] = valor("compila", "compila", "envio_compila")
    registro["carga_modelo_segundos"] = valor("servidor", "carga_segundos", "carga_modelo_segundos")
    registro["sesion_max_horas"] = valor("sesion", "horas", "sesion_max_horas")
    registro["tokens_por_segundo"] = valor("rendimiento", "tokens_por_segundo", "tokens_por_segundo")
    registro["max_time_minutes_ensayo"] = valor(agente, "max_time_minutes", "max_time_minutes_ensayo")
    turnos = valor(agente, "turnos_por_tarea", "turnos_por_tarea")
    registro["turnos_por_tarea"] = list(turnos) if isinstance(turnos, list | tuple) else turnos
    registro["peticiones_al_modelo"] = valor(agente, "peticiones_al_modelo", "peticiones_al_modelo")
    rechazos: dict[str, Any] = {}
    con_el_kit = valor(agente, "rechazos_por_contexto", f"rechazos_por_contexto[{primero}]")
    rechazos[str(primero)] = con_el_kit
    if isinstance(con_el_kit, int) and con_el_kit > 0:
        # A.0: si hay algun rechazo con el valor del kit, el ensayo se repite con el siguiente candidato
        for candidato in CANDIDATOS_TOKENS[1:]:
            rechazos[str(candidato)] = valor(
                nombre_agente(candidato), "rechazos_por_contexto", f"rechazos_por_contexto[{candidato}]"
            )
    registro["rechazos_por_contexto"] = rechazos
    if faltan:
        return None, faltan
    problemas = validar_registro(registro)
    if problemas:
        raise RuntimeError("El registro propio no pasa su esquema: " + "; ".join(problemas))
    return registro, []


def construir_informe(
    resultados: Sequence[Resultado],
    *,
    fecha: str,
    registro_sha256: str | None,
    faltan: Sequence[str],
    servidor_detenido: bool,
) -> dict[str, Any]:
    """Informe versionable de las sondas. Lo comprueba ``comprobar_versionable`` antes de escribirse."""
    informe: dict[str, Any] = {
        "schema_version": ESQUEMA_INFORME,
        "fecha": fecha,
        "registro": {"escrito": registro_sha256 is not None, "faltan": len(faltan)},
        "servidor_detenido": servidor_detenido,
        "sondas": [r.versionable() for r in resultados],
    }
    if registro_sha256 is not None:
        informe["registro"]["sha256"] = registro_sha256
    comprobar_versionable(informe)
    return informe


# ---------------------------------------------------------------------------
# Plan: que haria cada sonda, sin ejecutar nada
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PasoDelPlan:
    """Una sonda en el plan: que mide, que campos del registro alimenta y cuanto puede tardar."""

    sonda: str
    mide: str
    usa_gpu: bool
    campos: tuple[str, ...]
    espera_segundos: float
    comandos: tuple[tuple[str, ...], ...] = ()


def espera_agente(minutos_por_tarea: float) -> float:
    return 4 * minutos_por_tarea * 60.0


def plan(args: argparse.Namespace, python: str = "python") -> list[PasoDelPlan]:
    """Lista ordenada de las sondas de una corrida con estos argumentos. No toca el sistema."""
    cfg = ConfigServidor(
        args.modelo, descubrir_adaptadores(args.envio), args.puerto, tuple(args.servidor_arg)
    )
    pasos: list[PasoDelPlan] = [
        PasoDelPlan("python", "version del interprete", False, (), 0),
        PasoDelPlan("cpu", "numero de CPU visibles", False, (), 0),
        PasoDelPlan("memoria", "memoria total (/proc/meminfo)", False, (), 0),
        PasoDelPlan("disco", "espacio libre donde se escribe el volcado", False, (), 0),
        PasoDelPlan(
            "gpu",
            "GPU visibles, modelo y memoria",
            False,
            (),
            ESPERA_COMANDO,
            (("nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"),),
        ),
    ]
    pasos.extend(
        PasoDelPlan(f"version:{p}", f"version instalada de {p} (metadatos, sin importar)", False, (), 0)
        for p in PAQUETES
    )
    pasos.extend(
        [
            PasoDelPlan(
                "docker",
                "si el demonio responde, si esta la imagen y si arranca un contenedor sin red",
                False,
                ("docker_disponible",),
                4 * ESPERA_COMANDO,
                (
                    ("docker", "--version"),
                    ("docker", "info", "--format", "{{.ServerVersion}}"),
                    ("docker", "image", "inspect", "--format", "{{.Id}}", "<imagen>"),
                    ("docker", "run", "--rm", "--network", "none", "<imagen>", "true"),
                ),
            ),
            PasoDelPlan(
                "sesion", "duracion maxima de sesion declarada con su fuente", False, ("sesion_max_horas",), 0
            ),
            PasoDelPlan("envio", "el envio coincide con el manifiesto del kit", False, (), 0),
            PasoDelPlan(
                "compila",
                "el envio compila con el compilador del arnes",
                False,
                ("envio_compila",),
                ESPERA_COMPILAR,
                (("<python>", "-c", "<programa de compilacion>", "<envio>"),),
            ),
            PasoDelPlan(
                "tareas", "elige las cuatro tareas de A.0 (solo identificador y repositorio)", False, (), 0
            ),
        ]
    )
    if args.solo_anfitrion:
        return pasos
    pasos.extend(
        [
            PasoDelPlan(
                "servidor",
                "arranque del servidor con los parametros de HARNESS 3.1 y segundos hasta /health",
                True,
                ("servidor_arranca", "carga_modelo_segundos", "guion_servidor_sha256"),
                args.espera_servidor,
                (publico(comando_servidor(python, cfg)),),
            ),
            PasoDelPlan("modelo", "identificador que sirve el servidor", True, ("modelo",), ESPERA_COMANDO),
            PasoDelPlan(
                "rendimiento",
                f"tokens por segundo, {MUESTRAS_RENDIMIENTO} peticiones con un prompt inventado",
                True,
                ("tokens_por_segundo",),
                MUESTRAS_RENDIMIENTO * ESPERA_RENDIMIENTO,
            ),
        ]
    )
    pasos.extend(
        PasoDelPlan(
            f"rechazo_sintetico:{t}",
            f"codigo y marcadores del rechazo por contexto con max_tokens {t} (prompt inventado)",
            True,
            (),
            ESPERA_CONTROL + ESPERA_RECHAZO,
        )
        for t in CANDIDATOS_TOKENS
    )
    if not args.sin_agente:
        comando = publico(
            comando_agente(
                python,
                tasks=args.tasks,
                snapshots=args.snapshots_dir,
                resultados=Path("crudo") / "agente",
                envio=args.envio,
                backend="<backend>",
                imagen=args.imagen,
                ids=("a", "b", "c", "d"),
            )
        )
        for i, t in enumerate(CANDIDATOS_TOKENS):
            condicion = "" if i == 0 else f" (solo si hubo rechazos con {CANDIDATOS_TOKENS[0]})"
            pasos.append(
                PasoDelPlan(
                    nombre_agente(t),
                    f"turnos del modelo y rechazos en las cuatro tareas de A.0, salida de {t}{condicion}",
                    True,
                    ("backend", "turnos_por_tarea", "peticiones_al_modelo", "rechazos_por_contexto")
                    if i == 0
                    else ("rechazos_por_contexto",),
                    espera_agente(args.espera_agente_min),
                    (comando,),
                )
            )
    pasos.append(
        PasoDelPlan(
            "limpieza",
            "el servidor quedo detenido y cuantos procesos siguen en la GPU",
            True,
            (),
            GRACIA_TERMINAR + GRACIA_MATAR + ESPERA_COMANDO,
            (("nvidia-smi", "--query-compute-apps=pid", "--format=csv,noheader"),),
        )
    )
    return pasos


def texto_del_plan(pasos: Sequence[PasoDelPlan]) -> str:
    """Texto que imprime ``--plan``."""
    lineas = ["PLAN del ensayo de notebook: no se ha ejecutado nada.", ""]
    for i, p in enumerate(pasos, start=1):
        gpu = "con GPU" if p.usa_gpu else "sin GPU"
        lineas.append(f"{i:2d}. {p.sonda} [{gpu}; espera maxima {p.espera_segundos:.0f} s]")
        lineas.append(f"    mide: {p.mide}")
        if p.campos:
            lineas.append(f"    campos del registro: {', '.join(p.campos)}")
        lineas.extend(f"    comando: {' '.join(c)}" for c in p.comandos)
    con_gpu = sum(p.espera_segundos for p in pasos if p.usa_gpu)
    total = sum(p.espera_segundos for p in pasos)
    lineas.extend(
        [
            "",
            f"Caso peor (todas las esperas agotadas): {total / 60:.0f} min de sesion, "
            f"{con_gpu / 60:.0f} de ellos con el servidor en la GPU.",
            "La cuota de GPU corre mientras la sesion este abierta, no solo durante las sondas.",
        ]
    )
    return "\n".join(lineas)


# ---------------------------------------------------------------------------
# Corrida
# ---------------------------------------------------------------------------


def _elegir_backend(pedido: str, docker: Resultado) -> str | None:
    if pedido in BACKENDS:
        return pedido
    if docker.estado == MEDIDO:
        return str(docker.valores["backend"])
    return None


def _version_del_modelo(args: argparse.Namespace) -> str | None:
    """La version declarada o, si no, el ultimo componente numerico de la ruta del modelo."""
    if args.modelo_version is not None:
        return str(args.modelo_version)
    ultimo = args.modelo.name
    return ultimo if ultimo.isdigit() else None


def medir(args: argparse.Namespace, ent: Entorno, crudo: Crudo, guardia: Guardia) -> list[Resultado]:
    """Ejecuta las sondas en orden. El llamador detiene el servidor con ``guardia`` al terminar."""
    out: list[Resultado] = []

    def hacer(nombre: str, sonda: Callable[[], Parcial]) -> Resultado:
        r = correr(nombre, sonda, ent)
        out.append(r)
        print(f"  {nombre}: {r.estado}" + (f" ({r.categoria})" if r.categoria else "") + f" [{r.segundos} s]")
        return r

    def saltar(nombre: str, categoria: str = "dependencia_no_medida") -> None:
        out.append(omitida(nombre, categoria))
        print(f"  {nombre}: {NO_DISPONIBLE} ({categoria})")

    hacer("python", lambda: sonda_python(ent))
    hacer("cpu", lambda: sonda_cpu(ent))
    hacer("memoria", lambda: sonda_memoria(ent))
    hacer("disco", lambda: sonda_disco(ent, crudo.raiz.parent))
    hacer("gpu", lambda: sonda_gpu(ent, crudo))
    versiones = {p: hacer(f"version:{p}", partial(sonda_version, ent, p)) for p in PAQUETES}
    docker = hacer("docker", lambda: sonda_docker(ent, crudo, args.imagen))
    hacer("sesion", lambda: sonda_sesion(args.sesion_max_horas, args.sesion_fuente))
    kit = hacer("envio", lambda: sonda_envio(args.envio, args.manifiesto))
    compila = hacer("compila", lambda: sonda_compila(ent, crudo, args.envio))
    tareas = hacer("tareas", lambda: sonda_tareas(args.tasks))
    if args.solo_anfitrion:
        return out

    nombres_rechazo = [f"rechazo_sintetico:{t}" for t in CANDIDATOS_TOKENS]
    nombres_agente = [nombre_agente(t) for t in CANDIDATOS_TOKENS]
    con_servidor = ["modelo", "rendimiento", *nombres_rechazo, *nombres_agente]
    if versiones["vllm"].estado != MEDIDO or not args.modelo.is_dir():
        saltar(
            "servidor", "entrada_ausente" if versiones["vllm"].estado == MEDIDO else "dependencia_no_medida"
        )
        for nombre in con_servidor:
            saltar(nombre)
        return out

    cfg = ConfigServidor(
        args.modelo, descubrir_adaptadores(args.envio), args.puerto, tuple(args.servidor_arg)
    )
    servidor = hacer("servidor", lambda: sonda_servidor(ent, crudo, cfg, guardia, args.espera_servidor))
    if servidor.estado != MEDIDO or servidor.valores["arranca"] is not True:
        for nombre in con_servidor:
            saltar(nombre)
        return out

    hacer("modelo", lambda: sonda_modelo(ent, crudo, cfg, _version_del_modelo(args)))
    hacer("rendimiento", lambda: sonda_rendimiento(ent, crudo, cfg))
    for t, nombre in zip(CANDIDATOS_TOKENS, nombres_rechazo, strict=True):
        hacer(nombre, partial(sonda_rechazo, ent, crudo, cfg, t))

    backend = _elegir_backend(args.sandbox, docker)
    listo = (
        kit.estado == MEDIDO
        and kit.valores["coincide"] is True
        and compila.estado == MEDIDO
        and compila.valores["compila"] is True
        and tareas.estado == MEDIDO
        and backend is not None
    )
    if args.sin_agente or not listo:
        for nombre in nombres_agente:
            saltar(nombre, "no_solicitada" if args.sin_agente else "dependencia_no_medida")
        return out
    assert backend is not None
    ids = list(tareas.parcial.privado["ids"])
    for i, (t, nombre) in enumerate(zip(CANDIDATOS_TOKENS, nombres_agente, strict=True)):
        if i > 0:
            anterior = out[-1]
            if anterior.estado != MEDIDO:
                saltar(nombre)
                continue
            if anterior.valores["rechazos_por_contexto"] == 0:
                saltar(nombre, "no_necesaria")
                continue
        hacer(
            nombre,
            partial(
                sonda_agente,
                ent,
                crudo,
                cfg,
                max_tokens=t,
                tasks=args.tasks,
                snapshots=args.snapshots_dir,
                envio=args.envio,
                backend=backend,
                imagen=args.imagen,
                ids=ids,
                espera=espera_agente(args.espera_agente_min),
            ),
        )
    return out


def ejecutar(args: argparse.Namespace, ent: Entorno, guardia: Guardia) -> int:
    """Cuerpo de la CLI; lanza ``EnsayoError`` ante cualquier causa de salida 2."""
    if args.puerto < 1 or args.puerto > 65535:
        raise EnsayoError("--puerto fuera de rango.")
    if args.espera_servidor <= 0 or args.espera_agente_min <= 0:
        raise EnsayoError("Las esperas deben ser mayores que cero.")
    if args.plan:
        print(texto_del_plan(plan(args, "python")))
        return EXIT_OK
    for nombre in ("salida", "informe", "crudo"):
        if getattr(args, nombre) is None:
            raise EnsayoError(f"Falta --{nombre} (solo --plan puede omitirlo).")
    salida, informe_ruta, crudo_ruta = args.salida.resolve(), args.informe.resolve(), args.crudo.resolve()
    if salida == informe_ruta:
        raise EnsayoError("--salida y --informe deben ser archivos distintos.")
    for nombre, ruta in (("--salida", salida), ("--informe", informe_ruta)):
        if ruta.exists():
            raise EnsayoError(f"Ya existe {nombre} ({ruta.name}): este guion no sobrescribe resultados.")
        if ruta == crudo_ruta or crudo_ruta in ruta.parents:
            raise EnsayoError(f"{nombre} no puede quedar dentro de --crudo.")
    comprobar_crudo(args.crudo, ent)
    descubrir_adaptadores(args.envio)  # un nombre de adaptador no admitido es una entrada invalida

    crudo = Crudo(args.crudo)
    crudo.crear()
    print("Ensayo de notebook: sondas")
    try:
        resultados = medir(args, ent, crudo, guardia)
    finally:
        detenido = guardia.detener()
    if guardia.lanzados:
        resultados.append(correr("limpieza", lambda: sonda_limpieza(ent, crudo, detenido), ent))

    fecha = ent.ahora().astimezone(timezone.utc).date().isoformat()  # noqa: UP017
    registro, faltan = construir_registro(resultados, fecha=fecha, notebook=args.notebook)
    crudo.guardar(
        "sondas.json",
        a_json(
            {
                "resultados": [{**r.versionable(), "privado": _copia(r.parcial.privado)} for r in resultados],
                "faltan": faltan,
            }
        ),
    )
    registro_sha: str | None = None
    datos_registro = a_json(registro) if registro is not None else None
    if datos_registro is not None:
        registro_sha = sha256_bytes(datos_registro)
    informe = construir_informe(
        resultados, fecha=fecha, registro_sha256=registro_sha, faltan=faltan, servidor_detenido=detenido
    )
    if datos_registro is not None:
        escribir_sin_sobrescribir(args.salida, datos_registro)
        print(f"Registro escrito: {args.salida.name} (SHA-256 {registro_sha})")
    else:
        print("Registro NO escrito: faltan medidas y no se inventan.", file=sys.stderr)
        for f in faltan:
            print(f"  falta: {f}", file=sys.stderr)
    escribir_sin_sobrescribir(args.informe, a_json(informe))
    print(f"Informe de sondas escrito: {args.informe.name}")
    if not detenido:
        pid = guardia.proceso.pid if guardia.proceso is not None else "?"
        print(
            f"ATENCION: el servidor (pid {pid}) sigue vivo: detenga la sesion del notebook.", file=sys.stderr
        )
        return EXIT_INCOMPLETO
    return EXIT_OK if registro is not None else EXIT_INCOMPLETO


# ---------------------------------------------------------------------------
# Implementacion real de ``Entorno`` (no se usa en las pruebas de las sondas)
# ---------------------------------------------------------------------------


def _matar_grupo(proc: subprocess.Popen[Any], senal: int) -> None:
    """Envia la senal al grupo del proceso si la plataforma lo permite; si no, al proceso."""
    killpg = getattr(os, "killpg", None)
    if killpg is not None:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            killpg(proc.pid, senal)
        return
    if senal == signal.SIGTERM:
        proc.terminate()
    else:
        proc.kill()


def _senal_matar() -> int:
    return int(getattr(signal, "SIGKILL", signal.SIGTERM))


class ProcesoReal:
    """``Proceso`` sobre ``subprocess.Popen``, en su propio grupo para poder matar a sus hijos."""

    def __init__(self, proc: subprocess.Popen[Any], registro: Any) -> None:
        self._proc = proc
        self._registro = registro
        self.pid = proc.pid

    def vivo(self) -> bool:
        return self._proc.poll() is None

    def terminar(self) -> None:
        _matar_grupo(self._proc, signal.SIGTERM)

    def matar(self) -> None:
        _matar_grupo(self._proc, _senal_matar())

    def esperar(self, segundos: float) -> bool:
        try:
            self._proc.wait(timeout=segundos)
        except subprocess.TimeoutExpired:
            return False
        with contextlib.suppress(Exception):
            self._registro.close()
        return True


def lanzar_real(argv: Sequence[str], registro: Path, variables: Mapping[str, str]) -> Proceso:
    """Lanza un proceso en segundo plano con su salida en ``registro``."""
    f = open(registro, "xb")  # noqa: SIM115
    try:
        proc = subprocess.Popen(
            list(argv),
            stdout=f,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            env=dict(variables),
            start_new_session=os.name == "posix",
        )
    except BaseException:
        f.close()
        raise
    return ProcesoReal(proc, f)


def ejecutar_real(argv: Sequence[str], espera: float, variables: Mapping[str, str] | None) -> Salida:
    """Ejecuta un comando y espera su salida; al agotar la espera mata a todo su grupo."""
    try:
        proc = subprocess.Popen(
            list(argv),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            errors="replace",
            env=dict(variables) if variables is not None else None,
            start_new_session=os.name == "posix",
        )
    except FileNotFoundError:
        return Salida("ausente", None, "", "")
    except PermissionError:
        return Salida("sin_permiso", None, "", "")
    try:
        stdout, stderr = proc.communicate(timeout=espera)
    except subprocess.TimeoutExpired:
        _matar_grupo(proc, _senal_matar())
        stdout, stderr = proc.communicate()
        return Salida("tiempo_agotado", None, stdout or "", stderr or "")
    return Salida("ok", proc.returncode, stdout or "", stderr or "")


def http_real(metodo: str, url: str, cuerpo: bytes | None, espera: float) -> Respuesta:
    """Peticion HTTP sin proxy y solo a ``127.0.0.1``: el guion no habla con nadie mas."""
    if not url.startswith(f"http://{HOST}:"):
        raise ValueError("el ensayo solo hace peticiones al servidor local")
    peticion = urllib.request.Request(url, data=cuerpo, method=metodo)
    if cuerpo is not None:
        peticion.add_header("Content-Type", "application/json")
    abridor = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with abridor.open(peticion, timeout=espera) as r:
            return Respuesta("ok", int(r.status), r.read())
    except urllib.error.HTTPError as exc:
        return Respuesta("ok", int(exc.code), exc.read())
    except TimeoutError:
        return Respuesta("tiempo_agotado", None, b"")
    except urllib.error.URLError as exc:
        estado = "tiempo_agotado" if isinstance(exc.reason, TimeoutError) else "sin_conexion"
        return Respuesta(estado, None, b"")
    except OSError:
        return Respuesta("sin_conexion", None, b"")


def _version_real(paquete: str) -> str | None:
    try:
        return metadata.version(paquete)
    except metadata.PackageNotFoundError:
        return None


def _leer_texto_real(ruta: str) -> str | None:
    try:
        return Path(ruta).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _disco_real(ruta: str) -> int | None:
    try:
        return int(shutil.disk_usage(ruta).free)
    except OSError:
        return None


def entorno_real() -> Entorno:
    """``Entorno`` sobre el sistema real."""
    return Entorno(
        ejecutar=ejecutar_real,
        lanzar=lanzar_real,
        http=http_real,
        reloj=time.monotonic,
        dormir=time.sleep,
        ahora=lambda: datetime.now(timezone.utc),  # noqa: UP017
        version_paquete=_version_real,
        leer_texto=_leer_texto_real,
        disco_libre=_disco_real,
        cpus=os.cpu_count,
        variables=dict(os.environ),
        python=sys.executable,
        version_python=platform.python_version(),
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="kaggle_ensayo",
        description="Ensayo de notebook de la linea base A (pre-registro, seccion A.0).",
    )
    p.add_argument("--modelo", type=Path, required=True, help="Directorio del modelo (dataset oficial).")
    p.add_argument("--modelo-version", help="Version del modelo; por defecto, el ultimo componente numerico.")
    p.add_argument(
        "--envio", type=Path, required=True, help="Directorio del kit original (sample_submission)."
    )
    p.add_argument(
        "--manifiesto", type=Path, required=True, help="manifest.json del kit (de este repositorio)."
    )
    p.add_argument("--tasks", type=Path, required=True, help="tasks.jsonl de la competencia.")
    p.add_argument("--snapshots-dir", type=Path, required=True, help="Directorio de snapshots.")
    p.add_argument("--notebook", help="Notebook y version, p. ej. 'usuario/ensayo-a0 v1'.")
    p.add_argument("--sesion-max-horas", type=float, help="Duracion maxima de sesion, leida en Kaggle.")
    p.add_argument("--sesion-fuente", help="De donde sale esa duracion (texto corto).")
    p.add_argument("--sandbox", choices=("auto", *BACKENDS), default="auto")
    p.add_argument("--imagen", default="swebench-sandbox:latest", help="Imagen del sandbox si hay Docker.")
    p.add_argument("--puerto", type=int, default=8000)
    p.add_argument(
        "--servidor-arg",
        action="append",
        default=[],
        metavar="ARG",
        help="Opcion extra para vLLM (repetible; con '=' si empieza por guion). Cambia el hash del guion.",
    )
    p.add_argument("--espera-servidor", type=float, default=ESPERA_SERVIDOR, help="Segundos hasta /health.")
    p.add_argument(
        "--espera-agente-min",
        type=float,
        default=ESPERA_AGENTE_MIN_POR_TAREA,
        help="Minutos de espera por tarea en la sonda del agente.",
    )
    p.add_argument("--solo-anfitrion", action="store_true", help="Solo las sondas que no usan GPU.")
    p.add_argument("--sin-agente", action="store_true", help="No correr el agente (no habra registro).")
    p.add_argument("--plan", action="store_true", help="Imprime que haria cada sonda y no ejecuta nada.")
    p.add_argument("--crudo", type=Path, help="Directorio nuevo del volcado crudo (no se versiona).")
    p.add_argument("--salida", type=Path, help="Registro kaggle-notebook-trial/1; no se sobrescribe.")
    p.add_argument("--informe", type=Path, help="Informe versionable de sondas; no se sobrescribe.")
    return p


@contextlib.contextmanager
def _senales(activas: bool) -> Iterator[None]:
    """Convierte SIGTERM en una salida ordenada, para que el servidor se detenga."""
    if not activas:
        yield
        return

    def manejar(numero: int, _marco: object) -> None:
        raise SystemExit(128 + numero)

    anterior: Any = None
    with contextlib.suppress(ValueError, OSError):
        anterior = signal.signal(signal.SIGTERM, manejar)
    try:
        yield
    finally:
        if anterior is not None:
            with contextlib.suppress(ValueError, OSError):
                signal.signal(signal.SIGTERM, anterior)


def main(argv: Sequence[str] | None = None, *, entorno: Entorno | None = None) -> int:
    """Punto de entrada. ``entorno`` se inyecta en las pruebas."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            with contextlib.suppress(Exception):
                reconfigure(encoding="utf-8")
    args = _parser().parse_args(argv)
    guardia = Guardia()
    es_real = entorno is None
    if es_real:
        atexit.register(guardia.detener)
    try:
        with _senales(es_real):
            return ejecutar(args, entorno or entorno_real(), guardia)
    except (EnsayoError, OSError) as exc:
        mensaje = str(exc) if isinstance(exc, EnsayoError) else f"error de archivo ({type(exc).__name__})"
        print(f"ERROR: {mensaje}", file=sys.stderr)
        return EXIT_INVALIDO
    except Exception as exc:
        # solo el tipo y el punto del guion: el texto de la excepcion puede traer datos
        marco = traceback.extract_tb(exc.__traceback__)[-1] if exc.__traceback__ else None
        punto = f"{Path(marco.filename).name}:{marco.lineno} ({marco.name})" if marco else "?"
        print(f"ERROR INESPERADO ({type(exc).__name__}) en {punto}", file=sys.stderr)
        return EXIT_INESPERADO
    finally:
        guardia.detener()


if __name__ == "__main__":
    sys.exit(main())
