# Kaggle Gemma 4 Developer Agent · Especificaciones Técnicas Oficiales

Documento de referencia técnica verificado a partir de las páginas públicas oficiales de la competencia (descargadas vía API de Kaggle, guardadas localmente para lectura en `data/pages/`, ignoradas por git) y de la respuesta oficial de la API ([`docs/kaggle_api_2026-10-02.json`](kaggle_api_2026-10-02.json)).

Las menciones relativas al arnés interno se remiten por sección («`ver HARNESS § X.Y`») sin reproducir su texto protegido, en cumplimiento de la Sección 4 de las reglas de Kaggle (*Competition Data — Non-Redistribution*).

---

## 1. Fechas y Metadatos Oficiales

| Parámetro | Code Track (`id: 149921`) | Paper Track (`id: 163111`) | Fuente Pública Oficial |
|---|---|---|---|
| **Cierre de envíos** | **2026-12-02 23:59 UTC** | **2026-11-12 23:59 UTC** | `Timeline` (ambas pistas) |
| **Límite de envíos** | **1 envío por día** | **5 envíos por día** | `Evaluation` / `docs/kaggle_api_2026-10-02.json` |
| **Fusión de equipos** | **2026-11-25 23:59 UTC** | **2026-11-12 23:59 UTC** | `Timeline` (ambas pistas) |
| **Bolsa de premios** | **65 000 USD** | **35 000 USD** | `Prizes` (100 000 USD combinados) |
| **Requisito de entrada** | Aceptar reglas antes del 25-nov | Inscripción independiente requerida | `rules.md` / `Timeline` |

---

## 2. Entorno de Evaluación y Restricciones de Cómputo (Code Track)

### 2.1 Hardware y Aceleradores
* **Hardware de ejecución:** Máquinas con 4 × NVIDIA L4 (total 96 GB VRAM) (fuente: página pública `Upgraded Accelerators`).
* **Consumo de cuota:** Los notebooks de Kaggle configurados con aceleradores L4×4 consumen la cuota semanal de GPU al doble del ritmo estándar de T4×2/P100 (fuente: página pública `Upgraded Accelerators`).

### 2.2 Presupuesto y Tiempo de Ejecución
* **Límite de tiempo global:** El agente dispone de un límite máximo de **12 horas** para procesar y enviar parches para todas las tareas del conjunto de prueba, incluyendo el tiempo de preparación del sandbox, pero excluyendo la validación de parches (fuente: página pública `Evaluation`).
* **Presupuesto por tarea:** Puede configurarse opcionalmente en el archivo declarativo `eval_config.yaml` (fuente: página pública `Evaluation`; ver opciones en `HARNESS § 7.1`).

### 2.3 Conjunto de Prueba
* **Composición:** Aproximadamente **120 tareas** en el conjunto de prueba, divididas equitativamente entre los splits público y privado (fuente: página pública `Data`).
* **Naturaleza de los repositorios:** El conjunto de prueba fue curado a partir de un conjunto de **repositorios privados** (fuente: página pública `Data`). Las tareas del paquete público (`fastapi`, `rich`, `requests`, `httpx`) no corresponden a los repositorios con que se puntúa en la tabla de posiciones.

### 2.4 Restricciones de Modelo y Adaptadores
* **Modelo base obligatorio:** Debe seleccionarse estrictamente la variante de modelo [`gemma-4-31b-it-qat-w4a16-ct`](https://www.kaggle.com/models/google/gemma-4/other/gemma-4-31b-it-qat-w4a16-ct) para todos los agentes y subagentes (fuente: página pública `Model Selection, Budget, and Harness Rules`).
* **Adaptadores LoRA:** Se permite adjuntar adaptadores LoRA en formato `.safetensors`. Aunque el modelo base es único, se pueden asociar distintos adaptadores a diferentes agentes o subagentes (fuente: página pública `Model Selection, Budget, and Harness Rules`).

---

## 3. Paper Track: Reglas, Formato y Rúbrica (ID: 163111)

### 3.1 Formato de Entrega
* **Modalidad:** Kaggle Writeup de máximo **3 000 palabras** (fuente: página pública `Submission Requirements`).
* **Estructura requerida:** Título y subtítulo, Resumen (Abstract), Introducción, Métodos y Experimentos, Trabajo Relacionado y Citas (fuente: página pública `Submission Requirements`).
* **Independencia:** No se exige haber participado en el Code Track para presentar un trabajo en el Paper Track (fuente: página pública `Description`).

### 3.2 Criterios de Evaluación del Jurado
Las propuestas son evaluadas de forma promediada sobre cinco categorías con escala de 0 a 5 puntos (fuente: página pública `Evaluation`):
1. **Novelty (Novedad):** Originalidad técnica o conceptual del enfoque.
2. **Quality (Calidad):** Rigor metodológico y grado de generalización del método fuera de la competencia.
3. **Relevance (Relevancia):** Utilidad práctica y aplicabilidad en ingeniería de software autónoma.
4. **Verifiability (Verificabilidad):** Reproducibilidad del estudio, transparencia de los experimentos y solidez de las afirmaciones.
5. **Clarity (Claridad):** Precisión en la exposición, estructura del reporte y calidad de las figuras.

---

## 4. Referencias al Arnés de Evaluación (`swegemma`)

Para detalles sobre el funcionamiento interno del evaluador, consultar las secciones correspondientes de la documentación oficial de la competencia:
* **Estructura del envío (`submission.zip`):** Ver `HARNESS § 2.2`.
* **Clases de agente declarativo soportadas (`LlmAgent`, `SequentialAgent`, `ParallelAgent`, `LoopAgent`):** Ver `HARNESS § 2.3`.
* **Ciclo de vida en dos contenedores herméticos (Agente y Verificación):** Ver `HARNESS § 4.1` y `HARNESS § 4.2`.
* **Herramientas nativas de ejecución, archivos y grafos AST:** Ver `HARNESS § 6`.
* **Métrica de resolución de tareas y validación JUnit:** Ver `HARNESS § 8`.

---

## 5. Directrices de Diseño para Agents Learning Loops (ALL)

1. **Agnosticismo de Repositorio:** Dado que el conjunto de prueba oculta evalúa sobre repositorios privados (`Data`), el mecanismo de aprendizaje y consolidación de skills de ALL debe centrarse en patrones de diagnóstico agnósticos y heurísticas de grafo generales, evitando sobreajustar a convenciones particulares de los repositorios del split de entrenamiento.
2. **Presupuesto Operativo Acotado:** El techo global de 12 horas para ~120 tareas (`Evaluation`) impone una cota de aproximadamente 6 minutos por tarea en ejecución secuencial, lo que exige mecanismos rápidos de parada y recuperación selectiva en el grafo.
3. **Consistencia de Ciencia Abierta:** Todos los artefactos generados para el Paper Track deben ser reproducibles a partir de código versionado y manifiestos de datos con verificación criptográfica SHA-256.
