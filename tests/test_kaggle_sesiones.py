"""Tests de `scripts/kaggle_sesiones.py`. Sin red ni navegador: las respuestas de Kaggle son sintéticas."""

from __future__ import annotations

import json
from typing import Any

import pytest

from scripts import kaggle_sesiones as ks

# La forma de las respuestas de la página de Kaggle, leída el 2026-10-04.
SESIONES = {
    "totalCount": 1,
    "quotaLimits": {"gpuInteractive": 1, "gpuBatch": 2},
    "sessions": [
        {
            "kernelId": 1,
            "kernelRunId": 355193088,
            "type": "BATCH",
            "title": "prueba",
            "dateCreated": "2026-10-04T14:42:06.510Z",
            "accelerator": "NVIDIA_L4",
            "versionNumber": 2,
        }
    ],
}
CUOTA = {
    "quotaRefreshTime": "2026-10-10T00:00:00Z",
    "gpuQuota": {"timeReserved": "0s", "timeUsed": "6809.769267400s", "totalTimeAllowed": "108000s"},
}
VERSIONES = {
    "items": [
        {"version": {"versionNumber": 2}, "run": {"id": 355193088, "dateCreated": "2026-10-04T14:42:06Z"}},
        {
            "version": {"versionNumber": 1},
            "run": {
                "id": 355031739,
                "status": "ERROR",
                "dateCreated": "2026-10-04T00:56:59Z",
                "dateEvaluated": "2026-10-04T09:16:34Z",
                "runInfo": {"exitCode": 1, "runTimeSeconds": 22.7},
            },
        },
    ]
}


def test_resumir_sesiones_entrega_el_identificador_que_pide_la_cancelacion() -> None:
    resumen = ks.resumir_sesiones(SESIONES)
    assert resumen["total"] == 1
    assert resumen["sesiones"][0] == {
        "sesion": 355193088,
        "notebook": "prueba",
        "version": 2,
        "tipo": "BATCH",
        "acelerador": "NVIDIA_L4",
        "creada": "2026-10-04T14:42:06.510Z",
    }
    assert resumen["limites"]["gpuBatch"] == 2
    assert ks.resumir_sesiones({}) == {"total": 0, "sesiones": [], "limites": {}}


@pytest.mark.parametrize(
    ("texto", "valor"), [("6809.769267400s", 1.89), ("108000s", 30.0), ("0s", 0.0), ("", None), ("3 h", None)]
)
def test_horas_convierte_las_duraciones_de_kaggle(texto: str, valor: float | None) -> None:
    assert ks.horas(texto) == valor


def test_resumir_cuota() -> None:
    assert ks.resumir_cuota(CUOTA) == {
        "gpu_horas_usadas": 1.89,
        "gpu_horas_totales": 30.0,
        "gpu_horas_reservadas": 0.0,
        "reinicio": "2026-10-10T00:00:00Z",
    }


def test_resumir_versiones_distingue_la_que_espera_de_la_que_termino() -> None:
    en_cola, fallida = ks.resumir_versiones(VERSIONES)
    assert en_cola["sesion"] == 355193088
    assert en_cola["estado"] == "EN_COLA_O_CORRIENDO"
    assert fallida["estado"] == "ERROR"
    assert fallida["segundos_de_ejecucion"] == 22.7
    assert fallida["codigo_de_salida"] == 1


def _kaggle(respuestas: dict[str, tuple[int, str]], vistas: list[tuple[str, Any]]) -> Any:
    def pedir(url: str, token: str, cuerpo: dict[str, Any] | None = None) -> tuple[int, str]:
        assert token == "secreto"
        vistas.append((url, cuerpo))
        return next(v for k, v in respuestas.items() if k in url)

    return pedir


def test_cancelar_envia_el_identificador_y_confirma_el_estado(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    vistas: list[tuple[str, Any]] = []
    respuestas = {
        "CancelKernelSession": (200, "{}"),
        "kernels/status": (200, json.dumps({"status": "cancelAcknowledged"})),
    }
    monkeypatch.setenv("KAGGLE_API_TOKEN", "secreto")
    monkeypatch.setattr(ks, "_pedir", _kaggle(respuestas, vistas))
    monkeypatch.setattr(ks.time, "sleep", lambda s: None)
    codigo = ks.main(["cancelar", "--sesion", "355193088", "--usuario", "yo", "--notebook", "prueba"])
    assert codigo == ks.EXIT_OK
    assert vistas[0] == (f"{ks.RPC}/CancelKernelSession", {"kernelSessionId": 355193088})
    salida = json.loads(capsys.readouterr().out)
    assert salida == {"sesion_cancelada": 355193088, "estado_del_notebook": "cancelAcknowledged"}
    assert "secreto" not in json.dumps(salida)


def test_un_identificador_ajeno_sale_con_3(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("KAGGLE_API_TOKEN", "secreto")
    monkeypatch.setattr(ks, "_pedir", _kaggle({"CancelKernelSession": (403, '{"error": {}}')}, []))
    assert (
        ks.main(["cancelar", "--sesion", "1", "--usuario", "yo", "--notebook", "prueba"]) == ks.EXIT_RECHAZADA
    )
    assert "negó el permiso" in capsys.readouterr().err


def test_un_error_que_kaggle_devuelve_con_200_tambien_es_un_rechazo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KAGGLE_API_TOKEN", "secreto")
    monkeypatch.setattr(
        ks, "_pedir", _kaggle({"CancelKernelSession": (200, '{"errorMessage": "ya terminó"}')}, [])
    )
    assert (
        ks.main(["cancelar", "--sesion", "5", "--usuario", "yo", "--notebook", "prueba"]) == ks.EXIT_RECHAZADA
    )


@pytest.mark.parametrize("sesion", ["0", "-3"])
def test_un_identificador_no_positivo_no_llega_a_kaggle(monkeypatch: pytest.MonkeyPatch, sesion: str) -> None:
    monkeypatch.setenv("KAGGLE_API_TOKEN", "secreto")

    def nunca(*a: Any, **k: Any) -> tuple[int, str]:
        raise AssertionError("no debía llamarse")

    monkeypatch.setattr(ks, "_pedir", nunca)
    assert (
        ks.main(["cancelar", "--sesion", sesion, "--usuario", "yo", "--notebook", "prueba"])
        == ks.EXIT_ENTRADA
    )


def test_sin_token_no_se_cancela(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KAGGLE_API_TOKEN", raising=False)
    assert (
        ks.main(["cancelar", "--sesion", "5", "--usuario", "yo", "--notebook", "prueba"]) == ks.EXIT_ENTRADA
    )


def test_listar_sin_edge_abierto_sale_con_2(capsys: pytest.CaptureFixture[str]) -> None:
    codigo = ks.main(["listar", "--usuario", "yo", "--notebook", "prueba", "--puerto", "1"])
    assert codigo == ks.EXIT_ENTRADA
    assert capsys.readouterr().err.startswith("ENTRADA INVÁLIDA")


def test_una_lectura_rechazada_no_se_lee_como_sin_sesiones() -> None:
    with pytest.raises(ks.SesionesError, match="401"):
        ks.rechazar_errores({"sesiones": {"__error": 401}, "cuota": {}, "notebook": {}})
    ks.rechazar_errores({"sesiones": {}, "cuota": {"x": 1}, "notebook": {"kernel": {"id": 1}}})
