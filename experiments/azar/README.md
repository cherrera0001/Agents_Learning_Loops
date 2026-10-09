# Experimento «azar»

Documento de entrada del experimento. Está escrito para quien no conoce el proyecto.

**Estado al 2026-10-09: no se ha medido nada.** Esta caja contiene la pregunta, las reglas con que se va a
responder y el estado del arte verificado ([`docs/estado_del_arte.md`](docs/estado_del_arte.md)). No hay datos,
ni pruebas estadísticas, ni modelos.

## 1. Qué se quiere saber

¿Se puede identificar, en un sistema físico diseñado para dar resultados aleatorios, alguna estructura que
permita predecir por encima del azar? Por estructura se entiende una dependencia entre sorteos, un sesgo
físico, una deriva por desgaste o una anomalía de operación.

El caso de estudio son los sorteos con máquinas de esferas numeradas. No se presupone que el sistema sea
perfectamente aleatorio ni que tenga un patrón explotable: las dos cosas se examinan con evidencia.

Tres preguntas distintas, que no se mezclan:

1. **Detectar.** ¿El sistema se aparta de lo uniforme e independiente, en una cantidad medible?
2. **Predecir.** ¿Esa desviación mejora el acierto sobre sorteos que el modelo no vio, frente a elegir al
   azar?
3. **Medir el sistema.** ¿El estado físico de la máquina (masa y desgaste de las esferas, vibración,
   temperatura, flujo de aire) informa sobre el resultado más que la historia de resultados?

Detectar un sesgo no es predecir un sorteo. Una bola que sale un poco más de lo debido no dice cuál sale
mañana.

## 2. Qué no es

- **No es un sistema de apuestas.** Es un estudio de auditoría de aleatoriedad. Su resultado más probable es
  negativo, y un resultado negativo bien medido es el entregable.
- **No afirma nada todavía.** Ninguna frase de esta caja dice que algo se puede predecir.
- **No recoge datos de personas** ni datos que no sean públicos.

## 3. Por qué está en este repositorio

El problema es el mismo que el del experimento con Gemma
([`../gemma_developer_agent/`](../gemma_developer_agent/README.md)), a otra escala: distinguir una señal
débil del ruido con pocos datos. Las reglas que aquí son obligatorias desde el primer día (predicción fechada,
potencia calculada antes de correr, prueba exacta, comparaciones múltiples) son las que allí se aprendieron
tarde. Este experimento sirve para formar ese criterio sobre un caso donde la respuesta teórica es conocida:
si los sorteos son independientes y uniformes, ningún modelo supera al azar.

### El brazo que empieza primero: predecir el fallo propio

El dueño fijó el 2026-10-09 la pregunta con que arranca el experimento: **¿podemos predecir el error antes de
que ocurra, y resolver más rápido?** Es la versión de mantenimiento predictivo del mismo problema, aplicada al
sistema que tenemos a mano y del que sí hay datos: el propio proceso de desarrollo de este repositorio.

- **El sistema:** cada issue, con su PR, sus revisiones y su CI.
- **La historia:** los episodios de `learning/episodes/`, que registran cada fallo en la acción que lo causó.
- **La predicción:** antes de empezar un issue o de recibir una revisión, se escribe qué fallo se espera y
  con qué probabilidad.
- **La línea base:** la frecuencia histórica de ese fallo, sin mirar el caso.
- **La lectura:** cuando el issue cierra, se marca qué ocurrió y se compara.

El protocolo y las primeras predicciones fechadas están en
[`preregistro/prediccion_de_fallos.md`](preregistro/prediccion_de_fallos.md). Todavía no se ha leído ninguna.

## 4. Reglas de evidencia

Son condición para que un resultado de esta caja se pueda citar.

1. **Pre-registro antes de mirar.** Hipótesis, pruebas, tamaño de muestra y umbrales se escriben y se fechan
   en `preregistro/` antes de abrir los datos de prueba.
2. **Separación temporal estricta.** Entrenamiento, validación y prueba son tramos sucesivos en el tiempo. El
   tramo de prueba se lee una sola vez.
3. **Evaluación prospectiva.** Una predicción cuenta cuando se registró antes del sorteo que predice.
   Acertar sobre datos históricos no demuestra nada.
4. **Línea base aleatoria.** Todo modelo se compara con elegir al azar sobre los mismos sorteos, con
   intervalo de confianza y prueba de significancia.
5. **Potencia antes de correr.** Antes de cada prueba se calcula qué desviación puede detectar con los datos
   que hay. Si no puede detectar la que importa, se dice y no se corre como si pudiera.
6. **Comparaciones múltiples.** Se cuentan todas las pruebas hechas, también las que no dieron nada, y se
   corrige por ellas.
7. **Sin fuga.** Ningún dato posterior al sorteo entra en lo que lo predice.
8. **Cada afirmación lleva su clase:** evidencia experimental reproducida, evidencia experimental
   preliminar, resultado teórico, hipótesis pendiente o especulación.
9. **Un modelo no es mejor por ser más nuevo.** Se compara contra el método clásico más simple que responda
   la misma pregunta.

## 5. Fases

Cada fase es un issue propio, con su estimación y su pre-registro. Esta caja solo cubre la primera.

| Fase | Qué hace | Estado |
|---|---|---|
| 1. Investigación documental | Estado del arte verificado y mapa de evidencia | En curso: [`docs/estado_del_arte.md`](docs/estado_del_arte.md) |
| 2. Datos históricos | Resultados públicos de sorteos con sus metadatos: máquina, juego de esferas, cambios de equipo | Sin empezar |
| 3. Evaluación estadística | Uniformidad, independencia, autocorrelación, entropía, cambios de régimen | Sin empezar |
| 4. Modelado | Azar, estadística clásica, Transformers y modelos híbridos, sobre el mismo tramo de prueba | Sin empezar |
| 5. Validación física | Banco de laboratorio propio con sensores y un mecanismo de sorteo, para relacionar el estado físico con el resultado | Sin empezar |

## 6. Roles que el staff todavía no tiene

El staff de experimento ([`docs/entorno/agentes.md`](../../docs/entorno/agentes.md)) se armó para un
experimento con un modelo de lenguaje. Para este faltan cinco roles. Aquí solo se nombran; crear sus
definiciones es otro issue.

| Rol | Qué decide | Sin él |
|---|---|---|
| Físico experimental o modelador de sistemas dinámicos | Qué variables físicas importan y hasta qué horizonte se puede predecir | Se mide lo fácil, no lo que gobierna el resultado |
| Metrólogo o ingeniero de instrumentación | Sensores, calibración e incertidumbre de medida | Un «sesgo» puede ser un error del sensor |
| Custodio del pre-registro | Fija hipótesis, pruebas, potencia y correcciones antes de ver datos | El auditor del método revisa al cierre, cuando ya es tarde |
| Curador de datos y procedencia | Históricos con sus metadatos y de dónde salió cada fila | No se puede separar un sesgo de un cambio de máquina |
| Revisor legal y ético | Qué se puede medir y publicar en un tema de juegos de azar regulados | Se recoge o se publica algo que no se debía |

Antes de la fase 2 hace falta al menos el custodio del pre-registro y el revisor legal y ético.

## 7. Estructura

```
experiments/azar/
├── README.md            este documento
├── docs/                estado del arte y, después, protocolos e informes
├── preregistro/         hipótesis, umbrales y predicciones, fechados antes de mirar
└── data/                ignorado por git: datos crudos e instrumentos
```
