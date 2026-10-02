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
    ES["ESTIMAR<br/>orquestador"] --> IP["In Progress"]
    IP --> R["recall<br/>devlog recall"]
    R --> B["rama<br/>issue-&lt;n&gt;-&lt;tema&gt;"]
    B --> I["implementar<br/>+ tests"]
    I --> PR["PR con<br/>Closes #&lt;n&gt;"]
    PR --> E["episodio<br/>learning/episodes/"]
    E --> RB["rebuild<br/>devlog rebuild"]
    RB --> RV["REVISAR<br/>revisor independiente"]
    RV --> M["merge del orquestador<br/>verificado por mergedAt"]
    M --> CF["CONFIRMAR<br/>criterio de cierre"]
    CF --> D["Done"]
```

1. ESTIMAR (orquestador): «Estimación v1» en el issue y campos del Project #5.
2. In Progress (implementador).
3. `python -m scripts.devlog recall "<título del issue>"`.
4. Rama `issue-<n>-<tema>`; implementar con tests y abrir el PR.
5. Registrar el episodio `learning/episodes/NNN-issue-<n>.json` (con `estimate` y `outcome`).
6. `python -m scripts.devlog rebuild`.
7. REVISAR: el orquestador encarga la revisión a un revisor independiente ([roles](agentes.md#revisor)) y,
   con su informe y el CI en verde, hace el merge **verificado** por `mergedAt`. Después, CONFIRMAR:
   comprueba el criterio de cierre de la tabla siguiente y registra *Verificación*, *Modelo usado* y
   *Escaló*.
8. *Done* no es el cierre confirmado: la automatización del tablero ya pone la tarjeta en *Done* al mergear
   un PR con `Closes`. El cierre confirmado es *Verificación* = *Verificada*, y CONFIRMAR termina con
   `python -m scripts.devlog board --since <n>` sin hallazgos.

El texto canónico, los responsables y las reglas del registro están en
[`CONTRIBUTING.md`](../../CONTRIBUTING.md#flujo-por-issue-la-vida-del-proyecto).

### Criterios de cierre por tipo de trabajo

Cada issue declara su *Tipo de cierre* y su *Evidencia requerida* en la plantilla
([`issue.md`](../../.github/ISSUE_TEMPLATE/issue.md)). *Verificación* = *Verificada* solo cuando el criterio
de su tipo se cumple y la evidencia está enlazada en el issue.

| Tipo de trabajo | Criterio de cierre | Evidencia que se enlaza |
|---|---|---|
| Código | PR mergeado (`mergedAt`) y CI verde en main | PR y ejecución de CI en main |
| Experimento | Recibos, verificación independiente y lectura publicada | Recibos de `evidence/`, verificación hecha por un medio distinto del agente que ejecutó, y la lectura en `docs/` |
| Docs | PR mergeado (`mergedAt`) y CI verde en main | PR y ejecución de CI en main |
| Sistema externo | Observación en el sistema real, con comando y fecha | Comando, salida y fecha de la observación |

En un issue de **sistema externo**, mientras falte la observación el issue sigue abierto, el PR usa
`Refs #<n>` y no `Closes #<n>`, y *Verificación* = *Pendiente* ([rol Cierre](agentes.md#cierre)).

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
