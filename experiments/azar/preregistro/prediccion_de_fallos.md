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
- **Qué la refuta:** con 30 o más, una puntuación de Brier igual o peor que la de la línea base. (Sustituido por 8.4.)
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
| 6 | 0,75 | 0,97 | Ocurrió | PR #163 fusionado (`mergedAt` 2026-10-09T05:48:58Z, commit `3a55b08`); sus 12 comprobaciones en `main` terminaron en `success` sin otro commit |

Las aclaraciones de 8.2 para las predicciones 1, 2 y 3 se subieron en el commit `f7af948` (05:15 UTC). Que la
cuarta revisión y el cuarto recuento se lanzaron después de ese commit no consta en ningún registro: lo dice
el orquestador. La aclaración de la predicción 1 se reescribió en `61cc485` (05:30 UTC), tres minutos después
de fusionarse el PR #161, para nombrar el commit `90e6b31` y cerrar la lista de veredictos; su sentido no
cambió («aprobado con observaciones» ya no contaba), pero esa redacción es posterior al desenlace. Las de las
predicciones 4 y 5 se escribieron después de conocer el suyo.

Son seis predicciones cerradas en dos issues, escritas por quien hacía el trabajo. No se calcula ninguna
puntuación con ellas.

## 10. Predicciones del issue #164

Escritas por el orquestador antes de que el implementador empiece. La fecha que vale es la del commit que
añade esta sección, que es el primero de la rama `issue-164-tope-por-tarea`. El implementador las ve: no son
selladas (apartado 8.6).

El issue #164 añade al notebook de la iteración 08 un tope por tarea y el vaciado del mapa de hilos del
núcleo, y enseña a `diagnosticar` a distinguir una sesión viva y detenida de una muerta desde fuera.

| # | Hecho | Probabilidad | Línea base y de dónde sale |
|---|---|---|---|
| 7 | El primer informe de `revisor-codigo` sobre el PR del #164 tiene el veredicto «cambios requeridos antes de fusionar» o «cambios requeridos» | 0,30 | 0,00: en los PR #158, #161 y #163 el primer veredicto fue «aprobado con observaciones» las tres veces (0 de 3; Wilson 0,00 a 0,56) |
| 8 | El PR del #164 pasa por tres o más informes de `revisor-codigo` antes de fusionarse | 0,65 | 1,00: PR #158, tres; PR #161, cuatro (2 de 2; Wilson 0,34 a 1,00). El #163 no cuenta: sus revisiones fueron de documentos |
| 9 | Algún informe de `revisor-codigo` sobre ese PR muestra una entrada con la que `diagnosticar` o `comprobar` salen con código 0 sobre una corrida que el informe califica de incompleta o no fiable, alcanzable desde el notebook | 0,30 | 0,75: ocurrió en tres de las cuatro revisiones del PR #161 (Wilson 0,30 a 0,95) |
| 10 | Algún recuento de `analista-datos` sobre ese PR marca «no se reproduce» en al menos una cifra del informe del implementador (una cifra que solo cambia con otra definición, declarada, no cuenta) | 0,15 | 0,20: uno de cinco recuentos sobre los PR #158 y #161 (Wilson 0,04 a 0,62) |
| 11 | Todas las comprobaciones del primer commit del PR del #164 que traiga código terminan en `success` (una `cancelled` cuenta como no verde) | 0,80 | 0,86: 44 de 51 primeros commits (apartado 8.1) |
| 12 | El implementador entrega sin haber logrado que el cuelgue ocurra en el ensayo por la carrera natural de hilos, y el criterio «sin el arreglo la tarea se cuelga» lo cumple solo forzando el ciclo a mano | 0,80 | 0,5: sin historia contada. El forense no lo reprodujo en 9 corridas |

Plazo: las seis vencen el 2026-10-23. Si el PR no existe o no se ha fusionado para entonces, la 8 se anula y
las demás se marcan con lo ocurrido hasta esa fecha.

