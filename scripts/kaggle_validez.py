"""Validez de las tareas de la linea base A (issue #103, experimento Kaggle Gemma 4; commit C1).

Implementa la seccion A.2 a A.4 del pre-registro (``docs/preregistration/kaggle-baseline-a.md``):
para cada tarea, dos verificaciones (sin parche y con el parche de referencia), cada una dos
veces, con UNA misma funcion de verificacion; una ejecucion de infraestructura se repite una vez;
la tarea recibe una clase y toda clase distinta de ``discrimina`` la excluye. Solo biblioteca
estandar mas los modulos hermanos de ``scripts/``.

En esta entrega no se ha medido nada: el guion se prueba con verificadores sinteticos. La funcion
real del arnes (``swegemma``) se importa de forma perezosa; sin el paquete el guion sale con 2.

Clases, en este orden (la primera que se cumple):

1. ``no_medible``       alguna de las cuatro ejecuciones es de infraestructura tambien tras repetirla;
2. ``inestable``        las dos ejecuciones de una misma verificacion difieren en ``resolved``;
3. ``pasa_sin_parche``  sin parche, resuelta en las dos;
4. ``dorado_falla``     con parche de referencia, no resuelta en las dos;
5. ``discrimina``       sin parche no resuelta en las dos, con parche resuelta en las dos.

Una ejecucion es de infraestructura si ``scripts/kaggle_replicas.py`` la clasifica como
``infra_error`` o si las pruebas no se pudieron ejecutar (codigo -1). Los codigos 124 y 137 no lo
son: cuentan como no resuelta.

Frontera de fuga (A, Â«Frontera de fugaÂ»). El registro versionable lleva solo ``instance_id``,
repositorio, clase, codigos de salida, conteos, duraciones y fechas UTC; del error del arnes guarda
una categoria de una lista cerrada, nunca su texto. Nunca lleva nombres de pruebas, logs,
enunciados, parches ni el hash del parche de referencia. Las salidas crudas van a ``--crudo``, que
debe estar fuera de un repositorio git o ser una ruta ignorada por git.

Reanudable: cada ejecucion se guarda en ``--crudo`` al terminar, sin sobrescribir; al reanudar se
leen, se recalcula su registro y una discrepancia es salida 2. Un diario de solo-anadir
(``diario.jsonl``, encadenado por hashes) anota cada ejecucion lanzada: borrar o editar una ejecucion
sin dejar rastro en el diario es salida 2 (hace visible la manipulacion, no la impide). Un
``--crudo`` tiene un solo modo (medicion, muestra o ensayo ``--task-ids``) y un solo entorno.

Codigos de salida (no se solapan):

* 0  medicion completa y sin hallazgo (en modo muestra: todas las clases coinciden; en una
  medicion parcial con ``--task-ids``: terminada, sin registro).
* 1  medicion completa con hallazgo: la guarda de A.3 salta en algun repositorio (el registro se
  escribe igual, para conservarlo) o, en modo muestra, alguna clase difiere.
* 2  no se pudo medir o validar: entrada invalida, entorno que no coincide, ``swegemma`` ausente,
  fallo del verificador, error del arnes sin categoria, archivo que se sobrescribiria, ruta cruda
  versionada, discrepancia con lo guardado. Â«No pude medirÂ» nunca equivale a una clase.
* 3  error inesperado del propio script.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import hashlib
import importlib
import importlib.metadata
import json
import logging
import math
import os
import re
import subprocess
import sys
import tempfile
import time
import traceback
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts import kaggle_prereg, kaggle_replicas, kaggle_split

EXIT_OK, EXIT_FINDING, EXIT_INVALID, EXIT_UNEXPECTED = 0, 1, 2, 3

SCHEMA_VALIDEZ = kaggle_prereg.ESQUEMA_VALIDEZ
SCHEMA_MUESTRA = "kaggle-task-validity-sample/1"
SCHEMA_MANIFIESTO = "kaggle-task-validity-run/1"

CLASE_NO_MEDIBLE = "no_medible"
CLASE_INESTABLE = "inestable"
CLASE_PASA = "pasa_sin_parche"
CLASE_DORADO_FALLA = "dorado_falla"
CLASE_DISCRIMINA = "discrimina"

VERIF_SIN = "sin_parche"
VERIF_DORADO = "dorado"
# Orden de ejecucion de una tarea: intercalado, para que una deriva del entorno entre la primera y
# la segunda ronda se vea como inestabilidad y no como un resultado distinto por verificacion.
RONDAS: tuple[tuple[str, int], ...] = ((VERIF_SIN, 1), (VERIF_DORADO, 1), (VERIF_SIN, 2), (VERIF_DORADO, 2))
MAX_INTENTOS = 2  # la ejecucion y una repeticion si la primera es de infraestructura

# Guarda de A.3: repositorio con al menos 10 tareas y mas de la mitad sin ser ``discrimina``.
GUARDA_MIN_TAREAS = 10
MUESTRA_PRIMERAS = 10  # A.4: las 10 primeras tareas por orden de sha256(instance_id)

# Categorias que puede llevar el registro versionable en lugar del texto del error del arnes.
CATEGORIAS: tuple[str, ...] = (*kaggle_replicas.FAILURE_REASONS, *kaggle_replicas.INFRA_REASONS)
ESTADOS = (kaggle_replicas.ST_RESOLVED, kaggle_replicas.ST_UNRESOLVED, kaggle_replicas.ST_INFRA)

# Registro de una ejecucion en ``--crudo`` (lo que se recalcula al reanudar): incluye conteos y fecha.
CLAVES_EJECUCION = (
    "verificacion",
    "numero",
    "intento",
    "estado",
    "resolved",
    "codigo_salida",
    "categoria",
    "passed",
    "failed",
    "errors",
    "duracion_segundos",
    "fecha_utc",
)
# Lo que pasa al registro versionable: solo lo que A.2 y A.4 enumeran (sin conteos ni fecha por ejecucion).
CLAVES_EJECUCION_VERSIONADAS = (
    "verificacion",
    "numero",
    "intento",
    "estado",
    "resolved",
    "codigo_salida",
    "categoria",
    "duracion_segundos",
)
CLAVES_TAREA = (
    "instance_id",
    "repo",
    "clase",
    "sin_parche_segundos",
    "dorado_segundos",
    "ejecuciones",
    "ejecuciones_lanzadas",
)
CLAVES_DIARIO = (
    "n",
    "corrida",
    "instance_id",
    "verificacion",
    "numero",
    "intento",
    "fecha_utc",
    "sha256_ejecucion",
    "previo",
)
GENESIS = "0" * 64  # Â«hash de la linea anteriorÂ» de la primera linea del diario
MODO_MEDICION, MODO_MUESTRA, MODO_ENSAYO = "medicion", "muestra", "ensayo"
# Codigos cerrados con que un verificador explica que no pudo medir (su texto libre no se imprime).
CODIGOS_FALLO = ("sin_parche_referencia", "tarea_ausente")
LOGGERS_ARNES = ("swegemma", "adk_submission", "adk")
UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
UTC_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")
ID_SEGURO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,200}$")
VERSION_RE = re.compile(r"[_-]v([0-9]+)", re.IGNORECASE)
NOMBRE_EJECUCION = re.compile(r"^(sin_parche|dorado)_([12])_([12])\.json$")
RESUMEN_PRUEBAS = re.compile(r"\b([0-9]+) (passed|failed|errors?)\b")


class ValidezError(ValueError):
    """Entrada o estado que no permite una medicion fiable (se informa con salida 2)."""


class SinCategoria(ValidezError):
    """Resultado del arnes que la lista cerrada de A.3 no clasifica (hace falta una enmienda)."""


class FalloVerificador(ValidezError):
    """El verificador no pudo medir una tarea; ``codigo`` es uno de ``CODIGOS_FALLO`` (nunca un texto)."""

    def __init__(self, codigo: str) -> None:
        super().__init__(codigo)
        self.codigo = codigo


@dataclass(frozen=True)
class Tarea:
    """Lo unico que el guion necesita de una tarea para ordenar, nombrar y agrupar."""

    instance_id: str
    repo: str


@dataclass(frozen=True)
class ResultadoVerificacion:
    """Lo que devuelve un verificador. ``error`` y ``salida`` solo viajan a ``--crudo``."""

    resolved: bool
    test_exit_code: int
    error: str | None
    duration_seconds: float
    passed: int | None = None
    failed: int | None = None
    errors: int | None = None
    salida: str = ""


# ``Verificador(tarea, "sin_parche" | "dorado")``: la misma funcion para las dos verificaciones.
Verificador = Callable[[Tarea, str], ResultadoVerificacion]
Reloj = Callable[[], datetime]


# ---------------------------------------------------------------------------
# Clasificacion (funciones puras)
# ---------------------------------------------------------------------------


def clasificar(sin_parche: Sequence[dict[str, Any]], dorado: Sequence[dict[str, Any]]) -> str:
    """Clase de una tarea desde la ejecucion final de cada una de sus cuatro rondas.

    ``sin_parche`` y ``dorado`` traen dos registros cada uno (con ``estado`` y ``resolved``).
    """
    if len(sin_parche) != 2 or len(dorado) != 2:
        raise ValidezError("Una tarea necesita exactamente dos ejecuciones finales por verificacion.")
    if any(e["estado"] == kaggle_replicas.ST_INFRA for e in (*sin_parche, *dorado)):
        return CLASE_NO_MEDIBLE
    s = [bool(e["resolved"]) for e in sin_parche]
    d = [bool(e["resolved"]) for e in dorado]
    if s[0] != s[1] or d[0] != d[1]:
        return CLASE_INESTABLE
    if s[0]:
        return CLASE_PASA
    if not d[0]:
        return CLASE_DORADO_FALLA
    return CLASE_DISCRIMINA


def guarda(tareas: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Repositorios donde salta la guarda de A.3: 10 tareas o mas y mas de la mitad no ``discrimina``."""
    por_repo: dict[str, list[str]] = {}
    for t in tareas:
        por_repo.setdefault(str(t["repo"]), []).append(str(t["clase"]))
    saltan = []
    for repo in sorted(por_repo):
        clases = por_repo[repo]
        malas = sum(1 for c in clases if c != CLASE_DISCRIMINA)
        if len(clases) >= GUARDA_MIN_TAREAS and 2 * malas > len(clases):
            saltan.append({"repo": repo, "tareas": len(clases), "no_discrimina": malas})
    return saltan


