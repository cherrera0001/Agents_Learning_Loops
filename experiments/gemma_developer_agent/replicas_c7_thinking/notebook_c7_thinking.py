# Variante THINKING (razonamiento breve y silencioso) de la condición 7 (WIP, sin correr).
#
# Copia del paquete replicas_c7 con dos cambios trazables: (a) configs/sampling.yaml con
# thinking_budget 1024 e include_thoughts false (la condicion 7 usa 4096/true); (b)
# prompts/system.md gana los hechos de herramientas gratis (submit_patch/get_status cuestan
# cero llamadas) y reglas de disciplina de presupuesto. Pensado para medir si el razonamiento
# largo y visible de la condicion 7 paga su coste de reloj. Huella de configuracion: 9d0db7b946e7
# (original 0f52de0b84cb). Mismas 20 tareas, mismos topes. NO se ha subido ni corrido.
#
# Se sube a un notebook de Kaggle con GPU L4×4 (ver README.md de esta carpeta). Guion de
# celdas: ``armar_notebook.py`` lo parte en celdas, inserta la guarda de versiones del arnés
# (scripts/kaggle_arnes.py) y escribe ``notebook_c7.ipynb`` + ``kernel-metadata.json``.
#
# Qué mide: una pasada de la condición 7 (el zip `submission_i_razona.zip`, huella 65a02160…,
# fingerprint de configuración 0f52de0b84cb) sobre una lista fija de tareas, y escribe los
# resultados por tarea con marca de tiempo. No cambia nada entre réplicas: la etiqueta de
# salida sale del reloj, no de la configuración.
#
# Frontera de datos: no se versiona ni se incrusta contenido de la competencia. El kit se
# copia dentro de Kaggle desde la entrada de la competencia (sample_submission) y se le aplican
# tres valores propios (eval_config.yaml entero y dos claves de configs/sampling.yaml); la
# huella de configuración se comprueba contra la del zip enviado antes de cargar el modelo.
# Los identificadores de las 19 tareas del 9/19 original NO se pudieron recuperar (ver
# tareas_c7.json): el dueño las pega en la celda «tareas» o sube el archivo como entrada.
#
# ruff: noqa: E402, E501, E741, SIM115
#   Es un guion de notebook con celdas: los imports van donde va cada celda, las líneas largas
#   son salidas y mensajes literales, y ``l`` es el nombre de las líneas de los logs en el
#   patrón heredado de los notebooks rescatados. E501: los literales ``_SYSTEM_THINK`` y
#   ``_SAMPLING_THINK`` son byte a byte y no admiten cortes.

# ==== CELDA: guardia ====
import os
from pathlib import Path


def directorios_con(raiz, coincide, profundidad):
    base = raiz.rstrip("/").count("/")
    hallados = []
    for dirpath, dirs, files in os.walk(raiz, followlinks=True):
        if dirpath.count("/") - base >= profundidad:
            dirs[:] = []
        if coincide(dirpath, files):
            hallados.append(dirpath)
            dirs[:] = []
    return sorted(hallados)


def unico(nombre, hallados):
    print("GUARDIA", nombre, hallados)
    if len(hallados) != 1:
        motivo = "no se encontro" if not hallados else "hay mas de uno"
        raise RuntimeError(f"GUARDIA {nombre}: {motivo}; se detiene antes de gastar cuota")
    return hallados[0]


RAIZ = "/kaggle/input"
print("GUARDIA entradas:", sorted(os.listdir(RAIZ)))
for _d, _dirs, _fs in os.walk(RAIZ, followlinks=True):
    _nivel = _d.count("/") - RAIZ.count("/")
    if _nivel >= 6:
        _dirs[:] = []
    if "snapshots" in _dirs:
        _dirs.remove("snapshots")
    if "graphs" in _dirs:
        _dirs.remove("graphs")
    print("GUARDIA arbol", _nivel, _d, len(_fs), "archivos")
