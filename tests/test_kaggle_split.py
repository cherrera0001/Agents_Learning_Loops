"""Pruebas unitarias para la particion determinista de tareas (scripts/kaggle_split.py).

Verifica determinismo, no-solapamiento, estratificacion proporcional y
criterio temporal estricto (corte por fecha) utilizando exclusivamente tareas
sinteticas (sin datos de Kaggle).
"""

from __future__ import annotations

import random
from typing import Any

import pytest

from scripts.kaggle_split import (
    allocate_proportional_seats,
    split_leave_one_repo_out,
    split_tasks,
)


def generate_synthetic_tasks(counts_per_repo: dict[str, int], seed: int = 42) -> list[dict[str, Any]]:
    """Genera tareas sinteticas con fechas deterministas no correlacionadas con el orden."""
    rng = random.Random(seed)
    tasks: list[dict[str, Any]] = []

    for repo, count in counts_per_repo.items():
        base_year = 2025
        for i in range(count):
            day = (i * 3) % 28 + 1
            month = (i % 12) + 1
            hour = (i * 7) % 24
            minute = (i * 11) % 60
            created_at = f"{base_year:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:00Z"
            tasks.append(
                {
                    "instance_id": f"{repo}_task_{i:03d}",
                    "repo": repo,
                    "created_at": created_at,
                    "problem_statement": f"Synthetic bug in {repo} #{i}",
                }
            )

    # Mezclar aleatoriamente el orden de llegada para probar estabilidad
    rng.shuffle(tasks)
    return tasks


@pytest.fixture
def synthetic_tasks() -> list[dict[str, Any]]:
    """Fixture de 60 tareas sinteticas repartidas en 3 repositorios (30, 20, 10)."""
    return generate_synthetic_tasks({"repo_alpha": 30, "repo_beta": 20, "repo_gamma": 10}, seed=123)


def test_split_is_deterministic(synthetic_tasks: list[dict[str, Any]]) -> None:
    """Comprueba que dos ejecuciones con los mismos datos producen identica particion."""
    res1 = split_tasks(synthetic_tasks, n_test=18)
    res2 = split_tasks(synthetic_tasks, n_test=18)

    assert res1["train"] == res2["train"]
    assert res1["test"] == res2["test"]
    assert res1["cutoffs_by_repo"] == res2["cutoffs_by_repo"]


def test_train_and_test_do_not_overlap(synthetic_tasks: list[dict[str, Any]]) -> None:
    """Comprueba que los conjuntos de entrenamiento y prueba son disjuntos."""
    res = split_tasks(synthetic_tasks, n_test=18)
    train_set = set(res["train"])
    test_set = set(res["test"])

    intersection = train_set & test_set
    assert not intersection, f"Entrenamiento y prueba se solapan en: {intersection}"
    assert len(train_set) + len(test_set) == len(synthetic_tasks)


def test_proportions_per_repo(synthetic_tasks: list[dict[str, Any]]) -> None:
    """Comprueba que cada repositorio recibe vacantes proporcionales a su tamano."""
    # 60 tareas: 30 alpha (50%), 20 beta (33.3%), 10 gamma (16.7%)
    # Para n_test = 18:
    # alpha = 18 * 0.5 = 9
    # beta = 18 * (20/60) = 6
    # gamma = 18 * (10/60) = 3
    res = split_tasks(synthetic_tasks, n_test=18)
    by_repo = res["counts"]["by_repo"]

    assert by_repo["repo_alpha"]["test"] == 9
    assert by_repo["repo_alpha"]["train"] == 21

    assert by_repo["repo_beta"]["test"] == 6
    assert by_repo["repo_beta"]["train"] == 14

    assert by_repo["repo_gamma"]["test"] == 3
    assert by_repo["repo_gamma"]["train"] == 7

    assert len(res["test"]) == 18
    assert len(res["train"]) == 42


