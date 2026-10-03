"""Chequeo de solo lectura que cruza issues, tablero (Project #5) y episodios.

La lógica es una **función pura** (:func:`check_board`): recibe issues, tarjetas y
episodios ya leídos y devuelve los hallazgos ordenados; no toca red ni disco. Una
capa fina lee los datos con ``gh`` (:func:`read_github`) o de una instantánea
(:func:`read_snapshot`); :func:`run_board` los une e imprime. Nunca escribe en el
tablero ni en los issues.

Reglas (``--since`` limita las reglas 2 a 4 a los issues con número >= ``since``):

1. Issue cerrado con tarjeta fuera de *Done*, o tarjeta en *Done* con issue abierto.
2. Tarjeta en *In Progress* o *Done* sin *Talla*, *Puntos*, *Incertidumbre* o *Riesgo*
   (las épicas no se estiman).
3. Tarjeta en *Done* sin *Verificación* = Verificada, sin *Modelo usado* o sin *Escaló*
   (a las épicas solo se les exige *Verificación*).
4. Issue cerrado como completado sin episodio cuyo ``ref`` cite ``#<n>`` (las épicas
   quedan excluidas). Solo cuenta ``#n`` suelto: ni ``PR #n``, ni ``otro/repo#n``, ni
   ``#nn``; un rango ``#24-#36`` cita solo sus extremos.
5. Episodio con bloque ``estimate`` cuyo ``size`` difiere de la *Talla* del tablero del
   issue que cita su ``ref``.
6. Épica cerrada con subissues abiertos (necesita los subissues; sin ellos se informa
   «no evaluada»).
7. Episodio con ``estimate.planned_model`` distinto de *Modelo* de la tarjeta del issue
   principal (primero citado en ``ref``). Campo vacío o sin tarjeta: no hay hallazgo.
8. Episodio con ``outcome.used_model`` distinto de *Modelo usado*, o ``outcome.escalated``
   distinto de *Escaló* (`true` ↔ `"Sí"`, `false` ↔ `"No"`), en el issue principal.
   Campo vacío o sin tarjeta: no hay hallazgo.
9. Issue con número >= ``since`` sin tarjeta en el tablero (incluye épicas).
10. Lectura truncada de subissues: si alguna épica devuelve el tope (50 subissues),
   el comando sale con código 2 en vez de evaluar la regla 6. Solo aplica a la lectura
   por ``gh``; ``--snapshot`` no consulta subissues y no la evalúa.

Las reglas 1 a 8 y 10 salen de :func:`check_board`; la 9 es la función pura aparte
:func:`check_missing_cards`, que :func:`run_board` suma a los hallazgos.

Códigos de salida: 0 sin hallazgos, 1 con hallazgos, 2 si no se pudo leer la fuente.
Nunca se informa «sin hallazgos» si la lectura falló.

Uso::

    python -m scripts.devlog board --since 76
    python -m scripts.devlog board --snapshot tests/fixtures/board-2026-10-02
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

OWNER = "cherrera0001"
REPO = "cherrera0001/Agents_Learning_Loops"
PROJECT_NUMBER = 5
ITEM_LIMIT = 1000
LIMIT = ("--limit", str(ITEM_LIMIT))
ISSUE_FIELDS = "number,state,stateReason,title,labels,closedAt"
ESTIMATE_FIELDS = ("talla", "puntos", "incertidumbre", "riesgo")
EPIC_LABEL = "epic"
SUBISSUES_LIMIT = 50

Runner = Callable[[Sequence[str]], "subprocess.CompletedProcess[str]"]


class BoardReadError(Exception):
    """No se pudo leer la fuente: el chequeo no puede decir nada (código 2)."""


@dataclass(frozen=True, order=True)
class Finding:
    rule: int
    issue: int
    message: str

    def line(self) -> str:
        return f"R{self.rule} #{self.issue}: {self.message}"


_CITE = re.compile(r"(?P<pre>[\w./-]*)#(?P<n>\d+)(?!\w)")
_PR_BEFORE = re.compile(r"\bPR[\s:]*$", re.IGNORECASE)


def cited_issues(ref: str) -> set[int]:
    """Números de issue citados como ``#n`` suelto en el texto libre de ``ref``."""
    return set(cited_issues_ordered(ref))


