"""Pruebas de scripts/kaggle_validez.py con verificadores y datos sinteticos inventados.

Ningun dato de la competencia entra aqui, y estas pruebas no importan ``swegemma``. Los textos
«envenenados» (nombres de pruebas, fragmentos de parche y de log, enunciados) son inventados y
sirven para comprobar que no llegan al registro versionable.

Notacion de un caso: ``S1 D1 S2 D2`` son los resultados de las cuatro rondas (sin parche y con
parche de referencia, dos veces cada una); ``+`` resuelta, ``-`` no resuelta, ``I`` infraestructura.
"""

from __future__ import annotations

import hashlib
import importlib
import itertools
import json
import logging
import re
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from scripts import kaggle_prereg, kaggle_split
from scripts import kaggle_validez as kv
from scripts.kaggle_validez import (
    CLASE_DISCRIMINA,
    CLASE_DORADO_FALLA,
    CLASE_INESTABLE,
    CLASE_NO_MEDIBLE,
    CLASE_PASA,
    Almacen,
    ResultadoVerificacion,
    Tarea,
    ValidezError,
)

AHORA = datetime(2026, 10, 5, 12, 0, 0, tzinfo=UTC)
FECHA_UTC = "2026-10-05T12:00:00Z"
POISON_TEST = "test_secreto_nombre_de_prueba_xyz"
POISON_LOG = "LINEA_DE_LOG_PRIVADA_QWERTY"
POISON_PARCHE = "+    return PARCHE_DORADO_SECRETO_42"
POISON_ENUNCIADO = "ENUNCIADO_PRIVADO_ASDF"
POISON_ERROR = "texto-del-error-que-no-debe-guardarse-777"
POISON_TODOS = (
    POISON_TEST,
    POISON_LOG,
    POISON_PARCHE,
    POISON_ENUNCIADO,
    POISON_ERROR,
    "PARCHE_DORADO_SECRETO",
)


def reloj() -> datetime:
    return AHORA


# ---------------------------------------------------------------------------
# Resultados y verificador falsos
# ---------------------------------------------------------------------------


def ok() -> ResultadoVerificacion:
    """Resuelta (exit 0)."""
    return ResultadoVerificacion(
        True, 0, None, 2.0, 3, 0, 0, f"{POISON_LOG}\n3 passed in 2.00s\n{POISON_TEST}"
    )


def falla() -> ResultadoVerificacion:
    """No resuelta por pruebas que fallan (no es infraestructura)."""
    return ResultadoVerificacion(
        False,
        1,
        f"Test failures/errors recorded in JUnit XML ({POISON_ERROR})",
        1.5,
        1,
        2,
        0,
        f"FAILED tests/{POISON_TEST}\n{POISON_PARCHE}\n2 failed, 1 passed in 1.50s",
    )


def infra() -> ResultadoVerificacion:
    """Las pruebas no se pudieron ejecutar (codigo -1, sin error): infraestructura."""
    return ResultadoVerificacion(False, -1, None, 0.5, None, None, None, POISON_LOG)


class Falso:
    """Verificador falso con un guion por ``(instance_id, verificacion)``.

    Cada llamada consume el siguiente resultado de su lista; si la lista se agota, usa el
    comportamiento por defecto de una tarea que discrimina: sin parche falla y con parche pasa.
    """

    def __init__(self, guion: dict[tuple[str, str], list[ResultadoVerificacion]] | None = None) -> None:
        self.guion = {k: list(v) for k, v in (guion or {}).items()}
        self.llamadas: list[tuple[str, str]] = []
        self.explotar_en: int | None = None  # numero de llamada (base 1) que lanza una excepcion

    def __call__(self, tarea: Tarea, verificacion: str) -> ResultadoVerificacion:
        self.llamadas.append((tarea.instance_id, verificacion))
        if self.explotar_en == len(self.llamadas):
            raise RuntimeError(f"fallo del verificador con {POISON_ERROR}")
        cola = self.guion.get((tarea.instance_id, verificacion))
        if cola:
            return cola.pop(0)
        return falla() if verificacion == kv.VERIF_SIN else ok()


GUIONES: dict[str, dict[str, list[ResultadoVerificacion]]] = {
    CLASE_DISCRIMINA: {},
    CLASE_PASA: {kv.VERIF_SIN: [ok(), ok()]},
    CLASE_DORADO_FALLA: {kv.VERIF_DORADO: [falla(), falla()]},
    CLASE_INESTABLE: {kv.VERIF_SIN: [falla(), ok()]},
    CLASE_NO_MEDIBLE: {kv.VERIF_SIN: [infra(), infra(), falla()]},
}


def guion_de(iid: str, clase: str) -> dict[tuple[str, str], list[ResultadoVerificacion]]:
    return {(iid, v): list(r) for v, r in GUIONES[clase].items()}


# ---------------------------------------------------------------------------
# Archivos sinteticos
# ---------------------------------------------------------------------------


def escribir_tareas(ruta: Path, spec: list[tuple[str, str]]) -> None:
    """``tasks.jsonl`` sintetico con campos privados envenenados que el guion no debe copiar."""
    lineas = [
        json.dumps(
            {
                "instance_id": iid,
                "repo": repo,
                "created_at": "2025-01-01T00:00:00Z",
                "problem_statement": POISON_ENUNCIADO,
                "patch": POISON_PARCHE,
                "test_patch": f"def {POISON_TEST}(): pass",
            }
        )
        for iid, repo in spec
    ]
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")


ENTORNO = {
    "schema_version": "kaggle-sandbox-env/1",
    "ensayo_sha256": "a" * 64,
    "backend": "subprocess",
    "imagen": "sandbox:prueba",
    "version_arnes": "0.2.7",
    "ruedas_sha256": "b" * 64,
    "arreglos": ["arreglo inventado"],
}


def escribir_entorno(ruta: Path, **cambios: object) -> str:
    texto = json.dumps({**ENTORNO, **cambios}, indent=2)
    ruta.write_text(texto, encoding="utf-8")
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


class Escenario:
    """Directorio de trabajo con ``tasks.jsonl``, entorno y rutas de salida listos."""

    def __init__(self, base: Path, spec: list[tuple[str, str]]) -> None:
        self.base = base
        self.spec = spec
        self.tasks = base / "tasks.jsonl"
        self.entorno = base / "entorno.json"
        self.crudo = base / "crudo"
        self.salida = base / "validez_tareas_v1.json"
        self.snapshots = base / "snapshots"
        escribir_tareas(self.tasks, spec)
        self.entorno_sha = escribir_entorno(self.entorno)

    def argv(self, *extra: str, salida: bool = True) -> list[str]:
        base = [
            "--tasks",
            str(self.tasks),
            "--snapshots-dir",
            str(self.snapshots),
            "--entorno",
            str(self.entorno),
            "--imagen",
            "sandbox:prueba",
            "--sandbox",
            "subprocess",
            "--crudo",
            str(self.crudo),
        ]
        if salida:
            base += ["--salida", str(self.salida)]
        return [*base, *extra]

    def correr(self, verificador: Callable[..., Any] | None, *extra: str, salida: bool = True) -> int:
        return kv.main(self.argv(*extra, salida=salida), verificador=verificador, reloj=reloj)

    def registro(self) -> dict[str, Any]:
        return json.loads(self.salida.read_text(encoding="utf-8"))


def nuevo(tmp_path: Path, nombre: str, spec: list[tuple[str, str]]) -> Escenario:
    (tmp_path / nombre).mkdir()
    return Escenario(tmp_path / nombre, spec)


def spec_un_repo(n: int, repo: str = "owner/a") -> list[tuple[str, str]]:
    return [(f"{repo.split('/')[1]}__pkg-{i:03d}", repo) for i in range(n)]


@pytest.fixture
def esc(tmp_path: Path) -> Escenario:
    return Escenario(tmp_path, spec_un_repo(3))


def params_para(esc: Escenario) -> Path:
    """Copia de linea_base_a.json cuyo ``tasks_sha256`` es el del ``tasks.jsonl`` sintetico."""
    ruta = esc.base / "params.json"
    datos = json.loads(kaggle_prereg.DEFAULT_PARAMS.read_text(encoding="utf-8"))
    datos["fijos"]["tasks_sha256"] = hashlib.sha256(esc.tasks.read_bytes()).hexdigest()
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    return ruta


# ---------------------------------------------------------------------------
# clasificar: todas las combinaciones
# ---------------------------------------------------------------------------


def e(estado: str) -> dict[str, Any]:
    return {
        "estado": "infra_error" if estado == "I" else "resolved" if estado == "+" else "unresolved",
        "resolved": estado == "+",
    }


# (S1, S2, D1, D2) -> clase, calculada a mano de la tabla A.3.
ESPERADAS_SIN_INFRA = {
    "----": CLASE_DORADO_FALLA,  # sin parche no resuelta, dorado no resuelta
    "--++": CLASE_DISCRIMINA,
    "--+-": CLASE_INESTABLE,
    "---+": CLASE_INESTABLE,
    "++--": CLASE_PASA,  # resuelta sin parche en las dos: pasa_sin_parche aunque el dorado falle
    "++++": CLASE_PASA,
    "++-+": CLASE_INESTABLE,
    "+++-": CLASE_INESTABLE,
    "+---": CLASE_INESTABLE,
    "+-++": CLASE_INESTABLE,
    "+-+-": CLASE_INESTABLE,
    "+--+": CLASE_INESTABLE,
    "-+--": CLASE_INESTABLE,
    "-+++": CLASE_INESTABLE,
    "-++-": CLASE_INESTABLE,
    "-+-+": CLASE_INESTABLE,
}


def test_clasificar_las_16_combinaciones_sin_infraestructura() -> None:
    combos = ["".join(c) for c in itertools.product("+-", repeat=4)]
    assert sorted(combos) == sorted(ESPERADAS_SIN_INFRA)
    for combo, clase in ESPERADAS_SIN_INFRA.items():
        s1, s2, d1, d2 = combo
        assert kv.clasificar([e(s1), e(s2)], [e(d1), e(d2)]) == clase, combo


def test_clasificar_infraestructura_gana_a_todo_lo_demas() -> None:
    # alguna ejecucion final de infraestructura => no_medible, aunque lo demas sea inestable o pase
    for combo in itertools.product("+-I", repeat=4):
        if "I" not in combo:
            continue
        s1, s2, d1, d2 = combo
        assert kv.clasificar([e(s1), e(s2)], [e(d1), e(d2)]) == CLASE_NO_MEDIBLE, combo


def test_clasificar_exige_dos_ejecuciones_por_verificacion() -> None:
    with pytest.raises(ValidezError):
        kv.clasificar([e("-")], [e("+"), e("+")])
    with pytest.raises(ValidezError):
        kv.clasificar([e("-"), e("-")], [e("+")])


def test_las_clases_del_guion_son_las_de_la_compuerta() -> None:
    clases = {CLASE_DISCRIMINA, CLASE_PASA, CLASE_DORADO_FALLA, CLASE_INESTABLE, CLASE_NO_MEDIBLE}
    assert clases == set(kaggle_prereg.CLASES_VALIDEZ)


# ---------------------------------------------------------------------------
# registro_de_ejecucion y filtro del error
# ---------------------------------------------------------------------------


def reg(res: ResultadoVerificacion) -> dict[str, Any]:
    return kv.registro_de_ejecucion(res, kv.VERIF_SIN, 1, 1, FECHA_UTC)


def r(resolved: bool, code: int, error: str | None) -> ResultadoVerificacion:
    return ResultadoVerificacion(resolved, code, error, 1.0)


