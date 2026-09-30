"""Memoria de fallos (H6, #63): orden del runner, recibos, verificaciones del evaluador y CLI.

Ejecuta la receta ``failure_campaign`` real sobre una celda mínima (semilla 7, una réplica, EXP-01 de
entrenamiento y EXP-04 en dos pasadas, las cuatro condiciones), en un directorio temporal. Para que haya
registros **por construcción**, el test del primer intento de cada ejecución de EXP-04 se marca como
fallido. EXP-01 se ejecuta sin alterar. La celda comprueba estructura (orden, claves, derivación, alcance
de un registro sobre su propia tarea, rechazo de alteraciones), nunca qué estrategia acierta en una tarea
real ni una ganancia.
"""

import copy
import itertools
import json
import sys

import pytest

from experiments import __main__ as cli
from experiments import runner
from experiments.agent import STRATEGIES
from experiments.benchmark import DIAGNOSTIC_CAMPAIGN, FAILURE_MEMORY_CAMPAIGN, REFERENCE_CAMPAIGN, TASK_SETS
from experiments.diagnostic import DiagnosticRepairAgent
from experiments.diagnostic import replay_decision as replay_diagnostic
from experiments.evaluate import evaluate, expected_failure_record, failure_slices
from experiments.evidence import digest, publish, read_receipt
from experiments.failure_memory import (
    AGENT_NAME,
    DECISION_INPUTS,
    STORE,
    FailureMemory,
    FailureMemoryRepairAgent,
    replay_decision,
)
from experiments.runner import ROOT, load_task, run_experiment

FAILURE_RECORD_FIELDS = {"condition", "pass", "failure_memory_input", "failure_origins"}
FORCED = "\nFORCED FAILURE (test sintético del harness)\n"


def forced_first_attempt(real):
    """Marca como fallido el primer intento de EXP-04, reconocida por su test de aceptación público."""
    acceptance = (ROOT / "benchmark/public" / load_task("EXP-04").test_file).read_bytes()

    def execute(workspace, index, timeout=20):
        result = real(workspace, index, timeout)
        if index == 1 and (workspace / "tests/test_contract.py").read_bytes() == acceptance:
            result = {**result, "returncode": 1, "stderr": result["stderr"] + FORCED}
        return result

    return execute


@pytest.fixture(scope="module")
def cell(tmp_path_factory):
    evidence = tmp_path_factory.mktemp("failure-memory-cell")
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(runner, "execute_tests", forced_first_attempt(runner.execute_tests))
        cli.failure_campaign([7], 1, evidence, train=("EXP-01",), transfer=("EXP-04",))
    return evidence


def receipts_of(directory):
    return [read_receipt(p) for p in sorted(directory.glob("RUN-*.json"))]


def runs_of(directory):
    return [r for r in receipts_of(directory) if r["kind"] == "task_run"]


def find(runs, condition, task, number):
    return next(r for r in runs if (r["condition"], r["task"]["id"], r["pass"]) == (condition, task, number))


def test_runner_decides_once_after_the_reproduction_with_the_failure_snapshot(tmp_path, monkeypatch):
    log, seen = [], []
    real = runner.execute_tests

    def execute(workspace, index, timeout=20):
        log.append(index)
        return real(workspace, index, timeout)

    monkeypatch.setattr(runner, "execute_tests", execute)
    prior = FailureMemory([{"id": "failure:x", "strategy": STRATEGIES[0], "query": "q", "signature": []}])

    class Spy(FailureMemoryRepairAgent):
        def plan(self, view):
            log.append("plan")
            seen.append(view.failures)
            return super().plan(view)

    path = run_experiment(
        "EXP-01", Spy(), "NO_MEMORY", 7, evidence_dir=tmp_path, failures=prior, condition="A_N", pass_number=1
    )
    receipt = read_receipt(path)
    assert log[:2] == [0, "plan"] and log.count("plan") == 1 and log.count(0) == 1
    assert seen == [tuple(prior.records)]
    assert receipt["decision_inputs"] == DECISION_INPUTS
    assert receipt["failure_memory_input"] == prior.records
    assert (receipt["condition"], receipt["pass"], receipt["agent"]) == ("A_N", 1, AGENT_NAME)
    context = {
        "task": receipt["task"],
        "files": receipt["initial_source"],
        "memories": [],
        "reproduction": {
            "returncode": receipt["tests"][0]["returncode"],
            "stderr": receipt["tests"][0]["stderr"],
        },
        "failures": prior.records,
    }
    assert receipt["agent_context_sha256"] == digest(context)
    assert replay_decision(receipt) == receipt["decision"]
    later = copy.deepcopy(receipt)
    for test in later["tests"][1:]:
        test["returncode"], test["stderr"] = 1, "later output"
    assert replay_decision(later) == receipt["decision"]  # los tests posteriores no llegan a la decisión