Clases de la sección 3 cubiertas: «da por bueno lo que no lo es» (9), «cifra que no se reproduce» (10),
«ensayo que no se parece al sistema real» (12), «entorno» y «prueba frágil» (11, en parte). Quedan fuera
«cambio sin revisar» y «texto que dice más que la fuente», porque dependen de lo que haga el orquestador y no
el implementador, y «defecto de lógica propio», que la 7 y la 8 recogen de forma indirecta.

## 11. Predicciones del issue #169

Escritas por el orquestador antes de que el implementador empiece. La fecha que vale es la del commit que
añade esta sección, el primero de la rama `issue-169-guardian-sin-trabajo`. El implementador las ve: no son
selladas (apartado 8.6).

El issue #169 cambia tres reglas del guardián del tablero (`scripts/board_check.py`) para que no exijan
entrega a un issue cerrado sin trabajo. La regla exacta la escribió el auditor del método.

| # | Hecho | Probabilidad | Línea base y de dónde sale |
|---|---|---|---|
| 13 | El primer informe de `revisor-codigo` sobre el PR del #169 tiene el veredicto «cambios requeridos antes de fusionar» o «cambios requeridos» | 0,15 | 0,00: en los PR #158, #161 y #163 el primer veredicto fue «aprobado con observaciones» (0 de 3; Wilson 0,00 a 0,56) |
| 14 | El PR del #169 pasa por tres o más informes de `revisor-codigo` antes de fusionarse | 0,30 | 1,00: PR #158, tres; PR #161, cuatro (2 de 2; Wilson 0,34 a 1,00) |
| 15 | Algún informe de `revisor-codigo` sobre ese PR muestra un issue que queda exento de las reglas 2, 3 o 9 sin deberlo según la regla del issue, o uno que sigue saltando debiendo quedar exento | 0,35 | 0,5: sin historia contada |
| 16 | Todas las comprobaciones del primer commit del PR del #169 que traiga código terminan en `success` (una `cancelled` cuenta como no verde) | 0,85 | 0,86: 44 de 51 primeros commits (apartado 8.1) |

Plazo: las cuatro vencen el 2026-10-23. Si el PR no se ha fusionado para entonces, la 14 se anula.

Por qué la 14 va tan por debajo de su línea base: los dos PR de la historia eran de talla S y L con un guion
nuevo que juzga corridas; este cambia una condición ya escrita por otro rol, con sus casos de prueba
enumerados en el issue. Si aun así necesita tres rondas, la línea base acierta y la predicción falla.

Clases de la sección 3 cubiertas: «da por bueno lo que no lo es» (15), «entorno» y «prueba frágil» (16, en
parte), «defecto de lógica propio» (13 y 14, de forma indirecta). Quedan fuera las demás: no hay cifras de
experimento ni ensayo en este issue.

## 12. Predicciones del issue #171

Escritas por el orquestador antes de que el implementador empiece. La fecha que vale es la del commit que
añade esta sección, el primero de la rama `issue-171-procesamiento-de-logs`. El implementador las ve: no son
selladas (apartado 8.6).

El issue #171 añade un vigía de solo lectura de los envíos de Kaggle al iniciar sesión, una cuenta por llamada
de cada sesión a partir de las trazas, y un registro de hallazgos medidos con su estado.

