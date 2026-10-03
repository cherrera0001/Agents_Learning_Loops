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
from collections.abc import Sequence
from pathlib import Path
from typing import Any

DEFAULT_CALIBRACION_PATH = Path("experiments/gemma_developer_agent/calibracion/fase2_sin_parche.json")


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


def load_excluded_task_ids(calibracion_path: Path | str | None) -> set[str]:
    """Carga los instance_id a excluir desde el archivo de calibracion."""
    if calibracion_path is None:
        return set()
    p = Path(calibracion_path)
    if not p.is_file():
        return set()
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    invalid_tasks = data.get("tareas_invalidas", [])
    return {item["instance_id"] for item in invalid_tasks if "instance_id" in item}


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


def split_tasks(
    tasks: Sequence[dict[str, Any]],
    n_test: int,
    excluded_ids: set[str] | None = None,
    sha256_tasks: str = "",
) -> dict[str, Any]:
    """Divide las tareas en entrenamiento y prueba de forma temporal y estratificada."""
    if excluded_ids is None:
        excluded_ids = set()

    valid_tasks: list[dict[str, Any]] = [t for t in tasks if str(t.get("instance_id")) not in excluded_ids]

    # Agrupar por repositorio
    by_repo: dict[str, list[dict[str, Any]]] = {}
    for t in valid_tasks:
        repo = str(t.get("repo", "unknown"))
        by_repo.setdefault(repo, []).append(t)

    # Ordenar tareas dentro de cada repo por (created_at, instance_id) ascendente
    for repo_tasks in by_repo.values():
        repo_tasks.sort(key=lambda x: (str(x.get("created_at", "")), str(x.get("instance_id", ""))))

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
            cutoff_date = str(test_slice[0].get("created_at", ""))
        else:
            test_slice = []
            train_slice = rtasks
            cutoff_date = None

        cutoffs_by_repo[repo] = cutoff_date
        train_ids.extend(str(t["instance_id"]) for t in train_slice)
        test_ids.extend(str(t["instance_id"]) for t in test_slice)
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
            "exclusiones_count": len(excluded_ids),
            "excluded_instance_ids": sorted(list(excluded_ids)),
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

    valid_tasks: list[dict[str, Any]] = [t for t in tasks if str(t.get("instance_id")) not in excluded_ids]

    train_ids: list[str] = []
    test_ids: list[str] = []
    repo_breakdown: dict[str, dict[str, int]] = {}

    by_repo: dict[str, list[dict[str, Any]]] = {}
    for t in valid_tasks:
        repo = str(t.get("repo", "unknown"))
        by_repo.setdefault(repo, []).append(t)

    if held_out_repo not in by_repo:
        available = sorted(by_repo.keys())
        raise ValueError(
            f"El repositorio '{held_out_repo}' no existe entre las tareas validas. "
            f"Repositorios disponibles: {available}"
        )

    for repo in sorted(by_repo.keys()):
        rtasks = by_repo[repo]
        # Ordenar deterministamente
        rtasks.sort(key=lambda x: (str(x.get("created_at", "")), str(x.get("instance_id", ""))))
        if repo == held_out_repo:
            test_ids.extend(str(t["instance_id"]) for t in rtasks)
            repo_breakdown[repo] = {
                "total_valid": len(rtasks),
                "train": 0,
                "test": len(rtasks),
            }
        else:
            train_ids.extend(str(t["instance_id"]) for t in rtasks)
            repo_breakdown[repo] = {
                "total_valid": len(rtasks),
                "train": len(rtasks),
                "test": 0,
            }

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
            "exclusiones_count": len(excluded_ids),
            "excluded_instance_ids": sorted(list(excluded_ids)),
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
        help="Ruta al JSON de calibracion de fase 2 para excluir tareas invalidas.",
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
        default=32,
        choices=[24, 32, 40],
        help="Tamano objetivo del conjunto de prueba para temporal_stratified (24, 32 o 40).",
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

    if not args.tasks.is_file():
        raise FileNotFoundError(f"Archivo de tareas no encontrado: {args.tasks}")

    sha256_tasks = compute_sha256(args.tasks)
    excluded_ids = load_excluded_task_ids(args.calibracion)

    tasks: list[dict[str, Any]] = []
    with open(args.tasks, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                tasks.append(json.loads(line))

    if args.rule == "leave_one_repo_out":
        if not args.held_out_repo:
            parser.error("--held-out-repo es obligatorio cuando --rule leave_one_repo_out.")
        result = split_leave_one_repo_out(
            tasks=tasks,
            held_out_repo=args.held_out_repo,
            excluded_ids=excluded_ids,
            sha256_tasks=sha256_tasks,
        )
    else:
        result = split_tasks(
            tasks=tasks,
            n_test=args.n_test,
            excluded_ids=excluded_ids,
            sha256_tasks=sha256_tasks,
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
    import sys

    sys.exit(main())
