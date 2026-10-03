# Pre-registro · Campaña A/B/C/D de skills del envío (#104)

Fecha de este texto: 2026-10-03. No hay episodios de entrenamiento, ni skills congeladas, ni señuelos,
ni recibos de la campaña. Los tres parámetros que dependen de la línea base siguen en null en
[`campana_abcd.json`](../../experiments/gemma_developer_agent/preregistro/campana_abcd.json).

Este documento fija lo que el issue #104 pide dejar escrito antes de cualquier dato de C. No corre la
campaña. La línea base A sigue en
[`kaggle-baseline-a.md`](kaggle-baseline-a.md): aquí no se cambia, y sus reglas G1 a G6 se citan, no se
copian. El borrador [`preregistration_abcd.md`](../../experiments/gemma_developer_agent/drafts/preregistration_abcd.md)
queda como estaba.

Las «skills» de esta campaña son archivos `SKILL.md` del envío a la competencia. No son una skill de
memoria ni una skill de entorno ([glosario](../entorno/glosario.md), términos 4 y 5). El agente que las
lee es el agente del envío, no el agente de biblioteca ni el solver acotado.

## Qué queda bloqueado

La prueba no empieza hasta que se cumplan las dos cosas, en este orden:

1. `python -m scripts.kaggle_prereg comprobar` sale con 0 en un commit de `main` (compuertas de #103,
   de C0.5 a C5).
2. El análisis de réplicas de A sale con 0 y, con ese reporte, se cierra `variacion_a` en el JSON de
   esta campaña, todavía sin episodios de entrenamiento.

Lo que desbloquea el paso 1 es el registro del ensayo de notebook, la validez de las tareas, la cuota
versionada, el subconjunto y el piloto. Lo que desbloquea el paso 2 es ese reporte de réplicas. Mientras
tanto `python -m scripts.kaggle_campana comprobar` sale con 1.

## Partición

Se hereda la de la línea base, sección B: `leave_one_repo_out`. No es temporal.

La prueba son los `instance_id` de la lista `test` del archivo de subconjunto que cierre esa sección. El
entrenamiento son los de `train`. El argumento para reservar un repositorio y no cortar por fecha es el
de esa sección: la pregunta es si la experiencia pasa a un repositorio sin episodios, y con un corte
temporal las skills se consolidarían y se probarían en los mismos repositorios. Qué repositorio queda
reservado lo decide la escalera de la línea base, no este documento.

Los identificadores no se listan aquí: el archivo de subconjunto todavía no existe. Cuando exista, su
SHA-256 de blob de git es el valor de `subconjunto`.

## Condiciones

El envío de A es el de la línea base. El brazo A de los contrastes son todas sus réplicas completas
(G5). B, C y D usan el mismo `eval_config.yaml`, el mismo arnés, el mismo entorno y la misma
concurrencia. Si algo de eso difiere, A se corre de nuevo, como ya dice G5.

| Condición | Qué se añade al envío de A |
|---|---|
| A | Nada. |
| B | Un solo archivo de texto, de la misma longitud en caracteres que la suma de los `SKILL.md` de C, escrito a mano después de congelar C. |
| C | Los `SKILL.md` consolidados desde el pase de entrenamiento. |
| D | Los mismos archivos que C, más la instrucción de abajo, una sola vez, en el prompt del agente del envío. |

**B es un placebo de longitud, no unas heurísticas.** Quien lo escribe es otra persona que la que
redacta C. Recibe solo el entero de la longitud. No recibe el texto de C, ni los recibos, ni enunciados
de prueba, ni resultados. El archivo es la frase fijada
`Este párrafo no indica ningún cambio de código.` repetida, y espacios hasta completar el entero. Esa
frase no nombra `get_code_neighbors`, `search_similar_code` ni `get_code_subgraph`. B no contiene la
instrucción de D: un placebo que manda usar el grafo mediría D, no la longitud.

**C** sale de un solo pase de la condición A sobre las tareas de entrenamiento
(`pases_entrenamiento` = 1, el mismo número que ya fijó la línea base). Una skill entra en el envío solo
si hay al menos tres recibos de ese pase con estado resuelto, en tres `instance_id` distintos, todos de
`train`. El mismo identificador repetido no cuenta como tres. La redacta una persona, no un modelo de
lenguaje. Lee esos recibos (identificador, repositorio y motivo de los intentos anteriores al éxito) y
el texto que ella misma escribe. No lee enunciados de prueba, parches de referencia, salidas crudas del
arnés ni resultados de la prueba. Si más adelante la redactara un modelo de lenguaje, eso sería una
enmienda y habría que guardar el prompt, el identificador del modelo y la salida antes de ver la prueba.

**D no añade herramientas.** El kit ya anuncia `get_code_neighbors`, `search_similar_code` y
`get_code_subgraph`. La única diferencia con C es esta instrucción, literal:

```text
Before you apply any skill, locate the code with the graph tools. Take a symbol that appears in the failing test name or in the traceback and call get_code_neighbors, search_similar_code, or get_code_subgraph on that symbol. Read the tool result. Only then follow a skill.
```

D se corre solo si, después de reservar las corridas de B y de C que exige G2, el cómputo que ya fijó la
línea base también admite las mismas corridas de D. Si no, D no se corre y H(D, C) queda fuera de
alcance. Eso no es «sin diferencia».

## Réplicas y margen

No hay un número de réplicas en este documento. Sale del reporte de A, cuando exista.

