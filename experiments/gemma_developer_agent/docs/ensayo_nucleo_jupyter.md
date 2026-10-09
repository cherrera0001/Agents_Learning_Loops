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

Los tests versionados prueban cada enganche con un doble de lo que envuelve. Que el enganche esté en la ruta
por la que el arnés llama al modelo, y que los logs vuelvan bajo un núcleo, solo lo prueba el ensayo.

## El notebook de la iteración 08

`armar.py` lo arma a partir del de la iteración 07 y se detiene si algo no cuadra. Arma dos notebooks, uno
por pasada, porque 120 tareas no caben en una sesión de 9 000 s.

| Qué cambia respecto de la 07 | Celda | Líneas (quitadas, añadidas) |
|---|---|---|
| Condición `A` y un solo grupo, `sorteo_60`, con las 60 tareas sorteadas | 4 | 2, 2 |
| Celda nueva: el texto de `kaggle_registro_enganches.py`, byte a byte, y la línea que instala el registro | 8 | celda nueva |
| Plan de una pasada (`A8P1` o `A8P2`), nombres de salida `iteracion_08_p1` o `_p2`, tope de sesión de 150 min con 10 de margen, y las llamadas al registro | 10 (antes 9) | 5, 20 |
| Cierre del registro y nuevo empaquetado antes de detener el servidor | 11 (antes 10) | 0, 8 |

Las celdas 0, 1, 2, 3, 5, 6, 7 y 9 son las de la 07, byte a byte (la 9 es su antigua 8).

- **Condición.** El zip `submission_a_ajustado.zip` tiene el SHA-256
  `d8a3e1d3558f03b72b3f86037ff53b462a8f66566e1bb7907240bcb0ce4d7182`. `armar.py` comprueba que sus seis
  archivos son, byte a byte, los de la carpeta `envios/a_kit_ajustado` y los de la condición A del notebook
  de la iteración 04, y que su `eval_config.yaml` dice 4 minutos y 40 llamadas.
- **Dos pasadas.** La pasada 2 es la pasada 1 con `A8P1` → `A8P2` e `iteracion_08_p1` → `iteracion_08_p2`:
  cambia una línea en la celda 8 y tres en la 10, y nada más. `armar.py` lo comprueba.
