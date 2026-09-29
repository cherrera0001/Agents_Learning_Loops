"""Agents Learning Loops: memoria asociativa en grafo para bucles de aprendizaje de agentes."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("associative-agent-loop")
except PackageNotFoundError:  # ejecutado desde el árbol de fuentes sin instalar
    __version__ = "0.0.0+local"

from .agent.core import Agent, Episode, State
from .agent.tools import Tool, ToolResult
from .config import AppConfig, load_config
from .memory.associative import RetrievalConfig, Retriever
from .memory.consolidation import Consolidator
from .memory.graph import MemoryGraph
from .memory.store import GraphStore, JsonGraphStore

__all__ = [
    "Agent",
    "AppConfig",
    "Consolidator",
    "Episode",
    "GraphStore",
    "JsonGraphStore",
    "MemoryGraph",
    "RetrievalConfig",
    "Retriever",
    "State",
    "Tool",
    "ToolResult",
    "__version__",
    "load_config",
]
