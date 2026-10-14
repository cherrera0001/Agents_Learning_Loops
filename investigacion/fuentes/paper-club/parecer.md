# Parecer para el concilio: memoria en dos escalas frente a la compactación

Parecer de ejemplo del investigador de fuentes, fechado el 2026-10-13. No es un diseño de corrida ni
propone una subida. No vota.

**Mecanismo.** Una memoria en dos escalas: lo reciente se guarda comprimido y, aparte, un texto de
horizonte largo conserva qué etapas de la tarea ya están hechas. En el kit del experimento con modelo
sería un texto corto, con el enunciado y las etapas hechas, que queda fuera de la compactación del
contexto.

**Ficha.** `pc-p-2603.03596` en [`indice.jsonl`](../indice.jsonl): Torne et al. (2026), *MEM: Multi-Scale
Embodied Memory for Vision Language Action Models*, arXiv:2603.03596, versión v2. Se abrió el registro y
se leyeron el resumen y la transcripción de la charla el 2026-10-13; el texto completo del paper no. La
obra trata de políticas de robot, con video para el horizonte corto; su memoria larga es un texto corto
que la política reescribe en cada paso, y qué anotar en él lo fijaron sus autores de antemano. Lo que aquí se propone comparte la idea de las dos escalas y no implementa la
obra. Sus resultados son de sus autores.

**Si el código ya lo nombra.** No. Una búsqueda con `git grep` del nombre del método y de «multi-scale» no
da ninguna coincidencia. El repositorio sí nombra la compactación del arnés (por ejemplo, en
[`hallazgos.json`](../../../experiments/gemma_developer_agent/hallazgos.json)), que es otra cosa: resume
el contexto, y no separa un texto que se conserve.

**Qué medición de este repositorio lo toca.** El hallazgo «compactacion_del_contexto» de
[`hallazgos.json`](../../../experiments/gemma_developer_agent/hallazgos.json), en estado `medido` desde la
vuelta 32. En la vuelta 43 registra que el texto literal del enunciado falta en las 1 531 peticiones
posteriores a una compactación, y también en 204 de 3 042 sin compactación previa; y que las sesiones
resueltas son 11 de 59 con compactación y 10 de 57 sin ella, sin razonamiento. El propio registro dice que
el auditor no recontó esas cifras y que falta saber cada cuántos turnos compacta la corrida que puntúa.
`docs/results/` no tiene ninguna medición de este mecanismo. Esas cifras miden la compactación tal como
viene, no una memoria en dos escalas.

**Contraste que lo descartaría.** Uno solo: en las mismas tareas, las sesiones que conservan el enunciado
literal después de una compactación frente a las que lo pierden. Si las que lo conservan no resuelven más,
con el criterio de decisión válida de
[`CONTRIBUTING.md`](../../../CONTRIBUTING.md#vuelta-de-un-experimento-con-modelo), el mecanismo se
descarta para este kit: perder el enunciado no sería lo que impide resolver. La comparación ya medida,
con compactación y sin ella, no contesta esto: no separa las sesiones por si conservan el enunciado.

**Lo que este parecer no sabe.** Si el arnés permite fijar un texto fuera de la compactación; eso lo
contesta el forense del arnés. Y si la diferencia que el diseño puede detectar alcanza; eso lo contesta
el analista de datos.
