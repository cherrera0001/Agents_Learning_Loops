# Propuesta de entorno v2: candidato de arreglo de Starlette para el sandbox de FastAPI

> **Estado: ensayo local y lista candidata. No es el entorno del experimento.**
> Esta variante se construyó y se probó con Docker en una máquina local, sobre **dos tareas** y sin parche
> de referencia. El pre-registro (`docs/preregistration/kaggle-baseline-a.md`, § A.1) dice que el entorno
> de la validez es el entorno en que se verifican las réplicas, que fija el ensayo de notebook, y que «una
> medición local con Docker solo vale como ensayo». Por eso esto es una **lista candidata de arreglos**
> para `preregistro/entorno_sandbox_v1.json`, no ese archivo. No prueba que el entorno sirva para las
> demás tareas de fastapi, ni que alguna tarea sea válida, ni que v2 esté «reparado» o «verificado» en
> general.

Fecha: 2026-10-03. Autoría original: sesión de agy (Gemini 3.8 Flash (High), modelo autoinformado, no
telemetría del proveedor). Integración y revisión de contenido: ver el PR que incorpora este archivo.
Referencia: issue #103, épica #100.

Convención de este documento (la de `kaggle_specifications.md`): el arnés se cita por nombre de función o
por sección, sin copiar su texto, y no se reproducen contenidos de tareas, nombres de pruebas, logs ni
trazas. Solo hay nombres de archivo de ruedas, versiones, códigos de salida, conteos, hashes e ids de tareas.

---

## 1. Qué se observó en el control vacío v1

Control sin agente (`--skip-agent-patch`), imagen `swebench-sandbox:20261003-v1`
(`sha256:b1e2a17806d06ee3262368550dff61a56d7ef6772360fd6adbe897c1360f4054`), directorio local ignorado
`artifacts/control-vacio-20261003-v1`:

| Tarea | Código de salida de pytest | Lectura |
|---|---|---|
| `fastapi_11194` | 2 | La recolección falla: el constructor de `FastAPI()` rechaza un argumento que el enrutador de las versiones nuevas de starlette ya no acepta |
| `rich_3061` | 1 | Las pruebas se ejecutan y fallan sin parche (12 con fallo, 100 pasan) |

`summary.json` informa `errors=0` aunque una de las dos tareas no llegó a ejecutar pruebas: ese contador
no sustituye la lectura de los logs. El 0/2 de ese resumen no es una tasa de resolución de Gemma, que no se
ejecutó.

## 2. Diagnóstico

### 2.1 Cómo decide el arnés qué se instala (lectura estática del arnés)

Fuente: lectura estática del arnés `swegemma` 0.2.7 (revisor independiente, 2026-10-03); **no se
ejecutó**. Se cita por nombre de función, en `harness/container_setup.py`:

1. `resolve_wheels_dir` elige el directorio de ruedas **del host**.
2. `_deduplicate_wheels` deja, para cada paquete, la **versión más alta** de ese directorio. Solo entran
   ruedas compatibles con CPython 3.13 y de menos de 20 MB, y se saltan pytest, pluggy, setuptools y wheel.
3. `_build_unpacked_wheels_tar` desempaqueta esas ruedas en `<tempdir>/swegemma_sp_cache_v8/sp_base.tar`.
   **Reutiliza ese archivo siempre que exista y no esté vacío: no lo invalida cuando cambia el directorio
   de ruedas.**
4. `_ensure_container_site_packages` inyecta el contenido de esa caché en el `site-packages` del
   contenedor. Esta inyección **solo ocurre con el gestor Docker**; con el backend `subprocess` el arnés
   no instala nada.
5. `install_editable_package` instala el repositorio de la tarea con `--no-deps`. No se resuelven
   dependencias por tarea: las cotas de versión de cada proyecto no intervienen.
6. `setup_container_wheels` no copia nada si la imagen ya trae `/wheels`; ese `/wheels` de la imagen solo
   sirve de `--find-links` para la instalación editable con `--no-deps`.

