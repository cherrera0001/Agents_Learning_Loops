# Resultados · H8: recuperación sembrada con una señal no léxica (#98)

**Veredicto pre-registrado: «sin diferencia, y sigue citando el señuelo».** Sembrar la recuperación con los
archivos de la traza del fallo, en vez de con las palabras del issue, no evita el señuelo. En las tareas
engañosas, la condición nueva (C_S) acierta al primer intento en 4 de 18 ejecuciones: más que los dos controles
con memoria (0 de 18) y menos que no usar memoria (6 de 18). Cita la lección del señuelo en 6 de 18
ejecuciones, por encima del máximo de 2 que la regla admitía.

**La predicción se cumplió con sus dos números** (4 de 18 al primer intento y 6 citas del señuelo), incluida
la lectura secundaria «con coste»: en las tareas originales C_S acierta 4 de 18, frente a 18 de 18 de la
siembra léxica.
También coincide el desglose por tarea que el pre-registro anticipó: EXP-07 sembrada con la lección de EXP-03 y
0 de 6 al primer intento; EXP-08 y EXP-09 sin semilla y 2 de 6 cada una.

## Qué se comparó

Cuatro condiciones sobre el mismo solver acotado, sin modelo de lenguaje, con 6 órdenes de operadores y 2
réplicas idénticas. Cada conteo es sobre 18 ejecuciones (3 tareas × 6 órdenes) de la réplica 1.

| Condición | Memoria | Con qué se siembra la recuperación |
|---|---|---|
| A | Ninguna | — |
| B | Historial de lecciones | Las palabras del issue |
| C_L | Grafo asociativo | Las palabras del issue (la siembra de H4) |
| C_S | Grafo asociativo | Los archivos de la traza de la reproducción pública |

## Resultados

**Acierto al primer intento.**

| Tareas | A | B | C_L | C_S |
|---|---|---|---|---|
| Engañosas | 6/18 | 0/18 | 0/18 | 4/18 |
| Originales | 6/18 | 18/18 | 18/18 | 4/18 |

**Lección citada en las tareas engañosas.**

| Clase | A | B | C_L | C_S |
|---|---|---|---|---|
| Correcta | 0 | 0 | 0 | 0 |
| Señuelo | 0 | 18 | 18 | 6 |
| Otra | 0 | 0 | 0 | 0 |
| Ninguna | 18 | 0 | 0 | 12 |

**Estado de la siembra de C_S, por tarea** (6 ejecuciones cada una): `seeded` en EXP-04 y EXP-07; `empty` en
las otras siete. Ningún `tie`.

## Cómo se llega al veredicto

| Cantidad | Valor | Regla (sección 5 del pre-registro) |
|---|---|---|
| Δ frente a los controles con memoria | +4 (C_S menos B y menos C_L; se toma el menor) | Mejora si es ≥ 3 |
| Δ frente a no usar memoria | −2 (C_S menos A) | Mejora si es ≥ 3; perjuicio si es ≤ −3 |
| Lectura del primer intento | Sin diferencia | Supera a los controles con memoria, pero no a no usar memoria |
| Citas del señuelo, S | 6 | La selección se cumple si S ≤ 2: **no se cumple** |
| Ejecuciones que citan alguna lección | 6 | La marca «sin exposición» pide menos de 3: no aplica |
| Δ en las originales | −14 (C_S menos C_L) | «Con coste» si es ≤ −3 |

## Qué dice y qué no

- **La señal calla casi siempre.** En 7 de las 9 tareas la traza no nombra ningún componente que esté en la
  memoria, y C_S se comporta como no usar memoria. Por eso en las engañosas sube de 0 a 4: no porque elija
  mejor, sino porque en dos de las tres tareas no elige nada.
- **En la única tarea engañosa donde la señal habla, EXP-07, elige el señuelo.** En EXP-07 la siembra queda `seeded` en las 6
  ejecuciones, cita la lección del señuelo en las 6 y no acierta al primer intento en ninguna.
