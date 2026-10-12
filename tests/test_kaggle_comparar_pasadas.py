"""Pruebas de scripts/kaggle_comparar_pasadas.py (#179). Datos inventados: ningún identificador real."""

from __future__ import annotations

import json
import shutil
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
TAREAS = ["a_1", "a_2", "a_3", "a_4", "a_5", "a_6"]


def _ids(n: int) -> list[str]:
    return [f"b_{i}" for i in range(1, n + 1)]


def _e(tipo: str, tarea: str | None, hora: float, **campos: Any) -> dict[str, Any]:
    return {"evento": tipo, "tarea": tarea, "hora": hora, "hora_utc": f"h{hora}", **campos}


def _bien(nombre: str, hora: float, numero: int, resuelta: bool = True) -> list[dict[str, Any]]:
    return [
        _e("tarea_inicio", nombre, hora),
        _e("peticion_inicio", nombre, hora + 1, peticion=numero, caracteres_entrada=10),
        _e("peticion_fin", nombre, hora + 2, peticion=numero, motivo="stop"),
        _e("diff_cierre", nombre, hora + 3, bytes=5, sha256="x", archivos=[]),
        _e("agente_fin", nombre, hora + 4, error=None, entrego=True),
        _e(
            "tarea_fin",
            nombre,
            hora + 5,
            clase="resuelta" if resuelta else "no",
            resuelta=resuelta,
            con_tope=True,
        ),
    ]


def _colgada(nombre: str, hora: float) -> list[dict[str, Any]]:
    return [
        _e("tarea_inicio", nombre, hora),
        _e("tarea_colgada", nombre, hora + 9, tope_s=9, segundos=9.0, hilo_vivo=False, sigue=True),
        _e(
            "tarea_fin",
            nombre,
            hora + 10,
            clase="tarea_colgada",
            resuelta=False,
            con_tope=True,
            par_faltante=True,
        ),
    ]


def _registro(tareas: dict[str, str], cierre: bool = True, marca: str = "") -> str:
    eventos: list[dict[str, Any]] = [_e("registro_instalado", None, T0, enganches=ENGANCHES, pasada=marca)]
    for numero, (nombre, que) in enumerate(tareas.items(), start=1):
        hora = T0 + 20 * numero
        eventos += _colgada(nombre, hora) if que == "c" else _bien(nombre, hora, numero, que == "r")
    if cierre:
        eventos.append(
            _e("cierre", None, T0 + 20 * (len(tareas) + 2), errores_del_registro=0, ultimo_error=None)
        )
    return "\n".join(json.dumps(e) for e in eventos)


def _salida(
    carpeta: Path,
    tareas: dict[str, str],
    *,
    completo: bool | None = True,
    cierre: bool = True,
    prefijo: str = "",
    nombre: str = "p",
    registro_de: dict[str, str] | None = None,
    corridas: dict[str, Any] | None = None,
    marcas: dict[str, Any] | None = None,
) -> Path:
    """Una carpeta con su JSON y su registro. ``tareas``: id -> «r», «n» o «c» (colgada).

    ``registro_de`` da otras tareas al registro (para probar que se ata a su JSON); ``marcas`` añade campos a
    cada fila del JSON; ``completo=None`` quita la clave.
    """
    carpeta.mkdir(parents=True, exist_ok=True)
    filas = []
    for ident, que in tareas.items():
        if que == "c":
            filas.append(
                {"instance_id": ident, "resuelta": False, "clase": "tarea_colgada", "par_faltante": True}
            )
        else:
            filas.append(
                {"instance_id": ident, "resuelta": que == "r", "clase": "resuelta" if que == "r" else "no"}
            )
    for fila in filas:
        fila.update(marcas or {})
    (carpeta / f"{prefijo}registro_iteracion_{nombre}.jsonl").write_text(
        _registro(registro_de if registro_de is not None else tareas, cierre, nombre), encoding="utf-8"
    )
    pasada: dict[str, Any] = {
        "cortado_por": None,
        "corridas": corridas or {"X1": {"condicion": "A", "cuenta_para_resueltas": True, "tareas": filas}},
    }
    if completo is not None:
        pasada["completo"] = completo
    (carpeta / f"{prefijo}iteracion_{nombre}.json").write_text(json.dumps(pasada), encoding="utf-8")
    return carpeta


def _lista(tmp_path: Path, ids: list[str]) -> Path:
    ruta = tmp_path / "lista.json"
    ruta.write_text(json.dumps({"lista": ids}), encoding="utf-8")
    return ruta


def _comparar(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    base: list[Path],
    otra: list[Path],
    lista: list[str] | None = TAREAS,
) -> tuple[int, dict[str, Any], str]:
    argv = [x for p in base for x in ("--base", str(p))] + [x for p in otra for x in ("--otra", str(p))]
    if lista is not None:
        argv += ["--lista", str(_lista(tmp_path, lista))]
    codigo = kc.main(argv)
    fuera = capsys.readouterr()
    return codigo, (json.loads(fuera.out) if fuera.out.strip() else {}), fuera.err


def _dos(tmp_path: Path, a: str, b: str, ids: list[str] = TAREAS, **kw: Any) -> tuple[Path, Path]:
    return (
        _salida(tmp_path / "p1", dict(zip(ids, a, strict=True)), nombre="p1"),
        _salida(tmp_path / "p2", dict(zip(ids, b, strict=True)), nombre="p2", **kw),
    )


