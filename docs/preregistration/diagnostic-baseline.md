# Pre-registro · Línea base de diagnóstico público (#58)

**Registro**: el commit que introduce este archivo, hecho **antes** de implementar el diagnóstico y antes de
cualquier corrida identificada. Cambiar este documento después de ver datos de la campaña lo invalida en ese
punto, y toda desviación se reporta como tal en el informe de resultados.

**Carácter: exploratorio.** El autor conoce las 9 tareas, la tabla pública de familias de las tareas engañosas
([protocolo](../../specs/software_learning_protocol.md), *Misleading tasks*) y los resultados publicados de la
campaña de referencia v2 y de H4 ([resultados H4](../results/h4-associative-vs-history.md)). Leyó
`benchmark/public/`, la aplicación bajo reparación y el solver acotado. **No** leyó `benchmark/private/` ni la
salida de reproducción (`stderr`) de ningún recibo. Las reglas de la sección 2 se derivan de la regla pública
de cada operador y de la semántica de las excepciones de Python, sin ajustarlas a salidas observadas, pero su
elección no es ciega. No es una confirmación independiente.

Términos según el [glosario](../entorno/glosario.md). Condiciones: A = `NO_MEMORY`, B = `TEXT_HISTORY`,
C = `ASSOCIATIVE_MEMORY`.

## 1. Pregunta y alcance

> Con el **mismo diagnóstico público** D del fallo en las tres condiciones, ¿la experiencia previa (B, C)
> mejora la selección de operadores frente a no tenerla (A)?

D es una base diagnóstica **limitada**: tres reglas sobre la clase de la excepción. No es una línea base fuerte
en general. La utilidad de la memoria se mide **sobre esta base**, en estas tareas.

| Se mantiene (igual que referencia v2) | Cambia (solo opt-in) |
|---|---|
| 3 operadores y sus parches (`change()`), presupuesto 3, timeout de 20 s | Agente `bounded-ast-repair-v1+diagnostic-v1`, que lee la reproducción antes de decidir |
| Conjunto `misleading-v1` (9 tareas), semillas 1 4 5 6 7 9, 2 réplicas | `plan()` combina D, memoria y prior (sección 3) |
| Clave de recuperación `title + context` y contenido de la memoria | Campos aditivos en `decision` (sección 9) |
| Recibos `software-learning-receipt/v2`, hashes `lf/v1`, anotaciones privadas | Campaña `diagnostic-baseline-v1` en un directorio nuevo |
| Ruta **DEFAULT**: `BoundedRepairAgent`, el orden del runner y los valores por defecto de la CLI | — |
| Recetas antiguas: `run` (7 11 23, v1), `run --campaign reference-v2`, piloto, CI `--task-set v1 --seeds 7`, `evaluate`, `compare`, `reproduce`, `scripts.analyze_h4` | — |

## 2. Diagnóstico D

**Señal.** Solo el `stderr` de `test-0`: la ejecución de los tests públicos (el de aceptación de la tarea y
`test_business.py`) sobre el workspace con el defecto, antes de cualquier decisión y de cualquier parche. El
harness ya la ejecuta hoy en las tres condiciones. Se deriva del código visible y de tests públicos.

**Descartado.** `stdout`, nombres y cabeceras de tests, rutas, nombres de funciones y módulos de la
aplicación, líneas de código del traceback, el texto del mensaje (salvo el marcador `NoneType`), el
identificador de la tarea, anotaciones privadas, parches y `tests[1:]`. Motivo observable en archivos
públicos: EXP-08 y EXP-09 tienen el mismo test de aceptación, así que una regla basada en tests o rutas no
puede separarlos.

**Extracción (determinista).**

1. Normalizar con `normalize_source` (sin BOM; CRLF/CR → LF).
2. Separar por líneas de 20 o más `=`. Un bloque empieza por `ERROR: ` o `FAIL: `. El resumen final (guiones
   seguidos de `Ran `) se corta.
3. La excepción terminal de un bloque es la primera línea no vacía y sin sangría que sigue al **último** marco
   `File "…", line N, in …`. Sin marcos, la excepción es `null`.
4. Rasgos del bloque: `outcome` (ERROR/FAIL), `exception` (nombre calificado antes del primer `:` si es un
   identificador válido; si no, `null`) y `none_marker` (`\bNoneType\b` en esa línea). Se registran solo los
   rasgos, sin duplicados y en orden canónico. El texto crudo queda en `tests[0]`, como hoy.

