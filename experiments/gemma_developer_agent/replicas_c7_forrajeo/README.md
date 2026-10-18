# Variante FORRAJEO (Project WORM) de la condición 7 (WIP — NO subir, NO correr)

Paquete gemelo de [`../replicas_c7`](../replicas_c7) con **un único cambio trazable**:
`prompts/system.md` integra la «Foraging Policy» (298 palabras): búsqueda local primero con
escalada temporalizada a búsqueda global, reorientación tras estancamiento (pirueta), modos
dwelling/roaming, habituación a fallo repetido y cierre de lazo actuar. Los cinco principios y su
fuente biológica están en [`../docs/c7_gusano_mapping.md`](../docs/c7_gusano_mapping.md)
(extracción de `reports/Investigación en gusanos autónomos.md`, del dueño). Todo lo demás —ruedas
del arnés y su guarda SHA-256, `eval_config.yaml`, muestreo, las 20 tareas, topes, cortes de
seguridad, fix de `clase_fallo`— es byte a byte el de la condición 7.

| | condición 7 (réplicas) | variante forrajeo |
|---|---|---|
| huella de configuración | `0f52de0b84cb` | **`fb8175c0e74e`** |
| kernel (si se sube) | `cs4all/c7-replica-condicion-7` | `cs4all/c7-forrajeo-condicion-7` |

## Qué hay aquí

| Archivo | Rol |
|---|---|
| `notebook_c7_forrajeo.py` | Guion del notebook (fuente de verdad). Copia de `replicas_c7/notebook_c7.py`: la celda «kit» además sobrescribe `prompts/system.md` con `_SYSTEM_FORRAJEO` y la guarda exige la huella nueva. |
| `armar_notebook_forrajeo.py` | Genera `notebook_c7_forrajeo.ipynb` + `kernel-metadata.json`. Antes de escribir nada, verifica que `_SYSTEM_FORRAJEO` == `kit_forrajeo/prompts/system.md` (byte a byte), monta el kit de referencia desde la descarga local de réplica 1 (gitignored) sin `adapters/` con el `system.md` de forrajeo, y exige que la huella recomputada == `HUELLA_FORRAJEO`. Sale 2 si no. |
| `kit_forrajeo/prompts/system.md` | Único archivo del kit que se versiona: el bloque de instrucciones con la Foraging Policy insertada (texto nuestro; la inserción es única y el resto del prompt es idéntico al base). Los otros 5 archivos del kit no se versionan —los tres de plantilla son contenido de la competencia, y `eval_config.yaml`/`sampling.yaml` ya van como literales en la celda «kit»—; en Kaggle el kit se reconstruye desde `sample_submission` igual que en la condición 7. |
| `huella_forrajeo.txt` | Registro: huella original ↔ huella variante. |

## Estado

WIP construido el 2026-10-17. **No se ha subido ni corrido nada.** El contraste previsto (misma
sesión, mismas 20 tareas): condición 7 (`replicas_c7`) vs esta variante y las otras tres, tras el
reinicio de la cuota GPU. La decisión de correrla la toma el dueño.

## Cómo se construyó (trazabilidad)

1. Kit base = `data/replicas_c7/replica_1/c7_submission` tal como se bajó de Kaggle, **menos
   `adapters/`** (el notebook lo quita antes de medir; verificado: sin adapters la huella local
   reproduce `0f52de0b84cb` exacta).
2. Inserción única en `prompts/system.md`: sección «Foraging Policy (mandatory search
   discipline)» entre el Core Objective y `## Workflow`, con cada principio etiquetado en un
   comentario HTML con su fuente biológica (dwelling/escalation/pirueta/habituación/actuar). El
   resto del prompt es idéntico.
3. Huella nueva calculada con la fórmula del manuscrito (SHA-256 de los base64 de los 6
   archivos, ordenados y concatenados, 12 hex): `fb8175c0e74e`.
4. `notebook_c7_forrajeo.py` y `armar_notebook_forrajeo.py` derivados mecánicamente de los de la
   variante navegación (misma disciplina de frontera: nada de contenido de la competencia se
   versiona fuera del texto nuestro).
