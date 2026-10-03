# Entorno Local del Arnés Oficial (swegemma y adk-submission)

Este documento registra la procedencia, versiones, licencias y procedimiento de instalación del
arnés oficial de evaluación para el desafío Google Gemma 4 Developer Agent en un entorno virtual
aislado fuera del repositorio (`AGENTS.md`, `CONTRIBUTING.md`).

---

## 1. Procedencia Oficial y Licencias

El arnés de evaluación no se distribuye a través del índice público PyPI (donde `swegemma`, `adk-submission`
y `adk-eval-core` retornan HTTP 404), sino mediante el dataset oficial mantenido por la organización de
la competencia en Kaggle.

| Atributo | Detalle Verificado |
|---|---|
| **Dataset de origen** | `metric/gemma-4-developer-agent-wheelhouse` (Kaggle Dataset) |
| **URL del dataset** | `https://www.kaggle.com/datasets/metric/gemma-4-developer-agent-wheelhouse` |
| **Mantenedor oficial** | Ryan Holbrook / Kaggle Competition Metrics (`metric`) |
| **Versión del dataset** | Versión 28 (última actualización: 2026-09-30) |
| **Licencia del concurso**| Apache 2.0 (declarada en competencia `149921` / `gemma-4-developer-agent`) |
| **Licencia google-adk** | Apache 2.0 (Google LLC) |
| **Licencia swegemma / adk-submission** | Heredan la licencia Apache 2.0 del concurso oficial de Kaggle |

---

## 2. Paquetes y Versiones Instaladas

Los cuatro componentes clave del arnés fueron descargados desde la API de Kaggle con sus metadatos
dist-info verificados:

1. **`swegemma` (v0.2.7):**
   * Archivo: `swegemma-0.2.7-py3-none-any.whl` (117 587 bytes).
   * Entry point CLI: `swegemma = swegemma.cli:main`.
   * Rol: Motor de evaluación de dos contenedores, ejecución de pruebas de verificación y scoring.
2. **`adk-submission` (v0.2.12):**
   * Archivo: `adk_submission-0.2.12-py3-none-any.whl` (65 642 bytes).
   * Rol: Compilador declarativo de envíos YAML a árboles `BaseAgent` de Google ADK sin `importlib`.
3. **`adk-eval-core` (v0.1.0):**
   * Archivo: `adk_eval_core-0.1.0-py3-none-any.whl` (90 060 bytes).
   * Rol: Infraestructura de sandbox Docker/Subprocess, seguimiento de presupuestos y trazas ATIF.
4. **`google-adk` (v1.36.1):**
   * Archivo: `google_adk-1.36.1-py3-none-any.whl` (2 877 731 bytes).
   * Rol: Framework subyacente de agentes Google Agent Development Kit.

---

## 3. Instalación en Entorno Virtual Aislado (Fuera del Repositorio)

Para no contaminar el entorno de desarrollo principal del proyecto ni versionar binarios pesados en git,
el arnés se instaló en una ruta externa: `C:\Users\herre\harness_venv` con CPython 3.12.14.

### 3.1 Creación del entorno

```powershell
# Creación con uv en directorio externo al workspace
uv venv "C:\Users\herre\harness_venv" --python 3.12
```

### 3.2 Descarga e instalación de ruedas (wheels)

```powershell
# Instalación de las ruedas oficiales y sus 162 dependencias
uv pip install --python "C:\Users\herre\harness_venv\Scripts\python.exe" `
  google_adk-1.36.1-py3-none-any.whl `
  adk_eval_core-0.1.0-py3-none-any.whl `
  adk_submission-0.2.12-py3-none-any.whl `
  swegemma-0.2.7-py3-none-any.whl
```

### 3.3 Verificación de la CLI

```powershell
# Comprobación de la CLI de swegemma
C:\Users\herre\harness_venv\Scripts\python.exe -m swegemma.cli eval --help
```
Output: `usage: swegemma eval [-h] --tasks TASKS --snapshots-dir SNAPSHOTS_DIR ...` (código de salida 0).

---

## 4. Construcción de la Imagen Docker de Sandbox (`swebench-sandbox:latest`)

El arnés ejecuta los entornos de agente y verificación dentro de contenedores herméticos basados en
la imagen `swebench-sandbox:latest` (`HARNESS § 4.1`).

### 4.1 Comando de construcción e imagen resultante

A partir de los archivos oficiales descargados de Kaggle (`docker/Dockerfile.public`, `docker/imp.py`,
`docker/telnetlib.py` y `wheels/` con las 124 ruedas de dependencias públicas):

