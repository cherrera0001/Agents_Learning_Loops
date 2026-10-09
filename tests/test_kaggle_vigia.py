"""Tests de `scripts/kaggle_vigia.py` y del registro de hallazgos. Respuestas fijas: sin red ni token real."""

from __future__ import annotations

import copy
import json
import os
import time
from datetime import UTC, date, datetime
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
    rescates: Path,
    nombre: str,
    envios: list[dict[str, Any]],
    notebooks: list[dict[str, Any]] | None = None,
    completo: bool = True,
) -> Path:
    carpeta = rescates / nombre
    carpeta.mkdir(parents=True)
    (carpeta / "envios.json").write_text(json.dumps(envios), encoding="utf-8")
    (carpeta / "usuario.txt").write_text("yo", encoding="utf-8")
    if completo:
        (carpeta / "tabla_publica.zip").write_bytes(b"PK")
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
    # dice cuál de las dos lecturas falló: la guardada, no Kaggle
    assert any(x.startswith("no pude leer la lectura guardada") for x in lineas)
    assert not any("no pude leer Kaggle" in x for x in lineas)
    assert "envíos sin cambios desde esa lectura" not in lineas


def test_una_lectura_vieja_se_avisa_solo_pasadas_24_horas(tmp_path: Path) -> None:
    guardar(tmp_path / "r", "2026-10-06T1923Z", [envio(1, "complete", "0.05")])
    lineas = correr(tmp_path / "r", api_falsa([envio(1, "complete", "0.05")]))
    assert any("más de 24 h" in x for x in lineas)
    justo = datetime(2026, 10, 6, 19, 23, tzinfo=UTC)
    sin_aviso = kv.consultar(
        tmp_path / "r" / "2026-10-06T1923Z", justo, TOKEN, api_falsa([envio(1, "complete", "0.05")]),
        datetime(2026, 10, 7, 19, 23, tzinfo=UTC), time.monotonic() + 5,
    )  # fmt: skip
    assert "hace 24.0 h)" in sin_aviso[0]  # exactamente 24 h: todavía no es «más de»
    con_aviso = kv.consultar(
        tmp_path / "r" / "2026-10-06T1923Z", justo, TOKEN, api_falsa([envio(1, "complete", "0.05")]),
        datetime(2026, 10, 7, 19, 24, tzinfo=UTC), time.monotonic() + 5,
    )  # fmt: skip
    assert "más de 24 h" in con_aviso[0]


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
    # peor caso: una llamada a git + el tope del guion; el gancho no puede matar al vigía antes de que hable
    assert vigia[0]["timeout"] >= kv.TOPE_TOTAL_S + kv.TOPE_GIT_S + 10
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
    filas = json.loads(HALLAZGOS_REALES.read_text(encoding="utf-8"))["hallazgos"]
    assert not kv.PROHIBIDO_EN_HALLAZGOS.search(json.dumps(filas, ensure_ascii=False))
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


# ---------------------------------------------------------------------------
# Revisión: el token con salto de línea, rescates que no sirven, avisos que no deben callarse
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "token",
    ["KGAT_abc123\ndef456", '{"username":"yo",\n"key":"abc123"}', "con espacio", "tóken", "a\x00b", "a\rb"],
)
def test_un_token_mal_formado_no_se_usa_ni_se_imprime(tmp_path: Path, token: str) -> None:
    guardar(tmp_path / "r", "2026-10-08T2231Z", [envio(1, "error")])

    def no_debe_llamarse(ruta: str, tk: str) -> bytes:
        raise AssertionError("un token mal formado no se manda")

    lineas = kv.vigia(
        raiz_repo=tmp_path,
        entorno={"KAGGLE_API_TOKEN": token},
        pedir=no_debe_llamarse,
        ahora=AHORA,
        ruta_hallazgos=tmp_path / "x.json",
        principal=tmp_path,
        rescates=tmp_path / "r",
    )
    texto = "\n".join(lineas)
    assert "token mal formado" in texto and "no consulté" in texto
    for trozo in ("abc123", "def456", "KGAT", "username"):
        assert trozo not in texto


