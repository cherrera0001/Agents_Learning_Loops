"""Esquema ampliado del registro de validez: ``diario_sha256`` y ``ejecuciones_lanzadas`` opcionales.

Los registros anteriores (sin esos campos) siguen siendo validos; si los campos estan, se validan.
Cualquier otra clave sigue sobrando. Datos sinteticos inventados.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from scripts import kaggle_prereg as kp


def _registro(**cambios: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "schema_version": kp.ESQUEMA_VALIDEZ,
        "fecha": "2026-10-05",
        "sha256_tasks": "a" * 64,
        "entorno_sha256": "b" * 64,
        "tareas": [
            {"instance_id": "a__b-1", "repo": "o/a", "clase": "discrimina", "sin_parche_segundos": [1.0, 1.1]}
        ],
        "tareas_invalidas": [],
    }
    base.update(cambios)
    return base


def _leer(tmp_path: Path, obj: dict[str, Any], opcionales: bool = True) -> dict[str, Any]:
    datos = json.dumps(obj).encode()
    (tmp_path / "v.json").write_bytes(datos)
    valor = {"ruta": "v.json", "sha256": hashlib.sha256(datos).hexdigest()}
    return kp._read_record(
        tmp_path,
        valor,
        "validez_tareas",
        kp.VALIDEZ,
        opcionales=kp.VALIDEZ_OPCIONALES if opcionales else None,
    )


def test_registro_sin_los_campos_nuevos_sigue_siendo_valido(tmp_path: Path) -> None:
    assert _leer(tmp_path, _registro())["fecha"] == "2026-10-05"


def test_registro_con_diario_y_ejecuciones_lanzadas_es_valido(tmp_path: Path) -> None:
    obj = _registro(diario_sha256="c" * 64)
    obj["tareas"][0]["ejecuciones_lanzadas"] = 4
    assert _leer(tmp_path, obj)["diario_sha256"] == "c" * 64


@pytest.mark.parametrize("valor", ["zz", "C" * 64, "c" * 63, 5, None])
def test_diario_sha256_invalido_se_rechaza(tmp_path: Path, valor: object) -> None:
    with pytest.raises(kp.PreregError, match="diario_sha256"):
        _leer(tmp_path, _registro(diario_sha256=valor))


@pytest.mark.parametrize("valor", [3, 0, -1, "4", None, True, 4.0])
def test_ejecuciones_lanzadas_invalido_se_rechaza(tmp_path: Path, valor: object) -> None:
    obj = _registro()
    obj["tareas"][0]["ejecuciones_lanzadas"] = valor
    with pytest.raises(kp.PreregError, match="valores invalidos"):
        _leer(tmp_path, obj)


def test_una_clave_desconocida_sigue_sobrando(tmp_path: Path) -> None:
    with pytest.raises(kp.PreregError, match="debe tener las claves"):
        _leer(tmp_path, _registro(extra=1))
    with pytest.raises(kp.PreregError, match="debe tener las claves"):
        _leer(tmp_path, _registro(diario="c" * 64))


def test_sin_opcionales_declarados_el_diario_sobra(tmp_path: Path) -> None:
    """Quien no declara opcionales (el comportamiento anterior) sigue rechazando claves de mas."""
    with pytest.raises(kp.PreregError, match="debe tener las claves"):
        _leer(tmp_path, _registro(diario_sha256="c" * 64), opcionales=False)


def test_las_claves_obligatorias_siguen_siendo_obligatorias(tmp_path: Path) -> None:
    obj = _registro(diario_sha256="c" * 64)
    del obj["entorno_sha256"]
    with pytest.raises(kp.PreregError, match="debe tener las claves"):
        _leer(tmp_path, obj)
