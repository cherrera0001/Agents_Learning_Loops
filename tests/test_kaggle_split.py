"""Pruebas unitarias para la particion determinista de tareas (scripts/kaggle_split.py).

Verifica determinismo, no-solapamiento, estratificacion proporcional y
criterio temporal estricto (corte por fecha) utilizando exclusivamente tareas
sinteticas (sin datos de Kaggle).
"""

from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path
from typing import Any

import pytest

from scripts.kaggle_split import (
    ParticionError,
    allocate_proportional_seats,
    load_excluded_task_ids,
    load_exclusions,
    main,
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


# ---------------------------------------------------------------------------
# Datos pequenos escritos a mano: el orden esperado se calcula a ojo.
# ---------------------------------------------------------------------------


def _task(iid: str, repo: str, created_at: str) -> dict[str, Any]:
    return {"instance_id": iid, "repo": repo, "created_at": created_at}


def small_tasks() -> list[dict[str, Any]]:
    """Seis tareas en tres repos, entregadas a proposito fuera de orden.

    Orden interno esperado: a -> a2, a1; b -> b2, b3 (misma fecha, desempata el id), b1; c -> c1.
    El primer elemento es de `repo_c` para que el orden de aparicion no coincida con el alfabetico.
    """
    return [
        _task("c1", "repo_c", "2025-05-01T00:00:00Z"),
        _task("b1", "repo_b", "2025-01-02T00:00:00Z"),
        _task("a1", "repo_a", "2025-03-01T00:00:00Z"),
        _task("b3", "repo_b", "2025-01-01T00:00:00Z"),
        _task("a2", "repo_a", "2025-02-01T00:00:00Z"),
        _task("b2", "repo_b", "2025-01-01T00:00:00Z"),
    ]


def test_loro_exact_order_and_all_fields() -> None:
    """Fija el orden exacto de train/test y cada campo de salida de leave-one-repo-out."""
    res = split_leave_one_repo_out(small_tasks(), "repo_b", excluded_ids=set(), sha256_tasks="abc123")

    assert res["test"] == ["b2", "b3", "b1"]
    assert res["train"] == ["a2", "a1", "c1"]
    assert res["rule"]["name"] == "leave_one_repo_out"
    assert res["rule"]["held_out_repo"] == "repo_b"
    assert res["rule"]["n_test_efectivo"] == 3
    assert res["rule"]["n_train_efectivo"] == 3
    assert res["rule"]["exclusiones_pedidas"] == 0
    assert res["rule"]["exclusiones_aplicadas"] == 0
    assert res["rule"]["excluded_instance_ids"] == []
    assert res["rule"]["excluded_ids_inexistentes"] == []
    assert res["sha256_tasks"] == "abc123"
    assert res["counts"] == {
        "total_tasks_recibidas": 6,
        "total_excluidas": 0,
        "total_validas": 6,
        "total_train": 3,
        "total_test": 3,
        "by_repo": {
            "repo_a": {"total_valid": 2, "train": 2, "test": 0},
            "repo_b": {"total_valid": 3, "train": 0, "test": 3},
            "repo_c": {"total_valid": 1, "train": 1, "test": 0},
        },
    }
    assert list(res["counts"]["by_repo"]) == ["repo_a", "repo_b", "repo_c"]


def test_temporal_exact_order_and_all_fields() -> None:
    """Fija el orden exacto y cada campo de salida de la regla temporal estratificada."""
    # Cuotas con n_test=3: a=1.0, b=1.5, c=0.5 -> a:1, b:1 y la vacante restante
    # al empate de residuo 0.5 por nombre (b). Resultado: a=1, b=2, c=0.
    res = split_tasks(small_tasks(), n_test=3, excluded_ids=set(), sha256_tasks="abc123")

    assert res["train"] == ["a2", "b2", "c1"]
    assert res["test"] == ["a1", "b3", "b1"]
    assert res["rule"]["name"] == "temporal_stratified_by_repo"
    assert res["rule"]["n_test_solicitado"] == 3
    assert res["rule"]["n_test_efectivo"] == 3
    assert res["rule"]["n_train_efectivo"] == 3
    assert res["rule"]["excluded_instance_ids"] == []
    assert res["sha256_tasks"] == "abc123"
    assert res["cutoffs_by_repo"] == {
        "repo_a": "2025-03-01T00:00:00Z",
        "repo_b": "2025-01-01T00:00:00Z",
        "repo_c": None,
    }
    assert res["counts"] == {
        "total_tasks_recibidas": 6,
        "total_excluidas": 0,
        "total_validas": 6,
        "total_train": 3,
        "total_test": 3,
        "by_repo": {
            "repo_a": {"total_valid": 2, "train": 1, "test": 1},
            "repo_b": {"total_valid": 3, "train": 1, "test": 2},
            "repo_c": {"total_valid": 1, "train": 1, "test": 0},
        },
    }


def test_effective_counts_differ_so_swapping_is_detected() -> None:
    """Con train != test, cruzar los contadores de rule o de counts rompe la igualdad."""
    res = split_tasks(small_tasks(), n_test=2)
    assert (res["rule"]["n_test_efectivo"], res["rule"]["n_train_efectivo"]) == (2, 4)
    assert (res["counts"]["total_test"], res["counts"]["total_train"]) == (2, 4)

    res = split_leave_one_repo_out(small_tasks(), "repo_c")
    assert (res["rule"]["n_test_efectivo"], res["rule"]["n_train_efectivo"]) == (1, 5)
    assert (res["counts"]["total_test"], res["counts"]["total_train"]) == (1, 5)


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
def test_result_is_invariant_to_input_order(seed: int) -> None:
    """Barajar la lista de entrada no cambia ninguna parte de la salida, en ambas reglas."""
    base = generate_synthetic_tasks({"repo_alpha": 12, "repo_beta": 7, "repo_gamma": 3}, seed=99)
    shuffled = list(base)
    random.Random(seed).shuffle(shuffled)
    excluded = {"repo_alpha_task_002"}

    assert split_tasks(shuffled, 8, excluded, "h") == split_tasks(base, 8, excluded, "h")
    assert split_leave_one_repo_out(shuffled, "repo_beta", excluded, "h") == split_leave_one_repo_out(
        base, "repo_beta", excluded, "h"
    )


def test_train_and_test_are_sorted_by_date_then_id(synthetic_tasks: list[dict[str, Any]]) -> None:
    """Dentro de cada repositorio, train y test salen por (created_at, instance_id) ascendente."""
    by_id = {t["instance_id"]: t for t in synthetic_tasks}
    for res in (
        split_tasks(synthetic_tasks, 18),
        split_leave_one_repo_out(synthetic_tasks, "repo_beta"),
    ):
        for key in ("train", "test"):
            repos_seen: list[str] = []
            last: tuple[str, str] | None = None
            for tid in res[key]:
                repo = by_id[tid]["repo"]
                if not repos_seen or repos_seen[-1] != repo:
                    assert repo not in repos_seen, "un repo aparece en dos bloques"
                    repos_seen.append(repo)
                    last = None
                cur = (by_id[tid]["created_at"], tid)
                assert last is None or last < cur
                last = cur
            assert repos_seen == sorted(repos_seen)


def test_exclusion_report_distinguishes_requested_from_applied() -> None:
    """Separa exclusiones pedidas de aplicadas y lista los ids pedidos que no existen."""
    for res in (
        split_tasks(small_tasks(), 3, {"a1", "fantasma"}),
        split_leave_one_repo_out(small_tasks(), "repo_b", {"a1", "fantasma"}),
    ):
        assert res["rule"]["exclusiones_pedidas"] == 2
        assert res["rule"]["exclusiones_aplicadas"] == 1
        assert res["rule"]["excluded_instance_ids"] == ["a1", "fantasma"]
        assert res["rule"]["excluded_ids_inexistentes"] == ["fantasma"]
        assert res["counts"]["total_excluidas"] == 1
        assert "a1" not in res["train"] + res["test"]


# ---------------------------------------------------------------------------
# Bordes y validacion de entrada
# ---------------------------------------------------------------------------


def test_single_task_repo_edges() -> None:
    """Un repo de una tarea: en temporal sin vacantes queda en train; como held-out, test completo."""
    res = split_tasks(small_tasks(), n_test=1)
    assert res["counts"]["by_repo"]["repo_c"] == {"total_valid": 1, "train": 1, "test": 0}
    assert res["cutoffs_by_repo"]["repo_c"] is None

    res = split_leave_one_repo_out(small_tasks(), "repo_c")
    assert res["test"] == ["c1"]
    assert res["train"] == ["a2", "a1", "b2", "b3", "b1"]


def test_held_out_fully_excluded_is_an_error() -> None:
    """Si las exclusiones vacian el repo reservado, falla y lista los repos que si quedan."""
    with pytest.raises(ParticionError, match=r"'repo_c' no existe.*\['repo_a', 'repo_b'\]"):
        split_leave_one_repo_out(small_tasks(), "repo_c", excluded_ids={"c1"})


def test_empty_input_is_an_error() -> None:
    """Una lista vacia no es una particion valida en ninguna de las dos reglas."""
    with pytest.raises(ParticionError, match="No hay tareas"):
        split_tasks([], 24)
    with pytest.raises(ParticionError, match="No hay tareas"):
        split_leave_one_repo_out([], "repo_a")


def test_everything_excluded_is_an_error_in_temporal() -> None:
    """Excluir todas las tareas deja la regla temporal sin nada que partir."""
    with pytest.raises(ParticionError, match="excluidas"):
        split_tasks(small_tasks(), 3, {t["instance_id"] for t in small_tasks()})


def test_negative_n_test_is_an_error() -> None:
    """Un n_test negativo no se interpreta como «todo menos»."""
    with pytest.raises(ParticionError, match="negativo"):
        split_tasks(small_tasks(), -1)


@pytest.mark.parametrize("campo", ["repo", "instance_id", "created_at"])
def test_task_missing_required_field_is_an_error(campo: str) -> None:
    """Una tarea sin repo, instance_id o created_at se rechaza en lugar de inventar un valor."""
    tasks = small_tasks()
    del tasks[2][campo]
    with pytest.raises(ParticionError, match=f"'{campo}'"):
        split_tasks(tasks, 3)
    with pytest.raises(ParticionError, match=f"'{campo}'"):
        split_leave_one_repo_out(tasks, "repo_b")


def test_task_without_repo_cannot_be_held_out_as_unknown() -> None:
    """Una tarea sin repo no crea un repositorio sintetico 'unknown' reservable."""
    tasks = small_tasks()
    del tasks[0]["repo"]
    with pytest.raises(ParticionError):
        split_leave_one_repo_out(tasks, "unknown")


def test_duplicate_instance_id_is_an_error() -> None:
    """Un instance_id repetido se rechaza, incluso si una de las copias esta excluida."""
    tasks = [*small_tasks(), _task("a1", "repo_a", "2025-09-09T00:00:00Z")]
    with pytest.raises(ParticionError, match="duplicado: 'a1'"):
        split_tasks(tasks, 3)
    with pytest.raises(ParticionError, match="duplicado: 'a1'"):
        split_leave_one_repo_out(tasks, "repo_b", excluded_ids={"a1"})


# ---------------------------------------------------------------------------
# Carga de exclusiones
# ---------------------------------------------------------------------------


def _write_json(path: Path, data: Any) -> Path:
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_load_exclusions_variants(tmp_path: Path) -> None:
    """Distingue sin calibracion, clave presente, clave ausente y los errores de lectura."""
    assert load_exclusions(None) == (set(), "sin_calibracion")

    con = _write_json(
        tmp_path / "con.json", {"tareas_invalidas": [{"instance_id": "a1"}, {"instance_id": "b1"}]}
    )
    assert load_exclusions(con) == ({"a1", "b1"}, "calibracion:tareas_invalidas")
    assert load_excluded_task_ids(con) == {"a1", "b1"}

    vacia = _write_json(tmp_path / "vacia.json", {"tareas_invalidas": []})
    assert load_exclusions(vacia) == (set(), "calibracion:tareas_invalidas")

    sin_clave = _write_json(tmp_path / "sin.json", {"otra": 1})
    assert load_exclusions(sin_clave) == (set(), "calibracion:sin_clave_tareas_invalidas")

    with pytest.raises(FileNotFoundError):
        load_exclusions(tmp_path / "no_existe.json")

    roto = tmp_path / "roto.json"
    roto.write_text("{no es json", encoding="utf-8")
    with pytest.raises(ParticionError, match="No se pudo leer"):
        load_exclusions(roto)

    with pytest.raises(ParticionError, match="objeto JSON"):
        load_exclusions(_write_json(tmp_path / "lista.json", [1, 2]))
    with pytest.raises(ParticionError, match="debe ser una lista"):
        load_exclusions(_write_json(tmp_path / "t.json", {"tareas_invalidas": "x"}))
    with pytest.raises(ParticionError, match="instance_id"):
        load_exclusions(_write_json(tmp_path / "i.json", {"tareas_invalidas": [{"otro": 1}]}))


# ---------------------------------------------------------------------------
# main() de punta a punta
# ---------------------------------------------------------------------------


@pytest.fixture
def cli_files(tmp_path: Path) -> dict[str, Path]:
    """Escribe tasks.jsonl sintetico y una calibracion con la clave presente y vacia."""
    tasks_path = tmp_path / "tasks.jsonl"
    tasks_path.write_text("\n".join(json.dumps(t) for t in small_tasks()) + "\n\n", encoding="utf-8")
    cal = _write_json(tmp_path / "cal.json", {"tareas_invalidas": []})
    return {"tasks": tasks_path, "cal": cal, "dir": tmp_path}


def run_main(capsys: pytest.CaptureFixture[str], *args: str) -> tuple[dict[str, Any], str]:
    """Ejecuta main con exito (salida 0) y devuelve el JSON impreso y stderr."""
    assert main(list(args)) == 0
    captured = capsys.readouterr()
    return json.loads(captured.out), captured.err


def run_main_error(capsys: pytest.CaptureFixture[str], *args: str) -> str:
    """Ejecuta main esperando SystemExit con codigo 2 y devuelve stderr."""
    with pytest.raises(SystemExit) as exc:
        main(list(args))
    assert exc.value.code == 2
    return capsys.readouterr().err


def test_main_default_rule_is_temporal_with_n_test_32(
    cli_files: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """Sin --rule ni --n-test: temporal con 32 solicitados; con --n-test 24 se respeta."""
    out, _ = run_main(capsys, "--tasks", str(cli_files["tasks"]), "--calibracion", str(cli_files["cal"]))
    assert out["rule"]["name"] == "temporal_stratified_by_repo"
    assert out["rule"]["n_test_solicitado"] == 32
    assert out["sha256_tasks"] == hashlib.sha256(cli_files["tasks"].read_bytes()).hexdigest()
    assert out["rule"]["exclusiones_origen"] == "calibracion:tareas_invalidas"

    out, _ = run_main(
        capsys, "--tasks", str(cli_files["tasks"]), "--calibracion", str(cli_files["cal"]), "--n-test", "24"
    )
    assert out["rule"]["n_test_solicitado"] == 24


def test_main_dispatches_loro_with_requested_repo_and_sha(
    cli_files: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """--rule leave_one_repo_out despacha a LORO, usa el repo pedido y propaga el hash de las tareas."""
    sha = hashlib.sha256(cli_files["tasks"].read_bytes()).hexdigest()
    base = [
        "--tasks",
        str(cli_files["tasks"]),
        "--calibracion",
        str(cli_files["cal"]),
        "--rule",
        "leave_one_repo_out",
    ]

    out_b, _ = run_main(capsys, *base, "--held-out-repo", "repo_b")
    assert out_b["rule"]["name"] == "leave_one_repo_out"
    assert out_b["rule"]["held_out_repo"] == "repo_b"
    assert out_b["test"] == ["b2", "b3", "b1"]
    assert out_b["train"] == ["a2", "a1", "c1"]
    assert out_b["sha256_tasks"] == sha

    out_a, _ = run_main(capsys, *base, "--held-out-repo", "repo_a")
    assert out_a["rule"]["held_out_repo"] == "repo_a"
    assert out_a["test"] == ["a2", "a1"]
    assert "cutoffs_by_repo" not in out_a


def test_main_loro_applies_calibracion_exclusions(
    cli_files: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """Las exclusiones de --calibracion se aplican tambien en LORO y se informan pedidas/aplicadas."""
    cal = _write_json(
        cli_files["dir"] / "cal2.json",
        {"tareas_invalidas": [{"instance_id": "b3"}, {"instance_id": "fantasma"}]},
    )
    out, _ = run_main(
        capsys,
        "--tasks", str(cli_files["tasks"]),
        "--calibracion", str(cal),
        "--rule", "leave_one_repo_out",
        "--held-out-repo", "repo_b",
    )  # fmt: skip
    assert out["test"] == ["b2", "b1"]
    assert out["rule"]["exclusiones_pedidas"] == 2
    assert out["rule"]["exclusiones_aplicadas"] == 1
    assert out["rule"]["excluded_ids_inexistentes"] == ["fantasma"]
    assert out["counts"]["total_excluidas"] == 1


def test_main_declares_missing_key_in_output_and_stderr(
    cli_files: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """Un JSON valido sin 'tareas_invalidas' da cero exclusiones, declaradas en la salida y por stderr."""
    cal = _write_json(cli_files["dir"] / "sin.json", {"otra_cosa": 1})
    out, err = run_main(capsys, "--tasks", str(cli_files["tasks"]), "--calibracion", str(cal))
    assert out["rule"]["exclusiones_origen"] == "calibracion:sin_clave_tareas_invalidas"
    assert out["rule"]["exclusiones_pedidas"] == 0
    assert "AVISO" in err and "tareas_invalidas" in err


def test_main_writes_output_file(cli_files: dict[str, Path], capsys: pytest.CaptureFixture[str]) -> None:
    """--output guarda el JSON (creando directorios) y no lo imprime."""
    destino = cli_files["dir"] / "sub" / "out.json"
    assert (
        main(
            [
                "--tasks",
                str(cli_files["tasks"]),
                "--calibracion",
                str(cli_files["cal"]),
                "--output",
                str(destino),
            ]
        )
        == 0
    )
    assert "Particion guardada" in capsys.readouterr().out
    assert json.loads(destino.read_text(encoding="utf-8"))["rule"]["name"] == "temporal_stratified_by_repo"


def test_main_loro_requires_held_out_repo(
    cli_files: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """LORO sin --held-out-repo termina con salida 2."""
    err = run_main_error(
        capsys,
        "--tasks",
        str(cli_files["tasks"]),
        "--calibracion",
        str(cli_files["cal"]),
        "--rule",
        "leave_one_repo_out",
    )
    assert "--held-out-repo" in err


def test_main_rejects_options_that_do_not_apply(
    cli_files: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """--n-test con LORO y --held-out-repo con la regla temporal terminan con salida 2."""
    base = ["--tasks", str(cli_files["tasks"]), "--calibracion", str(cli_files["cal"])]
    # Incluso el valor por defecto escrito de forma explicita es un error.
    err = run_main_error(
        capsys, *base, "--rule", "leave_one_repo_out", "--held-out-repo", "repo_b", "--n-test", "32"
    )
    assert "--n-test" in err
    err = run_main_error(capsys, *base, "--held-out-repo", "repo_b")
    assert "--held-out-repo" in err


def test_main_unknown_repo_lists_available(
    cli_files: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """Un repo inexistente da salida 2 con la lista de repos disponibles, no un traceback."""
    err = run_main_error(
        capsys,
        "--tasks", str(cli_files["tasks"]),
        "--calibracion", str(cli_files["cal"]),
        "--rule", "leave_one_repo_out",
        "--held-out-repo", "repo_zzz",
    )  # fmt: skip
    assert "repo_zzz" in err and "['repo_a', 'repo_b', 'repo_c']" in err


def test_main_calibracion_unreadable_is_an_error(
    cli_files: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """Calibracion inexistente, con JSON roto o con forma invalida: salida 2, no «sin exclusiones»."""
    tasks = str(cli_files["tasks"])
    err = run_main_error(capsys, "--tasks", tasks, "--calibracion", str(cli_files["dir"] / "no_existe.json"))
    assert "no encontrado" in err

    roto = cli_files["dir"] / "roto.json"
    roto.write_text("{x", encoding="utf-8")
    err = run_main_error(capsys, "--tasks", tasks, "--calibracion", str(roto))
    assert "No se pudo leer" in err

    lista = _write_json(cli_files["dir"] / "lista.json", [])
    run_main_error(capsys, "--tasks", tasks, "--calibracion", str(lista))


def test_main_invalid_tasks_input_is_an_error(
    cli_files: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """Archivo ausente, linea no JSON, id duplicado, tarea sin repo o sin id: salida 2."""
    cal = str(cli_files["cal"])
    run_main_error(capsys, "--tasks", str(cli_files["dir"] / "nada.jsonl"), "--calibracion", cal)

    def con_lineas(nombre: str, lineas: list[str]) -> str:
        p = cli_files["dir"] / nombre
        p.write_text("\n".join(lineas) + "\n", encoding="utf-8")
        return str(p)

    good = json.dumps(_task("a1", "repo_a", "2025-01-01T00:00:00Z"))
    err = run_main_error(capsys, "--tasks", con_lineas("mala.jsonl", [good, "{no"]), "--calibracion", cal)
    assert "Linea 2" in err
    err = run_main_error(capsys, "--tasks", con_lineas("dup.jsonl", [good, good]), "--calibracion", cal)
    assert "duplicado" in err
    sin_repo = json.dumps({"instance_id": "x", "created_at": "2025-01-01T00:00:00Z"})
    err = run_main_error(capsys, "--tasks", con_lineas("sr.jsonl", [good, sin_repo]), "--calibracion", cal)
    assert "'repo'" in err
    sin_id = json.dumps({"repo": "r", "created_at": "2025-01-01T00:00:00Z"})
    err = run_main_error(capsys, "--tasks", con_lineas("si.jsonl", [good, sin_id]), "--calibracion", cal)
    assert "'instance_id'" in err
    run_main_error(capsys, "--tasks", con_lineas("vacio.jsonl", []), "--calibracion", cal)
