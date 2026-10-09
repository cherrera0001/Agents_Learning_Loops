# Informe del investigador de papers (2026-10-09)

Texto íntegro del informe que entregó el rol `investigador-papers` al verificar la lista del orquestador.
Es la fuente de [`estado_del_arte.md`](estado_del_arte.md) y se guarda sin editar, salvo esta cabecera.
«Tu lista» y «tus» se refieren al orquestador.

---

**Veredicto: apto con cambios.** Las entradas A y B quedan en su mayoría confirmadas, con correcciones puntuales. El bloque C de lotería con ML no tiene ni una fuente revisada que pueda citarse. Varias entradas siguen sin verificar y están en la lista final.

**Código del repositorio:** el Grep de lotería, Diaconis y Fano solo devuelve `scripts/kaggle_ensayo.py` y dos tests, es decir, coincidencias sin relación con este tema. El repositorio no nombra ningún mecanismo de este bloque. Ningún código implementa estas obras.

**Criterio de «abierto»:** el texto de los DOI de SIAM, Science, AIP y T&F, y los PDF de Keller y Diaconis, devolvieron 403 o binario ilegible. Para esas obras los metadatos salen de la API de Crossref (abrí la entrada, no el artículo). Donde pone «solo búsqueda», la obra no se abrió y va también en la lista final.

## Tabla

