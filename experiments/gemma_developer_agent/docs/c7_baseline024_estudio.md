# Estudio estructural de los notebooks «0.24» frente a la familia C7 (2026-10-18)

Insumo del paso 0.5 del runbook del lunes 2026-10-19: se lee **antes** de gastar GPU en brazos
intra-familia. Lectura de cuatro notebooks públicos (descargados con el CLI autenticado el
2026-10-17 ~22:05 UTC a un directorio aislado, leídos como texto, **sin ejecutar nada**) más un
quinto del mismo autor que explica su salto. Nada de esto se envió ni se subió. Informe de lectura
del arquitecto (modelo de tiempo y proyecciones) en la sesión de cierre; verificaciones propias
señaladas como tales.

Notebooks: `honghanhhh/gemma-4-baseline-lb-0-24` («Gemma 4 Baseline | LB 0.24», 35 votos),
`hitarthjain0/gemma-4-apex-silver-agent-lb-0-24`, `hitarthjain0/gemma-4-agent-what-took-lb-0-12-0-24`,
`averywright/gemma-4-caveman-thinking-0-20`, `verracodeguacas/gemma-4-agent-budget-fit-single-agent`
(210 votos; el «Budget-Fit 0.18» del dueño).

## 0. Hallazgo que cambia la pregunta: el «0.24» no está en el leaderboard

Verificado por el orquestador contra `analisis_c7/leaderboard_publico_2026-10-17T1501Z.csv`
(3.043 equipos): solo **2 equipos** tienen 0.24 (Yurnero/samson8 con 15 envíos; Yike Xu con 7), y
**ninguno** es autor de estos notebooks. Mejor nota de cada autor en esa foto: averywright
**0.20** (rank 122, 17 envíos), verracodeguacas **0.18** (126), honghanhhh **0.18** (162, 3 envíos),
hitarthjain0 **0.18** (252). El propio Apex escribe «It is not a measured score»; el baseline se
describe como «v3 (0.22 config + targeted prompt edits)» sin celda que reclame 0.24; la guía
«What took 0.12 → 0.24» dice «I have not scored this exact prompt».

Consecuencia: **no hay +0.07 que explicar con estas recetas.** La distancia medible entre esta
familia pública y nuestro 0.17 es de +0.01 a +0.03 (1-2 tareas de 58), dentro de la banda de ruido
que la propia guía estima en ±0.08-0.11 para una nota pública y que nosotros medimos en ±0.05.
El 0.24 real (2 equipos) no tiene explicación pública en estos notebooks.

## 1. Qué es cada notebook

- **Baseline «LB 0.24» (honghanhhh).** 31B QAT w4a16, arnés ADK oficial, kit declarativo de 4
  archivos, un solo agente (sin analizador). Registra las 9 herramientas pero el prompt prohíbe
  las tres de grafo. Prompt de ~1.150 palabras: especificación literal del issue, plan de llamadas
  (localizar en 1-8, **edición obligatoria antes de la llamada 12**, sin explorar desde la 20),
  aplicar el cambio a implementaciones paralelas (sync/async, `__all__`), scratch en `/tmp`,
  `git status --short && git diff` antes de `submit_patch`; como mucho dos verificaciones con pytest
  acotado y entrega. Presupuesto: `timeout_seconds 240`, `max_tool_calls 28`, `max_time_minutes 8`,
  `max_turns 80`. Muestreo 0.2/0.95/8192, `thinking_budget 4096`, `include_thoughts true`.
- **Apex Silver «LB 0.24» (hitarthjain0).** Mismo modelo, presupuesto y muestreo. Quita las
  herramientas de grafo de `agent.yaml` (6 herramientas). Prompt de ~550 palabras: **entrega en
  cuanto existe la edición, aunque el test local salga rojo**, y entrega ya si quedan <90 s. Afirma
  que `thinking_budget` «no se reenvía»: **falso** en `adk_submission 0.2.13` (`resolvers/generation.py`
  lo convierte en `thinking_token_budget`; nuestras trazas cortan en ~4.126 tokens, que es ese tope).
- **What Took 0.12 → 0.24 (mismo autor).** Guía, no envío. Cita la ablación pública de Ayush
  Thakur (129 tareas, una corrida cada una; cifras copiadas, no verificadas): thinking apagado 23
  resueltas frente a 48; sin resúmenes 35 frente a 51; bajar de 50 a 25 llamadas cuesta 14 tareas;
  temperatura/top_p/presupuesto de pensamiento mueven 0-3. Ruido de una nota pública ±0.08-0.11.
- **Caveman Thinking 0.20 (averywright).** Es Budget-Fit con un único cambio: un bloque «How You
  Think» (pensar corto, sin «Wait/Actually»). Declara 0.20, coherente con el leaderboard (mejor de
  17 envíos del equipo).
