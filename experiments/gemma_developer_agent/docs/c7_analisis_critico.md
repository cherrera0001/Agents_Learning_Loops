# Análisis crítico C7 — data science local (sin GPU)

Fecha: 2026-10-17. Rama `exp/kaggle-c7-replicates`. Autor: sesión Kimi Code del dueño.
Regla de oro: cada afirmación va etiquetada **[DATO]** (medido, con fuente), **[INFERENCIA]**
(deducción de datos) o **[ESPECULACIÓN]** (hipótesis sin evidencia directa).

> **Correcciones del concilio 2026-10-17** (vuelta 49 / concilio 51, bitácora
> [`c7_concilio_2026-10-17.md`](c7_concilio_2026-10-17.md); guiones en
> `analisis_c7/guiones_concilio_2026-10-17/`): «15/20 (75%) mueren en el muro» → **13/20 (65%)**
> timeouts y **12/16 (75%) de los fallos**; «0/148 bajo 230 s» → **18/148 ≥230 s**; «submit 20%
> (4/20)» → el intento con status ok fue **7/20 (35%)**, 4/20 es resolución; «mediana 79-93 s» y
> «×3-4 wall-clock» tomaban subconjuntos (rango real 61,2-213,4 s por corrida; ×2,3-3,3). La era
> 2026-10-06 **no era thinking-off**: `thinking_budget:4096` con `include_thoughts:false`
> (pensamiento oculto, no apagado), así que la proyección «thinking-off ≈ 314 min» queda como
> hipótesis sin medir. Las cifras corregidas aparecen marcadas [corregido] en el texto.

## Trazabilidad (fuentes)

| Fuente | Ruta | Uso |
|---|---|---|
| Réplica 1 condición 7 | `data/replicas_c7/replica_1/salida__c7_20261016T0459Z.json` (gitignored) | 20 tareas rich, 4.5 min, razonamiento on |
| Corridas 2026-10-06 | `data/rescate_kaggle/2026-10-06T1910Z/notebooks/iteracion-0{1,2,3}/salida__*.json` | 148 filas en 10 corridas (A/R/D/E/F), mismas 15 rich, era 4 min sin razonamiento |
| Registro de envíos | `submissions/registry.json` (versionado) | 19 envíos, scores |
| Ledger del dueño | `EXPERIMENT_LEDGER.csv` (no trackeado; snapshot en `analisis_c7/experiment_ledger_snapshot.csv`) | EXP-001…012 |
| Tareas públicas | `data/tasks.jsonl` (gitignored) | 129 tareas, features |
| Leaderboard | `kaggle competitions leaderboard -s` (2026-10-17) | top público |
| Discusiones Kaggle | enlaces en §Q3 | bugs públicos del harness |

Derivados cometidos en `experiments/gemma_developer_agent/analisis_c7/`: `corridas_tareas.csv`
(168 filas), `tareas_features.csv` (129), `envios.csv` (19), `predicciones.csv` (sellado),
`experiment_ledger_snapshot.csv`, figuras `fig_*.png`. **Desviación del encargo**: los CSV van en
`analisis_c7/` (versionado) y no en `data/analisis_c7/`, porque `data/` está en `.gitignore` y el
encargo pedía los derivados cometidos.

### Diccionario de columnas

- `corridas_tareas.csv`: `fuente` (replica1_c7_4.5min | iteracion_NN_2026-10-06), `corrida`
  (c7_20261016T0459Z | A1…AR1), `condicion` (c7_razonamiento_4.5min | A/R/D/E/F — letra tal cual
  en el rescate, el mapeo letra→config exacta no está en los artefactos leídos), `task_id`
  (instance_id), `resuelta`, `clase`, `llamadas_herramientas`, `llamadas_modelo`,
  `segundos_reloj`, `muro` (replica1: ≥260 s; iteraciones: ≥230 s — umbrales distintos, declarado),
  `usa_*` (conteos de herramientas, iteraciones solamente), `primera_edicion_llamada`,
  `err_tool_count`.
