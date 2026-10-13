# Why Robotics Still Isn't Solved - But Could Be Soon | YC Paper Club

Ficha `pc-v04` · video 4 de 7 de la lista Paper Club · consultada el 2026-10-13.

## Lo que la página mostró

- **URL:** <https://www.youtube.com/watch?v=myDCd0hNqQU>
- **Duración:** 1:24:13 (5052 s en los datos de la página).
- **Fecha de publicación que da la página:** 2026-08-08.
- **Canal:** Y Combinator.
- **Estado del contenido:** `abierto`. La descripción enlaza una transcripción, <https://www.ycrootaccess.com/p/memory-simtoolreal-and-world-action>, que abrió (HTTP 200, con texto). En este PR no se tomó nada de ella: lo que sigue sale de los registros de arXiv.

## Obras con identificador en la descripción

### MEM: Multi-Scale Embodied Memory for Vision Language Action Models

- **Ficha:** `pc-p-2603.03596`.
- **Autores (registro de arXiv):** Marcel Torne; Karl Pertsch; Homer Walke; Kyle Vedder; Suraj Nair; Brian Ichter; Allen Z. Ren; Haohuan Wang; Jiaming Tang; Kyle Stachowicz; Karan Dhabalia; Michael Equi; Quan Vuong; Jost Tobias Springenberg; Sergey Levine; Chelsea Finn; Danny Driess.
- **Año:** 2026 (primera versión, 2026-03-04).
- **Identificador abierto:** arXiv:2603.03596, <https://arxiv.org/abs/2603.03596>. Registro leído por la API de arXiv el 2026-10-13; versión vigente v2, del 2026-03-08.
- **Qué se leyó:** el registro y el resumen. El texto completo no.
- **Mecanismo:** Memoria en dos escalas: una de horizonte corto con lo reciente comprimido y otra de horizonte largo en texto, que guarda qué etapas ya están hechas.
- **En este repositorio:** En el kit del experimento con modelo: mantener fuera de la compactación un texto corto con el enunciado y las etapas ya hechas, y dejar que se compacte solo lo reciente.
- **Dónde lo nombra el código:** no lo nombra (git grep del nombre y de sus términos, sin resultados en texto, 2026-10-13).
- **Medición local:** experiments/gemma_developer_agent/hallazgos.json, «compactacion_del_contexto» (estado medido, vuelta 43): el texto literal del enunciado falta en las 1 531 peticiones posteriores a una compactación; sesiones resueltas 11 de 59 con compactación y 10 de 57 sin ella. Mide la compactación del arnés, no una memoria en dos escalas. Nada en docs/results/.
- **Contraste que lo descarta:** En las mismas tareas, las sesiones que conservan el enunciado literal después de compactar no resuelven más que las que lo pierden, con el criterio de decisión válida de CONTRIBUTING.md. Con ese resultado se descarta.

### Self-Supervised Bootstrapping of Action-Predictive Embodied Reasoning

- **Ficha:** `pc-p-2602.08167`.
- **Autores (registro de arXiv):** Milan Ganai; Katie Luo; Jonas Frey; Clark Barrett; Marco Pavone.
- **Año:** 2026 (primera versión, 2026-02-09).
- **Identificador abierto:** arXiv:2602.08167, <https://arxiv.org/abs/2602.08167>. Registro leído por la API de arXiv el 2026-10-13; versión vigente v2, del 2026-05-16.
- **Qué se leyó:** el registro y el resumen. El texto completo no.
- **Mecanismo:** Tratar el razonamiento como variable latente y quedarse con los pasos de razonamiento que predicen la acción correcta, en vez de una plantilla fija que obliga a razonar sobre todo.
- **En este repositorio:** Solo la idea, sin entrenamiento: quitar de la instrucción del kit los pasos de razonamiento obligatorios cuya presencia en la trayectoria no distingue las sesiones resueltas de las demás.
- **Dónde lo nombra el código:** no lo nombra (git grep del nombre y de sus términos, sin resultados en texto, 2026-10-13).
- **Medición local:** experiments/gemma_developer_agent/hallazgos.json: dos pasos obligatorios propuestos y descartados en la vuelta 42 («reproductor_antes_de_editar», «guion_mapa_al_inicio»). Se midió cada paso por separado, no una selección por lo que predice la acción. Nada en docs/results/.
- **Contraste que lo descarta:** En las trayectorias ya rescatadas, ningún paso de razonamiento que la instrucción pide aparece con frecuencia distinta en las sesiones resueltas y en las no resueltas de las mismas tareas: no hay nada que seleccionar. Con ese resultado se descarta.

### SimToolReal: An Object-Centric Policy for Zero-Shot Dexterous Tool Manipulation

- **Ficha:** `pc-p-2602.16863`.
- **Autores (registro de arXiv):** Kushal Kedia; Tyler Ga Wei Lum; Jeannette Bohg; C. Karen Liu.
- **Año:** 2026 (primera versión, 2026-02-18).
- **Identificador abierto:** arXiv:2602.16863, <https://arxiv.org/abs/2602.16863>. Registro leído por la API de arXiv el 2026-10-13; versión vigente v3, del 2026-10-06.
- **Qué se leyó:** el registro y el resumen. El texto completo no.
- **Mecanismo:** Una sola política de aprendizaje por refuerzo entrenada en simulación sobre primitivas de objeto generadas por procedimiento, con el objetivo único de llevar cada objeto a una pose.
- **En este repositorio:** No aplica: robótica; aquí no hay simulación física ni política entrenada.
- **Dónde lo nombra el código:** no lo nombra (git grep del nombre y de sus términos, sin resultados en texto, 2026-10-13).
- **Medición local:** ninguna en docs/results/
- **Contraste que lo descarta:** no se propone: sin frase de qué haría en este repositorio
