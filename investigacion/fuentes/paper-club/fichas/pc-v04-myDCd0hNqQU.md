# Why Robotics Still Isn't Solved - But Could Be Soon | YC Paper Club

Ficha `pc-v04` · video 4 de 7 de la lista Paper Club · consultada el 2026-10-13.

## Lo que la página mostró

- **URL:** <https://www.youtube.com/watch?v=myDCd0hNqQU>
- **Duración:** 1:24:13 (5052 s en los datos de la página).
- **Fecha de publicación que da la página:** 2026-08-08.
- **Canal:** Y Combinator.
- **Estado del contenido:** `abierto`. Transcripción publicada en <https://www.ycrootaccess.com/p/memory-simtoolreal-and-world-action> (enlazada en la descripción del video). Abrió sin sesión; el texto completo está en la copia local `investigacion/local/root-access/memory-simtoolreal-and-world-action.md`, que no se versiona. Las notas están al final de esta ficha.

## Obras con identificador en la descripción

### MEM: Multi-Scale Embodied Memory for Vision Language Action Models

- **Ficha:** `pc-p-2603.03596`.
- **Autores (registro de arXiv):** Marcel Torne; Karl Pertsch; Homer Walke; Kyle Vedder; Suraj Nair; Brian Ichter; Allen Z. Ren; Haohuan Wang; Jiaming Tang; Kyle Stachowicz; Karan Dhabalia; Michael Equi; Quan Vuong; Jost Tobias Springenberg; Sergey Levine; Chelsea Finn; Danny Driess.
- **Año:** 2026 (primera versión, 2026-03-04).
- **Identificador abierto:** arXiv:2603.03596, <https://arxiv.org/abs/2603.03596>. Registro leído por la API de arXiv el 2026-10-13; versión vigente v2, del 2026-03-08.
- **Qué se leyó:** el registro y el resumen. El texto completo no.
- **Mecanismo:** Memoria en dos escalas: una de horizonte corto con lo reciente comprimido y otra de horizonte largo en texto. Según la charla, la de horizonte largo es un texto corto que la política de alto nivel vuelve a escribir en cada paso y recibe de vuelta; qué anotar en él se decidió de antemano y se enseñó con datos anotados.
- **En este repositorio:** En el kit del experimento con modelo: mantener fuera de la compactación un texto corto con el enunciado y las etapas ya hechas, que el agente reescribe, y dejar que se compacte solo lo reciente. Qué debe anotar ese texto habría que fijarlo antes: aquí no se entrena nada.
- **Dónde lo nombra el código:** no lo nombra (git grep del nombre y de sus términos, sin resultados en texto, 2026-10-13).
- **Medición local:** experiments/gemma_developer_agent/hallazgos.json, «compactacion_del_contexto» (estado medido, vuelta 43): el texto literal del enunciado falta en las 1 531 peticiones posteriores a una compactación; sesiones resueltas 11 de 59 con compactación y 10 de 57 sin ella. Y «repeticiones_identicas» (decidido): la charla atribuye a la falta de memoria que una política repita el mismo error; aquí esas repeticiones se midieron sin relacionarlas con la compactación. Nada en docs/results/.
- **Contraste que lo descarta:** En las mismas tareas, las sesiones que conservan el enunciado literal después de compactar no resuelven más que las que lo pierden, con el criterio de decisión válida de CONTRIBUTING.md. Con ese resultado se descarta.

### Self-Supervised Bootstrapping of Action-Predictive Embodied Reasoning

- **Ficha:** `pc-p-2602.08167`.
- **Autores (registro de arXiv):** Milan Ganai; Katie Luo; Jonas Frey; Clark Barrett; Marco Pavone.
- **Año:** 2026 (primera versión, 2026-02-09).
- **Identificador abierto:** arXiv:2602.08167, <https://arxiv.org/abs/2602.08167>. Registro leído por la API de arXiv el 2026-10-13; versión vigente v2, del 2026-05-16.
- **Qué se leyó:** el registro y el resumen. El texto completo no.
- **Mecanismo:** Tratar el razonamiento como variable latente y quedarse con los pasos de razonamiento que predicen la acción correcta, en vez de una plantilla fija. Según la charla, cada traza se puntúa por tres cosas (que sea corta, que no sea trivial y que prediga la acción) y el razonamiento puede omitirse al ejecutar.
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

## Lo que dice la transcripción

Leídas el 2026-10-13 las dos primeras charlas (7:59 y 20:21) con sus preguntas. **El resto, desde 33:42,
no se leyó.** Copia local, no versionada: `investigacion/local/root-access/memory-simtoolreal-and-world-action.md`.
Son notas propias; las afirmaciones son de quienes hablan.

- **7:59, memoria en dos escalas** (ficha `pc-p-2603.03596`).
  - Sin memoria, la política no sabe cuánto lleva haciendo algo ni qué hizo ya, y repite el mismo error
    sin reaccionar. Añadir memoria sin más empeora el resultado y encarece el entrenamiento y la
    inferencia; por eso la comprimen.
  - La memoria larga es un texto corto, una especie de borrador, que la política de alto nivel predice en
    cada paso y vuelve a recibir. Es legible, y por eso se puede supervisar y depurar.
  - En las preguntas reconocen el límite: qué debe guardar ese texto lo decidieron ellos de antemano y
    lo anotaron a mano; aprender qué conviene recordar queda como trabajo futuro.
- **20:21, razonamiento que predice la acción** (ficha `pc-p-2602.08167`).
  - Un componente propone tipos de razonamiento y otro los puntúa por tres cosas: que sea corto, que no
    sea trivial y que prediga la acción.
  - Su conclusión: razonar de forma selectiva rinde más que razonar sobre todo, y un razonamiento válido
    no es por eso útil. Planificar ayuda, pero no en cada paso.
  - El razonamiento se puede omitir al ejecutar y conservar lo que aportó al entrenar. Aclaran que qué
    tipos sobran depende del banco en que lo midieron.
