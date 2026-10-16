# Réplicas de la condición 7 (razonamiento, 60 llamadas, 4,5 min)

Paquete para repetir tres veces la séptima condición sobre las mismas 19 tareas del 9/19 original
y medir su banda de ruido. Diagnóstico completo y evidencia: [`../docs/c7_replicas.md`](../docs/c7_replicas.md).

**Estado: bloqueado en un dato que el dueño debe aportar.** La configuración está congelada y
verificada (huella `0f52de0b84cb`, idéntica al zip enviado que puntúo 0,08 y 0,13), pero los 19
identificadores de tareas no se recuperan desde el repositorio ni de los rescates: vivían en
notebooks borrados antes del primer rescate y en la bitácora de predicciones fuera de control de
versiones. Sin esa lista, correr «la misma medición» no es posible; el notebook se detiene antes
de gastar cuota si la lista falta.

## Qué hay aquí

| Archivo | Rol |
|---|---|
| `notebook_c7.py` | Guion del notebook (fuente de verdad). Seis celdas: guardia de entradas, guarda de versiones del arnés, armado del kit con comprobación de huella, selección de tareas, servidor vLLM, pasada de evaluación con cortes de seguridad (#182). |
| `armar_notebook.py` | Genera `notebook_c7.ipynb` y `kernel-metadata.json` desde el guion (inserta la guarda de versiones con los SHA-256 del concilio 46). |
| `tareas_c7.json` | Marcador del estado de recuperación de las 19 tareas y las dos vías de aportarlas. |
| `notebook_c7.ipynb`, `kernel-metadata.json` | Generados por `armar_notebook.py` (no editar a mano). |

## Cómo correr las tres réplicas (una vez aportados los identificadores)

1. Pegar los 19 identificadores en `IDS_TAREAS_C7` (celda «tareas» de `notebook_c7.py`) o subir
   `tareas_c7.json` con `ids_19` relleno como entrada del notebook. Regenerar:
   `python experiments/gemma_developer_agent/replicas_c7/armar_notebook.py`
2. Chequeo previo (sale 0 e imprime la orden exacta de subida; exige las ruedas del arnés bajadas
   en `../data/rescate_kaggle/instrumentos/arnes_2026-10-12_1951/ruedas`, las del ensayo del 2026-10-12
   con los SHA-256 del concilio 46):
   `python -m scripts.kaggle_preflight comprobar experiments/gemma_developer_agent/replicas_c7 --tope-min 150 --ruedas experiments/gemma_developer_agent/data/rescate_kaggle/instrumentos/arnes_2026-10-12_1951/ruedas`
3. Subir y correr tres veces, cambiando nada: la etiqueta de salida la pone el reloj
   (`c7_<fecha>T<hora>Z`). Requiere el CLI de Kaggle autenticado de la cuenta del dueño y cuota
   L4×4 (≈1,5–2,5 h por réplica: 19 × 4,5 min + carga del modelo medida hasta 19 min + márgenes;
   tope de sesión 150 min). `enable_internet: false`.
4. Bajar las salidas (`task_results_<etiqueta>.jsonl` y `salida__<etiqueta>.json` de cada
   versión) a `../data/replicas_c7/<etiqueta>/` (carpeta ignorada) y convertir a recibos:
   `python -m scripts.kaggle_replicas convertir --replica <etiqueta> --task-results <archivo> --receipts-dir <salida>`
   (los recibos guardan hash del parche, nunca el parche; la frontera de fuga la aplica el propio
   `kaggle_replicas`).
5. Análisis (tasas por réplica, tareas que cambian, pares, y dónde cae el 9/19 original):
   `python -m scripts.kaggle_replicas analizar --receipts-dir <salida> --subset <subconjunto con las 19>`

## Límites declarados

- La huella garantiza que la configuración es byte a byte la del envío (0f52de0b84cb); no garantiza
  que el arnés de Kaggle hoy se comporte como el del 2026-10-07: la guarda de versiones frena la
  ejecución si las ruedas no son las ensayadas (0.2.11/0.2.13, SHA-256 fijados), pero un cambio de
  conducta que conserve versiones y firmas no lo ve nadie (documentado en `scripts/kaggle_arnes.py`).
- Si el dueño no recupera las 19 tareas, cualquier sustituto cambia el objeto medido y debe
  declararse como desviación (opciones en `tareas_c7.json`).
- Las réplicas son deterministas en configuración, no en muestreo: la temperatura es 0,2 sin
  semilla (manuscrito §3), así que la variación entre réplicas es la banda que se quiere medir.
