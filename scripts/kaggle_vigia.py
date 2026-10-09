"""Vigía de Kaggle al iniciar la sesión: qué cambió desde el último rescate y qué hallazgo no tiene decisión.

Lo ejecuta el gancho ``SessionStart`` de Claude Code (``.claude/settings.json``) y su salida entra en el
contexto de la sesión. **Solo lee**: pide por la API los envíos propios y la lista de notebooks propios, los
compara con la última lectura guardada por el rescate y dice lo que cambió y está **sin procesar**. No sube,
no envía, no escribe nada. Reutiliza ``scripts.kaggle_rescate.pedir`` (token solo a hosts de Kaggle, https,
sin seguir redirecciones a otro host), así que no hay una segunda forma de llamar a la API.

    python scripts/kaggle_vigia.py                      # como gancho: siempre sale con 0
    python scripts/kaggle_vigia.py --rescates <carpeta> # otra carpeta de rescates

Sin token, sin red, con una respuesta ilegible, o pasado su tope de tiempo, lo dice en una línea y sale con
0: un vigía que estorba el arranque se acaba quitando. No imprime el token ni lo guarda; si un mensaje de
error lo contuviera, se tapa antes de imprimir.

La «última lectura guardada» es el ``envios.json`` del rescate más reciente bajo la carpeta de rescates
(``experiments/gemma_developer_agent/data/rescate_kaggle``, ignorada por git, que solo existe en el árbol
principal: desde un worktree se busca en el árbol principal). Regla para elegir «el más reciente»: se buscan
los ``envios.json`` a profundidad 1 y 2; cada uno toma la marca de tiempo del nombre de carpeta más cercano
con la forma ``AAAA-MM-DDTHHMM[SS]Z``; gana la marca más alta, y entre marcas iguales gana el ``envios.json``
con fecha de modificación posterior y, si aún empatan, el de ruta mayor. Una carpeta sin marca de tiempo
no se considera. Tampoco sirven (y se avisa de ellas) las de marca futura y las incompletas: el rescate
escribe ``envios.json`` primero y puede morir justo después, así que una lectura vale solo si trae también
``tabla_publica.zip`` o ``notebooks.json``.

«Sin procesar» quiere decir solo esto: hay un cambio en Kaggle respecto del último rescate. Un rescate
nuevo lo apaga; que la bitácora y la memoria se actualicen es trabajo del orquestador.

Además imprime los hallazgos de ``experiments/gemma_developer_agent/hallazgos.json`` que llevan más de una
vuelta en estado ``medido`` (regla de ``CONTRIBUTING.md``: un hallazgo medido no puede aparecer en dos
vueltas sin una decisión escrita). Eso no necesita red ni token.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
import threading
import time
import urllib.parse
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

if __package__ in (None, ""):  # ejecutado como archivo, como lo llama el gancho
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import kaggle_rescate

RAIZ_REPO = Path(__file__).resolve().parent.parent
RUTA_RESCATES = Path("experiments") / "gemma_developer_agent" / "data" / "rescate_kaggle"
RUTA_HALLAZGOS = RAIZ_REPO / "experiments" / "gemma_developer_agent" / "hallazgos.json"
VARIABLE_DE_TOKEN = "KAGGLE_API_TOKEN"
# El gancho tiene 30 s (.claude/settings.json). Peor caso: git (3 s) + este tope (15 s) + leer archivos.
TOPE_TOTAL_S = 15.0
TOPE_GIT_S = 3
# Supuesto, no medido: con 20 envíos o más en la lista, la primera página puede no traerlos todos.
PAGINA_LLENA = 20
MAX_NOTEBOOKS_A_CONSULTAR = 5
UMBRAL_DE_EDAD_H = 24
TOPE_LINEAS_DE_HALLAZGOS = 12
MARCA_DE_CARPETA = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2})(\d{2})(\d{2})?Z$")
Pedir = Callable[[str, str], bytes]


# ---------------------------------------------------------------------------
# Token
# ---------------------------------------------------------------------------


def token_bien_formado(token: str) -> bool:
    """Un token sirve si son solo caracteres ASCII imprimibles, sin espacios ni saltos de línea.

    Un valor con un salto de línea interior (por ejemplo un ``kaggle.json`` pegado en la variable) haría que
    la biblioteca de red citara el valor entero en su mensaje de error; no se usa.
    """
    return bool(token) and all(0x21 <= ord(c) <= 0x7E for c in token)


def leer_token(entorno: Mapping[str, str], raices: Sequence[Path]) -> str:
    """El token del entorno o, si falta, de un ``.env`` de una de las raíces; ``""`` si no hay."""
    token = entorno.get(VARIABLE_DE_TOKEN, "").strip()
    if token:
        return token
    for raiz in raices:
        try:
            lineas = (raiz / ".env").read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for linea in lineas:
            nombre, _, valor = linea.partition("=")
            if nombre.strip() == VARIABLE_DE_TOKEN and valor.strip().strip("'\""):
                return valor.strip().strip("'\"")
    return ""


def tapar(texto: str, token: str) -> str:
    """Quita el token de un texto que se va a imprimir."""
    return texto.replace(token, "***") if token else texto


# ---------------------------------------------------------------------------
# Dónde están los rescates y cuál es el último
# ---------------------------------------------------------------------------


def raiz_del_arbol_principal(raiz_repo: Path) -> Path | None:
    """El árbol principal del repositorio (los worktrees comparten ``.git`` con él), o ``None``."""
    try:
        r = subprocess.run(
            ["git", "-C", str(raiz_repo), "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True,
            text=True,
            timeout=TOPE_GIT_S,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0 or not r.stdout.strip():
        return None
    return Path(r.stdout.strip()).parent


def carpeta_de_rescates(
    raiz_repo: Path, entorno: Mapping[str, str], principal: Path | None = None
) -> Path | None:
    """``KAGGLE_RESCATES`` si existe; si no, la carpeta del árbol actual; si no, la del árbol principal.

    ``principal`` lo calcula quien llama (una sola vez: cada llamada a ``git`` gasta tiempo del gancho).
    """
    puesta = entorno.get("KAGGLE_RESCATES", "").strip()
    candidatas = [Path(puesta)] if puesta else []
    candidatas.append(raiz_repo / RUTA_RESCATES)
    if principal is not None:
        candidatas.append(principal / RUTA_RESCATES)
    return next((c for c in candidatas if c.is_dir()), None)


def marca_de(carpeta: Path) -> datetime | None:
    """La marca de tiempo (UTC) del nombre de una carpeta de rescate, o ``None``."""
    m = MARCA_DE_CARPETA.match(carpeta.name)
    if not m:
        return None
    a, mes, d, h, mi, s = m.groups()
    try:
        return datetime(int(a), int(mes), int(d), int(h), int(mi), int(s or 0), tzinfo=UTC)
    except ValueError:
        return None


def rescate_completo(carpeta: Path) -> bool:
    """El rescate escribe ``envios.json`` primero y puede morir justo después: una lectura sirve para dar algo
    por procesado solo si trae también la tabla pública o la lista de notebooks."""
    return (carpeta / "tabla_publica.zip").is_file() or (carpeta / "notebooks.json").is_file()


def buscar_rescates(rescates: Path) -> list[tuple[datetime, float, str, Path]]:
    """(marca, mtime, ruta, carpeta) de cada ``envios.json`` a profundidad 1 y 2 con marca de tiempo."""
    candidatas: list[tuple[datetime, float, str, Path]] = []
    for archivo in [*rescates.glob("*/envios.json"), *rescates.glob("*/*/envios.json")]:
        carpeta = archivo.parent
        marca = marca_de(carpeta)
        if marca is None and carpeta.parent != rescates:
            marca = marca_de(carpeta.parent)  # carpeta interior sin marca propia: hereda la de su madre
        if marca is None:
            continue
        try:
            modificado = archivo.stat().st_mtime
        except OSError:
            continue
        candidatas.append((marca, modificado, str(archivo), carpeta))
    return candidatas


def ultima_lectura(rescates: Path, ahora: datetime | None = None) -> tuple[Path, datetime] | None:
    """La carpeta del rescate más reciente que sirve (completo, con marca no futura) y su marca."""
    validas = [
        c for c in buscar_rescates(rescates) if rescate_completo(c[3]) and (ahora is None or c[0] <= ahora)
    ]
    if not validas:
        return None
    mejor = max(validas, key=lambda c: (c[0], c[1], c[2]))
    return mejor[3], mejor[0]


def avisos_de_rescates(rescates: Path, ahora: datetime, marca_elegida: datetime | None) -> list[str]:
    """Rescates que no se usaron aunque parecían más nuevos: con fecha futura o incompletos."""
    avisos: list[str] = []
    for marca, _, _, carpeta in sorted(buscar_rescates(rescates), key=lambda c: c[0], reverse=True):
        if marca > ahora:
            avisos.append(f"ignoré {carpeta.name}: su fecha es futura")
        elif not rescate_completo(carpeta) and (marca_elegida is None or marca >= marca_elegida):
            avisos.append(
                f"el rescate {carpeta.name} está incompleto (solo envios.json): "
                "no lo uso para dar nada por procesado"
            )
    return avisos


# ---------------------------------------------------------------------------
# Comparar
# ---------------------------------------------------------------------------


def _nota(valor: Any) -> float | None:
    """La nota como número; ``None`` si no hay, no se entiende o no es finita (``nan`` != ``nan``)."""
    try:
        numero = float(str(valor).strip()) if str(valor).strip() else None
    except ValueError:
        return None
    return round(numero, 4) if numero is not None and math.isfinite(numero) else None


def resumen_de_envios(envios: Any) -> dict[int, tuple[str, float | None]]:
    """``{ref: (estado, nota)}`` de una lista de envíos de la API (o de un ``envios.json``)."""
    if not isinstance(envios, list):
        raise ValueError("la lista de envíos no es una lista")
    out: dict[int, tuple[str, float | None]] = {}
    for e in envios:
        if not isinstance(e, dict) or "ref" not in e:
            raise ValueError("un envío sin ref")
        if not isinstance(e.get("status"), str) or not e["status"].strip():
            raise ValueError("un envío sin status (¿cambió el nombre del campo?)")
        out[int(e["ref"])] = (e["status"].strip(), _nota(e.get("publicScore")))
    return out


def _nota_txt(nota: float | None) -> str:
    return "sin nota" if nota is None else f"{nota:g}".replace(".", ",")


def comparar_envios(
    guardados: dict[int, tuple[str, float | None]], actuales: dict[int, tuple[str, float | None]]
) -> list[str]:
    """Una línea por cada envío que cambió, apareció o desapareció. Sin cambios, ninguna línea."""
    lineas: list[str] = []
    for ref in sorted(set(guardados) | set(actuales), reverse=True):
        antes, ahora = guardados.get(ref), actuales.get(ref)
        if antes == ahora:
            continue
        if antes is None and ahora is not None:
            lineas.append(
                f"envío {ref} es nuevo (`{ahora[0]}`, {_nota_txt(ahora[1])}) y no está en el último rescate: "
                "sin procesar"
            )
        elif ahora is None and antes is not None:
            lineas.append(
                f"envío {ref} estaba en el último rescate (`{antes[0]}`, {_nota_txt(antes[1])}) "
                "y la API ya no lo devuelve: sin procesar"
            )
        elif antes is not None and ahora is not None and antes[0] != ahora[0]:
            lineas.append(
                f"envío {ref} pasó de `{antes[0]}` a `{ahora[0]}` con nota {_nota_txt(ahora[1])}: "
                "sin procesar"
            )
        elif antes is not None and ahora is not None:
            lineas.append(
                f"envío {ref} sigue `{ahora[0]}` pero su nota pasó de {_nota_txt(antes[1])} a "
                f"{_nota_txt(ahora[1])}: sin procesar"
            )
    return lineas


def notebooks_cambiados(guardados: Any, actuales: Any) -> list[str]:
    """Refs de notebooks nuevos o con otra ``lastRunTime`` que la guardada."""
    if not isinstance(guardados, list) or not isinstance(actuales, list):
        raise ValueError("la lista de notebooks no es una lista")
    antes = {str(n.get("ref")): str(n.get("lastRunTime") or "") for n in guardados if isinstance(n, dict)}
    cambiados = []
    for n in actuales:
        if (
            isinstance(n, dict)
            and n.get("ref")
            and antes.get(str(n["ref"])) != str(n.get("lastRunTime") or "")
        ):
            cambiados.append(str(n["ref"]))
    return cambiados


# ---------------------------------------------------------------------------
# Hallazgos
# ---------------------------------------------------------------------------


ESTADOS = ("medido", "decidido", "aplicado", "descartado")
PROHIBIDO_EN_HALLAZGOS = re.compile(
    r"\b[a-z]+_\d{3,5}\b"  # identificador de tarea con forma repo_1234
    r"|\b[\w.-]+__[\w.-]*-\d+\b"  # identificador con forma org__repo-12345
    r"|(?:[\w.-]+/)+[\w.-]+\.(?:py|js|ts|tsx|jsx|java|go|rs|c|h|cpp|rb|php|sh|toml|yaml|yml)\b"  # ruta
    r"|github\.com|diff --git|/workspace/"
)
CAMPOS_DE_HALLAZGO = frozenset(
    {
        "id",
        "que_se_midio",
        "primera_vuelta",
        "primera_fecha",
        "vueltas_medido",
        "estado",
        "decision",
        "motivo_descarte",
        "por_que_sigue_abierto",
    }
)
CAMPOS_DE_DECISION = frozenset({"texto", "quien", "vuelta", "fecha"})
CAMPOS_DEL_REGISTRO = frozenset({"version", "descripcion", "estados", "hallazgos"})
FECHA_ISO = re.compile(r"\d{4}-\d{2}-\d{2}")


def _texto(valor: Any) -> bool:
    return isinstance(valor, str) and bool(valor.strip())


def _fecha_iso(valor: Any) -> date | None:
    """La fecha de un ``AAAA-MM-DD`` estricto (con ceros), o ``None``."""
    if not isinstance(valor, str) or not FECHA_ISO.fullmatch(valor):
        return None
    try:
        return date.fromisoformat(valor)
    except ValueError:
        return None


def _entero(valor: Any) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool)


def validar_hallazgos(datos: Any, hoy: date | None = None) -> list[str]:
    """Los problemas de formato de un registro de hallazgos; lista vacía si es válido."""
    hoy = hoy or datetime.now(UTC).date()
    if (
        not isinstance(datos, dict)
        or datos.get("version") != 1
        or not isinstance(datos.get("hallazgos"), list)
    ):
        return ["el registro debe ser un objeto con version 1 y la lista `hallazgos`"]
    problemas: list[str] = []
    if set(datos) - CAMPOS_DEL_REGISTRO:
        problemas.append(f"campos desconocidos en el registro: {sorted(set(datos) - CAMPOS_DEL_REGISTRO)}")
    for campo in ("descripcion", "estados"):
        if PROHIBIDO_EN_HALLAZGOS.search(json.dumps(datos.get(campo), ensure_ascii=False)):
            problemas.append(f"`{campo}`: parece llevar un identificador de tarea, un enlace o una ruta")
    ids: set[str] = set()
    for fila in datos["hallazgos"]:
        if not isinstance(fila, dict):
            problemas.append("una fila no es un objeto")
            continue
        nombre = str(fila.get("id"))
        if set(fila) - CAMPOS_DE_HALLAZGO:
            problemas.append(f"{nombre}: campos desconocidos {sorted(set(fila) - CAMPOS_DE_HALLAZGO)}")
        if not re.fullmatch(r"[a-z][a-z0-9_]*", nombre) or nombre in ids:
            problemas.append(f"{nombre}: id ausente, mal formado o repetido")
        ids.add(nombre)
        if not _texto(fila.get("que_se_midio")):
            problemas.append(f"{nombre}: falta `que_se_midio`")
        vueltas = fila.get("vueltas_medido")
        if (
            not isinstance(vueltas, list)
            or not vueltas
            or not all(isinstance(v, int) and not isinstance(v, bool) and v >= 1 for v in vueltas)
            or vueltas != sorted(set(vueltas))
        ):
            problemas.append(f"{nombre}: `vueltas_medido` debe ser una lista no vacía de enteros crecientes")
        elif fila.get("primera_vuelta") != vueltas[0]:
            problemas.append(f"{nombre}: `primera_vuelta` no es la primera de `vueltas_medido`")
        primera = _fecha_iso(fila.get("primera_fecha"))
        if primera is None:
            problemas.append(f"{nombre}: `primera_fecha` debe ser AAAA-MM-DD")
        elif primera > hoy:
            problemas.append(f"{nombre}: `primera_fecha` es futura")
        estado = fila.get("estado")
        if estado not in ESTADOS:
            problemas.append(f"{nombre}: estado desconocido {estado!r}")
        decision = fila.get("decision")
        # `decidido` y `aplicado` la exigen; un `descartado` puede llevarla (el veto de un concilio).
        if estado in ("decidido", "aplicado") or (estado == "descartado" and decision is not None):
            if not (
                isinstance(decision, dict)
                and _texto(decision.get("texto"))
                and _texto(decision.get("quien"))
                and _entero(decision.get("vuelta"))
                and _texto(decision.get("fecha"))
            ):
                problemas.append(f"{nombre}: `{estado}` exige decision con texto, quien, vuelta y fecha")
            else:
                if set(decision) - CAMPOS_DE_DECISION:
                    problemas.append(
                        f"{nombre}: campos desconocidos en decision "
                        f"{sorted(set(decision) - CAMPOS_DE_DECISION)}"
                    )
                if (fecha := _fecha_iso(decision["fecha"])) is None or fecha > hoy:
                    problemas.append(f"{nombre}: `decision.fecha` debe ser AAAA-MM-DD y no futura")
                if _entero(fila.get("primera_vuelta")) and decision["vuelta"] < fila["primera_vuelta"]:
                    problemas.append(f"{nombre}: `decision.vuelta` es anterior a la primera vuelta")
        elif decision is not None:
            problemas.append(f"{nombre}: solo `decidido`, `aplicado` y `descartado` llevan decision")
        if estado == "descartado" and not _texto(fila.get("motivo_descarte")):
            problemas.append(f"{nombre}: `descartado` exige `motivo_descarte`")
        if (
            estado == "medido"
            and isinstance(vueltas, list)
            and len(set(vueltas)) > 1
            and not _texto(fila.get("por_que_sigue_abierto"))
        ):
            problemas.append(f"{nombre}: medido en más de una vuelta sin decisión ni `por_que_sigue_abierto`")
        if PROHIBIDO_EN_HALLAZGOS.search(json.dumps(fila, ensure_ascii=False)):
            problemas.append(f"{nombre}: parece llevar un identificador de tarea, un enlace o una ruta")
    return problemas


def hallazgos_sin_decision(ruta: Path) -> list[str]:
    """Líneas para los hallazgos en ``medido`` que aparecen en más de una vuelta."""
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        filas = datos["hallazgos"]
    except (OSError, ValueError, KeyError, TypeError):
        return ["no pude leer el registro de hallazgos (hallazgos.json): no sé cuáles siguen sin decisión"]
    lineas = []
    problemas = validar_hallazgos(datos)
    if problemas:
        lineas.append(
            f"hallazgos.json no cumple su formato ({len(problemas)} problemas; el primero: {problemas[0]})"
        )
    for h in filas:
        try:
            vueltas = sorted(set(h["vueltas_medido"]))
            if h["estado"] == "medido" and len(vueltas) > 1:
                razon = str(h.get("por_que_sigue_abierto") or "sin razón escrita")
                lineas.append(
                    f"hallazgo «{h['id']}» medido en {len(vueltas)} vueltas ({', '.join(map(str, vueltas))}) "
                    f"y sigue en `medido`: {razon}"
                )
        except (KeyError, TypeError):
            lineas.append("una fila de hallazgos.json no tiene el formato esperado")
    if len(lineas) > TOPE_LINEAS_DE_HALLAZGOS:
        extra = len(lineas) - TOPE_LINEAS_DE_HALLAZGOS
        lineas = [*lineas[:TOPE_LINEAS_DE_HALLAZGOS], f"… {extra} más en hallazgos.json"]
    return lineas


# ---------------------------------------------------------------------------
# La consulta a la API, con tope
# ---------------------------------------------------------------------------


def pedir_con_tope_de_socket(ruta: str, token: str, segundos: float = 8.0) -> bytes:
    """``kaggle_rescate.pedir`` con un tiempo de espera por petición menor que el suyo (120 s)."""
    anterior = kaggle_rescate.TOPE_S
    kaggle_rescate.TOPE_S = max(1, int(segundos))
    try:
        return kaggle_rescate.pedir(ruta, token)
    finally:
        kaggle_rescate.TOPE_S = anterior


def con_tope(funcion: Callable[[], list[str]], segundos: float) -> list[str] | None:
    """Ejecuta ``funcion`` en un hilo; ``None`` si no termina en ``segundos`` (el hilo se abandona)."""
    resultado: list[list[str]] = []
    errores: list[BaseException] = []

    def trabajo() -> None:
        try:
            resultado.append(funcion())
        except BaseException as exc:  # el hilo nunca debe morir en silencio
            errores.append(exc)

    hilo = threading.Thread(target=trabajo, daemon=True)
    hilo.start()
    hilo.join(segundos)
    if hilo.is_alive():
        return None
    if errores:
        raise errores[0]
    return resultado[0]


def _usuario_de(carpeta: Path, envios: Any) -> str | None:
    archivo = carpeta / "usuario.txt"
    if archivo.is_file():
        texto = archivo.read_text(encoding="utf-8").strip()
        if texto:
            return texto
    if isinstance(envios, list):
        return next(
            (str(e["submittedByRef"]) for e in envios if isinstance(e, dict) and e.get("submittedByRef")),
            None,
        )
    return None


def consultar(
    carpeta: Path, marca: datetime, token: str, pedir: Pedir, ahora: datetime, limite: float
) -> list[str]:
    """Compara la lectura guardada en ``carpeta`` con la API. Lanza si algo no se pudo leer."""
    try:
        guardados_crudo = json.loads((carpeta / "envios.json").read_text(encoding="utf-8"))
        guardados = resumen_de_envios(guardados_crudo)
    except (OSError, ValueError, TypeError) as exc:
        return [f"no pude leer la lectura guardada ({carpeta.name}/envios.json): {type(exc).__name__}"]
    edad_h = (ahora - marca).total_seconds() / 3600
    lineas = [
        f"última lectura guardada: {carpeta.name} (hace {edad_h:.1f} h"
        + (f", más de {UMBRAL_DE_EDAD_H} h: corre el rescate" if edad_h > UMBRAL_DE_EDAD_H else "")
        + ")"
    ]
    try:
        actuales_crudo = json.loads(
            pedir(f"competitions/submissions/list/{kaggle_rescate.COMPETITION_SLUG}?page=1", token)
        )
        actuales = resumen_de_envios(actuales_crudo)
    except (ValueError, TypeError) as exc:
        return [*lineas, f"no pude leer Kaggle (respuesta de envíos ilegible: {type(exc).__name__})"]
    cambios = comparar_envios(guardados, actuales)
    lineas += cambios
    if max(len(actuales), len(guardados)) >= PAGINA_LLENA:
        lineas.append(
            f"solo leí la primera página de envíos ({len(actuales)}): "
            "uno que «ya no aparece» puede estar en otra"
        )
    usuario = _usuario_de(carpeta, guardados_crudo)
    guardados_nb = carpeta / "notebooks.json"
    faltas = [
        texto
        for texto, falta in (
            ("usuario.txt y ningún envío trae el usuario", not usuario),
            ("notebooks.json en la lectura guardada", not guardados_nb.is_file()),
            ("tiempo (se gastó el tope)", time.monotonic() >= limite),
        )
        if falta
    ]
    if faltas:
        lineas.append(f"no comparé los notebooks: falta {', '.join(faltas)}")
    if usuario and guardados_nb.is_file() and time.monotonic() < limite:
        try:
            lista = json.loads(pedir(f"kernels/list?user={urllib.parse.quote(usuario)}&pageSize=100", token))
            cambiados = notebooks_cambiados(json.loads(guardados_nb.read_text(encoding="utf-8")), lista)
        except (ValueError, kaggle_rescate.RescateError) as exc:
            lineas.append(f"no pude comparar los notebooks: {type(exc).__name__}")
            cambiados = []
        for ref in cambiados[:MAX_NOTEBOOKS_A_CONSULTAR]:
            estado = "sin estado"
            slug = ref.split("/", 1)[-1]
            if time.monotonic() < limite:
                try:
                    consulta = f"userName={urllib.parse.quote(usuario)}&kernelSlug={urllib.parse.quote(slug)}"
                    estado = str(
                        json.loads(pedir(f"kernels/status?{consulta}", token)).get("status") or "sin estado"
                    )
                except (ValueError, AttributeError, kaggle_rescate.RescateError):
                    estado = "sin estado"
            terminado = "terminó" if estado == "complete" else f"está `{estado}`"
            lineas.append(
                f"notebook {ref} {terminado} y no está rescatado (corrió después del último rescate)"
            )
        if len(cambiados) > MAX_NOTEBOOKS_A_CONSULTAR:
            lineas.append(f"… y {len(cambiados) - MAX_NOTEBOOKS_A_CONSULTAR} notebooks más sin rescatar")
    if not cambios:
        lineas.append("envíos sin cambios desde esa lectura")
    return lineas


def vigia(
    raiz_repo: Path = RAIZ_REPO,
    entorno: Mapping[str, str] | None = None,
    pedir: Pedir | None = None,
    ahora: datetime | None = None,
    ruta_hallazgos: Path | None = None,
    tope_s: float = TOPE_TOTAL_S,
    principal: Path | None = None,
    rescates: Path | None = None,
) -> list[str]:
    """Las líneas que imprime el vigía. Nunca lanza."""
    entorno = os.environ if entorno is None else entorno
    ahora = ahora or datetime.now(UTC)
    salida = ["VIGÍA KAGGLE"]
    token = ""
    try:
        if principal is None:
            principal = raiz_del_arbol_principal(raiz_repo)  # una sola llamada a git
        raices = [raiz_repo] + ([principal] if principal and principal != raiz_repo else [])
        token = leer_token(entorno, raices)
        carpeta = rescates if rescates is not None else carpeta_de_rescates(raiz_repo, entorno, principal)
        lectura = ultima_lectura(carpeta, ahora) if carpeta is not None else None
        if carpeta is not None:
            salida += avisos_de_rescates(carpeta, ahora, lectura[1] if lectura else None)
        if not token:
            salida.append(f"sin token de Kaggle ({VARIABLE_DE_TOKEN}): no consulté la API")
        elif not token_bien_formado(token):
            salida.append(
                "token mal formado (caracteres de control, espacios o no ASCII): no consulté la API"
            )
            token = ""  # no se usa y no hay nada que tapar
        elif lectura is None:
            salida.append(
                "no hay lectura guardada y completa de un rescate: no tengo con qué comparar. "
                "Corre el rescate."
            )
        else:
            limite = time.monotonic() + tope_s
            pedir_real = pedir or (
                lambda ruta, tk: pedir_con_tope_de_socket(
                    ruta, tk, max(1.0, min(8.0, limite - time.monotonic()))
                )
            )
            lineas = con_tope(
                lambda: consultar(lectura[0], lectura[1], token, pedir_real, ahora, limite), tope_s
            )
            salida += (
                lineas
                if lineas is not None
                else [f"Kaggle no respondió en {tope_s:g} s: no sé si hay cambios"]
            )
    except Exception as exc:  # el vigía no debe estorbar el arranque por ningún motivo
        # Solo el mensaje de nuestra propia excepción (sin la URL con parámetros ni el valor del token) o,
        # para cualquier otra, su tipo: la biblioteca de red puede citar el valor de una cabecera.
        detalle = str(exc) if isinstance(exc, kaggle_rescate.RescateError) else ""
        salida.append(
            tapar(f"no pude leer Kaggle ({type(exc).__name__}{': ' + detalle if detalle else ''})", token)
        )
    try:
        salida += hallazgos_sin_decision(ruta_hallazgos or RUTA_HALLAZGOS)
    except Exception as exc:
        salida.append(f"no pude leer los hallazgos ({type(exc).__name__})")
    return [tapar(linea, token) for linea in salida]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="scripts/kaggle_vigia.py", description=__doc__.split("\n")[0])
    p.add_argument("--rescates", type=Path, default=None, help="Carpeta que contiene los rescates")
    p.add_argument("--tope-s", type=float, default=TOPE_TOTAL_S, help="Tope de tiempo total, en segundos")
    args, _ = p.parse_known_args(argv)
    texto = "\n".join(vigia(rescates=args.rescates, tope_s=args.tope_s))
    if hasattr(sys.stdout, "reconfigure"):  # la consola de Windows no siempre es UTF-8
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(texto)
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
