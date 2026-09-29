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
from typing import Callable, Iterable, Literal

from pydantic import BaseModel, ConfigDict, Field

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


class RetrievalConfig(BaseModel):
    """Parámetros de la activación propagada (ver ``specs/loop_protocol.md`` §3)."""

    model_config = ConfigDict(extra="forbid")

    damping: float = Field(0.7, gt=0.0, le=1.0, description="δ: atenuación por salto.")
    firing_threshold: float = Field(
        0.01, ge=0.0, le=1.0, description="θ: activación mínima acumulada para que un nodo dispare."
    )
    max_hops: int = Field(3, ge=0)
    fan_out: Literal["none", "sqrt", "linear"] = Field(
        "sqrt", description="Normalización de la salida por el grado del nodo que dispara."
    )
    min_goal_similarity: float = Field(0.2, ge=0.0, le=1.0)


@dataclass
class ActionScore:
    action: str  # nombre de la herramienta
    score: float
    relevance: float
    valence: float
    path: list[str] = field(default_factory=list)  # camino semilla → acción de mayor aporte


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


@dataclass
class Spread:
    """Resultado de la propagación: activación final y aportes por arista (traza)."""

    activation: dict[str, float]
    contributions: dict[str, dict[str, float]]  # destino -> {origen: aporte}
    seeds: dict[str, float]

    def path_to(self, node: str) -> list[str]:
        """Camino de mayor aporte desde una semilla hasta ``node``.

        Con refracción, cada nodo recibe solo de nodos que dispararon antes que
        él; seguir el mayor aporte hacia atrás siempre termina en una semilla.
        """
        path = [node]
        while path[-1] in self.contributions and path[-1] not in self.seeds:
            parents = self.contributions[path[-1]]
            path.append(max(parents, key=parents.__getitem__))
        return list(reversed(path))


class Retriever:
    def __init__(
        self,
        memory: MemoryGraph,
        similarity: Callable[[str, str], float] = cosine_similarity,
        config: RetrievalConfig | None = None,
    ) -> None:
        self.memory = memory
        self.similarity = similarity
        self.config = config or RetrievalConfig()

    # ---------------------------------------------------------------- siembra
    def seed(self, query: str) -> dict[str, float]:
        mg = self.memory
        seeds: dict[str, float] = {}
        for goal in mg.nodes_of_type(NodeType.GOAL):
            sim = self.similarity(query, mg.node(goal).label)
            if sim >= self.config.min_goal_similarity:
                seeds[goal] = sim
        for token in set(tokenize(query)):
            topic = topic_id(token)
            if mg.has_node(topic):
                seeds[topic] = max(seeds.get(topic, 0.0), 1.0)
        return seeds

    # ----------------------------------------------------------- propagación
    def _neighbors(self, node: str) -> list[tuple[str, float]]:
        """Vecinos con su peso de transmisión (adelante: w̃; atrás: ρ · w̃)."""
        mg = self.memory
        forward = [(dst, mg.effective_weight(e)) for _, dst, e in mg.out_edges(node)]
        backward = [
            (src, REVERSE_FACTOR[e.relation.value] * mg.effective_weight(e))
            for src, _, e in mg.in_edges(node)
        ]
        return forward + backward

    def _fan_out_norm(self, degree: int) -> float:
        if degree == 0 or self.config.fan_out == "none":
            return 1.0
        return math.sqrt(degree) if self.config.fan_out == "sqrt" else float(degree)

    def spread_trace(self, seeds: dict[str, float]) -> Spread:
        """Activación propagada con umbral de disparo, refracción y fan-out.

        - Un nodo **dispara** una sola vez (refracción), cuando su activación
          acumulada alcanza ``θ``, y transmite ``A(u) · δ · w / norm(grado(u))``.
        - Un nodo que ya disparó no acumula más activación, así que los rebotes
          A→B→A no inflan el resultado.
        - La activación se satura en 1.0; se descartan los nodos bajo ``θ``.
        """
        cfg = self.config
        activation = {n: min(1.0, a) for n, a in seeds.items()}
        contributions: dict[str, dict[str, float]] = defaultdict(dict)
        fired: set[str] = set()
        frontier = [n for n, a in activation.items() if a >= cfg.firing_threshold]
        for _ in range(cfg.max_hops):
            if not frontier:
                break
            fired.update(frontier)
            incoming: dict[str, float] = defaultdict(float)
            for node in frontier:
                neighbors = self._neighbors(node)
                norm = self._fan_out_norm(len(neighbors))
                for other, w in neighbors:
                    amount = activation[node] * cfg.damping * w / norm
                    if other in fired or amount <= 0:
                        continue
                    incoming[other] += amount
                    contributions[other][node] = contributions[other].get(node, 0.0) + amount
            for n, a in incoming.items():
                activation[n] = min(1.0, activation.get(n, 0.0) + a)
            frontier = [n for n in incoming if activation[n] >= cfg.firing_threshold]
        kept = {n: a for n, a in activation.items() if a >= cfg.firing_threshold}
        return Spread(kept, dict(contributions), dict(seeds))

    def spread(self, seeds: dict[str, float]) -> dict[str, float]:
        return self.spread_trace(seeds).activation

    # ------------------------------------------------------------- valencia
    def valence(self, action_node: str) -> float:
        mg = self.memory
        pos = sum(mg.effective_weight(d) for *_, d in mg.in_edges(action_node, EdgeType.RESOLVED_BY))
        neg = sum(mg.effective_weight(d) for *_, d in mg.out_edges(action_node, EdgeType.FAILED_DUE_TO))
        return math.tanh(pos - neg)

    # ------------------------------------------------------------ recuperar
    def retrieve(self, query: str, candidate_actions: Iterable[str]) -> RetrievalResult:
        """Devuelve activaciones, acciones ordenadas (con su camino) y lecciones.

        Efecto sobre la memoria: fija ``activation_level`` de todos los nodos a la
        activación de esta consulta (0 si no se activaron) y refresca
        ``last_accessed_at`` de los activados.

        El orden es estable: ante empate (p. ej. memoria vacía) se respeta el
        orden original de ``candidate_actions``.
        """
        candidates = list(candidate_actions)
        trace = self.spread_trace(self.seed(query))
        activation = trace.activation
        self._persist_activation(activation)

        scored = []
        for name in candidates:
            node = action_id(name)
            relevance = activation.get(node, 0.0)
            val = self.valence(node) if self.memory.has_node(node) else 0.0
            path = trace.path_to(node) if relevance > 0 else []
            scored.append(ActionScore(name, relevance * val, relevance, val, path))
        ranked = sorted(scored, key=lambda s: -s.score)  # sorted() es estable

        lessons = [
            self.memory.node(n).label
            for n, a in sorted(activation.items(), key=lambda kv: -kv[1])
            if self.memory.has_node(n)
            and self.memory.node(n).type == NodeType.CONCEPT
            and self.memory.node(n).metadata.get("kind") == "lesson"
        ]
        return RetrievalResult(activation, ranked, lessons)

    def _persist_activation(self, activation: dict[str, float]) -> None:
        mg = self.memory
        for node in mg.nodes():
            a = activation.get(node.id, 0.0)
            node.activation_level = a
            if a > 0:
                node.last_accessed_at = mg.clock


# Convenciones de identificadores compartidas con consolidation.py
def action_id(tool: str) -> str:
    return f"action:{tool}"


def topic_id(token: str) -> str:
    return f"concept:topic:{token}"
