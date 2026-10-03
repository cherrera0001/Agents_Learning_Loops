"""Pruebas de scripts/kaggle_eda.py con tareas sinteticas inventadas (ningun dato de la competencia)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts import kaggle_eda as eda
from scripts import kaggle_replicas as kr


def diff(lineas: int, archivo: str = "x.py") -> str:
    """Diff sintetico de un archivo con ``lineas`` lineas cambiadas y una de contexto.

    Mismo formato que los de la competencia: cabecera ``--- a/`` y ``+++ b/``, sin ``diff --git``.
    Las lineas quitadas empiezan por ``-- `` a proposito: no deben confundirse con una cabecera.
    """
    mas = [f"+linea {i}" for i in range(0, lineas, 2)]
    menos = [f"--- linea {i}" for i in range(1, lineas, 2)]
    bloque = f"@@ -1,{len(menos) + 1} +1,{len(mas) + 1} @@ def f():"
    return "\n".join([f"--- a/{archivo}", f"+++ b/{archivo}", bloque, " contexto", *menos, *mas])


def tarea(
    i: int, repo: str, enunciado: int, parche: int, pruebas: int, fecha: str, **extra: Any
) -> dict[str, Any]:
    return {
        "instance_id": f"t{i}",
        "repo": repo,
        "base_commit": f"{i % 5:040d}",
        "problem_statement": "x" * enunciado,
        "hints_text": "",
        "patch": diff(parche),
        "test_patch": diff(pruebas),
        "created_at": fecha,
        **extra,
    }


TAREAS = [
    tarea(1, "o/a", 10, 1, 4, "2025-09-30T00:00:00Z"),
    tarea(2, "o/a", 20, 2, 6, "2025-10-01T00:00:00Z"),
    tarea(3, "o/a", 30, 3, 8, "2025-12-31T00:00:00Z"),
    tarea(4, "o/b", 40, 10, 2, "2026-01-01T00:00:00Z"),
    tarea(5, "o/b", 50, 11, 2, "2026-04-01T00:00:00Z"),
    tarea(6, "o/b", 60, 100, 2, "2024-02-01T00:00:00Z", hints_text="una pista"),
]


def escribir(tmp_path: Path, tareas: list[dict[str, Any]]) -> Path:
    p = tmp_path / "tasks.jsonl"
    p.write_text("".join(json.dumps(t) + "\n" for t in tareas) + "\n", encoding="utf-8")
    return p


def test_lineas_cambiadas_no_cuenta_cabeceras_ni_contexto() -> None:
    assert eda.changed_lines(diff(7)) == 7
    assert eda.changed_lines("") == 0
    # 4 anadidas y 3 quitadas; 3 cabeceras + 1 de contexto + 7 cambiadas = 11 lineas totales
    s = eda.diff_stats(diff(7))
    assert (s.archivos, s.anadidas, s.quitadas, s.cambiadas, s.totales) == (1, 4, 3, 7, 11)


def test_archivos_por_parche_sin_cabecera_diff_git() -> None:
    """Los diffs de la competencia no traen ``diff --git``: los archivos se cuentan por ``---``/``+++``."""
    dos = diff(3, "a.py") + "\n" + diff(5, "pkg/b.py")
    assert "diff --git" not in dos
    s = eda.diff_stats(dos)
    assert (s.archivos, s.cambiadas) == (2, 8)
    # con la cabecera de git delante tambien se cuenta una vez por archivo
    con_git = "diff --git a/a.py b/a.py\nindex 111..222 100644\n" + diff(3, "a.py")
    assert eda.diff_stats(con_git).archivos == 1 and eda.diff_stats(con_git).cambiadas == 3
    # archivo nuevo, bloque sin longitudes (una linea) y marca de fin de archivo sin salto de linea
    nuevo = "--- /dev/null\n+++ b/n.py\n@@ -0,0 +1 @@\n+unica\n\\ No newline at end of file"
    assert (eda.diff_stats(nuevo).archivos, eda.diff_stats(nuevo).anadidas) == (1, 1)
    # una linea quitada que empieza por «-- » seguida de una anadida que empieza por «++ » no es cabecera
    trampa = "--- a/t.py\n+++ b/t.py\n@@ -1,2 +1,2 @@\n contexto\n--- era un separador\n+++ ahora otro"
    s = eda.diff_stats(trampa)
    assert (s.archivos, s.anadidas, s.quitadas) == (1, 1, 1)
    # texto fuera de los bloques no cuenta
    assert eda.diff_stats("+ suelta\n- suelta\n").cambiadas == 0


def test_unidades_declaradas_y_medidas_distintas() -> None:
    r = eda.summarize(TAREAS)
    assert set(r["unidades"]) >= {
        "enunciado_caracteres",
        "parche_lineas",
        "parche_lineas_totales",
        "parche_archivos",
    }
    # lineas totales del diff = cambiadas + 3 cabeceras + 1 de contexto: es otra variable
    assert r["global"]["parche_lineas_totales"]["min"] == r["global"]["parche_lineas"]["min"] + 4
    assert r["global"]["parche_archivos"] == {"min": 1, "p25": 1.0, "mediana": 1.0, "p75": 1.0, "max": 1}
    assert r["parches_de_un_solo_archivo"] == 6
    assert (
        eda.measures({"problem_statement": "añó", "patch": "", "test_patch": ""})["enunciado_caracteres"] == 3
    )


def test_cortes_y_tercil() -> None:
    assert eda.tercile_cuts([5, 1, 3, 2, 4, 6]) == [2, 4]  # rangos ceil(6/3) = 2 y ceil(12/3) = 4
    assert eda.tercile_cuts([1, 2, 3, 4, 5, 6, 7]) == [3, 5]  # rangos 3 y 5
    assert eda.tercile_cuts([4]) == [4, 4]
    assert [eda.tercile_of(v, [2, 4]) for v in (1, 2, 3, 4, 5)] == [1, 1, 2, 2, 3]
    with pytest.raises(eda.EdaError):
        eda.tercile_cuts([])


def test_resumen_a_mano() -> None:
    r = eda.summarize(TAREAS)
    assert r["tareas"] == 6 and r["hints_text_vacio"] == 5 and r["con_lista_de_pruebas"] == 0
    assert r["base_commit_distintos"] == 5  # t1 y t6 comparten commit
    assert "patch" in r["campos"] and len(r["campos"]) == 8
    assert r["por_repositorio"]["o/a"] == {
        "tareas": 3,
        "mediana_enunciado_caracteres": 20,
        "mediana_parche_lineas": 2,
        "mediana_parche_pruebas_lineas": 6,
        "p25_enunciado_caracteres": 15.0,
        "max_parche_lineas": 3,
    }
    assert r["por_repositorio"]["o/b"]["max_parche_lineas"] == 100
    assert r["global"]["parche_lineas"] == {"min": 1, "p25": 2.25, "mediana": 6.5, "p75": 10.75, "max": 100}
    assert r["parches_de_hasta_10_lineas"] == 4  # el de 10 lineas cuenta; el de 11, no
    assert r["por_trimestre"] == {"2024-T1": 1, "2025-T3": 1, "2025-T4": 2, "2026-T1": 1, "2026-T2": 1}
    assert r["desde_2025_T4"] == 4
    assert r["terciles"] == {"parche_lineas": [2, 10], "enunciado_caracteres": [20, 40]}


def test_resumen_no_expone_contenido_ni_identificadores() -> None:
    texto = json.dumps(eda.summarize(TAREAS))
    assert "xxxx" not in texto and "linea 0" not in texto and "x.py" not in texto
    assert not any(f'"t{i}"' in texto for i in range(1, 7))


def test_lista_de_pruebas_detectada() -> None:
    con = [*TAREAS[:5], {**TAREAS[5], "FAIL_TO_PASS": ["a"]}]
    assert eda.summarize(con)["con_lista_de_pruebas"] == 1


@pytest.mark.parametrize(
    "contenido",
    [
        "",
        "no es json\n",
        "[1]\n",
        json.dumps({"instance_id": "a"}) + "\n",
        (json.dumps(TAREAS[0]) + "\n") * 2,
    ],
)
def test_tareas_invalidas(tmp_path: Path, contenido: str, capsys: pytest.CaptureFixture[str]) -> None:
    p = tmp_path / "t.jsonl"
    p.write_text(contenido, encoding="utf-8")
    with pytest.raises(eda.EdaError):
        eda.load_tasks(p)
    assert eda.main(["resumen", "--tasks", str(p)]) == 2
    assert eda.main(["resumen", "--tasks", str(tmp_path / "no_existe.jsonl")]) == 2
    assert "ERROR" in capsys.readouterr().err


def recibo(iid: str, rep: int, resuelta: bool) -> dict[str, Any]:
    return {
        "schema_version": kr.SCHEMA_VERSION,
        "instance_id": iid,
        "repo": "o/a",
        "condition": "A",
        "replica": rep,
        "status": "resolved" if resuelta else "unresolved",
        "failure_reason": None if resuelta else "tests_failed",
        "infra_reason": None,
        "resolved": resuelta,
        "tool_calls": 1,
        "duration_seconds": 1.0,
        "patch_sha256": "a" * 64,
        "submission_sha256": "b" * 64,
        "tasks_sha256": "c" * 64,
        "subset_sha256": "d" * 64,
        "harness_version": "h",
        "sandbox_image": "i",
        "converted_utc": "2026-10-03T00:00:00Z",
        "run_utc": "2026-10-02T00:00:00Z",
        "harness_raw": {
            "resolved": resuelta,
            "error": None,
            "test_exit_code": 0 if resuelta else 1,
            "agent_patch_size": 5,
            "total_llm_calls": 1,
        },
    }


def test_tasa_por_tercil(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    tasks = escribir(tmp_path, TAREAS)
    recibos = tmp_path / "recibos"
    recibos.mkdir()
    # replica 1: resuelve t1, t2 y t4; replica 2: resuelve t6
    for rep, resueltas in ((1, {"t1", "t2", "t4"}), (2, {"t6"})):
        lineas = [json.dumps(recibo(f"t{i}", rep, f"t{i}" in resueltas)) for i in range(1, 7)]
        (recibos / f"replica_{rep}.jsonl").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    parametros = tmp_path / "p.json"
    cortes = {"parche_lineas": [2, 10], "enunciado_caracteres": [20, 40]}
    parametros.write_text(json.dumps({"fijos": {"terciles": cortes}}), encoding="utf-8")
    argv = ["terciles", "--tasks", str(tasks), "--recibos", str(recibos), "--parametros", str(parametros)]
    assert eda.main(argv) == 0
    out = json.loads(capsys.readouterr().out)
    # parche: tercil 1 = t1, t2 (<= 2); tercil 2 = t3, t4 (<= 10); tercil 3 = t5, t6
    assert out["parche_lineas"]["por_replica"] == {
        "1": {
            "1": {"resueltas": 2, "tareas": 2},
            "2": {"resueltas": 1, "tareas": 2},
            "3": {"resueltas": 0, "tareas": 2},
        },
        "2": {
            "1": {"resueltas": 0, "tareas": 2},
            "2": {"resueltas": 0, "tareas": 2},
            "3": {"resueltas": 1, "tareas": 2},
        },
    }
    assert out["enunciado_caracteres"]["cortes"] == [20, 40]
    assert out["enunciado_caracteres"]["por_replica"]["2"]["3"] == {"resueltas": 1, "tareas": 2}
    assert "t1" not in json.dumps(out)
    # cortes ausentes o invalidos, y recibos de tareas que no estan en tasks.jsonl
    parametros.write_text(json.dumps({"fijos": {}}), encoding="utf-8")
    assert eda.main(argv) == 2
    parametros.write_text(json.dumps({"fijos": {"terciles": {"parche_lineas": [10, 2]}}}), encoding="utf-8")
    assert eda.main(argv) == 2
    parametros.write_text(json.dumps({"fijos": {"terciles": cortes}}), encoding="utf-8")
    (recibos / "replica_3.jsonl").write_text(json.dumps(recibo("ajena", 3, True)) + "\n", encoding="utf-8")
    assert eda.main(argv) == 2
    assert "no estan en tasks.jsonl" in capsys.readouterr().err


def test_cortes_versionados_son_los_del_pre_registro() -> None:
    from scripts import kaggle_prereg

    fijos = kaggle_prereg.load_params(kaggle_prereg.DEFAULT_PARAMS)["fijos"]
    assert fijos["terciles"] == {"parche_lineas": [5, 26], "enunciado_caracteres": [237, 739]}


def test_error_inesperado_sale_con_3(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def falla(_: Path) -> list[dict[str, Any]]:
        raise RuntimeError("defecto inyectado")

    monkeypatch.setattr(eda, "load_tasks", falla)
    assert eda.main(["resumen", "--tasks", str(tmp_path)]) == 3
