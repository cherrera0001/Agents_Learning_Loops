# Auditoría Integral del Arnés Oficial (`swegemma` / `adk-submission` / `adk-eval-core`)

**Fecha de corte:** 2026-10-13  
**Rol:** Principal Research Engineer  
**Repositorio:** `Agents_Learning_Loops`  
**Objetivo:** Desmitificar el comportamiento real del entorno de evaluación, contrastando la especificación teórica (`HARNESS_README.md`) con las trazas de ejecución medidas en Kaggle y pruebas locales.

---

## 1. Catálogo Real de Herramientas y Diagnóstico Operativo

El arnés registra exactamente **9 herramientas** en el `ToolRegistry` (`SwegemmaContext.create_tools()`), más la capacidad declarativa de registrar subagentes como herramientas (`AgentTool`).

| Herramienta | Firma y Argumentos Exigidos | ¿Cuenta para Presupuesto? | Conducta Medida en Trazas Reales | Veredicto Operativo |
| :--- | :--- | :--- | :--- | :--- |
| **`run_command`** | `command: str` | **Sí** (`@budget_gated`) | Funciona. Salida truncada a 5,000 chars. Timeout por comando `timeout_seconds`. | **MANTENER**. Es la vía primaria para pruebas y búsqueda con `grep`. |
| **`read_file`** | `filepath: str`, `start_line: int \| None`, `end_line: int \| None` | **Sí** (`@budget_gated`) | Funciona pero propensa a mal uso: doble límite de 150 líneas y 10,000 chars. 507 llamadas mal formadas observadas en 44 sesiones (el modelo confunde nombres de argumentos y resetea a línea 1). | **MANTENER**, con instrucción explícita de paginación e inspección acotada. |
| **`edit_file`** | `filepath: str`, `old_string: str`, `new_string: str`, `allow_multiple: bool = False` | **Sí** (`@budget_gated`) | Motor de reemplazo de 3 niveles (`exact` $\to$ `flexible` $\to$ `regex`). Falla con `FileEditError` si `old_string` tiene >1 coincidencia y `allow_multiple=False`. 211 llamadas rechazadas por schema previo (falta `old_string`). | **MANTENER**. Es el instrumento central de modificación. |
| **`write_file`** | `filepath: str`, `content: str` | **Sí** (`@budget_gated`) | Crea o sobreescribe archivos. Crea directorios intermedios. | **MANTENER**. Usar para scripts temporales o archivos nuevos. *Atención*: No dejar scripts en `/workspace` al entregar. |
| **`get_status`** | Ninguno | **No** (`count_tool_call=False`) | Devuelve llamadas restantes, tiempo restante y estado del parche. No gasta llamadas. | **MANTENER**. Útil para auto-monitoreo de presupuesto. |
| **`submit_patch`** | Ninguno | **No** (`count_tool_call=False`) | Ejecuta `git add -N .` y extrae `git diff --binary HEAD`. Al emitir respuesta final con `patch_submitted=True`, **termina inmediatamente el bucle del agente**. | **MANTENER**. Debe llamarse como última acción tras verificar. |
| **`search_similar_code`** | `query: str`, `k: int = 10` | **Sí** (`@budget_gated`) | **DEFECTO CRÍTICO / INSTRUMENTO INÚTIL**: Devolvió vacío (`[]`) o error de embedding en **300 de 300 llamadas observadas**. Motivo: El sandbox corre sin red y sin servidor de embeddings; solo busca coincidencia exacta de sufijo en un archivo `.npz`. Para palabras en lenguaje natural siempre falla. | **ELIMINAR / PROHIBIR**. Desperdicio puro de llamadas y tiempo. |
| **`get_code_neighbors`** | `node: str`, `edge_type: str \| None`, `max_neighbors: int = 50` | **Sí** (`@budget_gated`) | Consultas de grafo NetworkX. 0 sesiones se beneficiaron. Gasta tokens de contexto y llamadas sin generar hipótesis accionables de parche. | **ELIMINAR / PROHIBIR**. |
| **`get_code_subgraph`** | `nodes: list[str]` | **Sí** (`@budget_gated`) | Extracción de subgrafo inducido. Complejidad innecesaria que confunde el razonamiento del modelo base. | **ELIMINAR / PROHIBIR**. |
| **Subagente `code_analyzer`** | Configurado en `sub_agents/code_analyzer.yaml` | **Sí** (gasta llamadas en cada sub-acción) | **VALOR NETO NEGATIVO**: 7 de 7 sesiones donde se invocó terminaron no resueltas (0% éxito), consumiendo hasta el 65% del tope de llamadas (198 llamadas acumuladas). No tiene compactación de contexto, causando desbordes de ventana. | **ELIMINAR COMPLETAMENTE**. Un único agente principal supera consistentemente la delegación. |

---

## 2. Aplicación Real de Presupuestos, Tiempos y Límites

### 2.1 Presupuesto de Razonamiento (`thinking_budget`)
- **Regla del arnés (`adk_submission >= 0.2.13`):**  
  `thinking_budget` determina si el servidor vLLM activa `enable_thinking`.
  - Con `thinking_budget: 4096`: el modelo razona en todas las llamadas, generando entre 1,500 y 4,000 tokens de pensamiento.
  - Con `thinking_budget: 0`: el razonamiento se apaga completamente.
  - Con `include_thoughts: true`: los pensamientos pasados se conservan en el historial de contexto (consume contexto rápidamente hacia el umbral de compactación de 14,336 tokens).
  - Con `include_thoughts: false`: el modelo razona internamente en cada turno pero el texto de pensamiento se elimina del historial enviado en el siguiente turno.

