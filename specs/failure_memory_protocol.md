# Suplemento: memoria de fallos con revisión (H6, #63)

Suplementa [`software_learning_protocol.md`](software_learning_protocol.md) y
[`diagnostic_baseline_protocol.md`](diagnostic_baseline_protocol.md) para un agente opt-in. No cambia esos
documentos, el agente por defecto, el agente de diagnóstico de #58 ni ninguna campaña publicada. Diseño,
métricas, reglas de decisión y predicciones están pre-registrados en
[`docs/preregistration/failure-memory.md`](../docs/preregistration/failure-memory.md) (C0 `87c5941`).

## Alcance

El agente `bounded-ast-repair-v1+diagnostic-v1+failure-memory-v1`
(`experiments.failure_memory.FailureMemoryRepairAgent`) tiene los mismos tres operadores, los mismos
parches y el mismo diagnóstico D que el de #58. Solo lo ejecuta
`python -m experiments run --campaign failure-memory-v1`, cuyos recibos van por defecto a
`evidence/failure-memory-v1/`. Cualquier otra receta ejecuta su agente exactamente como antes.

## Condiciones y secuencia

| Condición | `memory_mode` (lecciones) | Memoria de fallos |
|---|---|---|
| `A` | `NO_MEMORY` | no |
| `A_N` | `NO_MEMORY` | sí |
| `C` | `ASSOCIATIVE_MEMORY`, congelada tras el entrenamiento | no |
| `C_N` | `ASSOCIATIVE_MEMORY`, congelada tras el entrenamiento | sí |

Las cuatro condiciones usan el mismo agente y la misma política; en A y C el agente recibe una memoria de
fallos vacía, así que su decisión es la de #58. Por (réplica, semilla, condición), con memorias nuevas:
entrenamiento EXP-01..03 (`pass = 1`), pasada 1 de EXP-04..09 (`pass = 1`) y pasada 2 de EXP-04..09
(`pass = 2`), en el mismo orden. Las lecciones solo se añaden en entrenamiento (`ADD` con `PASS`
verificado, igual que #58); la memoria de fallos de A_N y C_N se actualiza en línea después de cada
ejecución, en las tres fases. Semillas 1 4 5 6 7 9, 2 réplicas, conjunto `misleading-v1`.

**Representación.** `pass` numera la pasada por la secuencia: el entrenamiento solo ocurre en la primera, así
que sus ejecuciones llevan `pass = 1`, y la «pasada 1» del pre-registro es `split = transfer` y `pass = 1`.
El orden temporal declarado dentro de una (lote, semilla, condición) es `(pass, orden de la tarea en
misleading-v1)`.

## Registro de fallo y entrada extendida del solver

Un registro nace de cada intento de reparación `tests[i]`, `i ≥ 1`, con `returncode ≠ 0`, de un recibo
`task_run` sellado de A_N o C_N:

```json
{"id": "failure:RUN-…#test-i", "strategy": "…", "query": "title + ' ' + context",
 "signature": [{"outcome": "…", "exception": "…", "none_marker": false}],
 "evidence": "RUN-…#test-i", "receipt_sha256": "…"}
```

`signature` son los rasgos que D extrae de `test-0` del recibo de origen. El registro no lleva el id de la
tarea: el origen (misma tarea u otra) lo lee el controlador del recibo sellado **después** de decidir y lo
anota en `failure_origins`; nunca llega al agente. Además de lo que recibe el agente de #58, este agente
recibe la lista de registros de su condición (`failure_memory_input`), tomada al recuperar y antes de
`test-0`. Nunca recibe anotaciones privadas, parches dorados ni la salida de los intentos de la ejecución
en curso.

## Alcance y política

Un registro aplica si su `signature` es idéntica a la de `test-0` y
`cosine_similarity(query, registro.query) ≥ 0.5` (`associative_agent_loop.memory.text`). Con `F` = las
estrategias de los registros que aplican:

```text
plan = sorted(STRATEGIES, key=λop: (op ∉ S, op ∈ F, op ≠ p, prior.index(op)))
```

`S` y `p` son los de #58. Con `F` vacío la decisión es exactamente la de #58 (salvo `policy` y los campos
aditivos). El plan sigue siendo una permutación de los tres operadores.

## Recibos

