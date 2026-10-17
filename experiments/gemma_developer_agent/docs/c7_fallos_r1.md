# Minería de fallos — réplica 1 de la condición 7 (c7_20261016T0459Z)

Análisis **offline** (sin GPU) de las 16 tareas `sin_parche` de la réplica 1. Alimenta el diseño de
la intervención «navegación-primero» (paquete `replicas_c7_nav/`, WIP). Rama
`exp/kaggle-c7-replicates`. Datos: `data/replicas_c7/replica_1/` (ignorado por git; los ids de
tarea ya estaban versionados en `replicas_c7/notebook_c7.py`).

## Trazabilidad

- Corrida: `cs4all/c7-replica-condicion-7` v6, huella `0f52de0b84cb`, 20/20 tareas, sin corte.
- Evidencia por tarea: `results/c7_20261016T0459Z/traces/trace_<id>.json` (pasos `thinking` con
  `tool_calls` registrados: nombre, argumentos, observación) + `c7-replica-condicion-7.log`
  (mensajes del arnés: «agent timed out», «submit_patch ok, patch_size …»).
- Los logs por tarea del arnés están vacíos (0 líneas); la agregación `salida__*.json` es binaria
  en esta campaña (`clase_fallo` solo distingue resuelta/sin_parche, notebook_c7.py:453-465), así
  que el modo de fallo se reconstruye de la traza + el log de kernel.
- «Relevante» = el archivo que el parche upstream (PR público de Textualize/rich; el id de tarea es
  el número de PR) tocó para esa issue. Verificado contra diffs públicos en 4/16 (grupo 1);
  juicio desde el enunciado en el resto (marcado como tal en el detalle interno).
- Límite: trazas pensadas para métricas, no para auditoría; los recuentos de llamadas de la
  agregación y los de la traza no siempre cuadran (±1-2 por llamadas fallidas).

## Corrección de premisa: `sin_parche` ≠ «no parche»

De las 16, solo **11** son genuinamente «sin parche». Las otras 5:

| tarea | qué pasó (hecho, del log/traza) |
|---|---|
| rich_3296 | `submit_patch` ok, patch_size 504 B, 1 archivo; no resuelta |
| rich_3675 | `submit_patch` ok, patch_size 723 B, 1 archivo; no resuelta |
| rich_3130 | editó `markdown.py`, verificó, `submit_patch` narrado (files_changed 2), pero `generated_patch` quedó **vacío** — sospecha: incluyó `repro.py` del scratch y falló la extracción |
| rich_3535 | narró edit+submit, pero el parche registrado fue **vacío**; su fix era además parcial vs upstream |
| rich_3772 | aplicó el fix y lo verificó («It worked!»), pero se puso a **revertirlo** para demostrar el fallo y el tiempo cortó antes de re-aplicar/submit |

Las dos primeras son decisión del verificador (el parche puede ser semánticamente distinto al
dorado); las tres últimas son **anomalías del pipeline de parche**, no de navegación.

## Tabla por tarea (16 sin_parche)

Leyenda — Relev.: «sí» = alcanzó archivo(es) relevantes; Fin: presupuesto = tope de ~270 s.

