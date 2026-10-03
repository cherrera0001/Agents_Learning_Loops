# Supervisión del trabajo de agy/Gemini · Kaggle Gemma 4 Developer Agent

> **Registro del 2026-10-02. Superado en varios puntos.** Es un registro fechado y no se reescribe. Hoy
> mandan el [pre-registro de la línea base A](../../../docs/preregistration/kaggle-baseline-a.md) y los
> issues #100 a #103. Ejemplos de lo superado: el presupuesto de 60 minutos por tarea como regla, que este
> registro opone al límite de 12 horas (la página oficial *Evaluation* fija las 12 horas para todas las
> tareas y el presupuesto por tarea se deriva de ellas); la rúbrica del Paper Track, que aquí consta como no
> verificada y luego se leyó en la página oficial; y que la cuenta no estaba inscrita en el Paper Track (hoy
> lo está, #101). Mapa de documentos: [`README.md`](../README.md#12-mapa-de-documentos).

Revisor: Claude (Opus 5.5), orquestador. Fecha: 2026-10-02. Alcance: todo `experiments/gemma_developer_agent/`
sin commitear, más el cambio de `.gitignore`. No se revisó `docs/entorno/revision-texto-publico-2026-10-02.md`.

Fuente oficial contrastada: `data/HARNESS_README.md` (49 356 bytes), descargado hoy con la API de Kaggle desde
los archivos de la competencia `gemma-4-developer-agent` (id 149921). Está en `data/`, ignorado por git. Las
citas «HARNESS § n» remiten a ese archivo. La API confirma: Code Track, cierre 2026-12-02 23:59 UTC, fusión de
equipos y nuevos inscritos hasta 2026-11-25, **1 envío por día**, premio 65 000 USD; Paper Track, cierre
2026-11-12, 35 000 USD. Las reglas y la rúbrica del Paper Track **no se pudieron verificar** (no están en los
archivos de datos).

---

## 0. Veredicto

**Todavía no está alineado con ALL, y la ficha técnica de Kaggle es en gran parte inventada.** Los tests pasan
(4/4 con `.venv`), pero prueban un simulador que no corresponde al harness real. El manuscrito afirma cosas que
el propio README del repositorio declara **no presentadas**. El rumbo de fondo, sin embargo, tiene una versión
honesta y bastante mejor que la actual (§ 4): el harness oficial obliga a que el aprendizaje de ALL ocurra
**fuera de línea** y llegue al envío como skills, y además ya entrega un grafo de código, que es justo el
ancla no léxica que pide H8.

---

## 1. Principios de ALL (AGENTS.md) — cumplimiento

| Principio | Estado | Hallazgo |
|---|---|---|
| Issue + estimación antes de empezar | **No** | No hay issue, épica ni talla. Esto es un XL (experimento nuevo, R = 3 sobre conclusiones públicas). |
| `recall-antes-de-issue` | **No consta** | Ninguna lección de los episodios aparece aplicada (ver § 3: repite errores ya registrados en H4, H6 y H7). |
| PR con `Closes`, revisión independiente, merge del orquestador | **No** | Todo está sin commitear en `main`, mezclado con un cambio de `.gitignore` (que sí es correcto: `.env` no está versionado ni en el historial). |
| Agentes no Claude (§ 2.3 de `docs/estimation.md`) | Pendiente | La estimación debe nombrar a agy/Gemini; *Modelo usado* = «Otro agente». Talla, verificación y cierre sí aplican. |
| Frontera de fuga | **Riesgo nuevo** | En Kaggle el equivalente de `benchmark/private/` es `test_patch`, `FAIL_TO_PASS` y las tareas de evaluación. Nada impide hoy diseñar skills a partir de tareas que luego se evalúan. Hay que declarar la partición antes de generar datos. |
| No reescribir evidencia | OK en intención | Pero el código usa `hash()` (aleatorio por proceso, `PYTHONHASHSEED`) para los ID de nodos: los recibos no serían reproducibles. |
| Texto público con veto (redactor, validador, papers) | **No** | El manuscrito no pasó por ninguno de los tres. |

---

## 2. La ficha `kaggle_specifications.md` contra el harness oficial

| Afirmación de la ficha | Realidad (HARNESS) | Consecuencia |
|---|---|---|
| Se entrega `src/agent_loop.py`, `memory_graph.py`, `estimation.py`, `tools/*.py` | **No se entrega código Python de agente.** Solo YAML declarativo compilado contra registros cerrados de herramientas, modelos, skills y callbacks (§ 2.1). Extensiones permitidas: `.yaml .yml .md .txt .py`(scripts de skill ADK) `.json .safetensors` | `gemma_agent.py` y `estimation.py` **no pueden correr en el envío**. Sirven, como mucho, de harness local. |
| Modelos 2B / 9B / 27B, enrutamiento por talla | **Un único modelo base**: `gemma-4-31b-it-qat-w4a16-ct` (§ 3.2). Declarar otro lanza `ParticipantVisibleError` | Toda la tabla talla → modelo de `estimation.py` y del manuscrito es **inválida** en competencia. El único eje legítimo es: LoRA por subagente (≤ 8, < 3 GiB), `thinking_budget` y presupuestos. |
| GPUs T4/P100 o TPU v3/v4 | 4 × L4, vLLM, `max_model_len = 32 768` (§ 3.1) | |
| Límite global de 12 horas | Presupuesto **por tarea**: 60 min, 100 tool calls, 500 turnos por defecto; ajustable en `eval_config.yaml` (§ 7.1) | El argumento «el circuit breaker evita agotar 12 h» no se apoya en nada. |
| Prefijo estático + KV caching como aporte propio | El harness **ya** compacta eventos y cachea contexto (§ 7.2) | No es novedad; a lo sumo, una decisión de configuración. |
| Criterios del jurado del Paper Track (incluye «taxonomía causal L0–L5 y promoción a skills») | No verificado; la redacción menciona rasgos de ALL como criterio del jurado | Casi seguro escrita desde la propia tesis. **Hay que leer la página real de reglas** antes de escribir una línea más del paper. |
| Score = tareas con PASS / total | Correcto en esencia: *Resolution Rate*, con JUnit validado y reseteo de tests tocados por el agente (§ 8.2) | |

**Pedido a Gemini:** reescribir la ficha desde `HARNESS_README.md`, citando sección por sección, y marcar
como «no verificado» todo lo que no salga de una fuente abierta. Nunca rellenar con lo que la tesis necesita.

---

## 3. Código y tests — preguntas que el código no responde

1. **`retrieve()` no usa el síntoma.** Devuelve las dos primeras estrategias `solved_by` del grafo entero,
   sea cual sea la tarea. No hay activación propagada: `decay_lambda`, `firing_threshold` y `max_hops` de
   `agent.yaml` no se leen en ninguna parte. ¿Dónde está Collins & Loftus?
2. **La inhibición es global.** Un `contradicts` registrado en una tarea inhibe esa estrategia en **todas**.
   Es exactamente el mecanismo que H7 midió como «contamina» (τ = 0.1, 3 de 18 pares). ¿Por qué se reintroduce
   sin alcance?
3. **La skill se promueve al repetir la misma tarea.** El test usa cuatro veces el mismo título. Es el defecto
   que el repositorio ya declaró en H6: «no repite porque la **misma** tarea se repite». La regla del manuscrito
   pide «≥ 3 tareas **independientes**»; el código cuenta `success_count` de la misma cadena.
4. **La skill se activa por subcadena del texto** (`s_key in symptom_text`). Es siembra léxica pura: lo que H4
   refutó (0/18 frente a 6/18 sin memoria).
5. **La estimación usa palabras clave** (`"timeout"` → I = 3). Mismo problema léxico, y contradice
   `docs/estimation.md` § 2.1: la escala no está calibrada y **manda el ancla**, no la suma.
6. **El test de aprendizaje está diseñado para pasar.** `realistic_runner` aprueba cualquier parche que
   contenga la cadena `"Canonical_Fix"`, que el propio agente genera. No hay un fallo que el diseño permita
   (ALL exige tareas donde la memoria **pueda perder**: los señuelos).
7. **«Iteración» no significa nada en el harness real.** k_max = 1 a 4 contra un presupuesto de 100 tool calls:
   ¿una iteración es un turno, una llamada o un ciclo editar-probar? Con k_max = 1 una XS no alcanza ni a leer
   el archivo.
8. **«XS falla directo a triage humano»**: en la evaluación no hay humano. Un abandono temprano es un 0 seguro;
   abandonar solo ahorra tiempo si ese tiempo se reasigna, y el presupuesto es **por tarea**, no compartido.
   ¿Qué gana el disyuntor en puntaje?

---

## 4. Lo que el harness sí permite: la versión honesta de ALL

Hechos del harness que cambian el diseño:

- Cada tarea corre en contenedores nuevos, `/workspace` se borra, y no hay código propio ni red. **No hay
  memoria entre tareas en tiempo de evaluación.**
- Sí se pueden entregar `skills/*/SKILL.md`, prompts, subagentes (`AgentTool`) y LoRA.
- El harness trae `get_code_neighbors`, `get_code_subgraph` y `search_similar_code` sobre un grafo AST /
  de dependencias precalculado (HARNESS § 6.3). **Eso es un ancla estructural no léxica gratis**: la pregunta
  de H8 (#98) se puede probar ahí.

Propuesta para que Gemini profundice:

1. **El bucle de aprendizaje es fuera de línea.** Correr el agente base localmente (`swegemma eval`) sobre un
   conjunto de **entrenamiento** declarado, registrar episodios con recibos, consolidar lecciones y empaquetarlas
   como `SKILL.md`. En evaluación, el agente solo lee skills. Así «promoción a skill» deja de ser trabajo futuro
   y pasa a ser **la** intervención medida.
2. **Diseño mínimo pre-registrado** (antes de generar datos):
   - A = starter kit sin skills; B = mismas skills escritas a mano sin experiencia (placebo de longitud);
     C = skills consolidadas desde episodios; opcional D = C con recuperación sembrada por el grafo de código.
   - Partición entrenamiento / prueba por repositorio **y** por tarea; nada de la prueba entra en las skills
     (frontera de fuga).
   - Métrica primaria: tasa de resolución en prueba local. Secundarias: tool calls y tiempo por tarea resuelta.
   - Regla de decisión y predicción escritas antes, como en H4.
3. **Incluir señuelos**: tareas cuyo enunciado se parece a una skill pero la causa es otra. Si C no pierde
   nunca, el diseño no prueba nada.
4. **Estimación**: si se usa, que gobierne `thinking_budget` y el reparto de tool calls entre subagentes, no el
   modelo. Y que la talla se estime **después** de una exploración barata con el grafo, no por palabras clave.
5. **El envío diario (1/día) es una medición ruidosa y escasa.** No sirve para elegir entre variantes; sirve
   para confirmar la elegida.

### ¿Qué esperamos?

Predicción del orquestador, para registrar: **una diferencia pequeña o nula entre A y C** en tasa de
resolución, porque la experiencia de un repositorio transfiere poco a otro (lo que H4, #58 y H7 vienen
mostrando), y una ventaja posible de D solo en tareas con señuelo. Un resultado así, bien medido, es un buen
paper; un 0.9 inventado no lo es.

---

## 5. Manuscrito — afirmaciones que deben salir o bajar de tono

Contrastadas con el README (sección «Qué no presenta» y tabla de hallazgos):

| En el borrador | Problema |
|---|---|
| «demonstrate how ALL maintains strict prefix KV-caching efficiency on Gemma 4» | No hay ninguna medición con Gemma ni de tokens. El README: «no presenta resultados con agentes LLM, mediciones de tokens o de costo». |
| Promoción a skills como pilar implementado | README: la promoción «queda como trabajo futuro». |
| «To permanently eliminate negative transfer… H8» | H8 está **abierta** (#98) y sin datos. |
| «We demonstrate that Vector RAG fundamentally breaks» (NRNE, L0–L5) | El repositorio no midió RAG vectorial. Es una hipótesis. |
| «Stochastic retry illusion» como descripción de agentes del estado del arte | Sin cita. Y el solver propio es determinista, con tres operadores escritos a mano, sin LLM: hay que decirlo en § 6. |
| H1–H3: «attempt reduction 2.0 → 1.0», «18/18 vs 18/54» | Correctos, pero omite que `RepeatedFailureRate` = 1.0 en las tres condiciones, #58 (−2/18 en engañosas) y H7 «contamina». Citar solo lo favorable es lo que ALL prohíbe. |
| Tabla talla → Gemma 2B/9B/27B | Prohibido por la regla de modelo único. |
| Fórmula de activación «Collins & Loftus» con √deg y e^(−λ) | Collins & Loftus (1975) no da esa fórmula; hay que atribuirla a la implementación propia o a la fuente que la tenga (pasar por `investigador-papers`). |
| Enlace `file:///F:/Code/...` | Ruta local, rota para cualquier lector. |
| «Cristóbal Herrera et al.» | ¿Quiénes son los demás autores? Si no hay, sin «et al.». |
| «resolve complex software defects deterministically» (conclusión) | No hay ni un defecto resuelto con Gemma todavía. |

---

## 6. Requisito nuevo: «informes inteligentes» del proceso, sobre GitHub Projects, construidos por Gemini

Pedido del dueño del proyecto: algo equivalente a los informes inteligentes de Claude Enterprise (flujos de
trabajo, entregables, costo por tipo de resultado, resultados, fricciones, ineficiencias, skills reutilizables,
sesiones más caras, trabajo autónomo complejo, preguntas propias), pero alimentado por el **Project #5** y la
bitácora, y construido por Gemini.

Qué ya existe y no hay que duplicar: `python -m scripts.devlog board` (chequeo del tablero) y `pilot`
(lectura del piloto). Los episodios (`learning/episodes/*.json`) tienen `estimate`, `outcome`, `steps` (con
`success` y `error`) y `lessons`.

| Sección del informe | Fuente en ALL | Brecha |
|---|---|---|
| Flujos de trabajo | Tipo del issue (código / docs / experimento), épica, talla | — |
| Entregables | PRs mergeados (`mergedAt`) y archivos tocados | — |
| Costo por tipo de resultado | Tokens de transcripciones de Claude (solo esta máquina) | **Gemini/agy y Codex no dejan tokens**: añadir `outcome.cost` con su fuente, o «no medido». Nunca estimarlo. |
| Resultados | *Verificación* del tablero, `outcome.escalated`, `estimate_revisions` | — |
| Fricciones más comunes | `steps[].success = false` y su `error` | Hace falta una taxonomía cerrada de categorías, escrita antes de clasificar. |
| Ineficiencias | Done sin *Verificación*, PR sin `Closes`, reaperturas, escalamientos | — |
| Skills a construir | Lecciones repetidas entre episodios | Usar **la misma regla que ALL**: ≥ 3 episodios independientes sin contradicción. Es dogfooding directo de la tesis. |
| Más caros / más autónomos | Tokens y duración por sesión | Solo donde haya transcripción. |

Reglas para que el informe sea de ALL y no un adorno:

1. **Los números los produce un script determinista** (comando `devlog` nuevo o vecino); Gemini solo agrupa y
   redacta, y todo texto suyo va marcado como interpretación.
2. Cada cifra con su fuente; pasa por `validador-estadistico` si se publica.
3. Solo lectura sobre GitHub, como `board` y `pilot`.
4. Como en el original: **no es para evaluar personas**. Mide el proceso y a los agentes.
5. Es un issue propio (talla S o M), con estimación y PR; no va dentro del issue de Kaggle.

---

## 7. Próximos pasos (en orden)

1. El orquestador abre la épica de Kaggle con dos issues hijos (Paper XL, Code XL) y el issue del informe;
   estimación v1 nombrando a agy/Gemini.
2. Gemini reescribe `kaggle_specifications.md` desde el HARNESS y lee las reglas reales del Paper Track.
3. Gemini reemplaza `agent.yaml` por uno válido para `adk-submission` (modelo único) partiendo del starter kit,
   y lo corre localmente una vez para tener la línea base A con recibos.
4. Pre-registro del diseño A/B/C/D (§ 4) antes de generar datos.
5. Recién entonces, el manuscrito: reescrito desde los resultados, con los tres vetos de texto público.
6. Commit en rama propia y PR; el `.gitignore` va en un commit separado.
