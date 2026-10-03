"""Pruebas de scripts/verify_no_competition_data.py (sin red ni datos reales)."""

from __future__ import annotations

import hashlib
import io
import json
import urllib.error
from pathlib import Path

import pytest

from scripts import verify_no_competition_data as v

EXP = v.EXPERIMENT_DIR
KIT = f"{EXP}/conditions/a_kit"


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


class FakeResp:
    def __init__(self, payload):
        self._raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()

    def read(self):
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _api(monkeypatch, tmp_path, responses, calls=None):
    """Fija un token y sustituye urlopen por una cola de respuestas (o excepciones)."""
    (tmp_path / ".env").write_text("KAGGLE_API_TOKEN=SECRETO123\n", encoding="utf-8")
    queue = list(responses)

    def fake(req, timeout=None):
        if calls is not None:
            calls.append((req.full_url, timeout))
        item = queue.pop(0)
        if isinstance(item, BaseException):
            raise item
        return FakeResp(item)

    monkeypatch.setattr(v.urllib.request, "urlopen", fake)


# ---------- flujo principal ----------


def test_referencia_vacia_no_verifica(tmp_path, capsys):
    _write(tmp_path, f"{EXP}/mine.txt", b"propio")
    code = v.run(tmp_path, fetch=_no_api, tracked=[f"{EXP}/mine.txt"])
    out = capsys.readouterr().out
    assert code == v.EXIT_UNVERIFIED == 2
    assert "[SIN REFERENCIA] No se pudo comprobar" in out
    assert "VERIFICADO" not in out


def test_coincidencia_por_hash(tmp_path, capsys):
    secret = b"dato de la competencia"
    _write(tmp_path, f"{EXP}/copia.bin", secret)
    _manifest(tmp_path, [_sha(secret)])
    code = v.run(tmp_path, fetch=_no_api, tracked=[f"{EXP}/copia.bin", v.MANIFEST_REL])
    out = capsys.readouterr().out
    assert code == v.EXIT_COLLISION == 1
    assert "copia.bin" in out and "[FALLO]" in out
    assert "VERIFICADO" not in out


def test_solo_manifiesto_es_parcial(tmp_path, capsys):
    _write(tmp_path, f"{EXP}/mine.txt", b"propio")
    _manifest(tmp_path, [_sha(b"otro contenido")])
    code = v.run(tmp_path, fetch=_no_api, tracked=[f"{EXP}/mine.txt"])
    out = capsys.readouterr().out
    assert code == v.EXIT_OK
    assert (
        "[VERIFICADO PARCIAL: solo manifiesto del kit, 1 hashes; no cubre el resto de los "
        "datos de la competencia]" in out
    )
    assert "[VERIFICADO]" not in out
    assert "por nombre" not in out


def test_require_full_con_solo_manifiesto_sale_2(tmp_path, capsys):
    _write(tmp_path, f"{EXP}/mine.txt", b"propio")
    _manifest(tmp_path, [_sha(b"otro")])
    code = v.run(tmp_path, fetch=_no_api, tracked=[f"{EXP}/mine.txt"], require_full=True)
    out = capsys.readouterr().out
    assert code == v.EXIT_UNVERIFIED
    assert "PARCIAL" in out and "--require-full" in out


def test_completo_con_data_lista_fuentes_y_recuentos(tmp_path, capsys):
    _write(tmp_path, f"{EXP}/data/a.bin", b"secreto")
    _write(tmp_path, f"{EXP}/mine.txt", b"propio")
    _manifest(tmp_path, [_sha(b"x"), _sha(b"y")])
    code = v.run(tmp_path, fetch=_no_api, tracked=[f"{EXP}/mine.txt"], require_full=True)
    out = capsys.readouterr().out
    assert code == v.EXIT_OK
    last = out.strip().splitlines()[-1]
    assert last.startswith("[VERIFICADO]") and "PARCIAL" not in last
    assert f"{v.SRC_MANIFEST}: 2" in last
    assert f"{v.SRC_DATA}: 1" in last
    assert "git ls-files" in last


