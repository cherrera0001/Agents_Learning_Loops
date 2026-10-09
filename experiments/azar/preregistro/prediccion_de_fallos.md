# Pre-registro: predecir el fallo antes de que ocurra

**Versión 1: commit `b98af92`, 2026-10-09 a las 05:05 UTC**, antes de conocer ninguno de los desenlaces de la
sección 5. La primera redacción decía «hacia las 05:30 UTC», 25 minutos después de su propio commit: era un
error, y lo señaló la revisión de documentos. La fecha que vale es siempre la del commit.

**Versión 2: enmiendas de la sección 8**, escritas tras la revisión de documentos y el recuento del analista
de datos, cuando las predicciones 4 y 5 ya tenían desenlace a la vista. Las secciones 1 a 7 quedan como se
escribieron, salvo este encabezado; lo que la sección 8 cambia, lo dice.

## 1. Pregunta

¿Una predicción escrita antes de empezar acierta los fallos de un issue mejor que la frecuencia histórica de
esos fallos? Y si acierta, ¿sirve para evitarlos o para resolverlos antes?

Son dos preguntas. Este pre-registro solo cubre la primera. La segunda necesita comparar issues con y sin
predicción, y no se intenta hasta que la primera tenga lectura.

## 2. Unidad y universo

- **Unidad:** una predicción binaria sobre un hecho comprobable de un issue de este repositorio, con una
  probabilidad entre 0 y 1.
- **Universo:** los issues que se abran o se revisen desde este commit. No se predice hacia atrás.
- **Quién predice:** el orquestador, antes del hecho. Más adelante, un rol propio (sección 7).
- **Quién marca el desenlace:** un rol distinto del que predijo, con el enlace que lo prueba (informe del
  revisor, CI, `mergedAt`).

## 3. Clases de fallo

Salen de lo que los episodios ya registran. Una predicción nombra una de estas clases o un hecho concreto.

