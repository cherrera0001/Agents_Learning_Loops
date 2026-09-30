# Resultados · Línea base de diagnóstico público (#58)

**Lectura exploratoria.** Con el mismo diagnóstico público D en las tres condiciones, la experiencia previa
**aporta en las tareas originales** (+6/18 al primer intento, tanto en B como en C). En las **tareas
engañosas no hay diferencia** según el criterio pre-registrado (−2/18 en B y en C). La utilidad se mide
**sobre esta base diagnóstica limitada** (tres reglas sobre la clase de la excepción), en estas 9 tareas:
no es una línea base fuerte en general ni una conclusión sobre el aprendizaje en general.

## Trazabilidad

| Paso | Commit | Hora (−03:00) | Contenido |
|---|---|---|---|
| Pre-registro (C0) | `1ed70e0` | 21:48 | [`docs/preregistration/diagnostic-baseline.md`](../preregistration/diagnostic-baseline.md): D, política conjunta, análisis y predicciones PD1–PD6 |
| Implementación y análisis (C1) | `4a0baaa` | 22:16 | Agente opt-in, receta de campaña, verificaciones del evaluador, [`scripts/analyze_diagnostic_baseline.py`](../../scripts/analyze_diagnostic_baseline.py) y tests, sin campaña |
| Guardas corregidas | `0d90edc` | 22:34 | Validación cerrada de la campaña en el análisis, `decision_inputs` exacto y coherencia agente↔política, tras la revisión del supervisor |
| Datos | `evidence/diagnostic-baseline-v1/` (código `0d90edc`) | 22:36–22:39 | Una sola campaña: 396 recibos |

`git diff 1ed70e0 -- docs/preregistration` y `git diff 0d90edc -- src scripts` están vacíos en el commit de
los datos: ni el diseño, ni las reglas de D, ni el análisis cambiaron después de ver los datos.

Reproducir:

```bash
python -m experiments run --campaign diagnostic-baseline-v1 --evidence-dir <directorio nuevo>
python -m experiments evaluate --evidence-dir evidence/diagnostic-baseline-v1 --output results/diagnostic-baseline-v1
python scripts/analyze_diagnostic_baseline.py --evidence evidence/diagnostic-baseline-v1
```

La salida del tercer comando es [`results/diagnostic-baseline-v1/diagnostic_analysis.json`](../../results/diagnostic-baseline-v1/diagnostic_analysis.json),
generada por el script y sin editar. Incluye el hash de cada recibo que la produjo (`generated_from`).

## Datos

| Comprobación | Resultado |
|---|---|
| Recibos | 324 `task_run` + 72 `memory_update` = 396, esquema `software-learning-receipt/v2`, hashes `lf/v1`, 396/396 sellos válidos |
| Resultado de las ejecuciones | 324 `PASS`, 0 `FAIL`, 0 `ERROR` |
| Código | los 324 `task_run` citan `git_commit` = `0d90edc` |
| Agente y política | `bounded-ast-repair-v1+diagnostic-v1` / `diagnostic-baseline/v1` en los 324; `decision_inputs` exacto en los 324 |
| Réplicas | 2 lotes completos; el evaluador encuentra 162/162 grupos replicados con proyecciones iguales y el análisis, `replicates_consistent: true` |
| Validación del análisis | 9 tareas × 3 modos × 6 semillas en cada lote, sin duplicados, particiones, procedencia de lecciones y biyección de `memory_update` |
| Comparabilidad con referencia v2 | 162/162 celdas con los mismos hashes de fuente inicial y de aceptación |

Unidad primaria: la réplica 1 (`BATCH-660dd8b5…`). La réplica 2 es idéntica en comportamiento y **no se suma**
como muestra independiente. Las familias original y engañosa se leen por separado y **nunca se agregan**.
El `README.md` y el `experiment1.json` que genera el evaluador en `results/diagnostic-baseline-v1/` suman las
dos réplicas de transferencia, original y engañosa (72 ejecuciones por condición): sirven para la auditoría genérica, no
para esta lectura.

## Resultado primario (18 pares por tipo y condición)

Éxito al primer intento (FA), con numeradores exactos. La diferencia se mide frente a A en los mismos pares
(semilla, tarea).

