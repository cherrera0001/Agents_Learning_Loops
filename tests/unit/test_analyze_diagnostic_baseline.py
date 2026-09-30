"""Análisis pre-registrado de #58: validación cerrada de la campaña y cada lectura alcanzable.

``analyze`` solo se ejercita sobre una campaña sintética **completa** (2 réplicas × 6 semillas × 3
condiciones × 9 tareas = 324 ``task_run`` y 72 ``memory_update``), igual en forma a la declarada. Los
helpers (clasificación de pares, veredicto, carga sellada) se prueban por separado.
"""

import ast
import copy
import inspect
import itertools
import json

import pytest

from scripts import analyze_diagnostic_baseline as analysis
from scripts.analyze_diagnostic_baseline import AGENT, POLICY, analyze, classify, compare, load, verdict

TASKS = [f"EXP-{i:02d}" for i in range(1, 10)]
TRAIN, ORIGINAL, MISLEADING = TASKS[:3], TASKS[3:6], TASKS[6:]
SEEDS = (1, 4, 5, 6, 7, 9)
MODES = ("NO_MEMORY", "TEXT_HISTORY", "ASSOCIATIVE_MEMORY")
BATCHES = ("BATCH-a", "BATCH-b")
PRIVATE = {t: {"family": f} for t, f in zip(TASKS, ["auth", "config", "ready"] * 3, strict=True)}
for _task, _decoy in zip(MISLEADING, ["ready", "auth", "config"], strict=True):
    PRIVATE[_task]["decoy_family"] = _decoy
PRIOR = ["initialize_storage", "validate_optional_identity", "normalize_environment"]


def baseline_first(mode, task, seed):
    return seed in (1, 4)  # 2 of 6 seeds per task: 6/18 per kind and condition


def task_run(batch, seed, task, mode, first, status, lessons):
    run_id = f"RUN-{batch}-{seed}-{task}-{mode}"
    proposal = "p" if lessons else None
    exposed = lessons if mode == "TEXT_HISTORY" else lessons[:1]
    iterations = 1 if first else 2
    return {
        "kind": "task_run",
        "run_id": run_id,
        "receipt_sha256": "sha-" + run_id,
        "agent": AGENT,
        "batch_id": batch,
        "seed": seed,
        "task": {"id": task},
        "memory_mode": mode,
        "split": "train" if task in TRAIN else "transfer",
        "result": "PASS",
        "memory_input": None if mode == "NO_MEMORY" else {"lessons": list(lessons)},
        "retrieval": {"memories": [{"id": m["id"], "task": m["task"]} for m in exposed]},
        "decision": {
            "policy": POLICY,
            "plan": PRIOR[::-1] if proposal else PRIOR,
            "memory_ids": [exposed[0]["id"]] if proposal else [],
            "memory_proposal": proposal,
            "memory_effect": "changed_first" if proposal else "no_proposal",
            "diagnostic": {"status": status(task)},
        },
        "iterations": iterations,
        "duration_ms": 1.0,
        "tests": [{}] * (iterations + 1),
        "outcome": {"success": True, "first_attempt_success": first, "iterations": iterations},
    }


def campaign(first=baseline_first, status=lambda task: "partial"):
    """Misma forma que ``python -m experiments run --campaign diagnostic-baseline-v1``."""
    receipts = []
    for batch, seed, mode in itertools.product(BATCHES, SEEDS, MODES):
        lessons = []
        for task in TASKS:
            r = task_run(batch, seed, task, mode, first(mode, task, seed), status, lessons)
            receipts.append(r)
            if task in TRAIN and mode != "NO_MEMORY":
                update = {"kind": "memory_update", "run_id": "RUN-mu" + r["run_id"][3:]}
                receipts.append({**update, "source_receipt": r["run_id"] + ".json"})
                lesson = {"id": "lesson:" + r["run_id"], "run_id": r["run_id"], "task": task}
                lessons = [*lessons, {**lesson, "receipt_sha256": r["receipt_sha256"]}]
    return receipts


