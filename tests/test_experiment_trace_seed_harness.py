"""Recuperación sembrada (H8, #98): orden del runner, recibos, verificaciones del evaluador y CLI.

Ejecuta la receta ``seed_campaign`` real sobre una celda mínima (semilla 7, una réplica, EXP-01..03 de
entrenamiento y EXP-04, una tarea original, en las cuatro condiciones), en un directorio temporal. La celda
comprueba estructura: orden, claves, repetición y rechazo de alteraciones. Ningún test afirma qué lección
recupera una tarea engañosa ni exige una ganancia; la invariancia de la sección 8 recorre las nueve tareas y
solo compara igualdades.
"""

import contextlib
import copy
import io
import json
import os
import shutil
import subprocess
import sys

import pytest

from experiments import __main__ as cli
from experiments import runner
from experiments.agent import BoundedRepairAgent
from experiments.benchmark import (
    DIAGNOSTIC_CAMPAIGN,
    FAILURE_TRANSFER_CAMPAIGN,
    NONLEXICAL_SEED_CAMPAIGN,
    REFERENCE_CAMPAIGN,
    TASK_SETS,
    private_metadata,
)
from experiments.diagnostic import DiagnosticRepairAgent
from experiments.evaluate import evaluate, seed_slices
from experiments.evidence import digest, publish, read_receipt, sources_digest
from experiments.failure_memory import FailureMemory
from experiments.nonlexical_seed import (
    AGENT_NAME,
    CONDITIONS,
    DECISION_INPUTS,
    TRACE,
    TraceSeedRepairAgent,
    replay_context,
    replay_decision,
    replay_retrieval,
)
from experiments.runner import ROOT, run_experiment
from experiments.trace_seed import EMPTY, POLICY, SEEDED, TIE, seeded_retrieval, trace_components

TRAIN, TARGET = NONLEXICAL_SEED_CAMPAIGN["train"], "EXP-04"
DEFAULT_KEYS = {
    "considered",
    "selected",
    "plan",
    "without_memory",
    "influenced_by_memory",
    "memory_ids",
    "initial_hypothesis",
}
METADATA = private_metadata(ROOT)
INJECTED = (
    "=" * 70
    + "\nERROR: test_x (m.K)\n"
    + "-" * 70
    + '\nTraceback (most recent call last):\n  File "<workspace>/app/config.py", line 1, in f\n    g()\n'
    + "tamper.Injected: not produced by any task\n\n"
)


def receipts_of(directory):
    return [read_receipt(p) for p in sorted(directory.glob("RUN-*.json"))]


def runs_of(directory):
    return [r for r in receipts_of(directory) if r["kind"] == "task_run"]


def find(runs, condition, task=TARGET):
    return next(r for r in runs if (r["condition"], r["task"]["id"]) == (condition, task))


def behaviour(r):
    origin = {m["id"]: m["task"] for m in r["retrieval"]["memories"]}
    return (
        r["decision"]["plan"],
        [m["task"] for m in r["retrieval"]["memories"]],
        [origin[i] for i in r["decision"]["memory_ids"]],
        r["result"],
        r["iterations"],
    )


# --- runner ---------------------------------------------------------------------------------------


def test_runner_reproduces_then_retrieves_then_decides_once(tmp_path, monkeypatch):
    log, views = [], []
    real_tests, real_retrieve = runner.execute_tests, runner.seeded_retrieve

    def execute(workspace, index, timeout=20):
        log.append(index)
        return real_tests(workspace, index, timeout)

    def retrieve(memory, condition, query, stderr, files):
        log.append("retrieve")
        return real_retrieve(memory, condition, query, stderr, files)

    monkeypatch.setattr(runner, "execute_tests", execute)
    monkeypatch.setattr(runner, "seeded_retrieve", retrieve)

    class Spy(TraceSeedRepairAgent):
        def plan(self, view):
            log.append("plan")
            views.append(view)
            return super().plan(view)

    path = run_experiment("EXP-01", Spy(), "ASSOCIATIVE_MEMORY", 7, evidence_dir=tmp_path, condition="C_S")
    receipt = read_receipt(path)
    assert receipt["result"] in ("PASS", "FAIL"), receipt.get("error")
    assert log[:3] == [0, "retrieve", "plan"]
    assert (log.count(0), log.count("retrieve"), log.count("plan")) == (1, 1, 1)
    assert (
        receipt["decision_inputs"]
        == DECISION_INPUTS
        == {
            "order": ["test-0", "RETRIEVE", "plan"],
            "reproduction": "test-0",
        }
    )
    assert receipt["phases"][:3] == ["ISSUE", "RETRIEVE", "INSPECT"]  # la tabla de fases no cambia
    assert [t["id"] for t in receipt["tests"]] == [f"test-{i}" for i in range(len(receipt["tests"]))]
    assert receipt["tests"][0]["returncode"] != 0
    # El solver recibe una AgentView como el agente por defecto: la traza no llega a la decisión.
    (view,) = views
    assert type(view).__name__ == "AgentView" and not hasattr(view, "reproduction")
    assert (receipt["agent"], receipt["condition"]) == (AGENT_NAME, "C_S")
    assert "pass" not in receipt and "failure_memory_input" not in receipt
    assert set(receipt["decision"]) == DEFAULT_KEYS | {"policy"} and receipt["decision"]["policy"] == POLICY
    seeding = receipt["retrieval"]["seeding"]
    assert set(seeding) == {"policy", "signal", "components", "seeds", "state", "lesson"}
    assert (seeding["policy"], seeding["signal"], seeding["state"]) == (POLICY, TRACE, EMPTY)  # memoria vacía
    files = tuple(receipt["initial_source"])
    assert seeding["components"] == trace_components(receipt["tests"][0]["stderr"], files)
    # El contexto hasheado cubre lo que recibió la recuperación.
    context = {
        "task": receipt["task"],
        "files": receipt["initial_source"],
        "memories": [],
        "retrieval": {
            "condition": "C_S",
            "policy": POLICY,
            "signal": TRACE,
            "memory_sha256": receipt["memory_before_sha256"],
            "stderr": receipt["tests"][0]["stderr"],
            "files": sorted(files),
        },
    }
    assert receipt["agent_context_sha256"] == digest(context) == digest(replay_context(receipt))
    assert replay_retrieval(receipt) == ([], [], seeding)
    assert replay_decision(receipt) == receipt["decision"]