| # | Hecho | Probabilidad | Línea base y de dónde sale |
|---|---|---|---|
| 17 | El primer informe de `revisor-codigo` sobre el PR del #171 tiene el veredicto «cambios requeridos antes de fusionar» o «cambios requeridos» | 0,55 | 0,25: uno de cuatro primeros veredictos (PR #158, #161 y #163 «aprobado con observaciones»; PR #170 «cambios requeridos»; Wilson 0,05 a 0,70) |
| 18 | El PR del #171 pasa por tres o más informes de `revisor-codigo` antes de fusionarse | 0,60 | 1,00: PR #158, tres; PR #161, cuatro (2 de 2; Wilson 0,34 a 1,00). El PR #170 sigue abierto y no cuenta |
| 19 | Algún recuento de `analista-datos` sobre ese PR marca «no se reproduce» en al menos una cifra de la cuenta por llamada frente a las que recalculó el auditor del método en el concilio 42 (una cifra que solo cambia con otra definición, declarada, no cuenta) | 0,45 | 0,5: sin historia contada. En el concilio 42 tres roles dieron cifras distintas de lo mismo por usar definiciones distintas |
| 20 | Algún informe de `revisor-codigo` muestra una entrada con la que el vigía calla un cambio de estado de un envío que debía avisar, o lo da por procesado sin estarlo | 0,40 | 0,80: cuatro de las cinco revisiones de guiones que juzgan corridas en los PR #161 y #170 hallaron un caso de «da por bueno lo que no lo es» (Wilson 0,38 a 0,96) |

Plazo: las cuatro vencen el 2026-10-23. Si el PR no se ha fusionado para entonces, la 18 se anula.

**Corrección a mis probabilidades anteriores.** En las predicciones 13 y 15 del issue #169 di 0,15 y 0,35 a
que la primera revisión pidiera cambios y a que mostrara un caso mal resuelto; ocurrieron las dos. Subo las de
este issue respecto de aquellas, y lo digo aquí para que quede a la vista: es el orquestador ajustando tras
fallar, no una línea base nueva.

Clases de la sección 3 cubiertas: «da por bueno lo que no lo es» (20), «cifra que no se reproduce» (19),
«defecto de lógica propio» (17 y 18, de forma indirecta). Quedan fuera «ensayo que no se parece al sistema
real» (no hay ensayo) y «entorno» (el vigía depende de la red y del token: lo cubren sus criterios, no una
predicción).

## 13. Predicciones del issue #173

Escritas por el orquestador antes de armar el kit y antes de que el implementador empiece. La fecha que vale
es la del commit que añade esta sección, el primero de la rama `issue-173-kit-interfaz-limpia`. El
implementador las ve: no son selladas (apartado 8.6).

El issue #173 arma un kit de envío sin el subagente ni las herramientas de grafo (no se envía) y añade a
`kaggle_submission verify` la comprobación de que la instrucción no nombra herramientas ausentes.

| # | Hecho | Probabilidad | Línea base y de dónde sale |
|---|---|---|---|
| 21 | El primer informe de `revisor-codigo` sobre el PR del #173 tiene el veredicto «cambios requeridos antes de fusionar» o «cambios requeridos» | 0,45 | 0,25: uno de cuatro primeros veredictos (PR #158, #161, #163 y #170; Wilson 0,05 a 0,70) |
| 22 | Algún informe de `revisor-codigo` muestra un kit con el que la comprobación nueva pasa aunque la instrucción ordena una herramienta que el agente no tiene (por ejemplo, nombrada sin comillas invertidas, en la instrucción de un subagente o en un archivo incluido) | 0,55 | 0,80: cuatro de las cinco revisiones de guiones que juzgan en los PR #161 y #170 hallaron un caso de «da por bueno lo que no lo es» (Wilson 0,38 a 0,96) |
| 23 | El primer ensayo local del kit K con el modelo falso no termina con una entrega (no compila, no arranca, o el guion del modelo falso llama a una herramienta retirada) | 0,35 | 0,5: sin historia contada para un kit nuevo; el ensayo del notebook de la iteración 08 falló en su primera corrida (1 de 1) |
| 24 | El `diff` entre el kit A y el K muestra algún cambio fuera de los tres decididos (lista de herramientas, subagente y su instrucción, una línea de la instrucción) | 0,10 | 0,5: sin historia contada |

Plazo: las cuatro vencen el 2026-10-23.

Clases de la sección 3 cubiertas: «da por bueno lo que no lo es» (22), «ensayo que no se parece al sistema
real» (23), «defecto de lógica propio» (21 y 24).

