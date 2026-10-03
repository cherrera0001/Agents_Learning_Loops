#!/usr/bin/env python3
"""Generación reproducible y determinista de figuras y tablas para el artículo del Paper Track.

Consume exclusivamente los agregados ya publicados en `results/`:
- `results/reference-v2/` (H4: memoria asociativa vs. historial vs. sin memoria)
- `results/failure-transfer-v1/` (H7: transferencia y contaminación de fallos por tau)
- `results/diagnostic-baseline-v1/` (#58: línea base con diagnóstico público)

Genera figuras en formato SVG determinista (mismo hash en corridas sucesivas)
y tablas en Markdown estructurado, respetando la regla de conteos exactos (numerador/denominador),
sin p-valores ni barras de error indebidas, e incluyendo en cada pie la procedencia, el comando
de regeneración y la especificación del agente (solver determinista de 3 operadores, sin LLM).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Intentar importar matplotlib si el extra [paper] está instalado
try:
    import matplotlib  # noqa: F401
    import matplotlib.pyplot as plt  # noqa: F401

    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

FOOTNOTE_BASE = (
    "Origen: campaña {campaign} (solver determinista de 3 operadores, sin LLM). "
    "Conteos exactos de diseño exhaustivo. Regenerar: python -m scripts.paper_figures"
)

COLOR_NO_MEMORY = "#94a3b8"  # slate-400
COLOR_TEXT_HISTORY = "#38bdf8"  # sky-400
COLOR_ASSOCIATIVE = "#22c55e"  # emerald-500
COLOR_HELPED = "#10b981"  # emerald-500
COLOR_HURT = "#f43f5e"  # rose-500
COLOR_BG = "#ffffff"
COLOR_TEXT = "#0f172a"
COLOR_MUTED = "#64748b"
COLOR_BORDER = "#e2e8f0"


def escape_xml(text: str) -> str:
    """Escapa caracteres especiales para SVG/XML."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def write_utf8_lf(path: Path, text: str) -> None:
    """Write UTF-8 text with platform-independent LF line endings."""
    with path.open("w", encoding="utf-8", newline="\n") as output:
        output.write(text)


# ==============================================================================
# 1. FIGURA 1 & TABLA 1: H4 Éxito al Primer Intento
# ==============================================================================


