"""Lectura del piloto de estimación por comando (solo lectura; no interpreta).

Calcula las medidas de ``docs/piloto-estimacion.md`` sobre los issues **cerrados** con número
``>= since`` (y ``<= until`` si se da), cerrados como COMPLETED y sin épicas. La lógica es una
**función pura** (:func:`compute_measures`): recibe issues, tarjetas, episodios y, opcionalmente,
el uso de tokens por issue; devuelve las medidas como datos (numerador, denominador, detalle).
:func:`format_report` las pasa a una tabla Markdown. Una capa fina lee el tablero con las funciones
de :mod:`scripts.board_check` (``gh`` o instantánea) y las transcripciones locales de Claude Code.

Reglas de lectura:

- Denominador 0: «sin datos», nunca «0 %». Con menos de 8 en el denominador no se imprime
  porcentaje, solo «n de m».
- El episodio de un issue es el que lo cita primero en su ``ref``; si hay varios, se suman los
  pasos y se toma el ``outcome`` del de mayor ``seq`` que lo tenga.
- Tokens: de cada ``message.id`` de la transcripción se toma el **último** uso (el mismo id se
  repite en varias líneas con uso creciente). Se asigna por ``outcome.transcript`` del episodio o
  por ``--map <issue>=<archivo>``, que prevalece. Son transcripciones locales: no incluyen la
  revisión del orquestador ni son una factura.
- Una lectura fallida (cuenta que no ve el Project, instantánea incompleta) termina con código 2;
  una salida normal termina con 0: el comando cuenta, no juzga.

Uso::

    python -m scripts.devlog pilot --since 76
    python -m scripts.devlog pilot --since 76 --until 79 --snapshot <dir>
    python -m scripts.devlog pilot --since 76 --transcripts <dir> --map 77=agent-xxx.jsonl
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

from scripts.board_check import (
    EPIC_LABEL,
    BoardReadError,
    Runner,
    _run_gh,
    cited_issues,
    read_github,
    read_snapshot,
)

MIN_RATE_DENOMINATOR = 8
NO_DATA = "sin datos"
NOT_MEASURED = "no medido"
NOT_FOUND = "transcripción no encontrada"
SIZE_ORDER = ("XS", "S", "M", "L", "XL")
ESTIMATE_FIELDS = ("talla", "puntos", "incertidumbre", "riesgo")
_ISSUE_REF = re.compile(r"#(\d+)(?!\w)")


# --- Tokens ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class TokenUsage:
    input: int = 0
    cache_creation: int = 0
    cache_read: int = 0
    output: int = 0
    models: frozenset[str] = frozenset()
    skipped_lines: int = 0


def _count(usage: Mapping[str, Any], key: str) -> int:
    value = usage.get(key)
    return value if isinstance(value, int) else 0


def parse_transcript(lines: Sequence[str]) -> TokenUsage:
    """Suma el último ``usage`` de cada ``message.id`` de un JSONL de Claude Code."""
    last: dict[str, Mapping[str, Any]] = {}
    models: set[str] = set()
    skipped = 0
    for raw in lines:
        if not raw.strip():
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            skipped += 1
            continue
        message = obj.get("message") if isinstance(obj, dict) else None
        if not isinstance(message, dict):
            continue
        usage = message.get("usage")
        message_id = message.get("id")
        if not isinstance(usage, dict) or not isinstance(message_id, str):
            continue
        last[message_id] = usage
        if isinstance(message.get("model"), str):
            models.add(message["model"])
    totals = list(last.values())
    return TokenUsage(
        input=sum(_count(u, "input_tokens") for u in totals),
        cache_creation=sum(_count(u, "cache_creation_input_tokens") for u in totals),
        cache_read=sum(_count(u, "cache_read_input_tokens") for u in totals),
        output=sum(_count(u, "output_tokens") for u in totals),
        models=frozenset(models),
        skipped_lines=skipped,
    )


# --- Datos de la lectura -----------------------------------------------------------------------


@dataclass(frozen=True)
class Measure:
    name: str
    numerator: int
    denominator: int
    detail: str = ""
    rate: bool = True  # False: nunca se imprime como porcentaje (sumas, pasos)


@dataclass(frozen=True)
class TokenRow:
    issue: int
    size: str
    usage: TokenUsage | None  # None: transcripción no encontrada


@dataclass(frozen=True)
class PilotReport:
    population: tuple[int, ...]
    measures: tuple[Measure, ...]
    tokens: tuple[TokenRow, ...] | None  # None: no se pidió --transcripts


def _label_names(labels: Any) -> set[str]:
    return {x["name"] if isinstance(x, Mapping) else str(x) for x in labels or []}


def _blank(value: Any) -> bool:
    return value is None or value == ""


def _board(cards: Sequence[Mapping[str, Any]]) -> dict[int, Mapping[str, Any]]:
    board: dict[int, Mapping[str, Any]] = {}
    for card in cards:
        content = card.get("content") or {}
        number = content.get("number")
        if number is None or content.get("type", "Issue") != "Issue":
            continue
        board[int(number)] = card
    return board


def select_population(
    issues: Sequence[Mapping[str, Any]],
    cards: Sequence[Mapping[str, Any]],
    since: int,
    until: int | None = None,
) -> list[int]:
    """Issues cerrados como COMPLETED con ``since <= n <= until``, sin épicas."""
    board = _board(cards)
    out = []
    for issue in issues:
        n = int(issue["number"])
        card = board.get(n, {})
        epic = EPIC_LABEL in _label_names(issue.get("labels")) | _label_names(card.get("labels"))
        if (
            n >= since
            and (until is None or n <= until)
            and issue.get("state") == "CLOSED"
            and issue.get("stateReason") == "COMPLETED"
            and not epic
        ):
            out.append(n)
    return sorted(set(out))


def primary_issue(ref: str) -> int | None:
    """Primer ``#n`` citado como issue en ``ref`` (el issue principal del episodio)."""
    cited = cited_issues(ref)
    for m in _ISSUE_REF.finditer(ref):
        if int(m[1]) in cited:
            return int(m[1])
    return None


