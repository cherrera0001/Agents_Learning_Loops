# Manifiesto de Adaptadores LoRA · Condición A (Starter Kit Oficial)

Este directorio documenta los adaptadores LoRA incluidos oficialmente en el starter kit de la
competencia (`data/sample_submission/adapters/`).
Siguiendo las directrices de gobernanza de ALL, **los archivos de pesos binarios (`*.safetensors`) no se
versionan en git** para mantener el repositorio ligero y reproducible.

---

## 1. Identificación y Verificación Criptográfica

| Adaptador | Archivo | Tamaño (bytes) | SHA-256 |
|---|---|---|---|
| `main_lora` | `adapter_config.json` | 664 | `75a46da2db7f3c70442e5c728f64059aff52cf64174cee7aeb3a4ec37f6e78fb` |
| `main_lora` | `adapter_model.safetensors` | 217 672 | `dcbedd989af34f5201a39606e0bd4014d351a29162dd96da418782cbbe487ad9` |
| `tool_lora` | `adapter_config.json` | 664 | `75a46da2db7f3c70442e5c728f64059aff52cf64174cee7aeb3a4ec37f6e78fb` |
| `tool_lora` | `adapter_model.safetensors` | 217 672 | `dcbedd989af34f5201a39606e0bd4014d351a29162dd96da418782cbbe487ad9` |

---

## 2. Inspección de Arquitectura (`adapter_config.json`)

Ambos adaptadores (`main_lora` y `tool_lora`) poseen configuraciones idénticas:
* **Modelo base:** `google/gemma-4-31b-it-qat-w4a16-ct`
* **Tipo PEFT:** `LORA`
* **Rango ($r$):** `4`
* **LoRA Alpha:** `8`
* **Módulos objetivo (`target_modules`):** `["q_proj", "o_proj"]`
* **Capas a transformar (`layers_to_transform`):** `[0]` (únicamente la capa 0)

### Diagnóstico Técnico: Adaptadores Dummy / Placeholders de Ejemplo
1. **Tamaño vs. Expectativa:** Un LoRA real de rango 16 aplicado a todas las capas de atención de un modelo
   de 31B parámetros ronda entre **110 MB y 220 MB** (`HARNESS § 3.4`). Estos adaptadores pesan apenas
   **217 KB** cada uno.
2. **Hashes idénticos:** Los archivos `adapter_model.safetensors` de `main_lora` y `tool_lora` tienen
   exactamente el mismo hash SHA-256 (`dcbedd...`), demostrando que son pesos idénticos de plantilla.
3. **Restricción a capa 0:** Solo adaptan la capa 0 (`layers_to_transform: [0]`). Son demostraciones
   provistas por Kaggle para ilustrar el mecanismo de carga de adaptadores múltiples vía vLLM
   (`enable_lora=True`).

---

## 3. Instrucción de Descarga

Para reconstruir localmente los pesos en un entorno de ejecución:

```bash
# Requiere KAGGLE_API_TOKEN en variables de entorno o archivo .env
python -c "
import os, urllib.request, urllib.parse

token = os.environ.get('KAGGLE_API_TOKEN')
if not token:
    raise RuntimeError('KAGGLE_API_TOKEN no configurada')

competition = 'gemma-4-developer-agent'
adapters = [
    ('adapters/main_lora/adapter_model.safetensors',
     'sample_submission/adapters/main_lora/adapter_model.safetensors'),
    ('adapters/tool_lora/adapter_model.safetensors',
     'sample_submission/adapters/tool_lora/adapter_model.safetensors'),
]

for dst_rel, src_path in adapters:
    enc = urllib.parse.quote(src_path, safe='')
    url = f'https://www.kaggle.com/api/v1/competitions/data/download/{competition}/{enc}'
    req = urllib.request.Request(url, headers={'Authorization': f'Bearer {token}'})
    with urllib.request.urlopen(req) as resp, open(dst_rel, 'wb') as f:
        f.write(resp.read())
    print(f'Descargado: {dst_rel}')
"
```

---

## 4. Propuesta de Decisión para el Orquestador (Condición A)

* **Opción A.1 (Estricto kit oficial):** Mantener `adapter: main_lora` y `adapter: tool_lora` activos con los
  pesos descargados.
  * *Ventaja:* Es una réplica exacta del submission provisto como muestra por la competencia.
  * *Riesgo:* Puede inducir perturbaciones espurias en el razonamiento al aplicar pesos dummy sobre la
    capa 0 de Gemma 4.
* **Opción A.2 («A sin LoRA»):** Retirar las directivas `adapter` de `agent.yaml` y `code_analyzer.yaml` para
  evaluar el modelo base puro `gemma-4-31b-it-qat-w4a16-ct`.
  * *Ventaja:* Establece una línea base limpia y determinista del modelo base sin sesgos de adaptadores dummy.
  * *Argumento recomendado:* La condición A de control científico debe ser «A sin LoRA» para medir el
    rendimiento genuino de Gemma 4 31B antes de introducir intervenciones (skills o LoRAs reales).
