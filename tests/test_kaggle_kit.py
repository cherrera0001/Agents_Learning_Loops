"""Armado de una variante de kit que cambia solo lo declarado, y su comprobación miembro a miembro (#205).

Los zips se escriben aquí, con la forma del kit real (orden fijo, fecha fija, permisos 0o644) y con textos
inventados: ningún contenido de un kit ni de una tarea.
"""

from __future__ import annotations

import io
import zipfile

import pytest

from scripts import kaggle_kit as kk

FECHA = (2026, 10, 1, 0, 0, 0)
MIEMBROS = {
    "agent.yaml": b"name: agente\ntools:\n  - run_command\n  - agent_tool:\n      config_path: sub/x.yaml\n",
    "configs/sampling.yaml": b"temperature: 0.2\nthinking_config:\n  thinking_budget: 4096\n",
    "eval_config.yaml": b"evaluation:\n  timeout_seconds: 60\n  max_tool_calls: 60\n",
    "prompts/system.md": b"uno\ndos\ntres\n",
    "sub/x.yaml": b"name: ayudante\n",
}


def zip_de(miembros: dict[str, bytes], fecha: tuple[int, ...] = FECHA, permisos: int = 0o644 << 16) -> bytes:
    salida = io.BytesIO()
    with zipfile.ZipFile(salida, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for nombre, datos in miembros.items():
            info = zipfile.ZipInfo(nombre, date_time=fecha)  # type: ignore[arg-type]
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = permisos
            z.writestr(info, datos)
    return salida.getvalue()


BASE = zip_de(MIEMBROS)


def contenido(crudo: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(crudo)) as z:
        return {i.filename: z.read(i) for i in z.infolist()}


def zip_con(metodo: int, nombre: str = "a.md", datos: bytes = b"uno\n" * 40) -> bytes:
    salida = io.BytesIO()
    with zipfile.ZipFile(salida, "w") as z:
        info = zipfile.ZipInfo(nombre, date_time=FECHA)  # type: ignore[arg-type]
        info.compress_type = metodo
        z.writestr(info, datos)
    return salida.getvalue()


def test_reescribir_la_base_sin_cambios_la_devuelve_byte_a_byte() -> None:
    assert kk.reescribir(BASE) == BASE
    assert kk.registros_identicos(BASE, BASE) == list(MIEMBROS)


def test_los_miembros_que_no_cambian_conservan_sus_bytes_comprimidos() -> None:
    """Aunque la base se comprimiera con otro nivel que el del módulo, lo no declarado se copia tal cual."""
    salida = io.BytesIO()
    with zipfile.ZipFile(salida, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1) as z:
        for nombre, datos in MIEMBROS.items():
            z.writestr(zipfile.ZipInfo(nombre, date_time=FECHA), datos * 30, zipfile.ZIP_DEFLATED, 1)  # type: ignore[arg-type]
    base = salida.getvalue()
    variante = kk.armar_variante(base, {"prompts/system.md": b"otro\n" * 30}, ["sub/x.yaml"])
    intactos = [n for n in MIEMBROS if n not in ("prompts/system.md", "sub/x.yaml")]
    assert kk.registros_identicos(base, variante) == intactos
    for nombre in intactos:
        assert (
            variante.count(base[base.index(nombre.encode()) - 30 :][:60]) == 1
        )  # su cabecera local, tal cual
    assert kk.diferencias_con_lo_declarado(base, variante, ["prompts/system.md"], ["sub/x.yaml"]) == []
    with zipfile.ZipFile(io.BytesIO(variante)) as z:
        assert z.testzip() is None


def test_un_miembro_sin_comprimir_se_cambia_sin_comprimir() -> None:
    base = zip_con(zipfile.ZIP_STORED)
    variante = kk.armar_variante(base, {"a.md": b"dos\n" * 40})
    assert b"dos\ndos\n" in variante
    with zipfile.ZipFile(io.BytesIO(variante)) as z:
        assert z.read("a.md") == b"dos\n" * 40 and z.infolist()[0].compress_type == zipfile.ZIP_STORED
    comprimido = kk.armar_variante(zip_con(zipfile.ZIP_DEFLATED), {"a.md": b"dos\n" * 40})
    assert b"dos\ndos\n" not in comprimido and len(comprimido) < len(variante)


def test_armar_se_niega_ante_un_zip_que_no_sabe_copiar() -> None:
    # Bytes antes del primer registro: zipfile lo lee, pero reescrito no saldría igual
    with pytest.raises(kk.KitError, match="directorio central"):
        kk.armar_variante(b"basura" + BASE, {"prompts/system.md": b"otro\n"})
    con_prefijo = io.BytesIO(b"basura")
    with zipfile.ZipFile(
        con_prefijo, "a"
    ) as z:  # desplazamientos correctos, pero el primer registro no está en 0
        z.writestr(zipfile.ZipInfo("a.md", date_time=FECHA), b"uno\n")  # type: ignore[arg-type]
    assert contenido(con_prefijo.getvalue()) == {"a.md": b"uno\n"}
    with pytest.raises(kk.KitError, match="no van seguidos"):
        kk.armar_variante(con_prefijo.getvalue(), {"a.md": b"dos\n"})
    # Otro método de compresión en el miembro que cambia
    with pytest.raises(kk.KitError, match="método de compresión"):
        kk.armar_variante(zip_con(zipfile.ZIP_BZIP2), {"a.md": b"dos\n"})
    # Control: ese mismo zip se reescribe sin cambios, y el miembro se puede borrar si queda otro
    assert kk.reescribir(zip_con(zipfile.ZIP_BZIP2)) == zip_con(zipfile.ZIP_BZIP2)
    # Descriptor de datos (bandera 0x08): los tamaños no están en la cabecera local
    con_descriptor = bytearray(zip_con(zipfile.ZIP_DEFLATED))
    con_descriptor[con_descriptor.rindex(b"PK\x01\x02") + 8] |= 0x08
    with pytest.raises(kk.KitError, match="descriptor"):
        kk.reescribir(bytes(con_descriptor))
    with pytest.raises(kk.KitError, match="registro de fin"):
        kk.reescribir(BASE + b"x")
    with pytest.raises(kk.KitError, match="registro de fin"):
        kk.reescribir(b"PK")


def test_la_variante_cambia_solo_el_miembro_declarado() -> None:
    nuevo = b"temperature: 0.2\nthinking_config:\n  thinking_budget: 1536\n"
    variante = kk.armar_variante(BASE, {"configs/sampling.yaml": nuevo})
    assert contenido(variante) == {**MIEMBROS, "configs/sampling.yaml": nuevo}
    c = kk.comparar(BASE, variante)
    assert c["cambiados"] == ["configs/sampling.yaml"]
    assert c["identicos"] == [n for n in MIEMBROS if n != "configs/sampling.yaml"]
    assert c["borrados"] == [] and c["anadidos"] == [] and c["metadatos_distintos"] == []
    assert c["orden_conservado"] is True
    assert c["base_sha256"] == kk.sha256_de(BASE) and c["variante_sha256"] == kk.sha256_de(variante)
    assert c["sha256_por_miembro"]["configs/sampling.yaml"] == [
        kk.sha256_de(MIEMBROS["configs/sampling.yaml"]),
        kk.sha256_de(nuevo),
    ]
    assert kk.diferencias_con_lo_declarado(BASE, variante, ["configs/sampling.yaml"]) == []


def test_la_variante_conserva_orden_fecha_y_permisos() -> None:
    base = zip_de(dict(reversed(list(MIEMBROS.items()))), fecha=(2024, 2, 3, 4, 5, 6), permisos=0o755 << 16)
    variante = kk.armar_variante(base, {"prompts/system.md": b"otro\n"}, ["sub/x.yaml"])
    with zipfile.ZipFile(io.BytesIO(variante)) as z:
        infos = z.infolist()
    assert [i.filename for i in infos] == [n for n in reversed(list(MIEMBROS)) if n != "sub/x.yaml"]
    assert {i.date_time for i in infos} == {(2024, 2, 3, 4, 5, 6)}
    assert {i.external_attr for i in infos} == {0o755 << 16}
    assert {i.compress_type for i in infos} == {zipfile.ZIP_DEFLATED}
    assert kk.diferencias_con_lo_declarado(base, variante, ["prompts/system.md"], ["sub/x.yaml"]) == []


def test_borrar_miembros_no_toca_los_demas() -> None:
    agente = b"name: agente\ntools:\n  - run_command\n"
    variante = kk.armar_variante(BASE, {"agent.yaml": agente}, ["sub/x.yaml"])
    esperado = {n: d for n, d in MIEMBROS.items() if n != "sub/x.yaml"} | {"agent.yaml": agente}
    assert contenido(variante) == esperado
    c = kk.comparar(BASE, variante)
    assert c["borrados"] == ["sub/x.yaml"] and c["cambiados"] == ["agent.yaml"]
    assert c["sha256_por_miembro"]["sub/x.yaml"] == [kk.sha256_de(MIEMBROS["sub/x.yaml"]), None]


@pytest.mark.parametrize(
    ("cambios", "borrados", "texto"),
    [
        ({}, [], "ningún cambio"),
        ({"no/esta.md": b"x"}, [], "no tiene estos miembros"),
        ({}, ["no/esta.md"], "no tiene estos miembros"),
        ({"prompts/system.md": MIEMBROS["prompts/system.md"]}, [], "deja el contenido como estaba"),
        ({"sub/x.yaml": b"y"}, ["sub/x.yaml"], "a la vez"),
        ({}, ["sub/x.yaml", "sub/x.yaml"], "dos veces"),
        ({}, list(MIEMBROS), "sin miembros"),
    ],
)
def test_armar_se_niega_ante_un_cambio_que_no_es_el_declarado(
    cambios: dict[str, bytes], borrados: list[str], texto: str
) -> None:
    with pytest.raises(kk.KitError, match=texto):
        kk.armar_variante(BASE, cambios, borrados)


def test_leer_se_niega_ante_nombres_repetidos_carpetas_o_comentario() -> None:
    salida = io.BytesIO()
    with zipfile.ZipFile(salida, "w") as z, pytest.warns(UserWarning):
        z.writestr("a.md", b"1")
        z.writestr("a.md", b"2")
    with pytest.raises(kk.KitError, match="repetidos"):
        kk.leer_miembros(salida.getvalue())
    salida = io.BytesIO()
    with zipfile.ZipFile(salida, "w") as z:
        z.writestr("carpeta/", b"")
    with pytest.raises(kk.KitError, match="carpeta"):
        kk.leer_miembros(salida.getvalue())
    salida = io.BytesIO()
    with zipfile.ZipFile(salida, "w") as z:
        z.writestr("a.md", b"1")
        z.comment = b"nota"
    with pytest.raises(kk.KitError, match="comentario"):
        kk.leer_miembros(salida.getvalue())


def test_la_comprobacion_ve_un_cambio_no_declarado() -> None:
    variante = zip_de({**MIEMBROS, "prompts/system.md": b"otro\n", "eval_config.yaml": b"evaluation: {}\n"})
    problemas = kk.diferencias_con_lo_declarado(BASE, variante, ["prompts/system.md"])
    assert len(problemas) == 1 and "eval_config.yaml" in problemas[0]
    # Control: declarando los dos, cuadra
    assert kk.diferencias_con_lo_declarado(BASE, variante, ["prompts/system.md", "eval_config.yaml"]) == []


def test_la_comprobacion_ve_un_cambio_declarado_que_no_se_hizo() -> None:
    variante = zip_de({**MIEMBROS, "prompts/system.md": b"otro\n"})
    problemas = kk.diferencias_con_lo_declarado(BASE, variante, ["prompts/system.md", "agent.yaml"])
    assert len(problemas) == 1 and "declarados ['agent.yaml', 'prompts/system.md']" in problemas[0]


def test_la_comprobacion_ve_borrados_anadidos_orden_y_metadatos() -> None:
    sin_uno = zip_de({n: d for n, d in MIEMBROS.items() if n != "sub/x.yaml"})
    assert any("borrados ['sub/x.yaml']" in p for p in kk.diferencias_con_lo_declarado(BASE, sin_uno, []))
    assert kk.diferencias_con_lo_declarado(BASE, sin_uno, [], ["sub/x.yaml"]) == []
    con_otro = zip_de({**MIEMBROS, "nuevo.md": b"x"})
    assert kk.diferencias_con_lo_declarado(BASE, con_otro, []) == ["miembros añadidos: ['nuevo.md']"]
    al_reves = zip_de(dict(reversed(list(MIEMBROS.items()))))
    (problema,) = kk.diferencias_con_lo_declarado(BASE, al_reves, [])
    assert problema.startswith("el orden de los miembros cambió")
    otra_fecha = zip_de(MIEMBROS, fecha=(2026, 10, 2, 0, 0, 0))
    problemas = kk.diferencias_con_lo_declarado(BASE, otra_fecha, [])
    assert len(problemas) == len(MIEMBROS) and all("date_time" in p for p in problemas)
    otros_permisos = zip_de(MIEMBROS, permisos=0o600 << 16)
    problemas = kk.diferencias_con_lo_declarado(BASE, otros_permisos, [])
    assert len(problemas) == len(MIEMBROS) and all("external_attr" in p for p in problemas)


def test_comparar_lee_de_un_archivo_igual_que_de_los_bytes(tmp_path) -> None:  # type: ignore[no-untyped-def]
    ruta = tmp_path / "base.zip"
    ruta.write_bytes(BASE)
    variante = kk.armar_variante(ruta, {"prompts/system.md": b"otro\n"})
    assert kk.comparar(ruta, variante) == kk.comparar(BASE, variante)


TEXTO = "uno\ndos\ntres\n"


def test_reemplazar_linea_exige_el_texto_anterior() -> None:
    assert kk.reemplazar_linea(TEXTO, 2, "dos", "DOS") == "uno\nDOS\ntres\n"
    for numero, antes, despues in (
        (2, "tres", "x"),
        (0, "uno", "x"),
        (4, "", "x"),
        (2, "dos", "dos"),
        (2, "dos", "a\nb"),
    ):
        with pytest.raises(kk.KitError):
            kk.reemplazar_linea(TEXTO, numero, antes, despues)


def test_insertar_tras_la_linea_que_se_dice() -> None:
    assert kk.insertar_tras(TEXTO, 1, "uno", ["a", "b"]) == "uno\na\nb\ndos\ntres\n"
    assert kk.insertar_tras(TEXTO, 3, "tres", [""]) == "uno\ndos\ntres\n\n"
    for numero, ancla, nuevas in ((1, "dos", ["a"]), (1, "uno", []), (1, "uno", ["a\nb"])):
        with pytest.raises(kk.KitError):
            kk.insertar_tras(TEXTO, numero, ancla, nuevas)


def test_borrar_lineas_exige_cada_una() -> None:
    assert kk.borrar_lineas(TEXTO, 2, ["dos", "tres"]) == "uno\n"
    assert kk.borrar_lineas(TEXTO, 1, ["uno"]) == "dos\ntres\n"
    for desde, esperadas in ((2, ["dos", "cuatro"]), (3, ["tres", ""]), (1, [])):
        with pytest.raises(kk.KitError):
            kk.borrar_lineas(TEXTO, desde, esperadas)


@pytest.mark.parametrize("texto", ["uno\r\ndos\r\n", "uno\ndos"])
def test_la_edicion_se_niega_ante_otros_saltos_de_linea(texto: str) -> None:
    with pytest.raises(kk.KitError):
        kk.reemplazar_linea(texto, 1, "uno", "x")
