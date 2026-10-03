"""Pruebas de scripts/kaggle_replicas.py con datos sinteticos inventados.

Cada numero del reporte esta fijado a mano en un caso pequeno (ver ``CASO``). Ningun dato de la
competencia entra aqui: los ids, repositorios y hashes son inventados.
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
    clopper_pearson,
    convert_harness_results,
    load_receipts,
    load_subset,
    main,
    mcnemar_exact_p,
    min_detectable_difference,
    parse_receipt,
    render_json,
    render_markdown,
    sha256_directory,
)

TASKS_SHA = "a" * 64
ENVIO_SHA = "b" * 64
R, N, T, I_, V = "resolved", "unresolved", "timeout", "infra_error", "empty_patch"
MISS = "-"

REPOS = {"t1": "o/a", "t2": "o/a", "t3": "o/a", "t4": "o/b", "t5": "o/b", "t6": "o/b"}
# Caso a mano: tres replicas, seis tareas, un timeout (t5 en la replica 2).
CASO: dict[str, list[str]] = {
    "t1": [R, R, R],
    "t2": [R, N, R],
    "t3": [N, N, N],
    "t4": [R, R, N],
    "t5": [N, T, N],
    "t6": [N, N, R],
}


def sha(texto: str) -> str:
    return hashlib.sha256(texto.encode()).hexdigest()


def receipt(iid: str, rep: int, status: str, repo: str = "o/a", **over: Any) -> dict[str, Any]:
    r: dict[str, Any] = {
        "schema_version": kr.SCHEMA_VERSION,
        "instance_id": iid,
        "repo": repo,
        "condition": "A",
        "replica": rep,
        "status": status,
        "resolved": status == R,
        "tool_calls": rep * 10,
        "duration_seconds": 12.5,
        "patch_sha256": None if status in (T, I_, V) else sha(f"{iid}-{rep}"),
        "submission_sha256": ENVIO_SHA,
        "tasks_sha256": TASKS_SHA,
        "subset_sha256": "",
        "harness_version": "swegemma-0.0.0",
        "sandbox_image": "img:sintetica",
        "created_utc": f"2026-10-0{rep}T10:00:00Z",
    }
    r.update(over)
    return r


def write_case(
    tmp_path: Path,
    grid: dict[str, list[str]],
    repos: dict[str, str] | None = None,
    subset_ids: list[str] | None = None,
) -> tuple[Path, Path]:
    """Escribe el subconjunto y un .jsonl por replica; devuelve (directorio de recibos, subconjunto)."""
    subset = tmp_path / "subset.json"
    ids = subset_ids if subset_ids is not None else sorted(grid)
    subset.write_text(json.dumps({"sha256_tasks": TASKS_SHA, "test": ids}), encoding="utf-8")
    subset_sha = hashlib.sha256(subset.read_bytes()).hexdigest()
    d = tmp_path / "recibos"
    d.mkdir()
    n_rep = max(len(v) for v in grid.values())
    for rep in range(1, n_rep + 1):
        lines = []
        for iid, row in grid.items():
            if row[rep - 1] == MISS:
                continue
            lines.append(
                json.dumps(
                    receipt(
                        iid, rep, row[rep - 1], (repos or REPOS).get(iid, "o/a"), subset_sha256=subset_sha
                    )
                )
            )
        (d / f"replica_{rep}.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return d, subset


def analizar(tmp_path: Path, grid: dict[str, list[str]], **kw: Any) -> dict[str, Any]:
    d, s = write_case(tmp_path, grid, **kw)
    receipts = load_receipts([d])
    sub = load_subset(s)
    assert check_integrity(receipts, sub) == []
    return analyze(receipts, sub)


# ---------------------------------------------------------------------------
# Estadistica
# ---------------------------------------------------------------------------


def test_binom_cdf_valores_a_mano() -> None:
    assert binom_cdf(1, 3, 0.5) == pytest.approx(0.5)
    assert binom_cdf(0, 6, 0.5) == pytest.approx(1 / 64)
    assert binom_cdf(-1, 4, 0.3) == 0.0
    assert binom_cdf(4, 4, 0.3) == 1.0


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
    assert lo < lo90 < 0.6 < hi90 < hi  # menor confianza, intervalo mas estrecho


def test_clopper_pearson_rechaza_entradas_invalidas() -> None:
    with pytest.raises(ValueError):
        clopper_pearson(1, 0)
    with pytest.raises(ValueError):
        clopper_pearson(6, 5)


def test_mcnemar_exacto() -> None:
    assert mcnemar_exact_p(0, 0) == 1.0
    assert mcnemar_exact_p(6, 0) == pytest.approx(2 / 64)
    assert mcnemar_exact_p(0, 6) == pytest.approx(2 / 64)  # simetrica
    assert mcnemar_exact_p(1, 1) == 1.0  # el doble de la cola se recorta a 1
    assert mcnemar_exact_p(5, 1) == pytest.approx(2 * 7 / 64)  # (1 + 6) colas


@pytest.mark.parametrize(
    ("d", "n", "g", "dif_pares", "tasa"),
    [(6, 10, 6, 6, 0.6), (8, 20, 8, 8, 0.4), (10, 20, 9, 8, 0.4), (12, 40, 10, 8, 0.2)],
)
def test_diferencia_minima_detectable(d: int, n: int, g: int, dif_pares: int, tasa: float) -> None:
    x = min_detectable_difference(d, n)
    assert x["alcanzable"] is True
    assert (x["ganadas_minimas"], x["diferencia_pares"], x["diferencia_tasa"]) == (g, dif_pares, tasa)


@pytest.mark.parametrize(("d", "n"), [(0, 10), (3, 5), (5, 5)])
def test_diferencia_minima_no_alcanzable_con_pocos_discordantes(d: int, n: int) -> None:
    x = min_detectable_difference(d, n)
    assert x["alcanzable"] is False
    assert x["diferencia_tasa"] is None


def test_diferencia_minima_depende_de_alfa() -> None:
    assert min_detectable_difference(5, 5, alpha=0.1)["alcanzable"] is True  # 2/32 = 0.0625 <= 0.1
    with pytest.raises(ValueError):
        min_detectable_difference(6, 5)


# ---------------------------------------------------------------------------
# Caso a mano: cada numero del reporte
# ---------------------------------------------------------------------------


def test_tasa_por_replica_con_numerador_y_denominador(tmp_path: Path) -> None:
    rep = analizar(tmp_path, CASO)
    p1, p2, p3 = rep["por_replica"]
    # replica 1: resuelve t1,t2,t4 (3 de 6)
    assert (p1["resueltas"], p1["no_resueltas"], p1["validas"], p1["tasa_sobre_validas"]) == (3, 3, 6, 0.5)
    # replica 2: resuelve t1,t4; t5 es timeout y NO cuenta como no resuelta
    assert (p2["resueltas"], p2["no_resueltas"], p2["validas"]) == (2, 3, 5)
    assert p2["tasa_sobre_validas"] == 0.4
    assert p2["tasa_sobre_subconjunto"] == round(2 / 6, 6)
    assert p2["errores"] == {"timeout": 1, "infra_error": 0, "empty_patch": 0}
    assert p2["errores_total"] == 1
    # replica 3: resuelve t1,t2,t6
    assert (p3["resueltas"], p3["validas"], p3["tasa_sobre_validas"]) == (3, 6, 0.5)
    assert all(p["faltantes"] == 0 and p["tareas_subconjunto"] == 6 for p in (p1, p2, p3))


def test_tareas_que_cambian_de_resultado(tmp_path: Path) -> None:
    rep = analizar(tmp_path, CASO)
    c = rep["cambian_de_resultado"]
    # t2 (R,N,R), t4 (R,R,N), t6 (N,N,R) cambian; t5 tiene 2 validas iguales (N,N) y no cambia
    assert (c["numerador"], c["denominador"]) == (3, 6)
    assert c["tareas"] == ["t2", "t4", "t6"]
    assert c["no_evaluables"] == []
    por_tarea = {t["instance_id"]: t for t in rep["tareas"]}
    assert por_tarea["t5"]["cambia"] is False
    assert por_tarea["t5"]["validas"] == 2
    assert por_tarea["t5"]["resultados"] == {"1": N, "2": T, "3": N}
    assert por_tarea["t1"]["cambia"] is False and por_tarea["t1"]["resueltas"] == 3
    assert por_tarea["t2"]["resueltas"] == 2 and por_tarea["t2"]["validas"] == 3


def test_acuerdo_por_pares(tmp_path: Path) -> None:
    rep = analizar(tmp_path, CASO)
    p12, p13, p23 = rep["pares"]
    assert [p12["replicas"], p13["replicas"], p23["replicas"]] == [[1, 2], [1, 3], [2, 3]]
    # 1-2: sin t5 -> n=5; RR en t1,t4; R/N en t2; NN en t3,t6
    assert (p12["comparables"], p12["ambas_resueltas"], p12["solo_primera"], p12["solo_segunda"]) == (
        5,
        2,
        1,
        0,
    )
    assert p12["ninguna_resuelta"] == 2 and p12["discordantes"] == 1
    assert p12["acuerdo"] == {"numerador": 4, "denominador": 5, "tasa": 0.8}
    assert p12["tasa_discordancia"] == 0.2
    assert p12["intervalo_discordancia"]["inferior"] == pytest.approx(0.0051, abs=1e-4)
    assert p12["intervalo_discordancia"]["superior"] == pytest.approx(0.7164, abs=1e-4)
    assert p12["mcnemar_p_exacto"] == 1.0
    # 1-3: n=6; RR t1,t2; NN t3,t5; R/N t4; N/R t6
    assert (p13["comparables"], p13["ambas_resueltas"], p13["solo_primera"], p13["solo_segunda"]) == (
        6,
        2,
        1,
        1,
    )
    assert p13["acuerdo"] == {"numerador": 4, "denominador": 6, "tasa": round(4 / 6, 6)}
    assert p13["discordantes"] == 2
    # 2-3: sin t5 -> n=5; RR t1; N/R t2,t6; R/N t4; NN t3
    assert (p23["comparables"], p23["ambas_resueltas"], p23["solo_primera"], p23["solo_segunda"]) == (
        5,
        1,
        1,
        2,
    )
    assert p23["ninguna_resuelta"] == 1
    assert p23["acuerdo"] == {"numerador": 2, "denominador": 5, "tasa": 0.4}
    assert p23["tasa_discordancia"] == 0.6


def test_desglose_por_repositorio(tmp_path: Path) -> None:
    rep = analizar(tmp_path, CASO)
    a, b = rep["por_repositorio"]
    assert (a["repo"], a["tareas"]) == ("o/a", 3)
    assert [(x["resueltas"], x["validas"]) for x in a["por_replica"]] == [(2, 3), (1, 3), (2, 3)]
    assert a["cambian"] == {"numerador": 1, "denominador": 3}  # solo t2
    assert (b["repo"], b["tareas"]) == ("o/b", 3)
    assert [(x["resueltas"], x["validas"], x["errores"]) for x in b["por_replica"]] == [
        (1, 3, 0),
        (1, 2, 1),
        (1, 3, 0),
    ]
    assert b["cambian"] == {"numerador": 2, "denominador": 3}  # t4 y t6


def test_errores_aparte_y_sin_faltantes(tmp_path: Path) -> None:
    rep = analizar(tmp_path, CASO)
    assert rep["errores_de_infraestructura"] == [{"instance_id": "t5", "replica": 2, "status": T}]
    assert rep["faltantes"] == []
    assert rep["completo"] is True


def test_margen_del_caso_a_mano(tmp_path: Path) -> None:
    rep = analizar(tmp_path, CASO)
    m = rep["margen"]
    assert m["calculable"] is True
    assert m["diferencia_observada_entre_replicas"] == 0.1  # 0.5 - 0.4
    assert m["par_base"] == [2, 3]  # el de mayor discordancia: 3/5
    assert (m["comparables"], m["discordantes_observados"]) == (5, 3)
    assert m["con_discordancia_observada"]["alcanzable"] is False
    assert m["con_limite_superior"]["alcanzable"] is False  # ceil(0.9 * 5) = 5 discordantes: 2/32 > 0.05
    assert m["con_limite_superior"]["discordantes"] == 5


def test_margen_alcanzable(tmp_path: Path) -> None:
    grid = {f"u{i}": [R, N] for i in range(1, 7)} | {f"u{i}": [N, N] for i in range(7, 11)}
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
    assert m["con_discordancia_observada"]["ganadas_minimas"] == 6
    assert m["con_discordancia_observada"]["diferencia_tasa"] == 0.6
    assert m["limite_superior_discordancia"] == pytest.approx(0.8784, abs=1e-3)
    # ceil(0.8784 * 10) = 9 discordantes -> 8 ganadas, diferencia 7/10
    assert m["con_limite_superior"]["discordantes"] == 9
    assert m["con_limite_superior"]["diferencia_pares"] == 7
    assert m["con_limite_superior"]["diferencia_tasa"] == 0.7


def test_error_no_se_cuenta_como_no_resuelta_ni_cambia_resultado(tmp_path: Path) -> None:
    # R en la replica 1 y error de infraestructura en la 2: solo una valida -> no evaluable
    rep = analizar(tmp_path, {"t1": [R, I_], "t2": [N, N]}, repos={})
    c = rep["cambian_de_resultado"]
    assert (c["numerador"], c["denominador"], c["no_evaluables"]) == (0, 1, ["t1"])
    assert rep["por_replica"][1]["no_resueltas"] == 1 and rep["por_replica"][1]["errores"]["infra_error"] == 1
    assert rep["pares"][0]["comparables"] == 1  # solo t2 es comparable
    assert rep["pares"][0]["mcnemar_p_exacto"] == 1.0
    assert rep["errores_de_infraestructura"] == [{"instance_id": "t1", "replica": 2, "status": I_}]


@pytest.mark.parametrize("estado_error", [T, I_, V])
def test_los_tres_tipos_de_error_van_aparte(tmp_path: Path, estado_error: str) -> None:
    rep = analizar(tmp_path, {"t1": [R, estado_error], "t2": [N, N], "t3": [R, R]}, repos={})
    assert rep["por_replica"][1]["errores"][estado_error] == 1
    assert rep["por_replica"][1]["validas"] == 2
    assert rep["por_replica"][1]["no_resueltas"] == 1


def test_faltante_se_reporta_y_no_se_omite(tmp_path: Path) -> None:
    rep = analizar(tmp_path, {"t1": [R, R], "t2": [N, MISS], "t3": [R, N]}, repos={})
    assert rep["completo"] is False
    assert rep["faltantes"] == [{"instance_id": "t2", "replicas": [2]}]
    assert rep["por_replica"][1]["faltantes"] == 1
    assert rep["por_replica"][1]["validas"] == 2
    assert rep["por_replica"][1]["tasa_sobre_subconjunto"] == round(1 / 3, 6)


def test_tarea_sin_ningun_recibo_cuenta_como_faltante(tmp_path: Path) -> None:
    d, s = write_case(tmp_path, {"t1": [R, R], "t2": [N, N]}, subset_ids=["t1", "t2", "t9"])
    rep = analyze(load_receipts([d]), load_subset(s))
    assert rep["faltantes"] == [{"instance_id": "t9", "replicas": [1, 2]}]
    assert rep["cambian_de_resultado"]["no_evaluables"] == ["t9"]
    assert rep["tareas"][-1]["repo"] is None


def test_no_se_ignora_ninguna_replica(tmp_path: Path) -> None:
    rep = analizar(tmp_path, {"t1": [R, R, N], "t2": [N, N, N]}, repos={})
    assert rep["entrada"]["replicas"] == [1, 2, 3]
    assert len(rep["por_replica"]) == 3 and len(rep["pares"]) == 3
    assert rep["cambian_de_resultado"]["tareas"] == ["t1"]  # solo la tercera replica lo delata


def test_replicas_no_consecutivas(tmp_path: Path) -> None:
    d, s = write_case(tmp_path, {"t1": [R, R, N]}, repos={})
    (d / "replica_2.jsonl").unlink()
    rep = analyze(load_receipts([d]), load_subset(s))
    assert rep["entrada"]["replicas"] == [1, 3]
    assert rep["pares"][0]["replicas"] == [1, 3]


def test_margen_no_calculable_sin_comparables(tmp_path: Path) -> None:
    rep = analizar(tmp_path, {"t1": [R, T], "t2": [T, R]}, repos={})
    assert rep["pares"][0]["comparables"] == 0
    assert rep["pares"][0]["acuerdo"]["tasa"] is None
    assert rep["pares"][0]["intervalo_discordancia"] is None
    assert rep["margen"]["calculable"] is False
    assert "Ningun" in render_markdown(rep) or "No calculable" in render_markdown(rep)


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


def test_invariante_al_orden_de_los_archivos_y_del_subconjunto(tmp_path: Path) -> None:
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
    assert j.endswith("}\n") and json.loads(j) == rep
    assert j == render_json(json.loads(j))  # mismo contenido, mismos bytes
    md = render_markdown(rep)
    assert "| 1 | 3/6 | 6 | 0.500 | 3/6 = 0.500 | 0 | 0 |" in md
    assert "| 2 | 2/5 | 5 | 0.400 | 2/6 = 0.333 | 1 | 0 |" in md
    assert "**3/6** tareas evaluables" in md
    assert "| 2-3 | 5 | 1 | 1 | 2 | 1 | 2/5 = 0.400 |" in md
    assert "| `t5` | o/b | N | T | N | no |" in md
    assert "| `t5` | 2 | timeout |" in md
    assert "| o/b | 3 | 1/3 | 1/2 | 1/3 | 2/3 |" in md
    assert "INCOMPLETO" not in md


def test_markdown_marca_incompleto(tmp_path: Path) -> None:
    rep = analizar(tmp_path, {"t1": [R, R], "t2": [N, MISS]}, repos={})
    md = render_markdown(rep)
    assert "INCOMPLETO" in md
    assert "| `t2` | [2] |" in md
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
        ({"resolved": True, "status": N}, "contradice"),
        ({"resolved": 1}, "booleano"),
        ({"replica": 0}, "replica"),
        ({"replica": True}, "replica"),
        ({"tool_calls": -1}, "tool_calls"),
        ({"tool_calls": 1.5}, "tool_calls"),
        ({"duration_seconds": -0.1}, "duration_seconds"),
        ({"duration_seconds": float("nan")}, "duration_seconds"),
        ({"duration_seconds": "10"}, "duration_seconds"),
        ({"patch_sha256": "no-es-un-hash"}, "patch_sha256"),
        ({"patch_sha256": "A" * 64}, "patch_sha256"),
        ({"tasks_sha256": None}, "tasks_sha256"),
        ({"instance_id": ""}, "instance_id"),
        ({"created_utc": "ayer"}, "created_utc"),
        ({"schema_version": "otra/9"}, "schema_version"),
        ({"llm_calls": -3}, "llm_calls"),
    ],
)
def test_recibo_invalido(cambio: dict[str, Any], texto: str) -> None:
    with pytest.raises(ReplicasError, match=texto):
        parse_receipt({**receipt("t1", 1, R, subset_sha256="c" * 64), **cambio}, "x:1")


def test_recibo_sin_clave_obligatoria_y_no_objeto() -> None:
    r = receipt("t1", 1, R, subset_sha256="c" * 64)
    del r["sandbox_image"]
    with pytest.raises(ReplicasError, match="faltan claves"):
        parse_receipt(r, "x:1")
    with pytest.raises(ReplicasError, match="objeto JSON"):
        parse_receipt([1], "x:1")


def test_recibo_valido_con_opcionales() -> None:
    r = parse_receipt(receipt("t1", 1, V, subset_sha256="c" * 64, llm_calls=4), "x:1")
    assert r.status == V and r.patch_sha256 is None and r.tool_calls == 10


def test_load_receipts_errores_de_lectura(tmp_path: Path) -> None:
    malo = tmp_path / "malo.jsonl"
    malo.write_text(json.dumps(receipt("t1", 1, R)) + "\n{no es json\n", encoding="utf-8")
    with pytest.raises(ReplicasError, match=r"malo\.jsonl:"):
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


@pytest.mark.parametrize(
    "contenido",
    [
        "{no es json",
        json.dumps([1, 2]),
        json.dumps({"test": []}),
        json.dumps({"test": ["a", "a"]}),
        json.dumps({"test": ["a", 3]}),
        json.dumps({"test": ["a"], "sha256_tasks": 5}),
    ],
)
def test_load_subset_invalido(tmp_path: Path, contenido: str) -> None:
    p = tmp_path / "s.json"
    p.write_text(contenido, encoding="utf-8")
    with pytest.raises(ReplicasError):
        load_subset(p)
    with pytest.raises(ReplicasError, match="no encontrado"):
        load_subset(tmp_path / "no_existe.json")


# ---------------------------------------------------------------------------
# main() de punta a punta: integridad y codigos de salida
# ---------------------------------------------------------------------------


def run(capsys: pytest.CaptureFixture[str], *args: str) -> tuple[int, str, str]:
    code = main(list(args))
    cap = capsys.readouterr()
    return code, cap.out, cap.err


def reescribir(d: Path, fn: Any) -> None:
    """Aplica ``fn(lista_de_recibos) -> lista`` a los recibos de cada archivo."""
    for f in sorted(d.glob("*.jsonl")):
        rows = [json.loads(x) for x in f.read_text("utf-8").splitlines() if x.strip()]
        rows = fn(f, rows)
        f.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


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


def test_main_sin_salidas_imprime_markdown(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    d, s = write_case(tmp_path, CASO)
    code, out, _ = run(capsys, "analizar", "--recibos", str(d), "--subconjunto", str(s))
    assert code == 0 and "## Tasa de resolucion por replica" in out


def test_main_faltante_sale_con_1_pero_escribe_el_reporte(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    d, s = write_case(tmp_path, {"t1": [R, R], "t2": [N, MISS]}, repos={})
    j = tmp_path / "r.json"
    code, _, err = run(
        capsys, "analizar", "--recibos", str(d), "--subconjunto", str(s), "--salida-json", str(j)
    )
    assert code == 1
    assert "INCOMPLETO" in err and "t2" in err
    rep = json.loads(j.read_text("utf-8"))
    assert rep["completo"] is False and rep["faltantes"] == [{"instance_id": "t2", "replicas": [2]}]


def _hash_tasks_distinto(f: Path, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if f.name == "replica_2.jsonl":
        rows[0]["tasks_sha256"] = "f" * 64
    return rows


def _hash_envio_distinto(f: Path, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if f.name == "replica_2.jsonl":
        rows[0]["submission_sha256"] = "f" * 64
    return rows


def _hash_subconjunto_distinto(f: Path, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for r in rows:
        r["subset_sha256"] = "f" * 64  # todos coinciden entre si, pero no con el archivo
    return rows


def _tarea_fuera(f: Path, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if f.name == "replica_1.jsonl":
        rows.append(receipt("zzz", 1, R, subset_sha256=rows[0]["subset_sha256"]))
    return rows


def _duplicado(f: Path, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if f.name == "replica_1.jsonl":
        rows.append(dict(rows[0]))
    return rows


def _condicion_distinta(f: Path, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if f.name == "replica_2.jsonl":
        rows[0]["condition"] = "B"
    return rows


def _arnes_distinto(f: Path, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if f.name == "replica_2.jsonl":
        rows[0]["harness_version"] = "otro"
    return rows


def _imagen_distinta(f: Path, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if f.name == "replica_2.jsonl":
        rows[0]["sandbox_image"] = "otra"
    return rows


def _repo_incoherente(f: Path, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if f.name == "replica_2.jsonl":
        rows[0]["repo"] = "x/y"
    return rows


@pytest.mark.parametrize(
    ("mutacion", "mensaje"),
    [
        (_hash_tasks_distinto, "tasks.jsonl"),
        (_hash_envio_distinto, "envio"),
        (_hash_subconjunto_distinto, "subconjunto"),
        (_tarea_fuera, "fuera del subconjunto"),
        (_duplicado, "duplicado"),
        (_condicion_distinta, "condicion"),
        (_arnes_distinto, "version del arnes"),
        (_imagen_distinta, "imagen del sandbox"),
        (_repo_incoherente, "repositorios distintos"),
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
    assert code == 2
    assert mensaje in err and err.startswith("ERROR:")
    assert not j.exists() and out == ""  # sin reporte parcial


def test_main_falla_si_el_hash_de_tasks_no_es_el_del_subconjunto(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    d, s = write_case(tmp_path, CASO)
    data = json.loads(s.read_text("utf-8"))
    data["sha256_tasks"] = "9" * 64
    s.write_text(json.dumps(data), encoding="utf-8")
    # el hash del archivo cambio: reescribe tambien ese hash en los recibos para aislar la otra causa
    nuevo = hashlib.sha256(s.read_bytes()).hexdigest()
    reescribir(d, lambda f, rows: [{**r, "subset_sha256": nuevo} for r in rows])
    code, _, err = run(capsys, "analizar", "--recibos", str(d), "--subconjunto", str(s))
    assert code == 2 and "declara el subconjunto" in err


def test_main_falla_con_menos_de_dos_replicas(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    d, s = write_case(tmp_path, {"t1": [R], "t2": [N]}, repos={})
    code, _, err = run(capsys, "analizar", "--recibos", str(d), "--subconjunto", str(s))
    assert code == 2 and "al menos 2 replicas" in err


def test_main_falla_si_una_replica_entera_falta(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    d, s = write_case(tmp_path, {"t1": [R, R], "t2": [N, N]}, repos={})
    (d / "replica_2.jsonl").unlink()
    code, _, err = run(capsys, "analizar", "--recibos", str(d), "--subconjunto", str(s))
    assert code == 2 and "al menos 2 replicas" in err


def test_main_falla_con_recibo_ilegible(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    d, s = write_case(tmp_path, CASO)
    with open(d / "replica_3.jsonl", "a", encoding="utf-8") as f:
        f.write("{truncado\n")
    code, _, err = run(capsys, "analizar", "--recibos", str(d), "--subconjunto", str(s))
    assert code == 2 and "replica_3.jsonl" in err and "no es JSON valido" in err


def test_main_falla_con_recibo_con_parche(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    d, s = write_case(tmp_path, CASO)
    reescribir(d, lambda f, rows: [{**rows[0], "patch": "diff"}, *rows[1:]])
    code, _, err = run(capsys, "analizar", "--recibos", str(d), "--subconjunto", str(s))
    assert code == 2 and "claves desconocidas" in err


def test_main_falla_con_subconjunto_ilegible_o_ausente(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    d, s = write_case(tmp_path, CASO)
    s.write_text("{roto", encoding="utf-8")
    assert run(capsys, "analizar", "--recibos", str(d), "--subconjunto", str(s))[0] == 2
    assert run(capsys, "analizar", "--recibos", str(d), "--subconjunto", str(tmp_path / "no.json"))[0] == 2


def test_main_alfa_invalido(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    d, s = write_case(tmp_path, CASO)
    for alfa in ("0", "1", "-0.5"):
        code, _, err = run(capsys, "analizar", "--recibos", str(d), "--subconjunto", str(s), "--alfa", alfa)
        assert code == 2 and "--alfa" in err


def test_main_alfa_cambia_el_intervalo(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    d, s = write_case(tmp_path, CASO)
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


def test_argumentos_obligatorios(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["analizar"])
    assert exc.value.code == 2
    capsys.readouterr()


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


def args_conv(p: Path, patches: Path | None) -> dict[str, Any]:
    return {
        "patches_dir": patches,
        "replica": 1,
        "condition": "A",
        "submission_sha256": ENVIO_SHA,
        "tasks_sha256": TASKS_SHA,
        "subset_sha256": "c" * 64,
        "harness_version": "h",
        "sandbox_image": "i",
        "created_utc": "2026-10-03T00:00:00Z",
    }


def test_conversor_estados(tmp_path: Path) -> None:
    patches = tmp_path / "patches"
    patches.mkdir()
    for n in ("ok", "mal"):
        (patches / f"{n}.patch").write_text(f"parche-sintetico-{n}", encoding="utf-8")
    res = tmp_path / "task_results.jsonl"
    escribir_resultados(
        res,
        [
            fila("ok", resolved=True),
            fila("mal", resolved=False),
            fila("vacio", agent_patch_size=0, resolved=False),
            fila("lento", error="Timeout after 600s", agent_patch_size=0),
            fila("infra", error="docker daemon not running", agent_patch_size=0),
            fila("lento2", error="request timed out", agent_patch_size=0),
        ],
    )
    out = {r["instance_id"]: r for r in convert_harness_results(res, **args_conv(res, patches))}
    assert {k: v["status"] for k, v in out.items()} == {
        "ok": R,
        "mal": N,
        "vacio": V,
        "lento": T,
        "infra": I_,
        "lento2": T,
    }
    assert out["ok"]["resolved"] is True and out["mal"]["resolved"] is False
    assert out["ok"]["patch_sha256"] == sha("parche-sintetico-ok")
    assert out["vacio"]["patch_sha256"] is None
    assert (
        out["ok"]["tool_calls"] == 4 and out["ok"]["llm_calls"] == 6 and out["ok"]["duration_seconds"] == 3.5
    )
    assert "patch" not in out["ok"]
    assert list(out) == sorted(out)  # salida ordenada por instance_id


def test_conversor_error_gana_aunque_el_arnes_diga_resuelta(tmp_path: Path) -> None:
    res = tmp_path / "r.jsonl"
    escribir_resultados(res, [fila("x", resolved=True, error="boom", agent_patch_size=0)])
    (r,) = convert_harness_results(res, **args_conv(res, None))
    assert r["status"] == I_ and r["resolved"] is False


def test_conversor_falla_si_falta_el_parche_o_la_clave(tmp_path: Path) -> None:
    res = tmp_path / "r.jsonl"
    escribir_resultados(res, [fila("x")])
    with pytest.raises(ReplicasError, match="no se puede calcular su hash"):
        convert_harness_results(res, **args_conv(res, None))
    row = fila("x")
    del row["tool_calls"]
    escribir_resultados(res, [row])
    with pytest.raises(ReplicasError, match="falta la clave 'tool_calls'"):
        convert_harness_results(res, **args_conv(res, None))
    res.write_text("{roto\n", encoding="utf-8")
    with pytest.raises(ReplicasError, match="no es JSON valido"):
        convert_harness_results(res, **args_conv(res, None))
    res.write_text("\n", encoding="utf-8")
    with pytest.raises(ReplicasError, match="no tiene filas"):
        convert_harness_results(res, **args_conv(res, None))
    with pytest.raises(ReplicasError, match="No se pudo leer"):
        convert_harness_results(tmp_path / "no.jsonl", **args_conv(res, None))


def test_sha256_directory_es_sensible_a_contenido_y_nombre(tmp_path: Path) -> None:
    d = tmp_path / "envio"
    (d / "sub").mkdir(parents=True)
    (d / "a.txt").write_text("uno", encoding="utf-8")
    (d / "sub" / "b.txt").write_text("dos", encoding="utf-8")
    base = sha256_directory(d)
    assert base == sha256_directory(d) and len(base) == 64
    (d / "a.txt").write_text("UNO", encoding="utf-8")
    cambiado = sha256_directory(d)
    assert cambiado != base
    (d / "a.txt").write_text("uno", encoding="utf-8")
    (d / "a.txt").rename(d / "c.txt")
    assert sha256_directory(d) not in (base, cambiado)
    with pytest.raises(ReplicasError):
        sha256_directory(tmp_path / "no_hay")


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
        escribir_resultados(res, [fila("t1", resolved=r1), fila("t2", resolved=r2)])
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
            "--fecha-utc",
            "2026-10-03T00:00:00Z",
            "--salida",
            str(rdir / f"replica_{rep}.jsonl"),
        )
        assert code == 0 and "2 recibos" in out
    j = tmp_path / "rep.json"
    code, _, _ = run(
        capsys, "analizar", "--recibos", str(rdir), "--subconjunto", str(subset), "--salida-json", str(j)
    )
    assert code == 0
    rep = json.loads(j.read_text("utf-8"))
    assert [(p["resueltas"], p["validas"]) for p in rep["por_replica"]] == [(1, 2), (0, 2)]
    assert rep["cambian_de_resultado"]["tareas"] == ["t1"]
    assert rep["entrada"]["envio_sha256"] == sha256_directory(envio)
    assert rep["entrada"]["tasks_sha256"] == hashlib.sha256(tasks.read_bytes()).hexdigest()


def test_convertir_sin_parche_falla_con_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    envio = tmp_path / "e"
    envio.mkdir()
    (envio / "x").write_text("x", encoding="utf-8")
    tasks = tmp_path / "t.jsonl"
    tasks.write_text("{}\n", encoding="utf-8")
    subset = tmp_path / "s.json"
    subset.write_text("{}", encoding="utf-8")
    res = tmp_path / "r.jsonl"
    escribir_resultados(res, [fila("t1")])
    code, _, err = run(
        capsys,
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
        "--salida",
        str(tmp_path / "o.jsonl"),
    )
    assert code == 2 and "ERROR:" in err
    assert not (tmp_path / "o.jsonl").exists()