def test_completo_con_api_lista_nombres(tmp_path, capsys):
    _write(tmp_path, f"{EXP}/mine.txt", b"propio")
    _manifest(tmp_path, [_sha(b"x")])
    code = v.run(tmp_path, fetch=lambda: (["a.csv", "b.csv"], None), tracked=[f"{EXP}/mine.txt"])
    last = capsys.readouterr().out.strip().splitlines()[-1]
    assert code == v.EXIT_OK
    assert last.startswith("[VERIFICADO]")
    assert f"{v.SRC_API}: 2" in last


def test_coincidencia_por_nombre_de_la_api(tmp_path, capsys):
    _write(tmp_path, f"{EXP}/train.csv", b"x")
    code = v.run(tmp_path, fetch=lambda: (["train.csv"], None), tracked=[f"{EXP}/train.csv"])
    out = capsys.readouterr().out
    assert code == v.EXIT_COLLISION
    assert "Ruta exacta" in out


def test_error_de_api_no_se_traga_y_no_pierde_nombres(tmp_path, capsys):
    _write(tmp_path, f"{EXP}/mine.txt", b"propio")
    _manifest(tmp_path, [_sha(b"otro")])
    code = v.run(tmp_path, fetch=lambda: (["a.csv"], "HTTPError: 401"), tracked=[f"{EXP}/mine.txt"])
    out = capsys.readouterr().out
    assert code == v.EXIT_UNVERIFIED
    assert "401" in out and "[INCOMPLETO]" in out
    assert f"{v.SRC_API}: 1" in out  # el nombre ya leído cuenta


def test_nombres_leidos_antes_del_error_provocan_coincidencia(tmp_path):
    _write(tmp_path, f"{EXP}/train.csv", b"x")
    code = v.run(tmp_path, fetch=lambda: (["train.csv"], "URLError"), tracked=[f"{EXP}/train.csv"])
    assert code == v.EXIT_COLLISION


def test_data_local_es_recursivo(tmp_path):
    _write(tmp_path, f"{EXP}/data/sub/hondo/a.bin", b"secreto")
    _write(tmp_path, f"{EXP}/copia.bin", b"secreto")
    code = v.run(tmp_path, fetch=_no_api, tracked=[f"{EXP}/copia.bin"])
    assert code == v.EXIT_COLLISION


def test_archivo_ilegible_en_data_es_error(tmp_path, monkeypatch, capsys):
    _write(tmp_path, f"{EXP}/data/a.bin", b"secreto")
    _manifest(tmp_path, [_sha(b"x")])
    real = v.compute_sha256

    def fail_on_data(p):
        if "data" in p.parts:
            raise PermissionError("denegado")
        return real(p)

    monkeypatch.setattr(v, "compute_sha256", fail_on_data)
    code = v.run(tmp_path, fetch=_no_api, tracked=[])
    out = capsys.readouterr().out
    assert code == v.EXIT_UNVERIFIED
    assert "ilegible en data/" in out and "a.bin" in out


# ---------- exclusión de archivos propios ----------


def test_propios_del_kit_no_cuentan_por_nombre(tmp_path):
    _write(tmp_path, f"{KIT}/README.md", b"doc")
    code = v.run(
        tmp_path,
        fetch=lambda: (["conditions/a_kit/README.md", f"{KIT}/README.md"], None),
        tracked=[f"{KIT}/README.md"],
    )
    assert code == v.EXIT_OK


def test_propios_del_kit_si_cuentan_por_hash(tmp_path):
    _write(tmp_path, f"{KIT}/README.md", b"contenido del kit")
    _manifest(tmp_path, [_sha(b"contenido del kit")])
    assert v.run(tmp_path, fetch=_no_api, tracked=[f"{KIT}/README.md"]) == v.EXIT_COLLISION


def test_readme_con_contenido_del_kit_en_otra_carpeta_da_1(tmp_path):
    _write(tmp_path, f"{EXP}/otra/README.md", b"contenido del kit")
    _manifest(tmp_path, [_sha(b"contenido del kit")])
    assert v.run(tmp_path, fetch=_no_api, tracked=[f"{EXP}/otra/README.md"]) == v.EXIT_COLLISION


# ---------- manifiesto ----------


