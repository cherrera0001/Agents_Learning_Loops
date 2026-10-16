"""Arma el notebook de Kaggle de las réplicas C7 desde ``notebook_c7.py``.

Parte el guion en celdas por los marcadores ``# ==== CELDA: <nombre> ====``, inserta la guarda de
versiones del arnés (``scripts.kaggle_arnes.celda_de_versiones`` con los SHA-256 fijados en el
concilio 46) en el marcador de la celda «versiones», y escribe ``notebook_c7.ipynb`` y
``kernel-metadata.json`` junto a este archivo. Salida 0; 2 si falta un marcador.

La guarda insertada se basta sola (no usa nombres de otras celdas salvo ``W``): detiene el
notebook antes de cargar el modelo si las ruedas no son las ensayadas o su SHA-256 difiere.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from scripts import kaggle_arnes

AQUI = Path(__file__).resolve().parent
MARCADOR = re.compile(r"^# ==== CELDA: (\w+) ====$", re.M)
MARCA_VERSIONES = "# Versiones del arnes (#195)"

KERNEL_METADATA = {
    "id": "cs4all/c7-replica-condicion-7",
    "title": "c7-replica-condicion-7",
    "code_file": "notebook_c7.ipynb",
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


def main() -> int:
    fuente = (AQUI / "notebook_c7.py").read_text(encoding="utf-8")
    celdas: dict[str, str] = {}
    matches = list(MARCADOR.finditer(fuente))
    for i, m in enumerate(matches):
        fin = matches[i + 1].start() if i + 1 < len(matches) else len(fuente)
        celdas[m.group(1)] = fuente[m.start() : fin].strip() + "\n"
    for nombre in ("guardia", "instalacion", "versiones", "kit", "tareas", "servidor", "evaluacion"):
        if nombre not in celdas:
            print(f"error: falta la celda {nombre!r} en notebook_c7.py", file=sys.stderr)
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
                "id": f"c7-{i:02d}",
                "metadata": {},
                "outputs": [],
                "source": [line + "\n" for line in celdas[nombre].splitlines()],
            }
            for i, nombre in enumerate(orden)
        ],
    }
    (AQUI / "notebook_c7.ipynb").write_text(json.dumps(ipynb, ensure_ascii=False, indent=1), encoding="utf-8")
    (AQUI / "kernel-metadata.json").write_text(
        json.dumps(KERNEL_METADATA, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(f"notebook_c7.ipynb: {len(orden)} celdas | kernel-metadata.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
