"""Transferencia de fallos (H7, #65): orden del runner, recibos, verificaciones del evaluador y CLI.

Ejecuta la receta ``transfer_campaign`` real sobre una celda mínima (semilla 7, una réplica, EXP-02 de
entrenamiento y EXP-05 en su única pasada, ocho de las 18 condiciones), en un directorio temporal, sin
alterar ningún test. EXP-02 y EXP-05 comparten la firma de D (tabla de similitudes de H6, que el
pre-registro declara); con la semilla 7, EXP-02 tiene un intento fallido, así que hay un registro de
**otra** tarea por construcción. La celda comprueba estructura (orden, claves, derivación, alcance, placebo,
rechazo de alteraciones), nunca qué estrategia acierta en una tarea real ni una ganancia.
"""

import copy
import itertools
import sys

import pytest

from associative_agent_loop.memory.text import cosine_similarity
from experiments import __main__ as cli
from experiments import runner
from experiments.agent import STRATEGIES
from experiments.benchmark import (
    DIAGNOSTIC_CAMPAIGN,
    FAILURE_MEMORY_CAMPAIGN,
    FAILURE_TRANSFER_CAMPAIGN,
    REFERENCE_CAMPAIGN,
    TASK_SETS,
)
from experiments.diagnostic import DiagnosticRepairAgent
from experiments.evaluate import evaluate, expected_failure_record, transfer_slices
from experiments.evidence import digest, publish, read_receipt
from experiments.failure_memory import AGENT_NAME as FAILURE_AGENT
from experiments.failure_memory import POLICY as FAILURE_POLICY
from experiments.failure_memory import STORE, FailureMemory, FailureMemoryRepairAgent
from experiments.failure_transfer import (
    AGENT_NAME,
    CONDITIONS,
    DECISION_INPUTS,
    ROTATION,
    FailureTransferRepairAgent,
    TransferFailureMemory,
    replay_decision,
)
from experiments.runner import ROOT, run_experiment

CELL = ("A", "C", "A_R50", "C_R50", "A_R00", "C_R00", "A_P00", "C_P00")
TRAIN, TARGET = "EXP-02", "EXP-05"
TRANSFER_RECORD_FIELDS = {"failure_scope_tau", "placebo"}
TRANSFER_DECISION_FIELDS = {"failure_scope_tau", "failure_placebo", "failure_recorded_strategies"}


@pytest.fixture(scope="module")
def cell(tmp_path_factory):
    evidence = tmp_path_factory.mktemp("failure-transfer-cell")
    cli.transfer_campaign([7], 1, evidence, train=(TRAIN,), transfer=(TARGET,), conditions=CELL)
    return evidence


def receipts_of(directory):
    return [read_receipt(p) for p in sorted(directory.glob("RUN-*.json"))]


def runs_of(directory):
    return [r for r in receipts_of(directory) if r["kind"] == "task_run"]


def find(runs, condition, task=TARGET):
    return next(r for r in runs if (r["condition"], r["task"]["id"]) == (condition, task))


