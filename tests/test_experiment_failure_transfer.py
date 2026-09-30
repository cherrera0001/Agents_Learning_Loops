"""Transferencia de fallos (H7, #65) sobre trazas y recibos sintéticos: alcance τ, placebo y condiciones.

Ningún test de este archivo ejecuta una reparación real ni lee un recibo publicado. El alcance, el placebo
y las condiciones son los del pre-registro (``docs/preregistration/failure-transfer.md``, secciones 3 a 5);
ninguno exige una ganancia.
"""

import ast
import inspect
import itertools
import json
import re
from pathlib import Path

import pytest

from associative_agent_loop.memory.text import cosine_similarity
from experiments import failure_transfer
from experiments.agent import STRATEGIES
from experiments.benchmark import FAILURE_MEMORY_CAMPAIGN, FAILURE_TRANSFER_CAMPAIGN
from experiments.diagnostic import DiagnosticRepairAgent, failure_features
from experiments.evidence import RECEIPT_SCHEMA, SOURCE_HASH_NORMALIZATION, publish
from experiments.failure_memory import AGENT_NAME as FAILURE_AGENT
from experiments.failure_memory import TAU, FailureMemory, FailureMemoryRepairAgent, FailureView
from experiments.failure_transfer import (
    AGENT_NAME,
    CONDITIONS,
    DECISION_INPUTS,
    POLICY,
    ROTATION,
    TAUS,
    FailureTransferRepairAgent,
    TransferFailureMemory,
    TransferView,
    condition_of,
    rotate,
)
from experiments.runner import run_experiment

IDENTITY, ENVIRONMENT, STORAGE = STRATEGIES
SEEDS = FAILURE_TRANSFER_CAMPAIGN["seeds"]
TRANSFER_KEYS = {"failure_scope_tau", "failure_placebo", "failure_recorded_strategies"}


def one(exception, outcome="ERROR"):
    """Salida sintética de unittest con un solo bloque de fallo (la misma forma que en H6)."""
    return (
        "test_contract (test_contract.Contract.test_contract) ... ERROR\n\n"
        + "=" * 70
        + f"\n{outcome}: test_contract (test_contract.Contract.test_contract)\n"
        + "-" * 70
        + '\nTraceback (most recent call last):\n  File "<workspace>/app/x.py", line 3, in f\n    g()\n'
        + exception
        + "\n\n"
        + "-" * 70
        + "\nRan 2 tests in 0.004s\n\nFAILED (errors=1)\n"
    )


DECISIVE = one("ConnectionError: refused")
PARTIAL = one("TypeError: 'NoneType' object is not subscriptable")
AMBIGUOUS = one("AssertionError: 1 != 2", "FAIL")
OTHER = one("KeyError: 'k'")  # firma distinta de las tres anteriores y de la vacía
TASK = {"id": "T-1", "title": "a request fails", "context": "when the profile is missing"}
QUERY = TASK["title"] + " " + TASK["context"]


def lesson(strategy):
    return {"id": f"lesson:{strategy}", "task": "T-0", "symptom": QUERY, "strategy": strategy, "rule": "r"}


LESSON_CASES = [((), "NO_MEMORY")] + [((lesson(s),), "ASSOCIATIVE_MEMORY") for s in STRATEGIES]
LESSON_CASES += [(tuple(lesson(s) for s in STRATEGIES), "TEXT_HISTORY")]


def record(strategy, stderr=PARTIAL, query=QUERY, n=0):
    evidence = f"RUN-{n}#test-1"
    return {
        "id": "failure:" + evidence,
        "strategy": strategy,
        "query": query,
        "signature": failure_features(stderr),
        "evidence": evidence,
        "receipt_sha256": "0" * 64,
    }


def reproduction(stderr):
    return {"returncode": 1, "stderr": stderr}


def decide(stderr, seed, failures=(), memories=(), mode="NO_MEMORY", task=TASK, tau=TAU, placebo=False):
    view = TransferView(
        task,
        {},
        tuple(memories),
        mode,
        seed,
        reproduction(stderr),
        failures=tuple(failures),
        scope_tau=tau,
        placebo=placebo,
    )
    return FailureTransferRepairAgent().plan(view)


def h6_decision(stderr, seed, failures=(), memories=(), mode="NO_MEMORY", task=TASK):
    view = FailureView(task, {}, tuple(memories), mode, seed, reproduction(stderr), failures=tuple(failures))
    return FailureMemoryRepairAgent().plan(view)


