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

### 2.1 Cómo elige el arnés las versiones (verificado por el orquestador)

El arnés (`swegemma` 0.2.7) inyecta en el contenedor, para cada paquete, la **versión más alta** que
encuentra en el directorio de ruedas del host (función `_deduplicate_wheels` del módulo de preparación del
contenedor) y luego instala el repositorio de la tarea con `--no-deps`. **No resuelve dependencias por
tarea**: las cotas de versión que declare el proyecto de cada tarea no intervienen.

### 2.2 Qué hay en el directorio de ruedas oficial

El directorio local del wheelhouse oficial traía 56 ruedas de starlette, de la 0.19.0 a la 1.6.0, y el
arnés elige siempre la más alta. Con el wheelhouse sin tocar, `fastapi_11194` falla en la recolección por
la razón de la tabla anterior.

### 2.3 Lo que declaró agy sobre las cotas de las dos tareas

Según agy, que leyó el archivo de proyecto de los snapshots de dos tareas (no se volvió a verificar en esta
integración): `fastapi_14077` fija starlette por debajo de 0.48.0 y `fastapi_11194`, por debajo de 0.49.0.
De ahí salió el corte «0.48.0 en adelante».

## 3. Variante v2: qué cambia

1. **11 ruedas de starlette fuera del directorio de ruedas** (de la 0.48.0 en adelante), de modo que la
   más alta sea `starlette-0.47.3-py3-none-any.whl`. En el equipo local se movieron a un directorio
   hermano ignorado por git. El lockfile las declara en `excluded_wheels` y `scripts/build_sandbox.py`
   las omite del contexto de construcción de la imagen; falla si alguna no está en el origen.
2. **4 ruedas de PyPI añadidas**, fijadas por nombre de archivo, URL, tamaño y SHA-256 en
   `desviaciones_entorno_wheels.lock`: `typing_inspection-0.4.4`, `h11-0.16.0`, `dirty_equals-0.11` y
   `python_multipart-0.0.18`. Los cuatro datos de cada una se contrastaron con la API JSON de PyPI el
   2026-10-03 y coinciden.
3. **Se conserva la evidencia v1.** La imagen v2 es `swebench-sandbox:20261003-v2`
   (`sha256:42d2948ac7a0006da88d9c1c497a5ccf669a72ce88622c5349574c2ac5c1f4c6`); sus recibos locales,
   ignorados por git, están en `artifacts/control-vacio-20261003-v2`.

## 4. Control vacío v2

Sin agente, `--skip-agent-patch --sandbox docker --concurrency 1`. SHA-256 de `task_results.jsonl`:
`be0ce50dcc34233d7e5e01a31c5f9e622ead149a4c021acfa5e9038fa79b9e3c`.

| Tarea | Código de salida | Lectura |
|---|---|---|
| `fastapi_11194` | 1 | Las pruebas se recolectan y fallan sin parche (2 con fallo, 2 pasan) |
| `rich_3061` | 1 | Igual que en v1 |

Lo que **sí** muestra: con esas 11 ruedas fuera, el fallo de recolección de `fastapi_11194` observado en
v1 deja de producirse en esta tarea.

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
3. **El entorno que vale es el del ensayo de notebook**, no el de esta máquina. Si el notebook no permite
   Docker, la validez se mide con `subprocess` y este entorno local solo habrá servido de ensayo.
4. **Ruedas añadidas con la versión que eligió el autor.** Para multipart no se midió ninguna alternativa.

## 6. Qué haría falta para convertirlo en entorno del experimento

1. Que el ensayo de notebook fije el backend (A.0).
2. Volcar los arreglos que sobrevivan a `preregistro/entorno_sandbox_v1.json` (A.1), cada uno con el fallo
   que corrige, y el SHA-256 de la lista ordenada del directorio de ruedas resultante.
3. Medir la validez de las 129 tareas con el parche de referencia, solo en manos del evaluador (A.0).
4. Repetir esa medición si el entorno cambia después.
