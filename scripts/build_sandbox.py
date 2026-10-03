#!/usr/bin/env python3
"""Reconstrucción verificada de la imagen Docker swebench-sandbox:latest.

Consume el lockfile de ruedas adicionales fijadas de PyPI, verifica sus hashes SHA-256
y tamaños en bytes, prepara el contexto de construcción junto al wheelhouse local de Kaggle
y construye la imagen Docker del sandbox de evaluación local. Es un instrumento de ensayo local: la
imagen que resulte no es, por sí sola, el entorno del experimento (pre-registro, A.1).

Códigos de salida: 0 correcto; 2 error de uso de la CLI; 3 lockfile desfasado o entrada local
ausente o mal formada; 4 fallo de red; 5 hash o tamaño erróneo; 6 fallo de docker.

Importante: la imagen NO decide qué ruedas instala el arnés. Esas salen del directorio de ruedas del
host y de su caché (ver docs/propuesta_entorno_fastapi_v2.md). Este guion solo reconstruye la imagen.
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

EXIT_INPUTS = 3
EXIT_NETWORK = 4
EXIT_INTEGRITY = 5
EXIT_DOCKER = 6


class StaleLockfileError(FileNotFoundError):
    """El lockfile declara algo (una rueda excluida) que el origen no tiene."""


class LockfileError(ValueError):
    """El lockfile tiene una entrada mal formada."""


class BuildContextError(FileExistsError, ValueError):
    """El directorio de construcción ya tiene un wheelhouse de una ejecución anterior."""


class NetworkFailure(RuntimeError):
    """La descarga de una rueda falló por la red, antes de poder verificar nada."""


class IntegrityError(ValueError):
    """Los bytes de una rueda no coinciden con el tamaño o el SHA-256 declarados."""


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
    if not isinstance(data, dict):
        raise LockfileError(f"La raíz del lockfile debe ser un objeto JSON, no {type(data).__name__}.")
    if "packages" not in data or not isinstance(data["packages"], list):
        raise ValueError("El lockfile debe contener una lista bajo la clave 'packages'.")
    return dict(data)


def check_wheel_filename(filename: object) -> str:
    """Rechaza nombres que no sean un nombre de archivo de rueda simple (sin rutas)."""
    if not isinstance(filename, str) or not filename:
        raise LockfileError(f"Nombre de rueda inválido en el lockfile: {filename!r}")
    if "/" in filename or "\\" in filename or ".." in filename or Path(filename).name != filename:
        raise LockfileError(f"El nombre de rueda no puede contener separadores de ruta: {filename!r}")
    if not filename.endswith(".whl"):
        raise LockfileError(f"El nombre de rueda debe terminar en .whl: {filename!r}")
    return filename


def excluded_filenames(lock_data: dict[str, Any]) -> set[str]:
    """Nombres de las ruedas excluidas; una entrada mal formada es un error, no se descarta."""
    entries = lock_data.get("excluded_wheels", [])
    if not isinstance(entries, list):
        raise LockfileError("'excluded_wheels' debe ser una lista.")
    names: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or "filename" not in entry:
            raise LockfileError(f"Entrada mal formada en 'excluded_wheels': {entry!r}")
        names.add(check_wheel_filename(entry["filename"]))
    return names


def validate_inputs(
    lock_data: dict[str, Any],
    full_wheels_dir: Path,
    docker_dir: Path,
) -> set[str]:
    """Valida lockfile y directorios locales antes de descargar nada; devuelve las exclusiones."""
    for pkg in lock_data["packages"]:
        if not isinstance(pkg, dict):
            raise LockfileError(f"Entrada mal formada en 'packages': {pkg!r}")
        for key in ("filename", "sha256", "size_bytes", "url"):
            if key not in pkg:
                raise LockfileError(f"Falta la clave {key!r} en un paquete del lockfile: {pkg!r}")
        check_wheel_filename(pkg["filename"])
    excluded = excluded_filenames(lock_data)
    added = {pkg["filename"] for pkg in lock_data["packages"]}
    contradictory = sorted(added & excluded)
    if contradictory:
        raise ValueError(f"Ruedas a la vez añadidas y excluidas: {', '.join(contradictory)}")
    _check_source_dirs(full_wheels_dir, docker_dir, excluded)
    return excluded


def _check_source_dirs(source_wheels_dir: Path, docker_source_dir: Path, excluded: set[str]) -> None:
    if not source_wheels_dir.exists():
        raise FileNotFoundError(f"Directorio de ruedas de origen no encontrado: {source_wheels_dir}")
    if not docker_source_dir.exists():
        raise FileNotFoundError(f"Directorio de Docker no encontrado: {docker_source_dir}")
    if (
        not (docker_source_dir / "Dockerfile.public").exists()
        and not (docker_source_dir / "Dockerfile").exists()
    ):
        raise FileNotFoundError(f"No se encontró Dockerfile.public en {docker_source_dir}")
    # Una exclusión declarada que no corresponde a ninguna rueda del origen indica un lockfile
    # desfasado: el entorno resultante no sería el que el lockfile describe.
    missing = sorted(name for name in excluded if not (source_wheels_dir / name).is_file())
    if missing:
        raise StaleLockfileError(
            f"El lockfile excluye ruedas que no están en {source_wheels_dir}: {', '.join(missing)}. "
            "Si ya las apartaste del directorio que lee el arnés, indica con --full-wheels-dir el "
            "directorio de origen completo, que es el que lee este guion."
        )


def _verify_bytes(
    filename: str, data_size: int, data_sha: str, expected_size: int, expected_sha: str
) -> None:
    if data_size != expected_size:
        raise IntegrityError(
            f"Tamaño inesperado en {filename}: obtenido {data_size}, esperado {expected_size}"
        )
    if data_sha != expected_sha:
        raise IntegrityError(
            f"Hash SHA-256 no coincide en {filename}: obtenido {data_sha}, esperado {expected_sha}"
        )


def download_and_verify_wheels(
    packages: list[dict[str, Any]],
    cache_dir: Path,
) -> list[Path]:
    """Descarga (si no existen) y verifica las ruedas declaradas en el lockfile."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    verified_paths: list[Path] = []

    for pkg in packages:
        filename = check_wheel_filename(pkg["filename"])
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
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = resp.read()
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                raise NetworkFailure(f"Fallo de red al descargar {filename}: {exc}") from exc
            # Se verifica en memoria: unos bytes que no coinciden no llegan al disco.
            _verify_bytes(
                filename, len(data), hashlib.sha256(data).hexdigest().lower(), expected_size, expected_sha
            )
            target_path.write_bytes(data)

        # Verificación estricta post-descarga/lectura
        actual_size = target_path.stat().st_size
        actual_sha = compute_sha256(target_path)
        _verify_bytes(filename, actual_size, actual_sha, expected_size, expected_sha)

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
    excluded = excluded_wheels or set()
    _check_source_dirs(source_wheels_dir, docker_source_dir, excluded)
    contradictory = sorted(aw.name for aw in additional_wheels if aw.name in excluded)
    if contradictory:
        raise ValueError(f"Ruedas a la vez añadidas y excluidas: {', '.join(contradictory)}")

    dockerfile_src = docker_source_dir / "Dockerfile.public"
    if not dockerfile_src.exists():
        dockerfile_src = docker_source_dir / "Dockerfile"

    build_dir.mkdir(parents=True, exist_ok=True)
    dest_wheels_dir = build_dir / "wheels"
    # Un contexto reutilizado puede conservar ruedas retiradas del origen.
    # El cache de descargas puede existir; el wheelhouse de construcción no.
    if dest_wheels_dir.exists():
        raise BuildContextError(
            f"El contexto de construcción ya existe: {dest_wheels_dir}. No se reutiliza, porque puede "
            "conservar ruedas retiradas del origen. Bórralo o indica otro directorio con --build-dir."
        )
    dest_wheels_dir.mkdir(parents=True)

    # Copiar ruedas base del wheelhouse (omitiendo las excluidas justificadamente)
    for item in source_wheels_dir.glob("*.whl"):
        if item.name not in excluded:
            shutil.copy2(item, dest_wheels_dir / item.name)

    # Copiar ruedas adicionales verificadas
    for aw in additional_wheels:
        if aw.name not in excluded:
            shutil.copy2(aw, dest_wheels_dir / aw.name)

    # Copiar Dockerfile.public como Dockerfile
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
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        raise RuntimeError("No se encontró el ejecutable 'docker' en el PATH.") from exc
    if res.returncode != 0:
        sys.stderr.write(res.stderr)
        raise RuntimeError(f"Fallo en docker build (código {res.returncode}):\n{res.stderr or res.stdout}")

    # Obtener ID exacto no truncado
    id_cmd = ["docker", "images", "--no-trunc", "--format", "{{.ID}}", tag]
    try:
        id_res = subprocess.run(id_cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        raise RuntimeError("No se encontró el ejecutable 'docker' en el PATH.") from exc
    if id_res.returncode != 0 or not id_res.stdout.strip():
        raise RuntimeError(f"No se pudo obtener el ID de la imagen {tag}")

    image_id = id_res.stdout.strip().splitlines()[0]
    return image_id, all_tags


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Reconstruye la imagen Docker del sandbox con verificación estricta de lockfile."
    )
    parser.add_argument("--lockfile", type=Path, default=DEFAULT_LOCKFILE, help="Ruta al lockfile JSON")
    parser.add_argument(
        "--wheels-dir", type=Path, default=DEFAULT_WHEELS_DIR, help="Ruta al wheelhouse local de Kaggle"
    )
    parser.add_argument(
        "--full-wheels-dir",
        type=Path,
        default=None,
        help=(
            "Directorio de origen COMPLETO que lee este guion para construir la imagen, si difiere del "
            "que usa el arnés (--wheels-dir, ya recortado). Por defecto, el mismo que --wheels-dir"
        ),
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
    return parser


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada de la CLI de reconstrucción del sandbox."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")
    args = _build_parser().parse_args(argv)
    full_wheels_dir: Path = args.full_wheels_dir or args.wheels_dir

    try:
        print("1. Cargando y validando lockfile y directorios locales...")
        lock_data = load_lockfile(args.lockfile)
        packages = lock_data["packages"]
        excluded = validate_inputs(lock_data, full_wheels_dir, args.docker_dir)
        print(f"   Total de paquetes declarados: {len(packages)}")

        print("2. Verificando y descargando ruedas adicionales...")
        cache_dir = args.build_dir / "pypi_cache"
        verified_wheels = download_and_verify_wheels(packages, cache_dir)

        print("3. Preparando contexto de construcción en build_sandbox...")
        if excluded:
            print(f"   Exclusiones justificadas por lockfile: {len(excluded)} ruedas")
        prepare_build_context(
            full_wheels_dir,
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
    except NetworkFailure as exc:
        print(f"[ERROR red] {exc}", file=sys.stderr)
        return EXIT_NETWORK
    except IntegrityError as exc:
        print(f"[ERROR integridad] {exc}", file=sys.stderr)
        return EXIT_INTEGRITY
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"[ERROR lockfile o entradas locales] {exc}", file=sys.stderr)
        return EXIT_INPUTS
    except RuntimeError as exc:
        print(f"[ERROR docker] {exc}", file=sys.stderr)
        return EXIT_DOCKER

    print("[OK] Imagen construida exitosamente:")
    print(f"     Tags: {', '.join(tags)}")
    print(f"     Image ID: {image_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