## 14. Desenlaces registrados el 2026-10-09 (issues #169 y #173)

Los registra el orquestador, que es también quien escribió las predicciones, a partir de los informes de
`revisor-codigo` y de `analista-datos`. Esos informes no están en GitHub: quedan resumidos en la bitácora del
caso y en el comentario de cierre de cada issue. Sigue sin existir el rol que marca (issue #165): esta tabla
no es una marca independiente.

| # | Probabilidad | Línea base | Desenlace | Qué lo prueba |
|---|---|---|---|---|
| 13 | 0,15 | 0,00 | Ocurrió | Primer informe de `revisor-codigo` sobre el PR #170: «cambios requeridos». No consta en ninguna fuente publicada; lo afirma el orquestador |
| 14 | 0,30 | 1,00 | Ocurrió | Tres informes de `revisor-codigo` antes de fusionar. El tercero («tercera lectura», «aprobado con observaciones no bloqueantes») consta en el comentario de cierre del issue #169; que hubo dos anteriores y que pidieron cambios no consta en ninguna fuente publicada: lo afirma el orquestador. PR #170 fusionado, `mergedAt` 2026-10-09T15:08:18Z |
| 15 | 0,35 | 0,5 | Ocurrió | Según el orquestador, el primer informe mostró un issue exento sin deberlo (uno cerrado como no planeado que tenía PR fusionados anteriores a su cierre) y el segundo, que la regla se anulaba al fusionar su propio PR. El cuerpo del PR #170 y la bitácora recogen esos dos casos como hallazgos del implementador. No consta en ninguna fuente publicada qué informe mostró cada uno |
| 16 | 0,85 | 0,86 | Ocurrió | `analista-datos`: las 12 comprobaciones de `f262573`, el primer commit con código del PR #170, en `success` |
| 21 | 0,45 | 0,25 | Ocurrió | Primer informe de `revisor-codigo` sobre el PR #175, en `923fe33`: «cambios requeridos antes de fusionar» |
| 22 | 0,55 | 0,80 | Ocurrió | Ese informe mostró diez kits que el compilador del organizador acepta y con los que la comprobación pasaba aunque la instrucción ordenaba una herramienta ausente |
| 23 | 0,35 | 0,5 | No ocurrió | El primer ensayo local del kit K terminó con entrega: seis herramientas ofrecidas, cinco llamadas, ninguna de las retiradas (informe del implementador; el revisor no lo repitió) |
| 24 | 0,10 | 0,5 | No ocurrió | El cuerpo del PR #175 describe la diferencia entre A y K en conteos y no muestra nada fuera de los tres cambios decididos; el orquestador afirma que `analista-datos` lo comprobó miembro a miembro en los dos zips (su informe no está publicado) |

Lectura, sin puntuación: de las ocho, seis ocurrieron. De las cinco que el orquestador puso por debajo de 0,40
(13, 14, 15, 23 y 24), ocurrieron la 13, la 14 y la 15. En la 13 la probabilidad (0,15) quedó más cerca del
desenlace que la línea base (0,00); en la 14 quedó más lejos que la línea base (1,00). Con catorce predicciones
cerradas en cuatro issues no se calcula nada: la convención del orquestador (apartado 8.4) pide cien en veinte.

En el PR #175 la primera revisión halló un caso de «da por bueno lo que no lo es» en la regla que juzga (el
YAML leído con expresiones regulares). Para el PR #170 no consta qué halló el primer informe. Dos casos no
permiten generalizar.

