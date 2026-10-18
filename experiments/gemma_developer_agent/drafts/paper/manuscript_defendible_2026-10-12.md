# Memoria bajo indicios engañosos: un resultado negativo y un diseño que mide la variación primero

**Subtítulo:** Un resultado medido con un solver determinista sin modelo de lenguaje, y un diseño de prueba preregistrado cuya comparación con Gemma 4 no se ha ejecutado.

**Versión del 2026-10-12.** Sustituye a la del 2026-10-04 en tres puntos: Gemma 4 ya se ejecutó en sesiones exploratorias (§ 4.1), la línea de base del § 4 dejó de describir lo que el arnés hace (§ 4.1) y la lectura del placebo del § 3 estaba al revés. Borrador sin publicar; los números del § 4.1 no han pasado por el validador estadístico ni por el auditor de datos.

Cristóbal Herrera Jara

## Resumen

Reportamos un resultado negativo de un solver de reparación determinista y un diseño para probar, con Gemma 4, si documentos de habilidad ayudan a un agente de codificación. Gemma 4 se ha ejecutado solo en sesiones exploratorias y en envíos a la competición (§ 4.1); la comparación del § 5 no se ha ejecutado, y ningún resultado de este texto dice que un documento ayude o perjudique a Gemma 4.

El solver tiene tres operadores de edición escritos a mano y ningún modelo de lenguaje. Cuando el texto de un issue nombraba el subsistema equivocado, el éxito en el primer intento fue de 0 de 18 con memoria y de 6 de 18 sin ella. Una historia plana y un grafo asociativo produjeron resultados idénticos.

El diseño, para la competición Gemma 4 Developer Agent, mide cuánto varía un agente de línea de base al repetir la misma ejecución antes de compararlo con cualquier otra cosa. Retiene un repositorio completo para pruebas y fija sus reglas de decisión antes de ver los datos. Una comparación entre documentos de habilidad y un texto de relleno de la misma longitud está escrita y no se ha ejecutado.

## 1. Introducción

Los agentes de codificación suelen reparar una tarea fallida editando y volviendo a ejecutar hasta que algo pasa. Incorporar al agente documentos derivados de ejecuciones anteriores, con la idea de reducir errores repetidos, es una práctica habitual en estos sistemas. La competición que enmarca este trabajo dificulta esa práctica en su forma habitual: el harness ejecuta cada tarea en un entorno aislado y ningún estado sobrevive de una tarea a la siguiente. Lo que el agente "recuerda" debe estar escrito antes de la evaluación, como archivos estáticos incluidos en la entrega.

Bajo esa restricción, la pregunta se estrecha:

> ¿Los documentos estáticos derivados de ejecuciones anteriores del agente ayudan a resolver tareas en un repositorio que no ha visto, comparados con el agente sin modificar y con un texto de relleno de la misma longitud?

Esta es una pregunta sobre documentos. Una respuesta positiva mostraría que un archivo ayudó; no mostraría que el agente adquirió una habilidad.

Contribuciones:

1. Un resultado negativo sobre recuperación de experiencia por el texto de un issue, medido en un solver determinista (§ 3).
2. Un diseño de línea de base preregistrado que mide la variación entre ejecuciones primero (§ 4).
3. Un control de texto de relleno para documentos de habilidad, propuesto pero no ejecutado (§ 5).

## 2. Trabajos relacionados

Los benchmarks de reparación a nivel de repositorio, como SWE-bench [1], establecieron el formato de tests ocultos que pasan o fallan que esta competición también usa. Las tareas de la competición son propias y no son tareas de SWE-bench. Los diseños de agente para este entorno van desde agentes que usan herramientas con una interfaz diseñada a propósito [2] hasta pipelines sin ciclo de agente [3].

Varias líneas de trabajo almacenan experiencia para uso posterior: reflexión verbal sobre intentos fallidos [4], conocimientos extraídos entre tareas [5], bibliotecas de habilidades reutilizables [6], flujos de trabajo inducidos de trayectorias pasadas [7] y gestión de memoria por niveles [8]. Se ha propuesto recuperación sobre grafos para casos en que la consulta y el elemento almacenado comparten poco texto de superficie [9], y los grafos de repositorio se han usado para guiar la navegación por código [10].

Citamos estos trabajos para situar el mecanismo. Nuestro propio resultado medido es desfavorable a la memoria bajo indicios engañosos. Ninguno de los trabajos citados, hasta donde los leímos, incluye un control que separe el texto útil del texto adicional; la condición de relleno del § 5 es nuestro intento de hacerlo.

