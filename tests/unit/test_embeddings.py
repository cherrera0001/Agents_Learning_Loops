"""Embeddings y búsqueda híbrida (#3)."""

import math

import pytest

from associative_agent_loop.agent.core import Agent
from associative_agent_loop.agent.tools import weather_scenario
from associative_agent_loop.memory.associative import Retriever
from associative_agent_loop.memory.consolidation import Consolidator
from associative_agent_loop.memory.embeddings import LexicalEmbedder, cosine
from associative_agent_loop.memory.graph import MemoryGraph, NodeType
from scripts.devlog import load_episodes, rebuild


class CountingEmbedder(LexicalEmbedder):
    """LexicalEmbedder que cuenta cuántos textos embebe (para probar el caché)."""

    def __init__(self, name: str = "counting"):
        super().__init__()
        self.name = name
        self.calls = 0

    def embed(self, texts):
        self.calls += len(texts)
        return super().embed(texts)


def test_lexical_embedder_is_deterministic_and_normalized():
    e = LexicalEmbedder()
    a, b, c = e.embed(["Clima en Santiago", "clima santiago", "precio de acciones"])
    assert a == LexicalEmbedder().embed(["Clima en Santiago"])[0]  # otra instancia, mismo vector
    assert math.isclose(sum(x * x for x in a), 1.0)
    assert cosine(a, b) == pytest.approx(1.0)  # stopwords y mayúsculas no importan
    assert cosine(a, c) == pytest.approx(0.0)


def _memory() -> MemoryGraph:
    agent = Agent(weather_scenario())
    agent.run("clima en Santiago")
    return agent.memory


def test_index_caches_embeddings_and_survives_serialization(tmp_path):
    mg = _memory()
    emb = CountingEmbedder()
    r = Retriever(mg, embedder=emb)
    indexed = r.index()
    assert indexed == sum(1 for n in mg.nodes() if n.type != NodeType.OUTCOME)
    assert r.index() == 0  # nada pendiente: no se recalcula

    path = tmp_path / "mem.json"
    mg.save(path)
    loaded = MemoryGraph.load(path)
    assert loaded.embedding_model == "counting"
    emb2 = CountingEmbedder()
    Retriever(loaded, embedder=emb2).retrieve("clima en Lima", ["weather_api_v2"])
    assert emb2.calls == 1  # solo la consulta; los nodos venían embebidos


def test_changing_the_model_invalidates_embeddings():
    mg = _memory()
    Retriever(mg, embedder=CountingEmbedder("modelo-a")).index()
    other = CountingEmbedder("modelo-b")
    reindexed = Retriever(mg, embedder=other).index()
    assert reindexed == other.calls > 0
    assert mg.embedding_model == "modelo-b"


def test_seeding_reaches_lessons_and_errors_not_only_goals():
    mg = MemoryGraph()
    c = Consolidator(mg)
    goal = c.record_goal("tarea sin relación", mg.tick())
    c.add_lesson(goal, "validar extremos antes de crear aristas en networkx")
    seeds = Retriever(mg).seed("networkx crea nodos sin atributos en aristas")
    assert any(n.startswith("concept:lesson:") for n in seeds)
    assert goal not in seeds


def test_dev_memory_recalls_lesson_text_for_non_goal_query():
    """Criterio de #3 (dogfooding): antes, esta consulta no recuperaba nada."""
    mg = rebuild([e for e in load_episodes() if e["seq"] <= 6])  # memoria previa a #4
    lessons = Retriever(mg).retrieve("saturación de la activación en grafos densos", []).lessons
    assert lessons[0].startswith("La activación acumulada con saturación en 1.0")


PARAPHRASE = "temperatura prevista para Lima"  # sin palabras en común con "clima en Santiago"


def test_lexical_channel_cannot_bridge_a_paraphrase():
    result = Retriever(_memory()).retrieve(PARAPHRASE, ["weather_api_v1", "weather_api_v2"])
    assert result.activation == {}


@pytest.mark.embeddings
def test_semantic_embeddings_recover_the_route_for_a_paraphrase():
    from associative_agent_loop.memory.embeddings import FastEmbedEmbedder

    embedder = FastEmbedEmbedder()
    agent = Agent(weather_scenario(), embedder=embedder)
    agent.run("clima en Santiago")  # aprende: v1 falla, v2 resuelve
    ep = agent.run(PARAPHRASE)
    assert ep.retrieval.score_of("weather_api_v2") > 0 > ep.retrieval.score_of("weather_api_v1")
    assert [s.tool for s in ep.steps] == ["weather_api_v2"]
