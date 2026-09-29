"""Consolidación: escritura de trayectorias, refuerzo/debilitamiento y poda.

Regla de aprendizaje (media móvil exponencial acotada en [0, 1])::

    w ← w + η · (objetivo − w)

- objetivo = 1 → refuerzo (camino exitoso / fallo confirmado)
- objetivo = 0 → debilitamiento (asociación contradicha por la evidencia)

Cada actualización fija ``last_updated = clock``, reiniciando el
``recency_factor`` de la arista. Las aristas que no se usan decaen solas y la
poda elimina las que caen bajo ``prune_threshold``.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from .associative import action_id, tokenize, topic_id
from .graph import EdgeType, MemoryGraph, NodeType

if TYPE_CHECKING:  # evita import circular en tiempo de ejecución
    from ..agent.tools import ToolResult


def _slug(text: str, max_len: int = 40) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:max_len]


class Consolidator:
    def __init__(
        self,
        memory: MemoryGraph,
        learning_rate: float = 0.4,
        penalty_rate: float = 0.2,
        prune_threshold: float = 0.02,
    ) -> None:
        self.memory = memory
        self.lr = learning_rate
        self.penalty_rate = penalty_rate
        self.prune_threshold = prune_threshold

    # ------------------------------------------------------------ primitivas
    def reinforce(
        self, src: str, dst: str, edge_type: EdgeType, target: float = 1.0, rate: float | None = None
    ) -> float:
        """Mueve el peso de la arista hacia ``target``; la crea con peso 0 si no existe."""
        mg = self.memory
        mg.add_edge(src, dst, edge_type, weight=0.0)
        data = mg.edge(src, dst, edge_type)
        eta = self.lr if rate is None else rate
        data["weight"] = data["weight"] + eta * (target - data["weight"])
        data["last_updated"] = mg.clock
        data["count"] += 1
        return data["weight"]

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
    def consolidate_episode(self, goal: str, steps: list[tuple[str, "ToolResult"]]) -> list[str]:
        """Aplica refuerzo/penalización a partir de la trayectoria del episodio.

        Devuelve la lista de lecciones (Concept kind=lesson) creadas o reforzadas.
        """
        mg = self.memory
        lessons: list[str] = []
        topics = [dst for _, dst, _ in mg.out_edges(goal, EdgeType.ASSOCIATED_WITH)]
        failures: list[tuple[str, str]] = []  # (tool, error_concept)

        for tool, result in steps:
            action = action_id(tool)
            if result.success:
                # Camino exitoso: la meta se resolvió con esta acción.
                self.reinforce(goal, action, EdgeType.RESOLVED_BY, 1.0)
                # Evidencia contra fallos previos de la misma acción (útil con
                # errores intermitentes: la valencia converge a la fiabilidad real).
                for _, err, _ in list(mg.out_edges(action, EdgeType.FAILED_DUE_TO)):
                    self.reinforce(action, err, EdgeType.FAILED_DUE_TO, 0.0, self.penalty_rate)
                # Cada error observado antes en este episodio quedó resuelto por esta acción.
                for failed_tool, err in failures:
                    self.reinforce(err, action, EdgeType.RESOLVED_BY, 1.0)
                    lessons.append(
                        self._lesson(
                            f"lesson:fallback:{_slug(failed_tool)}:{_slug(tool)}",
                            f"Si '{failed_tool}' falla con '{mg.node(err)['label']}', usar '{tool}'",
                            [action, *topics],
                        )
                    )
            else:
                err = self.error_concept(result.error or "unknown error")
                failures.append((tool, err))
                # Fallo confirmado: reforzar la asociación acción → causa del fallo.
                self.reinforce(action, err, EdgeType.FAILED_DUE_TO, 1.0)
                # Penalizar metas pasadas que se resolvieron con esta acción.
                for src, _, _ in list(mg.in_edges(action, EdgeType.RESOLVED_BY)):
                    self.reinforce(src, action, EdgeType.RESOLVED_BY, 0.0, self.penalty_rate)
                lessons.append(
                    self._lesson(
                        f"lesson:avoid:{_slug(tool)}:{_slug(mg.node(err)['label'])}",
                        f"'{tool}' falló con '{mg.node(err)['label']}'",
                        [action, err, *topics],
                    )
                )
        return lessons

    def _lesson(self, key: str, label: str, links: list[str]) -> str:
        mg = self.memory
        lesson = mg.add_node(f"concept:{key}", NodeType.CONCEPT, label, kind="lesson")
        for node in links:
            self.reinforce(lesson, node, EdgeType.ASSOCIATED_WITH, 1.0)
        return lesson

    # ----------------------------------------------------------------- poda
    def prune(self) -> tuple[int, int]:
        """Elimina aristas con peso efectivo bajo el umbral y nodos aislados.

        Los nodos Goal se conservan aunque queden aislados: son el registro
        episódico. Devuelve ``(aristas_eliminadas, nodos_eliminados)``.
        """
        mg = self.memory
        weak = [
            (s, t, d["type"])
            for s, t, d in mg.g.edges(data=True)
            if mg.effective_weight(d) < self.prune_threshold
        ]
        for s, t, k in weak:
            mg.remove_edge(s, t, EdgeType(k))
        orphans = [
            n for n, d in mg.g.nodes(data=True)
            if mg.g.degree(n) == 0 and d["type"] != NodeType.GOAL.value
        ]
        for n in orphans:
            mg.remove_node(n)
        return len(weak), len(orphans)
