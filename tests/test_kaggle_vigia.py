"""Tests de `scripts/kaggle_vigia.py` y del registro de hallazgos. Respuestas fijas: sin red ni token real."""

from __future__ import annotations

import copy
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from scripts import kaggle_rescate
from scripts import kaggle_vigia as kv

TOKEN = "tok-secreto-de-prueba-123"
AHORA = datetime(2026, 10, 9, 14, 0, tzinfo=UTC)
HALLAZGOS_REALES = (
    Path(__file__).resolve().parent.parent / "experiments" / "gemma_developer_agent" / "hallazgos.json"
)


def envio(ref: int, estado: str, nota: str = "") -> dict[str, Any]:
    return {"ref": ref, "status": estado, "publicScore": nota, "submittedByRef": "yo"}


def guardar(
    rescates: Path, nombre: str, envios: list[dict[str, Any]], notebooks: list[dict[str, Any]] | None = None
) -> Path:
    carpeta = rescates / nombre
    carpeta.mkdir(parents=True)
    (carpeta / "envios.json").write_text(json.dumps(envios), encoding="utf-8")
    (carpeta / "usuario.txt").write_text("yo", encoding="utf-8")
    if notebooks is not None:
        (carpeta / "notebooks.json").write_text(json.dumps(notebooks), encoding="utf-8")
    return carpeta


def api_falsa(
    envios: list[dict[str, Any]], notebooks: list[dict[str, Any]] | None = None, estado: str = "complete"
):
    peticiones: list[str] = []

    def pedir(ruta: str, token: str) -> bytes:
        peticiones.append(ruta)
        assert token == TOKEN
        if ruta.startswith("competitions/submissions/list/"):
            return json.dumps(envios).encode()
        if ruta.startswith("kernels/list"):
            return json.dumps(notebooks or []).encode()
        if ruta.startswith("kernels/status"):
            return json.dumps({"status": estado}).encode()
        raise AssertionError(ruta)

    pedir.peticiones = peticiones  # type: ignore[attr-defined]
    return pedir


def correr(rescates: Path, pedir: Any, hallazgos: Path | None = None, **kw: Any) -> list[str]:
    return kv.vigia(
        raiz_repo=rescates.parent,
        entorno={"KAGGLE_API_TOKEN": TOKEN},
        pedir=pedir,
        ahora=AHORA,
        ruta_hallazgos=hallazgos or rescates.parent / "no_hay_hallazgos.json",
        principal=rescates.parent,
        rescates=rescates,
        **kw,
    )


# ---------------------------------------------------------------------------
# Comparar
# ---------------------------------------------------------------------------


def test_error_que_pasa_a_complete_con_nota_se_marca_sin_procesar(tmp_path: Path) -> None:
    guardar(tmp_path / "r", "2026-10-08T2231Z", [envio(1, "error"), envio(2, "complete", "0.08")])
    lineas = correr(tmp_path / "r", api_falsa([envio(1, "complete", "0.13"), envio(2, "complete", "0.08")]))
    cambio = [x for x in lineas if x.startswith("envío 1 ")]
    assert cambio == ["envío 1 pasó de `error` a `complete` con nota 0,13: sin procesar"]
    assert not any(x.startswith("envío 2 ") for x in lineas)  # el que no cambió no se nombra


def test_con_las_dos_lecturas_iguales_no_se_imprime_ningun_envio(tmp_path: Path) -> None:
    envios = [envio(1, "error"), envio(2, "complete", "0.08")]
    guardar(tmp_path / "r", "2026-10-08T2231Z", envios)
    lineas = correr(tmp_path / "r", api_falsa(copy.deepcopy(envios)))
    assert not any(x.startswith("envío ") and "sin procesar" in x for x in lineas)
    assert "envíos sin cambios desde esa lectura" in lineas
    assert not any("sin procesar" in x for x in lineas)


def test_la_nota_cambia_sin_cambiar_el_estado() -> None:
    lineas = kv.comparar_envios({7: ("complete", 0.08)}, {7: ("complete", 0.13)})
    assert lineas == ["envío 7 sigue `complete` pero su nota pasó de 0,08 a 0,13: sin procesar"]
    assert kv.comparar_envios({7: ("complete", 0.13)}, {7: ("complete", 0.130)}) == []


