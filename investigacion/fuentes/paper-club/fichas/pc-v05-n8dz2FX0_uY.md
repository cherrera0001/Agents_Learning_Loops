# Lessons From Training Composer At Cursor And Building Meta/Nvidia Compute Clusters | YC Paper Club

Ficha `pc-v05` · video 5 de 7 de la lista Paper Club · consultada el 2026-10-13.

## Lo que la página mostró

- **URL:** <https://www.youtube.com/watch?v=n8dz2FX0_uY>
- **Duración:** 1:16:25 (4584 s en los datos de la página).
- **Fecha de publicación que da la página:** 2026-07-29.
- **Canal:** Y Combinator.
- **Estado del contenido:** `abierto`. La descripción enlaza una transcripción, <https://www.ycrootaccess.com/p/multi-gpu-kernels-intelligence-per>, que abrió (HTTP 200, con texto). En este PR no se tomó nada de ella: lo que sigue sale de los registros de arXiv.

Otros enlaces de la descripción, sin DOI ni arXiv (no son obras del índice y no se leyeron):

- <https://madrona-engine.github.io/shacklett_siggraph23.pdf>

## Obras con identificador en la descripción

### ParallelKittens: Systematic and Practical Simplification of Multi-GPU AI Kernels

- **Ficha:** `pc-p-2511.13940`.
- **Autores (registro de arXiv):** Stuart H. Sul; Simran Arora; Benjamin F. Spector; Christopher Ré.
- **Año:** 2025 (primera versión, 2025-11-17).
- **Identificador abierto:** arXiv:2511.13940, <https://arxiv.org/abs/2511.13940>. Registro leído por la API de arXiv el 2026-10-13; versión vigente v1, del 2025-11-17.
- **Qué se leyó:** el registro y el resumen. El texto completo no.
- **Mecanismo:** Un marco mínimo de CUDA, con ocho primitivas y una plantilla, para escribir kernels de varias GPU que solapan cómputo y comunicación.
- **En este repositorio:** No aplica: el repositorio no escribe kernels de GPU.
- **Dónde lo nombra el código:** no lo nombra (git grep del nombre y de sus términos, sin resultados en texto, 2026-10-13).
- **Medición local:** ninguna en docs/results/
- **Contraste que lo descarta:** no se propone: sin frase de qué haría en este repositorio

### Intelligence per Watt: Measuring Intelligence Efficiency of Local AI

- **Ficha:** `pc-p-2511.07885`.
- **Autores (registro de arXiv):** Jon Saad-Falcon; Avanika Narayan; Hakki Orhun Akengin; J. Wes Griffin; Herumb Shandilya; Adrian Gamarra Lafuente; Medhya Goel; Rebecca Joseph; Shlok Natarajan; Etash Kumar Guha; Shang Zhu; Ben Athiwaratkun; John Hennessy; Azalia Mirhoseini; Christopher Ré.
- **Año:** 2025 (primera versión, 2025-11-11).
- **Identificador abierto:** arXiv:2511.07885, <https://arxiv.org/abs/2511.07885>. Registro leído por la API de arXiv el 2026-10-13; versión vigente v7, del 2026-10-01.
- **Qué se leyó:** el registro y el resumen. El texto completo no.
- **Mecanismo:** Una métrica: exactitud de la tarea por unidad de potencia, para comparar configuraciones de modelo y acelerador en inferencia local.
- **En este repositorio:** Sería una métrica, no un cambio del agente: los recibos no registran tokens ni costo (CONTRIBUTING.md) y el sistema donde se mide no da una lectura de potencia.
- **Dónde lo nombra el código:** no lo nombra (git grep del nombre y de sus términos, sin resultados en texto, 2026-10-13).
- **Medición local:** ninguna en docs/results/
- **Contraste que lo descarta:** no se propone: sin frase de qué haría en este repositorio
