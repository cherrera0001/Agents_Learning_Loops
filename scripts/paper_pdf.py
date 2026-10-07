"""Genera un PDF con formato APA 7 a partir del manuscrito en Markdown, sin cambiar una sola palabra.

Uso:
    python -m scripts.paper_pdf <manuscrito.md> <salida.pdf>

Necesita ``reportlab``; con ``pypdf`` instalado comprueba además que el PDF contiene las mismas palabras
que el manuscrito (salvo el título repetido y los números de página). Salida: 0 si se generó y coincide,
1 si el texto del PDF difiere, 2 si falta ``reportlab`` o la entrada es inválida.

Formato aplicado: carta, márgenes de 1 pulgada, Times New Roman 12, doble espacio, texto alineado a la
izquierda, sangría de primera línea de 0,5 pulgadas, número de página arriba a la derecha, portada, resumen en
página propia, título repetido al inicio del cuerpo, encabezados de nivel 1 centrados en negrita y de nivel 2
a la izquierda en negrita, tablas con número en negrita, título en cursiva, solo filetes horizontales y
nota al
pie, y referencias en página propia con sangría francesa.

Desviación declarada respecto de APA 7: se conservan los números de sección del manuscrito, porque el texto
los usa en sus referencias cruzadas y el PDF no debe diferir del texto firmado.
"""

from __future__ import annotations

import collections
import re
import sys
from pathlib import Path

from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

FUENTES = Path(r"C:\Windows\Fonts")
_TTF = {
    "TNR": "times.ttf",
    "TNR-B": "timesbd.ttf",
    "TNR-I": "timesi.ttf",
    "TNR-BI": "timesbi.ttf",
    "CourNew": "cour.ttf",
}
if all((FUENTES / f).is_file() for f in _TTF.values()):
    for nombre, archivo in _TTF.items():
        pdfmetrics.registerFont(TTFont(nombre, str(FUENTES / archivo)))
    pdfmetrics.registerFontFamily("TNR", normal="TNR", bold="TNR-B", italic="TNR-I", boldItalic="TNR-BI")
    F = {"n": "TNR", "b": "TNR-B", "i": "TNR-I", "mono": "CourNew"}
else:  # sin Times New Roman instalada: las Times incorporadas de PDF (solo Latin-1)
    F = {"n": "Times-Roman", "b": "Times-Bold", "i": "Times-Italic", "mono": "Courier"}

DOBLE = 24
RESUMEN = ("Abstract", "Resumen")
REFERENCIAS = ("References", "Referencias")
SUBTITULO = ("**Subtitle:**", "**Subtítulo:**")
NOTA = ("*Note.*", "*Nota.*")
base = ParagraphStyle("base", fontName=F["n"], fontSize=12, leading=DOBLE, alignment=TA_LEFT)
ESTILOS = {
    "parrafo": ParagraphStyle("parrafo", parent=base, firstLineIndent=0.5 * inch),
    "sin_sangria": ParagraphStyle("sin_sangria", parent=base),
    "centrado": ParagraphStyle("centrado", parent=base, alignment=TA_CENTER),
    "titulo": ParagraphStyle("titulo", parent=base, alignment=TA_CENTER, fontName=F["b"]),
    "h1": ParagraphStyle("h1", parent=base, alignment=TA_CENTER, fontName=F["b"], keepWithNext=True),
    "h2": ParagraphStyle("h2", parent=base, fontName=F["b"], keepWithNext=True),
    "cita": ParagraphStyle("cita", parent=base, leftIndent=0.5 * inch),
    "lista": ParagraphStyle("lista", parent=base, leftIndent=0.5 * inch, firstLineIndent=-0.25 * inch),
    "referencia": ParagraphStyle(
        "referencia", parent=base, leftIndent=0.5 * inch, firstLineIndent=-0.5 * inch
    ),
    "tabla_num": ParagraphStyle("tabla_num", parent=base, fontName=F["b"], keepWithNext=True),
    "tabla_titulo": ParagraphStyle("tabla_titulo", parent=base, fontName=F["i"], keepWithNext=True),
    "celda": ParagraphStyle("celda", parent=base, fontSize=10.5, leading=13),
    "celda_cab": ParagraphStyle("celda_cab", parent=base, fontSize=10.5, leading=13, alignment=TA_CENTER),
    "nota": ParagraphStyle("nota", parent=base, spaceBefore=4),
}


