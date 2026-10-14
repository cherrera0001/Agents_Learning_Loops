# Estrategia vigente del concilio 50

Escrito el 2026-10-14 y puesto al día el mismo día, a las 13:10 UTC de la bitácora, desde el dictamen del auditor
del método del concilio 50 (`auditor/dictamen.md`, en la carpeta local
`.scratch/concilio_memoria/fase2/concilio_50/`, ignorada por git), la entrada «Vuelta 48» de la bitácora del caso
y estos informes, todos en carpetas ignoradas por git:

- `analista_p24/informe.md` (analista de datos, en la carpeta del concilio): el recuento de las dos sesiones de 12
  tareas del 0,24.
- `receta_publica_018/INFORME.md`, `lora_nulo/INFORME.md`, `lora_g3/INFORME.md` y `kit_all_1/ESPECIFICACION.md`
  (constructor y orquestador, en `data/rescate_kaggle/instrumentos/`).
- `sonda_g2.json` (en `data/rescate_kaggle/sonda_g2_2026-10-14T1236Z/`): la medición de G2.

Es una decisión de estrategia y no una medición. Las cifras medidas están en
[`hallazgos.json`](../hallazgos.json) (`sesiones_de_12_tareas_del_bundle_contract_first`,
`sin_write_file_se_crea_archivo_por_shell`, `el_arnes_vigente_acepta_un_adaptador_lora` y
`estrategia_del_concilio_50`); las huellas de los zips, en
[`registry.json`](../submissions/registry.json) (`sub-013` a `sub-017`). La campaña de C1 que esta estrategia
deja como respaldo es la de [`decision_c1.md`](decision_c1.md).

## Qué se hace

1. **Suelo.** Un zip nuevo, nuestro, y no el bundle público tal cual: el dueño ordenó el 2026-10-14 que el envío
   sea un zip nuevo. Un cambio posterior de estrategia (bitácora, 13:10 UTC, antes de cualquier dato del kit) retira
   el 0,24 sin `write_file` como candidato: el 0,24 exacto y el «sin `write_file`» quedan como controles de sesión.
   El candidato es el kit **ALL-1** (`kit_all_1/ESPECIFICACION.md`). Corrección del dueño de las 13:15 UTC: se
   construye a partir del zip del 0,24, con sus cuatro archivos tal cual, y encima solo las mejoras propias y los
   mismos topes, muestreo y herramientas: las reglas de higiene de llamadas que falten al prompt y dos mecanismos que
   el agente ejecuta, la skill `localizar` (búsqueda léxica más BM25 sobre los términos del enunciado, los 5
   primeros archivos) y la skill `entregar` (limpia rutas de pruebas y archivos sueltos, comprueba la sintaxis y
   prohíbe el diff vacío). El diff frente al 0,24 debe mostrar solo esas adiciones, y la sesión de ALL-1 mide una
   diferencia de dos skills sobre el 0,24, no un kit nuevo. La regla del envío no cambia. Cada pieza nombra el fallo medido que ataca, entre ellos el bucle de `submit_patch`
   vacío de las sesiones del 0,24 (49 y 51 llamadas con parche de tamaño 0, en 1 de 12 tareas por sesión).
   Antes de la sesión de 12 tareas del kit, sus puertas de ensayo son: que el arnés admita las skills, el ensayo en
   Docker con modelo falso, y `localizar` medido sin modelo sobre las 129 tareas públicas.
2. **Techo.** Una sola apuesta: un adaptador LoRA entrenado con episodios de Gemma. Es el bucle de este
   repositorio (episodios que se vuelven a usar) aplicado al peso del modelo y no al texto del prompt. El
   concilio 48 midió que el texto casi no mueve la conducta. Los episodios se generan con el kit que se envía,
   porque el adaptador aprende su formato: la generación con el 0,24 se canceló sin haber empezado y se relanza con
   ALL-1.
3. **Tres puertas baratas antes de gastar cuota de entrenamiento.**

