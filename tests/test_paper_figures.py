"""Pruebas unitarias y de integridad para la generación de figuras del paper (Issue #109).

Verifica:
1. Reproducibilidad determinista byte a byte (mismo hash SHA-256 en dos corridas independientes).
2. Coincidencia numérica estricta entre las figuras/tablas generadas y los agregados de origen en results/
   y los informes pre-registrados en docs/results/ (H4 primario en 18 pares y auditoría en 36 runs).
3. Cobertura explícita de todas las figuras (1 a 7) y tablas (1 a 5).
4. Pruebas de mutación con copias temporales modificadas de cada agregado usado para demostrar que
   ninguna cifra está hard-codeada y que cualquier cambio en los datos altera la salida generada.
5. Presencia de pies de página obligatorios con procedencia, comando y caracterización del agente (sin LLM).
6. Rotulado explícito de esquemas metodológicos para no confundirlos con resultados empíricos.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.paper_figures import (
    generate_all,
    generate_fig1_h4_first_attempt,
    generate_fig2_lesson_attribution,
    generate_fig3_attempts_distribution,
    generate_fig4_h7_failure_transfer,
    generate_fig5_diagnostic_baseline,
    generate_fig6_experimental_design_schema,
    generate_fig7_memory_cycle_schema,
    generate_table1_h4_markdown,
    generate_table2_misleading_markdown,
    generate_table3_attempts_markdown,
    generate_table4_h7_markdown,
    generate_table5_diagnostic_markdown,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = REPO_ROOT / "results"
DOCS_RESULTS_DIR = REPO_ROOT / "docs" / "results"


def compute_file_sha256(path: Path) -> str:
    """Calcula el hash SHA-256 exacto de un archivo."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_clean_results(target_dir: Path) -> None:
    """Copia los 5 archivos agregados fuente a un directorio temporal para pruebas de mutación."""
    dirs = [
        target_dir / "reference-v2",
        target_dir / "failure-transfer-v1",
        target_dir / "diagnostic-baseline-v1",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

    files_to_copy = [
        ("reference-v2", "experiment1.json"),
        ("reference-v2", "family_breakdown.json"),
        ("reference-v2", "task_breakdown.json"),
        ("failure-transfer-v1", "failure_transfer_analysis.json"),
        ("diagnostic-baseline-v1", "diagnostic_analysis.json"),
    ]
    for subdir, fname in files_to_copy:
        src = RESULTS_DIR / subdir / fname
        dst = target_dir / subdir / fname
        dst.write_bytes(src.read_bytes())


def test_paper_figures_determinism(tmp_path: Path) -> None:
    """Verifica que dos ejecuciones independientes generen archivos idénticos (mismo hash SHA-256)."""
    out1 = tmp_path / "run1"
    figs1 = out1 / "figures"
    tabs1 = out1 / "tables"

    out2 = tmp_path / "run2"
    figs2 = out2 / "figures"
    tabs2 = out2 / "tables"

    artifacts1 = generate_all(RESULTS_DIR, figs1, tabs1)
    artifacts2 = generate_all(RESULTS_DIR, figs2, tabs2)

    assert set(artifacts1.keys()) == set(artifacts2.keys())

    for key, path1 in artifacts1.items():
        path2 = artifacts2[key]
        assert path1.exists(), f"No se generó {path1}"
        assert path2.exists(), f"No se generó {path2}"

        hash1 = compute_file_sha256(path1)
        hash2 = compute_file_sha256(path2)
        assert hash1 == hash2, f"Discrepancia no determinista en {key}: {hash1} != {hash2}"


def test_fig1_and_table1_match_h4_sources(tmp_path: Path) -> None:
    """Verifica que Fig 1 y Tabla 1 coincidan tanto con el informe H4 (18 pares)
    como con family_breakdown (36 runs)."""
    fig_file = tmp_path / "fig1.svg"
    tab_file = tmp_path / "table1.md"

    counts = generate_fig1_h4_first_attempt(RESULTS_DIR, fig_file)
    generate_table1_h4_markdown(counts, tab_file)

    pri = counts["primary"]
    agg = counts["aggregate"]

    # 1. Cotejar conteos primarios con docs/results/h4-associative-vs-history.md
    # En engañosas: A: 6/18, B: 0/18, C: 0/18
    assert pri["misleading"]["NO_MEMORY"]["success"] == 6
    assert pri["misleading"]["NO_MEMORY"]["runs"] == 18
    assert pri["misleading"]["TEXT_HISTORY"]["success"] == 0
    assert pri["misleading"]["TEXT_HISTORY"]["runs"] == 18
    assert pri["misleading"]["ASSOCIATIVE_MEMORY"]["success"] == 0
    assert pri["misleading"]["ASSOCIATIVE_MEMORY"]["runs"] == 18

    # En originales: A: 6/18, B: 18/18, C: 18/18
    assert pri["original"]["NO_MEMORY"]["success"] == 6
    assert pri["original"]["NO_MEMORY"]["runs"] == 18
    assert pri["original"]["TEXT_HISTORY"]["success"] == 18
    assert pri["original"]["TEXT_HISTORY"]["runs"] == 18
    assert pri["original"]["ASSOCIATIVE_MEMORY"]["success"] == 18
    assert pri["original"]["ASSOCIATIVE_MEMORY"]["runs"] == 18

    # 2. Cotejar conteos consolidados con results/reference-v2/family_breakdown.json
    ref_file = RESULTS_DIR / "reference-v2" / "family_breakdown.json"
    ref_data = json.loads(ref_file.read_text(encoding="utf-8"))
    orig_ref = ref_data["kinds"]["original"]
    misl_ref = ref_data["kinds"]["misleading"]

    for cond in ("NO_MEMORY", "TEXT_HISTORY", "ASSOCIATIVE_MEMORY"):
        expected_orig_succ = sum(orig_ref[f][cond]["first_attempt_successes"] for f in orig_ref)
        expected_orig_runs = sum(orig_ref[f][cond]["runs"] for f in orig_ref)
        assert agg["original"][cond]["success"] == expected_orig_succ
        assert agg["original"][cond]["runs"] == expected_orig_runs

        expected_misl_succ = sum(misl_ref[f][cond]["first_attempt_successes"] for f in misl_ref)
        expected_misl_runs = sum(misl_ref[f][cond]["runs"] for f in misl_ref)
        assert agg["misleading"][cond]["success"] == expected_misl_succ
        assert agg["misleading"][cond]["runs"] == expected_misl_runs

    # 3. Comprobar que el texto de la figura y tabla contienen las cadenas de conteos
    fig_text = fig_file.read_text(encoding="utf-8")
    tab_text = tab_file.read_text(encoding="utf-8")

    assert "6/18" in fig_text
    assert "18/18" in fig_text
    assert "0/18" in fig_text
    assert "[2 rep: 12/36]" in fig_text
    assert "[2 rep: 36/36]" in fig_text

    assert "6/18" in tab_text
    assert "18/18" in tab_text
    assert "0/18" in tab_text
    assert "12/36" in tab_text


def test_fig2_and_table2_match_task_breakdown(tmp_path: Path) -> None:
    """Verifica que Fig 2 y Tabla 2 reflejen las citas del señuelo en EXP-07..09 desde task_breakdown.json."""
    fig_file = tmp_path / "fig2.svg"
    tab_file = tmp_path / "table2.md"

    attr = generate_fig2_lesson_attribution(RESULTS_DIR, fig_file)
    generate_table2_misleading_markdown(attr, tab_file)

    tb_file = RESULTS_DIR / "reference-v2" / "task_breakdown.json"
    tb_data = json.loads(tb_file.read_text(encoding="utf-8"))

    for tid, decoy_task in (("EXP-07", "EXP-03"), ("EXP-08", "EXP-01"), ("EXP-09", "EXP-02")):
        assert (
            attr[tid]["info"]["decoy_task"] == decoy_task
            if "info" in attr[tid]
            else attr[tid]["decoy_task_b"] == decoy_task
        )

        # Comprobar citas en task_breakdown.json
        c_b = tb_data["tasks"][tid]["TEXT_HISTORY"]["cited_lessons_by_source_task"]
        c_c = tb_data["tasks"][tid]["ASSOCIATIVE_MEMORY"]["cited_lessons_by_source_task"]
        assert c_b.get(decoy_task, 0) > 0
        assert c_c.get(decoy_task, 0) > 0


def test_fig3_and_table3_match_experiment1(tmp_path: Path) -> None:
    """Verifica que Fig 3 y Tabla 3 coincidan exactamente con reference-v2/experiment1.json:comparisons."""
    fig_file = tmp_path / "fig3.svg"
    tab_file = tmp_path / "table3.md"

    attempts_data = generate_fig3_attempts_distribution(RESULTS_DIR, fig_file)
    generate_table3_attempts_markdown(attempts_data, tab_file)

    # 1. Validar estructura y conteos
    for label, counts in attempts_data.items():
        assert counts["total"] == 36, f"Total de runs en {label} debe ser 36, obtenido {counts['total']}"
        sum_attempts = counts["1"] + counts["2"] + counts["3"]
        assert sum_attempts == counts["total"], (
            f"Suma de intentos ({sum_attempts}) != total ({counts['total']}) en {label}"
        )

    # 2. Verificar datos observados de H4 en experiment1:
    orig_nomem = attempts_data["Originales · Sin memoria"]
    assert orig_nomem["1"] == 12
    assert orig_nomem["total"] == 36

    orig_assoc = attempts_data["Originales · Asociativa"]
    assert orig_assoc["1"] == 36
    assert orig_assoc["2"] == 0
    assert orig_assoc["3"] == 0

    misl_assoc = attempts_data["Señuelos · Asociativa"]
    assert misl_assoc["1"] == 0
    assert misl_assoc["total"] == 36

    # 3. Comprobar que el archivo SVG y la tabla Markdown contienen las cadenas esperadas
    fig_text = fig_file.read_text(encoding="utf-8")
    tab_text = tab_file.read_text(encoding="utf-8")

    assert "Originales · Sin memoria" in fig_text
    assert "Originales · Asociativa" in fig_text
    assert "Señuelos · Asociativa" in fig_text
    assert "36/36" in tab_text
    assert "12/36" in tab_text


def test_fig4_and_table4_match_failure_transfer(tmp_path: Path) -> None:
    """Verifica que Fig 4 y Tabla 4 coincidan con failure_transfer_analysis.json."""
    fig_file = tmp_path / "fig4.svg"
    tab_file = tmp_path / "table4.md"

    h7 = generate_fig4_h7_failure_transfer(RESULTS_DIR, fig_file)
    generate_table4_h7_markdown(h7, tab_file)

    h7_file = RESULTS_DIR / "failure-transfer-v1" / "failure_transfer_analysis.json"
    h7_data = json.loads(h7_file.read_text(encoding="utf-8"))
    cells = h7_data["cells"]

    # Comprobar celdas clave de H7
    # Base A tau=0.25 real helped=3, hurt=0
    assert cells["A"]["0.25"]["real"]["original"]["helped"]["numerator"] == 3
    assert cells["A"]["0.25"]["real"]["original"]["hurt"]["numerator"] == 0

    # Base A tau=0.10 real helped=3, hurt=3
    assert cells["A"]["0.1"]["real"]["original"]["helped"]["numerator"] == 3
    assert cells["A"]["0.1"]["real"]["original"]["hurt"]["numerator"] == 3

    # Base C tau=0.10 real helped=0, hurt=3
    assert cells["C"]["0.1"]["real"]["original"]["helped"]["numerator"] == 0
    assert cells["C"]["0.1"]["real"]["original"]["hurt"]["numerator"] == 3

    # Verificaciones de ausencia de texto de conclusión fija y presencia de denominadores
    tab_text = tab_file.read_text(encoding="utf-8")
    assert "nunca ayudó" not in tab_text
    assert "causó contaminación" not in tab_text
    assert "Veredicto" not in tab_text
    assert "+3/18" in tab_text
    assert "-3/18" in tab_text
    assert "failure-transfer-v1" in tab_text


def test_fig5_and_table5_match_diagnostic_baseline(tmp_path: Path) -> None:
    """Verifica que Fig 5 y Tabla 5 coincidan con diagnostic_analysis.json."""
    fig_file = tmp_path / "fig5.svg"
    tab_file = tmp_path / "table5.md"

    diag = generate_fig5_diagnostic_baseline(RESULTS_DIR, fig_file)
    generate_table5_diagnostic_markdown(diag, tab_file)

    diag_file = RESULTS_DIR / "diagnostic-baseline-v1" / "diagnostic_analysis.json"
    diag_data = json.loads(diag_file.read_text(encoding="utf-8"))
    orig = diag_data["kinds"]["original"]["conditions"]
    misl = diag_data["kinds"]["misleading"]["conditions"]

    assert diag["original"]["A"] == orig["NO_MEMORY"]["FirstAttemptSuccess"]["numerator"]
    assert diag["original"]["B"] == orig["TEXT_HISTORY"]["FirstAttemptSuccess"]["numerator"]
    assert diag["original"]["C"] == orig["ASSOCIATIVE_MEMORY"]["FirstAttemptSuccess"]["numerator"]
    assert diag["original"]["total"] == 18

    assert diag["misleading"]["A"] == misl["NO_MEMORY"]["FirstAttemptSuccess"]["numerator"]
    assert diag["misleading"]["B"] == misl["TEXT_HISTORY"]["FirstAttemptSuccess"]["numerator"]
    assert diag["misleading"]["C"] == misl["ASSOCIATIVE_MEMORY"]["FirstAttemptSuccess"]["numerator"]
    assert diag["misleading"]["total"] == 18

    # Verificaciones de ausencia de veredictos interpretativos y presencia de delta con denominador
    tab_text = tab_file.read_text(encoding="utf-8")
    fig_text = fig_file.read_text(encoding="utf-8")
    assert "Veredicto" not in tab_text
    assert "Aporta" not in tab_text
    assert "Sin diferencia" not in tab_text
    assert "aporta" not in fig_text.lower()
    assert "sin diferencia" not in fig_text.lower()
    assert "perjudica" not in fig_text.lower()
    assert "+6/18" in tab_text
    assert "-2/18" in tab_text
    assert "Δ aciertos B − A" in tab_text


def test_mandatory_footnotes_and_labels(tmp_path: Path) -> None:
    """Verifica que todas las figuras incluyan pie de procedencia, comando y advertencia de esquemas."""
    f1 = tmp_path / "f1.svg"
    f2 = tmp_path / "f2.svg"
    f3 = tmp_path / "f3.svg"
    f4 = tmp_path / "f4.svg"
    f5 = tmp_path / "f5.svg"
    f6 = tmp_path / "f6.svg"
    f7 = tmp_path / "f7.svg"

    generate_fig1_h4_first_attempt(RESULTS_DIR, f1)
    generate_fig2_lesson_attribution(RESULTS_DIR, f2)
    generate_fig3_attempts_distribution(RESULTS_DIR, f3)
    generate_fig4_h7_failure_transfer(RESULTS_DIR, f4)
    generate_fig5_diagnostic_baseline(RESULTS_DIR, f5)
    generate_fig6_experimental_design_schema(f6)
    generate_fig7_memory_cycle_schema(f7)

    # Cada figura debe mencionar el comando de regeneración
    for f in (f1, f2, f3, f4, f5, f6, f7):
        content = f.read_text(encoding="utf-8")
        assert "python -m scripts.paper_figures" in content, f"Falta comando en {f.name}"

    # Figuras de resultados deben mencionar solver determinista sin LLM
    for f in (f1, f2, f3, f4, f5):
        content = f.read_text(encoding="utf-8")
        assert "solver determinista de 3 operadores, sin llm" in content.lower(), (
            f"Falta mención solver en {f.name}"
        )

    # Figuras 6 y 7 deben estar rotuladas explícitamente como esquemas metodológicos
    for f in (f6, f7):
        content = f.read_text(encoding="utf-8")
        assert "ESQUEMA METODOLÓGICO (NO ES RESULTADO EXPERIMENTAL)" in content, (
            f"Falta rótulo de esquema en {f.name}"
        )


def test_mutation_family_breakdown_changes_fig1_and_table1(tmp_path: Path) -> None:
    """Demuestra que alterar family_breakdown.json cambia inmediatamente Fig 1 y Tabla 1 (no hardcoding)."""
    mock_results = tmp_path / "mock_res1"
    copy_clean_results(mock_results)

    fb_path = mock_results / "reference-v2" / "family_breakdown.json"
    fb_data = json.loads(fb_path.read_text(encoding="utf-8"))

    # Mutación: aumentamos en 2 éxitos y 2 runs en la primera familia para mantener divisibilidad par
    fam_name = next(iter(fb_data["kinds"]["original"].keys()))
    orig_nomem = fb_data["kinds"]["original"][fam_name]["NO_MEMORY"]
    orig_nomem["first_attempt_successes"] += 2
    orig_nomem["runs"] += 2
    fb_path.write_text(json.dumps(fb_data), encoding="utf-8")

    out_svg = tmp_path / "mutated_fig1.svg"
    out_md = tmp_path / "mutated_table1.md"

    counts = generate_fig1_h4_first_attempt(mock_results, out_svg)
    generate_table1_h4_markdown(counts, out_md)

    # El conteo primario en NO_MEMORY original debe haber cambiado de 6/18 a 7/19
    assert counts["primary"]["original"]["NO_MEMORY"]["success"] == 7
    assert counts["primary"]["original"]["NO_MEMORY"]["runs"] == 19
    assert "7/19" in out_svg.read_text(encoding="utf-8")
    assert "7/19" in out_md.read_text(encoding="utf-8")


def test_mutation_task_breakdown_changes_fig2_and_table2(tmp_path: Path) -> None:
    """Demuestra que alterar task_breakdown.json cambia inmediatamente Fig 2 y Tabla 2 (no hardcoding)."""
    mock_results = tmp_path / "mock_res2"
    copy_clean_results(mock_results)

    tb_path = mock_results / "reference-v2" / "task_breakdown.json"
    tb_data = json.loads(tb_path.read_text(encoding="utf-8"))

    # Mutación: cambiamos el conteo de citas en EXP-07 para TEXT_HISTORY
    tb_data["tasks"]["EXP-07"]["TEXT_HISTORY"]["cited_lessons_by_source_task"]["EXP-03"] = 42
    tb_data["tasks"]["EXP-07"]["TEXT_HISTORY"]["runs"] = 42
    tb_path.write_text(json.dumps(tb_data), encoding="utf-8")

    out_svg = tmp_path / "mutated_fig2.svg"
    out_md = tmp_path / "mutated_table2.md"

    attr = generate_fig2_lesson_attribution(mock_results, out_svg)
    generate_table2_misleading_markdown(attr, out_md)

    assert attr["EXP-07"]["decoy_count_b"] == 42
    assert "42/42 señuelo" in out_svg.read_text(encoding="utf-8")
    assert "42/42 (EXP-03)" in out_md.read_text(encoding="utf-8")


def test_mutation_experiment1_changes_fig3_and_table3(tmp_path: Path) -> None:
    """Demuestra que alterar experiment1.json comparisons cambia Fig 3 y Tabla 3 (no hardcoding)."""
    mock_results = tmp_path / "mock_res3"
    copy_clean_results(mock_results)

    exp_path = mock_results / "reference-v2" / "experiment1.json"
    exp_data = json.loads(exp_path.read_text(encoding="utf-8"))

    # Mutación: en el primer comparison de TEXT_HISTORY original, cambiamos iterations de 1 a 3
    for comp in exp_data["comparisons"]:
        if comp["task"] == "EXP-04" and comp["mode"] == "TEXT_HISTORY":
            comp["treatment_observations"]["iterations"] = 3
            break
    exp_path.write_text(json.dumps(exp_data), encoding="utf-8")

    out_svg = tmp_path / "mutated_fig3.svg"
    out_md = tmp_path / "mutated_table3.md"

    attempts = generate_fig3_attempts_distribution(mock_results, out_svg)
    generate_table3_attempts_markdown(attempts, out_md)

    orig_hist = attempts["Originales · Historial"]
    # Al mutar una iteración a 3, las resueltas en 3 deben ser >= 1
    assert orig_hist["3"] >= 1
    assert f"{orig_hist['3']}/36" in out_md.read_text(encoding="utf-8")


def test_mutation_failure_transfer_changes_fig4_and_table4(tmp_path: Path) -> None:
    """Demuestra que alterar failure_transfer_analysis.json cambia Fig 4 y Tabla 4 (no hardcoding)."""
    mock_results = tmp_path / "mock_res4"
    copy_clean_results(mock_results)

    h7_path = mock_results / "failure-transfer-v1" / "failure_transfer_analysis.json"
    h7_data = json.loads(h7_path.read_text(encoding="utf-8"))

    # Mutación: cambiamos helped de base A tau=0.25 de 3 a 11
    h7_data["cells"]["A"]["0.25"]["real"]["original"]["helped"]["numerator"] = 11
    h7_path.write_text(json.dumps(h7_data), encoding="utf-8")

    out_svg = tmp_path / "mutated_fig4.svg"
    out_md = tmp_path / "mutated_table4.md"

    h7 = generate_fig4_h7_failure_transfer(mock_results, out_svg)
    generate_table4_h7_markdown(h7, out_md)

    assert h7["summary"][0]["helped"] == 11
    assert "+11/18 ayuda" in out_svg.read_text(encoding="utf-8")
    assert "+11/18" in out_md.read_text(encoding="utf-8")


def test_mutation_diagnostic_analysis_changes_fig5_and_table5(tmp_path: Path) -> None:
    """Demuestra que alterar diagnostic_analysis.json cambia Fig 5 y Tabla 5 (no hardcoding)."""
    mock_results = tmp_path / "mock_res5"
    copy_clean_results(mock_results)

    diag_path = mock_results / "diagnostic-baseline-v1" / "diagnostic_analysis.json"
    diag_data = json.loads(diag_path.read_text(encoding="utf-8"))

    # Mutación: cambiamos aciertos en NO_MEMORY original de 6 a 14
    diag_data["kinds"]["original"]["conditions"]["NO_MEMORY"]["FirstAttemptSuccess"]["numerator"] = 14
    diag_path.write_text(json.dumps(diag_data), encoding="utf-8")

    out_svg = tmp_path / "mutated_fig5.svg"
    out_md = tmp_path / "mutated_table5.md"

    diag = generate_fig5_diagnostic_baseline(mock_results, out_svg)
    generate_table5_diagnostic_markdown(diag, out_md)

    assert diag["original"]["A"] == 14
    assert "14/18" in out_svg.read_text(encoding="utf-8")
    assert "14/18" in out_md.read_text(encoding="utf-8")
    # Y la diferencia B - A cambia en consecuencia (12 - 14 = -2 en lugar de +6) con denominador
    assert "-2/18" in out_md.read_text(encoding="utf-8")


def test_all_paper_figures_and_tables_generated(tmp_path: Path) -> None:
    """Verifica que generate_all genere todas las 7 figuras y 5 tablas del issue con formato válido."""
    figs_dir = tmp_path / "figures"
    tabs_dir = tmp_path / "tables"
    expected_figs = [
        "fig1_first_attempt_h4.svg",
        "fig2_lesson_attribution_map.svg",
        "fig3_attempts_distribution.svg",
        "fig4_h7_failure_transfer.svg",
        "fig5_diagnostic_baseline_diff.svg",
        "fig6_experimental_design.svg",
        "fig7_memory_cycle.svg",
    ]
    expected_tabs = [
        "table1_h4_first_attempt.md",
        "table2_misleading_attribution.md",
        "table3_attempts_distribution.md",
        "table4_h7_tau_pairs.md",
        "table5_diagnostic_family_breakdown.md",
    ]
    artifacts = generate_all(RESULTS_DIR, figs_dir, tabs_dir)
    assert len(artifacts) == 12
    assert len(artifacts) == len(expected_figs) + len(expected_tabs)

    for fname in expected_figs:
        p = figs_dir / fname
        assert p.exists(), f"Falta figura: {fname}"
        content = p.read_text(encoding="utf-8")
        assert content.startswith("<svg"), f"{fname} no es un SVG válido"
        assert content.rstrip().endswith("</svg>"), f"{fname} no cierra el tag </svg>"
        assert len(content) > 500, f"{fname} parece truncado ({len(content)} bytes)"

    for fname in expected_tabs:
        p = tabs_dir / fname
        assert p.exists(), f"Falta tabla: {fname}"
        content = p.read_text(encoding="utf-8")
        assert content.startswith("# Tabla"), f"{fname} debe iniciar con encabezado Markdown # Tabla"
        assert "|---|" in content, f"{fname} debe contener separador de tabla Markdown"
        assert len(content) > 200, f"{fname} parece truncada ({len(content)} bytes)"
