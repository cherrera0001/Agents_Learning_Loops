"""Herramientas simuladas y escenarios de benchmark.

Cada herramienta es una función ``query -> ToolResult``. Los escenarios
reproducen problemas típicos de agentes en producción:

- ``weather_scenario``: una API deprecada (HTTP 410) listada primero y su
  reemplazo funcional. El agente sin memoria siempre cae en la trampa.
- ``flaky_scenario``: una API rápida con errores intermitentes (HTTP 503) y
  otra más lenta pero estable. Con semilla fija → resultados reproducibles.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable


@dataclass
class ToolResult:
    success: bool
    output: str | None = None
    error: str | None = None
    latency_ms: float = 0.0


@dataclass
class Tool:
    name: str
    description: str
    fn: Callable[[str], ToolResult]

    def __call__(self, query: str) -> ToolResult:
        return self.fn(query)


def weather_scenario() -> list[Tool]:
    def v1(query: str) -> ToolResult:
        return ToolResult(False, error="HTTP 410 Gone: endpoint deprecated", latency_ms=40)

    def v2(query: str) -> ToolResult:
        return ToolResult(True, output=f"Pronóstico para '{query}': 18°C, despejado", latency_ms=120)

    return [
        Tool("weather_api_v1", "API de clima (legacy)", v1),
        Tool("weather_api_v2", "API de clima (actual)", v2),
    ]


def domain_scenario() -> list[Tool]:
    """Una API genérica rápida que falla solo en el dominio *clima* y un respaldo lento.

    Sirve para verificar que un fallo en un dominio no contamina otro (#8).
    """

    def generic(query: str) -> ToolResult:
        if "clima" in query.lower():
            return ToolResult(False, error="HTTP 422 dominio no soportado", latency_ms=20)
        return ToolResult(True, output=f"resultado genérico para '{query}'", latency_ms=20)

    def fallback(query: str) -> ToolResult:
        return ToolResult(True, output=f"resultado de respaldo para '{query}'", latency_ms=300)

    return [
        Tool("generic_api", "API genérica (rápida)", generic),
        Tool("fallback_api", "API de respaldo (lenta)", fallback),
    ]


def flaky_scenario(failure_rate: float = 0.7, seed: int = 7) -> list[Tool]:
    rng = random.Random(seed)

    def fast(query: str) -> ToolResult:
        if rng.random() < failure_rate:
            return ToolResult(False, error="HTTP 503 Service Unavailable", latency_ms=30)
        return ToolResult(True, output=f"1 USD = 950 CLP ({query})", latency_ms=30)

    def stable(query: str) -> ToolResult:
        return ToolResult(True, output=f"1 USD = 948 CLP ({query})", latency_ms=250)

    return [
        Tool("fx_fast_api", "Tipo de cambio (rápida, inestable)", fast),
        Tool("fx_stable_api", "Tipo de cambio (lenta, estable)", stable),
    ]
