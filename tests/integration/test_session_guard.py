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
PRS = [
    {"number": 9, "title": "segundo", "headRefName": "rama-b", "isDraft": False},
    {"number": 7, "title": "primero", "headRefName": "rama-a", "isDraft": True},
]


def _correr(argv: list[str], runner=None, episodes_dir: Path | None = None) -> tuple[int, str]:
    salida = io.StringIO()
    codigo = sg.main(argv, runner=runner or _sin_gh, out=salida, episodes_dir=episodes_dir)
    return codigo, salida.getvalue()


def _sin_gh(args):
    return subprocess.CompletedProcess(args, 1, stdout="", stderr="gh no disponible")


def _gh_ausente(args):
    raise sg.BoardReadError("gh no está instalado o no está en el PATH")


def _instantanea(tmp_path: Path, issues: dict | None = None) -> Path:
    datos = json.loads((FIXTURE / "issues.json").read_text(encoding="utf-8"))
    for numero, campos in (issues or {}).items():
        for issue in datos:
            if issue["number"] == numero:
                issue.update(campos)
    (tmp_path / "issues.json").write_text(json.dumps(datos), encoding="utf-8")
    (tmp_path / "items.json").write_text(
        (FIXTURE / "items.json").read_text(encoding="utf-8"), encoding="utf-8"
    )
    return tmp_path


def _numeros() -> list[int]:
    return sorted(i["number"] for i in json.loads((FIXTURE / "issues.json").read_text(encoding="utf-8")))


def test_el_informe_lleva_los_bloques_y_la_regla(tmp_path):
    codigo, texto = _correr(["--snapshot", str(_instantanea(tmp_path))])
    assert codigo == sg.EXIT_OK
    assert texto.startswith("GUARDIÁN DEL TABLERO")
    assert "Hallazgos" in texto and "Issues abiertos: ninguno" in texto
    assert "no al fusionar el PR" in texto


def test_los_issues_abiertos_salen_en_orden_con_su_talla_o_como_epica(tmp_path):
    a, b, c = _numeros()[:3]
    directorio = _instantanea(
        tmp_path,
        issues={
            c: {"state": "OPEN", "labels": [{"name": "talla:M"}], "title": "tercero"},
            a: {"state": "OPEN", "labels": [{"name": "epic"}, {"name": "talla:L"}], "title": "primero"},
            b: {"state": "OPEN", "labels": [], "title": "segundo"},
        },
    )
    _codigo, texto = _correr(["--snapshot", str(directorio)])
    assert "Issues abiertos (3):" in texto
    filas = [linea for linea in texto.splitlines() if linea.startswith("  #")]
    assert filas == [f"  #{a} [épica] primero", f"  #{b} [sin talla] segundo", f"  #{c} [talla:M] tercero"]


def test_como_gancho_sale_con_0_y_en_modo_estricto_delata_los_hallazgos(tmp_path):
    directorio = _instantanea(tmp_path)
    _lineas, hallazgos = sg.informe(snapshot=directorio, episodes=[], runner=_sin_gh)
    assert hallazgos > 0, "la instantánea de prueba debe traer hallazgos para que este test diga algo"
    assert _correr(["--snapshot", str(directorio)])[0] == sg.EXIT_OK
    assert _correr(["--snapshot", str(directorio), "--estricto"])[0] == sg.EXIT_HALLAZGOS


def test_el_informe_incluye_las_tarjetas_que_faltan(tmp_path, monkeypatch):
    directorio = _instantanea(tmp_path)
    base = sg.informe(snapshot=directorio, episodes=[], runner=_sin_gh)[1]
    monkeypatch.setattr(sg, "check_missing_cards", lambda *a, **k: [])
    sin_faltantes = sg.informe(snapshot=directorio, episodes=[], runner=_sin_gh)[1]
    monkeypatch.undo()
    monkeypatch.setattr(sg, "check_board", lambda *a, **k: [])
    solo_faltantes = sg.informe(snapshot=directorio, episodes=[], runner=_sin_gh)[1]
    assert base == sin_faltantes + solo_faltantes


def test_no_poder_leer_no_es_sin_hallazgos(tmp_path):
    codigo, texto = _correr(["--snapshot", str(tmp_path / "no-existe")])
    assert codigo == sg.EXIT_OK
    assert "no se pudo leer" in texto and "ninguno" not in texto
    assert _correr(["--snapshot", str(tmp_path / "no-existe"), "--estricto"])[0] == sg.EXIT_ILEGIBLE


@pytest.mark.parametrize("runner", [_sin_gh, _gh_ausente])
def test_sin_gh_el_gancho_no_bloquea_la_sesion_ni_da_traza(monkeypatch, runner):
    monkeypatch.delenv("GH_TOKEN", raising=False)
    codigo, texto = _correr([], runner=runner)
    assert codigo == sg.EXIT_OK
    assert "no se pudo leer" in texto
    assert _correr(["--estricto"], runner=runner)[0] == sg.EXIT_ILEGIBLE


