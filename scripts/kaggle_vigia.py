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
no se considera.

«Sin procesar» quiere decir solo esto: hay un cambio en Kaggle respecto del último rescate. Un rescate
nuevo lo apaga; que la bitácora y la memoria se actualicen es trabajo del orquestador.

Además imprime los hallazgos de ``experiments/gemma_developer_agent/hallazgos.json`` que llevan más de una
vuelta en estado ``medido`` (regla de ``CONTRIBUTING.md``: un hallazgo medido no puede aparecer en dos
vueltas sin una decisión escrita). Eso no necesita red ni token.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.parse
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

if __package__ in (None, ""):  # ejecutado como archivo, como lo llama el gancho
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import kaggle_rescate

RAIZ_REPO = Path(__file__).resolve().parent.parent
RUTA_RESCATES = Path("experiments") / "gemma_developer_agent" / "data" / "rescate_kaggle"
RUTA_HALLAZGOS = RAIZ_REPO / "experiments" / "gemma_developer_agent" / "hallazgos.json"
VARIABLE_DE_TOKEN = "KAGGLE_API_TOKEN"
TOPE_TOTAL_S = 20.0
TOPE_GIT_S = 5
MAX_NOTEBOOKS_A_CONSULTAR = 5
TOPE_LINEAS_DE_HALLAZGOS = 12
MARCA_DE_CARPETA = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2})(\d{2})(\d{2})?Z$")
Pedir = Callable[[str, str], bytes]


# ---------------------------------------------------------------------------
# Token
# ---------------------------------------------------------------------------


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
    """``KAGGLE_RESCATES`` si existe; si no, la carpeta del árbol actual; si no, la del árbol principal."""
    puesta = entorno.get("KAGGLE_RESCATES", "").strip()
    candidatas = [Path(puesta)] if puesta else []
    candidatas.append(raiz_repo / RUTA_RESCATES)
    if principal is None:
        principal = raiz_del_arbol_principal(raiz_repo)
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


def ultima_lectura(rescates: Path) -> tuple[Path, datetime] | None:
    """La carpeta del rescate más reciente (con su ``envios.json``) y su marca. Regla en el docstring."""
    candidatas: list[tuple[datetime, float, str, Path]] = []
    for archivo in [*rescates.glob("*/envios.json"), *rescates.glob("*/*/envios.json")]:
        carpeta = archivo.parent
        marca = marca_de(carpeta) or (marca_de(carpeta.parent) if carpeta.parent != rescates else None)
        if marca is None:
            continue
        try:
            modificado = archivo.stat().st_mtime
        except OSError:
            continue
        candidatas.append((marca, modificado, str(archivo), carpeta))
    if not candidatas:
        return None
    mejor = max(candidatas, key=lambda c: (c[0], c[1], c[2]))
    return mejor[3], mejor[0]


# ---------------------------------------------------------------------------
# Comparar
# ---------------------------------------------------------------------------


def _nota(valor: Any) -> float | None:
    try:
        return round(float(str(valor).strip()), 4) if str(valor).strip() else None
    except ValueError:
        return None


def resumen_de_envios(envios: Any) -> dict[int, tuple[str, float | None]]:
    """``{ref: (estado, nota)}`` de una lista de envíos de la API (o de un ``envios.json``)."""
    if not isinstance(envios, list):
        raise ValueError("la lista de envíos no es una lista")
    out: dict[int, tuple[str, float | None]] = {}
    for e in envios:
        if not isinstance(e, dict) or "ref" not in e:
            raise ValueError("un envío sin ref")
        out[int(e["ref"])] = (str(e.get("status") or "").strip(), _nota(e.get("publicScore")))
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
PROHIBIDO_EN_HALLAZGOS = re.compile(r"\b[a-z]+_\d{3,5}\b|github\.com|diff --git|/workspace/")


def _texto(valor: Any) -> bool:
    return isinstance(valor, str) and bool(valor.strip())


def validar_hallazgos(datos: Any) -> list[str]:
    """Los problemas de formato de un registro de hallazgos; lista vacía si es válido."""
    if (
        not isinstance(datos, dict)
        or datos.get("version") != 1
        or not isinstance(datos.get("hallazgos"), list)
    ):
        return ["el registro debe ser un objeto con version 1 y la lista `hallazgos`"]
    problemas: list[str] = []
    ids: set[str] = set()
    for fila in datos["hallazgos"]:
        if not isinstance(fila, dict):
            problemas.append("una fila no es un objeto")
            continue
        nombre = str(fila.get("id"))
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
        try:
            datetime.strptime(str(fila.get("primera_fecha")), "%Y-%m-%d")
        except ValueError:
            problemas.append(f"{nombre}: `primera_fecha` debe ser AAAA-MM-DD")
        estado = fila.get("estado")
        if estado not in ESTADOS:
            problemas.append(f"{nombre}: estado desconocido {estado!r}")
        decision = fila.get("decision")
        if estado in ("decidido", "aplicado"):
            if not (
                isinstance(decision, dict)
                and _texto(decision.get("texto"))
                and _texto(decision.get("quien"))
                and isinstance(decision.get("vuelta"), int)
                and _texto(decision.get("fecha"))
            ):
                problemas.append(f"{nombre}: `{estado}` exige decision con texto, quien, vuelta y fecha")
        elif decision is not None:
            problemas.append(f"{nombre}: solo `decidido` y `aplicado` llevan decision")
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
    guardados_crudo = json.loads((carpeta / "envios.json").read_text(encoding="utf-8"))
    guardados = resumen_de_envios(guardados_crudo)
    edad_h = (ahora - marca).total_seconds() / 3600
    lineas = [
        f"última lectura guardada: {carpeta.name} (hace {edad_h:.1f} h"
        + (", más de un día: corre el rescate" if edad_h > 24 else "")
        + ")"
    ]
    actuales_crudo = json.loads(
        pedir(f"competitions/submissions/list/{kaggle_rescate.COMPETITION_SLUG}?page=1", token)
    )
    cambios = comparar_envios(guardados, resumen_de_envios(actuales_crudo))
    lineas += cambios
    usuario = _usuario_de(carpeta, guardados_crudo)
    guardados_nb = carpeta / "notebooks.json"
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
            principal = raiz_del_arbol_principal(raiz_repo)
        raices = [raiz_repo] + ([principal] if principal and principal != raiz_repo else [])
        token = leer_token(entorno, raices)
        carpeta = rescates if rescates is not None else carpeta_de_rescates(raiz_repo, entorno, principal)
        lectura = ultima_lectura(carpeta) if carpeta is not None else None
        if not token:
            salida.append(f"sin token de Kaggle ({VARIABLE_DE_TOKEN}): no consulté la API")
        elif lectura is None:
            salida.append(
                "no hay lectura guardada de un rescate: no tengo con qué comparar. Corre el rescate."
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
        salida.append(tapar(f"no pude leer Kaggle ({type(exc).__name__}: {exc})", token))
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