con_whl = directorios_con(RAIZ, lambda d, fs: any(f.endswith(".whl") for f in fs), 4)
W = unico(
    "ruedas del arnes",
    [d for d in con_whl if any(f.startswith("swegemma-") and f.endswith(".whl") for f in os.listdir(d))],
)
D = unico("datos", directorios_con(RAIZ, lambda d, fs: "tasks.jsonl" in fs, 3))
M = unico(
    "modelo",
    directorios_con(RAIZ, lambda d, fs: "config.json" in fs and "gemma-4-31b-it-qat-w4a16-ct" in d, 8),
)
print("GUARDIA ruedas:", len([f for f in os.listdir(W) if f.endswith(".whl")]), W)
faltan = [
    x
    for x in ("tasks.jsonl", "sample_submission", "graphs", "embeddings", "snapshots", "wheels")
    if not os.path.exists(os.path.join(D, x))
]
if faltan:
    raise RuntimeError(f"GUARDIA datos: faltan {faltan}; se detiene antes de gastar cuota")
if not any(f.endswith((".safetensors", ".bin")) for f in os.listdir(M)):
    raise RuntimeError("GUARDIA modelo: el directorio no tiene pesos; se detiene antes de gastar cuota")
print("GUARDIA completa: ruedas, datos (con graphs, embeddings y snapshots) y modelo localizados")

# ==== CELDA: instalacion ====
import contextlib
import glob
import importlib
import os
import subprocess
import sys

# Entorno offline de vLLM/LiteLLM (patron de las sesiones rescatadas).
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
os.environ["TRANSFORMERS_NO_TF"] = "1"
os.environ["VLLM_WORKER_MULTIPROC_METHOD"] = "spawn"
os.environ["VLLM_MEMORY_PROFILER_ESTIMATE_CUDAGRAPHS"] = "1"
os.environ["VLLM_ENGINE_READY_TIMEOUT_S"] = "1200"
os.environ["VLLM_NO_USAGE_STATS"] = "1"
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

WHEELHOUSE_DIR = Path(W)

# Quitar hooks .pth de cutlass rotos si existen.
for pth_pattern in (
    "/usr/local/lib/python*/dist-packages/*cutlass*.pth",
    "/usr/local/lib/python*/site-packages/*cutlass*.pth",
):
    for pth in glob.glob(pth_pattern):
        with contextlib.suppress(OSError):
            os.unlink(pth)

# Restaurar nombres PEP 440 '+cu128' que las subidas de Kaggle pelan.
tmp_whl = Path("/tmp/wheelhouse")
tmp_whl.mkdir(parents=True, exist_ok=True)
for w in WHEELHOUSE_DIR.glob("*.whl"):
    if "cutlass" in w.name.lower():
        continue
    target_name = w.name.replace("cu128", "+cu128") if ("cu128" in w.name and "+" not in w.name) else w.name
    target = tmp_whl / target_name
    if not target.exists():
        os.symlink(w, target)

wheels = sorted(str(w) for w in tmp_whl.glob("*.whl"))
print("INSTALACION ruedas:", len(wheels))
_proceso = subprocess.run(
    [sys.executable, "-m", "pip", "install", "-q", "--no-deps", "--force-reinstall", *wheels],
    capture_output=True,
    text=True,
)
if _proceso.returncode != 0:
    Path("/kaggle/working").mkdir(exist_ok=True)
    Path("/kaggle/working/instalacion_error.txt").write_text(_proceso.stderr[-4000:], encoding="utf-8")
    raise RuntimeError("INSTALACION: pip fallo; se detiene antes de gastar cuota")
importlib.invalidate_caches()

_fallidas = []
for _rueda in sorted(f for f in os.listdir(W) if f.endswith(".whl")):
    _nombre = _rueda.split("-")[0]
    try:
        importlib.metadata.version(_nombre)
    except importlib.metadata.PackageNotFoundError:
        _fallidas.append(_nombre)
print("INSTALACION comprobacion:", "todas instaladas" if not _fallidas else f"faltan {_fallidas}")
if _fallidas:
    raise RuntimeError(f"INSTALACION: {_fallidas} no quedaron instaladas; se detiene antes de la GPU")

# ==== CELDA: versiones ====
# ARMAR_NOTEBOOK_INSERTA_AQUI_LA_GUARDA_DE_VERSIONES

# ==== CELDA: kit ====
import base64
import hashlib
import shutil
import time

WORKING_DIR = Path("/kaggle/working")
KIT_ORIGEN = Path(D) / "sample_submission"
AGENT_DIR = WORKING_DIR / "c7_submission"
if AGENT_DIR.exists():
    shutil.rmtree(AGENT_DIR)
