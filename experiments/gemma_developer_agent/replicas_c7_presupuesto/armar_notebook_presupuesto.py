"""Arma el notebook de Kaggle de la variante conciencia-de-presupuesto desde ``notebook_c7_presupuesto.py``.

Copia de ``replicas_c7_nav/armar_notebook_nav.py`` con los nombres propios de esta variante.
Antes de escribir nada:

1. Verifica que el literal ``_SYSTEM_PRES`` del guion == ``kit_presupuesto/prompts/system.md``
   (byte a byte; única pieza del kit que se versiona).
2. Monta el kit de referencia desde la descarga local de réplica 1 (gitignored, proveniencia
   verificada) sin ``adapters/``, con el ``system.md`` de presupuesto, y exige que la huella
   recomputada == ``HUELLA_PRES``.

Los otros 5 archivos del kit no se versionan (los tres de plantilla son contenido de la
competencia; ``eval_config.yaml``/``sampling.yaml`` van como literales en la celda «kit»).

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
HUELLA_PRES = "52ba08ceac25"
FUENTE_KIT = AQUI.parent / "data/replicas_c7/replica_1/c7_submission"

KERNEL_METADATA = {
    "id": "cs4all/c7-presupuesto-condicion-7",
    "title": "c7-presupuesto-condicion-7",
    "code_file": "notebook_c7_presupuesto.ipynb",
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


def kit_para_huella(prompt_pres: str) -> Path:
    """Monta el kit de referencia: descarga de réplica 1 sin adapters + system.md de presupuesto."""
    if not FUENTE_KIT.exists():
        raise FileNotFoundError(
            f"no se encuentra {FUENTE_KIT}; se necesita la descarga local de réplica 1 "
            "(gitignored) para recomputar la huella sin versionar contenido de la competencia"
        )
    tmp = Path(tempfile.mkdtemp(prefix="kit_pres_huella_")) / "kit"
    shutil.copytree(FUENTE_KIT, tmp)
    shutil.rmtree(tmp / "adapters", ignore_errors=True)
    (tmp / "prompts/system.md").write_text(prompt_pres, encoding="utf-8")
    return tmp


def literal_system_pres(fuente: str) -> str:
    arbol = ast.parse(fuente)
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "_SYSTEM_PRES" for t in nodo.targets
        ):
            return nodo.value.value
    raise ValueError("no se encontró el literal _SYSTEM_PRES en el guion")


def main() -> int:
    guion = (AQUI / "notebook_c7_presupuesto.py").read_text(encoding="utf-8")
    prompt_archivo = (AQUI / "kit_presupuesto/prompts/system.md").read_text(encoding="utf-8")
    if literal_system_pres(guion) != prompt_archivo:
        print("error: _SYSTEM_PRES del guion != kit_presupuesto/prompts/system.md", file=sys.stderr)
        return 2
    try:
        huella = huella_config(kit_para_huella(prompt_archivo))
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if huella != HUELLA_PRES:
        print(f"error: huella del kit de referencia = {huella}, se esperaba {HUELLA_PRES}", file=sys.stderr)
        return 2

    celdas: dict[str, str] = {}
    matches = list(MARCADOR.finditer(guion))
    for i, m in enumerate(matches):
        fin = matches[i + 1].start() if i + 1 < len(matches) else len(guion)
        celdas[m.group(1)] = guion[m.start() : fin].strip() + "\n"
    for nombre in ("guardia", "instalacion", "versiones", "kit", "tareas", "servidor", "evaluacion"):
        if nombre not in celdas:
            print(f"error: falta la celda {nombre!r} en notebook_c7_presupuesto.py", file=sys.stderr)
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
                "id": f"c7pres-{i:02d}",
                "metadata": {},
                "outputs": [],
                "source": [line + "\n" for line in celdas[nombre].splitlines()],
            }
            for i, nombre in enumerate(orden)
        ],
    }
    (AQUI / "notebook_c7_presupuesto.ipynb").write_text(
        json.dumps(ipynb, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (AQUI / "kernel-metadata.json").write_text(
        json.dumps(KERNEL_METADATA, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(f"notebook_c7_presupuesto.ipynb: {len(orden)} celdas | huella {HUELLA_PRES} | kernel-metadata.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
