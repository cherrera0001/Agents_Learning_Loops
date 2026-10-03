"""Pruebas unitarias para el script de construcción del sandbox (scripts/build_sandbox.py)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from scripts.build_sandbox import (
    compute_sha256,
    download_and_verify_wheels,
    load_lockfile,
    prepare_build_context,
)


def test_compute_sha256(tmp_path: Path) -> None:
    test_file = tmp_path / "sample.txt"
    content = b"hello swe-bench sandbox"
    test_file.write_bytes(content)
    expected = hashlib.sha256(content).hexdigest()
    assert compute_sha256(test_file) == expected


def test_load_lockfile_valid(tmp_path: Path) -> None:
    lock_path = tmp_path / "test.lock"
    data: dict[str, Any] = {"packages": [{"name": "pkg1", "version": "1.0"}]}
    lock_path.write_text(json.dumps(data), encoding="utf-8")
    loaded = load_lockfile(lock_path)
    assert loaded["packages"][0]["name"] == "pkg1"


def test_load_lockfile_invalid(tmp_path: Path) -> None:
    lock_path = tmp_path / "invalid.lock"
    lock_path.write_text(json.dumps({"other": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="packages"):
        load_lockfile(lock_path)


def test_download_and_verify_wheels_cached(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    wheel_content = b"dummy wheel bytes 12345"
    sha = hashlib.sha256(wheel_content).hexdigest()
    size = len(wheel_content)
    wheel_file = cache_dir / "test_pkg-1.0-py3-none-any.whl"
    wheel_file.write_bytes(wheel_content)

    packages = [
        {
            "name": "test-pkg",
            "version": "1.0",
            "filename": "test_pkg-1.0-py3-none-any.whl",
            "sha256": sha,
            "size_bytes": size,
            "url": "http://invalid.url/not/called",
        }
    ]
    verified = download_and_verify_wheels(packages, cache_dir)
    assert len(verified) == 1
    assert verified[0] == wheel_file


def test_download_and_verify_wheels_corrupted_download_hash_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Prueba que bytes descargados con hash corrupto lanzan ValueError concreto."""
    import io
    import urllib.request

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    corrupted_bytes = b"corrupted bytes from network"
    fake_response = io.BytesIO(corrupted_bytes)

    class FakeUrlopen:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def __enter__(self) -> io.BytesIO:
            return fake_response

        def __exit__(self, *args: Any) -> None:
            pass

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=60: FakeUrlopen())

    packages = [
        {
            "name": "corrupt-pkg",
            "version": "1.0",
            "filename": "corrupt_pkg-1.0-py3-none-any.whl",
            "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "size_bytes": len(corrupted_bytes),
            "url": "http://simulated.network/corrupt.whl",
        }
    ]

    with pytest.raises(ValueError, match=r"Hash SHA-256 no coincide en corrupt_pkg-1\.0-py3-none-any\.whl"):
        download_and_verify_wheels(packages, cache_dir)


