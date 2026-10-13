# Self-Play for LLMs, AI for Biology, Formal Verification, and More | YC Paper Club

Ficha `pc-v06` · video 6 de 7 de la lista Paper Club · consultada el 2026-10-13.

## Lo que la página mostró

- **URL:** <https://www.youtube.com/watch?v=3rWSvrFahIY>
- **Duración:** 1:16:55 (4615 s en los datos de la página).
- **Fecha de publicación que da la página:** 2026-06-12.
- **Canal:** Y Combinator.
- **Estado del contenido:** `no_abierto`. No se encontró una transcripción publicada y la pista de subtítulos automáticos respondió HTTP 429. Lo que se dijo en el video no se leyó: esta ficha no afirma nada de su contenido.

Otros enlaces de la descripción, sin DOI ni arXiv (no son obras del índice y no se leyeron):

- <https://biohub.ai/esm/protein/about>

## Obras con identificador en la descripción

### Scaling Self-Play with Self-Guidance

- **Ficha:** `pc-p-2604.20209`.
- **Autores (registro de arXiv):** Luke Bailey; Kaiyue Wen; Kefan Dong; Tatsunori Hashimoto; Tengyu Ma.
- **Año:** 2026 (primera versión, 2026-04-22).
- **Identificador abierto:** arXiv:2604.20209, <https://arxiv.org/abs/2604.20209>. Registro leído por la API de arXiv el 2026-10-13; versión vigente v2, del 2026-08-11.
- **Qué se leyó:** el registro y el resumen. El texto completo no.
- **Mecanismo:** Un tercer papel, el guía, puntúa cada problema sintético por su relevancia para los problemas objetivo sin resolver y por lo limpio y natural que es, para que el generador no degenere.
- **En este repositorio:** Solo la idea del guía, sin entrenamiento: un juez que puntúe si un registro de fallo de otra tarea es relevante para la tarea actual, en lugar del umbral de similitud τ.
- **Dónde lo nombra el código:** no lo nombra (git grep del nombre y de sus términos, sin resultados en texto, 2026-10-13).
- **Medición local:** docs/results/failure-transfer.md (H7) mide el umbral de similitud, no un guía: ningún τ separa la transferencia útil de la dañina; con τ = 0.1 un fallo ajeno quita el primer intento correcto en 3 de 18 pares. No hay medición del guía.
- **Contraste que lo descarta:** Sobre los pares de H7 con cambio, la puntuación del guía intercala los que ayudaron y los que dañaron, igual que la similitud: ningún corte los separa. Con ese resultado se descarta.

### Stream RAG: Instant and Accurate Spoken Dialogue Systems with Streaming Tool Usage

- **Ficha:** `pc-p-2510.02044`.
- **Autores (registro de arXiv):** Siddhant Arora; Haidar Khan; Kai Sun; Xin Luna Dong; Sajal Choudhary; Seungwhan Moon; Xinyuan Zhang; Adithya Sagar; Surya Teja Appini; Kaushik Patnaik; Sanat Sharma; Shinji Watanabe; Anuj Kumar; Ahmed Aly; Yue Liu; Florian Metze; Zhaojiang Lin.
- **Año:** 2025 (primera versión, 2025-10-02).
- **Identificador abierto:** arXiv:2510.02044, <https://arxiv.org/abs/2510.02044>. Registro leído por la API de arXiv el 2026-10-13; versión vigente v1, del 2025-10-02.
- **Qué se leyó:** el registro y el resumen. El texto completo no.
- **Mecanismo:** Predecir las consultas a herramientas en paralelo con la entrada del usuario, antes de que termine de hablar.
- **En este repositorio:** No aplica: el enunciado de cada tarea llega entero y no hay latencia percibida que reducir.
- **Dónde lo nombra el código:** no lo nombra (git grep del nombre y de sus términos, sin resultados en texto, 2026-10-13).
- **Medición local:** ninguna en docs/results/
- **Contraste que lo descarta:** no se propone: sin frase de qué haría en este repositorio

### TorchLean: Formalizing Neural Networks in Lean

- **Ficha:** `pc-p-2602.22631`.
- **Autores (registro de arXiv):** Robert Joseph George; Jennifer Cruden; Will Adkisson; Xiangru Zhong; Huan Zhang; Anima Anandkumar.
- **Año:** 2026 (primera versión, 2026-02-26).
- **Identificador abierto:** arXiv:2602.22631, <https://arxiv.org/abs/2602.22631>. Registro leído por la API de arXiv el 2026-10-13; versión vigente v2, del 2026-05-24.
- **Qué se leyó:** el registro y el resumen. El texto completo no.
- **Nota:** la descripción del video anuncia esta charla con otro título; el de arriba es el del registro que abre el enlace de la descripción.
- **Mecanismo:** Formalizar, ejecutar y verificar redes neuronales en Lean 4 con una sola semántica para cómputo y demostración.
- **En este repositorio:** No aplica: el repositorio no verifica formalmente ningún modelo.
- **Dónde lo nombra el código:** no lo nombra (git grep del nombre y de sus términos, sin resultados en texto, 2026-10-13).
- **Medición local:** ninguna en docs/results/
- **Contraste que lo descarta:** no se propone: sin frase de qué haría en este repositorio