`M*` es el de la sección G de la línea base: el mayor entre el suelo 6/n y la diferencia mínima del peor
par de réplicas de A. Las comparaciones usan la fracción `diferencia / n`, no una tasa redondeada. Una
diferencia igual a `M*` no lo supera.

| Caso de G2 | Corridas de B y de C | D |
|---|---|---|
| Ruido bajo (`M* ≤ 6/40`) | 1; 2 si esas dos caben en las horas ya contadas | El mismo número, solo si cabe |
| Ruido intermedio | 2 | 2, solo si caben |
| Ruido dominante | No hay campaña confirmatoria ni descriptiva | No se corre |

Si el ruido es dominante, el resultado que se publica es el que ya escribe G2. No se abre una campaña
descriptiva después de ver el reporte: esa elección quedaría hecha con el número delante.

Si hace falta reducir (G6), se quita D primero. No se baja de las corridas que G2 marca como mínimo. Si
ni el mínimo de B y de C cabe, la campaña no se corre. El presupuesto por tarea no se cambia.

## Estimador

Varias corridas de una condición se resumen así, por `instance_id`, antes de ver episodios de
entrenamiento. Es mayoría estricta: la tarea cuenta como resuelta si hay más corridas resueltas que no
resueltas. Con una corrida manda esa. Con dos hacen falta las dos. Un empate no resuelve.

Un fallo de infraestructura se trata como en el análisis de réplicas de A: mientras quede uno sin
repetir, no hay desenlace. El contraste usa solo las tareas de prueba con bit definido en las dos
condiciones. `n` es ese número. La diferencia es el conteo de resueltas de la primera menos el de la
segunda.

## Hipótesis

Cada una tiene tres desenlaces, y no queda ningún entero fuera. Sea `d` la diferencia de resueltas y
`n` el denominador de arriba.

| Hipótesis | Apoyada si | Sin diferencia si | Refutada si |
|---|---|---|---|
| H(C, A) | `d/n > M*` con d = C − A | no se supera `M*` en ningún sentido | `d/n > M*` con d = A − C |
| H(C, B) | `d/n > M*` con d = C − B | no se supera `M*` en ningún sentido | `d/n > M*` con d = B − C |
| H(D, C) | `d/n > M*` con d = D − C | no se supera `M*` en ningún sentido | `d/n > M*` con d = C − D |

H(C, A) hereda G3. Si A resuelve menos de 6 tareas en alguna réplica, «refutada» de H(C, A) queda fuera
de alcance y se dice así. Si A deja menos de 6 sin resolver, la campaña no declara mejora y H(C, A)
«apoyada» queda fuera de alcance. Esos dos no se renombran como «sin diferencia».

H(C, B) y H(D, C) usan el mismo `M*`. Eso supone que la variación entre corridas es la de A: la de B, C
y D no se mide aparte. Si D no se corrió, H(D, C) no se lee.

La lectura, cuando haya recibos, da numerador y denominador por tarea y por réplica, y el desenlace con
la regla de esta tabla. Hoy no hay lectura en `docs/results/`: no hay recibos.

## Predicción

Una. Sobre las tareas de prueba, no sobre los señuelos: **H(C, A) no queda apoyada.** La refuta el
desenlace «apoyada» de H(C, A). No hay predicción sobre H(C, B), sobre H(D, C) ni sobre los señuelos.

## Señuelos

Se escriben después de congelar C y antes de la campaña de prueba. Quien los escribe no es quien redacta
las skills y no ha visto resultados de C ni el texto de las skills. Recibe solo los enunciados originales
de los `instance_id` que salen de la regla de abajo.

Regla, fijada ahora: se ordenan los `instance_id` de `test` y se toma uno de cada cinco, empezando por
el primero. Cada señuelo es una copia con otro enunciado y con identificador `instance_id + "#senuelo"`.
Reescribir el enunciado modifica el benchmark: los señuelos no entran en `test`, no cambian el archivo de
subconjunto y no entran en el denominador de H(C, A), H(C, B) ni H(D, C). Si salen menos de seis, la
lectura de señuelos da el conteo y no usa «apoyada», «sin diferencia» ni «refutada».

## Comprobación de fuga

`python -m scripts.kaggle_campana fuga --subconjunto <archivo> --raiz <directorio>` busca cada
`instance_id` de `test` en los archivos de esas raíces. Sale con 2 si aparece alguno. Se corre sobre los
episodios de entrenamiento y sobre las skills, y otra vez antes del merge de la campaña. El subconjunto
mismo no se pasa como raíz: ahí los identificadores de prueba están por definición.

## Orden de commits

1. Este documento y `campana_abcd.json`. Sin episodios.
2. `scripts/kaggle_campana.py` y sus pruebas, sobre datos sintéticos.
3. El reporte de réplicas de A y el cierre de `variacion_a` y de `corridas_por_condicion`. Sigue sin
   episodios de entrenamiento.
4. Episodios del pase de A sobre `train`.
5. Skills de C congeladas, con su hash.
6. Placebo y señuelos.
7. Recibos de la prueba de B, C y, si cupo, D.

Un commit posterior no puede ser ancestro de uno anterior de esta lista. La campaña de prueba no se
mergea si el paso 2, aplicado a los pasos 4 y 5, sale distinto de 0.

## Fuera de alcance

Entrenar un adaptador. Enviar a Kaggle para elegir entre condiciones. Correr Gemma en esta entrega.
Rellenar `variacion_a` sin el reporte de #103. Declarar un desenlace.
