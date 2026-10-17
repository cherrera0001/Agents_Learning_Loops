# Análisis crítico C7 — data science local (sin GPU)

Fecha: 2026-10-17. Rama `exp/kaggle-c7-replicates`. Autor: sesión Kimi Code del dueño.
Regla de oro: cada afirmación va etiquetada **[DATO]** (medido, con fuente), **[INFERENCIA]**
(deducción de datos) o **[ESPECULACIÓN]** (hipótesis sin evidencia directa).

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

**Tasa de resolución** [DATO]: replica1 4/20 (20%); iteraciones 25/148 (16.9%); ledger: EXP-002
6/30, EXP-007 7/30, EXP-011 5/12, EXP-012 5/12. Por repo solo tenemos rich (todas las corridas
locales son rich): 17-20%. Para fastapi/requests no hay corrida local por-tarea (hueco declarado).

**Muerte en el muro de tiempo** [DATO]: 4.5 min + razonamiento: 15/20 (75%) mueren en el muro,
mediana 272 s. 4 min sin razonamiento: 0/148 bajo el umbral de 230 s, mediana 79-93 s. El
razonamiento encendido multiplica ×3-4 el wall-clock por tarea (272 vs 79-93 s) **sin cambiar la
resolución local** (20% vs 17-18%, n pequeño).

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
| lunes presupuesto (local) | 5/20 | [3, 7] | ataca el 75% de muertes en muro [INFERENCIA] |
| lunes thinking (local) | 4/20 | [2, 6] | era sin razonamiento 17-18% en las mismas rich [DATO] |
| lunes forrajeo (local) | 5/20 | [2, 7] | prior débil [ESPECULACIÓN]; el test es el valor |

Tabla comparativa preparada (se rellena con el dato real): sub-019 predicho 0.10 [0.06, 0.14] vs
real ___ → veredicto: dentro de ruido si |real−0.10| ≤ 0.041 relativo al instrumento; señal si >
0.14.

## Fase 4 — Recomendaciones rankeadas (ganancia esperada de score por hora-GPU; presupuesto 30 h)

1. **Thinking bajo/apagado con el budget reinvertido en tiempo** — [DATO] ×3-4 wall-clock sin
   ganancia local de resolución; EXP-010 verificó `thinking_budget: 0` en el arnés nuevo. Esperado:
   eliminar riesgo de cap en el envío + 0-2 tareas/58 [INFERENCIA]. Coste: 1 corrida ≈ 1.7 h GPU.
   **Mejor ganancia/hora.**
2. **Gold-patch rerun local (CPU)** — 0 GPU-h. [DATO] la discusión 747248 muestra que la
   medibilidad real difiere del nombre de la tarea (61/67 fastapi); sin el conjunto medible real,
   cualquier optimización posterior apunta a tareas rotas. Programado para el lunes (STATUS).
3. **Measurement set estratificado** (repo × riqueza × tamaño de patch) — 0 GPU-h; rediseña las 20
   tareas sustitutas tras (2). Evita sobre-optimizar el peor caso (enunciados rich de 138 chars).
4. **Brazo presupuesto** — [DATO] 75% de muertes en el muro en la única corrida reasoning-on;
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
simulaciones, setup 45 s/tarea + 7 min una vez]: reasoning-on consume **607 min de media (p95
638) de 720 — cabe, sin margen para nada**; sin razonamiento consume **314 min (p95 336) — deja
~406 min de slack**, suficiente para **duplicar el tiempo por tarea** (p.ej. 4.5 → 9-10 min) o
duplicar intentos. Actualiza la recomendación #1 de Fase 4: **thinking-off + reinversión del
tiempo ahorrado** ataca a la vez el wall-death (75% de muertes en la única corrida
reasoning-on) y la cap; es la palanca de mayor ganancia esperada por GPU-hora del inventario.

**A4. Leaderboard, página 3** [DATO]: filas 41-60 todas 0.20 → top-60 = 0.24×2, 0.22×27,
0.20×31. La mediana del LB completo queda pendiente (2.951 equipos ≈ 148 páginas; token de
paginación disponible en el historial de la sesión).

## Limitaciones

- Las corridas 2026-10-06 son de otra era (arnés 0.2.7/0.2.11, configs A/R/D/E/F sin mapear
  completo a números); se usan como evidencia de conducta, no como réplica estricta.
- n pequeño en todo (15-20 tareas por corrida): las tasas tienen IC amplios; la banda de ruido
  del leaderboard (σ≈0.02) es el estimador más sólido del set.
- Denominador del LB (~58) tomado de EXP-003 [DATO]; si el denominador real difiere, las
  conversiones tareas↔score se mueven proporcionalmente.
