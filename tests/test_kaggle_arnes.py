"""Guardas del arnés de Kaggle (#195): versiones ensayadas, imports contra las ruedas, listado del conjunto.

Sin red, sin token real y sin código del arnés: las «ruedas» son zips de relleno escritos aquí, con la forma
que importa (un módulo que se elimina, un nombre servido por ``__getattr__``). Sin identificadores de tareas.
"""

from __future__ import annotations

import importlib.metadata as md
import json
import subprocess
import sys
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from scripts import kaggle_arnes as ka
from scripts import kaggle_ensayo as ke
from scripts import kaggle_preflight as kp
from scripts import kaggle_registro as kreg
from scripts import kaggle_registro_enganches as kre
from scripts import kaggle_rescate as kr
from scripts import kaggle_submission as ksub
from scripts import kaggle_vigia as kv

TOKEN = "tok-secreto-de-prueba-195"
AHORA = datetime(2026, 10, 12, 14, 0, tzinfo=UTC)
FECHA = "2026-10-09 14:43:26.259000"

# --- Ruedas de relleno ---------------------------------------------------------------------------------

ADK_INIT = (
    "from typing import TYPE_CHECKING, Any\n"
    "from .discovery import discover_adapters, discover_declared_models\n"
    "if TYPE_CHECKING:\n"
    "    from .server import VllmConfig, VllmServer, SoloEnTipos\n"
    "_SERVING_EXPORTS = {'VllmConfig', 'VllmServer', 'NoDefinidoEnNingunModulo'}\n"
    "def __getattr__(name: str) -> Any:\n"
    "    if name in _SERVING_EXPORTS:\n"
    "        from . import server\n"
    "        return getattr(server, name)\n"
    "    raise AttributeError(name)\n"
    "__all__ = ['VllmConfig', 'VllmServer', 'discover_adapters', 'SoloEnAll']\n"
)
PAQUETES: dict[str, dict[str, str]] = {
    "swegemma": {
        "swegemma/__init__.py": "__version__ = 'x'\n",
        "swegemma/config.py": "ALLOWED_ADAPTER_EXTENSIONS = {'.safetensors'}\nclass EvalConfig:\n    pass\n",
        "swegemma/evaluate.py": "class Evaluator:\n    pass\n",
        "swegemma/models/__init__.py": "from swegemma.models.task import load_tasks\n",
        "swegemma/models/task.py": "def load_tasks(ruta):\n    return []\n",
    },
    "adk_submission": {
        "adk_submission/__init__.py": ADK_INIT,
        "adk_submission/discovery.py": "discover_adapters = discover_declared_models = print\n",
        "adk_submission/server.py": "class VllmConfig:\n    pass\nclass VllmServer:\n    pass\n",
    },
    "adk_eval_core": {"adk_eval_core/__init__.py": "x = 1\n"},
    "google_adk": {
        "google/adk/__init__.py": "",
        "google/adk/apps/__init__.py": "",
        "google/adk/apps/app.py": "class EventsCompactionConfig:\n    pass\n",
    },
}
DISCOVERY_VIEJO = {
    "swegemma/models/discovery.py": "def validate_single_declared_model(d):\n    return 'm'\n",
}


def rueda(carpeta: Path, dist: str, version: str, archivos: dict[str, str]) -> Path:
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / f"{dist}-{version}-py3-none-any.whl"
    with zipfile.ZipFile(ruta, "w") as z:
        for nombre, texto in archivos.items():
            z.writestr(nombre, texto)
        z.writestr(f"{dist}-{version}.dist-info/METADATA", f"Name: {dist}\nVersion: {version}\n")
    return ruta


def ruedas_ensayadas(carpeta: Path, **versiones: str) -> Path:
    """Las cuatro ruedas del arnés con las versiones ensayadas, salvo las que se indiquen."""
    for dist, version in ka.ARNES_ENSAYADO.items():
        rueda(carpeta, dist, versiones.get(dist, version), PAQUETES[dist])
    return carpeta


def listado_de(carpeta: Path) -> list[dict[str, Any]]:
    return [
        {"nombre": p.name, "bytes": p.stat().st_size, "fecha": FECHA} for p in sorted(carpeta.glob("*.whl"))
    ]


# --- Celdas de un notebook de relleno, con la forma del real --------------------------------------------

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
SERVIDOR_VIEJO = (
    "try:\n"
    "    from adk_submission import VllmConfig, VllmServer, discover_adapters\n"
    "    from swegemma.config import ALLOWED_ADAPTER_EXTENSIONS\n"
    "    from swegemma.models.discovery import validate_single_declared_model\n"
    "    declared_model = validate_single_declared_model(AGENT_DIR)\n"
    "except BaseException as exc:\n"
    "    print(getattr(exc, 'output', None))\n"
    "    raise\n"
)
CORRER = "from swegemma.config import EvalConfig\nfrom swegemma.evaluate import Evaluator\n"


def celdas_del_notebook(servidor: str | None = None, guarda: str | None = None) -> list[str]:
    guarda = ka.celda_de_versiones("/kaggle/working/versiones.json") if guarda is None else guarda
    servidor = ka.sustituir_modelo_declarado(SERVIDOR_VIEJO) if servidor is None else servidor
    return [GUARDIA, "import subprocess\nsubprocess.run(['nvidia-smi'])\n", guarda, servidor, CORRER]


def directorio(tmp_path: Path, celdas: list[str]) -> Path:
    destino = tmp_path / "kernel"
    destino.mkdir()
    cells = [{"cell_type": "code", "source": fuente} for fuente in celdas]
    (destino / "nb.ipynb").write_text(json.dumps({"cells": cells}), encoding="utf-8")
    meta = {
        "id": "usuario/prueba",
        "code_file": "nb.ipynb",
        "is_private": True,
        "enable_gpu": True,
        "enable_internet": False,
        "dataset_sources": [kp.WHEELHOUSE],
        "competition_sources": ["gemma-4-developer-agent"],
        "docker_image": "gcr.io/imagen@sha256:abc",
        "machine_shape": "NvidiaL4",
    }
    (destino / "kernel-metadata.json").write_text(json.dumps(meta), encoding="utf-8")
    return destino


def fallos(directorio_nb: Path, ruedas: Path | None = None, listado: Path | None = None) -> list[str]:
    return [h.texto for h in kp.comprobar_para_subir(directorio_nb, 75, ruedas, listado) if not h.ok]


