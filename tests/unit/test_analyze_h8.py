"""Análisis pre-registrado de H8 (#98): validez de la campaña, métricas y cada veredicto.

``analyze`` solo se ejercita sobre campañas sintéticas **completas** con la forma declarada (2 réplicas × 6
semillas × 4 condiciones × 9 tareas = 432 ``task_run`` y 108 ``memory_update``) y sobre una referencia
sintética con la forma de ``evidence/reference-v2`` (2 réplicas × 6 semillas × 3 condiciones × 9 tareas). Un
simulador determinista genera los recibos: cada tarea tiene un operador correcto, cada semilla una permutación
del prior, el historial y la asociativa léxica citan la lección correcta en las originales y la del señuelo en
las engañosas, y ``seeded`` elige qué lección expone C_S. Los veredictos se alcanzan eligiendo esa lección;
ningún test exige que H8 gane.
"""

import ast
import copy
import inspect
import itertools
import json
import sys

import pytest

from experiments.agent import BoundedRepairAgent
from experiments.benchmark import NONLEXICAL_SEED_CAMPAIGN
from experiments.evidence import RECEIPT_SCHEMA, SOURCE_HASH_NORMALIZATION, digest
from experiments.nonlexical_seed import AGENT_NAME, DECISION_INPUTS, TraceSeedRepairAgent
from experiments.nonlexical_seed import CONDITIONS as EXPERIMENT_CONDITIONS
from experiments.trace_seed import EMPTY, SEEDED, TIE
from experiments.trace_seed import POLICY as EXPERIMENT_POLICY
from scripts import analyze_h8 as analysis
from scripts.analyze_h8 import (
    AGENT,
    CONDITIONS,
    IMPROVES,
    NO_DIFFERENCE,
    NOT_ABOVE_CONTROLS,
    POLICY,
    REFERENCE_AGENT,
    VERDICTS,
    WORSE,
    analyze,
    decide,
    first_attempt_reading,
    load,
    selection_met,
)

TASKS = [f"EXP-{i:02d}" for i in range(1, 10)]
TRAIN, ORIGINAL, MISLEADING = TASKS[:3], TASKS[3:6], TASKS[6:]
SEEDS = (1, 4, 5, 6, 7, 9)
BATCHES = ("BATCH-a", "BATCH-b")
ID, ENV, STO = "validate_optional_identity", "normalize_environment", "initialize_storage"
PRIORS = dict(zip(SEEDS, itertools.permutations((ID, ENV, STO)), strict=True))
CORRECT = dict(zip(TASKS, [ID, ENV, STO] * 3, strict=True))
FAMILY = dict(zip(TASKS, ["auth", "config", "ready"] * 3, strict=True))
PRIVATE = {t: {"family": f} for t, f in FAMILY.items()}
for _task, _decoy in zip(MISLEADING, ["ready", "auth", "config"], strict=True):
    PRIVATE[_task]["decoy_family"] = _decoy
LESSON_OF = {"auth": "EXP-01", "config": "EXP-02", "ready": "EXP-03"}
MODES = {"A": "NO_MEMORY", "B": "TEXT_HISTORY", "C_L": "ASSOCIATIVE_MEMORY"}
HEADER = {"schema_id": RECEIPT_SCHEMA, "source_hash_normalization": SOURCE_HASH_NORMALIZATION}


def correct_lesson(task):
    return LESSON_OF[FAMILY[task]]


def decoy_lesson(task):
    return LESSON_OF[PRIVATE[task]["decoy_family"]]


def other_lesson(task):
    return next(t for t in TRAIN if t not in (correct_lesson(task), decoy_lesson(task)))


def lexical(task):
    """La lección que citan el historial y la asociativa léxica: correcta en las originales, señuelo en
    las engañosas (lo que publicó H4)."""
    return correct_lesson(task) if task in ORIGINAL else decoy_lesson(task)


def seal(record):
    return {**record, "receipt_sha256": digest(record)}