def en_linea(texto):
    """Markdown en línea a marcado de ReportLab: código, negrita, cursiva. No toca las palabras."""
    texto = texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    texto = re.sub(r"`([^`]+)`", rf'<font face="{F["mono"]}" size="11">\1</font>', texto)
    texto = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", texto)
    texto = re.sub(r"(?<![\w*])\*([^*]+)\*(?![\w*])", r"<i>\1</i>", texto)
    return texto


def tabla(filas_md, ancho):
    filas = [
        [c.strip() for c in f.strip().strip("|").split("|")]
        for f in filas_md
        if not re.match(r"^\|[\s:|-]+\|$", f.strip())
    ]
    n = len(filas[0])
    datos = [
        [Paragraph(en_linea(c), ESTILOS["celda_cab"] if i == 0 else ESTILOS["celda"]) for c in fila]
        for i, fila in enumerate(filas)
    ]
    largo = [max(len(f[j]) for f in filas) for j in range(n)]
    pesos = [max(12, min(n_car, 46)) for n_car in largo]
    anchos = [ancho * p / sum(pesos) for p in pesos]
    t = Table(datos, colWidths=anchos, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("LINEABOVE", (0, 0), (-1, 0), 0.8, "black"),
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, "black"),
                ("LINEBELOW", (0, -1), (-1, -1), 0.8, "black"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return t


def numero_de_pagina(lienzo, doc):
    lienzo.setFont(F["n"], 12)
    lienzo.drawRightString(letter[0] - inch, letter[1] - 0.5 * inch, str(doc.page))


def construir(origen, destino):
    lineas = Path(origen).read_text(encoding="utf-8").split("\n")
    ancho = letter[0] - 2 * inch
    bloques, i = [], 0
    while i < len(lineas):
        linea = lineas[i]
        if not linea.strip():
            i += 1
            continue
        if linea.startswith("|"):
            j = i
            while j < len(lineas) and lineas[j].startswith("|"):
                j += 1
            bloques.append(("tabla", lineas[i:j]))
            i = j
            continue
        bloques.append(("linea", linea))
        i += 1

    titulo = next(b[1][2:] for b in bloques if b[0] == "linea" and b[1].startswith("# "))
    subtitulo = next(
        b[1].split(":**", 1)[1].strip() for b in bloques if b[0] == "linea" and b[1].startswith(SUBTITULO)
    )
    k_abs = next(
        k
        for k, b in enumerate(bloques)
        if b[0] == "linea" and b[1].strip() in tuple(f"## {r}" for r in RESUMEN)
    )
    autor = next(b[1] for b in bloques[:k_abs] if b[0] == "linea" and not b[1].startswith(("# ", *SUBTITULO)))

    historia = [
        Spacer(1, 3 * DOBLE),
        Paragraph(en_linea(titulo), ESTILOS["titulo"]),
        Paragraph(en_linea(subtitulo), ESTILOS["centrado"]),
        Spacer(1, DOBLE),
        Paragraph(en_linea(autor), ESTILOS["centrado"]),
        PageBreak(),
    ]

    seccion, primer_h1_del_cuerpo = None, True
    for tipo, contenido in bloques[k_abs:]:
        if tipo == "tabla":
            historia.append(tabla(contenido, ancho))
            continue
        linea = contenido
        if linea.startswith("## "):
            nombre = linea[3:].strip()
            seccion = nombre
            if nombre in RESUMEN:
                historia.append(Paragraph(nombre, ESTILOS["h1"]))
            elif nombre in REFERENCIAS:
                historia += [PageBreak(), Paragraph(nombre, ESTILOS["h1"])]
            else:
                if primer_h1_del_cuerpo:
                    historia += [PageBreak(), Paragraph(en_linea(titulo), ESTILOS["titulo"])]
                    primer_h1_del_cuerpo = False
                historia.append(Paragraph(en_linea(nombre), ESTILOS["h1"]))
        elif linea.startswith("### "):
            historia.append(Paragraph(en_linea(linea[4:].strip()), ESTILOS["h2"]))
        elif re.fullmatch(r"\*\*(Table|Tabla) \d+\*\*", linea.strip()):
            historia.append(Paragraph(en_linea(linea.strip()), ESTILOS["tabla_num"]))
        elif re.fullmatch(r"\*[^*].*\*", linea.strip()) and not linea.strip().startswith(NOTA):
            historia.append(Paragraph(linea.strip()[1:-1].replace("&", "&amp;"), ESTILOS["tabla_titulo"]))
        elif linea.strip().startswith(NOTA):
            historia += [Paragraph(en_linea(linea.strip()), ESTILOS["nota"]), Spacer(1, 6)]
        elif linea.startswith("> "):
            historia.append(Paragraph(en_linea(linea[2:]), ESTILOS["cita"]))
        elif re.match(r"^\d+\. ", linea):
            historia.append(Paragraph(en_linea(linea), ESTILOS["lista"]))
        elif linea.startswith("- "):
            historia.append(Paragraph("•&nbsp;&nbsp;" + en_linea(linea[2:]), ESTILOS["lista"]))
        elif seccion in REFERENCIAS:
            historia.append(Paragraph(en_linea(linea), ESTILOS["referencia"]))
        elif seccion in RESUMEN:
            historia.append(Paragraph(en_linea(linea), ESTILOS["sin_sangria"]))
        else:
            historia.append(Paragraph(en_linea(linea), ESTILOS["parrafo"]))

    doc = SimpleDocTemplate(
        str(destino),
        pagesize=letter,
        leftMargin=inch,
        rightMargin=inch,
        topMargin=inch,
        bottomMargin=inch,
        title=titulo,
        author=autor,
        subject=subtitulo,
    )
    doc.build(historia, onFirstPage=numero_de_pagina, onLaterPages=numero_de_pagina)
    return doc.page


def _fichas(texto: str) -> collections.Counter[str]:
    return collections.Counter(re.sub(r"[^0-9a-zà-ÿ]+", " ", texto.lower()).split())


def diferencias(origen: Path, destino: Path) -> dict[str, int] | None:
    """Palabras del manuscrito que faltan en el PDF. ``None`` si ``pypdf`` no está instalado."""
    try:
        from pypdf import PdfReader
    except ImportError:
        return None
    fuente = re.sub(
        r"\*\*(Subtitle|Subtítulo):\*\*|[|*`#>]|---", " ", Path(origen).read_text(encoding="utf-8")
    )
    pdf = " ".join((p.extract_text() or "") for p in PdfReader(str(destino)).pages)
    a, b = _fichas(fuente), _fichas(pdf)
    # Un URL largo se parte entre dos líneas: sus trozos no cuentan como palabras perdidas.
    urls = _fichas(" ".join(re.findall(r"https?://\S+", fuente)))
    return {k: v - b[k] for k, v in a.items() if v > b[k] and k not in urls}


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2 or not Path(args[0]).is_file():
        print("Uso: python -m scripts.paper_pdf <manuscrito.md> <salida.pdf>", file=sys.stderr)
        return 2
    paginas = construir(args[0], args[1])
    faltan = diferencias(Path(args[0]), Path(args[1]))
    estado = faltan if faltan is not None else "sin comprobar (falta pypdf)"
    print(f"paginas: {paginas} | palabras que faltan en el PDF: {estado}")
    return 1 if faltan else 0


if __name__ == "__main__":
    raise SystemExit(main())