def test_runner_decides_once_after_the_reproduction_with_scope_and_placebo(tmp_path, monkeypatch):
    log, seen = [], []
    real = runner.execute_tests

    def execute(workspace, index, timeout=20):
        log.append(index)
        return real(workspace, index, timeout)

    monkeypatch.setattr(runner, "execute_tests", execute)
    prior = TransferFailureMemory(
        [{"id": "failure:x", "strategy": STRATEGIES[0], "query": "q", "signature": []}]
    )

    class Spy(FailureTransferRepairAgent):
        def plan(self, view):
            log.append("plan")
            seen.append((view.failures, view.scope_tau, view.placebo))
            return super().plan(view)

    path = run_experiment(
        "EXP-01", Spy(), "NO_MEMORY", 7, evidence_dir=tmp_path, failures=prior, condition="A_P25"
    )
    receipt = read_receipt(path)
    assert log[:2] == [0, "plan"] and log.count("plan") == 1 and log.count(0) == 1
    assert seen == [(tuple(prior.records), 0.25, True)]
    assert receipt["decision_inputs"] == DECISION_INPUTS
    assert (receipt["condition"], receipt["failure_scope_tau"], receipt["placebo"]) == ("A_P25", 0.25, True)
    assert "pass" not in receipt and receipt["agent"] == AGENT_NAME
    assert (receipt["decision"]["failure_scope_tau"], receipt["decision"]["failure_placebo"]) == (0.25, True)
    assert receipt["failure_memory_input"] == prior.records
    context = {
        "task": receipt["task"],
        "files": receipt["initial_source"],
        "memories": [],
        "reproduction": {
            "returncode": receipt["tests"][0]["returncode"],
            "stderr": receipt["tests"][0]["stderr"],
        },
        "failures": prior.records,
        "failure_policy": {"failure_scope_tau": 0.25, "placebo": True},
    }
    assert receipt["agent_context_sha256"] == digest(context)
    assert replay_decision(receipt) == receipt["decision"]
    later = copy.deepcopy(receipt)
    for test in later["tests"][1:]:
        test["returncode"], test["stderr"] = 1, "later output"
    assert replay_decision(later) == receipt["decision"]  # los tests posteriores no llegan a la decisión
    other = copy.deepcopy(receipt)
    other["placebo"] = False
    assert replay_decision(other)["failure_placebo"] is False  # el placebo se repite desde el recibo


def test_other_agents_write_no_failure_transfer_field(tmp_path):
    receipt = read_receipt(
        run_experiment(
            "EXP-01",
            FailureMemoryRepairAgent(),
            "NO_MEMORY",
            7,
            evidence_dir=tmp_path,
            failures=FailureMemory(),
            condition="A_N",
            pass_number=1,
        )
    )
    assert not TRANSFER_RECORD_FIELDS & receipt.keys()
    assert not TRANSFER_DECISION_FIELDS & receipt["decision"].keys()
    assert receipt["decision"]["policy"] == FAILURE_POLICY and receipt["pass"] == 1


def test_campaign_follows_the_declared_single_pass_and_the_evaluator_accepts_it(cell):
    runs = runs_of(cell)
    assert len(runs) == len(CELL) * 2 and {r["agent"] for r in runs} == {AGENT_NAME}
    assert all("pass" not in r for r in runs)
    for condition in CELL:
        _, enabled, tau, placebo = CONDITIONS[condition]
        train, target = find(runs, condition, TRAIN), find(runs, condition, TARGET)
        assert (train["split"], target["split"]) == ("train", "transfer")
        assert (target["failure_scope_tau"], target["placebo"]) == (tau, placebo)
        if not enabled:
            assert train["failure_memory_input"] == target["failure_memory_input"] == []
            assert target["failure_origins"] == [] and target["decision"]["failure_effect"] == "none"
            continue
        failed = [i for i, t in enumerate(train["tests"]) if i >= 1 and t["returncode"]]
        assert failed, f"precondición: con la semilla 7, {TRAIN} tiene un intento fallido en {condition}"
        assert target["failure_memory_input"] == [expected_failure_record(train, i) for i in failed]
        same = train["decision"]["diagnostic"]["features"] == target["decision"]["diagnostic"]["features"]
        assert same, f"precondición: {TRAIN} y {TARGET} comparten la firma de D"
        similarity = cosine_similarity(
            target["task"]["title"] + " " + target["task"]["context"],
            train["task"]["title"] + " " + train["task"]["context"],
        )
        assert 0 < similarity < 0.5
        for item in target["decision"]["failure_scope"]:
            assert item["applies"] == (item["signature_match"] and item["similarity"] >= tau)
            assert item["demotes"] == (ROTATION[item["strategy"]] if placebo else item["strategy"])
        applied = target["decision"]["failure_ids"]
        assert bool(applied) == (tau == 0.0)  # con τ = 0 basta la firma; con τ = 0.5, no alcanza
        assert target["failure_origins"] == [{"id": i, "origin": "other_task"} for i in applied]
        recorded = {x["strategy"] for x in target["failure_memory_input"] if x["id"] in applied}
        demoted = {ROTATION[s] for s in recorded} if placebo else recorded
        assert target["decision"]["failure_strategies"] == [s for s in STRATEGIES if s in demoted]
    report = evaluate(cell)
    assert set(report["metrics"]) == set(transfer_slices(runs)) and len(report["metrics"]) == 9
    assert report["campaign"] == "failure-transfer-v1"
    assert all(r["all_semantic_projections_equal"] for r in report["replication"].values())
    for name in ("without-failure-memory", "real-tau-0.5", "real-tau-0.0", "placebo-tau-0.0"):
        assert len(report["comparisons"][name]) == 2, name  # C_x y A_x frente a A_x, una sola pasada
    assert report["comparisons"]["real-tau-0.25"] == []
    updates = [
        u for u in receipts_of(cell) if u["kind"] == "memory_update" and u.get("memory_store") == STORE
    ]
    expected = [
        r["run_id"] + ".json"
        for r in runs
        if CONDITIONS[r["condition"]][1] and any(t["returncode"] for t in r["tests"][1:])
    ]
    assert sorted(u["source_receipt"] for u in updates) == sorted(expected)


