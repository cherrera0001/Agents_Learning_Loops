# Paper Track — esqueleto decision-ready (2026-10-18)

Competencia hermana: `gemma-4-developer-agent-paper` (Kaggle). **Deadline 2026-11-12**
(verificado por CLI 2026-10-18). Premio 35.000 USD; 249 equipos; equipo CS4ALL ya inscrito
(userHasEntered=True). Extensión: paper de ~3.000 palabras (verificar límite exacto en las
rules del track — pendiente). No gasta slot del LB principal.

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
| 4 | Resultados | 800 | Apéndice A5 (sub-019: 0.17 vs predicción sellada refutada); tabla campaña nav (0.10→0.17); banda de ruido IC95 ±0.041; réplicas 2-3 (lunes); concilio (13/20 muro, submits 7/20, thinking-off exige budget 0) |
| 5 | Amenazas a la validez | 450 | §6 del manuscrito + honestidad del análisis crítico (n pequeño, LB 50%, un dato no es una ley, set sustituto 13/20 medible-ganable, cosecha del árbol) |
| 6 | Conclusión y trabajo futuro | 300 | Lecciones `learning/episodes/102`; R1-fiel/PR futuros; measurement set estratificado |
| — | Referencias y apéndice de huellas | 200 | registry.json (sub-018/sub-019/sub-020), `replicas_c7_r1fiel/huella_r1fiel.txt` |

## Decisiones pendientes (para la semana, antes del 12-11)

- [ ] Verificar límite de palabras y plantilla del track (rules del paper competition) — asignado al paso 0 del lunes.
- [ ] ¿Paper en inglés (idioma del manuscrito) — confirmar.
- [ ] Incluir o no la dimensión «cerebro de gusano» (Project WORM) como §4.8 condensada — depende del resultado del brazo forrajeo del lunes.
- [ ] Autores y afiliaciones; orden de autores si el dueño suma colaboradores.
- [ ] Figuras: fig1 (scores+ruido) y fig3 (LB) de `analisis_c7/` son reutilizables; licencia de datos del concurso (redistribución de tareas prohibida → solo agregados).

## Qué NO hacer todavía

No redactar secciones; no subir nada al track; no citar números del lunes hasta que existan
(recién después del contraste de réplicas/brazos).
