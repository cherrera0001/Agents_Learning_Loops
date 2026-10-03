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
