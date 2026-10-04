"""Chequeo previo local de un notebook de Kaggle, antes de subirlo y gastar cuota.

Comprueba, sin GPU y sin red, lo que en las corridas del 2026-10-03 y 04 falló ya dentro de Kaggle
(episodio 057): una celda con error de sintaxis, la imagen de Python sin fijar, un nombre de acelerador
que no existe, un notebook sin guardia del dataset adjunto y una subida hecha aunque la validación había
fallado. No comprueba que el modelo cargue ni que el agente resuelva: eso exige GPU.

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
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

COMPETITION_SLUG = "gemma-4-developer-agent"
WHEELHOUSE = "metric/gemma-4-developer-agent-wheelhouse"
# Aceleradores que Kaggle acepta por API y que se han visto funcionar. Un nombre fuera de esta lista no
# da error al subir: Kaggle asigna otra máquina sin avisar.
ACELERADORES = ("NvidiaL4", "NvidiaTeslaT4", "NvidiaTeslaP100")
TOPE_MAXIMO_MIN = 240
SECRETO = re.compile(r"KGAT_[A-Za-z0-9]{8,}|\"key\"\s*:\s*\"[0-9a-f]{32}\"")

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
        except SyntaxError as exc:
            rotas.append(f"celda {numero}, línea {exc.lineno}: {exc.msg}")
    out.append(
        _mal("Celdas que no compilan: " + "; ".join(rotas))
        if rotas
        else _bien(f"Las {len(fuentes)} celdas de código compilan.")
    )
    todo = "\n".join(fuentes)
    out.append(
        _mal("El notebook contiene algo con forma de credencial de Kaggle.")
        if SECRETO.search(todo)
        else _bien("Sin credenciales en el notebook.")
    )
    if meta.get("dataset_sources"):
        primera = fuentes[0]
        nombres = [str(fuente).split("/")[-1] for fuente in meta["dataset_sources"]]
        con_guardia = "assert" in primera and all(nombre in primera for nombre in nombres)
        out.append(
            _bien("La primera celda comprueba que el dataset adjunto está montado.")
            if con_guardia
            else _mal(
                "La primera celda no es una guardia del dataset adjunto (debe nombrarlo y llevar un "
                "assert): si llega sin montar, la corrida falla después de gastar cuota."
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
