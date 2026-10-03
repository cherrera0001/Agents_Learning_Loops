"""Descripcion agregada de ``tasks.jsonl`` (issue #103, experimento Kaggle Gemma 4).

Dos subcomandos, solo biblioteca estandar:

* ``resumen``: conteos y estadisticos agregados de las tareas (campos, fechas, longitud del
  enunciado, lineas cambiadas del parche de referencia y del parche de pruebas) y los cortes de los
  terciles que fija el pre-registro.
* ``terciles``: tasa de resolucion por replica en cada tercil de tamano del parche de referencia y de
  longitud del enunciado, a partir de los recibos. Es el analisis descriptivo declarado en el
  pre-registro.

Frontera: el script lee enunciados y parches solo para medir su tamano. Nunca escribe ni imprime un
enunciado, un parche, una prueba ni un dato por tarea: la salida son agregados (conteos, medianas,
cuartiles, extremos) y, en ``terciles``, numeradores y denominadores por grupo. Los estadisticos del
parche de referencia son del evaluador: no entran en prompts ni en skills.

Salida: 0 bien; 2 entrada invalida; 3 error inesperado del script.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts import kaggle_replicas

EXIT_OK, EXIT_INVALID, EXIT_UNEXPECTED = 0, 2, 3
CAMPOS_TEXTO = (
    "instance_id",
    "repo",
    "base_commit",
    "problem_statement",
    "patch",
    "test_patch",
    "created_at",
)
MEDIDAS = ("enunciado_caracteres", "parche_lineas", "parche_pruebas_lineas")
MEDIDAS_EXTRA = ("parche_lineas_totales", "parche_archivos", "parche_pruebas_archivos")
# Campos que, si existieran, darian la lista de pruebas que deben fallar o pasar sin tener que medirla.
CAMPOS_LISTA_PRUEBAS = ("FAIL_TO_PASS", "PASS_TO_PASS", "fail_to_pass", "pass_to_pass")
PARCHE_PEQUENO = 10


class EdaError(ValueError):
    """Entrada invalida para la descripcion de las tareas."""


HUNK_RE = re.compile(r"^@@ -\d+(?:,(\d+))? \+\d+(?:,(\d+))? @@")


@dataclass(frozen=True)
class DiffStats:
    """Medidas de un diff unificado.

    * ``archivos``: cabeceras de archivo, es decir, una linea ``--- `` seguida de una linea ``+++ ``
      fuera de un bloque. Los diffs de ``tasks.jsonl`` no traen la linea ``diff --git``: contar esa
      linea da 0 archivos en todas las tareas.
    * ``anadidas`` y ``quitadas``: lineas ``+`` y ``-`` **dentro de los bloques** ``@@``, contadas con
      las longitudes que declara cada cabecera ``@@``. Una linea de codigo quitada que empieza por
      ``--`` cuenta como quitada y no como cabecera.
    * ``cambiadas`` = ``anadidas + quitadas``. Es la medida que usa el pre-registro.
    * ``totales``: todas las lineas del texto del diff, con cabeceras y contexto. Es otra variable:
      siempre es mayor que ``cambiadas`` y depende de cuanto contexto trae el diff.
    """

    archivos: int
    anadidas: int
    quitadas: int
    totales: int

    @property
    def cambiadas(self) -> int:
        return self.anadidas + self.quitadas


def diff_stats(diff: str) -> DiffStats:
    """Recorre un diff unificado bloque a bloque; ver ``DiffStats``."""
    lineas = diff.splitlines()
    archivos = anadidas = quitadas = 0
    viejas = nuevas = 0  # lineas que le quedan al bloque en curso
    i = 0
    while i < len(lineas):
        linea = lineas[i]
        if viejas > 0 or nuevas > 0:
            if linea.startswith("+"):
                anadidas += 1
                nuevas -= 1
            elif linea.startswith("-"):
                quitadas += 1
                viejas -= 1
            elif not linea.startswith("\\"):  # contexto; «\ No newline at end of file» no cuenta
                viejas -= 1
                nuevas -= 1
        elif linea.startswith("--- ") and i + 1 < len(lineas) and lineas[i + 1].startswith("+++ "):
            archivos += 1
            i += 1
        else:
            m = HUNK_RE.match(linea)
            if m:
                viejas = int(m.group(1)) if m.group(1) is not None else 1
                nuevas = int(m.group(2)) if m.group(2) is not None else 1
        i += 1
    return DiffStats(archivos=archivos, anadidas=anadidas, quitadas=quitadas, totales=len(lineas))


def changed_lines(diff: str) -> int:
    """Lineas anadidas mas quitadas dentro de los bloques de un diff unificado (sin cabeceras ni contexto)."""
    return diff_stats(diff).cambiadas


def load_tasks(path: Path) -> list[dict[str, Any]]:
    """Lee ``tasks.jsonl``; exige los campos de texto y que los ``instance_id`` no se repitan."""
    try:
        lineas = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise EdaError(f"No se pudo leer {path}: {exc}") from exc
    tareas: list[dict[str, Any]] = []
    vistos: set[str] = set()
    for numero, linea in enumerate(lineas, start=1):
        if not linea.strip():
            continue
        try:
            obj = json.loads(linea)
        except ValueError as exc:
            raise EdaError(f"Linea {numero} de {path.name} no es JSON valido.") from exc
        if not isinstance(obj, dict) or not all(isinstance(obj.get(c), str) for c in CAMPOS_TEXTO):
            raise EdaError(f"Linea {numero} de {path.name}: faltan campos de texto {list(CAMPOS_TEXTO)}.")
        if obj["instance_id"] in vistos:
            raise EdaError(f"Linea {numero} de {path.name}: instance_id repetido.")
        vistos.add(obj["instance_id"])
        tareas.append(obj)
    if not tareas:
        raise EdaError(f"{path.name} no tiene tareas.")
    return tareas


def measures(tarea: dict[str, Any]) -> dict[str, int]:
    """Medidas de tamano de una tarea, con su unidad en el nombre.

    ``enunciado_caracteres`` son caracteres Unicode de ``problem_statement`` (``len`` de Python, no
    bytes ni tokens). ``*_lineas`` son lineas cambiadas (anadidas mas quitadas); ``*_lineas_totales``,
    todas las lineas del diff; ``*_archivos``, archivos que toca el diff.
    """
    parche, pruebas = diff_stats(tarea["patch"]), diff_stats(tarea["test_patch"])
    return {
        "enunciado_caracteres": len(tarea["problem_statement"]),
        "parche_lineas": parche.cambiadas,
        "parche_pruebas_lineas": pruebas.cambiadas,
        "parche_lineas_totales": parche.totales,
        "parche_archivos": parche.archivos,
        "parche_pruebas_archivos": pruebas.archivos,
    }


def tercile_cuts(valores: Sequence[int]) -> list[int]:
    """Cortes ``[a, b]``: el valor de rango ``ceil(n/3)`` y el de rango ``ceil(2n/3)``, ordenados."""
    if not valores:
        raise EdaError("No hay valores para calcular terciles.")
    orden = sorted(valores)
    n = len(orden)
    return [orden[math.ceil(n / 3) - 1], orden[math.ceil(2 * n / 3) - 1]]


def tercile_of(valor: int, cortes: Sequence[int]) -> int:
    """Tercil 1 si ``valor <= a``; 2 si ``a < valor <= b``; 3 si ``valor > b``."""
    a, b = cortes
    return 1 if valor <= a else (2 if valor <= b else 3)


def _trimestre(fecha: str) -> str:
    return f"{fecha[:4]}-T{(int(fecha[5:7]) - 1) // 3 + 1}"


def _cuantiles(valores: Sequence[int]) -> dict[str, float]:
    orden = sorted(valores)
    q = statistics.quantiles(orden, n=4, method="inclusive") if len(orden) > 1 else [orden[0]] * 3
    return {"min": orden[0], "p25": q[0], "mediana": statistics.median(orden), "p75": q[2], "max": orden[-1]}


def summarize(tareas: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Agregados de las tareas. Ningun valor de la salida identifica una tarea."""
    med = [measures(t) for t in tareas]
    repos = sorted({t["repo"] for t in tareas})
    por_repo: dict[str, Any] = {}
    for repo in repos:
        suyas = [m for t, m in zip(tareas, med, strict=True) if t["repo"] == repo]
        por_repo[repo] = {
            "tareas": len(suyas),
            **{f"mediana_{k}": statistics.median(m[k] for m in suyas) for k in MEDIDAS},
            "p25_enunciado_caracteres": _cuantiles([m["enunciado_caracteres"] for m in suyas])["p25"],
            "max_parche_lineas": max(m["parche_lineas"] for m in suyas),
        }
    trimestres = Counter(_trimestre(t["created_at"]) for t in tareas)
    return {
        "tareas": len(tareas),
        "campos": sorted({k for t in tareas for k in t}),
        "hints_text_vacio": sum(1 for t in tareas if not str(t.get("hints_text") or "").strip()),
        "con_lista_de_pruebas": sum(1 for t in tareas if any(c in t for c in CAMPOS_LISTA_PRUEBAS)),
        "base_commit_distintos": len({t["base_commit"] for t in tareas}),
        "por_repositorio": por_repo,
        "global": {k: _cuantiles([m[k] for m in med]) for k in (*MEDIDAS, *MEDIDAS_EXTRA)},
        "parches_de_un_solo_archivo": sum(1 for m in med if m["parche_archivos"] == 1),
        "unidades": {
            "enunciado_caracteres": "caracteres Unicode de problem_statement",
            "parche_lineas": "lineas anadidas mas quitadas dentro de los bloques @@ del parche de referencia",
            "parche_pruebas_lineas": "lo mismo que parche_lineas, sobre el parche de pruebas",
            "parche_lineas_totales": "todas las lineas del diff de referencia, con cabeceras y contexto",
            "parche_archivos": "cabeceras de archivo (--- seguida de +++) del parche de referencia",
            "parche_pruebas_archivos": "cabeceras de archivo (--- seguida de +++) del parche de pruebas",
            "cuantiles": "statistics.quantiles(n=4, method='inclusive'); mediana con statistics.median",
        },
        "parches_de_hasta_10_lineas": sum(1 for m in med if m["parche_lineas"] <= PARCHE_PEQUENO),
        "por_trimestre": dict(sorted(trimestres.items())),
        "desde_2025_T4": sum(n for q, n in trimestres.items() if q >= "2025-T4"),
        "terciles": {k: tercile_cuts([m[k] for m in med]) for k in ("parche_lineas", "enunciado_caracteres")},
    }


