"""Rescata de Kaggle todo lo que la cuenta puede leer del concurso y lo deja en disco, fechado.

Cada corrida en Kaggle deja información que se pierde si no se baja: el log completo de cada notebook
(se sobrescribe con la versión siguiente y desaparece al borrar el notebook), sus archivos de salida, el
registro completo de cada envío y la tabla pública entera. Este guion lo baja todo de una vez y resume la
tabla en **tareas**, no en decimales.

Uso:
    python -m scripts.kaggle_rescate --destino <directorio fuera de git o ignorado> [--usuario <usuario>]
    python -m scripts.kaggle_rescate --destino <directorio> --sin-red      # solo resume lo ya bajado

Lee el token de la variable ``KAGGLE_API_TOKEN`` y no lo imprime. Lo bajado puede contener salidas de
notebooks con datos de la competencia: el guion se niega si ``--destino`` queda versionable. El resumen que
imprime lleva solo agregados de la tabla pública y de los envíos propios.

Un notebook o un archivo de salida que no se pueda bajar o guardar no detiene el resto: queda anotado en
``faltantes.json`` y el resumen lo repite en ``descarga_incompleta``. Un nombre de archivo que no cabe en una
ruta de Windows se guarda acortado; ``salidas.json`` conserva el nombre que tenía en Kaggle.

Cada archivo de salida ``.zip`` se abre solo para leer su lista de miembros (nada se extrae). Un miembro
exigido (bajo ``logs/`` o ``traces/``, o ``task_results.jsonl``) de 0 bytes, o un zip ilegible, es un
faltante; un ``patches/`` o ``test_outputs/`` vacío solo se cuenta. Con ``--sin-red`` la revisión se repite
y se informa en el resumen y en el código de salida, sin reescribir ``faltantes.json``.

Salida: 0 si se bajó y resumió, 2 si la entrada es inválida o falta el token, 3 si Kaggle no respondió,
4 si se bajó y resumió pero faltó algún notebook o archivo de salida, o un zip trae un miembro exigido vacío.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import http.client
import io
import json
import math
import os
import statistics
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

API = "https://www.kaggle.com/api/v1"
HOSTS_CON_TOKEN = frozenset({urllib.parse.urlsplit(API).hostname, "www.kaggle.com", "api.kaggle.com"})
COMPETITION_SLUG = "gemma-4-developer-agent"
TOPE_S = 120
# Windows rechaza rutas de 260 caracteres o más si no se activó el soporte de rutas largas.
TOPE_RUTA = 240

EXIT_OK = 0
EXIT_ENTRADA = 2
EXIT_RED = 3
EXIT_PARCIAL = 4


class RescateError(RuntimeError):
    """Entrada inválida, token ausente o respuesta inesperada de Kaggle."""


# ---------------------------------------------------------------------------
# Lectura de la tabla: de decimales a tareas
# ---------------------------------------------------------------------------


def nota_truncada(k: int, n: int) -> float:
    """La nota que muestra la tabla para ``k`` de ``n`` tareas: dos decimales, truncados (no redondeados)."""
    return math.floor(k * 100 / n + 1e-9) / 100


def tamanos_compatibles(notas: Sequence[float], minimo: int = 20, maximo: int = 200) -> list[int]:
    """Tamaños ``n`` de la tabla para los que toda nota observada es ``k/n`` truncado a dos decimales."""
    distintas = sorted({round(x, 2) for x in notas})
    out = []
    for n in range(minimo, maximo + 1):
        posibles = {nota_truncada(k, n) for k in range(n + 1)}
        if all(any(abs(v - p) < 1e-9 for p in posibles) for v in distintas):
            out.append(n)
    return out


def tareas_de(nota: float, n: int) -> int | None:
    """Tareas resueltas que corresponden a ``nota`` con una tabla de ``n`` tareas; ``None`` si ninguna."""
    for k in range(n + 1):
        if abs(nota_truncada(k, n) - round(nota, 2)) < 1e-9:
            return k
    return None


def mejor_de(m: int, n: int, p: float) -> float:
    """Tareas esperadas del mejor de ``m`` envíos iguales e independientes, cada uno Binomial(n, p)."""
    acumulada = 0.0
    esperado = 0.0
    previo = 0.0
    for k in range(n + 1):
        acumulada += math.comb(n, k) * p**k * (1 - p) ** (n - k)
        actual = min(1.0, acumulada) ** m
        esperado += k * (actual - previo)
        previo = actual
    return esperado


def resumir_tabla(filas: Sequence[dict[str, str]], n: int, equipo: str | None = None) -> dict[str, Any]:
    """Agregados de la tabla pública en tareas. No conserva nombres de equipos salvo el propio."""
    tareas = [tareas_de(float(f["Score"]), n) for f in filas]
    if any(t is None for t in tareas):
        raise RescateError(f"Hay notas que no corresponden a k/{n} truncado: revise el tamaño de la tabla.")
    ks = [int(t) for t in tareas if t is not None]
    conteo = Counter(ks)
    por_envios: dict[int, list[int]] = {}
    for fila, k in zip(filas, ks, strict=True):
        por_envios.setdefault(int(fila.get("SubmissionCount") or 0), []).append(k)
    media = statistics.fmean(ks)
    p = media / n
    primeros = por_envios.get(1, [])
    p_primero = statistics.fmean(primeros) / n if primeros else None
    resumen: dict[str, Any] = {
        "equipos": len(ks),
        "tareas_de_la_tabla": n,
        "valor_de_una_tarea": round(1 / n, 4),
        "equipos_por_tareas": {str(k): conteo[k] for k in sorted(conteo, reverse=True)},
        "mediana_tareas": statistics.median(ks),
        "media_tareas": round(media, 2),
        "desviacion_observada": round(statistics.pstdev(ks), 2),
        "desviacion_binomial_con_la_misma_media": round(math.sqrt(n * p * (1 - p)), 2),
        "media_por_numero_de_envios": {
            str(e): {"equipos": len(v), "media_tareas": round(statistics.fmean(v), 2)}
            for e, v in sorted(por_envios.items())
        },
    }
    if p_primero is not None:
        resumen["mejor_de_m_envios_iguales_esperado"] = {
            str(m): round(mejor_de(m, n, p_primero), 2) for m in (1, 2, 3, 4, 5, 6, 7)
        }
    if equipo:
        propia = next(
            (f for f in filas if equipo.lower() in f.get("TeamMemberUserNames", "").lower().split(",")), None
        )
        if propia is not None:
            k = tareas_de(float(propia["Score"]), n)
            resumen["equipo_propio"] = {
                "puesto": int(propia["Rank"]),
                "tareas": k,
                "envios": int(propia.get("SubmissionCount") or 0),
                "equipos_con_mas_tareas": sum(1 for x in ks if k is not None and x > k),
            }
    return resumen


def leer_tabla(zip_bytes: bytes) -> list[dict[str, str]]:
    """Filas del CSV que trae el zip de la tabla pública."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        nombres = [x for x in z.namelist() if x.endswith(".csv")]
        if not nombres:
            raise RescateError("El zip de la tabla no trae un CSV.")
        with z.open(nombres[0]) as fh:
            return list(csv.DictReader(io.TextIOWrapper(fh, encoding="utf-8-sig")))