@pytest.mark.parametrize(
    ("res", "estado", "categoria"),
    [
        (r(True, 0, None), "resolved", None),
        (r(False, 1, None), "unresolved", "tests_failed"),
        (r(False, 124, None), "unresolved", "tests_failed"),  # timeout de las pruebas: no es infra
        (r(False, 137, None), "unresolved", "tests_failed"),  # proceso matado: no es infra
        (r(False, -1, None), "infra_error", "test_exec_failed"),  # pruebas no ejecutables
        (r(False, 1, f"Failed to apply agent patch: {POISON_PARCHE}"), "unresolved", "patch_apply_failed"),
        (
            r(False, 1, f"Test failures/errors recorded in JUnit XML ({POISON_TEST})"),
            "unresolved",
            "tests_failed",
        ),
        (
            r(False, 1, f"Sandbox execution error: ContextWindowExceededError {POISON_LOG}"),
            "unresolved",
            "context_exceeded",
        ),
        (r(False, -1, f"Sandbox execution error: {POISON_LOG}"), "infra_error", "sandbox_error"),
        (r(False, -1, "Snapshot file not found: x.tgz"), "infra_error", "snapshot_missing"),
        (r(False, -1, "Missing test specification (vacio)"), "infra_error", "missing_test_spec"),
        (r(False, -1, f"Failed to apply test_patch: {POISON_PARCHE}"), "infra_error", "test_patch_failed"),
        (r(False, -1, f"Evaluation error: {POISON_ERROR}"), "infra_error", "evaluation_error"),
        (r(False, -1, f"Unexpected evaluation worker error: {POISON_ERROR}"), "infra_error", "worker_error"),
    ],
)
def test_registro_guarda_categoria_y_nunca_el_texto(
    res: ResultadoVerificacion, estado: str, categoria: str | None
) -> None:
    registro = reg(res)
    assert registro["estado"] == estado
    assert registro["categoria"] == categoria
    assert registro["codigo_salida"] == res.test_exit_code
    assert set(registro) == set(kv.CLAVES_EJECUCION)
    dump = json.dumps(registro)
    assert all(p not in dump for p in POISON_TODOS)
    assert categoria is None or categoria in kv.CATEGORIAS


def test_error_fuera_de_la_lista_cerrada_es_salida_2_sin_su_texto() -> None:
    with pytest.raises(ValidezError) as info:
        reg(r(False, 1, f"Algo nunca visto: {POISON_ERROR}"))
    assert POISON_ERROR not in str(info.value)
    # combinacion incoherente: resuelta pero con codigo distinto de 0
    with pytest.raises(ValidezError):
        reg(r(True, 1, None))
    # sin error, no resuelta y con codigo 0
    with pytest.raises(ValidezError):
        reg(r(False, 0, None))


def test_codigo_menos_1_no_se_lee_como_parche_vacio() -> None:
    # sin parche no hay agente: -1 debe seguir siendo infraestructura, no «parche vacio»
    assert reg(r(False, -1, None))["estado"] == "infra_error"


@pytest.mark.parametrize(
    "res",
    [
        ResultadoVerificacion(1, 0, None, 1.0),  # type: ignore[arg-type]
        ResultadoVerificacion(True, True, None, 1.0),  # type: ignore[arg-type]
        ResultadoVerificacion(True, 0, None, -1.0),
        ResultadoVerificacion(True, 0, None, float("nan")),
        ResultadoVerificacion(True, 0, 5, 1.0),  # type: ignore[arg-type]
        ResultadoVerificacion(True, 0, None, 1.0, passed=-1),
        ResultadoVerificacion(True, 0, None, 1.0, failed=True),  # type: ignore[arg-type]
        ResultadoVerificacion(True, 0, None, 1.0, salida=3),  # type: ignore[arg-type]
    ],
)
def test_validar_resultado_rechaza_formas_invalidas(res: ResultadoVerificacion) -> None:
    with pytest.raises(ValidezError):
        kv.validar_resultado(res)


def test_validar_resultado_rechaza_lo_que_no_es_un_resultado() -> None:
    with pytest.raises(ValidezError):
        kv.validar_resultado({"resolved": True})


def test_contar_pruebas() -> None:
    assert kv.contar_pruebas("== 3 passed, 1 failed, 2 errors in 0.5s ==") == (3, 1, 2)
    assert kv.contar_pruebas("1 passed in 0.01s") == (1, 0, 0)
    assert kv.contar_pruebas("4 failed, 1 error in 2s") == (0, 4, 1)
    assert kv.contar_pruebas("ruido\n2 passed in 1s\n3 warnings\nfin") == (2, 0, 0)
    assert kv.contar_pruebas("sin resumen") == (None, None, None)
    assert kv.contar_pruebas("") == (None, None, None)
    assert kv.contar_pruebas("test_3_passed_algo") == (None, None, None)


# ---------------------------------------------------------------------------
# guarda: fronteras exactas
# ---------------------------------------------------------------------------


def tareas_con(repo: str, buenas: int, malas: int) -> list[dict[str, Any]]:
    return [{"repo": repo, "clase": CLASE_DISCRIMINA}] * buenas + [
        {"repo": repo, "clase": CLASE_INESTABLE}
    ] * malas


@pytest.mark.parametrize(
    ("buenas", "malas", "salta"),
    [
        (5, 5, False),  # 10 tareas, exactamente la mitad: no es «mas de la mitad»
        (4, 6, True),  # 10 tareas, 6 de 10
        (6, 4, False),
        (0, 10, True),
        (10, 0, False),
        (6, 5, False),  # 11 tareas, 5 malas
        (5, 6, True),  # 11 tareas, 6 malas
        (0, 9, False),  # 9 tareas: por debajo del minimo, no se evalua aunque todas fallen
        (1, 8, False),
    ],
)
def test_guarda_fronteras(buenas: int, malas: int, salta: bool) -> None:
    resultado = kv.guarda(tareas_con("o/r", buenas, malas))
    assert bool(resultado) is salta
    if salta:
        assert resultado == [{"repo": "o/r", "tareas": buenas + malas, "no_discrimina": malas}]


def test_guarda_evalua_cada_repositorio_por_separado() -> None:
    tareas = [*tareas_con("o/a", 4, 6), *tareas_con("o/b", 9, 1), *tareas_con("o/c", 0, 9)]
    assert [s["repo"] for s in kv.guarda(tareas)] == ["o/a"]


def test_guarda_cuenta_toda_clase_distinta_de_discrimina() -> None:
    clases = [CLASE_NO_MEDIBLE, CLASE_PASA, CLASE_DORADO_FALLA, CLASE_INESTABLE, CLASE_NO_MEDIBLE, CLASE_PASA]
    tareas = [{"repo": "o/r", "clase": c} for c in clases] + [{"repo": "o/r", "clase": CLASE_DISCRIMINA}] * 4
    assert kv.guarda(tareas)[0]["no_discrimina"] == 6


# ---------------------------------------------------------------------------
# medir_tarea: cada clase, infraestructura y repeticion
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("clase", sorted(GUIONES))
def test_medir_tarea_cada_clase(tmp_path: Path, clase: str) -> None:
    tarea = Tarea("pkg__x-1", "o/pkg")
    falso = Falso(guion_de(tarea.instance_id, clase))
    t = kv.medir_tarea(tarea, falso, Almacen(tmp_path), reloj)
    assert t["clase"] == clase
    assert set(t) == set(kv.CLAVES_TAREA)
    # ronda intercalada, con la misma funcion para las dos verificaciones
    orden = [v for _, v in falso.llamadas[:4]]
    if clase != CLASE_NO_MEDIBLE:
        assert orden == [kv.VERIF_SIN, kv.VERIF_DORADO, kv.VERIF_SIN, kv.VERIF_DORADO]
        assert len(falso.llamadas) == 4
    assert all(iid == tarea.instance_id for iid, _ in falso.llamadas)


def test_medir_tarea_duraciones_y_ejecuciones(tmp_path: Path) -> None:
    tarea = Tarea("pkg__x-1", "o/pkg")
    t = kv.medir_tarea(tarea, Falso(), Almacen(tmp_path), reloj)
    assert t["sin_parche_segundos"] == [1.5, 1.5]  # duraciones de falla()
    assert t["dorado_segundos"] == [2.0, 2.0]  # duraciones de ok()
    assert [(x["verificacion"], x["numero"], x["intento"]) for x in t["ejecuciones"]] == [
        ("sin_parche", 1, 1),
        ("dorado", 1, 1),
        ("sin_parche", 2, 1),
        ("dorado", 2, 1),
    ]
    assert t["ejecuciones_lanzadas"] == 4
    # lo versionable solo lleva lo que A.2 y A.4 enumeran: sin conteos ni fecha por ejecucion
    assert all(set(x) == set(kv.CLAVES_EJECUCION_VERSIONADAS) for x in t["ejecuciones"])
    # la fecha y los conteos quedan en el crudo
    crudo = json.loads(
        (tmp_path / "ejecuciones" / tarea.instance_id / "sin_parche_1_1.json").read_text("utf-8")
    )
    assert crudo["registro"]["fecha_utc"] == FECHA_UTC
    assert (crudo["registro"]["passed"], crudo["registro"]["failed"], crudo["registro"]["errors"]) == (
        1,
        2,
        0,
    )


def test_infraestructura_se_repite_una_vez_y_vale_la_repeticion(tmp_path: Path) -> None:
    tarea = Tarea("pkg__x-1", "o/pkg")
    falso = Falso({(tarea.instance_id, kv.VERIF_SIN): [infra(), falla(), falla()]})
    t = kv.medir_tarea(tarea, falso, Almacen(tmp_path), reloj)
    assert t["clase"] == CLASE_DISCRIMINA  # la repeticion sustituye a la ejecucion de infraestructura
    assert len(falso.llamadas) == 5
    assert [(x["verificacion"], x["numero"], x["intento"], x["estado"]) for x in t["ejecuciones"]][:2] == [
        ("sin_parche", 1, 1, "infra_error"),
        ("sin_parche", 1, 2, "unresolved"),
    ]
    assert t["sin_parche_segundos"] == [1.5, 1.5]  # la duracion de la infra (0,5) no cuenta como final


def test_infraestructura_dos_veces_es_no_medible_y_no_se_repite_una_tercera(tmp_path: Path) -> None:
    tarea = Tarea("pkg__x-1", "o/pkg")
    for verif in (kv.VERIF_SIN, kv.VERIF_DORADO):
        falso = Falso({(tarea.instance_id, verif): [infra(), infra(), infra(), infra()]})
        t = kv.medir_tarea(tarea, falso, Almacen(tmp_path / verif), reloj)
        assert t["clase"] == CLASE_NO_MEDIBLE
        assert len(falso.llamadas) == 6  # 4 rondas + 2 repeticiones: sin tercera ejecucion


def test_codigo_124_y_137_con_el_parche_dorado_no_son_infraestructura(tmp_path: Path) -> None:
    colgada = ResultadoVerificacion(False, 124, None, 9.0)
    matada = ResultadoVerificacion(False, 137, None, 9.0)
    tarea = Tarea("pkg__x-1", "o/pkg")
    falso = Falso({(tarea.instance_id, kv.VERIF_DORADO): [colgada, matada]})
    t = kv.medir_tarea(tarea, falso, Almacen(tmp_path), reloj)
    assert t["clase"] == CLASE_DORADO_FALLA
    assert len(falso.llamadas) == 4  # no hubo repeticion


def test_excepcion_del_verificador_es_salida_2_y_no_registra_nada(tmp_path: Path) -> None:
    tarea = Tarea("pkg__x-1", "o/pkg")
    falso = Falso()
    falso.explotar_en = 3
    with pytest.raises(ValidezError) as info:
        kv.medir_tarea(tarea, falso, Almacen(tmp_path), reloj)
    assert POISON_ERROR not in str(info.value)
    assert "RuntimeError" in str(info.value)
    guardadas = sorted(p.name for p in (tmp_path / "ejecuciones" / tarea.instance_id).iterdir())
    assert guardadas == ["dorado_1_1.json", "sin_parche_1_1.json"]  # la tercera no deja rastro


def test_resultado_mal_formado_del_verificador_es_salida_2(tmp_path: Path) -> None:
    def malo(_t: Tarea, _v: str) -> ResultadoVerificacion:
        return {"resolved": True}  # type: ignore[return-value]

    with pytest.raises(ValidezError):
        kv.medir_tarea(Tarea("pkg__x-1", "o/pkg"), malo, Almacen(tmp_path), reloj)


# ---------------------------------------------------------------------------
# Reanudacion, idempotencia y negativa a sobrescribir
# ---------------------------------------------------------------------------


def test_reanudar_no_repite_ni_pierde_ejecuciones(tmp_path: Path) -> None:
    tarea = Tarea("pkg__x-1", "o/pkg")
    completo = kv.medir_tarea(tarea, Falso(), Almacen(tmp_path / "limpio"), reloj)

    cortada = Falso()
    cortada.explotar_en = 3  # se corta en la tercera ejecucion
    almacen = Almacen(tmp_path / "cortado")
    with pytest.raises(ValidezError):
        kv.medir_tarea(tarea, cortada, almacen, reloj)
    reanudada = Falso()
    t = kv.medir_tarea(tarea, reanudada, almacen, reloj)
    assert t == completo
    assert reanudada.llamadas == [(tarea.instance_id, "sin_parche"), (tarea.instance_id, "dorado")]
    # idempotente: una tercera pasada no ejecuta nada
    otra = Falso()
    assert kv.medir_tarea(tarea, otra, almacen, reloj) == completo
    assert otra.llamadas == []


