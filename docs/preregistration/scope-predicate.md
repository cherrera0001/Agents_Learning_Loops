# Pre-registro · Predicado de alcance por diagnóstico, en tareas escritas a ciegas (#198)

**Registro**: el commit que introduce este archivo, hecho **antes** de que exista ninguna de las tareas del
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

**Diferencia con el agente de #58.** Aquel solo vetaba cuando D no era ambiguo, y con D ambiguo dejaba que la
memoria ordenara. Este predicado **también veta cuando D es ambiguo**: sin diagnóstico que distinga, la
lección no se admite. Es una regla nueva; no se ha ejecutado nunca.

**Límite lógico, declarado antes.** `D` solo lee rasgos del `stderr`. Dos tareas con los mismos rasgos
reciben los mismos candidatos, tengan la causa que tengan: sobre ellas el predicado no puede admitir una
lección y vetar la otra. Solo puede acertar absteniéndose en las dos. El informe cuenta aparte los pares con
rasgos idénticos.

## 4. El banco

- **Tamaño fijo: 16 tareas en 8 pares disjuntos.** Ninguna tarea está en dos pares. En 4 pares las dos tareas
  tienen el **mismo** operador correcto; en los otros 4, operadores **distintos**. No se añaden ni se quitan
  tareas después de escritas.
- **Qué comparte un par:** el síntoma tal como lo contaría quien reporta el fallo (título y contexto del
  enunciado público). El autor no fija ni conoce qué imprime la reproducción: eso sale del defecto.
- **Cada tarea** trae lo mismo que las actuales: el enunciado público con los campos de `benchmark/public/`,
  su test de aceptación público y, sellados, el defecto (archivo, texto antes y después), el operador correcto
  y el par.
- **Quién lo escribe:** un agente que no es el orquestador ni ningún rol del concilio. No lee
  `src/experiments/diagnostic.py`, `failure_memory.py`, `nonlexical_seed.py`, `docs/results/`,
  `docs/preregistration/`, `benchmark/private/` ni los expedientes de los concilios. Su encargo se guarda tal
  cual y se cita en el informe.
- **Dónde vive hasta evaluarse:** fuera de `benchmark/`, para no tocar las huellas que fijan los recibos
  publicados.

Por qué 4 y 4: con cuatro pares de cada tipo, una separación perfecta tiene probabilidad 1/70 si la
asignación fuera al azar. Con menos no hay prueba exacta que baje de 0,05 (tres y tres: 1/20).

## 5. Validez de una tarea

Se comprueba **sin ejecutar ni mirar `D`**, por alguien distinto del autor. Una tarea es válida si se cumplen
las tres:

1. con el defecto aplicado, su test de aceptación falla;
2. aplicando el parche del operador sellado, el test de aceptación y los tests de negocio pasan;
3. aplicando cada uno de los otros dos operadores, no pasan.

Un par es válido si lo son sus dos tareas y el tipo que resulta (mismo operador o distinto) es el que el
autor selló. Los pares inválidos se excluyen y se listan con su motivo. **No se reemplazan.**

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

**Estadístico primario:** número de aciertos sobre pares válidos, con la prueba exacta de Fisher unilateral
sobre la tabla tipo de par × (admitido / no admitido).

| Veredicto | Condición |
|---|---|
| **DISCRIMINA** | Todos los pares válidos son aciertos **y** la prueba exacta da p < 0,05 (exige al menos cuatro pares de un tipo y tres del otro) |
| **NO DEMOSTRADO** | Algún error, con pares suficientes para que la separación perfecta hubiera dado p < 0,05 |
| **INSUFICIENTE** | Quedan menos pares válidos que los necesarios para p < 0,05 aun con separación perfecta |

Con ocho pares válidos, un solo error ya da p = 17/70 = 0,24: el único resultado que pasa es la separación
perfecta. No hay veredicto intermedio ni «casi».

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
la validez; que el autor haya leído algo de la lista de la sección 4.