```powershell
# Contexto preparado en data/build_sandbox (ignorado por git)
docker build -t swebench-sandbox:latest experiments/gemma_developer_agent/data/build_sandbox
```

* **ID de la imagen construida:** `2eae82eab1fe` (manifest sha256:2eae82eab1fe, config sha256:35f1e24bbd02).
* **Tamaño en Docker:** 453 MB en disco (124 MB comprimido).
* **Imagen base:** `python:3.13-slim`.

### 4.2 Corrida piloto de 3 tareas y reconstrucción del entorno (Decisión b')

Se ejecutó la prueba piloto sobre 3 tareas (`fastapi_14077`, `fastapi_11194`, `rich_3061`) para validar la Fase 2 sin agente (`--skip-agent-patch`) y se aplicó la decisión (b') del orquestador en el PR #110 para subsanar los defectos de entorno observados:

1. **Host Windows y Codificación Unicode (`PYTHONUTF8=1`):**
   * El log de `rich_3061` contiene caracteres de formato de consola Unicode. `verification.py:420` abría archivos temporales sin declarar `encoding="utf-8"`, lo que bajo la configuración por defecto de Windows lanzaba `UnicodeEncodeError: 'charmap' codec can't encode...`.
   * Solución: Se ejecuta con `$env:PYTHONUTF8="1"`, activando el modo UTF-8 de CPython de forma estricta sin parchear el código del arnés. `rich_3061` ejecuta y reporta sus resultados sin error.

2. **Reconstrucción del Entorno de Tests con PyPI Fijado (Decisión b'):**
   * `fastapi_11194` y `fastapi_14077` presentaban inicialmente `ModuleNotFoundError: No module named 'typing_inspection'`, omitido en los 124 wheels del concurso pero requerido por `pydantic>=2.13.4` bajo Python 3.13.
   * Adicionalmente, el wheelhouse incluía una rueda fork `starlette-1.6.0-py3-none-any.whl` (que eliminó `on_startup` de `Router.__init__`, rompiendo FastAPI 0.116) y omitía dependencias de test (`h11`, `dirty-equals`).
   * Se fijaron las ruedas estrictas en `experiments/gemma_developer_agent/docs/desviaciones_entorno_wheels.lock` (`typing-inspection==0.4.4`, `h11==0.16.0`, `dirty-equals==0.11`, `anyio==4.14.2`, `starlette==0.48.0`).
   * Al reconstruir la imagen y el caché de inyección, el contenedor evalúa en aislamiento hermético absoluto (`network_mode="none"`).

3. **Resultados Empíricos de Validación (Fail-to-Pass):**
   * **`fastapi_14077` (INVÁLIDA):** Sin parche pasa los 3 tests (3 passed en 0.28s, exit code 0). No discrimina la solución del agente; el control vacío pasa sin cambios.
   * **`fastapi_11194` (VÁLIDA):** Sin parche falla genuinamente por el defecto reportado (`AssertionError: assert 422 == 200`, 2 failed, 2 passed, exit code 1). Con el parche dorado pasa al 100% (4 passed en 0.30s, exit code 0).
   * **`rich_3061` (VÁLIDA):** Sin parche falla en las aserciones por el método faltante (`AttributeError: 'Text' object has no attribute 'extend_style'`, 12 failed, 100 passed, exit code 1). Con el parche dorado pasa al 100% (112 passed en 0.29s, exit code 0).

---

## 5. Reporte de Tamaño de Snapshots de la Competencia

De acuerdo con la inspección realizada a través de la API oficial de Kaggle (`gemma-4-developer-agent`):
* **Total de snapshots para las 129 tareas:** 129 archivos tarball `.tgz`.
* **Tamaño total acumulado:** **20.02 GB** (21 502 446 736 bytes).
* **Snapshots locales descargados en `data/snapshots/`:** 3 tareas del piloto (515.8 MB).

---

## 6. Partición Estratificada y Regla Leave-One-Repo-Out

El script `scripts/kaggle_split.py` implementa dos reglas deterministas (stdlib pura) auditadas en `tests/test_kaggle_split.py`:
1. `temporal_stratified`: División temporal proporcional por cuotas de Hamilton por repositorio ($N \in \{24, 32, 40\}$).
2. `leave_one_repo_out`: Reserva la totalidad de un repositorio (`--held-out-repo <nombre>`) como conjunto de prueba de generalización fuera de distribución, asignando los demás repositorios al entrenamiento.


