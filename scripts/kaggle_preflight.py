"""Chequeo previo local de un notebook de Kaggle, antes de subirlo y gastar cuota.

Comprueba, sin GPU y sin red, lo que en las corridas del 2026-10-03 y 04 falló ya dentro de Kaggle
(episodio 057): una celda con error de sintaxis, la imagen de Python sin fijar, un nombre de acelerador
que no existe, una ruta fija bajo /kaggle/input que no existía en la sesión, y una subida hecha aunque la
validación había fallado. No comprueba que el modelo cargue ni que el agente resuelva: eso exige GPU.

La guardia no solo se lee: **se ejecuta** contra un árbol que reproduce la estructura real de
/kaggle/input. Los datos de la competencia traen su propia carpeta ``wheels/`` con ``.whl``, así que
una guardia que busca «el único directorio con ruedas» encuentra dos y se detiene en toda sesión real.

Desde el 2026-10-12 (#195) compara además el arnés: un notebook que importa ``swegemma``,
``adk_submission``, ``adk_eval_core`` o ``google.adk`` no se da por bueno sin ``--ruedas``, la carpeta con
las ``.whl`` bajadas del conjunto público (o sus fuentes extraídas). Con ella comprueba que sus versiones
son las ensayadas (``scripts/kaggle_arnes.py``) y, leyendo el código como texto, que cada import del notebook
existe en ellas. ``--listado`` añade el listado del conjunto (el ``listado_ruedas.json`` del último rescate o
la salida de ``kaggle datasets files``): versiones y tamaños. No ve un cambio de conducta del arnés que
conserve nombres y firmas.

Desde el concilio 46 (#182) compara también SHA-256, no solo tamaño: si la guarda del notebook trae los
SHA-256 esperados de las ruedas del arnés, exige que sean los de ``kaggle_arnes.RUEDAS_ESPERADAS_SHA256`` y
que las ``.whl`` de ``--ruedas`` los tengan, y dice los dos valores cuando no. Un notebook cuya guarda solo
compara versiones (los armados antes de ese día) recibe un ``[AVISO]``, que no impide la orden de subida.

Desde el 2026-10-14 (#100, sonda G3: tres subidas fallidas) añade cuatro controles que bloquean:

- ``--referencia <dir de un kernel que ya corrió en Kaggle>``: las celdas que instalan ruedas con ``pip``
  deben ser idénticas a las de la referencia (se comparan sin comentarios ni líneas en blanco). Un
  subconjunto de ruedas elegido a mano, o una celda cambiada, falla con el diff. Sin ``--referencia`` en un
  notebook que instala ruedas: ``[AVISO]``.
- ``from_pretrained(..., device_map=...)`` sin ``max_memory`` falla (salvo ``"cpu"`` o un dict literal).
- ``--imagen <imagen_paquetes.json>`` (``{distribución: versión}``, el inventario que escribe la sonda G3) y
  ``--ruedas``: el cierre de ``Requires-Dist`` (sin extras, con los marcadores evaluados para Linux y Python
  3.12) de todas las ``.whl`` de ``--ruedas`` contra la imagen más esas ruedas; falla si falta una
  distribución o su versión no cumple el requisito, y si se da un conflicto conocido (``peft<0.20`` con
  ``torchao<0.16``). No ve conflictos opcionales ni nuevos que no estén en la lista, ni lo que una rueda
  nueva rompe en un paquete de la imagen; supone que el notebook instala todas las ``.whl`` de ``--ruedas``.
- Un ``INFORME.md`` en el directorio con una línea «sin comprobar» y sin una línea «Aceptado por:» en la misma
  línea o en la anterior o siguiente (sin contar las vacías) falla: un hueco declarado no se sube solo.

Uso:
    python -m scripts.kaggle_preflight comprobar <directorio> --tope-min 75
    python -m scripts.kaggle_preflight comprobar <dir> --tope-min 75 --ruedas <carpeta> [--listado <archivo>]
    python -m scripts.kaggle_preflight comprobar <dir> --tope-min 75 --referencia <dir-que-ya-corrió>
    python -m scripts.kaggle_preflight comprobar <dir> --tope-min 75 --imagen <json> --ruedas <carpeta>

``<directorio>`` es el que recibe ``kaggle kernels push -p``: contiene ``kernel-metadata.json`` y el
notebook. Con todo en orden imprime la orden exacta de subida y sale con 0; con algún fallo sale con 2 y
no imprime la orden. La subida se encadena a este comando con ``&&``.
"""