def test_only_test0_feeds_the_retrieval(cell):
    receipt = find(runs_of(cell), "C_S")
    recorded = (
        receipt["retrieval"]["memories"],
        receipt["retrieval"]["paths"],
        receipt["retrieval"]["seeding"],
    )
    assert replay_retrieval(receipt) == recorded
    later = copy.deepcopy(receipt)
    for test in later["tests"][1:]:
        test["stderr"], test["returncode"] = INJECTED, 1
    later["tests"].append({"id": "test-9", "stderr": INJECTED, "returncode": 1})
    assert replay_retrieval(later) == recorded  # tests[1:] no llegan a la recuperación
    earlier = copy.deepcopy(receipt)
    earlier["tests"][0]["stderr"] = INJECTED
    files = tuple(receipt["initial_source"])
    expected = seeded_retrieval(receipt["memory_input"], INJECTED, files)
    assert replay_retrieval(earlier)[:2] == expected[:2] and replay_retrieval(earlier) != recorded
    assert replay_retrieval(earlier)[2]["components"] == [{"component": "app/config.py", "weight": 1.0}]


@pytest.mark.parametrize(
    ("mode", "kwargs"),
    [
        ("ASSOCIATIVE_MEMORY", {}),
        ("ASSOCIATIVE_MEMORY", {"condition": "C"}),
        ("ASSOCIATIVE_MEMORY", {"condition": "A"}),
        ("NO_MEMORY", {"condition": "C_S"}),
        ("TEXT_HISTORY", {"condition": "C_L"}),
        ("ASSOCIATIVE_MEMORY", {"condition": "C_S", "pass_number": 1}),
        ("ASSOCIATIVE_MEMORY", {"condition": "C_S", "failures": FailureMemory()}),
    ],
    ids=["no-condition", "unknown", "A-mode", "C_S-mode", "C_L-mode", "pass", "failures"],
)
def test_runner_requires_a_seed_condition_coherent_with_the_memory_mode(tmp_path, mode, kwargs):
    with pytest.raises(ValueError, match="siembra de la recuperación exige"):
        run_experiment("EXP-01", TraceSeedRepairAgent(), mode, 7, evidence_dir=tmp_path, **kwargs)
    assert not list(tmp_path.glob("RUN-*.json"))


def test_other_agents_cannot_declare_a_seed_condition_and_write_no_seed_field(tmp_path, monkeypatch):
    for agent, mode, condition in (
        (BoundedRepairAgent(), "ASSOCIATIVE_MEMORY", "C_S"),
        (DiagnosticRepairAgent(), "NO_MEMORY", "A"),
    ):
        with pytest.raises(ValueError, match="memoria de fallos exige su agente"):
            run_experiment("EXP-01", agent, mode, 7, evidence_dir=tmp_path, condition=condition)
    log = []
    real = runner.execute_tests

    class Spy(BoundedRepairAgent):
        def plan(self, view):
            log.append("plan")
            return super().plan(view)

    def execute(workspace, index, timeout=20):
        log.append(index)
        return real(workspace, index, timeout)

    monkeypatch.setattr(runner, "execute_tests", execute)
    receipt = read_receipt(run_experiment("EXP-01", Spy(), "ASSOCIATIVE_MEMORY", 7, evidence_dir=tmp_path))
    assert log[:2] == ["plan", 0]  # el orden histórico del agente por defecto: decide y después reproduce
    assert set(receipt["retrieval"]) == {"memories", "paths"}
    assert "decision_inputs" not in receipt and "condition" not in receipt
    assert set(receipt["decision"]) == DEFAULT_KEYS
    assert receipt["agent_context_sha256"] == digest(
        {"task": receipt["task"], "files": receipt["initial_source"], "memories": []}
    )