def task_run(run_id, batch, seed, mode, task, lessons, exposed, cited, extra):
    """Una ejecución: ``exposed`` y ``cited`` son tareas de origen de lecciones de ``lessons``."""
    by_task = {x["task"]: x for x in lessons}
    prior = list(PRIORS[seed])
    strategy = CORRECT[cited] if cited else None
    plan = [strategy, *(s for s in prior if s != strategy)] if strategy else prior
    attempts = plan[: plan.index(CORRECT[task]) + 1]
    record = {
        **HEADER,
        "kind": "task_run",
        "run_id": run_id,
        "batch_id": batch,
        "seed": seed,
        "task": {"id": task},
        "memory_mode": mode,
        "split": "train" if task in TRAIN else "transfer",
        "result": "PASS",
        "memory_input": None if mode == "NO_MEMORY" else {"lessons": copy.deepcopy(lessons)},
        "retrieval": {"memories": [{"id": by_task[t]["id"], "task": t} for t in exposed]},
        "decision": {
            "considered": prior,
            "selected": plan[0],
            "plan": plan,
            "without_memory": prior[0],
            "influenced_by_memory": plan != prior,
            "memory_ids": [by_task[cited]["id"]] if cited else [],
            "initial_hypothesis": "rule of " + plan[0],
        },
        "iterations": len(attempts),
        "outcome": {
            "success": True,
            "first_attempt_success": len(attempts) == 1,
            "iterations": len(attempts),
        },
    }
    extra(record)
    return seal(record)


def sequence(batch, seed, name, mode, chooser, extra):
    """Entrenamiento y transferencia de una (lote, semilla, condición): recibos y ``memory_update``."""
    receipts, lessons = [], []
    for task in TASKS:
        run_id = f"RUN-{batch}-{seed}-{name}-{task}"
        exposed, cited = chooser(task, lessons)
        record = task_run(
            run_id, batch, seed, mode, task, lessons, exposed, cited, lambda r, t=task: extra(r, t)
        )
        receipts.append(record)
        if task in TRAIN and mode != "NO_MEMORY":
            update = {**HEADER, "kind": "memory_update", "run_id": "RUN-mu" + run_id[3:]}
            receipts.append(seal({**update, "source_receipt": run_id + ".json"}))
            lessons.append(
                {
                    "id": "lesson:" + run_id,
                    "run_id": run_id,
                    "task": task,
                    "receipt_sha256": record["receipt_sha256"],
                }
            )
    return receipts


def control_chooser(mode):
    def choose(task, lessons):
        if mode == "NO_MEMORY" or task in TRAIN:
            return ([x["task"] for x in lessons] if mode == "TEXT_HISTORY" else []), None
        cited = lexical(task)
        return (list(TRAIN) if mode == "TEXT_HISTORY" else [cited]), cited

    return choose


def block_for(condition, task, state=None, lesson=None, seeds=None):
    return {
        "policy": POLICY,
        "signal": CONDITIONS[condition][1],
        "components": [{"component": f"app/{FAMILY[task]}.py", "weight": 1.0}],
        "seeds": seeds,
        "state": state,
        "lesson": lesson,
    }


def simulate(seeded=None, alter=None):
    """Campaña sintética con la forma de ``run --campaign nonlexical-seed-v1``.

    ``seeded(task, seed, batch)``: la tarea de origen de la lección que expone C_S en una tarea de
    transferencia, ``"tie"`` o ``None`` (ninguna semilla); por defecto la señal calla siempre.
    ``alter(record)`` modifica un ``task_run`` antes de sellarlo.
    """
    seeded = seeded or (lambda task, seed, batch: None)
    receipts = []
    for batch, seed, condition in itertools.product(BATCHES, SEEDS, CONDITIONS):
        mode = CONDITIONS[condition][0]

        def trace_chooser(task, lessons, seed=seed, batch=batch):
            choice = None if task in TRAIN else seeded(task, seed, batch)
            return ([choice], choice) if choice in TRAIN else ([], None)

        def extra(record, task, condition=condition, seed=seed, batch=batch):
            record.update(agent=AGENT, condition=condition, decision_inputs=copy.deepcopy(DECISION_INPUTS))
            record["decision"]["policy"] = POLICY
            block = block_for(condition, task)
            if condition == "C_S":
                choice = None if task in TRAIN else seeded(task, seed, batch)
                memories = record["retrieval"]["memories"]
                nodes = [m["id"].replace("lesson:", "component:") for m in memories]
                if choice == "tie":
                    block.update(state=TIE, seeds=[{"node": "component:x", "score": 1.0}] * 2)
                elif memories:
                    block.update(
                        state=SEEDED, lesson=memories[0]["id"], seeds=[{"node": nodes[0], "score": 1.0}]
                    )
                else:
                    block.update(state=EMPTY, seeds=[])
            record["retrieval"]["seeding"] = block
            if alter:
                alter(record)

        chooser = trace_chooser if condition == "C_S" else control_chooser(mode)
        receipts += sequence(batch, seed, condition, mode, chooser, extra)
    return receipts


