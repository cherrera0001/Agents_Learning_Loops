# Paper Club: manifiesto de la fuente

Lista: <https://youtube.com/playlist?list=PLQ-uHSnFig5ONK1tl_48m3zTtbRExLG_a>. Consultada el 2026-10-13,
entre las 22:34 y las 22:39 UTC, sin iniciar sesión.

La página dice de sí misma: título «Paper Club», «by Y Combinator», «7 videos», última actualización
«Oct 2, 2026».

## Método de cada ítem

| Qué | Método | Resultado |
|---|---|---|
| Lista, primera lectura | Herramienta de lectura web sobre la URL de la lista | Solo el título «Paper Club - YouTube» y el menú del sitio. **Cero entradas de video.** Coincide con la lectura anterior a este PR. |
| Lista, segunda lectura | Descarga del HTML con `curl` y cabecera de navegador (22:34:12 UTC; HTTP 200, 966 858 bytes, SHA-256 `512ff550…74eebc0`) y lectura del bloque de datos `ytInitialData` que la página trae incrustado | 7 entradas de tipo video, cada una con identificador, título y duración. La página declara 7: el conteo coincide. Ninguna entrada salió de otra parte. |
| Cada video | Descarga de su página (`watch?v=<id>`, HTTP 200 las 7, terminadas a las 22:35:41 UTC) y lectura de `ytInitialPlayerResponse`: título, duración en segundos, fecha de publicación, descripción y lista de pistas de subtítulos | 7 de 7. El título de cada página coincide con el de la lista. |
| Identificadores | Búsqueda de `arxiv.org/abs/` y `arxiv.org/pdf/` y de DOI en el texto de cada descripción | 13 identificadores de arXiv distintos en 4 videos; ningún DOI. 3 videos no traen ninguno. |
| Cada obra | Una petición a la API de arXiv con los 13 identificadores (22:38:11 UTC; HTTP 200, 34 066 bytes, SHA-256 `2981dc6f…c7950287`) | 13 registros de 13. Autores, fecha, título y resumen se copiaron de ahí. El texto completo de ninguna se leyó. |
| Transcripciones | La pista de subtítulos automáticos de cada página (22:38 UTC) y el enlace «Transcript» de la descripción, donde lo hay | Las 7 pistas respondieron HTTP 429: ninguna abrió. Dos descripciones enlazan una transcripción en otro sitio; las dos abrieron (HTTP 200, con texto) y no se tomó nada de ellas. |

Los HTML descargados y los tres guiones de lectura quedaron en una carpeta ignorada por git; no se
versionan. Las fichas y el índice se generaron desde esos datos, no a mano: lo escrito a mano es la frase
de mecanismo, la de «en este repositorio», la medición local y el contraste.

## Los siete videos

| Ficha | Título | Duración | Obras con arXiv | Contenido |
|---|---|---|---|---|
| [`pc-v01`](fichas/pc-v01-xc2FTBGRSJo.md) | What If We Stopped Using GPUs? | 1:20:35 | 0 | `no_abierto` |
| [`pc-v02`](fichas/pc-v02-n9xKblqyQ28.md) | Why The Harness Matters More Than The Model | 1:00:11 | 0 | `no_abierto` |
| [`pc-v03`](fichas/pc-v03-IfoPg2QefF8.md) | Going In Deep On Data | 52:35 | 0 | `no_abierto` |
| [`pc-v04`](fichas/pc-v04-myDCd0hNqQU.md) | Why Robotics Still Isn't Solved - But Could Be Soon | 1:24:13 | 3 | `abierto` (transcripción enlazada) |
| [`pc-v05`](fichas/pc-v05-n8dz2FX0_uY.md) | Lessons From Training Composer At Cursor And Building Meta/Nvidia Compute Clusters | 1:16:25 | 2 | `abierto` (transcripción enlazada) |
| [`pc-v06`](fichas/pc-v06-3rWSvrFahIY.md) | Self-Play for LLMs, AI for Biology, Formal Verification, and More | 1:16:55 | 3 | `no_abierto` |
| [`pc-v07`](fichas/pc-v07-wE1ZgJdt4uM.md) | Inference, Diffusion, World Models, and More | 1:07:19 | 5 | `no_abierto` |

