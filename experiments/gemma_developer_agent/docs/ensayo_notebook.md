# Ensayo de notebook: guion y paso a paso (#103, commit C0.5)

`scripts/kaggle_ensayo.py` es el instrumento de la sección A.0 del
[pre-registro](../../../docs/preregistration/kaggle-baseline-a.md). Este documento dice qué mide, cómo se
corre en Kaggle, cuánta cuota gasta y qué decisiones del pre-registro quedan fijadas por cada medida.

**No afirma ningún resultado.** El guion solo se ha probado con dobles (`tests/test_kaggle_ensayo.py`):
nadie lo ha corrido todavía en un notebook de Kaggle, no se ha arrancado ningún servidor y no se ha gastado
cuota de GPU. Todo lo que este documento dice del entorno de Kaggle es un supuesto con su fuente
([lista](#supuestos-sin-verificar)), y el ensayo existe para confirmarlo o desmentirlo.

«Arnés» es aquí el paquete `swegemma` de la competencia, como en el pre-registro; se cita por sección
(«HARNESS § 3.1») sin copiar su texto.

## Qué mide

El guion corre **sondas**. Cada sonda da uno de tres resultados:

| Resultado | Qué significa | Lleva valor |
|---|---|---|
| `medido` | Hay medida. «No hay Docker» y «el servidor no arranca» son medidas | Sí |
| `no_disponible` | Lo que había que medir no está al alcance: comando ausente, paquete sin instalar, dato sin declarar, o una sonda previa de la que depende no dio valor | No |
| `error` | Se intentó y falló: tiempo agotado, salida ilegible, respuesta inesperada | No |

`no_disponible` y `error` llevan una categoría de una lista cerrada y ningún valor: «no pude medir» nunca se
escribe como un número. Una sonda que falla no detiene las demás.

| Sonda | Qué mide | Usa GPU |
|---|---|---|
| `python`, `cpu`, `memoria`, `disco` | Versión del intérprete, CPU visibles, memoria total y espacio libre | No |
| `gpu` | GPU visibles, su modelo y su memoria (`nvidia-smi`) | No |
| `version:<paquete>` | Versión instalada de `vllm`, `swegemma`, `adk-submission`, `adk-eval-core`, `google-adk` y del SDK `docker`, leída de los metadatos sin importar el paquete | No |
| `docker` | Por pasos: si existe el binario, si el demonio responde, si está la imagen del sandbox y si arranca un contenedor sin red. De ahí sale el backend: `docker` solo si todo eso se cumple y está el SDK de Python; si no, `subprocess` (HARNESS § 4.1) | No |
| `sesion` | Duración máxima de una sesión. **La declara quien ejecuta**, con su fuente: desde dentro del notebook no hay de dónde leerla | No |
| `envio` | Que el directorio del kit tiene exactamente los archivos y los SHA-256 de [`manifest.json`](../conditions/a_kit/manifest.json) | No |
| `compila` | Que el kit compila con el compilador del arnés, en un proceso aparte | No |
| `tareas` | Elige las cuatro tareas de A.0: las tres primeras de requests por `instance_id` y la de httpx | No |
| `servidor` | Si el servidor del modelo arranca con los parámetros de HARNESS § 3.1 y cuántos segundos pasan desde que se lanza hasta la primera respuesta 200 de `/health`; hash del guion de arranque | Sí |
| `modelo` | Identificador que sirve el servidor, y la versión del modelo | Sí |
| `rendimiento` | Tokens de salida por segundo: mediana de tres peticiones con un prompt inventado (una lista de frases sobre carpintería). Incluye el tiempo de leer el prompt | Sí |
| `rechazo_sintetico:16384` y `:8192` | El observable del rechazo por contexto: código HTTP y qué marcadores trae la respuesta ante un prompt inventado que excede el contexto, con ese tope de tokens de salida. Antes hace un control con un prompt corto y el mismo tope, que debe dar 200 | Sí |
| `agente:16384` | Lo que A.0 delimita: `swegemma eval` sobre las cuatro tareas, con el kit original y `--max-time-minutes 5 --max-tool-calls 100 --max-turns 500 --timeout-seconds 300`. De la salida del arnés lee, por tarea, los turnos del modelo y la clase del error | Sí |
| `agente:8192` | La misma corrida con una copia del kit cuyo único cambio es `max_output_tokens: 8192`. **Solo se corre si hubo algún rechazo con 16 384** (A.0) | Sí |
| `limpieza` | Que el servidor quedó detenido y cuántos procesos siguen usando la GPU | Sí |

Lo que el guion **no** hace:

- No lee ni guarda si las cuatro tareas se resolvieron. Los turnos se guardan ordenados de menor a mayor,
  sin identificador de tarea.
- De `tasks.jsonl` conserva solo `instance_id` y `repo`. El enunciado, el parche de referencia y las pruebas
  se descartan al leer cada línea; no llegan a ninguna variable del guion. El arnés sí lee el archivo entero
  cuando corre las cuatro tareas, como en cualquier evaluación.
- No descarga ni instala nada. Sus peticiones HTTP solo van a `127.0.0.1`. A sus procesos hijos les fija las
  variables que impiden salir a la red (`HF_HUB_OFFLINE`, `TRANSFORMERS_OFFLINE` y otras tres).
- No sobrescribe nada: si existe `--salida`, `--informe` o `--crudo`, sale con 2 sin lanzar nada.

**El servidor se detiene siempre.** El guion guarda el proceso en cuanto lo lanza. Al terminar, al fallar
una sonda, ante una interrupción del notebook o ante `SIGTERM`, le pide que termine y espera 20 s; si sigue
vivo, lo mata y espera 10 s más. En Linux lo hace sobre todo el grupo de procesos, porque el servidor
reparte el modelo entre las cuatro GPU con procesos hijos. Si aun así queda vivo, lo dice por pantalla con
su PID y sale con 1: en ese caso **hay que detener la sesión del notebook a mano**, porque una sesión abierta
sigue gastando cuota.

## Qué deja escrito

| Archivo | Qué es | Se versiona |
|---|---|---|
| `--salida` | El registro `kaggle-notebook-trial/1`, con exactamente las claves que valida `scripts/kaggle_prereg.py`. **Solo se escribe si todas sus medidas existen** | Sí |
| `--informe` | Informe de sondas (`kaggle-notebook-trial-probes/1`): por sonda, estado, categoría, segundos, valores y la forma pública de cada comando | Sí |
| `--crudo` | Directorio con el log del servidor, la salida de cada comando, los cuerpos HTTP, los resultados del arnés y `sondas.json` con los identificadores de las cuatro tareas | **No** |

En los dos archivos versionables solo entran booleanos, números, hashes y cadenas cortas que pasan una lista
blanca (versiones, nombre de la GPU, el notebook y la fuente que declara quien ejecuta). No entra ningún
texto de log, de error ni de respuesta del modelo, ni ninguna ruta: en los comandos, las rutas y los
identificadores de tarea se sustituyen por etiquetas (`<modelo>`, `<envio>`, `<tarea>`), y cualquier
argumento que parezca una ruta queda como `<oculto>`. Antes de escribir el informe, el guion lo recorre
entero y se detiene con 3 si encuentra una cadena fuera de la lista blanca.

El texto exacto del rechazo por contexto queda **solo en `--crudo`**; el informe lleva su código HTTP, qué
marcadores contiene y el SHA-256 del cuerpo.

`--crudo` debe quedar fuera de un repositorio git o en una ruta que git ignore; si no, el guion sale con 2.

| Salida | Significado |
|---|---|
| 0 | Registro escrito y servidor detenido. También `--plan` |
| 1 | El ensayo terminó sin registro (falta alguna medida; el informe dice cuáles sondas) o el servidor sigue vivo |
| 2 | Entrada inválida, archivo de salida existente o `--crudo` en una ruta versionable. No se lanzó nada |
| 3 | Error del propio guion. Se imprime el tipo y el punto, no el texto de la excepción |

## Paso a paso para el dueño

### 0. Antes de gastar cuota

1. Lee el plan en tu máquina, sin Kaggle. Las rutas pueden ser inventadas: `--plan` solo imprime.

   ```bash
   python scripts/kaggle_ensayo.py --plan \
     --modelo <ruta del modelo> --envio <ruta del kit> \
     --manifiesto experiments/gemma_developer_agent/conditions/a_kit/manifest.json \
     --tasks <tasks.jsonl> --snapshots-dir <snapshots>
   ```

   Imprime cada sonda, el comando que correría con las rutas ocultas, su espera máxima y la suma del caso
   peor. Con las esperas por defecto esa suma es de **172 minutos**.

2. Opcional y sin cuota: una sesión de notebook **sin acelerador**, con los mismos datos adjuntos, y el
   comando del paso 4 con `--solo-anfitrion`. Corre solo las sondas que no usan GPU y sirve para comprobar
   las rutas, el kit contra el manifiesto, Docker y la selección de las cuatro tareas. No escribe registro
   y sale con 1.

### 1. Crear el notebook

- Un notebook nuevo **adjunto a la competencia** *Gemma 4 Developer Agent*: los L4 solo están disponibles
  para notebooks de la competencia (página *Upgraded Accelerators*).
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
3. Instala el arnés y vLLM desde el dataset de ruedas. **El guion no instala nada**: la instalación se hace
   aparte, con la celda de instalación del notebook oficial de inicio de la competencia (supuesto S2). La
   sonda `version:*` dirá después qué quedó instalado y en qué versión.

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
  --crudo /kaggle/working/ensayo_crudo \
  --salida /kaggle/working/ensayo_notebook_v1.json \
  --informe /kaggle/working/ensayo_notebook_v1.sondas.json
```

Opciones que conviene conocer:

- `--modelo-version`: versión del modelo. Si se omite, se toma el último componente de la ruta del modelo
  cuando es un número.
- `--sandbox {auto,docker,subprocess}`: `auto` usa el backend que dé la sonda `docker`.
- `--servidor-arg=<opción>`: añade una opción a vLLM. Cambia el hash del guion de arranque, y es una
  desviación de HARNESS § 3.1 que hay que declarar.
- `--sin-agente`: no corre las cuatro tareas. No habrá registro.
- `--espera-servidor` y `--espera-agente-min`: topes de espera; bajarlos acota el caso peor.

Si el ensayo termina con 1, **no se rellena nada a mano**. Se lee el informe, se corrige la causa y se
repite con otro `--crudo` y, si ya existen, con `_v2` en los nombres de salida.

### 5. Descargar y versionar

1. Descarga `ensayo_notebook_v1.json` y `ensayo_notebook_v1.sondas.json`.
2. `ensayo_crudo/` **no se sube al repositorio** ni se pega en un PR o en un comentario: trae logs,
   respuestas del modelo y la salida del arnés. Guárdalo aparte si quieres conservar el texto exacto del
   rechazo.
3. Copia los dos archivos a `experiments/gemma_developer_agent/preregistro/` sin editarlos y haz el commit.
4. El orquestador cierra `ensayo_notebook` en
   [`linea_base_a.json`](../preregistro/linea_base_a.json) con la ruta del registro y su SHA-256, que el
   guion imprime al escribirlo (commit C0.5), y corre `python -m scripts.kaggle_prereg comprobar`.
5. **Detén la sesión** del notebook.

## Cuánta cuota gasta

La página *Upgraded Accelerators* dice que un notebook con L4×4 consume cuota de GPU al doble del ritmo de
T4×2 y P100, y avisa de que ese factor puede subir. La cuota corre **mientras la sesión esté abierta**, no
solo mientras corren las sondas: cuenta también el rato de adjuntar datos, pegar el guion e instalar.

| Caso | Minutos de sesión | Horas de cuota con factor 2 | De dónde sale |
|---|---|---|---|
| Peor, por construcción | 172 de sondas más la preparación | 5,75 más la preparación | Suma de las esperas máximas que imprime `--plan`: no puede tardar más sin que una sonda corte |
| Esperado, una pasada del agente | unos 60 | unas 2 | Estimación con supuestos, abajo |
| Esperado, con repetición a 8 192 | unos 95 | unas 3,2 | Ídem, más una segunda pasada del agente |

El caso peor es una cuenta exacta del guion: 60 s de `gpu`, 240 de `docker`, 300 de `compila`, 1 200 de
`servidor`, 60 de `modelo`, 360 de `rendimiento`, 840 de las dos sondas de rechazo, 7 200 de las dos pasadas
del agente (15 min por tarea y cuatro tareas cada una) y 90 de `limpieza`: 10 350 s.

El caso esperado **es una estimación, no una medida**, y descansa en supuestos sin verificar:

- unos 15 min de preparación con la sesión ya abierta (elección de este documento, sin fuente);
- unos 9 min de carga del modelo (supuesto S6);
- menos de 2 min de `rendimiento` y unos 4 min de las sondas de rechazo (supuesto S7);
- unos 8 min por tarea en la pasada del agente: 5 del presupuesto de A.0 más 3 de montaje y verificación.
  Esos 3 min no tienen fuente: la única duración medida de una verificación es de 40,68 s en local
  (pre-registro, A.2).

Conviene reservar **6 horas de cuota** para el ensayo y, si no llega a tanto, mejor. Si la cuota semanal de
la cuenta (todavía sin medir, #101) no cubre el caso peor, baja `--espera-servidor` y `--espera-agente-min`
y vuelve a leer el plan.

## Qué decisión del pre-registro fija cada medida

| Medida | Dónde queda | Qué fija |
|---|---|---|
| `docker_disponible`, `backend` | Registro | El backend del entorno de pruebas (A.1): la declaración `entorno_sandbox` debe traer el mismo, y la validez se mide en ese entorno. La compuerta rechaza `backend: docker` sin Docker |
| `servidor_arranca`, `envio_compila`, `turnos_por_tarea` | Registro | La compuerta de viabilidad de A.0: servidor arrancado, kit compilado y al menos 5 turnos en al menos la mitad de las tareas. Si no, decisión del dueño `ensayo_no_viable` |
| `rechazos_por_contexto` | Registro | `max_output_tokens` de la línea base: 16 384 si no hay rechazos; 8 192 como desviación declarada si los hay con 16 384 y no con 8 192; si los hay con los dos, decisión `rechazos_con_todos_los_candidatos` |
| `sesion_max_horas` | Registro | Las partes por réplica (sección C) |
| `carga_modelo_segundos` | Registro | Nada por sí sola: es una lectura de viabilidad. La `m` de la fórmula del presupuesto sale del piloto (D.2), no del ensayo |
| `tokens_por_segundo`, `peticiones_al_modelo` | Registro | Nada: lecturas de viabilidad |
| `modelo`, `guion_servidor_sha256` | Registro | Lo que se mantiene fijo entre réplicas (sección C): modelo y parámetros del servidor |
| Observable del rechazo (`rechazo_sintetico:*`) | Informe y `--crudo` | Si la lista de marcadores de `scripts/kaggle_replicas.py` necesita una enmienda (A.0 y sección H). El guion no la cambia |
| Versiones y hardware | Informe | Datos para la declaración del entorno de A.1 (`version_arnes`). No los lee la compuerta |

## Lo que A.0 pide y el esquema de la compuerta no puede representar

El guion produce exactamente el registro que valida `scripts/kaggle_prereg.py`. Donde el esquema no alcanza,
hace lo que dice A.0 y no rellena:

1. **Un ensayo en el que el servidor no arranca o el kit no compila.** El esquema exige números para
   `carga_modelo_segundos`, `tokens_por_segundo`, `peticiones_al_modelo` y una lista no vacía en
   `turnos_por_tarea`. Sin servidor o sin compilación esas medidas no existen. El guion **no escribe
   registro** y sale con 1; no pone ceros. Consecuencia: la rama «ensayo no viable» de la compuerta solo se
   alcanza con un registro cuyos turnos no llegan al mínimo. Un ensayo que falla antes no puede cerrar
   `ensayo_notebook` con este esquema: hace falta una enmienda del esquema o la decisión del dueño.
2. **Hardware, versiones y el observable del rechazo** (código y texto) no tienen campo. Van al informe de
   sondas, que es un archivo versionable aparte, y el texto exacto solo a `--crudo`.
3. **«Identificador y versión del modelo»** son un solo campo de texto, `modelo`. El guion escribe
   `<identificador>@<versión>`.
4. **«Cuántas peticiones rechaza el servidor.»** El guion no cuenta peticiones rechazadas en el servidor:
   cuenta las **tareas** cuyo error del arnés es un rechazo por contexto, que es el observable que A.0
   describe del lado del arnés. `peticiones_al_modelo` es la suma de los turnos que anota el arnés.
5. **La repetición con 8 192** da sus propios turnos, y el esquema tiene una sola lista. El registro lleva
   los del kit original (16 384); los de la repetición quedan en el informe.
6. **«Duración máxima de una sesión.»** A.0 la lista como medida; el guion solo puede registrar lo que
   declara quien ejecuta.
7. **Concurrencia del ensayo.** A.0 no la fija; el guion usa 1.

Además, un error de infraestructura en la fase del agente (snapshot ausente, error del sandbox que no sea
un rechazo por contexto) deja la sonda `agente` en `error` y **no hay registro**: los turnos de una tarea
en la que el agente no llegó a correr no miden nada. Un texto de error que la lista cerrada no clasifica
tiene el mismo efecto.

## Supuestos sin verificar

Cada uno lo confirma o lo desmiente el ensayo. Ninguno es un hecho.

| # | Supuesto | Fuente | Qué lo comprueba |
|---|---|---|---|
| S1 | Las rutas de `/kaggle/input` del comando de arriba: datos de la competencia, modelo y dataset de ruedas | Notebook público de inicio de la competencia (*Getting Started*, del personal de Kaggle); las rutas candidatas del paquete `swegemma` (módulo de envío) | El dueño, en el panel de datos; `envio` y `tareas` |
| S2 | La celda de instalación de ese notebook deja `vllm` y `swegemma` instalados en el intérprete del notebook | El mismo notebook | `version:vllm`, `version:swegemma` |
| S3 | Las opciones de vLLM que corresponden a los parámetros de HARNESS § 3.1 son las que usa el guion, y la versión de vLLM del notebook las acepta | HARNESS § 3.1; la clase de servidor del paquete `adk-submission` 0.2.12 instalado en local | `servidor` |
| S4 | Los parámetros de § 3.1 bastan para arrancar. La clase de servidor del paquete añade opciones que § 3.1 no lista, y el notebook de inicio usa otra fracción de memoria de GPU que § 3.1. El guion sigue § 3.1, como pide el pre-registro | Los mismos | `servidor`. Si no arranca, `--servidor-arg` permite añadir opciones, como desviación declarada |
| S5 | La CLI `swegemma eval` encuentra el servidor en `127.0.0.1:8000` por variables de entorno y dirige cada adaptador LoRA del kit por su nombre | Paquete `swegemma` 0.2.7 instalado en local (registro de modelos) | `agente:16384` |
| S6 | La carga del modelo tarda unos 8 o 9 minutos | Notebook público de un competidor (dariushafshar, sobre el tope de 16 384 tokens) | `servidor`. Solo se usa para estimar la cuota |
| S7 | La generación va a unas decenas de tokens por segundo | El mismo notebook | `rendimiento`. Solo se usa para estimar la cuota |
| S8 | El rechazo por contexto es un HTTP 400 cuyo texto habla de la longitud máxima de contexto | Pre-registro, A.0; el mismo notebook | `rechazo_sintetico:*` |
| S9 | Con 16 384 tokens de salida, el servidor rechaza también prompts que caben en el contexto pero no dejan sitio para la salida | El mismo notebook | Solo `agente:16384`. La sonda sintética usa un prompt que excede el contexto entero y **no** distingue este caso |
| S10 | El notebook no tiene Docker y el backend será `subprocess` | El notebook de inicio usa `subprocess` | `docker` |
| S11 | La duración máxima de sesión | Ninguna de las páginas de la competencia leídas la da | El dueño la lee en Kaggle y la declara con su fuente |
| S12 | `nvidia-smi` existe en el notebook | Costumbre; sin fuente | `gpu`, `limpieza` |
| S13 | El campo de turnos que el arnés escribe por tarea cuenta los turnos del modelo de esa tarea | Paquete `swegemma` 0.2.7 (escritura de resultados); HARNESS § 9.2 | Lectura del volcado crudo |
| S14 | Cada palabra inventada del prompt largo ocupa al menos un token, así que 60 000 palabras exceden 32 768 tokens | Elección de este guion | `rechazo_sintetico:*`: si el código no es 400, el supuesto falla |
| S15 | El factor de consumo de cuota de L4×4 es 2 | Página *Upgraded Accelerators*, que avisa de que puede subir | El dueño lo relee el día del ensayo |
| S16 | La CLI compila el kit con sus dos adaptadores sin que se le pase la lista de adaptadores | [`compilacion_condicion_a.md`](compilacion_condicion_a.md) § 2.2, en local y sin la CLI | `compila`, `agente:16384` |

## Lo que no está comprobado

- Nada de lo anterior se ha ejecutado en Kaggle.
- La implementación real de procesos y HTTP se ha probado solo con procesos triviales de Python en Windows.
  La parada por grupo de procesos de Linux no se ha ejercitado.
- El programa de compilación se ha ejecutado solo en un intérprete sin el arnés, donde sale por la rama
  «arnés ausente».
