# STATUS · Réplicas condición 7 (rama exp/kaggle-c7-replicates)

Actualizado: 2026-10-16 (lote nocturno, sesión Kimi Code).

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