@dataclass(frozen=True)
class IssueEpisode:
    steps: tuple[Mapping[str, Any], ...]
    outcome: Mapping[str, Any] | None


def episodes_by_issue(episodes: Sequence[Mapping[str, Any]]) -> dict[int, IssueEpisode]:
    grouped: dict[int, list[Mapping[str, Any]]] = {}
    for ep in sorted(episodes, key=lambda e: e.get("seq", 0)):
        n = primary_issue(str(ep.get("ref", "")))
        if n is not None:
            grouped.setdefault(n, []).append(ep)
    result = {}
    for n, eps in grouped.items():
        steps = tuple(s for ep in eps for s in ep.get("steps", []))
        outcomes = [ep["outcome"] for ep in eps if isinstance(ep.get("outcome"), Mapping)]
        result[n] = IssueEpisode(steps, outcomes[-1] if outcomes else None)
    return result


def transcript_names(
    population: Sequence[int],
    episodes: Sequence[Mapping[str, Any]],
    mapping: Mapping[int, str] | None = None,
) -> dict[int, str]:
    """Archivo declarado por issue: ``--map`` prevalece sobre ``outcome.transcript``."""
    by_issue = episodes_by_issue(episodes)
    names: dict[int, str] = {}
    for n in population:
        ep = by_issue.get(n)
        declared = ep.outcome.get("transcript") if ep and ep.outcome else None
        if isinstance(declared, str) and declared:
            names[n] = declared
    names.update({n: f for n, f in (mapping or {}).items() if n in population})
    return names


# --- Medidas (función pura) --------------------------------------------------------------------


def _issues_text(numbers: Sequence[int]) -> str:
    return ", ".join(f"#{n}" for n in numbers)


