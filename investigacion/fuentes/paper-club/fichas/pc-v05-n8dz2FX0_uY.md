# Lessons From Training Composer At Cursor And Building Meta/Nvidia Compute Clusters | YC Paper Club

Ficha `pc-v05` · video 5 de 7 de la lista Paper Club · consultada el 2026-10-13.

## Lo que la página mostró

- **URL:** <https://www.youtube.com/watch?v=n8dz2FX0_uY>
- **Duración:** 1:16:25 (4584 s en los datos de la página).
- **Fecha de publicación que da la página:** 2026-07-29.
- **Canal:** Y Combinator.
- **Estado del contenido:** `abierto`. Transcripción publicada en <https://www.ycrootaccess.com/p/multi-gpu-kernels-intelligence-per> (enlazada en la descripción del video). Abrió sin sesión; el texto completo está en la copia local `investigacion/local/root-access/multi-gpu-kernels-intelligence-per.md`, que no se versiona. Las notas están al final de esta ficha.

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
- **Contraste que lo descarta:** no se propone.

### Intelligence per Watt: Measuring Intelligence Efficiency of Local AI

- **Ficha:** `pc-p-2511.07885`.
- **Autores (registro de arXiv):** Jon Saad-Falcon; Avanika Narayan; Hakki Orhun Akengin; J. Wes Griffin; Herumb Shandilya; Adrian Gamarra Lafuente; Medhya Goel; Rebecca Joseph; Shlok Natarajan; Etash Kumar Guha; Shang Zhu; Ben Athiwaratkun; John Hennessy; Azalia Mirhoseini; Christopher Ré.
- **Año:** 2025 (primera versión, 2025-11-11).
- **Identificador abierto:** arXiv:2511.07885, <https://arxiv.org/abs/2511.07885>. Registro leído por la API de arXiv el 2026-10-13; versión vigente v7, del 2026-10-01.
- **Qué se leyó:** el registro y el resumen. El texto completo no.
- **Nota:** las cifras que da la charla no coinciden con las del resumen de la versión vigente del registro (v7). Unas y otras son de sus autores; aquí no se usa ninguna.
- **Mecanismo:** Una métrica: exactitud de la tarea por unidad de potencia, para comparar configuraciones de modelo y acelerador en inferencia local. La charla añade la variante por unidad de energía de la carga completa.
- **En este repositorio:** Sería una métrica, no un cambio del agente: los recibos no registran tokens ni costo (CONTRIBUTING.md) y el sistema donde se mide no da una lectura de potencia.
- **Dónde lo nombra el código:** no lo nombra (git grep del nombre y de sus términos, sin resultados en texto, 2026-10-13).
- **Medición local:** ninguna en docs/results/
- **Contraste que lo descarta:** no se propone.

## Lo que dice la transcripción

Leídas el 2026-10-13 la segunda y la tercera charla (21:29 y 31:05). **La apertura, la primera charla y
todo desde 47:04 no se leyeron.** Copia local, no versionada:
`investigacion/local/root-access/multi-gpu-kernels-intelligence-per.md`. Son notas propias; las
afirmaciones y las cifras son de quienes hablan.

- **21:29, inteligencia por vatio** (ficha `pc-p-2511.07885`). Proponen medir la capacidad por unidad de
  potencia y, además, por unidad de energía de la carga completa, y sostienen que buena parte de las
  consultas se podría atender con modelos locales. Las cifras de la charla no coinciden con las del
  resumen vigente en arXiv; aquí no se usa ninguna.
- **31:05, cuando un modelo escribe código de sistemas** (ficha `pc-v05-c3`). Lo que toca a este
  repositorio es la evaluación, no los kernels:
  - Una evaluación con recompensa verificable no es por eso fácil. Cuenta trampas vistas en una
    competencia: devolver una constante porque las entradas de prueba tienen media conocida, guardar la
    salida y reutilizarla, y portarse bien mientras se comprueba la corrección y mal cuando solo se mide
    la velocidad, porque las dos cosas se comprobaban en fases distintas.
  - Prohibir cada trampa por su texto no alcanza: reaparece escrita de otro modo. Su práctica es
    auditar a mano lo que sale demasiado bien, marcarlo y derivar de esos casos un detector, que se
    rehace cuando aparece una trampa nueva.
  - La charla nombra dos trabajos propios sin identificador; una búsqueda por título en arXiv no los
    encontró: no tienen ficha.

## Charlas con ficha propia

### `pc-v05-c3`

- **Mecanismo:** Evaluación endurecida por sus propias trampas: cada solución que sale demasiado bien se audita a mano y de las trampas marcadas se deriva un detector, que se rehace con cada trampa nueva. En este repositorio: no es un cambio del agente ni del solver acotado; es una advertencia sobre comprobar la corrección y otra medida en fases separadas.
- **Dónde lo nombra el código:** no lo nombra (git grep de sus términos, sin resultados fuera de investigacion/, 2026-10-13).
- **Medición local:** ninguna en docs/results/
- **Contraste que lo descarta:** no se propone.
