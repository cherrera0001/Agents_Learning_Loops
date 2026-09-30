"""Análisis pre-registrado de H6 (#63): validación cerrada de la campaña, métricas y cada lectura.

``analyze`` solo se ejercita sobre campañas sintéticas **completas** con la forma declarada (2 réplicas
× 6 semillas × 4 condiciones × (9 + 6) ejecuciones = 720 ``task_run``, 72 ``memory_update`` de lecciones y
uno de fallos por ejecución de A_N o C_N con intentos fallidos). Un simulador determinista genera los
recibos: cada tarea tiene un operador correcto, cada semilla una permutación del prior, y la memoria de
fallos aplica solo entre tareas de un mismo grupo de firma. Las lecturas se alcanzan eligiendo grupos,
propuestas de lección o planes; ningún test exige que la memoria de fallos gane.
"""

import ast
import copy
import inspect
import itertools
import json

import pytest

from experiments.evidence import RECEIPT_SCHEMA, SOURCE_HASH_NORMALIZATION, digest
from scripts import analyze_failure_memory as analysis
from scripts.analyze_failure_memory import AGENT, POLICY, STORE, analyze, displaced, load

TASKS = [f"EXP-{i:02d}" for i in range(1, 10)]
TRAIN, ORIGINAL, MISLEADING = TASKS[:3], TASKS[3:6], TASKS[6:]
SEEDS = (1, 4, 5, 6, 7, 9)
BATCHES = ("BATCH-a", "BATCH-b")
CONDITIONS = ("A", "A_N", "C", "C_N")
MODE = {"A": "NO_MEMORY", "A_N": "NO_MEMORY", "C": "ASSOCIATIVE_MEMORY", "C_N": "ASSOCIATIVE_MEMORY"}
ENABLED = {"A_N", "C_N"}
ID, ENV, STO = "validate_optional_identity", "normalize_environment", "initialize_storage"
PRIORS = dict(zip(SEEDS, itertools.permutations((ID, ENV, STO)), strict=True))
CORRECT = dict(zip(TASKS, [ID, ENV, STO] * 3, strict=True))
DECOY = dict(zip(MISLEADING, [STO, ID, ENV], strict=True))
PRIVATE = {t: {"family": f} for t, f in zip(TASKS, ["auth", "config", "ready"] * 3, strict=True)}
for _task, _decoy in zip(MISLEADING, ["ready", "auth", "config"], strict=True):
    PRIVATE[_task]["decoy_family"] = _decoy
SEQUENCE = [(t, 1) for t in TASKS] + [(t, 2) for t in TASKS[3:]]


def correct_first(task, prior):
    return [CORRECT[task]] + [s for s in prior if s != CORRECT[task]]


