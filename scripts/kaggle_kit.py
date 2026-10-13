"""Arma una variante de un kit de envío cambiando solo lo declarado, y lo comprueba miembro a miembro (#205).

Un candidato de kit es el zip de base con unos pocos miembros cambiados o borrados. Este módulo:

- copia los miembros de la base **en su orden**, con su fecha, sus permisos y sus demás metadatos, y sustituye
  solo los que se declaran (`armar_variante`). Los que no cambian se copian con sus bytes comprimidos, sin
  volver a comprimirlos. Se niega si un cambio declarado no cambia nada, si nombra un miembro que la base no
  tiene, si la base trae nombres repetidos o si no sabe volver a escribirla byte a byte;
- compara dos zips miembro a miembro (`comparar`) y dice qué difiere de lo declarado
  (`diferencias_con_lo_declarado`): la prueba de que «el resto no cambió» no depende de quien armó el zip;
- edita el texto de un miembro por número de línea exigiendo el texto anterior (`reemplazar_linea`,
  `insertar_tras`, `borrar_lineas`): si la base no es la que la especificación describe, se detiene.

No sube nada, no usa red y no lee `benchmark/private/`. Los zips que arma no se versionan.
"""

from __future__ import annotations

import hashlib
import io
import struct
import zipfile
import zlib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Metadatos de cada miembro que se copian tal cual y se comparan. El tamaño y el CRC salen del contenido.
METADATOS = (
    "date_time",
    "compress_type",
    "create_system",
    "create_version",
    "extract_version",
    "flag_bits",
    "external_attr",
    "internal_attr",
    "extra",
    "comment",
)


class KitError(ValueError):
    """La base no es la esperada, o lo que se pide no es un cambio declarado y efectivo."""


