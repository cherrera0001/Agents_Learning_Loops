# Cuánto se puede creer una diferencia: validez de las tareas y variación de la línea de base en un agente de Gemma 4

**Subtítulo:** Una medición de validez de las tareas públicas, un diseño preregistrado que mide la variación antes de comparar y un resultado negativo previo de un solver sin modelo de lenguaje. No reporta ningún resultado obtenido con el modelo.

Cristóbal Herrera Jara

## Resumen

No hemos ejecutado Gemma 4. Reportamos tres cosas que existen hoy.

Primero, una medición de validez. En el sandbox del notebook de la competición *Gemma 4 Developer Agent*, 71 de las 129 tareas públicas discriminan: sus tests fallan sin parche y pasan con el parche de referencia. En 55 el parche de referencia no pasa sus propios tests, y 36 de esas 55 son del repositorio con más tareas.

Segundo, un diseño preregistrado que mide cuánto cambia el resultado de un agente al repetir la misma ejecución, antes de compararlo con nada. Con las tareas válidas que quedan, la menor diferencia que el diseño puede declarar es de 14 puntos porcentuales.

Tercero, un resultado negativo previo, de un solver determinista con tres operadores escritos a mano: cuando el texto de un issue nombraba el subsistema equivocado, el éxito en el primer intento fue de 0 de 18 con memoria y de 6 de 18 sin ella.

## 1. Introducción

La competición fija un modelo y un harness, y cada participante entrega la configuración de un agente. La nota es la fracción de tareas cuyo parche pasa tests ocultos. Con una nota así, la pregunta práctica de cualquier participante es si el cambio que acaba de hacer mejoró algo.

Esa pregunta tiene dos requisitos que suelen darse por cumplidos. El primero es que las tareas midan lo que dicen medir: una tarea cuyo parche de referencia no pasa sus propios tests no puede distinguir a un agente bueno de uno malo. El segundo es saber cuánto cambia el resultado cuando no se cambia nada: si repetir la misma configuración mueve el resultado tanto como el cambio que se quiere evaluar, la comparación no dice nada.

Este trabajo pregunta:

> En las tareas públicas de la competición, ¿qué diferencia entre dos configuraciones de un agente se puede distinguir de la variación de repetir una sola?

No podemos responderla todavía: no hemos ejecutado el modelo. Lo que sí tenemos es la medición del primer requisito y el diseño, fijado de antemano, para el segundo.

Contribuciones:

1. Una medición de la validez de las 129 tareas públicas en el sandbox del notebook de la competición (§ 3).
2. Un diseño de línea de base preregistrado que mide la variación entre ejecuciones antes de comparar (§ 4).
3. Un resultado negativo sobre recuperación de experiencia por el texto de un issue, medido en un solver determinista sin modelo de lenguaje, que motivó ese diseño (§ 5).

## 2. Trabajos relacionados

**Evaluar con issues reales.** SWE-bench [1] estableció el formato de tests ocultos que pasan o fallan, que esta competición también usa; las tareas de la competición son propias y no son tareas de SWE-bench. Trabajos posteriores encontraron en ese benchmark tareas con fuga de la solución o con tests débiles [2] y parches dados por resueltos que no lo estaban [3]. Nuestra medición del § 3 es de otra clase: no mira si los tests son débiles, sino si la tarea funciona en el entorno donde se la ejecuta.

**Variación entre ejecuciones.** En SWE-bench Verified, con tres modelos y dos andamiajes, la estimación de una sola ejecución varía entre 2,2 y 6,0 puntos según la ejecución elegida, y la desviación supera 1,5 puntos incluso a temperatura 0 [4]. No son cifras de Gemma 4 ni de conjuntos de 40 a 70 tareas. Para comparar dos clasificadores ejecutados una sola vez se ha recomendado el test de McNemar [5]; trasladarlo a agentes con repeticiones es un supuesto nuestro. Fijar las predicciones y el análisis antes de los datos distingue la predicción del análisis posterior [6].

