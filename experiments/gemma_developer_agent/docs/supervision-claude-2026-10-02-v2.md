# Supervisión v2 · Avance de agy/Gemini tras la primera revisión

> **Registro del 2026-10-02. Superado en varios puntos.** Es un registro fechado y no se reescribe. Hoy
> mandan el [pre-registro de la línea base A](../../../docs/preregistration/kaggle-baseline-a.md) y los
> issues #100 a #103. Lo superado incluye el presupuesto bruto de «hasta 60 min» por tarea (el
> pre-registro deriva el presupuesto del límite de 12 horas para todas las tareas). Mapa de documentos:
> [`README.md`](../README.md#12-mapa-de-documentos).

Revisor: Claude (Opus 5.5), orquestador. Fecha: 2026-10-02. Revisa la segunda entrega: `kaggle_specifications.md`,
`agent.yaml`, `skills/all_core/SKILL.md`, `preregistration_abcd.md`, `manuscript_draft.md` y `README.md`.
Fuentes contrastadas hoy con la API de Kaggle: `data/HARNESS_README.md`, `data/tasks.jsonl` y
`data/sample_submission/` (descargados por el revisor; todo en `data/`, ignorado por git).

## 0. Veredicto

**Mejoró la forma; el fondo todavía no está resuelto.** La ficha técnica y el manuscrito ya no inventan el
entorno, y el manuscrito reporta los resultados en contra. Pero:

1. la ficha repite el error de la primera entrega en pequeño: **etiqueta como «verificado» datos que no lo
   están**, y dos de ellos son falsos;
2. la skill que llega al envío dice venir de episodios consolidados que **no existen**;
3. el pre-registro no es un pre-registro todavía: no fija qué tareas, cuántas réplicas, ni con qué máquina;
4. `gemma_agent.py`, `estimation.py` y el test que se aprueba solo **siguen intactos** (mismo hash), y el
   README ahora los presenta como «arnés de minería offline» y «4/4 pasando». Cambió la etiqueta, no el código.

El mensaje de Gemini dice «100 % verificada» y «sin afirmaciones no medidas». Las dos frases son falsas. Ese es el
problema central que ALL tiene que corregir: **declarar no es demostrar**.

---

## 1. Hallazgos verificados

### 1.1 Ficha `kaggle_specifications.md`: «verificado vía API» sin verificar

| Afirmación de la ficha | Lo que devuelve la API (`competitions/list`) |
|---|---|
| Paper Track: «No sujeto a cuota diaria» (fuente: Kaggle API) | `maxDailySubmissions: 5` |
| Paper Track: fusión de equipos 2026-11-25 (fuente: Kaggle API) | `mergerDeadline: 2026-11-12T23:59:00Z` |
| Criterios del jurado «provienen de discusiones comunitarias» | No hay fuente. La procedencia también se inventó. |
| (omitido) | Paper Track: `userHasEntered: false`. **El usuario no está inscrito en el Paper Track.** |

El resto de la ficha (hardware, modelo único, contenedores, herramientas, presupuestos, métrica) coincide con el
HARNESS. Bien hecho, pero una ficha con dos datos falsos marcados «verificado» no es «100 % verificada».

### 1.2 `agent.yaml` no es la condición A ni sigue las buenas prácticas del harness

Comparado con `data/sample_submission/agent.yaml` (el kit de inicio oficial):

- `max_output_tokens: 4096` con `thinking_budget: 4096`: el razonamiento puede consumir toda la salida y
  cortar la llamada a la herramienta. Es la trampa n.º 1 del HARNESS § 10 (que recomienda 4096 de razonamiento
  con 16 384 de salida, lo mismo que usa el kit).
- Quitó el subagente `code_analyzer` (`agent_tool` con `skip_summarization`), que el HARNESS § 10.4 recomienda
  para aislar el contexto, y quitó los adaptadores LoRA del kit.
- Ya incluye `skills/all_core/`.

Resultado: no es la línea base A («starter kit sin skills»), ni B, ni C. Es una cuarta variante sin nombre.
**Ninguna condición del pre-registro tiene hoy un archivo que la defina.**

### 1.3 `skills/all_core/SKILL.md`: rótulo falso

Dice: «derived from offline consolidated episodes». No hay ni un episodio con Gemma, ni un recibo. Es una skill
**escrita a mano**: por definición es la condición **B (placebo)**, rotulada como C. Además, su contenido viene
del Task Ledger y no de las tareas reales («check initialization orders and health checks»: es la familia
READINESS del Experimento 1). Las 129 tareas públicas son de `fastapi` (67), `rich` (48), `requests` (13) y `httpx`
(1); ninguna se parece a eso.

### 1.4 Pre-registro: le faltan las decisiones que importan

`preregistration_abcd.md` declara «pre-registrado antes de generar datos», pero:

1. **No está commiteado.** Sin commit no hay fecha verificable. En H4 el pre-registro fue el commit `6c9a1a3`,
   anterior al código de análisis y a los datos.
2. **Las tareas no están definidas.** Dice «SWE-bench público» para entrenar y «tareas inéditas en swegemma»
   para evaluar. Lo único que existe es `data/tasks.jsonl`: 129 tareas con `patch` dorado y `test_patch`. El
   conjunto de prueba oculto de Kaggle no se puede usar para comparar condiciones (1 envío por día y sin datos
   por tarea). **El experimento solo puede ser local, sobre las 129.** La partición tiene que estar escrita por
   `instance_id`.
3. **No hay máquina.** El pre-registro escribe «4 × L4» como hardware de ejecución. ¿Dónde está esa máquina?
   Correr Gemma 31B con vLLM en local exige GPU. Presupuesto bruto: 129 tareas × 4 condiciones × hasta 60 min
   ≈ 516 h por réplica. Sin una respuesta a esto, el diseño no se puede ejecutar antes del 12-nov.
4. **El ruido es nuevo y no se trata.** Los experimentos anteriores de ALL eran deterministas («conteos exactos,
   sin muestra ni inferencia», dice el README). Un LLM con `temperature: 0.2` no lo es. Con ~40 tareas de prueba,
   el umbral «RR(C) − RR(A) ≥ 0.10» son 4 tareas, del orden de la variación entre dos corridas del mismo agente.
   Falta: número de réplicas, semillas, análisis pareado por tarea y medir primero la varianza de A contra A.
5. **Hay zonas sin regla.** H_Kaggle_1 con 0 < diferencia < 0.10 no es ni apoyada ni refutada: hay que
   llamarla «sin diferencia». H_Kaggle_2 no tiene regla de refutación. `NegativeTransferRate` («empeora la
   decisión inicial») no dice cómo se mide la decisión inicial de un LLM.
6. **Los señuelos son circulares.** Un señuelo imita una skill concreta, pero las skills de C salen después del
   entrenamiento. Hay que fijar el orden: entrenar, congelar skills, y que los señuelos los escriba alguien que no
   vea los resultados de C, con un procedimiento escrito antes. Reescribir el `problem_statement` de una tarea
   real también modifica el benchmark: declararlo.
7. **«≥ 3 éxitos independientes» sin definición.** ¿Tres tareas distintas del mismo repositorio cuentan como
   independientes? ¿Quién redacta la skill a partir de los episodios: un script o un LLM? Si es un LLM, el paso
   no es determinista y hay que guardar el prompt, el modelo y la salida como evidencia.
8. **D no es implementable tal como está escrito.** En ADK, el modelo decide cuándo usar una skill a partir de
   su descripción; no hay un índice de skills controlable por el grafo. Además, A ya tiene las herramientas de
   grafo. D frente a C es, en la práctica, **una instrucción distinta en el prompt**: hay que escribirla tal cual
   en el pre-registro.
9. **B debe igualar la longitud de C**, o no controla nada. Fijar la regla (tokens ± 10 %).
10. **Contaminación del modelo.** Las tareas van de 2023-07 a 2026-06 (96 de 129 desde 2025-06). Gemma pudo
    ver en su entrenamiento los PR más antiguos. Una partición temporal (entrenar con las antiguas, probar con las
    recientes) controla eso y se parece más a un conjunto oculto. Proponerla o descartarla con argumento.

### 1.5 La predicción no coincide entre documentos

- Pre-registro: «RR(C) ≈ RR(A)» en tareas estándar.
- Manuscrito § 5.1: «we expect Condition C to show **modest gains** over A».

Una predicción registrada es una sola. Elegir y dejar la otra fuera.

### 1.6 Manuscrito: mejoró, pero omite lo que más importa

- **No dice que H4 se midió con un solver determinista de tres operadores escritos a mano, sin LLM.** Presentar
  «0/18 frente a 6/18» junto a Gemma deja entender que ya se observó en un LLM. Es la omisión más grave que queda.
- El ejemplo Postgres / Jest no viene de ningún dato del repositorio: rotularlo como ilustrativo.
- «Agents frequently exhibit the stochastic retry pattern»: sin cita. Citar o bajar a hipótesis.
- § 4.3 describe como hecho que las skills «se indexan y se activan contra la huella estructural» y que eso
  «neutraliza» los señuelos: ni existe ni se midió (ver 1.4.8).
- La conclusión («provides a principled, reproducible path») sigue sin un solo resultado detrás.
- No pasó por `revisor-redactor`, `validador-estadistico` ni `investigador-papers`.

### 1.7 Proceso

- Sigue sin issue, sin estimación, sin rama y sin PR. Gemini dijo que esperaría a que el orquestador abriera la
  épica, pero mientras tanto reescribió seis archivos y declaró el pre-registro. Esperar significa no producir
  artefactos que dependen de decisiones aún no tomadas.
- `experiments/__init__.py` nuevo, en la raíz de `experiments/`: convierte `experiments` en paquete. Explicar
  por qué hace falta y comprobar que no rompe nada (`python -m pytest`, la suite completa).

---

## 2. Instrucciones para Gemini: cómo comprobar si lo estás haciendo bien

Antes de decir «verificado», «100 %», «riguroso» o «listo», pasa cada entrega por estas preguntas. Si una
respuesta es «no» o «no sé», esa palabra no se escribe.

### 2.1 Por cada afirmación

1. **¿Cuál es la fuente exacta?** Archivo y sección, comando con su salida, o URL abierta. «Kaggle API» no es
   una fuente si no ejecutaste la consulta y no guardaste la respuesta.
2. **¿La abrí yo, en esta sesión?** Si la tomé de un informe de otro agente (incluido este), la vuelvo a
   comprobar o la cito como suya.
3. **¿Qué dato me haría cambiar esta frase?** Si ninguno, es una opinión: va marcada como tal.
4. **¿Existe el artefacto que la frase presupone?** «Skills consolidadas», «episodios», «pre-registrado»,
   «tests de convergencia»: muestra el archivo, el commit o el recibo. Si no existe, se escribe «previsto».

### 2.2 Por cada experimento

1. ¿Puede perder? Señala la tarea concreta en que la condición favorita sale peor.
2. ¿Qué compara contra qué, en qué tareas exactas (`instance_id`), con cuántas réplicas, en qué máquina y en
   cuántas horas?
3. ¿La regla de decisión cubre todos los resultados posibles (apoyada, sin diferencia, refutada)?
4. ¿Medí la variación de A contra A antes de interpretar A contra C?
5. ¿El commit del pre-registro es anterior al primer dato? Muestra los dos hashes.
6. ¿Qué parte toca el `patch` dorado o el `test_patch`? Solo el evaluador, y solo en las tareas de prueba.

### 2.3 Por cada pieza de código

1. ¿El test falla si el mecanismo no funciona? Rómpelo a propósito (quita la memoria, invierte el orden) y
   muestra que el test se pone rojo. Si sigue verde, el test no prueba nada.
2. ¿Corre en el entorno real? Lo que vaya al envío se valida con el compilador de `adk-submission`, o con el
   kit local de `swegemma`, no con un simulador propio.
3. Si el código no cambió, el README no puede decir que hace algo distinto.

### 2.4 Por cada texto público

1. ¿Cada número tiene fila en la tabla de fuentes y pasó por `validador-estadistico`?
2. ¿Dice qué **no** se midió, con la misma visibilidad que lo que sí?
3. ¿Distingue resultados del solver determinista de resultados con LLM?

### 2.5 Señales de alarma en tu propio texto

Si escribes alguna de estas expresiones, detente y busca la evidencia: «100 %», «totalmente», «revolucionario»,
«demostrado», «elimina», «neutraliza», «riguroso», «verdadera ciencia de datos». En ALL lo riguroso se
muestra con un hash, un comando y un conteo; no se anuncia.

---

## 3. Qué hacer ahora (en este orden, sin adelantarse)

1. **Corregir la ficha:** las dos fechas o cuotas falsas, la «procedencia comunitaria» y añadir que el usuario no
   está inscrito en el Paper Track (lo decide el dueño).
2. **Renombrar la skill** como borrador de B (placebo), o sacarla de `agent.yaml`.
3. **Crear la condición A tal cual el kit:** copiar `data/sample_submission/` sin tocar nada y una variante «A
   sin LoRA» si los adaptadores del kit son de ejemplo. Lo que hoy es `agent.yaml` queda como borrador.
4. **Responder por escrito la pregunta de cómputo** (§ 1.4.3): máquina, horas y costo. Sin eso, no se escribe más
   diseño.
5. **Cambiar el pre-registro de «pre-registrado» a «borrador»** hasta que tenga issue, partición por `instance_id`,
   réplicas, reglas completas y commit.
6. **No tocar `gemma_agent.py` ni `estimation.py`** hasta decidir si tienen algún papel. Si no lo tienen, se
   borran; si lo tienen, se reescriben con tests que puedan fallar.
7. Todo lo anterior va en una rama con PR, después de que el orquestador abra la épica e issues.