**Reglas `diagnostic-rules/v1`.** La clase se resuelve en `builtins` y se compara con `issubclass`. «Símbolos
públicos» son solo nombres de Python y de su biblioteca estándar.

| Modo de fallo | Condición del bloque | Candidatos |
|---|---|---|
| Almacenamiento no disponible | subclase de `ConnectionError`, o módulo `sqlite3` | `initialize_storage` |
| Valor ausente usado | subclase de `TypeError` o `AttributeError`, con `none_marker` | `validate_optional_identity`, `normalize_environment` |
| Contrato incumplido | subclase de `AssertionError` | los tres |
| Otro (`null`, excepciones de la aplicación, otras clases) | — | los tres |

Justificación por la regla pública de cada operador (`RULES` en `agent.py`): validar una identidad opcional
«before accessing its fields»; resolver valores de entorno «missing or empty … before using them»; inicializar
el almacenamiento «before the first dependent operation».

**Combinación y estados.** `S` = intersección de los candidatos de todos los bloques.

| Estado | Condición | Efecto |
|---|---|---|
| `decisive` | `|S| = 1` | D fija el primer intento |
| `partial` | `|S| = 2` | D acota y la memoria y el prior eligen dentro de `S` |
| `ambiguous` | `|S| = 3` (`no_discrimination`), `S` vacío (`conflict`) o ningún bloque (`no_failure_block`) | **Fallback explícito**: `S` = los tres, y el plan es exactamente el DEFAULT de esa condición |

**Sesgos declarados.** Una capa de almacenamiento que expusiera un manejador `None` se clasificaría como
«valor ausente». Un valor de entorno usado como dirección de red se clasificaría como «almacenamiento». Un
`TypeError` sin `NoneType` no aporta información. D nunca elimina operadores: solo reordena.

## 3. Política conjunta

Una sola clave, igual en A, B y C:

```text
prior = prior_order(seed)                          # sin cambios (#44)
p     = estrategia de la lección citada (la misma que elegiría DEFAULT), o None
plan                = sorted(STRATEGIES, key=λop: (op ∉ S, op ≠ p, prior.index(op)))
plan_without_memory = sorted(STRATEGIES, key=λop: (op ∉ S, prior.index(op)))
```

El diagnóstico acota, la memoria ordena dentro de lo acotado y el prior desempata. Con `S` igual a los tres
operadores, la fórmula da exactamente el plan DEFAULT.

- **Cobertura, no garantía.** `plan` sigue siendo una permutación de los tres operadores y cada intento parte
  de la misma fuente. Eso conserva la cobertura del plan y permite **predecir** el mismo éxito final que
  DEFAULT en estas fixtures (predicción PD5). No garantiza éxito en cualquier caso ni con cualquier parche.
- **Opacidad declarada.** Con `decisive`, el primer intento coincide necesariamente en A, B y C: la memoria
  solo puede cambiar los intentos 2 y 3. Con `partial`, la memoria decide el primer intento solo si `p ∈ S`.
  Con `ambiguous`, la memoria actúa igual que en DEFAULT.
- **Efecto de la memoria por ejecución** (`decision.memory_effect`, evaluado en este orden):
  - `no_proposal`: no hay lección citada (siempre en A);
  - `vetoed`: el estado no es `ambiguous` y `p ∉ S`;
  - `confirmed`: `p` coincide con `plan_without_memory[0]`;
  - `changed_first`: la memoria cambió el primer intento.
- `decision.memory_ids` sigue siendo la lección citada, aunque quede vetada; `memory_effect` distingue los
  casos.

## 4. Recuperación y comparación B/C

La clave no cambia: B ordena las lecciones por similitud con `title + context` y C siembra la propagación con
`PublicTask.query()`. D no entra en la recuperación, y las lecciones y el grafo conservan su contenido y su
topología. B y C reciben así el mismo contenido bajo la misma clave y con el mismo D. **No se presupone
empate**: B y C empatan en un par solo si su plan (o su primer intento) resulta igual para los insumos
observados; lo que recupera cada condición es un resultado, no una premisa.

## 5. Temporalidad y congelamiento

**Dentro de una ejecución** (solo en el agente de diagnóstico):

1. `prepare`;
2. `RETRIEVE`, desde la instantánea congelada en transferencia;
3. **`test-0`** sobre el workspace intacto;
4. `plan()`, una sola vez, con la tarea, las fuentes, las lecciones y `test-0`;
5. hasta 3 intentos que parten de la fuente inicial. `tests[1:]` nunca realimentan el plan.