def simulate(group=None, proposal=None, override=None):
    """Campaña sintética con la forma de ``run --campaign failure-memory-v1``.

    ``group``: tarea → grupo de firma (por defecto, cada tarea el suyo: solo aplican registros propios).
    ``proposal``: tarea de transferencia → estrategia que propone la lección en C y C_N (por defecto la
    correcta en las originales y el señuelo en las engañosas). ``override(cond, pass, task, seed, plan)``
    puede sustituir el plan de una ejecución (``None`` = sin cambio).
    """
    group = {t: t for t in TASKS} | (group or {})
    proposal = {**{t: CORRECT[t] for t in ORIGINAL}, **DECOY} | (proposal or {})
    receipts = []
    for batch, seed, cond in itertools.product(BATCHES, SEEDS, CONDITIONS):
        records, lessons, origin_task = [], [], {}
        for task, number in SEQUENCE:
            run_id = f"RUN-{batch}-{seed}-{cond}-{number}-{task}"
            prior = list(PRIORS[seed])
            wants = proposal.get(task) if MODE[cond] != "NO_MEMORY" and task not in TRAIN else None
            base = sorted(prior, key=lambda op, p=wants: (op != p, prior.index(op)))
            signature = [{"outcome": "ERROR", "exception": group[task], "none_marker": False}]
            applied = [x for x in records if x["signature"] == signature] if cond in ENABLED else []
            failed = {x["strategy"] for x in applied}
            plan = sorted(prior, key=lambda op, p=wants, f=failed: (op in f, op != p, prior.index(op)))
            plan = (override and override(cond, number, task, seed, plan)) or plan
            if cond not in ENABLED:
                base = plan
            effect = "none" if not applied else "no_change" if plan[0] == base[0] else "changed_first"
            attempts = plan[: plan.index(CORRECT[task]) + 1]
            exposed = [{"id": lessons[0]["id"], "task": lessons[0]["task"]}] if wants and lessons else []
            record = {
                "schema_id": RECEIPT_SCHEMA,
                "source_hash_normalization": SOURCE_HASH_NORMALIZATION,
                "kind": "task_run",
                "run_id": run_id,
                "agent": AGENT,
                "batch_id": batch,
                "seed": seed,
                "task": {"id": task, "title": "title " + task, "context": "context"},
                "memory_mode": MODE[cond],
                "condition": cond,
                "pass": number,
                "split": "train" if task in TRAIN else "transfer",
                "result": "PASS",
                "memory_input": None if MODE[cond] == "NO_MEMORY" else {"lessons": copy.deepcopy(lessons)},
                "retrieval": {"memories": exposed},
                "decision": {
                    "policy": POLICY,
                    "plan": plan,
                    "memory_ids": [m["id"] for m in exposed],
                    "diagnostic": {"status": "partial", "features": signature},
                    "plan_without_failures": base,
                    "failure_scope": [],
                    "failure_ids": [x["id"] for x in applied],
                    "failure_strategies": sorted(failed),
                    "failure_effect": effect,
                },
                "failure_memory_input": copy.deepcopy(records) if cond in ENABLED else [],
                "failure_origins": [
                    {"id": x["id"], "origin": "same_task" if origin_task[x["id"]] == task else "other_task"}
                    for x in applied
                ],
                "iterations": len(attempts),
                "duration_ms": 1.0,
                "tests": [{"id": "test-0", "returncode": 1}]
                + [
                    {"id": f"test-{i}", "returncode": 0 if s == CORRECT[task] else 1}
                    for i, s in enumerate(attempts, 1)
                ],
                "actions": [{"iteration": i, "strategy": s} for i, s in enumerate(attempts, 1)],
                "outcome": {
                    "success": True,
                    "first_attempt_success": len(attempts) == 1,
                    "iterations": len(attempts),
                },
            }
            record["receipt_sha256"] = digest(record)
            receipts.append(record)
            header = {"schema_id": RECEIPT_SCHEMA, "source_hash_normalization": SOURCE_HASH_NORMALIZATION}
            if task in TRAIN and MODE[cond] != "NO_MEMORY":
                receipts.append(
                    seal(
                        {
                            **header,
                            "kind": "memory_update",
                            "run_id": "RUN-mu" + run_id[3:],
                            "source_receipt": run_id + ".json",
                        }
                    )
                )
                lessons.append(
                    {
                        "id": "lesson:" + run_id,
                        "run_id": run_id,
                        "task": task,
                        "receipt_sha256": record["receipt_sha256"],
                    }
                )
            if cond in ENABLED:
                new = [
                    {
                        "id": f"failure:{run_id}#test-{i}",
                        "strategy": s,
                        "query": "title " + task + " context",
                        "signature": signature,
                        "evidence": f"{run_id}#test-{i}",
                        "receipt_sha256": record["receipt_sha256"],
                    }
                    for i, s in enumerate(attempts, 1)
                    if s != CORRECT[task]
                ]
                if new:
                    changes = [{"action": "ADD", "memory": x["id"], "evidence": x["evidence"]} for x in new]
                    update = {
                        **header,
                        "kind": "memory_update",
                        "memory_store": STORE,
                        "run_id": "RUN-fm" + run_id[3:],
                    }
                    receipts.append(
                        seal({**update, "source_receipt": run_id + ".json", "memory_changes": changes})
                    )
                records = records + new
                origin_task.update({x["id"]: task for x in new})
    return receipts


def seal(record):
    return {**record, "receipt_sha256": digest(record)}


def runs_of(receipts):
    return [r for r in receipts if r["kind"] == "task_run"]


