"""Memoria de fallos (H6, #63) sobre trazas y recibos sintéticos: política, alcance y registros.

Ningún test de este archivo ejecuta una reparación real ni lee un recibo publicado. La política y el
alcance son los del pre-registro (``docs/preregistration/failure-memory.md``, secciones 2 y 3); ninguno
exige una ganancia.
"""

import ast
import inspect
import itertools
import json
import re
from pathlib import Path

import pytest

from associative_agent_loop.memory.text import cosine_similarity
from experiments import failure_memory
from experiments.agent import STRATEGIES, BoundedRepairAgent, prior_order
from experiments.benchmark import DIAGNOSTIC_CAMPAIGN, FAILURE_MEMORY_CAMPAIGN, TASK_SETS
from experiments.diagnostic import DiagnosticRepairAgent, DiagnosticView, failure_features, joint_plan
from experiments.evidence import RECEIPT_SCHEMA, SOURCE_HASH_NORMALIZATION, publish, read_receipt
from experiments.failure_memory import (
    AGENT_NAME,
    CONDITIONS,
    DECISION_INPUTS,
    POLICY,
    STORE,
    TAU,
    FailureMemory,
    FailureMemoryRepairAgent,
    FailureView,
    failure_plan,
    failure_records,
)
from experiments.runner import run_experiment, update_failure_memory

IDENTITY, ENVIRONMENT, STORAGE = STRATEGIES
SEEDS = DIAGNOSTIC_CAMPAIGN["seeds"]
FAILURE_KEYS = {
    "plan_without_failures",
    "failure_scope",
    "failure_ids",
    "failure_strategies",
    "failure_effect",
}


def one(exception, outcome="ERROR"):
    """Salida sintética de unittest con un solo bloque de fallo."""
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


def decide(stderr, seed, failures=(), memories=(), mode="NO_MEMORY", task=TASK):
    view = FailureView(task, {}, tuple(memories), mode, seed, reproduction(stderr), failures=tuple(failures))
    return FailureMemoryRepairAgent().plan(view)


def diagnostic_decision(stderr, seed, memories=(), mode="NO_MEMORY", task=TASK):
    view = DiagnosticView(task, {}, tuple(memories), mode, seed, reproduction(stderr))
    return DiagnosticRepairAgent().plan(view)


# --- contrato declarado -------------------------------------------------------------------------


def test_conditions_policy_and_campaign_are_the_preregistered_ones():
    assert CONDITIONS == {
        "A": ("NO_MEMORY", False),
        "A_N": ("NO_MEMORY", True),
        "C": ("ASSOCIATIVE_MEMORY", False),
        "C_N": ("ASSOCIATIVE_MEMORY", True),
    }
    assert TAU == 0.5 and POLICY == STORE == "failure-memory/v1"
    assert AGENT_NAME == DiagnosticRepairAgent.name + "+failure-memory-v1" == FAILURE_MEMORY_CAMPAIGN["agent"]
    assert DECISION_INPUTS == {
        "order": ["RETRIEVE", "test-0", "plan"],
        "reproduction": "test-0",
        "failures": "failure_memory_input",
    }
    campaign = FAILURE_MEMORY_CAMPAIGN
    assert (campaign["name"], campaign["seeds"], campaign["replicates"]) == ("failure-memory-v1", SEEDS, 2)
    assert campaign["seeds"] == (1, 4, 5, 6, 7, 9)
    assert campaign["train"] == TASK_SETS["misleading-v1"][:3] == ("EXP-01", "EXP-02", "EXP-03")
    assert campaign["transfer"] == tuple(f"EXP-{i:02d}" for i in range(4, 10))
    assert (campaign["passes"], campaign["conditions"]) == (2, tuple(CONDITIONS))
    assert campaign["evidence_dir"] == "evidence/failure-memory-v1"
    assert FailureMemoryRepairAgent.reads_reproduction and FailureMemoryRepairAgent.reads_failures
    assert not getattr(BoundedRepairAgent, "reads_failures", False)
    assert not getattr(DiagnosticRepairAgent, "reads_failures", False)


# --- política -----------------------------------------------------------------------------------


NOT_APPLYING = (record(STORAGE, stderr=OTHER), record(IDENTITY, query="unrelated words entirely"))