| Tipo | A · Sin memoria | B · Historial | C · Asociativa | B − A | C − A | Lectura B | Lectura C |
|---|---|---|---|---|---|---|---|
| Original (EXP-04..06) | 12/18 (0.67) | 18/18 (1.00) | 18/18 (1.00) | **+6** (+0.33) | **+6** (+0.33) | **aporta** | **aporta** |
| Engañosa (EXP-07..09) | 11/18 (0.61) | 9/18 (0.50) | 9/18 (0.50) | **−2** (−0.11) | **−2** (−0.11) | **sin diferencia** | **sin diferencia** |

Criterio de lectura pre-registrado: «aporta» si la diferencia es de +3/18 o más, «perjudica» si es de −3/18 o
menos. Es un criterio exploratorio, no significancia. Las −2/18 de las engañosas quedan dentro de la banda
«sin diferencia», aunque su signo es negativo.

## Complementario

**Pares** (clasificados por éxito y después por intentos):

| Comparación | Positivos | Negativos | Nulos por construcción | Nulos observados |
|---|---|---|---|---|
| Original · B frente a A | 6 | 0 | 12 | 0 |
| Original · C frente a A | 6 | 0 | 12 | 0 |
| Engañosa · B frente a A | 0 | 3 | 14 | 1 |
| Engañosa · C frente a A | 0 | 3 | 14 | 1 |
| Original · C frente a B | 0 | 0 | 18 | 0 |
| Engañosa · C frente a B | 0 | 0 | 18 | 0 |

Los nulos por construcción (planes idénticos, o primer intento forzado y exitoso) no son argumento a favor ni
en contra de la memoria.

**Holgura** (sobre los mismos 18 pares, sin filtrar denominadores):

| Tipo | Estado de D | Primer intento forzado | Planes idénticos X = A | Efecto de la memoria en B y en C |
|---|---|---|---|---|
| Original | 6 `decisive` · 12 `partial` | 6 | 12 | 6 `changed_first` · 12 `confirmed` |
| Engañosa | 6 `decisive` · 6 `partial` · 6 `ambiguous` | 6 | 11 | 4 `changed_first` · 2 `confirmed` · 12 `vetoed` |

**Por tarea** (réplica 1, 6 semillas; lecciones citadas iguales en B y en C):

| Tarea | D | Lección citada | Efecto de la memoria | FA A | FA B | FA C |
|---|---|---|---|---|---|---|
| EXP-04 | `partial` (valor ausente) | EXP-01 | 3 `changed_first`, 3 `confirmed` | 3/6 | 6/6 | 6/6 |
| EXP-05 | `partial` (valor ausente) | EXP-02 | 3 `changed_first`, 3 `confirmed` | 3/6 | 6/6 | 6/6 |
| EXP-06 | `decisive` (almacenamiento) | EXP-03 | 6 `confirmed` | 6/6 | 6/6 | 6/6 |
| EXP-07 | `partial` (valor ausente) | EXP-03 · señuelo | 6 `vetoed` | 3/6 | 3/6 | 3/6 |
| EXP-08 | `ambiguous` (solo aserción) | EXP-01 · señuelo | 4 `changed_first`, 2 `confirmed` | 2/6 | 0/6 | 0/6 |
| EXP-09 | `decisive` (almacenamiento) | EXP-02 · señuelo | 6 `vetoed` | 6/6 | 6/6 | 6/6 |

En las engañosas, D veta el señuelo en EXP-07 y EXP-09 (12 de 12 ejecuciones con memoria), y la memoria no
cambia el resultado frente a A. El único daño está en EXP-08, donde D es ambiguo y el plan vuelve a ser el
DEFAULT: la lección señuelo desplaza el primer intento en 4 de 6 semillas y las −2 al primer intento
provienen de las semillas 1 y 6.

**Intentos** (18 ejecuciones): original A 24, B 18, C 18 (−6 en B y en C); engañosa A 27, B 30, C 30 (+3).

**Coste** por condición (réplica 1, 18 ejecuciones por tipo). Los tests incluyen la reproducción `test-0`:

| Tipo | Tests A / B / C | Intentos A / B / C | Tiempo total A / B / C (ms) |
|---|---|---|---|
| Original | 42 / 36 / 36 | 24 / 18 / 18 | 10 568 / 8 783 / 8 495 |
| Engañosa | 45 / 48 / 48 | 27 / 30 / 30 | 11 813 / 10 743 / 11 615 |
| Entrenamiento | 42 / 45 / 42 | 24 / 27 / 24 | 10 384 / 9 954 / 9 890 |

El tiempo es solo descriptivo: depende de la máquina y no es prueba de mejora.

