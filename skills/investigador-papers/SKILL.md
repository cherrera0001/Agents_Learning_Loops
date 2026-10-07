---
name: investigador-papers
description: Localizar la obra que corresponde a un mecanismo que el código ya nombra y citarla solo si se abrió su identificador.
---

# Investigador de papers

> **Skill de entorno** ([glosario](../../docs/entorno/glosario.md), término 5). **No es un nodo Skill de
> la memoria**. Es personal de entorno para texto público: no es el agente de biblioteca ni el solver
> acotado, y no cambia el algoritmo.

## Fuente

- [`CONTRIBUTING.md`](../../CONTRIBUTING.md#revisión-de-un-texto-público), *Revisión de un texto
  público*: el procedimiento que esta skill proyecta. Lo demás son los textos que ese procedimiento aplica.
- [`README.md`](../../README.md) § 7.2, bloque «Qué no se demuestra», y
  [`docs/results/h4-associative-vs-history.md`](../../docs/results/h4-associative-vs-history.md)
  (*Alcance*): el límite de lo que una cita puede acompañar.
- [`specs/software_learning_protocol.md`](../../specs/software_learning_protocol.md) (*Metrics and
  falsification*): qué mide el laboratorio.
- Los mecanismos se toman del código, no del paper: `memory/consolidation.py` (regla hebbiana),
  `memory/associative.py` (activación propagada), `docs/results/h4-associative-vs-history.md`
  (transferencia negativa) y la condición C del protocolo (top-1 de lecciones).
- Episodio: ninguno registra este procedimiento como lección.

## Cuándo

Antes de publicar un texto (README, post, artículo) que nombre un mecanismo con su nombre de la literatura
o que cite una obra.

## Procedimiento

1. **Parte del código.** Localiza con Grep dónde nombra el repositorio el mecanismo. Si el código no lo
   nombra, se dice, y la ficha indica si el código implementa la obra o solo comparte la idea.
2. **Abre el identificador.** DOI, ISBN o URL del editor, en esta sesión. Si no se abre, no se cita. Un
   registro de Crossref cuenta como DOI abierto y se anota como tal.
3. **Escribe la ficha**: autor, año, título e identificador abierto, sin completar de memoria lo que la
   página no muestra.
4. **La cita ilumina el mecanismo; no hereda la conclusión.** Este repositorio no demostró que un agente
   adquiera una habilidad nueva: el solver acotado reordena tres operadores ya escritos, y en H4 la
   memoria asociativa no superó al historial textual.
5. **Implementa o comparte la idea.** Si un texto nombra una obra (por ejemplo, HippoRAG), ábrela y di
   cuál de las dos cosas ocurre. El grafo de este repositorio es siembra, activación propagada, refuerzo
   acotado y decaimiento; no es el índice de ningún paper.
6. **Veto.** Se veta toda cita sin identificador abierto y toda frase que use el paper como prueba de un
   resultado propio.

## Fichas

Las fichas no viven en esta skill: van al registro fechado de cada revisión. El primero es
[registro del 2026-10-02](../../docs/entorno/revision-texto-publico-2026-10-02.md).

## Reglas añadidas el 2026-10-07

- **Se abre el artefacto citado, no otro que lo cita.** Una cifra tomada de un tercero se marca «según
  [n]» hasta abrir el original.
- **Un notebook o una página viva lleva URL, versión, fecha de la última ejecución y fecha de consulta.**
  La fecha de publicación no sustituye a la de la versión leída.
- **«Informa» no es «reproducimos».** Una cifra ajena se atribuye a su autor; si las mediciones no se
  cruzaron unidad por unidad, dos conteos parecidos «son cercanos», no «coinciden».
- **Por qué difieren dos auditorías.** Antes de atribuir la diferencia a una sola causa, se lista en qué
  difieren: entorno, criterio de control e implementación del evaluador.
- **Reglas del destino.** El investigador lee las bases de la convocatoria (extensión, secciones, idioma,
  criterios, fecha) en su fuente y las entrega con la fecha de lectura.

## Citas en formato APA 7 y enlaces validados

Cuando el destino pide APA, o no fija otro estilo, la revisión de citas comprueba, obra por obra:

1. **Registro oficial.** Autores, año, título y fuente se copian del registro que da el identificador
   (API de arXiv, Crossref para un DOI), no de memoria ni de otro texto. Si la obra tiene versión
   publicada con DOI, se cita esa y no el preprint.
2. **Cita en el texto, autor–año.** Un autor: «(Miller, 2024)». Tres o más: «(Jimenez et al., 2023)». Sin
   corchetes numéricos.
3. **Lista de referencias.** Orden alfabético por primer apellido, sin numerar. Apellido e iniciales de
   cada autor; hasta 20 autores se listan todos; con 21 o más, los primeros 19, puntos suspensivos y el
   último. Título completo, en minúscula salvo la primera palabra, los nombres propios y la palabra tras
   dos puntos. Revista y volumen en cursiva; número entre paréntesis; páginas; DOI o URL completos.
4. **Artefactos vivos** (notebooks, páginas): autor, año, título, versión y fecha de la última ejecución,
   tipo entre corchetes, sitio, y «Retrieved <fecha>, from <URL>». La fecha de publicación no se inventa
   si no se conoce.
5. **Correspondencia.** Cada cita del texto tiene su entrada y cada entrada tiene al menos una cita. El
   año coincide en ambos lados.
6. **Enlaces.** Cada URL y cada DOI se pide de verdad y se anota el código de respuesta. Un 200 valida
   que existe; un 403 del editor con registro correcto en Crossref se anota como «identificador válido,
   texto no abierto». Un enlace validado no demuestra que la fuente respalde la frase.
7. **Coherencia con el resumen de la obra.** Para cada frase que atribuye algo a una obra, se lee su
   resumen y se anota la frase del resumen que la sostiene. Si el resumen de la versión vigente ya no
   dice lo que el texto le atribuye, se cambia la atribución o se quita la cita; no se cita una versión
   anterior para conservar una cifra.
8. **Lo que no se abrió, se dice.** El informe separa «registro verificado», «resumen leído» y «texto
   completo leído».

## Informe

Veredicto (apto, apto con cambios o no publicar), las fichas, las citas vetadas con su motivo y lo que no
se pudo abrir.