**Experiencia y documentos para el agente.** Varias líneas de trabajo almacenan experiencia para uso posterior: reflexión verbal sobre intentos fallidos [7], conocimientos extraídos entre tareas [8], bibliotecas de habilidades [9] y flujos de trabajo inducidos de trayectorias [10]. La evidencia sobre su efecto es mixta. Un estudio halló que los errores pasados se propagan cuando se reutilizan registros parecidos [11]. En 84 tareas de 11 dominios, las habilidades autogeneradas bajaron el resultado 1,3 puntos de media y las curadas lo subieron 4,5 puntos en ingeniería de software [12]. Los archivos de contexto de repositorio generados por un modelo empeoraron 5 de 8 configuraciones en otro estudio [13]. Ninguno de esos trabajos usa Gemma 4.

Una mejora de 4,5 puntos es menor que la diferencia mínima que nuestro diseño puede declarar (§ 4). Eso condiciona qué preguntas tiene sentido hacer con estas tareas.

## 3. Validez de las tareas públicas en el entorno del notebook

**Qué se midió.** Cada una de las 129 tareas públicas se ejecutó dos veces en el sandbox que usa el notebook oficial de la competición (`subprocess`, sin GPU y sin modelo): una sin parche y otra con el parche de referencia. Una tarea *discrimina* si sus tests fallan sin parche y pasan con él. El parche de referencia se usó solo para esto; no entra en ningún prompt ni documento del agente.

**Tabla 1. Validez por repositorio.**

| Repositorio | Tareas | Discriminan | El parche de referencia falla | Pasan sin parche |
|---|---|---|---|---|
| fastapi | 67 | 29 | 36 | 2 |
| rich | 48 | 42 | 6 | 0 |
| requests | 13 | 0 | 12 | 1 |
| httpx | 1 | 0 | 1 | 0 |
| Total | 129 | 71 | 55 | 3 |

**Lectura.** En este entorno, 58 de las 129 tareas no pueden distinguir un parche correcto de uno incorrecto. Un agente perfecto resolvería como mucho 71. Dos de los cuatro repositorios no aportan ninguna tarea válida.

**El límite de tiempo por comando no lo explica.** Las 71 tareas que discriminan se midieron también con un límite de 60 segundos por comando, el que usa nuestra configuración. Ninguna cambió de veredicto.

**Alcance.** Es una sola medición en un entorno. No sabemos por qué falla el parche de referencia en 55 tareas: no examinamos los fallos. No afirmamos que esas tareas sean inválidas en la evaluación oculta, que usa otros repositorios y cuyo entorno no vemos. Sí afirmamos que quien mida a su agente con las tareas públicas en este sandbox está midiendo sobre 71 tareas, no sobre 129.

## 4. Método: una línea de base preregistrada que mide la variación primero

**Entorno.** El modelo es `gemma-4-31b-it-qat-w4a16-ct`. El participante entrega solo una configuración del agente. Hay un límite de 12 horas para toda la ejecución.

**Pregunta.** ¿Cuánto cambia el resultado de una configuración fija cuando se repite la misma ejecución sobre las mismas tareas? ¿Qué diferencia entre dos configuraciones no puede distinguirse de esa variación?

**Línea de base del agente.** El kit de inicio oficial con cuatro cambios: sin adaptadores, un límite de 8 192 tokens de salida, razonamiento del modelo desactivado y un presupuesto por tarea de 4 minutos, 40 llamadas a herramientas y 100 turnos. Esta definición es una enmienda al preregistro. Se escribió después de leer, el 2026-10-03, publicaciones en el foro de la competición que indicaban que el kit sin modificar fallaba en la puntuación. Para entonces la configuración se había enviado una vez y su puntuación no se conocía. Los valores del presupuesto se eligieron sin una regla previa. Lo declaramos porque es una desviación.

**Partición.** Dejar un repositorio fuera: todas las tareas válidas de un repositorio forman el conjunto de prueba. El preregistro nombra un repositorio preferido y un segundo candidato, exige al menos 40 tareas válidas y deja la elección a la validez medida, no a una decisión posterior. Con la Tabla 1, el preferido queda con 29 tareas válidas y no es apto; el segundo queda con 42 y lo es.

**Repeticiones.** Dos como mínimo, tres si el cómputo lo permite. No se varía nada a propósito. El kit muestrea a una temperatura superior a cero y sin semilla, de modo que lo que se mide es la variación de repetir la misma entrega.

