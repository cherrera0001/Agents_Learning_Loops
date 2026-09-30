# Resultados · H7: transferencia y contaminación de la memoria de fallos (#65)

**Veredicto pre-registrado (base C): «contamina».** Con τ = 0.1, un fallo de otra tarea le quita el primer
intento correcto a una tarea original en 3 de 18 pares, y ningún τ cumple «transfiere sin contaminar». Con las
lecciones presentes, la memoria de fallos **nunca ayudó** entre tareas: solo pudo dañar.

Sin lecciones (base A, fuera de la conclusión) sí hay transferencia útil entre tareas de la **misma** familia, y
daño entre familias **distintas**. Pero ningún umbral de similitud separa unas de otras: se intercalan. τ = 0.25
parece limpio solo porque deja pasar una única relación, y se eligió conociendo las similitudes de H6.

## Trazabilidad

| Paso | Commit | Hora (−03:00) | Contenido |
|---|---|---|---|
| Pre-registro (C0) | `b1565bf` | 09:27 | [`docs/preregistration/failure-transfer.md`](../preregistration/failure-transfer.md) |
| Implementación y análisis (C1) | `33b0b21` | 10:13 | Alcance τ, placebo, 18 condiciones, receta `failure-transfer-v1`, verificaciones, [`scripts/analyze_failure_transfer.py`](../../scripts/analyze_failure_transfer.py), tests, sin campaña |
| Revisión del orquestador | `ffbf862` | — | Con medios propios: ruff, mypy, 496 tests, 88/88 mutaciones, lectura del núcleo, H6 reproducido byte a byte; CI 12/12 |
| Datos | `db26bd0` | 10:42 | Una sola campaña, 2 830 recibos, comprometidos **antes** de agregar |

Los 1 944 `task_run` citan `git_commit` = `ffbf862`; `git diff b1565bf -- docs/preregistration` está vacío.

```bash
python -m experiments run --campaign failure-transfer-v1 --evidence-dir <directorio nuevo>
python -m experiments evaluate --evidence-dir evidence/failure-transfer-v1 --output results/failure-transfer-v1
python -m scripts.analyze_failure_transfer --evidence evidence/failure-transfer-v1
```

La salida del tercer comando es [`results/failure-transfer-v1/failure_transfer_analysis.json`](../../results/failure-transfer-v1/failure_transfer_analysis.json),
sin editar (solo sin el CR que agrega la consola de Windows).

## Datos

| Comprobación | Resultado |
|---|---|
| Recibos | 1 944 `task_run` + 324 `memory_update` de lecciones + 562 de fallos = 2 830 |
| Resultado | 1 944 `PASS`, 0 `FAIL`, 0 `ERROR` |
| Réplicas | 2 lotes; `replicates_consistent: true`; réplica 1 (`BATCH-21433fa9…`) primaria |
| Mismo origen | ningún registro aplicado proviene de la misma tarea (verificado por el evaluador y el análisis) |

## Celdas (transferencia, réplica 1, 18 pares por tipo)

Solo las celdas con `Changed > 0`; en todas las demás, `Changed = 0`. τ = 0.5 no tiene exposición en ninguna
variante, como en H6.

| Base | τ | Variante | Tipo | Exposure | Changed | helped | hurt |
|---|---|---|---|---|---|---|---|
| A | 0.25 | real | original | 3 | 3 | **3** | 0 |
| A | 0.1 | real | original | 6 | 6 | 3 | **3** |
| A | 0 | real | original | 6 | 3 | **3** | 0 |
| A | 0 | real | engañosa | 3 | 3 | **3** | 0 |
| C | 0.25 | placebo | original | 3 | 3 | 0 | **3** |
| C | 0.1 | real | original | 6 | 3 | 0 | **3** |
| C | 0.1 | placebo | original | 6 | 3 | 0 | **3** |
| C | 0 | placebo | original | 6 | 3 | 0 | **3** |

## Reglas pre-registradas

**H7a · Contaminación** (real): A «contamina» con τ = 0.1; C «contamina» con τ = 0.1. El placebo de C
contamina con τ = 0.25, 0.1 y 0.

**H7b · Transferencia sin contaminar** (real):

| τ | A | C |
|---|---|---|
| 0.5 | sin exposición | sin exposición |
| 0.25 | **transfiere sin contaminar** | sin exposición (aplica en 3 pares, no cambia ninguno) |
| 0.1 | contamina | contamina |
| 0 | **transfiere sin contaminar** (ver hallazgo 3) | sin exposición (aplica en 6 pares, no cambia ninguno) |

**H7c · Contenido frente a placebo**: «el contenido importa» en A con τ = 0.25 y τ = 0 (real +3, placebo 0), y en
C con τ = 0.25 y τ = 0 (real 0, placebo −3). «Indistinguible del placebo» en A y en C con τ = 0.1.

**Conclusión (base C): «contamina».** Ningún τ da en C «transfiere sin contaminar».

## Qué relación produce cada efecto

Cada efecto es **una** relación entre dos tareas, repetida en las 3 semillas donde el prior la deja actuar:

