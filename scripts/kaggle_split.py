"""Particion determinista estratificada por repositorio y fecha para Kaggle.

Separa las tareas publicas en conjunto de entrenamiento (antiguas) y conjunto
de prueba (recientes), preservando la proporcion por repositorio y excluyendo
las tareas no aptas para medicion (fase 2 sin parche / errores de control).

Solo utiliza la biblioteca estandar de Python.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

DEFAULT_CALIBRACION_PATH = (
    Path(__file__).resolve().parent.parent
    / "experiments/gemma_developer_agent/calibracion/fase2_sin_parche.json"
)
CLAVE_EXCLUSIONES = "tareas_invalidas"

ORIGEN_SIN_CALIBRACION = "sin_calibracion"
ORIGEN_CLAVE_PRESENTE = f"calibracion:{CLAVE_EXCLUSIONES}"
ORIGEN_CLAVE_AUSENTE = f"calibracion:sin_clave_{CLAVE_EXCLUSIONES}"


class ParticionError(ValueError):
    """Entrada invalida para la particion (tareas mal formadas, repo inexistente, etc.)."""


def compute_sha256(file_path: Path | str) -> str:
    """Calcula el hash SHA-256 de un archivo."""
    p = Path(file_path)
    if not p.is_file():
        raise FileNotFoundError(f"Archivo no encontrado: {p}")
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def load_exclusions(calibracion_path: Path | str | None) -> tuple[set[str], str]:
    """Carga los instance_id a excluir y declara de donde salieron.

    Distingue «no pude leer» de «no hay exclusiones»: un archivo inexistente,
    ilegible o con JSON invalido lanza ``FileNotFoundError``/``ParticionError``.
    Un JSON valido sin la clave ``tareas_invalidas`` (el caso del archivo
    versionado hoy) devuelve cero exclusiones con el origen
    ``calibracion:sin_clave_tareas_invalidas``, para que la salida lo declare.
    """
    if calibracion_path is None:
        return set(), ORIGEN_SIN_CALIBRACION
    p = Path(calibracion_path)
    if not p.is_file():
        raise FileNotFoundError(f"Archivo de calibracion no encontrado: {p}")
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        raise ParticionError(f"No se pudo leer la calibracion {p}: {exc}") from exc
    if not isinstance(data, dict):
        raise ParticionError(f"La calibracion {p} debe ser un objeto JSON.")
    if CLAVE_EXCLUSIONES not in data:
        return set(), ORIGEN_CLAVE_AUSENTE
    items = data[CLAVE_EXCLUSIONES]
    if not isinstance(items, list):
        raise ParticionError(f"'{CLAVE_EXCLUSIONES}' en {p} debe ser una lista.")
    ids: set[str] = set()
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("instance_id"), str):
            raise ParticionError(
                f"Cada elemento de '{CLAVE_EXCLUSIONES}' en {p} necesita un 'instance_id' de texto."
            )
        ids.add(item["instance_id"])
    return ids, ORIGEN_CLAVE_PRESENTE


def load_excluded_task_ids(calibracion_path: Path | str | None) -> set[str]:
    """Carga los instance_id a excluir desde el archivo de calibracion."""
    return load_exclusions(calibracion_path)[0]


def allocate_proportional_seats(counts: dict[str, int], total_seats: int) -> dict[str, int]:
    """Asigna vacantes proporcionalmente mediante el metodo de mayor residuo (Hamilton)."""
    total_items = sum(counts.values())
    if total_items == 0 or total_seats == 0:
        return {k: 0 for k in counts}
    if total_seats >= total_items:
        return dict(counts)

    # Cuota exacta y parte entera (Hare quota)
    quotas = {k: (c * total_seats) / total_items for k, c in counts.items()}
    seats = {k: math.floor(q) for k, q in quotas.items()}
    remainders = {k: quotas[k] - seats[k] for k, k_val in counts.items()}

    unassigned = total_seats - sum(seats.values())
    # Desempate determinista por residuo descendente y luego por nombre de clave
    sorted_rem = sorted(counts.keys(), key=lambda k: (-remainders[k], k))
    for k in sorted_rem[:unassigned]:
        seats[k] += 1

    return seats


def validate_tasks(tasks: Sequence[dict[str, Any]]) -> None:
    """Valida la entrada completa (incluidas las tareas luego excluidas).

    Exige al menos una tarea y, en cada una, ``instance_id``, ``repo`` y
    ``created_at`` como texto no vacio; los ``instance_id`` no se repiten.
    """
    if not tasks:
        raise ParticionError("No hay tareas de entrada.")
    seen: set[str] = set()
    for pos, t in enumerate(tasks):
        if not isinstance(t, dict):
            raise ParticionError(f"La tarea en la posicion {pos} no es un objeto.")
        for campo in ("instance_id", "repo", "created_at"):
            valor = t.get(campo)
            if not isinstance(valor, str) or not valor:
                raise ParticionError(f"La tarea en la posicion {pos} no tiene '{campo}' de texto no vacio.")
        iid = t["instance_id"]
        if iid in seen:
            raise ParticionError(f"instance_id duplicado: '{iid}'.")
        seen.add(iid)


def _apply_exclusions(
    tasks: Sequence[dict[str, Any]], excluded_ids: set[str]
) -> tuple[list[dict[str, Any]], set[str]]:
    """Devuelve las tareas validas y los ids de exclusion que si existian en la entrada."""
    present = {t["instance_id"] for t in tasks}
    valid = [t for t in tasks if t["instance_id"] not in excluded_ids]
    return valid, excluded_ids & present


def _group_by_repo(valid_tasks: Sequence[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Agrupa por repositorio y ordena cada grupo por (created_at, instance_id) ascendente."""
    by_repo: dict[str, list[dict[str, Any]]] = {}
    for t in valid_tasks:
        by_repo.setdefault(t["repo"], []).append(t)
    for repo_tasks in by_repo.values():
        repo_tasks.sort(key=lambda x: (x["created_at"], x["instance_id"]))
    return by_repo


