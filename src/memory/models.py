"""Modelos formales (Pydantic v2) de la memoria asociativa.

Son la fuente de verdad del contrato: ``specs/memory_schema.json`` se genera a
partir de ``GraphDocument.model_json_schema()`` (ver ``scripts/export_schema.py``).

Decisión: los timestamps son un **reloj lógico** entero (un tick por episodio),
no fechas reales. Así el decaimiento es determinista y reproducible en tests; si
se necesita la hora real, puede guardarse en ``metadata["wall_time"]``.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = 2


class NodeType(str, Enum):
    GOAL = "Goal"
    ACTION = "Action"
    OUTCOME = "Outcome"
    CONCEPT = "Concept"


class Relation(str, Enum):
    LEADS_TO = "LEADS_TO"
    RESOLVED_BY = "RESOLVED_BY"
    FAILED_DUE_TO = "FAILED_DUE_TO"
    ASSOCIATED_WITH = "ASSOCIATED_WITH"


class _Model(BaseModel):
    # validate_assignment: una actualización de peso fuera de rango falla en el
    # momento de la asignación, no al serializar.
    model_config = ConfigDict(validate_assignment=True, extra="forbid", use_enum_values=False)


class Node(_Model):
    id: str = Field(pattern=r"^(goal|action|outcome|concept):.+$")
    type: NodeType
    label: str
    embedding: list[float] | None = Field(
        default=None, description="Vector semántico del label (#3); None si no se ha calculado."
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Atributos de dominio: kind (Concept), success/latency_ms/error (Outcome), episode...",
    )
    created_at: int = Field(ge=0, description="Tick del reloj lógico en que se creó.")
    last_accessed_at: int = Field(ge=0, description="Último tick en que se escribió o activó.")
    activation_level: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Última activación propagada recibida."
    )


class Edge(_Model):
    source: str
    target: str
    relation: Relation
    weight: float = Field(ge=0.0, le=1.0)
    decay_factor: float = Field(
        ge=0.0, description="λ de la arista: recency_factor = exp(-λ · (clock − last_updated))."
    )
    last_updated: int = Field(ge=0)
    count: int = Field(default=0, ge=0, description="Número de actualizaciones por refuerzo.")
    metadata: dict[str, Any] = Field(default_factory=dict)


class SerializedEdge(Edge):
    recency_factor: float = Field(
        ge=0.0, le=1.0, description="Derivado al serializar; se ignora al cargar."
    )


class GraphDocument(_Model):
    """Documento JSON completo que produce ``MemoryGraph.to_dict()``."""

    schema_version: Literal[2] = SCHEMA_VERSION
    clock: int = Field(ge=0, description="Reloj lógico: +1 por episodio.")
    default_decay_factor: float = Field(ge=0.0, description="decay_factor de las aristas nuevas.")
    nodes: list[Node]
    edges: list[SerializedEdge]
