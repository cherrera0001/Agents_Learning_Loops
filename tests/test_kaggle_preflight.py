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
    "def directorio_con_ruedas(raiz='/kaggle/input'):\n"
    "    print('GUARDIA entradas:', sorted(os.listdir(raiz)))\n"
    "    hallados = [\n"
    "        d for d, _dirs, files in os.walk(raiz)\n"
    "        if any(f.startswith('swegemma-') and f.endswith('.whl') for f in files)\n"
    "    ]\n"
    "    if len(hallados) != 1:\n"
    "        raise RuntimeError('GUARDIA: se detiene antes de gastar cuota')\n"
    "    return hallados[0]\n"
    "W = directorio_con_ruedas()\n"
)
# La guardia de la versión 3 del notebook de prueba: busca «el único directorio con .whl». El chequeo la
# aprobaba leyéndola; ejecutada contra la estructura real encuentra dos (el del arnés y wheels/ de los
# datos de la competencia) y se detiene siempre.
GUARDIA_CUALQUIER_RUEDA = GUARDIA.replace("f.startswith('swegemma-') and ", "")
# La guardia que el chequeo aprobaba antes del 2026-10-04: nombra el dataset y lleva un assert, con una
# ruta que no existía en la sesión real.
GUARDIA_CON_RUTA_INVENTADA = (
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


def test_la_guardia_con_la_ruta_inventada_que_antes_se_aprobaba_ahora_falla(tmp_path):
    """Nombrar el dataset y llevar un assert no basta: esa guardia falló dentro de Kaggle."""
    directorio = _escribir(tmp_path, celdas=[GUARDIA_CON_RUTA_INVENTADA, *CELDAS[1:]])
    fallos = _fallos(directorio)
    assert any("Rutas fijas bajo /kaggle/input" in texto for texto in fallos)
    assert any("no es la guardia" in texto for texto in fallos)
    assert any("no se detiene" in texto for texto in fallos)


@pytest.mark.parametrize(
    ("primera", "fragmento"),
    [
        ("x = 1\n", "no es la guardia"),
        (GUARDIA.replace("os.walk(raiz)", "[]"), "no es la guardia"),
        (GUARDIA.replace("os.listdir(raiz)", "raiz"), "no es la guardia"),
        (GUARDIA.replace("'.whl'", "'.zip'"), "no es la guardia"),
        (GUARDIA.replace("raise RuntimeError(", "print("), "no se detiene"),
        (GUARDIA_CUALQUIER_RUEDA, "la guardia se detiene"),
        (
            GUARDIA.replace("len(hallados) != 1", "len(hallados) > 1").replace(
                "return hallados[0]", "return hallados[0] if hallados else None"
            ),
            "sin las ruedas del arnés",
        ),
        (GUARDIA + "import time\ntime.sleep(10)\n", "espera o reintenta"),
        (GUARDIA + "from adk_submission import VllmServer\n", "comparte celda con el servidor"),
    ],
)
def test_cada_defecto_de_la_guardia_es_un_fallo(tmp_path, primera, fragmento):
    directorio = _escribir(tmp_path, celdas=[primera, *CELDAS[1:]])
    assert any(fragmento in texto for texto in _fallos(directorio))


@pytest.mark.parametrize(
    "celda",
    [
        "DATA_DIR = '/kaggle/input/competitions/gemma-4-developer-agent'\n",
        "MODEL = '/kaggle/input/models/google/gemma-4/other/variante/2'\n",
        "W = '/kaggle/input/gemma-4-developer-agent-wheelhouse'\n",
    ],
)
def test_una_ruta_fija_bajo_la_entrada_en_cualquier_celda_es_un_fallo(tmp_path, celda):
    fallos = _fallos(_escribir(tmp_path, celdas=[*CELDAS, celda]))
    assert len(fallos) == 1 and "Rutas fijas bajo /kaggle/input" in fallos[0]


def test_la_raiz_de_entrada_y_el_directorio_de_trabajo_no_son_rutas_fijas(tmp_path):
    celdas = [*CELDAS, "import os\nprint(os.listdir('/kaggle/input'))\nopen('/kaggle/working/r.txt', 'w')\n"]
    assert _fallos(_escribir(tmp_path, celdas=celdas)) == []


def test_la_guardia_se_exige_aunque_no_haya_datasets_adjuntos(tmp_path):
    directorio = _escribir(tmp_path, _meta(dataset_sources=[], docker_image=""), ["x = 1\n", CELDAS[1]])
    assert any("no es la guardia" in texto for texto in _fallos(directorio))


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


def test_la_guardia_de_la_version_3_se_detiene_en_las_dos_disposiciones_reales(tmp_path):
    fallos = _fallos(_escribir(tmp_path, celdas=[GUARDIA_CUALQUIER_RUEDA, *CELDAS[1:]]))
    assert sum("la guardia se detiene" in texto for texto in fallos) == 2
    assert any("(lotes)" in texto for texto in fallos)
    assert any("(plana)" in texto for texto in fallos)


@pytest.mark.parametrize("disposicion", ["lotes", "plana"])
def test_el_arbol_de_entrada_tiene_dos_directorios_con_ruedas_y_uno_solo_del_arnes(tmp_path, disposicion):
    from scripts.kaggle_preflight import arbol_de_entrada

    arbol_de_entrada(tmp_path, disposicion)
    con_ruedas = {p.parent for p in tmp_path.rglob("*.whl")}
    del_arnes = {p.parent for p in tmp_path.rglob("swegemma-*.whl")}
    assert len(con_ruedas) == 2
    assert len(del_arnes) == 1
    assert next(iter(con_ruedas - del_arnes)).name == "wheels"
    assert len(list(tmp_path.rglob("config.json"))) == 1


def test_el_arbol_sin_ruedas_del_arnes_conserva_las_de_la_competencia(tmp_path):
    from scripts.kaggle_preflight import arbol_de_entrada

    arbol_de_entrada(tmp_path, "lotes", ruedas_arnes=False)
    assert [p.parent.name for p in tmp_path.rglob("*.whl")] == ["wheels"]


def test_ejecutar_guardia_devuelve_el_codigo_de_salida_y_no_cuelga(tmp_path):
    from scripts.kaggle_preflight import arbol_de_entrada, ejecutar_guardia

    arbol_de_entrada(tmp_path, "lotes")
    assert ejecutar_guardia(GUARDIA, tmp_path) == 0
    assert ejecutar_guardia(GUARDIA_CUALQUIER_RUEDA, tmp_path) != 0
    assert ejecutar_guardia("raise SystemExit(7)\n", tmp_path) == 7


def test_una_guardia_mal_escrita_no_se_ejecuta(tmp_path):
    fallos = _fallos(_escribir(tmp_path, celdas=["import os\nos.system('echo no')\n", *CELDAS[1:]]))
    assert any("no es la guardia" in texto for texto in fallos)
    assert not any("Ejecutada" in texto for texto in fallos)


SERVIDOR = "from adk_submission import VllmServer\ntry:\n    s = VllmServer(cfg)\n    s.start()\n"


def test_un_notebook_que_arranca_el_servidor_debe_leer_la_salida_de_la_excepcion(tmp_path):
    sin_salida = SERVIDOR + "except BaseException as exc:\n    print(open(s.log_path).read())\n    raise\n"
    fallos = _fallos(_escribir(tmp_path, celdas=[*CELDAS, sin_salida]))
    assert any("ServerStartupError.output" in texto for texto in fallos)


def test_leer_la_salida_de_la_excepcion_del_servidor_no_es_un_fallo(tmp_path):
    con_salida = (
        SERVIDOR + "except BaseException as exc:\n    print(getattr(exc, 'output', None))\n    raise\n"
    )
    assert _fallos(_escribir(tmp_path, celdas=[*CELDAS, con_salida])) == []


def test_sin_servidor_no_se_exige_leer_la_salida_de_la_excepcion(tmp_path):
    assert _fallos(_escribir(tmp_path)) == []
