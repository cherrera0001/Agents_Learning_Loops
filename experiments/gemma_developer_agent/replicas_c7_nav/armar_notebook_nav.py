"""Arma el notebook de Kaggle de la variante navegación-primero desde ``notebook_c7_nav.py``.

Igual que ``replicas_c7/armar_notebook.py`` (del que es copia) con tres adiciones:

1. Lee el guion ``notebook_c7_nav.py`` y escribe ``notebook_c7_nav.ipynb`` + ``kernel-metadata.json``.
2. Antes de armar, verifica que el literal ``_SYSTEM_NAV`` del guion sea idéntico byte a byte a
   ``kit_nav/prompts/system.md`` (única pieza del kit que se versiona: es texto nuestro).
3. Recomputa la huella de configuración con la fórmula del manuscrito sobre un kit de referencia
   que se monta al vuelo: la descarga local de réplica 1 (gitignored, proveniencia verificada)
   sin ``adapters/``, con ``prompts/system.md`` sustituido por el de navegación. Exige que
   coincida con ``HUELLA_NAV``. Si algo difiere, sale 2 sin escribir nada.

Los otros 5 archivos del kit (agent.yaml, analyzer.md, code_analyzer.yaml, eval_config.yaml,
sampling.yaml) NO se versionan: los tres primeros son plantilla de la competencia y los dos
últimos ya van como literales en la celda «kit» del notebook; en Kaggle el kit se reconstruye
desde sample_submission igual que en la condición 7.

Salida 0; 2 si falta un marcador, si el prompt difiere o si la huella no cuadra.
"""

from __future__ import annotations

import ast
import base64
import hashlib
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

from scripts import kaggle_arnes

AQUI = Path(__file__).resolve().parent
MARCADOR = re.compile(r"^# ==== CELDA: (\w+) ====$", re.M)
MARCA_VERSIONES = "# Versiones del arnes (#195)"
HUELLA_NAV = "af8cca829561"
FUENTE_KIT = AQUI.parent / "data/replicas_c7/replica_1/c7_submission"

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


def kit_para_huella(prompt_nav: str) -> Path:
    """Monta el kit de referencia: descarga de réplica 1 sin adapters + system.md de navegación."""
    if not FUENTE_KIT.exists():
        raise FileNotFoundError(
            f"no se encuentra {FUENTE_KIT}; se necesita la descarga local de réplica 1 "
            "(gitignored) para recomputar la huella sin versionar contenido de la competencia"
        )
    tmp = Path(tempfile.mkdtemp(prefix="kit_nav_huella_")) / "kit"
    shutil.copytree(FUENTE_KIT, tmp)
    shutil.rmtree(tmp / "adapters", ignore_errors=True)
    (tmp / "prompts/system.md").write_text(prompt_nav, encoding="utf-8")
    return tmp


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
    try:
        huella = huella_config(kit_para_huella(prompt_archivo))
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if huella != HUELLA_NAV:
        print(f"error: huella del kit de referencia = {huella}, se esperaba {HUELLA_NAV}", file=sys.stderr)
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
