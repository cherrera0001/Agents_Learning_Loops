"""Siembra de la recuperación con los componentes de la traza de la reproducción pública (H8, #98).

Especificación: ``docs/preregistration/h8-nonlexical-seed.md``, sección 2. Este módulo es la **función de
siembra** y no conoce nada más: recibe el ``stderr`` de ``test-0``, las claves de archivo que el solver
acotado ya ve y la memoria de la condición. No recibe la tarea, no lee ningún archivo y no contiene ninguna
regla que nombre una tarea, una familia ni una estrategia de reparación: la única operación es comparar una
ruta de la traza con la ruta de un parche anterior.

Extracción, por bloque de fallo de ``unittest`` (``ERROR: `` o ``FAIL: ``) y solo sobre su **última** traza:
los marcos cuya ruta termina en ``/`` seguido de una clave de archivo son marcos de aplicación; el más cercano
al punto donde se lanza la excepción pesa 1, el siguiente 1/2, después 1/3. ``T(k)`` es el máximo sobre los
bloques. Se siembran solo los nodos ``Component`` con puntuación mayor que 0; no hay consulta léxica ni
respaldo. La proyección, la propagación, el corte y el top-1 son los de ``EvidenceMemory.retrieve``.

«No léxica» quiere decir «sin la consulta léxica de ``title + context``»: la política sí compara cadenas.
"""

import re

from associative_agent_loop.memory.associative import RetrievalConfig, Retriever
from associative_agent_loop.memory.graph import EdgeType, MemoryGraph, NodeType

from .evidence import normalize_source

POLICY = "trace-component-seed/v1"
SEED_NODE_TYPE = "Component"
# Estados de la siembra (tabla de la sección 2).
SEEDED, TIE, EMPTY = "seeded", "tie", "empty"
# Corte de activación y parámetros de la propagación: los de ``EvidenceMemory.retrieve``.
ACTIVATION_CUT = 0.005
EDGE_WEIGHT = 0.7
MAX_HOPS = 5
FIRING_THRESHOLD = 0.001

_SEPARATOR = re.compile(r"^={20,}$", re.MULTILINE)
_HEADER = re.compile(r"^(ERROR|FAIL): ")
_DASHES = re.compile(r"^-{20,}$")
_TRACEBACK = "Traceback (most recent call last):"
_FRAME = re.compile(r'^\s+File "(.*)", line \d+, in .+$')


def failure_blocks(stderr):
    """Bloques de fallo de ``unittest``, como el diagnóstico D: sin BOM ni CRLF, y sin el resumen final."""
    text = normalize_source(stderr or "")
    blocks = []
    for chunk in _SEPARATOR.split(text):
        lines = chunk.lstrip("\n").split("\n")
        if _HEADER.match(lines[0]) is None:
            continue
        body = lines[1:]
        for i in range(1, len(body)):
            if body[i].startswith("Ran ") and _DASHES.match(body[i - 1]):
                body = body[: i - 1]
                break
        blocks.append(body)
    return blocks


def application_frames(block, files):
    """Componentes de los marcos de aplicación de la última traza de un bloque, del más externo al más
    interno. De cada marco solo se usa la ruta; los marcos de tests y de la biblioteca estándar se descartan.
    """
    starts = [i for i, line in enumerate(block) if line == _TRACEBACK]
    if not starts:
        return []
    # La clave más larga primero: si dos claves casan con la misma ruta, gana la más específica.
    keys = sorted(set(files), key=lambda k: (-len(k), k))
    chain = []
    for line in block[starts[-1] + 1 :]:
        frame = _FRAME.match(line)
        if frame is None:
            continue
        path = frame.group(1).replace("\\", "/")
        component = next((k for k in keys if path.endswith("/" + k)), None)
        if component is not None:
            chain.append(component)
    return chain


def trace_weights(stderr, files):
    """``T(k)``: por componente, el máximo sobre los bloques de ``1 / (1 + d)``, con ``d`` la distancia de
    su aparición más interna al marco de aplicación más cercano a la excepción."""
    weights = {}
    for block in failure_blocks(stderr):
        chain = application_frames(block, files)
        innermost = {component: len(chain) - i for i, component in enumerate(chain, 1)}
        for component, distance in innermost.items():
            weights[component] = max(weights.get(component, 0.0), 1 / (1 + distance))
    return weights


