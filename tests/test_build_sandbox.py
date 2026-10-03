"""Pruebas unitarias para el script de construcción del sandbox (scripts/build_sandbox.py)."""

from __future__ import annotations

import hashlib
import io
import json
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from scripts import build_sandbox
from scripts.build_sandbox import (
    EXIT_DOCKER,
    EXIT_INPUTS,
    EXIT_INTEGRITY,
    EXIT_NETWORK,
    IntegrityError,
    LockfileError,
    NetworkFailure,
    build_docker_image,
    compute_sha256,
    download_and_verify_wheels,
    load_lockfile,
    main,
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


# --- Descarga, cache y verificación ---------------------------------------------------------------


def _fake_urlopen(monkeypatch: pytest.MonkeyPatch, payload: bytes, calls: list[str] | None = None) -> None:
    class Fake:
        def __enter__(self) -> io.BytesIO:
            return io.BytesIO(payload)

        def __exit__(self, *args: Any) -> None:
            pass

    def opener(req: Any, timeout: int = 60) -> Fake:
        if calls is not None:
            calls.append(req.full_url)
        return Fake()

    monkeypatch.setattr(urllib.request, "urlopen", opener)


def _pkg(payload: bytes, filename: str = "ok-1.0-py3-none-any.whl", **overrides: Any) -> dict[str, Any]:
    pkg: dict[str, Any] = {
        "filename": filename,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size_bytes": len(payload),
        "url": "https://example.invalid/" + filename,
    }
    pkg.update(overrides)
    return pkg


def test_download_writes_verified_file_and_returns_its_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = b"good wheel bytes"
    calls: list[str] = []
    _fake_urlopen(monkeypatch, payload, calls)

    paths = download_and_verify_wheels([_pkg(payload)], tmp_path / "cache")

    assert paths == [tmp_path / "cache" / "ok-1.0-py3-none-any.whl"]
    assert paths[0].read_bytes() == payload
    assert calls == ["https://example.invalid/ok-1.0-py3-none-any.whl"]


def test_download_accepts_uppercase_sha_in_lockfile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = b"good wheel bytes"
    _fake_urlopen(monkeypatch, payload)
    pkg = _pkg(payload)
    pkg["sha256"] = pkg["sha256"].upper()

    assert len(download_and_verify_wheels([pkg], tmp_path / "cache")) == 1


def test_valid_cache_is_not_downloaded_again(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = b"cached"
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "ok-1.0-py3-none-any.whl").write_bytes(payload)

    def boom(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("no debe descargar")

    monkeypatch.setattr(urllib.request, "urlopen", boom)

    assert len(download_and_verify_wheels([_pkg(payload)], cache)) == 1


def test_corrupt_cache_is_replaced_by_a_verified_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = b"the real bytes"
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "ok-1.0-py3-none-any.whl").write_bytes(b"x" * len(payload))  # mismo tamaño, otro hash
    _fake_urlopen(monkeypatch, payload)

    (path,) = download_and_verify_wheels([_pkg(payload)], cache)

    assert path.read_bytes() == payload


def test_corrupt_cache_with_bad_download_fails_instead_of_being_accepted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = b"the real bytes"
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "ok-1.0-py3-none-any.whl").write_bytes(b"corrupt")
    _fake_urlopen(monkeypatch, b"still wrong")

    with pytest.raises(IntegrityError):
        download_and_verify_wheels([_pkg(payload)], cache)


def test_network_error_is_a_network_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: Any, **kwargs: Any) -> None:
        raise urllib.error.URLError("sin red")

    monkeypatch.setattr(urllib.request, "urlopen", fail)

    with pytest.raises(NetworkFailure, match=r"ok-1\.0"):
        download_and_verify_wheels([_pkg(b"x")], tmp_path / "cache")


