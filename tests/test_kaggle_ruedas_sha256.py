"""Guarda por SHA-256 de las ruedas del arnés (#182, concilio 46).

El 2026-10-12 el conjunto público de ruedas se volvió a publicar con las mismas versiones y otro contenido.
La guarda del notebook comparaba cadenas de versión, el chequeo previo tamaños y el vigía el listado del
último rescate, que ya era el nuevo: nada lo vio. Aquí, sin red, sin token real y sin código del arnés: las
«ruedas» son zips de relleno. Cada prueba lleva su control (lo mismo, sin el defecto, pasa).
"""

from __future__ import annotations

import hashlib
import importlib.metadata as md
import json
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from scripts import kaggle_arnes as ka
from scripts import kaggle_preflight as kp
from scripts import kaggle_rescate as kr
from scripts import kaggle_vigia as kv

TOKEN = "tok-secreto-de-prueba-182"
AHORA = datetime(2026, 10, 12, 21, 0, tzinfo=UTC)
VERSIONES = {"pytest": md.version("pytest")}  # un paquete instalado: la guarda de versiones no estorba


def sha(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


# ---------------------------------------------------------------------------
# La guarda del notebook
# ---------------------------------------------------------------------------


def carpeta_de_ruedas(tmp_path: Path, contenido: dict[str, bytes]) -> Path:
    carpeta = tmp_path / "ruedas"
    carpeta.mkdir()
    for nombre, datos in contenido.items():
        (carpeta / nombre).write_bytes(datos)
    return carpeta


def correr_guarda(archivo: Path, esperado: dict[str, str], ruedas: Path | None) -> dict[str, Any]:
    espacio: dict[str, Any] = {} if ruedas is None else {"W": str(ruedas)}
    exec(ka.celda_de_versiones(archivo.as_posix(), VERSIONES, esperado), espacio)
    return json.loads(archivo.read_text(encoding="utf-8"))


def test_la_guarda_pasa_con_el_sha256_esperado_y_deja_la_huella_de_cada_rueda(tmp_path: Path) -> None:
    contenido = {"a-1-py3-none-any.whl": b"contenido de a", "b-2-py3-none-any.whl": b"contenido de b"}
    ruedas = carpeta_de_ruedas(tmp_path, {**contenido, ".gitignore": b"x"})
    esperado = {"a-1-py3-none-any.whl": sha(contenido["a-1-py3-none-any.whl"])}
    escrito = correr_guarda(tmp_path / "salida" / "v.json", esperado, ruedas)
    assert escrito["distintas"] == {} and escrito["sha256_distintas"] == {}
    assert escrito["sha256_esperadas"] == esperado
    # La huella queda de todas las .whl, también de las que no se comparan; lo que no es rueda, no
    assert escrito["sha256"] == {nombre: sha(datos) for nombre, datos in contenido.items()}
    assert escrito["ruedas"] == {".gitignore": 1, **{n: len(d) for n, d in contenido.items()}}


def test_un_byte_distinto_con_el_mismo_tamano_detiene_el_notebook_y_deja_los_dos_valores(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """El caso real: misma versión, mismo nombre, mismos bytes de tamaño y otro contenido."""
    nombre = "swegemma-0.2.11-py3-none-any.whl"
    ruedas = carpeta_de_ruedas(tmp_path, {nombre: b"contenido nuevo"})
    esperado = {nombre: sha(b"contenido viejo")}
    assert len(b"contenido nuevo") == len(b"contenido viejo")
    archivo = tmp_path / "v.json"
    with pytest.raises(RuntimeError, match="sha256 distinto del esperado") as error:
        correr_guarda(archivo, esperado, ruedas)
    visto = sha(b"contenido nuevo")
    assert esperado[nombre] in str(error.value) and visto in str(error.value)
    assert "antes de cargar el modelo" in str(error.value)
    escrito = json.loads(archivo.read_text(encoding="utf-8"))  # el archivo queda aunque se detenga
    assert escrito["sha256_distintas"] == {nombre: [esperado[nombre], visto]}
    assert escrito["distintas"] == {}  # la guarda de versiones no vio nada: por eso hace falta esta
    salida = capsys.readouterr().out
    assert f"ARNES sha256 distinto: {nombre} | esperado {esperado[nombre]} | visto {visto}" in salida
    # Control: con el contenido esperado, la misma guarda pasa
    (ruedas / nombre).write_bytes(b"contenido viejo")
    assert correr_guarda(archivo, esperado, ruedas)["sha256_distintas"] == {}


@pytest.mark.parametrize("con_directorio", [True, False])
def test_una_rueda_esperada_que_falta_o_un_directorio_ausente_tambien_detienen(
    tmp_path: Path, con_directorio: bool
) -> None:
    ruedas = carpeta_de_ruedas(tmp_path, {"otra-1-py3-none-any.whl": b"x"}) if con_directorio else None
    esperado = {"a-1-py3-none-any.whl": sha(b"a")}
    archivo = tmp_path / "v.json"
    with pytest.raises(RuntimeError, match="sha256 distinto del esperado"):
        correr_guarda(archivo, esperado, ruedas)
    escrito = json.loads(archivo.read_text(encoding="utf-8"))
    assert escrito["sha256_distintas"] == {"a-1-py3-none-any.whl": [esperado["a-1-py3-none-any.whl"], None]}


def test_si_tambien_difiere_la_version_el_archivo_trae_las_dos_diferencias(tmp_path: Path) -> None:
    ruedas = carpeta_de_ruedas(tmp_path, {"a-1-py3-none-any.whl": b"otra cosa"})
    archivo = tmp_path / "v.json"
    celda = ka.celda_de_versiones(
        archivo.as_posix(), {"pytest": "0.0.1"}, {"a-1-py3-none-any.whl": sha(b"a")}
    )
    with pytest.raises(RuntimeError, match="versiones distintas de las ensayadas"):
        exec(celda, {"W": str(ruedas)})
    escrito = json.loads(archivo.read_text(encoding="utf-8"))
    assert escrito["distintas"] == {"pytest": ["0.0.1", md.version("pytest")]}
    assert escrito["sha256_distintas"] == {"a-1-py3-none-any.whl": [sha(b"a"), sha(b"otra cosa")]}


def test_sin_sha256_la_guarda_es_la_de_siempre_y_quitar_las_lineas_nuevas_la_recupera() -> None:
    """Lo que permite al armado listar la diferencia exacta entre un notebook y el anterior."""
    vieja = ka.celda_de_versiones("/kaggle/working/v.json")
    assert "sha256" not in vieja.lower() and "hashlib" not in vieja
    esperado = {"a-1-py3-none-any.whl": "0" * 64}
    nueva = ka.celda_de_versiones("/kaggle/working/v.json", sha256=esperado)
    anadidas = ka.lineas_de_la_guarda_por_sha256(esperado)
    lineas = nueva.splitlines(keepends=True)
    for linea in anadidas:
        lineas.remove(linea)  # cada una está, y una sola vez más que en la vieja
    assert "".join(lineas) == vieja
    assert len(nueva.splitlines()) == len(vieja.splitlines()) + len(anadidas)
    compile(nueva, "celda", "exec")
    # Un mapa vacío no es «sin sha256»: la guarda sale, y no exige ninguna rueda
    assert ka.MARCA_SHA256 in ka.celda_de_versiones("/kaggle/working/v.json", sha256={})


def test_sha256_esperado_en_el_notebook_solo_acepta_la_guarda_entera() -> None:
    esperado = {"a-1-py3-none-any.whl": "ab" * 32}
    celda = ka.celda_de_versiones("/kaggle/working/v.json", sha256=esperado)
    assert ka.sha256_esperado_en_el_notebook(["x = 1\n", celda]) == esperado
    assert ka.esperado_en_el_notebook([celda]) == ka.ARNES_ENSAYADO  # la de versiones se sigue leyendo
    assert ka.sha256_esperado_en_el_notebook([ka.celda_de_versiones("/kaggle/working/v.json")]) is None
    assert ka.sha256_esperado_en_el_notebook(["x = 1\n"]) is None
    # Declarar la constante sin detenerse, o sin calcular, no es tener la guarda
    sin_parada = celda.replace("raise RuntimeError(f'ARNES: sha256", "print(f'ARNES: sha256")
    assert sin_parada != celda and ka.sha256_esperado_en_el_notebook([sin_parada]) is None
    sin_cuenta = celda.replace("_h.update(_bloque)", "pass")
    assert sin_cuenta != celda and ka.sha256_esperado_en_el_notebook([sin_cuenta]) is None
    rota = celda.replace(f"ARNES_SHA256_ESPERADO = {esperado!r}", "ARNES_SHA256_ESPERADO = {no es python}")
    assert rota != celda and ka.sha256_esperado_en_el_notebook([rota]) is None


def test_las_huellas_esperadas_son_las_cuatro_ruedas_de_las_versiones_ensayadas() -> None:
    assert ka.versiones_de(ka.RUEDAS_ESPERADAS_SHA256) == {k: [v] for k, v in ka.ARNES_ENSAYADO.items()}
    assert all(
        len(h) == 64 and set(h) <= set("0123456789abcdef") for h in ka.RUEDAS_ESPERADAS_SHA256.values()
    )


# ---------------------------------------------------------------------------
# El chequeo previo
# ---------------------------------------------------------------------------

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
PAQUETES = {
    "swegemma": {"swegemma/__init__.py": "x = 1\n", "swegemma/config.py": "class EvalConfig:\n    pass\n"},
    "adk_submission": {"adk_submission/__init__.py": "x = 1\n"},
    "adk_eval_core": {"adk_eval_core/__init__.py": "x = 1\n"},
    "google_adk": {"google/adk/__init__.py": ""},
}


def ruedas_de_relleno(carpeta: Path, cambio: tuple[str, str] | None = None) -> dict[str, str]:
    """Las cuatro ruedas del arnés con las versiones ensayadas; devuelve nombre -> SHA-256.

    ``cambio`` sustituye un texto por otro dentro de los archivos (del mismo largo: la rueda pesa lo mismo).
    """
    carpeta.mkdir(parents=True, exist_ok=True)
    huellas = {}
    for dist, version in ka.ARNES_ENSAYADO.items():
        ruta = carpeta / f"{dist}-{version}-py3-none-any.whl"
        with zipfile.ZipFile(ruta, "w") as z:
            for nombre, texto in PAQUETES[dist].items():
                z.writestr(
                    zipfile.ZipInfo(nombre, (2026, 10, 12, 0, 0, 0)), texto.replace(*(cambio or ("", "")))
                )
        huellas[ruta.name] = ka.sha256_de(ruta)
    return huellas


def directorio(tmp_path: Path, guarda: str) -> Path:
    destino = tmp_path / "kernel"
    destino.mkdir()
    celdas = [GUARDIA, "import subprocess\nsubprocess.run(['nvidia-smi'])\n", guarda]
    celdas.append("from swegemma.config import EvalConfig\n")
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


def fallos(nb: Path, ruedas: Path | None) -> list[str]:
    return [h.texto for h in kp.comprobar_para_subir(nb, 75, ruedas, None) if not h.ok]


@pytest.fixture
def esperadas(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Las ruedas de relleno de ``tmp_path/ruedas`` pasan a ser las esperadas."""
    huellas = ruedas_de_relleno(tmp_path / "ruedas")
    monkeypatch.setattr(ka, "RUEDAS_ESPERADAS_SHA256", huellas)
    return huellas


def test_con_la_guarda_y_las_ruedas_esperadas_el_chequeo_previo_pasa(
    tmp_path: Path, esperadas: dict[str, str], capsys: pytest.CaptureFixture[str]
) -> None:
    nb = directorio(tmp_path, ka.celda_de_versiones("/kaggle/working/v.json", sha256=esperadas))
    orden = ["comprobar", str(nb), "--tope-min", "75", "--ruedas", str(tmp_path / "ruedas")]
    assert kp.main(orden) == kp.EXIT_OK
    salida = capsys.readouterr().out
    assert "[OK] El notebook se detiene si el sha256 de alguna de las 4 ruedas del arnés" in salida
    assert (
        "[OK] Las 4 ruedas del arnés de --ruedas tienen el sha256 que la guarda del notebook espera" in salida
    )
    assert "[AVISO]" not in salida and "Se puede subir" in salida


def test_una_rueda_con_otro_contenido_y_el_mismo_tamano_no_pasa_y_se_dicen_los_dos_valores(
    tmp_path: Path, esperadas: dict[str, str], capsys: pytest.CaptureFixture[str]
) -> None:
    nb = directorio(tmp_path, ka.celda_de_versiones("/kaggle/working/v.json", sha256=esperadas))
    ruedas = tmp_path / "ruedas"
    nombre = "swegemma-0.2.11-py3-none-any.whl"
    assert fallos(nb, ruedas) == []  # control: antes de tocarla, pasa
    antes = (ruedas / nombre).stat().st_size
    ruedas_de_relleno(ruedas, ("    pass\n", "    1234\n"))  # solo cambia swegemma/config.py
    datos = (ruedas / nombre).read_bytes()
    assert len(datos) == antes  # mismo tamaño, mismo nombre, misma versión: solo la huella lo ve
    assert kp.main(["comprobar", str(nb), "--tope-min", "75", "--ruedas", str(ruedas)]) == kp.EXIT_INVALID
    captura = capsys.readouterr()
    assert "Se puede subir" not in captura.out and "NO SUBIR: 1 comprobaciones fallan" in captura.err
    esperado = f"{nombre}: se espera sha256 {esperadas[nombre]} y la de la carpeta tiene {sha(bytes(datos))}"
    assert (
        "[FALLA] Las ruedas de --ruedas no son las que la guarda del notebook espera: " + esperado
        in captura.out
    )


def test_una_guarda_que_espera_otras_huellas_que_las_versionadas_no_pasa(
    tmp_path: Path, esperadas: dict[str, str]
) -> None:
    nombre = "swegemma-0.2.11-py3-none-any.whl"
    otras = {**esperadas, nombre: "0" * 64}
    nb = directorio(tmp_path, ka.celda_de_versiones("/kaggle/working/v.json", sha256=otras))
    textos = fallos(nb, tmp_path / "ruedas")
    assert len(textos) == 2
    assert textos[0] == (
        "La guarda del notebook espera otro sha256 de las ruedas: "
        f"{nombre}: el notebook espera {'0' * 64} y el esperado es {esperadas[nombre]}."
    )
    assert "no son las que la guarda del notebook espera" in textos[1]


def test_una_rueda_esperada_que_falta_en_la_carpeta_o_una_carpeta_de_fuentes_no_pasan(
    tmp_path: Path, esperadas: dict[str, str]
) -> None:
    nb = directorio(tmp_path, ka.celda_de_versiones("/kaggle/working/v.json", sha256=esperadas))
    (tmp_path / "ruedas" / "google_adk-1.36.1-py3-none-any.whl").unlink()
    textos = fallos(nb, tmp_path / "ruedas")
    assert any(
        "google_adk-1.36.1-py3-none-any.whl: se espera sha256" in x and "no trae esa rueda" in x
        for x in textos
    )


def test_un_notebook_con_la_guarda_de_solo_versiones_recibe_un_aviso_y_no_un_ok(
    tmp_path: Path, esperadas: dict[str, str], capsys: pytest.CaptureFixture[str]
) -> None:
    """Los notebooks armados antes del concilio 46: el chequeo no dice que correrán con estas ruedas."""
    nb = directorio(tmp_path, ka.celda_de_versiones("/kaggle/working/v.json"))
    hallazgos = kp.comprobar_para_subir(nb, 75, tmp_path / "ruedas", None)
    (aviso,) = [h for h in hallazgos if h.aviso]
    assert aviso.ok and "no compara el sha256 de las ruedas" in aviso.texto
    assert (
        kp.main(["comprobar", str(nb), "--tope-min", "75", "--ruedas", str(tmp_path / "ruedas")])
        == kp.EXIT_OK
    )
    salida = capsys.readouterr().out
    assert "[AVISO] La guarda del notebook no compara el sha256" in salida
    assert "[OK] La guarda del notebook no compara" not in salida and "tienen el sha256" not in salida


# ---------------------------------------------------------------------------
# El vigía: el conjunto contra lo que vio la última sesión
# ---------------------------------------------------------------------------

ANTES = "2026-10-09T14:43:26.259Z"
DESPUES = "2026-10-12T19:51:41.56Z"
NOMBRES = [f"{d}-{v}-py3-none-any.whl" for d, v in ka.ARNES_ENSAYADO.items()]


def listado(fecha: str, **bytes_de: int) -> list[dict[str, Any]]:
    return [
        {"nombre": n, "bytes": bytes_de.get(n.split("-")[0], 100), "fecha": fecha} for n in sorted(NOMBRES)
    ]


def rescate(
    rescates: Path,
    guardado: list[dict[str, Any]],
    sesiones: dict[str, tuple[str | None, dict[str, int] | None]],
) -> Path:
    """Un rescate con su listado y, por notebook, ``(lastRunTime, ruedas que vio la sesión)``."""
    carpeta = rescates / "2026-10-12T2051Z"
    carpeta.mkdir(parents=True)
    (carpeta / "envios.json").write_text("[]", encoding="utf-8")
    (carpeta / "usuario.txt").write_text("yo", encoding="utf-8")
    (carpeta / "tabla_publica.zip").write_bytes(b"PK")
    contenido = {"conjunto": kr.WHEELHOUSE, "archivos": guardado}
    (carpeta / kr.ARCHIVO_LISTADO).write_text(json.dumps(contenido), encoding="utf-8")
    notebooks = []
    for slug, (arranque, ruedas) in sesiones.items():
        (carpeta / "notebooks" / slug).mkdir(parents=True)
        if arranque is not None:
            notebooks.append({"ref": f"yo/{slug}", "lastRunTime": arranque})
        if ruedas is not None:
            archivo = carpeta / "notebooks" / slug / f"salida__versiones_arnes_{slug.replace('-', '_')}.json"
            archivo.write_text(json.dumps({"ruedas": {".gitignore": 1, **ruedas}}), encoding="utf-8")
    (carpeta / "notebooks.json").write_text(json.dumps(notebooks), encoding="utf-8")
    return carpeta


def api(actual: list[dict[str, Any]]) -> Any:
    def pedir(ruta: str, token: str) -> bytes:
        assert token == TOKEN
        if ruta.startswith("competitions/submissions/list/"):
            return b"[]"
        if ruta.startswith("datasets/list/"):
            crudas = [
                {"name": e["nombre"], "totalBytes": e["bytes"], "creationDate": e["fecha"]} for e in actual
            ]
            return json.dumps({"datasetFiles": crudas}).encode()
        if ruta.startswith("kernels/list"):
            return b"[]"
        raise AssertionError(ruta)

    return pedir


def de_ruedas(rescates: Path, actual: list[dict[str, Any]]) -> list[str]:
    lineas = kv.vigia(
        raiz_repo=rescates.parent,
        entorno={"KAGGLE_API_TOKEN": TOKEN},
        pedir=api(actual),
        ahora=AHORA,
        ruta_hallazgos=rescates.parent / "no_hay_hallazgos.json",
        principal=rescates.parent,
        rescates=rescates,
    )
    assert TOKEN not in "\n".join(lineas)
    return [x for x in lineas if "ruedas" in x.lower()]


def vistas(**bytes_de: int) -> dict[str, int]:
    return {e["nombre"]: e["bytes"] for e in listado(ANTES, **bytes_de)}


def test_el_caso_del_concilio_46_el_rescate_ya_trae_el_listado_nuevo_y_el_vigia_avisa(tmp_path: Path) -> None:
    """La sesión corrió a las 13:57; a las 19:51 se publicaron otras ruedas; el rescate es de las 20:51."""
    nuevo = listado(DESPUES, swegemma=250)
    rescate(tmp_path / "r", nuevo, {"iteracion-08-s2": ("2026-10-12T13:57:31.263Z", vistas())})
    (linea,) = de_ruedas(tmp_path / "r", nuevo)  # contra el rescate nada cambió: sin esto, callaba
    assert linea.startswith(
        "EL CONJUNTO DE RUEDAS DEL ARNÉS YA NO ES EL DE LA ÚLTIMA SESIÓN "
        "(iteracion-08-s2, 2026-10-12T13:57:31Z; 2 cambios: swegemma-0.2.11-py3-none-any.whl: "
        "bytes 100 -> 250; 4 de 4 ruedas con fecha posterior a la sesión (la última, 2026-10-12T19:51:41Z))"
    )
    assert "lo que midió esa sesión es de otro arnés" in linea and "compara su sha256" in linea


def test_el_vigia_calla_si_el_conjunto_es_el_que_vio_la_ultima_sesion(tmp_path: Path) -> None:
    """Control del anterior: mismas ruedas, publicadas antes de que la sesión arrancara."""
    igual = listado(ANTES)
    rescate(tmp_path / "r", igual, {"iteracion-08-s2": ("2026-10-12T13:57:31.263Z", vistas())})
    assert de_ruedas(tmp_path / "r", igual) == []


def test_una_fecha_posterior_con_los_mismos_bytes_tambien_se_avisa(tmp_path: Path) -> None:
    """39 de las 41 ruedas reales se volvieron a publicar sin cambiar de tamaño."""
    republicado = listado(DESPUES)
    rescate(tmp_path / "r", republicado, {"iteracion-08-s2": ("2026-10-12T13:57:31.263Z", vistas())})
    (linea,) = de_ruedas(tmp_path / "r", republicado)
    assert "(iteracion-08-s2, 2026-10-12T13:57:31Z; 1 cambios: 4 de 4 ruedas con fecha posterior" in linea


def test_la_referencia_es_la_sesion_mas_reciente_que_dejo_su_archivo(tmp_path: Path) -> None:
    nuevo = listado(DESPUES, swegemma=250)
    sesiones = {
        "vieja": ("2026-10-12T08:41:00Z", vistas(swegemma=7)),
        "reciente": ("2026-10-12T20:10:00.1234567Z", vistas(swegemma=250)),  # ya con las ruedas nuevas
        "sin-archivo": ("2026-10-12T20:30:00Z", None),  # más reciente, pero no dejó qué comparar
    }
    rescate(tmp_path / "r", nuevo, sesiones)
    assert de_ruedas(tmp_path / "r", nuevo) == []
    # Control: si la reciente no hubiera dejado su archivo, la referencia sería la vieja, y difiere
    (
        tmp_path
        / "r"
        / "2026-10-12T2051Z"
        / "notebooks"
        / "reciente"
        / "salida__versiones_arnes_reciente.json"
    ).unlink()
    (linea,) = de_ruedas(tmp_path / "r", nuevo)
    assert (
        "(vieja, 2026-10-12T08:41:00Z; 2 cambios: swegemma-0.2.11-py3-none-any.whl: bytes 7 -> 250" in linea
    )


def test_sin_hora_de_arranque_compara_bytes_y_dice_que_no_comparo_fechas(tmp_path: Path) -> None:
    nuevo = listado(DESPUES, swegemma=250)
    rescate(tmp_path / "r", nuevo, {"iteracion-08-s2": (None, vistas())})
    (linea,) = de_ruedas(tmp_path / "r", nuevo)
    assert "(iteracion-08-s2, sin hora de arranque: no comparé fechas; 1 cambios: swegemma" in linea
    assert "fecha posterior" not in linea


def test_una_rueda_que_sale_o_entra_y_una_lista_larga_recortada_que_conserva_las_fechas() -> None:
    antes = {f"p{i}-1.0-py3-none-any.whl": 10 for i in range(9)} | {
        "sale-1-py3-none-any.whl": 1,
        "nota.txt": 5,
    }
    ahora = [{"nombre": f"p{i}-1.0-py3-none-any.whl", "bytes": 11, "fecha": DESPUES} for i in range(9)]
    ahora.append({"nombre": "entra-1-py3-none-any.whl", "bytes": 1, "fecha": "sin fecha legible"})
    cambios = ka.cambios_desde_la_sesion(antes, datetime(2026, 10, 12, 13, 57, tzinfo=UTC), ahora)
    assert cambios[:3] == [
        "sale sale-1-py3-none-any.whl",
        "entra entra-1-py3-none-any.whl",
        "p0-1.0-py3-none-any.whl: bytes 10 -> 11",
    ]
    assert cambios[-1] == "9 de 10 ruedas con fecha posterior a la sesión (la última, 2026-10-12T19:51:41Z)"
    assert len(cambios) == 12 and not any("nota.txt" in c for c in cambios)


def test_el_aviso_recortado_muestra_seis_cambios_y_el_ultimo_es_el_de_las_fechas(tmp_path: Path) -> None:
    nombres = [f"p{i}-1.0-py3-none-any.whl" for i in range(9)]
    nuevo = [{"nombre": n, "bytes": 11, "fecha": DESPUES} for n in nombres] + listado(DESPUES)
    antes = {n: 10 for n in nombres} | vistas()
    rescate(tmp_path / "r", nuevo, {"iteracion-08-s2": ("2026-10-12T13:57:31Z", antes)})
    (linea,) = de_ruedas(tmp_path / "r", nuevo)
    assert "10 cambios: p0-1.0-py3-none-any.whl: bytes 10 -> 11" in linea
    assert "p4-1.0-py3-none-any.whl: bytes 10 -> 11; 13 de 13 ruedas con fecha posterior" in linea
    assert "p5-1.0" not in linea and "… y 4 más" in linea


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("2026-10-12T19:51:41.56Z", datetime(2026, 10, 12, 19, 51, 41, tzinfo=UTC)),
        ("2026-10-09 14:43:26.259000", datetime(2026, 10, 9, 14, 43, 26, tzinfo=UTC)),
        ("2026-10-09T20:51:21.3021505Z", datetime(2026, 10, 9, 20, 51, 21, tzinfo=UTC)),
        ("2026-13-45T00:00:00Z", None),
        ("ayer", None),
        (None, None),
    ],
)
def test_fecha_de(texto: Any, esperado: datetime | None) -> None:
    assert ka.fecha_de(texto) == esperado


def test_archivos_ilegibles_de_la_sesion_no_hacen_lanzar_al_vigia(tmp_path: Path) -> None:
    nuevo = listado(DESPUES)
    carpeta = rescate(tmp_path / "r", nuevo, {"rota": ("2026-10-12T13:57:31Z", vistas())})
    (carpeta / "notebooks" / "rota" / "salida__versiones_arnes_rota.json").write_text(
        "no es json", encoding="utf-8"
    )
    (carpeta / "notebooks.json").write_text("{", encoding="utf-8")
    assert kv.ultima_sesion_con_ruedas(carpeta) is None
    assert kv.avisos_de_ruedas(carpeta, TOKEN, api(nuevo), time.monotonic() + 5) == []
    lista = carpeta / "notebooks" / "lista"
    lista.mkdir()
    (lista / "salida__versiones_arnes_lista.json").write_text("[1, 2]", encoding="utf-8")
    assert kv.ultima_sesion_con_ruedas(carpeta) is None
