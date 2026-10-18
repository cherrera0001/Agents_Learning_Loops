# Guiones del concilio C7 Fase 4 (2026-10-17, vuelta 49 / concilio 51)

Guiones y salidas que sostienen las correcciones de
[`docs/c7_concilio_2026-10-17.md`](../../docs/c7_concilio_2026-10-17.md) al
[`c7_analisis_critico.md`](../../docs/c7_analisis_critico.md). Cada subcarpeta es el aporte de un
rol del staff de experimento (definiciones en `docs/entorno/agentes.md`); las rutas de datos de
los guiones son relativas a la raíz del repo y se ejecutan con `.venv-linux/bin/python`.

| Carpeta | Rol | Guiones |
|---|---|---|
| `analista/` | analista de datos | 01–08: IC95 y ruido, integridad CSV≡JSON crudo, línea base de desenlaces, A1 enunciado, A2 conducta, A3 bootstrap cap 12 h (reescrito; el original del análisis no se comitó), A4 leaderboard, calibración de predicciones. |
| `qa/` | QA de trayectorias | `trazas_rep1.py` (parser de trazas ATIF) y `qa06_verificacion_doc.py` (verificación de las afirmaciones del documento). Los guiones qa01–qa05 viven en la carpeta de trabajo local `scratch/concilio-c7-fase4/qa-trayectorias/` (ignorada por git). |
| `arquitecto/` | arquitecto de IA | `cuenta_presupuesto.py` — envelope de la cap de 12 h y potencia del contraste. |
| `auditor/` | auditor del método | `audit_01`–`audit_07` con sus salidas `.txt` — los dictámenes que mandan (muro 13/20, submits 7/20, 18/148 ≥230 s, IC95 ±0,041, envelope 9 min, A1 por denominadores, conteos de snapshots/wheels). |
| `forense/` | forense del arnés | `gold_patch_local.py` — driver del gold-patch CPU (escrito, no corrido: faltan 82/129 snapshots y el venv del arnés). |

Dato de leaderboard: [`leaderboard_publico_2026-10-17T1501Z.csv`](../leaderboard_publico_2026-10-17T1501Z.csv)
(descarga oficial vía `kaggle competitions leaderboard -d`, 3.043 equipos; antes solo existía en
`/tmp` y se podía perder).
