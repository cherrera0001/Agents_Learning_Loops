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
    # La consulta toca varias acciones de los episodios reales. Con «agregar dependencia opcional» la única
    # acción relevante quedaba en 0,0106 sobre un umbral de 0,01, y cada episodio nuevo la baja: las aristas
    # viejas decaen con el reloj. Esto da margen, no lo quita; ver #162.
    consulta = "documentar el experimento y registrar el episodio"
    monkeypatch.setattr(sys, "argv", ["devlog", "recall", consulta])
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


def _fixed_episodes(monkeypatch):
    """Fija la lista de episodios que ve `main()` y la devuelve (el último decide las pruebas)."""
    episodes = devlog.load_episodes()
    monkeypatch.setattr(devlog, "load_episodes", lambda: episodes)
    return episodes


def test_recall_command_uses_every_episode(tmp_path, monkeypatch, capsys):
    """`recall` por `main()` responde con todos los episodios, también el último."""
    episodes = _fixed_episodes(monkeypatch)
    query = episodes[-1]["goal"]
    full = devlog.recall(devlog.rebuild(episodes), query, 5, None)
    assert full != devlog.recall(devlog.rebuild(episodes[:-1]), query, 5, None)  # control
    assert full != devlog.recall(devlog.rebuild(episodes[:10]), query, 5, None)  # control
    monkeypatch.setattr(devlog, "MEMORY_PATH", tmp_path / "dev_memory.json")
    monkeypatch.setattr(sys, "argv", ["devlog", "recall", query])
    devlog.main()
    assert capsys.readouterr().out.rstrip("\n") == full.rstrip("\n")


def test_rebuild_command_uses_every_episode(tmp_path, monkeypatch, capsys):
    """El comando `rebuild` guarda el grafo de todos los episodios, también el último."""
    episodes = _fixed_episodes(monkeypatch)
    expected, without_last = tmp_path / "expected.json", tmp_path / "without_last.json"
    devlog.rebuild(episodes).save(expected)
    devlog.rebuild(episodes[:-1]).save(without_last)
    assert expected.read_bytes() != without_last.read_bytes()  # control
    target = tmp_path / "dev_memory.json"
    monkeypatch.setattr(devlog, "MEMORY_PATH", target)
    monkeypatch.setattr(sys, "argv", ["devlog", "rebuild"])
    devlog.main()
    capsys.readouterr()
    assert target.read_bytes() == expected.read_bytes()


def test_recall_command_honours_n(tmp_path, monkeypatch, capsys):
    episodes = _fixed_episodes(monkeypatch)
    graph = devlog.rebuild(episodes)
    query = "agregar dependencia opcional"
    one, five = devlog.recall(graph, query, 1, None), devlog.recall(graph, query, 5, None)
    assert one != five  # control: -n cambia la respuesta
    monkeypatch.setattr(devlog, "MEMORY_PATH", tmp_path / "dev_memory.json")
    monkeypatch.setattr(sys, "argv", ["devlog", "recall", "-n", "1", query])
    devlog.main()
    assert capsys.readouterr().out.rstrip("\n") == one.rstrip("\n")


@pytest.mark.parametrize(("flags", "uses_fastembed"), [([], False), (["--embedder", "fastembed"], True)])
def test_recall_command_honours_embedder(tmp_path, monkeypatch, capsys, flags, uses_fastembed):
    _fixed_episodes(monkeypatch)
    sentinel = object()
    seen = []
    monkeypatch.setattr(devlog, "FastEmbedEmbedder", lambda: sentinel)
    monkeypatch.setattr(devlog, "recall", lambda mg, query, n, embedder: seen.append(embedder) or "")
    monkeypatch.setattr(devlog, "MEMORY_PATH", tmp_path / "dev_memory.json")
    monkeypatch.setattr(sys, "argv", ["devlog", "recall", *flags, "consulta"])
    devlog.main()
    capsys.readouterr()
    assert seen == [sentinel if uses_fastembed else None]