def cited_issues_ordered(ref: str) -> list[int]:
    """Números de issue citados como ``#n`` suelto, en orden de aparición y sin duplicados."""
    found: list[int] = []
    seen: set[int] = set()
    for m in _CITE.finditer(ref):
        if m["pre"].strip("-"):  # otro/repo#7, word#7
            continue
        if _PR_BEFORE.search(ref[: m.start()]):  # PR #66 no es el issue 66
            continue
        n = int(m["n"])
        if n not in seen:
            found.append(n)
            seen.add(n)
    return found


def _label_names(labels: Iterable[Any] | None) -> set[str]:
    return {x["name"] if isinstance(x, Mapping) else str(x) for x in labels or []}


def _blank(value: Any) -> bool:
    return value is None or value == ""


def _index_cards(cards: Sequence[Mapping[str, Any]], repo: str | None) -> dict[int, Mapping[str, Any]]:
    """Tarjetas de issues de ``repo`` indexadas por número de issue."""
    board: dict[int, Mapping[str, Any]] = {}
    for card in cards:
        content = card.get("content") or {}
        number = content.get("number")
        if number is None or content.get("type", "Issue") != "Issue":
            continue
        if repo is not None and content.get("repository", repo) != repo:
            continue
        board[int(number)] = card
    return board


def check_board(
    issues: Sequence[Mapping[str, Any]],
    cards: Sequence[Mapping[str, Any]],
    episodes: Sequence[Mapping[str, Any]],
    subissues: Mapping[int, Sequence[Mapping[str, Any]]] | None = None,
    since: int | None = None,
    repo: str | None = REPO,
) -> list[Finding]:
    """Aplica las reglas 1 a 8; devuelve los hallazgos ordenados por (regla, issue, mensaje).

    ``since=None`` desactiva las reglas 2 a 4. ``subissues=None`` desactiva la regla 6.
    La regla 9 vive en :func:`check_missing_cards`.
    """
    by_number = {int(i["number"]): i for i in issues}
    epics = {n for n, i in by_number.items() if EPIC_LABEL in _label_names(i.get("labels"))}
    board = _index_cards(cards, repo)
    epics |= {n for n, card in board.items() if EPIC_LABEL in _label_names(card.get("labels"))}

    def in_scope(n: int) -> bool:
        return since is not None and n >= since

    out: list[Finding] = []
    for n, card in board.items():
        status = card.get("status")
        issue = by_number.get(n)
        if issue is not None:
            state = issue.get("state")
            if state == "CLOSED" and status != "Done":
                out.append(Finding(1, n, f"issue cerrado con la tarjeta en {status or 'sin estado'}"))
            elif state == "OPEN" and status == "Done":
                out.append(Finding(1, n, "tarjeta en Done con el issue abierto"))
        if not in_scope(n):
            continue
        epic = n in epics
        if status in ("In Progress", "Done") and not epic:
            missing = [f for f in ESTIMATE_FIELDS if _blank(card.get(f))]
            if missing:
                out.append(Finding(2, n, f"tarjeta en {status} sin {', '.join(missing)}"))
        if status == "Done":
            problems = []
            if card.get("verificación") != "Verificada":
                problems.append(f"Verificación = {card.get('verificación') or 'vacía'}, no Verificada")
            if not epic:
                problems += [
                    f"sin {f.capitalize()}" for f in ("modelo usado", "escaló") if _blank(card.get(f))
                ]
            if problems:
                out.append(Finding(3, n, "tarjeta en Done: " + "; ".join(problems)))

    cites: dict[int, list[str]] = {}
    for ep in episodes:
        for n in cited_issues(str(ep.get("ref", ""))):
            cites.setdefault(n, []).append(str(ep.get("id", ep.get("seq"))))

    for n, issue in by_number.items():
        if (
            in_scope(n)
            and issue.get("state") == "CLOSED"
            and issue.get("stateReason") == "COMPLETED"
            and n not in epics
            and n not in cites
        ):
            out.append(Finding(4, n, "issue cerrado como completado sin episodio cuyo ref lo cite"))

    for ep in episodes:
        estimate = ep.get("estimate")
        size = estimate.get("size") if isinstance(estimate, Mapping) else None
        if size is None:
            continue
        for n in sorted(cited_issues(str(ep.get("ref", "")))):
            talla = board.get(n, {}).get("talla")
            if talla is not None and talla != size:
                out.append(Finding(5, n, f"episodio {ep.get('id')} estima {size}; el tablero dice {talla}"))

    if subissues is not None:
        for n in sorted(epics):
            if by_number.get(n, {}).get("state") != "CLOSED":
                continue
            open_subs = sorted(int(s["number"]) for s in subissues.get(n, []) if s.get("state") == "OPEN")
            if open_subs:
                listed = ", ".join(f"#{s}" for s in open_subs)
                out.append(Finding(6, n, f"épica cerrada con subissues abiertos: {listed}"))

    # Regla 7: Modelo previsto sobrescrito
    for ep in episodes:
        estimate = ep.get("estimate")
        planned_model = estimate.get("planned_model") if isinstance(estimate, Mapping) else None
        if planned_model is None:
            continue
        cited = cited_issues_ordered(str(ep.get("ref", "")))
        if not cited:
            continue
        principal = cited[0]
        card = board.get(principal)
        if card is None:
            continue
        modelo = card.get("modelo")
        if not _blank(modelo) and modelo != planned_model:
            msg = f"episodio {ep.get('id')} preveía {planned_model}; el tablero dice {modelo}"
            out.append(Finding(7, principal, msg))

    # Regla 8: Resultado incoherente
    for ep in episodes:
        outcome = ep.get("outcome")
        if not isinstance(outcome, Mapping):
            continue
        cited = cited_issues_ordered(str(ep.get("ref", "")))
        if not cited:
            continue
        principal = cited[0]
        card = board.get(principal)
        if card is None:
            continue
        problems = []
        used_model = outcome.get("used_model")  # clave ausente: el episodio no declara, no se compara
        modelo_usado = card.get("modelo usado")
        if not _blank(used_model) and not _blank(modelo_usado) and modelo_usado != used_model:
            problems.append(f"Modelo usado: episodio {used_model}, tablero {modelo_usado}")
        escalated = outcome.get("escalated")
        escaló = card.get("escaló")
        escalated_str = "Sí" if escalated is True else "No" if escalated is False else None
        if escalated_str is not None and not _blank(escaló) and escaló != escalated_str:
            problems.append(f"Escaló: episodio {escalated_str}, tablero {escaló}")
        if problems:
            out.append(Finding(8, principal, "resultado incoherente: " + "; ".join(problems)))

    return sorted(out)


