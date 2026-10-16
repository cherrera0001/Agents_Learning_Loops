"""Arma el notebook de Kaggle de la variante navegación-primero desde ``notebook_c7_nav.py``.

Igual que ``replicas_c7/armar_notebook.py`` (del que es copia) con tres adiciones:

1. Lee el guion ``notebook_c7_nav.py`` y escribe ``notebook_c7_nav.ipynb`` + ``kernel-metadata.json``.
2. Antes de armar, verifica que el literal ``_SYSTEM_NAV`` del guion sea idéntico byte a byte a
   ``kit_nav/prompts/system.md`` (única fuente de verdad del bloque de instrucciones).
3. Recomputa la huella de configuración sobre ``kit_nav/`` con la fórmula del manuscrito y exige
   que coincida con ``HUELLA_NAV``. Si algo difiere, sale 2 sin escribir nada.

Salida 0; 2 si falta un marcador, si el prompt difiere o si la huella no cuadra.
"""

from __future__ import annotations

import ast
import base64
import hashlib
import json
import re
import sys
from pathlib import Path

from scripts import kaggle_arnes

AQUI = Path(__file__).resolve().parent
MARCADOR = re.compile(r"^# ==== CELDA: (\w+) ====$", re.M)
MARCA_VERSIONES = "# Versiones del arnes (#195)"
HUELLA_NAV = "af8cca829561"

KERNEL_METADATA = {
    "id": "cs4all/c7-navegacion-condicion-7",
    "title": "c7-navegacion-condicion-7",
    "code_file": "notebook_c7_nav.ipynb",
    "language": "python",
    "kernel_type": "notebook",
    "is_private": True,
    "enable_gpu": True,
    "enable_internet": False,
    "dataset_sources": ["metric/gemma-4-developer-agent-wheelhouse"],
    "competition_sources": ["gemma-4-developer-agent"],
    "kernel_sources": [],
    "model_sources": ["google/gemma-4/Other/gemma-4-31b-it-qat-w4a16-ct/2"],
    "docker_image": (
        "gcr.io/kaggle-private-byod/python"
        "@sha256:37c64f7dd9c54116ecd1bcc88817c5469b88387388fade02bfa8bf3fc647d461"
    ),
    "machine_shape": "NvidiaL4",
}


def huella_config(directorio: Path) -> str:
    """Misma fórmula que la celda «kit» del notebook y el manuscrito §«Data availability»."""
    partes = []
    for raiz, _, archivos in __import__("os").walk(directorio):
        for a in archivos:
            partes.append(base64.b64encode((Path(raiz) / a).read_bytes()).decode())
    return hashlib.sha256("".join(sorted(partes)).encode()).hexdigest()[:12]


def literal_system_nav(fuente: str) -> str:
    arbol = ast.parse(fuente)
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "_SYSTEM_NAV" for t in nodo.targets
        ):
            return nodo.value.value
    raise ValueError("no se encontró el literal _SYSTEM_NAV en el guion")


def main() -> int:
    guion = (AQUI / "notebook_c7_nav.py").read_text(encoding="utf-8")
    prompt_archivo = (AQUI / "kit_nav/prompts/system.md").read_text(encoding="utf-8")
    if literal_system_nav(guion) != prompt_archivo:
        print("error: _SYSTEM_NAV del guion != kit_nav/prompts/system.md", file=sys.stderr)
        return 2
    huella = huella_config(AQUI / "kit_nav")
    if huella != HUELLA_NAV:
        print(f"error: huella de kit_nav = {huella}, se esperaba {HUELLA_NAV}", file=sys.stderr)
        return 2

    celdas: dict[str, str] = {}
    matches = list(MARCADOR.finditer(guion))
    for i, m in enumerate(matches):
        fin = matches[i + 1].start() if i + 1 < len(matches) else len(guion)
        celdas[m.group(1)] = guion[m.start() : fin].strip() + "\n"
    for nombre in ("guardia", "instalacion", "versiones", "kit", "tareas", "servidor", "evaluacion"):
        if nombre not in celdas:
            print(f"error: falta la celda {nombre!r} en notebook_c7_nav.py", file=sys.stderr)
            return 2
    guarda = kaggle_arnes.celda_de_versiones(
        "resultados_c7/versiones_arnes.json", sha256=kaggle_arnes.RUEDAS_ESPERADAS_SHA256
    )
    if MARCA_VERSIONES not in guarda:
        print("error: la guarda generada no trae la marca de versiones", file=sys.stderr)
        return 2
    celdas["versiones"] = guarda
    orden = ["guardia", "instalacion", "versiones", "kit", "tareas", "servidor", "evaluacion"]
    ipynb = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.11"},
        },
        "cells": [
            {
                "cell_type": "code",
                "execution_count": None,
                "id": f"c7nav-{i:02d}",
                "metadata": {},
                "outputs": [],
                "source": [line + "\n" for line in celdas[nombre].splitlines()],
            }
            for i, nombre in enumerate(orden)
        ],
    }
    (AQUI / "notebook_c7_nav.ipynb").write_text(
        json.dumps(ipynb, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (AQUI / "kernel-metadata.json").write_text(
        json.dumps(KERNEL_METADATA, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(f"notebook_c7_nav.ipynb: {len(orden)} celdas | huella {HUELLA_NAV} | kernel-metadata.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