**Reglas de decisión, fijadas de antemano.** Dos repeticiones se comparan tarea por tarea con un test exacto de McNemar. Una tarea es discordante cuando se resuelve en una repetición y no en la otra. Con α = 0,05 el test necesita al menos 6 tareas discordantes, todas en la misma dirección. Con 42 tareas de prueba eso es 6/42, unos 14 puntos porcentuales. Si el desacuerdo medido entre repeticiones es mayor que ese umbral, el valor mayor es el margen. Una comparación confirmatoria entre configuraciones no se ejecuta si ese margen supera 6/24, o si quedan menos de 6 tareas sin resolver. Una línea de base con menos de 6 tareas resueltas no detiene la comparación; solo impide declarar perjuicio.

**Predicciones, escritas antes de cualquier ejecución.** P1: algunas tareas cambiarán de resultado entre repeticiones; cero tareas cambiadas la refuta. P2: en cada repetición, más de la mitad de las tareas sin resolver lo estarán porque el agente agotó tiempo o presupuesto. P3: la tasa de tareas resueltas estará por debajo de la mitad en cada repetición. Un cuarto punto declara que no hacemos predicción sobre el tamaño de la variación.

**Estado al 2026-10-04.** No se ha ejecutado ninguna repetición. Se envió a la competición una entrega exploratoria de esta configuración. Su nota pública no es una tasa de resolución sobre estas tareas, no tiene un recibo por tarea y no se usó para elegir la configuración; por eso no la reportamos como resultado.

**Lo que el diseño ya dice sin datos.** Con 42 tareas válidas, una mejora real de menos de 14 puntos se reportaría como «sin diferencia». La mejora de 4,5 puntos que se ha medido para habilidades curadas [12] queda muy por debajo. Por eso retiramos de este trabajo la comparación de documentos de habilidad contra un texto de relleno que habíamos planeado: con estas tareas y el cómputo disponible no podía responder su pregunta.

## 5. Resultado previo: memoria bajo indicios engañosos

Este resultado es de un sistema distinto y motivó el diseño anterior.

**Solver.** Un programa determinista, sin modelo de lenguaje, que repara un test fallido eligiendo entre tres operadores de edición escritos a mano después de leer el texto del issue.

**Tareas.** Nueve tareas de un proyecto pequeño. Tres aportan las lecciones almacenadas. Seis se puntúan: tres con su redacción original y tres reescritas como señuelos, donde el issue nombra un subsistema que no es el defectuoso.

**Ejecuciones.** Sin memoria, el solver prueba sus tres operadores en un orden por omisión. Cada tarea puntuada se ejecuta bajo los 6 órdenes posibles, lo que da 18 ejecuciones por condición y tipo de tarea. Es una enumeración exhaustiva, no una muestra: sin memoria, el operador correcto queda primero en 2 de los 6 órdenes, por lo que 6 de 18 es fijo por construcción. Una segunda copia determinista de la campaña produjo resultados idénticos, por lo que se reportan 18 ejecuciones y no 36.

**Condiciones.** *Sin memoria*; *Historia*, una lista plana de lecciones pasadas; *Grafo*, un grafo asociativo que propaga activación desde las palabras del issue.

**Tabla 2. Éxito en el primer intento.**

| Redacción de la tarea | Sin memoria | Historia | Grafo |
|---|---|---|---|
| Original | 6/18 | 18/18 | 18/18 |
| Señuelo | 6/18 | 0/18 | 0/18 |

Con redacción original, el éxito en el primer intento fue mayor con memoria. Con redacción señuelo fue de 0 de 18 con cualquiera de las dos memorias, frente a 6 de 18 sin ella. Historia y Grafo dieron el mismo resultado en ambas filas, lo que puede significar que esta prueba no los distingue.

**Con reglas diagnósticas comunes.** En una segunda campaña, las tres condiciones recibieron además tres reglas diagnósticas públicas por tipo de excepción. Con redacción señuelo, el éxito en el primer intento fue de 11 de 18 sin memoria y de 9 de 18 con cualquiera de las dos memorias: la brecha pasó de 6 a 2 de 18. Los datos no separan cuánto de ese cambio viene de una condición sin memoria más fuerte y cuánto de las reglas actuando sobre las condiciones con memoria.

