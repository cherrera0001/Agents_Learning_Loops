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
este experimento quiere ver venir: estaba en `main` antes de que nadie lo tocara.

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

- **Predicción 1.** «La cuarta revisión» es la primera revisión de `revisor-codigo` sobre el commit que
  responde a la tercera. Ocurre el hecho si su veredicto escrito es «cambios requeridos antes de fusionar» o
  equivalente. «Aprobado con observaciones» no cuenta, aunque después se corrija algo.
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
- **Fuente de la predicción 4:** el informe del investigador está en
  [`../docs/informe_investigador_2026-10-09.md`](../docs/informe_investigador_2026-10-09.md).

### 8.3 Desenlaces ya a la vista al escribir esta versión

- **Predicción 4: ocurrió.** La revisión de documentos del PR #163 encontró frases de
  `docs/estado_del_arte.md` que no estaban en el informe del investigador (una interpretación sobre la moneda
  y la ruleta, y dos categorías de «no buscado»). La marcó el propio revisor en su informe. Falta que un rol
  distinto del orquestador la registre con su enlace.
- **Predicción 5: sin cerrar.** La CI del commit `b98af92` tenía comprobaciones en curso al escribir esto.

### 8.4 Medida y tamaño, corregidos

Sustituye a los dos últimos puntos de la lista de la sección 4 y a su párrafo de potencia.

- **Regla para afirmar que predecir acierta mejor:** prueba t pareada de una cola al 5 % sobre las
  diferencias de Brier por unidad efectiva, con su intervalo de confianza. Sin esa prueba, no se afirma.
- **Regla para refutar:** con el tamaño de decisión alcanzado, una puntuación de Brier igual o peor que la de
  la línea base.
- **Unidad efectiva:** las predicciones de un mismo issue están correlacionadas. Se agrupan por issue y la
  prueba se hace sobre la media por issue.
- **Potencia, calculada por el analista de datos** (simulación con un predictor calibrado, que es el mejor
  caso): con 30 predicciones independientes, una mejora de Brier de 0,02 se detecta entre 18 y 22 de cada 100
  veces, y una de 0,05 entre 37 y 43. Para 80 de cada 100 hacen falta entre 100 y 200 predicciones si la
  mejora es de 0,05, y más de 400 si es de 0,02.
- **Tamaños:** con menos de 30 predicciones cerradas solo se informa el conteo. Entre 30 y 100, la puntuación
  de Brier se informa como descripción, sin conclusión. La lectura de decisión no se hace con menos de 100
  predicciones cerradas en al menos 20 issues.
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
cuáles ve el implementador y cuáles quedan selladas. Comparar la frecuencia del hecho entre reveladas y selladas
separa el efecto de predecir del acierto de predecir. Con frecuencias de 0,4 frente a 0,2 hacen falta unas 62
predicciones por rama, y unas 135 contando la agrupación por issue.

Las seis predicciones de la sección 5 las escribió quien hace el trabajo y las vio todo el mundo. Sirven para
ensayar el protocolo, no para esa comparación.
