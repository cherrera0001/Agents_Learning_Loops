# Pre-registro · Predicado de alcance por diagnóstico, en tareas escritas a ciegas (#198)

**Registro**: el último commit de este archivo en el PR #199 (ver la nota de versión al final), hecho
**antes** de que exista ninguna de las tareas del
banco nuevo y antes de encargar su escritura. Cambiar este documento después de que el banco exista lo
invalida en ese punto, y toda desviación se reporta como tal en el informe de resultados.

**Carácter.** El predicado se congela aquí sin haber visto las tareas donde se prueba: en eso es
confirmatorio. Quien lo congela (el orquestador) **no es ciego**: conoce las nueve tareas actuales, los
resultados publicados en `docs/results/` y el código del diagnóstico. Por eso no escribe el banco. El autor
del banco sí es ciego a la regla (sección 4). El predicado no se eligió entre varios con datos nuevos: es el
único que el concilio dejó nombrado.

Términos según el [glosario](../entorno/glosario.md).

## 1. De dónde sale

El concilio cuantitativo del 2026-10-12 (ocho roles, ocho rondas, auditor del método; expediente sin
versionar) concluyó que el valor de un recuerdo solo es estimable sobre una **clase calculada con lo que se
observa antes de actuar**, y que este repositorio no tiene ninguna validada. Lo medido aquí sobre las señales
disponibles (solver acotado sin modelo de lenguaje, nueve tareas, conteos exactos):