| Clase | Ejemplo en la bitácora |
|---|---|
| Da por bueno lo que no lo es | Un guion sale con código 0 sobre una corrida incompleta (episodios 065, 067 y PR #161) |
| Cifra que no se reproduce | Una cifra del informe que otro recuento no encuentra |
| Cambio sin revisar | Una corrección posterior al dictamen que se sube sin volver al revisor (episodio 067) |
| Ensayo que no se parece al sistema real | Un «pasa» local que no cubre lo que cambia en producción (episodio 068) |
| Entorno | Rutas, codificación, cuenta equivocada, Git Bash |
| Texto que dice más que la fuente | Una cita o una frase que la fuente no respalda (este issue, episodio 070) |
| Prueba frágil | Una prueba que pasa por la razón equivocada o que depende de un umbral al límite |

## 4. Medida, línea base y lectura

- **Medida:** puntuación de Brier, la media de (probabilidad − desenlace)², con desenlace 1 o 0. Menor es
  mejor.
- **Línea base:** para cada predicción, la frecuencia histórica de ese hecho, contada desde los episodios
  antes de predecir y escrita junto a la predicción. Si no hay historia para contarla, la línea base es 0,5 y
  se dice.
- **Lectura:** se compara la puntuación de Brier de las predicciones con la de la línea base sobre las mismas
  unidades.
- **Tamaño mínimo:** no se lee con menos de 30 predicciones cerradas. Con menos, solo se informa el conteo de
  aciertos y fallos, sin conclusión.
- **Qué la refuta:** con 30 o más, una puntuación de Brier igual o peor que la de la línea base.
- **Lo que no se puede concluir:** que predecir sirva para evitar el fallo. Una predicción escrita puede
  cambiar el desenlace (quien predice un defecto lo busca). Ese efecto se anota, no se separa aquí.

**Potencia: sin calcular.** Antes de la primera lectura hay que calcular qué diferencia de Brier distinguen 30
predicciones. Hasta entonces, 30 es un mínimo para no leer ruido, no un tamaño justificado.

## 5. Primeras predicciones

Escritas antes de conocer el desenlace. La columna de la derecha se rellena después, por otro rol.

| # | Hecho | Probabilidad | Línea base y de dónde sale | Desenlace |
|---|---|---|---|---|
| 1 | La cuarta revisión de código del PR #161 pide al menos un cambio antes de fusionar | 0,45 | 0,67: dos de sus tres revisiones anteriores lo pidieron | |
| 2 | Esa revisión encuentra otro caso de «da por bueno lo que no lo es» en `scripts/kaggle_registro.py` | 0,35 | 1,00: las tres anteriores encontraron uno | |
| 3 | El recuento del analista de datos sobre esa ronda contradice alguna cifra del implementador | 0,10 | 0,00: tres recuentos, ninguna contradicción numérica | |
| 4 | La revisión de documentos del PR de este issue (#162) encuentra al menos una frase de `docs/estado_del_arte.md` que dice más que el informe del investigador | 0,65 | 0,5: sin historia contada | |
| 5 | La CI del primer commit del PR de este issue termina en verde | 0,80 | 0,5: sin historia contada | |
| 6 | Tras fusionar los PR #161 y #162, la CI de `main` queda en verde sin un commit de arreglo | 0,75 | 0,5: sin historia contada | |

Sobre la predicción 2: se da menos que la línea base porque la tercera ronda cambió el diseño (la orden recibe
la lista de pasadas esperadas en vez de adivinarlas). Si aun así aparece otro caso, la predicción falla y la
línea base acierta.

Sobre la predicción 6: al preparar este PR, un episodio nuevo hizo fallar una prueba de la bitácora que en
`main` pasaba con un margen de 0,01. Se arregló en este mismo PR. Queda anotado porque es el tipo de fallo que
este experimento quiere ver venir: estaba en `main` antes de que nadie lo tocara. (Esta nota tiene un error;
ver 8.3 bis.)

## 6. Qué se registra de cada predicción

Fecha y commit en que se escribió, quién la escribió, el hecho, la probabilidad, la línea base con su cuenta,
el desenlace, quién lo marcó y el enlace que lo prueba. Una predicción no se edita después de escrita: si
estaba mal planteada, se anula con su motivo y cuenta como anulada.

## 7. Lo que falta para que esto sea recurrente

- Un rol que prediga (con la bitácora delante) y otro que marque, con definición escrita.
- Una skill de entorno que obligue a escribir la predicción antes de empezar un issue, junto al recall.
- Contar las líneas base desde los episodios con un guion, no a mano.
- La investigación previa ante un problema nuevo como paso fijo, con las citas verificadas.

Cada punto es un issue aparte.

## 8. Enmiendas de la versión 2

Ninguna predicción se ha leído todavía con la medida de la sección 4. Estas enmiendas corrigen el protocolo
antes de esa lectura. Las probabilidades de la sección 5 no se tocan.

### 8.1 Líneas base recontadas

El analista de datos las contó desde la bitácora del caso, los episodios y GitHub. Donde difiere, vale su
cuenta. Las de la sección 5 quedan como testimonio de lo que el orquestador escribió de memoria.

| # | Sección 5 | Recuento | Intervalo de Wilson al 95 % | Qué pasó |
|---|---|---|---|---|
| 1 | 0,67 | 2 de 3 por el veredicto escrito; 3 de 3 por lo que provocó | 0,21 a 0,94; 0,44 a 1,00 | Ambigua: no decía qué cuenta como «pide un cambio» |
| 2 | 1,00 | 3 de 3 | 0,44 a 1,00 | Exacta, con tres observaciones |
| 3 | 0,00 | 1 de 4 recuentos marcó una cifra que no se reproduce | 0,05 a 0,70 | Inexacta: la línea base es 0,25 |
| 4 | 0,5 | No contable: una revisión sin hallazgos no deja rastro en los episodios | — | Sigue en 0,5 |
| 5 | 0,5 | 44 de 51 primeros commits con CI en verde, contando los cancelados como no verdes; 44 de 45 sin ellos | 0,74 a 0,93; 0,88 a 1,00 | Contable: 0,86 |
| 6 | 0,5 | 1 rojo en 82 fusiones a `main`; para dos fusiones seguidas, cerca de 0,97 en verde | 0,2 % a 6,6 % de rojo por fusión | Contable: 0,97 |

Tres de las seis líneas base estaban mal o sin contar. Una línea base la cuenta un guion antes de predecir
(issue #167), no quien predice.

### 8.2 Qué cuenta como acierto

Aclaraciones escritas antes de conocer el desenlace de las predicciones 1, 2, 3 y 6.

- **Predicción 1.** «La cuarta revisión» es la primera revisión de `revisor-codigo` sobre la cabeza del
  PR #161 posterior al tercer dictamen, que es el commit `90e6b31`. Ocurre el hecho si su veredicto escrito
  es «cambios requeridos antes de fusionar» o «cambios requeridos». No cuentan «apto para fusionar»,
  «apto con observaciones no bloqueantes» ni «aprobado con observaciones», aunque después se corrija algo.
- **Predicción 2.** Ocurre si esa revisión muestra una entrada con la que `diagnosticar` o `comprobar` salen
  con código 0 sobre una corrida que el propio informe califica de incompleta o no fiable, y esa entrada es
  alcanzable desde el notebook. Los casos que el informe marque como no alcanzables no cuentan.
- **Predicción 3.** Ocurre si el recuento marca «no se reproduce» en al menos una cifra del informe del
  implementador. Una cifra que solo cambia con otra definición, declarada como tal, no cuenta.
- **Predicción 6.** Se mide sobre el flujo de CI de `main` en el commit de fusión del segundo de los dos PR.
  Ocurre si sus comprobaciones terminan en `success` sin que medie otro commit. Si alguno de los dos PR no se
  fusiona antes del 2026-10-16, la predicción se anula.
- **Predicciones 1 y 2** hablan del mismo evento y no son independientes: cuentan como una sola unidad
  efectiva (apartado 8.4).
- **Predicción 4.** Ocurre si el informe de `revisor-docs` sobre el commit `b98af92` señala al menos una
  frase de `docs/estado_del_arte.md` que no está en el informe del investigador, guardado en
  [`../docs/informe_investigador_2026-10-09.md`](../docs/informe_investigador_2026-10-09.md). Esta
  definición se escribió con el desenlace ya conocido.
- **Predicción 5.** Se mide sobre las comprobaciones del commit `b98af92`. Ocurre si todas terminan en
  `success`. Una comprobación `cancelled` cuenta como no verde; por eso su línea base es 0,86 y no 0,98.
  Esta definición se escribió con el desenlace ya conocido.

### 8.3 Desenlaces ya a la vista al escribir esta versión

- **Predicción 4: ocurrió.** La revisión de documentos del PR #163 encontró frases de
  `docs/estado_del_arte.md` que no estaban en el informe del investigador (una interpretación sobre la moneda
  y la ruleta, y dos categorías de «no buscado»). La marcó el propio revisor en su informe. Falta que un rol
  distinto del orquestador la registre con su enlace.
- **Predicción 5: ocurrió.** Las 12 comprobaciones del commit `b98af92` terminaron en `success`
  (`gh api repos/cherrera0001/Agents_Learning_Loops/commits/b98af92/check-runs`). La primera redacción de
  esta versión decía «sin cerrar»: el orquestador había leído la CI unos minutos antes y no la volvió a
  leer al escribir. Lo corrigió la segunda revisión de documentos.

### 8.3 bis Una afirmación de la sección 5 que resultó falsa

La nota sobre la predicción 6 dice que un episodio nuevo «hizo fallar una prueba» y da a entender que `main`
habría fallado al fusionar los dos PR. La revisión de código del PR #163 lo midió: `main` con los episodios
de los dos PR pasaba. La prueba es frágil por otra causa (un episodio nuevo puede bajar la relevancia, porque
las aristas viejas decaen con el reloj; otro episodio puede subirla si su texto se parece a la consulta) y el
arreglo de este PR le da margen para unos 15 episodios sobre otro tema, no la cura. La predicción 6 no
cambia; su nota era una explicación equivocada del orquestador.

### 8.4 Medida y tamaño, corregidos

Sustituye, de la sección 4, los puntos «Lectura», «Tamaño mínimo» y «Qué la refuta», y su párrafo de
potencia. Quedan como estaban «Medida», «Línea base» y «Lo que no se puede concluir».

- **Prueba:** t pareada de una cola al 5 % sobre las diferencias de Brier por unidad efectiva. Sin esa
  prueba no se afirma ni se refuta nada.
- **Una sola regla, con tres resultados que se excluyen.** Se calcula el intervalo de confianza al 90 % de dos
  colas de la diferencia de Brier (línea base menos predicción; positivo es mejor), que equivale a la prueba
  de una cola al 5 %. Con el tamaño de decisión alcanzado:
  - si el extremo inferior del intervalo es mayor que cero, **se afirma** que predecir acierta mejor, y se
    da el intervalo;
  - si el extremo superior es menor que cero, **se refuta**: predecir acierta peor que la frecuencia
    histórica;
  - en cualquier otro caso (el intervalo contiene el cero o lo toca), el resultado es **no concluyente** y
    así se informa. Un «no concluyente» no dice que predecir no sirva: dice que estos datos no lo deciden.
- **Unidad efectiva:** las predicciones de un mismo issue están correlacionadas. Se agrupan por issue y la
  prueba se hace sobre la media por issue.
- **Potencia, calculada por el analista de datos** (simulación con un predictor calibrado, que es el mejor
  caso): con 30 predicciones independientes, una mejora de Brier de 0,02 se detecta entre 18 y 22 de cada 100
  veces, y una de 0,05 entre 37 y 43. Para 80 de cada 100 hacen falta entre 100 y 200 predicciones si la
  mejora es de 0,05, y más de 400 si es de 0,02.
- **Tamaños:** con menos de 30 predicciones cerradas solo se informa el conteo. Entre 30 y 100, la puntuación
  de Brier se informa como descripción, sin conclusión. La lectura de decisión no se hace con menos de 100
  predicciones cerradas en al menos 20 issues. **Ese umbral es una convención del orquestador y no sale
  de la tabla de potencia:** la prueba se hace sobre la media por issue, así que 20 issues son unas 20
  unidades, y con 20 unidades la potencia queda por debajo de la que el analista calculó para 100
  predicciones independientes. La potencia del diseño agrupado está sin calcular; hay que calcularla
  antes de la lectura de decisión y subir el umbral si no alcanza.
- **Predicción sin desenlace:** si el hecho no llega a poder comprobarse en el plazo que la predicción fija,
  se anula y cuenta como anulada. Una predicción sin plazo vence a los 30 días.
- **Quién elige qué se predice:** quien predice elige los hechos, pero debe cubrir cada clase de la sección 3
  que aplique al issue y decir cuáles dejó fuera y por qué. Predecir solo lo fácil se ve en ese registro.

### 8.5 Una clase que faltaba

El analista clasificó los 203 pasos fallidos de los 65 episodios: 68 no caben en ninguna de las siete clases.
La mayor parte son **defectos de lógica o de diseño propio** (un error en el código, una expectativa
equivocada, un conflicto entre dos PR paralelos). Se añade como octava clase. Su clasificación fue por
palabras clave, con un acierto de 60 a 70 % en una muestra revisada a mano: los conteos por clase son cotas,
no cifras.

### 8.6 El efecto de predecir sobre el desenlace

Propuesta del analista, sin aplicar todavía (issues #165 y #166): un rol distinto del implementador escribe
las predicciones y registra su hash antes de que empiece el trabajo; un sorteo fijado de antemano decide
cuáles ve el implementador y cuáles quedan selladas. Comparar la frecuencia del hecho entre reveladas y
selladas separa el efecto de predecir del acierto de predecir. Con frecuencias de 0,4 frente a 0,2 hacen
falta unas 62 predicciones por rama, y unas 135 contando la agrupación por issue.

Las seis predicciones de la sección 5 las escribió quien hace el trabajo y las vio todo el mundo. Sirven para
ensayar el protocolo, no para esa comparación.

## 9. Desenlaces registrados

Los registra el orquestador a partir de lo que cada rol escribió en su informe. Los informes de los revisores
y del analista no están en GitHub: quedan resumidos en la bitácora del caso. Mientras no exista el rol que
marca (issue #165), esta tabla no es una marca independiente, y se dice.

| # | Probabilidad | Línea base recontada | Desenlace | Quién lo escribió y qué lo prueba |
|---|---|---|---|---|
| 1 | 0,45 | 0,67 | No ocurrió | `revisor-codigo`, sobre `90e6b31`: «VEREDICTO: apto con observaciones no bloqueantes». PR #161 fusionado, `mergedAt` 2026-10-09T05:27:08Z |
| 2 | 0,35 | 1,00 | No ocurrió | El mismo informe: «CASO DE CÓDIGO 0 SIN MERECERLO, ALCANZABLE DESDE EL NOTEBOOK: no». Halló ocho entradas fabricadas a mano que salen con 0; ninguna la produce el notebook, y eso lo infirió leyendo las celdas, sin ejecutarlo |
| 3 | 0,10 | 0,25 | No ocurrió | `analista-datos`, cuarto recuento: «PREDICCIÓN 3: no ocurrió» |
| 4 | 0,65 | 0,5 | Ocurrió | `revisor-docs`, sobre `b98af92`: tres elementos de `docs/estado_del_arte.md` que no estaban en el informe del investigador (una interpretación sobre la moneda y la ruleta, y dos categorías de «no buscado») |
| 5 | 0,80 | 0,86 | Ocurrió | 12 de 12 comprobaciones de `b98af92` en `success` |
| 6 | 0,75 | 0,97 | Abierta | Falta fusionar el PR #163 |

Las aclaraciones de 8.2 para las predicciones 1, 2 y 3 se subieron en el commit `f7af948` (05:15 UTC). Que la
cuarta revisión y el cuarto recuento se lanzaron después de ese commit no consta en ningún registro: lo dice
el orquestador. La aclaración de la predicción 1 se reescribió en `61cc485` (05:30 UTC), tres minutos después
de fusionarse el PR #161, para nombrar el commit `90e6b31` y cerrar la lista de veredictos; su sentido no
cambió («aprobado con observaciones» ya no contaba), pero esa redacción es posterior al desenlace. Las de las
predicciones 4 y 5 se escribieron después de conocer el suyo.

Son cinco predicciones cerradas en dos issues, escritas por quien hacía el trabajo. No se calcula ninguna
puntuación con ellas.
