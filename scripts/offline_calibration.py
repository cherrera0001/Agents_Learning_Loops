"""Calibración offline de η_h, α y τ_seed reproduciendo los episodios de la bitácora.

Replay **online** y fiel al ciclo del agente (§5 del README) sobre los episodios de
``learning/episodes/``: por cada episodio, ``RETRIEVE(goal)`` → medir → consolidar con la
activación del retrieve → añadir sus lecciones. La etiqueta causal de cada fallo es la clase de
``learning/failure_classes.json`` (primer patrón que case, en el orden del archivo); el análisis
nunca lee ``benchmark/private/`` (sus etiquetas indexan las tareas del Experimento 1, no estos
episodios). Definiciones exactas y reglas de selección/decisión: pre-registro
``docs/preregistration/offline-calibration.md``, commit antes de cualquier corrida.

Uso::

    python -m scripts.offline_calibration run --output results/offline-calibration-v1
    python -m scripts.offline_calibration report --aggregates results/offline-calibration-v1/aggregates.json

``run`` escribe ``aggregates.json`` (generado, no editado a mano) y es determinista: mismos
episodios y mismo código ⇒ mismos bytes.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import random
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from associative_agent_loop.agent.tools import ToolResult
from associative_agent_loop.memory.associative import RetrievalConfig, Retriever
from associative_agent_loop.memory.consolidation import Consolidator
from associative_agent_loop.memory.graph import MemoryGraph, NodeType
from scripts.base_rates import classify, load_classes, wilson
from scripts.devlog import load_episodes, visible_lessons

ROOT = Path(__file__).resolve().parent.parent
EPISODES_DIR = ROOT / "learning" / "episodes"
CLASSES_PATH = ROOT / "learning" / "failure_classes.json"
PREREGISTRATION_PATH = "docs/preregistration/offline-calibration.md"

ETA_H_GRID = (0.1, 0.3, 0.5)
ALPHA_GRID = (0.5, 0.7, 0.9)
TAU_SEED_GRID = (0.1, 0.25, 0.4)
DEFAULT_CONFIG = {"eta_h": 0.3, "alpha": 0.7, "tau_seed": 0.25}
DECISION_THRESHOLD_PP = 5.0
TOP_LESSONS = 5
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 7

Classes = Sequence[tuple[str, Sequence[re.Pattern[str]]]]


def classify_text(text: str, classes: Classes) -> str | None:
    """Primera clase, en el orden del archivo, cuyo patrón case con el texto (regex sin mayúsculas)."""
    for name, patterns in classes:
        if any(p.search(text) for p in patterns):
            return name
    return None


def split_windows(
    episodes: Sequence[Mapping[str, Any]], calibrate_frac: float
) -> tuple[list[Mapping[str, Any]], list[Mapping[str, Any]]]:
    """Partición temporal por ``seq``: los primeros ``int(n·frac)`` episodios calibran, el resto valida."""
    ordered = sorted(episodes, key=lambda e: e["seq"])
    n_cal = int(len(ordered) * calibrate_frac)
    if not 1 <= n_cal <= len(ordered) - 1:
        raise ValueError(
            f"fracción de calibración {calibrate_frac} deja {n_cal} episodios de calibración "
            f"sobre {len(ordered)}: se exige al menos 1 por ventana"
        )
    return list(ordered[:n_cal]), list(ordered[n_cal:])


def _lesson_labels(mg: MemoryGraph) -> list[str]:
    return [
        node.label
        for node in mg.nodes()
        if node.type == NodeType.CONCEPT and node.metadata.get("kind") == "lesson"
    ]


def replay(
    episodes: Sequence[Mapping[str, Any]],
    classes: Classes,
    eta_h: float,
    alpha: float,
    tau_seed: float,
) -> list[dict[str, Any]]:
    """Replay online; devuelve una fila por paso fallido, medida **antes** de consolidar el episodio."""
    mg = MemoryGraph()
    consolidator = Consolidator(mg, hebbian_rate=eta_h)
    retriever = Retriever(mg, config=RetrievalConfig(alpha=alpha, min_seed_similarity=tau_seed))
    rows: list[dict[str, Any]] = []
    for ep in episodes:
        actions = [node.label for node in mg.nodes() if node.type == NodeType.ACTION]
        result = retriever.retrieve(str(ep["goal"]), [a for a in actions])
        shown, _ = visible_lessons(mg, result.activation, TOP_LESSONS)
        known_classes = {
            name for label in _lesson_labels(mg) if (name := classify_text(label, classes)) is not None
        }
        shown_classes = {name for label in shown if (name := classify_text(label, classes)) is not None}
        for i, step in enumerate(ep["steps"]):
            if step.get("success"):
                continue
            cause = classify(step, classes)
            known = cause is not None and cause in known_classes
            hit = known and cause in shown_classes
            rows.append(
                {
                    "seq": ep["seq"],
                    "step": i,
                    "action": step["action"],
                    "class": cause,
                    "known": known,
                    "hit_visible": hit,
                    "repeated": known and not hit,
                }
            )
        episode_id = mg.tick()
        goal = consolidator.record_goal(str(ep["goal"]), episode_id)
        recorded = []
        for i, step in enumerate(ep["steps"]):
            tool_result = ToolResult(bool(step["success"]), output=step.get("note"), error=step.get("error"))
            consolidator.record_step(goal, step["action"], tool_result, episode_id, i)
            recorded.append((step["action"], tool_result))
        consolidator.consolidate_episode(goal, recorded, result.activation)
        for lesson in ep.get("lessons", []):
            consolidator.add_lesson(goal, lesson)
    return rows


def _rate(failed: int, total: int) -> dict[str, Any]:
    ci = wilson(failed, total)
    return {
        "failed": failed,
        "total": total,
        "rate": None if total == 0 else failed / total,
        "ci95": None if ci is None else [ci[0], ci[1]],
    }


def summarize(rows: Sequence[Mapping[str, Any]], n_episodes: int) -> dict[str, Any]:
    failures = list(rows)
    unclassified = sum(1 for r in failures if r["class"] is None)
    known = [r for r in failures if r["known"]]
    repeated = [r for r in failures if r["repeated"]]
    return {
        "episodes": n_episodes,
        "failures": len(failures),
        "unclassified": _rate(unclassified, len(failures)),
        "known_cause": len(known),
        "repeated_known_cause": _rate(len(repeated), len(known)),
        "repeated_all_failures": _rate(len(repeated), len(failures)),
    }


def grid() -> list[dict[str, float]]:
    return [
        {"eta_h": eta_h, "alpha": alpha, "tau_seed": tau_seed}
        for eta_h in ETA_H_GRID
        for alpha in ALPHA_GRID
        for tau_seed in TAU_SEED_GRID
    ]


def select_best(configs: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
    """Menor tasa primaria en calibración; desempates: sensibilidad, |η_h−0.3|, |α−0.7|, |τ_seed−0.25|."""

    def key(cfg: Mapping[str, Any]) -> tuple[float, float, float, float, float]:
        cal = cfg["windows"]["calibration"]
        sens = cal["repeated_all_failures"]["rate"]
        prim = cal["repeated_known_cause"]["rate"]
        return (
            float("inf") if prim is None else prim,
            float("inf") if sens is None else sens,
            abs(cfg["eta_h"] - DEFAULT_CONFIG["eta_h"]),
            abs(cfg["alpha"] - DEFAULT_CONFIG["alpha"]),
            abs(cfg["tau_seed"] - DEFAULT_CONFIG["tau_seed"]),
        )

    return min(configs, key=key)


def _paired_validation_rows(
    default_rows: Sequence[Mapping[str, Any]], best_rows: Sequence[Mapping[str, Any]]
) -> list[tuple[Mapping[str, Any], Mapping[str, Any]]]:
    """Filas de validación conocidas pareadas por (seq, step) entre default y ganadora."""
    best_by_key = {(r["seq"], r["step"]): r for r in best_rows if r["window"] == "validation"}
    paired = []
    for row in default_rows:
        if row["window"] != "validation" or not row["known"]:
            continue
        other = best_by_key.get((row["seq"], row["step"]))
        if other is not None and other["known"]:
            paired.append((row, other))
    return paired


def compare(
    default_rows: Sequence[Mapping[str, Any]],
    best_rows: Sequence[Mapping[str, Any]],
    resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    """Diferencia pareada (default − ganadora) en puntos porcentuales sobre validación, con IC bootstrap."""
    paired = _paired_validation_rows(default_rows, best_rows)
    b = sum(1 for d, _ in paired if d["repeated"])
    c = sum(1 for _, w in paired if w["repeated"])
    default_rate = b / len(paired) if paired else None
    best_rate = c / len(paired) if paired else None
    delta_pp = None if default_rate is None or best_rate is None else (default_rate - best_rate) * 100
    rng = random.Random(seed)
    deltas: list[float] = []
    seqs = sorted({d["seq"] for d, _ in paired})
    by_seq: dict[int, list[tuple[Mapping[str, Any], Mapping[str, Any]]]] = {
        s: [p for p in paired if p[0]["seq"] == s] for s in seqs
    }
    for _ in range(resamples):
        sample = [by_seq[s] for s in rng.choices(seqs, k=len(seqs))]
        flat = [p for group in sample for p in group]
        if not flat:
            continue
        d_rate = sum(1 for d, _ in flat if d["repeated"]) / len(flat)
        w_rate = sum(1 for _, w in flat if w["repeated"]) / len(flat)
        deltas.append((d_rate - w_rate) * 100)
    ci = None
    if deltas:
        ordered = sorted(deltas)
        lo = ordered[max(0, int(0.025 * len(ordered)))]
        hi = ordered[min(len(ordered) - 1, int(0.975 * len(ordered)))]
        ci = [lo, hi]
    return {
        "paired_known_cause_failures": len(paired),
        "default_repeated": b,
        "calibrated_repeated": c,
        "default_rate": default_rate,
        "calibrated_rate": best_rate,
        "delta_pp": delta_pp,
        "delta_ci95": ci,
        "mcnemar": {"repeated_only_default": b, "repeated_only_calibrated": c},
        "bootstrap": {"resamples": resamples, "seed": seed},
    }


def decide(delta_pp: float | None, threshold_pp: float = DECISION_THRESHOLD_PP) -> bool:
    """Regla pre-registrada: se recomienda la config calibrada solo si Δ ≥ threshold (puntos porcentuales)."""
    return delta_pp is not None and delta_pp >= threshold_pp


def _git_commit(path: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%h", "--", path],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.stdout.strip() or None


def run_calibration(
    episodes: Sequence[Mapping[str, Any]],
    classes: Classes,
    calibrate_frac: float = 0.7,
    classes_caveat: str = "",
) -> dict[str, Any]:
    calibrate, validate = split_windows(episodes, calibrate_frac)
    calibrate_seqs = {e["seq"] for e in calibrate}
    configs: list[dict[str, Any]] = []
    for params in grid():
        # Una sola replay online por config: la memoria de validación es la que dejó la calibración.
        rows = replay(list(calibrate) + list(validate), classes, **params)
        for row in rows:
            row["window"] = "calibration" if row["seq"] in calibrate_seqs else "validation"
        cal_rows = [r for r in rows if r["window"] == "calibration"]
        val_rows = [r for r in rows if r["window"] == "validation"]
        configs.append(
            {
                **params,
                "is_default": params == DEFAULT_CONFIG,
                "windows": {
                    "calibration": summarize(cal_rows, len(calibrate)),
                    "validation": summarize(val_rows, len(validate)),
                },
                "failures": rows,
            }
        )
    winner = select_best(configs)
    default = next(c for c in configs if c["is_default"])
    comparison = compare(default["failures"], winner["failures"])
    return {
        "schema": "offline-calibration-v1",
        "code_commit": _git_commit("."),
        "pre_registration": {"path": PREREGISTRATION_PATH, "commit": _git_commit(PREREGISTRATION_PATH)},
        "episodes": len(calibrate) + len(validate),
        "split": {
            "calibrate_frac": calibrate_frac,
            "n_calibrate": len(calibrate),
            "n_validate": len(validate),
            "calibrate_seq": [calibrate[0]["seq"], calibrate[-1]["seq"]],
            "validate_seq": [validate[0]["seq"], validate[-1]["seq"]],
        },
        "decision_threshold_pp": DECISION_THRESHOLD_PP,
        "classes_caveat": classes_caveat,
        "configs": configs,
        "selection": {
            "rule": "menor RepeatedFailureRate primario en calibración; desempates: sensibilidad, "
            "|η_h−0.3|, |α−0.7|, |τ_seed−0.25|",
            "winner": {k: winner[k] for k in ("eta_h", "alpha", "tau_seed")},
            "winner_calibration_rate": winner["windows"]["calibration"]["repeated_known_cause"]["rate"],
            "winner_validation_rate": winner["windows"]["validation"]["repeated_known_cause"]["rate"],
        },
        "comparison": {
            "default": {k: default[k] for k in ("eta_h", "alpha", "tau_seed")},
            "calibrated": {k: winner[k] for k in ("eta_h", "alpha", "tau_seed")},
            "validation": comparison,
            "decision": {
                "recommended": decide(comparison["delta_pp"]),
                "threshold_pp": DECISION_THRESHOLD_PP,
                "note": "La recomendación no cambia los defaults: la decisión es del dueño.",
            },
        },
    }


def _pct(rate: float | None) -> str:
    return "-" if rate is None else f"{rate * 100:.1f}%"


def _ci(ci: Sequence[float] | None) -> str:
    return "-" if ci is None else f"{ci[0] * 100:.1f}–{ci[1] * 100:.1f} %"


def _rate_cell(block: Mapping[str, Any]) -> str:
    return f"{_pct(block['rate'])} ({block['failed']}/{block['total']}; IC95 {_ci(block['ci95'])})"


def format_report(aggregates: Mapping[str, Any]) -> str:
    lines = [
        "# Calibración offline de η_h, α y τ_seed (agregado generado)",
        "",
        f"Pre-registro: {aggregates['pre_registration']['path']} "
        f"(commit {aggregates['pre_registration']['commit']})",
        f"Código: commit {aggregates['code_commit']}. "
        f"{aggregates['episodes']} episodios; calibración "
        f"{aggregates['split']['calibrate_seq'][0]}..{aggregates['split']['calibrate_seq'][1]} "
        f"({aggregates['split']['n_calibrate']}), validación "
        f"{aggregates['split']['validate_seq'][0]}..{aggregates['split']['validate_seq'][1]} "
        f"({aggregates['split']['n_validate']}).",
        "",
        "## Denominadores por ventana",
        "",
        "| Ventana | Config | Episodios | Fallos | Sin clase | Causa conocida | Rep./conoc. | Rep./todos |",
        "|---|---|---|---|---|---|---|---|",
    ]
    seen: set[tuple[str, str]] = set()
    for cfg in aggregates["configs"]:
        for window in ("calibration", "validation"):
            m = cfg["windows"][window]
            key = (window, f"{cfg['eta_h']}/{cfg['alpha']}/{cfg['tau_seed']}")
            if key in seen:
                continue
            seen.add(key)
            uncl = m["unclassified"]
            lines.append(
                f"| {window} | η_h={cfg['eta_h']} α={cfg['alpha']} τ={cfg['tau_seed']} "
                f"{'(default)' if cfg['is_default'] else ''} | {m['episodes']} | {m['failures']} | "
                f"{uncl['failed']}/{uncl['total']} ({_pct(uncl['rate'])}) | {m['known_cause']} | "
                f"{_rate_cell(m['repeated_known_cause'])} | {_rate_cell(m['repeated_all_failures'])} |"
            )
    lines += ["", "## Comparación (validación)", ""]
    comp = aggregates["comparison"]
    val = comp["validation"]
    delta = "-" if val["delta_pp"] is None else f"{val['delta_pp']:.1f} pp"
    ci = val["delta_ci95"]
    ci_txt = "-" if ci is None else f"[{ci[0]:.1f}, {ci[1]:.1f}] pp"
    lines += [
        f"- Default η_h={comp['default']['eta_h']} α={comp['default']['alpha']} "
        f"τ={comp['default']['tau_seed']}: {_pct(val['default_rate'])} ({val['default_repeated']}/"
        f"{val['paired_known_cause_failures']})",
        f"- Ganadora η_h={comp['calibrated']['eta_h']} α={comp['calibrated']['alpha']} "
        f"τ={comp['calibrated']['tau_seed']}: {_pct(val['calibrated_rate'])} ({val['calibrated_repeated']}/"
        f"{val['paired_known_cause_failures']}); en calibración: "
        f"{_pct(aggregates['selection']['winner_calibration_rate'])}",
        f"- Δ (default − ganadora): {delta}; IC95 bootstrap {ci_txt}",
        f"- McNemar: solo default {val['mcnemar']['repeated_only_default']}, solo ganadora "
        f"{val['mcnemar']['repeated_only_calibrated']}",
        f"- Decisión (umbral {comp['decision']['threshold_pp']:.0f} pp): "
        + (
            "RECOMENDADA" if comp["decision"]["recommended"] else "NO recomendada — se conservan los defaults"
        ),
        "",
        f"Caveat de las clases: {aggregates['classes_caveat']}",
    ]
    return "\n".join(lines)


def cmd_run(args: argparse.Namespace) -> int:
    episodes = load_episodes(args.episodes_dir)
    try:
        classes = load_classes(args.clases)
    except (OSError, ValueError, KeyError, TypeError, re.error) as exc:
        print(f"error: no se pudo leer la clasificación {args.clases}: {exc}", file=sys.stderr)
        return 2
    caveat = ""
    with contextlib.suppress(OSError, ValueError):
        caveat = str(json.loads(CLASSES_PATH.read_text("utf-8")).get("caveat", ""))
    aggregates = run_calibration(episodes, classes, calibrate_frac=args.calibrate_frac, classes_caveat=caveat)
    out_dir: Path = args.output
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "aggregates.json"
    target.write_text(json.dumps(aggregates, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    shown = target.relative_to(ROOT) if target.is_relative_to(ROOT) else target
    print(f"{shown}: {len(episodes)} episodios, {len(aggregates['configs'])} configs")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    try:
        aggregates = json.loads(Path(args.aggregates).read_text("utf-8"))
    except (OSError, ValueError) as exc:
        print(f"error: no se pudo leer {args.aggregates}: {exc}", file=sys.stderr)
        return 2
    print(format_report(aggregates))
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run", help="corre el grid y escribe aggregates.json")
    p_run.add_argument("--output", type=Path, required=True, help="directorio de salida")
    p_run.add_argument(
        "--episodes-dir",
        type=Path,
        default=EPISODES_DIR,
        help="directorio de episodios (default learning/episodes)",
    )
    p_run.add_argument("--calibrate-frac", type=float, default=0.7)
    p_run.add_argument("--clases", type=Path, default=CLASSES_PATH)
    p_report = sub.add_parser("report", help="imprime el informe desde aggregates.json")
    p_report.add_argument("--aggregates", type=Path, required=True)
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(cmd_run(args) if args.cmd == "run" else cmd_report(args))


if __name__ == "__main__":
    main()
