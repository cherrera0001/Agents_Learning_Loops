"""Adaptador del grafo de memoria asociativa sobre NetworkX.

El grafo es un ``MultiDiGraph`` cuya *clave* de arista es la relación, de modo
que entre dos nodos existe a lo sumo una arista de cada tipo. Cada nodo y arista
guarda su modelo Pydantic (``Node`` / ``Edge``) en el atributo ``model``: la
validación ocurre al crear y al asignar (p. ej. un peso fuera de [0, 1] falla).

El tiempo es un reloj lógico (``clock``) que avanza una unidad por episodio.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Iterator

import networkx as nx

from .models import (
    SCHEMA_VERSION,
    Edge,
    GraphDocument,
    Node,
    NodeType,
    Relation,
    SerializedEdge,
)

# Alias retrocompatible: el código y los tests v0.1 usan ``EdgeType``.
EdgeType = Relation

__all__ = ["MemoryGraph", "Node", "Edge", "NodeType", "Relation", "EdgeType"]


class MemoryGraph:
    """Grafo de memoria con aristas ponderadas y decaimiento temporal por arista."""

    def __init__(self, decay_rate: float = 0.05) -> None:
        self.g = nx.MultiDiGraph()
        self.decay_rate = decay_rate  # decay_factor por defecto de las aristas nuevas
        self.clock = 0
        self.embedding_model: str | None = None  # modelo de los Node.embedding

    # ------------------------------------------------------------------ reloj
    def tick(self) -> int:
        """Avanza el reloj lógico (una unidad por episodio)."""
        self.clock += 1
        return self.clock

    # ------------------------------------------------------------------ nodos
    def add_node(self, node_id: str, node_type: NodeType, label: str, **metadata: Any) -> str:
        """Inserta o actualiza un nodo (idempotente por ``node_id``).

        Los ``metadata`` se fusionan con los existentes y se refresca ``last_accessed_at``.
        """
        if node_id in self.g:
            node = self.node(node_id)
            node.metadata.update(metadata)
            node.last_accessed_at = self.clock
        else:
            node = Node(
                id=node_id,
                type=NodeType(node_type),
                label=label,
                metadata=metadata,
                created_at=self.clock,
                last_accessed_at=self.clock,
            )
            self.g.add_node(node_id, model=node)
        return node_id

    def node(self, node_id: str) -> Node:
        return self.g.nodes[node_id]["model"]

    def nodes(self) -> Iterator[Node]:
        for _, data in self.g.nodes(data=True):
            yield data["model"]

    def has_node(self, node_id: str) -> bool:
        return node_id in self.g

    def nodes_of_type(self, node_type: NodeType) -> list[str]:
        t = NodeType(node_type)
        return [n.id for n in self.nodes() if n.type == t]

    # ----------------------------------------------------------------- aristas
    def add_edge(
        self,
        src: str,
        dst: str,
        relation: Relation,
        weight: float = 0.5,
        decay_factor: float | None = None,
        **metadata: Any,
    ) -> Edge:
        """Crea la arista si no existe; si existe, solo fusiona ``metadata``.

        Ambos extremos deben existir: NetworkX crearía nodos sin modelo en silencio.
        """
        for n in (src, dst):
            if n not in self.g:
                raise KeyError(f"nodo inexistente: {n!r}")
        rel = Relation(relation)
        if self.g.has_edge(src, dst, key=rel.value):
            edge = self.edge(src, dst, rel)
            edge.metadata.update(metadata)
            return edge
        edge = Edge(
            source=src,
            target=dst,
            relation=rel,
            weight=weight,
            decay_factor=self.decay_rate if decay_factor is None else decay_factor,
            last_updated=self.clock,
            metadata=metadata,
        )
        self.g.add_edge(src, dst, key=rel.value, model=edge)
        return edge

    def has_edge(self, src: str, dst: str, relation: Relation) -> bool:
        return self.g.has_edge(src, dst, key=Relation(relation).value)

    def edge(self, src: str, dst: str, relation: Relation) -> Edge:
        return self.g.edges[src, dst, Relation(relation).value]["model"]

    def edges(self) -> Iterator[Edge]:
        for *_, data in self.g.edges(data=True):
            yield data["model"]

    def recency_factor(self, edge: Edge) -> float:
        """``exp(-λ · Δt)``: 1.0 para aristas recién actualizadas, → 0 con el tiempo."""
        age = self.clock - edge.last_updated
        return math.exp(-edge.decay_factor * max(age, 0))

    def effective_weight(self, edge: Edge) -> float:
        """Peso efectivo = ``weight × recency_factor``."""
        return edge.weight * self.recency_factor(edge)

    def out_edges(
        self, node_id: str, relation: Relation | None = None
    ) -> Iterator[tuple[str, str, Edge]]:
        for src, dst, key, data in self.g.out_edges(node_id, keys=True, data=True):
            if relation is None or key == Relation(relation).value:
                yield src, dst, data["model"]

    def in_edges(
        self, node_id: str, relation: Relation | None = None
    ) -> Iterator[tuple[str, str, Edge]]:
        for src, dst, key, data in self.g.in_edges(node_id, keys=True, data=True):
            if relation is None or key == Relation(relation).value:
                yield src, dst, data["model"]

    def remove_edge(self, src: str, dst: str, relation: Relation) -> None:
        self.g.remove_edge(src, dst, key=Relation(relation).value)

    def remove_node(self, node_id: str) -> None:
        self.g.remove_node(node_id)

    # ---------------------------------------------------------- serialización
    def to_document(self) -> GraphDocument:
        return GraphDocument(
            clock=self.clock,
            default_decay_factor=self.decay_rate,
            embedding_model=self.embedding_model,
            nodes=list(self.nodes()),
            edges=[
                SerializedEdge(**e.model_dump(), recency_factor=round(self.recency_factor(e), 6))
                for e in self.edges()
            ],
        )

    def to_dict(self) -> dict[str, Any]:
        """Serializa según ``specs/memory_schema.json`` (schema_version 2)."""
        return self.to_document().model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryGraph":
        if data.get("schema_version", 1) < SCHEMA_VERSION:
            data = migrate_v1(data)
        doc = GraphDocument.model_validate(data)
        mg = cls(decay_rate=doc.default_decay_factor)
        mg.clock = doc.clock
        mg.embedding_model = doc.embedding_model
        for node in doc.nodes:
            mg.g.add_node(node.id, model=node)
        for sedge in doc.edges:
            edge = Edge(**sedge.model_dump(exclude={"recency_factor"}))
            mg.g.add_edge(edge.source, edge.target, key=edge.relation.value, model=edge)
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
        for node in self.nodes():
            counts[node.type.value] += 1
        counts["edges"] = self.g.number_of_edges()
        return counts


_V1_NODE_FIELDS = {"id", "type", "label", "created_at", "last_seen"}
_V1_EDGE_FIELDS = {"source", "target", "type", "weight", "last_updated", "count", "recency_factor"}


def migrate_v1(data: dict[str, Any]) -> dict[str, Any]:
    """Convierte un documento v0.1 (atributos sueltos, λ global) al esquema v2."""
    decay = data.get("decay_rate", 0.05)
    nodes = [
        {
            "id": n["id"],
            "type": n["type"],
            "label": n["label"],
            "created_at": n["created_at"],
            "last_accessed_at": n.get("last_seen", n["created_at"]),
            "metadata": {k: v for k, v in n.items() if k not in _V1_NODE_FIELDS},
        }
        for n in data["nodes"]
    ]
    edges = [
        {
            "source": e["source"],
            "target": e["target"],
            "relation": e["type"],
            "weight": e["weight"],
            "decay_factor": decay,
            "last_updated": e["last_updated"],
            "count": e.get("count", 0),
            "recency_factor": e.get("recency_factor", 1.0),
            "metadata": {k: v for k, v in e.items() if k not in _V1_EDGE_FIELDS},
        }
        for e in data["edges"]
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "clock": data.get("clock", 0),
        "default_decay_factor": decay,
        "nodes": nodes,
        "edges": edges,
    }
