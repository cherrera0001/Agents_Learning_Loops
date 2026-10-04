# Suplemento: recuperación sembrada con los componentes de la traza (H8, #98)

Suplementa [`software_learning_protocol.md`](software_learning_protocol.md) para un agente opt-in. No cambia
ese documento, el agente por defecto, los de #58, H6 y H7, ni ninguna campaña publicada. Diseño, métricas,
reglas de decisión y predicción están pre-registrados en
[`docs/preregistration/h8-nonlexical-seed.md`](../docs/preregistration/h8-nonlexical-seed.md) (C0 `6034512`).

## Alcance

El agente `bounded-ast-repair-v1+trace-seed-v1` (`experiments.nonlexical_seed.TraceSeedRepairAgent`) tiene
los mismos operadores, los mismos parches y el mismo `plan()` que `bounded-ast-repair-v1`: solo declara su
política, `trace-component-seed/v1`, y su condición. Lo ejecuta únicamente
`python -m experiments run --campaign nonlexical-seed-v1`, cuyos recibos van por defecto a
`evidence/nonlexical-seed-v1/`. Cualquier otra receta ejecuta su agente exactamente como antes;
`agent.py` y `memory.py` no cambian.

La señal entra en la **recuperación**, no en la decisión. En #58 el diagnóstico D entraba en `plan()`; aquí
`plan()` es el del agente por defecto y no usa D ni recibe `test-0`.

## Condiciones y secuencia

| Condición | `memory_mode` | Señal de siembra (`retrieval.seeding.signal`) |
|---|---|---|
| `A` | `NO_MEMORY` | `null` |
| `B` | `TEXT_HISTORY` | `null` (el solver ordena por similitud léxica) |
| `C_L` | `ASSOCIATIVE_MEMORY` | `lexical-title-context`: la de H4, `EvidenceMemory.retrieve` sin cambios |
| `C_S` | `ASSOCIATIVE_MEMORY` | `trace-components`: los componentes de la traza de `test-0` |

Por (réplica, semilla, condición), con memoria nueva: entrenamiento EXP-01..03, con `ADD` solo tras un `PASS`
verificado, y transferencia EXP-04..09 desde la memoria congelada. C_S usa su siembra también en el
entrenamiento. C_L y C_S construyen sus lecciones igual y no las comparten. Semillas 1 4 5 6 7 9, 2 réplicas;
el orden de las condiciones dentro de una semilla se baraja con la semilla.

Orden dentro de una ejecución, igual en las cuatro: `prepare`; `test-0`; `RETRIEVE`; `plan()`, una vez; hasta
3 intentos. La tabla de fases no cambia. El runner comprueba que `test-0` deja intactos el código de la
aplicación y los tests protegidos antes de recuperar; si no, la ejecución termina en `ERROR`. `tests[1:]`
nunca realimentan la recuperación ni el plan.

## La señal y la siembra de C_S

`experiments.trace_seed` es la función de siembra. Recibe tres entradas y ninguna más: el `stderr` de
`test-0`, las claves de archivo que el solver ya ve (`app/….py`) y la memoria de la condición. No recibe la
tarea ni su identificador, no lee archivos y no contiene ninguna regla que nombre una tarea, una familia o un
operador.

1. El `stderr` se normaliza (`normalize_source`) y se separa en bloques como D: un bloque empieza por
   `ERROR: ` o `FAIL: `, y el resumen final se corta.
2. De cada bloque se usa la **última** traza: las líneas posteriores a la última línea igual a
   `Traceback (most recent call last):`. Un bloque sin esa línea no aporta nada.
