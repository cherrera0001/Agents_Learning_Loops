"""`learning/dev_memory.json` no se versiona (#96): los episodios son la única fuente de verdad.

Fija lo esencial de esa decisión: el archivo está ignorado y fuera del índice de git, `recall` funciona
sin él (y no lo lee), y `rebuild` desde los episodios es determinista.
"""

import json
import shutil
import subprocess
import sys

import pytest

from scripts import devlog

GIT = shutil.which("git")
needs_git_checkout = pytest.mark.skipif(
    GIT is None or not (devlog.ROOT / ".git").exists(), reason="requiere un checkout de git"
)
MEMORY = "learning/dev_memory.json"


def _git(*args):
    assert GIT is not None
    return subprocess.run(
        [GIT, "-C", str(devlog.ROOT), *args], capture_output=True, text=True, encoding="utf-8"
    )


@needs_git_checkout
def test_dev_memory_is_not_tracked_and_is_ignored():
    assert MEMORY not in _git("ls-files").stdout.splitlines()
    assert _git("check-ignore", "-q", MEMORY).returncode == 0  # 0 = ignorado


@needs_git_checkout
def test_control_a_tracked_derived_file_is_not_reported_as_ignored():
    """Control: `check-ignore` no responde 0 para cualquier ruta; un episodio sí está versionado."""
    episode = "learning/episodes/001-v0.1-bootstrap.json"
    assert episode in _git("ls-files").stdout.splitlines()
    assert _git("check-ignore", "-q", episode).returncode == 1


def _recall(monkeypatch, capsys, memory_path):
    monkeypatch.setattr(devlog, "MEMORY_PATH", memory_path)
    monkeypatch.setattr(sys, "argv", ["devlog", "recall", "agregar dependencia opcional"])
    devlog.main()
    return capsys.readouterr().out


def test_recall_works_without_the_file(tmp_path, monkeypatch, capsys):
    absent = tmp_path / "dev_memory.json"
    out = _recall(monkeypatch, capsys, absent)
    assert "RETRIEVE:" in out and "Lecciones:" in out
    assert "(sin experiencia relacionada)" not in out  # sí hay experiencia en los episodios reales
    assert not absent.exists()  # recall no lo escribe


def test_recall_ignores_a_stale_local_file(tmp_path, monkeypatch, capsys):
    """Control: un archivo local viejo o corrupto no cambia la respuesta; recall lee los episodios."""
    absent = _recall(monkeypatch, capsys, tmp_path / "absent.json")
    stale = tmp_path / "dev_memory.json"
    stale.write_text("{ no es un grafo", encoding="utf-8")
    assert _recall(monkeypatch, capsys, stale) == absent


def test_rebuild_from_episodes_is_deterministic(tmp_path, monkeypatch, capsys):
    first, second = tmp_path / "a.json", tmp_path / "b.json"
    for target in (first, second):
        monkeypatch.setattr(devlog, "MEMORY_PATH", target)
        monkeypatch.setattr(sys, "argv", ["devlog", "rebuild"])
        devlog.main()
    capsys.readouterr()
    assert first.read_bytes() and first.read_bytes() == second.read_bytes()
    assert json.loads(first.read_text("utf-8"))["nodes"]


def test_rebuild_output_follows_the_episodes(tmp_path):
    """Control: si `rebuild` ignorara los episodios, la prueba de determinismo sería tautológica."""
    episodes = devlog.load_episodes()
    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    devlog.rebuild(episodes).save(before)
    extra = dict(episodes[-1], seq=episodes[-1]["seq"] + 1, id="extra", goal="meta nueva distinta")
    devlog.rebuild([*episodes, extra]).save(after)
    assert before.read_bytes() != after.read_bytes()
