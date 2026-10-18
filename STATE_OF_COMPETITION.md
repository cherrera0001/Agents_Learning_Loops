# Estado de la Competencia: Gemma 4 Developer Agent

**Fecha de corte:** 2026-10-13  
**Rol:** Principal Research Engineer  
**Repositorio:** `Agents_Learning_Loops`  
**Competencia:** Kaggle Gemma 4 Developer Agent (Code Track ID `149921`, Paper Track ID `163111`)

---

## 1. Pila de Software y Versiones Exactas del Arnés

El arnés oficial de evaluación no se distribuye por PyPI, sino a través del conjunto de ruedas (*wheelhouse*) mantenido por la organización en Kaggle (`metric/gemma-4-developer-agent-wheelhouse`). A lo largo de la competencia, el arnés ha sufrido cambios de versión críticos que rompen la comparabilidad directa entre corridas previas y actuales:

| Paquete | Versión Histórica (2026-10-02 a 10-08) | Versión Vigente Ensayada (2026-10-12 a 10-13) | SHA-256 de Rueda Vigente (`py3-none-any.whl`) | Rol en la Evaluación |
| :--- | :--- | :--- | :--- | :--- |
| **`swegemma`** | `0.2.7` | **`0.2.11`** *(actualizado 2026-10-09 y re-empaquetado 2026-10-12 19:51 UTC)* | `9ad876581f3acde8ec3c369858f0834e2b9f41a3cffce3ca42f09cb090aea9d3` | Motor de evaluación en dos contenedores, ciclo de vida del agente, extracción de diffs y verificación hermética con `pytest`. |
| **`adk-submission`** | `0.2.12` | **`0.2.13`** *(actualizado 2026-10-09)* | `f156f0bd84580ccb9334726d114d7a5481f16d3a6e2887cc4d276ced0ef8d99d` | Compilador declarativo de `agent.yaml` a árboles `BaseAgent` de Google ADK; gestor de procesos `VllmServer`. |
| **`adk-eval-core`** | `0.1.0` | **`0.1.0`** *(sin cambios)* | `e614e1b2fe8d886a634871e4c57f9887e1cc66e8c27300f8503a43c6e3ca82f3` | Infraestructura de sandbox Docker/Subprocess, motor de reemplazo de 3 niveles (`apply_replacement`), presupuesto y trazas ATIF. |
| **`google-adk`** | `1.36.1` | **`1.36.1`** *(sin cambios)* | `1a2f6868c509e3151fb0de3575a7d18b45c338be86f420924dad74e7193631a0` | Framework base Google Agent Development Kit. |

### Cambios semánticos críticos del paso 0.2.7/0.2.12 a 0.2.11/0.2.13:
1. **Gobierno del Razonamiento (`thinking_budget`):** En `adk-submission 0.2.12`, `include_thoughts: false` con `thinking_budget: 4096` enviaba `enable_thinking: False` al servidor vLLM. Desde `0.2.13`, cualquier `thinking_budget > 0` fuerza `enable_thinking: True` en vLLM; la bandera `include_thoughts` solo decide si el texto de pensamiento se reinyecta en el historial. Para apagar el razonamiento en `0.2.13` es obligatorio declarar `thinking_budget: 0`.
2. **Filtrado de Archivos Protegidos:** `swegemma 0.2.11` remueve proactivamente archivos de pruebas (`test_*.py`, `*_test.py`, rutas bajo `tests/`) y configuraciones de test runner (`conftest.py`, `pytest.ini`, `pyproject.toml`) del parche al entregar, en respaldo y en verificación.
3. **Manejo de Errores de Herramientas:** Los errores de herramientas se devuelven al modelo como respuesta de error estructurada en lugar de terminar la sesión.
4. **Eliminación de Símbolos:** `swegemma 0.2.11` eliminó `swegemma.models.discovery.validate_single_declared_model`, obligando a migrar los scripts de notebook a `adk_submission.discover_declared_models`.

---

## 2. Modelo Base y Adaptadores (LoRA)

- **Modelo Base Obligatorio:** `gemma-4-31b-it-qat-w4a16-ct` (cuantización W4A16, footprint en VRAM de ~16–18 GB en 4x L4 GPUs con vLLM TP=4, `gpu_memory_utilization=0.80`, `max_model_len=32768`).
- **Regla de Modelo Único:** Todo agente y subagente en el submission debe declarar estrictamente este modelo base (`validate_single_declared_model` / `discover_declared_models`).
- **Estado de Adaptadores (LoRA):**
  - El Starter Kit oficial traía dos adaptadores de muestra (`adapters/main_lora/` y `adapters/tool_lora/`, 217 KB cada uno). Se confirmó que eran pesos ficticios/placebo.
  - En todas las condiciones probadas y enviadas (`sub-002` a `sub-012`), los adaptadores fueron **retirados completamente** para evitar consumo innecesario de memoria, desajustes de inferencia y complejidad no validada.
  - **Uso actual de LoRA:** Ninguno (0 adaptadores).