def runs_of(receipts):
    return [r for r in receipts if r["kind"] == "task_run"]


def find(receipts, batch, seed, task, mode):
    key = (batch, seed, task, mode)
    return next(
        r for r in runs_of(receipts) if (r["batch_id"], r["seed"], r["task"]["id"], r["memory_mode"]) == key
    )


def renamed(r, **changes):
    r = copy.deepcopy(r)
    r.update(changes)
    r["run_id"] = f"RUN-{r['batch_id']}-{r['seed']}-{r['task']['id']}-{r['memory_mode']}-copy"
    return r


# --- validación cerrada de la campaña concreta -------------------------------------------------


def test_a_complete_campaign_is_accepted_with_its_exact_counts():
    report = analyze(campaign(), PRIVATE)
    assert report["campaign"]["task_runs"] == 324 and report["campaign"]["memory_updates"] == 72
    assert report["campaign"]["batches"] == list(BATCHES) and report["campaign"]["primary_batch"] == "BATCH-a"
    assert report["replicates_consistent"] is True
    for kind in ("original", "misleading", "train"):
        for key in ("TEXT_HISTORY", "ASSOCIATIVE_MEMORY", "ASSOCIATIVE_MEMORY_vs_TEXT_HISTORY"):
            assert report["kinds"][kind]["comparisons"][key]["pairs"] == 18


def test_one_seed_one_batch_27_runs_is_rejected_before_any_verdict():
    """Defecto reproducido en la revisión: 9 tareas × 3 condiciones, semilla 1, un lote."""
    runs = [r for r in runs_of(campaign()) if r["seed"] == 1 and r["batch_id"] == "BATCH-a"]
    assert len(runs) == 27
    with pytest.raises(ValueError, match="réplicas"):
        analyze(runs, PRIVATE)


def _without(predicate):
    return [r for r in campaign() if not predicate(r)]


DECLARED = "no es la campaña declarada"


@pytest.mark.parametrize(
    ("receipts", "message"),
    [
        (_without(lambda r: r["kind"] == "task_run" and r["task"]["id"] == "EXP-05"), DECLARED),  # una tarea
        (
            _without(lambda r: r.get("seed") == 9 or ("-9-" in r["run_id"] and r["kind"] == "memory_update")),
            DECLARED,
        ),
        (_without(lambda r: "BATCH-b" in r["run_id"]), "réplicas"),  # una réplica: nunca «consistente»
        (_without(lambda r: r["run_id"] == "RUN-BATCH-b-6-EXP-08-ASSOCIATIVE_MEMORY"), DECLARED),  # una celda
        (_without(lambda r: r["run_id"] == "RUN-mu-BATCH-a-4-EXP-02-TEXT_HISTORY"), "memory_update"),
    ],
    ids=["task", "seed", "replicate", "cell", "memory-update"],
)
def test_missing_parts_are_rejected(receipts, message):
    with pytest.raises(ValueError, match=message):
        analyze(receipts, PRIVATE)


def test_duplicate_cells_unexpected_seeds_tasks_and_batches_are_rejected():
    base = campaign()
    cell = find(base, "BATCH-a", 5, "EXP-04", "TEXT_HISTORY")
    extra_seed = [renamed(r, seed=2) for r in runs_of(base) if r["seed"] == 1]
    extra_task = [renamed(r, task={"id": "EXP-10"}) for r in runs_of(base) if r["task"]["id"] == "EXP-09"]
    third_batch = [renamed(r, batch_id="BATCH-c") for r in runs_of(base) if r["batch_id"] == "BATCH-a"]
    for receipts, message in (
        ([*base, renamed(cell)], "celda duplicada"),
        ([*base, *extra_seed], DECLARED),
        ([*base, *extra_task], DECLARED),
        ([*base, *third_batch], "réplicas"),
    ):
        with pytest.raises(ValueError, match=message):
            analyze(receipts, {**PRIVATE, "EXP-10": {"family": "auth"}})


