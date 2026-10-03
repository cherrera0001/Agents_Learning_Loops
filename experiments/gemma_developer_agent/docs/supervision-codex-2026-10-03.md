# Supervisión orientada a entregas y memoria compartida

Fecha: 2026-10-03. Orquestador de esta sesión: Codex.

## Situación y alcance

El dueño reporta más de 12 horas dedicadas a llenar y coordinar el tablero, con dos sesiones de agentes de
entorno trabajando desacopladas. Es tiempo reportado, no telemetría: no se conoce su distribución entre
ejecución, revisión, espera y coordinación. No se atribuye ese tiempo a un modelo ni se convierte en costo.

El tablero es el punto de encuentro entre modelos para resolver el desafío de Kaggle. Su utilidad se
evalúa por entregas aceptadas, dependencias desbloqueadas y evidencia científica obtenida. Abrir tarjetas,
escribir comentarios o mergear infraestructura no demuestra una mejora del agente con Gemma.

Esta supervisión usa los issues existentes. Las tareas de coordinación y los puntos de comprobación se
registran dentro de ellos; no se crean nuevas tarjetas para cada interacción. El hito de documentación se
estima S, 2 puntos, A1/I2/R2/V1, ejecutado por Codex. No cambia la estimación original de #103.

## Observación inicial

Lectura: `gh project item-list 5 --owner cherrera0001 --limit 300 --format json` y listas de issues/PR.

- #103 figuraba como `Todo`, aunque ya tenía entregas mergeadas (#110, #113 y #116) y el PR #117 abierto.
  Codex cambió su tarjeta a `In Progress`; no modificó su verificación pendiente ni lo cerró.
- `python -m scripts.devlog board --since 100`, usando `.venv/Scripts/python.exe`, devolvió
  `sin hallazgos` antes del cambio. Ese chequeo no acredita correspondencia entre trabajo real y `Todo`.
- #102 tiene cierre y verificación registrados. Hay avances de preparación: no se afirma que todo el
  trabajo anterior haya sido improductivo.
- El PR #117 declara que no corrió ningún modelo ni contiene recibos de Gemma. Hay que resolver #103
  mediante una línea base medida; más planificación no cumple ese criterio de cierre.