def test_a_reproduction_that_changes_the_observable_workspace_is_an_error(tmp_path, monkeypatch):
    real = runner.execute_tests

    def execute(workspace, index, timeout=20):
        result = real(workspace, index, timeout)
        if index == 0:
            target = workspace / "app" / "config.py"
            target.write_text(target.read_text("utf-8") + "\n# touched by test-0\n", encoding="utf-8")
        return result

    monkeypatch.setattr(runner, "execute_tests", execute)
    for condition, mode in (("C_S", "ASSOCIATIVE_MEMORY"), ("A", "NO_MEMORY")):
        receipt = read_receipt(
            run_experiment(
                "EXP-01",
                TraceSeedRepairAgent(),
                mode,
                7,
                evidence_dir=tmp_path / condition,
                condition=condition,
            )
        )
        assert receipt["result"] == "ERROR"
        assert "modificó el workspace observable" in receipt["error"]["message"]
        assert "decision" not in receipt  # se detiene antes de recuperar y de decidir


# --- la celda real y el evaluador -----------------------------------------------------------------


@pytest.fixture(scope="module")
def cell(tmp_path_factory):
    evidence = tmp_path_factory.mktemp("trace-seed-cell")
    cli.seed_campaign([7], 1, evidence, train=TRAIN, transfer=(TARGET,))
    return evidence


def test_campaign_follows_the_declared_sequence_and_the_evaluator_accepts_it(cell, tmp_path):
    runs = runs_of(cell)
    assert len(runs) == 4 * 4 and {r["agent"] for r in runs} == {AGENT_NAME}
    assert len({r["batch_id"] for r in runs}) == 1
    updates = [u for u in receipts_of(cell) if u["kind"] == "memory_update"]
    assert not any("memory_store" in u for u in updates)
    trained = [r for r in runs if r["split"] == "train" and r["memory_mode"] != "NO_MEMORY"]
    assert all(r["result"] == "PASS" for r in trained)
    assert sorted(u["source_receipt"] for u in updates) == sorted(r["run_id"] + ".json" for r in trained)
    for condition, (mode, signal) in CONDITIONS.items():
        target = find(runs, condition)
        assert (target["memory_mode"], target["split"]) == (mode, "transfer")
        assert [find(runs, condition, t)["split"] for t in TRAIN] == ["train"] * 3
        assert target["retrieval"]["seeding"]["signal"] == signal
        lessons = (target["memory_input"] or {}).get("lessons", [])
        assert [x["task"] for x in lessons] == ([] if condition == "A" else list(TRAIN))
        # Lecciones propias de la condición: C_L y C_S no comparten memoria.
        own = {find(runs, condition, t)["run_id"] for t in TRAIN}
        assert {x["run_id"] for x in lessons} <= own
    seeded = find(runs, "C_S")
    block = seeded["retrieval"]["seeding"]
    assert block["state"] in (SEEDED, TIE, EMPTY)
    exposed = [m["id"] for m in seeded["retrieval"]["memories"]]
    assert exposed == ([block["lesson"]] if block["state"] == SEEDED else [])
    nodes = {n["id"]: n["type"] for n in seeded["memory_input"]["nodes"]}
    assert all(nodes[s["node"]] == "Component" for s in block["seeds"])
    # La misma señal en las cuatro condiciones; solo C_S declara semillas y estado.
    for task in (*TRAIN, TARGET):
        signals = {json.dumps(find(runs, c, task)["retrieval"]["seeding"]["components"]) for c in CONDITIONS}
        assert len(signals) == 1
    for condition in ("A", "B", "C_L"):
        other = find(runs, condition)["retrieval"]["seeding"]
        assert (other["seeds"], other["state"], other["lesson"]) == (None, None, None)
    # C_L y C_S construyen sus lecciones igual: mismos nodos y aristas, salvo los identificadores.
    shapes = []
    for condition in ("C_L", "C_S"):
        memory = find(runs, condition)["memory_input"]
        shapes.append(
            (
                [
                    (n["type"], n["label"])
                    for n in memory["nodes"]
                    if n["type"] not in ("Experience", "Evidence")
                ],
                [e["relation"] for e in memory["edges"]],
                [(x["task"], x["strategy"], x["rule"]) for x in memory["lessons"]],
            )
        )
    assert shapes[0] == shapes[1]
    output = tmp_path / "results"
    report = evaluate(cell, output)
    assert report["campaign"] == "nonlexical-seed-v1"
    assert list(report["metrics"]) == list(seed_slices(runs)) == ["lexical-seed", "trace-seed"]
    assert all(r["all_semantic_projections_equal"] for r in report["replication"].values())
    for name, members in seed_slices(runs).items():
        assert len(members) == 3 * 4 and len(report["comparisons"][name]) == 3
        assert (output / name / "task_breakdown.json").exists()
        assert (output / name / "family_breakdown.json").exists()
    readme = (output / "README.md").read_text("utf-8")
    assert "non-lexical seed (#98)" in readme and "analyze_h8" in readme


