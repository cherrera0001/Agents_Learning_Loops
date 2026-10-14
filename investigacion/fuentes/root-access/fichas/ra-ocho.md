# Eight ML Papers, Explained by the Researchers Behind Them

Ficha `ra-ocho` · entrada de Root Access del 2026-08-06 · consultada el 2026-10-13.

- **URL:** <https://www.ycrootaccess.com/p/eight-ml-papers-explained-by-the>
- **Qué es:** una entrada que resume ocho trabajos presentados en una muestra de investigación y enlaza cada uno. No es una transcripción. Se leyó entera.
- **Copia local, no versionada:** `investigacion/local/root-access/eight-ml-papers-explained-by-the.md`.
- **Videos:** la entrada incrusta ocho videos de YouTube; ninguno se abrió.

Las frases de mecanismo salen del resumen de arXiv de cada obra. Las cifras que da la entrada son de sus autores y aquí no se usa ninguna.

## Obras

### Test-Time Scaling for Multistep Reasoning in Small Language Models via A* Search

- **Ficha:** `ra-p-astar-slm`, `no_abierto`: el enlace que da Root Access respondió HTTP 403; el título es el que escribe esa entrada, no el de un registro, y la obra no se cita.

### LeanAgent: Lifelong Learning for Formal Theorem Proving

- **Ficha:** `ra-p-2410.06209`.
- **Autores (registro de arXiv):** Adarsh Kumarappan; Mo Tiwari; Peiyang Song; Robert Joseph George; Chaowei Xiao; Anima Anandkumar.
- **Año:** 2024 (primera versión, 2024-10-08).
- **Identificador abierto:** arXiv:2410.06209, <https://arxiv.org/abs/2410.06209>. Registro leído por la API de arXiv el 2026-10-13; versión vigente v8, del 2025-03-06.
- **Qué se leyó:** el registro y el resumen. El texto completo no.
- **Mecanismo:** Aprendizaje continuo con un currículo: ordena los repositorios por dificultad estimada, actualiza un recuperador de premisas a medida que avanza y añade a su base las demostraciones logradas.
- **En este repositorio:** En el solver acotado: presentar las tareas de entrenamiento por dificultad creciente antes de consolidar lecciones, en lugar del orden actual. Solo la idea del orden; aquí no se entrena nada.
- **Dónde lo nombra el código:** no lo nombra (git grep de sus términos, sin resultados fuera de investigacion/, 2026-10-13).
- **Medición local:** ninguna en docs/results/: ninguna campaña compara órdenes de las tareas de entrenamiento.
- **Contraste que lo descarta:** Con las mismas tareas y las mismas semillas, el orden por dificultad da el mismo LearningGain que el orden actual. Con ese resultado se descarta.

### Diamond Maps: Efficient Reward Alignment via Stochastic Flow Maps

- **Ficha:** `ra-p-2602.05993`.
- **Autores (registro de arXiv):** Peter Holderrieth; Douglas Chen; Luca Eyring; Ishin Shah; Giri Anantharaman; Yutong He; Zeynep Akata; Tommi Jaakkola; Nicholas Matthew Boffi; Max Simchowitz.
- **Año:** 2026 (primera versión, 2026-02-05).
- **Identificador abierto:** arXiv:2602.05993, <https://arxiv.org/abs/2602.05993>. Registro leído por la API de arXiv el 2026-10-13; versión vigente v3, del 2026-05-16.
- **Qué se leyó:** el registro y el resumen. El texto completo no.
- **Mecanismo:** Para guiar un modelo generativo hacia una recompensa, estimar lo prometedor de un estado intermedio muestreando varios desenlaces en vez de uno.
- **En este repositorio:** No aplica: aquí no hay generación por flujo ni difusión.
- **Dónde lo nombra el código:** no lo nombra (git grep de sus términos, sin resultados fuera de investigacion/, 2026-10-13).
- **Medición local:** ninguna en docs/results/
- **Contraste que lo descarta:** no se propone.

### ChartNet: A Million-Scale, High-Quality Multimodal Dataset for Robust Chart Understanding

- **Ficha:** `ra-p-2603.27064`.
- **Autores (registro de arXiv):** Jovana Kondic; Pengyuan Li; Dhiraj Joshi; Isaac Sanchez; Ben Wiesel; Shafiq Abedin; Amit Alfassy; Eli Schwartz; Daniel Caraballo; Yagmur Gizem Cinar; Florian Scheidegger; Steven I. Ross; Daniel Karl I. Weidele; Hang Hua; Ekaterina Arutyunova; Roei Herzig; Zexue He; Zihan Wang; Xinyue Yu; Yunfei Zhao; Sicong Jiang; Minghao Liu; Qunshu Lin; Peter Staar; Luis Lastras; Aude Oliva; Rogerio Feris.
- **Año:** 2026 (primera versión, 2026-03-28).
- **Identificador abierto:** arXiv:2603.27064, <https://arxiv.org/abs/2603.27064>. Registro leído por la API de arXiv el 2026-10-13; versión vigente v2, del 2026-04-14.
- **Qué se leyó:** el registro y el resumen. El texto completo no.
- **Mecanismo:** Un conjunto de datos de gráficos generado desde código: recuperar el código de un gráfico, variarlo y volver a dibujarlo con sus datos exactos.
- **En este repositorio:** No aplica: el repositorio no trata gráficos.
- **Dónde lo nombra el código:** no lo nombra (git grep de sus términos, sin resultados fuera de investigacion/, 2026-10-13).
- **Medición local:** ninguna en docs/results/
- **Contraste que lo descarta:** no se propone.

