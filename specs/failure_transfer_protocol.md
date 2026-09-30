# Suplemento: transferencia y contaminación de la memoria de fallos (H7, #65)

Suplementa [`software_learning_protocol.md`](software_learning_protocol.md),
[`diagnostic_baseline_protocol.md`](diagnostic_baseline_protocol.md) y
[`failure_memory_protocol.md`](failure_memory_protocol.md) para un agente opt-in. No cambia esos documentos,
el agente por defecto, el de #58, el de H6 ni ninguna campaña publicada. Diseño, métricas, reglas de decisión
y predicciones están pre-registrados en
[`docs/preregistration/failure-transfer.md`](../docs/preregistration/failure-transfer.md) (C0 `b1565bf`).

## Alcance

El agente `bounded-ast-repair-v1+diagnostic-v1+failure-memory-v1+failure-transfer-v1`
(`experiments.failure_transfer.FailureTransferRepairAgent`) es el de H6 con dos parámetros más, que declara
su condición: el alcance τ y el placebo. Mismos operadores, parches, diagnóstico D, registro de fallo, firma,
clave `title + " " + context` y política `(op ∉ S, op ∈ F, op ≠ p, prior)`. Solo lo ejecuta
`python -m experiments run --campaign failure-transfer-v1`, cuyos recibos van por defecto a
`evidence/failure-transfer-v1/`. Cualquier otra receta ejecuta su agente exactamente como antes; en
particular, el agente de H6 sigue usando τ = 0.5 sin placebo.

## Condiciones y secuencia

| Condición | `memory_mode` (lecciones) | Memoria de fallos | `failure_scope_tau` | `placebo` |
|---|---|---|---|---|
| `A` | `NO_MEMORY` | no | `null` | `false` |
| `A_R50`, `A_R25`, `A_R10`, `A_R00` | `NO_MEMORY` | sí | 0.5, 0.25, 0.1, 0.0 | `false` |
| `A_P50`, `A_P25`, `A_P10`, `A_P00` | `NO_MEMORY` | sí | 0.5, 0.25, 0.1, 0.0 | `true` |
| `C` | `ASSOCIATIVE_MEMORY`, congelada tras el entrenamiento | no | `null` | `false` |
| `C_R50` … `C_R00`, `C_P50` … `C_P00` | `ASSOCIATIVE_MEMORY`, congelada tras el entrenamiento | sí | como en A | como en A |