@pytest.mark.parametrize(
    "stderr", [DECISIVE, PARTIAL, AMBIGUOUS, ""], ids=["decisive", "partial", "ambiguous", "none"]
)
@pytest.mark.parametrize("failures", [(), NOT_APPLYING], ids=["empty", "not-applying"])
def test_empty_f_reproduces_the_diagnostic_decision_of_58_exactly(stderr, failures):
    for seed, (memories, mode) in itertools.product(SEEDS, LESSON_CASES):
        decision = decide(stderr, seed, failures, memories, mode)
        base = diagnostic_decision(stderr, seed, memories, mode)
        assert {k: v for k, v in decision.items() if k not in FAILURE_KEYS} == {**base, "policy": POLICY}
        assert decision["plan_without_failures"] == base["plan"] == decision["plan"]
        assert (decision["failure_effect"], decision["failure_ids"], decision["failure_strategies"]) == (
            "none",
            [],
            [],
        )
        assert [s["applies"] for s in decision["failure_scope"]] == [False] * len(failures)


def test_every_plan_follows_the_preregistered_key_and_stays_a_permutation():
    subsets = [set(c) for n in range(4) for c in itertools.combinations(STRATEGIES, n)]
    candidate_sets = [[STORAGE], [IDENTITY, ENVIRONMENT], list(STRATEGIES)]
    for candidates, proposal, failed, seed in itertools.product(
        candidate_sets, [None, *STRATEGIES], subsets, SEEDS
    ):
        prior = prior_order(seed)
        plan = failure_plan(prior, candidates, proposal, failed)
        assert sorted(plan) == sorted(STRATEGIES)  # nunca elimina operadores
        blocks = [(op not in candidates, op in failed) for op in plan]
        assert blocks == sorted(blocks)  # D acota primero; dentro, lo que no falló antes que lo que falló
        for block in set(blocks):
            members = [op for op, b in zip(plan, blocks, strict=True) if b == block]
            rest = [op for op in members if op != proposal]
            assert members == ([proposal] if proposal in members else []) + sorted(rest, key=prior.index)
        if not failed:
            assert plan == joint_plan(prior, candidates, proposal)[0]


def test_failure_memory_demotes_a_failed_lesson_proposal_but_never_overrides_d():
    for seed in SEEDS:
        # Ambiguo: la lección propone IDENTITY, que ya falló; baja al final.
        decision = decide(
            AMBIGUOUS, seed, [record(IDENTITY, AMBIGUOUS)], [lesson(IDENTITY)], "ASSOCIATIVE_MEMORY"
        )
        assert decision["memory_proposal"] == IDENTITY and decision["plan"][-1] == IDENTITY
        assert decision["plan_without_failures"][0] == IDENTITY
        assert decision["failure_effect"] == "changed_first"
        # Decisivo: aunque STORAGE ya falló, sigue primero; la memoria de fallos solo reordena el resto.
        decisive = decide(DECISIVE, seed, [record(STORAGE, DECISIVE)])
        assert decisive["plan"][0] == STORAGE and decisive["failure_effect"] == "no_change"
        assert decisive["failure_strategies"] == [STORAGE]


def test_failure_effect_distinguishes_none_no_change_and_changed_first():
    for seed in SEEDS:
        base = decide(PARTIAL, seed)
        first, second = base["plan"][:2]
        assert base["failure_effect"] == "none"
        moved = decide(PARTIAL, seed, [record(first)])
        assert moved["failure_effect"] == "changed_first" and moved["plan"][0] == second
        assert moved["plan_without_failures"] == base["plan"]
        kept = decide(PARTIAL, seed, [record(base["plan"][-1])])
        assert kept["failure_effect"] == "no_change" and kept["plan"] == base["plan"]
        both = decide(PARTIAL, seed, [record(first, n=1), record(second, n=2)])
        assert both["failure_ids"] == ["failure:RUN-1#test-1", "failure:RUN-2#test-1"]
        assert both["failure_strategies"] == [s for s in STRATEGIES if s in (first, second)]


def test_scope_requires_identical_signature_and_similarity_of_at_least_tau():
    assert cosine_similarity("alpha", "alpha beta gamma delta") == 0.5  # frontera exacta en coma flotante
    assert cosine_similarity("alpha", "alpha beta gamma delta epsilon") < 0.5
    task = {"id": "T-2", "title": "alpha", "context": ""}
    cases = [
        (record(IDENTITY, OTHER, query="alpha"), False, 1.0, False),  # misma clave, otra firma
        (record(IDENTITY, PARTIAL, query="omega"), True, 0.0, False),  # misma firma, otra clave
        (record(IDENTITY, PARTIAL, query="alpha beta gamma delta"), True, 0.5, True),  # τ incluido
        (record(IDENTITY, PARTIAL, query="alpha beta gamma delta epsilon"), True, None, False),
    ]
    for item, signature_match, similarity, applies in cases:
        (scope,) = decide(PARTIAL, 7, [item], task=task)["failure_scope"]
        assert (scope["strategy"], scope["signature_match"], scope["applies"]) == (
            IDENTITY,
            signature_match,
            applies,
        )
        if similarity is not None:
            assert scope["similarity"] == similarity