## 3. Resultado previo: memoria bajo indicios engañosos

**Solver.** Un programa determinista, sin modelo de lenguaje, que repara un test fallido eligiendo entre tres operadores de edición escritos a mano después de leer el texto del issue.

**Tareas.** Nueve tareas de un proyecto pequeño. Tres aportan las lecciones almacenadas. Seis se puntúan: tres con su redacción original y tres reescritas como señuelos, donde el issue nombra un subsistema que no es el defectuoso.

**Ejecuciones.** Sin memoria, el solver prueba sus tres operadores en un orden por omisión. Cada tarea puntuada se ejecuta bajo los 6 órdenes posibles, lo que da 18 ejecuciones por condición y tipo de tarea. Estas ejecuciones son una enumeración exhaustiva, no una muestra: sin memoria, el operador correcto queda primero en 2 de los 6 órdenes, por lo que 6 de 18 es fijo por construcción. Una segunda copia determinista de la campaña produjo resultados idénticos, por lo que se reportan 18 ejecuciones y no 36.

**Condiciones.** *Sin memoria*; *Historia*, una lista plana de lecciones pasadas; *Grafo*, un grafo asociativo que propaga activación desde las palabras del issue.

**Tabla 1. Éxito en el primer intento.**

| Redacción de la tarea | Sin memoria | Historia | Grafo |
|---|---|---|---|
| Original | 6/18 | 18/18 | 18/18 |
| Señuelo | 6/18 | 0/18 | 0/18 |

Con redacción original, el éxito en el primer intento fue mayor con memoria, y la media de intentos fue 1,0 frente a 2,0 sin memoria. Con redacción señuelo, el éxito en el primer intento fue de 0 de 18 con cualquiera de las dos memorias, frente a 6 de 18 sin ella, y la media de intentos fue 2,5 frente a 2,0. Historia y Grafo produjeron el mismo resultado en ambas filas.

**Con reglas diagnósticas comunes.** En una segunda campaña, las tres condiciones recibieron además tres reglas diagnósticas públicas por tipo de excepción (Tabla 2). Con redacción señuelo, el éxito en el primer intento fue de 11 de 18 sin memoria y de 9 de 18 con cualquiera de las dos memorias, por lo que la brecha pasó de 6 a 2 de 18. Los datos no permiten separar cuánto de ese cambio proviene de una condición sin memoria más fuerte y cuánto de las reglas actuando sobre las condiciones con memoria.

**Tabla 2. Éxito en el primer intento con reglas diagnósticas comunes.**

| Redacción de la tarea | Sin memoria | Historia | Grafo |
|---|---|---|---|
| Original | 12/18 | 18/18 | 18/18 |
| Señuelo | 11/18 | 9/18 | 9/18 |

**Lecciones de fallos.** En una tercera campaña, lecciones extraídas de intentos fallidos se inyectaron bajo un umbral de similitud, a cuatro valores de umbral, en tareas con redacción original. Desde la condición sin lecciones, las lecciones reales ayudaron a 3 de 18 ejecuciones en tres de los cuatro umbrales, no ayudaron a ninguna en el más estricto y perjudicaron a 3 de 18 en uno. Desde la condición que ya tenía lecciones, las lecciones reales perjudicaron a 3 de 18 en un umbral, y una lección placebo perjudicó a 3 de 18 en tres de los cuatro. La lectura por contenido, según el análisis versionado (`docs/results/failure-transfer.md`, H7c): desde la condición sin lecciones, la lección real ayudó a 3 de 18 en dos umbrales donde el placebo no cambió nada; desde la condición que ya tenía lecciones, el placebo perjudicó a 3 de 18 en dos umbrales donde la real no cambió nada. En esos cuatro casos el contenido importó. En el umbral restante (0,1), real y placebo fueron indistinguibles en ambas condiciones. La versión del 2026-10-04 de este texto decía que el perjuicio no podía atribuirse al contenido; esa frase leía mal la tabla.

**Alcance.** Estos son recuentos exactos de un proyecto y de un solver con tres operadores. No permiten inferir nada sobre modelos de lenguaje ni sobre repositorios reales. Los reportamos porque cambiaron lo que estábamos dispuestos a asumir.

## 4. Método: una línea de base preregistrada que mide la variación primero

**Entorno.** La competición fija un modelo, `gemma-4-31b-it-qat-w4a16-ct`, y un harness. El participante entrega solo una configuración del agente. La puntuación es la fracción de tareas cuyo parche pasa los tests ocultos, en repositorios privados, con un límite de 12 horas para toda la ejecución. Hay 129 tareas públicas de cuatro repositorios de código abierto (67, 48, 13 y 1).

