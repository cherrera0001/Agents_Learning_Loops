"""Arma el notebook del brazo HÍBRIDO (nav-v2 + eval público) desde ``notebook_c7_hibrido.py``.

Copia del patrón de ``replicas_c7_r1fiel/armar_notebook_r1fiel.py`` (decisión (b) del estudio
``docs/c7_baseline024_estudio.md``). Kit de referencia = descarga de réplica 1 sin ``adapters/``
+ ``prompts/system.md`` de NAVEGACIÓN (versionado en ``kit_hibrido/``, sha f5bd1995…) +
``configs/sampling.yaml`` de la CONDICIÓN 7 (thinking_budget 4096) + ``eval_config.yaml`` PÚBLICO
(timeout_seconds 240, max_tool_calls 28, max_time_minutes 8.0, max_turns 80). Antes de escribir:

1. Verifica ``_SYSTEM_HIBRIDO`` == ``kit_hibrido/prompts/system.md``, ``_SAMPLING_HIBRIDO`` ==
   ``SAMPLING_HIBRIDO`` y que el guion escribe 8.0 min y 28 llamadas.
2. Monta el kit de referencia y exige huella == ``HUELLA_HIBRIDO``.

Pre-construido el 2026-10-18 (0 GPU). NO se corre ni se sube sin decisión del dueño: las tres
gates pre-registradas del estudio aplican antes de cualquier envío. Salida 0; 2 si falla algo.
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
HUELLA_HIBRIDO = "0fad98b7fe4d"
FUENTE_KIT = AQUI.parent / "data/replicas_c7/replica_1/c7_submission"
SAMPLING_HIBRIDO = (
    "temperature: 0.2\n"
    "top_p: 0.95\n"
    "max_output_tokens: 8192\n"
    "thinking_config:\n"
    "  thinking_budget: 4096\n"
    "  include_thoughts: true\n"
)
EVAL_CONFIG_R1FIEL = (
    "evaluation:\n  timeout_seconds: 240\n  max_tool_calls: 28\n  max_time_minutes: 8.0\n  max_turns: 80\n"
)

KERNEL_METADATA = {
    "id": "cs4all/c7-hibrido-condicion-7",
    "title": "c7-hibrido-condicion-7",
    "code_file": "notebook_c7_hibrido.ipynb",
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


def kit_para_huella(prompt_hibrido: str) -> Path:
    """Monta el kit de referencia: réplica 1 sin adapters + system.md, sampling y eval_config."""
    if not FUENTE_KIT.exists():
        raise FileNotFoundError(
            f"no se encuentra {FUENTE_KIT}; se necesita la descarga local de réplica 1 "
            "(gitignored) para recomputar la huella sin versionar contenido de la competencia"
        )
    tmp = Path(tempfile.mkdtemp(prefix="kit_hibrido_huella_")) / "kit"
    shutil.copytree(FUENTE_KIT, tmp)
    shutil.rmtree(tmp / "adapters", ignore_errors=True)
    (tmp / "prompts/system.md").write_text(prompt_hibrido, encoding="utf-8")
    (tmp / "configs/sampling.yaml").write_text(SAMPLING_HIBRIDO, encoding="utf-8")
    (tmp / "eval_config.yaml").write_text(EVAL_CONFIG_R1FIEL, encoding="utf-8")
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
    guion = (AQUI / "notebook_c7_hibrido.py").read_text(encoding="utf-8")
    if not FUENTE_KIT.exists():
        print(f"error: no se encuentra {FUENTE_KIT} (descarga de réplica 1)", file=sys.stderr)
        return 2
    prompt_archivo = (AQUI / "kit_hibrido/prompts/system.md").read_text(encoding="utf-8")
    if literal_del_guion(guion, "_SYSTEM_HIBRIDO") != prompt_archivo:
        print(
            "error: _SYSTEM_HIBRIDO del guion != prompts/system.md de la descarga de réplica 1",
            file=sys.stderr,
        )
        return 2
    if literal_del_guion(guion, "_SAMPLING_HIBRIDO") != SAMPLING_HIBRIDO:
        print("error: _SAMPLING_HIBRIDO del guion != SAMPLING_HIBRIDO de este script", file=sys.stderr)
        return 2
    if "max_time_minutes: 8.0" not in guion or "max_tool_calls: 28" not in guion:
        print("error: el guion no escribe los deltas del brazo (8.0 min / 28 llamadas)", file=sys.stderr)
        return 2
    try:
        huella = huella_config(kit_para_huella(prompt_archivo))
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if huella != HUELLA_HIBRIDO:
        print(f"error: huella = {huella}, se esperaba {HUELLA_HIBRIDO}", file=sys.stderr)
        return 2

    celdas: dict[str, str] = {}
    matches = list(MARCADOR.finditer(guion))
    for i, m in enumerate(matches):
        fin = matches[i + 1].start() if i + 1 < len(matches) else len(guion)
        celdas[m.group(1)] = guion[m.start() : fin].strip() + "\n"
    for nombre in ("guardia", "instalacion", "versiones", "kit", "tareas", "servidor", "evaluacion"):
        if nombre not in celdas:
            print(f"error: falta la celda {nombre!r} en notebook_c7_hibrido.py", file=sys.stderr)
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
                "id": f"c7hib-{i:02d}",
                "metadata": {},
                "outputs": [],
                "source": [line + "\n" for line in celdas[nombre].splitlines()],
            }
            for i, nombre in enumerate(orden)
        ],
    }
    (AQUI / "notebook_c7_hibrido.ipynb").write_text(
        json.dumps(ipynb, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (AQUI / "kernel-metadata.json").write_text(
        json.dumps(KERNEL_METADATA, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(f"notebook_c7_hibrido.ipynb: {len(orden)} celdas | huella {HUELLA_HIBRIDO} | kernel-metadata.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
