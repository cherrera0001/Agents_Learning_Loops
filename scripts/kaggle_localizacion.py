"""Localización del sitio de una edición por activación propagada sobre el grafo de código (#221).

Para cada tarea pública con grafo disponible:

1. toma como **semillas** los símbolos que nombra el enunciado (``simbolos_del_enunciado``) y los
   resuelve a nodos del grafo de código por sufijo de nombre con puntos (``semillas``);
2. **propaga** activación con el mecanismo del repositorio, sin cambiarlo:
   ``associative_agent_loop.memory.associative.Retriever.spread`` con ``RetrievalConfig()`` por defecto;
3. ordena los nodos por activación y mide si el **sitio de la edición de referencia** queda entre los
   1, 5, 10 y 20 primeros, frente a las líneas base: azar, solo palabras del enunciado, solo semillas,
   y solo vecinos a uno y a dos saltos sin propagación.

Adaptador (lo único que se añade al mecanismo): ``grafo_de_memoria`` convierte el grafo de código
(nodos ``id``/``text``, aristas ``calls``) en un ``MemoryGraph`` con nodos ``Concept`` y aristas
``ASSOCIATED_WITH`` de peso 1. La siembra no usa ``Retriever.seed`` porque el issue pide sembrar con
los símbolos del enunciado; ``--siembra-hibrida`` añade una fila con ``Retriever.seed`` tal cual.

Frontera de fuga: el parche de referencia (``patch``) se lee en una sola función,
``sitios_de_referencia``, y solo para medir. Ninguna clasificación lo recibe: todas se calculan con
el enunciado y el grafo, que es lo que ve el agente evaluado.

Empates: una clasificación deja muchos nodos empatados (todos los no activados, todos los vecinos del
mismo anillo). En vez de romper el empate con un orden arbitrario, ``prob_acierto`` calcula la
probabilidad exacta de que el sitio caiga entre los ``k`` primeros con los empates en orden aleatorio.
El azar es el caso en que todos empatan. Por eso las celdas son porcentajes esperados, no conteos.

Datos: tareas, grafos y embeddings se leen de una carpeta ignorada por git. La salida por defecto es
solo agregada (por repositorio y total); ``--detalle`` escribe una fila por tarea y solo debe apuntar
a una carpeta ignorada.

Uso::

    python -m scripts.kaggle_localizacion --tareas DATA/tasks.jsonl --grafos DATA/graphs
"""

from __future__ import annotations

import argparse
import importlib
import json
import math
import re
import sys
import types
import zipfile
from collections import Counter, defaultdict, deque
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from associative_agent_loop.memory.associative import RetrievalConfig, Retriever
from associative_agent_loop.memory.graph import EdgeType, MemoryGraph, NodeType
from associative_agent_loop.memory.text import STOPWORDS, tokenize

CORTES = (1, 5, 10, 20)
PREFIJO = "concept:code:"  # los identificadores de ``MemoryGraph`` llevan el tipo de nodo delante

AZAR = "azar"
PALABRAS = "palabras del enunciado"
SEMILLAS = "solo semillas (0 saltos)"
VECINOS_1 = "vecinos a 1 salto"
VECINOS_2 = "vecinos a 2 saltos"
ACTIVACION = "activación propagada"
HIBRIDA = "activación con siembra híbrida"
ARNES_VECINOS = "arnés: get_code_neighbors(símbolo)"
ARNES_SIMILAR = "arnés: search_similar_code(símbolo)"
ARNES_PALABRAS = "arnés: search_similar_code(palabras que nombran un nodo)"
ARNES_ENUNCIADO = "arnés: search_similar_code(enunciado entero)"


