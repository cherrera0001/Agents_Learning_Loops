"""Pruebas del seguimiento #179: vigía (cambios con hora, envíos sin terminar), registro y envíos.

Respuestas fijas: sin red, sin token real y sin identificadores de tareas de la competencia.
"""

from __future__ import annotations

import copy
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from scripts import kaggle_cuenta_llamadas as kc
from scripts import kaggle_registro as kr
from scripts import kaggle_vigia as kv
from scripts.kaggle_submission import SubmissionRecord

TOKEN = "tok-secreto-de-prueba-123"
AHORA = datetime(2026, 10, 9, 14, 0, tzinfo=UTC)
RAIZ = Path(__file__).resolve().parent.parent
REGISTRO_DE_ENVIOS = RAIZ / "experiments" / "gemma_developer_agent" / "submissions" / "registry.json"


def envio(ref: int, estado: str, nota: str = "", fecha: str = "2026-10-07T00:26:13.337Z") -> dict[str, Any]:
    return {"ref": ref, "status": estado, "publicScore": nota, "submittedByRef": "yo", "date": fecha}


def guardar(rescates: Path, nombre: str, envios: list[dict[str, Any]], completo: bool = True) -> Path:
    carpeta = rescates / nombre
    carpeta.mkdir(parents=True)
    (carpeta / "envios.json").write_text(json.dumps(envios), encoding="utf-8")
    (carpeta / "usuario.txt").write_text("yo", encoding="utf-8")
    if completo:
        (carpeta / "tabla_publica.zip").write_bytes(b"PK")
    return carpeta


def api(envios: list[dict[str, Any]]) -> Any:
    peticiones: list[str] = []

    def pedir(ruta: str, token: str) -> bytes:
        peticiones.append(ruta)
        assert token == TOKEN
        if ruta.startswith("competitions/submissions/list/"):
            return json.dumps(envios).encode()
        raise AssertionError(ruta)  # el vigía solo pide la lista de envíos aquí: no hay notebooks guardados

    pedir.peticiones = peticiones  # type: ignore[attr-defined]
    return pedir


def correr(rescates: Path, pedir: Any, ahora: datetime = AHORA) -> list[str]:
    return kv.vigia(
        raiz_repo=rescates.parent,
        entorno={"KAGGLE_API_TOKEN": TOKEN},
        pedir=pedir,
        ahora=ahora,
        ruta_hallazgos=rescates.parent / "no_hay_hallazgos.json",
        principal=rescates.parent,
        rescates=rescates,
    )


def cambios_guardados(rescates: Path) -> list[dict[str, Any]]:
    archivo = rescates / kv.ARCHIVO_DE_CAMBIOS
    if not archivo.is_file():
        return []
    return [json.loads(x) for x in archivo.read_text(encoding="utf-8").splitlines()]


# ---------------------------------------------------------------------------
# Punto 16: cada cambio de estado, con la hora de las dos lecturas que lo acotan
# ---------------------------------------------------------------------------


def test_un_cambio_de_estado_queda_con_la_hora_del_rescate_y_la_de_la_lectura(tmp_path: Path) -> None:
    r = tmp_path / "r"
    guardar(r, "2026-10-08T2113Z", [envio(1, "error"), envio(2, "complete", "0.08")])
    correr(r, api([envio(1, "complete", "0.13"), envio(2, "complete", "0.08")]))
    (cambio,) = cambios_guardados(r)
    assert cambio == {
        "ref": 1,
        "antes": {"estado": "error", "nota": None},
        "ahora": {"estado": "complete", "nota": 0.13},
        "lectura_anterior_utc": "2026-10-08T21:13:00Z",
        "lectura_anterior_de": "rescate",
        "lectura_utc": "2026-10-09T14:00:00Z",
    }