def test_other_agents_write_no_failure_memory_field(tmp_path):
    receipt = read_receipt(
        run_experiment("EXP-01", DiagnosticRepairAgent(), "NO_MEMORY", 7, evidence_dir=tmp_path)
    )
    assert not FAILURE_RECORD_FIELDS & receipt.keys()
    assert "plan_without_failures" not in receipt["decision"]
    assert replay_diagnostic(receipt) == receipt["decision"]


def test_campaign_follows_the_declared_sequence_and_the_evaluator_accepts_it(cell):
    runs = runs_of(cell)
    assert len(runs) == 4 * 3 and {r["agent"] for r in runs} == {AGENT_NAME}
    for condition in ("A", "A_N", "C", "C_N"):
        items = [r for r in runs if r["condition"] == condition]
        assert sorted((r["pass"], r["task"]["id"]) for r in items) == [
            (1, "EXP-01"),
            (1, "EXP-04"),
            (2, "EXP-04"),
        ]
        assert {r["split"] for r in items if r["task"]["id"] == "EXP-01"} == {"train"}
    for condition in ("A", "C"):  # sin memoria de fallos
        assert all(
            r["failure_memory_input"] == [] and r["failure_origins"] == []
            for r in runs
            if r["condition"] == condition
        )
    for condition in ("A_N", "C_N"):
        # Por construcción, test-1 falló en EXP-04 (pasada 1): su registro aplica en la pasada 2 (misma
        # firma, similitud 1), y su origen es la misma tarea.
        first, second = find(runs, condition, "EXP-04", 1), find(runs, condition, "EXP-04", 2)
        own = "failure:" + first["run_id"] + "#test-1"
        assert own in [x["id"] for x in second["failure_memory_input"]]
        assert own in second["decision"]["failure_ids"]
        assert {"id": own, "origin": "same_task"} in second["failure_origins"]
        assert first["actions"][0]["strategy"] in second["decision"]["failure_strategies"]
    report = evaluate(cell)
    assert (
        set(report["metrics"])
        == set(failure_slices(runs))
        == {
            "without-failure-memory-pass-1",
            "without-failure-memory-pass-2",
            "with-failure-memory-pass-1",
            "with-failure-memory-pass-2",
        }
    )
    assert all(r["all_semantic_projections_equal"] for r in report["replication"].values())
    for name, comparisons in report["comparisons"].items():
        assert len(comparisons) == 2, name  # C (o C_N) y A (o A_N) frente a su NO_MEMORY, una pasada
    updates = [
        u for u in receipts_of(cell) if u["kind"] == "memory_update" and u.get("memory_store") == STORE
    ]
    sources = sorted(u["source_receipt"] for u in updates)
    failed = [
        r["run_id"] + ".json"
        for r in runs
        if r["condition"] in ("A_N", "C_N") and any(t["returncode"] for t in r["tests"][1:])
    ]
    assert sources == sorted(failed)  # uno por ejecución de A_N o C_N con intentos fallidos, y ninguno más
    assert {find(runs, c, "EXP-04", n)["run_id"] + ".json" for c in ("A_N", "C_N") for n in (1, 2)} <= set(
        sources
    )


def test_evaluator_writes_the_generic_report_by_slice(cell, tmp_path):
    output = tmp_path / "results"
    report = evaluate(cell, output)
    assert json.loads((output / "experiment1.json").read_text("utf-8")) == report
    assert "failure memory (#63)" in (output / "README.md").read_text("utf-8")
    for name in report["metrics"]:
        assert (output / name / "task_breakdown.json").exists()
        assert (output / name / "family_breakdown.json").exists()


def resealed(cell, target, change, select=lambda r: True, drop=lambda r: False):
    """Copia la celda alterando los task_run elegidos y volviendo a sellarlos, como podría hacerlo un
    autor con privilegios: los sellos solos no detectan esto."""
    target.mkdir()
    for record in receipts_of(cell):
        record.pop("receipt_sha256")
        if drop(record):
            continue
        if record["kind"] == "task_run" and select(record):
            change(record)
        publish(target, record)
    return target


