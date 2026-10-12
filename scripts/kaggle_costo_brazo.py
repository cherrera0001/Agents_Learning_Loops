"""Costo en horas de cuota del brazo «solo razonamiento» de la iteración 08 y regla de parada (#182).

Es aritmética sobre cifras que se pasan como argumento; no lee ni escribe nada y no usa la red. Las constantes
son las del armado del brazo: cinco porciones de doce tareas (``experiments/gemma_developer_agent/docs/
ensayo_nucleo_jupyter.md``, sección del #182).

    cuota_h = porciones x factor x (tareas x media_por_tarea_s + carga_s) / 3600

``factor`` son las horas de cuota por hora de reloj. El 2,0 es un supuesto de la cuenta del concilio 43: no
tiene una fuente versionada que lo mida. El 2,25 es su techo, y es el que da las 5,6 h de una pasada de base
(9 000 s x 2,25 / 3 600 = 5,6; inferido). La fórmula no cuenta el tramo entre la carga y la primera tarea (de
91 a 122 s en las cinco sesiones rescatadas que traen ambos) ni el cierre de la sesión (no medido).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

PORCIONES = 5
TAREAS_POR_PORCION = 12
FACTOR_DE_CUOTA = 2.0
FACTOR_TECHO = 2.25
# El máximo observado en las 250 filas del rescate del 2026-10-09 (303,6 s), redondeado como en la cuenta.
# No es el tope por tarea: ese es TOPE_POR_TAREA_S.
MAXIMO_OBSERVADO_S = 304.0
# Lo que los topes del arnés permiten a una tarea que no se cuelga: 240 s del agente + 5 órdenes de 60 s.
TOPE_POR_TAREA_S = 540.0
# Carga del modelo medida en las sesiones rescatadas: la menor y la mayor.
CARGA_MINIMA_S = 364.0
CARGA_MAXIMA_S = 1142.0
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


def pasadas_de_base_h(factor: float) -> float:
    """Dos pasadas de base de 2,5 h de sesión cada una (9 000 s), con el mismo factor que el brazo."""
    return 2 * 2.5 * factor


def proyeccion_del_plan_h(
    media_por_tarea_s: float,
    carga_s: float,
    base_h: float | None = None,
    factor: float = FACTOR_TECHO,
) -> float:
    """Cuota del brazo entero si las cinco porciones repiten lo de la primera, más las pasadas de base.

    Por defecto usa el factor techo (2,25) en el brazo y en la base (11,25 h); ``base_h`` lo reemplaza.
    """
    base = pasadas_de_base_h(factor) if base_h is None else base_h
    return cuota_horas(media_por_tarea_s, carga_s, factor=factor) + base


def _valido(valor: float) -> bool:
    return math.isfinite(valor) and valor >= 0


def tras_la_primera_porcion(
    media_por_tarea_s: float,
    carga_s: float,
    tope_h: float = TOPE_DEL_PLAN_H,
    media_maxima_s: float = MEDIA_MAXIMA_POR_TAREA_S,
    base_h: float | None = None,
    factor: float = FACTOR_TECHO,
) -> Decision:
    """La regla del concilio: no se lanzan las otras cuatro si la media pasa de 240 s o la proyección de 24 h.

    Pasar es estrictamente mayor: una media de exactamente 240 s o una proyección de exactamente 24 h no
    detiene. Una media o una carga que no sean un número finito y no negativo (la media de cero filas es NaN)
    no autorizan nada: la decisión es no lanzar, con el motivo.

    Para decidir se usa el factor techo (2,25) en el brazo y en la base (11,25 h): a 240 s la proyección es de
    21,4 h con la carga menor y de 23,8 h con la mayor (1 142 s), y pasa de 24 h solo con una carga de más de
    1 200 s o con unas pasadas de base de más de 11,43 h (con la carga mayor). Por debajo de eso manda la
    media. Con el 2,0 en ambos (base de 10 h) los umbrales son 2 160 s de carga y 12,83 h de base; con la base
    mezclada del encargo (11,2 h), 1 728 s.
    """
    if not _valido(media_por_tarea_s) or not _valido(carga_s):
        motivo = (
            f"la media ({media_por_tarea_s!r} s) o la carga ({carga_s!r} s) no es un número finito "
            "y no negativo: no se puede decidir"
        )
        return Decision(False, math.nan, motivo)
    proyeccion = proyeccion_del_plan_h(media_por_tarea_s, carga_s, base_h, factor)
    if media_por_tarea_s > media_maxima_s:
        motivo = f"la media por tarea ({media_por_tarea_s:g} s) pasa de {media_maxima_s:g} s"
        return Decision(False, proyeccion, motivo)
    if proyeccion > tope_h:
        return Decision(False, proyeccion, f"la proyección ({proyeccion:.2f} h) pasa de {tope_h:g} h")
    return Decision(True, proyeccion, "ni la media ni la proyección pasan de su tope")
