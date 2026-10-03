# Verificación de compilación: condición A con adk-submission

> **Estado del documento.** Vigente solo en parte. Se escribió cuando `conditions/a_kit/` guardaba el kit
> completo; el PR #112 retiró del repositorio público esos archivos por la regla de no redistribución de los
> datos de la competencia (Rules § 2.4.b). Hoy ese directorio tiene solo `README.md`, `manifest.json` y
> `download_kit.py`, y el kit se reconstruye con `download_kit.py` desde el manifiesto. Las salidas de abajo
> **no tienen recibo**: se pegaron de una ejecución local que no quedó versionada. Se conservan como
> descripción del comportamiento, no como prueba. Mapa de documentos:
> [`README.md`](../README.md#12-mapa-de-documentos).

Este documento describe cómo se comprobó que el kit oficial (condición A) pasa por el compilador declarativo
`adk-submission` (v0.2.12) del arnés de la competencia, sin GPU ni servidor de inferencia activo.

---

## 1. Script de verificación

El directorio del envío es el que arma [`conditions/a_kit/README.md`](../conditions/a_kit/README.md): se
reconstruye con `download_kit.py` y se verifica contra el manifiesto. Con ese directorio reconstruido, desde
la raíz del repositorio:

```python
from pathlib import Path
from adk_submission import ToolRegistry, compile_submission
from swegemma.models import setup_gemma_model_registry

submission_dir = Path("experiments/gemma_developer_agent/conditions/a_kit")
tools = ToolRegistry()
for tool_name in [
    "run_command",
    "read_file",
    "edit_file",
    "write_file",
    "get_status",
    "submit_patch",
    "get_code_neighbors",
    "search_similar_code",
    "get_code_subgraph",
]:
    tools.register(tool_name, lambda **kwargs: None)

models = setup_gemma_model_registry()

agent = compile_submission(
    submission_dir=submission_dir,
    tool_registry=tools,
    model_registry=models,
)
```

---

## 2. Salida del compilador (sin recibo)

### 2.1 Sin los pesos de los adaptadores

Los archivos `*.safetensors` no se versionan (regla de no redistribución). En una ejecución local sin esos
pesos, el compilador comprobó la coherencia del esquema y se negó a compilar por la ausencia física de los
adaptadores que declaran `agent.yaml` y `sub_agents/code_analyzer.yaml`:

```text
Traceback (most recent call last):
  ...
  File ".../adk_submission/resolvers/models.py", line 53, in resolve_model
    raise AdapterNotFoundError(config.adapter, available=available)
adk_submission.errors.AdapterNotFoundError: Adapter 'tool_lora' not found in
discovered adapters. Available adapters: none
```

### 2.2 Con los adaptadores descargados

Con los adaptadores de muestra del kit oficial (217 KB cada uno, según el manifiesto) presentes en el
directorio del envío, la compilación terminó sin error y generó el árbol de agentes de Google ADK:

```text
Compiled sample_submission successfully:
  Agent Name: swe_baseline_agent
  Agent Type: <class 'google.adk.agents.llm_agent.LlmAgent'>
  Model: gemma-4-31b-it-qat-w4a16-ct
  Adapter: main_lora
  Tools (10):
   - run_command
   - read_file
   - edit_file
   - write_file
   - get_status
   - submit_patch
   - get_code_neighbors
   - search_similar_code
   - get_code_subgraph
   - code_analyzer_agent (Sub-agent tool: model=gemma-4-31b-it-qat-w4a16-ct, adapter=tool_lora)
```

---

## 3. Qué se concluye, y qué no

1. El compilador `adk-submission` valida la consistencia declarativa y no admite adaptadores declarados en
   un YAML sin sus archivos de pesos.
2. La estructura del kit (`agent.yaml`, `prompts/system.md`, `configs/sampling.yaml`,
   `sub_agents/code_analyzer.yaml`) coincide con la que lista el manifiesto, que lleva los SHA-256 de cada
   archivo; la comprobación de identidad con el kit oficial es esa verificación contra el manifiesto, no
   esta compilación.
3. Esta compilación no comprueba nada sobre el comportamiento del agente ni sobre el modelo: el ensayo de
   notebook del pre-registro de la línea base A (sección A.0) vuelve a comprobar que el kit compila, esta vez
   con recibo, y todavía no se ha ejecutado.
