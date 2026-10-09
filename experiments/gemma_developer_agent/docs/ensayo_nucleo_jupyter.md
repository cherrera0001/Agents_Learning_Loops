# Registro del notebook de la iteración 08 y ensayo bajo un núcleo Jupyter real (#160)

**Nada de esto se subió, se envió ni se corrió en Kaggle, y no se gastó cuota de GPU.** Todo lo que este
documento mide se midió en esta máquina, en Docker, el 2026-10-09 (UTC), con un modelo falso. Las cifras son
de un ensayo local: dicen si el registro explica un corte, no cuántas tareas resuelve el agente.

La vuelta 40 del experimento Kaggle decidió que la iteración 08 no se sube sin tres cosas: el rescate que
mira bytes (#156), el notebook con su registro y un ensayo local que demuestre que ese registro explica un
corte. Este documento cubre las dos últimas.

«Arnés» es aquí el paquete `swegemma` de la competencia. «Sesión del agente» es la corrida de una tarea;
«sesión del notebook» es la corrida entera en Kaggle.

## Qué se versiona y qué no

| Pieza | Dónde | Versionada |
|---|---|---|
| Los enganches de registro, que el notebook lleva como una celda | [`scripts/kaggle_registro_enganches.py`](../../../scripts/kaggle_registro_enganches.py) | Sí, con `tests/test_kaggle_registro_enganches.py` |
| El sorteo de tareas y el lector del registro | [`scripts/kaggle_registro.py`](../../../scripts/kaggle_registro.py) | Sí, con `tests/test_kaggle_registro.py` |
| `armar.py`, el ensayo, el modelo falso, el Dockerfile y los notebooks armados | `experiments/gemma_developer_agent/data/rescate_kaggle/instrumentos/iteracion_08/` | No: `data/` está ignorada por git |
| Las salidas del ensayo | `…/iteracion_08/ensayo_salida/` | No; se citan por ruta y SHA-256 ([huellas](#huellas)) |

## El notebook de la iteración 08

`armar.py` lo arma a partir del de la iteración 07 y se detiene si algo no cuadra. Arma dos notebooks, uno
por pasada, porque 120 tareas no caben en una sesión de 9 000 s.

| Qué cambia respecto de la 07 | Celda | Líneas (quitadas, añadidas) |
|---|---|---|
| Condición `A` y un solo grupo, `sorteo_60`, con las 60 tareas sorteadas | 4 | 2, 2 |
| Celda nueva: el texto de `kaggle_registro_enganches.py`, byte a byte, la línea que instala el registro y la guardia previa (17 líneas) | 8 | celda nueva |
| Plan de una pasada (`A8P1` o `A8P2`), nombres de salida `iteracion_08_p1` o `_p2`, tope de sesión de 150 min con 10 de margen, las llamadas al registro y la guardia tras la primera tarea (2 líneas) | 10 (antes 9) | 5, 22 |
| Cierre del registro y nuevo empaquetado antes de detener el servidor | 11 (antes 10) | 0, 8 |

Las celdas 0, 1, 2, 3, 5, 6, 7 y 9 son las de la 07, byte a byte (la 9 es su antigua 8).

- **Condición.** El zip `submission_a_ajustado.zip` tiene el SHA-256
  `d8a3e1d3558f03b72b3f86037ff53b462a8f66566e1bb7907240bcb0ce4d7182`. `armar.py` comprueba que sus seis
  archivos son, byte a byte, los de la carpeta `envios/a_kit_ajustado` y los de la condición A del notebook
  de la iteración 04, y que su `eval_config.yaml` dice 4 minutos y 40 llamadas.
- **Dos pasadas.** La pasada 2 es la pasada 1 con `A8P1` → `A8P2` e `iteracion_08_p1` → `iteracion_08_p2`:
  cambia una línea en la celda 8 y tres en la 10, y nada más. `armar.py` lo comprueba.
- **Topes.** No se cambian los del agente ni los de la condición. El tope de sesión vuelve a los 150 min y 10
  de margen de las iteraciones 03, 04 y 06 (la 07 los había recortado a 60 y 5 por la cuota que quedaba). El
  tope del conjunto de tareas sigue en `TOPE_SEGUNDOS = 7200`, que vence antes que los 150 min: ver
  [lo que queda sin medir](#lo-que-el-ensayo-no-puede-decir).

Notebooks armados, de 90 482 bytes cada uno:

| Notebook | SHA-256 |
|---|---|
| `kernel_iteracion_08_p1/iteracion.ipynb` | `9f3fdf02b367d989f3cf931ddb3d0f77c67027dd6138f4e8a240b86bd75bcc4a` |
| `kernel_iteracion_08_p2/iteracion.ipynb` | `7305a3c10c9b61484ee8dcaf216077afd4309fd2785a54a5c3a7bc2ac145bfc9` |

El texto de los enganches que llevan tiene el SHA-256
`fd1d3ff7de7f37776ae6f9b27d9cabfd29a877d4915ab9c956ad09a44fbf9b0c`, el de
`scripts/kaggle_registro_enganches.py` en el commit `41ec1c5`. Si ese archivo cambia, los notebooks se vuelven
a armar y el ensayo se repite.

## Los enganches

`instalar_registro` deja cuatro archivos en `/kaggle/working`: `registro_<nombre>.jsonl` (eventos),
`latido_<nombre>.jsonl`, `servidor_log_<nombre>.txt` y `diff_en_curso_<nombre>.diff`. Los tres primeros viajan
además dentro del zip `crudo_*.zip`, bajo `registro/`. El diff de cada tarea queda en el zip bajo
`diffs_cierre/`.

| Enganche del issue | Cómo se hace | Qué deja |
|---|---|---|
| 1. Inicio y fin de cada petición, emparejados | Envoltorio de `LiteLLMClient.acompletion`, la única ruta por la que el arnés llama al modelo | `peticion_inicio` (número, hora, mensajes, caracteres de entrada) y `peticion_fin`. El inicio se sincroniza a disco antes de llamar |
| 2. Motivo de fin de cada petición | El mismo envoltorio | `stop`, `tool_calls`, `length`, `cancelada` o `error`, con segundos y tokens |
| 3. Latido periódico con el estado de la GPU | Un hilo, cada 30 s (`LATIDO_SEGUNDOS`) | `nvidia-smi` por GPU, salud y código de salida del servidor, petición en vuelo y diff del árbol en curso |
| 4. Log entero del servidor | El latido lo copia entero; `cerrar()` hace la última copia antes de `server_instance.stop()`, que lo borra | `servidor_log_<nombre>.txt` |
| 5. Diff del árbol al cierre de cada sesión del agente | Envoltorio de `sandbox_stop` en `swegemma.harness.agent_runner`: el diff se toma justo antes de destruir el sandbox | `diffs_cierre/<tarea>.diff` y `diff_cierre` (bytes, SHA-256, archivos) |
| 6. Logs por tarea | `force_jupyter=False` solo en la consola del log por tarea ([por qué no la línea global](#el-control-sin-parche-y-la-línea-de-rich)) | `logs/<tarea>.log` con contenido |

Además de los seis, el ensayo obligó a añadir uno: **el motivo de fin de la sesión del agente** (`agente_fin`,
envoltorio de `Evaluator._run_agent_sandbox`). El arnés descarta ese motivo cuando el parche pasa las pruebas
([hallazgo 1](#lo-que-el-ensayo-encontró-y-el-concilio-no-tenía)).

Ningún enganche cambia el agente, su instrucción, sus herramientas ni sus topes. Un fallo del registro se
cuenta (`errores_del_registro`) y la llamada original sigue.

### Las dos guardias

Sin guardia, un enganche roto se descubre al final, con la cuota gastada. El notebook lleva dos, y ninguna
toca el agente, sus topes ni la condición:

| Guardia | Dónde | Cuándo detiene el notebook |
|---|---|---|
| `exigir_enganches` | Celda 8, antes de la primera tarea | Si un enganche exigido no quedó instalado. Antes de lanzar, cierra el registro, detiene el servidor y limpia, como las demás celdas. Las retrollamadas de litellm no se exigen: son solo el canal de comparación |
| `comprobar_primera_tarea` | Celda 10, tras la primera tarea, con su zip ya guardado | Si su `logs/<tarea>.log` no existe o pesa 0 bytes, o si el registro no tiene ninguna petición con inicio y fin |

La segunda existe porque un enganche puede decir «instalado» y no surtir efecto: el arnés podría crear la
consola o llamar al modelo por otra ruta. Las dos se ensayaron bajo el núcleo
([resultado](#resultado-por-escenario)).

### Cómo se lee el registro

```bash
python -m scripts.kaggle_registro diagnosticar --salida <carpeta o zip de salida de una sesión>
python -m scripts.kaggle_registro comprobar --rescate <carpeta de un rescate> [--notebook <slug>]
```

`diagnosticar` dice si el registro es de fiar, si la sesión se cerró o murió desde fuera, qué tope cortó cada
tarea, qué petición quedó en vuelo o cortada y qué diff quedó. Agrupa por corrida de tarea, no por nombre: si
una tarea se repite, cada corrida conserva lo suyo. Distingue dos cosas que la primera versión mezclaba:

- **petición en vuelo:** un inicio sin fin de ningún tipo. Solo queda si la sesión murió durante la llamada;
- **petición cortada:** la última petición de la tarea, si no llegó a responderse (`cancelada`, `error` o sin
  fin). Un error transitorio seguido de peticiones respondidas no es ni lo uno ni lo otro.

| Código | Qué significa |
|---|---|
| 0 | Registro fiable y sesión completa (en `sortear`: lista reproducida) |
| 1 | Solo `sortear`: la lista sorteada difiere de la guardada |
| 2 | Entrada inválida o ilegible: archivo ausente, JSON roto, acta o validez sin sus campos |
| 3 | Sesión cortada por el notebook; la causa está en el registro |
| 4 | Registro no fiable: un enganche exigido no se instaló, hubo errores propios, hay tareas corridas sin ninguna petición respondida, falta `registro_instalado` o una guardia detuvo el notebook |
| 5 | Sesión muerta desde fuera: el registro no termina en `cierre` |

`comprobar` corre `kaggle_rescate --sin-red` y después `diagnosticar` sobre los archivos `salida__registro_*`
de cada notebook del rescate. Sale con el código del rescate si no es 0 y, si lo es, con el del primer
diagnóstico que no lo sea.

## Tras una corrida real

El rescate solo mira bytes. Sobre una sesión muerta desde fuera sale con 0, porque el zip se empaquetó tras
la tarea anterior y está sano; sobre un notebook que la guardia previa detuvo también, porque no hay zip. Por
eso el rescate solo no basta:

1. Bajar con `python -m scripts.kaggle_rescate --destino <carpeta>` y anotar el código y la hora.
2. Correr `python -m scripts.kaggle_registro comprobar --rescate <carpeta fechada>`. Distinto de 0 es un
   hallazgo; el JSON dice de cuál de los dos y el veredicto de cada sesión.
3. Si el diagnóstico dice 5 (muerta desde fuera), el zip no trae el cierre ni la tarea cortada. Lo que hay
   que mirar son los archivos sueltos de la salida, que el notebook escribe fuera del zip:
   `registro_<nombre>.jsonl` (el inicio sin fin), `latido_<nombre>.jsonl` (el último latido, con la petición
   en vuelo y el estado del servidor), `diff_en_curso_<nombre>.diff` (el árbol en ese latido) y
   `servidor_log_<nombre>.txt`.
4. Si dice 4, leer `problemas_del_registro`: la corrida no es válida como registro aunque tenga resultados.

Que Kaggle conserve esos archivos sueltos cuando mata una sesión no está medido.

## El sorteo

Semilla fijada en un comentario del issue antes de sortear (2026-10-08, 23:55 UTC):
`ALL-kaggle-iteracion-08-2026-10-08`. Universo: las tareas de clase `discrimina` de `validez_ensayo.json`
(SHA-256 `d37264b1c9c44937fcab4d95429c790fbfcd06c8ebf524bce77700eea2cdd5bc`; las dos copias que hay en
`data/` son iguales), ordenadas por `instance_id`. Son 71. Generador:
`random.Random(int(sha256(semilla).hexdigest(), 16))`; lista: `sample(universo, 60)`.

```bash
python -m scripts.kaggle_registro sortear --validez <validez_ensayo.json> --salida <sorteo_60.json>
```

El guion se detiene si el universo no tiene 71 tareas y no pisa una lista guardada que difiera. SHA-256 de la
lista en su orden, una tarea por línea: `a9fb55f0b45288c4846d291e0264dbbec16bb71e5addf1dad6fbfeece9e650d5`.
Son 33 tareas de rich y 27 de fastapi. Las dos pasadas usan esta lista en este orden:

`rich_3470`, `rich_3942`, `rich_3180`, `rich_3882`, `rich_4079`, `rich_3518`,
`fastapi_14616`, `fastapi_15280`, `rich_2725`, `rich_3105`, `rich_3278`, `rich_3905`,
`fastapi_14301`, `fastapi_14786`, `fastapi_14487`, `rich_3052`, `rich_3935`, `fastapi_15588`,
`fastapi_14463`, `fastapi_14873`, `rich_3063`, `rich_3468`, `fastapi_14448`, `rich_3535`,
`rich_4077`, `rich_3067`, `rich_3454`, `rich_4075`, `rich_4076`, `fastapi_14258`,
`fastapi_14986`, `fastapi_14419`, `rich_3472`, `fastapi_14479`, `rich_3043`, `fastapi_14492`,
`rich_3676`, `rich_2943`, `rich_4070`, `fastapi_14458`, `rich_3061`, `rich_3944`,
`rich_3777`, `rich_3938`, `fastapi_9555`, `fastapi_13537`, `fastapi_5077`, `fastapi_5624`,
`fastapi_15589`, `fastapi_14794`, `fastapi_9753`, `rich_3506`, `fastapi_14372`, `fastapi_14306`,
`fastapi_9425`, `rich_3772`, `rich_4006`, `fastapi_13920`, `rich_3894`, `fastapi_15800`.

Quedan fuera del sorteo 11: `fastapi_11194`, `fastapi_15661`, `rich_3006`, `rich_3471`, `rich_3480`,
`rich_3521`, `rich_3675`, `rich_3718`, `rich_3930`, `rich_3934` y `rich_3953`.

## El ensayo

**Imagen.** `aal-ensayo-nucleo:local`, derivada de `aal-ensayo:local` sin pisarla (`imagen/Dockerfile`, SHA-256
`8243082780996d9fe83295046ad7181d26d35ca097fde2e45f9dbaf70dc599c8`). Añade `ipykernel` 6.29.5, `nbclient`
0.10.2 y `pytest` 8.4.2 con sus dependencias; ninguno de los paquetes que ya traía la imagen cambió de
versión (`/cambios_de_paquetes.txt` dentro de la imagen: solo líneas añadidas).

**Cómo corre.** `nbclient` arranca un núcleo `python3` y le manda las celdas del `.ipynb` armado. No hay `exec`
en el proceso del ensayo: el registro del notebook anota `ZMQInteractiveShell` y un identificador de proceso
distinto del proceso del ensayo, y el ensayo lo exige.

| Celdas | Cómo corren en el ensayo |
|---|---|
| 3, 6, 8 (enganches y guardia previa), 9, 10 (tareas) y 11 (cierre) | Tal cual |
| 4 | Tal cual salvo la línea `GRUPOS`, recortada a las tareas sorteadas con snapshot en esta máquina |
| 0, 1 y 2 | Doble: no hay `/kaggle/input` y el arnés ya está instalado en la imagen |
| 5 | Doble: la demostración del grafo usa la primera tarea de `tasks.jsonl`, que aquí no tiene grafo |
| 7 | Doble: no hay GPU. Deja `server_instance` con `base_url`, `log_path` y un `stop()` que borra el log, como el servidor real. En los dos escenarios de guardia lleva además el sabotaje |

De las 60 tareas sorteadas, 26 tienen snapshot en esta máquina. La corrida completa usa esas 26; las demás,
las 6, las 5 o las 3 primeras.

**Modelo falso.** Vive fuera del núcleo. En cada tarea aplica el parche de referencia y entrega, salvo en la
tarea que fuerza el corte. Escribe un log propio, que hace de log del servidor. `nvidia-smi` es un doble que
inventa cuatro GPU.

### Resultado por escenario

Dieciséis corridas, cada una en un contenedor efímero, entre las 02:20 y las 02:44 UTC del 2026-10-09, todas
con la misma versión del ensayo y del notebook. Las dieciséis pasan su validación, que incluye el código que
debe dar `diagnosticar`. «Rescate» es el código de `kaggle_rescate --sin-red` sobre esa salida; «Comprobar»,
el de la orden que junta rescate y diagnóstico.

| Escenario | Notebook | Tareas | Qué se fuerza | Cómo termina el notebook | Logs por tarea de 0 bytes | Diagnóstico | Rescate | Comprobar |
|---|---|---|---|---|---|---|---|---|
| `completa` | pasada 1 | 26 | Nada | Completo | 0 de 26 | 0 | 0 | 0 |
| `control_sin_parche` | sin el parche de rich | 6 | Nada | Completo | **6 de 6** | 0 | **4** | 4 |
| `parche_global` | con el parche global | 6 | Nada | Completo | 0 de 6 | 0 | 0 | 0 |
| `con_enganches` (3 corridas) | pasada 1 | 6 | Nada | Completo | 0 de 6 | 0 | 0 | 0 |
| `sin_enganches` (3 corridas) | registro inactivo | 6 | Nada | Completo | 6 de 6 | no hay registro | 4 | 2 |
| `corte_tiempo` | pasada 1 | 3 | El modelo retiene una petición más de 4 min | Completo: la sesión sigue | 0 de 3 | 0 | 0 | 0 |
| `corte_llamadas` | pasada 1 | 3 | El modelo no entrega y pasa de 40 llamadas | Completo: la sesión sigue | 0 de 3 | 0 | 0 | 0 |
| `corte_sesion` | pasada 1 | 5 | `TOPE_SESION_SEGUNDOS=45` | `cortado_por: sesion`, 1 tarea corrida | 0 de 1 | 3 | 0 | 3 |
| `corte_sesion_duro` | pasada 1 | 3 | El ensayo mata el núcleo con una petición en vuelo | No llega a escribir `cortado_por` | 0 de 1 | **5** | 0 | 5 |
| `servidor_caido` | pasada 1 | 3 | El servidor cierra la conexión y deja de escuchar | `cortado_por: servidor`, 2 tareas corridas | 0 de 2 | 3 | 0 | 3 |
| `guardia_enganche` | pasada 1 | 3 | El doble de la celda 7 borra `agent_runner.Console` | Se detiene en la celda 8, sin correr ninguna tarea | sin zip | **4** | 0 | 4 |
| `guardia_log` | pasada 1 | 3 | El doble de la celda 7 hace que toda consola con archivo se crea en Jupyter | Se detiene tras la primera tarea: `cortado_por: fallo RuntimeError` | 1 de 1 | **4** | 4 | 4 |

Cada variante de notebook difiere de la pasada 1 en una sola línea, la que instala el registro; `armar.py` lo
comprueba.

**Sesión sin corte (`completa`).** 78 peticiones iniciadas y 78 con su fin: 52 con motivo `tool_calls` y 26 con
`stop`. El registro cuenta las mismas 78 que recibió el servidor falso. Las 26 tareas tienen su fila de fin, su
motivo de fin del agente y su diff al cierre. En el zip (234 483 bytes, 135 miembros, ninguno de 0 bytes) el
registro pesa 286 204 bytes en tres archivos: eventos, latido (270 latidos) y log del servidor. El log
original del servidor ya no existía al terminar: el doble lo borró al detenerse, así que la copia es anterior.

**Las dos guardias.**

- `guardia_enganche`: el enganche de los logs falló con `AttributeError` y el notebook se detuvo en la celda 8
  con «GUARDIA registro: no quedó instalado logs por tarea (rich)». El servidor falso no recibió ninguna
  petición y no hay JSON de resultados ni zip. Quedaron el registro (con el evento `guardia` y su `cierre`), el
  latido y la copia del log del servidor; el servidor quedó detenido.
- `guardia_log`: el enganche dijo «modo archivo» (instalado), la primera tarea dejó `logs/rich_3470.log` en 0
  bytes y el notebook se detuvo con «GUARDIA registro: el log por tarea rich_3470.log pesa 0 bytes». Corrió una
  tarea de tres; su zip quedó guardado antes de la guardia.

## Los cuatro cortes

Lo que sigue sale de `diagnostico.json` de cada escenario, que el ensayo calcula solo con los archivos de
`/kaggle/working`. La consola del núcleo no se usa para validar.

| Corte | Qué dice la salida que cortó | Petición en vuelo o cortada | Diff del árbol |
|---|---|---|---|
| Tope de tiempo de la tarea | `agente_fin`: «Agent exceeded session timeout (4.0 min)» | Cortada: la 5, inicio a las 02:31:32.502 UTC, 19 145 caracteres de entrada en 4 mensajes, fin `cancelada` (`CancelledError`) a los 240,0 s. No figura en vuelo, porque tiene fin | Al cierre: 6 741 bytes, 2 archivos |
| Tope de llamadas | `agente_fin`: «Agent exceeded tool call budget (40 calls)», 40 llamadas usadas | **Ninguna**: el arnés corta entre dos peticiones. Queda la última: la 49, a las 02:31:35.873 UTC, 29 531 caracteres, fin `stop` | Al cierre: 6 741 bytes, 2 archivos |
| Tope de sesión, cortado por el notebook | Evento `corte` con `sesion`, y `cortado_por: sesion` en el JSON | **Ninguna**: el notebook corta antes de empezar una tarea. Las 3 peticiones tienen su fin | Al cierre de la tarea corrida: 440 bytes |
| Tope de sesión, sesión muerta desde fuera | El registro no termina en `cierre`; el último latido es de los 78,0 s de sesión | En vuelo: la 5, inicio a las 02:31:32.358 UTC, 19 145 caracteres, **sin fin**. El último latido la trae con 6,5 s en vuelo | No hay diff al cierre. Queda el del último latido: 6 741 bytes |
| Servidor caído | Evento `corte` con `servidor` y `servidor_caido_A8P1_3.txt`; `agente_fin`: «…Connection error. LiteLLM Retried: 5 times» | Cortada: la 10. Las peticiones 5 a 10 terminan las seis en `error` (`InternalServerError`), de 13,6 a 14,8 s cada una; la primera a las 02:31:32 UTC, 19 145 caracteres | Al cierre: 6 741 bytes, 2 archivos |

El issue pedía los cuatro cortes con su petición en vuelo. **Dos no la tienen, y no por un fallo del
registro:** el tope de llamadas y el corte de sesión que hace el propio notebook ocurren entre dos peticiones.
En esos dos la salida dice cuál fue la última petición y que terminó. Por eso el tope de sesión se ensayó de
dos maneras: la que el notebook controla y la que no.

El escenario `corte_sesion` cortó tras la primera tarea: el tope de 45 s se cumplió antes de la segunda, y la
tarea lenta que el modelo falso tenía preparada no llegó a correr.

Los tres diff de 6 741 bytes tienen el mismo SHA-256 (`8d83d222…`): es el parche de referencia que el modelo
falso aplica antes de forzar el corte, y es el mismo contenido que el diff del último latido.

En la sesión muerta desde fuera, lo que sobrevive es lo que ya estaba en `/kaggle/working`: el registro, el
latido, la copia del log del servidor, el diff en curso y el zip de la tarea anterior. La carpeta `results/`
de la tarea cortada queda sin empaquetar.

## El control sin parche y la línea de rich

El control reproduce el fallo de Kaggle: bajo el núcleo y sin parche, los 6 `logs/<tarea>.log` pesan 0 bytes
(también en las tres corridas sin enganches: 18 de 18). El ensayo de las iteraciones 06 y 07, que corría las
celdas con `exec`, dejaba logs de 715 bytes y no podía verlo.

El issue proponía la línea `rich.console._is_jupyter = lambda: False`. Se midieron las dos formas sobre las
mismas 6 tareas:

| Modo | Logs por tarea | Texto de la celda de tareas | Salidas ricas de esa celda | Total de la celda |
|---|---|---|---|---|
| Sin parche (control) | 0 bytes | 1 368 bytes | 6 (101 827 bytes) | 103 195 bytes |
| `archivo`: `force_jupyter=False` solo en la consola del log | 721 a 722 bytes | 1 364 a 1 365 bytes | 6 (101 835 a 101 838 bytes) | 103 199 a 103 203 bytes |
| `global`: la línea del issue | 715 a 716 bytes | **139 778 bytes** | 0 | 139 778 bytes |

Las dos devuelven los logs. La línea global cambia además la consola con la que el arnés pinta en el
notebook: deja de usar las salidas ricas de Jupyter y vuelca cada repintado del panel al texto de la celda.
Son dos cifras distintas y hay que dar las dos: el **texto** de la celda crece 102 veces (139 778 contra
1 368 bytes); el **total** de la celda, sumando las salidas ricas que desaparecen, crece 1,35 veces (139 778
contra 103 195). **El notebook armado usa el modo `archivo`**, que deja la salida de la celda como estaba. Es
una desviación de la letra del issue, decidida por esta medición; `armar.py` tiene la constante `PARCHE_RICH`
para cambiarla.

No se midió cuánto texto produciría el modo global con tareas reales de decenas de peticiones, ni si el log
de Kaggle trata igual el texto y las salidas ricas.

## Qué enganche funcionó y cuál no

La pregunta que el concilio dejó abierta era si las retrollamadas de litellm se disparan en la ruta del arnés
y ante una cancelación. Se registraron las dos vías a la vez.

| Qué pasa con la petición | Envoltorio de `acompletion` | Retrollamada de antes de la llamada | De éxito | De fallo |
|---|---|---|---|---|
| Responde (78 de 78 en `completa`) | Inicio y fin con motivo | 78 | 78 | 0 |
| La cancela el tope de tiempo de la tarea | Inicio y fin `cancelada` | 1 | **0** | **0** |
| La sesión muere desde fuera | Inicio, sin fin | 1 | 0 | 0 |
| El servidor no responde (6 peticiones) | Inicio y fin `error` | 6 por petición: litellm reintenta 5 veces por dentro | 0 | 1 por petición |

- **Funcionó:** el envoltorio de `LiteLLMClient.acompletion`. Ve las cuatro situaciones y da el motivo; la
  cancelación le llega como `CancelledError`.
- **Funcionó a medias:** las retrollamadas. Se disparan en la ruta del arnés, pero ante una cancelación solo
  la de antes de la llamada: sin el envoltorio, una petición cancelada y una sesión muerta se verían igual.
  Coincide con lo que midió el verificador limpio fuera del arnés.
- **Funcionó:** el envoltorio de `sandbox_stop` (diff al cierre) y el de `Evaluator._run_agent_sandbox`
  (motivo de fin del agente). Envolver solo `_run_agent_sandbox`, como se propuso en el concilio, no sirve para
  el diff: cuando esa función vuelve, el sandbox ya está destruido.
- **No se guarda:** el texto parcial de la petición cortada.

El registro no tuvo ningún error propio en las corridas que llegaron al cierre (`errores_del_registro` = 0).

## Cuánto cuesta el registro

Seis corridas de las mismas 6 tareas (18 peticiones cada una), tres con enganches y tres sin ellos, una tras
otra y alternadas (con, sin, sin, con, con, sin), entre las 02:35 y las 02:44 UTC. La carga de la máquina
virtual de Docker al empezar cada una fue parecida (`/proc/loadavg` de 0,54 a 1,24). No se controló la carga
del sistema anfitrión: la batería de pruebas de este mismo trabajo corrió en él hasta las 02:28.

| Medida | Con enganches | Sin enganches |
|---|---|---|
| Segundos entre que el servidor responde y recibe la petición siguiente de la misma tarea (media de 12, por corrida) | 0,110 · 0,093 · 0,091 | 0,041 · 0,045 · 0,054 |
| Segundos de reloj por tarea (media y mediana de 18) | 11,28 y 10,00 | 11,82 y 10,25 |
| Tiempo que el propio registro mide que le quita al hilo que lo llama, por corrida | 3,19 · 1,69 · 1,96 s | — |

El registro añade entre 0,04 y 0,07 s por petición en esta máquina. Casi todo es la sincronización a disco
del inicio de cada petición: 47 a 86 ms de media por inicio en estas tres corridas (46 ms en `completa`),
frente a 0,1 ms del fin, que no se sincroniza. Medir la entrada cuesta 0,03 ms. Por tarea hay además cuatro
eventos sincronizados y un diff. En segundos de reloj por tarea la diferencia no se distingue del ruido: las
corridas sin enganches salieron algo más lentas.

El analista de datos, sobre la batería anterior de este mismo día, contó de 16 a 36 ms por petición. La
cifra varía con la carga del disco: no hay un número único.

**Ese tiempo corre dentro del tope de 4 minutos de la tarea.** Las dos pasadas de la iteración 08 lo llevan
por igual, así que no sesga la comparación entre ellas; sí sesga, en esa medida, la comparación con las
iteraciones anteriores, que no llevaban registro. Con peticiones reales de varios segundos sería menos de un
2 % de una petición de 4 s, pero eso es una inferencia: el costo depende del disco y el de Kaggle no se
midió. El evento `cierre` de cada sesión trae `costo_del_registro_s` y el costo por parte, así que la corrida
real lo dirá.

El modelo falso responde en milisegundos, de modo que esta medición no dice nada del tiempo de una tarea
real; solo acota lo que el registro añade.

## El rescate sobre la salida del ensayo

El rescate que mira bytes (#156) está en `main` desde el PR #158 (commit `d8b95f7`). Se corrió con ese guion
(`scripts/kaggle_rescate.py`, SHA-256 `be2553059cca1723dafb961575537443b9443c6e28bb3b16dced37f12add6117`), sin
tocarlo.

`--sin-red` espera la disposición de una bajada real: `envios.json`, `tabla_publica.zip` y
`notebooks/<slug>/` con `estado.json`, `metadatos.json`, `log.txt` y cada archivo de salida como
`salida__<nombre>`. La salida del ensayo no tiene esa forma: `rescate_sobre_ensayo.py` arma esa carpeta por
escenario. `envios.json` y `tabla_publica.zip` se copian del rescate real `2026-10-08T2231Z` solo para que el
resumen tenga su tabla; `estado.json` y `metadatos.json` son dobles que dicen «ensayo local».

Los códigos están en la tabla de [resultado por escenario](#resultado-por-escenario). Lo que el rescate ve y
lo que no:

| Salida | Rescate | Por qué |
|---|---|---|
| `completa` | 0 | 135 miembros revisados, ninguno exigido de 0 bytes |
| `control_sin_parche`, `sin_enganches` | 4 | 6 `logs/<tarea>.log` de 0 bytes |
| `guardia_log` | 4 | 1 `logs/<tarea>.log` de 0 bytes |
| `corte_sesion_duro` | **0** | El zip se empaquetó antes de la muerte y está sano. Lo ve `diagnosticar` (5) |
| `guardia_enganche` | **0** | No hay zip que revisar. Lo ve `diagnosticar` (4) |
| `servidor_caido` | 0 | La tarea caída deja su parche y su salida de pruebas en 0 bytes, que el rescate solo cuenta. Lo ve `diagnosticar` (3) |

En las corridas sin enganches `comprobar` sale con 2: no hay registro que diagnosticar.

## Lo que el ensayo encontró y el concilio no tenía

1. **Una tarea «resuelta» puede haber agotado un tope, y el arnés no lo deja escrito.** En `corte_tiempo` y
   en `corte_llamadas` la tarea cortada quedó con clase `resuelta` y sin error en su fila: el arnés recoge el
   árbol como parche, las pruebas pasan y el motivo del corte se descarta. La clase del notebook sale de ese
   error, así que no lo ve. El evento `agente_fin` lo conserva. En el ensayo esto ocurre porque el modelo
   falso aplica el parche de referencia antes del corte.

   **En las corridas reales ocurrió.** Medición del analista de datos del 2026-10-09, no de este ensayo,
   sobre 12 zips distintos de las iteraciones 03 a 07 (145 sesiones): 4 sesiones figuran como resueltas y
   fueron cortadas por tiempo en mitad de una acción, sin `error_message` (2 en la 06 y 2 en la 07); otras 4
   pasaron el tope y sí cerraron la traza; ninguna cortada por llamadas figura como resuelta. Es lo que
   `agente_fin` viene a registrar. El notebook no cambia cómo puntúa: si una sesión cortada cuyo parche pasa
   cuenta como resuelta lo decide el dueño.
2. **Con el servidor caído, el arnés pierde el parche y el registro lo conserva.** La tarea terminó como
   `otro_error_sin_parche` con 0 caracteres de parche; el diff al cierre guardó los 6 741 bytes que había en
   el árbol.
3. **Un servidor caído cuesta unos tres minutos antes de que el notebook corte.** litellm reintenta 5 veces
   por dentro y el arnés repite la llamada 5 veces más: 6 peticiones entre las 02:31:32 y las 02:34:31 UTC, y
   la tarea duró 192,0 s. El notebook solo mira la salud del servidor antes de cada tarea.
4. **El tope de llamadas no corta al llegar a 40.** El arnés lo comprueba cuando el modelo cede el turno. Un
   modelo que sigue pidiendo herramientas recibe errores de presupuesto y la sesión continúa: en una prueba
   previa, con un modelo falso que nunca cedía, una tarea llegó a 100 peticiones (su salida no se conservó).
   En el escenario final el modelo cede tras 45 llamadas y la sesión tiene 46 peticiones.

## Lo que el ensayo no puede decir

Lo que sigue no se parece a Kaggle o no se midió.

**Del ensayo.**

- **Cinco celdas no corren tal cual:** las guardias de `/kaggle/input`, la instalación de ruedas, la
  comprobación de ruedas, la demostración del grafo y el arranque de vLLM. Un fallo en ellas no lo ve este
  ensayo.
- **El arnés de la imagen puede no ser el de Kaggle.** No está comprobado que el arnés de las ruedas de Kaggle
  tenga `agent_runner.Console` como el de la imagen local. Si no la tiene, la guardia previa detiene el
  notebook; si la tiene pero crea la consola por otra ruta, lo detiene la segunda.
- **El servidor es un doble.** `server_instance` no es un `VllmServer`: no tiene proceso, así que
  `servidor_codigo_de_salida` sale siempre vacío. El log que se copia es el del modelo falso; el de vLLM es
  más grande y no se midió cuánto tarda en copiarse cada 30 s.
- **La GPU es un doble.** No se sabe si `nvidia-smi` acepta en la imagen de Kaggle la consulta que usa el
  latido. Si falla, el latido lo anota en `gpu` y sigue.
- **El modelo falso repite una forma de 3 peticiones por tarea** (aplicar, entregar, cerrar) y no ejercita
  las peticiones de resumen del arnés; en las corridas reales hay de 2 a 22 por corrida.
- **Tareas.** Corrieron 26 de las 60 sorteadas: las ya corridas en iteraciones anteriores, que son las únicas
  con snapshot aquí. Ninguna de las 34 tareas nuevas del sorteo se ejercitó.
- **El escenario del tope de sesión cortó tras la primera tarea**; el modo lento del modelo falso nunca corrió.
- **Qué guarda Kaggle de una sesión que mata.** El ensayo copia `/kaggle/working` después de matar el
  núcleo. No se sabe si Kaggle conserva esos archivos cuando corta una sesión por tiempo.
- **Matar el núcleo no es lo mismo que el corte de Kaggle.** Aquí es una señal al proceso del núcleo.
- **Versiones.** La imagen local trae litellm 1.104.0. Otra versión podría disparar la retrollamada de fallo
  ante una cancelación; el envoltorio no depende de eso.
- **Costo del registro en el disco de Kaggle.** No medido.

**De las pruebas versionadas.**

- La cobertura que exige el CI se mide sobre `src/associative_agent_loop` y **no mide los dos archivos
  nuevos** de `scripts/`.
- Las funciones internas de `instalar_registro` que importan el arnés (`cliente`, `retrollamadas`, `sandbox`,
  `evaluador`, `rich`) se prueban en los tests con módulos falsos. Contra el arnés real solo las ejercita el
  ensayo, que no corre en el CI.
- Tras la revisión independiente se inyectaron 29 defectos, uno a uno, en los dos guiones: los 13 que la
  revisión dijo que sobrevivían y 16 sobre el código de esta ronda. Las pruebas detectan los 29
  (`defectos_inyectados.json`). Es una lista elegida a mano, no una búsqueda exhaustiva.

**De la corrida real.**

- **Topes.** `TOPE_SEGUNDOS = 7200` vence antes que los 150 min de sesión. Con 87 a 111 s por tarea, 60
  tareas son de 5 200 a 6 700 s: es una inferencia y deja poco margen. Si una pasada se corta, las dos
  pasadas pueden cubrir prefijos distintos de la lista, y la comparación entre ellas solo vale sobre el
  prefijo común. No se cambió ningún tope: lo debe mirar el concilio antes de subir.
- **Predicciones fechadas de la iteración 08.** Fuera de este issue: las escribe el concilio.

## Cómo repetirlo

```bash
# 1. Imagen (una vez)
docker build -t aal-ensayo-nucleo:local <instrumentos>/iteracion_08/imagen
# 2. Sorteo, armado, las dieciséis corridas, rescate y resumen
python -m scripts.kaggle_registro sortear --validez <validez_ensayo.json> --salida <instrumentos>/iteracion_08/sorteo_60.json
sh <instrumentos>/iteracion_08/correr_todo.sh
python <instrumentos>/iteracion_08/rescate_sobre_ensayo.py
python <instrumentos>/iteracion_08/resumen_ensayo.py
# 3. Defectos inyectados en los dos guiones versionados (los restaura siempre)
python <instrumentos>/iteracion_08/defectos_inyectados.py <árbol del repositorio>
```

`correr_todo.sh` vuelve a armar los notebooks, borra `ensayo_salida/` y deja un contenedor efímero por
escenario. Tardó 24 minutos. Al terminar no quedó ningún contenedor.

## Huellas

Todo bajo `experiments/gemma_developer_agent/data/rescate_kaggle/instrumentos/iteracion_08/`, ignorado por
git. `ensayo_salida/HUELLAS.txt` lista los 236 archivos de salida con sus bytes y su SHA-256.

| Archivo | SHA-256 |
|---|---|
| `ensayo_salida/HUELLAS.txt` | `3b9137c9c33c68762aadb9e8db9caad3704857cef6641ac8debc676c2ceed2ce` |
| `ensayo_salida/RESUMEN.json` | `6f5c4b0dcffdd885251c05ed0b0e03253d468e09fb587d24e4224bb6ea10a397` |
| `ensayo_salida/rescate_sobre_ensayo.json` | `625bd657dc681d478f28152a11a0abc49087f55b6170a27464a4fac0c519b8aa` |
| `ensayo_salida/completa/informe.json` | `0b215d7af80265a6af610c5b61b12bcb1b0819b9930475d1357b8f64c90f9495` |
| `ensayo_salida/completa/working/crudo_iteracion_08_p1_A8P1.zip` | `3c610a5962f1a547cba6a4ab84fbad2f1c8cc54ea391782c118f5f4f6e859787` |
| `ensayo_salida/control_sin_parche/informe.json` | `59724f1566ff1e9c997c37020717bbe2048ea60191e6f53f3857a0f0978ac99f` |
| `ensayo_salida/control_sin_parche/working/crudo_iteracion_08_p1_A8P1.zip` | `05f0b4b3ca769d4cb10bb6fb5b1942cab154edf279f28354e9b5d9a1c042ce28` |
| `ensayo_salida/corte_tiempo/informe.json` | `6d84e70a6f62ef39e2ae93844a71fdb147b4fa182930c18ab5704fb42a1d06a6` |
| `ensayo_salida/corte_llamadas/informe.json` | `6961eae80a9bab6bf2937a767efd8ed1f804977b6d2f762d69ed818eb2907e62` |
| `ensayo_salida/corte_sesion/informe.json` | `68c107c4bdedc51216c915bfa77d6e28ef055305256249fd3a47766128916bce` |
| `ensayo_salida/corte_sesion_duro/informe.json` | `c7f0879dd89729ef9affe9183607dc4f263314b5806a621c1fefcf38450a5332` |
| `ensayo_salida/servidor_caido/informe.json` | `8d270c1d5d6249618819ce22f90d0c53b4f6c7b8f645a325b1e8115dec3ca3b6` |
| `ensayo_salida/guardia_enganche/informe.json` | `f2853b60d4e5f4bdb9cd65dae91b4f761c3daff3d2a1ad9e4a7038e57224059b` |
| `ensayo_salida/guardia_log/informe.json` | `2a00c10dafb3b782ed167d8db7d8335b83ec81e7a505dbe6581acc31f5691568` |
| `defectos_inyectados.json` | `58e72584026e18a356cc1b2b64be7d61111d37a5a00b8e1827e1905b3e2db1d7` |
| `armado.json` | `3f000e29ba56169b3bdcaa47292dd2d3f04bec2c3616a090a2e8e2234646ef3a` |
| `armar.py` | `a60c796f3c4ee78802c2d7ffd0809fd35d3616d707e6ad22a6be444e9ceffe11` |
| `ensayo_nucleo.py` | `517f475902f43fa222655d8e1d3bacb554245dbca7c09ed87cef7b1d7d25e7c6` |
| `sorteo_60.json` | `0a2d9eb3e2aa5f7e03a3e9e4acac1ff963f21f66058a497a10b1aff0e86c61a6` |
| `imagen/Dockerfile` | `8243082780996d9fe83295046ad7181d26d35ca097fde2e45f9dbaf70dc599c8` |

Las dieciséis corridas usaron la misma versión de `ensayo_nucleo.py` (cada `informe.json` trae su SHA-256).
Dos baterías anteriores del mismo día se descartaron enteras y no están en disco: la primera por un fallo en
la validación del propio ensayo, la segunda porque la revisión independiente obligó a cambiar el notebook
(las guardias) y el diagnóstico.
