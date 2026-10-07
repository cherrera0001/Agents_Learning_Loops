"""Comprobaciones mecánicas de un manuscrito (scripts/paper_check.py) y su maquetación (paper_pdf.py)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import paper_check as pc

BUENO = """# Título

**Subtitle:** Subtítulo.

Autora

## Abstract

Medimos 71 de 129 tareas y 103 con paquetes.

## 1. Introduction

Las tareas se evalúan con pruebas (Jimenez et al., 2023). Miller (2024) da fórmulas.

**Table 1**

*Tareas Que Discriminan*

| Repositorio | Tareas |
|---|---|
| Total | 129 |

*Note.* De 129, discriminan 71; con paquetes, 103.

## References

Jimenez, C. E., & Yang, J. (2023). *SWE-bench* (arXiv:2310.06770). arXiv. https://arxiv.org/abs/2310.06770

Miller, E. (2024). *Adding error bars to evals* (arXiv:2411.00640). arXiv. https://arxiv.org/abs/2411.00640
"""


def test_un_manuscrito_en_regla_no_tiene_hallazgos() -> None:
    informe = pc.comprobar(BUENO, limite=3000)
    assert informe["hallazgos"] == []
    assert informe["referencias"] == 2 and informe["citas_en_texto"] == 2 and informe["tablas"] == 1
    assert len(informe["sha256"]) == 64 and informe["caracteres"] == len(BUENO)
    assert (
        informe["palabras"]["total"] == informe["palabras"]["cuerpo"] + informe["palabras"]["referencias"] + 2
    )


def test_las_barras_de_las_tablas_no_cuentan_como_palabras() -> None:
    assert pc.palabras("| a | b |\n|---|---|\n| c | d |") == 4


@pytest.mark.parametrize(
    ("cambio", "esperado"),
    [
        (
            ("(Jimenez et al., 2023)", "(Jimenez et al., 2024)"),
            "Cita sin entrada en la lista: Jimenez (2024)",
        ),
        (("Miller (2024) da fórmulas.", "Hay fórmulas."), "Entrada sin cita en el texto: Miller (2024)"),
        (("con pruebas (Jimenez", "con pruebas [1] (Jimenez"), "Citas numéricas en el texto"),
        (
            (
                "*Note.* De 129, discriminan 71; con paquetes, 103.",
                "De 129, discriminan 71; con paquetes, 103.",
            ),
            "falta nota",
        ),
        (("**Table 1**\n\n", ""), "falta número en negrita"),
        (
            ("y 103 con paquetes.", "y 104 con paquetes."),
            "Cifras del resumen que no aparecen en el cuerpo: ['104']",
        ),
        (("Medimos 71", "Primero.\n\nMedimos 71"), "El resumen tiene 2 párrafos"),
    ],
)
def test_cada_defecto_sale_como_hallazgo(cambio: tuple[str, str], esperado: str) -> None:
    assert BUENO.count(cambio[0]) == 1
    hallazgos = pc.comprobar(BUENO.replace(*cambio), limite=3000)["hallazgos"]
    assert any(esperado in h for h in hallazgos), hallazgos


def test_el_orden_alfabetico_y_la_numeracion_de_la_lista_se_comprueban() -> None:
    partes = BUENO.split("## References\n\n")
    jimenez, miller = partes[1].strip().split("\n\n")
    al_reves = pc.comprobar(f"{partes[0]}## References\n\n{miller}\n\n{jimenez}\n", limite=3000)["hallazgos"]
    assert any("orden alfabético" in h for h in al_reves)
    numerada = pc.comprobar(f"{partes[0]}## References\n\n1. {jimenez}\n\n2. {miller}\n", limite=3000)[
        "hallazgos"
    ]
    assert any("numerada" in h for h in numerada)


def test_pasar_el_limite_de_palabras_es_un_hallazgo() -> None:
    assert any("sobre el límite de 10" in h for h in pc.comprobar(BUENO, limite=10)["hallazgos"])


def test_sin_resumen_o_sin_referencias_la_entrada_es_invalida(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(ValueError, match="resumen y una de referencias"):
        pc.partir("# Solo un título\n")
    malo = tmp_path / "m.md"
    malo.write_text("# Solo un título\n", encoding="utf-8")
    assert pc.main(["comprobar", str(malo)]) == pc.EXIT_ENTRADA
    assert "ENTRADA INVÁLIDA" in capsys.readouterr().err


def test_la_orden_comprobar_sale_con_0_o_con_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bueno = tmp_path / "bueno.md"
    bueno.write_text(BUENO, encoding="utf-8")
    assert pc.main(["comprobar", str(bueno)]) == pc.EXIT_OK
    assert json.loads(capsys.readouterr().out)["hallazgos"] == []
    assert pc.main(["comprobar", str(bueno), "--limite", "10"]) == pc.EXIT_HALLAZGOS


def test_referencias_contrasta_cada_entrada_con_su_registro(monkeypatch: pytest.MonkeyPatch) -> None:
    registros = {
        "2310.06770": {
            "titulo": "SWE-bench",
            "anio": "2023",
            "autores": ["Carlos E. Jimenez", "John Yang"],
            "doi_publicado": "",
        },
        "2411.00640": {
            "titulo": "Adding Error Bars",
            "anio": "2025",
            "autores": ["Evan Miller"],
            "doi_publicado": "10.1/x",
        },
    }
    monkeypatch.setattr(pc, "registro_arxiv", lambda i: registros[i])
    monkeypatch.setattr(pc, "_pedir", lambda url, tope=30: (404 if "2411" in url else 200, b""))
    informe = pc.referencias(BUENO)
    assert [r["entrada"] for r in informe["referencias"]] == ["Jimenez (2023)", "Miller (2024)"]
    assert informe["problemas"] == [
        "Miller (2024): tiene versión publicada (10.1/x); APA pide citar esa.",
        "Miller (2024): el registro da el año 2025.",
        "Miller (2024): https://arxiv.org/abs/2411.00640 respondió 404.",
    ]


def test_con_mas_de_veinte_autores_se_exigen_los_puntos_suspensivos(monkeypatch: pytest.MonkeyPatch) -> None:
    muchos = {
        "titulo": "T",
        "anio": "2023",
        "autores": ["Carlos E. Jimenez"] + [f"A B{i}" for i in range(24)],
        "doi_publicado": "",
    }
    monkeypatch.setattr(
        pc,
        "registro_arxiv",
        lambda i: (
            muchos
            if i == "2310.06770"
            else {"titulo": "", "anio": "2024", "autores": ["Evan Miller"], "doi_publicado": ""}
        ),
    )
    monkeypatch.setattr(pc, "_pedir", lambda url, tope=30: (200, b""))
    assert pc.referencias(BUENO)["problemas"] == [
        "Jimenez (2023): con 25 autores faltan los puntos suspensivos antes del último."
    ]


def test_el_pdf_tiene_las_mismas_palabras_que_el_manuscrito(tmp_path: Path) -> None:
    pytest.importorskip("reportlab")
    pytest.importorskip("pypdf")
    from scripts import paper_pdf

    fuente = tmp_path / "m.md"
    fuente.write_text(BUENO, encoding="utf-8")
    assert paper_pdf.main([str(fuente), str(tmp_path / "m.pdf")]) == 0
    assert (tmp_path / "m.pdf").stat().st_size > 1000
    assert paper_pdf.diferencias(fuente, tmp_path / "m.pdf") == {}