@pytest.mark.parametrize("bad", ["../evil.whl", "sub/evil.whl", "sub\\evil.whl", "evil.txt", ""])
def test_filename_with_path_parts_is_rejected(tmp_path: Path, bad: str) -> None:
    with pytest.raises(LockfileError):
        download_and_verify_wheels([_pkg(b"x", filename=bad)], tmp_path / "cache")


# --- Contexto de construcción ---------------------------------------------------------------------


def test_prepare_build_context_copies_only_wheels_and_both_shims(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "a-1.0-py3-none-any.whl").write_bytes(b"a")
    (source / "notes.txt").write_text("no", encoding="utf-8")
    (source / "b-1.0.tar.gz").write_bytes(b"sdist")
    docker = _minimal_docker(tmp_path)
    (docker / "imp.py").write_text("# imp\n", encoding="utf-8")
    (docker / "telnetlib.py").write_text("# telnet\n", encoding="utf-8")

    build = tmp_path / "build"
    prepare_build_context(source, docker, [], build)

    assert sorted(p.name for p in (build / "wheels").iterdir()) == ["a-1.0-py3-none-any.whl"]
    assert (build / "imp.py").read_text(encoding="utf-8") == "# imp\n"
    assert (build / "telnetlib.py").read_text(encoding="utf-8") == "# telnet\n"
    assert (build / "Dockerfile").read_text(encoding="utf-8") == "FROM scratch\n"