- `tareas_features.csv`: `instance_id`, `repo`, `enunciado_chars`, `patch_lineas`,
  `patch_archivos` (conteo de `diff --git`), `test_patch_lineas`.
- `predicciones.csv`: `objetivo`, `prediccion`, `intervalo_inf/sup`, `timestamp_sellado_utc`,
  `base`, `notas`.

## Q1 — «¿Por qué seguimos pegados en 0.13?»

**La banda de ruido del instrumento** [DATO]: envíos del **mismo zip** reenviados:
`65a02160` (condición razonamiento): 0.08 / 0.13 / 0.13 (media 0.113, sd 0.0289);
`d8a3e1d3` (base 4 min): 0.06 / 0.05 (media 0.055, sd 0.0071). sd agrupada = **0.0207 →
IC95 ±0.041**. El «0.13» fue el **máximo** de tres replicados del mismo kit, no una cifra
estable; el 0.10 de sub-018 (nav) y el 0.13 (viejo) son indistinguibles (Δ=0.03 < IC95).

**Tasa de intento**: [INFERENCIA] no es el cuello. La aritmética oficial (12 h incl. setup,
§STATUS «Kit v2») da 540-637 min consumidas de 720 con el kit actual — las ~120 tareas caben.
[DATO] en nuestras corridas locales la tasa de submit fue 91% (135/148, era 4 min) y 20% (4/20,
era 4.5 min con razonamiento) — la diferencia es conducta del agente, no capacidad del run.
[corregido, concilio 2026-10-17] el «20%» rotula resolución: el submit con status ok en réplica 1
fue **7/20 (35%)** (auditor, `guiones_concilio_2026-10-17/auditor/audit_02_submits.py`); sin bytes
de parche mide intento, y 44/135 submits de la era están vacíos — la métrica sana es parche no
vacío.

**Tasa de resolución** [DATO]: replica1 4/20 (20%); iteraciones 25/148 (16.9%); ledger: EXP-002
6/30, EXP-007 7/30, EXP-011 5/12, EXP-012 5/12. Por repo solo tenemos rich (todas las corridas
locales son rich): 17-20%. Para fastapi/requests no hay corrida local por-tarea (hueco declarado).

**Muerte en el muro de tiempo** [DATO] [corregido, concilio 2026-10-17]: 4.5 min + razonamiento:
**13/20 (65%)** tocaron el muro por log del arnés y **12/16 (75%) de los fallos** murieron en él
(el «15/20» mezclaba denominadores; dos `muro=True` no murieron: rich_3278 y rich_3130; rich_3043
resolvió por cosecha del árbol al timeout con 0 llamadas `submit_patch`),
mediana 272 s. 4 min «sin razonamiento» [corregido: era `thinking_budget:4096` con thoughts
ocultos, no apagado]: **18/148 ≥230 s** (el «0/148» era falso), medianas por corrida 61,2-213,4 s
(el «79-93» tomaba un subconjunto). El razonamiento encendido multiplica ×2,3-3,3 el wall-clock
por tarea **sin cambiar la resolución local** (20% vs 17-18%, n pequeño).

**Veredicto Q1** [INFERENCIA]: el 0.13 es el techo **observado** de kit+instrumento, no una
meseta causal única. El instrumento aporta σ≈0.02; el kit aporta una tasa de resolución real del
~10-13% sobre el denominador público de 58 (EXP-003 [DATO]: 3/58 = 0.05). Las palancas que la
aritmética y los datos señalan son el wall-clock del razonamiento y la conversión
localizar→editar, no la cobertura de tareas.

## Q2 — «¿Sirvió el cerebro de gusano?»

**Respuesta correcta hoy: NO MEDIBLE** — el brazo forrajeo (`fb8175c0e74e`) nunca ha corrido
[DATO: estado WIP, sin pushes]. Lo que se entrega es el **test pre-registrado** del lunes:

- Diseño: forrajeo vs A (condición 7), mismas 20 tareas sustitutas, 2 réplicas de ruido de A,
  decisión con la regla fijada antes de correr.
- **«Sirvió»**: forrajeo supera a A en más de la banda de ruido medida el lunes (flips ≥3
  tareas de 20 entre réplicas de A). Resultado contaría como señal positiva para la política de
  búsqueda con escalada temporalizada.
- **«No sirvió»**: forrajeo ≤ A en ambas ventanas (banda incluida).
- **«Inconcluso»**: la banda de ruido de A resulta ≥3 tareas (cualquier diferencia menor que la
  banda no es legible, por la propia regla del dueño).
- Predicción sellada (§Fase 3): 5/20 [2,7] — prior débil [ESPECULACIÓN]; el valor del brazo es
  el test, no el punto.

## Q3 — «¿Qué más podemos descubrir de Kaggle?»

**Leaderboard público** [DATO, 2026-10-17, `leaderboard -s`]: top = 0.24 (2 equipos: Yurnero,
Yike Xu); banda densa en **0.22** (≥27 equipos en las primeras 40 filas); siguiente banda 0.20
(11 equipos). Los scores vienen cuantizados en pasos de ~0.02 (consistente con conteo de tareas
resueltas: denominador ~58, paso 1/58 ≈ 0.017 [INFERENCIA]). Nuestro 0.13 queda **~0.09 por
debajo de la banda 0.22** ≈ 5 tareas de 58 [INFERENCIA]. Mediana del LB completo: pendiente
(solo top-40 legible vía CLI; paginar completo queda como trabajo futuro).

**Discusiones públicas** [DATO, con fecha]:
- [744370 (2026-09-29)](https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/744370):
  `typing_inspection` (dependencia de pydantic 2) ausente en el entorno de evaluación → crashes
  al cargar. Corrobora nuestro hallazgo del wheelhouse (Track C(i)).
- [747248 (2026-10-08)](https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/747248):
  análisis público de measurability: «typing_inspection was the cause on 61 of the 67 fastapi
  tasks». Corrobora la crisis de medibilidad del manuscrito (58/129 no medibles) con fuente
  externa fechada.
- [744354](https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/744354): bug
  público de procesamiento de reasoning-tokens entre ADK y vLLM — relevante para el brazo
  thinking del lunes.
- Configs ganadoras reportadas: **pendiente** — no hay write-ups públicos de los top (competencia
  en curso; búsqueda web 2026-10-17 no arrojó uno).

## Fase 3 — Predicciones selladas

Selladas en `predicciones.csv` (2026-10-17 10:57 UTC), **antes** de conocer el score de sub-019.
El loop autónomo registrará el score real cuando caiga; la comparación se hará contra esta fila
(su uso para «ajustar» la predicción estaría prohibido — post-hoc).

| objetivo | predicción | IC | base |
|---|---|---|---|
| sub-019 (nav v2, 5.0 min) score LB | **0.10** | [0.06, 0.14] | sub-018=0.10 + Δ(0-1 tareas/58); ruido IC95 ±0.041 |
| lunes A (local, 20 rich) | 4/20 | [2, 6] | réplica 1 = mismo config |
| lunes nav (local) | 4/20 | [2, 6] | réplica 1 |
| lunes presupuesto (local) | 5/20 | [3, 7] | ataca 12/16 fallos que mueren en el muro [INFERENCIA] |
| lunes thinking (local) | 4/20 | [2, 6] | era con thoughts ocultos (budget 4096), 17-18% en las mismas rich [DATO] |
| lunes forrajeo (local) | 5/20 | [2, 7] | prior débil [ESPECULACIÓN]; el test es el valor |

Tabla comparativa preparada (se rellena con el dato real): sub-019 predicho 0.10 [0.06, 0.14] vs
real ___ → veredicto: dentro de ruido si |real−0.10| ≤ 0.041 relativo al instrumento; señal si >
0.14.