from __future__ import annotations

import argparse
import ast
import difflib
import json
import re
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from email.parser import Parser
from pathlib import Path
from typing import Any

from scripts import kaggle_arnes

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
    # Un aviso no impide subir (``ok`` sigue en True) pero no se imprime como «OK»: dice qué no se comprobó.
    aviso: bool = False


def _bien(texto: str) -> Hallazgo:
    return Hallazgo(True, texto)


def _aviso(texto: str) -> Hallazgo:
    return Hallazgo(True, texto, aviso=True)


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
    out.append(comprobar_device_map(fuentes))
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


def comprobar_device_map(fuentes: list[str]) -> Hallazgo:
    """``from_pretrained(..., device_map=...)`` sin ``max_memory`` es un fallo (OOM de la sonda G3).

    ``device_map="auto"`` reparte según el tamaño comprimido de los pesos y una GPU se queda sin memoria al
    descomprimir. Se exceptúan ``device_map="cpu"``, ``None`` y un dict escrito en la llamada. Un mapa que
    viene de una variable o de una llamada también falla: se pasa ``max_memory`` igualmente. Una llamada con
    ``**kwargs`` falla porque no se ve si lleva ``max_memory``. Las celdas que no compilan no se miran.
    """
    sitios: list[str] = []
    for numero, fuente in enumerate(fuentes, 1):
        try:
            arbol = ast.parse(codigo_comprobable(fuente))
        except (SyntaxError, ValueError):
            continue
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, ast.Call):
                continue
            f = nodo.func
            nombre = f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else None
            if nombre != "from_pretrained":
                continue
            claves = {k.arg: k.value for k in nodo.keywords}
            if "device_map" not in claves or "max_memory" in claves:
                continue
            valor = claves["device_map"]
            if isinstance(valor, ast.Dict) or (
                isinstance(valor, ast.Constant) and (valor.value is None or valor.value == "cpu")
            ):
                continue
            sitios.append(f"celda {numero}, línea {nodo.lineno}")
    if sitios:
        return _mal(
            "from_pretrained(device_map=...) sin max_memory en "
            + "; ".join(sitios)
            + ": device_map reparte según el tamaño comprimido y una GPU se queda sin memoria al "
            "descomprimir (OOM de la sonda G3). Pasa max_memory={i: tope_por_gpu} o un device_map literal."
        )
    return _bien("Ninguna llamada from_pretrained pasa device_map sin max_memory.")


# --- Ruedas: la celda de instalación probada, el cierre de dependencias y los conflictos conocidos (#100) ---

INSTALA_CON_PIP = re.compile(r"""pip['"]?\s*[,\s]\s*['"]?install""")
MENCIONA_RUEDAS = re.compile(r"\.whl|wheel", re.IGNORECASE)
MAX_LINEAS_DIFF = 40
# Para evaluar los marcadores de Requires-Dist: la máquina de Kaggle, no la de quien comprueba. La versión de
# Python es la que se fija en la imagen del kernel (3.12).
ENTORNO_IMAGEN = {
    "sys_platform": "linux",
    "platform_system": "Linux",
    "os_name": "posix",
    "platform_machine": "x86_64",
    "implementation_name": "cpython",
    "platform_python_implementation": "CPython",
    "python_version": "3.12",
    "python_full_version": "3.12.0",
    "extra": "",
}
# (distribución, versiones afectadas, otra distribución, versiones afectadas, explicación): falla si las dos
# están presentes con esas versiones. Solo lo que ya falló en una subida; no se deduce nada más.
CONFLICTOS_CONOCIDOS = (
    (
        "peft",
        "<0.20",
        "torchao",
        "<0.16",
        "peft<0.20 rechaza torchao<0.16 al importarse (sonda G3, 2026-10-14: peft 0.19.1 de la imagen con "
        "torchao 0.10.0). Sube torchao a 0.16 o más, o quítalo de la imagen, antes de subir.",
    ),
)