- **Budget-Fit Single Agent (verracodeguacas).** Prompt oficial de ejemplo con 8 min / 28 llamadas /
  240 s / 80 turnos y la regla «edita antes de la llamada 12»; grafo registrado pero desaconsejado.
  Dice que una corrida puntuada con estos topes terminó en menos de 12 h. Afirma que
  `timeout_seconds` acota también el pytest del calificador: **solo valía para el arnés viejo** (desde
  el 12-10 19:51 `budget.py` separa `verification_timeout_seconds = 300`; diff en
  `rescate_kaggle/instrumentos/arnes_2026-10-12_1951/`). Equipo en 0.18.

## 2. Tabla comparativa

| Dimensión | A (cond. 7) | sub-019 nav-v2 | Baseline «0.24» | Apex | Caveman 0.20 | Budget-Fit |
|---|---|---|---|---|---|---|
| Modelo | 31B qat w4a16 | igual | igual | igual | igual | igual |
| Agentes | coder + analizador (`agent_tool`) | igual | uno | uno | uno | uno |
| Herramientas de grafo | registradas; prompt sugiere `search_similar_code` | registradas; prompt **obliga** 2 llamadas | registradas, prohibidas | no registradas | registradas, prohibidas | registradas, desaconsejadas |
| `max_time_minutes` | 4.5 | 5.0 | 8 | 8 | 8 | 8 |
| `max_tool_calls` | 60 | 60 | 28 | 28 | 28 | 28 |
| `timeout_seconds` | 60 | 60 | 240 | 240 | 240 | 240 |
| `max_turns` | 100 | 100 | 80 | 80 | 80 | 80 |
| Muestreo / pensamiento | 0.2/0.95/8192/4096/true | igual | igual (sha `571a934e…` en todos) | igual | igual | igual |
| Edición obligatoria antes de la llamada 12 | no | no | sí | sí | sí | sí |
| Cuándo entrega | tras test verde | tras test verde | ≤2 verificaciones | con la edición, aunque el test esté rojo | tras test verde | tras test verde |
| Scratch en `/tmp` | no | no | sí | sí | no | no |
| Nota | sin envío (réplica local 4/20) | **0.17** | equipo 0.18 | no medido (equipo 0.18) | 0.20 | equipo 0.18 |

Verificado por sha256 en esta sesión: el prompt de A es idéntico al de `i_razona` (0.08/0.13/0.13) y
**distinto** del de nav-v2 (sub-019). El muestreo es byte-idéntico en las seis columnas.

## 3. Qué explicaría una diferencia (ordenado por evidencia)

1. **Ruido más selección.** *Dato:* ningún autor tiene 0.24; 317 equipos en 0.18, 95 en 0.20, 27 en
   0.22, 2 en 0.24; nuestro kit viejo dio 0.08/0.13/0.13 con el mismo zip. *Inferencia:* la receta
   8/28 rinde 0.17-0.20; 0.22-0.24 es la cola alta de muchos envíos.
2. **El muro de tiempo.** *Dato propio:* 15/20 tareas mueren en el muro de 270 s y pasar de 4.5 a
   5.0 min llevó 0.10 → 0.17 (A/B limpio). Los públicos dan 8 min. Es la palanca que cuadra con lo
   medido en casa. Con 28 llamadas, el tope que corta pasa a ser el de llamadas.
3. **Tope de llamadas + edición antes de la 12.** *Dato propio (trazas de réplica 1):* 8/20 tareas
   pasan de 28 llamadas, 3/20 nunca editan, mediana de la primera edición ≈ llamada 11. *Contra:* la
   ablación pública dice que bajar de 50 a 25 llamadas costó 14/129 (sin nuestro muro).
4. **Prompt de contrato** (cadenas exactas, implementaciones paralelas): ataca `parche_no_pasa`,
   31 % de nuestros fallos (`c7_frontera_2026-10-17.md`). No medido por nadie.
5. **Grafo y analizador.** *Dato propio:* en la condición 7 casi no se usan (6 `search_similar_code`
   y 1 analizador en 493 llamadas). Sub-019 obliga ~2 llamadas de grafo ≈ 8 % del muro de 300 s.
6. **`timeout_seconds` 60.** *Dato propio:* 0 `TimeoutExceeded` en 234 órdenes (todas rich). Solo
   pesaría en repos con tests lentos (requests ~100 s).

Descartado: el muestreo (idéntico byte a byte).

## 4. ¿Cabe en 12 h y en el contrato de envío?

Reglas verificadas el 2026-10-18 (STATUS §Reglas): las 12 h son **un solo presupuesto para toda la
corrida**, secuencial, incluida la preparación del sandbox y excluida la validación; superarlo hace
**fallar el envío entero** (host, 2026-09-24; sin cambio al 2026-10-15). La «regla de ~5,5 min por
tarea» es aritmética de participantes (720/120), no una regla del concurso: kits de 8 min con 28
llamadas han puntuado (equipos en 0.18-0.20).

