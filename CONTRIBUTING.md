# Contribuir

## Entorno

```bash
python -m venv .venv && .venv/Scripts/activate   # Linux/macOS: source .venv/bin/activate
pip install -e .[dev]            # añade ,embeddings para los tests semánticos
```

## Flujo por issue (la vida del proyecto)

Cada issue es un episodio del bucle de aprendizaje del propio repo ([`learning/README.md`](learning/README.md)).
Quien lo ejecuta es un agente de entorno: empieza por [`AGENTS.md`](AGENTS.md), que remite al
[glosario](docs/entorno/glosario.md) y al [harness de entorno](docs/entorno/harness.md). Los pasos 1, 3, 5, 7
y el manejo de evidencia tienen skills de entorno: [`estimar-issue`](skills/estimar-issue/SKILL.md),
[`recall-antes-de-issue`](skills/recall-antes-de-issue/SKILL.md),
[`registrar-episodio`](skills/registrar-episodio/SKILL.md),
[`confirmar-cierre`](skills/confirmar-cierre/SKILL.md) y [`proteger-evidencia`](skills/proteger-evidencia/SKILL.md).

Este es el **único texto canónico** del ciclo; los demás documentos lo enlazan y, a lo sumo, muestran su
diagrama:

```text
Issue listo (plantilla) → ESTIMAR → In Progress → RETRIEVE → implementar (rama + PR) → episodio
→ CONSOLIDATE → REVISAR → merge → CONFIRMAR → Done
```

0. **Issue listo**: escrito con la plantilla [`issue.md`](.github/ISSUE_TEMPLATE/issue.md) (o
   [`epica.md`](.github/ISSUE_TEMPLATE/epica.md)), con su *Tipo de cierre* y su *Evidencia requerida*.
1. **ESTIMAR** (orquestador), antes de que nadie empiece. La talla y el modelo de construcción salen de
   [`docs/estimation.md`](docs/estimation.md) y se aplican como indica
   [`docs/entorno/enrutamiento.md`](docs/entorno/enrutamiento.md). Se registra en el issue y en el
   tablero: la sección «Estimación v1» (con fecha) en el cuerpo del issue y los campos *Talla*, *Puntos*, *Incertidumbre*,
   *Riesgo* y *Modelo* del Project #5. *Modelo* es el modelo **previsto**; los puntos son tamaño
   relativo, no horas ni tokens. La talla se copia además en una etiqueta `talla:<talla>` del issue, para
   que el peso se vea sin abrir el tablero; si etiqueta y campo difieren, manda el campo. Procedimiento:
   skill [`estimar-issue`](skills/estimar-issue/SKILL.md).
2. **In Progress** (implementador): la tarjeta pasa a *In Progress* al crear la rama
   `issue-<n>-<tema>`.
3. **RETRIEVE**: `python -m scripts.devlog recall "<título del issue>"` (`--embedder fastembed` para
   búsqueda semántica). Lee las lecciones antes de elegir herramientas.
