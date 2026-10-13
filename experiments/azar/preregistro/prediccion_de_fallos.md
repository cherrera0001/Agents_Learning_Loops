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

## 15. Desenlaces registrados en la vuelta 43, 2026-10-09 (issues #164 y #171)

Los marca el concilio de la vuelta 43 del caso Kaggle (auditor del método, con el recuento del analista de
datos), no el orquestador solo. Sigue sin existir el rol que marca (issue #165). Los informes de
`revisor-codigo` y de `analista-datos` sobre los PR #176 y #174 no están publicados: `gh pr view 176` devuelve
cero comentarios y cero reseñas. Criterio de esta sección, uno solo: una predicción sobre lo que dice un
informe no se marca si ese informe no está publicado, aunque la bitácora del caso lo resuma. Por eso ocho
de las diez quedan sin marcar; una novena, la 11, por otra razón que su fila dice. La sección 14 marcó con
fuentes no publicadas y lo dijo en cada fila; aquí
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
el PR #183 se publican. Plazo de las ocho que siguen abiertas: 2026-10-23. La 11 no tiene plazo que la
cierre: su hecho no existió.

## 16. Predicciones del issue #186

**Nota de desviación (vale para las secciones 16, 17 y 18).** Estas diez predicciones (38 a 47) se escribieron
el 2026-10-12 como comentario del issue correspondiente, antes de lanzar al implementador, y no en este
archivo. La sección 6 pide fecha y commit; aquí no hay commit anterior al trabajo, y las secciones 10 a 13
decían «la fecha que vale es la del commit que añade esta sección». Para estas, la fecha que vale es la del
comentario, y el commit que las trae al archivo es el de este PR, posterior a los desenlaces. Lo que prueba
que son anteriores al trabajo (medido con `gh`):

| Issue | Comentario con las predicciones | Creado (UTC) | Editado después | Primer commit del PR | Fecha del primer commit (UTC) |
|---|---|---|---|---|---|
| #186 | [issuecomment-6116755436](https://github.com/cherrera0001/Agents_Learning_Loops/issues/186#issuecomment-6116755436) | 2026-10-12 02:38:31 | no (`updated_at` igual a `created_at`) | PR #191, `7d07ddd` | 2026-10-12 02:52:41 |
| #167 | [issuecomment-6116755654](https://github.com/cherrera0001/Agents_Learning_Loops/issues/167#issuecomment-6116755654) | 2026-10-12 02:38:32 | no | PR #189, `e150177` | 2026-10-12 02:50:07 |
| #187 | [issuecomment-6117136102](https://github.com/cherrera0001/Agents_Learning_Loops/issues/187#issuecomment-6117136102) | 2026-10-12 03:20:19 | no | PR #192, `6f075e3` | 2026-10-12 03:36:05 |

Que el comentario sea anterior al primer commit del PR no prueba que el implementador no los viera: eso no
consta. Otras tres desviaciones, también declaradas y no corregidas después:

- **Líneas base «sin contar».** La sección 8.1 dice que una línea base la cuenta un guion antes de predecir.
  La orden que las cuenta (`python -m scripts.devlog base-rates`, issue #167) se fusionó en esta misma vuelta,
  con el PR #189 a las 03:20:07 UTC, después de sellar las predicciones 38 a 44. Por eso seis de esas siete
  (todas menos la 41, que trae una cuenta a mano) dicen «sin contar». La 45 y la 47 traen una cifra «de esta
  tanda», contada a mano sobre cinco o cuatro PR, no con la orden.
- **Clases omitidas sin decirlo.** La sección 8.4 pide que quien predice diga qué clases de la sección 3 dejó
  fuera y por qué. Los comentarios no lo dicen y no se añade ahora, porque sería escribir después del hecho.
- **Plazo.** Ninguna de las diez fija una fecha. Por la regla de 8.4, una predicción sin plazo vence a los 30
  días: la 41, la única abierta, vence el 2026-11-11 (30 días desde el 2026-10-12).

El texto que sigue es el del comentario del issue, copiado tal cual.

> **Predicciones fechadas antes de empezar (orquestador, 2026-10-12 UTC), según `experiments/azar/preregistro/prediccion_de_fallos.md`.** Selladas aquí antes de lanzar al implementador; el desenlace se marca al cerrar. Línea base: «sin contar» donde no hay recuento (#167 es lo que permitirá contarla).
>
> | # | Fallo que se predice | Probabilidad | Línea base | Cómo se marca |
> |---|---|---|---|---|
> | 38 | La primera revisión de código pide cambios antes de fusionar | 0,70 | sin contar (PR #184: sí; PR #185: no) | veredicto del `revisor-codigo` sobre la primera cabeza |
> | 39 | El revisor encuentra al menos una orden legítima que el gancho rechaza | 0,50 | sin contar | caso reproducible citado en la revisión |
> | 40 | La CI sale en rojo en el primer push | 0,30 | sin contar | `gh pr checks` sobre la primera cabeza |
> | 41 | En los 15 episodios siguientes a la fusión aparece un paso fallido por heredoc | 0,35 | 10 de 73 episodios (0,14 por episodio; 5 tras la regla escrita) | pasos fallidos de los episodios |
>
> Decisión del concilio que origina el issue: dictamen del auditor del método del 2026-10-12 (candidatas C4 y C6). Condición de reversión: 2 o más pasos fallidos por heredoc en 15 episodios, o más de 1 orden legítima frenada: el gancho pasa a solo contar.

El issue #186 añade una guarda previa a una orden de Bash (`scripts/guarda_previa.py`) que rechaza heredocs que
alimentan un intérprete o escriben un archivo fuente, y escrituras de `gh` sin `GH_TOKEN` en la orden.

## 17. Predicciones del issue #167

Comentario del issue, copiado tal cual (enlace y hora en la tabla de la sección 16).

> **Predicciones fechadas antes de empezar (orquestador, 2026-10-12 UTC), según `experiments/azar/preregistro/prediccion_de_fallos.md`.** Selladas aquí antes de lanzar al implementador; el desenlace se marca al cerrar.
>
> | # | Fallo que se predice | Probabilidad | Línea base | Cómo se marca |
> |---|---|---|---|---|
> | 42 | La primera revisión de código pide cambios antes de fusionar | 0,50 | sin contar | veredicto del `revisor-codigo` sobre la primera cabeza |
> | 43 | El recuento de la orden difiere del recuento a mano del analista de datos para el PR #163 en al menos una celda | 0,45 | sin contar | comparación publicada en el PR |
> | 44 | Más del 30 % de los pasos fallidos queda sin clase con la clasificación por palabras | 0,55 | sin contar | salida de la orden sobre los episodios reales |
>
> Contexto del 2026-10-12: una medición exploratoria sobre 61 episodios (un corpus, episodios dependientes, código de hoy) dio que la tasa base de fallo por acción anticipa qué acción falla mejor que el ranking de `recall` (AUC medio 0,646 frente a 0,550; diferencia pareada −0,095, IC −0,165 a −0,022; prueba de signos p = 0,076). El concilio decidió hacer este issue **tal como está**: la orden solo cuenta y añade; no sustituye el ranking ni entra en la skill de recall. Condición escrita por el auditor: si en los 20 episodios siguientes la tasa base no supera a `recall`, no entra en la skill.

El issue #167 añade `python -m scripts.devlog base-rates`. El #167 pedía además que las predicciones estuvieran
en este archivo: no lo estaban cuando se cerró, y por eso su cierre quedó sin confirmar. Este PR es esa parte.

## 18. Predicciones del issue #187

Comentario del issue, copiado tal cual (enlace y hora en la tabla de la sección 16).

> **Predicciones fechadas antes de empezar (orquestador, 2026-10-12 UTC).** Selladas antes de lanzar al implementador; el desenlace se marca al cerrar.
>
> | # | Fallo que se predice | Probabilidad | Línea base (`devlog base-rates`, 74 episodios) | Cómo se marca |
> |---|---|---|---|---|
> | 45 | La primera revisión de código pide cambios antes de fusionar | 0,55 | hoy, 3 de 5 primeras revisiones de esta tanda pidieron cambios (#184, #190, #191 sí; #185, #189 no) | veredicto del `revisor-codigo` sobre la primera cabeza |
> | 46 | El filtro retira alguna lección cuyo remedio es otra acción (el error que revierte el cambio) | 0,15 | sin contar | réplica sobre los episodios reales publicada en el PR |
> | 47 | El PR entra en conflicto con `main` por `CHANGELOG.md` antes de fusionarse | 0,60 | hoy, 3 de 4 PR en paralelo chocaron ahí | `gh pr view --json mergeable` |
>
> Orden de fusión decidido por el concilio: después del #186 (PR #191), porque este filtro quita el único recordatorio del heredoc que hoy llega, por accidente, a través de una lección degenerada.

El issue #187 hace que `devlog recall` omita las lecciones «fallback» cuyo remedio es la misma acción que
falló. Nota sobre el encabezado de la tabla: dice «`devlog base-rates`, 74 episodios», pero las cifras de las
filas 45 y 47 son recuentos a mano sobre los PR de la tanda; la orden cuenta pasos por acción, no veredictos ni
conflictos.

## 19. Desenlaces registrados el 2026-10-12 (issues #186, #167 y #187)

Los registra la sesión que escribe este PR, a partir de lo que consta en los PR fusionados. Sigue sin existir
el rol que marca (issue #165): esta tabla no es una marca independiente. A diferencia de las secciones 14 y 15,
el resumen de cada informe de revisión está publicado como comentario del PR; pero ese comentario lo escribió el
orquestador («resumen fiel de los informes», dice él mismo), no el revisor, y el informe íntegro no está
publicado. Se marca con esos comentarios y se dice que son resúmenes. Fusiones, medidas con `gh pr view`:
PR #189 (`mergedAt` 2026-10-12T03:20:07Z), PR #191 (2026-10-12T04:18:07Z) y PR #192 (2026-10-12T04:35:21Z).

| # | Probabilidad | Línea base | Desenlace | Qué lo prueba |
|---|---|---|---|---|
| 38 | 0,70 | sin contar | Ocurrió | PR #191, primer comentario de revisión (2026-10-12 03:19 UTC): `revisor-codigo` sobre `7d07ddd`, «cambios requeridos»; el comentario de respuesta (03:32 UTC) habla de seis bloqueantes |
| 39 | 0,50 | sin contar | Ocurrió | Mismo comentario: el gancho frenaba órdenes legítimas de uso diario; el comentario del 04:18 UTC cuenta, en la primera revisión, 8 falsos rechazos de 46 órdenes de heredoc y 7 de 36 de cuenta, y 0 de 46 y 1 de 36 tras los cambios |
| 40 | 0,30 | sin contar | No ocurrió | Mismo primer comentario: 12 de 12 comprobaciones sobre `7d07ddd` |
| 41 | 0,35 | 10 de 73 episodios | **Abierta** | Se marca tras el episodio 15 posterior a la fusión del PR #191 (`ddc9e88`, 2026-10-12T04:18:07Z). Vence el 2026-11-11 si antes no se llega a 15 episodios |
| 42 | 0,50 | sin contar | No ocurrió | [PR #189, comentario de las 03:01 UTC](https://github.com/cherrera0001/Agents_Learning_Loops/pull/189#issuecomment-6116964635): primera revisión sobre `e150177`, «apto con observaciones», sin bloqueantes |
| 43 | 0,45 | sin contar | Ocurrió, con una salvedad | Mismo comentario, recuento del analista de datos: la orden coincide celda a celda con el recuento actual del analista (29 acciones, 73 episodios, 0 diferencias). Lo que difiere es contra el recuento del pre-registro: 203 pasos fallidos en el pre-registro (sección 8.5) frente a 214 en el recuento del analista sobre 65 episodios, y 68 frente a 81 sin clase. El analista dice que los 11 de diferencia «no son un error de conteo» sino otro conjunto de 65 episodios; los «68 sin clase» sí difieren porque entonces había siete clases. Se marca «ocurrió» porque la predicción decía «difiere en al menos una celda», no por qué difiere |
| 44 | 0,55 | sin contar | No ocurrió | Mismo comentario: 17,1 % sin clase (44 de 258 pasos fallidos, por la orden sobre los episodios reales). Es una cifra dentro de la muestra: el analista estima 20 a 30 % para episodios nuevos, y 30,1 % con solo los patrones anteriores al episodio 52 |
| 45 | 0,55 | 3 de 5 (a mano) | No ocurrió | PR #192, comentario de las 03:49 UTC: primera revisión sobre `6f075e3`, «apto con observaciones», sin bloqueantes |
| 46 | 0,15 | sin contar | No ocurrió | Mismo comentario: réplica propia del revisor sobre 75 episodios (`a32357e`); el resumen del analista dice que no empeora nada. La cifra «0 lecciones de otra acción retiradas» consta en `learning/README.md` (réplica del implementador sobre 65 episodios) |
| 47 | 0,60 | 3 de 4 (a mano) | No ocurrió | PR #192, comentario de las 04:35 UTC: `main` (`ddc9e88`) fusionado en la rama sin conflicto (`1409343`), 12 de 12 comprobaciones |

Cuenta, sin puntuación: de las diez, nueve tienen desenlace y una (la 41) sigue abierta. De las nueve, tres
ocurrieron (38, 39 y 43) y seis no. La suma de las probabilidades de las nueve es 4,45, así que se esperaban
unas 4,5 ocurrencias y hubo 3. Criterio de las predicciones 38, 42 y 45: «pide cambios» se leyó como el veredicto escrito «cambios
requeridos»; «apto con observaciones» cuenta como no ocurrido, aunque después se corrigieran observaciones.
Con nueve predicciones en tres issues no se puede hablar de calibración: la
convención de la sección 8.4 pide cien en veinte, y 4,45 contra 3 es un recuento, no una lectura.

Qué se midió y qué no: lo medido es el desenlace de cada hecho en los PR citados. No se midió si predecir
cambió el desenlace (sección 8.6), ni si la línea base habría acertado más: en siete de las diez dice «sin
contar» porque la orden que las cuenta se fusionó en esta misma vuelta. Desde ahora la tabla por acción de
`python -m scripts.devlog base-rates` sirve como línea base (con `--hasta N` para un issue `N`); la tabla por
clase no, hasta validarla con un segundo lector, como dice su propia salida.

Siguen abiertas, con plazo al 2026-10-23, las ocho de las secciones 10 a 12 que la sección 15 dejó sin marcar
(7, 8, 9, 10, 17, 18, 19 y 20); la 11 queda sin plazo, porque su hecho no existió. La 41 vence el 2026-11-11.

## 20. Predicciones y definiciones del concilio 46 (issue #182), fijadas antes de la corrida de 60 tareas

**Qué se predice.** Una corrida de 60 tareas del sorteo con el kit `A0` sin razonar, sobre las ruedas del
arnés publicadas el 2026-10-12 a las 19:51 UTC, y su repetición con el mismo zip y las mismas ruedas. Al
escribir esto no existe ninguna de las dos: no se ha subido nada.

**Quién las escribió.** El analista de datos y el forense del arnés, cada uno en su informe, los dos fechados
el 2026-10-12 a las 21:19 UTC. No las escribió el orquestador ni quien arma la corrida. El orquestador solo
las copió aquí y numeró las del forense, que venían como F1 a F8. Los originales están en el expediente sin
versionar del concilio (`.scratch/concilio_memoria/fase2/concilio_46/analista/definiciones_y_predicciones.md`
y `forense/paso2_ruedas.md`).

**Hueco de numeración.** Las predicciones 48 a 51 se escribieron en la bitácora del caso el 2026-10-12, antes
del sondeo de 12 tareas, y no llegaron a este archivo. No se copian aquí porque sus desenlaces ya se conocen:
añadirlas ahora sería escribirlas después. Queda dicho que existen y que este archivo no las contiene.

### 20.1 Definiciones (analista de datos, copiadas tal cual)

> **Tarea válida.** Tiene tarea_fin; ninguna de sus peticiones pide razonar ni carece del dato; no está entre las colgadas del cierre. Adopto la del auditor con una precisión: la tarea con rechazo por contexto (peticion_fin con motivo error y ContextWindowExceeded) es válida y se marca con_rechazo; el acierto se informa con y sin ellas. **Corrida válida:** termina en cierre, el sha256 de las cuatro ruedas es el esperado y hay al menos 55 tareas válidas.
>
> **Corte.** Dos reglas, porque forense contó 0 y QA 3: corte duro = agente_fin con entrego falso o error no nulo (clases: tiempo, turnos, contexto, otro; s2: 0, s1: 7 de tiempo). Tope de llamadas = llamadas_herramientas >= 39 de 40 (s2: 3; s1: 2).
>
> **Discordante.** Entre dos pasadas con el mismo zip y ruedas: denominador, tareas válidas en las dos; numerador, las de ellas con resuelta distinto. No se reponen tareas.
>
> **Unidad.** Todo costo y tope va en horas de cuota = segundos de sesión del log de Kaggle / 3600 x 2,01. El reloj se nombra reloj. El tope de 9 600 s son 5,4 h de cuota.

### 20.2 La puerta para comparar después con el kit que razona (analista de datos, copiada tal cual)

> Con n válidas en ambas y d discordantes: **pasa** si d <= floor(0,20 n) (n = 60: 12 o menos; n = 55 a 59: 11 o menos). **No se sabe** si d llega hasta el último valor con límite inferior del IC95 exacto <= 0,20 (n = 60: 13 a 18; n = 57 a 59: 12 a 18; n = 55 o 56: 12 a 17). **No pasa** por encima (n = 60: 19 o más). Con n < 55 no se lee. En «no se sabe» no se corre el paso 4 ni se declara alto el ruido.

Es la regla del concilio 45 («solo si la discordancia es 20 % o menos») escrita como condición sobre el
conteo. `s1` y `s2` son las dos corridas de 12 tareas del 2026-10-12, con las ruedas del 2026-10-09.

### 20.3 Predicciones del analista de datos (copiadas tal cual)

| # | Predicción y criterio que la marca | Probabilidad | Línea base |
|---|---|---|---|
| 52 | Pasada 1: media de segundos de tarea_fin sobre las válidas entre 80 y 135 | 0,80 | s2: 101,0 en 12 |
| 53 | Pasada 1: media sobre 150 s | 0,07 | máximo de s2: 157,6 |
| 54 | Pasada 1: resueltas entre 7 y 18 de 60 | 0,80 | s2: 3 de 12 |
| 55 | Pasada 1: en las 12 tareas de s2, resueltas entre 2 y 4 | 0,65 | s2: 3; s1: 4 |
| 56 | Pasada 1: al menos una tarea con_rechazo; y de 1 a 9 | 0,85; 0,80 | s2: 1 de 12 |
| 57 | Pasada 1: tareas_colgadas > 0 en el cierre | 0,08 | 0 de 24 |
| 58 | Pasada 1: al menos un corte duro | 0,30 | s2: 0 de 12 |
| 59 | Pasada 1: tope de llamadas en 7 a 24 tareas | 0,80 | s2: 3 de 12 |
| 60 | Pasada 1: cuota entre 3,0 y 4,6 h; la sesión cabe en 9 600 s | 0,80; 0,92 | s2: 0,98 h por 12 |
| 61 | Repetición: discordancia entre 0,08 y 0,28 | 0,80 | sin dato propio |
| 62 | Repetición: la puerta pasa (12 o menos de 60) | 0,60 | ninguna |
| 63 | Repetición: diferencia absoluta de resueltas entre pasadas <= 3 | 0,70 | ninguna |
| 64 | Cambia el sha256 de alguna rueda entre las dos subidas | 0,30 | dos cambios en el caso |
| 65 | Al menos un 500 de SaveKernel antes de cada subida exitosa | 0,45 | 2 en 3 intentos |

El costo de la 60 se lee de `uvx kaggle quota`, con dos decimales, antes y después. Las predicciones 56 y 60
llevan dos afirmaciones cada una, con su probabilidad: se marcan por separado.

### 20.4 Predicciones del forense del arnés (copiadas tal cual; la numeración 66 a 73 es de este archivo)

| # | Predicción | Probabilidad | Ocurre si |
|---|---|---|---|
| 66 | Al menos un rechazo por ventana de contexto | 0,85 | algún `peticion_fin` con `error` = `ContextWindowExceededError` |
| 67 | Tres o más rechazos | 0,55 | ídem, 3 o más |
| 68 | Alguna tarea colgada | 0,07 | `tareas_colgadas` > 0 en `cierre`, o evento `corte` |
| 69 | Algún agente cortado por tiempo | 0,35 | algún `agente_fin` con «exceeded session timeout» |
| 70 | Diez o más tareas con llamadas agotadas | 0,80 | `tarea_fin` con clase `llamadas_agotadas_*`, 10 o más |
| 71 | El primer intento de subida falla | 0,25 | la primera orden `kernels push` no devuelve «successfully pushed» |
| 72 | Alguna verificación dura 60 s o más | 0,05 | `tarea_fin` − `agente_fin` ≥ 60 s en alguna tarea |
| 73 | Sesión completa | 0,85 | registro con `cierre` y 60 `tarea_fin` |

Las del forense se marcan con el registro de la primera corrida de 60. Las dos listas se escribieron sin que
un rol viera la del otro, y varias hablan del mismo hecho con criterios distintos (56 y 66; 57 y 68; 59 y 70;
65 y 71): se marcan todas, cada una con su criterio.

### 20.5 Precisiones de los autores, tras la revisión del PR #200 (copiadas tal cual)

Un revisor independiente señaló criterios que no se podían aplicar sin juicio. Lo copiado en 20.1 a 20.4 no se
editó. Cada autor precisó lo suyo en una nota fechada el 2026-10-12 a las 21:24 UTC, todavía sin ningún dato
de la corrida, y sin cambiar ninguna probabilidad ni umbral. Donde una nota y una cita difieren, manda la nota.
Los nombres de campo son los de `registro_iteracion_08_s2.jsonl`.

**Analista de datos** (definiciones, puerta y predicciones 52 a 65):

> **P2, «corte».** Son tres objetos, no una definición doble. Corte duro (mi 58): agente_fin con entrego falso o error no nulo. Tope de llamadas (mi 59): tarea_fin.llamadas_herramientas >= 39. El evento corte del registro (scripts/kaggle_registro.py:457 y 567, con cortado_por) es otro, del notebook, y mi 57 usa cierre.tareas_colgadas. En s2: 0 eventos corte, 0 corte duro.
>
> **P3, 65.** No está en el registro. Se marca contra el texto guardado de la salida de cada uvx kaggle kernels push (bitácora del caso o archivo de la corrida). Ocurre si en cada una de las dos subidas hay al menos un intento con «500» y «SaveKernel» antes del primer «successfully pushed» de esa subida. Sin salida guardada o sin repetición: no evaluable. Es la lectura literal de «cada».
>
> **P5.** sha256 esperados (sha256_ruedas_1951.txt, recontados): adk_eval_core e614e1b2fe8d886a634871e4c57f9887e1cc66e8c27300f8503a43c6e3ca82f3; adk_submission f156f0bd84580ccb9334726d114d7a5481f16d3a6e2887cc4d276ced0ef8d99d; google_adk 1a2f6868c509e3151fb0de3575a7d18b45c338be86f420924dad74e7193631a0; swegemma 9ad876581f3acde8ec3c369858f0834e2b9f41a3cffce3ca42f09cb090aea9d3. «Las 12 de s2» (55): las 12 con tarea_inicio en registro_iteracion_08_s2.jsonl, campo tarea; no las listo (regla de no dar identificadores).
>
> **P6, puerta.** No pasa por encima del tramo «no se sabe» (puerta.py, copia puerta.txt): n = 55 o 56, d >= 18; n = 57 a 59, d >= 19; n = 60, d >= 19.
>
> **P7.** Todo conteo absoluto (54, 56, 59, 63) es sobre las tareas válidas, sin reescalar; con menos de 55 válidas en la pasada, no evaluable. La 62 usa la puerta: d <= floor(0,20 n), es decir 12 con n = 60 y 11 con 55 a 59.
>
> **P8.** El factor 2,01 es medido, no supuesto: s1, 1,71 h / 3 064 s (2,009); s2, 0,99 h / 1 770,5 s (2,013, lectura del orquestador). La fuente única para marcar la 60 es la diferencia de horas usadas de uvx kaggle quota, con dos decimales, leída justo antes del push y tras el estado complete; la fórmula solo pronostica. Si corre otra sesión de GPU entre las dos lecturas: no evaluable. «Cabe en 9 600 s»: cierre.sesion_s <= 9600.
>
> **Menores, 56.** Se divide: 56a, al menos una tarea con rechazo (0,85); 56b, el número de tareas (no de peticiones) con rechazo está entre 1 y 9 (0,80). Con_rechazo no es campo: tarea con alguna peticion_fin con motivo == error y la cadena ContextWindowExceeded contenida en error o en detalle. No uso igualdad literal.

**Forense del arnés** (predicciones 66 a 73):

> - **66 y 67 (punto 1): no se sostiene.** El campo que nombré existe con igualdad literal: `s2`, línea 1478 del registro, `peticion_fin` con `"motivo": "error"` y `"error": "ContextWindowExceededError"`. La línea 175 del preregistro describe otro objeto, el error de la tarea. Regla: número de eventos `peticion_fin` cuyo campo `error` es exactamente esa cadena; 66 ocurre con 1 o más, 67 con 3 o más. Cuenta peticiones, no tareas.
> - **68 (punto 2): mal planteada, se evalúa literal.** Ocurre si `cierre.tareas_colgadas` > 0 (celda 8, línea 924) o si hay algún evento con `evento` = `corte`, con cualquier `cortado_por`. Eso incluye el corte de sesión `corte('tareas')` (celda 10, líneas 397 a 399), que no es una tarea colgada: el criterio es más ancho que el título, y no lo estrecho porque me favorecería. No es el «corte» de las definiciones del analista (`agente_fin`). Sin `cierre` y sin evento `corte`: no ocurrió.
> - **70 (punto 4): se sostiene para `origin/main`, no para el registro.** La clase la arma el notebook por concatenación (celda 10, líneas 85 y 86) y está en `s2` (3 filas). Regla: `tarea_fin` cuyo `clase` empieza por `llamadas_agotadas`; ocurre con 10 o más. Aviso: salta con 39 llamadas o más (tope menos 1) y se evalúa antes que el corte por tiempo.
> - **71 (punto 3):** no está en el registro. Se marca contra la entrada de la subida en `BITACORA_MEJORA.md`: la salida literal de la primera orden `kernels push`. Si la bitácora no copia esa salida, **no evaluable**.
> - **72:** `tarea_fin.hora` − `agente_fin.hora` de la misma `tarea`, 60 s o más en alguna. Línea base: máximo 4,0 s en `s2` y 3,9 s en `s1` (`paso2_ordenes.txt`, orden 8). Tareas sin `agente_fin`: no cuentan.
> - **73:** exactamente un evento `cierre` y 60 eventos `tarea_fin`. No es el estado «completa» de la herramienta (`kaggle_registro.py:649`), que además exige ausencia de cortes.

**Segunda nota del analista de datos** (2026-10-12 21:31 UTC, tras la segunda revisión; copiada tal cual):

> **52 y 53.** Segundos = el campo segundos del evento tarea_fin del registro (en s2, 136,9 para la primera tarea); no segundos_arnes ni segundos_reloj del json por tarea. Media aritmética sobre las tareas válidas.
>
> **55.** Se cuentan las resueltas solo entre las de las 12 que sean válidas en la corrida nueva; el umbral 2 a 4 no se reescala. Si alguna de las 12 no es válida: no evaluable.
>
> **61.** Discordancia = d / n, con n = tareas válidas en las dos pasadas y d = las de ellas con resuelta distinto; n < 55: no evaluable.
>
> **64.** Se lee de versiones_arnes_iteracion_08_*.json de la salida de cada subida, campo sha256 de cada rueda del arnés (lo escribe la guarda del #182). El de s2 solo trae tamaños: si el archivo no trae sha256, no evaluable.
>
> **60, línea base.** Vale 0,99 h (2,77 − 1,78, lectura de uvx kaggle quota); el 0,98 era el cálculo previo (reloj x 2,01). La línea base no es criterio de marca.

**Segunda nota del forense del arnés** (2026-10-12 21:26 UTC; copiada tal cual):

> **69:** ocurre si algún evento `agente_fin` tiene en su campo `error` (cadena) el texto `exceeded session timeout`, sin distinguir mayúsculas. Ejemplo: registro de `s1`, línea 83, `"error": "Agent exceeded session timeout (4.0 min)"`; en `s1` son 7 eventos, todos en ese campo. `error` nulo o ausente: no cuenta. Probabilidad y umbral, sin cambio.

**Lo que queda dicho por el orquestador, no por los autores.** La frase de 20.4 «las del forense se marcan con
el registro» vale para todas menos la 71, que se marca contra la bitácora del caso. La 56 y la 66 hablan del mismo hecho con
reglas distintas (una cuenta tareas y busca la cadena contenida; la otra cuenta peticiones con igualdad
exacta): no se unifican, cada una se marca con la suya. Para que la 65 y la 71 sean evaluables, la bitácora
del caso tiene que copiar la salida literal de cada orden `kernels push`. El guion `puerta.py` del analista no
está en el repositorio: las cifras de la puerta se rehacen con la regla escrita en 20.2 y en la nota P6 (el
revisor del PR las recalculó por su cuenta y coinciden). Del original del analista quedó fuera de 20.2 una
frase, «Retiro mi "IC95 bajo 25 %"», que se refiere a una versión anterior de la puerta que nunca se fijó.

### 20.6 Qué no cubren

Ninguna predicción dice cuál kit acierta más: esta corrida no compara kits. Ninguna cubre la nota del envío.
Las probabilidades son juicio de cada rol; solo las que citan una línea base la tienen medida, y esa línea
base son 12 tareas.

## 21. Concilio 47 (issue #182): el «cerrojo», la edición temprana y los enunciados sin contenido

**Qué se predice.** Lo mismo que la sección 20: la corrida de 60 tareas con el kit `A0` sin razonar sobre las
ruedas del 2026-10-12 19:51 UTC, y su repetición. Al escribir esto no existe ninguna de las dos. La sección 20
no se toca.

**Quién escribió cada parte.** La definición, el auditor del método. Las predicciones, el analista de datos y
QA de trayectorias, cada uno por su cuenta, el 2026-10-13 antes de las 01:00 UTC. El orquestador las copió
aquí y les dio número: las dos listas venían numeradas desde la 74; las del analista quedan 74 a 77 y las de
QA pasan a 78 a 83. Originales, sin versionar: `.scratch/concilio_memoria/fase2/concilio_47/auditor/
definicion_cerrojo_2026-10-13.txt`, `analista/predicciones_21.md` y `qa/predicciones_21.md`.

**Un hecho que cambia la lectura de la sección 20.** De las 129 tareas públicas, 24 tienen un enunciado de
menos de 100 caracteres (20 de 48 en `rich`, 3 de 67 en `fastapi`, 1 de 13 en `requests`): un título de PR sin
descripción. De las 60 del sorteo, 14. Lo contaron tres lectores por separado con la misma regla sobre
`experiments/gemma_developer_agent/data/tasks.jsonl`. El corte de 100 se fijó antes de probar otros; con 150 y
200 salen 18 y 20 de 60.

### 21.1 Definición del auditor (copiada tal cual, sin tildes como en el original)

> D1. Lectura mal formada (LMF): llamada a read_file cuyos argumentos no cumplen la firma del arnes (swegemma/tools/workspace.py:88-93: filepath str, start_line int|None, end_line int|None). Es LMF si: (a) trae alguna clave distinta de filepath, start_line, end_line; o (b) falta filepath o no es cadena; o (c) filepath contiene comilla doble, coma, llave, o las palabras start_line / end_line; o (d) start_line o end_line presentes y no convertibles a entero. Una lectura bien formada (LBF) es toda otra llamada a read_file.
>
> D2. Sesion atrapada: tiene al menos una racha de 3 o mas llamadas CONSECUTIVAS a herramientas que son todas LMF. (Criterio primario. Un cerrojo es una racha, no un total.) Libres: todas las demas, hayan o no tenido alguna LMF.
>
> D3. Tasa de repeticion: entre las llamadas LMF que tienen llamada siguiente en la sesion, fraccion cuya siguiente es tambien LMF. Contraste: lo mismo tras una LBF. Secundaria: fraccion cuya siguiente es identica (mismos argumentos).
>
> D4. Resultado: `resolved` de task_results.jsonl (o el campo equivalente del resumen de la corrida si no hay jsonl).
>
> D5. Prueba: Fisher exacta de dos colas, atrapadas frente a libres. Tamano de efecto: diferencia de proporciones con intervalo de Newcombe al 95 % y razon de momios con correccion de 0,5. Alfa 0,05. Un solo contraste primario. Las sesiones repiten tareas entre corridas: se informa tambien por corrida y la cuenta de tareas distintas.
>
> D6. Sensibilidades (se informan, no deciden): total de LMF >=1, >=3, >=5.
>
> D7. Edicion temprana: N = 12 (viene de la instruccion de los kits publicos, no de nuestros datos). Primera edicion = indice (desde 1) de la primera llamada edit_file o write_file cuyo filepath no empieza por /tmp y cuyo nombre de archivo no empieza por test_ ni esta bajo tests/ o test/. Temprana: indice <= 12. Tardia o nunca: el resto. Como resolver exige editar, se informa tambien restringido a las sesiones que editaron alguna vez.
>
> D8. Lo que refuta «el cerrojo baja la tasa de resueltas»: en la muestra grande, diferencia con intervalo que incluye el cero, o tasa de resueltas de las atrapadas >= la de las libres. Lo que lo sostiene: p < 0,05 e intervalo entero bajo cero. En ningun caso se lee como causa: es observacional y la sesion atrapada puede ser la tarea dificil.

Con esta definición, antes de la corrida: 6 atrapadas de 24 en `s1` y `s2` (0 de 6 resueltas frente a 7 de 18;
p = 0,13) y 22 de 145 en las iteraciones 03 a 07 (2 de 22 frente a 37 de 123; p = 0,065). En el kit que razona,
0 atrapadas de 29. El umbral de la racha lo eligió el auditor y él mismo lo llama arbitrario.

### 21.2 Predicciones del analista de datos (copiadas tal cual)

> «Atrapada» = definición del auditor (racha de 3 o más `read_file` mal formados seguidos). Campos de `tarea_fin`: `tarea`, `resuelta`, `clase`. **La racha no está en el registro**: se cuenta en `traces/trace_<tarea>.json` del zip crudo. Solo con el registro, 74, 75 y 77 no son evaluables.

| N.º | Afirmación (60 tareas, A0, ruedas 19:51; cada pasada) | Prob. | Línea base | Criterio |
|---|---|---|---|---|
| 74 | Atrapadas entre 6 y 19 | 0,80 | 6/24 en s1+s2; 22/145; 0/29 razonando | racha >=3 en traza |
| 75 | Resueltas entre atrapadas <= 20 %; entre libres 20 a 40 % | 0,70 | 0/6 y 7/18; 2/22 y 37/123 | `resuelta` por grupo de 74; vale con >=5 atrapadas |
| 76 | Con `len(problem_statement)<100` en `tasks.jsonl`: 14 de 60; resueltas entre ellas <=3 (0,80); entre las otras 46, de 8 a 20 (0,75) | 0,99 la cuenta | s1+s2: 0/8 sesiones cortas, 7/16 el resto | regla y `resuelta` |
| 77 | Repetición: al menos la mitad de las atrapadas de la pasada 1 lo son en la 2 | 0,65 | sin dato | intersección de tareas |

> Con otros cortes (150, 200) salen 18 y 20; no probé otros antes de fijar 100. Las 12 de s1/s2 tienen 4 cortas con <100, no 5.
>
> Ninguna de 52 a 65 cambia de sentido. Nota a la 54: su base 3/12 incluye 4 cortas sin resolver; el techo es 46, y más de 14 resueltas se hace menos probable.

### 21.3 Predicciones de QA de trayectorias (copiadas tal cual; la numeración 78 a 83 es de este archivo)

> **Regla «primera edición».** Primera llamada `edit_file` o `write_file` de la sesión; su número es el orden de las llamadas a herramienta de esa tarea. Fuente: `anatomia.llamada_de_la_primera_edicion` de `iteracion_08_s*.json` (el registro `registro_iteracion_08_s2.jsonl` no guarda nombres de herramienta; el campo sale de las trazas).

| N.º | Afirmación | Prob. | Línea base | Marca |
|---|---|---|---|---|
| 78 | Fracción de sesiones con primera edición ≤12 llamadas, en la pasada 1, entre 0,15 y 0,40 | 0,75 | s1 6/12, s2 3/12 (`iteracion_08_s*.json`) | campo citado, sobre tareas válidas |
| 79 | Resueltas entre las de edición ≤12: ≥0,70; entre el resto: ≤0,10 | 0,70 | 7/9 y 0/15 (con la regla de arriba) | mismo campo y `resuelta` |
| 80 | De las ~14 tareas cortas, se resuelven de 0 a 3 | 0,80 | 0 de 8 sesiones | `instance_id` en la regla de enunciado, `resuelta` |
| 81 | Tasa de resueltas en cortas menor que en el resto (diferencia ≥0,10) | 0,80 | 0,00 contra 0,44 | igual |
| 82 | En cortas, la mediana de llamadas antes de la primera edición es mayor o no existe edición en ≥40 % de las sesiones | 0,65 | 4 de 8 sin parche (`parche_caracteres == 0`) | `parche_caracteres`, `llamadas_herramientas` |
| 83 | En cortas, ≥2 sesiones buscan por número de issue (`search_similar_code` o grep de «#NNNN») | 0,55 | rich_3105 en s1 y s2 | no evaluable con el registro; sí con trazas (`arguments`) |

> Repetición: 78-82 igual sentido; 83 solo con trazas.

(En el original la última línea dice «74-78» y «79», con la numeración provisional de QA.)

### 21.4 Precisiones de los autores, tras la revisión del PR #204 (copiadas tal cual)

Un revisor independiente señaló predicciones que no se podían aplicar sin juicio y una línea base errónea. Lo
copiado en 21.2 y 21.3 no se editó. Cada autor precisó lo suyo el 2026-10-13 antes de las 01:00 UTC, todavía
sin ningún dato de la corrida, sin cambiar afirmaciones, probabilidades ni umbrales. Donde una nota y una
tabla difieren, manda la nota.

**Analista de datos:**

> **75.** Mal planteada: dos partes, una cifra. Queda como probabilidad de la **conjunción** (atrapadas <=20 % Y libres 20 a 40 %); se marca cada parte aparte (acierta/falla) y la 75 acierta solo si ambas aciertan. Con menos de 5 atrapadas: «no evaluable». Con libres vacío: «no evaluable».
>
> **76.** Tres partes: la cuenta (14 de 60, prob. 0,99), cortas <=3 resueltas (0,80) y resto 8 a 20 (0,75). Cada probabilidad es de **su parte**, no de la conjunción. Si la pasada no termina las 60 tareas: las dos de resueltas «no evaluable»; la cuenta se marca igual (no depende de la corrida).
>
> **77.** Sin ninguna atrapada en la pasada 1: «no evaluable» (sin denominador). Si la pasada 2 no se corre o queda incompleta: «no evaluable».

**QA de trayectorias:**

> **79.** La probabilidad es de la **conjunción**: ≥0,70 entre edición ≤12 y ≤0,10 en el resto. Cada parte se marca con `resuelta` agrupada por `anatomia.llamada_de_la_primera_edicion` (≤12 frente a mayor o `None`). Grupo vacío: la 79 no es evaluable. Mal planteada: dos afirmaciones, una probabilidad.
>
> **82.** La probabilidad es de la **disyunción** de (a) mediana de llamadas hasta la primera edición en cortas mayor que en las no cortas de la misma pasada, y (b) ≥40 % de sesiones cortas con ese campo en `None`. Se marca con ese campo, no con `parche_caracteres` (`rich_3470` de `s2` tiene parche y `None`). Sin no cortas, (a) no es evaluable.
>
> **83.** `rich_3105` no es corta (452 caracteres): entre las 4 cortas de `s1` y `s2` no hay base. Mal fundada.
>
> **Exigen trazas del zip crudo:** 78, 79, 82 y 83. La 80 y la 81 salen de `resuelta` y `instance_id`.

### 21.5 Lo que queda dicho por el orquestador, no por los autores

- **Dos omisiones del orquestador al copiar la definición, que el revisor señaló.** El original trae un
  preámbulo que 21.1 dejó fuera: «Unidad: la sesion (una tarea en una corrida). Secuencia: todas las llamadas
  a herramientas de la traza, en orden», que es lo que D2 llama «consecutivas»; y «Ya conocia, por los
  informes ajenos, los resultados en las 24 sesiones de s1 y s2». Es decir: la definición se fijó antes de
  abrir las 145 sesiones antiguas, **no** antes de conocer el resultado en las 24. El recuento de 22 de 145 es
  esa definición aplicada. Lo que el auditor llama posterior y exploratorio es el análisis **por kit** (el «0
  atrapadas de 29» en el kit que razona, y 2 de 22 frente a 19 de 94 dentro de las iteraciones 03 a 05), que
  además está confundido con el kit.
- **A las notas de 21.4 les falta su primera línea**, la de fecha y hora, que sí está en los originales
  (analista: «2026-10-13, UTC»; QA: «2026-10-13T00:56Z»). El resto está copiado tal cual.
- **Regla por defecto para lo que ninguna nota fija.** El revisor señaló que varias predicciones no dicen
  sobre qué pasada se marcan ni qué pasa si la pasada queda incompleta (74, 78, 80, 81), y que la 82 (a) y la
  83 dejan sin fijar un detalle del recuento. No lo fija el orquestador en su nombre. Vale esto, **solo donde
  ni la tabla ni la nota del autor lo fijan** (si lo fijan, mandan ellas: la 74 dice «cada pasada» y se marca
  en cada una; la 76 dice qué pasa si la pasada no termina las 60): se marca sobre la primera pasada; si esa
  pasada tiene menos de 55 tareas válidas, o si al aplicar el criterio hace falta una decisión que no está
  escrita aquí, la predicción queda **«no evaluable»**, y el informe dice cuál fue la decisión que faltaba.
  Nunca se resuelve una ambigüedad a favor de la predicción.
- **Dos reglas distintas para «primera edición».** La del auditor (D7) excluye `/tmp` y los archivos de
  prueba; la de QA usa el campo `anatomia.llamada_de_la_primera_edicion`, que cuenta también los guiones de
  reproducción. En las mismas 24 sesiones, D7 da 7 de 8 y 0 de 16; el campo de QA, 7 de 9 y 0 de 15. Las
  predicciones 78 y 79 se marcan con la regla de QA; el contraste del auditor, con D7. No se unifican.
- **La 76 y la 80 hablan del mismo hecho** (cuántas tareas cortas se resuelven) con el mismo criterio y la
  misma probabilidad: se marcan las dos.
- **Las predicciones 74, 75, 77, 78, 79, 82 y 83 no se pueden marcar con el registro**: exigen las trazas
  del zip crudo de la corrida. Si ese zip no se rescata, quedan «no evaluables». La 76, la 80 y la 81 salen
  del registro y de `tasks.jsonl`.
- **Cuántas tareas cortas hay en las 12 de `s1` y `s2`:** el analista cuenta 4 con la regla de menos de 100
  caracteres; el rol diseñador contó 5 con otra regla, «menos de 120 caracteres útiles» (el quinto es
  `rich_3105`, de 452 caracteres). La regla escrita aquí es la de 100.
- **Ninguna de estas predicciones dice cuál kit acierta más**, y ninguna cubre la nota de un envío.

## 22. Bloque R1 del concilio 47 (issue #205): la base dos veces y cuatro candidatos, en 12 tareas

**Qué se predice.** El bloque R1 que fijó la adenda del auditor del concilio 47: las 12 primeras tareas del
sorteo (4 de ellas con enunciado de menos de 100 caracteres), el kit que razona (`65a02160…`), las ruedas del
2026-10-12 19:51 UTC, y seis brazos: la base dos veces y cuatro candidatos. Al escribir esto no existe ningún
dato de R1, los cuatro kits todavía se están construyendo y no se ha subido nada.

**Los cuatro candidatos**, cada uno distinto de la base solo en lo que se dice:

| | Candidato | Qué cambia |
|---|---|---|
| C1 | Tres cambios a 6 minutos | 6 min por tarea, 28 llamadas, 240 s por orden, sin subagente, grafo prohibido en la instrucción, edición temprana |
| C2 | Edición temprana sola | Solo esa instrucción (primera edición de fuente en la llamada 10 o antes) |
| C3 | Tope de pensamiento | `thinking_budget` 4096 → 1536 |
| C4 | Triaje de enunciado corto | Instrucción para tareas cuyo enunciado no describe el problema |

**La regla que se va a aplicar** (adenda del auditor, escrita antes; citada literal): «el primer candidato,
en este orden, revisado, ensayado en Docker, con media de 262 s o menos en R1, ninguna colgada y neto de −1 o
mejor frente a la base. Si ninguno está listo, no se reenvía la base.» El orden es el de la tabla de arriba,
de C1 a C4. La adenda dice también que 12 tareas locales filtran seguridad y no calidad. Todo envío y toda
subida siguen necesitando la palabra del dueño.

**Quién escribió cada lista.** El diseñador del agente (2026-10-13 01:01 UTC) y el analista de datos
(2026-10-13, antes de cualquier subida), cada uno sin ver la del otro. El orquestador las copió aquí; las del
diseñador no traían número y reciben del 93 al 98, uno por bloque. Originales, sin versionar:
`.scratch/concilio_memoria/fase2/concilio_47/disenador/predicciones_r1.md` y `analista/predicciones_r1.md`.

### 22.1 Predicciones del analista de datos (copiadas tal cual)

> Campos: `tarea_fin.{tarea,resuelta,segundos}`, `cierre.tareas_colgadas`. Neto = resueltas solo por el candidato menos solo por la primera pasada de la base. Grupo vacío o pasada incompleta: no evaluable.

| N.º | Afirmación | Prob. | Línea base | Criterio |
|---|---|---|---|---|
| 84 | Base contra sí misma: 1 a 5 discordantes de 12 | 0,80 | s1 vs s2: 3/12 (kits distintos) | `resuelta` por `tarea` |
| 85 | Resueltas de la base: 2 a 6 en cada pasada (conjunción) | 0,75 | s1: 4/12 | `resuelta` |
| 86 | Media de C1 (6 min) <=262 s | 0,45 | proyección 263 s; s1 212 s | media de `segundos` |
| 87 | Ninguna colgada, por candidato (C1 a C4) | 0,93 cada una | 0 en 24 sesiones | `tareas_colgadas`=0 |
| 88 | Neto >=-1: C1 0,70; C2 0,80; C3 0,75; C4 0,72 | por separado | nula 0,64 a 0,89 | conteo de discordantes |
| 89 | Pasa la regla (tiempo, colgada y neto, conjunción): C1 0,30; C2 0,68; C3 0,65; C4 0,62 | las del propio enunciado | idem | idem |
| 90 | Neto a 0,80: C1 y C2 de -2 a +3; C3 y C4 de -3 a +2 | 0,80 por candidato | idem | idem |
| 91 | Cuota del bloque entre 9,0 y 12,5 h | 0,80 | adenda 9,8 a 11,5; s2 0,98 h por 12 | diferencia de `uvx kaggle quota` antes de la primera subida y tras la última sesión `complete` |

> **Lo que el bloque no dice (92).** Orden de los cuatro por neto en R1 igual al orden por nota en la tabla: 0,05 (azar 0,04); el primero de R1 es el primero de la tabla: 0,30 (azar 0,25). Se marca con candidatos ya enviados, una lectura cada uno. No evaluable si se enviaron menos de 3, si hay empate en el primer lugar o si cambiaron las ruedas entre lecturas.

### 22.2 Predicciones del diseñador del agente (copiadas tal cual; los números 93 a 98 son de este archivo)

> «Base» = media de sus dos pasadas. Segundos = media de `duration_seconds`. (T) = exige las trazas del zip crudo; lo demás sale del json de la sesión.

**93. Base.**

> Media entre 215 y 245 s (p 0,7). Resueltas de 3 a 5 en cada pasada (p 0,8).

**94. C1, tres cambios a 6 minutos.**

> - Media entre 235 y 280 s (p 0,7). Pasa de 262 s: p 0,35.
> - Resueltas: base menos 1 o más (p 0,75); más que la mejor pasada de la base: p 0,25.
> - Primera edición de fuente en la llamada 10 o antes en 6 o más sesiones (p 0,4). (T)
> - Alguna llamada al subagente retirado: p 0,2. Llamadas de grafo: 3 o menos (p 0,6). (T)

**95. C2, edición temprana sola.**

> - Media a ±15 s de la base (p 0,75). Pasa de 262 s: p 0,03.
> - Resueltas a ±1 de la base (p 0,7).
> - Sesiones con primera edición en la llamada 10 o antes: al menos 2 más que la base (p 0,35). Apuesto a que no se adelanta. (T)

**96. C3, tope de pensamiento 1 536.**

> - Ninguna respuesta con 2 000 `completion_tokens` o más (p 0,8); la base, al menos una (p 0,8). (T)
> - Media menor que la base (p 0,65). Pasa de 262 s: p 0,02.
> - Pierde una tarea que las dos pasadas de la base resuelven: p 0,25.

**97. C4, triaje.**

> - Llamadas en las 4 cortas: mediana de 10 o menos (p 0,4); la base, 15 o más (p 0,8).
> - Segundos sumados en las 4 cortas: 600 o menos (p 0,4); la base, 850 o más (p 0,7).
> - Media menor que la base (p 0,6). Pasa de 262 s: p 0,02.
> - Una tarea no corta entregada en la llamada 8 o antes y no resuelta: p 0,2. (T)
> - Resueltas a ±1 de la base (p 0,75); alguna corta resuelta: p 0,1.

**98. General.**

> Ningún candidato difiere de la base en más de 2 resueltas (p 0,8).

### 22.3 Precisiones de los autores, tras la revisión del PR #207 (copiadas tal cual)

Un revisor independiente señaló criterios que no se podían aplicar sin juicio. Lo copiado en 22.1 y 22.2 no
se editó. Cada autor precisó lo suyo el 2026-10-13, todavía sin ningún dato de R1, sin cambiar afirmaciones,
probabilidades ni umbrales. Donde una nota y una lista difieren, manda la nota.

**Analista de datos** («2026-10-13, UTC. Precisiones a 84-92.»):

> 1. Pasada completa en R1: 12 eventos `tarea_fin` (uno por tarea) y un `cierre`. La definición de tarea válida de 20.1 rige tal cual; el umbral de 55 no se aplica.
> 2. 92: un empate de neto entre dos candidatos o de nota en la tabla deja esa pareja sin evaluar; si quedan menos de 3 candidatos ordenables sin empate, la 92 es no evaluable.
> 3. 91: la línea base no marca; vale la de 21.2 (0,99 h), que no he vuelto a derivar.
> 4. «263 s» sale de `ronda2_d_proyeccion.py`, fila de tope 360 s y 28 llamadas (media 263, 10,01 h para 120 tareas). «0,64 a 0,89» sale de `r1_cuentas.py`, solo de la fila de discordancia 0,25; la tabla completa de ese guion va de 0,55 a 0,93.
> 5. No leí `predicciones_r1.md` del diseñador antes ni después de escribir la mía.

**Diseñador del agente** («Escritas el 2026-10-13 a las 01:21 UTC, sin ningún dato de R1. No cambian afirmaciones, probabilidades ni umbrales.»):

> 1. **Primera edición de fuente:** uso `primera_edicion_fuente_ok` (`g2_compacto.py`): índice, desde 1, de la primera llamada `edit_file` o `write_file` con estado `ok`, cuyo `filepath` termina en `.py`, contiene `/`, no empieza por `tests/` y cuyo archivo no es `test_*.py` ni `*_test.py`. Una sesión que nunca edita no cuenta como «en la 10 o antes».
> 2. **Llamadas de grafo:** total del brazo en las 12 tareas. Cuentan `search_similar_code`, `get_code_neighbors` y `get_code_subgraph`, de cualquier autor.
> 3. **Tiempo:** vale `tarea_fin.segundos` del registro; las predicciones de tiempo no exigen trazas. Si falta en alguna tarea, esa predicción queda no evaluable.
> 4. **Base:** media de las dos pasadas, sin redondear. «±1»: |x − base| ≤ 1. «Base menos 1 o más»: x ≥ base − 1. «Al menos 2 más»: x ≥ base + 2. Las medianas de la base se promedian igual. «La base, al menos una» (C3): en las dos pasadas juntas.
> 5. **Mal planteada:** «pierde una tarea que las dos pasadas resuelven» es no evaluable si ninguna tarea cumple eso.

### 22.4 Lo que queda dicho por el orquestador, no por los autores

- **Sobre «sin verse».** Al analista se le pidió no leer la lista del diseñador, y declara que no la leyó
  (nota 5). Su archivo se escribió unos 80 segundos después del otro: la independencia no se puede comprobar
  desde fuera.
- **La regla por defecto de 21.5 rige aquí sin su umbral de 55 tareas válidas**, que es de la corrida de 60:
  en R1 «pasada completa» es lo que dice la nota 1 del analista.
- **Con estas notas hay cuatro reglas para «primera edición» en el archivo** (D7 del auditor, el campo de QA,
  y ahora `primera_edicion_fuente_ok`, que además exige estado `ok` y extensión `.py`). Las predicciones del
  diseñador se marcan con la suya. No se unifican.
- **Cada línea con su probabilidad es una predicción y se marca por separado.** Las del diseñador llevan
  varias por bloque; el número del bloque (93 a 98) es solo para citarlas.
- **Las dos listas definen la base de forma distinta.** El analista compara cada candidato con la primera
  pasada de la base; el diseñador, con la media de las dos, sin redondear. No se unifican: cada una se marca
  con su definición. Para el tiempo, el diseñador escribió `duration_seconds`, que solo está en el zip crudo,
  y en su nota 3 acepta `tarea_fin.segundos` del registro, el mismo campo que usa el analista.
- **Las dos listas discrepan en C1.** Que la media de C1 pase de 262 s: 0,35 según el diseñador y 0,55 según
  el analista (su 86 da 0,45 a que no pasa). Se marcan las dos.
- **Para lo que ninguna lista ni nota fija**, vale lo dicho arriba sobre la regla por defecto: si al marcar
  hace falta una decisión que no está escrita, la predicción queda «no evaluable», nunca a su favor.
- **Las marcadas (T) exigen las trazas del zip crudo de cada sesión.** Si no se rescatan, quedan «no
  evaluables».
- **Ninguna predicción de esta sección dice qué candidato sacará mejor nota.** La 92 dice expresamente que
  el bloque casi no informa de eso.