def at(condition, task, number):
    return lambda r: (r["condition"], r["task"]["id"], r["pass"]) == (condition, task, number)


def replayed(change):
    """Altera el recibo y recalcula la decisión desde él: la repetición sola ya no lo detecta."""

    def apply(record):
        change(record)
        record["decision"] = replay_decision(record)
        record["failure_origins"] = []  # A y C no aplican nada; en A_N/C_N lo corrige cada test

    return apply


def own_record(cell, condition):
    return copy.deepcopy(find(runs_of(cell), condition, "EXP-04", 2)["failure_memory_input"][0])


def test_evaluator_rejects_a_decision_that_does_not_replay(cell, tmp_path):
    def tamper(record):
        record["decision"]["failure_effect"] = "none"
        record["decision"]["plan"] = list(reversed(record["decision"]["plan"]))

    with pytest.raises(ValueError, match="no se repite"):
        evaluate(resealed(cell, tmp_path / "plan", tamper, at("A_N", "EXP-04", 2)))


def test_evaluator_rejects_failure_records_in_a_and_c(cell, tmp_path):
    for condition, donor in (("A", "A_N"), ("C", "C_N")):
        record = own_record(cell, donor)
        inject = replayed(lambda r, x=record: r["failure_memory_input"].append(x))
        with pytest.raises(ValueError, match="no cita una ejecución sellada de su"):
            evaluate(resealed(cell, tmp_path / condition, inject, at(condition, "EXP-04", 2)))


def _origins(record, tasks):
    """Orígenes coherentes con los recibos, para que solo falle la guarda que prueba cada caso."""
    source = {x["id"]: tasks.get(x["evidence"].partition("#")[0]) for x in record["failure_memory_input"]}
    return [
        {"id": i, "origin": "same_task" if source[i] == record["task"]["id"] else "other_task"}
        for i in record["decision"]["failure_ids"]
    ]


def tasks_of(cell):
    return {r["run_id"]: r["task"]["id"] for r in runs_of(cell)}


@pytest.mark.parametrize(
    ("edit", "message"),
    [
        (lambda inputs, r: inputs.pop(), "no es exactamente"),  # memoria incompleta
        (
            lambda inputs, r: (
                inputs.reverse() if len(inputs) > 1 else inputs.append(copy.deepcopy(inputs[0]))
            ),
            "no es exactamente",
        ),
        (lambda inputs, r: inputs[0].update(strategy="otra"), "no coincide con su recibo"),
        (
            lambda inputs, r: inputs[0].update(evidence=inputs[0]["evidence"].replace("test-1", "test-0")),
            "intento de reparación fallido",
        ),
        (
            lambda inputs, r: inputs[0].update(evidence=inputs[0]["evidence"].replace("test-1", "test-9")),
            "intento de reparación fallido",
        ),
        (lambda inputs, r: inputs[0].update(evidence="RUN-missing#test-1"), "no cita una ejecución sellada"),
    ],
    ids=[
        "incomplete",
        "reordered-or-duplicated",
        "field",
        "cites-test-0",
        "cites-missing-test",
        "unknown-run",
    ],
)
def test_evaluator_requires_each_record_to_cite_a_real_earlier_failed_attempt(cell, tmp_path, edit, message):
    tasks = tasks_of(cell)

    def change(record):
        edit(record["failure_memory_input"], record)
        record["decision"] = replay_decision(record)
        record["failure_origins"] = _origins(record, tasks)

    with pytest.raises(ValueError, match=message):
        evaluate(resealed(cell, tmp_path / "records", change, at("A_N", "EXP-04", 2)))


def test_evaluator_rejects_a_record_from_a_later_run(cell, tmp_path):
    later = find(runs_of(cell), "A_N", "EXP-04", 2)
    fake = {
        **own_record(cell, "A_N"),
        "evidence": later["run_id"] + "#test-1",
        "id": "failure:" + later["run_id"] + "#test-1",
    }

    tasks = tasks_of(cell)

    def change(record):
        record["failure_memory_input"].append(copy.deepcopy(fake))
        record["decision"] = replay_decision(record)
        record["failure_origins"] = _origins(record, tasks)

    with pytest.raises(ValueError, match="posterior"):
        evaluate(resealed(cell, tmp_path / "later", change, at("A_N", "EXP-04", 1)))