**Alcance.** Son recuentos exactos de un proyecto y de un solver con tres operadores. El resultado con señuelos es en buena parte una consecuencia del montaje: una memoria que recupera por las palabras del issue, frente a issues reescritos para nombrar otro subsistema, recupera la lección equivocada. No permite inferir nada sobre modelos de lenguaje. Lo reportamos porque nos llevó a no dar por buena una mejora sin medir antes contra qué se compara.

## 6. Amenazas a la validez

- **Una medición de validez, un entorno.** La Tabla 1 no se repitió ni se contrastó con otro sandbox.
- **Causa sin examinar.** No sabemos por qué falla el parche de referencia donde falla.
- **Contaminación.** Los repositorios públicos son de código abierto y el modelo puede haber visto su historial. Retener un repositorio no elimina esto.
- **Un solo repositorio de prueba.** Con 42 tareas de un repositorio, lo que se mida no se extiende a otros.
- **Presupuesto en tiempo de reloj.** Un límite de tiempo hace que los resultados dependan de la carga del servidor, que es parte de la variación que se mide y que no se puede separar.
- **Línea de base enmendada.** La configuración se redefinió tras una entrega, con valores elegidos sin regla previa.
- **Un proyecto, un solver.** El § 5 no puede generalizarse.

## 7. Reproducibilidad y uso de datos

Los conteos de la Tabla 1 están en `experiments/gemma_developer_agent/calibracion/validez_notebook_2026-10-04.json`, con el resumen SHA-256 del archivo de resultados por tarea. Ese archivo no se publica: la competición prohíbe redistribuir sus datos, y los identificadores y resultados por tarea no salen del equipo. Quien se una a la competición puede repetir la medición con `scripts/kaggle_validez.py`.

La Tabla 2 se regenera desde agregados con `python -m scripts.paper_figures`, y las tablas regeneradas coinciden byte a byte con las versionadas. El preregistro, sus enmiendas y un guion de compuerta que termina con estado distinto de cero mientras haya parámetros abiertos están en el repositorio público: https://github.com/cherrera0001/Agents_Learning_Loops.

## 8. Conclusión

En el sandbox del notebook de la competición, 71 de las 129 tareas públicas discriminan. Con las 42 del repositorio que queda apto como prueba, el diseño preregistrado solo puede declarar una diferencia de 14 puntos o más, y solo después de medir cuánto varía la línea de base contra sí misma. No hemos medido esa variación: no hemos ejecutado el modelo. Hasta tenerla, una diferencia de pocos puntos entre dos configuraciones sobre estas tareas no se puede distinguir de repetir una sola.

## Referencias

1. Jimenez et al. SWE-bench: Can Language Models Resolve Real-World GitHub Issues? arXiv:2310.06770.
2. Aleithan et al. SWE-Bench+: Enhanced Coding Benchmark for LLMs. arXiv:2410.06992.
3. Wang, Pradel y Liu. Are "Solved Issues" in SWE-bench Really Solved Correctly? arXiv:2503.15223.
4. Bjarnason, Silva y Monperrus. On Randomness in Agentic Evals. arXiv:2602.07150.
5. Dietterich. Approximate Statistical Tests for Comparing Supervised Classification Learning Algorithms. Neural Computation 10(7), 1998. doi:10.1162/089976698300017197.
6. Nosek et al. The preregistration revolution. PNAS 115(11), 2018. doi:10.1073/pnas.1708274114.
7. Shinn et al. Reflexion: Language Agents with Verbal Reinforcement Learning. arXiv:2303.11366.
8. Zhao et al. ExpeL: LLM Agents Are Experiential Learners. arXiv:2308.10144.
9. Wang et al. Voyager: An Open-Ended Embodied Agent with Large Language Models. arXiv:2305.16291.
10. Wang, Mao, Fried y Neubig. Agent Workflow Memory. arXiv:2409.07429.
11. Xiong et al. How Memory Management Impacts LLM Agents: An Empirical Study of Experience-Following Behavior. arXiv:2505.16067.
12. Li et al. SkillsBench, versión v1. arXiv:2602.12670v1.
13. Gloaguen et al. Evaluating AGENTS.md: Are Repository-Level Context Files Helpful for Coding Agents? arXiv:2602.11988.
