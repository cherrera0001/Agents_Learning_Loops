"""Pruebas de scripts/kaggle_prereg.py con datos sinteticos inventados.

Los numeros esperados estan calculados a mano en cada caso. Ningun dato de la competencia entra
aqui: las tareas, los repositorios de las tareas sinteticas y los hashes son inventados; el
subconjunto de prueba lo genera ``scripts/kaggle_split.py`` sobre esas tareas sinteticas, para que
la comprobacion lea el formato real de su salida.
"""

from __future__ import annotations

import copy
import hashlib
import json
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from scripts import kaggle_prereg as kp
from scripts import kaggle_split
from scripts.kaggle_prereg import (
    PreregError,
    budget_minutes,
    check_closed,
    check_structure,
    choose_step,
    fijos_digest,
    ladder,
    load_params,
    main,
    open_parameters,
    parse_eval_config,
    plan_hours,
    plan_slots,
    slot_minutes,
    usable_hours,
)

VERSIONADO = kp.DEFAULT_PARAMS
CONTEOS = {"fastapi/fastapi": 67, "Textualize/rich": 48, "psf/requests": 13, "encode/httpx": 1}


@pytest.fixture
def versionado() -> dict[str, Any]:
    return load_params(VERSIONADO)


@pytest.fixture
def fijos(versionado: dict[str, Any]) -> dict[str, Any]:
    return dict(versionado["fijos"])


# ---------------------------------------------------------------------------
# El archivo versionado
# ---------------------------------------------------------------------------