## Fase 4 — Recomendaciones rankeadas (ganancia esperada de score por hora-GPU; presupuesto 30 h)

1. **Thinking bajo/apagado con el budget reinvertido en tiempo** — [DATO] ×2,3-3,3 wall-clock sin
   ganancia local de resolución; EXP-010 verificó `thinking_budget: 0` en el arnés nuevo. [corregido,
   concilio 2026-10-17]: la era de contraste NO era thinking-off (era budget 4096 con thoughts
   ocultos; `include_thoughts:false` solo oculta — el apagado real exige `thinking_budget:0`), y el
   envelope de la cap rechaza 9-10 min/tarea salvo que thinking-off baje las muertes a menos de la
   mitad (break-even f≈0,49; a f=0,65 de réplica 1 no cabe: 874>720; **6,0 min sí cabe: 641 min**).
   La configuración fiel a esta recomendación es un sexto brazo `thinking_budget:0` + 6,0 min +
   prompt de A (delta puro de config). Esperado:
   eliminar riesgo de cap en el envío + 0-2 tareas/58 [INFERENCIA]. Coste: 1 corrida ≈ 1.7 h GPU.
   **Mejor ganancia/hora, condicionada a medir f el lunes.**
2. **Gold-patch rerun local (CPU)** — 0 GPU-h. [DATO] la discusión 747248 muestra que la
   medibilidad real difiere del nombre de la tarea (61/67 fastapi); sin el conjunto medible real,
   cualquier optimización posterior apunta a tareas rotas. Programado para el lunes (STATUS).
3. **Measurement set estratificado** (repo × riqueza × tamaño de patch) — 0 GPU-h; rediseña las 20
   tareas sustitutas tras (2). Evita sobre-optimizar el peor caso (enunciados rich de 138 chars).
4. **Brazo presupuesto** — [DATO] 12/16 de los fallos mueren en el muro en la única corrida
   reasoning-on [corregido, concilio 2026-10-17: era «75% de muertes» con denominador mezclado];
   el brazo existe y cuesta 1 corrida. Esperado +0-2 tareas/20 [INFERENCIA].
5. **Kit v2 (5.0 min, sub-019)** — ya enviado; esperado +0-1 tareas/58. Coste 0 (hecho).
6. **Brazo forrajeo** — test pre-registrado (Q2); upside exploratorio, coste 1 corrida.

Nota de contrato [DATO, HARNESS_README §2.1]: el envío es declarativo-only — las palancas de
código (harness, tools) no están disponibles; todo pasa por instrucciones, sampling y budgets.

## Anexos (2026-10-17, misma sesión)

**A1. La riqueza del enunciado domina la resolución** [DATO, join `corridas_tareas` ×
`tareas_features`, n=168]: mediana de `enunciado_chars` = **1.672 en las 29 tareas resueltas vs
159 en las 139 no resueltas** (~10×). `patch_lineas`: 16 vs 30 (las resueltas son parches más
cortos — tareas más triviales, [INFERENCIA]). Implicación: la variable explicativa dominante del
score es **qué tan informado está el enunciado**, antes que config del agente; el measurement set
estratificado (Fase 4 #3) no es opcional, y optimizar sobre rich de 138 chars (el set sustituto
actual) subestima cualquier mejora real.

**A2. Conducta asociada a resolver** [DATO, iteraciones con anatomía, n=103 con primera edición]:
primera edición en la llamada **5 (resueltas) vs 20 (no resueltas)**; errores de herramienta 1.7
vs 2.4 de media. Editar temprano y sin errores separa los grupos mejor que cualquier otra
variable medida. Matiza EXP-005 del ledger («ediciones tempranas apresuradas rotas»): temprana +
correcta es la que resuelve; la lección es **editar temprano con verificación, no editar pronto**.