- **En las originales pierde lo que la siembra léxica daba.** De 18 de 18 a 4 de 18.
- **No dice que una señal no léxica no pueda servir.** Se probó una señal y una política de siembra, en un
  proyecto, con tres operadores y nueve tareas. Los subgrafos de las lecciones son disjuntos: C_S equivale a
  elegir la lección cuyo componente queda más cerca de la excepción, y no prueba asociación de varios saltos
  (sección 10 del pre-registro).
- **No dice nada sobre modelos de lenguaje.** El solver reordena operadores ya escritos.

Son conteos exactos de una enumeración, sin inferencia estadística.

## Validez de la campaña

| Comprobación | Resultado |
|---|---|
| Forma declarada | 432 `task_run` y 108 `memory_update`; 2 réplicas × 6 órdenes × 4 condiciones × 9 tareas |
| Recibos `ERROR` | Ninguno: los 432 terminan en `PASS` |
| Réplica 2 igual a la 1 en comportamiento | Sí |
| A, B y C_L reproducen la campaña de referencia | Sí, en las 162 celdas |
| `python -m experiments evaluate` sobre el directorio | Código 0: no lo rechaza. El análisis no llama al evaluador, así que se corrió antes |

## Conocimiento previo a la campaña

La predicción y las reglas estaban en `main` desde C0. Antes de ejecutar la campaña ya se había visto esto:

- El implementador vio, por la salida de un test que falló, el resultado y las iteraciones de C_S en EXP-04 a
  EXP-09 con un orden de operadores, y el bloque de siembra de EXP-01 a EXP-04.
- El revisor vio, por un defecto que inyectó, en qué tareas C_S expone una lección de otra familia.
- La suite de tests ejecuta C_S con un orden sobre las nueve tareas en cada corrida, porque el test de
  invariancia del pre-registro lo exige. La traza no depende del orden, así que el estado de la siembra por
  tarea era conocido antes de la campaña.

El revisor no encontró en el código ni en los tests nada ajustado a esos resultados.

## Trazabilidad

| Paso | Commit | Contenido |
|---|---|---|
| Pre-registro (C0) | `6034512` | [`docs/preregistration/h8-nonlexical-seed.md`](../preregistration/h8-nonlexical-seed.md) |
| Implementación y análisis (C1) | `6cb0573` | Política de siembra, receta, verificaciones del evaluador y [`scripts/analyze_h8.py`](../../scripts/analyze_h8.py). Es el commit que citan los recibos |
| Datos (C2) | `322d060` | Una sola campaña, 540 recibos, comprometidos antes de agregar |

**Correcciones de la revisión independiente, anteriores al commit del análisis:** un caso de prueba para que el
coste en las originales se mida contra C_L y no contra B, y un código de salida propio (2) cuando el directorio
de recibos falta o está vacío. La revisión señaló además un desempate que el pre-registro no escribe (ordenar
las claves de archivo de la más larga a la más corta); no puede actuar aquí, porque ninguna de las diez claves
es sufijo de otra.

```bash
python -m experiments run --campaign nonlexical-seed-v1
python -m experiments evaluate --evidence-dir evidence/nonlexical-seed-v1 --output results/nonlexical-seed-v1
python -m scripts.analyze_h8 --evidence evidence/nonlexical-seed-v1 > results/nonlexical-seed-v1/h8_analysis.json
```

Comprobación del orden (sección 9 del pre-registro): `6034512` es ancestro de `6cb0573`, `6cb0573` es ancestro
de `322d060`, los 432 `task_run` citan `git_commit` = `6cb0573`, y `git diff 6cb0573 HEAD` sale vacío para
`scripts/analyze_h8.py`, el pre-registro y `src/experiments`.

La salida del análisis está en
[`results/nonlexical-seed-v1/h8_analysis.json`](../../results/nonlexical-seed-v1/h8_analysis.json), sin editar.
