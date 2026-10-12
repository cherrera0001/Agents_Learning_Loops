"""Líneas base de fallo contadas desde los episodios (``devlog base-rates``, #167).

Solo lectura y solo cuenta: no predice, no lee GitHub y no cambia el ranking de ``recall``. Lo que no
esté en ``learning/episodes/`` (CI, veredictos de revisión) no se cuenta y la salida lo dice.

Tres tablas:

- por acción: pasos, pasos fallidos, fracción e intervalo de Wilson al 95 %;
- por clase de fallo, con la clasificación declarada en ``learning/failure_classes.json`` (expresiones
  regulares sin distinguir mayúsculas sobre ``error`` y ``note`` del paso; cada paso fallido cae en la
  primera clase, en el orden del archivo, cuya expresión casa) y la cuenta de pasos fallidos sin clase;
- por tercios de la historia (episodios ordenados por ``seq``, partidos en tres grupos consecutivos).

``--hasta N`` excluye el episodio ``N`` y los posteriores, para que una línea base no use información
posterior a la predicción.
"""

from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CLASSES_PATH = ROOT / "learning" / "failure_classes.json"
Z95 = 1.96
NOT_COUNTABLE = (
    "no contable desde los episodios: resultado de la CI, veredicto de la revisión independiente y "
    "cualquier hecho que un episodio no registre"
)


def wilson(failed: int, total: int, z: float = Z95) -> tuple[float, float] | None:
    """Intervalo de Wilson de una proporción; ``None`` si no hay observaciones."""
    if total <= 0:
        return None
    p = failed / total
    denom = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def _rate(failed: int, total: int) -> dict[str, Any]:
    ci = wilson(failed, total)
    return {
        "failed": failed,
        "total": total,
        "rate": None if total == 0 else failed / total,
        "ci95": None if ci is None else [ci[0], ci[1]],
    }


def load_classes(path: Path = CLASSES_PATH) -> list[tuple[str, list[re.Pattern[str]]]]:
    data = json.loads(path.read_text("utf-8"))
    classes: list[tuple[str, list[re.Pattern[str]]]] = []
    for entry in data["classes"]:
        patterns = [re.compile(p, re.IGNORECASE) for p in entry["patterns"]]
        classes.append((str(entry["name"]), patterns))
    return classes


def load_caveat(path: Path = CLASSES_PATH) -> str:
    """Aviso sobre el uso de la tabla por clase, escrito en el archivo de clases."""
    return str(json.loads(path.read_text("utf-8")).get("caveat", ""))


def step_text(step: Mapping[str, Any]) -> str:
    return "\n".join(str(step[k]) for k in ("error", "note") if step.get(k))


def matching_classes(
    step: Mapping[str, Any], classes: Sequence[tuple[str, Sequence[re.Pattern[str]]]]
) -> list[str]:
    """Todas las clases cuyo patrón casa con el paso, en el orden del archivo."""
    text = step_text(step)
    return [name for name, patterns in classes if any(p.search(text) for p in patterns)]


def classify(step: Mapping[str, Any], classes: Sequence[tuple[str, Sequence[re.Pattern[str]]]]) -> str | None:
    matched = matching_classes(step, classes)
    return matched[0] if matched else None


def select(episodes: Sequence[Mapping[str, Any]], hasta: int | None) -> list[Mapping[str, Any]]:
    """Episodios ordenados por ``seq``; con ``hasta`` se excluye ese episodio y los posteriores."""
    chosen = sorted(episodes, key=lambda e: e["seq"])
    if hasta is not None:
        chosen = [e for e in chosen if e["seq"] < hasta]
    seqs = Counter(e["seq"] for e in chosen)
    repeated = sorted(seq for seq, n in seqs.items() if n > 1)
    if repeated:
        # Sale con error en vez de contar: «en N episodios» fundiría dos episodios con el mismo seq.
        raise ValueError(f"seq repetido en los episodios: {repeated}")
    return chosen


