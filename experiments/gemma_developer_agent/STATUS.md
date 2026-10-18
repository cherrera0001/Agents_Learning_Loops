# STATUS · Réplicas condición 7 (rama exp/kaggle-c7-replicates)

Actualizado: 2026-10-17 20:45 UTC (**sub-019 SCORED 0.17** — el mejor envío propio hasta la fecha;
loop vigía cumplido y autodestruido; concilio C7 Fase 4 registrado, bitácora
[`docs/c7_concilio_2026-10-17.md`](docs/c7_concilio_2026-10-17.md); merge de `origin/main` hecho).
**Bloqueo de cuota GPU sigue vigente** (reinicio semanal; el lunes 2026-10-19 es lo esperado).
Cabeza: `e97ef59` + commit de este registro.

## Kit v2 «presupuesto-corregido» (sub-019, SCORED 0.17 el 2026-10-17 20:39 UTC, ref 57296502)

- **Valores leídos del kit nav real** (los 6 archivos, Tarea 1): eval_config.yaml =
  `timeout_seconds 60, max_tool_calls 60, max_time_minutes 4.5, max_turns 100`;
  configs/sampling.yaml = `temperature 0.2, top_p 0.95, max_output_tokens 8192,
  thinking_budget 4096, include_thoughts true`. Defaults del harness (60 min/100 llamadas/
  500 turnos/300 s) NO están en uso.
- **Aritmética con evidencia propia** (réplica 1, salida `c7_20261016T0459Z.json`): carga de
  modelo 367 s (una vez, L4); por tarea media 255 s / mediana 272 s; **15/20 tareas mueren en
  el muro de 270 s**; llamadas medias 24/60 (máx 52, sin saturar); warm pooling con
  `reuse_containers=True` (HARNESS_README §4.1) → setup por tarea ≈0-45 s (la mediana 272 ≈
  270 del muro lo confirma). Proyección del kit v1 a 120 tareas: **540-637 min de 720 → cabe,
  con 83-180 min de margen**.
- **Veredicto sobre la causa sospechada**: la hipótesis «0.13 estancado por tareas no
  intentadas» queda **REFUTADA** (el kit actual ya intenta las ~120). La restricción activa
  observada es el **muro de tiempo por tarea** (15/20), no las llamadas (24/60) — consistente
  con el ledger del dueño (EXP-004: subir llamadas 40→100 aumentó loops → discard).
- **Corrección aplicada (cada número citado)**: `max_time_minutes 4.5 → 5.0`. Cabe incluso en
  el peor caso: 120×300 s + 120×45 s setup + 367 s carga = **698 min ≤ 720**; en el caso base
  (~0-30 s setup) ≈630 min. Todo lo demás intacto (llamadas 60: EXP-004; turnos 100: no
  activos; timeout 60: sin evidencia en contra; sampling: lo deciden los brazos
  thinking/presupuesto el lunes, NO se toca).
- **Artefactos**: kit en `data/envios/nav_kit_v2/` (gitignored), zip
  `data/envios/submission_nav_v2_2026-10-17.zip` (3.931 B, `agent.yaml` en raíz, 6 entradas
  .yaml/.md, sin symlinks, 6.487 B descomprimido « 3 GiB), **sha256
  `c08e53279ed2dba948bebd0c59e2345db4596adf1e2b7e42a82a19d5509cf066`**, huella de
  configuración **`355f4954f50c`** (la de sub-018 `af8cca829561` queda como era: el brazo nav
  del lunes se mide a 4.5 min por comparabilidad — sub-019 es candidato de LEADERBOARD, no del
  contraste). Compilación `adk-submission 0.2.13` oficial: **OK** (venv desechable
  `/tmp/venv_pack` con las ruedas locales).
- **sub-019: SCORED 0.17 el 2026-10-17 20:39 UTC, ref `57296502`** (sha `c08e5327…`, huella
  `355f4954f50c`, kit v2 con `max_time_minutes 5.0`, tras ~15,4 h de evaluación). Comparaciones:
  **vs 0.10 de sub-018 (nav @4.5 min) = +0.07 → FUERA DE RUIDO (±0.05)**; vs 0.13 del kit viejo
  (i_razona) = +0.04 (dentro de banda, en el borde; por encima de los tres replicados del kit
  viejo 0.08/0.13/0.13). **Predicción sellada 0.10 [0.06,0.14]: FUERA por arriba** — la predicción
  (basada en «el muro no es el cuello del score») subestimó el efecto del muro: dar 30 s más por
  tarea movió ~4 tareas/58 de media. nav-v2 es **el mejor envío propio hasta la fecha** y candidato
  de referencia. Registry: status `scored`, public_score 0.17; test tripwire 61 passed. El loop
  vigía se autodestruyó con este registro (tabla final abajo). Decisión para el dueño: la regla
  del árbol (0.08-0.18 = plan sin cambios) se aplica con matiz registrado: el contraste del lunes
  gana relevancia y **nav@5.0 local re-medido el lunes** antes de cualquier envío que lo supere.
  **Tabla final de la campaña nav**: kit viejo (i_razona) 0.08/0.13/0.13 (tres replicados) ·
  sub-018 nav @4.5 min 0.10 · **sub-019 nav-v2 @5.0 min 0.17**.
- **Tarea 6 (gold-patch CPU local)**: estimado >2 h en CPU (129 tareas × pytest en 2 vCPU) →
  **programada para el lunes** como primer paso opcional del runbook (fijar el conjunto
  medible real antes de cualquier nuevo measurement set; los públicos 109/129 vs «~la mitad»
  se contradicen y no valen).

## Push y auth (2026-10-17)
- **Repo público al día**: `origin/main` = `36b942a` y `origin/exp/kaggle-c7-replicates` =
  `f91997c` (0 ahead/0 behind en ambas; verificado con fetch). Requisito de reproducibilidad de
  las reglas del concurso cumplido (método y ablaciones citados en la descripción de sub-018).
- **Auth**: `gh` autenticado como `cherrera0001` (PAT por stdin; sin eco, sin tocar `.env`, sin
  commitear). **Pendiente del dueño: ROTAR el PAT en GitHub Settings** — transitó por el chat en
  claro con scopes amplios; tratar como expuesto (el push ya está hecho, no hay prisa operativa).
- **Discrepancia resuelta (sesión web paralela)**: esa sesión rebuildó la variante thinking con
  huella `5e4ccbe0…` desde fuentes públicas, sin el kit verificado de réplica 1. La huella
  **canónica sigue siendo `9d0db7b946e7`** (armar la recompute sobre la descarga de réplica 1,
  preflight 24/24). Nadie debe usar `5e4ccbe0…` para medir ni enviar; sus 12/12 checks son un
  subconjunto de nuestros 24/24.

## Ciclo corregir→enviar 2026-10-17 (autorizado; verificación completa, PARADO antes del envío)

- **Corrección de premisa (con evidencia, no enviada)**: el fix `clase_fallo` (`bc17aea`,
  `agent_patch`) vive en los **notebooks de réplica** (código de medición de la campaña), NO en
  el kit del envío — el contrato es declarativo-only (6 archivos `.yaml`/`.md`, cero código;
  `grep -r generated_patch\|agent_patch kit_nav/` → sin coincidencias). Por tanto **sub-018 nunca
  estuvo afectada por el bug**: su paquete YA es la versión «corregida».
- **Prueba de identidad**: reconstrucción del kit desde HEAD (receta documentada: `c7_submission`
  sin `adapters/` + `kit_nav/prompts/system.md`) → huella reproducida `af8cca829561` (armar, sin
  deriva) y zip reconstruido con la receta determinista de `pack_submission`: **6/6 entradas con
  CRC y tamaño idénticos** al zip de sub-018 (solo difiere `external_attr`, bits de permiso del
  contenedor: sha del rebuild `e04f8733…` vs `648d312c…`). El contenido es el mismo paquete.
- **Decisión**: NO se envió nada. Enviar quemaría el cupo 1/día (oficial, verificado) en un zip
  de contenido idéntico — contra la regla dura «never submit an identical or hash-equal zip».
  sub-019 **no existe**; registry y cron vigía sin cambios (siguen sub-018).
- **Consecuencia práctica**: el «reenvío corregido» queda descartado como concepto; el próximo
  envío distinto será, según la regla de decisión fijada, el brazo que supere a A en más de la
  banda de ruido el lunes (forrajeo `fb8175c0e74e` y las demás variantes ya están construidas).