def contar_pruebas(salida: str) -> tuple[int | None, int | None, int | None]:
    """``(passed, failed, errors)`` de la ultima linea de resumen de pytest; ``None`` si no hay."""
    for linea in reversed(salida.splitlines()):
        hallados = RESUMEN_PRUEBAS.findall(linea)
        if not hallados:
            continue
        conteos = {"passed": 0, "failed": 0, "errors": 0}
        for n, palabra in hallados:
            conteos["errors" if palabra.startswith("error") else palabra] += int(n)
        return conteos["passed"], conteos["failed"], conteos["errors"]
    return None, None, None


def orden_muestra(ids: Sequence[str]) -> list[str]:
    """Identificadores por orden de ``sha256(instance_id)`` (A.4); el hash es solo un orden."""
    return sorted(ids, key=lambda i: hashlib.sha256(i.encode("utf-8")).hexdigest())


# ---------------------------------------------------------------------------
# Un registro versionable por ejecucion
# ---------------------------------------------------------------------------


def _entero(v: object, nombre: str, *, nulo: bool = False, minimo: int | None = None) -> int | None:
    if v is None and nulo:
        return None
    if isinstance(v, bool) or not isinstance(v, int) or (minimo is not None and v < minimo):
        raise ValidezError(f"El verificador devolvio un valor invalido en '{nombre}'.")
    return v


def validar_resultado(res: object) -> ResultadoVerificacion:
    """Comprueba la forma de lo que devolvio un verificador; otra cosa es salida 2."""
    if not isinstance(res, ResultadoVerificacion):
        raise ValidezError("El verificador no devolvio un ResultadoVerificacion.")
    if not isinstance(res.resolved, bool):
        raise ValidezError("El verificador devolvio un valor invalido en 'resolved'.")
    _entero(res.test_exit_code, "test_exit_code")
    for nombre in ("passed", "failed", "errors"):
        _entero(getattr(res, nombre), nombre, nulo=True, minimo=0)
    d = res.duration_seconds
    if isinstance(d, bool) or not isinstance(d, int | float) or not math.isfinite(d) or d < 0:
        raise ValidezError("El verificador devolvio una duracion invalida.")
    if res.error is not None and not isinstance(res.error, str):
        raise ValidezError("El verificador devolvio un valor invalido en 'error'.")
    if not isinstance(res.salida, str):
        raise ValidezError("El verificador devolvio un valor invalido en 'salida'.")
    return res


def registro_de_ejecucion(
    res: ResultadoVerificacion, verificacion: str, numero: int, intento: int, fecha_utc: str
) -> dict[str, Any]:
    """Registro versionable de una ejecucion: sin texto del arnes ni de las pruebas.

    Del ``error`` del arnes queda solo una categoria de ``CATEGORIAS``. Se clasifica con
    ``kaggle_replicas.classify_harness`` (la misma lista cerrada de la seccion A.3), con el tamano
    de parche fijado en 1: aqui no hay un agente que pueda dejar el parche vacio, y con tamano 0 el
    codigo -1 se leeria como Â«parche vacioÂ» en vez de como pruebas que no se pudieron ejecutar.
    Un error del arnes fuera de la lista cerrada lanza ``SinCategoria`` **sin** su texto. La fecha
    se valida con formato estricto: es el unico texto libre que viene del crudo.
    """
    validar_fecha_utc(fecha_utc)
    crudo = {
        "resolved": res.resolved,
        "error": res.error,
        "test_exit_code": res.test_exit_code,
        "agent_patch_size": 1,
        "total_llm_calls": 0,
    }
    try:
        estado, motivo, infra = kaggle_replicas.classify_harness(crudo, "verificacion")
    except kaggle_replicas.ReplicasError:
        raise SinCategoria(
            "Resultado del arnes que no se puede clasificar (error fuera de la lista cerrada o "
            "combinacion incoherente); no se registra nada."
        ) from None
    categoria = motivo or infra
    if categoria is not None and categoria not in CATEGORIAS:
        raise ValidezError("Categoria de error fuera de la lista cerrada.")
    return {
        "verificacion": verificacion,
        "numero": numero,
        "intento": intento,
        "estado": estado,
        "resolved": res.resolved,
        "codigo_salida": res.test_exit_code,
        "categoria": categoria,
        "passed": res.passed,
        "failed": res.failed,
        "errors": res.errors,
        "duracion_segundos": round(float(res.duration_seconds), 3),
        "fecha_utc": fecha_utc,
    }


