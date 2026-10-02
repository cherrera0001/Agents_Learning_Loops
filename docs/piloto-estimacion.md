# Piloto: estimación conservada, modelo previsto/usado y cierre verificado

Es un piloto: mide si el registro se sostiene. **No valida** todavía las tallas ni la matriz de modelos de
[`docs/estimation.md`](estimation.md). El ciclo que se piloteó está en
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
| Tokens | Tokens de la sesión | Solo issues donde una sesión equivale a un issue | Telemetría de la sesión | No se calcula si una sesión cubre varios issues o un issue varias sesiones | Coste por talla, solo si el denominador existe |
| Modelo previsto sobrescrito | Issues cuyo *Modelo* cambió tras ESTIMAR | Issues del piloto cerrados | Historial del campo y «Estimación v1» | Requiere el historial del tablero | Criterio de éxito del pre-registro (debe ser 0) |

## Lecturas por ciclo

Se rellena al cerrar cada ciclo de lectura, con las medidas del pre-registro y sus denominadores. Vacía
hasta que exista la primera lectura; no se declara validado el piloto antes de tenerla.

### Ciclo 1

- **Fecha de la lectura:**
- **Issues incluidos (n):**
- **Medidas y denominadores:**

  | Medida | Numerador | Denominador | Observaciones |
  |---|---|---|---|
  | | | | |

- **Criterios de éxito (8 de 8; 0 *Done* sin evidencia; modelos registrados; ninguno sobrescrito):**
- **Condiciones de parada (activadas o no):**
- **Límites de esta lectura:**
- **Decisiones tomadas:**
