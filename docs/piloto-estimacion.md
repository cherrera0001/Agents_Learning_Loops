# Piloto: estimación conservada, modelo previsto/usado y cierre verificado

Es un piloto: mide si el registro se sostiene. **No valida** todavía las tallas ni la matriz de modelos de
[`docs/estimation.md`](estimation.md). El ciclo que se pilotea está en
[`CONTRIBUTING.md`](../CONTRIBUTING.md#flujo-por-issue-la-vida-del-proyecto) y su formato de episodio en
[`learning/README.md`](../learning/README.md).

## Pre-registro

Copiado sin cambios de las cifras ni de los criterios desde la épica
[#75](https://github.com/cherrera0001/Agents_Learning_Loops/issues/75), creada el 2026-10-02 (UTC). Fijado
antes de empezar el trabajo.

- **Alcance:** los próximos 8 issues del Project #5, empezando por los hijos de esta épica. Los tableros de vinculaterritorio quedan fuera.
- **Línea base:** las tres cifras de arriba (2/38, 2/25, 0/33).
- **Medidas, cada una sobre los issues del piloto cerrados:** estimación registrada antes de *In Progress*; *Done* con evidencia enlazada; revisiones de estimación; escalamientos; PR adicionales tras el primero; modelo previsto contra usado; tokens solo donde una sesión equivale a un issue.
- **Excluidos:** episodios meta, issues cerrados como «not planned», trabajo de otros agentes sin telemetría.
- **Éxito:** 8 de 8 con estimación previa; 0 *Done* sin evidencia; modelo previsto y usado registrados en los 8; ningún modelo previsto sobrescrito.
- **Detener si:** el registro exige más de una corrección manual por issue, dos agentes pisan el mismo campo, o al cuarto issue nadie consultó los campos nuevos.
- **Límites:** ocho issues no calibran tallas ni la matriz; los pasos fallidos de los episodios y el modelo usado son autoinformados salvo que exista transcripción; los puntos no son horas ni tokens.

«Las tres cifras de arriba» son las de la sección *Contexto* de la épica #75 (auditoría de solo lectura
del 2026-10-01/02, UTC): 2 de 38 tarjetas del Project #5 con estado desalineado (#65 y #68, cerrados con PR
mergeado y tarjeta en *In Progress*); 2 de 25 estimaciones sin *Modelo* (#68, #73); y 0 de 33 episodios con
talla, modelo o estado final.

## Campos del tablero (Project #5)

*Predictivo* es lo que se declara antes de trabajar; *observado* es lo que se registra después.

| Campo | Propósito | Valores | Cuándo se actualiza | Fuente de evidencia | Naturaleza |
|---|---|---|---|---|---|
| Status | Estado de la tarjeta | Todo / In Progress / Done | *In Progress* al crear la rama (implementador); *Done* tras CONFIRMAR (orquestador) | `mergedAt` del PR y comentario de cierre | Observado |
| Talla | Tamaño relativo del issue | XS–XL | En ESTIMAR, antes de *In Progress* | «Estimación v1» del issue | Predictivo |
| Puntos | Tamaño numérico de la talla (no son horas ni tokens) | Número | En ESTIMAR | «Estimación v1» del issue | Predictivo |
| Modelo | Modelo de construcción **previsto** | Nombre del modelo | En ESTIMAR; no se sobrescribe al escalar | «Estimación v1» del issue | Predictivo |
| Incertidumbre | Factor de la estimación | 1 / 2 / 3 | En ESTIMAR | «Estimación v1» del issue | Predictivo |
| Riesgo | Factor de la estimación | 1 / 2 / 3 | En ESTIMAR | «Estimación v1» del issue | Predictivo |
| Modelo usado | Modelo que construyó el issue | Haiku 4.5 / Sonnet 5.5 / Opus 5.5 / Fable 5.1 / Otro agente | En CONFIRMAR | Bloque `outcome` del episodio (autoinformado salvo transcripción) | Observado |
| Escaló | Si hubo que repetir con un escalón superior | No / Sí | En CONFIRMAR | Bloque `outcome` y comentarios del issue | Observado |
| Verificación | Si se cumplió el criterio de cierre de su tipo | Pendiente / Verificada / Fallida | En CONFIRMAR | Evidencia enlazada en el issue ([criterios](entorno/harness.md#criterios-de-cierre-por-tipo-de-trabajo)) | Observado |

En el Project #5, *Done* cierra el issue automáticamente: por eso no se mueve antes de CONFIRMAR.

## Métricas

Todas se calculan sobre los issues del piloto cerrados, sin los excluidos del pre-registro. Con ocho
issues ninguna es una tasa estable: son conteos para decidir si el registro se sostiene.

| Métrica | Fórmula | Denominador | Fuente | Límite | Decisión que permite |
|---|---|---|---|---|---|
| Estimación previa | Issues con «Estimación v1» fechada antes de pasar a *In Progress* | Issues del piloto cerrados | Cuerpo del issue y fecha de movimiento de la tarjeta | La fecha de la tarjeta puede no coincidir con la del trabajo real | Si el paso ESTIMAR se cumple o se debe automatizar |
| *Done* con evidencia | Issues en *Done* con *Verificación* = *Verificada* y evidencia enlazada | Issues del piloto en *Done* | Project #5 y comentario de cierre | La evidencia enlazada no prueba que sea suficiente | Si CONFIRMAR se mantiene como paso previo a *Done* |
| Revisiones de estimación | Comentarios «Estimación v2» por issue | Issues del piloto cerrados | Comentarios del issue, `outcome.estimate_revisions` | Pocas revisiones pueden ser estimación buena o revisión no registrada | **Revisión de estimación** y **división en épica** de los issues que acumulan v2 |
| Escalamientos | Issues con *Escaló* = *Sí* | Issues del piloto cerrados | Campo *Escaló* y `outcome.escalated` | Autoinformado; no distingue fallo del modelo de especificación pobre | **Escalamiento**: si la fila de talla debe subir de modelo |
| PR adicionales | PR del issue menos 1, sumados | Issues del piloto cerrados | `outcome.prs` y el issue | Un PR adicional puede ser trabajo nuevo y no un fallo | Si el alcance de la talla estaba mal medido (**PR adicionales**) |
| Modelo previsto contra usado | Issues con *Modelo* distinto de *Modelo usado* | Issues con ambos campos registrados | Campos *Modelo* y *Modelo usado* | *Modelo usado* es autoinformado salvo `model_source` = `transcript` | Si la matriz de `docs/estimation.md` se respeta; no la calibra |
| Pasos fallidos por talla | Pasos con `success: false` de los episodios, por talla | Pasos de los episodios del piloto | `steps` de los episodios | Autoinformado; ocho issues no dan una distribución | Si una talla concentra fallos (**autoinformado**) |
| Tokens | Tokens de entrada, de caché (escritura y lectura) y de salida, por separado | Solo issues donde una sesión o un subagente equivale a un issue | Transcripción local de Claude Code de esa sesión o subagente | No incluye la revisión del orquestador ni otros agentes; solo existe en la máquina que ejecutó; no es una factura | Coste por talla, solo si el denominador existe |
| Modelo previsto sobrescrito | Issues cuyo campo *Modelo* difiere del modelo de su «Estimación v1» | Issues del piloto cerrados | Campo *Modelo* y cuerpo del issue (su historial de ediciones es visible) | No detecta un cambio que se haga a la vez en el campo y en el cuerpo | Criterio de éxito del pre-registro (debe ser 0) |

## Cálculo por comando

`python -m scripts.devlog pilot` calcula las medidas anteriores sin escribir nada (código 0; 2 si no se pudo
leer el tablero, con el mismo mensaje que `board`):

```bash
python -m scripts.devlog pilot --since 76 [--until 79]            # lee GitHub con gh (GH_TOKEN de cherrera0001)
python -m scripts.devlog pilot --since 76 --snapshot <dir>         # lee <dir>/items.json e issues.json
python -m scripts.devlog pilot --since 76 --transcripts <dir> --map 77=agent-xxx.jsonl
```

- **Población:** issues cerrados como completados, con número entre `--since` y `--until` (opcional) y sin
  épicas; la salida los lista. El episodio de cada issue es el que lo cita primero en su `ref`; con varios
  se suman los pasos y vale el `outcome` del de mayor `seq` que lo tenga.
- **Filas:** estimación completa (*Talla*, *Puntos*, *Incertidumbre*, *Riesgo*), *Done* con *Verificación* =
  Verificada, *Escaló* = Sí, *Modelo* distinto de *Modelo usado*, PR adicionales, revisiones de estimación,
  `model_source` = `transcript`, pasos fallidos por talla (autoinformado) y tokens por issue. Cada una lleva
  numerador y denominador; con denominador 0 dice «sin datos», y con menos de 8 en el denominador no hay
  porcentaje, solo «n de m».
- **Tokens:** solo con `--transcripts`; sin él, «no medido». Se suma el último uso de cada `message.id` de la
  transcripción. El archivo sale de `outcome.transcript` del episodio o de `--map`, que prevalece; un archivo
  declarado que no existe da la fila «transcripción no encontrada»; un archivo vacío o sin ningún uso, «transcripción sin uso
  registrado», y uno que no se lee como UTF-8, «transcripción ilegible». `--map` sin `--transcripts` se avisa
  por stderr y se ignora.
- **Límites:** las transcripciones son locales (solo existen en la máquina que ejecutó), no incluyen la
  revisión del orquestador ni a otros agentes, y no son una factura. El comando cuenta; no declara éxito ni
  valida el piloto.

## Lecturas por ciclo

Se rellena al cerrar cada ciclo de lectura, con las medidas del pre-registro y sus denominadores. El
piloto no se declara validado con una lectura parcial: los criterios de éxito son sobre los 8 issues.

### Ciclo 1

- **Fecha de la lectura:** 2026-10-02 (UTC).
- **Issues incluidos (n = 4):** #76 (XS, tablero), #77 (M, ciclo y plantillas), #78 (S, chequeo) y #79 (S,
  política). Todos cerrados. La épica #75 no se cuenta: no se estima.
- **Medidas y denominadores:**

  | Medida | Numerador | Denominador | Fuente y observaciones |
  |---|---|---|---|
  | Estimación previa | 4 | 4 | «Estimación v1» en el cuerpo al crear el issue; campos del tablero puestos antes de *In Progress* |
  | *Done* con evidencia | 4 | 4 | Comentario de cierre con evidencia en cada issue y *Verificación* = *Verificada* |
  | *Done* antes de CONFIRMAR | 3 | 4 | #77, #78 y #79: la automatización del tablero los movió a *Done* al mergear; estuvieron minutos en *Done* sin verificar. No estaba entre las medidas del pre-registro |
  | Revisiones de estimación | 0 | 4 | Ningún comentario «Estimación v2» |
  | Escalamientos | 0 | 4 | Campo *Escaló* |
  | PR adicionales | 0 | 4 | Un PR por issue (#80 a #83) |
  | Modelo previsto distinto del usado | 0 | 4 | Campos *Modelo* y *Modelo usado* |
  | Modelo usado leído de transcripción | 4 | 4 | #77 a #79: transcripción de cada subagente, `claude-sonnet-5-5` en todos sus mensajes; #76: transcripción de la sesión del orquestador |
  | Modelo previsto sobrescrito | 0 | 4 | Campo *Modelo* igual al de la «Estimación v1» de cada issue |
  | Rondas de corrección del orquestador | 3 | 4 | Una ronda en #77, #78 y #79; ninguna en #76, que implementó el propio orquestador. Todas fueron de documentos o del episodio, ninguna de código |
  | Discrepancia entre suma y ancla | 1 | 4 | #77: la suma daba S y el ancla M |

- **Pasos fallidos de los episodios, por talla (autoinformado):** XS, 3 de 11 (#76); S, 2 de 10 (#78) y 2
  de 7 (#79); M, 2 de 10 (#77). Con un issue por talla, o dos, no hay nada que comparar.
- **Tokens (solo donde un subagente equivale a un issue; transcripciones locales):**

  | Issue | Talla | Entrada | Escritura de caché | Lectura de caché | Salida |
  |---|---|---|---|---|---|
  | #77 | M | 70 | 205 985 | 3 084 359 | 31 235 |
  | #78 | S | 62 | 199 466 | 2 657 709 | 34 631 |
  | #79 | S | 68 | 164 192 | 2 360 600 | 14 670 |

  #76 no se mide: se hizo en la sesión del orquestador, que cubre varios issues. Las cifras no incluyen
  la revisión del orquestador. Cada subagente ejecutó además la comprobación de mutaciones, que tarda más
  de diez minutos y no depende del tamaño del cambio.
- **Criterios de éxito (parcial, 4 de 8):** 4 de 4 con estimación previa; 0 *Done* sin evidencia al cerrar
  el ciclo, aunque 3 de 4 pasaron por *Done* antes de verificarse; modelo previsto y usado registrados en
  los 4; ninguno sobrescrito. No se declara éxito: faltan cuatro issues.
- **Condiciones de parada:** ninguna activada, con dos reservas.
  - «Más de una corrección manual por issue»: hubo como máximo una ronda por issue; «corrección manual»
    no estaba definida y aquí se cuenta como ronda de commits del orquestador en la rama del implementador,
    sin contar la integración de main.
  - «Dos agentes pisan el mismo campo»: ningún agente lo hizo, pero la automatización del tablero escribió
    *Status* por delante del orquestador.
  - «Nadie consultó los campos nuevos»: el chequeo de #78 los lee; su regla 3 señaló #77 en *Done* sin
    verificar.
- **Límites de esta lectura:** cuatro issues, tres de ellos de documentación, diseñados y revisados por la
  misma sesión que escribe esta lectura. El M y un S consumieron tokens de salida parecidos (31 235 y
  34 631): con tres mediciones eso no dice nada sobre las tallas. No hubo ningún issue con Haiku 4.5, así
  que el brazo Haiku sigue sin datos.
- **Decisiones tomadas:**
  1. *Done* deja de significar cierre confirmado; lo es *Verificación* = *Verificada*, y CONFIRMAR termina
     con el chequeo del tablero (#84).
  2. El chequeo gana reglas para el modelo previsto sobrescrito, el resultado incoherente y los issues sin
     tarjeta (#85, primer issue del brazo Haiku).
  3. El arranque del implementador pasa a definiciones versionadas, porque los tres subagentes repitieron
     el mismo fallo de arranque (#86).
  4. La lectura se calculará con un comando (#87) y se comparará con esta, hecha a mano.
  5. La talla se copia en una etiqueta `talla:*` del issue, porque la vista del tablero no muestra los
     campos (#88).

### Ciclo 2

- **Fecha de la lectura:** 2026-10-02 (UTC), sobre una instantánea del tablero de las 02:24.
- **Issues incluidos (n = 4):** #84 (S, lectura del ciclo 1), #85 (S, reglas 7 a 10 del chequeo, brazo
  Haiku), #86 (S, definiciones de implementador) y #87 (S, lectura por comando). Todos cerrados.
- **Medidas y denominadores:**

  | Medida | Numerador | Denominador | Fuente y observaciones |
  |---|---|---|---|
  | Estimación previa | 4 | 4 | «Estimación v1» al crear el issue; campos antes de *In Progress* |
  | *Done* con evidencia | 4 | 4 | Comentario de cierre y *Verificación* = *Verificada* |
  | *Done* antes de CONFIRMAR | al menos 1 | 4 | #84, señalado por la regla 3 del chequeo. #86 y #87 se cerraron con `Closes` por el mismo mecanismo, pero nadie registró la observación. #85 no: su PR no llevaba `Closes` |
  | Revisiones de estimación | 0 | 4 | Ningún comentario «Estimación v2» |
  | Escalamientos | 1 | 4 | #85: Haiku 4.5 → Sonnet 5.5, con el motivo en un comentario del issue |
  | PR adicionales | 0 | 4 | Un PR por issue (#89, #90, #91 y #93) |
  | Modelo previsto distinto del usado | 1 | 4 | #85 |
  | Modelo usado leído de transcripción | 3 | 4 | El episodio de #85 dice `self-reported`; el orquestador leyó después las dos transcripciones (comentario de cierre), pero el episodio ya estaba en main |
  | Modelo previsto sobrescrito | 0 | 4 | Campo *Modelo* igual al de la «Estimación v1»; en #85 sigue diciendo Haiku 4.5 tras escalar |
  | Rondas de corrección | 3 | 4 | #85, el escalamiento; #86, una del orquestador; #87, una del propio implementador tras la revisión; #84, ninguna |
  | Discrepancia entre suma y ancla | 2 | 4 | #84 (suma XS, ancla S) y #87 (suma M, ancla S) |

- **Revisiones independientes** (no estaban en el pre-registro; empezaron en este ciclo): tres de los
  cuatro PR pasaron por un subagente revisor antes del merge. En el PR #90, 6 de 18 defectos inyectados
  pasaban los tests y había cuatro tests existentes modificados. En el PR #91, 4 de 26 afirmaciones no
  coincidían con su fuente. En el PR #93, 4 de 48 defectos pasaban y hubo cinco hallazgos no bloqueantes.
  En los tres casos el autor no había declarado esos defectos. El PR #89 no pasó por revisor.
- **Criterios de éxito y condiciones de parada:** se leen sobre los 8 en la lectura final.
- **Límites de esta lectura:** cuatro issues, todos de talla S y de herramientas o documentación del propio
  piloto. Las revisiones las encargó y las interpretó la misma sesión que orquesta.
- **Decisiones tomadas:** las de la lectura final.

### Lectura final (8 de 8)

- **Fecha:** 2026-10-02 (UTC). **Población:** #76 a #79 y #84 a #87, los ocho issues del pre-registro.
  Quedan fuera #88 y #94, que siguieron el mismo ciclo pero no estaban entre «los próximos 8».
- **Cómo se calculó:** las diez primeras filas, con
  `python -m scripts.devlog pilot --since 76 --until 87` sobre la instantánea; las cuatro últimas, a mano,
  porque el comando no las calcula.

  | Medida | Resultado | Origen |
  |---|---|---|
  | Estimación completa en el tablero | 8 de 8 | Comando |
  | *Done* con *Verificación* = *Verificada* | 8 de 8 | Comando |
  | Escalamientos | 1 de 8 (#85) | Comando |
  | Modelo previsto distinto del usado | 1 de 8 (#85) | Comando |
  | PR adicionales | 0 de 8 | Comando (episodios) |
  | Revisiones de estimación | 0 de 8 | Comando (episodios) |
  | `model_source` = `transcript` | 7 de 8 (falta #85) | Comando (episodios) |
  | Pasos fallidos, XS (autoinformado) | 3 de 11 | Comando |
  | Pasos fallidos, S (autoinformado) | 16 de 61, en seis issues | Comando |
  | Pasos fallidos, M (autoinformado) | 2 de 10 | Comando |
  | *Done* antes de CONFIRMAR | al menos 4 de 8 (#77, #78, #79, #84) | A mano |
  | Modelo previsto sobrescrito | 0 de 8 | A mano |
  | Issues con alguna ronda de corrección | 6 de 8 (todos menos #76 y #84, que hizo el orquestador) | A mano |
  | Discrepancia entre suma y ancla | 3 de 8 (#77, #84, #87) | A mano |

- **Tokens de los implementadores** (transcripciones locales; no incluyen al orquestador):

  | Issue | Talla | Modelo | Entrada | Escritura de caché | Lectura de caché | Salida |
  |---|---|---|---|---|---|---|
  | #77 | M | Sonnet 5.5 | 70 | 205 985 | 3 084 359 | 31 235 |
  | #78 | S | Sonnet 5.5 | 62 | 199 466 | 2 657 709 | 34 631 |
  | #79 | S | Sonnet 5.5 | 68 | 164 192 | 2 360 600 | 14 670 |
  | #85, primera entrega | S | Haiku 4.5 | 830 | 233 865 | 8 304 906 | 39 605 |
  | #85, corrección | S | Sonnet 5.5 | 70 | 193 039 | 2 917 187 | 30 826 |
  | #86 | S | Sonnet 5.5 | 44 | 242 585 | 1 345 337 | 12 334 |
  | #87, con su ronda de corrección | S | Sonnet 5.5 | 98 | 713 380 | 4 980 099 | 55 976 |

  #76 y #84 no se miden: se hicieron en la sesión del orquestador. Los subagentes revisores sumaron, en
  tokens de salida, 14 816 (PR #90, Opus 5.5), 10 339 (PR #91, Sonnet 5.5) y 20 282 (PR #93, Opus 5.5).
  Los tokens de modelos distintos no se suman ni se comparan como costo: tienen precios distintos.

- **Criterios de éxito del pre-registro, uno por uno:**
  1. *8 de 8 con estimación previa.* **Cumplido**: los ocho issues nacieron con su «Estimación v1» en el
     cuerpo y los campos se pusieron antes de *In Progress*.
  2. *0 Done sin evidencia.* **Cumplido al cierre**, con una reserva: al menos cuatro tarjetas estuvieron
     en *Done* sin verificar durante minutos, por la automatización del tablero. Desde #84, *Done* ya no
     cuenta como cierre confirmado.
  3. *Modelo previsto y usado registrados en los 8.* **Cumplido** en el tablero. En los episodios, 7 de 8
     dicen que el modelo se leyó de una transcripción.
  4. *Ningún modelo previsto sobrescrito.* **Cumplido**, incluido el único caso con escalamiento.

  Lo que esto permite decir: **el registro se sostuvo en ocho issues**. No dice nada sobre si las tallas
  o la matriz de modelos son correctas, que el piloto no medía.
- **Condiciones de parada, una por una:**
  1. *Más de una corrección manual por issue.* **No activada**: ningún issue tuvo más de una ronda. La
     condición estaba mal definida; aquí «ronda» es un conjunto de commits de corrección posterior a la
     entrega, sin contar la integración de main.
  2. *Dos agentes pisan el mismo campo.* **No activada** entre agentes. La automatización del tablero sí
     escribió *Status* por delante del orquestador.
  3. *Al cuarto issue nadie consultó los campos nuevos.* **No activada**: los leen `devlog board` y
     `devlog pilot`.
- **Brazo Haiku** (`docs/estimation.md` § 2.6): una entrega (#85), una verificación fallida. El código era
  correcto en lo probado y pasó el CI; falló la disciplina de la entrega (cuatro tests existentes
  modificados sin declararlo, un requisito sin cubrir, PR sin `Closes`). Esa entrega consumió más
  mensajes y más lectura de caché que cualquiera de Sonnet 5.5 del piloto, y después hubo que pagar la
  corrección. Es un solo caso: no confirma ni refuta la hipótesis, y el brazo sigue abierto.
- **Límites:**
  - Ocho issues: siete de talla S o XS y uno M, todos de documentación o herramientas del propio piloto.
    Ninguno de talla L o XL, ninguno de experimento y ninguno de sistema externo salvo el tablero.
  - Quien diseñó el piloto lo ejecutó, lo midió y escribe esta lectura. Lo que no depende de esa sesión
    son el CI, las transcripciones y los informes de los subagentes revisores.
  - Los pasos fallidos de los episodios son autoinformados. Las tallas no se pueden comparar: seis de los
    ocho son S.
  - La comparación entre el comando y la lectura manual del ciclo 1 comparte fuente (tablero y episodios),
    salvo los tokens, que se recalcularon con un guion independiente.
- **Decisiones tomadas:**
  1. El ciclo ESTIMAR → CONFIRMAR, los campos del tablero, el chequeo y la lectura por comando se quedan
     como práctica del repositorio; el piloto termina.
  2. Todo PR pasa por un subagente revisor antes del merge (`revisor-codigo` o `revisor-docs`): en los
     cuatro PR revisados (#90 a #93) encontró defectos que el autor no había declarado. El orquestador
     sigue decidiendo el merge.
  3. Las definiciones de implementador exigen `Closes` al principio del PR, el recall como primera orden
     y no tocar tests existentes sin declararlo (#94).
  4. El brazo Haiku sigue como hipótesis; la próxima entrega fallida lo detiene.
  5. Queda sin resolver, como propuesta: `learning/dev_memory.json` es un archivo derivado que cada PR
     versiona, así que los PR paralelos chocan siempre en él y hubo que integrar main y regenerarlo a mano
     en los PR #81, #82, #83, #90, #91 y #93. Las tallas y la matriz siguen sin calibrar: haría falta un
     piloto con issues de talla L y XL y de tipo experimento.
