# Harness

Este repositorio usa dos harness distintos ([glosario](glosario.md), términos 6 y 7). Se describen por
separado y no se mezclan.

## 1. Harness de entorno

Es el contrato de quien edita el repositorio, es decir, de cualquier [agente de entorno](agentes.md).
Define qué puede leer, qué puede escribir, cuándo se detiene y qué evidencia deja.

### Lectura

Puede leer todo el repositorio. Excepción de rol: solo el **evaluador del experimento** usa
`benchmark/private/` para evaluar ([`agentes.md`](agentes.md)). La frontera que protege al solver acotado
es la del harness de experimento (sección 2).

### Escritura

| Permitido | Nunca |
|---|---|
| El código y la documentación que la tarea requiere | Editar a mano recibos existentes de `evidence/` |
| Tests nuevos, con su control o su mutación | Reescribir `results/` a mano: se generan con `python -m experiments evaluate` |
| Un episodio nuevo en `learning/episodes/` | Editar `learning/dev_memory.json` a mano: se regenera con `rebuild` |
| Una campaña nueva, en un directorio nuevo e identificado | Sobrescribir una campaña publicada |

Si un recibo revela un defecto, se corrige el código, se conserva la evidencia antigua y se ejecuta una
campaña nueva identificada ([`evidence/README.md`](../../evidence/README.md)).

### Parada

Una entrega está lista para PR cuando pasan los tests y las comprobaciones de
[`CONTRIBUTING.md`](../../CONTRIBUTING.md). No se hace merge con CI en rojo ni pendiente.

### Evidencia que deja

- Un episodio en `learning/episodes/` con los fallos tal como ocurrieron, atribuidos a la acción que los causó.
- El resultado de las comprobaciones (tests y CI) en el PR.

### Flujo

Es el flujo ya documentado en [`CONTRIBUTING.md`](../../CONTRIBUTING.md) y
[`learning/README.md`](../../learning/README.md):

```mermaid
flowchart LR
    R["recall<br/>devlog recall"] --> B["rama<br/>issue-&lt;n&gt;-&lt;tema&gt;"]
    B --> I["implementar<br/>+ tests"]
    I --> E["episodio<br/>learning/episodes/"]
    E --> RB["rebuild<br/>devlog rebuild"]
    RB --> PR["PR con<br/>Closes #&lt;n&gt;"]
    PR --> M["merge verificado<br/>por mergedAt"]
```

1. `python -m scripts.devlog recall "<título del issue>"`.
2. Rama `issue-<n>-<tema>`.
3. Implementar con tests.
4. Registrar el episodio `learning/episodes/NNN-issue-<n>.json`.
5. `python -m scripts.devlog rebuild`.
6. PR con `Closes #<n>`, y merge **verificado** por `mergedAt` antes de mover la tarjeta a *Done*.

## 2. Harness de experimento

Es el controlador del Experimento 1 que ejecuta al [solver acotado](glosario.md). Esta sección lo resume
y enlaza; la definición canónica es [`specs/software_learning_protocol.md`](../../specs/software_learning_protocol.md).

| Aspecto | Resumen | Sección del protocolo |
|---|---|---|
| Qué recibe el solver | Solo la tarea pública (`PublicTask`), el código fuente actual de la aplicación y las lecciones elegibles para la condición | *Leakage boundary* |
| Qué queda fuera | `hidden_cause_id`, tareas futuras, la receta de mutación, parches dorados, etiquetas de relevancia, resultados de otras condiciones y el checkout completo del repositorio | *Leakage boundary* |
| Workspace | Copia de la aplicación, de los tests de negocio y solo del test de aceptación de la tarea actual; ediciones limitadas a archivos existentes de la aplicación; tests protegidos; solo variables de entorno permitidas | *Leakage boundary* |
| Fases | `ISSUE → RETRIEVE → INSPECT → HYPOTHESIZE → CHANGE → TEST → OBSERVE`, y después `DIAGNOSE → REFLECT → CONSOLIDATE` | *Execution and receipts* |
| Recibos | Solo se añaden: publicación atómica sin sobrescritura y SHA-256, que detecta alteraciones pero no es una firma | *Execution and receipts* |
| Normalización | Recibos v2 con `source_hash_normalization: "lf/v1"`; los v1 se leen como `checkout-bytes/v0` | *Source hash normalization* |

El harness de experimento **no es un sandbox del sistema operativo**. El protocolo exige aislamiento de
proceso o de contenedor, de red y de sistema de archivos antes de usar un adaptador de modelo no confiable.