def test_un_envio_nuevo_que_no_estaba_en_la_lectura_guardada() -> None:
    lineas = kv.comparar_envios({1: ("complete", 0.05)}, {1: ("complete", 0.05), 2: ("pending", None)})
    assert len(lineas) == 1 and lineas[0].startswith("envío 2 es nuevo") and "sin procesar" in lineas[0]


def test_un_envio_que_desaparece_de_la_api() -> None:
    lineas = kv.comparar_envios({1: ("complete", 0.05), 2: ("error", None)}, {1: ("complete", 0.05)})
    assert len(lineas) == 1 and lineas[0].startswith("envío 2 estaba") and "ya no lo devuelve" in lineas[0]


def test_la_lectura_guardada_mas_nueva_que_la_api_tambien_avisa() -> None:
    # La lectura guardada dice `complete`; la API ahora dice `error`: es un cambio, no «todo procesado».
    lineas = kv.comparar_envios({1: ("complete", 0.13)}, {1: ("error", None)})
    assert lineas == ["envío 1 pasó de `complete` a `error` con nota sin nota: sin procesar"]


def test_notebooks_nuevos_o_con_otra_ultima_ejecucion() -> None:
    guardados = [{"ref": "yo/a", "lastRunTime": "t1"}, {"ref": "yo/b", "lastRunTime": "t1"}]
    actuales = [
        {"ref": "yo/a", "lastRunTime": "t1"},
        {"ref": "yo/b", "lastRunTime": "t2"},
        {"ref": "yo/c", "lastRunTime": "t3"},
    ]
    assert kv.notebooks_cambiados(guardados, actuales) == ["yo/b", "yo/c"]
    assert kv.notebooks_cambiados(guardados, guardados) == []


def test_un_notebook_terminado_y_no_rescatado_se_dice(tmp_path: Path) -> None:
    nb = [{"ref": "yo/it-8", "lastRunTime": "t1"}]
    guardar(tmp_path / "r", "2026-10-08T2231Z", [envio(1, "complete", "0.05")], nb)
    nuevo = [{"ref": "yo/it-8", "lastRunTime": "t2"}]
    pedir = api_falsa([envio(1, "complete", "0.05")], nuevo, estado="complete")
    lineas = correr(tmp_path / "r", pedir)
    assert "notebook yo/it-8 terminó y no está rescatado (corrió después del último rescate)" in lineas
    sin_cambio = correr(tmp_path / "r", api_falsa([envio(1, "complete", "0.05")], nb))
    assert not any(x.startswith("notebook ") for x in sin_cambio)


# ---------------------------------------------------------------------------
# Cuál es la última lectura guardada
# ---------------------------------------------------------------------------


def test_gana_la_marca_de_tiempo_mas_alta_y_no_el_orden_alfabetico_del_resto(tmp_path: Path) -> None:
    guardar(tmp_path, "2026-10-08T2231Z", [envio(1, "error")])
    nueva = guardar(tmp_path, "2026-10-09T1342Z", [envio(1, "complete", "0.13")])
    guardar(tmp_path, "2026-10-06T185453Z", [envio(1, "error")])  # seis dígitos de hora
    assert kv.ultima_lectura(tmp_path) == (nueva, datetime(2026, 10, 9, 13, 42, tzinfo=UTC))


def test_la_carpeta_anidada_con_su_propia_marca_cuenta(tmp_path: Path) -> None:
    guardar(tmp_path, "2026-10-08T2231Z", [envio(1, "error")])
    interna = guardar(tmp_path / "2026-10-09T1342Z", "2026-10-09T1342Z", [envio(1, "complete", "0.13")])
    assert kv.ultima_lectura(tmp_path) is not None
    assert kv.ultima_lectura(tmp_path)[0] == interna  # type: ignore[index]


def test_dos_rescates_con_la_misma_marca_gana_el_modificado_despues(tmp_path: Path) -> None:
    uno = guardar(tmp_path / "a", "2026-10-09T1342Z", [envio(1, "error")])
    dos = guardar(tmp_path / "b", "2026-10-09T1342Z", [envio(1, "complete", "0.13")])
    os.utime(uno / "envios.json", (time.time() - 100, time.time() - 100))
    assert kv.ultima_lectura(tmp_path)[0] == dos  # type: ignore[index]
    os.utime(dos / "envios.json", (time.time() - 500, time.time() - 500))
    assert kv.ultima_lectura(tmp_path)[0] == uno  # type: ignore[index]