def derive_h4_counts(results_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Deriva dinámicamente los conteos de H4 desde family_breakdown y experiment1.

    Comprueba que replication.all_semantic_projections_equal == True y que los conteos
    sean pares antes de dividirlos entre 2 para obtener la réplica equivalente (18 pares).
    """
    exp_file = results_dir / "reference-v2" / "experiment1.json"
    exp_data = json.loads(exp_file.read_text(encoding="utf-8"))

    rep = exp_data.get("replication", {})
    if not rep.get("all_semantic_projections_equal"):
        raise ValueError("Replicación inválida: all_semantic_projections_equal no es True")

    ref_file = results_dir / "reference-v2" / "family_breakdown.json"
    fam_data = json.loads(ref_file.read_text(encoding="utf-8"))

    orig = fam_data["kinds"]["original"]
    mislead = fam_data["kinds"]["misleading"]

    aggregate_counts: dict[str, dict[str, dict[str, int]]] = {
        "original": {
            "NO_MEMORY": {"success": 0, "runs": 0},
            "TEXT_HISTORY": {"success": 0, "runs": 0},
            "ASSOCIATIVE_MEMORY": {"success": 0, "runs": 0},
        },
        "misleading": {
            "NO_MEMORY": {"success": 0, "runs": 0},
            "TEXT_HISTORY": {"success": 0, "runs": 0},
            "ASSOCIATIVE_MEMORY": {"success": 0, "runs": 0},
        },
    }

    for fam in orig:
        for cond in ("NO_MEMORY", "TEXT_HISTORY", "ASSOCIATIVE_MEMORY"):
            aggregate_counts["original"][cond]["success"] += orig[fam][cond]["first_attempt_successes"]
            aggregate_counts["original"][cond]["runs"] += orig[fam][cond]["runs"]

    for fam in mislead:
        for cond in ("NO_MEMORY", "TEXT_HISTORY", "ASSOCIATIVE_MEMORY"):
            aggregate_counts["misleading"][cond]["success"] += mislead[fam][cond]["first_attempt_successes"]
            aggregate_counts["misleading"][cond]["runs"] += mislead[fam][cond]["runs"]

    primary_counts: dict[str, dict[str, dict[str, int]]] = {
        "original": {},
        "misleading": {},
    }

    for kind in ("original", "misleading"):
        for cond, vals in aggregate_counts[kind].items():
            succ = vals["success"]
            runs = vals["runs"]
            if runs % 2 != 0:
                raise ValueError(f"Total de runs en {kind}/{cond} no es divisible por 2: {runs}")
            if succ % 2 != 0:
                raise ValueError(f"Total de éxitos en {kind}/{cond} no es divisible por 2: {succ}")
            primary_counts[kind][cond] = {
                "success": succ // 2,
                "runs": runs // 2,
            }

    return primary_counts, aggregate_counts


def generate_fig1_h4_first_attempt(results_dir: Path, output_file: Path) -> dict[str, Any]:
    """Genera Fig 1: Éxito al primer intento por condición (primaria: 18 pares; auditoría: 36 runs)."""
    primary_counts, aggregate_counts = derive_h4_counts(results_dir)

    width = 820
    height = 500

    title_sub = (
        "Lectura primaria pre-registrada (réplica equivalente, 18 pares; "
        "derivada de reference-v2/experiment1.json)"
    )
    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" font-family="system-ui, -apple-system, sans-serif">',
        f'  <rect width="{width}" height="{height}" fill="{COLOR_BG}"/>',
        f'  <text x="40" y="42" font-size="18" font-weight="700" fill="{COLOR_TEXT}">'
        "Figura 1: Tasa de éxito al primer intento por condición (H4)</text>",
        f'  <text x="40" y="65" font-size="12" fill="{COLOR_MUTED}">{title_sub}</text>',
    ]

    plot_x = 80
    plot_y = 105
    plot_w = 680
    plot_h = 240

    for pct in (0.0, 0.25, 0.5, 0.75, 1.0):
        y = plot_y + int(plot_h * (1.0 - pct))
        svg_lines.append(
            f'  <line x1="{plot_x}" y1="{y}" x2="{plot_x + plot_w}" y2="{y}" '
            f'stroke="{COLOR_BORDER}" stroke-dasharray="4"/>'
        )
        svg_lines.append(
            f'  <text x="{plot_x - 12}" y="{y + 4}" font-size="11" text-anchor="end" '
            f'fill="{COLOR_MUTED}">{int(pct * 100)}%</text>'
        )

    groups = [
        ("Tareas Originales (EXP-04..06)", "original", plot_x + 60),
        ("Tareas con Señuelo (EXP-07..09)", "misleading", plot_x + 390),
    ]

    bar_w = 58
    spacing = 16

    for label, kind_key, gx in groups:
        svg_lines.append(
            f'  <text x="{gx + bar_w * 1.5 + spacing}" y="{plot_y + plot_h + 28}" '
            f'font-size="13" font-weight="600" text-anchor="middle" fill="{COLOR_TEXT}">{label}</text>'
        )

        cond_info = [
            ("Sin memoria", "NO_MEMORY", COLOR_NO_MEMORY, 0),
            ("Historial", "TEXT_HISTORY", COLOR_TEXT_HISTORY, 1),
            ("Asociativa", "ASSOCIATIVE_MEMORY", COLOR_ASSOCIATIVE, 2),
        ]

        for cond_label, ckey, color, idx in cond_info:
            succ = primary_counts[kind_key][ckey]["success"]
            tot = primary_counts[kind_key][ckey]["runs"]
            rate = succ / tot if tot > 0 else 0.0
            bh = int(plot_h * rate)
            bx = gx + idx * (bar_w + spacing)
            by = plot_y + plot_h - bh

            svg_lines.append(
                f'  <rect x="{bx}" y="{by}" width="{bar_w}" height="{bh}" fill="{color}" rx="4"/>'
            )
            label_y = by - 8 if bh > 20 else by - 6
            svg_lines.append(
                f'  <text x="{bx + bar_w // 2}" y="{label_y}" font-size="12" font-weight="700" '
                f'text-anchor="middle" fill="{COLOR_TEXT}">{succ}/{tot}</text>'
            )
            svg_lines.append(
                f'  <text x="{bx + bar_w // 2}" y="{plot_y + plot_h + 46}" font-size="11" '
                f'text-anchor="middle" fill="{COLOR_MUTED}">{cond_label}</text>'
            )

            agg_succ = aggregate_counts[kind_key][ckey]["success"]
            agg_tot = aggregate_counts[kind_key][ckey]["runs"]
            svg_lines.append(
                f'  <text x="{bx + bar_w // 2}" y="{plot_y + plot_h + 60}" font-size="9" '
                f'text-anchor="middle" fill="{COLOR_MUTED}">[2 rep: {agg_succ}/{agg_tot}]</text>'
            )

    leg_y = plot_y + plot_h + 92
    svg_lines.extend(
        [
            f'  <g transform="translate(200, {leg_y})">',
            f'    <rect x="0" y="0" width="14" height="14" fill="{COLOR_NO_MEMORY}" rx="2"/>',
            f'    <text x="22" y="12" font-size="11" fill="{COLOR_TEXT}">A · Sin memoria</text>',
            f'    <rect x="130" y="0" width="14" height="14" fill="{COLOR_TEXT_HISTORY}" rx="2"/>',
            f'    <text x="152" y="12" font-size="11" fill="{COLOR_TEXT}">B · Historial textual</text>',
            f'    <rect x="280" y="0" width="14" height="14" fill="{COLOR_ASSOCIATIVE}" rx="2"/>',
            f'    <text x="302" y="12" font-size="11" fill="{COLOR_TEXT}">C · Memoria asociativa</text>',
            "  </g>",
        ]
    )

    fn_lines = (
        "Origen: reference-v2/experiment1.json (18 pares primarios) y family_breakdown.json "
        "(36 ejecuciones de dos réplicas).",
        "Solver determinista de 3 operadores, sin LLM. Regenerar: python -m scripts.paper_figures",
    )
    for offset, line in enumerate(fn_lines):
        svg_lines.append(
            f'  <text x="40" y="{height - 31 + offset * 14}" font-size="9.5" '
            f'fill="{COLOR_MUTED}">{escape_xml(line)}</text>'
        )
    svg_lines.append("</svg>\n")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    write_utf8_lf(output_file, "\n".join(svg_lines))

    return {
        "primary": primary_counts,
        "aggregate": aggregate_counts,
    }


def generate_table1_h4_markdown(counts: dict[str, Any], output_file: Path) -> None:
    """Genera Tabla 1 en Markdown con lectura primaria y auditoría agregada de H4."""
    pri = counts["primary"]
    agg = counts["aggregate"]

    md_lines = [
        "# Tabla 1: Éxito al primer intento por condición (H4)",
        "",
        "| Tipo de tarea | A · Sin memoria (Primario) | B · Historial (Primario) | "
        "C · Asociativa (Primario) | Dif. C − B | Auditoría ambas réplicas (A / B / C / 36 runs) |",
        "|---|---|---|---|---|---|",
    ]

    for kind, label in (
        ("original", "Originales (EXP-04..06)"),
        ("misleading", "Con señuelo (EXP-07..09)"),
    ):
        sa = pri[kind]["NO_MEMORY"]["success"]
        ta = pri[kind]["NO_MEMORY"]["runs"]
        sb = pri[kind]["TEXT_HISTORY"]["success"]
        tb = pri[kind]["TEXT_HISTORY"]["runs"]
        sc = pri[kind]["ASSOCIATIVE_MEMORY"]["success"]
        tc = pri[kind]["ASSOCIATIVE_MEMORY"]["runs"]

        diff = sc - sb

        asa = agg[kind]["NO_MEMORY"]["success"]
        asb = agg[kind]["TEXT_HISTORY"]["success"]
        asc = agg[kind]["ASSOCIATIVE_MEMORY"]["success"]
        at = agg[kind]["NO_MEMORY"]["runs"]

        md_lines.append(
            f"| {label} | {sa}/{ta} ({sa / ta:.2f}) | {sb}/{tb} ({sb / tb:.2f}) | "
            f"{sc}/{tc} ({sc / tc:.2f}) | {diff:+d} | {asa}/{at} · {asb}/{at} · {asc}/{at} |"
        )

    md_lines.extend(
        [
            "",
            "> **Nota metodológica:** La lectura primaria utiliza una réplica equivalente derivada",
            "> tras verificar `replication.all_semantic_projections_equal == True` en "
            "`reference-v2/experiment1.json`.",
            "> La columna de auditoría reporta el total consolidado de ambas réplicas (36 ejecuciones,",
            "> fuente: `results/reference-v2/family_breakdown.json`).",
            "> Las 36 ejecuciones reúnen dos réplicas deterministas; no son 36 observaciones independientes.",
            "> El agente evaluado es el solver determinista de tres operadores sin LLM.",
            "> Regenerar: `python -m scripts.paper_figures`.",
            "",
        ]
    )
    output_file.parent.mkdir(parents=True, exist_ok=True)
    write_utf8_lf(output_file, "\n".join(md_lines))


# ==============================================================================
# 2. FIGURA 2 & TABLA 2: Atribución de Lecciones en Tareas con Señuelo
# ==============================================================================


def generate_fig2_lesson_attribution(results_dir: Path, output_file: Path) -> dict[str, Any]:
    """Genera Fig 2: Mapa de citas de lecciones derivado dinámicamente de task_breakdown.json."""
    tb_file = results_dir / "reference-v2" / "task_breakdown.json"
    data = json.loads(tb_file.read_text(encoding="utf-8"))

    tasks_data = data["tasks"]
    attribution_data: dict[str, Any] = {}

    for tid in data.get("misleading_tasks", ["EXP-07", "EXP-08", "EXP-09"]):
        tinfo = tasks_data[tid]
        b_info = tinfo["TEXT_HISTORY"]
        c_info = tinfo["ASSOCIATIVE_MEMORY"]
        fam = b_info.get("family", "N/A")
        decoy_fam = b_info.get("decoy_family", "N/A")

        b_cites = b_info["cited_lessons_by_source_task"]
        c_cites = c_info["cited_lessons_by_source_task"]

        decoy_task_b = max(b_cites.keys(), key=lambda k: b_cites[k]) if b_cites else "N/A"
        decoy_count_b = b_cites.get(decoy_task_b, 0)

        decoy_task_c = max(c_cites.keys(), key=lambda k: c_cites[k]) if c_cites else "N/A"
        decoy_count_c = c_cites.get(decoy_task_c, 0)

        runs = b_info["runs"]
        succ_b = int(b_info["FirstAttemptSuccessRate"] * runs)
        succ_c = int(c_info["FirstAttemptSuccessRate"] * runs)

        attribution_data[tid] = {
            "real_family": fam,
            "decoy_family": decoy_fam,
            "decoy_task_b": decoy_task_b,
            "decoy_count_b": decoy_count_b,
            "decoy_task_c": decoy_task_c,
            "decoy_count_c": decoy_count_c,
            "runs": runs,
            "succ_b": succ_b,
            "succ_c": succ_c,
            "rate_b": b_info["FirstAttemptSuccessRate"],
            "rate_c": c_info["FirstAttemptSuccessRate"],
        }

    width = 800
    height = 420

    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" font-family="system-ui, -apple-system, sans-serif">',
        f'  <rect width="{width}" height="{height}" fill="{COLOR_BG}"/>',
        f'  <text x="40" y="45" font-size="18" font-weight="700" fill="{COLOR_TEXT}">'
        "Figura 2: Atribución y citación de lecciones en tareas con señuelo (H4)</text>",
        f'  <text x="40" y="70" font-size="13" fill="{COLOR_MUTED}">'
        "Citas efectivas derivadas dinámicamente de reference-v2/task_breakdown.json</text>",
        "  <!-- Cabecera -->",
        '  <rect x="40" y="100" width="720" height="35" fill="#f1f5f9" rx="4"/>',
        f'  <text x="55" y="122" font-size="12" font-weight="700" fill="{COLOR_TEXT}">Tarea</text>',
        f'  <text x="145" y="122" font-size="12" font-weight="700" fill="{COLOR_TEXT}">Familia Real</text>',
        f'  <text x="250" y="122" font-size="12" font-weight="700" fill="{COLOR_TEXT}">Señuelo Léxico</text>',
        f'  <text x="375" y="122" font-size="12" font-weight="700" '
        f'fill="{COLOR_TEXT}">B · Historial citó</text>',
        f'  <text x="515" y="122" font-size="12" font-weight="700" '
        f'fill="{COLOR_TEXT}">C · Asociativa citó</text>',
        f'  <text x="655" y="122" font-size="12" font-weight="700" '
        f'fill="{COLOR_TEXT}">Acierto 1º int.</text>',
    ]

    row_y = 145
    row_h = 60

    for tid, item in attribution_data.items():
        runs = item["runs"]
        lbl_b = f"{item['decoy_task_b']} ({item['decoy_count_b']}/{runs} señuelo)"
        lbl_c = f"{item['decoy_task_c']} ({item['decoy_count_c']}/{runs} señuelo)"
        res_txt = f"{item['succ_c']}/{runs} ({item['rate_c']:.0%})"

        svg_lines.extend(
            [
                f"  <!-- Fila {tid} -->",
                f'  <rect x="40" y="{row_y}" width="720" height="{row_h}" '
                f'fill="#ffffff" stroke="{COLOR_BORDER}" rx="4"/>',
                f'  <text x="55" y="{row_y + 35}" font-size="13" font-weight="700" '
                f'fill="{COLOR_TEXT}">{tid}</text>',
                f'  <text x="145" y="{row_y + 35}" font-size="12" fill="{COLOR_TEXT}">'
                f"{escape_xml(item['real_family'])}</text>",
                f'  <rect x="245" y="{row_y + 18}" width="110" height="26" fill="#fee2e2" rx="3"/>',
                f'  <text x="300" y="{row_y + 35}" font-size="11" font-weight="600" text-anchor="middle" '
                f'fill="#991b1b">{escape_xml(item["decoy_family"])}</text>',
                "  <!-- B -->",
                f'  <rect x="370" y="{row_y + 18}" width="125" height="26" '
                f'fill="#fef2f2" stroke="#fca5a5" rx="3"/>',
                f'  <text x="432" y="{row_y + 35}" font-size="11" font-weight="600" text-anchor="middle" '
                f'fill="#b91c1c">{lbl_b}</text>',
                "  <!-- C -->",
                f'  <rect x="510" y="{row_y + 18}" width="125" height="26" '
                f'fill="#fef2f2" stroke="#fca5a5" rx="3"/>',
                f'  <text x="572" y="{row_y + 35}" font-size="11" font-weight="600" text-anchor="middle" '
                f'fill="#b91c1c">{lbl_c}</text>',
                "  <!-- Resultado -->",
                f'  <rect x="650" y="{row_y + 18}" width="95" height="26" '
                f'fill="#f8fafc" stroke="{COLOR_BORDER}" rx="3"/>',
                f'  <text x="697" y="{row_y + 35}" font-size="12" font-weight="700" text-anchor="middle" '
                f'fill="#e11d48">{res_txt}</text>',
            ]
        )
        row_y += row_h + 10

    note_text = (
        "Hallazgo clave: Tanto B como C citaron la lección señuelo en el 100% de las ejecuciones, "
        "resultando en tasa de acierto cero al primer intento."
    )
    svg_lines.extend(
        [
            f'  <rect x="40" y="340" width="720" height="42" fill="#f8fafc" stroke="{COLOR_BORDER}" rx="4"/>',
            f'  <text x="55" y="365" font-size="11" fill="{COLOR_MUTED}">{note_text}</text>',
        ]
    )

    fn = escape_xml(FOOTNOTE_BASE.format(campaign="reference-v2 (#44, #46)"))
    svg_lines.append(f'  <text x="40" y="{height - 14}" font-size="10" fill="{COLOR_MUTED}">{fn}</text>')
    svg_lines.append("</svg>\n")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    write_utf8_lf(output_file, "\n".join(svg_lines))

    return attribution_data


def generate_table2_misleading_markdown(attr_data: dict[str, Any], output_file: Path) -> None:
    """Genera Tabla 2 en Markdown para las citas en tareas con señuelo."""
    md_lines = [
        "# Tabla 2: Atribución de lecciones y citas en tareas engañosas (H4)",
        "",
        "| Tarea | Familia Real | Familia Señuelo | Citas en B (Historial) | "
        "Citas en C (Asociativa) | Éxito 1º intento (B y C) |",
        "|---|---|---|---|---|---|",
    ]

    for tid, item in attr_data.items():
        runs = item["runs"]
        cb = f"{item['decoy_count_b']}/{runs} ({item['decoy_task_b']})"
        cc = f"{item['decoy_count_c']}/{runs} ({item['decoy_task_c']})"
        succ = f"{item['succ_c']}/{runs} ({item['rate_c']:.2f})"
        md_lines.append(f"| {tid} | {item['real_family']} | {item['decoy_family']} | {cb} | {cc} | {succ} |")

    md_lines.extend(
        [
            "",
            "> **Nota:** Datos derivados directamente de `results/reference-v2/task_breakdown.json`.",
            "> Regenerar: `python -m scripts.paper_figures`.",
            "",
        ]
    )
    output_file.parent.mkdir(parents=True, exist_ok=True)
    write_utf8_lf(output_file, "\n".join(md_lines))


# ==============================================================================
# 3. FIGURA 3 & TABLA 3: Distribución de Intentos por Tarea y Condición
# ==============================================================================


def derive_attempts_distribution(results_dir: Path) -> dict[str, dict[str, int]]:
    """Deriva la distribución exacta de intentos (1, 2, 3) desde experiment1.json comparisons."""
    exp_file = results_dir / "reference-v2" / "experiment1.json"
    data = json.loads(exp_file.read_text(encoding="utf-8"))

    comparisons = data.get("comparisons", [])
    if not comparisons:
        raise ValueError("No se encontraron comparisons en reference-v2/experiment1.json")

    raw_counts: dict[str, dict[str, dict[str, int]]] = {
        "Originales": {
            "NO_MEMORY": {"1": 0, "2": 0, "3": 0, "total": 0},
            "TEXT_HISTORY": {"1": 0, "2": 0, "3": 0, "total": 0},
            "ASSOCIATIVE_MEMORY": {"1": 0, "2": 0, "3": 0, "total": 0},
        },
        "Señuelos": {
            "NO_MEMORY": {"1": 0, "2": 0, "3": 0, "total": 0},
            "TEXT_HISTORY": {"1": 0, "2": 0, "3": 0, "total": 0},
            "ASSOCIATIVE_MEMORY": {"1": 0, "2": 0, "3": 0, "total": 0},
        },
    }

    for comp in comparisons:
        task = comp["task"]
        mode = comp["mode"]

        if task in ("EXP-04", "EXP-05", "EXP-06"):
            cat = "Originales"
        elif task in ("EXP-07", "EXP-08", "EXP-09"):
            cat = "Señuelos"
        else:
            continue

        treat_it = str(comp["treatment_observations"]["iterations"])
        if mode in raw_counts[cat] and treat_it in raw_counts[cat][mode]:
            raw_counts[cat][mode][treat_it] += 1
            raw_counts[cat][mode]["total"] += 1

    formatted_data: dict[str, dict[str, int]] = {
        "Originales · Sin memoria": raw_counts["Originales"]["NO_MEMORY"],
        "Originales · Historial": raw_counts["Originales"]["TEXT_HISTORY"],
        "Originales · Asociativa": raw_counts["Originales"]["ASSOCIATIVE_MEMORY"],
        "Señuelos · Sin memoria": raw_counts["Señuelos"]["NO_MEMORY"],
        "Señuelos · Historial": raw_counts["Señuelos"]["TEXT_HISTORY"],
        "Señuelos · Asociativa": raw_counts["Señuelos"]["ASSOCIATIVE_MEMORY"],
    }
    return formatted_data


def generate_fig3_attempts_distribution(results_dir: Path, output_file: Path) -> dict[str, Any]:
    """Genera Fig 3: Barras apiladas de distribución de intentos derivadas de los datos."""
    attempts_data = derive_attempts_distribution(results_dir)

    width = 800
    height = 460

    sub_title = (
        "Barras apiladas de ejecuciones resueltas al intento 1, 2 o 3 "
        "(derivado de experiment1.json comparisons)"
    )
    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" font-family="system-ui, -apple-system, sans-serif">',
        f'  <rect width="{width}" height="{height}" fill="{COLOR_BG}"/>',
        f'  <text x="40" y="45" font-size="18" font-weight="700" fill="{COLOR_TEXT}">'
        "Figura 3: Distribución del número de intentos por tarea y condición</text>",
        f'  <text x="40" y="70" font-size="13" fill="{COLOR_MUTED}">{sub_title}</text>',
    ]

    plot_x = 220
    plot_y = 100
    plot_w = 520
    bar_h = 32
    gap = 18

    c_1 = "#22c55e"  # 1 intento
    c_2 = "#f59e0b"  # 2 intentos
    c_3 = "#ef4444"  # 3 intentos

    y = plot_y
    for label, counts in attempts_data.items():
        svg_lines.append(
            f'  <text x="{plot_x - 15}" y="{y + 21}" font-size="12" font-weight="600" '
            f'text-anchor="end" fill="{COLOR_TEXT}">{label}</text>'
        )

        tot = counts["total"]
        cur_x = plot_x

        for attempt_key, color in (("1", c_1), ("2", c_2), ("3", c_3)):
            cnt = counts[attempt_key]
            if cnt > 0 and tot > 0:
                seg_w = int(plot_w * (cnt / tot))
                svg_lines.append(
                    f'  <rect x="{cur_x}" y="{y}" width="{seg_w}" height="{bar_h}" '
                    f'fill="{color}" stroke="#ffffff" stroke-width="1.5"/>'
                )
                if seg_w >= 22:
                    svg_lines.append(
                        f'  <text x="{cur_x + seg_w // 2}" y="{y + 21}" font-size="11" font-weight="700" '
                        f'text-anchor="middle" fill="#ffffff">{cnt}/{tot}</text>'
                    )
                cur_x += seg_w

        y += bar_h + gap

    leg_y = y + 15
    svg_lines.extend(
        [
            f'  <g transform="translate(250, {leg_y})">',
            f'    <rect x="0" y="0" width="14" height="14" fill="{c_1}" rx="2"/>',
            f'    <text x="22" y="12" font-size="12" fill="{COLOR_TEXT}">1 intento</text>',
            f'    <rect x="130" y="0" width="14" height="14" fill="{c_2}" rx="2"/>',
            f'    <text x="152" y="12" font-size="12" fill="{COLOR_TEXT}">2 intentos</text>',
            f'    <rect x="250" y="0" width="14" height="14" fill="{c_3}" rx="2"/>',
            f'    <text x="272" y="12" font-size="12" fill="{COLOR_TEXT}">3 intentos</text>',
            "  </g>",
        ]
    )

    fn = escape_xml(FOOTNOTE_BASE.format(campaign="reference-v2 (#44, #46)"))
    svg_lines.append(f'  <text x="40" y="{height - 15}" font-size="10" fill="{COLOR_MUTED}">{fn}</text>')
    svg_lines.append("</svg>\n")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    write_utf8_lf(output_file, "\n".join(svg_lines))

    return attempts_data


def generate_table3_attempts_markdown(attempts_data: dict[str, Any], output_file: Path) -> None:
    """Genera Tabla 3 en Markdown para la distribución de intentos."""
    md_lines = [
        "# Tabla 3: Distribución de intentos por tarea y condición",
        "",
        "| Condición y tipo de tarea | 1 intento | 2 intentos | 3 intentos | "
        "Total ejecuciones | Promedio intentos |",
        "|---|---|---|---|---|---|",
    ]

    for label, counts in attempts_data.items():
        c1 = counts["1"]
        c2 = counts["2"]
        c3 = counts["3"]
        tot = counts["total"]
        mean_it = (c1 * 1 + c2 * 2 + c3 * 3) / tot if tot > 0 else 0.0
        md_lines.append(f"| {label} | {c1}/{tot} | {c2}/{tot} | {c3}/{tot} | {tot} | {mean_it:.2f} |")

    md_lines.extend(
        [
            "",
            "> **Nota:** Datos derivados de `results/reference-v2/experiment1.json:comparisons`.",
            "> Las 36 ejecuciones reúnen dos réplicas deterministas; no son 36 observaciones independientes.",
            "> Regenerar: `python -m scripts.paper_figures`.",
            "",
        ]
    )
    output_file.parent.mkdir(parents=True, exist_ok=True)
    write_utf8_lf(output_file, "\n".join(md_lines))


# ==============================================================================
# 4. FIGURA 4 & TABLA 4: H7 Transferencia y Contaminación de Fallos por Tau
# ==============================================================================


def derive_h7_summary(results_dir: Path) -> list[dict[str, Any]]:
    """Deriva dinámicamente las celdas de H7 desde failure_transfer_analysis.json:cells."""
    h7_file = results_dir / "failure-transfer-v1" / "failure_transfer_analysis.json"
    data = json.loads(h7_file.read_text(encoding="utf-8"))
    cells = data["cells"]

    order = [
        ("A", "0.25", "real", "original", "A (Sin lecciones)"),
        ("A", "0.1", "real", "original", "A (Sin lecciones)"),
        ("A", "0.0", "real", "original", "A (Sin lecciones)"),
        ("C", "0.25", "real", "original", "C (Con lecciones)"),
        ("C", "0.25", "placebo", "original", "C (Con lecciones)"),
        ("C", "0.1", "real", "original", "C (Con lecciones)"),
        ("C", "0.1", "placebo", "original", "C (Con lecciones)"),
        ("C", "0.0", "placebo", "original", "C (Con lecciones)"),
    ]

    summary = []
    for base_key, tau_key, var_key, kind_key, label_prefix in order:
        cell_data = cells[base_key][tau_key][var_key][kind_key]
        helped = cell_data["helped"]["numerator"]
        hurt = cell_data["hurt"]["numerator"]
        denominator = cell_data["pairs"]
        exposure = cell_data["Exposure"]["numerator"]
        changed = cell_data["Changed"]["numerator"]

        summary.append(
            {
                "base": label_prefix,
                "base_key": base_key,
                "tau": tau_key,
                "var": var_key,
                "kind": kind_key,
                "helped": helped,
                "hurt": hurt,
                "pairs": denominator,
                "exposure": exposure,
                "changed": changed,
            }
        )

    return summary


def generate_fig4_h7_failure_transfer(results_dir: Path, output_file: Path) -> dict[str, Any]:
    """Genera Fig 4: Pares ayudados vs dañados en H7 según umbral tau y placebo."""
    h7_summary = derive_h7_summary(results_dir)

    width = 820
    height = 490

    sub_title = (
        "Pares de tareas ayudadas (+1º intento) frente a dañadas (-1º intento), "
        "derivados de failure_transfer_analysis.json"
    )
    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" font-family="system-ui, -apple-system, sans-serif">',
        f'  <rect width="{width}" height="{height}" fill="{COLOR_BG}"/>',
        f'  <text x="40" y="45" font-size="18" font-weight="700" fill="{COLOR_TEXT}">'
        "Figura 4: Transferencia y contaminación de fallos por umbral \u03c4 (H7)</text>",
        f'  <text x="40" y="70" font-size="13" fill="{COLOR_MUTED}">{sub_title}</text>',
    ]

    plot_x = 240
    plot_y = 100
    row_h = 32
    gap = 12

    y = plot_y
    for item in h7_summary:
        lbl = f"{item['base']} | \u03c4={item['tau']} ({item['var']})"
        svg_lines.append(
            f'  <text x="{plot_x - 15}" y="{y + 21}" font-size="11" font-weight="600" '
            f'text-anchor="end" fill="{COLOR_TEXT}">{lbl}</text>'
        )

        zero_x = plot_x + 180
        svg_lines.append(
            f'  <line x1="{zero_x}" y1="{plot_y - 10}" x2="{zero_x}" '
            f'y2="{plot_y + len(h7_summary) * (row_h + gap)}" stroke="{COLOR_BORDER}" stroke-width="2"/>'
        )

        tot = item["pairs"]
        helped = int(item["helped"])
        hurt = int(item["hurt"])
        if helped > 0:
            bw = helped * 45
            svg_lines.append(
                f'  <rect x="{zero_x}" y="{y}" width="{bw}" height="{row_h}" fill="{COLOR_HELPED}" rx="3"/>'
            )
            svg_lines.append(
                f'  <text x="{zero_x + bw + 8}" y="{y + 20}" font-size="11" font-weight="700" '
                f'fill="{COLOR_HELPED}">+{helped}/{tot} ayuda</text>'
            )

        if hurt > 0:
            bw = hurt * 45
            bx = zero_x - bw
            svg_lines.append(
                f'  <rect x="{bx}" y="{y}" width="{bw}" height="{row_h}" fill="{COLOR_HURT}" rx="3"/>'
            )
            svg_lines.append(
                f'  <text x="{bx - 8}" y="{y + 20}" font-size="11" font-weight="700" '
                f'text-anchor="end" fill="{COLOR_HURT}">-{hurt}/{tot} daña</text>'
            )

        if helped == 0 and hurt == 0:
            svg_lines.append(
                f'  <text x="{zero_x + 8}" y="{y + 20}" font-size="11" '
                f'fill="{COLOR_MUTED}">0/{tot} cambios</text>'
            )

        y += row_h + gap

    leg_y = y + 10
    svg_lines.extend(
        [
            f'  <g transform="translate(240, {leg_y})">',
            f'    <rect x="0" y="0" width="14" height="14" fill="{COLOR_HELPED}" rx="2"/>',
            f'    <text x="22" y="12" font-size="11" fill="{COLOR_TEXT}">Pares ayudados (+1 intento)</text>',
            f'    <rect x="230" y="0" width="14" height="14" fill="{COLOR_HURT}" rx="2"/>',
            f'    <text x="252" y="12" font-size="11" fill="{COLOR_TEXT}">Pares dañados (-1 intento)</text>',
            "  </g>",
        ]
    )

    fn = escape_xml(FOOTNOTE_BASE.format(campaign="failure-transfer-v1 (#65)"))
    svg_lines.append(f'  <text x="40" y="{height - 15}" font-size="10" fill="{COLOR_MUTED}">{fn}</text>')
    svg_lines.append("</svg>\n")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    write_utf8_lf(output_file, "\n".join(svg_lines))

    return {"summary": h7_summary}


def generate_table4_h7_markdown(h7_data: dict[str, Any], output_file: Path) -> None:
    """Genera Tabla 4 en Markdown para el efecto de la memoria de fallos en H7."""
    md_lines = [
        "# Tabla 4: Transferencia y contaminación de fallos por umbral τ (H7)",
        "",
        "| Base | Umbral τ | Variante | Pares evaluados | Pares ayudados | Pares dañados |",
        "|---|---|---|---|---|---|",
    ]

    for item in h7_data["summary"]:
        pairs = item["pairs"]
        helped = item["helped"]
        hurt = item["hurt"]
        md_lines.append(
            f"| {item['base']} | {item['tau']} | {item['var']} | {pairs} | "
            f"+{helped}/{pairs} | -{hurt}/{pairs} |"
        )

    md_lines.extend(
        [
            "",
            "> **Nota:** Conteos descriptivos de pares de tareas según umbral τ y variante.",
            "> Pares ayudados: +1 primer intento correcto; pares dañados: -1 primer intento correcto.",
            "> Datos derivados directamente de `results/failure-transfer-v1/failure_transfer_analysis.json`.",
            "> Campaña: `failure-transfer-v1` (#65). Regenerar: `python -m scripts.paper_figures`.",
            "",
        ]
    )
    output_file.parent.mkdir(parents=True, exist_ok=True)
    write_utf8_lf(output_file, "\n".join(md_lines))


# ==============================================================================
# 5. FIGURA 5 & TABLA 5: #58 Línea Base con Diagnóstico Público
# ==============================================================================


def derive_diagnostic_baseline(results_dir: Path) -> dict[str, Any]:
    """Deriva dinámicamente las métricas de diagnóstico público común D (#58)."""
    diag_file = results_dir / "diagnostic-baseline-v1" / "diagnostic_analysis.json"
    data = json.loads(diag_file.read_text(encoding="utf-8"))

    orig = data["kinds"]["original"]["conditions"]
    mislead = data["kinds"]["misleading"]["conditions"]

    diag_counts = {
        "original": {
            "A": orig["NO_MEMORY"]["FirstAttemptSuccess"]["numerator"],
            "B": orig["TEXT_HISTORY"]["FirstAttemptSuccess"]["numerator"],
            "C": orig["ASSOCIATIVE_MEMORY"]["FirstAttemptSuccess"]["numerator"],
            "total": orig["NO_MEMORY"]["FirstAttemptSuccess"]["denominator"],
        },
        "misleading": {
            "A": mislead["NO_MEMORY"]["FirstAttemptSuccess"]["numerator"],
            "B": mislead["TEXT_HISTORY"]["FirstAttemptSuccess"]["numerator"],
            "C": mislead["ASSOCIATIVE_MEMORY"]["FirstAttemptSuccess"]["numerator"],
            "total": mislead["NO_MEMORY"]["FirstAttemptSuccess"]["denominator"],
        },
    }
    return diag_counts


def generate_fig5_diagnostic_baseline(results_dir: Path, output_file: Path) -> dict[str, Any]:
    """Genera Fig 5: Comparación con diagnóstico público común D (#58)."""
    diag_counts = derive_diagnostic_baseline(results_dir)

    width = 800
    height = 460

    sub_title = (
        "Acierto al primer intento con diagnóstico común de 3 reglas sobre excepción (18 pares por tipo)"
    )
    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" font-family="system-ui, -apple-system, sans-serif">',
        f'  <rect width="{width}" height="{height}" fill="{COLOR_BG}"/>',
        f'  <text x="40" y="45" font-size="18" font-weight="700" fill="{COLOR_TEXT}">'
        "Figura 5: Desempeño bajo línea base de diagnóstico público D (#58)</text>",
        f'  <text x="40" y="70" font-size="13" fill="{COLOR_MUTED}">{sub_title}</text>',
    ]

    plot_x = 80
    plot_y = 110
    plot_w = 660
    plot_h = 230

    for pct in (0.0, 0.25, 0.5, 0.75, 1.0):
        y = plot_y + int(plot_h * (1.0 - pct))
        svg_lines.append(
            f'  <line x1="{plot_x}" y1="{y}" x2="{plot_x + plot_w}" y2="{y}" '
            f'stroke="{COLOR_BORDER}" stroke-dasharray="4"/>'
        )
        svg_lines.append(
            f'  <text x="{plot_x - 12}" y="{y + 4}" font-size="11" text-anchor="end" '
            f'fill="{COLOR_MUTED}">{int(pct * 100)}%</text>'
        )

    orig_diff = diag_counts["original"]["B"] - diag_counts["original"]["A"]
    misl_diff = diag_counts["misleading"]["B"] - diag_counts["misleading"]["A"]

    groups = [
        (
            f"Originales (Δ B−A: {orig_diff:+d}/{diag_counts['original']['total']})",
            "original",
            plot_x + 60,
        ),
        (
            f"Engañosas (Δ B−A: {misl_diff:+d}/{diag_counts['misleading']['total']})",
            "misleading",
            plot_x + 380,
        ),
    ]

    bar_w = 55
    spacing = 15

    for label, kind_key, gx in groups:
        svg_lines.append(
            f'  <text x="{gx + bar_w * 1.5 + spacing}" y="{plot_y + plot_h + 30}" '
            f'font-size="13" font-weight="600" text-anchor="middle" fill="{COLOR_TEXT}">{label}</text>'
        )

        cond_info = [
            ("Sin memoria", "A", COLOR_NO_MEMORY, 0),
            ("Historial", "B", COLOR_TEXT_HISTORY, 1),
            ("Asociativa", "C", COLOR_ASSOCIATIVE, 2),
        ]

        tot = diag_counts[kind_key]["total"]
        for cond_label, ckey, color, idx in cond_info:
            succ = diag_counts[kind_key][ckey]
            rate = succ / tot if tot > 0 else 0.0
            bh = int(plot_h * rate)
            bx = gx + idx * (bar_w + spacing)
            by = plot_y + plot_h - bh

            svg_lines.append(
                f'  <rect x="{bx}" y="{by}" width="{bar_w}" height="{bh}" fill="{color}" rx="4"/>'
            )
            svg_lines.append(
                f'  <text x="{bx + bar_w // 2}" y="{by - 6}" font-size="12" font-weight="700" '
                f'text-anchor="middle" fill="{COLOR_TEXT}">{succ}/{tot}</text>'
            )
            svg_lines.append(
                f'  <text x="{bx + bar_w // 2}" y="{plot_y + plot_h + 50}" font-size="11" '
                f'text-anchor="middle" fill="{COLOR_MUTED}">{cond_label}</text>'
            )

    leg_y = plot_y + plot_h + 80
    svg_lines.extend(
        [
            f'  <g transform="translate(200, {leg_y})">',
            f'    <rect x="0" y="0" width="14" height="14" fill="{COLOR_NO_MEMORY}" rx="2"/>',
            f'    <text x="22" y="12" font-size="11" fill="{COLOR_TEXT}">A · Con D (sin memoria)</text>',
            f'    <rect x="160" y="0" width="14" height="14" fill="{COLOR_TEXT_HISTORY}" rx="2"/>',
            f'    <text x="182" y="12" font-size="11" fill="{COLOR_TEXT}">B · Con D + Historial</text>',
            f'    <rect x="320" y="0" width="14" height="14" fill="{COLOR_ASSOCIATIVE}" rx="2"/>',
            f'    <text x="342" y="12" font-size="11" fill="{COLOR_TEXT}">C · Con D + Asociativa</text>',
            "  </g>",
        ]
    )

    fn_lines = (
        "Origen: campaña diagnostic-baseline-v1 (#58); solver determinista de 3 operadores, sin LLM.",
        "Conteos exactos. Regenerar: python -m scripts.paper_figures",
    )
    for offset, line in enumerate(fn_lines):
        svg_lines.append(
            f'  <text x="40" y="{height - 31 + offset * 14}" font-size="10" '
            f'fill="{COLOR_MUTED}">{escape_xml(line)}</text>'
        )
    svg_lines.append("</svg>\n")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    write_utf8_lf(output_file, "\n".join(svg_lines))

    return diag_counts


def generate_table5_diagnostic_markdown(diag_counts: dict[str, Any], output_file: Path) -> None:
    """Genera Tabla 5 en Markdown para la línea base diagnóstica #58."""
    md_lines = [
        "# Tabla 5: Línea base de diagnóstico público común (#58) — Diferencia observada de aciertos",
        "",
        "| Tipo de tarea | A · Sin memoria (con D) | B · Historial (con D) | "
        "C · Asociativa (con D) | Δ aciertos B − A | Δ aciertos C − A |",
        "|---|---|---|---|---|---|",
    ]

    for kind, label in (
        ("original", "Originales (EXP-04..06)"),
        ("misleading", "Engañosas (EXP-07..09)"),
    ):
        tot = diag_counts[kind]["total"]
        sa = diag_counts[kind]["A"]
        sb = diag_counts[kind]["B"]
        sc = diag_counts[kind]["C"]
        db = sb - sa
        dc = sc - sa

        md_lines.append(
            f"| {label} | {sa}/{tot} ({sa / tot:.2f}) | {sb}/{tot} ({sb / tot:.2f}) | "
            f"{sc}/{tot} ({sc / tot:.2f}) | {db:+d}/{tot} | {dc:+d}/{tot} |"
        )

    md_lines.extend(
        [
            "",
            "> **Nota:** Línea base D agrega tres reglas públicas de diagnóstico por tipo de excepción.",
            "> Conteos descriptivos y diferencias observadas de aciertos (Δ) con "
            "denominador entre condiciones.",
            "> Campaña: `diagnostic-baseline-v1` (#58). Regenerar: `python -m scripts.paper_figures`.",
            "",
        ]
    )
    output_file.parent.mkdir(parents=True, exist_ok=True)
    write_utf8_lf(output_file, "\n".join(md_lines))


# ==============================================================================
# 6. ESQUEMAS METODOLÓGICOS (FIGURAS 6 Y 7)
# ==============================================================================


def generate_fig6_experimental_design_schema(output_file: Path) -> None:
    """Genera Fig 6: Esquema metodológico del diseño experimental."""
    width = 800
    height = 420

    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" font-family="system-ui, -apple-system, sans-serif">',
        f'  <rect width="{width}" height="{height}" fill="{COLOR_BG}"/>',
        f'  <text x="40" y="40" font-size="16" font-weight="700" fill="{COLOR_TEXT}">'
        "Figura 6: Esquema del diseño experimental (condiciones, tareas y señuelos)</text>",
        '  <rect x="40" y="55" width="410" height="24" fill="#fef3c7" stroke="#f59e0b" rx="3"/>',
        '  <text x="48" y="71" font-size="11" font-weight="700" fill="#b45309">'
        "ESQUEMA METODOLÓGICO (NO ES RESULTADO EXPERIMENTAL)</text>",
        "  <!-- Bloque Entrenamiento -->",
        f'  <rect x="40" y="100" width="220" height="220" fill="#f8fafc" stroke="{COLOR_BORDER}" '
        'stroke-width="1.5" rx="6"/>',
        f'  <text x="55" y="125" font-size="13" font-weight="700" fill="{COLOR_TEXT}">'
        "1. Entrenamiento (Train)</text>",
        f'  <text x="55" y="145" font-size="11" fill="{COLOR_MUTED}">Siembra de memoria léxica</text>',
        '  <rect x="55" y="165" width="190" height="32" fill="#e0f2fe" rx="4"/>',
        '  <text x="65" y="185" font-size="11" font-weight="600" fill="#0369a1">'
        "EXP-01: Auth (Storage)</text>",
        '  <rect x="55" y="205" width="190" height="32" fill="#e0f2fe" rx="4"/>',
        '  <text x="65" y="225" font-size="11" font-weight="600" fill="#0369a1">'
        "EXP-02: Config (Norm Env)</text>",
        '  <rect x="55" y="245" width="190" height="32" fill="#e0f2fe" rx="4"/>',
        '  <text x="65" y="265" font-size="11" font-weight="600" fill="#0369a1">'
        "EXP-03: Readiness (Identity)</text>",
        "  <!-- Bloque Transferencia Original -->",
        '  <rect x="310" y="100" width="210" height="220" fill="#f0fdf4" stroke="#86efac" '
        'stroke-width="1.5" rx="6"/>',
        f'  <text x="325" y="125" font-size="13" font-weight="700" fill="{COLOR_TEXT}">'
        "2. Transfer Original</text>",
        f'  <text x="325" y="145" font-size="11" fill="{COLOR_MUTED}">Texto alineado a familia real</text>',
        '  <rect x="325" y="165" width="180" height="32" fill="#dcfce7" rx="4"/>',
        '  <text x="335" y="185" font-size="11" font-weight="600" fill="#15803d">EXP-04: Auth</text>',
        '  <rect x="325" y="205" width="180" height="32" fill="#dcfce7" rx="4"/>',
        '  <text x="335" y="225" font-size="11" font-weight="600" fill="#15803d">EXP-05: Config</text>',
        '  <rect x="325" y="245" width="180" height="32" fill="#dcfce7" rx="4"/>',
        '  <text x="335" y="265" font-size="11" font-weight="600" fill="#15803d">EXP-06: Readiness</text>',
        "  <!-- Bloque Transferencia Engañosa -->",
        '  <rect x="540" y="100" width="220" height="220" fill="#fef2f2" stroke="#fca5a5" '
        'stroke-width="1.5" rx="6"/>',
        f'  <text x="555" y="125" font-size="13" font-weight="700" fill="{COLOR_TEXT}">'
        "3. Transfer Señuelo (Decoy)</text>",
        f'  <text x="555" y="145" font-size="11" fill="{COLOR_MUTED}">Texto imita familia ajena</text>',
        '  <rect x="555" y="165" width="190" height="32" fill="#fee2e2" rx="4"/>',
        '  <text x="565" y="185" font-size="10" font-weight="600" fill="#b91c1c">'
        "EXP-07 (Real Auth \u2192 Señuelo Read)</text>",
        '  <rect x="555" y="205" width="190" height="32" fill="#fee2e2" rx="4"/>',
        '  <text x="565" y="225" font-size="10" font-weight="600" fill="#b91c1c">'
        "EXP-08 (Real Config \u2192 Señuelo Auth)</text>",
        '  <rect x="555" y="245" width="190" height="32" fill="#fee2e2" rx="4"/>',
        '  <text x="565" y="265" font-size="10" font-weight="600" fill="#b91c1c">'
        "EXP-09 (Real Read \u2192 Señuelo Conf)</text>",
        f'  <rect x="40" y="335" width="720" height="42" fill="#f8fafc" stroke="{COLOR_BORDER}" rx="4"/>',
        f'  <text x="55" y="360" font-size="11" font-weight="600" fill="{COLOR_TEXT}">'
        "Condiciones cruzadas en 6 permutaciones de prior deterministas: "
        "A (Sin memoria) \u00b7 B (Historial) \u00b7 C (Memoria asociativa).</text>",
    ]

    fn = escape_xml(
        "Esquema: tres grupos de tareas en tres fases y tres condiciones evaluadas en seis permutaciones. "
        "Regenerar: python -m scripts.paper_figures"
    )
    svg_lines.append(f'  <text x="40" y="{height - 15}" font-size="10" fill="{COLOR_MUTED}">{fn}</text>')
    svg_lines.append("</svg>\n")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    write_utf8_lf(output_file, "\n".join(svg_lines))