def test_the_controls_behave_as_the_default_agent_in_the_published_reference(cell):
    """A, B y C_L de la receta nueva repiten la referencia v2 publicada en plan, lecciones expuestas y
    citadas, resultado e intentos: solo cambia la siembra de C_S."""
    reference = [
        r
        for r in runs_of(ROOT / "evidence/reference-v2")
        if r["seed"] == 7 and r["task"]["id"] in (*TRAIN, TARGET)
    ]
    primary = min(r["batch_id"] for r in reference)
    published = {(r["memory_mode"], r["task"]["id"]): r for r in reference if r["batch_id"] == primary}
    runs = runs_of(cell)
    compared = 0
    for condition in ("A", "B", "C_L"):
        for task in (*TRAIN, TARGET):
            mine = find(runs, condition, task)
            theirs = published[(CONDITIONS[condition][0], task)]
            assert behaviour(mine) == behaviour(theirs), (condition, task)
            assert mine["initial_source_sha256"] == theirs["initial_source_sha256"]
            assert mine["acceptance_sha256"] == theirs["acceptance_sha256"]
            assert {k: v for k, v in mine["decision"].items() if k not in ("memory_ids", "policy")} == {
                k: v for k, v in theirs["decision"].items() if k != "memory_ids"
            }
            compared += 1
    assert compared == 12


def resealed(cell, target, change, select=lambda r: True):
    """Copia la celda alterando los task_run elegidos y volviendo a sellarlos, como podría hacerlo un
    autor con privilegios: los sellos solos no detectan esto."""
    target.mkdir()
    for record in receipts_of(cell):
        record.pop("receipt_sha256")
        if record["kind"] == "task_run" and select(record):
            change(record)
        publish(target, record)
    return target


def at(condition, task=TARGET):
    return lambda r: (r["condition"], r["task"]["id"]) == (condition, task)


def test_control_an_untouched_resealed_cell_is_accepted(cell, tmp_path):
    assert evaluate(resealed(cell, tmp_path / "intact", lambda r: None))["campaign"] == "nonlexical-seed-v1"


def consistent(record):
    """Deja coherente todo lo que deriva de la recuperación, para que solo falle la guarda que se prueba."""
    record["retrieved_memories"] = [m["id"] for m in record["retrieval"]["memories"]]
    record["decision"] = replay_decision(record)
    record["agent_context_sha256"] = digest(replay_context(record))


def lesson_of(record, task):
    lesson = next(x for x in record["memory_input"]["lessons"] if x["task"] == task)
    return lesson, "component:" + lesson["run_id"]


def seed_on_the_private_correct_lesson(record):
    """La semilla movida a la lección de la familia correcta, tomada de las anotaciones privadas."""
    correct = METADATA[record["task"]["id"]]["relevant_training_tasks"][0]
    lesson, node = lesson_of(record, correct)
    assert [m["task"] for m in record["retrieval"]["memories"]] != [correct], "precondición: no es la real"
    record["retrieval"]["memories"] = [dict(lesson)]
    record["retrieval"]["seeding"].update(
        seeds=[{"node": node, "score": 1.0}], state=SEEDED, lesson=lesson["id"]
    )
    consistent(record)


def seed_on_a_cause_node(record):
    cause = next(n["id"] for n in record["memory_input"]["nodes"] if n["type"] == "Cause")
    record["retrieval"]["seeding"]["seeds"] = [{"node": cause, "score": 1.0}]


def seed_on_the_lesson_node(record):
    record["retrieval"]["seeding"]["seeds"] = [
        {"node": record["memory_input"]["lessons"][0]["id"], "score": 1.0}
    ]


def seed_on_an_unknown_node(record):
    record["retrieval"]["seeding"]["seeds"] = [{"node": "component:RUN-unknown", "score": 1.0}]


def changed_score(record):
    seeds = record["retrieval"]["seeding"]["seeds"]
    assert seeds, "precondición: con la semilla 7, la traza de la tarea pasa por un componente con lección"
    seeds[0]["score"] = seeds[0]["score"] / 2


