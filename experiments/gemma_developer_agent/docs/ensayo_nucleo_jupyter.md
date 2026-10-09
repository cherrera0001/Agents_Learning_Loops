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
| Los enganches de registro y las guardias, que el notebook lleva como una celda | [`scripts/kaggle_registro_enganches.py`](../../../scripts/kaggle_registro_enganches.py) | Sí, con `tests/test_kaggle_registro_enganches.py` |
| El sorteo de tareas y el lector del registro | [`scripts/kaggle_registro.py`](../../../scripts/kaggle_registro.py) | Sí, con `tests/test_kaggle_registro.py` |
| `armar.py`, el ensayo, el modelo falso, el Dockerfile y los notebooks armados | `experiments/gemma_developer_agent/data/rescate_kaggle/instrumentos/iteracion_08/` | No: `data/` está ignorada por git |
| Las salidas del ensayo | `…/iteracion_08/ensayo_salida/` | No; se citan por ruta y SHA-256 ([huellas](#huellas)) |

**Consecuencia:** el código de las guardias está versionado, pero las líneas del notebook que las llaman
las escribe `armar.py`, que no lo está. De esas líneas el repositorio solo tiene los SHA-256 que este
documento cita para `armar.py` y para los dos notebooks.

## El notebook de la iteración 08

`armar.py` lo arma a partir del de la iteración 07 y se detiene si algo no cuadra. Arma dos notebooks, uno
por pasada, porque 120 tareas no caben en una sesión de 9 000 s.

| Qué cambia respecto de la 07 | Celda | Líneas (quitadas, añadidas) |
|---|---|---|
| Condición `A` y un solo grupo, `sorteo_60`, con las 60 tareas sorteadas | 4 | 2, 2 |
| Celda nueva: el texto de `kaggle_registro_enganches.py`, byte a byte, la línea que instala el registro y la guardia previa (17 líneas) | 8 | celda nueva |
| Plan de una pasada (`A8P1` o `A8P2`), nombres de salida `iteracion_08_p1` o `_p2`, tope de sesión de 150 min con 10 de margen, las llamadas al registro, la guardia tras la primera tarea (2 líneas) y el reempaquetado del zip si la celda falla (1 línea) | 10 (antes 9) | 5, 23 |
| Cierre del registro y nuevo empaquetado antes de detener el servidor | 11 (antes 10) | 0, 8 |

Las celdas 0, 1, 2, 3, 5, 6, 7 y 9 son las de la 07, byte a byte (la 9 es su antigua 8).

- **Condición.** El zip `submission_a_ajustado.zip` tiene el SHA-256
  `d8a3e1d3558f03b72b3f86037ff53b462a8f66566e1bb7907240bcb0ce4d7182`. `armar.py` comprueba que sus seis
  archivos son, byte a byte, los de la carpeta `envios/a_kit_ajustado` y los de la condición A del notebook
  de la iteración 04, y que su `eval_config.yaml` dice 4 minutos y 40 llamadas.
- **Dos pasadas.** La pasada 2 es la pasada 1 con `A8P1` → `A8P2` e `iteracion_08_p1` → `iteracion_08_p2`:
  cambia una línea en la celda 8 y tres en la 10, y nada más. `armar.py` lo comprueba, y el notebook de la
  pasada 2 se ejecutó bajo el núcleo ([escenario `pasada_2`](#resultado-por-escenario)).
- **Topes.** No se cambian los del agente ni los de la condición. El tope de sesión vuelve a los 150 min y 10
  de margen de las iteraciones 03, 04 y 06 (la 07 los había recortado a 60 y 5 por la cuota que quedaba). El
  tope del conjunto de tareas sigue en `TOPE_SEGUNDOS = 7200`, que vence antes que los 150 min: ver
  [lo que queda sin medir](#lo-que-el-ensayo-no-puede-decir).

Notebooks armados, de 91 527 bytes cada uno:

| Archivo | SHA-256 |
|---|---|
| `kernel_iteracion_08_p1/iteracion.ipynb` | `62c07ff6d1779062087e1a32dcdb8981645e4cf588175ab0cf68d97560f5afae` |
| `kernel_iteracion_08_p2/iteracion.ipynb` | `0be9615e88b6c9eeb7344ae84b79854138012c6a79c8fabba1401e6ca7419831` |
| `armar.py` | `7fefc5d9d9c4381f15923844f0aaa72870081c75f37e3a1cdb4488aec0ee738b` |

El texto de los enganches que llevan tiene el SHA-256
`d2333a3de07329450411cd04dfe3ee64e9de1905403cfa5152853740f6dd454c`, el de
`scripts/kaggle_registro_enganches.py` en el commit `20b6136`. Si ese archivo cambia, los notebooks se vuelven
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
| `comprobar_primera_tarea` | Celda 10, tras la primera tarea, con su zip ya guardado | Si su `logs/<tarea>.log` no existe o pesa 0 bytes; si el registro no tiene ninguna petición respondida; o si la tarea no dejó su `agente_fin` o su `diff_cierre` |

La segunda existe porque un enganche puede decir «instalado» y no surtir efecto: el arnés podría crear la
consola, llamar al modelo o destruir el sandbox por otra ruta. Las dos se ensayaron bajo el núcleo, la
segunda de dos maneras ([resultado](#resultado-por-escenario)).

Cuando la segunda guardia detiene el notebook, la celda cierra el registro y **vuelve a empaquetar el zip**,
de modo que el zip lleva el evento `guardia`, el `corte` y el `cierre`: leído solo desde el zip, el
diagnóstico da lo mismo que con los archivos sueltos (4). Ensayado en `guardia_log` y `guardia_diff`.

Límites de las guardias:

- Los enganches `log del servidor` y `latido` nunca pueden quedar en `FALLO` (con un `log_path` vacío el
  primero dice «origen None» y cuenta como instalado), así que la guardia previa no los cubre. Si el log del
  servidor no se copia, se ve en el latido (`servidor_log_bytes` vacío) y en que el zip no lo trae.
- No está comprobado que Kaggle detenga «Run All» en la primera excepción. Si no lo hiciera, la guardia
  previa no ahorraría cuota; la segunda sí, porque la celda de tareas ya terminó cuando lanza.

### Cómo se lee el registro

```bash
python -m scripts.kaggle_registro diagnosticar --salida <carpeta o zip de salida de una sesión>
python -m scripts.kaggle_registro comprobar --rescate <carpeta de un rescate> --notebook <pasada 1> --notebook <pasada 2>
```

`diagnosticar` dice si el registro es de fiar, si la sesión se cerró o murió desde fuera, qué tope cortó cada
tarea, qué petición quedó en vuelo o cortada y qué diff quedó. Agrupa por corrida de tarea, no por nombre: si
una tarea se repite, cada corrida conserva lo suyo. Distingue:

- **petición en vuelo:** un inicio sin fin de ningún tipo. Solo queda si la sesión murió durante la llamada;
- **petición cortada:** la última petición de la tarea, si no llegó a responderse (`cancelada`, `error` o sin
  fin). Un error transitorio seguido de peticiones respondidas no es ni lo uno ni lo otro.

**`diagnosticar` solo mira el registro.** Sobre una corrida con los logs por tarea vacíos
(`control_sin_parche`) sale con 0, porque el registro está sano. Quien quiera juzgar una corrida usa
`comprobar`, no `diagnosticar` suelto.

| Código | Qué significa |
|---|---|
| 0 | Registro fiable y sesión completa (en `sortear`: lista reproducida). No significa «todas las tareas completas» |
| 1 | Solo `sortear`: la lista sorteada difiere de la guardada |
| 2 | Entrada inválida o ilegible: archivo ausente, JSON roto, acta o validez sin sus campos, un evento del registro con un campo de otro tipo; en `comprobar`, además, no haber nombrado ninguna pasada |
| 3 | Sesión cortada por el notebook; la causa está en el registro |
| 4 | Registro no fiable: un enganche exigido no se instaló; hubo errores propios; hay tareas corridas y **en toda la sesión** no hay ninguna petición respondida; una tarea terminada no trae su `agente_fin` o su `diff_cierre`; falta `registro_instalado`; o una guardia detuvo el notebook. En `comprobar`, además, una pasada esperada sin carpeta en el rescate o sin registro |
| 5 | Sesión muerta desde fuera: el registro no termina en `cierre` |

**Precedencia en `diagnosticar`:** 4 gana a 3, y 3 gana a 5. Un registro no fiable se dice aunque la sesión
esté cortada o muerta; un corte anotado por el notebook se dice aunque falte el cierre.

La comprobación de peticiones respondidas es de toda la sesión, no por tarea: una sesión con una tarea
resuelta y otra cuyas peticiones terminaron todas en error sale con 0, y la segunda tarea lo dice en su
ficha (`no_respondidas`, `peticion_cortada`). Cuando el 4 sale por esto, el mensaje nombra las dos lecturas
posibles: o el enganche de peticiones no surte efecto, o el servidor nunca respondió, con las peticiones
iniciadas y las que terminaron en error.

Una sesión que una guardia detuvo no se llama «completa»: su veredicto termina en «sesión detenida por una
guardia», antes o tras la primera tarea.

**El 0 es de la sesión, no de cada tarea.** Una tarea cortada por tiempo o por llamadas no cambia el código:
el notebook siguió y la sesión terminó. Su motivo está en `agente_fin` y en `tope_que_corto` de su ficha.

**Una sesión colgada sale con 5.** Si el notebook queda vivo y detenido, su registro tampoco termina en
`cierre` y el veredicto dice «muerta desde fuera». El diagnóstico no distingue las dos cosas; se ve en el
latido, que sigue llegando con la misma tarea en curso y ninguna petición en vuelo durante minutos.

**La regla de `agente_fin` y `diff_cierre` puede dar un 4 que no es del registro.** Inferido por la revisión
leyendo el arnés local, no ejecutado: si falta el snapshot de una tarea, el arnés devuelve sin llamar a
`_run_agent_sandbox`, así que esa tarea no deja ninguno de los dos y la sesión sale con 4; si es la primera
tarea, la guardia detiene el notebook. Un `diff_cierre` con error da el mismo 4. Falla hacia el lado seguro.
Se distingue en la ficha de la tarea: sin snapshot no tiene ninguna petición y su fila trae el error
«Snapshot file not found»; con un enganche sin efecto la tarea sí tiene peticiones respondidas.

**`comprobar`** corre `kaggle_rescate --sin-red` y después `diagnosticar` sobre los archivos
`salida__registro_*` de cada **pasada esperada**, que se nombra con `--notebook`, una vez por pasada.

- Para cada pasada nombrada, es un hallazgo que falte su carpeta en el rescate (4), que falte su registro
  (4) o que su diagnóstico no dé 0. El JSON dice cuál y por qué, y lista las salidas que sí trae.
- **Sin ninguna pasada nombrada la orden nunca sale con 0:** no puede afirmar que la corrida está completa
  sin saber cuántas pasadas se esperaban. Imprime lo que encontró y sale con 2, o con el código del rescate
  si no es 0.
- Imprime siempre lo que dio el rescate.
- Los notebooks del rescate que no se nombraron solo se listan. Si alguno no trae registro y sí trae
  archivos que solo deja un notebook con registro (`salida__latido_*`, `salida__servidor_log_*`,
  `salida__diff_en_curso_*`, o una salida con `iteracion_08` en el nombre), lleva un aviso que no cambia el
  código. La defensa es nombrar las pasadas, no esa lista de nombres.
- **Precedencia:** el código del rescate, si no es 0; si lo es, el de la primera pasada nombrada, en el
  orden en que se nombraron, cuyo código no sea 0. Un registro ilegible en una pasada no impide
  diagnosticar las demás.
- En Windows, si la salida se redirige a un archivo sin `PYTHONIOENCODING=utf-8`, no sale en UTF-8.

Por qué hace falta nombrarlas: una pasada puede morir antes de instalar el registro. La celda 7 escribe
`servidor_error_*.txt` cuando el servidor no arranca y el registro nace en la celda 8, así que esa pasada no
deja ningún archivo del registro, ni siquiera un nombre por el que reconocerla.

## Tras una corrida real

El rescate solo mira bytes. Sobre una sesión muerta desde fuera sale con 0, porque el zip se empaquetó tras
la tarea anterior y está sano; sobre un notebook que la guardia previa detuvo también, porque no hay zip. Por
eso el rescate solo no basta:

1. Bajar con `python -m scripts.kaggle_rescate --destino <carpeta>` y anotar el código y la hora.
2. Correr, con las dos pasadas nombradas,
   `python -m scripts.kaggle_registro comprobar --rescate <carpeta fechada> --notebook iteracion-08-p1 --notebook iteracion-08-p2`.
   Distinto de 0 es un hallazgo; el JSON dice si es del rescate o de una pasada, y de cuál.
3. Si el diagnóstico dice 5 (muerta desde fuera), el zip no trae el cierre ni la tarea cortada. Lo que hay
   que mirar son los archivos sueltos de la salida, que el notebook escribe fuera del zip:
   `registro_<nombre>.jsonl` (el inicio sin fin), `latido_<nombre>.jsonl` (el último latido, con la petición
   en vuelo y el estado del servidor), `diff_en_curso_<nombre>.diff` (el árbol en ese latido) y
   `servidor_log_<nombre>.txt`.
4. Si dice 4, leer `problemas_del_registro`: la corrida no es válida como registro aunque tenga resultados.

En una sesión muerta el zip va atrasado respecto de los archivos sueltos: se empaqueta tras cada tarea,
así que no trae la petición en vuelo ni el último `diff_en_curso`.

No está comprobado que Kaggle conserve los archivos sueltos de `/kaggle/working` cuando mata una sesión. El
latido del notebook real es cada 30 s: la ventana para ver por el latido una petición en vuelo, o el árbol de
la tarea, es de hasta 30 s.

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
| 7 | Doble: no hay GPU. Deja `server_instance` con `base_url`, `log_path` y un `stop()` que borra el log, como el servidor real. En los tres escenarios de guardia lleva además el sabotaje |

De las 60 tareas sorteadas, 26 tienen snapshot en esta máquina. La corrida completa usa esas 26; las demás,
las 6, las 5 o las 3 primeras.

**Modelo falso.** Vive fuera del núcleo. En cada tarea aplica el parche de referencia y entrega, salvo en la
tarea que fuerza el corte. Escribe un log propio, que hace de log del servidor. `nvidia-smi` es un doble que
inventa cuatro GPU.

**El ensayo late cada 2 s** (`LATIDO_SEGUNDOS=2`) y el notebook real cada 30 s. Ninguna cifra de latidos de
este documento vale para la corrida real.

### Resultado por escenario

Dieciocho corridas válidas, cada una en un contenedor efímero, entre las 03:28 y las 04:08 UTC del
2026-10-09, todas con la misma versión del ensayo y del notebook. Las dieciocho pasan su validación, que
incluye el código que debe dar `diagnosticar`. Hubo además una decimonovena que se colgó y se repitió: ver
[el cuelgue](#una-corrida-con-el-parche-global-se-colgó).

Orden: `completa` sola; después once escenarios en paralelo (inicios entre las 03:39:32 y las 03:39:35); al
final, solas y una tras otra, las seis corridas con y sin enganches. **Los relojes por tarea de los
escenarios en paralelo no son comparables con los de `completa`** ni entre baterías.

«Rescate» es el código de `kaggle_rescate --sin-red` sobre esa salida; «Comprobar», el de la orden que junta
rescate y diagnóstico, con ese notebook nombrado como pasada esperada.

| Escenario | Notebook | Tareas | Qué se fuerza | Cómo termina el notebook | Logs por tarea de 0 bytes | Diagnóstico | Rescate | Comprobar |
|---|---|---|---|---|---|---|---|---|
| `completa` | pasada 1 | 26 | Nada | Completo | 0 de 26 | 0 | 0 | 0 |
| `pasada_2` | **pasada 2** | 3 | Nada | Completo | 0 de 3 | 0 | 0 | 0 |
| `control_sin_parche` | sin el parche de rich | 6 | Nada | Completo | **6 de 6** | 0 | **4** | 4 |
| `parche_global` (repetida) | con el parche global | 6 | Nada | Completo | 0 de 6 | 0 | 0 | 0 |
| `con_enganches` (3 corridas) | pasada 1 | 6 | Nada | Completo | 0 de 6 | 0 | 0 | 0 |
| `sin_enganches` (3 corridas) | registro inactivo | 6 | Nada | Completo | 6 de 6 | no hay registro | 4 | 4 |
| `corte_tiempo` | pasada 1 | 3 | El modelo retiene una petición más de 4 min | Completo: la sesión sigue | 0 de 3 | 0 | 0 | 0 |
| `corte_llamadas` | pasada 1 | 3 | El modelo no entrega y pasa de 40 llamadas | Completo: la sesión sigue | 0 de 3 | 0 | 0 | 0 |
| `corte_sesion` | pasada 1 | 5 | `TOPE_SESION_SEGUNDOS=45` | `cortado_por: sesion`, 1 tarea corrida | 0 de 1 | 3 | 0 | 3 |
| `corte_sesion_duro` | pasada 1 | 3 | El ensayo mata el núcleo con una petición en vuelo | No llega a escribir `cortado_por` | 0 de 1 | **5** | 0 | 5 |
| `servidor_caido` | pasada 1 | 3 | El servidor cierra la conexión y deja de escuchar | `cortado_por: servidor`, 2 tareas corridas | 0 de 2 | 3 | 0 | 3 |
| `guardia_enganche` | pasada 1 | 3 | El doble de la celda 7 borra `agent_runner.Console` | Se detiene en la celda 8, sin correr ninguna tarea | sin zip | **4** | 0 | 4 |
| `guardia_log` | pasada 1 | 3 | El doble de la celda 7 hace que toda consola con archivo se crea en Jupyter | Se detiene tras la primera tarea: `cortado_por: fallo RuntimeError` | 1 de 1 | **4** | 4 | 4 |
| `guardia_diff` | pasada 1 | 3 | El doble de la celda 7 deja al arnés usando un `sandbox_stop` sin envolver | Se detiene tras la primera tarea: `cortado_por: fallo RuntimeError` | 0 de 1 | **4** | 0 | 4 |

Cada variante de notebook difiere de la pasada 1 en una sola línea, la que instala el registro; `armar.py` lo
comprueba.

**Sesión sin corte (`completa`).** 78 peticiones iniciadas y 78 con su fin: 52 con motivo `tool_calls` y 26 con
`stop`. El registro cuenta las mismas 78 que recibió el servidor falso. Las 26 tareas tienen su fila de fin, su
motivo de fin del agente y su diff al cierre. El zip tiene 135 miembros, ninguno de 0 bytes, con el registro
en tres archivos: eventos, latido y log del servidor. El log original del servidor ya no existía al terminar:
el doble lo borró al detenerse, así que la copia es anterior.

**La pasada 2 (`pasada_2`).** El notebook de la segunda pasada corrió 3 tareas y dejó solo archivos con su
nombre: `crudo_iteracion_08_p2_A8P2.zip`, `iteracion_08_p2.json`, `registro_iteracion_08_p2.jsonl`,
`latido_iteracion_08_p2.jsonl`, `servidor_log_iteracion_08_p2.txt` y `diff_en_curso_iteracion_08_p2.diff`.
Ningún nombre de la pasada 1 aparece en la salida ni dentro del zip, y los eventos llevan la etiqueta `A8P2`.

**Las guardias.**

- `guardia_enganche`: el enganche de los logs falló con `AttributeError` y el notebook se detuvo en la celda 8
  con «GUARDIA registro: no quedó instalado logs por tarea (rich)». El servidor falso no recibió ninguna
  petición y no hay JSON de resultados ni zip. Quedaron el registro (con el evento `guardia` y su `cierre`), el
  latido y la copia del log del servidor; el servidor quedó detenido.
- `guardia_log`: el enganche dijo «modo archivo» (instalado), la primera tarea dejó `logs/rich_3470.log` en 0
  bytes y el notebook se detuvo con «GUARDIA registro: el log por tarea rich_3470.log pesa 0 bytes». Corrió una
  tarea de tres.
- `guardia_diff`: todos los enganches dijeron «instalado». El sabotaje deja a `run_agent_sandbox` con una
  copia de sus nombres globales, así que el enganche envuelve un `sandbox_stop` que el arnés ya no usa. La
  primera tarea dejó su log con contenido y su `agente_fin`, pero no su `diff_cierre`, y el notebook se
  detuvo con «GUARDIA registro: la primera tarea no dejó su diff_cierre (diff del árbol al cierre)». Es el
  único problema que la guardia anotó: la detiene esa comprobación y no otra.

En las dos últimas el zip se volvió a empaquetar después de la guardia y, leído solo, da diagnóstico 4.

### `comprobar` con las pasadas nombradas

Sin repetir el ensayo, sobre salidas ya guardadas (`comprobar_pasadas.py`, código del commit `f5c1e62`). La
pasada 1 es siempre la salida de `completa`. La pasada 2 es la salida de `pasada_2`, que lleva los nombres
de la segunda pasada, o lo que dice cada fila. Las cuatro filas en negrita son los casos de la tercera
revisión, que antes salían con 0.

| Pasada 2 | Con las dos nombradas | Sin nombrar ninguna |
|---|---|---|
| La salida de `pasada_2`, con su registro | 0 | 2 |
| **Solo `estado.json`, `metadatos.json` y `log.txt`** | 4 | 2 |
| **Además, `salida__servidor_error_salida.txt`** | 4 | 2 |
| **La carpeta vacía** | 4 | 2 |
| **Sin carpeta** | 4 | 2 |
| La salida de `corte_sesion_duro` (muerta desde fuera) | 5 | 2 |
| La salida de `guardia_diff` (detenida por la guardia) | 4 | 2 |
| La salida de `control_sin_parche` (logs por tarea vacíos) | 4, por el rescate | 4, por el rescate |

### Una corrida con el parche global se colgó

En la batería final, la primera corrida de `parche_global` se quedó parada en su tercera tarea
(`rich_4079`) desde las 03:41:16 UTC. A las 03:57 seguía igual: el log por tarea creado y en 0 bytes, ninguna
petición al modelo, ningún subproceso vivo dentro del contenedor, el núcleo dormido y el latido escribiendo
(492 latidos, el último con la tarea `rich_4079` y ninguna petición en vuelo). Se copió `/kaggle/working` a
`ensayo_salida/parche_global_colgado/` y se mató el contenedor (código 137). Sobre esa copia `diagnosticar`
da 5.

**La causa no está diagnosticada.** No se pudo sacar la pila del núcleo: el contenedor no permite `ptrace`.
No se sabe si es del modo global de rich, de la carga (corrían once contenedores a la vez) o del arnés. Lo
medido es: una corrida colgada de cinco con el modo global a lo largo del día, y ninguna de las corridas con
el modo `archivo` o sin parche. La corrida se repitió una vez, sola, a las 04:06 UTC, y terminó bien; las
cifras del modo global de este documento son de esa repetición.

**Nada en el notebook corta una tarea colgada sin peticiones.** `run_sync` espera sin tope a que la tarea
termine, el tope de 4 minutos del arnés empieza con el bucle del agente y los topes de sesión solo se miran
entre tareas. El latido es lo único que lo deja visible. Queda como límite conocido y como decisión del
concilio antes de subir; aquí no se cambió.

## Los cuatro cortes

Lo que sigue sale de `diagnostico.json` de cada escenario, que el ensayo calcula solo con los archivos de
`/kaggle/working`. La consola del núcleo no se usa para validar.

| Corte | Qué dice la salida que cortó | Petición en vuelo o cortada | Diff del árbol |
|---|---|---|---|
| Tope de tiempo de la tarea | `agente_fin`: «Agent exceeded session timeout (4.0 min)» | Cortada: la 5, inicio a las 03:41:03.458 UTC, 19 145 caracteres de entrada en 4 mensajes, fin `cancelada` (`CancelledError`) a los 240,0 s. No figura en vuelo, porque tiene fin | Al cierre: 6 741 bytes, 2 archivos |
| Tope de llamadas | `agente_fin`: «Agent exceeded tool call budget (40 calls)», 40 llamadas usadas | **Ninguna**: el arnés corta entre dos peticiones. Queda la última: la 49, de 29 531 caracteres, con fin `stop` | Al cierre: 6 741 bytes, 2 archivos |
| Tope de sesión, cortado por el notebook | Evento `corte` con `sesion`, y `cortado_por: sesion` en el JSON | **Ninguna**: el notebook corta antes de empezar una tarea. Las 3 peticiones tienen su fin | Al cierre de la tarea corrida: 440 bytes |
| Tope de sesión, sesión muerta desde fuera | El registro no termina en `cierre`; el último latido es de los 98,0 s de sesión | En vuelo: la 5, inicio a las 03:41:03.461 UTC, 19 145 caracteres, **sin fin**. El último latido la trae con 6,3 s en vuelo | No hay diff al cierre. Queda el del último latido: 6 741 bytes |
| Servidor caído | Evento `corte` con `servidor` y `servidor_caido_A8P1_3.txt`; `agente_fin`: «…Connection error. LiteLLM Retried: 5 times» | Cortada: la 10. Las peticiones 5 a 10 terminan las seis en `error` (`InternalServerError`), de 12,3 a 13,8 s cada una; la primera a las 03:41:04 UTC, 19 145 caracteres | Al cierre: 6 741 bytes, 2 archivos |

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
mismas 6 tareas. Las salidas ricas de la celda se miden de dos maneras, y dan cifras distintas: «en bruto»
es la suma de sus textos; «serializadas» es su tamaño como JSON escapado, que es como las guarda un `.ipynb`.

| Modo | Logs por tarea | Texto de la celda de tareas | Salidas ricas, en bruto | Salidas ricas, serializadas |
|---|---|---|---|---|
| Sin parche (control) | 0 bytes | 1 367 bytes | 6 (75 969 bytes) | 101 835 bytes |
| `archivo`: `force_jupyter=False` solo en la consola del log | 721 a 722 bytes | 1 363 a 1 365 bytes | 6 (75 967 bytes en la primera corrida) | 101 825 a 101 840 bytes |
| `global`: la línea del issue | 715 a 716 bytes | **109 810 bytes** | 0 | 0 |

Las dos devuelven los logs. La línea global cambia además la consola con la que el arnés pinta en el
notebook: deja de usar las salidas ricas de Jupyter y vuelca cada repintado del panel al texto de la celda.

| Qué se compara, global contra control | Razón |
|---|---|
| Solo el texto de la celda (109 810 contra 1 367 bytes) | 80 veces |
| Texto más salidas ricas en bruto (109 810 contra 77 336) | 1,42 veces |
| Texto más salidas ricas serializadas (109 810 contra 103 202) | 1,06 veces |

El texto del modo global varió entre corridas del mismo día: 131 447, 139 778 y 109 810 bytes. Con las cifras
de la batería anterior (139 778), el analista de datos obtuvo 1,35 veces con las salidas serializadas y 1,81
con las salidas en bruto.

**El notebook armado usa el modo `archivo`**, que deja la salida de la celda como estaba. Es una desviación de
la letra del issue. La sostienen dos cosas medidas: el modo global cambia lo que el notebook manda a su
salida, y la única corrida que se colgó en todo el día fue con el modo global, aunque sin causa diagnosticada.
`armar.py` tiene la constante `PARCHE_RICH` para cambiarla.

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

Seis corridas de las mismas 6 tareas (18 peticiones cada una), tres con enganches (A) y tres sin ellos (B),
solas y una tras otra en orden ABBAAB, entre las 03:57 y las 04:06 UTC. Son las únicas corridas secuenciales
de la batería además de `completa`. La carga de la máquina virtual de Docker al empezar cada una fue parecida
(`/proc/loadavg` de 1,04 a 1,26). No se controló la carga del sistema anfitrión.

| Medida | Con enganches | Sin enganches |
|---|---|---|
| Segundos entre que el servidor responde y recibe la petición siguiente de la misma tarea (media de 12, por corrida) | 0,081 · 0,086 · 0,103 | 0,042 · 0,040 · 0,044 |
| Segundos de reloj por tarea (media y mediana de 18) | 11,59 y 10,85 | 11,44 y 10,55 |
| Tiempo que el propio registro mide que le quita al hilo que lo llama, por corrida | 1,76 · 2,38 · 2,12 s | — |

El registro añade entre 0,04 y 0,06 s por petición en esta máquina. Casi todo es la sincronización a disco
del inicio de cada petición: 44 a 68 ms de media por inicio en estas tres corridas (55 ms en `completa`),
frente a 0,1 ms del fin, que no se sincroniza. Por tarea hay además cuatro eventos sincronizados y un diff.
En segundos de reloj por tarea la diferencia no se distingue del ruido.

**La sincronización del inicio no dio la misma cifra en todas las baterías del día.** Por inicio de petición,
con la medida del propio registro: de 37 a 71 ms en la primera batería, de 47 a 86 en la segunda y de 44 a
68 en esta. El analista de datos, con su propia cuenta, obtuvo de 16 a 36 ms por petición sobre la batería
que revisó. No se sabe si la diferencia es carga de la máquina, código o manera de contar: **no está
medido**. Entre baterías cambió el código de los enganches (las guardias, y un contador de eventos); la
escritura del inicio no cambió.

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
| `guardia_diff` | **0** | Al zip le falta `diffs_cierre/`, que el rescate no exige. Lo ve `diagnosticar` (4) |
| `servidor_caido` | 0 | La tarea caída deja su parche y su salida de pruebas en 0 bytes, que el rescate solo cuenta. Lo ve `diagnosticar` (3) |

En las corridas sin enganches no hay registro que diagnosticar: `comprobar` imprime el resultado del rescate
y sale con su 4.

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
   por dentro y el arnés repite la llamada 5 veces más: 6 peticiones entre las 03:41:04 y las 03:43:55 UTC, y
   la tarea duró 186,0 s. El notebook solo mira la salud del servidor antes de cada tarea.
4. **El tope de llamadas no corta al llegar a 40.** El arnés lo comprueba cuando el modelo cede el turno. Un
   modelo que sigue pidiendo herramientas recibe errores de presupuesto y la sesión continúa: en una prueba
   previa, con un modelo falso que nunca cedía, una tarea llegó a 100 peticiones (su salida no se conservó).
   En el escenario final el modelo cede tras 45 llamadas y la sesión tiene 46 peticiones.
5. **Una tarea puede colgarse sin que nada la corte** ([el cuelgue](#una-corrida-con-el-parche-global-se-colgó)).

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
- **No se ensayó la cadencia real.** El ensayo late cada 2 s y su escenario de tope de sesión usa 45 s; el
  notebook real late cada 30 s y su tope de sesión es de 150 min.
- **Una tarea colgada sin peticiones no la corta nada**
  ([el cuelgue](#una-corrida-con-el-parche-global-se-colgó)).
- **Qué hace Kaggle.** No está comprobado que detenga «Run All» en la primera excepción, ni que conserve los
  archivos sueltos de `/kaggle/working` de una sesión que mata.
- **Matar el núcleo no es lo mismo que el corte de Kaggle.** Aquí es una señal al proceso del núcleo.
- **El cuelgue de una corrida** no tiene causa diagnosticada.
- **Versiones.** La imagen local trae litellm 1.104.0. Otra versión podría disparar la retrollamada de fallo
  ante una cancelación; el envoltorio no depende de eso.
- **Costo del registro en el disco de Kaggle.** No medido. Tampoco por qué la sincronización del inicio
  cambió entre baterías.

**De las pruebas versionadas.**

- La cobertura que exige el CI se mide sobre `src/associative_agent_loop` y **no mide los dos archivos
  nuevos** de `scripts/`.
- Las funciones internas de `instalar_registro` que importan el arnés (`cliente`, `retrollamadas`, `sandbox`,
  `evaluador`, `rich`) se prueban en los tests con módulos falsos. Contra el arnés real solo las ejercita el
  ensayo, que no corre en el CI.
- Las líneas del notebook que llaman a las guardias las escribe `armar.py`, sin versionar.
- Sobre el commit `f5c1e62`, con el árbol limpio, se inyectaron 60 defectos, uno a uno, en los dos guiones:
  los 13 que la primera revisión dijo que sobrevivían, los de la segunda y la tercera, y los demás sobre el
  código de las tres rondas de correcciones (19 sobre la lógica de pasadas esperadas, incluido quitar cada
  patrón de `SENALES_DE_PASADA`). Las pruebas detectan 59 (`defectos_inyectados.json`). El que sobrevive es
  equivalente: «una pasada nombrada dos veces se cuenta dos veces» no cambia nada, porque las pasadas se
  guardan en un diccionario por nombre y el duplicado se pierde igual. Los commits posteriores solo cambian
  este documento y el episodio. Es una lista elegida a mano, no una búsqueda exhaustiva.

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
# 2. Sorteo, armado, las corridas, rescate y resumen
python -m scripts.kaggle_registro sortear --validez <validez_ensayo.json> --salida <instrumentos>/iteracion_08/sorteo_60.json
sh <instrumentos>/iteracion_08/correr_todo.sh
python <instrumentos>/iteracion_08/rescate_sobre_ensayo.py
python <instrumentos>/iteracion_08/resumen_ensayo.py
# 3. Defectos inyectados en los dos guiones versionados (los restaura siempre; anota el commit)
python <instrumentos>/iteracion_08/defectos_inyectados.py <árbol del repositorio>
```

`correr_todo.sh` vuelve a armar los notebooks, borra `ensayo_salida/` y deja un contenedor efímero por
escenario. Al terminar no quedó ningún contenedor.

## Huellas

Todo bajo `experiments/gemma_developer_agent/data/rescate_kaggle/instrumentos/iteracion_08/`, ignorado por
git. `ensayo_salida/HUELLAS.txt` lista los 294 archivos de salida con sus bytes y su SHA-256, incluida la
copia de la corrida colgada.

| Archivo | SHA-256 |
|---|---|
| `ensayo_salida/HUELLAS.txt` | `a6a10b3908f5786afb392fe89e18112a041c0604cfed87988dc22cac27b2ef0d` |
| `ensayo_salida/RESUMEN.json` | `ff7679894e05d3112c15a2eca5ed0fb578ce8c8c45234ec7fe88043e77d53030` |
| `ensayo_salida/rescate_sobre_ensayo.json` | `9a2f544e6ff7633764df2c29959d8236b5c915feb6392ba46af48b52973c6d9e` |
| `ensayo_salida/comprobar_pasadas.json` | `0a003cb1e60b9d69f3219f3d88f94c004d294480f57d71486f36a8e41d3f87e4` |
| `ensayo_salida/completa/informe.json` | `8706790a8e3dcc58641c3e681724bc2af9070b627a824b1798b0db42b367a468` |
| `ensayo_salida/completa/working/crudo_iteracion_08_p1_A8P1.zip` | `dbd59df23fbb0ca6ec9473d79410221f2759b47cab2cc1bcaf3cc6a64502e24f` |
| `ensayo_salida/pasada_2/informe.json` | `6db6f0ba2588d3ff66a79e666804055238360ed4911c49e95bf93f8533fe9856` |
| `ensayo_salida/control_sin_parche/informe.json` | `11bde083d59398d729d48a7a088c176fa64710dd16253be48daf527eee275a78` |
| `ensayo_salida/control_sin_parche/working/crudo_iteracion_08_p1_A8P1.zip` | `10b551cfaa9873cad7e630fc50389fc179d759f01efa7ce989a42b539cba85da` |
| `ensayo_salida/parche_global/informe.json` | `2f892dd1da384f4c807977fe28dfeed701a265183385447e7cbb517dd867906b` |
| `ensayo_salida/parche_global_colgado/working/registro_iteracion_08_p1.jsonl` | `27295dd7c9a059b7118999c36decd564e05ffb2e24f6ab28891eb18c8e51cdf1` |
| `ensayo_salida/corte_tiempo/informe.json` | `d17a879b48e9403e0f14eafae1daa3b1e804944d97ddfdec9ede010e9e9b76bf` |
| `ensayo_salida/corte_llamadas/informe.json` | `07810176c4bbf556fa8fed81e2f24334f16e96f69a179f633ddfb40e2bbb20e3` |
| `ensayo_salida/corte_sesion/informe.json` | `29bda64cb1731084e6faa96b79a1d7d442619966c786ada8ebee83cae61275c0` |
| `ensayo_salida/corte_sesion_duro/informe.json` | `a03fee3dda0ddc5d270a0c41797eded38e74f2f9723420383e824447e13888fd` |
| `ensayo_salida/servidor_caido/informe.json` | `9038595607d049867681e1a342e65e7f0e039a1b47e3993b624e5f833ef71a2a` |
| `ensayo_salida/guardia_enganche/informe.json` | `df263dfbed4d6975aa60f55ba7674529df43dc3dff5b10e7f1fb1010d433bb05` |
| `ensayo_salida/guardia_log/informe.json` | `6e0e03489ed478521879a88c5be38c6857151cdd04896f9d81ecac0002970bf0` |
| `ensayo_salida/guardia_diff/informe.json` | `ea4c273dabd9963bbf3a2358f405b5cf2008e19f8e27750feb71f2a9c9651909` |
| `defectos_inyectados.json` | `cd35bbac252709556f373b82ce9c5fd1e8f7451803f459e49a7928e2cac69f5e` |
| `armado.json` | `3c0eaaf4541b6606a2aa3d57c45a6a3d3cee693e63ba91445627c0467e80ebeb` |
| `ensayo_nucleo.py` | `b288652594fbb4e4f011d61a992e5d340c71ed1b3078fd72e888a1e69c3b829c` |
| `sorteo_60.json` | `0a2d9eb3e2aa5f7e03a3e9e4acac1ff963f21f66058a497a10b1aff0e86c61a6` |
| `imagen/Dockerfile` | `8243082780996d9fe83295046ad7181d26d35ca097fde2e45f9dbaf70dc599c8` |

La tercera ronda de correcciones solo tocó `scripts/kaggle_registro.py`, sus pruebas y este documento:
`scripts/kaggle_registro_enganches.py` no cambió desde el commit `20b6136`, así que los notebooks armados y
el ensayo siguen valiendo y no se repitieron. Se volvieron a generar `rescate_sobre_ensayo.json`,
`RESUMEN.json` y `HUELLAS.txt`, porque `comprobar` cambió.

Las dieciocho corridas válidas usaron la misma versión de `ensayo_nucleo.py` (cada `informe.json` trae su
SHA-256). Tres baterías anteriores del mismo día se descartaron enteras y no están en disco: la primera por
un fallo en la validación del propio ensayo; la segunda y la tercera porque cada revisión independiente
obligó a cambiar el notebook y el diagnóstico.