def test_evaluator_writes_the_generic_report_by_slice(cell, tmp_path):
    output = tmp_path / "results"
    report = evaluate(cell, output)
    assert "failure transfer (#65)" in (output / "README.md").read_text("utf-8")
    assert "analyze_failure_transfer" in (output / "README.md").read_text("utf-8")
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


def at(condition, task=TARGET):
    return lambda r: (r["condition"], r["task"]["id"]) == (condition, task)


def origins_from(record, tasks):
    """Orígenes coherentes con los recibos, para que solo falle la guarda que prueba cada caso."""
    source = {x["id"]: tasks.get(x["evidence"].partition("#")[0]) for x in record["failure_memory_input"]}
    return [
        {"id": i, "origin": "same_task" if source[i] == record["task"]["id"] else "other_task"}
        for i in record["decision"]["failure_ids"]
    ]


def tasks_of(cell):
    return {r["run_id"]: r["task"]["id"] for r in runs_of(cell)}


def test_evaluator_rejects_a_decision_that_does_not_replay(cell, tmp_path):
    def tamper(record):
        record["decision"]["plan"] = list(reversed(record["decision"]["plan"]))

    with pytest.raises(ValueError, match="no se repite"):
        evaluate(resealed(cell, tmp_path / "plan", tamper, at("A_R00")))


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda r: r.update(failure_scope_tau=0.5), "alcance τ"),
        (lambda r: r.update(placebo=True), "placebo"),
        (lambda r: r.update(failure_scope_tau=0.5, condition="A_R50"), "no se repite"),
        (lambda r: r.update(memory_mode="ASSOCIATIVE_MEMORY"), "modo de memoria"),
        (lambda r: r.update(**{"pass": 1}), "con pasada"),
        (lambda r: r.pop("placebo"), "con pasada"),
        (lambda r: r.update(condition="A_N"), "con pasada"),
        (
            lambda r: r.update(
                decision_inputs={
                    "order": ["RETRIEVE", "test-0", "plan"],
                    "reproduction": "test-0",
                    "failures": "failure_memory_input",
                }
            ),
            "reproducción previa",
        ),
        (lambda r: r["tests"][0].update(returncode=0), "reproducción previa"),
    ],
    ids=[
        "tau",
        "placebo",
        "relabelled-condition",
        "mode",
        "pass",
        "missing-field",
        "h6-condition",
        "h6-inputs",
        "test0",
    ],
)
def test_evaluator_requires_the_declared_scope_placebo_and_inputs(cell, tmp_path, change, message):
    with pytest.raises(ValueError, match=message):
        evaluate(resealed(cell, tmp_path / "declared", change, at("A_R00")))


def test_evaluator_rejects_failure_records_in_the_bases(cell, tmp_path):
    for base, donor in (("A", "A_R00"), ("C", "C_R00")):
        record = copy.deepcopy(find(runs_of(cell), donor)["failure_memory_input"][0])

        def inject(r, x=record):
            r["failure_memory_input"].append(x)

        with pytest.raises(ValueError, match="bases A y C"):
            evaluate(resealed(cell, tmp_path / base, inject, at(base)))


