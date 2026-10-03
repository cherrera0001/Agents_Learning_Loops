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

### 4.2 Corrida piloto de 3 tareas sin parche (`--skip-agent-patch`)

Se ejecutó una prueba piloto sobre 3 tareas (`fastapi_14077`, `fastapi_11194`, `rich_3061`) con
concurrencia 1 para validar la interacción entre el arnés en el host y los contenedores Docker:

```powershell
$env:PYTHONIOENCODING="utf-8"
C:\Users\herre\harness_venv\Scripts\python.exe -m swegemma.cli eval `
  --tasks "experiments/gemma_developer_agent/data/tasks.jsonl" `
  --snapshots-dir "experiments/gemma_developer_agent/data/snapshots" `
  --results-dir "experiments/gemma_developer_agent/data/test_results_3" `
  --submission-dir "experiments/gemma_developer_agent/conditions/a_kit" `
  --skip-agent-patch --sandbox docker --concurrency 1 `
  --task-ids fastapi_14077 rich_3061 fastapi_11194
```

Resultados observados:
1. Docker levantó los contenedores correctamente en modo hermético (`network_mode="none"`, 2 vCPU, 4 GB).
2. `fastapi_14077` y `fastapi_11194`: los tests fallaron sin parche como se esperaba (exit code 2),
   arrojando `ModuleNotFoundError: No module named 'typing_inspection'` durante la recolección
   (dependencia no provista en el wheelhouse para Python 3.13).
3. `rich_3061`: el host Windows CP1252 lanzó un error de codificación al serializar el log Unicode
   en `verification.py:420`.
4. El análisis detallado y el contraste con el notebook `busyaprime` (119 tareas válidas) se
   registran en `experiments/gemma_developer_agent/calibracion/fase2_sin_parche.json`.