def _exclusion_report(excluded_ids: set[str], applied: set[str]) -> dict[str, Any]:
    """Campos de `rule` que distinguen exclusiones pedidas y aplicadas."""
    return {
        "exclusiones_pedidas": len(excluded_ids),
        "exclusiones_aplicadas": len(applied),
        "excluded_instance_ids": sorted(excluded_ids),
        "excluded_ids_inexistentes": sorted(excluded_ids - applied),
    }


def split_tasks(
    tasks: Sequence[dict[str, Any]],
    n_test: int,
    excluded_ids: set[str] | None = None,
    sha256_tasks: str = "",
) -> dict[str, Any]:
    """Divide las tareas en entrenamiento y prueba de forma temporal y estratificada."""
    if excluded_ids is None:
        excluded_ids = set()
    if n_test < 0:
        raise ParticionError(f"n_test no puede ser negativo: {n_test}.")
    validate_tasks(tasks)

    valid_tasks, applied = _apply_exclusions(tasks, excluded_ids)
    if not valid_tasks:
        raise ParticionError("Todas las tareas quedaron excluidas.")
    by_repo = _group_by_repo(valid_tasks)

    # Asignacion estratificada por repositorio
    repo_counts = {repo: len(rtasks) for repo, rtasks in by_repo.items()}
    target_seats = min(n_test, len(valid_tasks))
    test_allocations = allocate_proportional_seats(repo_counts, target_seats)

    train_ids: list[str] = []
    test_ids: list[str] = []
    cutoffs_by_repo: dict[str, str | None] = {}
    repo_breakdown: dict[str, dict[str, int]] = {}

    # Claves ordenadas para determinismo absoluto
    for repo in sorted(by_repo.keys()):
        rtasks = by_repo[repo]
        k = test_allocations[repo]
        if k > 0:
            test_slice = rtasks[-k:]
            train_slice = rtasks[:-k]
            cutoff_date = test_slice[0]["created_at"]
        else:
            test_slice = []
            train_slice = rtasks
            cutoff_date = None

        cutoffs_by_repo[repo] = cutoff_date
        train_ids.extend(t["instance_id"] for t in train_slice)
        test_ids.extend(t["instance_id"] for t in test_slice)
        repo_breakdown[repo] = {
            "total_valid": len(rtasks),
            "train": len(train_slice),
            "test": len(test_slice),
        }

    return {
        "rule": {
            "name": "temporal_stratified_by_repo",
            "n_test_solicitado": n_test,
            "n_test_efectivo": len(test_ids),
            "n_train_efectivo": len(train_ids),
            "metodo_asignacion": "largest_remainder_hamilton",
            "descripcion": (
                "Particion temporal estratificada por repositorio: tareas "
                "antiguas para entrenamiento y recientes para prueba."
            ),
            **_exclusion_report(excluded_ids, applied),
        },
        "sha256_tasks": sha256_tasks,
        "cutoffs_by_repo": cutoffs_by_repo,
        "counts": {
            "total_tasks_recibidas": len(tasks),
            "total_excluidas": len(tasks) - len(valid_tasks),
            "total_validas": len(valid_tasks),
            "total_train": len(train_ids),
            "total_test": len(test_ids),
            "by_repo": repo_breakdown,
        },
        "train": train_ids,
        "test": test_ids,
    }


