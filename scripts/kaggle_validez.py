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

Frontera de fuga (A, «Frontera de fuga»). El registro versionable lleva solo ``instance_id``,
repositorio, clase, codigos de salida, conteos, duraciones y fechas UTC; del error del arnes guarda
una categoria de una lista cerrada, nunca su texto. Nunca lleva nombres de pruebas, logs,
enunciados, parches ni el hash del parche de referencia. Las salidas crudas van a ``--crudo``, que
debe estar fuera de un repositorio git o ser una ruta ignorada por git.

Reanudable: cada ejecucion se guarda en ``--crudo`` al terminar, sin sobrescribir; al reanudar se
leen, se recalcula su registro y una discrepancia es salida 2.

Codigos de salida (no se solapan):

* 0  medicion completa y sin hallazgo (en modo muestra: todas las clases coinciden; en una
  medicion parcial con ``--task-ids``: terminada, sin registro).
* 1  medicion completa con hallazgo: la guarda de A.3 salta en algun repositorio (el registro se
  escribe igual, para conservarlo) o, en modo muestra, alguna clase difiere.
* 2  no se pudo medir o validar: entrada invalida, entorno que no coincide, ``swegemma`` ausente,
  fallo del verificador, error del arnes sin categoria, archivo que se sobrescribiria, ruta cruda
  versionada, discrepancia con lo guardado. «No pude medir» nunca equivale a una clase.
* 3  error inesperado del propio script.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib
import importlib.metadata
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import time
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
CLAVES_TAREA = (
    "instance_id",
    "repo",
    "clase",
    "sin_parche_segundos",
    "dorado_segundos",
    "ejecuciones",
)
UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
ID_SEGURO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,200}$")
NOMBRE_VERSION = re.compile(r"_v([0-9]+)\.json$")
RESUMEN_PRUEBAS = re.compile(r"\b([0-9]+) (passed|failed|errors?)\b")


class ValidezError(ValueError):
    """Entrada o estado que no permite una medicion fiable (se informa con salida 2)."""


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
    codigo -1 se leeria como «parche vacio» en vez de como pruebas que no se pudieron ejecutar.
    Un error del arnes fuera de la lista cerrada lanza ``ValidezError`` **sin** su texto.
    """
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
        raise ValidezError(
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

    Si no se puede comprobar (git ausente, error de git) lanza ``ValidezError``: «no pude
    comprobar» no es «esta ignorada».
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

    def _ruta(self, tarea: Tarea, verificacion: str, numero: int, intento: int) -> Path:
        if not ID_SEGURO.fullmatch(tarea.instance_id):
            raise ValidezError("Un instance_id no es seguro como nombre de archivo.")
        return self.raiz / "ejecuciones" / tarea.instance_id / f"{verificacion}_{numero}_{intento}.json"

    def existe(self, tarea: Tarea, verificacion: str, numero: int, intento: int) -> bool:
        return self._ruta(tarea, verificacion, numero, intento).is_file()

    def leer(self, tarea: Tarea, verificacion: str, numero: int, intento: int) -> dict[str, Any] | None:
        """Registro guardado de una ejecucion, o ``None`` si no se ha corrido.

        Recalcula el registro desde el resultado crudo guardado y exige que coincida con el
        guardado: una discrepancia es ``ValidezError`` (no se puede elegir cual vale).
        """
        ruta = self._ruta(tarea, verificacion, numero, intento)
        if not ruta.is_file():
            return None
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
        escribir_sin_sobrescribir(ruta, a_json({"resultado": crudo, "registro": registro}))

    def comprobar_manifiesto(self, manifiesto: dict[str, Any]) -> None:
        """Crea el manifiesto del entorno o exige que coincida con el de la medicion anterior."""
        ruta = self.raiz / "manifiesto.json"
        nuevo = {"schema_version": SCHEMA_MANIFIESTO, **manifiesto}
        if not ruta.is_file():
            escribir_sin_sobrescribir(ruta, a_json(nuevo))
            return
        try:
            previo = kaggle_replicas.loads_strict(ruta.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise ValidezError("manifiesto.json de --crudo ilegible.") from None
        if previo != nuevo:
            raise ValidezError(
                "--crudo pertenece a una medicion con otro entorno, otro tasks.jsonl u otra declaracion: "
                "no se mezclan ejecuciones de entornos distintos."
            )


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
            try:
                res = validar_resultado(verificador(tarea, verificacion))
            except ValidezError:
                raise
            except Exception as exc:
                raise ValidezError(
                    f"El verificador fallo ({type(exc).__name__}) en {verificacion} {numero}: no se registra "
                    "nada y se puede reanudar."
                ) from None
            fecha = reloj().astimezone(UTC).strftime(UTC_FORMAT)
            reg = registro_de_ejecucion(res, verificacion, numero, intento, fecha)
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
    return {
        "instance_id": tarea.instance_id,
        "repo": tarea.repo,
        "clase": clasificar(finales[VERIF_SIN], finales[VERIF_DORADO]),
        "sin_parche_segundos": [e["duracion_segundos"] for e in finales[VERIF_SIN]],
        "dorado_segundos": [e["duracion_segundos"] for e in finales[VERIF_DORADO]],
        "ejecuciones": todas,
    }


# ---------------------------------------------------------------------------
# Registro final y su validacion contra la compuerta
# ---------------------------------------------------------------------------


def construir_registro(
    tareas: Sequence[dict[str, Any]], *, sha256_tasks: str, entorno_sha256: str, fecha: str
) -> dict[str, Any]:
    """Registro ``kaggle-task-validity/1``: exactamente las claves que exige la compuerta.

    ``tareas_invalidas`` es la lista que lee ``kaggle_split.py --calibracion``: toda tarea cuya clase
    no es ``discrimina``.
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
    }


