"""Guardián de sesión (`scripts/session_guard.py`): lo que el tablero dice que está sin resolver."""

from __future__ import annotations

import io
import json
import subprocess
from pathlib import Path

import pytest

from scripts import session_guard as sg

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "board-2026-10-02"
SECRETO = "gho_" + "NOIMPRIMIR123456"


def _correr(argv: list[str], runner=None) -> tuple[int, str]:
    salida = io.StringIO()
    codigo = sg.main(argv, runner=runner or _sin_gh, out=salida)
    return codigo, salida.getvalue()


def _sin_gh(args):
    return subprocess.CompletedProcess(args, 1, stdout="", stderr="gh no disponible")


def _instantanea(tmp_path: Path, **cambios) -> Path:
    issues = json.loads((FIXTURE / "issues.json").read_text(encoding="utf-8"))
    items = json.loads((FIXTURE / "items.json").read_text(encoding="utf-8"))
    for numero, campos in cambios.get("issues", {}).items():
        for issue in issues:
            if issue["number"] == numero:
                issue.update(campos)
    (tmp_path / "issues.json").write_text(json.dumps(issues), encoding="utf-8")
    (tmp_path / "items.json").write_text(json.dumps(items), encoding="utf-8")
    return tmp_path


def test_el_informe_lleva_los_tres_bloques_y_la_regla(tmp_path):
    codigo, texto = _correr(["--snapshot", str(_instantanea(tmp_path))])
    assert codigo == sg.EXIT_OK
    assert texto.startswith("GUARDIÁN DEL TABLERO")
    assert "Hallazgos" in texto and "Issues abiertos" in texto
    assert "no al fusionar el PR" in texto


def test_un_issue_abierto_aparece_con_su_talla(tmp_path):
    numero = json.loads((FIXTURE / "issues.json").read_text(encoding="utf-8"))[0]["number"]
    directorio = _instantanea(
        tmp_path,
        issues={numero: {"state": "OPEN", "labels": [{"name": "talla:M"}], "title": "trabajo abierto"}},
    )
    _codigo, texto = _correr(["--snapshot", str(directorio)])
    assert f"#{numero} [talla:M] trabajo abierto" in texto
    assert "Issues abiertos (1):" in texto


def test_como_gancho_sale_siempre_con_0_y_en_modo_estricto_delata_los_hallazgos(tmp_path):
    directorio = _instantanea(tmp_path)
    lineas, hallazgos = sg.informe(snapshot=directorio, episodes=[], runner=_sin_gh)
    assert _correr(["--snapshot", str(directorio)])[0] == sg.EXIT_OK
    esperado = sg.EXIT_HALLAZGOS if hallazgos else sg.EXIT_OK
    assert _correr(["--snapshot", str(directorio), "--estricto"])[0] == esperado
    assert lineas[0].startswith("GUARDIÁN DEL TABLERO")


def test_no_poder_leer_no_es_sin_hallazgos(tmp_path):
    codigo, texto = _correr(["--snapshot", str(tmp_path / "no-existe")])
    assert codigo == sg.EXIT_OK
    assert "no se pudo leer el tablero" in texto and "ninguno" not in texto
    assert _correr(["--snapshot", str(tmp_path / "no-existe"), "--estricto"])[0] == sg.EXIT_ILEGIBLE


def test_sin_gh_el_gancho_no_bloquea_la_sesion(monkeypatch):
    monkeypatch.delenv("GH_TOKEN", raising=False)
    codigo, texto = _correr([])
    assert codigo == sg.EXIT_OK
    assert "no se pudo leer el tablero" in texto


def test_el_token_se_pide_a_gh_y_nunca_se_imprime(monkeypatch):
    monkeypatch.delenv("GH_TOKEN", raising=False)
    vistos = []

    def runner(args):
        vistos.append(list(args))
        if list(args[:2]) == ["auth", "token"]:
            return subprocess.CompletedProcess(args, 0, stdout=SECRETO + "\n", stderr="")
        return subprocess.CompletedProcess(args, 1, stdout="", stderr="sin red")

    codigo, texto = _correr([], runner=runner)
    assert codigo == sg.EXIT_OK
    assert vistos[0] == ["auth", "token", "--user", sg.OWNER]
    assert SECRETO not in texto


def test_prs_abiertos_se_listan_y_un_fallo_de_gh_se_dice():
    def runner(args):
        datos = [{"number": 7, "title": "algo", "headRefName": "rama", "isDraft": True}]
        return subprocess.CompletedProcess(args, 0, stdout=json.dumps(datos), stderr="")

    assert sg.prs_abiertos(runner) == ["  PR #7 (borrador) rama: algo"]
    with pytest.raises(sg.BoardReadError):
        sg.prs_abiertos(_sin_gh)


def test_los_bloques_largos_se_recortan():
    filas = [f"  fila {i}" for i in range(sg.TOPE_LINEAS + 5)]
    bloque = sg._bloque("Issues abiertos", filas, "ninguno")
    assert bloque[0] == f"Issues abiertos ({len(filas)}):"
    assert bloque[-1] == "  … y 5 más" and len(bloque) == sg.TOPE_LINEAS + 2
