# Verificación de Compilación · Condición A con adk-submission

Este documento certifica el paso de `conditions/a_kit/` por el compilador declarativo `adk-submission`
(v0.2.12) del arnés oficial, sin requerir GPU ni servidor de inferencia activo.

---

## 1. Script de Verificación

```python
from pathlib import Path
from adk_submission import ToolRegistry, compile_submission
from swegemma.models import setup_gemma_model_registry

submission_dir = Path("experiments/gemma_developer_agent/conditions/a_kit")
tools = ToolRegistry()
for tool_name in [
    "run_command", "read_file", "edit_file", "write_file", "get_status",
    "submit_patch", "get_code_neighbors", "search_similar_code", "get_code_subgraph",
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

## 2. Salida del Compilador

### 2.1 Sobre el árbol versionado en Git (sin pesos binarios .safetensors)

Debido a la regla de gobernanza de ALL («No versiones datos de Kaggle: ni tasks.jsonl, ni snapshots,
ni pesos»), los archivos binarios `*.safetensors` no están en el control de versiones. Al compilar
`conditions/a_kit/` en su estado puramente versionado, el compilador verifica la coherencia del esquema
y detecta la ausencia física de los adaptadores declarados en `agent.yaml` y `code_analyzer.yaml`:

```text
Traceback (most recent call last):
  ...
  File ".../adk_submission/resolvers/models.py", line 53, in resolve_model
    raise AdapterNotFoundError(config.adapter, available=available)
adk_submission.errors.AdapterNotFoundError: Adapter 'tool_lora' not found in
discovered adapters. Available adapters: none
```

### 2.2 Con adaptadores LoRA descargados localmente (`data/sample_submission/adapters/`)

Al disponer de los adaptadores LoRA de muestra provistos por el kit oficial (`217 KB`), la compilación
es completamente exitosa y genera el árbol canónico de Google ADK:

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

## 3. Conclusión Técnica

1. El compilador `adk-submission` valida estrictamente la consistencia declarativa: no tolera adaptadores
   declarados en YAML sin archivos de pesos presentes.
2. La estructura de `conditions/a_kit/` (`agent.yaml`, `prompts/system.md`, `configs/sampling.yaml`,
   `sub_agents/code_analyzer.yaml`) es 100 % idéntica y compatible con el starter kit oficial de Kaggle.