# ---------------------------------------------------------------------------
# La cuenta
# ---------------------------------------------------------------------------


def test_dos_pasadas_completas_cuentan_concordantes_discordantes_y_mcnemar(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # a_1 R/R, a_2 N/N, a_3 R/N, a_4 R/N, a_5 N/R, a_6 R/R
    p1, p2 = _dos(tmp_path, "rnrrnr", "rnnnrr")
    codigo, r, _ = _comparar(capsys, tmp_path, [p1], [p2])
    assert codigo == 0 and r["completa"] is True
    assert r["pares"]["excluidos"] == 0 and r["pares"]["que_quedan"] == 6
    assert r["tabla"]["concordantes"] == {"ambas_resueltas": 2, "ninguna_resuelta": 1}
    assert r["tabla"]["discordantes"]["solo_base"] == 2 and r["tabla"]["discordantes"]["solo_otra"] == 1
    assert r["tabla"]["mcnemar_p_exacto"] == mcnemar_exact_p(2, 1) == 1.0


@pytest.mark.parametrize(
    ("a", "b", "base", "otra"), [("rrrrrrrr", "nnnnnnnr", 7, 0), ("nnnnnnnn", "rrrrrrrn", 0, 7)]
)
def test_mcnemar_da_el_valor_exacto_y_el_sentido(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], a: str, b: str, base: int, otra: int
) -> None:
    """Siete a un lado y un par concordante: p = 2 * P(X <= 0) con 7 discordantes = 0,015625."""
    ids = _ids(8)
    p1, p2 = _dos(tmp_path, a, b, ids)
    codigo, r, _ = _comparar(capsys, tmp_path, [p1], [p2], ids)
    d = r["tabla"]["discordantes"]
    assert codigo == 0 and (d["solo_base"], d["solo_otra"]) == (base, otra)
    assert r["tabla"]["mcnemar_p_exacto"] == pytest.approx(0.015625)