def find(receipts, batch, seed, cond, number, task):
    key = (batch, seed, cond, number, task)
    return next(
        r
        for r in runs_of(receipts)
        if (r["batch_id"], r["seed"], r["condition"], r["pass"], r["task"]["id"]) == key
    )


def verdicts(report):
    return {name: rule["verdict"] for name, rule in report["rules"].items()}


def repeating_seeds(task):
    """Semillas cuyo prior no empieza por el operador correcto de la tarea (4 de 6)."""
    return [s for s in SEEDS if PRIORS[s][0] != CORRECT[task]]


# --- lecturas pre-registradas -------------------------------------------------------------------


def test_the_default_simulation_is_accepted_with_exact_counts_and_supports_h6():
    receipts = simulate()
    report = analyze(receipts, PRIVATE)
    campaign = report["campaign"]
    assert (campaign["task_runs"], campaign["lesson_memory_updates"]) == (720, 72)
    assert campaign["failure_memory_updates"] == sum(r.get("memory_store") == STORE for r in receipts) > 0
    assert campaign["batches"] == list(BATCHES) and campaign["primary_batch"] == "BATCH-a"
    assert report["replicates_consistent"] and report["determinism_control"] and report["valid"]
    for p, kind, cond in itertools.product(("pass-1", "pass-2"), ("original", "misleading"), CONDITIONS):
        assert report["passes"][p][kind][cond]["runs"] == 18
    second = report["passes"]["pass-2"]
    assert second["original"]["A"]["RepeatedFirstFailure"] == {
        "value": 12 / 18,
        "numerator": 12,
        "denominator": 18,
    }
    assert second["original"]["A_N"]["RepeatedFirstFailure"]["numerator"] == 0
    assert second["misleading"]["C"]["RepeatedFirstFailure"]["numerator"] == 18  # el señuelo se repite
    assert "RepeatedFirstFailure" not in report["passes"]["pass-1"]["original"]["A"]
    applied = sum(
        len(r["failure_origins"])
        for r in runs_of(receipts)
        if (r["batch_id"], r["condition"], r["pass"]) == ("BATCH-a", "C_N", 2)
        and r["task"]["id"] in MISLEADING
    )
    assert second["misleading"]["C_N"]["applied_records"] == {"same_task": applied, "other_task": 0}
    assert applied > 0 and second["misleading"]["C_N"]["CrossTaskEffect"]["same_task_only"] == 18
    cells = report["rules"]["H6a"]["cells"]
    assert cells["C_N vs C / original"] == {
        "R_X": {"value": 0.0, "numerator": 0, "denominator": 18},
        "R_X_N": {"value": 0.0, "numerator": 0, "denominator": 18},
        "headroom": False,
        "required_max_R_X_N": 0,
        "satisfied": True,
        "null_by_construction": True,
    }
    assert (
        cells["A_N vs A / misleading"]["headroom"]
        and cells["A_N vs A / misleading"]["required_max_R_X_N"] == 9
    )
    assert verdicts(report) == {"H6a": "apoyada", "H6b": "apoyada", "H6c": "aporta"}
    assert report["rules"]["H6c"]["difference_runs"] == 18
    assert report["conclusion"] == {"verdict": "aprendió de su error sin contaminar", "failing": {}}
    assert set(report["pass1_plans_identical_to_baseline"].values()) == {18}  # sin registros ajenos (PF4)


def test_pass1_plans_that_a_foreign_record_changed_are_counted():
    report = analyze(simulate(group={"EXP-08": "EXP-01"}), PRIVATE)
    identical = report["pass1_plans_identical_to_baseline"]
    assert identical["A_N vs A / original"] == 18 and identical["A_N vs A / misleading"] < 18


def test_original_and_misleading_tasks_must_be_the_declared_ones():
    private = {**PRIVATE, "EXP-04": {**PRIVATE["EXP-04"], "decoy_family": "config"}}
    private["EXP-07"] = {k: v for k, v in PRIVATE["EXP-07"].items() if k != "decoy_family"}
    with pytest.raises(ValueError, match="particiones"):
        analyze(simulate(), private)


