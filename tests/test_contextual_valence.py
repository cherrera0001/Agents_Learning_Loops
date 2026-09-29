"""Valencia contextual (#8): un fallo en un dominio no contamina otro."""

import pytest

from associative_agent_loop.agent.core import Agent
from associative_agent_loop.agent.tools import domain_scenario, weather_scenario
from associative_agent_loop.memory.associative import RetrievalConfig, Retriever

HISTORY = ["noticias de Santiago", "clima en Santiago", "clima en Valparaíso", "clima en Temuco"]


def trained_agent(contextual: bool) -> Agent:
    agent = Agent(domain_scenario(), retrieval_config=RetrievalConfig(contextual_valence=contextual))
    for goal in HISTORY:
        agent.run(goal)
    return agent


def test_failure_in_one_domain_does_not_contaminate_another():
    agent = trained_agent(contextual=True)
    news = agent.run("noticias de Santiago")
    assert [s.tool for s in news.steps] == ["generic_api"]  # sigue prefiriendo la rápida
    weather = agent.run("clima en Concepción")
    assert [s.tool for s in weather.steps] == ["fallback_api"]  # y la evita donde falla


def test_control_global_valence_leaks_across_domains():
    """Control: con la valencia global el escenario sí contamina (el test anterior puede fallar)."""
    agent = trained_agent(contextual=False)
    news = agent.run("noticias de Santiago")
    assert news.steps[0].tool == "fallback_api"


def test_contextual_valence_is_stronger_where_the_failures_happened():
    ctx, glob = trained_agent(True), trained_agent(False)
    q = "clima en Concepción"
    v_ctx = ctx.retriever.retrieve(q, ["generic_api"]).ranked_actions[0].valence
    v_glob = glob.retriever.retrieve(q, ["generic_api"]).ranked_actions[0].valence
    assert v_ctx < v_glob < 0


def test_without_activated_goals_falls_back_to_global_valence():
    agent = trained_agent(True)
    r = agent.retriever
    node = "action:generic_api"
    assert r.valence(node, activation={}) == pytest.approx(r.global_valence(node))
    assert r.valence(node, activation=None) == pytest.approx(r.global_valence(node))


def test_kernel_lets_the_closest_episode_dominate():
    agent = trained_agent(True)
    r = agent.retriever
    node = "action:generic_api"
    # goal:1 = "noticias de Santiago" (éxito); goal:2..4 = clima (fallos).
    near_news = r.valence(node, {"goal:1": 1.0, "goal:2": 0.5, "goal:3": 0.5, "goal:4": 0.5})
    near_weather = r.valence(node, {"goal:1": 0.5, "goal:2": 1.0, "goal:3": 1.0, "goal:4": 1.0})
    assert near_news > 0 > near_weather


def test_weather_learning_is_preserved():
    agent = Agent(weather_scenario())
    agent.run("clima en Santiago")
    ep = agent.run("clima en Lima")
    assert [s.tool for s in ep.steps] == ["weather_api_v2"]
    assert ep.retrieval.ranked_actions[-1].valence < 0  # v1 penalizada en contexto


def test_contextual_valence_config_is_validated():
    with pytest.raises(ValueError):
        RetrievalConfig(context_temperature=0.0)
    assert isinstance(Retriever(Agent(weather_scenario()).memory).config.contextual_valence, bool)