def test_mcnemar_con_siete_y_uno_no_da_uno_y_distingue_el_sentido(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ids = _ids(8)
    p1, p2 = _dos(tmp_path, "rrrrrrrn", "nnnnnnnr", ids)
    _, r, _ = _comparar(capsys, tmp_path, [p1], [p2], ids)
    d = r["tabla"]["discordantes"]
    assert (d["solo_base"], d["solo_otra"]) == (7, 1)
    assert d["tareas_solo_base"] == ids[:7] and d["tareas_solo_otra"] == [ids[7]]
    assert r["tabla"]["mcnemar_p_exacto"] == pytest.approx(0.0703125, abs=1e-9)


def test_el_p_no_se_redondea_a_cero(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    ids = _ids(30)
    p1, p2 = _dos(tmp_path, "r" * 30, "n" * 30, ids)
    _, r, _ = _comparar(capsys, tmp_path, [p1], [p2], ids)
    assert 0 < r["tabla"]["mcnemar_p_exacto"] < 1e-6


def test_las_discordantes_se_cuentan_por_sentido(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    p1, p2 = _dos(tmp_path, "rrrnnn", "nnnrrn")
    _, r, _ = _comparar(capsys, tmp_path, [p1], [p2])
    d = r["tabla"]["discordantes"]
    assert (d["solo_base"], d["solo_otra"]) == (3, 2)
    assert d["tareas_solo_base"] == ["a_1", "a_2", "a_3"] and d["tareas_solo_otra"] == ["a_4", "a_5"]
    assert r["tabla"]["mcnemar_p_exacto"] == mcnemar_exact_p(3, 2)


# ---------------------------------------------------------------------------
# Tareas colgadas y exclusión
# ---------------------------------------------------------------------------


def test_la_colgada_en_la_otra_pasada_se_excluye_y_la_orden_no_sale_con_0(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # La pasada 1 trae a_2 resuelta: se excluye igual por la colgada de la pasada 2.
    p1, p2 = _dos(tmp_path, "rrrnnn", "rcrrnn")
    codigo, r, err = _comparar(capsys, tmp_path, [p1], [p2])
    assert codigo == kc.EXIT_COLGADAS == 3 and r["completa"] is False
    assert r["pares"]["excluidos"] == 1 and r["pares"]["tareas_excluidas"] == ["a_2"]
    assert r["pares"]["que_quedan"] == 5 and "a_2" not in r["pares"]["tareas_que_quedan"]
    d = r["tabla"]["discordantes"]
    assert (d["solo_base"], d["solo_otra"], d["tareas_solo_otra"]) == (0, 1, ["a_4"])
    assert "no cuenta como completa" in err and "COMPARACIÓN NO COMPLETA" in err
    assert r["lados"]["otra"]["resueltas_con_las_excluidas"] == 3
    assert r["lados"]["base"]["resueltas_en_los_pares_que_quedan"] == 2


def test_la_colgada_de_la_base_tambien_se_excluye(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    p1, p2 = _dos(tmp_path, "rcrnnn", "rrrnnn")
    codigo, r, _ = _comparar(capsys, tmp_path, [p1], [p2])
    assert codigo == 3 and r["pares"]["tareas_excluidas"] == ["a_2"]
    assert r["lados"]["base"]["tareas_colgadas"] == ["a_2"] and r["lados"]["otra"]["tareas_colgadas"] == []


def test_la_exclusion_por_pares_faltantes_del_registro_sin_marca_en_el_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p1, p2 = _dos(tmp_path, "rrrnnn", "rrrnnn")
    (p2 / "registro_iteracion_p2.jsonl").write_text(_registro(dict(zip(TAREAS, "rcrnnn", strict=True))))
    codigo, r, _ = _comparar(capsys, tmp_path, [p1], [p2])
    assert r["pares"]["tareas_excluidas"] == ["a_2"] and codigo == 4  # no coinciden: se excluye y se denuncia
    assert any("no coinciden en las tareas colgadas" in m for m in r["motivos"])


def test_clase_tarea_colgada_sin_par_faltante_tambien_excluye(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p1, p2 = _dos(tmp_path, "rrrnnn", "rrrnnn")
    archivo = p2 / "iteracion_p2.json"
    datos = json.loads(archivo.read_text(encoding="utf-8"))
    datos["corridas"]["X1"]["tareas"][0]["clase"] = "tarea_colgada"
    archivo.write_text(json.dumps(datos), encoding="utf-8")
    _, r, _ = _comparar(capsys, tmp_path, [p1], [p2])
    assert r["pares"]["tareas_excluidas"] == ["a_1"]


def test_par_faltante_verdadero_sin_la_clase_tambien_excluye(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p1, p2 = _dos(tmp_path, "rrrnnn", "rrrnnn")
    archivo = p2 / "iteracion_p2.json"
    datos = json.loads(archivo.read_text(encoding="utf-8"))
    datos["corridas"]["X1"]["tareas"][1]["par_faltante"] = True  # su clase sigue siendo «resuelta»
    archivo.write_text(json.dumps(datos), encoding="utf-8")
    _, r, _ = _comparar(capsys, tmp_path, [p1], [p2])
    assert r["pares"]["tareas_excluidas"] == ["a_2"]


def test_varios_json_de_pasada_en_una_carpeta_son_entrada_invalida(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p1, p2 = _dos(tmp_path, "rrrnnn", "rrrnnn")
    (p2 / "iteracion_otra.json").write_text((p2 / "iteracion_p2.json").read_text(encoding="utf-8"))
    codigo, _, err = _comparar(capsys, tmp_path, [p1], [p2])
    assert codigo == kc.EXIT_ENTRADA and "un solo JSON" in err


def test_una_tarea_fuera_de_la_lista_no_forma_par_aunque_este_en_los_dos_lados(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ids = [*TAREAS, "extra_9"]
    p1 = _salida(tmp_path / "p1", dict(zip(ids, "rrrnnnr", strict=True)), nombre="p1")
    p2 = _salida(tmp_path / "p2", dict(zip(ids, "rrrnnnr", strict=True)), nombre="p2")
    codigo, r, _ = _comparar(capsys, tmp_path, [p1], [p2], lista=TAREAS)
    assert codigo == 4 and r["pares"]["que_quedan"] == 6 and "extra_9" not in r["pares"]["tareas_que_quedan"]


def test_un_par_faltante_que_no_es_booleano_es_entrada_invalida(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p1 = _salida(tmp_path / "p1", dict(zip(TAREAS, "rrrnnn", strict=True)), nombre="p1")
    for valor in ("true", 1, None):
        p2 = _salida(
            tmp_path / f"p2_{valor}",
            dict(zip(TAREAS, "rrrnnn", strict=True)),
            nombre="p2",
            marcas={"par_faltante": valor},
        )
        codigo, _, err = _comparar(capsys, tmp_path, [p1], [p2])
        assert codigo == kc.EXIT_ENTRADA and "booleano" in err


def test_completo_falso_con_una_colgada_sale_con_4(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p1 = _salida(tmp_path / "p1", dict(zip(TAREAS, "rrrnnn", strict=True)), nombre="p1")
    p2 = _salida(tmp_path / "p2", dict(zip(TAREAS, "rcrnnn", strict=True)), nombre="p2", completo=False)
    codigo, r, _ = _comparar(capsys, tmp_path, [p1], [p2])
    assert codigo == 4 and any("completo: true" in m for m in r["motivos"])


# ---------------------------------------------------------------------------
# Porciones
# ---------------------------------------------------------------------------


def test_un_lado_en_porciones_se_une_y_se_compara_con_la_pasada_entera(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base = _salida(tmp_path / "base", dict(zip(TAREAS, "rrrnnn", strict=True)), nombre="b")
    parte1 = _salida(tmp_path / "otra1", dict(zip(TAREAS[:3], "rnn", strict=True)), nombre="o1")
    parte2 = _salida(tmp_path / "otra2", dict(zip(TAREAS[3:], "rrn", strict=True)), nombre="o2")
    codigo, r, _ = _comparar(capsys, tmp_path, [base], [parte1, parte2])
    assert codigo == 0 and r["lados"]["otra"]["tareas"] == 6 and len(r["lados"]["otra"]["salidas"]) == 2
    assert r["pares"]["que_quedan"] == 6
    assert r["tabla"]["discordantes"]["solo_base"] == 2 and r["tabla"]["discordantes"]["solo_otra"] == 2


def test_una_colgada_en_una_porcion_se_excluye_y_se_dice(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base = _salida(tmp_path / "base", dict(zip(TAREAS, "rrrnnn", strict=True)), nombre="b")
    parte1 = _salida(tmp_path / "otra1", dict(zip(TAREAS[:3], "rrr", strict=True)), nombre="o1")
    parte2 = _salida(tmp_path / "otra2", dict(zip(TAREAS[3:], "ncn", strict=True)), nombre="o2")
    codigo, r, _ = _comparar(capsys, tmp_path, [base], [parte1, parte2])
    assert codigo == 3 and r["pares"]["tareas_excluidas"] == ["a_5"]


def test_una_tarea_en_dos_porciones_del_mismo_lado_es_una_entrada_invalida(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base = _salida(tmp_path / "base", dict(zip(TAREAS, "rrrnnn", strict=True)), nombre="b")
    parte1 = _salida(tmp_path / "otra1", dict(zip(TAREAS[:4], "rrrn", strict=True)), nombre="o1")
    parte2 = _salida(tmp_path / "otra2", dict(zip(TAREAS[3:], "nnn", strict=True)), nombre="o2")
    codigo, _, err = _comparar(capsys, tmp_path, [base], [parte1, parte2])
    assert codigo == kc.EXIT_ENTRADA and "más de una salida" in err


# ---------------------------------------------------------------------------
# Cobertura y lista (B5)
# ---------------------------------------------------------------------------


def test_sin_lista_no_sale_con_0_y_lo_dice(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    p1, p2 = _dos(tmp_path, "rrrnnn", "rrrnnn")
    codigo, r, err = _comparar(capsys, tmp_path, [p1], [p2], lista=None)
    assert codigo == 4 and r["completa"] is False and "--lista" in err
    assert r["tabla"]["mcnemar_p_exacto"] == 1.0  # la cuenta se escribe igual


def test_un_hueco_identico_en_los_dos_lados_solo_lo_ve_la_lista(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p1 = _salida(tmp_path / "p1", dict(zip(TAREAS[:4], "rrrn", strict=True)), nombre="p1")
    p2 = _salida(tmp_path / "p2", dict(zip(TAREAS[:4], "rrrn", strict=True)), nombre="p2")
    codigo, r, _ = _comparar(capsys, tmp_path, [p1], [p2], lista=TAREAS)
    assert codigo == 4
    assert r["huecos_de_cobertura"] == {"base_sin": ["a_5", "a_6"], "otra_sin": ["a_5", "a_6"]}


@pytest.mark.parametrize("lado", ["base", "otra"])
def test_los_huecos_por_cada_lado_sin_lista(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], lado: str
) -> None:
    entera = _salida(tmp_path / "e", dict(zip(TAREAS, "rrrnnn", strict=True)), nombre="e")
    corta = _salida(tmp_path / "c", dict(zip(TAREAS[:4], "rrrn", strict=True)), nombre="c")
    base, otra = (entera, corta) if lado == "base" else (corta, entera)
    codigo, r, _ = _comparar(capsys, tmp_path, [base], [otra], lista=None)
    sin = "otra_sin" if lado == "base" else "base_sin"
    assert codigo == 4 and r["huecos_de_cobertura"] == {sin: ["a_5", "a_6"]} and r["pares"]["que_quedan"] == 4


@pytest.mark.parametrize("lado", ["base", "otra"])
def test_los_huecos_y_los_sobrantes_por_cada_lado_con_lista(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], lado: str
) -> None:
    buena = _salida(tmp_path / "b", dict(zip(TAREAS, "rrrnnn", strict=True)), nombre="b")
    mala = _salida(
        tmp_path / "m", {**dict(zip(TAREAS[:5], "rrrnn", strict=True)), "extra_9": "r"}, nombre="m"
    )
    base, otra = (mala, buena) if lado == "base" else (buena, mala)
    codigo, r, _ = _comparar(capsys, tmp_path, [base], [otra], lista=TAREAS)
    assert codigo == 4
    assert r["huecos_de_cobertura"] == {f"{lado}_sin": ["a_6"], f"{lado}_de_mas": ["extra_9"]}


def test_una_lista_rota_o_con_repetidos_es_entrada_invalida(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p1 = _salida(tmp_path / "p1", dict(zip(TAREAS, "rrrnnn", strict=True)), nombre="p1")
    for texto in ("no json", json.dumps({"lista": ["a", "a"]}), json.dumps({"x": 1})):
        lista = tmp_path / "lista.json"
        lista.write_text(texto, encoding="utf-8")
        assert kc.main(["--base", str(p1), "--otra", str(p1), "--lista", str(lista)]) == kc.EXIT_ENTRADA
        capsys.readouterr()


# ---------------------------------------------------------------------------
# El registro atado a su JSON (B1, B2), la misma salida (B3) y cero pares (B4)
# ---------------------------------------------------------------------------


def test_un_registro_de_otras_tareas_no_sale_con_0(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p1 = _salida(tmp_path / "p1", dict(zip(TAREAS, "rrrnnn", strict=True)), nombre="p1")
    otras = dict(zip([f"z_{i}" for i in range(6)], "rrrnnn", strict=True))
    p2 = _salida(tmp_path / "p2", dict(zip(TAREAS, "rrrnnn", strict=True)), nombre="p2", registro_de=otras)
    codigo, r, _ = _comparar(capsys, tmp_path, [p1], [p2])
    assert codigo == 4 and any("difieren en 12 tareas" in m for m in r["motivos"])


def test_un_registro_con_menos_tareas_que_su_json_no_sale_con_0(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p1 = _salida(tmp_path / "p1", dict(zip(TAREAS, "rrrnnn", strict=True)), nombre="p1")
    p2 = _salida(
        tmp_path / "p2",
        dict(zip(TAREAS, "rrrnnn", strict=True)),
        nombre="p2",
        registro_de=dict(zip(TAREAS[:2], "rr", strict=True)),
    )
    assert _comparar(capsys, tmp_path, [p1], [p2])[0] == 4


def test_un_registro_con_una_tarea_empezada_dos_veces_no_sale_con_0(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p1, p2 = _dos(tmp_path, "rrrnnn", "rrrnnn")
    texto = (p2 / "registro_iteracion_p2.jsonl").read_text(encoding="utf-8")
    extra = "\n".join(json.dumps(e) for e in _bien("a_1", T0 + 500, 99))
    (p2 / "registro_iteracion_p2.jsonl").write_text(texto + "\n" + extra, encoding="utf-8")
    codigo, r, _ = _comparar(capsys, tmp_path, [p1], [p2])
    assert codigo == 4 and any("repetidas" in m for m in r["motivos"])


def test_el_registro_sale_del_nombre_del_json_en_una_carpeta_plana(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Dos pasadas en la misma carpeta: cada JSON toma su registro, no el primero de la carpeta (B2)."""
    plana = tmp_path / "plana"
    _salida(plana, dict(zip(TAREAS, "rrrnnn", strict=True)), nombre="p1")
    _salida(plana, dict(zip(TAREAS, "rrrnnn", strict=True)), nombre="p2", cierre=False)
    codigo, r, _ = _comparar(capsys, tmp_path, [plana / "iteracion_p1.json"], [plana / "iteracion_p2.json"])
    assert codigo == 4 and any("el registro dice" in m for m in r["motivos"])
    # Con las dos pasadas bien cerradas, la misma carpeta plana sale con 0.
    plana2 = tmp_path / "plana2"
    _salida(plana2, dict(zip(TAREAS, "rrrnnn", strict=True)), nombre="p1")
    _salida(plana2, dict(zip(TAREAS, "rrrnnn", strict=True)), nombre="p2")
    assert _comparar(capsys, tmp_path, [plana2 / "iteracion_p1.json"], [plana2 / "iteracion_p2.json"])[0] == 0


def test_la_colgada_solo_en_el_registro_de_la_segunda_de_una_carpeta_plana_se_excluye(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    plana = tmp_path / "plana"
    _salida(plana, dict(zip(TAREAS, "rrrnnn", strict=True)), nombre="p1")
    _salida(plana, dict(zip(TAREAS, "rrrnnn", strict=True)), nombre="p2")
    (plana / "registro_iteracion_p2.jsonl").write_text(_registro(dict(zip(TAREAS, "rcrnnn", strict=True))))
    codigo, r, _ = _comparar(capsys, tmp_path, [plana / "iteracion_p1.json"], [plana / "iteracion_p2.json"])
    assert r["pares"]["tareas_excluidas"] == ["a_2"] and codigo != 0


def test_un_json_sin_su_registro_es_entrada_invalida(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p1, p2 = _dos(tmp_path, "rrrnnn", "rrrnnn")
    (p2 / "registro_iteracion_p2.jsonl").rename(p2 / "registro_iteracion_otro.jsonl")
    codigo, _, err = _comparar(capsys, tmp_path, [p1], [p2])
    assert codigo == kc.EXIT_ENTRADA and "no existe su registro" in err


def test_la_misma_salida_en_los_dos_lados_no_sale_con_0(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p1 = _salida(tmp_path / "p1", dict(zip(TAREAS, "rrrnnn", strict=True)), nombre="p1")
    codigo, r, _ = _comparar(capsys, tmp_path, [p1], [p1])
    assert codigo == 4 and any("misma salida" in m for m in r["motivos"])
    # Una copia byte a byte en otra ruta tampoco.
    copia = tmp_path / "copia"
    copia.mkdir()
    for archivo in p1.iterdir():
        (copia / archivo.name).write_bytes(archivo.read_bytes())
    assert _comparar(capsys, tmp_path, [p1], [copia])[0] == 4


def test_cero_pares_tras_excluir_no_sale_con_0(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    p1 = _salida(tmp_path / "p1", {"a_1": "c"}, nombre="p1")
    p2 = _salida(tmp_path / "p2", {"a_1": "r"}, nombre="p2")
    codigo, r, _ = _comparar(capsys, tmp_path, [p1], [p2], lista=["a_1"])
    assert codigo == 4 and r["pares"]["que_quedan"] == 0 and r["tabla"]["mcnemar_p_exacto"] is None
    assert any("ningún par" in m for m in r["motivos"])


# ---------------------------------------------------------------------------
# El JSON
# ---------------------------------------------------------------------------


def test_una_sesion_sin_cierre_no_es_completa_aunque_el_json_lo_diga(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p1, p2 = _dos(tmp_path, "rrrnnn", "rrrnnn", cierre=False)
    codigo, r, _ = _comparar(capsys, tmp_path, [p1], [p2])
    assert codigo == 4 and any("registro dice" in m for m in r["motivos"])


@pytest.mark.parametrize("completo", [False, None])
def test_un_json_que_no_dice_completo_no_es_una_pasada_completa(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], completo: bool | None
) -> None:
    p1 = _salida(tmp_path / "p1", dict(zip(TAREAS, "rrrnnn", strict=True)), nombre="p1", completo=completo)
    p2 = _salida(tmp_path / "p2", dict(zip(TAREAS, "rrrnnn", strict=True)), nombre="p2")
    codigo, r, _ = _comparar(capsys, tmp_path, [p1], [p2])
    assert codigo == 4 and any("completo: true" in m for m in r["motivos"])


def test_acepta_la_carpeta_del_rescate_con_prefijo_salida_y_el_json_directo(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p1 = _salida(tmp_path / "p1", dict(zip(TAREAS, "rrrnnn", strict=True)), prefijo="salida__", nombre="p1")
    p2 = _salida(tmp_path / "p2", dict(zip(TAREAS, "rrrnnn", strict=True)), nombre="p2")
    codigo, r, _ = _comparar(capsys, tmp_path, [p1], [p2 / "iteracion_p2.json"])
    assert codigo == 0 and r["tabla"]["mcnemar_p_exacto"] == 1.0


@pytest.mark.parametrize(
    "que", ["sin_json", "dos_json", "sin_registro", "json_roto", "sin_corridas", "repetida"]
)
def test_una_entrada_ilegible_sale_con_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], que: str
) -> None:
    p1, p2 = _dos(tmp_path, "rrrnnn", "rrrnnn")
    archivo = p2 / "iteracion_p2.json"
    if que == "sin_json":
        archivo.unlink()
    elif que == "dos_json":
        (p2 / "iteracion_otra.json").write_text("{}", encoding="utf-8")
    elif que == "sin_registro":
        (p2 / "registro_iteracion_p2.jsonl").unlink()
    elif que == "json_roto":
        archivo.write_text("{", encoding="utf-8")
    elif que == "sin_corridas":
        archivo.write_text(json.dumps({"completo": True}), encoding="utf-8")
    else:
        datos = json.loads(archivo.read_text(encoding="utf-8"))
        datos["corridas"]["X1"]["tareas"].append(dict(datos["corridas"]["X1"]["tareas"][0]))
        archivo.write_text(json.dumps(datos), encoding="utf-8")
    codigo, _, err = _comparar(capsys, tmp_path, [p1], [p2])
    assert codigo == kc.EXIT_ENTRADA and "ENTRADA INVÁLIDA" in err


def test_una_carpeta_que_no_existe_sale_con_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    p1 = _salida(tmp_path / "p1", dict(zip(TAREAS, "rrrnnn", strict=True)), nombre="p1")
    assert _comparar(capsys, tmp_path, [p1], [tmp_path / "no_existe"])[0] == kc.EXIT_ENTRADA


def test_solo_cuentan_las_corridas_que_cuentan_para_las_resueltas(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p1, p2 = _dos(tmp_path, "rrrnnn", "rrrnnn")
    archivo = p2 / "iteracion_p2.json"
    datos = json.loads(archivo.read_text(encoding="utf-8"))
    datos["corridas"]["CTRL"] = {
        "condicion": "A",
        "cuenta_para_resueltas": False,
        "tareas": [{"instance_id": "a_1", "resuelta": True}, {"instance_id": "control_9", "resuelta": True}],
    }
    archivo.write_text(json.dumps(datos), encoding="utf-8")
    codigo, r, _ = _comparar(capsys, tmp_path, [p1], [p2])
    assert codigo == 0 and r["lados"]["otra"]["tareas"] == 6


def test_dos_corridas_que_cuentan_con_condiciones_distintas_no_se_funden(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p1 = _salida(tmp_path / "p1", dict(zip(TAREAS, "rrrnnn", strict=True)), nombre="p1")
    corridas = {
        "X1": {
            "condicion": "A",
            "cuenta_para_resueltas": True,
            "tareas": [{"instance_id": "a_1", "resuelta": True}],
        },
        "X2": {
            "condicion": "B",
            "cuenta_para_resueltas": True,
            "tareas": [{"instance_id": t, "resuelta": True} for t in TAREAS[1:]],
        },
    }
    p2 = _salida(tmp_path / "p2", dict(zip(TAREAS, "rrrnnn", strict=True)), nombre="p2", corridas=corridas)
    codigo, _, err = _comparar(capsys, tmp_path, [p1], [p2])
    assert codigo == kc.EXIT_ENTRADA and "condiciones distintas" in err


def test_la_salida_se_fuerza_a_utf8(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    llamadas: list[str] = []

    class Falso:
        def reconfigure(self, **kw: Any) -> None:
            llamadas.append(kw["encoding"])

        def write(self, texto: str) -> int:
            return len(texto)

        def flush(self) -> None:
            pass

    monkeypatch.setattr(kc.sys, "stdout", Falso())
    monkeypatch.setattr(kc.sys, "stderr", Falso())
    assert kc.main(["--base", str(tmp_path / "x"), "--otra", str(tmp_path / "y")]) == kc.EXIT_ENTRADA
    assert llamadas == ["utf-8", "utf-8"]


# ---------------------------------------------------------------------------
# Segunda revisión: el registro cruzado con el JSON, la huella de contenido y las líneas ilegibles
# ---------------------------------------------------------------------------


def _fijar_resuelta_en_el_registro(ruta: Path, valor: bool) -> None:
    eventos = [json.loads(x) for x in ruta.read_text(encoding="utf-8").splitlines()]
    for e in eventos:
        if e["evento"] == "tarea_fin":
            e["resuelta"] = valor
    ruta.write_text("\n".join(json.dumps(e) for e in eventos), encoding="utf-8")


def test_un_registro_de_otra_pasada_con_el_nombre_de_esta_no_sale_con_0(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """El registro del otro lado copiado con el nombre de este: mismas tareas, otro ``resuelta``."""
    p1 = _salida(tmp_path / "p1", dict(zip(TAREAS, "rrrnnn", strict=True)), nombre="p1")
    p2 = _salida(tmp_path / "p2", dict(zip(TAREAS, "nnnrrr", strict=True)), nombre="p2")
    copia = (p1 / "registro_iteracion_p1.jsonl").read_text(encoding="utf-8")
    (p2 / "registro_iteracion_p2.jsonl").write_text(copia, encoding="utf-8")
    codigo, r, _ = _comparar(capsys, tmp_path, [p1], [p2])
    assert codigo == 4
    (motivo,) = [m for m in r["motivos"] if "no coinciden en si" in m]
    assert "6 tareas" in motivo and "a_1" in motivo


def test_un_json_con_seis_resueltas_frente_a_un_registro_con_cero_no_sale_con_0(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p1 = _salida(tmp_path / "p1", dict.fromkeys(TAREAS, "r"), nombre="p1")
    p2 = _salida(tmp_path / "p2", dict.fromkeys(TAREAS, "r"), nombre="p2")
    _fijar_resuelta_en_el_registro(p2 / "registro_iteracion_p2.jsonl", False)
    codigo, r, _ = _comparar(capsys, tmp_path, [p1], [p2])
    assert codigo == 4 and any("no coinciden en si 6 tareas" in m for m in r["motivos"])


def test_una_copia_reformateada_de_la_misma_salida_sale_con_4(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p1 = _salida(tmp_path / "p1", dict(zip(TAREAS, "rrrnnn", strict=True)), nombre="p1")
    p2 = tmp_path / "p2"
    shutil.copytree(p1, p2)
    original = (p1 / "registro_iteracion_p1.jsonl").read_text(encoding="utf-8")
    (p2 / "registro_iteracion_p1.jsonl").write_text("\n\n" + original + "\n\n", encoding="utf-8")
    datos = json.loads((p1 / "iteracion_p1.json").read_text(encoding="utf-8"))
    (p2 / "iteracion_p1.json").write_text(json.dumps(datos, indent=4, sort_keys=True), encoding="utf-8")
    codigo, r, _ = _comparar(capsys, tmp_path, [p1], [p2])
    assert codigo == 4 and any("comparten la misma salida" in m for m in r["motivos"])


def test_dos_pasadas_distintas_con_las_mismas_tareas_y_resultados_no_comparten_huella(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p1, p2 = _dos(tmp_path, "rrrnnn", "rrrnnn")
    codigo, r, _ = _comparar(capsys, tmp_path, [p1], [p2])
    assert codigo == 0 and not any("misma salida" in m for m in r["motivos"])


@pytest.mark.parametrize("que", ["truncada", "basura_tras_el_cierre"])
def test_un_registro_con_lineas_ilegibles_no_sale_con_0_y_llega_al_informe(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], que: str
) -> None:
    p1, p2 = _dos(tmp_path, "rrrnnn", "rrrnnn")
    ruta = p2 / "registro_iteracion_p2.jsonl"
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    if que == "truncada":
        i = next(n for n, x in enumerate(lineas) if '"peticion_fin"' in x)
        lineas[i] = lineas[i][: len(lineas[i]) // 2]
    else:
        lineas.append('{"evento": "peticion_fin", "ta')
    ruta.write_text("\n".join(lineas), encoding="utf-8")
    codigo, r, _ = _comparar(capsys, tmp_path, [p1], [p2])
    assert codigo == 4 and any("líneas ilegibles" in m for m in r["motivos"])
    assert r["lados"]["otra"]["salidas"][0]["lineas_ilegibles"] == 1
    assert r["lados"]["base"]["salidas"][0]["lineas_ilegibles"] == 0


# ---------------------------------------------------------------------------
# Defectos que sobrevivían a la primera corrección
# ---------------------------------------------------------------------------


def _corrida(marca: bool | None, resueltas: str) -> dict[str, Any]:
    corrida: dict[str, Any] = {
        "condicion": "A",
        "tareas": [{"instance_id": t, "resuelta": c == "r"} for t, c in zip(TAREAS, resueltas, strict=True)],
    }
    if marca is not None:
        corrida["cuenta_para_resueltas"] = marca
    return corrida


def test_una_corrida_sin_la_marca_no_cuenta_aunque_traiga_filas(tmp_path: Path) -> None:
    solo_sin_marca = {"X1": _corrida(None, "rrrnnn")}
    p = _salida(
        tmp_path / "p1", dict(zip(TAREAS, "rrrnnn", strict=True)), nombre="p1", corridas=solo_sin_marca
    )
    with pytest.raises(kc.CompararError, match="ninguna corrida trae cuenta_para_resueltas"):
        kc.leer_salida(p)
    mixtas = {
        "X0": {"condicion": "A", "tareas": [{"instance_id": "x_9", "resuelta": True}]},
        "X1": _corrida(True, "rrrnnn"),
    }
    p3 = _salida(tmp_path / "p3", dict(zip(TAREAS, "rrrnnn", strict=True)), nombre="p3", corridas=mixtas)
    assert set(kc.leer_salida(p3)["filas"]) == set(TAREAS)


@pytest.mark.parametrize("valor", ["true", 1, None])
def test_una_fila_con_resuelta_que_no_es_booleano_es_entrada_invalida(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], valor: Any
) -> None:
    p1 = _salida(tmp_path / "p1", dict(zip(TAREAS, "rrrnnn", strict=True)), nombre="p1")
    p2 = _salida(tmp_path / "p2", dict(zip(TAREAS, "rrrnnn", strict=True)), nombre="p2")
    archivo = p2 / "iteracion_p2.json"
    datos = json.loads(archivo.read_text(encoding="utf-8"))
    datos["corridas"]["X1"]["tareas"][0]["resuelta"] = valor
    archivo.write_text(json.dumps(datos), encoding="utf-8")
    codigo, _, err = _comparar(capsys, tmp_path, [p1], [p2])
    assert codigo == kc.EXIT_ENTRADA and "«resuelta» booleano" in err


def test_un_json_sin_ninguna_corrida_que_cuente_es_entrada_invalida(tmp_path: Path) -> None:
    p = _salida(tmp_path / "p", dict(zip(TAREAS, "rrrnnn", strict=True)), nombre="p", corridas={"X1": 3})
    with pytest.raises(kc.CompararError, match="ninguna corrida trae cuenta_para_resueltas"):
        kc.leer_salida(p)


def test_un_registro_sin_ningun_evento_legible_es_entrada_invalida(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p1, p2 = _dos(tmp_path, "rrrnnn", "rrrnnn")
    (p2 / "registro_iteracion_p2.jsonl").write_text("no es json\n", encoding="utf-8")
    codigo, _, err = _comparar(capsys, tmp_path, [p1], [p2])
    assert codigo == kc.EXIT_ENTRADA and "ningún evento legible" in err


def test_una_lista_con_elementos_que_no_son_texto_es_entrada_invalida(tmp_path: Path) -> None:
    p1 = _salida(tmp_path / "p1", dict(zip(TAREAS, "rrrnnn", strict=True)), nombre="p1")
    lista = tmp_path / "lista.json"
    lista.write_text(json.dumps({"lista": [1, 2, 3]}), encoding="utf-8")
    assert kc.main(["--base", str(p1), "--otra", str(p1), "--lista", str(lista)]) == kc.EXIT_ENTRADA


def test_una_colgada_sin_par_no_cuenta_como_excluida_y_ninguna_resuelta_descuenta_las_excluidas(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # a_6 falta en la base y está colgada en la otra (sin par); a_2 está colgada en la otra y sí tiene par.
    p1 = _salida(tmp_path / "p1", dict(zip(TAREAS[:5], "rrnnn", strict=True)), nombre="p1")
    p2 = _salida(tmp_path / "p2", dict(zip(TAREAS, "rcnnnc", strict=True)), nombre="p2")
    _, r, _ = _comparar(capsys, tmp_path, [p1], [p2])
    assert r["pares"]["excluidos"] == 1 and r["pares"]["tareas_excluidas"] == ["a_2"]
    assert r["pares"]["colgadas_sin_par"] == ["a_6"]
    # quedan a_1, a_3, a_4 y a_5: a_1 la resuelven las dos y las otras tres, ninguna
    assert r["tabla"]["concordantes"] == {"ambas_resueltas": 1, "ninguna_resuelta": 3}
    assert r["tabla"]["discordantes"]["solo_base"] == 0 and r["tabla"]["discordantes"]["solo_otra"] == 0


def test_el_mensaje_de_resuelta_que_no_coincide_nombra_solo_cinco_y_dice_que_hay_mas(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ids = _ids(7)
    p1 = _salida(tmp_path / "p1", dict.fromkeys(ids, "r"), nombre="p1")
    p2 = _salida(tmp_path / "p2", dict.fromkeys(ids, "r"), nombre="p2")
    _fijar_resuelta_en_el_registro(p2 / "registro_iteracion_p2.jsonl", False)
    _, r, _ = _comparar(capsys, tmp_path, [p1], [p2], lista=ids)
    (motivo,) = [m for m in r["motivos"] if "no coinciden en si" in m]
    assert "7 tareas" in motivo and "b_5" in motivo and "b_6" not in motivo and "…" in motivo


def test_una_sesion_cortada_a_media_tarea_no_rompe_la_comparacion(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """La última tarea empezó y no tiene ``tarea_fin``: se dice por el registro, no por una excepción."""
    p1, p2 = _dos(tmp_path, "rrrnnn", "rrrnnn", cierre=False)
    ruta = p2 / "registro_iteracion_p2.jsonl"
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    ruta.write_text(
        "\n".join(x for x in lineas if '"tarea_fin"' not in x or "a_6" not in x), encoding="utf-8"
    )
    codigo, r, _ = _comparar(capsys, tmp_path, [p1], [p2])
    assert codigo == 4 and not any("no coinciden en si" in m for m in r["motivos"])


def test_el_latido_se_lee_y_distingue_una_sesion_viva_y_detenida_de_una_muerta(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p1, p2 = _dos(tmp_path, "rrrnnn", "rrrnnn", cierre=False)
    sin_latido = _comparar(capsys, tmp_path, [p1], [p2])[1]
    assert any("muerta desde fuera" in m for m in sin_latido["motivos"])
    (p2 / "latido_iteracion_p2.jsonl").write_text(json.dumps({"hora": T0 + 100_000}), encoding="utf-8")
    con_latido = _comparar(capsys, tmp_path, [p1], [p2])[1]
    assert any("viva y detenida" in m for m in con_latido["motivos"])
