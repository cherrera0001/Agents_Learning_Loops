"""Controles de ruedas del chequeo previo (#100): referencia, device_map, imagen y huecos sin aceptar."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any

import pytest

from scripts.kaggle_preflight import (
    EXIT_INVALID,
    EXIT_OK,
    WHEELHOUSE,
    comprobar,
    comprobar_instalacion,
    comprobar_para_subir,
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
INSTALACION = (
    "# Instala el conjunto entero\n"
    "import subprocess, sys, glob\n"
    "wheels = sorted(glob.glob(W + '/*.whl'))\n"
    "\n"
    "subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '--no-deps', *wheels], check=True)\n"
)
INSTALACION_A_MANO = (
    "import subprocess, sys, glob\n"
    "todas = sorted(glob.glob(W + '/*.whl'))\n"
    "wheels = [w for w in todas if w.split('/')[-1].startswith(('torch', 'peft'))]\n"
    "subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '--no-deps', *wheels], check=True)\n"
)
NVIDIA = "import subprocess\nsubprocess.run(['nvidia-smi'])\n"


def _meta() -> dict[str, Any]:
    return {
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


def _kernel(carpeta: Path, celdas: list[str], *, gpu: bool = True) -> Path:
    carpeta.mkdir(parents=True, exist_ok=True)
    cells = [{"cell_type": "code", "source": c} for c in celdas]
    (carpeta / "nb.ipynb").write_text(json.dumps({"cells": cells}), encoding="utf-8")
    meta = _meta() if gpu else {**_meta(), "enable_gpu": False, "machine_shape": "None"}
    (carpeta / "kernel-metadata.json").write_text(json.dumps(meta), encoding="utf-8")
    return carpeta


def _rueda(carpeta: Path, nombre: str, version: str, requiere: list[str] | None = None) -> Path:
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / f"{nombre}-{version}-py3-none-any.whl"
    cuerpo = f"Metadata-Version: 2.1\nName: {nombre}\nVersion: {version}\n"
    cuerpo += "".join(f"Requires-Dist: {r}\n" for r in requiere or [])
    with zipfile.ZipFile(ruta, "w") as z:
        z.writestr(f"{nombre}-{version}.dist-info/METADATA", cuerpo)
    return ruta


def _imagen(ruta: Path, paquetes: dict[str, str]) -> Path:
    ruta.write_text(json.dumps(paquetes), encoding="utf-8")
    return ruta


def _textos(hallazgos, *, ok: bool) -> list[str]:
    return [h.texto for h in hallazgos if h.ok is ok and not h.aviso]


def _avisos(hallazgos) -> list[str]:
    return [h.texto for h in hallazgos if h.aviso]


# --- a. referencia ---


def test_la_celda_de_instalacion_igual_a_la_referencia_pasa_aunque_cambien_comentarios_y_blancos(tmp_path):
    ref = _kernel(tmp_path / "ref", [GUARDIA, INSTALACION, NVIDIA])
    nb = _kernel(
        tmp_path / "nb",
        [
            GUARDIA,
            "# otro comentario\n\n" + INSTALACION.replace("# Instala el conjunto entero\n", ""),
            NVIDIA,
        ],
    )
    h = comprobar_para_subir(nb, 75, referencia=ref)
    assert not any("celda de instalación" in t for t in _textos(h, ok=False))
    assert any("de la referencia están enteras" in t for t in _textos(h, ok=True))


def test_un_subconjunto_elegido_a_mano_falla_con_el_diff(tmp_path):
    ref = _kernel(tmp_path / "ref", [GUARDIA, INSTALACION, NVIDIA])
    nb = _kernel(tmp_path / "nb", [GUARDIA, INSTALACION_A_MANO, NVIDIA])
    fallos = _textos(comprobar_para_subir(nb, 75, referencia=ref), ok=False)
    (mensaje,) = [t for t in fallos if "no es la de la referencia" in t]
    assert "--- referencia" in mensaje and "+++ notebook" in mensaje
    assert "-wheels = sorted(glob.glob(W + '/*.whl'))" in mensaje
    assert "startswith(('torch', 'peft'))" in mensaje


def test_sin_referencia_un_kernel_sin_gpu_que_instala_ruedas_recibe_un_aviso_y_no_falla(tmp_path, capsys):
    nb = _kernel(tmp_path / "nb", [GUARDIA, INSTALACION, NVIDIA], gpu=False)
    h = comprobar_para_subir(nb, 75)
    assert any("no se dio --referencia" in t for t in _avisos(h))
    assert not any("referencia" in t for t in _textos(h, ok=False))
    assert main(["comprobar", str(nb), "--tope-min", "75"]) == EXIT_OK
    assert "[AVISO]" in capsys.readouterr().out


def test_sin_referencia_ni_imagen_un_kernel_con_gpu_falla_salvo_que_alguien_lo_acepte(tmp_path, capsys):
    nb = _kernel(tmp_path / "nb", [GUARDIA, INSTALACION, NVIDIA])
    fallos = _textos(comprobar_para_subir(nb, 75), ok=False)
    assert any("no se dio --referencia" in t for t in fallos)
    assert any("no se dio --imagen" in t for t in fallos)
    assert main(["comprobar", str(nb), "--tope-min", "75"]) == EXIT_INVALID
    capsys.readouterr()
    aceptado = comprobar_para_subir(nb, 75, aceptado_por="el dueño")
    assert _textos(aceptado, ok=False) == []
    assert sum("Aceptado por: el dueño" in t for t in _avisos(aceptado)) == 2
    assert main(["comprobar", str(nb), "--tope-min", "75", "--aceptado-por", "el dueño"]) == EXIT_OK


def test_importar_peft_de_la_imagen_exige_el_inventario_aunque_no_instale_ruedas(tmp_path):
    nb = _kernel(tmp_path / "nb", [GUARDIA, NVIDIA, "from peft import LoraConfig\n"])
    fallos = _textos(comprobar_para_subir(nb, 75), ok=False)
    assert any("no se dio --imagen" in t for t in fallos)
    assert not any("--referencia" in t for t in fallos)


def test_pasar_ruedas_no_activa_el_control_del_arnes_si_el_notebook_no_lo_importa(tmp_path):
    nb = _kernel(tmp_path / "nb", [GUARDIA, INSTALACION, NVIDIA])
    ruedas = tmp_path / "ruedas"
    _rueda(ruedas, "app", "1.0")
    imagen = _imagen(tmp_path / "imagen.json", {"numpy": "2.1.0"})
    h = comprobar_para_subir(nb, 75, ruedas_instaladas=ruedas, imagen=imagen, aceptado_por="yo")
    assert _textos(h, ok=False) == []
    assert any("Cierre de dependencias" in t for t in _textos(h, ok=True))
    con_ruedas = comprobar_para_subir(nb, 75, ruedas=ruedas, aceptado_por="yo")
    assert (
        _textos(con_ruedas, ok=False) != []
    )  # --ruedas sí activa el control del arnés (comportamiento previo)


def test_la_celda_probada_entera_con_lineas_añadidas_alrededor_pasa_con_aviso(tmp_path):
    ref = _kernel(tmp_path / "ref", [GUARDIA, INSTALACION, NVIDIA])
    nb = _kernel(tmp_path / "nb", [GUARDIA, INSTALACION + "print('ENTRENO antes')\nx = 1\n", NVIDIA])
    h = comprobar_para_subir(nb, 75, referencia=ref)
    assert not any("referencia" in t for t in _textos(h, ok=False))
    assert any("entera en el notebook" in t and "2 líneas más" in t for t in _avisos(h))


def test_una_linea_de_la_celda_probada_cambiada_o_separada_falla(tmp_path):
    ref = _kernel(tmp_path / "ref", [GUARDIA, INSTALACION, NVIDIA])
    cambiada = INSTALACION.replace("'--no-deps', ", "")
    separada = INSTALACION.replace("wheels = ", "x = 1\nwheels = ")
    for nombre, celda in (("cambiada", cambiada), ("separada", separada)):
        nb = _kernel(tmp_path / nombre, [GUARDIA, celda, NVIDIA])
        fallos = _textos(comprobar_para_subir(nb, 75, referencia=ref), ok=False)
        assert any("no es la de la referencia" in t for t in fallos), nombre


def test_pip3_y_find_links_cuentan_como_instalacion_de_ruedas(tmp_path):
    orden = "'pip3 install --no-index --find-links /tmp/w loguru'"
    celda = f"import subprocess\nsubprocess.run({orden}, shell=True)\n"
    nb = _kernel(tmp_path / "nb", [GUARDIA, celda, NVIDIA], gpu=False)
    assert any("no se dio --referencia" in t for t in _avisos(comprobar_para_subir(nb, 75)))


def test_una_referencia_se_lee_sin_kernel_metadata_si_hay_un_solo_notebook(tmp_path):
    ref = tmp_path / "ref"
    ref.mkdir()
    cells = [{"cell_type": "code", "source": c} for c in (GUARDIA, INSTALACION)]
    (ref / "notebook.ipynb").write_text(json.dumps({"cells": cells}), encoding="utf-8")
    nb = _kernel(tmp_path / "nb", [GUARDIA, INSTALACION_A_MANO, NVIDIA])
    fallos = _textos(comprobar_para_subir(nb, 75, referencia=ref), ok=False)
    assert any("no es la de la referencia" in t for t in fallos)
    (ref / "otro.ipynb").write_text("{}", encoding="utf-8")
    assert any(
        "No se pudo leer el notebook de --referencia" in t
        for t in _textos(comprobar_para_subir(nb, 75, referencia=ref), ok=False)
    )


def test_un_notebook_sin_instalacion_no_recibe_aviso_de_referencia(tmp_path):
    nb = _kernel(tmp_path / "nb", [GUARDIA, NVIDIA])
    assert not any("referencia" in t for t in _avisos(comprobar_para_subir(nb, 75)))


def test_una_referencia_ilegible_o_sin_instalacion_falla(tmp_path):
    nb = _kernel(tmp_path / "nb", [GUARDIA, INSTALACION, NVIDIA])
    sin = _kernel(tmp_path / "sin", [GUARDIA, NVIDIA])
    assert any(
        "sin celda de instalación" in t or "no tiene celda de instalación" in t
        for t in _textos(comprobar_para_subir(nb, 75, referencia=sin), ok=False)
    )
    assert any(
        "No se pudo leer el notebook de --referencia" in t
        for t in _textos(comprobar_para_subir(nb, 75, referencia=tmp_path / "nada"), ok=False)
    )


def test_la_cli_con_referencia_distinta_sale_con_2_y_no_imprime_la_orden(tmp_path, capsys):
    ref = _kernel(tmp_path / "ref", [GUARDIA, INSTALACION, NVIDIA])
    nb = _kernel(tmp_path / "nb", [GUARDIA, INSTALACION_A_MANO, NVIDIA])
    assert main(["comprobar", str(nb), "--tope-min", "75", "--referencia", str(ref)]) == EXIT_INVALID
    captura = capsys.readouterr()
    assert "kaggle kernels push" not in captura.out and "NO SUBIR" in captura.err


# --- b. device_map ---


def _fallos_device_map(tmp_path: Path, celda: str) -> list[str]:
    nb = _kernel(tmp_path / "nb", [GUARDIA, NVIDIA, celda])
    return [t for t in _textos(comprobar(nb, 75), ok=False) if "device_map" in t]


@pytest.mark.parametrize(
    "celda",
    [
        "m = AutoModelForCausalLM.from_pretrained(p, device_map='auto')\n",
        "m = transformers.AutoModel.from_pretrained(p, torch_dtype=t, device_map=mapa)\n",
        "m = from_pretrained(p, device_map='balanced')\n",
        "m = M.from_pretrained(p, **opciones, device_map='auto')\n",
    ],
)
def test_device_map_sin_max_memory_falla_con_celda_y_linea(tmp_path, celda):
    (mensaje,) = _fallos_device_map(tmp_path, "x = 1\n" + celda)
    assert "celda 3, línea 2" in mensaje


@pytest.mark.parametrize(
    "celda",
    [
        "m = M.from_pretrained(p, device_map='auto', max_memory={0: '16GiB'})\n",
        "m = M.from_pretrained(p, device_map={'': 'cpu'})\n",
        "m = M.from_pretrained(p, device_map='cpu')\n",
        "m = M.from_pretrained(p)\n",
        "m = M.otra_cosa(p, device_map='auto')\n",
    ],
)
def test_device_map_con_max_memory_o_en_cpu_o_ausente_no_falla(tmp_path, celda):
    assert _fallos_device_map(tmp_path, celda) == []


# --- c. imagen ---


def _directorio_con_ruedas(tmp_path: Path) -> tuple[Path, Path]:
    nb = _kernel(tmp_path / "nb", [GUARDIA, INSTALACION, NVIDIA])
    return nb, tmp_path / "ruedas"


def test_el_cierre_completo_contra_imagen_mas_ruedas_pasa(tmp_path):
    nb, ruedas = _directorio_con_ruedas(tmp_path)
    _rueda(
        ruedas,
        "app",
        "1.0",
        ["loguru>=0.7", "numpy<3", "pywin32; sys_platform == 'win32'", "rich; extra == 'x'"],
    )
    _rueda(ruedas, "loguru", "0.7.3")
    imagen = _imagen(tmp_path / "imagen.json", {"numpy": "2.1.0"})
    h = comprobar_instalacion(nb, ruedas, None, imagen, "yo")
    assert _textos(h, ok=False) == []
    assert any("Cierre de dependencias" in t for t in _textos(h, ok=True))


def test_falta_una_dependencia_que_ni_la_imagen_ni_las_ruedas_traen(tmp_path):
    nb, ruedas = _directorio_con_ruedas(tmp_path)
    _rueda(ruedas, "app", "1.0", ["loguru>=0.7"])
    imagen = _imagen(tmp_path / "imagen.json", {"numpy": "2.1.0"})
    (mensaje,) = [
        t
        for t in _textos(comprobar_instalacion(nb, ruedas, None, imagen, "yo"), ok=False)
        if "ni la imagen ni las ruedas" in t
    ]
    assert "loguru (pedida por app)" in mensaje


def test_una_version_que_no_cumple_el_requisito_falla(tmp_path):
    nb, ruedas = _directorio_con_ruedas(tmp_path)
    _rueda(ruedas, "app", "1.0", ["numpy>=2.2"])
    imagen = _imagen(tmp_path / "imagen.json", {"numpy": "2.1.0"})
    fallos = _textos(comprobar_instalacion(nb, ruedas, None, imagen, "yo"), ok=False)
    assert any("app pide numpy>=2.2 y hay 2.1.0" in t for t in fallos)


def test_la_version_de_la_rueda_sustituye_a_la_de_la_imagen(tmp_path):
    nb, ruedas = _directorio_con_ruedas(tmp_path)
    _rueda(ruedas, "app", "1.0", ["numpy>=2.2"])
    _rueda(ruedas, "numpy", "2.3.0")
    imagen = _imagen(tmp_path / "imagen.json", {"numpy": "2.1.0"})
    assert _textos(comprobar_instalacion(nb, ruedas, None, imagen, "yo"), ok=False) == []


def test_el_conflicto_conocido_peft_con_torchao_falla_con_su_explicacion(tmp_path):
    nb, ruedas = _directorio_con_ruedas(tmp_path)
    _rueda(ruedas, "app", "1.0")
    imagen = _imagen(tmp_path / "imagen.json", {"peft": "0.19.1", "torchao": "0.10.0"})
    (mensaje,) = [
        t
        for t in _textos(comprobar_instalacion(nb, ruedas, None, imagen, "yo"), ok=False)
        if "Conflicto conocido" in t
    ]
    assert "peft 0.19.1 con torchao 0.10.0" in mensaje and "torchao a 0.16" in mensaje


@pytest.mark.parametrize(
    "paquetes",
    [
        {"peft": "0.19.1"},
        {"torchao": "0.10.0"},
        {"peft": "0.20.0", "torchao": "0.10.0"},
        {"peft": "0.19.1", "torchao": "0.16.0"},
    ],
)
def test_sin_las_dos_condiciones_no_hay_conflicto(tmp_path, paquetes):
    nb, ruedas = _directorio_con_ruedas(tmp_path)
    _rueda(ruedas, "app", "1.0")
    imagen = _imagen(tmp_path / "imagen.json", paquetes)
    assert _textos(comprobar_instalacion(nb, ruedas, None, imagen, "yo"), ok=False) == []


def test_el_conflicto_se_ve_tambien_cuando_una_rueda_trae_el_paquete(tmp_path):
    nb, ruedas = _directorio_con_ruedas(tmp_path)
    _rueda(ruedas, "peft", "0.19.1")
    imagen = _imagen(tmp_path / "imagen.json", {"torchao": "0.10.0"})
    assert any(
        "Conflicto conocido" in t
        for t in _textos(comprobar_instalacion(nb, ruedas, None, imagen, "yo"), ok=False)
    )


def test_imagen_ilegible_o_sin_ruedas_y_el_aviso_sin_imagen(tmp_path):
    nb, ruedas = _directorio_con_ruedas(tmp_path)
    _rueda(ruedas, "app", "1.0")
    mala = tmp_path / "mala.json"
    mala.write_text("[1, 2]", encoding="utf-8")
    assert any(
        "No se pudo leer --imagen" in t
        for t in _textos(comprobar_instalacion(nb, None, None, mala, "yo"), ok=False)
    )
    buena = _imagen(tmp_path / "ok.json", {"numpy": "2.1.0"})
    assert any("sin --ruedas" in t for t in _avisos(comprobar_instalacion(nb, None, None, buena, "yo")))
    assert any(
        "no se dio --imagen" in t for t in _avisos(comprobar_instalacion(nb, ruedas, None, None, "yo"))
    )
    assert any(
        "no se dio --imagen" in t for t in _textos(comprobar_instalacion(nb, ruedas, None, None), ok=False)
    )


def test_los_nombres_con_punto_o_guion_bajo_son_la_misma_distribucion(tmp_path):
    nb, ruedas = _directorio_con_ruedas(tmp_path)
    _rueda(ruedas, "app", "1.0", ["jaraco_classes>=3", "ruamel.yaml>=0.17"])
    imagen = _imagen(tmp_path / "imagen.json", {"jaraco.classes": "3.4.0", "ruamel_yaml": "0.18.0"})
    assert _textos(comprobar_instalacion(nb, ruedas, None, imagen, "yo"), ok=False) == []


def test_una_version_ilegible_en_la_imagen_es_un_fallo(tmp_path):
    nb, ruedas = _directorio_con_ruedas(tmp_path)
    _rueda(ruedas, "app", "1.0", ["numpy>=2"])
    imagen = _imagen(tmp_path / "imagen.json", {"numpy": "no-es-version"})
    fallos = _textos(comprobar_instalacion(nb, ruedas, None, imagen, "yo"), ok=False)
    assert any("no se puede leer" in t for t in fallos)
    imagen = _imagen(tmp_path / "i2.json", {"peft": "???", "torchao": "0.10.0"})
    assert any(
        "Versión ilegible" in t
        for t in _textos(comprobar_instalacion(nb, ruedas, None, imagen, "yo"), ok=False)
    )


def test_la_cli_con_imagen_en_conflicto_sale_con_2(tmp_path, capsys):
    nb, ruedas = _directorio_con_ruedas(tmp_path)
    _rueda(ruedas, "app", "1.0")
    imagen = _imagen(tmp_path / "imagen.json", {"peft": "0.19.1", "torchao": "0.10.0"})
    codigo = main(
        ["comprobar", str(nb), "--tope-min", "75", "--ruedas", str(ruedas), "--imagen", str(imagen)]
    )
    salida = capsys.readouterr().out
    assert codigo == EXIT_INVALID and "kaggle kernels push" not in salida
    assert "[FALLA] Conflicto conocido: peft 0.19.1 con torchao 0.10.0" in salida


# --- d. INFORME.md ---


def _con_informe(tmp_path: Path, texto: str) -> list[str]:
    nb = _kernel(tmp_path / "nb", [GUARDIA, NVIDIA])
    (nb / "INFORME.md").write_text(texto, encoding="utf-8")
    return [t for t in _textos(comprobar(nb, 75), ok=False) if "INFORME.md" in t]


def test_un_hueco_sin_aceptar_en_el_informe_bloquea(tmp_path):
    (mensaje,) = _con_informe(tmp_path, "# Informe\n\nSin comprobar CUDA ni memoria.\n\nOtra cosa.\n")
    assert "línea 3" in mensaje


@pytest.mark.parametrize(
    "texto",
    [
        "Sin comprobar CUDA ni memoria. Aceptado por: el dueño\n",
        "sin comprobar la memoria\nAceptado por: el dueño\n",
        "Aceptado por: el dueño\n\nsin comprobar la memoria\n",
        "Nada pendiente.\n",
    ],
)
def test_un_hueco_aceptado_al_lado_o_sin_huecos_no_bloquea(tmp_path, texto):
    assert _con_informe(tmp_path, texto) == []


def test_aceptado_por_vacio_o_lejos_no_cuenta(tmp_path):
    assert _con_informe(tmp_path, "sin comprobar la memoria\nAceptado por:\n")
    assert _con_informe(tmp_path, "sin comprobar la memoria\notra línea\nAceptado por: el dueño\n")


def test_sin_informe_no_hay_hallazgo_de_informe(tmp_path):
    nb = _kernel(tmp_path / "nb", [GUARDIA, NVIDIA])
    assert not any("INFORME.md" in h.texto for h in comprobar(nb, 75))


def test_el_informe_del_directorio_padre_tambien_se_lee(tmp_path):
    nb = _kernel(tmp_path / "lora" / "kernel", [GUARDIA, NVIDIA])
    (tmp_path / "lora" / "INFORME.md").write_text("Sin comprobar la memoria.\n", encoding="utf-8")
    assert any("INFORME.md declara algo sin comprobar" in t for t in _textos(comprobar(nb, 75), ok=False))


def test_el_informe_indicado_con_la_opcion_se_lee_y_si_no_existe_falla(tmp_path):
    nb = _kernel(tmp_path / "nb", [GUARDIA, NVIDIA])
    otro = tmp_path / "informe_constructor.md"
    otro.write_text("Pendiente: sin verificar CUDA.\n", encoding="utf-8")
    assert any("informe_constructor.md declara" in t for t in _textos(comprobar(nb, 75, otro), ok=False))
    assert any("no es un archivo" in t for t in _textos(comprobar(nb, 75, tmp_path / "no.md"), ok=False))


@pytest.mark.parametrize(
    "texto",
    [
        "Sin verificar la memoria.\n",
        "Esto está sin\ncomprobar todavía.\n",
        "SIN   COMPROBAR la memoria.\nAceptado por: nadie\n",
        "sin comprobar la memoria\nAceptado por: -\n",
    ],
)
def test_otras_formas_de_declarar_el_hueco_tambien_bloquean(tmp_path, texto):
    assert _con_informe(tmp_path, texto)


def test_dos_huecos_con_un_solo_aceptado_lejos_bloquean_el_que_queda_sin_aceptar(tmp_path):
    texto = "sin comprobar CUDA\nAceptado por: el dueño\n\nnota\nsin comprobar memoria\notra\n"
    (mensaje,) = _con_informe(tmp_path, texto)
    assert "línea 5" in mensaje and "línea 1" not in mensaje


# --- device_map: casos que no bloquean y el reparto automático con un modelo comprimido ---


@pytest.mark.parametrize(
    "celda",
    [
        "m = M.from_pretrained(p, device_map='cuda:0')\n",
        "m = M.from_pretrained(p, device_map=0)\n",
        "m = M.from_pretrained(p, device_map=None)\n",
    ],
)
def test_device_map_a_un_dispositivo_no_bloquea(tmp_path, celda):
    assert _fallos_device_map(tmp_path, celda) == []


COMPRIMIDO = "from transformers import CompressedTensorsConfig\n"


def test_reparto_automatico_con_modelo_comprimido_falla_aunque_lleve_max_memory(tmp_path):
    celda = COMPRIMIDO + "m = M.from_pretrained(p, device_map='auto', max_memory={0: '16GiB'})\n"
    (mensaje,) = _fallos_device_map(tmp_path, celda)
    assert "Reparto automático" in mensaje and "celda 3" in mensaje and "infer_auto_device_map" in mensaje


def test_reparto_automatico_escrito_como_cadena_o_en_un_dict_tambien_se_ve(tmp_path):
    celda = COMPRIMIDO + "codigo = '''\nkw['device_map'] = \"auto\"\nkw['max_memory'] = {}\n'''\n"
    assert any("Reparto automático" in t for t in _fallos_device_map(tmp_path, celda))
    celda = COMPRIMIDO + "kw = dict(device_map='balanced')\n"
    assert any("Reparto automático" in t for t in _fallos_device_map(tmp_path, celda))


def test_un_comentario_que_cita_el_reparto_automatico_no_bloquea_pero_el_codigo_en_una_cadena_si(tmp_path):
    comentado = '# v2: device_map="auto" reparte por el tamaño comprimido\n'
    assert _fallos_device_map(tmp_path, COMPRIMIDO + comentado) == []
    en_cadena = 'CELDA = \'# v2: device_map="auto"\\nkw["device_map"] = "auto"\\n\'\n'
    assert any("Reparto automático" in t for t in _fallos_device_map(tmp_path, COMPRIMIDO + en_cadena))
    solo_comentario = "CELDA = '# v2: device_map=\"auto\"\\nx = 1\\n'\n"
    assert _fallos_device_map(tmp_path, COMPRIMIDO + solo_comentario) == []


def test_reparto_automatico_sin_modelo_comprimido_o_un_mapa_calculado_no_bloquea(tmp_path):
    assert _fallos_device_map(tmp_path, "kw = dict(device_map='auto', max_memory={})\n") == []
    celda = COMPRIMIDO + "mapa = infer_auto_device_map(vacio, max_memory=mm)\nkw = dict(device_map=mapa)\n"
    assert _fallos_device_map(tmp_path, celda) == []
