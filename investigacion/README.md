# investigacion/: área de investigación

Una biblioteca local de fuentes (obras y videos) que cualquier sesión puede buscar antes de experimentar.
La mantiene el [investigador de fuentes](../docs/entorno/agentes.md#investigador-de-fuentes), un agente de
entorno. La regla y su orden están en
[`CONTRIBUTING.md`](../CONTRIBUTING.md#investigación-antes-del-experimento) (*Investigación antes del
experimento*); este archivo solo dice qué hay aquí y cómo se usa.

## Qué es

- [`fuentes/indice.jsonl`](fuentes/indice.jsonl): una línea por fuente, en JSON. Es lo que se busca.
- `fuentes/<fuente>/`: el manifiesto de esa fuente (fecha, método y conteo), sus fichas y, si lo hay, un
  parecer para el concilio. La primera es [`fuentes/paper-club/`](fuentes/paper-club/MANIFIESTO.md).

## Qué no es

- No es el agente de biblioteca ni el solver acotado, ni una entrada de ninguno de los dos: nada de esta
  carpeta llega al harness de experimento.
- No es una skill de memoria ni la bitácora: no crea nodos, y los episodios de `learning/episodes/` siguen
  siendo la fuente de verdad de lo aprendido al desarrollar.
- No es evidencia. Una cifra de un paper o de un video es de su autor; los resultados de este repositorio
  están en `docs/results/` y sus recibos en `evidence/`.
- No reemplaza al investigador de papers, que abre la obra que el código ya nombra y veta las citas de un
  texto público. Una ficha de aquí no autoriza una cita en un texto público: esa revisión se hace aparte.
- No es un diseño de experimento. Un parecer nombra un contraste y el resultado que lo descartaría; la
  corrida se diseña después, con [`specs/software_learning_protocol.md`](../specs/software_learning_protocol.md),
  [`specs/loop_protocol.md`](../specs/loop_protocol.md) y la skill
  [`concilio-de-experimento`](../skills/concilio-de-experimento/SKILL.md).

## Esquema de una ficha

Cada línea de `indice.jsonl` es un objeto con estos trece campos, todos de texto:

| Campo | Qué lleva |
|---|---|
| `id` | Identificador corto y estable de la ficha. |
| `clase` | `biblioteca` u `oceano`, con la definición de `CONTRIBUTING.md`. Una obra abierta cuyo mecanismo no está medido aquí es `oceano`. |
| `tipo` | `paper`, `video`, `foro` u `otro`. |
| `titulo` | Tal como lo da el registro de la obra o la página del video. |
| `url` | Dirección que se abrió. Vacía si no se abrió ninguna. |
| `identificador` | DOI, identificador de arXiv con su versión, o `youtube:<id>`. |
| `fecha_consulta` | Día en que se abrió, `AAAA-MM-DD`. |
| `estado` | `abierto` o `no_abierto`. En un video se refiere a su contenido: sin transcripción abierta es `no_abierto` aunque la página haya dado título y descripción. |
| `motivo_si_no_abierto` | Por qué no abrió. Vacío si abrió. |
| `mecanismo` | Una frase con el mecanismo y otra con qué haría en este repositorio, o por qué no aplica. |
| `donde_lo_nombra_el_codigo` | Archivo que lo nombra, o que no lo nombra y con qué búsqueda se comprobó. |
| `medicion_local` | Qué medición de este repositorio lo toca, con su ruta, o que no hay ninguna. |
| `contraste_que_lo_descarta` | Un contraste y el resultado que descartaría el mecanismo. Vacío si no se propone. |

Reglas de una ficha:

- Autor, año y título se copian del registro (arXiv o Crossref), no de memoria.
- Ninguna ficha cita una obra cuyo identificador no se abrió en la sesión que la escribió. Lo que no abre
  queda `no_abierto` con su motivo.
- Una entrada que la página no mostró no existe en el índice.
- De un video se anota solo lo que la página mostró. No se pega una transcripción entera.
- Una fila reservada para una fuente siguiente lleva `no_abierto` y dice que no se procesó.

## Cómo se busca

Con las herramientas de lectura, sin código propio:

- Grep sobre `investigacion/fuentes/indice.jsonl` con una palabra del mecanismo (por ejemplo `memoria`,
  `compactación` o `guía`), con un identificador (`2603.03596`) o con un campo (`"estado": "no_abierto"`,
  `"clase": "oceano"`).
- Glob sobre `investigacion/fuentes/*/fichas/*.md` y Read de la ficha larga, que trae autores y versión.
- Después, Grep del mismo término sobre el código: si el código ya nombra el mecanismo, el orden de
  `CONTRIBUTING.md` manda parar ahí.

## Fuentes

| Fuente | Estado | Dónde |
|---|---|---|
| Paper Club, lista de YouTube del canal de Y Combinator | Procesada el 2026-10-13 | [`fuentes/paper-club/MANIFIESTO.md`](fuentes/paper-club/MANIFIESTO.md) |
| Canal de Y Combinator | Fila reservada, sin procesar | `indice.jsonl`, id `yc-canal` |
| Otras listas de Paper Club | Fila reservada, sin procesar | `indice.jsonl`, id `pc-otras-listas` |