def texto_del_log(crudo: str) -> str:
    """El log de un notebook como texto: Kaggle lo entrega como lista JSON de fragmentos."""
    try:
        trozos = json.loads(crudo)
    except json.JSONDecodeError:
        return crudo
    if not isinstance(trozos, list):
        return crudo
    return "".join(str(t.get("data", "")) for t in trozos if isinstance(t, dict))


# ---------------------------------------------------------------------------
# Red
# ---------------------------------------------------------------------------


def cabeceras_para(url: str, token: str) -> dict[str, str]:
    """El token solo viaja por https y solo a Kaggle; a cualquier otro host, la petición va sin él."""
    partes = urllib.parse.urlsplit(url)
    if partes.scheme != "https":
        raise RescateError("Solo se piden direcciones https.")
    if partes.hostname in HOSTS_CON_TOKEN:
        return {"Authorization": f"Bearer {token}"}
    return {}


class RedireccionSinToken(urllib.request.HTTPRedirectHandler):
    """Al seguir una redirección, el token no va a un host que no es Kaggle; sin https, no se sigue."""

    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> Any:
        nueva = super().redirect_request(req, fp, code, msg, headers, newurl)
        if nueva is not None:
            partes = urllib.parse.urlsplit(newurl)
            if partes.scheme != "https":
                raise RescateError("Kaggle redirigió a una dirección que no es https.")
            if partes.hostname not in HOSTS_CON_TOKEN:
                for nombre in [n for n in nueva.headers if n.lower() == "authorization"]:
                    del nueva.headers[nombre]
                nueva.unredirected_hdrs.pop("Authorization", None)
        return nueva