def reference(alter=None):
    """Referencia sintética con la forma de ``evidence/reference-v2``: el agente por defecto."""
    receipts = []
    for batch, seed, (name, mode) in itertools.product(("BATCH-r1", "BATCH-r2"), SEEDS, MODES.items()):

        def extra(record, task):
            record["agent"] = REFERENCE_AGENT
            if alter:
                alter(record)

        receipts += sequence(batch, seed, name, mode, control_chooser(mode), extra)
    return receipts


REFERENCE = reference()


def runs_of(receipts):
    return [r for r in receipts if r["kind"] == "task_run"]


def always(choice):
    return lambda task, seed, batch: choice(task) if callable(choice) else choice


def on(choices):
    """``choices``: tarea → función de la tarea, ``"tie"`` o ``None``."""

    def seeded(task, seed, batch):
        choice = choices.get(task)
        return choice(task) if callable(choice) else choice

    return seeded


def reading(report):
    d = report["decision"]
    return d["verdict"], d["first_attempt"], d["selection_met"], d["mark"], d["secondary"]


# --- constantes y forma declarada -----------------------------------------------------------------


def test_constants_match_the_experiment_and_the_declared_campaign():
    assert CONDITIONS == EXPERIMENT_CONDITIONS
    assert (AGENT, POLICY) == (AGENT_NAME, EXPERIMENT_POLICY) == (NONLEXICAL_SEED_CAMPAIGN["agent"], POLICY)
    assert BoundedRepairAgent.name == REFERENCE_AGENT
    assert analysis.DECISION_INPUTS == DECISION_INPUTS
    assert (analysis.SEEDED, analysis.TIE, analysis.EMPTY) == (SEEDED, TIE, EMPTY)
    campaign = NONLEXICAL_SEED_CAMPAIGN
    assert campaign["seeds"] == analysis.SEEDS and campaign["replicates"] == analysis.REPLICATES
    assert campaign["train"] + campaign["transfer"] == analysis.TASKS
    assert (
        campaign["train"],
        campaign["transfer"],
    ) == (analysis.TRAIN, analysis.ORIGINAL + analysis.MISLEADING)
    assert tuple(CONDITIONS) == campaign["conditions"] == (*analysis.CONTROLS, analysis.NEW)
    assert (analysis.MARGIN, analysis.RUNS_PER_KIND, analysis.REFERENCE_CELLS) == (3, 18, 162)
    assert (RECEIPT_SCHEMA, SOURCE_HASH_NORMALIZATION) == (analysis.RECEIPT_SCHEMA, analysis.NORMALIZATION)
    view_keys = set(inspect.signature(TraceSeedRepairAgent.plan).parameters)
    assert view_keys == {"self", "view"}
    from experiments.agent import AgentView

    decision = TraceSeedRepairAgent().plan(AgentView({"title": "t", "context": "c"}, {}, (), "NO_MEMORY", 7))
    assert decision.keys() == analysis.DECISION_KEYS  # los campos del agente por defecto y ``policy``


