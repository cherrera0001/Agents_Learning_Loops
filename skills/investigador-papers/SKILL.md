---
name: investigador-papers
description: Localizar la obra que corresponde a un mecanismo que el código ya nombra y citarla solo si se abrió su identificador.
---

# Investigador de papers

> **Skill de entorno** ([glosario](../../docs/entorno/glosario.md), término 5). **No es un nodo Skill de
> la memoria**. Es personal de entorno para texto público: no es el agente de biblioteca ni el solver
> acotado, y no cambia el algoritmo.

## Fuente

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

## Fichas abiertas el 2026-10-02

| Mecanismo en el código | Obra | Identificador abierto | Estado |
|---|---|---|---|
| Regla hebbiana (`consolidation.py`, `hebbian`) | D. O. Hebb, *The Organization of Behavior*. La edición abierta es la de Psychology Press, 2005; el año de la primera edición no figura en la página abierta | DOI `10.4324/9781410612403`, ISBN 9781410612403 (página del editor y registro de Crossref) | citable como edición de 2005 |
| Activación propagada (`associative.py`) | A. M. Collins y E. F. Loftus (1975), «A spreading-activation theory of semantic processing», *Psychological Review* 82(6), 407-428 | DOI `10.1037/0033-295X.82.6.407` (registro de Crossref; la página de APA no cargó) | citable |
| Aprendizaje experiencial (el código no usa el término; la cadena experiencia → reflexión está en README § 7.2) | D. A. Kolb, *Experiential Learning: Experience as the Source of Learning and Development*, 2.ª ed., Pearson FT Press, 2014 | ISBN 9780133892406 (página del editor) | citable solo como origen del término |
| Transferencia negativa (`docs/results/h4-associative-vs-history.md`) | S. J. Pan y Q. Yang (2010), «A Survey on Transfer Learning», *IEEE TKDE* 22(10), 1345-1359 | DOI `10.1109/TKDE.2009.191` (registro de Crossref, sin resumen; la página de IEEE llegó vacía) | **pendiente**: no se leyó que trate la transferencia negativa |
| Selección de casos (condición C: top-1 de lecciones) | A. Aamodt y E. Plaza (1994), «Case-Based Reasoning: Foundational Issues, Methodological Variations, and System Approaches», *AI Communications* 7(1), 39-59 | DOI `10.3233/AIC-1994-7104` (registro de Crossref; el editor respondió 403) | citable |
| Ninguno: el repositorio no nombra HippoRAG | B. Jiménez Gutiérrez, Y. Shu, Y. Gu, M. Yasunaga e Y. Su (2024), «HippoRAG: Neurobiologically Inspired Long-Term Memory for Large Language Models», NeurIPS 2024 | arXiv `2405.14831` (página de arXiv) | solo como inspiración declarada; su resumen describe Personalized PageRank, que este código no implementa |

## Informe

Veredicto (apto, apto con cambios o no publicar), las fichas, las citas vetadas con su motivo y lo que no
se pudo abrir.
