#!/usr/bin/env python3
"""Descarga y verificación del kit oficial sample_submission (Kaggle Gemma 4 Developer Agent).

Uso exclusivo de la biblioteca estándar de Python (stdlib).
Cumple con la Sección 4 de las reglas de la competencia: no redistribuye
los archivos en el repositorio de código abierto; los adquiere localmente
vía API oficial de Kaggle y verifica su integridad mediante SHA-256.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

DEFAULT_MANIFEST = Path(__file__).parent / "manifest.json"
DEFAULT_TARGET_DIR = Path(__file__).parent
DATA_SAMPLE_SUBMISSION = (
    Path(__file__).parent.parent.parent / "data" / "sample_submission"
)


def compute_sha256(file_path: Path) -> str:
    """Calcula el hash SHA-256 de un archivo en bloques de 64 KB."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def load_manifest(manifest_path: Path) -> dict[str, Any]:
    """Carga y valida la estructura básica del manifiesto JSON."""
    if not manifest_path.exists():
        raise FileNotFoundError(f"No se encontró el manifiesto: {manifest_path}")
    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if "files" not in data or not isinstance(data["files"], list):
        raise ValueError("El manifiesto debe contener una lista bajo la clave 'files'.")
    return data


def verify_files(target_dir: Path, manifest: dict[str, Any]) -> tuple[bool, list[str]]:
    """Verifica que todos los archivos declarados existan y coincidan en tamaño y SHA-256."""
    all_ok = True
    messages: list[str] = []

    for item in manifest["files"]:
        rel_path = item["path"]
        expected_size = item["size"]
        expected_sha = item["sha256"].lower()

        file_path = target_dir / rel_path
        if not file_path.exists():
            messages.append(f"[FALTA] {rel_path} no existe en {target_dir}")
            all_ok = False
            continue

        actual_size = file_path.stat().st_size
        if actual_size != expected_size:
            messages.append(
                f"[TAMAÑO INCORRECTO] {rel_path}: esperado {expected_size} bytes, real {actual_size} bytes"
            )
            all_ok = False
            continue

        actual_sha = compute_sha256(file_path).lower()
        if actual_sha != expected_sha:
            messages.append(
                f"[SHA-256 DISCORDANTE] {rel_path}:\n"
                f"  esperado: {expected_sha}\n"
                f"  real:     {actual_sha}"
            )
            all_ok = False
            continue

        messages.append(f"[OK] {rel_path} ({actual_size} bytes, sha256: {actual_sha[:12]}...)")

    return all_ok, messages


def get_kaggle_credentials() -> tuple[str | None, str | None]:
    """Obtiene credenciales de Kaggle desde el entorno, kaggle.json o .env sin imprimirlas."""
    # 1. Variables de entorno estándar
    username = os.environ.get("KAGGLE_USERNAME")
    key = os.environ.get("KAGGLE_KEY")
    if username and key:
        return username.strip(), key.strip()

    # 2. ~/.kaggle/kaggle.json
    kaggle_json = Path.home() / ".kaggle" / "kaggle.json"
    if kaggle_json.exists():
        try:
            data = json.loads(kaggle_json.read_text(encoding="utf-8"))
            if data.get("username") and data.get("key"):
                return str(data["username"]).strip(), str(data["key"]).strip()
        except Exception:
            pass

    # 3. .env en la raíz del repositorio
    # Busca KAGGLE_API_TOKEN o KAGGLE_KEY / KAGGLE_USERNAME
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    env_file = repo_root / ".env"
    if env_file.exists():
        try:
            for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k == "KAGGLE_USERNAME" and not username:
                    username = v
                elif k in ("KAGGLE_KEY", "KAGGLE_API_KEY") and not key:
                    key = v
                elif k == "KAGGLE_API_TOKEN" and not key:
                    # Formato token directo o json serializado
                    if "{" in v and "username" in v:
                        try:
                            tdata = json.loads(v)
                            return str(tdata.get("username")).strip(), str(tdata.get("key")).strip()
                        except Exception:
                            pass
                    key = v
        except Exception:
            pass

    return username, key


