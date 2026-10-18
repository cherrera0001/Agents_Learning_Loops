# Robótica blanda y modelos neuromecánicos de gusanos

El homónimo informático (programas que se copian solos entre máquinas) es otro campo y no se trata aquí.

Fuentes abiertas en esta sesión, el 2026-10-13. Lo que no se abrió queda en Gaps y no aporta cifras.

## Qué líneas hay, y qué dicen los papers abiertos

### Takeaway

Hay dos líneas que no se han juntado. Una fabrica robots peristálticos inspirados en la lombriz (malla con aleación de memoria, módulos neumáticos, lógica neumática sin electrónica). La otra simula el sistema nervioso y el cuerpo de *Caenorhabditis elegans* (Cohen y Boyle; Izquierdo y Beer, y el trabajo posterior de Olivares; BAAIWorm en 2024). Un tercer objeto, en *Science Robotics*, es un robot rígido-blando de cables bilaterales que imita la ondulación del nematodo, no el peristaltismo de la lombriz.

### Cited Findings

- Meshworm (Seok, Onal, Cho, Wood, Rus y Kim), *IEEE/ASME Transactions on Mechatronics* 18(5), 1485–1497, DOI [10.1109/TMECH.2012.2204070](https://softrobotics.wpi.edu/papers/2013-Seok-TransMechat.pdf). Robot de tubo de malla trenzada y bobinas de níquel-titanio, antagonismo inducido al estilo de los oligoquetos. Cinco segmentos en un tubo de unos 200 mm y unos 22 mm de diámetro. La marcha se genera con una secuencia de contracciones; hay potenciómetros de longitud de segmento y, en otra serie, control en lazo cerrado del tiempo de actuación, incluido control por aprendizaje iterativo del periodo de cada segmento. — [PDF del artículo](https://softrobotics.wpi.edu/papers/2013-Seok-TransMechat.pdf)
- Das, Murali Babu, Visentin, Palagi y Mazzolai, «An earthworm-like modular soft robot for locomotion in multi-terrain environments», *Scientific Reports* (2023), [artículo](https://www.nature.com/articles/s41598-023-28873-w) y [PDF institucional](https://www.iris.santannapisa.it/retrieve/ae081cd9-9093-4b79-93cd-7d5c0ee57d4f/2023_Das_An_earthworm%E2%80%91like_modular_soft_robot_for_locomotion_in_multi-terrain_environments.pdf). Cinco actuadores peristálticos blandos en serie (longitud del robot = 350 mm). Cada módulo, con un fuelle y una cámara de volumen de fluido constante (gel, 50 ml en el robot), se alarga con presión positiva y se comprime y expande en radio con vacío. Las marchas (elongación, combinada, multisecuencial) las produce un banco de electroválvulas mandado por una placa microcontroladora. Setae pasivas en la cara ventral. — [Scientific Reports](https://www.nature.com/articles/s41598-023-28873-w)
- Das, Teichmann, Tauber y Speck, «Locomotion analysis of a 3D printed electronics-free peristaltic soft robot», *npj Robotics* 4, artículo 27, publicado el 3 de junio de 2026, [https://www.nature.com/articles/s44182-026-00100-4](https://www.nature.com/articles/s44182-026-00100-4). Módulos impresos en 3D con puertas lógicas neumáticas integradas. Un oscilador en anillo, alimentado por una presión de suministro constante, genera la onda sin electrónica. Dos versiones: setae pasivas (v1.0) y setae retráctiles (v2.0). — [npj Robotics](https://www.nature.com/articles/s44182-026-00100-4)
- Liu, Li y Zuo, «Actuation and design innovations in earthworm-inspired soft robots: A review», *Frontiers in Bioengineering and Biotechnology* 11:1088105 (2023), DOI [10.3389/fbioe.2023.1088105](https://pmc.ncbi.nlm.nih.gov/articles/PMC9989016/). Revisión de robots de un segmento y de varios, clasificados por actuador (neumático, eléctrico, hidráulico, magnético, híbrido y métodos emergentes). El texto dice que la mejora del sistema de control no entra en el tema de la revisión, y más adelante que los métodos de control y las innovaciones de sensado no se tratan por eso. — [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC9989016/)
- Boyle, Berri y Cohen, «Gait Modulation in *C. elegans*: An Integrated Neuromechanical Model», *Frontiers in Computational Neuroscience* 6:10 (2012), DOI [10.3389/fncom.2012.00010](https://pmc.ncbi.nlm.nih.gov/articles/PMC3296079/). Modelo de simulación de la marcha hacia adelante: circuito neuromuscular con retroalimentación propioceptiva, acoplado a un cuerpo y a un medio físico. El artículo toma como premisa biológica un continuo desde el arrastre lento (0,5 Hz, longitud de onda corta) en gel hasta el nado rápido (2 Hz, longitud de onda larga) en líquido, y afirma que el modelo reproduce toda la transición nado–arrastre, y también medios heterogéneos, sin otro mecanismo de modulación que la respuesta propioceptiva al medio. No es un robot. — [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC3296079/)
- Izquierdo y Beer, «From head to tail: a neuromechanical model of forward locomotion in *Caenorhabditis elegans*», *Philosophical Transactions of the Royal Society B* 373:20170374 (2018), DOI [10.1098/rstb.2017.0374](https://pmc.ncbi.nlm.nih.gov/articles/PMC6158225/). Simulación. Circuito de motoneuronas de la cabeza (SMD y RMD) más unidades repetidas del cordón nervioso ventral, músculos y el cuerpo mecánico de Boyle et al. (2012), en agar. 30 parámetros libres, ajustados con un algoritmo evolutivo para igualar la velocidad media del gusano en agar, fijada en el artículo en 0,22 mm/s. 100 corridas; 46 soluciones con aptitud de al menos 0,95. El cuerpo del modelo mide aproximadamente 1 mm y tiene 50 segmentos (153 grados de libertad). Código: [github.com/edizquierdo/RoyalSociety2018](https://github.com/edizquierdo/RoyalSociety2018). — [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC6158225/)
- Olivares, Izquierdo y Beer, «A Neuromechanical Model of Multiple Network Rhythmic Pattern Generators for Forward Locomotion in *C. elegans*», *Frontiers in Computational Neuroscience*, 18 de febrero de 2021, DOI [10.3389/fncom.2021.572339](https://www.frontiersin.org/journals/computational-neuroscience/articles/10.3389/fncom.2021.572339/full). Simulación. Pregunta explícita: si una cadena de generadores de ritmo de red en el cordón ventral puede producir la onda de la marcha hacia adelante sin neuronas marcapasos y sin retroalimentación de receptores de estiramiento, y sin neuronas fuera del cordón. El cuerpo y el medio son los de Boyle et al. (2012); los músculos, los de Izquierdo y Beer (2018). Siete subunidades. El resumen dice que hay varias configuraciones compatibles con ciertos aspectos de la cinemática en agar, y que las uniones comunicantes entre clases de motoneuronas pueden coordinar esos generadores. — [Frontiers](https://www.frontiersin.org/journals/computational-neuroscience/articles/10.3389/fncom.2021.572339/full)
- Zhao, Wang, Jiang, Ma, Ma, He, Du, Ma y Huang, «An integrative data-driven model simulating *C. elegans* brain, body and environment interactions», *Nature Computational Science*, 16 de diciembre de 2024, [https://www.nature.com/articles/s43588-024-00738-w](https://www.nature.com/articles/s43588-024-00738-w). BAAIWorm: 136 de las 302 neuronas, cuerpo de 96 músculos y 3.341 tetraedros, entorno fluido 3D. Lazo cerrado en simulación: la concentración de un atractor entra como corriente en las neuronas sensoriales y una matriz de lectura (reservorio) pasa el potencial de 80 motoneuronas a 96 fuerzas musculares. El artículo dice que la integración en OpenWorm del sistema nervioso (c302) y del cuerpo (Sibernetic) es en lazo abierto, sin retroalimentación del entorno. — [Nature Computational Science](https://www.nature.com/articles/s43588-024-00738-w)
- «Mechanical intelligence simplifies control in terrestrial limbless locomotion», *Science Robotics*, DOI [10.1126/scirobotics.adi2243](https://www.science.org/doi/10.1126/scirobotics.adi2243). El extracto de la página no trae la línea de autores. Compara *C. elegans* en redes de pilares con un modelo robofísico de 86 cm y siete articulaciones, actuado por cables bilaterales. Con control en lazo abierto y una compliancia generalizada G = 0,75, la cinemática y la eficiencia de onda se acercan a las del nematodo. Un sensor de fuerza en la cabeza añade un reflejo de inversión de la onda. No es un gusano blando peristáltico. — [Science Robotics](https://www.science.org/doi/10.1126/scirobotics.adi2243)
- Ge, Calderón y Pérez-Arancibia, «An Earthworm-Inspired Soft Crawling Robot Controlled by Friction», preprint [arXiv:1707.04084](https://ar5iv.labs.arxiv.org/html/1707.04084). Se abrió el HTML. El resumen describe actuadores neumáticos, control de la fricción en los extremos y controladores de realimentación en tiempo real para el arrastre. No se extrajo de ese HTML una velocidad ni una distancia, así que no se cita ninguna.

### Inferences

- «Línea Izquierdo» y «línea Cohen» no son escuelas enfrentadas en estos papers: Izquierdo y Beer (2018) reimplementan el cuerpo de Boyle, Berri y Cohen (2012), y Olivares et al. (2021) acopla ese cuerpo a un circuito distinto a propósito (sin estiramiento). La disputa abierta entre ellos es el mecanismo de la onda: propiocepción posterior corta (Izquierdo y Beer) frente a generadores de red en el cordón sin propiocepción (Olivares, Izquierdo y Beer).
- BAAIWorm no sustituye a esos modelos neuromecánicos. Optimiza pesos para parecerse a una matriz de correlación de calcio y luego lee el reservorio; no demuestra el mismo tipo de mecanismo de marcha que Izquierdo y Beer o que Boyle, Berri y Cohen.
- La revisión de 2023 (Liu, Li y Zuo) cubre actuadores y velocidades normalizadas, y deja fuera el control y el sensado. No cierra la pregunta de autonomía.

### Gaps

- No se abrió el artículo de *Cyborg and Bionic Systems* (DOI 10.34133/cbsystems.0204) cuyo resumen de búsqueda menciona 6,65 mm/s. Esa cifra no se usa.
- No se abrió la página de documentación del robot de OpenWorm ni el artículo de Sarma et al. (2018) más allá de la cita que hace BAAIWorm. Lo que se dice de OpenWorm sale solo de Zhao et al. (2024).
- No se abrió Dong et al., *Science Robotics* 6, eabe3950 (2021), ni el artículo de *Nature Machine Intelligence* de 2024 sobre aprendizaje por refuerzo acoplado a un *C. elegans* vivo. Un gusano vivo estimulado con luz no es un robot; al no abrirse, no entra en los hallazgos.
- Del modelo de Boyle, Berri y Cohen no se extrajo una velocidad del modelo en mm/s ni el número de unidades neurales; solo la premisa biológica de 0,5 Hz y 2 Hz y la afirmación cualitativa de que la transición queda reproducida.
- De Olivares, Izquierdo y Beer (2021) no se extrajeron velocidades ni longitudes de onda del apartado de resultados; solo el resumen y los métodos.

## Qué sistemas sienten y actúan sin una orden externa continua, y cuáles van en lazo abierto o teleoperados

### Takeaway

En los papers abiertos, «autónomo» no significa lo mismo. El único sistema con batería y microcontrolador dentro del cuerpo, que avanza sin un ordenador externo durante esa prueba, es el Meshworm en marcha de onda corta. Su lazo cerrado con aprendizaje iterativo es otro experimento, sobre el periodo de actuación, y el artículo no dice que ese lazo corriera dentro del cuerpo. Los robots neumáticos de Das o bien obedecen marchas escritas en un microcontrolador que gobierna electroválvulas, o bien oscilan solos mientras haya una presión constante, sin sensores. El robot de *Science Robotics* anda en lazo abierto; el único cierre es un reflejo de inversión ante un choque de la cabeza. Ningún paper abierto muestra teleoperación continua por una persona.

### Cited Findings

- Meshworm, implementación autónoma: placa con ATmega88PA, ocho salidas digitales, regulador elevador y baterías Li-Poly, metidos en el tubo. Con esa placa se usó la marcha de onda corta y se midió una velocidad lineal media de 3 mm/s. La bajada respecto del ensayo con el ordenador externo se atribuye a que la placa rígida estorba la deformación del segmento. El texto dice que la placa «incluye ocho canales A/D de 10 bits hacia una implementación en lazo cerrado»: la frase es prospectiva para ese hardware. — [PDF](https://softrobotics.wpi.edu/papers/2013-Seok-TransMechat.pdf)
- Meshworm, ensayos de marcha con herramienta externa: controlador en LabVIEW y NI Single-Board RIO (sbRIO-9642). No es el ensayo de la placa metida en el cuerpo. — [PDF](https://softrobotics.wpi.edu/papers/2013-Seok-TransMechat.pdf)
- Meshworm, cuatro controladores en un prototipo de cuatro segmentos con potenciómetros lineales: lazo abierto de paso fijo, bang-bang, aprendizaje iterativo que maximiza deflexión/tiempo, y aprendizaje iterativo que penaliza la energía. El artículo los compara en velocidad y potencia; no dice que el aprendizaje iterativo corriera en el ATmega metido en el tubo. El aprendizaje iterativo ajusta el periodo de actuación de cada segmento a partir de ensayos anteriores; no es una política que elija acciones según un objetivo en el terreno. — [PDF](https://softrobotics.wpi.edu/papers/2013-Seok-TransMechat.pdf)
- Das et al. (2023): «las matrices de electroválvulas eran controladas por la placa microcontroladora para generar distintos patrones de marcha». Los patrones (EGP, CGP, MSGP) están definidos de antemano. El banco neumático forma parte del montaje experimental (figura 5b), no de un cuerpo que decida. No hay sensores de entorno en la locomoción descrita. — [PDF](https://www.iris.santannapisa.it/retrieve/ae081cd9-9093-4b79-93cd-7d5c0ee57d4f/2023_Das_An_earthworm%E2%80%91like_modular_soft_robot_for_locomotion_in_multi-terrain_environments.pdf)
- Das et al. (2026): una presión de suministro constante (2 bar en los ensayos) y el anillo de puertas neumáticas mantienen la onda sin electrónica y sin una secuencia de órdenes externa durante la marcha. La dirección de la onda (directa o retrógrada) y el patrón (NWP3, NWP4, IWP4) se eligen al cablear el circuito. El artículo dice que las implementaciones sin amarre son trabajo futuro, y que detectar contactos y adaptar la marcha solo con lógica neumática sigue abierto. En la discusión llaman al sistema un paso hacia robots autónomos, no un sistema que ya lo sea. — [npj Robotics](https://www.nature.com/articles/s44182-026-00100-4)
- *Science Robotics* (DOI 10.1126/scirobotics.adi2243): en las redes de pilares, en terreno abierto, en medio granular, en canales y en un montón de piedras, el robot ejecuta una plantilla de onda viajera en lazo abierto. La compliancia G está fijada por el experimentador. El lazo cerrado solo aparece en la condición de inversión: un conjunto de resistencias sensibles a la fuerza en la cabeza invierte la onda si el choque es fuerte y anguloso. Los autores escriben que, como G se puede cambiar, añadir sensores podría permitir que el robot aprenda o elija G en tiempo real; lo formulan como una posibilidad, no como un resultado. — [Science Robotics](https://www.science.org/doi/10.1126/scirobotics.adi2243)
- Liu, Li y Zuo (2023): «la realización de robots neumáticos sin amarre es un problema mayor que hay que resolver antes de que puedan aplicarse de forma general. Depende del diseño de válvulas neumáticas pequeñas y de fuentes de aire.» El objetivo que enuncian es hacer los robots blandos «más autónomos, más sensibles y, al final, más parecidos a las lombrices». — [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC9989016/)
- Izquierdo y Beer (2018) y Boyle, Berri y Cohen (2012): el «lazo» es propiocepción dentro de la simulación. El ajuste evolutivo de Izquierdo y Beer ocurre antes de la marcha analizada; no es aprendizaje durante el desplazamiento. Olivares, Izquierdo y Beer (2021) quitan a propósito ese lazo sensorial y dejan solo la dinámica de red, también en simulación.
- BAAIWorm: el lazo sensorial cerrado (gradiente de comida → corriente → músculos → nueva posición) es simulado. Sin esa retroalimentación, una entrada periódica produce una trayectoria en Z. La matriz de lectura se entrena con 10 s de movimiento generado en el entorno simulado; los parámetros de la red quedan fijos. El artículo dice que el modelo «presenta un escenario» para probar algoritmos de aprendizaje por refuerzo; no informa un entrenamiento de ese tipo ni un robot físico. La plasticidad sináptica no está modelada. — [Nature Computational Science](https://www.nature.com/articles/s43588-024-00738-w)

### Inferences

- Conviene separar cuatro grados, porque los artículos los mezclan bajo «autónomo» o «sin electrónica»: (1) marcha escrita y ejecutada por un banco externo; (2) oscilador físico que no recibe órdenes mientras haya suministro; (3) cómputo y energía a bordo con la marcha ya escrita; (4) sensores a bordo que cambian la acción sin una orden continua. En lo abierto, (3) aparece en el Meshworm de 3 mm/s y (4) solo como el reflejo de inversión del robot de *Science Robotics* y como el aprendizaje iterativo del periodo de actuación del Meshworm, que no elige un camino.
- Un suministro neumático constante no es teleoperación, y tampoco es un robot que decide. Das et al. (2026) lo dicen al dejar el sensado y la adaptación como problema abierto.
- Ningún modelo de *C. elegans* abierto en esta sesión sale de la simulación. Cerrar el lazo con el agar o con un atractor virtual no es un robot que siente y actúa.

### Gaps

- No se abrió un paper que describa teleoperación continua (palanca o interfaz en tiempo real) de un gusano robótico. La ausencia en este conjunto no demuestra que no exista.
- No quedó escrito en Das et al. (2023) si el compresor está en la misma sala o a qué distancia van los tubos. Sí quedó escrito que las electroválvulas y la placa forman el montaje de los experimentos de locomoción.
- No quedó escrito si el aprendizaje iterativo del Meshworm corrió en la placa interna o en un ordenador de banco.

## Qué cifras de velocidad, distancia y terreno están en los papers

### Takeaway

Las velocidades físicas abiertas están entre unos 0,17 mm/s (Das 2023, granulado a 40 mm de profundidad) y 5,56 mm/s (Das 2026, espuma, setae activas, onda retrógrada NWP4). El gusano simulado de Izquierdo y Beer está ajustado a 0,22 mm/s en agar. No hay, en lo abierto, una distancia larga de misión: los recorridos medidos son de 10 cm (Das 2023, superficie plana) o 150 mm (Das 2026, laboratorio).

### Cited Findings

Meshworm, superficie plana, seguimiento por cámara. — [PDF](https://softrobotics.wpi.edu/papers/2013-Seok-TransMechat.pdf)

- Marcha de onda corta, con el ordenador externo: velocidad teórica 4,08 mm/s; medida 5,25 mm/s. Deformación media de segmento 10,02 mm; frecuencia 0,4 Hz. El artículo explica el exceso sobre la teoría porque el primer segmento no se enfría y la onda efectiva es más larga.
- La marcha de onda larga va más despacio que la corta; el texto no da un mm/s de esa marcha en el pasaje leído, solo las causas (menos deformación y más deslizamiento hacia atrás).
- Placa y batería dentro del cuerpo, marcha de onda corta: 3 mm/s de media.
- Prototipo de cuatro segmentos, paso fijo en lazo abierto: 0,495 mm/s a 3,783 W de media. Bang-bang: 0,478 mm/s y 3,386 W. Aprendizaje iterativo de velocidad máxima: 0,506 mm/s y 3,525 W, periodo medio de actuación 1.406 ms. Aprendizaje iterativo de velocidad y energía: 0,444 mm/s y 3,367 W, periodo medio 1.219 ms.
- El cuerpo aguanta golpes de martillo y que lo pisen durante la marcha; no hay una distancia ni un terreno irregular cuantificados en ese ensayo.
- Energía del actuador de bobina: 1.314 J/kg en un ensayo de elevación (resorte de 25 mm, 37,9 g, carrera 50 mm). No es velocidad del robot.

Das et al. (2023). Longitud del robot 350 mm. En superficie plana el recorrido fijado es 10 cm. Medio granular: cuentas elípticas de polioximetileno de 4 mm. Tubo de policarbonato de 60 mm de diámetro interior. — [PDF](https://www.iris.santannapisa.it/retrieve/ae081cd9-9093-4b79-93cd-7d5c0ee57d4f/2023_Das_An_earthworm%E2%80%91like_modular_soft_robot_for_locomotion_in_multi-terrain_environments.pdf)

- Superficie plana, sin setae: 0,45 mm/s (marcha de elongación) y 0,5 mm/s (marcha combinada).
- Superficie plana, con setae: 1,25 mm/s (elongación) y 1,35 mm/s (combinada).
- Superficie del granulado, sin setae en los ensayos de profundidad: 0,68 mm/s (elongación) y 0,71 mm/s (combinada).
- Granulado, 20 mm de profundidad: 0,36 mm/s (combinada) y 0,28 mm/s (elongación).
- Granulado, 40 mm de profundidad: 0,26 mm/s y 0,17 mm/s, en el mismo orden.
- Tubo: 0,65 mm/s con la marcha multisecuencial. Las figuras muestran sellos de tiempo a lo largo de 70 s; el texto no da una longitud de tubo recorrida.
- Fuerza bloqueada del módulo: del orden de 50–60 N a 1 bar; el texto cita un máximo de 56,3 N. Fuerza radial traducida: hasta 9,72 N (gel, 60 ml) y 9,65 N (gel, 50 ml) en aire.
- La tabla 1 del mismo artículo lista, para este robot, Pl—1,23, Gr—0,71 y Pi—0,65 mm/s. El 0,71 y el 0,65 coinciden con la prosa; el 1,23 de la superficie plana no coincide con el 1,35 mm/s de la marcha combinada con setae en el texto. Se dejan las dos cifras, sin elegir una.
- La misma tabla, atribuida a un trabajo anterior de R. Das et al., lista Pl—12,42±3,7 y Gr—4,38±0,8 mm/s. Es una cita de otro paper dentro de la tabla; ese paper no se abrió, así que no se usa como resultado propio.

Das et al. (2026). Cada condición única se repitió 5 veces. En el laboratorio el robot recorre 150 mm. Masas: versión 1.0 de cuatro módulos, 191 g; versión 2.0 de cuatro módulos, 224,4 g; versión 1.0 de tres módulos, 139 g; versión 2.0 de tres módulos, 178,2 g. Frecuencias del oscilador: 0,23 Hz (NWP3 e IWP4) y 0,167 Hz (NWP4). Presión de conmutación aproximada: 1,5 bar, y cerca de 1,75 bar en la cuarta puerta de las configuraciones de cuatro módulos. Coeficiente de fricción medio: espuma 0,48, 0,50 y 0,52 a 200, 300 y 400 mm/min; textil 1,00, 1,01 y 1,02. — [npj Robotics](https://www.nature.com/articles/s44182-026-00100-4)

- Espuma, setae pasivas, ondas directas: 4,22 mm/s (NWP3), 3,79 (NWP4), 4,25 (IWP4). Retrógradas: 4,72, 4,36 y 3,75 mm/s.
- Desvío lateral en 150 mm, versión 1.0, NWP3, espuma: 25,5 ± 10,4 mm (directa) y 6,3 ± 3,8 mm (retrógrada).
- Espuma, setae retráctiles, directas: 2,87 mm/s (NWP3) y 3,38 (NWP4); IWP4 directa no genera fricción suficiente y resbala de continuo. Retrógradas: 3,37, 5,56 y 3,92 mm/s.
- Textil, setae pasivas, directas: 1,96 mm/s (NWP4) y 3,57 (IWP4); NWP3 directa no se mueve. Retrógradas: 3,95, 3,58 y 2,94 mm/s.
- Textil, setae retráctiles: la única marcha que funciona es NWP3 directa, 2,64 mm/s, con desvío lateral medio de 50,1 ± 19,1 mm.
- Hormigón de árido expuesto, NWP3 con setae pasivas: aproximadamente 1,89 mm/s (directa) y 1,58 mm/s (retrógrada).
- Tubo de acrílico: solo la onda retrógrada sostiene la marcha, aproximadamente 1,89 mm/s; la directa no.
- Hierba, suelo mojado y grava: el texto dice que no hubo locomoción sostenida (figura suplementaria). No hay velocidad de esos tres medios.
- Coste de transporte ≳ 4000. El artículo lo compara, como orden de magnitud, con el de la lombriz *Aporrectodea caliginosa* durante la excavación, del orden de 10^4, y advierte que la escala y el modo no coinciden.

Izquierdo y Beer (2018), simulación en agar, no robot. — [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC6158225/)

- Velocidad objetivo: 0,22 mm/s, medida como distancia euclídea del centro del cuerpo en 50 s simulados.
- El conjunto de 46 soluciones: frecuencias en [0,34, 0,43] y longitudes de onda en [0,70, 0,96], frente a intervalos de la literatura citados en la misma frase, [0,25, 0,58] y [0,45, 0,83]. La frase no repite la unidad. El extremo 0,96 queda por encima del extremo superior de literatura que la misma frase cita para la longitud de onda (0,83); el artículo aun así dice que caen dentro de ese intervalo.
- En la solución analizada al detalle, quitar las uniones comunicantes entre unidades sube la amplitud de la curvatura un 22 %, baja la velocidad al 88,7 % y cambia la longitud de onda de 0,81 a 0,68. La frase tampoco repite la unidad.
- Coeficientes de arrastre en agar usados en el modelo: C∥ = 3,2 × 10⁻³ kg s⁻¹ y C⊥ = 128 × 10⁻³ kg s⁻¹.

*Science Robotics*, DOI 10.1126/scirobotics.adi2243. La velocidad que el texto define es la eficiencia de onda η = vCoM / vwave, no un mm/s. Los valores de η están en figuras; el extracto no da un número único de η ni una distancia en metros del montón de piedras. — [Science Robotics](https://www.science.org/doi/10.1126/scirobotics.adi2243)

- Nematodos: redes con L/d = 0 (fluido abierto), 1,8 (rala), 2,8 (media) y 3,3 (densa). n = 26 individuos en abierto y rala, n = 20 en media, n = 24 en densa.
- Robot: tres repeticiones por valor de G (de 0 a 1,5 en pasos de 0,25) y por entorno. G = 0,75 es el valor en el que el texto sitúa máximos locales de η en los entornos con obstáculos. Con G ≤ 0,5 el robot se atasca a menudo; con G ≥ 1,5 no genera empuje suficiente.
- Amplitudes y frecuencias espaciales de la plantilla, copiadas de la cinemática del nematodo: A = 46°, 48°, 51° y 72°, y ξ = 0,82, 0,80, 0,58 y 1,02, para abierto, ralo, medio y denso.
- Choques de cabeza, n ≈ 100 en cada sistema: 33,6 % clasificados como pandeo en el robot (pausa de fase > 0,5 s) y 28,6 % en el nematodo (pausa > 0,2 s).
- Montón de piedras, lazo abierto: G = 0,75 atraviesa; G = 0 no negocia los obstáculos; G = 1,5 no genera empuje suficiente. El coste de transporte mecánico tiene mínimos locales en G intermedios; el extracto no da el valor.
- Número de costa: el robot ~10⁻³, el nematodo en fluido ~10⁻². Anisotropía de arrastre de las ruedas del robot ~1,6:1.

Liu, Li y Zuo (2023), cifras de la comparación, no de un robot nuevo. — [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC9989016/)

- La mayoría de los robots de la revisión caen entre 0,01 y 0,1 longitudes de cuerpo por segundo. Casi la mitad se mueve a velocidades parecidas a las de las lombrices (el texto remite a un triángulo amarillo de la figura 18; no se transcribió la velocidad de la lombriz de esa figura).
- Longitudes de laboratorio, en general, entre 10 y 1.000 mm; las que el texto llama de uso práctico, por encima de 1.000 mm.
- Velocidad dividida por el diámetro del cuerpo: la mayoría entre 0,01 y 1 diámetros por segundo, con diámetros sobre todo entre 10 y 100 mm.
- Carga citada de la literatura de la revisión: de 1,47 N (Hu y Cheneler, 2021) a 52 N (Omori et al., 2013). Esos dos papers no se abrieron; la cifra se reporta solo como lo que la revisión afirma.
- La revisión dice que sigue habiendo una brecha entre los robots mayoritarios y las lombrices, sobre todo en velocidad dividida por el diámetro.

BAAIWorm no publica una velocidad del cuerpo simulado en mm/s en los pasajes leídos. Sí publica: 136 neuronas; compartimentos de neurita de menos de 2 μm; error cuadrático medio de 0,076 entre la matriz de correlación simulada y la de 65 neuronas del experimento de calcio; paso de red 5/3 ms y paso del cuerpo 100 ms, sincronizados cada 100 ms; cuerpo de 984 vértices, 3.341 tetraedros y 1.466 triángulos; 4.558 restricciones musculares y 3.341 de elasticidad. El entorno es un cubo de arista de unas 1.200 veces la longitud del gusano. La trayectoria en lazo cerrado se describe como zigzag parecido al experimento, sin una distancia. — [Nature Computational Science](https://www.nature.com/articles/s43588-024-00738-w)

### Inferences

- Las velocidades de unos pocos mm/s en robots de decenas de centímetros y la de 0,22 mm/s del modelo de 1 mm no se pueden restar una de otra. El medio tampoco es el mismo: fricción seca o granulado frente a arrastre viscoso lineal en agar.
- Donde el paper da dos cifras para el mismo caso (1,35 mm/s en prosa y 1,23 mm/s en la tabla de Das et al. 2023), la medición no está cerrada en el propio artículo.
- «Terreno» en estos papers es mesa, espuma, tela, granulado de laboratorio, tubo, hormigón, o un montón de piedras. Hierba, suelo mojado y grava ya rompen el robot sin electrónica de 2026. No hay una distancia de exploración medida en suelo natural.

### Gaps

- No se transcribieron las celdas de velocidad de la tabla 1 de Das et al. (2026) ni los puntos de las figuras de eficiencia de onda de *Science Robotics*. Esas cifras siguen sin extraer.
- No se abrió el paper de la fila «R. Das et al.» de la tabla de 2023 (12,42 mm/s en plano).
- Boyle, Berri y Cohen (2012): sin mm/s del modelo en lo leído.
- Olivares, Izquierdo y Beer (2021): sin cifras de velocidad en lo leído más allá del planteamiento.

## Qué contaría como hueco no explotado entre un *C. elegans* simulado y un robot físico que aprende

### Takeaway

El hueco está en la intersección, no en cada pieza por separado. Hace falta un cuerpo físico, sensores que cambien la acción sin una orden externa continua, y una actualización de la conducta a partir de las pruebas del propio robot, con la velocidad y el terreno escritos en el paper. Ningún artículo abierto junta las tres cosas. Lo más cerca son piezas sueltas: parámetros evolutivos o un reservorio solo en simulación; un aprendizaje iterativo del tiempo de calentamiento de una bobina; un reflejo de inversión ya programado; y una frase que deja para más adelante aprender la compliancia o sentir el contacto.

### Cited Findings

- Izquierdo y Beer (2018) ajustan 30 parámetros con un algoritmo evolutivo para clavar 0,22 mm/s en agar simulado. El conjunto reproduce, sin haberlo puesto en la aptitud, un intervalo de frecuencias y de longitudes de onda. Eso es ajuste fuera de línea de un modelo, no un robot que aprende. El artículo deja como trabajo futuro casar el modelo con manipulaciones optogenéticas y físicas. — [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC6158225/)
- Olivares, Izquierdo y Beer (2021) muestran que, en simulación, una cadena de generadores de red sin receptores de estiramiento también puede producir marcha hacia adelante compatible con parte de la cinemática. El mecanismo de la onda sigue sin estar cerrado entre este paper y el de 2018. — [Frontiers](https://www.frontiersin.org/journals/computational-neuroscience/articles/10.3389/fncom.2021.572339/full)
- BAAIWorm (2024) cierra en simulación un lazo con un atractor, pero: modela 136 de 302 neuronas; la única conducta es el zigzag; la propiocepción, la temperatura y los estímulos mecánicos quedan para después; los parámetros físicos del cuerpo «no correspondían con precisión» a los del animal porque eran difíciles de medir; no hay plasticidad sináptica; la lectura muscular es una matriz lineal entrenada con 10 s de simulación. El artículo dice que ese lazo sería un escenario para aprendizaje por refuerzo, no que lo hayan corrido. — [Nature Computational Science](https://www.nature.com/articles/s43588-024-00738-w)
- El mismo artículo dice que la integración de OpenWorm (c302 y Sibernetic) carece de retroalimentación del entorno. — [Nature Computational Science](https://www.nature.com/articles/s43588-024-00738-w)
- *Science Robotics* (DOI 10.1126/scirobotics.adi2243): un robot físico ya reproduce, en lazo abierto y con la compliancia bien puesta, la cinemática del nematodo en pilares, y un reflejo de inversión amplía el rango de G que atraviesa la red densa. Los autores escriben que hace falta un modelo mecánico para elegir G según el terreno, y que sensores podrían permitir aprender o seleccionar G en tiempo real, incluso G distinto en cada articulación. No informan ese aprendizaje. — [Science Robotics](https://www.science.org/doi/10.1126/scirobotics.adi2243)
- Das et al. (2026): «detectar contactos externos y permitir una adaptación de la marcha al estímulo usando solo lógica neumática sigue siendo un problema abierto». El mismo robot no sostiene la marcha en hierba, suelo mojado ni grava. El coste de transporte es ≳ 4000. — [npj Robotics](https://www.nature.com/articles/s44182-026-00100-4)
- Meshworm: el aprendizaje iterativo cambia el tiempo de corriente de cada segmento para ir más rápido o gastar menos, con velocidades de 0,444 a 0,506 mm/s en el prototipo de cuatro segmentos. No hay un conectoma, no hay un objetivo espacial y no hay un terreno distinto de la superficie de ensayo. La discusión dice que harían falta placas flexibles y muchas baterías pequeñas para un sistema del todo blando, y que con menos de diez segmentos no se forma una onda como la de la lombriz, que tiene cerca de cien. — [PDF](https://softrobotics.wpi.edu/papers/2013-Seok-TransMechat.pdf)
- Liu, Li y Zuo (2023): el control y el sensado quedan fuera de la revisión; el neumático sin amarre depende de válvulas y fuentes de aire pequeñas que aún no dan por resueltas; el objetivo de «más autónomos, más sensibles» se enuncia como meta, no como logro. — [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC9989016/)

### Inferences

- Un resultado que llenaría el hueco, y que estos papers no contienen, sería: un robot físico cuyo controlador se inicializa con un modelo neuromecánico de *C. elegans* (propiocepción de Izquierdo y Beer, o generadores del cordón de Olivares, o el lazo sensorial de BAAIWorm), que actualiza esa conducta con las pruebas del robot y no solo con una aptitud evolutiva en agar simulado, que no recibe una marcha ni una presión mandada paso a paso desde fuera, y que publica velocidad, distancia y terreno del antes y del después. El reflejo de inversión ya programado y el aprendizaje iterativo del tiempo de una bobina no llegan a eso.
- Aunque ese robot existiera, los papers abiertos marcan tres translationes que nadie ha medido: de arrastre viscoso a 0,22 mm/s en un cuerpo de 1 mm a fricción seca en un cuerpo de decenas de centímetros; de 136 neuronas y un reservorio lineal a músculos reales; de una compliancia G fijada a mano a una G elegida por el propio robot según el suelo. Das et al. (2026) ya muestran que el mismo oscilador que hace ~4 mm/s en espuma no sostiene la marcha en hierba, suelo mojado ni grava: un aprendizaje que solo se probara en espuma o en agar simulado no cubriría el fallo que el paper deja medido.
- «Que aprende» tiene que distinguirse del ajuste evolutivo previo. Izquierdo y Beer y Olivares, Izquierdo y Beer usan evolución para buscar parámetros. Eso explora mecanismos; no es un agente que cambia de conducta mientras se desplaza.

### Gaps

- No se buscó de forma exhaustiva un paper posterior a 2024 que pusiera un modelo de *C. elegans* a bordo de un robot y lo entrenara en hardware. Si existe y no salió en las búsquedas de esta sesión, este hueco podría estar ya ocupado. Las búsquedas hechas no lo abrieron.
- El artículo de *Nature Machine Intelligence* (2024) sobre un agente de aprendizaje por refuerzo acoplado por optogenética a un nematodo vivo no se abrió. Aunque se abriera, el cuerpo que se mueve sería el animal, no un robot físico.
- No se abrió un experimento que transfiera los parámetros evolutivos de Izquierdo y Beer (2018) a ningún hardware.
