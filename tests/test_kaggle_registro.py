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


def test_un_acta_o_una_validez_ilegibles_no_se_confunden_con_una_lista_distinta(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    validez, salida = _validez(tmp_path, UNIVERSO), tmp_path / "sorteo.json"
    for acta_rota in ("{no es json", '{"sin": "lista"}', "[1, 2]"):
        salida.write_text(acta_rota, encoding="utf-8")
        assert kr.main(["sortear", "--validez", str(validez), "--salida", str(salida)]) == kr.EXIT_ENTRADA
        assert "ENTRADA INVÁLIDA" in capsys.readouterr().err
        assert salida.read_text(encoding="utf-8") == acta_rota
    sin_id = tmp_path / "sin_id.json"
    sin_id.write_text(json.dumps({"tareas": [{"clase": "discrimina"}]}), encoding="utf-8")
    assert kr.main(["sortear", "--validez", str(sin_id)]) == kr.EXIT_ENTRADA
    assert "instance_id" in capsys.readouterr().err
    assert kr.EXIT_ENTRADA != kr.EXIT_DIFIERE


ENGANCHES = {"peticiones": "instalado", "logs por tarea (rich)": "modo archivo", "latido": "cada 30.0 s"}
INSTALADO = {"evento": "registro_instalado", "tarea": None, "enganches": ENGANCHES}


def _e(tipo: str, tarea: str | None = "t_1", **campos: Any) -> dict[str, Any]:
    return {"evento": tipo, "tarea": tarea, "hora_utc": "2026-10-09T00:00:00.000+00:00", **campos}


def _inicio(n: int, tarea: str = "t_1") -> list[dict[str, Any]]:
    return [
        _e("peticion_inicio", tarea, peticion=n, caracteres_entrada=1000 + n, n_mensajes=2),
        _e("cb_antes", tarea, llamada=f"id{n}", peticion_en_curso=n),
    ]


def _fin(n: int, motivo: str, tarea: str = "t_1", **campos: Any) -> list[dict[str, Any]]:
    eventos = [_e("peticion_fin", tarea, peticion=n, motivo=motivo, segundos=1.5, **campos)]
    if motivo in ("stop", "tool_calls"):
        eventos.append(_e("cb_exito", tarea, llamada=f"id{n}", peticion_en_curso=None))
    return eventos


def _peticion(n: int, motivo: str | None, tarea: str = "t_1", **fin: Any) -> list[dict[str, Any]]:
    return _inicio(n, tarea) + ([] if motivo is None else _fin(n, motivo, tarea, **fin))


def _tarea(tarea: str, peticiones: list[dict[str, Any]], diff: int, **fin: Any) -> list[dict[str, Any]]:
    return [
        _e("tarea_inicio", tarea),
        *peticiones,
        _e("agente_fin", tarea, error=fin.get("error"), entrego=True, parche_caracteres=diff),
        _e("diff_cierre", tarea, bytes=diff, sha256=f"sha-{tarea}-{diff}", archivos=[f"{tarea}.py"]),
        _e("tarea_fin", tarea, clase=fin.get("clase", "resuelta"), error=None),
    ]


CIERRE = _e("cierre", None, errores_del_registro=0, ultimo_error=None)


def test_leer_jsonl_tolera_una_ultima_linea_a_medias() -> None:
    filas, ilegibles = kr.leer_jsonl('{"a": 1}\n\n[1]\n{"evento": "petic')
    assert filas == [{"a": 1}] and ilegibles == 2


def test_una_sesion_sin_corte_tiene_cada_inicio_con_su_fin() -> None:
    eventos = [INSTALADO, *_tarea("t_1", _peticion(1, "tool_calls") + _peticion(2, "stop"), 10), CIERRE]
    d = kr.diagnosticar(eventos, [{"hora_utc": "h", "sesion_s": 9.0, "en_vuelo": []}])
    assert d["sesion"]["veredicto"].startswith("completa") and d["sesion"]["cerrada"] is True
    assert d["sesion"]["registro_fiable"] is True and kr.codigo_de(d) == kr.EXIT_OK
    assert d["peticiones"] == {
        "iniciadas": 2,
        "con_fin": 2,
        "motivos": {"tool_calls": 1, "stop": 1},
        "no_respondidas": [],
    }
    (tarea,) = d["tareas"]
    assert tarea["peticion_en_vuelo"] is None and tarea["peticion_cortada"] is None
    assert tarea["tope_que_corto"] is None and tarea["veces_en_la_sesion"] == 1
    assert tarea["ultima_peticion"]["peticion"] == 2 and tarea["diff_al_cierre"]["bytes"] == 10
    assert d["enganches"]["retrollamadas"] == {"cb_antes": 2, "cb_exito": 2}


def test_un_registro_que_no_registro_no_es_una_sesion_completa() -> None:
    """El caso que encontró la revisión: enganches en FALLO, ninguna petición y errores propios."""
    rotos = {"peticiones": "FALLO ModuleNotFoundError: x", "logs por tarea (rich)": "FALLO ImportError: y"}
    eventos = [
        {**INSTALADO, "enganches": {**rotos, "retrollamadas de litellm": "FALLO ImportError: z"}},
        _e("tarea_inicio"),
        _e("tarea_fin", clase="resuelta", error=None),
        _e("cierre", None, errores_del_registro=7, ultimo_error="OSError: disco"),
    ]
    d = kr.diagnosticar(eventos, [])
    assert not d["sesion"]["veredicto"].startswith("completa")
    assert d["sesion"]["veredicto"].startswith("registro no fiable") and d["sesion"]["estado"] == "completa"
    problemas = d["sesion"]["problemas_del_registro"]
    assert sum(p.startswith("enganche sin instalar") for p in problemas) == 2
    assert any("7 errores propios" in p for p in problemas)
    assert any("ninguna petición con respuesta" in p for p in problemas)
    assert kr.codigo_de(d) == kr.EXIT_REGISTRO


@pytest.mark.parametrize(
    ("cambio", "frase"),
    [
        (lambda ev: ev[1:], "registro_instalado"),
        (
            lambda ev: [{**ev[0], "enganches": {"diff al cierre": "FALLO KeyError: x"}}, *ev[1:]],
            "enganche sin",
        ),
        (lambda ev: [*ev[:-1], _e("cierre", None, errores_del_registro=1, ultimo_error="x")], "1 errores"),
        (
            lambda ev: [
                *ev[:-1],
                _e("guardia", None, cuando="tras la primera tarea", problemas=["x"]),
                ev[-1],
            ],
            "guardia",
        ),
        (lambda ev: [e for e in ev if not e["evento"].startswith(("peticion_", "cb_"))], "ninguna petición"),
    ],
)
def test_cada_motivo_de_desconfianza_cambia_el_veredicto_y_el_codigo(cambio: Any, frase: str) -> None:
    sana = [INSTALADO, *_tarea("t_1", _peticion(1, "stop"), 10), CIERRE]
    assert kr.codigo_de(kr.diagnosticar(sana, [])) == kr.EXIT_OK
    d = kr.diagnosticar(cambio(sana), [])
    assert kr.codigo_de(d) == kr.EXIT_REGISTRO and frase in d["sesion"]["veredicto"]


def test_las_retrollamadas_en_fallo_no_hacen_desconfiar_del_registro() -> None:
    instalado = {**INSTALADO, "enganches": {**ENGANCHES, "retrollamadas de litellm": "FALLO ImportError: z"}}
    d = kr.diagnosticar([instalado, *_tarea("t_1", _peticion(1, "stop"), 10), CIERRE], [])
    assert d["sesion"]["registro_fiable"] is True and kr.codigo_de(d) == kr.EXIT_OK


def test_el_fin_se_empareja_por_numero_y_no_con_la_ultima_peticion_vista() -> None:
    eventos = [INSTALADO, _e("tarea_inicio"), *_inicio(1), *_inicio(2), *_fin(1, "stop")]
    d = kr.diagnosticar(eventos, [])
    fichas = {f["peticion"]: f["como_termino"] for f in d["peticiones"]["no_respondidas"]}
    assert fichas == {2: "sin fin"} and d["peticiones"]["motivos"] == {"stop": 1, "sin fin": 1}
    assert d["tareas"][0]["peticion_en_vuelo"]["peticion"] == 2


def test_un_tope_de_tiempo_se_lee_del_agente_aunque_la_fila_diga_resuelta() -> None:
    peticiones = _peticion(1, "tool_calls") + _peticion(2, "cancelada", error="CancelledError")
    sesion = _tarea("t_1", peticiones, 77, error="Agent exceeded session timeout (4.0 min)")
    d = kr.diagnosticar([INSTALADO, *sesion, CIERRE], [])
    (tarea,) = d["tareas"]
    assert tarea["clase"] == "resuelta" and tarea["tope_que_corto"] == "tope de tiempo de la tarea"
    # Tiene fin (cancelada): no está en vuelo, está cortada.
    assert tarea["peticion_en_vuelo"] is None
    cortada = tarea["peticion_cortada"]
    assert (cortada["peticion"], cortada["como_termino"], cortada["caracteres_entrada"]) == (
        2,
        "cancelada",
        1002,
    )
    assert cortada["hora_utc"] and cortada["retrollamadas"] == {"cb_antes": 1}
    assert d["enganches"]["no_respondidas_por_retrollamada"] == [
        {"peticion": 2, "como_termino": "cancelada", "cb_antes": 1}
    ]


def test_un_error_recuperado_en_una_tarea_resuelta_no_es_una_peticion_en_vuelo() -> None:
    peticiones = _peticion(1, "error", error="APIError") + _peticion(2, "tool_calls") + _peticion(3, "stop")
    d = kr.diagnosticar([INSTALADO, *_tarea("t_1", peticiones, 10), CIERRE], [])
    (tarea,) = d["tareas"]
    assert tarea["peticion_en_vuelo"] is None and tarea["peticion_cortada"] is None
    assert tarea["no_respondidas"] == 1 and tarea["ultima_peticion"]["peticion"] == 3
    assert kr.codigo_de(d) == kr.EXIT_OK


@pytest.mark.parametrize(
    ("error", "tope"),
    [
        ("Agent exceeded tool call budget (40 calls)", "tope de llamadas"),
        ("Agent exceeded turns budget (100 turns)", "tope de turnos"),
        ("Sandbox execution error: Connection error.", "el servidor del modelo dejó de responder"),
        ("Agent completed execution without calling submit_patch.", None),
        (None, None),
    ],
)
def test_el_tope_sale_del_mensaje_del_arnes(error: str | None, tope: str | None) -> None:
    assert kr.tope_de_tarea(error) == tope


def test_una_sesion_muerta_desde_fuera_deja_un_inicio_sin_fin() -> None:
    eventos = [
        INSTALADO,
        _e("tarea_inicio"),
        *_peticion(1, None),
        *_peticion(2, "tool_calls"),
        *_peticion(3, None),
    ]
    primero = {"hora_utc": "h1", "sesion_s": 10.0, "tarea": "t_1", "en_vuelo": [{"peticion": 1}]}
    ultimo = {"hora_utc": "h2", "sesion_s": 54.6, "tarea": "t_1", "en_vuelo": [{"peticion": 3}], "otro": 1}
    d = kr.diagnosticar(eventos, [primero, ultimo])
    assert d["sesion"]["veredicto"].startswith("muerta desde fuera") and d["sesion"]["cerrada"] is False
    assert kr.codigo_de(d) == kr.EXIT_MUERTA
    assert d["sesion"]["ultimo_latido"] == {
        "hora_utc": "h2",
        "sesion_s": 54.6,
        "tarea": "t_1",
        "en_vuelo": [{"peticion": 3}],
        "servidor_sano": None,
        "diff_en_curso": None,
    }
    (tarea,) = d["tareas"]
    assert tarea["terminada"] is False and tarea["diff_al_cierre"] is None
    # Hay dos inicios sin fin: en vuelo al morir estaba el último.
    assert tarea["peticion_en_vuelo"]["peticion"] == 3 and tarea["peticion_en_vuelo"]["segundos"] is None
    assert tarea["peticion_cortada"]["como_termino"] == "sin fin"
    assert d["peticiones"]["con_fin"] == 1 and d["peticiones"]["motivos"] == {"sin fin": 2, "tool_calls": 1}


def test_un_corte_del_notebook_dice_cual_y_la_tarea_caida_su_error() -> None:
    eventos = [
        INSTALADO,
        _e("tarea_inicio"),
        *_peticion(1, "error", error="InternalServerError"),
        _e("cb_fallo", llamada="id1"),
        _e("diff_cierre", error="RuntimeError: sin git"),
        _e("tarea_fin", clase="otro_error_sin_parche", error="Sandbox execution error: Connection error."),
        _e("corte", None, cortado_por="tareas"),
        _e("corte", None, cortado_por="servidor"),
        CIERRE,
    ]
    d = kr.diagnosticar(eventos, [])
    # Con dos cortes vale el último.
    assert (
        d["sesion"]["cortado_por"] == "servidor" and "servidor del modelo caído" in d["sesion"]["veredicto"]
    )
    assert kr.codigo_de(d) == kr.EXIT_REGISTRO  # una tarea corrida y ninguna petición respondida
    (tarea,) = d["tareas"]
    assert tarea["tope_que_corto"] == "el servidor del modelo dejó de responder"
    assert tarea["peticion_en_vuelo"] is None
    assert tarea["peticion_cortada"]["retrollamadas"] == {"cb_antes": 1, "cb_fallo": 1}
    assert tarea["diff_al_cierre"] == {"error": "RuntimeError: sin git"}
    otro = kr.diagnosticar([INSTALADO, _e("corte", None, cortado_por="fallo KeyError"), CIERRE], [])
    assert otro["sesion"]["veredicto"] == "cortada por el notebook: fallo KeyError" and otro["tareas"] == []
    assert kr.codigo_de(otro) == kr.EXIT_CORTADA


def test_dos_tareas_no_se_mezclan_ni_una_tarea_repetida_se_pisa() -> None:
    segunda = _tarea(
        "t_2", _peticion(3, "stop", "t_2"), 20, error="Agent exceeded tool call budget (40 calls)"
    )
    # Un evento con el nombre de otra tarea en medio de esta sesión no se le atribuye.
    segunda.insert(-1, _e("diff_cierre", "t_9", bytes=999, sha256="ajeno", archivos=[]))
    eventos = [
        INSTALADO,
        *_tarea("t_1", _peticion(1, "tool_calls") + _peticion(2, "stop"), 10),
        *segunda,
        *_tarea("t_1", _peticion(4, "tool_calls") + _peticion(5, "tool_calls") + _peticion(6, "stop"), 30),
        CIERRE,
    ]
    d = kr.diagnosticar(eventos, [])
    resumen = [
        (t["orden"], t["tarea"], t["veces_en_la_sesion"], t["peticiones"], t["diff_al_cierre"]["bytes"])
        for t in d["tareas"]
    ]
    assert resumen == [(1, "t_1", 2, 2, 10), (2, "t_2", 1, 1, 20), (3, "t_1", 2, 3, 30)]
    assert [t["diff_al_cierre"]["sha256"] for t in d["tareas"]] == ["sha-t_1-10", "sha-t_2-20", "sha-t_1-30"]
    assert [t["ultima_peticion"]["peticion"] for t in d["tareas"]] == [2, 3, 6]
    assert [t["tope_que_corto"] for t in d["tareas"]] == [None, "tope de llamadas", None]
    assert [t["fin_del_agente"]["parche_caracteres"] for t in d["tareas"]] == [10, 20, 30]


def _salida() -> tuple[str, str]:
    eventos = [INSTALADO, *_tarea("t_1", _peticion(1, "stop"), 10), CIERRE]
    registro = "\n".join(json.dumps(e) for e in eventos) + "\n"
    latido = json.dumps({"hora_utc": "h", "sesion_s": 1.0}) + "\n"
    return registro, latido


def test_el_registro_se_lee_de_una_carpeta_y_de_un_zip(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registro, latido = _salida()
    carpeta = tmp_path / "working"
    carpeta.mkdir()
    (carpeta / "registro_s.jsonl").write_text(registro, encoding="utf-8")
    (carpeta / "latido_s.jsonl").write_text(latido, encoding="utf-8")
    crudo = tmp_path / "crudo.zip"
    with zipfile.ZipFile(crudo, "w") as z:
        z.writestr("registro/registro_s.jsonl", registro)
        z.writestr("logs/registro_que_no_es.jsonl", "{}")
    de_carpeta, de_zip = kr.cargar_salida(carpeta), kr.cargar_salida(crudo)
    assert de_carpeta["eventos"] == de_zip["eventos"] and len(de_zip["eventos"]) == 10
    assert (de_carpeta["hay_latido"], de_zip["hay_latido"]) == (True, False)

    assert kr.main(["diagnosticar", "--salida", str(crudo)]) == kr.EXIT_OK
    informe = json.loads(capsys.readouterr().out)
    assert informe["sesion"]["veredicto"].startswith("completa") and informe["hay_latido"] is False


def test_diagnosticar_no_sale_con_0_si_la_sesion_murio_o_el_registro_no_es_fiable(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registro, _ = _salida()
    lineas = registro.splitlines()
    casos = {
        kr.EXIT_MUERTA: lineas[:-1],
        kr.EXIT_REGISTRO: lineas[1:],
        kr.EXIT_CORTADA: [*lineas[:-1], json.dumps(_e("corte", None, cortado_por="sesion")), lineas[-1]],
    }
    for codigo, contenido in casos.items():
        carpeta = tmp_path / f"caso_{codigo}"
        carpeta.mkdir()
        (carpeta / "registro_s.jsonl").write_text("\n".join(contenido) + "\n", encoding="utf-8")
        assert kr.main(["diagnosticar", "--salida", str(carpeta)]) == codigo
        capsys.readouterr()


def test_una_salida_sin_registro_es_una_entrada_invalida(tmp_path: Path) -> None:
    vacia = tmp_path / "vacia"
    vacia.mkdir()
    roto = tmp_path / "roto.zip"
    roto.write_bytes(b"no es un zip")
    for ruta in (vacia, roto, tmp_path / "no_existe"):
        with pytest.raises(kr.RegistroError):
            kr.cargar_salida(ruta)
        assert kr.main(["diagnosticar", "--salida", str(ruta)]) == kr.EXIT_ENTRADA


def _rescate(tmp_path: Path, registros: dict[str, list[str]]) -> Path:
    destino = tmp_path / "rescate"
    for slug, lineas in registros.items():
        carpeta = destino / "notebooks" / slug
        carpeta.mkdir(parents=True)
        (carpeta / "salida__registro_s.jsonl").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    (destino / "notebooks" / "sin-registro").mkdir(parents=True, exist_ok=True)
    return destino


def test_comprobar_corre_el_rescate_y_el_diagnostico_y_falla_si_falla_cualquiera(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from scripts import kaggle_rescate

    llamadas: list[list[str]] = []
    codigo_del_rescate = {"valor": 0}

    def rescate_falso(argv: list[str]) -> int:
        llamadas.append(argv)
        print(json.dumps({"descarga_incompleta": [1] * (2 if codigo_del_rescate["valor"] else 0)}))
        return codigo_del_rescate["valor"]

    monkeypatch.setattr(kaggle_rescate, "main", rescate_falso)
    sana = _salida()[0].splitlines()
    destino = _rescate(tmp_path, {"completa": sana, "muerta": sana[:-1]})

    # El rescate da 0 sobre una sesión muerta desde fuera: el diagnóstico es el que la ve.
    assert kr.main(["comprobar", "--rescate", str(destino)]) == kr.EXIT_MUERTA
    resumen = json.loads(capsys.readouterr().out)
    assert llamadas == [["--destino", str(destino), "--sin-red"]]
    assert resumen["rescate"] == {"codigo": 0, "faltantes": 0}
    assert {k: v["codigo"] for k, v in resumen["sesiones"].items()} == {
        "completa": 0,
        "muerta": kr.EXIT_MUERTA,
    }

    assert kr.main(["comprobar", "--rescate", str(destino), "--notebook", "completa"]) == kr.EXIT_OK
    capsys.readouterr()
    codigo_del_rescate["valor"] = 4
    assert kr.main(["comprobar", "--rescate", str(destino), "--notebook", "completa"]) == 4
    assert json.loads(capsys.readouterr().out)["rescate"] == {"codigo": 4, "faltantes": 2}
    assert kr.main(["comprobar", "--rescate", str(destino), "--notebook", "sin-registro"]) == kr.EXIT_ENTRADA
