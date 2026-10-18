# Brazo 12B — variante de modelo (construido 2026-10-18; NO subir, NO correr sin decisión del dueño)

Brazo «model-variant» de la Fase D del plan del dueño (2026-10-17, log 4), construido **solo** porque
la regla de variantes se verificó favorable: la página oficial «Model Selection, Budget, and Harness
Rules» y el hilo sticky 748287 (host, 2026-10-11) exigen **una sola variante por envío** («Every agent
and subagent in your submission must use the same variant») y soportan `31b`, `12b`, `e4b` y `e2b`;
nada prohíbe que envíos distintos usen variantes distintas (STATUS §Reglas, Fase B, fila f).

Elección 12B sobre E4B: el estudio de los notebooks públicos (`docs/c7_baseline024_estudio.md`) no
aporta evidencia sobre modelos chicos (los cuatro usan 31B); la ablación pública citada allí (no
verificada) atribuye al pensamiento la mitad de las resueltas, así que el candidato más cercano en
capacidad al 31B (12B, **thinking on**) es el que menos confunde la lectura. E4B/E2B quedan para
después, con el mismo patrón (cambiar el nombre del modelo en dos archivos y el `model_sources`).

Deltas **puros de configuración** respecto a la condición 7 (`0f52de0b84cb`):

- **(a) Modelo**: `gemma-4-31b-it-qat-w4a16-ct → gemma-4-12b-it-qat-w4a16-ct` en `agent.yaml` y en
  `sub_agents/code_analyzer.yaml` (los dos agentes con la misma variante).
- **(b) Muro**: `eval_config.yaml` con `max_time_minutes: 5.0` (sub-019 lo probó en producción).
- **Sampling sin tocar** (`thinking_budget: 4096`, `include_thoughts: true`) y **prompt byte-idéntico**
  al de la condición 7 (el armar lo verifica contra la descarga de réplica 1).

| | condición 7 | R1-fiel | **brazo 12B** |
|---|---|---|---|
| huella de configuración | `0f52de0b84cb` | `5e1638518420` | **`adb3004b2f76`** |
| kernel (si se sube) | `cs4all/c7-replica-condicion-7` | `cs4all/c7-r1fiel-condicion-7` | `cs4all/c7-12b-condicion-7` |
| `model_sources` | `…/gemma-4-31b-it-qat-w4a16-ct/2` | igual | `google/gemma-4/Other/gemma-4-12b-it-qat-w4a16-ct/2` |

## Qué hay aquí

| Archivo | Rol |
|---|---|
| `notebook_c7_12b.py` | Guion del notebook (fuente de verdad). Copia del patrón R1-fiel: la guardia busca el directorio del **12B**; la celda «kit» reescribe el modelo en los dos YAML, escribe el eval_config con 5.0 min y deja el sampling de la condición 7; la celda «servidor» pasa a vLLM el override indicado por el host (`extra_args=("--hf-overrides", '{"architectures": ["Gemma4ForCausalLM"], "model_type": "gemma4"}')`, hilo 748287, respuesta del 2026-10-11 14:39); la guarda exige `HUELLA_12B`. |
| `armar_notebook_12b.py` | Genera `notebook_c7_12b.ipynb` + `kernel-metadata.json`. Verifica el prompt contra la descarga de réplica 1, el sampling contra su constante, los tres deltas en el guion (5.0 min, modelo 12B, override) y exige huella == `adb3004b2f76`. Se ejecuta con `PYTHONPATH=. .venv-linux/bin/python experiments/gemma_developer_agent/replicas_c7_12b/armar_notebook_12b.py`. |
| `huella_12b.txt` | Registro: huellas de la condición 7, R1-fiel y 12B con los deltas. |

## Verificación (2026-10-18, todo en local, 0 GPU)

- Armar ×5: huella estable `adb3004b2f76`, ipynb sin deriva.
- Diff contra `replicas_c7_r1fiel/notebook_c7_r1fiel.py` (normalizando el nombre del brazo): solo la
  cabecera, la cadena del modelo en la guardia y en `TARGET_MODEL_NAME`, la reescritura del modelo en
  la celda «kit», el sampling (4096 en vez de 0) y el `extra_args` del servidor.
- Preflight `scripts.kaggle_preflight comprobar … --tope-min 150 --ruedas …`: **24/24 «Se puede
  subir»**. El simulador del preflight fijaba el directorio del 31B y hacía fallar la guardia de
  cualquier otra variante; ahora lee la variante de `model_sources` del `kernel-metadata.json`
  (`modelo_de_metadatos`, con test propio en `tests/test_kaggle_preflight_modelo.py`).
- `ruff check` y `ruff format --check` limpios (el `.ipynb` generado está excluido en `pyproject.toml`,
  como los demás brazos).

## Riesgos conocidos antes de correrlo o enviarlo

1. **El scorer puede no servir el 12B**: tres equipos reportan «Notebook Threw Exception» al enviar
   con 12B el mismo bundle que puntúa con 31B (hilo 749259, 2026-10-14/15); al 2026-10-16 nadie
   confirma públicamente un 12B puntuado de extremo a extremo. Un participante sí corrió el 12B en un
   notebook con el wheelhouse V31 y **Python 3.12** (el entorno con Python 3.13 rechaza nueve ruedas
   `cp312`). **Regla**: no enviar 12B hasta ver un 12B puntuado en el foro, o hasta correr este
   notebook en local y leer su salida.
2. La imagen fijada en `kernel-metadata.json` es la del patrón R1-fiel; si el entorno resulta ser
   Python 3.13, cambiar al pin de Python 3.12 que reporta el foro (2026-07-01) antes de subir.
3. El 12B cambia la velocidad por token y el uso de memoria: el envelope de 12 h se recalcula con su
   primera corrida local, no se hereda del 31B.

## Estado

Construido el 2026-10-18. **No se ha subido ni corrido nada.** Correrlo es decisión del dueño
(el cron del lunes lo lista como «no correr ni enviar hasta confirmación pública»).
