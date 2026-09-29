"""Adaptador del grafo de memoria asociativa sobre NetworkX.

El grafo es un ``MultiDiGraph`` donde la *clave* de cada arista es su tipo
semántico, de modo que entre dos nodos puede existir a lo sumo una arista de
cada tipo (p. ej. ``LEADS_TO`` y ``RESOLVED_BY`` en paralelo).

El tiempo es un reloj lógico (``clock``) que avanza una unidad por episodio.
Usar un reloj lógico en vez de ``time.time()`` hace que el decaimiento sea
determinista y reproducible en pruebas.
"""

from __future__ import annotations

import json
import math
from enum import Enum
from pathlib import Path
from typing import Any, Iterator

import networkx as nx


class NodeType(str, Enum):
    GOAL = "Goal"
    ACTION = "Action"
    OUTCOME = "Outcome"
    CONCEPT = "Concept"


class EdgeType(str, Enum):
    LEADS_TO = "LEADS_TO"
    RESOLVED_BY = "RESOLVED_BY"
    FAILED_DUE_TO = "FAILED_DUE_TO"
    ASSOCIATED_WITH = "ASSOCIATED_WITH"


class MemoryGraph:
    """Grafo de memoria con aristas ponderadas y decaimiento temporal."""

    def __init__(self, decay_rate: float = 0.05) -> None:
        self.g = nx.MultiDiGraph()
        self.decay_rate = decay_rate
        self.clock = 0

    # ------------------------------------------------------------------ reloj
    def tick(self) -> int:
        """Avanza el reloj lógico (una unidad por episodio)."""
        self.clock += 1
        return self.clock

    # ------------------------------------------------------------------ nodos
    def add_node(self, node_id: str, node_type: NodeType, label: str, **attrs: Any) -> str:
        """Inserta o actualiza un nodo (idempotente por ``node_id``)."""
        if node_id in self.g:
            self.g.nodes[node_id].update(attrs)
            self.g.nodes[node_id]["last_seen"] = self.clock
        else:
            self.g.add_node(
                node_id,
                type=NodeType(node_type).value,
                label=label,
                created_at=self.clock,
                last_seen=self.clock,
                **attrs,
            )
        return node_id

    def node(self, node_id: str) -> dict[str, Any]:
        return self.g.nodes[node_id]

    def has_node(self, node_id: str) -> bool:
        return node_id in self.g

    def nodes_of_type(self, node_type: NodeType) -> list[str]:
        t = NodeType(node_type).value
        return [n for n, d in self.g.nodes(data=True) if d["type"] == t]

    # ----------------------------------------------------------------- aristas
    def add_edge(
        self, src: str, dst: str, edge_type: EdgeType, weight: float = 0.5, **attrs: Any
    ) -> None:
        """Crea la arista si no existe; si existe, solo refresca atributos.

        Ambos extremos deben existir: NetworkX crearía nodos sin tipo en silencio.
        """
        for n in (src, dst):
            if n not in self.g:
                raise KeyError(f"nodo inexistente: {n!r}")
        key = EdgeType(edge_type).value
        if self.g.has_edge(src, dst, key=key):
            self.g.edges[src, dst, key].update(attrs)
            return
        self.g.add_edge(
            src,
            dst,
            key=key,
            type=key,
            weight=float(weight),
            last_updated=self.clock,
            count=0,
            **attrs,
        )

    def has_edge(self, src: str, dst: str, edge_type: EdgeType) -> bool:
        return self.g.has_edge(src, dst, key=EdgeType(edge_type).value)

    def edge(self, src: str, dst: str, edge_type: EdgeType) -> dict[str, Any]:
        return self.g.edges[src, dst, EdgeType(edge_type).value]

    def recency_factor(self, edge_data: dict[str, Any]) -> float:
        """``exp(-λ · Δt)``: 1.0 para aristas recién actualizadas, → 0 con el tiempo."""
        age = self.clock - edge_data["last_updated"]
        return math.exp(-self.decay_rate * max(age, 0))

    def effective_weight(self, edge_data: dict[str, Any]) -> float:
        """Peso efectivo = ``weight × recency_factor``."""
        return edge_data["weight"] * self.recency_factor(edge_data)

    def out_edges(
        self, node_id: str, edge_type: EdgeType | None = None
    ) -> Iterator[tuple[str, str, dict[str, Any]]]:
        for src, dst, key, data in self.g.out_edges(node_id, keys=True, data=True):
            if edge_type is None or key == EdgeType(edge_type).value:
                yield src, dst, data

    def in_edges(
        self, node_id: str, edge_type: EdgeType | None = None
    ) -> Iterator[tuple[str, str, dict[str, Any]]]:
        for src, dst, key, data in self.g.in_edges(node_id, keys=True, data=True):
            if edge_type is None or key == EdgeType(edge_type).value:
                yield src, dst, data

    def remove_edge(self, src: str, dst: str, edge_type: EdgeType) -> None:
        self.g.remove_edge(src, dst, key=EdgeType(edge_type).value)

    def remove_node(self, node_id: str) -> None:
        self.g.remove_node(node_id)

    # ---------------------------------------------------------- serialización
    def to_dict(self) -> dict[str, Any]:
        """Serializa según ``specs/memory_schema.json``."""
        return {
            "clock": self.clock,
            "decay_rate": self.decay_rate,
            "nodes": [{"id": n, **d} for n, d in self.g.nodes(data=True)],
            "edges": [
                {
                    "source": s,
                    "target": t,
                    **d,
                    "recency_factor": round(self.recency_factor(d), 6),
                }
                for s, t, d in self.g.edges(data=True)
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryGraph":
        mg = cls(decay_rate=data.get("decay_rate", 0.05))
        mg.clock = data.get("clock", 0)
        for node in data["nodes"]:
            attrs = dict(node)
            mg.g.add_node(attrs.pop("id"), **attrs)
        for edge in data["edges"]:
            attrs = dict(edge)
            src, dst = attrs.pop("source"), attrs.pop("target")
            attrs.pop("recency_factor", None)  # derivado, se recalcula
            mg.g.add_edge(src, dst, key=attrs["type"], **attrs)
        return mg

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), "utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "MemoryGraph":
        return cls.from_dict(json.loads(Path(path).read_text("utf-8")))

    def __len__(self) -> int:
        return self.g.number_of_nodes()

    def stats(self) -> dict[str, int]:
        counts = {t.value: 0 for t in NodeType}
        for _, d in self.g.nodes(data=True):
            counts[d["type"]] += 1
        counts["edges"] = self.g.number_of_edges()
        return counts