def pedir(ruta: str, token: str) -> bytes:
    url = ruta if ruta.startswith("http") else f"{API}/{ruta}"
    peticion = urllib.request.Request(url, headers=cabeceras_para(url, token))
    try:
        with urllib.request.build_opener(RedireccionSinToken).open(peticion, timeout=TOPE_S) as resp:
            return bytes(resp.read())
    except urllib.error.HTTPError as exc:
        raise RescateError(f"Kaggle respondió {exc.code} a {ruta.split('?')[0]}") from None
    except (urllib.error.URLError, TimeoutError, http.client.HTTPException) as exc:
        raise RescateError(f"Sin respuesta de Kaggle: {type(exc).__name__}") from None


def comprobar_destino_fuera_de_git(destino: Path) -> None:
    padre = destino
    while not padre.exists() and padre != padre.parent:
        padre = padre.parent
    try:
        dentro = subprocess.run(
            ["git", "-C", str(padre), "rev-parse", "--is-inside-work-tree"], capture_output=True, text=True
        )
    except OSError:
        return
    if dentro.returncode != 0:
        return
    ignorado = subprocess.run(["git", "-C", str(padre), "check-ignore", "-q", str(destino)])
    if ignorado.returncode != 0:
        raise RescateError("--destino está dentro de un repositorio git y no está ignorado.")


def nombre_que_cabe(carpeta: Path, nombre: str, tope: int = TOPE_RUTA) -> str:
    """Nombre en disco de un archivo de salida: el de Kaggle, o acortado con su huella si la ruta no cabe."""
    completo = f"salida__{nombre}"
    sobra = len(str(carpeta.resolve() / completo)) - tope
    if sobra <= 0:
        return completo
    sufijo = "".join(Path(nombre).suffixes[-2:])
    huella = hashlib.sha256(nombre.encode("utf-8")).hexdigest()[:10]
    base = nombre[: len(nombre) - len(sufijo)] if sufijo else nombre
    cabe = len(base) - sobra - len(huella) - 1
    if cabe < 0:
        raise RescateError(f"La ruta de salida no cabe en TOPE_RUTA ({tope}), ni sin la base del nombre.")
    return f"salida__{base[:cabe]}~{huella}{sufijo}"


def causa_de(exc: Exception) -> str:
    """La causa de un fallo sin la ruta ni la dirección: una ``OSError`` las trae en su texto."""
    if isinstance(exc, RescateError):
        return str(exc)
    if isinstance(exc, OSError):
        return f"{type(exc).__name__}: no se pudo guardar"
    return f"{type(exc).__name__}: respuesta de Kaggle ilegible"


CARPETAS_EXIGIDAS = frozenset({"logs", "traces"})
CARPETAS_OPCIONALES = ("patches", "test_outputs")
ARCHIVO_EXIGIDO = "task_results.jsonl"


def _partes_de(miembro: str) -> tuple[list[str], str]:
    """Carpetas y nombre de un miembro de zip, solo como texto: nada se toca en disco."""
    partes = miembro.replace("\\", "/").split("/")
    return partes[:-1], partes[-1]


