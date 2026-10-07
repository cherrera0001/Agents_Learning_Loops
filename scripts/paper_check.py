"""Comprobaciones mecánicas de un manuscrito en Markdown antes de pedir una revisión.

Hace sin agentes lo que no necesita juicio: huella y extensión, resumen en un párrafo, correspondencia entre
citas autor–año y lista de referencias, orden alfabético, restos de citas numéricas, formato de las tablas y
cifras del resumen que no aparecen en el cuerpo. Con ``referencias`` consulta además el registro oficial de
cada obra (arXiv o Crossref) y pide cada enlace.

Uso:
    python -m scripts.paper_check comprobar <manuscrito.md> [--limite 3000]
    python -m scripts.paper_check referencias <manuscrito.md>

``comprobar`` no usa la red. Salida: 0 sin hallazgos, 1 con hallazgos, 2 si la entrada es inválida.
``referencias`` usa la red, solo lee, y sale con 0 si todo enlace respondió y todo registro coincide en año
y primer autor, 1 si no, 3 si no hubo red.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

EXIT_OK = 0
EXIT_HALLAZGOS = 1
EXIT_ENTRADA = 2
EXIT_RED = 3

TITULO_REFERENCIAS = ("## References", "## Referencias")
TITULO_RESUMEN = ("## Abstract", "## Resumen")
CITA = re.compile(
    r"\b([A-Z][A-Za-zÀ-ÿ'-]+)(?: et al\.| (?:and|&|y) [A-Z][A-Za-zÀ-ÿ'-]+)?(?:,\s|\s\()(\d{4})[a-z]?\)?"
)
NUMERICA = re.compile(r"\[\d+(?:\s*[,–-]\s*\d+)*\]")
ARXIV = re.compile(r"arXiv[:.](\d{4}\.\d{4,5})")
DOI = re.compile(r"https://doi\.org/(10\.[^\s)]+)")
URL = re.compile(r"https?://[^\s)>\]]+")


def palabras(texto: str) -> int:
    """Palabras separadas por espacios, sin contar las barras ni los filetes de las tablas."""
    return len(re.sub(r"\|", " ", re.sub(r"^\|[\s:|-]+\|$", " ", texto, flags=re.M)).split())


def partir(texto: str) -> dict[str, str]:
    """Cuerpo, resumen y referencias de un manuscrito. Lanza ``ValueError`` si falta una parte."""
    marca_ref = next((m for m in TITULO_REFERENCIAS if f"\n{m}\n" in texto), None)
    marca_res = next((m for m in TITULO_RESUMEN if f"\n{m}\n" in texto), None)
    if marca_ref is None or marca_res is None:
        raise ValueError("El manuscrito necesita una sección de resumen y una de referencias.")
    cuerpo, referencias = texto.split(f"\n{marca_ref}\n", 1)
    resto = cuerpo.split(f"\n{marca_res}\n", 1)[1]
    resumen = re.split(r"\n## ", resto, maxsplit=1)[0]
    return {"cuerpo": cuerpo, "resumen": resumen.strip(), "referencias": referencias.strip()}


def entradas(referencias: str) -> list[dict[str, str]]:
    """Una entrada por párrafo de la lista: primer apellido, año y texto."""
    out = []
    for parrafo in (p.strip() for p in referencias.split("\n\n")):
        if not parrafo:
            continue
        apellido = re.match(r"(?:\d+\.\s*)?([^,]+),", parrafo)
        anio = re.search(r"\((\d{4})[a-z]?(?:,[^)]*)?\)", parrafo)
        out.append(
            {
                "apellido": apellido.group(1).strip() if apellido else "",
                "anio": anio.group(1) if anio else "",
                "texto": parrafo,
            }
        )
    return out


def citas(cuerpo: str) -> set[tuple[str, str]]:
    return {(m.group(1), m.group(2)) for m in CITA.finditer(cuerpo)}


def tablas(cuerpo: str) -> list[dict[str, Any]]:
    """Cada bloque de filas con barras, con lo que tiene encima y debajo."""
    lineas = cuerpo.split("\n")
    out, i = [], 0
    while i < len(lineas):
        if lineas[i].startswith("|"):
            j = i
            while j < len(lineas) and lineas[j].startswith("|"):
                j += 1
            antes = [x for x in lineas[max(0, i - 5) : i] if x.strip()]
            despues = next((x for x in lineas[j : j + 3] if x.strip()), "")
            numero = next((x for x in antes if re.fullmatch(r"\*\*(Table|Tabla) \d+\*\*", x.strip())), None)
            titulo = next((x for x in antes if re.fullmatch(r"\*[^*].*[^*]\*", x.strip())), None)
            out.append(
                {
                    "linea": i + 1,
                    "numero": numero,
                    "titulo": titulo,
                    "nota": despues.strip().startswith(("*Note.*", "*Nota.*")),
                }
            )
            i = j
        else:
            i += 1
    return out


def comprobar(texto: str, limite: int) -> dict[str, Any]:
    partes = partir(texto)
    refs = entradas(partes["referencias"])
    en_texto = citas(partes["cuerpo"])
    en_lista = {(r["apellido"], r["anio"]) for r in refs}
    apellidos = [r["apellido"] for r in refs]
    cuerpo_sin_resumen = partes["cuerpo"].replace(partes["resumen"], "")
    numeros_resumen = sorted(set(re.findall(r"\d+(?:[.,]\d+)?", partes["resumen"])))
    hallazgos: list[str] = []
    total = palabras(texto)
    if total > limite:
        hallazgos.append(f"Extensión: {total} palabras, sobre el límite de {limite}.")
    parrafos = [p for p in partes["resumen"].split("\n\n") if p.strip()]
    if len(parrafos) != 1:
        hallazgos.append(f"El resumen tiene {len(parrafos)} párrafos; debe ser uno.")
    for cita in sorted(en_texto - en_lista):
        hallazgos.append(f"Cita sin entrada en la lista: {cita[0]} ({cita[1]}).")
    for ref in sorted(en_lista - en_texto):
        hallazgos.append(f"Entrada sin cita en el texto: {ref[0]} ({ref[1]}).")
    if apellidos != sorted(apellidos, key=str.casefold):
        hallazgos.append("La lista de referencias no está en orden alfabético.")
    if any(re.match(r"\d+\.\s", r["texto"]) for r in refs):
        hallazgos.append("La lista de referencias está numerada.")
    restos = NUMERICA.findall(partes["cuerpo"])
    if restos:
        hallazgos.append(f"Citas numéricas en el texto: {sorted(set(restos))}.")
    for t in tablas(partes["cuerpo"]):
        falta = [
            n
            for n, ok in (
                ("número en negrita", t["numero"]),
                ("título en cursiva", t["titulo"]),
                ("nota", t["nota"]),
            )
            if not ok
        ]
        if falta:
            hallazgos.append(f"Tabla en la línea {t['linea']}: falta {', '.join(falta)}.")
    ausentes = [
        n
        for n in numeros_resumen
        if not re.search(rf"(?<![\d.,]){re.escape(n)}(?![\d.,]\d)", cuerpo_sin_resumen)
    ]
    if ausentes:
        hallazgos.append(f"Cifras del resumen que no aparecen en el cuerpo: {ausentes}.")
    return {
        "sha256": hashlib.sha256(texto.encode("utf-8")).hexdigest(),
        "caracteres": len(texto),
        "palabras": {
            "total": total,
            "cuerpo": palabras(partes["cuerpo"]),
            "referencias": palabras(partes["referencias"]),
            "resumen": palabras(partes["resumen"]),
        },
        "referencias": len(refs),
        "citas_en_texto": len(en_texto),
        "tablas": len(tablas(partes["cuerpo"])),
        "hallazgos": hallazgos,
    }


def _pedir(url: str, tope: int = 30) -> tuple[int, bytes]:
    peticion = urllib.request.Request(url, headers={"User-Agent": "paper-check (lectura)"})
    try:
        with urllib.request.urlopen(peticion, timeout=tope) as resp:
            return int(resp.status), bytes(resp.read())
    except urllib.error.HTTPError as exc:
        return int(exc.code), b""


def registro_arxiv(identificador: str) -> dict[str, Any]:
    _, crudo = _pedir(f"https://export.arxiv.org/api/query?id_list={identificador}")
    xml = crudo.decode("utf-8", "replace")
    entrada = re.search(r"<entry>(.*?)</entry>", xml, re.S)
    if not entrada:
        return {}
    e = entrada.group(1)
    titulo = re.search(r"<title>(.*?)</title>", e, re.S)
    publicado = re.search(r"<published>(\d{4})", e)
    return {
        "titulo": re.sub(r"\s+", " ", titulo.group(1)).strip() if titulo else "",
        "anio": publicado.group(1) if publicado else "",
        "autores": re.findall(r"<name>(.*?)</name>", e),
        "doi_publicado": (re.search(r"<arxiv:doi[^>]*>(.*?)</arxiv:doi>", e) or [None, ""])[1],
    }


def registro_crossref(doi: str) -> dict[str, Any]:
    estado, crudo = _pedir(f"https://api.crossref.org/works/{doi}")
    if estado != 200:
        return {}
    m = json.loads(crudo)["message"]
    return {
        "titulo": (m.get("title") or [""])[0],
        "anio": str((m.get("issued", {}).get("date-parts") or [[""]])[0][0]),
        "autores": [f"{a.get('given', '')} {a.get('family', '')}".strip() for a in m.get("author", [])],
    }


def referencias(texto: str) -> dict[str, Any]:
    """Registro oficial y código de respuesta de cada entrada. Usa la red."""
    filas, problemas = [], []
    for ref in entradas(partir(texto)["referencias"]):
        arxiv, doi = ARXIV.search(ref["texto"]), DOI.search(ref["texto"])
        registro = (
            registro_arxiv(arxiv.group(1))
            if arxiv
            else registro_crossref(doi.group(1).rstrip("."))
            if doi
            else {}
        )
        enlaces = {u.rstrip("."): _pedir(u.rstrip("."))[0] for u in URL.findall(ref["texto"])}
        fila: dict[str, Any] = {
            "entrada": f"{ref['apellido']} ({ref['anio']})",
            "enlaces": enlaces,
            "registro": registro,
        }
        if registro:
            primer = registro["autores"][0].split()[-1] if registro["autores"] else ""
            if primer.casefold() != ref["apellido"].split()[-1].casefold():
                problemas.append(f"{fila['entrada']}: el primer autor del registro es {primer}.")
            n = len(registro["autores"])
            listados = ref["texto"].split("(")[0].count(".,") + 1
            if n <= 20 and listados != n and n > 1:
                problemas.append(
                    f"{fila['entrada']}: el registro tiene {n} autores y la entrada lista {listados}."
                )
            if n > 20 and ". . ." not in ref["texto"] and "…" not in ref["texto"]:
                problemas.append(
                    f"{fila['entrada']}: con {n} autores faltan los puntos suspensivos antes del último."
                )
            if registro.get("doi_publicado") and registro["doi_publicado"] not in ref["texto"]:
                problemas.append(
                    f"{fila['entrada']}: tiene versión publicada ({registro['doi_publicado']}); "
                    "APA pide citar esa."
                )
            if arxiv and registro["anio"] != ref["anio"]:
                problemas.append(f"{fila['entrada']}: el registro da el año {registro['anio']}.")
        elif arxiv or doi:
            problemas.append(f"{fila['entrada']}: el registro oficial no respondió.")
        for url, estado in enlaces.items():
            if estado not in (200, 403):
                problemas.append(f"{fila['entrada']}: {url} respondió {estado}.")
        filas.append(fila)
    return {"referencias": filas, "problemas": problemas}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m scripts.paper_check", description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("comprobar", help="Comprobaciones sin red")
    a.add_argument("manuscrito", type=Path)
    a.add_argument("--limite", type=int, default=3000, help="Máximo de palabras del destino")
    b = sub.add_parser("referencias", help="Registro oficial y enlaces de cada referencia (usa la red)")
    b.add_argument("manuscrito", type=Path)
    args = p.parse_args(argv)
    try:
        texto = args.manuscrito.read_text(encoding="utf-8")
        if args.cmd == "comprobar":
            informe = comprobar(texto, args.limite)
            print(json.dumps(informe, ensure_ascii=False, indent=2))
            return EXIT_HALLAZGOS if informe["hallazgos"] else EXIT_OK
        informe = referencias(texto)
    except (OSError, ValueError) as exc:
        if isinstance(exc, urllib.error.URLError):
            print(f"SIN RED: {type(exc).__name__}", file=sys.stderr)
            return EXIT_RED
        print(f"ENTRADA INVÁLIDA: {exc}", file=sys.stderr)
        return EXIT_ENTRADA
    print(json.dumps(informe, ensure_ascii=False, indent=2))
    return EXIT_HALLAZGOS if informe["problemas"] else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