### 2.2 Presupuesto de Llamadas (`max_tool_calls`)
- Gated vía decorador `@budget_gated`.
- Cuando quedan $\le 10$ llamadas (ej. llamada 30 con tope 40, o llamada 18 con tope 28), el arnés inyecta en la respuesta JSON:
  `"budget_warning": "Only X tool call(s) remaining (Y/Z used). Finalize your edits and call submit_patch soon."`
- **Efecto observado:** Las sesiones no resueltas que reciben este aviso suelen reaccionar haciendo su primera edición apresurada entre las llamadas 30 y 32, entregando parches incompletos o rotos. Las sesiones exitosas editan mucho antes (llamadas 5 a 9).

### 2.3 Tiempo por Comando (`timeout_seconds`)
- Controlado por subproceso en el contenedor: si un comando excede `timeout_seconds`, el subproceso es terminado con `SIGKILL` y devuelve `TimeoutExceeded` **sin abortar la sesión del agente**.
- **Descubrimiento crítico:** En el arnés oficial, el valor de `timeout_seconds` configurado en `eval_config.yaml` se aplicaba tanto a los comandos del agente como a la fase de verificación local (`verify_task`). Cuando se fijaba en 60s, **16 de 26 suites de test en ciertos repositorios eran interrumpidas por timeout antes de reportar el resultado**. Con 240s, las suites completan normalmente.

### 2.4 Tiempo de Sesión (`max_time_minutes`)
- Temporizador de pared (*wall-clock*) que mide exclusivamente el bucle del agente (la creación del contenedor y la extracción del snapshot no consumen este presupuesto).
- Si expira, la sesión termina inmediatamente con `timeout`. El arnés ejecuta el fallback de emergencia: corre `git add -N .` y `git diff HEAD`. Si hay modificaciones no vacías, se guarda el parche y se envía a verificación Fase 2. Si no hay cambios, la tarea queda no resuelta con parche vacío.

---

## 3. Dinámica del Agente: ¿Usa los Resultados o Solo Invoca?

El análisis de 4,246 llamadas del agente principal y 145 trazas completas demuestra patologías severas de política:

1. **Repeticiones Idénticas sin Avance:**
   - En la condición base sin instrucciones anti-repetición, **1,545 de 4,246 llamadas (36.4%) fueron repeticiones exactas de una llamada anterior sin que mediara una edición de código**.
   - 359 llamadas repitieron la misma petición rota de lectura de archivo tras recibir un error de schema o rango.
2. **Llamadas del Subagente:**
   - 198 llamadas ejecutadas por `code_analyzer_agent` en 7 sesiones no aportaron una sola solución. El agente principal delegaba al subagente, el subagente leía múltiples archivos sin editar nada, devolvía un resumen largo que consumía tokens de contexto, y el agente principal volvía a leer los mismos archivos.
3. **Búsqueda Semántica:**
   - Las llamadas a `search_similar_code` fueron puramente inerciales: tras recibir `[]`, el modelo volvía a intentar la misma búsqueda con pequeñas variaciones de palabras o se quedaba atascado en bucles.

---

## 4. Auditoría de Verificación Fase 2 (`Container B`)

1. **Parche Fallback Automático:**
   Si el agente no llama a `submit_patch()` explícitamente pero hizo cambios en `/workspace`, el arnés recupera el diff automáticamente (`git add -N . && git diff HEAD`). Esto salvó parches en múltiples sesiones que agotaron llamadas o tiempo.
2. **Anti-Tampering Restricciones:**
   Cualquier edición a archivos de prueba (`tests/`, `test_*.py`) o configuración (`conftest.py`, `pytest.ini`, `pyproject.toml`) es revertida con `git checkout HEAD` antes de correr la suite de verificación. El agente no puede "hacer pasar" la prueba modificando el test.
3. **Verificación Hermética:**
   La verificación requiere:
   - Código de salida `exit_code == 0` de `pytest`.
   - Reporte JUnit XML parseable con `passed_tests > 0`, `failures == 0`, `errors == 0`.
   - Que todos los tests de `FAIL_TO_PASS` y `PASS_TO_PASS` hayan sido ejecutados y superados.

---

## 5. Decisiones Inmediatas Derivadas de la Auditoría

1. **Eliminación Total de Herramientas de Grafo:** `search_similar_code`, `get_code_neighbors`, `get_code_subgraph` quedan totalmente prohibidas en la instrucción del sistema y removidas del flujo. La localización debe realizarse mediante `run_command` con `grep -rn "PATRON" --include="*.py" .` o inspección dirigida de archivos.
2. **Supresión del Subagente:** La arquitectura multi-agente se descarta; se adopta un único `LlmAgent` principal sin delegaciones.
3. **Ajuste de Presupuestos:**
   - `timeout_seconds`: Elevar a `240` segundos (permite correr suites de test completas y evita falsos timeouts).
   - `max_time_minutes`: `6.0` minutos por tarea (balance óptimo para no exceder las 12 horas globales en Kaggle con ~120 tareas).
   - `max_tool_calls`: Acotar a `28-35` llamadas (evita vagabundeo improductivo; si no hay edición temprana, más llamadas solo acumulan fallos).