def score_on_an_unseeded_component(record):
    seeded = {s["node"] for s in record["retrieval"]["seeding"]["seeds"]}
    node = next(
        n["id"] for n in record["memory_input"]["nodes"] if n["type"] == "Component" and n["id"] not in seeded
    )
    record["retrieval"]["seeding"]["seeds"].append({"node": node, "score": 1.0})


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (seed_on_the_private_correct_lesson, "no sale de la traza"),
        (seed_on_a_cause_node, "no es Component"),
        (seed_on_the_lesson_node, "no es Component"),
        (seed_on_an_unknown_node, "no es Component"),
        (changed_score, "no sale de la traza"),
        (score_on_an_unseeded_component, "no sale de la traza"),
    ],
    ids=["private-correct-lesson", "cause-node", "lesson-node", "unknown-node", "score", "extra-component"],
)
def test_evaluator_rejects_a_seed_that_is_not_a_component_scored_by_the_trace(
    cell, tmp_path, change, message
):
    with pytest.raises(ValueError, match=message):
        evaluate(resealed(cell, tmp_path / "seed", change, at("C_S")))


def private_key_in_block(record):
    record["retrieval"]["seeding"]["hidden_cause_id"] = None


def causal_value_in_block(record):
    record["retrieval"]["seeding"]["lesson"] = METADATA[record["task"]["id"]]["hidden_cause_id"]


def family_inside_a_token(record):
    family = METADATA[record["task"]["id"]]["family"]
    record["retrieval"]["seeding"]["components"].append({"component": f"app/{family}.py", "weight": 1.0})


def private_path_in_block(record):
    record["retrieval"]["seeding"]["components"].append(
        {"component": "benchmark\\private\\tasks.json", "weight": 1.0}
    )


def private_path_in_context(record):
    record["initial_source"]["benchmark/private/tasks.json"] = "{}\n"
    record["initial_source_sha256"] = sources_digest(record["initial_source"])


@pytest.mark.parametrize(
    "change",
    [
        private_key_in_block,
        causal_value_in_block,
        family_inside_a_token,
        private_path_in_block,
        private_path_in_context,
    ],
    ids=["private-key", "causal-value", "family-token", "private-path", "context-path"],
)
@pytest.mark.parametrize("condition", ["C_S", "A"])
def test_evaluator_rejects_private_or_causal_material_in_the_seed(cell, tmp_path, change, condition):
    with pytest.raises(ValueError, match="material privado o causal"):
        evaluate(resealed(cell, tmp_path / "private", change, at(condition)))


def test_public_words_that_match_a_family_do_not_trip_the_private_material_guard(cell, tmp_path):
    """La búsqueda es por token exacto y solo en el bloque de siembra y en las rutas del contexto: no mira
    el código fuente ni el texto de la tarea, donde hay palabras públicas que coinciden con una familia."""
    words = " ".join(sorted({meta["family"] for meta in METADATA.values()})) + " hidden_cause_id"

    def public_words(record):
        record["task"]["expected"] += " " + words
        record["initial_source"]["app/config.py"] += f"\n# {words}\n"
        record["initial_source_sha256"] = sources_digest(record["initial_source"])
        consistent(record)

    def every_condition(record):
        return record["task"]["id"] == TARGET

    report = evaluate(resealed(cell, tmp_path / "public", public_words, every_condition))
    assert report["campaign"] == "nonlexical-seed-v1"


def emptied(record):
    record["retrieval"].update(memories=[], paths=[])
    record["retrieval"]["seeding"].update(state=EMPTY, lesson=None)
    consistent(record)


def other_components(record):
    record["retrieval"]["seeding"]["components"] = [{"component": "app/config.py", "weight": 1.0}]


@pytest.mark.parametrize(
    ("change", "condition"),
    [
        (lambda r: r["retrieval"]["seeding"].update(state=TIE), "C_S"),
        (emptied, "C_S"),
        (other_components, "C_S"),
        (other_components, "B"),
        (lambda r: r["retrieval"]["seeding"].update(seeds=[]), "C_L"),
        (lambda r: r["retrieval"].update(paths=[]), "C_L"),
        (lambda r: r["retrieval"]["memories"].pop(), "B"),
        (lambda r: r.update(retrieved_memories=[]), "C_S"),
        (lambda r: r["tests"][0].update(stderr=INJECTED), "A"),
    ],
    ids=[
        "state",
        "emptied",
        "components",
        "components-in-control",
        "seeds-in-control",
        "paths",
        "history",
        "retrieved-ids",
        "test0",
    ],
)
def test_evaluator_rejects_a_retrieval_that_does_not_replay(cell, tmp_path, change, condition):
    with pytest.raises(ValueError, match="recuperación sembrada no se repite"):
        evaluate(resealed(cell, tmp_path / "replay", change, at(condition)))


def reversed_plan(record):
    record["decision"]["plan"] = list(reversed(record["decision"]["plan"]))


def diagnostic_decision(record):
    record["decision"]["diagnostic"] = {"status": "ambiguous"}