def _conteo_vacio() -> dict[str, int]:
    return {
        "zips": 0,
        "zips_ilegibles": 0,
        "miembros_revisados": 0,
        "miembros_de_0_bytes": 0,
        "exigidos_de_0_bytes": 0,
        **{f"{c}_de_0_bytes": 0 for c in CARPETAS_OPCIONALES},
    }


def revisar_zip(ruta: Path, notebook: str, conteo: dict[str, int]) -> list[dict[str, str]]:
    """Revisa los miembros de un zip de salida sin extraer nada: solo lee ``infolist()``.

    Un miembro exigido (bajo ``logs/`` o ``traces/``, o ``task_results.jsonl``) de 0 bytes es un faltante,
    y un zip ilegible también. Los de ``patches/`` y ``test_outputs/`` de 0 bytes solo se cuentan. Si un
    miembro cuelga de varias carpetas conocidas, decide la más externa. Los nombres se comparan tal cual, con
    sus mayúsculas. Los zips
    son datos no confiables: un nombre absoluto o con ``..`` se trata como texto y no causa escritura alguna.
    """
    conteo["zips"] += 1
    try:
        with zipfile.ZipFile(ruta) as z:
            miembros = [(i.filename, i.file_size) for i in z.infolist() if not i.is_dir()]
    except (zipfile.BadZipFile, OSError, ValueError, EOFError, NotImplementedError):
        conteo["zips_ilegibles"] += 1
        return [{"notebook": notebook, "archivo": ruta.name, "miembro": "", "causa": "zip ilegible"}]
    faltantes: list[dict[str, str]] = []
    for nombre, tamano in miembros:
        conteo["miembros_revisados"] += 1
        if tamano != 0:
            continue
        conteo["miembros_de_0_bytes"] += 1
        carpetas, base = _partes_de(nombre)
        # Decide la carpeta conocida más externa: `patches/logs/x.diff` es un parche, no un log.
        conocida = next((c for c in carpetas if c in CARPETAS_EXIGIDAS or c in CARPETAS_OPCIONALES), None)
        if conocida in CARPETAS_EXIGIDAS or base == ARCHIVO_EXIGIDO:
            conteo["exigidos_de_0_bytes"] += 1
            causa = "miembro exigido de 0 bytes"
            faltantes.append({"notebook": notebook, "archivo": ruta.name, "miembro": nombre, "causa": causa})
        elif conocida is not None:
            conteo[f"{conocida}_de_0_bytes"] += 1
    return faltantes


