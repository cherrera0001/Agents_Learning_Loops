# Decisión de campaña C1: ingesta de lecturas y regla de parada

Escrito el 2026-10-14 a las 02:05 UTC, solo con archivos locales: no se leyó Kaggle, no se usó ninguna
credencial y no se envió nada. Compara el candidato C1 con la base razonada.

| Kit | Archivo | Tamaño | SHA-256 |
|---|---|---:|---|
| Base razonada | `submission_i_razona.zip` | 3 494 bytes | `65a0216007e19bf6b26ec1ae0386be06814e97a3d85f63636fb10053651a6763` |
| C1 | `submission_r1_c1_tres_cambios_6min.zip` | 2 980 bytes | `a038a38925d7f1cf34a09e425e66f4b5eaedef9481fee23efe3e33b2b2d0193f` |

Tamaños y huellas recalculados hoy sobre los dos archivos. C1 es un paquete de cambios y se evalúa como
paquete: nada de lo que sigue atribuye un resultado a una modificación suya.

## Fase 1: ingesta y control de identidad

**Hecho medido: no hay ninguna lectura de C1.** Se buscaron rescates y lecturas nuevos en la carpeta de
rescates del experimento, en la carpeta del caso y en la de descargas del equipo: los archivos más recientes
son las lecturas de las 00:34, 00:46 y 01:22 UTC del 2026-10-14, y ninguna trae un envío de C1.
`submissions/registry.json` tiene el zip de C1 en estado `prepared`: nunca se envió a la competencia. No
existen, por tanto, ni tres lecturas nuevas ni una cuarta.

| Lectura | Envío | Estado | Score | Tareas | Identidad confirmada | Comparable |
|---|---|---|---:|---:|---|---|
| C1, 1 a 4 | no existe | — | — | — | — | — |
| Otro kit | 57160374, del 2026-10-14 00:07 UTC | `pending` a las 01:22 UTC | sin score | — | No es C1: es el zip `aa0750f0…` | `NO_COMPARABLE` |

Lo único que C1 tiene es una sesión propia de 12 tareas del bloque R1 (5 resueltas, 297,2 s de media por
tarea). No es una lectura de la tabla y no entra en la regla.

**Lecturas de la base**, del `envios.json` del rescate `2026-10-13T2337Z`:

| Lectura | Envío | Fecha (UTC) | Estado | Score | Tareas | Conjunto de ruedas del arnés publicado en esa fecha |
|---|---|---|---|---:|---:|---|
| Base 1 | 56895202 | 2026-10-07 00:26 | `complete` | 0,08 | 5 | El anterior al cambio del 2026-10-09 |
| Base 2 | 56916129 | 2026-10-07 16:25 | `complete` | 0,13 | 8 | El anterior al cambio del 2026-10-09 |
| Base 3 | 57098570 | 2026-10-12 06:46 | `complete` | 0,13 | 8 | El del 2026-10-09, antes de la republicación del 2026-10-12 19:51 |

- **Número de tareas de la tabla.** El analista de datos del concilio 48 dedujo 58 del conjunto de notas de la
  tabla pública entera. Con solo nuestras cinco notas, y con la nota truncada a dos decimales, 58 y 60 son
  los dos compatibles; con 58, las notas 0,08 y 0,13 son 5 y 8 tareas. La tabla no se volvió a leer hoy.
- **Versión del arnés.** No se sabe con qué ruedas puntúa el sistema; solo se sabe qué conjunto era público en
  cada fecha. El conjunto cambió el 2026-10-09 (`hallazgos.json`,
  `el_conjunto_de_ruedas_cambio_y_nadie_lo_comparaba`) y se volvió a publicar con otro contenido el 2026-10-12
  a las 19:51 UTC.
- **Lecturas limpias.** `hallazgos.json` (`ruido_entre_dos_envios_del_mismo_zip`) anota que las dos lecturas del
  2026-10-07 pasaron por un estado de error antes de puntuar.

## Fase 2: análisis

| Medida | C1 | Base |
|---|---:|---:|
| Lecturas válidas | 0 | 3 |
| Media de tareas | — | 7,0 |
| Mediana | — | 8 |
| Mínimo y máximo | — | 5 y 8 |
| Diferencia de medias contra la base | no calculable | — |

- **Hecho medido.** C1 no tiene lecturas. La base tiene tres, repartidas en dos estados distintos del conjunto
  de ruedas, y ninguna es posterior a la republicación del 2026-10-12 19:51 UTC, que es el estado en que
  puntuaría hoy una lectura de C1. Dos de las tres pasaron por un estado de error.
- **Inferencia.** Una diferencia entre lecturas futuras de C1 y la media de 7,0 mezclaría el efecto del kit con
  el del arnés. No está medido cuánto mueve el arnés la nota de un mismo zip; sí está medido en local que el
  cambio de ruedas altera lo que el kit pide al servidor (`hallazgos.json`,
  `con_el_arnes_nuevo_el_kit_de_base_razona`).
- **Decisión.** La regla predefinida no se aplica: no hay ninguna observación de C1 que meter en ella, y la
  base contra la que compararía no cumple la condición de comparabilidad que la propia regla exige.

## Fase 3: la cuarta lectura

No se ha enviado ninguna lectura de C1. La cuarta no se recomienda: no hay tres primeras.

## Veredicto

`CAMPAÑA NO COMPARABLE; REQUIERE REINICIO CONTROLADO`

**Estrategia posterior.** La estrategia vigente después de esta decisión, con C1 como respaldo del envío del
día 15, está en [`estrategia_concilio_50.md`](estrategia_concilio_50.md).

**Única acción siguiente.** Que el dueño decida el envío de la primera lectura de C1 (el zip de la tabla de
arriba, sin tocar), alternando después un día C1 y un día la base, para que las dos series se lean sobre el
mismo arnés; la regla se aplica entonces a las lecturas de C1 contra las lecturas nuevas de la base.