def validar_registro(obj: object) -> list[str]:
    """Problemas del registro contra el esquema de ``kaggle_prereg`` y las claves propias.

    Lista vacia = el registro pasa la validacion que hace la compuerta al cerrar ``validez_tareas``
    (sin el cruce con ``tasks.jsonl``, que lo hace ``comprobar --tasks``).
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
        for e in t["ejecuciones"]:
            if (
                not isinstance(e, dict)
                or set(e) != set(CLAVES_EJECUCION)
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
    try:
        filas = kaggle_split._read_tasks(ruta)
    except (OSError, kaggle_split.ParticionError) as exc:
        raise ValidezError(f"No se pudo leer tasks.jsonl: {exc}") from None
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


def leer_referencia(ruta: Path) -> dict[str, Any]:
    """Registro de validez anterior (para el modo muestra), validado."""
    try:
        obj = kaggle_prereg.loads_strict(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ValidezError(f"No se pudo leer el registro de referencia {ruta}.") from None
    problemas = validar_registro(obj)
    if problemas:
        raise ValidezError("El registro de referencia no es valido: " + "; ".join(problemas))
    assert isinstance(obj, dict)
    return obj


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


def construir_verificador_swegemma(
    *,
    tasks_path: Path,
    snapshots_dir: Path,
    crudo: Path,
    imagen: str,
    sandbox: str,
    version_arnes: str,
) -> Verificador:
    """Verificador sobre ``swegemma.harness.verification.verify_task`` (importacion perezosa).

    Llama a ``verify_task(docker, config, task, snapshot_path, base_snapshot_path=..., patch_path=...,
    agent_patch=<'' o parche de referencia>, start_time=time.perf_counter())``, que es la misma
    funcion que usa ``swegemma eval`` en su fase 2. El parche de referencia se lee de la tarea
    dentro de esta funcion y no sale de ella. Sin el paquete, o con otra version que la declarada,
    lanza ``ValidezError``.
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
    config = config_mod.EvalConfig(
        tasks_path=tasks_path,
        snapshots_dir=snapshots_dir,
        results_dir=crudo / "arnes",
        submission_dir=crudo / "arnes_envio",
        models=adk_mod.ModelRegistry(),
        image=imagen,
        sandbox=sandbox,
        skip_agent_patch=True,
        display_mode="quiet",
    )
    evaluator = eval_mod.Evaluator(config)
    tareas = {
        t.instance_id: evaluator._hydrate_task_from_secret(t) for t in models_mod.load_tasks(tasks_path)
    }

    def verificar(tarea: Tarea, verificacion: str) -> ResultadoVerificacion:
        task = tareas.get(tarea.instance_id)
        if task is None:
            raise ValidezError("Una tarea medida no esta en tasks.jsonl del arnes.")
        parche = ""
        if verificacion == VERIF_DORADO:
            parche = str(task.patch or "")
            if not parche.strip():
                raise ValidezError("Una tarea no tiene parche de referencia: no se puede verificar.")
        inicio = time.perf_counter()
        snap, base, parche_ruta = dedup_mod.resolve_task_snapshot_paths(
            snapshots_dir, task.instance_id, task.repo
        )
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

    return verificar


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
    version = NOMBRE_VERSION.search(ruta.name)
    if version and int(version.group(1)) > 2:
        raise ValidezError("A.3: no hay una tercera medicion (_v3); la decision es del dueno.")


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


def ejecutar(args: argparse.Namespace, verificador: Verificador | None, reloj: Reloj) -> int:
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
    if args.params is not None:
        try:
            esperado = kaggle_prereg.load_params(args.params)["fijos"]["tasks_sha256"]
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

    todas = leer_tareas(args.tasks)
    referencia = leer_referencia(args.muestra_desde) if muestra else None
    if referencia is not None and referencia["sha256_tasks"] != sha_tasks:
        raise ValidezError("El registro de referencia es de otro tasks.jsonl.")
    elegidas = elegir_tareas(todas, args.task_ids, referencia)

    if verificador is None:
        verificador = construir_verificador_swegemma(
            tasks_path=args.tasks,
            snapshots_dir=args.snapshots_dir,
            crudo=args.crudo,
            imagen=args.imagen,
            sandbox=args.sandbox,
            version_arnes=entorno["version_arnes"],
        )
    almacen = Almacen(args.crudo)
    almacen.raiz.mkdir(parents=True, exist_ok=True)
    almacen.comprobar_manifiesto(
        {
            "sha256_tasks": sha_tasks,
            "entorno_sha256": entorno_sha,
            "imagen": args.imagen,
            "sandbox": args.sandbox,
            "version_arnes": entorno["version_arnes"],
        }
    )

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
) -> int:
    """Punto de entrada. ``verificador`` y ``reloj`` se inyectan en las pruebas."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")
    args = _parser().parse_args(argv)
    try:
        return ejecutar(args, verificador, reloj or (lambda: datetime.now(UTC)))
    except (ValidezError, kaggle_replicas.ReplicasError, kaggle_split.ParticionError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_INVALID
    except Exception as exc:
        print(f"ERROR INESPERADO ({type(exc).__name__}): {exc}", file=sys.stderr)
        return EXIT_UNEXPECTED


if __name__ == "__main__":
    sys.exit(main())
