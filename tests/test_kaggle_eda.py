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
        "base_commit": f"{i % 7:040d}",
        "problem_statement": "x" * enunciado,
        "hints_text": "",
        "patch": diff(parche),
        "test_patch": diff(pruebas),
        "created_at": fecha,
        **extra,
    }


# o/a: 5 tareas (el minimo para dar estadisticos); o/b: 4 (se suprime); en total 9
TAREAS = [
    tarea(1, "o/a", 10, 1, 4, "2025-09-30T00:00:00Z"),
    tarea(2, "o/a", 20, 2, 6, "2025-10-01T00:00:00Z"),
    tarea(3, "o/a", 30, 3, 8, "2025-12-31T00:00:00Z"),
    tarea(4, "o/a", 40, 10, 2, "2026-01-01T00:00:00Z"),
    tarea(5, "o/a", 50, 11, 2, "2026-04-01T00:00:00Z"),
    tarea(6, "o/b", 60, 100, 2, "2024-02-01T00:00:00Z", hints_text="una pista"),
    tarea(7, "o/b", 70, 101, 2, "2024-02-02T00:00:00Z"),
    tarea(8, "o/b", 5001, 1001, 2, "2024-02-03T00:00:00Z"),
    tarea(9, "o/b", 100, 7, 2, "2024-05-03T00:00:00Z"),
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
    # una linea quitada que empieza por «-- » seguida de una anadida que empieza por «++ » no es cabecera
    trampa = "--- a/t.py\n+++ b/t.py\n@@ -1,2 +1,2 @@\n contexto\n--- era un separador\n+++ ahora otro"
    s = eda.diff_stats(trampa)
    assert (s.archivos, s.anadidas, s.quitadas) == (1, 1, 1)
    # texto fuera de los bloques no cuenta
    assert eda.diff_stats("+ suelta\n- suelta\n").cambiadas == 0


def test_una_cabecera_de_archivo_necesita_las_dos_lineas() -> None:
    """``---`` sin ``+++`` detras no es un archivo, y ``+++`` suelta tampoco."""
    assert eda.diff_stats("--- a/x.py\ncualquier cosa\n+++ b/x.py\n").archivos == 0
    assert eda.diff_stats("+++ b/x.py\n--- a/x.py\n").archivos == 0
    assert eda.diff_stats("--- a/x.py\n+++ b/x.py\n").archivos == 1
    assert eda.diff_stats("--- a/x.py").archivos == 0  # ultima linea, sin pareja


def test_bloque_sin_longitud_vale_una_linea() -> None:
    """``@@ -3 +3 @@`` declara una linea vieja y una nueva: tras ellas el bloque se acaba."""
    texto = "--- a/x.py\n+++ b/x.py\n@@ -3 +3 @@\n-vieja\n+nueva\n+fuera del bloque\n-fuera del bloque"
    s = eda.diff_stats(texto)
    assert (s.anadidas, s.quitadas) == (1, 1)
    # solo el lado nuevo sin longitud: 0 viejas y 1 nueva
    s = eda.diff_stats("--- /dev/null\n+++ b/n.py\n@@ -0,0 +1 @@\n+unica\n+fuera")
    assert (s.archivos, s.anadidas, s.quitadas) == (1, 1, 0)
    # solo el lado viejo sin longitud: 1 vieja y 0 nuevas
    s = eda.diff_stats("--- a/n.py\n+++ /dev/null\n@@ -1 +0,0 @@\n-unica\n-fuera")
    assert (s.anadidas, s.quitadas) == (0, 1)


def test_marca_de_fin_sin_salto_de_linea_no_consume_el_bloque() -> None:
    """``\\ No newline at end of file`` en medio de un bloque no cuenta como contexto."""
    marca = "\\ No newline at end of file"
    cabecera = ["--- a/x.py", "+++ b/x.py", "@@ -1,2 +1,2 @@"]
    texto = "\n".join([*cabecera, " contexto", "-vieja", marca, "+nueva", marca, "+fuera del bloque"])
    s = eda.diff_stats(texto)
    assert (s.anadidas, s.quitadas) == (1, 1)


def test_cortes_y_tercil() -> None:
    assert eda.tercile_cuts([5, 1, 3, 2, 4, 6]) == [2, 4]  # rangos ceil(6/3) = 2 y ceil(12/3) = 4
    assert eda.tercile_cuts([1, 2, 3, 4, 5, 6, 7]) == [3, 5]  # rangos 3 y 5
    assert [eda.tercile_of(v, [2, 4]) for v in (1, 2, 3, 4, 5)] == [1, 1, 2, 2, 3]
    with pytest.raises(eda.EdaError):
        eda.tercile_cuts([1, 2, 3, 4])  # menos de 5 valores: no se publican cortes


def test_cuantiles_y_supresion_de_grupos_pequenos() -> None:
    assert eda.MIN_GRUPO == 5
    assert eda.quantiles([1, 2, 3, 4]) is None
    # 5 valores, metodo inclusivo: p10 = 1,4; p25 = 2; mediana = 3; p75 = 4; p90 = 4,6
    q = eda.quantiles([5, 1, 3, 2, 4])
    assert q is not None and {k: round(v, 6) for k, v in q.items()} == {
        "p10": 1.4,
        "p25": 2.0,
        "mediana": 3.0,
        "p75": 4.0,
        "p90": 4.6,
    }
    assert set(q) == {"p10", "p25", "mediana", "p75", "p90"}  # ni minimo ni maximo
    assert eda.group_summary([eda.measures(t) for t in TAREAS[5:]]) == {"tareas": 4, "estadisticos": None}
    con_cinco = eda.group_summary([eda.measures(t) for t in TAREAS[:5]])
    assert con_cinco["tareas"] == 5 and con_cinco["estadisticos"]["parche_lineas"]["mediana"] == 3.0


def test_resumen_a_mano() -> None:
    r = eda.summarize(TAREAS)
    assert r["tareas"] == 9 and r["hints_text_vacio"] == 8 and r["con_lista_de_pruebas"] == 0
    assert r["base_commit_distintos"] == 7
    assert "patch" in r["campos"] and len(r["campos"]) == 8
    a = r["por_repositorio"]["o/a"]
    assert a["tareas"] == 5 and a["por_anio"] == {"2025": 3, "2026": 2}
    assert a["estadisticos"]["enunciado_caracteres"] == {
        "p10": 14.0,
        "p25": 20.0,
        "mediana": 30.0,
        "p75": 40.0,
        "p90": 46.0,
    }
    assert a["estadisticos"]["parche_archivos"]["p90"] == 1.0
    # el grupo de 4 tareas no da ningun estadistico, ni siquiera por anio
    assert r["por_repositorio"]["o/b"] == {"tareas": 4, "estadisticos": None, "por_anio": None}
    assert r["global"]["tareas"] == 9 and r["global"]["estadisticos"]["parche_lineas"]["mediana"] == 10.0
    assert r["conteos_por_umbral"] == {
        "parches_de_hasta_10_lineas": 5,  # 1, 2, 3, 10 y 7; el de 11 no
        "parches_de_mas_de_100_lineas": 2,  # 101 y 1001; el de 100 no
        "parches_de_mas_de_1000_lineas": 1,
        "parches_de_un_solo_archivo": 9,
        "parches_de_mas_de_10_archivos": 0,
        "enunciados_de_hasta_100_caracteres": 8,  # el de 100 cuenta
        "enunciados_de_mas_de_5000_caracteres": 1,
    }
    assert r["por_trimestre"] == {
        "2024-T1": 3,
        "2024-T2": 1,
        "2025-T3": 1,
        "2025-T4": 2,
        "2026-T1": 1,
        "2026-T2": 1,
    }
    assert r["desde_2025_T4"] == 4
    assert r["terciles"] == {"parche_lineas": [3, 11], "enunciado_caracteres": [30, 60]}
    assert (
        eda.summarize(TAREAS[:4])["terciles"] is None
        and eda.summarize(TAREAS[:4])["global"]["estadisticos"] is None
    )


def _numeros(obj: Any) -> list[float]:
    if isinstance(obj, dict):
        return [n for v in obj.values() for n in _numeros(v)]
    if isinstance(obj, list):
        return [n for v in obj for n in _numeros(v)]
    return [obj] if isinstance(obj, int | float) and not isinstance(obj, bool) else []


def test_resumen_no_expone_contenido_identificadores_ni_extremos() -> None:
    r = eda.summarize(TAREAS)
    texto = json.dumps(r)
    assert "xxxx" not in texto and "linea 0" not in texto and "x.py" not in texto
    assert not any(f'"t{i}"' in texto for i in range(1, 10))
    assert '"min"' not in texto and '"max"' not in texto
    # los valores extremos de una tarea concreta (el parche de 1001 lineas, el enunciado de 5001) no salen
    estadisticos = _numeros(r["global"]["estadisticos"]) + _numeros(r["por_repositorio"])
    assert 1001 not in estadisticos and 5001 not in estadisticos


def test_unidades_declaradas_y_medidas_distintas() -> None:
    r = eda.summarize(TAREAS)
    assert set(r["unidades"]) >= {*eda.MEDIDAS, "cuantiles", "supresion"}
    g = r["global"]["estadisticos"]
    # lineas totales del diff = cambiadas + 3 cabeceras + 1 de contexto: es otra variable
    assert g["parche_lineas_totales"]["mediana"] == g["parche_lineas"]["mediana"] + 4
    medidas = eda.measures({"problem_statement": "añó", "patch": "", "test_patch": ""})
    assert medidas["enunciado_caracteres"] == 3


def test_lista_de_pruebas_detectada() -> None:
    con = [*TAREAS[:8], {**TAREAS[8], "FAIL_TO_PASS": ["a"]}]
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


def test_tasa_por_tercil_con_supresion(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # 12 tareas con parches de 1 a 12 lineas y enunciados de 10 a 120 caracteres
    tareas = [tarea(i, "o/a", 10 * i, i, 2, "2026-01-01T00:00:00Z") for i in range(1, 13)]
    tasks = escribir(tmp_path, tareas)
    recibos = tmp_path / "recibos"
    recibos.mkdir()
    resueltas = {1: {"t1", "t2", "t6", "t12"}, 2: {"t7"}}
    for rep, si in resueltas.items():
        lineas = [json.dumps(recibo(f"t{i}", rep, f"t{i}" in si)) for i in range(1, 13)]
        (recibos / f"replica_{rep}.jsonl").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    parametros = tmp_path / "p.json"
    # parche: tercil 1 = t1..t5 (<= 5); tercil 2 = t6..t10 (<= 10); tercil 3 = t11, t12 (2 tareas: suprimido)
    cortes = {"parche_lineas": [5, 10], "enunciado_caracteres": [40, 80]}
    parametros.write_text(json.dumps({"fijos": {"terciles": cortes}}), encoding="utf-8")
    argv = ["terciles", "--tasks", str(tasks), "--recibos", str(recibos), "--parametros", str(parametros)]
    assert eda.main(argv) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["parche_lineas"]["por_replica"] == {
        "1": {
            "1": {"resueltas": 2, "tareas": 5},
            "2": {"resueltas": 1, "tareas": 5},
            "3": {"resueltas": None, "tareas": 2},
        },
        "2": {
            "1": {"resueltas": 0, "tareas": 5},
            "2": {"resueltas": 1, "tareas": 5},
            "3": {"resueltas": None, "tareas": 2},
        },
    }
    # enunciado: terciles de 4 tareas cada uno: todos suprimidos
    assert out["enunciado_caracteres"]["cortes"] == [40, 80]
    assert all(
        c["resueltas"] is None and c["tareas"] == 4
        for c in out["enunciado_caracteres"]["por_replica"]["1"].values()
    )
    assert "t1" not in json.dumps(out)
    # cortes ausentes o invalidos, y recibos de tareas que no estan en tasks.jsonl
    parametros.write_text(json.dumps({"fijos": {}}), encoding="utf-8")
    assert eda.main(argv) == 2
    parametros.write_text(json.dumps({"fijos": {"terciles": {"parche_lineas": [10, 2]}}}), encoding="utf-8")
    assert eda.main(argv) == 2
    parametros.write_text(json.dumps({"fijos": {"terciles": {"parche_archivos": [1, 2]}}}), encoding="utf-8")
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
