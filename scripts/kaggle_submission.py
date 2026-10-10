"""Empaquetado, verificación y registro de envíos para el Code Track (Kaggle).

Valida que un submission.zip cumpla con el formato declarativo de adk-submission,
calcula su resumen SHA-256 de forma determinista y mantiene el registro versionado
en experiments/gemma_developer_agent/submissions/registry.json.

Uso:
    python -m scripts.kaggle_submission pack --condition-dir <dir> --output <archivo.zip>
    python -m scripts.kaggle_submission verify <archivo.zip> [--sin-resultados a,b | archivo.json]
                                               [--permitir-mencion a,b]
    python -m scripts.kaggle_submission register --zip <archivo.zip> --condition A --notes <texto>
    python -m scripts.kaggle_submission list
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import sys
import tempfile
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path

SCHEMA_VERSION = "kaggle-submission-registry/1"
COMPETITION_ID = 149921
COMPETITION_SLUG = "gemma-4-developer-agent"

DEFAULT_REGISTRY_PATH = (
    Path(__file__).resolve().parent.parent
    / "experiments"
    / "gemma_developer_agent"
    / "submissions"
    / "registry.json"
)

DEFAULT_A_KIT_DIR = (
    Path(__file__).resolve().parent.parent / "experiments" / "gemma_developer_agent" / "conditions" / "a_kit"
)

# Herramientas que el arnés del organizador registra. Fuente única: la usan `compile_with_adk` (las
# registra) y `check_tool_references` (decide qué nombres de una instrucción son herramientas conocidas).
HARNESS_TOOLS: tuple[str, ...] = (
    "run_command",
    "read_file",
    "edit_file",
    "write_file",
    "get_status",
    "submit_patch",
    "get_code_neighbors",
    "search_similar_code",
    "get_code_subgraph",
)

REQUIRED_ROOT_FILES = ["agent.yaml", "eval_config.yaml"]
RECOMMENDED_FILES = ["configs/sampling.yaml", "prompts/system.md"]

EXIT_OK = 0
EXIT_INPUTS = 2
EXIT_INVALID = 3


def compute_file_sha256(path: Path) -> str:
    """Calcula el hash SHA-256 de un archivo en bloques de 64 KB."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def find_declared_adapters(yaml_content: str) -> list[str]:
    """Extrae nombres de adaptadores declarados en un archivo agent.yaml sin dependencias externas."""
    adapters: list[str] = []
    # Buscar patrones 'adapter: <nombre>'
    for line in yaml_content.splitlines():
        line_clean = line.strip()
        if line_clean.startswith("adapter:"):
            parts = line_clean.split(":", 1)
            if len(parts) == 2:
                val = parts[1].strip().strip("\"'")
                if val and val.lower() != "none" and val != "null":
                    adapters.append(val)
    return adapters


def compile_with_adk(submission_dir: Path) -> tuple[bool, str]:
    """Compila la submission con adk-submission oficial; sin el compilador instalado, falla."""
    try:
        from adk_submission import ToolRegistry, compile_submission  # type: ignore[import-not-found]
        from swegemma.models import setup_gemma_model_registry  # type: ignore[import-not-found]

        tools = ToolRegistry()
        for tool_name in HARNESS_TOOLS:
            tools.register(tool_name, lambda **kwargs: None)

        models = setup_gemma_model_registry()
        agent = compile_submission(
            submission_dir=submission_dir,
            tool_registry=tools,
            model_registry=models,
        )
        return True, f"adk-submission: compilado con éxito ({agent})"
    except ImportError:
        return (
            False,
            "adk-submission no instalado en el entorno: el envío NO se compiló y no se da por válido",
        )
    except Exception as exc:
        return False, f"Fallo al compilar con adk-submission: {exc}"


