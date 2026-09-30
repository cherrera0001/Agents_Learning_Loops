# Pre-registro · H7: transferencia y contaminación de la memoria de fallos (#65)

**Registro**: el commit que introduce este archivo (C0), hecho **antes** de implementar y antes de cualquier
corrida identificada. Cambiarlo después de ver datos de la campaña lo invalida en ese punto; toda desviación se
reporta como tal.

**Carácter: exploratorio, con conocimiento previo declarado.** El autor diseñó H6 (#63) y leyó su informe
([resultados](../results/failure-memory.md)). En particular, conoce esta tabla de H6: entre tareas distintas,
los pares con firma idéntica tuvieron similitud máxima 0.277 (EXP-02 → EXP-05), 0.108 (EXP-01 → EXP-05),
0.093 (EXP-04 ↔ EXP-07) y 0.071 (EXP-01 → EXP-02). Los umbrales de la sección 3 se eligieron **conociendo esa
tabla**. Los recibos de H6 contienen información suficiente para anticipar parte de H7 (qué estrategias
fallaron en cada tarea); el autor **no** la derivó y no leyó `benchmark/private/`.

Términos según el [glosario](../entorno/glosario.md).

## 1. Pregunta

> Un intento fallido registrado en una tarea, ¿**mejora** (transferencia) o **empeora** (contaminación) la
> primera decisión en **otra** tarea? ¿Y ese efecto depende del **contenido** del fallo o aparece igual con un
> registro falso?

## 2. Qué cambia respecto de H6

| Se mantiene (H6, #63) | Cambia |
|---|---|
| Agente de diagnóstico de #58 y memoria de fallos de #63: registro por intento fallido, firma de D, clave `title + " " + context`, política `(op∉S, op∈F, op≠p, prior)` | **Una sola pasada** de transferencia (EXP-04..09); ninguna tarea se repite |
| Entrenamiento EXP-01..03, lecciones congeladas tras EXP-03, memoria de fallos en línea | **Alcance** parametrizado por τ (sección 3) |
| Semillas 1 4 5 6 7 9, 2 réplicas, réplica 1 primaria | **Placebo** (sección 4) |
| Recibos v2, hashes `lf/v1`, sellos y recibos `memory_update` separados | Campaña `failure-transfer-v1` en un directorio nuevo |

Como ninguna tarea se repite y la memoria es nueva por (semilla, condición), **todo registro que aplique
proviene de otra tarea por construcción**. El análisis lo verifica con el origen leído de los recibos.

## 3. Alcance

Un registro aplica si su firma es **idéntica** a la de `test-0` actual y `cosine_similarity(query, registro.query)
≥ τ`, con τ ∈ {**0.5**, **0.25**, **0.1**, **0**}. Con τ = 0 basta la firma. τ = 0.5 es el alcance de H6 y sirve
de ancla: el autor espera exposición nula ahí.

## 4. Placebo

El registro placebo es idéntico al real y usa el mismo alcance, salvo la estrategia, que se rota de forma
determinista: `STRATEGIES[i] → STRATEGIES[(i + 1) mod 3]`, sobre el orden de `STRATEGIES` en `agent.py`. La
rotación se aplica al construir `F`, sin cambiar el recibo del registro. Si un efecto aparece igual con el
placebo, no depende de qué falló.

## 5. Condiciones

Dos bases × nueve variantes = 18 condiciones por semilla:

| Base | Sin memoria de fallos | Real, τ = 0.5 / 0.25 / 0.1 / 0 | Placebo, τ = 0.5 / 0.25 / 0.1 / 0 |
|---|---|---|---|
| **A** (sin lecciones) | A | A_R50, A_R25, A_R10, A_R00 | A_P50, A_P25, A_P10, A_P00 |
| **C** (asociativa congelada) | C | C_R50, C_R25, C_R10, C_R00 | C_P50, C_P25, C_P10, C_P00 |

## 6. Métricas

Unidad: el par (semilla, tarea de transferencia) entre una variante V y su base sin memoria de fallos X ∈ {A, C},
réplica 1. Tipos **original** (EXP-04..06) y **engañosa** (EXP-07..09), 18 pares por tipo, **nunca agregados**.

| Métrica | Definición | Origen |
|---|---|---|
| `Exposure` | pares donde al menos un registro aplica | nueva |
| `Changed` | pares con `failure_effect = changed_first` en V | nueva |
| `helped` | V acierta al primer intento y X no | nueva; pareada, sustituye a la de H6 (D1) |
| `hurt` | X acierta al primer intento y V no | nueva; pareada |
| `NetTransfer` | `helped − hurt` | nueva |
| `FA` | éxito al primer intento | existente (#58) |

`helped` y `hurt` solo pueden ocurrir si `Changed`, porque la política conserva el resto del plan. Se
reportan los tres conteos juntos, con numerador y denominador.

## 7. Reglas de decisión

Margen: 3 pares de 18, como H4, #58 y H6. Por base (A, C), por tipo y por τ:

- **Exposición.** Si `Changed < 3`, la celda es **«sin exposición»**: ninguna regla de contaminación o
  transferencia se lee en ella, y se reporta así (lección de H6: una métrica que no tuvo ocasión de ocurrir no
  prueba nada).
- **H7a · Contaminación.** «contamina» si `hurt ≥ 3` en alguna celda con exposición.
- **H7b · Transferencia sin contaminar.** Para cada τ y base: «transfiere sin contaminar» si en **algún** tipo
  `helped ≥ 3` y en **los dos** tipos `hurt = 0`. «contamina» si en algún tipo `hurt ≥ 3`. «neutral» en otro caso.
  «sin exposición» si los dos tipos lo están. Un tipo sin exposición cumple `hurt = 0` por construcción: se
  marca así en el informe y no cuenta como evidencia de no contaminar.
- **H7c · Contenido frente a placebo.** En cada celda con exposición en la real **o** en el placebo:
  `NetTransfer(real) − NetTransfer(placebo)` ≥ +3 → «el contenido importa»; ≤ −3 → «peor que placebo»; en
  otro caso, «indistinguible del placebo».
- **Conclusión de H7**, solo sobre la base C:
  - **«la memoria de fallos transfiere sin contaminar»** si existe un τ con H7b = «transfiere sin contaminar» y
    H7c = «el contenido importa» en el tipo donde transfiere;
  - **«contamina»** si algún τ da H7a = «contamina» y ningún τ cumple lo anterior;
  - **«sin evidencia de transferencia»** en otro caso.

  La base A se reporta con las mismas reglas, sin entrar en la conclusión.

## 8. Predicciones (antes de implementar)

- **PT1 · Exposición.** Nula con τ = 0.5 (ancla). Crece al bajar τ: pocos pares con τ = 0.25, más con 0.1, la
  mayor con τ = 0. Las tareas con D `decisive` (EXP-06, EXP-09) no pueden cambiar el primer intento por
  construcción, así que no tendrán `Changed`.
- **PT2 · Contaminación.** Espero `hurt > 0` con τ = 0. Dentro de un mismo estado `partial`, un fallo de una
  tarea de otra familia baja justo la estrategia que la tarea destino necesita. No sé si llegará al margen.
- **PT3 · Transferencia.** Sin predicción firme. Si aparece, espero que sea con τ = 0.25, y el autor sabe que ahí
  solo cruza EXP-02 → EXP-05, que comparten familia. Una transferencia observada solo en ese par sería
  **una** relación, no generalización.
- **PT4 · Placebo.** Espero que el placebo contamine distinto del real. No sé en qué dirección.

## 9. Orden de commits

- **C0**: este documento.
- **C1**: alcance parametrizado, placebo, 18 condiciones opt-in, receta `failure-transfer-v1`, verificaciones
  del evaluador (incluye que ningún registro aplicado tenga origen en la misma tarea),
  `scripts/analyze_failure_transfer.py` y tests sintéticos, **sin campaña**.
- Revisión del orquestador con medios propios. Después, la campaña en `evidence/failure-transfer-v1/` y los
  resultados en `results/failure-transfer-v1/`.

Las recetas anteriores y la ruta DEFAULT no cambian. H6 (`failure-memory-v1`) debe seguir reproduciéndose
byte a byte.

## 10. Límites declarados

- Nueve tareas de un proyecto, tres operadores, D fijo y un orden de tareas fijo (EXP-04..09): qué registros
  existen al decidir depende de ese orden. Conteos exactos, sin inferencia estadística; las réplicas no son
  muestras independientes.
- Los umbrales se eligieron conociendo la tabla de similitudes de H6: el resultado con τ = 0.25 no es
  independiente de esa lectura.
