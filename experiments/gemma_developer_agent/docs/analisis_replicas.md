# Análisis de réplicas de la línea base A

Ficha del comando `scripts/kaggle_replicas.py` (issue #103, parte del análisis). Se escribe y se mergea
**antes** de que exista ningún recibo real: fija cómo se leerá la evidencia. Este documento no afirma
ningún resultado; no hay datos todavía.

## Qué mide

Cuánto varía la condición A (kit oficial) contra sí misma al repetir la misma corrida sobre el mismo
subconjunto de tareas. Con eso se calcula qué diferencia entre dos condiciones no se distingue de ese
ruido. El script calcula y reporta; los umbrales de decisión se fijan en el pre-registro, no aquí.

## Formato de recibo (`kaggle-replica-receipt/1`)

Un archivo **JSONL por réplica** (`replica_1.jsonl`, `replica_2.jsonl`, ...) con una línea por tarea. Se
eligió JSONL por réplica porque es la forma del `task_results.jsonl` que escribe `swegemma eval` (el
conversor es una correspondencia fila a fila) y porque cada línea lleva su propia réplica: el análisis
no depende de los nombres de archivo ni de su orden. Los recibos se añaden y no se editan a mano
([`proteger-evidencia`](../../../skills/proteger-evidencia/SKILL.md)).

| Clave | Contenido |
|---|---|
| `schema_version` | `kaggle-replica-receipt/1` |
| `instance_id`, `repo` | tarea y repositorio |
| `condition` | condición (`A`) |
| `replica` | entero ≥ 1 |
| `status` | `resolved`, `unresolved`, o un estado sin resultado válido: `timeout`, `infra_error`, `empty_patch` |
| `resolved` | booleano; debe ser `true` solo si `status` es `resolved` |
| `tool_calls`, `duration_seconds` | llamadas a herramientas y duración |
| `patch_sha256` | SHA-256 del parche del agente, o `null` si no hay parche. **Nunca el parche** |
| `submission_sha256` | SHA-256 del directorio de la condición (ver abajo) |
| `tasks_sha256` | SHA-256 de `tasks.jsonl` |
| `subset_sha256` | SHA-256 del archivo de subconjunto (salida de `kaggle_split.py`) |
| `harness_version`, `sandbox_image` | versión del arnés e imagen del sandbox |
| `created_utc` | `YYYY-MM-DDTHH:MM:SSZ` |
| `llm_calls` | opcional |

Una clave no listada (por ejemplo `patch` o `test_patch`) hace fallar la lectura: un recibo no lleva
parches ni pruebas. El hash de un directorio es el SHA-256 de las líneas `ruta<TAB>sha256_del_archivo`
ordenadas, con rutas relativas en formato POSIX.

## Comandos

```bash
# Arnés -> recibos (una vez por réplica). El análisis no necesita los datos de la competencia.
python -m scripts.kaggle_replicas convertir --task-results <task_results.jsonl> --patches <dir_parches> \
  --replica 1 --condicion A --envio experiments/gemma_developer_agent/conditions/a_kit \
  --tasks <tasks.jsonl> --subconjunto <subconjunto.json> \
  --version-arnes <versión> --imagen-sandbox <imagen> --salida evidence/<campaña>/replica_1.jsonl

# Análisis
python -m scripts.kaggle_replicas analizar --recibos evidence/<campaña> --subconjunto <subconjunto.json> \
  --salida-json analisis.json --salida-md analisis.md
```

El conversor lee del arnés `instance_id`, `repo`, `resolved`, `agent_patch_size`, `duration_seconds`,
`error`, `tool_calls` y `total_llm_calls`. El estado sale primero de `error` (si menciona «timeout» o
«timed out», `timeout`; si no, `infra_error`), luego de `agent_patch_size == 0` (`empty_patch`) y luego de
`resolved`. El parche se busca como `<dir_parches>/<instance_id>.patch`; ese nombre es una suposición
sobre el arnés que se confirma con la primera corrida real.

Salida de `analizar`: `0` completo; `1` se escribió el reporte pero faltan tareas en alguna réplica
(se listan como faltantes); `2` entrada inválida, sin reporte. La salida es determinista: mismos recibos,
mismos bytes, en cualquier orden de entrada.

## Comprobaciones que hacen fallar el análisis (salida 2)

- Un recibo ilegible o inválido (JSON roto, clave faltante o desconocida, tipo incorrecto, `resolved`
  contradictorio con `status`).
- Recibos que mezclan valores de `tasks_sha256`, `submission_sha256`, `subset_sha256`, condición, versión
  del arnés o imagen del sandbox; o un `subset_sha256` distinto del hash del archivo dado; o un
  `tasks_sha256` distinto del `sha256_tasks` que declara el subconjunto.
- Tareas fuera de la lista `test` del subconjunto; recibos duplicados para una misma tarea y réplica; una
  misma tarea con repositorios distintos.
- Menos de 2 réplicas.

Una tarea del subconjunto sin recibo en alguna réplica se reporta como **faltante** y da salida 1.

## Qué reporta

1. **Tasa por réplica**: resueltas / válidas (válida = `resolved` o `unresolved`) y resueltas / tareas del
   subconjunto.
2. **Errores aparte**: `timeout`, `infra_error` y `empty_patch` se cuentan por separado y no entran como
   «no resuelta» ni en los pares; una tarea con error en una réplica se compara solo con las réplicas
   donde tiene resultado válido.
3. **Tareas que cambian de resultado**: de las tareas con al menos 2 réplicas válidas, cuántas tienen
   resultados mixtos (numerador / denominador), con su lista.
4. **Pares de réplicas**, sobre las tareas válidas en ambas: tabla 2×2, acuerdo (numerador / denominador),
   tasa de discordancia con intervalo y p-valor de McNemar exacto.
5. **Tabla por tarea** y **desglose por repositorio** (el repositorio sale de los recibos).

## Método del margen

Supuestos: las tareas del subconjunto son las únicas de interés (no se generaliza a otras); la
discordancia entre réplicas de A es una medida del ruido de una corrida; la campaña comparará dos
condiciones con **una corrida cada una** sobre las mismas tareas.

1. Para cada par de réplicas, discordantes = tareas resueltas en una y no en la otra. Su tasa
   (discordantes / comparables) lleva un **intervalo exacto de Clopper-Pearson** de nivel 1 − α (α = 0,05
   por defecto, `--alfa`), calculado por bisección sobre la binomial con `math.comb`. No hay aproximación
   normal.
2. La **prueba pareada de McNemar exacta** usa solo los pares discordantes: bajo la hipótesis nula, de `d`
   discordantes cada condición gana cada uno con probabilidad 1/2; el p-valor bilateral es
   `min(1, 2·P(X ≤ min(b, c)))` con X ~ Binomial(d, 1/2).
3. Del par con **mayor** discordancia se toman dos números de discordantes `d`: el observado y el que
   corresponde al límite superior del intervalo (`ceil(límite · comparables)`). Para cada uno se busca el
   menor número de pares ganados `g` con p ≤ α. La **diferencia mínima de tasa** es `(2g − d) / comparables`.
   Si ni `g = d` alcanza α (muy pocos discordantes), se reporta «no alcanzable».
4. Se reporta además la diferencia observada entre la mayor y la menor tasa de réplica, como dato
   descriptivo.

Límites: con 3 o más réplicas los pares comparten tareas y no son independientes, por eso no se agrupan y
se toma el peor par; no se corrige por comparaciones múltiples; el número de tareas es pequeño y el
intervalo ancho: ese ancho es parte del resultado. Si la campaña usa otro número de tareas o más corridas
por condición, la diferencia mínima se recalcula con otro `n`.

## Frontera de fuga

El análisis no lee parches (ni dorados ni del agente), ni `test_patch`, ni `tasks.jsonl` (solo su hash).
Del subconjunto lee la lista `test` y `sha256_tasks`. Los datos de la competencia no se redistribuyen: las
pruebas del script usan solo datos sintéticos.
