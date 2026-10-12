"""Costo en horas de cuota del brazo «solo razonamiento» de la iteración 08 y regla de parada (#182).

Es aritmética sobre cifras que se pasan como argumento; no lee ni escribe nada y no usa la red. Las constantes
son las del armado del brazo: cinco porciones de doce tareas (``experiments/gemma_developer_agent/docs/
ensayo_nucleo_jupyter.md``, sección del #182).

    cuota_h = porciones x factor x (tareas x media_por_tarea_s + carga_s) / 3600

``factor`` es las horas de cuota por hora de reloj (2,0 en las medidas del experimento).
"""

from __future__ import annotations

from dataclasses import dataclass

PORCIONES = 5
TAREAS_POR_PORCION = 12
FACTOR_DE_CUOTA = 2.0
# La tarea más larga de las 250 filas del rescate del 2026-10-09 (303,6 s), redondeada como en la cuenta.
TAREA_MAS_LARGA_S = 304.0
# Carga del modelo medida en las sesiones rescatadas: la menor y la mayor.
CARGA_MINIMA_S = 364.0
CARGA_MAXIMA_S = 1142.0
# Dos pasadas de la base, cifra del encargo del concilio (no recalculada aquí).
PASADAS_DE_BASE_H = 2 * 5.6
TOPE_DEL_PLAN_H = 24.0
MEDIA_MAXIMA_POR_TAREA_S = 240.0


def cuota_horas(
    media_por_tarea_s: float,
    carga_s: float,
    porciones: int = PORCIONES,
    tareas: int = TAREAS_POR_PORCION,
    factor: float = FACTOR_DE_CUOTA,
) -> float:
    """Horas de cuota de ``porciones`` sesiones de ``tareas`` tareas, cada una con su carga del modelo."""
    return porciones * factor * (tareas * media_por_tarea_s + carga_s) / 3600


@dataclass(frozen=True)
class Decision:
    """Qué dice la regla tras leer la primera porción."""

    lanzar_el_resto: bool
    proyeccion_h: float
    motivo: str


def proyeccion_del_plan_h(
    media_por_tarea_s: float, carga_s: float, base_h: float = PASADAS_DE_BASE_H
) -> float:
    """Cuota del brazo entero si las cinco porciones repiten lo de la primera, más las pasadas de base."""
    return cuota_horas(media_por_tarea_s, carga_s) + base_h


def tras_la_primera_porcion(
    media_por_tarea_s: float,
    carga_s: float,
    tope_h: float = TOPE_DEL_PLAN_H,
    media_maxima_s: float = MEDIA_MAXIMA_POR_TAREA_S,
    base_h: float = PASADAS_DE_BASE_H,
) -> Decision:
    """La regla del concilio: no se lanzan las otras cuatro si la media pasa de 240 s o la proyección de 24 h.

    Pasar es estrictamente mayor: una media de exactamente 240 s o una proyección de exactamente 24 h no
    detiene. Con las constantes de este módulo la media de 240 s detiene antes que las 24 h (a 240 s y con la
    carga mayor la proyección es de 22,4 h); la proyección solo manda si las pasadas de base cuestan más de
    11,2 h.
    """
    proyeccion = proyeccion_del_plan_h(media_por_tarea_s, carga_s, base_h)
    if media_por_tarea_s > media_maxima_s:
        motivo = f"la media por tarea ({media_por_tarea_s:g} s) pasa de {media_maxima_s:g} s"
        return Decision(False, proyeccion, motivo)
    if proyeccion > tope_h:
        return Decision(False, proyeccion, f"la proyección ({proyeccion:.2f} h) pasa de {tope_h:g} h")
    return Decision(True, proyeccion, "ni la media ni la proyección pasan de su tope")
