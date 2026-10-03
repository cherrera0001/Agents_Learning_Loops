"""Pruebas de scripts/verify_no_competition_data.py (sin red ni datos reales)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts import verify_no_competition_data as v

EXP = v.EXPERIMENT_DIR


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write(root: Path, rel: str, data: bytes) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)


def _manifest(root: Path, hashes: list[str]) -> None:
    files = [{"path": f"f{i}", "size": 1, "sha256": h} for i, h in enumerate(hashes)]
    _write(root, v.MANIFEST_REL, json.dumps({"files": files}).encode())


def _no_api() -> tuple[list[str], str | None]:
    return [], None


def test_referencia_vacia_no_verifica(tmp_path, capsys):
    _write(tmp_path, f"{EXP}/mine.txt", b"propio")
    code = v.run(tmp_path, fetch=_no_api, tracked=[f"{EXP}/mine.txt"])
    out = capsys.readouterr()
    assert code == v.EXIT_UNVERIFIED == 2
    assert "VERIFICADO" not in out.out.replace("[SIN REFERENCIA]", "")
    assert "no se pudo comprobar" in out.err.lower()


def test_coincidencia_por_hash(tmp_path, capsys):
    secret = b"dato de la competencia"
    _write(tmp_path, f"{EXP}/copia.bin", secret)
    _manifest(tmp_path, [_sha(secret)])
    code = v.run(tmp_path, fetch=_no_api, tracked=[f"{EXP}/copia.bin", v.MANIFEST_REL])
    out = capsys.readouterr()
    assert code == v.EXIT_COLLISION == 1
    assert "copia.bin" in out.out
    assert "FALLO" in out.err


def test_sin_coincidencias_verifica_e_informa_fuentes(tmp_path, capsys):
    _write(tmp_path, f"{EXP}/mine.txt", b"propio")
    _manifest(tmp_path, [_sha(b"otro contenido")])
    code = v.run(tmp_path, fetch=_no_api, tracked=[f"{EXP}/mine.txt"])
    out = capsys.readouterr().out
    assert code == v.EXIT_OK
    assert "[VERIFICADO]" in out
    assert "manifest.json (hashes únicos): 1 archivos" in out


def test_archivos_propios_del_kit_no_cuentan(tmp_path):
    kit = f"{EXP}/conditions/a_kit"
    _write(tmp_path, f"{kit}/download_kit.py", b"codigo")
    _write(tmp_path, f"{kit}/README.md", b"doc")
    _manifest(tmp_path, [_sha(b"codigo"), _sha(b"doc")])
    tracked = [v.MANIFEST_REL, f"{kit}/download_kit.py", f"{kit}/README.md"]
    assert v.run(tmp_path, fetch=_no_api, tracked=tracked) == v.EXIT_OK


def test_coincidencia_por_nombre_de_la_api(tmp_path):
    _write(tmp_path, f"{EXP}/train.csv", b"x")
    code = v.run(tmp_path, fetch=lambda: (["train.csv"], None), tracked=[f"{EXP}/train.csv"])
    assert code == v.EXIT_COLLISION


def test_error_de_api_no_se_traga(tmp_path, capsys):
    _write(tmp_path, f"{EXP}/mine.txt", b"propio")
    _manifest(tmp_path, [_sha(b"otro")])
    code = v.run(tmp_path, fetch=lambda: ([], "HTTPError: 401"), tracked=[f"{EXP}/mine.txt"])
    err = capsys.readouterr().err
    assert code == v.EXIT_UNVERIFIED
    assert "401" in err


def test_hashes_de_data_local_cuentan(tmp_path):
    _write(tmp_path, f"{EXP}/data/a.bin", b"secreto")
    _write(tmp_path, f"{EXP}/copia.bin", b"secreto")
    code = v.run(tmp_path, fetch=_no_api, tracked=[f"{EXP}/copia.bin"])
    assert code == v.EXIT_COLLISION


def test_fetch_sin_token_no_es_error(tmp_path):
    assert v.fetch_api_names(tmp_path) == ([], None)


def test_error_de_red_no_expone_token(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("KAGGLE_API_TOKEN=SECRETO123\n", encoding="utf-8")

    def boom(*a, **k):
        raise OSError("sin red")

    monkeypatch.setattr(v.urllib.request, "urlopen", boom)
    names, error = v.fetch_api_names(tmp_path)
    assert names == []
    assert error is not None and "SECRETO123" not in error


@pytest.mark.parametrize("line", ["KAGGLE_API_TOKEN=", "OTRA=1"])
def test_token_vacio_o_ausente(tmp_path, line):
    (tmp_path / ".env").write_text(line + "\n", encoding="utf-8")
    assert v.get_kaggle_bearer_token(tmp_path) is None
