# Estrategia vigente del concilio 50

Escrito el 2026-10-14 desde el dictamen del auditor del método del concilio 50 (`auditor/dictamen.md`, en la
carpeta local `.scratch/concilio_memoria/fase2/concilio_50/`, ignorada por git), la entrada «Vuelta 48» de la
bitácora del caso y los informes del constructor (`receta_publica_018/INFORME.md` y `lora_nulo/INFORME.md`, en
`data/rescate_kaggle/instrumentos/`). No se leyó Kaggle ni se subió nada al escribirlo.

Es una decisión de estrategia y no una medición. Las cifras medidas están en
[`hallazgos.json`](../hallazgos.json) (`sesiones_de_12_tareas_del_bundle_contract_first`,
`sin_write_file_se_crea_archivo_por_shell`, `el_arnes_vigente_acepta_un_adaptador_lora` y
`estrategia_del_concilio_50`); las huellas de los zips, en
[`registry.json`](../submissions/registry.json) (`sub-013` a `sub-017`). La campaña de C1 que esta estrategia
deja como respaldo es la de [`decision_c1.md`](decision_c1.md).

## Qué se hace

1. **Suelo.** Un zip propio de la familia contract-first (la que hoy puntúa 0,24 en la tabla pública), no una
   copia del bundle público: el dueño ordenó el 2026-10-14 que el envío sea un zip nuevo. Lo exacto y lo
   «sin `write_file`» son controles de sesión.
2. **Techo.** Una sola apuesta: un adaptador LoRA entrenado con episodios de Gemma. Es el bucle de este
   repositorio (episodios que se vuelven a usar) aplicado al peso del modelo y no al texto del prompt. El
   concilio 48 midió que el texto casi no mueve la conducta.
3. **Tres puertas baratas antes de gastar cuota de entrenamiento.**

| Puerta | Pregunta | Pasa si | Si no pasa |
|---|---|---|---|
| G2, sonda de efecto (2,5 h de GPU como máximo) | ¿El vLLM del arnés aplica el adaptador? | Arranca a `gpu_memory_utilization` 0,80; el adaptador de ceros coincide con la base dentro de la deriva (la base medida dos veces); y el adaptador N(0, 1) mueve el primer token al menos 1 nat y al menos 10 veces la deriva en 4 de 5 indicaciones | Se cierra la vía LoRA con el puntuador como está; se pide al organizador `cudagraph_specialize_lora: false` |
| E2, aceptación | ¿El puntuador acepta el zip con adaptador? | El zip del día 15 más el adaptador nulo, con los demás bytes idénticos, puntúa sin error (el primer cupo libre tras puntuar el del 15) | Un error genérico cuenta como «sin lectura» y se repite una vez; un segundo error cierra el LoRA |
| G3, tokens por segundo de entrenamiento (4 h como máximo, solo si pasó G2) | ¿Cabe el entrenamiento en la cuota? | 150 o más: 31B; de 50 a 150: solo una miniatura de 4 M de tokens o menos; menos de 50: se cierra el entrenamiento en GPU | Sin G3 no hay entrenamiento |

La sonda G2 se rehízo según el dictamen: un adaptador de ceros da logits iguales por construcción, así que no
puede detectar el fallo que otro participante midió el 2026-10-08 con un LoRA; por eso lleva gemelos ruidosos
(N(0, 1e-3) y N(0, 1), que nunca se envían). Su criterio está escrito en la celda antes de los datos. G2 se
subió el 2026-10-14 y sigue en curso al escribir esto.

## Envío del día 15 (regla escrita antes de los datos, con el veto 1)

1. Si C2 (envío 57160374) puntúa 9 tareas o más, se repite C2: es el protocolo del dueño del 2026-10-14.
2. Si no, y la sesión sin `write_file` terminó completa, sin tareas colgadas, y resuelve al menos lo de la
   exacta menos 1, se envía el 0,24 sin `write_file`.
3. Si no, C1 sin tocar.

**Veto 1.** La rama (3) que se había escrito después enviaba el 0,24 exacto cuando la sesión no terminaba a
tiempo. Es una copia del zip público y contradice la orden del dueño; además sustituía a C1 sin texto suyo.
Vuelve a C1 sin tocar. El envío del día 15 se rotula «lectura, no mejora». Antes de enviar, el analista de
datos y el auditor leen la nota de C2 y las sesiones.

