# Diagnóstico del envío fallido y réplicas de la condición 7 (#103)

Fecha: 2026-10-16. Rama: `exp/kaggle-c7-replicates`. Solo lectura sobre Kaggle: no se envió ni subió
nada; no se tocó `eval_config.yaml` del kit ni la tabla. Paquete de réplicas:
[`../replicas_c7`](../replicas_c7) (notebook verificado por `kaggle_preflight`, sin GPU).

## Tarea 1 · La causa exacta del error del tercer envío

El envío que llevaba la condición 7 (razonamiento, 60 llamadas, 4,5 min; zip `65a02160…`) es el
Kaggle **56895202**, enviado 2026-10-07 00:26 UTC (`submissions/registry.json`, sub-005). Su réplica
del mismo zip es el 56916129 (sub-006, "reenvío tras error de sistema"). Las lecturas guardadas por
`scripts/kaggle_rescate.py` (`data/rescate_kaggle/*/envios.json`, carpeta ignorada) dicen:

| Ref. | Lecturas guardadas (UTC) | Nota final |
|---|---|---|
| 56895202 | `pending` 10-07 02:13 → `error` 10-08 21:13 → `complete` 10-08 21:37 | 0,08 |
| 56916129 | `error` 10-08 21:13, 21:37, 21:41, 22:17, 22:31 → `complete` 10-09 13:42 | 0,13 |

**La causa exacta, con el texto que Kaggle dio:**

- **56916129**: `errorDescription` = **«A system error. Please try resubmitting to resolve the error
  and contact Kaggle Support if it persists.»** — idéntico en las cinco lecturas del 10-08. Es el
  mensaje genérico de fallo de la plataforma: sin traza, sin tarea culpable, sin nada del contenido
  del zip. Kaggle pide reenviar y contactar a soporte.
- **56895202**: `errorDescription` **vacío** (`hasErrorDescription: false`) en su lectura `error`
  (10-08 21:13). Kaggle ni siquiera dio mensaje para este.

**Lectura.** El error fue de infraestructura del lado de Kaggle, no del envío: el mismo zip pasó por
el estado, se recuperó solo y puntuó dos veces (0,08 y 0,13). Que las notas difieran entre reenvíos
es el ruido de la tabla, no un efecto del error. Corrección respecto de la foto del README (estado
del 2026-10-07 15:55, «error y sin nota»): hoy consta que ambos envíos puntuaron tras recuperarse;
la corrección ya estaba anotada en `registry.json` (sub-005/006) y en
`docs/rescate_kaggle.md` («Los envíos con razonamiento, 2026-10-07 al 2026-10-09»). No hay logs del
puntuador accesibles: la API no da logs de envíos (solo de notebooks) ni deja bajar el archivo
guardado, así que nada más puede afirmarse sobre la causa raíz de la plataforma.

## Tarea 2 · Banda de ruido de la condición 7 — diagnóstico y paquete

**No se pudieron lanzar las tres réplicas, por dos bloqueos independientes, y no se lanzó nada
sustituto sin declararlo.**

### 2.1 Lo que está congelado y verificado

La configuración de la condición 7 es exactamente tres valores distintos del kit base enviado
(`registry.json` sub-005): `eval_config.yaml` con `max_tool_calls: 60` y `max_time_minutes: 4.5`, y
`configs/sampling.yaml` con `include_thoughts: true`. El directorio
`data/envios/i_razona/` (ignorado por git) reproduce el zip enviado **byte a byte**: su huella de
configuración (SHA-256 de los base64 de los seis archivos, ordenados y concatenados; fórmula del
manuscrito §«Data availability») es `0f52de0b84cb`, la publicada para la séptima condición; la del
kit base es `3b0e87556166`. Verificado localmente el 2026-10-16.

### 2.2 El bloqueo: las 19 tareas del 9/19 no se recuperan