@pytest.mark.parametrize("change", [reversed_plan, diagnostic_decision], ids=["plan", "diagnostic-field"])
@pytest.mark.parametrize("condition", ["C_S", "B"])
def test_evaluator_rejects_a_decision_that_is_not_the_default_plan(cell, tmp_path, change, condition):
    with pytest.raises(ValueError, match="decisión de la recuperación sembrada no se repite"):
        evaluate(resealed(cell, tmp_path / "decision", change, at(condition)))


def test_evaluator_requires_the_context_hash_to_cover_the_retrieval_inputs(cell, tmp_path):
    def default_context(record):
        record["agent_context_sha256"] = digest(
            {
                "task": record["task"],
                "files": record["initial_source"],
                "memories": record["retrieval"]["memories"],
            }
        )

    with pytest.raises(ValueError, match="contexto del agente no cubre"):
        evaluate(resealed(cell, tmp_path / "context", default_context, at("C_S")))

    def other_memory(record):
        record["memory_before_sha256"] = "0" * 64

    with pytest.raises(ValueError, match="memoria de entrada no es la que declara"):
        evaluate(resealed(cell, tmp_path / "memory", other_memory, at("C_S")))


H58_INPUTS = {"order": ["RETRIEVE", "test-0", "plan"], "reproduction": "test-0"}


def every_run_of(condition):
    return lambda r: r["condition"] == condition


@pytest.mark.parametrize(
    ("change", "select", "message"),
    [
        (lambda r: r.pop("decision_inputs"), at("C_S"), "reproducción previa"),
        (lambda r: r.update(decision_inputs=H58_INPUTS), at("C_S"), "reproducción previa"),
        (lambda r: r.update(decision_inputs={**DECISION_INPUTS, "x": 1}), at("C_S"), "reproducción previa"),
        (lambda r: r["tests"][0].update(returncode=0), at("C_S"), "reproducción previa"),
        (lambda r: r["tests"][0].update(id="test-9"), at("C_S"), "reproducción previa"),
        # Reetiquetar C_S como C_L, una ejecución o toda la secuencia, rompe antes la procedencia de sus
        # lecciones (citan recibos de otra condición o con otro sello).
        (lambda r: r.update(condition="C_L"), at("C_S"), "memory provenance"),
        (lambda r: r.update(condition="C_L"), every_run_of("C_S"), "memory provenance"),
        (lambda r: r.update(condition="B"), at("A"), "modo de memoria"),
        (lambda r: r.update(memory_mode="TEXT_HISTORY"), at("A"), "modo de memoria"),
        (lambda r: r["retrieval"]["seeding"].update(policy="x/v9"), at("C_S"), "política de siembra"),
        (lambda r: r["retrieval"]["seeding"].update(signal=None), at("C_S"), "política de siembra"),
        (lambda r: r["retrieval"]["seeding"].update(signal=TRACE), at("C_L"), "política de siembra"),
        (lambda r: r.update(condition="C"), at("A"), "sin condición"),
        (lambda r: r.pop("condition"), at("A"), "sin condición"),
        (lambda r: r.update(**{"pass": 1}), at("C_S"), "ajeno a la memoria de fallos"),
        (lambda r: r["retrieval"].pop("seeding"), at("C_S"), "sin condición o bloque"),
        (lambda r: r["retrieval"].update(seeding="trace"), at("C_S"), "sin condición o bloque"),
    ],
    ids=[
        "inputs-missing",
        "inputs-h58-order",
        "inputs-extra",
        "test0-passed",
        "test0-renamed",
        "relabelled-C_L",
        "relabelled-C_L-whole-sequence",
        "relabelled-B",
        "mode",
        "policy",
        "signal-dropped",
        "signal-claimed",
        "unknown-condition",
        "no-condition",
        "pass",
        "no-block",
        "block-not-a-dict",
    ],
)
def test_evaluator_requires_the_declared_order_condition_and_seed_policy(
    cell, tmp_path, change, select, message
):
    with pytest.raises(ValueError, match=message):
        evaluate(resealed(cell, tmp_path / "declared", change, select))


def test_evaluator_rejects_different_signals_within_one_cell(cell, tmp_path):
    def consistent_but_different(record):
        record["tests"][0]["stderr"] = INJECTED
        memories, paths, seeding = replay_retrieval(record)
        record["retrieval"] = {"memories": memories, "paths": paths, "seeding": seeding}
        consistent(record)

    with pytest.raises(ValueError, match="señales distintas"):
        evaluate(resealed(cell, tmp_path / "signal", consistent_but_different, at("A")))


def _drop_policy(record):
    record["decision"].pop("policy")


def _as_default_agent(record):
    record["agent"] = BoundedRepairAgent.name
    record["decision"].pop("policy")
    record.pop("decision_inputs")
    record.pop("condition")