| Puerta | Pregunta | Pasa si | Estado | Si no pasa |
|---|---|---|---|---|
| G2, sonda de efecto (2,5 h de GPU como máximo) | ¿El vLLM del arnés aplica el adaptador? | Arranca a `gpu_memory_utilization` 0,80; el adaptador de ceros coincide con la base dentro de la deriva en 5 de 5; el adaptador N(0, 1) mueve el primer token al menos 1 nat y al menos 10 veces la deriva en 4 de 5 | **Pasó** (2026-10-14) | Se cierra la vía LoRA con el puntuador como está; se pide al organizador `cudagraph_specialize_lora: false` |
| E2, aceptación | ¿El puntuador acepta el zip con adaptador? | El zip del envío del día 15 más el adaptador nulo, con los demás bytes idénticos, puntúa sin error (el primer cupo libre tras puntuar el del 15) | Espera la palabra del dueño | Un error genérico cuenta como «sin lectura» y se repite una vez; un segundo error cierra el LoRA |
| G3, tokens por segundo de entrenamiento (4 h como máximo, solo si pasó G2) | ¿Cabe el entrenamiento en la cuota? | 150 o más: 31B; de 50 a 150: solo una miniatura de 4 M de tokens o menos; menos de 50: se cierra el entrenamiento en GPU | Relanzada, en cola | Sin G3 no hay entrenamiento |

**G2 se subió el 2026-10-14 y pasó** (`sonda_g2.json`): arrancó a 0,80 en 427 s; el adaptador de ceros quedó dentro
de la deriva en 5 de 5; N(0, 1) movió el primer token entre 12,2 y 16,5 nats en 5 de 5 (deriva máxima 0,19 nats).
Es una medición en cuaderno: no dice nada del puntuador (E2). La decodificación con adaptador fue de 35,4 frente a
37,9 tokens por segundo con la base (6,5 % más lenta; el dictamen daba +1,7 % el arquitecto y +11 % el foro) y la
caché KV quedó en 26 768 tokens a 0,80.

La sonda G2 se rehízo según el dictamen: un adaptador de ceros da logits iguales por construcción, así que no
puede detectar el fallo que otro participante midió el 2026-10-08 con un LoRA; por eso lleva gemelos ruidosos
(N(0, 1e-3) y N(0, 1), que nunca se envían). Su criterio estaba escrito en la celda antes de los datos.

**G3 necesita el dataset privado `cs4all/ruedas-g3`** con `peft`, `accelerate`, `loguru` y sus dependencias:
faltan en el wheelhouse del arnés y sin él la sesión falla por construcción. La primera G3 falló a los 85 s por
falta de `loguru`; se versionó el dataset con él y se relanzó. Hallazgo del constructor: con `run_compressed=True`
la capa cuantizada no se ejecuta y `peft` no la envuelve, así que el cuaderno la descomprime a bf16 o la
recuantiza a nf4.

## Envío del día 15 (regla vigente, escrita antes de cualquier dato de ALL-1)

1. Si C2 (envío 57160374) puntúa 9 tareas o más, se repite C2: es el protocolo del dueño del 2026-10-14.
2. Si no, se envía ALL-1 si su sesión de 12 tareas terminó completa, sin tareas colgadas, y resolvió 4 o más (la
   base hizo 5 y 5 en las mismas tareas; se admite una menos).
3. Si no, C1 sin tocar.

Esta regla reemplaza a la anterior, cuya rama (2) enviaba el 0,24 sin `write_file`. **Veto 1 del dictamen:** enviar
el bundle público exacto es una copia y contradice la orden del dueño; por eso la rama (3) es C1 y no el 0,24. El
envío del día 15 se rotula «lectura, no mejora». Antes de enviar, el analista de datos y el auditor leen la nota
de C2 y las sesiones.

### Qué dicen las sesiones del 0,24 (ya no son la condición de envío)

Recontadas por el analista de datos (`analista_p24/informe.md`; coincide con el recuento del orquestador). Las dos
sesiones son válidas (12 de 12 tareas con fin, sin colgadas, mismas ruedas que R1):

- El 0,24 exacto resolvió 4 de 12 (269,9 s de media por tarea) y el sin `write_file`, 4 de 12 (268,6 s); 1 par
  discordante en cada sentido (McNemar exacto, p = 1,0).
- **Potencia casi nula.** La regla antigua se cumple el 86 % de las veces si los dos brazos son iguales y todavía
  el 56 % si el sin `write_file` fuera un 25 % peor: descarta un daño grande y no prueba «no peor».
