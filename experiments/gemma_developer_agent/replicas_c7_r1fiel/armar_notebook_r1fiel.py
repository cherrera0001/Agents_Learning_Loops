"""Arma el notebook de Kaggle del sexto brazo R1-FIEL desde ``notebook_c7_r1fiel.py``.

Copia del patrón de ``replicas_c7_thinking/armar_notebook_thinking.py`` con la semántica propia
de este brazo (concilio C7 Fase 4, 2026-10-17; REESPECIFICADO el 2026-10-18 a 5.0 min): **dos
deltas puros de configuración** respecto a la condición 7 —(1) ``configs/sampling.yaml`` con
``thinking_budget: 0`` (apagado real; el resto idéntico a la condición 7, incluido
``include_thoughts: true``) y (2) ``eval_config.yaml`` con ``max_time_minutes: 5.0``. El prompt NO
cambia: es byte-idéntico al de la condición 7. Antes de escribir nada:

1. Verifica que el literal ``_SYSTEM_R1FIEL`` del guion == ``prompts/system.md`` de la descarga
   local de réplica 1 (proveniencia verificada, gitignored) y que el literal ``_SAMPLING_R1FIEL``
   coincide con la constante ``SAMPLING_R1FIEL``; y que el guion escribe el eval_config con
   ``max_time_minutes: 5.0``.
2. Monta el kit de referencia desde esa descarga sin ``adapters/``, con el ``system.md`` de la
   propia descarga, el ``sampling.yaml`` de la variante y el ``eval_config.yaml`` de la variante,
   y exige que la huella recomputada == ``HUELLA_R1FIEL``.

Reespecificación 2026-10-18 (decisión del orquestador con evidencia del envelope del auditor):
el valor original 6.0 min se movió a 5.0. Razones: (a) regla pública no archivada atribuida al
equipo de Google en los foros («~5,5 min/tarea incl. setup; even 6 min cap is out of reach») —
NO verificada desde el repo (muro de cookies de Kaggle); ante la duda, 5.0 es seguro bajo
cualquiera de los dos muros; (b) 5.0 min está probado en producción (sub-019, 0.17, ~15,4 h de
evaluación sin corte de sesión); (c) la ciencia mejora: R1-fiel@5.0 es un A/B limpio contra
sub-019@5.0 aislando ``thinking_budget: 0`` (mismo muro, mismo prompt, misma configuración base);
(d) el envelope de 12 h sobra a 5.0 (562-698 min según setup). El valor 6.0 queda descartado
para envío; si se quiere medir H3 (más minutos) el lunes, es medición local pura, no candidato.

El resto del kit no se versiona (los tres archivos de plantilla son contenido de la competencia).

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
HUELLA_R1FIEL = "5e1638518420"
FUENTE_KIT = AQUI.parent / "data/replicas_c7/replica_1/c7_submission"
SAMPLING_R1FIEL = (
    "temperature: 0.2\n"
    "top_p: 0.95\n"
    "max_output_tokens: 8192\n"
    "thinking_config:\n"
    "  thinking_budget: 0\n"
    "  include_thoughts: true\n"
)
EVAL_CONFIG_R1FIEL = (
    "evaluation:\n  timeout_seconds: 60\n  max_tool_calls: 60\n  max_time_minutes: 5.0\n  max_turns: 100\n"
)

KERNEL_METADATA = {
    "id": "cs4all/c7-r1fiel-condicion-7",
    "title": "c7-r1fiel-condicion-7",
    "code_file": "notebook_c7_r1fiel.ipynb",
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


def kit_para_huella(prompt_r1fiel: str) -> Path:
    """Monta el kit de referencia: réplica 1 sin adapters + system.md, sampling y eval_config."""
    if not FUENTE_KIT.exists():
        raise FileNotFoundError(
            f"no se encuentra {FUENTE_KIT}; se necesita la descarga local de réplica 1 "
            "(gitignored) para recomputar la huella sin versionar contenido de la competencia"
        )
    tmp = Path(tempfile.mkdtemp(prefix="kit_r1fiel_huella_")) / "kit"
    shutil.copytree(FUENTE_KIT, tmp)
    shutil.rmtree(tmp / "adapters", ignore_errors=True)
    (tmp / "prompts/system.md").write_text(prompt_r1fiel, encoding="utf-8")
    (tmp / "configs/sampling.yaml").write_text(SAMPLING_R1FIEL, encoding="utf-8")
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
    guion = (AQUI / "notebook_c7_r1fiel.py").read_text(encoding="utf-8")
    if not FUENTE_KIT.exists():
        print(f"error: no se encuentra {FUENTE_KIT} (descarga de réplica 1)", file=sys.stderr)
        return 2
    prompt_archivo = (FUENTE_KIT / "prompts/system.md").read_text(encoding="utf-8")
    if literal_del_guion(guion, "_SYSTEM_R1FIEL") != prompt_archivo:
        print(
            "error: _SYSTEM_R1FIEL del guion != prompts/system.md de la descarga de réplica 1",
            file=sys.stderr,
        )
        return 2
    if literal_del_guion(guion, "_SAMPLING_R1FIEL") != SAMPLING_R1FIEL:
        print("error: _SAMPLING_R1FIEL del guion != SAMPLING_R1FIEL de este script", file=sys.stderr)
        return 2
    if "max_time_minutes: 5.0" not in guion or "thinking_budget: 0" not in guion:
        print("error: el guion no escribe los deltas del brazo (5.0 min / budget 0)", file=sys.stderr)
        return 2
    try:
        huella = huella_config(kit_para_huella(prompt_archivo))
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if huella != HUELLA_R1FIEL:
        print(f"error: huella del kit de referencia = {huella}, se esperaba {HUELLA_R1FIEL}", file=sys.stderr)
        return 2

    celdas: dict[str, str] = {}
    matches = list(MARCADOR.finditer(guion))
    for i, m in enumerate(matches):
        fin = matches[i + 1].start() if i + 1 < len(matches) else len(guion)
        celdas[m.group(1)] = guion[m.start() : fin].strip() + "\n"
    for nombre in ("guardia", "instalacion", "versiones", "kit", "tareas", "servidor", "evaluacion"):
        if nombre not in celdas:
            print(f"error: falta la celda {nombre!r} en notebook_c7_r1fiel.py", file=sys.stderr)
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
    (AQUI / "notebook_c7_r1fiel.ipynb").write_text(
        json.dumps(ipynb, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (AQUI / "kernel-metadata.json").write_text(
        json.dumps(KERNEL_METADATA, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(f"notebook_c7_r1fiel.ipynb: {len(orden)} celdas | huella {HUELLA_R1FIEL} | kernel-metadata.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