def sha256_de(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


def _bytes_de(origen: bytes | Path) -> bytes:
    return origen if isinstance(origen, bytes) else Path(origen).read_bytes()


def leer_miembros(origen: bytes | Path) -> list[tuple[zipfile.ZipInfo, bytes]]:
    """Miembros del zip en su orden, con su contenido. Se niega ante nombres repetidos o carpetas."""
    with zipfile.ZipFile(io.BytesIO(_bytes_de(origen))) as z:
        if z.comment:
            raise KitError("KIT: el zip trae un comentario de archivo; no sé copiarlo")
        miembros = [(info, z.read(info)) for info in z.infolist()]
    nombres = [info.filename for info, _ in miembros]
    repetidos = sorted({n for n in nombres if nombres.count(n) > 1})
    if repetidos:
        raise KitError(f"KIT: el zip trae nombres repetidos: {repetidos}")
    carpetas = [n for n in nombres if n.endswith("/")]
    if carpetas:
        raise KitError(f"KIT: el zip trae entradas de carpeta: {carpetas}")
    return miembros


# --- El zip, registro a registro. Los miembros que no cambian se copian con sus bytes: cabecera local, nombre
# y datos comprimidos. Volver a comprimirlos daría otro flujo con otra versión de zlib (medido: la base se
# comprimió con una y este intérprete trae otra), y «el resto no cambió» dejaría de ser cierto byte a byte.

_LOCAL = struct.Struct(
    "<4s5H3L2H"
)  # firma, versión, banderas, método, hora, fecha, crc, comprimido, tamaño, n, e
_CENTRAL = struct.Struct(
    "<4s6H3L5H2L"
)  # …, crc, comprimido, tamaño, n, e, c, disco, internos, externos, desplaz.
_FIN = struct.Struct(
    "<4s4H2LH"
)  # firma, disco, disco del directorio, entradas aquí, entradas, bytes, desplaz., c
FIRMA_LOCAL, FIRMA_CENTRAL, FIRMA_FIN = b"PK\x03\x04", b"PK\x01\x02", b"PK\x05\x06"
NIVEL_DE_COMPRESION = 9


@dataclass(frozen=True)
class _Registro:
    nombre: str
    local: bytes  # cabecera local, nombre, extra y datos, tal cual están en el zip
    central: bytes  # su entrada del directorio central, tal cual


def _registros(crudo: bytes) -> list[_Registro]:
    """Los registros del zip en el orden del directorio central. Se niega ante lo que no sabe copiar."""
    if len(crudo) < _FIN.size or crudo[-_FIN.size :][:4] != FIRMA_FIN:
        raise KitError("KIT: el zip no termina en su registro de fin (¿trae comentario?); no sé copiarlo")
    _, disco, disco_dir, aqui, entradas, bytes_dir, desplazamiento, _ = _FIN.unpack(crudo[-_FIN.size :])
    if disco or disco_dir or aqui != entradas or entradas == 0xFFFF:
        raise KitError("KIT: zip en varios discos o zip64; no sé copiarlo")
    registros, pos, esperado = [], desplazamiento, 0
    for _ in range(entradas):
        campos = _CENTRAL.unpack_from(crudo, pos)
        if campos[0] != FIRMA_CENTRAL:
            raise KitError("KIT: el directorio central del zip no se puede leer")
        banderas, comprimido, largo_nombre, largo_extra, largo_nota, donde = (
            campos[3],
            campos[8],
            campos[10],
            campos[11],
            campos[12],
            campos[16],
        )
        if banderas & 0x09:
            raise KitError("KIT: miembro cifrado o con descriptor de datos; no sé copiarlo")
        central = crudo[pos : pos + _CENTRAL.size + largo_nombre + largo_extra + largo_nota]
        pos += len(central)
        cabecera = _LOCAL.unpack_from(crudo, donde)
        if cabecera[0] != FIRMA_LOCAL or donde != esperado:
            raise KitError("KIT: los registros del zip no van seguidos desde el principio; no sé copiarlo")
        local = crudo[donde : donde + _LOCAL.size + cabecera[9] + cabecera[10] + comprimido]
        esperado += len(local)
        nombre = central[_CENTRAL.size : _CENTRAL.size + largo_nombre]
        registros.append(_Registro(nombre.decode("utf-8" if banderas & 0x800 else "cp437"), local, central))
    if esperado != desplazamiento or pos != desplazamiento + bytes_dir or pos != len(crudo) - _FIN.size:
        raise KitError("KIT: el zip trae bytes fuera de sus registros; no sé copiarlo")
    return registros


def _montar(registros: Sequence[_Registro]) -> bytes:
    locales, centrales, donde = [], [], 0
    for r in registros:
        locales.append(r.local)
        centrales.append(r.central[:42] + struct.pack("<L", donde) + r.central[46:])
        donde += len(r.local)
    directorio = b"".join(centrales)
    fin = _FIN.pack(FIRMA_FIN, 0, 0, len(registros), len(registros), len(directorio), donde, 0)
    return b"".join(locales) + directorio + fin


def _con_contenido(registro: _Registro, datos: bytes) -> _Registro:
    """El mismo registro con otro contenido: cambian el CRC, los dos tamaños y los datos, y nada más."""
    cabecera = _LOCAL.unpack_from(registro.local)
    metodo = cabecera[3]
    if metodo == zipfile.ZIP_DEFLATED:
        compresor = zlib.compressobj(NIVEL_DE_COMPRESION, zlib.DEFLATED, -15)
        cuerpo = compresor.compress(datos) + compresor.flush()
    elif metodo == zipfile.ZIP_STORED:
        cuerpo = datos
    else:
        raise KitError(f"KIT: {registro.nombre} usa un método de compresión que no sé escribir: {metodo}")
    medidas = struct.pack("<3L", zlib.crc32(datos), len(cuerpo), len(datos))
    resto = _LOCAL.size + cabecera[9] + cabecera[10]
    local = registro.local[:14] + medidas + registro.local[26:resto] + cuerpo
    central = registro.central[:16] + medidas + registro.central[28:]
    return _Registro(registro.nombre, local, central)


def reescribir(base: bytes | Path) -> bytes:
    """El zip vuelto a montar sin cambios. Si no sale igual que entró, este módulo no sabe copiarlo."""
    return _montar(_registros(_bytes_de(base)))


def armar_variante(base: bytes | Path, cambios: Mapping[str, bytes], borrados: Iterable[str] = ()) -> bytes:
    """El zip de base con `cambios` (nombre -> contenido nuevo) y sin `borrados`; lo demás, tal cual.

    Los miembros conservan su orden, su fecha y sus permisos, y los que no cambian conservan también sus bytes
    comprimidos. No se añaden miembros: un nombre que la base no tiene es un error, igual que un cambio que
    deja el contenido como estaba o un zip sin ningún cambio.
    """
    crudo = _bytes_de(base)
    borrados = list(borrados)
    contenido = {info.filename: datos for info, datos in leer_miembros(crudo)}
    registros = _registros(crudo)
    if [r.nombre for r in registros] != list(contenido) or _montar(registros) != crudo:
        raise KitError("KIT: no sé volver a escribir la base byte a byte; no sigo")
    ajenos = sorted(n for n in [*cambios, *borrados] if n not in contenido)
    if ajenos:
        raise KitError(f"KIT: la base no tiene estos miembros: {ajenos}")
    dobles = sorted(set(cambios) & set(borrados))
    if dobles:
        raise KitError(f"KIT: miembros declarados a la vez como cambiados y borrados: {dobles}")
    if len(set(borrados)) != len(borrados):
        raise KitError(f"KIT: miembros borrados dos veces: {sorted(borrados)}")
    if not cambios and not borrados:
        raise KitError("KIT: no se declaró ningún cambio")
    nuevos: list[_Registro] = []
    for registro in registros:
        if registro.nombre in borrados:
            continue
        if registro.nombre in cambios:
            if cambios[registro.nombre] == contenido[registro.nombre]:
                raise KitError(f"KIT: el cambio declarado en {registro.nombre} deja el contenido como estaba")
            registro = _con_contenido(registro, cambios[registro.nombre])
        nuevos.append(registro)
    if not nuevos:
        raise KitError("KIT: la variante quedaría sin miembros")
    variante = _montar(nuevos)
    esperado = {n: cambios.get(n, d) for n, d in contenido.items() if n not in borrados}
    if {info.filename: datos for info, datos in leer_miembros(variante)} != esperado:
        raise KitError("KIT: la variante escrita no se lee como se esperaba")
    return variante


def registros_identicos(base: bytes | Path, variante: bytes | Path) -> list[str]:
    """Miembros cuyo registro local (cabecera, nombre y datos comprimidos) es igual byte a byte en los dos."""
    de_base = {r.nombre: r.local for r in _registros(_bytes_de(base))}
    return [r.nombre for r in _registros(_bytes_de(variante)) if de_base.get(r.nombre) == r.local]


def comparar(base: bytes | Path, variante: bytes | Path) -> dict[str, Any]:
    """Miembros idénticos, cambiados, borrados y añadidos, y si se conservan el orden y los metadatos."""
    de_base = leer_miembros(base)
    de_variante = leer_miembros(variante)
    a = {info.filename: (info, datos) for info, datos in de_base}
    b = {info.filename: (info, datos) for info, datos in de_variante}
    comunes = [n for n in a if n in b]
    metadatos = [
        f"{n}: {campo} {getattr(a[n][0], campo)!r} -> {getattr(b[n][0], campo)!r}"
        for n in comunes
        for campo in METADATOS
        if getattr(a[n][0], campo) != getattr(b[n][0], campo)
    ]
    return {
        "base_sha256": sha256_de(_bytes_de(base)),
        "variante_sha256": sha256_de(_bytes_de(variante)),
        "miembros_de_la_base": list(a),
        "miembros_de_la_variante": list(b),
        "identicos": [n for n in comunes if a[n][1] == b[n][1]],
        "cambiados": [n for n in comunes if a[n][1] != b[n][1]],
        "borrados": [n for n in a if n not in b],
        "anadidos": [n for n in b if n not in a],
        "orden_conservado": [n for n in b if n in a] == comunes,
        "metadatos_distintos": metadatos,
        "sha256_por_miembro": {
            n: [sha256_de(a[n][1]) if n in a else None, sha256_de(b[n][1]) if n in b else None]
            for n in [*a, *(n for n in b if n not in a)]
        },
    }


def diferencias_con_lo_declarado(
    base: bytes | Path, variante: bytes | Path, cambian: Iterable[str], se_borran: Iterable[str] = ()
) -> list[str]:
    """Lista de lo que no cuadra con lo declarado; vacía si la variante cambia eso y nada más."""
    c = comparar(base, variante)
    problemas = []
    if sorted(c["cambiados"]) != sorted(cambian):
        problemas.append(f"miembros cambiados {sorted(c['cambiados'])}, declarados {sorted(cambian)}")
    if sorted(c["borrados"]) != sorted(se_borran):
        problemas.append(f"miembros borrados {sorted(c['borrados'])}, declarados {sorted(se_borran)}")
    if c["anadidos"]:
        problemas.append(f"miembros añadidos: {c['anadidos']}")
    if not c["orden_conservado"]:
        problemas.append(f"el orden de los miembros cambió: {c['miembros_de_la_variante']}")
    problemas.extend(f"metadatos distintos en {m}" for m in c["metadatos_distintos"])
    return problemas


# --- Edición de un miembro de texto por número de línea (desde 1), exigiendo lo que había


def _lineas(texto: str) -> list[str]:
    if "\r" in texto:
        raise KitError("KIT: el texto trae retornos de carro; se esperaban saltos LF")
    if not texto.endswith("\n"):
        raise KitError("KIT: el texto no termina en salto de línea")
    return texto[:-1].split("\n")


def _unir(lineas: Sequence[str]) -> str:
    return "\n".join(lineas) + "\n"


def _exigir(lineas: Sequence[str], numero: int, esperada: str) -> None:
    if not 1 <= numero <= len(lineas):
        raise KitError(f"KIT: no hay línea {numero} (el texto tiene {len(lineas)})")
    if lineas[numero - 1] != esperada:
        raise KitError(f"KIT: la línea {numero} no es la esperada: {lineas[numero - 1][:120]!r}")


def reemplazar_linea(texto: str, numero: int, antes: str, despues: str) -> str:
    """Cambia la línea `numero`, que debe ser exactamente `antes`, por `despues`."""
    lineas = _lineas(texto)
    _exigir(lineas, numero, antes)
    if antes == despues or "\n" in despues:
        raise KitError(f"KIT: el reemplazo de la línea {numero} no cambia nada o trae un salto de línea")
    lineas[numero - 1] = despues
    return _unir(lineas)


def insertar_tras(texto: str, numero: int, ancla: str, nuevas: Sequence[str]) -> str:
    """Inserta `nuevas` después de la línea `numero`, que debe ser exactamente `ancla`."""
    lineas = _lineas(texto)
    _exigir(lineas, numero, ancla)
    if not nuevas or any("\n" in x for x in nuevas):
        raise KitError(f"KIT: nada que insertar tras la línea {numero}, o una línea trae un salto")
    return _unir([*lineas[:numero], *nuevas, *lineas[numero:]])


def borrar_lineas(texto: str, desde: int, esperadas: Sequence[str]) -> str:
    """Borra las líneas `desde`… que deben ser exactamente `esperadas`."""
    lineas = _lineas(texto)
    if not esperadas:
        raise KitError("KIT: no se declaró ninguna línea que borrar")
    for k, esperada in enumerate(esperadas):
        _exigir(lineas, desde + k, esperada)
    return _unir([*lineas[: desde - 1], *lineas[desde - 1 + len(esperadas) :]])