def _todo_abierto(data: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(data)
    for entrada in out["abiertos"].values():
        entrada["valor"] = None
    return out


def test_archivo_versionado_bien_formado_y_coherente(versionado: dict[str, Any]) -> None:
    """Vale tambien cuando los commits C2 a C5 vayan cerrando parametros: no hay que tocar este test."""
    assert check_structure(versionado) == []
    assert check_closed(versionado, kp.REPO_ROOT) == []
    assert main(["comprobar"]) == (kp.EXIT_OPEN if open_parameters(versionado) else kp.EXIT_OK)


def test_decisiones_fijadas_no_cambian_en_silencio(fijos: dict[str, Any]) -> None:
    """Cambiar una decision del pre-registro obliga a cambiar tambien este test y el documento."""
    assert fijos["limite_envio_minutos"] == 720
    assert fijos["tareas_envio"] == 120
    assert fijos["reserva"] == 0.1
    assert (fijos["max_tool_calls"], fijos["max_turns"], fijos["timeout_seconds"]) == (100, 500, 300)
    assert fijos["replicas_minimo"] == 2
    assert fijos["min_tareas_prueba"] == 40
    assert fijos["escalera"][0] == ["fastapi/fastapi", 3, 2]
    assert fijos_digest(fijos) == "4ce398e49d13004b4207716a64cfb18848d60d5ba1d42edca50f2e9998488374"
    documento = (kp.REPO_ROOT / "docs/preregistration/kaggle-baseline-a.md").read_text(encoding="utf-8")
    assert fijos_digest(fijos) in documento


def test_digest_de_fijos_cambia_con_cualquier_valor(fijos: dict[str, Any]) -> None:
    otro = {**fijos, "reserva": 0.2}
    assert fijos_digest(otro) != fijos_digest(fijos)
    assert fijos_digest(dict(reversed(list(fijos.items())))) == fijos_digest(fijos)


def test_main_con_todo_abierto_sale_con_1(
    tmp_path: Path, versionado: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    data = _todo_abierto(versionado)
    assert open_parameters(data) == list(kp.ABIERTOS)
    path = tmp_path / "parametros.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert main(["comprobar", "--parametros", str(path), "--raiz", str(tmp_path)]) == kp.EXIT_OPEN
    salida = capsys.readouterr()
    assert "ABIERTO  presupuesto" in salida.out
    assert "Quedan 8 parametros abiertos" in salida.err


# ---------------------------------------------------------------------------
# Formulas
# ---------------------------------------------------------------------------


def test_minutos_de_reloj_por_tarea(fijos: dict[str, Any]) -> None:
    assert slot_minutes(fijos) == Fraction(27, 5)  # 720 * 0,9 / 120 = 5,4


@pytest.mark.parametrize(
    ("c", "m", "s", "esperado"),
    [
        (1, 0, 0, 5),  # floor(5,4)
        (1, 15, 1, 4),  # floor(705 * 0,9 / 120 - 1) = floor(4,2875)
        (2, 0, 1, 9),  # floor(10,8 - 1)
        (4, 30, 2, 18),  # floor(4 * 690 * 0,9 / 120 - 2) = floor(18,7)
        (1, 0, 0.4, 5),  # 5,0 exacto: sin error de coma flotante
        (20, 0, 0, 60),  # 108 -> tope de 60
    ],
)
def test_presupuesto_por_tarea(fijos: dict[str, Any], c: int, m: float, s: float, esperado: int) -> None:
    assert budget_minutes(fijos, c, m, s) == esperado


def test_presupuesto_cabe_en_el_limite_del_envio(fijos: dict[str, Any]) -> None:
    """Control de la formula: con b, las N tareas mas la carga caben en T * (1 - reserva)."""
    for c, m, s in [(1, 15, 1), (2, 30, 2), (4, 0, 0.5)]:
        b = budget_minutes(fijos, c, m, s)
        total = m + Fraction(fijos["tareas_envio"], c) * (b + Fraction(str(s)))
        assert total <= 720 * Fraction(9, 10)
        assert m + Fraction(fijos["tareas_envio"], c) * (b + 1 + Fraction(str(s))) > 720 * Fraction(9, 10)


def test_presupuesto_bajo_el_minimo_no_se_fija(fijos: dict[str, Any]) -> None:
    with pytest.raises(PreregError, match="menos que el minimo"):
        budget_minutes(fijos, 1, 0, 4)  # floor(1,4) = 1 < 2


@pytest.mark.parametrize(("c", "m", "s"), [(0, 0, 0), (True, 0, 0), (1.5, 0, 0), (1, -1, 0), (1, 0, -0.1)])
def test_presupuesto_rechaza_entradas_invalidas(fijos: dict[str, Any], c: Any, m: Any, s: Any) -> None:
    with pytest.raises(PreregError):
        budget_minutes(fijos, c, m, s)


def test_corridas_y_horas_de_un_escalon(fijos: dict[str, Any]) -> None:
    assert plan_slots(fijos, 67, 62, 3, 2) == 3 * 67 + 62 + 2 * 2 * 67 == 531
    assert plan_slots(fijos, 48, 81, 2, 0) == 96  # sin campana no hay pase de entrenamiento
    assert plan_hours(fijos, 531) == Fraction(531 * 27, 5 * 60)  # 47,79 h
    assert usable_hours(fijos, 30, 4) == 48  # 0,8 * (30 / 2) * 4


def test_escalera_con_todas_las_tareas(fijos: dict[str, Any]) -> None:
    escalones = ladder(fijos, CONTEOS)
    assert [(e.repo, e.replicas, e.por_condicion, e.slots) for e in escalones] == [
        ("fastapi/fastapi", 3, 2, 531),
        ("fastapi/fastapi", 2, 2, 464),
        ("Textualize/rich", 3, 2, 417),
        ("Textualize/rich", 2, 2, 369),
        ("fastapi/fastapi", 2, 1, 330),
        ("Textualize/rich", 2, 1, 273),
        ("Textualize/rich", 2, 0, 96),
        ("fastapi/fastapi", 2, 0, 134),
    ]
    assert all(e.apto for e in escalones)
    assert (escalones[0].n_test, escalones[0].n_train) == (67, 62)


@pytest.mark.parametrize(
    ("horas", "indice"),
    [(48, 0), ("47.78", 1), (40, 2), (34, 3), (30, 4), (25, 5), (10, 6), ("8.63", None)],
)
def test_eleccion_de_escalon(fijos: dict[str, Any], horas: Any, indice: int | None) -> None:
    escalones = ladder(fijos, CONTEOS)
    paso = choose_step(escalones, Fraction(str(horas)))
    assert (None if paso is None else escalones.index(paso)) == indice


def test_escalon_con_pocas_tareas_de_prueba_se_salta(fijos: dict[str, Any]) -> None:
    escalones = ladder(fijos, {**CONTEOS, "fastapi/fastapi": 39})
    assert [e.apto for e in escalones] == [False, False, True, True, False, True, True, False]
    paso = choose_step(escalones, Fraction(1000))
    assert paso is not None and (paso.repo, paso.replicas) == ("Textualize/rich", 3)
    assert choose_step(ladder(fijos, {"fastapi/fastapi": 39, "Textualize/rich": 39}), Fraction(1000)) is None


# ---------------------------------------------------------------------------
# Estructura
# ---------------------------------------------------------------------------


def _mutado(data: dict[str, Any], ruta: tuple[str, ...], valor: Any) -> dict[str, Any]:
    out = copy.deepcopy(data)
    nodo = out
    for k in ruta[:-1]:
        nodo = nodo[k]
    nodo[ruta[-1]] = valor
    return out


@pytest.mark.parametrize(
    ("ruta", "valor", "texto"),
    [
        (("schema_version",), "otro/9", "schema_version"),
        (("fijos", "reserva"), 1, "fijos.reserva"),
        (("fijos", "tareas_envio"), True, "fijos.tareas_envio"),
        (("fijos", "regla_particion"), "temporal_stratified", "fijos.regla_particion"),
        (("fijos", "escalera"), [["fastapi/fastapi", 1, 2]], "fijos.escalera"),
        (("fijos", "tasks_sha256"), "E4B3", "fijos.tasks_sha256"),
        (("fijos", "minimo_max_time_minutes"), 61, "supera al tope"),
        (("fijos", "umbral_ruido_bajo"), 0.3, "umbral_ruido_bajo"),
        (("abiertos", "replicas", "valor"), 1, "abiertos.replicas"),
        (("abiertos", "replicas", "regla"), " ", "abiertos.replicas"),
        (("abiertos", "repeticion_infra", "valor"), "a mano", "abiertos.repeticion_infra"),
        (("abiertos", "cuota", "valor"), {"gpu_semanal_horas": 30}, "abiertos.cuota"),
        (("abiertos", "subconjunto"), {"valor": None, "regla": "r"}, "abiertos.subconjunto"),
    ],
)
def test_estructura_invalida(
    versionado: dict[str, Any], ruta: tuple[str, ...], valor: Any, texto: str
) -> None:
    problemas = check_structure(_mutado(versionado, ruta, valor))
    assert problemas and any(texto in p for p in problemas)


def test_estructura_claves_de_mas_o_de_menos(versionado: dict[str, Any]) -> None:
    assert check_structure({**versionado, "extra": 1})
    sin = copy.deepcopy(versionado)
    del sin["fijos"]["alfa"]
    assert any("'fijos' debe tener" in p for p in check_structure(sin))
    con = copy.deepcopy(versionado)
    con["abiertos"]["nuevo"] = {"valor": None, "regla": "r", "cierra": "c"}
    assert any("'abiertos' debe tener" in p for p in check_structure(con))
    assert check_structure({**versionado, "fijos": []})


# ---------------------------------------------------------------------------
# Parametros cerrados contra sus reglas
# ---------------------------------------------------------------------------


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _escribir(path: Path, texto: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(texto.encode("utf-8"))
    return _sha(path)


def _arbol_cerrado(tmp_path: Path, versionado: dict[str, Any]) -> dict[str, Any]:
    """Un pre-registro con todo cerrado y coherente, sobre tareas sinteticas (61 + 45 + 12)."""
    tareas = [
        {"instance_id": f"{corto}_{i:03d}", "repo": repo, "created_at": f"2026-01-{i % 28 + 1:02d}T00:00:00Z"}
        for repo, corto, n in (
            ("fastapi/fastapi", "fa", 61),
            ("Textualize/rich", "ri", 45),
            ("psf/requests", "re", 12),
        )
        for i in range(n)
    ]
    tasks_sha = _escribir(tmp_path / "tasks.jsonl", "".join(json.dumps(t) + "\n" for t in tareas))
    validez_sha = _escribir(
        tmp_path / "validez.json",
        json.dumps({"sha256_tasks": tasks_sha, "tareas_invalidas": [{"instance_id": "fa_000"}]}),
    )
    assert (
        kaggle_split.main(
            [
                "--tasks",
                str(tmp_path / "tasks.jsonl"),
                "--calibracion",
                str(tmp_path / "validez.json"),
                "--rule",
                "leave_one_repo_out",
                "--held-out-repo",
                "fastapi/fastapi",
                "--output",
                str(tmp_path / "subconjunto.json"),
            ]
        )
        == 0
    )
    entorno_sha = _escribir(tmp_path / "entorno.json", "{}")
    piloto_sha = _escribir(tmp_path / "piloto.json", "{}")
    eval_sha = _escribir(
        tmp_path / "eval_config.yaml",
        "# linea base A\nevaluation:\n  timeout_seconds: 300\n  max_tool_calls: 100\n"
        "  max_time_minutes: 4\n  max_turns: 500\n",
    )
    data = copy.deepcopy(versionado)
    data["fijos"]["tasks_sha256"] = tasks_sha
    cerrar = {
        "entorno_sandbox": {
            "backend": "docker",
            "imagen": "imagen-inventada",
            "version_arnes": "0.0.0",
            "declaracion_ruta": "entorno.json",
            "declaracion_sha256": entorno_sha,
        },
        "validez_tareas": {"ruta": "validez.json", "sha256": validez_sha},
        # 0,8 * (30 / 2) * 4 = 48 h; escalon 1 con 60/45/12 validas: 3*60 + 57 + 4*60 = 477 -> 42,93 h
        "cuota": {"gpu_semanal_horas": 30, "semanas": 4, "sesion_max_horas": 12},
        "subconjunto": {"ruta": "subconjunto.json", "sha256": _sha(tmp_path / "subconjunto.json")},
        "replicas": 3,
        "piloto": {
            "concurrencia": 1,
            "fuente_concurrencia": "supuesto: sin fuente",
            "carga_modelo_minutos": 15,
            "montaje_por_tarea_minutos": 1,
            "max_output_tokens": 16384,
            "registro_ruta": "piloto.json",
            "registro_sha256": piloto_sha,
        },
        "presupuesto": {
            "max_time_minutes": 4,
            "eval_config_ruta": "eval_config.yaml",
            "eval_config_sha256": eval_sha,
            "envio_sha256": "a" * 64,
        },
        "repeticion_infra": "replica_completa",
    }
    for nombre, valor in cerrar.items():
        data["abiertos"][nombre]["valor"] = valor
    return data


def _guardar(tmp_path: Path, data: dict[str, Any]) -> Path:
    path = tmp_path / "parametros.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_todo_cerrado_y_coherente_sale_con_0(
    tmp_path: Path, versionado: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    data = _arbol_cerrado(tmp_path, versionado)
    assert check_structure(data) == []
    assert check_closed(data, tmp_path) == []
    assert open_parameters(data) == []
    assert main(["comprobar", "--parametros", str(_guardar(tmp_path, data)), "--raiz", str(tmp_path)]) == 0
    assert "Todos los parametros estan cerrados" in capsys.readouterr().out


def _problemas(tmp_path: Path, data: dict[str, Any]) -> str:
    assert check_structure(data) == []
    problemas = check_closed(data, tmp_path)
    assert main(["comprobar", "--parametros", str(_guardar(tmp_path, data)), "--raiz", str(tmp_path)]) == 2
    return "\n".join(problemas)


def test_presupuesto_distinto_de_la_formula(tmp_path: Path, versionado: dict[str, Any]) -> None:
    data = _arbol_cerrado(tmp_path, versionado)
    data["abiertos"]["presupuesto"]["valor"]["max_time_minutes"] = 5
    assert "la formula da 4" in _problemas(tmp_path, data)


def test_eval_config_con_otros_valores(tmp_path: Path, versionado: dict[str, Any]) -> None:
    data = _arbol_cerrado(tmp_path, versionado)
    sha = _escribir(
        tmp_path / "eval_config.yaml",
        "evaluation:\n  timeout_seconds: 60\n  max_tool_calls: 100\n  max_time_minutes: 4\n"
        "  max_turns: 500\n",
    )
    data["abiertos"]["presupuesto"]["valor"]["eval_config_sha256"] = sha
    assert "debe decir" in _problemas(tmp_path, data)


def test_archivo_citado_alterado_o_ausente(tmp_path: Path, versionado: dict[str, Any]) -> None:
    data = _arbol_cerrado(tmp_path, versionado)
    (tmp_path / "eval_config.yaml").write_bytes(b"evaluation:\n  max_time_minutes: 4\n")
    assert "no el declarado" in _problemas(tmp_path, data)
    data = _arbol_cerrado(tmp_path, versionado)
    (tmp_path / "piloto.json").unlink()
    assert "piloto: no existe el archivo" in _problemas(tmp_path, data)
    data = _arbol_cerrado(tmp_path, versionado)
    data["abiertos"]["entorno_sandbox"]["valor"]["declaracion_sha256"] = "b" * 64
    assert "entorno_sandbox" in _problemas(tmp_path, data)


def test_repositorio_que_no_da_la_escalera(tmp_path: Path, versionado: dict[str, Any]) -> None:
    data = _arbol_cerrado(tmp_path, versionado)
    # 36 h utilizables: fastapi con 3 replicas (42,93 h) y con 2 (37,53 h) no caben; rich con 3 si (34,83 h)
    data["abiertos"]["cuota"]["valor"]["semanas"] = 3
    assert "la escalera da 'Textualize/rich'" in _problemas(tmp_path, data)


def test_replicas_que_no_da_la_escalera(tmp_path: Path, versionado: dict[str, Any]) -> None:
    data = _arbol_cerrado(tmp_path, versionado)
    data["abiertos"]["replicas"]["valor"] = 2
    assert "la escalera da 3" in _problemas(tmp_path, data)


def test_ningun_escalon_cabe(tmp_path: Path, versionado: dict[str, Any]) -> None:
    data = _arbol_cerrado(tmp_path, versionado)
    data["abiertos"]["cuota"]["valor"]["gpu_semanal_horas"] = 1
    assert "ningun escalon cabe" in _problemas(tmp_path, data)


def test_subconjunto_sin_las_exclusiones_de_la_validez(tmp_path: Path, versionado: dict[str, Any]) -> None:
    data = _arbol_cerrado(tmp_path, versionado)
    tasks_sha = data["fijos"]["tasks_sha256"]
    sha = _escribir(
        tmp_path / "validez.json",
        json.dumps({"sha256_tasks": tasks_sha, "tareas_invalidas": [{"instance_id": "fa_001"}]}),
    )
    data["abiertos"]["validez_tareas"]["valor"]["sha256"] = sha
    assert "no son las 'tareas_invalidas'" in _problemas(tmp_path, data)


def test_subconjunto_con_otra_regla_u_otro_tasks(tmp_path: Path, versionado: dict[str, Any]) -> None:
    for clave, valor, texto in [
        (("rule", "name"), "temporal_stratified_by_repo", "la regla es"),
        (("sha256_tasks",), "c" * 64, "tasks_sha256"),
        (("rule", "exclusiones_origen"), "sin_calibracion", "exclusiones_origen"),
        (("test",), ["fa_001"], "lista 'test'"),
        (("counts",), {}, "counts.by_repo"),
    ]:
        data = _arbol_cerrado(tmp_path, versionado)
        sub = json.loads((tmp_path / "subconjunto.json").read_text(encoding="utf-8"))
        nodo = sub
        for k in clave[:-1]:
            nodo = nodo[k]
        nodo[clave[-1]] = valor
        data["abiertos"]["subconjunto"]["valor"]["sha256"] = _escribir(
            tmp_path / "subconjunto.json", json.dumps(sub)
        )
        assert texto in _problemas(tmp_path, data)


def test_validez_mal_formada(tmp_path: Path, versionado: dict[str, Any]) -> None:
    for contenido, texto in [
        ("{}", "tareas_invalidas"),
        (json.dumps({"sha256_tasks": "d" * 64, "tareas_invalidas": []}), "sha256_tasks"),
        ("[]", "debe ser un objeto"),
        ('{"a": 1, "a": 2}', "no es JSON valido"),
    ]:
        data = _arbol_cerrado(tmp_path, versionado)
        data["abiertos"]["validez_tareas"]["valor"]["sha256"] = _escribir(
            tmp_path / "validez.json", contenido
        )
        assert texto in _problemas(tmp_path, data)


def test_orden_de_cierre(tmp_path: Path, versionado: dict[str, Any]) -> None:
    data = _arbol_cerrado(tmp_path, versionado)
    data["abiertos"]["cuota"]["valor"] = None
    assert "subconjunto: no puede cerrarse antes que cuota" in _problemas(tmp_path, data)
    data = _arbol_cerrado(tmp_path, versionado)
    data["abiertos"]["piloto"]["valor"] = None
    assert "presupuesto: no puede cerrarse antes que piloto" in _problemas(tmp_path, data)
    data = _arbol_cerrado(tmp_path, versionado)
    data["abiertos"]["entorno_sandbox"]["valor"] = None
    assert "validez_tareas: no puede cerrarse antes que entorno_sandbox" in _problemas(tmp_path, data)


def test_max_output_tokens_fuera_de_los_candidatos(tmp_path: Path, versionado: dict[str, Any]) -> None:
    data = _arbol_cerrado(tmp_path, versionado)
    data["abiertos"]["piloto"]["valor"]["max_output_tokens"] = 4096
    assert "max_output_tokens debe ser uno de" in _problemas(tmp_path, data)


def test_cierre_parcial_valido_sale_con_1(tmp_path: Path, versionado: dict[str, Any]) -> None:
    data = _arbol_cerrado(tmp_path, versionado)
    for nombre in ("presupuesto", "repeticion_infra"):
        data["abiertos"][nombre]["valor"] = None
    assert check_closed(data, tmp_path) == []
    assert open_parameters(data) == ["presupuesto", "repeticion_infra"]
    assert main(["comprobar", "--parametros", str(_guardar(tmp_path, data)), "--raiz", str(tmp_path)]) == 1


# ---------------------------------------------------------------------------
# eval_config y CLI
# ---------------------------------------------------------------------------


def test_parse_eval_config() -> None:
    texto = (
        "# comentario\notra:\n  max_turns: 9\nevaluation:\n  max_turns: 500  # turnos\n\n"
        "  timeout_seconds: 300\n"
    )
    assert parse_eval_config(texto) == {"max_turns": 500, "timeout_seconds": 300}
    assert parse_eval_config("") == {}
    for malo in (
        "evaluation:\n  max_turns 500\n",
        "evaluation:\n  a: 1\n  a: 2\n",
        "evaluation:\n  a: muchos\n",
    ):
        with pytest.raises(PreregError):
            parse_eval_config(malo)


def test_main_entradas_ilegibles_salen_con_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["comprobar", "--parametros", str(tmp_path / "no_existe.json")]) == 2
    roto = tmp_path / "roto.json"
    roto.write_text("{", encoding="utf-8")
    assert main(["comprobar", "--parametros", str(roto)]) == 2
    roto.write_text("[]", encoding="utf-8")
    assert main(["comprobar", "--parametros", str(roto)]) == 2
    roto.write_text('{"fijos": {}, "fijos": {}}', encoding="utf-8")
    assert main(["presupuesto", "--parametros", str(roto)]) == 2
    assert "ERROR" in capsys.readouterr().err


def test_main_error_inesperado_sale_con_3(monkeypatch: pytest.MonkeyPatch) -> None:
    def falla(_: Path) -> dict[str, Any]:
        raise RuntimeError("defecto inyectado")

    monkeypatch.setattr(kp, "load_params", falla)
    assert main(["comprobar"]) == kp.EXIT_UNEXPECTED


def test_cli_presupuesto(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["presupuesto", "--concurrencia", "1", "--carga-modelo", "15", "--montaje", "1", "4"]) == 0
    lineas = capsys.readouterr().out.splitlines()
    assert lineas[0].endswith("5.40")
    assert lineas[2].split() == ["1", "15.0", "1.0", "4"]
    assert "no se fija" in lineas[3]


def test_cli_computo(capsys: pytest.CaptureFixture[str]) -> None:
    validas = [f"{repo}={n}" for repo, n in CONTEOS.items()]
    assert main(["computo", "--validas", *validas, "--cuota", "30", "--semanas", "4"]) == 0
    salida = capsys.readouterr().out
    assert "531   47.79    95.58" in salida
    assert "escalon elegido: 1 (fastapi/fastapi, 3 replicas de A)" in salida
    assert main(["computo", "--validas", "fastapi/fastapi=39", "--cuota", "30", "--semanas", "4"]) == 0
    salida = capsys.readouterr().out
    assert "no apto" in salida and "ningun escalon cabe" in salida
    assert main(["computo", "--validas", "sin_numero"]) == 2
    assert main(["computo", "--validas", *validas, "--cuota", "30"]) == 2