def compute_measures(
    issues: Sequence[Mapping[str, Any]],
    cards: Sequence[Mapping[str, Any]],
    episodes: Sequence[Mapping[str, Any]],
    tokens: Mapping[int, TokenUsage | None] | None = None,
    since: int = 0,
    until: int | None = None,
) -> PilotReport:
    """Calcula las medidas del piloto; no toca red ni disco.

    ``tokens=None`` significa «no medido»; con un diccionario, las claves son los issues con
    transcripción declarada y ``None`` marca una transcripción no encontrada.
    """
    population = select_population(issues, cards, since, until)
    board = _board(cards)
    by_issue = episodes_by_issue(episodes)

    def card(n: int) -> Mapping[str, Any]:
        return board.get(n, {})

    def share(name: str, eligible: Sequence[int], hit: Sequence[int], rate: bool = True) -> Measure:
        return Measure(name, len(hit), len(eligible), _issues_text(hit), rate)

    complete = [n for n in population if not any(_blank(card(n).get(f)) for f in ESTIMATE_FIELDS)]
    done = [n for n in population if card(n).get("status") == "Done"]
    verified = [n for n in done if card(n).get("verificación") == "Verificada"]
    escalation_known = [n for n in population if not _blank(card(n).get("escaló"))]
    escalated = [n for n in escalation_known if card(n).get("escaló") == "Sí"]
    both = [
        n for n in population if not _blank(card(n).get("modelo")) and not _blank(card(n).get("modelo usado"))
    ]
    differ = [n for n in both if card(n)["modelo"] != card(n)["modelo usado"]]
    with_outcome = [n for n in population if n in by_issue and by_issue[n].outcome is not None]

    def outcome(n: int) -> Mapping[str, Any]:
        found = by_issue[n].outcome
        assert found is not None
        return found

    extra_prs = {n: int(outcome(n).get("prs", 1)) - 1 for n in with_outcome}
    revisions = {n: int(outcome(n).get("estimate_revisions", 0)) for n in with_outcome}
    from_transcript = [n for n in with_outcome if outcome(n).get("model_source") == "transcript"]

    measures = [
        share("Estimación completa en el tablero", population, complete),
        share("Done con Verificación = Verificada", done, verified),
        share("Escalamientos (Escaló = Sí)", escalation_known, escalated),
        share("Modelo previsto distinto del usado", both, differ),
        Measure(
            "PR adicionales (outcome.prs − 1)",
            sum(extra_prs.values()),
            len(with_outcome),
            ", ".join(f"#{n}: {v}" for n, v in extra_prs.items() if v),
            rate=False,
        ),
        Measure(
            "Revisiones de estimación",
            sum(revisions.values()),
            len(with_outcome),
            ", ".join(f"#{n}: {v}" for n, v in revisions.items() if v),
            rate=False,
        ),
        share("model_source = transcript", with_outcome, from_transcript),
    ]

    sizes: dict[str, list[int]] = {}
    for n in population:
        size = card(n).get("talla")
        if not _blank(size) and n in by_issue:
            sizes.setdefault(str(size), []).append(n)
    for size in sorted(sizes, key=lambda s: (SIZE_ORDER.index(s) if s in SIZE_ORDER else 99, s)):
        steps = [s for n in sizes[size] for s in by_issue[n].steps]
        failed = [s for s in steps if s.get("success") is False]
        per_issue = [
            (n, sum(s.get("success") is False for s in by_issue[n].steps), len(by_issue[n].steps))
            for n in sizes[size]
        ]
        detail = ", ".join(f"#{n}: {f} de {t}" for n, f, t in per_issue)
        measures.append(
            Measure(f"Pasos fallidos, talla {size} (autoinformado)", len(failed), len(steps), detail, False)
        )
    if not sizes:
        measures.append(Measure("Pasos fallidos por talla (autoinformado)", 0, 0, "", False))

    rows: tuple[TokenRow, ...] | None = None
    if tokens is not None:
        rows = tuple(
            TokenRow(n, str(card(n).get("talla") or "—"), tokens[n]) for n in population if n in tokens
        )
    return PilotReport(tuple(population), tuple(measures), rows)


# --- Formato -----------------------------------------------------------------------------------


def format_result(m: Measure) -> str:
    if m.denominator == 0:
        return NO_DATA
    text = f"{m.numerator} de {m.denominator}"
    if m.rate and m.denominator >= MIN_RATE_DENOMINATOR:
        text += f" ({100 * m.numerator / m.denominator:.0f} %)"
    return text