def test_prepare_build_context_falls_back_to_plain_dockerfile(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    docker = tmp_path / "docker"
    docker.mkdir()
    (docker / "Dockerfile").write_text("FROM plain\n", encoding="utf-8")

    prepare_build_context(source, docker, [], tmp_path / "build")

    assert (tmp_path / "build" / "Dockerfile").read_text(encoding="utf-8") == "FROM plain\n"


def test_prepare_build_context_without_dockerfile_creates_nothing(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    docker = tmp_path / "docker"
    docker.mkdir()

    with pytest.raises(FileNotFoundError, match="Dockerfile"):
        prepare_build_context(source, docker, [], tmp_path / "build")

    assert not (tmp_path / "build").exists()


def test_prepare_build_context_without_source_or_docker_dir_fails(tmp_path: Path) -> None:
    docker = _minimal_docker(tmp_path)
    with pytest.raises(FileNotFoundError, match="ruedas de origen"):
        prepare_build_context(tmp_path / "nope", docker, [], tmp_path / "build")
    source = tmp_path / "source"
    source.mkdir()
    with pytest.raises(FileNotFoundError, match="Docker"):
        prepare_build_context(source, tmp_path / "nope", [], tmp_path / "build")


# --- docker build con subprocess simulado ---------------------------------------------------------


class _Run:
    def __init__(self, results: list[subprocess.CompletedProcess[str]]) -> None:
        self.results = results
        self.cmds: list[list[str]] = []

    def __call__(self, cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        self.cmds.append(cmd)
        return self.results.pop(0)


def _done(code: int = 0, out: str = "", err: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], code, out, err)


def test_build_docker_image_passes_tags_and_no_cache_and_returns_full_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = _Run([_done(), _done(out="sha256:abc\nsha256:old\n")])
    monkeypatch.setattr(subprocess, "run", run)

    image_id, tags = build_docker_image(tmp_path, "img:v2", ["img:alias"], no_cache=True)

    assert run.cmds[0] == ["docker", "build", "--no-cache", "-t", "img:v2", "-t", "img:alias", str(tmp_path)]
    assert run.cmds[1] == ["docker", "images", "--no-trunc", "--format", "{{.ID}}", "img:v2"]
    assert (image_id, tags) == ("sha256:abc", ["img:v2", "img:alias"])


def test_build_docker_image_without_no_cache_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run = _Run([_done(), _done(out="sha256:abc\n")])
    monkeypatch.setattr(subprocess, "run", run)

    build_docker_image(tmp_path, "img:v2")

    assert run.cmds[0] == ["docker", "build", "-t", "img:v2", str(tmp_path)]


def test_build_docker_image_failure_code_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", _Run([_done(code=7, err="boom")]))

    with pytest.raises(RuntimeError, match=r"código 7"):
        build_docker_image(tmp_path, "img:v2")


def test_build_docker_image_without_id_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", _Run([_done(), _done(out="")]))

    with pytest.raises(RuntimeError, match="ID de la imagen"):
        build_docker_image(tmp_path, "img:v2")


# --- main: cableado y códigos de salida -----------------------------------------------------------


def _write_lock(tmp_path: Path, **extra: Any) -> Path:
    lock = tmp_path / "x.lock"
    data: dict[str, Any] = {"packages": [_pkg(b"p")], "excluded_wheels": []}
    data.update(extra)
    lock.write_text(json.dumps(data), encoding="utf-8")
    return lock


def _env(tmp_path: Path) -> tuple[Path, Path, Path]:
    full = tmp_path / "full"
    full.mkdir()
    (full / "starlette-1.6.0-py3-none-any.whl").write_bytes(b"new")
    (full / "starlette-0.47.3-py3-none-any.whl").write_bytes(b"old")
    return full, _minimal_docker(tmp_path), tmp_path / "build"


def test_main_passes_lockfile_exclusions_and_full_dir_to_prepare(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    full, docker, build = _env(tmp_path)
    lock = _write_lock(tmp_path, excluded_wheels=[{"filename": "starlette-1.6.0-py3-none-any.whl"}])
    seen: dict[str, Any] = {}
    verified = [tmp_path / "v.whl"]

    monkeypatch.setattr(build_sandbox, "download_and_verify_wheels", lambda pk, cache: verified)

    def fake_prepare(src: Path, dk: Path, extra: list[Path], bd: Path, excluded_wheels: set[str]) -> None:
        seen.update(src=src, dk=dk, extra=extra, bd=bd, excluded=excluded_wheels)
        (bd / "wheels").mkdir(parents=True)

    monkeypatch.setattr(build_sandbox, "prepare_build_context", fake_prepare)
    code = main(
        [
            "--lockfile", str(lock), "--wheels-dir", str(tmp_path / "trimmed"),
            "--full-wheels-dir", str(full), "--docker-dir", str(docker),
            "--build-dir", str(build), "--skip-docker-build",
        ]
    )  # fmt: skip

    assert code == 0
    assert seen == {
        "src": full, "dk": docker, "extra": verified, "bd": build,
        "excluded": {"starlette-1.6.0-py3-none-any.whl"},
    }  # fmt: skip


def test_main_without_full_dir_uses_wheels_dir_and_calls_docker_with_tags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    full, docker, build = _env(tmp_path)
    lock = _write_lock(tmp_path)
    seen: dict[str, Any] = {}
    monkeypatch.setattr(build_sandbox, "download_and_verify_wheels", lambda pk, cache: [])

    def fake_prepare(src: Path, dk: Path, extra: list[Path], bd: Path, excluded_wheels: set[str]) -> None:
        seen["src"] = src
        (bd / "wheels").mkdir(parents=True)

    def fake_build(bd: Path, tag: str, extra_tags: list[str], no_cache: bool) -> tuple[str, list[str]]:
        seen["build"] = (bd, tag, extra_tags, no_cache)
        return "sha256:id", [tag, *extra_tags]

    monkeypatch.setattr(build_sandbox, "prepare_build_context", fake_prepare)
    monkeypatch.setattr(build_sandbox, "build_docker_image", fake_build)
    code = main(
        [
            "--lockfile", str(lock), "--wheels-dir", str(full), "--docker-dir", str(docker),
            "--build-dir", str(build), "--tag", "t:1", "--extra-tag", "t:2", "--no-cache",
        ]
    )  # fmt: skip

    assert code == 0
    assert seen["src"] == full
    assert seen["build"] == (build, "t:1", ["t:2"], True)


def test_skip_docker_build_never_calls_docker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    full, docker, build = _env(tmp_path)
    lock = _write_lock(tmp_path)
    monkeypatch.setattr(build_sandbox, "download_and_verify_wheels", lambda pk, cache: [])

    def boom(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("no debe llamar a docker")

    monkeypatch.setattr(build_sandbox, "build_docker_image", boom)

    code = main(
        ["--lockfile", str(lock), "--wheels-dir", str(full), "--docker-dir", str(docker),
         "--build-dir", str(build), "--skip-docker-build"]
    )  # fmt: skip

    assert code == 0
    assert (build / "wheels" / "starlette-1.6.0-py3-none-any.whl").exists()


def test_main_validates_local_inputs_before_downloading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    full, docker, build = _env(tmp_path)
    lock = _write_lock(tmp_path, excluded_wheels=[{"filename": "starlette-9.9.9-py3-none-any.whl"}])

    def boom(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("no debe descargar antes de validar")

    monkeypatch.setattr(build_sandbox, "download_and_verify_wheels", boom)

    code = main(
        ["--lockfile", str(lock), "--wheels-dir", str(full), "--docker-dir", str(docker),
         "--build-dir", str(build), "--skip-docker-build"]
    )  # fmt: skip

    assert code == EXIT_INPUTS
    assert not build.exists()


def test_main_stale_lockfile_message_points_to_full_wheels_dir(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    full, docker, build = _env(tmp_path)
    lock = _write_lock(tmp_path, excluded_wheels=[{"filename": "starlette-9.9.9-py3-none-any.whl"}])

    main(["--lockfile", str(lock), "--wheels-dir", str(full), "--docker-dir", str(docker),
          "--build-dir", str(build)])  # fmt: skip

    assert "--full-wheels-dir" in capsys.readouterr().err


@pytest.mark.parametrize(
    "excluded",
    [
        ["starlette-1.6.0-py3-none-any.whl"],
        [{"motivo": "sin nombre"}],
        [{"filename": "../x.whl"}],
        "no es lista",
    ],
)
def test_main_rejects_malformed_exclusions_instead_of_dropping_them(tmp_path: Path, excluded: Any) -> None:
    full, docker, build = _env(tmp_path)
    lock = _write_lock(tmp_path, excluded_wheels=excluded)

    code = main(["--lockfile", str(lock), "--wheels-dir", str(full), "--docker-dir", str(docker),
                 "--build-dir", str(build), "--skip-docker-build"])  # fmt: skip

    assert code == EXIT_INPUTS


def test_main_exit_code_for_network_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    full, docker, build = _env(tmp_path)
    lock = _write_lock(tmp_path)

    def fail(*args: Any, **kwargs: Any) -> None:
        raise urllib.error.URLError("sin red")

    monkeypatch.setattr(urllib.request, "urlopen", fail)

    code = main(["--lockfile", str(lock), "--wheels-dir", str(full), "--docker-dir", str(docker),
                 "--build-dir", str(build)])  # fmt: skip

    assert code == EXIT_NETWORK


def test_main_exit_code_for_wrong_hash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    full, docker, build = _env(tmp_path)
    lock = _write_lock(tmp_path)
    _fake_urlopen(monkeypatch, b"not p")

    code = main(["--lockfile", str(lock), "--wheels-dir", str(full), "--docker-dir", str(docker),
                 "--build-dir", str(build)])  # fmt: skip

    assert code == EXIT_INTEGRITY


def test_main_exit_code_for_docker_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    full, docker, build = _env(tmp_path)
    lock = _write_lock(tmp_path)
    monkeypatch.setattr(build_sandbox, "download_and_verify_wheels", lambda pk, cache: [])
    monkeypatch.setattr(subprocess, "run", _Run([_done(code=1, err="boom")]))

    code = main(["--lockfile", str(lock), "--wheels-dir", str(full), "--docker-dir", str(docker),
                 "--build-dir", str(build)])  # fmt: skip

    assert code == EXIT_DOCKER
