# Estado del arte verificado (fase 1, primera pasada)

**Fecha de la verificación: 2026-10-09.** La hizo el rol `investigador-papers` sobre una lista que el
orquestador escribió de memoria. Su informe íntegro está en
[`informe_investigador_2026-10-09.md`](informe_investigador_2026-10-09.md).

Regla: una obra solo figura como verificada si se abrió su identificador.
Presupuesto de la pasada: 60 búsquedas o aperturas; se agotó. Lo que no se buscó está al final y no es
«ausencia comprobada».

**Cómo leer la columna «abierto».**

- *Artículo*: se abrió el texto o su resumen en la página del editor o en arXiv.
- *Metadatos*: se abrió la entrada de Crossref (autores, año, revista, páginas), no el artículo. Lo que la
  obra afirma viene entonces de una fuente secundaria y se dice.
- *Solo búsqueda*: la obra no se abrió. No se puede citar como verificada.

La columna «clase» es una clasificación editorial del investigador. Ninguna fila está marcada «reproducida»:
esta pasada no buscó reproducciones independientes.

## 1. Sistemas físicos «aleatorios» con predictibilidad medida

| Obra | Abierto | Qué respalda | Clase |
|---|---|---|---|
| Diaconis, Holmes y Montgomery (2007), «Dynamical bias in the coin toss», *SIAM Review* 49(2):211–235. [DOI 10.1137/S0036144504446436](https://doi.org/10.1137/S0036144504446436) | Metadatos | Que predice cerca de 51 % del lado inicial viene de una página de D. Aldous (que cita 50,8 %), no del artículo | Resultado teórico |
| Bartoš y 49 coautores, «Fair coins tend to land on the same side they started: Evidence from 350,757 flips», *JASA* 120 (2025). [arXiv 2310.04153](https://arxiv.org/abs/2310.04153) · [DOI 10.1080/01621459.2025.2516210](https://doi.org/10.1080/01621459.2025.2516210) | Artículo (arXiv) | Probabilidad de caer del mismo lado: 0,508, IC 95 % de 0,506 a 0,509 | Experimental preliminar: un solo estudio |
| Keller (1986), «The probability of heads», *Am. Math. Monthly* 93(3):191–197. [DOI 10.2307/2323340](https://doi.org/10.2307/2323340) | Metadatos | Lo que afirma no se leyó | Resultado teórico |
| Small y Tse (2012), «Predicting the outcome of roulette», *Chaos* 22, 033150. [arXiv 1204.6412](https://arxiv.org/abs/1204.6412) | Artículo (arXiv) | Retorno esperado de «al menos 18 %» en rueda europea midiendo las rotaciones con un dispositivo; sesgos significativos con cámara | Experimental preliminar: muestra pequeña |
| Kapitaniak, Strzałko, Grabski y Kapitaniak (2012), «The three-dimensional dynamics of the die throw», *Chaos* 22(4), 047504. [DOI 10.1063/1.4746038](https://doi.org/10.1063/1.4746038) | Metadatos | Lo que afirma no se leyó | Experimental preliminar |
| Pinitsoontorn, Buathong y Srisodaphol (2014), «Is it possible to cheat the lottery draw by weighing?», *Asia-Pacific J. Sci. Technol.* 19(6):804–818. [Página de la revista](https://so01.tci-thaijo.org/index.php/APST/article/view/83061) | Artículo | Máquina modelo de aire, 1 000 sorteos, bolas de espuma del 0 al 9: una bola 1 % o 5 % más pesada no dio sesgo significativo; una más ligera sí, y salió más | Experimental preliminar: modelo a escala |

La última fila es **el único trabajo revisado encontrado sobre una máquina de sorteo de esferas**. Es un
modelo a escala con bolas de espuma.

## 2. Loterías: auditorías, sesgo de los jugadores y fallos

| Obra | Abierto | Qué respalda | Clase |
|---|---|---|---|
| Fienberg (1971), «Randomization and social affairs: the 1970 draft lottery», *Science* 171(3968):255–261. [DOI 10.1126/science.171.3968.255](https://doi.org/10.1126/science.171.3968.255) | Metadatos | Que la mezcla de cápsulas fue insuficiente viene de fuentes secundarias | Observacional |
| Haigh (1997), «The statistics of the National Lottery», *JRSS A* 160(2):187–206. [Página del editor](https://academic.oup.com/jrsssa/article/160/2/187/7102439) | Artículo | Los primeros 96 sorteos son compatibles con el azar; las combinaciones que eligen los jugadores están lejos de ser aleatorias | Observacional |
| Farrell, Hartley, Lanot y Walker (2000), «The demand for lotto: the role of conscious selection», *JBES* 18(2):228–241. [DOI 10.1080/07350015.2000.10524865](https://doi.org/10.1080/07350015.2000.10524865) | Metadatos | Que los jugadores no eligen de forma uniforme viene del resumen en un índice | Observacional |
| Coronel-Brizio, Hernández-Montoya, Rapallo y Scalas (2008), «Statistical auditing and randomness test of lotto k/N-type games», *Physica A* 387(25):6385–6390. [arXiv 0806.4595](https://arxiv.org/abs/0806.4595) | Artículo (arXiv) | Marco estadístico para auditar un sorteo de k entre N, con medias y covarianzas hipergeométricas | Método |

La obra de Coronel-Brizio y otros es la más cercana a lo que la fase 3 necesita.

## 3. Aprendizaje automático sobre secuencias aleatorias

| Obra | Abierto | Qué respalda | Clase |
|---|---|---|---|
| Truong, Haw, Assad, Lam y Kavehei (2019), «Machine learning cryptanalysis of a quantum random number generator», *IEEE TIFS* 14(2):403–414. [arXiv 1905.02342](https://arxiv.org/abs/1905.02342) | Artículo (arXiv) | El modelo detecta correlaciones cuando el ruido determinista es fuerte; tras filtrar y extraer aleatoriedad, el dispositivo resiste | Experimental preliminar |
| Gohr (2019), «Improving attacks on round-reduced Speck32/64 using deep learning», CRYPTO 2019. [ePrint 2019/037](https://eprint.iacr.org/2019/037) | Artículo | Una red supera al distinguidor clásico en un cifrador reducido. No es un sistema físico | Experimental |
| Tao, Doshi, Kalra, He y Barkeshli (2025), «(How) Can Transformers predict pseudo-random numbers?», ICML 2025. [arXiv 2502.10390](https://arxiv.org/abs/2502.10390) | Artículo (arXiv) | Los Transformers predicen en contexto un generador congruencial lineal. Es un generador determinista, no físico | Experimental preliminar |
| Crespo, González-Villa, Gutiérrez y Valle (2024), «Assessing the quality of random number generators through neural networks». [ePrint 2024/578](https://eprint.iacr.org/2024/578) | Artículo | Redes para auditar generadores; resultados distintos según el tipo de generador | Experimental preliminar |
| Lopez-Paz y Oquab, «Revisiting classifier two-sample tests». [arXiv 1610.06545](https://arxiv.org/abs/1610.06545) | Artículo (arXiv) | Si un clasificador no supera el azar en datos retenidos, hay evidencia de que las dos muestras vienen de la misma distribución. El congreso no se confirmó | Método |
| Zeng, Chen, Zhang y Xu (2023), «Are Transformers effective for time series forecasting?», *AAAI* 37(9):11121–11128. [arXiv 2205.13504](https://arxiv.org/abs/2205.13504) | Artículo | Modelos lineales de una capa superan a los Transformers de series temporales en nueve conjuntos de datos | Experimental preliminar |
| PatchTST: Nie, Nguyen, Sinthong y Kalagnanam. [arXiv 2211.14730](https://arxiv.org/abs/2211.14730) | Artículo (arXiv) | La obra existe; no se evaluó lo que afirma | Sin clasificar |
| iTransformer: Liu y otros. [arXiv 2310.06625](https://arxiv.org/abs/2310.06625) | Artículo (arXiv) | La obra existe; el congreso no se confirmó | Sin clasificar |
| Informer: Zhou y otros. [arXiv 2012.07436](https://arxiv.org/abs/2012.07436) | Artículo (arXiv) | La obra existe | Sin clasificar |
| Temporal Fusion Transformer: Lim, Arik, Loeff y Pfister. [arXiv 1912.09363](https://arxiv.org/abs/1912.09363) | Artículo (arXiv) | La obra existe | Sin clasificar |

**Predicción de lotería con redes: no se encontró ningún artículo revisado.** Ninguna búsqueda de esta pasada
localizó un trabajo revisado que prediga sorteos con LSTM o Transformers, y por tanto tampoco uno que lo haga
fuera de muestra contra una línea base aleatoria. Es «no encontrado con este presupuesto», no «no existe».

## 4. Pruebas de aleatoriedad y límites

| Obra | Abierto | Qué respalda | Clase |
|---|---|---|---|
| Benjamini y Hochberg (1995), *JRSS B* 57(1):289–300. [DOI 10.1111/j.2517-6161.1995.tb02031.x](https://doi.org/10.1111/j.2517-6161.1995.tb02031.x) | Metadatos | Referencia para el control de comparaciones múltiples | Resultado teórico |

## 5. No verificado

Nada de esta lista se puede citar todavía. Son obras o hechos que no se abrieron, o que no se encontraron.

- **Thorp (1998), «The invention of the first wearable computer».** Solo búsqueda. La cifra que circula es
  una ganancia esperada de 44 % en laboratorio.
- **Strzałko y otros, *Dynamics of Gambling* (Springer, 2009).** Solo catálogos.
- **Auditorías de la lotería británica (Royal Statistical Society o Universidad de Salford).** No se
  encontró ningún informe. El orquestador las había dado por existentes.
- **Fraude de Pensilvania (1980) y caso Tipton (2010).** Solo Wikipedia; sus fuentes primarias no se
  abrieron.
- **Cash WinFall de Massachusetts y los raspes de Ontario (Srivastava).** Solo búsqueda; el informe del
  Inspector General no se pudo leer.
- **Los 433 ganadores de Filipinas (2022).** Solo prensa. La explicación publicada es la declaración de la
  propia lotería, no un análisis.
- **NIST SP 800-22 Rev. 1a y SP 800-90B; TestU01 (L'Ecuyer y Simard, 2007); Cover y Thomas (2006).** Solo
  búsqueda o catálogos.

## 6. Correcciones a lo que el orquestador escribió de memoria

- El coautor del trabajo sobre el generador cuántico es Kavehei, no Kanno, y el año es 2019.
- El estudio de las 350 757 tiradas ya está publicado (*JASA*, 2025).
- Informer es de 2020 y Temporal Fusion Transformer de 2019 en arXiv.
- Las auditorías británicas que se citaron no aparecieron.
- Sobre «muchos artículos que dicen predecir lotería con LSTM»: no se encontró ninguno revisado.

## 7. Qué tiene respaldo y qué no

Las clases de esta sección son del orquestador.

- **Con respaldo, con cautela (evidencia experimental preliminar):** un sistema mecánico «aleatorio» puede
  tener un sesgo físico medible. La moneda (0,508 en un solo estudio grande) y la ruleta (retorno de al menos
  18 % midiendo el sistema, con muestra pequeña). *Interpretación del orquestador, no del informe:* en la
  ruleta la ventaja sale de medir el sistema antes del resultado, no de mirar resultados pasados; en la moneda
  lo medido es un sesgo, no una ventaja.
- **Brecha candidata (hipótesis):** para máquinas de sorteo de esferas solo se encontró un modelo a escala con
  bolas de espuma. No se encontró ningún estudio que mida una máquina real con sensores.
- **Sin respaldo encontrado (especulación mientras no haya fuente):** que un modelo prediga un sorteo real
  por encima del azar.
- **No son evidencia de predictibilidad física:** los fraudes por manipulación y las explotaciones de reglas.

## 8. Lo que esta pasada no buscó

Revisiones sistemáticas de auditorías de lotería; reproducciones independientes de Small y Tse; estudios con
medición física de máquinas de aire o de paletas; sorteos de países distintos del Reino Unido y Estados
Unidos. Hasta aquí, la lista del investigador. El orquestador añade, porque el encargo no las pedía:
literatura de mantenimiento predictivo, patentes y documentación de fabricantes.
