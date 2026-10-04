# Borrador de Pre-registro · Experimento Kaggle Gemma 4 (Diseño A/B/C/D)

> **Borrador del 2026-10-02. Superado en parte por el
> [pre-registro de la línea base A](../../../docs/preregistration/kaggle-baseline-a.md) y por el issue #104.**
> No se reescribe. Está superado en: los 60 minutos por tarea (valor por defecto del arnés, no una regla);
> el «split estratificado» (la regla es reservar un repositorio); que A no tenga «anclaje» (el kit ya
> declara las herramientas de grafo); y las definiciones de B y D, que el issue #104 fija de otro modo. El
> pre-registro de la campaña está en `docs/preregistration/kaggle-campaign-abcd.md`, y las hipótesis de este borrador no son refutables ni
> están pre-registradas. Las tareas no son «SWE-bench»: son el conjunto propio de la competencia. La línea
> «No commiteado» de abajo es falsa: el borrador está en el repositorio. Mapa de documentos: [`../README.md`](../README.md#12-mapa-de-documentos).

**Estado:** BORRADOR INCOMPLETO (No commiteado; pendiente de partición exacta por `instance_id`, hardware de cómputo y calibración de ruido).  
**Fecha:** 2026-10-02.  
**Tareas públicas disponibles:** 129 tareas en `data/tasks.jsonl` (fastapi: 67, rich: 48, requests: 13, httpx: 1).  
**Arnés oficial:** `swegemma` / `adk-submission` con `gemma-4-31b-it-qat-w4a16-ct`. Presupuesto por tarea: 60 min, 100 tool calls.  

> [!CAUTION]
> Este documento NO es un pre-registro formal hasta que esté asociado a un issue con talla, defina la partición exacta de las 129 tareas (entrenamiento vs prueba), especifique la máquina de ejecución y el presupuesto de horas, y se congele en un commit anterior a cualquier corrida de datos.

---

## 1. Pregunta de Investigación

¿La consolidación fuera de línea de experiencias de reparación en skills declarativas (`SKILL.md`) mejora la tasa de resolución (*Resolution Rate*) de un agente Gemma 4 en tareas SWE-bench inéditas, y puede un anclaje estructural sobre el grafo AST del repositorio (H8) neutralizar la transferencia negativa ante tareas con señuelos léxicos (H4)?

---

## 2. Condiciones Experimentales

Se evalúan 4 condiciones cerradas sobre un split de prueba idéntico:

| Condición | Descripción del Agente | Configuración de Skills | Anclaje de Recuperación |
|---|---|---|---|
| **A · Línea Base** | Starter kit oficial (`gemma-4-31b-it-qat-w4a16-ct`) con prompt estándar | Sin skills (`skills: []`) | Ninguno (cero memoria previa) |
| **B · Placebo** | Mismo agente base | Skills escritas a mano por un desarrollador sin experiencia empírica de ejecución | Léxico (texto del issue) |
| **C · ALL Offline** | Mismo agente base | Skills consolidadas automáticamente por ALL a partir de episodios de entrenamiento ($\ge 3$ éxitos independientes) | Léxico (texto del issue) |
| **D · ALL + H8** | Mismo agente base | Mismas skills consolidadas por ALL | Estructural: Grafo AST (`get_code_neighbors`) + Traza de excepción |

---

## 3. Partición de Datos y Frontera de Fuga

* **Conjunto de Entrenamiento (Offline Learning Split):** Tareas del benchmark público SWE-bench seleccionadas para la minería de lecciones. Ninguna tarea de este conjunto formará parte de la prueba.
* **Conjunto de Evaluación (Test Split):** Tareas inéditas evaluadas en `swegemma`. Incluye:
  1. *Tareas Estándar:* Defectos directos de librerías.
  2. *Tareas Señuelo (Decoys):* Enunciados redactados con palabras clave que sugieren un subsistema conocido pero cuya causa raíz es ajena (prueba de falsación de H4).
* **Frontera de Fuga:** Las skills de C y D se compilan exclusivamente a partir de recibos de entrenamiento. Ningún archivo de `test_patch` ni traza de evaluación interviene en la compilación de skills.

---

## 4. Métricas Pre-registradas

1. **Métrica Primaria:**
   * **`ResolutionRate` (RR):** Proporción de tareas con estado resuelto (`PASS`) verificado por JUnit XML (`exit_code == 0`).
2. **Métricas Secundarias:**
   * **`MeanToolCalls`:** Promedio de llamadas a herramientas consumidas por tarea resuelta (eficiencia de presupuesto).
   * **`NegativeTransferRate` (NTR):** Fracción de tareas señuelo donde la presencia de skills empeora la decisión inicial o induce a un fallo no observado en la línea base A.
   * **`TimePerResolvedTask`:** Minutos de ejecución por tarea con resolución exitosa.

---

## 5. Reglas de Decisión Falsables

* **H_Kaggle_1 (Beneficio de Skills Consolidadas en Tareas Estándar):**
  * *Apoyada* si $RR(C) - RR(A) \ge 0.10$ con un ahorro de tool calls $\ge 15\%$.
  * *Refutada* si $RR(C) \le RR(A)$.
* **H_Kaggle_2 (Efecto Placebo):**
  * *Apoyada* si $RR(C) > RR(B)$, confirmando que la experiencia empírica supera al texto redactado a priori.
* **H_Kaggle_3 (Superación de la Transferencia Negativa vía H8 en Señuelos):**
  * *Apoyada* si en las tareas señuelo:
    $$RR(D) > RR(C) \quad \text{y} \quad NTR(D) < NTR(C)$$
  * *Refutada* si $RR(D) \le RR(C)$ ante señuelos.

---

## 6. Predicción Registrada del Orquestador

Siguiendo el principio de ALL de registrar la predicción antes de ver los datos:
* **Predicción en Tareas Estándar:** Se espera una diferencia pequeña o nula entre A y C ($RR(C) \approx RR(A)$), debido a que la experiencia transfiere poco entre tareas de un mismo proyecto (confirmando los hallazgos de H4 y H7 en Task Ledger).
* **Predicción en Tareas Señuelo:** Se predice que C sufrirá transferencia negativa frente a A (reproduciendo H4), mientras que D obtendrá una ventaja moderada gracias a que `get_code_neighbors` ancla la búsqueda en la topología real del código y no en las palabras del issue.