# ---------------------------------------------------------------------------
# Nombres de ruedas y listado del conjunto
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("archivo", "esperado"),
    [
        ("swegemma-0.2.11-py3-none-any.whl", ("swegemma", "0.2.11")),
        ("google_adk-1.36.1-py3-none-any.whl", ("google_adk", "1.36.1")),
        ("Google-ADK-1.36.1-py3-none-any.whl", None),  # un guion en el nombre no es una rueda bien nombrada
        (
            "apache_tvm_ffi-0.1.13.post3-cp312-cp312-manylinux_2_24_x86_64.whl",
            ("apache_tvm_ffi", "0.1.13.post3"),
        ),
        ("swegemma-0.2.11.tar.gz", None),
        (".gitignore", None),
    ],
)
def test_version_de_rueda(archivo: str, esperado: tuple[str, str] | None) -> None:
    assert ka.version_de_rueda(archivo) == esperado


TABLA = (
    "name                                       size  creationDate                \n"
    "--------------------------------------  -------  --------------------------  \n"
    ".gitignore                                    1  2026-10-09 14:43:26.259000  \n"
    "adk_eval_core-0.1.0-py3-none-any.whl      90060  2026-10-09 14:43:26.273000  \n"
    "adk_submission-0.2.13-py3-none-any.whl    66528  2026-10-09 14:43:26.499000  \n"
    "google_adk-1.36.1-py3-none-any.whl      2877731  2026-10-09 14:43:26.620000  \n"
    "swegemma-0.2.11-py3-none-any.whl         119520  2026-10-09 14:43:26.805000  \n"
)


def test_leer_listado_acepta_la_tabla_de_la_cli_y_el_json_del_rescate() -> None:
    de_tabla = ka.leer_listado(TABLA)
    assert [e["nombre"] for e in de_tabla][:2] == [".gitignore", "adk_eval_core-0.1.0-py3-none-any.whl"]
    assert de_tabla[4] == {
        "nombre": "swegemma-0.2.11-py3-none-any.whl",
        "bytes": 119520,
        "fecha": "2026-10-09 14:43:26.805000",
    }
    assert len(de_tabla) == 5  # ni el encabezado ni la raya son archivos
    como_rescate = json.dumps({"conjunto": "x", "archivos": de_tabla})
    assert ka.leer_listado(como_rescate) == de_tabla
    de_la_api = json.dumps(
        [{"name": "swegemma-0.2.11-py3-none-any.whl", "totalBytes": 119520, "creationDate": "f"}]
    )
    assert ka.leer_listado(de_la_api) == [
        {"nombre": "swegemma-0.2.11-py3-none-any.whl", "bytes": 119520, "fecha": "f"}
    ]
    with pytest.raises(ValueError, match="lista"):
        ka.leer_listado('{"archivos": "no"}')


def test_el_listado_real_del_fallo_coincide_con_lo_ensayado_y_el_anterior_no() -> None:
    versiones = ka.versiones_de(e["nombre"] for e in ka.leer_listado(TABLA))
    assert ka.diferencias_con_lo_ensayado(versiones) == []
    # Control: las versiones de antes del 2026-10-09, con las que se armó el notebook que falló.
    anteriores = {**versiones, "swegemma": ["0.2.7"], "adk_submission": ["0.2.12"]}
    assert ka.diferencias_con_lo_ensayado(anteriores) == [
        "swegemma: se ensayó con 0.2.11 y el listado trae 0.2.7",
        "adk_submission: se ensayó con 0.2.13 y el listado trae 0.2.12",
    ]


def test_una_rueda_que_falta_o_que_esta_dos_veces_tambien_difiere() -> None:
    sin = ka.versiones_de(["swegemma-0.2.11-py3-none-any.whl"])
    assert (
        "adk_submission: se ensayó con 0.2.13 y el listado no trae esa rueda"
        in ka.diferencias_con_lo_ensayado(sin)
    )
    dos = ka.versiones_de(["swegemma-0.2.11-py3-none-any.whl", "swegemma-0.2.7-py3-none-any.whl"])
    assert "swegemma: se ensayó con 0.2.11 y el listado trae 0.2.11, 0.2.7" in ka.diferencias_con_lo_ensayado(
        dos
    )
    assert ka.diferencias_con_lo_ensayado({"google_adk": ["1.36.1"]}, {"google-adk": "1.36.1"}) == []


def test_cambios_del_listado_dice_que_entra_que_sale_y_que_cambia() -> None:
    antes = [
        {"nombre": "a-1.0-py3-none-any.whl", "bytes": 10, "fecha": "f1"},
        {"nombre": "b-1.0-py3-none-any.whl", "bytes": 20, "fecha": "f1"},
        {"nombre": "c-1.0-py3-none-any.whl", "bytes": 30, "fecha": "f1"},
    ]
    ahora = [
        {"nombre": "a-1.0-py3-none-any.whl", "bytes": 10, "fecha": "f1"},
        {"nombre": "b-1.1-py3-none-any.whl", "bytes": 21, "fecha": "f2"},
        {"nombre": "c-1.0-py3-none-any.whl", "bytes": 31, "fecha": "f2"},
    ]
    assert ka.cambios_del_listado(antes, antes) == []
    assert ka.cambios_del_listado(antes, ahora) == [
        "sale b-1.0-py3-none-any.whl",
        "entra b-1.1-py3-none-any.whl",
        "c-1.0-py3-none-any.whl: bytes 30 -> 31",
        "c-1.0-py3-none-any.whl: fecha f1 -> f2",
    ]


# ---------------------------------------------------------------------------
# El texto que el armado pone en el notebook
# ---------------------------------------------------------------------------


def test_el_sustituto_no_importa_el_modulo_eliminado_y_compila() -> None:
    nueva = ka.sustituir_modelo_declarado(SERVIDOR_VIEJO)
    assert "validate_single_declared_model" not in nueva and "swegemma.models.discovery" not in nueva
    assert "from adk_submission import discover_declared_models" in nueva
    compile(nueva, "celda", "exec")
    with pytest.raises(ValueError, match="exactamente una vez"):
        ka.sustituir_modelo_declarado(nueva)  # ya sustituida: no casa


@pytest.mark.parametrize(
    ("declarados", "esperado"),
    [
        ({"gemma-x"}, "gemma-x"),
        ({" OpenAI/Gemma-X "}, "gemma-x"),  # la normalización de swegemma 0.2.7: minúsculas y sin prefijo
        ({"hosted_vllm/gemma-x", "gemma-x"}, "gemma-x"),  # dos escrituras del mismo modelo son uno
        (set(), RuntimeError),
        ({"gemma-x", "gemma-y"}, RuntimeError),
    ],
)
def test_el_sustituto_exige_exactamente_un_modelo_declarado(declarados: set[str], esperado: Any) -> None:
    def descubrir(_directorio: object, normalize_fn: Any) -> set[str]:
        return {normalize_fn(x) for x in declarados}

    # El cuerpo del sustituto, ejecutado con un `discover_declared_models` de relleno
    fuente = "\n".join(linea[4:] for linea in ka.USO_SUSTITUTO.splitlines())
    espacio: dict[str, Any] = {"discover_declared_models": descubrir, "AGENT_DIR": "x"}
    if esperado is RuntimeError:
        with pytest.raises(RuntimeError, match="se exige exactamente uno"):
            exec(fuente, espacio)
    else:
        exec(fuente, espacio)
        assert espacio["declared_model"] == esperado


