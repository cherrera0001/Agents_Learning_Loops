# Ensayo de notebook: guion y paso a paso (#103, commit C0.5)

`scripts/kaggle_ensayo.py` es el instrumento de la sección A.0 del
[pre-registro](../../../docs/preregistration/kaggle-baseline-a.md). Este documento dice qué mide, cómo se
corre en Kaggle, cuánta cuota gasta y qué decisiones del pre-registro quedan fijadas por cada medida.

**No afirma ningún resultado.** El guion solo se ha probado con dobles (`tests/test_kaggle_ensayo.py`):
nadie lo ha corrido todavía en un notebook de Kaggle, no se ha arrancado ningún servidor y no se ha gastado
cuota de GPU. Todo lo que este documento dice del entorno de Kaggle es un supuesto con su fuente
([lista](#supuestos-sin-verificar)), y el ensayo existe para confirmarlo o desmentirlo.

«Arnés» es aquí el paquete `swegemma` de la competencia, como en el pre-registro; se cita por sección
(«HARNESS § 3.1») sin copiar su texto. El registro que produce el guion sigue el esquema de la
**Enmienda 1** del pre-registro (sección I.4).

## Qué mide

El guion corre **sondas**. Cada sonda da uno de tres resultados:

| Resultado | Qué significa | Lleva valor |
|---|---|---|
| `medido` | Hay medida. «No hay Docker» y «el servidor no arranca» son medidas | Sí |
| `no_disponible` | Lo que había que medir no está al alcance: comando ausente, paquete sin instalar, dato sin declarar, una sonda previa de la que depende no dio valor, o se agotó el tope global | No |
| `error` | Se intentó y falló: tiempo agotado, salida ilegible, respuesta inesperada, puerto ocupado | No |

`no_disponible` y `error` llevan una categoría de una lista cerrada y ningún valor: «no pude medir» nunca se
escribe como un número. Una sonda que falla no detiene las demás.

| Sonda | Qué mide | Usa GPU | Necesaria para el registro |
|---|---|---|---|
| `python`, `cpu`, `memoria`, `disco` | Versión del intérprete, CPU visibles, memoria total y espacio libre | No | No |
| `gpu` | GPU visibles, su modelo y su memoria (`nvidia-smi`) | No | No |
| `version:<paquete>` | Versión instalada de `vllm`, `swegemma`, `adk-submission`, `adk-eval-core`, `google-adk` y del SDK `docker`, leída de los metadatos sin importar el paquete | No | No (pero sin `vllm` no se lanza el servidor) |
| `docker` | Por pasos: si existe el binario, si el demonio responde, si está la imagen del sandbox y si arranca un contenedor sin red. De ahí sale el backend (HARNESS § 4.1) | No | Sí |
| `sesion` | Duración máxima de una sesión. **La declara quien ejecuta**, con su fuente | No | Sí |
| `envio` | Que el directorio del kit tiene exactamente los archivos y los SHA-256 de [`manifest.json`](../conditions/a_kit/manifest.json) | No | Para correr el agente |
| `compila` | Que el kit compila con el compilador del arnés, en un proceso aparte | No | Sí |
| `tareas` | Elige las cuatro tareas de A.0: las tres primeras de requests por `instance_id` y la de httpx | No | Para correr el agente |
| `servidor` | Si el servidor del modelo arranca con los parámetros de HARNESS § 3.1 y cuántos segundos pasan desde que se lanza hasta la primera respuesta 200 de `/health`; hash del guion de arranque | Sí | Sí |
| `modelo` | Identificador que sirve el servidor, y la versión del modelo | Sí | Sí |
| `rendimiento` | Tokens de salida por segundo: mediana de tres peticiones con un prompt inventado (una lista de frases sobre carpintería). Incluye el tiempo de leer el prompt | Sí | Sí |
| `rechazo_sintetico:16384` y `:8192` | Control del observable: código HTTP y marcadores ante un prompt inventado que excede **el contexto entero**. Con los dos topes mide lo mismo; sirve para fijar el texto del rechazo, no para elegir entre ellos | Sí | No |
| `calibracion` | Cuántos tokens ocupa cada palabra del relleno, con dos peticiones cortas y el conteo que devuelve el propio servidor | Sí | Sí |
| `rechazo_calibrado:16384` y `:8192` | El caso que decide entre los dos topes: un prompt inventado de unos 20 000 tokens, que cabe en el contexto pero con 16 384 de salida no deja sitio. Da un resultado explícito: `rechazado`, `rechazo_sin_marcador`, `aceptado`, `truncado`, `aceptado_sin_conteo` u `otro` | Sí | Sí |
| `agente:16384` | Lo que A.0 delimita: `swegemma eval` sobre las cuatro tareas, con el kit original y `--max-time-minutes 5 --max-tool-calls 100 --max-turns 500 --timeout-seconds 300`. Lee por tarea los turnos y la clase del error, y cuenta en el registro del servidor las peticiones rechazadas | Sí | Sí |
| `agente:8192` | La misma corrida con una copia del kit cuyo único cambio es `max_output_tokens: 8192`. **Solo se corre si hubo algún rechazo con 16 384** (A.0) | Sí | Solo si hubo rechazos |
| `limpieza` | Que el servidor quedó detenido y cuántos procesos siguen usando la GPU | Sí | Sí: debe quedar limpio |

Tres aclaraciones sobre lo que significan los números:

- **`rechazo_calibrado`**: lo esperable, **a confirmar**, es rechazo con 16 384 y aceptación con 8 192. El
  informe dice en cada caso si coincidió con lo esperado. Si el servidor **trunca** el prompt en vez de
  rechazarlo (responde 200 pero cuenta bastantes menos tokens de los enviados), queda como `truncado`, que
  es un resultado distinto de `aceptado`.
- **`rechazos_por_contexto`** cuenta **peticiones rechazadas por el servidor**: las respuestas 400 a la ruta
  de chat que el servidor anota en su registro de accesos mientras corre el agente. Se contrasta con las
  tareas cuyo error del arnés es un rechazo por contexto: si un conteo ve rechazos y el otro no, o si el
  registro del servidor no muestra ninguna petición pese a haber turnos, la sonda queda en `error` y no se
  elige a cuál creer.
- **`peticiones_al_modelo`** son los **turnos completados según el arnés** (la suma del campo de turnos de
  cada tarea), no las peticiones HTTP. Las peticiones que anotó el servidor quedan aparte en el informe.

Lo que el guion **no** hace:

- No lee ni guarda si las cuatro tareas se resolvieron. Los turnos se guardan ordenados de menor a mayor,
  sin identificador de tarea.
- De `tasks.jsonl` conserva solo `instance_id` y `repo`. El enunciado, el parche de referencia y las pruebas
  se descartan al leer cada línea; no llegan a ninguna variable del guion. El arnés sí lee el archivo entero
  cuando corre las cuatro tareas, como en cualquier evaluación.
- No descarga ni instala nada. Sus peticiones HTTP solo van a `127.0.0.1`. A sus procesos hijos les fija las
  variables que impiden salir a la red (`HF_HUB_OFFLINE`, `TRANSFORMERS_OFFLINE` y otras tres).
- No sobrescribe nada: si existe `--salida`, `--informe` o `--crudo`, sale con 2 sin lanzar nada, y la
  escritura final es exclusiva aunque el archivo aparezca a mitad del ensayo.
- No se fía de un servidor ajeno: si algo contesta ya en el puerto antes de lanzar, la sonda `servidor`
  queda en `error` (`puerto_ocupado`) y no lanza nada.

### Parada del servidor

El guion guarda el proceso en cuanto lo lanza. Al terminar, al fallar una sonda, al agotarse el tope global
o ante una interrupción (`SIGINT`, `SIGTERM`, `SIGHUP`), le pide que termine, espera 20 s y después **mata
siempre a todo el grupo de procesos**, porque el servidor reparte el modelo entre las cuatro GPU con
procesos hijos y que el proceso principal haya terminado no dice nada de ellos. Luego comprueba el grupo
entero, no solo el proceso principal, y pregunta a `nvidia-smi` qué procesos siguen en la GPU.

Si queda vivo algún proceso del grupo, o `nvidia-smi` ve procesos en la GPU, el guion lo dice por pantalla,
**no escribe registro** y sale con 1. En ese caso **hay que detener la sesión del notebook a mano**: una
sesión abierta sigue gastando cuota.

### Tope global

Además de la espera de cada sonda, hay un tope para el ensayo entero: `--tope-total-min`, que por defecto es
la suma de todas las esperas más 10 minutos. Al agotarse, las sondas que falten no se ejecutan (quedan
`no_disponible`, categoría `tope_global`), la que esté en curso se corta y el servidor se detiene. Cada
petición HTTP tiene un tope **total**, no solo por operación de red.

## Qué deja escrito

| Archivo | Qué es | Se versiona |
|---|---|---|
| `--salida` | El registro `kaggle-notebook-trial/1`, con exactamente las claves que valida `scripts/kaggle_prereg.py`, incluido el SHA-256 del informe | Sí |
| `--informe` | Informe de sondas (`kaggle-notebook-trial-probes/1`): por sonda, estado, categoría, segundos, valores y la forma pública de cada comando; la lista `sin_medir`; y qué cuenta cada campo dudoso | Sí |
| `--crudo` | Directorio con el log del servidor, la salida de cada comando, los cuerpos HTTP, los resultados del arnés (**parches del agente y trazas incluidos**) y `sondas.json` con los identificadores de las cuatro tareas | **No** |

Hay tres desenlaces, y el informe dice cuál (`registro.clase`):

| Clase | Cuándo | Registro | Salida |
|---|---|---|---|
| `completo` | El servidor arrancó, el kit compila y están medidas **todas** las sondas necesarias: `servidor`, `modelo`, `rendimiento`, `rechazo_calibrado` con los dos topes y `agente` (más `docker`, `sesion` y `compila`), con la limpieza correcta | Sí | 0 |
| `fallo_temprano` | Está **medido** que el servidor no arranca o que el kit no compila | Sí, con las medidas que no existen **nulas** (Enmienda 1). La compuerta lo cerrará como ensayo no viable | 1 |
| `ninguno` | Falta alguna medida necesaria (en `error` o `no_disponible`), o la limpieza no fue correcta | No | 1 |

`gpu` y `version:*` no bloquean el registro, pero el informe las lista en `sin_medir` si no dieron valor.

En los dos archivos versionables solo entran booleanos, números, hashes y cadenas cortas que pasan una lista
blanca (versiones, nombre de la GPU, el notebook y la fuente que declara quien ejecuta). No entra ningún
texto de log, de error ni de respuesta del modelo, ni ninguna ruta: en los comandos, las rutas y los
identificadores de tarea se sustituyen por etiquetas (`<modelo>`, `<envio>`, `<tarea>`), y cualquier
argumento que parezca una ruta queda como `<oculto>`. Antes de escribir el informe, el guion lo recorre
entero y se detiene con 3 si encuentra una cadena fuera de la lista blanca. El texto exacto del rechazo por
contexto queda **solo en `--crudo`**.

| Salida | Significado |
|---|---|
| 0 | Registro completo escrito y limpieza correcta. También `--plan` |
| 1 | El ensayo terminó con hallazgo: sin registro, con un registro de fallo temprano, o con procesos vivos |
| 2 | Entrada inválida, archivo de salida existente o `--crudo` en una ruta versionable. No se lanzó nada |
| 3 | Error del propio guion. Se imprime el tipo y el punto, no el texto de la excepción |

## Paso a paso para el dueño

### 0. Antes de gastar cuota

**Chequeo previo obligatorio si el notebook se sube por API.** Antes de `kaggle kernels push`, corre
`python -m scripts.kaggle_preflight comprobar <directorio> --tope-min <minutos>` y encadena la subida con
`&&`. Comprueba, sin GPU, que cada celda compila, que la imagen de Python está fijada, que el acelerador
existe, que ninguna celda escribe una ruta fija bajo `/kaggle/input`, que la primera celda lista esa raíz y
localiza el único directorio con ruedas sin esperar ni reintentar, que el notebook es privado y sin internet,
y que hay tope de ejecución. Sale con 2 y no imprime la orden si algo falla. No comprueba que el modelo
cargue: eso exige GPU.

1. Lee el plan en tu máquina, sin Kaggle. Las rutas pueden ser inventadas: `--plan` solo imprime.

   ```bash
   python scripts/kaggle_ensayo.py --plan \
     --modelo <ruta del modelo> --envio <ruta del kit> \
     --manifiesto experiments/gemma_developer_agent/conditions/a_kit/manifest.json \
     --tasks <tasks.jsonl> --snapshots-dir <snapshots>
   ```

   Imprime cada sonda, el comando que correría con las rutas ocultas, su espera máxima, la suma del caso
   peor y el tope global. Con las esperas por defecto: **196 minutos** de sondas y un tope de 206.

2. **Recomendado: una primera pasada sin GPU.** Abre el notebook sin acelerador, adjunta los mismos datos,
   instala el arnés (paso 3) y corre el comando del paso 4 con `--solo-anfitrion`. No gasta cuota de GPU,
   corre solo las sondas que no la usan y comprueba lo que más probablemente falle: las rutas, la
   instalación, el kit contra el manifiesto, la compilación, Docker y la selección de las cuatro tareas. No
   escribe registro y sale con 1; lo que hay que leer es el informe. Solo cuando esa pasada no deje nada en
   `sin_medir` (salvo lo que dependa de la GPU) conviene abrir la sesión con L4×4.

### 1. Crear el notebook

- Un notebook nuevo **adjunto a la competencia** *Gemma 4 Developer Agent*: los L4 solo están disponibles
  para notebooks de la competencia (página *Upgraded Accelerators*).
- **Privado.** No lo compartas ni lo hagas público: su salida puede contener datos de la competencia.
- Acelerador: **GPU L4 ×4**. Internet: **apagado** (la misma página lo exige para toda sesión con L4).
- Anota el nombre y la versión del notebook; se pasan en `--notebook` y quedan en el registro.

### 2. Adjuntar los datos

| Qué | Para qué | Fuente de la ruta |
|---|---|---|
| Datos de la competencia | `tasks.jsonl`, `snapshots/` y el kit `sample_submission/` | Supuesto S1 |
| Modelo `gemma-4-31b-it-qat-w4a16-ct` de `google/gemma-4` | Lo que sirve el servidor. Es el único modelo admitido (página *Model Selection, Budget, and Harness Rules*) | Supuesto S1 |
| Dataset de ruedas `metric/gemma-4-developer-agent-wheelhouse` | De ahí salen el arnés y vLLM ([`entorno_local.md`](entorno_local.md) § 1) | Supuesto S1 |

Comprueba las rutas reales en el panel de datos del notebook: las del comando de abajo son las que cabe
esperar, no un hecho.

### 3. Subir el guion sin internet e instalar el arnés

1. En una celda, `%%writefile /kaggle/working/kaggle_ensayo.py` en la primera línea y, debajo, el contenido
   de `scripts/kaggle_ensayo.py` pegado entero. Es un solo archivo y solo usa la biblioteca estándar.
   Alternativa: subirlo como dataset privado y adjuntarlo.
2. Del mismo modo, `%%writefile /kaggle/working/manifest.json` con el contenido de
   [`conditions/a_kit/manifest.json`](../conditions/a_kit/manifest.json).
3. **Instala el arnés y vLLM. El guion no instala nada.** La instalación es la del notebook oficial de
   inicio de la competencia (*Getting Started: Gemma 4 Developer Agent*, supuesto S2):

   - Copia a tu notebook y ejecuta **solo su primera celda de código**, la de la sección «1. Environment
     Configuration and Package Installation». Esa celda fija variables de entorno para servir sin red e
     instala con `pip`, sin índice y sin dependencias, las ruedas del dataset adjunto.
   - **No ejecutes ninguna otra celda de ese notebook.** En particular:

     > **No ejecutes la celda de la sección «4. Start vLLM Server».** Arranca un servidor del modelo en el
     > puerto 8000 y ocupa las cuatro GPU. Con ese servidor en marcha el guion no mide nada: la sonda
     > `servidor` queda en `puerto_ocupado` y la sesión habrá gastado cuota para nada. Tampoco ejecutes la
     > sección «5», que corre tareas con otra configuración.

   Después, la sonda `version:*` dice qué quedó instalado y en qué versión. Este documento no copia el
   código de esa celda: es de su autor.

### 4. Correr

Primero el plan, con las rutas reales, y después el ensayo:

```bash
!python /kaggle/working/kaggle_ensayo.py \
  --modelo /kaggle/input/models/google/gemma-4/other/gemma-4-31b-it-qat-w4a16-ct/2 \
  --envio /kaggle/input/competitions/gemma-4-developer-agent/sample_submission \
  --manifiesto /kaggle/working/manifest.json \
  --tasks /kaggle/input/competitions/gemma-4-developer-agent/tasks.jsonl \
  --snapshots-dir /kaggle/input/competitions/gemma-4-developer-agent/snapshots \
  --notebook "<usuario>/<notebook> v<versión>" \
  --sesion-max-horas <horas> --sesion-fuente "<dónde lo leíste y qué día>" \
  --crudo /tmp/ensayo_crudo \
  --salida /kaggle/working/ensayo_notebook_v1.json \
  --informe /kaggle/working/ensayo_notebook_v1.sondas.json
```

**El volcado crudo va a `/tmp`, no a `/kaggle/working`.** Todo lo que haya en `/kaggle/working` se publica
como salida del notebook si guardas una versión («Save Version»), y el volcado trae parches del agente,
trazas, respuestas del modelo y logs. Si quieres conservarlo, descárgalo durante la sesión por otro medio;
si en algún momento lo copias a `/kaggle/working`, **bórralo antes de guardar una versión**. Los dos archivos
versionables sí pueden quedar en `/kaggle/working`.

**De dónde sale `--sesion-max-horas`.** No de las páginas de la competencia, que no lo dicen, ni del guion,
que no puede medirlo. Es el límite de duración de una sesión de notebook con GPU que publica Kaggle en su
documentación de notebooks (o el que muestre la propia sesión). Léelo el día del ensayo y escribe en
`--sesion-fuente` de qué página sale y la fecha, en un texto corto y sin rutas, por ejemplo
`"documentacion de notebooks de Kaggle, leida el 2026-10-06"`. Sin las dos opciones no hay registro.

Opciones que conviene conocer:

- `--modelo-version`: versión del modelo. Si se omite, se toma el último componente de la ruta del modelo
  cuando es un número.
- `--sandbox {auto,docker,subprocess}`: `auto` usa el backend que dé la sonda `docker`.
- `--servidor-arg=<opción>`: añade una opción a vLLM (ver «Si el servidor no arranca»).
- `--sin-agente`: no corre las cuatro tareas. No habrá registro.
- `--espera-servidor`, `--espera-agente-min` y `--tope-total-min`: topes de espera; bajarlos acota el caso
  peor.

Si el ensayo termina con 1, **no se rellena nada a mano**. Se lee el informe, se corrige la causa y se
repite con otro `--crudo` y, si ya existen, con `_v2` en los nombres de salida.

### Si se interrumpe, antes de repetir

Una interrupción no debería dejar el servidor vivo, pero se comprueba antes de volver a lanzar nada:

```bash
!nvidia-smi --query-compute-apps=pid,used_memory --format=csv
!pgrep -af vllm
```

Las dos órdenes deben salir sin procesos. Si queda alguno, `!pkill -9 -f vllm.entrypoints` y se comprueba
otra vez; si sigue, se reinicia la sesión. Repetir el ensayo con un vLLM anterior vivo no da una medida: el
guion lo detecta por el puerto ocupado, pero la memoria de las GPU seguiría tomada.

### Si el servidor no arranca

El guion arranca vLLM con los parámetros que lista HARNESS § 3.1 y nada más, como pide el pre-registro. La
clase de servidor del paquete `adk-submission`, que es la que usa el notebook de inicio, añade opciones que
§ 3.1 **no** lista; entre ellas `--dtype` y `--reasoning-config`. Si la sonda `servidor` da `arranca: false`
y el log (`servidor.log`, en `--crudo`) apunta a una de ellas:

1. Imprime en el notebook el comando que construiría el propio arnés, para ver sus opciones exactas:

   ```bash
   !python -c "from adk_submission import VllmConfig, VllmServer; print(VllmServer(VllmConfig(model='x', tool_call_parser='gemma4', reasoning_parser='gemma4', tensor_parallel_size=4)).build_cmd())"
   ```

2. Pasa al guion las que falten, una opción `--servidor-arg` por palabra del comando:

   ```bash
   --servidor-arg=--dtype --servidor-arg=<valor> \
   --servidor-arg=--reasoning-config --servidor-arg='<el JSON que imprimió el paso 1>'
   ```

3. Repite el ensayo con otro `--crudo` y `_v2` en las salidas.

Cada opción añadida **cambia el hash del guion de arranque** y es una **desviación de HARNESS § 3.1**: se
declara en el PR que versiona el registro. Un registro de fallo temprano obtenido sin esas opciones no se
borra: se conserva junto al nuevo.

### 5. Descargar y versionar

1. Descarga `ensayo_notebook_v1.json` y `ensayo_notebook_v1.sondas.json`.
2. El volcado crudo **no se sube al repositorio** ni se pega en un PR o en un comentario.
3. Copia los dos archivos a `experiments/gemma_developer_agent/preregistro/` **sin editarlos** y haz el
   commit. El registro cita al informe por su SHA-256: si el informe cambia un byte, deja de corresponderle.
4. El orquestador cierra `ensayo_notebook` en
   [`linea_base_a.json`](../preregistro/linea_base_a.json) con la ruta del registro y su SHA-256, que el
   guion imprime al escribirlo (commit C0.5), y corre `python -m scripts.kaggle_prereg comprobar`.
5. **Detén la sesión** del notebook. No guardes una versión con el volcado crudo dentro de `/kaggle/working`.

## Cuánta cuota gasta

La página *Upgraded Accelerators* dice que un notebook con L4×4 consume cuota de GPU al doble del ritmo de
T4×2 y P100, y avisa de que ese factor puede subir. La cuota corre **mientras la sesión esté abierta**, no
solo mientras corren las sondas: cuenta también el rato de adjuntar datos, pegar el guion e instalar.

| Caso | Minutos de sesión | Horas de cuota con factor 2 | De dónde sale |
|---|---|---|---|
| Peor, por construcción | 196,5 de sondas (tope global: 206,5) más la preparación | 6,55 (tope: 6,88) más la preparación | Suma de las esperas máximas que imprime `--plan`; el tope global corta el ensayo si se pasa |
| Esperado, una pasada del agente | unos 65 | unas 2,2 | Estimación con supuestos, abajo |
| Esperado, con repetición a 8 192 | unos 100 | unas 3,3 | Ídem, más una segunda pasada del agente |

El caso peor es una cuenta exacta del guion: 60 s de `gpu`, 240 de `docker`, 300 de `compila`, 1 200 de
`servidor`, 60 de `modelo`, 360 de `rendimiento`, 840 de las dos sondas de exceso total, 240 de
`calibracion`, 1 200 de las dos sondas calibradas, 7 200 de las dos pasadas del agente (15 min por tarea y
cuatro tareas cada una) y 90 de `limpieza`: 11 790 s. El tope global por defecto añade 600 s.

El caso esperado **es una estimación, no una medida**, y descansa en supuestos sin verificar:

- unos 15 min de preparación con la sesión ya abierta (elección de este documento, sin fuente);
- unos 9 min de carga del modelo (supuesto S6);
- menos de 2 min de `rendimiento`, unos 4 de las sondas de exceso total y unos 5 de la calibración y las
  sondas calibradas (supuesto S7; los 5 min no tienen fuente);
- unos 8 min por tarea en la pasada del agente: 5 del presupuesto de A.0 más 3 de montaje y verificación.
  Esos 3 min no tienen fuente: la única duración medida de una verificación es de 40,68 s en local
  (pre-registro, A.2).

Conviene reservar **7 horas de cuota** para el ensayo. Si la cuota semanal de la cuenta (todavía sin medir,
#101) no cubre el caso peor, baja `--espera-servidor`, `--espera-agente-min` o `--tope-total-min` y vuelve a
leer el plan. La primera pasada con `--solo-anfitrion` no gasta cuota de GPU.

## Qué decisión del pre-registro fija cada medida

| Medida | Dónde queda | Qué fija |
|---|---|---|
| `docker_disponible`, `backend` | Registro | El backend del entorno de pruebas (A.1): la declaración `entorno_sandbox` debe traer el mismo, y la validez se mide en ese entorno. La compuerta rechaza `backend: docker` sin Docker |
| `servidor_arranca`, `envio_compila`, `turnos_por_tarea`, `turnos_por_tarea_repeticion` | Registro | La compuerta de viabilidad de A.0: servidor arrancado, kit compilado y al menos 5 turnos en al menos la mitad de las tareas, con la lista medida con el `max_output_tokens` que quede fijado. Si no, decisión del dueño `ensayo_no_viable` |
| `rechazos_por_contexto` | Registro | `max_output_tokens` de la línea base: 16 384 si no hay rechazos; 8 192 como desviación declarada si los hay con 16 384 y no con 8 192; si los hay con los dos, decisión `rechazos_con_todos_los_candidatos` |
| `sesion_max_horas` | Registro | Las partes por réplica (sección C) |
| `carga_modelo_segundos` | Registro | Nada por sí sola: es una lectura de viabilidad. La `m` de la fórmula del presupuesto sale del piloto (D.2), no del ensayo |
| `tokens_por_segundo`, `peticiones_al_modelo` | Registro | Nada: lecturas de viabilidad |
| `modelo`, `guion_servidor_sha256` | Registro | Lo que se mantiene fijo entre réplicas (sección C): modelo y parámetros del servidor |
| `informe_sha256` | Registro | Qué informe de sondas acompaña al registro |
| `rechazo_calibrado:*` | Informe | Nada en la compuerta. Dice si el mecanismo que se espera (rechazo con 16 384, aceptación con 8 192) es el real, antes de gastar una pasada del agente en descubrirlo |
| Observable del rechazo (`rechazo_sintetico:*`, `rechazo_calibrado:*`) | Informe y `--crudo` | Si la lista de marcadores de `scripts/kaggle_replicas.py` necesita una enmienda (A.0 y sección H). El guion no la cambia |
| Versiones y hardware | Informe | Datos para la declaración del entorno de A.1 (`version_arnes`). No los lee la compuerta |

**Docker sin la imagen del sandbox.** Si el notebook tiene Docker pero la imagen del sandbox no está cargada
(o falta el SDK de Python, o el contenedor de prueba no arranca), el guion registra `docker_disponible:
true` y fija el backend **`subprocess`**, que es con el que corre las cuatro tareas. Eso fija A.1: la validez
se mediría con `subprocess`. Si lo que se quiere es Docker, hay que cargar la imagen en el notebook y repetir
el ensayo; no se cambia el backend del registro a mano. `--sandbox docker` fuerza el backend, pero entonces
las cuatro tareas tienen que correr de verdad con Docker o la sonda del agente queda en `error`.

## Cómo quedó lo que A.0 pide frente al esquema

La Enmienda 1 del pre-registro resolvió tres de los puntos que la primera versión de este instrumento
encontró; el resto sigue como límite declarado.

| Punto | Estado |
|---|---|
| Un ensayo en el que el servidor no arranca o el kit no compila no tenía cómo registrarse sin inventar números | **Resuelto (Enmienda 1):** registro de fallo temprano con esas medidas nulas; la compuerta lo cierra como no viable y rechaza un número en una medida que no puede existir |
| La repetición con 8 192 da sus propios turnos y el esquema tenía una sola lista | **Resuelto (Enmienda 1):** `turnos_por_tarea_repeticion`; la viabilidad se juzga con la lista del valor que queda fijado |
| Hardware, versiones y observable del rechazo no tienen campo | **Resuelto (Enmienda 1):** van al informe de sondas, que el registro cita con `informe_sha256`. El texto exacto, solo en `--crudo` |
| «Cuántas peticiones rechaza el servidor» | Ahora se cuentan peticiones rechazadas en el registro de accesos del servidor, contrastadas con el arnés. Depende del supuesto S17 |
| «Peticiones al modelo» | Son turnos completados según el arnés, no peticiones HTTP |
| «Identificador y versión del modelo» son un solo campo de texto | El guion escribe `<identificador>@<versión>` |
| «Duración máxima de una sesión» | Se declara con su fuente (Enmienda 1); no se mide |
| Concurrencia del ensayo | A.0 no la fija; el guion usa 1 |

Además, un error de infraestructura en la fase del agente (snapshot ausente, error del sandbox que no sea
un rechazo por contexto) deja la sonda `agente` en `error` y **no hay registro**: los turnos de una tarea
en la que el agente no llegó a correr no miden nada. Un texto de error que la lista cerrada no clasifica
tiene el mismo efecto.

## Disposición medida de `/kaggle/input`

El supuesto S1 de abajo resultó falso como regla: la disposición **no es fija**. Hay dos medidas.

| Dónde se midió | `os.listdir('/kaggle/input')` | Directorio de las ruedas |
|---|---|---|
| Tres corridas por lotes del 2026-10-03, lanzadas por API con la imagen fijada (dos en L4×4 y una en T4×2) | `['competitions', 'datasets', 'models']` | `/kaggle/input/datasets/metric/gemma-4-developer-agent-wheelhouse`, con 41 ruedas instaladas |
| Sesión interactiva del dueño en `cs4all/prueba-a-ajustada`, GPU L4×4, 2026-10-04 | `['gemma-4-developer-agent', 'gemma-4-developer-agent-wheelhouse', 'models']` | `/kaggle/input/gemma-4-developer-agent-wheelhouse` |

En la sesión del 2026-10-04, la ruta de la primera fila no era un directorio. `metric/gemma-4-developer-agent-wheelhouse`
es el identificador del dataset para `dataset_sources`; no es una ruta de disco. Por API, el dataset lista 41
archivos `.whl` (2026-10-04); eso dice que tiene ruedas, no cómo se llama su directorio en el notebook.

No se sabe por qué cambia la disposición (sesión interactiva frente a corrida por lotes, o un cambio de Kaggle
entre un día y otro). Dentro de `models` no se listó nada en la sesión interactiva.

**Regla que sale de esto.** Ninguna celda escribe una ruta bajo `/kaggle/input`. La primera celda lista la raíz,
localiza el único directorio con ruedas, el de `tasks.jsonl` y el del modelo, imprime lo que encontró y se
detiene si falta alguno o hay más de uno. No espera ni reintenta, y no comparte celda con el servidor del
modelo. Las rutas del notebook oficial de inicio son las de la primera fila y no se copian.
`scripts/kaggle_preflight.py` rechaza un notebook que no cumpla esto.

## Supuestos sin verificar

Cada uno lo confirma o lo desmiente el ensayo. Ninguno es un hecho.

| # | Supuesto | Fuente | Qué lo comprueba |
|---|---|---|---|
| S1 | Las rutas de `/kaggle/input` del comando de arriba: datos de la competencia, modelo y dataset de ruedas | Notebook público de inicio de la competencia (*Getting Started*, del personal de Kaggle); las rutas candidatas del paquete `swegemma` (módulo de envío) | El dueño, en el panel de datos; `envio` y `tareas` |
| S2 | La primera celda de código de ese notebook deja `vllm` y `swegemma` instalados en el intérprete del notebook, y basta por sí sola | El mismo notebook | `version:vllm`, `version:swegemma`, `compila` |
| S3 | Las opciones de vLLM que corresponden a los parámetros de HARNESS § 3.1 son las que usa el guion, y la versión de vLLM del notebook las acepta | HARNESS § 3.1; la clase de servidor del paquete `adk-submission` 0.2.12 instalado en local | `servidor` |
| S4 | Los parámetros de § 3.1 bastan para arrancar. La clase de servidor del paquete añade opciones que § 3.1 no lista (`--dtype`, `--reasoning-config` y otra del planificador), y el notebook de inicio usa otra fracción de memoria de GPU que § 3.1. El guion sigue § 3.1, como pide el pre-registro | Los mismos | `servidor`. Si no arranca: «Si el servidor no arranca» |
| S5 | La CLI `swegemma eval` encuentra el servidor en `127.0.0.1:8000` por variables de entorno y dirige cada adaptador LoRA del kit por su nombre | Paquete `swegemma` 0.2.7 instalado en local (registro de modelos) | `agente:16384` |
| S6 | La carga del modelo tarda unos 8 o 9 minutos | Notebook público de un competidor (dariushafshar, sobre el tope de 16 384 tokens) | `servidor`. Solo se usa para estimar la cuota |
| S7 | La generación va a unas decenas de tokens por segundo | El mismo notebook | `rendimiento`. Solo se usa para estimar la cuota |
| S8 | El rechazo por contexto es un HTTP 400 cuyo texto habla de la longitud máxima de contexto | Pre-registro, A.0; el mismo notebook | `rechazo_sintetico:*`, `rechazo_calibrado:*` |
| S9 | Con 16 384 tokens de salida, el servidor rechaza también prompts que caben en el contexto pero no dejan sitio para la salida, y con 8 192 no | El mismo notebook | `rechazo_calibrado:16384` y `:8192`, que dicen si coincidió con lo esperado |
| S10 | El notebook no tiene Docker y el backend será `subprocess` | El notebook de inicio usa `subprocess` | `docker` |
| S11 | La duración máxima de sesión | Ninguna de las páginas de la competencia leídas la da | El dueño la lee en la documentación de Kaggle y la declara con su fuente |
| S12 | `nvidia-smi` existe en el notebook | Costumbre; sin fuente | `gpu`, `limpieza` |
| S13 | El campo de turnos que el arnés escribe por tarea cuenta los turnos del modelo de esa tarea | Paquete `swegemma` 0.2.7 (escritura de resultados); HARNESS § 9.2 | Lectura del volcado crudo; `peticiones_en_el_registro_del_servidor` del informe |
| S14 | El relleno del prompt ocupa entre 0,25 y 8 tokens por palabra, y 60 000 palabras exceden 32 768 tokens | Elección de este guion | `calibracion` lo mide; fuera de ese rango queda en `error` |
| S15 | El factor de consumo de cuota de L4×4 es 2 | Página *Upgraded Accelerators*, que avisa de que puede subir | El dueño lo relee el día del ensayo |
| S16 | La CLI compila el kit con sus dos adaptadores sin que se le pase la lista de adaptadores | [`compilacion_condicion_a.md`](compilacion_condicion_a.md) § 2.2, en local y sin la CLI | `compila`, `agente:16384` |
| S17 | El servidor anota en su salida una línea por petición de chat con su código HTTP, en el formato habitual de los registros de acceso, y lo hace al momento | Costumbre del servidor web que usa vLLM; sin fuente de la competencia | `agente:*`: si hay turnos y el registro no muestra peticiones, la sonda queda en `error` (`log_sin_peticiones`) en vez de dar un cero |
| S18 | El servidor devuelve `usage.prompt_tokens` en una petición de chat | API compatible con OpenAI; sin fuente de la competencia | `calibracion`: sin ese conteo queda en `error` y no hay registro |
| S19 | Un prompt de 20 000 tokens con el tope de 8 192 se responde dentro de 10 minutos | Elección de este guion | `rechazo_calibrado:8192`: si no, `tiempo_agotado` |

## Lo que no está comprobado

- Nada de lo anterior se ha ejecutado en Kaggle.
- La parada por grupo de procesos y el conteo de procesos vivos del grupo solo corren en POSIX. Sus pruebas
  con un árbol de procesos real están marcadas para POSIX y las ejercita el CI de Ubuntu; en la máquina
  donde se escribió el guion (Windows) se omiten.
- El programa de compilación lo ejecutó el revisor con el arnés real sobre el kit local y compila; en el
  notebook no se ha ejecutado.
