"""Persistencia del grafo de memoria.

``GraphStore`` es el punto de extensión para backends persistentes (SQLite,
Neo4j...). ``JsonGraphStore`` es la implementación por defecto: escribe de forma
**atómica** (archivo temporal en el mismo directorio + ``os.replace``), así que
un proceso interrumpido nunca deja un JSON truncado.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from .fsutil import atomic_write_text
from .graph import MemoryGraph


class GraphStore(Protocol):
    def load(self) -> MemoryGraph: ...

    def save(self, graph: MemoryGraph) -> None: ...


class JsonGraphStore:
    """Grafo serializado como JSON (``specs/memory_schema.json``)."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def exists(self) -> bool:
        return self.path.exists()

    def load(self) -> MemoryGraph:
        return MemoryGraph.from_dict(json.loads(self.path.read_text("utf-8")))

    def load_or_new(self, decay_rate: float = 0.05) -> MemoryGraph:
        return self.load() if self.exists() else MemoryGraph(decay_rate=decay_rate)

    def save(self, graph: MemoryGraph) -> None:
        atomic_write_text(self.path, json.dumps(graph.to_dict(), indent=2, ensure_ascii=False) + "\n")
