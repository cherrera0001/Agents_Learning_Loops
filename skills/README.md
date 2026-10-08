# skills/: skills de entorno

Procedimientos del equipo para quien edita el repositorio, escritos en Markdown. Son **skills de entorno**
([glosario](../docs/entorno/glosario.md), término 5): cada una proyecta de forma legible un procedimiento
**ya fijado** en `learning/README.md`, `CONTRIBUTING.md` o el protocolo del Experimento 1. Regla de admisión
completa: [`docs/entorno/skills.md`](../docs/entorno/skills.md).

**No son skills de memoria.** El tipo de nodo `Skill` y la relación `promoted_to_skill` del esquema
`software-learning-memory/v1` siguen sin implementarse, y ninguna lección del grafo se promociona a skill.
Los episodios de `learning/episodes/` siguen siendo la fuente de verdad.

| Skill | Cuándo | Fuente |
|---|---|---|
| [`estimar-issue`](estimar-issue/SKILL.md) | Antes de que un issue pase a *In Progress* | `CONTRIBUTING.md`, `learning/README.md` |
| [`recall-antes-de-issue`](recall-antes-de-issue/SKILL.md) | Antes de implementar un issue | `learning/README.md`, `CONTRIBUTING.md` |
| [`registrar-episodio`](registrar-episodio/SKILL.md) | Al cerrar un issue, antes del PR | `learning/README.md` |
| [`confirmar-cierre`](confirmar-cierre/SKILL.md) | Tras el merge verificado y antes de mover a *Done* | `CONTRIBUTING.md`, `docs/entorno/harness.md` |
| [`proteger-evidencia`](proteger-evidencia/SKILL.md) | Al tocar evidencia, benchmark o el solver acotado | `evidence/README.md`, *Leakage boundary* |
| [`corrida-valida`](corrida-valida/SKILL.md) | Al bajar lo que dejó una corrida de un experimento con modelo, y antes de conservar o descartar una condición | `CONTRIBUTING.md` (*Vuelta de un experimento con modelo*) |
| [`concilio-de-experimento`](concilio-de-experimento/SKILL.md) | En cada vuelta de un experimento con modelo, antes de proponer un cambio | `CONTRIBUTING.md` (*Vuelta de un experimento con modelo*) |
| [`investigador-papers`](investigador-papers/SKILL.md) | Antes de publicar un texto que cite una obra o nombre un mecanismo | `CONTRIBUTING.md` (*Revisión de un texto público*) |
| [`revisor-redactor`](revisor-redactor/SKILL.md) | Antes de publicar un texto público del proyecto | `CONTRIBUTING.md` (*Revisión de un texto público*) |
| [`validador-estadistico`](validador-estadistico/SKILL.md) | Antes de publicar un texto con cifras o verbos de resultado | `CONTRIBUTING.md` (*Revisión de un texto público*) |
| [`auditor-datos`](auditor-datos/SKILL.md) | Antes del validador, cuando el experimento siguió corriendo después de escribirse el texto | `CONTRIBUTING.md` (*Revisión de un texto público*) |
| [`revisor-figuras-tablas`](revisor-figuras-tablas/SKILL.md) | Antes de publicar un texto con figuras, tablas o diagramas | `CONTRIBUTING.md` (*Revisión de un texto público*), `scripts/paper_figures.py` |
| [`revisar-manuscrito`](revisar-manuscrito/SKILL.md) | Para llevar un manuscrito con datos hasta una versión firmada | `CONTRIBUTING.md` (*Revisión de un texto público*), `scripts/paper_check.py` |
| [`maquetar-apa`](maquetar-apa/SKILL.md) | Tras la firma, cuando el destino acepta o pide PDF | `scripts/paper_pdf.py` |

De `investigador-papers` a `maquetar-apa` son las skills del staff de texto público; `corrida-valida` y
`concilio-de-experimento` son las del [staff de experimento](../docs/entorno/agentes.md#staff-de-experimento).
Ninguna es un nodo Skill de la memoria.