def _as_diagnostic_agent(record):
    record["agent"] = DiagnosticRepairAgent.name
    record["decision"]["policy"] = "diagnostic-baseline/v1"
    record.pop("condition")


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (_drop_policy, "agent and decision policy disagree"),
        (
            lambda r: r["decision"].update(policy="diagnostic-baseline/v1"),
            "agent and decision policy disagree",
        ),
        (lambda r: r.update(agent="custom-repair-v1"), "unknown agent"),
        (_as_default_agent, "ajeno a la siembra"),
        (_as_diagnostic_agent, "ajeno a la siembra"),
        (lambda r: r.update(failure_memory_input=[]), "ajeno a la memoria de fallos"),
        (lambda r: r["decision"].update(failure_ids=[]), "ajeno a la memoria de fallos"),
        (lambda r: r.update(placebo=False), "ajeno a la transferencia"),
    ],
    ids=[
        "policy-omitted",
        "policy-of-another-agent",
        "unknown-agent",
        "default-agent-with-seed-block",
        "diagnostic-agent-with-seed-block",
        "failure-record-field",
        "failure-decision-field",
        "transfer-field",
    ],
)
def test_agent_policy_and_seed_fields_agree_both_ways(cell, tmp_path, change, message):
    with pytest.raises(ValueError, match=message):
        evaluate(resealed(cell, tmp_path / "coherence", change))


def test_evaluator_rejects_mixed_agents_in_one_directory(cell, tmp_path):
    mixed = resealed(cell, tmp_path / "mixed", lambda r: None)
    run_experiment("EXP-01", BoundedRepairAgent(), "NO_MEMORY", 7, evidence_dir=mixed, batch_id="other")
    with pytest.raises(ValueError, match="mix of agents or decision policies"):
        evaluate(mixed)


def test_evaluator_rejects_lessons_shared_between_the_two_associative_conditions(cell, tmp_path):
    donor = copy.deepcopy(find(runs_of(cell), "C_L")["memory_input"])

    def change(record):
        record["memory_input"] = copy.deepcopy(donor)
        record["memory_before_sha256"] = digest(donor)

    with pytest.raises(ValueError, match="memory provenance"):
        evaluate(resealed(cell, tmp_path / "lessons", change, at("C_S")))


# --- invariancia frente a las anotaciones privadas (sección 8) -------------------------------------


@pytest.fixture(scope="module")
def trace_runs(tmp_path_factory):
    """C_S sobre las nueve tareas (semilla 7, una réplica): solo para comparar igualdades."""
    evidence = tmp_path_factory.mktemp("trace-seed-all-tasks")
    with contextlib.redirect_stdout(io.StringIO()):  # sin resultados de EXP-07..09 en la salida capturada
        cli.seed_campaign([7], 1, evidence, conditions=("C_S",))
    return sorted(runs_of(evidence), key=lambda r: r["task"]["id"])


def copy_tree(target):
    for folder in ("src", "benchmark", "experiments/software_project"):
        shutil.copytree(
            ROOT / folder, target / folder, ignore=shutil.ignore_patterns("__pycache__", "*.egg-info")
        )
    return target


def permute_private_annotations(root):
    """Rota todos los campos de las anotaciones privadas entre las tareas de cada archivo: familia, causa,
    familia del señuelo, mutación (ruta y texto), tareas relevantes y de señuelo, distancia y partición."""
    changed = 0
    for name in ("tasks.json", "tasks_misleading.json"):
        path = root / "benchmark/private" / name
        annotations = json.loads(path.read_text("utf-8"))
        tasks = sorted(annotations)
        rotated = {task: annotations[tasks[(i + 1) % len(tasks)]] for i, task in enumerate(tasks)}
        changed += sum(rotated[task] != annotations[task] for task in tasks)
        path.write_text(json.dumps(rotated, indent=2) + "\n", encoding="utf-8")
    return changed


REPLAY = """
import json, sys
from experiments import trace_seed
cases = json.loads(open(sys.argv[1], encoding="utf-8").read())
out = [trace_seed.seeded_retrieval(c["memory"], c["stderr"], c["files"]) for c in cases]
print(json.dumps({"module": trace_seed.__file__, "retrievals": out}))
"""