def _thousands(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def format_report(report: PilotReport) -> str:
    listed = _issues_text(report.population) or "ninguno"
    lines = [
        f"Población (n = {len(report.population)}): {listed}",
        "",
        "| Medida | Numerador | Denominador | Resultado | Detalle |",
        "|---|---|---|---|---|",
    ]
    for m in report.measures:
        lines.append(f"| {m.name} | {m.numerator} | {m.denominator} | {format_result(m)} | {m.detail} |")
    lines += ["", "Tokens por issue (transcripciones locales; no incluyen la revisión del orquestador):", ""]
    if report.tokens is None:
        lines += ["| Issue | Estado |", "|---|---|", f"| tokens | {NOT_MEASURED} |"]
    elif not report.tokens:
        lines += ["| Issue | Estado |", "|---|---|", f"| tokens | {NO_DATA} |"]
    else:
        lines += [
            "| Issue | Talla | Entrada | Escritura de caché | Lectura de caché | Salida | Modelos |",
            "|---|---|---|---|---|---|---|",
        ]
        for row in report.tokens:
            u = row.usage
            if u is None:
                lines.append(f"| #{row.issue} | {row.size} | {NOT_FOUND} | | | | |")
                continue
            models = ", ".join(sorted(u.models)) or "—"
            if u.skipped_lines:
                models += f" (líneas ilegibles: {u.skipped_lines})"
            lines.append(
                f"| #{row.issue} | {row.size} | {_thousands(u.input)} | {_thousands(u.cache_creation)} "
                f"| {_thousands(u.cache_read)} | {_thousands(u.output)} | {models} |"
            )
    return "\n".join(lines)


# --- Lectura y ejecución -----------------------------------------------------------------------


def parse_map(entries: Sequence[str]) -> dict[int, str]:
    """``77=agent-x.jsonl`` -> ``{77: "agent-x.jsonl"}``; ``ValueError`` si no tiene esa forma."""
    mapping: dict[int, str] = {}
    for entry in entries:
        number, sep, name = entry.partition("=")
        if not sep or not number.strip().isdigit() or not name.strip():
            raise ValueError(f"--map espera <issue>=<archivo>, recibió {entry!r}")
        mapping[int(number)] = name.strip()
    return mapping


def read_usage(directory: Path, name: str) -> TokenUsage | None:
    path = directory / name
    if not path.is_file():
        return None
    return parse_transcript(path.read_text("utf-8-sig").splitlines())


def run_pilot(
    *,
    since: int,
    until: int | None = None,
    snapshot: Path | None,
    episodes: Sequence[Mapping[str, Any]],
    transcripts: Path | None = None,
    mapping: Mapping[int, str] | None = None,
    runner: Runner = _run_gh,
    out: TextIO | None = None,
    err: TextIO | None = None,
) -> int:
    """Lee, calcula e imprime. Devuelve 0, o 2 si no se pudo leer la fuente."""
    out = out or sys.stdout
    err = err or sys.stderr
    try:
        if snapshot is not None:
            items, issues, _ = read_snapshot(snapshot)
        else:
            items, issues, _ = read_github(runner)
    except BoardReadError as exc:
        print(f"error: no se pudo leer la fuente: {exc}", file=err)
        return 2
    tokens: dict[int, TokenUsage | None] | None = None
    if transcripts is not None:
        population = select_population(issues, items, since, until)
        names = transcript_names(population, episodes, mapping)
        tokens = {n: read_usage(transcripts, name) for n, name in names.items()}
    print(format_report(compute_measures(issues, items, episodes, tokens, since, until)), file=out)
    return 0


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--since", type=int, required=True, help="primer issue de la población (piloto: 76)")
    parser.add_argument("--until", type=int, help="último issue de la población (opcional)")
    parser.add_argument("--snapshot", type=Path, help="directorio con items.json e issues.json en vez de gh")
    parser.add_argument(
        "--transcripts",
        type=Path,
        help="directorio con transcripciones JSONL de Claude Code; añade los tokens por issue",
    )
    parser.add_argument(
        "--map",
        action="append",
        default=[],
        metavar="ISSUE=ARCHIVO",
        help="transcripción de un issue (prevalece sobre outcome.transcript); repetible",
    )
