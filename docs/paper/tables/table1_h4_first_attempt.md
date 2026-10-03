# Tabla 1: Éxito al primer intento por condición (H4)

| Tipo de tarea | A · Sin memoria (Primario) | B · Historial (Primario) | C · Asociativa (Primario) | Dif. C − B | Auditoría ambas réplicas (A / B / C / 36 runs) |
|---|---|---|---|---|---|
| Originales (EXP-04..06) | 6/18 (0.33) | 18/18 (1.00) | 18/18 (1.00) | +0 | 12/36 · 36/36 · 36/36 |
| Con señuelo (EXP-07..09) | 6/18 (0.33) | 0/18 (0.00) | 0/18 (0.00) | +0 | 12/36 · 0/36 · 0/36 |

> **Nota metodológica:** La lectura primaria utiliza una réplica equivalente derivada
> tras verificar `replication.all_semantic_projections_equal == True` en `reference-v2/experiment1.json`.
> La columna de auditoría reporta el total consolidado de ambas réplicas (36 ejecuciones,
> fuente: `results/reference-v2/family_breakdown.json`).
> Las 36 ejecuciones reúnen dos réplicas deterministas; no son 36 observaciones independientes.
> El agente evaluado es el solver determinista de tres operadores sin LLM.
> Regenerar: `python -m scripts.paper_figures`.