def test_reanudar_despues_de_una_infraestructura_corre_solo_la_repeticion(tmp_path: Path) -> None:
    tarea = Tarea("pkg__x-1", "o/pkg")
    almacen = Almacen(tmp_path)
    primera = Falso({(tarea.instance_id, kv.VERIF_SIN): [infra()]})
    primera.explotar_en = 2  # guarda la infra de la primera ronda y se corta
    with pytest.raises(ValidezError):
        kv.medir_tarea(tarea, primera, almacen, reloj)
    segunda = Falso()
    t = kv.medir_tarea(tarea, segunda, almacen, reloj)
    assert segunda.llamadas[0] == (tarea.instance_id, "sin_parche")  # la repeticion de la ronda 1
    assert len(segunda.llamadas) == 4  # repeticion + 3 rondas restantes: no repite la infra guardada
    assert t["clase"] == CLASE_DISCRIMINA


def test_no_se_sobrescribe_una_ejecucion_guardada(tmp_path: Path) -> None:
    tarea = Tarea("pkg__x-1", "o/pkg")
    almacen = Almacen(tmp_path)
    res = ok()
    registro = kv.registro_de_ejecucion(res, "sin_parche", 1, 1, FECHA_UTC)
    almacen.guardar(tarea, "sin_parche", 1, 1, res, registro)
    antes = (tmp_path / "ejecuciones" / tarea.instance_id / "sin_parche_1_1.json").read_bytes()
    with pytest.raises(ValidezError):
        almacen.guardar(tarea, "sin_parche", 1, 1, falla(), registro)
    despues = (tmp_path / "ejecuciones" / tarea.instance_id / "sin_parche_1_1.json").read_bytes()
    assert antes == despues


def guardar_ronda(almacen: Almacen, tarea: Tarea) -> Path:
    kv.medir_tarea(tarea, Falso(), almacen, reloj)
    return almacen.raiz / "ejecuciones" / tarea.instance_id / "sin_parche_1_1.json"


def rehacer_diario(raiz: Path) -> None:
    """Recalcula el diario tras editar archivos a mano (lo que haria quien manipula con cuidado)."""
    lineas = (raiz / "diario.jsonl").read_bytes().split(b"\n")[:-1]
    previo = kv.GENESIS
    salida: list[bytes] = []
    for linea in lineas:
        obj = json.loads(linea)
        ruta = (
            raiz
            / "ejecuciones"
            / obj["instance_id"]
            / f"{obj['verificacion']}_{obj['numero']}_{obj['intento']}.json"
        )
        obj["sha256_ejecucion"] = hashlib.sha256(ruta.read_bytes()).hexdigest()
        obj["previo"] = previo
        nueva = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
        previo = hashlib.sha256(nueva).hexdigest()
        salida.append(nueva)
    (raiz / "diario.jsonl").write_bytes(b"".join(x + b"\n" for x in salida))


def test_discrepancia_entre_lo_guardado_y_lo_recalculado_es_error(tmp_path: Path) -> None:
    tarea = Tarea("pkg__x-1", "o/pkg")
    ruta = guardar_ronda(Almacen(tmp_path), tarea)
    obj = json.loads(ruta.read_text(encoding="utf-8"))
    # cambiar el resultado crudo (pasa de fallar a resolver) sin tocar el registro
    obj["resultado"]["resolved"] = True
    obj["resultado"]["test_exit_code"] = 0
    obj["resultado"]["error"] = None
    ruta.write_text(json.dumps(obj), encoding="utf-8")
    rehacer_diario(tmp_path)  # el diario ya no delata la edicion: queda el recalculo
    with pytest.raises(ValidezError, match="Discrepancia"):
        kv.medir_tarea(tarea, Falso(), Almacen(tmp_path), reloj)


def test_registro_alterado_tambien_es_discrepancia(tmp_path: Path) -> None:
    tarea = Tarea("pkg__x-1", "o/pkg")
    ruta = guardar_ronda(Almacen(tmp_path), tarea)
    obj = json.loads(ruta.read_text(encoding="utf-8"))
    obj["registro"]["resolved"] = True
    ruta.write_text(json.dumps(obj), encoding="utf-8")
    rehacer_diario(tmp_path)
    with pytest.raises(ValidezError, match="Discrepancia"):
        kv.medir_tarea(tarea, Falso(), Almacen(tmp_path), reloj)


def test_editar_resultado_y_registro_a_la_vez_y_rehacer_el_diario_pasa_pero_cambia_el_hash_final(
    tmp_path: Path,
) -> None:
    """Limite declarado: el diario hace visible la manipulacion, no la impide."""
    tarea = Tarea("pkg__x-1", "o/pkg")
    almacen = Almacen(tmp_path)
    ruta = guardar_ronda(almacen, tarea)
    antes = kv.Almacen(tmp_path).diario_sha256()
    obj = json.loads(ruta.read_text(encoding="utf-8"))
    obj["resultado"].update(resolved=True, test_exit_code=0, error=None)
    obj["registro"].update(resolved=True, estado="resolved", categoria=None, codigo_salida=0)
    ruta.write_text(json.dumps(obj), encoding="utf-8")
    rehacer_diario(tmp_path)
    nuevo_almacen = Almacen(tmp_path)
    assert kv.medir_tarea(tarea, Falso(), nuevo_almacen, reloj)["clase"] == CLASE_INESTABLE
    assert nuevo_almacen.diario_sha256() != antes  # lo unico que lo delata: el hash final registrado


@pytest.mark.parametrize("contenido", ["no es json", "[]", '{"resultado": {}, "registro": {}}'])
def test_ejecucion_guardada_ilegible_es_error(tmp_path: Path, contenido: str) -> None:
    tarea = Tarea("pkg__x-1", "o/pkg")
    ruta = guardar_ronda(Almacen(tmp_path), tarea)
    ruta.write_text(contenido, encoding="utf-8")
    rehacer_diario(tmp_path)  # que el diario coincida: se prueba la lectura, no el hash
    with pytest.raises(ValidezError):
        kv.medir_tarea(tarea, Falso(), Almacen(tmp_path), reloj)


def test_repeticion_sin_primera_ejecucion_o_sobrante_es_error(tmp_path: Path) -> None:
    tarea = Tarea("pkg__x-1", "o/pkg")
    almacen = Almacen(tmp_path)
    ruta = guardar_ronda(almacen, tarea)
    # una «repeticion» de una ejecucion que no era de infraestructura
    ruta.with_name("sin_parche_1_2.json").write_bytes(ruta.read_bytes())
    with pytest.raises(ValidezError):
        kv.medir_tarea(tarea, Falso(), almacen, reloj)
    # una repeticion guardada sin la primera
    ruta.unlink()
    with pytest.raises(ValidezError):
        kv.medir_tarea(tarea, Falso(), almacen, reloj)


def test_instance_id_peligroso_no_se_usa_como_nombre_de_archivo(tmp_path: Path) -> None:
    with pytest.raises(ValidezError):
        Almacen(tmp_path).existe(Tarea("../../fuera", "o/r"), "sin_parche", 1, 1)


def test_escribir_sin_sobrescribir(tmp_path: Path) -> None:
    destino = tmp_path / "sub" / "a.json"
    kv.escribir_sin_sobrescribir(destino, b"uno")
    assert destino.read_bytes() == b"uno"
    with pytest.raises(ValidezError):
        kv.escribir_sin_sobrescribir(destino, b"dos")
    assert destino.read_bytes() == b"uno"
    assert [p.name for p in destino.parent.iterdir()] == ["a.json"]  # sin temporales