El manuscrito (§4.3) define el conjunto —las 12 juzgadas resolubles de §4.4 + las 7 resueltas
antes— pero los identificadores solo vivían en los notebooks de las corridas del 2026-10-03 al 06,
**borrados antes del primer rescate** (2026-10-04 16:28 UTC ya solo lista `prueba-a-ajustada` y
`ensayo-a0-anfitrion` de esa época), y en la bitácora de predicciones que estuvo fuera del control
de versiones (manuscrito §3 «Deviations»; README §7.3). Búsqueda hecha aquí, sin encontrarlos:

- Todas las carpetas de rescate 2026-10-04 → 2026-10-15: los `salida__*.json` y los zips crudos con
  `task_results.jsonl` se escanearon completos. Pasadas rescatadas: 15 tareas (iteraciones 01–05),
  20 (`sesion-unica-a`: base, variante razonada, base), 13, 12, 8–11, 7, 3, 1–6 y 26 (ensayos).
  **Ninguna pasada de 19 tareas con 9 resueltas existe en disco.**
- `learning/episodes/`, `hallazgos.json`, borradores y manuscritos: publican solo conteos agregados
  (regla de no redistribución), sin identificadores.
- `ensayo_kaggle/ids_rich_provisional.txt` trae 20 identificadores rich, no el conjunto de 19.

Sin esa lista, «la misma medición» no es repeatable: cualquier sustituto mide otro objeto.
Alternativas y su costo están en `replicas_c7/tareas_c7.json`; todas requieren decisión del dueño y
declaración de desviación.

### 2.3 El segundo bloqueo: no hay cómputo ni camino de subida desde aquí

Esta máquina no tiene GPU; las réplicas exigen L4×4 en Kaggle (19 × 4,5 min + carga del modelo
medida hasta 1 142 s + márgenes ≈ 1,5–2,5 h por réplica; cuota semanal 30 h del dueño, consumo actual
sin medir — exige su sesión web). El CLI de Kaggle no está instalado ni autenticado en este entorno
y la subida corre con la cuenta del dueño (`kaggle kernels push`, orden que imprime el propio
preflight). No se subió nada.

### 2.4 Lo que quedó preparado y verificado (`replicas_c7/`)

- `notebook_c7.py` + `armar_notebook.py` → `notebook_c7.ipynb` + `kernel-metadata.json`: guardia de
  entradas (probada contra la estructura real por `kaggle_preflight`), guarda de versiones y
  SHA-256 de las ruedas del concilio 46 (0.2.11/0.2.13), armado del kit **con comprobación de huella
  contra `0f52de0b84cb` antes de cargar el modelo**, selección de tareas que se detiene antes de
  gastar cuota si faltan los identificadores, servidor vLLM con el patrón vigente
  (`discover_declared_models`, sustituto de lo eliminado en 0.2.11) y pasada secuencial con los
  cortes de seguridad del #182 (tope de sesión 150 min, tope duro por tarea 900 s, servidor caído,
  tarea colgada). La etiqueta de salida la pone el reloj: entre réplicas no cambia nada.
- `python -m scripts.kaggle_preflight comprobar … --tope-min 150 --ruedas …` sale con **0** («Se
  puede subir»): incluidos los 11 imports del arnés comprobados contra las ruedas reales leídas
  como texto. Lo único no verificado es la ejecución con GPU, que no existe en esta máquina.
- Análisis listo: `scripts/kaggle_replicas.py convertir` + `analizar` (recibos con hash de parche,
  frontera de fuga incluida) producen (a) resueltas por réplica, (b) tareas que cambian entre
  réplicas y pares, y (c) la lectura del 9/19 frente a la banda — una vez bajados los
  `task_results_<etiqueta>.jsonl` de las tres versiones.

### 2.5 Qué se necesita para terminar la Tarea 2

1. El dueño aporta los 19 identificadores (celda «tareas» o entrada `tareas_c7.json`), o aprueba un
   sustituto declarado como desviación.
2. Subir y correr tres veces con la cuenta del dueño (orden en el README del paquete; ~5–7 h de
   cuota L4×4 en total).
3. Bajar salidas y correr `kaggle_replicas convertir` + `analizar`; reportar (a), (b) y (c).