def keep_repeating(count, cond="A_N", kinds=(ORIGINAL,)):
    """En la pasada 2 de ``cond``, repite el primer intento de la pasada 1 en ``count`` ejecuciones."""
    chosen = set()
    for tasks in kinds:
        pairs = [(t, s) for t in tasks for s in repeating_seeds(t)]
        chosen |= set(pairs[:count])

    def override(c, number, task, seed, plan):
        if (c, number) == (cond, 2) and (task, seed) in chosen:
            return list(PRIORS[seed])
        return None

    return override


@pytest.mark.parametrize(("count", "verdict"), [(9, "apoyada"), (10, "refutada"), (12, "refutada")])
def test_h6a_requires_three_fewer_repetitions_in_a_cell_with_headroom(count, verdict):
    report = analyze(simulate(override=keep_repeating(count)), PRIVATE)
    cell = report["rules"]["H6a"]["cells"]["A_N vs A / original"]
    assert (cell["R_X"]["numerator"], cell["R_X_N"]["numerator"], cell["headroom"]) == (12, count, True)
    assert report["rules"]["H6a"]["verdict"] == verdict
    if verdict == "refutada":
        assert report["conclusion"] == {"verdict": "no concluye", "failing": {"H6a": "refutada"}}


def solved_first(cond_numbers, keep=()):
    """Plan con el operador correcto primero en las condiciones/pasadas dadas, salvo las ``keep``."""

    def override(cond, number, task, seed, plan):
        if (cond, number) in cond_numbers and (task, seed) not in keep:
            return correct_first(task, PRIORS[seed])
        return None

    return override


BASELINES = {(c, n) for c in ("A", "C") for n in (1, 2)}


def test_h6a_without_headroom_in_any_cell_is_reported_as_such():
    report = analyze(simulate(override=solved_first(BASELINES)), PRIVATE)
    cells = report["rules"]["H6a"]["cells"].values()
    assert not any(c["headroom"] for c in cells) and all(c["null_by_construction"] for c in cells)
    assert report["rules"]["H6a"]["verdict"] == "sin holgura"
    assert report["conclusion"]["failing"] == {"H6a": "sin holgura"}


@pytest.mark.parametrize(("kept", "verdict"), [(3, "apoyada"), (2, "sin holgura")])
def test_headroom_starts_at_exactly_three_of_eighteen(kept, verdict):
    keep = {("EXP-04", s) for s in repeating_seeds("EXP-04")[:kept]}
    report = analyze(simulate(override=solved_first(BASELINES, keep)), PRIVATE)
    cell = report["rules"]["H6a"]["cells"]["A_N vs A / original"]
    assert cell["R_X"]["numerator"] == kept and cell["headroom"] == (kept >= 3)
    assert report["rules"]["H6a"]["verdict"] == verdict


def test_h6b_is_refuted_by_a_cross_task_record_that_hurts():
    # EXP-08 (correcto: ENV) comparte firma con EXP-01 (correcto: ID). Con el prior [ENV, ID, STO],
    # EXP-01 falla ENV; en A_N ese registro baja ENV en EXP-08, el nuevo primer intento falla y ENV
    # acierta después: «hurt».
    report = analyze(simulate(group={"EXP-08": "EXP-01"}), PRIVATE)
    hurt = report["rules"]["H6b"]["CrossTaskEffect_hurt"]
    assert hurt["A_N / pass-1 / misleading"] > 0
    assert report["rules"]["H6b"]["FirstAttemptSuccess_original"]["pass-1"]["satisfied"]
    assert report["rules"]["H6b"]["verdict"] == "refutada"
    effect = report["passes"]["pass-1"]["misleading"]["A_N"]["CrossTaskEffect"]
    assert (
        effect["hurt"] == hurt["A_N / pass-1 / misleading"]
        and effect["cross_task"]["numerator"] >= effect["hurt"]
    )
    assert report["conclusion"]["failing"] == {"H6b": "refutada"}


