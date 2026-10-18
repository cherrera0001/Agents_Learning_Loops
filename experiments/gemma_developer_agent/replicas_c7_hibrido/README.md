# Brazo HÍBRIDO — nav-v2 + presupuesto público 8 min / 28 llamadas / 240 s (pre-construido 2026-10-18)

Brazo de la **decisión (b)** de `docs/c7_baseline024_estudio.md`, pre-construido con 0 GPU para que
el paso 0.5 del lunes 2026-10-19 sea solo correrlo. **NO subir, NO correr sin decisión del dueño.**

- **Base**: kit de sub-019 (nav-v2, 0.17, huella `355f4954f50c` = condición 7 + prompt de navegación
  + 5.0 min). **Único delta funcional vs ese kit**: `eval_config.yaml` → la receta pública
  (`timeout_seconds 240, max_tool_calls 28, max_time_minutes 8.0, max_turns 80`). Verificado
  archivo-a-archivo: los únicos diffs contra `data/envios/nav_kit_v2/` son ese archivo.
- **Contra la condición 7** difiere en dos cosas declaradas: el prompt de navegación y el eval_config.
- Sampling = condición 7 (`thinking_budget 4096`, `include_thoughts true`); prompt = navegación
  (sha `f5bd1995…`, versionado en `kit_hibrido/prompts/system.md`). Mismas 20 tareas (ids_20_rich).
- **Por qué este brazo** (del estudio): la familia pública con estos topes puntúa 0.18-0.20 en el
  LB (verificado contra el CSV; los «0.24» de los notebooks no existen en el tablero de sus
  autores); el envelope cierra con nuestras trazas (media 199-255 s/tarea → 8,2-10,1 h de 720, sin
  contar que muchas tareas terminan antes); y ataca la única restricción que medimos como activa
  (el muro de tiempo: 13/20 lo tocaban a 4,5 min y +30 s compraron +0.07).

| | condición 7 | sub-019 nav-v2 | **híbrido** |
|---|---|---|---|
| huella | `0f52de0b84cb` | `355f4954f50c` | **`0fad98b7fe4d`** |
| `max_time_minutes` | 4.5 | 5.0 | **8.0** |
| `max_tool_calls` | 60 | 60 | **28** |
| `timeout_seconds` | 60 | 60 | **240** |
| `max_turns` | 100 | 100 | **80** |
| prompt | condición 7 | navegación | navegación |
| kernel (si se sube) | `cs4all/c7-replica-condicion-7` | — | `cs4all/c7-hibrido-condicion-7` |

## Verificación (2026-10-18, local, 0 GPU)

- Armar ×5 sin deriva (huella `0fad98b7fe4d`); preflight **24/24 «Se puede subir»**; ruff limpio.
- Delta puro verificado byte a byte contra el kit nav-v2 (solo `eval_config.yaml`).

## Tres gates pre-registradas (antes de que pase a candidato de envío)

1. **≥6/20** resueltas en local (réplica 1 de A resolvió 4/20; techo medible-ganable 13/20).
2. **Envelope**: media por tarea (s) × 120 + 90 min (preparación + carga) ≤ **660 min** (margen de
   60 min sobre las 720 del presupuesto global).
3. **≤3/20** tareas terminan en «llamadas agotadas sin parche» (con 28 de tope, réplica 1 habría
   cortado 8/20 por llamadas; la cosecha del arnés rescata parte, por eso la gate cuenta entregas).

Si falla (2) o (3): variante **(b′)** = mismo eval_config + regla «edita antes de la llamada 12» en
el prompt (segundo delta pre-declarado en el estudio). Si resuelve ≤4/20: se descarta y el lunes
sigue con la familia propia (brazos pre-registrados).