**Consecuencias.**

- Lo instalado en el contenedor sale del **directorio del host más la caché**, no de la imagen. El
  identificador de la imagen no fija qué starlette se instaló.
- Los recibos no registran la imagen usada. Qué imagen corrió cada control es «declarado por la sesión de
  origen», no verificado.
- Las exclusiones del lockfile y del guion `scripts/build_sandbox.py` actúan sobre la **imagen**, y no son
  lo que produjo el cambio observado en `fastapi_11194` (véase 3).
- Si el notebook de Kaggle no tiene Docker y se usa `subprocess`, el arnés no instala nada: el entorno de
  pruebas será el que traiga el notebook, y este ensayo local con Docker no lo anticipa.

### 2.2 Qué había en el directorio de ruedas oficial

El wheelhouse oficial traía 56 ruedas de starlette, de la 0.19.0 a la 1.6.0 (imagen v1: 127 ruedas en
total, según el revisor). Con la más alta elegida siempre, `fastapi_11194` falla en la recolección por la
razón de la tabla anterior.

### 2.3 Lo que declaró agy sobre las cotas de las dos tareas

Según agy, que leyó el archivo de proyecto de los snapshots de dos tareas (no se volvió a verificar en esta
integración): `fastapi_14077` fija starlette por debajo de 0.48.0 y `fastapi_11194`, por debajo de 0.49.0.
De ahí salió el corte «0.48.0 en adelante».

## 3. Variante v2: qué cambia y qué produjo el cambio observado

1. **11 ruedas de starlette fuera del directorio de ruedas del host** (de la 0.48.0 en adelante), de modo
   que la más alta sea `starlette-0.47.3-py3-none-any.whl`. En el equipo local se apartaron, sin borrarlas,
   a `data/wheels_incompatibles_fastapi` (ignorado por git).
2. **Dos ruedas copiadas a mano al directorio del host**: `python_multipart-0.0.18` y
   `typing_inspection-0.4.4`.
3. **Borrado de la caché `swegemma_sp_cache_v8`** (véase 2.1, punto 3). Sin este paso, apartar las ruedas
   no cambia nada: el arnés reutiliza la caché anterior y reproduce v1.
4. **Imagen nueva** `swebench-sandbox:20261003-v2`
   (`sha256:42d2948ac7a0006da88d9c1c497a5ccf669a72ce88622c5349574c2ac5c1f4c6`), 117 ruedas según el
   revisor. La imagen v1 ya traía tres de las cuatro ruedas del lockfile; **entre v1 y v2 solo cambia
   `python_multipart`**, además de las 11 de starlette retiradas. Lo que produjo el cambio observado en
   `fastapi_11194` es el directorio del host recortado más la caché regenerada, no la imagen.
5. **Lockfile con 4 ruedas de PyPI**, fijadas por nombre de archivo, URL, tamaño y SHA-256
   (`desviaciones_entorno_wheels.lock`): `typing_inspection-0.4.4`, `h11-0.16.0`, `dirty_equals-0.11` y
   `python_multipart-0.0.18`. Los datos de las cuatro se contrastaron con la API JSON de PyPI el
   2026-10-03 y coinciden. Pero `h11` y `dirty_equals` están en el `/wheels` de las imágenes y **no** en
   el directorio del host ni en la caché del control v2: todo indica que no estuvieron instaladas en él.
6. **Se conserva la evidencia v1.** Los recibos locales de v2, ignorados por git, están en
   `artifacts/control-vacio-20261003-v2`. Esas carpetas (`patches`, `test_outputs`, `traces`) tienen marca
   de tiempo anterior a la de la imagen v2, y la caché se regeneró justo antes de los recibos finales: hubo
   una corrida previa cuyos recibos se sobrescribieron. Que fuera con la caché vieja es una inferencia a
   partir de esas marcas.

### Procedimiento reproducible (orden de los pasos)

