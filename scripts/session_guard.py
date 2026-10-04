"""Guardián de sesión: lo que el tablero (Project #5) dice que está sin resolver, al empezar a trabajar.

Lo ejecuta el gancho ``SessionStart`` de Claude Code (``.claude/settings.json``) y su salida entra en el
contexto de la sesión. Cruza issues, tarjetas y episodios con las mismas reglas que ``devlog board`` y
añade los issues y los PR abiertos, para que ninguna sesión abra trabajo nuevo sin ver el pendiente.

    python scripts/session_guard.py              # como gancho: informa y sale siempre con 0
    python scripts/session_guard.py --estricto   # a mano: 1 si hay hallazgos, 2 si no se pudo leer

Nunca bloquea una sesión: si no puede leer el tablero lo dice, y eso no es «sin hallazgos». No imprime
el token ni lo guarda.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, TextIO

# Ejecutado como archivo (el gancho lo llama así), la raíz del repositorio no está en la ruta de módulos.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.board_check import (
    OWNER,
    PROJECT_NUMBER,
    REPO,
    BoardReadError,
    Runner,
    _run_gh,
    check_board,
    check_missing_cards,
    read_github,
    read_snapshot,
)

EPISODES_DIR = Path(__file__).resolve().parent.parent / "learning" / "episodes"
# Primer issue al que aplican las reglas de estimación y cierre verificado (inicio del piloto).
DESDE = 76
TOPE_LINEAS = 12

EXIT_OK = 0
EXIT_HALLAZGOS = 1
EXIT_ILEGIBLE = 2


def load_episodes(directorio: Path = EPISODES_DIR) -> list[dict[str, Any]]:
    """Los episodios versionados. Se leen aquí, sin importar ``scripts.devlog``, para que el gancho
    funcione con cualquier Python, aunque el paquete del proyecto no esté instalado."""
    episodios = [json.loads(p.read_text("utf-8")) for p in directorio.glob("*.json")]
    return sorted(episodios, key=lambda e: e["seq"])


def token_de_la_cuenta(runner: Runner = _run_gh) -> str | None:
    """El token de la cuenta del proyecto, sin imprimirlo. ``None`` si ``gh`` no lo entrega."""
    proc = runner(["auth", "token", "--user", OWNER])
    valor = proc.stdout.strip()
    return valor if proc.returncode == 0 and valor else None


def abiertos(issues: Sequence[Mapping[str, Any]]) -> list[str]:
    filas = []
    for issue in sorted(issues, key=lambda i: int(i["number"])):
        if str(issue.get("state", "")).upper() != "OPEN":
            continue
        etiquetas = [str(e.get("name", "")) for e in issue.get("labels") or [] if isinstance(e, Mapping)]
        talla = next((e for e in etiquetas if e.startswith("talla:")), "sin talla")
        tipo = "épica" if "epic" in etiquetas else talla
        filas.append(f"  #{issue['number']} [{tipo}] {str(issue.get('title', ''))[:90]}")
    return filas


def prs_abiertos(runner: Runner) -> list[str]:
    proc = runner(
        ["pr", "list", "--repo", REPO, "--state", "open", "--json", "number,title,headRefName,isDraft"]
    )
    if proc.returncode != 0:
        raise BoardReadError(f"gh pr list falló ({proc.stderr.strip() or 'sin mensaje'})")
    try:
        datos = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise BoardReadError("gh pr list no devolvió JSON") from exc
    return [
        f"  PR #{pr['number']}{' (borrador)' if pr.get('isDraft') else ''} {pr.get('headRefName', '')}: "
        f"{str(pr.get('title', ''))[:70]}"
        for pr in sorted(datos, key=lambda p: int(p["number"]))
    ]


def _bloque(titulo: str, filas: Sequence[str], vacio: str) -> list[str]:
    if not filas:
        return [f"{titulo}: {vacio}"]
    visibles = list(filas[:TOPE_LINEAS])
    if len(filas) > TOPE_LINEAS:
        visibles.append(f"  … y {len(filas) - TOPE_LINEAS} más")
    return [f"{titulo} ({len(filas)}):", *visibles]


def informe(
    *,
    snapshot: Path | None,
    episodes: Sequence[Mapping[str, Any]],
    runner: Runner = _run_gh,
) -> tuple[list[str], int]:
    """Las líneas del informe y cuántos hallazgos hay. Lanza ``BoardReadError`` si no se pudo leer."""
    if snapshot is not None:
        items, issues, subs = read_snapshot(snapshot)
        prs: list[str] | None = None
    else:
        items, issues, subs = read_github(runner)
        prs = prs_abiertos(runner)
    hallazgos = sorted(
        check_board(issues, items, episodes, subs, DESDE) + check_missing_cards(issues, items, DESDE)
    )
    lineas = [f"GUARDIÁN DEL TABLERO · Project #{PROJECT_NUMBER} de {REPO}"]
    lineas += _bloque(
        "Hallazgos (tarjeta, issue y episodio no coinciden)", [f"  {h.line()}" for h in hallazgos], "ninguno"
    )
    lineas += _bloque("Issues abiertos", abiertos(issues), "ninguno")
    if prs is not None:
        lineas += _bloque("PR abiertos", prs, "ninguno")
    lineas.append(
        "Antes de abrir un issue o una rama: resuelve un hallazgo o avanza un issue abierto. Un issue se "
        "cierra con sus criterios comprobados y la tarjeta en Verificada, no al fusionar el PR."
    )
    return lineas, len(hallazgos)


def main(argv: list[str] | None = None, *, runner: Runner = _run_gh, out: TextIO | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--snapshot", type=Path, help="instantánea del tablero en vez de leer GitHub")
    parser.add_argument("--estricto", action="store_true", help="salir con 1 o 2 en vez de siempre con 0")
    args = parser.parse_args(argv)
    if out is None:
        # La consola de Windows no es UTF-8 por defecto y el informe lleva tildes.
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        out = sys.stdout

    if args.snapshot is None and not os.environ.get("GH_TOKEN"):
        valor = token_de_la_cuenta(runner)
        if valor:
            os.environ["GH_TOKEN"] = valor
    try:
        lineas, hallazgos = informe(snapshot=args.snapshot, episodes=load_episodes(), runner=runner)
    except (BoardReadError, OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print(
            f"GUARDIÁN DEL TABLERO: no se pudo leer el tablero ({type(exc).__name__}: {str(exc)[:200]}). "
            "Eso no significa que no haya pendientes: corre `python -m scripts.devlog board --since 76`.",
            file=out,
        )
        return EXIT_ILEGIBLE if args.estricto else EXIT_OK
    print("\n".join(lineas), file=out)
    if args.estricto and hallazgos:
        return EXIT_HALLAZGOS
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