def rates_by_tercile(
    tareas: Sequence[dict[str, Any]],
    recibos: Sequence[kaggle_replicas.Recibo],
    cortes: dict[str, Sequence[int]],
) -> dict[str, Any]:
    """Resueltas / tareas con recibo, por replica y por tercil de cada medida. Solo agregados."""
    medidas = {t["instance_id"]: measures(t) for t in tareas}
    ajenas = sorted({r.instance_id for r in recibos} - set(medidas))
    if ajenas:
        raise EdaError(f"Hay {len(ajenas)} recibos de tareas que no estan en tasks.jsonl.")
    out: dict[str, Any] = {}
    for medida, c in cortes.items():
        if medida not in MEDIDAS or len(c) != 2 or c[0] > c[1]:
            raise EdaError(f"Cortes invalidos para {medida!r}: {list(c)}.")
        filas: dict[str, dict[str, dict[str, int]]] = {}
        for r in sorted(recibos, key=lambda x: (x.replica, x.instance_id)):
            celda = filas.setdefault(
                str(r.replica), {str(i): {"resueltas": 0, "tareas": 0} for i in (1, 2, 3)}
            )
            tercil = celda[str(tercile_of(medidas[r.instance_id][medida], c))]
            tercil["tareas"] += 1
            tercil["resueltas"] += 1 if r.status == kaggle_replicas.ST_RESOLVED else 0
        out[medida] = {"cortes": list(c), "por_replica": filas}
    return out


