"""Una sola orden: rescata de Kaggle y, al terminar, cuenta por llamada lo rescatado.

Es la forma menos invasiva de enganchar la cuenta al rescate: no toca ``scripts/kaggle_rescate.py`` (que pasó
tres revisiones). Recibe los mismos argumentos que él, lo ejecuta tal cual y, si bajó y resumió (salida 0 o
4), ejecuta ``scripts.kaggle_cuenta_llamadas`` sobre la carpeta que el rescate dice haber escrito.

    python -m scripts.kaggle_rescate_y_cuenta --destino <directorio ignorado por git>

Salida del proceso: la del rescate si no fue 0 ni 4. Si fue 0 o 4: 4 si la cuenta leyó con problemas (zip o
traza ilegible), y si no, la del rescate; una carpeta sin nada que contar no cambia la salida del rescate.
Un rescate con faltantes (4) sigue contando lo que bajó.
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import kaggle_cuenta_llamadas, kaggle_rescate


def main(argv: list[str] | None = None) -> int:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        codigo = kaggle_rescate.main(argv)
    sys.stdout.write(buffer.getvalue())
    if codigo not in (kaggle_rescate.EXIT_OK, kaggle_rescate.EXIT_PARCIAL):
        return codigo
    try:
        carpeta = Path(json.loads(buffer.getvalue())["directorio"])
    except (ValueError, KeyError, TypeError):
        print("CUENTA POR LLAMADA: el rescate no dijo su carpeta; no conté", file=sys.stderr)
        return kaggle_cuenta_llamadas.EXIT_ENTRADA
    cuenta = io.StringIO()
    with contextlib.redirect_stdout(cuenta):
        codigo_cuenta = kaggle_cuenta_llamadas.main(["--rescate", str(carpeta)])
    if codigo_cuenta in (kaggle_cuenta_llamadas.EXIT_OK, kaggle_cuenta_llamadas.EXIT_PARCIAL):
        print(f"CUENTA POR LLAMADA escrita en {carpeta / 'cuenta_llamadas.json'} (salida {codigo_cuenta})")
    if codigo_cuenta == kaggle_cuenta_llamadas.EXIT_ENTRADA:
        print("CUENTA POR LLAMADA: no había qué contar (ver arriba); el rescate sí terminó", file=sys.stderr)
        return codigo
    return codigo_cuenta if codigo_cuenta else codigo


if __name__ == "__main__":
    raise SystemExit(main())