@pytest.mark.parametrize(
    "raw",
    [
        b'{"files": [{"path": "a", "sha256": "ab',  # truncado
        b'[{"path": "a"}]',  # lista en la raíz
        b'{"files": [{"sha256": "' + b"a" * 64 + b'"}]}',  # sin path
        b'{"files": [{"path": "a", "sha256": "zz"}]}',  # hash inválido
        b'{"files": [{"path": "a", "sha256": "' + b"a" * 63 + b'"}]}',  # corto
        b'{"files": [{"path": "a"}]}',  # sin sha256
    ],
)
def test_manifiesto_corrupto_sale_2(tmp_path, capsys, raw):
    _write(tmp_path, v.MANIFEST_REL, raw)
    _write(tmp_path, f"{EXP}/mine.txt", b"propio")
    code = v.run(tmp_path, fetch=lambda: (["x.csv"], None), tracked=[f"{EXP}/mine.txt"])
    out = capsys.readouterr().out
    assert code == v.EXIT_UNVERIFIED
    assert "manifiesto" in out and "[INCOMPLETO]" in out


def test_manifiesto_con_bom_y_hash_en_mayusculas(tmp_path):
    h = _sha(b"secreto").upper()
    raw = b"\xef\xbb\xbf" + json.dumps({"files": [{"path": "a", "sha256": h}]}).encode()
    _write(tmp_path, v.MANIFEST_REL, raw)
    _write(tmp_path, f"{EXP}/copia.bin", b"secreto")
    assert v.run(tmp_path, fetch=_no_api, tracked=[f"{EXP}/copia.bin"]) == v.EXIT_COLLISION


# ---------- API: lectura, paginación, token ----------


def test_fetch_sin_token_no_es_error(tmp_path):
    assert v.fetch_api_names(tmp_path) == ([], None)


@pytest.mark.parametrize(
    "payload",
    [
        {},  # sin 'files'
        {"files": []},  # vacío
        [{"name": "a"}],  # lista en la raíz
        {"files": [{"size": 1}, {"name": ""}, "x"]},  # 0 nombres válidos
        b"no es json",
    ],
)
def test_api_200_sin_nombres_utiles_es_error(tmp_path, monkeypatch, payload):
    _api(monkeypatch, tmp_path, [payload])
    names, error = v.fetch_api_names(tmp_path)
    assert names == [] and error


def test_api_respuesta_vacia_con_token_sale_2(tmp_path, monkeypatch, capsys):
    _api(monkeypatch, tmp_path, [{"files": []}])
    _write(tmp_path, f"{EXP}/mine.txt", b"propio")
    _manifest(tmp_path, [_sha(b"x")])
    code = v.run(tmp_path, tracked=[f"{EXP}/mine.txt"])
    out = capsys.readouterr().out
    assert code == v.EXIT_UNVERIFIED
    assert "[ERROR] Error al consultar la API" in out


def test_api_cuenta_solo_nombres_utiles(tmp_path, monkeypatch):
    _api(monkeypatch, tmp_path, [{"files": [{"name": "a"}, {"size": 1}, {"name": "b"}]}])
    assert v.fetch_api_names(tmp_path) == (["a", "b"], None)


def test_api_paginacion_dos_paginas(tmp_path, monkeypatch):
    calls: list = []
    _api(
        monkeypatch,
        tmp_path,
        [
            {"files": [{"name": "a"}], "nextPageToken": "t/2 =x"},
            {"files": [{"name": "b"}]},
        ],
        calls,
    )
    assert v.fetch_api_names(tmp_path) == (["a", "b"], None)
    assert len(calls) == 2
    assert calls[1][0].endswith("?pageToken=t%2F2%20%3Dx")
    assert all(t == v.API_TIMEOUT for _, t in calls)


def test_api_error_en_segunda_pagina_conserva_y_sale_2(tmp_path, monkeypatch, capsys):
    _api(
        monkeypatch,
        tmp_path,
        [
            {"files": [{"name": "a"}], "nextPageToken": "t2"},
            urllib.error.URLError("sin red"),
        ],
    )
    _write(tmp_path, f"{EXP}/mine.txt", b"propio")
    _manifest(tmp_path, [_sha(b"x")])
    code = v.run(tmp_path, tracked=[f"{EXP}/mine.txt"])
    out = capsys.readouterr().out
    assert code == v.EXIT_UNVERIFIED
    assert "URLError" in out and f"{v.SRC_API}: 1" in out


