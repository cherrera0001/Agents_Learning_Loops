"""Pruebas de comportamiento: el agente no comete el mismo error dos veces."""

from associative_agent_loop.agent.core import Agent, State
from associative_agent_loop.agent.tools import flaky_scenario, weather_scenario
from associative_agent_loop.memory.graph import EdgeType, MemoryGraph

WEATHER_GOALS = [
    "clima en Santiago",
    "pronóstico del clima en Madrid",
    "clima para mañana en Lima",
    "clima de Buenos Aires hoy",
    "pronóstico en Valparaíso",
]


def test_baseline_without_memory_repeats_the_mistake():
    agent = Agent(weather_scenario(), use_memory=False)
    episodes = [agent.run(g) for g in WEATHER_GOALS]
    assert all(ep.failed_tools == ["weather_api_v1"] for ep in episodes)


def test_attempt_1_fails_then_attempt_2_takes_correct_route():
    agent = Agent(weather_scenario())

    ep1 = agent.run("clima en Santiago")
    assert ep1.success
    assert [s.tool for s in ep1.steps] == ["weather_api_v1", "weather_api_v2"]

    ep2 = agent.run("pronóstico del clima en Madrid")  # redacción distinta
    assert ep2.success
    assert [s.tool for s in ep2.steps] == ["weather_api_v2"]
    assert ep2.retrieval.score_of("weather_api_v2") > 0 > ep2.retrieval.score_of("weather_api_v1")


def test_never_makes_the_same_mistake_twice():
    agent = Agent(weather_scenario())
    episodes = [agent.run(g) for g in WEATHER_GOALS]
    failures = [t for ep in episodes for t in ep.failed_tools]
    assert failures == ["weather_api_v1"]  # solo en el primer episodio
    assert all(ep.first_try_success for ep in episodes[1:])


def test_lessons_are_extracted_and_recalled():
    agent = Agent(weather_scenario())
    ep1 = agent.run("clima en Santiago")
    assert any("avoid:weather_api_v1" in lesson for lesson in ep1.lessons)
    ep2 = agent.run("clima en Lima")
    assert any("usar 'weather_api_v2'" in lesson for lesson in ep2.retrieval.lessons)


def test_error_concept_is_resolved_by_fallback_action():
    agent = Agent(weather_scenario())
    agent.run("clima en Santiago")
    mg = agent.memory
    err = "concept:error:http_410_gone_endpoint_deprecated"
    assert mg.has_edge("action:weather_api_v1", err, EdgeType.FAILED_DUE_TO)
    assert mg.has_edge(err, "action:weather_api_v2", EdgeType.RESOLVED_BY)


def test_only_first_success_resolves_pending_failures():
    """Regresión #13: en trayectorias largas, los éxitos posteriores no son alternativas."""
    from associative_agent_loop.agent.tools import ToolResult
    from associative_agent_loop.memory.consolidation import Consolidator

    mg = MemoryGraph()
    c = Consolidator(mg)
    goal = c.record_goal("tarea larga", mg.tick())
    steps = [
        ("write_tests", ToolResult(False, error="test tautologico")),
        ("edit_module", ToolResult(True, output="ok")),
        ("run_tests", ToolResult(True, output="ok")),
    ]
    for i, (tool, result) in enumerate(steps):
        c.record_step(goal, tool, result, 1, i)
    lessons = c.consolidate_episode(goal, steps)

    err = "concept:error:test_tautologico"
    assert mg.has_edge(err, "action:edit_module", EdgeType.RESOLVED_BY)
    assert not mg.has_edge(err, "action:run_tests", EdgeType.RESOLVED_BY)
    assert [x for x in lessons if "fallback" in x] == ["concept:lesson:fallback:write_tests:edit_module"]


def test_memory_persists_across_agent_instances(tmp_path):
    first = Agent(weather_scenario())
    first.run("clima en Santiago")
    path = tmp_path / "memory.json"
    first.memory.save(path)

    second = Agent(weather_scenario(), memory=MemoryGraph.load(path))
    ep = second.run("clima en Lima")
    assert ep.first_try_success and ep.failed_tools == []


def test_memory_reduces_calls_under_intermittent_errors():
    def total_calls(use_memory: bool) -> int:
        agent = Agent(flaky_scenario(seed=7), use_memory=use_memory)
        return sum(agent.run(f"tipo de cambio usd clp {i}").attempts for i in range(20))

    assert total_calls(True) < total_calls(False)


def test_loop_follows_protocol_transitions():
    agent = Agent(weather_scenario())
    ep = agent.run("clima en Santiago")
    assert ep.transitions == [
        State.PLAN,
        State.RETRIEVE,
        State.ACT,
        State.OBSERVE,  # weather_api_v1 ✗
        State.ACT,
        State.OBSERVE,  # weather_api_v2 ✓
        State.CONSOLIDATE,
        State.DONE,
    ]