- **Tope de sesión.** Vuelve a los 150 min y 10 de margen de las iteraciones 03, 04 y 06 (la 07 los había
  recortado a 60 y 5 por la cuota que quedaba). El tope del conjunto de tareas sigue en 7 200 s. No se midió
  si 60 tareas caben en esos topes: ver [lo que queda sin medir](#lo-que-el-ensayo-no-puede-decir).

Notebooks armados, de 87 052 bytes cada uno:

| Notebook | SHA-256 |
|---|---|
| `kernel_iteracion_08_p1/iteracion.ipynb` | `7a1d8ed3092e6ebbd2f3c5daccbe40896d8a19d27ed6dc6fdd80f617fe48f3fc` |
| `kernel_iteracion_08_p2/iteracion.ipynb` | `e85913c0e7d9b8d7573222656399933a590c8551bfb59c5c1d7e80693982720d` |

El texto de los enganches que llevan tiene el SHA-256
`11479036052b1c12cde94759f7d1d178b7e9859c4c652af559ee92d765c1562a`, el de
`scripts/kaggle_registro_enganches.py` en el commit que lo introduce. Si ese archivo cambia, los notebooks se
vuelven a armar y el ensayo se repite.

## Los enganches

`instalar_registro` deja cuatro archivos en `/kaggle/working`, que además viajan dentro del zip `crudo_*.zip`
bajo `registro/`: `registro_<nombre>.jsonl` (eventos), `latido_<nombre>.jsonl`, `servidor_log_<nombre>.txt` y
`diff_en_curso_<nombre>.diff`. El diff de cada tarea queda en el zip bajo `diffs_cierre/`.

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

`python -m scripts.kaggle_registro diagnosticar --salida <carpeta o zip>` lee esos archivos y dice si la sesión
se cerró o murió desde fuera, qué tope cortó cada tarea, cuál era la petición en vuelo y qué diff quedó.

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
| 3, 6, 8 (enganches), 9, 10 (tareas) y 11 (cierre) | Tal cual |
| 4 | Tal cual salvo la línea `GRUPOS`, recortada a las tareas sorteadas con snapshot en esta máquina |
| 0, 1 y 2 | Doble: no hay `/kaggle/input` y el arnés ya está instalado en la imagen |
| 5 | Doble: la demostración del grafo usa la primera tarea de `tasks.jsonl`, que aquí no tiene grafo |
| 7 | Doble: no hay GPU. Deja `server_instance` con `base_url`, `log_path` y un `stop()` que borra el log, como el servidor real |

De las 60 tareas sorteadas, 26 tienen snapshot en esta máquina. La corrida completa usa esas 26; las demás,
las 6 primeras o las 3 primeras.

**Modelo falso.** Vive fuera del núcleo. En cada tarea aplica el parche de referencia y entrega, salvo en la
tarea que fuerza el corte. Escribe un log propio, que hace de log del servidor. `nvidia-smi` es un doble que
inventa cuatro GPU.

### Resultado por escenario

Catorce corridas, cada una en un contenedor efímero, entre las 01:13 y las 01:36 UTC del 2026-10-09. Las
catorce pasan su validación. «Rescate» es el código de salida de `kaggle_rescate --sin-red` sobre esa salida.

| Escenario | Notebook | Tareas | Qué fuerza el modelo falso | `cortado_por` del notebook | Logs por tarea de 0 bytes | Rescate |
|---|---|---|---|---|---|---|
| `completa` | pasada 1 | 26 | Nada | — (completo) | 0 de 26 | 0 |
| `control_sin_parche` | pasada 1 sin el parche de rich | 6 | Nada | — | **6 de 6** | **4** |
| `parche_global` | pasada 1 con el parche global | 6 | Nada | — | 0 de 6 | 0 |
| `con_enganches` (3 corridas) | pasada 1 | 6 | Nada | — | 0 de 6 | 0 |
| `sin_enganches` (3 corridas) | pasada 1 con el registro inactivo | 6 | Nada | — | 6 de 6 | 4 |
| `corte_tiempo` | pasada 1 | 3 | Retiene una petición más de 4 min | — (la sesión sigue) | 0 de 3 | 0 |
| `corte_llamadas` | pasada 1 | 3 | No entrega: pasa de 40 llamadas | — (la sesión sigue) | 0 de 3 | 0 |
| `corte_sesion` | pasada 1 | 5 | Nada; `TOPE_SESION_SEGUNDOS=45` | `sesion`, con 1 tarea corrida | 0 de 1 | 0 |
| `corte_sesion_duro` | pasada 1 | 3 | Retiene una petición; el ensayo mata el núcleo | ninguno: el notebook no llega a escribirlo | 0 de 1 | 0 |
| `servidor_caido` | pasada 1 | 3 | Cierra la conexión con una petición en vuelo y deja de escuchar | `servidor`, con 2 tareas corridas | 0 de 2 | 0 |

Cada variante de notebook difiere de la pasada 1 en una sola línea, la que instala el registro; `armar.py` lo
comprueba.

**Sesión sin corte (`completa`).** 78 peticiones iniciadas y 78 con su fin: 52 con motivo `tool_calls` y 26 con
`stop`. El registro cuenta las mismas 78 que recibió el servidor falso. Las 26 tareas tienen su fila de fin, su
motivo de fin del agente y su diff al cierre. En el zip (233 869 bytes, 135 miembros, ninguno de 0 bytes) el
registro pesa 273 337 bytes en tres archivos: eventos, latido (246 latidos) y log del servidor. El log
original del servidor ya no existía al terminar: el doble lo borró al detenerse, así que la copia es anterior.

## Los cuatro cortes

Lo que sigue sale de `diagnostico.json` de cada escenario, que el ensayo calcula solo con los archivos de
`/kaggle/working`. La consola del núcleo no se usa para validar.

| Corte | Qué dice la salida que cortó | Petición en vuelo | Diff del árbol |
|---|---|---|---|
| Tope de tiempo de la tarea | `agente_fin`: «Agent exceeded session timeout (4.0 min)» | Petición 5: inicio a las 01:23:57.371 UTC, 19 145 caracteres de entrada en 4 mensajes, fin `cancelada` (`CancelledError`) a los 239,9 s | Al cierre: 6 741 bytes, 2 archivos |
| Tope de llamadas | `agente_fin`: «Agent exceeded tool call budget (40 calls)», 40 llamadas usadas | **Ninguna**: el arnés corta entre dos peticiones. Queda la última: la 49, a las 01:24:02.349 UTC, 29 531 caracteres, fin `stop` | Al cierre: 6 741 bytes, 2 archivos |
| Tope de sesión, cortado por el notebook | Evento `corte` con `sesion`, y `cortado_por: sesion` en el JSON | **Ninguna**: el notebook corta antes de empezar una tarea. Las 3 peticiones tienen su fin | Al cierre de la tarea corrida: 440 bytes |
| Tope de sesión, sesión muerta desde fuera | El registro no termina en `cierre`; el último latido es de los 68,6 s de sesión | Petición 5: inicio a las 01:23:57.427 UTC, 19 145 caracteres, **sin fin**. El último latido la trae con 6,1 s en vuelo | No hay diff al cierre. Queda el del último latido: 6 741 bytes |
| Servidor caído | Evento `corte` con `servidor` y `servidor_caido_A8P1_3.txt`; `agente_fin`: «…Connection error. LiteLLM Retried: 5 times» | Peticiones 5 a 10, las seis con fin `error` (`InternalServerError`), de 12,5 a 14,2 s cada una; la primera a las 01:23:57 UTC, 19 145 caracteres | Al cierre: 6 741 bytes, 2 archivos |

El issue pedía los cuatro cortes con su petición en vuelo. **Dos no la tienen, y no por un fallo del
registro:** el tope de llamadas y el corte de sesión que hace el propio notebook ocurren entre dos peticiones.
En esos dos la salida dice cuál fue la última petición y que terminó. Por eso el tope de sesión se ensayó de
dos maneras: la que el notebook controla y la que no.

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

| Modo | Logs por tarea | Texto que la celda de tareas manda a la salida | Salidas ricas de esa celda |
|---|---|---|---|
| Sin parche (control) | 0 bytes | 1 368 bytes | 6 (101 833 bytes) |
| `archivo`: `force_jupyter=False` solo en la consola del log | 721 a 722 bytes | 1 363 a 1 367 bytes | 6 (101 837 a 101 842 bytes) |
| `global`: la línea del issue | 715 a 716 bytes | **131 447 bytes** | 0 |

Las dos devuelven los logs. La línea global cambia además la consola con la que el arnés pinta en el
notebook: deja de usar las salidas de Jupyter y vuelca cada repintado del panel al texto de la celda, 96 veces
más texto con tareas de tres peticiones. **El notebook armado usa el modo `archivo`**, que deja la salida de la
celda como estaba. Es una desviación de la letra del issue, decidida por esta medición; `armar.py` tiene la
constante `PARCHE_RICH` para cambiarla.

No se midió cuánto texto produciría el modo global con tareas reales de decenas de peticiones.

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

El registro no tuvo ningún error propio en las catorce corridas (`errores_del_registro` = 0 en las que
llegaron al cierre).

## Cuánto cuesta el registro

Seis corridas de las mismas 6 tareas (18 peticiones cada una), tres con enganches y tres sin ellos, una tras
otra y alternadas (con, sin, sin, con, con, sin), entre las 01:28 y las 01:36 UTC. La carga de la máquina
virtual de Docker al empezar cada una fue parecida (`/proc/loadavg` de 0,57 a 1,16). No se controló la carga
del sistema anfitrión, donde otros procesos corrieron pruebas hasta poco antes.

| Medida | Con enganches | Sin enganches |
|---|---|---|
| Segundos entre que el servidor responde y recibe la petición siguiente de la misma tarea (media de 12, por corrida) | 0,074 · 0,066 · 0,108 | 0,034 · 0,038 · 0,039 |
| Segundos de reloj por tarea (media y mediana de 18) | 11,60 y 10,65 | 10,37 y 9,10 |
| Tiempo que el propio registro mide que le quita al hilo que lo llama, por corrida | 2,05 · 1,45 · 2,64 s | — |

El registro añade entre 0,03 y 0,07 s por petición en esta máquina. Casi todo es la sincronización a disco
del inicio de cada petición: 37 a 71 ms de media por inicio, frente a 0,1 ms del fin, que no se sincroniza.
Medir la entrada cuesta 0,02 a 0,03 ms. Por tarea hay además cuatro eventos sincronizados y un diff.

Con peticiones reales de varios segundos, 0,07 s es menos de un 2 % de una petición de 4 s. **Eso es una
inferencia:** el costo depende del disco, y el de Kaggle no se midió. El evento `cierre` de cada sesión trae
`costo_del_registro_s` y el costo por parte, así que la corrida real lo dirá.

El modelo falso responde en milisegundos, de modo que esta medición no dice nada del tiempo de una tarea
real; solo acota lo que el registro añade.

## El rescate sobre la salida del ensayo

El rescate que mira bytes (#156) se fusionó en `main` con el PR #158 (commit `d8b95f7`) mientras se hacía este
trabajo. La comprobación se corrió dos veces con el mismo resultado: primero desde la rama
`issue-156-rescate-bytes` en el commit `bde8104`, en solo lectura, y después con el guion de `main` ya
fusionado. `scripts/kaggle_rescate.py` es el mismo archivo en los dos (SHA-256
`be2553059cca1723dafb961575537443b9443c6e28bb3b16dced37f12add6117`). La tabla es la de la segunda.

`--sin-red` espera la disposición de una bajada real: `envios.json`, `tabla_publica.zip` y
`notebooks/<slug>/` con `estado.json`, `metadatos.json`, `log.txt` y cada archivo de salida como
`salida__<nombre>`. La salida del ensayo no tiene esa forma, y el guion no se tocó: `rescate_sobre_ensayo.py`
arma esa carpeta por escenario. `envios.json` y `tabla_publica.zip` se copian del rescate real
`2026-10-08T2231Z` solo para que el resumen tenga su tabla; `estado.json` y `metadatos.json` son dobles que
dicen «ensayo local».

| Salida | Código | Miembros revisados | Exigidos de 0 bytes |
|---|---|---|---|
| `completa` | 0 | 135 | 0 |
| Los cinco cortes y el parche global | 0 | — | 0 |
| `control_sin_parche` | **4** | 35 | 6 (`logs/<tarea>.log`) |
| `sin_enganches` (3 corridas) | 4 | 35 | 6 |

## Lo que el ensayo encontró y el concilio no tenía

1. **Una tarea «resuelta» puede haber agotado un tope, y el arnés no lo deja escrito.** En `corte_tiempo` y
   en `corte_llamadas` la tarea cortada quedó con clase `resuelta` y sin error en su fila: el arnés recoge el
   árbol como parche, las pruebas pasan y el motivo del corte se descarta. La clase del notebook sale de ese
   error, así que no lo ve. El evento `agente_fin` lo conserva. En el ensayo esto ocurre porque el modelo
   falso aplica el parche de referencia antes del corte; no se sabe cuántas veces ocurrió en Kaggle.
2. **Con el servidor caído, el arnés pierde el parche y el registro lo conserva.** La tarea terminó como
   `otro_error_sin_parche` con 0 caracteres de parche; el diff al cierre guardó los 6 741 bytes que había en
   el árbol.
3. **Un servidor caído cuesta unos tres minutos antes de que el notebook corte.** litellm reintenta 5 veces
   por dentro y el arnés repite la llamada 5 veces más: 6 peticiones entre las 01:23:57 y las 01:26:48 UTC, y
   la tarea duró 184,5 s. El notebook solo mira la salud del servidor antes de cada tarea.
4. **El tope de llamadas no corta al llegar a 40.** El arnés lo comprueba cuando el modelo cede el turno. Un
   modelo que sigue pidiendo herramientas recibe errores de presupuesto y la sesión continúa: en una prueba
   previa, con un modelo falso que nunca cedía, una tarea llegó a 100 peticiones (su salida no se conservó). En el escenario final el
   modelo cede tras 45 llamadas y la sesión tiene 46 peticiones.

## Lo que el ensayo no puede decir

Lo que sigue no se parece a Kaggle o no se midió.

- **Cinco celdas no corren tal cual:** las guardias de `/kaggle/input`, la instalación de ruedas, la
  comprobación de ruedas, la demostración del grafo y el arranque de vLLM. Un fallo en ellas no lo ve este
  ensayo.
- **El servidor es un doble.** `server_instance` no es un `VllmServer`: no tiene proceso, así que
  `servidor_codigo_de_salida` sale siempre vacío. El log que se copia es el del modelo falso; el de vLLM es
  más grande y no se midió cuánto tarda en copiarse cada 30 s.
- **La GPU es un doble.** No se sabe si `nvidia-smi` acepta en la imagen de Kaggle la consulta que usa el
  latido. Si falla, el latido lo anota en `gpu` y sigue.
- **Qué guarda Kaggle de una sesión que mata.** El ensayo copia `/kaggle/working` después de matar el
  núcleo. No se sabe si Kaggle conserva esos archivos cuando corta una sesión por tiempo.
- **Matar el núcleo no es lo mismo que el corte de Kaggle.** Aquí es una señal al proceso del núcleo.
- **Versiones.** La imagen local trae litellm 1.104.0. Otra versión podría disparar la retrollamada de fallo
  ante una cancelación; el envoltorio no depende de eso.
- **Tareas.** Corrieron 26 de las 60 sorteadas, las que tienen snapshot aquí. Las otras 34 no se ejercitaron.
- **Topes de la corrida real.** No se midió si 60 tareas caben en 7 200 s de tareas y en 150 min de sesión
  con 10 de margen. Con los 99,8 a 113,1 s por tarea-corrida que midió el verificador limpio, 60 tareas son
  de 5 988 a 6 786 s, más 479 a 1 337 s antes de la primera tarea: el margen es estrecho y lo debe mirar el
  concilio antes de subir.
- **Costo del registro en el disco de Kaggle.** No medido.
- **Predicciones fechadas de la iteración 08.** Fuera de este issue: las escribe el concilio.

## Cómo repetirlo

```bash
# 1. Imagen (una vez)
docker build -t aal-ensayo-nucleo:local <instrumentos>/iteracion_08/imagen
# 2. Sorteo, armado, las catorce corridas, rescate y resumen
python -m scripts.kaggle_registro sortear --validez <validez_ensayo.json> --salida <instrumentos>/iteracion_08/sorteo_60.json
sh <instrumentos>/iteracion_08/correr_todo.sh
python <instrumentos>/iteracion_08/rescate_sobre_ensayo.py
python <instrumentos>/iteracion_08/resumen_ensayo.py
```

`correr_todo.sh` vuelve a armar los notebooks, borra `ensayo_salida/` y deja un contenedor efímero por
escenario. Tardó 22 minutos. Al terminar no quedó ningún contenedor.

## Huellas

Todo bajo `experiments/gemma_developer_agent/data/rescate_kaggle/instrumentos/iteracion_08/`, ignorado por
git. `ensayo_salida/HUELLAS.txt` lista los 194 archivos de salida con sus bytes y su SHA-256.

| Archivo | SHA-256 |
|---|---|
| `ensayo_salida/HUELLAS.txt` | `e4befcf1b21ad4dc76b8281a03f6893cf0ccbcba8a7c170c4922a8288cfc6160` |
| `ensayo_salida/RESUMEN.json` | `3babe9e9c2a7157a6f319df58fe43d9b6c4f3cc5613f28b5b4170ab10d2cdc85` |
| `ensayo_salida/rescate_sobre_ensayo.json` | `d248aae65492e53079597ac0837b565c26574bffe1ea0ff6b00569ffcda91938` |
| `ensayo_salida/completa/informe.json` | `0389bb61fced327718aa98ef848a1753ce5912285828660928e3e7a98d3f5f2c` |
| `ensayo_salida/completa/working/crudo_iteracion_08_p1_A8P1.zip` | `77c566f21224458666a6c8861ee153be71055e9406500cee1dcfbab7fad8e381` |
| `ensayo_salida/control_sin_parche/informe.json` | `f47b4426822833d75b66df2f521fe104189f821e1c5d557b5f895566225ddeea` |
| `ensayo_salida/control_sin_parche/working/crudo_iteracion_08_p1_A8P1.zip` | `2447c98b7500e72639d771ac0254703b23bf10bd20e1fb8dc20993729b783b9d` |
| `ensayo_salida/corte_tiempo/informe.json` | `d128ea0906506c439d5c942a6c45e962cfe2a6e5eff35546ca12eb52f24ddfcc` |
| `ensayo_salida/corte_llamadas/informe.json` | `e50703508ca88f3af7f45bb65b038795fc67352d7a8857ce47ebe810e1f20482` |
| `ensayo_salida/corte_sesion/informe.json` | `4f209ec12d1fa18e13309e8df4423e77bebb2294109afde003cf0da1e043325d` |
| `ensayo_salida/corte_sesion_duro/informe.json` | `3cf2e4994cdeb03676db8c1222170b43a3bdbb7735f8b6ed416265e0f53b2459` |
| `ensayo_salida/servidor_caido/informe.json` | `c5797f4344e9fd0d4a89a31819d7eaf610106dc7a763cc87a446cd19ea1f5bdf` |
| `armado.json` | `ec5ef7f57d522e008bd4cf427cd695e1bf7f49d934dca5b1cd4c9d35e7fae200` |
| `armar.py` | `9f129e862978ea2b967c0ff2c2390ad715b7cfba791ce2c4e2f9622b9b1a0147` |
| `ensayo_nucleo.py` | `33991389c7fa52bb324edcd50d619dabe7324c61bc54e5ba762a0c9a8a439dc2` |
| `sorteo_60.json` | `0a2d9eb3e2aa5f7e03a3e9e4acac1ff963f21f66058a497a10b1aff0e86c61a6` |
| `imagen/Dockerfile` | `8243082780996d9fe83295046ad7181d26d35ca097fde2e45f9dbaf70dc599c8` |

Las catorce corridas usaron la misma versión de `ensayo_nucleo.py` (cada `informe.json` trae su SHA-256). Una
batería anterior del mismo día, con un fallo en la validación del propio ensayo (exigía logs con contenido en
las corridas sin enganches), se descartó entera y no está en disco.
