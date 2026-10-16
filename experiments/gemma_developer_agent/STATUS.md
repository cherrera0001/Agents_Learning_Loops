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