def split_leave_one_repo_out(
    tasks: Sequence[dict[str, Any]],
    held_out_repo: str,
    excluded_ids: set[str] | None = None,
    sha256_tasks: str = "",
) -> dict[str, Any]:
    """Divide las tareas dejando un repositorio completo como conjunto de prueba."""
    if excluded_ids is None:
        excluded_ids = set()
    validate_tasks(tasks)

    valid_tasks, applied = _apply_exclusions(tasks, excluded_ids)
    by_repo = _group_by_repo(valid_tasks)

    if held_out_repo not in by_repo:
        available = sorted(by_repo.keys())
        raise ParticionError(
            f"El repositorio '{held_out_repo}' no existe entre las tareas validas. "
            f"Repositorios disponibles: {available}"
        )

    train_ids: list[str] = []
    test_ids: list[str] = []
    repo_breakdown: dict[str, dict[str, int]] = {}

    for repo in sorted(by_repo.keys()):
        rtasks = by_repo[repo]
        ids = [t["instance_id"] for t in rtasks]
        if repo == held_out_repo:
            test_ids.extend(ids)
            repo_breakdown[repo] = {"total_valid": len(rtasks), "train": 0, "test": len(rtasks)}
        else:
            train_ids.extend(ids)
            repo_breakdown[repo] = {"total_valid": len(rtasks), "train": len(rtasks), "test": 0}

    return {
        "rule": {
            "name": "leave_one_repo_out",
            "held_out_repo": held_out_repo,
            "n_test_efectivo": len(test_ids),
            "n_train_efectivo": len(train_ids),
            "descripcion": (
                f"Particion leave-one-repo-out: todas las tareas de '{held_out_repo}' "
                "para prueba y las de los demas repositorios para entrenamiento."
            ),
            **_exclusion_report(excluded_ids, applied),
        },
        "sha256_tasks": sha256_tasks,
        "counts": {
            "total_tasks_recibidas": len(tasks),
            "total_excluidas": len(tasks) - len(valid_tasks),
            "total_validas": len(valid_tasks),
            "total_train": len(train_ids),
            "total_test": len(test_ids),
            "by_repo": repo_breakdown,
        },
        "train": train_ids,
        "test": test_ids,
    }


def _read_tasks(path: Path) -> list[dict[str, Any]]:
    """Lee tasks.jsonl; una linea que no sea JSON lanza ParticionError con su numero."""
    tasks: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for numero, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                tasks.append(json.loads(line))
            except ValueError as exc:
                raise ParticionError(f"Linea {numero} de {path} no es JSON valido: {exc}") from exc
    return tasks


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada de la CLI de particion."""
    parser = argparse.ArgumentParser(
        description="Genera la particion determinista y estratificada de tasks.jsonl."
    )
    parser.add_argument(
        "--tasks",
        type=Path,
        required=True,
        help="Ruta al archivo tasks.jsonl de Kaggle.",
    )
    parser.add_argument(
        "--calibracion",
        type=Path,
        default=DEFAULT_CALIBRACION_PATH,
        help=(
            "Ruta al JSON de calibracion de fase 2 para excluir tareas invalidas. "
            "Si no existe o no es JSON valido, el comando falla (salida 2); si no trae "
            f"'{CLAVE_EXCLUSIONES}', no excluye nada y lo declara en rule.exclusiones_origen."
        ),
    )
    parser.add_argument(
        "--rule",
        type=str,
        default="temporal_stratified",
        choices=["temporal_stratified", "leave_one_repo_out"],
        help="Regla de particion a aplicar: temporal_stratified o leave_one_repo_out.",
    )
    parser.add_argument(
        "--n-test",
        type=int,
        default=None,
        choices=[24, 32, 40],
        help="Tamano objetivo del conjunto de prueba para temporal_stratified (24, 32 o 40; por defecto 32).",
    )
    parser.add_argument(
        "--held-out-repo",
        type=str,
        default=None,
        help="Repositorio a reservar para prueba cuando --rule leave_one_repo_out.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Ruta donde guardar el JSON resultante (opcional).",
    )

    args = parser.parse_args(argv)

    if args.rule == "leave_one_repo_out":
        if not args.held_out_repo:
            parser.error("--held-out-repo es obligatorio cuando --rule leave_one_repo_out.")
        if args.n_test is not None:
            parser.error("--n-test no aplica con --rule leave_one_repo_out.")
    elif args.held_out_repo is not None:
        parser.error("--held-out-repo solo aplica con --rule leave_one_repo_out.")

    if not args.tasks.is_file():
        parser.error(f"Archivo de tareas no encontrado: {args.tasks}")

    try:
        sha256_tasks = compute_sha256(args.tasks)
        excluded_ids, origen = load_exclusions(args.calibracion)
        tasks = _read_tasks(args.tasks)
        if args.rule == "leave_one_repo_out":
            result = split_leave_one_repo_out(
                tasks=tasks,
                held_out_repo=str(args.held_out_repo),  # no vacio: lo exige el control de argumentos
                excluded_ids=excluded_ids,
                sha256_tasks=sha256_tasks,
            )
        else:
            result = split_tasks(
                tasks=tasks,
                n_test=32 if args.n_test is None else args.n_test,
                excluded_ids=excluded_ids,
                sha256_tasks=sha256_tasks,
            )
    except (OSError, ParticionError) as exc:
        parser.error(str(exc))

    result["rule"]["exclusiones_origen"] = origen
    if origen == ORIGEN_CLAVE_AUSENTE:
        print(
            f"AVISO: {args.calibracion} no tiene '{CLAVE_EXCLUSIONES}'; no se excluye ninguna tarea.",
            file=sys.stderr,
        )

    formatted_json = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as out:
            out.write(formatted_json)
        print(f"Particion guardada en: {args.output}")
    else:
        print(formatted_json)

    return 0


if __name__ == "__main__":
    sys.exit(main())