**Pregunta.** ¿Cuánto cambia el resultado de una configuración fija cuando se repite la misma ejecución sobre las mismas tareas? ¿Qué diferencia entre dos configuraciones no puede distinguirse de esa variación?

**Línea de base del agente.** El kit de inicio oficial con cuatro cambios: sin adaptadores, un límite de 8 192 tokens de salida, razonamiento del modelo desactivado (`include_thoughts: false`; enmienda 3), y un presupuesto por tarea de 4 minutos, 40 llamadas a herramientas y 100 turnos. Esta definición es una enmienda al preregistro. Se escribió después de leer, el 2026-10-03, publicaciones en el foro de la competición que indicaban que el kit sin modificar fallaba en la puntuación. Para entonces, la configuración se había enviado una vez y su puntuación no se conocía. Los valores del presupuesto se eligieron sin una regla previa. Lo declaramos porque es una desviación.

**Partición.** Dejar un repositorio fuera: todas las tareas válidas de un repositorio forman el conjunto de prueba y el resto forma el conjunto de entrenamiento. El repositorio preferido para retener tiene 67 tareas; la segunda opción tiene 48. La evaluación oculta usa repositorios que el agente no ha visto, por lo que una división dentro de un repositorio mediría algo distinto.

**Repeticiones.** Dos como mínimo, tres si el cómputo lo permite. No se varía nada a propósito. El kit muestrea a una temperatura superior a cero sin semilla, por lo que lo que se mide es la variación de repetir la misma entrega.

**Reglas de decisión, fijadas de antemano.** Dos repeticiones se comparan tarea por tarea con un test exacto de McNemar. Una tarea es discordante cuando se resuelve en una repetición y no en la otra. Con α = 0,05 el test necesita al menos 6 tareas discordantes, todas en la misma dirección. Con 67 tareas de prueba eso es 6/67, aproximadamente 9 puntos porcentuales; con 48 es 12,5. Si el desacuerdo medido entre repeticiones es mayor que ese umbral, el valor mayor es el margen. La comparación confirmatoria del § 5 no se ejecuta si ese margen supera 6/24, o si quedan menos de 6 tareas sin resolver. Una línea de base con menos de 6 tareas resueltas no detiene la comparación; solo impide declarar perjuicio.

**Predicciones, escritas antes de cualquier ejecución.** P1: algunas tareas cambiarán de resultado entre repeticiones; cero tareas cambiadas la refuta. P2: en cada repetición, más de la mitad de las tareas sin resolver lo estarán porque el agente agotó tiempo o presupuesto. P3: la tasa de tareas resueltas estará por debajo de la mitad en cada repetición. Un cuarto punto declara que no hacemos predicción sobre el tamaño de la variación.

**Estado al 2026-10-04.** No se había ejecutado ninguna repetición. Se envió a la competición una entrega exploratoria de esta configuración (referencia 56808559). Su nota pública, 0,06, se leyó el 2026-10-04 después de congelar la configuración. Esa nota no es una tasa de resolución: no hay recibo por tarea detrás de ella y no se usó para elegir la configuración.

### 4.1 Estado al 2026-10-12: sesiones exploratorias y un cambio del arnés

Lo que sigue es exploratorio. No sigue la partición del § 4 (las sesiones usan un sorteo de tareas públicas, no un repositorio retenido) y no se usa para ninguna comparación confirmatoria. Esta versión no comprobó de nuevo el estado de las repeticiones preregistradas.

**Envíos.** Cuatro envíos tienen nota pública (Tabla 3). El mismo archivo recibió notas distintas al reenviarlo, en los dos kits. La nota no trae recibo por tarea.

**Tabla 3. Notas públicas, leídas por la API de la competición el 2026-10-12.**

| Referencia | Enviado | Kit | Nota pública |
|---|---|---|---|
| 56808559 | 2026-10-03 | Línea de base del § 4 (`d8a3e1d3…`) | 0,06 |
| 56830336 | 2026-10-04 | El mismo archivo | 0,05 |
| 56895202 | 2026-10-07 | Razonamiento devuelto, 60 llamadas, 4,5 min (`65a02160…`) | 0,08 |
| 56916129 | 2026-10-07 | El mismo archivo | 0,13 |
| 57098570 | 2026-10-12 | El mismo archivo | sin nota al cierre de esta versión |

