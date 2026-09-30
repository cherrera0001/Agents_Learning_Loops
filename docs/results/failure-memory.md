# Resultados · H6: memoria de fallos con revisión (#63)

**Lectura exploratoria.** Las tres reglas pre-registradas salen favorables y la conclusión literal es
**«aprendió de su error sin contaminar»**. Pero cada regla mide menos de lo que su nombre sugiere:

- **No repetir (H6a) y mejora en las engañosas (H6c)**: se cumplen porque las tareas **se repiten**. En la
  pasada 2 el sistema no vuelve a elegir primero una estrategia que ya falló **en la misma tarea**. Es el
  objetivo operativo del README, pero es aprendizaje por repetición, no transferencia.
- **No contaminar (H6b)**: se cumple **por construcción**. Ningún registro de fallo de otra tarea aplicó nunca
  (0 de 351 evaluados), así que la contaminación **no llegó a ponerse a prueba**.
- **Transferencia de un fallo a otra tarea**: **cero**.

## Trazabilidad

| Paso | Commit | Hora (−03:00) | Contenido |
|---|---|---|---|
| Pre-registro (C0) | `87c5941` | 00:09 | [`docs/preregistration/failure-memory.md`](../preregistration/failure-memory.md) |
| Implementación y análisis (C1) | `25eb418` | 00:56 | Memoria de fallos, condiciones opt-in, receta `failure-memory-v1`, verificaciones del evaluador, [`scripts/analyze_failure_memory.py`](../../scripts/analyze_failure_memory.py), tests, sin campaña |
| Revisión del orquestador | `02a7b84` | — | Con medios propios: ruff, mypy, 354 tests, 57/57 mutaciones, lectura del núcleo; CI 12/12 |
| Datos | `8d26a95` | 01:08 | Una sola campaña, 860 recibos, comprometidos **antes** de agregar |

`git diff 87c5941 -- docs/preregistration` está vacío en el commit de los datos. Los 720 `task_run` citan
`git_commit` = `02a7b84`.

```bash
python -m experiments run --campaign failure-memory-v1 --evidence-dir <directorio nuevo>
python -m experiments evaluate --evidence-dir evidence/failure-memory-v1 --output results/failure-memory-v1
python -m scripts.analyze_failure_memory --evidence evidence/failure-memory-v1
```

La salida del tercer comando es [`results/failure-memory-v1/failure_memory_analysis.json`](../../results/failure-memory-v1/failure_memory_analysis.json),
sin editar, con el hash de cada uno de los 860 recibos (`generated_from`).

## Datos

| Comprobación | Resultado |
|---|---|
| Recibos | 720 `task_run` + 72 `memory_update` de lecciones + 68 de fallos = 860 |
| Resultado | 720 `PASS`, 0 `FAIL`, 0 `ERROR` |
| Réplicas | 2 lotes; `replicates_consistent: true`; el evaluador encuentra 108/108 grupos con proyecciones iguales |
| Control de determinismo | A y C reproducen en la pasada 2 exactamente su pasada 1 |
| PF4 | la pasada 1 de A_N y C_N es idéntica a la de A y C en 18/18 planes de cada celda |

Unidad primaria: réplica 1 (`BATCH-8c1f66ed…`). Originales (EXP-04..06) y engañosas (EXP-07..09) nunca se
agregan.

## Reglas pre-registradas (pasada 2, 18 ejecuciones por celda)

**H6a · No repetir.** `R` = ejecuciones cuyo primer intento usa una estrategia que ya falló en la pasada 1 de
la misma (semilla, tarea).

| Celda | R(X) | R(X_N) | Holgura | Cumple |
|---|---|---|---|---|
| A_N frente a A · original | 6/18 | 0/18 | sí | sí |
| A_N frente a A · engañosa | 7/18 | 0/18 | sí | sí |
| C_N frente a C · original | 0/18 | 0/18 | **no** (nula por construcción) | sí |
| C_N frente a C · engañosa | 9/18 | 0/18 | sí | sí |

Veredicto: **apoyada**.

**H6b · No contaminar.** `FA(C_N) = FA(C) = 18/18` en las originales de las dos pasadas, y
`CrossTaskEffect.hurt = 0` en las ocho celdas (A_N y C_N × pasada × tipo). Veredicto: **apoyada**.