def test_una_carpeta_sin_marca_de_tiempo_no_se_considera(tmp_path: Path) -> None:
    guardar(tmp_path, "copia-de-seguridad", [envio(1, "complete", "0.99")])
    assert kv.ultima_lectura(tmp_path) is None


def test_sin_lectura_guardada_lo_dice_y_no_compara(tmp_path: Path) -> None:
    (tmp_path / "r").mkdir()
    lineas = correr(tmp_path / "r", api_falsa([envio(1, "complete", "0.1")]))
    assert any("no hay lectura guardada" in x for x in lineas)
    assert not any("sin procesar" in x for x in lineas)


def test_una_lectura_guardada_ilegible_no_dice_todo_procesado(tmp_path: Path) -> None:
    carpeta = guardar(tmp_path / "r", "2026-10-08T2231Z", [envio(1, "error")])
    (carpeta / "envios.json").write_text("{no es json", encoding="utf-8")
    lineas = correr(tmp_path / "r", api_falsa([envio(1, "complete", "0.13")]))
    assert any(x.startswith("no pude leer Kaggle") for x in lineas)
    assert "envíos sin cambios desde esa lectura" not in lineas


def test_una_lectura_vieja_se_avisa(tmp_path: Path) -> None:
    guardar(tmp_path / "r", "2026-10-06T1923Z", [envio(1, "complete", "0.05")])
    lineas = correr(tmp_path / "r", api_falsa([envio(1, "complete", "0.05")]))
    assert any("más de un día" in x for x in lineas)


# ---------------------------------------------------------------------------
# Sin token, sin red, ilegible, tope, y el token nunca sale
# ---------------------------------------------------------------------------


def test_sin_token_lo_dice_en_una_linea(tmp_path: Path) -> None:
    guardar(tmp_path / "r", "2026-10-08T2231Z", [envio(1, "error")])

    def no_debe_llamarse(ruta: str, token: str) -> bytes:
        raise AssertionError("sin token no se consulta")

    lineas = kv.vigia(
        raiz_repo=tmp_path,
        entorno={},
        pedir=no_debe_llamarse,
        ahora=AHORA,
        ruta_hallazgos=tmp_path / "x.json",
        principal=tmp_path,
        rescates=tmp_path / "r",
    )
    assert lineas[0] == "VIGÍA KAGGLE"
    assert [x for x in lineas if "token" in x] == [
        "sin token de Kaggle (KAGGLE_API_TOKEN): no consulté la API"
    ]