- Nota: el texto de descripción propuesto en el ciclo («parseo agent_patch») habría sido falso
  en el paquete; queda descartado con el envío. Artefactos del rebuild en `/tmp` (fuera del repo).

## Verified 2026-10-16 (pasada V1–V5, sesión ~16:25 UTC)

- **V1 integridad del registro: PASS.** sha256 del zip recalculado =
  `648d312c…49682` (coincide con registry sub-018). Campos cruzados registry ↔ STATUS.md
  sin inconsistencias (status submitted, ref 57274153, 2026-10-16 15:30:14 UTC).
- **V2 estado en vivo: PENDING.** sub-018 (ref 57274153) sigue `SubmissionStatus.PENDING`;
  ~53 min transcurridos a las 16:23 UTC. Sin score → registro sin cambios por V2.
- **V3 lunes sin tocar: PASS.** Los 4 armar_notebook corren y los 3 de variantes recomputan
  huella exacta (nav af8cca829561, presupuesto 52ba08ceac25, thinking 9d0db7b946e7; el brazo A
  guarda en runtime el kit 0f52de0b84cb y su base 3b0e87556166 está documentada en
  docs/c7_replicas.md). Preflight 24/24 «Se puede subir» en las 4 carpetas. Set fijo de 20
  tareas: ids embebidas en los 4 notebooks == `tareas_c7.json` ids_20_rich. Cuota GPU sigue
  bloqueada (nota de reinicio semanal; sin push de prueba). Coste lunes: 6 corridas × 93 min =
  9,3 h ≤ 30 h de cuota.
- **V4 salud del repo: PASS con un fix necesario (hecho, no silencioso).** `ruff format`
  exigía reformat en las 3 fuentes `notebook_c7_*.py` de variantes (diff cosmético: una línea
  en blanco y un raise envuelto; strings intactos) → formateadas, notebooks regenerados con
  armar (huellas re-aseguradas, preflight re-corridas 24/24), y los 3 `.ipynb` generados
  añadidos a `extend-exclude` de ruff (mismo precedente que el notebook base; `.codex/`
  excluido también: es local del dueño y no trackeado). Un test del repo
  (`test_kaggle_registro_215`) fijaba el registry en 17 entradas/2026-10-14: actualizado a
  18/2026-10-16 con bloque sub-018 en el estilo del archivo; la sesión anterior había añadido
  a sub-018 tres claves ajenas al esquema (`kaggle_ref`, `submitted_at_utc`,
  `platform_filename`) — movidas a notes, que es el patrón establecido (sub-008/sub-010).
  ruff check: 0 errores. ruff format --check: 391 archivos OK. mypy (a pelo): sin issues en
  15 archivos. devlog rebuild: 97 goals / 2246 conceptos. pytest completo: **3479 passed,
  5 skipped, 0 failed** (4:27).
- **V5:** sin submissions, sin pushes a Kernels, sin GPU; main intacto.

## Ahora (estado real)
- **sub-018 (NAV) = ENVIADO** 2026-10-16 15:30:14 UTC, ref **57274153**, estado inicial PENDING
  (slot diario consumido: «0 submissions remaining today»). El API rechazó el nombre
  `submission_nav_2026-10-16.zip` (regla de plataforma: «Submission files must be named
  submission.zip»); se subió copia desde `/tmp/submission.zip`, contenido idéntico
  (sha256 `648d312c…49682`). Score: pendiente (los envíos previos tardaron horas-días).
  Registro actualizado en `submissions/registry.json` (status → submitted). Subida hecha
  por el agente por instrucción expresa del dueño de esta sesión; regla «el agente no
  sube» queda reemplazada mientras el dueño lo disponga expresamente.
- **Consulta de estado 2026-10-16 23:54 UTC (solo lectura): sub-018 sigue PENDING**, sin
  publicScore/privateScore; ~8,4 h transcurridas, dentro del rango histórico (envíos
  previos tardaron horas-días en puntuar). Registro SIN cambios (correcto: nada que
  actualizar hasta que haya score). Reanudar con:
  `.venv-linux/bin/kaggle competitions submissions -c gemma-4-developer-agent | grep 57274153`
  y, si aparece scored, seguir los pasos 1-5 del protocolo de la sesión 2026-10-16
  (esquema SubmissionRecord → campos existentes + notes → test focalizado → STATUS;
  commit solo con autorización explícita).
- **PAQUETE DE ENVÍO NAV** (veredicto de gates al prepararlo):
  - Zip: `data/envios/submission_nav_2026-10-16.zip` (3.932 B), construido por el pipeline
    establecido (`scripts.kaggle_submission pack`), compilado con `adk-submission 0.2.13`
    oficial (en venv desechable `/tmp/venv_pack`, para no tocar `.venv-linux`), validación
    estricta `verify` = VÁLIDO, registro **sub-018** en `submissions/registry.json`.
  - **SHA-256: `648d312cd5349522f0fdf85ad50477dc3a9845bb0b4d3a9a4bbe4f2107497682`** — sin
    colisión con los 17 envíos previos (sub-001..017). El directorio de ensamblaje
    `data/envios/nav_kit/` se ELIMINÓ tras empaquetar (el verificador trata `data/` como
    referencia y un duplicado del system.md versionado allí es colisión); para reempaquetar:
    copiar `data/replicas_c7/replica_1/c7_submission` sin `adapters/` + `replicas_c7_nav/
    kit_nav/prompts/system.md`, comprobar huella `af8cca829561` y repetir `pack`.
  - Kit: los 6 archivos del kit verificado de réplica 1 + `prompts/system.md` de navegación;
    huella de configuración `af8cca829561` recomputada y EXACTA antes de empaquetar. Sin
    `adapters/`, sin archivos de plantilla extra: el zip trae exactamente los 6 archivos.
  - **Instrucciones de subida (dueño, Kaggle UI):** (1) abrir
    https://www.kaggle.com/competitions/gemma-4-developer-agent/submissions → «Submit
    Predictions»; (2) subir `submission_nav_2026-10-16.zip` (mantener ese nombre); (3) en
    Description: «Navigation-first instruction variant of condition 7 (reasoning on, 60 tool
    calls, 4.5 min/task); single change: system instructions (identifier extraction →
    multi-word search_similar_code → get_code_neighbors → read → edit best candidate).
    Configuration fingerprint af8cca829561. Method and replication package:
    https://github.com/cherrera0001/Agents_Learning_Loops»; (4) tras la subida, anotar el
    submission id y la puntuación en `submissions/registry.json` (sub-018, status →
    submitted/scored). **El agente NO sube nada: la subida la hace el dueño.**
- **Réplica 1/3 = COMPLETE**: 4/20 (20,0%), huella OK, validada. Réplicas 2-3 esperando cuota.
- **Tres variantes LISTAS, sin correr** (preflight 24/24, nada subido a Kernels):
  navegación-primero `af8cca829561` (ahora también empaquetada como envío, sub-018);
  conciencia-de-presupuesto `52ba08ceac25` (`75ff644`); thinking `9d0db7b946e7` (`ddfc537`).
- **Veredicto candidato «env-packages» (paquetes de prueba en el ENVÍO): MUERTO** (contrato
  declarativo-only, sin gancho de entorno; HARNESS_README §2.1-2.4). Nuevo matiz del Track C(i):
  el WHEELHOUSE del dataset oficial (lado datos, no envío) trae typing_inspection y
  python_multipart pero **no** h11 ni dirty_equals.
- **fix de `clase_fallo` = APLICADO** (2026-10-16 ~23:59 UTC, `bc17aea`, decisión tomada con
  autorización expresa del dueño en sesión; antes pendiente aquí): los 4 notebooks leen
  `res.agent_patch` (TaskResult 0.2.11, models/task.py:162) con `generated_patch` como respaldo;
  nueva clase `parche_no_resuelto` (sustituye a `pruebas_fallan`, que el bug impedía emitir) y la
  fila de resultados registra además `error`. Huellas de configuración sin cambio (re-aseguradas
  con armar), preflight 24/24 ×4 verde, lógica ejercitada offline contra 9 casos simulados.
  Desviación declarada: réplicas 2-3 ya no son byte-idénticas en código de medición con la
  réplica 1 (el kit del agente sí lo es; la taxonomía de réplica 1 queda corregida a mano en
  docs/c7_fallos_r1.md).

