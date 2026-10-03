# Pre-registro · Línea base A del experimento Kaggle Gemma 4 y su variación entre réplicas (#103)

**Registro**: el commit que introduce este archivo (C0), hecho **antes** de correr ningún modelo y antes
de cualquier recibo. Cambiarlo después de ver datos lo invalida en ese punto; toda desviación se reporta
como tal en la lectura de resultados.

**Qué es y qué no es.** Fija cómo se medirá la condición A (el kit oficial de la competencia) contra sí
misma. No afirma ningún resultado: no hay ninguna corrida con modelo. Varios datos que el diseño necesita
todavía no existen (qué tareas son válidas, la cuota de GPU, la concurrencia real). Este documento no los
inventa: escribe la regla que determina cada uno, quién lo cierra y cómo, y exige que todos estén cerrados
por un commit antes del primer recibo (sección I).

**Carácter: exploratorio.** El autor leyó la documentación del arnés, el código del paquete instalado
(`swegemma` 0.2.7), los archivos de configuración del kit, las páginas públicas de la competencia y los
comentarios de los issues #100, #101, #103 y #104. De `tasks.jsonl` solo calculó conteos
por repositorio y por fecha y ejecutó `scripts/kaggle_split.py`; no leyó enunciados, parches ni pruebas.
Conoce, por [`fase2_sin_parche.json`](../../experiments/gemma_developer_agent/calibracion/fase2_sin_parche.json),
qué tareas señala como anómalas el notebook de un competidor: esa lista no tiene recibo propio y no se usa
aquí para elegir ni excluir nada.

**Términos.** «Arnés» es aquí el paquete `swegemma` de la competencia, no el harness de experimento del
[glosario](../entorno/glosario.md) (término 6). Las «skills» de la campaña #104 son archivos `SKILL.md`
del envío a Kaggle: no son skills de memoria ni skills de entorno (términos 4 y 5). El arnés se cita por
sección («HARNESS § 7.1») y con palabras propias, sin copiar su texto
([`kaggle_specifications.md`](../../experiments/gemma_developer_agent/docs/kaggle_specifications.md)).

Los valores fijados por este documento están también en
[`linea_base_a.json`](../../experiments/gemma_developer_agent/preregistro/linea_base_a.json), bloque
`fijos`, cuyo resumen es `4ce398e49d13004b4207716a64cfb18848d60d5ba1d42edca50f2e9998488374`
(`python -m scripts.kaggle_prereg comprobar` lo imprime; cambia si cambia cualquier valor fijado).

## Punto de partida

| Hecho | Fuente |
|---|---|
| Las 129 tareas públicas son de entrenamiento: fastapi 67, rich 48, requests 13, httpx 1 | Conteo sobre `tasks.jsonl` (SHA-256 `e4b3fd60…8ad6`); HARNESS § 9.1 |
| El conjunto con que Kaggle puntúa tiene unas 120 tareas de repositorios privados | Página *Data* del Code Track, citada en #100 |
| El envío real tiene 12 h para todas las tareas, incluido el montaje del sandbox y sin contar la validación de parches | Página *Evaluation*, citada en #100 |
| El cómputo son notebooks de Kaggle con L4×4, sin internet, que consumen cuota de GPU al doble | Página *Upgraded Accelerators*; decisión del dueño en #101 |
| La cuota semanal de GPU de la cuenta **no está medida** | #101 |
| La partición de `main` hoy no excluye ninguna tarea; la validez de cada tarea **no está medida** | Comentario del orquestador en #103 (2026-10-03) |
| El presupuesto por tarea entra en el prompt del agente | HARNESS § 5.2 |

## 1. Pregunta

> Con el kit oficial sin cambios de prompt ni de herramientas, ¿cuánto varía el resultado de la condición A
> al repetir la misma corrida sobre las mismas tareas? ¿Qué diferencia entre dos condiciones no se
> distingue de esa variación?

La respuesta decide cuántas réplicas y qué margen necesita la campaña A/B/C/D de #104, o si esa campaña
puede afirmar algo.

## A. Paso previo: validez de las tareas (sin GPU)

Una tarea solo sirve para medir si **discrimina**: sus pruebas fallan sin arreglo y pasan con el parche de
referencia, dentro del mismo sandbox que verificará al agente. Hoy eso no está medido.