def test_la_segunda_lectura_se_acota_con_la_primera_del_vigia_y_no_se_repite(tmp_path: Path) -> None:
    r = tmp_path / "r"
    guardar(r, "2026-10-08T2113Z", [envio(1, "pending")])
    correr(r, api([envio(1, "error")]), AHORA)
    correr(r, api([envio(1, "complete", "0.13")]), AHORA + timedelta(hours=2))
    primero, segundo = cambios_guardados(r)
    assert (primero["antes"]["estado"], primero["ahora"]["estado"]) == ("pending", "error")
    assert primero["lectura_anterior_de"] == "rescate"
    assert (segundo["antes"]["estado"], segundo["ahora"]["estado"]) == ("error", "complete")
    # La segunda se acota con la primera lectura del vigía (2 h), no con el rescate (de hace 17 h).
    assert segundo["lectura_anterior_de"] == "vigia"
    assert segundo["lectura_anterior_utc"] == "2026-10-09T14:00:00Z"
    assert segundo["lectura_utc"] == "2026-10-09T16:00:00Z"
    # Una tercera lectura igual no anota nada nuevo.
    correr(r, api([envio(1, "complete", "0.13")]), AHORA + timedelta(hours=3))
    assert len(cambios_guardados(r)) == 2


def test_sin_cambios_no_se_anota_nada_pero_si_la_lectura(tmp_path: Path) -> None:
    r = tmp_path / "r"
    guardar(r, "2026-10-08T2113Z", [envio(1, "complete", "0.08")])
    correr(r, api([envio(1, "complete", "0.08")]))
    assert cambios_guardados(r) == []
    assert (r / kv.ARCHIVO_DE_LECTURA).is_file()


def test_una_lectura_del_vigia_ilegible_o_futura_no_se_usa(tmp_path: Path) -> None:
    r = tmp_path / "r"
    guardar(r, "2026-10-08T2113Z", [envio(1, "pending")])
    for texto in (
        "no json",
        json.dumps({"leido_utc": "2099-01-01T00:00:00Z", "envios": {"1": ["error", None]}}),
    ):
        (r / kv.ARCHIVO_DE_LECTURA).write_text(texto, encoding="utf-8")
        (r / kv.ARCHIVO_DE_CAMBIOS).unlink(missing_ok=True)
        correr(r, api([envio(1, "complete", "0.13")]))
        (cambio,) = cambios_guardados(r)
        assert cambio["lectura_anterior_de"] == "rescate" and cambio["antes"]["estado"] == "pending"


def test_un_envio_nuevo_o_que_desaparece_tambien_se_anota(tmp_path: Path) -> None:
    r = tmp_path / "r"
    guardar(r, "2026-10-08T2113Z", [envio(1, "complete", "0.08")])
    correr(r, api([envio(2, "pending")]))
    por_ref = {c["ref"]: c for c in cambios_guardados(r)}
    assert por_ref[1]["ahora"] is None and por_ref[2]["antes"] is None


def test_si_no_puede_escribir_lo_dice_y_no_lanza(tmp_path: Path) -> None:
    r = tmp_path / "r"
    guardar(r, "2026-10-08T2113Z", [envio(1, "error")])
    (r / kv.ARCHIVO_DE_CAMBIOS).mkdir()  # un directorio donde iría el archivo: abrirlo para anexar falla
    lineas = correr(r, api([envio(1, "complete", "0.13")]))
    assert any("no pude guardar la lectura del vigía" in x for x in lineas)
    assert any(x.startswith("envío 1 pasó de `error` a `complete`") for x in lineas)


def test_el_vigia_solo_pide_lecturas_y_no_imprime_el_token(tmp_path: Path) -> None:
    r = tmp_path / "r"
    guardar(r, "2026-10-08T2113Z", [envio(1, "error")])
    pedir = api([envio(1, "pending")])
    lineas = correr(r, pedir)
    assert pedir.peticiones == ["competitions/submissions/list/gemma-4-developer-agent?page=1"]
    assert TOKEN not in "\n".join(lineas) and TOKEN not in "".join(
        p.read_text(encoding="utf-8") for p in r.glob("vigia_*")
    )