# --- Comprobación de la instrucción contra la lista de herramientas (issue #173) -------------------
#
# Qué se comprueba. Un agente solo puede llamar a las herramientas de su propia lista `tools` (más los
# subagentes que declara con `agent_tool` o con `sub_agents`, y los pares de su mismo `sub_agents`, a los
# que ADK deja transferir; todos se llaman por su `name`). Si su instrucción nombra una herramienta
# conocida que no está en esa lista, le ordena algo que no puede hacer: es un defecto del envío y `verify`
# falla. Se comprueba cada agente con SU lista: la del principal y la de cada subagente. Se lee el campo
# `instruction` y, si el agente declara `skills:`, el `SKILL.md` de cada skill (el compilador las monta con
# las herramientas del agente). No se lee `description` ni otros archivos de la skill (ver las pruebas de
# límites conocidos).
#
# Cómo se lee el YAML. Con PyYAML y las mismas reglas que el cargador del organizador (adk_submission
# 0.2.12, `yaml_loader.py`): `yaml.SafeLoader` con la etiqueta `!include` (ruta relativa al archivo que la
# cita, dentro del envío, sin enlaces simbólicos, solo .md/.txt/.yaml/.yml, un .yaml incluido se interpreta
# como YAML y un .md/.txt es texto, profundidad máxima 10, 50 MiB por archivo y acumulados). Así la regla
# ve lo mismo que el compilador: BOM, claves entrecomilladas o complejas, alias, estilo de flujo, `tools:
# !include`, etc. No se imitan los demás campos del esquema (`extra="forbid"`): eso lo valida el
# compilador, que `verify` también ejecuta.
#
# Falla cerrado. Un archivo de agente que no se puede interpretar, un `agent_tool` o `sub_agents` mal
# formado, un agente LlmAgent sin `instruction` o PyYAML ausente son `[ERROR]`: la regla nunca pasa en
# silencio lo que no pudo leer. (Un esqueleto sin `name`, `tools`, `sub_agents` ni `skills`, como el de
# las pruebas estructurales, no se trata como agente.) Los agentes SequentialAgent, ParallelAgent y
# LoopAgent no llevan
# `instruction` (esquema) y no se les exige.
#
# Qué es «nombrar». Cualquier aparición del nombre como palabra completa, sin distinguir mayúsculas: entre
# comillas invertidas, dentro de un bloque de código o suelto en la prosa. Los nombres de las herramientas
# son identificadores con guion bajo, así que el falso positivo es raro; y exigir las comillas invertidas
# dejaría pasar la instrucción que ordena la herramienta sin ellas. «Palabra completa» significa que el
# carácter anterior y el siguiente no son letra, dígito ni guion bajo (`read_file(x)` y `read_file.`
# nombran; `read_file_all` no). Límites conocidos, que no se cubren: un nombre partido (`read file`), con
# escapes de Markdown (`read\_file`) o un nombre de subagente que sea una palabra común (se leería como
# nombrado en cualquier frase).
#
# Mención en negativo. «La búsqueda por similitud no está disponible» nombra la herramienta ausente para
# negarla, y la regla la cuenta como error: el modelo puede intentar llamarla, y detectar negaciones por el
# lenguaje no es fiable. La regla es estricta a propósito. Quien lo decida kit a kit lo declara con
# `--permitir-mencion nombre`: ese nombre deja de ser error y sale como `[AVISO]` en cada aparición, de
# modo que el caso sigue visible en la salida: un `[AVISO]` por cada línea donde aparece el nombre, y no sale
# el `[OK]` de ese agente (el permiso no prueba que todas las menciones sean negaciones). El permiso es global
# y alcanza a todos los agentes. `register` verifica sin él, a propósito (falla seguro).
#
# Un subagente declarado en `sub_agents` puede nombrar a quien lo declara (ADK permite transferir al padre),
# y a sus pares; no a un tío ni a un ancestro más lejano.
#
# Qué son «conocidas»: las de HARNESS_TOOLS y los nombres de los subagentes alcanzables desde `agent.yaml`.
# Un nombre que no es ninguna de las dos no se puede juzgar y no se señala. Un `sub_agents/*.yaml` que
# nadie referencia no cuenta: no está en el envío compilado.

try:
    import yaml as _yaml
except ImportError:  # sin PyYAML la regla no corre y lo dice (falla cerrado)
    _yaml = None

_INCLUDABLE_TEXT = frozenset({".md", ".txt"})
_INCLUDABLE_YAML = frozenset({".yaml", ".yml"})
_MAX_INCLUDE_DEPTH = 10
_MAX_YAML_BYTES = 50 * 1024 * 1024
_MAX_YAML_NODES = 50_000
_LLM_CLASS = "LlmAgent"
_WORKFLOW_CLASSES = ("SequentialAgent", "ParallelAgent", "LoopAgent")

PYYAML_AUSENTE = (
    "PyYAML no está instalado: la comprobación de herramientas no pudo correr y el envío NO se da por "
    "válido (instala el extra: pip install '.[kaggle]', o pip install pyyaml)"
)


class _YamlProblem(Exception):
    """Un problema al leer un archivo del envío (ruta fuera del envío, inexistente, demasiado grande...)."""


@dataclass
class AgentSpec:
    """Lo que la comprobación necesita de un archivo de agente (`agent.yaml` o uno de `sub_agents/`)."""

    path: Path
    name: str = ""
    agent_class: str = _LLM_CLASS
    tools: list[str] | None = None
    sub_agent_paths: list[Path] | None = None  # agent_tool y sub_agents
    sub_agents_only: list[Path] | None = None  # solo los de `sub_agents` (entre ellos son pares)
    texts: list[tuple[str, str]] | None = None  # (de dónde viene, texto): instruction y SKILL.md
    problems: list[str] | None = None


def _sandboxed(rel: str, base_dir: Path, root: Path, extensions: frozenset[str] | None) -> Path:
    """Resuelve `rel` desde `base_dir` sin salir de `root` ni usar enlaces simbólicos (como el cargador)."""
    raw = base_dir / rel
    if raw.is_symlink():
        raise _YamlProblem("enlace")
    for parent in raw.parents:
        if parent == root:
            break
        if parent.is_symlink():
            raise _YamlProblem("enlace")
    resolved = raw.resolve()
    if not resolved.is_relative_to(root):
        raise _YamlProblem("fuera")
    if not resolved.exists():
        raise _YamlProblem("no existe")
    if extensions is not None and resolved.suffix.lower() not in extensions:
        raise _YamlProblem("extensión")
    return resolved