def as_h6(decision):
    """La decisión de H7 sin sus campos aditivos (``policy`` aparte)."""
    out = {k: v for k, v in decision.items() if k not in TRANSFER_KEYS}
    out["failure_scope"] = [{k: v for k, v in s.items() if k != "demotes"} for s in out["failure_scope"]]
    return out


def words(n, first="alpha"):
    """Una clave con ``n`` palabras distintas; su coseno con ``first`` es exactamente 1/√n."""
    return " ".join([first, *(f"w{i}" for i in range(n - 1))])


# --- contrato declarado -------------------------------------------------------------------------


def test_conditions_taus_rotation_and_campaign_are_the_preregistered_ones():
    assert TAUS == {"50": 0.5, "25": 0.25, "10": 0.1, "00": 0.0}
    expected = {}
    for base, mode in (("A", "NO_MEMORY"), ("C", "ASSOCIATIVE_MEMORY")):
        expected[base] = (mode, False, None, False)
        for variant, placebo in (("R", False), ("P", True)):
            for suffix, tau in (("50", 0.5), ("25", 0.25), ("10", 0.1), ("00", 0.0)):
                expected[f"{base}_{variant}{suffix}"] = (mode, True, tau, placebo)
    assert expected == CONDITIONS and list(CONDITIONS) == list(expected) and len(CONDITIONS) == 18
    assert list(CONDITIONS)[:9] == [
        "A",
        "A_R50",
        "A_R25",
        "A_R10",
        "A_R00",
        "A_P50",
        "A_P25",
        "A_P10",
        "A_P00",
    ]
    # Sección 4: STRATEGIES[i] → STRATEGIES[(i + 1) mod 3], sobre el orden de agent.py.
    assert ROTATION == {IDENTITY: ENVIRONMENT, ENVIRONMENT: STORAGE, STORAGE: IDENTITY}
    assert [rotate(s) for s in STRATEGIES] == [STRATEGIES[(i + 1) % 3] for i in range(3)]
    assert POLICY == "failure-transfer/v1"
    assert AGENT_NAME == FAILURE_AGENT + "+failure-transfer-v1" == FAILURE_TRANSFER_CAMPAIGN["agent"]
    assert DECISION_INPUTS == {
        "order": ["RETRIEVE", "test-0", "plan"],
        "reproduction": "test-0",
        "failures": "failure_memory_input",
        "failure_scope_tau": "failure_scope_tau",
        "placebo": "placebo",
    }
    campaign = FAILURE_TRANSFER_CAMPAIGN
    assert campaign["name"] == "failure-transfer-v1"
    assert (campaign["seeds"], campaign["replicates"]) == ((1, 4, 5, 6, 7, 9), 2)
    assert campaign["train"] == ("EXP-01", "EXP-02", "EXP-03") == FAILURE_MEMORY_CAMPAIGN["train"]
    assert campaign["transfer"] == tuple(f"EXP-{i:02d}" for i in range(4, 10))
    assert campaign["passes"] == 1 and campaign["conditions"] == tuple(CONDITIONS)
    assert campaign["taus"] == tuple(TAUS.values())
    assert campaign["evidence_dir"] == "evidence/failure-transfer-v1"
    assert FailureTransferRepairAgent.reads_reproduction and FailureTransferRepairAgent.reads_failures
    assert FailureTransferRepairAgent.failure_transfer
    assert not getattr(FailureMemoryRepairAgent, "failure_transfer", False)
    assert not getattr(DiagnosticRepairAgent, "failure_transfer", False)
    with pytest.raises(ValueError, match="desconocida"):
        condition_of("A_N")


# --- τ = 0.5 sin placebo es H6 ------------------------------------------------------------------


RECORD_SETS = [
    (),
    (record(IDENTITY),),
    (record(IDENTITY, n=1), record(ENVIRONMENT, n=2)),
    (record(STORAGE, DECISIVE),),
    (record(IDENTITY, AMBIGUOUS), record(STORAGE, OTHER, n=3)),
    (record(ENVIRONMENT, query="unrelated words entirely"),),
    (record(IDENTITY, query=words(4, "a request")), record(STORAGE, query=words(16), n=4)),
]


