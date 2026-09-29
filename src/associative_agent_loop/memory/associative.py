"""Recuperación asociativa mediante activación propagada (Spreading Activation).

Algoritmo
---------
1. **Siembra híbrida**: la consulta activa todo nodo con texto (Goal, Action,
   Concept) cuya similitud ``α · coseno(embeddings) + (1 − α) · léxica`` supere
   ``min_seed_similarity`` (top-k), más los ``Concept(topic)`` cuyo término
   aparece literalmente en la consulta.
2. **Propagación**: activación propagada con umbral de disparo, refracción y
   normalización por fan-out (ver ``spread_trace``).
3. **Puntuación de acciones**: ``score(a) = relevancia(a) · valencia(a)``
   - ``relevancia`` = activación que llegó al nodo ``Action`` (¿cuán asociado
     está al contexto actual?);
   - ``valencia`` = ``tanh(Σ RESOLVED_BY entrantes − Σ FAILED_DUE_TO salientes)``
     usando pesos efectivos (¿cuán bien ha funcionado históricamente?).

Una acción nunca vista tiene score 0: queda por debajo de las acciones exitosas
y por encima de las que ya fallaron. Así el agente *no repite el mismo error*.

Por defecto los embeddings son léxicos (``LexicalEmbedder``, sin dependencias);
con el extra ``[embeddings]`` se puede usar ``FastEmbedEmbedder`` para recuperar
paráfrasis sin palabras en común.
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Iterable, Literal

from pydantic import BaseModel, ConfigDict, Field

from .embeddings import Embedder, LexicalEmbedder, cosine
from .graph import EdgeType, MemoryGraph, Node, NodeType
from .text import STOPWORDS, cosine_similarity, tokenize  # noqa: F401  (API pública)

# Las asociaciones son simétricas; el resto de relaciones se recorren hacia
# atrás con menor intensidad (p. ej. de una Action a las Goals que la usaron).
REVERSE_FACTOR = {
    EdgeType.ASSOCIATED_WITH.value: 1.0,
    EdgeType.LEADS_TO.value: 0.5,
    EdgeType.RESOLVED_BY.value: 0.5,
    EdgeType.FAILED_DUE_TO.value: 0.5,
}


logger = logging.getLogger(__name__)


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
    alpha: float = Field(
        0.7, ge=0.0, le=1.0, description="Peso del canal semántico en la similitud híbrida."
    )
    min_seed_similarity: float = Field(
        0.25, ge=0.0, le=1.0, description="Similitud híbrida mínima para sembrar un nodo."
    )
    seed_top_k: int = Field(20, ge=1, description="Máximo de nodos sembrados por similitud.")
    contextual_valence: bool = Field(
        True, description="Valencia a partir de episodios del contexto activado (#8); False = global."
    )
    context_temperature: float = Field(
        0.1, gt=0.0, description="T del núcleo: cuánto se privilegian los episodios más activados."
    )
    context_prior: float = Field(
        0.2, gt=0.0, description="κ: evidencia contextual necesaria para confiar más en ella que en la global."
    )


# Tipos de nodo con texto que participan en la siembra. Los Outcome se excluyen:
# sus etiquetas ("success", "failure: ...") duplican a los Concept(error).
INDEXED_TYPES = {NodeType.GOAL, NodeType.ACTION, NodeType.CONCEPT}


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
        embedder: Embedder | None = None,
        config: RetrievalConfig | None = None,
        lexical_similarity: Callable[[str, str], float] = cosine_similarity,
    ) -> None:
        self.memory = memory
        self.embedder = embedder or LexicalEmbedder()
        self.config = config or RetrievalConfig()
        self.lexical_similarity = lexical_similarity

    # ------------------------------------------------------------------ índice
    def index(self) -> int:
        """Calcula y cachea ``Node.embedding`` de los nodos con texto que no lo tengan.

        Si la memoria fue indexada con otro modelo, se invalidan todos los vectores
        (no son comparables entre modelos). Devuelve cuántos nodos se embebieron.
        """
        mg = self.memory
        if mg.embedding_model != self.embedder.name:
            for node in mg.nodes():
                node.embedding = None
            mg.embedding_model = self.embedder.name
        pending = [n for n in mg.nodes() if n.type in INDEXED_TYPES and n.embedding is None]
        if pending:
            for node, vec in zip(pending, self.embedder.embed([n.label for n in pending])):
                node.embedding = vec
        return len(pending)

    # ---------------------------------------------------------------- siembra
    def hybrid_similarity(self, query: str, query_vec: list[float], node: Node) -> float:
        a = self.config.alpha
        semantic = cosine(query_vec, node.embedding) if node.embedding else 0.0
        return a * max(semantic, 0.0) + (1 - a) * self.lexical_similarity(query, node.label)

    def seed(self, query: str) -> dict[str, float]:
        """Siembra híbrida sobre todos los nodos con texto + coincidencia exacta de topics."""
        mg = self.memory
        self.index()
        query_vec = self.embedder.embed([query])[0]
        scored = [
            (node.id, self.hybrid_similarity(query, query_vec, node))
            for node in mg.nodes()
            if node.type in INDEXED_TYPES
        ]
        scored = [(n, s) for n, s in scored if s >= self.config.min_seed_similarity]
        scored.sort(key=lambda kv: -kv[1])
        seeds = dict(scored[: self.config.seed_top_k])
        for token in set(tokenize(query)):
            topic = topic_id(token)
            if mg.has_node(topic):
                seeds[topic] = 1.0
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
    def global_valence(self, action_node: str) -> float:
        """``tanh(Σ RESOLVED_BY − Σ FAILED_DUE_TO)``: historia completa, sin contexto."""
        mg = self.memory
        pos = sum(mg.effective_weight(d) for *_, d in mg.in_edges(action_node, EdgeType.RESOLVED_BY))
        neg = sum(mg.effective_weight(d) for *_, d in mg.out_edges(action_node, EdgeType.FAILED_DUE_TO))
        return math.tanh(pos - neg)

    def valence(self, action_node: str, activation: dict[str, float] | None = None) -> float:
        """Valencia condicionada al contexto activado (#8).

        Evidencia episódica: cada ``Outcome`` de la acción cuenta +1 (éxito) o −1
        (fallo), ponderado por la recencia de la arista y por un núcleo sobre la
        activación de la meta de ese episodio::

            k(g)  = A(g) · exp(−(A_max − A(g)) / T)
            ctx   = Σ k·s·w̃ / Σ k·w̃                  ∈ [−1, 1]
            conf  = masa / (masa + κ),   masa = Σ k·w̃
            val   = conf · ctx + (1 − conf) · valencia_global

        El núcleo privilegia los episodios más parecidos a la consulta, así que
        un fallo en otro dominio pesa poco aunque compartan algún término. Sin
        evidencia contextual se usa la valencia global.
        """
        global_val = self.global_valence(action_node)
        cfg = self.config
        mg = self.memory
        goals = {
            n: a for n, a in (activation or {}).items()
            if a > 0 and mg.has_node(n) and mg.node(n).type == NodeType.GOAL
        }
        if not cfg.contextual_valence or not goals:
            return global_val
        a_max = max(goals.values())
        signed = mass = 0.0
        for _, out_id, edge in mg.out_edges(action_node, EdgeType.LEADS_TO):
            outcome = mg.node(out_id)
            if outcome.type != NodeType.OUTCOME:
                continue
            a_g = goals.get(goal_id(outcome.metadata.get("episode")), 0.0)
            if a_g <= 0:
                continue
            k = a_g * math.exp(-(a_max - a_g) / cfg.context_temperature)
            w = k * mg.effective_weight(edge)
            signed += w if outcome.metadata.get("success") else -w
            mass += w
        if mass == 0:
            return global_val
        conf = mass / (mass + cfg.context_prior)
        return conf * (signed / mass) + (1 - conf) * global_val

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
        logger.debug("retrieve %r: %d semillas, %d nodos activados", query, len(trace.seeds), len(activation))

        scored = []
        for name in candidates:
            node = action_id(name)
            relevance = activation.get(node, 0.0)
            val = self.valence(node, activation) if self.memory.has_node(node) else 0.0
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


def goal_id(episode: object) -> str:
    return f"goal:{episode}"
