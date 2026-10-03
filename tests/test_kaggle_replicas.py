"""Pruebas de scripts/kaggle_replicas.py con datos sinteticos inventados.

Cada numero del reporte esta fijado a mano en un caso pequeno (ver ``CASO``). Ningun dato de la
competencia entra aqui: los ids, repositorios, hashes y textos de error de prueba son inventados o
son los prefijos genericos de la lista cerrada del conversor.

Letras de las cuadriculas: R resuelta; N no resuelta por pruebas; E parche vacio; T timeout del
agente; B presupuesto agotado; P parche que no aplica; I error de infraestructura; - sin recibo.
"""

from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path
from typing import Any

import pytest

from scripts import kaggle_replicas as kr
from scripts.kaggle_replicas import (
    ReplicasError,
    analyze,
    binom_cdf,
    check_integrity,
    classify_harness,
    clopper_pearson,
    convert_harness_results,
    discordance_floor,
    load_receipts,
    load_subset,
    loads_strict,
    main,
    mcnemar_exact_p,
    min_significant_difference,
    parse_receipt,
    render_json,
    render_markdown,
    resolve_tasks_sha,
    sha256_directory,
    submission_files,
)

TASKS_SHA = "a" * 64
ENVIO_SHA = "b" * 64
MISS = "-"

# letra -> (status, failure_reason, harness_raw)
RAWS: dict[str, tuple[str, str | None, dict[str, Any]]] = {
    "R": ("resolved", None, {"resolved": True, "error": None, "test_exit_code": 0, "agent_patch_size": 10}),
    "N": (
        "unresolved",
        "tests_failed",
        {"resolved": False, "error": None, "test_exit_code": 1, "agent_patch_size": 10},
    ),
    "E": (
        "unresolved",
        "empty_patch",
        {
            "resolved": False,
            "error": "Agent completed execution without calling submit_patch. sintetico",
            "test_exit_code": -1,
            "agent_patch_size": 0,
        },
    ),
    "T": (
        "unresolved",
        "agent_timeout",
        {
            "resolved": False,
            "error": "Agent exceeded session timeout (sintetico)",
            "test_exit_code": -1,
            "agent_patch_size": 0,
        },
    ),
    "B": (
        "unresolved",
        "budget_exhausted",
        {
            "resolved": False,
            "error": "Agent exceeded tool call budget (sintetico)",
            "test_exit_code": -1,
            "agent_patch_size": 0,
        },
    ),
    "P": (
        "unresolved",
        "patch_apply_failed",
        {
            "resolved": False,
            "error": "Failed to apply agent patch: sintetico",
            "test_exit_code": 1,
            "agent_patch_size": 10,
        },
    ),
    "I": (
        "infra_error",
        None,
        {
            "resolved": False,
            "error": "Sandbox execution error: sintetico",
            "test_exit_code": -1,
            "agent_patch_size": 0,
        },
    ),
    # sin error y con parche: el codigo de salida de las pruebas es de infraestructura
    "X": (
        "infra_error",
        None,
        {"resolved": False, "error": None, "test_exit_code": 124, "agent_patch_size": 10},
    ),
}
INFRA_REASON = {"I": "sandbox_error", "X": "test_timeout"}

REPOS = {"t1": "o/a", "t2": "o/a", "t3": "o/a", "t4": "o/b", "t5": "o/b", "t6": "o/b"}
# Caso a mano: tres replicas, seis tareas; t5 en la replica 2 es un timeout del agente (cuenta como N).
CASO: dict[str, list[str]] = {
    "t1": ["R", "R", "R"],
    "t2": ["R", "N", "R"],
    "t3": ["N", "N", "N"],
    "t4": ["R", "R", "N"],
    "t5": ["N", "T", "N"],
    "t6": ["N", "N", "R"],
}


def sha(texto: str) -> str:
    return hashlib.sha256(texto.encode()).hexdigest()


def receipt(iid: str, rep: int, letra: str, repo: str = "o/a", **over: Any) -> dict[str, Any]:
    status, reason, raw = RAWS[letra]
    raw = {**raw, "total_llm_calls": 3}
    r: dict[str, Any] = {
        "schema_version": kr.SCHEMA_VERSION,
        "instance_id": iid,
        "repo": repo,
        "condition": "A",
        "replica": rep,
        "status": status,
        "failure_reason": reason,
        "infra_reason": INFRA_REASON.get(letra),
        "resolved": status == "resolved",
        "tool_calls": rep * 10,
        "duration_seconds": 12.5,
        "patch_sha256": None if raw["agent_patch_size"] == 0 else sha(f"{iid}-{rep}"),
        "submission_sha256": ENVIO_SHA,
        "tasks_sha256": TASKS_SHA,
        "subset_sha256": "c" * 64,
        "harness_version": "swegemma-0.0.0",
        "sandbox_image": "img:sintetica",
        "converted_utc": f"2026-10-0{rep}T10:00:00Z",
        "harness_raw": raw,
    }
    r.update(over)
    return r