@pytest.mark.parametrize(
    "stderr", [DECISIVE, PARTIAL, AMBIGUOUS, ""], ids=["decisive", "partial", "ambiguous", "none"]
)
@pytest.mark.parametrize("failures", RECORD_SETS, ids=[f"records-{i}" for i in range(len(RECORD_SETS))])
def test_tau_half_without_placebo_reproduces_h6_exactly(stderr, failures):
    for seed, (memories, mode) in itertools.product(SEEDS, LESSON_CASES):
        decision = decide(stderr, seed, failures, memories, mode)
        reference = h6_decision(stderr, seed, failures, memories, mode)
        assert as_h6(decision) == {**reference, "policy": POLICY}
        assert (decision["failure_scope_tau"], decision["failure_placebo"]) == (0.5, False)
        assert all(s["demotes"] == s["strategy"] for s in decision["failure_scope"])
        applied = {r["strategy"] for r in failures if r["id"] in decision["failure_ids"]}
        assert decision["failure_recorded_strategies"] == decision["failure_strategies"]
        assert decision["failure_recorded_strategies"] == [s for s in STRATEGIES if s in applied]


# --- alcance ------------------------------------------------------------------------------------


def test_each_tau_includes_its_own_boundary_and_excludes_just_below():
    task = {"id": "T-2", "title": "alpha", "context": ""}
    for tau, n in ((0.5, 4), (0.25, 16), (0.1, 100)):
        assert cosine_similarity("alpha", words(n)) == tau  # frontera exacta en coma flotante
        assert cosine_similarity("alpha", words(n + 1)) < tau
        at = record(IDENTITY, query=words(n))
        below = record(IDENTITY, query=words(n + 1), n=1)
        scopes = decide(PARTIAL, 7, [at, below], task=task, tau=tau)["failure_scope"]
        assert [s["applies"] for s in scopes] == [True, False]
        assert scopes[0]["similarity"] == tau


def test_lower_tau_applies_a_superset_and_tau_zero_needs_only_the_signature():
    task = {"id": "T-2", "title": "alpha", "context": ""}
    items = [record(IDENTITY, query=words(n), n=n) for n in (1, 2, 4, 5, 16, 17, 100, 101)] + [
        record(ENVIRONMENT, query="omega", n=200),
        record(STORAGE, OTHER, query="alpha", n=201),
    ]
    applied = {}
    for tau in (0.5, 0.25, 0.1, 0.0):
        scopes = decide(PARTIAL, 7, items, task=task, tau=tau)["failure_scope"]
        applied[tau] = [s["applies"] for s in scopes]
        for s in scopes:
            assert s["applies"] == (s["signature_match"] and s["similarity"] >= tau)
    for high, low in itertools.pairwise((0.5, 0.25, 0.1, 0.0)):
        assert all(
            b for a, b in zip(applied[high], applied[low], strict=True) if a
        )  # más bajo, superconjunto
    assert applied[0.0][-2:] == [True, False]  # similitud 0 con la misma firma aplica; otra firma, nunca
    assert cosine_similarity("alpha", "omega") == 0.0
    assert sum(applied[0.5]) < sum(applied[0.25]) < sum(applied[0.1]) < sum(applied[0.0])


# --- placebo ------------------------------------------------------------------------------------


def test_placebo_demotes_the_rotated_strategy_with_the_same_scope_and_records():
    for seed, (memories, mode) in itertools.product(SEEDS, LESSON_CASES):
        for strategy in STRATEGIES:
            items = (record(strategy), record(STORAGE, OTHER, n=9))
            snapshot = json.dumps(items)
            real = decide(PARTIAL, seed, items, memories, mode, tau=0.0)
            placebo = decide(PARTIAL, seed, items, memories, mode, tau=0.0, placebo=True)
            assert json.dumps(items) == snapshot  # el registro no cambia
            assert [s["applies"] for s in placebo["failure_scope"]] == [
                s["applies"] for s in real["failure_scope"]
            ]
            assert placebo["failure_ids"] == real["failure_ids"] == [items[0]["id"]]
            assert placebo["failure_placebo"] and not real["failure_placebo"]
            assert placebo["failure_recorded_strategies"] == real["failure_recorded_strategies"] == [strategy]
            assert real["failure_strategies"] == [strategy]
            assert placebo["failure_strategies"] == [ROTATION[strategy]]
            assert [s["demotes"] for s in placebo["failure_scope"]] == [ROTATION[strategy], IDENTITY]
            # Con la estrategia rotada, el placebo es la decisión real de un registro de esa estrategia.
            rotated = decide(PARTIAL, seed, (record(ROTATION[strategy]),), memories, mode, tau=0.0)
            assert placebo["plan"] == rotated["plan"]
            assert placebo["plan_without_failures"] == real["plan_without_failures"]
            assert placebo["failure_effect"] == rotated["failure_effect"]


