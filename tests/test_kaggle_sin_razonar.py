"""Regla de validez de una corrida con un kit sin razonamiento (`kaggle_registro --sin-razonar`).

Paso 0 del concilio 45: con el kit `A0` toda petición debe pedir «no razonar». Una sola que pida razonar, o
que no traiga el dato, invalida la corrida. Registros escritos aquí, sin identificadores de tareas.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts import kaggle_registro as kr
from scripts import kaggle_rescate

HORA = "2026-10-12T00:00:00.000+00:00"
ENGANCHES = {"peticiones": "instalado", "logs por tarea (rich)": "modo archivo", "latido": "cada 30.0 s"}


def _e(tipo: str, tarea: str | None = "t_1", **campos: Any) -> dict[str, Any]:
    return {"evento": tipo, "tarea": tarea, "hora_utc": HORA, **campos}


def registro(piden: list[Any], cerrado: bool = True) -> str:
    """Un registro de una tarea con una petición por elemento de ``piden`` (True, False o None: sin dato)."""
    eventos = [{"evento": "registro_instalado", "tarea": None, "enganches": ENGANCHES}, _e("tarea_inicio")]
    for n, pide in enumerate(piden, start=1):
        dato = {} if pide is None else {"pide_razonar": pide}
        eventos += [
            _e("peticion_inicio", peticion=n, caracteres_entrada=100, n_mensajes=2, **dato),
            _e("cb_antes", llamada=f"id{n}", peticion_en_curso=n),
            _e("peticion_fin", peticion=n, motivo="stop", segundos=1.0, completion_tokens=40),
            _e("cb_exito", llamada=f"id{n}", peticion_en_curso=None),
        ]
    eventos += [
        _e("agente_fin", error=None, entrego=True, parche_caracteres=10),
        _e("diff_cierre", bytes=10, sha256="s", archivos=["a.py"]),
        _e("tarea_fin", clase="resuelta", error=None),
    ]
    if cerrado:
        eventos.append(_e("cierre", None, errores_del_registro=0, ultimo_error=None))
    return "\n".join(json.dumps(x) for x in eventos) + "\n"


def carpeta_con(tmp_path: Path, nombre: str, texto: str) -> Path:
    carpeta = tmp_path / nombre
    carpeta.mkdir()
    (carpeta / "registro_s.jsonl").write_text(texto, encoding="utf-8")
    return carpeta


def test_el_diagnostico_trae_el_recuento_de_peticiones_que_piden_razonar(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    carpeta = carpeta_con(tmp_path, "mixta", registro([False, True, False, None]))
    assert kr.main(["diagnosticar", "--salida", str(carpeta)]) == kr.EXIT_OK  # sin la regla, no cambia nada
    informe = json.loads(capsys.readouterr().out)
    cuenta = informe["razonamiento"]
    assert (cuenta["peticiones_que_piden_razonar"], cuenta["peticiones_que_piden_no_razonar"]) == (1, 2)
    assert cuenta["peticiones_sin_el_dato"] == 1
    assert informe["tareas"][0]["razonamiento"]["peticiones_que_piden_razonar"] == 1


def test_con_todas_las_peticiones_sin_razonar_la_regla_se_cumple(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    carpeta = carpeta_con(tmp_path, "limpia", registro([False] * 6))
    assert kr.main(["diagnosticar", "--salida", str(carpeta), "--sin-razonar"]) == kr.EXIT_OK
    captura = capsys.readouterr()
    assert "CORRIDA INVÁLIDA" not in captura.err
    assert json.loads(captura.out)["razonamiento"]["peticiones_que_piden_razonar"] == 0


@pytest.mark.parametrize(
    ("piden", "fragmento"),
    [
        ([False, False, True, False, False, False], "1 peticiones piden razonar"),  # una sola invalida
        ([True] * 6, "6 peticiones piden razonar"),  # el kit de base con el arnés nuevo
        ([False, None], "1 no traen el dato"),  # sin el parámetro decide el servidor
        ([None, None], "2 no traen el dato"),  # un registro anterior al #195
    ],
)
def test_una_sola_peticion_que_pida_razonar_o_sin_el_dato_invalida_la_corrida(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], piden: list[Any], fragmento: str
) -> None:
    carpeta = carpeta_con(tmp_path, "caso", registro(piden))
    assert kr.main(["diagnosticar", "--salida", str(carpeta)]) == kr.EXIT_OK  # control: sin la regla pasa
    capsys.readouterr()
    assert kr.main(["diagnosticar", "--salida", str(carpeta), "--sin-razonar"]) == kr.EXIT_RAZONA
    error = capsys.readouterr().err
    assert "CORRIDA INVÁLIDA" in error and fragmento in error


def test_otro_codigo_distinto_de_0_gana_al_de_la_regla_y_el_problema_se_dice_igual(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    muerta = carpeta_con(tmp_path, "muerta", registro([True], cerrado=False))
    assert kr.main(["diagnosticar", "--salida", str(muerta), "--sin-razonar"]) == kr.EXIT_MUERTA
    assert "CORRIDA INVÁLIDA: 1 peticiones piden razonar" in capsys.readouterr().err
    assert len({kr.EXIT_RAZONA, kr.EXIT_OK, kr.EXIT_ENTRADA, kr.EXIT_CORTADA, kr.EXIT_REGISTRO}) == 5
    assert kr.EXIT_RAZONA not in (
        kr.EXIT_MUERTA,
        kr.EXIT_DETENIDA_VIVA,
        kr.EXIT_CON_COLGADAS,
        kr.EXIT_DIFIERE,
    )


def test_un_informe_sin_el_recuento_no_cumple_la_regla() -> None:
    assert "no trae el recuento" in str(kr.problema_si_no_debia_razonar({"sesion": {}}))
    # Ninguna petición tampoco demuestra nada: la regla exige al menos una, y todas pidiendo no razonar.
    vacio = {
        "peticiones_que_piden_razonar": 0,
        "peticiones_sin_el_dato": 0,
        "peticiones_que_piden_no_razonar": 0,
    }
    assert "0 piden no razonar" in str(kr.problema_si_no_debia_razonar({"razonamiento": vacio}))
    vacio["peticiones_que_piden_no_razonar"] = 3
    assert kr.problema_si_no_debia_razonar({"razonamiento": vacio}) is None


def test_comprobar_aplica_la_regla_a_cada_pasada_nombrada(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def rescate_sano(argv: list[str]) -> int:
        print(json.dumps({"descarga_incompleta": []}))
        return 0

    monkeypatch.setattr(kaggle_rescate, "main", rescate_sano)
    destino = tmp_path / "rescate"
    for slug, piden in (("sin-razonar", [False, False]), ("razona", [False, True])):
        carpeta = destino / "notebooks" / slug
        carpeta.mkdir(parents=True)
        (carpeta / "salida__registro_s.jsonl").write_text(registro(piden), encoding="utf-8")
        (carpeta / "salida__latido_s.jsonl").write_text("{}\n", encoding="utf-8")
    base = ["comprobar", "--rescate", str(destino)]

    assert kr.main([*base, "--notebook", "sin-razonar", "--notebook", "razona"]) == kr.EXIT_OK
    sin_regla = json.loads(capsys.readouterr().out)["pasadas_esperadas"]
    assert sin_regla["razona"] == {"codigo": 0, "veredicto": sin_regla["razona"]["veredicto"]}

    assert kr.main([*base, "--notebook", "sin-razonar", "--sin-razonar"]) == kr.EXIT_OK
    buena = json.loads(capsys.readouterr().out)["pasadas_esperadas"]["sin-razonar"]
    assert buena["codigo"] == 0 and buena["razonamiento"]["peticiones_que_piden_razonar"] == 0
    assert buena["regla_sin_razonar"].startswith("cumplida")

    assert (
        kr.main([*base, "--notebook", "sin-razonar", "--notebook", "razona", "--sin-razonar"])
        == kr.EXIT_RAZONA
    )
    pasadas = json.loads(capsys.readouterr().out)["pasadas_esperadas"]
    assert pasadas["sin-razonar"]["codigo"] == 0 and pasadas["razona"]["codigo"] == kr.EXIT_RAZONA
    assert pasadas["razona"]["razonamiento"]["peticiones_que_piden_razonar"] == 1
    assert "1 peticiones piden razonar" in pasadas["razona"]["regla_sin_razonar"]
