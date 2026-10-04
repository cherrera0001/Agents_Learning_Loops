"""Tests de `scripts/kaggle_rescate.py`. No usan la red: la descarga se sustituye por datos sintéticos."""

from __future__ import annotations

import csv
import io
import json
import zipfile
from pathlib import Path

import pytest

from scripts import kaggle_rescate as kr


def _tabla(filas: list[tuple[str, float, int, str]]) -> bytes:
    texto = io.StringIO()
    escritor = csv.writer(texto)
    escritor.writerow(
        [
            "Rank",
            "TeamId",
            "TeamName",
            "LastSubmissionDate",
            "Score",
            "SubmissionCount",
            "TeamMemberUserNames",
        ]
    )
    for puesto, (equipo, nota, envios, usuarios) in enumerate(filas, 1):
        escritor.writerow([puesto, 1000 + puesto, equipo, "2026-10-04 00:00:00", nota, envios, usuarios])
    paquete = io.BytesIO()
    with zipfile.ZipFile(paquete, "w") as z:
        z.writestr("tabla.csv", "﻿" + texto.getvalue())
    return paquete.getvalue()


# Notas de una tabla de 58 tareas: 14, 10, 9, 7, 6, 4, 4, 1 y 0 resueltas.
FILAS = [
    ("a", 0.24, 9, "u1"),
    ("b", 0.17, 4, "u2"),
    ("c", 0.15, 3, "u3"),
    ("d", 0.12, 2, "u4"),
    ("e", 0.10, 2, "u5"),
    ("f", 0.06, 1, "yo"),
    ("g", 0.06, 1, "u7,u8"),
    ("h", 0.01, 1, "u9"),
    ("i", 0.00, 1, "u10"),
]


@pytest.mark.parametrize(
    ("k", "nota"), [(1, 0.01), (2, 0.03), (4, 0.06), (7, 0.12), (8, 0.13), (10, 0.17), (14, 0.24)]
)
def test_la_nota_de_la_tabla_se_trunca_y_no_se_redondea(k: int, nota: float) -> None:
    assert kr.nota_truncada(k, 58) == nota
    assert kr.tareas_de(nota, 58) == k


def test_una_nota_que_no_es_k_sobre_n_no_tiene_tareas() -> None:
    assert kr.tareas_de(0.02, 58) is None


def test_el_tamano_de_la_tabla_se_infiere_de_las_notas_observadas() -> None:
    notas = [0.0, 0.01, 0.03, 0.05, 0.06, 0.08, 0.10, 0.12, 0.13, 0.15, 0.17, 0.24]
    candidatos = kr.tamanos_compatibles(notas)
    assert candidatos[0] == 58
    assert 60 not in candidatos
    assert kr.tamanos_compatibles([0.5], minimo=2, maximo=4) == [2, 4]


def test_mejor_de_un_envio_es_la_media_y_crece_con_los_envios() -> None:
    assert kr.mejor_de(1, 58, 0.1) == pytest.approx(5.8, abs=1e-6)
    assert kr.mejor_de(2, 58, 0.1) > kr.mejor_de(1, 58, 0.1)
    assert kr.mejor_de(7, 58, 0.1) < 58


def test_resumir_tabla_cuenta_en_tareas_y_no_guarda_nombres_ajenos() -> None:
    filas = kr.leer_tabla(_tabla(FILAS))
    resumen = kr.resumir_tabla(filas, 58, "yo")
    assert resumen["equipos"] == 9
    assert resumen["equipos_por_tareas"]["4"] == 2
    assert resumen["equipos_por_tareas"]["14"] == 1
    assert resumen["mediana_tareas"] == 6
    assert resumen["media_por_numero_de_envios"]["1"] == {"equipos": 4, "media_tareas": 2.25}
    assert resumen["equipo_propio"] == {"puesto": 6, "tareas": 4, "envios": 1, "equipos_con_mas_tareas": 5}
    texto = json.dumps(resumen)
    assert "u7" not in texto
    assert '"a"' not in texto


def test_resumir_tabla_no_confunde_un_usuario_con_otro_que_lo_contiene() -> None:
    filas = kr.leer_tabla(_tabla([("x", 0.10, 1, "yoyo"), ("y", 0.06, 1, "otro")]))
    assert "equipo_propio" not in kr.resumir_tabla(filas, 58, "yo")


def test_resumir_tabla_rechaza_un_tamano_que_no_explica_las_notas() -> None:
    filas = kr.leer_tabla(_tabla(FILAS))
    with pytest.raises(kr.RescateError):
        kr.resumir_tabla(filas, 60)


def test_el_log_de_kaggle_se_convierte_en_texto() -> None:
    crudo = json.dumps(
        [{"stream_name": "stdout", "time": 1.0, "data": "uno\n"}, {"time": 2.0, "data": "dos\n"}]
    )
    assert kr.texto_del_log(crudo) == "uno\ndos\n"
    assert kr.texto_del_log("texto plano") == "texto plano"
    assert kr.texto_del_log('{"no": "lista"}') == '{"no": "lista"}'


