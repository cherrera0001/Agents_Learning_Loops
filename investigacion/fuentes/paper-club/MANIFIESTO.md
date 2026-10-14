# Paper Club: manifiesto de la fuente

Lista: <https://youtube.com/playlist?list=PLQ-uHSnFig5ONK1tl_48m3zTtbRExLG_a>. Consultada el 2026-10-13,
entre las 22:34 y las 23:08 UTC, sin iniciar sesión.

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
| Subtítulos de YouTube | La pista de subtítulos automáticos de cada página (22:38 UTC) y, después, `yt-dlp` sobre un video, dos veces, la segunda con imitación de navegador | Las 7 pistas respondieron HTTP 429 y los dos intentos con `yt-dlp` también. **Ningún subtítulo abrió.** |
| Transcripciones publicadas | La API pública de Root Access, el sitio que dos descripciones enlazan como «Transcript»: su archivo (22 entradas) y cada entrada por su nombre (23:05:55 UTC, HTTP 200) | 3 transcripciones de Paper Club: dos enlazadas en la descripción y una tercera que la descripción no enlaza y que incrusta el mismo video. Los otros 4 videos no tienen entrada en ese archivo. |
| Obra de una charla sin enlace | Búsqueda por título en la API de arXiv, una por charla (23:07 UTC) | 1 obra encontrada, con un solo resultado y el ponente como primer autor. Otras dos búsquedas no dieron resultados: esas charlas no tienen ficha de obra. |

El texto completo de las transcripciones está en `investigacion/local/root-access/`, que git ignora: es
texto de terceros y no se republica. Los HTML descargados y los guiones de lectura tampoco se versionan.
Las fichas y el índice se generaron desde esos datos; lo escrito a mano son las notas de cada
transcripción, la frase de mecanismo, la de «en este repositorio», la medición local y el contraste.

## Los siete videos

| Ficha | Título | Duración | Obras con arXiv | Contenido |
|---|---|---|---|---|
| [`pc-v01`](fichas/pc-v01-xc2FTBGRSJo.md) | What If We Stopped Using GPUs? | 1:20:35 | 0 | `no_abierto` |
| [`pc-v02`](fichas/pc-v02-n9xKblqyQ28.md) | Why The Harness Matters More Than The Model | 1:00:11 | 0 | `no_abierto` |
| [`pc-v03`](fichas/pc-v03-IfoPg2QefF8.md) | Going In Deep On Data | 52:35 | 1, localizada por título | `abierto`: transcripción leída entera |
| [`pc-v04`](fichas/pc-v04-myDCd0hNqQU.md) | Why Robotics Still Isn't Solved - But Could Be Soon | 1:24:13 | 3 | `abierto`: leídas 2 de 5 charlas |
| [`pc-v05`](fichas/pc-v05-n8dz2FX0_uY.md) | Lessons From Training Composer At Cursor And Building Meta/Nvidia Compute Clusters | 1:16:25 | 2 | `abierto`: leídas 2 de 5 charlas |
| [`pc-v06`](fichas/pc-v06-3rWSvrFahIY.md) | Self-Play for LLMs, AI for Biology, Formal Verification, and More | 1:16:55 | 3 | `no_abierto` |
| [`pc-v07`](fichas/pc-v07-wE1ZgJdt4uM.md) | Inference, Diffusion, World Models, and More | 1:07:19 | 5 | `no_abierto` |

Todos los títulos terminan en «| YC Paper Club» en la página; aquí se omite por espacio y el índice lo
conserva.

**Límite que importa.** El video más cercano a este repositorio por su título, `pc-v02` (sobre el arnés
del agente), no trae ningún identificador, no tiene transcripción publicada y sus subtítulos no abrieron.
No aporta ninguna obra ni ningún mecanismo al índice: los títulos de sus capítulos no son fichas. Lo
mismo vale para `pc-v01`, y de `pc-v06` y `pc-v07` solo constan sus obras.

## Cierre del índice

Conteos de esta fuente (filas cuyo `id` empieza por `pc-`, más `yc-canal`):

| Conteo | Valor |
|---|---|
| Videos de la lista | 7 de 7 que la página declara |
| Videos con el contenido abierto | 3 (transcripción publicada); 4 `no_abierto` |
| De esos 3, leídos enteros | 1; de los otros dos se leyeron 2 de 5 charlas de cada uno |
| Papers con el identificador abierto | 14 de 14: 13 de las descripciones y 1 localizado por título (registro y resumen de arXiv; texto completo, 0) |
| Charlas con ficha propia | 3 |
| Filas de esta fuente | 26: 7 videos, 14 papers, 3 charlas y 2 reservadas |
| En océano | 26 de 26 |
| En biblioteca | 0 |
| Con un contraste propuesto | 6: 4 papers y 2 charlas |