def _steps(episodes: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [s for e in episodes for s in e["steps"]]


def thirds(episodes: Sequence[Mapping[str, Any]]) -> list[list[Mapping[str, Any]]]:
    n = len(episodes)
    return [list(episodes[i * n // 3 : (i + 1) * n // 3]) for i in range(3)]


def compute(
    episodes: Sequence[Mapping[str, Any]],
    classes: Sequence[tuple[str, Sequence[re.Pattern[str]]]],
    hasta: int | None = None,
) -> dict[str, Any]:
    chosen = select(episodes, hasta)
    steps = _steps(chosen)
    failed_steps = [s for s in steps if not s["success"]]

    totals: Counter[str] = Counter(s["action"] for s in steps)
    fails: Counter[str] = Counter(s["action"] for s in failed_steps)
    by_action = [
        {"action": a, **_rate(fails[a], totals[a])} for a in sorted(totals, key=lambda a: (-fails[a], a))
    ]

    class_steps: Counter[str] = Counter()
    class_episodes: dict[str, set[int]] = {name: set() for name, _ in classes}
    unclassified = 0
    several = 0
    for e in chosen:
        for s in e["steps"]:
            if s["success"]:
                continue
            matched = matching_classes(s, classes)
            several += len(matched) > 1
            name = matched[0] if matched else None
            if name is None:
                unclassified += 1
            else:
                class_steps[name] += 1
                class_episodes[name].add(e["seq"])
    by_class = [
        {
            "class": name,
            **_rate(class_steps[name], len(failed_steps)),
            "episodes": len(class_episodes[name]),
        }
        for name, _ in classes
    ]

    by_third = []
    for i, group in enumerate(thirds(chosen), start=1):
        gsteps = _steps(group)
        gfailed = sum(1 for s in gsteps if not s["success"])
        by_third.append(
            {
                "third": i,
                "episodes": len(group),
                "seq_from": group[0]["seq"] if group else None,
                "seq_to": group[-1]["seq"] if group else None,
                **_rate(gfailed, len(gsteps)),
            }
        )

    return {
        "hasta": hasta,
        "episodes": len(chosen),
        "steps": len(steps),
        "failed_steps": len(failed_steps),
        "by_action": by_action,
        "by_class": by_class,
        "unclassified": _rate(unclassified, len(failed_steps)),
        "failed_matching_several_classes": several,
        "by_third": by_third,
        "not_countable": NOT_COUNTABLE,
    }


def _pct(rate: float | None) -> str:
    return "-" if rate is None else f"{rate * 100:.1f}%"


def _ci(ci: Sequence[float] | None) -> str:
    return "-" if ci is None else f"{ci[0] * 100:.1f}% a {ci[1] * 100:.1f}%"


def format_report(result: Mapping[str, Any]) -> str:
    limit = "" if result["hasta"] is None else f" (episodios con seq < {result['hasta']})"
    lines = [
        f"Líneas base de fallo{limit}: {result['episodes']} episodios, {result['steps']} pasos, "
        f"{result['failed_steps']} fallidos",
        "",
        "Por acción (pasos fallidos / pasos; intervalo de Wilson al 95 %):",
    ]
    for r in result["by_action"]:
        lines.append(
            f"  {r['action']:<20} {r['failed']:>3} / {r['total']:<3} {_pct(r['rate']):>7}  {_ci(r['ci95'])}"
        )
    lines += ["", "Por clase de fallo (pasos fallidos de la clase / todos los fallidos):"]
    for c in result["by_class"]:
        lines.append(
            f"  {c['class']:<44} {c['failed']:>3} / {c['total']:<3} {_pct(c['rate']):>7}  "
            f"{_ci(c['ci95'])}  en {c['episodes']} episodios"
        )
    u = result["unclassified"]
    lines.append(
        f"  {'sin clase':<44} {u['failed']:>3} / {u['total']:<3} {_pct(u['rate']):>7}  {_ci(u['ci95'])}"
    )
    lines.append(
        f"  {result['failed_matching_several_classes']} de {result['failed_steps']} pasos fallidos casan "
        "con más de una clase; decide el orden del archivo."
    )
    if result.get("class_caveat"):
        lines.append(f"  AVISO: {result['class_caveat']}")
    lines += ["", "Por tercios de la historia (pasos fallidos / pasos):"]
    for t in result["by_third"]:
        span = "-" if t["seq_from"] is None else f"{t['seq_from']}-{t['seq_to']}"
        lines.append(
            f"  tercio {t['third']} (episodios {span}, {t['episodes']}) "
            f"{t['failed']:>3} / {t['total']:<3} {_pct(t['rate']):>7}  {_ci(t['ci95'])}"
        )
    lines += ["", f"Nota: {result['not_countable']}."]
    return "\n".join(lines)


def run_base_rates(
    episodes: Sequence[Mapping[str, Any]],
    hasta: int | None = None,
    as_json: bool = False,
    classes_path: Path = CLASSES_PATH,
) -> int:
    """Imprime las tres tablas (o JSON). Salida 0; 2 si el archivo de clases no se puede leer o hay
    episodios con el mismo ``seq``."""
    try:
        classes = load_classes(classes_path)
    except (OSError, ValueError, KeyError, TypeError, re.error) as exc:
        print(f"error: no se pudo leer la clasificación {classes_path}: {exc}", file=sys.stderr)
        return 2
    try:
        result = compute(episodes, classes, hasta)
        result["class_caveat"] = load_caveat(classes_path)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(format_report(result))
    return 0


def add_arguments(parser: Any) -> None:
    parser.add_argument("--hasta", type=int, help="excluye este episodio (seq) y los posteriores")
    parser.add_argument("--json", action="store_true", help="la misma cuenta en JSON")
    parser.add_argument(
        "--clases",
        type=Path,
        default=CLASSES_PATH,
        help="archivo de clases de fallo (por defecto learning/failure_classes.json)",
    )
