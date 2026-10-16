# STATUS · Réplicas condición 7 (rama exp/kaggle-c7-replicates)

Actualizado: 2026-10-16 ~16:30 UTC (sesión: subida de sub-018 + pasada de verificación V1-V5;
sin GPU). **Bloqueo de cuota GPU sigue vigente** (reinicio semanal; el lunes
2026-10-19 es lo esperado).

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
- **Pendiente de decisión del dueño**: fix de `clase_fallo` (leer `agent_patch`) antes de réplicas
  2-3. Recomendado: aplicar — la clase actual no mide nada.

## Track C: preguntas del dataset (22 GB, fuera del repo; `data/` cubierto por .gitignore)

**(i) ¿Los 3 paquetes de test del apunte 71→103 están en el wheelhouse? VEREDICTO: palanca
MUERTA confirmada (2 de 4 candidatos presentes, los 2 test-only ausentes).** El único conjunto
candidato trazable es el del lock de desviaciones (`docs/desviaciones_entorno_wheels.lock`,
2026-10-03): typing-inspection 0.4.4, h11 0.16.0, dirty-equals 0.11 (faltantes entonces) +
python-multipart 0.0.18 (ya presente). Listado de `data/wheels/` (115 ruedas): **typing_inspection
0.4.4 SÍ**, **python_multipart 0.0.18 SÍ**, **h11 NO**, **dirty_equals NO**. Caveat: el trio
exacto de la nota 71→103 no se nombra en ningún archivo commiteado; con los candidatos
trazables, la medición 71→103 no es reproducible desde el wheelhouse mientras falten h11 y
dirty_equals (starlette ya sube a 0.50.0 — el entorno evolucionó desde el lock).

**(ii) tasks.jsonl: 129 tareas** — repos: fastapi/fastapi 67, Textualize/rich 48, psf/requests 13,
encode/httpx 1. `hints_text`: presente como campo en las 129 pero **VACÍO en todas** (el arnés
soporta `{hints}` en instrucciones, HARNESS_README §2.3, pero el dataset público no trae ninguna).
Mediana de caracteres del enunciado: fastapi 677, rich **146** (confirma el problema de
enunciados-casi-título del manuscrito), requests 406, httpx 243. Entrada para un mejor conjunto
de medición que las 20 rich: priorizar enunciados largos y tareas que discriminen (validez
71/103), y considerar fastapi (mediana 677) si el objetivo es separación agente↔tarea; las 20
rich actuales miden el peor caso (enunciado corto). Solo informe; no se cambia nada.

## Flags de verificación pendientes
- **Presupuesto de 12 h de evaluación: FUENTE NO VERIFICADA.** El dato «12 h / ~120 tareas»
  usado en la §3 del manuscrito (aritmética ~6 min/tarea) procede de la página de reglas, que no
  fue legible desde aquí (JS/cookies); el HARNESS_README fija los mecanismos por tarea pero no
  el total. Marcar como UNVERIFIED hasta que el dueño lo lea de las reglas. Mismo estatus para el
  **límite diario de envíos** y las **horas consumidas** (gates 3-4 de envío). Subir el nav hoy
  es decisión del dueño con esos datos aún no verificados.

## Lunes (cuota reiniciada): contraste de CUATRO brazos
1. Decidir el fix de `clase_fallo` (recomendado: aplicar).
2. Réplicas 2 y 3 de la condición 7 (brazo A; push v7/v8 de `replicas_c7/`, poller, pull,
   commits) → miden la **banda de ruido**.
3. Un run de cada variante sobre las mismas 20 tareas: navegación (`af8cca829561`), presupuesto
   (`52ba08ceac25`), thinking (`9d0db7b946e7`).
4. **Coste estimado: 4 brazos × 1 run × 20 tareas ≈ 6,5 h de GPU en total** (≈1,5-1,7 h por
   corrida con carga de modelo ~6-19 min + 20 × 4,5 min + márgenes), dentro de los 30 h
   semanales con margen para reintentos.
5. **Regla de decisión (fijada antes de correr)**: cualquier brazo que supere a A en más de la
   banda de ruido (medida en las réplicas 2-3; si la banda resulta ≥3 tareas, ninguna
   decisión) pasa a ser **candidato de envío para la semana siguiente**, sujeto a las gates de
   envío vigentes (reglas del concurso, horas consumidas del presupuesto de 12 h, límite diario).
6. Con todo: `docs/c7_ruido.md` + informe del contraste + episodio devlog + STATUS COMPLETE.

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
- Fase 1: conjunto sustituto = las 20 tareas rich rescatadas (ids_rich_provisional.txt, la pasada
  real `sesion-unica-a` de 20 tareas). DESVIACIÓN declarada: 20 rich, no las 19 mixtas del 9/19.
- Próximo paso exacto: actualizar tareas_c7.json + guard del notebook, rebuild, preflight, commit,
  lanzar corrida 1/3 con `kaggle kernels push -p experiments/gemma_developer_agent/replicas_c7
  -t 9000 --accelerator NvidiaL4`.

## Siguiente (resume)
Si la sesión se interrumpe: leer este archivo; continuar en el paso «Ahora». Kernel id/URL de cada
corrida se anota abajo en cuanto exista.

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