def test_placebo_of_all_three_strategies_demotes_the_same_set():
    items = tuple(record(s, AMBIGUOUS, n=i) for i, s in enumerate(STRATEGIES))
    for seed in SEEDS:
        real = decide(AMBIGUOUS, seed, items, tau=0.0)
        placebo = decide(AMBIGUOUS, seed, items, tau=0.0, placebo=True)
        assert real["plan"] == placebo["plan"] and real["failure_strategies"] == list(STRATEGIES)


def test_placebo_changes_the_first_attempt_differently_from_the_real_record():
    """Con D parcial ({identidad, entorno}), un fallo registrado de la primera estrategia la baja en la
    real; en el placebo baja la siguiente, así que el primer intento puede no cambiar."""
    changed = {"real": 0, "placebo": 0}
    for seed in SEEDS:
        first = decide(PARTIAL, seed, tau=0.0)["plan"][0]
        real = decide(PARTIAL, seed, [record(first)], tau=0.0)
        placebo = decide(PARTIAL, seed, [record(first)], tau=0.0, placebo=True)
        assert real["failure_effect"] == "changed_first" and real["plan"][0] != first
        changed["real"] += real["failure_effect"] == "changed_first"
        changed["placebo"] += placebo["failure_effect"] == "changed_first"
    assert changed["real"] == len(SEEDS) > changed["placebo"]


# --- bases sin memoria de fallos ----------------------------------------------------------------


def test_bases_without_scope_decide_as_h6_with_an_empty_memory_and_refuse_records():
    for seed, (memories, mode) in itertools.product(SEEDS, LESSON_CASES):
        decision = decide(PARTIAL, seed, (), memories, mode, tau=None)
        assert as_h6(decision) == {**h6_decision(PARTIAL, seed, (), memories, mode), "policy": POLICY}
        assert (decision["failure_scope_tau"], decision["failure_placebo"]) == (None, False)
        assert decision["failure_effect"] == "none"
    with pytest.raises(ValueError, match="sin alcance declarado"):
        decide(PARTIAL, 7, [record(IDENTITY)], tau=None)
    with pytest.raises(ValueError, match="sin alcance declarado"):
        decide(PARTIAL, 7, (), tau=None, placebo=True)


def test_the_decision_ignores_task_identity_and_record_provenance():
    items = [record(IDENTITY, n=1), record(ENVIRONMENT, n=2)]
    renamed = [{**r, "evidence": "RUN-x#test-2", "receipt_sha256": "f" * 64} for r in items]
    for seed, placebo, tau in itertools.product(SEEDS, (False, True), (0.5, 0.0)):
        reference = decide(PARTIAL, seed, items, tau=tau, placebo=placebo)
        assert (
            decide(PARTIAL, seed, renamed, task={**TASK, "id": "EXP-99"}, tau=tau, placebo=placebo)
            == reference
        )


def test_the_view_carries_no_private_or_task_keyed_data():
    view = TransferView(
        TASK, {}, (), "NO_MEMORY", 7, reproduction(PARTIAL), failures=(record(IDENTITY),), scope_tau=0.0
    )
    serialized = json.dumps(view.__dict__)
    for forbidden in (
        "hidden_cause_id",
        "relevant_training_tasks",
        "golden_patch",
        "mutation",
        "EXP-",
        "decoy",
    ):
        assert forbidden not in serialized
    assert view.failures[0]["query"] == QUERY