## Track C: preguntas del dataset (22 GB, fuera del repo; `data/` cubierto por .gitignore)

**(i) ¿Los 3 paquetes de test del apunte 71→103 están en el wheelhouse? VEREDICTO: dead lever
confirmado (2026-10-17, comando del dueño sobre el wheelhouse local).** El único conjunto
candidato trazable es el del lock de desviaciones (`docs/desviaciones_entorno_wheels.lock`,
2026-10-03): typing-inspection 0.4.4, h11 0.16.0, dirty-equals 0.11 (faltantes entonces) +
python-multipart 0.0.18 (ya presente). `ls data/wheels/ | grep -iE "h11|dirty|typing_inspection|
python_multipart"` (115 ruedas): **typing_inspection 0.4.4 SÍ**, **python_multipart 0.0.18 SÍ**,
**h11 NO**, **dirty_equals NO** — 0 coincidencias para los dos test-only. Misma ausencia en
`ruedas/` del arnés (son solo las 4 ruedas del harness, no del entorno). Caveat: el trio exacto
de la nota 71→103 no se nombra en ningún archivo commiteado (la sesión web paralela lo
confirmó: el apunte no viajó al repo); con los candidatos trazables, la medición 71→103 no es
reproducible desde el wheelhouse mientras falten h11 y dirty_equals (starlette ya sube a 0.50.0
— el entorno evolucionó desde el lock). **Matiz del concilio 2026-10-17 (forense, verificado en
bytes)**: la ausencia vale solo para `data/wheels/` (espejo de Kaggle, 115 ruedas) — en
`data/build_sandbox_20261003_v2/wheels` (117 ruedas) **h11-0.16.0 y dirty_equals-0.11 SÍ están**;
la medición 71→103 queda executable en local con el build sandbox, no desde el espejo.

**(ii) tasks.jsonl (local, 2026-10-17): verificación contra EDA público — COINCIDE en todo.**
129 tareas — repos: fastapi/fastapi 67, Textualize/rich 48, psf/requests 13, encode/httpx 1.
`hints_text`: presente como campo en las 129 pero **VACÍO en 129/129** (el arnés soporta
`{hints}` en instrucciones, HARNESS_README §2.3, pero el dataset público no trae ninguna). Con
`hints_text` vacío universal, el conjunto «20 rich» **nunca fue una categoría de hints**: son
~20 tareas (28 rich tienen enunciado <300 chars) con enunciado corto título+link. Mediana de
caracteres del enunciado, local: fastapi 677, rich **138,5** (corrige el 146 anterior), requests
406, httpx 243. Medición futura: estratificar por repo × riqueza de enunciado × tamaño de
patch, **gateada por gold-patch-pass en nuestro propio harness** — los números públicos de
gold-patch se contradicen (109/129 vs «~la mitad»); solo vale el rerun local. Solo informe; no
se cambia nada.

## Flags de verificación
- **Presupuesto de 12 h de evaluación: VERIFIED-OFFICIAL (2026-10-17).** Cita verbatim de la
  página oficial (Overview → Evaluation), obtenida por fetch directo en la sesión web paralela y
  archivada aquí: «Your agent has a limit of 12 hours to submit patches for all tasks, inclusive
  of sandbox setup time, but excluding time for patch validation». Esto resuelve la bandera
  UNVERIFIED anterior (la página no era legible desde el CLI por JS/cookies). Sin discrepancia
  con el HARNESS_README (fija mecanismos por tarea, no el total); el notebook comunitario
  «12-Hour Budget» es solo un calculador sobre esa regla, no fuente normativa. La aritmética
  ~6 min/tarea de la §3 del manuscrito queda respaldada.
- **Límite diario de envíos: VERIFIED-OFFICIAL.** 1 envío/día y 2 selecciones finales
  (mecánica oficial de Submit Predictions; corroborado en vivo el 2026-10-16: tras subir sub-018
  la plataforma devolvió «0 submissions remaining today»).
- **Horas consumidas del presupuesto: sigue siendo del DUEÑO** (no hay endpoint legible desde
  aquí; ver en la página del concurso). Única gate de envío pendiente de dato.
- **sub-018 (57274153): SCORED 0.10 el 2026-10-17 05:15 UTC** (~13,75 h de evaluación;
  el «Notebook Running» no estaba atascado, era la evaluación completa). Comparación: vs **0.13**
  del kit viejo (i_razona) = −0.03 → **DENTRO DE RUIDO (±0.05)**; vs 0.10 de C2 = igual. La
  variante navegación-primero a 4.5 min **no batió al kit viejo** — el bottleneck observado en
  réplica (localizar→editar dentro del presupuesto) no se resolvió con el procedimiento de
  navegación solo. Cupo de pending liberado → Fase 2 ejecutada en el mismo despertar (sub-019).

## Lunes (cuota reiniciada): contraste de CINCO brazos
1. ~~Decidir el fix de `clase_fallo`~~ → APLICADO el 2026-10-16 (`bc17aea`, ver arriba).
2. Réplicas 2 y 3 de la condición 7 (brazo A; push v7/v8 de `replicas_c7/`, poller, pull,
   commits) → miden la **banda de ruido**.
3. Un run de cada variante sobre las mismas 20 tareas: navegación (`af8cca829561`), presupuesto
   (`52ba08ceac25`), thinking (`9d0db7b946e7`), **forrajeo (`fb8175c0e74e`, Project WORM)**.
4. **Coste estimado: 7 corridas × ~93 min ≈ 10,9 h de GPU en total** (2 réplicas de ruido + 5
   brazos; ≈1,5-1,7 h por corrida con carga de modelo ~6-19 min + 20 × 4,5 min + márgenes),
   dentro de los 30 h semanales con margen para reintentos. El forrajeo se corre como
   `kaggle kernels push -p experiments/gemma_developer_agent/replicas_c7_forrajeo -t 9000 --accelerator NvidiaL4`
   (kernel `cs4all/c7-forrajeo-condicion-7`, preflight 24/24 verde el 2026-10-17).
5. **Regla de decisión (fijada antes de correr)**: cualquier brazo que supere a A en más de la
   banda de ruido (medida en las réplicas 2-3; si la banda resulta ≥3 tareas, ninguna
   decisión) pasa a ser **candidato de envío para la semana siguiente**, sujeto a las gates de
   envío vigentes (reglas del concurso, horas consumidas del presupuesto de 12 h, límite diario).
6. Con todo: `docs/c7_ruido.md` + informe del contraste + episodio devlog + STATUS COMPLETE.
7. **Addenda del concilio 2026-10-17 (pre-registradas antes de correr)**:
   a. **Métrica de entrega: parche no vacío** (44/135 submits de la era estaban vacíos; `submit>0`
      solo cuenta intento). Leer con `clase_fallo` corregido (`bc17aea`) y verificar que
      `res.error` viaja en la salida.
   b. **Regla de empate**: banda observada 0-2 flips; ventaja ≤3 tareas ⇒ exploratorio + réplicas
      del líder con la cuota restante. Veto a adoptar con Δ≤3.
   c. El brazo thinking (`9d0db7b946e7`) mide «thoughts ocultos vs visibles», NO thinking-off.
      **Sexto brazo R1-fiel CONSTRUIDO y REESPECIFICADO el 2026-10-18 a 5.0 min**
      (`replicas_c7_r1fiel/`): `thinking_budget:0` + 5.0 min + prompt byte-identico a A (delta
      puro), huella **`5e1638518420`**, preflight 24/24, armar ×5 sin deriva, kernel
      `cs4all/c7-r1fiel-condicion-7`. La reespecificación (antes 6.0, huella obsoleta
      `3a28671c4f60`) responde a una regla atribuida al equipo de Google en los foros
      («~5,5 min/tarea incl. setup») que NO pudo verificarse desde el repo: 5.0 es seguro bajo
      ambos muros, probado en producción (sub-019) y deja un A/B limpio vs sub-019 aislando solo
      `thinking_budget`. Si la regla de 5,5 min se verifica el lunes, el kit ya cumple; si se
      refuta, 5.0 sigue siendo el diseño correcto (A/B limpio). Correrlo decide el dueño tras
      réplicas 2-3 y gold-patch, reconciliando cuota con la reserva del concilio 50.
   d. **Gold-patch CPU tiene bloqueo hoy**: faltan 82/129 snapshots (48 fastapi/33 rich/1 httpx; 47
      cubiertas) y el venv del arnés (google-genai/litellm/docker-sdk; ruedas h11/dirty_equals en
      `data/build_sandbox_20261003_v2/wheels`). Decisión del dueño: descargar los snapshots o
      correr las 47 cubiertas; driver escrito en
      `analisis_c7/guiones_concilio_2026-10-17/forense/gold_patch_local.py`.
   e. Contar la «cosecha del árbol» (resuelta sin `submit_patch`, caso rich_3043) como entrega
      válida al leer resultados ajenos.
