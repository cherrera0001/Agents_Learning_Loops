# Hipótesis Zorzal

Agents Learning Loops (ALL) aplicado a un modelo pequeño. Estado: **hipótesis registrada, sin resultados**.
Aprobada por el dueño el 2026-10-04. Los umbrales se congelaron antes de leer ninguna corrida.

## La idea

Un zorzal no gana por fuerza. Camina, se detiene, ladea la cabeza y escucha lo que hay bajo la tierra. Pasa
casi todo el tiempo quieto. Cuando ataca, lo hace una vez.

Gemma 4 es un modelo pequeño con un presupuesto fijo por tarea. No puede ganar por fuerza.

> **Un modelo pequeño resuelve más tareas cuando escucha antes de actuar y actúa una sola vez, que cuando usa
> el mismo presupuesto en actuar muchas veces.**

Esta es la parte de ALL que el arnés de la competición permite expresar. Cada tarea corre aislada, así que no
hay memoria entre tareas; pero aprender de un fallo dentro de la misma tarea no la necesita.

## Los cinco rasgos

Se miden en la traza de una tarea, solo con conteos. Los valores están en [`umbrales.json`](umbrales.json).

| Rasgo | En el agente | Se cumple si |
|---|---|---|
| **Busca** | Recorre el código antes de tocarlo | Hay al menos una llamada antes de la primera edición |
| **Oye** | Toma la señal de la ejecución, no solo las palabras del problema | Ejecutó al menos una prueba |
| **Observa** | Nota lo que ya falló | Ninguna llamada repite una que ya había fallado |
| **Espera** | No gasta el presupuesto en moverse | Terminó al menos 2 llamadas por debajo del límite |
| **Acierta** | Un golpe pequeño y comprobado | Entre 1 y 3 ediciones y a lo más una entrega |

Una sesión tiene **perfil zorzal** si cumple los cinco.

**De dónde sale el 3.** De las soluciones de referencia de las 71 tareas válidas: la mediana es de 2 bloques de
cambio y el percentil 75 es 3. En 54 de las 71 bastan 3 o menos. En las otras 17 este rasgo es más difícil de
cumplir.

**Una medida incompleta.** «Oye» cuenta hoy solo los comandos que nombran pytest. No cuenta una comprobación
escrita en línea ni guarda si ocurrió antes de entregar. Mientras siga así, el perfil que decide deja «oye»
fuera y la lectura lo dice. Corregir la medida es una versión nueva de los umbrales.

## Las hipótesis y lo que las refuta

| Hipótesis | Qué afirma | La refuta | No cuenta si |
|---|---|---|---|
| **H-Z1** | Las sesiones con perfil zorzal se resuelven con más frecuencia | Una frecuencia igual o menor | Hay menos de 5 sesiones en alguno de los dos grupos |
| **H-Z2** | Una configuración que induce el perfil resuelve más que la base y más que un texto de relleno del mismo largo | Una ventaja menor que la exigida, frente a la base o frente al relleno | La configuración no aumentó en al menos 2 las sesiones con perfil, o falta el relleno |
| **H-Z3** | Con esa configuración no aumentan las tareas cortadas por tiempo | Más tareas cortadas que en la base | — |
| **H-O** | Operar como zorzal cuesta menos: una subida a Kaggle por resultado útil y ninguna corrida perdida por una causa visible en local | Más de una subida por resultado útil, o un fallo visible en local, entre el 2026-10-05 y el 2026-10-11 | No hubo subidas en la ventana |

**Ventaja exigida:** el ruido más una tarea, y nunca menos de 2. El ruido es el número de tareas que cambian de
resultado entre dos pasadas iguales de la base.

H-Z1 es una observación y no una causa: una tarea fácil produce una sesión limpia. H-Z2 es la hipótesis del
artículo.

## Lo que hoy va en contra

En el resultado H8 de ALL, sin modelo de lenguaje, la señal de la ejecución calló en 7 de 9 tareas y eligió mal
en la única tarea engañosa donde habló. Escuchar no garantiza elegir bien.

## Después de la revisión independiente (2026-10-05)

Los umbrales de la versión 1 no se han tocado. Lo que sigue es lo que una versión 2 tendría que recoger; espera
la aprobación del dueño.

**El nombre.** La propuesta se llama **ZorzALL**.

**Tres revisores intentaron refutarla.** Veredicto: solo con cambios.

| Lo que decía la versión 1 | Qué encontró la revisión |
|---|---|
| Ventaja exigida: el ruido más una tarea | Mal planteada: se vuelve más exigente con más tareas. Con una mejora real de 10 puntos y 43 tareas daría «apoyada» entre el 1 % y el 13 % de las veces |
| H-Z1 | En parte una tautología: sin relación real saldría «apoyada» entre el 48 % y el 92 % de las veces. Pasa a ser exploratoria |
| H-O | No es una hipótesis: es un indicador de operación |
| «Busca» y «espera» como rasgos que deciden | Circulares: una etapa sin herramienta de edición cumple «busca» por construcción, y «espera» se mide contra un tope distinto en cada brazo |
| Una etapa sin herramienta de edición no puede escribir | Falso: puede hacerlo con un comando de consola |