def _respuestas(tabla: bytes) -> dict[str, bytes]:
    envio = {"ref": 7, "date": "2026-10-03T23:46:26Z", "status": "complete", "publicScore": "0.06"}
    envio.update({"submittedByRef": "yo", "totalBytes": 86883})
    salida = {
        "log": json.dumps([{"data": "linea 1\nlinea 2\n"}]),
        "files": [{"fileName": "s.json", "url": "http://x/s"}],
    }
    return {
        "competitions/submissions/list": json.dumps([envio]).encode(),
        "leaderboard/download": tabla,
        "kernels/list": json.dumps([{"ref": "yo/mi-notebook"}]).encode(),
        "kernels/status": json.dumps({"status": "complete"}).encode(),
        "kernels/pull": json.dumps(
            {
                "metadata": {"currentVersionNumber": 3, "machineShape": "NvidiaL4", "isPrivate": True},
                "blob": {"source": "{}"},
            }
        ).encode(),
        "kernels/output": json.dumps(salida).encode(),
        "http://x/s": b'{"sonda": 1}',
    }


def test_bajar_y_resumir_de_punta_a_punta_sin_red(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    respuestas = _respuestas(_tabla(FILAS))
    pedidas: list[str] = []

    def pedir_falso(ruta: str, token: str) -> bytes:
        assert token == "secreto"
        pedidas.append(ruta)
        return next(v for k, v in respuestas.items() if k in ruta)

    monkeypatch.setattr(kr, "pedir", pedir_falso)
    kr.bajar(tmp_path, "secreto", None)
    carpeta = tmp_path / "notebooks" / "mi-notebook"
    assert (carpeta / "log.txt").read_text(encoding="utf-8") == "linea 1\nlinea 2\n"
    assert (carpeta / "salida__s.json").read_bytes() == b'{"sonda": 1}'
    assert "secreto" not in "".join(
        p.read_text(encoding="utf-8", errors="ignore") for p in tmp_path.rglob("*.json")
    )
    resumen = kr.resumir(tmp_path, None)
    assert resumen["tamanos_de_tabla_compatibles"][0] == 58
    assert resumen["envios_propios"] == [
        {
            "ref": 7,
            "fecha": "2026-10-03T23:46:26Z",
            "estado": "complete",
            "nota_publica": "0.06",
            "tareas": 4,
            "bytes_guardados_por_kaggle": 86883,
        }
    ]
    assert resumen["tabla"]["equipo_propio"]["tareas"] == 4
    assert resumen["notebooks"] == [
        {
            "notebook": "mi-notebook",
            "estado": "complete",
            "version": 3,
            "maquina": "NvidiaL4",
            "privado": True,
            "lineas_de_log": 2,
            "archivos_de_salida": ["s.json"],
        }
    ]


def test_sin_token_sale_con_2_y_no_crea_nada(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KAGGLE_API_TOKEN", raising=False)
    assert kr.main(["--destino", str(tmp_path / "rescate")]) == kr.EXIT_ENTRADA
    assert not (tmp_path / "rescate").exists()


def test_si_kaggle_no_responde_sale_con_3(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KAGGLE_API_TOKEN", "secreto")

    def falla(ruta: str, token: str) -> bytes:
        raise kr.RescateError("Kaggle respondió 500")

    monkeypatch.setattr(kr, "pedir", falla)
    assert kr.main(["--destino", str(tmp_path / "rescate")]) == kr.EXIT_RED


def test_sin_red_resume_un_directorio_ya_bajado(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "envios.json").write_text("[]", encoding="utf-8")
    (tmp_path / "tabla_publica.zip").write_bytes(_tabla(FILAS))
    assert kr.main(["--destino", str(tmp_path), "--sin-red"]) == kr.EXIT_OK
    assert json.loads(capsys.readouterr().out)["tabla"]["tareas_de_la_tabla"] == 58
    assert kr.main(["--destino", str(tmp_path / "vacio"), "--sin-red"]) == kr.EXIT_ENTRADA


def test_el_token_solo_viaja_por_https_a_kaggle() -> None:
    assert kr.cabeceras_para(f"{kr.API}/kernels/list", "secreto") == {"Authorization": "Bearer secreto"}
    assert kr.cabeceras_para("https://www.kaggle.com/x", "secreto") == {"Authorization": "Bearer secreto"}
    assert kr.cabeceras_para("https://storage.example.invalid/archivo?firma=1", "secreto") == {}
    with pytest.raises(kr.RescateError, match="https"):
        kr.cabeceras_para("http://www.kaggle.com/x", "secreto")


def test_un_destino_anidado_dentro_del_repositorio_se_rechaza(tmp_path: Path) -> None:
    import subprocess

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    with pytest.raises(kr.RescateError, match="dentro de un repositorio"):
        kr.comprobar_destino_fuera_de_git(tmp_path / "nuevo" / "sub")
