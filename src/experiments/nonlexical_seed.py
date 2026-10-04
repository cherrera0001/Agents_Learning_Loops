"""Recuperación sembrada con una señal no léxica frente al señuelo (H8, #98): agente opt-in y condiciones.

Especificación: ``docs/preregistration/h8-nonlexical-seed.md`` (secciones 2, 3, 7 y 8). Cuatro condiciones
con un solo agente opt-in que declara la suya:

- ``A`` (``NO_MEMORY``) y ``B`` (``TEXT_HISTORY``): sin siembra, como en la campaña de referencia;
- ``C_L`` (``ASSOCIATIVE_MEMORY``): la siembra léxica de H4, ``EvidenceMemory.retrieve`` sin cambios;
- ``C_S`` (``ASSOCIATIVE_MEMORY``): la siembra con los componentes de la traza de ``test-0``
  (``trace_seed.seeded_retrieval``), sin consulta léxica ni respaldo.

La señal entra en la **recuperación**, no en la decisión: en las cuatro, ``plan()`` es el del agente por
defecto, con ``policy`` como único campo añadido y sin ningún campo del diagnóstico D. Dentro de una
ejecución el orden es ``test-0``, ``RETRIEVE``, ``plan``; ``tests[1:]`` nunca llegan a la recuperación. El
agente por defecto, ``agent.py``, ``memory.py`` y las campañas publicadas no cambian.
"""

from .agent import AgentView, BoundedRepairAgent
from .memory import EvidenceMemory
from .trace_seed import POLICY, seeded_retrieval, trace_components

AGENT_NAME = BoundedRepairAgent.name + "+trace-seed-v1"
# Señal de siembra de cada condición (tabla de la sección 3); ``None`` = la condición no siembra.
LEXICAL, TRACE = "lexical-title-context", "trace-components"
# Condición → (modo de memoria, señal de siembra).
CONDITIONS = {
    "A": ("NO_MEMORY", None),
    "B": ("TEXT_HISTORY", None),
    "C_L": ("ASSOCIATIVE_MEMORY", LEXICAL),
    "C_S": ("ASSOCIATIVE_MEMORY", TRACE),
}
# Declaración exacta que escribe el runner en cada recibo de este agente. El orden lo impone el código del
# runner (y lo prueba un test por orden de llamadas); el evaluador exige este valor y un ``test-0`` fallido.
DECISION_INPUTS = {"order": ["test-0", "RETRIEVE", "plan"], "reproduction": "test-0"}


def condition_of(condition):
    """(modo de memoria, señal de siembra) de una condición de H8; ``ValueError`` si no lo es."""
    if condition not in CONDITIONS:
        raise ValueError(f"condición de siembra desconocida: {condition!r}")
    return CONDITIONS[condition]


class TraceSeedRepairAgent(BoundedRepairAgent):
    """Mismos operadores, parches y ``plan()``; solo declara su política. La siembra ocurre antes, en la
    recuperación, y este agente recibe una ``AgentView`` como el agente por defecto: no ve ``test-0``."""

    name = AGENT_NAME
    seeds_retrieval = True

    def plan(self, view):
        return {**super().plan(view), "policy": POLICY}


def retrieve(memory, condition, query, stderr, files):
    """Recuperación de una condición: (lecciones expuestas, caminos, bloque de siembra del recibo).

    A, B y C_L recuperan exactamente como el agente por defecto (``memory.retrieve(query, modo)``) y no
    usan la traza. C_S recibe solo el ``stderr`` de ``test-0``, las claves de archivo y la memoria. Los
    componentes extraídos se registran en las cuatro, para que el evaluador compruebe que la señal es la
    misma; ``seeds``, ``state`` y ``lesson`` solo existen en C_S.
    """
    mode, signal = condition_of(condition)
    if signal == TRACE:
        memories, paths, block = seeded_retrieval(memory.snapshot(), stderr, files)
        return memories, paths, {**block, "signal": signal}
    memories, paths = memory.retrieve(query, mode)
    block = {
        "policy": POLICY,
        "signal": signal,
        "components": trace_components(stderr, files),
        "seeds": None,
        "state": None,
        "lesson": None,
    }
    return memories, paths, block


def retrieval_inputs(condition, query, stderr, files, memory_sha256):
    """Lo que recibió la recuperación de una condición: entra en el contexto hasheado del agente."""
    mode, signal = condition_of(condition)
    inputs = {"condition": condition, "policy": POLICY, "signal": signal}
    if mode != "NO_MEMORY":
        inputs["memory_sha256"] = memory_sha256
    if signal == LEXICAL:
        inputs["query"] = query
    if signal == TRACE:
        inputs["stderr"] = stderr
        inputs["files"] = sorted(files)
    return inputs


def query_of(task):
    """La clave léxica de una tarea (``PublicTask.query``), desde el recibo."""
    return task["title"] + " " + task["context"]


def replay_retrieval(record):
    """Repite la recuperación desde el recibo (lado del evaluador): ``tests[0].stderr``, las claves de
    ``initial_source`` y ``memory_input``, más ``title + context`` en C_L."""
    return retrieve(
        EvidenceMemory(record["memory_input"]),
        record["condition"],
        query_of(record["task"]),
        record["tests"][0]["stderr"],
        tuple(record["initial_source"]),
    )


def replay_context(record):
    """El contexto que el runner hasheó en ``agent_context_sha256``, reconstruido desde el recibo."""
    return {
        "task": record["task"],
        "files": record["initial_source"],
        "memories": record["retrieval"]["memories"],
        "retrieval": retrieval_inputs(
            record["condition"],
            query_of(record["task"]),
            record["tests"][0]["stderr"],
            tuple(record["initial_source"]),
            record["memory_before_sha256"],
        ),
    }


def replay_decision(record):
    """Repite la decisión con el ``plan()`` **por defecto**, desde la tarea, las lecciones expuestas, el
    modo y la semilla: la decisión de este agente no puede usar nada más."""
    view = AgentView(
        record["task"],
        dict(record["initial_source"]),
        tuple(record["retrieval"]["memories"]),
        record["memory_mode"],
        record["seed"],
    )
    return {**BoundedRepairAgent().plan(view), "policy": POLICY}