Todos los títulos terminan en «| YC Paper Club» en la página; aquí se omite por espacio y el índice lo
conserva.

**Límite que importa.** El video más cercano a este repositorio por su título, `pc-v02` (sobre el arnés
del agente), no trae ningún identificador y su contenido no abrió. No aporta ninguna obra ni ningún
mecanismo al índice: los títulos de sus capítulos no son fichas.

## Cierre del índice

| Conteo | Valor |
|---|---|
| Videos de la lista | 7 de 7 que la página declara |
| Videos con el contenido abierto | 2 (transcripción enlazada); 5 `no_abierto` |
| Papers con el identificador abierto | 13 de 13 (registro y resumen de arXiv; texto completo, 0) |
| Filas del índice | 22: 7 videos, 13 papers y 2 reservadas |
| Filas en océano | 22 de 22 |
| Filas en biblioteca | 0 |
| Papers con un contraste propuesto | 3 de 13; los otros 10 no tienen una frase de qué harían aquí |

Por qué las 22 filas están en océano: los 13 papers tienen el identificador abierto, pero `docs/results/` no
mide ninguno de sus mecanismos en el solver acotado ni en el kit del experimento con modelo; los 7 videos
no son obras con identificador; y las 2 filas reservadas no se abrieron. Con la definición de
[`CONTRIBUTING.md`](../../../CONTRIBUTING.md#investigación-antes-del-experimento), una obra abierta y sin
medir aquí es océano.

## Tres mecanismos que el código no nombra

Comprobado con `git grep`, sin distinguir mayúsculas, del nombre de cada método y de sus términos: ninguna
coincidencia en archivos de texto. Las tres frases de «en este repositorio» comparten la idea de la obra y
no la implementan: según sus resúmenes, las tres obras entrenan un modelo, y aquí no se entrena ninguno. Ninguna cifra de
esos papers es un resultado de este repositorio.

| Ficha | Mecanismo | Qué medición local lo toca | Contraste que lo descartaría |
|---|---|---|---|
| `pc-p-2603.03596` | Memoria en dos escalas: lo reciente comprimido y, aparte, un texto de horizonte largo con las etapas ya hechas. Aquí: un texto corto con el enunciado y las etapas hechas, fuera de la compactación. | [`hallazgos.json`](../../../experiments/gemma_developer_agent/hallazgos.json), «compactacion_del_contexto», estado `medido`. Mide la compactación del arnés, no este mecanismo. | En las mismas tareas, las sesiones que conservan el enunciado literal después de compactar no resuelven más que las que lo pierden. |
| `pc-p-2602.08167` | Quedarse con los pasos de razonamiento que predicen la acción correcta, en vez de una plantilla fija. Aquí: quitar de la instrucción del kit los pasos obligatorios que no distinguen las sesiones resueltas. | [`hallazgos.json`](../../../experiments/gemma_developer_agent/hallazgos.json): dos pasos obligatorios descartados en la vuelta 42, cada uno medido por separado. | En las trayectorias ya rescatadas, ningún paso que la instrucción pide aparece con frecuencia distinta en las sesiones resueltas y en las no resueltas de las mismas tareas. |
| `pc-p-2604.20209` | Un guía que puntúa cada problema sintético por su relevancia para los problemas sin resolver. Aquí: un juez de relevancia entre un registro de fallo ajeno y la tarea actual, en lugar del umbral de similitud. | [`failure-transfer.md`](../../../docs/results/failure-transfer.md) (H7): mide el umbral de similitud, no un guía. | Sobre los pares de H7 con cambio, la puntuación del guía intercala los que ayudaron y los que dañaron: ningún corte los separa. |

El parecer de ejemplo, sobre el primero de los tres, está en [`parecer.md`](parecer.md).

## Fuentes siguientes, sin procesar

El índice reserva dos filas en `no_abierto`: `yc-canal` (el canal de Y Combinator; la URL es la que la
página de la lista da como dueño y el canal no se abrió) y `pc-otras-listas` (otras listas de Paper Club:
ninguna se buscó ni se abrió, y por eso no lleva URL). Las abre el siguiente desafío.