def write_case(
    tmp_path: Path,
    grid: dict[str, list[str]],
    repos: dict[str, str] | None = None,
    subset_ids: list[str] | None = None,
    declare_tasks: bool = True,
) -> tuple[Path, Path]:
    """Escribe el subconjunto y un .jsonl por replica; devuelve (directorio de recibos, subconjunto)."""
    subset = tmp_path / "subset.json"
    ids = subset_ids if subset_ids is not None else sorted(grid)
    data: dict[str, Any] = {"test": ids}
    if declare_tasks:
        data["sha256_tasks"] = TASKS_SHA
    subset.write_text(json.dumps(data), encoding="utf-8")
    subset_sha = hashlib.sha256(subset.read_bytes()).hexdigest()
    d = tmp_path / "recibos"
    d.mkdir()
    n_rep = max(len(v) for v in grid.values())
    for rep in range(1, n_rep + 1):
        lines = [
            json.dumps(
                receipt(iid, rep, row[rep - 1], (repos or REPOS).get(iid, "o/a"), subset_sha256=subset_sha)
            )
            for iid, row in grid.items()
            if row[rep - 1] != MISS
        ]
        (d / f"replica_{rep}.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return d, subset


def analizar(tmp_path: Path, grid: dict[str, list[str]], **kw: Any) -> dict[str, Any]:
    d, s = write_case(tmp_path, grid, **kw)
    receipts = load_receipts([d])
    sub = load_subset(s)
    assert check_integrity(receipts, sub, resolve_tasks_sha(sub, None)) == []
    return analyze(receipts, sub)


# ---------------------------------------------------------------------------
# Estadistica
# ---------------------------------------------------------------------------


def test_binom_cdf_valores_a_mano() -> None:
    assert binom_cdf(1, 3, 0.5) == pytest.approx(0.5)
    assert binom_cdf(0, 6, 0.5) == pytest.approx(1 / 64)
    assert binom_cdf(-1, 4, 0.3) == 0.0
    assert binom_cdf(4, 4, 0.3) == 1.0
    assert binom_cdf(2, 5, 0.0) == 1.0
    assert binom_cdf(2, 5, 1.0) == 0.0


def test_n_grande_no_desborda() -> None:
    assert binom_cdf(10, 100000, 0.0001) == pytest.approx(0.58304, abs=1e-3)  # Poisson(10): P(X<=10)
    lo, hi = clopper_pearson(300, 5000)
    assert 0.05 < lo < 0.06 < hi < 0.07
    lo2, hi2 = clopper_pearson(0, 100000)
    assert lo2 == 0.0 and 0 < hi2 < 0.0001


def test_clopper_pearson_valores_conocidos() -> None:
    lo, hi = clopper_pearson(1, 5)
    assert lo == pytest.approx(0.0051, abs=1e-4)
    assert hi == pytest.approx(0.7164, abs=1e-4)
    lo0, hi0 = clopper_pearson(0, 10)
    assert lo0 == 0.0
    assert hi0 == pytest.approx(1 - 0.025 ** (1 / 10), abs=1e-9)  # forma cerrada
    lo_n, hi_n = clopper_pearson(10, 10)
    assert hi_n == 1.0
    assert lo_n == pytest.approx(0.025 ** (1 / 10), abs=1e-9)


def test_clopper_pearson_cumple_su_definicion() -> None:
    lo, hi = clopper_pearson(6, 10)
    assert binom_cdf(6, 10, hi) == pytest.approx(0.025, abs=1e-9)
    assert 1 - binom_cdf(5, 10, lo) == pytest.approx(0.025, abs=1e-9)
    lo90, hi90 = clopper_pearson(6, 10, alpha=0.10)
    assert lo < lo90 < 0.6 < hi90 < hi


def test_clopper_pearson_rechaza_entradas_invalidas() -> None:
    with pytest.raises(ValueError):
        clopper_pearson(1, 0)
    with pytest.raises(ValueError):
        clopper_pearson(6, 5)


def test_mcnemar_exacto() -> None:
    assert mcnemar_exact_p(0, 0) == 1.0
    assert mcnemar_exact_p(6, 0) == pytest.approx(2 / 64)
    assert mcnemar_exact_p(0, 6) == pytest.approx(2 / 64)
    assert mcnemar_exact_p(1, 1) == 1.0
    assert mcnemar_exact_p(5, 1) == pytest.approx(2 * 7 / 64)


@pytest.mark.parametrize(
    ("d", "n", "g", "dif_pares", "tasa"),
    [(6, 10, 6, 6, 0.6), (8, 20, 8, 8, 0.4), (10, 20, 9, 8, 0.4), (12, 40, 10, 8, 0.2), (7, 10, 7, 7, 0.7)],
)
def test_diferencia_minima_significativa(d: int, n: int, g: int, dif_pares: int, tasa: float) -> None:
    x = min_significant_difference(d, n)
    assert x["alcanzable"] is True
    assert (x["ganadas_minimas"], x["diferencia_pares"], x["diferencia_tasa"]) == (g, dif_pares, tasa)


@pytest.mark.parametrize(("d", "n"), [(0, 10), (3, 5), (5, 5)])
def test_diferencia_con_pocos_discordantes_no_alcanza_alfa(d: int, n: int) -> None:
    x = min_significant_difference(d, n)
    assert x["alcanzable"] is False and x["diferencia_tasa"] is None


def test_frontera_p_igual_a_alfa_cuenta_como_significativa() -> None:
    # 6 discordantes unilaterales: p = 2/64 = 0.03125 exacto; con alfa = 0.03125 todavia alcanza (p <= alfa)
    assert min_significant_difference(6, 10, alpha=0.03125)["alcanzable"] is True
    assert min_significant_difference(6, 10, alpha=0.03124)["alcanzable"] is False
    assert discordance_floor(0.03125) == 6
    assert discordance_floor(0.0625) == 5  # 2/32 = 0.0625 exacto
    assert discordance_floor(0.0624) == 6
    assert discordance_floor(0.05) == 6
    assert discordance_floor(0.10) == 5
    assert min_significant_difference(5, 5, alpha=0.1)["alcanzable"] is True
    with pytest.raises(ValueError):
        min_significant_difference(6, 5)


def test_paridad_hace_la_funcion_no_monotona() -> None:
    # g minimo: d=7 -> 7 (diferencia 7); d=8 -> 8 (diferencia 8); d=9 -> 8 (diferencia 7)
    difs = [min_significant_difference(d, 20)["diferencia_pares"] for d in (7, 8, 9)]
    assert difs == [7, 8, 7]


# ---------------------------------------------------------------------------
# Clasificacion del arnes
# ---------------------------------------------------------------------------


def raw(**over: Any) -> dict[str, Any]:
    base = {
        "resolved": False,
        "error": None,
        "test_exit_code": 1,
        "agent_patch_size": 10,
        "total_llm_calls": 2,
    }
    base.update(over)
    return base


SUF = " sintetico-xyz"  # sufijo inventado: los tests no copian mensajes completos del arnes

# prefijo -> clasificacion exacta. Si se anade un prefijo al script, test_la_tabla_cubre_la_lista_cerrada
# obliga a fijarlo aqui.
PREFIJOS_AGENTE = {
    "Agent exceeded session timeout (": "agent_timeout",
    "Agent exceeded turns budget (": "budget_exhausted",
    "Agent exceeded maximum allowed LLM turns": "budget_exhausted",
    "Agent exceeded tool call budget (": "budget_exhausted",
    "Agent completed execution without calling submit_patch.": "empty_patch",
    "Failed to apply agent patch:": "patch_apply_failed",
    "Missing or empty JUnit XML report": "tests_failed",
    "Malformed JUnit XML report:": "tests_failed",
    "No <testsuite> elements found in JUnit XML": "tests_failed",
    "No passing tests recorded in JUnit XML (": "tests_failed",
    "Test failures/errors recorded in JUnit XML (": "tests_failed",
    "Required test node did not pass:": "tests_failed",
    "Pytest stdout summary indicates zero or no passing tests": "tests_failed",
    "Missing JUnit XML report (possible premature os._exit(0))": "tests_failed",
}
PREFIJOS_INFRA = {
    "Snapshot file not found:": "snapshot_missing",
    "Sandbox execution error:": "sandbox_error",
    "Evaluation error:": "evaluation_error",
    "Unexpected evaluation worker error:": "worker_error",
    "Missing test specification": "missing_test_spec",
    "Failed to apply test_patch:": "test_patch_failed",
}


def test_la_tabla_cubre_la_lista_cerrada() -> None:
    assert dict(kr.AGENT_ERROR_PREFIXES) == PREFIJOS_AGENTE
    assert dict(kr.INFRA_ERROR_PREFIXES) == PREFIJOS_INFRA


@pytest.mark.parametrize(("prefijo", "motivo"), sorted(PREFIJOS_AGENTE.items()))
def test_prefijo_del_agente_se_clasifica_como_no_resuelta(prefijo: str, motivo: str) -> None:
    for tamano, codigo in ((0, -1), (10, 1)):
        fila = raw(error=prefijo + SUF, agent_patch_size=tamano, test_exit_code=codigo)
        assert classify_harness(fila, "x") == ("unresolved", motivo, None)


@pytest.mark.parametrize(("prefijo", "motivo"), sorted(PREFIJOS_INFRA.items()))
def test_prefijo_de_infraestructura_se_clasifica_como_infra_error(prefijo: str, motivo: str) -> None:
    for tamano, codigo in ((0, -1), (10, 1)):
        fila = raw(error=prefijo + SUF, agent_patch_size=tamano, test_exit_code=codigo)
        assert classify_harness(fila, "x") == ("infra_error", None, motivo)


@pytest.mark.parametrize(
    ("fila", "esperado"),
    [
        (raw(resolved=True, test_exit_code=0), ("resolved", None, None)),
        # resolved del arnes manda: con parche vacio y tambien con texto de error (caso defensivo)
        (raw(resolved=True, test_exit_code=0, agent_patch_size=0), ("resolved", None, None)),
        (
            raw(resolved=True, test_exit_code=0, error="Agent exceeded session timeout (" + SUF),
            ("resolved", None, None),
        ),
        (raw(), ("unresolved", "tests_failed", None)),
        (raw(agent_patch_size=0), ("unresolved", "empty_patch", None)),
        (raw(agent_patch_size=0, test_exit_code=-1), ("unresolved", "empty_patch", None)),
        # sin error y con parche, el codigo de salida de las pruebas decide
        (raw(test_exit_code=-1), ("infra_error", None, "test_exec_failed")),
        (raw(test_exit_code=124), ("infra_error", None, "test_timeout")),
        (raw(test_exit_code=137), ("infra_error", None, "test_killed")),
        (raw(test_exit_code=1), ("unresolved", "tests_failed", None)),
        (raw(test_exit_code=2), ("unresolved", "tests_failed", None)),
        (raw(test_exit_code=5), ("unresolved", "tests_failed", None)),
        (raw(test_exit_code=127), ("unresolved", "tests_failed", None)),
        (raw(test_exit_code=128), ("unresolved", "tests_failed", None)),
    ],
)
def test_clasificacion_con_lista_cerrada(fila: dict[str, Any], esperado: tuple[str, ...]) -> None:
    assert classify_harness(fila, "x") == esperado


@pytest.mark.parametrize("codigo", [-2, -9, -15, 129, 130, 139, 143, 255, 300])
def test_codigo_de_salida_raro_sin_error_no_se_clasifica(codigo: int) -> None:
    with pytest.raises(ReplicasError, match=f"test_exit_code={codigo}"):
        classify_harness(raw(test_exit_code=codigo), "x")


def test_codigos_de_infraestructura_estan_en_la_lista_de_motivos() -> None:
    assert kr.INFRA_EXIT_CODES == {-1: "test_exec_failed", 124: "test_timeout", 137: "test_killed"}
    assert set(kr.INFRA_EXIT_CODES.values()) <= set(kr.INFRA_REASONS)
    assert set(PREFIJOS_INFRA.values()) <= set(kr.INFRA_REASONS)


def test_error_desconocido_no_se_clasifica_por_defecto() -> None:
    with pytest.raises(ReplicasError, match="fuera de la lista cerrada") as exc:
        classify_harness(raw(error="algo nunca visto: timeout?"), "x")
    assert "algo nunca visto" in str(exc.value)
    # una subcadena conocida en medio del texto no basta: se compara el principio
    with pytest.raises(ReplicasError, match="lista cerrada"):
        classify_harness(raw(error="wrapper: Agent exceeded session timeout (" + SUF), "x")


@pytest.mark.parametrize(
    "fila",
    [
        raw(resolved="yes"),
        raw(resolved=1),
        raw(resolved=None),
        raw(agent_patch_size=-1),
        raw(agent_patch_size=1.5),
        raw(agent_patch_size="10"),
        raw(agent_patch_size=True),
        raw(test_exit_code="1"),
        raw(test_exit_code=True),
        raw(total_llm_calls=-1),
        raw(error=7),
        raw(resolved=True, test_exit_code=1),  # resuelta con pytest fallido
        raw(test_exit_code=0),  # no resuelta, sin error y con pytest ok
    ],
)
def test_clasificacion_rechaza_entradas_incoherentes(fila: dict[str, Any]) -> None:
    with pytest.raises(ReplicasError):
        classify_harness(fila, "x")


# ---------------------------------------------------------------------------
# Caso a mano: cada numero del reporte
# ---------------------------------------------------------------------------


def test_tasa_principal_sobre_subconjunto_y_secundaria(tmp_path: Path) -> None:
    rep = analizar(tmp_path, CASO)
    p1, p2, p3 = rep["por_replica"]
    assert (p1["resueltas"], p1["no_resueltas"], p1["tareas_subconjunto"]) == (3, 3, 6)
    assert p1["tasa_sobre_subconjunto"] == 0.5 and p1["tasa_sobre_validas"] == 0.5
    # replica 2: resuelve t1,t4; el timeout del agente (t5) es NO RESUELTA y entra en el denominador
    assert (p2["resueltas"], p2["no_resueltas"], p2["validas"], p2["infra_error"]) == (2, 4, 6, 0)
    assert p2["tasa_sobre_subconjunto"] == round(2 / 6, 6)
    assert p2["no_resueltas_por_motivo"] == {
        "empty_patch": 0,
        "agent_timeout": 1,
        "budget_exhausted": 0,
        "patch_apply_failed": 0,
        "tests_failed": 3,
    }
    assert (p3["resueltas"], p3["validas"], p3["tasa_sobre_subconjunto"]) == (3, 6, 0.5)
    assert all(p["faltantes"] == 0 for p in (p1, p2, p3))


def test_tareas_que_cambian_de_resultado(tmp_path: Path) -> None:
    rep = analizar(tmp_path, CASO)
    c = rep["cambian_de_resultado"]
    assert (c["numerador"], c["denominador"]) == (3, 6)
    assert c["tareas"] == ["t2", "t4", "t6"]
    assert c["no_evaluables"] == []
    por_tarea = {t["instance_id"]: t for t in rep["tareas"]}
    assert por_tarea["t5"]["cambia"] is False and por_tarea["t5"]["validas"] == 3
    assert por_tarea["t5"]["resultados"] == {"1": "unresolved", "2": "unresolved", "3": "unresolved"}
    assert por_tarea["t5"]["motivos"] == {"1": "tests_failed", "2": "agent_timeout", "3": "tests_failed"}
    assert por_tarea["t1"]["cambia"] is False and por_tarea["t1"]["resueltas"] == 3
    assert por_tarea["t2"]["resueltas"] == 2 and por_tarea["t2"]["validas"] == 3


def test_acuerdo_por_pares(tmp_path: Path) -> None:
    rep = analizar(tmp_path, CASO)
    p12, p13, p23 = rep["pares"]
    assert [p12["replicas"], p13["replicas"], p23["replicas"]] == [[1, 2], [1, 3], [2, 3]]
    # 1-2: RR t1,t4; R/N t2; NN t3,t5,t6
    assert (p12["comparables"], p12["ambas_resueltas"], p12["solo_primera"], p12["solo_segunda"]) == (
        6,
        2,
        1,
        0,
    )
    assert p12["ninguna_resuelta"] == 3 and p12["discordantes"] == 1
    assert p12["acuerdo"] == {"numerador": 5, "denominador": 6, "tasa": round(5 / 6, 6)}
    assert p12["tasa_discordancia"] == round(1 / 6, 6)
    assert p12["mcnemar_p_exacto"] == 1.0
    # 1-3: RR t1,t2; NN t3,t5; R/N t4; N/R t6
    assert (p13["comparables"], p13["ambas_resueltas"], p13["solo_primera"], p13["solo_segunda"]) == (
        6,
        2,
        1,
        1,
    )
    assert p13["acuerdo"] == {"numerador": 4, "denominador": 6, "tasa": round(4 / 6, 6)}
    # 2-3: RR t1; N/R t2,t6; R/N t4; NN t3,t5
    assert (p23["comparables"], p23["ambas_resueltas"], p23["solo_primera"], p23["solo_segunda"]) == (
        6,
        1,
        1,
        2,
    )
    assert p23["ninguna_resuelta"] == 2
    assert p23["acuerdo"] == {"numerador": 3, "denominador": 6, "tasa": 0.5}
    assert p23["tasa_discordancia"] == 0.5
    lo, hi = p23["intervalo_discordancia"]["inferior"], p23["intervalo_discordancia"]["superior"]
    assert binom_cdf(3, 6, hi) == pytest.approx(0.025, abs=1e-5)
    assert 1 - binom_cdf(2, 6, lo) == pytest.approx(0.025, abs=1e-5)


def test_desglose_por_repositorio(tmp_path: Path) -> None:
    rep = analizar(tmp_path, CASO)
    a, b = rep["por_repositorio"]
    assert (a["repo"], a["tareas"]) == ("o/a", 3)
    assert [(x["resueltas"], x["validas"]) for x in a["por_replica"]] == [(2, 3), (1, 3), (2, 3)]
    assert a["cambian"] == {"numerador": 1, "denominador": 3}  # solo t2
    assert (b["repo"], b["tareas"]) == ("o/b", 3)
    assert [(x["resueltas"], x["validas"], x["infra_error"]) for x in b["por_replica"]] == [
        (1, 3, 0),
        (1, 3, 0),
        (1, 3, 0),
    ]
    assert b["cambian"] == {"numerador": 2, "denominador": 3}  # t4 y t6


def test_caso_a_mano_completo(tmp_path: Path) -> None:
    rep = analizar(tmp_path, CASO)
    assert rep["completo"] is True
    assert rep["faltantes"] == [] and rep["errores_de_infraestructura"] == [] and rep["infra_afectadas"] == []
    e = rep["entrada"]
    assert e["convertido_utc_primero"] == "2026-10-01T10:00:00Z"
    assert e["convertido_utc_ultimo"] == "2026-10-03T10:00:00Z"
    assert e["recibos"] == 18 and e["replicas"] == [1, 2, 3]


def test_margen_del_caso_a_mano(tmp_path: Path) -> None:
    m = analizar(tmp_path, CASO)["margen"]
    assert m["calculable"] is True
    assert m["diferencia_observada_entre_replicas"] == round(0.5 - round(2 / 6, 6), 6)
    assert m["par_base"] == [2, 3]  # discordancia 3/6, la mayor
    assert (m["comparables"], m["discordantes_observados"]) == (6, 3)
    assert m["discordantes_limite_superior"] == 6  # ceil(0.8819 * 6)
    assert m["suelo"] == {"pares_discordantes_unilaterales": 6, "alcanzable": True, "diferencia_tasa": 1.0}
    assert [(x["discordantes"], x["alcanzable"]) for x in m["por_discordantes"]] == [
        (3, False),
        (4, False),
        (5, False),
        (6, True),
    ]
    assert m["diferencia_minima_significativa"] == 1.0 and m["discordantes_de_la_maxima"] == 6
    assert "mitad de las veces" in m["nota"]


def test_margen_es_el_maximo_del_rango_no_el_valor_del_extremo(tmp_path: Path) -> None:
    grid = {f"u{i}": ["R", "N"] for i in range(1, 7)} | {f"u{i}": ["N", "N"] for i in range(7, 11)}
    rep = analizar(tmp_path, grid, repos={})
    (par,) = rep["pares"]
    assert (par["ambas_resueltas"], par["solo_primera"], par["solo_segunda"], par["ninguna_resuelta"]) == (
        0,
        6,
        0,
        4,
    )
    assert par["mcnemar_p_exacto"] == pytest.approx(0.03125)
    m = rep["margen"]
    assert m["limite_superior_discordancia"] == pytest.approx(0.8784, abs=1e-3)
    assert m["discordantes_limite_superior"] == 9
    assert [(x["discordantes"], x["diferencia_pares"]) for x in m["por_discordantes"]] == [
        (6, 6),
        (7, 7),
        (8, 8),
        (9, 7),
    ]
    assert m["suelo"] == {"pares_discordantes_unilaterales": 6, "alcanzable": True, "diferencia_tasa": 0.6}
    # el extremo superior (9 discordantes) da 0.7, pero la cota es el maximo del rango: 0.8
    assert m["diferencia_minima_significativa"] == 0.8 and m["discordantes_de_la_maxima"] == 8


def test_empate_en_la_maxima_se_resuelve_con_el_menor_numero_de_discordantes(tmp_path: Path) -> None:
    grid = {f"u{i}": ["R", "N"] for i in range(1, 9)} | {f"u{i}": ["N", "N"] for i in (9, 10)}
    m = analizar(tmp_path, grid, repos={})["margen"]
    assert [(x["discordantes"], x["diferencia_pares"]) for x in m["por_discordantes"]] == [
        (8, 8),
        (9, 7),
        (10, 8),
    ]
    assert m["diferencia_minima_significativa"] == 0.8 and m["discordantes_de_la_maxima"] == 8


def test_suelo_no_alcanzable_solo_si_n_es_menor_que_el_suelo(tmp_path: Path) -> None:
    grid = {"a": ["R", "N"], "b": ["R", "N"], "c": ["R", "N"], "d": ["N", "N"], "e": ["N", "N"]}
    rep = analizar(tmp_path, grid, repos={})
    m = rep["margen"]
    assert (m["comparables"], m["discordantes_observados"]) == (5, 3)
    assert m["suelo"] == {"pares_discordantes_unilaterales": 6, "alcanzable": False, "diferencia_tasa": None}
    assert m["diferencia_minima_significativa"] is None
    md = render_markdown(rep)
    assert (
        "se necesitan 6 pares discordantes a favor de una condicion "
        "y solo hay 5 tareas comparables: no alcanzable" in md
    )
    assert "| 3 | n/a | n/a | n/a |" in md
    assert "no calculable con esos discordantes" in md
    assert "ninguna diferencia alcanza" not in md and "ninguna diferencia alcanza" not in json.dumps(rep)


def test_caso_del_revisor_24_tareas(tmp_path: Path) -> None:
    # replica 1 resuelve 10; la 2 pierde 6 de esas 10: 3 parche vacio y 3 timeout del agente
    grid: dict[str, list[str]] = {}
    for i in range(1, 25):
        if i <= 4:
            grid[f"u{i:02d}"] = ["R", "R"]
        elif i <= 7:
            grid[f"u{i:02d}"] = ["R", "E"]
        elif i <= 10:
            grid[f"u{i:02d}"] = ["R", "T"]
        else:
            grid[f"u{i:02d}"] = ["N", "N"]
    rep = analizar(tmp_path, grid, repos={})
    c = rep["cambian_de_resultado"]
    assert (c["numerador"], c["denominador"]) == (6, 24)
    (par,) = rep["pares"]
    assert (par["comparables"], par["discordantes"]) == (24, 6)  # no 0 sobre 18
    assert (par["ambas_resueltas"], par["solo_primera"], par["solo_segunda"], par["ninguna_resuelta"]) == (
        4,
        6,
        0,
        14,
    )
    assert par["acuerdo"] == {"numerador": 18, "denominador": 24, "tasa": 0.75}
    assert par["mcnemar_p_exacto"] == pytest.approx(0.03125)
    p1, p2 = rep["por_replica"]
    assert (p1["resueltas"], p1["tasa_sobre_subconjunto"]) == (10, round(10 / 24, 6))
    assert (p2["resueltas"], p2["no_resueltas"], p2["validas"]) == (4, 20, 24)
    assert (
        p2["no_resueltas_por_motivo"]["empty_patch"] == 3
        and p2["no_resueltas_por_motivo"]["agent_timeout"] == 3
    )
    assert rep["completo"] is True
    assert rep["margen"]["por_discordantes"][0]["diferencia_tasa"] == 0.25  # 6/24


@pytest.mark.parametrize("letra", ["E", "T", "B", "P", "N"])
def test_fallos_del_agente_cuentan_como_no_resuelta(tmp_path: Path, letra: str) -> None:
    rep = analizar(tmp_path, {"t1": ["R", letra], "t2": ["N", "N"], "t3": ["R", "R"]}, repos={})
    p2 = rep["por_replica"][1]
    assert (p2["resueltas"], p2["no_resueltas"], p2["validas"], p2["infra_error"]) == (1, 2, 3, 0)
    assert rep["cambian_de_resultado"]["tareas"] == ["t1"]
    assert rep["pares"][0]["comparables"] == 3 and rep["pares"][0]["solo_primera"] == 1
    assert rep["completo"] is True


def test_infra_error_se_excluye_de_pares_y_deja_incompleto(tmp_path: Path) -> None:
    rep = analizar(tmp_path, {"t1": ["R", "I"], "t2": ["N", "N"], "t3": ["R", "R"]}, repos={})
    assert rep["completo"] is False
    assert rep["infra_afectadas"] == ["t1"]
    assert rep["errores_de_infraestructura"] == [
        {"instance_id": "t1", "replica": 2, "status": "infra_error", "infra_reason": "sandbox_error"}
    ]
    p2 = rep["por_replica"][1]
    assert (p2["infra_error"], p2["no_resueltas"], p2["validas"]) == (1, 1, 2)
    assert p2["tasa_sobre_subconjunto"] == round(1 / 3, 6) and p2["tasa_sobre_validas"] == 0.5
    assert rep["pares"][0]["comparables"] == 2  # t1 queda fuera
    c = rep["cambian_de_resultado"]
    assert (c["numerador"], c["denominador"], c["no_evaluables"]) == (0, 2, ["t1"])
    assert "INCOMPLETO" in render_markdown(rep)


def test_faltante_se_reporta_y_no_se_omite(tmp_path: Path) -> None:
    rep = analizar(tmp_path, {"t1": ["R", "R"], "t2": ["N", MISS], "t3": ["R", "N"]}, repos={})
    assert rep["completo"] is False
    assert rep["faltantes"] == [{"instance_id": "t2", "replicas": [2]}]
    assert rep["por_replica"][1]["faltantes"] == 1 and rep["por_replica"][1]["validas"] == 2
    assert rep["por_replica"][1]["tasa_sobre_subconjunto"] == round(1 / 3, 6)


def test_tarea_sin_ningun_recibo_cuenta_como_faltante(tmp_path: Path) -> None:
    d, s = write_case(tmp_path, {"t1": ["R", "R"], "t2": ["N", "N"]}, subset_ids=["t1", "t2", "t9"])
    rep = analyze(load_receipts([d]), load_subset(s))
    assert rep["faltantes"] == [{"instance_id": "t9", "replicas": [1, 2]}]
    assert rep["cambian_de_resultado"]["no_evaluables"] == ["t9"]
    assert rep["tareas"][-1]["repo"] is None
    assert "(sin recibos)" in render_markdown(rep)


def test_no_se_ignora_ninguna_replica(tmp_path: Path) -> None:
    rep = analizar(tmp_path, {"t1": ["R", "R", "N"], "t2": ["N", "N", "N"]}, repos={})
    assert rep["entrada"]["replicas"] == [1, 2, 3]
    assert len(rep["por_replica"]) == 3 and len(rep["pares"]) == 3
    assert rep["cambian_de_resultado"]["tareas"] == ["t1"]


def test_replicas_no_consecutivas(tmp_path: Path) -> None:
    d, s = write_case(tmp_path, {"t1": ["R", "R", "N"]}, repos={})
    (d / "replica_2.jsonl").unlink()
    rep = analyze(load_receipts([d]), load_subset(s))
    assert rep["entrada"]["replicas"] == [1, 3] and rep["pares"][0]["replicas"] == [1, 3]


def test_desempate_del_peor_par_es_el_de_menor_numeracion(tmp_path: Path) -> None:
    rep = analizar(tmp_path, {"t1": ["R", "N", "N"], "t2": ["N", "N", "N"]}, repos={})
    assert [p["discordantes"] for p in rep["pares"]] == [1, 1, 0]
    assert rep["margen"]["par_base"] == [1, 2]


def test_peor_par_compara_fracciones_no_conteos(tmp_path: Path) -> None:
    # par 1-2: 1 discordante de 2 comparables (0.5); par 1-3: 2 discordantes de 6 (0.333)
    grid = {
        "a": ["R", "N", "R"],
        "b": ["N", "N", "R"],
        "c": ["R", "I", "N"],
        "d": ["N", "I", "N"],
        "e": ["N", "I", "N"],
        "f": ["N", "I", "N"],
    }
    rep = analizar(tmp_path, grid, repos={})
    assert [(p["replicas"], p["comparables"], p["discordantes"]) for p in rep["pares"]] == [
        ([1, 2], 2, 1),
        ([1, 3], 6, 2),
        ([2, 3], 2, 2),
    ]
    assert rep["margen"]["par_base"] == [2, 3]  # 2/2 es la mayor fraccion


def test_margen_no_calculable_sin_comparables(tmp_path: Path) -> None:
    rep = analizar(tmp_path, {"t1": ["R", "I"], "t2": ["I", "R"]}, repos={})
    assert rep["pares"][0]["comparables"] == 0
    assert rep["pares"][0]["acuerdo"]["tasa"] is None and rep["pares"][0]["intervalo_discordancia"] is None
    assert rep["margen"]["calculable"] is False
    assert "No calculable: ningun par" in render_markdown(rep)


# ---------------------------------------------------------------------------
# Determinismo e invariancia
# ---------------------------------------------------------------------------


def test_invariante_al_orden_de_los_recibos(tmp_path: Path) -> None:
    d, s = write_case(tmp_path, CASO)
    receipts = load_receipts([d])
    sub = load_subset(s)
    base = render_json(analyze(receipts, sub)), render_markdown(analyze(receipts, sub))
    rng = random.Random(7)
    for _ in range(10):
        mezclado = list(receipts)
        rng.shuffle(mezclado)
        assert (render_json(analyze(mezclado, sub)), render_markdown(analyze(mezclado, sub))) == base


def test_invariante_al_orden_de_archivos_y_subconjunto(tmp_path: Path) -> None:
    d, s = write_case(tmp_path, CASO)
    files = sorted(d.glob("*.jsonl"))
    a = analyze(load_receipts(files), load_subset(s))
    b = analyze(load_receipts(list(reversed(files))), load_subset(s))
    assert render_json(a) == render_json(b)
    data = json.loads(s.read_text("utf-8"))
    data["test"] = list(reversed(data["test"]))
    s2 = tmp_path / "subset2.json"
    s2.write_text(json.dumps(data), encoding="utf-8")
    assert load_subset(s2).ids == load_subset(s).ids


def test_json_canonico_y_markdown_con_los_numeros(tmp_path: Path) -> None:
    rep = analizar(tmp_path, CASO)
    j = render_json(rep)
    assert j.endswith("}\n") and json.loads(j) == rep and j == render_json(json.loads(j))
    md = render_markdown(rep)
    assert "| 1 | 3/6 = 0.500 | 3/6 = 0.500 | 3 | 0 | 0 |" in md
    assert "| 2 | 2/6 = 0.333 | 2/6 = 0.333 | 4 | 0 | 0 |" in md
    assert "resueltas / tareas del subconjunto" in md and "Secundaria: resueltas / validas" in md
    assert "| 2 | 0 | 1 | 0 | 0 | 3 |" in md  # motivos de la replica 2
    assert "**3/6** tareas evaluables" in md
    assert "| 2-3 | 6 | 1 | 1 | 2 | 2 | 3/6 = 0.500 |" in md
    assert "| `t5` | o/b | N | N | N | no |" in md
    assert "| o/b | 3 | 1/3 | 1/3 | 1/3 | 2/3 |" in md
    assert "Diferencia minima significativa" in md and "aproximadamente la mitad de las veces" in md
    assert (
        "- Suelo: 6 pares discordantes a favor de una condicion alcanzan alfa; "
        "con 6 tareas es una diferencia de 6/6 = 1.000." in md
    )
    assert "(maximo del rango, con 6 discordantes): 1.000." in md
    assert "INCOMPLETO" not in md
    assert "Recibos convertidos del 2026-10-01T10:00:00Z al 2026-10-03T10:00:00Z" in md


def test_markdown_marca_incompleto_y_lineas_vacias(tmp_path: Path) -> None:
    rep = analizar(tmp_path, {"t1": ["R", "R"], "t2": ["N", MISS], "t3": ["I", "N"]}, repos={})
    md = render_markdown(rep)
    assert "INCOMPLETO" in md
    assert "| `t2` | [2] |" in md and "| `t3` | 1 | sandbox_error |" in md
    assert "| `t2` | o/a | N | - | n/d |" in md


# ---------------------------------------------------------------------------
# Validacion de recibos
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("cambio", "texto"),
    [
        ({"patch": "diff --git ..."}, "claves desconocidas"),
        ({"test_patch": "x"}, "claves desconocidas"),
        ({"status": "exploto"}, "status"),
        ({"status": "timeout"}, "status"),  # estado de la version /1
        ({"resolved": True, "status": "unresolved", "failure_reason": "tests_failed"}, "contradice"),
        ({"resolved": False}, "contradice"),
        ({"resolved": 1}, "booleano"),
        ({"failure_reason": "pereza"}, "failure_reason"),
        ({"failure_reason": "tests_failed"}, "failure_reason"),  # resuelta con motivo de fallo
        ({"status": "infra_error", "resolved": False, "failure_reason": "tests_failed"}, "failure_reason"),
        ({"replica": 0}, "replica"),
        ({"replica": True}, "replica"),
        ({"tool_calls": -1}, "tool_calls"),
        ({"tool_calls": 1.5}, "tool_calls"),
        ({"duration_seconds": -0.1}, "duration_seconds"),
        ({"duration_seconds": float("nan")}, "duration_seconds"),
        ({"duration_seconds": "10"}, "duration_seconds"),
        ({"patch_sha256": "no-es-un-hash"}, "patch_sha256"),
        ({"patch_sha256": "A" * 64}, "patch_sha256"),
        ({"patch_sha256": None}, "null si y solo si"),  # hay parche (tamano 10) pero no hash
        ({"tasks_sha256": None}, "tasks_sha256"),
        ({"instance_id": ""}, "instance_id"),
        ({"converted_utc": "ayer"}, "converted_utc"),
        ({"converted_utc": "2026-13-45T00:00:00Z"}, "converted_utc"),
        ({"converted_utc": "2026-02-30T00:00:00Z"}, "converted_utc"),
        ({"converted_utc": 5}, "converted_utc"),
        ({"run_utc": "2026-99-01T00:00:00Z"}, "run_utc"),
        ({"schema_version": "kaggle-replica-receipt/1"}, "schema_version"),
        ({"created_utc": "2026-10-01T00:00:00Z"}, "claves desconocidas"),
        ({"harness_raw": "x"}, "harness_raw"),
    ],
)
def test_recibo_invalido(cambio: dict[str, Any], texto: str) -> None:
    with pytest.raises(ReplicasError, match=texto):
        parse_receipt({**receipt("t1", 1, "R"), **cambio}, "x:1")


