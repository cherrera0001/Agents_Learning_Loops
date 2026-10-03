# Apuntes sobre Circuit Breakers y Presupuesto por Tarea

Notas conceptuales preservadas tras la retirada del prototipo ejecutable no soportado por el compilador de
Kaggle.

---

## 1. Restricciones del Arnés Oficial (`swegemma`)

1. **Modelo único:** El submission no puede seleccionar modelos de diferente tamaño (2B, 9B, 27B); el arnés
   impone `gemma-4-31b-it-qat-w4a16-ct` de forma obligatoria (`HARNESS § 3.2`).
2. **Sin código Python ejecutable:** La evaluación de Kaggle corre exclusivamente mediante archivos YAML
   procesados por `adk-submission` (`HARNESS § 2.1`).
3. **Presupuestos nativos:** El arnés ya gestiona los presupuestos operativos por tarea (`HARNESS § 7`):
   * Tiempo máximo: 60 minutos
   * Límite de llamadas a herramientas: 100 llamadas
   * Turnos de razonamiento: 500 turnos
   * Configuración personalizable vía `eval_config.yaml` en la raíz de la submission.

---

## 2. Ideas para Futuras Intervenciones Declarativas

* **Circuit Breaker vía `eval_config.yaml`:**
  En lugar de implementar bucles en Python, se pueden acotar los presupuestos por tarea configurando
  `max_tool_calls` o timeouts en `eval_config.yaml` para evitar iteraciones infinitas o gasto inútil de tiempo
  en tareas atascadas.
* **Circuit Breaker en Prompts / Skills:**
  Incluir directivas explícitas de parada temprana en el prompt del sistema: si un archivo no puede ser
  modificado tras 3 intentos fallidos consecutivos con `edit_file`, invocar `submit_patch()` o abortar la
  edición en lugar de agotar las 100 llamadas a herramientas.