def test_con_el_pedir_real_un_token_con_salto_de_linea_no_llega_a_la_red(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    guardar(tmp_path / "r", "2026-10-08T2231Z", [envio(1, "error")])
    llamadas: list[str] = []
    monkeypatch.setattr(kaggle_rescate.urllib.request, "build_opener", lambda *a: llamadas.append("red"))
    lineas = kv.vigia(
        raiz_repo=tmp_path,
        entorno={"KAGGLE_API_TOKEN": "KGAT_abc123\ndef456"},
        ahora=AHORA,
        ruta_hallazgos=tmp_path / "x.json",
        principal=tmp_path,
        rescates=tmp_path / "r",
    )
    assert llamadas == []
    assert "abc123" not in "\n".join(lineas) and "def456" not in "\n".join(lineas)


def test_una_excepcion_ajena_solo_muestra_su_tipo(tmp_path: Path) -> None:
    guardar(tmp_path / "r", "2026-10-08T2231Z", [envio(1, "error")])

    def revienta(ruta: str, token: str) -> bytes:
        raise RuntimeError(f"Invalid header value b'Bearer {token[:5]}\\ndef456'")  # cita el valor, recortado

    lineas = correr(tmp_path / "r", revienta)
    linea = next(x for x in lineas if x.startswith("no pude leer Kaggle"))
    assert linea == "no pude leer Kaggle (RuntimeError)"
    assert "Bearer" not in "\n".join(lineas) and TOKEN[:5] not in "\n".join(lineas)


def test_un_rescate_que_solo_trae_envios_no_apaga_el_aviso(tmp_path: Path) -> None:
    guardar(tmp_path / "r", "2026-10-08T2231Z", [envio(1, "error")])
    guardar(tmp_path / "r", "2026-10-09T1342Z", [envio(1, "complete", "0.13")], completo=False)
    lineas = correr(tmp_path / "r", api_falsa([envio(1, "complete", "0.13")]))
    assert any("2026-10-09T1342Z está incompleto" in x for x in lineas)
    assert "envío 1 pasó de `error` a `complete` con nota 0,13: sin procesar" in lineas  # contra el completo
    assert "envíos sin cambios desde esa lectura" not in lineas
    assert kv.ultima_lectura(tmp_path / "r")[0].name == "2026-10-08T2231Z"  # type: ignore[index]


def test_sin_ningun_rescate_completo_no_hay_con_que_comparar(tmp_path: Path) -> None:
    guardar(tmp_path / "r", "2026-10-09T1342Z", [envio(1, "complete", "0.13")], completo=False)
    lineas = correr(tmp_path / "r", api_falsa([envio(1, "complete", "0.13")]))
    assert any("no hay lectura guardada y completa" in x for x in lineas)
    assert "envíos sin cambios desde esa lectura" not in lineas


def test_un_rescate_con_la_lista_de_notebooks_pero_sin_tabla_tambien_es_completo(tmp_path: Path) -> None:
    carpeta = guardar(tmp_path / "r", "2026-10-09T1342Z", [envio(1, "error")], [], completo=False)
    assert kv.rescate_completo(carpeta)
    assert kv.ultima_lectura(tmp_path / "r") is not None


def test_una_marca_futura_se_descarta_y_se_avisa(tmp_path: Path) -> None:
    guardar(tmp_path / "r", "2026-10-08T2231Z", [envio(1, "error")])
    guardar(tmp_path / "r", "2099-01-01T0000Z", [envio(1, "complete", "0.99")])
    lineas = correr(tmp_path / "r", api_falsa([envio(1, "complete", "0.13")]))
    assert "ignoré 2099-01-01T0000Z: su fecha es futura" in lineas
    assert any("2026-10-08T2231Z (hace 15.5 h" in x for x in lineas)
    assert not any("hace -" in x for x in lineas)
    assert "envío 1 pasó de `error` a `complete` con nota 0,13: sin procesar" in lineas


def test_la_carpeta_interior_sin_marca_hereda_la_de_su_madre(tmp_path: Path) -> None:
    guardar(tmp_path / "r", "2026-10-08T2231Z", [envio(1, "error")])
    interior = guardar(tmp_path / "r" / "2026-10-09T1342Z", "sin_marca", [envio(1, "complete", "0.13")])
    elegida = kv.ultima_lectura(tmp_path / "r")
    assert elegida is not None and elegida[0] == interior
    assert elegida[1] == datetime(2026, 10, 9, 13, 42, tzinfo=UTC)


def test_si_no_se_pueden_comparar_los_notebooks_lo_dice(tmp_path: Path) -> None:
    guardar(tmp_path / "r", "2026-10-08T2231Z", [envio(1, "complete", "0.05")])  # sin notebooks.json
    lineas = correr(tmp_path / "r", api_falsa([envio(1, "complete", "0.05")]))
    assert any(x.startswith("no comparé los notebooks: falta notebooks.json") for x in lineas)
    # y sin usuario en ningún sitio:
    carpeta = guardar(tmp_path / "s", "2026-10-08T2231Z", [{"ref": 1, "status": "complete"}], [])
    (carpeta / "usuario.txt").unlink()
    lineas = correr(tmp_path / "s", api_falsa([{"ref": 1, "status": "complete"}]))
    assert any("falta usuario.txt" in x for x in lineas)
    # con el tope gastado:
    guardar(tmp_path / "t", "2026-10-08T2231Z", [envio(1, "complete", "0.05")], [])
    lineas = kv.consultar(
        tmp_path / "t" / "2026-10-08T2231Z", AHORA, TOKEN, api_falsa([envio(1, "complete", "0.05")]),
        AHORA, time.monotonic() - 1,
    )  # fmt: skip
    assert any("falta" in x and "tiempo" in x for x in lineas if x.startswith("no comparé"))


def test_una_pagina_llena_de_envios_se_dice(tmp_path: Path) -> None:
    llenos = [envio(i, "complete", "0.01") for i in range(kv.PAGINA_LLENA)]
    guardar(tmp_path / "r", "2026-10-08T2231Z", llenos)
    lineas = correr(tmp_path / "r", api_falsa(llenos[1:]))
    assert any(x.startswith("solo leí la primera página de envíos") for x in lineas)
    assert any(x.startswith("envío 0 estaba en el último rescate") for x in lineas)
    pocos = [envio(1, "complete", "0.01")]
    guardar(tmp_path / "s", "2026-10-08T2231Z", pocos)
    assert not any("primera página" in x for x in correr(tmp_path / "s", api_falsa(pocos)))


@pytest.mark.parametrize("campo", ["status", "estado_nuevo"])
def test_un_envio_sin_status_es_una_respuesta_ilegible(tmp_path: Path, campo: str) -> None:
    sin_status = {"ref": 1, campo: "complete", "publicScore": "0.1"} if campo != "status" else {"ref": 1}
    guardar(tmp_path / "r", "2026-10-08T2231Z", [sin_status])
    lineas = correr(tmp_path / "r", api_falsa([sin_status]))
    assert any(x.startswith("no pude leer la lectura guardada") for x in lineas)
    assert "envíos sin cambios desde esa lectura" not in lineas
    guardar(tmp_path / "s", "2026-10-08T2231Z", [envio(1, "error")])
    lineas = correr(tmp_path / "s", api_falsa([sin_status]))  # solo la respuesta de la API cambió de forma
    assert any(x.startswith("no pude leer Kaggle") for x in lineas)
    assert "envíos sin cambios desde esa lectura" not in lineas


def test_una_nota_nan_en_ambos_lados_no_avisa() -> None:
    assert kv._nota("nan") is None and kv._nota("inf") is None and kv._nota("-inf") is None
    antes = kv.resumen_de_envios([{"ref": 1, "status": "complete", "publicScore": "nan"}])
    ahora = kv.resumen_de_envios([{"ref": 1, "status": "complete", "publicScore": "nan"}])
    assert kv.comparar_envios(antes, ahora) == []


def test_git_se_llama_una_sola_vez_aunque_falle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    llamadas: list[list[str]] = []

    def falso(cmd: list[str], **kw: Any) -> Any:
        llamadas.append(cmd)
        raise OSError("sin git")

    monkeypatch.setattr(kv.subprocess, "run", falso)
    kv.vigia(raiz_repo=tmp_path, entorno={}, ahora=AHORA, ruta_hallazgos=tmp_path / "x.json")
    assert len(llamadas) == 1
    assert kv.TOPE_GIT_S + kv.TOPE_TOTAL_S < 20  # holgura real bajo los 30 s del gancho


def test_la_salida_del_vigia_se_fuerza_a_utf8(monkeypatch: pytest.MonkeyPatch) -> None:
    visto: list[tuple[str, str]] = []

    class Consola:
        def reconfigure(self, encoding: str, errors: str) -> None:
            visto.append((encoding, errors))

        def write(self, s: str) -> int:
            return len(s)

        def flush(self) -> None:
            pass

    monkeypatch.setattr(kv.sys, "stdout", Consola())
    monkeypatch.setattr(kv, "vigia", lambda **kw: ["VIGÍA KAGGLE"])
    assert kv.main([]) == 0
    assert visto == [("utf-8", "replace")]


# ---------------------------------------------------------------------------
# Validador del registro de hallazgos, segunda mano
# ---------------------------------------------------------------------------


def decidido(**cambios: Any) -> dict[str, Any]:
    decision = {"texto": "se quita", "quien": "concilio", "vuelta": 5, "fecha": "2026-10-09"}
    decision.update(cambios)
    return registro_minimo(estado="decidido", decision=decision, por_que_sigue_abierto=None)


def test_el_registro_decidido_correcto_pasa() -> None:
    assert kv.validar_hallazgos(decidido(), hoy=date(2026, 10, 9)) == []


@pytest.mark.parametrize(
    ("cambios", "fragmento"),
    [
        ({"fecha": "2026-13-45"}, "decision.fecha"),
        ({"fecha": "2026-1-5"}, "decision.fecha"),
        ({"fecha": "ayer"}, "decision.fecha"),
        ({"fecha": "2099-01-01"}, "decision.fecha"),
        ({"vuelta": "5"}, "exige decision"),
        ({"vuelta": True}, "exige decision"),
        ({"vuelta": 2}, "anterior a la primera vuelta"),
        ({"quien": ""}, "exige decision"),
        ({"texto": "  "}, "exige decision"),
        ({"extra": 1}, "campos desconocidos en decision"),
    ],
)
def test_la_decision_se_valida(cambios: dict[str, Any], fragmento: str) -> None:
    problemas = kv.validar_hallazgos(decidido(**cambios), hoy=date(2026, 10, 9))
    assert any(fragmento in p for p in problemas), problemas


@pytest.mark.parametrize(
    ("cambios", "fragmento"),
    [
        ({"primera_fecha": "2026-1-5"}, "primera_fecha"),
        ({"primera_fecha": "2026-02-30"}, "primera_fecha"),
        ({"primera_fecha": "2099-01-01"}, "es futura"),
        ({"estdo": "medido"}, "campos desconocidos"),
        ({"que_se_midio": "falla en pydata__xarray-12345"}, "identificador"),
        ({"que_se_midio": "falla en repo_1234"}, "identificador"),
        ({"por_que_sigue_abierto": "ver src/core/models.py"}, "identificador"),
        ({"que_se_midio": "ver tests/unit/test_x.py"}, "identificador"),
    ],
)
def test_el_formato_rechaza_ademas(cambios: dict[str, Any], fragmento: str) -> None:
    problemas = kv.validar_hallazgos(registro_minimo(**cambios), hoy=date(2026, 10, 9))
    assert any(fragmento in p for p in problemas), problemas


def test_un_campo_desconocido_en_el_registro_se_rechaza() -> None:
    datos = registro_minimo()
    datos["extra"] = 1
    assert any("campos desconocidos en el registro" in p for p in kv.validar_hallazgos(datos))


def test_el_archivo_sembrado_sigue_pasando_el_validador_estricto() -> None:
    datos = json.loads(HALLAZGOS_REALES.read_text(encoding="utf-8"))
    assert kv.validar_hallazgos(datos, hoy=date.today()) == []