def _include_message(kind: str, ref: str, file_name: str) -> str:
    if kind == "fuera":
        return f"`!include {ref}` en {file_name} apunta fuera del envío"
    if kind == "no existe":
        return f"`!include {ref}` en {file_name}: el archivo no existe"
    if kind == "enlace":
        return f"`!include {ref}` en {file_name}: es o pasa por un enlace simbólico"
    return f"`!include {ref}` en {file_name}: solo se incluyen .md, .txt, .yaml y .yml"


def _expanded_size(data: object, max_chars: int) -> None:
    """Como `_measure_expanded_size` del organizador: corta las bombas de alias."""
    total = 0
    visited = 0
    stack: list[object] = [data]
    while stack:
        cur = stack.pop()
        visited += 1
        if visited > _MAX_YAML_NODES:
            raise _YamlProblem("el YAML expandido tiene demasiados nodos (¿bomba de alias?)")
        if isinstance(cur, dict):
            total += 2
            for k, v in cur.items():
                total += len(str(k)) + 4
                stack.append(v)
        elif isinstance(cur, list):
            total += 2 + len(cur) * 2
            stack.extend(cur)
        else:
            total += len(str(cur))
        if total > max_chars:
            raise _YamlProblem("el YAML expandido excede el límite de tamaño")


