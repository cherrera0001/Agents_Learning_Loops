"""Tests de `scripts/kaggle_rescate.py`. No usan la red: la descarga se sustituye por datos sintéticos."""

from __future__ import annotations

import csv
import io
import json
import urllib.request
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


def test_un_nombre_de_salida_que_no_cabe_en_la_ruta_se_acorta_y_conserva_su_extension(tmp_path: Path) -> None:
    corto = kr.nombre_que_cabe(tmp_path, "s.json")
    assert corto == "salida__s.json"
    largo = "tarea_" + "x" * 300 + "-run_id_Run_1.atif.json"
    en_disco = kr.nombre_que_cabe(tmp_path, largo)
    assert len(str(tmp_path.resolve() / en_disco)) <= kr.TOPE_RUTA
    assert en_disco.startswith("salida__tarea_") and en_disco.endswith(".atif.json")
    otro = kr.nombre_que_cabe(tmp_path, "tarea_" + "x" * 300 + "-run_id_Run_2.atif.json")
    assert otro != en_disco, "dos nombres largos distintos no pueden caer en el mismo archivo"


def test_una_salida_de_nombre_largo_se_guarda_y_el_resumen_muestra_el_nombre_de_kaggle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    largo = "tarea_" + "x" * 300 + ".result.json"
    respuestas = _respuestas(_tabla(FILAS))
    respuestas["kernels/output"] = json.dumps(
        {"log": "[]", "files": [{"fileName": largo, "url": "http://x/s"}]}
    ).encode()
    monkeypatch.setattr(kr, "pedir", lambda ruta, token: next(v for k, v in respuestas.items() if k in ruta))
    assert kr.bajar(tmp_path, "secreto", None) == []
    carpeta = tmp_path / "notebooks" / "mi-notebook"
    guardados = list(carpeta.glob("salida__*"))
    assert len(guardados) == 1 and guardados[0].read_bytes() == b'{"sonda": 1}'
    resumen = kr.resumir(tmp_path, None)
    assert resumen["notebooks"][0]["archivos_de_salida"] == [largo]
    assert resumen["descarga_incompleta"] == []


