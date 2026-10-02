# Borradores Exploratorios (Sin Condición Asignada)

Este directorio contiene configuraciones y directivas preliminares escritas durante la fase inicial de exploración del concurso.
**Ningún archivo de este directorio está asignado a las condiciones formales del experimento (A, B, C, D) ni forma parte de una submission oficial.**

---

## 1. Naturaleza de los Archivos

### `agent.yaml`
* **Estado:** Borrador exploratorio de configuración declarativa para `adk-submission`.
* **Propósito:** Plantilla de trabajo para explorar los límites de tokens (`max_output_tokens: 16384`, `thinking_budget: 4096`) y la sintaxis de herramientas nativas de `swegemma`.
* **Aclaración de gobernanza:** No utiliza ni referencia skills consolidadas inexistentes. La condición A oficial está aislada en `conditions/a_kit/`.

### `skills/all_core/SKILL.md`
* **Estado:** Borrador de instrucciones redactado a mano.
* **No es una skill consolidada:** En este repositorio aún no se ha ejecutado minería offline sobre las tareas de entrenamiento; por tanto, no existen episodios consolidados que respalden estas directrices.
* **No es un placebo:** Un placebo experimental (Condición B) requiere ser un texto neutral redactado con una longitud de tokens equivalente a la Condición C una vez que C esté congelada, y sin adelantar intervenciones de anclaje estructural (las cuales pertenecen a la hipótesis D). Este archivo se conserva exclusivamente como apunte conceptual preliminar.