shutil.copytree(KIT_ORIGEN, AGENT_DIR)
# El zip enviado de la condicion 7 no lleva adaptadores (registry sub-005): el sample_submission
# de la competencia si los trae (directorio adapters/ y dos lineas "adapter:"), y la huella los contaria.
shutil.rmtree(AGENT_DIR / "adapters", ignore_errors=True)
for _f in ("agent.yaml", "sub_agents/code_analyzer.yaml"):
    _p = AGENT_DIR / _f
    _lineas = _p.read_text(encoding="utf-8").splitlines(keepends=True)
    _p.write_text("".join(l for l in _lineas if not l.startswith("adapter:")), encoding="utf-8")

# La condición 7 son exactamente tres valores distintos del kit original (registry.json,
# sub-005): eval_config.yaml (60 llamadas, 4,5 min) e include_thoughts: true en el muestreo.
(AGENT_DIR / "eval_config.yaml").write_text(
    "evaluation:\n  timeout_seconds: 60\n  max_tool_calls: 60\n  max_time_minutes: 4.5\n  max_turns: 100\n",
    encoding="utf-8",
)
_SAMPLING_THINK = 'temperature: 0.2\ntop_p: 0.95\nmax_output_tokens: 8192\nthinking_config:\n  thinking_budget: 1024\n  include_thoughts: false\n'


(AGENT_DIR / "configs" / "sampling.yaml").write_text(_SAMPLING_THINK, encoding="utf-8")


# La disciplina de presupuesto va en el bloque de instrucciones (prompts/system.md).
# Contenido idéntico byte a byte a kit_thinking/prompts/system.md; armar_notebook_thinking.py lo verifica.
_SYSTEM_THINK = 'You are an expert autonomous software engineer assigned to resolve an issue in a repository efficiently and decisively.\n\n## Core Objective: Fast, Minimal, and Precise Fixes\nAim to understand, resolve, and submit the fix in the minimum number of tool calls (under 8–10 turns). Move directly from the problem statement to the relevant files, apply the solution, verify with a targeted test, and submit.\n\n## Free Tools and Budget Discipline (mandatory)\n\nFacts about your tools (use them):\n\n- `submit_patch()` and `get_status()` cost **zero** tool calls. Call `get_status()` when a\n  task starts and after any long exploration; both remain available even at zero remaining\n  calls, as long as wall-clock time remains.\n- Thinking burns your wall-clock budget. Reason briefly, then act. Never re-read a file or\n  file region you have already read.\n- Never leave scratch or reproduction files in `/workspace` — write them to `/tmp` only.\n  Files under `/workspace` become part of your patch.\n- The harness recovers your patch automatically at timeout even if you never call\n  `submit_patch()`, so always leave a real edit in place.\n- If you have located the edit site and time remains, edit **now**. Run a single targeted\n  verification, then call `submit_patch()` as your final action.\n\n## Workflow\n\n### 1. Identify Target Files Immediately\n- Extract filenames, functions, classes, CLI subcommands, or error messages directly from the problem statement.\n- Read only the specific target files and lines using `read_file` or search tools. Do not wander across unrelated files.\n- If the problem statement does not provide explicit file paths, use `search_similar_code` with keywords from the error message to locate relevant files efficiently, rather than running `find` or `grep` across the entire repo.\n\n### 2. Implement the Solution Directly\n- Apply the minimal necessary fix or feature directly to the source files using `edit_file` or `write_file`.\n- Strictly adhere to specified error strings, exception types, HTTP status codes, and API signatures.\n- For documentation code tasks (e.g. FastAPI), edit executable code under `docs_src/`.\n\n### 3. Run Targeted Tests Only (Existing Tests May Be Broken)\n- **Run ONLY Targeted Tests**: Run only the specific test file or test method directly verifying the bug or feature you modified (e.g. `pytest tests/test_target.py -k test_feature` or `python3 -m unittest tests.test_target`).\n- **Be Aware That Existing Tests May Be Broken**: Many repositories contain pre-existing test breakages, missing test data fixtures (e.g. `/test_data`), or environment import errors unrelated to your task.\n- **Do NOT Attempt to Fix Existing Tests**: If an existing test fails due to pre-existing repository issues or missing fixtures, IGNORE IT. Never spend turns attempting to repair pre-existing test failures, create test stubs, or alter test code.\n- **STRICT RULE: NEVER Run Bare Pytest or Full-Repo Sweeps**: NEVER run bare `pytest`, `pytest .`, `python3 -m unittest discover`, or full-repo test suites without specifying a target file. Full test suites take several minutes, cause catastrophic timeouts, and exhaust your turn and time budgets.\n- If you need to locate the test file, find it explicitly with `find tests -name "*<name>*.py"` instead of running the test runner across the repo.\n\n### 4. Immediate Patch Submission\n- Once your targeted test passes:\n  1. Call `submit_patch` immediately.\n  2. Verify `patch_size > 0` and `files_changed > 0`.\n  3. Output a short summary of the fix to end the session.\n\n## Anti-Patterns to Avoid\n- **NEVER modify, create, or delete test files** (`*_test.py`, `test_*.py`, or anything under `tests/`). All changes must be to source implementation files. Modifying tests results in an automatic evaluation failure.\n- **NEVER run full repository test suites** (e.g., bare `pytest` or `pytest .`) — always specify the exact test file path.\n- **NEVER attempt to fix or repair existing tests or pre-existing repository breakages** — your task is strictly to implement the fix for the reported issue in source code.\n- **NEVER search outside `/workspace`** for source files or packages (e.g., `/usr/local/lib/`, `/wheels/`, `/opt/`). All repository code and test dependencies are pre-installed. If `ModuleNotFoundError` occurs during test runs, focus on fixing code under `/workspace`, not looking for missing system packages.\n- Do NOT spend turns running broad exploratory searches if the file path or symbol is obvious.\n- Do NOT refactor or reformat unrelated functions or files.\n- Do NOT conclude without submitting a non-empty patch (`patch_size > 0`). Every task requires concrete source modifications. Concluding that the codebase is already clean without making changes is an anti-pattern.\n'


