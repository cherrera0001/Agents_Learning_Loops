#!/usr/bin/env python3
"""Construye los snapshots de tareas que faltan en data/snapshots/ (repo@base_commit + .git).

Receta replicada de los 20 tgz existentes (./ prefix, .git incluido). Una clonación por repo
(4 repos), un worktree por tarea. Topes del dueño (2026-10-18): 20 GB acumulados o 2 h — al
superarlos se detiene con avance parcial y reporte. Uso:

  python construir_snapshots.py [--tope-gb 20] [--tope-min 120]

Salida: data/snapshots/<instance_id>.tgz nuevos + construir_snapshots.log junto a este guion.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
DATA = RAIZ / "experiments/gemma_developer_agent/data"
SNAPSHOTS = DATA / "snapshots"
TASKS = DATA / "tasks.jsonl"
CLONES = Path("/tmp/repos_snapshots")
LOG = Path(__file__).resolve().parent / "construir_snapshots.log"


def log(msg: str) -> None:
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(f"{time.strftime('%H:%M:%S')} {msg}\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tope-gb", type=float, default=20.0)
    ap.add_argument("--tope-min", type=float, default=120.0)
    args = ap.parse_args()
    t0 = time.time()
    acumulados = 0
    CLONES.mkdir(parents=True, exist_ok=True)
    tareas = [json.loads(l) for l in TASKS.read_text(encoding="utf-8").splitlines() if l.strip()]
    faltan = [t for t in tareas if not (SNAPSHOTS / f"{t['instance_id']}.tgz").exists()]
    por_repo: dict[str, list[dict]] = {}
    for t in faltan:
        por_repo.setdefault(t["repo"], []).append(t)
    log(f"inicio: {len(faltan)} snapshots a construir en {len(por_repo)} repos")
    for repo, grupo in sorted(por_repo.items()):
        destino = CLONES / repo.replace("/", "__")
        if not (destino / ".git").exists():
            log(f"clonando {repo} …")
            r = subprocess.run(
                ["git", "clone", "--quiet", f"https://github.com/{repo}.git", str(destino)],
                capture_output=True, text=True, timeout=1800,
            )
            if r.returncode != 0:
                log(f"ERROR clonando {repo}: {r.stderr.strip()[:200]}")
                continue
        for t in grupo:
            iid = t["instance_id"]
            salida = SNAPSHOTS / f"{iid}.tgz"
            if salida.exists():
                continue
            if time.time() - t0 > args.tope_min * 60:
                log(f"TOPE DE TIEMPO tras {iid}; parando con avance parcial")
                return 0
            wt = CLONES / "wt" / iid
            wt.parent.mkdir(parents=True, exist_ok=True)
            r = subprocess.run(
                ["git", "-C", str(destino), "worktree", "add", "--detach", "--quiet", str(wt),
                 t["base_commit"]],
                capture_output=True, text=True, timeout=600,
            )
            if r.returncode != 0:
                log(f"ERROR worktree {iid}@{t['base_commit'][:8]}: {r.stderr.strip()[:200]}")
                continue
            try:
                r = subprocess.run(
                    ["tar", "-C", str(wt), "-czf", str(salida), "."],
                    capture_output=True, text=True, timeout=900,
                )
            finally:
                subprocess.run(["git", "-C", str(destino), "worktree", "remove", "--force", str(wt)],
                               capture_output=True)
            if r.returncode != 0:
                log(f"ERROR tar {iid}: {r.stderr.strip()[:200]}")
                salida.unlink(missing_ok=True)
                continue
            acumulados += salida.stat().st_size
            log(f"OK {iid} ({salida.stat().st_size/1e6:.0f} MB; acum {acumulados/1e9:.1f} GB)")
            if acumulados > args.tope_gb * 1e9:
                log(f"TOPE DE TAMAÑO ({args.tope_gb} GB); parando con avance parcial")
                return 0
    log(f"fin: {len(faltan)} solicitados, avance completo o con tope")
    return 0


if __name__ == "__main__":
    sys.exit(main())