# --------------------------------------------------------------------------- grafo de código
@dataclass
class GrafoCodigo:
    """Grafo de código de una tarea: texto por nodo y aristas dirigidas (quien llama, llamado)."""

    textos: dict[str, str]
    aristas: list[tuple[str, str]]
    _sufijos: dict[str, list[str]] = field(default_factory=dict, repr=False)
    _prefijos: set[str] = field(default_factory=set, repr=False)
    _ultimos: dict[str, list[str]] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        for nodo in self.textos:
            partes = nodo.split(".")
            for i in range(len(partes)):
                self._sufijos.setdefault(".".join(partes[i:]), []).append(nodo)
            for i in range(1, len(partes)):
                self._prefijos.add(".".join(partes[:i]))
            self._ultimos.setdefault(partes[-1].lower().lstrip("_"), []).append(nodo)

    def por_sufijo(self, simbolo: str) -> list[str]:
        """Nodos cuyo nombre es ``simbolo`` o termina en ``.simbolo``."""
        return self._sufijos.get(simbolo, [])

    def por_ultimo(self, nombre: str) -> list[str]:
        """Nodos cuyo último componente es ``nombre``, sin mayúsculas ni guiones bajos iniciales."""
        return self._ultimos.get(nombre.lower().lstrip("_"), [])

    def es_prefijo(self, modulo: str) -> bool:
        return modulo in self._prefijos

    def vecinos(self) -> dict[str, set[str]]:
        """Adyacencia no dirigida, sin lazos."""
        ady: dict[str, set[str]] = defaultdict(set)
        for a, b in self.aristas:
            if a != b:
                ady[a].add(b)
                ady[b].add(a)
        return ady


def leer_grafo(ruta: Path) -> GrafoCodigo:
    """Lee un grafo en el formato ``node_link_data`` de NetworkX (``edges`` o ``links``)."""
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    textos = {str(n["id"]): str(n.get("text") or "") for n in datos["nodes"]}
    crudas = datos.get("edges", datos.get("links", []))
    aristas = [
        (str(e["source"]), str(e["target"]))
        for e in crudas
        if str(e["source"]) in textos and str(e["target"]) in textos
    ]
    return GrafoCodigo(textos, aristas)


def grafo_de_memoria(grafo: GrafoCodigo) -> MemoryGraph:
    """Adaptador mínimo: grafo de código → ``MemoryGraph`` que ``Retriever`` sabe propagar.

    Cada nodo de código es un ``Concept`` cuya etiqueta es su nombre; cada llamada es una arista
    ``ASSOCIATED_WITH`` de peso 1 (se recorre igual en los dos sentidos: quien llama y a quién llama).
    """
    mg = MemoryGraph(decay_rate=0.0)
    for nodo in grafo.textos:
        mg.add_node(PREFIJO + nodo, NodeType.CONCEPT, nodo)
    for a, b in grafo.aristas:
        if a != b:
            mg.add_edge(PREFIJO + a, PREFIJO + b, EdgeType.ASSOCIATED_WITH, weight=1.0)
    return mg


def _sin_prefijo(activacion: Mapping[str, float]) -> dict[str, float]:
    return {n[len(PREFIJO) :]: a for n, a in activacion.items() if n.startswith(PREFIJO)}