def test_the_script_does_not_import_the_experiments_package():
    tree = ast.parse(inspect.getsource(analysis))
    imported = {
        (node.module or "") if isinstance(node, ast.ImportFrom) else alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert not any(name.split(".")[0] in ("experiments", "associative_agent_loop") for name in imported)


# --- reglas de decisión (sección 5) ---------------------------------------------------------------


def test_first_attempt_table_covers_every_integer_without_overlap():
    for delta_ctrl, delta_a in itertools.product(range(-18, 19), repeat=2):
        expected = (
            NOT_ABOVE_CONTROLS
            if delta_ctrl <= 2
            else WORSE
            if delta_a <= -3
            else IMPROVES
            if delta_a >= 3
            else NO_DIFFERENCE
        )
        assert first_attempt_reading(delta_ctrl, delta_a) == expected
    assert first_attempt_reading(3, 3) == IMPROVES and first_attempt_reading(2, 18) == NOT_ABOVE_CONTROLS
    assert first_attempt_reading(3, 2) == first_attempt_reading(3, -2) == NO_DIFFERENCE
    assert first_attempt_reading(3, -3) == WORSE


def test_selection_and_joint_verdict_table():
    assert [selection_met(s) for s in (0, 2, 3, 18)] == [True, True, False, False]
    assert VERDICTS == {
        (IMPROVES, True): "apoyada",
        (IMPROVES, False): "no apoyada: mejora, pero sigue citando el señuelo",
        (NO_DIFFERENCE, True): "sin diferencia",
        (NO_DIFFERENCE, False): "sin diferencia, y sigue citando el señuelo",
        (WORSE, True): "no apoyada: peor que no usar memoria",
        (WORSE, False): "no apoyada: peor que no usar memoria",
        (NOT_ABOVE_CONTROLS, True): "refutada",
        (NOT_ABOVE_CONTROLS, False): "refutada",
    }


def test_derived_table_with_the_controls_at_their_published_values():
    """Con B = C_L = 0/18 y A = 6/18, el primer intento depende solo de ``FA(C_S)`` (tabla derivada)."""
    original = {"A": 6, "B": 18, "C_L": 18, "C_S": 18}
    for fa in range(19):
        d = decide({"A": 6, "B": 0, "C_L": 0, "C_S": fa}, 0, 18, original)
        expected = (
            IMPROVES if fa >= 9 else NO_DIFFERENCE if fa >= 4 else WORSE if fa == 3 else NOT_ABOVE_CONTROLS
        )
        assert d["first_attempt"] == expected, fa
        assert (d["delta_ctrl"], d["delta_A"], d["delta_B"], d["delta_L"]) == (fa, fa - 6, fa, fa)


def test_the_control_difference_is_the_smaller_of_the_two():
    original = {"A": 0, "B": 0, "C_L": 0, "C_S": 0}
    d = decide({"A": 0, "B": 0, "C_L": 5, "C_S": 6}, 0, 18, original)
    assert (d["delta_B"], d["delta_L"], d["delta_ctrl"], d["first_attempt"]) == (6, 1, 1, NOT_ABOVE_CONTROLS)
    d = decide({"A": 0, "B": 5, "C_L": 0, "C_S": 6}, 0, 18, original)
    assert (d["delta_B"], d["delta_L"], d["delta_ctrl"], d["verdict"]) == (1, 6, 1, "refutada")


def test_no_exposure_mark_and_secondary_rule_boundaries():
    fa = {"A": 6, "B": 0, "C_L": 0, "C_S": 6}
    assert [decide(fa, 0, n, fa)["no_exposure"] for n in (0, 2, 3, 18)] == [True, True, False, False]
    assert decide(fa, 0, 2, fa)["mark"] == "sin exposición" and decide(fa, 0, 3, fa)["mark"] is None
    for c_s, expected in ((15, "con coste"), (16, "sin coste"), (18, "sin coste"), (0, "con coste")):
        d = decide(fa, 0, 18, {"A": 6, "B": 18, "C_L": 18, "C_S": c_s})
        assert (d["delta_orig"], d["secondary"]) == (c_s - 18, expected)


# --- veredictos sobre campañas sintéticas completas -----------------------------------------------


def test_a_silent_signal_is_no_difference_without_exposure():
    receipts = simulate()
    report = analyze(receipts, PRIVATE, REFERENCE)
    assert report["valid"] and report["replicates_consistent"]
    campaign = report["campaign"]
    assert (campaign["task_runs"], campaign["memory_updates"]) == (432, 108)
    assert campaign["batches"] == list(BATCHES) and campaign["primary_batch"] == "BATCH-a"
    assert report["controls_reproduce_reference"] == {"cells": 162, "reference_primary_batch": "BATCH-r1"}
    assert (report["margin_runs"], report["runs_per_kind"]) == (3, 18)
    fa = {c: report["metrics"][c]["by_kind"]["misleading"]["FA"] for c in CONDITIONS}
    assert {c: (v["numerator"], v["denominator"]) for c, v in fa.items()} == {
        "A": (6, 18),
        "B": (0, 18),
        "C_L": (0, 18),
        "C_S": (6, 18),
    }
    assert reading(report) == ("sin diferencia", NO_DIFFERENCE, True, "sin exposición", "con coste")
    assert report["verdict"] == "sin diferencia"
    d = report["decision"]
    assert (d["delta_B"], d["delta_L"], d["delta_A"], d["delta_ctrl"], d["delta_orig"]) == (6, 6, 0, 6, -12)
    assert (d["S"], d["cited_runs"], d["no_exposure"]) == (0, 0, True)
    assert report["seed_state_C_S"] == {t: {"seeded": 0, "tie": 0, "empty": 6} for t in TASKS}
    cited = report["cited_lesson_misleading"]
    assert cited["C_S"]["classes"] == {"correcta": 0, "señuelo": 0, "otra": 0, "ninguna": 18}
    for control in ("B", "C_L"):
        assert cited[control]["classes"] == {"correcta": 0, "señuelo": 18, "otra": 0, "ninguna": 0}
        assert cited[control]["by_task"]["EXP-07"] == {
            "runs": 6,
            "classes": {"correcta": 0, "señuelo": 6, "otra": 0, "ninguna": 0},
            "source_tasks": {"EXP-03": 6},
        }
    assert cited["A"]["classes"]["ninguna"] == 18
    # Por tarea y por tipo, con numerador y denominador; el entrenamiento se reporta igual.
    row = report["metrics"]["C_L"]["by_task"]["EXP-08"]
    assert row["FA"] == {"value": 0.0, "numerator": 0, "denominator": 6}
    assert row["Iter"]["denominator"] == 6 and row["Iter"]["numerator"] == sum(
        r["iterations"]
        for r in runs_of(receipts)
        if (r["batch_id"], r["condition"]) == ("BATCH-a", "C_L") and r["task"]["id"] == "EXP-08"
    )
    assert report["metrics"]["C_L"]["by_kind"]["original"]["FA"]["numerator"] == 18
    assert report["metrics"]["A"]["by_kind"]["train"]["FA"] == {
        "value": 6 / 18,
        "numerator": 6,
        "denominator": 18,
    }
    assert report["metrics"]["A"]["by_kind"]["misleading"]["Iter"] == {
        "value": 2.0,
        "numerator": 36,
        "denominator": 18,
    }


def test_citing_the_correct_lesson_everywhere_supports_h8():
    report = analyze(simulate(always(correct_lesson)), PRIVATE, REFERENCE)
    assert reading(report) == ("apoyada", IMPROVES, True, None, "sin coste")
    d = report["decision"]
    assert (d["delta_ctrl"], d["delta_A"], d["S"], d["cited_runs"], d["delta_orig"]) == (18, 12, 0, 18, 0)
    assert report["cited_lesson_misleading"]["C_S"]["classes"]["correcta"] == 18
    assert report["cited_lesson_misleading"]["C_S"]["by_task"]["EXP-09"]["source_tasks"] == {"EXP-03": 6}
    assert report["seed_state_C_S"]["EXP-07"] == {"seeded": 6, "tie": 0, "empty": 0}
    assert report["seed_state_C_S"]["EXP-01"] == {"seeded": 0, "tie": 0, "empty": 6}
    assert report["prediction"]["fulfilled"] is False


def test_following_the_decoy_refutes_h8():
    report = analyze(simulate(always(lexical)), PRIVATE, REFERENCE)
    assert reading(report) == ("refutada", NOT_ABOVE_CONTROLS, False, None, "sin coste")
    d = report["decision"]
    assert (d["delta_ctrl"], d["delta_A"], d["S"]) == (0, -6, 18)
    assert report["cited_lesson_misleading"]["C_S"]["classes"]["señuelo"] == 18


def test_the_registered_prediction_is_reachable_and_recognised():
    """EXP-07 sigue al señuelo y la señal calla en EXP-08 y EXP-09 (sección 6): 4/18 y S = 6."""
    report = analyze(simulate(on({"EXP-07": decoy_lesson})), PRIVATE, REFERENCE)
    assert reading(report) == (
        "sin diferencia, y sigue citando el señuelo",
        NO_DIFFERENCE,
        False,
        None,
        "con coste",
    )
    d = report["decision"]
    assert (report["metrics"]["C_S"]["by_kind"]["misleading"]["FA"]["numerator"], d["S"]) == (4, 6)
    assert (d["delta_ctrl"], d["delta_A"], d["cited_runs"]) == (4, -2, 6)
    assert report["prediction"] == {
        "predicted": {
            "verdict": "sin diferencia, y sigue citando el señuelo",
            "secondary": "con coste",
            "FA_C_S_misleading": 4,
            "S": 6,
        },
        "fulfilled": True,
        "FA_C_S_misleading_minus_predicted": 0,
        "S_minus_predicted": 0,
    }


def test_an_improvement_that_still_cites_the_decoy_is_not_support():
    choices = {"EXP-07": correct_lesson, "EXP-08": correct_lesson, "EXP-09": decoy_lesson}
    report = analyze(simulate(on(choices)), PRIVATE, REFERENCE)
    assert reading(report)[:3] == ("no apoyada: mejora, pero sigue citando el señuelo", IMPROVES, False)
    assert (report["decision"]["delta_ctrl"], report["decision"]["delta_A"], report["decision"]["S"]) == (
        12,
        6,
        6,
    )
    assert report["cited_lesson_misleading"]["C_S"]["classes"] == {
        "correcta": 12,
        "señuelo": 6,
        "otra": 0,
        "ninguna": 0,
    }


def test_a_wrong_lesson_that_is_not_the_decoy_can_be_worse_than_no_memory():
    def seeded(task, seed, batch):
        if task == "EXP-09" and seed in SEEDS[:3]:
            return correct_lesson(task)
        return other_lesson(task) if task in MISLEADING else None

    report = analyze(simulate(seeded), PRIVATE, REFERENCE)
    assert reading(report)[:3] == ("no apoyada: peor que no usar memoria", WORSE, True)
    d = report["decision"]
    assert (d["delta_ctrl"], d["delta_A"], d["S"], d["cited_runs"]) == (3, -3, 0, 18)
    assert report["cited_lesson_misleading"]["C_S"]["classes"] == {
        "correcta": 3,
        "señuelo": 0,
        "otra": 15,
        "ninguna": 0,
    }


def test_ties_are_counted_as_a_seed_state_and_expose_nothing():
    report = analyze(simulate(on({"EXP-08": "tie", "EXP-04": correct_lesson})), PRIVATE, REFERENCE)
    assert report["seed_state_C_S"]["EXP-08"] == {"seeded": 0, "tie": 6, "empty": 0}
    assert report["seed_state_C_S"]["EXP-04"] == {"seeded": 6, "tie": 0, "empty": 0}
    assert report["decision"]["cited_runs"] == 0 and report["decision"]["mark"] == "sin exposición"
    assert report["decision"]["delta_orig"] == -8  # 6 de EXP-04 y 2 + 2 del prior, frente a 18


# --- validez: una campaña inválida no tiene veredicto (sección 5) ---------------------------------


def invalid(receipts, reason, reference_receipts=REFERENCE):
    report = analyze(receipts, PRIVATE, reference_receipts)
    assert report["valid"] is False and report["verdict"] == "inválida", report.get("verdict")
    assert reason in report["invalid_reason"], report["invalid_reason"]
    assert "decision" not in report and "metrics" not in report  # ningún veredicto
    return report


def where(batch="BATCH-a", seed=1, condition="C_S", task="EXP-07"):
    return lambda r: (
        (r["batch_id"], r["seed"], r["condition"], r["task"]["id"]) == (batch, seed, condition, task)
    )


def altering(select, change):
    def alter(record):
        if select(record):
            change(record)

    return alter


def test_control_the_untouched_simulation_is_valid():
    assert analyze(simulate(alter=lambda r: None), PRIVATE, REFERENCE)["valid"] is True


def test_an_incomplete_or_malformed_campaign_is_invalid():
    receipts = simulate()
    dropped = [r for r in receipts if not (r["kind"] == "task_run" and where()(r))]
    invalid(dropped, "no es la campaña declarada")
    invalid([r for r in receipts if r.get("batch_id") != "BATCH-b"], "se esperaban 2 réplicas")
    invalid([*receipts, seal({**receipts[0], "run_id": "RUN-twin"})], "celda duplicada")
    extra = [
        seal({**copy.deepcopy(r), "run_id": r["run_id"] + "-x", "seed": 2}) for r in runs_of(receipts)[:1]
    ]
    invalid([*receipts, *extra], "no es la campaña declarada")
    invalid(
        [*receipts, seal({**HEADER, "kind": "other", "run_id": "RUN-x"})],
        "tipo o de una memoria no previstos",
    )
    stray = seal({**HEADER, "kind": "memory_update", "run_id": "RUN-f", "memory_store": "failure-memory/v1"})
    invalid([*receipts, stray], "tipo o de una memoria no previstos")


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        (lambda r: r.update(result="ERROR"), "resultado ERROR"),
        (lambda r: r.update(agent=REFERENCE_AGENT), "solo recibos de la recuperación sembrada"),
        (lambda r: r["decision"].update(policy="diagnostic-baseline/v1"), "solo recibos de la recuperación"),
        (lambda r: r["decision"].update(diagnostic={"status": "partial"}), "campos distintos"),
        (lambda r: r["decision"].pop("without_memory"), "campos distintos"),
        (lambda r: r.pop("decision_inputs"), "orden test-0, RETRIEVE, plan"),
        (lambda r: r["decision_inputs"].update(order=["RETRIEVE", "test-0", "plan"]), "orden test-0"),
        (lambda r: r.update(**{"pass": 1}), "orden test-0"),
        (lambda r: r.update(condition="C"), "sin condición o bloque"),
        (lambda r: r["retrieval"].pop("seeding"), "sin condición o bloque"),
        (lambda r: r.update(memory_mode="TEXT_HISTORY"), "no concuerda con el modo"),
        (
            lambda r: r["retrieval"]["seeding"].update(signal="lexical-title-context"),
            "no concuerda con el modo",
        ),
        (lambda r: r["retrieval"]["seeding"].update(policy="x/v9"), "no concuerda con el modo"),
        (
            lambda r: r["retrieval"]["seeding"].update(state="seeded", lesson="lesson:x"),
            "estado de la siembra",
        ),
        (lambda r: r["retrieval"]["seeding"].update(state="unknown"), "estado de la siembra"),
        (lambda r: r["retrieval"]["seeding"].update(components=[]), "señales distintas"),
        (lambda r: r.update(split="train"), "particiones"),
    ],
    ids=[
        "error-receipt",
        "other-agent",
        "other-policy",
        "diagnostic-field",
        "missing-default-field",
        "no-inputs",
        "h58-order",
        "pass",
        "unknown-condition",
        "no-block",
        "mode",
        "signal",
        "seed-policy",
        "state-without-lesson",
        "unknown-state",
        "signal-differs",
        "split",
    ],
)
def test_a_receipt_outside_the_declared_contract_is_invalid(change, reason):
    invalid(simulate(alter=altering(where(), change)), reason)