def _cmd_resumen(args: argparse.Namespace) -> int:
    print(json.dumps(summarize(load_tasks(args.tasks)), indent=2, sort_keys=True, ensure_ascii=False))
    return EXIT_OK


def _cmd_terciles(args: argparse.Namespace) -> int:
    try:
        parametros = json.loads(args.parametros.read_text(encoding="utf-8"))
        cortes = parametros["fijos"]["terciles"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise EdaError(f"No se pudieron leer los cortes de {args.parametros}: {exc}") from exc
    recibos = kaggle_replicas.load_receipts(args.recibos)
    tabla = rates_by_tercile(load_tasks(args.tasks), recibos, cortes)
    print(json.dumps(tabla, indent=2, sort_keys=True, ensure_ascii=False))
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada: ``resumen`` o ``terciles``."""
    parser = argparse.ArgumentParser(description="Descripcion agregada de tasks.jsonl (#103).")
    sub = parser.add_subparsers(dest="comando", required=True)
    r = sub.add_parser("resumen", help="Agregados de las tareas y cortes de los terciles.")
    r.add_argument("--tasks", type=Path, required=True)
    r.set_defaults(func=_cmd_resumen)
    t = sub.add_parser("terciles", help="Tasa por tercil de tamano, desde los recibos.")
    t.add_argument("--tasks", type=Path, required=True)
    t.add_argument("--recibos", type=Path, nargs="+", required=True)
    t.add_argument(
        "--parametros", type=Path, required=True, help="linea_base_a.json (cortes en fijos.terciles)."
    )
    t.set_defaults(func=_cmd_terciles)
    args = parser.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")
    try:
        return int(args.func(args))
    except (EdaError, kaggle_replicas.ReplicasError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_INVALID
    except Exception as exc:
        print(f"ERROR INESPERADO: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_UNEXPECTED


if __name__ == "__main__":
    sys.exit(main())
