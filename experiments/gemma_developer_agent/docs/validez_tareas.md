# Validez de las tareas: guion y registro (#103, commit C1)

`scripts/kaggle_validez.py` implementa las secciones A.2 a A.4 del
[pre-registro](../../../docs/preregistration/kaggle-baseline-a.md). Este documento dice cómo se usa y qué
queda versionado. No afirma ningún resultado: el guion está probado solo con verificadores sintéticos y
todavía no se ha medido ninguna tarea.

## Qué hace

Para cada tarea de `tasks.jsonl`, en orden de `instance_id`, corre cuatro rondas con una misma función de
verificación (sin parche, parche de referencia, sin parche, parche de referencia). Una ejecución de
infraestructura (error de la lista cerrada de `scripts/kaggle_replicas.py` o código −1 de las pruebas) se
repite una vez; 124 y 137 no son infraestructura. La clase sale de las ejecuciones finales, en este orden:
`no_medible`, `inestable`, `pasa_sin_parche`, `dorado_falla`, `discrimina`. Se excluye toda tarea que no sea
`discrimina`.

La guarda de A.3 se evalúa por repositorio: con 10 tareas o más y **más de la mitad** sin ser `discrimina`,
el guion escribe igualmente el registro (el archivo anterior se conserva) y sale con 1.

**Código de salida fuera de la lista.** Un resultado del arnés que la lista cerrada de A.3 no clasifica
(por ejemplo, un código 139 de las pruebas, o un texto de error nuevo) **aborta toda la medición con 2**,
nombrando la tarea y la ronda y sin guardar esa ejecución. No se clasifica a mano: hace falta una enmienda
del pre-registro (I.4) que amplíe la lista, y después se reanuda con el mismo comando.

## Comando

```bash
python -m scripts.kaggle_validez \
  --tasks experiments/gemma_developer_agent/data/tasks.jsonl \
  --snapshots-dir <directorio de snapshots> \
  --entorno experiments/gemma_developer_agent/preregistro/entorno_sandbox_v1.json \
  --imagen <imagen de la declaración> --sandbox <docker|subprocess> \
  --crudo experiments/gemma_developer_agent/data/validez_crudo_v1 \
  --params experiments/gemma_developer_agent/preregistro/linea_base_a.json \
  --salida experiments/gemma_developer_agent/calibracion/validez_tareas_v1.json
```

- `--entorno` es la declaración `kaggle-sandbox-env/1`; `--imagen` y `--sandbox` deben coincidir con ella.
  El guion necesita el paquete `swegemma` en el mismo intérprete, en la versión de la declaración; si no
  está, sale con 2 antes de crear nada.
- `--params` es **obligatorio con el arnés real**: exige que el SHA-256 de `tasks.jsonl` sea el registrado
  y de él sale `timeout_seconds`, que se pasa al arnés; si el arnés aplica otro, sale con 2.
- Antes de medir comprueba que existen los snapshots de **todas** las tareas elegidas, con la misma
  resolución que el arnés (el directorio dado y, si falta, `secret/sandbox/snapshots`); si faltan, sale con
  2 diciendo cuántos. Un snapshot ausente no es una propiedad de la tarea.
- `--crudo` recibe las salidas crudas y el estado de reanudación. Debe quedar fuera de un repositorio git o
  en una ruta que git ignore (`data/` lo está); si no, el guion se niega.
- `--salida` no se sobrescribe nunca. Solo existen `_v1` y `_v2` (cualquier `v3` o mayor en el nombre se
  rechaza); `_v2` exige que exista el `_v1` conservado y que la declaración del entorno sea otra.
- `--task-ids ID...` mide solo esas tareas (modo ensayo) y no escribe registro (no admite `--salida`).

Una corrida cortada se continúa con **el mismo comando**: cada ejecución se guarda al terminar y no se
repite ni se sobrescribe. Un `--crudo` tiene **un solo modo** (medición, ensayo con `--task-ids` o muestra),
un entorno, un `tasks.jsonl` y un directorio de snapshots, fijados en su `manifiesto.json` junto con un
identificador de corrida; intentar otra cosa sobre el mismo `--crudo` es salida 2. En particular, una
medición completa **no reutiliza** las ejecuciones de un ensayo, y una muestra no reutiliza las de la medición.

## Diario de solo-añadir