def test_an_error_receipt_without_decision_is_invalid_and_does_not_crash():
    def broken(record):
        for key in ("decision", "retrieval", "outcome"):
            record.pop(key)
        record.update(result="ERROR", error={"type": "ValueError", "message": "x"})

    invalid(simulate(alter=altering(where(), broken)), "resultado ERROR")


def test_a_control_declaring_trace_seeds_is_invalid():
    change = lambda r: r["retrieval"]["seeding"].update(seeds=[], state="empty")  # noqa: E731
    invalid(
        simulate(alter=altering(where(condition="C_L"), change)), "sin siembra de la traza declara semillas"
    )


def test_misdeclared_private_partitions_are_invalid():
    private = copy.deepcopy(PRIVATE)
    private["EXP-04"]["decoy_family"] = "ready"
    report = analyze(simulate(), private, REFERENCE)
    assert (report["valid"], "particiones" in report["invalid_reason"]) == (False, True)
    private = copy.deepcopy(PRIVATE)
    private["EXP-07"].pop("decoy_family")
    assert analyze(simulate(), private, REFERENCE)["valid"] is False


def test_lessons_out_of_provenance_or_unmatched_memory_updates_are_invalid():
    receipts = simulate()
    runs = runs_of(receipts)
    donor = next(r for r in runs if where(condition="C_L")(r))["memory_input"]

    def foreign(record):
        record["memory_input"] = copy.deepcopy(donor)

    invalid(simulate(alter=altering(where(), foreign)), "lección fuera de procedencia")

    def lesson_in_a(record):
        record["memory_input"] = copy.deepcopy(donor)

    invalid(simulate(alter=altering(where(condition="A"), lesson_in_a)), "A con lecciones")

    def outside(record):
        record["retrieval"]["memories"] = [{"id": "lesson:elsewhere", "task": "EXP-01"}]
        record["retrieval"]["seeding"].update(state="seeded", lesson="lesson:elsewhere")

    invalid(simulate(alter=altering(where(), outside)), "fuera de la memoria elegible")
    updates = [r for r in receipts if r["kind"] == "memory_update"]
    invalid([r for r in receipts if r is not updates[0]], "memory_update no corresponden")
    invalid([*receipts, seal({**updates[0], "run_id": "RUN-again"})], "memory_update no corresponden")