Modelo de tiempo del arquitecto, ajustado sobre 499 peticiones de réplica 1: Δt ≈ 4,5 s + 28,8 ms
por token de salida (R² 0,89; coincide con el concilio 48, 28,5 ms). La salida es ~80 % del reloj.
A 5,0 min caben ≈ 6.700 tokens de salida por tarea; a 8 min con 28 llamadas ≈ 12.300.

- **8 min / 28 llamadas**: proyección con nuestras trazas (cortando en la llamada 28 o a 480 s):
  media 199-255 s → **8,2-10,1 h, cabe**; peor caso (todo a 480 s) 17,6 h, **no cabe**. Tres kits
  públicos puntuaron con estos topes. Advertencia: nuestras trazas son 20 rich, no el set oculto.
- **8 min / 60 llamadas no cabe**: 60 × ~12 s supera 480 s → casi todo al muro → ≈ 17,6 h.
- Todo es **configuración declarativa** (`eval_config.yaml`, lista `tools:` de `agent.yaml`,
  `prompts/system.md`). Nada exige código. Palancas del arnés que no usamos: `timeout_seconds`,
  retirar `agent_tool` y grafo, `thinking_budget` 0-32.768, y que `submit_patch`/`get_status` no
  cuentan como llamada (entregar antes sale gratis).

## 5. Decisión documentada

**(a) Adoptar-merge el baseline «0.24».** A favor: receta con >300 equipos en su banda, un agente.
En contra: su 0.24 no existe; nuestro `submission_publico_024_exacta.zip` (sub-015) lleva el prompt
**de Apex** (`7163e664…`), no el del baseline (`ff760906…`); rompe la comparabilidad con la familia
C7 y no explica nada que no esté ya en el muro. Coste: 0 GPU + un envío.

**(b) Híbrido mínimo: nav-v2 (0.17) con el `eval_config.yaml` público (8 / 28 / 240 / 80), prompt
sin tocar.** A favor: un solo archivo; mueve la única restricción que medimos como activa (el muro)
sin cambiar la conducta del modelo. En contra: ese archivo cambia **tres cosas** (tiempo, llamadas,
timeout); sin la regla «edita antes de la 12» en el prompt, el tope de 28 puede cortar tareas sin
parche (8/20 en réplica 1 pasan de 28 llamadas). Coste: 0 GPU para construir; 1 corrida local de 20
tareas (≈ 1,8 h de reloj, ≈ 3,6 h de cuota a L4 doble).

**(c) Seguir la familia propia** (réplicas 2-3 de A, brazos, R1-fiel). A favor: pre-registrado.
En contra: R1-fiel apaga el pensamiento y la ablación pública (no verificada) predice que eso
divide por dos las resueltas (23 vs 48); además R1-fiel **no es un A/B limpio contra sub-019**
(difiere en prompt y en thinking; corregido en `replicas_c7_r1fiel/README.md`).

**Decisión: (b), como brazo adicional del lunes con gate de envelope, sin abandonar (c).** Orden
del lunes: réplicas 2-3 de A (banda de ruido) → **híbrido (b) local sobre las 20 rich** → brazos
intra-familia. (b) quedó **pre-construido el 2026-10-18** en `replicas_c7_hibrido/` (huella
`0fad98b7fe4d`, armar ×5 sin deriva, preflight 24/24, delta puro verificado: único diff vs el kit
nav-v2 es `eval_config.yaml`); el lunes solo hay que correrlo. Las tres gates pre-registradas:

1. resuelve **≥ 6/20** (réplica 1 de A: 4/20; banda de ruido pendiente de réplicas 2-3; techo
   medible 13/20);
2. **envelope**: media por tarea (s) × 120 + 90 min de preparación/carga ≤ **660 min** (margen de
   60 min sobre 720);
3. **≤ 3/20** tareas terminan en «llamadas agotadas sin parche».

Si falla 2 o 3, se prueba la variante **(b′)**: mismo `eval_config` más la regla «edición antes de
la llamada 12» en el prompt (un segundo delta, pre-declarado aquí). Si (b) resuelve ≤ 4/20, se
descarta y el lunes sigue con (c) tal como está pre-registrado. R1-fiel conserva su valor como
medición de la hipótesis «thinking-off libera reloj», no como candidato de envío.

## 6. Lo que NO se pudo verificar

- Si algún notebook puntuó 0.24 con alguna versión (las notas de equipo pueden venir de otros zips).
- Qué versión de `swegemma` usa hoy el calificador y si su etapa 2 lee `timeout_seconds`.
- Las fechas de puntuación de los kits de 8 min frente al cambio de arnés del 12-10.
- Si los scripts de scratch en `/workspace` (`repro*.py`, `test_*.py`) ensucian el parche calificado.
- La conducta de nav-v2 en local: no tiene ninguna corrida local (re-medición prometida el lunes).
- Las cifras de la ablación de Ayush Thakur: copiadas en un notebook ajeno, sin acceso a la fuente.