Los dos kits difieren en tres cosas a la vez (razonamiento, llamadas y minutos), por lo que la diferencia entre sus notas no puede atribuirse a ninguna. Con dos lecturas por kit tampoco puede distinguirse de la variación entre reenvíos.

**El arnés cambió durante el estudio.** El 2026-10-09 el organizador publicó versiones nuevas de sus paquetes (`swegemma` 0.2.7 a 0.2.11; `adk_submission` 0.2.12 a 0.2.13). Con la versión nueva, un presupuesto de razonamiento mayor que cero activa el razonamiento del modelo aunque `include_thoughts` sea `false`; el organizador dijo en el foro que es intencional. Dos consecuencias para este diseño:

1. La línea de base del § 4 se definió con «razonamiento del modelo desactivado (`include_thoughts: false`)». Con el arnés nuevo, ese mismo archivo razona con el pensamiento oculto. Lo medimos en una prueba local de las peticiones y en una sesión con el modelo real. Para apagar el razonamiento hace falta `thinking_budget: 0`. La definición del § 4 necesita una enmienda nueva antes de ejecutar cualquier repetición.
2. Las sesiones y las notas anteriores al cambio no sirven de referencia para las posteriores. Las notas 0,05 y 0,06 son de antes; no sabemos con qué versión se puntuaron 0,08 y 0,13. El 2026-10-12 el organizador escribió que el puntuador usa «el mismo sandbox pero ruedas distintas» de las públicas, sin decir cuáles.

**Una sesión con el arnés nuevo.** El 2026-10-12, el archivo de la línea de base corrió 12 tareas públicas bajo el arnés nuevo (por tanto, razonando). Resolvió 4 de 12 según los tests de nuestro arnés local (intervalo exacto del 95 %: 10 a 65 %). Seis de las 12 se cortaron por el tope de 4 minutos; la media fue de 212 s por tarea, censurada por ese tope. El 97 % del tiempo de reloj fue generación del modelo. Doce tareas sin repetición no estiman una tasa ni una variación.

**En curso.** La misma sesión con `thinking_budget: 0` se subió el 2026-10-12 a las 13:53 UTC y estaba en ejecución, sin resultado, al cierre de esta versión. Su regla de lectura se escribió antes: mide segundos y clases de fin sin razonar, no acierto. El plan posterior (60 tareas sin razonar, su repetición para medir la discordancia entre pasadas iguales, y 60 pares razonar frente a no razonar) fija que solo una diferencia de 16,5 puntos o más cambia de kit; por debajo se anota como exploratoria.

**Predicciones del § 4 frente a esta sesión.** Con una sola sesión de 12 tareas, y fuera de la partición preregistrada, no se confirma ni se refuta ninguna. Como descripción: 8 de 12 quedaron sin resolver, todas por tiempo o por llamadas agotadas (P2 pedía más de la mitad), y la tasa quedó por debajo de la mitad (P3). P1 necesita una repetición.

## 5. Comparación propuesta (sin preregistrar)

Lo que sigue es una propuesta. Su estimador y su predicción no están fijados, y nada de lo que contiene se ha ejecutado. Sus condiciones se etiquetan de A a D y no guardan relación con las condiciones del solver del § 3.

| Condición | Qué puede leer el agente | Propósito |
|---|---|---|
| A | La línea de base del agente del § 4 | Referencia y variación |
| B | A más un texto de relleno tan largo como las habilidades de C | Separa el texto adicional del texto útil |
| C | A más documentos de habilidad consolidados a partir de las ejecuciones del agente en los repositorios de entrenamiento | La propuesta bajo prueba |
| D | C más una instrucción para usar las herramientas del grafo de código | Separa tener las habilidades de que se le indique usarlas; solo se ejecuta si el cómputo lo permite |

Tres definiciones deben cerrarse antes de poder preregistrar esto: qué contiene el relleno (el texto neutro y las heurísticas humanas son controles distintos), qué cuenta como confirmación independiente de un patrón, y quién escribe los documentos de habilidad. El paso de consolidación que produciría C aún no existe.

**Un límite que ya conocemos.** Con 67 tareas de prueba, solo puede declararse una diferencia de aproximadamente 9 puntos, el mismo umbral que en el § 4. Un beneficio real menor que ese umbral se reportaría como «sin diferencia».

