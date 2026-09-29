"""Reference campaign v2 (#44): the declared seeds must cover every prior permutation.

The orders are computed with ``experiments.agent.prior_order``, the very function
``BoundedRepairAgent.plan`` uses, never with a copy of its logic.
"""

import itertools
import sys

import pytest

from experiments import __main__ as cli
from experiments.agent import STRATEGIES, AgentView, BoundedRepairAgent, prior_order
from experiments.benchmark import (
    HISTORICAL_CAMPAIGN,
    REFERENCE_CAMPAIGN,
    TASK_SETS,
    family_breakdown,
    family_markdown,
)


def orders(seeds):
    return {prior_order(seed) for seed in seeds}


def test_reference_seeds_cover_all_permutations_exactly_once():
    seeds = REFERENCE_CAMPAIGN["seeds"]
    expected = set(itertools.permutations(STRATEGIES))
    assert len(expected) == 6
    assert orders(seeds) == expected
    assert len(seeds) == len(set(seeds)) == len(expected), "one seed per permutation"


def test_control_historical_seeds_cover_only_two_permutations():
    # If this control stops giving 2, the coverage test above no longer proves anything.
    assert len(orders(HISTORICAL_CAMPAIGN["seeds"])) == 2
    assert orders(HISTORICAL_CAMPAIGN["seeds"]) != set(itertools.permutations(STRATEGIES))
    assert orders([7, 11, 23]) == {
        ("initialize_storage", "validate_optional_identity", "normalize_environment"),
        ("validate_optional_identity", "initialize_storage", "normalize_environment"),
    }


def test_agent_uses_the_same_prior_function():
    agent = BoundedRepairAgent()
    for seed in REFERENCE_CAMPAIGN["seeds"]:
        view = AgentView(
            task={"title": "", "context": ""}, files={}, memories=(), memory_mode="NO_MEMORY", seed=seed
        )
        plan = agent.plan(view)
        assert tuple(plan["considered"]) == prior_order(seed)
        assert plan["selected"] == prior_order(seed)[0]


def test_reference_campaign_declares_replication_and_all_tasks():
    assert REFERENCE_CAMPAIGN["replicates"] == 2
    assert REFERENCE_CAMPAIGN["task_set"] == "misleading-v1"
    assert len(TASK_SETS[REFERENCE_CAMPAIGN["task_set"]]) == 9


def test_cli_campaign_flag_fixes_the_configuration(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(cli, "campaign", lambda *args: calls.append(args))
    monkeypatch.setattr(
        sys, "argv", ["experiments", "run", "--campaign", "reference-v2", "--evidence-dir", str(tmp_path)]
    )
    cli.main()
    seeds, replicates, _, tasks = calls[0]
    assert (seeds, replicates, tasks) == (
        list(REFERENCE_CAMPAIGN["seeds"]),
        2,
        TASK_SETS["misleading-v1"],
    )
    monkeypatch.setattr(
        sys, "argv", ["experiments", "run", "--campaign", "reference-v2", "--seeds", "7", "11", "23"]
    )
    with pytest.raises(SystemExit):
        cli.main()
    # Without the flag the historical defaults are unchanged.
    calls.clear()
    monkeypatch.setattr(sys, "argv", ["experiments", "run", "--evidence-dir", str(tmp_path)])
    cli.main()
    assert calls[0][0] == [7, 11, 23] and calls[0][1] == 2 and calls[0][3] == TASK_SETS["v1"]


def synthetic(task, mode, iterations, first):
    return {
        "split": "transfer",
        "task": {"id": task},
        "memory_mode": mode,
        "iterations": iterations,
        "outcome": {"first_attempt_success": first},
    }


def test_family_breakdown_separates_kinds_and_states_denominators():
    metadata = {
        "EXP-04": {"family": "authentication"},
        "EXP-07": {"family": "authentication", "decoy_family": "readiness"},
    }
    runs = [
        synthetic("EXP-04", "NO_MEMORY", 2, False),
        synthetic("EXP-04", "NO_MEMORY", 3, False),
        synthetic("EXP-04", "TEXT_HISTORY", 1, True),
        synthetic("EXP-04", "TEXT_HISTORY", 1, True),
        synthetic("EXP-07", "NO_MEMORY", 2, False),
        synthetic("EXP-07", "TEXT_HISTORY", 3, False),
        {**synthetic("EXP-01", "NO_MEMORY", 9, True), "split": "train"},
    ]
    report = family_breakdown(runs, metadata)
    assert set(report["kinds"]) == {"original", "misleading"}
    original = report["kinds"]["original"]["authentication"]
    assert original["NO_MEMORY"]["runs"] == 2 and original["NO_MEMORY"]["IterationsPerTask"] == 2.5
    assert original["TEXT_HISTORY"]["first_attempt_successes"] == 2
    assert original["TEXT_HISTORY"]["LearningGain"] == {
        "IterationsPerTask": -1.5,
        "FirstAttemptSuccessRate": 1.0,
    }
    misleading = report["kinds"]["misleading"]["authentication"]
    assert misleading["TEXT_HISTORY"]["LearningGain"]["IterationsPerTask"] == 1.0
    assert "NO_MEMORY" in misleading and "LearningGain" not in misleading["NO_MEMORY"]
    assert "(2/2)" in family_markdown(report)