def _make_loader(root: Path, current_file: Path, state: dict[str, int], depth: int) -> type:
    yaml = _yaml
    current_dir = current_file.parent.resolve()

    class _Loader(yaml.SafeLoader):
        def compose_node(self, parent: object, index: object) -> object:
            state["nodes"] = state.get("nodes", 0) + 1
            if state["nodes"] > max(_MAX_YAML_BYTES // 8, 10_000):
                raise _YamlProblem("demasiados nodos YAML")
            return super().compose_node(parent, index)

    def include(loader: object, node: object) -> object:
        ref = loader.construct_scalar(node)
        try:
            target = _sandboxed(ref, current_dir, root, _INCLUDABLE_TEXT | _INCLUDABLE_YAML)
        except _YamlProblem as exc:
            raise _YamlProblem(_include_message(str(exc), ref, current_file.name)) from exc
        size = target.stat().st_size
        state["total"] = state.get("total", 0) + size
        if size > _MAX_YAML_BYTES or state["total"] > _MAX_YAML_BYTES:
            raise _YamlProblem(f"`!include {ref}` excede el límite de tamaño")
        if target.suffix.lower() in _INCLUDABLE_YAML:
            if depth >= _MAX_INCLUDE_DEPTH:
                raise _YamlProblem(f"`!include {ref}` anidado a más de {_MAX_INCLUDE_DEPTH} niveles")
            return _load_yaml(target, root, state, depth + 1)
        return target.read_text(encoding="utf-8")

    _Loader.add_constructor("!include", include)
    return _Loader


def _load_yaml(path: Path, root: Path, state: dict[str, int], depth: int = 0) -> object:
    text = path.read_text(encoding="utf-8")
    data = _yaml.load(text, Loader=_make_loader(root, path, state, depth))
    _expanded_size(data, _MAX_YAML_BYTES)
    return data


def _relative_to_root(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix() if root in path.parents else path.name


def _resolve_config(cfg: str, path: Path, root: Path) -> Path:
    """Ruta de un `config_path` como la resuelve el compilador: antes junto al archivo que lo cita, y si no
    existe allí, desde la raíz del envío. Sin rutas absolutas ni `..`."""
    parts = re.split(r"[\\/]", cfg.strip())
    if cfg.strip().startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", cfg.strip()) or ".." in parts:
        raise _YamlProblem("fuera")
    base = path.parent if path.parent != root and (path.parent / cfg).exists() else root
    return _sandboxed(cfg, base, root, _INCLUDABLE_YAML)


def _parse_agent_file(path: Path, root: Path) -> AgentSpec:
    spec = AgentSpec(path=path, tools=[], sub_agent_paths=[], sub_agents_only=[], texts=[], problems=[])
    assert spec.tools is not None and spec.sub_agent_paths is not None and spec.sub_agents_only is not None
    assert spec.problems is not None and spec.texts is not None
    where = _relative_to_root(path, root)
    try:
        data = _load_yaml(path, root, {"total": path.stat().st_size})
    except (OSError, UnicodeDecodeError, ValueError, RecursionError, _yaml.YAMLError, _YamlProblem) as exc:
        detail = " ".join(str(exc).split()) or type(exc).__name__
        if isinstance(exc, UnicodeDecodeError):
            detail = "no es UTF-8"
        spec.problems.append(f"{where}: no se pudo interpretar el archivo ({detail})")
        return spec
    if not isinstance(data, dict):
        spec.problems.append(f"{where}: el archivo no es un mapa YAML (es {type(data).__name__})")
        return spec

    name = data.get("name")
    if isinstance(name, str):
        spec.name = name
    spec.agent_class = data.get("agent_class") or _LLM_CLASS
    if spec.agent_class != _LLM_CLASS and spec.agent_class not in _WORKFLOW_CLASSES:
        spec.problems.append(f"{where}: `agent_class` desconocida: {spec.agent_class!r}")
        return spec

    if spec.agent_class == _LLM_CLASS:
        instruction = data.get("instruction")
        if isinstance(instruction, str):
            spec.texts.append(("la instrucción", instruction))
        elif instruction is not None or any(k in data for k in ("name", "tools", "sub_agents", "skills")):
            # Un archivo que declara algo de un agente y no trae texto de `instruction` no se puede juzgar.
            # (Un esqueleto sin ninguno de esos campos, como el de las pruebas estructurales, no es un
            # agente que ordene nada; el compilador lo rechaza igualmente.)
            spec.problems.append(
                f"{where}: agente LlmAgent sin `instruction` de texto: no se puede comprobar lo que ordena"
            )

    tools = data.get("tools")
    if tools is not None and not isinstance(tools, list):
        spec.problems.append(f"{where}: `tools` debe ser una lista, no {type(tools).__name__}")
        tools = []
    configs: list[tuple[str, bool]] = []  # (config_path, viene de sub_agents)
    for item in tools or []:
        if isinstance(item, str):
            spec.tools.append(item)
        elif isinstance(item, dict) and set(item) == {"agent_tool"}:
            ref = item["agent_tool"]
            cfg = ref.get("config_path") if isinstance(ref, dict) else None
            if isinstance(cfg, str):
                configs.append((cfg, False))
            else:
                spec.problems.append(f"{where}: `agent_tool` sin `config_path`")
        else:
            spec.problems.append(f"{where}: elemento de `tools` que no se sabe leer: {item!r}")

    subs = data.get("sub_agents")
    if subs is not None and not isinstance(subs, list):
        spec.problems.append(f"{where}: `sub_agents` debe ser una lista, no {type(subs).__name__}")
        subs = []
    for item in subs or []:
        cfg = item.get("config_path") if isinstance(item, dict) else None
        if isinstance(cfg, str):
            configs.append((cfg, True))
        else:
            spec.problems.append(f"{where}: elemento de `sub_agents` sin `config_path`: {item!r}")

    for cfg, from_sub_agents in configs:
        try:
            target = _resolve_config(cfg, path, root)
        except _YamlProblem as exc:
            why = "sale del envío" if str(exc) in ("fuera", "enlace") else "no existe dentro del envío"
            spec.problems.append(f"{where}: el subagente `{cfg}` {why}")
            continue
        spec.sub_agent_paths.append(target)
        if from_sub_agents:
            spec.sub_agents_only.append(target)

    skills = data.get("skills")
    if skills is not None and not isinstance(skills, list):
        spec.problems.append(f"{where}: `skills` debe ser una lista, no {type(skills).__name__}")
        skills = []
    for skill in skills or []:
        if not isinstance(skill, str):
            spec.problems.append(f"{where}: elemento de `skills` que no es una ruta: {skill!r}")
            continue
        try:
            if re.split(r"[\\/]", skill).count("..") or skill.startswith(("/", "\\")):
                raise _YamlProblem("fuera")
            skill_md = _sandboxed(skill, root, root, None) / "SKILL.md"
            spec.texts.append((f"el SKILL.md de la skill `{skill}`", skill_md.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError, _YamlProblem) as exc:
            spec.problems.append(f"{where}: no se pudo leer `{skill}/SKILL.md` ({type(exc).__name__}: {exc})")
    return spec


def _mention_lines(text: str, name: str) -> list[int]:
    """Líneas (desde 1) donde `name` aparece como palabra completa, sin distinguir mayúsculas."""
    pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])", re.IGNORECASE)
    return [n for n, line in enumerate(text.splitlines(), start=1) if pattern.search(line)]


def _split_names(value: str) -> frozenset[str]:
    return frozenset(n.strip().lower() for n in value.split(",") if n.strip())


def parse_sin_resultados(value: str) -> frozenset[str]:
    """Interpreta `--sin-resultados`: lista separada por comas o ruta a un JSON.

    Formato del JSON: una lista de nombres, o un objeto con la clave `sin_resultados` que la contiene (puede
    estar vacía: el registro no marca ninguna). El registro de hallazgos del issue #171 no existía al escribir
    esto: cuando exista, basta una función que lo convierta a esta lista. Los nombres se comparan sin
    distinguir mayúsculas. Un valor que parece una ruta (termina en `.json` o lleva separadores) y no existe
    es un error de entrada (`FileNotFoundError`), no un nombre de herramienta; un valor sin nombres, también.
    """
    path = Path(value)
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = data.get("sin_resultados")
        if not isinstance(data, list) or not all(isinstance(x, str) for x in data):
            raise ValueError(f"{path}: se esperaba una lista de nombres o {{'sin_resultados': [...]}}")
        return frozenset(n.strip().lower() for n in data if n.strip())
    if value.lower().endswith(".json") or "/" in value or "\\" in value:
        raise FileNotFoundError(f"{value}: el archivo no existe")
    names = _split_names(value)
    if not names:
        raise ValueError("--sin-resultados no contiene ningún nombre")
    return names


def check_tool_references(
    submission_dir: Path,
    sin_resultados: frozenset[str] | None = None,
    permitir_mencion: frozenset[str] | None = None,
) -> tuple[bool, list[str]]:
    """Falla si la instrucción de un agente nombra una herramienta conocida que no está en SU lista.

    Avisa (sin fallar) de cada herramienta de la lista que `sin_resultados` marca como sin resultados.
    Sin `sin_resultados` no avisa de nada y lo dice. `permitir_mencion` exime a esos nombres (con un `[AVISO]`
    por aparición): ver «Mención en negativo» arriba. Falla cerrado ante lo que no pueda leer.
    """
    root_file = submission_dir / "agent.yaml"
    if not root_file.is_file():
        return True, []  # la ausencia de agent.yaml ya la señala la validación estructural
    if _yaml is None:
        return False, [f"[ERROR] {PYYAML_AUSENTE}"]
    root = submission_dir.resolve()
    messages: list[str] = []
    valid = True

    specs: list[AgentSpec] = []
    seen: set[Path] = set()
    queue = [root_file.resolve()]
    while queue:
        current = queue.pop(0)
        if current in seen:
            continue
        seen.add(current)
        spec = _parse_agent_file(current, root)
        specs.append(spec)
        queue.extend(spec.sub_agent_paths or [])

    by_path = {s.path: s for s in specs}
    declared: set[str] = {s.name.lower() for s in specs[1:] if s.name}
    known = {t.lower() for t in HARNESS_TOOLS} | declared

    # pares: los hijos de un mismo `sub_agents` pueden transferirse entre sí
    peers: dict[Path, set[str]] = {}
    for spec in specs:
        group = [p for p in spec.sub_agents_only or [] if p in by_path]
        for child in group:
            peers.setdefault(child, set()).update(
                by_path[o].name.lower() for o in group if o != child and by_path[o].name
            )

    # padres: un subagente de `sub_agents` puede transferir a quien lo declara (solo al padre directo: un
    # nieto no puede transferir a un tío)
    parents: dict[Path, set[str]] = {}
    for spec in specs:
        if spec.name:
            for child in spec.sub_agents_only or []:
                parents.setdefault(child, set()).add(spec.name.lower())

    flagged = None if sin_resultados is None else set(sin_resultados)
    if flagged is None:
        messages.append(
            "[INFO] Sin --sin-resultados: no se avisa de herramientas sin resultados "
            "(no se pasó un registro de hallazgos)"
        )
    elif not flagged:
        messages.append(
            "[INFO] El registro de hallazgos se leyó y no marca ninguna herramienta sin resultados "
            "(lista vacía): no hay avisos"
        )
    else:
        for unknown in sorted(flagged - known):
            messages.append(
                f"[ERROR] --sin-resultados nombra '{unknown}', que no es una herramienta conocida"
            )
            valid = False

    permitted = set() if permitir_mencion is None else set(permitir_mencion)
    for unknown in sorted(permitted - known):
        messages.append(f"[ERROR] --permitir-mencion nombra '{unknown}', que no es una herramienta conocida")
        valid = False

    for spec in specs:
        label = spec.name or spec.path.name
        for problem in spec.problems or []:
            messages.append(f"[ERROR] {problem}")
            valid = False
        allowed = {t.lower() for t in spec.tools or []}
        for sub_path in spec.sub_agent_paths or []:
            if sub_path in by_path and by_path[sub_path].name:
                allowed.add(by_path[sub_path].name.lower())
        allowed |= peers.get(spec.path, set())
        allowed |= parents.get(spec.path, set())
        absent = sorted(known - allowed - {spec.name.lower()})
        found = 0
        for origin, text in spec.texts or []:
            for n in absent:
                lines = _mention_lines(text, n)
                if not lines:
                    continue
                found += 1  # una permitida tampoco se da por limpia: no sale el [OK]
                if n in permitted:
                    for line in lines:  # un [AVISO] por cada línea
                        messages.append(
                            f"[AVISO] Se permite que {origin} de '{label}' nombre '{n}' (línea {line}) sin "
                            "tenerla en su lista (--permitir-mencion)"
                        )
                    continue
                messages.append(  # un [ERROR] por herramienta y texto: el de la primera línea
                    f"[ERROR] {origin[0].upper() + origin[1:]} de '{label}' nombra '{n}' "
                    f"(línea {lines[0]}) y esa herramienta no está en su lista de herramientas. Si la "
                    "menciona para negarla y se acepta ese riesgo, `--permitir-mencion`"
                )
                valid = False
        if spec.texts and not found and not spec.problems:
            messages.append(f"[OK] El texto de '{label}' no nombra herramientas fuera de su lista")
        for tool in sorted(allowed & (flagged or set())):
            ordered = (
                " y su instrucción la nombra"
                if any(_mention_lines(t, tool) for _, t in spec.texts or [])
                else ""
            )
            messages.append(
                f"[AVISO] '{label}' ofrece '{tool}', que el registro de hallazgos marca "
                f"sin resultados{ordered}"
            )
    return valid, messages


def validate_submission_dir(
    submission_dir: Path,
    sin_resultados: frozenset[str] | None = None,
    permitir_mencion: frozenset[str] | None = None,
) -> tuple[bool, list[str]]:
    """Valida la consistencia estructural de un directorio de envío antes de empaquetar."""
    messages: list[str] = []
    valid = True

    if not submission_dir.exists() or not submission_dir.is_dir():
        return False, [f"El directorio de origen no existe: {submission_dir}"]

    # 1. Comprobar archivos requeridos
    for req in REQUIRED_ROOT_FILES:
        req_path = submission_dir / req
        if not req_path.is_file():
            messages.append(f"[FALTA] Archivo obligatorio ausente: {req}")
            valid = False
        else:
            messages.append(f"[OK] Archivo presente: {req}")

    # 2. Comprobar archivos recomendados
    for rec in RECOMMENDED_FILES:
        rec_path = submission_dir / rec
        if not rec_path.is_file():
            messages.append(f"[AVISO] Archivo recomendado no encontrado: {rec}")
        else:
            messages.append(f"[OK] Archivo recomendado presente: {rec}")

    # 3. Comprobar adaptadores declarados en agent.yaml
    agent_yaml_path = submission_dir / "agent.yaml"
    if agent_yaml_path.is_file():
        try:
            content = agent_yaml_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            messages.append("[ERROR] agent.yaml no es UTF-8: no se pueden leer sus adaptadores")
            valid = False
            content = ""
        adapters = find_declared_adapters(content)
        for adp in adapters:
            adapter_dir = submission_dir / "adapters" / adp
            weights_file = adapter_dir / "adapter_model.safetensors"
            config_file = adapter_dir / "adapter_config.json"
            if not weights_file.is_file():
                messages.append(
                    f"[ERROR] Adaptador '{adp}' declarado en agent.yaml pero falta: {weights_file}"
                )
                valid = False
            else:
                messages.append(
                    f"[OK] Pesos del adaptador '{adp}' encontrados ({weights_file.stat().st_size} B)"
                )
            if not config_file.is_file():
                messages.append(f"[AVISO] Adaptador '{adp}' no tiene adapter_config.json")

    # 4. La instrucción no ordena herramientas que el agente no tiene
    refs_ok, refs_msgs = check_tool_references(submission_dir, sin_resultados, permitir_mencion)
    messages.extend(refs_msgs)
    if not refs_ok:
        valid = False

    # 5. Compilar con adk-submission si es posible
    adk_ok, adk_msg = compile_with_adk(submission_dir)
    messages.append(f"[COMPILACIÓN] {adk_msg}")
    if not adk_ok:
        valid = False

    return valid, messages


def pack_submission(submission_dir: Path, output_zip: Path) -> tuple[str, int]:
    """Empaqueta un directorio en un ZIP determinista (orden fijo, fechas fijas)."""
    valid, msgs = validate_submission_dir(submission_dir)
    if not valid:
        sys.stderr.write("Error: el directorio no cumple con los requisitos del envío:\n")
        for m in msgs:
            sys.stderr.write(f"  {m}\n")
        raise ValueError(f"Directorio inválido para empaquetado: {submission_dir}")

    output_zip.parent.mkdir(parents=True, exist_ok=True)
    fixed_time = (2026, 10, 1, 0, 0, 0)

    # Recolectar archivos ignorando artefactos temporales
    files_to_pack: list[tuple[Path, str]] = []
    for root, _, files in os.walk(submission_dir):
        for f in files:
            full = Path(root) / f
            rel = full.relative_to(submission_dir).as_posix()
            if rel.startswith(".") or rel.startswith("__pycache__") or rel.endswith(".pyc"):
                continue
            # No incluir manifiestos locales ni scripts auxiliares de descarga
            if rel in ("manifest.json", "download_kit.py", "README.md"):
                continue
            files_to_pack.append((full, rel))

    # Orden determinista
    files_to_pack.sort(key=lambda x: x[1])

    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for full_path, arcname in files_to_pack:
            data = full_path.read_bytes()
            zinfo = zipfile.ZipInfo(arcname, date_time=fixed_time)
            zinfo.compress_type = zipfile.ZIP_DEFLATED
            zinfo.external_attr = 0o644 << 16  # Permisos regulares
            zf.writestr(zinfo, data)

    sha256 = compute_file_sha256(output_zip)
    size = output_zip.stat().st_size
    return sha256, size


def verify_zip_submission(
    zip_path: Path,
    sin_resultados: frozenset[str] | None = None,
    permitir_mencion: frozenset[str] | None = None,
) -> tuple[bool, list[str], str, int]:
    """Verifica que un archivo submission.zip cumpla con el estándar de Kaggle Code Track."""
    messages: list[str] = []
    valid = True

    if not zip_path.is_file():
        return False, [f"El archivo zip no existe: {zip_path}"], "", 0

    size = zip_path.stat().st_size
    sha256 = compute_file_sha256(zip_path)

    # Límite Kaggle típico: < 500 MB
    if size > 500 * 1024 * 1024:
        messages.append(f"[ERROR] Tamaño del ZIP ({size} bytes) excede el límite recomendado de 500 MB")
        valid = False

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            namelist = zf.namelist()
            # 1. Comprobar archivos obligatorios
            for req in REQUIRED_ROOT_FILES:
                if req not in namelist:
                    messages.append(f"[FALTA] Archivo obligatorio ausente en ZIP: {req}")
                    valid = False
                else:
                    messages.append(f"[OK] Archivo presente en ZIP: {req}")

            # 2. Comprobar adaptadores
            if "agent.yaml" in namelist:
                try:
                    yaml_data = zf.read("agent.yaml").decode("utf-8")
                except UnicodeDecodeError:
                    messages.append("[ERROR] agent.yaml no es UTF-8: no se pueden leer sus adaptadores")
                    valid = False
                    yaml_data = ""
                adapters = find_declared_adapters(yaml_data)
                for adp in adapters:
                    expected_weights = f"adapters/{adp}/adapter_model.safetensors"
                    if expected_weights not in namelist:
                        messages.append(
                            f"[ERROR] Adaptador '{adp}' declarado en agent.yaml "
                            f"pero falta: {expected_weights}"
                        )
                        valid = False
                    else:
                        messages.append(f"[OK] Pesos del adaptador '{adp}' presentes en ZIP")

            # 3. Compilación con adk-submission mediante extracción temporal
            with tempfile.TemporaryDirectory() as tmp_dir:
                zf.extractall(tmp_dir)
                refs_ok, refs_msgs = check_tool_references(Path(tmp_dir), sin_resultados, permitir_mencion)
                messages.extend(refs_msgs)
                if not refs_ok:
                    valid = False
                adk_ok, adk_msg = compile_with_adk(Path(tmp_dir))
                messages.append(f"[COMPILACIÓN] {adk_msg}")
                if not adk_ok:
                    valid = False

    except zipfile.BadZipFile:
        return False, [f"El archivo no es un ZIP válido: {zip_path}"], sha256, size

    return valid, messages, sha256, size


@dataclass
class SubmissionRecord:
    submission_id: str
    date: str
    condition: str
    zip_filename: str
    sha256: str
    size_bytes: int
    is_exploratory: bool
    status: str  # "prepared", "submitted", "scored", "error"
    public_score: float | None = None
    kaggle_url: str | None = None
    notes: str = ""


class SubmissionRegistry:
    def __init__(self, path: Path = DEFAULT_REGISTRY_PATH) -> None:
        self.path = path
        self.submissions: list[SubmissionRecord] = []
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        with open(self.path, encoding="utf-8") as f:
            data = json.load(f)
        for item in data.get("submissions", []):
            self.submissions.append(SubmissionRecord(**item))

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": SCHEMA_VERSION,
            "competition_id": COMPETITION_ID,
            "competition_slug": COMPETITION_SLUG,
            "last_updated": datetime.date.today().isoformat(),
            "submissions": [asdict(s) for s in self.submissions],
        }
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def next_id(self) -> str:
        count = len(self.submissions) + 1
        return f"sub-{count:03d}"

    def register(
        self,
        zip_path: Path,
        condition: str,
        notes: str = "",
        is_exploratory: bool = False,
        status: str = "prepared",
        public_score: float | None = None,
        kaggle_url: str | None = None,
    ) -> SubmissionRecord:
        valid, msgs, sha256, size = verify_zip_submission(zip_path)
        if not valid:
            raise ValueError(f"No se puede registrar un ZIP inválido: {zip_path}\n" + "\n".join(msgs))

        # Comprobar si ya existe con el mismo hash
        for existing in self.submissions:
            if existing.sha256.lower() == sha256.lower():
                return existing

        sub_id = self.next_id()
        record = SubmissionRecord(
            submission_id=sub_id,
            date=datetime.date.today().isoformat(),
            condition=condition,
            zip_filename=zip_path.name,
            sha256=sha256,
            size_bytes=size,
            is_exploratory=is_exploratory,
            status=status,
            public_score=public_score,
            kaggle_url=kaggle_url,
            notes=notes,
        )
        self.submissions.append(record)
        self.save()
        return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    # pack
    p_pack = subparsers.add_parser("pack", help="Empaqueta un directorio de condición en submission.zip")
    p_pack.add_argument(
        "--condition-dir",
        type=Path,
        default=DEFAULT_A_KIT_DIR,
        help="Directorio de la condición (por defecto: a_kit)",
    )
    p_pack.add_argument(
        "--output",
        "-o",
        type=Path,
        required=True,
        help="Ruta de destino del archivo ZIP",
    )

    # verify
    p_verify = subparsers.add_parser("verify", help="Verifica un archivo ZIP de envío")
    p_verify.add_argument("zip_path", type=Path, help="Ruta al archivo ZIP a verificar")
    p_verify.add_argument(
        "--sin-resultados",
        type=str,
        default=None,
        help="Herramientas que el registro de hallazgos marca sin resultados: lista separada por comas "
        "o ruta a un JSON (lista, u objeto con la clave 'sin_resultados'). Sin él no se avisa de ninguna.",
    )
    p_verify.add_argument(
        "--permitir-mencion",
        type=str,
        default=None,
        help="Herramientas conocidas que una instrucción puede nombrar sin tenerlas (por ejemplo para "
        "negarlas), separadas por comas. Cada aparición sale como [AVISO]. Por defecto, ninguna.",
    )

    # register
    p_reg = subparsers.add_parser(
        "register",
        help="Registra un envío en el registro oficial (verifica con la regla estricta: sin "
        "--permitir-mencion ni --sin-resultados; un kit que los necesite no se puede registrar)",
    )
    p_reg.add_argument("--zip", type=Path, required=True, help="Ruta al ZIP validado")
    p_reg.add_argument("--condition", type=str, required=True, help="Condición experimental (A, B, C, D...)")
    p_reg.add_argument("--notes", type=str, default="", help="Notas descriptivas del envío")
    p_reg.add_argument(
        "--exploratory",
        action="store_true",
        help="Marcar como exploración (no entra en conclusiones)",
    )
    p_reg.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY_PATH, help="Ruta a registry.json")

    # list
    p_list = subparsers.add_parser("list", help="Lista los envíos registrados")
    p_list.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY_PATH, help="Ruta a registry.json")

    args = parser.parse_args(argv)

    if args.cmd == "pack":
        try:
            sha, size = pack_submission(args.condition_dir, args.output)
            sys.stdout.write(f"Empaquetado exitoso: {args.output}\n")
            sys.stdout.write(f"  Tamaño: {size} bytes\n")
            sys.stdout.write(f"  SHA-256: {sha}\n")
            return EXIT_OK
        except Exception as exc:
            sys.stderr.write(f"Error al empaquetar: {exc}\n")
            return EXIT_INVALID

    elif args.cmd == "verify":
        flagged = None
        if args.sin_resultados is not None:
            try:
                flagged = parse_sin_resultados(args.sin_resultados)
            except (ValueError, OSError) as exc:
                sys.stderr.write(f"Error en --sin-resultados: {exc}\n")
                return EXIT_INPUTS
        permitted = None
        if args.permitir_mencion is not None:
            permitted = _split_names(args.permitir_mencion)
            if not permitted:
                sys.stderr.write("Error en --permitir-mencion: no contiene ningún nombre\n")
                return EXIT_INPUTS
        valid, msgs, sha, size = verify_zip_submission(args.zip_path, flagged, permitted)
        for m in msgs:
            sys.stdout.write(f"{m}\n")
        sys.stdout.write(f"\nResultado: {'VÁLIDO' if valid else 'INVÁLIDO'}\n")
        sys.stdout.write(f"  Tamaño: {size} bytes\n")
        sys.stdout.write(f"  SHA-256: {sha}\n")
        return EXIT_OK if valid else EXIT_INVALID

    elif args.cmd == "register":
        reg = SubmissionRegistry(args.registry)
        try:
            rec = reg.register(
                zip_path=args.zip,
                condition=args.condition,
                notes=args.notes,
                is_exploratory=args.exploratory,
            )
            sys.stdout.write(f"Envío registrado: {rec.submission_id}\n")
            sys.stdout.write(f"  Condición: {rec.condition}\n")
            sys.stdout.write(f"  Archivo: {rec.zip_filename}\n")
            sys.stdout.write(f"  SHA-256: {rec.sha256}\n")
            sys.stdout.write(f"  Registro: {args.registry}\n")
            return EXIT_OK
        except Exception as exc:
            sys.stderr.write(f"Error al registrar: {exc}\n")
            return EXIT_INVALID

    elif args.cmd == "list":
        reg = SubmissionRegistry(args.registry)
        if not reg.submissions:
            sys.stdout.write(f"No hay envíos registrados en {args.registry}\n")
            return EXIT_OK
        sys.stdout.write(f"Envíos registrados ({len(reg.submissions)}) en {args.registry}:\n")
        sys.stdout.write(
            f"{'ID':<8} {'FECHA':<12} {'COND':<6} {'STATUS':<10} {'SCORE':<8} "
            f"{'SHA256 (prefijo)':<18} {'ARCHIVO'}\n"
        )
        sys.stdout.write("-" * 80 + "\n")
        for s in reg.submissions:
            score_str = f"{s.public_score:.4f}" if s.public_score is not None else "-"
            sys.stdout.write(
                f"{s.submission_id:<8} {s.date:<12} {s.condition:<6} {s.status:<10} "
                f"{score_str:<8} {s.sha256[:16]:<18} {s.zip_filename}\n"
            )
        return EXIT_OK

    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
