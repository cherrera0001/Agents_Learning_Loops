"""Tests del sorteo y de la lectura del registro (`scripts/kaggle_registro.py`). Sin red ni Docker."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any

import pytest

from scripts import kaggle_registro as kr

UNIVERSO = [f"t_{i:02d}" for i in range(71)]


def _validez(tmp_path: Path, validas: list[str], otras: int = 5) -> Path:
    tareas = [{"instance_id": i, "clase": "discrimina"} for i in reversed(validas)]
    tareas += [{"instance_id": f"otra_{i}", "clase": "dorado_falla"} for i in range(otras)]
    ruta = tmp_path / "validez_ensayo.json"
    ruta.write_text(json.dumps({"sandbox": "subprocess", "tareas": tareas}), encoding="utf-8")
    return ruta


def test_el_universo_son_las_tareas_que_discriminan_ordenadas(tmp_path: Path) -> None:
    validez = json.loads(_validez(tmp_path, UNIVERSO).read_text(encoding="utf-8"))
    assert kr.universo_valido(validez) == UNIVERSO
    with pytest.raises(kr.RegistroError):
        kr.universo_valido({"sin": "tareas"})


def test_el_sorteo_es_el_de_la_semilla_escrita() -> None:
    """Valores calculados aparte, sin este guion, con el procedimiento del issue."""
    lista = kr.sortear(UNIVERSO)
    assert len(lista) == 60 == len(set(lista)) and set(lista) <= set(UNIVERSO)
    assert lista[:5] == ["t_42", "t_62", "t_38", "t_55", "t_70"]
    assert kr.huella_de_lista(lista) == "b6f4ed6bc1626d77bec5a5d7ed4ad7780cfb0625381735fd339083af6f0115cd"
    assert kr.sortear(list(reversed(UNIVERSO))) == lista
    assert kr.sortear(UNIVERSO, semilla="otra") != lista


@pytest.mark.parametrize("universo", [UNIVERSO[:70], [*UNIVERSO, "t_71"], [*UNIVERSO[:70], "t_00"]])
def test_el_sorteo_se_detiene_si_el_universo_no_es_el_esperado(universo: list[str]) -> None:
    with pytest.raises(kr.RegistroError, match="se detiene"):
        kr.sortear(universo)


def test_la_orden_sortear_guarda_el_acta_y_no_pisa_una_lista_distinta(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    validez, salida = _validez(tmp_path, UNIVERSO), tmp_path / "sorteo.json"
    assert kr.main(["sortear", "--validez", str(validez), "--salida", str(salida)]) == kr.EXIT_OK
    acta = json.loads(salida.read_text(encoding="utf-8"))
    assert acta == json.loads(capsys.readouterr().out)
    assert (acta["universo"], acta["n"], acta["semilla"]) == (71, 60, kr.SEMILLA_ITERACION_08)
    assert sorted(acta["lista"] + acta["fuera_del_sorteo"]) == UNIVERSO
    assert acta["lista_sha256"] == kr.huella_de_lista(acta["lista"])

    assert kr.main(["sortear", "--validez", str(validez), "--salida", str(salida)]) == kr.EXIT_OK
    guardado = salida.read_bytes()
    args = ["sortear", "--validez", str(validez), "--salida", str(salida), "--semilla", "otra"]
    assert kr.main(args) == kr.EXIT_DIFIERE
    assert salida.read_bytes() == guardado


def test_la_orden_sortear_rechaza_un_universo_de_otro_tamano(tmp_path: Path) -> None:
    assert kr.main(["sortear", "--validez", str(_validez(tmp_path, UNIVERSO[:69]))]) == kr.EXIT_ENTRADA
    assert kr.main(["sortear", "--validez", str(tmp_path / "no_existe.json")]) == kr.EXIT_ENTRADA


def _e(tipo: str, tarea: str | None = "t_1", **campos: Any) -> dict[str, Any]:
    return {"evento": tipo, "tarea": tarea, "hora_utc": "2026-10-09T00:00:00.000+00:00", **campos}


def _peticion(n: int, motivo: str | None, tarea: str = "t_1", **fin: Any) -> list[dict[str, Any]]:
    eventos = [
        _e("peticion_inicio", tarea, peticion=n, caracteres_entrada=1000 + n, n_mensajes=2),
        _e("cb_antes", tarea, llamada=f"id{n}", peticion_en_curso=n),
    ]
    if motivo is not None:
        eventos.append(_e("peticion_fin", tarea, peticion=n, motivo=motivo, segundos=1.5, **fin))
    if motivo in ("stop", "tool_calls"):
        eventos.append(_e("cb_exito", tarea, llamada=f"id{n}", peticion_en_curso=None))
    return eventos


def test_leer_jsonl_tolera_una_ultima_linea_a_medias() -> None:
    filas, ilegibles = kr.leer_jsonl('{"a": 1}\n\n[1]\n{"evento": "petic')
    assert filas == [{"a": 1}] and ilegibles == 2


def test_una_sesion_sin_corte_tiene_cada_inicio_con_su_fin() -> None:
    eventos = [
        _e("tarea_inicio"),
        *_peticion(1, "tool_calls"),
        *_peticion(2, "stop"),
        _e("agente_fin", error=None, entrego=True, parche_caracteres=10, llamadas_herramientas=1),
        _e("diff_cierre", bytes=10, sha256="ab", archivos=["x.py"]),
        _e("tarea_fin", clase="resuelta", error=None),
        _e("cierre", None),
    ]
    d = kr.diagnosticar(eventos, [{"hora_utc": "h", "sesion_s": 9.0, "en_vuelo": []}])
    assert d["sesion"]["veredicto"].startswith("completa") and d["sesion"]["cerrada"] is True
    assert d["peticiones"] == {
        "iniciadas": 2,
        "con_fin": 2,
        "motivos": {"tool_calls": 1, "stop": 1},
        "no_respondidas": [],
    }
    (tarea,) = d["tareas"]
    assert tarea["peticion_en_vuelo"] is None and tarea["tope_que_corto"] is None
    assert tarea["ultima_peticion"]["peticion"] == 2 and tarea["diff_al_cierre"]["bytes"] == 10
    assert d["enganches"]["retrollamadas"] == {"cb_antes": 2, "cb_exito": 2}


def test_un_tope_de_tiempo_se_lee_del_agente_aunque_la_fila_diga_resuelta() -> None:
    eventos = [
        _e("tarea_inicio"),
        *_peticion(1, "tool_calls"),
        *_peticion(2, "cancelada", error="CancelledError"),
        _e("agente_fin", error="Agent exceeded session timeout (4.0 min)", entrego=False),
        _e("diff_cierre", bytes=77, sha256="cd", archivos=["x.py"]),
        _e("tarea_fin", clase="resuelta", error=None),
        _e("cierre", None),
    ]
    d = kr.diagnosticar(eventos, [])
    (tarea,) = d["tareas"]
    assert tarea["clase"] == "resuelta" and tarea["tope_que_corto"] == "tope de tiempo de la tarea"
    en_vuelo = tarea["peticion_en_vuelo"]
    assert (en_vuelo["peticion"], en_vuelo["como_termino"], en_vuelo["caracteres_entrada"]) == (
        2,
        "cancelada",
        1002,
    )
    assert en_vuelo["hora_utc"] and en_vuelo["retrollamadas"] == {"cb_antes": 1}
    assert d["enganches"]["no_respondidas_por_retrollamada"] == [
        {"peticion": 2, "como_termino": "cancelada", "cb_antes": 1}
    ]


@pytest.mark.parametrize(
    ("error", "tope"),
    [
        ("Agent exceeded tool call budget (40 calls)", "tope de llamadas"),
        ("Agent exceeded turns budget (100 turns)", "tope de turnos"),
        (
            "Sandbox execution error: litellm.InternalServerError: Connection error.",
            "el servidor del modelo dejó de responder",
        ),
        ("Agent completed execution without calling submit_patch.", None),
        (None, None),
    ],
)
def test_el_tope_sale_del_mensaje_del_arnes(error: str | None, tope: str | None) -> None:
    assert kr.tope_de_tarea(error) == tope


def test_una_sesion_muerta_desde_fuera_deja_un_inicio_sin_fin() -> None:
    eventos = [_e("tarea_inicio"), *_peticion(1, "tool_calls"), *_peticion(2, None)]
    latido = {"hora_utc": "h", "sesion_s": 54.6, "tarea": "t_1", "en_vuelo": [{"peticion": 2}], "otro": 1}
    d = kr.diagnosticar(eventos, [latido])
    assert d["sesion"]["veredicto"].startswith("muerta desde fuera") and d["sesion"]["cerrada"] is False
    assert (
        d["sesion"]["ultimo_latido"]["en_vuelo"] == [{"peticion": 2}]
        and "otro" not in d["sesion"]["ultimo_latido"]
    )
    (tarea,) = d["tareas"]
    assert tarea["terminada"] is False and tarea["diff_al_cierre"] is None
    assert (
        tarea["peticion_en_vuelo"]["como_termino"] == "sin fin"
        and tarea["peticion_en_vuelo"]["segundos"] is None
    )
    assert d["peticiones"]["con_fin"] == 1 and d["peticiones"]["motivos"] == {"tool_calls": 1, "sin fin": 1}


def test_un_corte_del_notebook_dice_cual_y_la_tarea_caida_su_error() -> None:
    eventos = [
        _e("tarea_inicio"),
        *_peticion(1, "error", error="InternalServerError"),
        _e("cb_fallo", llamada="id1"),
        _e("diff_cierre", error="RuntimeError: sin git"),
        _e("tarea_fin", clase="otro_error_sin_parche", error="Sandbox execution error: Connection error."),
        _e("corte", None, cortado_por="servidor"),
        _e("cierre", None),
    ]
    d = kr.diagnosticar(eventos, [])
    assert (
        d["sesion"]["cortado_por"] == "servidor" and "servidor del modelo caído" in d["sesion"]["veredicto"]
    )
    (tarea,) = d["tareas"]
    assert tarea["tope_que_corto"] == "el servidor del modelo dejó de responder"
    assert tarea["peticion_en_vuelo"]["retrollamadas"] == {"cb_antes": 1, "cb_fallo": 1}
    assert tarea["diff_al_cierre"] == {"error": "RuntimeError: sin git"}
    otro = kr.diagnosticar([_e("corte", None, cortado_por="fallo KeyError")], [])
    assert otro["sesion"]["veredicto"] == "cortada por el notebook: fallo KeyError" and otro["tareas"] == []


def _salida(tmp_path: Path) -> tuple[str, str]:
    eventos = [
        _e("tarea_inicio"),
        *_peticion(1, "stop"),
        _e("tarea_fin", clase="resuelta"),
        _e("cierre", None),
    ]
    registro = "\n".join(json.dumps(e) for e in eventos) + "\n"
    latido = json.dumps({"hora_utc": "h", "sesion_s": 1.0}) + "\n"
    return registro, latido


def test_el_registro_se_lee_de_una_carpeta_y_de_un_zip(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registro, latido = _salida(tmp_path)
    carpeta = tmp_path / "working"
    carpeta.mkdir()
    (carpeta / "registro_s.jsonl").write_text(registro, encoding="utf-8")
    (carpeta / "latido_s.jsonl").write_text(latido, encoding="utf-8")
    crudo = tmp_path / "crudo.zip"
    with zipfile.ZipFile(crudo, "w") as z:
        z.writestr("registro/registro_s.jsonl", registro)
        z.writestr("logs/registro_que_no_es.jsonl", "{}")
    de_carpeta, de_zip = kr.cargar_salida(carpeta), kr.cargar_salida(crudo)
    assert de_carpeta["eventos"] == de_zip["eventos"] and len(de_zip["eventos"]) == 7
    assert (de_carpeta["hay_latido"], de_zip["hay_latido"]) == (True, False)

    assert kr.main(["diagnosticar", "--salida", str(crudo)]) == kr.EXIT_OK
    informe = json.loads(capsys.readouterr().out)
    assert informe["sesion"]["veredicto"].startswith("completa") and informe["hay_latido"] is False


def test_una_salida_sin_registro_es_una_entrada_invalida(tmp_path: Path) -> None:
    vacia = tmp_path / "vacia"
    vacia.mkdir()
    roto = tmp_path / "roto.zip"
    roto.write_bytes(b"no es un zip")
    for ruta in (vacia, roto, tmp_path / "no_existe"):
        with pytest.raises(kr.RegistroError):
            kr.cargar_salida(ruta)
        assert kr.main(["diagnosticar", "--salida", str(ruta)]) == kr.EXIT_ENTRADA
