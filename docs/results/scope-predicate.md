# Resultados · Predicado de alcance por diagnóstico, en tareas escritas a ciegas (#198)

**Veredicto pre-registrado: INSUFICIENTE.** El banco no se pudo escribir. El [pre-registro](../preregistration/scope-predicate.md)
pedía 16 tareas en 8 pares disjuntos y exigía, para cualquier otro veredicto, al menos cuatro pares válidos
de un tipo y tres del otro. La aplicación y los tres operadores del solver acotado admiten como máximo
**tres** pares disjuntos. El predicado no se ejecutó sobre ninguna tarea: no hay ningún dato sobre si
discrimina.

Es el resultado que el pre-registro llama INSUFICIENTE, alcanzado antes de la etapa de validez y por una
razón más fuerte que la prevista: no es que se perdieran pares por inválidos, es que no caben.

## Qué pasó

1. El pre-registro quedó fijado en el commit `87e6032` del PR #199, tras tres pasadas de un revisor
   independiente, antes de encargar el banco.
2. El banco se encargó a una ejecución nueva de Codex, sin contexto del concilio, en una carpeta que solo
   contenía el protocolo, `src/experiments/agent.py`, la aplicación y `benchmark/public/`.
3. El autor leyó los tres operadores y la aplicación, contó dónde puede actuar cada operador y **se detuvo
   sin escribir ninguna tarea**, como su encargo le pedía hacer si los dieciséis defectos distintos no
   existían. No ejecutó tests ni operadores. Dejó un manifiesto con lo que leyó y lo que ejecutó.

## La cuenta, comprobada

El autor contó seis sitios reparables. El orquestador lo comprobó aparte, leyendo `BoundedRepairAgent.change`
y buscando en la aplicación los patrones que cada operador exige:

| Operador | Patrón que exige | Sitios en la aplicación |
|---|---|---|
| `validate_optional_identity` | una asignación `… = USERS.get(…)` en un archivo que nombra `Unauthorized` | `app/auth.py`, `app/middleware.py` |
| `normalize_environment` | una asignación `… = os.getenv(…)` en un archivo con una constante `DEFAULT_…` | `app/config.py`, `app/services/reporting.py` |
| `initialize_storage` | un método `start` que usa `self.database.execute`, o una asignación `nombre = Database()` | `app/api.py`, `app/worker.py` |

Seis sitios, dos por operador. Con seis sitios caben tres pares disjuntos: o los tres de mismo operador, o
tres de operador distinto, no cuatro y cuatro.

**Las nueve tareas actuales ya ocupan esos seis sitios.** Según `benchmark/private/`, EXP-01 a EXP-06 usan
uno cada una, y EXP-07, EXP-08 y EXP-09 repiten los sitios de EXP-04, EXP-05 y EXP-06 con otro defecto u otro
enunciado.

## Qué se puede concluir

- **Sobre el predicado: nada.** Sigue siendo un candidato respaldado por tres tareas cuyas reglas se
  escribieron conociéndolas ([#58](diagnostic-baseline.md)).
- **Sobre el banco: tiene un techo de seis defectos distintos, en tres familias de dos.** No es una cuestión
  de escribir más tareas: cualquier tarea nueva cae en uno de esos seis sitios. Ningún contraste que necesite
  más de seis unidades independientes, o más de tres pares disjuntos, cabe en este solver tal como está. Eso
  incluye el contraste de selección frente a reservorio que el concilio discutió y las doce familias que
  pedía el diseño del concilio anterior.
- **Sobre los resultados ya publicados: no cambian.** Son conteos exactos sobre esas nueve tareas y así se
  presentaron. Lo que cambia es lo que se puede esperar de añadirles tareas.

## Qué no se hizo

- No se comprobó la validez de ninguna tarea (no hay tareas).
- No se ejecutó `diagnose` sobre nada nuevo.
- No se midió el efecto del predicado sobre el primer intento: era la segunda etapa y no se abre.

## Desviaciones

- **El tamaño pedido era inalcanzable y el pre-registro no lo comprobó antes.** Quien lo escribió no contó
  los sitios reparables, aunque podía: el código de los operadores estaba a la vista. Lo advirtió al dueño
  como riesgo después de fijar el tamaño, no antes.
- **El encargo permitía al autor detenerse**, y se detuvo. No se le pidió después escribir los tres pares que
  sí caben: tres pares no alcanzan ningún veredicto distinto de INSUFICIENTE (una separación perfecta de tres
  pares tiene probabilidad de 1/3 o más por azar), y habría sido cambiar el diseño después de conocer el
  obstáculo.

## Material

- Encargo al autor y su manifiesto: en el expediente sin versionar del concilio
  (`.scratch/concilio_cuantitativo/codex/prompt_autor_banco.md` y `autor_banco_manifiesto.md`). El texto del
  manifiesto sobre la capacidad de los operadores se resume en la tabla de arriba.
- Código leído para la comprobación: `src/experiments/agent.py` (`change`), `experiments/software_project/app/`.