def test_recibo_raw_incoherente_con_status() -> None:
    base = receipt("t1", 1, "N")
    # el recibo dice "no resuelta por pruebas" pero el crudo dice error de infraestructura
    raw_infra = {**base["harness_raw"], "error": "Sandbox execution error: x"}
    with pytest.raises(ReplicasError, match="no corresponden a 'harness_raw'"):
        parse_receipt({**base, "harness_raw": raw_infra}, "x:1")
    # el crudo trae un texto de error fuera de la lista cerrada
    with pytest.raises(ReplicasError, match="lista cerrada"):
        parse_receipt({**base, "harness_raw": {**base["harness_raw"], "error": "texto nuevo"}}, "x:1")
    # falta una clave del crudo / sobra una
    sin = dict(base["harness_raw"])
    del sin["test_exit_code"]
    with pytest.raises(ReplicasError, match="harness_raw"):
        parse_receipt({**base, "harness_raw": sin}, "x:1")
    with pytest.raises(ReplicasError, match="harness_raw"):
        parse_receipt({**base, "harness_raw": {**base["harness_raw"], "extra": 1}}, "x:1")


def test_recibo_sin_clave_obligatoria_y_no_objeto() -> None:
    r = receipt("t1", 1, "R")
    del r["sandbox_image"]
    with pytest.raises(ReplicasError, match="faltan claves"):
        parse_receipt(r, "x:1")
    with pytest.raises(ReplicasError, match="objeto JSON"):
        parse_receipt([1], "x:1")