def test_api_token_de_pagina_repetido_es_error(tmp_path, monkeypatch):
    page = {"files": [{"name": "a"}], "nextPageToken": "t"}
    _api(monkeypatch, tmp_path, [page, page])
    names, error = v.fetch_api_names(tmp_path)
    assert names == ["a", "a"]
    assert error is not None and "paginación" in error


@pytest.mark.parametrize(
    "exc",
    [
        urllib.error.HTTPError("https://x", 401, "Unauthorized", {}, io.BytesIO(b"")),
        urllib.error.HTTPError("https://x", 403, "Forbidden", {}, io.BytesIO(b"")),
        urllib.error.URLError("sin red"),
    ],
)
def test_error_de_red_no_expone_token(tmp_path, monkeypatch, exc):
    _api(monkeypatch, tmp_path, [exc])
    names, error = v.fetch_api_names(tmp_path)
    assert names == []
    assert error is not None and "SECRETO123" not in error
    assert type(exc).__name__ in error


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("KAGGLE_API_TOKEN=", None),
        ("OTRA=1", None),
        ("KAGGLE_API_TOKEN=abc", "abc"),
        ("export KAGGLE_API_TOKEN=abc", "abc"),
        ("KAGGLE_API_TOKEN = 'abc'", "abc"),
        ('  export KAGGLE_API_TOKEN =  "abc"  ', "abc"),
    ],
)
def test_lectura_del_token(tmp_path, line, expected):
    (tmp_path / ".env").write_text(line + "\n", encoding="utf-8")
    assert v.get_kaggle_bearer_token(tmp_path) == expected


# ---------- CLI ----------


def test_main_require_full_pasa_la_opcion(monkeypatch):
    seen = {}

    def fake_run(**kw):
        seen.update(kw)
        return 0

    monkeypatch.setattr(v, "run", fake_run)
    assert v.main(["--require-full"]) == 0
    assert seen == {"require_full": True}
    assert v.main([]) == 0
    assert seen == {"require_full": False}


# ---------- directorio del envio de la linea base (pre-registro de #103) ----------


def test_linea_base_solo_admite_sus_dos_archivos_propios(tmp_path, capsys):
    base = v.LINEA_BASE_DIR
    _manifest(tmp_path, [_sha(b"archivo del kit")])
    _write(tmp_path, f"{base}/eval_config.yaml", b"evaluation:\n  max_time_minutes: 4\n")
    _write(tmp_path, f"{base}/README.md", b"armado del envio")
    propios = [f"{base}/eval_config.yaml", f"{base}/README.md", v.MANIFEST_REL]
    assert v.run(tmp_path, fetch=_no_api, tracked=propios) == v.EXIT_OK
    capsys.readouterr()
    # una copia del kit modificada: su hash ya no coincide con el manifiesto, pero no puede versionarse ahi
    _write(tmp_path, f"{base}/configs/sampling.yaml", b"copia del kit con un valor cambiado")
    code = v.run(tmp_path, fetch=_no_api, tracked=[*propios, f"{base}/configs/sampling.yaml"])
    out = capsys.readouterr().out
    assert code == v.EXIT_COLLISION and "no permitido en conditions/a_linea_base" in out
    assert f"{base}/configs/sampling.yaml" in out


def test_linea_base_copia_exacta_del_kit_da_alerta_por_hash_y_por_lugar(tmp_path):
    base = v.LINEA_BASE_DIR
    kit = b"archivo del kit"
    _manifest(tmp_path, [_sha(kit)])
    _write(tmp_path, f"{base}/agent.yaml", kit)
    ref = v.build_reference(tmp_path, _no_api)
    por_ruta, por_hash = v.find_collisions(tmp_path, [f"{base}/agent.yaml"], ref)
    assert len(por_ruta) == 1 and len(por_hash) == 1
    # el eval_config propio con el contenido del kit tambien se detecta, por hash
    _write(tmp_path, f"{base}/eval_config.yaml", kit)
    por_ruta, por_hash = v.find_collisions(tmp_path, [f"{base}/eval_config.yaml"], ref)
    assert por_ruta == [] and len(por_hash) == 1


def test_regla_de_gitignore_de_la_linea_base():
    reglas = (v.REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert f"{v.LINEA_BASE_DIR}/*" in reglas
    assert {f"!{p}" for p in v.LINEA_BASE_OWN} <= set(reglas)
