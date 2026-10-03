#!/usr/bin/env python3
"""Comprobación de higiene contra la lista oficial de archivos de la competencia.

Alcance real: solo los archivos que devuelve ``git ls-files experiments/gemma_developer_agent``.
No inspecciona el resto del repositorio ni el historial.

Fuentes de referencia (el informe dice cuántos elementos aporta cada una):
  - manifiesto versionado conditions/a_kit/manifest.json (SHA-256);
  - datos locales descargados en data/ (SHA-256), si existen;
  - lista de la API de Kaggle (nombres), si hay KAGGLE_API_TOKEN en .env.

Códigos de salida:
  0  sin coincidencias. Si solo hubo manifiesto, la etiqueta es «VERIFICADO PARCIAL»;
     «VERIFICADO» a secas exige además API o data/.
  1  hay archivos versionados que coinciden con la competencia.
  2  no se pudo comprobar: referencia vacía, o una fuente falló (API, manifiesto, data/),
     o se pidió --require-full y solo hubo manifiesto. Nunca es «verificado».

Todos los mensajes de resultado van por stdout, en orden.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EXPERIMENT_DIR = "experiments/gemma_developer_agent"
MANIFEST_REL = f"{EXPERIMENT_DIR}/conditions/a_kit/manifest.json"
# Archivos propios de la carpeta del kit: se excluyen solo de la comparación por nombre.
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

SRC_MANIFEST = "manifiesto a_kit/manifest.json (hashes SHA-256 únicos)"
SRC_DATA = "datos locales data/ (hashes SHA-256 únicos)"
SRC_API = "API de Kaggle (nombres de archivo)"

API_TIMEOUT = 30
MAX_PAGES = 1000
_SHA_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_TOKEN_RE = re.compile(r"^\s*(?:export\s+)?KAGGLE_API_TOKEN\s*=\s*(.*?)\s*$")


@dataclass
class Reference:
    """Lista de referencia con el recuento por fuente y los errores al obtenerla."""

    hashes: dict[str, str] = field(default_factory=dict)  # sha256 -> etiqueta
    names: set[str] = field(default_factory=set)
    sources: dict[str, int] = field(default_factory=dict)  # fuente -> nº de elementos
    errors: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return sum(self.sources.values())

    @property
    def complete(self) -> bool:
        """Hubo referencia más amplia que el manifiesto (API o data/)."""
        return self.sources.get(SRC_API, 0) > 0 or self.sources.get(SRC_DATA, 0) > 0


FetchFn = Callable[[], tuple[list[str], str | None]]


def get_kaggle_bearer_token(repo_root: Path = REPO_ROOT) -> str | None:
    env_file = repo_root / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            m = _TOKEN_RE.match(line)
            if m:
                return m.group(1).strip("'\"") or None
    return None


def fetch_api_names(repo_root: Path = REPO_ROOT) -> tuple[list[str], str | None]:
    """Nombres de archivo de la competencia y un error (None si todo fue bien).

    Sin token devuelve ([], None): fuente no disponible, no es un fallo de la API.
    Con token, una respuesta sin nombres útiles es un error. Los nombres ya leídos se
    conservan ante un error parcial. Nunca imprime el token ni lo incluye en el error.
    """
    token = get_kaggle_bearer_token(repo_root)
    if not token:
        return [], None

    base_url = "https://www.kaggle.com/api/v1/competitions/data/list/gemma-4-developer-agent"
    names: list[str] = []
    seen_tokens: set[str] = set()
    page_token: str | None = None
    for _ in range(MAX_PAGES):
        url = base_url
        if page_token:
            url = f"{base_url}?pageToken={urllib.parse.quote(page_token, safe='')}"
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(req, timeout=API_TIMEOUT) as resp:
                data = json.loads(resp.read().decode())
            if not isinstance(data, dict):
                return names, "respuesta de la API con formato inesperado (no es un objeto)"
            files = data.get("files")
            if not isinstance(files, list):
                return names, "respuesta de la API sin la clave 'files'"
            names.extend(
                f["name"]
                for f in files
                if isinstance(f, dict) and isinstance(f.get("name"), str) and f["name"]
            )
            nxt = data.get("nextPageToken")
        except Exception as e:
            return names, f"{type(e).__name__}: {e}"
        if not nxt:
            break
        if not isinstance(nxt, str) or nxt in seen_tokens:
            return names, "paginación de la API inválida (token repetido o no textual)"
        seen_tokens.add(nxt)
        page_token = nxt
    else:
        return names, "la API devolvió demasiadas páginas"

    if not names:
        return names, "la API respondió sin ningún nombre de archivo útil"
    return names, None


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def load_manifest_hashes(manifest: Path) -> tuple[dict[str, str], str | None]:
    """(SHA-256 minúsculas -> etiqueta, error). Sin manifiesto: ({}, None)."""
    if not manifest.exists():
        return {}, None
    hashes: dict[str, str] = {}
    try:
        data = json.loads(manifest.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict) or not isinstance(data.get("files"), list):
            return {}, "manifiesto ilegible: se esperaba un objeto con la lista 'files'"
        for i, entry in enumerate(data["files"]):
            if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
                return hashes, f"manifiesto: la entrada {i} no tiene 'path'"
            sha = entry.get("sha256")
            if not isinstance(sha, str) or not _SHA_RE.match(sha):
                return hashes, f"manifiesto: sha256 inválido en {entry['path']}"
            hashes[sha.lower()] = f"manifest:{entry['path']}"
    except (OSError, ValueError) as e:
        return {}, f"manifiesto ilegible ({type(e).__name__}: {e})"
    return hashes, None


def load_local_data_hashes(data_dir: Path) -> tuple[dict[str, str], list[str]]:
    hashes: dict[str, str] = {}
    errors: list[str] = []
    if data_dir.exists():
        for p in sorted(data_dir.rglob("*")):
            if p.is_file():
                rel = p.relative_to(data_dir).as_posix()
                try:
                    hashes[compute_sha256(p)] = f"data/{rel}"
                except OSError as e:
                    errors.append(f"archivo ilegible en data/: {rel} ({type(e).__name__})")
    return hashes, errors


def build_reference(repo_root: Path, fetch: FetchFn | None = None) -> Reference:
    ref = Reference()

    manifest, m_err = load_manifest_hashes(repo_root / MANIFEST_REL)
    ref.hashes.update(manifest)
    ref.sources[SRC_MANIFEST] = len(manifest)
    if m_err:
        ref.errors.append(m_err)

    local, l_errs = load_local_data_hashes(repo_root / EXPERIMENT_DIR / "data")
    for h, label in local.items():
        ref.hashes.setdefault(h, label)
    ref.sources[SRC_DATA] = len(local)
    ref.errors.extend(l_errs)

    names, error = (fetch or (lambda: fetch_api_names(repo_root)))()
    ref.names.update(n for n in names if n)
    ref.sources[SRC_API] = len(ref.names)
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
        full_path = repo_root / rel_path
        if not full_path.is_file():
            continue
        if rel_path not in OWN_FILES:
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
    require_full: bool = False,
) -> int:
    print("1. Construyendo la lista de referencia de la competencia...")
    ref = build_reference(repo_root, fetch)
    for source, count in ref.sources.items():
        print(f"   {source}: {count}")
    for err in ref.errors:
        print(f"   [ERROR] {err}")

    if tracked is None:
        tracked = tracked_files(repo_root)
    print(f"\n2. Archivos versionados en {EXPERIMENT_DIR} (git ls-files): {len(tracked)}")

    path_collisions, hash_collisions = find_collisions(repo_root, tracked, ref)
    print("\n3. Resultados de la comprobación:")
    print(f"   Coincidencias por ruta/nombre: {len(path_collisions)}")
    for pc in path_collisions:
        print(f"     [ALERTA] {pc}")
    print(f"   Coincidencias por hash SHA-256: {len(hash_collisions)}")
    for hc in hash_collisions:
        print(f"     [ALERTA] {hc}")

    print()
    if path_collisions or hash_collisions:
        print("[FALLO] Se detectaron archivos de la competencia versionados en git.")
        return EXIT_COLLISION

    if ref.total == 0:
        print(
            "[SIN REFERENCIA] No se pudo comprobar: la lista de referencia está vacía "
            "(sin manifiesto, sin data/ y sin acceso a la API)."
        )
        return EXIT_UNVERIFIED
    if ref.errors:
        print(
            "[INCOMPLETO] No se pudo comprobar del todo: falló una fuente de referencia "
            "(ver errores). No se da por verificado."
        )
        return EXIT_UNVERIFIED

    used = "; ".join(f"{s}: {n}" for s, n in ref.sources.items() if n)
    if not ref.complete:
        n = ref.sources[SRC_MANIFEST]
        print(
            f"[VERIFICADO PARCIAL: solo manifiesto del kit, {n} hashes; no cubre el resto "
            "de los datos de la competencia]"
        )
        if require_full:
            print("--require-full: se exige además la API de Kaggle o data/. Salida 2.")
            return EXIT_UNVERIFIED
        return EXIT_OK

    print(f"[VERIFICADO] Sin coincidencias en git ls-files {EXPERIMENT_DIR} contra: {used}.")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0] if __doc__ else None)
    parser.add_argument(
        "--require-full",
        action="store_true",
        help="salir con 2 si solo se comparó contra el manifiesto (sin API ni data/)",
    )
    args = parser.parse_args(argv)
    return run(require_full=args.require_full)


if __name__ == "__main__":
    sys.exit(main())
