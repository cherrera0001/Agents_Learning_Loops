# Glosario de entorno

Siete términos con significado fijo. Los demás documentos del repositorio los usan con estos nombres
exactos y no los intercambian. Cuando un texto dice «agente», «skill» o «harness» sin calificar, se
refiere al término de esta tabla que corresponda según su contexto.

| # | Término | Qué es | Qué no es | Dónde vive |
|---|---|---|---|---|
| 1 | **Agente de biblioteca** | La clase `Agent` y su máquina `PLAN → RETRIEVE → ACT → OBSERVE → CONSOLIDATE`. Es el objeto de estudio del Experimento 0. | No es quien edita este repositorio ni el agente del Experimento 1. | [`src/associative_agent_loop/agent/core.py`](../../src/associative_agent_loop/agent/core.py) (`Agent`, `Episode`, `State`, `TRANSITIONS`); especificación: [`specs/loop_protocol.md`](../../specs/loop_protocol.md) |
| 2 | **Solver acotado** | El agente del Experimento 1: ordena tres operadores de reparación ya escritos, inspecciona el código y propone un parche. | No descubre algoritmos nuevos. No es un modelo de lenguaje con herramientas abiertas. | [`src/experiments/agent.py`](../../src/experiments/agent.py) (`BoundedRepairAgent`, nombre `bounded-ast-repair-v1`; recibe `AgentView`); especificación: [`specs/software_learning_protocol.md`](../../specs/software_learning_protocol.md) |
| 3 | **Agente de entorno** | Un rol de quien edita este repositorio: una persona o un agente de Cursor o Claude. | No es una clase Python ni un componente del sistema. Solo existe en la documentación. | [`AGENTS.md`](../../AGENTS.md), [`docs/entorno/agentes.md`](agentes.md) |
| 4 | **Skill de memoria** | El tipo de nodo `Skill` y la relación `promoted_to_skill` del esquema `software-learning-memory/v1`. | No está implementada: el protocolo deja la promoción a Skill como trabajo futuro. No es una skill de entorno. | [`src/experiments/models.py`](../../src/experiments/models.py), [`specs/software_memory_schema_v1.json`](../../specs/software_memory_schema_v1.json) |
| 5 | **Skill de entorno** | Un procedimiento escrito en `skills/<nombre>/SKILL.md`, derivado de una regla que el repositorio ya cumple. | No sustituye a `learning/episodes/`: los episodios siguen siendo la fuente de verdad y `dev_memory.json` sigue siendo derivado. No es un nodo de ninguna memoria. | [`skills/`](../../skills/README.md), [`docs/entorno/skills.md`](skills.md) |
| 6 | **Harness de experimento** | El controlador del Experimento 1: tabla de fases, copia del workspace, lista de archivos editables, variables de entorno permitidas, recibos inmutables y frontera entre `benchmark/public` y `benchmark/private`. | No es un sandbox del sistema operativo. El protocolo exige aislamiento de proceso antes de usar un adaptador de modelo no confiable. | [`src/experiments/runner.py`](../../src/experiments/runner.py) (`PHASES`, `TRANSITIONS`, `prepare`, `protected_files`, `execute_tests`), [`src/experiments/evidence.py`](../../src/experiments/evidence.py); especificación: [`specs/software_learning_protocol.md`](../../specs/software_learning_protocol.md) (*Execution and receipts*, *Leakage boundary*) |
| 7 | **Harness de entorno** | El contrato de quien edita este repositorio: qué puede leer, qué puede escribir, cuándo se detiene y qué evidencia deja. | No reimplementa el harness de experimento; apunta a él. | [`docs/entorno/harness.md`](harness.md) |

## Tres usos de «modelo»

Tabla complementaria a los siete términos anteriores, que conservan su numeración.

| Uso | Qué es | Qué no es | Dónde vive |
|---|---|---|---|
| **Modelo de datos** | El grafo Pydantic: `Node`, `Edge`, `GraphDocument` | No es un modelo de Claude ni de embedding | [`src/associative_agent_loop/memory/models.py`](../../src/associative_agent_loop/memory/models.py); README § 4 |
| **Modelo de embedding** | `LexicalEmbedder` o `FastEmbedEmbedder`; `GraphDocument.embedding_model` nombra este | No es el modelo de Claude que construye un issue | [`src/associative_agent_loop/memory/embeddings.py`](../../src/associative_agent_loop/memory/embeddings.py); README § 6 |
| **Modelo de construcción** | El modelo de Claude que construye un issue, elegido por talla | No se fija en un Markdown de sesión: el ID se aplica al crear el subagente | Política: [`docs/estimation.md`](../estimation.md); aplicación: [`enrutamiento.md`](enrutamiento.md); registro: campos *Talla*, *Modelo* y *Puntos* del Project #5 |

Par que no debe confundirse: **Task Ledger** ([`experiments/software_project/`](../../experiments/software_project/README.md))
es la aplicación bajo reparación del Experimento 1 y no asigna modelos; el registro de modelos de
construcción es [`docs/estimation.md`](../estimation.md) junto con el Project #5.

## Pares que suelen confundirse

- **Agente de biblioteca y solver acotado**: el primero elige herramientas en escenarios simulados
  (Experimento 0); el segundo repara código real con tres operadores fijos (Experimento 1).
- **Agente de entorno y cualquiera de los anteriores**: el agente de entorno trabaja *sobre* el
  repositorio; los otros dos son código *dentro* del repositorio.
- **Skill de memoria y skill de entorno**: la primera es un tipo de nodo, todavía sin implementar; la
  segunda es un documento Markdown con un procedimiento del equipo.
- **Harness de experimento y harness de entorno**: el primero es código que controla al solver acotado;
  el segundo es un contrato escrito para quien edita el repositorio.