@pytest.mark.parametrize("letra", list(RAWS))
def test_recibo_valido_de_cada_tipo(letra: str) -> None:
    r = parse_receipt({**receipt("t1", 1, letra), "run_utc": "2026-10-01T09:00:00Z"}, "x:1")
    assert (r.status, r.failure_reason) == RAWS[letra][:2]
    assert (r.patch_sha256 is None) == (RAWS[letra][2]["agent_patch_size"] == 0)
    assert parse_receipt({**receipt("t1", 1, letra), "run_utc": None}, "x:1").status == r.status


def test_status_es_el_del_recibo_no_uno_inventado() -> None:
    for letra in RAWS:
        assert parse_receipt(receipt("t1", 1, letra), "x").status == RAWS[letra][0]


def test_load_receipts_errores_de_lectura(tmp_path: Path) -> None:
    malo = tmp_path / "malo.jsonl"
    malo.write_text(json.dumps(receipt("t1", 1, "R")) + "\n{no es json\n", encoding="utf-8")
    with pytest.raises(ReplicasError, match=r"malo\.jsonl:2"):
        load_receipts([malo])
    with pytest.raises(ReplicasError, match="no encontrada"):
        load_receipts([tmp_path / "nada.jsonl"])
    vacio = tmp_path / "vacio"
    vacio.mkdir()
    with pytest.raises(ReplicasError, match="no contiene"):
        load_receipts([vacio])
    binario = tmp_path / "bin.jsonl"
    binario.write_bytes(b"\xff\xfe\x00\x80")
    with pytest.raises(ReplicasError, match="No se pudo leer"):
        load_receipts([binario])


@pytest.mark.parametrize("contenido", ["", "\n\n   \n", "  "])
def test_archivo_de_replica_sin_recibos_es_un_error(tmp_path: Path, contenido: str) -> None:
    buenos = tmp_path / "b.jsonl"
    buenos.write_text(json.dumps(receipt("t1", 1, "R")) + "\n", encoding="utf-8")
    vacio = tmp_path / "v.jsonl"
    vacio.write_text(contenido, encoding="utf-8")
    with pytest.raises(ReplicasError, match="ningun recibo"):
        load_receipts([buenos, vacio])


def test_lineas_en_blanco_entre_recibos_se_toleran(tmp_path: Path) -> None:
    f = tmp_path / "r.jsonl"
    f.write_text(
        "\n" + json.dumps(receipt("t1", 1, "R")) + "\n   \n\n" + json.dumps(receipt("t2", 1, "N")) + "\n\n",
        encoding="utf-8",
    )
    assert [r.instance_id for r in load_receipts([f])] == ["t1", "t2"]


def test_clave_duplicada_en_una_linea_json(tmp_path: Path) -> None:
    linea = json.dumps(receipt("t1", 1, "R"))[:-1] + ', "status": "unresolved"}'
    f = tmp_path / "r.jsonl"
    f.write_text(linea + "\n", encoding="utf-8")
    with pytest.raises(ReplicasError, match="clave duplicada"):
        load_receipts([f])
    with pytest.raises(ValueError, match="duplicada"):
        loads_strict('{"a": 1, "a": 2}')
    assert loads_strict('{"a": {"a": 1}}') == {"a": {"a": 1}}


@pytest.mark.parametrize(
    "contenido",
    [
        "{no es json",
        json.dumps([1, 2]),
        json.dumps({"x": 1}),  # sin test
        json.dumps({"test": "abc"}),  # test no es lista
        json.dumps({"test": {"a": 1}}),
        json.dumps({"test": []}),
        json.dumps({"test": ["a", "a"]}),
        json.dumps({"test": ["a", 3]}),
        json.dumps({"test": ["a"], "sha256_tasks": 5}),
        '{"test": ["a"], "test": ["b"]}',
    ],
)
def test_load_subset_invalido(tmp_path: Path, contenido: str) -> None:
    p = tmp_path / "s.json"
    p.write_text(contenido, encoding="utf-8")
    with pytest.raises(ReplicasError):
        load_subset(p)
    with pytest.raises(ReplicasError, match="no encontrado"):
        load_subset(tmp_path / "no_existe.json")


def test_hash_de_tasks_de_referencia(tmp_path: Path) -> None:
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"test": ["a"], "sha256_tasks": TASKS_SHA}), encoding="utf-8")
    s = load_subset(p)
    assert resolve_tasks_sha(s, None) == TASKS_SHA
    assert resolve_tasks_sha(s, TASKS_SHA) == TASKS_SHA
    with pytest.raises(ReplicasError, match="contradice"):
        resolve_tasks_sha(s, "d" * 64)
    with pytest.raises(ReplicasError, match="hexadecimal"):
        resolve_tasks_sha(s, "xyz")
    for contenido in ({"test": ["a"]}, {"test": ["a"], "sha256_tasks": ""}):
        p.write_text(json.dumps(contenido), encoding="utf-8")
        s = load_subset(p)
        with pytest.raises(ReplicasError, match="no declara"):
            resolve_tasks_sha(s, None)
        assert resolve_tasks_sha(s, "e" * 64) == "e" * 64
    p.write_text(json.dumps({"test": ["a"], "sha256_tasks": "corto"}), encoding="utf-8")
    with pytest.raises(ReplicasError, match="no es un SHA-256"):
        resolve_tasks_sha(load_subset(p), None)


# ---------------------------------------------------------------------------
# main() de punta a punta: integridad y codigos de salida
# ---------------------------------------------------------------------------


def run(capsys: pytest.CaptureFixture[str], *args: str) -> tuple[int, str, str]:
    code = main(list(args))
    cap = capsys.readouterr()
    return code, cap.out, cap.err


