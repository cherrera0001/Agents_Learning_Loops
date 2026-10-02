# Skills de entorno: regla de admisión

Una **skill de entorno** ([glosario](glosario.md), término 5) es un procedimiento escrito en
`skills/<nombre>/SKILL.md`. No es una **skill de memoria** (término 4): el tipo de nodo `Skill` y la
relación `promoted_to_skill` del esquema `software-learning-memory/v1` siguen sin implementarse, y ninguna
lección del grafo se promociona a skill.

## Regla de admisión

Una skill de entorno se admite solo si documenta un procedimiento **ya presente** en al menos una de estas
fuentes:

- [`learning/README.md`](../../learning/README.md)
- [`CONTRIBUTING.md`](../../CONTRIBUTING.md)
- [`specs/software_learning_protocol.md`](../../specs/software_learning_protocol.md) (o [`evidence/README.md`](../../evidence/README.md), que lo aplica)

- Para el **staff de texto público** ([`agentes.md`](agentes.md#staff-de-texto-público)): los límites ya
  publicados de un resultado, en [`README.md`](../../README.md) § 7.2 («Qué no se demuestra»),
  [`results/README.md`](../../results/README.md) o un informe de [`docs/results/`](../results/). Estas skills
  aplican esos límites a un texto; no añaden ninguno al experimento.

Una skill no crea reglas nuevas. Si hace falta una regla nueva, primero se incorpora a una de esas fuentes
y después, si conviene, se escribe su skill.

## Requisitos de cada `SKILL.md`

1. Declara su **fuente**: archivo y sección y, si existe, el episodio de `learning/episodes/` donde se
   aprendió la regla.
2. Dice explícitamente que **no es un nodo Skill de la memoria**.
3. Está en español y se limita al procedimiento, sin reescribir el protocolo.

## Relación con la bitácora

`skills/` es una **proyección legible** de procedimientos ya fijados. Los episodios de
`learning/episodes/` siguen siendo la fuente de verdad, y `learning/dev_memory.json` sigue siendo derivado.
Si una skill y su fuente divergen, prevalece la fuente y la skill se corrige.

## Skills admitidas

| Skill | Fuente |
|---|---|
| [`estimar-issue`](../../skills/estimar-issue/SKILL.md) | `CONTRIBUTING.md`, `learning/README.md` |
| [`recall-antes-de-issue`](../../skills/recall-antes-de-issue/SKILL.md) | `learning/README.md`, `CONTRIBUTING.md` |
| [`confirmar-cierre`](../../skills/confirmar-cierre/SKILL.md) | `CONTRIBUTING.md`, `docs/entorno/harness.md` |
| [`registrar-episodio`](../../skills/registrar-episodio/SKILL.md) | `learning/README.md` |
| [`proteger-evidencia`](../../skills/proteger-evidencia/SKILL.md) | `evidence/README.md`, *Leakage boundary* del protocolo |
| [`investigador-papers`](../../skills/investigador-papers/SKILL.md) | README § 7.2, informe de H4 |
| [`revisor-redactor`](../../skills/revisor-redactor/SKILL.md) | README § 7.2 y § 12, informe de H4 |
| [`validador-estadistico`](../../skills/validador-estadistico/SKILL.md) | Protocolo (*Metrics and falsification*), `results/README.md`, informe de H4 |