def replay_in(root, cases):
    env = {**os.environ, "PYTHONPATH": str(root / "src"), "PYTHONUTF8": "1"}
    result = subprocess.run(
        [sys.executable, "-c", REPLAY, str(cases)],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    answer = json.loads(result.stdout)
    assert str(root) in answer["module"]  # control: se ejecutó el módulo de la copia, no el del checkout
    return answer["retrievals"]


def test_seeding_is_invariant_to_private_annotations_and_works_without_them(trace_runs, tmp_path):
    assert [r["task"]["id"] for r in trace_runs] == list(TASK_SETS["misleading-v1"])
    recorded, cases = [], []
    for r in trace_runs:
        block = {k: v for k, v in r["retrieval"]["seeding"].items() if k != "signal"}
        recorded.append([r["retrieval"]["memories"], r["retrieval"]["paths"], block])
        cases.append(
            {
                "memory": r["memory_input"],
                "stderr": r["tests"][0]["stderr"],
                "files": list(r["initial_source"]),
            }
        )
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(cases), encoding="utf-8")
    permuted = copy_tree(tmp_path / "permuted")
    assert permute_private_annotations(permuted) == len(METADATA) == 9  # control: todas cambiaron
    assert private_metadata(permuted) != METADATA
    assert replay_in(permuted, path) == recorded
    absent = copy_tree(tmp_path / "absent")
    shutil.rmtree(absent / "benchmark/private")
    assert replay_in(absent, path) == recorded
    assert json.loads(json.dumps(recorded)) == recorded  # control: la comparación es sobre JSON


# --- receta y CLI ---------------------------------------------------------------------------------


def test_cli_nonlexical_seed_campaign_fixes_configuration_and_directory(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "seed_campaign", lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setattr(cli, "transfer_campaign", lambda *args, **kwargs: calls.append(("h7", args, kwargs)))
    monkeypatch.setattr(cli, "campaign", lambda *args, **kwargs: calls.append(("default", args, kwargs)))
    monkeypatch.setattr(sys, "argv", ["experiments", "run", "--campaign", "nonlexical-seed-v1"])
    cli.main()
    (seeds, replicates, evidence_dir, train, transfer), kwargs = calls[0]
    assert (seeds, replicates) == ([1, 4, 5, 6, 7, 9], 2) and kwargs == {}
    assert (train, transfer) == (NONLEXICAL_SEED_CAMPAIGN["train"], NONLEXICAL_SEED_CAMPAIGN["transfer"])
    assert evidence_dir == ROOT / "evidence/nonlexical-seed-v1"
    for extra in (["--replicates", "1"], ["--seeds", "7"], ["--task-set", "v1"]):
        monkeypatch.setattr(sys, "argv", ["experiments", "run", "--campaign", "nonlexical-seed-v1", *extra])
        with pytest.raises(SystemExit):
            cli.main()
    # Las recetas anteriores no cambian: ni directorio, ni agente, ni receta.
    calls.clear()
    for argv in (
        ["--campaign", "failure-transfer-v1"],
        ["--campaign", "diagnostic-baseline-v1"],
        ["--campaign", "reference-v2"],
        [],
    ):
        monkeypatch.setattr(sys, "argv", ["experiments", "run", *argv])
        cli.main()
    assert calls == [
        (
            "h7",
            (
                [1, 4, 5, 6, 7, 9],
                2,
                ROOT / "evidence/failure-transfer-v1",
                FAILURE_TRANSFER_CAMPAIGN["train"],
                FAILURE_TRANSFER_CAMPAIGN["transfer"],
            ),
            {},
        ),
        (
            "default",
            ([1, 4, 5, 6, 7, 9], 2, ROOT / DIAGNOSTIC_CAMPAIGN["evidence_dir"], TASK_SETS["misleading-v1"]),
            {"agent_factory": DiagnosticRepairAgent},
        ),
        (
            "default",
            (list(REFERENCE_CAMPAIGN["seeds"]), 2, ROOT / "evidence/runs", TASK_SETS["misleading-v1"]),
            {},
        ),
        ("default", ([7, 11, 23], 2, ROOT / "evidence/runs", TASK_SETS["v1"]), {}),
    ]


def test_seed_campaign_refuses_bad_replication_conditions_and_a_misdeclared_split(tmp_path):
    with pytest.raises(ValueError, match="unique seeds"):
        cli.seed_campaign([7, 7], 1, tmp_path)
    with pytest.raises(ValueError, match="unique seeds"):
        cli.seed_campaign([7], 0, tmp_path)
    for conditions in ((), ("A", "A"), ("A", "C"), ("C_S", "A_N")):
        with pytest.raises(ValueError, match="condiciones de siembra"):
            cli.seed_campaign([7], 1, tmp_path, conditions=conditions)
    with pytest.raises(RuntimeError, match="partición declarada"):
        cli.seed_campaign([7], 1, tmp_path, train=(TARGET,), transfer=(), conditions=("A",))


def test_seed_campaign_stops_on_a_harness_error(tmp_path, monkeypatch):
    def broken(*args, **kwargs):
        raise ValueError("fixture rota (test sintético)")

    monkeypatch.setattr(runner, "prepare", broken)
    with pytest.raises(RuntimeError, match="fixture rota"):
        cli.seed_campaign([7], 1, tmp_path, train=(TRAIN[0],), transfer=(), conditions=("C_S",))
    (receipt,) = receipts_of(tmp_path)
    assert receipt["result"] == "ERROR" and receipt["condition"] == "C_S"
    with pytest.raises(ValueError, match="Harness ERROR receipts"):
        evaluate(tmp_path)