def test_h6b_is_refuted_when_c_n_loses_first_attempts_on_the_originals():
    def override(cond, number, task, seed, plan):
        if (cond, number, task, seed) == ("C_N", 1, "EXP-04", 1):
            return [s for s in plan if s != CORRECT[task]] + [CORRECT[task]]
        return None

    report = analyze(simulate(override=override), PRIVATE)
    first = report["rules"]["H6b"]["FirstAttemptSuccess_original"]["pass-1"]
    assert (first["FA_C_N"]["numerator"], first["FA_C"]["numerator"], first["satisfied"]) == (17, 18, False)
    assert not any(report["rules"]["H6b"]["CrossTaskEffect_hurt"].values())
    assert report["rules"]["H6b"]["verdict"] == "refutada"


def test_h6c_reaches_each_reading():
    everything_right = {t: CORRECT[t] for t in MISLEADING}
    assert (
        analyze(simulate(proposal=everything_right), PRIVATE)["rules"]["H6c"]["verdict"] == "sin diferencia"
    )

    def worse(cond, number, task, seed, plan):  # C_N empeora en EXP-07 en la pasada 2
        if (cond, number, task) == ("C_N", 2, "EXP-07"):
            return [s for s in plan if s != CORRECT[task]] + [CORRECT[task]]
        return None

    report = analyze(simulate(proposal=everything_right, override=worse), PRIVATE)
    assert (report["rules"]["H6c"]["difference_runs"], report["rules"]["H6c"]["verdict"]) == (-6, "perjudica")
    keep = {("EXP-07", s) for s in SEEDS[:3]}  # C acierta en 15 de 18; C_N en 18
    report = analyze(simulate(override=solved_first({("C", 1), ("C", 2)}, keep)), PRIVATE)
    assert (report["rules"]["H6c"]["difference_runs"], report["rules"]["H6c"]["verdict"]) == (3, "aporta")


def test_inconsistent_replicates_or_a_failed_determinism_control_invalidate_every_verdict():
    receipts = simulate()
    replica = find(receipts, "BATCH-b", 4, "C_N", 2, "EXP-05")
    replica["outcome"] = {**replica["outcome"], "iterations": 9}
    report = analyze(receipts, PRIVATE)
    assert report["replicates_consistent"] is False and report["valid"] is False
    assert set(verdicts(report).values()) == {"inválido"}
    assert report["conclusion"] == {"verdict": "inválido", "failing": {}}

    def drift(cond, number, task, seed, plan):  # A cambia entre pasadas sin memoria nueva
        return correct_first(task, PRIORS[seed]) if (cond, number, task) == ("A", 2, "EXP-06") else None

    report = analyze(simulate(override=drift), PRIVATE)
    assert report["replicates_consistent"] and report["determinism_control"] is False
    assert set(verdicts(report).values()) == {"inválido"}


def run(tests, plan_without_failures, strategies):
    return {
        "tests": [{"returncode": 1}] + [{"returncode": code} for code in tests],
        "actions": [{"strategy": s} for s in strategies],
        "decision": {"plan_without_failures": plan_without_failures},
    }


def test_displaced_attempts_are_compared_within_the_same_run():
    assert displaced(run([1, 0], [ID, ENV, STO], [ENV, ID])) == ("hurt", False)
    assert displaced(run([1, 1, 0], [ID, ENV, STO], [ENV, ID, STO])) == ("neutral", False)
    assert displaced(run([1, 0], [ID, ENV, STO], [ENV, STO])) == (
        "neutral",
        True,
    )  # el desplazado no se probó
    # Si el nuevo primer intento acierta, la ejecución termina y el desplazado nunca se prueba:
    assert displaced(run([0], [ID, ENV, STO], [ENV])) == ("neutral", True)
    # «helped» solo es alcanzable si el desplazado se probó y falló tras un acierto, lo que el runner
    # no produce (pre-registro, sección 5); la función lo clasifica igual.
    assert displaced(run([0, 1], [ID, ENV, STO], [ENV, ID])) == ("helped", False)


# --- validación cerrada de la campaña -----------------------------------------------------------


def _without(predicate, receipts=None):
    return [r for r in (receipts or simulate()) if not predicate(r)]


DECLARED = "no es la campaña declarada"


