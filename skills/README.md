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
| [`recall-antes-de-issue`](recall-antes-de-issue/SKILL.md) | Antes de implementar un issue | `learning/README.md`, `CONTRIBUTING.md` |
| [`registrar-episodio`](registrar-episodio/SKILL.md) | Al cerrar un issue, antes del PR | `learning/README.md` |
| [`proteger-evidencia`](proteger-evidencia/SKILL.md) | Al tocar evidencia, benchmark o el solver acotado | `evidence/README.md`, *Leakage boundary* |