def test_evaluator_rejects_altered_origins_and_missing_or_extra_updates(cell, tmp_path):
    def swap(record):
        for item in record["failure_origins"]:
            item["origin"] = "other_task" if item["origin"] == "same_task" else "same_task"

    with pytest.raises(ValueError, match="orígenes"):
        evaluate(resealed(cell, tmp_path / "origins", swap, at("C_N", "EXP-04", 2)))
    with pytest.raises(ValueError, match="un único memory_update"):
        evaluate(
            resealed(
                cell, tmp_path / "missing", lambda r: None, drop=lambda r: r.get("memory_store") == STORE
            )
        )
    extra = resealed(cell, tmp_path / "extra", lambda r: None)
    update = next(u for u in receipts_of(cell) if u.get("memory_store") == STORE)
    update = {k: v for k, v in update.items() if k != "receipt_sha256"}
    publish(extra, {**update, "run_id": "RUN-extra"})
    with pytest.raises(ValueError, match="un único memory_update"):
        evaluate(extra)  # dos memory_update para la misma ejecución
    stray = resealed(cell, tmp_path / "stray", lambda r: None)
    source = find(runs_of(cell), "A", "EXP-04", 1)["run_id"] + ".json"
    publish(stray, {**update, "run_id": "RUN-stray", "source_receipt": source})
    with pytest.raises(ValueError, match="no corresponden a los intentos fallidos"):
        evaluate(stray)  # un memory_update de fallos desde A


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (
            lambda r: r.update(
                decision_inputs={"order": ["RETRIEVE", "test-0", "plan"], "reproduction": "test-0"}
            ),
            "reproducción previa",
        ),
        (lambda r: r["tests"][0].update(returncode=0), "reproducción previa"),
        (lambda r: r.update(memory_mode="ASSOCIATIVE_MEMORY"), "no concuerdan"),
        (lambda r: r.update(**{"pass": 3}), "pasada"),
        (lambda r: r.pop("failure_origins"), "pasada"),
    ],
    ids=["58-inputs", "test0-passed", "mode", "pass", "missing-field"],
)
def test_evaluator_requires_declared_inputs_condition_and_pass(cell, tmp_path, change, message):
    with pytest.raises(ValueError, match=message):
        evaluate(resealed(cell, tmp_path / "declared", change, at("A_N", "EXP-04", 1)))


def test_evaluator_rejects_lessons_shared_between_c_and_c_n(cell, tmp_path):
    """Lecciones de C en C_N: misma semilla, lote y modo; solo la condición las separa."""
    runs = runs_of(cell)
    lessons = copy.deepcopy(find(runs, "C", "EXP-04", 1)["memory_input"]["lessons"])
    assert lessons, "precondición: C aprendió de EXP-01 (cada tarea tiene un operador que la repara)"

    def change(record):
        record["memory_input"]["lessons"] = copy.deepcopy(lessons)

    with pytest.raises(ValueError, match="memory provenance"):
        evaluate(resealed(cell, tmp_path / "lessons", change, at("C_N", "EXP-04", 1)))


def test_other_agents_carrying_failure_fields_are_rejected(cell, tmp_path):
    def as_diagnostic(record):
        record["agent"] = DiagnosticRepairAgent.name
        record["decision"]["policy"] = "diagnostic-baseline/v1"

    with pytest.raises(ValueError, match="ajeno a la memoria de fallos"):
        evaluate(resealed(cell, tmp_path / "agent", as_diagnostic))