Por qué todo está en océano: los 14 papers tienen el identificador abierto, pero `docs/results/` no mide
ninguno de sus mecanismos en el solver acotado ni en el kit del experimento con modelo; los videos y las
charlas no son obras con identificador; y las filas reservadas no se abrieron. Con la definición de
[`CONTRIBUTING.md`](../../../CONTRIBUTING.md#investigación-antes-del-experimento), una obra abierta y sin
medir aquí es océano.

## Mecanismos que el código no nombra

Comprobado con `git grep`, sin distinguir mayúsculas, del nombre de cada método y de sus términos: ninguna
coincidencia en archivos de texto fuera de esta área. Cada frase de «en este repositorio» comparte la idea
de la fuente y no la implementa: las obras entrenan un modelo, y aquí no se entrena ninguno. Ninguna cifra
de esas fuentes es un resultado de este repositorio.

Los tres primeros salieron de los resúmenes de arXiv; los tres últimos, de leer las transcripciones.

| Ficha | Mecanismo, y qué sería aquí | Qué medición local lo toca | Contraste que lo descartaría |
|---|---|---|---|
| `pc-p-2603.03596` | Memoria en dos escalas. Aquí: un texto corto con el enunciado y las etapas hechas, fuera de la compactación. | [`hallazgos.json`](../../../experiments/gemma_developer_agent/hallazgos.json), «compactacion_del_contexto» (medido). Mide la compactación del arnés, no este mecanismo. | En las mismas tareas, las sesiones que conservan el enunciado literal después de compactar no resuelven más que las que lo pierden. |
| `pc-p-2602.08167` | Quedarse con el razonamiento que predice la acción. Aquí: quitar de la instrucción del kit los pasos obligatorios que no distinguen las sesiones resueltas. | [`hallazgos.json`](../../../experiments/gemma_developer_agent/hallazgos.json): dos brazos propuestos y vetados en la vuelta 42; miden su costo, no si el paso distingue las sesiones resueltas. | En las trayectorias ya rescatadas, ningún paso que la instrucción pide aparece con frecuencia distinta en las sesiones resueltas y en las no resueltas. |
| `pc-p-2604.20209` | Un guía que puntúa la relevancia de un problema para los que faltan por resolver. Aquí: un juez de relevancia entre un registro de fallo ajeno y la tarea actual. | [`failure-transfer.md`](../../../docs/results/failure-transfer.md) (H7): mide el umbral de similitud, no un guía. | Sobre los pares de H7 con cambio, la puntuación del guía intercala los que ayudaron y los que dañaron. |
| `pc-v03-c1` | Un agente de validación que escribe pruebas para cada parche desde una especificación corta. Aquí: que la comprobación local del parche no la escriba el agente evaluado. | [`hallazgos.json`](../../../experiments/gemma_developer_agent/hallazgos.json), «reproductor_antes_de_editar» (descartado): mide la comprobación que escribe el propio agente. | Sobre el código sin arreglar, esas pruebas salen verdes con la misma frecuencia que el reproductor del agente. |
| `pc-v03-c2` | Filtrar las tareas que el modelo resuelve siempre o nunca. Aquí: elegir el conjunto local de tareas por su resultado en las pasadas de la base. | [`hallazgos.json`](../../../experiments/gemma_developer_agent/hallazgos.json), «potencia_del_diseno» (decidido): mide la potencia por número de tareas, no por cuáles. | En las pasadas repetidas de la base, los pares discordantes aparecen repartidos por todas las tareas. |
| `pc-p-2510.22037` | Una matriz de transferencia medida por pares y no simétrica. Aquí: medir la transferencia de un registro de fallo entre familias de tareas en los dos sentidos. | [`failure-transfer.md`](../../../docs/results/failure-transfer.md) (H7). No se comprobó si esa campaña guarda cada par en los dos sentidos. | En los pares de H7 con cambio, el efecto de A sobre B y el de B sobre A tienen siempre el mismo signo. |

El parecer de ejemplo, sobre el primero, está en [`parecer.md`](parecer.md).

## Lo que falta de esta fuente

- **Cuatro videos sin contenido**: `pc-v01`, `pc-v02`, `pc-v06` y `pc-v07`. Para abrirlos hace falta otra
  vía (otra red, la sesión de un navegador o transcribir el audio en local); ninguna se usó.
- **Seis charlas sin leer** de `pc-v04` y `pc-v05`, que ya están en la copia local.
- Dos filas reservadas en `no_abierto`: `yc-canal` (se listaron los nombres de las listas del canal y no se
  abrió ninguna otra) y `pc-otras-listas`.
