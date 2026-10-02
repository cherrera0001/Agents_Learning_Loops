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
   nombra, no se busca paper: se informa «el repositorio no nombra ese mecanismo».
2. **Abre el identificador.** DOI, ISBN o URL del editor, en esta sesión. Si no se abre, no se cita. Un
   registro de Crossref cuenta como DOI abierto y se anota como tal.
3. **Escribe la ficha**: autor, año, título, identificador abierto, fecha de apertura y la línea del
   código que nombra el mecanismo.
4. **La cita ilumina el mecanismo; no hereda la conclusión.** Junto a cada ficha va lo que este
   repositorio no demostró: el solver acotado reordena tres operadores ya escritos y no adquiere una
   habilidad nueva, y en H4 la memoria asociativa no superó al historial textual.
5. **Implementa o comparte la idea.** Si un texto nombra una obra (por ejemplo, HippoRAG), ábrela y di
   cuál de las dos cosas ocurre. El grafo de este repositorio es siembra, activación propagada, refuerzo
   acotado y decaimiento; no es el índice de ningún paper.
6. **Veto.** Se veta toda cita sin identificador abierto, toda cita cuyo mecanismo no esté en el código y
   toda frase que use el paper como prueba de un resultado propio.

## Fichas

Las fichas no viven en esta skill: van al registro fechado de cada revisión. El primero es
[`docs/entorno/revision-texto-publico-2026-10-02.md`](../../docs/entorno/revision-texto-publico-2026-10-02.md).

## Informe

Veredicto (apto, apto con cambios o no publicar), las fichas, las citas vetadas con su motivo y lo que no
se pudo abrir.