3. Un marco es una línea `File "…", line N, in …`. Solo se usa su ruta, con `\` cambiada por `/`. Pertenece al
   componente `k` si la ruta termina en `/` seguido de la clave de archivo `k`; si dos claves casan, gana la
   más larga. Los demás marcos se descartan.
4. Con `d = 0` para el marco de aplicación más cercano a la excepción, el peso de un componente en el bloque
   es `1 / (1 + d)` para su aparición más interna. `T(k)` es el máximo sobre los bloques.
5. La puntuación de un nodo `Component` (su etiqueta es una lista de rutas separadas por espacios) es el
   máximo de `T(k)` sobre sus rutas. Se siembra si es mayor que 0. Ningún otro tipo de nodo se siembra y no
   hay consulta léxica.

La proyección, la propagación, el corte (activación ≥ 0.005) y el top-1 son los de `EvidenceMemory.retrieve`.

| Estado | Condición | Lección expuesta |
|---|---|---|
| `seeded` | un solo nodo `Component` tiene la puntuación máxima y su lección supera el corte | esa lección |
| `tie` | dos o más nodos `Component` comparten la puntuación máxima | ninguna |
| `empty` | ningún nodo sembrado (también con memoria vacía), o la lección no supera el corte | ninguna |

Sin lección expuesta el plan es el prior de la semilla. **No hay respaldo léxico.** «No léxica» quiere decir
«sin la consulta léxica de `title + context`»: la política sí compara rutas de archivo.

## Recibos

- Mismo esquema (`software-learning-receipt/v2`) y normalización (`lf/v1`).
- Campos aditivos del recibo, solo con este agente: `condition` (sin `pass`),
  `decision_inputs = {"order": ["test-0", "RETRIEVE", "plan"], "reproduction": "test-0"}` y el bloque
  `retrieval.seeding = {"policy", "signal", "components", "seeds", "state", "lesson"}`. `components` son los
  componentes extraídos con su peso (`[{"component", "weight"}]`) y se registran en las cuatro condiciones,
  aunque solo C_S los usa. `seeds` (`[{"node", "score"}]`), `state` y `lesson` solo existen en C_S; en A, B y
  C_L son `null`.
- Decisión: los campos del agente por defecto y `policy = "trace-component-seed/v1"`. Ningún campo de D.
- El contexto hasheado del agente cubre, además de la tarea, el código y las lecciones expuestas, lo que
  recibió la recuperación (`retrieval`): la condición, la política, la señal, la huella de la memoria en las
  condiciones con memoria, `title + context` en C_L, y el `stderr` de `test-0` y las claves de archivo en C_S.
- Las lecciones se publican como antes, en recibos `memory_update` separados.

## Evaluación

`python -m experiments evaluate` añade, solo para recibos de este agente:

1. coherencia agente↔política en los dos sentidos; ningún otro agente lleva el bloque `retrieval.seeding`, y
   este agente no lleva campos de la memoria de fallos; un directorio no mezcla agentes;
2. `decision_inputs` exacto, identificadores de test consecutivos y `test-0` fallido;
3. condición coherente con `memory_mode` y con la señal de siembra de la tabla;
4. rechazo de una siembra con material privado o causal: una semilla en un nodo que no sea `Component`, una
   puntuación que no salga de la traza registrada, o una ruta de `benchmark/private/`, una clave de las
   anotaciones privadas o uno de sus valores causales (`family`, `decoy_family`, `hidden_cause_id`) en el
   bloque de siembra o en las rutas del contexto del agente. La búsqueda es por token exacto y no mira el
   código fuente ni el texto de la tarea;
5. repetición de la recuperación solo con `tests[0].stderr`, las claves de `initial_source` y `memory_input`
   (más `title + context` en C_L): debe coincidir con la registrada en componentes, puntuaciones, estado,
   caminos y lección expuesta; la memoria de entrada debe ser la de su huella y el contexto hasheado, el que
   cubre esas entradas;
6. repetición de la decisión con el `plan()` por defecto desde la tarea, las lecciones expuestas, el modo y la
   semilla;
7. la misma señal en las cuatro condiciones de cada (lote, semilla, tarea).

La repetición prueba coherencia con lo registrado, no que no se consultó nada más. Eso lo cubren la auditoría
del módulo de siembra (sin imports del controlador, del evaluador ni de `benchmark`) y el test de invariancia:
en una copia del árbol con todas las anotaciones privadas rotadas entre tareas, y en otra sin
`benchmark/private/`, la recuperación de C_S de las nueve tareas no cambia.

El informe genérico de esta campaña se indexa por corte: `lexical-seed` (A, B y C_L) y `trace-seed` (A, B y
C_S), para que los pares con `NO_MEMORY` no mezclen las dos siembras. Los informes de las campañas publicadas
no cambian.

## Análisis pre-registrado

`python -m scripts.analyze_h8 --evidence <dir> [--reference evidence/reference-v2]` verifica el sello de cada
recibo con la biblioteca estándar y cita `generated_from`. Antes de cualquier veredicto comprueba la validez.
La campaña es **inválida** (la salida lo dice con su motivo, sin veredicto, y el código de salida es 1) si no
tiene la forma declarada (2 lotes × 6 semillas × 4 condiciones × 9 tareas, sin duplicados, lecciones solo del
entrenamiento verificado de su misma condición, un `memory_update` por entrenamiento con `ADD`), si hay un
recibo `ERROR`, si la réplica 2 difiere de la 1, o si A, B o C_L no reproducen la réplica 1 de la referencia
en alguna de sus 162 celdas. Se compara el plan, las lecciones expuestas y citadas por su tarea de origen, el
resultado y los intentos. Que el evaluador rechace el directorio también invalida la campaña; esa
comprobación es la orden anterior, no este script.

Sobre la réplica 1, por condición: `FA` e `Iter` por tipo (entrenamiento, original EXP-04..06, engañosa
EXP-07..09, nunca agregados) y por tarea, con numerador y denominador; la clase de la lección citada en las
engañosas (correcta, señuelo, otra, ninguna) con su tarea de origen; y el estado de la siembra de C_S por
tarea. El veredicto aplica la sección 5 del pre-registro: el primer intento según `Δ_ctrl = min(Δ_B, Δ_L)` y
`Δ_A` con margen de 3 ejecuciones de 18, la selección (`S ≤ 2` ejecuciones que citan el señuelo), la marca
«sin exposición» (menos de 3 ejecuciones citan una lección) y la regla secundaria de las originales
(`Δ_orig ≤ −3` es «con coste»). Reporta además si se cumplió la predicción de la sección 6.
