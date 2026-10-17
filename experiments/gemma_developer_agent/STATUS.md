# STATUS · Réplicas condición 7 (rama exp/kaggle-c7-replicates)

Actualizado: 2026-10-17 ~02:00 UTC (envío forzado de sub-019: RECHAZADO por pending de sub-018,
registrado literal; vigía ampliado con regla de desbloqueo). **Bloqueo de cuota GPU sigue
vigente** (reinicio semanal; el lunes 2026-10-19 es lo esperado). Cabeza: `d60ddc0`.

## Kit v2 «presupuesto-corregido» (sub-019, CONSTRUIDO NO ENVIADO)

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
- **sub-019** registrado. **INTENTO DE ENVÍO 2026-10-17 ~01:50 UTC (orden expresa del dueño, un
  solo intento): RECHAZADO** — mensaje literal de la plataforma: «Submission not allowed: Your
  team already has 1 pending submissions; please wait for one to finish scoring.»
  (FAILED_PRECONDITION). El cupo diario estaba libre (0 envíos hoy UTC) y el sha se verificó
  antes de subir; el bloqueo es sub-018 PENDING, no cuota GPU ni zip. Registry: status
  `submit_failed` con el mensaje en notes; test tripwire 61 passed. **Queda listo para reenviar
  en cuanto sub-018 puntúe**; el reenvío requiere confirmación explícita del dueño (la regla
  «el lunes decide» sigue vigente para elegir entre sub-019 y un brazo ganador).
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
— el entorno evolucionó desde el lock).

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
- **sub-018 (57274153): PENDING >24 h — ANÓMALO** (enviada 2026-10-16 15:30 UTC; lecturas del
  vigía t+10/12/15/26/34 h: PENDING). Cruzó el umbral de las 12 h oficiales de evaluación + cola:
  **dueño revisa la cola en la página web del concurso; si aparece atascada, cancelarla desde la
  UI** (yo no la cancelo). Bloqueo colateral verificado: la plataforma rechaza envíos nuevos
  mientras haya 1 pending («Your team already has 1 pending submissions») → sub-019 no puede
  subir hasta que sub-018 termine. Vigía (id `01M53RZD2AY1YN3V23FXG1GT6Q`) vigila sub-018 con
  reglas a/b/c + aviso de desbloqueo de sub-019 (regla d, sin enviar por su cuenta).

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