La ruta DEFAULT conserva su orden actual (`plan` antes de `test-0`). La tabla de fases del runner no cambia.
El recibo registra el orden (`decision_inputs`), y el evaluador vuelve a ejecutar la decisión desde lo
registrado (tarea, lecciones, `seed` y `test-0`) y exige que coincida con la decisión registrada.

**Congelamiento.** Entrenamiento con EXP-01..03 y memoria nueva por (semilla, condición); transferencia con
EXP-04..09 desde la instantánea tras EXP-03; `ADD` solo con `PASS` verificado. D no tiene estado ni aprende: la
memoria es el único portador de experiencia entre tareas. No hay revisión persistente
(`UPDATE`/`MERGE`/`DEPRECATE`), así que una lección que engaña no se degrada.

**Orden de commits.**

- **C0**: este documento.
- **C1**: el diagnóstico y el agente opt-in, la receta de campaña, las verificaciones aditivas del evaluador,
  `scripts/analyze_diagnostic_baseline.py`, los tests sintéticos y un suplemento del protocolo.
- Revisión del supervisor. Solo después, la campaña en un directorio nuevo y los resultados generados.

Ni este documento ni el análisis se modifican después de la campaña. Los recibos citan el commit que los
produjo (`git_commit`), que debe seguir alcanzable en el historial.

## 6. Campaña, datos y denominadores

| Concepto | Valor |
|---|---|
| Receta | `python -m experiments run --campaign diagnostic-baseline-v1` (fija semillas, réplicas, conjunto y agente) |
| Directorios | `evidence/diagnostic-baseline-v1/` (recibos) y `results/diagnostic-baseline-v1/` (agregados). Ambos son nuevos y no se sobrescribe nada |
| Semillas y réplicas | 1 4 5 6 7 9 (cada permutación del prior una vez) · 2 réplicas de la misma semilla, que comprueban determinismo y no son muestras independientes |
| Recibos | 324 `task_run` (6 × 2 × 3 × 9) + 72 `memory_update` (6 × 2 × 2 × 3) = 396 |
| Unidad primaria | Réplica 1 (la primera por `batch_id`). La réplica 2 debe ser idéntica en comportamiento; si no, el análisis es inválido |
| Pares | (semilla, tarea): X ∈ {B, C} frente a A, con el mismo workspace, hashes, presupuesto, agente y D. Tipos **original** (EXP-04..06) y **engañosa** (EXP-07..09): 18 pares cada uno por condición, **nunca agregados**. Entrenamiento (EXP-01..03): descriptivo |

## 7. Análisis (implementado en C1, antes de los datos)

**Primario.** Por tipo (original, engañosa) y por X ∈ {B, C}: `FA(X) = n_X/18` y `FA(A) = n_A/18`, éxitos al
primer intento, con numerador y denominador exactos. Se reporta la diferencia `FA(X) − FA(A)` en ejecuciones y
en tasa. Criterio de lectura, que adopta localmente el margen de H4 por continuidad y es un **criterio
exploratorio, no significancia**:

- «aporta» si la diferencia es de +3/18 o más;
- «perjudica» si es de −3/18 o menos;
- «sin diferencia» en otro caso;
- «inválido» si las réplicas no coinciden o falta un denominador.

**Complementario** (no reemplaza a la diferencia de FA ni condiciona el veredicto):

- **Pares** clasificados primero por éxito y después por intentos, solo si ambos tuvieron éxito: positivo,
  negativo o nulo. Un nulo se marca **por construcción** si los planes de X y A son idénticos, o si el primer
  intento coincide necesariamente (D `decisive` o X sin propuesta) y tuvo éxito. En otro caso es un nulo
  observado.
- **Holgura**: pares por estado de D y por `memory_effect`, y pares con primer intento forzado. Se reporta
  junto a los mismos 18 pares, **sin filtrar denominadores**.
- **Intentos por tarea** y su diferencia frente a A.
- **B frente a C**: diferencia de FA y clasificación de pares. Se cuentan los pares con plan idéntico.
- **Entrenamiento**: FA e intentos, solo descriptivos.
- **Coste** por condición y tipo: tests ejecutados (incluida la reproducción), intentos y tiempo. El tiempo
  nunca es prueba de mejora.
- **Lecciones**: expuestas (`retrieval.memories`), citadas (`memory_ids`), vetadas, confirmadas y aplicadas
  (`changed_first`), cada una por separado.

