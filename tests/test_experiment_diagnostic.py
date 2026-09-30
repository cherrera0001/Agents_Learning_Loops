"""Diagnostic baseline D (#58) on synthetic reproduction traces only.

No test here runs a repair or reads a recorded reproduction: the rules are the
pre-registered table (docs/preregistration/diagnostic-baseline.md, section 2)
and must decide from the terminal exception of each failing test alone.
"""

import ast
import inspect
import itertools
import json
import re
from pathlib import Path

import pytest

from experiments import diagnostic
from experiments.agent import RULES, STRATEGIES, AgentView, BoundedRepairAgent, prior_order
from experiments.benchmark import REFERENCE_CAMPAIGN
from experiments.diagnostic import (
    FAILURE_MODES,
    STORAGE_MODULES,
    DiagnosticRepairAgent,
    DiagnosticView,
    diagnose,
    failure_features,
    joint_plan,
)

IDENTITY, ENVIRONMENT, STORAGE = "validate_optional_identity", "normalize_environment", "initialize_storage"
DEFAULT_KEYS = (
    "considered",
    "selected",
    "plan",
    "without_memory",
    "influenced_by_memory",
    "memory_ids",
    "initial_hypothesis",
)


def block(outcome, exception, *, test="test_contract (test_contract.Contract.test_contract)", path=None):
    path = path or "<workspace>/app/component.py"
    return (
        "=" * 70
        + f"\n{outcome}: {test}\n"
        + "-" * 70
        + "\nTraceback (most recent call last):\n"
        + f'  File "{path}", line 12, in handler\n    value = lookup(key)\n            ^^^^^^^^^^^\n'
        + f'  File "{path}", line 30, in lookup\n    return item["field"]\n           ~~~~^^^^^^^^^\n'
        + exception
        + "\n\n"
    )


def trace(*blocks):
    head = "test_create_and_list (test_business.BusinessTests.test_create_and_list) ... ok\n"
    head += "test_contract (test_contract.Contract.test_contract) ... ERROR\n\n"
    return head + "".join(blocks) + "-" * 70 + "\nRan 2 tests in 0.004s\n\nFAILED (errors=1)\n"


def one(exception, outcome="ERROR"):
    return trace(block(outcome, exception))


def test_rules_are_the_preregistered_table():
    assert FAILURE_MODES == {
        "storage_unavailable": (STORAGE,),
        "missing_value": (IDENTITY, ENVIRONMENT),
        "contract_violated": STRATEGIES,
        "other": STRATEGIES,
    }
    assert STORAGE_MODULES == ("sqlite3",)
    assert set(itertools.chain(*FAILURE_MODES.values())) == set(STRATEGIES)


def test_features_keep_only_outcome_exception_class_and_none_marker():
    assert failure_features(one("TypeError: 'NoneType' object is not subscriptable")) == [
        {"outcome": "ERROR", "exception": "TypeError", "none_marker": True}
    ]
    assert failure_features(one("AssertionError: 500 != 401", "FAIL")) == [
        {"outcome": "FAIL", "exception": "AssertionError", "none_marker": False}
    ]


def test_paths_test_names_messages_and_line_endings_do_not_change_the_diagnosis():
    reference = one("AttributeError: 'NoneType' object has no attribute 'strip'")
    variants = [
        trace(
            block("ERROR", "AttributeError: 'NoneType' object has no attribute 'title'", path="C:\\ws\\a.py")
        ),
        trace(
            block("ERROR", "AttributeError: 'NoneType' object has no attribute 'x'", test="test_other (m.K)")
        ),
        "\ufeff" + reference.replace("\n", "\r\n"),
    ]
    for variant in variants:
        assert diagnose(variant) == diagnose(reference)


