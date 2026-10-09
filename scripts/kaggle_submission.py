"""Empaquetado, verificación y registro de envíos para el Code Track (Kaggle).

Valida que un submission.zip cumpla con el formato declarativo de adk-submission,
calcula su resumen SHA-256 de forma determinista y mantiene el registro versionado
en experiments/gemma_developer_agent/submissions/registry.json.

Uso:
    python -m scripts.kaggle_submission pack --condition-dir <dir> --output <archivo.zip>
    python -m scripts.kaggle_submission verify <archivo.zip> [--sin-resultados a,b | archivo.json]
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
# subagentes que declara con `agent_tool` o con `sub_agents`, que se llaman por su `name`). Si su
# instrucción nombra una herramienta conocida que no está en esa lista, le ordena algo que no puede hacer:
# es un defecto del envío y `verify` falla. Se comprueba cada agente con SU lista: la del principal y la
# de cada subagente. Solo se lee el campo `instruction` (el esquema del organizador no admite otro).
#
# Qué es «nombrar». Cualquier aparición del nombre como palabra completa, sin distinguir mayúsculas:
# entre comillas invertidas, dentro de un bloque de código o suelto en la prosa. Los nombres de las
# herramientas son identificadores con guion bajo, así que el falso positivo es raro; y exigir las comillas
# invertidas dejaría pasar la instrucción que ordena la herramienta sin ellas. «Palabra completa» significa
# que el carácter anterior y el siguiente no son letra, dígito ni guion bajo (`read_file(x)` y `read_file.`
# nombran; `read_file_all` no). Límites conocidos, que no se cubren: un nombre partido (`read file`), con
# escapes de Markdown (`read\_file`) o un nombre de subagente que sea una palabra común (se leería como
# nombrado en cualquier frase).
#
# Qué son «conocidas»: las de HARNESS_TOOLS y los nombres de los subagentes declarados. Un nombre que no es
# ninguna de las dos no se puede juzgar y no se señala.

_INCLUDE = "!include"
_BLOCK_SCALAR = ("|", ">")


@dataclass
class AgentSpec:
    """Lo que la comprobación necesita de un archivo de agente (`agent.yaml` o uno de `sub_agents/`)."""

    path: Path
    name: str = ""
    tools: list[str] | None = None
    sub_agent_paths: list[Path] | None = None
    instruction: str | None = None
    problems: list[str] | None = None


def _strip_comment(line: str) -> str:
    if "'" in line or '"' in line:
        return line.rstrip()
    return re.sub(r"(^|\s)#.*$", "", line).rstrip()


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _resolve_include(ref: str, base_file: Path, root: Path, problems: list[str]) -> str:
    """Lee el archivo de un `!include` (relativo al archivo que lo cita, dentro del envío).

    Como el compilador del organizador, `!include` es una etiqueta de un valor YAML: el contenido del archivo
    incluido es texto y no se vuelve a interpretar.
    """
    target = (base_file.parent / ref).resolve()
    if root.resolve() not in target.parents:
        problems.append(f"`!include {ref}` en {base_file.name} apunta fuera del envío")
        return ""
    if not target.is_file():
        problems.append(f"`!include {ref}` en {base_file.name}: el archivo no existe")
        return ""
    return target.read_text(encoding="utf-8")


def _parse_tools(
    value: str, block: list[str], problems: list[str], where: str
) -> tuple[list[str], list[str]]:
    """Devuelve (nombres de herramientas, rutas `config_path` de subagentes)."""
    names: list[str] = []
    configs: list[str] = []
    if value:
        if value.startswith("[") and value.endswith("]"):
            names = [_unquote(p) for p in value[1:-1].split(",") if p.strip()]
        else:
            problems.append(f"{where}: `tools` con un valor que esta comprobación no sabe leer: {value!r}")
        return names, configs
    items: list[dict[str, str]] = []
    for raw in block:
        s = _strip_comment(raw).strip()
        if not s:
            continue
        if s.startswith("-"):
            item = s[1:].strip()
            key, sep, rest = item.partition(":")
            if sep and not item.startswith(("'", '"')):
                items.append({"key": key.strip(), "text": rest})
            else:
                items.append({"name": _unquote(item)})
        elif items:
            items[-1]["text"] = items[-1].get("text", "") + " " + s
    for it in items:
        if "name" in it:
            names.append(it["name"])
        elif it["key"] == "agent_tool":
            m = re.search(r"config_path:\s*[\"']?([^\s,\"'}]+)", it.get("text", ""))
            if m:
                configs.append(m.group(1))
            else:
                problems.append(f"{where}: `agent_tool` sin `config_path`")
        else:
            names.append(it["key"])
    return names, configs


def _parse_agent_file(path: Path, root: Path) -> AgentSpec:
    spec = AgentSpec(path=path, tools=[], sub_agent_paths=[], problems=[])
    assert spec.problems is not None and spec.tools is not None and spec.sub_agent_paths is not None
    lines = path.read_text(encoding="utf-8").splitlines()
    where = path.relative_to(root).as_posix() if root in path.parents else path.name
    i = 0
    while i < len(lines):
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", _strip_comment(lines[i]))
        i += 1
        if not m:
            continue
        key, value = m.group(1), m.group(2).strip()
        block: list[str] = []
        while i < len(lines) and (not lines[i].strip() or lines[i][0] in " \t-"):
            block.append(lines[i])
            i += 1
        if key == "name":
            spec.name = _unquote(value)
        elif key == "instruction":
            if value.startswith(_INCLUDE):
                ref = value[len(_INCLUDE) :].strip()
                spec.instruction = _resolve_include(ref, path, root, spec.problems)
            elif value.startswith(_BLOCK_SCALAR):
                spec.instruction = "\n".join(b.strip() for b in block)
            else:
                # escalar simple en una o varias líneas
                joined = " ".join([value, *(b.strip() for b in block)]).strip()
                spec.instruction = _unquote(joined)
        elif key in ("tools", "sub_agents"):
            if key == "tools":
                names, configs = _parse_tools(value, block, spec.problems, where)
                spec.tools = names
            else:
                joined_block = "\n".join([value, *block])
                configs = re.findall(r"config_path:\s*[\"']?([^\s,\"'}]+)", joined_block)
            for cfg in configs:
                candidate = (path.parent / cfg).resolve()
                if not candidate.is_file():
                    candidate = (root / cfg).resolve()
                if root.resolve() in candidate.parents and candidate.is_file():
                    spec.sub_agent_paths.append(candidate)
                else:
                    spec.problems.append(f"{where}: el subagente `{cfg}` no existe dentro del envío")
    return spec


def _mentions(text: str, name: str) -> int | None:
    """Primera línea (desde 1) donde `name` aparece como palabra completa, sin distinguir mayúsculas."""
    pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])", re.IGNORECASE)
    for n, line in enumerate(text.splitlines(), start=1):
        if pattern.search(line):
            return n
    return None


def parse_sin_resultados(value: str) -> frozenset[str]:
    """Interpreta `--sin-resultados`: lista separada por comas o ruta a un JSON.

    Formato del JSON: una lista de nombres, o un objeto con la clave `sin_resultados` que la contiene. El
    registro de hallazgos del issue #171 no existía al escribir esto: cuando exista, basta una función que
    lo convierta a esta lista. Los nombres se comparan sin distinguir mayúsculas.
    """
    path = Path(value)
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = data.get("sin_resultados")
        if not isinstance(data, list) or not all(isinstance(x, str) for x in data):
            raise ValueError(f"{path}: se esperaba una lista de nombres o {{'sin_resultados': [...]}}")
        names = data
    else:
        names = value.split(",")
    return frozenset(n.strip().lower() for n in names if n.strip())


def check_tool_references(
    submission_dir: Path, sin_resultados: frozenset[str] | None = None
) -> tuple[bool, list[str]]:
    """Falla si la instrucción de un agente nombra una herramienta conocida que no está en SU lista.

    Avisa (sin fallar) de cada herramienta de la lista que `sin_resultados` marca como sin resultados.
    Sin `sin_resultados` no avisa de nada y lo dice.
    """
    root_file = submission_dir / "agent.yaml"
    if not root_file.is_file():
        return True, []  # la ausencia de agent.yaml ya la señala la validación estructural
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
    sub_dir = root / "sub_agents"
    if sub_dir.is_dir():
        for extra in sorted(sub_dir.glob("*.yaml")):
            if extra.resolve() not in by_path:
                declared.add(_parse_agent_file(extra.resolve(), root).name.lower())
    declared.discard("")
    known = {t.lower() for t in HARNESS_TOOLS} | declared

    flagged = None if sin_resultados is None else set(sin_resultados)
    if flagged is None:
        messages.append(
            "[INFO] Sin --sin-resultados: no se avisa de herramientas sin resultados "
            "(no se pasó un registro de hallazgos)"
        )
    else:
        for unknown in sorted(flagged - known):
            messages.append(
                f"[ERROR] --sin-resultados nombra '{unknown}', que no es una herramienta conocida"
            )
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
        text = spec.instruction or ""
        if spec.instruction is not None:
            absent = sorted(known - allowed - {spec.name.lower()})
            bad = [(n, _mentions(text, n)) for n in absent]
            bad = [(n, line) for n, line in bad if line is not None]
            for n, line in bad:
                messages.append(
                    f"[ERROR] La instrucción de '{label}' nombra '{n}' (línea {line}) y esa herramienta "
                    "no está en su lista de herramientas"
                )
                valid = False
            if not bad:
                messages.append(f"[OK] La instrucción de '{label}' no nombra herramientas fuera de su lista")
        for tool in sorted(allowed & (flagged or set())):
            ordered = " y su instrucción la nombra" if _mentions(text, tool) is not None else ""
            messages.append(
                f"[AVISO] '{label}' ofrece '{tool}', que el registro de hallazgos marca "
                f"sin resultados{ordered}"
            )
    return valid, messages


def validate_submission_dir(
    submission_dir: Path, sin_resultados: frozenset[str] | None = None
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
        content = agent_yaml_path.read_text(encoding="utf-8")
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
    refs_ok, refs_msgs = check_tool_references(submission_dir, sin_resultados)
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
    zip_path: Path, sin_resultados: frozenset[str] | None = None
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
                yaml_data = zf.read("agent.yaml").decode("utf-8")
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
                refs_ok, refs_msgs = check_tool_references(Path(tmp_dir), sin_resultados)
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

    # register
    p_reg = subparsers.add_parser("register", help="Registra un envío en el registro oficial")
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
        valid, msgs, sha, size = verify_zip_submission(args.zip_path, flagged)
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
