# Revisión de texto público · 2026-10-02

Registro de la primera revisión hecha con el procedimiento de
[`CONTRIBUTING.md`](../../CONTRIBUTING.md#revisión-de-un-texto-público). Es un registro fechado: no se
reescribe; una revisión nueva abre un archivo nuevo. No es evidencia del Experimento 0 ni del Experimento 1.

## Qué se revisó

| Escrito | Investigador | Redactor | Validador |
|---|---|---|---|
| A · `README.md`, encabezado y promesa | apto | apto con cambios | apto con cambios |
| B · post de LinkedIn del 2026-09-29, español e inglés (el inglés llegó cortado y no se completó) | no publicar tal cual | no publicar tal cual | no publicar |
| C · fragmento de artículo, tratado como borrador de debate | no publicar | no publicar como resultado | no publicar |

Según el orquestador, los tres roles corrieron como subagentes lanzados con las definiciones de
`.claude/agents/`. Es autoinformado: no se comprobó en la transcripción qué modelo ejecutó cada uno, y sus
informes no se conservaron en el repositorio. Este registro guarda las fichas, los vetos y el texto firmado.

## Fichas

Abiertas el 2026-10-02. «Registro de Crossref» significa que se abrió `api.crossref.org/works/<DOI>`.

| Mecanismo en el código | Obra | Identificador abierto | Estado |
|---|---|---|---|
| Regla hebbiana (`consolidation.py`, `hebbian`) | D. O. Hebb, *The Organization of Behavior*. La edición abierta es la de Psychology Press, 2005; el año de la primera edición no figura en la página abierta | DOI `10.4324/9781410612403`, ISBN 9781410612403 (página del editor y registro de Crossref) | citable como edición de 2005 |
| Activación propagada (`associative.py`) | A. M. Collins y E. F. Loftus (1975), «A spreading-activation theory of semantic processing», *Psychological Review* 82(6), 407-428 | DOI `10.1037/0033-295X.82.6.407` (registro de Crossref; la página de APA no cargó) | citable |
| Aprendizaje experiencial (el código no usa el término; la cadena experiencia → reflexión está en README § 7.2) | D. A. Kolb, *Experiential Learning: Experience as the Source of Learning and Development*, 2.ª ed., Pearson FT Press, 2014 | ISBN 9780133892406 (página del editor) | citable solo como origen del término |
| Transferencia negativa (`docs/results/h4-associative-vs-history.md`) | S. J. Pan y Q. Yang (2010), «A Survey on Transfer Learning», *IEEE TKDE* 22(10), 1345-1359 | DOI `10.1109/TKDE.2009.191` (registro de Crossref, sin resumen; la página de IEEE llegó vacía) | **pendiente**: no se leyó que trate la transferencia negativa |
| Selección de casos (condición C: top-1 de lecciones) | A. Aamodt y E. Plaza (1994), «Case-Based Reasoning: Foundational Issues, Methodological Variations, and System Approaches», *AI Communications* 7(1), 39-59 | DOI `10.3233/AIC-1994-7104` (registro de Crossref; el editor respondió 403) | citable |
| Ninguno: el repositorio no nombra HippoRAG | B. Jiménez Gutiérrez, Y. Shu, Y. Gu, M. Yasunaga e Y. Su (2024), «HippoRAG: Neurobiologically Inspired Long-Term Memory for Large Language Models», NeurIPS 2024 | arXiv `2405.14831` (página de arXiv) | solo como inspiración declarada; su resumen describe Personalized PageRank, que este código no implementa |

Sobre HippoRAG solo se leyó el resumen de la página de arXiv, no el PDF.

## Vetos concretos

| Frase | Por qué | Fuente |
|---|---|---|
| Una lección se promueve a skill, como si ya ocurriera | `promoted_to_skill` sigue sin implementarse | Protocolo: «Skill promotion and contradiction resolution remain future work»; [glosario](glosario.md), término 4 |
| El siguiente paso es probar transferencia en software real | El Experimento 1 ya la probó, y H4 no se sostiene | README § 7.2; [`h4`](../results/h4-associative-vs-history.md) |
| «El MemoryGraph resuelve» la falta de coincidencia léxica en L3–L5 | En las tareas con señuelo la clave era léxica y el grafo citó el señuelo igual que el historial | `h4`, *Datos* e *Interpretación* 1 |
| «El aprendizaje altera positivamente las decisiones», como hecho general | En los señuelos las empeoró | `h4`, *Interpretación* 2 |
| DEPRECATED o SUPERSEDED como protocolo ya activo | El protocolo sí representa la acción: «UPDATE, MERGE and DEPRECATE are representable but explicitly rejected until implemented». Se puede escribir y se rechaza; no está activa. SUPERSEDED no figura en el protocolo | [`specs/software_learning_protocol.md`](../../specs/software_learning_protocol.md), párrafo de las acciones de memoria (ADD, IGNORE) |
| KV prefix caching, NRNE o un contexto partido en prefijo y sufijo, como arquitectura del repositorio | No están en este código. Como debate, se marcan «pregunta abierta» | Grep sin resultados en `src/` y `specs/` |
| LG como diferencia de probabilidades de éxito | `LearningGain` es `metric(memoria) − metric(sin memoria)` | Protocolo, *Metrics and falsification* |

Además, en B se vetó «medir … tokens y costo» (los recibos no los registran) y «el siguiente paso es probar
transferencia entre problemas reales de software». En C, «el RAG vectorial colapsa en L3–L5» no tiene fuente:
el repositorio no incluye una línea base vectorial.

## Texto firmado

Según el orquestador, el validador leyó este texto entero, en esta versión, contó 1.297 caracteres y no
vetó ninguna frase, después de vetar dos versiones anteriores: una decía «0 fallos repetidos» sin el fallo
del escenario de dominio cruzado y otra no decía que el conteo era con memoria. El número de caracteres se
puede volver a contar sobre el bloque siguiente; lo demás es autoinformado. No se publicó desde este
repositorio.

```text
Estoy construyendo Agents Learning Loops, un experimento abierto sobre si un agente puede evitar repetir un error cuya causa ya observó. Acepto críticas.

Qué hay: una memoria asociativa en grafo. Tras un fallo se guarda la evidencia y una lección, y al reintentar se recupera por activación propagada, con refuerzo acotado y decaimiento.

Qué se midió: en un experimento simulado con una semilla, con memoria hubo 0 fallos repetidos en tres de los cuatro escenarios (en el cuarto, de dominio cruzado, hubo 1). En una aplicación de software, con un solver acotado (tres operadores de reparación escritos a mano, sin modelos de lenguaje) y 9 tareas, el éxito final fue igual con y sin memoria. En las tareas de transferencia originales hicieron falta 1,0 intentos de media con memoria, frente a 2,0 sin ella, con pistas léxicas en el texto; el historial textual simple empató con el grafo.

Lo que salió peor: en tareas con un señuelo, el éxito al primer intento fue 6/18 sin memoria y 0/18 con historial y con grafo. Las dos memorias empeoraron el primer intento.

No quedó demostrado: ninguna ventaja del grafo sobre el historial, ni transferencia con agentes de lenguaje, ni inferencia estadística. No se midieron tokens ni costo.

Código y recibos: github.com/cherrera0001/Agents_Learning_Loops
```
