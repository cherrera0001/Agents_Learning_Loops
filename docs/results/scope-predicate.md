# Resultados · Predicado de alcance por diagnóstico, en tareas escritas a ciegas (#198)

**Veredicto pre-registrado: INSUFICIENTE.** No se escribió ninguna tarea. El
[pre-registro](../preregistration/scope-predicate.md) exige, para cualquier otro veredicto, al menos cuatro
pares válidos de un tipo y tres del otro; hay cero. El predicado no se ejecutó sobre nada: no hay ningún dato
sobre si discrimina.

El autor del banco se detuvo porque leyó su encargo de un modo más estricto que el pre-registro (ver
*Desviaciones*). Con esa lectura caben tres pares, no ocho. Con la lectura literal del pre-registro quizá
cabían más tareas. Si habrían sido más unidades independientes depende de una definición que el pre-registro
no fijó; la lectura del orquestador es que no (ver *Qué significa y qué no*).

## Qué pasó

1. El pre-registro quedó fijado en el commit `87e6032` del PR #199, tras tres pasadas de un revisor
   independiente, antes de encargar el banco.
2. Según el encargo y el manifiesto (en el expediente sin versionar, ver *Material*), el banco se encargó a
   una ejecución nueva de Codex, sin contexto del concilio, en una carpeta que solo contenía el protocolo,
   `src/experiments/agent.py`, la aplicación y `benchmark/public/`.
3. El autor leyó los tres operadores y la aplicación, contó dónde puede actuar cada operador y **se detuvo
   sin escribir ninguna tarea**, como su encargo le permitía si no existían dieciséis defectos distintos. No
   ejecutó tests ni operadores. Dejó un manifiesto con lo que leyó y lo que ejecutó.

## La cuenta de sitios, comprobada tres veces

El autor contó seis sitios donde algún operador puede aplicar su parche. Lo comprobaron aparte el orquestador
y el revisor del PR, leyendo `BoundedRepairAgent.change` y toda la aplicación; el revisor buscó un séptimo y
no lo hay.

| Operador | Patrón que exige | Sitios en la aplicación |
|---|---|---|
| `validate_optional_identity` | una asignación `… = USERS.get(…)` en un archivo que nombra `Unauthorized` | `app/auth.py`, `app/middleware.py` |
| `normalize_environment` | una asignación `… = os.getenv(…)` en un archivo con una constante `DEFAULT_…` | `app/config.py`, `app/services/reporting.py` |
| `initialize_storage` | un método `start` que usa `self.database.execute`, o una asignación `nombre = Database()` | `app/api.py`, `app/worker.py` |

**Seis sitios, dos por operador.** Según `benchmark/private/`, las nueve tareas actuales ya los ocupan:
EXP-01 a EXP-06 usan uno cada una, y EXP-07, EXP-08 y EXP-09 vuelven sobre los sitios de EXP-04, EXP-05 y
EXP-06 con otro defecto.

## Qué significa y qué no

- **Un sitio admite más de un defecto.** EXP-04 y EXP-07 alteran la misma línea de `app/middleware.py` de dos
  maneras. El número de **defectos** que se pueden escribir no está acotado en seis; el de **sitios**, sí.
- **Tareas en el mismo sitio comparten la reparación.** El operador aplica ahí el mismo parche, sea cual sea
  el defecto. Lectura del orquestador, que el pre-registro no fijó: por eso dos tareas del mismo sitio no
  deberían contarse como unidades independientes.
- **Con seis sitios caben tres pares que no compartan ninguno.** En tres mezclas: los tres de mismo
  operador, los tres de operador distinto, o uno de mismo y dos de distinto. Con tres pares la separación
  perfecta tiene probabilidad de 1/3 o más por azar, así que ninguna de esas mezclas alcanza un veredicto
  distinto de INSUFICIENTE.
- **Sobre el predicado: nada.** Sigue siendo un candidato respaldado por tres tareas cuyas reglas se
  escribieron conociéndolas ([#58](diagnostic-baseline.md)).
- **Sobre los resultados ya publicados: no cambian.** Son conteos exactos sobre esas nueve tareas y así se
  presentaron.

Lectura del orquestador, no medida: un contraste que necesite más unidades independientes que los sitios que
hay no cabe en este solver sin ampliar los operadores o la aplicación.

## Qué no se hizo

- No se comprobó la validez de ninguna tarea (no hay tareas).
- No se ejecutó `diagnose` sobre nada nuevo.
- No se midió el efecto del predicado sobre el primer intento: era la segunda etapa y no se abre.

## Desviaciones

- **El autor aplicó una condición más estricta que la escrita.** El pre-registro pide 16 tareas en 8 pares
  disjuntos (ninguna tarea en dos pares) y no exige un sitio distinto por tarea. El encargo pedía «otro
  archivo u otra línea» **dentro de cada par**. El autor lo exigió entre las dieciséis y concluyó que no
  cabían. Con la lectura literal habría podido repetir sitios entre pares con defectos distintos.
- **No se le pidió reescribir con la lectura literal.** Habría sido cambiar el encargo después de conocer el
  obstáculo, y el banco resultante tendría pares que comparten sitio. La cuenta de 1/70 trata los pares como
  intercambiables; si pares que comparten sitio lo son, el pre-registro no lo decía.
- **El pre-registro no fijó qué hace independientes a dos tareas**, ni comprobó antes cuántos sitios había,
  aunque el código de los operadores estaba a la vista. Es un defecto del diseño, no del autor.

## Material

- Encargo al autor y su manifiesto: en el expediente sin versionar del concilio
  (`.scratch/concilio_cuantitativo/codex/prompt_autor_banco.md` y `autor_banco_manifiesto.md`). Lo que el
  manifiesto dice sobre los sitios está en la tabla de arriba y se puede rehacer con el código.
- Código leído para la comprobación: `src/experiments/agent.py` (`change`) y
  `experiments/software_project/app/`.
