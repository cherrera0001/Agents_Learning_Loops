# Inference, Diffusion, World Models, and More | YC Paper Club

Ficha `pc-v07` · video 7 de 7 de la lista Paper Club · consultada el 2026-10-13.

## Lo que la página mostró

- **URL:** <https://www.youtube.com/watch?v=wE1ZgJdt4uM>
- **Duración:** 1:07:19 (4038 s en los datos de la página).
- **Fecha de publicación que da la página:** 2026-05-28.
- **Canal:** Y Combinator.
- **Estado del contenido:** `no_abierto`. No se encontró una transcripción publicada y la pista de subtítulos automáticos respondió HTTP 429. Lo que se dijo en el video no se leyó: esta ficha no afirma nada de su contenido.

## Obras con identificador en la descripción

### Speculative Speculative Decoding

- **Ficha:** `pc-p-2603.03251`.
- **Autores (registro de arXiv):** Tanishq Kumar; Tri Dao; Avner May.
- **Año:** 2026 (primera versión, 2026-03-03).
- **Identificador abierto:** arXiv:2603.03251, <https://arxiv.org/abs/2603.03251>. Registro leído por la API de arXiv el 2026-10-13; versión vigente v3, del 2026-05-04.
- **Qué se leyó:** el registro y el resumen. El texto completo no.
- **Mecanismo:** Mientras el modelo objetivo verifica una especulación, el modelo borrador predice los desenlaces probables de esa verificación y prepara la especulación siguiente.
- **En este repositorio:** No aplica hoy: cambia el motor de inferencia, que el kit del experimento con modelo no controla.
- **Dónde lo nombra el código:** no lo nombra (git grep del nombre y de sus términos, sin resultados en texto, 2026-10-13).
- **Medición local:** ninguna en docs/results/
- **Contraste que lo descarta:** no se propone: sin frase de qué haría en este repositorio

### Diffusion Model Predictive Control

- **Ficha:** `pc-p-2410.05364`.
- **Autores (registro de arXiv):** Guangyao Zhou; Sivaramakrishnan Swaminathan; Rajkumar Vasudeva Raju; J. Swaroop Guntupalli; Wolfgang Lehrach; Joseph Ortiz; Antoine Dedieu; Miguel Lázaro-Gredilla; Kevin Murphy.
- **Año:** 2024 (primera versión, 2024-10-07).
- **Identificador abierto:** arXiv:2410.05364, <https://arxiv.org/abs/2410.05364>. Registro leído por la API de arXiv el 2026-10-13; versión vigente v2, del 2025-05-22.
- **Qué se leyó:** el registro y el resumen. El texto completo no.
- **Mecanismo:** Control predictivo en línea que combina una propuesta de acciones de varios pasos y un modelo de dinámica de varios pasos, ambos de difusión.
- **En este repositorio:** No aplica: ni el solver acotado ni el kit planifican con un modelo de dinámica aprendido.
- **Dónde lo nombra el código:** no lo nombra (git grep del nombre y de sus términos, sin resultados en texto, 2026-10-13).
- **Medición local:** ninguna en docs/results/
- **Contraste que lo descarta:** no se propone: sin frase de qué haría en este repositorio

### LeWorldModel: Stable End-to-End Joint-Embedding Predictive Architecture from Pixels

- **Ficha:** `pc-p-2603.19312`.
- **Autores (registro de arXiv):** Lucas Maes; Quentin Le Lidec; Damien Scieur; Yann LeCun; Randall Balestriero.
- **Año:** 2026 (primera versión, 2026-03-13).
- **Identificador abierto:** arXiv:2603.19312, <https://arxiv.org/abs/2603.19312>. Registro leído por la API de arXiv el 2026-10-13; versión vigente v3, del 2026-06-03.
- **Qué se leyó:** el registro y el resumen. El texto completo no.
- **Nota:** la descripción del video escribe el nombre de otra forma; el título de arriba es el del registro.
- **Mecanismo:** Arquitectura predictiva de representación conjunta entrenada de extremo a extremo desde píxeles con dos términos de pérdida.
- **En este repositorio:** No aplica: aquí no se entrena ningún modelo ni hay entrada de píxeles.
- **Dónde lo nombra el código:** no lo nombra (git grep del nombre y de sus términos, sin resultados en texto, 2026-10-13).
- **Medición local:** ninguna en docs/results/
- **Contraste que lo descarta:** no se propone: sin frase de qué haría en este repositorio

### Deep Learning is Not So Mysterious or Different

- **Ficha:** `pc-p-2503.02113`.
- **Autores (registro de arXiv):** Andrew Gordon Wilson.
- **Año:** 2025 (primera versión, 2025-03-03).
- **Identificador abierto:** arXiv:2503.02113, <https://arxiv.org/abs/2503.02113>. Registro leído por la API de arXiv el 2026-10-13; versión vigente v2, del 2025-07-10.
- **Qué se leyó:** el registro y el resumen. El texto completo no.
- **Mecanismo:** Argumento, no mecanismo: un espacio de hipótesis flexible con preferencia blanda por soluciones simples explica fenómenos de generalización que se atribuían solo a las redes.
- **En este repositorio:** No aplica: es una posición teórica sobre generalización, sin nada que medir en este repositorio.
- **Dónde lo nombra el código:** no lo nombra (git grep del nombre y de sus términos, sin resultados en texto, 2026-10-13).
- **Medición local:** ninguna en docs/results/
- **Contraste que lo descarta:** no se propone: sin frase de qué haría en este repositorio

### Pre-training under infinite compute

- **Ficha:** `pc-p-2509.14786`.
- **Autores (registro de arXiv):** Konwoo Kim; Suhas Kotha; Percy Liang; Tatsunori Hashimoto.
- **Año:** 2025 (primera versión, 2025-09-18).
- **Identificador abierto:** arXiv:2509.14786, <https://arxiv.org/abs/2509.14786>. Registro leído por la API de arXiv el 2026-10-13; versión vigente v1, del 2025-09-18.
- **Qué se leyó:** el registro y el resumen. El texto completo no.
- **Mecanismo:** Con datos fijos y cómputo sin tope: regularización ajustada y ensamble de modelos entrenados por separado, después destilado.
- **En este repositorio:** No aplica: aquí no se preentrena ningún modelo.
- **Dónde lo nombra el código:** no lo nombra (git grep del nombre y de sus términos, sin resultados en texto, 2026-10-13).
- **Medición local:** ninguna en docs/results/
- **Contraste que lo descarta:** no se propone: sin frase de qué haría en este repositorio