def test_la_guarda_de_versiones_escribe_el_archivo_y_pasa_con_las_versiones_esperadas(tmp_path: Path) -> None:
    archivo = tmp_path / "salida" / "versiones.json"
    ruedas = tmp_path / "ruedas"
    ruedas.mkdir()
    (ruedas / "pytest-1-py3-none-any.whl").write_bytes(b"12345")
    esperadas = {"pytest": md.version("pytest")}
    exec(ka.celda_de_versiones(archivo.as_posix(), esperadas), {"W": str(ruedas)})
    escrito = json.loads(archivo.read_text(encoding="utf-8"))
    assert escrito == {
        "esperadas": esperadas,
        "instaladas": esperadas,
        "distintas": {},
        "ruedas": {"pytest-1-py3-none-any.whl": 5},
    }


def test_la_guarda_de_versiones_detiene_el_notebook_y_deja_el_archivo(tmp_path: Path) -> None:
    archivo = tmp_path / "versiones.json"
    esperadas = {"pytest": "0.0.1", "paquete_que_no_existe_195": "1.0"}
    with pytest.raises(RuntimeError, match="versiones distintas de las ensayadas"):
        exec(ka.celda_de_versiones(archivo.as_posix(), esperadas), {})  # sin W: lo tolera
    escrito = json.loads(archivo.read_text(encoding="utf-8"))
    assert escrito["distintas"] == {
        "pytest": ["0.0.1", md.version("pytest")],
        "paquete_que_no_existe_195": ["1.0", None],
    }
    assert escrito["ruedas"] is None


def test_esperado_en_el_notebook_lee_la_guarda_y_no_acepta_una_sin_raise() -> None:
    celda = ka.celda_de_versiones("/kaggle/working/v.json")
    assert ka.esperado_en_el_notebook(["x = 1\n", celda]) == ka.ARNES_ENSAYADO
    assert ka.esperado_en_el_notebook(["x = 1\n"]) is None
    assert ka.esperado_en_el_notebook([celda.replace("raise RuntimeError", "print")]) is None
    otra = ka.celda_de_versiones("/kaggle/working/v.json", {"swegemma": "0.2.7"})
    assert ka.esperado_en_el_notebook([otra]) == {"swegemma": "0.2.7"}


# ---------------------------------------------------------------------------
# Imports del notebook contra las ruedas, sin ejecutar
# ---------------------------------------------------------------------------


def test_los_imports_del_notebook_rearmado_existen_en_las_ruedas(tmp_path: Path) -> None:
    fuentes = ka.leer_fuentes(ruedas_ensayadas(tmp_path / "ruedas"))
    assert fuentes.versiones == {k: [v] for k, v in ka.ARNES_ENSAYADO.items()}
    informe = ka.comprobar_imports(celdas_del_notebook(), fuentes)
    assert (informe.rotos, informe.sin_fuente) == ([], [])
    assert informe.comprobados == 7 and informe.ok


def test_el_notebook_que_fallo_tiene_un_import_roto_y_se_nombra(tmp_path: Path) -> None:
    fuentes = ka.leer_fuentes(ruedas_ensayadas(tmp_path / "ruedas"))
    informe = ka.comprobar_imports(celdas_del_notebook(servidor=SERVIDOR_VIEJO), fuentes)
    assert informe.rotos == [
        "celda 3, línea 4: from swegemma.models.discovery import validate_single_declared_model: "
        "el módulo no existe"
    ]
    assert not informe.ok
    # Control: con el módulo en la rueda (la versión anterior), el mismo notebook no tiene imports rotos.
    viejas = tmp_path / "viejas"
    ruedas_ensayadas(viejas)
    rueda(viejas, "swegemma", "0.2.11", {**PAQUETES["swegemma"], **DISCOVERY_VIEJO})
    assert ka.comprobar_imports(celdas_del_notebook(servidor=SERVIDOR_VIEJO), ka.leer_fuentes(viejas)).ok


def test_quitar_un_modulo_de_las_ruedas_rompe_el_notebook_rearmado(tmp_path: Path) -> None:
    """El criterio del issue: sale bien contra las ruedas reales y mal si se les quita un módulo."""
    carpeta = ruedas_ensayadas(tmp_path / "ruedas")
    sin_evaluate = {k: v for k, v in PAQUETES["swegemma"].items() if k != "swegemma/evaluate.py"}
    rueda(carpeta, "swegemma", "0.2.11", sin_evaluate)
    informe = ka.comprobar_imports(celdas_del_notebook(), ka.leer_fuentes(carpeta))
    assert informe.rotos == ["celda 4, línea 2: from swegemma.evaluate import Evaluator: el módulo no existe"]


@pytest.mark.parametrize(
    ("celda", "roto"),
    [
        ("from adk_submission import VllmServer\n", None),  # servido por __getattr__ y definido en server.py
        ("from adk_submission import discover_declared_models\n", None),  # reexportado
        ("from adk_submission import server\n", None),  # un submódulo
        ("import swegemma.models.task\n", None),
        ("from swegemma.models import *\n", None),
        ("from adk_submission import NoDefinidoEnNingunModulo\n", "no define ese nombre"),
        ("from adk_submission import SoloEnTipos\n", "no define ese nombre"),  # solo bajo TYPE_CHECKING
        ("from adk_submission import SoloEnAll\n", "no define ese nombre"),  # __all__ no define nada
        ("from swegemma.config import NoExiste\n", "no define ese nombre"),
        ("import swegemma.no_existe\n", "el módulo no existe"),
        ("def f():\n    from swegemma.harness import agent_runner\n", "el módulo no existe"),
    ],
)
def test_cada_forma_de_import(tmp_path: Path, celda: str, roto: str | None) -> None:
    fuentes = ka.leer_fuentes(ruedas_ensayadas(tmp_path / "ruedas"))
    informe = ka.comprobar_imports([celda], fuentes)
    if roto is None:
        assert informe.rotos == [] and informe.comprobados == 1
    else:
        assert len(informe.rotos) == 1 and roto in informe.rotos[0]


