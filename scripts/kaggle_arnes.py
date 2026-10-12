"""Versiones del arnés de Kaggle con las que se ensayó, y lo que se comprueba contra ellas (#195).

El 2026-10-12 una corrida real falló a los 106 s: el conjunto público de ruedas había cambiado tres días
antes (``swegemma`` 0.2.7 -> 0.2.11, ``adk_submission`` 0.2.12 -> 0.2.13) y una celda importaba un módulo
que la versión nueva eliminó. Nada lo comparaba. Este módulo reúne, sin red y sin ejecutar código ajeno:

- ``ARNES_ENSAYADO``: las versiones con las que se hizo el último ensayo local con las ruedas reales;
- el texto que el armado pone en el notebook: la guarda de versiones de la celda de instalación y el
  sustituto de ``validate_single_declared_model`` (eliminado en ``swegemma`` 0.2.11);
- la lectura de un listado del conjunto de ruedas (el que imprime ``kaggle datasets files`` o el JSON que
  guarda el rescate) y su comparación con las versiones ensayadas y con otro listado;
- la comprobación estática de los imports de un notebook contra las ruedas (``.whl``) o sus fuentes
  extraídas: se leen como texto con ``ast``, no se importan ni se instalan.

Lo que **no** ve ninguna de estas guardas: un cambio de conducta del arnés que conserva nombres y firmas
(en 0.2.13, ``thinking_budget`` pasa a decidir si el modelo razona). Eso exige leer el diff de fuentes en
cada cambio de versión.

Desde el concilio 46 (#182) guarda además el SHA-256 esperado de cada rueda del arnés
(``RUEDAS_ESPERADAS_SHA256``): el 2026-10-12 el conjunto se volvió a publicar con las mismas versiones y otro
contenido, y comparar cadenas de versión no lo vio. La guarda del notebook puede compararlo antes de cargar
el modelo (``celda_de_versiones(..., sha256=...)``), el chequeo previo lo compara contra la carpeta de ruedas
y ``cambios_desde_la_sesion`` dice qué cambió respecto de las ruedas con que corrió una sesión. El SHA-256
dice que el archivo es otro; no dice qué cambió dentro.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import zipfile
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Versiones con las que se ensayó (ensayo local con las ruedas reales, 2026-10-12). Cambiarlas exige
# repetir ese ensayo: no son «las que hay hoy en Kaggle», son las que se probaron.
ARNES_ENSAYADO: dict[str, str] = {
    "swegemma": "0.2.11",
    "adk_submission": "0.2.13",
    "adk_eval_core": "0.1.0",
    "google_adk": "1.36.1",
}
# SHA-256 esperado de cada rueda del arnés (concilio 46, #182): las publicadas en el conjunto el 2026-10-12
# a las 19:51 UTC. La versión no basta: ese día ``swegemma-0.2.11`` cambió de contenido sin cambiar de
# versión, y la guarda de versiones no lo vio. Son las que el notebook exige antes de cargar el modelo, no
# «las que hay hoy en Kaggle»: cambiarlas exige leer el diff de fuentes y repetir el ensayo con las ruedas
# reales. Ese ensayo (en Docker) NO se había corrido con estas ruedas al escribir esto: ver el PR del #182.
RUEDAS_ESPERADAS_SHA256: dict[str, str] = {
    f"{dist}-py3-none-any.whl": huella
    for dist, huella in (
        ("adk_eval_core-0.1.0", "e614e1b2fe8d886a634871e4c57f9887e1cc66e8c27300f8503a43c6e3ca82f3"),
        ("adk_submission-0.2.13", "f156f0bd84580ccb9334726d114d7a5481f16d3a6e2887cc4d276ced0ef8d99d"),
        ("google_adk-1.36.1", "1a2f6868c509e3151fb0de3575a7d18b45c338be86f420924dad74e7193631a0"),
        ("swegemma-0.2.11", "9ad876581f3acde8ec3c369858f0834e2b9f41a3cffce3ca42f09cb090aea9d3"),
    )
}
# Paquete de Python que instala cada rueda del arnés (para la comprobación de imports).
PAQUETES_DEL_ARNES: dict[str, str] = {
    "swegemma": "swegemma",
    "adk_submission": "adk_submission",
    "adk_eval_core": "adk_eval_core",
    "google_adk": "google.adk",
}
RUEDA = re.compile(r"^(?P<dist>[A-Za-z0-9_.]+?)-(?P<version>[0-9][A-Za-z0-9_.!+]*)-.+\.whl$")
CARPETA_DE_RUEDA = re.compile(
    r"^(?P<dist>[A-Za-z0-9_.]+?)-(?P<version>[0-9][A-Za-z0-9_.!+]*)(-.+|\.dist-info)$"
)

# --- Texto que el armado pone en el notebook -------------------------------------------------------------

MARCA_VERSIONES = "# Versiones del arnes (#195)"
IMPORT_ELIMINADO = "    from swegemma.models.discovery import validate_single_declared_model\n"
IMPORT_SUSTITUTO = "    from adk_submission import discover_declared_models\n"
USO_ELIMINADO = "    declared_model = validate_single_declared_model(AGENT_DIR)\n"
# Lo que hacía ``validate_single_declared_model`` en swegemma 0.2.7: normalizar cada nombre (minúsculas, sin
# prefijo de proveedor) y exigir exactamente un modelo. ``discover_declared_models`` es el mismo en
# adk_submission 0.2.12 y 0.2.13.
USO_SUSTITUTO = (
    "    def _normalizar_modelo(nombre):\n"
    "        valor = nombre.strip().lower()\n"
    "        for prefijo in ('openai/', 'google/', 'hosted_vllm/', 'custom/'):\n"
    "            if valor.startswith(prefijo):\n"
    "                valor = valor[len(prefijo):]\n"
    "        return valor\n"
    "    _declarados = sorted(discover_declared_models(AGENT_DIR, normalize_fn=_normalizar_modelo))\n"
    "    if len(_declarados) != 1:\n"
    "        raise RuntimeError(f'MODELO: la condicion declara {len(_declarados)} modelos {_declarados}; "
    "se exige exactamente uno')\n"
    "    declared_model = _declarados[0]\n"
)


MARCA_SHA256 = "# SHA-256 de las ruedas (#182)"
# Líneas que la guarda por sha256 añade a la de versiones, y detrás de cuál van. Quitarlas devuelve la guarda
# de versiones byte a byte (lo comprueba una prueba): así el armado puede listar la diferencia exacta.
_SHA256_IMPORT = "import hashlib as _hashlib\n"
_SHA256_CUENTA = (
    f"{MARCA_SHA256}: de cada .whl del directorio de ruedas, leída por bloques; las esperadas se comparan.\n"
    "_sha256_visto = {}\n"
    "if _ruedas is not None:\n"
    "    for _archivo in [_a for _a in _ruedas if _a.endswith('.whl')]:\n"
    "        try:\n"
    "            _h = _hashlib.sha256()\n"
    "            with open(_os.path.join(_dir_ruedas, _archivo), 'rb') as _f:\n"
    "                for _bloque in iter(lambda: _f.read(1 << 20), b''):\n"
    "                    _h.update(_bloque)\n"
    "            _sha256_visto[_archivo] = _h.hexdigest()\n"
    "        except OSError as _exc:\n"
    "            _sha256_visto[_archivo] = 'ilegible: ' + type(_exc).__name__\n"
    "_sha256_distintas = {}\n"
    "for _archivo, _esperado in ARNES_SHA256_ESPERADO.items():\n"
    "    if _sha256_visto.get(_archivo) != _esperado:\n"
    "        _sha256_distintas[_archivo] = [_esperado, _sha256_visto.get(_archivo)]\n"
)
_SHA256_RESUMEN = (
    "_resumen_arnes.update({'sha256_esperadas': ARNES_SHA256_ESPERADO, 'sha256': _sha256_visto})\n"
    "_resumen_arnes['sha256_distintas'] = _sha256_distintas\n"
)
_SHA256_AVISO = (
    "print('ARNES sha256:', 'las esperadas' if not _sha256_distintas else 'DISTINTAS', "
    "'|', len(_sha256_visto), 'ruedas con huella')\n"
    "for _archivo, (_esperado, _visto) in _sha256_distintas.items():\n"
    "    print('ARNES sha256 distinto:', _archivo, '| esperado', _esperado, '| visto', _visto)\n"
)
_SHA256_PARADA = (
    "if _sha256_distintas:\n"
    "    raise RuntimeError(f'ARNES: sha256 distinto del esperado (esperado, visto) "
    "{_sha256_distintas}; se detiene antes de cargar el modelo')\n"
)


def celda_de_versiones(
    archivo: str, esperadas: Mapping[str, str] | None = None, sha256: Mapping[str, str] | None = None
) -> str:
    """Texto que se añade a la celda que comprueba la instalación de las ruedas.

    Escribe en ``archivo`` (un archivo de salida de la sesión) las versiones instaladas del arnés, las
    esperadas y el listado del directorio de ruedas con sus bytes, y detiene el notebook, antes de la GPU,
    si alguna versión no es la esperada. Se basta sola: no usa nombres de otras celdas salvo ``W`` (el
    directorio de ruedas), y lo tolera ausente.

    Con ``sha256`` (nombre de archivo ``.whl`` -> SHA-256 esperado; #182) calcula además el SHA-256 de cada
    ``.whl`` del directorio de ruedas, lo deja en el mismo archivo junto a los esperados, y detiene el
    notebook, antes de cargar el modelo, si alguna de las esperadas difiere, falta o no hay directorio: la
    salida y el archivo traen los dos valores. Lo que compara es el archivo del que ``pip`` instaló en la
    celda anterior, no lo que quedó en ``site-packages``. Sin ``sha256`` el texto es el de siempre.
    """
    esperadas = dict(ARNES_ENSAYADO if esperadas is None else esperadas)
    con_sha256 = sha256 is not None
    return (
        f"{MARCA_VERSIONES}: quedan en un archivo de salida; si no son las ensayadas, se detiene.\n"
        + (_SHA256_IMPORT if con_sha256 else "")
        + "import importlib.metadata as _md\n"
        "import json as _json\n"
        "import os as _os\n"
        f"ARNES_ESPERADO = {esperadas!r}\n"
        + (f"ARNES_SHA256_ESPERADO = {dict(sha256 or {})!r}\n" if con_sha256 else "")
        + f"ARCHIVO_VERSIONES = {archivo!r}\n"
        "_arnes_visto = {}\n"
        "for _nombre in ARNES_ESPERADO:\n"
        "    try:\n"
        "        _arnes_visto[_nombre] = _md.version(_nombre)\n"
        "    except _md.PackageNotFoundError:\n"
        "        _arnes_visto[_nombre] = None\n"
        "_arnes_distintas = {}\n"
        "for _nombre, _vista in _arnes_visto.items():\n"
        "    if _vista != ARNES_ESPERADO[_nombre]:\n"
        "        _arnes_distintas[_nombre] = [ARNES_ESPERADO[_nombre], _vista]\n"
        "_dir_ruedas = globals().get('W')\n"
        "_ruedas = None\n"
        "if _dir_ruedas and _os.path.isdir(_dir_ruedas):\n"
        "    _ruedas = {}\n"
        "    for _archivo in sorted(_os.listdir(_dir_ruedas)):\n"
        "        _ruedas[_archivo] = _os.path.getsize(_os.path.join(_dir_ruedas, _archivo))\n"
        + (_SHA256_CUENTA if con_sha256 else "")
        + "_os.makedirs(_os.path.dirname(ARCHIVO_VERSIONES), exist_ok=True)\n"
        "_resumen_arnes = {'esperadas': ARNES_ESPERADO, 'instaladas': _arnes_visto}\n"
        "_resumen_arnes.update({'distintas': _arnes_distintas, 'ruedas': _ruedas})\n"
        + (_SHA256_RESUMEN if con_sha256 else "")
        + "with open(ARCHIVO_VERSIONES, 'w', encoding='utf-8') as _f:\n"
        "    _json.dump(_resumen_arnes, _f, indent=1)\n"
        "print('ARNES versiones:', _arnes_visto, '| archivo', ARCHIVO_VERSIONES)\n"
        + (_SHA256_AVISO if con_sha256 else "")
        + "if _arnes_distintas:\n"
        "    raise RuntimeError(f'ARNES: versiones distintas de las ensayadas (esperada, instalada) "
        "{_arnes_distintas}; se detiene antes de la GPU')\n" + (_SHA256_PARADA if con_sha256 else "")
    )


def lineas_de_la_guarda_por_sha256(sha256: Mapping[str, str]) -> list[str]:
    """Las líneas que ``celda_de_versiones`` añade cuando recibe ``sha256``, en su orden."""
    texto = (
        _SHA256_IMPORT
        + f"ARNES_SHA256_ESPERADO = {dict(sha256)!r}\n"
        + _SHA256_CUENTA
        + _SHA256_RESUMEN
        + _SHA256_AVISO
        + _SHA256_PARADA
    )
    return texto.splitlines(keepends=True)


def sha256_de(ruta: Path) -> str:
    """SHA-256 de un archivo, leído por bloques."""
    huella = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            huella.update(bloque)
    return huella.hexdigest()


def diferencias_de_sha256(carpeta: Path, esperadas: Mapping[str, str]) -> list[str]:
    """Una frase, con los dos valores, por cada rueda esperada que en ``carpeta`` falta o difiere."""
    out = []
    for nombre, esperado in esperadas.items():
        ruta = carpeta / nombre
        if not ruta.is_file():
            out.append(f"{nombre}: se espera sha256 {esperado} y la carpeta no trae esa rueda")
            continue
        visto = sha256_de(ruta)
        if visto != esperado:
            out.append(f"{nombre}: se espera sha256 {esperado} y la de la carpeta tiene {visto}")
    return out


def sustituir_modelo_declarado(celda: str) -> str:
    """La celda del servidor sin ``validate_single_declared_model``. Falla si no casa exactamente una vez."""
    for viejo in (IMPORT_ELIMINADO, USO_ELIMINADO):
        if celda.count(viejo) != 1:
            raise ValueError(f"La celda no trae exactamente una vez: {viejo.strip()}")
    return celda.replace(IMPORT_ELIMINADO, IMPORT_SUSTITUTO).replace(USO_ELIMINADO, USO_SUSTITUTO)


# --- Listado del conjunto de ruedas ----------------------------------------------------------------------


def normalizar_dist(nombre: str) -> str:
    """Nombre de distribución comparable: minúsculas y ``_`` (``google-adk`` es ``google_adk``)."""
    return re.sub(r"[-_.]+", "_", nombre).lower()


def version_de_rueda(archivo: str) -> tuple[str, str] | None:
    """``(distribución, versión)`` de un nombre de archivo ``.whl``; ``None`` si no tiene esa forma."""
    m = RUEDA.match(archivo)
    return (normalizar_dist(m["dist"]), m["version"]) if m else None


def leer_listado(texto: str) -> list[dict[str, Any]]:
    """Entradas ``{nombre, bytes, fecha}`` de un listado del conjunto de ruedas.

    Acepta el JSON que guarda el rescate (una lista de entradas, o un objeto con ``archivos``) y la tabla
    de texto de ``kaggle datasets files`` (columnas ``name``, ``size``, ``creationDate``).
    """
    limpio = texto.lstrip("\ufeff").strip()
    if limpio.startswith(("[", "{")):
        datos = json.loads(limpio)
        crudas = datos.get("archivos", []) if isinstance(datos, dict) else datos
        if not isinstance(crudas, list):
            raise ValueError("El listado JSON no trae una lista de archivos.")
        return [entrada_de(x) for x in crudas if isinstance(x, dict)]
    entradas = []
    for linea in limpio.splitlines():
        partes = re.split(r"\s{2,}", linea.strip())
        if len(partes) < 2 or not partes[1].isdigit():
            continue  # encabezado, raya o línea en blanco
        entradas.append(
            {"nombre": partes[0], "bytes": int(partes[1]), "fecha": partes[2] if len(partes) > 2 else None}
        )
    return entradas


def entrada_de(cruda: Mapping[str, Any]) -> dict[str, Any]:
    """Una entrada del listado, venga con las claves del rescate o con las de la API de Kaggle."""
    tamano = cruda.get("bytes", cruda.get("totalBytes", cruda.get("size")))
    return {
        "nombre": str(cruda.get("nombre", cruda.get("name", ""))),
        "bytes": int(tamano) if isinstance(tamano, int | float) or str(tamano).isdigit() else None,
        "fecha": cruda.get("fecha", cruda.get("creationDate")),
    }


def versiones_de(nombres: Iterable[str]) -> dict[str, list[str]]:
    """Versiones de cada distribución entre unos nombres de archivo (una lista: puede haber dos ruedas)."""
    vistas: dict[str, list[str]] = {}
    for nombre in nombres:
        par = version_de_rueda(Path(nombre).name)
        if par is not None and par[1] not in vistas.setdefault(par[0], []):
            vistas[par[0]].append(par[1])
    return vistas


def diferencias_con_lo_ensayado(
    vistas: Mapping[str, Sequence[str]], esperadas: Mapping[str, str] | None = None
) -> list[str]:
    """Una frase por cada rueda del arnés cuya versión no es, sola, la ensayada. Vacía si coinciden todas."""
    esperadas = ARNES_ENSAYADO if esperadas is None else esperadas
    out = []
    for dist, version in esperadas.items():
        hay = list(vistas.get(normalizar_dist(dist), []))
        if not hay:
            out.append(f"{dist}: se ensayó con {version} y el listado no trae esa rueda")
        elif hay != [version]:
            out.append(f"{dist}: se ensayó con {version} y el listado trae {', '.join(hay)}")
    return out


def cambios_del_listado(antes: Sequence[Mapping[str, Any]], ahora: Sequence[Mapping[str, Any]]) -> list[str]:
    """Qué cambió entre dos listados: archivos que entran, que salen o que cambian de tamaño o de fecha."""
    a = {str(x["nombre"]): x for x in antes}
    b = {str(x["nombre"]): x for x in ahora}
    out = [f"sale {n}" for n in sorted(set(a) - set(b))]
    out += [f"entra {n}" for n in sorted(set(b) - set(a))]
    for nombre in sorted(set(a) & set(b)):
        for campo in ("bytes", "fecha"):
            if a[nombre].get(campo) != b[nombre].get(campo):
                out.append(f"{nombre}: {campo} {a[nombre].get(campo)} -> {b[nombre].get(campo)}")
    return out


FECHA_HORA = re.compile(r"(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})")


def fecha_de(texto: Any) -> datetime | None:
    """La fecha y hora UTC de un texto de Kaggle (``2026-10-12T19:51:41.56Z`` o ``2026-10-09 14:43:26.259``).

    Se queda en el segundo: las fracciones llegan con una, tres o siete cifras según la ruta de la API.
    ``None`` si el texto no tiene esa forma o no es una fecha que exista.
    """
    m = FECHA_HORA.match(str(texto or "").strip())
    if m is None:
        return None
    anio, mes, dia, hora, minuto, segundo = (int(x) for x in m.groups())
    try:
        return datetime(anio, mes, dia, hora, minuto, segundo, tzinfo=UTC)
    except ValueError:
        return None


def cambios_desde_la_sesion(
    ruedas_de_la_sesion: Mapping[str, Any], corrio: datetime | None, ahora: Sequence[Mapping[str, Any]]
) -> list[str]:
    """Qué cambió entre las ruedas con que corrió una sesión y un listado del conjunto (#182).

    ``ruedas_de_la_sesion`` es el ``ruedas`` del archivo de versiones que deja la celda 2 (nombre -> bytes,
    tal como la sesión los vio); ``corrio``, la hora en que arrancó. Una rueda cambió si sale, entra, pesa
    otra cosa o su fecha en el listado es posterior al arranque de la sesión: el 2026-10-12 las 41 ruedas se
    volvieron a publicar a las 19:51 UTC, 39 con el mismo tamaño, y una sesión de las 13:57 quedó atrás sin
    que nada lo dijera. Las fechas posteriores se resumen en una sola frase. Sin ``corrio`` solo compara
    nombres y bytes.
    """
    antes = {str(n): b for n, b in ruedas_de_la_sesion.items() if str(n).endswith(".whl")}
    actual = {str(x["nombre"]): x for x in ahora if str(x.get("nombre", "")).endswith(".whl")}
    out = [f"sale {n}" for n in sorted(set(antes) - set(actual))]
    out += [f"entra {n}" for n in sorted(set(actual) - set(antes))]
    for nombre in sorted(set(antes) & set(actual)):
        if antes[nombre] != actual[nombre].get("bytes"):
            out.append(f"{nombre}: bytes {antes[nombre]} -> {actual[nombre].get('bytes')}")
    if corrio is not None:
        fechas = {n: fecha_de(x.get("fecha")) for n, x in actual.items()}
        despues = sorted(f for f in fechas.values() if f is not None and f > corrio)
        if despues:
            out.append(
                f"{len(despues)} de {len(actual)} ruedas con fecha posterior a la sesión "
                f"(la última, {despues[-1].strftime('%Y-%m-%dT%H:%M:%SZ')})"
            )
    return out


# --- Imports del notebook contra las ruedas, sin ejecutar nada ------------------------------------------


@dataclass
class FuentesDelArnes:
    """Archivos ``.py`` de unas ruedas, por ruta de paquete (``swegemma/models/__init__.py``), como texto."""

    archivos: dict[str, str] = field(default_factory=dict)
    versiones: dict[str, list[str]] = field(default_factory=dict)

    def ruta_de(self, modulo: str) -> str | None:
        base = modulo.replace(".", "/")
        for candidata in (f"{base}/__init__.py", f"{base}.py"):
            if candidata in self.archivos:
                return candidata
        return None

    def tiene_paquete(self, paquete: str) -> bool:
        prefijo = paquete.replace(".", "/") + "/"
        return any(ruta.startswith(prefijo) for ruta in self.archivos)


def leer_fuentes(carpeta: Path) -> FuentesDelArnes:
    """Lee las ruedas ``.whl`` de ``carpeta`` y los paquetes extraídos que haya en ella o un nivel más abajo.

    Una rueda se abre como zip y sus ``.py`` se leen como texto; nada se extrae, se importa ni se ejecuta.
    """
    fuentes = FuentesDelArnes()
    if not carpeta.is_dir():
        return fuentes
    for rueda in sorted(carpeta.glob("*.whl")):
        par = version_de_rueda(rueda.name)
        if par is not None and par[1] not in fuentes.versiones.setdefault(par[0], []):
            fuentes.versiones[par[0]].append(par[1])
        try:
            with zipfile.ZipFile(rueda) as z:
                for info in z.infolist():
                    nombre = info.filename.replace("\\", "/")
                    if nombre.endswith(".py") and ".dist-info/" not in nombre and ".data/" not in nombre:
                        fuentes.archivos[nombre] = z.read(info).decode("utf-8", errors="replace")
        except (zipfile.BadZipFile, OSError):
            continue
    for raiz in [carpeta, *sorted(p for p in carpeta.iterdir() if p.is_dir())]:
        m = CARPETA_DE_RUEDA.match(raiz.name) if raiz != carpeta else None
        if m is not None and m["version"] not in fuentes.versiones.setdefault(normalizar_dist(m["dist"]), []):
            fuentes.versiones[normalizar_dist(m["dist"])].append(m["version"])
        for paquete in sorted(p for p in raiz.iterdir() if p.is_dir()):
            if not any(paquete.glob("**/__init__.py")):
                continue
            for archivo in sorted(paquete.rglob("*.py")):
                relativa = archivo.relative_to(raiz).as_posix()
                if relativa not in fuentes.archivos:
                    fuentes.archivos[relativa] = archivo.read_text(encoding="utf-8", errors="replace")
    return fuentes


def _cuerpo_de_nivel_superior(arbol: ast.Module) -> Iterable[ast.stmt]:
    """Sentencias del módulo, entrando en ``if`` y ``try`` (un nombre definido bajo ``TYPE_CHECKING`` cuenta
    solo si además lo sirve ``__getattr__``; eso se resuelve aparte)."""
    pendientes: list[ast.stmt] = list(arbol.body)
    while pendientes:
        nodo = pendientes.pop(0)
        yield nodo
        if isinstance(nodo, ast.If) and not _es_type_checking(nodo.test):
            pendientes += [*nodo.body, *nodo.orelse]
        elif isinstance(nodo, ast.Try):
            pendientes += [
                *nodo.body,
                *nodo.orelse,
                *nodo.finalbody,
                *(s for h in nodo.handlers for s in h.body),
            ]


def _es_type_checking(prueba: ast.expr) -> bool:
    nombre = prueba.attr if isinstance(prueba, ast.Attribute) else getattr(prueba, "id", "")
    return nombre == "TYPE_CHECKING"


def nombres_de(fuente: str) -> tuple[set[str], set[str]]:
    """``(definidos, perezosos)`` de un módulo: lo que enlaza al importarse y lo que sirve ``__getattr__``.

    Los perezosos son los textos de las colecciones de nivel superior de un módulo que define
    ``__getattr__`` (la forma de ``adk_submission``: ``_SERVING_EXPORTS`` y ``from . import server``).
    """
    arbol = ast.parse(fuente)
    definidos: set[str] = set()
    textos: set[str] = set()
    for nodo in _cuerpo_de_nivel_superior(arbol):
        if isinstance(nodo, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            definidos.add(nodo.name)
        elif isinstance(nodo, ast.Import | ast.ImportFrom):
            definidos.update((a.asname or a.name).split(".")[0] for a in nodo.names)
        elif isinstance(nodo, ast.Assign | ast.AnnAssign):
            destinos = nodo.targets if isinstance(nodo, ast.Assign) else [nodo.target]
            es_all = any(isinstance(t, ast.Name) and t.id == "__all__" for t in destinos)
            definidos.update(t.id for t in destinos if isinstance(t, ast.Name))
            if nodo.value is not None and not es_all:
                textos.update(
                    c.value
                    for c in ast.walk(nodo.value)
                    if isinstance(c, ast.Constant) and isinstance(c.value, str)
                )
    return definidos, (textos if "__getattr__" in definidos else set())


def _es_opcional(pila: Sequence[ast.AST], nodo: ast.AST) -> bool:
    """Un import dentro del cuerpo de un ``try`` que atrapa ``ImportError``: su ausencia está prevista."""
    for padre in pila:
        if not isinstance(padre, ast.Try) or not any(nodo is x for s in padre.body for x in ast.walk(s)):
            continue
        for manejador in padre.handlers:
            tipos = manejador.type.elts if isinstance(manejador.type, ast.Tuple) else [manejador.type]
            if any(
                getattr(t, "id", "") in ("ImportError", "ModuleNotFoundError") for t in tipos if t is not None
            ):
                return True
    return False


def _imports_de(fuente: str) -> list[tuple[int, str, str | None, bool]]:
    """``(línea, módulo, nombre o None, opcional)`` de cada import absoluto de una celda."""
    limpia = "\n".join(
        "pass" if linea.lstrip().startswith(("!", "%")) else linea for linea in fuente.splitlines()
    )
    arbol = ast.parse(limpia)
    intentos = [n for n in ast.walk(arbol) if isinstance(n, ast.Try)]
    out: list[tuple[int, str, str | None, bool]] = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.ImportFrom) and nodo.module and nodo.level == 0:
            opcional = _es_opcional(intentos, nodo)
            out += [(nodo.lineno, nodo.module, a.name, opcional) for a in nodo.names]
        elif isinstance(nodo, ast.Import):
            opcional = _es_opcional(intentos, nodo)
            out += [(nodo.lineno, a.name, None, opcional) for a in nodo.names]
    return out


@dataclass
class InformeDeImports:
    comprobados: int = 0
    opcionales: int = 0
    rotos: list[str] = field(default_factory=list)
    sin_fuente: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.comprobados > 0 and not self.rotos and not self.sin_fuente


def _pertenece(modulo: str, paquete: str) -> bool:
    return modulo == paquete or modulo.startswith(paquete + ".")


def comprobar_imports(
    celdas: Sequence[str], fuentes: FuentesDelArnes, paquetes: Iterable[str] | None = None
) -> InformeDeImports:
    """Comprueba que cada import del arnés que hacen las celdas existe en ``fuentes``.

    Para ``import a.b`` exige el módulo; para ``from a.b import c`` exige además que ``c`` sea un submódulo,
    un nombre que el módulo enlaza al importarse o uno que sirve su ``__getattr__`` y que define algún módulo
    del mismo paquete. Un paquete del arnés sin fuente en la carpeta no se da por bueno: queda en
    ``sin_fuente``. No ve los accesos por atributo ni lo que el código resuelve al ejecutarse.
    """
    paquetes = list(PAQUETES_DEL_ARNES.values() if paquetes is None else paquetes)
    informe = InformeDeImports()
    for numero, celda in enumerate(celdas):
        try:
            imports = _imports_de(celda)
        except SyntaxError:
            informe.rotos.append(f"celda {numero}: no compila; sus imports no se pudieron leer")
            continue
        for linea, modulo, nombre, opcional in imports:
            paquete = next((p for p in paquetes if _pertenece(modulo, p)), None)
            if paquete is None:
                continue
            texto = f"celda {numero}, línea {linea}: " + (
                f"from {modulo} import {nombre}" if nombre else f"import {modulo}"
            )
            if opcional:
                informe.opcionales += 1
                continue
            if not fuentes.tiene_paquete(paquete):
                informe.sin_fuente.append(f"{texto} (la carpeta no trae el paquete {paquete})")
                continue
            informe.comprobados += 1
            ruta = fuentes.ruta_de(modulo)
            if ruta is None:
                informe.rotos.append(f"{texto}: el módulo no existe")
            elif nombre not in (None, "*") and not _nombre_existe(fuentes, modulo, ruta, str(nombre)):
                informe.rotos.append(f"{texto}: el módulo no define ese nombre")
    return informe


def _nombre_existe(fuentes: FuentesDelArnes, modulo: str, ruta: str, nombre: str) -> bool:
    if fuentes.ruta_de(f"{modulo}.{nombre}") is not None:
        return True
    try:
        definidos, perezosos = nombres_de(fuentes.archivos[ruta])
    except SyntaxError:
        return False
    if nombre in definidos:
        return True
    if nombre not in perezosos:
        return False
    # Lo sirve ``__getattr__``: tiene que definirlo algún módulo del mismo paquete de primer nivel.
    prefijo = modulo.split(".")[0] + "/"
    for otra, texto in fuentes.archivos.items():
        if otra.startswith(prefijo) and otra != ruta:
            try:
                if nombre in nombres_de(texto)[0]:
                    return True
            except SyntaxError:
                continue
    return False


IMPORT_DINAMICO = re.compile(
    r"""(import_module|__import__)\(\s*['"](swegemma|adk_submission|adk_eval_core|google\.adk)\b"""
)
ESPERADO_EN_LA_CELDA = re.compile(r"^ARNES_ESPERADO = (\{.*\})$", re.MULTILINE)


def usa_el_arnes(celdas: Sequence[str], paquetes: Iterable[str] | None = None) -> bool:
    """¿Alguna celda importa un paquete del arnés? Una celda que no compila cuenta como que sí."""
    paquetes = list(PAQUETES_DEL_ARNES.values() if paquetes is None else paquetes)
    for celda in celdas:
        if IMPORT_DINAMICO.search(celda):
            return True
        try:
            imports = _imports_de(celda)
        except SyntaxError:
            continue  # una celda que no compila ya es un fallo del chequeo previo
        if any(_pertenece(modulo, p) for _, modulo, _, _ in imports for p in paquetes):
            return True
    return False


def esperado_en_el_notebook(celdas: Sequence[str]) -> dict[str, str] | None:
    """Las versiones que la guarda del notebook exige (``ARNES_ESPERADO``); ``None`` si no trae la guarda."""
    for celda in celdas:
        if MARCA_VERSIONES not in celda:
            continue
        m = ESPERADO_EN_LA_CELDA.search(celda)
        if m is None:
            return None
        try:
            valor = ast.literal_eval(m.group(1))
        except (ValueError, SyntaxError):
            return None
        if isinstance(valor, dict) and "raise RuntimeError" in celda:
            return {str(k): str(v) for k, v in valor.items()}
    return None


SHA256_ESPERADO_EN_LA_CELDA = re.compile(r"^ARNES_SHA256_ESPERADO = (\{.*\})$", re.MULTILINE)


def sha256_esperado_en_el_notebook(celdas: Sequence[str]) -> dict[str, str] | None:
    """Los SHA-256 que la guarda del notebook exige (``ARNES_SHA256_ESPERADO``); ``None`` si no los compara.

    Solo cuenta una guarda que trae, tal cual, las líneas que calculan, comparan y detienen: un notebook que
    solo declara la constante, o que la compara sin detenerse, no la tiene.
    """
    for celda in celdas:
        if MARCA_VERSIONES not in celda:
            continue
        m = SHA256_ESPERADO_EN_LA_CELDA.search(celda)
        if m is None or not all(x in celda for x in (_SHA256_CUENTA, _SHA256_RESUMEN, _SHA256_PARADA)):
            return None
        try:
            valor = ast.literal_eval(m.group(1))
        except (ValueError, SyntaxError):
            return None
        if isinstance(valor, dict):
            return {str(k): str(v) for k, v in valor.items()}
    return None


def celdas_de_codigo(notebook: Any) -> list[str]:
    """Texto de las celdas de código de un notebook ya leído como JSON."""
    celdas = notebook.get("cells") if isinstance(notebook, dict) else None
    out = []
    for celda in celdas if isinstance(celdas, list) else []:
        if isinstance(celda, dict) and celda.get("cell_type") == "code":
            fuente = celda.get("source", "")
            out.append("".join(fuente) if isinstance(fuente, list) else str(fuente))
    return out
