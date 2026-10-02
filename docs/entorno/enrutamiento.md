# Enrutamiento: el modelo de construcción

Contrato para elegir **qué modelo de Claude construye cada issue**. La política con sus cifras está en un
solo lugar, [`docs/estimation.md`](../estimation.md); este documento explica cómo se aplica y **cuánta fuerza
tiene** esa elección. Terminología: [glosario](glosario.md), tabla «Tres usos de modelo».

## 1. Tres usos de «modelo»

| Uso | Qué es | Dónde vive |
|---|---|---|
| **Modelo de datos** | El grafo Pydantic: `Node`, `Edge`, `GraphDocument` | [`src/associative_agent_loop/memory/models.py`](../../src/associative_agent_loop/memory/models.py); README § 4 |
| **Modelo de embedding** | `LexicalEmbedder` o `FastEmbedEmbedder`. El campo `GraphDocument.embedding_model` nombra **este** modelo, no un modelo de Claude | [`src/associative_agent_loop/memory/embeddings.py`](../../src/associative_agent_loop/memory/embeddings.py); README § 6 |
| **Modelo de construcción** | El modelo de Claude que construye un issue | Política: [`docs/estimation.md`](../estimation.md). Registro por issue: cuerpo del issue y Project #5 (§ 3) |

Este documento trata solo del **modelo de construcción**.

## 2. Política

Fuente única: [`docs/estimation.md`](../estimation.md). Aquí solo se resume, sin copiar tablas:

- **Talla** XS–XL, calculada con cuatro factores: alcance, incertidumbre, riesgo y verificación (§ 1).
- **Modelo, ID y esfuerzo por talla**: la tabla de § 2.
- **Reglas** de § 2:
  1. piso por riesgo;
  2. si la verificación falla, se sube **un solo escalón**;
  3. antes de sumar modelos, bajar el esfuerzo;
  4. el orquestador (Opus 5.5) especifica, revisa y es el único que hace merge.
- **Excepciones que mandan sobre la talla** (I = 3, sistema externo compartido, orquestador que implementa):
  § 2.2.

## 3. Registro

El registro por issue es la «Estimación v1» del cuerpo del issue, los comentarios «Estimación v2…» y los
campos del Project #5: *Talla*, *Puntos*, *Incertidumbre*, *Riesgo*, *Modelo* (previsto, no se
sobrescribe) y, al cerrar, *Modelo usado*, *Escaló* y *Verificación*. *Modelo usado* es autoinformado salvo
que exista transcripción. Las excepciones, los agentes que no son Claude y el esfuerzo no aplicable por la
herramienta de subagentes están en [`docs/estimation.md`](../estimation.md) § 2.1–2.5; la sección 5 de ese
documento es el registro histórico de 2026-09-29.

**[`experiments/software_project/`](../../experiments/software_project/README.md) no es este registro.** Es
Task Ledger, la aplicación bajo reparación del Experimento 1, y no asigna modelos de Claude.

## 4. Cuánta fuerza tiene la elección

La elección del modelo **no es un interruptor automático**. Opera en tres niveles, de menor a mayor fuerza:

| Nivel | Qué es | Qué hace | Qué no hace |
|---|---|---|---|
| **Política** | [`docs/estimation.md`](../estimation.md) | Fija talla, modelo, ID y esfuerzo | No se carga sola: alguien tiene que leerla |
| **Reglas inyectadas** | [`AGENTS.md`](../../AGENTS.md), [`CLAUDE.md`](../../CLAUDE.md), [`.cursor/rules/entorno.mdc`](../../.cursor/rules/entorno.mdc) | El entorno las carga y ordenan leer la política antes de delegar | **No cambian el modelo de la sesión ya abierta** |
| **Aplicación del ID** | El momento en que el orquestador crea el subagente o el worktree | Le pasa el ID de la tabla (`claude-haiku-4-5`, `claude-sonnet-5-5` o `claude-opus-5-5`) y el esfuerzo de esa fila | Solo afecta al subagente que se crea |

Por herramienta:

- **Claude Code**: el lugar que fija el modelo de un rol es el frontmatter `model:` de
  `.claude/agents/<rol>.md`. El repositorio versiona tres definiciones de implementador:
  [`implementador-haiku`](../../.claude/agents/implementador-haiku.md),
  [`implementador-sonnet`](../../.claude/agents/implementador-sonnet.md) e
  [`implementador-opus`](../../.claude/agents/implementador-opus.md). Comparten un cuerpo corto (arranque,
  cuenta de GitHub por orden, comprobaciones, episodio, PR sin merge) y solo cambian el modelo y su
  `description`. Qué **declaran**: el alias del modelo del subagente (`haiku`, `sonnet` u `opus`). A qué ID
  resuelve cada alias lo decide Claude Code, no este repositorio: el 2026-10-02, en subagentes lanzados
  pasando el alias a mano, las transcripciones registraron `claude-sonnet-5-5` para `sonnet` y
  `claude-haiku-4-5-20251001` para `haiku`. Que un subagente lanzado **con la definición** corra con ese
  modelo está pendiente de observar en una transcripción, y una definición nueva puede no cargarse hasta
  reiniciar la sesión; tampoco está comprobado. Qué **no fijan**: el esfuerzo (la herramienta de subagentes
  no lo permite) ni el modelo de la sesión ya abierta. `.gitignore` ignora el resto de `.claude/`.
- **Cursor**: la persona elige el modelo del chat en el selector. Un subagente usa el ID de la tabla solo
  si quien lo lanza lo copia desde `docs/estimation.md`.

## 5. Rol del orquestador

El orquestador es un agente de entorno ([`agentes.md`](agentes.md)):

1. Estima la talla con la política antes de abrir la rama o el worktree.
2. Delega pasando el **ID y el esfuerzo** de la fila correspondiente.
3. Revisa cada entrega con **medios propios**, independientes del agente que la produjo.
4. Es el **único que hace merge**, después de verificar `mergedAt`. El implementador abre el PR y no hace merge.