4. **Implementar** con tests y abrir el PR. Cada test debe poder fallar: añade un control cuando el efecto
   pueda quedar oculto. El PR lleva `Closes #<n>`, salvo que el *Tipo de cierre* sea «sistema externo»
   y falte la observación: entonces `Refs #<n>` ([criterios de cierre](docs/entorno/harness.md#criterios-de-cierre-por-tipo-de-trabajo)).
   El implementador no hace merge.
5. **Registrar** `learning/episodes/NNN-issue-<n>.json` con los fallos **tal como ocurrieron** (en la
   acción que los causó), más los bloques opcionales `estimate` y `outcome`
   ([formato](learning/README.md#formato-de-un-episodio)).
6. **CONSOLIDATE** (local; ya no se entrega): el grafo `learning/dev_memory.json` **no se versiona**
   ([#96](https://github.com/cherrera0001/Agents_Learning_Loops/issues/96); motivo en
   [`learning/README.md`](learning/README.md#por-qué-dev_memoryjson-no-se-versiona)). El PR lleva el episodio y
   nada más de la memoria; `recall` lo deriva de `learning/episodes/` y CI comprueba que `rebuild` funciona y
   es determinista. Quien quiera el archivo en disco ejecuta `python -m scripts.devlog rebuild`.

   **REVISAR** (antes del merge): el orquestador encarga la revisión del PR a un revisor independiente
   del autor
   ([`revisor-codigo`](.claude/agents/revisor-codigo.md) o [`revisor-docs`](.claude/agents/revisor-docs.md),
   según lo que toque; ambos si toca código y documentos), y decide el merge con su informe y con el CI en
   verde. El revisor informa y no edita; las correcciones vuelven al implementador o las hace el
   orquestador, y si la verificación falla se escala un modelo (regla 2 de `docs/estimation.md`).
7. **CONFIRMAR** (orquestador), después del merge squash **verificado** (`mergedAt`) y no antes. Se
   comprueba el criterio de cierre según el tipo de trabajo y se escribe en el tablero y en el issue:
   *Verificación* = *Verificada* con la evidencia enlazada, *Modelo usado* y *Escaló*. Si falla,
   *Verificación* = *Fallida* y el issue se reabre si el merge lo cerró. Procedimiento: skill
   [`confirmar-cierre`](skills/confirmar-cierre/SKILL.md).
8. **Done**: una tarjeta en *Done* **no es un cierre confirmado**; el cierre confirmado es
   *Verificación* = *Verificada*. Las automatizaciones del Project #5 actúan en los dos sentidos: al
   mergear un PR con `Closes #<n>` mueven la tarjeta a *Done* antes de CONFIRMAR, y mover una tarjeta a
   *Done* a mano cierra el issue. Por eso nadie mueve a mano antes de CONFIRMAR, y CONFIRMAR termina con
   `python -m scripts.devlog board --since <n>` sin hallazgos: su regla 3 señala toda tarjeta en *Done*
   sin verificar.

Responsables: el **orquestador** estima y confirma; el **implementador** pasa a *In Progress*,
implementa y registra el episodio ([roles](docs/entorno/agentes.md)).

### Reglas del registro

- **La estimación se conserva.** Si cambia el alcance, se añade un comentario «Estimación v2» con fecha,
  motivo y evidencia; la v1 no se reescribe.
- **El modelo previsto no se sobrescribe.** El campo *Modelo* sigue siendo el previsto aunque se escale;
  el resultado va en *Modelo usado* y *Escaló*. *Modelo usado* es autoinformado salvo que exista una
  transcripción.
- **La verificación del cierre no va en el episodio.** El episodio se escribe antes del merge y
  quedaría obsoleto; la verificación vive en el tablero y en el issue.
- Campos, métricas y límites del piloto: [`docs/piloto-estimacion.md`](docs/piloto-estimacion.md).
  Chequeo de coherencia entre issues, tablero y episodios, de solo lectura:
  `python -m scripts.devlog board --since <n>` ([reglas](learning/README.md#chequeo-del-tablero)).
- **Un issue cerrado sin trabajo** (creado por error o repetido) se cierra como «no planeado» o
  «duplicado», con un comentario que dice a qué issue remite. El chequeo del tablero lo exime de las
  reglas 2, 3 y 9 solo si ningún episodio lo cita con `#n` en su `ref`, y lo avisa por stderr.

## Jerarquía: épica, issue, tareas

Tres niveles, definidos aquí y en ningún otro sitio:

| Nivel | Qué es | Reglas |
|---|---|---|
| **Épica** | Issue con la etiqueta `epic` y subissues ([`epica.md`](.github/ISSUE_TEMPLATE/epica.md)) | Solo si tres o más issues comparten un resultado. No se estima: muestra la suma de sus hijos. Se cierra con todos los hijos obligatorios cerrados y sus criterios propios cumplidos. |
| **Issue** | La unidad que se estima ([`issue.md`](.github/ISSUE_TEMPLATE/issue.md)) | Se asigna a un modelo o agente, tiene tarjeta en el Project #5 y se cierra. |
| **Tareas** | Lista de verificación en el cuerpo del issue | Sin tarjeta ni talla. |

Si un issue necesita subissues, se convierte en épica y deja de estimarse. No hay nivel «historia de
usuario».

## Revisión de un texto público

Un texto que explica el proyecto hacia fuera (el README, un post, un artículo) pasa por tres roles antes de
publicarse. Cada uno tiene veto y solo informa: ninguno publica.

1. El **investigador de papers** comprueba cada obra citada.
2. El **validador estadístico** da un veto o un visto bueno a cada número y a cada verbo de resultado, con el
   archivo que lo sostiene.
3. El **revisor redactor** reescribe el texto sin ninguna frase vetada y conserva qué se midió, en qué diseño
   y qué salió peor.
4. El validador lee el texto reescrito **entero y en su versión exacta**. Un texto solo está firmado si su
   última respuesta cita el conteo de caracteres y no veta nada; cualquier cambio posterior exige otra lectura.

**Citas.**

- Solo se cita una obra cuyo DOI, ISBN o URL del editor se abrió en esa revisión. El registro de Crossref de
  un DOI cuenta como abierto y se anota como tal. Lo que la página abierta no muestra no se completa de
  memoria.
- Se parte del código: una obra acompaña a un mecanismo que el repositorio nombra. Si el texto nombra una
  obra que el código no nombra, se dice si el código la implementa o solo comparte la idea.
- Una cita no hereda la conclusión del paper ni prueba un resultado propio.

**Números y verbos de resultado.**

- Cada número lleva su fuente: archivo y, si existe, recibo o comando. Sin fuente, «no está en el repo» y
  veto. Un porcentaje va con su numerador y su denominador.
- No hay inferencia estadística: seis o nueve tareas, un proyecto, tres operadores y réplicas de la misma
  semilla no son una muestra. Las réplicas verifican determinismo.
- `LearningGain` es `metric(memoria) − metric(sin memoria)`, como lo define el
  [protocolo](specs/software_learning_protocol.md) (*Metrics and falsification*), no una diferencia de
  probabilidades de éxito. `LearningGain` y `MemoryUtilityRate` son métricas de este laboratorio, no un ensayo.
- Una medida no se lee como otra: la cobertura de tests no es una tasa de aprendizaje, un `delivered` no es
  bandeja de entrada y un LCP de laboratorio no es un dato de campo. Los recibos no registran tokens ni costo.
- Una cifra vigente que ya no coincide con su fuente es falsa; una cifra fechada se comprueba contra su fecha.
- Cada «resuelve», «aprende» o «significativo» recibe su fuente o un veto. «Aprende de verdad» y «memoria
  humana» no se usan sin la firma del validador.

**Redacción.**

- Español, frases completas, para alguien técnico que no vive en el repositorio, con los nombres del
  [glosario](docs/entorno/glosario.md). Sin anuncio: sin preguntas retóricas, cifras de gancho ni adjetivos
  de venta.
- No se inventan cifras ni enlaces; un enlace solo entra si ya está en el README. Un texto cortado se revisa
  hasta donde llega y no se completa. No se añaden hashtags.
- Una frase vetada no queda en el texto reescrito, ni entera ni parafraseada. Lo que un texto propone como
  debate se marca «pregunta abierta», no arquitectura del repositorio.

**Vetos obligatorios.** No se publica:

1. una ventaja de la memoria asociativa sobre el historial textual:
   [H4](docs/results/h4-associative-vs-history.md) no la sostiene;
2. como hecho, lo que el protocolo deja sin implementar: la promoción de una lección a skill, y UPDATE, MERGE
   y DEPRECATE, que se pueden representar y se rechazan;
3. como siguiente paso, algo que el repositorio ya probó;
4. como arquitectura del repositorio, algo que su código no tiene;
5. una afirmación general que un resultado negativo publicado contradice.

Las fichas de las obras y los vetos concretos de cada revisión se guardan en un registro fechado en
`docs/entorno/` (el primero: [2026-10-02](docs/entorno/revision-texto-publico-2026-10-02.md)), no en las
skills.

Roles: [`docs/entorno/agentes.md`](docs/entorno/agentes.md#staff-de-texto-público). Skills de entorno:
[`investigador-papers`](skills/investigador-papers/SKILL.md),
[`revisor-redactor`](skills/revisor-redactor/SKILL.md),
[`validador-estadistico`](skills/validador-estadistico/SKILL.md),
[`auditor-datos`](skills/auditor-datos/SKILL.md) y
[`revisor-figuras-tablas`](skills/revisor-figuras-tablas/SKILL.md).

Orden de una revisión con datos: auditor de datos (de qué medición sale cada cifra y si sigue vigente),
investigador de papers y revisor de figuras y tablas en paralelo, revisor redactor, y al final el
validador estadístico, que firma la versión exacta citando su huella. Cualquier cambio posterior exige
otra firma. La skill [`revisar-manuscrito`](skills/revisar-manuscrito/SKILL.md) fija ese orden y empieza por
`python -m scripts.paper_check comprobar <manuscrito>`, que encuentra sin agentes lo mecánico (extensión,
citas sin entrada, tablas sin nota, cifras del resumen sin respaldo).

## Vuelta de un experimento con modelo

Una **vuelta** es un ciclo de un experimento que corre un modelo de lenguaje en un sistema que cuesta
(cuota de GPU, envíos contados, dinero): bajar lo que dejó la corrida anterior, leerlo, decidir y, si el
dueño lo ordena, correr otra vez. Este procedimiento es de agentes de entorno; no cambia el agente de
biblioteca ni el solver acotado. Lo ejecuta el orquestador con el
[staff de experimento](docs/entorno/agentes.md#staff-de-experimento).

1. **Recall.** `python -m scripts.devlog recall "<pregunta de la vuelta>"` desde una rama al día con
   `origin/main`.
2. **Rescate demostrado.** El orquestador baja lo que dejó la corrida con el guion de rescate del
   experimento y anota el código de salida, la hora UTC y la ruta. La prueba del rescate es una lista de
   archivos con sus bytes y líneas, también de lo que hay dentro de los archivos comprimidos; no es un
   relato. Un archivo exigido de 0 bytes es un faltante, aunque el guion haya salido con 0. Sin rescate
   demostrado no hay concilio.
3. **Estado de lo remoto.** El estado de un envío o de una corrida remota puede cambiar: se lee al menos
   dos veces, separadas en el tiempo, antes de afirmarlo, y cada lectura se guarda con su hora. Un error
   genérico de la plataforma se anota «sin lectura», se vuelve a leer en el rescate siguiente y no cuenta
   como refutación de una predicción.
4. **Concilio.** Roles independientes, en paralelo, sobre los mismos archivos. Ninguno modifica el
   repositorio, la evidencia ni un sistema externo; lo que ejecutan lo ejecutan en local y escriben solo
   en una carpeta ignorada por git.
   - Van siempre el analista de datos, el forense del arnés y el auditor del método. Según la pregunta se
     suman QA de trayectorias (si se propone cambiar la conducta del agente), el arquitecto de IA (si se
     propone cambiar el modelo, el presupuesto o el cómputo, o adoptar un método ajeno) e inteligencia
     pública (si el experimento se mide en un sistema externo).
   - Cuando una corrida o un envío falla sin explicación, el forense del arnés se convoca de inmediato,
     sin esperar a que alguien lo pida.
   - El orquestador da a cada rol la pregunta, las rutas y las prohibiciones, no su conclusión: un rol al
     que se le entrega la hipótesis la devuelve confirmada.
   - Cada rol separa lo medido, lo inferido y lo no medido, dice qué refutaría su conclusión y termina con
     la lista de eventos de fallo que no dejaron rastro en ningún archivo.
   - El orquestador cruza los informes. Cuando llega un hecho nuevo, vuelve a preguntar a cada rol qué
     afirmación suya se cae. Los desacuerdos se anotan con el dato que los cerraría; no se promedian.
5. **Verificación limpia.** Si el relato de la vuelta ya cambió de conclusión, o si la decisión cuesta
   dinero, cuota o un envío, un verificador que no hereda el relato vuelve a medir sus afirmaciones,
   entregadas como frases sin cifras. Es la única excepción al paso 2: hace su propio rescate, con el
   guion de solo descarga y la credencial del experimento, que nunca imprime. Si su recuento difiere del
   relato, vale el suyo y se anota la diferencia.
6. **Registro.** El orquestador copia en la bitácora del experimento el parecer de cada rol tal cual, lo
   que cada uno retiró y sus propios fallos de la vuelta; los roles no escriben en ella. La vuelta deja un
   episodio en `learning/episodes/` el mismo día.
7. **Decisión.** El concilio va antes de preguntar. Subir, enviar o pagar lo decide el dueño, con la orden
   a la vista.

Skills: [`concilio-de-experimento`](skills/concilio-de-experimento/SKILL.md) (pasos 1 y 4 a 7) y
[`corrida-valida`](skills/corrida-valida/SKILL.md) (pasos 2 y 3 y el criterio que sigue).

Criterio, aprobado por el dueño el 2026-10-08:

- **Corrida válida.** Cuenta solo si cada tarea deja en disco, con bytes mayores que 0 y con huella:
  traza, parche, salida de pruebas y una fila con el motivo de fin aunque la tarea se resuelva, más la
  última petición en vuelo; y si quedan el notebook o el archivo de envío exacto, el log completo de la
  sesión y las predicciones fechadas antes de subir. Un envío a una tabla no es una corrida válida: es una
  nota. Solo se envía una condición que ya tiene una corrida válida. Una corrida que no cumple se usa como
  exploración, no como base de una decisión.
- **Decisión válida.** Conservar o descartar una condición exige una predicción previa con su umbral, el
  mismo conjunto de tareas en los dos brazos, 60 tareas o más por brazo o 6 pares discordantes a favor,
  la prueba exacta de McNemar con p ≤ 0,05 y una repetición de la base en la misma semana. Con menos, el
  resultado se anota «exploratorio» y no cambia la configuración enviada.

De dónde salen los dos números. Los **6 pares discordantes** están derivados: es el suelo de la prueba
exacta con α = 0,05
([análisis de réplicas](experiments/gemma_developer_agent/docs/analisis_replicas.md#método-diferencia-mínima-significativa)).
Las **60 tareas por brazo** no tienen derivación versionada: es el umbral que propuso el auditor del método
en la vuelta 39 del experimento Kaggle y que el dueño aprobó con el resto del criterio. Un experimento con
otro pre-registro fija los suyos antes de correr.

## Comprobaciones (las mismas que CI)

```bash
ruff check . && ruff format --check .
mypy
pytest --cov                                # unit + integration, cobertura ≥ 90 %
python -m scripts.export_schema --check     # specs/memory_schema.json sincronizado
python -m scripts.mutation_check            # cada propiedad detecta su defecto inyectado
```

`mutation_check` tarda más de diez minutos. Un subagente implementador o revisor no la lanza en local
salvo que el encargo lo pida: lee su resultado en el CI del PR.

## Tests

| Carpeta | Qué contiene | Ejecutar |
|---|---|---|
| `tests/unit/` | Grafo, modelos, activación (valores a mano), consolidación, embeddings, configuración y **propiedades** (`hypothesis`) | `pytest tests/unit` |
| `tests/integration/` | Agente completo, benchmark, CLI, bitácora `learning/`, valencia contextual entre dominios | `pytest tests/integration` |

Los tests marcados `embeddings` requieren el extra `[embeddings]` y se omiten sin él.
Al añadir una propiedad, añade también su mutación en `scripts/mutation_check.py`: una propiedad que ninguna mutación rompe no está probando nada.

## Convenciones

- Código e identificadores en inglés; docstrings, docs y mensajes en español.
- Commits: `tipo(ámbito): descripción (#issue)` (`feat`, `fix`, `docs`, `build`, `test`, `chore`).
- `specs/memory_schema.json` es generado: cambia `src/associative_agent_loop/memory/models.py` y ejecuta `python -m scripts.export_schema`.
