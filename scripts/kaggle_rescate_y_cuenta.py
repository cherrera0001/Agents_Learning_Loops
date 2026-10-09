"""Una sola orden: rescata de Kaggle y, al terminar, cuenta por llamada lo rescatado.

Es la forma menos invasiva de enganchar la cuenta al rescate: no toca ``scripts/kaggle_rescate.py`` (que pasó
tres revisiones). Recibe los mismos argumentos que él, lo ejecuta tal cual y, si bajó y resumió (salida 0 o
4), ejecuta ``scripts.kaggle_cuenta_llamadas`` sobre la carpeta que el rescate dice haber escrito.

    python -m scripts.kaggle_rescate_y_cuenta --destino <directorio ignorado por git>

La salida del rescate se muestra a medida que llega (si el rescate lanza, lo que ya imprimió no se pierde).

Códigos de salida. Los del rescate (``kaggle_rescate.py``) son 0 (bajó y resumió), 2 (entrada inválida o
falta el token), 3 (Kaggle no respondió) y 4 (bajó pero faltó algo); si no son 0 ni 4, se devuelven tal cual
y no se cuenta. Si el rescate salió 0 o 4:

* la cuenta contó: se devuelve el código del rescate, salvo 4 si la cuenta leyó con problemas;
* la cuenta no tenía qué contar (el rescate no trae zips de trazas; su salida 5): se devuelve el código del
  rescate y se dice;
* la cuenta no pudo contar (su salida 2: no pudo escribir, o el detalle caería en una carpeta versionable):
  se devuelve 6, distinto de todos los anteriores, y la causa sale por la salida de error.
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path
from typing import TextIO

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import kaggle_cuenta_llamadas, kaggle_rescate

EXIT_NO_PUDO_CONTAR = 6


class _Eco(io.StringIO):
    """Guarda lo escrito y lo reenvía enseguida a ``destino``."""

    def __init__(self, destino: TextIO) -> None:
        super().__init__()
        self._destino = destino

    def write(self, s: str) -> int:
        self._destino.write(s)
        return super().write(s)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):  # la consola de Windows no siempre es UTF-8
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    salida_del_rescate = _Eco(sys.stdout)
    with contextlib.redirect_stdout(salida_del_rescate):
        codigo = kaggle_rescate.main(argv)
    if codigo not in (kaggle_rescate.EXIT_OK, kaggle_rescate.EXIT_PARCIAL):
        return codigo
    try:
        carpeta = Path(json.loads(salida_del_rescate.getvalue())["directorio"])
    except (ValueError, KeyError, TypeError):
        print("CUENTA POR LLAMADA: el rescate no dijo su carpeta; no pude contar", file=sys.stderr)
        return EXIT_NO_PUDO_CONTAR
    cuenta = io.StringIO()
    with contextlib.redirect_stdout(cuenta):
        codigo_cuenta = kaggle_cuenta_llamadas.main(["--rescate", str(carpeta)])
    if codigo_cuenta == kaggle_cuenta_llamadas.EXIT_NADA_QUE_CONTAR:
        print("CUENTA POR LLAMADA: el rescate no trae trazas; nada que contar", file=sys.stderr)
        return codigo
    if codigo_cuenta not in (kaggle_cuenta_llamadas.EXIT_OK, kaggle_cuenta_llamadas.EXIT_PARCIAL):
        print(f"CUENTA POR LLAMADA: no pude contar (salida {codigo_cuenta}; ver arriba)", file=sys.stderr)
        return EXIT_NO_PUDO_CONTAR
    print(f"CUENTA POR LLAMADA escrita en {carpeta / 'cuenta_llamadas.json'} (salida {codigo_cuenta})")
    return codigo_cuenta if codigo_cuenta else codigo


if __name__ == "__main__":
    raise SystemExit(main())