def validar_fecha_utc(valor: object) -> str:
    """``AAAA-MM-DDTHH:MM:SSZ`` con fecha real; otra cosa es ``ValidezError`` (sin eco del valor)."""
    if not isinstance(valor, str) or not UTC_RE.fullmatch(valor):
        raise ValidezError("Una fecha UTC del crudo no tiene el formato AAAA-MM-DDTHH:MM:SSZ.")
    try:
        datetime.strptime(valor, UTC_FORMAT)
    except ValueError:
        raise ValidezError("Una fecha UTC del crudo no es una fecha real.") from None
    return valor


def registro_versionable(registro: dict[str, Any]) -> dict[str, Any]:
    """Proyeccion al registro versionable: solo lo que A.2 y A.4 enumeran (sin conteos ni fecha)."""
    return {k: registro[k] for k in CLAVES_EJECUCION_VERSIONADAS}


# ---------------------------------------------------------------------------
# Archivos: escritura sin sobrescribir, ruta cruda ignorada por git, almacen reanudable
# ---------------------------------------------------------------------------


def escribir_sin_sobrescribir(destino: Path, datos: bytes) -> None:
    """Crea ``destino`` con ``datos`` sin pisar nada: escribe un temporal y lo enlaza al destino.

    Si ``destino`` existe (tambien si aparece a mitad de camino) lanza ``ValidezError``. Si el
    sistema de archivos no admite enlaces duros, abre con creacion exclusiva.
    """
    destino.parent.mkdir(parents=True, exist_ok=True)
    existe = ValidezError(f"Ya existe {destino.name}: este guion no sobrescribe resultados.")
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


def a_json(obj: object) -> bytes:
    """JSON estable con saltos de linea LF, en bytes."""
    return (json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=False) + "\n").encode("utf-8")


def comprobar_crudo_ignorado(crudo: Path) -> None:
    """``crudo`` debe estar fuera de todo repositorio git, o ser una ruta ignorada por git.

    Si no se puede comprobar (git ausente, error de git) lanza ``ValidezError``: Â«no pude
    comprobarÂ» no es Â«esta ignoradaÂ».
    """
    base = crudo.resolve()
    while not base.exists():
        if base.parent == base:
            raise ValidezError(f"No hay ningun directorio existente sobre {crudo}.")
        base = base.parent
    if not base.is_dir():
        raise ValidezError(f"{crudo} no es un directorio.")
    en_repo = any((p / ".git").exists() for p in (base, *base.parents))
    if not en_repo:
        return
    sonda = crudo.resolve() / "sonda"
    try:
        r = subprocess.run(
            ["git", "-C", str(base), "check-ignore", "-q", "--", str(sonda)], capture_output=True
        )
    except OSError:
        raise ValidezError("No se pudo ejecutar git para comprobar que --crudo esta ignorada.") from None
    if r.returncode == 0:
        return
    if r.returncode == 1:
        raise ValidezError(
            f"--crudo ({crudo}) esta dentro de un repositorio y git no la ignora: las salidas crudas "
            "no pueden quedar en una ruta versionable."
        )
    raise ValidezError("git check-ignore fallo: no se pudo comprobar que --crudo este ignorada.")