def check_missing_cards(
    issues: Sequence[Mapping[str, Any]],
    cards: Sequence[Mapping[str, Any]],
    since: int | None,
    repo: str | None = REPO,
) -> list[Finding]:
    """Regla 9: issues con número >= ``since`` sin tarjeta (incluye épicas). ``since=None``: ninguno."""
    if since is None:
        return []
    board = _index_cards(cards, repo)
    numbers = sorted({int(i["number"]) for i in issues})
    return [
        Finding(9, n, "issue sin tarjeta en el tablero") for n in numbers if n >= since and n not in board
    ]


def not_evaluated(since: int | None, subissues: object | None) -> list[str]:
    """Reglas que no se pudieron evaluar con los datos recibidos (para avisarlo)."""
    notes = []
    if since is None:
        notes.append("reglas 2, 3 y 4 no evaluadas: falta --since")
    if subissues is None:
        notes.append("regla 6 no evaluada: no hay datos de subissues")
    return notes


# --- Lectura -----------------------------------------------------------------------------


def _run_gh(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8", check=False)
    except FileNotFoundError as exc:
        raise BoardReadError("gh no está instalado o no está en el PATH") from exc


def _json(text: str, what: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise BoardReadError(f"{what}: JSON inválido ({exc})") from exc


def _items_payload(data: Any, what: str) -> list[dict[str, Any]]:
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise BoardReadError(f"{what}: falta la clave 'items'")
    items: list[dict[str, Any]] = data["items"]
    total = data.get("totalCount")
    if isinstance(total, int) and total > len(items):
        raise BoardReadError(f"{what}: lectura incompleta ({len(items)} de {total} tarjetas)")
    return items


def _issues_payload(data: Any, what: str, limit: int | None = None) -> list[dict[str, Any]]:
    if not isinstance(data, list):
        raise BoardReadError(f"{what}: se esperaba una lista de issues")
    if limit is not None and len(data) >= limit:
        raise BoardReadError(f"{what}: posible lectura truncada ({len(data)} issues, límite {limit})")
    return data


def _subissues_payload(data: Any, what: str) -> dict[int, list[dict[str, Any]]]:
    if not isinstance(data, dict):
        raise BoardReadError(f"{what}: se esperaba un objeto {{épica: [subissues]}}")
    return {int(k): list(v) for k, v in data.items()}


_EPICS_QUERY = (
    f"query($o:String!,$r:String!){{repository(owner:$o,name:$r){{"
    f'issues(first:100,labels:["epic"]){{nodes{{number state '
    f"subIssues(first:{SUBISSUES_LIMIT}){{nodes{{number state}}}}}}}}}}}}"
)


def read_snapshot(directory: Path) -> tuple[Any, Any, dict[int, list[dict[str, Any]]] | None]:
    """Lee ``items.json`` e ``issues.json`` (y ``subissues.json`` si existe)."""

    def load(name: str, required: bool) -> Any:
        path = directory / name
        if not path.is_file():
            if required:
                raise BoardReadError(f"instantánea incompleta: falta {path}")
            return None
        return _json(path.read_text("utf-8-sig"), str(path))

    items = _items_payload(load("items.json", True), str(directory / "items.json"))
    issues = _issues_payload(load("issues.json", True), str(directory / "issues.json"))
    raw = load("subissues.json", False)
    subs = None if raw is None else _subissues_payload(raw, str(directory / "subissues.json"))
    return items, issues, subs


def cards_from_snapshot(directory: Path) -> dict[int, Mapping[str, Any]]:
    """Tarjetas de una instantánea del tablero, indexadas por número de issue."""
    items, _issues, _subs = read_snapshot(directory)
    return _index_cards(items, None)


def read_github(runner: Runner = _run_gh) -> tuple[Any, Any, dict[int, list[dict[str, Any]]]]:
    """Lee el tablero, los issues y los subissues de las épicas con ``gh``."""

    def gh(args: Sequence[str], what: str) -> str:
        proc = runner(args)
        if proc.returncode != 0:
            raise BoardReadError(f"{what}: gh falló ({proc.stderr.strip() or 'sin mensaje'})")
        return proc.stdout

    login = gh(["api", "user", "--jq", ".login"], "no se pudo comprobar la cuenta de gh").strip()
    raw_items = gh(
        ["project", "item-list", str(PROJECT_NUMBER), "--owner", OWNER, *LIMIT, "--format", "json"],
        f"la cuenta {login!r} no ve el Project #{PROJECT_NUMBER} de {OWNER} (exporta GH_TOKEN de {OWNER})",
    )
    items = _items_payload(_json(raw_items, "gh project item-list"), "gh project item-list")
    raw_issues = gh(
        ["issue", "list", "--repo", REPO, "--state", "all", *LIMIT, "--json", ISSUE_FIELDS],
        "gh issue list",
    )
    issues = _issues_payload(_json(raw_issues, "gh issue list"), "gh issue list", ITEM_LIMIT)
    owner, name = REPO.split("/")
    raw_epics = gh(
        ["api", "graphql", "-f", f"query={_EPICS_QUERY}", "-F", f"o={owner}", "-F", f"r={name}"],
        "gh api graphql (subissues de las épicas)",
    )
    nodes = _json(raw_epics, "gh api graphql")["data"]["repository"]["issues"]["nodes"]
    subs = {}
    for n in nodes:
        epic_num = int(n["number"])
        sub_list = list(n["subIssues"]["nodes"])
        if len(sub_list) >= SUBISSUES_LIMIT:
            raise BoardReadError(
                f"épica #{epic_num}: lectura truncada ({len(sub_list)} subissues, límite {SUBISSUES_LIMIT})"
            )
        subs[epic_num] = sub_list
    return items, issues, subs


def run_board(
    *,
    since: int | None,
    snapshot: Path | None,
    episodes: Sequence[Mapping[str, Any]],
    runner: Runner = _run_gh,
    out: TextIO | None = None,
    err: TextIO | None = None,
) -> int:
    """Lee, comprueba e imprime. Devuelve el código de salida (0, 1 o 2)."""
    out = out or sys.stdout
    err = err or sys.stderr
    try:
        if snapshot is not None:
            items, issues, subs = read_snapshot(snapshot)
        else:
            if since is None:
                raise BoardReadError("--since es obligatorio al leer de GitHub")
            items, issues, subs = read_github(runner)
    except BoardReadError as exc:
        print(f"error: no se pudo leer la fuente: {exc}", file=err)
        return 2
    findings = sorted(
        check_board(issues, items, episodes, subs, since) + check_missing_cards(issues, items, since)
    )
    for note in not_evaluated(since, subs):
        print(f"aviso: {note}", file=err)
    if since is None:
        print("aviso: regla 9 no evaluada: falta --since", file=err)
    for f in findings:
        print(f.line(), file=out)
    if not findings:
        print("sin hallazgos", file=out)
    return 1 if findings else 0