def test_download_and_verify_wheels_corrupted_download_size_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Prueba que bytes descargados con tamaño inesperado lanzan ValueError concreto."""
    import io
    import urllib.request

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    truncated_bytes = b"short"
    fake_response = io.BytesIO(truncated_bytes)

    class FakeUrlopen:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def __enter__(self) -> io.BytesIO:
            return fake_response

        def __exit__(self, *args: Any) -> None:
            pass

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=60: FakeUrlopen())

    packages = [
        {
            "name": "size-pkg",
            "version": "1.0",
            "filename": "size_pkg-1.0-py3-none-any.whl",
            "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "size_bytes": 99999,  # Tamaño esperado mucho mayor
            "url": "http://simulated.network/size.whl",
        }
    ]

    with pytest.raises(ValueError, match=r"Tamaño inesperado en size_pkg-1\.0-py3-none-any\.whl"):
        download_and_verify_wheels(packages, cache_dir)


def test_prepare_build_context(tmp_path: Path) -> None:
    src_wheels = tmp_path / "src_wheels"
    src_wheels.mkdir()
    (src_wheels / "base-1.0-py3-none-any.whl").write_bytes(b"base wheel")

    docker_dir = tmp_path / "docker"
    docker_dir.mkdir()
    (docker_dir / "Dockerfile.public").write_text("FROM python:3.13-slim\n", encoding="utf-8")
    (docker_dir / "imp.py").write_text("# imp shim\n", encoding="utf-8")

    extra_dir = tmp_path / "extra"
    extra_dir.mkdir()
    extra_wheel = extra_dir / "extra-2.0-py3-none-any.whl"
    extra_wheel.write_bytes(b"extra wheel")

    build_dir = tmp_path / "build"

    prepare_build_context(src_wheels, docker_dir, [extra_wheel], build_dir)

    assert (build_dir / "Dockerfile").exists()
    assert (build_dir / "imp.py").exists()
    assert (build_dir / "wheels" / "base-1.0-py3-none-any.whl").exists()
    assert (build_dir / "wheels" / "extra-2.0-py3-none-any.whl").exists()


def test_prepare_build_context_rejects_reuse(tmp_path: Path) -> None:
    """Una rueda retirada del origen no debe sobrevivir en un contexto reutilizado."""
    source = tmp_path / "source"
    source.mkdir()
    old_wheel = source / "old-1.0-py3-none-any.whl"
    old_wheel.write_bytes(b"old")
    docker = tmp_path / "docker"
    docker.mkdir()
    (docker / "Dockerfile.public").write_text("FROM scratch\n", encoding="utf-8")
    build = tmp_path / "build"
    prepare_build_context(source, docker, [], build)
    old_wheel.unlink()
    (source / "new-1.0-py3-none-any.whl").write_bytes(b"new")

    with pytest.raises(FileExistsError):
        prepare_build_context(source, docker, [], build)

    assert not (build / "wheels" / "new-1.0-py3-none-any.whl").exists()


def test_prepare_build_context_allows_existing_download_cache(tmp_path: Path) -> None:
    """El cache previo no impide preparar un wheelhouse nuevo."""
    source = tmp_path / "source"
    source.mkdir()
    docker = tmp_path / "docker"
    docker.mkdir()
    (docker / "Dockerfile.public").write_text("FROM scratch\n", encoding="utf-8")
    build = tmp_path / "build"
    cache = build / "pypi_cache"
    cache.mkdir(parents=True)
    cached_wheel = cache / "extra-1.0-py3-none-any.whl"
    cached_wheel.write_bytes(b"extra")

    prepare_build_context(source, docker, [cached_wheel], build)

    assert (build / "wheels" / cached_wheel.name).read_bytes() == b"extra"


def test_prepare_build_context_respects_excluded_wheels(tmp_path: Path) -> None:
    """Las ruedas marcadas como excluidas no se copian al wheelhouse de construcción."""
    source = tmp_path / "source"
    source.mkdir()
    (source / "starlette-0.47.3-py3-none-any.whl").write_bytes(b"compatible")
    (source / "starlette-1.6.0-py3-none-any.whl").write_bytes(b"incompatible")

    docker = tmp_path / "docker"
    docker.mkdir()
    (docker / "Dockerfile.public").write_text("FROM scratch\n", encoding="utf-8")

    build = tmp_path / "build"
    excluded = {"starlette-1.6.0-py3-none-any.whl"}

    prepare_build_context(source, docker, [], build, excluded_wheels=excluded)

    assert (build / "wheels" / "starlette-0.47.3-py3-none-any.whl").exists()
    assert not (build / "wheels" / "starlette-1.6.0-py3-none-any.whl").exists()


def _minimal_docker(tmp_path: Path) -> Path:
    docker = tmp_path / "docker"
    docker.mkdir()
    (docker / "Dockerfile.public").write_text("FROM scratch\n", encoding="utf-8")
    return docker


def test_prepare_build_context_fails_if_declared_exclusion_is_missing(tmp_path: Path) -> None:
    """Una exclusión del lockfile que no existe en el origen es un lockfile desfasado: falla."""
    source = tmp_path / "source"
    source.mkdir()
    (source / "starlette-0.47.3-py3-none-any.whl").write_bytes(b"ok")

    with pytest.raises(FileNotFoundError, match=r"starlette-1\.6\.0"):
        prepare_build_context(
            source,
            _minimal_docker(tmp_path),
            [],
            tmp_path / "build",
            excluded_wheels={"starlette-1.6.0-py3-none-any.whl"},
        )

    assert not (tmp_path / "build" / "wheels").exists()


def test_prepare_build_context_rejects_wheel_both_added_and_excluded(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "dup-1.0-py3-none-any.whl").write_bytes(b"x")
    added = tmp_path / "dup-1.0-py3-none-any.whl"
    added.write_bytes(b"x")

    with pytest.raises(ValueError, match="añadidas y excluidas"):
        prepare_build_context(
            source,
            _minimal_docker(tmp_path),
            [added],
            tmp_path / "build",
            excluded_wheels={"dup-1.0-py3-none-any.whl"},
        )


def test_download_with_wrong_hash_leaves_nothing_in_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unos bytes sin verificar no se escriben al disco, ni siquiera en el cache."""
    import io
    import urllib.request

    payload = b"bytes that do not match the lock"

    class FakeUrlopen:
        def __enter__(self) -> io.BytesIO:
            return io.BytesIO(payload)

        def __exit__(self, *args: Any) -> None:
            pass

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=60: FakeUrlopen())
    cache = tmp_path / "cache"
    packages = [
        {
            "filename": "bad-1.0-py3-none-any.whl",
            "sha256": "b" * 64,
            "size_bytes": len(payload),
            "url": "https://example.invalid/bad.whl",
        }
    ]

    with pytest.raises(ValueError, match="Hash SHA-256 no coincide"):
        download_and_verify_wheels(packages, cache)

    assert not (cache / "bad-1.0-py3-none-any.whl").exists()
