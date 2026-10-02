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
| [`investigador-papers`](investigador-papers/SKILL.md) | Antes de publicar un texto que cite una obra o nombre un mecanismo | README § 7.2, informe de H4 |
| [`revisor-redactor`](revisor-redactor/SKILL.md) | Antes de publicar un texto público del proyecto | README § 7.2 y § 12, informe de H4 |
| [`validador-estadistico`](validador-estadistico/SKILL.md) | Antes de publicar un texto con cifras o verbos de resultado | Protocolo (*Metrics and falsification*), `results/README.md`, informe de H4 |