def test_el_token_tambien_se_lee_del_env_del_arbol_principal(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(f"OTRA=1\nKAGGLE_API_TOKEN='{TOKEN}'\n", encoding="utf-8")
    assert kv.leer_token({}, [tmp_path / "no_existe", tmp_path]) == TOKEN
    assert kv.leer_token({"KAGGLE_API_TOKEN": "de-entorno"}, [tmp_path]) == "de-entorno"
    assert kv.leer_token({}, [tmp_path / "no_existe"]) == ""


def test_sin_red_sale_con_una_linea_y_sin_lanzar(tmp_path: Path) -> None:
    guardar(tmp_path / "r", "2026-10-08T2231Z", [envio(1, "error")])

    def sin_red(ruta: str, token: str) -> bytes:
        raise kaggle_rescate.RescateError("Sin respuesta de Kaggle: URLError")

    lineas = correr(tmp_path / "r", sin_red)
    assert any(x.startswith("no pude leer Kaggle") and "URLError" in x for x in lineas)
    assert not any("sin procesar" in x for x in lineas)


@pytest.mark.parametrize("cuerpo", [b"<html>502</html>", b"", b"[1, 2]", b'[{"sin_ref": 1}]', b'{"a": 1}'])
def test_respuesta_ilegible_o_con_otra_forma_no_estorba(tmp_path: Path, cuerpo: bytes) -> None:
    guardar(tmp_path / "r", "2026-10-08T2231Z", [envio(1, "error")])
    lineas = correr(tmp_path / "r", lambda ruta, token: cuerpo)
    assert any(x.startswith("no pude leer Kaggle") for x in lineas)
    assert "envíos sin cambios desde esa lectura" not in lineas


def test_el_token_no_se_imprime_ni_en_un_mensaje_de_error(tmp_path: Path) -> None:
    guardar(tmp_path / "r", "2026-10-08T2231Z", [envio(1, "error")])

    def revienta_con_el_token(ruta: str, token: str) -> bytes:
        raise RuntimeError(f"fallo con {token} dentro")

    lineas = correr(tmp_path / "r", revienta_con_el_token)
    assert any("no pude leer Kaggle" in x for x in lineas)
    assert TOKEN not in "\n".join(lineas)
    assert kv.tapar(f"a {TOKEN} b", TOKEN) == "a *** b"


def test_el_token_no_sale_por_main(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("KAGGLE_API_TOKEN", TOKEN)
    monkeypatch.setattr(
        kv,
        "pedir_con_tope_de_socket",
        lambda ruta, token, segundos=8.0: (_ for _ in ()).throw(RuntimeError(token)),
    )
    guardar(tmp_path / "r", "2026-10-08T2231Z", [envio(1, "error")])
    assert kv.main(["--rescates", str(tmp_path / "r")]) == 0
    salida = capsys.readouterr()
    assert TOKEN not in salida.out + salida.err
    assert "VIGÍA KAGGLE" in salida.out


def test_pasado_el_tope_de_tiempo_lo_dice_y_vuelve(tmp_path: Path) -> None:
    guardar(tmp_path / "r", "2026-10-08T2231Z", [envio(1, "error")])

    def colgada(ruta: str, token: str) -> bytes:
        time.sleep(5)
        return b"[]"

    t0 = time.monotonic()
    lineas = correr(tmp_path / "r", colgada, tope_s=0.3)
    assert time.monotonic() - t0 < 2.5
    assert any("Kaggle no respondió en 0.3 s" in x for x in lineas)
    assert not any("sin procesar" in x for x in lineas)


def test_el_gancho_esta_declarado_con_un_tope_mayor_que_el_del_guion() -> None:
    config = json.loads(
        (Path(__file__).resolve().parent.parent / ".claude" / "settings.json").read_text(encoding="utf-8")
    )
    ganchos = [h for g in config["hooks"]["SessionStart"] for h in g["hooks"]]
    vigia = [h for h in ganchos if "kaggle_vigia.py" in h["command"]]
    assert len(vigia) == 1
    assert vigia[0]["timeout"] > kv.TOPE_TOTAL_S
    assert any("session_guard.py" in h["command"] for h in ganchos)  # el otro gancho sigue


def test_usa_la_funcion_pedir_del_rescate_con_su_defensa_del_token(monkeypatch: pytest.MonkeyPatch) -> None:
    vistos: list[tuple[str, str, int]] = []

    def falso(ruta: str, token: str) -> bytes:
        vistos.append((ruta, token, kaggle_rescate.TOPE_S))
        return b"[]"

    monkeypatch.setattr(kaggle_rescate, "pedir", falso)
    original = kaggle_rescate.TOPE_S
    kv.pedir_con_tope_de_socket("x", "t", 3.0)
    assert vistos == [("x", "t", 3)]
    assert original == kaggle_rescate.TOPE_S  # se restaura


# ---------------------------------------------------------------------------
# Hallazgos
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


def test_el_registro_real_es_valido_y_esta_sembrado() -> None:
    datos = json.loads(HALLAZGOS_REALES.read_text(encoding="utf-8"))
    assert kv.validar_hallazgos(datos) == []
    estados = {h["id"]: h["estado"] for h in datos["hallazgos"]}
    assert estados["repeticiones_identicas"] == "decidido"
    assert estados["busqueda_por_similitud_vacia"] == "decidido"
    assert estados["subagente_sin_resolver"] == "decidido"
    assert estados["reproductor_antes_de_editar"] == "descartado"
    assert estados["guion_mapa_al_inicio"] == "descartado"
    for medido in (
        "argumento_mal_formado",
        "salida_truncada_por_la_cabeza",
        "aviso_de_presupuesto_en_la_llamada_30",
        "ruido_entre_dos_envios_del_mismo_zip",
    ):
        assert estados[medido] == "medido"
    assert len(estados) >= 9


def test_el_registro_no_lleva_datos_de_la_competencia() -> None:
    texto = HALLAZGOS_REALES.read_text(encoding="utf-8")
    assert not kv.PROHIBIDO_EN_HALLAZGOS.search(texto)
    problemas = kv.validar_hallazgos(registro_minimo(que_se_midio="falla en tarea_1234 de github.com/x/y"))
    assert any("identificador" in p for p in problemas)


@pytest.mark.parametrize(
    ("cambios", "fragmento"),
    [
        ({"estado": "inventado"}, "estado desconocido"),
        ({"estado": "decidido"}, "exige decision"),
        ({"estado": "descartado", "por_que_sigue_abierto": None}, "motivo_descarte"),
        ({"por_que_sigue_abierto": None}, "sin decisión"),
        ({"vueltas_medido": [5, 3]}, "vueltas_medido"),
        ({"vueltas_medido": []}, "vueltas_medido"),
        ({"primera_vuelta": 4}, "primera_vuelta"),
        ({"primera_fecha": "05/10/2026"}, "primera_fecha"),
        ({"id": "Mal Id"}, "id"),
        ({"que_se_midio": ""}, "que_se_midio"),
        ({"decision": {"texto": "x"}}, "solo `decidido`"),
    ],
)
def test_el_formato_rechaza(cambios: dict[str, Any], fragmento: str) -> None:
    problemas = kv.validar_hallazgos(registro_minimo(**cambios))
    assert any(fragmento in p for p in problemas), problemas


def test_el_formato_acepta_un_registro_correcto_y_rechaza_ids_repetidos() -> None:
    assert kv.validar_hallazgos(registro_minimo()) == []
    doble = registro_minimo()
    doble["hallazgos"].append(copy.deepcopy(doble["hallazgos"][0]))
    assert any("repetido" in p for p in kv.validar_hallazgos(doble))
    assert kv.validar_hallazgos([]) and kv.validar_hallazgos({"version": 2, "hallazgos": []})


def test_el_vigia_imprime_los_medidos_con_mas_de_una_vuelta(tmp_path: Path) -> None:
    fila_decidida = registro_minimo(
        id="dos",
        estado="decidido",
        decision={"texto": "se quita", "quien": "concilio", "vuelta": 5, "fecha": "2026-10-09"},
        por_que_sigue_abierto=None,
    )["hallazgos"][0]
    una_vuelta = registro_minimo(id="tres", vueltas_medido=[5], primera_vuelta=5, por_que_sigue_abierto=None)[
        "hallazgos"
    ][0]
    datos = registro_minimo()
    datos["hallazgos"] += [fila_decidida, una_vuelta]
    ruta = tmp_path / "h.json"
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    lineas = kv.hallazgos_sin_decision(ruta)
    assert lineas == ["hallazgo «uno» medido en 2 vueltas (3, 5) y sigue en `medido`: falta decidir"]


def test_el_vigia_imprime_los_hallazgos_aunque_no_haya_token(tmp_path: Path) -> None:
    ruta = tmp_path / "h.json"
    ruta.write_text(json.dumps(registro_minimo()), encoding="utf-8")
    lineas = kv.vigia(
        raiz_repo=tmp_path,
        entorno={},
        ahora=AHORA,
        ruta_hallazgos=ruta,
        principal=tmp_path,
        rescates=tmp_path,
    )
    assert any(x.startswith("hallazgo «uno»") for x in lineas)


def test_con_el_registro_real_el_vigia_nombra_los_que_siguen_en_medido() -> None:
    lineas = kv.hallazgos_sin_decision(HALLAZGOS_REALES)
    nombres = " ".join(lineas)
    for esperado in (
        "argumento_mal_formado",
        "aviso_de_presupuesto_en_la_llamada_30",
        "ruido_entre_dos_envios",
    ):
        assert esperado in nombres
    assert "repeticiones_identicas" not in nombres  # decidido
    assert "salida_truncada_por_la_cabeza" not in nombres  # una sola vuelta


def test_un_registro_ilegible_se_dice(tmp_path: Path) -> None:
    ruta = tmp_path / "h.json"
    ruta.write_text("{roto", encoding="utf-8")
    assert "no pude leer el registro de hallazgos" in kv.hallazgos_sin_decision(ruta)[0]
    assert "no pude leer" in kv.hallazgos_sin_decision(tmp_path / "no_existe.json")[0]
