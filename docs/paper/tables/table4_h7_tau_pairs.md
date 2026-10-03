# Tabla 4: Transferencia y contaminación de fallos por umbral τ (H7)

| Base | Umbral τ | Variante | Pares evaluados | Pares ayudados | Pares dañados | Veredicto de celda |
|---|---|---|---|---|---|---|
| A (Sin lecciones) | 0.25 | real | 18 | +3 | -0 | Transfiere sin contaminar |
| A (Sin lecciones) | 0.1 | real | 18 | +3 | -3 | Contamina (mixto) |
| A (Sin lecciones) | 0.0 | real | 18 | +3 | -0 | Transfiere sin contaminar |
| C (Con lecciones) | 0.25 | real | 18 | +0 | -0 | Neutro |
| C (Con lecciones) | 0.25 | placebo | 18 | +0 | -3 | Contamina |
| C (Con lecciones) | 0.1 | real | 18 | +0 | -3 | Contamina |
| C (Con lecciones) | 0.1 | placebo | 18 | +0 | -3 | Contamina |
| C (Con lecciones) | 0.0 | placebo | 18 | +0 | -3 | Contamina |

> **Conclusión pre-registrada:** Con lecciones presentes (base C), la memoria de fallos nunca
> ayudó entre tareas distintas y causó contaminación con τ = 0.10 (-3/18 pares).
> Datos derivados directamente de `results/failure-transfer-v1/failure_transfer_analysis.json`.
> Regenerar: `python -m scripts.paper_figures`.
