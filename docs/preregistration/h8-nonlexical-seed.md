# Pre-registro · H8: recuperación sembrada con una señal no léxica frente al señuelo (#98)

**Registro**: 2026-10-03. El commit que introduce este archivo en `main` (C0) es la marca temporal
verificable. Es anterior a la política de siembra, al análisis y a cualquier corrida identificada. Cambiar
este documento después de ver datos de la campaña lo invalida en ese punto; las enmiendas se rigen por la
sección 10 y toda desviación se reporta como tal en la lectura.

**Carácter: exploratorio, con conocimiento previo declarado.** El autor no es ciego al banco:

- **Leyó**: los informes de H4, #58, H6 y H7 y sus pre-registros; el
  [protocolo](../../specs/software_learning_protocol.md), incluida la tabla pública de las tareas engañosas
  (familia real, señuelo y descripción del defecto de EXP-07..09); los nueve `benchmark/public/EXP-0x.json`
  y un solo test de aceptación, el de EXP-01; el solver acotado, el harness de experimento, el evaluador,
  `scripts/analyze_h4.py` y `tests/test_experiment_misleading.py`; los agregados publicados de
  `results/reference-v2/`.
- **Sabe por esos informes**: el estado del diagnóstico D por tarea
  ([resultados de #58](../results/diagnostic-baseline.md), tabla «Por tarea»), y con él la clase de excepción
  de cada reproducción. En EXP-08 solo hay fallos de aserción.
- **No leyó**: `benchmark/private/`, la salida (`stdout`, `stderr`) de ningún recibo, el código de la
  aplicación bajo reparación (solo los nombres de sus archivos) ni los tests de aceptación de EXP-02..09.
- **No ejecutó**: el solver acotado ni la reproducción de ninguna tarea, ni calculó qué lección recuperaría
  la política de la sección 2. La batería de tests del repositorio se corrió para las comprobaciones del PR;
  de ella solo se miró el resumen de pasados y fallados.
- **Prueba de viabilidad** (sin datos de la hipótesis): un proyecto sintético en un directorio temporal, con
  la misma orden que `experiments.runner.execute_tests`, para comprobar el formato de los marcos de una
  traza de `unittest`, las excepciones encadenadas y un fallo de aserción sin marcos de aplicación.

- **Después de la revisión independiente (2026-10-03), y antes de C0**: se leyó el código público de la
  aplicación (`experiments/software_project/app/`: `api.py`, `middleware.py`, `worker.py` y
  `services/reporting.py`) y se cruzó con la tabla pública del protocolo y con las etiquetas `Component` de
  las lecciones de `evidence/reference-v2/`. Con eso se corrigieron la predicción (sección 6), la regla de
  decisión (sección 5) y las amenazas 4 y 5. Siguen sin leerse `benchmark/private/`, el `stderr` de ningún
  recibo y los tests de aceptación de EXP-02..09, y no se ejecutó nada.

No es una confirmación independiente. Términos según el [glosario](../entorno/glosario.md).

## 1. Pregunta, hipótesis y relación con lo anterior

> En las tareas con señuelo, ¿la condición asociativa deja de citar la lección del señuelo y mejora el primer
> intento si su recuperación se siembra con una señal del fallo que no es el texto del issue?

**H8**: si la recuperación de la condición asociativa se siembra con una señal no léxica del problema, la
lección recuperada en las tareas engañosas (EXP-07..09) deja de ser la del señuelo y el primer intento mejora
frente al historial textual.

| Antecedente | Qué dejó | Qué hace H8 con ello |
|---|---|---|
| H4 (#46), [informe](../results/h4-associative-vs-history.md) | Con siembra léxica, el historial y la asociativa citan el señuelo y aciertan al primer intento 0/18 en las engañosas, frente a 6/18 sin memoria (tabla «Datos»; `python -m scripts.analyze_h4 --evidence evidence/reference-v2`). «Trabajo futuro»: sembrar con señales no léxicas y repetir con las mismas tareas | Es esa prueba. Mismas tareas, semillas y solver acotado |
| #58, [informe](../results/diagnostic-baseline.md) | Un diagnóstico público D en la decisión veta el señuelo en EXP-07 y EXP-09 y es ambiguo en EXP-08. «Pregunta abierta»: una recuperación sembrada con la propia reproducción | Usa la reproducción, pero en la recuperación (tabla siguiente) |
| H6 (#63) y H7 (#65), informes [H6](../results/failure-memory.md) y [H7](../results/failure-transfer.md) | La memoria de fallos no se transfiere de forma segura con firma y similitud léxica. H7, «Qué resuelve y qué no»: un alcance que discrimine tendría que usar otra señal, «por ejemplo la propia excepción o el componente afectado», y probarse en tareas nuevas | H8 no usa memoria de fallos. Usa el componente como señal para recuperar lecciones, y lo hace sobre las tareas ya vistas: ese límite queda declarado (sección 10) |

**Diferencia con #58.** Es un criterio de aceptación del issue.

| | #58 (`diagnostic-baseline-v1`) | H8 |
|---|---|---|
| Dónde entra la señal | En la **decisión**: `plan()` combina D, memoria y prior | En la **recuperación**: decide qué lección se entrega; `plan()` es el del agente por defecto |
| Quién la recibe | Las tres condiciones, con el mismo D | Solo la condición nueva, C_S. A, B y C_L no la usan |
| Qué es | Clase de la excepción terminal y marcador `NoneType` | Archivos de la aplicación por los que pasa la traza |
| Tabla escrita a mano | Sí: `FAILURE_MODES` asigna clases de excepción a operadores | No: no hay ninguna regla que nombre operadores, familias ni tareas |
| Clave de recuperación | Sin cambios (`title + context`) | Es lo único que cambia, y solo en C_S |
| Pregunta | Con el mismo D, ¿la memoria aporta? | Con la misma decisión, ¿otra siembra recupera otra lección? |

En H8 la decisión no usa D: un veto de D no puede explicar el resultado.

## 2. La señal: componentes de la traza de la reproducción pública

Se fija **una** señal, de las tres que nombra el informe de H4.

**Entradas.** Tres, todas dentro de la frontera de fuga:

1. el `stderr` de `test-0`, la reproducción pública sobre el workspace con el defecto. El harness de
   experimento ya la ejecuta en todas las condiciones, y un solver acotado opt-in ya la recibe desde #58
   ([suplemento](../../specs/diagnostic_baseline_protocol.md), *Extended solver input*). El solver acotado
   por defecto no la recibe;
2. las claves de `AgentView.files`: las rutas relativas (`app/….py`) del código que el solver ya ve;
3. los nodos `Component` de las lecciones de la condición. Su etiqueta es la ruta del archivo que cambió el
   parche verificado del propio solver en el entrenamiento (`EvidenceMemory.consolidate` en
   [`memory.py`](../../src/experiments/memory.py)). Ya están en la memoria de C desde la campaña de
   referencia.

**Extracción (determinista).**

1. Normalizar el `stderr` con `normalize_source` y separarlo en bloques como D (pasos 1 y 2 de la sección 2
   del [pre-registro de #58](diagnostic-baseline.md)): un bloque empieza por `ERROR: ` o `FAIL: `.
2. En cada bloque se usa solo la **última traza**: las líneas posteriores a la última línea igual a
   `Traceback (most recent call last):`. Un bloque sin esa línea no aporta nada.
3. Un marco es una línea que casa `^\s+File "(.*)", line \d+, in .+$`. De cada marco se usa solo la ruta,
   con `\` cambiada por `/`. El marco pertenece al componente `k` si la ruta termina en `/` seguido de `k`,
   para alguna clave `k` de la entrada 2. Los demás marcos (tests, biblioteca estándar) se descartan.
4. Sean `c_1 … c_n` los componentes de los marcos de aplicación de esa traza, del más externo al más
   interno, y `d_i = n − i` (0 es el marco de aplicación más cercano al punto donde se lanza la excepción).
   El peso del componente `k` en el bloque es `1 / (1 + d_i)` para su aparición más interna, y 0 si no
   aparece.
5. `T(k)` es el máximo de ese peso sobre los bloques.

**Descartado.** Número de línea, nombre de función, línea de código, clase y mensaje de la excepción, nombres
y marcos de tests, `stdout`, el texto del issue, el identificador de la tarea y `tests[1:]`.

**Siembra en C_S.** Para cada nodo `Component`, cuya etiqueta es una lista de rutas separadas por espacios,
la puntuación es el máximo de `T(k)` sobre sus rutas. Se siembra si es mayor que 0. No se siembra ningún otro
tipo de nodo y la consulta léxica `title + context` no se usa. La proyección, la propagación, el corte
(activación ≥ 0.005) y el top-1 son los de `EvidenceMemory.retrieve` hoy. Los subgrafos de las lecciones son
disjuntos (sus identificadores llevan el `run_id`), así que la lección expuesta es la del `Component` con
mayor puntuación.

**Estados de la siembra**, registrados por ejecución:

| Estado | Condición | Lección expuesta |
|---|---|---|
| `seeded` | Un solo nodo `Component` tiene la puntuación máxima y su lección supera el corte | Esa lección |
| `tie` | Dos o más nodos `Component` comparten la puntuación máxima | Ninguna |
| `empty` | Ningún nodo sembrado (también con memoria vacía), o la lección no supera el corte | Ninguna |

Sin lección expuesta, el plan es el prior de la semilla, igual que en A. **No hay respaldo léxico**: si la
señal calla, C_S no vuelve a la siembra de H4. Así la condición mide la señal sola. El orden por
identificador de tarea que hoy desempata en `retrieve` no decide nunca un empate de C_S.

**«No léxica»** quiere decir aquí «sin la consulta léxica de `title + context`». La política sí compara
cadenas: rutas de archivo de la traza con rutas de archivo de las lecciones.

**Frontera de fuga: qué se puede comprobar.** El riesgo del issue es R = 3. Lo comprobable es que la siembra
no accede a las anotaciones privadas. Que una ruta de la traza actúe como sustituto observable de la familia
no es fuga, pero sí una amenaza de constructo (sección 10, amenaza 4).

1. **Material.** Las tres entradas salen de ejecutar tests públicos sobre código visible, o son un parche que
   el propio solver escribió y verificó. Ninguna viene de `benchmark/private/`. La función de siembra recibe
   el `stderr`, las claves de archivo y los nodos de la memoria; no recibe la tarea ni su identificador.
2. **Sin tabla.** No hay ninguna correspondencia escrita a mano entre un rasgo y un operador, una familia o
   una tarea. La única operación es comparar una ruta de la traza con la ruta de un parche anterior. No hay
   regla que el autor pueda ajustar para que nombre la causa.
3. **Invariancia.** Permutar cualquier campo de las anotaciones privadas no puede cambiar la siembra. La
   sección 8 lo comprueba con un test, y el evaluador recalcula cada siembra desde el recibo.

**Lo que muestra el banco público, y limita esta señal.** Las lecciones de entrenamiento tienen como
`Component` `app/auth.py` (EXP-01), `app/config.py` (EXP-02) y `app/api.py` (EXP-03). La tabla pública del
protocolo sitúa los defectos de las tareas engañosas en otros archivos: `authorize`, en `app/middleware.py`
(EXP-07); la etiqueta del informe, en `app/services/reporting.py` (EXP-08); y `worker` (EXP-09). Ningún
archivo donde está un defecto de transferencia tiene lección propia. La señal solo puede citar una lección
si la traza pasa por `auth.py`, `config.py` o `api.py`, y `api.py` es el punto de entrada de las peticiones.
Por eso el resultado de esta señal se puede deducir en buena parte sin correr (sección 6), igual que el de
la clase de excepción que se descarta abajo. Se corre de todos modos para que la deducción quede confirmada
o desmentida con recibos, y porque es la señal que nombra el informe de H4.

**Señales que quedan fuera, y por qué.**

- **Componente inspeccionado, en sentido literal** (`actions[].inspected`): lo produce `change()` después de
  elegir la estrategia. No existe antes de la decisión de la tarea actual, así que no puede sembrar su
  recuperación. La señal elegida es su equivalente observable antes de decidir.
- **Clase de la excepción** (los rasgos de D): el informe de #58 ya publica el estado de D por tarea, y el
  [pre-registro de H7](failure-transfer.md) qué tareas comparten firma. El resultado de sembrar con ella se
  puede deducir de esas tablas; no sería una prueba.
- **Embedding del código**: el solver ve la aplicación con el defecto, no la versión sana, y los nueve
  workspaces difieren en una mutación. `LexicalEmbedder` sobre código es una señal léxica.
  `FastEmbedEmbedder` es un extra opcional que descarga un modelo
  ([`embeddings.py`](../../src/associative_agent_loop/memory/embeddings.py)); no está en la receta de las
  campañas y el protocolo no implementa condiciones vectoriales. Una señal así es otra hipótesis, con su
  pre-registro.

## 3. Condiciones y diseño

Cuatro condiciones, con un solo solver acotado opt-in que declara su condición:

| Condición | `memory_mode` | Siembra | Papel |
|---|---|---|---|
| **A** | `NO_MEMORY` | — | Referencia: lo que se obtiene sin lección |
| **B** | `TEXT_HISTORY` | — (el solver ordena por similitud léxica) | Control: el historial textual |
| **C_L** | `ASSOCIATIVE_MEMORY` | Léxica, la de H4: `title + context` sobre `Symptom`, `Component` y `Lesson`, umbral 0.12 | Control: la asociativa de H4 |
| **C_S** | `ASSOCIATIVE_MEMORY` | Componentes de la traza (sección 2) | La condición nueva |

- **Decisión.** En las cuatro, `plan()` es el de `BoundedRepairAgent`: la lección citada va primero y el
  prior ordena el resto. Sin D, sin memoria de fallos. Mismos operadores, parches, presupuesto (3) y
  timeout (20 s).
- **Orden dentro de una ejecución**, igual en las cuatro: `prepare`; `test-0`; `RETRIEVE`; `plan()`, una
  vez; hasta 3 intentos. `tests[1:]` nunca realimentan la recuperación ni el plan. La tabla de fases del
  runner no cambia. `test-0` se adelanta a la recuperación; A, B y C_L no lo usan.
- **Secuencia**, por (réplica, semilla, condición), con memoria nueva: entrenamiento EXP-01..03, `ADD` solo
  con `PASS` verificado; transferencia EXP-04..09 desde la instantánea congelada tras EXP-03. C_S usa su
  siembra también en el entrenamiento. Las lecciones de C_L y de C_S se construyen igual, con los mismos
  nodos y aristas: solo cambia qué nodos se siembran.
- **Tareas y semillas.** Conjunto `misleading-v1` (9 tareas). Semillas 1 4 5 6 7 9: las 6 permutaciones del
  prior, una vez cada una (`tests/test_experiment_reference_campaign.py`). 2 réplicas de la misma semilla,
  que comprueban determinismo y no son muestras independientes.
- **Unidad primaria**: la réplica 1 (la primera por `batch_id`). Tipos **original** (EXP-04..06) y
  **engañosa** (EXP-07..09): 18 ejecuciones por tipo y condición, **nunca agregadas**.
- **Opt-in.** El agente por defecto, sus recetas y las campañas publicadas no cambian. Ningún recibo ni
  agregado de `evidence/` o `results/` se toca.

**Por qué entra A.** En la campaña de referencia B y C_L aciertan 0/18 al primer intento en las engañosas
([informe de H4](../results/h4-associative-vs-history.md)). Con el control en el suelo, C_S no puede quedar
por debajo, y una siembra que nunca recuperase nada obtendría el resultado de A, 6/18, y «mejoraría» frente
al historial sin haber recuperado ninguna lección. A es la referencia que permite que H8 pierda en ese caso.
Exigir que C_S supere también a A es una lectura más estricta que la del issue, que solo nombra al historial.

## 4. Métricas (definidas antes de los datos)

Sobre la réplica 1. «Citada» es la lección de `decision.memory_ids`; «expuesta», las de
`retrieval.memories`. La familia de una lección es la de su tarea de origen y la lee el análisis, del lado
del evaluador.

| Métrica | Numerador | Denominador |
|---|---|---|
| `FA(X, tipo)` | ejecuciones de X con éxito al primer intento | 18 ejecuciones de ese tipo |
| `FA(X, tarea)` | ídem, en una tarea | 6 ejecuciones |
| `Iter(X, tipo)` e `Iter(X, tarea)` | intentos de reparación | 18 y 6 ejecuciones |
| Lección citada en las engañosas | ejecuciones de X por clase: **correcta** (familia real), **señuelo**, **otra**, **ninguna** | 18; y 6 por tarea, con la tarea de origen |
| Estado de la siembra de C_S | ejecuciones por estado (`seeded`, `tie`, `empty`) | 6 por tarea, en las 9 tareas |
| `Δ_B`, `Δ_L`, `Δ_A` | `FA(C_S) − FA(B)`, `FA(C_S) − FA(C_L)`, `FA(C_S) − FA(A)` en las engañosas, en ejecuciones | enteros entre −18 y 18 |
| `Δ_ctrl` | `min(Δ_B, Δ_L)` | ídem |
| `Δ_orig` | `FA(C_S) − FA(C_L)` en las originales, en ejecuciones | ídem |

El entrenamiento (EXP-01..03) se reporta con las mismas métricas, solo como descripción.

## 5. Reglas de decisión

Diseño exhaustivo y determinista: conteos exactos, sin inferencia estadística. Margen: 3 ejecuciones de 18,
el de H4, #58, H6 y H7.

**Validez, antes de cualquier veredicto.** La campaña es **inválida**, y se publica como tal, si:

- no tiene la forma declarada (sección 9), hay un recibo `ERROR` o el evaluador rechaza el directorio;
- la réplica 2 difiere de la 1 en comportamiento: plan, lecciones expuestas y citadas (por su tarea de
  origen), resultado e intentos;
- A, B o C_L no reproducen, en esas mismas variables, la réplica 1 de `evidence/reference-v2/` en alguna de
  sus 162 celdas (3 condiciones × 9 tareas × 6 semillas). Es el control de que solo cambió la siembra.

**Veredicto de H8**, sobre las 18 ejecuciones engañosas. H8 es una conjunción: la lección citada deja de ser
la del señuelo **y** el primer intento mejora. Por eso el veredicto tiene dos componentes.

*Selección.* `S` es el número de ejecuciones engañosas de C_S que citan la lección del señuelo (fila
«Lección citada» de la sección 4). En la referencia, B y C_L citan el señuelo en 18 de 18
(`results/reference-v2/task_breakdown.json`, `decoy_cited`). La selección **se cumple** si `S ≤ 2` y **no
se cumple** si `S ≥ 3`: el mismo margen de 3 de 18.

*Primer intento.*

| | `Δ_A ≤ −3` | `−2 ≤ Δ_A ≤ +2` | `Δ_A ≥ +3` |
|---|---|---|---|
| `Δ_ctrl ≥ +3` | peor que sin memoria | sin diferencia | mejora |
| `Δ_ctrl ≤ +2` | no supera a los controles | no supera a los controles | no supera a los controles |

*Veredicto conjunto.*

| Primer intento | Selección cumplida (`S ≤ 2`) | Selección no cumplida (`S ≥ 3`) |
|---|---|---|
| Mejora | **apoyada** | no apoyada: mejora, pero sigue citando el señuelo |
| Sin diferencia | sin diferencia | sin diferencia, y sigue citando el señuelo |
| Peor que sin memoria | no apoyada: peor que no usar memoria | no apoyada: peor que no usar memoria |
| No supera a los controles | **refutada** | **refutada** |

- **Apoyada** exige las dos partes: C_S supera por el margen al historial, a la asociativa léxica y a no
  usar memoria, y deja de citar el señuelo.
- **Refutada**: C_S no supera por el margen a alguno de los dos controles. No se usa la regla de H4
  («refutada si `FA(C) < FA(B)`»): con B en 0/18 no podría cumplirse nunca.
- **Peor que no usar memoria** se separa de «refutada»: C_S supera a los controles, que están en el suelo,
  pero la lección que cita cuesta el primer intento.

Las celdas cubren todos los valores enteros de `Δ_ctrl`, `Δ_A` y `S`, y no se solapan.

**Tabla derivada.** La validez fija B = C_L = 0/18 y A = 6/18 en las engañosas, de modo que `Δ_ctrl =
FA(C_S)` y `Δ_A = FA(C_S) − 6`. El primer intento queda en función de un solo número:

| `FA(C_S)` en las engañosas | Primer intento |
|---|---|
| 9 a 18 | mejora |
| 4 a 8 | sin diferencia |
| 3 | peor que sin memoria |
| 0 a 2 | no supera a los controles |

**Marca «sin exposición».** Si C_S cita una lección (de cualquier clase) en menos de 3 de las 18
ejecuciones engañosas, el veredicto lleva esa marca: la señal no llegó a actuar. Con los controles en sus
valores publicados, ese caso cae en «sin diferencia».

**Regla secundaria, originales.** «Con coste» si `Δ_orig ≤ −3`; «sin coste» si `Δ_orig ≥ −2`. No cambia el
veredicto, pero la lectura la escribe en la misma frase.

**Qué se afirmaría en cada desenlace**, siempre con la tabla por tarea y con el límite de la sección 10:

| Desenlace | Afirmación permitida |
|---|---|
| Apoyada | En este banco, sembrar con los componentes de la traza mejora el primer intento en las engañosas frente al historial, a la asociativa léxica y a no usar memoria. Se dice en cuántas de las 3 tareas se citó la lección correcta y cuál fue el coste en las originales. No se afirma una ventaja del grafo sobre el historial (sección 10, amenaza 2) |
| No apoyada: mejora, pero sigue citando el señuelo | El primer intento mejora, pero no porque la siembra evite el señuelo. Se dice en cuántas ejecuciones lo citó y de dónde sale la mejora |
| Sin diferencia | Con esta señal, la asociativa rinde como no usar memoria. Se dice en cuántas de las 18 ejecuciones citó el señuelo, la lección correcta, otra o ninguna; solo si `S ≤ 2` se puede decir que dejó de seguir al señuelo |
| Sin diferencia, sin exposición | La señal no discrimina en estas tareas: calla o empata. No dice nada sobre otras señales |
| No apoyada: peor que no usar memoria | La lección que cita C_S cuesta el primer intento frente a no usar memoria. Se dice qué lección citó en cada tarea |
| Refutada | Con esta señal, la asociativa sigue sin superar al historial ni a la siembra léxica en las engañosas. Se dice qué lección citó en cada tarea |
| Inválida | Ningún veredicto. Se publica el motivo |

Se publican todos los resultados, incluidos los nulos, los negativos y los inválidos.

## 6. Predicción

Una, escrita antes de implementar: **el veredicto será «sin diferencia, y sigue citando el señuelo», con
`FA(C_S)` = 4/18 en las engañosas y `S` = 6/18, y «con coste» en las originales.** Se da por cumplida solo
si se cumplen el veredicto y la regla secundaria; los dos números son la estimación puntual, y la lectura
dice cuánto se apartó el resultado de ellos.

Una primera versión de este documento predecía «apoyada» sin haber leído la aplicación. La revisión
independiente mostró, solo con material público, que esa predicción no era alcanzable; se corrigió antes de
C0. Razonamiento, tarea por tarea, con el código público de la aplicación y la tabla pública del protocolo:

- **EXP-07** (familia real: autenticación; señuelo: disponibilidad, la lección de EXP-03). La petición entra
  por `app/api.py` y la excepción se lanza en `app/middleware.py`. `middleware.py` no tiene lección; `api.py`
  sí, y es la del señuelo. Espero `seeded` con la lección de EXP-03 y 0/6 al primer intento: la señal sigue
  al señuelo por el punto de entrada, como advierte la amenaza 5.
- **EXP-08** (familia real: configuración). La reproducción solo tiene fallos de aserción (#58), sin marcos
  de aplicación. Espero `empty` y el resultado de A, 2/6.
- **EXP-09** (familia real: disponibilidad). El defecto está en `worker`, que llama a
  `services/reporting.py` y a `database.py`; ninguno tiene lección y el camino no pasa por `api.py`. Espero
  `empty` y el resultado de A, 2/6.

Lo que más puede desmentir esta predicción: que la traza de EXP-07 incluya `app/auth.py` más cerca de la
excepción que `api.py` (por la importación de `middleware.py`), o que la reproducción de EXP-09 entre por
`api.py`; en el segundo caso citaría la lección de EXP-03, que ahí es la correcta. No se comprobó ninguna de
las dos cosas ejecutando. En las originales espero que la señal calle o se equivoque donde la siembra léxica
acierta siempre (12/12 por tarea con las dos réplicas, `results/reference-v2/family_breakdown.md`).

Una relación estructural distinta, por ejemplo la cercanía en el grafo de importaciones entre los archivos
de la traza y el `Component` de cada lección, podría unir `middleware.py` con `auth.py`. No se pre-registra
aquí: se pensó conociendo la disposición pública de los módulos y la tabla de defectos, y sería otra
hipótesis, con su propio pre-registro.

## 7. Recibos y contrato

- **Esquema**: `software-learning-receipt/v2` con `lf/v1`, como referencia v2. Los hashes de fuente y de
  tests se calculan igual y son comparables por tarea con `evidence/reference-v2/`.
- **Campos aditivos**, solo con el agente de H8: `condition`; `decision_inputs`, con el orden
  `["test-0", "RETRIEVE", "plan"]`; en `retrieval`, la política de siembra, los componentes extraídos con su
  peso, los nodos sembrados con su puntuación y el estado. La decisión lleva los campos del agente por
  defecto y `policy`, y ningún campo de D. El contexto hasheado del agente cubre lo que recibió la
  recuperación.
- Un cambio de nombre de un campo en C1 no es una desviación; un cambio de contenido, sí.
- **Suplemento** nuevo del protocolo en `specs/`, enlazado con una línea, sin reescribir el texto histórico.

## 8. Verificaciones del evaluador (aditivas, en C1)

`python -m experiments evaluate` añade, solo para recibos del agente de H8:

1. **Agente y política** coinciden en los dos sentidos; ningún otro agente lleva campos de H8; no se mezclan
   agentes en un directorio.
2. **Orden**: `decision_inputs` exacto, identificadores de test consecutivos y `test-0` fallido.
3. **Condición** coherente con `memory_mode` y con la política de siembra (tabla de la sección 3).
4. **Repetición de la recuperación.** El evaluador recalcula la siembra solo con `tests[0].stderr`, las
   claves de `initial_source` y `memory_input` (más `title + context` en C_L), repite la recuperación y
   exige que coincida con la registrada: componentes, puntuaciones, estado y lección expuesta.
5. **Repetición de la decisión** con el `plan()` por defecto desde la tarea, las lecciones expuestas, el
   modo y la semilla.
6. **Rechazo de siembra con material privado o causal.** Se rechaza la ejecución si en C_S hay una semilla
   en un nodo que no sea `Component` (por ejemplo `Cause`, `Strategy` o `Lesson`); si una puntuación no sale
   de la traza registrada; o si el bloque de siembra o el contexto del agente contienen una ruta de
   `benchmark/private/`, una clave de las anotaciones privadas o uno de sus valores causales, que el
   evaluador lee de esas anotaciones. La búsqueda es por token exacto y solo en el bloque de siembra del
   recibo (componentes, puntuaciones, estado y lección expuesta) y en las rutas del contexto del agente; no
   en el código fuente ni en el texto de la tarea, donde hay palabras públicas que coinciden con nombres de
   familia.
7. **Misma señal** en las cuatro condiciones de cada (lote, semilla, tarea): los componentes extraídos de
   `test-0` coinciden.

**Cómo se comprobará.** Con tests que pueden fallar, y con una mutación en `scripts/mutation_check.py` por
cada guarda:

- recibos sintéticos alterados, uno por rechazo: la semilla movida a la lección de la familia correcta
  tomada de las anotaciones privadas, una semilla en un nodo `Cause`, una puntuación cambiada, una clave
  privada en el bloque de siembra. Cada uno debe rechazarse, tras un control en verde con el recibo intacto;
- **invariancia**: en una copia del árbol con todos los campos de las anotaciones privadas permutados entre
  tareas (familia, causa, familia del señuelo, la mutación con su ruta y su texto, las listas de tareas
  relevantes y de señuelo, la distancia y la partición), la recuperación de C_S no cambia en ninguna tarea;
  y el módulo de siembra funciona igual en una copia donde `benchmark/private/` no existe;
- auditoría del módulo de siembra: sin imports del controlador, del evaluador ni de `benchmark`; sin
  identificadores de tarea, nombres de operador ni rutas privadas; la función de siembra no recibe la tarea;
- orden de llamadas del runner: `test-0` antes de `RETRIEVE`; alterar `tests[1:]` no cambia la recuperación
  y alterar `test-0` sí;
- trazas **sintéticas**: sin marcos de aplicación, excepciones encadenadas, separadores `\` y `/`, CRLF, dos
  bloques, empate y memoria vacía;
- el agente por defecto sin cambios: `agent.py` y `memory.py` sin diferencias de comportamiento, y las
  evaluaciones publicadas idénticas;
- el análisis puede llegar a «apoyada», «refutada», «sin diferencia», «sin exposición» e «inválida» con
  recibos sintéticos. Ningún test exige que H8 gane.

La repetición prueba coherencia con lo registrado, no que no se consultó nada más: eso lo cubren la
auditoría del módulo y la invariancia.

## 9. Identidad de la campaña y orden de commits

| Concepto | Valor |
|---|---|
| Campaña | `nonlexical-seed-v1` |
| Receta | `python -m experiments run --campaign nonlexical-seed-v1` (fija semillas, réplicas, conjunto, agente y condiciones) |
| Agente y política | `bounded-ast-repair-v1+trace-seed-v1` · `trace-component-seed/v1` |
| Directorios | `evidence/nonlexical-seed-v1/` (recibos) y `results/nonlexical-seed-v1/` (agregados). Nuevos; no se sobrescribe nada |
| Recibos esperados | 432 `task_run` (2 × 6 × 4 × 9). Un `memory_update` por ejecución de entrenamiento con `ADD` en B, C_L y C_S: 108 si todas terminan en `PASS`, como en referencia v2 |
| Análisis | `python -m scripts.analyze_h8 --evidence evidence/nonlexical-seed-v1`, con salida en `results/nonlexical-seed-v1/h8_analysis.json`, sin editar |
| Lectura | `docs/results/h8-nonlexical-seed.md` |

**Qué se hashea.** Cada recibo lleva su sello `receipt_sha256` (SHA-256 del contenido canónico; detecta
alteraciones, no es una firma). Además: `initial_source_sha256`, `acceptance_sha256`,
`agent_context_sha256`, las huellas de la memoria, el manifiesto de fuentes y `git_commit`. La salida del
análisis lista el sello de cada recibo que la produjo (`generated_from`).

**Orden.**

- **C0**: este documento, en `main`.
- **C1**: la política de siembra opt-in, la receta, las verificaciones de la sección 8,
  `scripts/analyze_h8.py`, sus tests y el suplemento del protocolo. **Sin campaña.** Revisión independiente.
- **C2**: la campaña, ejecutada una vez desde un commit de `main` que contiene C1. Los recibos se
  comprometen **antes** de agregar.
- **C3**: agregados, salida del análisis, lectura y verificación independiente.

El **commit del análisis** es el que citan los recibos en `provenance.git_commit`. Debe quedar alcanzable en
`main`. Las correcciones de la revisión son anteriores a él y la lectura las lista.

**Comprobación**, en el commit de la lectura:

```bash
git log --diff-filter=A --format=%H -- docs/preregistration/h8-nonlexical-seed.md   # C0
git merge-base --is-ancestor <C0> <commit del análisis> && echo "C0 antes del análisis"
git merge-base --is-ancestor <commit del análisis> <C2> && echo "análisis antes de la campaña"
git diff <commit del análisis> HEAD -- scripts/analyze_h8.py docs/preregistration/h8-nonlexical-seed.md
git diff <commit del análisis> HEAD -- src/experiments
```

Los dos `git diff` deben salir vacíos, y los 432 `task_run` deben citar el mismo `git_commit`.

## 10. Límites, amenazas a la validez y grados de libertad

**Límites que la lectura debe conservar.** Un proyecto, tres operadores y nueve tareas. Un solver acotado
sin modelo de lenguaje, que reordena operadores ya escritos. Seis permutaciones deterministas y dos réplicas
idénticas: conteos exactos, sin inferencia estadística. Una señal y una política de siembra.

**Amenazas a la validez.**

1. **Autor no ciego.** Conoce las tareas y los resultados anteriores (cabecera). La señal se fijó sin ver
   trazas, pero no a ciegas del diseño del banco.
2. **Señal y estructura confundidas.** C_S difiere de B en dos cosas: el grafo y la señal. La comparación
   que aísla la señal es C_S frente a C_L. No hay un historial ordenado con la misma señal. Un veredicto
   «apoyada» dice que la señal sirve en la recuperación, no que el grafo supere al historial.
3. **Propagación trivial: el grafo no interviene.** Los subgrafos de las lecciones son disjuntos: la
   activación va del `Component` a su propia lección y es monótona en la puntuación. C_S equivale a elegir
   la lección cuyo componente queda más cerca de la excepción en la traza; un historial ordenado por la
   misma señal recuperaría la misma lección. H8 compara **señales de siembra**, no el grafo frente al
   historial, y no prueba asociación de varios saltos entre lecciones.
4. **Componente y familia.** El archivo reparado en el entrenamiento no es el archivo donde está el defecto
   de transferencia de su misma familia (sección 2): la señal no une una tarea engañosa con su lección
   correcta salvo que la traza pase por ese archivo. Y una ruta que coincida con un componente puede actuar
   como sustituto observable de la familia: es una amenaza de constructo, no una fuga.
5. **Sesgo del punto de entrada.** `app/api.py` es el punto de entrada de las peticiones y es el componente
   de la lección de EXP-03. Recibe puntuación positiva en toda traza que entre por ahí y gana cuando ningún
   otro componente con lección aparece. La predicción (sección 6) espera que eso ocurra en EXP-07.
6. **Tareas ya vistas.** H7 pedía probar una señal así en tareas nuevas. El issue las deja fuera.
7. **Controles en el suelo.** B y C_L no pueden empeorar. Por eso el veredicto exige también superar a A.
8. **Formato de la traza.** La extracción depende de `unittest` y de la versión de Python. La campaña se
   ejecuta en una máquina; la portabilidad entre sistemas no se prueba con ella.
9. **Una política entre muchas.** El máximo entre bloques, la última traza del bloque y la abstención en el
   empate se fijaron por principio, sin datos. El peso `1 / (1 + d)` no es un grado de libertad real: como la
   propagación es monótona, cualquier función decreciente de la distancia da el mismo orden, y el corte de
   0.005 no llega a actuar. El criterio que decide es el empate.
10. **Sin veto.** La lección citada va siempre primero: una lección equivocada cuesta el primer intento.

**Grados de libertad cerrados.** Después de C0 no se cambian: la señal y su fórmula; los nodos que se
siembran; la ausencia de respaldo léxico; el tratamiento del empate; los parámetros de propagación, el corte
y el top-1; las cuatro condiciones; las tareas, las semillas, las réplicas y la réplica primaria; el
presupuesto; las métricas, el margen y las reglas de la sección 5; qué cuenta como «citada»; las condiciones
de invalidez. No se añade una segunda señal ni un segundo análisis después de ver datos: eso es otra
hipótesis, con otro pre-registro. La campaña se ejecuta una vez. Si se interrumpe o resulta inválida, sus
recibos se conservan sin agregar, la lectura lo declara, y una campaña corregida va a un directorio nuevo
con otro nombre.

**Enmiendas.** Una enmienda es un commit propio en `main`, anterior al commit del análisis, que añade al
final de este archivo una sección «Enmienda N» con fecha y motivo, sin reescribir el texto original. Después
del commit del análisis este archivo no se toca: lo que cambie se escribe en la lectura como «desviación
declarada», con su efecto sobre el veredicto.

## 11. Fuera de alcance

Como fija el issue: agentes LLM, tareas nuevas, un segundo proyecto y barrer *k* distractores; la promoción
de lecciones a skill de memoria (`promoted_to_skill`) y UPDATE, MERGE o DEPRECATE; la inferencia
estadística; y reescribir recibos, agregados o conclusiones de H4, #58, H6 o H7.

Además, por este diseño: el diagnóstico D y la memoria de fallos; un respaldo léxico o una siembra mixta;
otras señales (sección 2); un historial textual ordenado con la señal; y un placebo de la siembra.
