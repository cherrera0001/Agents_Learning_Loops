# Pre-registro · H6: memoria de fallos con revisión (#63)

**Registro**: el commit que introduce este archivo (C0), hecho **antes** de implementar la memoria de fallos y
antes de cualquier corrida identificada. Cambiar este documento después de ver datos de la campaña lo invalida
en ese punto, y toda desviación se reporta como tal en el informe de resultados.

**Carácter: exploratorio.** El autor conoce las 9 tareas, los resultados de referencia v2, H4 y la línea base
de diagnóstico de #58 ([resultados](../results/diagnostic-baseline.md)), que verificó de forma independiente.
**No** leyó `benchmark/private/`, no calculó similitudes entre las tareas ni corrió la política de esta
sección. No es una confirmación independiente.

Términos según el [glosario](../entorno/glosario.md). Condiciones sobre el agente de diagnóstico de #58:

| Condición | Lecciones (`ASSOCIATIVE_MEMORY`) | Memoria de fallos |
|---|---|---|
| **A** | no | no |
| **A_N** | no | sí |
| **C** | sí, congeladas en transferencia (igual que #58) | no |
| **C_N** | sí, congeladas en transferencia | sí |

## 1. Pregunta

> Con el diagnóstico público D de #58 fijo, ¿registrar los intentos fallidos y bajar la prioridad de esa
> estrategia en contextos similares evita **repetir un error ya observado** sin **contaminar** las decisiones de
> otras tareas?

Es el objetivo operativo del README. En #58 la memoria de lecciones aporta en las originales (+6/18) y
perjudica en EXP-08 (−2/18), pero no puede aprender de ese fallo: la transferencia está congelada y la única
operación de memoria es `ADD`.

## 2. Registro de fallo

Un **registro de fallo** se crea por cada intento de reparación cuyo test (`tests[i]`, `i ≥ 1`) falla, en
cualquier ejecución (entrenamiento y transferencia) de A_N y C_N. Contenido:

| Campo | Valor |
|---|---|
| `strategy` | la estrategia del intento fallido |
| `query` | la misma clave pública que usa la recuperación: `title + " " + context` de la tarea |
| `signature` | los rasgos que D extrae de `test-0` (`outcome`, `exception`, `none_marker` por bloque, en orden canónico) |
| `evidence` | `RUN-…#test-i` del intento fallido, en un recibo sellado |

Se publica en un recibo `memory_update` distinto del `task_run`, con la misma disciplina que `ADD`: solo se
escribe a partir de un recibo sellado cuyo test citado tiene `returncode ≠ 0`. Nunca usa `benchmark/private/`,
el id de la tarea como clave, parches dorados ni `tests` posteriores a la decisión que se toma.

## 3. Alcance y política

Un registro **aplica** a una decisión si se cumplen las dos condiciones:

1. `signature` es **idéntica** a la de `test-0` de la ejecución actual;
2. `cosine_similarity(query_actual, registro.query) ≥ τ`, con **τ = 0.5** y la misma función que usa
   `TEXT_HISTORY` (`associative_agent_loop.memory.text.cosine_similarity`).

`F` = conjunto de estrategias con al menos un registro que aplica. La política extiende la de #58 con una
clave más, **entre D y la lección**:

```text
plan = sorted(STRATEGIES, key=λop: (op ∉ S, op ∈ F, op ≠ p, prior.index(op)))
```

D acota, la memoria de fallos baja lo que ya falló en un contexto así, la lección ordena el resto y el prior
desempata. Con `F` vacío, el plan es exactamente el de #58 en esa condición. La memoria de fallos **nunca
elimina** operadores: el plan sigue siendo una permutación de los tres.

Se registra por ejecución `decision.failure_effect`:

- `none`: ningún registro aplica;
- `no_change`: aplican registros, pero el primer intento es el mismo que sin ellos;
- `changed_first`: los registros cambiaron el primer intento.

Y, para cada registro aplicado, si su origen es la **misma tarea** o **otra tarea** (el origen se lee del
recibo del registro, no se usa para decidir).

## 4. Secuencia

Por (semilla, condición), con memorias nuevas:

1. Entrenamiento EXP-01..03, igual que #58 (`ADD` de lecciones solo con `PASS` verificado).
2. **Pasada 1** de transferencia EXP-04..09. Las lecciones quedan congeladas desde la instantánea tras EXP-03.
3. **Pasada 2**, las mismas tareas en el mismo orden.

La memoria de fallos se actualiza **en línea** en las tres fases, después de cada ejecución. En A y C la
pasada 2 no tiene memoria nueva, así que debe reproducir la pasada 1: es el control de determinismo.

Semillas 1 4 5 6 7 9 y **2 réplicas**, como #58. Unidad primaria: la réplica 1. Si la réplica 2 difiere en
comportamiento, el análisis es inválido.

## 5. Métricas (definidas antes de los datos)

Tipos **original** (EXP-04..06) y **engañosa** (EXP-07..09), nunca agregados: 18 ejecuciones por tipo, pasada y
condición.

| Métrica | Numerador | Denominador | Origen |
|---|---|---|---|
| `FA` | ejecuciones con éxito al primer intento | ejecuciones | existente (#58) |
| `RepeatedFirstFailure` (pasada 2) | ejecuciones cuyo **primer** intento usa una estrategia que ya **falló** en la pasada 1 de la misma (semilla, tarea) | ejecuciones de la pasada 2 | experimental, nueva |
| `CrossTaskEffect` | primeros intentos cambiados por un registro de **otra** tarea, clasificados como `helped` (el nuevo primer intento tuvo éxito y el que habría sido no), `hurt` (al revés) o `neutral` | ejecuciones con `failure_effect = changed_first` | experimental, nueva |
| Intentos por tarea | intentos | ejecuciones | existente |

`helped` y `hurt` se deciden con el resultado observado del primer intento y el resultado del intento
desplazado **en la misma ejecución** (la política conserva la permutación, así que el desplazado se prueba
después). Si el desplazado no llegó a probarse, el caso es `neutral` con la marca `untested`.

## 6. Reglas de decisión

Pares (semilla, tarea) de la pasada 2, réplica 1: A_N frente a A y C_N frente a C.

- **H6a · No repetir.** Por celda (X ∈ {A, C}, tipo), con `R(·) = RepeatedFirstFailure` de la pasada 2:
  - celda **con holgura**, `R(X) ≥ 3/18`: se exige `R(X_N) ≤ R(X) − 3/18`;
  - celda **sin holgura**, `R(X) < 3/18`: se exige `R(X_N) ≤ R(X)`, y se reporta como nula por construcción.

  Apoyada si todas las celdas cumplen su condición y hay **al menos una** celda con holgura. «Sin holgura» si
  no hay ninguna. Refutada si alguna celda no cumple. Con los resultados de #58, que el autor conoce, C acierta
  18/18 al primer intento en las originales: esa celda será probablemente sin holgura.
- **H6b · No contaminar.** Apoyada si `FA(C_N) ≥ FA(C)` en las originales de **las dos pasadas**, y
  `CrossTaskEffect.hurt = 0` en las cuatro combinaciones de condición y pasada. Refutada si falla cualquiera.
- **H6c · Mejora en las engañosas.** Según el criterio de #58 sobre `FA(C_N) − FA(C)` en la pasada 2: «aporta»
  si es de +3/18 o más, «perjudica» si es de −3/18 o menos, «sin diferencia» en otro caso.
- **Conclusión de H6**: «aprendió de su error sin contaminar» solo si H6a **y** H6b están apoyadas. Si no, se
  publica cuál falla.

Transferencia y repetición se separan: la mejora de la pasada 2 frente a la 1 en la **misma** tarea es
aprendizaje por repetición (el objetivo del README), no transferencia. Solo `CrossTaskEffect.helped` cuenta
como transferencia de un fallo, y solo `hurt` como contaminación.

## 7. Predicciones (antes de implementar, cualitativas)

- **PF1**: H6a apoyada. La repetición es determinista y los registros de la misma tarea aplican con τ = 0.5,
  porque la similitud de una clave consigo misma es 1.
- **PF2**: H6b apoyada, con poca holgura para probarla. Exigir la misma `signature` debería impedir casi todos
  los efectos entre tareas. Espero pocos o ningún `CrossTaskEffect`, y eso **no** prueba ausencia de
  contaminación con otra política de alcance.
- **PF3**: H6c «aporta» en la pasada 2. Los fallos de la pasada 1 en las engañosas, incluido el señuelo de
  EXP-08, no se repiten.
- **PF4**: la pasada 1 de A_N y C_N es igual a la de A y C, salvo que un registro de entrenamiento aplique
  (misma `signature` y similitud ≥ 0.5).

## 8. Orden de commits

- **C0**: este documento.
- **C1**: registro de fallo, política, condiciones opt-in, receta de campaña `failure-memory-v1`, verificaciones
  del evaluador, `scripts/analyze_failure_memory.py` y tests sintéticos, **sin campaña**.
- Revisión del orquestador con medios propios. Solo después, la campaña en `evidence/failure-memory-v1/` y los
  resultados generados en `results/failure-memory-v1/`.

Ni este documento ni el análisis se modifican después de la campaña. La ruta DEFAULT y las recetas anteriores
(`run`, `reference-v2`, `diagnostic-baseline-v1`, `analyze_h4`, `analyze_diagnostic_baseline`) no cambian.

## 9. Límites declarados

- τ = 0.5 y la exigencia de `signature` idéntica son una sola política de alcance, fijada sin ver similitudes.
  Otra política puede contaminar o transferir distinto.
- Nueve tareas de un proyecto, tres operadores, D fijo y un diseño exhaustivo y determinista: conteos exactos,
  sin inferencia estadística. Las réplicas no son muestras independientes.
- La pasada 2 repite tareas ya vistas. Mide si el sistema deja de repetir un error, no si generaliza.
