"""Consolidación: escritura de trayectorias, aprendizaje hebbiano, decaimiento y poda.

Dos reglas, ambas acotadas en [0, 1]:

1. **Refuerzo dirigido** (EMA) para las relaciones *agregadas* que resumen la
   experiencia (``RESOLVED_BY``, ``FAILED_DUE_TO``, lecciones)::

       w ← w + η · (objetivo − w)          objetivo ∈ {0, 1}

2. **Hebbiana con signo** («neurons that fire together wire together») para las
   *rutas* (``LEADS_TO``, ``RESOLVED_BY``) entre nodos co-activados::

       Δw = η_h · a_i · a_j · (1 − w)      si el resultado fue éxito  (r = +1)
       Δw = −η_h · a_i · a_j · w           si fue fallo               (r = −1)

   ``a_j = 1`` para la acción ejecutada y ``a_i`` es la activación con que el
   nodo de contexto fue recuperado (``Node.activation_level`` del RETRIEVE), o
   1 para la meta actual. Los factores ``(1 − w)`` y ``w`` acotan el peso sin
   necesidad de recortarlo: la potenciación satura en 1 y la depresión en 0.

Cada actualización fija ``last_updated = clock``. El decaimiento es perezoso
(``effective_weight``) o explícito (``decay()``, equivalente), y la poda elimina
aristas bajo ``prune_threshold`` y, opcionalmente, las más débiles hasta
respetar ``max_edges``.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from .associative import action_id, tokenize, topic_id
from .graph import EdgeType, MemoryGraph, NodeType

if TYPE_CHECKING:  # evita import circular en tiempo de ejecución
    from ..agent.tools import ToolResult


logger = logging.getLogger(__name__)


def _slug(text: str, max_len: int = 40) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:max_len]


# Relaciones que forman *rutas* y reciben aprendizaje hebbiano. ASSOCIATED_WITH
# (lecciones, topics) y FAILED_DUE_TO quedan fuera: que una acción falle no debe
# debilitar la lección que advertía justamente ese fallo.
HEBBIAN_RELATIONS = {EdgeType.LEADS_TO, EdgeType.RESOLVED_BY}


class Consolidator:
    def __init__(
        self,
        memory: MemoryGraph,
        learning_rate: float = 0.4,
        penalty_rate: float = 0.2,
        hebbian_rate: float = 0.3,
        prune_threshold: float = 0.02,
        max_edges: int | None = None,
    ) -> None:
        self.memory = memory
        self.lr = learning_rate
        self.penalty_rate = penalty_rate
        self.hebbian_rate = hebbian_rate
        self.prune_threshold = prune_threshold
        self.max_edges = max_edges

    def hebbian(
        self, src: str, dst: str, relation: EdgeType, a_src: float, a_dst: float, reward: int
    ) -> float | None:
        """Actualización hebbiana acotada de una arista existente; ``None`` si no existe."""
        mg = self.memory
        if not mg.has_edge(src, dst, relation):
            return None
        edge = mg.edge(src, dst, relation)
        co = a_src * a_dst
        if co <= 0:
            return edge.weight
        if reward > 0:
            edge.weight = edge.weight + self.hebbian_rate * co * (1.0 - edge.weight)
        else:
            edge.weight = edge.weight - self.hebbian_rate * co * edge.weight
        edge.last_updated = mg.clock
        edge.count += 1
        return edge.weight

    def _hebbian_step(
        self, goal: str, action: str, activation: dict[str, float], reward: int
    ) -> None:
        """Co-activación de la meta, la acción ejecutada y el contexto recuperado."""
        mg = self.memory
        # La meta actual y la acción dispararon juntas (a = 1).
        self.hebbian(goal, action, EdgeType.LEADS_TO, 1.0, 1.0, reward)
        # Contexto recuperado que llevó a esta acción: metas pasadas, errores resueltos...
        for src, _, edge in list(mg.in_edges(action)):
            if src != goal and edge.relation in HEBBIAN_RELATIONS:
                self.hebbian(src, action, edge.relation, activation.get(src, 0.0), 1.0, reward)

    # ------------------------------------------------------------ primitivas
    def reinforce(
        self, src: str, dst: str, edge_type: EdgeType, target: float = 1.0, rate: float | None = None
    ) -> float:
        """Mueve el peso de la arista hacia ``target``; la crea con peso 0 si no existe."""
        mg = self.memory
        edge = mg.add_edge(src, dst, edge_type, weight=0.0)
        eta = self.lr if rate is None else rate
        edge.weight = edge.weight + eta * (target - edge.weight)  # validado en [0, 1]
        edge.last_updated = mg.clock
        edge.count += 1
        return edge.weight

    # ------------------------------------------------------------- escritura
    def record_goal(self, goal_text: str, episode_id: int) -> str:
        """Crea el nodo Goal y lo asocia a Concepts *topic* (uno por término)."""
        mg = self.memory
        goal = mg.add_node(f"goal:{episode_id}", NodeType.GOAL, goal_text, episode=episode_id)
        for token in dict.fromkeys(tokenize(goal_text)):
            topic = mg.add_node(topic_id(token), NodeType.CONCEPT, token, kind="topic")
            mg.add_edge(goal, topic, EdgeType.ASSOCIATED_WITH, weight=0.5)
        return goal

    def record_step(
        self, goal: str, tool: str, result: "ToolResult", episode_id: int, step: int
    ) -> str:
        """Goal -LEADS_TO-> Action -LEADS_TO-> Outcome [-FAILED_DUE_TO-> Concept(error)]."""
        mg = self.memory
        action = mg.add_node(action_id(tool), NodeType.ACTION, tool)
        mg.add_edge(goal, action, EdgeType.LEADS_TO, weight=0.5, step=step)

        outcome = mg.add_node(
            f"outcome:{episode_id}:{step}",
            NodeType.OUTCOME,
            "success" if result.success else f"failure: {result.error}",
            success=result.success,
            latency_ms=result.latency_ms,
            error=result.error,
            episode=episode_id,
            step=step,
        )
        mg.add_edge(action, outcome, EdgeType.LEADS_TO, weight=1.0)

        if not result.success:
            error = self.error_concept(result.error or "unknown error")
            mg.add_edge(outcome, error, EdgeType.FAILED_DUE_TO, weight=1.0)
        return outcome

    def error_concept(self, error: str) -> str:
        return self.memory.add_node(
            f"concept:error:{_slug(error)}", NodeType.CONCEPT, error, kind="error"
        )

    # ------------------------------------------------------------- refuerzo
    def consolidate_episode(
        self,
        goal: str,
        steps: list[tuple[str, "ToolResult"]],
        activation: dict[str, float] | None = None,
    ) -> list[str]:
        """Aplica refuerzo hebbiano y dirigido a partir de la trayectoria del episodio.

        ``activation`` es la activación del RETRIEVE que precedió al episodio
        (nodo → [0, 1]); sin ella solo se refuerza la ruta meta → acción.
        Devuelve la lista de lecciones (Concept kind=lesson) creadas o reforzadas.
        """
        mg = self.memory
        activation = activation or {}
        lessons: list[str] = []
        topics = [dst for _, dst, _ in mg.out_edges(goal, EdgeType.ASSOCIATED_WITH)]
        failures: list[tuple[str, str]] = []  # (tool, error_concept)

        for tool, result in steps:
            action = action_id(tool)
            self._hebbian_step(goal, action, activation, +1 if result.success else -1)
            if result.success:
                # Camino exitoso: la meta se resolvió con esta acción.
                self.reinforce(goal, action, EdgeType.RESOLVED_BY, 1.0)
                # Evidencia contra fallos previos de la misma acción (útil con
                # errores intermitentes: la valencia converge a la fiabilidad real).
                for _, err, _ in list(mg.out_edges(action, EdgeType.FAILED_DUE_TO)):
                    self.reinforce(action, err, EdgeType.FAILED_DUE_TO, 0.0, self.penalty_rate)
                # Los errores pendientes quedan resueltos por el *primer* éxito posterior;
                # los éxitos siguientes no son alternativas a esos fallos.
                for failed_tool, err in failures:
                    self.reinforce(err, action, EdgeType.RESOLVED_BY, 1.0)
                    lessons.append(
                        self._lesson(
                            f"lesson:fallback:{_slug(failed_tool)}:{_slug(tool)}",
                            f"Si '{failed_tool}' falla con '{mg.node(err).label}', usar '{tool}'",
                            [action, *topics],
                        )
                    )
                failures.clear()
            else:
                err = self.error_concept(result.error or "unknown error")
                failures.append((tool, err))
                # Fallo confirmado: reforzar la asociación acción → causa del fallo.
                # (Las rutas que llevaron a la acción ya se deprimieron en
                # _hebbian_step, en proporción a cuánto se activaron.)
                self.reinforce(action, err, EdgeType.FAILED_DUE_TO, 1.0)
                lessons.append(
                    self._lesson(
                        f"lesson:avoid:{_slug(tool)}:{_slug(mg.node(err).label)}",
                        f"'{tool}' falló con '{mg.node(err).label}'",
                        [action, err, *topics],
                    )
                )
        return lessons

    def add_lesson(self, goal: str, text: str) -> str:
        """Lección explícita (redactada por una persona o un LLM), anclada a la meta y sus topics."""
        topics = [dst for _, dst, _ in self.memory.out_edges(goal, EdgeType.ASSOCIATED_WITH)]
        return self._lesson(f"lesson:note:{_slug(text, 60)}", text, [goal, *topics])

    def _lesson(self, key: str, label: str, links: list[str]) -> str:
        mg = self.memory
        lesson = mg.add_node(f"concept:{key}", NodeType.CONCEPT, label, kind="lesson")
        for node in links:
            self.reinforce(lesson, node, EdgeType.ASSOCIATED_WITH, 1.0)
        return lesson

    # ------------------------------------------------------------ decaimiento
    def decay(self) -> int:
        """Materializa el decaimiento: ``w ← w · exp(−λₑ · Δt)`` y ``last_updated ← clock``.

        Es equivalente a la lectura perezosa (``effective_weight``): el peso
        efectivo de cada arista no cambia. Útil antes de exportar o podar por
        tamaño. Devuelve cuántas aristas cambiaron.
        """
        mg = self.memory
        changed = 0
        for edge in mg.edges():
            if edge.last_updated < mg.clock:
                edge.weight = mg.effective_weight(edge)
                edge.last_updated = mg.clock
                changed += 1
        return changed

    # ----------------------------------------------------------------- poda
    def prune(self) -> tuple[int, int]:
        """Elimina aristas débiles y nodos aislados.

        1. Aristas con peso efectivo bajo ``prune_threshold``.
        2. Si ``max_edges`` está definido, las más débiles hasta respetarlo.

        Los nodos Goal se conservan aunque queden aislados: son el registro
        episódico. Devuelve ``(aristas_eliminadas, nodos_eliminados)``.
        """
        mg = self.memory
        weak = [e for e in mg.edges() if mg.effective_weight(e) < self.prune_threshold]
        if self.max_edges is not None:
            survivors = sorted(
                (e for e in mg.edges() if mg.effective_weight(e) >= self.prune_threshold),
                key=mg.effective_weight,
            )
            excess = len(survivors) - self.max_edges
            weak += survivors[: max(excess, 0)]
        for e in weak:
            mg.remove_edge(e.source, e.target, e.relation)
        orphans = [
            n.id for n in mg.nodes() if mg.g.degree(n.id) == 0 and n.type != NodeType.GOAL
        ]
        for n in orphans:
            mg.remove_node(n)
        logger.debug("poda: %d aristas y %d nodos eliminados", len(weak), len(orphans))
        return len(weak), len(orphans)
