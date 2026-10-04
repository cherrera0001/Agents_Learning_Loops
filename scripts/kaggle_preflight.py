"""Chequeo previo local de un notebook de Kaggle, antes de subirlo y gastar cuota.

Comprueba, sin GPU y sin red, lo que en las corridas del 2026-10-03 y 04 falló ya dentro de Kaggle
(episodio 057): una celda con error de sintaxis, la imagen de Python sin fijar, un nombre de acelerador
que no existe, una ruta fija bajo /kaggle/input que no existía en la sesión, y una subida hecha aunque la
validación había fallado. No comprueba que el modelo cargue ni que el agente resuelva: eso exige GPU.

La guardia no solo se lee: **se ejecuta** contra un árbol que reproduce la estructura real de
/kaggle/input. Los datos de la competencia traen su propia carpeta ``wheels/`` con ``.whl``, así que
una guardia que busca «el único directorio con ruedas» encuentra dos y se detiene en toda sesión real.

Uso:
    python -m scripts.kaggle_preflight comprobar <directorio> --tope-min 75

``<directorio>`` es el que recibe ``kaggle kernels push -p``: contiene ``kernel-metadata.json`` y el
notebook. Con todo en orden imprime la orden exacta de subida y sale con 0; con algún fallo sale con 2 y
no imprime la orden. La subida se encadena a este comando con ``&&``.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

COMPETITION_SLUG = "gemma-4-developer-agent"
WHEELHOUSE = "metric/gemma-4-developer-agent-wheelhouse"
# Aceleradores que Kaggle acepta por API y que se han visto funcionar. Un nombre fuera de esta lista no
# da error al subir: Kaggle asigna otra máquina sin avisar.
ACELERADORES = ("NvidiaL4", "NvidiaTeslaT4", "NvidiaTeslaP100")
TOPE_MAXIMO_MIN = 240
RAIZ_ENTRADA = "/kaggle/input"
# Una ruta escrita a mano bajo la raíz de entrada. La raíz sola, que es lo que la guardia lista, no cuenta.
RUTA_FIJA = re.compile(r"/kaggle/input/[A-Za-z0-9_.\-/]+")
# La raíz unida a un componente (concatenación o join) y los componentes de una disposición concreta.
RAIZ_UNIDA = re.compile(r"""['"]/kaggle/input/?['"]\s*(\+|,\s*['"])""")
COMPONENTE_FIJO = re.compile(r"""['"]/?(datasets|competitions)(/[^'"]*)?['"]""")
SECRETO = re.compile(r"KGAT_[A-Za-z0-9]{8,}|\"key\"\s*:\s*\"[0-9a-f]{32}\"")
MODELO = "gemma-4-31b-it-qat-w4a16-ct"
# Estructura del dataset de la competencia según su página «Data»: un archivo de relleno por carpeta.
# La carpeta wheels/ es la que importa aquí: contiene .whl y NO es el directorio de ruedas del arnés.
DATOS_COMPETENCIA = (
    "tasks.jsonl",
    "HARNESS_README.md",
    "docker/Dockerfile.sandbox",
    "embeddings/relleno.npz",
    "graphs/relleno.json",
    "sample_submission/agent.yaml",
    "sandbox/setup.py",
    "snapshots/relleno.tgz",
    "wheels/pytest-8.3.4-py3-none-any.whl",
)
# Ruedas del arnés: lo que distingue su directorio es la rueda de swegemma.
RUEDAS_ARNES = ("swegemma-0.2.7-py3-none-any.whl", "adk_submission-0.2.12-py3-none-any.whl")
ARCHIVOS_MODELO = ("config.json", "model.safetensors")
DISPOSICIONES = ("lotes", "plana")
TOPE_GUARDIA_S = 60

EXIT_OK = 0
EXIT_INVALID = 2


@dataclass(frozen=True)
class Hallazgo:
    ok: bool
    texto: str


def _bien(texto: str) -> Hallazgo:
    return Hallazgo(True, texto)


def _mal(texto: str) -> Hallazgo:
    return Hallazgo(False, texto)


def codigo_comprobable(fuente: str) -> str:
    """La celda sin sus líneas de magia de IPython (``!`` y ``%``), que Python no puede compilar."""
    lineas = []
    for linea in fuente.splitlines():
        sangria = linea[: len(linea) - len(linea.lstrip())]
        lineas.append(f"{sangria}pass" if linea.lstrip().startswith(("!", "%")) else linea)
    return "\n".join(lineas)


def comprobar_metadatos(meta: Any, directorio: Path) -> list[Hallazgo]:
    if not isinstance(meta, dict):
        return [_mal("kernel-metadata.json no es un objeto JSON.")]
    out: list[Hallazgo] = []
    codigo = meta.get("code_file")
    if isinstance(codigo, str) and (directorio / codigo).is_file():
        out.append(_bien(f"El notebook existe: {codigo}"))
    else:
        out.append(_mal(f"code_file no apunta a un archivo del directorio: {codigo!r}"))
    out.append(
        _bien("El notebook es privado.")
        if meta.get("is_private") is True
        else _mal("is_private debe ser true: la salida puede contener datos de la competencia.")
    )
    out.append(
        _bien("Internet apagado.")
        if meta.get("enable_internet") is False
        else _mal("enable_internet debe ser false: las sesiones con L4 lo exigen.")
    )
    for clave in ("competition_sources", "dataset_sources"):
        valor = meta.get(clave)
        if valor is not None and not (isinstance(valor, list) and all(isinstance(x, str) for x in valor)):
            return [*out, _mal(f"{clave} debe ser una lista de textos.")]
    if not isinstance(meta.get("enable_gpu"), bool):
        return [*out, _mal("enable_gpu debe ser true o false, no otro tipo de valor.")]
    competencias = meta.get("competition_sources") or []
    out.append(
        _bien("La competencia está adjunta.")
        if COMPETITION_SLUG in competencias
        else _mal(f"competition_sources no incluye {COMPETITION_SLUG}: sin eso no hay L4 ni datos.")
    )
    imagen = meta.get("docker_image")
    if WHEELHOUSE in (meta.get("dataset_sources") or []):
        out.append(
            _bien("Imagen de Python fijada.")
            if isinstance(imagen, str) and imagen.strip()
            else _mal(
                "docker_image vacío con el dataset de ruedas adjunto: la imagen por defecto puede traer "
                "otra versión de Python y la instalación falla."
            )
        )
    acelerador = meta.get("machine_shape") or ""
    if meta.get("enable_gpu") is True:
        out.append(
            _bien(f"Acelerador conocido: {acelerador}")
            if acelerador in ACELERADORES
            else _mal(
                f"machine_shape {acelerador!r} no está en {list(ACELERADORES)}: Kaggle asignaría otra "
                "máquina sin avisar."
            )
        )
    elif acelerador not in ("", "None"):
        out.append(_mal(f"machine_shape {acelerador!r} con enable_gpu distinto de true."))
    else:
        out.append(_bien("Sin GPU: no gasta cuota."))
    return out


def arbol_de_entrada(raiz: Path, disposicion: str, *, ruedas_arnes: bool = True) -> None:
    """Crea bajo ``raiz`` un /kaggle/input de relleno con la estructura real, en una de sus dos formas.

    ``lotes`` es la de las corridas por API (``competitions/``, ``datasets/<dueño>/``, ``models/``);
    ``plana`` cuelga cada fuente de la raíz por su nombre. Los archivos están vacíos.
    """
    if disposicion not in DISPOSICIONES:
        raise ValueError(f"Disposición desconocida: {disposicion}")
    if disposicion == "lotes":
        datos = raiz / "competitions" / COMPETITION_SLUG
        ruedas = raiz / "datasets" / WHEELHOUSE
    else:
        datos = raiz / COMPETITION_SLUG
        ruedas = raiz / WHEELHOUSE.split("/")[1]
    modelo = raiz / "models" / "google" / "gemma-4" / "other" / MODELO / "2"
    archivos = [datos / relativo for relativo in DATOS_COMPETENCIA]
    archivos += [modelo / nombre for nombre in ARCHIVOS_MODELO]
    if ruedas_arnes:
        archivos += [ruedas / nombre for nombre in RUEDAS_ARNES]
    for archivo in archivos:
        archivo.parent.mkdir(parents=True, exist_ok=True)
        archivo.write_bytes(b"")


def ejecutar_guardia(primera: str, raiz: Path) -> int:
    """Ejecuta la celda de la guardia en otro proceso, con ``raiz`` en lugar de /kaggle/input."""
    fuente = codigo_comprobable(primera).replace(RAIZ_ENTRADA, raiz.as_posix())
    try:
        proceso = subprocess.run(
            [sys.executable, "-c", fuente], capture_output=True, timeout=TOPE_GUARDIA_S, check=False
        )
    except subprocess.TimeoutExpired:
        return -1
    return proceso.returncode


def comprobar_guardia_ejecutada(primera: str) -> list[Hallazgo]:
    """La guardia, ejecutada: pasa con la estructura real y se detiene sin las ruedas del arnés."""
    out: list[Hallazgo] = []
    for disposicion in DISPOSICIONES:
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp) / "input"
            arbol_de_entrada(raiz, disposicion)
            codigo = ejecutar_guardia(primera, raiz)
        out.append(
            _bien(f"Ejecutada con la estructura real ({disposicion}), la guardia pasa.")
            if codigo == 0
            else _mal(
                f"Ejecutada con la estructura real ({disposicion}), la guardia se detiene: los datos de la "
                "competencia traen una carpeta wheels/ con .whl; el directorio de ruedas del arnés es el que "
                "contiene swegemma-*.whl."
            )
        )
    with tempfile.TemporaryDirectory() as tmp:
        raiz = Path(tmp) / "input"
        arbol_de_entrada(raiz, "lotes", ruedas_arnes=False)
        codigo = ejecutar_guardia(primera, raiz)
    out.append(
        _mal("Ejecutada sin las ruedas del arnés, la guardia no se detiene: la corrida gastaría cuota.")
        if codigo == 0
        else _bien("Ejecutada sin las ruedas del arnés, la guardia se detiene.")
    )
    return out


def comprobar_guardia(primera: str) -> list[Hallazgo]:
    """La primera celda localiza las ruedas en /kaggle/input; no espera, no arranca nada y se detiene sola.

    Nombrar el dataset no basta: una guardia con una ruta inventada lo nombra y falla ya dentro de Kaggle.
    """
    out: list[Hallazgo] = []
    lista = "os.listdir" in primera and RAIZ_ENTRADA in primera
    busca = "os.walk" in primera and ".whl" in primera
    out.append(
        _bien("La primera celda lista /kaggle/input y busca el directorio con ruedas.")
        if lista and busca
        else _mal(
            "La primera celda no es la guardia: debe listar /kaggle/input (os.listdir) y buscar con os.walk "
            "el directorio de ruedas del arnés (el que contiene swegemma-*.whl)."
        )
    )
    out.append(
        _bien("La guardia se detiene sola si no encuentra un único directorio.")
        if "raise" in primera
        else _mal("La guardia no se detiene (falta un raise): la corrida seguiría y gastaría cuota.")
    )
    out.append(
        _mal("La guardia espera o reintenta (sleep): si el directorio no está, reintentar no lo crea.")
        if "sleep" in primera
        else _bien("La guardia no espera ni reintenta.")
    )
    out.append(
        _mal("La guardia comparte celda con el servidor del modelo.")
        if re.search(r"vllm|VllmServer", primera, re.IGNORECASE)
        else _bien("La guardia no arranca el servidor del modelo.")
    )
    if all(h.ok for h in out):
        out += comprobar_guardia_ejecutada(primera)
    return out


def comprobar_notebook(notebook: Any, meta: dict[str, Any]) -> list[Hallazgo]:
    celdas = notebook.get("cells") if isinstance(notebook, dict) else None
    if not isinstance(celdas, list):
        return [_mal("El notebook no tiene una lista de celdas.")]
    fuentes: list[str] = []
    for celda in celdas:
        if not isinstance(celda, dict):
            return [_mal("Una celda del notebook no es un objeto.")]
        if celda.get("cell_type") != "code":
            continue
        fuente = celda.get("source", "")
        fuentes.append("".join(fuente) if isinstance(fuente, list) else str(fuente))
    if not fuentes:
        return [_mal("El notebook no tiene celdas de código.")]
    out: list[Hallazgo] = []
    rotas = []
    for numero, fuente in enumerate(fuentes, 1):
        try:
            compile(codigo_comprobable(fuente), f"celda {numero}", "exec")
        except (SyntaxError, ValueError) as exc:
            linea, motivo = getattr(exc, "lineno", None), getattr(exc, "msg", None) or str(exc)
            rotas.append(f"celda {numero}, línea {linea}: {motivo}")
    out.append(
        _mal("Celdas que no compilan: " + "; ".join(rotas))
        if rotas
        else _bien(f"Las {len(fuentes)} celdas de código compilan.")
    )
    todo = "\n".join(fuentes)
    out.append(
        _mal("El notebook (código, texto o salidas) contiene algo con forma de credencial de Kaggle.")
        if SECRETO.search(json.dumps(notebook, ensure_ascii=False))
        else _bien("Sin credenciales en el notebook.")
    )
    fijas = sorted({ruta for fuente in fuentes for ruta in RUTA_FIJA.findall(fuente)})
    if any(RAIZ_UNIDA.search(fuente) for fuente in fuentes):
        fijas.append("/kaggle/input unida a un componente escrito a mano")
    if any(COMPONENTE_FIJO.search(fuente) for fuente in fuentes):
        fijas.append("un componente de disposición (datasets o competitions) escrito a mano")
    out.append(
        _mal(
            "Rutas fijas bajo /kaggle/input: "
            + ", ".join(fijas)
            + ". La disposición cambia entre sesiones: las rutas se localizan, no se escriben."
        )
        if fijas
        else _bien("Ninguna celda escribe una ruta fija bajo /kaggle/input.")
    )
    out += comprobar_guardia(fuentes[0])
    if re.search(r"VllmServer|TransformersServer", todo):
        out.append(
            _bien("Si el servidor del modelo falla, el notebook toma la causa de la salida de la excepción.")
            if re.search(r"getattr\(\s*\w+\s*,\s*['\"]output['\"]|\.output\b", todo)
            else _mal(
                "El notebook arranca el servidor del modelo y no lee la salida de la excepción "
                "(ServerStartupError.output): cuando el servidor no queda sano a tiempo el arnés borra su "
                "archivo de log, y la causa del fallo se pierde."
            )
        )
    if meta.get("enable_gpu") is True:
        out.append(
            _bien("El notebook imprime la GPU asignada.")
            if "nvidia-smi" in todo
            else _mal("Con GPU, el notebook debe ejecutar nvidia-smi para dejar constancia de la máquina.")
        )
    return out


def comprobar(directorio: Path, tope_min: int) -> list[Hallazgo]:
    """Todos los hallazgos del directorio; ninguno ``ok=False`` significa que se puede subir."""
    out: list[Hallazgo] = []
    out.append(
        _bien(f"Tope de ejecución: {tope_min} min.")
        if 0 < tope_min <= TOPE_MAXIMO_MIN
        else _mal(f"--tope-min debe estar entre 1 y {TOPE_MAXIMO_MIN}; ninguna corrida va sin tope.")
    )
    ruta_meta = directorio / "kernel-metadata.json"
    try:
        meta = json.loads(ruta_meta.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [*out, _mal(f"No se pudo leer {ruta_meta.name}: {type(exc).__name__}")]
    out += comprobar_metadatos(meta, directorio)
    if not isinstance(meta, dict) or not isinstance(meta.get("code_file"), str):
        return out
    ruta_nb = directorio / meta["code_file"]
    try:
        notebook = json.loads(ruta_nb.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [*out, _mal(f"No se pudo leer el notebook: {type(exc).__name__}")]
    return out + comprobar_notebook(notebook, meta)


def orden_de_subida(directorio: Path, meta: dict[str, Any], tope_min: int) -> str:
    orden = f'kaggle kernels push -p "{directorio}" -t {tope_min * 60}'
    if meta.get("enable_gpu") is True:
        orden += f" --accelerator {meta.get('machine_shape')}"
    return orden


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="comando", required=True)
    p = sub.add_parser("comprobar", help="Comprueba un directorio de notebook antes de subirlo.")
    p.add_argument("directorio", type=Path, help="Directorio con kernel-metadata.json y el notebook.")
    p.add_argument("--tope-min", type=int, required=True, help="Tope de ejecución en minutos.")
    args = parser.parse_args(argv)

    hallazgos = comprobar(args.directorio, args.tope_min)
    for h in hallazgos:
        print(f"[{'OK' if h.ok else 'FALLA'}] {h.texto}")
    fallos = sum(1 for h in hallazgos if not h.ok)
    if fallos:
        print(f"\nNO SUBIR: {fallos} comprobaciones fallan.", file=sys.stderr)
        return EXIT_INVALID
    meta = json.loads((args.directorio / "kernel-metadata.json").read_text(encoding="utf-8"))
    print("\nSe puede subir. Orden:")
    print(orden_de_subida(args.directorio, meta, args.tope_min))
    if meta.get("enable_gpu") is True:
        print(f"Gasta cuota de GPU: hasta {args.tope_min} min de sesión (L4 cuenta al doble).")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