def generate_fig7_memory_cycle_schema(output_file: Path) -> None:
    """Genera Fig 7: Esquema metodológico del ciclo de memoria y operadores."""
    width = 800
    height = 420

    fn_msg = escape_xml(
        "Esquema ilustrativo del bucle de aprendizaje. Regenerar: python -m scripts.paper_figures"
    )
    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" font-family="system-ui, -apple-system, sans-serif">',
        f'  <rect width="{width}" height="{height}" fill="{COLOR_BG}"/>',
        f'  <text x="40" y="40" font-size="16" font-weight="700" fill="{COLOR_TEXT}">'
        "Figura 7: Esquema del ciclo de memoria y operadores del solver determinista</text>",
        '  <rect x="40" y="55" width="410" height="24" fill="#fef3c7" stroke="#f59e0b" rx="3"/>',
        '  <text x="48" y="71" font-size="11" font-weight="700" fill="#b45309">'
        "ESQUEMA METODOLÓGICO (NO ES RESULTADO EXPERIMENTAL)</text>",
        f'  <rect x="50" y="130" width="140" height="70" fill="#f1f5f9" stroke="{COLOR_BORDER}" rx="5"/>',
        f'  <text x="120" y="160" font-size="12" font-weight="700" text-anchor="middle" '
        f'fill="{COLOR_TEXT}">1. Entrada</text>',
        f'  <text x="120" y="180" font-size="10" text-anchor="middle" fill="{COLOR_MUTED}">'
        "Issue / Excepción</text>",
        '  <rect x="240" y="130" width="140" height="70" fill="#e0f2fe" stroke="#7dd3fc" rx="5"/>',
        f'  <text x="310" y="160" font-size="12" font-weight="700" text-anchor="middle" '
        f'fill="{COLOR_TEXT}">2. Recuperación</text>',
        f'  <text x="310" y="180" font-size="10" text-anchor="middle" fill="{COLOR_MUTED}">'
        "Similitud léxica</text>",
        '  <rect x="430" y="130" width="140" height="70" fill="#fef08a" stroke="#facc15" rx="5"/>',
        '  <text x="500" y="160" font-size="12" font-weight="700" text-anchor="middle" '
        'fill="#854d0e">3. Actuación</text>',
        f'  <text x="500" y="180" font-size="10" text-anchor="middle" fill="{COLOR_MUTED}">'
        "3 operadores AST</text>",
        '  <rect x="610" y="130" width="140" height="70" fill="#dcfce7" stroke="#86efac" rx="5"/>',
        '  <text x="680" y="160" font-size="12" font-weight="700" text-anchor="middle" '
        'fill="#15803d">4. Verificación</text>',
        f'  <text x="680" y="180" font-size="10" text-anchor="middle" fill="{COLOR_MUTED}">'
        "Test pass / fail</text>",
        '  <rect x="330" y="260" width="160" height="60" fill="#f3e8ff" stroke="#d8b4fe" rx="5"/>',
        '  <text x="410" y="285" font-size="12" font-weight="700" text-anchor="middle" '
        'fill="#6b21a8">5. Registro / Grafo</text>',
        f'  <text x="410" y="303" font-size="10" text-anchor="middle" fill="{COLOR_MUTED}">'
        "Lección (éxito) / Fallo</text>",
        f'  <line x1="190" y1="165" x2="230" y2="165" stroke="{COLOR_MUTED}" stroke-width="2"/>',
        f'  <line x1="380" y1="165" x2="420" y2="165" stroke="{COLOR_MUTED}" stroke-width="2"/>',
        f'  <line x1="570" y1="165" x2="600" y2="165" stroke="{COLOR_MUTED}" stroke-width="2"/>',
        f'  <path d="M 680 200 L 680 290 L 500 290" fill="none" stroke="{COLOR_MUTED}" stroke-width="2"/>',
        f'  <path d="M 330 290 L 120 290 L 120 210" fill="none" stroke="{COLOR_MUTED}" stroke-width="2"/>',
        f'  <text x="40" y="{height - 15}" font-size="10" fill="{COLOR_MUTED}">{fn_msg}</text>',
        "</svg>\n",
    ]

    output_file.parent.mkdir(parents=True, exist_ok=True)
    write_utf8_lf(output_file, "\n".join(svg_lines))