8. **sub-019 SCORED 0.17 (2026-10-17 20:39 UTC)** — A/B limpio vs sub-018 (solo max_time_minutes
   4.5→5.0): **+0.07 fuera de ruido**; el muro SÍ era cuello del score. nav-v2 = mejor envío
   propio; re-medir nav@5.0 local el lunes antes de que un brazo lo supere; la predicción sellada
   quedó FUERA por arriba (apéndice A5 del análisis crítico).

## Auditoría de la página de submissions (2026-10-18 00:20 UTC)

- **Reconciliación completa**: la plataforma tiene **8 envíos completados** — refs 57296502, 57274153,
  57160374, 57098570, 56916129, 56895202, 56830336, 56808559 = sub-019, sub-018, sub-010, sub-008,
  sub-006, sub-005, sub-003, sub-002. Esto **resuelve el `num_total=8`** de la API de límites
  (antes NO VERIFICADO): cuenta los envíos completados en plataforma; los otros 11 del registry
  están `prepared` (nunca enviados). Sin envíos huérfanos ni faltantes.
- **Descripciones**: solo sub-018 y sub-019 llevan método + huella + enlace al repo (requisito de
  reproducibilidad cubierto por el mejor envío). Los 6 envíos más viejos tienen notas cortas sin
  enlace. **Las descripciones NO se pueden editar a posteriori**: el SDK del CLI no expone ningún
  endpoint de actualización de envío (solo `update_competition_page`/`update_competition_settings`,
  que son de la competencia, no del envío). Nada que «completar» ahí; queda registrado.
- **Selecciones finales**: 0/2, sin tocar (protocolo §Fase F: revisar con cada score ≥0.17 y el
  30-11 23:59 UTC). La mecánica de selección es manual en la UI; el cron del lunes lo recuerda.
- **Acción del dueño en esa página hoy**: ninguna obligatoria. La página queda como tablero de
  lectura; todo lo demás (registro, predicciones, huellas) vive en el repo.

## Reglas del concurso — verificación 2026-10-18 (respuesta a «¿hay alguna regla que desconozco?»)

**Mecánica del cupo (Fase B, 2026-10-18)**: 1 envío/día **VERIFICADO** en vivo («0 submissions
remaining today» tras sub-018, 2026-10-16). **Hora de reset**: no expuesta por CLI; evidencia
circunstancial a favor de **~00:00 UTC** (sub-019 aceptado 05:18 UTC del 17 tras sub-018 de
15:30 UTC del 16 — no es rolling-24h). Se confirma observando el domingo (Fase C: la hora UTC
del rechazo/aceptación queda en registry notes). **Tope total de envíos**: **no visible vía CLI**
(el cliente no expone el límite para esta competencia) — documentado como NO VERIFICADO con
evidencia empírica favorable (19 envíos en 3+ semanas sin tope alcanzado); condición (b) del
envío dominical se apoya en eso. Detalle operativo re-verificado: la plataforma exige el nombre
`submission.zip` y un rechazo por cupo/pending **no** consume el slot (dos rechazos el
2026-10-17 01:50/01:56, slot intacto). Verificación de foros (regla ~5,5 min, 2 selecciones
finales, LB 50%, variantes): **HECHA el 2026-10-17 22:00-22:40 UTC** con la sesión del CLI vía
`kagglesdk` (guion `analisis_c7/leer_foro_kaggle.py`; páginas oficiales y 29 hilos volcados en
`data/foro_kaggle/2026-10-18/`, gitignored) — tabla «Fase B» más abajo.

**Por qué esperar al lunes no es una regla oculta**: (1) la cuota GPU semanal del dueño está
bloqueada hasta el lunes (reinicio semanal, observado dos semanas seguidas); (2) la regla
pre-registrada de la campaña retiene el slot diario salvo ganador local > 0.17 + banda; (3) el
cupo de 1 envío/día se observó en vivo («0 submissions remaining today»). No hay premura:
**deadline principal 2026-12-02 23:59** (CLI oficial; corrige el «25 nov» del documento del
dueño — hay ~6,5 semanas; el «2 nov» de la prensa es probablemente el cierre de altas/merge).

**Verificado por CLI (2026-10-18)**: deadline 2026-12-02; **Paper Track
`gemma-4-developer-agent-paper`: deadline 2026-11-12, 35.000 USD, 249 equipos, equipo YA
inscrito** (userHasEntered=True) — el manuscrito del repo es candidato natural y no gasta slot;
3.061 equipos; rank 853.

**Fase B — reglas verificadas con lectura autenticada (2026-10-17 22:00-22:40 UTC)**. Fuentes: páginas
oficiales de la competencia (Evaluation, Rules, Model Selection…, Data) leídas por la API, hilos del
foro (id = `/discussion/<id>`) y la API de límites. La API no expone el autor de cada mensaje: «host»
se atribuye cuando el mensaje responde a @ryanholbrook con voz de organizador.

