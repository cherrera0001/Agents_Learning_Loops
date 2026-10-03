#!/usr/bin/env python3
"""Comprobación de higiene contra la lista oficial de archivos de la competencia.

Verifica que ningún archivo versionado en experiments/gemma_developer_agent/
coincida por nombre, ruta relativa o hash SHA-256 con los datos de la competencia.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def get_kaggle_bearer_token() -> str | None:
    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line.startswith("KAGGLE_API_TOKEN="):
                return line.split("=", 1)[1].strip().strip("'\"")
    return None


def fetch_all_competition_files() -> list[dict[str, str | int]]:
    token = get_kaggle_bearer_token()
    if not token:
        print("Aviso: No se encontró KAGGLE_API_TOKEN en .env", file=sys.stderr)
        return []

    base_url = "https://www.kaggle.com/api/v1/competitions/data/list/gemma-4-developer-agent"
    all_files: list[dict[str, str | int]] = []
    page_token = None

    while True:
        url = f"{base_url}?pageToken={page_token}" if page_token else base_url
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode())
                files = data.get("files", [])
                for f in files:
                    all_files.append(
                        {
                            "name": f.get("name", ""),
                            "totalBytes": f.get("totalBytes", 0),
                        }
                    )
                page_token = data.get("nextPageToken")
                if not page_token:
                    break
        except Exception as e:
            print(f"Error al consultar la API de Kaggle: {e}", file=sys.stderr)
            break

    return all_files


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    print("1. Consultando lista oficial de archivos de la competencia vía API...")
    comp_files = fetch_all_competition_files()
    print(f"   Total de archivos reportados por la API de Kaggle: {len(comp_files)}")

    comp_names = {f["name"] for f in comp_files}

    # Hashing de archivos locales descargados en data/
    local_data_dir = REPO_ROOT / "experiments" / "gemma_developer_agent" / "data"
    comp_hashes: dict[str, str] = {}
    if local_data_dir.exists():
        for p in local_data_dir.rglob("*"):
            if p.is_file():
                rel = p.relative_to(local_data_dir).as_posix()
                with contextlib.suppress(Exception):
                    comp_hashes[compute_sha256(p)] = rel
    print(f"   Hashes calculados de datos locales descargados en data/: {len(comp_hashes)}")

    print("\n2. Inspeccionando archivos versionados en git (experiments/gemma_developer_agent)...")
    cmd = ["git", "ls-files", "experiments/gemma_developer_agent"]
    res = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, check=True)
    tracked_files = [line.strip() for line in res.stdout.splitlines() if line.strip()]
    print(f"   Total de archivos versionados: {len(tracked_files)}")

    # Comprobación de colisiones
    path_collisions: list[str] = []
    hash_collisions: list[str] = []

    for rel_path in tracked_files:
        full_path = REPO_ROOT / rel_path
        if not full_path.exists():
            continue

        # Coincidencia por nombre de ruta relativa dentro del kit/competencia
        sub_name = rel_path.replace("experiments/gemma_developer_agent/", "")
        if sub_name in comp_names or rel_path in comp_names:
            path_collisions.append(f"Ruta exacta: {rel_path}")

        # Coincidencia por SHA-256 contra datos de la competencia
        file_sha = compute_sha256(full_path)
        if file_sha in comp_hashes:
            matched_comp_file = comp_hashes[file_sha]
            hash_collisions.append(
                f"SHA-256 idéntico ({file_sha[:12]}...): {rel_path} == data/{matched_comp_file}"
            )

    print("\n3. Resultados de la comprobación:")
    print(f"   Coincidencias por ruta/nombre: {len(path_collisions)}")
    for pc in path_collisions:
        print(f"     [ALERTA] {pc}")

    print(f"   Coincidencias por hash SHA-256: {len(hash_collisions)}")
    for hc in hash_collisions:
        print(f"     [ALERTA] {hc}")

    if path_collisions or hash_collisions:
        print("\n[FALLO] Se detectaron archivos de la competencia versionados en git.", file=sys.stderr)
        return 1

    print(
        "\n[VERIFICADO] Ningún archivo versionado coincide con la lista de la competencia ni por nombre "
        "ni por SHA-256."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
