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
(none yet)
