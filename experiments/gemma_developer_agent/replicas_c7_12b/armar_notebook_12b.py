"""Arma el notebook de Kaggle del brazo 12B (variante de modelo) desde ``notebook_c7_12b.py``.

Copia del patrón de ``replicas_c7_r1fiel/armar_notebook_r1fiel.py``. Dos deltas puros de
configuración respecto a la condición 7: (1) ``model: gemma-4-12b-it-qat-w4a16-ct`` en
``agent.yaml`` y ``sub_agents/code_analyzer.yaml`` (la regla oficial exige una sola variante por
envío; distintos envíos pueden usar variantes distintas — STATUS §Reglas f); (2)
``eval_config.yaml`` con ``max_time_minutes: 5.0``. Sampling idéntico a la condición 7
(``thinking_budget: 4096``, ``include_thoughts: true``) y prompt byte-idéntico. Antes de escribir:

1. Verifica ``_SYSTEM_12B`` == ``prompts/system.md`` de la descarga de réplica 1, ``_SAMPLING_12B``
   == ``SAMPLING_12B`` y que el guion escribe 5.0 min y el modelo 12B.
2. Monta el kit de referencia (descarga sin ``adapters/``, modelo reescrito, sampling y eval_config
   de la variante) y exige huella == ``HUELLA_12B``.

Construido el 2026-10-18 (Fase D del plan del dueño) tras verificar la regla de variantes. NO se
corre ni se sube sin decisión del dueño: el scorer falló con 12B en tres reportes (hilo 749259).

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
MODELO_12B = "gemma-4-12b-it-qat-w4a16-ct"
MODELO_31B = "gemma-4-31b-it-qat-w4a16-ct"
HUELLA_12B = "adb3004b2f76"
FUENTE_KIT = AQUI.parent / "data/replicas_c7/replica_1/c7_submission"
SAMPLING_12B = (
    "temperature: 0.2\n"
    "top_p: 0.95\n"
    "max_output_tokens: 8192\n"
    "thinking_config:\n"
    "  thinking_budget: 4096\n"
    "  include_thoughts: true\n"
)
EVAL_CONFIG_12B = (
    "evaluation:\n  timeout_seconds: 60\n  max_tool_calls: 60\n  max_time_minutes: 5.0\n  max_turns: 100\n"
)

KERNEL_METADATA = {
    "id": "cs4all/c7-12b-condicion-7",
    "title": "c7-12b-condicion-7",
    "code_file": "notebook_c7_12b.ipynb",
    "language": "python",
    "kernel_type": "notebook",
    "is_private": True,
    "enable_gpu": True,
    "enable_internet": False,
    "dataset_sources": ["metric/gemma-4-developer-agent-wheelhouse"],
    "competition_sources": ["gemma-4-developer-agent"],
    "kernel_sources": [],
    "model_sources": ["google/gemma-4/Other/gemma-4-12b-it-qat-w4a16-ct/2"],
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


def kit_para_huella(prompt_12b: str) -> Path:
    """Monta el kit de referencia: réplica 1 sin adapters + system.md, sampling y eval_config."""
    if not FUENTE_KIT.exists():
        raise FileNotFoundError(
            f"no se encuentra {FUENTE_KIT}; se necesita la descarga local de réplica 1 "
            "(gitignored) para recomputar la huella sin versionar contenido de la competencia"
        )
    tmp = Path(tempfile.mkdtemp(prefix="kit_12b_huella_")) / "kit"
    shutil.copytree(FUENTE_KIT, tmp)
    shutil.rmtree(tmp / "adapters", ignore_errors=True)
    for f in ("agent.yaml", "sub_agents/code_analyzer.yaml"):
        p = tmp / f
        p.write_text(p.read_text(encoding="utf-8").replace(MODELO_31B, MODELO_12B), encoding="utf-8")
    (tmp / "prompts/system.md").write_text(prompt_12b, encoding="utf-8")
    (tmp / "configs/sampling.yaml").write_text(SAMPLING_12B, encoding="utf-8")
    (tmp / "eval_config.yaml").write_text(EVAL_CONFIG_12B, encoding="utf-8")
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
    guion = (AQUI / "notebook_c7_12b.py").read_text(encoding="utf-8")
    if not FUENTE_KIT.exists():
        print(f"error: no se encuentra {FUENTE_KIT} (descarga de réplica 1)", file=sys.stderr)
        return 2
    prompt_archivo = (FUENTE_KIT / "prompts/system.md").read_text(encoding="utf-8")
    if literal_del_guion(guion, "_SYSTEM_12B") != prompt_archivo:
        print(
            "error: _SYSTEM_12B del guion != prompts/system.md de la descarga de réplica 1",
            file=sys.stderr,
        )
        return 2
    if literal_del_guion(guion, "_SAMPLING_12B") != SAMPLING_12B:
        print("error: _SAMPLING_12B del guion != SAMPLING_12B de este script", file=sys.stderr)
        return 2
    if "max_time_minutes: 5.0" not in guion or MODELO_12B not in guion or "--hf-overrides" not in guion:
        print("error: el guion no escribe los deltas (5.0 min / modelo 12B / override)", file=sys.stderr)
        return 2
    try:
        huella = huella_config(kit_para_huella(prompt_archivo))
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if huella != HUELLA_12B:
        print(f"error: huella del kit de referencia = {huella}, se esperaba {HUELLA_12B}", file=sys.stderr)
        return 2

    celdas: dict[str, str] = {}
    matches = list(MARCADOR.finditer(guion))
    for i, m in enumerate(matches):
        fin = matches[i + 1].start() if i + 1 < len(matches) else len(guion)
        celdas[m.group(1)] = guion[m.start() : fin].strip() + "\n"
    for nombre in ("guardia", "instalacion", "versiones", "kit", "tareas", "servidor", "evaluacion"):
        if nombre not in celdas:
            print(f"error: falta la celda {nombre!r} en notebook_c7_12b.py", file=sys.stderr)
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
                "id": f"c7r1f-{i:02d}",
                "metadata": {},
                "outputs": [],
                "source": [line + "\n" for line in celdas[nombre].splitlines()],
            }
            for i, nombre in enumerate(orden)
        ],
    }
    (AQUI / "notebook_c7_12b.ipynb").write_text(
        json.dumps(ipynb, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (AQUI / "kernel-metadata.json").write_text(
        json.dumps(KERNEL_METADATA, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(f"notebook_c7_12b.ipynb: {len(orden)} celdas | huella {HUELLA_12B} | kernel-metadata.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