def test_un_import_opcional_no_es_una_rotura_y_uno_bajo_except_general_si(tmp_path: Path) -> None:
    fuentes = ka.leer_fuentes(ruedas_ensayadas(tmp_path / "ruedas"))
    opcional = "try:\n    import swegemma.no_existe\nexcept ImportError:\n    pass\n"
    informe = ka.comprobar_imports([opcional], fuentes)
    assert (informe.rotos, informe.opcionales, informe.comprobados) == ([], 1, 0)
    # La celda del servidor real envuelve todo en `except BaseException`: eso no lo hace opcional.
    general = "try:\n    import swegemma.no_existe\nexcept BaseException:\n    raise\n"
    assert len(ka.comprobar_imports([general], fuentes).rotos) == 1
    # Ni lo que va en el `except ImportError`: ese import sí se ejecuta cuando falla el primero.
    en_el_manejador = "try:\n    import json\nexcept ImportError:\n    import swegemma.no_existe\n"
    assert len(ka.comprobar_imports([en_el_manejador], fuentes).rotos) == 1


def test_un_paquete_sin_fuente_no_se_da_por_bueno(tmp_path: Path) -> None:
    carpeta = tmp_path / "ruedas"
    rueda(carpeta, "swegemma", "0.2.11", PAQUETES["swegemma"])
    informe = ka.comprobar_imports(celdas_del_notebook(), ka.leer_fuentes(carpeta))
    assert not informe.ok and informe.rotos == []
    assert len(informe.sin_fuente) == 4 and all("adk_submission" in x for x in informe.sin_fuente)
    vacia = ka.comprobar_imports(celdas_del_notebook(), ka.leer_fuentes(tmp_path / "no_existe"))
    assert not vacia.ok and vacia.comprobados == 0 and len(vacia.sin_fuente) == 7


def test_las_fuentes_extraidas_valen_lo_mismo_que_las_ruedas(tmp_path: Path) -> None:
    extraidas = tmp_path / "src"
    for dist, version in ka.ARNES_ENSAYADO.items():
        for nombre, texto in PAQUETES[dist].items():
            destino = extraidas / f"{dist}-{version}-py3-none-any" / nombre
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(texto, encoding="utf-8")
    fuentes = ka.leer_fuentes(extraidas)
    assert fuentes.versiones == {k: [v] for k, v in ka.ARNES_ENSAYADO.items()}
    assert ka.comprobar_imports(celdas_del_notebook(), fuentes).ok
    assert len(ka.comprobar_imports(celdas_del_notebook(servidor=SERVIDOR_VIEJO), fuentes).rotos) == 1


def test_un_zip_ilegible_no_lanza_y_una_celda_que_no_compila_se_dice(tmp_path: Path) -> None:
    carpeta = ruedas_ensayadas(tmp_path / "ruedas")
    (carpeta / "rota-1.0-py3-none-any.whl").write_bytes(b"no es un zip")
    fuentes = ka.leer_fuentes(carpeta)
    assert "rota" in fuentes.versiones and not fuentes.tiene_paquete("rota")
    informe = ka.comprobar_imports(["print('\n"], fuentes)
    assert informe.rotos == ["celda 0: no compila; sus imports no se pudieron leer"]


def test_usa_el_arnes() -> None:
    assert ka.usa_el_arnes(celdas_del_notebook())
    assert ka.usa_el_arnes(["import importlib\nm = importlib.import_module('swegemma.evaluate')\n"])
    assert ka.usa_el_arnes(["from google.adk.apps.app import EventsCompactionConfig\n"])
    # La guardia nombra la rueda de swegemma como texto: eso no es importar el arnés.
    assert not ka.usa_el_arnes([GUARDIA, "import json\nfrom google.genai import types\nprint('\n"])


# ---------------------------------------------------------------------------
# El chequeo previo
# ---------------------------------------------------------------------------


