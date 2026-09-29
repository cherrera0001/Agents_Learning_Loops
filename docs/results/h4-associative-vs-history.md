# Resultados · H4: memoria asociativa vs. historial textual (#46)

**Veredicto: H4 no se sostiene en este diseño.** Con señuelos sin pistas léxicas, la memoria asociativa
(C) no obtiene mejor resultado que el historial textual (B). Las dos rinden peor que no usar memoria.

## Trazabilidad

| Paso | Commit | Hora (−03:00) | Contenido |
|---|---|---|---|
| Pre-registro | `6c9a1a3` | 16:37 | Hipótesis, métricas, reglas de decisión y predicción del orquestador |
| Código de análisis | `4c337e2` | 17:11 | [`scripts/analyze_h4.py`](../../scripts/analyze_h4.py) y sus tests, antes de que existiera la campaña |
| Datos | `7f22a1e` (código `62d6ff7`) | 17:35 | Campaña de referencia v2: [`evidence/reference-v2/`](../../evidence/reference-v2/), 396 recibos (#44) |

`git diff 4c337e2 HEAD -- scripts/analyze_h4.py docs/preregistration` está vacío: ni el análisis ni el
pre-registro cambiaron después de ver los datos.

Reproducir: `python -m scripts.analyze_h4 --evidence evidence/reference-v2`.

## Datos

Campaña: 9 tareas, 6 permutaciones del prior (semillas 1, 4, 5, 6, 7, 9), 2 réplicas y recibos v2 con
hashes portables. Las réplicas son consistentes en comportamiento y el análisis usa una por semilla, como
fija el pre-registro. Verificación independiente de la campaña (antes del merge): 396 recibos íntegros,
0 fugas, 0 diferencias de métricas, 9/9 tareas reproducidas y reparadas, y el manifiesto de fuentes
coincide 76/76 con `62d6ff7`.

| Métrica pre-registrada | A · Sin memoria | B · Historial | C · Asociativa |
|---|---|---|---|
| Éxito al primer intento en tareas engañosas | 6/18 (0.33) | **0/18** | **0/18** |
| Tasa de transferencia negativa en entrenamiento | — | 4/12 (0.33) | 2/6 (0.33) |
| Tasa de transferencia positiva en entrenamiento | — | 0/12 | 0/6 |

Lecciones recuperadas en las tareas engañosas (EXP-07..09):

| Condición | EXP-07 (real AUTH, señuelo READINESS) | EXP-08 (real CONFIG, señuelo AUTH) | EXP-09 (real READINESS, señuelo CONFIG) |
|---|---|---|---|
| B · Historial (expuestas) | EXP-01, 02, 03 | EXP-01, 02, 03 | EXP-01, 02, 03 |
| B · Historial (citada) | EXP-03 · señuelo | EXP-01 · señuelo | EXP-02 · señuelo |
| C · Asociativa (expuesta y citada) | EXP-03 · señuelo | EXP-01 · señuelo | EXP-02 · señuelo |

## Decisión (reglas pre-registradas)

| Hipótesis | Regla | Resultado | Decisión |
|---|---|---|---|
| **H4a**: FA(C) ≥ FA(B) con un margen de al menos 3 ejecuciones | apoyada si C − B ≥ 3; refutada si C − B < 0 | C − B = **0** | **Sin diferencia** |
| **H4b**: NT(C) < NT(B) por al menos 3 pares | apoyada si B − C ≥ 3 pares | B − C = **2** pares; tasas **iguales** (1/3 y 1/3) | **No apoyada** |
| **H0**: no difieren en ninguna métrica | — | Iguales en FA y en tasa de NT; difieren solo en el conteo bruto de NT (denominadores distintos) | Compatible en tasas |

**Predicción registrada** (antes de los datos): «no espero una ventaja fuerte de C en H4a; ambas condiciones
siembran léxicamente». **Se cumplió.** También predije que H4b mantendría la dirección observada en la
verificación (B con más transferencia negativa que C): se cumple en conteos (4 frente a 2), pero **no en
tasa**, así que no la considero confirmada.

## Desviación declarada

El pre-registro define `MisleadingRetrievalRate` como «lecciones de la familia señuelo recuperadas / lecciones
recuperadas», sin precisar si *recuperadas* significa **expuestas** al solver o **citadas** en su decisión.
`analyze_h4.py` implementó la lectura *expuestas*. El evaluador de #45 usa *citadas*. Se reportan las dos;
**ninguna regla de decisión depende de esta métrica**, así que la ambigüedad no afecta al veredicto.

| Lectura | B · Historial | C · Asociativa |
|---|---|---|
| Expuestas (`analyze_h4.py`, una réplica) | 18/54 (0.33, por construcción: el historial expone todo) | 18/18 (1.0) |
| Citadas (evaluador #45, ambas réplicas) | 36/36 (1.0) | 36/36 (1.0) |

## Interpretación

1. **La mayor precisión de C no se convierte en resultado.** C expone una sola lección, pero es la misma que
   B termina citando: ambas condiciones ordenan por similitud léxica con el texto del issue. Cuando el texto
   apunta a la familia equivocada, las dos eligen el señuelo el 100 % de las veces.
2. **La memoria puede perjudicar.** En tareas engañosas, las dos condiciones con memoria aciertan al primer
   intento el 0 % de las veces, frente al 33 % sin memoria, y necesitan 2.5 intentos frente a 2.0 (#44).
   El beneficio de la memoria en las tareas originales (2.0 → 1.0) depende de que el texto del issue
   contenga pistas léxicas de la causa correcta.
3. **La transferencia negativa en entrenamiento existe en las dos condiciones** con la misma tasa (1/3 de
   los pares con recuperación). El hallazgo exploratorio de la verificación («B en 2 tareas, C en 1») no se
   confirma como diferencia de tasa.

## Alcance

Un solver acotado con 3 operadores, 9 tareas de un solo proyecto, 6 permutaciones deterministas y
recuperación léxica en las dos condiciones. Los resultados son **conteos exactos** de un diseño exhaustivo,
no estimaciones, y no admiten inferencia estadística más allá de este diseño. No se evaluó recuperación
semántica ni causal (por ejemplo, embeddings del código o de la traza de error): la conclusión es que
**la asociación sobre las mismas señales léxicas no supera al historial**, no que ninguna memoria
asociativa pueda hacerlo.

## Trabajo futuro (sin issue abierto)

- Sembrar la recuperación con señales no léxicas del problema: la traza de la excepción, el componente
  inspeccionado o el embedding del código, y repetir H4 con estas mismas tareas engañosas.
- Barrer *k* distractores con tareas de entrenamiento adicionales, fuera del alcance de este pre-registro.