---

## 3. Registro Histórico de Envíos (Submissions) y Huellas SHA-256

Fuente de verdad: `experiments/gemma_developer_agent/submissions/registry.json`.

| ID | Fecha (UTC) | Condición | Archivo ZIP | Tamaño (bytes) | SHA-256 (completo) | Score Público | Estado Kaggle | Notas Operativas |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`sub-001`** | 2026-10-03 | A | `a_kit_submission.zip` | 172 770 | `bcc4bf4efd2b064257194e470f85c6cde0b4bfa0a50a68b80a6b9f20beccdf5b` | — | `prepared` | Kit oficial intacto (con adaptadores dummy). Descartado antes de enviar. |
| **`sub-002`** | 2026-10-03 | A | `submission_a_ajustado.zip` | 3 495 | `d8a3e1d3558f03b72b3f86037ff53b462a8f66566e1bb7907240bcb0ce4d7182` | **0.0600** | `scored` | Ref 56808559. Sin adaptadores, thoughts: false, 4 min, 40 llamadas, 100 turnos, 60s cmd. (~4/58 tareas). |
| **`sub-003`** | 2026-10-04 | A | `submission_a_ajustado.zip` | 3 495 | `d8a3e1d3558f03b72b3f86037ff53b462a8f66566e1bb7907240bcb0ce4d7182` | **0.0500** | `scored` | Ref 56830336. **Mismo ZIP idéntico byte a byte** reenviado para medir ruido. (~3/58 tareas). |
| **`sub-004`** | 2026-10-09 | K | `submission_k_interfaz_limpia.zip` | 2 545 | `3346af0e9a92fd42e9a93d30f9e0e7fab42279e47b9015853fe13439b3c2c8b1` | — | `prepared` | Interfaz limpia: sin subagente, sin herramientas de grafo (6 herramientas). No enviado. |
| **`sub-005`** | 2026-10-07 | I | `submission_i_razona.zip` | 3 494 | `65a0216007e19bf6b26ec1ae0386be06814e97a3d85f63636fb10053651a6763` | **0.0800** | `scored` | Ref 56895202. Razonamiento encendido (`include_thoughts: true`), 60 llamadas, 4.5 min. Pasó por error de sistema antes de puntuar. (~5/58 tareas). |
| **`sub-006`** | 2026-10-07 | I | `submission_i_razona.zip` | 3 494 | `65a0216007e19bf6b26ec1ae0386be06814e97a3d85f63636fb10053651a6763` | **0.1300** | `scored` | Ref 56916129. **Mismo ZIP idéntico** que `sub-005`. Variación extrema: de 0.08 a 0.13 (~8/58 tareas). Ruido puro de evaluación. |
| **`sub-007`** | 2026-10-12 | A0 | `submission_a0_sin_razonar.zip` | 3 475 | `01a6d82fc42fb9991601570520eda0e8e81bf0a05b253e13fe9718306a1cc4e2` | — | `prepared` | Condición A con `thinking_budget: 0` para apagar efectivamente el razonamiento en `adk-submission 0.2.13`. No enviado. |
| **`sub-008`** | 2026-10-12 | I | `submission_i_razona.zip` | 3 494 | `65a0216007e19bf6b26ec1ae0386be06814e97a3d85f63636fb10053651a6763` | — | `submitted` | Ref 57098570. Tercera lectura de la condición I bajo arnés nuevo. |
| **`sub-009`** | 2026-10-13 | C1 | `submission_r1_c1_tres_cambios_6min.zip` | 2 980 | `a038a38925d7f1cf34a09e425e66f4b5eaedef9481fee23efe3e33b2b2d0193f` | — | `prepared` | Candidato R1: 28 llamadas, 6.0 min, timeout cmd 240s, sin subagente, grafo prohibido en prompt, edición temprana texto E. |
| **`sub-010`** | 2026-10-13 | C2 | `submission_r1_c2_edicion_temprana.zip` | 3 749 | `aa0750f0f47f63276cfcd3756fd0771d0b6633b3e21393e60ce8f9351dea0f39` | — | `prepared` | Candidato R1: Base I con solo la inserción de texto E (edición temprana). |
| **`sub-011`** | 2026-10-13 | C3 | `submission_r1_c3_pensamiento_1536.zip` | 3 494 | `e655e942abce3fb8576cf0abbe461fb518d4194ec8cde78521bb9055191b7e44` | — | `prepared` | Candidato R1: Base I con `thinking_budget: 1536` (aislar presupuesto de tokens de pensamiento). |
| **`sub-012`** | 2026-10-13 | C4 | `submission_r1_c4_triaje.zip` | 4 013 | `8e7009dda5d9e460e3be852084408f45864393e63e4602dde053f243615f96b8` | — | `prepared` | Candidato R1: Base I con Step 0 de triaje para problemas con enunciados vacíos/cortos (<250 caracteres). |