@pytest.mark.parametrize(
    ("receipts", "message"),
    [
        (_without(lambda r: "BATCH-b" in r["run_id"]), "réplicas"),
        (
            _without(lambda r: r["run_id"] == "RUN-BATCH-a-5-C_N-2-EXP-09"),
            DECLARED,
        ),  # una celda de la pasada 2
        (_without(lambda r: r["kind"] == "task_run" and r["pass"] == 2 and r["condition"] == "A"), DECLARED),
        (_without(lambda r: r["run_id"] == "RUN-mu-BATCH-a-4-C-1-EXP-02"), "memory_update de lecciones"),
        (_without(lambda r: r["run_id"].startswith("RUN-fm-BATCH-b-7-A_N")), "memory_update de fallos"),
    ],
    ids=["replicate", "pass-2-cell", "pass-2-condition", "lesson-update", "failure-update"],
)
def test_missing_parts_are_rejected(receipts, message):
    with pytest.raises(ValueError, match=message):
        analyze(receipts, PRIVATE)


def renamed(r, **changes):
    r = copy.deepcopy(r)
    r.update(changes)
    r["run_id"] = f"RUN-{r['batch_id']}-{r['seed']}-{r['condition']}-{r['pass']}-{r['task']['id']}-copy"
    return r


def test_duplicates_unexpected_seeds_passes_and_batches_are_rejected():
    base = simulate()
    cell = find(base, "BATCH-a", 5, "A", 1, "EXP-04")
    for receipts, message in (
        ([*base, renamed(cell)], "celda duplicada"),
        ([*base, renamed(cell, seed=2)], DECLARED),
        ([*base, renamed(find(base, "BATCH-a", 5, "A", 1, "EXP-01"), **{"pass": 2})], DECLARED),
        (
            [*base, *(renamed(r, batch_id="BATCH-c") for r in runs_of(base) if r["batch_id"] == "BATCH-a")],
            "réplicas",
        ),
    ):
        with pytest.raises(ValueError, match=message):
            analyze(receipts, PRIVATE)


def _mutated(change, batch="BATCH-a", seed=4, cond="A_N", number=2, task="EXP-05"):
    receipts = simulate()
    change(find(receipts, batch, seed, cond, number, task), receipts)
    return receipts


def _donor(receipts, cond="A_N"):
    return copy.deepcopy(find(receipts, "BATCH-a", 4, cond, 2, "EXP-05")["failure_memory_input"][0])


def _cite(field_value):
    def change(r, receipts):
        record = r["failure_memory_input"][0]
        record.update(field_value(record, receipts))

    return change


def _passing_attempt(record, receipts):
    source_id = record["evidence"].partition("#")[0]
    source = next(x for x in runs_of(receipts) if x["run_id"] == source_id)
    passing = source["tests"][-1]["id"]
    return {"evidence": f"{source_id}#{passing}", "id": f"failure:{source_id}#{passing}"}


@pytest.mark.parametrize(
    ("change", "kwargs", "message"),
    [
        (
            lambda r, rs: r["failure_memory_input"].append(_donor(rs)),
            {"cond": "A"},
            "A con memoria de fallos",
        ),
        (
            lambda r, rs: r["decision"]["failure_ids"].append("failure:x"),
            {"cond": "C"},
            "C con memoria de fallos",
        ),
        (_cite(_passing_attempt), {}, "no cita un intento fallido"),
        (
            _cite(lambda rec, rs: {"evidence": rec["evidence"].partition("#")[0] + "#test-0"}),
            {},
            "no cita un intento",
        ),
        (
            _cite(
                lambda rec, rs: {"evidence": find(rs, "BATCH-a", 4, "A_N", 2, "EXP-09")["run_id"] + "#test-1"}
            ),
            {},
            "no anterior",
        ),
        (
            _cite(
                lambda rec, rs: {"evidence": find(rs, "BATCH-a", 4, "C_N", 1, "EXP-01")["run_id"] + "#test-1"}
            ),
            {},
            "otra celda",
        ),
        (_cite(lambda rec, rs: {"strategy": "otra"}), {}, "no coincide con su recibo"),
        (_cite(lambda rec, rs: {"receipt_sha256": "x"}), {}, "no coincide con su recibo"),
        (lambda r, rs: r["failure_memory_input"].pop(), {}, "no es la de los intentos fallidos"),
        (
            lambda r, rs: r["failure_origins"].reverse() or r["failure_origins"].append({"id": "x"}),
            {},
            "orígenes",
        ),
    ],
    ids=[
        "records-in-a",
        "applied-in-c",
        "cites-passing-attempt",
        "cites-test-0",
        "later-run",
        "other-condition",
        "strategy",
        "seal",
        "incomplete",
        "origins",
    ],
)
def test_failure_records_must_cite_real_earlier_failed_attempts(change, kwargs, message):
    with pytest.raises(ValueError, match=message):
        analyze(_mutated(change, **kwargs), PRIVATE)


