"""Esquema del registro de validez: ``diario_sha256`` y ``ejecuciones_lanzadas`` son obligatorios.

Una compuerta que aceptara un registro de validez sin diario anularia el rastro de las ejecuciones.
Datos sinteticos inventados.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from scripts import kaggle_prereg as kp


def _registro() -> dict[str, Any]:
    return {
        "schema_version": kp.ESQUEMA_VALIDEZ,
        "fecha": "2026-10-05",
        "sha256_tasks": "a" * 64,
        "entorno_sha256": "b" * 64,
        "tareas": [
            {
                "instance_id": "a__b-1",
                "repo": "o/a",
                "clase": "discrimina",
                "sin_parche_segundos": [1.0, 1.1],
                "ejecuciones_lanzadas": 4,
            }
        ],
        "tareas_invalidas": [],
        "diario_sha256": "c" * 64,
    }


def _leer(tmp_path: Path, obj: dict[str, Any]) -> dict[str, Any]:
    datos = json.dumps(obj).encode()
    (tmp_path / "v.json").write_bytes(datos)
    valor = {"ruta": "v.json", "sha256": hashlib.sha256(datos).hexdigest()}
    return kp._read_record(tmp_path, valor, "validez_tareas", kp.VALIDEZ)


def test_registro_completo_es_valido(tmp_path: Path) -> None:
    assert _leer(tmp_path, _registro())["diario_sha256"] == "c" * 64


def test_falta_diario_sha256_se_rechaza(tmp_path: Path) -> None:
    obj = _registro()
    del obj["diario_sha256"]
    with pytest.raises(kp.PreregError, match="debe tener las claves"):
        _leer(tmp_path, obj)


def test_falta_ejecuciones_lanzadas_se_rechaza(tmp_path: Path) -> None:
    obj = _registro()
    del obj["tareas"][0]["ejecuciones_lanzadas"]
    with pytest.raises(kp.PreregError, match="valores invalidos"):
        _leer(tmp_path, obj)


@pytest.mark.parametrize("valor", [3, 0, -1, "4", None, True, 4.0])
def test_ejecuciones_lanzadas_menor_que_4_o_mal_formado_se_rechaza(tmp_path: Path, valor: object) -> None:
    obj = _registro()
    obj["tareas"][0]["ejecuciones_lanzadas"] = valor
    with pytest.raises(kp.PreregError, match="valores invalidos"):
        _leer(tmp_path, obj)


@pytest.mark.parametrize("valor", ["zz", "C" * 64, "c" * 63, "c" * 65, 5, None, ""])
def test_diario_sha256_mal_formado_se_rechaza(tmp_path: Path, valor: object) -> None:
    obj = _registro()
    obj["diario_sha256"] = valor
    with pytest.raises(kp.PreregError, match="diario_sha256"):
        _leer(tmp_path, obj)


def test_una_clave_desconocida_sigue_sobrando(tmp_path: Path) -> None:
    obj = _registro()
    obj["diario"] = "c" * 64
    with pytest.raises(kp.PreregError, match="debe tener las claves"):
        _leer(tmp_path, obj)
