---
name: maquetar-apa
description: Generar el PDF en formato APA 7 de un manuscrito firmado, sin cambiar una palabra, y comprobar que el PDF dice lo mismo que la fuente.
---

# Maquetar en APA 7

> **Skill de entorno** ([glosario](../../docs/entorno/glosario.md), término 5). **No es un nodo Skill de
> la memoria**. No revisa el contenido: maqueta un texto que ya pasó por
> [`revisar-manuscrito`](../revisar-manuscrito/SKILL.md).

## Fuente

- [`scripts/paper_pdf.py`](../../scripts/paper_pdf.py): el generador. Necesita `reportlab`; con `pypdf`
  comprueba además el texto del PDF.
- [`skills/revisor-figuras-tablas`](../revisor-figuras-tablas/SKILL.md), *Formato de tabla cuando el
  destino pide APA 7*.
- Episodio: `learning/episodes/063-issue-148-staff-datos-y-figuras.json`. Markdown no tiene sangría
  francesa, interlineado ni paginación: «el manuscrito está en APA» solo se puede afirmar del PDF.

## Cuándo

Después de la firma del validador, cuando el destino acepta o pide un PDF. Cada cambio del manuscrito
obliga a generar el PDF otra vez.

## Lo que el manuscrito fuente debe traer

- Primera línea `# Título`; después `**Subtitle:** …`, la línea de autoría y `## Abstract`.
- Secciones con `## ` y subsecciones con `### `.
- Cada tabla: `**Table N**`, en la línea siguiente `*Título en Cursiva*`, las filas con barras, y debajo
  `*Note.* …`.
- Citas autor–año en el texto y `## References` con una entrada por párrafo, en orden alfabético.

## Procedimiento

1. Comprueba la fuente: `python -m scripts.paper_check comprobar <manuscrito>` sin hallazgos.
2. Genera: `python -m scripts.paper_pdf <manuscrito.md> <salida.pdf>`. Sale con 1 si alguna palabra del
   manuscrito falta en el PDF.
3. Mira al menos cuatro páginas renderizadas: portada, primera del cuerpo, una con tabla y la de
   referencias. Se busca texto cortado, tablas que se salen del margen y URL partidos de forma ilegible.
4. Anota junto al PDF la huella del manuscrito del que salió.

## Qué aplica el generador

Carta, márgenes de 1 pulgada, Times New Roman 12, doble espacio, texto alineado a la izquierda, sangría de
primera línea de 0,5 pulgadas, número de página arriba a la derecha, portada, resumen en página propia,
título repetido al inicio del cuerpo, encabezados de nivel 1 centrados en negrita y de nivel 2 a la
izquierda en negrita, tablas con solo filetes horizontales, y referencias en página propia con sangría
francesa.

## Desviaciones que hay que declarar

- **Números de sección.** APA no numera los encabezados. El generador conserva los del manuscrito para que
  el PDF no difiera del texto firmado. Si el destino exige APA estricto, se quitan en la fuente y se pide
  otra firma.
- **Afiliación, nota de autor y palabras clave.** El generador no las inventa; si la fuente no las trae, la
  portada sale sin ellas.
- **Sin Times New Roman instalada** el generador usa las Times incorporadas de PDF, que no cubren todos
  los caracteres.

## Informe

- Ruta del PDF, número de páginas, huella del manuscrito fuente y resultado de la comparación de texto.
- Páginas que se miraron y qué se vio.
- Desviaciones de APA que quedan.