| Relación | Familias | Registro | Efecto | Dónde |
|---|---|---|---|---|
| EXP-02 → EXP-05 | misma (valor de entorno) | EXP-02 falló con `validate_optional_identity` | baja esa estrategia en EXP-05: **ayuda** | A con τ = 0.25, 0.1 y 0 |
| EXP-04 → EXP-07 | misma (identidad opcional; se infiere de que en EXP-07 acierta `validate_optional_identity` tras bajar la otra candidata de D) | EXP-04 falló con `normalize_environment` | **ayuda** en EXP-07 | A con τ = 0 |
| EXP-01 → EXP-05 | distintas | EXP-01 falló con `normalize_environment`, la correcta de EXP-05 | la baja: **daña** | A y C con τ = 0.1 |
| EXP-01 → EXP-02 | distintas | el mismo registro de EXP-01 | **daña** EXP-02 en el **entrenamiento** | A y C con τ = 0 |
| placebo de EXP-02 → EXP-05 | — | rota la estrategia y baja `normalize_environment` | **daña** | C con τ = 0.25, 0.1 y 0 |

**Ningún umbral separa lo que ayuda de lo que daña.** Ordenadas por similitud léxica (tabla de H6): EXP-02 →
EXP-05 (misma familia, 0.277, ayuda) · EXP-01 → EXP-05 (distinta, 0.108, daña) · EXP-04 → EXP-07 (misma, 0.093,
ayuda) · EXP-01 → EXP-02 (distinta, 0.071, daña). Las útiles y las dañinas se **intercalan**: todo τ que deje
pasar las dos útiles deja pasar también EXP-01 → EXP-05, y todo τ que bloquee las dañinas bloquea también
EXP-04 → EXP-07. τ = 0.25 parece limpio solo porque deja pasar una única relación, y se eligió conociendo la tabla
(pre-registro, carácter). En este banco, la similitud léxica de la clave **no discrimina** la familia del fallo.

## Lo que las reglas no dicen

1. **Con lecciones, la memoria de fallos no aporta.** En C las originales ya aciertan 18/18: un registro de otra
   tarea solo puede empeorar. En las engañosas, C no tuvo exposición en ningún τ.
2. **La dosis-respuesta no es monótona.** τ = 0.1 daña y τ = 0 no. Con τ = 0, el registro contaminante de EXP-01
   ya había aplicado en el entrenamiento a EXP-02; ahí bajó la estrategia correcta, EXP-02 falló a la primera
   y dejó un segundo registro que en EXP-05 anula al primero. Es una cancelación entre dos errores, no un alcance
   seguro.
3. **H7b «transfiere sin contaminar» en A con τ = 0 es engañoso.** Esa misma condición contamina el
   entrenamiento: EXP-02 pierde el primer intento en 3 de 6 semillas, en A y en C. El pre-registro solo lee la
   transferencia, así que ese daño queda fuera de la regla. Se reporta aquí como hallazgo.
4. **El placebo daña donde el real no ayuda.** En C, un registro falso es peor que uno verdadero: lo que baja
   importa. En A, el placebo nunca cambió un primer intento, porque la estrategia rotada ya quedaba detrás.

## Desviaciones declaradas (el pre-registro no se modificó)

Las detectó el implementador en C1, antes de la campaña:

- **D1 · «sin exposición ⇒ hurt = 0 por construcción» es falso si `Changed` es 1 o 2.** Se aplicó de forma literal,
  con la marca `hurt_zero_by_construction` y el `hurt` observado. En esta campaña, toda celda con `Changed > 0`
  tiene `Changed ≥ 3`.
- **D2 · El placebo tiene su propia memoria**: tras la primera divergencia, sus registros pueden ser otros que los
  de la variante real con el mismo τ. «Mismo registro» se leyó como «misma derivación».
- **D3 · H7a y H7b sobre real y placebo**: se calculan los dos; la conclusión usa solo la real. Se agregaron las
  etiquetas «no contamina» y «sin exposición».
- **D4 · Exposición por `Changed < 3`**, como dice el pre-registro, no por `Exposure`.
- **D5 · «en el tipo donde transfiere»**: basta un tipo con H7c «el contenido importa».

## Qué resuelve y qué no

- **Resuelto en este banco:** abrir el alcance de la memoria de fallos entre tareas **contamina**, con y sin
  lecciones, y en C nunca compensa. Junto con H6, el sistema aprende a no repetir un error en la misma tarea,
  pero ese aprendizaje no se transfiere de forma segura con un alcance por firma y similitud léxica.
- **Sin resolver:** si existe un alcance que transfiera sin contaminar. Con firma más similitud léxica no existe
  en este banco: ningún τ separa las relaciones útiles de las dañinas. Un alcance que discrimine tendría que usar
  otra señal, por ejemplo la propia excepción o el componente afectado, y probarse en tareas nuevas que no se hayan
  visto al fijarlo.

## Alcance

Nueve tareas de un proyecto, tres operadores, D fijo y el orden EXP-04..09. Conteos exactos, sin inferencia
estadística; las réplicas no son muestras independientes. Umbrales elegidos conociendo la tabla de H6.