def trace_components(stderr, files):
    """Los componentes extraídos con su peso, en orden canónico (por ruta): lo que registra el recibo."""
    return [{"component": k, "weight": w} for k, w in sorted(trace_weights(stderr, files).items())]


def component_seeds(stderr, files, nodes):
    """La función de siembra: ``stderr`` de ``test-0``, claves de archivo y nodos de la memoria.

    Devuelve los nodos ``Component`` sembrados con su puntuación (el máximo de ``T(k)`` sobre las rutas de
    su etiqueta, mayor que 0), en el orden de la memoria. Ningún otro tipo de nodo se siembra.
    """
    weights = trace_weights(stderr, files)
    seeds = []
    for node in nodes:
        if node["type"] != SEED_NODE_TYPE:
            continue
        score = max((weights.get(path, 0.0) for path in node["label"].split()), default=0.0)
        if score > 0:
            seeds.append({"node": node["id"], "score": score})
    return seeds


def spread(document, seeds):
    """Proyección, propagación, corte y top-1 de ``EvidenceMemory.retrieve``, desde unas semillas dadas.

    ``document`` es la instantánea de la memoria (``nodes``, ``edges``, ``lessons``); ``seeds``, nodo →
    puntuación. Un test comprueba que, con las semillas léxicas de H4, devuelve lo mismo que ``retrieve``.
    """
    projection = MemoryGraph(decay_rate=0)
    for node in document["nodes"]:
        projection.add_node("concept:" + node["id"], NodeType.CONCEPT, node["label"])
    for edge in document["edges"]:
        projection.add_edge(
            "concept:" + edge["source"],
            "concept:" + edge["target"],
            EdgeType.ASSOCIATED_WITH,
            weight=EDGE_WEIGHT,
        )
    config = RetrievalConfig(max_hops=MAX_HOPS, firing_threshold=FIRING_THRESHOLD)
    trace = Retriever(projection, config=config).spread_trace(
        {"concept:" + node: score for node, score in seeds.items()}
    )
    ranked = sorted(
        document["lessons"],
        key=lambda m: (-trace.activation.get("concept:" + m["id"], 0), m["task"], m["strategy"]),
    )
    ranked = [m for m in ranked if trace.activation.get("concept:" + m["id"], 0) >= ACTIVATION_CUT][:1]
    paths = [
        {
            "memory": m["id"],
            "activation": trace.activation["concept:" + m["id"]],
            "path": [s.removeprefix("concept:") for s in trace.path_to("concept:" + m["id"])],
            "evidence": m["evidence"],
        }
        for m in ranked
    ]
    return [dict(m) for m in ranked], paths


def seeded_retrieval(document, stderr, files):
    """Recuperación de C_S: (lecciones expuestas, caminos, bloque de siembra del recibo).

    ``seeded``: un solo nodo ``Component`` tiene la puntuación máxima y su lección supera el corte. ``tie``:
    dos o más comparten la puntuación máxima; no se expone ninguna lección. ``empty``: ningún nodo sembrado
    (también con memoria vacía) o la lección no supera el corte. Sin lección expuesta no hay respaldo léxico.
    """
    seeds = component_seeds(stderr, files, document["nodes"])
    block = {
        "policy": POLICY,
        "components": trace_components(stderr, files),
        "seeds": seeds,
        "state": EMPTY,
        "lesson": None,
    }
    if not seeds:
        return [], [], block
    top = max(seed["score"] for seed in seeds)
    leaders = [seed["node"] for seed in seeds if seed["score"] == top]
    if len(leaders) > 1:
        return [], [], {**block, "state": TIE}
    memories, paths = spread(document, {seed["node"]: seed["score"] for seed in seeds})
    if not memories:
        return [], [], block
    if paths[0]["path"][0] != leaders[0]:
        # Solo puede ocurrir si los subgrafos de las lecciones no son disjuntos: fuera del diseño.
        raise ValueError("la lección expuesta no procede del componente de mayor puntuación")
    return memories, paths, {**block, "state": SEEDED, "lesson": memories[0]["id"]}
