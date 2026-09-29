"""Demostración ejecutable: ``python -m src.main``.

1. Escenario *weather*: el intento 1 falla con la API deprecada, el agente
   aprende la asociación y en el intento 2 (meta distinta pero similar) elige
   directamente la ruta correcta.
2. Escenario *flaky*: con errores intermitentes, la memoria converge hacia la
   herramienta fiable. Se compara contra un agente sin memoria.
"""

from __future__ import annotations

import argparse

from .agent.core import Agent, Episode
from .agent.tools import flaky_scenario, weather_scenario


def show(ep: Episode) -> None:
    status = "OK " if ep.success else "FAIL"
    path = " → ".join(f"{s.tool}{'✓' if s.result.success else '✗'}" for s in ep.steps)
    print(f"  [{status}] #{ep.id} '{ep.goal}'  intentos={ep.attempts}  {path}")
    if ep.retrieval and any(s.score for s in ep.retrieval.ranked_actions):
        scores = ", ".join(f"{s.action}={s.score:+.3f}" for s in ep.retrieval.ranked_actions)
        print(f"         memoria: {scores}")
        for lesson in ep.retrieval.lessons[:2]:
            print(f"         lección recordada: {lesson}")


def weather_demo(out: str | None) -> None:
    print("\n=== Escenario 1: API deprecada (weather) ===")
    agent = Agent(weather_scenario())
    for goal in ["clima en Santiago", "pronóstico del clima en Madrid", "clima para mañana en Lima"]:
        show(agent.run(goal))
    print(f"  grafo: {agent.memory.stats()}")
    if out:
        agent.memory.save(out)
        print(f"  memoria serializada en {out}")


def flaky_demo(episodes: int = 20) -> None:
    print(f"\n=== Escenario 2: errores intermitentes (flaky), {episodes} episodios ===")
    for use_memory in (False, True):
        agent = Agent(flaky_scenario(), use_memory=use_memory)
        eps = [agent.run(f"tipo de cambio usd clp consulta {i}") for i in range(episodes)]
        attempts = sum(e.attempts for e in eps)
        first = sum(e.first_try_success for e in eps)
        latency = sum(s.result.latency_ms for e in eps for s in e.steps)
        label = "con memoria" if use_memory else "sin memoria"
        print(
            f"  {label:12s} éxito al 1er intento={first}/{episodes}  "
            f"llamadas totales={attempts}  latencia total={latency:.0f} ms"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="memory_graph.json", help="ruta del JSON del grafo")
    parser.add_argument("--episodes", type=int, default=20)
    args = parser.parse_args()
    weather_demo(args.out)
    flaky_demo(args.episodes)


if __name__ == "__main__":
    main()
