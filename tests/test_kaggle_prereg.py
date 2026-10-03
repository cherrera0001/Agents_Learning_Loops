"""Pruebas de scripts/kaggle_prereg.py con datos sinteticos inventados.

Los numeros esperados estan calculados a mano en cada caso. Ningun dato de la competencia entra
aqui: las tareas, los repositorios de las tareas sinteticas, los registros y los hashes son
inventados; el subconjunto de prueba lo genera ``scripts/kaggle_split.py`` sobre esas tareas
sinteticas, para que la comprobacion lea el formato real de su salida.
"""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
from collections.abc import Callable
from datetime import date
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from scripts import kaggle_prereg as kp
from scripts import kaggle_replicas, kaggle_split
from scripts.kaggle_prereg import (
    PreregError,
    budget_minutes,
    check_closed,
    check_structure,
    choose_step,
    eval_config_bytes,
    fijos_digest,
    ladder,
    load_params,
    main,
    noise_case,
    noise_case_for_observed,
    open_parameters,
    plan_hours,
    plan_slots,
    quota_resets,
    session_parts,
    slot_minutes,
    usable_hours,
)

VERSIONADO = kp.DEFAULT_PARAMS
CANONICO_4 = (
    b"evaluation:\n  timeout_seconds: 300\n  max_tool_calls: 100\n  max_time_minutes: 4\n  max_turns: 500\n"
)
SAMPLING_KIT = b"temperature: 0.5\nmax_output_tokens: 16384\n"  # inventado: no es el del kit
CONTEOS = {"fastapi/fastapi": 67, "Textualize/rich": 48, "psf/requests": 13, "encode/httpx": 1}


@pytest.fixture
def versionado() -> dict[str, Any]:
    return load_params(VERSIONADO)