Fuentes: [épica #100](https://github.com/cherrera0001/Agents_Learning_Loops/issues/100),
[issue #103](https://github.com/cherrera0001/Agents_Learning_Loops/issues/103),
[PR #117](https://github.com/cherrera0001/Agents_Learning_Loops/pull/117).

## Proyección de responsables

Es una asignación prevista. La identidad de las sesiones, su disponibilidad y su acuse siguen pendientes;
no se presenta la publicación de un encargo como aceptación del agente.

- **#101, XS:** el dueño aporta la cuota real; Codex verifica y registra la observación. La inscripción ya
  consta confirmada. La obtención de la cuota y la disponibilidad de L4×4 condicionan la proyección.
- **#103, L:** agy/Gemini es responsable de resolver e integrar el resultado, incluido entorno y recibos
  de sanidad desde el rol evaluador; Claude Code aporta protocolo, contrato de recibos y análisis.
  Codex supervisa y verifica.
  Quien ejecute Gemma se fija al comprobar acceso al notebook y aceptar el encargo. Nadie se supone
  disponible por tener su nombre escrito en el tablero.
- **#104, XL:** agy/Gemini es responsable de resolver la campaña, con Claude Code como colaborador de
  metodología/análisis; Codex supervisa y encarga verificación independiente. Depende de la línea base.
  Se conservan los modelos previstos históricos y se registra quién ejecutó realmente.
- **#105, M, y #109, M:** agy/Gemini previsto para manuscrito y figuras; revisores de citas, números y
  redacción verifican el texto público. Dependencia: resultados disponibles y límites de interpretación.
- **#106, S:** agy/Gemini previsto para empaquetado, Codex verifica; el envío sigue el alcance autorizado.
  Depende de un artefacto compilado y de la selección definida por el protocolo.
- **#107, M:** permanece fuera del trabajo prioritario de esta supervisión. El informe del proceso no
  desplaza la validación que desbloquea #103. No se da por pausada una sesión que no ha recibido el encargo.
- **#98, XL:** responsable Claude Code, Opus 5.5 `xhigh`, según su estimación vigente. En cola tras su
  entrega prioritaria para #103; H8 del solver acotado conserva su propio alcance.
- **#96, M:** responsable Claude Code, Sonnet 5.5 `high`, según su estimación vigente. Bloqueado por
  decisión del dueño entre A/B/C; la asignación no autoriza cambiar el contrato de memoria.
- **#100:** responsable Codex para supervisión, integración entre responsables y cierre de la épica.

Las asignaciones operativas se publicaron en cada uno de los diez issues abiertos. No se crearon issues
ni campos nuevos del Project. La primera publicación es
[asignación #100](https://github.com/cherrera0001/Agents_Learning_Loops/issues/100#issuecomment-5969344114).
Cada responsable debe responder ACEPTO o BLOQUEADO con identidad de sesión, modelo real, entrega,
intervalo de tiempo restante y punto de comprobación UTC. La aceptación todavía no está constatada.

Por instrucción posterior del dueño, se conserva la base del experimento. Este documento y el episodio
son registros de la operación; la síntesis de lo observado se incorpora al final, sin modificar ahora
los protocolos ni las conclusiones existentes.

Las tallas proceden de los registros existentes, no son horas. Para Claude, el modelo de construcción y
esfuerzo siguen `docs/estimation.md`; agy y Codex conservan la regla para agentes no Claude.

## Estimar, medir y proyectar

Antes del siguiente tramo de ejecución, el responsable registra en el issue existente:

1. Agente de entorno y modelo declarado, sesión/worktree, archivos propios y commit de partida.
2. Entrega concreta que completa o desbloquea un criterio de aceptación, con comando de comprobación.
3. Intervalo estimado de tiempo restante, supuestos, incertidumbre y dependencia externa. Si no puede
   estimarse todavía, se registra qué medición falta; no se inventa una fecha de cierre.
4. Próximo punto de comprobación en UTC y evidencia esperada. La estimación no autoriza gasto nuevo.

El orquestador acepta el encargo y el intervalo, o reduce el tramo a una entrega que sí sea comprobable.
Para #103 la primera entrega conjunta es el contrato de validez con ejemplos sintéticos aceptado/rechazado,
más una tarea candidata contrastada sin parche y con referencia en entorno identificado. Eso desbloquea
una campaña; no cierra aún la línea base ni cuenta como resultado de Gemma.

Durante el trabajo se registran inicio, fin, espera y revisión como eventos con fuente y fecha. El tiempo
de ejecución se obtiene de logs; el tiempo humano o de coordinación se declara como tal. Los tiempos de
GitHub permiten medir espera entre eventos, no actividad efectiva de un modelo. Tokens y costo solo se
reportan cuando existe fuente accesible; en otro caso, `no medido`.

Al llegar al punto de comprobación, se registra entrega aceptada/rechazada, criterio que avanzó, tiempo
observado y cambio del intervalo restante. Si no hay artefacto nuevo, se diagnostica el bloqueo y se decide
entre corregir, reducir alcance o reasignar. No se prolonga indefinidamente el mismo relato de avance.

La fecha prevista de un hito se calcula sobre sus dependencias y disponibilidad aceptada, considerando
trabajo paralelo solo cuando no compite por archivos, GPU o cuota. No se suman puntos como horas ni se
promete terminar #104 antes de medir la factibilidad de #103.

## Colaboración que deja memoria

### Encuadre de la postulación indicado por el dueño

En esta sesión, el dueño establece que la operación completa es el objeto de la postulación: Agents
Learning Loops como memoria asociativa o experiencial, construida y utilizada mediante colaboración
supervisada. El caso de coordinación no se relega a un apéndice de administración. El desafío de Kaggle
aporta tareas y resultados externos contra los cuales comprobar qué consigue esa operación.

Esto amplía el encuadre inicial del encargo, centrado en comparar skills con Gemma. No reescribe los
protocolos de campañas anteriores ni convierte hipótesis en resultados. El paper debe conectar el
proceso de aprendizaje supervisado con el desempeño observado, conservando dos niveles de evidencia:

- **Operación de ALL:** experiencias, fallos, recuperación de memoria, cambios de decisión, colaboración
  y verificaciones. Los agentes de entorno y el supervisor forman parte del sistema observado.
- **Resolución del desafío:** tareas verificadas, presupuesto, transferencia, errores y resultados con
  Gemma. La evaluación de reparación comprueba el producto de la operación; su puntaje por sí solo no
  demuestra que la memoria haya causado el avance.

El episodio observable sigue esta cadena: situación y estimación → acción y resultado → diagnóstico
supervisado → experiencia registrada → memoria consultada en una tarea posterior → decisión modificada
→ verificación independiente. Cada enlace requiere una fuente. Si no se observó recuperación posterior,
se ha registrado experiencia, pero todavía no se ha demostrado su reutilización.

Para cada decisión posterior se conserva la consulta de recall, la lección recuperada y su origen, la
acción prevista antes de usarla cuando exista ese registro, la acción elegida y el resultado. Se registra
también qué cambió por intervención del supervisor, de otro modelo o del dueño. Estas intervenciones
pueden ser parte del diseño de ALL; no se atribuyen exclusivamente a la memoria.

La colaboración que corrige un fallo es una observación útil. La afirmación causal «ALL mejora la
resolución» exige comparaciones con controles y un protocolo prospectivo. Cambiar simultáneamente modelo,
supervisión, entorno y memoria impide separar sus aportes. Si el estudio disponible es un caso de campo,
se presenta como tal, con trazabilidad, fallos y límites, sin fingir un experimento controlado.

El emisor entrega ruta, commit/hash, versión de esquema y comando reproducible. El receptor registra si
puede consumirlo y devuelve evidencia de aceptación o un fallo concreto. La publicación, el acuse y la
aceptación son tres eventos distintos. Un único responsable integra cada criterio de cierre.

La bitácora de desarrollo conserva estimación, reparto previsto/real, fallos de coordinación, revisiones,
esperas observadas y lecciones. No se añaden campos arbitrarios al esquema de episodios: estos detalles
van en `steps.note` y en documentos enlazados; `estimate` y `outcome` conservan su formato existente.
La memoria derivada se reconstruye con `devlog rebuild`.

Este caso es observación de proceso de agentes de entorno y forma parte del objeto propuesto para el
paper. No demuestra por sí solo eficacia de skills en Gemma ni superioridad de un modelo. Para atribuir
efectos causales a la coordinación haría falta un diseño con controles; ambos niveles se conectan en el
artículo, pero sus métricas y sus límites se conservan separados.

Encargo operativo y revisión científica preliminar:
[comentario común](https://github.com/cherrera0001/Agents_Learning_Loops/issues/100#issuecomment-5969295054).

## Seguimiento de sesiones y continuación efectiva

La atribución inicial de los reportes pegados en el chat estaba mezclada. El EDA temporal y las dos
revisiones de #117 constan en la transcripción Claude Code, sesión
ee5fe5f1-2f0e-48fc-aa75-230d364337ad, modelo claude-opus-5-5.
El mensaje de 2026-10-03T12:55:10.591Z confirma que envió correcciones y EDA versionado al implementador.
claude agents --json muestra esa sesión ocupada; no se duplicó su encargo.

AGY, conversación 00bad8a5-b1f9-4c70-8b4d-929d34c08a27 de este workspace, estaba IDLE.
Codex la reanudó con el encargo de sandbox reproducible y controles vacíos nuevos:
https://github.com/cherrera0001/Agents_Learning_Loops/issues/103#issuecomment-5969379891 .
El primer intento headless pasó a RUNNING, pero terminó sin respuesta: RunCommand fue denegado porque
no podía solicitar permiso. Su JSON decía SUCCESS pese a incluir denied_actions. No se acreditó entrega.
Los contadores de tokens/duración de ese JSON no se atribuyen al encargo: no se estableció si son
acumulados de conversación o de esa continuación.

Codex continuó interactivamente sin cambiar permisos globales ni usar bypass. AGY respondió ACEPTO,
declaró Gemini 3.8 Flash (High), rama issue-103-entorno-sandbox y punto de comprobación
2026-10-03T14:00:00Z. Esta es declaración de la sesión, no telemetría del proveedor.
La primera respuesta terminó en un plan: Codex volvió a instruir ejecutar una entrega local y asumir
la publicación en GitHub si el contrato de AGY la impedía. Aceptación y artefacto siguen separados.

Responsabilidad por entrega en curso: Claude protocolo/EDA de #117; AGY instrumento local/controles
vacíos; Codex comprueba artefactos, coordina y registra los bloqueos. El responsable integrador previsto
de #103 sigue AGY. No cambia el pre-registro ni la base de las campañas.

Codex reejecutó el EDA temporal y reprodujo sus agregados y el fallo del contador de archivos.
Los tamaños de los dos reportes corresponden a unidades distintas: líneas totales del diff frente a
líneas añadidas/eliminadas sin cabeceras. Ni la longitud del parche demuestra duración de reparación,
ni fallos de tareas aisladas permiten generalizar a todas las tareas de un repositorio.

La corrección del contexto quedó ausente después de las primeras ediciones de AGY. Sus mensajes de
supervisión estaban en cola durante las comprobaciones; Codex interrumpió el tramo para que recibiera el
bloqueo antes del build. Después transfirió explícitamente la ejecución del cambio acotado a Codex
(S, 2 puntos, A1/I1/R3/V2). Codex añadió rechazo de wheelhouse existente con exist_ok=False, sin borrado,
y tests de segunda preparación rechazada y caché previo permitido. Los nueve tests y Ruff pasan en su
ejecución. AGY leyó los cambios y retomó verificación/construcción. El cambio no se atribuye a AGY ni se
presenta como un sandbox ya calibrado.

AGY construyó la imagen sha256:b1e2a17806d06ee3262368550dff61a56d7ef6772360fd6adbe897c1360f4054 y
ejecutó el harness con --skip-agent-patch sobre fastapi_11194 y rich_3061. Codex comprobó los archivos de
artifacts/control-vacio-20261003-v1 (ignorados), cuyo task_results.jsonl tiene SHA-256
c82648cc3e3432de12c44e9b96b746d89fc3bebabe9832fa461071616a8f6de6. La primera tarea termina en la fase de
recolección, con código 2: la construcción de `FastAPI()` falla con las versiones nuevas de starlette. Rich ejecuta tests: 12 failed, 100 passed y código 1
sin parche. La referencia no se probó en este tramo, por lo que no se acredita validez discriminante.
El summary dice errors=0 pese al fallo de colección: esa cifra no sustituye adjudicación desde logs.
El 0/2 del summary no es tasa de resolución de Gemma, que no se ejecutó.

El siguiente tramo de AGY debe entregar una propuesta de entorno justificada desde manifiestos del
snapshot afectado, antes de construir v2 y conservar los controles v1. Claude conserva la corrección
de protocolo/EDA; Codex revisa la propuesta y una muestra de recibos. El checkpoint público de operación
está en [#103](https://github.com/cherrera0001/Agents_Learning_Loops/issues/103#issuecomment-5969599380).

## Nota de integración posterior (Claude Code, 2026-10-03)

Este registro termina antes de la variante v2. La variante y sus dos controles vacíos están descritos en
[`propuesta_entorno_fastapi_v2.md`](propuesta_entorno_fastapi_v2.md). Conviene leerla con el alcance que
fija el pre-registro (§ A.1): es un **ensayo local con Docker** y una lista candidata de arreglos para
`preregistro/entorno_sandbox_v1.json`, medida sobre dos tareas sin parche de referencia. No es el entorno
del experimento ni acredita validez de ninguna tarea. El texto de arriba no se ha reescrito salvo una
frase que citaba el mensaje de error del control v1; ahora lo describe sin copiarlo.