| Regla | Estado | Fuente y fecha |
|---|---|---|
| **a. Semántica de las 12 h**: es **un solo presupuesto para toda la corrida**, secuencial, **incluye** la preparación del sandbox y **excluye** la validación de parches; los límites por tarea en `eval_config.yaml` son opcionales. Superar las 12 h hace **fallar el envío entero**; el arreglo «no terminadas = 0» sigue **sin implementar** y el host duda de él («could lead to inconsistent results on the public and private leaderboards»). | **VERIFICADO**. La semántica **no cambió**: nunca hubo tope por tarea impuesto; el envelope de 5.0 min (698 min peor caso ≤ 720) sigue válido. | Página Evaluation (texto oficial); hilo 743063, respuesta del host 2026-09-24 («Sequentially… hitting the 12-hour limit will error»); hilo 749597, respuesta 2026-10-15. |
| **b. Errores y rechazos no queman cupo**: rechazo por cupo o por envío pendiente (`FAILED_PRECONDITION`) **no consume** el slot (propio, 2 rechazos el 2026-10-17); «Kaggle Error» de plataforma: el host anunció recuperación en lote **sin reenviar** («No action needed: You do not need to resubmit»); existe un **límite de 1 envío pendiente por equipo**, separado del 1/día. Un envío con estado «Kaggle Error» **no consume** el envío: respuesta del host en el mismo hilo («Kaggle Error should not consume a submission anyway»; la recuperación en lote fue única, para el timeout de cola). Sí se **pierde** el día si el envío anterior sigue pendiente cuando resetea el cupo (host: «It's possible, yes, that you will lose a daily submission this way»). Sobre el arreglo de las 12 h el host añade: «I may not implement this». API de límites (2026-10-17 22:10 UTC): `limited_by_total=false` (**sin tope total, VERIFICADO**), `max_daily_submissions=1`, `num_today=1`, `num_allowed_now=0` (sub-019 fue a las 05:18 UTC → el día no ha reseteado a las 22:10: **CONFIRMADO: reset a las 00:00 UTC** — lectura 00:04 UTC del 18: `num_allowed_now=1`, `num_today=0`, `limited_by_total=false`), `num_total=8` (qué cuenta ese 8 frente a los 19 envíos propios: NO VERIFICADO). | **VERIFICADO** (salvo lo marcado) | Hilo 747519 (sticky, host, 2026-10-08); `ApiGetSubmissionLimits`; registro propio 2026-10-17. |
| **c. Origen de «~5,5 min/tarea»**: es **aritmética de participantes** (720 min / ~120 tareas), **no una regla del host**. El autor de la frase que citó el dueño («even 6 min cap is out of reach») escribe dos días después: «a 5.5-minute cap allows up to 11 hours of agent time… **This is our chosen budget, not a competition rule**». Kits públicos de 8 min / 28 llamadas han puntuado (Budget-Fit declara una corrida puntuada < 12 h; equipos en 0.18-0.20). | **REFUTADA como regla** (la atribución a Google era errónea). R1-fiel a 5.0 sigue siendo un diseño seguro; 6.0 nunca estuvo prohibido, solo arriesga el envelope. | Hilos 746469 (2026-10-07), 746250 (comentario), 747857 (2026-10-09), 748618 (2026-10-12). |
| **d. Pytest 8 / httpbin en requests**: conftest antiguo con fixture `httpbin` recursiva → error de colección en pytest 8.4.2 → `resolved=False` aunque el parche sea el gold; `conftest.py` es protegido (se revierte). Además 8 tareas requests son irresolubles en py3.13 por el certificado de pytest-httpbin (6589, 6592, 6629, 6757, 7328, 7433, 7502, 7505): coinciden con 8 de nuestras 10 gold-fallan de requests (las otras: 6644, 7205). **Lo decisivo**: el host confirma que el set oculto está filtrado y que «a submission with "gold patches" validates at 100%» → los 52 gold-fallan son del set público/local, no del scorer. Impacto en el set medible: ya excluidas por el gold local; requests aporta 3 medibles. | **VERIFICADO** (local + foro). «fastapi ambiental de campo» **confirmado como fenómeno local/público**: 21/67 fastapi públicas importan `dirty_equals`/`inline_snapshot` ausentes en `data/wheels`; `task_soundness.csv` del organizador muestra el gold pasando en scoring. | Hilos 750253 (2026-10-17), 743973 (2026-09-28), 744259 (respuesta del host 2026-09-29), 750345 (2026-10-17), 745775, 747248. |
| **e. Dos Final Submissions**: «You may select up to two (2) Final Submissions for judging»; «Final Submission» = la elegida por el usuario o automáticamente por Kaggle; el LB privado decide. **Cómo se combinan**: las reglas del concurso **no lo dicen**; el comportamiento estándar de la plataforma es «cuenta la mejor de las seleccionadas en el privado». LB público = «representative sample»; data description: «about 120 tasks… evenly divided between the public and private splits» (58 públicas inferidas por granularidad). | «Hasta 2» **VERIFICADO**; «mejor-de-2» **NO VERIFICADO documentalmente** (sin fuente abierta en esta sesión; se asume provisionalmente); 50 % **VERIFICADO**. | Rules §2.b y foundational §c/§e/§f; página Data; hilo 743506 (2026-09-26). |
| **f. Variantes entre envíos**: cuatro variantes soportadas (`31b`, `12b`, `e4b`, `e2b`); «Every agent and subagent in your submission must use the same variant» → la restricción es **por envío**; nada prohíbe que envíos distintos usen variantes distintas. | **FAVORABLE, VERIFICADO** por el texto oficial. **Riesgo operativo**: tres equipos reportan «Notebook Threw Exception» al enviar con 12B el mismo bundle que puntúa con 31B (2026-10-14/15); al 2026-10-16 no hay un 12B puntuado de extremo a extremo confirmado en público. | Página «Model Selection, Budget, and Harness Rules»; hilo sticky 748287 (host, 2026-10-11); hilo 749259. |
| g. (extra) Thinking: desde `adk_submission 0.2.13` `include_thoughts:false` ya **no** apaga el pensamiento; `thinking_budget:0` sí. «This was intended. My apologies.» | **VERIFICADO** (confirma el hallazgo del concilio 51) | Hilo 747914 (host, 2026-10-10). |
| h. (extra) Tope de compute del notebook y colas: las corridas de scoring tardan 13-46 h por cola; un participante afirma que las 12 h cuentan desde el inicio de la corrida, no desde el envío. | NO VERIFICADO por el host | Hilo 748443 (2026-10-12). |

## Fase 0 (fin de semana 2026-10-17, 0 GPU-h — plan del dueño procesado del log)

- **Gate anti-patch-vacío IMPLEMENTADO** (medición, no el contrato de envío): las 6 fuentes
  `notebook_c7_*.py` registran por tarea `parche_bytes`, `parche_sha256` (16 hex) y
  `parche_no_vacio` (la cosecha del arnés cuenta como parche si viajó en `agent_patch`).
  Huellas de kit SIN cambio (af8cca829561 / 52ba08ceac25 / 9d0db7b946e7 / fb8175c0e74e /
  3a28671c4f60), armar ×6 sin deriva, preflight 24/24 ×6, ruff/format limpios. Desviación
  declarada: código de medición ya no byte-idéntico con réplica 1 (mismo precedente que
  `bc17aea`); el kit del agente sí lo es.
- **Frontera de fallos registrada**: [`docs/c7_frontera_2026-10-17.md`](docs/c7_frontera_2026-10-17.md).
  Corrección de observabilidad: las ~48 no resueltas de sub-019 NO son observables (Kaggle no
  publica por tarea); la frontera real observable = 41/48 tareas nunca resueltas localmente;
  top-3 clases: parche_no_pasa 51, llamadas_agotadas_sin_parche 34, sin_parche 27 (parte del
  `sin_parche` era el bug ya corregido).
- **Gold-patch CPU HECHO** (H1 del plan): venv `/tmp/venv_gold` (4 ruedas del arnés + google-genai/
  litellm/docker), driver corregido (el del forense importaba `DockerSandboxManager`, inexistente
  en 0.2.11; el real es `ContainerManager` + `ContainerConfig(image=config.image)`). Resultado en
  [`analisis_c7/gold_results_2026-10-17.jsonl`](analisis_c7/gold_results_2026-10-17.jsonl):
  **20/129 con snapshot local (15 rich + 5 fastapi), 109 sin snapshot; gold-pasa 15/20**
  (rich 13/15, fastapi 2/5) → **conjunto medible real hoy = 15 tareas**.
  **Corrección de precisión**: el concilio contó «47 cubiertas / 82 faltantes»; el conteo real en
  `data/snapshots/` es **20 cubiertas / 109 faltantes** (auditor incluido — el dictamen se
  corrige aquí). En el set sustituto de 20: 15 cubiertas, **13 gold-pasan, 2 gold-fallan**
  (rich_3472 y rich_4079 — de las 4 «ganables» del QA, 2 no pasan el gold local). La contradicción
  pública (109/129 vs «~la mitad») se matiza: en el subconjunto cubierto pasa el 75%.
  Implicación para el lunes: la decisión de descargar snapshots (tuya) pesa más con 109 faltantes;
  el pre-screening local arranca sobre una base de 15 tareas (todas rich salvo 2 fastapi).
  Matiz del plan: la «calibración contra los 3 scores» sigue sin poder ejecutarse en CPU puro
  (exige corridas locales de los kits = GPU); lo entregado es el conjunto medible.
- **Gold-patch CPU COMPLETO sobre 129/129 (2026-10-18 ~21:55 UTC, tras construir los 109
  snapshots en `aa50041`)**: resultado en
  [`analisis_c7/gold_results_2026-10-18.jsonl`](analisis_c7/gold_results_2026-10-18.jsonl)
  (129 filas, 129 ids únicos, ninguna sin snapshot; 19,8 min de CPU, 9,2 s/tarea de media,
  máx. 33 s). **gold-pasa 77/129, gold-falla 52/129 → conjunto medible nuevo = 77 tareas**
  (antes 15). Por repo: rich **39/48** pasan (9 fallan), fastapi **35/67** (32 fallan, 48 %),
  requests **3/13** (10 fallan), httpx **0/1**. Los 52 fallos son ambientales del arnés local
  (51 con exit 1 de pytest sin mensaje; 1 rich con «Required test node did not pass»): el gold
  no puede «no resolver» su propia tarea. Anotación **«fastapi ambiental de campo»**: el dueño
  reporta hilos del foro donde el gold patch tampoco pasa en el evaluador (faltan dependencias
  de test) y un quirk pytest 8 / httpbin en requests → su estado de verificación va en §Reglas
  (Fase B). Consistencia con la corrida del 17: las 2 gold-fallan del set sustituto (rich_3472,
  rich_4079) siguen fallando → el techo local del set de 20 sigue en 13/20. Implicación para el
  lunes: las comparaciones de brazos se normalizan por el conjunto medible de 77; un fallo del
  agente en una tarea gold-falla no cuenta como «no resuelta» del agente. Guion:
  `analisis_c7/guiones_concilio_2026-10-17/forense/gold_patch_local.py` (sin cambios; salida en
  `/tmp/gold_rerun_d2`, copiada al repo).
- **Cron de campaña del lunes**: despertador 08:00 -03:00 (2026-10-19) que arranca el runbook
  §Lunes (quota check → réplica 2 → poller → …). Cancelable/modificable con el id en CronList.
  **Sustituido** el 2026-10-18 por el cron de la sesión de cierre (ver §«Crons de esta sesión»): el
  de la sesión Kimi murió con ella.

## Cierre de noche 2026-10-18 (Fases A-F del plan del dueño, log 4; sesión Claude Code en WSL)

Todo con 0 GPU y **sin enviar nada**. Commits de esta sesión en `exp/kaggle-c7-replicates`.

- **Fase A — gold completo**: hecho, ver arriba (§Fase 0, bullet «Gold-patch CPU COMPLETO»): 77/129
  medibles; conteos por repo rich 39/48, fastapi 35/67, requests 3/13, httpx 0/1.
- **Fase B — foro**: hecho, tabla en §Reglas («Fase B — reglas verificadas»). Resumen: (a) las 12 h
  **no cambiaron**: siempre fueron un solo presupuesto por corrida; (c) la regla «~5,5 min» era
  aritmética de un participante («not a competition rule»), no de Google; (e) hasta 2 finales,
  combinación no escrita en las reglas (asumido «mejor-de-2»); (f) variantes distintas entre envíos
  **permitidas**, pero el scorer falla con 12B según tres reportes.
- **Fase C — estudio del baseline «0.24»**: [`docs/c7_baseline024_estudio.md`](docs/c7_baseline024_estudio.md).
  Hallazgo: **ningún autor de esos notebooks tiene 0.24** en el LB (0.18-0.20; solo 2 equipos de
  3.043 tienen 0.24); la receta pública difiere en 8 min / 28 llamadas / 240 s / un agente / «edita
  antes de la llamada 12». **Decisión (b)**: híbrido nav-v2 + `eval_config` público como brazo del
  lunes con tres gates pre-registradas (≥ 6/20; media × 120 + 90 min ≤ 660 min; ≤ 3/20 con llamadas
  agotadas sin parche), sin abandonar (c). Corrección colateral: **R1-fiel no es A/B limpio contra
  sub-019** (prompt distinto, verificado por sha256; `replicas_c7_r1fiel/README.md` corregido).
- **Fase D — brazo 12B construido** (`replicas_c7_12b/`, huella **`adb3004b2f76`**, armar ×5 sin
  deriva, **preflight 24/24 «Se puede subir»**, override de vLLM del host incluido, README con
  riesgos). Arreglo colateral: el simulador de `scripts/kaggle_preflight.py` fijaba el directorio
  del 31B y hacía fallar la guardia de cualquier otra variante; ahora lee `model_sources` del
  `kernel-metadata.json` (`modelo_de_metadatos`, con test propio; R1-fiel sigue 24/24). **No se
  corre ni se envía** hasta ver un 12B puntuado de extremo a extremo en el foro.
- **Fase E — outline del paper** actualizado (`docs/paper/paper_track_outline.md`): requisitos y
  rúbrica del track verificados por la API (3.000 palabras máx., Writeup o PDF, cinco criterios),
  A5, hallazgo fastapi de campo, contexto 0.24, modelos chicos, amenazas a la validez (nueve puntos),
  presupuesto re-chequeado = 3.000.
- **Fase F — selecciones finales**: **0/2 elegidas a mano** (auto = 0.17 + 0.13, verificado en la UI
  por el dueño). **Protocolo**: revisar las selecciones (1) con cada score nuevo ≥ 0.17 y (2) **48 h
  antes del cierre: 2026-11-30 23:59 UTC** (deadline 2026-12-02 23:59 UTC). Regla de combinación
  (Fase B, fila e): si la plataforma cuenta la mejor de las dos (estándar, no escrito en las reglas),
  la 2ª selección se elige **diversa** (otra familia: tiempo/presupuesto vs thinking/forrajeo) como
  cobertura del 50 % privado; solo si se verificara «promedio», top-2. Mientras no se verifique:
  **mejor-de-2 → diversa**. Nada se selecciona todavía.
- **Predicción sellada sub-020** (R1-fiel): `analisis_c7/predicciones.csv`, fila
  `sub-020_LB_score` 0.17 [0.13, 0.21], sellada 2026-10-17 22:45 UTC **antes** de cualquier envío,
  con la advertencia de que no es A/B limpio.
- **Zip de R1-fiel listo, NO enviado**: `data/envios/submission_r1fiel_2026-10-18.zip` (3.491 B,
  6 archivos, huella `5e1638518420` recomputada, `verify` VÁLIDO, compilado con adk-submission
  0.2.13 — `thinking_budget=0` visible en la config compilada), **sha256
  `82a8ea619e5babb3f0287ed36c38221a3ee4f79091cea0634aa52ecddd90c1de`** (sin colisión en el registro).

## Crons de esta sesión (2026-10-18; sesión Claude Code; mueren si la sesión se cierra)

Los crons de la sesión Kimi (`01M55X4Z0TYD7392AHVP4AVSV9` envío dominical; `01M55WZC45XCQA2QWV8T1TX3KB`
lunes) **sobrevivieron** (la sesión siguió viva; la sesión Claude paralela no los veía). El envío
dominical quedó **actualizado el 2026-10-18 00:10 UTC** para usar el zip ya verificado. Estado:

| Cron | Id | Estado |
|---|---|---|
| 2026-10-17 21:04 -03 (00:04 UTC): leer la API de límites y anotar en §Reglas b si el reset es a las 00:00 UTC | `2dc96c0e` | **ejecutado**: reset a las 00:00 UTC confirmado (`num_allowed_now=1`, `num_today=0`); el slot del domingo está disponible desde las 00:00 UTC, no hace falta esperar a las 12:00 UTC |
| Domingo 09:00 -03 (12:00 UTC): envío condicionado sub-020 (R1-fiel) con 4 condiciones + zip pre-verificado | `01M565FDVDPWM2TSH1033FX23N` (re-creado 00:10 UTC) | **activo** — el ÚNICO camino que envía; nada más envía |
| Lunes 08:00 -03 (11:00 UTC): despertador del runbook con conciencia de sub-020, paso 0.5 (híbrido) y 12B | `01M565GSZBDYJ9QWVEAH77BT29` (re-creado 00:10 UTC) | **activo** |

**Lo que el dueño decide sobre el domingo.** El envío de R1-fiel ya no es automático. Si decide
hacerlo (por la UI o por el CLI, como con sub-018/019), las cuatro condiciones reconstruidas del plan
son hechos a comprobar antes: (a) cupo diario disponible (la API de límites debe dar
`num_allowed_now >= 1`; si el reset no es a medianoche, el segundo intento del plan era a las 19:00
UTC); (b) sin tope total (`limited_by_total == false`, ya verificado); (c) ningún envío del equipo
pendiente (la última fila de `submissions` sigue siendo 57296502 COMPLETE 0.17); (d) el zip íntegro
(sha256 `82a8ea61…c1de`, huella `5e1638518420`) y la predicción sellada presente en
`predicciones.csv`. El nombre que exige la plataforma es `submission.zip`; la descripción del envío
debe citar la huella, la predicción sellada y el repositorio del método, como en sub-019. Tras un
envío: registrar con `scripts.kaggle_submission register --condition r1fiel` (en `/tmp/venv_pack`),
anotar ref y hora aquí y en §Kit v2, commit `feat(kaggle)` y suite verde antes del push. Si no se
envía, el slot del domingo se pierde (no se acumula) y el lunes sigue igual. Evidencia nueva **en
contra** de enviar R1-fiel: no es A/B limpio vs sub-019 y una ablación pública (no verificada) predice
que apagar el pensamiento reduce a la mitad las resueltas; **a favor**: el slot es gratis, la
predicción está sellada y el LB conserva el mejor score.

## Concilio C7 Fase 4 (2026-10-17, vuelta 49 / concilio 51)

Pregunta: ¿las recomendaciones de Fase 4 del análisis crítico se sostienen y qué falta medir para
el lunes? Procedimiento completo del skill (recall+rescate → 4 roles en paralelo → revisión
cruzada sin firma → auditor → registro). Bitácora completa con los pareceres tal cual:
[`docs/c7_concilio_2026-10-17.md`](docs/c7_concilio_2026-10-17.md). Dictámenes del auditor (mandan)
y cambios operativos:

- **Correcciones al análisis crítico** (hechas, con guiones comiteados en
  `analisis_c7/guiones_concilio_2026-10-17/`): muro **13/20 (65%)** timeouts y **12/16 (75%) de
  los fallos** (no «15/20»); submit réplica 1 **7/20 (35%)** intento-ok y 4/20 resolución (44/135
  submits de la era vacíos → métrica del lunes: **parche no vacío**); **18/148 ≥230 s** (el
  «0/148» era falso); A1 10,5× fila / 5,1× tarea única; era 2026-10-06 = **thoughts ocultos
  (budget 4096), no thinking-off**.
- **El brazo thinking del lunes (huella `9d0db7b946e7`) NO prueba R1**: `include_thoughts:false`
  solo oculta pensamientos; el apagado real exige `thinking_budget:0` (verificado en código del
  compilador; el validador inyecta budget=max si falta). Sexto brazo R1-fiel propuesto:
  `thinking_budget:0` + **6,0 min** (el envelope rechaza 9-10 min: a f=0,65 no caben; 6 min = 641
  min de 720) + prompt de A, delta puro de config. Construcción 0 GPU-h; correrlo es decisión del
  dueño (después de réplicas 2-3 y gold-patch, y reconciliando cuota con la reserva del
  concilio 50).
- **Regla de empate PRE-REGISTRADA hoy**: banda A-vs-A observada 0–2 flips; ventaja ≤3 tareas ⇒
  resultado exploratorio + réplicas del líder con la cuota restante; banda ≥3 ⇒ nada se adopta.
  Veto: no adoptar con Δ≤3 (p≈0,24–0,43), no decidir por `submit>0` sin filtrar vacíos.
- **Gold-patch CPU no ejecutable hoy**: faltan 82/129 snapshots (48 fastapi/33 rich/1 httpx; 47
  cubiertas) y el venv del arnés (google-genai/litellm/docker-sdk). **Corrección al Track C(i):
  h11-0.16.0 y dirty_equals-0.11 SÍ existen en `data/build_sandbox_20261003_v2/wheels`** (no en
  `data/wheels/`, espejo de Kaggle — dos directorios distintos).
- **rich_3043 resolvió sin `submit_patch`** (cosecha del árbol al timeout, verificado en bytes) —
  corregido `c7_fallos_r1.md` (addendum 2); el arnés acepta entregas no confirmadas por el agente.
- Set sustituto: solo **4/20 tareas ganables** (16 ceros estructurales); la banda 0-2 hace la
  regla del lunes justa pero de rango casi nulo — la regla de empate cubre ese hueco.
- **Sexto brazo R1-fiel construido y reespecificado a 5.0 min** (2026-10-18; ver §Lunes
  addendum 7c): la regla no verificada de «~5,5 min/tarea» del evaluador se resolvió con
  robustez — 5.0 cumple bajo ambos muros y deja A/B limpio vs sub-019.
- Fallo de la vuelta (orquestador): recall inicial sin episodios 100-101 (rama no al día con
  main) — detectado en vuelta, merge `origin/main` hecho y recall repetido; queda en el episodio.
- Diversidad declarada: los 5 roles son el mismo modelo (quitar firmas evita deferencia, no da
  diversidad). Nuevos hallazgos en `hallazgos.json` (primera_vuelta 49); ningún hallazgo abierto
  previo fue re-medido en esta vuelta.

## Project WORM (2026-10-17): del documento de gusanos a un quinto brazo

- **Mapeo**: `docs/c7_gusano_mapping.md` — extracción con citas de los cuatro niveles de autonomía,
  la paradoja del lazo cerrado de BAAIWorm (lazo abierto «extremadamente similar»; cerrado, menos
  regular que el animal), pirueta/sesgo + secuencia local ~15 min → global, habituación con
  entrenamiento espaciado (4 bloques × 1 h para memoria de 24 h), y «la conectividad sola no
  basta»; con el análogo en el arnés (HARNESS_README §2.2, §5.3, §6.1, §6.3) por principio.
- **Quinto brazo construido**: `replicas_c7_forrajeo/` (WIP, sin subir ni correr). Único cambio:
  `prompts/system.md` con la «Foraging Policy» de 298 palabras (búsqueda local primero con
  escalada a ~⅓ del presupuesto, reorientación tras dos intentos estériles, habituación a fallo
  repetido, cierre de lazo actuar); cada principio etiquetado en comentario HTML con su fuente
  biológica. Huella de configuración **`fb8175c0e74e`** (fórmula del manuscrito, recomputable con
  `armar_notebook_forrajeo.py`; kit de referencia = descarga de réplica 1 sin `adapters/`).
- **Verificación**: armar ×5 reproduce las 5 huellas sin deriva; preflight 24/24 «Se puede subir»
  ×5; ruff check/format y mypy verdes; verificador de frontera 0 colisiones de ruta y 0 de hash
  (corrida 2026-10-17; INCOMPLETO solo por los 4 `.safetensors` root conocidos, sin impacto en lo
  versionado); pytest completo 3479 passed / 5 skipped / 0 failed.
- **Paper**: `docs/paper/manuscript_en.md` §4.8 «Discussion: Levels of autonomy, biological
  precedent» commiteado en main (`36b942a`): tabla de mapeo, paradoja BAAIWorm como
  justificación del measure-before-submit, y el negativo de calibración conectado a
  «connectivity alone is insufficient» **etiquetado como framing analógico, no evidencia**; §6
  con la huella forrajeo y la lista [PENDING — Monday] de 7 corridas (10,9 h ≤ 30 h).
- **Reanudación exacta**: es la sección «Lunes» de arriba; el brazo forrajeo se corre con el
  comando del punto 4 tras las réplicas 2-3 y las variantes previas, mismas 20 tareas
  (`tareas_c7.json` ids_20_rich).

## Siguiente (resume EXACTO para la sesión que reanude, tras el reinicio semanal de cuota GPU)
1. `cd '/mnt/f/Code/Agents Learning Loops' && git switch exp/kaggle-c7-replicates` (ya estará).
2. Verificar cuota disponible: ` .venv-linux/bin/kaggle kernels push -p experiments/gemma_developer_agent/replicas_c7 -t 9000 --accelerator NvidiaL4` — si da error de cuota otra vez, parar y esperar.
3. Ese mismo push crea la versión v7 = **réplica 2/3** (código idéntico, ya commiteado). Poner un poller en background (sleep 240 + `kaggle kernels status -k cs4all/c7-replica-condicion-7` cada 5 min, hasta estado terminal, timeout 14.400 s).
4. Al COMPLETE: ` .venv-linux/bin/kaggle kernels output -k cs4all/c7-replica-condicion-7 -p experiments/gemma_developer_agent/data/replicas_c7/replica_2 -o -q`; validar `salida__*.json` (20 filas, huella `0f52de0b84cb`, cortado_por null); actualizar `docs/replicas_c7_progreso.md`; commit.
5. Repetir push v8 = réplica 3 → poller → pull a `replica_3/` → commit.
6. Con las 3 réplicas: escribir `docs/c7_ruido.md` (formato del repo; (a) resueltas por réplica,
   (b) flips por tarea = banda de ruido, (c) dónde cae el 9/19 original — declarando que el conjunto
   es sustituto y no comparable tarea a tarea, (d) denominadores explícitos 20 y 19); commit.
7. Episodio `learning/episodes/101-exp-kaggle-c7-replicas.json` (learning/README.md; estimate M,
   outcome real: v1–v6 fallos+fixes, 1 réplica, bloqueo de cuota); commit. STATUS → COMPLETE.

## Hecho
- T1 (diagnóstico envío caído): error de plataforma de Kaggle («A system error. Please try
  resubmitting…» / descripción vacía); 56895202 y 56916129 puntuaron 0,08/0,13. Commiteado (1f40d2e).
- Config condición 7 verificada por huella 0f52de0b84cb (== zip enviado). Paquete replicas_c7 con
  preflight verde.
- Secrets: Kaggle autenticado (`~/.kaggle/access_token`, 600; CLI 2.2.4 lista competiciones).
  GitHub token 401 → **el dueño debe regenerar el PAT en GitHub Settings** (no reintentar).
- Verificador de datos: **0 colisiones** de contenido. INCOMPLETO solo por 4 `.safetensors` de
  `data/` propiedad de root con `rw-------` sobre /mnt/f (drvfs no aplica chmod; sudo -n tampoco
  cambia perms en drvfs). Sin impacto en los archivos versionados.
- Reejecución de `verify_no_competition_data.py` en Windows con red/API Kaggle deshabilitada:
  manifiesto 8 hashes + datos locales 6.617 hashes; 47 archivos versionados, 0 colisiones por
  ruta/nombre y 0 por SHA-256; `[VERIFICADO]`. No se reutilizó el token expuesto. Esta corrida local
  completa no sustituye una comprobación por nombres de la API.
- Conjunto de 19 tareas original: irrecuperable (evidencia en replicas_c7/tareas_c7.json).

## Ahora
- **Estado: CERRADO hasta el lunes 2026-10-19** (reinicio de la cuota GPU). Todo el código está
  commiteado, verificado y empujado; sub-018 en PENDING la vigía el cron (reglas a/b/c).
- **Próximo paso exacto**: la sección «Lunes» de arriba (5 brazos + 2 réplicas de ruido) y el
  «Siguiente (resume)» de abajo. Kernel ids: `cs4all/c7-replica-condicion-7` (A, v6=v1 hecha;
  push v7/v8 = réplicas 2-3), `cs4all/c7-navegacion-condicion-7`, `-presupuesto-`… los metadatos
  de cada kernel están en su `kernel-metadata.json`.

## Siguiente (resume EXACTO — lunes 2026-10-19, cuota reiniciada)
0. `git switch exp/kaggle-c7-replicates` (ya está) y spot-check: los 5 armar corren y reproducen
   huellas (A `0f52de0b84cb`, nav `af8cca829561`, presupuesto `52ba08ceac25`, thinking
   `9d0db7b946e7`, forrajeo `fb8175c0e74e`); preflight 5/5 «Se puede subir».
1. **Réplica 2 (A)**: `kaggle kernels push -p experiments/gemma_developer_agent/replicas_c7
   -t 9000 --accelerator NvidiaL4` → crea v7. Si responde error de cuota semanal: PARAR, anotar
   mensaje literal, esperar (no reintentar en bucle).
2. Poller en background (sleep 240 + `kaggle kernels status -k cs4all/c7-replica-condicion-7`
   cada 5 min, hasta terminal, timeout 14.400 s). Al COMPLETE:
   `kaggle kernels output -k cs4all/c7-replica-condicion-7 -p experiments/gemma_developer_agent/data/replicas_c7/replica_2 -o -q`;
   validar salida (20 filas, huella `0f52de0b84cb`, cortado_por null); commit.
3. **Réplica 3 (A)**: mismo ciclo (push → v8) hacia `replica_3/`. Con réplicas 1-3: banda de
   ruido = flips por tarea entre las tres.
4. **Cuatro variantes**, en este orden (mismo patrón push → poller → pull → validar → commit;
   datos bajo `data/replicas_c7/<variante>_run1/`): nav (`-p …/replicas_c7_nav`), presupuesto,
   thinking, **forrajeo** (`cs4all/c7-forrajeo-condicion-7`). Verificar en cada salida la huella
   de su brazo y 20 filas.
5. **Análisis**: `docs/c7_ruido.md` (formato del repo; resueltas por corrida, flips por tarea,
   dónde cae el 9/19 original declarando el conjunto sustituto, denominadores 20/19) + informe
   del contraste. Regla de decisión fijada: un brazo solo cuenta si supera a A en MÁS de la banda
   de ruido; banda ≥3 tareas → ninguna decisión. El ganador pasa a candidato de envío de la
   semana siguiente, sujeto a gates (1/día oficiales, horas consumidas del dueño, sin duplicados
   de contenido).
6. **Cierre de campaña**: episodio devlog (101/102 según numeración vigente) + STATUS COMPLETE.
   Si a mitad cae la cuota o la sesión: registrar ids/URLs de kernels lanzados aquí y STOP.

## Corridas lanzadas
- v1 ERROR: makedirs('') en guarda de versiones. v2 ERROR: sin celda de instalacion. v3 ERROR:
  pip resolvia deps (httpx2 ausente). v4 ERROR: huella 9fd49638 != 0f52de0b84cb (sample_submission
  trae adapters/; el zip enviado no). Todos pararon ANTES de la GPU; cada uno fixeado y commiteado.
- **c7-replica-1 = v5** (push ~04:50 UTC): instalacion --no-deps + guardas de versiones/sha256 OK
  en v4; huella corregida quitando adapters/.
- **v1 ERROR (~25 s, sin GPU)**: la guarda de versiones llamaba `makedirs(dirname('versiones_arnes.json'))`
  = `makedirs('')` → FileNotFoundError. La guarda detuvo ANTES de la GPU, como se diseñó. Fix:
  `resultados_c7/versiones_arnes.json` (commit «fix(kaggle): guarda de versiones…»).
- **c7-replica-1 = v2**: kernel `cs4all/c7-replica-condicion-7` v2, push 2026-10-16 ~04:35 UTC
  (https://www.kaggle.com/code/cs4all/c7-replica-condicion-7). 20 tareas rich, tope 150 min.
  Al terminar: `kaggle kernels output -k cs4all/c7-replica-condicion-7 -p data/replicas_c7/replica_1 -o -q`
  + commit, luego push v3 (corrida 2) y v4 (corrida 3), idénticos.
- Verificador datos: 0 colisiones ruta/hash; INCOMPLETO solo por 4 safetensors root en drvfs.

## Gates de envío (Fase 1.5) — RESULTADO: NO ENVIAR NADA
- Gate 1 FALLO: la duda «env additions permitidos» sigue sin respuesta (README §2.5 la lista como
  pregunta abierta a organizadores; la página de reglas exige JS/cookies y no se pudo leer). No hay
  confirmación → candidato descartado.
- Gate 3 FALLO: horas de evaluación consumidas desconocidas (la API no las da) → «si es desconocido:
  NO enviar».
- Gate 4 FALLO: límite diario no legible desde aquí → desconocido.
- Decisión: slot diario guardado, presupuesto de 12 h intacto. Réplicas por Kernels no tocan ese
  presupuesto (cuota GPU del dueño, separada). Si el dueño confirma reglas + horas, el candidato
  sigue siendo condición-7 + 3 paquetes de prueba (huella a calcular ANTES de subir; nunca un zip
  hash-igual a sub-005/006/008).

## Comprobación de continuidad (2026-10-16)
- Preflight local repetido después de los commits `7e57936` y `8cd8b8e`: pasó; notebook de 7
  celdas y todas las comprobaciones listadas verdes, con cuatro ruedas del arnés verificadas.
- Consulta remota de solo lectura: `cs4all/c7-replica-condicion-7` está `RUNNING`. El estado de Kaggle
  no expone aquí el número de versión; el dueño reporta que es v3 (réplica 1 de 3).
- Poller observado en WSL (PID 28996 al comprobar): espera 90 s y luego consulta el estado cada
  300 s, hasta 36 veces. **Solo imprime el estado y sale al terminar/error/cancelación**: no descarga
  outputs, no valida filas, no hace commit ni lanza v4/v5. Por tanto la cadena no es automática pese
  al mensaje anterior. No cerrar la sesión WSL/Kimi que lo aloja.
- No se envió nada al concurso. La decisión sigue bloqueada por reglas de paquetes adicionales,
  horas consumidas desconocidas y límite diario desconocido.
- Próximo paso exacto al despertar: consultar estado con
  `cd '/mnt/f/Code/Agents Learning Loops' && .venv-linux/bin/kaggle kernels status -k cs4all/c7-replica-condicion-7`.
  Si COMPLETE, descargar a `experiments/gemma_developer_agent/data/replicas_c7/replica_1` con
  `.venv-linux/bin/kaggle kernels output -k cs4all/c7-replica-condicion-7 -p <directorio> -o -q`,
  verificar los 20 IDs/resultados y registrar el estado antes de subir la siguiente versión. Si
  ERROR/CANCEL o faltan filas, detenerse; no lanzar la siguiente réplica automáticamente.
- Reanudar: “Lee AGENTS.md y STATUS.md; permanece en `exp/kaggle-c7-replicates`; no toques main,
  `eval_config.yaml` ni defaults; no muestres ni uses secretos. Primero verifica el estado real del
  kernel y su salida. Si COMPLETE, baja y valida los resultados de la réplica 1 antes de registrar
  o lanzar réplica 2; actualiza STATUS.md con hecho/siguiente/paso exacto.”