(AGENT_DIR / "prompts" / "system.md").write_text(_SYSTEM_THINK, encoding="utf-8")


def huella_config(directorio):
    """Fingerprint del manuscrito §«Data availability»: SHA-256 de los base64 de los archivos,
    ordenados como cadenas y concatenados sin nombres ni separadores, 12 hex."""
    partes = []
    for raiz, _, archivos in os.walk(directorio):
        for a in archivos:
            partes.append(base64.b64encode((Path(raiz) / a).read_bytes()).decode())
    return hashlib.sha256("".join(sorted(partes)).encode()).hexdigest()[:12]


HUELLA = huella_config(AGENT_DIR)
print(
    "HUELLA configuracion:",
    HUELLA,
    "(variante thinking: 9d0db7b946e7; condicion 7: 0f52de0b84cb)",
)
if HUELLA != "9d0db7b946e7":
    raise RuntimeError("GUARDIA configuracion: no reproduce la variante thinking 9d0db7b946e7; se detiene antes de gastar cuota")

# ==== CELDA: tareas ====
# Las 19 tareas del 9/19 original no se recuperan desde el repositorio (tareas_c7.json).
# El dueño pega aquí los identificadores exactos (o sube tareas_c7.json como entrada y se leen).
IDS_TAREAS_C7 = [
    "rich_3894",
    "rich_3535",
    "rich_3772",
    "rich_3278",
    "rich_4076",
    "rich_3905",
    "rich_3472",
    "rich_4079",
    "rich_3470",
    "rich_3180",
    "rich_3130",
    "rich_3486",
    "rich_3938",
    "rich_3061",
    "rich_3521",
    "rich_3782",
    "rich_3296",
    "rich_3043",
    "rich_3675",
    "rich_3953",
]  # sustituto fijado 2026-10-16 (ver tareas_c7.json)

import json as _json

_candidatas = [Path(r) / a for r, _, fs in os.walk(RAIZ) for a in fs if a == "tareas_c7.json"]
if not IDS_TAREAS_C7 and len(_candidatas) == 1:
    IDS_TAREAS_C7 = _json.loads(_candidatas[0].read_text(encoding="utf-8"))["ids_19"]
elif not IDS_TAREAS_C7 and len(_candidatas) > 1:
    raise RuntimeError(f"TAREAS: hay {len(_candidatas)} archivos tareas_c7.json; se exige exactamente uno")
if not IDS_TAREAS_C7:
    raise RuntimeError(
        "TAREAS: faltan los identificadores de las 19 tareas; se detiene antes de gastar cuota"
    )