**Lo que queda como contraste.** Uno solo: el arnés base con un texto de relleno contra el arnés ZorzALL, con
los mismos topes, con una prueba de permutación por tarea y tres veredictos (apoyada, refutada, no
concluyente). Con 103 tareas y dos pasadas por brazo detectaría una mejora de 10 puntos ocho de cada diez
veces. Cuesta unas 17 horas de cuota.

**La definición corregida, en discusión.** Escucha, resuelve, comprueba. Sustituye «acierta una vez» por
«resuelve», las veces que haga falta. Rasgos: busca, oye, ubica, resuelve, comprueba.

**Lo que dijeron los primeros datos** (exploratorios; agregados en
[`calibracion/medicion_exploratoria_2026-10-05.json`](../calibracion/medicion_exploratoria_2026-10-05.json),
que llega con el PR #141):

- Las tareas resueltas tienen el perfil esperado: de 5 a 8 llamadas, sin repeticiones, una edición.
- Pero la causa principal de no resolver no está en la conducta del agente. Está en las tareas cuyo enunciado
  es un título y una referencia que el agente no puede abrir: ninguna configuración resolvió ninguna, en 66
  pasadas.
- En esas tareas, buscar las palabras del título como texto deja el archivo correcto en primer lugar en 6 de
  9. Ubicar no es el obstáculo; falta saber qué cambiar.

**Lo que eso le pide a la hipótesis.** «Oír» no puede significar solo ejecutar las pruebas. En un tercio de las
tareas públicas no hay descripción del defecto, y el agente tiene que deducirlo del código que rodea las
palabras del título. Ese caso todavía no está cubierto.

## Historias y criterios de aceptación

Cada criterio es una prueba de [`tests/unit/test_zorzal_perfil.py`](../../../tests/unit/test_zorzal_perfil.py).
El nombre de la prueba empieza por el identificador de la historia.

### Historias de usuario

| Id | Como… | quiero… | para… | Se acepta cuando |
|---|---|---|---|---|
| HU-1 | investigador | clasificar una sesión con los cinco rasgos | saber si el agente se comportó como zorzal | Una sesión que cumple los cinco tiene perfil; cada rasgo falla justo al cruzar su umbral |
| HU-2 | investigador | leer cada hipótesis con una regla fijada de antemano | no elegir la lectura después de ver el resultado | H-Z1, H-Z2 y H-Z3 devuelven apoyada, refutada o no evaluable según los casos de prueba; la ventaja exigida descuenta el ruido |
| HU-3 | operador | un informe antes de cada acción: qué oí, qué vi, qué falta por oír y la única acción | actuar una sola vez y con evidencia | El informe tiene sus cuatro partes, nombra sus fuentes y propone una acción o ninguna |
| HU-4 | dueño | una bitácora de subidas a Kaggle | medir H-O sobre las propias sesiones | La regla lee la bitácora, cuenta solo la ventana y refuta ante una resubida o un fallo visible en local |

### Historias de uso de datos

| Id | Dato | Uso permitido | Se acepta cuando |
|---|---|---|---|
| HD-1 | Traza de una tarea | Solo conteos: nombres de herramientas, tipos de error y posiciones | Un registro con un campo desconocido, con texto o sin traza se rechaza |
| HD-2 | Lista de tareas válidas | Decide qué sesiones entran en una lectura | Las sesiones de tareas no válidas quedan fuera |
| HD-3 | Umbrales | Se congelan antes de leer resultados; cambiarlos es una enmienda | Una lectura anterior al congelado se rechaza; la huella del archivo no cambió; el umbral de ediciones declara su origen |
| HD-4 | Medida de «oye» | Se usa solo como dato secundario mientras sea incompleta | El perfil que decide la deja fuera y la lectura lo declara |
| HD-5 | Pasadas de una comparación | Toda comparación lleva dos pasadas de la base y el límite de cada condición | Sin eso, la comparación se rechaza |

Las soluciones de referencia se usaron una sola vez y en agregado, para fijar el umbral de ediciones. No entran
en ninguna instrucción del agente.

## Uso

```bash
python -m scripts.zorzal_perfil evaluar <resultados.json> --validas <ids.json> --leido-en <fecha ISO> \
    --limite A=40 --limite R=60 --base A --candidata R
python -m scripts.zorzal_perfil informe <informe.md>
python -m scripts.zorzal_perfil operacion experiments/gemma_developer_agent/zorzal/bitacora_operacion.json
```

El archivo de resultados y la lista de tareas válidas llevan identificadores de tareas y no se versionan.
