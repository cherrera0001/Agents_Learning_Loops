# Root Access: manifiesto de la fuente

Sitio: <https://www.ycrootaccess.com>. Es donde Y Combinator publica las transcripciones que algunas
descripciones de Paper Club enlazan. Consultado el 2026-10-13, hasta las 23:08 UTC, sin iniciar sesión.

## Método

| Qué | Método | Resultado |
|---|---|---|
| Archivo del sitio | Una petición a su API pública de archivo | 22 entradas, del 2026-07-17 al 2026-08-26, todas con audiencia pública. No hay entradas posteriores en esa respuesta. |
| Cada entrada procesada | Una petición a la API por el nombre de la entrada (23:05:55 UTC, HTTP 200 las 5) y conversión de su HTML a Markdown, con cabecera de fuente, fecha, hora de consulta y SHA-256 de la respuesta | 5 archivos en `investigacion/local/root-access/`, que git ignora. |
| Obras de la entrada de ocho papers | Los enlaces «Paper» de la entrada; los 6 de arXiv, en una petición a su API (23:07 UTC; HTTP 200, 18 090 bytes, SHA-256 `bb6321ad…a4199cbc`); el de ACL Anthology, por su página; el de OpenReview, por su enlace | 6 registros de arXiv de 6. La página de ACL abrió y dio título, autores, fecha y DOI. OpenReview respondió HTTP 403: esa obra queda `no_abierto`. |

El texto completo no se versiona: es de terceros y no se republica. En el repositorio quedan las fichas,
con notas propias y el minuto de cada charla.

## Entradas

| Entrada | Qué es | Estado | Dónde |
|---|---|---|---|
| Expert Supervision, Diffusion, and Multilingual Scaling | Transcripción de `pc-v03` | Leída entera | [ficha del video](../paper-club/fichas/pc-v03-IfoPg2QefF8.md) |
| Memory, SimToolReal, and World Action Models | Transcripción de `pc-v04` | Leídas 2 de 5 charlas | [ficha del video](../paper-club/fichas/pc-v04-myDCd0hNqQU.md) |
| Multi-GPU Kernels, Intelligence per Watt, Heterogeneous Inference, and More | Transcripción de `pc-v05` | Leídas 2 de 5 charlas | [ficha del video](../paper-club/fichas/pc-v05-n8dz2FX0_uY.md) |
| Eight ML Papers, Explained by the Researchers Behind Them | Resumen de ocho trabajos, con sus enlaces | Leída entera | [`ra-ocho`](fichas/ra-ocho.md) |
| World Models: An intuitive introduction | Otra transcripción, de un video que no está en la lista | Descargada, **sin leer** | fila `ra-modelos-de-mundo`, `no_abierto` |
| Las otras 17 entradas del archivo | Entrevistas y charlas de otros temas | Sin procesar | fila `ra-archivo`, `no_abierto` |

## Cierre del índice

Conteos de esta fuente (filas cuyo `id` empieza por `ra-`):

| Conteo | Valor |
|---|---|
| Filas | 11: la entrada de ocho papers, sus 8 obras y 2 reservadas |
| Obras con el identificador abierto | 7 de 8: 6 por arXiv (registro y resumen) y 1 por ACL Anthology (registro, sin resumen) |
| Obras `no_abierto` | 1 (OpenReview, HTTP 403) |
| En océano | 11 de 11 |
| Con un contraste propuesto | 2 |

## Dos mecanismos que el código no nombra

Comprobado con `git grep` de sus términos: ninguna coincidencia fuera de esta área.

| Ficha | Mecanismo, y qué sería aquí | Qué medición local lo toca | Contraste que lo descartaría |
|---|---|---|---|
| `ra-p-2410.06209` | Un currículo por dificultad con una base que crece. Aquí: presentar al solver acotado las tareas de entrenamiento por dificultad creciente antes de consolidar lecciones. | Ninguna en `docs/results/`: ninguna campaña compara órdenes de las tareas de entrenamiento. | Con las mismas tareas y semillas, el orden por dificultad da el mismo `LearningGain` que el orden actual. |
| `ra-p-2025.findings-emnlp.1382` | Un diagnóstico barato de capacidades sueltas de planificación. Aquí: preguntar al modelo del kit sobre trayectorias ya rescatadas antes de gastar cuota. | Ninguna en `docs/results/`. | Las notas del diagnóstico no ordenan las condiciones ya medidas igual que sus corridas completas. |

La frase de mecanismo de la segunda sale del resumen que publica Root Access, no del resumen del paper,
que no se leyó.