# ---------------------------------------------------------------------------
# Punto 17: avisa de un envío sin terminar
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("estado", ["pending", "queued", "running", "PENDING"])
def test_un_envio_sin_terminar_se_avisa_con_su_fecha(tmp_path: Path, estado: str) -> None:
    r = tmp_path / "r"
    guardar(r, "2026-10-08T2113Z", [envio(7, "complete", "0.08")])
    lineas = correr(r, api([envio(7, "complete", "0.08"), envio(8, estado, fecha="2026-10-09T13:00:00Z")]))
    (aviso,) = [x for x in lineas if "SIN TERMINAR" in x]
    assert "HAY 1 ENVÍOS SIN TERMINAR" in aviso and f"8 `{estado}` (enviado 2026-10-09T13:00:00Z)" in aviso
    assert "límite de envíos pendientes" in aviso and "7 `complete`" not in aviso


def test_con_los_envios_terminados_no_hay_aviso(tmp_path: Path) -> None:
    r = tmp_path / "r"
    guardar(r, "2026-10-08T2113Z", [envio(1, "error"), envio(2, "complete", "0.08")])
    lineas = correr(r, api([envio(1, "error"), envio(2, "COMPLETE", "0.08")]))
    assert not any("SIN TERMINAR" in x for x in lineas)


def test_envios_sin_terminar_con_una_forma_inesperada_da_lista_vacia() -> None:
    assert kv.envios_sin_terminar({"a": 1}) == [] and kv.envios_sin_terminar([1, {"sin_ref": 1}]) == []
    assert kv.envios_sin_terminar([{"ref": 3, "status": "pending"}]) == [(3, "pending", "sin fecha")]


# ---------------------------------------------------------------------------
# Puntos 2, 3 y 6: el validador de hallazgos y el aviso de rescate incompleto
# ---------------------------------------------------------------------------


def registro_minimo(**cambios: Any) -> dict[str, Any]:
    fila = {
        "id": "uno",
        "que_se_midio": "algo, en conteos",
        "primera_vuelta": 3,
        "primera_fecha": "2026-10-05",
        "vueltas_medido": [3, 5],
        "estado": "medido",
        "decision": None,
        "motivo_descarte": None,
        "por_que_sigue_abierto": "falta decidir",
    }
    fila.update(cambios)
    return {"version": 1, "hallazgos": [fila]}


def test_la_lista_de_estados_del_archivo_se_compara_con_los_validos() -> None:
    bien = registro_minimo()
    bien["estados"] = list(kv.ESTADOS)
    assert kv.validar_hallazgos(bien) == []
    for estados in (["medido", "inventado"], "medido"):
        mal = registro_minimo()
        mal["estados"] = estados
        assert any("estados" in p for p in kv.validar_hallazgos(mal)), estados


def test_una_decision_anterior_a_la_primera_fecha_se_rechaza() -> None:
    decision = {"texto": "se quita", "quien": "concilio", "vuelta": 5, "fecha": "2026-10-04"}
    problemas = kv.validar_hallazgos(
        registro_minimo(estado="decidido", decision=decision, por_que_sigue_abierto=None),
        hoy=date(2026, 10, 9),
    )
    assert any("anterior a la `primera_fecha`" in p for p in problemas), problemas
    decision["fecha"] = "2026-10-05"  # el mismo día vale
    assert (
        kv.validar_hallazgos(
            registro_minimo(estado="decidido", decision=decision, por_que_sigue_abierto=None),
            hoy=date(2026, 10, 9),
        )
        == []
    )


def test_el_registro_real_sigue_pasando_con_las_dos_comprobaciones_nuevas() -> None:
    ruta = RAIZ / "experiments" / "gemma_developer_agent" / "hallazgos.json"
    assert kv.validar_hallazgos(json.loads(ruta.read_text(encoding="utf-8")), hoy=date.today()) == []


