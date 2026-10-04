"""Chequeo previo local de un notebook de Kaggle (`scripts/kaggle_preflight.py`)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts.kaggle_preflight import (
    EXIT_INVALID,
    EXIT_OK,
    WHEELHOUSE,
    codigo_comprobable,
    comprobar,
    main,
)

GUARDIA = (
    "import os\n"
    "W = '/kaggle/input/datasets/metric/gemma-4-developer-agent-wheelhouse'\n"
    "assert os.listdir(W), 'dataset sin montar'\n"
)
CELDAS = [GUARDIA, "import subprocess\nsubprocess.run(['nvidia-smi'])\n", "x = 1\n"]


def _meta(**cambios: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "usuario/prueba",
        "code_file": "nb.ipynb",
        "is_private": True,
        "enable_gpu": True,
        "enable_internet": False,
        "dataset_sources": [WHEELHOUSE],
        "competition_sources": ["gemma-4-developer-agent"],
        "docker_image": "gcr.io/imagen@sha256:abc",
        "machine_shape": "NvidiaL4",
    }
    base.update(cambios)
    return base


def _escribir(tmp_path: Path, meta: dict[str, Any] | None = None, celdas: list[str] | None = None) -> Path:
    cells = [{"cell_type": "code", "source": fuente} for fuente in (CELDAS if celdas is None else celdas)]
    (tmp_path / "nb.ipynb").write_text(json.dumps({"cells": cells}), encoding="utf-8")
    (tmp_path / "kernel-metadata.json").write_text(
        json.dumps(_meta() if meta is None else meta), encoding="utf-8"
    )
    return tmp_path


def _fallos(directorio: Path, tope: int = 75) -> list[str]:
    return [h.texto for h in comprobar(directorio, tope) if not h.ok]


def test_un_directorio_correcto_no_tiene_fallos_y_da_la_orden(tmp_path, capsys):
    directorio = _escribir(tmp_path)
    assert _fallos(directorio) == []
    assert main(["comprobar", str(directorio), "--tope-min", "75"]) == EXIT_OK
    salida = capsys.readouterr().out
    assert f'kaggle kernels push -p "{directorio}" -t 4500 --accelerator NvidiaL4' in salida
    assert "Gasta cuota de GPU: hasta 75 min" in salida


@pytest.mark.parametrize(
    ("cambio", "fragmento"),
    [
        ({"machine_shape": "NvidiaL4X4"}, "no está en"),
        ({"machine_shape": ""}, "no está en"),
        ({"docker_image": ""}, "docker_image vacío"),
        ({"is_private": False}, "is_private debe ser true"),
        ({"enable_internet": True}, "enable_internet debe ser false"),
        ({"competition_sources": []}, "competition_sources no incluye"),
        ({"code_file": "otro.ipynb"}, "code_file no apunta"),
        ({"enable_gpu": False}, "con enable_gpu distinto de true"),
    ],
)
def test_cada_metadato_malo_es_un_fallo_y_no_se_imprime_la_orden(tmp_path, capsys, cambio, fragmento):
    directorio = _escribir(tmp_path, _meta(**cambio))
    assert any(fragmento in texto for texto in _fallos(directorio))
    assert main(["comprobar", str(directorio), "--tope-min", "75"]) == EXIT_INVALID
    captura = capsys.readouterr()
    assert "kaggle kernels push" not in captura.out
    assert "NO SUBIR" in captura.err


def test_sin_gpu_no_exige_acelerador_ni_nvidia_smi(tmp_path, capsys):
    directorio = _escribir(tmp_path, _meta(enable_gpu=False, machine_shape="None"), [GUARDIA, "x = 1\n"])
    assert _fallos(directorio) == []
    assert main(["comprobar", str(directorio), "--tope-min", "30"]) == EXIT_OK
    salida = capsys.readouterr().out
    assert "--accelerator" not in salida and "Gasta cuota" not in salida


def test_una_celda_con_error_de_sintaxis_se_nombra_por_su_numero(tmp_path):
    directorio = _escribir(tmp_path, celdas=[GUARDIA, "subprocess.run(['nvidia-smi'])\n", "print('\n')\n"])
    fallos = _fallos(directorio)
    assert len(fallos) == 1 and "celda 3" in fallos[0]


def test_las_magias_de_ipython_no_cuentan_como_error_de_sintaxis(tmp_path):
    celdas = [GUARDIA, "!nvidia-smi\n%time x = 1\nif True:\n    !ls\n"]
    assert _fallos(_escribir(tmp_path, celdas=celdas)) == []
    assert codigo_comprobable("if True:\n    !ls") == "if True:\n    pass"


@pytest.mark.parametrize(
    "primera",
    ["x = 1\n", "W = 'gemma-4-developer-agent-wheelhouse'\n", "assert True\n"],
)
def test_sin_guardia_del_dataset_en_la_primera_celda_es_un_fallo(tmp_path, primera):
    directorio = _escribir(tmp_path, celdas=[primera, "subprocess.run(['nvidia-smi'])\n", GUARDIA])
    assert any("no es una guardia" in texto for texto in _fallos(directorio))


def test_con_gpu_y_sin_nvidia_smi_es_un_fallo(tmp_path):
    assert any("nvidia-smi" in texto for texto in _fallos(_escribir(tmp_path, celdas=[GUARDIA, "x = 1\n"])))


def test_una_credencial_en_el_notebook_es_un_fallo(tmp_path):
    celdas = [*CELDAS, "import os\nos.environ['T'] = 'KGAT_" + "a1b2c3d4e5f6" + "'\n"]
    assert any("credencial" in texto for texto in _fallos(_escribir(tmp_path, celdas=celdas)))


@pytest.mark.parametrize("tope", [0, -5, 241])
def test_el_tope_es_obligatorio_y_acotado(tmp_path, tope):
    assert any("--tope-min" in texto for texto in _fallos(_escribir(tmp_path), tope))


@pytest.mark.parametrize(
    ("archivo", "contenido"),
    [
        ("kernel-metadata.json", "{no es json"),
        ("kernel-metadata.json", "[]"),
        ("nb.ipynb", "{no es json"),
        ("nb.ipynb", '{"cells": "x"}'),
        ("nb.ipynb", '{"cells": []}'),
        ("nb.ipynb", '{"cells": [null]}'),
    ],
)
def test_archivos_ilegibles_o_mal_formados_salen_con_2_sin_traza(tmp_path, capsys, archivo, contenido):
    directorio = _escribir(tmp_path)
    (directorio / archivo).write_text(contenido, encoding="utf-8")
    assert main(["comprobar", str(directorio), "--tope-min", "75"]) == EXIT_INVALID
    assert "Traceback" not in capsys.readouterr().err


def test_un_directorio_sin_metadatos_sale_con_2(tmp_path):
    assert main(["comprobar", str(tmp_path), "--tope-min", "75"]) == EXIT_INVALID
