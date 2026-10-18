# Variante R1-FIEL (thinking-off real + tiempo reinvertido) — sexto brazo propuesto (WIP — NO subir, NO correr)

Sexto brazo propuesto por el concilio C7 Fase 4 (2026-10-17, vuelta 49 / concilio 51; bitácora
[`../docs/c7_concilio_2026-10-17.md`](../docs/c7_concilio_2026-10-17.md)) para medir la
recomendación #1 del análisis crítico **fielmente**. Hallazgo del concilio: el brazo thinking
(`9d0db7b946e7`) solo *oculta* los pensamientos (`include_thoughts:false` con
`thinking_budget:1024` — el modelo sigue razonando y quemando reloj); apagar de verdad exige
`thinking_budget:0` (verificado en el código del compilador; el validador inyecta budget=max si
falta). **REESPECIFICADO el 2026-10-18 a 5.0 min** (antes 6.0): una regla atribuida al equipo de
Google en los foros («~5,5 min/tarea incl. setup; even 6 min cap is out of reach») no pudo
verificarse desde el repo (muro de cookies), y ante la duda 5.0 es seguro bajo cualquiera de los
dos muros, está probado en producción (sub-019) y convierte al brazo en un A/B limpio contra
sub-019@5.0 que aísla solo `thinking_budget: 0`. El envelope de 12 h sobra a 5.0 (562-698 min).

Dos deltas **puros de configuración** respecto a la condición 7 (`0f52de0b84cb`):

- **(a) Config**: `configs/sampling.yaml` con `thinking_budget: 0` (el resto idéntico a la
  condición 7, incluido `include_thoughts: true`; con presupuesto 0 no hay pensamientos que
  mostrar u ocultar).
- **(b) Muro**: `eval_config.yaml` con `max_time_minutes: 5.0` (la condición 7 usa 4.5; sub-019 probó 5.0).
- **Prompt sin tocar**: byte-identico al `prompts/system.md` de la condición 7 — el armar lo
  verifica contra la descarga de réplica 1.

| | condición 7 (réplicas) | brazo R1-fiel |
|---|---|---|
| huella de configuración | `0f52de0b84cb` | **`5e1638518420`** |
| kernel (si se sube) | `cs4all/c7-replica-condicion-7` | `cs4all/c7-r1fiel-condicion-7` |

## Qué hay aquí

| Archivo | Rol |
|---|---|
| `notebook_c7_r1fiel.py` | Guion del notebook (fuente de verdad). Copia de `replicas_c7_thinking/notebook_c7_thinking.py`: la celda «kit» escribe `_SAMPLING_R1FIEL` y el `eval_config` con 5.0 min; el prompt queda como el de la condición 7; la guarda exige `HUELLA_R1FIEL`. |
| `armar_notebook_r1fiel.py` | Genera `notebook_c7_r1fiel.ipynb` + `kernel-metadata.json`. Verifica el literal `_SYSTEM_R1FIEL` contra el `prompts/system.md` de la descarga de réplica 1, `_SAMPLING_R1FIEL` contra su constante, la presencia de los dos deltas en el guion, monta el kit de huella (descarga sin `adapters/` + sampling y eval_config de la variante) y exige huella == `HUELLA_R1FIEL`. |
| `huella_r1fiel.txt` | Registro: huella condición 7 ↔ huella R1-fiel y los dos deltas. |

## Verificación (2026-10-17, todo en local, 0 GPU)

- Armar re-ejecutado 5 veces tras la reespecificación: huella estable `5e1638518420` (la huella 3a28671c4f60 del valor 6.0 queda obsoleta, no referenciada en ningún envío).
- Preflight 24/24 «Se puede subir» (`scripts.kaggle_preflight comprobar … --ruedas …`).
- Comparación archivo-a-archivo contra el kit de la condición 7: los únicos diffs son
  `configs/sampling.yaml` (solo `thinking_budget: 4096 → 0`) y `eval_config.yaml` (solo
  `max_time_minutes: 4.5 → 5.0`; la cifra 6.0 fue la del diseño inicial); prompt byte-identico.
- **Corrección 2026-10-18 (sesión de cierre, verificada por sha256)**: el prompt de la condición 7
  (`replica_1/c7_submission/prompts/system.md`, sha `f1cbf794…`) es idéntico al de `i_razona`
  (0.08/0.13/0.13) y **distinto** al de `nav_kit_v2` / sub-019 (sha `f5bd1995…`). Por tanto este
  brazo **NO es un A/B limpio contra sub-019**: respecto a sub-019 difiere en prompt (cond. 7 vs
  navegación) y en `thinking_budget`; respecto a `i_razona` difiere en `thinking_budget` y en
  `max_time_minutes` (4.5 → 5.0). El único A/B limpio que ofrece es contra una condición 7 a 5.0 min
  con thinking 4096, que no existe en el LB. La afirmación «aísla solo thinking_budget» de los
  párrafos anteriores queda retirada; la predicción sellada de un envío de este brazo debe
  declararse como comparación de familia (cond. 7), no como A/B.
- `ruff check`/`format` limpios; mypy con los dos avisos heredados del patrón thinking.

## Estado

Construido el 2026-10-17. **No se ha subido ni corrido nada.** Correrlo es decisión del dueño
(STATUS §Lunes addendum 7c: tras réplicas 2-3 y gold-patch, y reconciliando cuota con la reserva
del concilio 50; el kernel se lanzaría como
`kaggle kernels push -p experiments/gemma_developer_agent/replicas_c7_r1fiel -t 9000 --accelerator NvidiaL4`).