**Qué se retiró.** El plan original preguntaba si un grafo de memoria asociativa mejora a un agente con Gemma 4. Retiramos esa pregunta. Ninguna de las condiciones anteriores ejecuta un grafo en el momento de la evaluación; el modelo lee un archivo fijo. Un estudio preregistrado separado, al que llamamos H8, pregunta solo en el solver determinista si sembrar la recuperación desde los archivos tocados por una traza de reproducción pública evita el señuelo. Su predicción escrita es que no lo hará. No se ha ejecutado, y no dice nada sobre Gemma 4.

## 6. Amenazas a la validez

- **Un proyecto, un solver.** El § 3 no puede generalizarse.
- **Contaminación.** Los repositorios públicos son de código abierto, y el modelo puede haber visto su historial. Retener un repositorio no elimina esto.
- **Conjunto de prueba confundido.** El repositorio, la fecha de la tarea y el tamaño de la tarea cambian juntos entre entrenamiento y prueba.
- **Presupuesto en tiempo de reloj.** Un límite de tiempo hace que los resultados dependan de la carga del servidor, que es parte de la variación que medimos y que no podemos separar.
- **Los resultados locales pueden no predecir la puntuación oculta.** Publicaciones del foro del 2026-10-03 indicaron que el mismo archivo recibió puntuaciones distintas al enviarlo de nuevo.
- **Línea de base enmendada.** La línea de base del agente se redefinió tras una entrega, con valores elegidos sin regla previa.
- **El instrumento cambió a mitad del estudio.** El arnés se actualizó el 2026-10-09 y cambió la conducta de un archivo que no tocamos (§ 4.1). Puede volver a cambiar; cada sesión anota las versiones instaladas, y las sesiones de versiones distintas no se juntan.
- **El puntuador no usa los mismos paquetes que el arnés público.** Lo dijo el organizador el 2026-10-12. Un resultado local, aunque fuera estable, mide otro instrumento.
- **Tope de tiempo como censura.** En la sesión del § 4.1 la mitad de las tareas llegó al tope de 4 minutos; los segundos por tarea y la tasa de resolución dependen de ese tope.

## 7. Reproducibilidad y uso de datos

Las tablas del § 3 se regeneran desde agregados con `python -m scripts.paper_figures`, y las tablas regeneradas coinciden byte a byte con las versionadas. El preregistro, sus enmiendas y un script de puerta que termina con estado no cero mientras los parámetros estén abiertos están en el repositorio público: https://github.com/cherrera0001/Agents_Learning_Loops.

La competición prohíbe redistribuir sus datos. Un script de comprobación no encontró ningún archivo versionado bajo el directorio del experimento que coincida con los archivos de la competición por nombre o por hash. El archivo de tareas no está versionado, por lo que los agregados del lado de la competición no pueden reconstruirse sin unirse a la competición.

## 8. Conclusión

En un entorno determinista pequeño, observamos que la memoria recuperada por el texto de un issue no produjo éxito en el primer intento cuando la redacción era engañosa, que un grafo no fue mejor que una historia plana, y que la brecha fue menor cuando todas las condiciones compartían reglas diagnósticas. No sabemos si algo de esto se mantiene para un modelo de lenguaje: las sesiones con Gemma 4 hechas hasta el 2026-10-12 son exploratorias y ninguna compara una condición con memoria. Mostraron, eso sí, que el instrumento puede cambiar bajo el diseño (§ 4.1). El diseño del § 4 existe para que, cuando se ejecute el modelo, una diferencia se declare solo si supera la variación de la línea de base contra sí misma.

## Referencias

1. Jimenez et al. SWE-bench: Can Language Models Resolve Real-World GitHub Issues? arXiv:2310.06770.
2. Yang et al. SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering. arXiv:2405.15793.
3. Xia et al. Agentless: Demystifying LLM-based Software Engineering Agents. arXiv:2407.01489.
4. Shinn et al. Reflexion: Language Agents with Verbal Reinforcement Learning. arXiv:2303.11366.
5. Zhao et al. ExpeL: LLM Agents Are Experiential Learners. arXiv:2308.10144.
6. Wang et al. Voyager: An Open-Ended Embodied Agent with Large Language Models. arXiv:2305.16291.
7. Wang et al. Agent Workflow Memory. arXiv:2409.07429.
8. Packer et al. MemGPT: Towards LLMs as Operating Systems. arXiv:2310.08560.
9. Jiménez Gutiérrez et al. HippoRAG: Neurobiologically Inspired Long-Term Memory for Large Language Models. arXiv:2405.14831.
10. Ouyang et al. RepoGraph: Enhancing AI Software Engineering with Repository-level Code Graph. arXiv:2410.14684.