| tarea | problema (1 línea) | ¿llegó a relevante? | ¿editó? | fin | clase |
|---|---|---|---|---|---|
| rich_3535 | regex fast-path celdas ancho 1 | sí (`cells.py`) | narró, parche vacío | concluyó (anomalía) | llego_no_edito |
| rich_3772 | recursión infinita en `traceback.install` | sí (`traceback.py`) | sí, y verificó | presupuesto (auto-revert) | presupuesto_agotado |
| rich_4076 | preservar newlines (enunciado mínimo) | **no** (`ansi.py` dorado, jamás abierto) | no | presupuesto | no_llego_a_relevante |
| rich_3472 | dataclass con campo `init=False` | sí (`pretty.py`, leyó L1-300; bug en ~L781) | no | presupuesto | llego_no_edito |
| rich_3180 | CJK doble ancho al envolver | sí (`_wrap.py`,`cells.py`) | no | presupuesto (5 llamadas, 2 pasos de 119/135 s) | presupuesto_agotado |
| rich_3470 | `record` + `capture()` duplican | sí (`console.py`) | no | presupuesto | presupuesto_agotado |
| rich_4079 | código inline en tabla Markdown | sí (`markdown.py`, tarde) | no | presupuesto (≥6 llamadas malformadas) | presupuesto_agotado |
| rich_3130 | tabla Markdown pisa estilos | sí (`markdown.py`) | sí, verificó, submit vacío (anomalía) | concluyó | arnés: parche vacío |
| rich_3486 | ubicaciones finas de error (PEP 657) | sí (`traceback.py`) | no (scripts repro) | presupuesto | presupuesto_agotado |
| rich_3938 | fondo con `soft_wrap` | sí (`console.py`) | no | presupuesto (3 repros, greps repetidos) | presupuesto_agotado |
| rich_3061 | `expand_tabs` preserva estilos | sí (`text.py`), fix diseñado | no | presupuesto (re-lecturas tras diseñar fix) | presupuesto_agotado |
| rich_3521 | `Segment.split_cells` duplica control | sí (`segment.py`) | no | presupuesto (write/ejecución idénticos ×2) | bucle |
| rich_3782 | padding de `Syntax` | sí (`syntax.py`,`padding.py`,`measure.py`) | no | presupuesto (4 monólogos de 72–249 s) | presupuesto_agotado |
| rich_3296 | padding ignora `background_color` | sí (`syntax.py`) | sí, verificó, submit 504 B | concluyó | arnés: no resuelta |
| rich_3675 | env var `TTY_COMPATIBLE` | sí (`console.py`) | sí, verificó, submit 723 B | concluyó | arnés: no resuelta |
| rich_3953 | secuencias ZWJ | sí (`cells.py`), 2 fixes aplicados, repro ok | sí (sin submit) | presupuesto (deliberando sobre tests) | presupuesto_agotado |

## Clasificación con conteos

| clase | n | % de 16 | nota |
|---|---|---|---|
| presupuesto_agotado | 9 | 56 % | terminador literal: tope de ~270 s; en 8/9 ya había llegado al archivo relevante; causa raíz = sobre-exploración, verificación sin límite, monólogos de razonamiento de 70–250 s, o generación patológicamente lenta (3180) |
| arnés (parche enviado no resuelto / parche vacío) | 3 | 19 % | 3296, 3675 (verificador), 3130 (extracción); investigar pipeline de `generated_patch` |
| llego_no_edito | 2 | 13 % | 3535 (parche vacío + fix parcial), 3472 (leyó el archivo dorado por la región equivocada y lo descartó) |
| bucle | 1 | 6 % | 3521 (re-lectura/re-ejecución idéntica) |
| no_llego_a_relevante | 1 | 6 % | 4076 (enunciado sin pistas; nunca abrió `ansi.py`) |

## Lectura transversal (para la intervención)

1. **Herramientas de inteligencia de código: 0 usos en las 16 tareas.** Ni `search_similar_code`
   (1 uso aislado en 3061, con símbolo inexistente → 0 resultados), ni `get_code_neighbors`,
   ni `get_code_subgraph`. Toda la navegación fue `grep` de **término único**
   («newlines», «dataclass», «Table», «soft_wrap»…) + lectura secuencial de archivos enteros.
2. **Pero la búsqueda rara vez fue el cuello de botella:** en 13/16 el agente alcanzó el archivo
   relevante en la 1ª-3ª llamada. El fallo dominante es **convertir la ubicación en un edit dentro
   del presupuesto**: re-lecturas repetidas (≥6 tareas), greps idénticos repetidos tras fallar
   (≥3), llamadas malformadas que el tool ignora silenciosamente devolviendo líneas 1-150
   (backtick en ruta, `start_line` corrupto; ≥4 tareas, ~10 llamadas), y deliberación de
   verificación sin reloj (3953, 3782).
3. **Único fallo de navegación limpio: 4076** (y parcialmente 3472). Es exactamente el patrón que
   el procedimiento de navegación apunta a corregir: enunciado vago → grep genérico → leer
   archivos completos → morir. 1-2 de 16 es poca masa para la intervención tal cual.
4. **Riesgo para el A/B del lunes:** si la variante navegación-primero solo reordena la búsqueda,
   el contraste contra la condición 7 puede salir en el ruido (el cuello real es tiempo/razonamiento
   y anomalías de parche). Hipótesis alternativa que los datos sí apoyan: intervención de
   **conciencia de presupuesto** («quedan N llamadas / M s: pasa a editar ya») y **higiene de
   llamadas** (los errores silenciosos de `read_file` cuesten llamadas reales).

## Anomalías de arnés a investigar (antes de gastar más cuota)

- **A1.** `generated_patch` vacío tras submit declarado (3130, 3535): ¿inclusión de archivos
  scratch (`repro.py`) rompe la extracción? ¿dónde se pierde el parche entre el agente y el grader?
