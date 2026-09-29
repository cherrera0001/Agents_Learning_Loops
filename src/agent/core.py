"""Orquestador del ciclo Plan → Act → Observe → Consolidate.

Ver ``specs/loop_protocol.md`` para la máquina de estados formal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from ..memory.associative import RetrievalConfig, RetrievalResult, Retriever
from ..memory.consolidation import Consolidator
from ..memory.embeddings import Embedder
from ..memory.graph import MemoryGraph
from .tools import Tool, ToolResult


class State(str, Enum):
    PLAN = "PLAN"
    ACT = "ACT"
    OBSERVE = "OBSERVE"
    CONSOLIDATE = "CONSOLIDATE"
    DONE = "DONE"


@dataclass
class Step:
    tool: str
    result: ToolResult


@dataclass
class Episode:
    id: int
    goal: str
    plan: list[str]
    retrieval: RetrievalResult | None
    steps: list[Step] = field(default_factory=list)
    success: bool = False
    lessons: list[str] = field(default_factory=list)
    transitions: list[State] = field(default_factory=list)

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
    ) -> None:
        self.tools = {t.name: t for t in tools}
        self.memory = memory if memory is not None else MemoryGraph()
        self.use_memory = use_memory
        self.max_attempts = max_attempts
        self.evaluator = evaluator
        self.prune_every = prune_every
        self.retriever = Retriever(self.memory, embedder=embedder, config=retrieval_config)
        self.consolidator = Consolidator(self.memory)
        self.episodes: list[Episode] = []

    # ------------------------------------------------------------------ fases
    def plan(self, goal: str) -> tuple[list[str], RetrievalResult | None]:
        """PLAN/QUERY: ordena las herramientas según la memoria asociativa."""
        names = list(self.tools)
        if not self.use_memory:
            return names, None
        retrieval = self.retriever.retrieve(goal, names)
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
        ep = Episode(episode_id, goal, plan=[], retrieval=None)

        ep.transitions.append(State.PLAN)
        ep.plan, ep.retrieval = self.plan(goal)
        goal_node = self.consolidator.record_goal(goal, episode_id) if self.use_memory else None

        for step_idx, tool in enumerate(ep.plan[: self.max_attempts]):
            ep.transitions.append(State.ACT)
            raw = self.act(tool, goal)

            ep.transitions.append(State.OBSERVE)
            result = self.observe(goal, raw)
            ep.steps.append(Step(tool, result))
            if goal_node:
                self.consolidator.record_step(goal_node, tool, result, episode_id, step_idx)
            if result.success:
                ep.success = True
                break

        ep.transitions.append(State.CONSOLIDATE)
        if goal_node:
            ep.lessons = self.consolidator.consolidate_episode(
                goal_node, [(s.tool, s.result) for s in ep.steps]
            )
            if self.prune_every and episode_id % self.prune_every == 0:
                self.consolidator.prune()

        ep.transitions.append(State.DONE)
        self.episodes.append(ep)
        return ep