def test_sin_ruedas_no_dice_que_se_puede_subir_y_explica_que_falta(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    nb = directorio(tmp_path, celdas_del_notebook())
    assert kp.main(["comprobar", str(nb), "--tope-min", "75"]) == kp.EXIT_INVALID
    captura = capsys.readouterr()
    assert "Se puede subir" not in captura.out and "kaggle kernels push" not in captura.out
    assert "NO SUBIR: 2 comprobaciones fallan" in captura.err
    assert "falta --ruedas <carpeta con las .whl del arnés" in captura.out
    assert "falta --listado <listado_ruedas.json del último rescate" in captura.out


def test_con_las_ruedas_ensayadas_pasa_y_da_la_orden(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    nb = directorio(tmp_path, celdas_del_notebook())
    ruedas = ruedas_ensayadas(tmp_path / "ruedas")
    listado = tmp_path / "listado_ruedas.json"
    listado.write_text(json.dumps({"archivos": listado_de(ruedas)}), encoding="utf-8")
    assert fallos(nb, ruedas) == []
    orden = ["comprobar", str(nb), "--tope-min", "75", "--ruedas", str(ruedas), "--listado", str(listado)]
    assert kp.main(orden) == kp.EXIT_OK
    salida = capsys.readouterr().out
    assert "Se puede subir" in salida and "kaggle kernels push" in salida
    assert "Los 7 imports del arnés que hace el notebook existen en las ruedas" in salida
    assert "trae las versiones ensayadas" in salida and "tienen el tamaño que dice el listado" in salida


@pytest.mark.parametrize("donde", ["ruedas", "listado"])
def test_si_las_versiones_difieren_de_las_ensayadas_falla_con_un_mensaje_claro(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], donde: str
) -> None:
    nb = directorio(tmp_path, celdas_del_notebook())
    buenas = ruedas_ensayadas(tmp_path / "buenas")
    otras = ruedas_ensayadas(tmp_path / "otras", swegemma="0.2.12")
    listado = tmp_path / "listado.json"
    listado.write_text(json.dumps(listado_de(otras if donde == "listado" else buenas)), encoding="utf-8")
    ruedas = otras if donde == "ruedas" else buenas
    orden = ["comprobar", str(nb), "--tope-min", "75", "--ruedas", str(ruedas), "--listado", str(listado)]
    assert kp.main(orden) == kp.EXIT_INVALID
    captura = capsys.readouterr()
    assert "Se puede subir" not in captura.out
    assert "swegemma: se ensayó con 0.2.11 y el listado trae 0.2.12" in captura.out
    esperado = (
        "Las ruedas de --ruedas no son las ensayadas"
        if donde == "ruedas"
        else "cambió respecto de lo ensayado"
    )
    assert esperado in captura.out


def test_el_listado_solo_compara_versiones_pero_no_basta_para_subir(tmp_path: Path) -> None:
    nb = directorio(tmp_path, celdas_del_notebook())
    listado = tmp_path / "listado.txt"
    listado.write_text(TABLA, encoding="utf-8")
    (unico,) = fallos(nb, None, listado)
    assert "No se comprobaron los imports" in unico
    listado.write_text(TABLA.replace("swegemma-0.2.11", "swegemma-0.2.12"), encoding="utf-8")
    assert any(
        "swegemma: se ensayó con 0.2.11 y el listado trae 0.2.12" in x for x in fallos(nb, None, listado)
    )
    assert any("No se pudo leer el listado" in x for x in fallos(nb, None, tmp_path / "no_existe.json"))


def test_una_carpeta_de_ruedas_que_no_es_la_del_listado_falla(tmp_path: Path) -> None:
    nb = directorio(tmp_path, celdas_del_notebook())
    ruedas = ruedas_ensayadas(tmp_path / "ruedas")
    entradas = listado_de(ruedas)
    entradas[-1]["bytes"] += 1  # la rueda de swegemma del listado pesa otra cosa: la carpeta está vieja
    listado = tmp_path / "listado.json"
    listado.write_text(json.dumps(entradas), encoding="utf-8")
    (unico,) = fallos(nb, ruedas, listado)
    assert "que no están en el listado con ese tamaño: swegemma-0.2.11-py3-none-any.whl" in unico


def test_el_notebook_que_fallo_no_pasa_el_chequeo_previo(tmp_path: Path) -> None:
    ruedas = ruedas_ensayadas(tmp_path / "ruedas")
    viejo = directorio(tmp_path, celdas_del_notebook(servidor=SERVIDOR_VIEJO, guarda="x = 1\n"))
    textos = fallos(viejo, ruedas)
    assert len(textos) == 2
    assert "no trae la guarda de versiones" in textos[0]
    assert "Import que no existe en las ruedas: celda 3, línea 4" in textos[1]


def test_una_guarda_que_espera_otras_versiones_falla(tmp_path: Path) -> None:
    guarda = ka.celda_de_versiones("/kaggle/working/v.json", {**ka.ARNES_ENSAYADO, "swegemma": "0.2.7"})
    nb = directorio(tmp_path, celdas_del_notebook(guarda=guarda))
    (unico,) = fallos(nb, ruedas_ensayadas(tmp_path / "ruedas"))
    assert unico.startswith("La guarda del notebook espera") and "'swegemma': '0.2.7'" in unico


def test_un_notebook_que_no_importa_el_arnes_no_necesita_ruedas(tmp_path: Path) -> None:
    nb = directorio(tmp_path, [GUARDIA, "import subprocess\nsubprocess.run(['nvidia-smi'])\n"])
    assert fallos(nb) == []
    assert kp.main(["comprobar", str(nb), "--tope-min", "75"]) == kp.EXIT_OK
    # Pero si se le pasa una carpeta de ruedas, se compara: una sonda también corre con esas ruedas.
    otras = ruedas_ensayadas(tmp_path / "otras", adk_submission="0.2.12")
    assert any("adk_submission: se ensayó con 0.2.13" in x for x in fallos(nb, otras))


def test_un_directorio_ilegible_no_anade_hallazgos_del_arnes(tmp_path: Path) -> None:
    assert kp.comprobar_arnes_del_directorio(tmp_path, None, None) == []


# ---------------------------------------------------------------------------
# El rescate guarda el listado
# ---------------------------------------------------------------------------


def api_del_listado(paginas: list[list[dict[str, Any]]]) -> Any:
    pedidas: list[str] = []

    def pedir(ruta: str, token: str) -> bytes:
        assert token == TOKEN
        pedidas.append(ruta)
        assert ruta.startswith(f"datasets/list/{kr.WHEELHOUSE}?pageSize=200")
        indice = int(ruta.split("pageToken=p")[1]) if "pageToken=" in ruta else 0
        siguiente = f"p{indice + 1}" if indice + 1 < len(paginas) else ""
        return json.dumps({"datasetFiles": paginas[indice], "nextPageToken": siguiente}).encode()

    pedir.pedidas = pedidas  # type: ignore[attr-defined]
    return pedir


def de_la_api(entradas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"name": e["nombre"], "totalBytes": e["bytes"], "creationDate": e["fecha"]} for e in entradas]


def test_el_rescate_guarda_el_listado_de_todas_las_paginas(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    entradas = ka.leer_listado(TABLA)
    pedir = api_del_listado([de_la_api(entradas[:2]), de_la_api(entradas[2:])])
    monkeypatch.setattr(kr, "pedir", pedir)
    resumen = kr.guardar_listado_de_ruedas(tmp_path, TOKEN)
    assert len(pedir.pedidas) == 2 and pedir.pedidas[1].endswith("&pageToken=p1")
    guardado = json.loads((tmp_path / kr.ARCHIVO_LISTADO).read_text(encoding="utf-8"))
    assert guardado["conjunto"] == kr.WHEELHOUSE and guardado["archivos"] == entradas
    assert TOKEN not in (tmp_path / kr.ARCHIVO_LISTADO).read_text(encoding="utf-8")
    assert resumen == {
        "guardado": True,
        "archivos": 5,
        "fecha_mas_reciente": "2026-10-09 14:43:26.805000",
        "arnes": {k: [v] for k, v in ka.ARNES_ENSAYADO.items()},
        "difiere_de_lo_ensayado": [],
    }
    assert kr.leer_listado_guardado(tmp_path) == resumen
    assert ka.leer_listado((tmp_path / kr.ARCHIVO_LISTADO).read_text(encoding="utf-8")) == entradas


@pytest.mark.parametrize(
    ("respuesta", "causa"),
    [
        (kr.RescateError("Kaggle respondió 404 a datasets/list"), "Kaggle respondió 404"),
        (b"no es json", "respuesta de Kaggle ilegible"),
        (json.dumps({"datasetFiles": []}).encode(), "llegó vacío"),
        (json.dumps({"otra_cosa": 1}).encode(), "no trae una lista"),
    ],
)
def test_si_el_listado_falla_el_rescate_sigue_y_el_archivo_dice_el_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, respuesta: Any, causa: str
) -> None:
    def pedir(ruta: str, token: str) -> bytes:
        if isinstance(respuesta, Exception):
            raise respuesta
        return bytes(respuesta)

    monkeypatch.setattr(kr, "pedir", pedir)
    resumen = kr.guardar_listado_de_ruedas(tmp_path, TOKEN)
    assert resumen["guardado"] is False and causa in resumen["error"]
    guardado = json.loads((tmp_path / kr.ARCHIVO_LISTADO).read_text(encoding="utf-8"))
    assert "archivos" not in guardado and causa in guardado["error"]
    assert kr.leer_listado_guardado(tmp_path) == resumen