---

## 4. Parámetros Operativos por Condición

| Parámetro | Starter Kit Oficial | Condición A (sub-002) | Condición I (sub-005) | Condición C1 (sub-009) |
| :--- | :--- | :--- | :--- | :--- |
| `thinking_config.include_thoughts` | `false` | `false` | `true` | `true` |
| `thinking_config.thinking_budget` | `4096` | `4096` *(0 en A0)* | `4096` | `4096` *(1536 en C3)* |
| `max_output_tokens` | `16384` | `8192` | `16384` | `16384` |
| `max_time_minutes` (por tarea) | `60.0` (default arnés) | `4.0` | `4.5` | `6.0` |
| `max_tool_calls` (por tarea) | `100` (default arnés) | `40` | `60` | `28` |
| `max_turns` (turnos de razonamiento) | `500` (default arnés) | `100` | `100` | `100` |
| `timeout_seconds` (por comando) | `300` (default arnés) | `60` | `60` | `240` |
| Subagente `code_analyzer` | Presente (`agent_tool`) | Presente | Presente | **Eliminado** |
| Herramientas de Grafo | Declaradas y ordenadas | Declaradas | Declaradas | Declaradas, **prohibidas en prompt** |

---

## 5. Resultados Locales vs. Resultados Públicos y Comparabilidad

### 5.1 Validez del Conjunto Local (129 tareas públicas)
- **Como viene el entorno oficial:** Solo **71 de 129 tareas discriminan** (fallan sin parche y pasan con parche de referencia).
  - `fastapi`: 29 de 67 discriminan.
  - `rich`: 42 de 48 discriminan.
  - `requests` y `httpx`: 0 de 14 discriminan (entorno roto para tests).
- **Con 3 paquetes de test auxiliares instalados:** 103 de 129 discriminan.
- **Lección metrológica:** 58 tareas públicas fallan por defectos del entorno de test, no por incapacidad del modelo. Toda medición local válida debe restringirse estrictamente a tareas que discriminan.

### 5.2 Variación Corrida a Corrida (Ruido Intrínseco)
- **Local (réplicas idénticas sobre 30 tareas públicas):**
  - El resultado neto varía en $\pm 1$ tarea resuelta (ej. 6 vs 7 de 30).
  - La clasificación de fallo de una tarea cambia en **13 de 30 tareas** entre corridas idénticas. Una tabla de fallos de una sola corrida no es estable.
- **Público (Leaderboard de Kaggle):**
  - Mismo archivo ZIP local enviado dos veces (`sub-002` vs `sub-003`): **0.0600 vs 0.0500** (4 vs 3 tareas de 58).
  - Mismo archivo ZIP local con razonamiento enviado dos veces (`sub-005` vs `sub-006`): **0.0800 vs 0.1300** (5 vs 8 tareas de 58).
  - Desviación típica estimada: $\sigma \approx 2.4$ tareas por envío.

### 5.3 Conclusión sobre Comparabilidad
Un score público aislado carece por completo de validez estadística para adjudicar superioridad. Una aparente subida de 0.08 a 0.13 ocurre por mera varianza del muestreo y estado del cluster en Kaggle sin alterar un solo byte del submission. Solo diferencias consistentes pareadas con test exacto de McNemar ($p \le 0.05$) sobre $\ge 60$ tareas o replicadas en al menos 5 lecturas de leaderboard justifican mantener un cambio.

---

## 6. Evidencia Faltante y Brechas Abiertas

1. **Concurrencia real del evaluador de Kaggle:** No está documentado si el evaluador privado corre 1 tarea a la vez (serie) o múltiples en paralelo (concurrencia $N \ge 2$), lo cual altera drásticamente el margen del presupuesto global de 12 horas.
2. **Distribución de tareas privadas:** Se desconoce si el test set oculto tiene la misma patología de enunciados cortos (<250 caracteres) que los repositorios públicos (donde 15/30 tareas tienen enunciados mínimos y tasa de éxito cercana a 0).
3. **Comportamiento del evaluador ante herramientas no declaradas:** Permanece pendiente verificar si en el entorno de Kaggle retirar una herramienta del YAML termina la tarea con error o simplemente devuelve `ToolNotFound`.
