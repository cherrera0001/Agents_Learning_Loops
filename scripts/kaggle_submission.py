"""Empaquetado, verificación y registro de envíos para el Code Track (Kaggle).

Valida que un submission.zip cumpla con el formato declarativo de adk-submission,
calcula su resumen SHA-256 de forma determinista y mantiene el registro versionado
en experiments/gemma_developer_agent/submissions/registry.json.

Uso:
    python -m scripts.kaggle_submission pack --condition-dir <dir> --output <archivo.zip>
    python -m scripts.kaggle_submission verify <archivo.zip>
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
from typing import Any

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
        for tool_name in [
            "run_command",
            "read_file",
            "edit_file",
            "write_file",
            "get_status",
            "submit_patch",
            "get_code_neighbors",
            "search_similar_code",
            "get_code_subgraph",
        ]:
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


def validate_submission_dir(submission_dir: Path) -> tuple[bool, list[str]]:
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

    # 4. Compilar con adk-submission si es posible
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


def verify_zip_submission(zip_path: Path) -> tuple[bool, list[str], str, int]:
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
                            f"[ERROR] Adaptador '{adp}' declarado en agent.yaml pero falta: {expected_weights}"
                        )
                        valid = False
                    else:
                        messages.append(f"[OK] Pesos del adaptador '{adp}' presentes en ZIP")

            # 3. Compilación con adk-submission mediante extracción temporal
            with tempfile.TemporaryDirectory() as tmp_dir:
                zf.extractall(tmp_dir)
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
        valid, msgs, sha, size = verify_zip_submission(args.zip_path)
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
            f"{'ID':<8} {'FECHA':<12} {'COND':<6} {'STATUS':<10} {'SCORE':<8} {'SHA256 (prefijo)':<18} {'ARCHIVO'}\n"
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
