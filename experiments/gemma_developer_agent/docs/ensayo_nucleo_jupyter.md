# Registro del notebook de la iteración 08 y ensayo bajo un núcleo Jupyter real (#160, #164)

**Nada de esto se subió, se envió ni se corrió en Kaggle, y no se gastó cuota de GPU.** Todo lo que este
documento mide se midió en esta máquina, en Docker, el 2026-10-09 (UTC), con un modelo falso. Las cifras son
de un ensayo local: dicen si el registro explica un corte, no cuántas tareas resuelve el agente.

El documento tiene dos capas. El #160 dejó el registro, el notebook y el ensayo. El #164 añadió al notebook
un tope por tarea y el vaciado del mapa de hilos del núcleo, y al diagnóstico dos códigos; está en
[su sección](#tope-por-tarea-y-mapa-de-hilos-del-núcleo-164). Donde el #164 cambió algo que el #160
describía, el texto lo dice. Las cifras de las secciones del #160 son de su batería, que se conserva sin
tocar en `…/iteracion_08/ensayo_salida_160/`; las del #164 son de una batería nueva, en `ensayo_salida/`.

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
| Las salidas del ensayo | `…/iteracion_08/ensayo_salida_160/` (batería del #160) y `…/iteracion_08/ensayo_salida/` (batería del #164) | No; se citan por ruta y SHA-256 ([huellas](#huellas)) |

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
| Plan de una pasada (`A8P1` o `A8P2`), nombres de salida `iteracion_08_p1` o `_p2`, tope de sesión de 150 min con 10 de margen, las llamadas al registro, la guardia tras la primera tarea (2 líneas) y el reempaquetado del zip si la celda falla (1 línea) | 10 (antes 9) | 5, 23 (#160) |
| Tope por tarea (#164): dos constantes con su comentario (4 líneas), `run_sync` espera con tope (quita 2, añade 1), la llamada a `run_sync` va en un `try` con lo que se hace si la tarea no vuelve (quita 1, añade 23) y la guardia mira la primera tarea que no se colgó (quita 1, añade 1) | 10 | 4, 29 sobre lo anterior; 8, 51 en total respecto de la 07 |
| Cierre del registro y nuevo empaquetado antes de detener el servidor | 11 (antes 10) | 0, 8 |

Las celdas 0, 1, 2, 3, 5, 6, 7 y 9 son las de la 07, byte a byte (la 9 es su antigua 8).

- **Condición.** El zip `submission_a_ajustado.zip` tiene el SHA-256
  `d8a3e1d3558f03b72b3f86037ff53b462a8f66566e1bb7907240bcb0ce4d7182`. `armar.py` comprueba que sus seis
  archivos son, byte a byte, los de la carpeta `envios/a_kit_ajustado` y los de la condición A del notebook
  de la iteración 04, y que su `eval_config.yaml` dice 4 minutos y 40 llamadas.
- **Dos pasadas.** La pasada 2 es la pasada 1 con `A8P1` → `A8P2` e `iteracion_08_p1` → `iteracion_08_p2`:
  cambia una línea en la celda 8 y tres en la 10, y nada más. `armar.py` lo comprueba, y el notebook de la
  pasada 2 se ejecutó bajo el núcleo ([escenario `pasada_2`](#resultado-por-escenario)).
- **Topes.** No se cambian los del agente ni los de la condición: `armar.py` comprueba además que el bloque
  que construye la configuración del arnés (`EvalConfig`) es el de la 07, byte a byte. El tope de sesión
  vuelve a los 150 min y 10 de margen de las iteraciones 03, 04 y 06 (la 07 los había recortado a 60 y 5 por
  la cuota que quedaba). El tope del conjunto de tareas sigue en `TOPE_SEGUNDOS = 7200`, que vence antes que
  los 150 min: ver [lo que queda sin medir](#lo-que-el-ensayo-no-puede-decir). El #164 añade un tope **por
  tarea** de 900 s, que es del notebook y no del agente:
  [por qué 900](#el-tope-por-qué-900-s-y-qué-margen-deja).

Notebooks armados tras el #164, de 108 297 bytes cada uno (los del #160 pesaban 91 527 y están en
`…/iteracion_08/instrumentos_160/`):

| Archivo | SHA-256 |
|---|---|
| `kernel_iteracion_08_p1/iteracion.ipynb` | `30aa9b31f776ac522077ef5e93562082ea7bdfdcbd7dbc7e49193b76808714fa` |
| `kernel_iteracion_08_p2/iteracion.ipynb` | `0351fd806807223f21382457ab2352be761dbaeaf0e57c25de4a1491eec214c5` |
| `armar.py` | `52a5f85c9144f1da485f4350a4864d85002c4e7abe1cc81a49cbc58353bb379d` |

El texto de los enganches que llevan tiene el SHA-256
`3d342272fdc9b9357c56867225ba6ce8263e0f15caaf84b8aa0adc700469f130`, el de
`scripts/kaggle_registro_enganches.py` en el commit `2e57468`. Si ese archivo cambia, los notebooks se
vuelven a armar y el ensayo se repite.

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
| 6 | Sesión viva y detenida (#164): el registro no termina en `cierre` ni anota un corte, y el latido siguió más de 960 s después del último evento |
| 7 | Sesión terminada con tareas colgadas (#164): el notebook cortó al menos una tarea por su tope por tarea, comprobó que su hilo había terminado y siguió con las demás. Esas tareas son pares faltantes |

Una sesión que el notebook **terminó** por una tarea colgada lleva `corte('tarea_colgada')` y sale con 3,
como los demás cortes del notebook; el veredicto dice cuál.

**Precedencia en `diagnosticar`:** 4 gana a 3, y 3 gana a 7, a 6 y a 5. Un registro no fiable se dice aunque
la sesión esté cortada o muerta; un corte anotado por el notebook se dice aunque falte el cierre. El 7 exige
`cierre`; el 6 y el 5 son de un registro sin `cierre`, y los separa cuánto siguió el latido sin eventos.

La comprobación de peticiones respondidas es de toda la sesión, no por tarea: una sesión con una tarea
resuelta y otra cuyas peticiones terminaron todas en error sale con 0, y la segunda tarea lo dice en su
ficha (`no_respondidas`, `peticion_cortada`). Cuando el 4 sale por esto, el mensaje nombra las dos lecturas
posibles: o el enganche de peticiones no surte efecto, o el servidor nunca respondió, con las peticiones
iniciadas y las que terminaron en error.

Una sesión que una guardia detuvo no se llama «completa»: su veredicto termina en «sesión detenida por una
guardia», antes o tras la primera tarea.

**El 0 es de la sesión, no de cada tarea.** Una tarea cortada por tiempo o por llamadas no cambia el código:
el notebook siguió y la sesión terminó. Su motivo está en `agente_fin` y en `tope_que_corto` de su ficha.

**Una sesión colgada ya no sale con 5 (#164).** Antes, un notebook vivo y detenido se llamaba «muerta desde
fuera». Ahora hay tres desenlaces distintos, y ninguno es 0:

- el notebook cortó la tarea y siguió: 7, con la lista de tareas cortadas en `tareas_colgadas` y en
  `pares_faltantes`;
- el notebook cortó la tarea y terminó la sesión: 3, con `cortado_por: tarea_colgada`;
- el notebook no llegó a cortar (no debería ocurrir con el tope, y es lo que pasó en el #160, que no lo
  tenía): 6 si el latido siguió más de 960 s tras el último evento, 5 si menos. El veredicto de un 5 dice
  cuántos segundos de latido sin eventos hubo.

El umbral de 960 s es el tope por tarea (900 s), su margen tras el corte (30 s) y un latido (30 s): con
menos silencio el notebook aún no había tenido ocasión de cortar. Es una constante de
`scripts/kaggle_registro.py` (`SILENCIO_DETENIDA_SEGUNDOS`); si cambia el tope del notebook hay que cambiarla.
La corrida que se colgó en el #160 (983,7 s de latido sin eventos) sale ahora con 6.

**Reglas que impiden un 0 sobre una sesión colgada o cortada por el tope.** Dan 4 (registro no fiable):

- un registro cerrado, sin ningún corte ni guardia, con una tarea que empezó y no tiene su `tarea_fin`;
- una tarea terminada que no dice `con_tope: true`. En un registro del #164 en adelante (el que declara el
  enganche «mapa de hilos del núcleo») el campo se exige: ausente, `null` o cualquier valor que no sea `true`
  da 4. Un registro anterior no trae el campo y solo cuenta un `false` explícito;
- una tarea colgada que figura como resuelta, que no lleva `par_faltante: true` o que no trae su evento
  `tarea_colgada`. Una tarea con `par_faltante: true` y sin corte entra en `pares_faltantes` y da 4;
- un evento `tarea_colgada` cuyo `sigue` no es un booleano (un texto como «no» no se interpreta);
- haber seguido tras una tarea colgada sin que el registro pruebe que su hilo terminó (`hilo_vivo` distinto
  de `false`), o siendo la segunda colgada seguida;
- haber empezado otra tarea, o haber cerrado sin `corte`, después de decidir no seguir;
- un evento `tarea_colgada` que no cae dentro de la corrida de ninguna tarea;
- cualquier evento después del `cierre`. Un segundo `cierre` no cuenta como evento posterior; esa tolerancia
  es inocua y no responde a ningún caso visto: de los 16 registros del #160, 14 traen un solo `cierre` y 2
  ninguno; ninguno trae dos.

Cinco de estas reglas (la exigencia de `con_tope`, `sigue` no booleano, la segunda seguida, la marca sin
corte y los eventos tras el cierre) salieron de la revisión del PR #176. Se corrigieron las cinco en vez de
documentarlas como límite: son comprobaciones de una línea sobre el registro, y los 42 registros reales del
ensayo (#160 y #164) dan el mismo código antes y después del cambio.

**`diagnosticar` no sabe cuántas tareas había.** Un registro que termina en `cierre` tras dos tareas
completas sale con 0 aunque el plan fuera de sesenta: el número de tareas está en el JSON de resultados de
la pasada, no en el registro.

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
5. Si dice 7, la sesión terminó y perdió tareas. `sesion.pares_faltantes` las lista. **Una tarea cortada por
   el tope por tarea es un par faltante, no una tarea no resuelta:** al comparar las dos pasadas se excluye
   de la cuenta de discordantes. Lleva `par_faltante: true` en su fila del JSON de la pasada, en su línea de
   `task_results.jsonl` y en su `tarea_fin`, y la clase `tarea_colgada`. Mirar en su ficha (`tareas[].colgada`)
   si el mapa de hilos cerraba un ciclo (`mapa_de_hilos.ciclo`) y abrir `pila_tarea_colgada_<nombre>.txt`,
   que está suelto y dentro del zip (`registro/`): dice en qué línea estaba cada hilo.
6. Si dice 3 con `cortado_por: tarea_colgada`, el notebook terminó la sesión porque el hilo de la tarea
   seguía vivo tras el margen, o porque era la segunda tarea colgada seguida. La pila dice dónde giraba o
   esperaba. Las tareas que no llegaron a correr no están en el registro.
7. Si dice 6, el notebook quedó vivo sin cortar. Mirar `sesion.ultimo_latido_de_la_tarea`: con
   `hilo_de_tarea.cpu_s` creciendo un segundo por segundo el hilo giraba; con la CPU quieta, esperaba.
8. En cualquier caso, leer del primer evento (`registro_instalado`) las versiones de `ipykernel`,
   `jupyter_client`, `rich`, `litellm` y Python, y si el mapa de hilos existe (`mapa_de_hilos.disponible`): es
   la primera medición de la plataforma, y decide con qué versión hay que repetir el ensayo. El notebook las
   imprime también en la celda 8 (`REGISTRO versiones` y `REGISTRO mapa de hilos`). Cada latido trae la
   carga, el número de CPU y los hilos vivos; `sesion.tareas_que_empezaron_con_un_ciclo_en_el_mapa` dice
   cuántas veces el vaciado encontró un ciclo, que es la primera medida de si la carrera ocurre en Kaggle.

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

**Nada en el notebook del #160 cortaba una tarea colgada sin peticiones.** `run_sync` esperaba sin tope a que
la tarea terminara, el tope de 4 minutos del arnés empieza con el bucle del agente y los topes de sesión solo
se miran entre tareas. El #164 lo cambió: ver
[la sección del tope por tarea](#tope-por-tarea-y-mapa-de-hilos-del-núcleo-164), que también recoge lo que
el forense del arnés reconstruyó de este cuelgue.

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
5. **Una tarea podía colgarse sin que nada la cortara** ([el cuelgue](#una-corrida-con-el-parche-global-se-colgó)).
   Desde el #164 la corta el tope por tarea.

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
- **Una tarea colgada sin peticiones** la corta desde el #164 el tope por tarea; lo que ese tope no cubre
  está en [sus límites](#lo-que-el-164-no-midió-o-no-se-parece-a-kaggle).
- **Qué hace Kaggle.** No está comprobado que detenga «Run All» en la primera excepción, ni que conserve los
  archivos sueltos de `/kaggle/working` de una sesión que mata.
- **Matar el núcleo no es lo mismo que el corte de Kaggle.** Aquí es una señal al proceso del núcleo.
- **El cuelgue de una corrida** tiene una causa probable, inferida y no reproducida en el ensayo completo
  ([#164](#la-causa-probable-del-cuelgue-del-160)).
- **Versiones.** La imagen local trae litellm 1.104.0. Otra versión podría disparar la retrollamada de fallo
  ante una cancelación; el envoltorio no depende de eso. La versión de `ipykernel` de la imagen la eligió el
  `Dockerfile` local y la de Kaggle no está medida ([#164](#versiones-de-ipykernel)).
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
  este documento, el episodio y el registro de cambios. Es una lista elegida a mano, no una búsqueda exhaustiva.

**De la corrida real.**

- **Topes.** `TOPE_SEGUNDOS = 7200` vence antes que los 150 min de sesión. Con 87 a 111 s por tarea, 60
  tareas son de 5 200 a 6 700 s: es una inferencia y deja poco margen. Si una pasada se corta, las dos
  pasadas pueden cubrir prefijos distintos de la lista, y la comparación entre ellas solo vale sobre el
  prefijo común. No se cambió ningún tope: lo debe mirar el concilio antes de subir.
- **Predicciones fechadas de la iteración 08.** Fuera de este issue: las escribe el concilio.

## Tope por tarea y mapa de hilos del núcleo (#164)

**Nada de esta sección se subió ni se corrió en Kaggle.** Es código del notebook y ensayo local del
2026-10-09, entre las 12:20 y las 15:41 UTC. La máquina no estuvo en reposo: otros procesos ajenos al
ensayo la cargaron durante la batería (carga de un minuto de la máquina virtual de Docker entre 0,70 y
10,64 al empezar o terminar cada corrida), y las tareas del ensayo que no se colgaron, que en el #160
duraban unos 11 s, duraron de 11,7 a 518,1 s. Ningún reloj de esta sección sirve para comparar con el #160.

### La causa probable del cuelgue del #160

Lo reconstruyó el forense del arnés. Lo que este issue volvió a medir por su cuenta lo dice cada punto.

- **Leído en el código** (`ipykernel` 6.29.5, `iostream.py`, línea 516): una escritura a stdout o stderr
  desde un hilo sin cabecera propia recorre el mapa `_thread_to_parent` con
  `while identity in self._thread_to_parent`, sin guardia. `ipkernel.py` añade una entrada al mapa cuando
  arranca un hilo creado por otro hilo que no es el del núcleo, y solo las quita, para los hilos ya muertos,
  cuando arranca el recolector de basura.
- **Medido aquí:** con un ciclo en ese mapa que pasa por el identificador del hilo de la tarea, la tarea
  queda girando: la pila del núcleo muestra al hilo en `iostream.py`, línea 516, `parent_header`, y el
  latido lo muestra gastando un segundo de CPU por segundo, sin ningún evento
  ([escenario `ciclo_sin_arreglo`](#las-dos-ramas-del-corte)).
- **Medido aquí, fuera del arnés** (sonda con el patrón de hilos del notebook y la máquina cargada): el
  ciclo aparece solo, por la reutilización de identificadores de hilo entre una tarea y la siguiente
  ([tabla](#el-arreglo-de-la-causa-vaciar-el-mapa-antes-de-cada-tarea)).
- **Inferido, no medido:** que ese fuera el cuelgue del #160. El forense le dio cerca de un 75 %; no hay pila
  del proceso que se colgó. En el ensayo completo, con el arnés, el cuelgue **no** se reprodujo por la
  carrera natural: ni en las 9 corridas del forense ni en las de esta batería, que no lo buscó (ver
  [límites](#lo-que-el-164-no-midió-o-no-se-parece-a-kaggle)).
- **Por qué importa en el modo `archivo`:** el arnés escribe a stderr desde el hilo de la tarea en sus
  avisos (`logger.warning` de `swegemma.harness.agent_runner`, por ejemplo cuando una tarea agota su tope).
  Leído en el código; el escenario lo imita con un `WARNING` desde el hilo de la tarea.

### Versiones de ipykernel

- La imagen del ensayo trae `ipykernel` **6.29.5** porque lo fija su `Dockerfile` local, no porque Kaggle
  lo traiga. **La versión de Kaggle no está medida:** ningún log de las corridas reales la dice.
- Leído en el código por el arquitecto de IA, no comprobado aquí más que en tres versiones: el bucle sin
  guardia existe de la 6.29.0 a la 7.0.1 y no existe hasta la 6.28.0 ni desde la 7.1.0. Comprobado aquí:
  `iostream.py` no nombra `_thread_to_parent` ni en la 6.17.1 ni en la 7.1.0, y sí en la 6.29.5.
- **Qué hace el código si la versión es otra.** El vaciado busca el mapa con
  `getattr(flujo, "_thread_to_parent", None)` en `_stdout` y `_stderr` del núcleo y en `sys.stdout` y
  `sys.stderr`. Si no hay núcleo, o ningún flujo lo tiene, anota
  `mapa_de_hilos: {disponible: false, motivo: …}` en `registro_instalado` y en cada `tarea_inicio`, lo
  imprime en la celda 8 y sigue. No es un enganche exigido: la guardia previa no detiene el notebook por
  esto. **El tope por tarea no depende del mapa ni de la versión.**
- **Ensayado sin el mapa.** Dos imágenes más, que solo cambian `ipykernel` (6.17.1 y 7.1.0; una anterior
  al bucle y otra posterior, las dos instalan con Python 3.12): una sesión de 4 tareas sin corte y una
  tarea colgada en cada una. En las cuatro el registro anota «este ipykernel (…) no tiene el mapa
  _thread_to_parent», nada falla por el atributo y el tope corta igual
  ([tabla](#resultado-de-la-batería-del-164)).
- **Condición de lanzamiento, pendiente:** repetir el ensayo con la versión que resulte de Kaggle.
  `imagen_otro_ipykernel/Dockerfile` la recibe como argumento:
  `docker build --build-arg IPYKERNEL=<versión> -t aal-ensayo-nucleo:ipykernel-<versión> <carpeta>`.

### El arreglo de la causa: vaciar el mapa antes de cada tarea

`Registro.tarea` vacía el mapa (el mismo diccionario, con `clear()`) antes de crear el hilo de la tarea y
anota en `tarea_inicio` cuántas entradas había y si cerraban un ciclo. Se eligió frente a la otra opción
del issue, un único grupo de hilos para toda la sesión, con esta medición.

Sonda fuera del arnés (`sonda_164/sonda_arreglos.py`): un núcleo real, el patrón de hilos del notebook (un
hilo por tarea que corre `asyncio.run` y lanza un hilo hijo) y, en cada frontera entre dos tareas, el mismo
recorrido que hace `parent_header`, con tope, desde el hilo de la tarea y desde su hijo. Configuración: 12
procesos quemando CPU dentro del contenedor, `--cpus 4`, 20 ms de trabajo del hilo del núcleo entre tareas.

| Cómo se lanza la tarea | Fronteras | Con un ciclo que dejaría girando una escritura |
|---|---|---|
| Un grupo de hilos nuevo por tarea (celda 10 del #160) | 1 500 | 11 |
| Un hilo demonio nuevo por tarea (celda 10 del #164), sin vaciar | 1 500 | 25 |
| Un hilo demonio nuevo por tarea y el mapa vaciado antes | 1 500 | **0** |
| Un único grupo de hilos para toda la sesión, sin vaciar | 1 500 | **0** |

Los cuatro modos corrieron uno tras otro, cada uno en su contenedor. Para que el cero del arreglo no
dependa de que la carga hubiera cambiado, los dos brazos se repitieron **intercalados en el mismo núcleo**,
en 12 bloques alternos de 250 fronteras:

| Brazo | Fronteras | Con ciclo | Por bloque |
|---|---|---|---|
| Sin vaciar (control positivo) | 1 500 | 60 | 3, 4, 3, 14, 17, 19 |
| Con el vaciado | 1 500 | **0** | 0, 0, 0, 0, 0, 0 |

El control positivo tiene eventos en sus seis bloques, así que la carga abrió la carrera mientras el
arreglo daba cero. **Esto mide el laboratorio y no es una cota para Kaggle:** la tasa sin arreglo fue de
11, 25 y 60 por 1 500 fronteras en tres tandas de la misma configuración, y el auditor del método la vio
variar de 0,03 % a 29 % según la configuración. Sin carga, el forense midió 0 de 3 000.

Las dos opciones dan cero en la carrera natural. Lo que las separa es un ciclo que **ya está** en el mapa
(prueba determinista de la misma sonda, cinco veces por modo: se planta un ciclo que pasa por el
identificador que usará el hilo de la tarea):

| Modo | Una escritura del hilo de la tarea no terminaría |
|---|---|
| Hilo o grupo nuevo por tarea, sin vaciar | 5 de 5 |
| Un único grupo de hilos, sin vaciar | **5 de 5** |
| Con el vaciado | **0 de 5** |

Un único grupo de hilos evita que la carrera cree el ciclo pero no quita uno que ya exista; el vaciado
quita los dos casos, cambia menos líneas y deja en el registro, tarea a tarea, si había un ciclo. Por eso se
eligió. Lo que el vaciado no cubre: un ciclo que se forme **dentro** de una tarea, entre hilos que no son
el de la tarea (hace falta que un hilo cree otro después de morir el que lo creó a él). No se observó; lo
cubre el tope.

**El vaciado no cambia lo que el notebook manda a su salida** (comparación con y sin él sobre las mismas 6
tareas, escenarios `sin_vaciado` y `control_sin_parche`): 1 368 bytes de texto y 6 salidas ricas en la celda
de tareas en los dos, de 101 833 y 101 835 bytes serializadas. Los segundos entre que el servidor responde
y recibe la petición siguiente quedaron entre 0,04 y 0,19 en `ciclo_con_arreglo`, sin ningún corte, y entre
0,04 y 0,20 en las cuatro tareas que siguieron a un corte (`ciclo_sin_arreglo_599` y
`ciclo_sin_arreglo_anillo`): son 8 esperas por lado y no distinguen nada.

### El tope: por qué 900 s y qué margen deja

`run_sync` ya no usa `with ThreadPoolExecutor`, que esperaba sin tope y, al salir del `with`, volvía a
esperar al hilo. Ahora llama a `Registro.correr_con_tope`: la tarea corre en un hilo **demonio** y el
notebook la espera `TOPE_TAREA_SEGUNDOS`. El hilo es demonio para que un hilo colgado no impida salir al
proceso del núcleo.

El valor, **900 s**, lo fijó el concilio: tres veces la tarea real más larga medida.

| Qué | Segundos | Margen que deja el tope |
|---|---|---|
| Tarea real más larga (reloj por tarea, 250 filas de los JSON de las iteraciones 01 a 07 del rescate `2026-10-08T2231Z`; 145 `duration_seconds` de sus 12 zips distintos dan el mismo máximo) | 303,6 | 596,4 s (2,96 veces) |
| Lo que el arnés permite sin colgarse: 4 min del agente más cinco órdenes de la verificación a su tope de 60 s (`eval_config.yaml` del zip) | 540 | 360 s |
| Tarea más larga de las 15 corridas con tope de 900 s y sin cuelgue forzado: la que corta el tope de 4 min del agente en `corte_tiempo` | 269,1 | 630,9 s |
| Tarea más larga de `completa` (26 tareas) | 50,4 | 849,6 s |
| Tarea legítima más larga de todo el día, en una corrida con **tope de ensayo de 600 s**, no de 900 (`fastapi_15280` en `ciclo_con_arreglo`) | 518,1 | 381,9 s frente a 900; 81,9 s frente a los 600 con que corrió |

El recuento del coordinador habla de 310 tareas; aquí se contaron 250 filas con `segundos_reloj` en los
JSON de `iteracion-01` a `iteracion-07` y ninguna pasa de 304 s. La diferencia de recuento no está
explicada.

**El tope no cortó ninguna tarea legítima** en las corridas con el tope de 900 s: `completa`,
`corte_tiempo`, `corte_llamadas`, `corte_sesion`, `corte_sesion_duro`, `servidor_caido`, las tres
guardias, `pasada_2`, `control_sin_parche`, `parche_global`, `sin_vaciado` y las dos sesiones cortas con
otro `ipykernel` (el ensayo lo exige en cada una: cero filas `tarea_colgada` y `con_tope: true` en todos
los `tarea_fin`). Son 15 corridas y su tarea más larga duró 269,1 s. Diez de las 15 arrancaron a la vez,
entre las 13:02:16 y las 13:02:19 UTC, junto con `tarea_colgada_tope_real`: once contenedores en paralelo,
así que parte de la carga de esas corridas era la propia batería.

**Con un tope corto sí se cortan tareas legítimas, y eso se vio.** Los escenarios que cuelgan una tarea usan
un tope de ensayo más corto para no esperar 15 minutos. Con 90 s y la máquina cargada, tres corridas
cortaron además una tarea que no estaba colgada (tardaba 83 s solo en copiar las ruedas al sandbox, con la
CPU del hilo en 0). Las tres se conservan con el sufijo `_t90`. Lo que enseñan: una tarea lenta pero viva
se cancela bien (su hilo terminó en 0,57, 6,21 y 11,58 s y el notebook siguió), y un tope cerca de la
duración real pierde tareas. Con 540 s, el valor que este issue iba a proponer antes de la decisión del
concilio, la tarea de 518,1 s habría quedado a 22 s del corte.

**Lo que el tope de 900 s deja sin cubrir, por aritmética y sin medir:** el notebook deja de empezar tareas
cuando quedan 600 s de sesión (`MARGEN_FINAL_SEGUNDOS`). Una tarea que se cuelgue en los últimos 330 s
antes de ese punto (entre los 8 070 y los 8 400 s de una sesión de 9 000) se cortaría a los 930 s, después
del fin de la sesión. Ahí manda el corte de Kaggle y el diagnóstico dará 5. Lo arregla subir el margen
final o bajar el tope; es decisión del concilio.

### Qué pasa cuando vence el tope

`Registro.tarea_colgada`, en este orden:

1. vuelca la pila de **todos** los hilos con `faulthandler` a `pila_tarea_colgada_<nombre>.txt` (con la hora,
   la tarea y, por hilo, su nombre y su CPU gastada), que queda suelta y dentro del zip;
2. mira, sin tocarlo, si el mapa de hilos cierra un ciclo;
3. pide la cancelación de la tarea a su bucle de eventos;
4. vacía el mapa de hilos: si el hilo giraba en él, eso lo suelta, y la cancelación ya pedida le entra en
   su primer `await`;
5. espera `MARGEN_TAREA_COLGADA_SEGUNDOS` (30 s) a que el hilo termine;
6. anota el evento `tarea_colgada` con todo lo anterior, la carga y los hilos vivos, y devuelve si se puede
   seguir.

**Regla, comprobada en ejecución cada vez:** el notebook sigue con la tarea siguiente solo si el hilo de la
tarea cortada **terminó** dentro del margen. Si sigue vivo, o si es la segunda tarea colgada seguida, anota
`corte('tarea_colgada')` y la celda termina con la excepción `TareaColgada`; el manejador de la celda
cierra el registro, vuelve a empaquetar el zip, detiene el servidor y relanza. **Nunca corren dos tareas a
la vez.** «Dos seguidas» se eligió porque dos cortes consecutivos con el mapa recién vaciado señalan una
causa que no es el mapa, y cada uno cuesta un tope entero.

En las dos ramas la tarea deja su fila: `clase: tarea_colgada`, `resuelta: false` y **`par_faltante: true`**
en el JSON de la pasada, una línea con `resolved: false`, `status: tarea_colgada` y `par_faltante: true` en
`task_results.jsonl`, y su `tarea_fin` con `par_faltante: true`. No queda como «no resuelta» a secas.

La guardia tras la primera tarea mira ahora la primera tarea que **no** se colgó.

### Las dos ramas del corte

| Rama | Escenario | Qué se fuerza | Qué pasó, medido |
|---|---|---|---|
| Corta y sigue | `ciclo_sin_arreglo_599` (notebook sin el vaciado previo) | Antes de la segunda tarea, un ciclo en el mapa sobre los identificadores de seis hilos recién muertos (cada uno apunta a sí mismo); el hilo de la tarea reutiliza uno y escribe un `WARNING` tras arrancar su sandbox | El hilo quedó girando: 595,58 s de CPU en 600 s, ningún evento, ninguna petición al servidor. El tope (600 s de ensayo) la cortó. La pila lo muestra en `iostream.py`, línea 516, `parent_header`, y el corte vio el ciclo en el mapa. Al vaciar el mapa el hilo dejó de girar y la cancelación entró en menos de un segundo (`diff_cierre` y `agente_fin` con `CancelledError`); el hilo terminó a los 25,31 s. El notebook siguió y las tareas 3 y 4 terminaron (97,9 y 195,0 s). Tras el `tarea_fin` de la cortada no hay ningún evento suyo ni peticiones suyas en el servidor. Diagnóstico 7. La validación del ensayo no pasa por una comprobación: exigía 600,0 s o más y el reloj de pared midió 599,9 (el tope se espera con el reloj monótono) |
| Corta y termina, porque el hilo suelto tardó | `ciclo_sin_arreglo_margen`, el mismo escenario repetido | Lo mismo | Igual hasta el corte (594,66 s de CPU, pila en `parent_header`, ciclo visto, `CancelledError` en menos de un segundo, CPU quieta después). El hilo **seguía vivo a los 30 s** del margen, sin gastar CPU. El notebook no siguió: `corte('tarea_colgada')`, registro cerrado, excepción. Diagnóstico 3. Es lo que manda la regla; la validación del ensayo, que esperaba «sigue», no pasa |
| Corta y termina | `tarea_colgada` | El hilo de la segunda tarea entra en un bucle síncrono tras arrancar su sandbox | El tope (90 s de ensayo) la cortó a los 90,0 s. La pila nombra el bucle. Vaciar el mapa no lo suelta: el hilo seguía vivo tras el margen (CPU del hilo de 86,05 a 101,16 s en 15 s). `corte('tarea_colgada')`, registro cerrado, zip con la pila y el cierre, servidor detenido. Corrió 1 tarea de 4 y el servidor no recibió peticiones de ninguna otra. Diagnóstico 3, también leído solo desde el zip |
| Corta y termina, con el tope real | `tarea_colgada_tope_real` | Lo mismo, sin variables de entorno: 900 s y 30 s | Cortada a los 900,0 s; el hilo siguió girando (890,58 a 920,65 s de CPU). Diagnóstico 3 |
| No se cuelga | `ciclo_con_arreglo` (notebook de la pasada 1) | Un ciclo sobre los seis identificadores; **no se puede saber por sus archivos si en anillo o de cada uno consigo mismo** (ver abajo) | El hilo de la tarea reutilizó un identificador del ciclo plantado y ya no estaba en el mapa: `tarea_inicio` anota 12 entradas, `ciclo: true`, `vaciado: true`. Las 4 tareas terminaron. Diagnóstico 0 |

El escenario del ciclo sin el arreglo se corrió cinco veces y **ninguna pasa entera la validación del
ensayo**; se conservan las cinco y el motivo de cada una está en su `informe.json`:

| Corrida | Tope | Qué pasó | Por qué no pasa la validación |
|---|---|---|---|
| Primera prueba, antes de la batería | 40 s | Cortó, el hilo terminó en 0,29 s y siguió | Esperaba la clase `resuelta` en una tarea que da `parche_no_pasa`. No se conserva: la batería la pisó |
| `ciclo_sin_arreglo_t90` | 90 s | Cortó la tarea 1, que no estaba colgada (terminó en 11,58 s), y después la 2, con el ciclo (terminó en 8,96 s): segunda seguida, sesión terminada. Diagnóstico 3 | El tope de 90 s cortó una tarea legítima |
| `ciclo_sin_arreglo_anillo` | 600 s | El ciclo en anillo dejó de existir a los 545 s de CPU; el tope cortó la tarea cuando ya avanzaba, el hilo terminó en 16,89 s y siguió. Diagnóstico 7 | La pila ya no muestra `parent_header` ni el corte ve el ciclo |
| `ciclo_sin_arreglo_599` | 600 s | Cortó y siguió (fila de arriba) | 599,9 s frente a 600,0 |
| `ciclo_sin_arreglo_margen` | 600 s | Cortó y terminó la sesión (fila de arriba) | Esperaba «sigue» |

**El desacuerdo del concilio, con el dato.** Tras vencer el tope y vaciar el mapa, el hilo que giraba en el
mapa **deja de girar y no sigue con la tarea vieja**: en las corridas conservadas su CPU dejó de
crecer, `agente_fin` anotó `CancelledError` en menos de un segundo y el servidor no recibió ninguna petición
suya. Lo que tarda es en **terminar**: 8,96, 16,89 y 25,31 s en las corridas conservadas (0,29 s en la
primera prueba, que no se conserva), y en una corrida más de 30 s, con la máquina cargada. De esas, solo en
dos el corte vio el ciclo plantado: en una el hilo terminó en 25,31 s y el notebook siguió; en la otra no
terminó en 30 s. «Corta y sigue» con el ciclo a la vista tiene, por tanto, un solo caso. No se midió en qué espera ese rato (hipótesis: el cierre de su bucle de eventos espera a
los hilos que recogen el sandbox). En esa corrida el notebook terminó la sesión, como manda la regla. Un
hilo en un bucle síncrono que no depende del mapa **no** termina y sigue gastando CPU (15 s de CPU en 15 s
de margen): ahí el notebook nunca sigue. Las dos posturas quedan cubiertas por la regla: se sigue solo con
el hilo muerto.

**El margen de 30 s queda justo.** Una de cinco esperas lo superó y otra llegó a 25,31 s. Subirlo cuesta
poco frente a un tope de 900 s y es una línea de `armar.py`, pero cambia el notebook y obliga a repetir el
ensayo: queda como decisión del concilio y no se cambió aquí.

**Qué queda del sandbox de la tarea cortada.** En la rama «corta y sigue» la cancelación pasa por el
`finally` del arnés: la tarea deja su `diff_cierre` y su `agente_fin` (con `lanzo: true`) antes de su
`tarea_fin`, y al terminar el ensayo no queda ninguna carpeta `swegemma_sandbox_*` en `/tmp`. En la rama
«corta y termina» queda una (`swegemma_sandbox_…`), porque el hilo nunca llega a ese `finally`.

**El apagado del núcleo no espera al hilo colgado.** Tras la última celda, `nbclient` tardó entre 1,0 y 3,5
s en apagar el núcleo en todas las corridas, también en las seis que dejaron un hilo vivo (2,3 a 2,8 s). Con
el `with ThreadPoolExecutor` del #160 el hilo no era demonio. No se midió el apagado con el código anterior.

### Lo que el latido dice ahora

Cada latido añade: `ultimo_evento` y `segundos_sin_eventos`, `tarea_segundos`, `hilo_de_tarea` (`vivo` y
`cpu_s`, los segundos de CPU de ese hilo), `carga` (`os.getloadavg()`), `cpus`, `cpus_utilizables` (la
afinidad, donde la plataforma la da) e `hilos_vivos`. Donde falta `getloadavg` o la afinidad se anota el
error y el latido sigue. `registro_instalado` añade `versiones` (Python, `ipykernel`, `jupyter_client`,
`nbclient`, `papermill`, `rich` y `litellm`; `None` si el paquete no está) y el estado del mapa.

Con esos campos un giro y un bloqueo se distinguen. Medido en `ciclo_sin_arreglo_t90`: la
primera tarea esperaba al disco (72,4 s sin eventos y `cpu_s` 0,0) y la segunda giraba en el mapa (20,1 s
sin eventos y `cpu_s` 16,79; 32,8 s y 29,48).

### Resultado de la batería del #164

Notebook de la pasada 1 salvo donde se dice. «Tope» es el tope por tarea de esa corrida. «Rescate» y
«Comprobar» como en la [tabla del #160](#resultado-por-escenario).

| Escenario | `ipykernel` | Qué se fuerza | Tope (s) | Filas, de tareas | Tareas cortadas por el tope | Tarea no cortada más larga (s) | Diagnóstico | Rescate | Comprobar | Validación del ensayo |
|---|---|---|---|---|---|---|---|---|---|---|
| `completa` | 6.29.5 | Nada | 900 | 26 de 26 | 0 | 50,4 | 0 | 0 | 0 | pasa |
| `pasada_2` | 6.29.5 | Nada, con el notebook de la **pasada 2** | 900 | 3 de 3 | 0 | 55,0 | 0 | 0 | 0 | pasa |
| `control_sin_parche` | 6.29.5 | Nada, sin el parche de rich | 900 | 6 de 6 | 0 | 55,4 | 0 | 4 | 4 | pasa |
| `parche_global` | 6.29.5 | Nada, con el parche global de rich | 900 | 6 de 6 | 0 | 42,8 | 0 | 0 | 0 | pasa |
| `sin_vaciado` | 6.29.5 | Nada, sin el vaciado del mapa | 900 | 6 de 6 | 0 | 73,4 | 0 | 0 | 0 | pasa |
| `corte_tiempo` | 6.29.5 | El modelo retiene una petición más de 4 min | 900 | 3 de 3 | 0 | 269,1 | 0 | 0 | 0 | pasa |
| `corte_llamadas` | 6.29.5 | El modelo pasa de 40 llamadas | 900 | 3 de 3 | 0 | 56,5 | 0 | 0 | 0 | pasa |
| `corte_sesion` | 6.29.5 | `TOPE_SESION_SEGUNDOS=45` | 900 | 1 de 5 | 0 | 56,8 | 3 | 0 | 3 | pasa |
| `corte_sesion_duro` | 6.29.5 | El ensayo mata el núcleo con una petición en vuelo | 900 | 1 de 3 | 0 | 59,4 | 5 | 0 | 5 | pasa |
| `servidor_caido` | 6.29.5 | El servidor deja de escuchar | 900 | 2 de 3 | 0 | 189,3 | 3 | 0 | 3 | pasa |
| `guardia_enganche` | 6.29.5 | Sin `agent_runner.Console` | 900 | — de 3 | 0 | — | 4 | 0 | 4 | pasa |
| `guardia_log` | 6.29.5 | Toda consola con archivo se cree en Jupyter | 900 | 1 de 3 | 0 | 56,1 | 4 | 4 | 4 | pasa |
| `guardia_diff` | 6.29.5 | El arnés usa un `sandbox_stop` sin envolver | 900 | 1 de 3 | 0 | 53,2 | 4 | 0 | 4 | pasa |
| `ciclo_con_arreglo` | 6.29.5 | Ciclo en el mapa antes de la tarea 2 | 600 | 4 de 4 | 0 | 518,1 | 0 | 0 | 0 | pasa |
| `ciclo_sin_arreglo_599` | 6.29.5 | Ciclo en el mapa antes de la tarea 2, sin el vaciado previo | 600 | 4 de 4 | 1 | 317,9 | **7** | 4 | 4 | no pasa (1) |
| `ciclo_sin_arreglo_margen` | 6.29.5 | Lo mismo, repetido | 600 | 2 de 4 | 1 | 314,4 | **3** | 4 | 4 | no pasa (5) |
| `tarea_colgada` | 6.29.5 | Bucle síncrono en la tarea 2 | 90 | 2 de 4 | 1 | 73,8 | **3** | 0 | 3 | pasa |
| `tarea_colgada_tope_real` | 6.29.5 | Bucle síncrono en la tarea 2 | 900 | 2 de 4 | 1 | 54,5 | **3** | 0 | 3 | pasa |
| `completa_ipykernel_6.17.1` | 6.17.1 | Nada | 900 | 4 de 4 | 0 | 39,5 | 0 | 0 | 0 | pasa |
| `colgada_ipk_6.17.1` | 6.17.1 | Bucle síncrono en la tarea 2 | 90 | 2 de 4 | 1 | 57,4 | **3** | 0 | 3 | pasa |
| `completa_ipykernel_7.1.0` | 7.1.0 | Nada | 900 | 4 de 4 | 0 | 151,9 | 0 | 0 | 0 | pasa |
| `colgada_ipk_7.1.0` | 7.1.0 | Bucle síncrono en la tarea 2 | 600 | 2 de 4 | 1 | 309,2 | **3** | 0 | 3 | pasa |
| `ciclo_sin_arreglo_t90` | 6.29.5 | Como `ciclo_sin_arreglo_599`, con tope de 90 s | 90 | 2 de 4 | 2 | — | 3 | 4 | 4 | no pasa (9) |
| `ciclo_con_arreglo_t90` | 6.29.5 | Como `ciclo_con_arreglo`, con tope de 90 s | 90 | 4 de 4 | 1 | 62,6 | 7 | 0 | 7 | no pasa (9) |
| `colgada_ipk_7.1.0_t90` | 7.1.0 | Como `colgada_ipk_7.1.0`, con tope de 90 s | 90 | 2 de 4 | 2 | — | 3 | 0 | 3 | no pasa (3) |
| `ciclo_sin_arreglo_anillo` | 6.29.5 | Como `ciclo_sin_arreglo_599`, con el ciclo en anillo | 600 | 4 de 4 | 1 | 225,2 | 7 | 4 | 4 | no pasa (2) |

Son 26 corridas: **20 pasan su validación y 6 no** (contado en los `informe.json`: `problemas` vacío o no).
En las seis el diagnóstico da un código distinto de 0.

| Corrida que no pasa | Motivo |
|---|---|
| `ciclo_sin_arreglo_599` | Exigía 600,0 s o más hasta el corte y el reloj de pared midió 599,9 |
| `ciclo_sin_arreglo_margen` | Esperaba «sigue»; el hilo seguía vivo a los 30 s y el notebook terminó la sesión |
| `ciclo_sin_arreglo_anillo` | La pila no muestra `parent_header` y el corte no vio el ciclo: el anillo se había deshecho |
| `ciclo_sin_arreglo_t90` | El tope de 90 s cortó una tarea legítima (y después la del ciclo: segunda seguida) |
| `ciclo_con_arreglo_t90` | El tope de 90 s cortó una tarea legítima |
| `colgada_ipk_7.1.0_t90` | El tope de 90 s cortó una tarea legítima |

Las corridas de la batería no usaron todas la misma versión de `ensayo_nucleo.py`: entre unas y otras
cambió el tope de ensayo de los escenarios, la forma del ciclo plantado y una comprobación de reloj. **El
SHA-256 que trae cada `informe.json` es el del archivo al escribir el informe, no al arrancar** (se calcula
al final): si el archivo se editó durante la corrida, el informe trae el de después. Pasó con
`ciclo_con_arreglo`: arrancó a las 14:28:02 UTC y su informe trae el mismo SHA que `ciclo_sin_arreglo_599`,
que plantó ciclos de cada identificador consigo mismo. Por el orden de la sesión, la edición que cambió el
anillo por esos ciclos fue posterior a su arranque, así que lo probable es que plantara el anillo; ningún
archivo lo prueba. Para lo que el escenario demuestra da igual: `tarea_inicio` anota `ciclo: true` y 12
entradas vaciadas, y el hilo de la tarea reutilizó un identificador plantado. El notebook sí es el mismo
en todas las corridas.

**`comprobar` da 4 y no 7 cuando la tarea cortada dejó su log vacío.** En las corridas del ciclo, la tarea
se corta antes de que el agente escriba nada en `logs/<tarea>.log`, que queda en 0 bytes; el rescate que
mira bytes lo cuenta como faltante y sale con 4, y `comprobar` da el código del rescate antes que el del
diagnóstico. El JSON de `comprobar` trae el 7 de la pasada. En `ciclo_con_arreglo_t90` la tarea cortada ya
tenía su log y `comprobar` da 7. Con las pasadas nombradas (`comprobar_pasadas.py`): la pasada 2 terminada
por una tarea colgada da 3; con una tarea cortada y la sesión seguida da 4 (por el rescate) o 7.

Las seis corridas de medición de tiempo con y sin enganches del #160 **no se repitieron**: la primera
llevaba 11 minutos en 5 tareas (una de 357,2 s, `consolas/con_enganches_r1.log`) y se detuvo a mano. El
costo del registro medido en el #160 no se volvió a medir con el código nuevo.

### Defectos inyectados y entradas adversas

- **Defectos.** `defectos_inyectados_164.py`, con el molde del #160: un reemplazo de texto por defecto en el
  código nuevo de los dos guiones, las tres baterías de pruebas tras cada uno. Se corre sobre una copia del
  árbol, no sobre el que montan los contenedores. Primera pasada, 76 defectos: las pruebas detectaron 72.
  Los cuatro que sobrevivían (no imprimir las versiones al arrancar; seguir sin hilo que comprobar; una
  colgada sin la marca de par faltante; tomar del primer latido lo que dice el último) llevaron a reforzar
  cuatro pruebas. Segunda pasada, con dos defectos más: **78 de 78 detectados**
  (`defectos_inyectados_164.json`). Ese archivo trae `commit: ""`, porque la copia sobre la que corre no es
  un repositorio: que la copia era la del commit `2e57468` lo dice solo el orden de la sesión. Dos de los 78
  (esperar a la tarea sin tope y esperar al hilo sin margen) se detectan porque la batería no termina en
  180 s, no por una aserción. Es una lista elegida a mano, no una búsqueda exhaustiva, y la revisión del
  PR #176 lo demostró: encontró cuatro defectos que sobrevivían (el 7 sin exigir `cierre`; la guardia como
  corte para la tarea sin fin; esperar el doble del tope; `tarea_colgada` que devuelve «seguir» cuando
  algo lanza). Con las pruebas añadidas tras esa revisión, esos cuatro y otros cinco sobre las reglas
  nuevas del diagnóstico se reinyectaron sobre una copia y los nueve se detectan (no quedó archivo de esa
  pasada: es la salida de consola de la sesión).
- **Entradas adversas contra `diagnosticar`** (`adversas_164.py`): los registros reales de cinco sesiones
  con una tarea colgada o cortada y el de la corrida colgada del #160, deformados de a un cambio (quitar un
  evento, moverlo al final, quitar o cambiar un campo, truncar en cada punto con y sin un `cierre`, quitar
  el latido). De 4 397 variantes, 12 salen con 0, y las 12 son de la misma forma: el registro truncado justo
  después de una o dos tareas completas, o antes de la primera, con un `cierre` añadido. Eso es el registro
  de una sesión más corta y completa, y el diagnóstico no puede distinguirlo (no sabe cuántas tareas había).
  Ninguna otra deformación da 0 (`adversas_164.json`).
- **Casos de «sale con 0 sin merecerlo» que encontró el propio implementador** antes de la revisión, y que
  ahora dan 4: un registro cerrado con una tarea sin `tarea_fin` y sin ningún corte (ya salía con 0 antes
  del #164); una tarea que no corrió bajo el tope por tarea; y un evento `tarea_colgada` fuera de la corrida
  de su tarea con una fila que dice que terminó bien. Ninguno de los tres lo produce el notebook armado, que
  se sepa. Además, dos códigos equivocados que no eran 0: una sesión terminada por una primera tarea colgada
  sin peticiones salía con 4 en vez de 3, y una sesión cerrada sin `corte` tras decidir no seguir salía con 7.

### Lo que el #164 no midió o no se parece a Kaggle

- **La versión de `ipykernel` de Kaggle**, y por tanto si el mapa existe allí.
- **El cuelgue por la carrera natural en el ensayo completo.** No se buscó: la carrera se midió en la sonda,
  sin el arnés. En el ensayo, sin el arreglo, la tarea solo se cuelga con el ciclo plantado a mano.
- **Qué rompe un ciclo solo.** En una corrida (`ciclo_sin_arreglo_anillo`) el ciclo
  plantado, un anillo entre seis identificadores, dejó de existir a los 545 s: la CPU del hilo dejó de crecer
  y la tarea siguió. Hipótesis sin medir: la limpieza que `ipykernel` hace al arrancar el recolector de
  basura quitó las entradas de los hilos muertos del anillo. El escenario planta desde entonces un ciclo de
  cada identificador consigo mismo, que dura mientras viva el hilo.
- **Un cuelgue que no suelta el GIL.** El tope lo aplica el hilo del núcleo. Si el hilo colgado no suelta el
  GIL (una llamada nativa que lo retiene), el hilo del núcleo no corre y nada corta. No apareció en ningún
  escenario: el bucle síncrono del ensayo es Python puro y el hilo del núcleo siguió corriendo. Haría falta
  un vigía en otro proceso; es otro issue.
- **Cómo termina Kaggle el núcleo** con un hilo demonio girando, y si conserva la salida de una celda que
  termina con excepción en este caso. Consta que la conserva en otra corrida
  (`data/ensayo_kaggle/kernel_out_l4v3/`), según el arquitecto de IA; no se comprobó aquí.
- **Kaggle ejecuta con papermill**, no con `nbclient` directo. La imagen no trae papermill.
- **El reloj de 4 minutos de las tareas siguientes a un corte.** Tras «corta y sigue» no queda ningún hilo
  girando, así que no hay CPU que repartir; no se midió un caso con un hilo vivo y el notebook siguiendo,
  porque la regla lo impide.
- **Una tarea vieja que siguiera viva contaminaría sin dejar rastro por nombre.** El registro atribuye cada
  evento a la tarea en curso, no al hilo que lo emite. La única defensa es la que hay: no seguir con el
  hilo vivo.
- **La carga de la máquina durante la batería** no se controló y fue alta.
- **El costo del registro** con los campos nuevos del latido no se midió.
- **La ventana final de la sesión** ([arriba](#el-tope-por-qué-900-s-y-qué-margen-deja)).

### Nadie consume todavía la marca de par faltante

La regla del concilio es que una tarea cortada por el tope por tarea es un par faltante: al comparar la
pasada 1 con la pasada 2, ese par se excluye. **Hoy ningún guion versionado hace esa exclusión**, porque
ningún guion versionado compara dos pasadas del notebook:

- Se buscó en `scripts/kaggle_*.py` quién lee el JSON de una pasada o su `task_results.jsonl`. El único
  guion con una prueba por pares es `scripts/kaggle_replicas.py` (McNemar exacto entre réplicas).
- `kaggle_replicas convertir` no acepta el `task_results.jsonl` que escribe el notebook: exige las claves
  del arnés (`instance_id`, `repo`, `agent_patch_size`, `error`), y las filas del notebook traen `task_id`,
  `status` y `error_message`. Leído en el código (`convert_harness_results`); no se ejecutó sobre una
  salida del notebook.
- Si alguien adaptara las filas a esa forma, la de una tarea colgada no se clasificaría: la lista de textos
  de error del arnés es cerrada y el del corte no está en ella, así que el análisis sale con 2 en vez de
  contarla como no resuelta. Lo fija una prueba
  (`test_el_analisis_de_replicas_no_cuenta_una_tarea_colgada_como_no_resuelta`).

Así que la tarea cortada no puede entrar hoy como par discordante por un guion versionado, pero tampoco hay
uno que la excluya: la comparación de las iteraciones anteriores se hizo fuera de git. Queda como
[condición de lanzamiento](#condiciones-de-lanzamiento). La orden que lista los pares que hay que excluir,
por pasada:

```bash
python -m scripts.kaggle_registro diagnosticar --salida <carpeta o zip de la pasada> | python -c "import json,sys; print(json.load(sys.stdin)['sesion']['pares_faltantes'])"
```

Un par se excluye si la tarea está en esa lista en cualquiera de las dos pasadas.

### Condiciones de lanzamiento

Ninguna está cumplida al escribir esto. Subir a Kaggle lo decide el dueño.

1. PR del #164 fusionado, con la CI en verde.
2. Ensayo repetido con la versión de `ipykernel` de Kaggle, que **no está medida**
   ([versiones](#versiones-de-ipykernel)).
3. Exclusión de los pares faltantes resuelta: un análisis de la pasada 1 contra la pasada 2 que excluya
   las tareas de `pares_faltantes` de cualquiera de las dos y diga cuántas excluyó
   ([arriba](#nadie-consume-todavía-la-marca-de-par-faltante)).
4. Primera subida en serie: una pasada, y la segunda solo después de leer la primera.
5. Orden del dueño, con la orden a la vista.
6. Cuota disponible de al menos 14,6 h. La cifra es de la regla del concilio 41 y llegó por el
   coordinador; no se comprobó aquí.

### Límites conocidos

- **La pérdida máxima de 1,1 h de cuota se cumple por cuelgue, no por sesión.** Con los parámetros del
  notebook (sesión de 9 000 s, margen final de 600 s, tope de 900 s, margen de 30 s) una colgada aislada
  cuesta hasta 930 s (0,26 h) y dos seguidas hasta 1 860 s (0,52 h). Con colgadas alternas caben unas ocho
  en una sesión y se irían cerca de 7 440 s (unas 2,07 h de las 2,5 h). Es aritmética, no medición.
- **El tope de 900 s frente a las duraciones reales.** En las 145 filas de tarea de los 12 zips rescatados
  de las iteraciones 03 a 07: mediana 107 s, percentil 95 de 289 s, máximo 303,6 s; 2 pasan de 300 s y
  ninguna de 600 s. Esas corridas tenían un tope de agente de 4 minutos: no descartan una tarea legítima
  más larga con otro tope.
- **La sonda mide el laboratorio.** Sus 1 500 pasadas por sesión son una corrida en serie en un solo núcleo,
  no 1 500 ensayos independientes (los bloques de 250 van de 3 a 19 fronteras y suben con el tiempo). No dice
  nada de la tasa en Kaggle, y la causa del cuelgue original sigue siendo inferida.
- **No hay tope al total de tareas colgadas, solo a las seguidas.** Una sesión en que se cuelgue una tarea
  de cada dos, y cada hilo termine, sigue hasta el final y gasta hasta 930 s por cada una. `diagnosticar`
  da 7 y las lista. Si hace falta un tope al total lo decide el concilio.
- **La ventana final de la sesión.** Una tarea que se cuelgue entre los 8 070 y los 8 400 s de una sesión de
  9 000 se cortaría después del fin de la sesión: se pierden las celdas finales y el diagnóstico da 5.
  Aritmética, no medición ([arriba](#el-tope-por-qué-900-s-y-qué-margen-deja)).
- **El margen de 30 s tras el corte queda justo:** el hilo suelto tardó 25,31 s en terminar en una corrida
  y más de 30 en otra ([arriba](#las-dos-ramas-del-corte)).
- **Un registro truncado tras tareas completas, con un `cierre` añadido, sale con 0** en `diagnosticar` y
  en `comprobar`: ninguno sabe cuántas tareas se esperaban. El notebook armado no puede producirlo, porque
  toda salida temprana del bucle de tareas anota un `corte` (leído en la celda 10; no hay un escenario que
  lo ejercite). El número de tareas está en el JSON de la pasada.
- **Un cuelgue que no suelte el GIL no lo corta este tope**
  ([arriba](#lo-que-el-164-no-midió-o-no-se-parece-a-kaggle)).
- **`comprobar` puede dar 4 en vez de 7** cuando la tarea cortada dejó su log por tarea en 0 bytes
  ([arriba](#resultado-de-la-batería-del-164)).
- **Un evento escrito después del `cierre` da 4, y puede tapar un 3.** Es alcanzable de dos maneras: un hilo
  suelto que se destraba después de «corta y termina» y escribe un evento con el registro ya cerrado, o una
  retrollamada tardía de litellm que llega tras el cierre de una corrida buena. El 4 gana al 3, así que el
  código dejaría de decir «cortada por el notebook»; el veredicto sí lo sigue diciendo, detrás del
  problema. En los 42 registros del ensayo no ocurrió: en los 39 que tienen `cierre`, entre el último evento
  y el `cierre` pasan de 0,014 a 0,418 s y después no hay nada. Con el modelo real no está medido.
- **Un registro con `registro_instalado` y `cierre`, sin ninguna tarea, sale con 0.** Es el caso extremo de
  no saber cuántas tareas se esperaban.

### Pruebas versionadas del #164

`tests/test_kaggle_tope_por_tarea.py`, 81 pruebas, sin Docker, sin el arnés y sin un núcleo: el núcleo es un
doble con el mapa o sin él. No se modificó ninguna prueba del #160. Como en el #160, la cobertura que exige
el CI no mide `scripts/`. Las comparaciones con el reloj llevan tolerancia: la primera versión exigía que
la espera de un tope de 0,3 s durara 0,3 s o más, y en Windows `Thread.join` volvió a los 0,296 s, con la
CI en rojo.

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

Lo que añade el #164:

```bash
# Imágenes con otro ipykernel (una vez por versión)
docker build --build-arg IPYKERNEL=6.17.1 -t aal-ensayo-nucleo:ipykernel-6.17.1 <instrumentos>/iteracion_08/imagen_otro_ipykernel
# Un escenario suelto; IMAGEN, TAREAS_MAX y TOPE_ESCENARIO son opcionales
IMAGEN=aal-ensayo-nucleo:ipykernel-6.17.1 TAREAS_MAX=4 SUFIJO=_ipk_6.17.1 sh <instrumentos>/iteracion_08/correr_ensayo_nucleo.sh tarea_colgada
# La sonda de la carrera, fuera del arnés: los cuatro modos, y los dos brazos intercalados
sh <instrumentos>/iteracion_08/sonda_164/correr_sonda.sh 1500 12 4 20 <nombre de la fase>
sh <instrumentos>/iteracion_08/sonda_164/correr_intercalada.sh 12 250 12 4 20
# Tabla del documento, entradas adversas y defectos (estos últimos, sobre una COPIA del árbol)
python <instrumentos>/iteracion_08/tabla_164.py
python <instrumentos>/iteracion_08/adversas_164.py <árbol del repositorio>
python <instrumentos>/iteracion_08/defectos_inyectados_164.py <copia del árbol>
```

Tres avisos de esta batería:

- **`correr_todo.sh` borra `ensayo_salida/`.** La batería del #160 se copió antes a `ensayo_salida_160/` y
  sus instrumentos a `instrumentos_160/`.
- **Los nombres de carpeta se acortaron a mano** para que el rescate quepa en una ruta de Windows:
  `tarea_colgada_ipykernel_<versión>` pasó a `colgada_ipk_<versión>`. `correr_todo.sh` sigue usando el
  sufijo largo y hay que cambiarlo antes de repetir la batería entera. `ensayo_salida/estado.txt` anota cada
  cambio de nombre.
- **Los guiones de la sonda** que quedaron en `sonda_164/` apuntan a una carpeta temporal de esta sesión
  (`C:/Users/herre/AppData/Local/Temp/t164`): hay que cambiar esa ruta para repetirlos.

La batería no corrió de un tirón: `completa` sola, once escenarios en paralelo, cinco uno tras otro, las
cuatro corridas con otro `ipykernel`, y después tres repeticiones sueltas (`correr_ciclo_164.sh` y dos
corridas más de `ciclo_sin_arreglo`). Un contenedor de medición de tiempo que debía haberse detenido corrió
unos 20 minutos a la vez que la primera repetición (`ciclo_sin_arreglo_anillo`). Al terminar no quedó ningún
contenedor del ensayo.

## Huellas

Todo bajo `experiments/gemma_developer_agent/data/rescate_kaggle/instrumentos/iteracion_08/`, ignorado por
git.

**Del #164** (`ensayo_salida/HUELLAS.txt` lista 420 archivos de salida con sus bytes y su SHA-256):

| Archivo | SHA-256 |
|---|---|
| `ensayo_salida/HUELLAS.txt` | `7d200887001c5d6863ca4f0b8990276d9e2a36b6c99d18d6ee111fc802b5e1d5` |
| `ensayo_salida/RESUMEN.json` | `9c79722fa8aa68a5b71c83cca7d13c27955f25d01d0dc9e9223e0382e88b34bb` |
| `ensayo_salida/rescate_sobre_ensayo.json` | `9e790d977c7311cff3f49b8789b70fbf3a7c9b0022fc4ae3a083c9697a9fc8ee` |
| `ensayo_salida/comprobar_pasadas.json` | `5f423a3f0d8013d70a4cfe7d55a44d4475f84622fe78e321c64b5bdb87637e60` |
| `ensayo_salida/completa/informe.json` | `2723bb9a55e799a249e98b86728eed53218881195e856e2fec62933e72952848` |
| `ensayo_salida/completa/working/crudo_iteracion_08_p1_A8P1.zip` | `93973b1cbd16eac5d888fd2d7e0581eee8dbb43d8c9cb89b2b48e3306c64e625` |
| `ensayo_salida/pasada_2/informe.json` | `f1155018e71d8c30055ee86e4a8d095babf6f9ad65e74807d5b5a82c9ae2c765` |
| `ensayo_salida/sin_vaciado/informe.json` | `0c2b9b9ad8953b0e2da232e1174c638c9c50fb394198ce02063210605b04bb57` |
| `ensayo_salida/ciclo_sin_arreglo_599/informe.json` | `b04255ffd35a7d5160ccc99cce75a5e79d90fac93ea5e69e61fc56ccc55101e6` |
| `ensayo_salida/ciclo_sin_arreglo_599/working/pila_tarea_colgada_iteracion_08_p1.txt` | `63ef87acca60000e611512b73185cacbf0915392b2f0fcfab76ca6efcaf8e2c9` |
| `ensayo_salida/ciclo_sin_arreglo_599/working/crudo_iteracion_08_p1_A8P1.zip` | `ef1cf97552a6b6857020a0f2753942b9746b3d755de14629207895a20e9b1900` |
| `ensayo_salida/tarea_colgada/informe.json` | `13ce14301a4c18bd1d0d7579fcb906c0fd92f4cf372eb3ac1babd948f5858314` |
| `ensayo_salida/tarea_colgada/working/pila_tarea_colgada_iteracion_08_p1.txt` | `fc90a5249fd7dabb467e3a5a24a51287a50ac5d30a93260d88cb4d6a1b42eb46` |
| `ensayo_salida/tarea_colgada/working/crudo_iteracion_08_p1_A8P1.zip` | `5723b0e74b4508ea80d0242a7ab29cf2f32866506ffb6fd9577f4372d9073da4` |
| `sonda_164/resultado.jsonl` | `d9ad2be52c1a76a9a1c38aecd3d6fd954663b9500310bc83a494e2008eb05073` |
| `sonda_164/sonda_arreglos.py` | `1e73f1f7637527d1b19b9dd6b08dc1bd8ea7c532459ae687f7d63d12611b38f9` |
| `defectos_inyectados_164.json` | `89f2dd79c3daa3550e9bb79eb007955ceee904a5b8ff41b5efb67ef935746d98` |
| `adversas_164.json` | `97f20285040cebba61855a0afb366c58574a28c3fcfc465a92f31a68edac9826` |
| `armado.json` | `d08b54869fff64c652c7119eac3979c4cb1caa3f0de8295639d63aaf046a4468` |
| `armar.py` | `52a5f85c9144f1da485f4350a4864d85002c4e7abe1cc81a49cbc58353bb379d` |
| `ensayo_nucleo.py` (última versión; cada `informe.json` trae la suya) | `c5f4a203014d35c8a6eb74b26acbd10684f88cbfccc0893d06535fd344896457` |
| `imagen_otro_ipykernel/Dockerfile` | `ad84974284054a5212b7b2e46c2d850d255476bbd2931f67f7ecd5e496553095` |

`armar.py` se volvió a correr al final y `armado.json` salió idéntico: los notebooks armados son los que
ejecutó la batería.

**Del #160.** Las rutas `ensayo_salida/…` de la tabla siguiente están ahora bajo `ensayo_salida_160/…`, y
`armar.py`, `ensayo_nucleo.py` y `armado.json` de entonces, bajo `instrumentos_160/`. Sus huellas no
cambiaron: `ensayo_salida_160/HUELLAS.txt` sigue siendo `a6a10b39…`, con 294 archivos de salida, incluida
la copia de la corrida colgada.

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
