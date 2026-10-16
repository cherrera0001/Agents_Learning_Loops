# Progreso réplicas condición 7 (agregado, sin ids de tareas)

Rama: `exp/kaggle-c7-replicates`. Los ids de tareas y los outputs completos NO se versionan
(contenido de la competencia); viven en `data/replicas_c7/replica_<n>/` (gitignored).

## Réplica 1 — COMPLETE (2026-10-16, kernel v6)

- Kernel: `cs4all/c7-replica-condicion-7` (etiqueta de corrida `c7_20261016T0459Z`).
- Huella de config: `0f52de0b84cb` (== condición 7 verificada, == zip enviado).
- Guardas: 4 versiones de paquetes == esperadas; SHA-256 de ruedas registrado; preflight 24/24
  había pasado antes del push.
- Tareas intentadas: **20/20** (conjunto sustituto rich; desviación vs las 19 mixtas originales
  declarada en `replicas_c7/tareas_c7.json`). `cortado_por: null` (no hubo corte por tope).
- Resultado: **4 resueltas / 20 (20,0%)**; clases: 4 `resuelta`, 16 `sin_parche`, 0 errores de sesión.
- Duración de sesión: 5.563 s (~92,7 min) dentro del tope de 9.000 s (150 min).
- Referencia externa: la medición local original fue **9/19 (47,4%)**. No comparable tarea a
  tarea (conjunto distinto y tamaño distinto); solo referencia de magnitud. El informe final
  (`docs/c7_ruido.md`) decidirá «dentro/fuera de banda» con las 3 réplicas.

## Bloqueo: réplicas 2 y 3

- Push de v7 (réplica 2) el 2026-10-16: **`Kernel push error: Maximum weekly GPU quota of 30.00
  hours reached.`** — cuota GPU semanal de la cuenta agotada.
- Sin workaround legítimo: la cuota es por cuenta y semanal. Cambiar de acelerador alteraría la
  condición (no comparable con 9/19). No se reintentó en bucle (regla del lote).
- Reanudación: tras el reinicio semanal de cuota (lunes), push idéntico de v7 y v8; código del
  paquete `replicas_c7/` ya está listo y commiteado en la rama.