**Lecciones** (réplica 1): en las originales, B expone 54 y C 18, y las dos citan 18; en las engañosas, lo
mismo. Citadas en las originales, en B y en C por igual: 12 confirmadas y 6 aplicadas (`changed_first`), ninguna
vetada. En las engañosas: 12 vetadas, 2 confirmadas y 4 aplicadas.

**Entrenamiento** (EXP-01..03, descriptivo): FA A 12/18, B 9/18, C 12/18. B cita en EXP-02 la lección de
EXP-01, de otra familia dentro de los candidatos de D, y pierde el primer intento en 3 semillas. C no propone
nada en EXP-02. En EXP-03, D es decisivo y veta la lección que citan B y C.

## Predicciones frente a observaciones

| Predicción (C0) | Observado | ¿Se cumple? |
|---|---|---|
| **PD1** · D `decisive` en fallos de almacenamiento, `partial` en errores sobre `NoneType` y `ambiguous` donde solo hay aserciones (probablemente EXP-08) | `decisive`: EXP-03, 06, 09; `partial`: EXP-01, 02, 04, 05, 07; `ambiguous`: EXP-08 (`no_discrimination`); igual en A, B y C y en las 6 semillas | Sí |
| **PD2** · Original: «aporta» para B y C | +6/18 en B y en C | Sí |
| **PD3** · Engañosa: D veta el señuelo cuando la excepción excluye su operador; la memoria perjudica donde D es ambiguo; «perjudica» o «sin diferencia», no «aporta» | Veto en EXP-07 y EXP-09; daño solo en EXP-08; −2/18 = «sin diferencia» | Sí |
| **PD4** · B y C con planes iguales en transferencia | 18/18 planes idénticos en original y en engañosa (difieren en entrenamiento) | Sí |
| **PD5** · Mismo éxito final que DEFAULT | 324/324 `PASS`, como en referencia v2 | Sí |
| **PD6** · Mismas lecciones expuestas y citadas que en referencia v2 | 162/162 celdas iguales en expuestas y en citadas | Sí |

Que se cumplan las seis es coherente con el carácter exploratorio del diseño: el autor conocía las tareas y
los resultados de referencia v2 al escribirlas.

## Contexto descriptivo (fuera del análisis pre-registrado)

Misma receta, semillas y hashes que referencia v2, con el agente DEFAULT en lugar del de diagnóstico
(réplica 1 de cada campaña; FA al primer intento):

| Tipo | A (v2 → D) | B (v2 → D) | C (v2 → D) |
|---|---|---|---|
| Original | 6/18 → 12/18 | 18/18 → 18/18 | 18/18 → 18/18 |
| Engañosa | 6/18 → 11/18 | 0/18 → 9/18 | 0/18 → 9/18 |

D sube el FA de A en las originales y de las tres condiciones en las engañosas. Reduce la ventaja de la memoria en las originales (de +12 a +6) y su
daño en las engañosas (de −6 a −2). No es una comparación pre-registrada: se muestra para situar la pregunta,
no para el veredicto.

## Límites y pregunta abierta

- **Holgura reducida.** Con D, el primer intento queda forzado en 6 de 18 pares por tipo, y en las engañosas
  D veta la memoria en 12 de 18. La memoria solo puede actuar donde D deja dos o tres candidatos: la lectura
  depende de cuánto discrimina D y no se extiende a un diagnóstico más fuerte ni más débil.
- **B y C no se distinguen en transferencia.** Comparten la clave léxica `title + context`: citan la misma
  lección en las 18 ejecuciones de cada tipo. El empate refleja esos insumos; no evalúa el grafo más allá de
  esa clave ni dice que el grafo sea irrelevante.
- **Diseño exhaustivo y determinista.** Son conteos exactos de 9 tareas de un proyecto, 6 permutaciones del
  prior y 2 réplicas idénticas. No admiten inferencia estadística, y las réplicas no son muestras
  independientes.
- **D se eligió conociendo las tareas** y depende del formato de `unittest`.
- **Pregunta abierta.** Dónde D es ambiguo (EXP-08), la memoria léxica vuelve a elegir el señuelo, como en
  referencia v2. Queda sin probar una recuperación sembrada con la propia reproducción, o un D que
  discrimine las aserciones, con estas mismas tareas.

La bitácora de desarrollo (`learning/`) registra cómo se construyó este experimento; la memoria de los
agentes del experimento (lecciones, grafo) vive solo en los recibos de la campaña. Son memorias distintas.