def bajar_notebook(carpeta: Path, consulta: str, token: str) -> list[dict[str, str]]:
    """Baja un notebook a ``carpeta``. Devuelve los archivos de salida que no se pudieron guardar o que
    traen un miembro exigido vacío."""
    (carpeta / "estado.json").write_bytes(pedir(f"kernels/status?{consulta}", token))
    fuente = json.loads(pedir(f"kernels/pull?{consulta}", token))
    (carpeta / "metadatos.json").write_text(
        json.dumps(fuente.get("metadata", {}), ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (carpeta / "notebook.ipynb").write_text(str(fuente.get("blob", {}).get("source", "")), encoding="utf-8")
    salida = json.loads(pedir(f"kernels/output?{consulta}", token))
    (carpeta / "log.txt").write_text(texto_del_log(str(salida.get("log") or "")), encoding="utf-8")
    (carpeta / "log_crudo.json").write_text(str(salida.get("log") or ""), encoding="utf-8")
    guardados: list[dict[str, str]] = []
    faltantes: list[dict[str, str]] = []
    for archivo in salida.get("files") or []:
        nombre = Path(str(archivo.get("fileName") or "")).name
        if not nombre or not archivo.get("url"):
            continue
        try:
            en_disco = nombre_que_cabe(carpeta, nombre)
            (carpeta / en_disco).write_bytes(pedir(str(archivo["url"]), token))
        except (RescateError, OSError) as exc:
            faltantes.append({"notebook": carpeta.name, "archivo": nombre, "causa": causa_de(exc)})
            continue
        guardados.append({"archivo": en_disco, "nombre_en_kaggle": nombre})
        if en_disco.lower().endswith(".zip"):
            faltantes += revisar_zip(carpeta / en_disco, carpeta.name, _conteo_vacio())
    (carpeta / "salidas.json").write_text(
        json.dumps(guardados, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return faltantes


def _escribir_faltantes(destino: Path, faltantes: list[dict[str, str]]) -> None:
    """Se escribe tras cada notebook: una bajada que muere a medias no queda como completa."""
    texto = json.dumps(faltantes, ensure_ascii=False, indent=1)
    (destino / "faltantes.json").write_text(texto, encoding="utf-8")


def bajar(destino: Path, token: str, usuario: str | None) -> list[dict[str, str]]:
    """Baja envíos, tabla y, por cada notebook propio, estado, metadatos, log y archivos de salida.

    Devuelve lo que faltó, que también queda en ``faltantes.json``. Si fallan los envíos, la tabla o la
    lista de notebooks, lanza: sin eso no hay rescate.
    """
    envios = json.loads(pedir(f"competitions/submissions/list/{COMPETITION_SLUG}?page=1", token))
    (destino / "envios.json").write_text(json.dumps(envios, ensure_ascii=False, indent=1), encoding="utf-8")
    (destino / "tabla_publica.zip").write_bytes(
        pedir(f"competitions/{COMPETITION_SLUG}/leaderboard/download", token)
    )
    usuario = usuario or next((e.get("submittedByRef") for e in envios if e.get("submittedByRef")), None)
    if not usuario:
        return []
    (destino / "usuario.txt").write_text(usuario, encoding="utf-8")
    lista = json.loads(pedir(f"kernels/list?user={urllib.parse.quote(usuario)}&pageSize=100", token))
    (destino / "notebooks.json").write_text(json.dumps(lista, ensure_ascii=False, indent=1), encoding="utf-8")
    faltantes: list[dict[str, str]] = []
    for nb in lista:
        ref = str(nb.get("ref") or "")
        if "/" not in ref:
            continue
        slug = ref.split("/", 1)[1]
        carpeta = destino / "notebooks" / slug
        consulta = f"userName={urllib.parse.quote(usuario)}&kernelSlug={urllib.parse.quote(slug)}"
        try:
            carpeta.mkdir(parents=True, exist_ok=True)
            faltantes += bajar_notebook(carpeta, consulta, token)
        except (RescateError, OSError, ValueError, AttributeError) as exc:
            faltantes.append({"notebook": slug, "archivo": "", "causa": causa_de(exc)})
        _escribir_faltantes(destino, faltantes)
    _escribir_faltantes(destino, faltantes)
    return faltantes


def salidas_de(carpeta: Path) -> list[str]:
    """Nombres de los archivos de salida tal como estaban en Kaggle, aunque en disco estén acortados."""
    indice = carpeta / "salidas.json"
    if indice.is_file():
        return sorted(str(x["nombre_en_kaggle"]) for x in json.loads(indice.read_text(encoding="utf-8")))
    return sorted(p.name[8:] for p in carpeta.glob("salida__*"))


def resumir(destino: Path, n: int | None) -> dict[str, Any]:
    """Resumen de lo que hay en ``destino``: envíos propios, tabla en tareas y notebooks con su estado."""
    envios = json.loads((destino / "envios.json").read_text(encoding="utf-8"))
    filas = leer_tabla((destino / "tabla_publica.zip").read_bytes())
    notas = [float(f["Score"]) for f in filas]
    candidatos = tamanos_compatibles(notas)
    origen = "indicado con --tareas-tabla"
    if n is None:
        origen = "el menor de los compatibles; las tareas de cada nota dependen de este tamaño"
        if not candidatos:
            raise RescateError("Ningún tamaño de tabla explica las notas observadas.")
        n = candidatos[0]
    usuario_txt = destino / "usuario.txt"
    usuario = usuario_txt.read_text(encoding="utf-8").strip() if usuario_txt.exists() else None
    notebooks = []
    revision: list[dict[str, str]] = []
    for carpeta in sorted((destino / "notebooks").glob("*")) if (destino / "notebooks").is_dir() else []:
        if not (carpeta / "estado.json").is_file() or not (carpeta / "metadatos.json").is_file():
            continue  # notebook que no se alcanzó a bajar: está en faltantes.json
        estado = json.loads((carpeta / "estado.json").read_text(encoding="utf-8"))
        meta = json.loads((carpeta / "metadatos.json").read_text(encoding="utf-8"))
        entrada = {
            "notebook": carpeta.name,
            "estado": estado.get("status"),
            "version": meta.get("currentVersionNumber"),
            "maquina": meta.get("machineShape"),
            "privado": meta.get("isPrivate"),
            "lineas_de_log": (carpeta / "log.txt").read_text(encoding="utf-8").count("\n")
            if (carpeta / "log.txt").is_file()
            else None,
            "archivos_de_salida": salidas_de(carpeta),
        }
        conteo = _conteo_vacio()
        for zip_en_disco in sorted(carpeta.glob("salida__*.zip")):
            revision += revisar_zip(zip_en_disco, carpeta.name, conteo)
        if conteo["zips"]:
            entrada["revision_de_zips"] = conteo
        notebooks.append(entrada)
    faltantes = destino / "faltantes.json"
    en_disco: list[dict[str, str]] = (
        json.loads(faltantes.read_text(encoding="utf-8")) if faltantes.is_file() else []
    )
    # La revisión se rehace aquí también (es lo que hace --sin-red sobre una carpeta vieja) y no se escribe en
    # disco: lo que ya estaba en faltantes.json no se repite.
    incompleta = en_disco + [f for f in revision if f not in en_disco]
    return {
        "descarga_incompleta": incompleta,
        "tamanos_de_tabla_compatibles": candidatos,
        "tamano_de_tabla_usado": {"n": n, "origen": origen},
        "envios_propios": [
            {
                "ref": e.get("ref"),
                "fecha": e.get("date"),
                "estado": e.get("status"),
                "nota_publica": e.get("publicScore"),
                "tareas": tareas_de(float(e["publicScore"]), n) if e.get("publicScore") else None,
                "bytes_guardados_por_kaggle": e.get("totalBytes"),
            }
            for e in envios
        ],
        "tabla": resumir_tabla(filas, n, usuario),
        "notebooks": notebooks,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m scripts.kaggle_rescate", description=__doc__.split("\n")[0])
    p.add_argument("--destino", type=Path, required=True, help="Directorio fuera de git o ignorado")
    p.add_argument("--usuario", default=None, help="Usuario de Kaggle dueño de los notebooks")
    p.add_argument("--tareas-tabla", type=int, default=None, help="Tamaño de la tabla pública, si se conoce")
    p.add_argument("--sin-red", action="store_true", help="No baja nada: resume lo que ya está en --destino")
    args = p.parse_args(argv)
    try:
        comprobar_destino_fuera_de_git(args.destino)
        if not args.sin_red:
            token = os.environ.get("KAGGLE_API_TOKEN", "").strip()
            if not token:
                raise RescateError("Falta la variable KAGGLE_API_TOKEN.")
            carpeta = args.destino / datetime.now(UTC).strftime("%Y-%m-%dT%H%MZ")
            carpeta.mkdir(parents=True, exist_ok=False)
            try:
                bajar(carpeta, token, args.usuario)
            except RescateError as exc:
                print(f"KAGGLE NO RESPONDIÓ: {exc}", file=sys.stderr)
                return EXIT_RED
        else:
            carpeta = args.destino
        if not (carpeta / "envios.json").is_file() or not (carpeta / "tabla_publica.zip").is_file():
            raise RescateError("En el directorio no hay envios.json y tabla_publica.zip.")
        resumen = resumir(carpeta, args.tareas_tabla)
    except RescateError as exc:
        print(f"ENTRADA INVÁLIDA: {exc}", file=sys.stderr)
        return EXIT_ENTRADA
    print(json.dumps({"directorio": str(carpeta), **resumen}, ensure_ascii=False, indent=2))
    return EXIT_PARCIAL if resumen["descarga_incompleta"] else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