def test_pairs_come_from_one_batch_even_when_batches_split_seeds():
    """La réplica se elige por lote para toda semilla, nunca por celda o por semilla: si la semilla 9
    de un lote vive en un tercer lote, cada semilla sigue teniendo dos lotes, pero la campaña no."""
    moved = [
        {**r, "batch_id": "BATCH-c"}
        if r["kind"] == "task_run" and r["batch_id"] == "BATCH-a" and r["seed"] == 9
        else r
        for r in campaign()
    ]
    with pytest.raises(ValueError, match="réplicas"):
        analyze(moved, PRIVATE)


@pytest.mark.parametrize(
    ("task", "mode", "lesson_task"),
    [
        ("EXP-02", "TEXT_HISTORY", "EXP-03"),  # entrenamiento futuro
        ("EXP-05", "ASSOCIATIVE_MEMORY", "EXP-04"),  # lección de una tarea de transferencia
    ],
)
def test_lessons_from_future_or_transfer_runs_are_rejected(task, mode, lesson_task):
    base = campaign()
    target = find(base, "BATCH-a", 4, task, mode)
    source = find(base, "BATCH-a", 4, lesson_task, mode)
    lesson = {"id": "lesson:" + source["run_id"], "run_id": source["run_id"], "task": lesson_task}
    target["memory_input"]["lessons"].append({**lesson, "receipt_sha256": source["receipt_sha256"]})
    with pytest.raises(ValueError, match="procedencia"):
        analyze(base, PRIVATE)


def test_lessons_from_another_batch_or_with_a_wrong_seal_are_rejected():
    base = campaign()
    target = find(base, "BATCH-a", 6, "EXP-07", "TEXT_HISTORY")
    target["memory_input"]["lessons"][0]["run_id"] = find(base, "BATCH-b", 6, "EXP-01", "TEXT_HISTORY")[
        "run_id"
    ]
    with pytest.raises(ValueError, match="procedencia"):
        analyze(base, PRIVATE)
    base = campaign()
    find(base, "BATCH-a", 6, "EXP-07", "TEXT_HISTORY")["memory_input"]["lessons"][0]["receipt_sha256"] = "x"
    with pytest.raises(ValueError, match="procedencia"):
        analyze(base, PRIVATE)


def _mutated(batch, seed, task, mode, change):
    base = campaign()
    change(find(base, batch, seed, task, mode))
    return base


@pytest.mark.parametrize(
    ("receipts", "message"),
    [
        (
            _mutated(
                "BATCH-a", 1, "EXP-04", "NO_MEMORY", lambda r: r["retrieval"]["memories"].append({"id": "m"})
            ),
            "NO_MEMORY con memoria",
        ),
        (
            _mutated(
                "BATCH-b",
                7,
                "EXP-06",
                "TEXT_HISTORY",
                lambda r: r["retrieval"]["memories"].append({"id": "x"}),
            ),
            "recuperación fuera",
        ),
        (
            _mutated("BATCH-b", 7, "EXP-06", "TEXT_HISTORY", lambda r: r.update(result="ERROR")),
            "resultado ERROR",
        ),
        (
            _mutated("BATCH-a", 5, "EXP-03", "NO_MEMORY", lambda r: r.update(agent="bounded-ast-repair-v1")),
            "solo recibos",
        ),
        (
            _mutated("BATCH-a", 5, "EXP-03", "NO_MEMORY", lambda r: r["decision"].pop("policy")),
            "solo recibos",
        ),
        (_mutated("BATCH-a", 5, "EXP-04", "NO_MEMORY", lambda r: r.update(split="train")), "particiones"),
    ],
    ids=["no-memory-with-memory", "retrieval-outside-memory", "error", "agent", "policy", "split"],
)
def test_ineligible_memory_errors_other_policies_and_splits_are_rejected(receipts, message):
    with pytest.raises(ValueError, match=message):
        analyze(receipts, PRIVATE)