def test_un_descartado_con_decision_buena_y_sin_motivo_se_rechaza() -> None:
    decision = {"texto": "vetado", "quien": "concilio", "vuelta": 5, "fecha": "2026-10-09"}
    sin_motivo = registro_minimo(
        estado="descartado", motivo_descarte=None, decision=decision, por_que_sigue_abierto=None
    )
    assert any("motivo_descarte" in p for p in kv.validar_hallazgos(sin_motivo, hoy=date(2026, 10, 9)))
    con_motivo = copy.deepcopy(sin_motivo)
    con_motivo["hallazgos"][0]["motivo_descarte"] = "no ayuda"
    assert kv.validar_hallazgos(con_motivo, hoy=date(2026, 10, 9)) == []


def test_las_dos_fronteras_del_aviso_de_rescate_incompleto(tmp_path: Path) -> None:
    r = tmp_path / "r"
    guardar(r, "2026-10-08T2000Z", [envio(1, "complete")])  # completo, es el elegido
    guardar(r, "2026-10-08T1959Z", [envio(1, "complete")], completo=False)  # un minuto antes: no avisa
    elegida = kv.marca_de(r / "2026-10-08T2000Z")
    assert kv.avisos_de_rescates(r, AHORA, elegida) == []
    guardar(r, "2026-10-08T2001Z", [envio(1, "complete")], completo=False)  # posterior: avisa
    assert [a for a in kv.avisos_de_rescates(r, AHORA, elegida) if "2026-10-08T2001Z" in a]
    # Misma marca que la elegida: avisa (>=). Una carpeta anidada con la misma marca.
    otra = tmp_path / "s"
    guardar(otra, "2026-10-08T2000Z", [envio(1, "complete")])
    (otra / "2026-10-08T2000Z" / "tabla_publica.zip").unlink()
    (otra / "2026-10-08T2000Z" / "notebooks.json").write_text(
        "[]", encoding="utf-8"
    )  # completo por notebooks
    guardar(otra, "2026-10-08T200000Z", [envio(1, "complete")], completo=False)  # mismo instante, sin tabla
    assert [a for a in kv.avisos_de_rescates(otra, AHORA, elegida) if "200000Z" in a]
    # Sin ningún rescate elegido, el incompleto avisa.
    sola = tmp_path / "t"
    guardar(sola, "2026-10-08T2000Z", [envio(1, "complete")], completo=False)
    assert [a for a in kv.avisos_de_rescates(sola, AHORA, None) if "incompleto" in a]


# ---------------------------------------------------------------------------
# Puntos 9 y 10: el registro sabe cuántas tareas se esperaban
# ---------------------------------------------------------------------------

ENGANCHES = {"peticiones": "instalado", "latido": "cada 30.0 s"}
T0 = 1_760_000_000.0


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


INSTALADO = _e("registro_instalado", None, T0, enganches=ENGANCHES)


def _cierre(hora: float) -> dict[str, Any]:
    return _e("cierre", None, hora, errores_del_registro=0, ultimo_error=None)


def _registro_de(tareas: int) -> list[dict[str, Any]]:
    cuerpo = [e for n in range(tareas) for e in _bien(f"t_{n}", T0 + 10 * (n + 1), n + 1)]
    return [INSTALADO, *cuerpo, _cierre(T0 + 10 * (tareas + 2))]


def test_un_registro_truncado_con_cierre_sale_con_0_sin_el_numero_y_con_4_con_el() -> None:
    truncado = _registro_de(3)  # se esperaban 5
    assert kr.codigo_de(kr.diagnosticar(truncado, [])) == kr.EXIT_OK  # el defecto del punto 9
    informe = kr.diagnosticar(truncado, [], tareas_esperadas=5)
    assert kr.codigo_de(informe) == kr.EXIT_REGISTRO
    assert any(
        "3 tareas empezadas y se esperaban 5" in p for p in informe["sesion"]["problemas_del_registro"]
    )
    assert kr.codigo_de(kr.diagnosticar(_registro_de(5), [], tareas_esperadas=5)) == kr.EXIT_OK