if len(IDS_TAREAS_C7) != 20:
    raise RuntimeError(f"TAREAS: se esperan 20 identificadores y hay {len(IDS_TAREAS_C7)}")

from swegemma.models import load_tasks

TASKS_PATH = Path(D) / "tasks.jsonl"
DATA_DIR = Path(D)
GRAPH_DIR = DATA_DIR / "graphs"
EMBEDDINGS_DIR = DATA_DIR / "embeddings"
SANDBOX = "subprocess"
tasks = load_tasks(str(TASKS_PATH))
por_id = {t.instance_id: t for t in tasks}
faltan = [i for i in IDS_TAREAS_C7 if i not in por_id]
if faltan:
    raise RuntimeError(f"TAREAS: {len(faltan)} identificadores no estan en tasks.jsonl")
TAREAS = [por_id[i] for i in IDS_TAREAS_C7]
ETIQUETA = os.environ.get("ETIQUETA", "c7_" + time.strftime("%Y%m%dT%H%MZ", time.gmtime()))
print("TAREAS:", len(TAREAS), "| ETIQUETA:", ETIQUETA)

# ==== CELDA: servidor ====
import atexit
import subprocess
import time

print(
    subprocess.run(
        ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv"], capture_output=True, text=True
    ).stdout
)
T_SERVIDOR = time.time()

try:
    import litellm
    import torch
    from adk_submission import VllmConfig, VllmServer, discover_adapters, discover_declared_models
    from swegemma.config import ALLOWED_ADAPTER_EXTENSIONS

    litellm.drop_params = True

    TARGET_MODEL_NAME = "gemma-4-31b-it-qat-w4a16-ct"
    MODEL_PATH = Path(M)
    INFERENCE_API_KEY = "EMPTY"

    def _normalizar_modelo(nombre):
        valor = nombre.strip().lower()
        for prefijo in ("openai/", "google/", "hosted_vllm/", "custom/"):
            if valor.startswith(prefijo):
                valor = valor[len(prefijo) :]
        return valor

    _declarados = sorted(discover_declared_models(AGENT_DIR, normalize_fn=_normalizar_modelo))
    if len(_declarados) != 1:
        raise RuntimeError(
            f"MODELO: la condicion declara {len(_declarados)} modelos {_declarados}; se exige exactamente uno"
        )
    declared_model = _declarados[0]
    adapters = discover_adapters(str(AGENT_DIR), adapter_extensions=ALLOWED_ADAPTER_EXTENSIONS)

    gpu_count = torch.cuda.device_count() if torch.cuda.is_available() else 1
    tp_size = 4 if gpu_count >= 4 else (2 if gpu_count >= 2 else 1)

    vllm_cfg = VllmConfig(
        model=str(MODEL_PATH),
        port=8000,
        host="127.0.0.1",
        tool_call_parser="gemma4",
        reasoning_parser="gemma4",
        max_model_len=32768,
        dtype="bfloat16" if (torch.cuda.is_available() and torch.cuda.is_bf16_supported()) else "auto",
        gpu_memory_utilization=0.90,
        enable_auto_tool_choice=True,
        enable_lora=True,
        max_loras=8,
        max_lora_rank=128,
        tensor_parallel_size=tp_size,
        startup_timeout=60 * 20,
    )
    server_instance = VllmServer(vllm_cfg, adapter_manifest=adapters)
    server_instance.start()
    atexit.register(server_instance.stop)
    print(f"vLLM server started on {server_instance.base_url} (tp={tp_size})")

    models = server_instance.create_model_registry(
        aliases=[declared_model, TARGET_MODEL_NAME],
        model_prefix="openai/",
        api_key=INFERENCE_API_KEY,
    )
