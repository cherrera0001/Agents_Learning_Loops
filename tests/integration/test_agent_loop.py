"""Ciclo formal del agente y benchmark (#6)."""

import json
import subprocess
import sys

import pytest

from associative_agent_loop.agent.core import Agent, Episode, IllegalTransition, State
from associative_agent_loop.agent.tools import weather_scenario
from associative_agent_loop.main import benchmark


def test_illegal_transitions_are_rejected():
    ep = Episode(1, "meta")
    with pytest.raises(IllegalTransition):
        ep.transition(State.ACT)  # no se puede actuar sin planificar
    ep.transition(State.PLAN)
    with pytest.raises(IllegalTransition):
        ep.transition(State.ACT)  # tampoco sin pasar por RETRIEVE
    ep.transition(State.RETRIEVE)
    ep.transition(State.ACT)
    with pytest.raises(IllegalTransition):
        ep.transition(State.DONE)  # hay que observar y consolidar antes de terminar


def test_same_goal_second_attempt_takes_the_alternative_route():
    agent = Agent(weather_scenario())
    first = agent.run("clima en Santiago")
    second = agent.run("clima en Santiago")
    assert [s.tool for s in first.steps] == ["weather_api_v1", "weather_api_v2"]
    assert [s.tool for s in second.steps] == ["weather_api_v2"]
    assert second.candidates == ["weather_api_v1", "weather_api_v2"]  # PLAN no cambia...
    assert second.plan == ["weather_api_v2", "weather_api_v1"]  # ...RETRIEVE re-rankea


class ReversePlanner:
    def plan(self, goal, tools):
        return [t.name for t in reversed(tools)]


def test_custom_planner_defines_candidates():
    ep = Agent(weather_scenario(), planner=ReversePlanner()).run("clima en Santiago")
    assert ep.candidates == ["weather_api_v2", "weather_api_v1"]
    assert ep.first_try_success


class EmptyPlanner:
    def plan(self, goal, tools):
        return []


def test_empty_plan_goes_straight_to_consolidate():
    ep = Agent(weather_scenario(), planner=EmptyPlanner()).run("clima en Santiago")
    assert ep.transitions == [State.PLAN, State.RETRIEVE, State.CONSOLIDATE, State.DONE]
    assert not ep.success and ep.attempts == 0


def test_benchmark_report_is_deterministic_and_shows_learning():
    report = benchmark(flaky_episodes=10)
    assert report == benchmark(flaky_episodes=10)
    same = report["scenarios"]["same_goal"]
    assert same["metrics"]["repeated_failures"] == 0
    assert same["episodes"][1]["path"] == [{"tool": "weather_api_v2", "success": True}]
    flaky = report["scenarios"]["flaky"]
    assert flaky["with_memory"]["total_calls"] < flaky["without_memory"]["total_calls"]


def test_cli_json_output_is_valid_and_reproducible():
    cmd = [sys.executable, "-m", "associative_agent_loop.main", "--json", "--episodes", "5"]
    runs = [subprocess.run(cmd, capture_output=True, check=True).stdout for _ in range(2)]
    assert runs[0] == runs[1]
    assert json.loads(runs[0].decode("utf-8"))["seed"] == 7
