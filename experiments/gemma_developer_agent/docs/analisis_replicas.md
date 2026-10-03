# Análisis de réplicas de la línea base A

Ficha del comando `scripts/kaggle_replicas.py` (issue #103, parte del análisis). Se escribe y se mergea
**antes** de que exista ningún recibo real: fija cómo se leerá la evidencia. Este documento no afirma
ningún resultado; no hay datos todavía.

## Qué mide

Cuánto varía la condición A (kit oficial) contra sí misma al repetir la misma corrida sobre el mismo
subconjunto de tareas. Con eso se calcula qué diferencia entre dos condiciones no se distingue de ese
ruido. El script calcula y reporta; los umbrales de decisión se fijan en el pre-registro, no aquí.

La métrica de Kaggle es resueltas / total de tareas. Por eso **un fallo del agente es «no resuelta»**
(parche vacío, timeout o presupuesto del agente agotados, parche que no aplica, pruebas que fallan, se
cuelgan o mueren con el parche aplicado, petición rechazada por exceder el contexto) y entra en las
tasas, en los pares y en «cambia de resultado», con su motivo en un campo aparte. Solo un fallo de
infraestructura (sandbox, contenedor, snapshot, otro error del servidor del modelo) queda fuera de los
pares: mientras haya alguno sin repetir, el análisis sale con 1 y no con 0. Lo que se repite es la
**réplica entera**, con un número nuevo (sección «Réplicas descartadas»).

## Formato de recibo (`kaggle-replica-receipt/3`)

Un archivo **JSONL por réplica** (`replica_1.jsonl`, `replica_2.jsonl`, ...) con una línea por tarea. Se
eligió JSONL por réplica porque es la forma del `task_results.jsonl` que escribe `swegemma eval` (el
conversor es una correspondencia fila a fila) y porque cada línea lleva su propia réplica: el análisis
no depende de los nombres de archivo ni de su orden. Los recibos se añaden y no se editan a mano
([`proteger-evidencia`](../../../skills/proteger-evidencia/SKILL.md)); `convertir` se niega a sobrescribir
un archivo existente.

| Clave | Contenido |
|---|---|
| `schema_version` | `kaggle-replica-receipt/3` |
| `instance_id`, `repo` | tarea y repositorio |
| `condition` | condición (`A`) |
| `replica` | entero ≥ 1 |
| `status` | `resolved`, `unresolved` o `infra_error` |
| `failure_reason` | solo con `unresolved`: `empty_patch`, `agent_timeout`, `budget_exhausted`, `patch_apply_failed`, `tests_failed` o `context_exceeded`; en los demás casos `null` |
| `infra_reason` | solo con `infra_error`: `snapshot_missing`, `sandbox_error`, `evaluation_error`, `worker_error`, `missing_test_spec`, `test_patch_failed` o `test_exec_failed`; en los demás casos `null` |
| `resolved` | booleano; `true` solo si `status` es `resolved` |
| `tool_calls`, `duration_seconds` | llamadas a herramientas y duración (del arnés) |
| `patch_sha256` | SHA-256 del parche del agente; `null` si y solo si el parche está vacío. **Nunca el parche** |
| `submission_sha256` | SHA-256 del envío (ver abajo) |
| `tasks_sha256` | SHA-256 de `tasks.jsonl` |
| `subset_sha256` | SHA-256 del archivo de subconjunto (salida de `kaggle_split.py`) |
| `harness_version`, `sandbox_image` | versión del arnés e imagen del sandbox |
| `converted_utc` | momento de la conversión, `YYYY-MM-DDTHH:MM:SSZ` con ceros de relleno y fecha real; se ordena como fecha |
| `run_utc` | **obligatorio**: momento de la corrida. `convertir` lo toma de la fecha de modificación del `task_results.jsonl` del arnés, no de una opción; no puede ser posterior a `converted_utc`. No es una firma: copiar el archivo puede cambiar esa fecha |
| `harness_raw` | campos crudos del arnés: `resolved`, `error`, `test_exit_code`, `agent_patch_size`, `total_llm_calls` |

`harness_raw` permite reclasificar sin el `task_results.jsonl`, que git ignora: al leer un recibo, el
análisis vuelve a clasificar el crudo y exige que coincida con `status`, `failure_reason` e `infra_reason`
(editar un motivo a otro válido tampoco pasa). Una clave no
listada (por ejemplo `patch` o `test_patch`), una clave repetida dentro de una línea o una fecha
imposible hacen fallar la lectura.

### Hash del envío

Es el SHA-256 de las líneas `ruta<TAB>sha256_del_archivo`, ordenadas, con rutas relativas en formato POSIX.
Entran todos los archivos regulares del directorio salvo `__pycache__`, `*.pyc`, `*.pyo`, `.DS_Store`,
`Thumbs.db` y `desktop.ini`; un directorio inexistente o sin archivos es un error. `conditions/a_kit/` se
reconstruye con `download_kit.py` desde `manifest.json`, así que el hash se calcula **sobre el kit
descargado y verificado**, no sobre una copia cualquiera. `analizar --envio <dir>` recalcula ese hash,
exige que coincida con los recibos y añade al reporte la lista de archivos con su hash, para contrastarla
con el manifiesto.

## Qué entiende el conversor del arnés

El conversor lee de `task_results.jsonl` (HARNESS § 9.2) `instance_id`, `repo`, `resolved`,
`agent_patch_size`, `test_exit_code`, `duration_seconds`, `error`, `tool_calls` y `total_llm_calls`; el
parche, de `<dir_parches>/<instance_id>.patch`, con «/» del id sustituido por «__» como hace el arnés
(HARNESS § 9.2). Lo clasifica así (HARNESS § 8.1 y § 8.2):

- `resolved` del arnés manda. Si es `true`, la tarea es resuelta, también con parche vacío, y el tamaño
  y el `error` crudos se guardan. El arnés instalado deja `error` nulo cuando resuelve; conservar el
  texto de error en una tarea resuelta es solo un caso defensivo, no algo observado.
- Sin `error` y con parche vacío: `empty_patch`.
- Sin `error` y con parche, decide `test_exit_code`. Solo `-1` (no se pudo ejecutar el comando de
  pruebas) es `infra_error`, con `infra_reason` `test_exec_failed`. `124` (timeout del comando de
  pruebas) y `137` (proceso matado, por ejemplo por memoria) son `tests_failed`: con el parche del
  agente aplicado sobre una tarea que discrimina, el parche puede causarlos, y excluirlos sería
  quitar fallos del agente del denominador. Cualquier otro valor negativo o mayor que 128 sin error
  del arnés hace salir con 2 mostrando el valor. El resto de los códigos (por ejemplo 1, 2 o 5) es
  `tests_failed`.
- Con `error`, el texto se compara por prefijo con una **lista cerrada** derivada del código del arnés
  instalado, descrita con palabras propias:
  - sesión del agente agotada por tiempo → `agent_timeout`;
  - turnos, llamadas a herramientas o presupuesto del agente agotados → `budget_exhausted`;
  - el agente terminó sin enviar parche → `empty_patch`;
  - el parche del agente no se pudo aplicar → `patch_apply_failed`;
  - informe de pruebas ausente, mal formado, sin pruebas que pasen, con fallos o con un nodo requerido que
    no pasó → `tests_failed`;
  - snapshot ausente, error de ejecución del sandbox, error de evaluación, fallo inesperado del worker,
    especificación de pruebas ausente o `test_patch` que no aplica → `infra_error`. Un timeout del
    servidor del modelo llega por la vía del error de ejecución del sandbox;
  - un error de ejecución del sandbox cuyo texto contiene `ContextWindowExceededError` o `maximum
    context length` (sin distinguir mayúsculas) es un rechazo del servidor del modelo por exceder el
    contexto → `context_exceeded`, fallo del agente. El texto real del rechazo se confirma en el
    ensayo de notebook del pre-registro; hasta entonces estos dos marcadores son un supuesto.
- Un texto de error que no figure en la lista, `resolved` que no sea booleano, `agent_patch_size` que no
  sea un entero ≥ 0 o una combinación incoherente (por ejemplo `resolved` con `test_exit_code` distinto de
  0) hacen que el comando salga con 2 y muestre el texto; no hay categoría por defecto. Tampoco se acepta
  `--replica` menor que 1.

## Excepción a la convención de citar el arnés solo por sección

[`kaggle_specifications.md`](kaggle_specifications.md) cita el arnés únicamente por sección, para no
redistribuir su contenido. `scripts/kaggle_replicas.py` rompe esa convención en un punto: guarda los
**prefijos** de los mensajes de `error` del arnés. Son identificadores funcionales cortos, imprescindibles
para clasificar sin una categoría por defecto; no son tareas, parches ni pruebas de la competencia, y las
pruebas del script solo usan cada prefijo seguido de un sufijo inventado. Los prefijos salen de la versión
`swegemma` 0.2.7 del arnés instalado; con otra versión, un texto nuevo hará fallar el comando con 2 hasta
revisar la lista. La licencia del wheel de `swegemma` no consta en sus metadatos: está pendiente de
confirmar en la página del dataset de Kaggle, y la confirma el dueño del repositorio.

## Comandos

```bash
# Arnés -> recibos (una vez por réplica; no sobrescribe; run_utc sale de la fecha del task_results.jsonl).
python -m scripts.kaggle_replicas convertir --task-results <task_results.jsonl> --patches <dir_parches> \
  --replica 1 --condicion A --envio experiments/gemma_developer_agent/conditions/a_kit \
  --tasks <tasks.jsonl> --subconjunto <subconjunto.json> \
  --version-arnes <versión> --imagen-sandbox <imagen> --salida evidence/<campaña>/replica_1.jsonl

# Análisis
python -m scripts.kaggle_replicas analizar --recibos evidence/<campaña> --subconjunto <subconjunto.json> \
  --descartadas evidence/<campaña>/descartadas \
  --envio experiments/gemma_developer_agent/conditions/a_kit \
  --salida-json analisis.json --salida-md analisis.md
```

`convertir` comprueba antes de escribir que no haya tareas repetidas ni ajenas al subconjunto.
`--recibos <directorio>` lee solo los `.jsonl` de ese directorio, no los de sus subdirectorios;
`--descartadas` se omite si no hay réplicas descartadas.

## Réplicas descartadas y tope por tarea

Una réplica con algún `infra_error` o con tareas sin recibo se repite **entera** con un número de
réplica nuevo, y sus recibos se mueven sin editar a `descartadas/`. No entran en tasas ni en pares; el
reporte las lista con sus tareas afectadas. El análisis sale con 2 si una réplica descartada está
completa y sin errores de infraestructura (**una réplica no se descarta por su tasa**), si hay más de
2 descartadas, si un número de réplica está a la vez vigente y descartado, o si sus hashes no son los
de las vigentes.

Tope por tarea: si una misma tarea tiene `infra_error` en 2 réplicas o más, contando las descartadas,
deja de repetirse. En las réplicas vigentes cuenta como no resuelta, con el motivo de análisis
`infra_repetida`, y el reporte la lista aparte. El recibo no cambia: sigue diciendo `infra_error`.

Salida de `analizar`: `0` completo; `1` se escribió el reporte pero está incompleto (faltan tareas en
alguna réplica o hay errores de infraestructura, con la lista de tareas afectadas); `2` entrada inválida,
sin reporte nuevo; `3` error inesperado del script. La salida es determinista: mismos recibos, mismos
bytes, en cualquier orden de entrada.

Rutas de salida: antes de tocar nada, `analizar` rechaza con 2 una ruta que coincida con una entrada
(subconjunto, archivos o directorios de recibos, directorio de envío), que caiga dentro de un directorio
de entrada, que sea un directorio, o la misma ruta para el JSON y el Markdown. Un archivo que ya existe
solo se borra si es un reporte propio reconocible (JSON con la clave de versión del reporte, Markdown con
su encabezado); si existe y no lo es, sale con 2 y no lo borra. Un reporte propio anterior se borra antes
de leer las entradas, para que un error no deje un reporte obsoleto; si no se puede borrar (por ejemplo,
abierto en Windows) sale con 2 y dice que el reporte viejo sigue en disco y es obsoleto. El JSON y el
Markdown nuevos se escriben a temporales de nombre único y se renombran solo cuando ambos se escribieron
bien: o quedan los dos o ninguno.

## Comprobaciones que hacen fallar el análisis (salida 2)

- Un recibo ilegible o inválido (JSON roto, clave faltante, desconocida o repetida, tipo incorrecto,
  `status` incoherente con `harness_raw`) o un archivo de réplica sin ningún recibo.
- Recibos que mezclan valores de `tasks_sha256`, `submission_sha256`, `subset_sha256`, condición, versión
  del arnés o imagen del sandbox; o un `subset_sha256` distinto del hash del archivo dado.
- Un hash de `tasks.jsonl` de referencia ausente: el subconjunto debe declarar `sha256_tasks` o se pasa
  `--tasks-sha256`; si ambos existen y difieren, o los recibos no coinciden con él, falla.
- Con `--envio`, un hash de envío distinto del recalculado.
- Tareas fuera de la lista `test` del subconjunto; recibos duplicados para una misma tarea y réplica; una
  misma tarea con repositorios distintos.
- Menos de 2 réplicas.

## Qué reporta

1. **Tasa por réplica**: la principal es resueltas / tareas del subconjunto (la métrica de Kaggle); la
   secundaria, rotulada, es resueltas / válidas (sin errores de infraestructura ni faltantes). Las no
   resueltas se desglosan por motivo.
2. **Errores de infraestructura aparte**: solo `infra_error` se excluye de los pares y de «cambia»; una
   tarea con ese error en una réplica se compara únicamente con las réplicas donde tiene resultado válido,
   y el análisis queda incompleto hasta repetir la réplica. Los fallos del agente no se excluyen. Se
   listan también las réplicas descartadas, las tareas con infraestructura repetida y la fecha de la
   corrida de cada réplica.
3. **Tareas que cambian de resultado**: de las tareas con al menos 2 réplicas válidas, cuántas tienen
   resultados mixtos (numerador / denominador), con su lista.
4. **Pares de réplicas**, sobre las tareas válidas en ambas: tabla 2×2, acuerdo (numerador / denominador),
   tasa de discordancia con intervalo y p-valor de McNemar exacto.
5. **Tabla por tarea** y **desglose por repositorio** (el repositorio sale de los recibos).
6. **Diferencia mínima significativa** y **suelo** (siguiente sección).

## Método: diferencia mínima significativa

Supuestos: las tareas del subconjunto son las únicas de interés (no se generaliza a otras); la
discordancia entre réplicas de A es una medida del ruido de una corrida; la campaña comparará dos
condiciones con **una corrida cada una** sobre las mismas tareas.

1. Para cada par de réplicas, discordantes = tareas resueltas en una y no en la otra. Su tasa
   (discordantes / comparables) lleva un **intervalo exacto de Clopper-Pearson** de nivel 1 − α (α = 0,05
   por defecto, `--alfa`), calculado por bisección sobre la binomial, en logaritmos para que `n` grande no
   desborde. No hay aproximación normal.
2. La **prueba pareada de McNemar exacta** usa solo los pares discordantes: bajo la hipótesis nula, de `d`
   discordantes cada condición gana cada uno con probabilidad 1/2; el p-valor bilateral es
   `min(1, 2·P(X ≤ min(b, c)))` con X ~ Binomial(d, 1/2). Se acepta p ≤ α (la igualdad cuenta).
3. **Suelo**: el menor número de pares discordantes, todos a favor de una condición, con p ≤ α. Con
   α = 0,05 son 6 (p = 0,03125; con 5 sería 0,0625), es decir una diferencia de 6/n. Solo es «no
   alcanzable» si hay menos de ese número de tareas comparables.
4. **Diferencia mínima significativa**: del par con **mayor** discordancia se toma el rango de números de
   discordantes `d` entre el observado y el del límite superior del intervalo (`ceil(límite · comparables)`).
   Para cada `d` se busca el menor número de pares ganados `g` con p ≤ α; la diferencia de tasa es
   `(2g − d) / comparables`. Esa función no es monótona en `d` (depende de la paridad), por eso la cota es
   el **máximo** sobre el rango y no el valor en el extremo. Un `d` menor que el suelo no alcanza α y no
   aporta valor; el reporte lo marca.
5. Se reporta además la diferencia observada entre la mayor y la menor tasa de réplica, como dato
   descriptivo.

Qué es y qué no es:

- Es un umbral de **significación**, no de potencia: un efecto real de ese tamaño se declararía
  significativo aproximadamente la mitad de las veces. No hay cálculo de potencia.
- El `d` de A contra B no lo fija el de A contra A: la discordancia A contra B incluye el ruido de B y el
  efecto real. Por eso el suelo no depende del ruido medido, y la tabla por `d` solo ilustra cómo sube la
  diferencia mínima si el ruido es mayor.
- El intervalo sobre «el peor par» entre `k` pares no tiene cobertura 1 − α: escoger el máximo de varios
  pares sesga el límite hacia arriba. Con 3 o más réplicas los pares comparten tareas y no son
  independientes; no se agrupan ni se corrigen por comparaciones múltiples.
- Con tareas fijas y no muestreadas, usar una binomial con probabilidad común para todas las tareas es una
  aproximación conservadora: la discordancia real puede concentrarse en pocas tareas inestables.
- El número de tareas es pequeño y el intervalo ancho: ese ancho es parte del resultado. Con otro número
  de tareas o más corridas por condición, la diferencia mínima se recalcula con otro `n`.

## Frontera de fuga

El análisis no lee parches (ni dorados ni del agente), ni `test_patch`, ni `tasks.jsonl` (solo su hash).
Del subconjunto lee la lista `test` y `sha256_tasks`. Los datos de la competencia no se redistribuyen: las
pruebas del script usan solo datos sintéticos, y este documento describe el arnés con palabras propias.