def test_chained_exceptions_use_the_reported_last_traceback():
    chained = (
        "=" * 70
        + "\nERROR: test_contract (test_contract.Contract.test_contract)\n"
        + "-" * 70
        + '\nTraceback (most recent call last):\n  File "<workspace>/a.py", line 3, in f\n    x = d["k"]\n'
        + "KeyError: 'k'\n\nDuring handling of the above exception, another exception occurred:\n\n"
        + 'Traceback (most recent call last):\n  File "<workspace>/a.py", line 5, in f\n    raise X\n'
        + "ConnectionError: database connection refused\n\n"
    )
    result = diagnose(trace(chained))
    assert result["features"][0]["exception"] == "ConnectionError"
    assert result["status"] == "decisive"


@pytest.mark.parametrize(
    ("exception", "status", "candidates"),
    [
        ("ConnectionError: database connection refused", "decisive", [STORAGE]),
        ("ConnectionRefusedError: [Errno 111] refused", "decisive", [STORAGE]),  # builtin subclass
        ("sqlite3.OperationalError: no such table: tasks", "decisive", [STORAGE]),
        ("TypeError: 'NoneType' object is not subscriptable", "partial", [IDENTITY, ENVIRONMENT]),
        ("AttributeError: 'NoneType' object has no attribute 'strip'", "partial", [IDENTITY, ENVIRONMENT]),
        ("AssertionError: {'label': ''} != {'label': 'Open tasks'}", "ambiguous", list(STRATEGIES)),
    ],
)
def test_preregistered_rules(exception, status, candidates):
    result = diagnose(one(exception))
    assert (result["status"], result["candidates"]) == (status, candidates)


@pytest.mark.parametrize(
    "exception",
    [
        "app.auth.Unauthorized: authentication required",  # application exception: no public meaning
        "TypeError: unsupported operand type(s) for +: 'int' and 'str'",  # no NoneType marker
        "ValueError: NoneType is not allowed here",  # marker without a missing-value class
        "KeyError: 'field'",
        "CustomError: something",  # not a builtin
        "sqlite3x.Error: lookalike module",  # only the sqlite3 standard module counts
        "not an exception line",
    ],
)
def test_negative_cases_fall_back_to_ambiguous(exception):
    result = diagnose(one(exception))
    assert result["status"] == "ambiguous"
    assert result["reason"] == "no_discrimination"
    assert result["candidates"] == list(STRATEGIES)


@pytest.mark.parametrize(
    "stderr",
    [None, "", "TEST TIMEOUT", "test_a (m.K) ... ok\n\n" + "-" * 70 + "\nRan 2 tests in 0.1s\n\nOK\n"],
)
def test_no_failure_block_is_ambiguous(stderr):
    assert (diagnose(stderr)["status"], diagnose(stderr)["reason"]) == ("ambiguous", "no_failure_block")


def test_block_without_frames_has_no_exception():
    frameless = "=" * 70 + "\nERROR: test_x (m.K)\n" + "-" * 70 + "\nsomething went wrong\n\n"
    assert failure_features(trace(frameless)) == [
        {"outcome": "ERROR", "exception": None, "none_marker": False}
    ]


def test_blocks_combine_by_intersection_and_conflict_is_explicit():
    storage = block("ERROR", "ConnectionError: refused")
    missing = block("ERROR", "TypeError: 'NoneType' object is not subscriptable", test="test_b (m.K)")
    contract = block("FAIL", "AssertionError: 1 != 2", test="test_c (m.K)")
    assert diagnose(trace(missing, contract))["candidates"] == [IDENTITY, ENVIRONMENT]
    assert diagnose(trace(storage, contract))["status"] == "decisive"
    conflict = diagnose(trace(storage, missing))
    assert (conflict["status"], conflict["reason"], conflict["candidates"]) == (
        "ambiguous",
        "conflict",
        list(STRATEGIES),
    )


def lesson(strategy, task="T"):
    return {
        "id": f"lesson:{strategy}",
        "task": task,
        "symptom": "a request fails",
        "strategy": strategy,
        "rule": RULES[strategy],
    }