except BaseException as exc:
    import glob as _glob
    import tempfile

    print("SERVIDOR FALLO", type(exc).__name__, str(exc)[:500])
    salida_exc = getattr(exc, "output", None)
    if salida_exc:
        lineas_exc = str(salida_exc).splitlines()
        (WORKING_DIR / "servidor_error_salida.txt").write_text(
            chr(10).join(lineas_exc[-200:]), encoding="utf-8"
        )
        for l in lineas_exc[-60:]:
            if any(
                k in l
                for k in ("Error", "error", "ERROR", "Traceback", "raise", "OOM", "memory", "Killed", "CUDA")
            ):
                print("LOG", l[:300])
    rutas = []
    try:
        rutas.append(server_instance.log_path)
    except Exception:
        rutas += sorted(_glob.glob(tempfile.gettempdir() + "/*.log"))
    for i, ruta in enumerate(rutas[:3]):
        try:
            lineas = open(ruta, encoding="utf-8", errors="replace").read().splitlines()
            (WORKING_DIR / f"servidor_error_{i}.txt").write_text(
                chr(10).join(lineas[-200:]), encoding="utf-8"
            )
            for l in lineas[-60:]:
                if any(
                    k in l
                    for k in (
                        "Error",
                        "error",
                        "ERROR",
                        "Traceback",
                        "raise",
                        "OOM",
                        "memory",
                        "Killed",
                        "CUDA",
                    )
                ):
                    print("LOG", l[:300])
        except Exception as e2:
            print("sin log", ruta, type(e2).__name__)
    raise

CARGA_S = round(time.time() - T_SERVIDOR, 1)
print("MEDIDA carga_modelo_segundos", CARGA_S)

# ==== CELDA: evaluacion ====
# Una pasada, secuencial, con los topes que fija el eval_config de la condición y dos cortes
# de seguridad del #182: tope duro por tarea (el arnés 0.2.11 puede dejar una tarea colgada)
# y tope de sesión con margen final. Sin enganches de registro ni captura de peticiones:
# instrumentación que la réplica no necesita.
import asyncio
import concurrent.futures
import threading

import yaml
from google.adk.agents.context_cache_config import ContextCacheConfig
from google.adk.apps._configs import EventsCompactionConfig
from swegemma.config import EvalConfig, build_submission_limits
from swegemma.evaluate import Evaluator

TOPE_SESION_SEGUNDOS = float(os.environ.get("TOPE_SESION_SEGUNDOS", str(150 * 60)))
MARGEN_FINAL_SEGUNDOS = float(os.environ.get("MARGEN_FINAL_SEGUNDOS", str(10 * 60)))
TOPE_TAREA_SEGUNDOS = float(os.environ.get("TOPE_TAREA_SEGUNDOS", str(900)))
MARGEN_TAREA_COLGADA_SEGUNDOS = float(os.environ.get("MARGEN_TAREA_COLGADA_SEGUNDOS", str(30)))


class TareaColgada(Exception):
    pass


def inicio_de_sesion():
    try:
        with open("/proc/self/stat") as f:
            campos = f.read().rsplit(")", 1)[1].split()
        with open("/proc/stat") as f:
            btime = next(float(l.split()[1]) for l in f if l.startswith("btime"))
        return btime + float(campos[19]) / os.sysconf("SC_CLK_TCK")
    except Exception:
        return time.time()


def run_sync(coro_or_fn, *args, **kwargs):
    fn = (lambda: coro_or_fn(*args, **kwargs)) if callable(coro_or_fn) else (lambda: coro_or_fn)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is not None and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(lambda: asyncio.run(fn())).result()
    return asyncio.run(fn())


def con_tope_tarea(fn, *args, **kwargs):
    caja = {}
    hilo = threading.Thread(target=lambda: _corre(caja, fn, *args, **kwargs), daemon=True)
    hilo.start()
    hilo.join(TOPE_TAREA_SEGUNDOS)
    if hilo.is_alive():
        raise TareaColgada(hilo)
    if "err" in caja:
        raise caja["err"]
    return caja["ok"]


def _corre(caja, fn, *args, **kwargs):
    try:
        caja["ok"] = run_sync(fn, *args, **kwargs)
    except BaseException as exc:
        caja["err"] = exc


def servidor_sano():
    try:
        import urllib.request

        with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=10) as r:
            return r.status == 200
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"


def clase_fallo(res):
    if getattr(res, "resolved", False):
        return "resuelta"
    error = str(getattr(res, "error_message", "") or "")
    if "context" in error.lower() or "maximum context length" in error.lower():
        return "rechazo_contexto"
    patch = str(getattr(res, "generated_patch", "") or "")
    agotado = getattr(res, "agent_budget_exhausted", None) or getattr(res, "timed_out", None)
    if agotado:
        return "tiempo_agotado_con_parche" if patch.strip() else "tiempo_agotado_sin_parche"
    if not patch.strip():
        return "sin_parche"
    return "pruebas_fallan"