def test_failure_updates_must_derive_from_their_run_and_exist_only_for_a_n_and_c_n():
    receipts = simulate()
    update = next(u for u in receipts if u.get("memory_store") == STORE)
    update["memory_changes"] = [*update["memory_changes"][:-1], {"evidence": "x"}]
    with pytest.raises(ValueError, match="no deriva de su recibo"):
        analyze(receipts, PRIVATE)
    receipts = simulate()
    source = find(receipts, "BATCH-a", 1, "A", 1, "EXP-02")
    extra = {"kind": "memory_update", "memory_store": STORE, "run_id": "RUN-fm-extra", "memory_changes": []}
    with pytest.raises(ValueError, match="memory_update de fallos"):
        analyze([*receipts, {**extra, "source_receipt": source["run_id"] + ".json"}], PRIVATE)
    with pytest.raises(ValueError, match="memoria no prevista"):
        analyze([*receipts, {**extra, "memory_store": "other"}], PRIVATE)


@pytest.mark.parametrize(
    ("change", "kwargs", "message"),
    [
        (
            lambda r, rs: r["memory_input"]["lessons"].append(
                {"run_id": find(rs, "BATCH-a", 4, "C", 1, "EXP-01")["run_id"], "receipt_sha256": "?"}
            ),
            {"cond": "C_N"},
            "lección fuera de procedencia",
        ),
        (lambda r, rs: r["memory_input"]["lessons"].pop(), {"cond": "C_N"}, "no congelada"),
        (
            lambda r, rs: r["memory_input"]["lessons"][0].update(receipt_sha256="x"),
            {"cond": "C"},
            "procedencia",
        ),
        (
            lambda r, rs: r["retrieval"]["memories"].append({"id": "m", "task": "EXP-01"}),
            {"cond": "A"},
            "con lecciones",
        ),
        (
            lambda r, rs: r["retrieval"]["memories"].append({"id": "m", "task": "EXP-01"}),
            {"cond": "C"},
            "recuperación fuera",
        ),
    ],
    ids=["lesson-from-c", "not-frozen", "seal", "retrieval-in-a", "retrieval-outside"],
)
def test_lessons_follow_their_condition_and_stay_frozen_after_training(change, kwargs, message):
    with pytest.raises(ValueError, match=message):
        analyze(_mutated(change, **kwargs), PRIVATE)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda r, rs: r.update(agent="bounded-ast-repair-v1+diagnostic-v1"), "solo recibos"),
        (lambda r, rs: r["decision"].update(policy="diagnostic-baseline/v1"), "solo recibos"),
        (lambda r, rs: r.update(result="ERROR"), "resultado ERROR"),
        (lambda r, rs: r.pop("failure_origins"), "sin los campos"),
        (lambda r, rs: r["decision"].pop("failure_effect"), "sin los campos"),
        (lambda r, rs: r.update(memory_mode="ASSOCIATIVE_MEMORY"), "no concuerda con el modo"),
        (lambda r, rs: r.update(condition="B"), "condición desconocida"),
        (lambda r, rs: r.update(**{"pass": 3}), "pasada"),
        (lambda r, rs: r["decision"].update(failure_effect="maybe"), "efecto"),
        (lambda r, rs: r.update(split="train"), "particiones"),
    ],
    ids=[
        "agent",
        "policy",
        "error",
        "record-field",
        "decision-field",
        "mode",
        "condition",
        "pass",
        "effect",
        "split",
    ],
)
def test_other_agents_errors_and_malformed_receipts_are_rejected(change, message):
    with pytest.raises(ValueError, match=message):
        analyze(_mutated(change), PRIVATE)