- Mismo esquema (`software-learning-receipt/v2`) y normalización (`lf/v1`).
- Campos aditivos del recibo, solo con este agente: `condition`, `pass`, `failure_memory_input`,
  `failure_origins` (`[{"id", "origin": "same_task" | "other_task"}]` por registro aplicado) y
  `decision_inputs = {"order": ["RETRIEVE", "test-0", "plan"], "reproduction": "test-0",
  "failures": "failure_memory_input"}`. El contexto hasheado del agente cubre también los registros.
- Campos aditivos de `decision`: `policy = "failure-memory/v1"`, `plan_without_failures` (el plan de #58),
  `failure_scope` (por registro, en orden: estrategia, firma idéntica, similitud y si aplica),
  `failure_ids`, `failure_strategies` y `failure_effect` (`none`, `no_change`, `changed_first`). Los campos
  de #58 (`plan_without_memory`, `memory_effect`, `without_memory`, `influenced_by_memory`) conservan su
  significado respecto de las lecciones: se calculan como en #58, sin la memoria de fallos.
- Memoria de fallos: un `memory_update` separado y sellado por cada ejecución de A_N o C_N con intentos
  fallidos, con `memory_store = "failure-memory/v1"`, `source_receipt`, `memory_before`, `memory_after` y
  `memory_changes` (`ADD` por registro). Las lecciones siguen publicándose como antes (sin `memory_store`).

## Evaluación

`python -m experiments evaluate` añade, solo para recibos de este agente:

- coherencia agente↔política en los dos sentidos: ningún otro agente puede llevar campos de H6;
- `decision_inputs` exacto, `test-0` fallido, condición y pasada coherentes con `memory_mode`;
- la decisión se vuelve a calcular desde el recibo (tarea, lecciones, semilla, `test-0` y
  `failure_memory_input`) y debe coincidir; D es el mismo en todas las condiciones y pasadas de cada
  (lote, semilla, tarea);
- en el orden temporal declarado, cada registro cita un test fallido real (`i ≥ 1`, `returncode ≠ 0`) de un
  recibo sellado **anterior** de su (lote, semilla, condición), con campos iguales a los que se derivan de
  él, y la memoria que recibe cada ejecución es exactamente la de los intentos fallidos anteriores (vacía en
  A y C);
- los orígenes anotados coinciden con los recibos, y hay un único `memory_update` de fallos por ejecución
  de A_N o C_N con intentos fallidos, y ninguno más; las lecciones de C_N nunca provienen de C.

El informe genérico de esta campaña se indexa por corte (`without-failure-memory-pass-1`,
`…-pass-2`, `with-failure-memory-pass-1`, `…-pass-2`): cada corte tiene el entrenamiento de sus dos
condiciones y una pasada de transferencia, así que los pares con `NO_MEMORY` no mezclan condiciones ni
pasadas (A_N se empareja consigo mismo y C_N con A_N). Los informes de las campañas publicadas no cambian.

## Análisis pre-registrado

`python -m scripts.analyze_failure_memory --evidence <dir>` verifica el sello de cada recibo con la
biblioteca estándar, cita `generated_from` y rechaza cualquier cosa distinta de la campaña declarada
(2 lotes × 6 semillas × 4 condiciones × (9 + 6) ejecuciones, sin duplicados; lecciones en línea solo del
entrenamiento de la misma condición y congeladas después; registros que citan intentos fallidos anteriores
de su celda; un `memory_update` por ejecución que lo exige) antes de cualquier veredicto. Calcula `FA`,
`RepeatedFirstFailure` (pasada 2), `CrossTaskEffect` e intentos por pasada, condición y tipo (original,
engañosa; nunca agregados), y aplica las reglas H6a, H6b y H6c de la sección 6. Es inválido si las réplicas
difieren o si A o C no reproducen la pasada 1 en la pasada 2 (control de determinismo).

`CrossTaskEffect` cuenta los primeros intentos cambiados (`changed_first`) con al menos un registro aplicado
de otra tarea (`mixed` cuenta los que también aplicaron uno de la misma tarea). `helped` y `hurt` comparan el
nuevo primer intento con el desplazado (`plan_without_failures[0]`) en la misma ejecución; si el desplazado
no llegó a probarse, el caso es `neutral` con la marca `untested`. Como una ejecución termina en su primer
acierto, un nuevo primer intento exitoso deja siempre al desplazado sin probar: con esta regla, `helped` no
es observable.
