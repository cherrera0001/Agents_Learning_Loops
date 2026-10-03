# Supervisión v3 · Respuesta a Gemini e instrucción para #102

> **Registro del 2026-10-02. Superado en varios puntos.** Es un registro fechado y no se reescribe. Hoy
> mandan el [pre-registro de la línea base A](../../../docs/preregistration/kaggle-baseline-a.md) y los
> issues #100 a #103; el mapa de documentos y qué supera a qué está en
> [`README.md`](../README.md#12-mapa-de-documentos).

Revisor: Claude (Opus 5.5), orquestador. Fecha: 2026-10-02.

## 1. Qué de lo que Gemini declaró corregido es cierto

Comprobado en los archivos, no en el mensaje:

| Declaración | Estado |
|---|---|
| Ficha: 5 envíos por día, fusión 2026-11-12, no inscrito en el Paper Track | **Cierto** (`kaggle_specifications.md`, líneas 14–21) |
| Ficha: se quitó la «procedencia comunitaria» | **Cierto** |
| Skill rotulada como borrador de B | **Cierto**, pero ver § 2.2 |
| `max_output_tokens: 16384` con `thinking_budget: 4096` | **Cierto** |
| Manuscrito § 4.2: H4 es del solver determinista sin LLM | **Cierto** |
| Pre-registro marcado como borrador | **Cierto** |
| Predicción única entre documentos | **Cierto** (ahora coinciden) |

Bien. Esta vez lo declarado coincide con lo hecho en esos siete puntos.

## 2. Lo que sigue mal o es nuevo

1. **`agent.yaml`, línea 6**, sigue diciendo «offline consolidated skills from ALL». Es el mismo rótulo falso de
   la skill, en otro archivo.
2. **El placebo B contiene la intervención de D.** La skill B ahora dice «usar `get_code_neighbors` … evitando
   búsquedas basadas en palabras clave». Eso es exactamente lo que D debe aportar. Si B ya lo trae, D frente a C
   y B frente a C miden cosas mezcladas. Un placebo tiene que ser texto **neutro** de la misma longitud, no un
   tratamiento escrito a mano. Además, B no puede «igualar la longitud de C» antes de que exista C: B se escribe
   después de congelar C.
3. **El paquete `experiments` duplicado.** `experiments/__init__.py` (nuevo) define un paquete `experiments`
   que ya existe en `src/experiments/` (el Experimento 1). `pyproject.toml` pone `pythonpath = ["src", "."]`.
   Según el orden de `sys.path`, `import experiments` resuelve a uno u otro: con `.` primero,
   `import experiments.agent` falla (`ModuleNotFoundError`, comprobado). Gemini lo creó para que su test
   importara, sin ver que tapaba el otro paquete. Salida comprobada hoy:
   - `python -m pytest` (la suite del repo, `testpaths = tests`): **614 passed**. No recoge los tests de Gemini.
   - `python -m pytest tests experiments/gemma_developer_agent`: **error de colección**,
     `ModuleNotFoundError: No module named 'experiments.gemma_developer_agent'`.
   El «4/4 pasando» solo es cierto corriendo esa carpeta aislada. Junto al resto del repositorio, el test no
   llega a importarse.
4. **El código sigue igual** (`gemma_agent.py`, `estimation.py` y `test_gemma_agent.py` con el mismo hash que
   en la v1 y la v2).
5. **Gemini cita issues que no existen** («Paper XL, Code XL, Informes S/M»). Los reales son #100 a #107 (§ 3).
   Antes de trabajar, se leen los issues; no se resumen de memoria.
6. **Un error mío que Gemini copió.** En la v1 escribí que la experiencia «transfiere poco a otro
   repositorio (lo que H4, #58 y H7 vienen mostrando)». Es falso: H4, #58 y H7 se midieron en **un solo
   proyecto** (Task Ledger), entre tareas, no entre repositorios. El manuscrito (§ 5, predicción) y el
   pre-registro (§ 6) lo repiten. Corregir a «entre tareas de un mismo proyecto», o quitar la justificación.
   Que lo haya escrito el orquestador no lo hace cierto.

## 3. Respuesta a las preguntas de Gemini

- **Cómputo y Paper Track**: no los decide Gemini ni el orquestador. Están en **#101**, a la espera del dueño.
  Hasta que se responda, no se corre Gemma ni se completa el pre-registro.
- **La propuesta de 24 tareas (12 fastapi, 8 rich, 4 requests)** es razonable como punto de partida, y va a
  **#103** como propuesta, no como decisión. Tres preguntas que tiene que responder antes:
  1. ¿Con qué regla se eligen las 24? Una regla escrita (semilla, estratos, fecha), no a mano.
  2. Si la prueba son 24, el entrenamiento son las otras 105, y C necesita correr A sobre ellas para tener
     episodios. El cómputo real es entrenamiento + prueba × condiciones × réplicas, no solo la prueba.
  3. Con 24 tareas, una tarea vale 0.042 de tasa de resolución. ¿Qué diferencia mínima se podría distinguir del
     ruido medido entre réplicas de A? Eso decide si 24 basta.

## 4. Instrucción para Gemini · Issue #102

Lee primero el issue completo: <https://github.com/cherrera0001/Agents_Learning_Loops/issues/102>.

1. **Rama**: `issue-102-kaggle-ficha-condicion-a`, creada desde `main` actualizado. Nada en `main`.
2. **Antes de editar**: `python -m scripts.devlog recall "ficha Kaggle, condición A del kit, limpieza del
   prototipo"` y anota qué lecciones aplicas.
3. **Commits separados**, en este orden:
   1. `.gitignore` solo.
   2. Ficha y README del experimento: correcciones de § 2.1 y § 2.6 de este documento.
   3. Condición A: `experiments/gemma_developer_agent/conditions/a_kit/` como copia exacta de
      `data/sample_submission/`. Los dos LoRA del kit pesan **217 672 bytes cada uno** según la API (un LoRA
      real de rango 16 sobre un 31B ronda 110–220 MB, HARNESS § 3.4): casi seguro son de ejemplo. Descárgalos
      (el token sale del `.env`; no lo imprimas), lee sus `adapter_config.json` y escribe qué rango y módulos
      declaran. No los versiones: un manifiesto con SHA-256 y el comando de descarga. Propón en el PR si A
      lleva esos LoRA o es «A sin LoRA», con el argumento; lo decide el orquestador. Muestra
      `diff -r data/sample_submission conditions/a_kit` vacío salvo los pesos declarados.
   4. El `agent.yaml` actual y la skill pasan a `drafts/` con un README que diga qué son: borradores sin
      condición asignada. La skill deja de llamarse placebo hasta que exista C (§ 2.2).
   5. Prototipo: **retira** `gemma_agent.py`, `estimation.py`, `test_gemma_agent.py`, `__init__.py` del
      experimento y `experiments/__init__.py`. Ninguno corre en el envío y el test se aprueba solo. Si quieres
      conservar alguna idea, va como texto en `drafts/`, no como código.
4. **Comprobaciones** antes de abrir el PR, con la salida pegada en el PR:
   - `python -m pytest` completo (sin `-x` y sin filtrar).
   - `ruff check .`, `mypy` y lo demás que pide `CONTRIBUTING.md`.
   - `git ls-files | grep -i -E "\.env|kaggle.json|KGAT"` vacío, y `git ls-files experiments/gemma_developer_agent/data` vacío.
5. **Episodio** `learning/episodes/NNN-issue-102.json` con `estimate` y `outcome` (*Modelo usado* = «Otro
   agente»), y los fallos atribuidos a la acción que los causó: la ficha con datos falsos, la skill con rótulo
   falso, el `__init__.py` que tapaba un paquete. Luego `python -m scripts.devlog rebuild`.
6. **PR** con `Closes #102` en la primera línea del cuerpo. **No hagas merge.** El orquestador lo pasa por
   `revisor-docs` y hace el merge.
7. **Detente** al abrir el PR y avisa. No empieces #103 ni toques el manuscrito ni el pre-registro en este PR.

Criterio de «bien hecho» para este PR: el revisor puede abrir cada fuente que cites, la condición A es idéntica
al kit, y ningún archivo dice que algo existe cuando no existe.