Por (réplica, semilla, condición), con memorias nuevas: entrenamiento EXP-01..03 y **una sola pasada** de
EXP-04..09, en el orden de `misleading-v1`. Las lecciones solo se añaden en entrenamiento (`ADD` con `PASS`
verificado, igual que #58 y H6). La memoria de fallos de cada variante real o placebo es **suya**: se
actualiza en línea después de cada una de sus ejecuciones, en las dos fases, con los intentos fallidos de esa
misma (réplica, semilla, condición). Semillas 1 4 5 6 7 9, 2 réplicas; el orden de las condiciones dentro de
una semilla se baraja con la semilla, como en H6.

**Representación.** Los recibos de H7 no llevan `pass`: la secuencia tiene una sola pasada y su orden
temporal declarado dentro de una (lote, semilla, condición) es el orden de la tarea en `misleading-v1`. Como
ninguna tarea se repite, todo registro que aplica viene de otra tarea por construcción; el evaluador y el
análisis lo verifican igualmente.

## Alcance τ y placebo

Un registro aplica si su `signature` es idéntica a la de `test-0` y
`cosine_similarity(query, registro.query) ≥ τ` (`associative_agent_loop.memory.text`, la misma función de
H6). El coseno léxico nunca es negativo, así que con τ = 0 basta la firma. En A y C, τ es `null` y el agente
rechaza cualquier registro.

En el placebo, cada registro que aplica baja `STRATEGIES[(i + 1) mod 3]` en lugar de su propia estrategia
`STRATEGIES[i]`, sobre el orden de `STRATEGIES` en `agent.py`: identidad → entorno → almacenamiento →
identidad. La rotación solo se aplica al construir `F`: el registro, su recibo `memory_update` y
`failure_memory_input` guardan la estrategia real.

## Recibos

- Mismo esquema (`software-learning-receipt/v2`) y normalización (`lf/v1`).
- Campos aditivos del recibo, solo con este agente: `condition`, `failure_scope_tau`, `placebo`,
  `failure_memory_input`, `failure_origins` (siempre `other_task`) y
  `decision_inputs = {"order": ["RETRIEVE", "test-0", "plan"], "reproduction": "test-0",
  "failures": "failure_memory_input", "failure_scope_tau": "failure_scope_tau", "placebo": "placebo"}`. El
  contexto hasheado del agente cubre también `failure_policy = {"failure_scope_tau", "placebo"}`.
- Decisión: todos los campos de H6 con el mismo significado, `policy = "failure-transfer/v1"` y, además,
  `failure_scope_tau`, `failure_placebo` y `failure_recorded_strategies` (las estrategias registradas de los
  registros aplicados). `failure_strategies` es `F`, lo que **bajó**: coincide con
  `failure_recorded_strategies` en las variantes reales y es su rotación en el placebo. Cada elemento de
  `failure_scope` lleva además `demotes`, la estrategia que ese registro baja si aplica.
- Memoria de fallos: los mismos recibos `memory_update` separados de H6 (`memory_store = "failure-memory/v1"`),
  uno por ejecución de una variante con intentos fallidos. Las lecciones se publican como antes.

Con τ = 0.5 y sin placebo, la decisión de este agente es exactamente la de H6 salvo `policy` y los campos
aditivos (lo comprueba un test sobre todas las combinaciones de D, lecciones y registros sintéticos).

## Evaluación

`python -m experiments evaluate` añade, solo para recibos de este agente:

- coherencia agente↔política en los dos sentidos: ningún otro agente, tampoco el de H6, puede llevar campos
  de H7;
- `decision_inputs` exacto, `test-0` fallido, sin `pass`, y condición, modo, τ y placebo coherentes con la
  tabla anterior;
- las bases A y C no tienen registros de fallo, registros aplicados ni orígenes;
- la decisión se vuelve a calcular desde el recibo (tarea, lecciones, semilla, `test-0`,
  `failure_memory_input`, τ y placebo) y debe coincidir; D es el mismo en todas las condiciones de cada
  (lote, semilla, tarea);
- ningún registro aplicado tiene origen en la misma tarea: se comprueba con la tarea del recibo citado,
  buscado en toda la campaña, y con los orígenes anotados;
- la misma cadena de registros de H6, en el orden de la única pasada: cada registro cita un test fallido real
  de un recibo sellado anterior de su (lote, semilla, condición), la memoria que recibe cada ejecución es
  exactamente la de los intentos fallidos anteriores, y hay un único `memory_update` de fallos por ejecución
  de una variante con intentos fallidos, y ninguno más.

El informe genérico de esta campaña se indexa por corte: `without-failure-memory` (A y C) y
`real-tau-<τ>` / `placebo-tau-<τ>` (A_x y C_x de esa variante). Cada corte tiene su entrenamiento y su única
pasada, así que los pares con `NO_MEMORY` no mezclan condiciones. Los informes de las campañas publicadas no
cambian.

## Análisis pre-registrado

`python -m scripts.analyze_failure_transfer --evidence <dir>` verifica el sello de cada recibo con la
biblioteca estándar, cita `generated_from` y **rechaza** (`ValueError`, sin veredicto) cualquier cosa distinta
de la campaña declarada: 2 lotes × 6 semillas × 18 condiciones × 9 ejecuciones, sin duplicados ni semillas o
condiciones inesperadas; τ y placebo de su condición; lecciones en línea solo del entrenamiento de la misma
condición y congeladas después; registros que citan intentos fallidos anteriores de su celda, ninguno en A y
C y ninguno aplicado de la misma tarea; decisiones coherentes con su alcance y su placebo (lo verificable sin
el coseno, que el evaluador recalcula); un `memory_update` por ejecución que lo exige; y réplicas idénticas
en comportamiento.

Sobre la réplica 1, para cada base X ∈ {A, C}, variante V (real o placebo), τ y tipo (original EXP-04..06,
engañosa EXP-07..09, nunca agregados), con los 18 pares (semilla, tarea) de V frente a X: `Exposure`
(pares con algún registro aplicado), `Changed` (`failure_effect = changed_first`), `helped` (V acierta al
primer intento y X no), `hurt` (al revés), `NetTransfer = helped − hurt` y `FA` de V y de X, con numerador y
denominador. Una celda con `Changed < 3` es «sin exposición». Aplica H7a, H7b y H7c de la sección 7 a las dos
variantes y la conclusión, solo sobre la base C y la variante real. Añade descriptivos: por tarea, el origen
de los registros aplicados (`origen -> destino`), el estado de D por tarea, los pares cuyo plan sin memoria de
fallos no es el de la base (`base_plan_equal`) y los pares con `helped` o `hurt` sin `Changed`.
