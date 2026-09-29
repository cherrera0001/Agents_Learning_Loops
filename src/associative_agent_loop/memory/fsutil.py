"""Utilidades de sistema de archivos (módulo hoja: sin dependencias internas)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def atomic_write_text(path: str | Path, content: str) -> None:
    """Escribe ``content`` en ``path`` de forma atómica (todo o nada).

    Escribe a un temporal en el mismo directorio y lo renombra con
    ``os.replace``, que es atómico en POSIX y Windows: un proceso interrumpido
    nunca deja un archivo truncado.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, target)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