## Regla de adopción y de parada

- **Adopción.** Un brazo se adopta con la media de 3 lecturas igual o mayor que la media del vigente más 2,0
  tareas. Con efecto 0 la regla se cumple por azar con probabilidad 0,06; con un efecto de 3 tareas, con 0,84
  (recontado por el auditor).
- **Los finales se eligen por la media de varias lecturas del mismo zip,** no por el máximo
  ([`CONTRIBUTING.md`](../../../CONTRIBUTING.md), «Vuelta de un experimento con modelo»).
- **Guarda local.** El adaptador se entrena sin 12 tareas apartadas; se para si la pérdida queda plana o si
  pierde más de 2 de esas 12.
- **Parada.** El 2026-11-14, si ningún brazo llega a una media de 13 tareas o más en 3 lecturas, se cierra la
  vía del adaptador y se dice al dueño que la probabilidad de ser primero es menor que 0,01.
- **Lo que refutaría la estrategia:** logits iguales o fallo de arranque a 0,80 en G2; un error repetido en E2;
  que la familia 0,24 llegue sola a 13 o más en 3 lecturas (entonces el LoRA sobra); o, al revés, una nota
  pública con adaptador que supere a su base en 3 tareas (eso subiría la apuesta).

## Fechas

| Fecha (2026) | Qué |
|---|---|
| 10-14 | Sesiones de 12 tareas del 0,24 (terminadas); G2 subida |
| 10-15 | Resultado de G2; envío del día 15 |
| 10-15 y 10-16 | G3, solo si pasó G2 |
| 10-17 00:00 | Caducan 15,36 h de GPU y 20 h de TPU (la de TPU no se usa: no hay pila sin internet ni datos antes del 17) |
| 10-17 a 10-24 | Primer adaptador con la cuota de la semana (30 h como máximo), si pasaron G2, G3 y E2 y hay 200 trayectorias o más |
| 10-18 a 10-31 | Tres lecturas de la familia 0,24 en la tabla |
| 11-01 a 11-08 | Tres lecturas del adaptador, con la misma regla; un segundo ciclo (11-08 a 11-21) solo si el primero da al menos el suelo más 1,0 |
| 11-14 | Parada |
| 11-24 | Se congela el kit final y se toman 2 lecturas |
| 12-01 como límite | Se eligen 2 finales por la media |

Lo que espera la palabra del dueño: E2 y todo envío posterior al día 15. Las sesiones de GPU de hasta 4,5 h las
sube el orquestador, según la entrada de la bitácora.

## Lo que esto no sostiene

- **P(primero)** queda entre 0,01 y 0,035 con los priores del estratega y por debajo de 0,01 con priores
  prudentes. Son juicios y no mediciones; el orden «con adaptador mejor que sin él» se mantiene en ambos.
- **El costo de entrenar** no se reproduce: entre 7 y 115 h por 10 M de tokens según los supuestos. Solo lo
  cierra G3.
- **No hay evidencia de que un LoRA tenga efecto en el puntuador.** Los antecedentes públicos recontados por el
  auditor: en el puntuador, 0 éxitos y 2 fallos; en cuaderno, 1 sí y 1 no; de beneficio, una medición,
  negativa (2 de 32 frente a 4 de 32).
- **El concilio tuvo tres fallos de proceso.** Sus tres roles (inteligencia pública, arquitecto y estratega)
  recibieron un encargo con cifras y palancas del concilio 48 y son el mismo modelo, así que su acuerdo no es
  una medición; faltaron el analista de datos, el forense del arnés y la revisión cruzada que exige
  `CONTRIBUTING.md`. Mientras falten, el dictamen declara inválida toda decisión que gaste la cuota de la
  semana del 17 o envíos posteriores al 15. La revisión cruzada sin firmas debe terminar antes del 2026-10-17.
- **Las horas de la bitácora de ese día van unas 2 h adelantadas** respecto de los sellos de los archivos; este
  documento usa fechas y deja las horas a la bitácora.