def copy_from_local_source(source_dir: Path, target_dir: Path, manifest: dict[str, Any]) -> bool:
    """Intenta copiar los archivos desde una fuente local previa (por ejemplo, data/sample_submission)."""
    if not source_dir.exists():
        return False

    all_exist = all((source_dir / item["path"]).exists() for item in manifest["files"])
    if not all_exist:
        return False

    for item in manifest["files"]:
        src = source_dir / item["path"]
        dst = target_dir / item["path"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.resolve() != dst.resolve():
            shutil.copy2(src, dst)
    return True


def download_from_kaggle_api(competition_slug: str, target_dir: Path, manifest: dict[str, Any]) -> None:
    """Descarga sample_submission.zip usando el endpoint oficial de la API de Kaggle."""
    username, key = get_kaggle_credentials()
    if not username or not key:
        raise PermissionError(
            "No se encontraron credenciales de Kaggle (KAGGLE_USERNAME y KAGGLE_KEY en entorno, "
            "~/.kaggle/kaggle.json o .env)."
        )

    url = f"https://www.kaggle.com/api/v1/competitions/data/download/{competition_slug}/sample_submission.zip"
    req = urllib.request.Request(url)
    auth_header = base64.b64encode(f"{username}:{key}".encode()).decode("ascii")
    req.add_header("Authorization", f"Basic {auth_header}")

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp_zip:
        tmp_path = Path(tmp_zip.name)

    try:
        with urllib.request.urlopen(req) as resp, open(tmp_path, "wb") as out_f:
            shutil.copyfileobj(resp, out_f)

        with zipfile.ZipFile(tmp_path, "r") as zf:
            zf.extractall(target_dir)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Descarga y verificación del kit oficial sample_submission de Kaggle."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Ruta al manifiesto JSON con los hashes oficiales.",
    )
    parser.add_argument(
        "--target-dir",
        type=Path,
        default=DEFAULT_TARGET_DIR,
        help="Directorio destino para verificar o alojar los archivos del kit.",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Solo verifica la integridad de los archivos existentes sin intentar descargar.",
    )
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    target_dir = args.target_dir.resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    # 1. Comprobar si ya están en target_dir
    ok, msgs = verify_files(target_dir, manifest)
    if ok:
        print(f"Verificación exitosa: todos los archivos en {target_dir} coinciden con el manifiesto.")
        for m in msgs:
            print(f"  {m}")
        return 0

    if args.verify_only:
        print(f"Fallo de verificación en {target_dir}:")
        for m in msgs:
            print(f"  {m}")
        return 1

    # 2. Intentar recuperar desde copia local en data/sample_submission (ignorado por git)
    print("Archivos incompletos en destino. Buscando copia local en data/...")
    if copy_from_local_source(DATA_SAMPLE_SUBMISSION, target_dir, manifest):
        ok, msgs = verify_files(target_dir, manifest)
        if ok:
            print(f"Kit poblado y verificado exitosamente desde {DATA_SAMPLE_SUBMISSION}:")
            for m in msgs:
                print(f"  {m}")
            return 0

    # 3. Descargar vía API de Kaggle
    competition_slug = manifest.get("competition_slug", "gemma-4-developer-agent")
    print(f"Descargando kit oficial desde la API de Kaggle para '{competition_slug}'...")
    try:
        download_from_kaggle_api(competition_slug, target_dir, manifest)
    except Exception as e:
        print(f"Error al descargar desde la API de Kaggle: {e}", file=sys.stderr)
        return 1

    ok, msgs = verify_files(target_dir, manifest)
    if ok:
        print(f"Descarga y verificación completadas con éxito en {target_dir}:")
        for m in msgs:
            print(f"  {m}")
        return 0
    else:
        print(f"Error: los archivos descargados no coinciden con el manifiesto:")
        for m in msgs:
            print(f"  {m}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