**H6c · Engañosas.** `FA(C_N) − FA(C)` = 18/18 − 9/18 = **+9**. Veredicto: **aporta**.

## Lo que las reglas no dicen

**1. La pasada 2 es perfecta por construcción.** La pasada 1 prueba estrategias hasta acertar, y cada intento
fallido deja un registro. En la pasada 2, la misma tarea da la misma firma y similitud 1 consigo misma, así
que todas las estrategias que fallaron bajan y queda primera la que acertó. Con tres operadores, eso da 18/18
siempre que la pasada 1 termine en éxito, como en las 720 ejecuciones. PF1 y PF3 lo anticipaban. Lo que se
demuestra es que el mecanismo funciona tal como se diseñó, no que haya descubierto algo.

**2. La contaminación no se puso a prueba.** Distribución del alcance para registros de **otra** tarea (réplica
1, todas las condiciones y pasadas con memoria de fallos):

| Firma | Similitud | Registros |
|---|---|---|
| distinta | < 0.5 | 297 |
| distinta | ≥ 0.5 | 12 |
| igual | < 0.5 | 42 |
| igual | ≥ 0.5 | **0** |

Todo registro aplicado vino de la misma tarea: `failure_effect = changed_first` se da solo en la pasada 2
(A_N: 6 originales y 7 engañosas; C_N: 9 engañosas), y la pasada 1, incluido el entrenamiento, nunca tuvo un
registro aplicable. La mayor similitud entre tareas distintas fue EXP-02 → EXP-09 (0.57), justamente el par
señuelo, y lo bloqueó la firma. Las parejas con firma igual no pasaron de 0.277 (EXP-02 → EXP-05). PF2 lo
anticipaba: **H6b apoyada no prueba ausencia de contaminación con una política de alcance que sí cruce.**

**3. Transferencia: nula.** `CrossTaskEffect` tiene 0 casos de cualquier clase. Tampoco habría podido
observarse un beneficio con la definición pre-registrada (ver desviación D1).

**4. A_N frente a A.** Sin lecciones, la memoria de fallos basta para no repetir: R pasa de 6 a 0 y de 7 a 0.
Las lecciones no hacen falta para ese objetivo, y la memoria de lecciones no evitó ninguna repetición por sí
sola (C engañosa: R = 9/18).

## Desviaciones declaradas (el pre-registro no se modificó)

Las detectó el implementador en C1, antes de la campaña, y se implementaron de forma literal:

- **D1 · `helped` no es observable.** Si el nuevo primer intento acierta, la ejecución termina y el intento
  desplazado no se prueba, así que el caso es siempre `neutral`/`untested`. La métrica, tal como se definió,
  solo puede detectar daño. En esta campaña no cambia nada, porque no hubo ningún efecto entre tareas. Un
  diseño futuro debe clasificar `helped` frente a la ejecución pareada de X en la misma (semilla, tarea, pasada).
- **D2 · Atribución.** Un primer intento cuenta como cambiado por otra tarea si al menos un registro aplicado
  viene de otra tarea. Es la lectura más amplia y la más estricta para H6b.
- **D3 · Control de determinismo.** Si A o C no reproducían la pasada 1 en la 2, el análisis se marcaba
  inválido. El pre-registro decía «debe reproducir» sin fijar la consecuencia. Se reprodujo.
- **D4 · Frontera de τ.** `cosine_similarity` se usó tal cual. No hubo ningún caso cerca de 0.5 con firma igual.

## Qué queda abierto

La pregunta de contaminación sigue sin respuesta empírica en este banco. Probarla exige una política de alcance
que **sí** cruce entre tareas (por ejemplo, solo firma, o τ más bajo), pre-registrada antes de ver cuántos cruces
produce, y un `helped` pareado (D1). Con esta política, la contaminación es imposible, pero también lo es la
transferencia de un fallo.

## Alcance

Nueve tareas de un proyecto, tres operadores, el diagnóstico D de #58 y un diseño exhaustivo y determinista:
conteos exactos, sin inferencia estadística. Las réplicas no son muestras independientes. El autor conocía las
tareas y los resultados de #58 al pre-registrar.
