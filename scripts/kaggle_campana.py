"""Reglas ya fijadas de la campana A/B/C/D (issue #104) y la comprobacion de fuga.

No corre el modelo, no lee tasks.jsonl y no rellena los parametros abiertos. Esos siguen
en null hasta que la linea base (#103) tenga un reporte de replicas con salida 0.

* ``comprobar`` sale con 1 mientras falte un abierto, con 2 si el archivo contradice
  este modulo, y con 0 solo cuando los tres abiertos tienen valor.
* ``fuga`` busca instance_id de prueba dentro de episodios o skills. Salida 2 si hay
  alguno. Es la comprobacion automatica que el pre-registro exige antes de la campana.
* ``desenlace`` aplica la regla de las tres lecturas sobre conteos ya resumidos.

El documento es ``docs/preregistration/kaggle-campaign-abcd.md``.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable, Sequence
from fractions import Fraction
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "kaggle-campaign-prereg/1"
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PARAMS = REPO_ROOT / "experiments/gemma_developer_agent/preregistro/campana_abcd.json"

EXIT_OK = 0
EXIT_OPEN = 1
EXIT_INVALID = 2
EXIT_UNEXPECTED = 3

INSTRUCCION_D = (
    "Before you apply any skill, locate the code with the graph tools. "
    "Take a symbol that appears in the failing test name or in the traceback and call "
    "get_code_neighbors, search_similar_code, or get_code_subgraph on that symbol. "
    "Read the tool result. Only then follow a skill."
)
FRASE_PLACEBO = "Este párrafo no indica ningún cambio de código."
HERRAMIENTAS_GRAFO = ("get_code_neighbors", "search_similar_code", "get_code_subgraph")
ABIERTOS = ("variacion_a", "subconjunto", "corridas_por_condicion")

_SKIP_DIRS = {".git", "__pycache__", ".venv", "node_modules"}


class CampanaError(Exception):
    """El archivo o los argumentos no cumplen la regla fijada."""


def resuelve_mayoria_estricta(corridas: Sequence[bool]) -> bool:
    """Una tarea queda resuelta si hay mas corridas resueltas que no resueltas.

    Con una corrida, manda esa. Con dos, hacen falta las dos. Un empate no resuelve.
    """

    if not corridas:
        raise CampanaError("mayoria estricta: la tarea no tiene corridas.")
    return sum(corridas) * 2 > len(corridas)


def supera_umbral(diferencia: int, n: int, m_star: Fraction) -> bool:
    """True si ``diferencia / n`` es mayor que ``m_star``. La igualdad no supera."""

    if n <= 0:
        raise CampanaError("el denominador de la tasa tiene que ser positivo.")
    if m_star < 0:
        raise CampanaError("M* no es negativo.")
    return Fraction(diferencia, n) > m_star


def desenlace(diferencia: int, n: int, m_star: Fraction) -> str:
    """``apoyada``, ``sin_diferencia`` o ``refutada``.

    ``diferencia`` es resueltas de la primera condicion menos resueltas de la segunda,
    sobre las mismas ``n`` tareas. Los tres nombres cubren todos los enteros: la
    igualdad con ``M*`` cae en ``sin_diferencia``.
    """

    if supera_umbral(diferencia, n, m_star):
        return "apoyada"
    if supera_umbral(-diferencia, n, m_star):
        return "refutada"
    return "sin_diferencia"


def ids_senuelo(test_ids: Sequence[str], paso: int = 5) -> list[str]:
    """Uno de cada ``paso`` identificadores, en orden lexicografico, empezando por el primero."""

    if paso < 1:
        raise CampanaError("el paso de los senuelos es un entero mayor que cero.")
    return sorted(test_ids)[::paso]


def texto_placebo(longitud: int, frase: str = FRASE_PLACEBO) -> str:
    """Texto de exactamente ``longitud`` caracteres. No nombra las herramientas de grafo."""

    if longitud < 0:
        raise CampanaError("la longitud del placebo no es negativa.")
    if not frase:
        raise CampanaError("la frase del placebo esta vacia.")
    if any(nombre in frase for nombre in HERRAMIENTAS_GRAFO):
        raise CampanaError("la frase del placebo nombra una herramienta de grafo.")
    repeticiones = longitud // len(frase)
    resto = longitud % len(frase)
    return frase * repeticiones + (" " * resto)


def load_params(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CampanaError(f"no pude leer {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise CampanaError(f"{path} no es un objeto JSON.")
    return data


def validar_fijos(data: dict[str, Any]) -> None:
    if data.get("schema_version") != SCHEMA_VERSION:
        raise CampanaError(f"schema_version distinto de {SCHEMA_VERSION}.")
    fijos = data.get("fijos")
    if not isinstance(fijos, dict):
        raise CampanaError("falta el bloque fijos.")
    if fijos.get("particion") != "leave_one_repo_out":
        raise CampanaError("la particion fijada es leave_one_repo_out.")
    if fijos.get("estimador") != "mayoria_estricta":
        raise CampanaError("el estimador fijado es mayoria_estricta.")
    if fijos.get("instruccion_d") != INSTRUCCION_D:
        raise CampanaError("instruccion_d no coincide con el texto de este modulo.")
    if any(nombre not in INSTRUCCION_D for nombre in HERRAMIENTAS_GRAFO):
        raise CampanaError("la instruccion de D no nombra las tres herramientas de grafo.")
    if fijos.get("frase_placebo") != FRASE_PLACEBO:
        raise CampanaError("frase_placebo no coincide con el texto de este modulo.")
    if fijos.get("prediccion") != "H(C, A) no queda apoyada":
        raise CampanaError("la prediccion fijada es una: H(C, A) no queda apoyada.")
    if fijos.get("exitos_independientes") != 3:
        raise CampanaError("hacen falta tres exitos independientes.")
    abiertos = data.get("abiertos")
    if not isinstance(abiertos, dict) or any(nombre not in abiertos for nombre in ABIERTOS):
        raise CampanaError("faltan abiertos: variacion_a, subconjunto, corridas_por_condicion.")


def abiertos_pendientes(data: dict[str, Any]) -> list[str]:
    pendientes = []
    for nombre in ABIERTOS:
        entrada = data["abiertos"][nombre]
        if not isinstance(entrada, dict) or "valor" not in entrada:
            raise CampanaError(f"el abierto {nombre} no tiene valor.")
        if entrada["valor"] is None:
            pendientes.append(nombre)
    return pendientes


def test_ids_de_subconjunto(data: dict[str, Any]) -> list[str]:
    crudos = data.get("test")
    if (
        not isinstance(crudos, list)
        or not crudos
        or not all(isinstance(item, str) and item for item in crudos)
    ):
        raise CampanaError("el subconjunto necesita una lista 'test' de instance_id no vacios.")
    if len(set(crudos)) != len(crudos):
        raise CampanaError("hay instance_id de prueba repetidos.")
    train = data.get("train")
    if isinstance(train, list):
        comunes = sorted(set(crudos) & set(train))
        if comunes:
            raise CampanaError(f"un instance_id esta en train y en test: {comunes[0]}")
    return list(crudos)


def buscar_fuga(test_ids: Iterable[str], raices: Sequence[Path]) -> list[tuple[str, str]]:
    """Pares (instance_id, ruta) de cada identificador de prueba hallado en un archivo."""

    ids = tuple(test_ids)
    if not ids:
        raise CampanaError("no hay instance_id de prueba que buscar.")
    hallados: list[tuple[str, str]] = []
    for raiz in raices:
        if not raiz.exists():
            raise CampanaError(f"no existe {raiz}.")
        archivos = [raiz] if raiz.is_file() else sorted(path for path in raiz.rglob("*") if path.is_file())
        for path in archivos:
            if any(parte in _SKIP_DIRS for parte in path.parts):
                continue
            try:
                texto = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                continue
            hallados.extend((iid, path.as_posix()) for iid in ids if iid in texto)
    return hallados


def _cmd_comprobar(args: argparse.Namespace) -> int:
    data = load_params(args.parametros)
    validar_fijos(data)
    pendientes = abiertos_pendientes(data)
    if pendientes:
        print("abiertos: " + ", ".join(pendientes))
        print("la campana de prueba no empieza")
        return EXIT_OPEN
    print("parametros de la campana cerrados")
    return EXIT_OK


def _cmd_fuga(args: argparse.Namespace) -> int:
    subconjunto = load_params(args.subconjunto)
    ids = test_ids_de_subconjunto(subconjunto)
    hallados = buscar_fuga(ids, [Path(ruta) for ruta in args.raiz])
    if hallados:
        for iid, ruta in hallados:
            print(f"{iid}\t{ruta}")
        return EXIT_INVALID
    print(f"sin fuga: {len(ids)} instance_id de prueba")
    return EXIT_OK


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pre-registro de la campana A/B/C/D (#104).")
    sub = parser.add_subparsers(dest="comando", required=True)

    comprobar = sub.add_parser("comprobar")
    comprobar.add_argument("--parametros", type=Path, default=DEFAULT_PARAMS)
    comprobar.set_defaults(func=_cmd_comprobar)

    fuga = sub.add_parser("fuga")
    fuga.add_argument("--subconjunto", type=Path, required=True)
    fuga.add_argument("--raiz", type=Path, action="append", required=True)
    fuga.set_defaults(func=_cmd_fuga)

    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except CampanaError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_INVALID


if __name__ == "__main__":
    raise SystemExit(main())