**Interpretación.** Los nulos por construcción no son argumento sobre la memoria. Un empate B/C con planes
iguales refleja los insumos observados y no evalúa el grafo más allá de la clave léxica. Los resultados son
conteos exactos de un diseño exhaustivo y determinista, condicionales a D, a la clave léxica y a estas 9 tareas;
no admiten inferencia estadística. No se concluye irrelevancia universal del grafo ni ausencia universal de
aprendizaje. Se publican todos los resultados, incluidos los nulos, los negativos y los inválidos.

## 8. Predicciones (antes de los datos, cualitativas)

- **PD1 · D.** Espero `decisive` en los fallos que lanza la capa de almacenamiento, `partial` en los errores
  sobre `NoneType` y `ambiguous` donde solo hay fallos de aserción (probablemente EXP-08: «no error is
  raised»). Es menos segura en EXP-01, EXP-06 y EXP-09, cuyo texto no nombra la excepción.
- **PD2 · Original.** Espero «aporta» para B y C, porque la memoria cita la familia correcta en estas tareas.
- **PD3 · Engañosa.** Espero que D vete el señuelo cuando la clase de excepción excluye su operador, y que la
  memoria perjudique donde D es ambiguo. Espero «perjudica» o «sin diferencia», y no «aporta».
- **PD4 · B frente a C.** Espero planes iguales en transferencia, porque las citas publicadas en H4 coincidían.
  Es una predicción, no una premisa.
- **PD5 · Éxito final.** Espero el mismo éxito final que DEFAULT (sección 3).
- **PD6 · Recuperación.** Espero las mismas lecciones expuestas y citadas que en referencia v2.

## 9. Contrato y compatibilidad

- **Recibos.** Se mantiene `software-learning-receipt/v2` con `lf/v1`. Los hashes de fuente y de tests se
  calculan igual y son comparables por tarea con referencia v2.
- **Campos nuevos**, solo con el agente de diagnóstico:
  - en `decision`: `policy` (`diagnostic-baseline/v1`), `diagnostic` (reglas, hash de reglas, rasgos, modos,
    candidatos, estado y motivo), `plan_without_memory`, `memory_proposal` y `memory_effect`;
  - en el recibo: `decision_inputs` (el orden);
  - en el contexto hasheado: la reproducción que ve el solver (`returncode`, `stderr`).
- **Campos existentes.** Conservan su significado: `without_memory = plan_without_memory[0]` e
  `influenced_by_memory = plan ≠ plan_without_memory`, que en DEFAULT coinciden con la fórmula actual. Los
  recibos DEFAULT no ganan ninguna clave.
- **Evaluador** (aditivo). Rechaza mezclar agentes o políticas en una evaluación, vuelve a ejecutar cada
  decisión de diagnóstico desde el recibo y exige el mismo D en A, B y C por (lote, semilla, tarea). El informe
  de las campañas publicadas no cambia.
- **Contrato.** El solver de este agente recibe además la salida de `test-0`. Se documenta en un suplemento
  nuevo del protocolo, enlazado con una línea, sin reescribir el texto histórico.

## 10. Verificaciones y límites

**Verificaciones (C1).**

- El código cargado es el de este worktree, y `git_commit()` es su `HEAD`.
- DEFAULT sin cambios: `agent.py` sin diff, claves y orden del runner históricos, y la evaluación publicada
  idéntica.
- El fallback con D ambiguo es igual a DEFAULT para las 6 semillas, con y sin lección.
- Auditoría genérica del módulo de D: sin identificadores de tarea, sin rutas privadas y sin imports del
  controlador ni del evaluador.
- Casos negativos con trazas **sintéticas**: excepción de la aplicación, `TypeError` sin `NoneType`, sin
  bloques, conflicto, excepciones encadenadas, CRLF y rutas distintas.
- El plan no cambia si se altera `tests[1:]`; alterar `test-0` sí cambia D.
- El evaluador rechaza un D alterado, un plan alterado y la mezcla de políticas.
- El análisis puede llegar a «aporta», «perjudica», «sin diferencia» e «inválido».
- Hay mutaciones que cada guarda debe detectar, tras un control en verde.
- Ningún test exige ganancia positiva.

**Fuera de alcance.** Un oráculo o test de aplicabilidad de operadores (que trivializaría la pregunta), una
reevaluación de D sobre campañas históricas, cambiar la clave de recuperación, la revisión persistente de
lecciones, y tareas u operadores nuevos.

**Límites.** D se eligió conociendo las tareas y puede dejar poca holgura a la memoria. B y C comparten una
clave léxica. El analizador depende del formato de `unittest` y de las versiones de Python probadas en CI
(3.11–3.14). El diseño cubre un solo proyecto con 9 tareas, 6 permutaciones y 2 réplicas deterministas.
