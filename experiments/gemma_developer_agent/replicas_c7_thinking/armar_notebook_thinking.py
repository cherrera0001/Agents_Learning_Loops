"""Arma el notebook de Kaggle de la variante thinking desde ``notebook_c7_thinking.py``.

Copia de ``replicas_c7_nav/armar_notebook_nav.py`` con los nombres propios de esta variante, que
tiene **dos** deltas (sampling + system prompt). Antes de escribir nada:

1. Verifica que el literal ``_SYSTEM_THINK`` del guion == ``kit_thinking/prompts/system.md``
   (byte a byte; única pieza de prompt que se versiona) y que el literal ``_SAMPLING_THINK``
   coincide con la constante ``SAMPLING_THINK``.
2. Monta el kit de referencia desde la descarga local de réplica 1 (gitignored, proveniencia
   verificada) sin ``adapters/``, con el ``system.md`` y el ``configs/sampling.yaml`` de la
   variante, y exige que la huella recomputada == ``HUELLA_THINK``.

El resto del kit no se versiona (los tres archivos de plantilla son contenido de la competencia;
``eval_config.yaml`` va como literal en la celda «kit», idéntico al de la condición 7).

Salida 0; 2 si falta un marcador, si un literal difiere o si la huella no cuadra.
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
HUELLA_THINK = "9d0db7b946e7"
FUENTE_KIT = AQUI.parent / "data/replicas_c7/replica_1/c7_submission"
SAMPLING_THINK = (
    "temperature: 0.2\n"
    "top_p: 0.95\n"
    "max_output_tokens: 8192\n"
    "thinking_config:\n"
    "  thinking_budget: 1024\n"
    "  include_thoughts: false\n"
)

KERNEL_METADATA = {
    "id": "cs4all/c7-thinking-condicion-7",
    "title": "c7-thinking-condicion-7",
    "code_file": "notebook_c7_thinking.ipynb",
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


def kit_para_huella(prompt_think: str) -> Path:
    """Monta el kit de referencia: réplica 1 sin adapters + system.md y sampling de la variante."""
    if not FUENTE_KIT.exists():
        raise FileNotFoundError(
            f"no se encuentra {FUENTE_KIT}; se necesita la descarga local de réplica 1 "
            "(gitignored) para recomputar la huella sin versionar contenido de la competencia"
        )
    tmp = Path(tempfile.mkdtemp(prefix="kit_think_huella_")) / "kit"
    shutil.copytree(FUENTE_KIT, tmp)
    shutil.rmtree(tmp / "adapters", ignore_errors=True)
    (tmp / "prompts/system.md").write_text(prompt_think, encoding="utf-8")
    (tmp / "configs/sampling.yaml").write_text(SAMPLING_THINK, encoding="utf-8")
    return tmp


def literal_del_guion(fuente: str, nombre: str) -> str:
    arbol = ast.parse(fuente)
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == nombre for t in nodo.targets
        ):
            return nodo.value.value
    raise ValueError(f"no se encontró el literal {nombre} en el guion")


def main() -> int:
    guion = (AQUI / "notebook_c7_thinking.py").read_text(encoding="utf-8")
    prompt_archivo = (AQUI / "kit_thinking/prompts/system.md").read_text(encoding="utf-8")
    if literal_del_guion(guion, "_SYSTEM_THINK") != prompt_archivo:
        print("error: _SYSTEM_THINK del guion != kit_thinking/prompts/system.md", file=sys.stderr)
        return 2
    if literal_del_guion(guion, "_SAMPLING_THINK") != SAMPLING_THINK:
        print("error: _SAMPLING_THINK del guion != SAMPLING_THINK de este script", file=sys.stderr)
        return 2
    try:
        huella = huella_config(kit_para_huella(prompt_archivo))
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if huella != HUELLA_THINK:
        print(f"error: huella del kit de referencia = {huella}, se esperaba {HUELLA_THINK}", file=sys.stderr)
        return 2

    celdas: dict[str, str] = {}
    matches = list(MARCADOR.finditer(guion))
    for i, m in enumerate(matches):
        fin = matches[i + 1].start() if i + 1 < len(matches) else len(guion)
        celdas[m.group(1)] = guion[m.start() : fin].strip() + "\n"
    for nombre in ("guardia", "instalacion", "versiones", "kit", "tareas", "servidor", "evaluacion"):
        if nombre not in celdas:
            print(f"error: falta la celda {nombre!r} en notebook_c7_thinking.py", file=sys.stderr)
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
                "id": f"c7think-{i:02d}",
                "metadata": {},
                "outputs": [],
                "source": [line + "\n" for line in celdas[nombre].splitlines()],
            }
            for i, nombre in enumerate(orden)
        ],
    }
    (AQUI / "notebook_c7_thinking.ipynb").write_text(
        json.dumps(ipynb, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (AQUI / "kernel-metadata.json").write_text(
        json.dumps(KERNEL_METADATA, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(f"notebook_c7_thinking.ipynb: {len(orden)} celdas | huella {HUELLA_THINK} | kernel-metadata.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
