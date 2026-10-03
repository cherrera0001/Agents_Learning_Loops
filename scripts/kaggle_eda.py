"""Descripcion agregada de ``tasks.jsonl`` (issue #103, experimento Kaggle Gemma 4).

Dos subcomandos, solo biblioteca estandar:

* ``resumen``: conteos y cuantiles de las tareas (campos, fechas, longitud del enunciado, lineas
  cambiadas y archivos del parche de referencia y del parche de pruebas) y los cortes de los terciles
  que fija el pre-registro.
* ``terciles``: tasa de resolucion por replica en cada tercil de tamano del parche de referencia y de
  longitud del enunciado, a partir de los recibos. Es el analisis descriptivo declarado en el
  pre-registro.

Frontera. El script lee enunciados y parches solo para medir su tamano, y nunca escribe ni imprime un
enunciado, un parche, una prueba ni un ``instance_id``. Lo que imprime son conteos y cuantiles de
grupos de al menos ``MIN_GRUPO`` tareas:

* de un grupo con menos de ``MIN_GRUPO`` tareas solo se da cuantas son, sin ningun estadistico;
* no se dan minimos ni maximos, que son el valor de una tarea concreta: se dan los percentiles 10,
  25, 50, 75 y 90 y, para los extremos, conteos por umbral.

Un cuantil sigue siendo un numero derivado de los datos de la competencia; lo que la regla evita es
publicar el valor de una tarea identificable. Los estadisticos del parche de referencia son del
evaluador: no entran en prompts ni en skills.

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
MEDIDAS = (
    "enunciado_caracteres",
    "parche_lineas",
    "parche_pruebas_lineas",
    "parche_lineas_totales",
    "parche_archivos",
    "parche_pruebas_archivos",
)
MEDIDAS_TERCILES = ("parche_lineas", "enunciado_caracteres")
# Campos que, si existieran, darian la lista de pruebas que deben fallar o pasar sin tener que medirla.
CAMPOS_LISTA_PRUEBAS = ("FAIL_TO_PASS", "PASS_TO_PASS", "fail_to_pass", "pass_to_pass")
MIN_GRUPO = 5
# Conteos por umbral: (nombre, medida, operador, valor). Sustituyen a los minimos y maximos.
UMBRALES: tuple[tuple[str, str, str, int], ...] = (
    ("parches_de_hasta_10_lineas", "parche_lineas", "<=", 10),
    ("parches_de_mas_de_100_lineas", "parche_lineas", ">", 100),
    ("parches_de_mas_de_1000_lineas", "parche_lineas", ">", 1000),
    ("parches_de_un_solo_archivo", "parche_archivos", "<=", 1),
    ("parches_de_mas_de_10_archivos", "parche_archivos", ">", 10),
    ("enunciados_de_hasta_100_caracteres", "enunciado_caracteres", "<=", 100),
    ("enunciados_de_mas_de_5000_caracteres", "enunciado_caracteres", ">", 5000),
)
UNIDADES = {
    "enunciado_caracteres": "caracteres Unicode de problem_statement (no bytes ni tokens)",
    "parche_lineas": "lineas anadidas mas quitadas dentro de los bloques @@ del parche de referencia",
    "parche_pruebas_lineas": "lo mismo que parche_lineas, sobre el parche de pruebas",
    "parche_lineas_totales": "todas las lineas del diff de referencia, con cabeceras y contexto",
    "parche_archivos": "cabeceras de archivo (--- seguida de +++) del parche de referencia",
    "parche_pruebas_archivos": "cabeceras de archivo (--- seguida de +++) del parche de pruebas",
    "cuantiles": "statistics.quantiles(n=20, method='inclusive'): percentiles 10, 25, 50, 75 y 90",
    "supresion": f"sin estadisticos en grupos de menos de {MIN_GRUPO} tareas; sin minimos ni maximos",
}
HUNK_RE = re.compile(r"^@@ -\d+(?:,(\d+))? \+\d+(?:,(\d+))? @@")


class EdaError(ValueError):
    """Entrada invalida para la descripcion de las tareas."""


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
    """Medidas de tamano de una tarea, con su unidad en el nombre (ver ``UNIDADES``)."""
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
    if len(valores) < MIN_GRUPO:
        raise EdaError(f"Hacen falta al menos {MIN_GRUPO} valores para calcular terciles.")
    orden = sorted(valores)
    n = len(orden)
    return [orden[math.ceil(n / 3) - 1], orden[math.ceil(2 * n / 3) - 1]]


def tercile_of(valor: int, cortes: Sequence[int]) -> int:
    """Tercil 1 si ``valor <= a``; 2 si ``a < valor <= b``; 3 si ``valor > b``."""
    a, b = cortes
    return 1 if valor <= a else (2 if valor <= b else 3)


def quantiles(valores: Sequence[int]) -> dict[str, float] | None:
    """Percentiles 10, 25, 50, 75 y 90; ``None`` si el grupo tiene menos de ``MIN_GRUPO`` valores.

    Nunca devuelve el minimo ni el maximo: con ``MIN_GRUPO`` valores o mas y el metodo inclusivo, los
    percentiles 10 y 90 interpolan entre valores vecinos.
    """
    if len(valores) < MIN_GRUPO:
        return None
    q = statistics.quantiles(sorted(valores), n=20, method="inclusive")
    return {"p10": q[1], "p25": q[4], "mediana": q[9], "p75": q[14], "p90": q[17]}


def group_summary(medidas: Sequence[dict[str, int]]) -> dict[str, Any]:
    """Tamano de un grupo y, solo si tiene ``MIN_GRUPO`` tareas o mas, sus cuantiles por medida."""
    if len(medidas) < MIN_GRUPO:
        return {"tareas": len(medidas), "estadisticos": None}
    return {"tareas": len(medidas), "estadisticos": {k: quantiles([m[k] for m in medidas]) for k in MEDIDAS}}


def _cumple(valor: int, operador: str, umbral: int) -> bool:
    return valor <= umbral if operador == "<=" else valor > umbral


def _trimestre(fecha: str) -> str:
    return f"{fecha[:4]}-T{(int(fecha[5:7]) - 1) // 3 + 1}"


def summarize(tareas: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Agregados de las tareas: conteos y cuantiles de grupos de ``MIN_GRUPO`` tareas o mas.

    La salida no contiene identificadores, texto, minimos ni maximos. Un conteo por trimestre o por
    umbral puede ser pequeno; dice cuantas tareas hay, no cual ni cuanto mide.
    """
    med = [measures(t) for t in tareas]
    por_repo: dict[str, dict[str, Any]] = {}
    for repo in sorted({t["repo"] for t in tareas}):
        suyas = [(t, m) for t, m in zip(tareas, med, strict=True) if t["repo"] == repo]
        por_repo[repo] = group_summary([m for _, m in suyas])
        anios = Counter(t["created_at"][:4] for t, _ in suyas)
        por_repo[repo]["por_anio"] = dict(sorted(anios.items())) if len(suyas) >= MIN_GRUPO else None
    trimestres = Counter(_trimestre(t["created_at"]) for t in tareas)
    return {
        "tareas": len(tareas),
        "campos": sorted({k for t in tareas for k in t}),
        "hints_text_vacio": sum(1 for t in tareas if not str(t.get("hints_text") or "").strip()),
        "con_lista_de_pruebas": sum(1 for t in tareas if any(c in t for c in CAMPOS_LISTA_PRUEBAS)),
        "base_commit_distintos": len({t["base_commit"] for t in tareas}),
        "por_repositorio": por_repo,
        "global": group_summary(med),
        "conteos_por_umbral": {
            nombre: sum(1 for m in med if _cumple(m[medida], op, umbral))
            for nombre, medida, op, umbral in UMBRALES
        },
        "por_trimestre": dict(sorted(trimestres.items())),
        "desde_2025_T4": sum(n for q, n in trimestres.items() if q >= "2025-T4"),
        "terciles": (
            {k: tercile_cuts([m[k] for m in med]) for k in MEDIDAS_TERCILES}
            if len(med) >= MIN_GRUPO
            else None
        ),
        "unidades": UNIDADES,
    }


