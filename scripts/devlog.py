"""Bitácora de aprendizaje del propio repositorio (*dogfooding*).

Cada issue trabajado es un episodio en ``learning/episodes/*.json``. El grafo
``learning/dev_memory.json`` se deriva de ellos de forma determinista (no se versiona: está en
``.gitignore``), y antes de empezar un issue se consulta con ``recall``, que reconstruye el grafo
en memoria desde los episodios.

Uso::

    python -m scripts.devlog recall "texto del issue"
    python -m scripts.devlog recall "texto del issue" --snapshot tests/fixtures/board-2026-10-02
    python -m scripts.devlog rebuild
    python -m scripts.devlog board --since 76        # chequeo de solo lectura (ver board_check)
    python -m scripts.devlog pilot --since 76        # lectura del piloto (ver pilot_metrics)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from associative_agent_loop.agent.tools import ToolResult
from associative_agent_loop.memory.associative import Retriever
from associative_agent_loop.memory.consolidation import Consolidator
from associative_agent_loop.memory.embeddings import Embedder, FastEmbedEmbedder
from associative_agent_loop.memory.graph import MemoryGraph, NodeType
from scripts.board_check import cited_issues_ordered

ROOT = Path(__file__).resolve().parent.parent
EPISODES_DIR = ROOT / "learning" / "episodes"
MEMORY_PATH = ROOT / "learning" / "dev_memory.json"


def load_episodes(episodes_dir: Path = EPISODES_DIR) -> list[dict[str, Any]]:
    episodes = [json.loads(p.read_text("utf-8")) for p in episodes_dir.glob("*.json")]
    return sorted(episodes, key=lambda e: e["seq"])


_FOREIGN_REF = re.compile(r"[\w.-]+/[\w.-]+#\d+")


def board_record(ep: Mapping[str, Any]) -> dict[str, Any]:
    """Lo que el tablero registra del issue de un episodio: estimación, resultado y pasos.

    ``estimate`` y ``outcome`` copian los campos del Project #5 (talla, puntos, incertidumbre, riesgo y
    modelo previsto; modelo usado, escaló y PR). Va en el nodo ``Goal`` para que ``recall`` pueda decir
    cómo se estimó y cómo salió un issue parecido (#122).
    """
    steps = ep.get("steps", [])
    ref = str(ep.get("ref", ""))
    # Un ``ref`` que cita otro repositorio (``dueño/repo#n``) no es de un issue de este tablero:
    # sus ``#n`` sueltos pueden ser PR o issues ajenos, así que no se atribuye ninguno.
    issues = [] if _FOREIGN_REF.search(ref) else cited_issues_ordered(ref)
    return {
        "issue": issues[0] if issues else None,
        "estimate": ep.get("estimate"),
        "outcome": ep.get("outcome"),
        "steps": len(steps),
        "failed_steps": sum(1 for step in steps if not step.get("success")),
    }


def rebuild(episodes: list[dict[str, Any]]) -> MemoryGraph:
    """Reproduce los episodios en orden de ``seq`` sobre una memoria vacía."""
    mg = MemoryGraph()
    consolidator = Consolidator(mg)
    for ep in sorted(episodes, key=lambda e: e["seq"]):
        episode_id = mg.tick()
        goal = consolidator.record_goal(ep["goal"], episode_id)
        mg.node(goal).metadata["ref"] = ep["id"]
        mg.node(goal).metadata["board"] = board_record(ep)
        steps = []
        for i, step in enumerate(ep["steps"]):
            result = ToolResult(step["success"], output=step.get("note"), error=step.get("error"))
            consolidator.record_step(goal, step["action"], result, episode_id, i)
            steps.append((step["action"], result))
        consolidator.consolidate_episode(goal, steps)
        for lesson in ep.get("lessons", []):
            consolidator.add_lesson(goal, lesson)
    return mg


def _shown(value: Any) -> str:
    """Un dato del episodio tal cual, o ``?`` si falta: la línea no afirma lo que el dato no dice."""
    return "?" if value is None or value == "" else str(value)


def _issue_line(
    mg: MemoryGraph, goal: str, activation: float, cards: Mapping[int, Mapping[str, Any]] | None
) -> str:
    node = mg.node(goal)
    board = node.metadata["board"]
    issue = board.get("issue")
    estimate, outcome = board.get("estimate") or {}, board.get("outcome") or {}
    parts = [f"activación {activation:.2f}"]
    if estimate:
        planned = estimate.get("planned_model")
        parts.append(
            f"estimado {_shown(estimate.get('size'))} · {_shown(estimate.get('points'))} pts, "
            f"I{_shown(estimate.get('uncertainty'))} R{_shown(estimate.get('risk'))}, "
            # la cadena vacía es un dato: issue de un agente que no es Claude, sin modelo previsto
            f"previsto {'ninguno' if planned == '' else _shown(planned)} "
            "(declarado en episodio; no leído de tarjeta)"
        )
    else:
        parts.append("episodio sin estimación")
    if outcome:
        escalated = outcome.get("escalated")
        parts.append(
            f"usado {_shown(outcome.get('used_model'))}, "
            f"escaló: {'sí' if escalated is True else 'no' if escalated is False else '?'}, "
            f"PR: {_shown(outcome.get('prs'))}, "
            f"revisiones de estimación: {_shown(outcome.get('estimate_revisions'))} "
            "(declarado en episodio; no leído de tarjeta)"
        )
    else:
        parts.append("episodio sin resultado")
    parts.append(f"pasos fallidos {board.get('failed_steps', 0)}/{board.get('steps', 0)}")
    if cards is not None and issue is not None:
        card = cards.get(int(issue))
        if card is None:
            parts.append("tablero: sin tarjeta")
        else:
            status, verified = card.get("status") or "sin estado", card.get("verificación") or "vacía"
            parts.append(f"tablero: {status}, verificación {verified} (snapshot)")
            discrepancies = _snapshot_discrepancies(estimate, outcome, card)
            if discrepancies:
                parts.append("discrepancias episodio/snapshot: " + ", ".join(discrepancies))
    name = f"#{issue}" if issue is not None else node.metadata.get("ref", goal)
    return f"  {name} ({node.metadata.get('ref', goal)}): " + "; ".join(parts)


def _snapshot_discrepancies(
    estimate: Mapping[str, Any], outcome: Mapping[str, Any], card: Mapping[str, Any]
) -> list[str]:
    """Compara los valores declarados en el episodio con los campos presentes en la tarjeta."""
    comparisons = [
        ("estimate.size", estimate.get("size"), "talla", card.get("talla")),
        ("estimate.points", estimate.get("points"), "puntos", card.get("puntos")),
        ("estimate.uncertainty", estimate.get("uncertainty"), "incertidumbre", card.get("incertidumbre")),
        ("estimate.risk", estimate.get("risk"), "riesgo", card.get("riesgo")),
        ("estimate.planned_model", estimate.get("planned_model"), "modelo", card.get("modelo")),
        ("outcome.used_model", outcome.get("used_model"), "modelo usado", card.get("modelo usado")),
        ("outcome.escalated", _escalated_label(outcome.get("escalated")), "escaló", card.get("escaló")),
    ]
    linked_prs = card.get("linked pull requests")
    if isinstance(linked_prs, list):
        comparisons.append(("outcome.prs", outcome.get("prs"), "PR vinculados", len(linked_prs)))
    return [
        f"{source}={_shown(episode_value)}; {target}={_shown(snapshot_value)}"
        for source, episode_value, target, snapshot_value in comparisons
        if episode_value is not None and snapshot_value is not None and episode_value != snapshot_value
    ]


def _escalated_label(value: Any) -> str | None:
    if value is True:
        return "Sí"
    if value is False:
        return "No"
    return None


def similar_issues(
    mg: MemoryGraph,
    activation: Mapping[str, float],
    top: int = 3,
    cards: Mapping[int, Mapping[str, Any]] | None = None,
) -> list[str]:
    """Líneas con la estimación y el resultado de los episodios más activados por la consulta.

    Son episodios, no issues: dos episodios del mismo issue salen en dos líneas. No hay umbral de
    parecido; cada línea muestra su activación para que quien lee juzgue cuánto se parece.
    """
    goals = set(mg.nodes_of_type(NodeType.GOAL))
    ranked = sorted(
        ((a, n) for n, a in activation.items() if n in goals and "board" in mg.node(n).metadata),
        key=lambda pair: (-pair[0], pair[1]),
    )
    return [_issue_line(mg, goal, a, cards) for a, goal in ranked[: max(top, 0)]]


def recall(
    mg: MemoryGraph,
    query: str,
    top_lessons: int = 5,
    embedder: Embedder | None = None,
    cards: Mapping[int, Mapping[str, Any]] | None = None,
    top_issues: int = 3,
) -> str:
    actions = [mg.node(n).label for n in mg.nodes_of_type(NodeType.ACTION)]
    result = Retriever(mg, embedder=embedder).retrieve(query, actions)
    lines = [f"RETRIEVE: {query!r}", "", "Acciones (score = relevancia · valencia):"]
    lines += [
        f"  {s.score:+.3f}  {s.action}  (rel={s.relevance:.2f}, val={s.valence:+.2f})"
        for s in result.ranked_actions
        if s.relevance > 0
    ] or ["  (sin experiencia relacionada)"]
    lines += ["", "Lecciones:"]
    lines += [f"  - {lesson}" for lesson in result.lessons[:top_lessons]] or ["  (ninguna)"]
    lines += ["", "Issues parecidos (cómo se estimaron y cómo salieron):"]
    lines += similar_issues(mg, result.activation, top_issues, cards) or ["  (ninguno)"]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_recall = sub.add_parser("recall", help="consulta la memoria antes de empezar un issue")
    p_recall.add_argument("query")
    p_recall.add_argument("-n", type=int, default=5, help="máximo de lecciones")
    p_recall.add_argument(
        "--embedder",
        choices=["lexical", "fastembed"],
        default="lexical",
        help="fastembed requiere el extra [embeddings]",
    )
    p_recall.add_argument(
        "--snapshot",
        type=Path,
        default=None,
        help="instantánea del tablero (items.json e issues.json): añade estado y verificación",
    )
    p_recall.add_argument("--issues", type=int, default=3, help="máximo de episodios parecidos")
    sub.add_parser("rebuild", help="escribe learning/dev_memory.json (copia local, ignorada por git)")
    p_board = sub.add_parser(
        "board",
        help="chequeo de solo lectura: issues, tablero y episodios (salida 0, 1 hallazgos, 2 sin lectura)",
    )
    p_board.add_argument(
        "--since",
        type=int,
        help="primer issue al que aplican las reglas 2 a 4 (obligatorio con gh; piloto: 76)",
    )
    p_board.add_argument(
        "--snapshot",
        type=Path,
        help="directorio con items.json e issues.json (y subissues.json opcional) en vez de gh",
    )
    p_pilot = sub.add_parser(
        "pilot",
        help="lectura de solo lectura del piloto de estimación (salida 0, o 2 sin lectura; no interpreta)",
    )
    from scripts.pilot_metrics import add_arguments, parse_map

    add_arguments(p_pilot)
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):  # UTF-8 también al redirigir en Windows
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    if args.cmd == "board":
        from scripts.board_check import run_board

        sys.exit(run_board(since=args.since, snapshot=args.snapshot, episodes=load_episodes()))
    if args.cmd == "pilot":
        from scripts.pilot_metrics import run_pilot

        try:
            mapping = parse_map(args.map)
        except ValueError as exc:
            parser.error(str(exc))
        sys.exit(
            run_pilot(
                since=args.since,
                until=args.until,
                snapshot=args.snapshot,
                episodes=load_episodes(),
                transcripts=args.transcripts,
                mapping=mapping,
            )
        )
    if args.cmd == "rebuild":
        mg = rebuild(load_episodes())
        mg.save(MEMORY_PATH)
        shown = MEMORY_PATH.relative_to(ROOT) if MEMORY_PATH.is_relative_to(ROOT) else MEMORY_PATH
        print(f"{shown}: {mg.stats()}")
    else:
        # El grafo no se versiona (#96): `recall` lo deriva de los episodios y nunca lee un
        # `dev_memory.json` local, que podría estar desactualizado tras un `git pull`.
        mg = rebuild(load_episodes())
        embedder = FastEmbedEmbedder() if args.embedder == "fastembed" else None
        if args.snapshot is None and args.issues == 3:
            print(recall(mg, args.query, args.n, embedder))
        elif args.snapshot is None:
            print(recall(mg, args.query, args.n, embedder, None, args.issues))
        else:
            from scripts.board_check import BoardReadError, cards_from_snapshot

            try:
                cards = cards_from_snapshot(args.snapshot)
            except BoardReadError as exc:
                print(f"error: no se pudo leer la instantánea: {exc}", file=sys.stderr)
                sys.exit(2)
            print(recall(mg, args.query, args.n, embedder, cards, args.issues))


if __name__ == "__main__":
    main()