| Señal previa a la acción | Qué se midió | Fuente |
|---|---|---|
| Firma diagnóstica más similitud léxica | Ningún umbral separó las relaciones que ayudan de las que dañan | [H7](../results/failure-transfer.md) |
| Componente de la traza | Habla en 2 tareas de 9; en la única engañosa donde habla elige el señuelo | [H8](../results/h8-nonlexical-seed.md) |
| Candidatos y estado del diagnóstico D | Vetó el señuelo en 2 tareas (12 de 12 ejecuciones); el daño quedó en la tarea donde D fue ambiguo | [#58](../results/diagnostic-baseline.md) |

La tercera es la candidata. La respaldan tres tareas y sus reglas se escribieron conociéndolas: no es una
validación. Este pre-registro fija cómo se valida.

## 2. Pregunta

> En tareas que no existían cuando se fijó, ¿el predicado de la sección 3 admite las lecciones que
> corresponden a la tarea y veta las que no?

No se pregunta aquí si usar el predicado mejora el resultado del solver. Eso es una segunda etapa, que solo se
abre con el veredicto DISCRIMINA y con su propio pre-registro.

## 3. El predicado, congelado

Para una lección que recomienda el operador `o` y una tarea `q`:

    a(o, q) = 1   si y solo si   D(q).status ≠ "ambiguous"   y   o ∈ D(q).candidates
    a(o, q) = 0   en otro caso

- `D` es la función `diagnose` de `src/experiments/diagnostic.py` tal como está en el commit `756e2c2` de
  `main`, aplicada al `stderr` de `test-0` (la reproducción pública de la tarea con el defecto, antes de
  cualquier decisión o parche).
- Reglas `diagnostic-rules/v1`, huella
  `b2e2abf329c0ffd953e5c42f316adec8a003c0eb4224c87c2a20693771b17942`. Si la huella calculada al evaluar
  difiere, no se evalúa.
- `a = 1` se lee «admitida»; `a = 0`, «vetada».

**Diferencia con el solver acotado con D de #58.** Aquel solo vetaba cuando D no era ambiguo, y con D ambiguo
dejaba que la memoria ordenara. Este predicado **también veta cuando D es ambiguo**: sin diagnóstico que
distinga, la lección no se admite. Es una regla nueva; no se ha ejecutado nunca.

**Límite lógico, declarado antes.** `D` solo lee rasgos del `stderr`. Dos tareas con los mismos rasgos
reciben los mismos candidatos, tengan la causa que tengan. En un par de **operador distinto** con rasgos
idénticos, el predicado no puede vetar una lección y admitir la otra: solo acierta si veta las dos. En un par
de **mismo operador** con rasgos idénticos, admitir las dos es un acierto. El informe cuenta aparte los pares
con rasgos idénticos.

## 4. El banco

- **Tamaño fijo: 16 tareas en 8 pares disjuntos.** Ninguna tarea está en dos pares. En 4 pares las dos tareas
  tienen el **mismo** operador correcto; en los otros 4, operadores **distintos**. No se añaden ni se quitan
  tareas después de escritas.
- **Qué comparte un par:** el síntoma tal como lo contaría quien reporta el fallo (título y contexto del
  enunciado público). El autor no fija ni conoce qué imprime la reproducción: eso sale del defecto.
- **Cada tarea** trae lo mismo que las actuales: el enunciado público con los campos de `benchmark/public/`,
  su test de aceptación público y, sellados, el defecto (archivo, texto antes y después), el operador correcto
  y el par.
- **Quién lo escribe:** un agente de entorno que no es el orquestador y que **no trae contexto del concilio**:
  una ejecución nueva de Codex, sin reanudar ninguna sesión anterior. Codex ocupó un rol en el concilio en
  otras ejecuciones, y en una de ellas recibió la lista de campos candidatos; por eso no basta con pedirle que
  no lea. Trabaja en una carpeta aislada que solo contiene `specs/software_learning_protocol.md`,
  `src/experiments/agent.py`, `experiments/software_project/` y `benchmark/public/`. No están ahí
  `src/experiments/diagnostic.py`, `failure_memory.py`, `nonlexical_seed.py`, `docs/results/`,
  `docs/preregistration/`, `benchmark/private/` ni los expedientes de los concilios. Su encargo se guarda tal
  cual, su manifiesto lista lo que leyó y ejecutó, y los dos se citan en el informe.
- **Exposición residual, declarada:** el protocolo que sí lee menciona en una línea que existe una línea base
  de diagnóstico que lee la reproducción pública. No dice sus reglas.
- **Dónde vive hasta evaluarse:** fuera de `benchmark/`, para no tocar las huellas que fijan los recibos
  publicados.

Por qué 4 y 4: si los pares se marcaran «admitido» al azar, acertar los ocho tiene probabilidad 1/70. El
mínimo que deja esa probabilidad bajo 0,05 es cuatro pares de un tipo y tres del otro (1/35); con tres y tres
es 1/20 y no alcanza. Se piden cuatro y cuatro para poder perder un par por invalidez.

## 5. Validez de una tarea

Se comprueba **sin ejecutar ni mirar `D`**, por alguien distinto del autor, con las funciones que ya usa el
harness de experimento en `756e2c2`:

- **«Pasa»** es lo que `execute_tests` de `src/experiments/runner.py` llama éxito sobre el workspace: el test
  de aceptación de la tarea y `tests/test_business.py` se ejecutan sin fallos y corren al menos dos tests.
- **«Aplicar un operador»** es escribir en el workspace la salida de
  `BoundedRepairAgent.change(archivos, operador, semilla)`. No es restaurar el texto `before` del defecto.
- **Semillas:** 1, 4, 5, 6, 7 y 9, las de la campaña de referencia. El archivo que `change` toca puede
  depender de la semilla.

Una tarea es válida si se cumplen las cuatro:

1. sin el defecto, pasa;
2. con el defecto aplicado, no pasa;
3. con el defecto y el operador sellado aplicado, pasa **con las seis semillas**;
4. con el defecto y cada uno de los otros dos operadores, no pasa **con ninguna** de las seis semillas. Que
   `change` no encuentre dónde aplicar (devuelve `None`) cuenta como no pasar.

Casos límite: si `change` lanza una excepción (por ejemplo, porque el defecto deja un archivo que no se puede
analizar), cuenta como no pasar; con el operador sellado eso hace inválida la tarea. En la condición 3 el
operador sellado tiene que modificar el mismo archivo que el defecto: si hace pasar los tests tocando otro, la
tarea es inválida. Si el resultado de 3 o de 4 cambia según la semilla, la tarea es inválida.

Un par es válido si lo son sus dos
tareas y el tipo que resulta (mismo operador o distinto) es el que el autor selló. Los pares inválidos se
excluyen y se listan con su motivo. **No se reemplazan.**

## 6. Unidad, estadístico y veredicto

**Unidad: el par.** En cada par válido se evalúa el predicado en las dos direcciones: la lección de una tarea
(su operador correcto) frente a la otra tarea, y al revés.

| Resultado del par | Condición |
|---|---|
| admitido | `a = 1` en las dos direcciones |
| vetado | `a = 0` en las dos direcciones |
| mixto | una y una |

**Acierto:** un par de mismo operador *admitido*, o un par de operador distinto *vetado*. Un par mixto es un
error, del tipo que sea.

**Estadístico primario: el número de errores sobre los pares válidos.** El veredicto sale de esa cuenta y de
cuántos pares válidos quedan de cada tipo; no de una prueba aplicada después.

| Veredicto | Condición |
|---|---|
| **DISCRIMINA** | Quedan al menos cuatro pares válidos de un tipo y tres del otro, **y** cero errores |
| **NO DEMOSTRADO** | Quedan al menos cuatro de un tipo y tres del otro, **y** uno o más errores |
| **INSUFICIENTE** | Quedan menos pares válidos que cuatro de un tipo y tres del otro, haya o no errores |

Por qué cero errores: la referencia es marcar al azar como «admitidos» tantos pares como pares de mismo
operador hay. Acertarlos todos tiene probabilidad 1/70 con cuatro y cuatro y 1/35 con cuatro y tres. Con un
solo par de mismo operador sin admitir, o uno de operador distinto admitido, ya no baja de 0,05 (con cuatro y
cuatro, la prueba exacta unilateral da 1/14). Un par mixto es un error aunque esa prueba no lo vea. No hay
veredicto intermedio ni «casi».

Como dato descriptivo, y sin efecto en el veredicto, se informa también la prueba exacta de Fisher sobre la
tabla tipo de par × (admitido / no admitido). Esa tabla cuenta un par mixto como «no admitido», así que puede
dar un valor pequeño con un error presente: por eso no decide.

**Se informa siempre, sea cual sea el veredicto:** la tabla par a par; lecciones dañinas admitidas sobre
pares de operador distinto; lecciones útiles vetadas sobre pares de mismo operador; pares mixtos; pares con
rasgos de `stderr` idénticos; el estado de D en cada tarea (`decisive`, `partial`, `ambiguous`). Una regla que
lo vetara todo acertaría los cuatro pares de operador distinto y fallaría los cuatro de mismo operador: por
eso se informan las dos tasas y no una.

## 7. Qué no puede concluir

- Nada sobre el efecto en el primer intento ni en el éxito del solver: aquí no se ejecuta el agente.
- Nada sobre un agente con modelo de lenguaje.
- Nada sobre la similitud léxica como recuperador: el par se define por construcción, no por lo que una
  recuperación elegiría.
- DISCRIMINA sobre ocho pares de una aplicación y tres operadores no es una señal validada en general: es la
  condición para gastar en la segunda etapa.

## 8. Orden y desviaciones

1. Este commit.
2. Encargo al autor ciego; banco completo.
3. Validez (sección 5).
4. Evaluación del predicado e informe en `docs/results/scope-predicate.md`.

Toda desviación se anota en el informe con su motivo. Son desviaciones, entre otras: cambiar el predicado, las
reglas o su huella; añadir, quitar o corregir tareas; cambiar la regla de validez; evaluar `D` antes de cerrar
la validez; que el autor haya leído algo fuera de su carpeta aislada.

**Nota de versión.** Este archivo tuvo tres commits antes de que existiera el banco, y el vinculante es el
último: el primero (`f99c3e6`), una corrección tras la revisión independiente del PR #199 (`6e5bb22`) y un
ajuste tras la segunda revisión (casos límite de la validez y redacción). La corrección cambió la
definición del estadístico (era una
prueba de Fisher que no coincidía con la definición de acierto), cerró la regla de validez (semillas, qué es
aplicar un operador, qué es pasar), precisó quién escribe el banco y corrigió una cifra (17/70 por 1/14). El
predicado de la sección 3 y su huella no cambiaron.