def test_gh_fuera_del_path_o_colgado_es_un_error_de_lectura(monkeypatch):
    def no_esta(*a, **k):
        raise FileNotFoundError("gh")

    monkeypatch.setattr(sg.subprocess, "run", no_esta)
    with pytest.raises(sg.BoardReadError, match="PATH"):
        sg.gh_con_tope(["api", "user"])

    def colgado(*a, **k):
        raise subprocess.TimeoutExpired("gh", sg.TOPE_GH_S)

    monkeypatch.setattr(sg.subprocess, "run", colgado)
    with pytest.raises(sg.BoardReadError, match="no respondió"):
        sg.gh_con_tope(["api", "user"])


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


def test_un_token_ya_presente_no_se_pide_ni_se_pisa(monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "ya-estaba")
    vistos = []

    def runner(args):
        vistos.append(list(args[:2]))
        return subprocess.CompletedProcess(args, 1, stdout="otro\n", stderr="")

    _correr([], runner=runner)
    assert ["auth", "token"] not in vistos
    assert sg.os.environ["GH_TOKEN"] == "ya-estaba"


def test_un_token_de_un_gh_que_fallo_no_se_acepta():
    assert (
        sg.token_de_la_cuenta(lambda a: subprocess.CompletedProcess(a, 1, stdout="algo\n", stderr="")) is None
    )
    assert sg.token_de_la_cuenta(lambda a: subprocess.CompletedProcess(a, 0, stdout="\n", stderr="")) is None
    assert sg.token_de_la_cuenta(lambda a: subprocess.CompletedProcess(a, 0, stdout="t\n", stderr="")) == "t"


def test_prs_abiertos_en_orden_y_con_la_marca_de_borrador():
    runner = lambda args: subprocess.CompletedProcess(args, 0, stdout=json.dumps(PRS), stderr="")  # noqa: E731
    assert sg.prs_abiertos(runner) == ["  PR #7 (borrador) rama-a: primero", "  PR #9 rama-b: segundo"]


@pytest.mark.parametrize(
    "salida", ['{"message": "x"}', "null", "[1]", '"hola"', '[{"title": "t"}]', "{no json"]
)
def test_una_respuesta_de_pr_list_que_no_es_una_lista_de_pr_es_un_error_de_lectura(salida):
    with pytest.raises(sg.BoardReadError):
        sg.prs_abiertos(lambda args: subprocess.CompletedProcess(args, 0, stdout=salida, stderr=""))


def test_un_fallo_de_pr_list_es_un_error_de_lectura_aunque_traiga_salida():
    with pytest.raises(sg.BoardReadError, match="falló"):
        sg.prs_abiertos(lambda args: subprocess.CompletedProcess(args, 1, stdout=json.dumps(PRS), stderr="x"))


def test_en_vivo_el_informe_lleva_el_bloque_de_pr(tmp_path, monkeypatch):
    directorio = _instantanea(tmp_path)
    monkeypatch.setattr(sg, "read_github", lambda runner: sg.read_snapshot(directorio))
    monkeypatch.setenv("GH_TOKEN", "x")
    runner = lambda args: subprocess.CompletedProcess(args, 0, stdout=json.dumps(PRS), stderr="")  # noqa: E731
    codigo, texto = _correr([], runner=runner)
    assert codigo == sg.EXIT_OK
    assert "PR abiertos (2):" in texto and "PR #7 (borrador) rama-a: primero" in texto


@pytest.mark.parametrize(
    "contenido",
    ["{no es json", "[1]", '{"id": "sin-seq"}', '{"seq": "2"}'],
)
def test_un_episodio_ilegible_o_mal_formado_se_dice_y_no_da_traza(tmp_path, contenido):
    episodios = tmp_path / "episodios"
    episodios.mkdir()
    (episodios / "001-malo.json").write_text(contenido, encoding="utf-8")
    with pytest.raises(sg.BoardReadError, match=r"001-malo.json"):
        sg.load_episodes(episodios)
    instantanea = tmp_path / "tablero"
    instantanea.mkdir()
    codigo, texto = _correr(["--snapshot", str(_instantanea(instantanea))], episodes_dir=episodios)
    assert codigo == sg.EXIT_OK and "no se pudo leer" in texto and "001-malo.json" in texto


def test_un_directorio_de_episodios_inexistente_no_es_cero_episodios(tmp_path):
    with pytest.raises(sg.BoardReadError, match="no existe"):
        sg.load_episodes(tmp_path / "no-existe")


def test_los_episodios_reales_se_leen_en_orden():
    episodios = sg.load_episodes()
    assert [e["seq"] for e in episodios] == sorted(e["seq"] for e in episodios) and episodios


@pytest.mark.parametrize(
    ("n", "resto"), [(sg.TOPE_LINEAS, None), (sg.TOPE_LINEAS + 1, 1), (sg.TOPE_LINEAS + 5, 5)]
)
def test_los_bloques_largos_se_recortan_justo_en_el_tope(n, resto):
    filas = [f"  fila {i}" for i in range(n)]
    bloque = sg._bloque("Issues abiertos", filas, "ninguno")
    assert bloque[0] == f"Issues abiertos ({n}):"
    if resto is None:
        assert bloque[1:] == filas
    else:
        assert bloque[-1] == f"  … y {resto} más" and len(bloque) == sg.TOPE_LINEAS + 2
    assert sg._bloque("Issues abiertos", [], "ninguno") == ["Issues abiertos: ninguno"]
