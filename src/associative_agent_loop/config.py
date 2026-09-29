"""Configuración centralizada (Pydantic), cargable desde TOML y variables de entorno.

Ejemplo ``aal.toml``::

    [agent]
    max_attempts = 3
    prune_every = 10

    [retrieval]
    damping = 0.7
    fan_out = "sqrt"

    [consolidation]
    hebbian_rate = 0.3
    max_edges = 5000

Variables de entorno con prefijo ``AAL_`` y ``__`` como separador de sección
tienen prioridad sobre el archivo: ``AAL_RETRIEVAL__DAMPING=0.6``.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .memory.associative import RetrievalConfig

ENV_PREFIX = "AAL_"


class AgentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    use_memory: bool = True
    max_attempts: int = Field(3, ge=1)
    prune_every: int = Field(10, ge=0, description="0 desactiva la poda periódica.")
    decay_rate: float = Field(0.05, ge=0.0, description="decay_factor por defecto de aristas nuevas.")


class ConsolidationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    learning_rate: float = Field(0.4, gt=0.0, le=1.0)
    penalty_rate: float = Field(0.2, gt=0.0, le=1.0)
    hebbian_rate: float = Field(0.3, ge=0.0, le=1.0)
    prune_threshold: float = Field(0.02, ge=0.0, le=1.0)
    max_edges: int | None = Field(None, ge=1)


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent: AgentConfig = Field(default_factory=AgentConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    consolidation: ConsolidationConfig = Field(default_factory=ConsolidationConfig)


def _env_overrides(environ: dict[str, str]) -> dict[str, dict[str, Any]]:
    overrides: dict[str, dict[str, Any]] = {}
    for key, value in environ.items():
        if not key.startswith(ENV_PREFIX) or "__" not in key:
            continue
        section, _, field = key[len(ENV_PREFIX) :].lower().partition("__")
        overrides.setdefault(section, {})[field] = value  # Pydantic convierte los tipos
    return overrides


def load_config(path: str | Path | None = None, environ: dict[str, str] | None = None) -> AppConfig:
    """Carga la configuración: valores por defecto ← TOML (si existe) ← variables de entorno."""
    data: dict[str, dict[str, Any]] = {}
    if path is not None:
        data = tomllib.loads(Path(path).read_text("utf-8"))
    for section, values in _env_overrides(dict(os.environ if environ is None else environ)).items():
        data.setdefault(section, {}).update(values)
    return AppConfig.model_validate(data)