# --------------------------------------------------------------------------- semillas
_CON_PUNTOS = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+")
_CAMEL = re.compile(r"\b(?:[A-Z][a-z0-9]+[A-Z]\w*|[A-Z]{2,}[a-z]\w*)\b")
_SNAKE = re.compile(r"\b[A-Za-z0-9]*_[A-Za-z0-9_]+\b")
_LLAMADA = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\(")
_COMILLAS = re.compile(r"`([^`\n]+)`")
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def simbolos_del_enunciado(texto: str, estrictos: bool = False) -> list[str]:
    """Candidatos a símbolo que el texto nombra, sin repetir y en orden de aparición.

    Por defecto es candidato todo nombre con puntos (``a.b.c``) y todo identificador de tres letras o
    más que no sea una palabra vacía; ``semillas`` se queda con los que nombran un nodo del grafo.
    Con ``estrictos`` solo cuenta lo que está escrito como código: un nombre con puntos, en CamelCase,
    con guion bajo, seguido de ``(`` o dentro de comillas invertidas.
    """
    hallados: list[tuple[int, int, str]] = [
        (m.start(), -len(m.group(0)), m.group(0)) for m in _CON_PUNTOS.finditer(texto)
    ]
    if estrictos:
        for patron in (_CAMEL, _SNAKE):
            hallados += [(m.start(), -len(m.group(0)), m.group(0)) for m in patron.finditer(texto)]
        hallados += [(m.start(1), -len(m.group(1)), m.group(1)) for m in _LLAMADA.finditer(texto)]
        for m in _COMILLAS.finditer(texto):
            hallados += [
                (m.start(1) + i.start(), -len(i.group(0)), i.group(0)) for i in _IDENT.finditer(m.group(1))
            ]
    else:
        hallados += [(m.start(), -len(m.group(0)), m.group(0)) for m in _IDENT.finditer(texto)]
    vistos: dict[str, None] = {}
    for _, _, simbolo in sorted(hallados):
        limpio = simbolo.strip("._")
        if len(limpio) >= 3 and not limpio.isdigit() and limpio.lower() not in STOPWORDS:
            vistos.setdefault(limpio, None)
    return list(vistos)


def resolver(simbolo: str, grafo: GrafoCodigo) -> list[str]:
    """Nodos que nombra un símbolo.

    Primero el sufijo con puntos más largo que coincide con algún nodo (``b.c`` nombra ``a.b.c``); si
    ninguno coincide, los nodos cuyo último componente es el símbolo sin distinguir mayúsculas ni
    guiones bajos iniciales (``encode_files`` nombra ``_encode_files``).
    """
    partes = simbolo.split(".")
    for i in range(len(partes)):
        nodos = grafo.por_sufijo(".".join(partes[i:]))
        if nodos:
            return nodos
    return grafo.por_ultimo(partes[-1])


def semillas(simbolos: Iterable[str], grafo: GrafoCodigo) -> dict[str, float]:
    """Activación inicial: cada símbolo reparte 1 entre los nodos que nombra (tope 1 por nodo).

    Un símbolo que nombra un solo nodo lo siembra con 1; uno que nombra cincuenta, con 0,02 cada uno.
    """
    pesos: dict[str, float] = defaultdict(float)
    ya: set[frozenset[str]] = set()
    for simbolo in simbolos:
        nodos = resolver(simbolo, grafo)
        if not nodos or frozenset(nodos) in ya:  # dos escrituras del mismo símbolo cuentan una vez
            continue
        ya.add(frozenset(nodos))
        for nodo in nodos:
            pesos[nodo] += 1.0 / len(nodos)
    return {n: min(1.0, p) for n, p in pesos.items()}


# --------------------------------------------------------------------------- clasificaciones
def puntajes_palabras(enunciado: str, grafo: GrafoCodigo) -> dict[str, float]:
    """Coseno entre bolsas de palabras del enunciado y de cada nodo (nombre y texto).

    Es la similitud léxica del repositorio (``memory.text.cosine_similarity``) con el enunciado
    tokenizado una sola vez.
    """
    consulta = Counter(tokenize(enunciado))
    norma_c = math.sqrt(sum(v * v for v in consulta.values()))
    puntajes: dict[str, float] = {}
    if not consulta:
        return puntajes
    for nodo, texto in grafo.textos.items():
        bolsa = Counter(tokenize(f"{nodo} {texto}"))
        punto = sum(consulta[t] * c for t, c in bolsa.items() if t in consulta)
        if punto:
            puntajes[nodo] = punto / (norma_c * math.sqrt(sum(v * v for v in bolsa.values())))
    return puntajes


def distancias(origenes: Iterable[str], ady: Mapping[str, set[str]], tope: int) -> dict[str, int]:
    """Saltos (sin dirección) desde el origen más cercano, hasta ``tope``."""
    dist = dict.fromkeys(origenes, 0)
    cola = deque(dist)
    while cola:
        nodo = cola.popleft()
        if dist[nodo] >= tope:
            continue
        for otro in ady.get(nodo, ()):
            if otro not in dist:
                dist[otro] = dist[nodo] + 1
                cola.append(otro)
    return dist


def puntajes_vecinos(sem: Mapping[str, float], dist: Mapping[str, int], saltos: int) -> dict[str, float]:
    """Semillas primero (por su peso), después cada anillo de vecinos, empatado, hasta ``saltos``."""
    puntajes = {n: float(saltos) + 1.0 + p for n, p in sem.items()}
    for nodo, d in dist.items():
        if 0 < d <= saltos:
            puntajes[nodo] = float(saltos - d + 1)
    return puntajes


def puntajes_activacion(
    sem: Mapping[str, float], mg: MemoryGraph, config: RetrievalConfig
) -> dict[str, float]:
    """Activación propagada del repositorio desde las semillas dadas."""
    return _sin_prefijo(Retriever(mg, config=config).spread({PREFIJO + n: p for n, p in sem.items()}))


def prob_acierto(puntajes: Mapping[str, float], oro: set[str], total: int, k: int) -> float:
    """Probabilidad de que algún nodo de ``oro`` quede entre los ``k`` primeros.

    Los nodos se ordenan por puntaje descendente; los que faltan en ``puntajes`` valen 0 y los
    empates se ordenan al azar. Si ``m`` nodos superan al mejor nodo de oro y este empata dentro de un
    grupo de ``t`` nodos, de los cuales ``g`` son de oro, quedan ``r = k − m`` plazas para el grupo y
    la probabilidad es ``1 − C(t − g, r) / C(t, r)``.
    """
    if not oro or total <= 0 or k <= 0:
        return 0.0
    mejor = max(puntajes.get(n, 0.0) for n in oro)
    encima = sum(1 for p in puntajes.values() if p > mejor)
    if mejor > 0.0:
        grupo = sum(1 for p in puntajes.values() if p == mejor)
    else:
        grupo = total - sum(1 for p in puntajes.values() if p > 0.0)
    en_oro = sum(1 for n in oro if puntajes.get(n, 0.0) == mejor)
    plazas = min(k - encima, grupo)
    if plazas <= 0:
        return 0.0
    return 1.0 - math.comb(grupo - en_oro, plazas) / math.comb(grupo, plazas)


# --------------------------------------------------------------------------- sitio de referencia
_CABECERA = re.compile(r"^@@ -\d+(?:,(\d+))? \+\d+(?:,(\d+))? @@ ?(.*)$")
_DEFINICION = re.compile(r"^(\s*)(?:async\s+def|def|class)\s+([A-Za-z_][A-Za-z0-9_]*)")


def _sangria(linea: str) -> int:
    return len(linea) - len(linea.lstrip())


def modulo_de(ruta: str, grafo: GrafoCodigo) -> str | None:
    """Módulo del grafo que corresponde a un archivo ``.py``: admite quitar hasta dos carpetas."""
    if not ruta.endswith(".py"):
        return None
    partes = ruta[:-3].split("/")
    if partes[-1] == "__init__":
        partes = partes[:-1]
    for i in range(min(3, len(partes))):
        modulo = ".".join(partes[i:])
        if grafo.es_prefijo(modulo):
            return modulo
    return None


def _trozos(parche: str) -> Iterator[tuple[str, str, list[tuple[str, str]]]]:
    """Por cada trozo del parche: ruta del archivo, texto de su cabecera ``@@`` y líneas (marca, cuerpo)."""
    ruta = ""
    cabecera = ""
    lineas: list[tuple[str, str]] = []
    faltan = {"-": 0, "+": 0}  # líneas que le quedan al trozo abierto, según su cabecera
    for linea in parche.splitlines():
        if faltan["-"] > 0 or faltan["+"] > 0:
            marca = linea[:1] if linea[:1] in ("-", "+") else " "
            if linea[:1] != "\\":  # «\ No newline at end of file» no es una línea del archivo
                lineas.append((marca, linea[1:]))
                for lado in ("-", "+"):
                    faltan[lado] -= marca in (" ", lado)
            if faltan["-"] <= 0 and faltan["+"] <= 0:
                yield ruta, cabecera, lineas
            continue
        m = _CABECERA.match(linea)
        if m:
            cabecera, lineas = m.group(3), []
            faltan = {"-": int(m.group(1) or 1), "+": int(m.group(2) or 1)}
        elif linea.startswith("+++ "):
            ruta = linea[4:].split("\t")[0].strip()
            ruta = ruta[2:] if ruta.startswith("b/") else ruta
    if faltan["-"] > 0 or faltan["+"] > 0:  # parche cortado: el último trozo cuenta con lo que trae
        yield ruta, cabecera, lineas


def _visibles(previas: Sequence[str], desde: int, tope: int) -> list[str]:
    """Definiciones del trozo que encierran una línea, de dentro a fuera, según la sangría."""
    nombres: list[str] = []
    for i in range(desde, -1, -1):
        m = _DEFINICION.match(previas[i])
        if m and len(m.group(1)) < tope:
            nombres.append(m.group(2))
            tope = len(m.group(1))
    return nombres


def _por_texto(candidatos: Sequence[str], ventana: Sequence[str], grafo: GrafoCodigo) -> list[str]:
    """Candidatos cuyo texto contiene más líneas de la ventana del cambio (ninguno si no contiene ninguna)."""
    cuenta = {n: sum(1 for linea in ventana if linea in grafo.textos[n]) for n in candidatos}
    maximo = max(cuenta.values(), default=0)
    return [n for n, c in cuenta.items() if c == maximo] if maximo else []


def _nodos_del_cambio(
    modulo: str,
    visibles: Sequence[str],
    contenedor: str | None,
    ventana: Sequence[str],
    definicion_nueva: bool,
    grafo: GrafoCodigo,
) -> set[str]:
    """Nodos de un módulo que corresponden a un cambio.

    ``visibles`` son las definiciones que el trozo deja ver alrededor del cambio (la primera es la que
    lo encierra); ``contenedor`` es la definición de la cabecera ``@@``, que encierra el trozo pero puede
    ser la clase y no el método: entonces el método se busca por el texto de la ventana.
    """
    del_modulo = [n for n in grafo.textos if n.startswith(modulo + ".")]
    if visibles:
        candidatos = [n for n in del_modulo if n.rsplit(".", 1)[-1] == visibles[0]]
        for exterior in [*visibles[1:], *([contenedor] if contenedor else [])]:
            dentro = [n for n in candidatos if exterior in n.split(".")[:-1]]
            candidatos = dentro or candidatos
        if len(candidatos) > 1:
            candidatos = _por_texto(candidatos, ventana, grafo) or candidatos
        return set(candidatos)
    if contenedor:
        miembros = [n for n in del_modulo if contenedor in n.split(".")]
        propios = [n for n in miembros if n.rsplit(".", 1)[-1] == contenedor]
        return set(propios if definicion_nueva else (_por_texto(miembros, ventana, grafo) or propios))
    return set()


def sitios_de_referencia(parche: str, grafo: GrafoCodigo) -> set[str]:
    """Nodos del grafo que la edición de referencia toca. **Solo para medir.**

    Por cada línea quitada, y por cada tanda de líneas añadidas, se busca la definición (``def`` o
    ``class``) que la encierra: por la sangría dentro del trozo del parche y, si el trozo no la deja
    ver, entre los miembros de la definición de su cabecera ``@@`` cuyo texto contiene las líneas
    vecinas al cambio. Un cambio a nivel de módulo, o en un archivo que el grafo no tiene, no da sitio.
    """
    sitios: set[str] = set()
    for ruta, cabecera, lineas in _trozos(parche):
        modulo = modulo_de(ruta, grafo)
        if modulo is None:
            continue
        en_cabecera = _DEFINICION.match(cabecera)
        previas = [cuerpo for marca, cuerpo in lineas if marca != "+"]
        vistas = 0  # líneas del archivo original ya recorridas
        tanda_abierta = False
        for marca, cuerpo in lineas:
            if marca != "+":
                vistas += 1
            cambia = cuerpo.strip() and (marca == "-" or (marca == "+" and not tanda_abierta))
            tanda_abierta = marca == "+" and (tanda_abierta or bool(cuerpo.strip()))
            if not cambia:
                continue
            propia = _DEFINICION.match(cuerpo)
            tope = _sangria(cuerpo) + (1 if marca == "-" and propia else 0)
            ventana = [p.strip() for p in previas[max(0, vistas - 4) : vistas + 3] if p.strip()]
            sitios |= _nodos_del_cambio(
                modulo,
                _visibles(previas, vistas - 1, tope),
                en_cabecera.group(2) if en_cabecera and tope > 0 else None,
                ventana,
                marca == "+" and bool(propia or cuerpo.lstrip().startswith("@")),
                grafo,
            )
    return sitios


# --------------------------------------------------------------------------- medida por tarea
@dataclass
class Medida:
    """Resultado de una tarea: sin identificador, sin enunciado y sin parche."""

    repo: str
    nodos: int
    sitios: int
    simbolos: int
    semillas: int
    distancia: int | None  # saltos de la semilla más cercana a un sitio; None = sin camino o sin semillas
    aciertos: dict[str, dict[int, float]]


Clasificador = Callable[[str, Sequence[str], GrafoCodigo], dict[str, float]]


def medir_tarea(
    repo: str,
    enunciado: str,
    parche: str,
    grafo: GrafoCodigo,
    config: RetrievalConfig | None = None,
    siembra_hibrida: bool = False,
    extra: Mapping[str, Clasificador] | None = None,
    estrictos: bool = False,
) -> Medida | None:
    """Mide una tarea. Devuelve ``None`` si la edición de referencia no toca ningún nodo del grafo.

    ``parche`` solo se pasa a ``sitios_de_referencia``; las clasificaciones se calculan antes, con el
    enunciado y el grafo.
    """
    config = config or RetrievalConfig()
    simbolos = [s for s in simbolos_del_enunciado(enunciado, estrictos) if resolver(s, grafo)]
    sem = semillas(simbolos, grafo)
    ady = grafo.vecinos()
    dist = distancias(sem, ady, tope=2)
    mg = grafo_de_memoria(grafo)
    clasificaciones: dict[str, dict[str, float]] = {
        AZAR: {},
        PALABRAS: puntajes_palabras(enunciado, grafo),
        SEMILLAS: dict(sem),
        VECINOS_1: puntajes_vecinos(sem, dist, 1),
        VECINOS_2: puntajes_vecinos(sem, dist, 2),
        ACTIVACION: puntajes_activacion(sem, mg, config),
    }
    if siembra_hibrida:
        hibrido = Retriever(mg, config=config)
        clasificaciones[HIBRIDA] = _sin_prefijo(hibrido.spread(hibrido.seed(enunciado)))
    for nombre, clasificador in (extra or {}).items():
        clasificaciones[nombre] = clasificador(enunciado, simbolos, grafo)

    oro = sitios_de_referencia(parche, grafo)
    if not oro:
        return None
    lejos = distancias(sem, ady, tope=len(grafo.textos))
    alcanzados = [lejos[n] for n in oro if n in lejos]
    total = len(grafo.textos)
    return Medida(
        repo=repo,
        nodos=total,
        sitios=len(oro),
        simbolos=len(simbolos),
        semillas=len(sem),
        distancia=min(alcanzados) if alcanzados else None,
        aciertos={m: {k: prob_acierto(p, oro, total, k) for k in CORTES} for m, p in clasificaciones.items()},
    )


# --------------------------------------------------------------------------- herramientas del arnés
def clasificadores_del_arnes(
    paquete: Path, grafos: Path, embeddings: Path, tallo: str
) -> dict[str, Clasificador]:
    """Clasificaciones que el agente evaluado puede pedir con sus herramientas de grafo.

    Importa ``swegemma.graph`` desde la carpeta del paquete del arnés y llama a las mismas funciones
    que sus herramientas ``get_code_neighbors`` y ``search_similar_code``, sobre los mismos archivos.
    """
    if "swegemma" not in sys.modules:
        # Paquete padre vacío: ``swegemma/__init__.py`` importa el arnés entero (ADK, modelo), que el
        # subpaquete de grafo no necesita. Así solo hacen falta numpy, networkx y cachetools.
        raiz = types.ModuleType("swegemma")
        raiz.__path__ = [str(paquete / "swegemma")]
        sys.modules["swegemma"] = raiz
    sg: Any = importlib.import_module("swegemma.graph")
    graph_utils: Any = importlib.import_module("swegemma.graph.graph_utils")

    comun: dict[str, Any] = {"repo_name": tallo, "graph_dir": str(grafos), "embeddings_dir": str(embeddings)}

    def vecinos(_enunciado: str, simbolos: Sequence[str], _grafo: GrafoCodigo) -> dict[str, float]:
        puntajes: dict[str, float] = {}
        completo = sg.get_graph(**comun)
        for simbolo in simbolos:
            resuelto = (
                simbolo if completo.has_node(simbolo) else graph_utils.resolve_node_name(simbolo, completo)
            )
            if resuelto is None:
                continue
            for vecino in sg.get_neighbor(node=simbolo, max_neighbors=50, **comun):
                puntajes.setdefault(str(vecino).split(";", 1)[-1], 1.0)
            puntajes[str(resuelto)] = 2.0
        return puntajes

    def similares(_enunciado: str, simbolos: Sequence[str], _grafo: GrafoCodigo) -> dict[str, float]:
        puntajes: dict[str, float] = {}
        completo = sg.get_graph(**comun)
        for simbolo in simbolos:
            if not completo.has_node(simbolo) and graph_utils.resolve_node_name(simbolo, completo) is None:
                continue
            for hallado in sg.get_similar_nodes(node=simbolo, k=max(CORTES), **comun):
                nombre, similitud = str(hallado["node_name"]), float(hallado.get("similarity", 0.0))
                puntajes[nombre] = max(puntajes.get(nombre, 0.0), similitud)
        return puntajes

    def por_palabras(consulta: str) -> dict[str, float]:
        # Con un espacio la consulta no se resuelve a un nodo y el arnés busca por palabras.
        hallados = sg.get_similar_nodes(node=consulta + " ", k=max(CORTES), **comun)
        return {str(h["node_name"]): float(h.get("similarity", 0.0)) for h in hallados}

    def palabras(_enunciado: str, simbolos: Sequence[str], _grafo: GrafoCodigo) -> dict[str, float]:
        return por_palabras(" ".join(simbolos)) if simbolos else {}

    def entero(enunciado: str, _simbolos: Sequence[str], _grafo: GrafoCodigo) -> dict[str, float]:
        return por_palabras(enunciado)

    return {
        ARNES_VECINOS: vecinos,
        ARNES_SIMILAR: similares,
        ARNES_PALABRAS: palabras,
        ARNES_ENUNCIADO: entero,
    }


# --------------------------------------------------------------------------- agregado
def agregar(medidas: Sequence[Medida]) -> dict[str, Any]:
    """Porcentaje esperado de tareas con el sitio entre los ``k`` primeros, por repositorio y total."""
    grupos: dict[str, list[Medida]] = defaultdict(list)
    for m in medidas:
        grupos[m.repo].append(m)
    filas: dict[str, Any] = {}
    for nombre, grupo in [*sorted(grupos.items()), ("total", list(medidas))]:
        if not grupo:
            continue
        metodos = list(grupo[0].aciertos)
        filas[nombre] = {
            "tareas": len(grupo),
            "sitio_a_2_saltos_o_menos_de_una_semilla": sum(
                1 for m in grupo if m.distancia is not None and m.distancia <= 2
            ),
            "sin_semillas": sum(1 for m in grupo if m.semillas == 0),
            "metodos": {
                metodo: {
                    str(k): round(100.0 * sum(m.aciertos[metodo][k] for m in grupo) / len(grupo), 1)
                    for k in CORTES
                }
                for metodo in metodos
            },
        }
    return filas


def tabla_markdown(agregado: Mapping[str, Any]) -> str:
    """Tabla agregada: una fila por repositorio y método, con el número de tareas de la celda."""
    lineas = [
        "| Repositorio | Tareas | Método | " + " | ".join(f"Entre los {k}" for k in CORTES) + " |",
        "|---|---:|---|" + "---:|" * len(CORTES),
    ]
    for repo, fila in agregado.items():
        for metodo, celdas in fila["metodos"].items():
            valores = " | ".join(f"{celdas[str(k)]:.1f} %".replace(".", ",") for k in CORTES)
            lineas.append(f"| {repo} | {fila['tareas']} | {metodo} | {valores} |")
    return "\n".join(lineas)


def resueltas_por_tarea(carpeta: Path) -> dict[str, bool]:
    """Por tarea, si alguna sesión rescatada la resolvió (lee ``task_results.jsonl`` de cada zip)."""
    alguna: dict[str, bool] = {}
    for ruta in sorted(carpeta.rglob("*.zip")):
        try:
            archivo = zipfile.ZipFile(ruta)
        except zipfile.BadZipFile:
            continue
        with archivo:
            for nombre in archivo.namelist():
                if not nombre.endswith("task_results.jsonl"):
                    continue
                for linea in archivo.read(nombre).decode("utf-8", "replace").splitlines():
                    if linea.strip():
                        fila = json.loads(linea)
                        tarea = str(fila.get("task_id"))
                        alguna[tarea] = alguna.get(tarea, False) or bool(fila.get("resolved"))
    return alguna


def cruce_con_resultados(
    medidas: Mapping[str, Medida], resueltas: Mapping[str, bool], k: int = 5
) -> dict[str, Any]:
    """Conteos (sin identificadores) del sitio entre los ``k`` primeros según si la tarea se resolvió."""
    salida: dict[str, Any] = {
        "tareas_con_resultado": len(resueltas),
        "de_ellas_sin_medir": sum(1 for t in resueltas if t not in medidas),
    }
    for etiqueta, quiere in (("nunca_resueltas", False), ("resueltas_alguna_vez", True)):
        grupo = [m for t, m in medidas.items() if t in resueltas and resueltas[t] is quiere]
        metodos = list(grupo[0].aciertos) if grupo else []
        salida[etiqueta] = {
            "tareas_medidas": len(grupo),
            "metodos": {
                metodo: {
                    "esperadas": round(sum(m.aciertos[metodo][k] for m in grupo), 1),
                    "seguras": sum(1 for m in grupo if m.aciertos[metodo][k] >= 0.999),
                }
                for metodo in metodos
            },
        }
    return salida


def _mediana(valores: Sequence[int]) -> float:
    orden = sorted(valores)
    if not orden:
        return 0.0
    mitad = len(orden) // 2
    return float(orden[mitad]) if len(orden) % 2 else (orden[mitad - 1] + orden[mitad]) / 2


# --------------------------------------------------------------------------- orden de línea
def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tareas", type=Path, required=True, help="tasks.jsonl (carpeta ignorada por git)")
    ap.add_argument("--grafos", type=Path, required=True, help="carpeta con <repo>_<commit>.json")
    ap.add_argument("--siembra-hibrida", action="store_true", help="añadir Retriever.seed tal cual")
    ap.add_argument("--simbolos-estrictos", action="store_true", help="solo símbolos escritos como código")
    ap.add_argument("--arnes", type=Path, help="carpeta que contiene el paquete swegemma del arnés")
    ap.add_argument("--embeddings", type=Path, help="carpeta con <repo>_<commit>.npz (para --arnes)")
    ap.add_argument("--resultados", type=Path, help="carpeta con zips de sesiones (task_results.jsonl)")
    ap.add_argument("--salida", type=Path, help="JSON agregado (sin identificadores de tarea)")
    ap.add_argument("--detalle", type=Path, help="JSONL por tarea: SOLO en una carpeta ignorada por git")
    args = ap.parse_args(argv)
    if args.arnes and not args.embeddings:
        ap.error("--arnes necesita --embeddings")

    tareas = [json.loads(x) for x in args.tareas.read_text(encoding="utf-8").splitlines() if x.strip()]
    medidas: dict[str, Medida] = {}
    sin_grafo = sin_sitio = 0
    for tarea in tareas:
        tallo = f"{str(tarea['repo']).rsplit('/', 1)[-1]}_{tarea['base_commit']}"
        ruta = args.grafos / f"{tallo}.json"
        if not ruta.exists():
            sin_grafo += 1
            continue
        enunciado = str(tarea["problem_statement"])  # ``hints_text`` viene vacío en las 129 públicas
        extra = (
            clasificadores_del_arnes(args.arnes, args.grafos, args.embeddings, tallo) if args.arnes else None
        )
        medida = medir_tarea(
            str(tarea["repo"]),
            enunciado,
            str(tarea["patch"]),
            leer_grafo(ruta),
            siembra_hibrida=args.siembra_hibrida,
            extra=extra,
            estrictos=args.simbolos_estrictos,
        )
        if medida is None:
            sin_sitio += 1
            continue
        medidas[str(tarea["instance_id"])] = medida

    informe: dict[str, Any] = {
        "tareas_leidas": len(tareas),
        "sin_grafo": sin_grafo,
        "sin_sitio_en_el_grafo": sin_sitio,
        "tareas_medidas": len(medidas),
        "simbolos": "escritos como código"
        if args.simbolos_estrictos
        else "todo identificador que nombra un nodo",
        "mediana_de_simbolos_que_nombran_un_nodo": _mediana([m.simbolos for m in medidas.values()]),
        "mediana_de_sitios_por_tarea": _mediana([m.sitios for m in medidas.values()]),
        "mediana_de_nodos_del_grafo": _mediana([m.nodos for m in medidas.values()]),
        "config": RetrievalConfig().model_dump(
            include={"damping", "firing_threshold", "max_hops", "fan_out"}
        ),
        "agregado": agregar(list(medidas.values())),
    }
    if args.resultados:
        informe["cruce_entre_los_5"] = cruce_con_resultados(medidas, resueltas_por_tarea(args.resultados))
    print(tabla_markdown(informe["agregado"]))
    print(json.dumps({k: v for k, v in informe.items() if k != "agregado"}, ensure_ascii=False, indent=2))
    for repo, fila in informe["agregado"].items():
        print(
            f"{repo}: {fila['tareas']} tareas; sitio a 2 saltos o menos de una semilla en "
            f"{fila['sitio_a_2_saltos_o_menos_de_una_semilla']}; sin semillas {fila['sin_semillas']}"
        )
    if args.salida:
        args.salida.write_text(json.dumps(informe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.detalle:
        with args.detalle.open("w", encoding="utf-8") as f:
            for tarea_id, m in medidas.items():
                f.write(json.dumps({"id": tarea_id, **m.__dict__}, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
