#!/usr/bin/env python3
"""Reconstrucción verificada de la imagen Docker swebench-sandbox:latest.

Consume el lockfile de ruedas adicionales fijadas de PyPI, verifica sus hashes SHA-256
y tamaños en bytes, prepara el contexto de construcción junto al wheelhouse local de Kaggle
y construye la imagen Docker del sandbox de evaluación local. Es un instrumento de ensayo local: la
imagen que resulte no es, por sí sola, el entorno del experimento (pre-registro, A.1).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOCKFILE = (
    REPO_ROOT / "experiments" / "gemma_developer_agent" / "docs" / "desviaciones_entorno_wheels.lock"
)
DEFAULT_WHEELS_DIR = REPO_ROOT / "experiments" / "gemma_developer_agent" / "data" / "wheels"
DEFAULT_DOCKER_DIR = REPO_ROOT / "experiments" / "gemma_developer_agent" / "data" / "docker"
DEFAULT_BUILD_DIR = REPO_ROOT / "experiments" / "gemma_developer_agent" / "data" / "build_sandbox"
DEFAULT_TAG = "swebench-sandbox:latest"


def compute_sha256(file_path: Path) -> str:
    """Calcula el hash SHA-256 de un archivo en bloques de 64 KB."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().lower()


def load_lockfile(lockfile_path: Path) -> dict[str, Any]:
    """Carga y valida el archivo lockfile JSON de ruedas adicionales."""
    if not lockfile_path.exists():
        raise FileNotFoundError(f"No se encontró el lockfile: {lockfile_path}")
    with open(lockfile_path, encoding="utf-8") as f:
        data = json.load(f)
    if "packages" not in data or not isinstance(data["packages"], list):
        raise ValueError("El lockfile debe contener una lista bajo la clave 'packages'.")
    return dict(data)


