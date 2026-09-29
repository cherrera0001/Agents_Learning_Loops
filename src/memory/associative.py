"""Recuperación asociativa mediante activación propagada (Spreading Activation).

Algoritmo
---------
1. **Siembra**: la consulta (texto de la meta) activa
   - nodos ``Goal`` pasados, con activación = similitud léxica con la consulta;
   - nodos ``Concept`` de tipo *topic* cuyo término aparece en la consulta.
2. **Propagación**: durante ``max_hops`` saltos, cada nodo transmite
   ``a · decay · peso_efectivo`` a sus vecinos (hacia adelante y, atenuado por
   ``REVERSE_FACTOR``, hacia atrás). La activación acumulada se satura en 1.0.
3. **Puntuación de acciones**: ``score(a) = relevancia(a) · valencia(a)``
   - ``relevancia`` = activación que llegó al nodo ``Action`` (¿cuán asociado
     está al contexto actual?);
   - ``valencia`` = ``tanh(Σ RESOLVED_BY entrantes − Σ FAILED_DUE_TO salientes)``
     usando pesos efectivos (¿cuán bien ha funcionado históricamente?).

Una acción nunca vista tiene score 0: queda por debajo de las acciones exitosas
y por encima de las que ya fallaron. Así el agente *no repite el mismo error*.

La similitud es deliberadamente simple (bolsa de palabras + coseno) para no
depender de modelos de embeddings; ``Retriever`` acepta cualquier función
``similarity(a, b) -> float`` si se quiere sustituir por embeddings reales.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Callable, Iterable

from .graph import EdgeType, MemoryGraph, NodeType

STOPWORDS = {
    # español
    "el", "la", "los", "las", "de", "del", "en", "para", "por", "con", "un", "una",
    "y", "o", "a", "al", "que", "es", "hoy", "mi", "su",
    # inglés
    "the", "of", "for", "in", "on", "to", "and", "or", "an", "is", "my", "get",
}

# Las asociaciones son simétricas; el resto de relaciones se recorren hacia
# atrás con menor intensidad (p. ej. de una Action a las Goals que la usaron).
REVERSE_FACTOR = {
    EdgeType.ASSOCIATED_WITH.value: 1.0,
    EdgeType.LEADS_TO.value: 0.5,
    EdgeType.RESOLVED_BY.value: 0.5,
    EdgeType.FAILED_DUE_TO.value: 0.5,
}


def _strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9_]+", _strip_accents(text.lower()))
    return [w for w in words if w not in STOPWORDS and len(w) > 1]


def cosine_similarity(a: str, b: str) -> float:
    ca, cb = Counter(tokenize(a)), Counter(tokenize(b))
    if not ca or not cb:
        return 0.0
    dot = sum(ca[t] * cb[t] for t in ca)
    return dot / (math.sqrt(sum(v * v for v in ca.values())) * math.sqrt(sum(v * v for v in cb.values())))


@dataclass
class ActionScore:
    action: str  # nombre de la herramienta
    score: float
    relevance: float
    valence: float


@dataclass
class RetrievalResult:
    activation: dict[str, float]
    ranked_actions: list[ActionScore]
    lessons: list[str] = field(default_factory=list)

    def score_of(self, action: str) -> float:
        for s in self.ranked_actions:
            if s.action == action:
                return s.score
        return 0.0


class Retriever:
    def __init__(
        self,
        memory: MemoryGraph,
        similarity: Callable[[str, str], float] = cosine_similarity,
        decay: float = 0.7,
        max_hops: int = 3,
        threshold: float = 0.01,
        min_goal_similarity: float = 0.2,
    ) -> None:
        self.memory = memory
        self.similarity = similarity
        self.decay = decay
        self.max_hops = max_hops
        self.threshold = threshold
        self.min_goal_similarity = min_goal_similarity

    # ---------------------------------------------------------------- siembra
    def seed(self, query: str) -> dict[str, float]:
        mg = self.memory
        seeds: dict[str, float] = {}
        for goal in mg.nodes_of_type(NodeType.GOAL):
            sim = self.similarity(query, mg.node(goal)["label"])
            if sim >= self.min_goal_similarity:
                seeds[goal] = sim
        for token in set(tokenize(query)):
            topic = topic_id(token)
            if mg.has_node(topic):
                seeds[topic] = max(seeds.get(topic, 0.0), 1.0)
        return seeds

    # ----------------------------------------------------------- propagación
    def spread(self, seeds: dict[str, float]) -> dict[str, float]:
        mg = self.memory
        activation = dict(seeds)
        frontier = dict(seeds)
        for _ in range(self.max_hops):
            incoming: dict[str, float] = defaultdict(float)
            for node, a in frontier.items():
                for _, dst, data in mg.out_edges(node):
                    incoming[dst] += a * self.decay * mg.effective_weight(data)
                for src, _, data in mg.in_edges(node):
                    rev = REVERSE_FACTOR[data["type"]]
                    incoming[src] += a * self.decay * rev * mg.effective_weight(data)
            frontier = {n: a for n, a in incoming.items() if a >= self.threshold}
            if not frontier:
                break
            for n, a in frontier.items():
                activation[n] = min(1.0, activation.get(n, 0.0) + a)
        return activation

    # ------------------------------------------------------------- valencia
    def valence(self, action_node: str) -> float:
        mg = self.memory
        pos = sum(mg.effective_weight(d) for *_, d in mg.in_edges(action_node, EdgeType.RESOLVED_BY))
        neg = sum(mg.effective_weight(d) for *_, d in mg.out_edges(action_node, EdgeType.FAILED_DUE_TO))
        return math.tanh(pos - neg)

    # ------------------------------------------------------------ recuperar
    def retrieve(self, query: str, candidate_actions: Iterable[str]) -> RetrievalResult:
        """Devuelve activaciones, acciones ordenadas y lecciones relevantes.

        El orden es estable: ante empate (p. ej. memoria vacía) se respeta el
        orden original de ``candidate_actions``.
        """
        candidates = list(candidate_actions)
        activation = self.spread(self.seed(query))

        scored = []
        for name in candidates:
            node = action_id(name)
            relevance = activation.get(node, 0.0)
            val = self.valence(node) if self.memory.has_node(node) else 0.0
            scored.append(ActionScore(name, relevance * val, relevance, val))
        ranked = sorted(scored, key=lambda s: -s.score)  # sorted() es estable

        lessons = [
            self.memory.node(n)["label"]
            for n, a in sorted(activation.items(), key=lambda kv: -kv[1])
            if self.memory.has_node(n)
            and self.memory.node(n)["type"] == NodeType.CONCEPT.value
            and self.memory.node(n).get("kind") == "lesson"
        ]
        return RetrievalResult(activation, ranked, lessons)


# Convenciones de identificadores compartidas con consolidation.py
def action_id(tool: str) -> str:
    return f"action:{tool}"


def topic_id(token: str) -> str:
    return f"concept:topic:{token}"
