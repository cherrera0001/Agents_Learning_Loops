# Condición A: Kit Oficial de Kaggle (`sample_submission`)

Este directorio contiene las especificaciones y herramientas para reconstruir y verificar localmente la **Condición A** (línea base oficial del kit de la competencia Kaggle Gemma 4 Developer Agent).

En cumplimiento de la **Sección 4 de las reglas oficiales de la competencia** (*Competition Data — Non-Redistribution*), los archivos del kit y los pesos de los adaptadores **no se versionan en el repositorio público**. En su lugar, se provee un manifiesto declarativo con los hashes SHA-256 oficiales y un script en biblioteca estándar (`stdlib`) para su descarga y verificación íntegra.

---

## 1. Manifiesto Declarativo de Integridad

El archivo [`manifest.json`](manifest.json) define la lista exhaustiva de los 10 archivos que componen el kit oficial, su tamaño en bytes y su hash SHA-256 oficial:

| Archivo | Tamaño (bytes) | SHA-256 |
|---|---|---|
| `agent.yaml` | 438 | `c7fbbbbdc44778419be8e9f53a85800eeb17d0cf151e0846c46e107401b72034` |
| `eval_config.yaml` | 232 | `adb486b67535fa59b427b79d44dafc131176f1f1964d184e16046ed520ede02d` |
| `configs/sampling.yaml` | 120 | `3dab0b2506dae34ce92fef7b380d6073729104b23fe2cf66d44ac1d2f213aa6a` |
| `prompts/analyzer.md` | 527 | `c762b062032cc8463015e589ad8b4f0e17296062e1b0ff1e78712eef9f5e2d43` |
| `prompts/system.md` | 3 888 | `f1cbf7943ee9687382321b1dfd9cd88581d608c1c8b8e6ea61a763bd1a3234af` |
| `sub_agents/code_analyzer.yaml` | 361 | `7a764798e36cc68aa38900256245e4aed969b5439b992c7da4105b6ebcb7e62b` |
| `adapters/main_lora/adapter_config.json` | 664 | `75a46da2db7f3c70442e5c728f64059aff52cf64174cee7aeb3a4ec37f6e78fb` |
| `adapters/main_lora/adapter_model.safetensors` | 217 672 | `dcbedd989af34f5201a39606e0bd4014d351a29162dd96da418782cbbe487ad9` |
| `adapters/tool_lora/adapter_config.json` | 664 | `75a46da2db7f3c70442e5c728f64059aff52cf64174cee7aeb3a4ec37f6e78fb` |
| `adapters/tool_lora/adapter_model.safetensors` | 217 672 | `dcbedd989af34f5201a39606e0bd4014d351a29162dd96da418782cbbe487ad9` |

---

## 2. Reconstrucción y Verificación Local

Para poblar y verificar localmente los archivos del kit:

```bash
# Opción 1: Descargar desde la API de Kaggle y verificar automáticamente
python experiments/gemma_developer_agent/conditions/a_kit/download_kit.py

# Opción 2: Solo verificar la integridad de los archivos existentes
python experiments/gemma_developer_agent/conditions/a_kit/download_kit.py --verify-only
```

El script utiliza exclusivamente la biblioteca estándar de Python (`urllib.request`, `hashlib`, `json`, `zipfile`), requiere autenticación estándar de Kaggle (`~/.kaggle/kaggle.json`, variables de entorno `KAGGLE_USERNAME`/`KAGGLE_KEY` o `.env`), y no imprime secretos ni tokens.

---

## 3. Estado en Control de Versiones (`.gitignore`)

Los archivos descargados del kit (`agent.yaml`, adaptadores, prompts y configuraciones) están excluidos en `.gitignore` para evitar cualquier redistribución accidental de datos de la competencia.