# ==============================================================================
# PIPELINE COMPLETO
# ==============================================================================


def generate_all(
    results_dir: Path,
    figures_dir: Path,
    tables_dir: Path,
) -> dict[str, Path]:
    """Genera todas las figuras y tablas desde los resultados agregados."""
    figures_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)

    artifacts: dict[str, Path] = {}

    # Fig 1 & Tabla 1
    f1 = figures_dir / "fig1_first_attempt_h4.svg"
    t1 = tables_dir / "table1_h4_first_attempt.md"
    c1 = generate_fig1_h4_first_attempt(results_dir, f1)
    generate_table1_h4_markdown(c1, t1)
    artifacts["fig1"] = f1
    artifacts["table1"] = t1

    # Fig 2 & Tabla 2
    f2 = figures_dir / "fig2_lesson_attribution_map.svg"
    t2 = tables_dir / "table2_misleading_attribution.md"
    c2 = generate_fig2_lesson_attribution(results_dir, f2)
    generate_table2_misleading_markdown(c2, t2)
    artifacts["fig2"] = f2
    artifacts["table2"] = t2

    # Fig 3 & Tabla 3
    f3 = figures_dir / "fig3_attempts_distribution.svg"
    t3 = tables_dir / "table3_attempts_distribution.md"
    c3 = generate_fig3_attempts_distribution(results_dir, f3)
    generate_table3_attempts_markdown(c3, t3)
    artifacts["fig3"] = f3
    artifacts["table3"] = t3

    # Fig 4 & Tabla 4
    f4 = figures_dir / "fig4_h7_failure_transfer.svg"
    t4 = tables_dir / "table4_h7_tau_pairs.md"
    c4 = generate_fig4_h7_failure_transfer(results_dir, f4)
    generate_table4_h7_markdown(c4, t4)
    artifacts["fig4"] = f4
    artifacts["table4"] = t4

    # Fig 5 & Tabla 5
    f5 = figures_dir / "fig5_diagnostic_baseline_diff.svg"
    t5 = tables_dir / "table5_diagnostic_family_breakdown.md"
    c5 = generate_fig5_diagnostic_baseline(results_dir, f5)
    generate_table5_diagnostic_markdown(c5, t5)
    artifacts["fig5"] = f5
    artifacts["table5"] = t5

    # Fig 6 & Fig 7 (Esquemas metodológicos)
    f6 = figures_dir / "fig6_experimental_design.svg"
    f7 = figures_dir / "fig7_memory_cycle.svg"
    generate_fig6_experimental_design_schema(f6)
    generate_fig7_memory_cycle_schema(f7)
    artifacts["fig6"] = f6
    artifacts["fig7"] = f7

    return artifacts


def main(argv: list[str] | None = None) -> int:
    """CLI para regenerar figuras y tablas."""
    parser = argparse.ArgumentParser(
        description="Genera figuras SVG y tablas Markdown reproducibles desde results/ para el paper."
    )
    repo_root = Path(__file__).resolve().parent.parent
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=repo_root / "results",
        help="Directorio raíz de agregados results/",
    )
    parser.add_argument(
        "--figures-dir",
        type=Path,
        default=repo_root / "docs" / "paper" / "figures",
        help="Directorio de destino de figuras SVG",
    )
    parser.add_argument(
        "--tables-dir",
        type=Path,
        default=repo_root / "docs" / "paper" / "tables",
        help="Directorio de destino de tablas Markdown",
    )

    args = parser.parse_args(argv)
    generate_all(args.results_dir, args.figures_dir, args.tables_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