Hay **dos directorios distintos**: el **origen completo**, que lee `scripts/build_sandbox.py` para construir
la imagen, y el **directorio recortado del host**, que lee el arnés.

1. Conservar el wheelhouse oficial completo (56 ruedas de starlette) como origen completo; por ejemplo,
   fusionar `data/wheels` y `data/wheels_incompatibles_fastapi` en un directorio nuevo, el que se pase a
   `--full-wheels-dir`.
2. En el directorio del host (`data/wheels`), sacar a `data/wheels_incompatibles_fastapi` las 11 ruedas
   de `excluded_wheels` del lockfile.
3. Copiar a mano al directorio del host `python_multipart-0.0.18` y `typing_inspection-0.4.4` (las del
   lockfile; no se copiaron `h11` ni `dirty_equals`).
4. **Borrar `<tempdir>/swegemma_sp_cache_v8/`** (obligatorio).
5. Construir la imagen: `python -m scripts.build_sandbox --wheels-dir data/wheels --full-wheels-dir
   <origen completo> --tag <tag nuevo> --build-dir <directorio nuevo>`. El guion sale con 3 si el
   lockfile excluye una rueda ausente del origen completo, y no reutiliza un contexto previo.
6. Correr el control vacío; el arnés regenera la caché. Comprobar con `tar -tf` que la caché nueva no
   contiene starlette posterior a 0.47.3.

## 4. Control vacío v2

Sin agente, `--skip-agent-patch --sandbox docker --concurrency 1`. SHA-256 de `task_results.jsonl`:
`be0ce50dcc34233d7e5e01a31c5f9e622ead149a4c021acfa5e9038fa79b9e3c`.

| Tarea | Código de salida | Lectura |
|---|---|---|
| `fastapi_11194` | 1 | Las pruebas se recolectan y fallan sin parche (2 con fallo, 2 pasan) |
| `rich_3061` | 1 | Igual que en v1 |

Lo que **sí** muestra: con el directorio del host recortado y la caché regenerada, el fallo de recolección
de `fastapi_11194` observado en v1 deja de producirse en esta tarea.

Lo que **no** muestra:

- Que los 2 fallos de `fastapi_11194` sean los que corrige el parche de referencia. No se usó el parche, y
  una rueda de multipart elegida por el autor también puede cambiar el comportamiento de la tarea.
- Que `rich_3061` sea una tarea válida: igual que en v1, falta el contraste con la referencia.
- Nada sobre las otras 66 tareas de fastapi ni sobre las 129.

## 5. Riesgos que deben leerse antes de usar esta lista

1. **Un único tope de versión elegido mirando dos tareas.** Las 67 tareas de fastapi van de 2025-09 a
   2026-06 y cada commit fija su propio rango de starlette. Un tope en 0.47.3 puede romper las tareas
   cuyo proyecto necesite una versión más nueva. Esto solo lo decide la medición de validez sobre las 129.
2. **Cada rueda añadida o retirada aleja el sandbox del distribuido** (pre-registro, § H, «Entorno
   arreglado a mano»). La validez que se mida será la de ese entorno, no la del oficial.
3. **El entorno que vale es el del ensayo de notebook**, no el de esta máquina. Con `subprocess` el arnés
   no instala ruedas (2.1); este ensayo con Docker no anticipa ese caso.
4. **Caché del arnés.** Cualquier cambio del directorio de ruedas sin borrar la caché se ignora en silencio.
5. **Ruedas añadidas con la versión que eligió el autor.** Para multipart no se midió ninguna alternativa.

## 6. Qué haría falta para convertirlo en entorno del experimento

1. Que el ensayo de notebook fije el backend (A.0).
2. Volcar los arreglos que sobrevivan a `preregistro/entorno_sandbox_v1.json` (A.1), cada uno con el fallo
   que corrige, y el SHA-256 de la lista ordenada del directorio de ruedas resultante.
3. Medir la validez de las 129 tareas con el parche de referencia, solo en manos del evaluador (A.0).
4. Repetir esa medición si el entorno cambia después.
