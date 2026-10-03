#!/usr/bin/env python3
"""Comprobación de higiene contra la lista oficial de archivos de la competencia.

Verifica que ningún archivo versionado en experiments/gemma_developer_agent/
coincida por nombre, ruta relativa o hash SHA-256 con los datos de la competencia.

Fuentes de referencia (se informa cuántos archivos aporta cada una):
  - manifiesto versionado conditions/a_kit/manifest.json (SHA-256);
  - datos locales descargados en data/ (SHA-256), si existen;
  - lista de la API de Kaggle (nombres), si hay KAGGLE_API_TOKEN en .env.

Códigos de salida:
  0  verificado: se comparó contra una referencia no vacía y completa, sin coincidencias.
  1  hay archivos versionados que coinciden con la competencia.
  2  no se pudo comprobar: referencia vacía o incompleta (error de la API). Nunca es «verificado».
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import subprocess
import sys
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EXPERIMENT_DIR = "experiments/gemma_developer_agent"
MANIFEST_REL = f"{EXPERIMENT_DIR}/conditions/a_kit/manifest.json"
# Archivos propios de la carpeta del kit: no son datos de la competencia.
OWN_FILES = frozenset(
    {
        MANIFEST_REL,
        f"{EXPERIMENT_DIR}/conditions/a_kit/download_kit.py",
        f"{EXPERIMENT_DIR}/conditions/a_kit/README.md",
    }
)

EXIT_OK = 0
EXIT_COLLISION = 1
EXIT_UNVERIFIED = 2


@dataclass
class Reference:
    """Lista de referencia con el recuento por fuente y los errores al obtenerla."""

    hashes: dict[str, str] = field(default_factory=dict)  # sha256 -> etiqueta
    names: set[str] = field(default_factory=set)
    sources: dict[str, int] = field(default_factory=dict)  # fuente -> nº de archivos
    errors: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return sum(self.sources.values())


FetchFn = Callable[[], tuple[list[str], str | None]]


def get_kaggle_bearer_token(repo_root: Path = REPO_ROOT) -> str | None:
    env_file = repo_root / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line.startswith("KAGGLE_API_TOKEN="):
                return line.split("=", 1)[1].strip().strip("'\"") or None
    return None


def fetch_api_names(repo_root: Path = REPO_ROOT) -> tuple[list[str], str | None]:
    """Nombres de archivo de la competencia y un error (None si todo fue bien).

    Sin token devuelve ([], None): fuente no disponible, no es un fallo de la API.
    Nunca imprime el token ni lo incluye en el error.
    """
    token = get_kaggle_bearer_token(repo_root)
    if not token:
        return [], None

    base_url = "https://www.kaggle.com/api/v1/competitions/data/list/gemma-4-developer-agent"
    names: list[str] = []
    page_token = None
    while True:
        url = f"{base_url}?pageToken={page_token}" if page_token else base_url
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode())
        except Exception as e:
            # str(e) de urllib no contiene cabeceras; se omite igualmente el request.
            return names, f"{type(e).__name__}: {e}"
        names.extend(f.get("name", "") for f in data.get("files", []))
        page_token = data.get("nextPageToken")
        if not page_token:
            return names, None


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def load_manifest_hashes(manifest: Path) -> dict[str, str]:
    """SHA-256 -> etiqueta del manifiesto versionado ({} si no existe)."""
    if not manifest.exists():
        return {}
    data = json.loads(manifest.read_text(encoding="utf-8"))
    return {f["sha256"]: f"manifest:{f['path']}" for f in data.get("files", []) if f.get("sha256")}


def load_local_data_hashes(data_dir: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    if data_dir.exists():
        for p in data_dir.rglob("*"):
            if p.is_file():
                with contextlib.suppress(Exception):
                    hashes[compute_sha256(p)] = f"data/{p.relative_to(data_dir).as_posix()}"
    return hashes


def build_reference(repo_root: Path, fetch: FetchFn | None = None) -> Reference:
    ref = Reference()

    manifest = load_manifest_hashes(repo_root / MANIFEST_REL)
    ref.hashes.update(manifest)
    ref.sources["manifiesto a_kit/manifest.json (hashes únicos)"] = len(manifest)

    local = load_local_data_hashes(repo_root / EXPERIMENT_DIR / "data")
    for h, label in local.items():
        ref.hashes.setdefault(h, label)
    ref.sources["datos locales data/ (hashes únicos)"] = len(local)

    names, error = (fetch or (lambda: fetch_api_names(repo_root)))()
    ref.names.update(n for n in names if n)
    ref.sources["API de Kaggle (nombres)"] = len(names)
    if error:
        ref.errors.append(f"Error al consultar la API de Kaggle: {error}")
    return ref


def tracked_files(repo_root: Path) -> list[str]:
    res = subprocess.run(
        ["git", "ls-files", EXPERIMENT_DIR],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=True,
    )
    return [line.strip() for line in res.stdout.splitlines() if line.strip()]


def find_collisions(repo_root: Path, tracked: list[str], ref: Reference) -> tuple[list[str], list[str]]:
    path_collisions: list[str] = []
    hash_collisions: list[str] = []
    for rel_path in tracked:
        if rel_path in OWN_FILES:
            continue
        full_path = repo_root / rel_path
        if not full_path.is_file():
            continue
        sub_name = rel_path.removeprefix(f"{EXPERIMENT_DIR}/")
        if sub_name in ref.names or rel_path in ref.names:
            path_collisions.append(f"Ruta exacta: {rel_path}")
        sha = compute_sha256(full_path)
        if sha in ref.hashes:
            hash_collisions.append(f"SHA-256 idéntico ({sha[:12]}...): {rel_path} == {ref.hashes[sha]}")
    return path_collisions, hash_collisions


def run(
    repo_root: Path = REPO_ROOT,
    fetch: FetchFn | None = None,
    tracked: list[str] | None = None,
) -> int:
    print("1. Construyendo la lista de referencia de la competencia...")
    ref = build_reference(repo_root, fetch)
    for source, count in ref.sources.items():
        print(f"   {source}: {count} archivos")
    for err in ref.errors:
        print(f"   [ERROR] {err}", file=sys.stderr)

    if tracked is None:
        tracked = tracked_files(repo_root)
    print(f"\n2. Archivos versionados en {EXPERIMENT_DIR}: {len(tracked)}")

    path_collisions, hash_collisions = find_collisions(repo_root, tracked, ref)
    print("\n3. Resultados de la comprobación:")
    print(f"   Coincidencias por ruta/nombre: {len(path_collisions)}")
    for pc in path_collisions:
        print(f"     [ALERTA] {pc}")
    print(f"   Coincidencias por hash SHA-256: {len(hash_collisions)}")
    for hc in hash_collisions:
        print(f"     [ALERTA] {hc}")

    if path_collisions or hash_collisions:
        print(
            "\n[FALLO] Se detectaron archivos de la competencia versionados en git.",
            file=sys.stderr,
        )
        return EXIT_COLLISION

    if ref.total == 0:
        print(
            "\n[SIN REFERENCIA] No se pudo comprobar: la lista de referencia está vacía "
            "(sin manifiesto, sin data/ y sin acceso a la API).",
            file=sys.stderr,
        )
        return EXIT_UNVERIFIED
    if ref.errors:
        print(
            "\n[INCOMPLETO] No se pudo comprobar del todo: falló una fuente de referencia "
            "(ver errores). Sin coincidencias contra las fuentes disponibles, pero no se "
            "da por verificado.",
            file=sys.stderr,
        )
        return EXIT_UNVERIFIED

    used = ", ".join(f"{s}: {n}" for s, n in ref.sources.items() if n)
    print(f"\n[VERIFICADO] Sin coincidencias por nombre ni por SHA-256 contra: {used}.")
    return EXIT_OK


def main() -> int:
    return run()


if __name__ == "__main__":
    sys.exit(main())