**A3. Simulación de la cap de 12 h** [DATO, bootstrap sobre tiempos reales por tarea, 2.000
simulaciones, setup 45 s/tarea + 7 min una vez; guion cometido en
`guiones_concilio_2026-10-17/analista/06_a3_bootstrap_cap12h.py`]: reasoning-on consume **607 min de
media (p95 636-638) de 720 — cabe, sin margen para nada**. [corregido, concilio 2026-10-17]: la
era «sin razonamiento» consumía **314 min (p95 336)** con `thinking_budget:4096` y thoughts
**ocultos** — no apagados —, así que esa proyección NO calibra pensamiento apagado: es la cifra de
«ocultar los pensamientos», hipótesis sin medir para `thinking_budget:0`. La misma simulación con
la distribución real y la cap incluyendo setup (auditor, `auditor/audit_05_envelope.py`) da:
reinversión a **9,0 min solo cabe si f≤0,47-0,49** (a f=0,65 de réplica 1: 874 min, no cabe);
**6,0 min cabe con margen** (641 min a f=0,65; break-even f≈0,81). Actualiza la recomendación #1
de Fase 4: **thinking-off real (`thinking_budget:0`) + reinversión moderada (6,0 min)** ataca el
wall-death (12/16 de los fallos en la única corrida reasoning-on) y la cap; el detector de
pérdida de capacidad es la subida de `parche_no_resuelto`/`err_tool_count`.

**A4. Leaderboard completo** [DATO, descarga oficial del LB 2026-10-17 15:01 UTC, 3.043 equipos]:
**mediana 0.13, media 0.119** (p25 0.08 / p75 0.17 / p90 0.18). Cabeza: 0.24×2, 0.22×27,
0.20×95, 0.18×317, 0.17×401, 0.15×412, 0.13×344. Con ≥0.13 hay 1.598 equipos (top ~52%): el
0.13 del kit viejo está **exactamente en la mediana del campo**, y el 0.10 de sub-018 por debajo
de ella. La mediana completa corrige la estimación de página 3 (0.20×31 en top-60 → 0.20×95 en
todo el LB): la cola es mucho más densa en 0.13-0.18 de lo que sugiere el top-60.

**A5. Resultado sub-019 (nav-v2 @5.0 min) vs predicción y vs el muro** [DATO, ref 57296502,
scored 2026-10-17 20:39 UTC tras ~15,4 h]: **0.17**. Comparaciones: vs 0.10 de sub-018 (mismo
kit a 4.5 min — A/B limpio, solo cambia `max_time_minutes`) = **+0.07 → FUERA de ruido** (banda
IC95 ±0.041 del instrumento y ±0.05 de la regla de envío); vs 0.13 del kit viejo = +0.04 (dentro,
en el borde; por encima de sus tres replicados 0.08/0.13/0.13). **Predicción sellada 0.10
[0.06,0.14]: FUERA por arriba** — la premisa «el muro no es el cuello del score» queda
refutada por el dato: +30 s/tarea compraron ~4 tareas/58. Refuerza la recomendación #1
(wall-clock como palanca) y da al brazo presupuesto una base causal limpia. Matiz [INFERENCIA]:
es un envío único; la atribución causal descansa en la limpieza del A/B (mismo zip-base, una
clave de diferencia) y no en réplicas. nav-v2 = mejor envío propio hasta la fecha; el lunes se
re-mide nav@5.0 en local antes de que cualquier brazo lo supere.

## Limitaciones

- Las corridas 2026-10-06 son de otra era (arnés 0.2.7/0.2.11, configs A/R/D/E/F sin mapear
  completo a números); se usan como evidencia de conducta, no como réplica estricta.
- n pequeño en todo (15-20 tareas por corrida): las tasas tienen IC amplios; la banda de ruido
  del leaderboard (σ≈0.02) es el estimador más sólido del set.
- Denominador del LB (~58) tomado de EXP-003 [DATO]; si el denominador real difiere, las
  conversiones tareas↔score se mueven proporcionalmente.
