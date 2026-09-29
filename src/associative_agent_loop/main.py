"""Benchmark ejecutable: ``aal-benchmark [--json] [--episodes N] [-v]``
(equivalente: ``python -m associative_agent_loop.main``).

Escenarios
----------
1. ``same_goal``: la **misma meta** repetida. El intento 1 falla con la API
   deprecada, se consolida el fallo y en el intento 2 la memoria activa
   directamente la ruta alternativa exitosa.
2. ``paraphrase``: metas distintas pero relacionadas; la experiencia se
   generaliza por asociación (topics compartidos, similitud híbrida).
3. ``flaky``: errores intermitentes; se compara con un agente sin memoria.
4. ``cross_domain``: una API falla solo en un dominio; se compara la valencia
   contextual con la global (que contamina al otro dominio).

Con ``--json`` se imprime un reporte determinista (misma semilla ⇒ mismo JSON),
útil para comparar corridas entre versiones.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Any

from .agent.core import Agent, Episode
from .agent.tools import domain_scenario, flaky_scenario, weather_scenario
from .memory.associative import RetrievalConfig


def episode_record(ep: Episode) -> dict[str, Any]:
    record: dict[str, Any] = {
        "episode": ep.id,
        "goal": ep.goal,
        "path": [{"tool": s.tool, "success": s.result.success} for s in ep.steps],
        "attempts": ep.attempts,
        "success": ep.success,
        "first_try_success": ep.first_try_success,
    }
    if ep.retrieval:
        record["scores"] = {s.action: round(s.score, 4) for s in ep.retrieval.ranked_actions}
        record["lessons_recalled"] = ep.retrieval.lessons[:2]
    return record


def metrics(episodes: list[Episode]) -> dict[str, Any]:
    return {
        "episodes": len(episodes),
        "first_try_success": sum(e.first_try_success for e in episodes),
        "total_calls": sum(e.attempts for e in episodes),
        "total_latency_ms": sum(s.result.latency_ms for e in episodes for s in e.steps),
        "repeated_failures": sum(len(e.failed_tools) for e in episodes[1:]),
    }


def run_goals(agent: Agent, goals: list[str]) -> dict[str, Any]:
    episodes = [agent.run(g) for g in goals]
    return {
        "episodes": [episode_record(e) for e in episodes],
        "metrics": metrics(episodes),
        "graph": agent.memory.stats(),
    }


def benchmark(flaky_episodes: int = 20, seed: int = 7) -> dict[str, Any]:
    same = run_goals(Agent(weather_scenario()), ["clima en Santiago"] * 3)
    paraphrase = run_goals(
        Agent(weather_scenario()),
        ["clima en Santiago", "pronóstico del clima en Madrid", "clima para mañana en Lima"],
    )
    flaky_goals = [f"tipo de cambio usd clp consulta {i}" for i in range(flaky_episodes)]
    flaky = {
        label: run_goals(Agent(flaky_scenario(seed=seed), use_memory=use_memory), flaky_goals)["metrics"]
        for label, use_memory in (("without_memory", False), ("with_memory", True))
    }
    domain_goals = [
        "noticias de Santiago",
        "clima en Santiago",
        "clima en Valparaíso",
        "clima en Temuco",
        "noticias de Santiago",
        "clima en Concepción",
    ]
    cross_domain = {
        label: run_goals(
            Agent(domain_scenario(), retrieval_config=RetrievalConfig(contextual_valence=ctx)),
            domain_goals,
        )["metrics"]
        for label, ctx in (("global_valence", False), ("contextual_valence", True))
    }
    return {
        "benchmark": "associative-agent-loop",
        "seed": seed,
        "scenarios": {
            "same_goal": same,
            "paraphrase": paraphrase,
            "flaky": flaky,
            "cross_domain": cross_domain,
        },
    }


def print_report(report: dict[str, Any]) -> None:
    titles = {
        "same_goal": "Escenario 1: misma meta repetida (API deprecada)",
        "paraphrase": "Escenario 2: metas parafraseadas",
    }
    for key, title in titles.items():
        print(f"\n=== {title} ===")
        for ep in report["scenarios"][key]["episodes"]:
            status = "OK " if ep["success"] else "FAIL"
            path = " → ".join(f"{p['tool']}{'✓' if p['success'] else '✗'}" for p in ep["path"])
            print(f"  [{status}] #{ep['episode']} '{ep['goal']}'  intentos={ep['attempts']}  {path}")
            if any(ep.get("scores", {}).values()):
                scores = ", ".join(f"{a}={s:+.3f}" for a, s in ep["scores"].items())
                print(f"         memoria: {scores}")
                for lesson in ep.get("lessons_recalled", [])[:1]:
                    print(f"         lección recordada: {lesson}")
        m = report["scenarios"][key]["metrics"]
        print(f"  fallos repetidos tras el primer episodio: {m['repeated_failures']}")

    flaky = report["scenarios"]["flaky"]
    print(f"\n=== Escenario 3: errores intermitentes, {flaky['with_memory']['episodes']} episodios ===")
    for label, key in (("sin memoria", "without_memory"), ("con memoria", "with_memory")):
        m = flaky[key]
        print(
            f"  {label:12s} éxito al 1er intento={m['first_try_success']}/{m['episodes']}  "
            f"llamadas totales={m['total_calls']}  latencia total={m['total_latency_ms']:.0f} ms"
        )

    cross = report["scenarios"]["cross_domain"]
    print("\n=== Escenario 4: fallo en un dominio (clima) vs otro (noticias) ===")
    for label, key in (("valencia global", "global_valence"), ("valencia contextual", "contextual_valence")):
        m = cross[key]
        print(
            f"  {label:20s} llamadas totales={m['total_calls']}  "
            f"latencia total={m['total_latency_ms']:.0f} ms"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--json", action="store_true", help="imprime el reporte como JSON")
    parser.add_argument("--episodes", type=int, default=20, help="episodios del escenario flaky")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("-v", "--verbose", action="count", default=0, help="-v: INFO, -vv: DEBUG (a stderr)")
    args = parser.parse_args()
    # En Windows, stdout redirigido usa la codificación ANSI (cp1252): el JSON y
    # los símbolos ✓/✗ dejarían de ser UTF-8 al hacer `--json > reporte.json`.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if args.verbose:
        logging.basicConfig(
            level=logging.DEBUG if args.verbose > 1 else logging.INFO,
            format="%(levelname)s %(name)s: %(message)s",
            stream=sys.stderr,
        )

    report = benchmark(args.episodes, args.seed)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print_report(report)


if __name__ == "__main__":
    main()
