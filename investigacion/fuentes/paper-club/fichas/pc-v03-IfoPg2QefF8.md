# Going In Deep On Data | YC Paper Club

Ficha `pc-v03` · video 3 de 7 de la lista Paper Club · consultada el 2026-10-13.

## Lo que la página mostró

- **URL:** <https://www.youtube.com/watch?v=IfoPg2QefF8>
- **Duración:** 52:35 (3155 s en los datos de la página).
- **Fecha de publicación que da la página:** 2026-08-20.
- **Canal:** Y Combinator.
- **Estado del contenido:** `abierto`. Transcripción publicada en <https://www.ycrootaccess.com/p/expert-supervision-diffusion-and> (la descripción no la enlaza: se localizó en el archivo del sitio y la entrada incrusta este mismo video). Abrió sin sesión; el texto completo está en la copia local `investigacion/local/root-access/expert-supervision-diffusion-and.md`, que no se versiona. Las notas están al final de esta ficha.

## Obras con identificador en la descripción

Ninguna. Ni el título ni la descripción traen un DOI o un identificador de arXiv. Los títulos de los capítulos no son fichas.

## Obra localizada por título

La descripción del video no la enlaza. Se buscó en la API de arXiv por las palabras del título de la charla y hubo un solo resultado, cuyo primer autor es el ponente que nombra la descripción.

### ATLAS: Adaptive Transfer Scaling Laws for Multilingual Pretraining, Finetuning, and Decoding the Curse of Multilinguality

- **Ficha:** `pc-p-2510.22037`.
- **Autores (registro de arXiv):** Shayne Longpre; Sneha Kudugunta; Niklas Muennighoff; I-Hung Hsu; Isaac Caswell; Alex Pentland; Sercan Arik; Chen-Yu Lee; Sayna Ebrahimi.
- **Año:** 2025 (primera versión, 2025-10-24).
- **Identificador abierto:** arXiv:2510.22037, <https://arxiv.org/abs/2510.22037>. Registro leído por la API de arXiv el 2026-10-13; versión vigente v2, del 2026-02-25.
- **Qué se leyó:** el registro y el resumen. El texto completo no.
- **Nota:** el título de la charla y el del registro no son iguales.
- **Mecanismo:** Una matriz de transferencia medida, no supuesta: cuánto ayuda o estorba cada fuente de datos a otra, por pares. Según la charla, la ayuda no es simétrica y no se deduce del parentesco entre lenguas.
- **En este repositorio:** En el solver acotado: medir la transferencia de un registro de fallo entre familias de tareas en los dos sentidos, en lugar de suponerla por similitud.
- **Dónde lo nombra el código:** no lo nombra (git grep de sus términos, sin resultados fuera de investigacion/, 2026-10-13).
- **Medición local:** docs/results/failure-transfer.md (H7): ningún umbral de similitud separa la transferencia útil de la dañina. No se comprobó si esa campaña guarda cada par en los dos sentidos.
- **Contraste que lo descarta:** En los pares de H7 con cambio, el efecto de A sobre B y el de B sobre A tienen siempre el mismo signo: la asimetría no aparece y medirla por sentido no aporta. Con ese resultado se descarta.

## Lo que dice la transcripción

Leída entera el 2026-10-13. Copia local, no versionada: `investigacion/local/root-access/expert-supervision-diffusion-and.md`.
Son notas propias; las afirmaciones y las cifras son de quienes hablan.

- **0:00, apertura.** El argumento es que los datos pesan más que la arquitectura: ante un modelo que
  falla, primero se miran los errores y se agrupan por causa. Coincide con lo que aquí ya hace el staff
  de experimento; no añade un mecanismo.
- **9:51, evaluación de agentes de código** (ficha `pc-v03-c1`). Dos ideas:
  - Un verificador escrito de antemano es fiable y rígido: castiga soluciones válidas que tomaron otro
    camino. Un juez que es un modelo es flexible y poco fiable: premia soluciones plausibles e
    incorrectas. Proponen un término medio: un experto escribe una especificación corta y un agente
    escribe, para cada parche, pruebas deterministas sobre el código que ese parche tocó; otro juez
    revisa que la corrida no haya hecho trampa.
  - Las tareas de los bancos habituales están sobreespecificadas; proponen enunciados cortos, como un
    mensaje de trabajo, y una medida que además de la corrección penaliza el parche hinchado.
  - La charla nombra un banco de pruebas y un método anterior de etiquetado, sin identificador. Una
    búsqueda por título en arXiv no encontró el banco: no tiene ficha.
- **28:44, modelos de lenguaje por difusión** (ficha `pc-v03-c2`). Lo que toca a este repositorio no es
  el modelo sino cómo arman sus tareas: generan entornos sintéticos y filtran o endurecen cada tarea
  según cuánto la resuelve el modelo, porque una tarea que siempre se resuelve, o nunca, no da señal.
  También dicen que un banco muy usado da notas altas que no se repiten con registros reales.
- **40:26, leyes de escala multilingües** (ficha `pc-p-2510.22037`). Miden cuánto ayuda o estorba cada
  fuente de datos a otra y arman una matriz. Dos resultados que el ponente subraya: la ayuda no es
  simétrica y no se deduce del parentesco entre lenguas; hay que medirla. Dice que el método vale para
  cualquier partición de los datos, no solo lenguas.

## Charlas con ficha propia

### `pc-v03-c1`

- **Mecanismo:** Un agente de validación: un experto escribe una especificación corta y un agente escribe, para cada parche, pruebas deterministas sobre el código que ese parche tocó; un juez revisa que la corrida no haga trampa. Es el término medio entre un verificador fijo, que rechaza soluciones válidas, y un juez que es un modelo, que acepta incorrectas. En este repositorio: una comprobación local del parche que no la escriba el agente evaluado, sino otro agente a partir de una especificación corta de la tarea.
- **Dónde lo nombra el código:** no lo nombra (git grep de sus términos, sin resultados fuera de investigacion/, 2026-10-13).
- **Medición local:** experiments/gemma_developer_agent/hallazgos.json, «reproductor_antes_de_editar» (descartado, vuelta 42): el reproductor que escribe el agente evaluado sale verde antes de editar en 18 de 27 sesiones malas. Mide una comprobación escrita por el propio agente, no por un agente de validación. Nada en docs/results/.
- **Contraste que lo descarta:** Sobre el código sin arreglar de las mismas tareas, las pruebas escritas a partir de una especificación corta salen verdes con la misma frecuencia que el reproductor del agente: no distinguen el arreglo. Con ese resultado se descarta.

### `pc-v03-c2`

- **Mecanismo:** Filtrar o endurecer cada tarea según cuánto la resuelve el modelo: la que siempre se resuelve, o nunca, no da señal. En este repositorio: elegir el conjunto local de tareas de un experimento con modelo por su resultado en las pasadas de la base, dejando fuera las que la base resuelve siempre o nunca.
- **Dónde lo nombra el código:** no lo nombra (git grep de sus términos, sin resultados fuera de investigacion/, 2026-10-13).
- **Medición local:** experiments/gemma_developer_agent/hallazgos.json, «potencia_del_diseno» (decidido): mide qué diferencia detecta el diseño según el número de tareas y de pasadas, no según qué tareas se eligen. Nada en docs/results/.
- **Contraste que lo descarta:** En las pasadas repetidas de la base ya rescatadas, los pares discordantes entre dos pasadas no se concentran en un subconjunto de tareas: aparecen repartidos por todas. Con ese resultado, filtrar no aporta y se descarta.