class Almacen:
    """Salidas crudas y estado de reanudacion de una medicion (un archivo por ejecucion)."""

    def __init__(self, raiz: Path) -> None:
        self.raiz = raiz
        self.corrida = ""  # identificador de la corrida; lo fija el manifiesto
        self._diario: dict[tuple[str, str, int, int], str] = {}
        self._ultimo = GENESIS
        self._cargado = False

    @property
    def ruta_diario(self) -> Path:
        return self.raiz / "diario.jsonl"

    def _ruta(self, tarea: Tarea, verificacion: str, numero: int, intento: int) -> Path:
        if not ID_SEGURO.fullmatch(tarea.instance_id):
            raise ValidezError("Un instance_id no es seguro como nombre de archivo.")
        return self.raiz / "ejecuciones" / tarea.instance_id / f"{verificacion}_{numero}_{intento}.json"

    # -- diario de solo-anadir --------------------------------------------------------------------

    def _asegurar(self) -> None:
        """Verifica el diario contra el disco la primera vez que se usa el almacen."""
        if not self._cargado:
            self.verificar_diario()

    def verificar_diario(self) -> None:
        """Comprueba la cadena del diario y que diario y disco coincidan exactamente.

        Toda ejecucion del diario debe existir con el SHA-256 anotado y toda ejecucion en disco debe
        estar en el diario; si no, ``ValidezError``. Esto hace visible borrar o editar una ejecucion,
        no lo impide.
        """
        entradas: dict[tuple[str, str, int, int], str] = {}
        previo = GENESIS
        if self.ruta_diario.is_file():
            datos = self.ruta_diario.read_bytes()
            if datos and not datos.endswith(b"\n"):
                raise ValidezError("El diario esta truncado (la ultima linea no termina en salto de linea).")
            for numero, linea in enumerate(datos.split(b"\n")[:-1], start=1):
                entrada = self._leer_linea(linea, numero, previo)
                clave = (
                    entrada["instance_id"],
                    entrada["verificacion"],
                    entrada["numero"],
                    entrada["intento"],
                )
                if clave in entradas:
                    raise ValidezError("El diario repite una ejecucion.")
                entradas[clave] = entrada["sha256_ejecucion"]
                previo = hashlib.sha256(linea).hexdigest()
        for (iid, verif, num, intento), sha in entradas.items():
            ruta = self._ruta(Tarea(iid, ""), verif, num, intento)
            if not ruta.is_file():
                raise ValidezError(f"El diario anota una ejecucion que ya no esta en disco ({ruta.name}).")
            if hashlib.sha256(ruta.read_bytes()).hexdigest() != sha:
                raise ValidezError(f"La ejecucion {ruta.name} no tiene el SHA-256 anotado en el diario.")
        carpeta = self.raiz / "ejecuciones"
        if carpeta.is_dir():
            for ruta in sorted(carpeta.glob("*/*")):
                if ruta.name.startswith(".") and ruta.name.endswith(".tmp"):
                    continue  # temporal de una escritura cortada: no es una ejecucion
                m = NOMBRE_EJECUCION.fullmatch(ruta.name)
                if m is None or (ruta.parent.name, m[1], int(m[2]), int(m[3])) not in entradas:
                    raise ValidezError(f"Hay una ejecucion en disco que no esta en el diario ({ruta.name}).")
        self._diario = entradas
        self._ultimo = previo
        self._cargado = True

    def _leer_linea(self, linea: bytes, numero: int, previo: str) -> dict[str, Any]:
        try:
            obj = kaggle_replicas.loads_strict(linea.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise ValidezError(f"La linea {numero} del diario es ilegible.") from None
        ok = (
            isinstance(obj, dict)
            and set(obj) == set(CLAVES_DIARIO)
            and obj["n"] == numero
            and obj["previo"] == previo
            and obj["corrida"] == self.corrida
            and isinstance(obj["instance_id"], str)
            and ID_SEGURO.fullmatch(obj["instance_id"]) is not None
            and obj["verificacion"] in (VERIF_SIN, VERIF_DORADO)
            and obj["numero"] in (1, 2)
            and obj["intento"] in (1, 2)
            and isinstance(obj["sha256_ejecucion"], str)
            and re.fullmatch(r"[0-9a-f]{64}", obj["sha256_ejecucion"]) is not None
        )
        if not ok:
            raise ValidezError(f"La linea {numero} del diario no es valida o rompe la cadena de hashes.")
        validar_fecha_utc(obj["fecha_utc"])
        assert isinstance(obj, dict)
        return obj

    def _anotar(
        self, tarea: Tarea, verificacion: str, numero: int, intento: int, fecha: str, sha: str
    ) -> None:
        linea = json.dumps(
            {
                "n": len(self._diario) + 1,
                "corrida": self.corrida,
                "instance_id": tarea.instance_id,
                "verificacion": verificacion,
                "numero": numero,
                "intento": intento,
                "fecha_utc": fecha,
                "sha256_ejecucion": sha,
                "previo": self._ultimo,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        with open(self.ruta_diario, "ab") as f:
            f.write(linea + b"\n")
        self._diario[(tarea.instance_id, verificacion, numero, intento)] = sha
        self._ultimo = hashlib.sha256(linea).hexdigest()

    def lanzadas(self, instance_id: str) -> int:
        """Ejecuciones lanzadas de una tarea, segun el diario."""
        self._asegurar()
        return sum(1 for (iid, *_resto) in self._diario if iid == instance_id)

    def diario_sha256(self) -> str:
        """Hash final del diario: el de su ultima linea, que encadena todas las anteriores."""
        self._asegurar()
        return self._ultimo

    # -- ejecuciones ------------------------------------------------------------------------------

    def existe(self, tarea: Tarea, verificacion: str, numero: int, intento: int) -> bool:
        self._asegurar()
        return self._ruta(tarea, verificacion, numero, intento).is_file()

    def leer(self, tarea: Tarea, verificacion: str, numero: int, intento: int) -> dict[str, Any] | None:
        """Registro guardado de una ejecucion, o ``None`` si no se ha corrido.

        Recalcula el registro desde el resultado crudo guardado y exige que coincida con el
        guardado y con el diario: una discrepancia es ``ValidezError`` (no se puede elegir cual vale).
        """
        self._asegurar()
        ruta = self._ruta(tarea, verificacion, numero, intento)
        clave = (tarea.instance_id, verificacion, numero, intento)
        if not ruta.is_file():
            if clave in self._diario:
                raise ValidezError(f"El diario anota {ruta.name} pero la ejecucion no esta en disco.")
            return None
        if self._diario.get(clave) != hashlib.sha256(ruta.read_bytes()).hexdigest():
            raise ValidezError(f"La ejecucion {ruta.name} no esta en el diario con ese SHA-256.")
        try:
            obj = kaggle_replicas.loads_strict(ruta.read_text(encoding="utf-8"))
            guardado = obj["registro"]
            crudo = obj["resultado"]
            res = validar_resultado(ResultadoVerificacion(**crudo))
            recalculado = registro_de_ejecucion(res, verificacion, numero, intento, guardado["fecha_utc"])
        except (OSError, ValueError, KeyError, TypeError) as exc:
            if isinstance(exc, ValidezError):
                raise
            raise ValidezError(f"Ejecucion guardada ilegible: {ruta.name}.") from None
        if recalculado != guardado:
            raise ValidezError(
                f"Discrepancia entre lo guardado y lo recalculado en {ruta.name}: no se reanuda."
            )
        return recalculado

    def guardar(
        self,
        tarea: Tarea,
        verificacion: str,
        numero: int,
        intento: int,
        res: ResultadoVerificacion,
        registro: dict[str, Any],
    ) -> None:
        """Guarda resultado crudo y registro; falla si la ejecucion ya estaba guardada."""
        self._asegurar()
        ruta = self._ruta(tarea, verificacion, numero, intento)
        crudo = {
            "resolved": res.resolved,
            "test_exit_code": res.test_exit_code,
            "error": res.error,
            "duration_seconds": res.duration_seconds,
            "passed": res.passed,
            "failed": res.failed,
            "errors": res.errors,
            "salida": res.salida,
        }
        datos = a_json({"resultado": crudo, "registro": registro})
        escribir_sin_sobrescribir(ruta, datos)
        self._anotar(
            tarea, verificacion, numero, intento, registro["fecha_utc"], hashlib.sha256(datos).hexdigest()
        )

    def comprobar_manifiesto(self, manifiesto: dict[str, Any]) -> None:
        """Crea el manifiesto de ``--crudo`` o exige que coincida con el de la medicion anterior.

        El manifiesto fija el modo (medicion, muestra o ensayo), el entorno, ``tasks.jsonl`` y el
        directorio de snapshots, y un identificador de corrida que lleva cada linea del diario. Un
        ``--crudo`` no se comparte entre modos ni entre entornos: se nombran los campos que difieren.
        """
        self.raiz.mkdir(parents=True, exist_ok=True)
        ruta = self.raiz / "manifiesto.json"
        nuevo = {"schema_version": SCHEMA_MANIFIESTO, **manifiesto}
        if not ruta.is_file():
            self.corrida = uuid.uuid4().hex
            escribir_sin_sobrescribir(ruta, a_json({**nuevo, "corrida": self.corrida}))
            self._cargado = False
            return
        try:
            previo = kaggle_replicas.loads_strict(ruta.read_text(encoding="utf-8"))
            corrida = previo.pop("corrida")
        except (OSError, ValueError, KeyError, AttributeError):
            raise ValidezError("manifiesto.json de --crudo ilegible.") from None
        if previo != nuevo or not isinstance(corrida, str) or not corrida:
            difieren = sorted(k for k in {*previo, *nuevo} if previo.get(k) != nuevo.get(k))
            raise ValidezError(
                "--crudo pertenece a otra medicion (campos que difieren: "
                f"{', '.join(difieren) or 'corrida'}): no se mezclan modos, entornos ni snapshots."
            )
        self.corrida = corrida
        self._cargado = False


# ---------------------------------------------------------------------------
# Medicion de una tarea
# ---------------------------------------------------------------------------


def _ronda(
    tarea: Tarea,
    verificacion: str,
    numero: int,
    verificador: Verificador,
    almacen: Almacen,
    reloj: Reloj,
) -> list[dict[str, Any]]:
    """Intentos de una ronda: la ejecucion y, si es de infraestructura, una repeticion."""
    existentes = [almacen.existe(tarea, verificacion, numero, i) for i in (1, 2)]
    if existentes[1] and not existentes[0]:
        raise ValidezError("Hay una repeticion guardada sin su primera ejecucion.")
    intentos: list[dict[str, Any]] = []
    for intento in range(1, MAX_INTENTOS + 1):
        reg = almacen.leer(tarea, verificacion, numero, intento)
        if reg is None:
            donde = f"en {tarea.instance_id}, {verificacion} {numero}"
            try:
                bruto = verificador(tarea, verificacion)
            except FalloVerificador as exc:
                raise ValidezError(
                    f"El verificador no pudo medir ({exc.codigo}) {donde}: no se registra nada."
                ) from None
            except Exception as exc:  # solo el tipo: el texto de la excepcion puede traer datos
                raise ValidezError(
                    f"El verificador fallo ({type(exc).__name__}) {donde}: no se registra nada y se puede "
                    "reanudar."
                ) from None
            res = validar_resultado(bruto)
            fecha = reloj().astimezone(UTC).strftime(UTC_FORMAT)
            try:
                reg = registro_de_ejecucion(res, verificacion, numero, intento, fecha)
            except SinCategoria:
                raise ValidezError(
                    f"Resultado del arnes sin categoria {donde} (por ejemplo, un codigo de salida fuera de "
                    "la lista cerrada de A.3): hace falta una enmienda del pre-registro (I.4) antes de "
                    "seguir; no se registro nada."
                ) from None
            almacen.guardar(tarea, verificacion, numero, intento, res, reg)
        intentos.append(reg)
        if reg["estado"] != kaggle_replicas.ST_INFRA:
            break
    if intentos[-1]["estado"] != kaggle_replicas.ST_INFRA and almacen.existe(
        tarea, verificacion, numero, len(intentos) + 1
    ):
        raise ValidezError("Hay una repeticion guardada de una ejecucion que no era de infraestructura.")
    return intentos


def medir_tarea(tarea: Tarea, verificador: Verificador, almacen: Almacen, reloj: Reloj) -> dict[str, Any]:
    """Corre (o reanuda) las cuatro rondas de una tarea y devuelve su registro versionable."""
    finales: dict[str, list[dict[str, Any]]] = {VERIF_SIN: [], VERIF_DORADO: []}
    todas: list[dict[str, Any]] = []
    for verificacion, numero in RONDAS:
        intentos = _ronda(tarea, verificacion, numero, verificador, almacen, reloj)
        todas.extend(intentos)
        finales[verificacion].append(intentos[-1])
    lanzadas = almacen.lanzadas(tarea.instance_id)
    if lanzadas != len(todas):
        raise ValidezError("El diario y las ejecuciones de una tarea no coinciden en su numero.")
    return {
        "instance_id": tarea.instance_id,
        "repo": tarea.repo,
        "clase": clasificar(finales[VERIF_SIN], finales[VERIF_DORADO]),
        "sin_parche_segundos": [e["duracion_segundos"] for e in finales[VERIF_SIN]],
        "dorado_segundos": [e["duracion_segundos"] for e in finales[VERIF_DORADO]],
        "ejecuciones": [registro_versionable(e) for e in todas],
        "ejecuciones_lanzadas": lanzadas,
    }


# ---------------------------------------------------------------------------
# Registro final y su validacion contra la compuerta
# ---------------------------------------------------------------------------


def construir_registro(
    tareas: Sequence[dict[str, Any]],
    *,
    sha256_tasks: str,
    entorno_sha256: str,
    fecha: str,
    diario_sha256: str,
) -> dict[str, Any]:
    """Registro ``kaggle-task-validity/1``: las claves de la compuerta mas ``diario_sha256``.

    ``tareas_invalidas`` es la lista que lee ``kaggle_split.py --calibracion``: toda tarea cuya clase
    no es ``discrimina``. ``diario_sha256`` es el hash final del diario de ``--crudo``.
    """
    ordenadas = sorted(tareas, key=lambda t: str(t["instance_id"]))
    invalidas = [
        {"instance_id": t["instance_id"], "clase": t["clase"]}
        for t in ordenadas
        if t["clase"] != CLASE_DISCRIMINA
    ]
    return {
        "schema_version": SCHEMA_VALIDEZ,
        "fecha": fecha,
        "sha256_tasks": sha256_tasks,
        "entorno_sha256": entorno_sha256,
        "tareas": ordenadas,
        "tareas_invalidas": invalidas,
        "diario_sha256": diario_sha256,
    }


def validar_registro(obj: object) -> list[str]:
    """Problemas del registro contra el esquema de ``kaggle_prereg`` y las claves propias.

    Lista vacia = el registro pasa la validacion que hace la compuerta al cerrar ``validez_tareas``
    (sin el cruce con ``tasks.jsonl``, que lo hace ``comprobar --tasks``). ``diario_sha256`` y
    ``ejecuciones_lanzadas`` son obligatorios tambien en la compuerta.
    """
    if not isinstance(obj, dict):
        return ["El registro debe ser un objeto."]
    esquema = kaggle_prereg.VALIDEZ
    if set(obj) != set(esquema):
        return [f"Claves del registro: se esperaban {sorted(esquema)}, hay {sorted(obj)}."]
    problemas = [f"'{k}' invalido." for k, ok in esquema.items() if not ok(obj[k])]
    if problemas:
        return problemas
    for t in obj["tareas"]:
        if set(t) != set(CLAVES_TAREA):
            problemas.append("Una tarea no tiene exactamente las claves del registro.")
            continue
        if t["ejecuciones_lanzadas"] != len(t["ejecuciones"]):
            problemas.append("'ejecuciones_lanzadas' no es el numero de ejecuciones de la tarea.")
        for e in t["ejecuciones"]:
            if (
                not isinstance(e, dict)
                or set(e) != set(CLAVES_EJECUCION_VERSIONADAS)
                or e["estado"] not in ESTADOS
                or e["categoria"] not in (None, *CATEGORIAS)
            ):
                problemas.append("Una ejecucion no tiene la forma del registro.")
    invalidas = {t["instance_id"]: t["clase"] for t in obj["tareas"] if t["clase"] != CLASE_DISCRIMINA}
    listadas = {x["instance_id"]: x["clase"] for x in obj["tareas_invalidas"]}
    if listadas != invalidas or len(obj["tareas_invalidas"]) != len(invalidas):
        problemas.append("'tareas_invalidas' no es la lista de tareas cuya clase no es 'discrimina'.")
    return problemas


def resumen_texto(tareas: Sequence[dict[str, Any]]) -> str:
    """Conteo por clase y por repositorio, sin identificadores."""
    por_clase: dict[str, int] = {}
    por_repo: dict[str, dict[str, int]] = {}
    for t in tareas:
        por_clase[t["clase"]] = por_clase.get(t["clase"], 0) + 1
        r = por_repo.setdefault(t["repo"], {})
        r[t["clase"]] = r.get(t["clase"], 0) + 1
    lineas = [f"Tareas medidas: {len(tareas)}", "Por clase: " + json.dumps(por_clase, sort_keys=True)]
    lineas.extend(f"  {repo}: {json.dumps(c, sort_keys=True)}" for repo, c in sorted(por_repo.items()))
    return "\n".join(lineas)


# ---------------------------------------------------------------------------
# Entradas
# ---------------------------------------------------------------------------


def leer_tareas(ruta: Path) -> list[Tarea]:
    """Identificador y repositorio de cada tarea de ``tasks.jsonl``, ordenadas por ``instance_id``."""
    filas: list[Any] = []
    try:
        with open(ruta, encoding="utf-8") as f:
            for linea in f:
                if linea.strip():
                    filas.append(kaggle_replicas.loads_strict(linea))  # rechaza claves repetidas
    except (OSError, ValueError):
        # sin el texto del error: puede citar un fragmento de la linea
        raise ValidezError("tasks.jsonl es ilegible, no es JSON valido o repite una clave.") from None
    tareas: list[Tarea] = []
    vistos: set[str] = set()
    for pos, fila in enumerate(filas):
        iid = fila.get("instance_id") if isinstance(fila, dict) else None
        repo = fila.get("repo") if isinstance(fila, dict) else None
        if not isinstance(iid, str) or not ID_SEGURO.fullmatch(iid) or not isinstance(repo, str) or not repo:
            raise ValidezError(f"La tarea en la posicion {pos} no tiene instance_id y repo validos.")
        if iid in vistos:
            raise ValidezError(f"instance_id repetido en tasks.jsonl (posicion {pos}).")
        vistos.add(iid)
        tareas.append(Tarea(iid, repo))
    if not tareas:
        raise ValidezError("tasks.jsonl no tiene tareas.")
    return sorted(tareas, key=lambda t: t.instance_id)


def leer_entorno(ruta: Path) -> tuple[dict[str, Any], str]:
    """Declaracion del entorno (``kaggle-sandbox-env/1``) y su SHA-256, validada con el esquema."""
    try:
        datos = ruta.read_bytes()
        obj = kaggle_prereg.loads_strict(datos.decode("utf-8"))
    except (OSError, ValueError):
        raise ValidezError(f"No se pudo leer la declaracion del entorno {ruta}.") from None
    esquema = kaggle_prereg.ENTORNO
    if not isinstance(obj, dict) or set(obj) != set(esquema):
        raise ValidezError("La declaracion del entorno no tiene las claves de 'kaggle-sandbox-env/1'.")
    malos = sorted(k for k, ok in esquema.items() if not ok(obj[k]))
    if malos:
        raise ValidezError(f"La declaracion del entorno tiene valores invalidos: {malos}.")
    return obj, hashlib.sha256(datos).hexdigest()


def leer_referencia(ruta: Path) -> tuple[dict[str, Any], str]:
    """Registro de validez anterior (para el modo muestra), validado, y su SHA-256."""
    try:
        datos = ruta.read_bytes()
        obj = kaggle_prereg.loads_strict(datos.decode("utf-8"))
    except (OSError, ValueError):
        raise ValidezError(f"No se pudo leer el registro de referencia {ruta}.") from None
    problemas = validar_registro(obj)
    if problemas:
        raise ValidezError("El registro de referencia no es valido: " + "; ".join(problemas))
    assert isinstance(obj, dict)
    return obj, hashlib.sha256(datos).hexdigest()


def elegir_tareas(
    todas: Sequence[Tarea], task_ids: Sequence[str] | None, referencia: dict[str, Any] | None
) -> list[Tarea]:
    """Tareas a medir, en orden determinista (por ``instance_id``)."""
    por_id = {t.instance_id: t for t in todas}
    if referencia is not None:
        excluidas = [t["instance_id"] for t in referencia["tareas"] if t["clase"] != CLASE_DISCRIMINA]
        ids = {*excluidas, *orden_muestra(list(por_id))[:MUESTRA_PRIMERAS]}
    elif task_ids:
        ids = set(task_ids)
    else:
        ids = set(por_id)
    desconocidas = ids - set(por_id)
    if desconocidas:
        raise ValidezError(f"{len(desconocidas)} identificador(es) no estan en tasks.jsonl.")
    return [por_id[i] for i in sorted(ids)]


# ---------------------------------------------------------------------------
# El verificador real: la funcion de verificacion del arnes ``swegemma``
# ---------------------------------------------------------------------------


SnapshotResolver = Callable[[Path, str, str], tuple[Path, Path | None, Path | None]]


@dataclass(frozen=True)
class Arnes:
    """Lo que el guion usa del arnes real: verificar, comprobar snapshots y limpiar el sandbox."""

    verificar: Verificador
    faltan: Callable[[Sequence[Tarea]], int]
    limpiar: Callable[[], None]


def buscar_secret_dir(*raices: Path) -> Path | None:
    """Directorio ``secret`` hermano de ``tasks.jsonl`` o de los snapshots, como lo busca el arnes.

    Es el primer ``secret/`` con ``solution.parquet`` o ``solution.csv`` entre los ancestros de cada
    raiz (en el orden dado, empezando por la propia raiz).
    """
    for raiz in raices:
        try:
            resuelta = raiz.resolve()
        except OSError:
            continue
        for ancestro in (resuelta, *resuelta.parents):
            candidato = ancestro / "secret"
            if (candidato / "solution.parquet").is_file() or (candidato / "solution.csv").is_file():
                return candidato
    return None


def ubicar_snapshot(
    resolver: SnapshotResolver, snapshots_dir: Path, secret_dir: Path | None, tarea: Tarea
) -> tuple[Path, Path | None, Path | None]:
    """``(snapshot, base, parche)`` con la misma resolucion que el arnes: primero ``snapshots_dir``;
    si el snapshot no existe, bajo ``<secret>/sandbox/snapshots`` cuando ese directorio existe."""
    ruta = resolver(snapshots_dir, tarea.instance_id, tarea.repo)
    if not ruta[0].exists() and secret_dir is not None and (secret_dir / "sandbox" / "snapshots").is_dir():
        return resolver(secret_dir / "sandbox" / "snapshots", tarea.instance_id, tarea.repo)
    return ruta


def contar_snapshots_faltantes(
    tareas: Sequence[Tarea], resolver: SnapshotResolver, snapshots_dir: Path, secret_dir: Path | None
) -> int:
    """Cuantas tareas elegidas no tienen snapshot en ninguna de las dos ubicaciones."""
    return sum(1 for t in tareas if not ubicar_snapshot(resolver, snapshots_dir, secret_dir, t)[0].exists())


def redirigir_registros(archivo: Path) -> logging.Handler:
    """Dirige los loggers ``swegemma*`` y ``adk*`` a ``archivo``, sin propagar a stderr.

    El arnes registra con ``logger.error`` el detalle de un parche que no aplica: eso es salida
    cruda y no puede salir por la consola.
    """
    archivo.parent.mkdir(parents=True, exist_ok=True)
    manejador = logging.FileHandler(archivo, encoding="utf-8")
    nombres = {
        *LOGGERS_ARNES,
        *(n for n in logging.root.manager.loggerDict if n.startswith(("swegemma", "adk"))),
    }
    for nombre in nombres:
        logger = logging.getLogger(nombre)
        logger.handlers[:] = [manejador]
        logger.propagate = False
    return manejador


def comprobar_timeout(esperado: object, real: object) -> None:
    """``timeout_seconds`` del pre-registro debe ser el que aplica el arnes; si difieren, ``ValidezError``."""
    if esperado != real:
        raise ValidezError(
            "El timeout por comando que aplica el arnes no es el timeout_seconds del pre-registro."
        )


def construir_arnes_swegemma(
    *,
    tasks_path: Path,
    snapshots_dir: Path,
    crudo: Path,
    imagen: str,
    sandbox: str,
    version_arnes: str,
    timeout_seconds: int,
) -> Arnes:
    """Arnes real sobre ``swegemma.harness.verification.verify_task`` (importacion perezosa).

    Llama a ``verify_task(docker, config, task, snapshot_path, base_snapshot_path=..., patch_path=...,
    agent_patch=<'' o parche de referencia>, start_time=time.perf_counter())``, que es la misma
    funcion que usa ``swegemma eval`` en su fase 2. El parche de referencia se lee de la tarea
    dentro de esta funcion y no sale de ella. Sin el paquete, o con otra version que la declarada,
    lanza ``ValidezError``. Los loggers del arnes van a ``<crudo>/arnes.log``. El timeout por comando
    es ``timeout_seconds`` del pre-registro, y si el arnes aplica otro, ``ValidezError``.
    """
    try:
        instalada = importlib.metadata.version("swegemma")
        config_mod = importlib.import_module("swegemma.config")
        dedup_mod = importlib.import_module("swegemma.deduplication")
        eval_mod = importlib.import_module("swegemma.evaluate")
        verif_mod = importlib.import_module("swegemma.harness.verification")
        models_mod = importlib.import_module("swegemma.models")
        adk_mod = importlib.import_module("adk_submission")
    except (ImportError, importlib.metadata.PackageNotFoundError):
        raise ValidezError(
            "El paquete 'swegemma' no esta instalado en este entorno de Python: la verificacion real "
            "no se puede ejecutar (instale el arnes declarado o use el entorno donde esta)."
        ) from None
    if instalada != version_arnes:
        raise ValidezError(
            f"swegemma {instalada} instalado, pero la declaracion del entorno dice {version_arnes}."
        )
    redirigir_registros(crudo / "arnes.log")
    config = config_mod.EvalConfig(
        tasks_path=tasks_path,
        snapshots_dir=snapshots_dir,
        results_dir=crudo / "arnes",
        submission_dir=crudo / "arnes_envio",
        models=adk_mod.ModelRegistry(),
        image=imagen,
        sandbox=sandbox,
        timeout_seconds=timeout_seconds,
        skip_agent_patch=True,
        display_mode="quiet",
    )
    comprobar_timeout(timeout_seconds, config.harness.command_timeout_seconds)
    evaluator = eval_mod.Evaluator(config)
    resolver: SnapshotResolver = dedup_mod.resolve_task_snapshot_paths
    secret_dir = buscar_secret_dir(tasks_path, snapshots_dir)
    tareas = {
        t.instance_id: evaluator._hydrate_task_from_secret(t) for t in models_mod.load_tasks(tasks_path)
    }

    def faltan(elegidas: Sequence[Tarea]) -> int:
        return contar_snapshots_faltantes(elegidas, resolver, snapshots_dir, secret_dir)

    def limpiar() -> None:
        cleanup = getattr(evaluator.docker, "cleanup_all", None)
        if cleanup is not None:
            cleanup()

    def verificar(tarea: Tarea, verificacion: str) -> ResultadoVerificacion:
        task = tareas.get(tarea.instance_id)
        if task is None:
            raise FalloVerificador("tarea_ausente")
        parche = ""
        if verificacion == VERIF_DORADO:
            parche = str(task.patch or "")
            if not parche.strip():
                raise FalloVerificador("sin_parche_referencia")
        inicio = time.perf_counter()
        snap, base, parche_ruta = ubicar_snapshot(resolver, snapshots_dir, secret_dir, tarea)
        if not snap.exists():
            return ResultadoVerificacion(False, -1, "Snapshot file not found:", time.perf_counter() - inicio)
        try:
            res = asyncio.run(
                verif_mod.verify_task(
                    evaluator.docker,
                    config,
                    task,
                    snap,
                    base_snapshot_path=base,
                    patch_path=parche_ruta,
                    agent_patch=parche,
                    start_time=inicio,
                )
            )
        except Exception as exc:  # igual que el arnes: un fallo del worker es infraestructura
            return ResultadoVerificacion(
                False,
                -1,
                f"Unexpected evaluation worker error: {type(exc).__name__}",
                time.perf_counter() - inicio,
            )
        salida = str(getattr(res, "test_output", "") or "")
        passed, failed, errors = contar_pruebas(salida)
        error = getattr(res, "error", None)
        return ResultadoVerificacion(
            resolved=bool(res.resolved),
            test_exit_code=int(res.test_exit_code),
            error=None if error is None else str(error),
            duration_seconds=float(res.duration_seconds),
            passed=passed,
            failed=failed,
            errors=errors,
            salida=salida,
        )

    return Arnes(verificar=verificar, faltan=faltan, limpiar=limpiar)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _comparar_muestra(referencia: dict[str, Any], medidas: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Compara la clase de cada tarea de la muestra con la del registro de referencia."""
    clase_ref = {t["instance_id"]: t["clase"] for t in referencia["tareas"]}
    filas = []
    for t in sorted(medidas, key=lambda x: str(x["instance_id"])):
        ref = clase_ref.get(t["instance_id"])
        if ref is None:
            raise ValidezError("Una tarea de la muestra no esta en el registro de referencia.")
        filas.append(
            {
                "instance_id": t["instance_id"],
                "clase_referencia": ref,
                "clase_repeticion": t["clase"],
                "coincide": ref == t["clase"],
            }
        )
    return {
        "schema_version": SCHEMA_MUESTRA,
        "coincide": all(f["coincide"] for f in filas),
        "tareas": filas,
    }


def _revisar_salida(ruta: Path | None, crudo: Path, nombre: str) -> None:
    if ruta is None:
        return
    if ruta.exists():
        raise ValidezError(f"Ya existe el archivo de {nombre}: este guion no sobrescribe resultados.")
    if ruta.resolve().is_relative_to(crudo.resolve()):
        raise ValidezError(f"El archivo de {nombre} no puede estar dentro de --crudo.")


def revisar_version(ruta: Path, entorno_sha: str) -> None:
    """A.3: solo hay ``_v1`` y ``_v2``; ``_v2`` exige el ``_v1`` conservado y un entorno distinto.

    Cualquier ``v<N>`` con N > 2 en el nombre (``_v3``, ``-V3``, ``_v3_final``) se rechaza.
    """
    numeros = [int(m.group(1)) for m in VERSION_RE.finditer(ruta.stem)]
    if any(n > 2 for n in numeros):
        raise ValidezError("A.3: no hay una tercera medicion (_v3 o posterior); la decision es del dueno.")
    if 2 not in numeros:
        return
    anterior = ruta.with_name(re.sub(r"([_-]v)2", r"\g<1>1", ruta.name, count=1, flags=re.IGNORECASE))
    if anterior == ruta or not anterior.is_file():
        raise ValidezError("A.3: una medicion _v2 exige que se conserve el archivo _v1 anterior.")
    previo, _ = leer_referencia(anterior)
    if previo["entorno_sha256"] == entorno_sha:
        raise ValidezError("A.3: la medicion _v2 exige declarar un entorno distinto del de la _v1.")


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="kaggle_validez",
        description="Mide la validez de las tareas de la linea base A (pre-registro, seccion A.2 a A.4).",
    )
    p.add_argument("--tasks", type=Path, required=True, help="tasks.jsonl de la competencia.")
    p.add_argument("--snapshots-dir", type=Path, required=True, help="Directorio de snapshots del arnes.")
    p.add_argument(
        "--entorno", type=Path, required=True, help="Declaracion del entorno (kaggle-sandbox-env/1)."
    )
    p.add_argument("--imagen", required=True, help="Imagen del sandbox; debe ser la de la declaracion.")
    p.add_argument("--sandbox", choices=kaggle_prereg.BACKENDS, default="docker")
    p.add_argument("--crudo", type=Path, required=True, help="Salidas crudas y estado (ignorada por git).")
    p.add_argument("--salida", type=Path, help="Registro versionable (medicion completa); no se sobrescribe.")
    p.add_argument(
        "--task-ids", nargs="+", metavar="ID", help="Medicion parcial: solo estas tareas, sin registro."
    )
    p.add_argument(
        "--muestra-desde", type=Path, help="Registro anterior: repite sus excluidas y las 10 primeras."
    )
    p.add_argument("--comparacion", type=Path, help="Salida de la comparacion (con --muestra-desde).")
    p.add_argument(
        "--params", type=Path, help="linea_base_a.json: exige que el hash de tasks.jsonl sea el registrado."
    )
    return p


def ejecutar(
    args: argparse.Namespace,
    verificador: Verificador | None,
    reloj: Reloj,
    faltan_snapshots: Callable[[Sequence[Tarea]], int] | None = None,
) -> int:
    """Cuerpo de la CLI; lanza ``ValidezError`` ante cualquier causa de salida 2."""
    muestra = args.muestra_desde is not None
    if muestra and (args.task_ids or args.salida or args.comparacion is None):
        raise ValidezError("--muestra-desde exige --comparacion y no admite --task-ids ni --salida.")
    if not muestra and args.comparacion is not None:
        raise ValidezError("--comparacion solo se usa con --muestra-desde.")
    if args.task_ids and args.salida:
        raise ValidezError("--task-ids es una medicion parcial: no escribe el registro (quite --salida).")
    if not muestra and not args.task_ids and args.salida is None:
        raise ValidezError("Una medicion completa necesita --salida (use --task-ids para una parcial).")

    if not args.tasks.is_file():
        raise ValidezError(f"No existe tasks.jsonl: {args.tasks}")
    sha_tasks = kaggle_split.compute_sha256(args.tasks)
    fijos: dict[str, Any] | None = None
    if args.params is not None:
        try:
            fijos = kaggle_prereg.load_params(args.params)["fijos"]
            esperado = fijos["tasks_sha256"]
        except (kaggle_prereg.PreregError, KeyError, TypeError) as exc:
            raise ValidezError(f"No se pudo leer --params: {exc}") from None
        if sha_tasks != esperado:
            raise ValidezError("El SHA-256 de tasks.jsonl no es el registrado en el pre-registro.")
    entorno, entorno_sha = leer_entorno(args.entorno)
    if entorno["imagen"] != args.imagen or entorno["backend"] != args.sandbox:
        raise ValidezError("--imagen y --sandbox no coinciden con la declaracion del entorno.")

    comprobar_crudo_ignorado(args.crudo)
    _revisar_salida(args.salida, args.crudo, "registro")
    _revisar_salida(args.comparacion, args.crudo, "comparacion")
    if args.salida is not None:
        revisar_version(args.salida, entorno_sha)

    todas = leer_tareas(args.tasks)
    referencia: dict[str, Any] | None = None
    sha_referencia: str | None = None
    if muestra:
        referencia, sha_referencia = leer_referencia(args.muestra_desde)
        if referencia["sha256_tasks"] != sha_tasks:
            raise ValidezError("El registro de referencia es de otro tasks.jsonl.")
        if referencia["entorno_sha256"] != entorno_sha:
            raise ValidezError("El registro de referencia es de otro entorno: la muestra exige el mismo.")
    elegidas = elegir_tareas(todas, args.task_ids, referencia)

    arnes: Arnes | None = None
    faltan = faltan_snapshots
    if verificador is None:
        if fijos is None:
            raise ValidezError("La verificacion real necesita --params (timeout_seconds del pre-registro).")
        arnes = construir_arnes_swegemma(
            tasks_path=args.tasks,
            snapshots_dir=args.snapshots_dir,
            crudo=args.crudo,
            imagen=args.imagen,
            sandbox=args.sandbox,
            version_arnes=entorno["version_arnes"],
            timeout_seconds=int(fijos["timeout_seconds"]),
        )
        verificador, faltan = arnes.verificar, arnes.faltan
    try:
        return _medir_y_escribir(
            args,
            verificador,
            faltan,
            reloj,
            entorno,
            entorno_sha,
            sha_tasks,
            sha_referencia,
            referencia,
            elegidas,
        )
    finally:
        if arnes is not None:
            with contextlib.suppress(Exception):
                arnes.limpiar()


def _medir_y_escribir(
    args: argparse.Namespace,
    verificador: Verificador,
    faltan: Callable[[Sequence[Tarea]], int] | None,
    reloj: Reloj,
    entorno: dict[str, Any],
    entorno_sha: str,
    sha_tasks: str,
    sha_referencia: str | None,
    referencia: dict[str, Any] | None,
    elegidas: Sequence[Tarea],
) -> int:
    """Segunda mitad de ``ejecutar``: snapshots, manifiesto, medicion y escritura."""
    if faltan is not None:
        n = faltan(elegidas)
        if n:
            raise ValidezError(
                f"Faltan los snapshots de {n} de las {len(elegidas)} tareas elegidas: un snapshot ausente no "
                "es una propiedad de la tarea, y no se mide hasta tenerlos todos."
            )
    modo = MODO_MUESTRA if referencia is not None else MODO_ENSAYO if args.task_ids else MODO_MEDICION
    almacen = Almacen(args.crudo)
    almacen.comprobar_manifiesto(
        {
            "modo": modo,
            "sha256_tasks": sha_tasks,
            "entorno_sha256": entorno_sha,
            "imagen": args.imagen,
            "sandbox": args.sandbox,
            "version_arnes": entorno["version_arnes"],
            "snapshots_dir": str(args.snapshots_dir.resolve()),
            "referencia_sha256": sha_referencia,
        }
    )
    almacen.verificar_diario()
    print(f"Corrida {almacen.corrida}, modo {modo}, {len(elegidas)} tareas.")

    medidas: list[dict[str, Any]] = []
    for i, tarea in enumerate(elegidas, start=1):
        t = medir_tarea(tarea, verificador, almacen, reloj)
        medidas.append(t)
        print(f"[{i}/{len(elegidas)}] {t['instance_id']}: {t['clase']}")
    print(resumen_texto(medidas))

    if referencia is not None:
        comparacion = _comparar_muestra(referencia, medidas)
        escribir_sin_sobrescribir(args.comparacion, a_json(comparacion))
        if not comparacion["coincide"]:
            print("HALLAZGO: alguna clase de la muestra difiere de la referencia.", file=sys.stderr)
            return EXIT_FINDING
        return EXIT_OK
    if args.task_ids:
        print("Medicion parcial: no se escribe registro.")
        return EXIT_OK

    registro = construir_registro(
        medidas,
        sha256_tasks=sha_tasks,
        entorno_sha256=entorno_sha,
        fecha=reloj().astimezone(UTC).date().isoformat(),
        diario_sha256=almacen.diario_sha256(),
    )
    problemas = validar_registro(registro)
    if problemas:
        raise RuntimeError("El registro propio no pasa la validacion: " + "; ".join(problemas))
    escribir_sin_sobrescribir(args.salida, a_json(registro))
    saltan = guarda(medidas)
    for s in saltan:
        print(
            f"GUARDA: {s['repo']}: {s['no_discrimina']} de {s['tareas']} tareas no discriminan "
            "(mas de la mitad): el entorno de ese repositorio no esta arreglado (A.3).",
            file=sys.stderr,
        )
    return EXIT_FINDING if saltan else EXIT_OK


def main(
    argv: Sequence[str] | None = None,
    *,
    verificador: Verificador | None = None,
    reloj: Reloj | None = None,
    faltan_snapshots: Callable[[Sequence[Tarea]], int] | None = None,
) -> int:
    """Punto de entrada. ``verificador``, ``reloj`` y ``faltan_snapshots`` se inyectan en las pruebas."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")
    args = _parser().parse_args(argv)
    try:
        return ejecutar(args, verificador, reloj or (lambda: datetime.now(UTC)), faltan_snapshots)
    except (ValidezError, kaggle_replicas.ReplicasError, kaggle_split.ParticionError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_INVALID
    except Exception as exc:
        # solo el tipo y el punto del guion: el texto de la excepcion puede traer datos de las tareas
        marco = traceback.extract_tb(exc.__traceback__)[-1] if exc.__traceback__ else None
        punto = f"{Path(marco.filename).name}:{marco.lineno} ({marco.name})" if marco else "?"
        print(f"ERROR INESPERADO ({type(exc).__name__}) en {punto}", file=sys.stderr)
        return EXIT_UNEXPECTED


if __name__ == "__main__":
    sys.exit(main())