T_SESION = inicio_de_sesion()
T_TAREAS = time.time()
seccion = yaml.safe_load((AGENT_DIR / "eval_config.yaml").read_text(encoding="utf-8"))
seccion = seccion.get("evaluation", seccion)
turnos = seccion.get("max_turns", seccion.get("max_llm_calls"))
limits, gen_constraints = build_submission_limits()
eval_config = EvalConfig(
    tasks_path=TASKS_PATH,
    snapshots_dir=DATA_DIR / "snapshots",
    results_dir=WORKING_DIR / "results" / ETIQUETA,
    submission_dir=AGENT_DIR,
    models=models,
    sandbox=SANDBOX,
    timeout_seconds=int(seccion.get("timeout_seconds", 300)),
    max_time_minutes=float(seccion.get("max_time_minutes", 60.0)),
    max_tool_calls=int(seccion.get("max_tool_calls", 100)),
    max_turns=int(turnos) if turnos is not None else None,
    limits=limits,
    generation_constraints=gen_constraints,
    adapter_manifest=adapters,
    context_cache_config=ContextCacheConfig(min_tokens=2048, ttl_seconds=1800, cache_intervals=10),
    events_compaction_config=EventsCompactionConfig(
        compaction_interval=15, overlap_size=2, token_threshold=14336, event_retention_size=5
    ),
    graph_dir=GRAPH_DIR,
    embeddings_dir=EMBEDDINGS_DIR,
    wheels_dir=DATA_DIR / "wheels",
    verbose=False,
)
evaluator = Evaluator(eval_config)

RESUMEN = {
    "etiqueta": ETIQUETA,
    "huella_config": HUELLA,
    "tareas": len(TAREAS),
    "carga_modelo_segundos": CARGA_S,
    "tope_sesion_segundos": TOPE_SESION_SEGUNDOS,
    "filas": [],
}
cortado_por = None
for idx, task in enumerate(TAREAS, start=1):
    if time.time() - T_SESION > TOPE_SESION_SEGUNDOS - MARGEN_FINAL_SEGUNDOS:
        cortado_por = "sesion"
        print("CORTE por tope de sesion en tarea", idx, flush=True)
        break
    salud = servidor_sano()
    if salud is not True:
        cortado_por = f"servidor: {salud}"
        print("CORTE por servidor caido en tarea", idx, salud, flush=True)
        break
    t0 = time.time()
    try:
        res = con_tope_tarea(evaluator.evaluate_task, task=task, task_index=idx, total_tasks=len(TAREAS))
        fila = {
            "id": task.instance_id,
            "resuelta": bool(getattr(res, "resolved", False)),
            "clase": clase_fallo(res),
            "segundos_reloj": round(time.time() - t0, 1),
            "llamadas_herramientas": getattr(res, "tool_calls", None),
            "llamadas_modelo": getattr(res, "total_llm_calls", None),
        }
    except TareaColgada as colgada:
        fila = {
            "id": task.instance_id,
            "resuelta": False,
            "clase": "tarea_colgada",
            "segundos_reloj": round(time.time() - t0, 1),
            "par_faltante": True,
        }
        time.sleep(MARGEN_TAREA_COLGADA_SEGUNDOS)
        if colgada.args[0].is_alive():
            cortado_por = "tarea_colgada_viva"
            RESUMEN["filas"].append(fila)
            print("CORTE por tarea colgada que no murio en el margen", idx, flush=True)
            break
    RESUMEN["filas"].append(fila)
    print("TAREA", idx, fila["id"], fila["clase"], fila["segundos_reloj"], flush=True)

RESUMEN["cortado_por"] = cortado_por
RESUMEN["sesion_segundos"] = round(time.time() - T_SESION, 1)
(WORKING_DIR / f"salida__{ETIQUETA}.json").write_text(
    __import__("json").dumps(RESUMEN, ensure_ascii=False, indent=1), encoding="utf-8"
)
_res = WORKING_DIR / "results" / ETIQUETA / "task_results.jsonl"
if _res.exists():
    shutil.copy(_res, WORKING_DIR / f"task_results_{ETIQUETA}.jsonl")
print(
    "LISTO",
    ETIQUETA,
    "resueltas",
    sum(1 for f in RESUMEN["filas"] if f["resuelta"]),
    "de",
    len(RESUMEN["filas"]),
)
