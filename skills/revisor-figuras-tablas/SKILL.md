---
name: revisor-figuras-tablas
description: Comprobar que cada figura y cada tabla de un texto público corresponde al texto, a su fuente y a lo que hoy se hace, y que se lee sin ayuda.
---

# Revisor de figuras y tablas

> **Skill de entorno** ([glosario](../../docs/entorno/glosario.md), término 5). **No es un nodo Skill de
> la memoria**. Es personal de entorno para texto público: no es el agente de biblioteca ni el solver
> acotado, y no cambia el algoritmo.

## Fuente

- [`CONTRIBUTING.md`](../../CONTRIBUTING.md#revisión-de-un-texto-público), *Revisión de un texto
  público*.
- [`scripts/paper_figures.py`](../../scripts/paper_figures.py): generador de `docs/paper/figures/` y
  `docs/paper/tables/`. Se ejecuta con salida a un directorio temporal, nunca sobre el repositorio.
- [`skills/proteger-evidencia`](../proteger-evidencia/SKILL.md): el revisor lee `results/`; no lo modifica.
- Episodio: `learning/episodes/063-issue-148-staff-datos-y-figuras.json`. El manuscrito del 2026-10-04 se
  publicó junto a siete figuras de una versión anterior que no citaba, y con una tabla cuyo archivo
  versionado llevaba otro número y otras columnas.

## Cuándo

Antes de publicar un texto con al menos una figura, una tabla o un diagrama, y cada vez que cambie la
numeración de las tablas.

## Procedimiento

1. **Correspondencia.** Lista qué figuras y tablas cita el texto y cuáles existen versionadas. Una figura
   versionada que el texto no cita es huérfana; una citada que no existe es un veto.
2. **Numeración y columnas.** El número, el título y las columnas de cada tabla del texto coinciden con el
   archivo versionado y con lo que produce el generador.
3. **Celda a celda.** Cada valor dibujado o tabulado coincide con su fuente. Si la tabla tiene fila de
   totales, suma. Si una fila agrega una sola unidad, se fusiona con otra.
4. **Una medida por columna.** Una tabla no mezcla dos medidas bajo un mismo encabezado: tareas que
   cambian de resultado y cambio neto del total son columnas distintas.
5. **Denominadores a la vista.** «n de m», no solo porcentajes. Un mismo experimento no usa tres
   denominadores sin decirlo.
6. **Ejes y escala.** Ejes rotulados con unidad; los conteos empiezan en cero; nada truncado.
7. **Legibilidad.** Se distingue en blanco y negro y con daltonismo (tramas u orden de luminancia, no solo
   color); texto legible al ancho de columna; contraste del texto sobre relleno.
8. **Título.** Dice la variable y, si se puede, la conclusión; sin nombres internos (H4, EXP-nn, #58).
9. **Diagramas de proceso.** Describen lo que el texto dice que se hizo. Un diagrama con un paso retirado
   es un veto. Las flechas tienen sentido visible y cada caja está explicada.
10. **Lo que falta.** Si el resultado central no tiene figura ni tabla, descríbela en dos líneas: qué
    variable en cada eje y qué dato. No la dibujes.
11. **Material visual alrededor.** Páginas HTML, recorridos y README con cifras: lista las afirmaciones
    que la fuente ya corrigió, con archivo y línea.

## Formato de tabla cuando el destino pide APA 7

- Número de tabla en negrita en su propia línea («**Table 1**») y, en la línea siguiente, el título en
  cursiva y con mayúscula inicial en las palabras principales.
- Bajo la tabla, una nota («*Note.*») que diga qué cuenta cada celda, cuál es el denominador y cuántas
  corridas hay detrás de cada fila.
- Cada tabla se cita en el texto antes de aparecer o en el párrafo que la sigue.
- Lo que el formato fuente no permite comprobar (márgenes, interlineado, sangría francesa, paginación) se
  anota como no verificable, no como cumplido.

## Vetos obligatorios

- Una figura o tabla citada que no existe, o cuyo número no corresponde al archivo.
- Un valor que no coincide con su fuente.
- Un diagrama que muestra como vigente algo que el texto declara retirado.
- Una celda que identifique una tarea concreta donde las reglas piden solo agregados.

## Informe

- **Veredicto:** apto, apto con cambios o no publicar.
- **Tabla de correspondencia:** elemento, existe, citado, coincide con su fuente, problema.
- **Hallazgos** por gravedad, con archivo, ubicación y la corrección en una línea.
- **Figuras que faltan** y **afirmaciones desactualizadas** en el material visual.
- **Qué no pudiste ver** (por ejemplo, sin conversor para renderizar un SVG).

El revisor no edita archivos ni hace commit.
