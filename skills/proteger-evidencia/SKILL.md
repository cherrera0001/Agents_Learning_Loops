---
name: proteger-evidencia
description: No alterar la evidencia del Experimento 1 y respetar la frontera de fuga del solver acotado.
---

# Proteger la evidencia

> **Skill de entorno** ([glosario](../../docs/entorno/glosario.md), término 5). **No es un nodo Skill de
> la memoria**. Resume reglas del harness de experimento; no las redefine.

## Fuente

- [`evidence/README.md`](../../evidence/README.md): «Never hand-edit a receipt to fix a finding. Correct the
  code, retain the old evidence and run a new explicitly identified campaign.»
- [`specs/software_learning_protocol.md`](../../specs/software_learning_protocol.md), sección *Leakage
  boundary* (y *Execution and receipts* para los recibos).
- Episodio: ninguno registra esta regla como lección; su origen es el protocolo.

## Cuándo

Siempre que un cambio toque `evidence/`, `results/`, `benchmark/` o el solver acotado, y al revisar un PR
que presente conclusiones experimentales.

## Procedimiento

### Recibos

1. **No edites recibos a mano.** Los recibos de `evidence/` solo se añaden; su SHA-256 detecta cualquier
   alteración.
2. Si un recibo revela un defecto, **corrige el código**, conserva la evidencia antigua y **publica una
   campaña nueva** en un directorio nuevo e identificado.
3. Los agregados de `results/` se regeneran con `python -m experiments evaluate`; no se editan a mano.

### Frontera de fuga

El solver acotado recibe **solo** la tarea pública, el código fuente actual de la aplicación y las
lecciones elegibles para su condición. **Nunca** recibe:

- `benchmark/private/` (etiquetas causales, pares, inyecciones);
- causas ocultas (`hidden_cause_id`), tareas futuras ni resultados de otras condiciones;
- la receta de mutación ni parches dorados;
- el checkout completo del repositorio.

Esta frontera la hace cumplir el harness de experimento. No es un sandbox del sistema operativo:
cualquier adaptador de modelo no confiable requiere antes aislamiento de proceso
([`docs/entorno/harness.md`](../../docs/entorno/harness.md), sección 2).