`--crudo/diario.jsonl` lleva una línea por ejecución lanzada (tarea, ronda, intento, fecha, SHA-256 del
archivo de la ejecución y hash de la línea anterior). Al reanudar, toda ejecución del diario debe existir
con ese hash y toda ejecución en disco debe estar en el diario; si no, salida 2. Una escritura cortada justo
entre el archivo de la ejecución y su línea del diario deja una ejecución sin anotar y también da 2: en ese
caso el `--crudo` se descarta y se mide de nuevo.

El registro versionable lleva por tarea `ejecuciones_lanzadas` y, arriba, `diario_sha256` (hash de la última
línea, que encadena todas). **Esto hace visible la manipulación; no la impide.** Quien edita a la vez una
ejecución y el diario completo produce un diario coherente, y solo el hash final distinto lo delata, si
alguien tenía el original. La defensa real es la repetición de una muestra por el orquestador.

## Códigos de salida

| Código | Significado |
|---|---|
| 0 | Medición completa sin hallazgo (muestra: todas las clases coinciden; `--task-ids`: terminada, sin registro) |
| 1 | Completa con hallazgo: la guarda salta (registro escrito) o, en muestra, alguna clase difiere |
| 2 | No se pudo medir o validar (entrada, entorno, `swegemma` ausente, snapshots que faltan, verificador caído, error del arnés sin categoría, archivo existente, ruta cruda versionada, diario o crudo manipulados) |
| 3 | Error inesperado del guion (se imprime el tipo y el punto del guion, no el texto de la excepción) |

## Qué queda versionado y qué no

Versionado, en `validez_tareas_v1.json` (esquema `kaggle-task-validity/1`, el que valida
`scripts/kaggle_prereg.py`): `sha256_tasks`, `entorno_sha256` (hash de la declaración, que contiene la
imagen y la versión del arnés), `diario_sha256`, por tarea `instance_id`, repositorio, clase, duraciones,
`ejecuciones_lanzadas` y las ejecuciones con lo que A.2 y A.4 enumeran (estado, `resolved`, código de
salida, categoría del error de una lista cerrada, nunca su texto, y duración), y la lista
`tareas_invalidas`. El mismo archivo es el que `scripts/kaggle_split.py --calibracion` lee para excluir.

No versionado, solo en `--crudo`: el resultado crudo de cada ejecución (texto del error, salida de las
pruebas, conteos `passed`/`failed`/`errors` y fecha UTC por ejecución), el diario, el manifiesto y
`arnes.log`. Nunca en ningún archivo del repositorio: nombres de pruebas, logs, enunciados, parches, ni el
SHA-256 del parche de referencia. El parche se lee dentro de la función que llama al arnés y no sale de ella.

**La consola de una corrida real también es salida cruda.** El guion dirige los loggers `swegemma*` y
`adk*` a `--crudo/arnes.log`, pero stdout y stderr de una corrida real pueden traer fragmentos del arnés
(otros módulos, advertencias, avisos de Docker): no se pegan en ningún sitio versionado (ni en el PR ni en
un comentario). El arnés escribe el parche en un archivo temporal del sistema y lo borra al terminar; si el
proceso muere, hay que limpiar la carpeta temporal (`%TEMP%` en Windows).

## Dónde medir

El entorno de la validez es el entorno en que se verifican las réplicas (A.1), y lo fija el ensayo de
notebook. **Riesgo declarado de Windows:** el arnés escribe el parche temporal en modo texto, así que
cp1252 y CRLF pueden hacer fallar el parche de referencia en general y disparar la guarda en todos los
repositorios. Por eso la medición que vale se hace en el entorno que fije el ensayo de notebook y no en un
Windows local; una medición local solo es un ensayo.

## Repetir una muestra (revisión del orquestador)

```bash
python -m scripts.kaggle_validez ... --crudo <OTRO directorio crudo> \
  --muestra-desde experiments/gemma_developer_agent/calibracion/validez_tareas_v1.json \
  --comparacion <ruta nueva>.json
```

El `--crudo` de la muestra **debe ser otro**: sobre el de la medición el guion sale con 2 sin ejecutar nada
(el modo no coincide), para que «coincide» no pueda salir de ejecuciones reutilizadas. Exige además el mismo
`tasks.jsonl` y la misma declaración de entorno que la referencia. Mide todas las tareas excluidas del
registro de referencia y las 10 primeras por orden de `sha256(instance_id)`, y compara clase contra clase
(las duraciones no se comparan). Sale con 0 si todas coinciden y con 1 si alguna difiere; en ese caso el
archivo no se mergea (A.4).