def test_the_decision_ignores_task_identity_and_record_provenance():
    items = [record(IDENTITY, n=1), record(ENVIRONMENT, n=2)]
    renamed = [{**r, "evidence": "RUN-x#test-2", "receipt_sha256": "f" * 64} for r in items]
    for seed in SEEDS:
        reference = decide(PARTIAL, seed, items)
        other_task = decide(PARTIAL, seed, renamed, task={**TASK, "id": "EXP-99"})
        assert {k: v for k, v in other_task.items()} == reference


def test_the_view_carries_no_private_or_task_keyed_data():
    view = FailureView(TASK, {}, (), "NO_MEMORY", 7, reproduction(PARTIAL), failures=(record(IDENTITY),))
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
    assert set(view.failures[0]) == {"id", "strategy", "query", "signature", "evidence", "receipt_sha256"}


def test_generic_audit_no_task_ids_private_data_or_controller_imports():
    tree = ast.parse(Path(inspect.getfile(failure_memory)).read_text("utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add("." * node.level + (node.module or ""))
    assert imported == {
        "copy",
        "dataclasses",
        "associative_agent_loop.memory.text",
        ".agent",
        ".diagnostic",
        ".evidence",
    }
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


# --- registros de fallo -------------------------------------------------------------------------


def source(tmp_path, returncodes=(1, 1, 0), run_id="RUN-src", **changes):
    """Recibo task_run sintético y sellado: test-0 reproduce; cada intento con su test."""
    order = [IDENTITY, ENVIRONMENT, STORAGE]
    tests = [
        {"id": f"test-{i}", "returncode": code, "stderr": PARTIAL if i == 0 else f"attempt {i}"}
        for i, code in enumerate(returncodes)
    ]
    record_ = {
        "schema_id": RECEIPT_SCHEMA,
        "source_hash_normalization": SOURCE_HASH_NORMALIZATION,
        "kind": "task_run",
        "run_id": run_id,
        "batch_id": "BATCH-x",
        "seed": 7,
        "agent": AGENT_NAME,
        "condition": "A_N",
        "pass": 1,
        "task": TASK,
        "result": "PASS" if returncodes[-1] == 0 else "FAIL",
        "tests": tests,
        "actions": [{"iteration": i, "strategy": s} for i, s in enumerate(order[: len(tests) - 1], 1)],
        **changes,
    }
    return publish(tmp_path, record_)


def test_one_record_per_failed_repair_attempt_from_a_sealed_receipt(tmp_path):
    path = source(tmp_path, (1, 1, 1, 0))
    sealed = read_receipt(path)
    memory = FailureMemory()
    changes = memory.consolidate(path)
    assert [r["evidence"] for r in memory.records] == ["RUN-src#test-1", "RUN-src#test-2"]  # nunca test-0
    assert [r["strategy"] for r in memory.records] == [IDENTITY, ENVIRONMENT]
    for item in memory.records:
        assert item == {
            "id": "failure:" + item["evidence"],
            "strategy": item["strategy"],
            "query": QUERY,
            "signature": failure_features(PARTIAL),
            "evidence": item["evidence"],
            "receipt_sha256": sealed["receipt_sha256"],
        }
    assert changes == [
        {"action": "ADD", "memory": r["id"], "evidence": r["evidence"]} for r in memory.records
    ]
    assert memory.origins == {r["id"]: "T-1" for r in memory.records}  # leído del recibo, fuera del registro
    assert memory.origin("failure:RUN-src#test-1", "T-1") == "same_task"
    assert memory.origin("failure:RUN-src#test-1", "T-9") == "other_task"
    assert memory.consolidate(path) == []  # idempotente
    assert failure_records(sealed) == memory.records


def test_a_run_without_failed_attempts_writes_no_record(tmp_path):
    memory = FailureMemory()
    assert memory.consolidate(source(tmp_path, (1, 0))) == [] and memory.records == []


@pytest.mark.parametrize(
    "changes",
    [{"condition": "A"}, {"condition": "C"}, {"condition": None}, {"agent": DiagnosticRepairAgent.name}],
    ids=["A", "C", "no-condition", "diagnostic-agent"],
)
def test_records_are_written_only_from_a_n_and_c_n_receipts(tmp_path, changes):
    with pytest.raises(ValueError, match=r"solo se escribe|desconocida"):
        FailureMemory().consolidate(source(tmp_path, **changes))


@pytest.mark.parametrize(
    "returncodes_or_changes",
    [
        {"returncodes": (0, 1, 0)},  # test-0 no reproduce el fallo
        {"actions": [{"iteration": 1, "strategy": IDENTITY}]},  # un intento sin su test
        {"actions": [{"iteration": 2, "strategy": IDENTITY}, {"iteration": 1, "strategy": ENVIRONMENT}]},
        {"result": "ERROR"},
    ],
    ids=["test0-passed", "missing-test", "misnumbered", "error"],
)
def test_inconsistent_receipts_write_no_record(tmp_path, returncodes_or_changes):
    changes = dict(returncodes_or_changes)
    path = source(tmp_path, changes.pop("returncodes", (1, 1, 0)), **changes)
    with pytest.raises(ValueError, match=r"reproducción fallida|no se corresponden"):
        FailureMemory().consolidate(path)


def test_tampered_or_foreign_receipts_are_rejected(tmp_path):
    path = source(tmp_path)
    data = json.loads(path.read_text("utf-8"))
    data["tests"][1]["returncode"] = 0
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="integrity"):
        FailureMemory().consolidate(path)
    memory = FailureMemory()
    memory.consolidate(source(tmp_path, run_id="RUN-a"))
    with pytest.raises(ValueError, match="otra"):
        memory.consolidate(source(tmp_path, run_id="RUN-b", seed=9))


def test_update_failure_memory_publishes_a_separate_receipt_and_swaps_only_after(tmp_path):
    evidence = tmp_path / "evidence"
    memory = FailureMemory()
    path = update_failure_memory(memory, source(tmp_path, (1, 1, 0)), evidence)
    update = read_receipt(path)
    assert update["kind"] == "memory_update" and update["memory_store"] == STORE
    assert update["source_receipt"] == "RUN-src.json" and update["phases"] == ["MEMORY_UPDATE"]
    assert update["memory_before"] == {"schema_id": STORE, "records": []}
    assert update["memory_after"] == memory.snapshot() and len(memory.records) == 1
    assert update_failure_memory(memory, source(tmp_path, (1, 0), run_id="RUN-ok"), evidence) is None
    assert len(list(evidence.glob("RUN-*.json"))) == 1  # sin intentos fallidos no hay recibo
    before = memory.snapshot()
    with pytest.raises(ValueError, match="solo se escribe"):
        update_failure_memory(memory, source(tmp_path, run_id="RUN-c", condition="C"), evidence)
    assert memory.snapshot() == before and len(list(evidence.glob("RUN-*.json"))) == 1


@pytest.mark.parametrize(
    ("agent", "mode", "kwargs"),
    [
        (FailureMemoryRepairAgent(), "NO_MEMORY", {}),  # agente de H6 sin condición
        (DiagnosticRepairAgent(), "NO_MEMORY", {"condition": "A", "pass_number": 1}),
        (FailureMemoryRepairAgent(), "NO_MEMORY", {"condition": "A_N", "pass_number": 1}),  # sin memoria
        (
            FailureMemoryRepairAgent(),
            "NO_MEMORY",
            {"condition": "A", "pass_number": 1, "failures": FailureMemory()},
        ),
        (FailureMemoryRepairAgent(), "NO_MEMORY", {"condition": "C", "pass_number": 1}),
        (FailureMemoryRepairAgent(), "NO_MEMORY", {"condition": "A", "pass_number": 3}),
        (FailureMemoryRepairAgent(), "NO_MEMORY", {"condition": "B", "pass_number": 1}),
    ],
    ids=["no-condition", "other-agent", "a_n-without-memory", "a-with-memory", "c-mode", "pass-3", "unknown"],
)
def test_runner_refuses_inconsistent_failure_memory_arguments(tmp_path, agent, mode, kwargs):
    with pytest.raises(ValueError, match=r"exige su agente|no concuerdan"):
        run_experiment("EXP-01", agent, mode, 7, evidence_dir=tmp_path, **kwargs)
    assert not list(tmp_path.glob("RUN-*.json"))