@pytest.mark.parametrize("honest", [False, True], ids=["origin-claimed-other", "origin-declared-same"])
def test_evaluator_rejects_an_applied_record_from_the_same_task(cell, tmp_path, honest):
    runs = runs_of(cell)
    donor = find(runs, "A_P00")
    failed = [i for i, t in enumerate(donor["tests"]) if i >= 1 and t["returncode"]]
    assert failed, "precondición: el placebo no baja la estrategia que falló, así que falla un intento"
    same = expected_failure_record(donor, failed[0])  # un registro de la misma tarea, de otra condición
    tasks = tasks_of(cell)

    def change(record):
        record["failure_memory_input"].append(copy.deepcopy(same))
        record["decision"] = replay_decision(record)
        assert same["id"] in record["decision"]["failure_ids"]  # misma firma y similitud 1: aplica
        record["failure_origins"] = (
            origins_from(record, tasks)
            if honest
            else [{"id": i, "origin": "other_task"} for i in record["decision"]["failure_ids"]]
        )

    with pytest.raises(ValueError, match="misma tarea"):
        evaluate(resealed(cell, tmp_path / "same", change, at("A_R00")))


def test_evaluator_keeps_the_chain_checks_of_h6(cell, tmp_path):
    tasks = tasks_of(cell)

    def incomplete(record):
        record["failure_memory_input"].pop()
        record["decision"] = replay_decision(record)
        record["failure_origins"] = origins_from(record, tasks)

    with pytest.raises(ValueError, match="no es exactamente"):
        evaluate(resealed(cell, tmp_path / "incomplete", incomplete, at("A_R00")))
    stray = resealed(cell, tmp_path / "stray", lambda r: None)
    update = next(u for u in receipts_of(cell) if u.get("memory_store") == STORE)
    update = {k: v for k, v in update.items() if k != "receipt_sha256"}
    source = find(runs_of(cell), "A", TRAIN)["run_id"] + ".json"
    publish(stray, {**update, "run_id": "RUN-stray", "source_receipt": source})
    with pytest.raises(ValueError, match="no corresponden a los intentos fallidos"):
        evaluate(stray)  # un memory_update de fallos desde la base A
    with pytest.raises(ValueError, match="un único memory_update"):
        evaluate(
            resealed(
                cell, tmp_path / "missing", lambda r: None, drop=lambda r: r.get("memory_store") == STORE
            )
        )


def test_evaluator_rejects_lessons_shared_between_c_and_its_variants(cell, tmp_path):
    lessons = copy.deepcopy(find(runs_of(cell), "C")["memory_input"]["lessons"])
    assert lessons, f"precondición: C aprendió de {TRAIN} (cada tarea tiene un operador que la repara)"

    def change(record):
        record["memory_input"]["lessons"] = copy.deepcopy(lessons)

    with pytest.raises(ValueError, match="memory provenance"):
        evaluate(resealed(cell, tmp_path / "lessons", change, at("C_R00")))


def test_other_agents_carrying_transfer_or_failure_fields_are_rejected(cell, tmp_path):
    def as_h6(record):
        record["agent"] = FAILURE_AGENT
        record["decision"]["policy"] = FAILURE_POLICY

    with pytest.raises(ValueError, match="ajeno a la transferencia"):
        evaluate(resealed(cell, tmp_path / "h6", as_h6))

    def as_diagnostic(record):
        record["agent"] = DiagnosticRepairAgent.name
        record["decision"]["policy"] = "diagnostic-baseline/v1"

    with pytest.raises(ValueError, match="ajeno a la memoria de fallos"):
        evaluate(resealed(cell, tmp_path / "diagnostic", as_diagnostic))


def test_evaluator_rejects_different_diagnoses_across_conditions(cell, tmp_path):
    def other_reproduction(record):
        record["tests"][0]["stderr"] = "\nERROR: x (m.K)\n"  # otra traza, otra firma
        record["decision"] = replay_decision(record)

    with pytest.raises(ValueError, match="diagnósticos distintos"):
        evaluate(resealed(cell, tmp_path / "diagnosis", other_reproduction, at("A")))