def test_escribir_sin_sobrescribir_sin_enlaces_duros(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def sin_enlaces(*_a: object, **_k: object) -> None:
        raise OSError("sin enlaces duros")

    monkeypatch.setattr(kv.os, "link", sin_enlaces)
    destino = tmp_path / "a.json"
    kv.escribir_sin_sobrescribir(destino, b"uno")
    assert destino.read_bytes() == b"uno"
    with pytest.raises(ValidezError):
        kv.escribir_sin_sobrescribir(destino, b"dos")


def test_escribir_sin_sobrescribir_carrera(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    destino = tmp_path / "a.json"

    def aparece(origen: object, dest: object) -> None:
        Path(str(dest)).write_bytes(b"ajeno")
        raise FileExistsError

    monkeypatch.setattr(kv.os, "link", aparece)
    with pytest.raises(ValidezError):
        kv.escribir_sin_sobrescribir(destino, b"mio")
    assert destino.read_bytes() == b"ajeno"


# ---------------------------------------------------------------------------
# Ruta cruda ignorada por git
# ---------------------------------------------------------------------------


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def test_crudo_fuera_de_un_repositorio_se_acepta(tmp_path: Path) -> None:
    kv.comprobar_crudo_ignorado(tmp_path / "crudo")


def test_crudo_dentro_de_un_repositorio_sin_ignorar_se_rechaza(tmp_path: Path) -> None:
    git(tmp_path, "init", "-q")
    with pytest.raises(ValidezError, match="no la ignora"):
        kv.comprobar_crudo_ignorado(tmp_path / "datos" / "crudo")


def test_crudo_dentro_de_un_repositorio_ignorado_se_acepta(tmp_path: Path) -> None:
    git(tmp_path, "init", "-q")
    (tmp_path / ".gitignore").write_text("datos/\n", encoding="utf-8")
    kv.comprobar_crudo_ignorado(tmp_path / "datos" / "crudo")
    # tambien cuando el directorio ya existe
    (tmp_path / "datos" / "crudo").mkdir(parents=True)
    kv.comprobar_crudo_ignorado(tmp_path / "datos" / "crudo")
    with pytest.raises(ValidezError):
        kv.comprobar_crudo_ignorado(tmp_path / "otro")


def test_crudo_sin_poder_comprobar_con_git_es_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".git").mkdir()

    def sin_git(*_a: object, **_k: object) -> None:
        raise FileNotFoundError

    monkeypatch.setattr(kv.subprocess, "run", sin_git)
    with pytest.raises(ValidezError, match="No se pudo ejecutar git"):
        kv.comprobar_crudo_ignorado(tmp_path / "crudo")


def test_crudo_con_error_de_git_no_equivale_a_ignorada(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(
        kv.subprocess, "run", lambda *_a, **_k: subprocess.CompletedProcess([], 128, b"", b"fatal")
    )
    with pytest.raises(ValidezError, match="no se pudo comprobar"):
        kv.comprobar_crudo_ignorado(tmp_path / "crudo")


def test_crudo_que_es_un_archivo_es_error(tmp_path: Path) -> None:
    f = tmp_path / "archivo"
    f.write_text("x", encoding="utf-8")
    with pytest.raises(ValidezError):
        kv.comprobar_crudo_ignorado(f / "dentro")


# ---------------------------------------------------------------------------
# main de punta a punta
# ---------------------------------------------------------------------------


def verificador_con_clases(esc: Escenario, clases: dict[str, str]) -> Falso:
    guion: dict[tuple[str, str], list[ResultadoVerificacion]] = {}
    for iid, clase in clases.items():
        guion.update(guion_de(iid, clase))
    return Falso(guion)


def test_main_punta_a_punta_escribe_el_registro_y_pasa_la_validacion(
    esc: Escenario, capsys: pytest.CaptureFixture[str]
) -> None:
    ids = [i for i, _ in esc.spec]
    falso = verificador_con_clases(
        esc, {ids[0]: CLASE_DISCRIMINA, ids[1]: CLASE_INESTABLE, ids[2]: CLASE_DORADO_FALLA}
    )
    assert esc.correr(falso) == kv.EXIT_OK
    out = capsys.readouterr().out
    assert "Tareas medidas: 3" in out
    registro = esc.registro()
    assert set(registro) == set(kaggle_prereg.VALIDEZ)
    assert registro["schema_version"] == "kaggle-task-validity/1"
    assert registro["fecha"] == "2026-10-05"
    assert registro["sha256_tasks"] == hashlib.sha256(esc.tasks.read_bytes()).hexdigest()
    assert registro["entorno_sha256"] == esc.entorno_sha
    assert [t["instance_id"] for t in registro["tareas"]] == sorted(ids)
    assert {t["instance_id"]: t["clase"] for t in registro["tareas"]} == {
        ids[0]: CLASE_DISCRIMINA,
        ids[1]: CLASE_INESTABLE,
        ids[2]: CLASE_DORADO_FALLA,
    }
    assert registro["tareas_invalidas"] == [
        {"instance_id": ids[1], "clase": CLASE_INESTABLE},
        {"instance_id": ids[2], "clase": CLASE_DORADO_FALLA},
    ]
    assert kv.validar_registro(registro) == []
    assert esc.salida.read_bytes().endswith(b"\n") and b"\r" not in esc.salida.read_bytes()
    # el manifiesto del entorno queda en la ruta cruda
    assert (esc.crudo / "manifiesto.json").is_file()


def test_el_registro_pasa_el_contraste_de_la_compuerta(esc: Escenario) -> None:
    assert esc.correr(Falso()) == kv.EXIT_OK
    valor = {"ruta": esc.salida.name, "sha256": hashlib.sha256(esc.salida.read_bytes()).hexdigest()}
    leido = kaggle_prereg._read_record(esc.base, valor, "validez_tareas", kaggle_prereg.VALIDEZ)
    assert leido["entorno_sha256"] == esc.entorno_sha
    # el hash final del diario del registro es el de la ultima linea del diario del crudo
    ultima = (esc.crudo / "diario.jsonl").read_bytes().split(b"\n")[-2]
    assert leido["diario_sha256"] == hashlib.sha256(ultima).hexdigest()
    assert [t["ejecuciones_lanzadas"] for t in leido["tareas"]] == [4, 4, 4]
    # la media que usa la compuerta para s sale de las duraciones sin parche de las que discriminan
    s = kaggle_prereg.setup_minutes(leido)
    assert float(s) == pytest.approx(0.1, abs=1e-9)  # 1,5 s -> 0,025 min -> hacia arriba a 0,1 min


def test_el_registro_es_el_archivo_de_exclusiones_que_lee_kaggle_split(esc: Escenario) -> None:
    ids = [i for i, _ in esc.spec]
    falso = verificador_con_clases(
        esc, {ids[0]: CLASE_PASA, ids[1]: CLASE_NO_MEDIBLE, ids[2]: CLASE_DISCRIMINA}
    )
    assert esc.correr(falso) == kv.EXIT_OK
    excluidas, origen = kaggle_split.load_exclusions(esc.salida)
    assert excluidas == {ids[0], ids[1]}
    assert origen == kaggle_split.ORIGEN_CLAVE_PRESENTE
    assert kaggle_split.load_excluded_task_ids(esc.salida) == {ids[0], ids[1]}


def test_el_orden_de_las_tareas_no_depende_del_archivo(tmp_path: Path) -> None:
    spec = spec_un_repo(4)
    a = nuevo(tmp_path, "a", spec)
    b = nuevo(tmp_path, "b", list(reversed(spec)))
    fa, fb = Falso(), Falso()
    assert a.correr(fa) == kv.EXIT_OK
    assert b.correr(fb) == kv.EXIT_OK
    assert fa.llamadas == fb.llamadas
    assert [x[0] for x in fa.llamadas[::4]] == sorted(i for i, _ in spec)
    # mismo registro salvo el hash de tasks.jsonl (las lineas estan en otro orden)
    ra, rb = a.registro(), b.registro()
    assert ra["tareas"] == rb["tareas"]


def test_guarda_en_main_escribe_el_registro_y_sale_con_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    esc = Escenario(tmp_path, spec_un_repo(10))
    ids = [i for i, _ in esc.spec]
    # 5 de 10 no discriminan: exactamente la mitad, la guarda no salta
    mitad = verificador_con_clases(esc, {i: CLASE_INESTABLE for i in ids[:5]})
    assert esc.correr(mitad) == kv.EXIT_OK
    capsys.readouterr()

    otro = tmp_path / "otro"
    otro.mkdir()
    esc2 = Escenario(otro, spec_un_repo(10))
    seis = verificador_con_clases(esc2, {i: CLASE_INESTABLE for i in ids[:6]})
    assert esc2.correr(seis) == kv.EXIT_FINDING
    err = capsys.readouterr().err
    assert "GUARDA" in err and "owner/a" in err and "6 de 10" in err
    assert esc2.salida.is_file()  # se conserva el registro (A.3: el archivo anterior no se pisa)
    assert len(esc2.registro()["tareas_invalidas"]) == 6


def test_main_dos_repositorios_la_guarda_solo_salta_en_el_que_corresponde(tmp_path: Path) -> None:
    spec = [*spec_un_repo(10, "o/a"), *spec_un_repo(9, "o/b")]
    esc = Escenario(tmp_path, spec)
    # o/b: 9 tareas, todas inestables => por debajo del minimo de 10, no salta
    falso = verificador_con_clases(esc, {i: CLASE_INESTABLE for i, r in spec if r == "o/b"})
    assert esc.correr(falso) == kv.EXIT_OK


def test_no_sobrescribe_el_registro_existente(esc: Escenario, capsys: pytest.CaptureFixture[str]) -> None:
    esc.salida.write_text("anterior", encoding="utf-8")
    falso = Falso()
    assert esc.correr(falso) == kv.EXIT_INVALID
    assert esc.salida.read_text(encoding="utf-8") == "anterior"
    assert falso.llamadas == []  # ni siquiera mide: lo comprueba antes
    assert "no sobrescribe" in capsys.readouterr().err


def test_segunda_corrida_completa_sobre_un_registro_ya_escrito_es_error(esc: Escenario) -> None:
    assert esc.correr(Falso()) == kv.EXIT_OK
    contenido = esc.salida.read_bytes()
    falso = Falso()
    assert esc.correr(falso) == kv.EXIT_INVALID
    assert esc.salida.read_bytes() == contenido
    assert falso.llamadas == []


def test_reanudar_una_corrida_cortada_da_el_mismo_registro(tmp_path: Path) -> None:
    spec = spec_un_repo(3)
    limpio = nuevo(tmp_path, "limpio", spec)
    cortado = nuevo(tmp_path, "cortado", spec)
    assert limpio.correr(Falso()) == kv.EXIT_OK

    corte = Falso()
    corte.explotar_en = 6  # en la segunda tarea
    assert cortado.correr(corte) == kv.EXIT_INVALID
    assert not cortado.salida.exists()
    resto = Falso()
    assert cortado.correr(resto) == kv.EXIT_OK
    assert len(corte.llamadas) - 1 + len(resto.llamadas) == 12  # 3 tareas x 4: ni repite ni pierde
    esperado = limpio.registro()
    obtenido = cortado.registro()
    assert obtenido["tareas"] == esperado["tareas"]
    assert obtenido["tareas_invalidas"] == esperado["tareas_invalidas"]


def test_reanudar_con_otro_entorno_es_error(esc: Escenario, capsys: pytest.CaptureFixture[str]) -> None:
    corte = Falso()
    corte.explotar_en = 2
    assert esc.correr(corte) == kv.EXIT_INVALID
    escribir_entorno(esc.entorno, arreglos=["otro arreglo"])  # cambia el hash de la declaracion
    falso = Falso()
    assert esc.correr(falso) == kv.EXIT_INVALID
    assert falso.llamadas == []
    err = capsys.readouterr().err
    assert "campos que difieren" in err and "entorno_sha256" in err


def test_task_ids_es_parcial_ordenado_y_sin_registro(
    esc: Escenario, capsys: pytest.CaptureFixture[str]
) -> None:
    ids = [i for i, _ in esc.spec]
    falso = Falso()
    assert esc.correr(falso, "--task-ids", ids[2], ids[0], ids[2], salida=False) == kv.EXIT_OK
    assert [x[0] for x in falso.llamadas[::4]] == [ids[0], ids[2]]
    assert not esc.salida.exists()
    assert "no se escribe registro" in capsys.readouterr().out
    # otro ensayo sobre el mismo crudo si se puede reanudar (mismo modo)
    otro = Falso()
    assert esc.correr(otro, "--task-ids", ids[0], ids[1], salida=False) == kv.EXIT_OK
    assert {x[0] for x in otro.llamadas} == {ids[1]}


def test_una_medicion_completa_no_reutiliza_un_ensayo_de_task_ids(
    esc: Escenario, capsys: pytest.CaptureFixture[str]
) -> None:
    ids = [i for i, _ in esc.spec]
    assert esc.correr(Falso(), "--task-ids", ids[0], salida=False) == kv.EXIT_OK
    capsys.readouterr()
    falso = Falso()
    assert esc.correr(falso) == kv.EXIT_INVALID
    assert falso.llamadas == []
    assert "modo" in capsys.readouterr().err
    assert not esc.salida.exists()
    # y al reves: un ensayo no continua una medicion
    otra = nuevo(esc.base, "otra", esc.spec)
    assert otra.correr(Falso()) == kv.EXIT_OK
    assert otra.correr(Falso(), "--task-ids", ids[0], salida=False) == kv.EXIT_INVALID


def test_la_muestra_sobre_el_crudo_de_la_medicion_original_es_salida_2_sin_ejecutar(
    esc: Escenario, capsys: pytest.CaptureFixture[str]
) -> None:
    assert esc.correr(Falso()) == kv.EXIT_OK
    capsys.readouterr()
    falso = Falso()
    comparacion = esc.base / "comparacion.json"
    argv = [*esc.argv(salida=False), "--muestra-desde", str(esc.salida), "--comparacion", str(comparacion)]
    assert kv.main(argv, verificador=falso, reloj=reloj) == kv.EXIT_INVALID
    assert falso.llamadas == []  # no reutiliza ninguna ejecucion de la medicion
    assert not comparacion.exists()
    assert "modo" in capsys.readouterr().err


def test_la_muestra_exige_el_mismo_entorno_que_la_referencia(tmp_path: Path) -> None:
    ref = corrida_completa(tmp_path, spec_un_repo(12), {})
    escribir_entorno(ref.entorno, arreglos=["otro arreglo"])  # otro hash de declaracion
    codigo, comparacion = muestra(ref, tmp_path, Falso())
    assert codigo == kv.EXIT_INVALID
    assert not comparacion.exists()


def test_task_ids_con_salida_o_desconocido_es_error(esc: Escenario) -> None:
    ids = [i for i, _ in esc.spec]
    assert esc.correr(Falso(), "--task-ids", ids[0]) == kv.EXIT_INVALID  # con --salida
    assert esc.correr(Falso(), "--task-ids", "no__existe-1", salida=False) == kv.EXIT_INVALID


def test_swegemma_ausente_es_salida_2_con_mensaje_claro(
    esc: Escenario, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def sin_paquete(nombre: str, *_a: object, **_k: object) -> object:
        raise ImportError(nombre)

    monkeypatch.setattr(importlib, "import_module", sin_paquete)
    monkeypatch.setattr(kv.importlib.metadata, "version", lambda _n: "0.2.7")
    assert esc.correr(None, "--params", str(params_para(esc))) == kv.EXIT_INVALID
    err = capsys.readouterr().err
    assert "swegemma" in err and "no esta instalado" in err
    assert not esc.salida.exists()
    assert not esc.crudo.exists()  # falla antes de crear nada


def test_swegemma_con_otra_version_es_salida_2(
    esc: Escenario, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(kv.importlib.metadata, "version", lambda _n: "9.9.9")
    monkeypatch.setattr(importlib, "import_module", lambda *_a, **_k: object())
    assert esc.correr(None, "--params", str(params_para(esc))) == kv.EXIT_INVALID
    assert "9.9.9" in capsys.readouterr().err


def test_la_verificacion_real_exige_params(esc: Escenario, capsys: pytest.CaptureFixture[str]) -> None:
    assert esc.correr(None) == kv.EXIT_INVALID
    assert "--params" in capsys.readouterr().err


def test_imagen_o_backend_distintos_de_la_declaracion_es_salida_2(esc: Escenario) -> None:
    argv = esc.argv()
    argv[argv.index("--imagen") + 1] = "otra:imagen"
    assert kv.main(argv, verificador=Falso(), reloj=reloj) == kv.EXIT_INVALID
    argv = esc.argv()
    argv[argv.index("--sandbox") + 1] = "docker"
    assert kv.main(argv, verificador=Falso(), reloj=reloj) == kv.EXIT_INVALID


@pytest.mark.parametrize(
    "cambio", [{"schema_version": "otro/1"}, {"backend": "nube"}, {"ruedas_sha256": "xyz"}]
)
def test_declaracion_de_entorno_invalida_es_salida_2(esc: Escenario, cambio: dict[str, object]) -> None:
    escribir_entorno(esc.entorno, **cambio)
    assert esc.correr(Falso()) == kv.EXIT_INVALID


def test_declaracion_de_entorno_con_clave_de_mas_o_ilegible_es_salida_2(esc: Escenario) -> None:
    esc.entorno.write_text(json.dumps({**ENTORNO, "extra": 1}), encoding="utf-8")
    assert esc.correr(Falso()) == kv.EXIT_INVALID
    esc.entorno.write_text("no json", encoding="utf-8")
    assert esc.correr(Falso()) == kv.EXIT_INVALID
    esc.entorno.unlink()
    assert esc.correr(Falso()) == kv.EXIT_INVALID


def test_params_exige_el_hash_registrado_de_tasks(esc: Escenario, tmp_path: Path) -> None:
    params = tmp_path / "params.json"
    datos = json.loads(kaggle_prereg.DEFAULT_PARAMS.read_text(encoding="utf-8"))
    params.write_text(json.dumps(datos), encoding="utf-8")
    assert esc.correr(Falso(), "--params", str(params)) == kv.EXIT_INVALID  # tasks sintetico != registrado
    datos["fijos"]["tasks_sha256"] = hashlib.sha256(esc.tasks.read_bytes()).hexdigest()
    params.write_text(json.dumps(datos), encoding="utf-8")
    assert esc.correr(Falso(), "--params", str(params)) == kv.EXIT_OK
    assert esc.correr(Falso(), "--params", str(tmp_path / "no_existe.json")) == kv.EXIT_INVALID


@pytest.mark.parametrize(
    "nombre",
    [
        "validez_tareas_v3.json",
        "validez_tareas_V3.json",
        "validez_tareas-v3.json",
        "validez_tareas_v3_final.json",
        "validez_tareas_v10.json",
    ],
)
def test_tercera_medicion_se_rechaza_con_cualquier_forma_del_nombre(esc: Escenario, nombre: str) -> None:
    argv = esc.argv()
    argv[argv.index("--salida") + 1] = str(esc.base / nombre)
    falso = Falso()
    assert kv.main(argv, verificador=falso, reloj=reloj) == kv.EXIT_INVALID
    assert falso.llamadas == []


def test_v2_exige_el_v1_conservado_y_un_entorno_distinto(
    esc: Escenario, capsys: pytest.CaptureFixture[str]
) -> None:
    v2 = esc.base / "validez_tareas_v2.json"
    argv2 = esc.argv()
    argv2[argv2.index("--salida") + 1] = str(v2)
    # sin v1
    assert kv.main(argv2, verificador=Falso(), reloj=reloj) == kv.EXIT_INVALID
    assert "_v1" in capsys.readouterr().err
    # con v1 y el mismo entorno
    assert esc.correr(Falso()) == kv.EXIT_OK
    falso = Falso()
    assert kv.main(argv2, verificador=falso, reloj=reloj) == kv.EXIT_INVALID
    assert falso.llamadas == []
    assert "entorno distinto" in capsys.readouterr().err
    # con v1 y un entorno nuevo declarado (otro crudo: el manifiesto es de otro entorno)
    escribir_entorno(esc.entorno, arreglos=["rueda anadida"])
    argv2[argv2.index("--crudo") + 1] = str(esc.base / "crudo_v2")
    assert kv.main(argv2, verificador=Falso(), reloj=reloj) == kv.EXIT_OK
    assert v2.is_file() and esc.salida.is_file()  # el v1 se conserva


def test_registro_dentro_de_crudo_se_rechaza(esc: Escenario) -> None:
    argv = esc.argv()
    argv[argv.index("--salida") + 1] = str(esc.crudo / "validez_tareas_v1.json")
    assert kv.main(argv, verificador=Falso(), reloj=reloj) == kv.EXIT_INVALID


def test_crudo_versionado_se_rechaza_antes_de_medir(esc: Escenario) -> None:
    git(esc.base, "init", "-q")
    falso = Falso()
    assert esc.correr(falso) == kv.EXIT_INVALID  # crudo dentro del repo y sin ignorar
    assert falso.llamadas == []
    assert not esc.crudo.exists()
    (esc.base / ".gitignore").write_text("crudo/\n", encoding="utf-8")
    assert esc.correr(falso) == kv.EXIT_OK


def test_error_del_arnes_sin_categoria_es_salida_2_y_no_filtra_su_texto(
    esc: Escenario, capsys: pytest.CaptureFixture[str]
) -> None:
    ids = [i for i, _ in esc.spec]
    raro = ResultadoVerificacion(False, 1, f"Mensaje nuevo del arnes {POISON_ERROR}", 1.0)
    falso = Falso({(ids[0], kv.VERIF_DORADO): [raro]})
    assert esc.correr(falso) == kv.EXIT_INVALID
    capturado = capsys.readouterr()
    assert POISON_ERROR not in capturado.out + capturado.err
    assert not esc.salida.exists()
    # nada se guardo de esa ejecucion: se puede reanudar tras arreglar el clasificador
    assert not (esc.crudo / "ejecuciones" / ids[0] / "dorado_1_1.json").exists()


def test_fallo_del_verificador_en_main_es_salida_2(
    esc: Escenario, capsys: pytest.CaptureFixture[str]
) -> None:
    falso = Falso()
    falso.explotar_en = 1
    assert esc.correr(falso) == kv.EXIT_INVALID
    err = capsys.readouterr().err
    assert "RuntimeError" in err and POISON_ERROR not in err


def test_error_inesperado_del_script_es_salida_3(
    esc: Escenario, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def roto(*_a: object, **_k: object) -> None:
        raise ZeroDivisionError

    monkeypatch.setattr(kv, "medir_tarea", roto)
    assert esc.correr(Falso()) == kv.EXIT_UNEXPECTED
    assert "ERROR INESPERADO" in capsys.readouterr().err


def test_codigos_de_salida_son_distintos() -> None:
    codigos = (kv.EXIT_OK, kv.EXIT_FINDING, kv.EXIT_INVALID, kv.EXIT_UNEXPECTED)
    assert codigos == (0, 1, 2, 3)


def test_opciones_incompatibles_son_salida_2(esc: Escenario) -> None:
    assert esc.correr(Falso(), salida=False) == kv.EXIT_INVALID  # completa sin --salida
    assert esc.correr(Falso(), "--comparacion", str(esc.base / "c.json")) == kv.EXIT_INVALID
    assert (
        esc.correr(Falso(), "--muestra-desde", str(esc.base / "r.json")) == kv.EXIT_INVALID
    )  # sin --comparacion


def test_muestra_junto_con_task_ids_o_salida_es_salida_2(tmp_path: Path) -> None:
    ref = corrida_completa(tmp_path, spec_un_repo(12), {})
    base = [
        "--tasks", str(ref.tasks), "--snapshots-dir", str(ref.snapshots), "--entorno", str(ref.entorno),
        "--imagen", "sandbox:prueba", "--sandbox", "subprocess", "--crudo", str(tmp_path / "otro_crudo"),
        "--muestra-desde", str(ref.salida), "--comparacion", str(tmp_path / "c.json"),
    ]  # fmt: skip
    falso = Falso()
    assert kv.main([*base, "--task-ids", ref.spec[0][0]], verificador=falso, reloj=reloj) == kv.EXIT_INVALID
    assert kv.main([*base, "--salida", str(tmp_path / "s_v1.json")], verificador=falso, reloj=reloj) == (
        kv.EXIT_INVALID
    )
    assert falso.llamadas == []
    assert not (tmp_path / "otro_crudo").exists()


def test_tasks_inexistente_o_invalido_es_salida_2(esc: Escenario) -> None:
    esc.tasks.unlink()
    assert esc.correr(Falso()) == kv.EXIT_INVALID
    esc.tasks.write_text("no json\n", encoding="utf-8")
    assert esc.correr(Falso()) == kv.EXIT_INVALID
    esc.tasks.write_text("", encoding="utf-8")
    assert esc.correr(Falso()) == kv.EXIT_INVALID
    esc.tasks.write_text(json.dumps({"instance_id": "a__b-1"}) + "\n", encoding="utf-8")  # sin repo
    assert esc.correr(Falso()) == kv.EXIT_INVALID
    dup = json.dumps({"instance_id": "a__b-1", "repo": "o/a"})
    esc.tasks.write_text(f"{dup}\n{dup}\n", encoding="utf-8")
    assert esc.correr(Falso()) == kv.EXIT_INVALID
    clave_repetida = '{"instance_id": "a__b-1", "instance_id": "a__b-2", "repo": "o/a"}'
    esc.tasks.write_text(clave_repetida + "\n", encoding="utf-8")
    assert esc.correr(Falso()) == kv.EXIT_INVALID
    esc.tasks.write_text(json.dumps({"instance_id": "../x", "repo": "o/a"}) + "\n", encoding="utf-8")
    assert esc.correr(Falso()) == kv.EXIT_INVALID


# ---------------------------------------------------------------------------
# Frontera de fuga: datos envenenados
# ---------------------------------------------------------------------------


def todas_las_cadenas(obj: object) -> list[str]:
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        return [s for k, v in obj.items() for s in (*todas_las_cadenas(k), *todas_las_cadenas(v))]
    if isinstance(obj, list):
        return [s for v in obj for s in todas_las_cadenas(v)]
    return []


def test_el_registro_versionable_no_contiene_ninguna_cadena_envenenada(
    esc: Escenario, capsys: pytest.CaptureFixture[str]
) -> None:
    ids = [i for i, _ in esc.spec]
    clases = {ids[0]: CLASE_DISCRIMINA, ids[1]: CLASE_NO_MEDIBLE, ids[2]: CLASE_DORADO_FALLA}
    assert esc.correr(verificador_con_clases(esc, clases)) == kv.EXIT_OK
    texto = esc.salida.read_text(encoding="utf-8")
    consola = capsys.readouterr()
    for veneno in POISON_TODOS:
        assert veneno not in texto, veneno
        assert veneno not in consola.out + consola.err, veneno
        # el veneno si esta en la salida cruda: la prueba no pasa en vacio
    crudo = "".join(p.read_text(encoding="utf-8") for p in (esc.crudo / "ejecuciones").rglob("*.json"))
    assert POISON_LOG in crudo and POISON_TEST in crudo and POISON_ERROR in crudo

    # estructura: toda cadena del registro es de un conjunto cerrado o tiene forma de id, fecha o hash
    permitidas = {
        "kaggle-task-validity/1",
        *ids,
        "owner/a",
        *kaggle_prereg.CLASES_VALIDEZ,
        *kv.ESTADOS,
        *kv.CATEGORIAS,
        kv.VERIF_SIN,
        kv.VERIF_DORADO,
        *kv.CLAVES_TAREA,
        *kv.CLAVES_EJECUCION_VERSIONADAS,
        *kaggle_prereg.VALIDEZ,
        "2026-10-05",
        esc.entorno_sha,
        hashlib.sha256(esc.tasks.read_bytes()).hexdigest(),
    }
    registro = json.loads(texto)
    cadenas = set(todas_las_cadenas(registro))
    # la unica cadena que no es de un conjunto cerrado es el hash final del diario
    assert cadenas - permitidas == {registro["diario_sha256"]}
    # ningun texto sobrante: ni el hash del parche de referencia
    parche_sha = hashlib.sha256(POISON_PARCHE.encode()).hexdigest()
    assert parche_sha not in texto


def test_el_registro_no_lleva_conteos_ni_fecha_por_ejecucion(esc: Escenario) -> None:
    """A.4 no los enumera: quedan solo en el crudo."""
    assert esc.correr(Falso()) == kv.EXIT_OK
    texto = esc.salida.read_text(encoding="utf-8")
    for clave in ('"passed"', '"failed"', '"errors"', '"fecha_utc"'):
        assert clave not in texto
    for t in esc.registro()["tareas"]:
        for x in t["ejecuciones"]:
            assert isinstance(x["codigo_salida"], int)
            assert isinstance(x["duracion_segundos"], float)
    crudo = "".join(p.read_text(encoding="utf-8") for p in (esc.crudo / "ejecuciones").rglob("*.json"))
    assert '"passed"' in crudo and '"fecha_utc"' in crudo


def test_validar_registro_detecta_defectos(esc: Escenario) -> None:
    assert esc.correr(Falso()) == kv.EXIT_OK
    base = esc.registro()

    def con(mutar: Callable[[dict[str, Any]], None]) -> list[str]:
        copia = json.loads(json.dumps(base))
        mutar(copia)
        return kv.validar_registro(copia)

    assert kv.validar_registro(base) == []
    assert kv.validar_registro([]) != []
    assert con(lambda d: d.update(extra=1))  # clave de mas en el primer nivel
    assert con(lambda d: d["tareas"][0].update(patch="x"))  # clave de mas en una tarea
    assert con(lambda d: d["tareas"][0]["ejecuciones"][0].update(error="texto"))
    assert con(lambda d: d["tareas"][0]["ejecuciones"][0].update(categoria="texto libre"))
    assert con(lambda d: d["tareas"][0].update(clase="rara"))
    assert con(lambda d: d["tareas"][0]["ejecuciones"][0].update(estado="otro"))
    assert con(lambda d: d["tareas_invalidas"].append({"instance_id": "zzz", "clase": "inestable"}))
    assert con(lambda d: d["tareas"][0].update(clase="inestable"))  # invalida y no esta en la lista
    assert con(lambda d: d.update(sha256_tasks="no"))
    assert con(lambda d: d.pop("diario_sha256"))
    assert con(lambda d: d.update(diario_sha256="zz"))
    assert con(lambda d: d["tareas"][0].update(ejecuciones_lanzadas=7))
    assert con(lambda d: d["tareas"][0].pop("ejecuciones_lanzadas"))
    assert con(lambda d: d["tareas"][0]["ejecuciones"][0].update(fecha_utc=POISON_TEST))  # clave de mas
    assert con(lambda d: d["tareas"][0]["ejecuciones"][0].pop("duracion_segundos"))


# ---------------------------------------------------------------------------
# Modo muestra
# ---------------------------------------------------------------------------


def test_orden_muestra_es_por_sha256_del_instance_id() -> None:
    ids = [f"pkg__x-{i}" for i in range(20)]
    esperado = sorted(ids, key=lambda i: hashlib.sha256(i.encode()).hexdigest())
    assert kv.orden_muestra(ids) == esperado
    assert kv.orden_muestra(list(reversed(ids))) == esperado


def test_elegir_tareas_muestra_son_las_excluidas_mas_las_10_primeras_por_hash() -> None:
    spec = spec_un_repo(40)
    todas = [Tarea(i, r) for i, r in spec]
    excluidas = [spec[3][0], spec[17][0], spec[33][0]]
    referencia = {
        "tareas": [
            {"instance_id": i, "clase": CLASE_INESTABLE if i in excluidas else CLASE_DISCRIMINA}
            for i, _ in spec
        ]
    }
    elegidas = kv.elegir_tareas(todas, None, referencia)
    primeras = sorted(spec, key=lambda s: hashlib.sha256(s[0].encode()).hexdigest())[:10]
    esperado = sorted({*excluidas, *(i for i, _ in primeras)})
    assert [t.instance_id for t in elegidas] == esperado
    assert len(elegidas) >= 10
    # sin referencia ni lista: todas, ordenadas; con lista: solo esas
    assert [t.instance_id for t in kv.elegir_tareas(todas, None, None)] == sorted(i for i, _ in spec)
    assert [t.instance_id for t in kv.elegir_tareas(todas, [spec[5][0]], None)] == [spec[5][0]]
    with pytest.raises(ValidezError):
        kv.elegir_tareas(todas, ["no__esta-1"], None)


def corrida_completa(tmp_path: Path, spec: list[tuple[str, str]], clases: dict[str, str]) -> Escenario:
    base = tmp_path / "referencia"
    base.mkdir()
    esc = Escenario(base, spec)
    assert esc.correr(verificador_con_clases(esc, clases)) in (kv.EXIT_OK, kv.EXIT_FINDING)
    return esc


def muestra(esc: Escenario, tmp_path: Path, verificador: Falso) -> tuple[int, Path]:
    base = tmp_path / "repeticion"
    base.mkdir(exist_ok=True)
    comparacion = base / "comparacion.json"
    argv = [
        "--tasks", str(esc.tasks), "--snapshots-dir", str(esc.snapshots), "--entorno", str(esc.entorno),
        "--imagen", "sandbox:prueba", "--sandbox", "subprocess", "--crudo", str(base / "crudo"),
        "--muestra-desde", str(esc.salida), "--comparacion", str(comparacion),
    ]  # fmt: skip
    return kv.main(argv, verificador=verificador, reloj=reloj), comparacion


def test_muestra_que_coincide_sale_con_0(tmp_path: Path) -> None:
    spec = spec_un_repo(14)
    ids = [i for i, _ in spec]
    clases = {ids[1]: CLASE_PASA, ids[6]: CLASE_NO_MEDIBLE}
    ref = corrida_completa(tmp_path, spec, clases)
    falso = verificador_con_clases(ref, clases)
    codigo, comparacion = muestra(ref, tmp_path, falso)
    assert codigo == kv.EXIT_OK
    datos = json.loads(comparacion.read_text(encoding="utf-8"))
    assert datos["schema_version"] == "kaggle-task-validity-sample/1"
    assert datos["coincide"] is True
    medidas = {f["instance_id"] for f in datos["tareas"]}
    assert {ids[1], ids[6]} <= medidas  # las excluidas siempre estan
    assert len(medidas) >= 10
    assert all(f["clase_referencia"] == f["clase_repeticion"] for f in datos["tareas"])
    assert len({x[0] for x in falso.llamadas}) == len(medidas)  # solo mide la muestra


def test_muestra_con_una_clase_distinta_sale_con_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    spec = spec_un_repo(14)
    ids = [i for i, _ in spec]
    ref = corrida_completa(tmp_path, spec, {ids[1]: CLASE_PASA})
    # en la repeticion la tarea excluida ya no pasa sin parche: ahora discrimina
    codigo, comparacion = muestra(ref, tmp_path, Falso())
    assert codigo == kv.EXIT_FINDING
    datos = json.loads(comparacion.read_text(encoding="utf-8"))
    assert datos["coincide"] is False
    distinta = [f for f in datos["tareas"] if not f["coincide"]]
    assert [(f["instance_id"], f["clase_referencia"], f["clase_repeticion"]) for f in distinta] == [
        (ids[1], CLASE_PASA, CLASE_DISCRIMINA)
    ]
    assert "HALLAZGO" in capsys.readouterr().err


def test_muestra_una_tarea_de_la_muestra_con_otra_clase_aunque_no_estaba_excluida(tmp_path: Path) -> None:
    spec = spec_un_repo(14)
    ids = [i for i, _ in spec]
    ref = corrida_completa(tmp_path, spec, {})
    primera = kv.orden_muestra(ids)[0]
    codigo, comparacion = muestra(ref, tmp_path, verificador_con_clases(ref, {primera: CLASE_DORADO_FALLA}))
    assert codigo == kv.EXIT_FINDING
    datos = json.loads(comparacion.read_text(encoding="utf-8"))
    assert [f["instance_id"] for f in datos["tareas"] if not f["coincide"]] == [primera]


def test_muestra_no_sobrescribe_la_comparacion_ni_acepta_otro_tasks(tmp_path: Path) -> None:
    spec = spec_un_repo(12)
    ref = corrida_completa(tmp_path, spec, {})
    codigo, comparacion = muestra(ref, tmp_path, Falso())
    assert codigo == kv.EXIT_OK
    contenido = comparacion.read_bytes()
    otra, _ = muestra(ref, tmp_path, Falso())  # la comparacion ya existe
    assert otra == kv.EXIT_INVALID
    assert comparacion.read_bytes() == contenido
    # otro tasks.jsonl: la referencia es de otro archivo
    ref.tasks.write_text(ref.tasks.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    comparacion.unlink()
    (tmp_path / "repeticion" / "crudo").rename(tmp_path / "repeticion" / "crudo_viejo")
    codigo, _ = muestra(ref, tmp_path, Falso())
    assert codigo == kv.EXIT_INVALID


def test_muestra_con_referencia_invalida_es_salida_2(tmp_path: Path) -> None:
    spec = spec_un_repo(12)
    ref = corrida_completa(tmp_path, spec, {})
    ref.salida.write_text("[]", encoding="utf-8")
    codigo, _ = muestra(ref, tmp_path, Falso())
    assert codigo == kv.EXIT_INVALID
    ref.salida.write_text("no json", encoding="utf-8")
    codigo, _ = muestra(ref, tmp_path, Falso())
    assert codigo == kv.EXIT_INVALID


# ---------------------------------------------------------------------------
# Verificador real: solo la importacion perezosa (swegemma no se importa en estas pruebas)
# ---------------------------------------------------------------------------


def test_el_modulo_no_importa_swegemma_al_cargarse() -> None:
    fuente = Path(kv.__file__).read_text(encoding="utf-8")
    lineas = [
        ln for ln in fuente.splitlines() if ln.startswith(("import swegemma", "from swegemma", "import adk"))
    ]
    assert lineas == []


def test_construir_verificador_sin_paquete(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def sin_version(_n: str) -> str:
        raise kv.importlib.metadata.PackageNotFoundError

    monkeypatch.setattr(kv.importlib.metadata, "version", sin_version)
    with pytest.raises(ValidezError, match="no esta instalado"):
        kv.construir_arnes_swegemma(
            tasks_path=tmp_path / "t.jsonl",
            snapshots_dir=tmp_path,
            crudo=tmp_path,
            imagen="i",
            sandbox="subprocess",
            version_arnes="0.2.7",
            timeout_seconds=300,
        )


def test_comprobar_timeout() -> None:
    kv.comprobar_timeout(300, 300)
    with pytest.raises(ValidezError, match="timeout"):
        kv.comprobar_timeout(300, 600)
    with pytest.raises(ValidezError):
        kv.comprobar_timeout(300, None)


def test_la_limpieza_del_sandbox_se_llama_al_terminar_y_tambien_si_falla(
    esc: Escenario, monkeypatch: pytest.MonkeyPatch
) -> None:
    llamadas: list[str] = []
    falso = Falso()

    def arnes(**_k: object) -> kv.Arnes:
        return kv.Arnes(falso, lambda _t: 0, lambda: llamadas.append("limpiar"))

    monkeypatch.setattr(kv, "construir_arnes_swegemma", arnes)
    assert esc.correr(None, "--params", str(params_para(esc))) == kv.EXIT_OK
    assert llamadas == ["limpiar"]
    # si la medicion falla, tambien se limpia
    otro = nuevo(esc.base, "otro", esc.spec)
    roto = Falso()
    roto.explotar_en = 1
    monkeypatch.setattr(
        kv,
        "construir_arnes_swegemma",
        lambda **_k: kv.Arnes(roto, lambda _t: 0, lambda: llamadas.append("limpiar")),
    )
    assert otro.correr(None, "--params", str(params_para(otro))) == kv.EXIT_INVALID
    assert llamadas == ["limpiar", "limpiar"]

    # un fallo de la propia limpieza no cambia el resultado
    def mala() -> None:
        raise RuntimeError

    tercero = nuevo(esc.base, "tercero", esc.spec)
    monkeypatch.setattr(kv, "construir_arnes_swegemma", lambda **_k: kv.Arnes(Falso(), lambda _t: 0, mala))
    assert tercero.correr(None, "--params", str(params_para(tercero))) == kv.EXIT_OK


def test_el_arnes_real_recibe_el_timeout_del_preregistro(
    esc: Escenario, monkeypatch: pytest.MonkeyPatch
) -> None:
    recibido: dict[str, object] = {}

    def arnes(**k: object) -> kv.Arnes:
        recibido.update(k)
        return kv.Arnes(Falso(), lambda _t: 0, lambda: None)

    monkeypatch.setattr(kv, "construir_arnes_swegemma", arnes)
    assert esc.correr(None, "--params", str(params_para(esc))) == kv.EXIT_OK
    fijos = json.loads(kaggle_prereg.DEFAULT_PARAMS.read_text(encoding="utf-8"))["fijos"]
    assert recibido["timeout_seconds"] == fijos["timeout_seconds"] == 60
    assert recibido["version_arnes"] == "0.2.7"


# ---------------------------------------------------------------------------
# Diario de solo-anadir
# ---------------------------------------------------------------------------


def lineas_diario(raiz: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in (raiz / "diario.jsonl").read_bytes().split(b"\n")[:-1]]


def test_el_diario_tiene_una_linea_por_ejecucion_lanzada_y_encadena_hashes(esc: Escenario) -> None:
    ids = [i for i, _ in esc.spec]
    falso = verificador_con_clases(esc, {ids[1]: CLASE_NO_MEDIBLE})  # 5 ejecuciones: 1 repeticion
    assert esc.correr(falso) == kv.EXIT_OK
    lineas = lineas_diario(esc.crudo)
    assert len(lineas) == len(falso.llamadas) == 13
    assert [x["n"] for x in lineas] == list(range(1, 14))
    previo = kv.GENESIS
    crudas = (esc.crudo / "diario.jsonl").read_bytes().split(b"\n")[:-1]
    for obj, cruda in zip(lineas, crudas, strict=True):
        assert obj["previo"] == previo
        previo = hashlib.sha256(cruda).hexdigest()
        ruta = (
            esc.crudo
            / "ejecuciones"
            / obj["instance_id"]
            / f"{obj['verificacion']}_{obj['numero']}_{obj['intento']}.json"
        )
        assert obj["sha256_ejecucion"] == hashlib.sha256(ruta.read_bytes()).hexdigest()
        assert obj["fecha_utc"] == FECHA_UTC
    assert len({x["corrida"] for x in lineas}) == 1
    registro = esc.registro()
    assert registro["diario_sha256"] == previo
    por_tarea = {t["instance_id"]: t["ejecuciones_lanzadas"] for t in registro["tareas"]}
    assert por_tarea == {ids[0]: 4, ids[1]: 5, ids[2]: 4}


def test_el_diario_sobrevive_a_una_reanudacion_con_la_cadena_intacta(tmp_path: Path) -> None:
    limpio = nuevo(tmp_path, "limpio", spec_un_repo(3))
    cortado = nuevo(tmp_path, "cortado", spec_un_repo(3))
    assert limpio.correr(Falso()) == kv.EXIT_OK
    corte = Falso()
    corte.explotar_en = 6
    assert cortado.correr(corte) == kv.EXIT_INVALID
    assert cortado.correr(Falso()) == kv.EXIT_OK
    a, b = limpio.registro(), cortado.registro()
    assert [t["ejecuciones_lanzadas"] for t in a["tareas"]] == [
        t["ejecuciones_lanzadas"] for t in b["tareas"]
    ]
    assert len(lineas_diario(cortado.crudo)) == 12
    assert [x["n"] for x in lineas_diario(cortado.crudo)] == list(range(1, 13))


def cortada(esc: Escenario) -> list[str]:
    """Deja una medicion completa y devuelve los ids; el registro se borra para poder reanudar."""
    assert esc.correr(Falso()) == kv.EXIT_OK
    esc.salida.unlink()
    return [i for i, _ in esc.spec]


def test_borrar_una_ejecucion_y_relanzar_es_salida_2(
    esc: Escenario, capsys: pytest.CaptureFixture[str]
) -> None:
    """Antes: borrar ``sin_parche_1_1.json`` y relanzar podia cambiar el resultado sin rastro."""
    ids = [i for i, _ in esc.spec]
    falso = verificador_con_clases(esc, {ids[0]: CLASE_INESTABLE})
    assert esc.correr(falso) == kv.EXIT_OK
    esc.salida.unlink()
    (esc.crudo / "ejecuciones" / ids[0] / "sin_parche_1_1.json").unlink()
    nuevo_falso = Falso()  # la repeticion «elegiria» otro resultado
    assert esc.correr(nuevo_falso) == kv.EXIT_INVALID
    assert nuevo_falso.llamadas == []
    assert "diario" in capsys.readouterr().err
    assert not esc.salida.exists()


def test_una_ejecucion_en_disco_que_no_esta_en_el_diario_es_salida_2(esc: Escenario) -> None:
    ids = cortada(esc)
    carpeta = esc.crudo / "ejecuciones" / ids[0]
    (carpeta / "sin_parche_1_2.json").write_bytes((carpeta / "sin_parche_1_1.json").read_bytes())
    falso = Falso()
    assert esc.correr(falso) == kv.EXIT_INVALID
    assert falso.llamadas == []
    (carpeta / "sin_parche_1_2.json").unlink()
    (carpeta / "raro.json").write_text("{}", encoding="utf-8")  # nombre que no es de una ejecucion
    assert esc.correr(falso) == kv.EXIT_INVALID


def test_una_ejecucion_ajena_a_la_seleccion_tambien_se_detecta(esc: Escenario) -> None:
    """Solo el recorrido del disco la ve: la tarea sobrante no se vuelve a leer en esta corrida."""
    ids = [i for i, _ in esc.spec]
    assert esc.correr(Falso(), "--task-ids", ids[0], ids[2], salida=False) == kv.EXIT_OK
    carpeta = esc.crudo / "ejecuciones" / ids[2]
    (carpeta / "dorado_2_1.json").unlink()  # borrada sin tocar el diario
    falso = Falso()
    assert esc.correr(falso, "--task-ids", ids[0], salida=False) == kv.EXIT_INVALID
    assert falso.llamadas == []
    otro = nuevo(esc.base, "otro", esc.spec)
    assert otro.correr(Falso(), "--task-ids", ids[0], ids[2], salida=False) == kv.EXIT_OK
    huerfana = otro.crudo / "ejecuciones" / ids[2] / "dorado_2_1.json"
    huerfana.with_name("dorado_2_2.json").write_bytes(huerfana.read_bytes())  # sobra en disco
    assert otro.correr(falso, "--task-ids", ids[0], salida=False) == kv.EXIT_INVALID
    assert falso.llamadas == []


def test_un_temporal_de_una_escritura_cortada_no_cuenta_como_ejecucion(esc: Escenario) -> None:
    ids = cortada(esc)
    (esc.crudo / "ejecuciones" / ids[0] / ".sin_parche_1_1.json.abc.tmp").write_bytes(b"medio escrito")
    assert esc.correr(Falso()) == kv.EXIT_OK


def test_editar_una_ejecucion_sin_rehacer_el_diario_es_salida_2(esc: Escenario) -> None:
    ids = cortada(esc)
    ruta = esc.crudo / "ejecuciones" / ids[0] / "dorado_1_1.json"
    obj = json.loads(ruta.read_text(encoding="utf-8"))
    obj["resultado"].update(resolved=False, test_exit_code=1, error=None)
    obj["registro"].update(resolved=False, estado="unresolved", categoria="tests_failed", codigo_salida=1)
    ruta.write_text(json.dumps(obj), encoding="utf-8")  # resultado y registro a la vez
    falso = Falso()
    assert esc.correr(falso) == kv.EXIT_INVALID
    assert falso.llamadas == []


def reescribir_diario(esc: Escenario, mutar: Callable[[list[bytes]], list[bytes]]) -> None:
    ruta = esc.crudo / "diario.jsonl"
    lineas = ruta.read_bytes().split(b"\n")[:-1]
    ruta.write_bytes(b"".join(x + b"\n" for x in mutar(lineas)))


@pytest.mark.parametrize(
    "mutar",
    [
        lambda ls: ls[:-1],  # se quita la ultima linea: su ejecucion queda sin anotar
        lambda ls: ls[1:],  # se quita la primera: la cadena se rompe
        lambda ls: [ls[1], ls[0], *ls[2:]],  # se reordenan
        lambda ls: [ls[0], ls[0], *ls[1:]],  # se duplica
        lambda ls: [ls[0].replace(b"sin_parche", b"dorado"), *ls[1:]],  # se edita una linea
        lambda ls: [b"no es json", *ls[1:]],
        lambda ls: [*ls, b"{}"],
    ],
)
def test_un_diario_manipulado_es_salida_2(
    esc: Escenario, mutar: Callable[[list[bytes]], list[bytes]]
) -> None:
    cortada(esc)
    reescribir_diario(esc, mutar)
    falso = Falso()
    assert esc.correr(falso) == kv.EXIT_INVALID
    assert falso.llamadas == []


def test_un_diario_truncado_o_de_otra_corrida_es_salida_2(esc: Escenario) -> None:
    cortada(esc)
    ruta = esc.crudo / "diario.jsonl"
    original = ruta.read_bytes()
    ruta.write_bytes(original[:-1])  # sin el salto de linea final
    assert esc.correr(Falso()) == kv.EXIT_INVALID
    ruta.write_bytes(original.replace(b'"corrida":"', b'"corrida":"x'))
    assert esc.correr(Falso()) == kv.EXIT_INVALID
    ruta.write_bytes(original)
    assert esc.correr(Falso()) == kv.EXIT_OK  # el diario original sigue valiendo


def test_borrar_el_diario_entero_es_salida_2(esc: Escenario) -> None:
    cortada(esc)
    (esc.crudo / "diario.jsonl").unlink()
    assert esc.correr(Falso()) == kv.EXIT_INVALID  # las ejecuciones en disco no estan anotadas


def test_el_hash_final_del_diario_cambia_si_cambia_una_ejecucion(tmp_path: Path) -> None:
    a = nuevo(tmp_path, "a", spec_un_repo(3))
    b = nuevo(tmp_path, "b", spec_un_repo(3))
    assert a.correr(Falso()) == kv.EXIT_OK
    ids = [i for i, _ in b.spec]
    assert b.correr(verificador_con_clases(b, {ids[2]: CLASE_PASA})) == kv.EXIT_OK
    assert a.registro()["diario_sha256"] != b.registro()["diario_sha256"]


# ---------------------------------------------------------------------------
# fecha_utc del crudo: el unico texto libre que podria cruzar la frontera
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "valor",
    [
        POISON_TEST,
        "",
        "2026-10-05T12:00:00",
        "2026-10-05 12:00:00Z",
        "2026-13-45T00:00:00Z",
        FECHA_UTC + "\n",
        5,
        None,
    ],
)
def test_validar_fecha_utc_rechaza_todo_lo_que_no_es_el_formato(valor: object) -> None:
    with pytest.raises(ValidezError) as info:
        kv.validar_fecha_utc(valor)
    assert POISON_TEST not in str(info.value)


def test_validar_fecha_utc_acepta_el_formato() -> None:
    assert kv.validar_fecha_utc(FECHA_UTC) == FECHA_UTC


def test_registro_de_ejecucion_rechaza_una_fecha_envenenada() -> None:
    with pytest.raises(ValidezError):
        kv.registro_de_ejecucion(ok(), "sin_parche", 1, 1, POISON_TEST)


def test_una_fecha_envenenada_en_el_crudo_no_llega_al_registro_y_es_salida_2(
    esc: Escenario, capsys: pytest.CaptureFixture[str]
) -> None:
    ids = cortada(esc)
    ruta = esc.crudo / "ejecuciones" / ids[0] / "sin_parche_1_1.json"
    obj = json.loads(ruta.read_text(encoding="utf-8"))
    obj["registro"]["fecha_utc"] = POISON_TEST
    ruta.write_text(json.dumps(obj), encoding="utf-8")
    rehacer_diario(esc.crudo)
    assert esc.correr(Falso()) == kv.EXIT_INVALID
    capturado = capsys.readouterr()
    assert POISON_TEST not in capturado.out + capturado.err
    assert not esc.salida.exists()


def test_una_fecha_envenenada_en_el_diario_es_salida_2(esc: Escenario) -> None:
    cortada(esc)
    reescribir_diario(esc, lambda ls: [ls[0].replace(FECHA_UTC.encode(), POISON_TEST.encode()), *ls[1:]])
    assert esc.correr(Falso()) == kv.EXIT_INVALID


# ---------------------------------------------------------------------------
# Snapshots, manifiesto y loggers
# ---------------------------------------------------------------------------


def resolver_falso(snapshots_dir: Path, instance_id: str, repo: str) -> tuple[Path, Path | None, Path | None]:
    return snapshots_dir / f"{instance_id}.tgz", None, None


def test_snapshots_faltantes_con_las_dos_ubicaciones(tmp_path: Path) -> None:
    principal = tmp_path / "snapshots"
    secreta = tmp_path / "secret"
    (secreta / "sandbox" / "snapshots").mkdir(parents=True)
    principal.mkdir()
    tareas = [Tarea(f"x__y-{i}", "o/r") for i in range(4)]
    (principal / "x__y-0.tgz").write_bytes(b"")
    (secreta / "sandbox" / "snapshots" / "x__y-1.tgz").write_bytes(b"")
    (secreta / "sandbox" / "snapshots" / "x__y-0.tgz").write_bytes(b"")
    assert kv.contar_snapshots_faltantes(tareas, resolver_falso, principal, secreta) == 2  # 2 y 3
    assert kv.contar_snapshots_faltantes(tareas, resolver_falso, principal, None) == 3  # sin la segunda
    ruta, _, _ = kv.ubicar_snapshot(resolver_falso, principal, secreta, tareas[1])
    assert ruta == secreta / "sandbox" / "snapshots" / "x__y-1.tgz"
    # si el directorio secreto no tiene sandbox/snapshots, se queda con la ruta principal
    ruta, _, _ = kv.ubicar_snapshot(resolver_falso, principal, tmp_path, tareas[1])
    assert ruta == principal / "x__y-1.tgz"
    assert kv.contar_snapshots_faltantes([], resolver_falso, principal, secreta) == 0


def test_buscar_secret_dir_sube_por_los_ancestros(tmp_path: Path) -> None:
    secret = tmp_path / "datos" / "secret"
    secret.mkdir(parents=True)
    profundo = tmp_path / "datos" / "a" / "b"
    profundo.mkdir(parents=True)
    assert kv.buscar_secret_dir(profundo) is None  # sin solution.*
    (secret / "solution.csv").write_text("x", encoding="utf-8")
    assert kv.buscar_secret_dir(profundo) == secret.resolve()
    assert kv.buscar_secret_dir(tmp_path / "otro", profundo) == secret.resolve()
    otro = tmp_path / "datos2" / "secret"
    otro.mkdir(parents=True)
    (otro / "solution.parquet").write_bytes(b"")
    assert kv.buscar_secret_dir(tmp_path / "datos2", profundo) == otro.resolve()  # el primero que se da


def test_faltan_snapshots_es_salida_2_con_el_conteo_y_sin_crear_el_manifiesto(
    esc: Escenario, capsys: pytest.CaptureFixture[str]
) -> None:
    falso = Falso()
    codigo = kv.main(esc.argv(), verificador=falso, reloj=reloj, faltan_snapshots=lambda ts: 2)
    assert codigo == kv.EXIT_INVALID
    err = capsys.readouterr().err
    assert "2 de las 3 tareas" in err
    assert falso.llamadas == []
    assert not (esc.crudo / "manifiesto.json").exists()
    assert not esc.salida.exists()
    # con todos presentes, se mide
    assert kv.main(esc.argv(), verificador=falso, reloj=reloj, faltan_snapshots=lambda ts: 0) == kv.EXIT_OK
    # solo cuenta las tareas elegidas
    vistas: list[int] = []
    otro = nuevo(esc.base, "otro", esc.spec)
    kv.main(
        otro.argv("--task-ids", esc.spec[0][0], salida=False),
        verificador=Falso(),
        reloj=reloj,
        faltan_snapshots=lambda ts: vistas.append(len(ts)) or 0,
    )
    assert vistas == [1]


def test_cambiar_el_directorio_de_snapshots_a_mitad_es_salida_2(
    esc: Escenario, capsys: pytest.CaptureFixture[str]
) -> None:
    corte = Falso()
    corte.explotar_en = 2
    assert esc.correr(corte) == kv.EXIT_INVALID
    argv = esc.argv()
    argv[argv.index("--snapshots-dir") + 1] = str(esc.base / "otros_snapshots")
    falso = Falso()
    assert kv.main(argv, verificador=falso, reloj=reloj) == kv.EXIT_INVALID
    assert falso.llamadas == []
    assert "snapshots_dir" in capsys.readouterr().err
    # el mismo directorio, escrito con un rodeo, es el mismo
    argv[argv.index("--snapshots-dir") + 1] = str(esc.base / "x" / ".." / "snapshots")
    assert kv.main(argv, verificador=falso, reloj=reloj) == kv.EXIT_OK


def test_el_manifiesto_guarda_modo_corrida_y_snapshots(esc: Escenario) -> None:
    assert esc.correr(Falso()) == kv.EXIT_OK
    m = json.loads((esc.crudo / "manifiesto.json").read_text(encoding="utf-8"))
    assert m["modo"] == "medicion"
    assert re.fullmatch(r"[0-9a-f]{32}", m["corrida"])
    assert m["snapshots_dir"] == str(esc.snapshots.resolve())
    assert m["referencia_sha256"] is None
    assert {x["corrida"] for x in lineas_diario(esc.crudo)} == {m["corrida"]}


def test_redirigir_registros_lleva_los_loggers_del_arnes_a_un_archivo(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    nombres = ("swegemma", "swegemma.harness", "adk_submission", "adk")
    previos = {n: (logging.getLogger(n).handlers[:], logging.getLogger(n).propagate) for n in nombres}
    archivo = tmp_path / "crudo" / "arnes.log"
    manejador = kv.redirigir_registros(archivo)
    try:
        logging.getLogger("swegemma.harness").error("Failed to apply agent patch %s", POISON_PARCHE)
        logging.getLogger("adk_submission").warning(POISON_LOG)
        logging.getLogger("adk.tools").exception("fallo %s", POISON_TEST)
        manejador.flush()
        consola = capsys.readouterr()
        assert POISON_PARCHE not in consola.out + consola.err
        assert POISON_LOG not in consola.out + consola.err
        assert POISON_TEST not in consola.out + consola.err
        texto = archivo.read_text(encoding="utf-8")
        assert POISON_PARCHE in texto and POISON_LOG in texto and POISON_TEST in texto
        assert logging.getLogger("swegemma").propagate is False
    finally:
        manejador.close()
        for n, (handlers, propaga) in previos.items():
            logging.getLogger(n).handlers[:] = handlers
            logging.getLogger(n).propagate = propaga
        for n in ("swegemma.harness", "adk.tools"):
            logging.getLogger(n).handlers.clear()


# ---------------------------------------------------------------------------
# Mensajes sin texto de excepciones, codigos sin categoria
# ---------------------------------------------------------------------------


def test_una_validez_error_del_verificador_no_imprime_su_texto(
    esc: Escenario, capsys: pytest.CaptureFixture[str]
) -> None:
    def malo(_t: Tarea, _v: str) -> ResultadoVerificacion:
        raise ValidezError(f"contenido {POISON_PARCHE} {POISON_ERROR}")

    assert esc.correr(malo) == kv.EXIT_INVALID
    err = capsys.readouterr().err
    assert POISON_PARCHE not in err and POISON_ERROR not in err
    assert "ValidezError" in err and esc.spec[0][0] in err


def test_un_fallo_con_codigo_cerrado_imprime_el_codigo(
    esc: Escenario, capsys: pytest.CaptureFixture[str]
) -> None:
    def sin_parche(_t: Tarea, v: str) -> ResultadoVerificacion:
        raise kv.FalloVerificador("sin_parche_referencia")

    assert esc.correr(sin_parche) == kv.EXIT_INVALID
    assert "sin_parche_referencia" in capsys.readouterr().err
    assert set(kv.CODIGOS_FALLO) == {"sin_parche_referencia", "tarea_ausente"}


def test_la_salida_3_no_imprime_el_texto_de_la_excepcion_sino_tipo_y_punto(
    esc: Escenario, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def roto(*_a: object, **_k: object) -> None:
        raise KeyError(POISON_ERROR)

    monkeypatch.setattr(kv, "medir_tarea", roto)
    assert esc.correr(Falso()) == kv.EXIT_UNEXPECTED
    err = capsys.readouterr().err
    assert POISON_ERROR not in err
    assert "KeyError" in err and "test_kaggle_validez.py" in err


def test_un_codigo_de_salida_fuera_de_la_lista_aborta_con_la_tarea_y_pide_enmienda(
    esc: Escenario, capsys: pytest.CaptureFixture[str]
) -> None:
    ids = [i for i, _ in esc.spec]
    extrano = ResultadoVerificacion(False, 139, None, 1.0)  # segmentation fault: ni agente ni lista
    falso = Falso({(ids[1], kv.VERIF_DORADO): [extrano]})
    assert esc.correr(falso) == kv.EXIT_INVALID
    err = capsys.readouterr().err
    assert ids[1] in err and "enmienda" in err and "dorado" in err
    assert not esc.salida.exists()


# ---------------------------------------------------------------------------
# Huecos de la primera version: UTC, redondeo, muestra ausente, rutas, resumenes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("hora_local", "utc", "fecha"),
    [
        (
            datetime(2026, 10, 5, 23, 30, tzinfo=timezone(timedelta(hours=-5))),
            "2026-10-06T04:30:00Z",
            "2026-10-06",
        ),
        (
            datetime(2026, 10, 6, 3, 0, tzinfo=timezone(timedelta(hours=14))),
            "2026-10-05T13:00:00Z",
            "2026-10-05",
        ),
    ],
)
def test_fecha_y_fecha_utc_se_convierten_a_utc_con_un_reloj_no_utc(
    esc: Escenario, hora_local: datetime, utc: str, fecha: str
) -> None:
    assert kv.main(esc.argv(), verificador=Falso(), reloj=lambda: hora_local) == kv.EXIT_OK
    assert esc.registro()["fecha"] == fecha
    crudo = json.loads(
        (esc.crudo / "ejecuciones" / esc.spec[0][0] / "sin_parche_1_1.json").read_text(encoding="utf-8")
    )
    assert crudo["registro"]["fecha_utc"] == utc
    assert lineas_diario(esc.crudo)[0]["fecha_utc"] == utc


@pytest.mark.parametrize(("bruto", "esperado"), [(1.23449, 1.234), (1.2346, 1.235), (2, 2.0), (0.0004, 0.0)])
def test_la_duracion_se_redondea_a_milesimas(bruto: float, esperado: float) -> None:
    res = ResultadoVerificacion(True, 0, None, bruto)
    registro = kv.registro_de_ejecucion(res, "sin_parche", 1, 1, FECHA_UTC)
    assert registro["duracion_segundos"] == esperado
    assert isinstance(registro["duracion_segundos"], float)
    assert kv.registro_versionable(registro)["duracion_segundos"] == esperado


def test_una_tarea_de_la_muestra_ausente_de_la_referencia_es_error() -> None:
    referencia = {"tareas": [{"instance_id": "a__b-1", "clase": CLASE_DISCRIMINA}]}
    with pytest.raises(ValidezError, match="no esta en el registro de referencia"):
        kv._comparar_muestra(referencia, [{"instance_id": "a__b-9", "clase": CLASE_DISCRIMINA}])
    comparacion = kv._comparar_muestra(referencia, [{"instance_id": "a__b-1", "clase": CLASE_PASA}])
    assert comparacion["coincide"] is False
    assert comparacion["tareas"] == [
        {
            "instance_id": "a__b-1",
            "clase_referencia": CLASE_DISCRIMINA,
            "clase_repeticion": CLASE_PASA,
            "coincide": False,
        }
    ]


def test_crudo_con_rodeos_y_enlaces_se_resuelve_antes_de_comprobar(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "otro").mkdir(parents=True)
    git(repo, "init", "-q")
    (repo / ".gitignore").write_text("datos/\n", encoding="utf-8")
    # un rodeo con ``..`` que acaba en la ruta ignorada, y otro que acaba en una versionable
    kv.comprobar_crudo_ignorado(repo / "otro" / ".." / "datos" / "crudo")
    with pytest.raises(ValidezError):
        kv.comprobar_crudo_ignorado(repo / "datos" / ".." / "visible" / "crudo")
    # un enlace desde fuera del repositorio hacia una ruta versionable
    (repo / "visible").mkdir()
    enlace = tmp_path / "enlace"
    try:
        enlace.symlink_to(repo / "visible", target_is_directory=True)
    except OSError:
        pytest.skip("sin permiso para crear enlaces simbolicos")
    with pytest.raises(ValidezError):
        kv.comprobar_crudo_ignorado(enlace / "crudo")
    # y uno hacia la ruta ignorada si se acepta
    (repo / "datos").mkdir()
    bueno = tmp_path / "bueno"
    bueno.symlink_to(repo / "datos", target_is_directory=True)
    kv.comprobar_crudo_ignorado(bueno / "crudo")


def test_la_salida_dentro_del_crudo_se_detecta_aunque_se_escriba_con_rodeos(esc: Escenario) -> None:
    argv = esc.argv()
    argv[argv.index("--salida") + 1] = str(esc.base / "otro" / ".." / "crudo" / "x_v1.json")
    assert kv.main(argv, verificador=Falso(), reloj=reloj) == kv.EXIT_INVALID


def test_contar_pruebas_con_varias_lineas_de_resumen_usa_la_ultima() -> None:
    texto = "1 passed in 0.1s\nruido\n2 failed, 5 passed in 1s\nlinea sin cifras\n"
    assert kv.contar_pruebas(texto) == (5, 2, 0)
    assert kv.contar_pruebas("3 failed in 1s\n7 passed in 2s") == (7, 0, 0)
    assert kv.contar_pruebas("2 passed and 1 passed in 1s") == (
        3,
        0,
        0,
    )  # varias cifras en una linea se suman