# --- lecturas pre-registradas sobre la campaña completa --------------------------------------


def readings(mode, task, seed):
    if mode == "NO_MEMORY" or task in TRAIN:
        return seed in (1, 4)
    if mode == "TEXT_HISTORY":
        return seed in ((1, 4, 5) if task in ORIGINAL else (1,))
    return seed in (1, 4) or (task in ("EXP-04", "EXP-05") and seed == 5)


def test_each_reading_is_reachable_with_exact_counts_and_kinds_never_pooled():
    report = analyze(campaign(readings), PRIVATE)
    original = report["kinds"]["original"]["comparisons"]["TEXT_HISTORY"]
    assert original["FirstAttemptSuccess"] == {"value": 9 / 18, "numerator": 9, "denominator": 18}
    assert original["FirstAttemptSuccess_NO_MEMORY"]["numerator"] == 6
    assert original["FirstAttemptDifference"] == {"runs": 3, "rate": 3 / 18}
    assert report["verdicts"] == {
        "original/TEXT_HISTORY": "aporta",  # +3
        "original/ASSOCIATIVE_MEMORY": "sin diferencia",  # +2
        "misleading/TEXT_HISTORY": "perjudica",  # -3
        "misleading/ASSOCIATIVE_MEMORY": "sin diferencia",  # 0
    }


def test_nulls_by_construction_are_marked_and_headroom_keeps_all_18_pairs():
    def status(task):
        return "decisive" if task == "EXP-04" else "partial"

    comparison = analyze(campaign(status=status), PRIVATE)["kinds"]["original"]["comparisons"]
    history = comparison["TEXT_HISTORY"]
    assert history["pairs"] == 18
    # EXP-04 decisivo: primer intento forzado; nulo por construcción solo si ese intento tuvo éxito.
    assert history["pair_classes"] == {"null_by_construction": 2, "null_observed": 16}
    assert history["headroom"]["first_action_forced"] == 6
    assert history["headroom"]["diagnostic_status"] == {"decisive": 6, "partial": 12}
    between = comparison["ASSOCIATIVE_MEMORY_vs_TEXT_HISTORY"]
    assert between["pair_classes"] == {"null_by_construction": 18}  # planes iguales observados
    assert between["headroom"]["plan_identical"] == 18


def test_inconsistent_replicates_invalidate_every_verdict():
    base = campaign()
    replica = find(base, "BATCH-b", 1, "EXP-04", "TEXT_HISTORY")
    replica["outcome"] = {**replica["outcome"], "first_attempt_success": False}
    report = analyze(base, PRIVATE)
    assert report["replicates_consistent"] is False
    assert set(report["verdicts"].values()) == {"inválido"}


# --- helpers por separado -------------------------------------------------------------------


def pair_run(success, first, iterations, plan=PRIOR, status="partial", proposal=None):
    return {
        "outcome": {"success": success, "first_attempt_success": first},
        "iterations": iterations,
        "decision": {"plan": plan, "diagnostic": {"status": status}, "memory_proposal": proposal},
        "task": {"id": "T"},
        "seed": 1,
    }


def test_classify_puts_success_before_iterations():
    assert classify(pair_run(False, False, 3), pair_run(True, False, 3)) == "negative"
    assert classify(pair_run(True, False, 3), pair_run(False, False, 3)) == "positive"
    assert classify(pair_run(True, True, 1), pair_run(True, False, 2)) == "positive"
    assert classify(pair_run(True, False, 3, proposal="p"), pair_run(True, False, 2)) == "negative"


def test_classify_marks_nulls_by_construction_only_when_forced():
    reversed_plan = PRIOR[::-1]
    assert (
        classify(pair_run(True, False, 2, proposal="p"), pair_run(True, False, 2)) == "null_by_construction"
    )
    forced = pair_run(True, True, 1, plan=reversed_plan, status="decisive", proposal="p")
    assert classify(forced, pair_run(True, True, 1, status="decisive")) == "null_by_construction"
    free = pair_run(True, True, 1, plan=reversed_plan, proposal="p")
    assert classify(free, pair_run(True, True, 1)) == "null_observed"