def rates_by_tercile(
    tareas: Sequence[dict[str, Any]],
    recibos: Sequence[kaggle_replicas.Recibo],
    cortes: dict[str, Sequence[int]],
) -> dict[str, Any]:
    """Resueltas / tareas con recibo, por replica y por tercil de cada medida.

    Una celda con menos de ``MIN_GRUPO`` tareas da su tamano y ``resueltas: null``.
    """
    medidas = {t["instance_id"]: measures(t) for t in tareas}
    ajenas = sorted({r.instance_id for r in recibos} - set(medidas))
    if ajenas:
        raise EdaError(f"Hay {len(ajenas)} recibos de tareas que no estan en tasks.jsonl.")
    out: dict[str, Any] = {}
    for medida, c in cortes.items():
        if medida not in MEDIDAS_TERCILES or len(c) != 2 or c[0] > c[1]:
            raise EdaError(f"Cortes invalidos para {medida!r}: {list(c)}.")
        filas: dict[str, dict[str, dict[str, Any]]] = {}
        for r in sorted(recibos, key=lambda x: (x.replica, x.instance_id)):
            celda = filas.setdefault(
                str(r.replica), {str(i): {"resueltas": 0, "tareas": 0} for i in (1, 2, 3)}
            )
            tercil = celda[str(tercile_of(medidas[r.instance_id][medida], c))]
            tercil["tareas"] += 1
            tercil["resueltas"] += 1 if r.status == kaggle_replicas.ST_RESOLVED else 0
        for celda in filas.values():
            for tercil in celda.values():
                if tercil["tareas"] < MIN_GRUPO:
                    tercil["resueltas"] = None
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