def test_un_notebook_que_falla_no_impide_bajar_los_siguientes_y_sale_con_4(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    respuestas = _respuestas(_tabla(FILAS))
    respuestas["kernels/list"] = json.dumps([{"ref": "yo/roto"}, {"ref": "yo/mi-notebook"}]).encode()
    salida = {
        "log": "[]",
        "files": [{"fileName": "a.json", "url": "http://x/a"}, {"fileName": "s.json", "url": "http://x/s"}],
    }
    respuestas["kernels/output"] = json.dumps(salida).encode()

    def pedir_falso(ruta: str, token: str) -> bytes:
        if "kernelSlug=roto" in ruta and "kernels/pull" in ruta:
            raise kr.RescateError("Kaggle respondió 404 a kernels/pull")
        if ruta == "http://x/a":
            raise OSError("ruta secreta C:/Users/alguien")
        return next(v for k, v in respuestas.items() if k in ruta)

    monkeypatch.setattr(kr, "pedir", pedir_falso)
    monkeypatch.setenv("KAGGLE_API_TOKEN", "secreto")
    assert kr.main(["--destino", str(tmp_path / "rescate")]) == kr.EXIT_PARCIAL
    resumen = json.loads(capsys.readouterr().out)
    assert resumen["descarga_incompleta"] == [
        {"notebook": "roto", "archivo": "", "causa": "Kaggle respondió 404 a kernels/pull"},
        {"notebook": "mi-notebook", "archivo": "a.json", "causa": "OSError: no se pudo guardar"},
    ]
    assert [n["notebook"] for n in resumen["notebooks"]] == ["mi-notebook"]
    assert resumen["notebooks"][0]["archivos_de_salida"] == ["s.json"]
    assert kr.main(["--destino", resumen["directorio"], "--sin-red"]) == kr.EXIT_PARCIAL


def test_el_resumen_dice_de_donde_sale_el_tamano_de_la_tabla(tmp_path: Path) -> None:
    (tmp_path / "envios.json").write_text("[]", encoding="utf-8")
    (tmp_path / "tabla_publica.zip").write_bytes(_tabla(FILAS))
    assert "menor de los compatibles" in kr.resumir(tmp_path, None)["tamano_de_tabla_usado"]["origen"]
    assert kr.resumir(tmp_path, 58)["tamano_de_tabla_usado"] == {
        "n": 58,
        "origen": "indicado con --tareas-tabla",
    }


NOMBRE_SALIDA_REAL = (
    "printer_queue_minimize_average_wait_time-run_id_Run_1_anthropic_claude-sonnet-5-5default.atif.json"
)


def _ruta_de_longitud(tmp_path: Path, longitud: int) -> Path:
    carpeta = tmp_path / ("x" * (longitud - len(str(tmp_path.resolve())) - 1))
    assert len(str(carpeta.resolve())) == longitud
    return carpeta


@pytest.mark.parametrize("longitud", [180, 210])
def test_nombre_real_cabe_incluso_sin_espacio_para_la_base(tmp_path: Path, longitud: int) -> None:
    carpeta = _ruta_de_longitud(tmp_path, longitud)
    nombre = kr.nombre_que_cabe(carpeta, NOMBRE_SALIDA_REAL)
    assert len(str(carpeta.resolve() / nombre)) <= kr.TOPE_RUTA
    assert nombre.endswith(".atif.json")
    assert nombre != kr.nombre_que_cabe(carpeta, NOMBRE_SALIDA_REAL.replace("Run_1", "Run_2"))


def test_nombre_real_imposible_se_rechaza_antes_de_guardar(tmp_path: Path) -> None:
    carpeta = _ruta_de_longitud(tmp_path, 211)
    with pytest.raises(kr.RescateError, match="TOPE_RUTA"):
        kr.nombre_que_cabe(carpeta, NOMBRE_SALIDA_REAL)


@pytest.mark.parametrize("longitud", [210, 211])
def test_bajar_nombre_real_en_ruta_larga_continua_con_el_segundo_notebook(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, longitud: int
) -> None:
    # La carpeta del primer notebook deja justo cero caracteres de base, o ni eso.
    destino = _ruta_de_longitud(tmp_path, longitud - len("/notebooks/primero"))
    destino.mkdir()
    respuestas = _respuestas(_tabla(FILAS))
    respuestas["kernels/list"] = json.dumps([{"ref": "yo/primero"}, {"ref": "yo/segundo"}]).encode()

    def pedir_falso(ruta: str, token: str) -> bytes:
        if "kernels/output" in ruta and "kernelSlug=primero" in ruta:
            return json.dumps(
                {"log": "[]", "files": [{"fileName": NOMBRE_SALIDA_REAL, "url": "http://x/s"}]}
            ).encode()
        return next(v for k, v in respuestas.items() if k in ruta)

    monkeypatch.setattr(kr, "pedir", pedir_falso)
    faltantes = kr.bajar(destino, "secreto", None)
    primero = destino / "notebooks" / "primero"
    assert len(str(primero.resolve())) == longitud >= 180
    assert (destino / "notebooks" / "segundo" / "salida__s.json").read_bytes() == b'{"sonda": 1}'
    assert json.loads((destino / "faltantes.json").read_text()) == faltantes
    if longitud == 210:
        assert faltantes == []
        archivo = next(primero.glob("salida__*"))
        assert len(str(archivo.resolve())) <= kr.TOPE_RUTA
        assert archivo.read_bytes() == b'{"sonda": 1}'
    else:
        assert len(faltantes) == 1
        assert faltantes[0]["notebook"] == "primero"
        assert faltantes[0]["archivo"] == NOMBRE_SALIDA_REAL
        assert "TOPE_RUTA" in faltantes[0]["causa"]
        assert not list(primero.glob("salida__*"))


def test_una_redireccion_fuera_de_kaggle_no_lleva_el_token() -> None:
    manejador = kr.RedireccionSinToken()
    original = urllib.request.Request(f"{kr.API}/x", headers=kr.cabeceras_para(f"{kr.API}/x", "secreto"))
    fuera = manejador.redirect_request(original, None, 302, "Found", {}, "https://storage.example.com/firma")
    assert "secreto" not in str(fuera.header_items())
    dentro = manejador.redirect_request(original, None, 302, "Found", {}, "https://www.kaggle.com/otra")
    assert ("Authorization", "Bearer secreto") in dentro.header_items()
    with pytest.raises(kr.RescateError, match="no es https"):
        manejador.redirect_request(original, None, 302, "Found", {}, "http://www.kaggle.com/otra")


def test_una_respuesta_ilegible_a_media_bajada_queda_en_faltantes_y_sale_con_4(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    respuestas = _respuestas(_tabla(FILAS))
    respuestas["kernels/list"] = json.dumps([{"ref": "yo/roto"}, {"ref": "yo/mi-notebook"}]).encode()

    def pedir_falso(ruta: str, token: str) -> bytes:
        if "kernelSlug=roto" in ruta and "kernels/pull" in ruta:
            return b"<html>no es json</html>"
        return next(v for k, v in respuestas.items() if k in ruta)

    monkeypatch.setattr(kr, "pedir", pedir_falso)
    monkeypatch.setenv("KAGGLE_API_TOKEN", "secreto")
    assert kr.main(["--destino", str(tmp_path / "rescate")]) == kr.EXIT_PARCIAL
    resumen = json.loads(capsys.readouterr().out)
    assert [f["notebook"] for f in resumen["descarga_incompleta"]] == ["roto"]
    assert "ilegible" in resumen["descarga_incompleta"][0]["causa"]
    assert [n["notebook"] for n in resumen["notebooks"]] == ["mi-notebook"]


# ---------------------------------------------------------------------------
# Revisión de los miembros de los zips de salida (datos sintéticos)
# ---------------------------------------------------------------------------


def _zip(miembros: dict[str, bytes]) -> bytes:
    paquete = io.BytesIO()
    with zipfile.ZipFile(paquete, "w") as z:
        for nombre, datos in miembros.items():
            z.writestr(nombre, datos)
    return paquete.getvalue()


def _bajar_con_zip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, contenido: bytes, nombres: tuple[str, ...] = ("z.zip",)
) -> Path:
    respuestas = _respuestas(_tabla(FILAS))
    archivos = [{"fileName": n, "url": f"http://x/{n}"} for n in nombres]
    respuestas["kernels/output"] = json.dumps({"log": "[]", "files": archivos}).encode()
    for n in nombres:
        respuestas[f"http://x/{n}"] = contenido
    monkeypatch.setattr(kr, "pedir", lambda ruta, token: next(v for k, v in respuestas.items() if k in ruta))
    monkeypatch.setenv("KAGGLE_API_TOKEN", "secreto")
    return tmp_path / "rescate"


def test_un_log_exigido_de_0_bytes_es_un_faltante_y_sale_con_4(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    contenido = _zip({"logs/a.log": b"", "traces/a.json": b"{}", "task_results.jsonl": b"{}\n"})
    destino = _bajar_con_zip(tmp_path, monkeypatch, contenido)
    assert kr.main(["--destino", str(destino)]) == kr.EXIT_PARCIAL
    resumen = json.loads(capsys.readouterr().out)
    assert resumen["descarga_incompleta"] == [
        {
            "notebook": "mi-notebook",
            "archivo": "salida__z.zip",
            "miembro": "logs/a.log",
            "causa": "miembro exigido de 0 bytes",
        }
    ]
    escrito = json.loads(next(destino.rglob("faltantes.json")).read_text(encoding="utf-8"))
    assert escrito == resumen["descarga_incompleta"]
    assert resumen["notebooks"][0]["revision_de_zips"]["miembros_revisados"] == 3
    assert resumen["notebooks"][0]["revision_de_zips"]["miembros_de_0_bytes"] == 1


def test_el_mismo_zip_con_bytes_sale_con_0_y_faltantes_vacio(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    contenido = _zip({"logs/a.log": b"linea\n", "traces/a.json": b"{}", "task_results.jsonl": b"{}\n"})
    destino = _bajar_con_zip(tmp_path, monkeypatch, contenido)
    assert kr.main(["--destino", str(destino)]) == kr.EXIT_OK
    resumen = json.loads(capsys.readouterr().out)
    assert resumen["descarga_incompleta"] == []
    assert next(destino.rglob("faltantes.json")).read_text(encoding="utf-8") == "[]"
    assert resumen["notebooks"][0]["revision_de_zips"]["exigidos_de_0_bytes"] == 0


def test_task_results_vacio_en_una_subcarpeta_es_un_faltante(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    destino = _bajar_con_zip(tmp_path, monkeypatch, _zip({"corrida/task_results.jsonl": b""}))
    assert kr.main(["--destino", str(destino)]) == kr.EXIT_PARCIAL
    assert (
        json.loads(capsys.readouterr().out)["descarga_incompleta"][0]["miembro"]
        == "corrida/task_results.jsonl"
    )


def test_un_zip_corrupto_es_un_faltante_y_la_bajada_sigue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    destino = _bajar_con_zip(tmp_path, monkeypatch, b"esto no es un zip", ("a.zip", "b.json"))
    assert kr.main(["--destino", str(destino)]) == kr.EXIT_PARCIAL
    resumen = json.loads(capsys.readouterr().out)
    assert resumen["descarga_incompleta"] == [
        {"notebook": "mi-notebook", "archivo": "salida__a.zip", "miembro": "", "causa": "zip ilegible"}
    ]
    assert resumen["notebooks"][0]["archivos_de_salida"] == ["a.zip", "b.json"]
    assert resumen["notebooks"][0]["revision_de_zips"]["zips_ilegibles"] == 1


def test_patches_y_test_outputs_vacios_se_cuentan_y_no_son_faltantes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    contenido = _zip(
        {"logs/a.log": b"x", "patches/a.diff": b"", "test_outputs/a.txt": b"", "patches/b.diff": b""}
    )
    destino = _bajar_con_zip(tmp_path, monkeypatch, contenido)
    assert kr.main(["--destino", str(destino)]) == kr.EXIT_OK
    resumen = json.loads(capsys.readouterr().out)
    assert resumen["descarga_incompleta"] == []
    revision = resumen["notebooks"][0]["revision_de_zips"]
    assert revision["patches_de_0_bytes"] == 2 and revision["test_outputs_de_0_bytes"] == 1
    assert revision["miembros_de_0_bytes"] == 3 and revision["exigidos_de_0_bytes"] == 0


def test_un_miembro_de_nombre_peligroso_no_escribe_nada_fuera(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    contenido = _zip({"../../escapa/logs/x.log": b"", "/abs/logs/y.log": b"", r"..\z\logs\w.log": b""})
    destino = _bajar_con_zip(tmp_path, monkeypatch, contenido)
    antes = set(tmp_path.parent.rglob("*")) - set(tmp_path.rglob("*"))
    assert kr.main(["--destino", str(destino)]) == kr.EXIT_PARCIAL
    resumen = json.loads(capsys.readouterr().out)
    assert len(resumen["descarga_incompleta"]) == 3
    assert not (tmp_path / "escapa").exists() and not (tmp_path.parent / "escapa").exists()
    assert not any("escapa" in str(p) for p in tmp_path.rglob("*"))
    assert set(tmp_path.parent.rglob("*")) - set(tmp_path.rglob("*")) == antes
    carpeta = next(destino.glob("*")) / "notebooks" / "mi-notebook"
    assert sorted(p.name for p in carpeta.iterdir()) == sorted(
        [
            "estado.json",
            "metadatos.json",
            "notebook.ipynb",
            "log.txt",
            "log_crudo.json",
            "salida__z.zip",
            "salidas.json",
        ]
    )


def test_sin_red_repite_la_revision_sin_reescribir_faltantes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    contenido = _zip({"logs/a.log": b"", "patches/a.diff": b""})
    destino = _bajar_con_zip(tmp_path, monkeypatch, contenido)
    assert kr.main(["--destino", str(destino)]) == kr.EXIT_PARCIAL
    bajada = json.loads(capsys.readouterr().out)
    carpeta = Path(bajada["directorio"])
    # Una carpeta vieja: su faltantes.json no sabía de los miembros vacíos.
    (carpeta / "faltantes.json").write_text("[]", encoding="utf-8")
    assert kr.main(["--destino", str(carpeta), "--sin-red"]) == kr.EXIT_PARCIAL
    resumen = json.loads(capsys.readouterr().out)
    assert resumen["descarga_incompleta"] == bajada["descarga_incompleta"]
    assert resumen["notebooks"][0]["revision_de_zips"] == bajada["notebooks"][0]["revision_de_zips"]
    assert (carpeta / "faltantes.json").read_text(encoding="utf-8") == "[]"


def test_sin_red_no_repite_lo_que_faltantes_ya_trae(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    destino = _bajar_con_zip(tmp_path, monkeypatch, _zip({"logs/a.log": b""}))
    assert kr.main(["--destino", str(destino)]) == kr.EXIT_PARCIAL
    carpeta = Path(json.loads(capsys.readouterr().out)["directorio"])
    assert kr.main(["--destino", str(carpeta), "--sin-red"]) == kr.EXIT_PARCIAL
    assert len(json.loads(capsys.readouterr().out)["descarga_incompleta"]) == 1


def _revisar(tmp_path: Path, miembros: dict[str, bytes]) -> tuple[list[str], dict[str, int]]:
    ruta = tmp_path / "salida__z.zip"
    ruta.write_bytes(_zip(miembros))
    conteo = kr._conteo_vacio()
    faltantes = kr.revisar_zip(ruta, "nb", conteo)
    return [f["miembro"] for f in faltantes], conteo


@pytest.mark.parametrize(
    "miembro",
    [
        "traces/t.json",
        "logs/sub/x.log",
        "run/x/logs/d.log",
        "run/traces/sub/t.json",
        "sub/task_results.jsonl",
    ],
)
def test_un_exigido_vacio_a_cualquier_nivel_es_un_faltante(tmp_path: Path, miembro: str) -> None:
    faltantes, conteo = _revisar(tmp_path, {miembro: b"", "logs/lleno.log": b"x"})
    assert faltantes == [miembro]
    assert conteo["exigidos_de_0_bytes"] == 1
    assert conteo["miembros_de_0_bytes"] == 1
    assert conteo["miembros_revisados"] == 2


@pytest.mark.parametrize(
    "miembro",
    ["mylogs/a.log", "catalogs/b.log", "logs_old/c.log", "x/logs", "task_results.jsonl.bak", "otros/d.txt"],
)
def test_un_nombre_parecido_a_uno_exigido_no_es_un_faltante(tmp_path: Path, miembro: str) -> None:
    faltantes, conteo = _revisar(tmp_path, {miembro: b""})
    assert faltantes == []
    assert conteo["exigidos_de_0_bytes"] == 0
    assert conteo["miembros_de_0_bytes"] == 1


def test_un_miembro_que_es_una_carpeta_no_se_revisa(tmp_path: Path) -> None:
    faltantes, conteo = _revisar(tmp_path, {"logs/": b"", "traces/sub/": b"", "logs/a.log": b"x"})
    assert faltantes == []
    assert conteo["miembros_revisados"] == 1
    assert conteo["miembros_de_0_bytes"] == 0


def test_decide_la_carpeta_conocida_mas_externa(tmp_path: Path) -> None:
    miembros = {"patches/logs/h.diff": b"", "test_outputs/traces/i.txt": b"", "logs/patches/j.log": b""}
    faltantes, conteo = _revisar(tmp_path, miembros)
    assert faltantes == ["logs/patches/j.log"]
    assert conteo["exigidos_de_0_bytes"] == 1
    assert conteo["patches_de_0_bytes"] == 1
    assert conteo["test_outputs_de_0_bytes"] == 1


def test_varios_exigidos_vacios_se_cuentan_uno_por_uno(tmp_path: Path) -> None:
    faltantes, conteo = _revisar(tmp_path, {"logs/a.log": b"", "logs/b.log": b"", "traces/c.json": b""})
    assert len(faltantes) == 3
    assert conteo["exigidos_de_0_bytes"] == 3


def test_un_zip_con_la_extension_en_mayusculas_tambien_se_revisa(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    destino = _bajar_con_zip(tmp_path, monkeypatch, _zip({"logs/a.log": b""}), nombres=("Z.ZIP",))
    assert kr.main(["--destino", str(destino)]) == kr.EXIT_PARCIAL
    carpeta = Path(json.loads(capsys.readouterr().out)["directorio"])
    faltantes = json.loads((carpeta / "faltantes.json").read_text(encoding="utf-8"))
    assert [f["miembro"] for f in faltantes] == ["logs/a.log"]
