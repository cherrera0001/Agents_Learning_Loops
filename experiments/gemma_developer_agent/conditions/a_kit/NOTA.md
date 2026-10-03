# Nota Técnica sobre Presupuestos de Ejecución · Condición A

Este documento describe los presupuestos operativos definidos en `eval_config.yaml` dentro de la Condición A
(`conditions/a_kit/`), réplica exacta del starter kit oficial provisto por Kaggle (`sample_submission/`).

---

## 1. Presupuesto de Ejemplo del Kit Oficial (`eval_config.yaml`)

El archivo `eval_config.yaml` del kit declara:
* `max_time_minutes: 1` (1 minuto de tiempo total por tarea)
* `max_tool_calls: 10` (máximo 10 llamadas a herramientas)
* `max_turns: 50` (50 turnos de interacción)
* `timeout_seconds: 60` (60 segundos por comando bash)

### Diagnóstico
Tal como documenta `HARNESS § 7.1`, estos valores corresponden a una **configuración de prueba mínima**
(smoke test) para verificar la tubería de ejecución del arnés en pocos segundos. Con un tope de 1 minuto y
10 llamadas, un modelo de 31B parámetros difícilmente podrá leer el código, reproducir el fallo con pytest,
editar los archivos y verificar la solución, resultando en una tasa de resolución artificialmente cercana a 0.

---

## 2. Presupuesto Real de Evaluación Oficial (`HARNESS § 7`)

El arnés `swegemma` establece por defecto para la evaluación oficial:
* Tiempo de sesión: **60 minutos**
* Llamadas a herramientas: **100 llamadas**
* Turnos de razonamiento: **500 turnos**
* Timeout por comando individual: **300 segundos**

---

## 3. Propuesta para la Línea Base de #103 (Decide el Orquestador)

Para el diseño experimental formal en #103, se presentan dos alternativas:

* **Alternativa 1 (Presupuesto Oficial Completo - Recomendada):**
  Eliminar `eval_config.yaml` o configurarlo con los topes oficiales (60 min, 100 tool calls, 300 s).
  * *Justificación:* Permite medir el desempeño genuino de Gemma 4 frente a los defectos reales de SWE-bench
    sin que el corte prematuro oculte el comportamiento del agente.
* **Alternativa 2 (Presupuesto Intermedio Acotado):**
  Fijar `max_time_minutes: 15`, `max_tool_calls: 30`, `timeout_seconds: 120`.
  * *Justificación:* Ahorra cómputo GPU en experimentos preliminares locales, aunque subestima la tasa de
    resolución final frente a la evaluación oficial.