def test_compare_rejects_a_missing_pair_and_verdict_needs_pairs():
    with pytest.raises(ValueError, match="par sin NO_MEMORY"):
        compare([pair_run(True, True, 1)], {}, "NO_MEMORY")
    empty = compare([], {}, "NO_MEMORY")
    assert empty["FirstAttemptSuccess"]["value"] is None
    assert verdict(empty, consistent=True) == "inválido"


def sealed(tmp_path, record, name=None):
    from experiments.evidence import digest

    path = tmp_path / ((name or record["run_id"]) + ".json")
    path.write_text(json.dumps({**record, "receipt_sha256": digest(record)}), encoding="utf-8")
    return path


def header(**changes):
    from experiments.evidence import RECEIPT_SCHEMA, SOURCE_HASH_NORMALIZATION

    record = {"schema_id": RECEIPT_SCHEMA, "source_hash_normalization": SOURCE_HASH_NORMALIZATION}
    return {**record, "run_id": "RUN-a", "kind": "memory_update", **changes}


def test_load_verifies_seals_with_stdlib_and_cites_generated_from(tmp_path):
    path = sealed(tmp_path, header(note="ñandú"))  # canonical JSON keeps non-ASCII text
    receipts, generated_from = load(tmp_path)
    assert generated_from == {"RUN-a.json": receipts[0]["receipt_sha256"]}
    tampered = json.loads(path.read_text("utf-8"))
    tampered["note"] = "otra"
    path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(ValueError, match="sello"):
        load(tmp_path)


@pytest.mark.parametrize(
    "change",
    [
        {"schema_id": "software-learning-receipt/v1"},
        {"source_hash_normalization": "checkout-bytes/v0"},
        {"run_id": "RUN-other"},  # el nombre del archivo debe ser el run_id sellado
    ],
)
def test_load_rejects_other_schemas_and_misnamed_receipts(tmp_path, change):
    sealed(tmp_path, header(**change), name="RUN-a")
    with pytest.raises(ValueError, match=r"esquema|nombre del archivo"):
        load(tmp_path)


def test_load_rejects_an_unsealed_receipt(tmp_path):
    (tmp_path / "RUN-a.json").write_text(json.dumps(header()), encoding="utf-8")
    with pytest.raises(ValueError, match="sello"):
        load(tmp_path)


def test_script_constants_match_the_declared_campaign_and_it_imports_only_stdlib():
    from experiments.benchmark import DIAGNOSTIC_CAMPAIGN, TASK_SETS
    from experiments.diagnostic import AGENT_NAME
    from experiments.diagnostic import POLICY as DIAGNOSTIC_POLICY
    from experiments.evidence import RECEIPT_SCHEMA, SOURCE_HASH_NORMALIZATION

    assert DIAGNOSTIC_CAMPAIGN["seeds"] == analysis.SEEDS
    assert DIAGNOSTIC_CAMPAIGN["replicates"] == analysis.REPLICATES
    assert TASK_SETS[DIAGNOSTIC_CAMPAIGN["task_set"]] == analysis.TASKS
    assert analysis.AGENT == AGENT_NAME == DIAGNOSTIC_CAMPAIGN["agent"]
    assert analysis.POLICY == DIAGNOSTIC_POLICY
    assert (analysis.RECEIPT_SCHEMA, analysis.NORMALIZATION) == (RECEIPT_SCHEMA, SOURCE_HASH_NORMALIZATION)
    tree = ast.parse(inspect.getsource(analysis))
    imported = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    imported |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    stdlib = {
        "__future__",
        "argparse",
        "collections",
        "hashlib",
        "itertools",
        "json",
        "pathlib",
        "sys",
        "typing",
    }
    assert imported <= stdlib
