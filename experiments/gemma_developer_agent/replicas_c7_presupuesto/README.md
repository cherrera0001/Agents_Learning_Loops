# Variante conciencia-de-presupuesto de la condición 7 (WIP — NO subir, NO correr)

Segunda variante de instrucciones sobre el paquete [`../replicas_c7`](../replicas_c7), gemela en
disciplina de [`../replicas_c7_nav`](../replicas_c7_nav): **un único cambio trazable** en
`prompts/system.md` — una sección «Budget Awareness» con reglas de gasto del presupuesto
(tope de exploración a un tercio, nunca repetir una llamada idéntica, verificar una vez,
re-intento único ante lecturas que ignoran el rango, final: submit con lo que haya).

**Motivación medida** (no estética): la minería de réplica 1
([`../docs/c7_fallos_r1.md`](../docs/c7_fallos_r1.md)) encontró que 12 de los 16 fallos
`sin_parche` murieron contra el muro de 4,5 minutos (10 sin editar, 2 con ediciones nunca
enviadas) y que las herramientas de búsqueda no se usaron en ninguna — el cuello de botella es
convertir la ubicación en un edit dentro del presupuesto, no la búsqueda. Cada regla de la
sección responde a un patrón contado allí.

| | condición 7 (réplicas) | variante presupuesto |
|---|---|---|
| huella de configuración | `0f52de0b84cb` | **`52ba08ceac25`** |
| kernel (si se sube) | `cs4all/c7-replica-condicion-7` | `cs4all/c7-presupuesto-condicion-7` |

## Qué hay aquí

| Archivo | Rol |
|---|---|
| `notebook_c7_presupuesto.py` | Guion del notebook (fuente de verdad). Copia de `replicas_c7/notebook_c7.py`: la celda «kit» sobrescribe `prompts/system.md` con `_SYSTEM_PRES` y la guarda exige la huella nueva. |
| `armar_notebook_presupuesto.py` | Genera `notebook_c7_presupuesto.ipynb` + `kernel-metadata.json`. Verifica `_SYSTEM_PRES` == `kit_presupuesto/prompts/system.md` (byte a byte), monta el kit de huella desde la descarga local de réplica 1 sin `adapters/` y exige huella == `HUELLA_PRES`. |
| `kit_presupuesto/prompts/system.md` | Único archivo del kit versionado (texto nuestro); mismas 20 tareas, mismos topes. |
| `huella_presupuesto.txt` | Registro: huella original ↔ huella variante. |

## Estado

WIP commiteado el 2026-10-16. **No se ha subido ni corrido nada.** Contraste previsto tras el
reinicio de cuota GPU: condición 7 vs navegación-primero vs presupuesto, mismas 20 tareas.
La decisión de correrlas la toma el dueño.
