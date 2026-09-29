"""Orquestador del ciclo Plan → Retrieve → Act → Observe → Consolidate.

Ver ``specs/loop_protocol.md`` §1 para la máquina de estados formal. Las
transiciones se validan contra ``TRANSITIONS``: una transición ilegal lanza
``IllegalTransition`` en lugar de producir un episodio inconsistente.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

from ..memory.associative import RetrievalConfig, RetrievalResult, Retriever
from ..memory.consolidation import Consolidator
from ..memory.embeddings import Embedder
from ..memory.graph import MemoryGraph
from .tools import Tool, ToolResult

if TYPE_CHECKING:
    from ..config import AppConfig

logger = logging.getLogger(__name__)


class State(StrEnum):
    PLAN = "PLAN"
    RETRIEVE = "RETRIEVE"
    ACT = "ACT"
    OBSERVE = "OBSERVE"
    CONSOLIDATE = "CONSOLIDATE"
    DONE = "DONE"


# Transiciones válidas. None es el estado inicial (antes de PLAN).
TRANSITIONS: dict[State | None, set[State]] = {
    None: {State.PLAN},
    State.PLAN: {State.RETRIEVE},
    State.RETRIEVE: {State.ACT, State.CONSOLIDATE},  # CONSOLIDATE si no hay candidatas
    State.ACT: {State.OBSERVE},
    State.OBSERVE: {State.ACT, State.CONSOLIDATE},
    State.CONSOLIDATE: {State.DONE},
    State.DONE: set(),
}


class IllegalTransition(RuntimeError):
    pass


@dataclass
class Step:
    tool: str
    result: ToolResult


@dataclass
class Episode:
    id: int
    goal: str
    candidates: list[str] = field(default_factory=list)  # salida de PLAN
    plan: list[str] = field(default_factory=list)  # candidatas re-rankeadas por RETRIEVE
    retrieval: RetrievalResult | None = None
    steps: list[Step] = field(default_factory=list)
    success: bool = False
    lessons: list[str] = field(default_factory=list)
    transitions: list[State] = field(default_factory=list)

    def transition(self, to: State) -> None:
        current = self.transitions[-1] if self.transitions else None
        if to not in TRANSITIONS[current]:
            raise IllegalTransition(f"{current} → {to} no está permitido")
        logger.debug("episodio %s: %s → %s", self.id, current, to.value)
        self.transitions.append(to)

    @property
    def state(self) -> State | None:
        return self.transitions[-1] if self.transitions else None

    @property
    def attempts(self) -> int:
        return len(self.steps)

    @property
    def first_try_success(self) -> bool:
        return bool(self.steps) and self.steps[0].result.success

    @property
    def failed_tools(self) -> list[str]:
        return [s.tool for s in self.steps if not s.result.success]


Evaluator = Callable[[str, ToolResult], bool]


def default_evaluator(goal: str, result: ToolResult) -> bool:
    return result.success and bool(result.output)


class Planner(Protocol):
    """PLAN: decide qué herramientas son candidatas para la meta.

    Punto de extensión: un planner basado en LLM puede recibir aquí las
    lecciones de episodios previos y proponer subobjetivos o un orden propio.
    """

    def plan(self, goal: str, tools: Sequence[Tool]) -> list[str]: ...


class RuleBasedPlanner:
    """Todas las herramientas registradas, en orden de registro."""

    def plan(self, goal: str, tools: Sequence[Tool]) -> list[str]:
        return [t.name for t in tools]


class Agent:
    def __init__(
        self,
        tools: list[Tool],
        memory: MemoryGraph | None = None,
        use_memory: bool = True,
        max_attempts: int = 3,
        evaluator: Evaluator = default_evaluator,
        prune_every: int = 10,
        embedder: Embedder | None = None,
        retrieval_config: RetrievalConfig | None = None,
        planner: Planner | None = None,
        consolidator: Consolidator | None = None,
    ) -> None:
        self.tools = {t.name: t for t in tools}
        self.memory = memory if memory is not None else MemoryGraph()
        self.use_memory = use_memory
        self.max_attempts = max_attempts
        self.evaluator = evaluator
        self.prune_every = prune_every
        self.planner = planner or RuleBasedPlanner()
        self.retriever = Retriever(self.memory, embedder=embedder, config=retrieval_config)
        self.consolidator = consolidator or Consolidator(self.memory)
        self.episodes: list[Episode] = []

    @classmethod
    def from_config(
        cls,
        tools: list[Tool],
        config: AppConfig,
        memory: MemoryGraph | None = None,
        embedder: Embedder | None = None,
        planner: Planner | None = None,
    ) -> Agent:
        """Construye el agente a partir de una ``AppConfig`` (TOML/entorno)."""
        memory = memory if memory is not None else MemoryGraph(decay_rate=config.agent.decay_rate)
        return cls(
            tools,
            memory=memory,
            use_memory=config.agent.use_memory,
            max_attempts=config.agent.max_attempts,
            prune_every=config.agent.prune_every,
            embedder=embedder,
            retrieval_config=config.retrieval,
            planner=planner,
            consolidator=Consolidator(memory, **config.consolidation.model_dump()),
        )

    # ------------------------------------------------------------------ fases
    def plan(self, goal: str) -> list[str]:
        """PLAN: herramientas candidatas para la meta (sin consultar la memoria)."""
        return self.planner.plan(goal, list(self.tools.values()))

    def retrieve(self, goal: str, candidates: list[str]) -> tuple[list[str], RetrievalResult | None]:
        """RETRIEVE: contexto asociado; re-rankea las candidatas por score."""
        if not self.use_memory:
            return candidates, None
        retrieval = self.retriever.retrieve(goal, candidates)
        return [s.action for s in retrieval.ranked_actions], retrieval

    def act(self, tool: str, goal: str) -> ToolResult:
        """ACT: ejecuta la herramienta elegida."""
        return self.tools[tool](goal)

    def observe(self, goal: str, result: ToolResult) -> ToolResult:
        """OBSERVE & EVALUATE: contrasta el resultado con la meta."""
        ok = self.evaluator(goal, result)
        if result.success and not ok:
            return ToolResult(False, result.output, "output did not satisfy goal", result.latency_ms)
        return result

    # ------------------------------------------------------------------ ciclo
    def run(self, goal: str) -> Episode:
        episode_id = self.memory.tick()
        ep = Episode(episode_id, goal)

        ep.transition(State.PLAN)
        ep.candidates = self.plan(goal)

        ep.transition(State.RETRIEVE)
        ep.plan, ep.retrieval = self.retrieve(goal, ep.candidates)
        # La meta se escribe DESPUÉS de recuperar, para que no se active a sí misma.
        goal_node = self.consolidator.record_goal(goal, episode_id) if self.use_memory else None

        for step_idx, tool in enumerate(ep.plan[: self.max_attempts]):
            ep.transition(State.ACT)
            raw = self.act(tool, goal)

            ep.transition(State.OBSERVE)
            result = self.observe(goal, raw)
            ep.steps.append(Step(tool, result))
            logger.debug("episodio %s: %s → %s", episode_id, tool, "ok" if result.success else result.error)
            if goal_node:
                self.consolidator.record_step(goal_node, tool, result, episode_id, step_idx)
            if result.success:
                ep.success = True
                break

        ep.transition(State.CONSOLIDATE)
        if goal_node:
            ep.lessons = self.consolidator.consolidate_episode(
                goal_node,
                [(s.tool, s.result) for s in ep.steps],
                activation=ep.retrieval.activation if ep.retrieval else None,
            )
            if self.prune_every and episode_id % self.prune_every == 0:
                self.consolidator.prune()

        ep.transition(State.DONE)
        logger.info(
            "episodio %s '%s': %s en %d intento(s)",
            episode_id,
            goal,
            "éxito" if ep.success else "fallo",
            ep.attempts,
        )
        self.episodes.append(ep)
        return ep