def reescribir(d: Path, fn: Any) -> None:
    """Aplica ``fn(archivo, filas) -> filas`` a los recibos de cada archivo."""
    for f in sorted(d.glob("*.jsonl")):
        rows = [json.loads(x) for x in f.read_text("utf-8").splitlines() if x.strip()]
        rows = fn(f, rows)
        f.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def en_replica2(**cambio: Any) -> Any:
    def fn(f: Path, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if f.name == "replica_2.jsonl":
            rows[0].update(cambio)
        return rows

    return fn


def test_main_ok_escribe_json_y_markdown_deterministas(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    d, s = write_case(tmp_path, CASO)
    j1, m1, j2, m2 = (tmp_path / n for n in ("a.json", "a.md", "b.json", "b.md"))
    assert (
        run(
            capsys,
            "analizar",
            "--recibos",
            str(d),
            "--subconjunto",
            str(s),
            "--salida-json",
            str(j1),
            "--salida-md",
            str(m1),
        )[0]
        == 0
    )
    files = sorted(d.glob("*.jsonl"))
    assert (
        run(
            capsys,
            "analizar",
            "--recibos",
            *map(str, reversed(files)),
            "--subconjunto",
            str(s),
            "--salida-json",
            str(j2),
            "--salida-md",
            str(m2),
        )[0]
        == 0
    )
    assert j1.read_bytes() == j2.read_bytes() and m1.read_bytes() == m2.read_bytes()
    assert json.loads(j1.read_text("utf-8"))["cambian_de_resultado"]["numerador"] == 3
    assert b"\r\n" not in j1.read_bytes()
    assert not list(tmp_path.glob("*.tmp"))


def test_main_sin_salidas_imprime_markdown(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    d, s = write_case(tmp_path, CASO)
    code, out, _ = run(capsys, "analizar", "--recibos", str(d), "--subconjunto", str(s))
    assert code == 0 and "## Tasa de resolucion por replica" in out


def test_main_faltante_sale_con_1_pero_escribe_el_reporte(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    d, s = write_case(tmp_path, {"t1": ["R", "R"], "t2": ["N", MISS]}, repos={})
    j = tmp_path / "r.json"
    code, _, err = run(
        capsys, "analizar", "--recibos", str(d), "--subconjunto", str(s), "--salida-json", str(j)
    )
    assert code == 1 and "INCOMPLETO" in err and "t2" in err
    rep = json.loads(j.read_text("utf-8"))
    assert rep["completo"] is False and rep["faltantes"] == [{"instance_id": "t2", "replicas": [2]}]


def test_main_infra_error_impide_la_salida_0(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    d, s = write_case(tmp_path, {"t1": ["R", "I"], "t2": ["N", "N"]}, repos={})
    j = tmp_path / "r.json"
    code, _, err = run(
        capsys, "analizar", "--recibos", str(d), "--subconjunto", str(s), "--salida-json", str(j)
    )
    assert code == 1
    assert "infraestructura" in err and "t1" in err
    rep = json.loads(j.read_text("utf-8"))
    assert rep["completo"] is False and rep["infra_afectadas"] == ["t1"]


@pytest.mark.parametrize(
    ("mutacion", "mensaje"),
    [
        (en_replica2(tasks_sha256="f" * 64), "tasks.jsonl"),
        (en_replica2(submission_sha256="f" * 64), "envio"),
        (en_replica2(condition="B"), "condicion"),
        (en_replica2(harness_version="otro"), "version del arnes"),
        (en_replica2(sandbox_image="otra"), "imagen del sandbox"),
        (en_replica2(repo="x/y"), "repositorios distintos"),
        (lambda f, rows: [{**r, "subset_sha256": "f" * 64} for r in rows], "subconjunto"),
        (
            lambda f, rows: (
                [*rows, receipt("zzz", 1, "R", subset_sha256=rows[0]["subset_sha256"])]
                if f.name == "replica_1.jsonl"
                else rows
            ),
            "fuera del subconjunto",
        ),
        (lambda f, rows: [*rows, dict(rows[0])] if f.name == "replica_1.jsonl" else rows, "duplicado"),
    ],
)
def test_main_falla_con_2_si_la_integridad_se_rompe(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], mutacion: Any, mensaje: str
) -> None:
    d, s = write_case(tmp_path, CASO)
    reescribir(d, mutacion)
    j = tmp_path / "r.json"
    code, out, err = run(
        capsys, "analizar", "--recibos", str(d), "--subconjunto", str(s), "--salida-json", str(j)
    )
    assert code == 2 and mensaje in err and err.startswith("ERROR:")
    assert not j.exists() and out == ""


def test_main_salida_2_borra_el_reporte_de_una_corrida_anterior(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    d, s = write_case(tmp_path, CASO)
    j, m = tmp_path / "r.json", tmp_path / "r.md"
    assert (
        run(
            capsys,
            "analizar",
            "--recibos",
            str(d),
            "--subconjunto",
            str(s),
            "--salida-json",
            str(j),
            "--salida-md",
            str(m),
        )[0]
        == 0
    )
    assert j.exists() and m.exists()
    with open(d / "replica_3.jsonl", "a", encoding="utf-8") as f:
        f.write("{truncado\n")
    assert (
        run(
            capsys,
            "analizar",
            "--recibos",
            str(d),
            "--subconjunto",
            str(s),
            "--salida-json",
            str(j),
            "--salida-md",
            str(m),
        )[0]
        == 2
    )
    assert not j.exists() and not m.exists()


def test_main_hash_de_tasks_sin_declaracion_en_el_subconjunto(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    d, s = write_case(tmp_path, CASO, declare_tasks=False)
    base = ("analizar", "--recibos", str(d), "--subconjunto", str(s))
    code, _, err = run(capsys, *base)
    assert code == 2 and "no declara" in err
    assert run(capsys, *base, "--tasks-sha256", TASKS_SHA)[0] == 0
    code, _, err = run(capsys, *base, "--tasks-sha256", "9" * 64)
    assert code == 2 and "tasks.jsonl" in err
    # mezcla de hashes entre recibos aunque el subconjunto no declare nada
    reescribir(d, en_replica2(tasks_sha256="f" * 64))
    code, _, err = run(capsys, *base, "--tasks-sha256", TASKS_SHA)
    assert code == 2 and "mezclan" in err


def test_main_hash_de_tasks_distinto_del_declarado(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    d, s = write_case(tmp_path, CASO)
    data = json.loads(s.read_text("utf-8"))
    data["sha256_tasks"] = "9" * 64
    s.write_text(json.dumps(data), encoding="utf-8")
    nuevo = hashlib.sha256(s.read_bytes()).hexdigest()
    reescribir(d, lambda f, rows: [{**r, "subset_sha256": nuevo} for r in rows])
    code, _, err = run(capsys, "analizar", "--recibos", str(d), "--subconjunto", str(s))
    assert code == 2 and "de referencia" in err and "tasks.jsonl" in err


def test_main_falla_con_menos_de_dos_replicas(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    d, s = write_case(tmp_path, {"t1": ["R"], "t2": ["N"]}, repos={})
    code, _, err = run(capsys, "analizar", "--recibos", str(d), "--subconjunto", str(s))
    assert code == 2 and "al menos 2 replicas" in err


def test_main_falla_si_una_replica_entera_falta(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    d, s = write_case(tmp_path, {"t1": ["R", "R"], "t2": ["N", "N"]}, repos={})
    (d / "replica_2.jsonl").unlink()
    code, _, err = run(capsys, "analizar", "--recibos", str(d), "--subconjunto", str(s))
    assert code == 2 and "al menos 2 replicas" in err


def test_main_falla_si_una_replica_esta_vacia(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    d, s = write_case(tmp_path, CASO)
    (d / "replica_3.jsonl").write_text("\n\n", encoding="utf-8")
    code, _, err = run(capsys, "analizar", "--recibos", str(d), "--subconjunto", str(s))
    assert code == 2 and "replica_3.jsonl" in err and "ningun recibo" in err


def test_main_falla_con_recibo_ilegible_o_con_parche(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    d, s = write_case(tmp_path, CASO)
    with open(d / "replica_3.jsonl", "a", encoding="utf-8") as f:
        f.write("{truncado\n")
    code, _, err = run(capsys, "analizar", "--recibos", str(d), "--subconjunto", str(s))
    assert code == 2 and "replica_3.jsonl" in err and "no es JSON valido" in err
    otro = tmp_path / "otro"
    otro.mkdir()
    d2, s2 = write_case(otro, CASO)
    reescribir(d2, lambda f, rows: [{**rows[0], "patch": "diff"}, *rows[1:]])
    code, _, err = run(capsys, "analizar", "--recibos", str(d2), "--subconjunto", str(s2))
    assert code == 2 and "claves desconocidas" in err


def test_main_falla_con_subconjunto_ilegible_o_ausente(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    d, s = write_case(tmp_path, CASO)
    s.write_text("{roto", encoding="utf-8")
    assert run(capsys, "analizar", "--recibos", str(d), "--subconjunto", str(s))[0] == 2
    assert run(capsys, "analizar", "--recibos", str(d), "--subconjunto", str(tmp_path / "no.json"))[0] == 2


def test_main_alfa(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    d, s = write_case(tmp_path, CASO)
    for alfa in ("0", "1", "-0.5"):
        code, _, err = run(capsys, "analizar", "--recibos", str(d), "--subconjunto", str(s), "--alfa", alfa)
        assert code == 2 and "--alfa" in err
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    run(capsys, "analizar", "--recibos", str(d), "--subconjunto", str(s), "--salida-json", str(a))
    run(
        capsys,
        "analizar",
        "--recibos",
        str(d),
        "--subconjunto",
        str(s),
        "--alfa",
        "0.2",
        "--salida-json",
        str(b),
    )
    ia = json.loads(a.read_text("utf-8"))["pares"][0]["intervalo_discordancia"]
    ib = json.loads(b.read_text("utf-8"))["pares"][0]["intervalo_discordancia"]
    assert ib["superior"] < ia["superior"] and ib["inferior"] > ia["inferior"]
    assert (
        json.loads(b.read_text("utf-8"))["margen"]["suelo"]["pares_discordantes_unilaterales"] == 4
    )  # 2/16 <= 0.2


def test_main_error_inesperado_no_sale_con_el_codigo_de_incompleto(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    d, s = write_case(tmp_path, CASO)

    def boom(*a: Any, **k: Any) -> Any:
        raise RuntimeError("fallo interno")

    monkeypatch.setattr(kr, "analyze", boom)
    code, _, err = run(capsys, "analizar", "--recibos", str(d), "--subconjunto", str(s))
    assert code == 3 and code not in (kr.EXIT_OK, kr.EXIT_INCOMPLETE, kr.EXIT_INVALID)
    assert "INESPERADO" in err and "fallo interno" in err


def test_argumentos_obligatorios(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["analizar"])
    assert exc.value.code == 2
    capsys.readouterr()


# ---------------------------------------------------------------------------
# Hash del envio
# ---------------------------------------------------------------------------


def hacer_envio(d: Path) -> None:
    (d / "z_ultimo").mkdir(parents=True)
    (d / "sub").mkdir()
    (d / "z_ultimo" / "m.txt").write_text("tres", encoding="utf-8")
    (d / "b.txt").write_text("dos", encoding="utf-8")  # creados fuera de orden alfabetico
    (d / "a.txt").write_text("uno", encoding="utf-8")
    (d / "sub" / "c.txt").write_text("cuatro", encoding="utf-8")


def test_sha256_directory_con_definicion_independiente(tmp_path: Path) -> None:
    d = tmp_path / "envio"
    hacer_envio(d)
    esperado = hashlib.sha256(
        "".join(
            f"{n}\t{sha(t)}\n"
            for n, t in [
                ("a.txt", "uno"),
                ("b.txt", "dos"),
                ("sub/c.txt", "cuatro"),
                ("z_ultimo/m.txt", "tres"),
            ]
        ).encode()
    ).hexdigest()
    assert sha256_directory(d) == esperado
    assert [r for r, _ in submission_files(d)] == ["a.txt", "b.txt", "sub/c.txt", "z_ultimo/m.txt"]


def test_sha256_directory_no_depende_del_orden_del_sistema_de_archivos(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    d = tmp_path / "envio"
    hacer_envio(d)
    base = sha256_directory(d)
    original = Path.rglob
    monkeypatch.setattr(Path, "rglob", lambda self, pat: reversed(list(original(self, pat))))
    assert sha256_directory(d) == base
    assert [r for r, _ in submission_files(d)] == ["a.txt", "b.txt", "sub/c.txt", "z_ultimo/m.txt"]


def test_sha256_directory_sensible_a_contenido_y_nombre(tmp_path: Path) -> None:
    d = tmp_path / "envio"
    hacer_envio(d)
    base = sha256_directory(d)
    (d / "a.txt").write_text("UNO", encoding="utf-8")
    cambiado = sha256_directory(d)
    assert cambiado != base
    (d / "a.txt").write_text("uno", encoding="utf-8")
    (d / "a.txt").rename(d / "aa.txt")
    assert sha256_directory(d) not in (base, cambiado)


def test_sha256_directory_ignora_basura_del_sistema(tmp_path: Path) -> None:
    d = tmp_path / "envio"
    hacer_envio(d)
    base = sha256_directory(d)
    (d / "__pycache__").mkdir()
    (d / "__pycache__" / "x.cpython-311.pyc").write_bytes(b"\x00")
    (d / "sub" / "__pycache__").mkdir()
    (d / "sub" / "__pycache__" / "notas.txt").write_text("cache", encoding="utf-8")
    (d / "suelto.pyc").write_bytes(b"\x01")
    (d / ".DS_Store").write_bytes(b"\x02")
    (d / "sub" / "Thumbs.db").write_bytes(b"\x03")
    (d / "desktop.ini").write_text("x", encoding="utf-8")
    assert sha256_directory(d) == base
    (d / ".gitignore").write_text("x", encoding="utf-8")  # un archivo oculto de verdad SI cuenta
    assert sha256_directory(d) != base


def test_sha256_directory_vacio_o_inexistente_es_error(tmp_path: Path) -> None:
    with pytest.raises(ReplicasError, match="no existe"):
        sha256_directory(tmp_path / "no_hay")
    vacio = tmp_path / "vacio"
    vacio.mkdir()
    with pytest.raises(ReplicasError, match="no tiene archivos"):
        sha256_directory(vacio)
    (vacio / "__pycache__").mkdir()
    (vacio / "__pycache__" / "a.pyc").write_bytes(b"x")
    with pytest.raises(ReplicasError, match="no tiene archivos"):
        sha256_directory(vacio)


def test_main_envio_contrasta_el_hash_y_lista_archivos(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    envio = tmp_path / "envio"
    hacer_envio(envio)
    d, s = write_case(tmp_path, CASO)
    reescribir(d, lambda f, rows: [{**r, "submission_sha256": sha256_directory(envio)} for r in rows])
    j = tmp_path / "r.json"
    m = tmp_path / "r.md"
    assert (
        run(
            capsys,
            "analizar",
            "--recibos",
            str(d),
            "--subconjunto",
            str(s),
            "--envio",
            str(envio),
            "--salida-json",
            str(j),
            "--salida-md",
            str(m),
        )[0]
        == 0
    )
    archivos = json.loads(j.read_text("utf-8"))["entrada"]["envio_archivos"]
    assert archivos[0] == {"ruta": "a.txt", "sha256": sha("uno")} and len(archivos) == 4
    assert f"| `a.txt` | `{sha('uno')}` |" in m.read_text("utf-8")
    (envio / "a.txt").write_text("cambiado", encoding="utf-8")  # el kit ya no es el de los recibos
    code, _, err = run(
        capsys, "analizar", "--recibos", str(d), "--subconjunto", str(s), "--envio", str(envio)
    )
    assert code == 2 and "hash del envio" in err
    code, _, err = run(
        capsys,
        "analizar",
        "--recibos",
        str(d),
        "--subconjunto",
        str(s),
        "--envio",
        str(tmp_path / "no_existe"),
    )
    assert code == 2 and "no existe" in err


# ---------------------------------------------------------------------------
# Conversor arnes -> recibos
# ---------------------------------------------------------------------------


def fila(iid: str, **over: Any) -> dict[str, Any]:
    r: dict[str, Any] = {
        "instance_id": iid,
        "repo": "o/a",
        "resolved": False,
        "agent_patch_size": 10,
        "test_exit_code": 1,
        "duration_seconds": 3.5,
        "error": None,
        "tool_calls": 4,
        "total_llm_calls": 6,
        "task_index": 1,
    }
    r.update(over)
    return r


def escribir_resultados(p: Path, filas: list[dict[str, Any]]) -> None:
    p.write_text("".join(json.dumps(f) + "\n" for f in filas), encoding="utf-8")


def args_conv(ids: list[str], patches: Path | None) -> dict[str, Any]:
    return {
        "patches_dir": patches,
        "subset_ids": ids,
        "replica": 1,
        "condition": "A",
        "submission_sha256": ENVIO_SHA,
        "tasks_sha256": TASKS_SHA,
        "subset_sha256": "c" * 64,
        "harness_version": "h",
        "sandbox_image": "i",
        "converted_utc": "2026-10-03T00:00:00Z",
    }


def test_conversor_estados_y_crudos(tmp_path: Path) -> None:
    patches = tmp_path / "patches"
    patches.mkdir()
    for n in ("ok", "mal", "apl", "rescate"):
        (patches / f"{n}.patch").write_text(f"parche-sintetico-{n}", encoding="utf-8")
    res = tmp_path / "task_results.jsonl"
    filas = [
        fila("ok", resolved=True, test_exit_code=0),
        fila("mal"),
        fila("vacio", agent_patch_size=0, test_exit_code=-1),
        fila("lento", error="Agent exceeded session timeout (30 min)", agent_patch_size=0, test_exit_code=-1),
        fila(
            "presup",
            error="Agent exceeded tool call budget (50 calls)",
            agent_patch_size=0,
            test_exit_code=-1,
        ),
        fila("apl", error="Failed to apply agent patch: x"),
        fila("infra", error="Sandbox execution error: docker", agent_patch_size=0, test_exit_code=-1),
        # el arnes rescata el parche tras un timeout y lo verifica: resolved manda, el error crudo se guarda
        fila("rescate", resolved=True, test_exit_code=0, error="Agent exceeded session timeout (30 min)"),
    ]
    escribir_resultados(res, filas)
    ids = [f["instance_id"] for f in filas]
    out = {r["instance_id"]: r for r in convert_harness_results(res, **args_conv(ids, patches))}
    assert {k: (v["status"], v["failure_reason"]) for k, v in out.items()} == {
        "ok": ("resolved", None),
        "mal": ("unresolved", "tests_failed"),
        "vacio": ("unresolved", "empty_patch"),
        "lento": ("unresolved", "agent_timeout"),
        "presup": ("unresolved", "budget_exhausted"),
        "apl": ("unresolved", "patch_apply_failed"),
        "infra": ("infra_error", None),
        "rescate": ("resolved", None),
    }
    assert out["rescate"]["resolved"] is True
    assert out["rescate"]["harness_raw"]["error"] == "Agent exceeded session timeout (30 min)"
    assert out["mal"]["harness_raw"] == {
        "resolved": False,
        "error": None,
        "test_exit_code": 1,
        "agent_patch_size": 10,
        "total_llm_calls": 6,
    }
    assert out["ok"]["patch_sha256"] == sha("parche-sintetico-ok")
    assert out["vacio"]["patch_sha256"] is None
    assert out["ok"]["tool_calls"] == 4 and out["ok"]["duration_seconds"] == 3.5
    assert "patch" not in out["ok"] and "run_utc" not in out["ok"] and "created_utc" not in out["ok"]
    assert out["ok"]["converted_utc"] == "2026-10-03T00:00:00Z"
    assert list(out) == sorted(out)
    # todo lo que emite el conversor lo acepta el analisis
    for r in out.values():
        parse_receipt(r, "x")


def test_conversor_run_utc_aparte(tmp_path: Path) -> None:
    res = tmp_path / "r.jsonl"
    escribir_resultados(res, [fila("x", agent_patch_size=0, test_exit_code=-1)])
    (r,) = convert_harness_results(res, **args_conv(["x"], None), run_utc="2026-10-02T08:00:00Z")
    assert r["run_utc"] == "2026-10-02T08:00:00Z" and r["converted_utc"] == "2026-10-03T00:00:00Z"
    with pytest.raises(ReplicasError, match="run_utc"):
        convert_harness_results(res, **args_conv(["x"], None), run_utc="ayer")
    with pytest.raises(ReplicasError, match="converted_utc"):
        convert_harness_results(res, **{**args_conv(["x"], None), "converted_utc": "2026-02-31T00:00:00Z"})


@pytest.mark.parametrize(
    ("cambio", "texto"),
    [
        ({"resolved": "True"}, "booleano"),
        ({"resolved": 1}, "booleano"),
        ({"agent_patch_size": -3}, "agent_patch_size"),
        ({"agent_patch_size": 2.5}, "agent_patch_size"),
        ({"test_exit_code": None}, "test_exit_code"),
        ({"error": "texto que el arnes no escribe"}, "lista cerrada"),
        ({"resolved": True, "test_exit_code": 1}, "incoherente"),
        ({"test_exit_code": -7}, "no se clasifica"),
        ({"test_exit_code": 139}, "no se clasifica"),
        ({"tool_calls": "4"}, "tool_calls"),
        ({"tool_calls": -1}, "tool_calls"),
        ({"duration_seconds": "3"}, "duration_seconds"),
        ({"duration_seconds": -1.0}, "duration_seconds"),
        ({"repo": ""}, "repo"),
        ({"repo": None}, "repo"),
        ({"instance_id": 7}, "instance_id"),
        ({"instance_id": ""}, "instance_id"),
    ],
)
def test_conversor_sale_con_error_ante_datos_incoherentes(
    tmp_path: Path, cambio: dict[str, Any], texto: str
) -> None:
    res = tmp_path / "r.jsonl"
    escribir_resultados(res, [fila("x", **cambio)])
    patches = tmp_path / "p"
    patches.mkdir()
    (patches / "x.patch").write_text("p", encoding="utf-8")
    with pytest.raises(ReplicasError, match=texto):
        convert_harness_results(res, **args_conv(["x"], patches))


def test_conversor_falla_si_falta_parche_clave_o_archivo(tmp_path: Path) -> None:
    res = tmp_path / "r.jsonl"
    escribir_resultados(res, [fila("x")])
    with pytest.raises(ReplicasError, match="no se puede calcular su hash"):
        convert_harness_results(res, **args_conv(["x"], None))
    row = fila("x")
    del row["tool_calls"]
    escribir_resultados(res, [row])
    with pytest.raises(ReplicasError, match="falta la clave 'tool_calls'"):
        convert_harness_results(res, **args_conv(["x"], None))
    row = fila("x")
    del row["total_llm_calls"]
    escribir_resultados(res, [row])
    with pytest.raises(ReplicasError, match="falta la clave 'total_llm_calls'"):
        convert_harness_results(res, **args_conv(["x"], None))
    res.write_text("{roto\n", encoding="utf-8")
    with pytest.raises(ReplicasError, match="no es JSON valido"):
        convert_harness_results(res, **args_conv(["x"], None))
    res.write_text('{"instance_id": "x", "instance_id": "y"}\n', encoding="utf-8")
    with pytest.raises(ReplicasError, match="duplicada"):
        convert_harness_results(res, **args_conv(["x"], None))
    res.write_text("\n", encoding="utf-8")
    with pytest.raises(ReplicasError, match="no tiene filas"):
        convert_harness_results(res, **args_conv(["x"], None))
    with pytest.raises(ReplicasError, match="No se pudo leer"):
        convert_harness_results(tmp_path / "no.jsonl", **args_conv(["x"], None))


def test_conversor_rechaza_duplicados_y_tareas_ajenas(tmp_path: Path) -> None:
    res = tmp_path / "r.jsonl"
    vacia = {"agent_patch_size": 0, "test_exit_code": -1}
    escribir_resultados(res, [fila("x", **vacia), fila("x", **vacia)])
    with pytest.raises(ReplicasError, match="repetidas"):
        convert_harness_results(res, **args_conv(["x"], None))
    escribir_resultados(res, [fila("x", **vacia), fila("ajena", **vacia)])
    with pytest.raises(ReplicasError, match="fuera del subconjunto"):
        convert_harness_results(res, **args_conv(["x"], None))


def test_convertir_cli_no_sobrescribe_ni_escribe_con_errores(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    envio = tmp_path / "e"
    envio.mkdir()
    (envio / "x").write_text("x", encoding="utf-8")
    tasks = tmp_path / "t.jsonl"
    tasks.write_text("{}\n", encoding="utf-8")
    subset = tmp_path / "s.json"
    subset.write_text(json.dumps({"test": ["t1"], "sha256_tasks": TASKS_SHA}), encoding="utf-8")
    res = tmp_path / "r.jsonl"
    escribir_resultados(res, [fila("t1", agent_patch_size=0, test_exit_code=-1)])
    salida = tmp_path / "o.jsonl"
    base = (
        "convertir",
        "--task-results",
        str(res),
        "--replica",
        "1",
        "--condicion",
        "A",
        "--envio",
        str(envio),
        "--tasks",
        str(tasks),
        "--subconjunto",
        str(subset),
        "--version-arnes",
        "h",
        "--imagen-sandbox",
        "i",
        "--convertido-utc",
        "2026-10-03T00:00:00Z",
        "--salida",
        str(salida),
    )
    assert run(capsys, *base)[0] == 0
    original = salida.read_bytes()
    code, _, err = run(capsys, *base)
    assert code == 2 and "ya existe" in err and salida.read_bytes() == original
    # tarea ajena al subconjunto: nada se escribe
    salida2 = tmp_path / "o2.jsonl"
    escribir_resultados(res, [fila("ajena", agent_patch_size=0, test_exit_code=-1)])
    cmd2 = [a if a != str(salida) else str(salida2) for a in base]
    code, _, err = run(capsys, *cmd2)
    assert code == 2 and "fuera del subconjunto" in err and not salida2.exists()
    # error del arnes desconocido: salida 2 con el texto
    escribir_resultados(res, [fila("t1", error="algo raro del arnes", agent_patch_size=0, test_exit_code=-1)])
    code, _, err = run(capsys, *cmd2)
    assert code == 2 and "algo raro del arnes" in err and not salida2.exists()
    # envio inexistente
    cmd3 = [a if a != str(envio) else str(tmp_path / "nada") for a in cmd2]
    code, _, err = run(capsys, *cmd3)
    assert code == 2 and "no existe" in err


def test_convertir_y_analizar_de_punta_a_punta(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    envio = tmp_path / "envio"
    envio.mkdir()
    (envio / "agent.yaml").write_text("nombre: sintetico", encoding="utf-8")
    tasks = tmp_path / "tasks.jsonl"
    tasks.write_text('{"instance_id": "t1"}\n', encoding="utf-8")
    subset = tmp_path / "subset.json"
    subset.write_text(
        json.dumps({"sha256_tasks": hashlib.sha256(tasks.read_bytes()).hexdigest(), "test": ["t1", "t2"]}),
        encoding="utf-8",
    )
    patches = tmp_path / "patches"
    patches.mkdir()
    for n in ("t1", "t2"):
        (patches / f"{n}.patch").write_text(n, encoding="utf-8")
    rdir = tmp_path / "recibos"
    for rep, (r1, r2) in enumerate([(True, False), (False, False)], start=1):
        res = tmp_path / f"res{rep}.jsonl"
        escribir_resultados(
            res,
            [
                fila("t1", resolved=r1, test_exit_code=0 if r1 else 1),
                fila("t2", resolved=r2, test_exit_code=0 if r2 else 1),
            ],
        )
        code, out, _ = run(
            capsys,
            "convertir",
            "--task-results",
            str(res),
            "--patches",
            str(patches),
            "--replica",
            str(rep),
            "--condicion",
            "A",
            "--envio",
            str(envio),
            "--tasks",
            str(tasks),
            "--subconjunto",
            str(subset),
            "--version-arnes",
            "swegemma-x",
            "--imagen-sandbox",
            "img:y",
            "--convertido-utc",
            "2026-10-03T00:00:00Z",
            "--run-utc",
            "2026-10-02T08:00:00Z",
            "--salida",
            str(rdir / f"replica_{rep}.jsonl"),
        )
        assert code == 0 and "2 recibos" in out
    j = tmp_path / "rep.json"
    code, _, _ = run(
        capsys,
        "analizar",
        "--recibos",
        str(rdir),
        "--subconjunto",
        str(subset),
        "--envio",
        str(envio),
        "--salida-json",
        str(j),
    )
    assert code == 0
    rep = json.loads(j.read_text("utf-8"))
    assert [(p["resueltas"], p["validas"]) for p in rep["por_replica"]] == [(1, 2), (0, 2)]
    assert rep["cambian_de_resultado"]["tareas"] == ["t1"]
    assert rep["entrada"]["envio_sha256"] == sha256_directory(envio)
    assert rep["entrada"]["tasks_sha256"] == hashlib.sha256(tasks.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# N1: rutas de salida (no borrar nunca algo ajeno ni una entrada)
# ---------------------------------------------------------------------------


def args_analizar(d: Path, s: Path) -> list[str]:
    return ["analizar", "--recibos", str(d), "--subconjunto", str(s)]


def assert_exit2_sin_tocar(
    capsys: pytest.CaptureFixture[str], argv: list[str], intactos: dict[Path, bytes]
) -> str:
    code, _, err = run(capsys, *argv)
    assert code == 2 and err.startswith("ERROR:")
    for ruta, contenido in intactos.items():
        assert ruta.is_file() and ruta.read_bytes() == contenido
    return err


def test_salida_json_igual_a_un_recibo_no_lo_borra(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    d, s = write_case(tmp_path, CASO)
    recibo = d / "replica_1.jsonl"
    antes = {recibo: recibo.read_bytes(), s: s.read_bytes()}
    err = assert_exit2_sin_tocar(capsys, [*args_analizar(d, s), "--salida-json", str(recibo)], antes)
    assert "entrada" in err


def test_salida_md_igual_al_subconjunto_no_lo_borra(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    d, s = write_case(tmp_path, CASO)
    antes = {s: s.read_bytes()}
    assert_exit2_sin_tocar(capsys, [*args_analizar(d, s), "--salida-md", str(s)], antes)
    assert_exit2_sin_tocar(capsys, [*args_analizar(d, s), "--salida-json", str(s)], antes)


def test_salida_dentro_del_directorio_de_recibos_o_del_envio(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    d, s = write_case(tmp_path, CASO)
    envio = tmp_path / "envio"
    hacer_envio(envio)
    # recibos coherentes con el envio: si la ruta no se rechazara, el analisis saldria bien y escribiria
    reescribir(d, lambda f, rows: [{**r, "submission_sha256": sha256_directory(envio)} for r in rows])
    antes = {s: s.read_bytes(), **{f: f.read_bytes() for f in d.glob("*.jsonl")}}
    nuevo_en_recibos = d / "reporte.json"
    assert_exit2_sin_tocar(capsys, [*args_analizar(d, s), "--salida-json", str(nuevo_en_recibos)], antes)
    assert not nuevo_en_recibos.exists()
    en_envio = envio / "reporte.md"
    assert_exit2_sin_tocar(
        capsys, [*args_analizar(d, s), "--envio", str(envio), "--salida-md", str(en_envio)], antes
    )
    assert not en_envio.exists()
    # la propia ruta del directorio y rutas disfrazadas con «..»
    assert_exit2_sin_tocar(capsys, [*args_analizar(d, s), "--salida-json", str(d)], antes)
    disfrazada = d / ".." / "recibos" / "replica_2.jsonl"
    antes[d / "replica_2.jsonl"] = (d / "replica_2.jsonl").read_bytes()
    assert_exit2_sin_tocar(capsys, [*args_analizar(d, s), "--salida-json", str(disfrazada)], antes)


def test_recibos_dados_como_archivos_tambien_son_entradas(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    d, s = write_case(tmp_path, CASO)
    archivos = sorted(d.glob("*.jsonl"))
    antes = {f: f.read_bytes() for f in archivos}
    argv = [
        "analizar",
        "--recibos",
        *map(str, archivos),
        "--subconjunto",
        str(s),
        "--salida-md",
        str(archivos[2]),
    ]
    assert_exit2_sin_tocar(capsys, argv, antes)


def test_json_y_md_en_la_misma_ruta(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    d, s = write_case(tmp_path, CASO)
    mismo = tmp_path / "salida.out"
    err = assert_exit2_sin_tocar(
        capsys, [*args_analizar(d, s), "--salida-json", str(mismo), "--salida-md", str(mismo)], {}
    )
    assert "la misma ruta" in err and not mismo.exists()


def test_salida_ajena_existente_no_se_borra_ni_con_error_de_entrada(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    d, s = write_case(tmp_path, CASO)
    ajeno_json = tmp_path / "datos.json"
    ajeno_json.write_text('{"version_reporte": 3, "otro": true}', encoding="utf-8")  # version no es texto
    ajeno_md = tmp_path / "notas.md"
    ajeno_md.write_text("# Mis notas\n", encoding="utf-8")
    plano = tmp_path / "plano.json"
    plano.write_text("no es json", encoding="utf-8")
    json_ajeno = tmp_path / "otro.json"
    json_ajeno.write_text('{"a": 1}', encoding="utf-8")
    for ruta, flag in (
        (ajeno_json, "--salida-json"),
        (plano, "--salida-json"),
        (json_ajeno, "--salida-json"),
        (ajeno_md, "--salida-md"),
    ):
        antes = {ruta: ruta.read_bytes()}
        err = assert_exit2_sin_tocar(capsys, [*args_analizar(d, s), flag, str(ruta)], antes)
        assert "no es un reporte" in err
        # y tampoco si ademas la entrada es ilegible
        (d / "replica_1.jsonl").write_text("{roto\n", encoding="utf-8")
        assert_exit2_sin_tocar(capsys, [*args_analizar(d, s), flag, str(ruta)], antes)
    # un archivo con el encabezado del reporte pero pasado como JSON, y al reves, tampoco es propio
    md_propio = tmp_path / "x.md"
    md_propio.write_text(kr.REPORT_MD_HEADER + "\n", encoding="utf-8")
    assert_exit2_sin_tocar(
        capsys, [*args_analizar(d, s), "--salida-json", str(md_propio)], {md_propio: md_propio.read_bytes()}
    )
    json_propio = tmp_path / "y.json"
    json_propio.write_text(json.dumps({"version_reporte": kr.REPORT_VERSION}), encoding="utf-8")
    assert_exit2_sin_tocar(
        capsys,
        [*args_analizar(d, s), "--salida-md", str(json_propio)],
        {json_propio: json_propio.read_bytes()},
    )


def test_salida_que_es_un_directorio(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    d, s = write_case(tmp_path, CASO)
    carpeta = tmp_path / "carpeta"
    carpeta.mkdir()
    err = assert_exit2_sin_tocar(capsys, [*args_analizar(d, s), "--salida-json", str(carpeta)], {})
    assert "directorio" in err and carpeta.is_dir()


def test_solo_se_borra_un_reporte_propio_y_se_reescribe(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    d, s = write_case(tmp_path, CASO)
    j, m = tmp_path / "r.json", tmp_path / "r.md"
    j.write_text(
        json.dumps({"version_reporte": "kaggle-replica-analysis/1", "viejo": True}), encoding="utf-8"
    )
    m.write_text(kr.REPORT_MD_HEADER + "\nviejo\n", encoding="utf-8")
    assert run(capsys, *args_analizar(d, s), "--salida-json", str(j), "--salida-md", str(m))[0] == 0
    assert "viejo" not in j.read_text("utf-8") and "viejo" not in m.read_text("utf-8")
    # con error de entrada, el reporte propio anterior si desaparece
    with open(d / "replica_3.jsonl", "a", encoding="utf-8") as f:
        f.write("{roto\n")
    assert run(capsys, *args_analizar(d, s), "--salida-json", str(j), "--salida-md", str(m))[0] == 2
    assert not j.exists() and not m.exists()


def test_reporte_anterior_que_no_se_puede_borrar_se_declara_obsoleto(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    d, s = write_case(tmp_path, CASO)
    j = tmp_path / "r.json"
    assert run(capsys, *args_analizar(d, s), "--salida-json", str(j))[0] == 0
    viejo = j.read_bytes()
    original = Path.unlink

    def unlink(self: Path, missing_ok: bool = False) -> None:
        if self == j:
            raise PermissionError("archivo abierto en otro proceso")
        original(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", unlink)
    code, _, err = run(capsys, *args_analizar(d, s), "--salida-json", str(j))
    assert code == 2
    assert "sigue en disco" in err and "obsoleto" in err and "abierto en otro proceso" in err
    assert j.read_bytes() == viejo


# ---------------------------------------------------------------------------
# N3: escritura de JSON y Markdown, ambos o ninguno
# ---------------------------------------------------------------------------


def test_si_falla_el_segundo_renombrado_no_queda_ningun_archivo_nuevo(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    d, s = write_case(tmp_path, CASO)
    salidas = tmp_path / "out"
    j, m = salidas / "r.json", salidas / "r.md"
    real = kr.os.replace
    llamadas = []

    def replace(src: Any, dst: Any) -> None:
        llamadas.append(dst)
        if len(llamadas) == 2:
            raise OSError("disco lleno")
        real(src, dst)

    monkeypatch.setattr(kr.os, "replace", replace)
    code, _, err = run(capsys, *args_analizar(d, s), "--salida-json", str(j), "--salida-md", str(m))
    assert code == 2 and "disco lleno" in err
    assert len(llamadas) == 2
    assert not j.exists() and not m.exists() and list(salidas.iterdir()) == []


def test_si_falla_la_escritura_del_segundo_temporal_no_queda_nada(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    d, s = write_case(tmp_path, CASO)
    salidas = tmp_path / "out"
    j, m = salidas / "r.json", salidas / "r.md"
    real = kr.tempfile.mkstemp
    n = []

    def mkstemp(*a: Any, **k: Any) -> Any:
        n.append(1)
        if len(n) == 2:
            raise OSError("sin espacio")
        return real(*a, **k)

    monkeypatch.setattr(kr.tempfile, "mkstemp", mkstemp)
    code, _, _ = run(capsys, *args_analizar(d, s), "--salida-json", str(j), "--salida-md", str(m))
    assert code == 2 and list(salidas.iterdir()) == []


def test_temporal_con_nombre_unico_no_pisa_un_archivo_ajeno(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    d, s = write_case(tmp_path, CASO)
    j = tmp_path / "r.json"
    ajeno = tmp_path / "r.json.tmp"
    ajeno.write_text("no tocar", encoding="utf-8")
    assert run(capsys, *args_analizar(d, s), "--salida-json", str(j))[0] == 0
    assert ajeno.read_text("utf-8") == "no tocar"
    assert sorted(p.name for p in tmp_path.glob("*.tmp")) == ["r.json.tmp"]


# ---------------------------------------------------------------------------
# N2: codigos de salida de las pruebas sin error del arnes
# ---------------------------------------------------------------------------


def test_infra_por_codigo_de_salida_deja_incompleto_con_su_motivo(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rep = analizar(tmp_path, {"t1": ["R", "X"], "t2": ["N", "N"]}, repos={})
    assert rep["completo"] is False
    assert rep["errores_de_infraestructura"] == [
        {"instance_id": "t1", "replica": 2, "status": "infra_error", "infra_reason": "test_timeout"}
    ]
    assert rep["por_replica"][1]["infra_error"] == 1 and rep["por_replica"][1]["no_resueltas"] == 1
    assert "| `t1` | 2 | test_timeout |" in render_markdown(rep)
    otro = tmp_path / "otro"
    otro.mkdir()
    d, s = write_case(otro, {"t1": ["R", "X"], "t2": ["N", "N"]}, repos={})
    assert run(capsys, *args_analizar(d, s))[0] == 1


@pytest.mark.parametrize(
    ("codigo", "motivo"), [(-1, "test_exec_failed"), (124, "test_timeout"), (137, "test_killed")]
)
def test_conversor_infra_por_codigo_de_salida(tmp_path: Path, codigo: int, motivo: str) -> None:
    patches = tmp_path / "p"
    patches.mkdir()
    (patches / "x.patch").write_text("p", encoding="utf-8")
    res = tmp_path / "r.jsonl"
    escribir_resultados(res, [fila("x", test_exit_code=codigo)])
    (r,) = convert_harness_results(res, **args_conv(["x"], patches))
    assert (r["status"], r["failure_reason"], r["infra_reason"]) == ("infra_error", None, motivo)
    assert r["harness_raw"]["test_exit_code"] == codigo and r["harness_raw"]["error"] is None


# ---------------------------------------------------------------------------
# N4: huecos de pruebas
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("letra", "cambio", "texto"),
    [
        ("N", {"failure_reason": "empty_patch"}, "no corresponden a 'harness_raw'"),
        ("N", {"failure_reason": "agent_timeout"}, "no corresponden a 'harness_raw'"),
        ("T", {"failure_reason": "tests_failed"}, "no corresponden a 'harness_raw'"),
        ("E", {"failure_reason": "budget_exhausted"}, "no corresponden a 'harness_raw'"),
        ("I", {"infra_reason": "test_timeout"}, "no corresponden a 'harness_raw'"),
        ("X", {"infra_reason": "sandbox_error"}, "no corresponden a 'harness_raw'"),
        ("I", {"infra_reason": None}, "infra_reason"),
        ("I", {"infra_reason": "pereza"}, "infra_reason"),
        ("N", {"infra_reason": "sandbox_error"}, "salvo con status"),
        ("R", {"infra_reason": "sandbox_error"}, "salvo con status"),
    ],
)
def test_editar_el_motivo_de_un_recibo_a_otro_valido_lo_rechaza(
    letra: str, cambio: dict[str, Any], texto: str
) -> None:
    parse_receipt(receipt("t1", 1, letra), "x")  # el recibo sin editar es valido
    with pytest.raises(ReplicasError, match=texto):
        parse_receipt({**receipt("t1", 1, letra), **cambio}, "x")


def test_main_rechaza_un_recibo_con_failure_reason_editado(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    d, s = write_case(tmp_path, CASO)
    reescribir(d, en_replica2(failure_reason="empty_patch"))  # la primera fila de la replica 2 es «R»
    code, _, err = run(capsys, *args_analizar(d, s))
    assert code == 2 and "failure_reason" in err
    # un motivo valido pero distinto del que sale del crudo (fila «N» de la replica 1)
    d2 = tmp_path / "otro"
    d2.mkdir()
    d3, s3 = write_case(d2, CASO)

    def editar(f: Path, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if f.name == "replica_1.jsonl":
            fila_n = next(r for r in rows if r["status"] == "unresolved")
            fila_n["failure_reason"] = "empty_patch"
        return rows

    reescribir(d3, editar)
    code, _, err = run(capsys, *args_analizar(d3, s3))
    assert code == 2 and "no corresponden a 'harness_raw'" in err


def test_conversor_replica_cero(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    res = tmp_path / "r.jsonl"
    escribir_resultados(res, [fila("x", agent_patch_size=0, test_exit_code=-1)])
    for replica in (0, -1, True, "1"):
        with pytest.raises(ReplicasError, match="replica"):
            convert_harness_results(res, **{**args_conv(["x"], None), "replica": replica})
    envio = tmp_path / "e"
    envio.mkdir()
    (envio / "f").write_text("f", encoding="utf-8")
    tasks = tmp_path / "t.jsonl"
    tasks.write_text("{}\n", encoding="utf-8")
    subset = tmp_path / "s.json"
    subset.write_text(json.dumps({"test": ["x"], "sha256_tasks": TASKS_SHA}), encoding="utf-8")
    salida = tmp_path / "o.jsonl"
    code, _, err = run(
        capsys,
        "convertir",
        "--task-results",
        str(res),
        "--replica",
        "0",
        "--condicion",
        "A",
        "--envio",
        str(envio),
        "--tasks",
        str(tasks),
        "--subconjunto",
        str(subset),
        "--version-arnes",
        "h",
        "--imagen-sandbox",
        "i",
        "--salida",
        str(salida),
    )
    assert code == 2 and "replica" in err and not salida.exists()


@pytest.mark.parametrize("alfa", [0, 0.0, 1, 1.0, -0.1, 1.5])
def test_discordance_floor_rechaza_alfa_fuera_de_rango(alfa: float) -> None:
    with pytest.raises(ValueError, match="alpha"):
        discordance_floor(alfa)


# ---------------------------------------------------------------------------
# N5 / N6
# ---------------------------------------------------------------------------


def test_resolved_con_parche_vacio_manda(tmp_path: Path) -> None:
    fila_ok = raw(resolved=True, test_exit_code=0, agent_patch_size=0)
    assert classify_harness(fila_ok, "x") == ("resolved", None, None)
    res = tmp_path / "r.jsonl"
    escribir_resultados(res, [fila("x", resolved=True, test_exit_code=0, agent_patch_size=0)])
    (r,) = convert_harness_results(res, **args_conv(["x"], None))
    assert r["status"] == "resolved" and r["resolved"] is True and r["patch_sha256"] is None
    assert r["harness_raw"]["agent_patch_size"] == 0 and r["harness_raw"]["error"] is None
    assert parse_receipt(r, "x").status == "resolved"


@pytest.mark.parametrize(
    "valor",
    [
        "2026-1-1T00:00:00Z",
        "2026-10-03T0:00:00Z",
        " 2026-10-03T00:00:00Z",
        "2026-10-03T00:00:00Z\n",
        "2026-10-03 00:00:00Z",
        "2026-10-03T00:00:00",
        "2026-10-03T00:00:00+00:00",
        "２０２６-10-03T00:00:00Z",
    ],
)
def test_fecha_utc_estricta(valor: str) -> None:
    with pytest.raises(ReplicasError, match="converted_utc"):
        parse_receipt({**receipt("t1", 1, "R"), "converted_utc": valor}, "x")


def test_hash_con_salto_de_linea_no_es_un_sha256() -> None:
    with pytest.raises(ReplicasError, match="patch_sha256"):
        parse_receipt({**receipt("t1", 1, "R"), "patch_sha256": "a" * 64 + "\n"}, "x")


def test_parche_de_un_id_con_barra_usa_dos_guiones_bajos(tmp_path: Path) -> None:
    patches = tmp_path / "p"
    patches.mkdir()
    (patches / "org__repo-7.patch").write_text("parche-sintetico", encoding="utf-8")
    res = tmp_path / "r.jsonl"
    escribir_resultados(res, [fila("org/repo-7", resolved=True, test_exit_code=0)])
    (r,) = convert_harness_results(res, **args_conv(["org/repo-7"], patches))
    assert r["patch_sha256"] == sha("parche-sintetico")
    (patches / "org__repo-7.patch").rename(patches / "org_repo-7.patch")
    with pytest.raises(ReplicasError, match="no se puede calcular su hash"):
        convert_harness_results(res, **args_conv(["org/repo-7"], patches))


def test_stdout_y_stderr_en_utf8(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import io
    import sys

    out_b, err_b = io.BytesIO(), io.BytesIO()
    out = io.TextIOWrapper(out_b, encoding="cp1252", errors="strict")
    err = io.TextIOWrapper(err_b, encoding="cp1252", errors="strict")
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr(sys, "stderr", err)
    s = tmp_path / "subset.json"
    s.write_text(json.dumps({"test": ["a"], "sha256_tasks": TASKS_SHA}), encoding="utf-8")
    code = main(["analizar", "--recibos", str(tmp_path / "no→existe.jsonl"), "--subconjunto", str(s)])
    err.flush()
    assert code == 2
    assert "no→existe" in err_b.getvalue().decode("utf-8")
