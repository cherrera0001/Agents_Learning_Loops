# Paper Track — esqueleto decision-ready (2026-10-18)

Competencia hermana: `gemma-4-developer-agent-paper` (Kaggle). **Deadline 2026-11-12 23:59 UTC**
(verificado por CLI 2026-10-18). Premio 35.000 USD; 249 equipos; equipo CS4ALL ya inscrito
(userHasEntered=True). **Requisitos verificados el 2026-10-17 en la página «Submission
Requirements» del track** (leída por la API): Kaggle Writeup con título y subtítulo, abstract,
introducción, descripción de la investigación (métodos y experimentos), trabajos relacionados y
citas; **3.000 palabras máximo**, investigación original no publicada, no archival; opcional un
notebook público (Project Links) y opcional un PDF arXiv-ready (LaTeX/Word) en lugar del Writeup.
Rúbrica (página Evaluation): cinco criterios 0-5 con igual peso — Novelty, Quality (generaliza
más allá del concurso), Relevance, **Verifiability** (cómo se obtuvieron, analizaron e
interpretaron los datos), Clarity; premio a los tres mejores; desempate por orden de entrada.
Temas sugeridos: tuning/RL, comprensión de código y grafos, tareas y benchmarks, razonamiento
sobre grafos. No gasta slot del LB principal. La API de límites del track da 5 envíos/día.

## Tesis (1 párrafo, borrador)

Un agente de software con bucle de aprendizaje por refuerzo-asociativo y memoria de fallos
puede mejorar su tasa de resolución en tareas SWE reales con intervenciones mínimas y
declarativas (instrucción, muestreo, presupuesto), siempre que cada intervención se mida con
A/B limpios, predicciones selladas y bandas de ruido explícitas. Evidencia: campaña C7 en
gemma-4-developer-agent — el muro de tiempo por tarea fue el cuello causal (A/B 4.5→5.0 min:
+0.07 fuera de ruido, 0.10→0.17), y la corrección de premisas medidas (clase_fallo,
thinking-off real vs oculto) cambió las palancas priorizadas.

## Secciones (presupuesto de palabras sobre 3.000)

| # | Sección | Palabras | Fuente en el repo |
|---|---|---|---|
| 1 | Introducción y motivación | 350 | Manuscrito `docs/paper/manuscript_en.md` §1, §4.8 (WORM/biological precedent) |
| 2 | Método: bucle medir→proponer→decidir | 500 | §4 del manuscrito; skill concilio-de-experimento; `docs/c7_concilio_2026-10-17.md` (vuelta 49) como caso de estudio del método |
| 3 | Setup: contrato declarativo-only, huellas, frontera de datos | 400 | §3 «Competition contract», §«Data availability»; `verify_no_competition_data.py` |
| 4 | Resultados | 800 | **A5 (sub-019: 0.17; predicción sellada 0.10 [0.06,0.14] refutada por arriba; A/B limpio del muro 4.5→5.0 min, +0.07 fuera de ruido ±0.05)**; tabla campaña nav (0.10→0.17); banda de ruido IC95 ±0.041; réplicas 2-3 (lunes); concilio (13/20 muro, submits 7/20, thinking-off exige budget 0); **hallazgo de campo: 52/129 gold-fallan en local (fastapi 32/67, requests 10/13), confirmado como fenómeno del set público (deps de test ausentes, pytest 8/httpbin, cert py3.13) mientras el host confirma gold 100 % en el set oculto → conjunto medible local = 77** (`analisis_c7/gold_results_2026-10-18.jsonl`; STATUS §Reglas d); **contexto del «baseline 0.24»: ningún autor de esos notebooks tiene 0.24 en el LB (0.18-0.20); la receta pública difiere en 8 min / 28 llamadas / un agente / edición antes de la llamada 12** (`docs/c7_baseline024_estudio.md`); **dimensión de modelos chicos**: cuatro variantes permitidas (31B/12B/E4B/E2B), una por envío; brazo 12B construido sin correr (`replicas_c7_12b/`), con el riesgo de que el scorer no sirva 12B (tres reportes 10-14/15) |
| 5 | Amenazas a la validez | 450 | §6 del manuscrito + honestidad del análisis crítico: **(i) n pequeño (58 tareas públicas: 1 tarea = 0.017) y ruido ±0.05 propio / ±0.08-0.11 público; (ii) LB público = 50 % del test, privado decide; (iii) un dato no es una ley (el +0.07 es una observación); (iv) set sustituto de 20 rich ≠ conjunto oculto, techo medible 13/20; (v) sesgo ambiental del set público (gold-falla 52/129) → toda medición local se normaliza por el conjunto medible; (vi) cosecha del árbol y parches vacíos como métrica (44/135 submits vacíos); (vii) R1-fiel no es A/B limpio contra sub-019 (difiere prompt y thinking); (viii) cifras de ablaciones públicas citadas, no reproducidas; (ix) el arnés del calificador cambió el 12-10 (verificación separada a 300 s) y no se sabe qué versión corre hoy** |
| 6 | Conclusión y trabajo futuro | 300 | Lecciones `learning/episodes/102`; híbrido nav-v2 + eval público (decisión (b) de `c7_baseline024_estudio.md`); R1-fiel; variante 12B; measurement set estratificado por repo |
| — | Referencias y apéndice de huellas | 200 | registry.json (sub-018/sub-019/sub-020), `replicas_c7_r1fiel/huella_r1fiel.txt`, `replicas_c7_12b/huella_12b.txt`, predicciones selladas (`analisis_c7/predicciones.csv`) |

Presupuesto re-chequeado el 2026-10-17: 350 + 500 + 400 + 800 + 450 + 300 + 200 = **3.000** (el
límite del track es 3.000 máximo: las referencias cuentan si van en el Writeup; dejar 100-150 de
holgura recortando §4 a 700 si hace falta).

## Decisiones pendientes (para la semana, antes del 12-11)

- [x] Límite de palabras y formato verificados el 2026-10-17 (3.000 máx.; Writeup o PDF arXiv-ready; secciones obligatorias arriba).
- [ ] ¿Paper en inglés (idioma del manuscrito) — confirmar (el Writeup de Kaggle y los jueces operan en inglés; recomendación: inglés).
- [ ] Decidir Writeup nativo vs PDF LaTeX (el PDF permite figuras y tablas con control de formato; el Writeup se puede guardar como borrador y enviar al final).
- [ ] Incluir o no la dimensión «cerebro de gusano» (Project WORM) como §4.8 condensada — depende del resultado del brazo forrajeo del lunes.
- [ ] Autores y afiliaciones; orden de autores si el dueño suma colaboradores.
- [ ] Figuras: fig1 (scores+ruido) y fig3 (LB) de `analisis_c7/` son reutilizables; licencia de datos del concurso (redistribución de tareas prohibida → solo agregados).

## Qué NO hacer todavía

No redactar secciones; no subir nada al track; no citar números del lunes hasta que existan
(recién después del contraste de réplicas/brazos).
