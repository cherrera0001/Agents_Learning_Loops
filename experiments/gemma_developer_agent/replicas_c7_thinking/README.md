# Variante thinking (razonamiento breve y silencioso) de la condición 7 (WIP — NO subir, NO correr)

Tercera variante sobre el paquete [`../replicas_c7`](../replicas_c7), gemela en disciplina de
[`../replicas_c7_nav`](../replicas_c7_nav) y [`../replicas_c7_presupuesto`](../replicas_c7_presupuesto).
A diferencia de esas, aquí hay **dos** deltas trazables:

- **(a) Config**: `configs/sampling.yaml` con `thinking_budget: 1024` e `include_thoughts: false`
  (la condición 7, «razonamiento encendido», usa 4096/true). `thinking_level` se omite a propósito:
  bajo el endpoint OpenAI-compatible de vLLM se mapea a `reasoning_effort` y el contrato recomienda
  `thinking_budget` + `include_thoughts` (HARNESS_README §2.4).
- **(b) Instrucciones**: `prompts/system.md` gana una sección «Free Tools and Budget Discipline»
  (+138 palabras, ≤400): `submit_patch()`/`get_status()` cuestan cero llamadas; el razonamiento
  quema reloj; scratch solo en `/tmp`; el arnés recupera el parche al timeout aunque no se llame
  `submit_patch`; si se halló el sitio del edit y queda tiempo, editar ya y submit como acción final.
  Hechos citables al contrato (HARNESS_README §6.1 y §8.1).

**Motivación medida**: en réplica 1, varios pasos de thinking costaron 70-250 s de reloj cada uno
y 12/16 fallos murieron por el muro de 4,5 min (docs/c7_fallos_r1.md). La variante mide si el
razonamiento largo y visible de la condición 7 paga su coste.

| | condición 7 (réplicas) | variante thinking |
|---|---|---|
| huella de configuración | `0f52de0b84cb` | **`9d0db7b946e7`** |
| kernel (si se sube) | `cs4all/c7-replica-condicion-7` | `cs4all/c7-thinking-condicion-7` |

## Qué hay aquí

| Archivo | Rol |
|---|---|
| `notebook_c7_thinking.py` | Guion del notebook (fuente de verdad). Copia de `replicas_c7/notebook_c7.py`: la celda «kit» escribe `_SAMPLING_THINK` y sobrescribe `prompts/system.md` con `_SYSTEM_THINK`; la guarda exige la huella nueva. |
| `armar_notebook_thinking.py` | Genera `notebook_c7_thinking.ipynb` + `kernel-metadata.json`. Verifica ambos literales contra `kit_thinking/` y la constante, monta el kit de huella (descarga local de réplica 1 sin `adapters/` + system.md y sampling de la variante) y exige huella == `HUELLA_THINK`. |
| `kit_thinking/prompts/system.md` | Único archivo de prompt versionado (texto nuestro). El `sampling.yaml` de la variante va como literal en el guion y como constante en este script (doble verificación). Mismas 20 tareas, mismos topes. |
| `huella_thinking.txt` | Registro: huella original ↔ huella variante. |

## Estado

WIP commiteado el 2026-10-16. **No se ha subido ni corrido nada.** [PENDING — Monday: medición
como cuarto brazo del contraste, ver STATUS.md.]
