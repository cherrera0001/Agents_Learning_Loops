"""Pruebas de la segunda corrección del seguimiento #179: vigía (puntos 7 a 9) y ``--tareas-esperadas`` (10).

Respuestas fijas: sin red, sin token real y sin identificadores de tareas de la competencia.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from scripts import kaggle_registro as kr
from scripts import kaggle_rescate
from scripts import kaggle_vigia as kv

AHORA = datetime(2026, 10, 9, 14, 0, tzinfo=UTC)
T_RESCATE = datetime(2026, 10, 9, 10, 0, tzinfo=UTC)  # la marca de un rescate guardado
Envios = dict[int, tuple[str, float | None]]


def _lectura_del_vigia(carpeta: Path, momento: datetime, envios: Envios) -> None:
    datos = {
        "leido_utc": momento.strftime(kv.FORMATO_HORA),
        "envios": {str(r): list(v) for r, v in envios.items()},
    }
    (carpeta / kv.ARCHIVO_DE_LECTURA).write_text(json.dumps(datos), encoding="utf-8")


def _cambios(carpeta: Path) -> list[dict[str, Any]]:
    archivo = carpeta / kv.ARCHIVO_DE_CAMBIOS
    if not archivo.is_file():
        return []
    return [json.loads(x) for x in archivo.read_text(encoding="utf-8").splitlines()]


# ---------------------------------------------------------------------------
# Punto 7: el cambio que el rescate vio antes que el vigía también queda anotado
# ---------------------------------------------------------------------------


def test_el_cambio_que_vio_el_rescate_antes_que_el_vigia_se_anota_con_las_dos_lecturas(
    tmp_path: Path,
) -> None:
    _lectura_del_vigia(tmp_path, T_RESCATE - timedelta(hours=4), {1: ("pending", None)})
    # El rescate (más reciente que la lectura del vigía) ya vio el envío en error; ahora sigue en error.
    lineas = kv.registrar_lectura(tmp_path, T_RESCATE, {1: ("error", None)}, {1: ("error", None)}, AHORA)
    (cambio,) = _cambios(tmp_path)
    assert (cambio["antes"]["estado"], cambio["ahora"]["estado"]) == ("pending", "error")
    assert cambio["lectura_anterior_de"] == "vigia"
    assert cambio["lectura_anterior_utc"] == "2026-10-09T06:00:00Z"
    assert cambio["lectura_utc"] == "2026-10-09T10:00:00Z"  # la hora del rescate que lo vio
    assert lineas and "1 cambios" in lineas[0] and "2026-10-09T06:00:00Z (vigia)" in lineas[0]
    # La lectura del vigía queda en la de ahora: el mismo cambio no se anota otra vez.
    assert kv.registrar_lectura(tmp_path, T_RESCATE, {1: ("error", None)}, {1: ("error", None)}, AHORA) == []
    assert len(_cambios(tmp_path)) == 1


def test_si_hay_cambio_antes_y_despues_del_rescate_se_anotan_los_dos_tramos(tmp_path: Path) -> None:
    _lectura_del_vigia(tmp_path, T_RESCATE - timedelta(hours=4), {1: ("pending", None)})
    kv.registrar_lectura(tmp_path, T_RESCATE, {1: ("error", None)}, {1: ("complete", 0.13)}, AHORA)
    primero, segundo = _cambios(tmp_path)
    assert (primero["antes"]["estado"], primero["ahora"]["estado"], primero["lectura_anterior_de"]) == (
        "pending",
        "error",
        "vigia",
    )
    assert (segundo["antes"]["estado"], segundo["ahora"]["estado"], segundo["lectura_anterior_de"]) == (
        "error",
        "complete",
        "rescate",
    )


def test_con_el_rescate_mas_viejo_que_la_lectura_del_vigia_la_base_es_la_del_vigia(tmp_path: Path) -> None:
    """La rama ``marca < previa[0]``: un rescate anterior a la última lectura del vigía no se usa de base."""
    _lectura_del_vigia(tmp_path, T_RESCATE + timedelta(hours=2), {1: ("error", None)})
    kv.registrar_lectura(tmp_path, T_RESCATE, {1: ("pending", None)}, {1: ("complete", 0.13)}, AHORA)
    (cambio,) = _cambios(tmp_path)
    assert (cambio["antes"]["estado"], cambio["ahora"]["estado"]) == ("error", "complete")
    assert cambio["lectura_anterior_de"] == "vigia"
    assert cambio["lectura_anterior_utc"] == "2026-10-09T12:00:00Z"


def test_una_lectura_del_vigia_del_futuro_no_se_usa_y_el_rescate_es_la_base(tmp_path: Path) -> None:
    _lectura_del_vigia(tmp_path, AHORA + timedelta(days=1), {1: ("error", None)})
    kv.registrar_lectura(tmp_path, T_RESCATE, {1: ("pending", None)}, {1: ("complete", 0.13)}, AHORA)
    (cambio,) = _cambios(tmp_path)
    assert (cambio["antes"]["estado"], cambio["lectura_anterior_de"]) == ("pending", "rescate")


# ---------------------------------------------------------------------------
# Punto 8: la última lectura se escribe de forma atómica y un fallo no duplica el cambio
# ---------------------------------------------------------------------------


def test_la_ultima_lectura_se_guarda_con_reemplazo_y_no_deja_temporal(tmp_path: Path) -> None:
    kv.registrar_lectura(tmp_path, T_RESCATE, {}, {1: ("pending", None)}, AHORA)
    assert not list(tmp_path.glob("*.tmp"))
    leida = kv.leer_lectura_del_vigia(tmp_path)
    assert leida == (AHORA, {1: ("pending", None)})


def test_si_no_puede_guardar_la_lectura_no_anota_nada_y_el_siguiente_arranque_lo_anota_una_vez(
    tmp_path: Path,
) -> None:
    (tmp_path / (kv.ARCHIVO_DE_LECTURA + ".tmp")).mkdir()  # el temporal no se puede escribir
    lineas = kv.registrar_lectura(tmp_path, T_RESCATE, {1: ("error", None)}, {1: ("complete", 0.13)}, AHORA)
    assert any("no pude guardar la lectura del vigía" in x for x in lineas)
    assert _cambios(tmp_path) == []
    (tmp_path / (kv.ARCHIVO_DE_LECTURA + ".tmp")).rmdir()
    kv.registrar_lectura(tmp_path, T_RESCATE, {1: ("error", None)}, {1: ("complete", 0.13)}, AHORA)
    kv.registrar_lectura(tmp_path, T_RESCATE, {1: ("error", None)}, {1: ("complete", 0.13)}, AHORA)
    assert len(_cambios(tmp_path)) == 1


def test_si_falla_la_anotacion_la_lectura_ya_esta_guardada_y_no_se_duplica(tmp_path: Path) -> None:
    (tmp_path / kv.ARCHIVO_DE_CAMBIOS).mkdir()  # abrir para anexar falla
    lineas = kv.registrar_lectura(tmp_path, T_RESCATE, {1: ("error", None)}, {1: ("complete", 0.13)}, AHORA)
    (mensaje,) = lineas
    # Dice la verdad: la lectura sí se guardó; nombra el cambio (envío, estados, las dos horas) y que no se
    # reintentará.
    assert "sí se guardó" in mensaje and "no quedaron anotados" in mensaje and "no se reintentarán" in mensaje
    assert "envío 1: error -> complete entre 2026-10-09T10:00:00Z y 2026-10-09T14:00:00Z" in mensaje
    assert "no pude guardar la lectura" not in mensaje
    assert kv.leer_lectura_del_vigia(tmp_path) == (AHORA, {1: ("complete", 0.13)})
    # El siguiente arranque ve la misma lectura: no hay cambio nuevo y no se reintenta la anotación.
    assert (
        kv.registrar_lectura(tmp_path, T_RESCATE, {1: ("error", None)}, {1: ("complete", 0.13)}, AHORA) == []
    )


# ---------------------------------------------------------------------------
# Punto 9: `estados` que no es una lista
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("malo", ["medido", {"medido": 1}, 3, None])
def test_estados_que_no_es_una_lista_se_rechaza(malo: Any) -> None:
    problemas = kv.validar_hallazgos({"version": 1, "hallazgos": [], "estados": malo})
    assert problemas == ["`estados` debe ser una lista"]


def test_estados_con_uno_desconocido_se_rechaza_y_con_un_subconjunto_se_acepta() -> None:
    base: dict[str, Any] = {"version": 1, "hallazgos": []}
    assert kv.validar_hallazgos({**base, "estados": ["medido"]}) == []
    (problema,) = kv.validar_hallazgos({**base, "estados": ["medido", "inventado"]})
    assert "inventado" in problema


# ---------------------------------------------------------------------------
# Punto 10: --tareas-esperadas con más tareas de las esperadas y en `comprobar`
# ---------------------------------------------------------------------------

ENGANCHES = {"peticiones": "instalado", "latido": "cada 30.0 s"}
T0 = 1_760_000_000.0


def _e(tipo: str, tarea: str | None, hora: float, **campos: Any) -> dict[str, Any]:
    return {"evento": tipo, "tarea": tarea, "hora": hora, "hora_utc": f"h{hora}", **campos}


def _tarea(nombre: str, hora: float, numero: int) -> list[dict[str, Any]]:
    return [
        _e("tarea_inicio", nombre, hora),
        _e("peticion_inicio", nombre, hora + 1, peticion=numero, caracteres_entrada=10),
        _e("peticion_fin", nombre, hora + 2, peticion=numero, motivo="stop"),
        _e("diff_cierre", nombre, hora + 3, bytes=5, sha256="x", archivos=[]),
        _e("agente_fin", nombre, hora + 4, error=None, entrego=True),
        _e("tarea_fin", nombre, hora + 5, clase="resuelta", resuelta=True, con_tope=True),
    ]


def _registro_de(tareas: int) -> list[dict[str, Any]]:
    cuerpo = [e for n in range(tareas) for e in _tarea(f"t_{n}", T0 + 10 * (n + 1), n + 1)]
    cierre = _e("cierre", None, T0 + 10 * (tareas + 2), errores_del_registro=0, ultimo_error=None)
    return [_e("registro_instalado", None, T0, enganches=ENGANCHES), *cuerpo, cierre]


def test_un_registro_con_mas_tareas_de_las_esperadas_sale_con_4() -> None:
    informe = kr.diagnosticar(_registro_de(5), [], tareas_esperadas=3)
    assert kr.codigo_de(informe) == kr.EXIT_REGISTRO
    assert any(
        "5 tareas empezadas y se esperaban 3" in p for p in informe["sesion"]["problemas_del_registro"]
    )
    assert kr.codigo_de(kr.diagnosticar(_registro_de(5), [], tareas_esperadas=5)) == kr.EXIT_OK


@pytest.fixture
def rescate_falso(monkeypatch: pytest.MonkeyPatch) -> None:
    def principal(argv: list[str]) -> int:
        print(json.dumps({"descarga_incompleta": []}))
        return 0

    monkeypatch.setattr(kaggle_rescate, "main", principal)


def test_comprobar_pasa_tareas_esperadas_a_cada_pasada_nombrada(
    tmp_path: Path, rescate_falso: None, capsys: pytest.CaptureFixture[str]
) -> None:
    carpeta = tmp_path / "notebooks" / "pasada-a"
    carpeta.mkdir(parents=True)
    (carpeta / "salida__registro_p.jsonl").write_text(
        "\n".join(json.dumps(e) for e in _registro_de(3)), encoding="utf-8"
    )
    base = ["comprobar", "--rescate", str(tmp_path), "--notebook", "pasada-a"]
    assert kr.main(base) == kr.EXIT_OK
    assert kr.main([*base, "--tareas-esperadas", "3"]) == kr.EXIT_OK
    capsys.readouterr()
    assert kr.main([*base, "--tareas-esperadas", "2"]) == kr.EXIT_REGISTRO  # trae más de las esperadas
    assert kr.main([*base, "--tareas-esperadas", "4"]) == kr.EXIT_REGISTRO  # trae menos
    resumen = json.loads(capsys.readouterr().out.split("\n}\n")[-2] + "\n}")
    assert resumen["pasadas_esperadas"]["pasada-a"]["codigo"] == kr.EXIT_REGISTRO
    with pytest.raises(SystemExit) as salida:
        kr.main([*base, "--tareas-esperadas", "0"])
    assert salida.value.code == 2