def test_la_orden_diagnosticar_acepta_tareas_esperadas_y_rechaza_uno_invalido(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    carpeta = tmp_path / "salida"
    carpeta.mkdir()
    (carpeta / "registro_p.jsonl").write_text(
        "\n".join(json.dumps(e) for e in _registro_de(3)), encoding="utf-8"
    )
    assert kr.main(["diagnosticar", "--salida", str(carpeta)]) == kr.EXIT_OK
    assert kr.main(["diagnosticar", "--salida", str(carpeta), "--tareas-esperadas", "3"]) == kr.EXIT_OK
    assert kr.main(["diagnosticar", "--salida", str(carpeta), "--tareas-esperadas", "4"]) == kr.EXIT_REGISTRO
    capsys.readouterr()
    for malo in ("0", "-2", "tres"):
        with pytest.raises(SystemExit) as salida:
            kr.main(["diagnosticar", "--salida", str(carpeta), "--tareas-esperadas", malo])
        assert salida.value.code == 2


def test_un_evento_tras_el_cierre_da_4_pero_el_diagnostico_sigue_diciendo_cortada() -> None:
    """Punto 10, descartado como cambio: el 4 es la respuesta prudente y el JSON conserva la causa."""
    eventos = [
        INSTALADO,
        *_bien("t_1", T0 + 10, 1),
        _e("corte", None, T0 + 30, cortado_por="tarea_colgada"),
        _cierre(T0 + 31),
        _e("peticion_fin", "t_1", T0 + 32, peticion=1, motivo="stop"),
    ]
    informe = kr.diagnosticar(eventos, [])
    assert kr.codigo_de(informe) == kr.EXIT_REGISTRO
    assert informe["sesion"]["estado"] == "cortada" and informe["sesion"]["cortado_por"] == "tarea_colgada"
    assert any("después del «cierre»" in p for p in informe["sesion"]["problemas_del_registro"])
    assert "cortada por el notebook" in informe["sesion"]["veredicto"]


# ---------------------------------------------------------------------------
# Punto 4: un rescate sin notebooks/ no es «no pude contar»
# ---------------------------------------------------------------------------


def test_un_rescate_sin_carpeta_notebooks_es_nada_que_contar_y_una_ruta_mala_sigue_siendo_entrada_invalida(
    tmp_path: Path,
) -> None:
    rescate = tmp_path / "2026-10-09T1342Z"
    rescate.mkdir()
    (rescate / "envios.json").write_text("[]", encoding="utf-8")
    assert kc.main(["--rescate", str(rescate)]) == kc.EXIT_NADA_QUE_CONTAR
    otra = tmp_path / "no_es_un_rescate"
    otra.mkdir()
    assert kc.main(["--rescate", str(otra)]) == kc.EXIT_ENTRADA
    assert kc.main(["--rescate", str(tmp_path / "no_existe")]) == kc.EXIT_ENTRADA


# ---------------------------------------------------------------------------
# Punto 15: los dos envíos del kit con razonamiento
# ---------------------------------------------------------------------------


def test_el_registro_de_envios_trae_los_dos_envios_con_razonamiento_y_su_advertencia() -> None:
    datos = json.loads(REGISTRO_DE_ENVIOS.read_text(encoding="utf-8"))
    filas = {s["submission_id"]: s for s in datos["submissions"]}
    assert len(filas) == len(datos["submissions"])  # ids únicos
    for fila in filas.values():
        SubmissionRecord(**fila)  # el esquema del registro
    a, b = filas["sub-005"], filas["sub-006"]
    assert (a["public_score"], b["public_score"]) == (0.08, 0.13)
    assert a["sha256"] == b["sha256"] and a["sha256"].startswith("65a02160")
    assert a["size_bytes"] == b["size_bytes"] == 3494
    assert (a["date"], b["date"]) == ("2026-10-07", "2026-10-07")
    assert a["status"] == b["status"] == "scored"
    assert "56895202" in a["notes"] and "56916129" in b["notes"]
    assert all("error" in x["notes"] and "ADVERTENCIA" in x["notes"] for x in (a, b))
    # Los envíos que ya estaban no cambian
    assert filas["sub-002"]["public_score"] == 0.06 and filas["sub-003"]["public_score"] == 0.05
