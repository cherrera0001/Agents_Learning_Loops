# Pre-registro · Línea base A del experimento Kaggle Gemma 4 y su variación entre réplicas (#103)

**Registro**: los commits de este documento anteriores a su merge en `main`, hechos **antes** de correr
ningún modelo y antes de cualquier recibo. Después del merge solo cambia por una enmienda declarada
(sección I.4); cambiarlo de otro modo después de ver datos lo invalida en ese punto, y toda desviación se
reporta como tal en la lectura de resultados.

**Qué es y qué no es.** Fija cómo se medirá la condición A (el kit oficial de la competencia) contra sí
misma. No afirma ningún resultado: no hay ninguna corrida con modelo. Varios datos que el diseño necesita
todavía no existen (qué tareas son válidas, la cuota de GPU, la concurrencia real). Este documento no los
inventa: escribe la regla que determina cada uno, quién lo cierra y cómo, y exige que todos estén cerrados
por un commit antes del primer recibo (sección I).

**Carácter: exploratorio.** El autor leyó la documentación del arnés, el código del paquete instalado
(`swegemma` 0.2.7), los archivos de configuración del kit, las páginas públicas de la competencia y los
comentarios de los issues #100, #101, #103 y #104. De `tasks.jsonl` calculó solo los agregados de la
sección «Datos» y ejecutó `scripts/kaggle_split.py`; no leyó enunciados, parches ni pruebas. Conoce, por
[`fase2_sin_parche.json`](../../experiments/gemma_developer_agent/calibracion/fase2_sin_parche.json), qué
tareas señala como anómalas el notebook de un competidor: esa lista no tiene recibo propio y no se usa
aquí para elegir ni excluir nada. Dos revisores independientes leyeron una versión anterior de este
documento, sin datos de Gemma, y sus correcciones están incorporadas.

**Términos.** «Arnés» es aquí el paquete `swegemma` de la competencia, no el harness de experimento del
[glosario](../entorno/glosario.md) (término 6). Las «skills» de la campaña #104 son archivos `SKILL.md`
del envío a Kaggle: no son skills de memoria ni skills de entorno (términos 4 y 5). El arnés se cita por
sección («HARNESS § 7.1») y con palabras propias, sin copiar su texto
([`kaggle_specifications.md`](../../experiments/gemma_developer_agent/docs/kaggle_specifications.md)).

Este documento **sustituye** en lo que toca a la línea base a los borradores de
`experiments/gemma_developer_agent/drafts/`, que siguen diciendo 60 minutos por tarea.

Los valores fijados están también en
[`linea_base_a.json`](../../experiments/gemma_developer_agent/preregistro/linea_base_a.json), bloque
`fijos`. Su resumen SHA-256 es:

```text
f0fdb8caeedb145fd5443a649026ce83766e981fd3664a80d0608689d3d0f346
```

`python -m scripts.kaggle_prereg comprobar` lo recalcula y sale con 2 si no coincide.

## Punto de partida

| Hecho | Fuente |
|---|---|
| Las 129 tareas públicas son de entrenamiento: fastapi 67, rich 48, requests 13, httpx 1 | `python -m scripts.kaggle_eda resumen` sobre `tasks.jsonl` (SHA-256 `e4b3fd60…8ad6`); HARNESS § 9.1 |
| El conjunto con que Kaggle puntúa tiene unas 120 tareas de repositorios privados | Página *Data* del Code Track, citada en #100 |
| El envío real tiene 12 h para todas las tareas, incluido el montaje del sandbox y sin contar la validación de parches | Página *Evaluation*, citada en #100 |
| El cómputo son notebooks de Kaggle con L4×4, sin internet, que consumen cuota de GPU al doble; la página avisa de que ese factor puede subir | Página *Upgraded Accelerators*; decisión del dueño en #101 |
| La cuota semanal de GPU de la cuenta **no está medida** | #101 |
| La partición de `main` hoy no excluye ninguna tarea; la validez de cada tarea **no está medida** | Comentario del orquestador en #103 (2026-10-03) |
| El presupuesto por tarea entra en el prompt del agente | HARNESS § 5.2 |

## 1. Pregunta

> Con el kit oficial sin cambios de prompt ni de herramientas, ¿cuánto varía el resultado de la condición A
> al repetir la misma corrida sobre las mismas tareas? ¿Qué diferencia entre dos condiciones no se
> distingue de esa variación?

La respuesta decide cuántas réplicas y qué margen necesita la campaña A/B/C/D de #104, o si esa campaña
puede afirmar algo.

## Datos

Agregados de `tasks.jsonl`, de `python -m scripts.kaggle_eda resumen --tasks <tasks.jsonl>`. Qué publica
el comando y qué no:

- no imprime enunciados, parches, pruebas ni identificadores de tarea;
- de un grupo con **menos de 5 tareas** solo dice cuántas son, sin ningún estadístico;
- no da mínimos ni máximos, que son el valor de una tarea concreta: da los percentiles 10, 25, 50, 75 y
  90 y, para los extremos, conteos por umbral.

Un cuantil sigue siendo un número derivado de los datos de la competencia; lo que estas reglas evitan es
publicar el valor de una tarea identificable. Un conteo por umbral o por año puede ser pequeño: dice
cuántas tareas hay, no cuál ni cuánto mide.

- 129 tareas con 8 campos. `hints_text` está vacío en las 129. No hay listas de pruebas que deban fallar
  o pasar: **la validez de una tarea solo se puede medir** (sección A). Hay 127 `base_commit` distintos.
- 86 de las 129 tareas son del cuarto trimestre de 2025 en adelante.
- Parches de referencia: 60 cambian 10 líneas o menos; 16 cambian más de 100; 3, más de 1 000.
- Parches de referencia: 91 tocan un solo archivo; 3 tocan más de 10.
- Enunciados: 24 tienen 100 caracteres o menos; 2 tienen más de 5 000.

Unidades y método de cada medida:

| Medida | Qué cuenta |
|---|---|
| Enunciado, en caracteres | Caracteres Unicode de `problem_statement` (no bytes ni tokens) |
| Parche, en **líneas cambiadas** | Líneas añadidas más líneas quitadas **dentro de los bloques `@@`**, contadas con las longitudes que declara cada bloque. No entran las cabeceras `---` y `+++` ni las líneas de contexto |
| Parche, en líneas totales | Todas las líneas del texto del diff. Es **otra variable**: su mediana es 32, frente a 12 de las líneas cambiadas. Este documento no la usa |
| Archivos por parche | Cabeceras de archivo: una línea `--- ` seguida de una `+++ `. Los diffs de `tasks.jsonl` no traen la línea `diff --git`; contar esa línea da 0 en las 129 |
| Percentiles | `statistics.quantiles(n=20, method="inclusive")` de Python |

Toda cifra de «líneas» de este documento es de líneas cambiadas. Percentiles 10 / 25 / 50 / 75 / 90:

| Repositorio | Tareas | Por año | Enunciado (caracteres) | Parche de referencia (líneas) | Parche de pruebas (líneas) |
|---|---|---|---|---|---|
| fastapi | 67 | 2025: 41; 2026: 26 | 146,4 / 269,5 / 677 / 1 241,5 / 2 530,6 | 3 / 5,5 / 18 / 66,5 / 261,8 | 13,2 / 29,5 / 76 / 170,5 / 392,8 |
| rich | 48 | 2023: 9; 2024: 17; 2025: 6; 2026: 16 | 67,4 / 79 / 138,5 / 695 / 1 218,4 | 2 / 2 / 9 / 34,25 / 76,3 | 6 / 14 / 20 / 31,25 / 71,7 |
| requests | 13 | 2023: 1; 2024: 4; 2026: 8 | 237,4 / 268 / 406 / 580 / 677 | 2 / 3 / 4 / 10 / 15,8 | 8 / 8 / 11 / 15 / 21,8 |
| httpx | 1 | — | 1 tarea, sin estadísticos | — | — |
| Las 129 | 129 | — | 75 / 146 / 418 / 1 000 / 1 801,4 | 2 / 4 / 12 / 44 / 127,2 | 8 / 15 / 31 / 92 / 238,6 |

**No se excluye ninguna tarea por tamaño ni por longitud del enunciado.** Excluir por una propiedad del
parche de referencia modificaría el benchmark con información que el agente no tiene. En su lugar, la
lectura reporta, además del total, la tasa por **terciles** de dos medidas, con cortes fijados ahora sobre
las 129 tareas:

| Medida | Tercil 1 | Tercil 2 | Tercil 3 |
|---|---|---|---|
| Líneas del parche de referencia | hasta 5 | de 6 a 26 | más de 26 |
| Caracteres del enunciado | hasta 237 | de 238 a 739 | más de 739 |

Es un análisis descriptivo declarado, sin regla de decisión. Los cortes son de las 129, así que dentro del
subconjunto los tres grupos no tendrán el mismo tamaño; un grupo con menos de 5 tareas se reporta sin
su número de resueltas. Los estadísticos del parche de referencia son del
evaluador: no entran en prompts ni en skills.

## A. Pasos previos: ensayo de notebook y validez de las tareas

Una tarea solo sirve para medir si **discrimina**: sus pruebas fallan sin arreglo y pasan con el parche de
referencia, dentro del mismo sandbox que verificará al agente. Hoy eso no está medido.

**Único uso del parche dorado.** Este paso es el único lugar del experimento donde se usa el parche de
referencia de `tasks.jsonl` (criterio 4 de #103). Se usa en las 129 tareas y no solo en las de prueba,
porque la campaña #104 cuenta un episodio de entrenamiento como éxito con esta misma verificación, y una
tarea de entrenamiento que no discrimina daría éxitos o fracasos falsos. Lo que sale del paso es una
clase por tarea, no el parche.

**Frontera de fuga.** El **evaluador** es quien ejecuta o repite la validez y la verificación: lee
`tasks.jsonl` completo y las salidas crudas del arnés. Reglas:

- quien ejecuta o repite la validez no redacta skills ni señuelos de #104;
- ningún agente de #104 lee las salidas crudas (`data/`, logs de pruebas, trazas de la validez);
- el parche no entra en el prompt del agente, en el envío, en los recibos ni en el repositorio, y tampoco
  su SHA-256, que es un dato derivado de la competencia;
- el guion guarda la **clase** de un error del arnés, nunca su texto.

### A.0 Ensayo de notebook (commit C0.5)

Antes de medir la validez se hace un ensayo en un notebook de Kaggle con L4×4. **Solo mide cosas que no
son resultados**: no se registra qué tareas se resuelven. Usa cuatro tareas que nunca serán de prueba: las
tres primeras de requests por `instance_id` y la de httpx.

El ensayo corre con la condición A de la Enmienda 2, no con el kit sin cambios. El `eval_config.yaml`
de la línea base no existe hasta C5, así que los límites se pasan por las opciones de la CLI:
`--max-time-minutes 5 --max-tool-calls 40 --max-turns 100 --timeout-seconds 60`. Los 5 minutos son los
de esta sonda; los 4 minutos de A son los del envío.

Deja un registro versionado (`preregistro/ensayo_notebook_v1.json`, esquema `kaggle-notebook-trial/1`):

| Medida | Para qué |
|---|---|
| Si el notebook tiene Docker; backend que funciona (`docker` o `subprocess`, HARNESS § 4.1) | Fija el backend del entorno de A.1 |
| Si el servidor del modelo arranca con los parámetros de HARNESS § 3.1; segundos de carga; hash del guion de arranque; identificador y versión del modelo | Viabilidad; carga del modelo |
| Si el kit original compila | Viabilidad |
| Duración máxima de una sesión, declarada por quien ejecuta con su fuente (Enmienda 1) | Partes por réplica (sección C) |
| Tokens por segundo; turnos del modelo completados por tarea en 5 minutos | Viabilidad |
| Peticiones al modelo y cuántas rechaza el servidor por exceder el contexto, con `max_output_tokens` del kit (16 384) | `max_output_tokens` |

**Enmienda 1 (2026-10-03, sección I.4).** Tres precisiones sobre el registro, anteriores a cualquier
recibo:

- **Medidas ausentes en un fallo temprano.** Si el servidor no arranca o el kit no compila, las medidas
  que por eso no existen (modelo, carga, tokens por segundo, backend, turnos, peticiones y rechazos) van
  **ausentes (nulas)** en el registro, no con un número, y el ensayo se cierra como no viable. Un registro
  que traiga un número en una medida que no puede existir se rechaza.
- **Lista de turnos de la repetición.** Si hubo rechazos con 16 384, el registro lleva además la lista
  de turnos de la repetición con 8 192 (`turnos_por_tarea_repeticion`).
- **Informe citado.** El registro cita por su SHA-256 (`informe_sha256`) el informe de sondas que lo
  acompaña, donde quedan el hardware, las versiones y el observable del rechazo.

**`max_output_tokens`.** Se mantiene el 16 384 del kit. El observable de un rechazo es una respuesta HTTP
400 del servidor del modelo cuyo mensaje dice que se excede la longitud máxima de contexto; en el arnés
llega como un error que empieza por `Sandbox execution error:` y contiene `ContextWindowExceededError` o
`maximum context length`. Si el ensayo muestra algún rechazo con 16 384, se repite con 8 192; si con
8 192 no hay ninguno, la línea base usa 8 192 como **desviación declarada del kit**, decidida aquí y antes
de la primera réplica. Si el texto real del rechazo es otro, la lista de marcadores de
`scripts/kaggle_replicas.py` se corrige por **enmienda** (sección I.4) antes del primer recibo. Un
rechazo durante una réplica cuenta como no resuelta (`context_exceeded`), no como infraestructura.

**Compuerta de viabilidad.** El ensayo es viable si el servidor arranca, el kit compila y el agente
completa al menos **5 turnos** del modelo en al menos la mitad de las tareas. Los turnos se toman de la
lista medida con el `max_output_tokens` que queda fijado: la del kit si no hubo rechazos con 16 384 y la
de la repetición con 8 192 si los hubo (Enmienda 1). Cinco turnos es una
convención: lo mínimo para leer, editar y entregar. Si no es viable, o si hay rechazos también con 8 192,
`comprobar` sale con 2 y no se sigue con este diseño. El dueño elige entre detener el experimento o una
**línea base v2** por enmienda (sección I.4), con otra regla de presupuesto, antes de medir nada más.

### A.1 Entorno de pruebas declarado

El entorno del sandbox se arregla y se declara en un archivo versionado
(`preregistro/entorno_sandbox_v1.json`, esquema `kaggle-sandbox-env/1`) con:

- el backend que fijó el ensayo y la imagen con su identificador, o el intérprete y su versión;
- la versión del arnés y el SHA-256 de la lista ordenada `nombre<TAB>sha256` del directorio de ruedas;
- cada arreglo aplicado (rueda añadida o sustituida, variable de entorno, parche del sistema) con el
  fallo que corrige;
- el SHA-256 del registro del ensayo.

Fallos conocidos hoy: uno **medido**, la importación de fastapi falla por ruedas faltantes o incompatibles
(comentario del orquestador en #103); y uno **reportado sin recibo**, un error de codificación cp1252 en
un host Windows ([`entorno_local.md`](../../experiments/gemma_developer_agent/docs/entorno_local.md)
§ 4.2).

**El entorno de la validez es el entorno en que se verifican las réplicas.** Si el notebook no permite
Docker, la validez se mide con `subprocess` en una sesión de notebook sin GPU, y una medición local con
Docker solo vale como ensayo. Si el entorno cambia después de medir, la validez se mide otra vez.

### A.2 Qué se mide

Para cada una de las 129 tareas, dos verificaciones, cada una ejecutada **dos veces**:

1. **Sin parche**: la verificación de la fase 2 del arnés (HARNESS § 8.2) con un parche vacío.
2. **Con el parche dorado**: la misma función, con el parche de referencia en el lugar del parche del
   agente.

Las dos las hace el mismo guion versionado (`scripts/kaggle_validez.py`, commit C1), que llama a la
función de verificación del arnés; la CLI de `swegemma` 0.2.7 no tiene una opción para verificar un parche
dado. `swegemma eval --skip-agent-patch` (HARNESS § 9.1) se usa solo como contraste en la muestra de
revisión. De cada ejecución el guion deja el `instance_id`, el repositorio, `resolved`, el código de
salida de las pruebas, la clase del error del arnés si lo hay y la duración. Se mergea con tests sobre
datos sintéticos antes de medir.

Coste, **estimado y por medir**: 516 ejecuciones. La única duración local que existe es la de una
verificación sin parche, 40,68 s (el `task_results.jsonl` del piloto local, una fila); a ese ritmo serían
unas 6 horas en serie. En disco, unos 21,5 GB de snapshots para las 129 (cifra del orquestador en #103;
en local hay 3) y la imagen del sandbox. Se empieza por fastapi y rich, que son los candidatos a prueba.

### A.3 Clases y regla de exclusión

Una ejecución es **de infraestructura** si el arnés da uno de los errores que
`scripts/kaggle_replicas.py` clasifica como `infra_error`, o si las pruebas no se pudieron ejecutar
(código −1). Un timeout o un proceso matado en las pruebas (124, 137) **no** es infraestructura: cuenta
como no resuelta, igual que en las réplicas. Una ejecución de infraestructura se repite una vez.

Las clases se evalúan en este orden y la primera que se cumple es la de la tarea:

| Orden | Clase | Condición |
|---|---|---|
| 1 | `no_medible` | Alguna de las cuatro ejecuciones es de infraestructura y su repetición también |
| 2 | `inestable` | Las dos ejecuciones de una misma verificación difieren en `resolved` |
| 3 | `pasa_sin_parche` | Sin parche: resuelta en las dos |
| 4 | `dorado_falla` | Con dorado: no resuelta en las dos |
| 5 | `discrimina` | Sin parche: no resuelta en las dos. Con dorado: resuelta en las dos |

**Se excluye toda tarea cuya clase no sea `discrimina`.** No hay excepciones caso por caso. Una tarea que
falla sin parche por un error del entorno también falla con el dorado y queda `dorado_falla`.

**Guarda contra un entorno roto.** Si en un repositorio con 10 tareas o más, **más de la mitad** no son
`discrimina`, se considera que el entorno de ese repositorio no está arreglado. El umbral es una
convención con este argumento: un entorno roto falla al importar el paquete y tumba casi todas las tareas
del repositorio; unas tareas defectuosas sueltas no llegan a la mitad. Se diagnostica, se declara un
entorno nuevo y se mide **una** vez más (`_v2`), conservando el archivo anterior. No hay `_v3`: si tras la
segunda medición la guarda sigue saltando, el dueño elige entre `seguir_excluyendo` y `detener`, y la
decisión se versiona (sección I.3).

### A.4 Qué queda versionado y quién lo hace

El resultado es un archivo **nuevo**,
`experiments/gemma_developer_agent/calibracion/validez_tareas_v1.json` (esquema
`kaggle-task-validity/1`); `fase2_sin_parche.json` no se pisa ni se usa como fuente de exclusiones.
Contiene `sha256_tasks`, el SHA-256 de la declaración del entorno, el registro de las 129 tareas
(identificador, repositorio, clase, códigos de salida y duraciones) y la lista `tareas_invalidas` que lee
`scripts/kaggle_split.py`. Ningún enunciado, parche, prueba, log ni hash del parche. Las salidas crudas
del arnés quedan en `data/`, que git ignora.

Lo ejecuta un agente de entorno, en el papel de evaluador, en la máquina del dueño o en un notebook sin
GPU. El orquestador lo revisa con una repetición propia: todas las tareas excluidas y las 10 primeras
tareas por orden de `sha256(instance_id)`. **Coincide** si cada tarea de la muestra tiene la misma clase;
las duraciones no se comparan. Si alguna clase difiere, el archivo no se mergea.

## B. Subconjunto

**Regla: `leave_one_repo_out`.** La prueba son todas las tareas válidas de un repositorio y el
entrenamiento son las de los demás. El repositorio preferido es `fastapi/fastapi`; el segundo,
`Textualize/rich`. Cuál de los dos se usa lo decide la escalera de la sección E con la validez y la cuota
medidas, no una elección posterior. **La campaña #104 hereda esta partición.**

Opciones que ofrece `scripts/kaggle_split.py`, con las 129 tareas antes de excluir ninguna:

| Regla | Prueba | Suelo 6/N | Entrenamiento | Fechas de las tareas de prueba |
|---|---|---|---|---|
| `temporal_stratified`, N = 24 | 24 | 0,250 | 105 | las más recientes de cada repositorio |
| `temporal_stratified`, N = 32 | 32 | 0,188 | 97 | ídem |
| `temporal_stratified`, N = 40 | 40 | 0,150 | 89 | ídem |
| `leave_one_repo_out`, fastapi | 67 | 0,090 | 62 | todas de 2025 o 2026 |
| `leave_one_repo_out`, rich | 48 | 0,125 | 81 | 26 de 48 son de 2023 o 2024 |
| `leave_one_repo_out`, requests | 13 | 0,462 | 116 | 5 de 13 son de 2023 o 2024 |
| `leave_one_repo_out`, httpx | 1 | no alcanzable | 128 | 1 tarea, sin estadísticos |

El suelo es la menor diferencia de tasa que la prueba de McNemar exacta puede declarar significativa con
α = 0,05: 6 pares discordantes, todos a favor de una condición, sobre N tareas
([`analisis_replicas.md`](../../experiments/gemma_developer_agent/docs/analisis_replicas.md)).

Por qué un repositorio reservado y no la partición temporal:

1. **La evaluación real es sobre repositorios que el agente no vio.** Con la partición temporal, las
   skills de #104 se consolidarían y se probarían en los mismos repositorios; eso mide transferencia
   dentro de un repositorio, que no es lo que pregunta la competencia ni el criterio *Quality* del Paper
   Track (generalización fuera de la competencia). Reservar un repositorio mide transferencia a un
   repositorio sin episodios de entrenamiento.
2. **Resolución.** Con N = 24 el suelo es 6/24: una mejora de 5 tareas de 24 no se podría declarar.
3. **Entrenamiento para #104.** Quedan 62 tareas (rich, requests, httpx) u 81 (fastapi, requests, httpx).

Por qué fastapi antes que rich: tiene 67 tareas frente a 48, y todas son de 2025 o 2026,
mientras que 26 de las 48 de rich son de 2023 o 2024. Los arreglos de las tareas antiguas pueden estar en
los datos de entrenamiento del modelo. No se conoce la fecha de corte del modelo, así que ninguna de las
dos opciones queda libre de ese riesgo.

**«Más reciente» no es solo una ventaja.** En estos datos el repositorio, la fecha y el tamaño van juntos
(sección «Datos»): las tareas de fastapi son las recientes y también las de enunciado más largo (mediana
677 caracteres frente a 138,5), parche más grande (18 líneas frente a 9) y más pruebas (76 frente a 20).
Lo que se mida sobre fastapi no separa el efecto del repositorio del de la fecha ni del tamaño de la
tarea. Además cuesta más GPU (sección E) y su entorno de pruebas es el que hoy falla. Por eso rich es el
segundo y no se descarta.

Lo que esta regla no da: la partición temporal dentro de cada repositorio. Con un repositorio reservado,
parte del entrenamiento es posterior a parte de la prueba; no importa para la pregunta de transferencia
entre repositorios, pero impide leer el resultado como «aprender del pasado para el futuro».

**Mínimo.** Un repositorio solo es apto si le quedan al menos 40 tareas válidas (suelo ≤ 6/40). Si
ninguno de los dos es apto, no hay subconjunto y `comprobar` sale con 2 (decisión `sin_escalon`).

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
recibos. `comprobar --tasks <tasks.jsonl>` regenera la partición y exige que coincida byte a byte.

## C. Réplicas

**Cuántas.** 3 si caben y 2 si no, según la escalera de la sección E. Nunca menos de 2. La tercera
réplica da tres pares en vez de uno y una estabilidad por tarea de 0 a 3; es lo primero que se recorta.

**Qué varía entre réplicas: nada que se configure.** El archivo de muestreo del kit (la entrada
`configs/sampling.yaml` de
[`manifest.json`](../../experiments/gemma_developer_agent/conditions/a_kit/manifest.json)) fija una
temperatura mayor que cero y no fija semilla, y este diseño no añade una: añadirla cambiaría el envío. La
variación que se mide es la de repetir el mismo envío: muestreo del modelo, no determinismo del servidor
y un presupuesto de tiempo de reloj.

**Cómo se repite.** Cada réplica es una invocación nueva de `swegemma eval` en una sesión nueva del
notebook, con el servidor del modelo arrancado de nuevo y un `--results-dir` nuevo. El orden de las tareas
es el de `tasks.jsonl` en todas (la CLI no permite otro).

**Partes.** Una réplica se corre entera en una sesión. Partirla con `--shard-index` y `--num-shards`
(HARNESS § 9.1) está **prohibido salvo que no quepa**: el número de partes es
`ceil((m + n · (b + 2·s) / c) / sesión máxima)`, con los símbolos de la sección D y la sesión máxima del
ensayo; es el mismo en todas las réplicas y `comprobar` lo recalcula.

**Qué se mantiene fijo**, y dónde queda escrito:

| Elemento | Dónde |
|---|---|
| Subconjunto | `subset_sha256` de los recibos |
| Envío: kit verificado contra `manifest.json`, más el `eval_config.yaml` de la sección D | `submission_sha256` de los recibos |
| `tasks.jsonl` | `tasks_sha256` de los recibos |
| Versión del arnés y entorno del sandbox | `harness_version` y `sandbox_image` de los recibos; declaración de A.1 |
| Modelo y cuantización: `gemma-4-31b-it-qat-w4a16-ct`, sin otro modelo | Registro del ensayo |
| Servidor del modelo: los parámetros de HARNESS § 3.1 | Registro del ensayo (hash del guion de arranque) |
| Parámetros de muestreo del kit | Dentro del hash del envío |
| Presupuesto y concurrencia | Sección D; registro de cada corrida (sección F.1) |

`scripts/kaggle_replicas.py` rechaza recibos que mezclen subconjunto, envío, `tasks.jsonl`, versión del
arnés o imagen.

## D. Presupuesto por tarea

### D.1 Fórmula

El presupuesto de la línea base es el mayor que cabe en el envío real, no el valor por defecto del arnés
(60 min, HARNESS § 7.1) ni el del ejemplo del kit.

```text
b = min(60, floor( c · (T · (1 − r) − m) / N − s ))      minutos por tarea
```

| Símbolo | Valor | Fuente |
|---|---|---|
| T | 720 min | Página *Evaluation*: 12 h para todas las tareas |
| N | 120 | Página *Data*: «unas 120 tareas» |
| r | 0,10 | Elección convencional de este documento: N es aproximado y el tiempo de cada tarea fluctúa. Con r = 0,10 caben hasta 133 tareas al mismo ritmo |
| c | por cerrar | Tareas en paralelo en el envío real (D.2) |
| m | por cerrar | Minutos de carga del modelo, medidos en el piloto (D.2) |
| s | por cerrar | Minutos de montaje del sandbox por tarea (D.2) |

Con todas las tareas agotando `b`, la carga del modelo y las N tareas ocupan `m + N · (b + s) / c`, que es
como mucho `T · (1 − r)` = 648 min. Es el caso peor: un envío válido no puede pasarse de 12 h. Si la
fórmula da menos de 2 min, el presupuesto no se fija y `comprobar` sale con 2 (decisión
`presupuesto_bajo_minimo`).

Valores candidatos (`python -m scripts.kaggle_prereg presupuesto`):

| c | m = 0, s = 0 | m = 15, s = 1 | m = 30, s = 2 |
|---|---|---|---|
| 1 | 5 | 4 | 3 |
| 2 | 10 | 9 | 8 |
| 4 | 21 | 20 | 18 |

Los otros tres límites quedan en los valores que el guion de puntuación aplica cuando el envío no los
cambia (HARNESS § 7.1): **100 llamadas a herramientas, 500 turnos y 300 s por comando**. Solo el tiempo se
deriva, porque es el único que el límite de 12 h restringe.

**Enmienda 2 (2026-10-04, sección I.4).** Esos tres límites pasan a **40 llamadas a herramientas, 100
turnos y 60 s por comando**, y `max_time_minutes` queda fijado en **4** como valor de A. La fórmula de
esta sección se conserva como comprobación: si el piloto muestra que 4 minutos no caben en las 12 horas
con el montaje medido, se corrige con otra enmienda antes de cualquier réplica.

**Diferencia con el kit.** El `eval_config.yaml` del kit trae valores de ejemplo mucho menores en los
cuatro límites (HARNESS § 7.1). Antes de la Enmienda 2, la línea base cambiaba ese archivo y nada más.
Desde la Enmienda 2, A es el zip enviado (sección I.4): no es «el kit con un solo archivo cambiado».

**Cómo se pasa.** El presupuesto queda en `conditions/a_linea_base/eval_config.yaml`, un archivo propio
que se versiona. `comprobar` no interpreta ese YAML: exige que sus bytes sean exactamente los que genera
desde la fórmula. El directorio del envío es una copia del kit verificado más ese archivo; el armado está
en su [README][armado]. `.gitignore` excluye las copias del kit y `scripts/verify_no_competition_data.py`
da alerta si se versiona ahí cualquier otro archivo.

[armado]: ../../experiments/gemma_developer_agent/conditions/a_linea_base/README.md

La CLI local `swegemma eval` 0.2.7 **no lee** `eval_config.yaml` (HARNESS § 7.1 atribuye esa lectura al
guion de puntuación de Kaggle, que no viene en el paquete), así que los mismos cuatro valores se pasan
además por opciones:

```bash
swegemma eval --tasks <tasks.jsonl> --snapshots-dir <snapshots> --results-dir <directorio nuevo> \
  --submission-dir experiments/gemma_developer_agent/conditions/a_linea_base \
  --sandbox <backend declarado> --image <imagen declarada> --task-ids <lista test del subconjunto> \
  --concurrency <c> --max-time-minutes 4 --max-tool-calls 40 --max-turns 100 --timeout-seconds 60 \
  --display quiet
```

Dos consecuencias que se declaran. Ningún recibo prueba qué presupuesto se aplicó, así que cada corrida
deja además el registro de F.1. Y el prompt no es idéntico al del envío real: la CLI recibe el tiempo como
número con decimales y el prompt lo muestra como `4.0`, mientras que un entero leído del YAML se mostraría
como `4`; omitir una de las cuatro opciones quitaría su línea del prompt, por eso se pasan las cuatro.

### D.2 Piloto

Una corrida corta en el notebook L4×4, **que no cuenta como réplica** y cuyos resultados por tarea no se
reportan ni se usan para decidir nada salvo lo que sigue. Usa solo tareas **válidas de entrenamiento** del
subconjunto ya commiteado: las dos primeras por `instance_id` de cada repositorio de entrenamiento y las
dos de enunciado más largo (longitud en caracteres; empates por `instance_id`). Como mucho 8 tareas, con
`--max-time-minutes 5`.

Deja un registro versionado (`preregistro/piloto_v1.json`, esquema `kaggle-pilot/1`) con:

- **c.** La concurrencia del envío real es del guion de puntuación de Kaggle, no del participante: el
  `eval_config.yaml` no tiene esa clave (HARNESS § 7.1). Solo vale como fuente una **página oficial de la
  competencia** o una **respuesta de los organizadores**, citada. Un notebook de otro competidor no es
  fuente. **Sin fuente, c = 1.** Las réplicas usan `--concurrency c`.
- **m.** Segundos desde que arranca el servidor del modelo hasta que responde; se usa en minutos,
  redondeados hacia arriba.
- La comprobación de que la sección de presupuesto del prompt, en la traza de una tarea (HARNESS § 5.2 y
  § 9.2), muestra los cuatro valores pasados.
- El piloto es la primera corrida con el directorio `conditions/a_linea_base/`, que lleva un
  `README.md` propio: si el arnés no compila el envío con ese archivo dentro, el piloto es degenerado y
  el README se saca del directorio por enmienda.

**s** no sale del piloto: es la media de la duración de la verificación sin parche de las tareas
`discrimina`, tomada del archivo de validez y redondeada hacia arriba a 0,1 min. Es una **aproximación**
del montaje: una verificación monta el sandbox y además ejecuta las pruebas, pero no es la misma operación
que el montaje del contenedor del agente y no se afirma que sea una cota.

`comprobar` lee `c` y `m` del registro del piloto y `s` del archivo de validez, y calcula `b`; no acepta
un valor tecleado.

**Tope y piloto degenerado.** Como mucho **2** pilotos. Un piloto es degenerado si el servidor no arranca,
si todas sus tareas terminan en error de infraestructura o si el prompt no muestra el presupuesto pasado.
Un piloto degenerado se repite una vez; si el segundo también lo es, `comprobar` sale con 2 (decisión
`piloto_degenerado`).

## E. Cómputo y regla de reducción

### E.1 Fórmula y calendario

Una corrida de `n` tareas con presupuesto `b` y concurrencia `c` ocupa como mucho

```text
horas ≤ ( m + n · (s + b + v) / c ) / 60          v = minutos de verificación por tarea
```

Por la fórmula de D.1, `(s + b) / c ≤ T · (1 − r) / N = 5,4 min` para cualquier `c`. La parte del agente y
el montaje cuesta entonces como mucho **5,4 min de L4×4 por tarea**. La carga del modelo por sesión y la
verificación se suman aparte.

Horas utilizables: **`0,8 · (Q / f) · W`**.

- `Q` es la cuota semanal de GPU de la cuenta y `f` el factor de consumo de L4×4. `f` se **relee el mismo
  día que `Q`**, porque la página avisa de que puede subir de 2.
- Una «semana» es un periodo de cuota de Kaggle. `W` es el número de **reinicios de cuota** entre una
  fecha de inicio y el corte, los dos inclusive; el dueño lee en Kaggle qué día de la semana se reinicia.
- La fecha de inicio para elegir el subconjunto (C4) es la **fecha mínima de compuerta, 2026-10-12**,
  escrita aquí antes de leer la cuota. La cuota que quede del periodo en curso no se cuenta.
- 0,8 es una elección convencional: el 20 % restante es para la carga del modelo, la verificación, el
  ensayo y el piloto, que la cota de 5,4 min no incluye.

Calendario inverso desde el cierre del Paper Track:

| Fecha | Hito |
|---|---|
| 2026-11-12 | Cierre del Paper Track: envío del writeup |
| 2026-11-10 y 11 | Los tres revisores de texto público y correcciones |
| 2026-11-07 a 09 | Manuscrito |
| 2026-11-06 | Análisis, verificación independiente y lectura de la campaña |
| **2026-11-05** | **Corte**: último recibo de la campaña #104 |
| 2026-10-23 | Análisis y lectura de la línea base (C7) |
| **2026-10-22** | **Límite de recibos de la línea base (C6)**: deja dos semanas a la campaña |
| **2026-10-19** | **Límite de la compuerta (C5)**: deja tres días para las réplicas |
| 2026-10-12 | Fecha mínima de compuerta |

Si la compuerta se abre después del 2026-10-19, la campaña ya no tiene sus dos semanas: el dueño elige
entre `seguir_solo_linea_base` y `detener` (decisión `compuerta_tardia`). Después del 2026-10-22 la
compuerta no se abre.

### E.2 Escalera

Para que la línea base no deje a la campaña sin cómputo, cada escalón suma:

- las réplicas de A **más 2 réplicas extra**, el tope de repeticiones por infraestructura (sección F.3);
- una **campaña de referencia para el cálculo**: un pase de A sobre las tareas de entrenamiento (los
  episodios de C) y dos condiciones nuevas, B y C, sobre las tareas de prueba, con A reutilizada de la
  línea base. No es un compromiso de #104, que fija su propio diseño.

Con todas las tareas válidas (`python -m scripts.kaggle_prereg computo --validas fastapi/fastapi=67
Textualize/rich=48 psf/requests=13 encode/httpx=1`) y f = 2:

| Escalón | Reservado | Réplicas de A | Corridas por condición nueva | Corridas de tarea | Horas L4×4 | Horas de cuota |
|---|---|---|---|---|---|---|
| 1 | fastapi | 3 | 2 | 665 | 59,85 | 119,70 |
| 2 | fastapi | 2 | 2 | 598 | 53,82 | 107,64 |
| 3 | rich | 3 | 2 | 513 | 46,17 | 92,34 |
| 4 | rich | 2 | 2 | 465 | 41,85 | 83,70 |
| 5 | fastapi | 2 | 1 | 464 | 41,76 | 83,52 |
| 6 | rich | 2 | 1 | 369 | 33,21 | 66,42 |
| 7 | fastapi | 2 | sin campaña | 268 | 24,12 | 48,24 |
| 8 | rich | 2 | sin campaña | 192 | 17,28 | 34,56 |

**Regla.** Se elige el primer escalón, en este orden, cuyo repositorio sea apto (sección B) y cuyas horas
quepan en las horas utilizables. Los números se recalculan con las tareas válidas medidas.

El orden dice qué se reduce primero. Dentro de cada nivel de campaña (2 corridas por condición, 1, o
ninguna) fastapi va antes que rich. Antes de bajar de 2 corridas por condición a 1 se cambia de fastapi a
rich: la regla G2 puede exigir 2 corridas por condición, y una campaña que no puede darlas no sirve en
ese caso. Así, de mayor a menor cómputo: se quita la tercera réplica de A (escalones 1 → 2 y 3 → 4); se
pasa de fastapi a rich (2 → 3); se baja a una corrida por condición, primero con fastapi (5) y después
con rich (6); se renuncia a la campaña, primero con fastapi (7) y después con rich (8).

Con los escalones 7 u 8 la línea base se mide y la campaña no cabe: el dueño elige entre
`seguir_solo_linea_base` y `detener` (decisión `campana_no_cabe`). Si no cabe ni el escalón 8,
`comprobar` sale con 2 (decisión `sin_escalon`).

**Dos momentos.** En C4, con `W` contado desde el 2026-10-12, la escalera fija el **repositorio**. En C5,
con `W` contado desde la fecha real de la compuerta, se recalcula solo entre los escalones de ese
repositorio y fija las **réplicas de A**. Las dos veces por la misma regla y sin ningún dato de
resultados.

**Lo que nunca se reduce:** el presupuesto por tarea (cambiarlo cambia el prompt y lo que se mide), el
mínimo de 2 réplicas y las tareas del subconjunto una vez commiteado.

Lo que cuesta además lo que la referencia no incluye: la condición D con dos corridas, 12,06 h (fastapi) u
8,64 h (rich); cada pase adicional sobre el entrenamiento, 5,58 h u 7,29 h. Son cotas de la misma fórmula.

## F. Qué se reporta y con qué comando

### F.1 Recibos y registro de cada corrida

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

Cada recibo lleva `run_utc`, **obligatorio**: `convertir` lo toma de la fecha de modificación del
`task_results.jsonl` del arnés, no de una opción tecleada, y rechaza una conversión anterior a la corrida.
Esa fecha no es una firma: se puede alterar al copiar el archivo. Por eso se anota además la versión del
notebook de Kaggle, que tiene fecha del servidor.

Junto a los recibos de cada réplica se versiona `replica_<k>.corrida.json` con: el comando exacto de
`swegemma eval`, la versión del notebook, los cuatro valores de presupuesto leídos de la sección de
presupuesto del prompt en la traza de la primera tarea, y el SHA-256 de esa sección. Es lo único que
prueba qué presupuesto se aplicó.

Los recibos se commitean **antes** de analizar. Después:

```bash
python -m scripts.kaggle_replicas analizar --recibos evidence/kaggle-baseline-a-v1 \
  --descartadas evidence/kaggle-baseline-a-v1/descartadas \
  --subconjunto experiments/gemma_developer_agent/preregistro/subconjunto_linea_base_a.json \
  --envio experiments/gemma_developer_agent/conditions/a_linea_base \
  --salida-json results/kaggle-baseline-a-v1/analisis.json \
  --salida-md results/kaggle-baseline-a-v1/analisis.md

python -m scripts.kaggle_eda terciles --tasks experiments/gemma_developer_agent/data/tasks.jsonl \
  --recibos evidence/kaggle-baseline-a-v1 \
  --parametros experiments/gemma_developer_agent/preregistro/linea_base_a.json
```

`--recibos <directorio>` lee solo los `.jsonl` de ese directorio, no los de `descartadas/`. La opción
`--descartadas` se omite si no hay ninguna réplica descartada. α = 0,05, el valor por defecto. Las salidas
se publican sin editar y la lectura va en `docs/results/kaggle-baseline-a.md`.

### F.2 Qué se reporta

- **Tasa principal por réplica: resueltas / tareas del subconjunto**, con numerador y denominador. Un
  fallo del agente cuenta como no resuelta: parche vacío, timeout, presupuesto agotado, parche que no
  aplica, pruebas que fallan, se cuelgan o mueren con el parche aplicado, o una petición rechazada por
  exceder el contexto. La tasa sobre válidas es secundaria. Las tasas de las réplicas no se promedian en
  una sola cifra de cabecera.
- No resueltas por motivo, por réplica.
- **Tareas que cambian de resultado**: numerador, denominador y lista.
- Por cada par de réplicas: tabla 2×2, acuerdo, discordancia con su intervalo y p de McNemar exacto.
- Tabla por tarea, desglose por repositorio, diferencia mínima significativa y suelo.
- Réplicas descartadas y tareas con infraestructura repetida (F.3).
- Descriptivo: tasa por terciles (sección «Datos»); llamadas a herramientas y duración por tarea.

### F.3 Corrida válida, infraestructura y códigos de salida

**Qué es infraestructura.** Solo los errores del arnés de la lista cerrada de
`scripts/kaggle_replicas.py` (snapshot ausente, error de ejecución del sandbox que no sea un rechazo por
contexto, error de evaluación, fallo del worker, pruebas sin especificación, `test_patch` que no aplica) y
el código −1 del paso de pruebas. Los códigos 124 y 137 del paso de pruebas, con el parche del agente
aplicado sobre una tarea `discrimina`, cuentan como **no resuelta**: el parche puede causarlos.

**Repetición.** Si una réplica tiene algún error de infraestructura, se **repite entera** con el número
de réplica siguiente, y el archivo de sus recibos se mueve sin editar a
`evidence/kaggle-baseline-a-v1/descartadas/`. Si a una réplica solo le faltan recibos (la corrida se
cortó), no se descarta: se corren las tareas que faltan y se convierten a otro archivo con el mismo número
de réplica.

**Qué comprueba el análisis**, y sale con 2 si no se cumple:

- los números de réplica de vigentes y descartadas, juntos, son 1, 2, …, k **sin huecos**: una réplica
  borrada en vez de movida deja un hueco;
- cada réplica descartada tiene recibo de **todas** las tareas del subconjunto y **al menos un**
  `infra_error`: una réplica no se descarta por su tasa, ni se le quitan recibos;
- hay como mucho **2** descartadas (el tope de réplicas extra, ya cargado al cómputo de la escalera);
- ningún número de réplica es a la vez vigente y descartado, no hay recibos duplicados ni tareas ajenas al
  subconjunto, y los hashes, la versión del arnés y la imagen de las descartadas son los de las vigentes.

**Qué no puede comprobar** y solo protege el historial de git: que no se haya borrado la réplica de número
más alto, ni renumerado réplicas antes de commitear. Por eso los recibos de cada réplica se commitean al
terminar esa réplica y antes de correr la siguiente.

**Tope por tarea.** Si la misma tarea cae en infraestructura en **2 réplicas**, contando las descartadas,
deja de repetirse; cuenta como no resuelta (motivo `infra_repetida`) y el reporte la lista. Así una tarea
que rompe siempre el sandbox no impide terminar.

| Salida de `analizar` | Qué significa | Qué se hace |
|---|---|---|
| 0 | Todas las tareas del subconjunto tienen resultado en todas las réplicas vigentes | **Corrida válida.** Solo sobre este reporte se leen las reglas de la sección G |
| 1 | Faltan tareas o hay errores de infraestructura sin repetir | No es una corrida válida. Se descarta y se repite la réplica afectada, dentro del tope. El reporte con salida 1 se conserva y se menciona en la lectura |
| 2 | Recibos ilegibles, incoherentes, mezclados o fuera del subconjunto; descartes inválidos o por encima del tope | No hay reporte. No se edita ningún recibo: se corrige el código o la conversión; si el defecto está en los recibos, se publica una campaña nueva en otro directorio |
| 3 | Error del propio script | Se corrige el script por enmienda (sección I.4), en un PR revisado, y se analiza otra vez sobre los mismos recibos |

Si se agota el tope sin 2 réplicas completas, la línea base no llegó a salida 0: la lectura publica el
reporte con salida 1, no aplica ninguna regla de la sección G y la campaña no empieza hasta arreglar la
causa.

## G. Reglas de decisión hacia #104

Se leen del reporte con salida 0. Notación, con los nombres del JSON:

- `n`: tareas del subconjunto.
- `S = 6 / n`: `margen.suelo.diferencia_tasa`.
- `M`: `margen.diferencia_minima_significativa`. Es nulo cuando ni el límite superior de la discordancia
  llega a 6 pares; entonces manda el suelo. Se usa **`M* = max(S, M)`**, y las comparaciones se hacen con
  enteros: con `p` pares de diferencia mínima, `p · 40 ≤ 6 · n` y `p · 24 > 6 · n`, no con tasas
  redondeadas.
- `L`: el menor número de resueltas entre las réplicas. `U`: el menor número de no resueltas.

**Precedencia.** Las reglas se aplican todas. Si alguna impide la campaña (G2 «ruido dominante», G3
«techo»), la campaña confirmatoria no se corre, aunque las demás la permitan.

**G1 · A–A discrepa.** Si algún par de réplicas tiene `mcnemar_p_exacto ≤ 0,05`, se publica como «A–A
discrepa», con el par y su tabla. **No se interpreta causalmente**: puede ser azar o puede ser que algo
cambió entre sesiones, y los recibos no lo distinguen. No se descarta ninguna réplica por su p, no se
añaden réplicas fuera del tope de F.3 y se pasa a G2 con el `M*` del peor par, como siempre. Tasa de falsa
alarma: cada par salta por azar como mucho un 5 % de las veces; con 3 réplicas hay 3 pares, así que el
estudio da al menos una alarma falsa como mucho un 15 % de las veces (≈ 14 % si los pares fueran
independientes, que no lo son).

**G2 · Ruido.** Los dos umbrales, 6/40 y 6/24, son elecciones convencionales: son las resoluciones que
habrían tenido sin ruido las particiones de 40 y de 24 tareas que ofrece `scripts/kaggle_split.py`. No
salen de un cálculo de potencia ni de un tamaño de efecto esperado.

| Caso | Condición | Qué necesita la campaña | Qué se afirma |
|---|---|---|---|
| Ruido bajo | `M* ≤ 6/40` | Las mismas `n` tareas; basta **1 corrida por condición**, 2 si el cómputo alcanza | «Con una corrida por condición, la prueba declararía significativa una diferencia de `M*` o más» |
| Ruido intermedio | `6/40 < M* ≤ 6/24` | Las mismas `n` tareas y **al menos 2 corridas por condición**; el pre-registro de #104 define el análisis sobre corridas repetidas | Con una sola corrida solo se declararía significativa una diferencia de `M*` o más |
| Ruido dominante | `M* > 6/24` | La campaña no se corre como confirmatoria | «Con este kit, este presupuesto y `n` tareas, repetir A cambia el resultado de x de `n` tareas, y una diferencia entre condiciones menor que `M*` no se declararía significativa frente a repetir A». Es un resultado y se publica como tal. Una campaña descriptiva, sin veredictos de apoyada o refutada, queda a decisión del dueño |

En los tres casos, la campaña no declara una diferencia menor que `M*`. `M*` es un umbral de
significación, no de potencia: un efecto real de ese tamaño se declararía significativo más o menos la
mitad de las veces.

Cuántos pares discordantes observados en el peor par admite cada caso (`python -m scripts.kaggle_prereg
ruido --tareas 40 48 67`):

| Tareas | Suelo | «Ruido bajo» hasta | «Ruido intermedio» hasta |
|---|---|---|---|
| 40 | 6/40 | 1 discordante | 11 |
| 48 | 6/48 | 2 discordantes | 18 |
| 67 | 6/67 | 10 discordantes | 44 |

Con rich (48 tareas o menos) el caso «ruido bajo» es casi inalcanzable: basta que 3 tareas cambien entre
dos réplicas para salir de él. Con rich, lo esperable es que la campaña necesite 2 corridas por
condición.

**G3 · Suelo y techo.** Para que la prueba declare que una condición gana a A hacen falta 6 tareas que A
no resuelva; para que declare que pierde, 6 que A sí resuelva.

| Caso | Condición | Consecuencia |
|---|---|---|
| Margen en los dos sentidos | `U ≥ 6` y `L ≥ 6` | La campaña puede declarar mejora o daño |
| Suelo | `L < 6` | La campaña puede declarar mejora, pero no daño: «refutada por empeorar» queda fuera de alcance y se dice así. La lectura reporta los motivos de las no resueltas; si en todas las réplicas **más de la mitad** de las no resueltas son por timeout o presupuesto agotado, se dice que el límite de 12 h domina, y **el presupuesto no se cambia** |
| Techo | `U < 6` | La campaña no puede declarar mejora sobre este subconjunto: no se corre para ese fin. Se reporta «A resuelve casi todas» y se anota la contaminación como explicación posible, sin concluirla |
| Las dos | `U < 6` y `L < 6` | Solo ocurre si una réplica resuelve casi todo y otra casi nada: se publica como G1 y la campaña no se corre |

**G4 · N y selección.** La campaña usa las mismas `n` tareas del subconjunto. No se quitan las tareas
inestables ni se elige un subconjunto después de ver cuáles cambian: sería seleccionar por resultado.
Cambiar de tareas exige un subconjunto nuevo y una línea base nueva.

**G5 · El brazo A de la campaña.** Son **todas** las réplicas completas de la línea base, no una elegida.
Cómo se resumen varias corridas de una condición (el estimador) lo fija el pre-registro de #104 antes de
ver ningún episodio de entrenamiento. Las réplicas valen como brazo A solo si los recibos de las otras
condiciones tienen el mismo `subset_sha256`, `tasks_sha256`, versión del arnés, entorno, presupuesto y
concurrencia. Si algo difiere, A se corre de nuevo.

**G6 · Si el cómputo no alcanza para lo que pide G2.** Se reduce primero la condición D, que #104 ya
condiciona al cómputo, y después las corridas por condición hasta el mínimo de G2. Si ni así cabe, lo
decide #104 en su pre-registro antes de sus datos.

## Predicciones (antes de cualquier corrida)

Del autor, que no ha visto ninguna corrida del modelo. Cada una dice qué la refutaría.

- **P1.** Habrá tareas que cambian de resultado entre réplicas: la temperatura es mayor que cero, no hay
  semilla y el límite es de tiempo de reloj. La refuta un 0 en «tareas que cambian».
- **P2.** En todas las réplicas, más de la mitad de las no resueltas serán por timeout del agente o
  presupuesto agotado. La refuta cualquier réplica donde no lo sean.
- **P3.** La tasa principal de A quedará por debajo de la mitad en todas las réplicas, porque el
  presupuesto es mucho menor que el valor por defecto del arnés. La refuta una réplica con la mitad o
  más de las tareas resueltas.
- **P4.** Sin predicción sobre el caso de G2.

## H. Desviaciones declaradas y amenazas a la validez

**Respecto del kit.**

- `eval_config.yaml`: los cuatro límites cambian (sección D).
- `max_output_tokens`: solo si el ensayo muestra rechazos con 16 384 (A.0).
- El directorio del envío lleva además un `README.md` propio, que ningún archivo del envío incluye.
- Nada más: prompts, herramientas, subagente, adaptadores y muestreo son los del kit.

**Respecto de la evaluación real.**

| Aspecto | Evaluación de Kaggle | Esta línea base |
|---|---|---|
| Tareas | Unas 120 de repositorios privados | Las válidas de un repositorio público y popular |
| Guion | El de puntuación de la competencia | La CLI `swegemma eval`, que no lee `eval_config.yaml` |
| Contexto | El guion de puntuación compacta los eventos y cachea el contexto (HARNESS § 7.2) | La CLI deja las dos configuraciones sin poner: **ni compacta ni cachea** |
| Máquina | La de puntuación, con 4 × L4 | Un notebook de Kaggle con L4×4 y un servidor arrancado por nosotros con los parámetros de HARNESS § 3.1 |
| Sandbox | Contenedores Docker (HARNESS § 4.1) | El backend que permita el notebook, fijado en el ensayo |
| Presupuesto | El que ponga cada participante | El mayor que cabe en 12 h en el caso peor; el prompt lo muestra con decimales |
| Concurrencia | La del guion de puntuación | La misma si hay fuente oficial; si no, 1 |

Las tasas de esta línea base **no predicen** el puntaje de la tabla de posiciones.

**Amenazas.**

- **Sin compactación de contexto.** Con una ventana de 32 768 tokens y sin compactar, una sesión larga
  puede llenar el contexto antes que en el envío real. Los rechazos resultantes cuentan como no resuelta:
  la línea base puede **subestimar** a A por una diferencia del guion, no del agente. El ensayo cuenta los
  rechazos; el reporte los separa con el motivo `context_exceeded`.
- **Repositorio, fecha y tamaño van juntos.** Reservar fastapi es reservar las tareas recientes, las de
  enunciado más largo y las de parche más grande (sección «Datos»). Ningún resultado sobre el subconjunto
  separa esos factores.
- **Contaminación.** El modelo pudo ver los repositorios y los arreglos. La comparación entre condiciones
  es pareada sobre las mismas tareas, pero la contaminación puede acercar A al techo y reducir el margen.
- **Un solo repositorio de prueba.** Lo que se mida vale para ese repositorio. No se separa «repositorio
  no visto» de «dominio distinto».
- **Tareas fijas, no muestreadas.** Los intervalos y la diferencia mínima describen estas tareas; no se
  generaliza a otras. Tres réplicas dan tres pares que comparten tareas y no son independientes.
- **El tiempo es de reloj.** La carga de la máquina cambia cuánto alcanza a hacer el agente en `b`
  minutos; es parte del ruido que se mide y también de lo que no se controla.
- **Pruebas colgadas.** Un timeout o un proceso matado en las pruebas cuenta como fallo del agente. Si la
  causa fuera el sandbox y no el parche, A quedaría subestimada. La lectura lista esas tareas.
- **Repetir réplicas enteras.** Una réplica repetida vuelve a muestrear todas sus tareas, no solo la que
  falló, y quien repite ya conoce la tasa de la descartada. El análisis comprueba que cada descartada
  esté completa y tenga un error de infraestructura, y que no falte ningún número de réplica (F.3). No
  puede comprobar que no se borró la última réplica ni que no se renumeró antes de commitear: eso solo
  lo protege el historial de git.
- **Marcador del rechazo por contexto.** Los dos marcadores son un supuesto hasta el ensayo, y se buscan
  en cualquier punto del texto del error del sandbox. Un fallo real de infraestructura cuyo mensaje
  contuviera una de esas frases se contaría como fallo del agente y no se repetiría. El ensayo fija el
  texto exacto del rechazo y la lista se ajusta por enmienda antes del primer recibo.
- **Fechas declaradas.** La fecha de la compuerta y las de los registros (ensayo, validez, lectura de
  la cuota, piloto) son valores declarados, no firmados. `comprobar` exige que no retrocedan de un paso
  al siguiente, que no sean anteriores al registro (2026-10-03) ni posteriores al corte, y que la
  compuerta no sea anterior al 2026-10-12. Quien revisa las contrasta además con la fecha de los
  commits C0.5 a C5 y con la versión de cada notebook, que tiene fecha del servidor de Kaggle.
- **Supuesto de concurrencia.** Si `c` real es mayor que 1 y no se logra una fuente oficial, el
  presupuesto queda más corto que el que un participante podría usar, y la línea base subestima a A.
- **Caso peor.** El presupuesto supone que todas las tareas agotan su tiempo. Un participante puede
  apostar a un tope mayor.
- **Entorno arreglado a mano.** Cada rueda añadida aleja el sandbox del distribuido. Queda declarada en
  A.1, pero la validez medida es la de ese entorno.
- **Fecha de la corrida.** `run_utc` sale de la fecha de un archivo, que se puede alterar.
- **Convenciones.** r = 0,10, la fracción 0,8, los umbrales 6/40 y 6/24, el mínimo de 40 tareas, los 5
  turnos de viabilidad y «más de la mitad» se eligieron sin datos de Gemma, conociendo los agregados de
  la sección «Datos». Son convenciones, no resultados de un cálculo.

## I. Orden de commits, parámetros abiertos, decisiones y enmiendas

### I.1 Orden de commits

| Commit | Contenido | Condición | Límite |
|---|---|---|---|
| **C0** | Este documento, `linea_base_a.json`, `scripts/kaggle_prereg.py`, `scripts/kaggle_eda.py`, los cambios de `scripts/kaggle_replicas.py` y sus tests | Mergeado en `main` | — |
| **C0.5** | Registro del ensayo de notebook; cierra `ensayo_notebook` | C0 | — |
| **C1** | `scripts/kaggle_validez.py` con tests sintéticos, sin datos | Revisado y mergeado | — |
| **C2** | Declaración del entorno y `validez_tareas_v1.json`; cierra `entorno_sandbox` y `validez_tareas` | C0.5, C1 y la repetición del orquestador | — |
| **C3** | Cierra `cuota` | Lectura del dueño | — |
| **C4** | `subconjunto_linea_base_a.json`; cierra `subconjunto` | C2 y C3 | — |
| **C5** | Registro del piloto y `eval_config.yaml`; cierra `piloto`, `presupuesto`, `corrida` y `decisiones_dueno` | C4 | 2026-10-19 |
| **Compuerta** | `comprobar --tasks <tasks.jsonl> --envio <directorio>` sale con **0** sobre un commit de `main` | Antes de la primera réplica | 2026-10-19 |
| **C6** | Recibos y registro de cada réplica en `evidence/kaggle-baseline-a-v1/` | Después de la compuerta; antes de analizar | 2026-10-22 |
| **C7** | Salidas del análisis y lectura en `docs/results/kaggle-baseline-a.md` | Verificación independiente | 2026-10-23 |

Qué comprueba la compuerta sobre git: que el archivo de parámetros y cada archivo que cita estén
commiteados y sin cambios locales, y que `HEAD` esté contenido en `origin/main`. Usa la referencia
**local** de `origin/main` y no consulta la red: quien abre la compuerta hace antes `git fetch`. No
comprueba firmas ni que el commit sea el último de `main`.

Cómo se verifica: el orden de los commits en `main`; el resumen del bloque `fijos`; `run_utc` de cada
recibo posterior a la fecha del commit C5; los hashes de los recibos iguales a los declarados en C4 y C5;
y `git diff <E> C6 -- docs/preregistration/kaggle-baseline-a.md scripts/kaggle_replicas.py
scripts/kaggle_split.py scripts/kaggle_eda.py` vacío, donde `<E>` es el commit de la última enmienda
anterior a C5, o C0 si no hay ninguna. De C0.5 a C5, cada commit solo rellena `valor` en
`linea_base_a.json` y añade los archivos que cita.

### I.2 Parámetros abiertos

`comprobar` sale con **1** mientras quede alguno o falte una comprobación (sin `--tasks`, sin `--envio` o
con `--sin-git`), y con **2** si un valor cerrado contradice su regla. No acepta valores tecleados donde
puede derivarlos: lee los registros, comprueba su hash y su esquema, deriva el presupuesto, el
repositorio, las réplicas, las partes y `max_output_tokens`, regenera la partición, cruza los
identificadores de la validez con `tasks.jsonl`, recalcula el hash del envío, exige que el archivo de
muestreo del envío sea el del kit con el `max_output_tokens` que fijó el ensayo, que las fechas
declaradas estén en orden y que cada archivo citado esté commiteado, con una ruta relativa dentro del
repositorio y sin citar un mismo archivo en dos papeles.

| Parámetro | Regla | Quién lo cierra | Commit |
|---|---|---|---|
| `ensayo_notebook` | A.0 | Quien ejecute el ensayo en Kaggle; revisa el orquestador | C0.5 |
| `entorno_sandbox` | A.1 | El implementador del paso de validez; revisa el orquestador | C2 |
| `validez_tareas` | A.2 a A.4 | El implementador del paso de validez; el orquestador repite una muestra | C2 |
| `cuota` | E.1: `Q`, `f`, día de reinicio, fuente y fecha de lectura | El dueño la lee en Kaggle (#101); el orquestador la versiona | C3 |
| `subconjunto` | B y E.2 | El orquestador | C4 |
| `piloto` | D.2 | Quien ejecute el piloto; revisa el orquestador | C5 |
| `presupuesto` | D.1: `eval_config.yaml` canónico y hash del envío | El orquestador | C5 |
| `corrida` | C y E.2: fecha de la compuerta, réplicas y partes | El orquestador | C5 |
| `decisiones_dueno` | I.3 | El dueño decide; el orquestador versiona | C5 como tarde |

### I.3 Decisiones del dueño

Toda decisión del dueño que este diseño prevé tiene sus opciones escritas aquí y se **versiona** en
`decisiones_dueno` (decisión, opción, fecha y referencia): un comentario de GitHub no basta, porque la
compuerta no lo ve. `comprobar` exige la decisión cuando su condición se da, la rechaza cuando no se da, y
solo se abre con una opción que permite seguir.

| Decisión | Cuándo | Opciones |
|---|---|---|
| `entorno_sin_arreglo` | La guarda de A.3 sigue saltando tras la segunda medición | `seguir_excluyendo` · `detener` |
| `campana_no_cabe` | La escalera da un escalón sin campaña | `seguir_solo_linea_base` · `detener` |
| `compuerta_tardia` | La compuerta se abre después del 2026-10-19 | `seguir_solo_linea_base` · `detener` |
| `ensayo_no_viable` | El ensayo de notebook no es viable | `enmienda_v2` · `detener` |
| `rechazos_con_todos_los_candidatos` | Hay rechazos por contexto también con 8 192 | `enmienda_v2` · `detener` |
| `sin_escalon` | Ningún escalón apto cabe, o ningún repositorio es apto | `enmienda_v2` · `detener` |
| `presupuesto_bajo_minimo` | La fórmula da menos de 2 minutos | `enmienda_v2` · `detener` |
| `piloto_degenerado` | Dos pilotos degenerados | `enmienda_v2` · `detener` |

Con `detener` o `enmienda_v2` la compuerta de este diseño no se abre. `enmienda_v2` significa una línea
base nueva, con su propia sección de enmienda, antes de cualquier recibo.

### I.4 Enmiendas

Después del merge de C0, este documento, los valores `fijos` y los scripts de análisis solo cambian por
una enmienda: un commit propio, anterior al primer recibo al que afecta, con su fila aquí y su entrada en
`enmiendas` de `linea_base_a.json`, y con el resumen de `fijos` actualizado en el documento y en
`scripts/kaggle_prereg.py` si cambia. Una enmienda posterior al primer recibo se reporta como desviación.

| Fecha | Motivo | Commit |
|---|---|---|
| 2026-10-03 | **Enmienda 1.** Registro del ensayo de notebook (A.0): medidas ausentes cuando el servidor no arranca o el kit no compila; lista de turnos de la repetición con 8 192 y viabilidad juzgada con la lista del `max_output_tokens` que queda fijado; `informe_sha256`; y la duración de sesión se declara con su fuente. Cambia el esquema `kaggle-notebook-trial/1` en `scripts/kaggle_prereg.py`; no cambia ningún valor de `fijos` ni su resumen. Anterior a cualquier recibo y a C0.5 | PR #119 (commit de squash en `main`) |
| 2026-10-04 | **Enmienda 2.** La condición A pasa a ser el kit ajustado. A deja de ser «el kit oficial con un solo archivo cambiado» y es el zip enviado el 2026-10-03 (envío 56808559, SHA-256 `d8a3e1d3558f03b72b3f86037ff53b462a8f66566e1bb7907240bcb0ce4d7182`), con cuatro cambios sobre el kit: (1) sin adaptadores: los del kit tienen pesos en cero y reducían el contexto de vLLM (foro, hilo 744794); (2) `max_output_tokens` 8192: con 16 384, vLLM rechaza prompts de más de 16 384 tokens (notebook público de Dariush Afshar); (3) `include_thoughts: false`: se imita una configuración pública que puntúa (notebook de Roman Rozen), sin evidencia propia de que ayude; (4) 4 minutos, 40 llamadas, 100 turnos y 60 s por comando: el kit trae 1 minuto y 10 llamadas, la puntuación es secuencial y pasar de 12 h anula el envío (hilos 743063 y 743964). **Por qué:** el kit sin cambios dio error sin nota en septiembre (hilos 743213 y 744807), así que la A original no es ejecutable. **Sección D:** los 4 minutos quedan fijados como valor de A y la fórmula se conserva como comprobación; si el piloto muestra que no caben en las 12 horas con el montaje medido, se corrige con otra enmienda antes de cualquier réplica. **A.0:** el ensayo de notebook corre con la A redefinida. **Cambia `fijos`:** `max_tool_calls` 100 → 40, `max_turns` 500 → 100, `timeout_seconds` 300 → 60, y su resumen. **No cambia:** la partición, el número de réplicas, las reglas de decisión ni la frontera de fuga. **Lo que se sabía:** el zip ya estaba enviado y su nota no se conocía (estado pendiente); los valores del presupuesto se eligieron sin regla previa. Anterior a cualquier réplica | Rama `issue-106-envio-code-track` (commit de esta enmienda) |
| 2026-10-04 | **Enmienda 3 (aclaración; no cambia `fijos`).** El cambio (3) de la Enmienda 2, `include_thoughts: false`, **desactiva el razonamiento del modelo**; no se limita a no devolverlo. Con ese valor el arnés envía `chat_template_kwargs.enable_thinking = false` y no envía presupuesto de razonamiento, así que `thinking_budget: 4096` queda sin efecto, también en el subagente. Se comprobó capturando la petición con `scripts/kaggle_simulacro.py` ([ficha](../../experiments/gemma_developer_agent/docs/simulacro_sin_gpu.md)): el kit original envía `enable_thinking = true` y un presupuesto de 4 096. La condición A sigue siendo el zip de la Enmienda 2, sin razonamiento. **Lo que se sabía:** la primera nota de ese zip (0,06, envío 56808559) ya se conocía; por eso esta enmienda no cambia ningún valor y no elige configuración a partir de esa nota. Si se quiere medir A con razonamiento, es otra condición y exige otra enmienda antes de sus recibos. Anterior a cualquier réplica | Rama `datito/simulacro-sin-gpu` (commit de esta enmienda) |

## Fuera de alcance

Las condiciones B, C y D, las skills, los señuelos y los envíos a Kaggle (#104, #106). Este documento no
fija el diseño de la campaña: le deja medido el ruido de A, la partición y las reglas con que leerlo.
