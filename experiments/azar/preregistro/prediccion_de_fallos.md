# Pre-registro: predecir el fallo antes de que ocurra

**Fechado el 2026-10-09, hacia las 05:30 UTC**, antes de conocer ninguno de los desenlaces de la sección 5.
La fecha que vale es la del commit que añade este archivo.

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
