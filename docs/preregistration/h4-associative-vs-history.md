# Pre-registro · H4: memoria asociativa vs. historial textual (#46)

**Registrado**: 2026-09-29, **antes** de conocer los resultados de las tareas engañosas (#45) y de la
campaña de referencia (#44). El commit que introduce este archivo es la marca temporal verificable.
Cambiar este documento después de ver los datos invalida el pre-registro. Toda desviación se reporta
como tal en el informe de resultados.

## Pregunta

En el Experimento 1, B (`TEXT_HISTORY`) y C (`ASSOCIATIVE_MEMORY`) empatan en resultado (1.0 intentos
por tarea de transferencia). C es más precisa (1.0 frente a 0.333), pero con solo 3 lecciones y tareas
sin distractores efectivos esa precisión no se traduce en resultado. ¿Aparece una diferencia de
**resultado** cuando la tarea ofrece un señuelo plausible?

## Hipótesis

- **H4a (precisión → resultado)**: en las tareas engañosas (EXP-07..09 de #45), el éxito al primer
  intento de C es **mayor o igual** que el de B.
- **H4b (transferencia negativa)**: en la partición de entrenamiento, la tasa de transferencia negativa
  de C es **menor o igual** que la de B.
- **H0**: B y C no difieren en ninguna de las dos métricas.

Predicción del orquestador, registrada para contrastarla: **no espero una ventaja fuerte de C en H4a**.
Ambas condiciones siembran la recuperación **léxicamente**, así que un texto diseñado para sugerir la
familia equivocada debería desviar a las dos. Espero que H4b se mantenga en la dirección observada en la
verificación (B con transferencia negativa en 2 tareas de entrenamiento y C en 1), con una diferencia
pequeña.

## Diseño

- **Campaña**: la de referencia de #44, con las 9 tareas (6 originales y 3 engañosas), las 6
  permutaciones del prior (semillas 1, 4, 5, 6, 7, 9), una réplica por semilla y hashes normalizados
  (#42).
- **Pareo**: cada ejecución de B y de C se compara con la de A (`NO_MEMORY`) de la misma semilla y tarea.
- **Determinismo**: las 6 semillas cubren exhaustivamente los órdenes del prior; no hay muestreo. Los
  resultados son **conteos exactos**, no estimaciones, y no se aplica ninguna prueba de significancia.

## Métricas (definidas antes de ver los datos)

| Métrica | Numerador | Denominador | Indefinido |
|---|---|---|---|
| `FirstAttemptSuccess(tareas engañosas)` | ejecuciones engañosas con éxito al primer intento | ejecuciones engañosas | `null` si no hay |
| `MisleadingRetrievalRate` | lecciones de la familia señuelo recuperadas | lecciones recuperadas en tareas engañosas | `null` |
| `NegativeTransferRate(entrenamiento)` | pares donde la condición falla al primer intento y A acierta | pares de entrenamiento con recuperación | `null` |
| `PositiveTransferRate(entrenamiento)` | pares donde la condición acierta al primer intento y A falla | ídem | `null` |

## Reglas de decisión

Con 3 tareas engañosas × 6 semillas = 18 ejecuciones por condición:

- **H4a apoyada** si `FA(C) − FA(B) ≥ 3/18`, es decir, al menos 3 ejecuciones de diferencia (equivale
  a una tarea completa en la mitad de las semillas).
- **H4a refutada** si `FA(C) < FA(B)`.
- **Sin diferencia** si `0 ≤ FA(C) − FA(B) < 3/18`.
- **H4b**: se reportan los conteos exactos de ambas tasas; se considera **apoyada** solo si
  `NT(C) < NT(B)` en al menos 3 pares de diferencia.

Todos los resultados se publican, incluidos los nulos y los negativos, con recibos, denominadores y
desglose por tarea.

## Fuera de alcance

No se varía el número de distractores más allá del que aportan las tareas existentes. Un barrido de
*k* distractores requiere tareas de entrenamiento adicionales y queda como trabajo futuro si H4a resulta
no concluyente.