def download_and_verify_wheels(
    packages: list[dict[str, Any]],
    cache_dir: Path,
) -> list[Path]:
    """Descarga (si no existen) y verifica las ruedas declaradas en el lockfile."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    verified_paths: list[Path] = []

    for pkg in packages:
        filename = pkg["filename"]
        expected_sha = pkg["sha256"].lower()
        expected_size = pkg["size_bytes"]
        url = pkg["url"]
        target_path = cache_dir / filename

        # Si el archivo no existe o su tamaño/hash difiere, se descarga
        needs_download = True
        if target_path.exists():
            actual_size = target_path.stat().st_size
            if actual_size == expected_size and compute_sha256(target_path) == expected_sha:
                needs_download = False

        if needs_download:
            print(f"Descargando {filename} desde {url}...")
            req = urllib.request.Request(url, headers={"User-Agent": "ALL-Sandbox-Builder/1.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
            # Se verifica en memoria: unos bytes que no coinciden no llegan al disco.
            if len(data) != expected_size:
                raise ValueError(
                    f"Tamaño inesperado en {filename}: obtenido {len(data)}, esperado {expected_size}"
                )
            downloaded_sha = hashlib.sha256(data).hexdigest().lower()
            if downloaded_sha != expected_sha:
                raise ValueError(
                    f"Hash SHA-256 no coincide en {filename}: obtenido {downloaded_sha}, "
                    f"esperado {expected_sha}"
                )
            target_path.write_bytes(data)

        # Verificación estricta post-descarga/lectura
        actual_size = target_path.stat().st_size
        if actual_size != expected_size:
            raise ValueError(
                f"Tamaño inesperado en {filename}: obtenido {actual_size}, esperado {expected_size}"
            )
        actual_sha = compute_sha256(target_path)
        if actual_sha != expected_sha:
            raise ValueError(
                f"Hash SHA-256 no coincide en {filename}: obtenido {actual_sha}, esperado {expected_sha}"
            )

        print(f"  [OK] {filename} ({actual_size} bytes, sha256: {actual_sha[:16]}...)")
        verified_paths.append(target_path)

    return verified_paths


def prepare_build_context(
    source_wheels_dir: Path,
    docker_source_dir: Path,
    additional_wheels: list[Path],
    build_dir: Path,
    excluded_wheels: set[str] | None = None,
) -> None:
    """Prepara el directorio de construcción Docker con todos los artefactos requeridos."""
    if not source_wheels_dir.exists():
        raise FileNotFoundError(f"Directorio de ruedas de origen no encontrado: {source_wheels_dir}")
    if not docker_source_dir.exists():
        raise FileNotFoundError(f"Directorio de Docker no encontrado: {docker_source_dir}")

    excluded = excluded_wheels or set()
    # Una exclusión declarada que no corresponde a ninguna rueda del origen indica un lockfile
    # desfasado: el entorno resultante no sería el que el lockfile describe.
    missing = sorted(name for name in excluded if not (source_wheels_dir / name).is_file())
    if missing:
        raise FileNotFoundError(
            f"El lockfile excluye ruedas que no están en {source_wheels_dir}: {', '.join(missing)}"
        )
    contradictory = sorted(aw.name for aw in additional_wheels if aw.name in excluded)
    if contradictory:
        raise ValueError(f"Ruedas a la vez añadidas y excluidas: {', '.join(contradictory)}")

    build_dir.mkdir(parents=True, exist_ok=True)
    dest_wheels_dir = build_dir / "wheels"
    # Un contexto reutilizado puede conservar ruedas retiradas del origen.
    # El cache de descargas puede existir; el wheelhouse de construcción no.
    dest_wheels_dir.mkdir(parents=True, exist_ok=False)

    # Copiar ruedas base del wheelhouse (omitiendo las excluidas justificadamente)
    for item in source_wheels_dir.glob("*.whl"):
        if item.name not in excluded:
            shutil.copy2(item, dest_wheels_dir / item.name)

    # Copiar ruedas adicionales verificadas
    for aw in additional_wheels:
        if aw.name not in excluded:
            shutil.copy2(aw, dest_wheels_dir / aw.name)

    # Copiar Dockerfile.public como Dockerfile
    dockerfile_src = docker_source_dir / "Dockerfile.public"
    if not dockerfile_src.exists():
        dockerfile_src = docker_source_dir / "Dockerfile"
    if not dockerfile_src.exists():
        raise FileNotFoundError(f"No se encontró Dockerfile.public en {docker_source_dir}")
    shutil.copy2(dockerfile_src, build_dir / "Dockerfile")

    # Copiar shims imp.py y telnetlib.py si existen
    for shim in ("imp.py", "telnetlib.py"):
        shim_src = docker_source_dir / shim
        if shim_src.exists():
            shutil.copy2(shim_src, build_dir / shim)


def build_docker_image(
    build_dir: Path,
    tag: str,
    extra_tags: list[str] | None = None,
    no_cache: bool = False,
) -> tuple[str, list[str]]:
    """Ejecuta docker build y retorna el ID completo de la imagen generada y sus tags."""
    cmd = ["docker", "build"]
    if no_cache:
        cmd.append("--no-cache")
    cmd.extend(["-t", tag])
    all_tags = [tag]
    if extra_tags:
        for et in extra_tags:
            cmd.extend(["-t", et])
            all_tags.append(et)
    cmd.append(str(build_dir))

    print(f"Ejecutando: {' '.join(cmd)}")
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        sys.stderr.write(res.stderr)
        raise RuntimeError(f"Fallo en docker build (código {res.returncode}):\n{res.stderr or res.stdout}")

    # Obtener ID exacto no truncado
    id_cmd = ["docker", "images", "--no-trunc", "--format", "{{.ID}}", tag]
    id_res = subprocess.run(id_cmd, capture_output=True, text=True, check=False)
    if id_res.returncode != 0 or not id_res.stdout.strip():
        raise RuntimeError(f"No se pudo obtener el ID de la imagen {tag}")

    image_id = id_res.stdout.strip().splitlines()[0]
    return image_id, all_tags


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada de la CLI de reconstrucción del sandbox."""
    parser = argparse.ArgumentParser(
        description="Reconstruye la imagen Docker del sandbox con verificación estricta de lockfile."
    )
    parser.add_argument("--lockfile", type=Path, default=DEFAULT_LOCKFILE, help="Ruta al lockfile JSON")
    parser.add_argument(
        "--wheels-dir", type=Path, default=DEFAULT_WHEELS_DIR, help="Ruta al wheelhouse local de Kaggle"
    )
    parser.add_argument(
        "--docker-dir", type=Path, default=DEFAULT_DOCKER_DIR, help="Ruta a los archivos Docker de Kaggle"
    )
    parser.add_argument(
        "--build-dir", type=Path, default=DEFAULT_BUILD_DIR, help="Ruta del contexto temporal de construcción"
    )
    parser.add_argument("--tag", type=str, default=DEFAULT_TAG, help="Tag principal de la imagen Docker")
    parser.add_argument(
        "--extra-tag",
        type=str,
        action="append",
        default=[],
        help=(
            "Tags adicionales para la imagen (los tags son mutables; "
            "el identificador inmutable es el Image ID/digest)"
        ),
    )
    parser.add_argument(
        "--no-cache", action="store_true", help="Fuerza reconstrucción de Docker sin usar capas en caché"
    )
    parser.add_argument(
        "--skip-docker-build", action="store_true", help="Solo prepara el contexto sin invocar docker build"
    )
    args = parser.parse_args(argv)

    print("1. Cargando lockfile de dependencias adicionales...")
    lock_data = load_lockfile(args.lockfile)
    packages = lock_data["packages"]
    print(f"   Total de paquetes declarados: {len(packages)}")

    print("2. Verificando y descargando ruedas adicionales...")
    cache_dir = args.build_dir / "pypi_cache"
    verified_wheels = download_and_verify_wheels(packages, cache_dir)

    print("3. Preparando contexto de construcción en build_sandbox...")
    excluded = {
        pkg["filename"]
        for pkg in lock_data.get("excluded_wheels", [])
        if isinstance(pkg, dict) and "filename" in pkg
    }
    if excluded:
        print(f"   Exclusiones justificadas por lockfile: {len(excluded)} ruedas")
    prepare_build_context(
        args.wheels_dir,
        args.docker_dir,
        verified_wheels,
        args.build_dir,
        excluded_wheels=excluded,
    )
    total_wheels = len(list((args.build_dir / "wheels").glob("*.whl")))
    print(f"   Contexto listo con {total_wheels} ruedas en {args.build_dir / 'wheels'}")

    if args.skip_docker_build:
        print("[OK] Preparación completada (docker build omitido).")
        return 0

    print("4. Construyendo imagen Docker...")
    image_id, tags = build_docker_image(args.build_dir, args.tag, args.extra_tag, args.no_cache)
    print("[OK] Imagen construida exitosamente:")
    print(f"     Tags: {', '.join(tags)}")
    print(f"     Image ID: {image_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