| # | Cita corregida | Identificador abierto | Qué respalda exactamente | Clasificación |
|---|---|---|---|---|
| 1 | Diaconis, Holmes, Montgomery (2007), *SIAM Review* 49(2):211–235 | [Crossref 10.1137/S0036144504446436](https://api.crossref.org/works/10.1137/S0036144504446436). El resumen «≈.51» viene de la [página de Aldous](https://www.stat.berkeley.edu/~aldous/Real-World/coin_tosses.html) y de búsqueda. | Metadatos confirmados. La cifra: Aldous la cita como 50,8 %, es decir «~51 %». No leí el artículo. | Resultado teórico |
| 2 | Bartoš y otros (49 coautores más; 50 en total), «Fair coins tend to land on the same side they started: Evidence from 350,757 flips». **Publicado:** *JASA* 120 (2025) | [arXiv 2310.04153](https://arxiv.org/abs/2310.04153); [Crossref 10.1080/01621459.2025.2516210](https://api.crossref.org/works/10.1080/01621459.2025.2516210) | «Pr(same side) = 0.508», IC 95 % [0,506; 0,509]. Tus 350 757 tiradas y tu 50,8 % están correctos. | Experimental preliminar. Es un único estudio, sin reproducción independiente que yo haya visto. |
| 3 | Keller (1986), *Am. Math. Monthly* 93(3):191–197 | [Crossref 10.2307/2323340](https://api.crossref.org/works/10.2307/2323340). El PDF no era legible. | Metadatos confirmados. Que la probabilidad tiende a 1/2 en el límite de velocidades altas viene solo de una búsqueda. | Resultado teórico |
| 4 | Small y Tse (2012), *Chaos* 22, 033150 | [arXiv 1204.6412](https://arxiv.org/abs/1204.6412) | Retorno esperado «at least 18 %» en rueda europea con un dispositivo mecánico de cuenta de rotaciones. Hay sesgos significativos con cámara. Sobre la muestra: Inside Science (solo búsqueda) dice que acertaron 13 de 22 en una mitad. | Experimental preliminar |
| 5 | Thorp (1998), «The Invention of the First Wearable Computer», Int. Symp. on Wearable Computers | Solo búsqueda: [escholarship.org/uc/item/8342j4k0](https://escholarship.org/uc/item/8342j4k0) | La ganancia esperada que se cita es +44 % en laboratorio (el «octante» más favorecido), no 18 %. Prueba en Las Vegas en 1961 sin apuestas sostenidas. | Experimental preliminar. Es un relato autobiográfico. |
| 6 | Kapitaniak, Strzałko, Grabski, Kapitaniak (2012), *Chaos* 22(4), 047504 | [Crossref 10.1063/1.4746038](https://api.crossref.org/works/10.1063/1.4746038) | Metadatos confirmados, y el número de artículo que dabas queda confirmado. Que la cara inicial inferior tiene más probabilidad de quedar arriba viene de notas de prensa. | Experimental preliminar |
| 7 | Strzałko, Grabski, Perlikowski, Stefański, Kapitaniak, *Dynamics of Gambling*, Springer LNP 792, **2009**, DOI 10.1007/978-3-642-03960-7 | Solo catálogos (UiTM, MPDL). Springer redirigió. | Año y autores correctos. La tesis es que los aleatorizadores mecánicos son predecibles en principio. | Resultado teórico y de simulación. Es un libro. |
| 8 | Fienberg (1971), *Science* 171(3968):255–261 | [Crossref 10.1126/science.171.3968.255](https://api.crossref.org/works/10.1126/science.171.3968.255) | Metadatos confirmados. La mezcla insuficiente de cápsulas viene de fuentes secundarias de la búsqueda. | Evidencia observacional |
| 9 | Haigh (1997), *JRSS A* 160(2):187–206 | [OUP](https://academic.oup.com/jrsssa/article/160/2/187/7102439), abierto | Los primeros 96 sorteos son consistentes con azar. Las combinaciones elegidas por los jugadores están «far from random». | Evidencia observacional |
| 10 | No encontrado | | No hallé ningún informe de auditoría de la RSS ni de Salford. Encontré el relato de 1997 de Camelot sobre control de bolas (Marketing Week, solo búsqueda) y el artículo de Haigh. | |
| 11 | Pensilvania 1980 y Tipton | Solo Wikipedia: [Tipton](https://en.wikipedia.org/wiki/Eddie_Tipton), [Pensilvania](https://en.wikipedia.org/wiki/Pennsylvania_Lottery_scandal) | Pensilvania: sorteo del 24-abr-1980 con resultado 666, bolas lastradas. Tipton: manipuló el generador de Hot Lotto en el sorteo del 29-dic-2010. Las fuentes primarias que cita Wikipedia son *State v. Tipton*, 897 N.W.2d 653 (Iowa, 2017) y prensa (Des Moines Register, Tribune). No las abrí. | Hecho judicial, de fuente secundaria |
| 12 | Cash WinFall y Srivastava | Solo búsqueda. El PDF del Inspector General no era legible. | Búsqueda (ABC, NBC, Freakonomics): 4 sindicatos, unos 40 M$ gastados y 48 M$ ganados. Srivastava aparece en Freakonomics/Wired como el estadístico de los raspes de Ontario. | Explotación de reglas, no de física. Sin verificar. |
| 13 | Farrell, Hartley, Lanot, Walker (2000), «The Demand for Lotto: The Role of Conscious Selection», *JBES* 18(2):228–241, DOI 10.1080/07350015.2000.10524865 | Metadatos de Crossref (consulta bibliográfica). Resumen de búsqueda (RePEc). | «Strong evidence» de que los jugadores no eligen números de forma uniforme. Sobre Filipinas (1-oct-2022, 433 ganadores): la combinación 09-45-36-27-18-54, múltiplos de 9, ya está verificada en prensa filipina (solo búsqueda). La explicación de PCSO («leales a sus números») es la declaración de la propia lotería, no un análisis. | Evidencia observacional |
| 14 | Pinitsoontorn, Buathong, Srisodaphol, «Is it possible to cheat the lottery draw by weighing?», *Asia-Pacific J. Sci. Technol.* 19(6):804–818, **2014** | [Thaijo](https://so01.tci-thaijo.org/index.php/APST/article/view/83061), abierto | Máquina modelo de aire con 1000 sorteos y bolas de espuma 0–9. Una bola 1 % o 5 % más pesada no produjo sesgo significativo. Una más ligera sí, y su probabilidad subió. El año 2014 es el de la edición. La cita dice 2017 por la fecha en línea. | Experimental preliminar. Es un modelo a escala. |
| 15 | No encontrado | | Ninguna búsqueda localizó un artículo revisado de predicción de lotería con LSTM o Transformer. | |
| 16 | **Truong, Haw, Assad, Lam, Kavehei** (no Kanno), *IEEE TIFS* 14(2):403–414, **feb. 2019** | [arXiv 1905.02342](https://arxiv.org/abs/1905.02342) | El modelo detecta correlaciones cuando el ruido determinista es fuerte. Tras filtrado y extracción de aleatoriedad, el dispositivo resiste. | Experimental preliminar |
| 17 | Gohr (2019), *CRYPTO 2019* | [ePrint 2019/037](https://eprint.iacr.org/2019/037) | Redes residuales superan al distinguidor diferencial clásico en Speck de 9 rondas. Es un cifrador reducido, no un sistema físico. | Experimental, reproducida por terceros en la literatura criptográfica (no verificado aquí) |
| 18 | Lopez-Paz y Oquab, «Revisiting Classifier Two-Sample Tests» | [arXiv 1610.06545](https://arxiv.org/abs/1610.06545). La página no lista congreso. | Si el clasificador no supera el azar en datos retenidos, hay evidencia de misma distribución. El ICLR 2017 de tu lista queda sin confirmar. | Resultado teórico y metodológico |
| 19 | Zeng, Chen, Zhang, Xu (2023), *AAAI* 37(9):11121–11128 | [AAAI OJS](https://ojs.aaai.org/index.php/AAAI/article/view/26317); [arXiv 2205.13504](https://arxiv.org/abs/2205.13504) | Modelos lineales de una capa superan a los Transformers de series temporales en nueve conjuntos de datos reales. | Experimental preliminar |
| 19b | PatchTST (Nie, Nguyen, Sinthong, Kalagnanam), arXiv 2022, aceptado en ICLR 2023 | [arXiv 2211.14730](https://arxiv.org/abs/2211.14730) | La cita existe. Tu año 2023 es el del congreso. | |
| 19c | iTransformer (Liu y otros; Long es el último autor), arXiv 2023/2024 | [arXiv 2310.06625](https://arxiv.org/abs/2310.06625) | **La página de arXiv no lista congreso.** | |
| 19d | Informer (Zhou y otros), **arXiv 2020**, anunciado para AAAI 2021 | [arXiv 2012.07436](https://arxiv.org/abs/2012.07436) | Año 2020 en arXiv, no 2021. | |
| 19e | TFT (Lim, Arik, Loeff, Pfister), **arXiv 2019** | [arXiv 1912.09363](https://arxiv.org/abs/1912.09363) | Año 2019, no 2021. La página no lista revista. | |
| 20 | SP 800-22 Rev. 1a (abril 2010); SP 800-90B (enero 2018) | Solo búsqueda (CSRC) | Rev. 1a sigue vigente. En 2022 NIST decidió revisarla y no se halló borrador. SP 800-90B está final, con dos erratas anotadas en 2025. | Norma |
| 21 | L'Ecuyer y Simard (2007), *ACM TOMS* 33(4), DOI 10.1145/1268776.1268777 | Solo búsqueda | El título correcto es «TestU01: A C library for empirical testing of random number generators». | Herramienta |
| 22 | Cover y Thomas, *Elements of Information Theory*, 2.ª ed., Wiley-Interscience, 2006, ISBN 9780471241959 | Solo catálogos de biblioteca | Cita de libro estándar. Benjamini y Hochberg (1995), *JRSS B* 57(1):289–300: [Crossref 10.1111/j.2517-6161.1995.tb02031.x](https://api.crossref.org/works/10.1111/j.2517-6161.1995.tb02031.x), metadatos confirmados. | Resultado teórico |

## Obras nuevas abiertas

- Coronel-Brizio, Hernandez-Montoya, Rapallo, Scalas (2008), «Statistical auditing and randomness test of lotto k/N-type games», *Physica A* 387(25):6385–6390, [arXiv 0806.4595](https://arxiv.org/abs/0806.4595). Es un marco estadístico de auditoría con medias y covarianzas hipergeométricas, y es lo más cercano a lo que quieres diseñar.
- Tao, Doshi, Kalra, He, Barkeshli (ICML 2025), «(How) Can Transformers Predict Pseudo-Random Numbers?», [arXiv 2502.10390](https://arxiv.org/abs/2502.10390). Resultado positivo y estructurado: los Transformers predicen LCG en contexto. No es un generador físico, así que no se extiende a lotería.
- Crespo, González-Villa, Gutierrez, Valle (2024), «Assessing the quality of Random Number Generators through Neural Networks», [ePrint 2024/578](https://eprint.iacr.org/2024/578). Usa redes para auditar RNG, con error de entropía cruzada 0,52 sobre un QRNG. Resultados matizados por tipo de generador.

## Qué no pude abrir

- Texto completo de Diaconis, Keller, Kapitaniak, Fienberg (403 o binario).
- Informe del Inspector General de Massachusetts (PDF ilegible).
- Wired y cualquier fuente primaria de Srivastava.
- Fuentes primarias de Tipton y Pensilvania.
- Las páginas del NIST, de TestU01 y de Cover y Thomas.
- La entrada de Crossref para Thorp (1998).

Quedan sin buscar: revisiones sistemáticas de auditorías de lotería, reproducciones independientes de Small y Tse, estudios con medición física de máquinas de aire o de paletas, ni cualquier trabajo sobre la ruleta electrónica o sobre sorteos de bolas de países distintos de Reino Unido y EE. UU. Es presupuesto agotado, no ausencia comprobada.

## Respaldo de la hipótesis

Hay respaldo, con cautela, para que sistemas mecánicos «aleatorios» tengan sesgo físico medible: la moneda (50,8 % en un solo gran estudio, publicado en *JASA* 2025) y la ruleta (retorno ≥18 % con un dispositivo mecánico, muestra pequeña). Para máquinas de sorteo de esferas, el único trabajo revisado que encontré es un modelo a escala de espuma, que ve sesgo solo con una bola más ligera. Eso es una brecha candidata, no un hallazgo. No encontré ninguna fuente revisada que demuestre predicción por encima del azar de un sorteo real con ML, ni una auditoría pública de la lotería británica. Lo que sí hay son fraudes por manipulación del hardware o del software (Pensilvania, Tipton) y explotaciones por reglas (WinFall), que no sirven de evidencia sobre predictibilidad física. La clasificación de mis tablas es editorial: la evidencia por reproducción independiente queda sin cubrir.