def test_generic_audit_no_task_ids_private_data_or_controller_imports():
    tree = ast.parse(Path(inspect.getfile(failure_transfer)).read_text("utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add("." * node.level + (node.module or ""))
    assert imported == {"dataclasses", ".agent", ".failure_memory"}
    docstrings = {
        id(n.body[0].value)
        for n in ast.walk(tree)
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef))
        and n.body
        and isinstance(n.body[0], ast.Expr)
        and isinstance(n.body[0].value, ast.Constant)
    }
    tokens = [
        n.value
        for n in ast.walk(tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstrings
    ]
    tokens += [n.id for n in ast.walk(tree) if isinstance(n, ast.Name)]
    tokens += [n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)]
    forbidden = re.compile(r"EXP-\d|benchmark|private|hidden_cause|golden|mutation|decoy|relevant_training")
    assert not [t for t in tokens if forbidden.search(t)]


# --- memoria de fallos de H7 --------------------------------------------------------------------


def source(tmp_path, condition="A_R00", agent=AGENT_NAME, run_id="RUN-src"):
    """Recibo task_run sintético y sellado con un intento fallido y uno que pasa."""
    tests = [
        {"id": "test-0", "returncode": 1, "stderr": PARTIAL},
        {"id": "test-1", "returncode": 1, "stderr": "attempt 1"},
        {"id": "test-2", "returncode": 0, "stderr": "attempt 2"},
    ]
    record_ = {
        "schema_id": RECEIPT_SCHEMA,
        "source_hash_normalization": SOURCE_HASH_NORMALIZATION,
        "kind": "task_run",
        "run_id": run_id,
        "batch_id": "BATCH-x",
        "seed": 7,
        "agent": agent,
        "condition": condition,
        "task": TASK,
        "result": "PASS",
        "tests": tests,
        "actions": [{"iteration": 1, "strategy": IDENTITY}, {"iteration": 2, "strategy": ENVIRONMENT}],
    }
    return publish(tmp_path, record_)


def test_h7_failure_memory_is_written_only_from_its_real_and_placebo_variants(tmp_path):
    for condition in ("A_R00", "C_P50"):
        memory = TransferFailureMemory()
        changes = memory.consolidate(source(tmp_path / condition, condition))
        assert [c["evidence"] for c in changes] == ["RUN-src#test-1"]
        assert memory.records[0]["strategy"] == IDENTITY  # el registro guarda la estrategia real
        assert isinstance(memory.copy(), TransferFailureMemory)
    for condition, agent in (
        ("A", AGENT_NAME),
        ("C", AGENT_NAME),
        ("A_N", FAILURE_AGENT),
        ("A_R00", FAILURE_AGENT),
    ):
        with pytest.raises(ValueError, match=r"solo se escribe|desconocida"):
            TransferFailureMemory().consolidate(
                source(tmp_path / f"{condition}-{agent[-4:]}", condition, agent)
            )
    # Y la memoria de H6 no acepta recibos de H7.
    with pytest.raises(ValueError, match=r"solo se escribe|desconocida"):
        FailureMemory().consolidate(source(tmp_path / "h6", "A_R00"))


@pytest.mark.parametrize(
    ("agent", "kwargs"),
    [
        (FailureTransferRepairAgent(), {}),  # agente de H7 sin condición
        (FailureTransferRepairAgent(), {"condition": "A_N", "pass_number": 1}),  # condición de H6
        (FailureTransferRepairAgent(), {"condition": "A", "pass_number": 1}),  # con pasada
        (FailureTransferRepairAgent(), {"condition": "A_R00"}),  # variante sin memoria de fallos
        (FailureTransferRepairAgent(), {"condition": "A", "failures": TransferFailureMemory()}),
        (FailureTransferRepairAgent(), {"condition": "C_R50"}),  # modo de C con NO_MEMORY
        (FailureTransferRepairAgent(), {"condition": "B_R50", "failures": TransferFailureMemory()}),
        (FailureMemoryRepairAgent(), {"condition": "A_R00", "pass_number": 1, "failures": FailureMemory()}),
        (DiagnosticRepairAgent(), {"condition": "A"}),
    ],
    ids=[
        "no-condition",
        "h6-condition",
        "pass",
        "variant-without-memory",
        "base-with-memory",
        "mode",
        "unknown",
        "h6-agent",
        "other-agent",
    ],
)
def test_runner_refuses_inconsistent_failure_transfer_arguments(tmp_path, agent, kwargs):
    with pytest.raises(ValueError, match=r"exige su agente|no concuerdan"):
        run_experiment("EXP-01", agent, "NO_MEMORY", 7, evidence_dir=tmp_path, **kwargs)
    assert not list(tmp_path.glob("RUN-*.json"))