def test_unknown_receipt_kinds_are_rejected():
    with pytest.raises(ValueError, match="tipo no previsto"):
        analyze([*simulate(), {"kind": "other"}], PRIVATE)


# --- carga sellada, constantes y salida ---------------------------------------------------------


def write(tmp_path, receipts):
    for r in receipts:
        (tmp_path / (r["run_id"] + ".json")).write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")


def test_main_is_deterministic_and_cites_every_sealed_receipt(tmp_path, monkeypatch, capsys):
    receipts = simulate()
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    write(evidence, receipts)
    monkeypatch.setattr(analysis, "annotations", lambda root: PRIVATE)
    outputs = []
    for _ in range(2):
        monkeypatch.setattr("sys.argv", ["analyze", "--root", str(tmp_path), "--evidence", "evidence"])
        analysis.main()
        outputs.append(capsys.readouterr().out)
    assert outputs[0] == outputs[1]
    report = json.loads(outputs[0])
    assert report["generated_from"] == {r["run_id"] + ".json": r["receipt_sha256"] for r in receipts}
    assert report["conclusion"]["verdict"] == "aprendió de su error sin contaminar"


def test_load_verifies_seals_schemas_and_names(tmp_path):
    record = seal(
        {
            "schema_id": RECEIPT_SCHEMA,
            "source_hash_normalization": SOURCE_HASH_NORMALIZATION,
            "run_id": "RUN-a",
            "kind": "memory_update",
            "note": "ñandú",
        }
    )
    write(tmp_path, [record])
    loaded, generated_from = load(tmp_path)
    assert generated_from == {"RUN-a.json": record["receipt_sha256"]} and loaded == [record]
    (tmp_path / "RUN-a.json").write_text(json.dumps({**record, "note": "otra"}), encoding="utf-8")
    with pytest.raises(ValueError, match="sello"):
        load(tmp_path)
    for change, message in (
        ({"schema_id": "software-learning-receipt/v1"}, "esquema"),
        ({"run_id": "RUN-b"}, "nombre del archivo"),
    ):
        bad = {k: v for k, v in record.items() if k != "receipt_sha256"} | change
        (tmp_path / "RUN-a.json").write_text(json.dumps(seal(bad)), encoding="utf-8")
        with pytest.raises(ValueError, match=message):
            load(tmp_path)


def test_script_constants_match_the_declared_campaign_and_it_imports_only_stdlib():
    from experiments.benchmark import FAILURE_MEMORY_CAMPAIGN, TASK_SETS
    from experiments.evidence import RECEIPT_SCHEMA as SCHEMA
    from experiments.failure_memory import AGENT_NAME, CONDITIONS
    from experiments.failure_memory import POLICY as FAILURE_POLICY
    from experiments.failure_memory import STORE as FAILURE_STORE

    campaign = FAILURE_MEMORY_CAMPAIGN
    assert (campaign["seeds"], campaign["replicates"]) == (analysis.SEEDS, analysis.REPLICATES)
    assert TASK_SETS[campaign["task_set"]] == analysis.TASKS
    assert (campaign["train"], campaign["transfer"]) == (analysis.TRAIN, analysis.TRANSFER)
    assert campaign["passes"] == len(analysis.PASSES) and campaign["conditions"] == tuple(analysis.CONDITIONS)
    assert analysis.CONDITIONS == CONDITIONS
    assert analysis.AGENT == AGENT_NAME == campaign["agent"]
    assert (analysis.POLICY, analysis.STORE) == (FAILURE_POLICY, FAILURE_STORE)
    assert (analysis.RECEIPT_SCHEMA, analysis.NORMALIZATION) == (SCHEMA, SOURCE_HASH_NORMALIZATION)
    assert analysis.MARGIN == 3 and analysis.RUNS_PER_CELL == 18
    tree = ast.parse(inspect.getsource(analysis))
    imported = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    imported |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert imported <= {
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