def _normalizado(texto: str) -> str:
    """El código de una celda sin comentarios de línea completa ni líneas en blanco, sin espacios al final."""
    lineas = [x.rstrip() for x in texto.splitlines()]
    return "\n".join(x for x in lineas if x.strip() and not x.lstrip().startswith("#"))


def celdas_de_instalacion(celdas: list[str]) -> list[str]:
    """Las celdas que corren ``pip install`` con ruedas, normalizadas, en orden."""
    return [_normalizado(c) for c in celdas if INSTALA_CON_PIP.search(c) and MENCIONA_RUEDAS.search(c)]


def leer_celdas_del_directorio(directorio: Path) -> list[str] | None:
    """Las celdas de código del notebook de un directorio de kernel; ``None`` si no se puede leer."""
    try:
        meta = json.loads((directorio / "kernel-metadata.json").read_text(encoding="utf-8"))
        ruta = directorio / meta["code_file"]
    except (OSError, UnicodeDecodeError, ValueError, KeyError, TypeError):
        otros = sorted(directorio.glob("*.ipynb")) if directorio.is_dir() else []
        if len(otros) != 1:
            return None
        ruta = otros[0]
    try:
        return kaggle_arnes.celdas_de_codigo(json.loads(ruta.read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError, ValueError):
        return None


def comprobar_instalacion_de_ruedas(celdas: list[str], referencia: list[str] | None) -> list[Hallazgo]:
    """Las celdas de instalación del notebook contra las de un kernel que ya corrió en Kaggle.

    La sonda G3 (2026-10-14) instaló a mano cinco ruedas del conjunto en lugar de la celda probada, que
    instala el conjunto entero, y faltó ``loguru``. Una celda distinta de la probada es un fallo con el diff.
    """
    propias = celdas_de_instalacion(celdas)
    if not propias:
        return [_bien("El notebook no instala ruedas con pip: no hay celda de instalación que comparar.")]
    if referencia is None:
        return [
            _aviso(
                "El notebook instala ruedas con pip y no se dio --referencia <directorio de un kernel que "
                "ya corrió en Kaggle>: no se comprobó que la celda de instalación sea la probada."
            )
        ]
    probadas = celdas_de_instalacion(referencia)
    if not probadas:
        return [_mal("La referencia no tiene celda de instalación de ruedas: no sirve para comparar.")]
    if propias == probadas:
        return [_bien(f"Las {len(propias)} celdas de instalación de ruedas son las de la referencia.")]
    diff = list(
        difflib.unified_diff(
            "\n".join(probadas).splitlines(),
            "\n".join(propias).splitlines(),
            "referencia",
            "notebook",
            lineterm="",
            n=1,
        )
    )
    corte = diff[:MAX_LINEAS_DIFF] + (
        [f"... ({len(diff) - MAX_LINEAS_DIFF} líneas más)"] if len(diff) > MAX_LINEAS_DIFF else []
    )
    return [
        _mal(
            "La celda de instalación de ruedas no es la de la referencia (un subconjunto elegido a mano "
            "dejó sin instalar loguru en la sonda G3). Diff:\n" + "\n".join(corte)
        )
    ]


def leer_imagen(ruta: Path) -> dict[str, str]:
    """``{distribución normalizada: versión}`` de un ``imagen_paquetes.json``; ``ValueError`` si no lo es."""
    datos = json.loads(ruta.read_text(encoding="utf-8-sig"))
    if not isinstance(datos, dict) or not all(isinstance(v, str) for v in datos.values()):
        raise ValueError("el inventario debe ser un objeto {distribución: versión}")
    return {kaggle_arnes.normalizar_dist(k): v for k, v in datos.items()}


def requisitos_de_rueda(ruta: Path) -> tuple[str, str, list[str]] | None:
    """``(distribución, versión, Requires-Dist)`` del METADATA de la ``.whl``; ``None`` si no lo tiene."""
    try:
        with zipfile.ZipFile(ruta) as z:
            nombre = next((n for n in z.namelist() if n.endswith(".dist-info/METADATA")), None)
            if nombre is None:
                return None
            meta = Parser().parsestr(z.read(nombre).decode("utf-8", errors="replace"))
    except (OSError, zipfile.BadZipFile):
        return None
    if not meta["Name"] or not meta["Version"]:
        return None
    return meta["Name"], meta["Version"], meta.get_all("Requires-Dist") or []


def comprobar_cierre_contra_imagen(imagen: dict[str, str], ruedas: Path | None) -> list[Hallazgo]:
    """Cierre de ``Requires-Dist`` de las ``.whl`` de ``ruedas`` contra la imagen más esas ruedas.

    ``pip install --no-deps`` no resuelve nada: una dependencia que ni la imagen ni las ruedas traen se
    descubre al importar, ya dentro de Kaggle. Los conflictos conocidos se miran sobre el mismo conjunto.
    """
    from packaging.requirements import InvalidRequirement, Requirement
    from packaging.specifiers import SpecifierSet
    from packaging.version import InvalidVersion, Version

    efectivo = dict(imagen)
    pedidas: list[tuple[str, str, str]] = []  # (rueda, requisito, texto)
    out: list[Hallazgo] = []
    if ruedas is not None:
        archivos = sorted(ruedas.glob("*.whl"))
        leidas = [(a, requisitos_de_rueda(a)) for a in archivos]
        ilegibles = [a.name for a, r in leidas if r is None]
        if not archivos:
            return [_mal(f"--ruedas {ruedas} no tiene ningún .whl: no hay cierre que calcular.")]
        if ilegibles:
            out.append(_mal("Ruedas sin METADATA legible: " + ", ".join(ilegibles) + "."))
        for _a, r in leidas:
            if r is not None:
                efectivo[kaggle_arnes.normalizar_dist(r[0])] = r[1]
        for _a, r in leidas:
            if r is None:
                continue
            for linea in r[2]:
                try:
                    req = Requirement(linea)
                    aplica = req.marker is None or req.marker.evaluate(ENTORNO_IMAGEN)
                except InvalidRequirement:
                    out.append(_mal(f"Requires-Dist ilegible en {r[0]}: {linea!r}."))
                    continue
                if aplica:
                    pedidas.append((r[0], kaggle_arnes.normalizar_dist(req.name), linea))
        faltan: dict[str, list[str]] = {}
        incumplen: list[str] = []
        for rueda, nombre, linea in pedidas:
            if nombre not in efectivo:
                faltan.setdefault(nombre, []).append(rueda)
                continue
            try:
                ok = Requirement(linea).specifier.contains(Version(efectivo[nombre]), prereleases=True)
            except InvalidVersion:
                ok = True
            if not ok:
                incumplen.append(f"{rueda} pide {linea} y hay {efectivo[nombre]}")
        if faltan:
            out.append(
                _mal(
                    "Dependencias que ni la imagen ni las ruedas traen (sin internet no se instalan): "
                    + "; ".join(
                        f"{n} (pedida por {', '.join(sorted(set(v)))})" for n, v in sorted(faltan.items())
                    )
                    + "."
                )
            )
        if incumplen:
            out.append(
                _mal("Requisitos que la versión disponible no cumple: " + "; ".join(sorted(incumplen)) + ".")
            )
        if not faltan and not incumplen and not any(not h.ok for h in out):
            out.append(
                _bien(
                    f"Cierre de dependencias: las {len(archivos)} ruedas piden {len(pedidas)} requisitos y "
                    "todos están en la imagen o en las ruedas con versión válida."
                )
            )
    else:
        out.append(
            _aviso(
                "Se dio --imagen sin --ruedas: no se calculó el cierre de dependencias, solo los conflictos."
            )
        )
    for a, spec_a, b, spec_b, explicacion in CONFLICTOS_CONOCIDOS:
        va, vb = efectivo.get(a), efectivo.get(b)
        try:
            if (
                va is not None
                and vb is not None
                and SpecifierSet(spec_a).contains(Version(va), prereleases=True)
                and SpecifierSet(spec_b).contains(Version(vb), prereleases=True)
            ):
                out.append(_mal(f"Conflicto conocido: {a} {va} con {b} {vb}. {explicacion}"))
        except InvalidVersion:
            continue
    if not any(not h.ok and h.texto.startswith("Conflicto conocido") for h in out):
        out.append(
            _bien(f"Ninguno de los conflictos conocidos de la lista ({len(CONFLICTOS_CONOCIDOS)}) se da.")
        )
    return out


def comprobar_informe(directorio: Path) -> list[Hallazgo]:
    """Un ``INFORME.md`` con «sin comprobar» y sin «Aceptado por:» al lado bloquea la subida.

    El 2026-10-14 el constructor declaró «sin comprobar CUDA ni memoria» y la subida siguió. Un hueco
    declarado necesita a alguien que lo acepte con nombre: ``Aceptado por: <quién>`` en la misma línea o en la
    línea anterior o siguiente (sin contar las vacías).
    """
    ruta = directorio / "INFORME.md"
    if not ruta.is_file():
        return []
    try:
        lineas = ruta.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        return [_mal(f"No se pudo leer INFORME.md: {type(exc).__name__}")]
    aceptado = re.compile(r"aceptado por:\s*\S", re.IGNORECASE)
    no_vacias = [i for i, x in enumerate(lineas) if x.strip()]
    huecos = []
    for i, x in enumerate(lineas):
        if "sin comprobar" not in x.lower():
            continue
        pos = no_vacias.index(i)
        vecinas = [i] + [no_vacias[p] for p in (pos - 1, pos + 1) if 0 <= p < len(no_vacias)]
        if not any(aceptado.search(lineas[j]) for j in vecinas):
            huecos.append(f"línea {i + 1}: {x.strip()}")
    if huecos:
        return [
            _mal(
                "INFORME.md declara algo sin comprobar y nadie lo aceptó (falta «Aceptado por: <quién>» al "
                "lado): " + "; ".join(huecos)
            )
        ]
    return [_bien("INFORME.md no declara huecos sin aceptar.")]


def comprobar_instalacion(
    directorio: Path, ruedas: Path | None, referencia: Path | None, imagen: Path | None
) -> list[Hallazgo]:
    """Los controles de ruedas (#100) sobre el notebook del directorio. Si no se puede leer, no añade nada."""
    celdas = leer_celdas_del_directorio(directorio)
    if celdas is None:
        return []
    out: list[Hallazgo] = []
    celdas_ref = None
    if referencia is not None:
        celdas_ref = leer_celdas_del_directorio(referencia)
        if celdas_ref is None:
            return [_mal(f"No se pudo leer el notebook de --referencia {referencia}.")]
    out += comprobar_instalacion_de_ruedas(celdas, celdas_ref)
    if imagen is not None:
        try:
            inventario = leer_imagen(imagen)
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            return [*out, _mal(f"No se pudo leer --imagen: {type(exc).__name__}")]
        out += comprobar_cierre_contra_imagen(inventario, ruedas)
    elif celdas_de_instalacion(celdas):
        out.append(
            _aviso(
                "El notebook instala ruedas y no se dio --imagen <imagen_paquetes.json>: no se comprobó el "
                "cierre de dependencias ni los conflictos conocidos."
            )
        )
    return out


def comprobar_arnes(celdas: list[str], ruedas: Path | None, listado: Path | None) -> list[Hallazgo]:
    """Las ruedas del arnés contra las versiones con que se ensayó, y los imports del notebook contra ellas.

    El 2026-10-12 una corrida falló a los 106 s porque el conjunto público de ruedas había cambiado y una
    celda importaba un módulo que ya no existía (#195). Un notebook que importa el arnés no se da por bueno
    sin ``--ruedas`` (las ``.whl`` bajadas o sus fuentes extraídas): sin ellas no hay con qué comparar, y
    se dice qué falta. No ejecuta ni instala nada: lee los nombres de archivo y el código como texto.

    No ve un cambio de conducta del arnés que conserve nombres y firmas: eso exige leer el diff de fuentes.
    """
    if not kaggle_arnes.usa_el_arnes(celdas) and ruedas is None and listado is None:
        return [_bien("El notebook no importa el arnés: no hay versiones de ruedas que comparar.")]
    ensayado = kaggle_arnes.ARNES_ENSAYADO
    out: list[Hallazgo] = []
    esperado = kaggle_arnes.esperado_en_el_notebook(celdas)
    if esperado is None:
        out.append(
            _mal(
                "El notebook importa el arnés y no trae la guarda de versiones: debe escribir las versiones "
                "instaladas en un archivo de salida y detenerse si no son las ensayadas (el armado la pone "
                "con scripts/kaggle_arnes.py)."
            )
        )
    elif esperado != ensayado:
        out.append(_mal(f"La guarda del notebook espera {esperado} y se ensayó con {ensayado}."))
    else:
        out.append(_bien("El notebook se detiene si las versiones del arnés no son las ensayadas."))
    # SHA-256 (#182): la versión no basta, el conjunto se volvió a publicar con las mismas versiones.
    sha_esperado = kaggle_arnes.RUEDAS_ESPERADAS_SHA256
    sha_del_notebook = kaggle_arnes.sha256_esperado_en_el_notebook(celdas)
    if esperado is not None and sha_del_notebook is None:
        out.append(
            _aviso(
                "La guarda del notebook no compara el sha256 de las ruedas (armado anterior al concilio 46): "
                "si el conjunto se vuelve a publicar con las mismas versiones, correrá con otro arnés sin "
                "detenerse. Este chequeo no lo impide; rearma el notebook con la guarda por sha256."
            )
        )
    elif sha_del_notebook is not None and sha_del_notebook != sha_esperado:
        distintas = sorted(
            f"{n}: el notebook espera {sha_del_notebook.get(n)} y el esperado es {sha_esperado.get(n)}"
            for n in set(sha_del_notebook) | set(sha_esperado)
            if sha_del_notebook.get(n) != sha_esperado.get(n)
        )
        out.append(
            _mal("La guarda del notebook espera otro sha256 de las ruedas: " + "; ".join(distintas) + ".")
        )
    elif sha_del_notebook is not None:
        out.append(
            _bien(
                f"El notebook se detiene si el sha256 de alguna de las {len(sha_esperado)} ruedas del arnés "
                "no es el esperado."
            )
        )

    entradas: list[dict[str, Any]] = []
    if listado is not None:
        try:
            entradas = kaggle_arnes.leer_listado(listado.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            out.append(_mal(f"No se pudo leer el listado de ruedas: {type(exc).__name__}"))
        else:
            diferencias = kaggle_arnes.diferencias_con_lo_ensayado(
                kaggle_arnes.versiones_de(str(e["nombre"]) for e in entradas)
            )
            fechas = sorted(str(e["fecha"]) for e in entradas if e.get("fecha"))
            out += [_mal(f"El conjunto de ruedas cambió respecto de lo ensayado: {d}.") for d in diferencias]
            if not diferencias:
                out.append(
                    _bien(
                        f"El listado del conjunto de ruedas ({len(entradas)} archivos, el más reciente del "
                        f"{fechas[-1] if fechas else 'sin fecha'}) trae las versiones ensayadas."
                    )
                )
    if ruedas is None:
        if listado is None:
            out.append(
                _mal(
                    "No se compararon las versiones del conjunto de ruedas con las ensayadas: falta "
                    "--listado <listado_ruedas.json del último rescate, o la salida de `kaggle datasets "
                    f"files {WHEELHOUSE}`> o --ruedas <carpeta>."
                )
            )
        out.append(
            _mal(
                "No se comprobaron los imports del notebook contra las ruedas reales: falta --ruedas "
                "<carpeta con las .whl del arnés bajadas del conjunto, o con sus fuentes extraídas>."
            )
        )
        return out
    fuentes = kaggle_arnes.leer_fuentes(ruedas)
    diferencias = kaggle_arnes.diferencias_con_lo_ensayado(fuentes.versiones)
    out += [_mal(f"Las ruedas de --ruedas no son las ensayadas: {d}.") for d in diferencias]
    if not diferencias:
        out.append(_bien(f"Las ruedas de --ruedas son las ensayadas: {dict(sorted(ensayado.items()))}."))
    if entradas:
        por_nombre = {str(e["nombre"]): e.get("bytes") for e in entradas}
        del_arnes = {kaggle_arnes.normalizar_dist(dist) for dist in ensayado}
        distintas = []
        for rueda in sorted(ruedas.glob("*.whl")):
            par = kaggle_arnes.version_de_rueda(rueda.name)
            if par is not None and par[0] in del_arnes and por_nombre.get(rueda.name) != rueda.stat().st_size:
                distintas.append(rueda.name)
        out.append(
            _mal(f"Ruedas de --ruedas que no están en el listado con ese tamaño: {', '.join(distintas)}.")
            if distintas
            else _bien("Las ruedas del arnés de --ruedas tienen el tamaño que dice el listado.")
        )
    if sha_del_notebook is not None:
        # El tamaño no basta: dos ruedas del arnés cambiaron de contenido el 2026-10-12 con los mismos bytes.
        try:
            distintas = kaggle_arnes.diferencias_de_sha256(ruedas, sha_del_notebook)
        except OSError as exc:
            distintas = [f"no se pudieron leer las ruedas ({type(exc).__name__})"]
        out += [
            _mal(f"Las ruedas de --ruedas no son las que la guarda del notebook espera: {d}.")
            for d in distintas
        ]
        if not distintas:
            out.append(
                _bien(
                    f"Las {len(sha_del_notebook)} ruedas del arnés de --ruedas tienen el sha256 que la "
                    "guarda del notebook espera."
                )
            )
    informe = kaggle_arnes.comprobar_imports(celdas, fuentes)
    out += [_mal(f"Import que no existe en las ruedas: {texto}.") for texto in informe.rotos]
    out += [_mal(f"Import sin fuente con que comprobarlo: {texto}.") for texto in informe.sin_fuente]
    if informe.ok:
        out.append(
            _bien(
                f"Los {informe.comprobados} imports del arnés que hace el notebook existen en las ruedas "
                "(leídas como texto, sin ejecutar)."
            )
        )
    elif not informe.rotos and not informe.sin_fuente:
        out.append(_mal("No se encontró ningún import del arnés que comprobar contra las ruedas."))
    return out


def comprobar(directorio: Path, tope_min: int) -> list[Hallazgo]:
    """Los hallazgos del directorio solo (metadatos, celdas, guardia). No mira el arnés: para decidir una
    subida se usa ``comprobar_para_subir``, que añade ``comprobar_arnes``."""
    out: list[Hallazgo] = comprobar_informe(directorio)
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


def comprobar_arnes_del_directorio(
    directorio: Path, ruedas: Path | None, listado: Path | None
) -> list[Hallazgo]:
    """``comprobar_arnes`` sobre el notebook del directorio. Si no se puede leer, no añade nada: eso ya es
    un fallo de ``comprobar``."""
    try:
        meta = json.loads((directorio / "kernel-metadata.json").read_text(encoding="utf-8"))
        notebook = json.loads((directorio / meta["code_file"]).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError, KeyError, TypeError):
        return []
    return comprobar_arnes(kaggle_arnes.celdas_de_codigo(notebook), ruedas, listado)


def comprobar_para_subir(
    directorio: Path,
    tope_min: int,
    ruedas: Path | None = None,
    listado: Path | None = None,
    referencia: Path | None = None,
    imagen: Path | None = None,
) -> list[Hallazgo]:
    """Lo que decide la orden de subida: el directorio (``comprobar``), el arnés (``comprobar_arnes``) y
    las ruedas (``comprobar_instalacion``: referencia, imagen y conflictos conocidos).

    Ninguno ``ok=False`` significa que se puede subir. Un notebook que importa el arnés no pasa sin
    ``ruedas``.
    """
    return (
        comprobar(directorio, tope_min)
        + comprobar_arnes_del_directorio(directorio, ruedas, listado)
        + comprobar_instalacion(directorio, ruedas, referencia, imagen)
    )


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
    p.add_argument(
        "--ruedas",
        type=Path,
        default=None,
        help="Carpeta con las .whl del arnés bajadas del conjunto de ruedas, o con sus fuentes extraídas.",
    )
    p.add_argument(
        "--listado",
        type=Path,
        default=None,
        help="Listado del conjunto de ruedas: listado_ruedas.json del rescate o la salida de la CLI.",
    )
    p.add_argument(
        "--referencia",
        type=Path,
        default=None,
        help="Directorio de un kernel que ya corrió en Kaggle: su celda de instalación es la probada.",
    )
    p.add_argument(
        "--imagen",
        type=Path,
        default=None,
        help="imagen_paquetes.json: inventario {distribución: versión} de la imagen (sonda G3).",
    )
    args = parser.parse_args(argv)

    hallazgos = comprobar_para_subir(
        args.directorio, args.tope_min, args.ruedas, args.listado, args.referencia, args.imagen
    )
    for h in hallazgos:
        print(f"[{'AVISO' if h.aviso else 'OK' if h.ok else 'FALLA'}] {h.texto}")
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
