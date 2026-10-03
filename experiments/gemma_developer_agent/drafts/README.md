# Borradores Exploratorios (Sin Condición Asignada)

> **Nota de estado.** Catálogo vigente de los borradores, pero varios de ellos están superados: ver el
> [mapa de documentos](../README.md#12-mapa-de-documentos). Sobre B, las tres definiciones que circulan (la
> de este catálogo, la del borrador de pre-registro y la del issue #104) no coinciden: la que vale es la del
> [pre-registro de la campaña](../../../docs/preregistration/kaggle-campaign-abcd.md).

Este directorio contiene configuraciones, directivas y textos preliminares escritos durante la fase inicial
de exploración del concurso.
**Ningún archivo de este directorio está asignado a las condiciones formales del experimento (A, B, C, D)
ni forma parte de una submission oficial.**

---

## 1. Naturaleza de los Archivos

### `agent.yaml`
* **Estado:** Borrador exploratorio de configuración declarativa para `adk-submission`.
* **Propósito:** Plantilla de trabajo para explorar límites de tokens y herramientas nativas de `swegemma`.
* **Aclaración:** No utiliza ni referencia skills consolidadas inexistentes. La condición A oficial está
  aislada en `conditions/a_kit/`.

### `skills/all_core/SKILL.md`
* **Estado:** Borrador de instrucciones redactado a mano.
* **No es una skill consolidada:** En este repositorio aún no se ha ejecutado minería offline sobre las tareas
  de entrenamiento; por tanto, no existen episodios consolidados que respalden estas directrices.
* **No es un placebo:** Un placebo experimental (Condición B) requiere ser un texto neutral redactado con una
  longitud de tokens equivalente a la Condición C una vez que C esté congelada, y sin adelantar intervenciones
  de anclaje estructural (las cuales pertenecen a la hipótesis D).

### `preregistration_abcd.md`
* **Estado:** Borrador para #104 y #105, sin revisar.
* **Propósito:** Documento preliminar de diseño experimental A/B/C/D a formalizar en issues posteriores.

### `paper/manuscript_draft.md`
* **Estado:** Borrador para #104 y #105, sin revisar.
* **Propósito:** Borrador inicial de manuscrito académico para el Paper Track, pendiente de revisión tras la
  ejecución de los experimentos.

### `NOTES_DISYUNTOR_Y_PRESUPUESTO.md`
* **Estado:** Apuntes conceptuales sobre circuit breakers y presupuestos por tarea.

### `architecture_explainer.html`
* **Estado:** Diagrama de intención, nada de esto está implementado ni medido.
* **Propósito:** Documento visual exploratorio generado para ilustrar conceptos arquitectónicos teóricos.