def test_replicates_that_differ_in_behaviour_are_invalid():
    def seeded(task, seed, batch):
        return correct_lesson(task) if (task, seed, batch) == ("EXP-07", 4, "BATCH-b") else None

    report = invalid(simulate(seeded), "las réplicas difieren en comportamiento")
    assert "semilla 4, EXP-07, C_S" in report["invalid_reason"]


@pytest.mark.parametrize("condition", ["A", "B", "C_L"])
def test_controls_that_do_not_reproduce_the_reference_are_invalid(condition):
    mode = CONDITIONS[condition][0]

    def other_plan(record):
        if (record["memory_mode"], record["seed"], record["task"]["id"]) == (mode, 5, "EXP-05"):
            record["decision"]["plan"] = list(reversed(record["decision"]["plan"]))

    report = invalid(
        simulate(), "los controles no reproducen la referencia en 1 de 162", reference(other_plan)
    )
    assert f"{condition}/EXP-05/semilla 5" in report["invalid_reason"]

    def other_iterations(record):
        if (record["memory_mode"], record["task"]["id"]) == (mode, "EXP-09"):
            record["iterations"] += 1

    invalid(simulate(), "no reproducen la referencia en 6 de 162", reference(other_iterations))


def test_only_the_first_replicate_of_the_reference_is_compared():
    def second_batch(record):
        if record["batch_id"] == "BATCH-r2":
            record["decision"]["plan"] = list(reversed(record["decision"]["plan"]))

    assert analyze(simulate(), PRIVATE, reference(second_batch))["valid"] is True


