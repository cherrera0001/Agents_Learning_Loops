# Entorno Local del Arnés Oficial (swegemma y adk-submission)

> **Estado del documento.** Vigente, con partes sin recibo que se rotulan como tales: el § 4.2 (la corrida
> piloto de tres tareas) **no tiene recibo** y sus causas de fallo no están establecidas, y la licencia del
> arnés está **pendiente de confirmar**. El entorno que cuenta para el experimento es el que fije el ensayo
> de notebook (pre-registro de la línea base A, sección A.1), no este entorno local. Mapa de documentos:
> [`README.md`](../README.md#12-mapa-de-documentos).

Este documento registra la procedencia, versiones, licencias y procedimiento de instalación del
arnés oficial de evaluación para el desafío Google Gemma 4 Developer Agent en un entorno virtual
aislado fuera del repositorio (`AGENTS.md`, `CONTRIBUTING.md`).

---

## 1. Procedencia y licencias

El arnés de evaluación no se distribuye a través del índice público PyPI (donde `swegemma`, `adk-submission`
y `adk-eval-core` retornan HTTP 404), sino mediante el dataset oficial mantenido por la organización de
la competencia en Kaggle.

| Atributo | Detalle (la fila de licencia de `swegemma` y `adk-submission` no está confirmada) |
|---|---|
| **Dataset de origen** | `metric/gemma-4-developer-agent-wheelhouse` (Kaggle Dataset) |
| **URL del dataset** | `https://www.kaggle.com/datasets/metric/gemma-4-developer-agent-wheelhouse` |
| **Mantenedor oficial** | Ryan Holbrook / Kaggle Competition Metrics (`metric`) |
| **Versión del dataset** | Versión 28 (última actualización: 2026-09-30) |
| **Licencia de la competencia** | Apache 2.0, según el campo `licenseName` de la API para la competencia `149921` (`kaggle_api_2026-10-02.json`) |
| **Licencia google-adk** | Apache 2.0 (Google LLC) |
| **Licencia swegemma / adk-submission** | **Pendiente de confirmar.** La licencia del concurso no se hereda al arnés: las reglas fijan la licencia de la solución ganadora (Rules § 1.6), no la del arnés. La confirma el dueño del repositorio en la página del dataset de Kaggle |

---

## 2. Paquetes y Versiones Instaladas

Los cuatro componentes clave del arnés se descargaron desde la API de Kaggle:

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
el arnés se instaló en un entorno virtual fuera del repositorio, que en los comandos siguientes se llama
`<harness_venv>`, con CPython 3.12.14. Los comandos son los que se usaron en un host Windows.

### 3.1 Creación del entorno

```powershell
# Creación con uv en un directorio externo al workspace
uv venv "<harness_venv>" --python 3.12
```

### 3.2 Descarga e instalación de ruedas (wheels)

```powershell
# Instalación de las ruedas oficiales y sus 162 dependencias
uv pip install --python "<harness_venv>\Scripts\python.exe" `
  google_adk-1.36.1-py3-none-any.whl `
  adk_eval_core-0.1.0-py3-none-any.whl `
  adk_submission-0.2.12-py3-none-any.whl `
  swegemma-0.2.7-py3-none-any.whl
```

### 3.3 Verificación de la CLI

```powershell
# Comprobación de la CLI de swegemma
<harness_venv>\Scripts\python.exe -m swegemma.cli eval --help
```
Salida: `usage: swegemma eval [-h] --tasks TASKS --snapshots-dir SNAPSHOTS_DIR ...` (código de salida 0). Sin
recibo versionado: es una comprobación de que la CLI arranca.

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

* **ID de la imagen construida:** `2eae82eab1fe` (manifest sha256:2eae82eab1fe, config sha256:35f1e24bbd02),
  según lo que este documento registró en su momento. **Sin recibo:** la imagen se identificó por un tag
  mutable (`latest`), y el orquestador señaló que la calibración cita una imagen Docker que no existe
  (comentario de #103, 2026-10-03). El PR #120 (fusionado el 2026-10-03) integró una variante local v2 del
  entorno, con una imagen identificada por su resumen; es un ensayo, no el entorno del experimento.
* **Tamaño en Docker:** 453 MB en disco (124 MB comprimido), con el mismo reparo.
* **Imagen base:** `python:3.13-slim`.

### 4.2 Corrida piloto de 3 tareas sin parche (`--skip-agent-patch`): **sin recibo**

> **Esta subsección no tiene recibo.** El registro de la corrida, el comando y la imagen que usó no están
> versionados con comprobación, y el orquestador encontró que los registros locales del arnés contradicen dos
> de sus tres resultados (comentario de #103 sobre la revisión del PR #113). Las causas de fallo que se
> atribuyen abajo son lo que se **reportó**, no un hecho establecido; las corridas posteriores muestran otra
> causa. No se usan para clasificar la validez de ninguna tarea.

Se reportó una prueba piloto sobre 3 tareas (`fastapi_14077`, `fastapi_11194`, `rich_3061`) con
concurrencia 1 para validar la interacción entre el arnés en el host y los contenedores Docker:

```powershell
$env:PYTHONIOENCODING="utf-8"
<harness_venv>\Scripts\python.exe -m swegemma.cli eval `
  --tasks "experiments/gemma_developer_agent/data/tasks.jsonl" `
  --snapshots-dir "experiments/gemma_developer_agent/data/snapshots" `
  --results-dir "experiments/gemma_developer_agent/data/test_results_3" `
  --submission-dir "experiments/gemma_developer_agent/conditions/a_kit" `
  --skip-agent-patch --sandbox docker --concurrency 1 `
  --task-ids fastapi_14077 rich_3061 fastapi_11194
```

Resultados reportados, sin recibo:
1. Docker levantó los contenedores en modo hermético (`network_mode="none"`, 2 vCPU, 4 GB).
2. `fastapi_14077` y `fastapi_11194`: las pruebas fallaron sin parche (código de salida 2), con
   `ModuleNotFoundError: No module named 'typing_inspection'` en la recolección, que se atribuyó a una
   dependencia ausente del wheelhouse para Python 3.13. Un control vacío posterior de `fastapi_11194` dio otro
   fallo de recolección (un `TypeError` en `Router.__init__`), cuya causa **no está establecida**.
3. `rich_3061`: se reportó un error de codificación cp1252 en un host Windows, al serializar el log, en
   `verification.py:420`. Sin recibo.
4. El contraste con las listas de un notebook de un competidor está en
   [`calibracion/fase2_sin_parche.json`](../calibracion/fase2_sin_parche.json), un registro fechado que **no
   es fuente de exclusiones** (pre-registro, sección A.4) y habla de 114 y 119 tareas válidas: esas cifras
   son de ese notebook ajeno, no una medición propia. La partición de `main` trabaja con las 129 tareas, y
   qué tareas son válidas está sin medir.

