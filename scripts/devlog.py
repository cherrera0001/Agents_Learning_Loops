"""Bitácora de aprendizaje del propio repositorio (*dogfooding*).

Cada issue trabajado es un episodio en ``learning/episodes/*.json``. El grafo
``learning/dev_memory.json`` se deriva de ellos de forma determinista, y antes
de empezar un issue se consulta con ``recall``.

Uso::

    python -m scripts.devlog recall "texto del issue"
    python -m scripts.devlog rebuild
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.agent.tools import ToolResult
from src.memory.associative import Retriever
from src.memory.consolidation import Consolidator
from src.memory.embeddings import Embedder, FastEmbedEmbedder
from src.memory.graph import MemoryGraph, NodeType

ROOT = Path(__file__).resolve().parent.parent
EPISODES_DIR = ROOT / "learning" / "episodes"
MEMORY_PATH = ROOT / "learning" / "dev_memory.json"


def load_episodes(episodes_dir: Path = EPISODES_DIR) -> list[dict[str, Any]]:
    episodes = [json.loads(p.read_text("utf-8")) for p in episodes_dir.glob("*.json")]
    return sorted(episodes, key=lambda e: e["seq"])


def rebuild(episodes: list[dict[str, Any]]) -> MemoryGraph:
    """Reproduce los episodios en orden de ``seq`` sobre una memoria vacía."""
    mg = MemoryGraph()
    consolidator = Consolidator(mg)
    for ep in sorted(episodes, key=lambda e: e["seq"]):
        episode_id = mg.tick()
        goal = consolidator.record_goal(ep["goal"], episode_id)
        mg.node(goal).metadata["ref"] = ep["id"]
        steps = []
        for i, step in enumerate(ep["steps"]):
            result = ToolResult(step["success"], output=step.get("note"), error=step.get("error"))
            consolidator.record_step(goal, step["action"], result, episode_id, i)
            steps.append((step["action"], result))
        consolidator.consolidate_episode(goal, steps)
        for lesson in ep.get("lessons", []):
            consolidator.add_lesson(goal, lesson)
    return mg


def recall(mg: MemoryGraph, query: str, top_lessons: int = 5, embedder: Embedder | None = None) -> str:
    actions = [mg.node(n).label for n in mg.nodes_of_type(NodeType.ACTION)]
    result = Retriever(mg, embedder=embedder).retrieve(query, actions)
    lines = [f"RETRIEVE: {query!r}", "", "Acciones (score = relevancia · valencia):"]
    lines += [
        f"  {s.score:+.3f}  {s.action}  (rel={s.relevance:.2f}, val={s.valence:+.2f})"
        for s in result.ranked_actions
        if s.relevance > 0
    ] or ["  (sin experiencia relacionada)"]
    lines += ["", "Lecciones:"]
    lines += [f"  - {l}" for l in result.lessons[:top_lessons]] or ["  (ninguna)"]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_recall = sub.add_parser("recall", help="consulta la memoria antes de empezar un issue")
    p_recall.add_argument("query")
    p_recall.add_argument("-n", type=int, default=5, help="máximo de lecciones")
    p_recall.add_argument(
        "--embedder", choices=["lexical", "fastembed"], default="lexical",
        help="fastembed requiere el extra [embeddings]",
    )
    sub.add_parser("rebuild", help="reconstruye learning/dev_memory.json")
    args = parser.parse_args()

    if args.cmd == "rebuild":
        mg = rebuild(load_episodes())
        mg.save(MEMORY_PATH)
        print(f"{MEMORY_PATH.relative_to(ROOT)}: {mg.stats()}")
    else:
        mg = MemoryGraph.load(MEMORY_PATH) if MEMORY_PATH.exists() else rebuild(load_episodes())
        embedder = FastEmbedEmbedder() if args.embedder == "fastembed" else None
        print(recall(mg, args.query, args.n, embedder))


if __name__ == "__main__":
    main()