def test_a_malformed_reference_is_invalid():
    full = reference()
    invalid(simulate(), "la referencia no tiene ejecuciones", [])
    missing = [r for r in full if not (r["kind"] == "task_run" and r["task"]["id"] == "EXP-09")]
    invalid(simulate(), "no tiene las 162 celdas", missing)
    invalid(simulate(), "con error o de otro agente", reference(lambda r: r.update(agent=AGENT)))
    invalid(simulate(), "con error o de otro agente", reference(lambda r: r.update(result="ERROR")))


# --- carga y CLI ----------------------------------------------------------------------------------


def write(directory, receipts):
    directory.mkdir(parents=True)
    for record in receipts:
        (directory / (record["run_id"] + ".json")).write_text(json.dumps(record), encoding="utf-8")


def test_load_verifies_seals_schema_and_file_names(tmp_path):
    receipts = simulate()[:3]
    write(tmp_path / "ok", receipts)
    loaded, generated_from = load(tmp_path / "ok")
    assert loaded == sorted(receipts, key=lambda r: r["run_id"])
    assert generated_from == {r["run_id"] + ".json": r["receipt_sha256"] for r in receipts}
    record = copy.deepcopy(receipts[0])
    record["seed"] = 99  # alterado sin volver a sellar
    write(tmp_path / "tampered", [record])
    with pytest.raises(ValueError, match="sello del recibo"):
        load(tmp_path / "tampered")
    write(tmp_path / "unsealed", [{k: v for k, v in receipts[0].items() if k != "receipt_sha256"}])
    with pytest.raises(ValueError, match="sello del recibo"):
        load(tmp_path / "unsealed")
    legacy = seal(
        {k: v for k, v in receipts[0].items() if k not in ("receipt_sha256", "source_hash_normalization")}
    )
    write(tmp_path / "legacy", [legacy])
    with pytest.raises(ValueError, match="esquema o normalización"):
        load(tmp_path / "legacy")
    (tmp_path / "renamed").mkdir()
    (tmp_path / "renamed" / "RUN-other.json").write_text(json.dumps(receipts[0]), encoding="utf-8")
    with pytest.raises(ValueError, match="nombre del archivo"):
        load(tmp_path / "renamed")