def test_el_resumen_del_rescate_avisa_si_el_conjunto_no_es_el_ensayado(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import io

    tabla = io.BytesIO()
    with zipfile.ZipFile(tabla, "w") as z:
        z.writestr("tabla.csv", "Rank,TeamMemberUserNames,Score,SubmissionCount\n1,alguien,0.10,1\n")
    (tmp_path / "envios.json").write_text("[]", encoding="utf-8")
    (tmp_path / "tabla_publica.zip").write_bytes(tabla.getvalue())
    assert kr.main(["--destino", str(tmp_path), "--sin-red"]) == kr.EXIT_OK
    captura = capsys.readouterr()
    assert json.loads(captura.out)["listado_de_ruedas"] is None
    assert "AVISO: sin listado del conjunto de ruedas (este rescate no lo trae)" in captura.err
    viejo = ka.leer_listado(TABLA.replace("swegemma-0.2.11", "swegemma-0.2.7"))
    (tmp_path / kr.ARCHIVO_LISTADO).write_text(json.dumps({"archivos": viejo}), encoding="utf-8")
    assert kr.main(["--destino", str(tmp_path), "--sin-red"]) == kr.EXIT_OK
    captura = capsys.readouterr()
    assert json.loads(captura.out)["listado_de_ruedas"]["arnes"]["swegemma"] == ["0.2.7"]
    assert "EL CONJUNTO DE RUEDAS NO ES EL ENSAYADO: swegemma: se ensayó con 0.2.11" in captura.err
    (tmp_path / kr.ARCHIVO_LISTADO).write_text(
        json.dumps({"archivos": ka.leer_listado(TABLA)}), encoding="utf-8"
    )
    assert kr.main(["--destino", str(tmp_path), "--sin-red"]) == kr.EXIT_OK
    assert "AVISO" not in capsys.readouterr().err


# ---------------------------------------------------------------------------
# El vigía avisa de un cambio del conjunto
# ---------------------------------------------------------------------------


def rescate_con_listado(rescates: Path, entradas: Any) -> Path:
    carpeta = rescates / "2026-10-12T0700Z"
    carpeta.mkdir(parents=True)
    (carpeta / "envios.json").write_text("[]", encoding="utf-8")
    (carpeta / "usuario.txt").write_text("yo", encoding="utf-8")
    (carpeta / "tabla_publica.zip").write_bytes(b"PK")
    if entradas is not None:
        contenido = {
            "conjunto": kr.WHEELHOUSE,
            **({"archivos": entradas} if isinstance(entradas, list) else entradas),
        }
        (carpeta / kr.ARCHIVO_LISTADO).write_text(json.dumps(contenido), encoding="utf-8")
    return carpeta


def api_del_vigia(actual: Any) -> Any:
    peticiones: list[str] = []

    def pedir(ruta: str, token: str) -> bytes:
        peticiones.append(ruta)
        assert token == TOKEN
        if ruta.startswith("competitions/submissions/list/"):
            return b"[]"
        if ruta.startswith("datasets/list/"):
            if isinstance(actual, Exception):
                raise actual
            return json.dumps({"datasetFiles": de_la_api(actual)}).encode()
        raise AssertionError(ruta)

    pedir.peticiones = peticiones  # type: ignore[attr-defined]
    return pedir


def correr_vigia(rescates: Path, pedir: Any, tope_s: float = kv.TOPE_TOTAL_S) -> list[str]:
    return kv.vigia(
        raiz_repo=rescates.parent,
        entorno={"KAGGLE_API_TOKEN": TOKEN},
        pedir=pedir,
        ahora=AHORA,
        ruta_hallazgos=rescates.parent / "no_hay_hallazgos.json",
        principal=rescates.parent,
        rescates=rescates,
        tope_s=tope_s,
    )


def de_ruedas(lineas: list[str]) -> list[str]:
    return [x for x in lineas if "ruedas" in x.lower()]


def test_el_vigia_calla_si_el_conjunto_es_el_del_rescate_y_el_ensayado(tmp_path: Path) -> None:
    entradas = ka.leer_listado(TABLA)
    rescate_con_listado(tmp_path / "r", entradas)
    pedir = api_del_vigia(entradas)
    lineas = correr_vigia(tmp_path / "r", pedir)
    assert de_ruedas(lineas) == []
    assert pedir.peticiones[-1] == f"datasets/list/{kr.WHEELHOUSE}?pageSize=200"
    assert TOKEN not in "\n".join(lineas)


def test_el_vigia_avisa_si_el_conjunto_cambio_desde_el_ultimo_rescate(tmp_path: Path) -> None:
    """Lo que pasó entre el 2026-10-08 y el 2026-10-12: el rescate guardó unas ruedas y Kaggle tiene otras."""
    antes = ka.leer_listado(
        TABLA.replace("swegemma-0.2.11", "swegemma-0.2.7").replace(
            "adk_submission-0.2.13", "adk_submission-0.2.12"
        )
    )
    rescate_con_listado(tmp_path / "r", antes)
    lineas = de_ruedas(correr_vigia(tmp_path / "r", api_del_vigia(ka.leer_listado(TABLA))))
    assert len(lineas) == 1
    assert lineas[0].startswith(
        "EL CONJUNTO DE RUEDAS DEL ARNÉS CAMBIÓ desde el rescate 2026-10-12T0700Z (4 cambios: "
    )
    assert "sale swegemma-0.2.7-py3-none-any.whl" in lineas[0]
    assert "entra swegemma-0.2.11-py3-none-any.whl" in lineas[0]
    assert "repite el ensayo antes de subir" in lineas[0]


def test_el_vigia_avisa_si_el_conjunto_no_es_el_ensayado_aunque_no_haya_cambiado(tmp_path: Path) -> None:
    otras = ka.leer_listado(TABLA.replace("swegemma-0.2.11", "swegemma-0.2.12"))
    rescate_con_listado(tmp_path / "r", otras)
    (linea,) = de_ruedas(correr_vigia(tmp_path / "r", api_del_vigia(otras)))
    assert linea.startswith(
        "EL CONJUNTO DE RUEDAS DEL ARNÉS NO ES EL ENSAYADO (swegemma: se ensayó con 0.2.11"
    )


def test_un_cambio_de_tamano_con_el_mismo_nombre_tambien_se_avisa_y_la_lista_se_recorta(
    tmp_path: Path,
) -> None:
    antes = [{"nombre": f"paquete{i}-1.0-py3-none-any.whl", "bytes": 10, "fecha": FECHA} for i in range(9)]
    antes += ka.leer_listado(TABLA)
    ahora = [{**e, "bytes": e["bytes"] + 1} if e["nombre"].startswith("paquete") else e for e in antes]
    rescate_con_listado(tmp_path / "r", antes)
    (linea,) = de_ruedas(correr_vigia(tmp_path / "r", api_del_vigia(ahora)))
    assert "(9 cambios: paquete0-1.0-py3-none-any.whl: bytes 10 -> 11" in linea and "… y 3 más" in linea


def test_sin_listado_en_el_rescate_el_vigia_no_pide_el_conjunto(tmp_path: Path) -> None:
    rescate_con_listado(tmp_path / "r", None)
    pedir = api_del_vigia(AssertionError("no debía pedirse"))
    lineas = correr_vigia(tmp_path / "r", pedir)
    assert de_ruedas(lineas) == []
    assert pedir.peticiones == ["competitions/submissions/list/gemma-4-developer-agent?page=1"]


def test_si_el_rescate_no_pudo_guardar_el_listado_el_vigia_lo_dice(tmp_path: Path) -> None:
    rescate_con_listado(tmp_path / "r", {"error": "Kaggle respondió 404"})
    pedir = api_del_vigia(AssertionError("no debía pedirse"))
    (linea,) = de_ruedas(correr_vigia(tmp_path / "r", pedir))
    assert "no pudo guardar el listado de ruedas" in linea
    assert not any(p.startswith("datasets/") for p in pedir.peticiones)


def test_si_kaggle_no_entrega_el_listado_el_vigia_lo_dice_sin_el_token(tmp_path: Path) -> None:
    rescate_con_listado(tmp_path / "r", ka.leer_listado(TABLA))
    error = kr.RescateError(f"Kaggle respondió 500 con {TOKEN}")
    lineas = correr_vigia(tmp_path / "r", api_del_vigia(error))
    (linea,) = de_ruedas(lineas)
    assert linea == "no pude leer el conjunto de ruedas del arnés (RescateError): no sé si cambió"
    assert TOKEN not in "\n".join(lineas)
    assert any(x.startswith("envíos sin cambios") for x in lineas)  # lo demás se dijo igual


def test_con_el_tope_gastado_el_vigia_no_pide_el_listado(tmp_path: Path) -> None:
    carpeta = rescate_con_listado(tmp_path / "r", ka.leer_listado(TABLA))
    pedir = api_del_vigia(AssertionError("no debía pedirse"))
    lineas = kv.avisos_de_ruedas(carpeta, TOKEN, pedir, time.monotonic() - 1)
    assert lineas == ["no comparé el conjunto de ruedas del arnés: se gastó el tope"]
    assert pedir.peticiones == []


def test_un_listado_guardado_ilegible_no_hace_lanzar_al_vigia(tmp_path: Path) -> None:
    carpeta = rescate_con_listado(tmp_path / "r", None)
    (carpeta / kr.ARCHIVO_LISTADO).write_text("no es json", encoding="utf-8")
    lineas = kv.avisos_de_ruedas(carpeta, TOKEN, api_del_vigia([]), time.monotonic() + 5)
    assert lineas == ["no pude comparar el conjunto de ruedas del arnés (JSONDecodeError)"]


def test_el_vigia_con_el_listado_no_pasa_de_su_tope_si_kaggle_no_responde(tmp_path: Path) -> None:
    rescate_con_listado(tmp_path / "r", ka.leer_listado(TABLA))

    def pedir(ruta: str, token: str) -> bytes:
        if ruta.startswith("datasets/list/"):
            time.sleep(5)
        return b"[]"

    inicio = time.monotonic()
    lineas = correr_vigia(tmp_path / "r", pedir, tope_s=0.5)
    assert time.monotonic() - inicio < 3
    assert "Kaggle no respondió en 0.5 s: no sé si hay cambios" in lineas


# ---------------------------------------------------------------------------
# Los dos guiones que compilan el envío ya no dependen de swegemma.models
# ---------------------------------------------------------------------------

ADK_DE_RELLENO = (
    "import json, os, sys\n"
    "class ModelRegistry:\n"
    "    def __init__(self):\n        self.modelos = {}\n"
    "    def register(self, nombre, destino):\n        self.modelos[nombre] = destino\n"
    "class ToolRegistry:\n"
    "    def __init__(self):\n        self.herramientas = []\n"
    "    def register(self, nombre, fn):\n        self.herramientas.append(nombre)\n"
    "def discover_declared_models(directorio):\n    return {' gemma-x ', 'custom/otro'}\n"
    "def compile_submission(submission_dir, tool_registry, model_registry):\n"
    "    visto = {'modelos': {k: str(v) for k, v in model_registry.modelos.items()},\n"
    "             'herramientas': tool_registry.herramientas}\n"
    "    with open(os.environ['VISTO_195'], 'w') as f:\n        json.dump(visto, f)\n"
    "    return 'agente'\n"
)


def test_el_programa_de_compilacion_no_usa_lo_que_swegemma_elimino(tmp_path: Path) -> None:
    assert "setup_gemma_model_registry" not in ke.PROGRAMA_COMPILAR
    assert "swegemma" not in ke.PROGRAMA_COMPILAR
    paquetes = tmp_path / "paquetes"
    (paquetes / "adk_submission").mkdir(parents=True)
    (paquetes / "adk_submission" / "__init__.py").write_text(ADK_DE_RELLENO, encoding="utf-8")
    visto = tmp_path / "visto.json"
    entorno = {"PYTHONPATH": str(paquetes), "VISTO_195": str(visto), "SYSTEMROOT": "C:\\Windows"}
    orden = [sys.executable, "-S", "-c", ke.PROGRAMA_COMPILAR, str(tmp_path)]
    proceso = subprocess.run(orden, env=entorno, capture_output=True, text=True, timeout=60, check=False)
    assert proceso.returncode == 0, proceso.stderr
    datos = json.loads(visto.read_text(encoding="utf-8"))
    # Sin google.adk instalado en ese intérprete, registra el nombre con su prefijo, como el arnés sin LiteLlm
    assert datos["modelos"] == {"gemma-x": "openai/gemma-x", "custom/otro": "custom/otro"}
    assert datos["herramientas"] == list(ke.HERRAMIENTAS_ARNES)


def test_el_programa_de_compilacion_sale_con_4_si_la_compilacion_lanza(tmp_path: Path) -> None:
    paquetes = tmp_path / "paquetes"
    (paquetes / "adk_submission").mkdir(parents=True)
    roto = ADK_DE_RELLENO.replace("    return 'agente'\n", "    raise ValueError('no compila')\n")
    (paquetes / "adk_submission" / "__init__.py").write_text(roto, encoding="utf-8")
    entorno = {
        "PYTHONPATH": str(paquetes),
        "VISTO_195": str(tmp_path / "v.json"),
        "SYSTEMROOT": "C:\\Windows",
    }
    orden = [sys.executable, "-S", "-c", ke.PROGRAMA_COMPILAR, str(tmp_path)]
    proceso = subprocess.run(orden, env=entorno, capture_output=True, text=True, timeout=60, check=False)
    assert proceso.returncode == 4 and "no compila" in proceso.stderr


def test_compile_with_adk_sin_la_funcion_eliminada_usa_los_modelos_declarados(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import types

    recibido: dict[str, Any] = {}

    class Registro:
        def __init__(self) -> None:
            self.vistos: dict[str, object] = {}

        def register(self, nombre: str, destino: object) -> None:
            self.vistos[nombre] = destino

    def compilar(**kw: Any) -> str:
        recibido.update(kw)
        return "agente"

    adk = types.ModuleType("adk_submission")
    adk.ToolRegistry = Registro  # type: ignore[attr-defined]
    adk.ModelRegistry = Registro  # type: ignore[attr-defined]
    adk.compile_submission = compilar  # type: ignore[attr-defined]
    adk.discover_declared_models = lambda _d: {"gemma-x ", "hosted_vllm/y"}  # type: ignore[attr-defined]
    swe = types.ModuleType("swegemma")
    modelos = types.ModuleType("swegemma.models")  # como swegemma 0.2.11: sin setup_gemma_model_registry
    monkeypatch.setitem(sys.modules, "adk_submission", adk)
    monkeypatch.setitem(sys.modules, "swegemma", swe)
    monkeypatch.setitem(sys.modules, "swegemma.models", modelos)

    ok, mensaje = ksub.compile_with_adk(tmp_path)
    assert ok is True, mensaje
    assert recibido["model_registry"].vistos == {
        "gemma-x": "openai/gemma-x",
        "hosted_vllm/y": "hosted_vllm/y",
    }
    # Control: sin adk_submission el envío no se da por compilado.
    monkeypatch.setitem(sys.modules, "adk_submission", None)
    ok, mensaje = ksub.compile_with_adk(tmp_path)
    assert ok is False and "NO se compiló" in mensaje


# ---------------------------------------------------------------------------
# El registro anota lo que cada petición pide y trae de razonamiento (solo números)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("opciones", "esperado"),
    [
        # adk_submission 0.2.13 con el kit de base: los parámetros viajan en extra_body
        (
            {
                "extra_body": {
                    "chat_template_kwargs": {"enable_thinking": True},
                    "thinking_token_budget": 4096,
                }
            },
            (True, 4096),
        ),
        ({"extra_body": {"chat_template_kwargs": {"enable_thinking": False}}}, (False, None)),
        ({"chat_template_kwargs": {"enable_thinking": True}, "thinking_token_budget": 512.0}, (True, 512)),
        ({"temperature": 0.2}, (None, None)),
        (
            {
                "extra_body": {
                    "chat_template_kwargs": {"enable_thinking": "si"},
                    "thinking_token_budget": True,
                }
            },
            (None, None),
        ),
        ({"extra_body": "no es un diccionario"}, (None, None)),
        (None, (None, None)),
    ],
)
def test_razonamiento_pedido_lee_los_dos_sitios_y_nunca_lanza(
    opciones: Any, esperado: tuple[Any, Any]
) -> None:
    datos = kre.razonamiento_pedido(opciones)
    assert (datos["pide_razonar"], datos["presupuesto_razonamiento"]) == esperado


def test_razonamiento_recibido_solo_trae_numeros_y_calla_lo_que_no_se_informo() -> None:
    import types

    uso = types.SimpleNamespace(completion_tokens_details=types.SimpleNamespace(reasoning_tokens=321))
    eleccion = types.SimpleNamespace(
        message=types.SimpleNamespace(reasoning_content="texto que no se guarda")
    )
    assert kre.razonamiento_recibido(eleccion, uso) == {
        "reasoning_tokens": 321,
        "caracteres_razonamiento": 22,
    }
    como_dict = {"message": {"reasoning_content": "abc"}}
    assert kre.razonamiento_recibido(como_dict, {"completion_tokens_details": {"reasoning_tokens": 0}}) == {
        "reasoning_tokens": 0,
        "caracteres_razonamiento": 3,
    }
    assert kre.razonamiento_recibido(types.SimpleNamespace(message=None), None) == {}
    assert kre.razonamiento_recibido(None, types.SimpleNamespace(completion_tokens_details=None)) == {}


def _ficha_de(pide: Any, **fin: Any) -> dict[str, Any]:
    inicio = {"peticion": 1, "tarea": "t", "pide_razonar": pide}
    return kreg._ficha({"inicio": inicio, "fin": {"motivo": "stop", **fin}, "retrollamadas": {}})


def test_el_diagnostico_suma_el_razonamiento_por_tarea_sin_contar_como_cero_lo_no_informado() -> None:
    propias = [
        _ficha_de(
            True, completion_tokens=900, prompt_tokens=5000, reasoning_tokens=700, caracteres_razonamiento=40
        ),
        _ficha_de(True, completion_tokens=100, prompt_tokens=6000),
        _ficha_de(False, completion_tokens=50),
        kreg._ficha({"inicio": {"peticion": 4, "tarea": "t"}, "fin": None, "retrollamadas": {}}),
    ]
    assert kreg.razonamiento_de_la_tarea(propias) == {
        "peticiones_que_piden_razonar": 2,
        "peticiones_que_piden_no_razonar": 1,
        "peticiones_sin_el_dato": 1,
        "prompt_tokens": 11000,
        "peticiones_con_prompt_tokens": 2,
        "completion_tokens": 1050,
        "peticiones_con_completion_tokens": 3,
        "reasoning_tokens": 700,
        "peticiones_con_reasoning_tokens": 1,
        "caracteres_razonamiento": 40,
        "peticiones_con_caracteres_razonamiento": 1,
    }
    # Un registro anterior al #195 no trae nada de esto: None, no cero.
    vieja = kreg.razonamiento_de_la_tarea([_ficha_de(None)])
    assert vieja["reasoning_tokens"] is None and vieja["completion_tokens"] is None
    assert vieja["peticiones_sin_el_dato"] == 1 and vieja["peticiones_que_piden_razonar"] == 0
