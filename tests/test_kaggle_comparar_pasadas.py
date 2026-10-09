"""Pruebas de scripts/kaggle_comparar_pasadas.py (#179). Datos inventados: ningún identificador real."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts import kaggle_comparar_pasadas as kc
from scripts.kaggle_replicas import mcnemar_exact_p

T0 = 1_760_000_000.0
ENGANCHES = {
    "peticiones": "instalado",
    "latido": "cada 30.0 s",
    "mapa de hilos del núcleo": "instalado",
}


def _e(tipo: str, tarea: str | None, hora: float, **campos: Any) -> dict[str, Any]:
    return {"evento": tipo, "tarea": tarea, "hora": hora, "hora_utc": f"h{hora}", **campos}


def _bien(nombre: str, hora: float, numero: int) -> list[dict[str, Any]]:
    return [
        _e("tarea_inicio", nombre, hora),
        _e("peticion_inicio", nombre, hora + 1, peticion=numero, caracteres_entrada=10),
        _e("peticion_fin", nombre, hora + 2, peticion=numero, motivo="stop"),
        _e("diff_cierre", nombre, hora + 3, bytes=5, sha256="x", archivos=[]),
        _e("agente_fin", nombre, hora + 4, error=None, entrego=True),
        _e("tarea_fin", nombre, hora + 5, clase="resuelta", resuelta=True, con_tope=True),
    ]


def _colgada(nombre: str, hora: float) -> list[dict[str, Any]]:
    return [
        _e("tarea_inicio", nombre, hora),
        _e("tarea_colgada", nombre, hora + 9, tope_s=9, segundos=9.0, hilo_vivo=False, sigue=True),
        _e("tarea_fin", nombre, hora + 10, clase="tarea_colgada", con_tope=True, par_faltante=True),
    ]


def _salida(
    carpeta: Path,
    tareas: dict[str, str],
    *,
    completo: bool = True,
    cierre: bool = True,
    prefijo: str = "",
) -> Path:
    """Una carpeta de salida con su JSON y su registro. ``tareas``: id -> «r», «n» o «c» (colgada)."""
    carpeta.mkdir(parents=True)
    eventos: list[dict[str, Any]] = [
        _e("registro_instalado", None, T0, enganches=ENGANCHES, versiones={"ipykernel": "x"})
    ]
    filas = []
    for numero, (nombre, que) in enumerate(tareas.items(), start=1):
        hora = T0 + 20 * numero
        if que == "c":
            eventos += _colgada(nombre, hora)
            filas.append(
                {"instance_id": nombre, "resuelta": False, "clase": "tarea_colgada", "par_faltante": True}
            )
        else:
            eventos += _bien(nombre, hora, numero)
            filas.append(
                {"instance_id": nombre, "resuelta": que == "r", "clase": "resuelta" if que == "r" else "no"}
            )
    if cierre:
        eventos.append(
            _e("cierre", None, T0 + 20 * (len(tareas) + 2), errores_del_registro=0, ultimo_error=None)
        )
    (carpeta / f"{prefijo}registro_p.jsonl").write_text(
        "\n".join(json.dumps(e) for e in eventos), encoding="utf-8"
    )
    pasada = {
        "completo": completo,
        "cortado_por": None,
        "corridas": {"X1": {"condicion": "A", "cuenta_para_resueltas": True, "tareas": filas}},
    }
    (carpeta / f"{prefijo}iteracion_p.json").write_text(json.dumps(pasada), encoding="utf-8")
    return carpeta


def _comparar(
    capsys: pytest.CaptureFixture[str], base: list[Path], otra: list[Path], *extra: str
) -> tuple[int, dict[str, Any], str]:
    argv = [x for p in base for x in ("--base", str(p))] + [x for p in otra for x in ("--otra", str(p))]
    codigo = kc.main([*argv, *extra])
    fuera = capsys.readouterr()
    return codigo, (json.loads(fuera.out) if fuera.out.strip() else {}), fuera.err


TAREAS = ["a_1", "a_2", "a_3", "a_4", "a_5", "a_6"]


def test_dos_pasadas_completas_cuentan_concordantes_discordantes_y_mcnemar(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # a_1 R/R, a_2 N/N, a_3 R/N, a_4 R/N, a_5 N/R, a_6 R/R
    p1 = _salida(tmp_path / "p1", dict(zip(TAREAS, "rnrrnr", strict=True)))
    p2 = _salida(tmp_path / "p2", dict(zip(TAREAS, "rnnnrr", strict=True)))
    codigo, r, _ = _comparar(capsys, [p1], [p2])
    assert codigo == 0 and r["completa"] is True
    assert r["pares"]["excluidos"] == 0 and r["pares"]["que_quedan"] == 6
    assert r["tabla"]["concordantes"] == {"ambas_resueltas": 2, "ninguna_resuelta": 1}
    assert r["tabla"]["discordantes"]["solo_base"] == 2 and r["tabla"]["discordantes"]["solo_otra"] == 1
    assert r["tabla"]["mcnemar_p_exacto"] == round(mcnemar_exact_p(2, 1), 6)


def test_la_tarea_colgada_en_cualquiera_de_las_dos_se_excluye_y_la_orden_no_sale_con_0(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p1 = _salida(tmp_path / "p1", dict(zip(TAREAS, "rrrnnn", strict=True)))
    # La colgada de la pasada 2 es a_2, y la pasada 1 trae la suya como resuelta: se excluye igual.
    p2 = _salida(tmp_path / "p2", dict(zip(TAREAS, "rcrrnn", strict=True)))
    codigo, r, err = _comparar(capsys, [p1], [p2])
    assert codigo == kc.EXIT_COLGADAS == 3 and r["completa"] is False
    assert r["pares"]["excluidos"] == 1 and r["pares"]["tareas_excluidas"] == ["a_2"]
    assert r["pares"]["que_quedan"] == 5 and "a_2" not in r["pares"]["tareas_que_quedan"]
    assert r["tabla"]["discordantes"] == {
        "solo_base": 0,
        "solo_otra": 1,
        "tareas_solo_base": [],
        "tareas_solo_otra": ["a_4"],
    }
    assert "no cuenta como completa" in err and "COMPARACIÓN NO COMPLETA" in err


def test_una_colgada_en_el_otro_sentido_tambien_se_excluye(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p1 = _salida(tmp_path / "p1", dict(zip(TAREAS, "rcrnnn", strict=True)))
    p2 = _salida(tmp_path / "p2", dict(zip(TAREAS, "rrrnnn", strict=True)))
    codigo, r, _ = _comparar(capsys, [p1], [p2])
    assert codigo == 3 and r["pares"]["tareas_excluidas"] == ["a_2"]
    assert r["lados"]["base"]["tareas_colgadas"] == ["a_2"] and r["lados"]["otra"]["tareas_colgadas"] == []


def test_las_discordantes_se_cuentan_por_sentido(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    p1 = _salida(tmp_path / "p1", dict(zip(TAREAS, "rrrnnn", strict=True)))
    p2 = _salida(tmp_path / "p2", dict(zip(TAREAS, "nnnrrn", strict=True)))
    _, r, _ = _comparar(capsys, [p1], [p2])
    d = r["tabla"]["discordantes"]
    assert (d["solo_base"], d["solo_otra"]) == (3, 2)
    assert d["tareas_solo_base"] == ["a_1", "a_2", "a_3"] and d["tareas_solo_otra"] == ["a_4", "a_5"]
    assert r["tabla"]["mcnemar_p_exacto"] == round(mcnemar_exact_p(3, 2), 6)


def test_un_lado_en_porciones_se_une_y_se_compara_con_la_pasada_entera(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base = _salida(tmp_path / "base", dict(zip(TAREAS, "rrrnnn", strict=True)))
    parte1 = _salida(tmp_path / "otra1", dict(zip(TAREAS[:3], "rnn", strict=True)))
    parte2 = _salida(tmp_path / "otra2", dict(zip(TAREAS[3:], "rrn", strict=True)))
    codigo, r, _ = _comparar(capsys, [base], [parte1, parte2])
    assert codigo == 0 and r["lados"]["otra"]["tareas"] == 6 and len(r["lados"]["otra"]["salidas"]) == 2
    assert r["pares"]["que_quedan"] == 6
    assert r["tabla"]["discordantes"]["solo_base"] == 2 and r["tabla"]["discordantes"]["solo_otra"] == 2


def test_una_colgada_en_una_porcion_se_excluye_y_se_dice(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base = _salida(tmp_path / "base", dict(zip(TAREAS, "rrrnnn", strict=True)))
    parte1 = _salida(tmp_path / "otra1", dict(zip(TAREAS[:3], "rrr", strict=True)))
    parte2 = _salida(tmp_path / "otra2", dict(zip(TAREAS[3:], "ncn", strict=True)))
    codigo, r, _ = _comparar(capsys, [base], [parte1, parte2])
    assert codigo == 3 and r["pares"]["tareas_excluidas"] == ["a_5"]


def test_una_tarea_en_dos_porciones_del_mismo_lado_es_una_entrada_invalida(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base = _salida(tmp_path / "base", dict(zip(TAREAS, "rrrnnn", strict=True)))
    parte1 = _salida(tmp_path / "otra1", dict(zip(TAREAS[:4], "rrrn", strict=True)))
    parte2 = _salida(tmp_path / "otra2", dict(zip(TAREAS[3:], "nnn", strict=True)))
    codigo, _, err = _comparar(capsys, [base], [parte1, parte2])
    assert codigo == kc.EXIT_ENTRADA and "más de una salida" in err


def test_los_huecos_de_cobertura_hacen_la_comparacion_incompleta(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p1 = _salida(tmp_path / "p1", dict(zip(TAREAS, "rrrnnn", strict=True)))
    p2 = _salida(tmp_path / "p2", dict(zip(TAREAS[:4], "rrrn", strict=True)))
    codigo, r, _ = _comparar(capsys, [p1], [p2])
    assert codigo == kc.EXIT_INCOMPLETA == 4
    assert r["huecos_de_cobertura"] == {"otra_sin": ["a_5", "a_6"]} and r["pares"]["que_quedan"] == 4


def test_con_lista_cada_lado_debe_cubrirla_exactamente(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p1 = _salida(tmp_path / "p1", dict(zip(TAREAS, "rrrnnn", strict=True)))
    p2 = _salida(tmp_path / "p2", dict(zip(TAREAS, "rrrnnn", strict=True)))
    lista = tmp_path / "lista.json"
    lista.write_text(json.dumps({"lista": [*TAREAS[:5], "otra_9"]}), encoding="utf-8")
    codigo, r, _ = _comparar(capsys, [p1], [p2], "--lista", str(lista))
    assert codigo == 4
    assert r["huecos_de_cobertura"]["base_sin"] == ["otra_9"] and r["huecos_de_cobertura"]["base_de_mas"] == [
        "a_6"
    ]
    lista.write_text(json.dumps({"lista": TAREAS}), encoding="utf-8")
    assert _comparar(capsys, [p1], [p2], "--lista", str(lista))[0] == 0


def test_una_lista_rota_o_con_repetidos_es_entrada_invalida(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p1 = _salida(tmp_path / "p1", dict(zip(TAREAS, "rrrnnn", strict=True)))
    for texto in ("no json", json.dumps({"lista": ["a", "a"]}), json.dumps({"x": 1})):
        lista = tmp_path / "lista.json"
        lista.write_text(texto, encoding="utf-8")
        assert _comparar(capsys, [p1], [p1], "--lista", str(lista))[0] == kc.EXIT_ENTRADA


def test_una_sesion_sin_cierre_no_es_completa_aunque_el_json_lo_diga(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p1 = _salida(tmp_path / "p1", dict(zip(TAREAS, "rrrnnn", strict=True)))
    p2 = _salida(tmp_path / "p2", dict(zip(TAREAS, "rrrnnn", strict=True)), cierre=False)
    codigo, r, _ = _comparar(capsys, [p1], [p2])
    assert codigo == 4 and any("registro dice" in m for m in r["motivos"])


def test_un_json_que_no_dice_completo_no_es_una_pasada_completa(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p1 = _salida(tmp_path / "p1", dict(zip(TAREAS, "rrrnnn", strict=True)), completo=False)
    p2 = _salida(tmp_path / "p2", dict(zip(TAREAS, "rrrnnn", strict=True)))
    codigo, r, _ = _comparar(capsys, [p1], [p2])
    assert codigo == 4 and any("completo: true" in m for m in r["motivos"])


def test_la_marca_solo_en_el_json_o_solo_en_el_registro_se_excluye_y_se_denuncia(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p1 = _salida(tmp_path / "p1", dict(zip(TAREAS, "rrrnnn", strict=True)))
    p2 = _salida(tmp_path / "p2", dict(zip(TAREAS, "rrrnnn", strict=True)))
    archivo = next(p2.glob("iteracion_*.json"))
    datos = json.loads(archivo.read_text(encoding="utf-8"))
    datos["corridas"]["X1"]["tareas"][0]["par_faltante"] = True
    archivo.write_text(json.dumps(datos), encoding="utf-8")
    codigo, r, _ = _comparar(capsys, [p1], [p2])
    assert r["pares"]["tareas_excluidas"] == ["a_1"]
    assert codigo == 4 and any("no coinciden en las tareas colgadas" in m for m in r["motivos"])


def test_acepta_la_carpeta_del_rescate_con_prefijo_salida_y_el_json_directo(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p1 = _salida(tmp_path / "p1", dict(zip(TAREAS, "rrrnnn", strict=True)), prefijo="salida__")
    p2 = _salida(tmp_path / "p2", dict(zip(TAREAS, "rrrnnn", strict=True)))
    codigo, r, _ = _comparar(capsys, [p1], [next(p2.glob("iteracion_*.json"))])
    assert codigo == 0 and r["tabla"]["mcnemar_p_exacto"] == 1.0


@pytest.mark.parametrize(
    "que", ["sin_json", "dos_json", "sin_registro", "json_roto", "sin_corridas", "repetida"]
)
def test_una_entrada_ilegible_sale_con_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], que: str
) -> None:
    p1 = _salida(tmp_path / "p1", dict(zip(TAREAS, "rrrnnn", strict=True)))
    p2 = _salida(tmp_path / "p2", dict(zip(TAREAS, "rrrnnn", strict=True)))
    archivo = next(p2.glob("iteracion_*.json"))
    if que == "sin_json":
        archivo.unlink()
    elif que == "dos_json":
        (p2 / "iteracion_otra.json").write_text("{}", encoding="utf-8")
    elif que == "sin_registro":
        next(p2.glob("registro_*.jsonl")).unlink()
    elif que == "json_roto":
        archivo.write_text("{", encoding="utf-8")
    elif que == "sin_corridas":
        archivo.write_text(json.dumps({"completo": True}), encoding="utf-8")
    else:
        datos = json.loads(archivo.read_text(encoding="utf-8"))
        datos["corridas"]["X1"]["tareas"].append(dict(datos["corridas"]["X1"]["tareas"][0]))
        archivo.write_text(json.dumps(datos), encoding="utf-8")
    codigo, _, err = _comparar(capsys, [p1], [p2])
    assert codigo == kc.EXIT_ENTRADA and "ENTRADA INVÁLIDA" in err


def test_una_carpeta_que_no_existe_sale_con_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    p1 = _salida(tmp_path / "p1", dict(zip(TAREAS, "rrrnnn", strict=True)))
    assert _comparar(capsys, [p1], [tmp_path / "no_existe"])[0] == kc.EXIT_ENTRADA


def test_solo_cuentan_las_corridas_que_cuentan_para_las_resueltas(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p1 = _salida(tmp_path / "p1", dict(zip(TAREAS, "rrrnnn", strict=True)))
    p2 = _salida(tmp_path / "p2", dict(zip(TAREAS, "rrrnnn", strict=True)))
    archivo = next(p2.glob("iteracion_*.json"))
    datos = json.loads(archivo.read_text(encoding="utf-8"))
    datos["corridas"]["CTRL"] = {
        "cuenta_para_resueltas": False,
        "tareas": [{"instance_id": "a_1", "resuelta": True}, {"instance_id": "control_9", "resuelta": True}],
    }
    archivo.write_text(json.dumps(datos), encoding="utf-8")
    codigo, r, _ = _comparar(capsys, [p1], [p2])
    assert codigo == 0 and r["lados"]["otra"]["tareas"] == 6


def test_sin_pares_que_comparar_no_hay_mcnemar(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    p1 = _salida(tmp_path / "p1", {"a_1": "c"})
    p2 = _salida(tmp_path / "p2", {"a_1": "r"})
    codigo, r, _ = _comparar(capsys, [p1], [p2])
    assert codigo == 3 and r["pares"]["que_quedan"] == 0 and r["tabla"]["mcnemar_p_exacto"] is None