### Relational Transformer: Toward Zero-Shot Foundation Models for Relational Data

- **Ficha:** `ra-p-2510.06377`.
- **Autores (registro de arXiv):** Rishabh Ranjan; Valter Hudovernik; Mark Znidar; Charilaos Kanatsoulis; Roshan Upendra; Mahmoud Mohammadi; Joe Meyer; Tom Palczewski; Carlos Guestrin; Jure Leskovec.
- **Año:** 2025 (primera versión, 2025-10-07).
- **Identificador abierto:** arXiv:2510.06377, <https://arxiv.org/abs/2510.06377>. Registro leído por la API de arXiv el 2026-10-13; versión vigente v3, del 2026-03-02.
- **Qué se leyó:** el registro y el resumen. El texto completo no.
- **Mecanismo:** Un transformer que recibe la base de datos relacional como grafo, sin aplanarla en una tabla.
- **En este repositorio:** No aplica: el repositorio no predice sobre datos relacionales.
- **Dónde lo nombra el código:** no lo nombra (git grep de sus términos, sin resultados fuera de investigacion/, 2026-10-13).
- **Medición local:** ninguna en docs/results/
- **Contraste que lo descarta:** no se propone.

### SAGE: Training Smart Any-Horizon Agents for Long Video Reasoning with Reinforcement Learning

- **Ficha:** `ra-p-2512.13874`.
- **Autores (registro de arXiv):** Jitesh Jain; Jialuo Li; Zixian Ma; Jieyu Zhang; Chris Dongjoo Kim; Sangho Lee; Rohun Tripathi; Tanmay Gupta; Christopher Clark; Humphrey Shi.
- **Año:** 2025 (primera versión, 2025-12-15).
- **Identificador abierto:** arXiv:2512.13874, <https://arxiv.org/abs/2512.13874>. Registro leído por la API de arXiv el 2026-10-13; versión vigente v2, del 2026-03-29.
- **Qué se leyó:** el registro y el resumen. El texto completo no.
- **Mecanismo:** Un agente que ajusta cuántos pasos de razonamiento y qué herramientas usa según la longitud del video y la pregunta, entrenado por refuerzo.
- **En este repositorio:** No aplica: es razonamiento sobre video y entrenamiento por refuerzo.
- **Dónde lo nombra el código:** no lo nombra (git grep de sus términos, sin resultados fuera de investigacion/, 2026-10-13).
- **Medición local:** ninguna en docs/results/
- **Contraste que lo descarta:** no se propone.

### Mechanistic interpretability for steering vision-language-action models

- **Ficha:** `ra-p-2509.00328`.
- **Autores (registro de arXiv):** Bear Häon; Kaylene Stocking; Ian Chuang; Claire Tomlin.
- **Año:** 2025 (primera versión, 2025-08-30).
- **Identificador abierto:** arXiv:2509.00328, <https://arxiv.org/abs/2509.00328>. Registro leído por la API de arXiv el 2026-10-13; versión vigente v1, del 2025-08-30.
- **Qué se leyó:** el registro y el resumen. El texto completo no.
- **Mecanismo:** Proyectar activaciones internas de una política de robot sobre su espacio de embeddings y amplificar grupos de ellas para dirigir su conducta.
- **En este repositorio:** No aplica: el experimento no tiene acceso a las activaciones del modelo.
- **Dónde lo nombra el código:** no lo nombra (git grep de sus términos, sin resultados fuera de investigacion/, 2026-10-13).
- **Medición local:** ninguna en docs/results/
- **Contraste que lo descarta:** no se propone.

### On the Fine-Grained Planning Abilities of VLM Web Agents

- **Ficha:** `ra-p-2025.findings-emnlp.1382`.
- **Autores (registro de ACL Anthology):** Surgan Jandial; Yinong Oliver Wang; Andrea Bajcsy; Fernando De la Torre.
- **Año:** 2025.
- **Identificador abierto:** doi:10.18653/v1/2025.findings-emnlp.1382, <https://aclanthology.org/2025.findings-emnlp.1382/>. Página del editor leída el 2026-10-13.
- **Qué se leyó:** título, autores, fecha y DOI del registro. Ni el resumen ni el texto completo.
- **Mecanismo y en este repositorio:** Jandial et al. (2025). Un diagnóstico barato: descomponer la planificación de un agente en capacidades sueltas (ordenar estados, predecir el siguiente, elegir entre acciones, reconocer un error) y medirlas con preguntas simples hechas con datos que ya existen. Del registro se leyeron título, autores y fecha; el mecanismo sale del resumen que publica Root Access, no del resumen del paper. En este repositorio: antes de gastar cuota, preguntar al modelo del kit sobre trayectorias ya rescatadas (cuál es el paso siguiente, si un paso fue un error).
- **Dónde lo nombra el código:** no lo nombra (git grep de sus términos, sin resultados fuera de investigacion/, 2026-10-13).
- **Medición local:** ninguna en docs/results/
- **Contraste que lo descarta:** Las notas del diagnóstico no ordenan las condiciones ya medidas igual que sus corridas completas. Con ese resultado no sirve de sustituto y se descarta.