**Único uso del parche dorado.** Este paso es el único lugar del experimento donde se usa el parche de
referencia de `tasks.jsonl` (criterio 4 de #103). Lo lee el evaluador, en memoria, y se lo pasa a la
verificación del arnés. No entra en el prompt del agente, en el envío, en los recibos ni en el
repositorio.

### A.1 Entorno de pruebas declarado

Antes de medir, el entorno del sandbox se arregla y se declara en un archivo versionado
(`experiments/gemma_developer_agent/preregistro/entorno_sandbox_v1.json`) con:

- el backend (`docker` o `subprocess`, HARNESS § 4.1) y la imagen con su identificador, o el intérprete
  y su versión;
- las versiones de `swegemma`, `adk-submission`, `adk-eval-core` y `google-adk`;
- el SHA-256 de la lista ordenada `nombre<TAB>sha256` del directorio de ruedas;
- cada arreglo aplicado: rueda añadida o sustituida (nombre, versión, origen, SHA-256), variable de
  entorno o parche del sistema, con el fallo que corrige. Hoy se conocen dos sin resolver: la importación
  de fastapi falla por ruedas faltantes o incompatibles, y el arnés falla al escribir un log con Unicode
  en un host Windows con codificación cp1252
  ([`entorno_local.md`](../../experiments/gemma_developer_agent/docs/entorno_local.md) § 4.2).

**El entorno de la validez es el entorno en que se verifican las réplicas.** Si el notebook de Kaggle no
permite Docker y las réplicas usan `subprocess`, la validez se mide con `subprocess` en una sesión de
notebook sin GPU, y una medición local con Docker solo vale como ensayo. Si el entorno cambia después de
medir, la validez se mide otra vez en un archivo nuevo (`_v2`).

### A.2 Qué se mide

Para cada una de las 129 tareas, cuatro verificaciones con el arnés:

1. **Sin parche**, dos veces: `swegemma eval --skip-agent-patch` (HARNESS § 9.1).
2. **Con el parche dorado**, dos veces: la verificación de la fase 2 del arnés (HARNESS § 8.2) recibe el
   parche de referencia en el lugar del parche del agente. La CLI de `swegemma` 0.2.7 no tiene una opción
   para esto, así que hace falta un guion versionado (`scripts/kaggle_validez.py`, commit C1) que llame a
   esa misma función. El guion no escribe ni imprime el parche: de cada verificación deja el
   `instance_id`, el repositorio, `resolved`, el código de salida de las pruebas, la clase del error del
   arnés (si lo hay) según la lista cerrada de `scripts/kaggle_replicas.py`, la duración y el SHA-256 del
   parche. Se mergea con
   tests sobre datos sintéticos antes de medir.

Se miden las **129** y no solo las candidatas a prueba, por tres motivos: las exclusiones del
entrenamiento quedan en el mismo archivo de subconjunto, cuyo hash citan los recibos; la campaña #104
necesita saber qué tareas de entrenamiento discriminan para contar un episodio como éxito; y el paso no
gasta GPU. Cuesta descargar los snapshots (unos 21,5 GB para las 129, según el orquestador en #103) y 516
verificaciones. Se empieza por fastapi y rich, que son los candidatos a prueba.

### A.3 Clases y regla de exclusión

Una verificación es **de infraestructura** si el arnés da uno de los errores que
`scripts/kaggle_replicas.py` clasifica como `infra_error`, o si el código de salida de las pruebas es −1,
124 o 137 (no se pudo ejecutar, timeout, proceso matado). Las clases se evalúan en este orden y la primera
que se cumple es la de la tarea:

| Orden | Clase | Condición |
|---|---|---|
| 1 | `no_medible` | Alguna verificación es de infraestructura también al repetirla una vez más |
| 2 | `inestable` | Las dos repeticiones de una misma verificación dan resultados distintos |
| 3 | `pasa_sin_parche` | Sin parche: resuelta |
| 4 | `dorado_falla` | Con dorado: no resuelta |
| 5 | `discrimina` | Sin parche: no resuelta. Con dorado: resuelta |

**Se excluye toda tarea cuya clase no sea `discrimina`.** No hay excepciones caso por caso. Una tarea que
falla sin parche por un error del entorno también falla con el dorado y queda `dorado_falla`.

**Guarda contra un entorno roto.** Si en un repositorio con 10 tareas o más, más de la mitad no son
`discrimina`, se considera que el entorno de ese repositorio no está arreglado: se diagnostica, se declara
un entorno nuevo y se mide otra vez (`_v2`), conservando el archivo anterior. Si tras la segunda
declaración sigue igual, decide el dueño y lo deja escrito en #103: seguir con esas tareas excluidas o
detenerse.

### A.4 Qué queda versionado y quién lo hace

El resultado es un archivo **nuevo**,
`experiments/gemma_developer_agent/calibracion/validez_tareas_v1.json`; `fase2_sin_parche.json` no se
pisa ni se usa como fuente de exclusiones. Contiene `sha256_tasks`, el SHA-256 de la declaración del
entorno, los comandos exactos, el registro por tarea (identificador, repositorio, códigos de salida,
duraciones, hash del parche, clase), los conteos por repositorio y clase, y la lista `tareas_invalidas`
que lee `scripts/kaggle_split.py`. Solo identificadores, repositorios, códigos, conteos, duraciones y
hashes: ningún enunciado, parche, prueba ni log de pruebas. Las salidas crudas del arnés quedan en
`data/`, que git ignora.

Lo ejecuta un agente de entorno en la máquina del dueño o en un notebook sin GPU. El orquestador lo revisa
con una repetición propia: todas las tareas excluidas y las 10 primeras tareas por orden de
`sha256(instance_id)`. Si la repetición no coincide, el archivo no se mergea.

## B. Subconjunto

**Regla: `leave_one_repo_out`.** La prueba son todas las tareas válidas de un repositorio y el
entrenamiento son las de los demás. El repositorio preferido es `fastapi/fastapi`; el segundo,
`Textualize/rich`. Cuál de los dos se usa lo decide la escalera de la sección E con la validez y la cuota
medidas, no una elección posterior.

Opciones que ofrece `scripts/kaggle_split.py`, con las 129 tareas antes de excluir ninguna:

| Regla | Prueba | Suelo 6/N | Entrenamiento | Fechas de las tareas de prueba |
|---|---|---|---|---|
| `temporal_stratified`, N = 24 | 24 | 0,250 | 105 | las más recientes de cada repositorio |
| `temporal_stratified`, N = 32 | 32 | 0,188 | 97 | ídem |
| `temporal_stratified`, N = 40 | 40 | 0,150 | 89 | ídem |
| `leave_one_repo_out`, fastapi | 67 | 0,090 | 62 | 2025-09-16 a 2026-06-20 |
| `leave_one_repo_out`, rich | 48 | 0,125 | 81 | 2023-07-29 a 2026-04-12; 26 de 48 son de 2023 o 2024 |
| `leave_one_repo_out`, requests | 13 | 0,462 | 116 | 2023-12-16 a 2026-06-09 |
| `leave_one_repo_out`, httpx | 1 | no alcanzable | 128 | 2025-09-19 |

El suelo es la menor diferencia de tasa que la prueba de McNemar exacta puede declarar con α = 0,05: 6
pares discordantes, todos a favor de una condición, sobre N tareas
([`analisis_replicas.md`](../../experiments/gemma_developer_agent/docs/analisis_replicas.md)).

Por qué un repositorio reservado y no la partición temporal:

1. **La evaluación real es sobre repositorios que el agente no vio.** Con la partición temporal, las
   skills de #104 se consolidarían y se probarían en los mismos repositorios; eso mide transferencia
   dentro de un repositorio, que no es lo que pregunta la competencia ni el criterio *Quality* del Paper
   Track (generalización fuera de la competencia). Reservar un repositorio mide transferencia a un
   repositorio sin episodios de entrenamiento.
2. **Resolución.** Con N = 24 el suelo es 0,25: una mejora de 5 tareas de 24 no se podría declarar. Con
   67 es 0,09 y con 48 es 0,125.
3. **Entrenamiento para #104.** Quedan 62 tareas (rich, requests, httpx) u 81 (fastapi, requests, httpx).

Por qué fastapi antes que rich:

- **Contaminación.** Los arreglos de las tareas antiguas pueden estar en los datos de entrenamiento del
  modelo. Todas las tareas de fastapi son de 2025-09-16 en adelante; 26 de las 48 de rich son de 2023 o
  2024. No se conoce la fecha de corte del modelo, así que ninguna de las dos opciones queda libre de
  este riesgo; fastapi lo reduce.
- **Resolución.** 67 tareas frente a 48.

En contra de fastapi: cuesta más GPU (sección E) y su entorno de pruebas es el que hoy falla. Por eso rich
es el segundo y no se descarta.

Lo que esta regla no da: la partición temporal dentro de cada repositorio. Con un repositorio reservado,
parte del entrenamiento es posterior a parte de la prueba; no importa para la pregunta de transferencia
entre repositorios, pero sí impide leer el resultado como «aprender del pasado para el futuro».

**Mínimo.** Un repositorio solo es apto si le quedan al menos 40 tareas válidas (suelo ≤ 0,15). Si
ninguno de los dos es apto, no hay subconjunto: decide el dueño, y cualquier otra regla exige una
enmienda de este documento antes del primer recibo.

**Comando.** Con la validez y la cuota cerradas, desde la raíz del repositorio:

```bash
python -m scripts.kaggle_split \
  --tasks experiments/gemma_developer_agent/data/tasks.jsonl \
  --calibracion experiments/gemma_developer_agent/calibracion/validez_tareas_v1.json \
  --rule leave_one_repo_out --held-out-repo <repositorio de la escalera> \
  --output experiments/gemma_developer_agent/preregistro/subconjunto_linea_base_a.json
```

El archivo se commitea tal cual (identificadores, conteos y hashes) y su SHA-256 se toma **del blob de
git** (`git cat-file blob HEAD:<ruta> | sha256sum`), porque `.gitattributes` normaliza los finales de
línea y el archivo recién escrito en Windows tiene otros bytes. Ese hash es el `subset_sha256` de los
recibos.

## C. Réplicas

**Cuántas.** 3 si caben y 2 si no, según la escalera de la sección E. Nunca menos de 2. La tercera
réplica da tres pares en vez de uno y una estabilidad por tarea de 0 a 3; es lo primero que se recorta.

**Qué varía entre réplicas: nada que se configure.** El kit fija una temperatura mayor que cero y no fija
semilla (`configs/sampling.yaml`), y este diseño no añade una: añadirla cambiaría el envío. La variación
que se mide es la de repetir el mismo envío: muestreo del modelo, no determinismo del servidor y un
presupuesto de tiempo de reloj.

**Cómo se repite.** Cada réplica es una invocación nueva de `swegemma eval` en una sesión nueva del
notebook, con el servidor del modelo arrancado de nuevo y un `--results-dir` nuevo. El orden de las tareas
es el de `tasks.jsonl` en todas (la CLI no permite otro). Si una réplica no cabe en una sesión, se parte
con `--shard-index` y `--num-shards` (HARNESS § 9.1) con el mismo número de partes en todas las réplicas.

**Qué se mantiene fijo**, y dónde queda escrito:

| Elemento | Dónde |
|---|---|
| Subconjunto | `subset_sha256` de los recibos |
| Envío: kit verificado contra [`manifest.json`](../../experiments/gemma_developer_agent/conditions/a_kit/manifest.json), más el `eval_config.yaml` de la sección D | `submission_sha256` de los recibos |
| `tasks.jsonl` | `tasks_sha256` de los recibos |
| Versión del arnés y entorno del sandbox | `harness_version` y `sandbox_image` de los recibos; declaración de A.1 |
| Modelo y cuantización: `gemma-4-31b-it-qat-w4a16-ct`, sin otro modelo | Registro del piloto (identificador y versión en Kaggle Models) |
| Servidor del modelo: los parámetros de HARNESS § 3.1 | Registro del piloto (hash del guion de arranque) |
| Parámetros de muestreo del kit | Dentro del hash del envío |
| Presupuesto y concurrencia | Sección D; registro del piloto |

`scripts/kaggle_replicas.py` rechaza recibos que mezclen subconjunto, envío, `tasks.jsonl`, versión del
arnés o imagen.

## D. Presupuesto por tarea

### D.1 Fórmula

El presupuesto de la línea base es el mayor que cabe en el envío real, no el valor por defecto del arnés
(60 min, HARNESS § 7.1) ni el del ejemplo del kit.

```text
b = min(60, floor( c · (T − m) · (1 − r) / N − s ))      minutos por tarea
```

| Símbolo | Valor | Fuente |
|---|---|---|
| T | 720 min | Página *Evaluation*: 12 h para todas las tareas |
| N | 120 | Página *Data*: «unas 120 tareas» |
| r | 0,10 | Elección de este documento: N es aproximado y el tiempo de cada tarea fluctúa. Con r = 0,10 caben hasta 133 tareas |
| c | por cerrar | Tareas en paralelo en el envío real (D.2) |
| m | por cerrar | Minutos de carga del modelo, medidos en el piloto (D.2) |
| s | por cerrar | Minutos de montaje del sandbox por tarea (D.2) |

Con todas las tareas agotando `b`, las N tareas y la carga del modelo ocupan como mucho `T · (1 − r)`. Es
el caso peor: un envío válido no puede pasarse de 12 h. Si la fórmula da menos de 2 min, el presupuesto no
se fija y decide el dueño.

Valores candidatos (`python -m scripts.kaggle_prereg presupuesto`):

| c | m = 0, s = 0 | m = 15, s = 1 | m = 30, s = 2 |
|---|---|---|---|
| 1 | 5 | 4 | 3 |
| 2 | 10 | 9 | 8 |
| 4 | 21 | 20 | 18 |

Los otros tres límites quedan en los valores que el guion de puntuación aplica cuando el envío no los
cambia (HARNESS § 7.1): **100 llamadas a herramientas, 500 turnos y 300 s por comando**. Solo el tiempo se
deriva, porque es el único que el límite de 12 h restringe.

**Diferencia con el kit.** El `eval_config.yaml` del kit trae valores de ejemplo mucho menores en los
cuatro límites (HARNESS § 7.1). La línea base cambia ese archivo y nada más. Es una desviación declarada:
la condición A es «el kit con el presupuesto que cabe en 12 h».

**Cómo se pasa.** El presupuesto queda en
`experiments/gemma_developer_agent/conditions/a_linea_base/eval_config.yaml`, que es un archivo propio y
se versiona con su SHA-256; el directorio del envío es el kit verificado más ese archivo, y su hash es el
`submission_sha256`. La CLI local `swegemma eval` 0.2.7 **no lee** `eval_config.yaml` (HARNESS § 7.1
atribuye esa lectura al guion de puntuación de Kaggle, que no viene en el paquete), así que los mismos
cuatro valores se pasan además por opciones:

```bash
swegemma eval --tasks <tasks.jsonl> --snapshots-dir <snapshots> --results-dir <directorio nuevo> \
  --submission-dir experiments/gemma_developer_agent/conditions/a_linea_base \
  --sandbox <backend declarado> --image <imagen declarada> --task-ids <lista test del subconjunto> \
  --concurrency <c> --max-time-minutes <b> --max-tool-calls 100 --max-turns 500 --timeout-seconds 300 \
  --display quiet
```

`python -m scripts.kaggle_prereg comprobar` exige que el archivo y la fórmula digan lo mismo. Que el
prompt muestre esos valores se comprueba en el piloto, en la sección de presupuesto del prompt que guarda
la traza de cada tarea (HARNESS § 5.2 y § 9.2).

### D.2 Piloto

Una corrida corta en el notebook L4×4, **que no cuenta como réplica** y cuyos resultados por tarea no se
reportan ni se usan para decidir nada salvo lo que sigue. Usa solo tareas de **entrenamiento** del
subconjunto ya commiteado: las dos primeras por `instance_id` de cada repositorio de entrenamiento y las
dos de enunciado más largo (longitud en caracteres; empates por `instance_id`). Como mucho 8 tareas, con
`--max-time-minutes 5`.

Deja un registro versionado (`preregistro/piloto_v1.json`, solo números y hashes) con:

- **c.** La concurrencia del envío real es del guion de puntuación de Kaggle, no del participante: el
  `eval_config.yaml` no tiene esa clave (HARNESS § 7.1). Se toma de una fuente citada (el guion de
  puntuación, si el dueño puede leerlo en la competencia, o una respuesta de los organizadores). **Sin
  fuente, c = 1**, el supuesto más conservador. Las réplicas usan `--concurrency c`.
- **m.** Minutos desde que arranca el servidor del modelo hasta que responde, redondeados hacia arriba.
- **s.** La media de la duración de la verificación sin parche de las tareas válidas, tomada del archivo
  de validez, redondeada hacia arriba a 0,1 min. Incluye ejecutar las pruebas, así que es una cota
  superior del montaje.
- **`max_output_tokens`.** Riesgo sin verificar: el servidor podría rechazar el valor del kit (16 384) con
  prompts largos (#103). Si en el piloto no hay ningún rechazo, queda 16 384. Si hay alguno, la condición
  A no se puede correr tal cual: el valor baja a 8 192 en una copia del archivo de muestreo, se declara
  como segunda desviación del kit y cambia el hash del envío. Si con 8 192 también hay rechazos, se
  detiene y decide el dueño.
- La duración máxima de una sesión, el identificador y la versión del modelo y el hash del guion que
  arranca el servidor.
- Dos comprobaciones: que la sección de presupuesto del prompt muestra los cuatro valores, y si la CLI
  local aplica la compactación de contexto que HARNESS § 7.2 describe para el guion de puntuación. En
  `swegemma` 0.2.7 la CLI no la configura; se anota lo observado (sección H).

## E. Cómputo y regla de reducción

### E.1 Fórmula

Una corrida de `n` tareas con presupuesto `b` y concurrencia `c` ocupa como mucho

```text
horas ≤ ( m + n · (s + b + v) / c ) / 60          v = minutos de verificación por tarea
```

Por la fórmula de D.1, `(s + b) / c ≤ T · (1 − r) / N = 5,4 min` para cualquier `c`. La parte del agente y
el montaje cuesta entonces como mucho **5,4 min de L4×4 por tarea**, y la cuota se descuenta al doble
(página *Upgraded Accelerators*). La carga del modelo por sesión y la verificación se suman aparte y se
miden en el piloto.

Horas utilizables: `0,8 · (Q / 2) · W`, con `Q` la cuota semanal y `W` las semanas enteras entre el día en
que se lee la cuota y el **2026-11-05**, una semana antes del cierre del Paper Track. El 20 % restante es
para la carga del modelo, la verificación, el piloto y las repeticiones por infraestructura.

### E.2 Escalera

Para que la línea base no deje a la campaña sin cómputo, cada escalón suma la línea base y una **campaña
de referencia para el cálculo**: un pase de A sobre las tareas de entrenamiento (los episodios de C) y dos
condiciones nuevas, B y C, sobre las tareas de prueba, con A reutilizada de la línea base. No es un
compromiso de #104, que fija su propio diseño.

Con todas las tareas válidas (`python -m scripts.kaggle_prereg computo --validas fastapi/fastapi=67
Textualize/rich=48 psf/requests=13 encode/httpx=1`):

| Escalón | Reservado | Réplicas de A | Corridas por condición nueva | Corridas de tarea | Horas L4×4 | Horas de cuota |
|---|---|---|---|---|---|---|
| 1 | fastapi | 3 | 2 | 531 | 47,79 | 95,58 |
| 2 | fastapi | 2 | 2 | 464 | 41,76 | 83,52 |
| 3 | rich | 3 | 2 | 417 | 37,53 | 75,06 |
| 4 | rich | 2 | 2 | 369 | 33,21 | 66,42 |
| 5 | fastapi | 2 | 1 | 330 | 29,70 | 59,40 |
| 6 | rich | 2 | 1 | 273 | 24,57 | 49,14 |
| 7 | rich | 2 | sin campaña | 96 | 8,64 | 17,28 |
| 8 | fastapi | 2 | sin campaña | 134 | 12,06 | 24,12 |

**Regla.** Se elige el primer escalón, en este orden, cuyo repositorio sea apto (sección B) y cuyas horas
quepan en las horas utilizables. Los números se recalculan con las tareas válidas medidas. El escalón fija
el repositorio y las réplicas de A; la columna de la campaña solo dice cuánto queda para #104.

Es decir, se reduce en este orden: la tercera réplica de A; el repositorio (de fastapi a rich); las
corridas por condición de la campaña; la campaña entera. Con los escalones 7 u 8 la línea base se mide
igual y la campaña no cabe: decide el dueño (más cómputo, o un paper sin campaña). Si no cabe ni el
escalón 7, no se corre nada.

**Lo que nunca se reduce:** el presupuesto por tarea (cambiarlo cambia el prompt y lo que se mide), el
mínimo de 2 réplicas y las tareas del subconjunto una vez commiteado.

Lo que cuesta además lo que la referencia no incluye: la condición D con dos corridas, 12,06 h (fastapi) u
8,64 h (rich); cada pase adicional sobre el entrenamiento, 5,58 h u 7,29 h. Son cotas de la misma fórmula.

## F. Qué se reporta y con qué comando

### F.1 Recibos y análisis

Por cada réplica, una vez, desde la salida del arnés (no sobrescribe):

```bash
python -m scripts.kaggle_replicas convertir --task-results <results-dir>/task_results.jsonl \
  --patches <results-dir>/patches --replica <k> --condicion A \
  --envio experiments/gemma_developer_agent/conditions/a_linea_base \
  --tasks experiments/gemma_developer_agent/data/tasks.jsonl \
  --subconjunto experiments/gemma_developer_agent/preregistro/subconjunto_linea_base_a.json \
  --version-arnes <versión declarada> --imagen-sandbox <imagen declarada> \
  --salida evidence/kaggle-baseline-a-v1/replica_<k>.jsonl
```

Los recibos se commitean **antes** de analizar. Después:

```bash
python -m scripts.kaggle_replicas analizar --recibos evidence/kaggle-baseline-a-v1 \
  --subconjunto experiments/gemma_developer_agent/preregistro/subconjunto_linea_base_a.json \
  --envio experiments/gemma_developer_agent/conditions/a_linea_base \
  --salida-json results/kaggle-baseline-a-v1/analisis.json \
  --salida-md results/kaggle-baseline-a-v1/analisis.md
```

Con α = 0,05, el valor por defecto. Las dos salidas se publican sin editar y la lectura va en
`docs/results/kaggle-baseline-a.md`.

### F.2 Qué se reporta

- **Tasa principal por réplica: resueltas / tareas del subconjunto**, con numerador y denominador. Un
  fallo del agente (parche vacío, timeout, presupuesto agotado, parche que no aplica, pruebas que fallan)
  cuenta como no resuelta. La tasa sobre válidas es secundaria. Las tasas de las réplicas no se promedian
  en una sola cifra de cabecera.
- No resueltas por motivo, por réplica.
- **Tareas que cambian de resultado**: numerador, denominador y lista.
- Por cada par de réplicas: tabla 2×2, acuerdo, discordancia con su intervalo y p de McNemar exacto.
- Tabla por tarea, desglose por repositorio, diferencia mínima significativa y suelo.
- Descriptivo, de los recibos: llamadas a herramientas y duración por tarea.

### F.3 Corrida válida y códigos de salida

| Salida de `analizar` | Qué significa | Qué se hace |
|---|---|---|
| 0 | Todas las tareas del subconjunto tienen resultado del agente en todas las réplicas | **Corrida válida.** Solo sobre este reporte se leen las reglas de la sección G |
| 1 | Faltan tareas o hay errores de infraestructura | No es una corrida válida. Se repite lo afectado (abajo) y se vuelve a analizar. El reporte con salida 1 se conserva y se menciona en la lectura |
| 2 | Recibos ilegibles, incoherentes, mezclados o fuera del subconjunto | No hay reporte. No se edita ningún recibo: se corrige el código o la conversión; si el defecto está en los recibos, se publica una campaña nueva en otro directorio |
| 3 | Error del propio script | Se corrige el script en un PR revisado y se analiza otra vez sobre los mismos recibos |

**Repetir por infraestructura.** El análisis de `main` rechaza dos recibos de la misma tarea y réplica,
así que hoy no hay forma de sustituir un recibo `infra_error` por el de su repetición sin editar el
original. Con esa herramienta, lo que se repite es **la réplica completa**, con un número de réplica
nuevo; el reporte válido se calcula nombrando en `--recibos` solo los archivos de las réplicas completas,
y los de las incompletas se conservan en el mismo directorio y se listan en la lectura. Una réplica solo
se descarta por tener errores de infraestructura o tareas faltantes, nunca por su tasa. Si antes del
primer recibo se mergea un cambio revisado que permita repetir solo la tarea, se usa ese: es el parámetro
`repeticion_infra`.

**Tope.** Como mucho dos réplicas más que las fijadas. Si con eso no hay 2 réplicas completas, la línea
base no llegó a salida 0: la lectura publica el reporte con salida 1, no aplica ninguna regla de la
sección G y la campaña no empieza hasta arreglar la causa.

## G. Reglas de decisión hacia #104

Se leen del reporte con salida 0. Notación, con los nombres del JSON:

- `n`: tareas del subconjunto.
- `S = 6 / n`: `margen.suelo.diferencia_tasa`.
- `M`: `margen.diferencia_minima_significativa`. Es nulo cuando ni el límite superior de la discordancia
  llega a 6 pares; entonces manda el suelo. Se usa **`M* = max(S, M)`**.
- `L`: el menor número de resueltas entre las réplicas. `U`: el menor número de no resueltas.

**G1 · Estabilidad.** Si algún par de réplicas tiene `mcnemar_p_exacto ≤ 0,05`, A difiere de sí misma más
de lo que explica el azar de una corrida. Se lee como señal de que algo cambió entre sesiones (servidor,
entorno), no como ruido del agente: se revisa la infraestructura, no se aplican G2 a G4 y la campaña no
empieza. Se declara que esta alarma salta por azar hasta un 5 % de las veces por par.

**G2 · Ruido.** Los dos umbrales son las resoluciones que habrían tenido sin ruido las particiones de 40
y de 24 tareas: 6/40 = 0,15 y 6/24 = 0,25.

| Caso | Condición | Qué necesita la campaña | Qué se afirma |
|---|---|---|---|
| Ruido bajo | `M* ≤ 0,15` | Las mismas `n` tareas; basta **1 corrida por condición**, 2 si el cómputo alcanza | «Una corrida por condición distingue diferencias de `M*` o más» |
| Ruido intermedio | `0,15 < M* ≤ 0,25` | Las mismas `n` tareas y **al menos 2 corridas por condición**; el pre-registro de #104 define el análisis sobre corridas repetidas | Con una sola corrida solo se podrían declarar diferencias de `M*` o más |
| Ruido dominante | `M* > 0,25` | La campaña no se corre como confirmatoria | «Con este kit, este presupuesto y `n` tareas, repetir A cambia el resultado de x de `n` tareas, y una diferencia entre condiciones menor que `M*` no se distingue de repetir A». Es un resultado y se publica como tal. Una campaña descriptiva, sin veredictos de apoyada o refutada, queda a decisión del dueño |

En los tres casos, la campaña no declara una diferencia menor que `M*`. `M*` es un umbral de
significación, no de potencia: un efecto real de ese tamaño se detectaría más o menos la mitad de las
veces.

**G3 · Suelo y techo.** Para que una condición gane a A hacen falta 6 tareas que A no resuelva; para que
pierda, 6 que A sí resuelva.

| Caso | Condición | Consecuencia |
|---|---|---|
| Margen en los dos sentidos | `U ≥ 6` y `L ≥ 6` | La campaña puede declarar mejora o daño |
| Suelo | `L < 6` | La campaña puede declarar mejora, pero no daño: «refutada por empeorar» queda fuera de alcance y se dice así. La lectura reporta los motivos de las no resueltas; si predominan el timeout o el presupuesto agotado, se dice que el límite de 12 h domina, y **el presupuesto no se cambia** |
| Techo | `U < 6` | La campaña no puede declarar mejora sobre este subconjunto: no se corre para ese fin. Se reporta «A resuelve casi todas» y se anota la contaminación como explicación posible, sin concluirla |
| Las dos | `U < 6` y `L < 6` | Solo ocurre si una réplica resuelve casi todo y otra casi nada: se trata como G1 |

**G4 · N y selección.** La campaña usa las mismas `n` tareas del subconjunto. No se quitan las tareas
inestables ni se elige un subconjunto después de ver cuáles cambian: sería seleccionar por resultado.
Cambiar de tareas exige un subconjunto nuevo y una línea base nueva.

**G5 · Reutilizar A.** Las réplicas de la línea base valen como brazo A de la campaña solo si los recibos
de las otras condiciones tienen el mismo `subset_sha256`, `tasks_sha256`, versión del arnés, entorno,
presupuesto y concurrencia. Si algo difiere, A se corre de nuevo.

**G6 · Si el cómputo no alcanza para lo que pide G2.** Se reduce primero la condición D, que #104 ya
condiciona al cómputo, y después las corridas por condición hasta el mínimo de G2. Si ni así cabe, lo
decide #104 en su pre-registro antes de sus datos.

## Predicciones (antes de cualquier corrida)

Del autor, que no ha visto ninguna corrida del modelo:

- **P1.** Habrá tareas que cambian de resultado entre réplicas: la temperatura es mayor que cero, no hay
  semilla y el límite es de tiempo de reloj.
- **P2.** Con el presupuesto que cabe en 12 h, una parte apreciable de las no resueltas será por timeout
  o presupuesto agotado. No sé si llegará a suelo (G3).
- **P3.** Sin predicción sobre el caso de G2.

## H. Desviaciones declaradas y amenazas a la validez

**Respecto del kit.**

- `eval_config.yaml`: los cuatro límites cambian (sección D).
- `max_output_tokens`: solo si el piloto muestra rechazos (D.2).
- Nada más: prompts, herramientas, subagente, adaptadores y muestreo son los del kit.

**Respecto de la evaluación real.**

| Aspecto | Evaluación de Kaggle | Esta línea base |
|---|---|---|
| Tareas | Unas 120 de repositorios privados | Las válidas de un repositorio público y popular |
| Guion | El de puntuación de la competencia | La CLI `swegemma eval`, que no lee `eval_config.yaml` ni configura la compactación de contexto de HARNESS § 7.2 |
| Máquina | La de puntuación, con 4 × L4 | Un notebook de Kaggle con L4×4 y un servidor arrancado por nosotros con los parámetros de HARNESS § 3.1 |
| Sandbox | Contenedores Docker (HARNESS § 4.1) | El backend que permita el notebook, declarado en A.1 |
| Presupuesto | El que ponga cada participante | El mayor que cabe en 12 h en el caso peor |
| Concurrencia | La del guion de puntuación | La misma si hay fuente; si no, 1 |

Las tasas de esta línea base **no predicen** el puntaje de la tabla de posiciones.

**Amenazas.**

- **Contaminación.** El modelo pudo ver los repositorios y los arreglos. La comparación entre condiciones
  es pareada sobre las mismas tareas, pero la contaminación puede acercar A al techo y reducir el margen.
- **Un solo repositorio de prueba.** Lo que se mida vale para ese repositorio. No se separa «repositorio
  no visto» de «dominio distinto».
- **Tareas fijas, no muestreadas.** Los intervalos y la diferencia mínima describen estas tareas; no se
  generaliza a otras. Tres réplicas dan tres pares que comparten tareas y no son independientes.
- **El tiempo es de reloj.** La carga de la máquina cambia cuánto alcanza a hacer el agente en `b`
  minutos; es parte del ruido que se mide y también de lo que no se controla.
- **Clasificación de infraestructura.** Un timeout o un proceso matado en las pruebas se excluye como
  infraestructura, aunque un parche del agente puede causarlo. Si una misma tarea da ese error en dos
  réplicas, la lectura lo señala.
- **Supuesto de concurrencia.** Si `c` real es mayor que 1 y no se logra una fuente, el presupuesto queda
  más corto que el que un participante podría usar, y la línea base subestima a A.
- **Caso peor.** El presupuesto supone que todas las tareas agotan su tiempo. Un participante puede
  apostar a un tope mayor.
- **Entorno arreglado a mano.** Cada rueda añadida aleja el sandbox del distribuido. Queda declarada en
  A.1, pero la validez medida es la de ese entorno.
- **Conocimiento previo.** Los umbrales de G2 y el mínimo de 40 tareas se eligieron sin datos de Gemma,
  conociendo los conteos por repositorio y por fecha.

## I. Orden de commits y parámetros abiertos

| Commit | Contenido | Condición |
|---|---|---|
| **C0** | Este documento, `linea_base_a.json` con todo abierto, `scripts/kaggle_prereg.py` y sus tests | — |
| **C1** | `scripts/kaggle_validez.py` con tests sintéticos, sin datos. Opcional: el cambio de `kaggle_replicas.py` para repetir una tarea | Revisado y mergeado |
| **C2** | Declaración del entorno y `validez_tareas_v1.json`; cierra `entorno_sandbox` y `validez_tareas` | Repetición del orquestador |
| **C3** | Cierra `cuota` | Comentario del dueño en #101 |
| **C4** | `subconjunto_linea_base_a.json`; cierra `subconjunto` y `replicas` | C2 y C3 |
| **C5** | Registro del piloto, `eval_config.yaml` de la línea base; cierra `piloto`, `presupuesto` y `repeticion_infra` | C4 |
| **Compuerta** | `python -m scripts.kaggle_prereg comprobar` sale con **0** en `main` | Antes de la primera réplica |
| **C6** | Recibos de cada réplica en `evidence/kaggle-baseline-a-v1/` | Después de la compuerta; antes de analizar |
| **C7** | Salidas del análisis y lectura en `docs/results/kaggle-baseline-a.md` | Verificación independiente |

Cómo se verifica: el orden de los commits en `main`; `git diff C0 -- docs/preregistration/kaggle-baseline-a.md
scripts/kaggle_replicas.py scripts/kaggle_split.py` vacío en C6, salvo el cambio declarado de C1; el
resumen del bloque `fijos` igual al de arriba; `converted_utc` de cada recibo posterior a la fecha de C5; y
los hashes de los recibos iguales a los declarados en C4 y C5. De C2 a C5, cada commit solo rellena
`valor` en `linea_base_a.json` y añade los archivos que cita.

Parámetros abiertos. `comprobar` sale con 1 mientras quede alguno, y con 2 si un valor cerrado contradice
su regla (el presupuesto frente a la fórmula, el repositorio y las réplicas frente a la escalera, cada
archivo frente a su hash):

| Parámetro | Regla | Quién lo cierra |
|---|---|---|
| `entorno_sandbox` | A.1 | El implementador del paso de validez; revisa el orquestador |
| `validez_tareas` | A.2 a A.4 | El implementador del paso de validez; el orquestador repite una muestra |
| `cuota` | E.1: cuota semanal, semanas hasta el 2026-11-05 y duración máxima de sesión | El dueño la lee en Kaggle (#101); el orquestador la traslada |
| `subconjunto` | B y E.2 | El orquestador |
| `replicas` | C y E.2 | El orquestador |
| `piloto` | D.2: `c` con su fuente, `m`, `s`, `max_output_tokens` | Quien ejecute el piloto; revisa el orquestador |
| `presupuesto` | D.1 | El orquestador |
| `repeticion_infra` | F.3 | El orquestador |

## Fuera de alcance

Las condiciones B, C y D, las skills, los señuelos y los envíos a Kaggle (#104, #106). Este documento no
fija el diseño de la campaña: le deja medido el ruido de A y las reglas con que leerlo.