- **Bucle de `submit_patch` vacío:** en cada sesión una tarea llamó 51 (exacta) y 49 (sin `write_file`) veces a
  `submit_patch` con parche de tamaño 0, falla que no aparece en R1 (como mucho 5 por tarea) y que cuesta 1 de 12
  por sesión. Es la razón de ser de la skill `entregar`.
- **«Solo archivos nuevos» ya era 0 de 12 en la exacta,** con `write_file`: la bajada respecto de R1 viene del
  prompt y los topes del 0,24, no de quitar la herramienta.
- La comparación con R1 no es limpia: cambian a la vez prompt, topes y herramientas.

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
- **Lo que refutaría la estrategia:** un error repetido en E2; que la familia 0,24 (o ALL-1) llegue sola a 13 o
  más en 3 lecturas (entonces el LoRA sobra); o, al revés, una nota pública con adaptador que supere a su base
  en 3 tareas (eso subiría la apuesta). G2 ya no puede refutarla: pasó.

## Fechas

| Fecha (2026) | Qué |
|---|---|
| 10-14 | Sesiones de 12 tareas del 0,24 (terminadas); G2 (pasó); G3 relanzada; kit ALL-1 especificado |
| 10-15 | Envío del día 15 según la regla vigente; E2 el primer cupo libre tras puntuar ese envío |
| 10-15 y 10-16 | Resultado de G3 |
| 10-17 00:00 | Caducan 15,36 h de GPU y 20 h de TPU (la de TPU no se usa: no hay pila sin internet ni datos antes del 17) |
| 10-17 a 10-24 | Primer adaptador con la cuota de la semana (30 h como máximo), si pasaron G2, G3 y E2 y hay trayectorias suficientes (ver abajo) |
| 10-18 a 10-31 | Tres lecturas del kit propio en la tabla |
| 11-01 a 11-08 | Tres lecturas del adaptador, con la misma regla; un segundo ciclo (11-08 a 11-21) solo si el primero da al menos el suelo más 1,0 |
| 11-14 | Parada |
| 11-24 | Se congela el kit final y se toman 2 lecturas |
| 12-01 como límite | Se eligen 2 finales por la media |

**Criterio de «trayectorias suficientes».** El dictamen pide 200 trayectorias o más. La conversión de trayectorias
abiertas (`lora_g3/INFORME.md`, § 2.3) da 3 336 que caben en 24 000 tokens, pero solo 142 si además deben caber en
28 llamadas, el tope del kit. El criterio que vale para el kit enviado es el segundo, y con 142 no se llega a 200:
o bien se generan trayectorias propias con ALL-1, o se baja el criterio con una decisión escrita.

Lo que espera la palabra del dueño: E2 y todo envío posterior al día 15. Las sesiones de GPU de hasta 4,5 h las
sube el orquestador, según la entrada de la bitácora.

## Lo que esto no sostiene

- **P(primero)** queda entre 0,01 y 0,035 con los priores del estratega y por debajo de 0,01 con priores
  prudentes. Son juicios y no mediciones; el orden «con adaptador mejor que sin él» se mantiene en ambos.
- **G2 pasó, pero no prueba que un adaptador entrenado ayude.** Que vLLM aplique un adaptador en un cuaderno no
  dice que el puntuador lo acepte (E2) ni que mejore la nota. Los antecedentes públicos recontados por el auditor:
  en el puntuador, 0 éxitos y 2 fallos; en cuaderno, 1 sí y 1 no; de beneficio, una medición, negativa (2 de 32
  frente a 4 de 32).
- **El costo de entrenar** no se reproduce: entre 7 y 115 h por 10 M de tokens según los supuestos. Solo lo
  cierra G3.
- **El concilio tuvo tres fallos de proceso.** Sus tres roles (inteligencia pública, arquitecto y estratega)
  recibieron un encargo con cifras y palancas del concilio 48 y son el mismo modelo, así que su acuerdo no es
  una medición; faltaron el analista de datos, el forense del arnés y la revisión cruzada que exige
  `CONTRIBUTING.md`. Mientras falten, el dictamen declara inválida toda decisión que gaste la cuota de la
  semana del 17 o envíos posteriores al 15. La revisión cruzada sin firmas debe terminar antes del 2026-10-17.
- **Las horas de la bitácora de ese día van unas 2 h adelantadas** respecto de los sellos de los archivos; este
  documento usa fechas y deja las horas a la bitácora.