@pytest.fixture
def fijos(versionado: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(versionado["fijos"])


# ---------------------------------------------------------------------------
# El archivo versionado
# ---------------------------------------------------------------------------


def test_archivo_versionado_bien_formado_y_coherente(versionado: dict[str, Any]) -> None:
    """Vale tambien cuando los commits siguientes vayan cerrando parametros: no hay que tocar este test."""
    assert check_structure(versionado) == []
    assert check_closed(versionado, kp.REPO_ROOT).problemas == []
    esperado = kp.EXIT_OPEN if open_parameters(versionado) else kp.EXIT_OK
    assert main(["comprobar", "--sin-git"]) in (kp.EXIT_OPEN, esperado)


def test_decisiones_fijadas_no_cambian_en_silencio(fijos: dict[str, Any]) -> None:
    """Cambiar una decision del pre-registro obliga a cambiar el resumen del script y el del documento."""
    assert fijos["limite_envio_minutos"] == 720 and fijos["tareas_envio"] == 120 and fijos["reserva"] == 0.1
    assert (fijos["max_tool_calls"], fijos["max_turns"], fijos["timeout_seconds"]) == (100, 500, 300)
    assert (fijos["replicas_minimo"], fijos["replicas_extra_maximo"], fijos["min_tareas_prueba"]) == (
        2,
        2,
        40,
    )
    assert fijos["escalera"][0] == ["fastapi/fastapi", 3, 2]
    assert fijos_digest(fijos) == kp.FIJOS_SHA256
    documento = (kp.REPO_ROOT / "docs/preregistration/kaggle-baseline-a.md").read_text(encoding="utf-8")
    assert kp.FIJOS_SHA256 in documento


def test_digest_de_fijos_cambia_con_cualquier_valor(fijos: dict[str, Any]) -> None:
    assert fijos_digest({**fijos, "reserva": 0.2}) != fijos_digest(fijos)
    assert fijos_digest(dict(reversed(list(fijos.items())))) == fijos_digest(fijos)


def test_fijos_distintos_del_resumen_registrado_salen_con_2(
    tmp_path: Path, versionado: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    data = copy.deepcopy(versionado)
    data["fijos"]["reserva"] = 0.2
    assert check_structure(data) == []
    assert "enmienda" in "\n".join(check_closed(data, tmp_path).problemas)
    path = tmp_path / "p.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert main(["comprobar", "--parametros", str(path), "--raiz", str(tmp_path), "--sin-git"]) == 2
    assert "no el registrado" in capsys.readouterr().err


def test_main_con_todo_abierto_sale_con_1(
    tmp_path: Path, versionado: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    data = copy.deepcopy(versionado)
    for entrada in data["abiertos"].values():
        entrada["valor"] = None
    assert open_parameters(data) == list(kp.ABIERTOS)
    path = tmp_path / "parametros.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert main(["comprobar", "--parametros", str(path), "--raiz", str(tmp_path)]) == kp.EXIT_OPEN
    salida = capsys.readouterr()
    assert "ABIERTO  presupuesto" in salida.out
    assert f"Quedan {len(kp.ABIERTOS)} parametros abiertos" in salida.err


# ---------------------------------------------------------------------------
# Formulas
# ---------------------------------------------------------------------------


def test_minutos_de_reloj_por_tarea(fijos: dict[str, Any]) -> None:
    assert slot_minutes(fijos) == Fraction(27, 5)  # 720 * 0,9 / 120 = 5,4


@pytest.mark.parametrize(
    ("c", "m", "s", "esperado"),
    [
        (1, 0, 0, 5),  # floor(648 / 120) = floor(5,4)
        (1, 15, 1, 4),  # floor(633 / 120 - 1) = floor(4,275)
        (2, 0, 1, 9),  # floor(10,8 - 1)
        (4, 30, 2, 18),  # floor(4 * 618 / 120 - 2) = floor(18,6)
        (1, 0, 0.4, 5),  # 5,0 exacto: sin error de coma flotante
        (1, 40, 0.1, 4),  # floor(608 / 120 - 0,1) = floor(4,967)
        (1, 0, 3.4, 2),  # 2,0 exacto: el minimo se admite
        (20, 0, 0, 60),  # 108 -> tope de 60
    ],
)
def test_presupuesto_por_tarea(fijos: dict[str, Any], c: int, m: float, s: float, esperado: int) -> None:
    assert budget_minutes(fijos, c, m, s) == esperado


@pytest.mark.parametrize(("c", "m", "s"), [(1, 15, 1), (2, 30, 2), (4, 0, 0.5), (1, 40, 0.1), (3, 100, 0)])
def test_presupuesto_cabe_en_el_limite_del_envio(fijos: dict[str, Any], c: int, m: float, s: float) -> None:
    """Control de la formula: con b, la carga y las N tareas caben en T * (1 - reserva); con b + 1, no."""
    b = budget_minutes(fijos, c, m, s)
    por_tanda = Fraction(fijos["tareas_envio"], c)
    assert m + por_tanda * (b + Fraction(str(s))) <= 648
    assert m + por_tanda * (b + 1 + Fraction(str(s))) > 648


def test_presupuesto_bajo_el_minimo_no_se_fija(fijos: dict[str, Any]) -> None:
    with pytest.raises(PreregError, match="menos que el minimo"):
        budget_minutes(fijos, 1, 0, 3.5)  # floor(1,9) = 1 < 2


@pytest.mark.parametrize(
    ("c", "m", "s"),
    [
        (0, 0, 0),
        (True, 0, 0),
        (1.5, 0, 0),
        (1, -1, 0),
        (1, 0, -0.1),
        (1, float("inf"), 0),
        (1, 0, float("nan")),
    ],
)
def test_presupuesto_rechaza_entradas_invalidas(fijos: dict[str, Any], c: Any, m: Any, s: Any) -> None:
    with pytest.raises(PreregError):
        budget_minutes(fijos, c, m, s)


def test_eval_config_canonico(fijos: dict[str, Any]) -> None:
    assert eval_config_bytes(fijos, 4) == CANONICO_4


def test_corridas_y_horas_de_un_escalon(fijos: dict[str, Any]) -> None:
    # 3 replicas mas 2 de tope por infraestructura, un pase de entrenamiento y 2 condiciones x 2 corridas
    assert plan_slots(fijos, 67, 62, 3, 2) == (3 + 2) * 67 + 62 + 2 * 2 * 67 == 665
    assert plan_slots(fijos, 48, 81, 2, 0) == (2 + 2) * 48 == 192  # sin campana no hay pase de entrenamiento
    assert plan_hours(fijos, 665) == Fraction(665 * 27, 5 * 60)  # 59,85 h
    assert usable_hours(fijos, 30, 2, 4) == 48  # 0,8 * (30 / 2) * 4
    assert usable_hours(fijos, 30, 3, 4) == 32
    with pytest.raises(PreregError):
        usable_hours(fijos, 30, 0, 4)


def test_reinicios_de_cuota() -> None:
    # sabados entre el lunes 2026-10-12 y el jueves 2026-11-05: 17, 24 y 31 de octubre
    assert quota_resets(date(2026, 10, 12), date(2026, 11, 5), 6) == 3
    assert quota_resets(date(2026, 10, 17), date(2026, 10, 17), 6) == 1  # los extremos cuentan
    assert quota_resets(date(2026, 10, 18), date(2026, 10, 23), 6) == 0
    assert quota_resets(date(2026, 11, 6), date(2026, 11, 5), 6) == 0
    assert quota_resets(date(2026, 10, 12), date(2026, 11, 5), 4) == 4  # jueves: 15, 22, 29 y 5
    with pytest.raises(PreregError):
        quota_resets(date(2026, 10, 12), date(2026, 11, 5), 8)


def test_escalera_con_todas_las_tareas(fijos: dict[str, Any]) -> None:
    escalones = ladder(fijos, CONTEOS)
    assert [(e.repo, e.replicas, e.por_condicion, e.slots) for e in escalones] == [
        ("fastapi/fastapi", 3, 2, 665),
        ("fastapi/fastapi", 2, 2, 598),
        ("Textualize/rich", 3, 2, 513),
        ("Textualize/rich", 2, 2, 465),
        ("fastapi/fastapi", 2, 1, 464),
        ("Textualize/rich", 2, 1, 369),
        ("fastapi/fastapi", 2, 0, 268),
        ("Textualize/rich", 2, 0, 192),
    ]
    assert all(e.apto for e in escalones)
    assert (escalones[0].n_test, escalones[0].n_train) == (67, 62)
    with pytest.raises(PreregError):
        ladder(fijos, {**CONTEOS, "psf/requests": -1})


@pytest.mark.parametrize(
    ("horas", "indice"),
    [
        ("59.85", 0),
        ("59.84", 1),
        (50, 2),
        (45, 3),
        ("41.8", 4),
        (35, 5),
        ("24.12", 6),
        (20, 7),
        ("17.27", None),
    ],
)
def test_eleccion_de_escalon(fijos: dict[str, Any], horas: Any, indice: int | None) -> None:
    """Con 24,12 h exactas cabe fastapi sin campana: el limite es inclusivo y fastapi va antes que rich."""
    escalones = ladder(fijos, CONTEOS)
    paso = choose_step(escalones, Fraction(str(horas)))
    assert (None if paso is None else escalones.index(paso)) == indice


def test_escalon_con_pocas_tareas_de_prueba_se_salta(fijos: dict[str, Any]) -> None:
    escalones = ladder(fijos, {**CONTEOS, "fastapi/fastapi": 39, "Textualize/rich": 40})
    assert [e.apto for e in escalones] == [False, False, True, True, False, True, False, True]  # 40 es apto
    paso = choose_step(escalones, Fraction(1000))
    assert paso is not None and (paso.repo, paso.replicas) == ("Textualize/rich", 3)
    assert choose_step(ladder(fijos, {"fastapi/fastapi": 39, "Textualize/rich": 39}), Fraction(1000)) is None


def test_partes_por_replica() -> None:
    # 14 + 60 * (4 + 2 * 0,9) = 362 min = 6,03 h
    assert session_parts(60, 1, 4, 14, 0.9, 12) == 1
    assert session_parts(60, 1, 4, 14, 0.9, 6.04) == 1
    assert session_parts(60, 1, 4, 14, 0.9, 6) == 2
    assert session_parts(60, 2, 4, 14, 0.9, 3) == 2  # 14 + 30 * 5,8 = 188 min
    assert session_parts(60, 1, 4, 14, 0.9, 2) == 4
    with pytest.raises(PreregError):
        session_parts(60, 1, 4, 14, 0.9, 0)


def test_casos_de_ruido_con_enteros(fijos: dict[str, Any]) -> None:
    assert noise_case(fijos, 40, None) == "bajo"  # 6 * 40 <= 6 * 40
    assert noise_case(fijos, 40, 7) == "intermedio"
    assert noise_case(fijos, 40, 10) == "intermedio"  # 10 * 24 = 240 no supera 6 * 40
    assert noise_case(fijos, 40, 11) == "dominante"
    assert noise_case(fijos, 67, 10) == "bajo" and noise_case(fijos, 67, 11) == "intermedio"
    assert noise_case(fijos, 24, 6) == "intermedio" and noise_case(fijos, 24, 7) == "dominante"
    # con el mismo calculo que el analisis: discordantes observados que admite «ruido bajo»
    assert [noise_case_for_observed(fijos, 67, d) for d in (0, 10, 11)] == ["bajo", "bajo", "intermedio"]
    assert [noise_case_for_observed(fijos, 48, d) for d in (2, 3)] == ["bajo", "intermedio"]
    assert [noise_case_for_observed(fijos, 40, d) for d in (1, 2)] == ["bajo", "intermedio"]


def test_cli_ruido(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["ruido", "--tareas", "40", "48", "67"]) == 0
    filas = [linea.split() for linea in capsys.readouterr().out.splitlines()[1:]]
    assert filas == [["40", "6/40", "1", "11"], ["48", "6/48", "2", "18"], ["67", "6/67", "10", "44"]]
    assert main(["ruido", "--tareas", "5"]) == 2


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


ARCHIVO = {"ruta": "a/b.json", "sha256": "a" * 64}
CUOTA = {
    "gpu_semanal_horas": 30,
    "factor_l4x4": 2,
    "dia_reinicio": 6,
    "fuente": "f",
    "fecha_lectura": "2026-10-10",
}
CORRIDA = {"replicas": 3, "partes": 1, "fecha_compuerta": "2026-10-15"}


@pytest.mark.parametrize(
    ("ruta", "valor", "texto"),
    [
        (("schema_version",), "otro/9", "schema_version"),
        (("enmiendas",), [{"fecha": "2026-10-04", "motivo": "m"}], "enmiendas"),
        (("enmiendas",), {}, "enmiendas"),
        (("fijos", "reserva"), 1, "fijos.reserva"),
        (("fijos", "reserva"), float("nan"), "fijos.reserva"),
        (("fijos", "tareas_envio"), True, "fijos.tareas_envio"),
        (("fijos", "regla_particion"), "temporal_stratified", "fijos.regla_particion"),
        (("fijos", "escalera"), [["fastapi/fastapi", 1, 2]], "fijos.escalera"),
        (("fijos", "escalera"), [["fastapi/fastapi", 2, 2]], "sin campana"),
        (("fijos", "escalera"), [["a/b", 2, 0], ["a/b", 2, 0]], "repite"),
        (("fijos", "tasks_sha256"), "E4B3", "fijos.tasks_sha256"),
        (("fijos", "tasks_sha256"), "g" * 64, "fijos.tasks_sha256"),
        (("fijos", "minimo_max_time_minutes"), 61, "supera al tope"),
        (("fijos", "umbral_ruido_bajo"), [6, 24], "umbral_ruido_bajo"),
        (("fijos", "umbral_ruido_bajo"), [0.15, 1], "umbral_ruido_bajo"),
        (("fijos", "alfa"), 1, "fijos.alfa"),
        (("fijos", "alfa"), 0, "fijos.alfa"),
        (("fijos", "fraccion_utilizable"), 1.01, "fijos.fraccion_utilizable"),
        (("fijos", "fecha_corte_campana"), "5 de noviembre", "fijos.fecha_corte_campana"),
        (("fijos", "fecha_corte_campana"), "2026-02-30", "fijos.fecha_corte_campana"),
        (("fijos", "fecha_corte_campana"), "2026-11-12", "fechas"),
        (("fijos", "fecha_minima_compuerta"), "2026-10-20", "fechas"),
        (("fijos", "fecha_registro"), "2026-10-13", "fechas"),
        (("fijos", "fecha_registro"), "ayer", "fijos.fecha_registro"),
        (("fijos", "terciles"), {"parche_lineas": [26, 5], "enunciado_caracteres": [1, 2]}, "fijos.terciles"),
        (("fijos", "decisiones"), {"x": []}, "fijos.decisiones"),
        (("abiertos", "corrida", "valor"), {**CORRIDA, "replicas": 1}, "abiertos.corrida"),
        (("abiertos", "corrida", "valor"), {**CORRIDA, "partes": 0}, "abiertos.corrida"),
        (("abiertos", "corrida", "valor"), {**CORRIDA, "extra": 1}, "abiertos.corrida"),
        (("abiertos", "corrida", "valor"), {**CORRIDA, "fecha_compuerta": "15/10/2026"}, "abiertos.corrida"),
        (("abiertos", "corrida", "regla"), " ", "abiertos.corrida"),
        (("abiertos", "cuota", "valor"), {"gpu_semanal_horas": 30}, "abiertos.cuota"),
        (("abiertos", "cuota", "valor"), {**CUOTA, "dia_reinicio": 8}, "abiertos.cuota"),
        (("abiertos", "cuota", "valor"), {**CUOTA, "gpu_semanal_horas": float("inf")}, "abiertos.cuota"),
        (("abiertos", "cuota", "valor"), {**CUOTA, "factor_l4x4": 0}, "abiertos.cuota"),
        (("abiertos", "subconjunto"), {"valor": None, "regla": "r"}, "abiertos.subconjunto"),
        (
            ("abiertos", "subconjunto"),
            {"valor": None, "regla": "r", "cierra": "c", "x": 1},
            "abiertos.subconjunto",
        ),
        (("abiertos", "piloto", "valor"), {**ARCHIVO, "sha256": "A" * 64}, "abiertos.piloto"),
        (("abiertos", "piloto", "valor"), {**ARCHIVO, "sha256": "a" * 63}, "abiertos.piloto"),
        (("abiertos", "piloto", "valor"), {**ARCHIVO, "ruta": "../fuera.json"}, "abiertos.piloto"),
        (("abiertos", "piloto", "valor"), {**ARCHIVO, "ruta": "/abs/x.json"}, "abiertos.piloto"),
        (("abiertos", "piloto", "valor"), {**ARCHIVO, "ruta": "C:\\x.json"}, "abiertos.piloto"),
        (("abiertos", "piloto", "valor"), {**ARCHIVO, "ruta": "a/./b.json"}, "abiertos.piloto"),
        (
            ("abiertos", "decisiones_dueno", "valor"),
            [{"decision": "x", "opcion": "y"}],
            "abiertos.decisiones_dueno",
        ),
        (("abiertos", "decisiones_dueno", "valor"), {}, "abiertos.decisiones_dueno"),
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
    con["fijos"]["nuevo"] = 1
    assert any("'fijos' debe tener" in p for p in check_structure(con))
    con = copy.deepcopy(versionado)
    con["abiertos"]["nuevo"] = {"valor": None, "regla": "r", "cierra": "c"}
    assert any("'abiertos' debe tener" in p for p in check_structure(con))
    assert check_structure({**versionado, "fijos": []})


# ---------------------------------------------------------------------------
# Parametros cerrados contra sus reglas
# ---------------------------------------------------------------------------


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git(raiz: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=prueba", "-c", "user.email=prueba@example.invalid", *args],
        cwd=raiz,
        check=True,
        capture_output=True,
    )


class Arbol:
    """Un pre-registro con todo cerrado y coherente sobre tareas sinteticas (61 + 45 + 12).

    Los registros son atributos que cada prueba puede alterar antes de ``escribir``; los hashes se
    encadenan al escribir, igual que en los commits C0.5 a C5.
    """

    def __init__(self, raiz: Path, versionado: dict[str, Any]) -> None:
        self.raiz = raiz
        self.fijos = copy.deepcopy(versionado["fijos"])
        self.base = versionado
        self.tareas = [
            {
                "instance_id": f"{corto}_{i:03d}",
                "repo": repo,
                "created_at": f"2026-01-{i % 28 + 1:02d}T00:00:00Z",
            }
            for repo, corto, n in (
                ("fastapi/fastapi", "fa", 61),
                ("Textualize/rich", "ri", 45),
                ("psf/requests", "re", 12),
            )
            for i in range(n)
        ]
        self.clases = {t["instance_id"]: "discrimina" for t in self.tareas}
        self.clases["fa_000"] = "dorado_falla"
        self.ensayo: dict[str, Any] = {
            "schema_version": kp.ESQUEMA_ENSAYO,
            "fecha": "2026-10-05",
            "notebook": "cuenta/ensayo-inventado v1",
            "modelo": "modelo-inventado/1",
            "guion_servidor_sha256": "1" * 64,
            "docker_disponible": False,
            "backend": "subprocess",
            "servidor_arranca": True,
            "envio_compila": True,
            "carga_modelo_segundos": 800,
            "sesion_max_horas": 12,
            "tokens_por_segundo": 25.5,
            "max_time_minutes_ensayo": 5,
            "turnos_por_tarea": [9, 4, 12, 5],
            "peticiones_al_modelo": 30,
            "rechazos_por_contexto": {"16384": 0},
        }
        self.entorno: dict[str, Any] = {
            "schema_version": kp.ESQUEMA_ENTORNO,
            "backend": "subprocess",
            "imagen": "python-inventado",
            "version_arnes": "0.0.0",
            "ruedas_sha256": "2" * 64,
            "arreglos": [],
        }
        self.segundos = [50, 58]  # media 54 s = 0,9 min
        # 3 sabados entre el 12 de octubre y el 5 de noviembre: 0,8 * (60 / 2) * 3 = 72 h;
        # escalon 1 con 60/45/12 validas: 5 * 60 + 57 + 4 * 60 = 597 corridas -> 53,73 h
        self.cuota: dict[str, Any] = {
            "gpu_semanal_horas": 60,
            "factor_l4x4": 2,
            "dia_reinicio": 6,
            "fuente": "panel de cuotas, leido por el dueno",
            "fecha_lectura": "2026-10-10",
        }
        self.repo = "fastapi/fastapi"
        # carga 800 s -> m = 14 min; s = 0,9; b = floor((648 - 14) / 120 - 0,9) = floor(4,38) = 4
        self.piloto: dict[str, Any] = {
            "schema_version": kp.ESQUEMA_PILOTO,
            "fecha": "2026-10-14",
            "numero": 1,
            "tareas": 8,
            "degenerado": False,
            "concurrencia": 1,
            "fuente_concurrencia": {"tipo": "supuesto", "referencia": "sin fuente oficial"},
            "carga_modelo_segundos": 800,
            "prompt_muestra_presupuesto": True,
        }
        self.b = 4
        self.sampling_envio = SAMPLING_KIT
        self.eval_config_envio: bytes | None = None  # None: el canonico
        self.citar_fuera = False  # citar un eval_config.yaml que no es el del directorio del envio
        self.fecha_validez = "2026-10-08"
        self.corrida: dict[str, Any] = {"replicas": 3, "partes": 1, "fecha_compuerta": "2026-10-15"}
        self.decisiones: list[dict[str, str]] = []
        self.abrir: tuple[str, ...] = ()
        self.alterar_subconjunto: Callable[[dict[str, Any]], None] | None = None
        self.alterar_validez: Callable[[dict[str, Any]], None] | None = None

    def fechar(self, **fechas: str) -> None:
        """Cambia las fechas declaradas: ensayo, validez, cuota, piloto y compuerta."""
        if "ensayo" in fechas:
            self.ensayo["fecha"] = fechas["ensayo"]
        if "validez" in fechas:
            self.fecha_validez = fechas["validez"]
        if "cuota" in fechas:
            self.cuota["fecha_lectura"] = fechas["cuota"]
        if "piloto" in fechas:
            self.piloto["fecha"] = fechas["piloto"]
        if "compuerta" in fechas:
            self.corrida["fecha_compuerta"] = fechas["compuerta"]

    def _json(self, nombre: str, obj: Any) -> dict[str, str]:
        data = json.dumps(obj).encode("utf-8")
        (self.raiz / nombre).write_bytes(data)
        return {"ruta": nombre, "sha256": _sha(data)}

    def escribir(self, *, git: bool = False) -> dict[str, Any]:
        raiz = self.raiz
        tasks = raiz / "tasks.jsonl"
        tasks.write_bytes("".join(json.dumps(t) + "\n" for t in self.tareas).encode("utf-8"))
        self.fijos["tasks_sha256"] = _sha(tasks.read_bytes())
        self.fijos["tareas_publicas"] = len(self.tareas)
        ensayo = self._json("ensayo.json", self.ensayo)
        entorno = self._json("entorno.json", {"ensayo_sha256": ensayo["sha256"], **self.entorno})
        validez_obj: dict[str, Any] = {
            "schema_version": kp.ESQUEMA_VALIDEZ,
            "fecha": self.fecha_validez,
            "sha256_tasks": self.fijos["tasks_sha256"],
            "entorno_sha256": entorno["sha256"],
            "tareas": [
                {
                    "instance_id": t["instance_id"],
                    "repo": t["repo"],
                    "clase": self.clases[t["instance_id"]],
                    "sin_parche_segundos": self.segundos,
                    "con_dorado_segundos": [60, 61],
                }
                for t in self.tareas
            ],
            "tareas_invalidas": [
                {"instance_id": i, "clase": c} for i, c in sorted(self.clases.items()) if c != "discrimina"
            ],
        }
        if self.alterar_validez:
            self.alterar_validez(validez_obj)
        validez = self._json("validez.json", validez_obj)
        salida = raiz / "subconjunto.json"
        argv = ["--tasks", str(tasks), "--calibracion", str(raiz / "validez.json")]
        argv += ["--rule", "leave_one_repo_out", "--held-out-repo", self.repo, "--output", str(salida)]
        assert kaggle_split.main(argv) == 0
        # como en el repositorio: finales de linea LF (el blob de git), no los del sistema
        salida.write_bytes(salida.read_bytes().replace(b"\r\n", b"\n"))
        if self.alterar_subconjunto:
            sub = json.loads(salida.read_text(encoding="utf-8"))
            self.alterar_subconjunto(sub)
            salida.write_bytes(json.dumps(sub, indent=2, ensure_ascii=False).encode("utf-8"))
        subconjunto = {"ruta": "subconjunto.json", "sha256": _sha(salida.read_bytes())}
        piloto = self._json("piloto.json", {"subconjunto_sha256": subconjunto["sha256"], **self.piloto})
        envio = raiz / "envio"
        envio.mkdir(exist_ok=True)
        (envio / "agent.yaml").write_bytes(b"nombre: inventado\n")
        canonico = eval_config_bytes(self.fijos, self.b)
        (envio / "eval_config.yaml").write_bytes(self.eval_config_envio or canonico)
        (envio / "configs").mkdir(exist_ok=True)
        (envio / "configs" / "sampling.yaml").write_bytes(self.sampling_envio)
        manifiesto = raiz / kp.MANIFEST_REL
        manifiesto.parent.mkdir(parents=True, exist_ok=True)
        entrada = {"path": kp.SAMPLING_REL, "size": len(SAMPLING_KIT), "sha256": _sha(SAMPLING_KIT)}
        manifiesto.write_text(json.dumps({"files": [entrada]}), encoding="utf-8")
        citado = "eval_config_citado.yaml" if self.citar_fuera else "envio/eval_config.yaml"
        if self.citar_fuera:
            (raiz / citado).write_bytes(canonico)
        data = copy.deepcopy(self.base)
        data["fijos"] = self.fijos
        cerrar: dict[str, Any] = {
            "ensayo_notebook": ensayo,
            "entorno_sandbox": entorno,
            "validez_tareas": validez,
            "cuota": self.cuota,
            "subconjunto": subconjunto,
            "piloto": piloto,
            "presupuesto": {
                "eval_config_ruta": citado,
                "eval_config_sha256": _sha((raiz / citado).read_bytes()),
                "envio_sha256": kaggle_replicas.sha256_directory(envio),
            },
            "corrida": self.corrida,
            "decisiones_dueno": self.decisiones,
        }
        for nombre, valor in cerrar.items():
            data["abiertos"][nombre]["valor"] = None if nombre in self.abrir else valor
        (raiz / "parametros.json").write_text(json.dumps(data), encoding="utf-8")
        if git:
            _git(raiz, "init", "-q")
            _git(raiz, "add", "-A")
            _git(raiz, "commit", "-q", "-m", "cierre sintetico")
            _git(raiz, "update-ref", "refs/remotes/origin/main", "HEAD")
        return data

    def argv(self, *extra: str) -> list[str]:
        return [
            "comprobar",
            "--parametros",
            str(self.raiz / "parametros.json"),
            "--raiz",
            str(self.raiz),
            *extra,
        ]

    def completo(self) -> list[str]:
        return self.argv("--tasks", str(self.raiz / "tasks.jsonl"), "--envio", str(self.raiz / "envio"))


@pytest.fixture
def arbol(tmp_path: Path, versionado: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> Arbol:
    a = Arbol(tmp_path, versionado)
    # los fijos sinteticos (otro tasks.jsonl y otro numero de tareas) tienen su propio resumen registrado
    fijos = copy.deepcopy(a.fijos)
    tasks = "".join(json.dumps(t) + "\n" for t in a.tareas).encode("utf-8")
    fijos["tasks_sha256"], fijos["tareas_publicas"] = _sha(tasks), len(a.tareas)
    monkeypatch.setattr(kp, "FIJOS_SHA256", fijos_digest(fijos))
    return a


def _problemas(a: Arbol, *, completo: bool = True) -> str:
    """Escribe el arbol y exige salida 2; devuelve el texto de los problemas."""
    data = a.escribir()
    assert check_structure(data) == []
    extra = {"tasks": a.raiz / "tasks.jsonl", "envio": a.raiz / "envio"} if completo else {}
    problemas = check_closed(data, a.raiz, **extra).problemas
    assert main([*(a.completo() if completo else a.argv()), "--sin-git"]) == 2
    return "\n".join(problemas)


def test_todo_cerrado_coherente_y_commiteado_sale_con_0(
    arbol: Arbol, capsys: pytest.CaptureFixture[str]
) -> None:
    data = arbol.escribir(git=True)
    assert check_structure(data) == [] and open_parameters(data) == []
    assert main(arbol.completo()) == 0
    assert "Todos los parametros estan cerrados" in capsys.readouterr().out


def test_comprobacion_parcial_sale_con_1(arbol: Arbol, capsys: pytest.CaptureFixture[str]) -> None:
    arbol.escribir(git=True)
    for argv, texto in [
        (arbol.argv("--envio", str(arbol.raiz / "envio")), "--tasks"),
        (arbol.argv("--tasks", str(arbol.raiz / "tasks.jsonl")), "--envio"),
        ([*arbol.completo(), "--sin-git"], "--sin-git"),
    ]:
        assert main(argv) == 1
        assert texto in capsys.readouterr().err


def test_archivo_citado_sin_commitear_o_modificado(arbol: Arbol, capsys: pytest.CaptureFixture[str]) -> None:
    arbol.escribir(git=True)
    (arbol.raiz / "nuevo.txt").write_text("ajeno", encoding="utf-8")  # un archivo ajeno no molesta
    assert main(arbol.completo()) == 0
    _git(arbol.raiz, "rm", "-q", "--cached", "piloto.json")
    assert main(arbol.completo()) == 2
    assert "piloto.json: no esta versionado" in capsys.readouterr().err


def test_archivo_citado_con_cambios_sin_commitear(arbol: Arbol, capsys: pytest.CaptureFixture[str]) -> None:
    data = arbol.escribir(git=True)
    # mismo contenido para el hash declarado, pero el indice de git tiene otra version
    original = (arbol.raiz / "ensayo.json").read_bytes()
    (arbol.raiz / "ensayo.json").write_bytes(original + b" ")
    _git(arbol.raiz, "add", "ensayo.json")
    _git(arbol.raiz, "commit", "-q", "-m", "otra version")
    (arbol.raiz / "ensayo.json").write_bytes(original)
    assert check_closed(data, arbol.raiz, git=False).problemas == []
    assert main(arbol.completo()) == 2
    assert "ensayo.json: tiene cambios sin commitear" in capsys.readouterr().err


def test_archivo_citado_alterado_o_ausente(arbol: Arbol) -> None:
    arbol.escribir()
    (arbol.raiz / "envio" / "eval_config.yaml").write_bytes(b"evaluation:\n  max_time_minutes: 4\n")
    assert main([*arbol.completo(), "--sin-git"]) == 2
    arbol.escribir()
    (arbol.raiz / "piloto.json").unlink()
    data = load_params(arbol.raiz / "parametros.json")
    assert "piloto: no existe el archivo" in "\n".join(check_closed(data, arbol.raiz).problemas)


@pytest.mark.parametrize(
    "contenido",
    [
        CANONICO_4.replace(b"minutes: 4", b"minutes: 3"),
        CANONICO_4.replace(b"minutes: 4", b"minutes: 5"),
        CANONICO_4.replace(b"seconds: 300", b"seconds: 3e2"),
        CANONICO_4 + b"evaluation: {max_time_minutes: 60}\n",
        b"evaluation:\r\n  timeout_seconds: 300\r\n  max_tool_calls: 100\r\n  max_time_minutes: 4\r\n"
        b"  max_turns: 500\r\n",
        b"\xff\xfe no es utf-8",
    ],
)
def test_eval_config_que_no_es_el_canonico(arbol: Arbol, contenido: bytes) -> None:
    """Menos o mas minutos que la formula, otro modo de escribir un numero, una clave repetida: salida 2."""
    arbol.escribir()
    (arbol.raiz / "envio" / "eval_config.yaml").write_bytes(contenido)
    data = load_params(arbol.raiz / "parametros.json")
    data["abiertos"]["presupuesto"]["valor"]["eval_config_sha256"] = _sha(contenido)
    (arbol.raiz / "parametros.json").write_text(json.dumps(data), encoding="utf-8")
    assert "bytes canonicos" in "\n".join(check_closed(data, arbol.raiz).problemas)
    assert main([*arbol.argv(), "--sin-git"]) == 2


def test_hash_del_envio_recalculado(arbol: Arbol) -> None:
    arbol.escribir()
    (arbol.raiz / "envio" / "agent.yaml").write_bytes(b"nombre: otro\n")
    data = load_params(arbol.raiz / "parametros.json")
    assert check_closed(data, arbol.raiz).problemas == []  # sin --envio no se puede ver
    problemas = check_closed(data, arbol.raiz, envio=arbol.raiz / "envio").problemas
    assert "el hash del envio es" in "\n".join(problemas)
    assert "presupuesto" in "\n".join(
        check_closed(data, arbol.raiz, envio=arbol.raiz / "no_existe").problemas
    )


def test_registro_alterado_sin_cambiar_nada_que_se_derive(arbol: Arbol) -> None:
    """Un dato del ensayo que ninguna regla usa: solo el hash declarado delata el cambio."""
    data = arbol.escribir()
    obj = json.loads((arbol.raiz / "ensayo.json").read_text(encoding="utf-8"))
    obj["tokens_por_segundo"] = 99
    (arbol.raiz / "ensayo.json").write_bytes(json.dumps(obj).encode("utf-8"))
    assert "ensayo_notebook: el SHA-256" in "\n".join(check_closed(data, arbol.raiz).problemas)
    assert main([*arbol.argv(), "--sin-git"]) == 2


def test_un_archivo_en_dos_papeles(arbol: Arbol) -> None:
    data = arbol.escribir()
    data["abiertos"]["piloto"]["valor"] = dict(data["abiertos"]["ensayo_notebook"]["valor"])
    assert "dos papeles" in "\n".join(check_closed(data, arbol.raiz).problemas)


@pytest.mark.parametrize(
    ("abrir", "texto"),
    [
        (("ensayo_notebook",), "entorno_sandbox: no puede cerrarse antes que ensayo_notebook"),
        (("entorno_sandbox",), "validez_tareas: no puede cerrarse antes que entorno_sandbox"),
        (("cuota",), "subconjunto: no puede cerrarse antes que cuota"),
        (("validez_tareas",), "subconjunto: no puede cerrarse antes que validez_tareas"),
        (("subconjunto",), "piloto: no puede cerrarse antes que subconjunto"),
        (("piloto",), "presupuesto: no puede cerrarse antes que piloto"),
        (("presupuesto",), "corrida: no puede cerrarse antes que presupuesto"),
    ],
)
def test_orden_de_cierre(arbol: Arbol, abrir: tuple[str, ...], texto: str) -> None:
    arbol.abrir = abrir
    assert texto in _problemas(arbol, completo=False)


def test_cierre_parcial_valido_sale_con_1(arbol: Arbol) -> None:
    arbol.abrir = ("presupuesto", "corrida", "decisiones_dueno")
    data = arbol.escribir()
    assert check_closed(data, arbol.raiz).problemas == []
    assert open_parameters(data) == ["presupuesto", "corrida", "decisiones_dueno"]
    assert main([*arbol.argv(), "--sin-git"]) == 1


# --- ensayo de notebook y entorno ---


@pytest.mark.parametrize(
    ("cambio", "texto"),
    [
        ({"servidor_arranca": False}, "no es viable"),
        ({"envio_compila": False}, "no es viable"),
        ({"turnos_por_tarea": [9, 4, 4, 5]}, "no es viable"),  # 2 de 4 con 5 turnos o mas basta; 1 de 4 no
        ({"turnos_por_tarea": [4, 4, 4]}, "no es viable"),
        ({"backend": "docker"}, "no tiene Docker"),
        ({"rechazos_por_contexto": {"16384": 1}}, "falta el conteo de rechazos con 8192"),
        ({"rechazos_por_contexto": {"16384": 1, "8192": 2}}, "todos los candidatos"),
        ({"backend": "podman"}, "valores invalidos"),
        ({"sesion_max_horas": 0}, "valores invalidos"),
        ({"schema_version": "otro/1"}, "valores invalidos"),
        ({"extra": 1}, "debe tener las claves"),
    ],
)
def test_ensayo_de_notebook_invalido_o_no_viable(arbol: Arbol, cambio: dict[str, Any], texto: str) -> None:
    arbol.ensayo.update(cambio)
    if cambio.get("turnos_por_tarea") == [9, 4, 4, 5]:
        arbol.ensayo["turnos_por_tarea"] = [9, 4, 4, 4]
    assert texto in _problemas(arbol)


def test_ensayo_viable_en_la_frontera_y_con_8192(arbol: Arbol) -> None:
    arbol.ensayo["turnos_por_tarea"] = [5, 4, 4, 5]  # justo la mitad con el minimo de turnos
    arbol.ensayo["rechazos_por_contexto"] = {"16384": 3, "8192": 0}
    data = arbol.escribir()
    assert check_closed(data, arbol.raiz).problemas == []
    ensayo = json.loads((arbol.raiz / "ensayo.json").read_text(encoding="utf-8"))
    assert kp.output_tokens(arbol.fijos, ensayo) == 8192
    assert kp.output_tokens(arbol.fijos, {"rechazos_por_contexto": {"16384": 0}}) == 16384


def test_entorno_que_no_sigue_al_ensayo(arbol: Arbol) -> None:
    arbol.ensayo.update({"docker_disponible": True})
    arbol.entorno["backend"] = "docker"
    assert "el backend no es el que fijo el ensayo" in _problemas(arbol)


def test_entorno_con_otro_ensayo(arbol: Arbol) -> None:
    data = arbol.escribir()
    obj = json.loads((arbol.raiz / "entorno.json").read_text(encoding="utf-8"))
    obj["ensayo_sha256"] = "9" * 64
    nuevo = json.dumps(obj).encode("utf-8")
    (arbol.raiz / "entorno.json").write_bytes(nuevo)
    data["abiertos"]["entorno_sandbox"]["valor"]["sha256"] = _sha(nuevo)
    assert "'ensayo_sha256' no es el del ensayo" in "\n".join(check_closed(data, arbol.raiz).problemas)


# --- validez ---


def test_validez_con_menos_tareas_o_repetidas(arbol: Arbol) -> None:
    arbol.alterar_validez = lambda v: v["tareas"].pop()
    assert "tareas distintas" in _problemas(arbol)


def test_validez_con_una_tarea_repetida(arbol: Arbol) -> None:
    def repetir(v: dict[str, Any]) -> None:
        v["tareas"][-1] = dict(v["tareas"][-2])

    arbol.alterar_validez = repetir
    assert "tareas distintas" in _problemas(arbol)


@pytest.mark.parametrize(
    "alterar",
    [
        lambda v: v["tareas_invalidas"].clear(),
        lambda v: v["tareas_invalidas"].append({"instance_id": "ri_000", "clase": "inestable"}),
        lambda v: v["tareas_invalidas"].__setitem__(0, {"instance_id": "fa_000", "clase": "inestable"}),
        lambda v: v["tareas_invalidas"].append(dict(v["tareas_invalidas"][0])),
    ],
)
def test_validez_con_invalidas_que_no_son_las_no_discrimina(arbol: Arbol, alterar: Any) -> None:
    arbol.alterar_validez = alterar
    assert "tareas_invalidas" in _problemas(arbol)


@pytest.mark.parametrize(
    ("alterar", "texto"),
    [
        (lambda v: v.__setitem__("sha256_tasks", "d" * 64), "sha256_tasks"),
        (lambda v: v.__setitem__("entorno_sha256", "d" * 64), "entorno_sha256"),
        (lambda v: v["tareas"][0].__setitem__("clase", "rara"), "valores invalidos"),
        (lambda v: v["tareas"][0].pop("repo"), "valores invalidos"),
        (lambda v: v.pop("tareas_invalidas"), "debe tener las claves"),
        (lambda v: [t.__setitem__("sin_parche_segundos", []) for t in v["tareas"]], "duracion sin parche"),
    ],
)
def test_validez_mal_formada(arbol: Arbol, alterar: Any, texto: str) -> None:
    arbol.alterar_validez = alterar
    assert texto in _problemas(arbol)


def test_validez_json_roto(arbol: Arbol) -> None:
    for contenido, texto in [(b"[]", "debe ser un objeto"), (b'{"a": 1, "a": 2}', "no es JSON valido")]:
        data = arbol.escribir()
        (arbol.raiz / "validez.json").write_bytes(contenido)
        data["abiertos"]["validez_tareas"]["valor"]["sha256"] = _sha(contenido)
        assert texto in "\n".join(check_closed(data, arbol.raiz).problemas)


def test_entorno_roto_exige_la_decision_del_dueno(arbol: Arbol) -> None:
    """En requests (12 tareas), 7 no discriminan: mas de la mitad. Con 6 no hace falta decision."""
    for i in range(7):
        arbol.clases[f"re_{i:03d}"] = "dorado_falla"
    assert "faltan las decisiones versionadas ['entorno_sin_arreglo']" in _problemas(arbol)
    decision = {"decision": "entorno_sin_arreglo", "fecha": "2026-10-09", "referencia": "commit inventado"}
    arbol.decisiones = [{**decision, "opcion": "seguir_excluyendo"}]
    data = arbol.escribir()
    assert check_closed(data, arbol.raiz).problemas == []
    arbol.decisiones = [{**decision, "opcion": "detener"}]
    assert "la compuerta no se abre" in _problemas(arbol)
    arbol.clases["re_006"] = "discrimina"  # 6 de 12: ya no es mas de la mitad
    arbol.decisiones = [{**decision, "opcion": "seguir_excluyendo"}]
    assert "no corresponde a ninguna condicion presente" in _problemas(arbol)


@pytest.mark.parametrize(
    ("decisiones", "texto"),
    [
        ([{"decision": "inventada", "opcion": "seguir_excluyendo"}], "no esta entre las opciones"),
        ([{"decision": "campana_no_cabe", "opcion": "seguir_excluyendo"}], "no esta entre las opciones"),
        ([{"decision": "campana_no_cabe", "opcion": "seguir_solo_linea_base"}], "ninguna condicion presente"),
        ([{"decision": "sin_escalon", "opcion": "enmienda_v2"}], "la compuerta no se abre"),
    ],
)
def test_decisiones_fuera_de_lugar(arbol: Arbol, decisiones: list[dict[str, str]], texto: str) -> None:
    arbol.decisiones = [{**d, "fecha": "2026-10-09", "referencia": "r"} for d in decisiones]
    assert texto in _problemas(arbol)


def test_decision_repetida(arbol: Arbol) -> None:
    for i in range(7):
        arbol.clases[f"re_{i:03d}"] = "dorado_falla"
    d = {
        "decision": "entorno_sin_arreglo",
        "opcion": "seguir_excluyendo",
        "fecha": "2026-10-09",
        "referencia": "r",
    }
    arbol.decisiones = [d, dict(d)]
    assert "aparece dos veces" in _problemas(arbol)


# --- subconjunto, cuota y escalera ---


def test_repositorio_que_no_da_la_escalera(arbol: Arbol) -> None:
    # 0,8 * (40 / 2) * 3 = 48 h: fastapi con 3 replicas (53,73 h) no cabe; con 2 (597 - 60 = 537 -> 48,33 h)
    # tampoco; rich con 3 replicas (5 * 45 + 72 + 180 = 477 -> 42,93 h) si
    arbol.cuota["gpu_semanal_horas"] = 40
    assert "la escalera da 'Textualize/rich'" in _problemas(arbol)


def test_el_factor_de_cuota_releido_cuenta(arbol: Arbol) -> None:
    arbol.cuota["factor_l4x4"] = 3  # 0,8 * (60 / 3) * 3 = 48 h: como arriba
    assert "la escalera da 'Textualize/rich'" in _problemas(arbol)


def test_el_dia_de_reinicio_cuenta(arbol: Arbol) -> None:
    arbol.cuota["dia_reinicio"] = 4  # jueves: 4 reinicios -> 96 h; sigue fastapi con 3 replicas
    data = arbol.escribir()
    assert check_closed(data, arbol.raiz).problemas == []
    arbol.cuota.update({"dia_reinicio": 6, "gpu_semanal_horas": 45})  # 0,8 * 22,5 * 3 = 54 h >= 53,73
    assert check_closed(arbol.escribir(), arbol.raiz).problemas == []
    arbol.cuota["gpu_semanal_horas"] = 44.7  # 53,64 h < 53,73: ya no cabe el escalon 1
    assert "corrida: se declaran 3 replicas; la escalera da 2" in _problemas(arbol)


def test_ningun_escalon_cabe(arbol: Arbol) -> None:
    arbol.cuota["gpu_semanal_horas"] = 1
    assert "ningun escalon apto cabe" in _problemas(arbol)


def test_cuota_leida_despues_del_corte(arbol: Arbol) -> None:
    arbol.cuota["fecha_lectura"] = "2026-11-06"
    assert "posterior al corte" in _problemas(arbol)


@pytest.mark.parametrize(
    ("alterar", "texto"),
    [
        (lambda s: s["rule"].__setitem__("name", "temporal_stratified_by_repo"), "la regla es"),
        (lambda s: s.__setitem__("sha256_tasks", "c" * 64), "tasks_sha256"),
        (lambda s: s["rule"].__setitem__("exclusiones_origen", "sin_calibracion"), "exclusiones_origen"),
        (lambda s: s["rule"].__setitem__("excluded_instance_ids", []), "no son las 'tareas_invalidas'"),
        (lambda s: s["rule"].__setitem__("excluded_ids_inexistentes", ["zz_1"]), "no existen en tasks.jsonl"),
        (lambda s: s["test"].append(s["train"].pop()), "se esperaban 60 tareas de prueba"),
        (lambda s: s["test"].append("fa_000"), "disjuntas"),
        (lambda s: s["test"].__setitem__(0, s["train"][0]), "disjuntas"),
        (lambda s: s["test"].__setitem__(0, s["test"][1]), "repetidos"),
        (lambda s: s["test"].pop(), "se esperaban 60 tareas de prueba"),
        (lambda s: s["test"].append("zz_nueva"), "se esperaban 60 tareas de prueba"),
        (lambda s: s["train"].pop(), "se esperaban 60 tareas de prueba"),
        (lambda s: s.__setitem__("counts", {}), "counts"),
        (lambda s: s.__setitem__("counts", None), "counts"),
        (lambda s: s["counts"].__setitem__("total_validas", 118), "'counts' no coincide"),
        (lambda s: s["counts"].__setitem__("total_test", 61), "'counts' no coincide"),
        (
            lambda s: s["counts"]["by_repo"]["psf/requests"].__setitem__("total_valid", 13),
            "'counts' no coincide",
        ),
        (lambda s: s.__setitem__("test", "fa_001"), "listas de identificadores"),
        (lambda s: s.pop("rule"), "objeto JSON con 'rule'"),
    ],
)
def test_subconjunto_que_no_cuadra(arbol: Arbol, alterar: Any, texto: str) -> None:
    arbol.alterar_subconjunto = alterar
    assert texto in _problemas(arbol, completo=False)


def test_subconjunto_coherente_pero_distinto_del_generado(arbol: Arbol) -> None:
    """Listas con los mismos conjuntos y otro orden: solo regenerar desde tasks.jsonl lo descubre."""
    arbol.alterar_subconjunto = lambda s: s["train"].reverse()
    data = arbol.escribir()
    assert check_closed(data, arbol.raiz).problemas == []
    assert "byte a byte" in "\n".join(
        check_closed(data, arbol.raiz, tasks=arbol.raiz / "tasks.jsonl").problemas
    )
    otro = arbol.raiz / "otro.jsonl"
    otro.write_bytes((arbol.raiz / "tasks.jsonl").read_bytes() + b"\n")
    assert "no tiene el tasks_sha256" in "\n".join(check_closed(data, arbol.raiz, tasks=otro).problemas)


# --- piloto, presupuesto y corrida ---


@pytest.mark.parametrize(
    ("cambio", "texto"),
    [
        ({"degenerado": True}, "piloto_degenerado"),
        ({"prompt_muestra_presupuesto": False}, "piloto_degenerado"),
        ({"numero": 3}, "numero maximo de pilotos"),
        ({"tareas": 9}, "numero maximo de pilotos"),
        ({"concurrencia": 2}, "exige una fuente oficial"),
        ({"fuente_concurrencia": {"tipo": "foro", "referencia": "r"}}, "valores invalidos"),
        ({"subconjunto_sha256": "7" * 64}, "'subconjunto_sha256' no es el del subconjunto"),
        ({"carga_modelo_segundos": -1}, "valores invalidos"),
    ],
)
def test_piloto_invalido(arbol: Arbol, cambio: dict[str, Any], texto: str) -> None:
    arbol.piloto.update(cambio)
    if "subconjunto_sha256" in cambio:
        data = arbol.escribir()
        obj = {**json.loads((arbol.raiz / "piloto.json").read_text(encoding="utf-8")), **cambio}
        nuevo = json.dumps(obj).encode("utf-8")
        (arbol.raiz / "piloto.json").write_bytes(nuevo)
        data["abiertos"]["piloto"]["valor"]["sha256"] = _sha(nuevo)
        assert texto in "\n".join(check_closed(data, arbol.raiz).problemas)
        return
    assert texto in _problemas(arbol)


def test_concurrencia_con_fuente_oficial_cambia_el_presupuesto(arbol: Arbol) -> None:
    arbol.piloto.update(
        {
            "concurrencia": 2,
            "fuente_concurrencia": {"tipo": "pagina_oficial", "referencia": "pagina inventada"},
        }
    )
    assert "bytes canonicos para max_time_minutes = 9" in _problemas(arbol)  # floor(2 * 634 / 120 - 0,9)
    arbol.b = 9
    # 14 + 30 * (9 + 1,8) = 338 min: una parte
    assert check_closed(arbol.escribir(), arbol.raiz).problemas == []


def test_presupuesto_que_no_es_el_de_la_formula(arbol: Arbol) -> None:
    for b in (3, 5):
        arbol.b = b
        assert "bytes canonicos para max_time_minutes = 4" in _problemas(arbol)


def test_carga_y_montaje_salen_de_los_registros(arbol: Arbol) -> None:
    arbol.piloto["carga_modelo_segundos"] = 841  # m = 15: floor(633 / 120 - 0,9) = 4, igual
    assert check_closed(arbol.escribir(), arbol.raiz).problemas == []
    arbol.segundos = [80, 88]  # s = 1,4: floor(5,275 - 1,4) = 3
    assert "max_time_minutes = 3" in _problemas(arbol)
    arbol.segundos = [200, 210]  # s = 3,5: floor(1,775) = 1 < 2
    assert "presupuesto_bajo_minimo" in _problemas(arbol)


@pytest.mark.parametrize(("replicas", "texto"), [(2, "la escalera da 3"), (4, "la escalera da 3")])
def test_replicas_que_no_da_la_escalera(arbol: Arbol, replicas: int, texto: str) -> None:
    arbol.corrida["replicas"] = replicas
    assert texto in _problemas(arbol)


def test_partes_por_replica_segun_la_sesion(arbol: Arbol) -> None:
    arbol.corrida["partes"] = 2
    assert "la regla da 1" in _problemas(arbol)
    arbol.ensayo["sesion_max_horas"] = 6  # 362 min no caben en 360
    assert check_closed(arbol.escribir(), arbol.raiz).problemas == []
    arbol.corrida["partes"] = 1
    assert "la regla da 2" in _problemas(arbol)
    # la carga se redondea hacia arriba: 800 s son 14 min y 14 + 348 = 362 min no caben en 361,8;
    # con 13,33 min sin redondear (361,33) si cabrian
    arbol.ensayo["sesion_max_horas"] = 6.03
    assert "la regla da 2" in _problemas(arbol)


def test_compuerta_tardia_recalcula_la_escalera(arbol: Arbol) -> None:
    # desde el 20 de octubre quedan 2 sabados (24 y 31): 0,8 * 30 * 2 = 48 h; fastapi con 3 y 2 replicas y
    # campana no caben; fastapi con una corrida por condicion (4 * 60 + 57 + 120 = 417 -> 37,53 h) si
    arbol.corrida["fecha_compuerta"] = "2026-10-20"
    assert "la escalera da 2" in _problemas(arbol)
    arbol.corrida["replicas"] = 2
    assert "faltan las decisiones versionadas ['compuerta_tardia']" in _problemas(arbol)
    d = {
        "decision": "compuerta_tardia",
        "opcion": "seguir_solo_linea_base",
        "fecha": "2026-10-20",
        "referencia": "r",
    }
    arbol.decisiones = [d]
    assert check_closed(arbol.escribir(), arbol.raiz).problemas == []
    arbol.corrida["fecha_compuerta"] = "2026-10-19"  # el limite de la compuerta es inclusivo
    assert "no corresponde a ninguna condicion presente" in _problemas(arbol)
    arbol.corrida["fecha_compuerta"] = "2026-10-23"
    assert "posterior al limite de recibos" in _problemas(arbol)


def test_campana_que_no_cabe_exige_decision(arbol: Arbol) -> None:
    # 0,8 * (25 / 2) * 3 = 30 h: solo cabe fastapi sin campana (4 * 60 = 240 -> 21,6 h)
    arbol.cuota["gpu_semanal_horas"] = 25
    arbol.corrida["replicas"] = 2
    assert "faltan las decisiones versionadas ['campana_no_cabe']" in _problemas(arbol)
    arbol.decisiones = [
        {
            "decision": "campana_no_cabe",
            "opcion": "seguir_solo_linea_base",
            "fecha": "2026-10-11",
            "referencia": "r",
        }
    ]
    assert check_closed(arbol.escribir(), arbol.raiz).problemas == []
    arbol.decisiones[0]["opcion"] = "detener"
    assert "la compuerta no se abre" in _problemas(arbol)


def test_ni_la_linea_base_cabe_al_recalcular(arbol: Arbol) -> None:
    arbol.cuota["gpu_semanal_horas"] = 25
    arbol.corrida.update({"replicas": 2, "fecha_compuerta": "2026-10-19"})
    assert check_closed(arbol.escribir(), arbol.raiz).problemas != []  # falta la decision, pero cabe
    arbol.fijos["fecha_limite_compuerta"] = "2026-10-21"
    arbol.fijos["fecha_limite_recibos"] = "2026-11-02"
    arbol.corrida["fecha_compuerta"] = "2026-11-01"  # ya no queda ningun sabado antes del corte
    data = arbol.escribir()
    kp.FIJOS_SHA256 = fijos_digest(arbol.fijos)  # el fixture restaura el valor al terminar
    assert "ni la linea base sola" in "\n".join(check_closed(data, arbol.raiz).problemas)


# --- ronda 3: contrastes anadidos tras la verificacion independiente ---


def test_max_output_tokens_del_envio_es_el_que_fija_el_ensayo(arbol: Arbol) -> None:
    """Ensayo con rechazos a 16384 y ninguno a 8192: el envio tiene que llevar 8192, y solo ese cambio."""
    arbol.ensayo["rechazos_por_contexto"] = {"16384": 3, "8192": 0}
    assert "el ensayo fija max_output_tokens = 8192" in _problemas(arbol)  # el envio sigue con 16384
    arbol.sampling_envio = SAMPLING_KIT.replace(b"16384", b"8192")
    data = arbol.escribir()
    extra = {"tasks": arbol.raiz / "tasks.jsonl", "envio": arbol.raiz / "envio"}
    assert check_closed(data, arbol.raiz, **extra).problemas == []
    # el valor correcto, pero con otro cambio en el archivo de muestreo
    arbol.sampling_envio = SAMPLING_KIT.replace(b"16384", b"8192").replace(b"0.5", b"0.9")
    assert "no es el del kit con max_output_tokens = 8192" in _problemas(arbol)
    # declarado dos veces
    arbol.sampling_envio = SAMPLING_KIT.replace(b"16384", b"8192") + b"max_output_tokens: 8192\n"
    assert "no lo declara exactamente una vez" in _problemas(arbol)


def test_envio_con_8192_sin_que_el_ensayo_lo_pida(arbol: Arbol) -> None:
    arbol.sampling_envio = SAMPLING_KIT.replace(b"16384", b"8192")
    assert "no es el del kit con max_output_tokens = 16384" in _problemas(arbol)
    arbol.sampling_envio = SAMPLING_KIT
    data = arbol.escribir()
    (arbol.raiz / kp.MANIFEST_REL).unlink()
    problemas = check_closed(data, arbol.raiz, envio=arbol.raiz / "envio").problemas
    assert "no se pudo contrastar" in "\n".join(problemas)
    # sin --envio no se puede ver: queda como comprobacion pendiente, no como aprobada
    assert any("--envio" in p for p in check_closed(data, arbol.raiz).pendientes)


def test_eval_config_del_envio_distinto_del_citado(arbol: Arbol) -> None:
    """El archivo citado es canonico, pero el que esta dentro del envio no."""
    arbol.citar_fuera = True
    extra = {"tasks": arbol.raiz / "tasks.jsonl", "envio": arbol.raiz / "envio"}
    assert check_closed(arbol.escribir(), arbol.raiz, **extra).problemas == []
    arbol.eval_config_envio = CANONICO_4.replace(b"minutes: 4", b"minutes: 60")
    assert "el eval_config.yaml del envio no es el canonico" in _problemas(arbol)


@pytest.mark.parametrize(
    ("cambios", "texto"),
    [
        ({"ensayo": "2026-10-02"}, "el ensayo de notebook (2026-10-02) es anterior a la de el registro"),
        ({"validez": "2026-10-04"}, "la validez de tareas (2026-10-04) es anterior a la de el ensayo"),
        ({"cuota": "2026-10-07"}, "la lectura de la cuota (2026-10-07) es anterior a la de la validez"),
        ({"piloto": "2026-10-09"}, "el piloto (2026-10-09) es anterior a la de la lectura de la cuota"),
        ({"compuerta": "2026-10-13"}, "la compuerta (2026-10-13) es anterior a la de el piloto"),
        ({"piloto": "2026-11-06", "compuerta": "2026-11-06"}, "el piloto (2026-11-06) es posterior al corte"),
        (
            {"cuota": "2026-10-10", "piloto": "2026-10-10", "compuerta": "2026-10-11"},
            "anterior a la fecha minima",
        ),
    ],
)
def test_fechas_declaradas_fuera_de_orden(arbol: Arbol, cambios: dict[str, str], texto: str) -> None:
    arbol.fechar(**cambios)
    assert texto in _problemas(arbol)


def test_fechas_iguales_y_en_los_limites_se_aceptan(arbol: Arbol) -> None:
    arbol.fechar(ensayo="2026-10-03", validez="2026-10-03", cuota="2026-10-03", piloto="2026-10-03")
    arbol.fechar(compuerta="2026-10-12")  # todo el mismo dia del registro; compuerta en la fecha minima
    assert check_closed(arbol.escribir(), arbol.raiz).problemas == []
    arbol.fechar(ensayo="2026-10-12", validez="2026-10-12", cuota="2026-10-12", piloto="2026-10-12")
    assert check_closed(arbol.escribir(), arbol.raiz).problemas == []
    # el limite de recibos es inclusivo (con la decision de compuerta tardia); un dia despues, no
    arbol.fechar(compuerta="2026-10-22")
    arbol.corrida["replicas"] = 2  # quedan 2 sabados: 48 h
    arbol.decisiones = [
        {
            "decision": "compuerta_tardia",
            "opcion": "seguir_solo_linea_base",
            "fecha": "2026-10-22",
            "referencia": "r",
        }
    ]
    assert check_closed(arbol.escribir(), arbol.raiz).problemas == []
    arbol.fechar(compuerta="2026-10-23")
    assert "posterior al limite de recibos" in _problemas(arbol)


def test_segundo_piloto_se_acepta(arbol: Arbol) -> None:
    arbol.piloto["numero"] = 2
    assert check_closed(arbol.escribir(), arbol.raiz).problemas == []
    arbol.piloto.update({"numero": 1, "tareas": 8})
    assert check_closed(arbol.escribir(), arbol.raiz).problemas == []


def test_montaje_se_redondea_hacia_arriba_a_decimas(arbol: Arbol) -> None:
    """15 s son 0,25 min: redondeado a 0,3 da floor(5,283 - 0,3) = 4; sin redondear daria 5."""
    arbol.segundos = [15, 15]
    data = arbol.escribir()
    assert check_closed(data, arbol.raiz).problemas == []
    validez = json.loads((arbol.raiz / "validez.json").read_text(encoding="utf-8"))
    assert kp.setup_minutes(validez) == Fraction(3, 10)
    arbol.b = 5
    assert "max_time_minutes = 4" in _problemas(arbol)


def test_validez_con_un_identificador_que_no_esta_en_tasks(arbol: Arbol) -> None:
    def renombrar(v: dict[str, Any]) -> None:
        v["tareas"][70]["instance_id"] = "zz_inexistente"  # una tarea 'discrimina' de rich

    arbol.alterar_validez = renombrar
    data = arbol.escribir()
    sin_tasks = "\n".join(check_closed(data, arbol.raiz).problemas)
    assert "no son exactamente las tareas de clase 'discrimina'" in sin_tasks
    con_tasks = "\n".join(check_closed(data, arbol.raiz, tasks=arbol.raiz / "tasks.jsonl").problemas)
    assert "no son los de tasks.jsonl (sobran 1, faltan 1)" in con_tasks
    assert main([*arbol.completo(), "--sin-git"]) == 2


def test_parametros_sin_commitear_o_head_fuera_de_main(
    arbol: Arbol, capsys: pytest.CaptureFixture[str]
) -> None:
    arbol.escribir(git=True)
    assert main(arbol.completo()) == 0
    capsys.readouterr()
    # el propio archivo de parametros con un cambio local (un espacio al final)
    p = arbol.raiz / "parametros.json"
    original = p.read_bytes()
    p.write_bytes(original + b" ")
    assert main(arbol.completo()) == 2
    assert "parametros.json: tiene cambios sin commitear" in capsys.readouterr().err
    p.write_bytes(original)
    assert main(arbol.completo()) == 0
    # un commit nuevo que origin/main (referencia local) no contiene
    (arbol.raiz / "nuevo.txt").write_text("x", encoding="utf-8")
    _git(arbol.raiz, "add", "nuevo.txt")
    _git(arbol.raiz, "commit", "-q", "-m", "commit sin mergear")
    capsys.readouterr()
    assert main(arbol.completo()) == 2
    assert "HEAD no esta contenido en origin/main" in capsys.readouterr().err
    _git(arbol.raiz, "update-ref", "refs/remotes/origin/main", "HEAD")
    assert main(arbol.completo()) == 0


def test_parametros_fuera_de_la_raiz(arbol: Arbol, tmp_path_factory: pytest.TempPathFactory) -> None:
    arbol.escribir(git=True)
    fuera = tmp_path_factory.mktemp("fuera") / "parametros.json"
    fuera.write_bytes((arbol.raiz / "parametros.json").read_bytes())
    argv = ["comprobar", "--parametros", str(fuera), "--raiz", str(arbol.raiz)]
    assert (
        main([*argv, "--tasks", str(arbol.raiz / "tasks.jsonl"), "--envio", str(arbol.raiz / "envio")]) == 2
    )
    assert kp.relative_posix(arbol.raiz / "a" / "b.json", arbol.raiz) == "a/b.json"
    assert kp.relative_posix(fuera, arbol.raiz) is None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


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


def test_git_no_disponible_es_un_problema(tmp_path: Path) -> None:
    assert kp.git_problems(tmp_path / "no_existe", ["a.json"])[0].startswith("No se pudo ejecutar git")
    problemas = kp.git_problems(tmp_path, ["a.json"])
    assert len(problemas) == 2 and problemas[0].startswith("HEAD no esta contenido en origin/main")
    assert problemas[1] == "a.json: no esta versionado en git."


def test_cli_presupuesto(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["presupuesto", "--concurrencia", "1", "--carga-modelo", "15", "--montaje", "1", "4"]) == 0
    lineas = capsys.readouterr().out.splitlines()
    assert lineas[0].endswith("5.40")
    assert lineas[2].split() == ["1", "15.0", "1.0", "4"]
    assert "no se fija" in lineas[3]


def test_cli_computo(capsys: pytest.CaptureFixture[str]) -> None:
    validas = [f"{repo}={n}" for repo, n in CONTEOS.items()]
    cuota = ["--cuota", "30", "--dia-reinicio", "6", "--desde", "2026-10-12"]
    assert main(["computo", "--validas", *validas, *cuota]) == 0
    salida = capsys.readouterr().out
    assert "665   59.85   119.70" in salida
    assert "reinicios de cuota hasta el corte: 3; horas utilizables de L4x4: 36.00" in salida
    assert "escalon elegido: 6 (Textualize/rich, 2 replicas de A)" in salida
    assert main(["computo", "--validas", *validas, *cuota, "--factor", "4"]) == 0
    salida = capsys.readouterr().out
    assert "665   59.85   239.40" in salida and "utilizables de L4x4: 18.00" in salida
    assert "escalon elegido: 8 (Textualize/rich" in salida
    assert main(["computo", "--validas", "fastapi/fastapi=39", *cuota]) == 0
    salida = capsys.readouterr().out
    assert "no apto" in salida and "ningun escalon cabe" in salida
    assert main(["computo", "--validas", "sin_numero"]) == 2
    assert main(["computo", "--validas", *validas, "--cuota", "30"]) == 2
    assert main(["computo", "--validas", *validas, *cuota[:-1], "ayer"]) == 2