Siguen abiertas, con plazo al 2026-10-23: las predicciones 7 a 12 (issue #164, PR #176) y 17 a 20 (issue
#171, PR #174; sección 12, solo en la rama de ese PR).

## 15. Desenlaces registrados en la vuelta 43, 2026-10-09 y 10 UTC (issues #164 y #171)

Los marca el concilio de la vuelta 43 del caso Kaggle (auditor del método, con el recuento del analista de
datos), no el orquestador solo. Sigue sin existir el rol que marca (issue #165). Los informes de
`revisor-codigo` y de `analista-datos` sobre los PR #176 y #174 no están publicados: `gh pr view 176` devuelve
cero comentarios y cero reseñas. Criterio de esta sección, uno solo: una predicción sobre lo que dice un
informe no se marca si ese informe no está publicado, aunque la bitácora del caso lo resuma. Por eso nueve
de las diez quedan sin marcar. La sección 14 marcó con fuentes no publicadas y lo dijo en cada fila; aquí
no se sigue ese camino. La sección 12, que la 14 daba «solo en la rama de ese PR», ya está en `main`.

| # | Probabilidad | Línea base | Desenlace | Qué lo prueba |
|---|---|---|---|---|
| 7 | 0,30 | 0,00 | Sin marcar | La bitácora del caso (cierre de las 17:10 UTC del 2026-10-09) dice que la primera revisión del PR #176 pidió cambios; el informe no está publicado |
| 8 | 0,65 | 1,00 | Sin marcar | No consta cuántos informes hubo. El PR tiene dos commits de respuesta a revisión, lo que sugiere dos informes, no tres |
| 9 | 0,30 | 0,75 | Sin marcar | Informes no publicados. El documento del ensayo declara no alcanzables desde el notebook los casos de salida 0 que cita |
| 10 | 0,15 | 0,20 | Sin marcar | Informe del analista no publicado. Un recuento posterior (concilio 43) reproduce 145 filas, máximo 303,6 s, mediana 107 s y 250 filas con reloj; la diferencia con las «310 tareas» del coordinador sigue sin explicar |
| 11 | 0,80 | 0,86 | Sin marcar | No evaluable como está escrita: el primer commit con código del PR #176 (`2e57468`) no tuvo ninguna ejecución de CI. La primera CI con código (`b319586`) terminó con una comprobación fallida y once en verde (recuento del analista en el concilio 43, comprobado por el revisor de documentos) |
| 12 | 0,80 | 0,5 | Ocurrió | El documento del ensayo dice que el cuelgue solo se logró plantando el ciclo a mano; la carrera natural salió en la sonda, fuera del arnés |
| 17 | 0,55 | 0,25 | Sin marcar | El veredicto del primer informe sobre el PR #174 no consta en ninguna fuente; la bitácora solo recoge el de la segunda revisión («aprobado con observaciones no bloqueantes») |
| 18 | 0,60 | 1,00 | Sin marcar | Solo consta una segunda revisión |
| 19 | 0,45 | 0,5 | Sin marcar | El informe del analista sobre el PR #174 no está publicado. Lo que sí consta: un recuento independiente del concilio 43 reproduce los totales de la cuenta por llamada (4 086 contadas, 4 444 en traza, 211 rechazadas), y el concilio leyó que las cifras que no se sostuvieron estaban en el registro de hallazgos, que no es la cuenta por llamada. Eso dice que las cifras se reproducen, no qué marcó el analista |
| 20 | 0,40 | 0,80 | Sin marcar | Informes no publicados |

Corrección: el cierre del 2026-10-09 en la bitácora del caso decía «17, 18 y 20 ocurrieron». Esa frase la
escribió el orquestador sin fuente publicada; el auditor del método la señaló y las tres quedan sin marcar.

Lectura, sin puntuación: de diez predicciones, una se pudo marcar (la 12, que depende de un documento
versionado) y nueve no. Ocho, por la misma causa: el informe de revisión vive en la sesión del orquestador y
no en el PR. La otra, la 11, porque el hecho que predecía no llegó a existir. Mientras los informes no se
publiquen como comentario del PR, las predicciones sobre lo que dice un informe no se pueden cerrar; desde
el PR #183 se publican. Plazo de las nueve que siguen abiertas: 2026-10-23.
