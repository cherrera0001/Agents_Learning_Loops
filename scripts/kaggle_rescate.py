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

Salida: 0 si se bajó y resumió, 2 si la entrada es inválida o falta el token, 3 si Kaggle no respondió.
"""

from __future__ import annotations

import argparse
import csv
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

EXIT_OK = 0
EXIT_ENTRADA = 2
EXIT_RED = 3


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


def pedir(ruta: str, token: str) -> bytes:
    url = ruta if ruta.startswith("http") else f"{API}/{ruta}"
    peticion = urllib.request.Request(url, headers=cabeceras_para(url, token))
    try:
        with urllib.request.urlopen(peticion, timeout=TOPE_S) as resp:
            return bytes(resp.read())
    except urllib.error.HTTPError as exc:
        raise RescateError(f"Kaggle respondió {exc.code} a {ruta.split('?')[0]}") from None
    except (urllib.error.URLError, TimeoutError) as exc:
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


def bajar(destino: Path, token: str, usuario: str | None) -> None:
    """Baja envíos, tabla y, por cada notebook propio, estado, metadatos, log y archivos de salida."""
    envios = json.loads(pedir(f"competitions/submissions/list/{COMPETITION_SLUG}?page=1", token))
    (destino / "envios.json").write_text(json.dumps(envios, ensure_ascii=False, indent=1), encoding="utf-8")
    (destino / "tabla_publica.zip").write_bytes(
        pedir(f"competitions/{COMPETITION_SLUG}/leaderboard/download", token)
    )
    usuario = usuario or next((e.get("submittedByRef") for e in envios if e.get("submittedByRef")), None)
    if not usuario:
        return
    (destino / "usuario.txt").write_text(usuario, encoding="utf-8")
    lista = json.loads(pedir(f"kernels/list?user={urllib.parse.quote(usuario)}&pageSize=100", token))
    (destino / "notebooks.json").write_text(json.dumps(lista, ensure_ascii=False, indent=1), encoding="utf-8")
    for nb in lista:
        ref = str(nb.get("ref") or "")
        if "/" not in ref:
            continue
        slug = ref.split("/", 1)[1]
        carpeta = destino / "notebooks" / slug
        carpeta.mkdir(parents=True, exist_ok=True)
        consulta = f"userName={urllib.parse.quote(usuario)}&kernelSlug={urllib.parse.quote(slug)}"
        (carpeta / "estado.json").write_bytes(pedir(f"kernels/status?{consulta}", token))
        fuente = json.loads(pedir(f"kernels/pull?{consulta}", token))
        (carpeta / "metadatos.json").write_text(
            json.dumps(fuente.get("metadata", {}), ensure_ascii=False, indent=1), encoding="utf-8"
        )
        (carpeta / "notebook.ipynb").write_text(
            str(fuente.get("blob", {}).get("source", "")), encoding="utf-8"
        )
        salida = json.loads(pedir(f"kernels/output?{consulta}", token))
        (carpeta / "log.txt").write_text(texto_del_log(str(salida.get("log") or "")), encoding="utf-8")
        (carpeta / "log_crudo.json").write_text(str(salida.get("log") or ""), encoding="utf-8")
        for archivo in salida.get("files") or []:
            nombre = Path(str(archivo.get("fileName") or "")).name
            if nombre and archivo.get("url"):
                (carpeta / f"salida__{nombre}").write_bytes(pedir(str(archivo["url"]), token))


def resumir(destino: Path, n: int | None) -> dict[str, Any]:
    """Resumen de lo que hay en ``destino``: envíos propios, tabla en tareas y notebooks con su estado."""
    envios = json.loads((destino / "envios.json").read_text(encoding="utf-8"))
    filas = leer_tabla((destino / "tabla_publica.zip").read_bytes())
    notas = [float(f["Score"]) for f in filas]
    candidatos = tamanos_compatibles(notas)
    if n is None:
        if not candidatos:
            raise RescateError("Ningún tamaño de tabla explica las notas observadas.")
        n = candidatos[0]
    usuario_txt = destino / "usuario.txt"
    usuario = usuario_txt.read_text(encoding="utf-8").strip() if usuario_txt.exists() else None
    notebooks = []
    for carpeta in sorted((destino / "notebooks").glob("*")) if (destino / "notebooks").is_dir() else []:
        estado = json.loads((carpeta / "estado.json").read_text(encoding="utf-8"))
        meta = json.loads((carpeta / "metadatos.json").read_text(encoding="utf-8"))
        notebooks.append(
            {
                "notebook": carpeta.name,
                "estado": estado.get("status"),
                "version": meta.get("currentVersionNumber"),
                "maquina": meta.get("machineShape"),
                "privado": meta.get("isPrivate"),
                "lineas_de_log": (carpeta / "log.txt").read_text(encoding="utf-8").count("\n"),
                "archivos_de_salida": sorted(p.name[8:] for p in carpeta.glob("salida__*")),
            }
        )
    return {
        "tamanos_de_tabla_compatibles": candidatos,
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
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
