# Variante navegación-primero de la condición 7 (WIP — NO subir, NO correr)

Paquete gemelo de [`../replicas_c7`](../replicas_c7) con **un único cambio trazable**:
`prompts/system.md` integra el procedimiento de navegación del dueño (extraer identificadores →
`search_similar_code` con varias palabras → `get_code_neighbors` → leer → editar el mejor
candidato). Todo lo demás —ruedas del arnés y su guarda SHA-256, `eval_config.yaml`, muestreo,
las 20 tareas, topes, cortes de seguridad— es byte a byte el de la condición 7.

| | condición 7 (réplicas) | variante navegación |
|---|---|---|
| huella de configuración | `0f52de0b84cb` | **`af8cca829561`** |
| kernel (si se sube) | `cs4all/c7-replica-condicion-7` | `cs4all/c7-navegacion-condicion-7` |

## Qué hay aquí

| Archivo | Rol |
|---|---|
| `notebook_c7_nav.py` | Guion del notebook (fuente de verdad). Copia de `replicas_c7/notebook_c7.py`: la celda «kit» además sobrescribe `prompts/system.md` con `_SYSTEM_NAV` y la guarda exige la huella nueva. |
| `armar_notebook_nav.py` | Genera `notebook_c7_nav.ipynb` + `kernel-metadata.json`. Antes escribe nada, verifica que `_SYSTEM_NAV` == `kit_nav/prompts/system.md` (byte a byte), monta el kit de referencia desde la descarga local de réplica 1 (gitignored) sin `adapters/` con el `system.md` de navegación, y exige que la huella recomputada == `HUELLA_NAV`. Sale 2 si no. |
| `kit_nav/prompts/system.md` | Único archivo del kit que se versiona: el bloque de instrucciones con el procedimiento de navegación (texto nuestro). Los otros 5 archivos del kit no se versionan —los tres de plantilla son contenido de la competencia, y `eval_config.yaml`/`sampling.yaml` ya van como literales en la celda «kit»—; en Kaggle el kit se reconstruye desde `sample_submission` igual que en la condición 7. |
| `huella_nav.txt` | Registro: huella original ↔ huella variante. |

## Estado

WIP commiteado el 2026-10-16. **No se ha subido ni corrido nada.** El contraste previsto (misma
sesión, mismas 20 tareas): condición 7 (`replicas_c7`) vs esta variante, tras el reinicio de la
cuota GPU. La decisión de correrla la toma el dueño.

## Cómo se construyó (trazabilidad)

1. Kit base = `data/replicas_c7/replica_1/c7_submission` tal como se bajó de Kaggle, **menos
   `adapters/`** (el notebook lo quita antes de medir; verificado: sin adapters la huella local
   reproduce `0f52de0b84cb` exacta).
2. Inserción única en `prompts/system.md`: sección «Navigation-First Procedure (mandatory,
   before any edit)» entre el Core Objective y `## Workflow`. El resto del prompt es idéntico.
3. Huella nueva calculada con la fórmula del manuscrito (SHA-256 de los base64 de los 6
   archivos, ordenados y concatenados, 12 hex): `af8cca829561`.