def test_cli_failure_memory_campaign_fixes_configuration_and_directory(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "failure_campaign", lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setattr(cli, "campaign", lambda *args, **kwargs: calls.append(("default", args, kwargs)))
    monkeypatch.setattr(sys, "argv", ["experiments", "run", "--campaign", "failure-memory-v1"])
    cli.main()
    (seeds, replicates, evidence_dir, train, transfer), kwargs = calls[0]
    assert (seeds, replicates) == ([1, 4, 5, 6, 7, 9], 2) and kwargs == {}
    assert (train, transfer) == (FAILURE_MEMORY_CAMPAIGN["train"], FAILURE_MEMORY_CAMPAIGN["transfer"])
    assert evidence_dir == ROOT / "evidence/failure-memory-v1"
    for extra in (["--replicates", "1"], ["--seeds", "7"], ["--task-set", "v1"]):
        monkeypatch.setattr(sys, "argv", ["experiments", "run", "--campaign", "failure-memory-v1", *extra])
        with pytest.raises(SystemExit):
            cli.main()
    # Las recetas anteriores no cambian: ni directorio, ni agente, ni receta.
    calls.clear()
    monkeypatch.setattr(sys, "argv", ["experiments", "run", "--campaign", "reference-v2"])
    cli.main()
    monkeypatch.setattr(sys, "argv", ["experiments", "run", "--campaign", "diagnostic-baseline-v1"])
    cli.main()
    monkeypatch.setattr(sys, "argv", ["experiments", "run"])
    cli.main()
    assert calls == [
        (
            "default",
            (list(REFERENCE_CAMPAIGN["seeds"]), 2, ROOT / "evidence/runs", TASK_SETS["misleading-v1"]),
            {},
        ),
        (
            "default",
            (
                list(DIAGNOSTIC_CAMPAIGN["seeds"]),
                2,
                ROOT / "evidence/diagnostic-baseline-v1",
                TASK_SETS["misleading-v1"],
            ),
            {"agent_factory": DiagnosticRepairAgent},
        ),
        ("default", ([7, 11, 23], 2, ROOT / "evidence/runs", TASK_SETS["v1"]), {}),
    ]


def test_failure_campaign_refuses_bad_replication_and_a_misdeclared_split(tmp_path):
    with pytest.raises(ValueError, match="unique seeds"):
        cli.failure_campaign([7, 7], 1, tmp_path)
    with pytest.raises(RuntimeError, match="partición declarada"):
        cli.failure_campaign([7], 1, tmp_path, train=("EXP-04",), transfer=())


def test_the_declared_seeds_cover_every_prior_permutation():
    from experiments.agent import prior_order

    seeds = FAILURE_MEMORY_CAMPAIGN["seeds"]
    assert {prior_order(s) for s in seeds} == set(itertools.permutations(STRATEGIES))


def test_evaluator_rejects_a_well_formed_record_of_an_attempt_that_passed(cell, tmp_path):
    runs = runs_of(cell)
    source = find(runs, "A_N", "EXP-01", 1)
    assert source["result"] == "PASS", "precondición: EXP-01 se ejecuta sin alterar y termina reparada"
    passing = expected_failure_record(source, len(source["tests"]) - 1)  # bien formado, pero su test pasó
    tasks = tasks_of(cell)

    def change(record):
        record["failure_memory_input"].append(copy.deepcopy(passing))
        record["decision"] = replay_decision(record)
        record["failure_origins"] = _origins(record, tasks)

    with pytest.raises(ValueError, match="intento de reparación fallido"):
        evaluate(resealed(cell, tmp_path / "passing", change, at("A_N", "EXP-04", 1)))


def test_evaluator_rejects_an_update_that_does_not_derive_from_its_run(cell, tmp_path):
    target = find(runs_of(cell), "C_N", "EXP-04", 2)["run_id"] + ".json"
    altered = tmp_path / "update"
    altered.mkdir()
    for record in receipts_of(cell):
        record.pop("receipt_sha256")
        if record.get("memory_store") == STORE and record["source_receipt"] == target:
            record["memory_after"] = record["memory_before"]
        publish(altered, record)
    with pytest.raises(ValueError, match="no deriva de su recibo"):
        evaluate(altered)


def test_evaluator_rejects_different_diagnoses_across_conditions_or_passes(cell, tmp_path):
    def other_reproduction(record):
        record["tests"][0]["stderr"] = FORCED + "\nERROR: x (m.K)\n"  # otra traza, otra firma
        record["decision"] = replay_decision(record)

    with pytest.raises(ValueError, match="diagnósticos distintos"):
        evaluate(resealed(cell, tmp_path / "diagnosis", other_reproduction, at("A", "EXP-04", 2)))


def test_evaluator_rejects_a_repeated_run_in_a_sequence(cell, tmp_path):
    repeated = resealed(cell, tmp_path / "repeated", lambda r: None)
    copy_ = {k: v for k, v in find(runs_of(cell), "A", "EXP-04", 1).items() if k != "receipt_sha256"}
    publish(repeated, {**copy_, "run_id": "RUN-repeated", "batch_id": copy_["batch_id"]})
    with pytest.raises(ValueError, match="ejecución repetida"):
        evaluate(repeated)