def test_no_test_task_is_older_than_repo_cutoff(
    synthetic_tasks: list[dict[str, Any]],
) -> None:
    """Comprueba que ninguna tarea de prueba es anterior a las tareas de entrenamiento del mismo repo."""
    res = split_tasks(synthetic_tasks, n_test=18)
    tasks_by_id = {t["instance_id"]: t for t in synthetic_tasks}

    test_ids = set(res["test"])
    train_ids = set(res["train"])

    for repo, cutoff in res["cutoffs_by_repo"].items():
        if cutoff is None:
            continue

        repo_train_dates = [
            tasks_by_id[tid]["created_at"] for tid in train_ids if tasks_by_id[tid]["repo"] == repo
        ]
        repo_test_dates = [
            tasks_by_id[tid]["created_at"] for tid in test_ids if tasks_by_id[tid]["repo"] == repo
        ]

        assert repo_test_dates, f"Repo {repo} no tiene tareas de prueba"
        assert min(repo_test_dates) == cutoff

        if repo_train_dates:
            assert max(repo_train_dates) <= min(repo_test_dates), (
                f"Fallo temporal en {repo}: la tarea de train mas reciente "
                f"({max(repo_train_dates)}) es posterior a la de test mas antigua "
                f"({min(repo_test_dates)})"
            )


def test_excluded_tasks_are_ignored(synthetic_tasks: list[dict[str, Any]]) -> None:
    """Comprueba que las tareas marcadas como excluidas no van a train ni a test."""
    excluded = {"repo_alpha_task_001", "repo_beta_task_005"}
    res = split_tasks(synthetic_tasks, n_test=18, excluded_ids=excluded)

    all_assigned = set(res["train"]) | set(res["test"])
    for ex in excluded:
        assert ex not in all_assigned, f"Tarea excluida {ex} fue asignada"

    assert res["counts"]["total_excluidas"] == len(excluded)
    assert res["counts"]["total_validas"] == len(synthetic_tasks) - len(excluded)


def test_largest_remainder_hamilton_exactness() -> None:
    """Verifica que la asignacion proporcional suma exactamente el total de vacantes."""
    counts = {"A": 10, "B": 10, "C": 10}
    seats = allocate_proportional_seats(counts, total_seats=7)
    assert sum(seats.values()) == 7


def test_leave_one_repo_out_basic(synthetic_tasks: list[dict[str, Any]]) -> None:
    """Comprueba que leave-one-repo-out aisla completamente el repo objetivo en test."""
    res = split_leave_one_repo_out(synthetic_tasks, held_out_repo="repo_beta")

    assert res["rule"]["name"] == "leave_one_repo_out"
    assert res["rule"]["held_out_repo"] == "repo_beta"

    train_set = set(res["train"])
    test_set = set(res["test"])

    # Disjuntos y completos
    assert not (train_set & test_set)
    assert len(train_set) + len(test_set) == len(synthetic_tasks)

    # 20 tareas de repo_beta deben estar exactamente en test
    assert len(test_set) == 20
    assert len(train_set) == 40

    tasks_by_id = {t["instance_id"]: t for t in synthetic_tasks}
    for tid in test_set:
        assert tasks_by_id[tid]["repo"] == "repo_beta"
    for tid in train_set:
        assert tasks_by_id[tid]["repo"] != "repo_beta"


def test_leave_one_repo_out_deterministic(synthetic_tasks: list[dict[str, Any]]) -> None:
    """Comprueba que leave-one-repo-out produce salidas identicas entre ejecuciones."""
    res1 = split_leave_one_repo_out(synthetic_tasks, held_out_repo="repo_alpha")
    res2 = split_leave_one_repo_out(synthetic_tasks, held_out_repo="repo_alpha")

    assert res1["train"] == res2["train"]
    assert res1["test"] == res2["test"]
    assert res1["counts"] == res2["counts"]


def test_leave_one_repo_out_with_exclusions(synthetic_tasks: list[dict[str, Any]]) -> None:
    """Comprueba que tareas excluidas se ignoran tanto del repo reservado como de los de entrenamiento."""
    excluded = {"repo_alpha_task_001", "repo_beta_task_005"}
    res = split_leave_one_repo_out(synthetic_tasks, held_out_repo="repo_beta", excluded_ids=excluded)

    all_assigned = set(res["train"]) | set(res["test"])
    for ex in excluded:
        assert ex not in all_assigned

    assert res["counts"]["total_excluidas"] == 2
    assert res["counts"]["total_validas"] == 58
    assert res["counts"]["by_repo"]["repo_beta"]["test"] == 19
    assert res["counts"]["by_repo"]["repo_alpha"]["train"] == 29


def test_leave_one_repo_out_unknown_repo(synthetic_tasks: list[dict[str, Any]]) -> None:
    """Comprueba que solicitar un repo inexistente lanza ValueError."""
    with pytest.raises(ValueError, match="El repositorio 'repo_fantasma' no existe"):
        split_leave_one_repo_out(synthetic_tasks, held_out_repo="repo_fantasma")