- **A2.** Recuento de llamadas de la agregación ≠ traza (±1-2; llamadas fallidas).
- **A3.** `clase_fallo` binario en esta campaña: no distingue «sin parche», «parche sin submit» y
  «parche no resuelto»; para el informe de ruido convendría re-clasificar las réplicas 2-3 con el
  log de kernel, no con la agregación.

## Addendum (2026-10-16): A1/A3 resueltas — el «parche vacío» era un atributo mal leído, no una pérdida

Investigación offline sobre la traza + el código del arnés 0.2.11 (rueda desempaquetada localmente,
`swegemma/models/task.py` y `swegemma/evaluate.py`). Cuatro hechos:

1. **Las 4 tareas de final normal enviaron parche y el arnés lo aceptó.** `submit_patch` devolvió
   `status: ok` con patch_size y files_changed: rich_3535 (465 B, 1 archivo), rich_3130
   (1.248 B, 2 — `markdown.py` + un `repro.py` scratch en la raíz), rich_3296 (504 B, 1),
   rich_3675 (723 B, 1). El parche se colecciona en el submit y lo aplica `verify_task`
   (`swegemma/harness/verification.py:470`); no hay evidencia de fallo de extracción.
2. **`clase_fallo` lee un atributo que no existe.** `TaskResult` (`swegemma/models/task.py:154`)
   define `agent_patch` (línea 162); no existe `generated_patch`. El `clase_fallo()` de
   `replicas_c7/notebook_c7.py:459` hace `getattr(res, "generated_patch", "")` → siempre `''` →
   toda tarea no resuelta sin flag de presupuesto cae en `sin_parche`. **El agregado de clases de
   esta campaña no distingue «sin parche» de «parche enviado no resuelto»** (tampoco pudo emitir
   `pruebas_fallan` nunca). Es un bug de nuestro notebook de réplica, no del arnés. A1 se
   re-diagnostica: anomalía de medición local, no de pipeline de parche.
3. **Re-clasificación con el log de kernel (A3):** 13 tareas con «agent timed out» (incluida
   rich_3043, que resolvió pese al aviso — el submit fue anterior al timeout); 4 con
   «completed without explicit submit_patch call and no working tree modifications»
   (rich_3472, rich_3180, rich_3521, rich_3782 → sin parche confirmado por el propio arnés);
   4 finales normales con submit ok (las del punto 1).
4. **Taxonomía corregida de las 16:** 4 «parche enviado y evaluado, no resuelto»
   (3535, 3130, 3296, 3675); 12 sin parche, todas contra el muro de 4,5 min: 10 sin editar
   (una en bucle: 3521; una que nunca llegó al archivo: 4076) y 2 con ediciones reales en el
   árbol nunca enviadas (3772 —se puso a revertir el fix ya verificado—; 3953 —deliberando sobre
   tests existentes—).

**¿Subcuenta 4/20?** No en parches evaluados: los 4 parches se evaluaron y perdieron. Sí en la
etiqueta: 16 `sin_parche` ≠ 16 «sin parche». Si alguno de los 4 «merecía» resolverse no es
determinable offline (los parches no se guardan, por la frontera de datos; haría falta re-correr
con captura de parche o recibos con hash).

**Addendum 2 (2026-10-17, concilio C7 Fase 4 — corrige el punto 3 de arriba):** rich_3043 **no
hizo `submit_patch` antes del timeout** — su traza tiene 0 llamadas `submit_patch` (verificado en
bytes por forense, QA y auditor del método, concilio 51 / vuelta 49,
[`c7_concilio_2026-10-17.md`](c7_concilio_2026-10-17.md)). Resolvió por **cosecha automática del
diff del árbol de trabajo al cortar el tiempo** (`agent_runner.py:1054-1097`): el parche se
colecciona del árbol aunque el agente no lo envíe. El hecho corrige el relato («el submit fue
anterior al timeout» es falso) y abre la clase «resuelta sin submit por cosecha» — el arnés
acepta entregas que el agente nunca confirmó, lo que importa para leer tiempos-límite ajenos y
para el contraste del lunes (contar la cosecha como entrega válida).

**Fix propuesto para réplicas 2-3 (decisión del dueño):** leer `res.agent_patch` en `clase_fallo`
y añadir `clase = "parche_no_resuelto"` cuando haya parche sin resolución, registrando también
`res.error`. No cambia la huella (es código del notebook, no del kit) pero rompe la identidad
estricta del paquete de réplica con la réplica 1; por eso queda pendiente y no aplicado.