def test_cli_prints_the_report_with_its_sources_and_fails_on_an_invalid_campaign(
    tmp_path, monkeypatch, capsys
):
    (tmp_path / "benchmark/private").mkdir(parents=True)
    tasks = {t: PRIVATE[t] for t in TASKS[:6]}
    (tmp_path / "benchmark/private/tasks.json").write_text(json.dumps(tasks), encoding="utf-8")
    misleading = {t: PRIVATE[t] for t in MISLEADING}
    (tmp_path / "benchmark/private/tasks_misleading.json").write_text(
        json.dumps(misleading), encoding="utf-8"
    )
    receipts = simulate(on({"EXP-07": decoy_lesson}))
    write(tmp_path / "evidence/nonlexical-seed-v1", receipts)
    write(tmp_path / "evidence/reference-v2", REFERENCE)
    argv = ["analyze_h8", "--root", str(tmp_path), "--evidence", "evidence/nonlexical-seed-v1"]
    monkeypatch.setattr(sys, "argv", argv)
    analysis.main()
    report = json.loads(capsys.readouterr().out)
    assert report["valid"] and report["verdict"] == "sin diferencia, y sigue citando el señuelo"
    assert report["generated_from"] == {r["run_id"] + ".json": r["receipt_sha256"] for r in receipts}
    assert report["reference"]["directory"] == "evidence/reference-v2"
    assert len(report["reference"]["generated_from"]) == len(REFERENCE)
    # Una campaña inválida se publica como tal: informe con su motivo y código de salida 1.
    write(
        tmp_path / "evidence/other-reference", reference(lambda r: r.update(iterations=r["iterations"] + 1))
    )
    monkeypatch.setattr(sys, "argv", [*argv, "--reference", "evidence/other-reference"])
    with pytest.raises(SystemExit) as stop:
        analysis.main()
    assert stop.value.code == 1
    report = json.loads(capsys.readouterr().out)
    assert (report["valid"], report["verdict"]) == (False, "inválida")
    assert "no reproducen la referencia" in report["invalid_reason"] and report["generated_from"]
