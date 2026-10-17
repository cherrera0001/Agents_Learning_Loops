#!/usr/bin/env python3
"""Rerun dorado local: verificar task.patch (gold) contra el harness propio, sin GPU.

Estado: NO EJECUTADO (forense, 2026-10-17). Faltan para correrlo:
  1. snapshots de 82/129 tareas (localmente hay 47; faltan 48 fastapi, 33 rich, 1 httpx)
  2. venv del arnés con deps que no están en disco como ruedas: google-genai, litellm, docker-sdk
     (las 4 ruedas del arnés sí están en data/rescate_kaggle/instrumentos/arnes_2026-10-12_1951/ruedas)

Entorno estimado (2 vCPU, sin GPU):
  python -m venv /tmp/venv_gold && /tmp/venv_gold/bin/pip install \
      --no-index --find-links experiments/gemma_developer_agent/data/rescate_kaggle/instrumentos/arnes_2026-10-12_1951/ruedas \
      swegemma adk_eval_core adk_submission google_adk pydantic pyyaml networkx \
  # + google-genai, litellm, docker (SDK) y transitivas (requieren internet o el wheelhouse de Kaggle)

Ruedas del sandbox (con h11 y dirty_equals, que data/wheels no trae):
  experiments/gemma_developer_agent/data/build_sandbox_20261003_v2/wheels  (117 ruedas)

Comando:
  /tmp/venv_gold/bin/python gold_patch_local.py \
      --tasks experiments/gemma_developer_agent/data/tasks.jsonl \
      --snapshots experiments/gemma_developer_agent/data/snapshots \
      --wheels experiments/gemma_developer_agent/data/build_sandbox_20261003_v2/wheels \
      --results /tmp/gold_rerun

Salida: /tmp/gold_rerun/gold_results.jsonl con una fila por tarea:
instance_id, repo, resolved, test_exit_code, error, duration_seconds
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

from swegemma.config import EvalConfig
from swegemma.harness.verification import verify_task
from swegemma.models.task import Task, load_tasks
from swegemma.sandbox.docker import DockerSandboxManager  # manager concreto del backend docker


async def una(config: EvalConfig, docker, task: Task) -> dict:
    t0 = time.perf_counter()
    snapshot = config.snapshots_dir / f"{task.instance_id}.tgz"
    if not snapshot.exists():
        snapshot = config.snapshots_dir / f"{task.instance_id}.tar.gz"
    if not snapshot.exists():
        return {
            "instance_id": task.instance_id,
            "repo": task.repo,
            "resolved": None,
            "error": "sin snapshot local",
        }
    # El parche DORADO entra como agent_patch: se salta la Fase 1 por completo.
    res = await verify_task(
        docker,
        config,
        task,
        snapshot,
        agent_patch=task.patch,
        agent_error=None,
        trace=None,
        start_time=time.perf_counter(),
    )
    return {
        "instance_id": task.instance_id,
        "repo": task.repo,
        "resolved": bool(res.resolved),
        "test_exit_code": res.test_exit_code,
        "error": res.error_message,
        "duration_seconds": round(time.perf_counter() - t0, 2),
    }


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--snapshots", required=True)
    ap.add_argument("--wheels", required=True)
    ap.add_argument("--results", required=True)
    args = ap.parse_args()

    resultados = Path(args.results)
    resultados.mkdir(parents=True, exist_ok=True)
    config = EvalConfig(
        tasks_path=Path(args.tasks),
        snapshots_dir=Path(args.snapshots),
        results_dir=resultados,
        submission_dir=Path(args.tasks).parent,  # no se usa en verificación
        models=None,  # type: ignore[arg-type]  # la Fase 2 no toca el modelo
        wheels_dir=Path(args.wheels),
    )
    docker = DockerSandboxManager()
    tareas = load_tasks(Path(args.tasks))
    with (resultados / "gold_results.jsonl").open("a", encoding="utf-8") as fh:
        for task in tareas:
            fila = await una(config, docker, task)
            fh.write(json.dumps(fila, ensure_ascii=False) + "\n")
            fh.flush()
            print(fila["instance_id"], fila["resolved"], fila.get("error"))


if __name__ == "__main__":
    asyncio.run(main())
