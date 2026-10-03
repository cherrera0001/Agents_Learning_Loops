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
- `--crudo` recibe las salidas crudas y el estado de reanudación. Debe quedar fuera de un repositorio git o
  en una ruta que git ignore (`data/` lo está); si no, el guion se niega.
- `--params` es opcional: exige que el SHA-256 de `tasks.jsonl` sea el registrado en el pre-registro.
- `--salida` no se sobrescribe nunca. Un nombre `_v3` o posterior se rechaza (A.3: no hay tercera medición).
- `--task-ids ID...` mide solo esas tareas y no escribe registro (no admite `--salida`); sirve para ensayar.

Una corrida cortada se continúa con **el mismo comando**: cada ejecución se guarda al terminar y no se
repite ni se sobrescribe; si lo guardado y lo recalculado difieren, sale con 2.

## Códigos de salida

| Código | Significado |
|---|---|
| 0 | Medición completa sin hallazgo (muestra: todas las clases coinciden; `--task-ids`: terminada, sin registro) |
| 1 | Completa con hallazgo: la guarda salta (registro escrito) o, en muestra, alguna clase difiere |
| 2 | No se pudo medir o validar (entrada, entorno, `swegemma` ausente, verificador caído, error del arnés sin categoría, archivo existente, ruta cruda versionada, discrepancia) |
| 3 | Error inesperado del guion |

## Qué queda versionado y qué no

Versionado, en `validez_tareas_v1.json` (esquema `kaggle-task-validity/1`, el que valida
`scripts/kaggle_prereg.py`): `sha256_tasks`, `entorno_sha256` (hash de la declaración, que contiene la
imagen y la versión del arnés), por tarea `instance_id`, repositorio, clase, duraciones y todas las
ejecuciones con su código de salida, conteos `passed`/`failed`/`errors`, estado, categoría del error (lista
cerrada, nunca su texto), duración y fecha UTC, y la lista `tareas_invalidas`. El mismo archivo es el que
`scripts/kaggle_split.py --calibracion` lee para excluir.

No versionado, solo en `--crudo`: el resultado crudo de cada ejecución (texto del error y salida de las
pruebas) y el manifiesto del entorno. Nunca en ningún archivo del repositorio: nombres de pruebas, logs,
enunciados, parches, ni el SHA-256 del parche de referencia. El parche se lee dentro de la función que
llama al arnés y no sale de ella.

## Repetir una muestra (revisión del orquestador)

```bash
python -m scripts.kaggle_validez ... --crudo <otro directorio crudo> \
  --muestra-desde experiments/gemma_developer_agent/calibracion/validez_tareas_v1.json \
  --comparacion <ruta nueva>.json
```

Mide todas las tareas excluidas del registro de referencia y las 10 primeras por orden de
`sha256(instance_id)`, y compara clase contra clase (las duraciones no se comparan). Sale con 0 si todas
coinciden y con 1 si alguna difiere; en ese caso el archivo no se mergea (A.4).