def decisions(stderr, seed, memories, mode):
    task = {"title": "a request fails", "context": "it fails"}
    default = BoundedRepairAgent().plan(AgentView(task, {}, memories, mode, seed))
    view = DiagnosticView(task, {}, memories, mode, seed, reproduction={"returncode": 1, "stderr": stderr})
    return default, DiagnosticRepairAgent().plan(view)


LESSON_CASES = [((), "NO_MEMORY")] + [((lesson(s),), "ASSOCIATIVE_MEMORY") for s in STRATEGIES]
LESSON_CASES += [(tuple(lesson(s) for s in STRATEGIES), "TEXT_HISTORY")]


@pytest.mark.parametrize("stderr", [one("AssertionError: 1 != 2"), "", one("KeyError: 'k'")])
def test_ambiguous_diagnosis_falls_back_exactly_to_default(stderr):
    for seed, (memories, mode) in itertools.product(REFERENCE_CAMPAIGN["seeds"], LESSON_CASES):
        default, joint = decisions(stderr, seed, memories, mode)
        assert {k: joint[k] for k in DEFAULT_KEYS} == default
        assert joint["plan_without_memory"] == list(prior_order(seed))


def test_decisive_diagnosis_fixes_the_first_attempt_in_every_condition():
    stderr = one("ConnectionError: refused")
    for seed, (memories, mode) in itertools.product(REFERENCE_CAMPAIGN["seeds"], LESSON_CASES):
        _, joint = decisions(stderr, seed, memories, mode)
        assert joint["selected"] == joint["plan"][0] == STORAGE
        proposal = joint["memory_proposal"]
        expected = "no_proposal" if proposal is None else "confirmed" if proposal == STORAGE else "vetoed"
        assert joint["memory_effect"] == expected
        if expected == "vetoed":
            assert joint["plan"][1] == proposal  # memory still orders the remaining attempts


def test_partial_diagnosis_lets_memory_decide_only_within_candidates():
    stderr = one("TypeError: 'NoneType' object is not subscriptable")
    for seed in REFERENCE_CAMPAIGN["seeds"]:
        _, vetoed = decisions(stderr, seed, (lesson(STORAGE),), "ASSOCIATIVE_MEMORY")
        assert vetoed["memory_effect"] == "vetoed" and vetoed["plan"][-1] == STORAGE
        for strategy in (IDENTITY, ENVIRONMENT):
            _, joint = decisions(stderr, seed, (lesson(strategy),), "ASSOCIATIVE_MEMORY")
            assert joint["selected"] == strategy
            first_without = joint["plan_without_memory"][0]
            assert joint["memory_effect"] == ("confirmed" if strategy == first_without else "changed_first")
            assert joint["influenced_by_memory"] == (joint["plan"] != joint["plan_without_memory"])


def test_every_plan_is_a_permutation_of_the_three_operators():
    for candidates, proposal, seed in itertools.product(
        [[STORAGE], [IDENTITY, ENVIRONMENT], list(STRATEGIES)],
        [None, *STRATEGIES],
        REFERENCE_CAMPAIGN["seeds"],
    ):
        plan, without_memory = joint_plan(prior_order(seed), candidates, proposal)
        assert sorted(plan) == sorted(without_memory) == sorted(STRATEGIES)
        assert plan[: len(candidates)] == [op for op in plan if op in candidates]


def test_diagnosis_reads_only_the_reproduction_stderr():
    assert list(inspect.signature(diagnose).parameters) == ["stderr"]
    view = DiagnosticView(
        {"title": "", "context": ""}, {}, (), "NO_MEMORY", 7, {"returncode": 1, "stderr": ""}
    )
    serialized = json.dumps(view.__dict__)
    for forbidden in ("hidden_cause_id", "relevant_training_tasks", "golden_patch", "mutation", "EXP-"):
        assert forbidden not in serialized


def test_generic_audit_no_task_ids_private_data_or_controller_imports():
    tree = ast.parse(Path(inspect.getfile(diagnostic)).read_text("utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add("." * node.level + (node.module or ""))
    assert imported == {"builtins", "re", "dataclasses", ".agent", ".evidence"}
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