def test_cli_failure_transfer_campaign_fixes_configuration_and_directory(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "transfer_campaign", lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setattr(cli, "failure_campaign", lambda *args, **kwargs: calls.append(("h6", args, kwargs)))
    monkeypatch.setattr(cli, "campaign", lambda *args, **kwargs: calls.append(("default", args, kwargs)))
    monkeypatch.setattr(sys, "argv", ["experiments", "run", "--campaign", "failure-transfer-v1"])
    cli.main()
    (seeds, replicates, evidence_dir, train, transfer), kwargs = calls[0]
    assert (seeds, replicates) == ([1, 4, 5, 6, 7, 9], 2) and kwargs == {}
    assert (train, transfer) == (FAILURE_TRANSFER_CAMPAIGN["train"], FAILURE_TRANSFER_CAMPAIGN["transfer"])
    assert evidence_dir == ROOT / "evidence/failure-transfer-v1"
    for extra in (["--replicates", "1"], ["--seeds", "7"], ["--task-set", "v1"]):
        monkeypatch.setattr(sys, "argv", ["experiments", "run", "--campaign", "failure-transfer-v1", *extra])
        with pytest.raises(SystemExit):
            cli.main()
    # Las recetas anteriores no cambian: ni directorio, ni agente, ni receta.
    calls.clear()
    for argv in (["--campaign", "failure-memory-v1"], ["--campaign", "reference-v2"], []):
        monkeypatch.setattr(sys, "argv", ["experiments", "run", *argv])
        cli.main()
    assert calls == [
        (
            "h6",
            (
                [1, 4, 5, 6, 7, 9],
                2,
                ROOT / "evidence/failure-memory-v1",
                FAILURE_MEMORY_CAMPAIGN["train"],
                FAILURE_MEMORY_CAMPAIGN["transfer"],
            ),
            {},
        ),
        (
            "default",
            (list(REFERENCE_CAMPAIGN["seeds"]), 2, ROOT / "evidence/runs", TASK_SETS["misleading-v1"]),
            {},
        ),
        ("default", ([7, 11, 23], 2, ROOT / "evidence/runs", TASK_SETS["v1"]), {}),
    ]
    assert DIAGNOSTIC_CAMPAIGN["evidence_dir"] == "evidence/diagnostic-baseline-v1"


def test_transfer_campaign_refuses_bad_replication_conditions_and_a_misdeclared_split(tmp_path):
    with pytest.raises(ValueError, match="unique seeds"):
        cli.transfer_campaign([7, 7], 1, tmp_path)
    with pytest.raises(ValueError, match="unique seeds"):
        cli.transfer_campaign([7], 0, tmp_path)
    for conditions in ((), ("A", "A"), ("A", "A_N")):
        with pytest.raises(ValueError, match="condiciones de transferencia"):
            cli.transfer_campaign([7], 1, tmp_path, conditions=conditions)
    with pytest.raises(RuntimeError, match="partición declarada"):
        cli.transfer_campaign([7], 1, tmp_path, train=("EXP-04",), transfer=(), conditions=("A",))


def test_transfer_campaign_stops_on_a_harness_error(tmp_path, monkeypatch):
    def broken(*args, **kwargs):
        raise ValueError("fixture rota (test sintético)")

    monkeypatch.setattr(runner, "prepare", broken)
    with pytest.raises(RuntimeError, match="fixture rota"):
        cli.transfer_campaign([7], 1, tmp_path, train=(TRAIN,), transfer=(), conditions=("A_R00",))
    (receipt,) = receipts_of(tmp_path)
    assert receipt["result"] == "ERROR" and receipt["condition"] == "A_R00"


def test_the_declared_seeds_cover_every_prior_permutation():
    from experiments.agent import prior_order

    seeds = FAILURE_TRANSFER_CAMPAIGN["seeds"]
    assert {prior_order(s) for s in seeds} == set(itertools.permutations(STRATEGIES))
