"""Pruebas de la comprobación «la instrucción no nombra herramientas fuera de la lista» (issue #173).

Todos los kits se definen aquí, con texto inventado: ningún enunciado, identificador de tarea ni
instrucción real de la competencia entra en el repositorio.
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

from scripts import kaggle_submission
from scripts.kaggle_submission import (
    EXIT_INPUTS,
    EXIT_INVALID,
    EXIT_OK,
    HARNESS_TOOLS,
    check_tool_references,
    main,
    pack_submission,
    parse_sin_resultados,
    validate_submission_dir,
    verify_zip_submission,
)

BASIC = ["run_command", "read_file", "edit_file", "write_file", "get_status", "submit_patch"]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_kit(
    root: Path,
    *,
    tools: list[str],
    instruction: str,
    sub_tools: list[str] | None = None,
    sub_instruction: str = "Analiza el código.\n",
    sub_listed: bool = True,
    name: str = "agente_principal",
    sub_name: str = "agente_analizador",
) -> Path:
    """Kit mínimo: agent.yaml con la instrucción en prompts/system.md y, opcionalmente, un subagente."""
    items = "".join(f"  - {t}\n" for t in tools)
    if sub_tools is not None and sub_listed:
        items += (
            "  - agent_tool:\n      config_path: sub_agents/analizador.yaml\n      skip_summarization: true\n"
        )
    _write(
        root / "agent.yaml",
        f"name: {name}\nmodel: modelo-ficticio\ninstruction: !include prompts/system.md\n"
        f"tools:\n{items}generate_content_config: !include configs/sampling.yaml\n",
    )
    _write(root / "eval_config.yaml", "timeout: 10\n")
    _write(root / "configs" / "sampling.yaml", "temperature: 0.0\n")
    _write(root / "prompts" / "system.md", instruction)
    if sub_tools is not None:
        sub_items = "".join(f"  - {t}\n" for t in sub_tools)
        _write(
            root / "sub_agents" / "analizador.yaml",
            f"name: {sub_name}\nmodel: modelo-ficticio\ninstruction: !include ../prompts/analizador.md\n"
            f"tools:\n{sub_items}",
        )
        _write(root / "prompts" / "analizador.md", sub_instruction)
    return root


def errors(messages: list[str]) -> list[str]:
    return [m for m in messages if m.startswith("[ERROR]")]


def warnings(messages: list[str]) -> list[str]:
    return [m for m in messages if m.startswith("[AVISO]")]


# --- regla 1: nombra una herramienta ausente ---------------------------------------------------


def test_instruccion_que_nombra_una_herramienta_ausente_falla(tmp_path: Path) -> None:
    kit = make_kit(tmp_path, tools=BASIC, instruction="Localiza con `search_similar_code` y edita.\n")
    ok, msgs = check_tool_references(kit)
    assert ok is False
    assert len(errors(msgs)) == 1
    assert "search_similar_code" in errors(msgs)[0]
    assert "línea 1" in errors(msgs)[0]


def test_instruccion_que_solo_nombra_presentes_pasa(tmp_path: Path) -> None:
    kit = make_kit(
        tmp_path, tools=BASIC, instruction="Usa `read_file`, luego `edit_file` y `submit_patch`.\n"
    )
    ok, msgs = check_tool_references(kit)
    assert ok is True
    assert errors(msgs) == []
    assert any(m.startswith("[OK]") for m in msgs)


def test_nombre_sin_comillas_invertidas_tambien_cuenta(tmp_path: Path) -> None:
    kit = make_kit(tmp_path, tools=BASIC, instruction="Primero get_code_neighbors del símbolo.\n")
    ok, msgs = check_tool_references(kit)
    assert ok is False
    assert "get_code_neighbors" in errors(msgs)[0]


def test_nombre_dentro_de_un_bloque_de_codigo_cuenta(tmp_path: Path) -> None:
    instruction = "Pasos:\n\n```\nget_code_subgraph(nodo)\n```\n"
    kit = make_kit(tmp_path, tools=BASIC, instruction=instruction)
    ok, msgs = check_tool_references(kit)
    assert ok is False
    assert "get_code_subgraph" in errors(msgs)[0]
    assert "línea 4" in errors(msgs)[0]


@pytest.mark.parametrize("escrito", ["SEARCH_SIMILAR_CODE", "Search_Similar_Code", "sEaRcH_sImIlAr_CoDe"])
def test_las_mayusculas_no_esconden_el_nombre(tmp_path: Path, escrito: str) -> None:
    kit = make_kit(tmp_path, tools=BASIC, instruction=f"Llama a `{escrito}` primero.\n")
    ok, _ = check_tool_references(kit)
    assert ok is False


def test_la_lista_con_otras_mayusculas_sigue_ofreciendo_la_herramienta(tmp_path: Path) -> None:
    kit = make_kit(
        tmp_path, tools=["Read_File", "SUBMIT_PATCH"], instruction="Usa `read_file` y `submit_patch`.\n"
    )
    ok, msgs = check_tool_references(kit)
    assert ok is True, msgs


def test_un_nombre_mas_largo_no_es_el_nombre(tmp_path: Path) -> None:
    # ninguna de las cuatro está en la lista: la coincidencia por subcadena las daría por nombradas
    instruction = "Ver read_file_all, xget_status, submit_patch2 y search_similar_code_v2.\n"
    kit = make_kit(tmp_path, tools=["run_command"], instruction=instruction)
    ok, msgs = check_tool_references(kit)
    assert ok is True, msgs


@pytest.mark.parametrize(
    "texto", ["(read_file)", "read_file.", "`read_file`,", "- read_file: leer", "x=read_file(a)"]
)
def test_signos_alrededor_del_nombre_si_cuentan(tmp_path: Path, texto: str) -> None:
    kit = make_kit(tmp_path, tools=["run_command"], instruction=f"{texto}\n")
    ok, _ = check_tool_references(kit)
    assert ok is False


# --- el archivo incluido y las otras formas de dar la instrucción -------------------------------


def test_nombre_en_un_include_de_otra_carpeta(tmp_path: Path) -> None:
    kit = make_kit(tmp_path, tools=BASIC, instruction="x\n")
    _write(kit / "textos" / "regla.md", "Reglas.\nUsa `search_similar_code`.\n")
    _write(
        kit / "agent.yaml",
        "name: a\ninstruction: !include textos/regla.md\ntools:\n  - read_file\n",
    )
    ok, msgs = check_tool_references(kit)
    assert ok is False
    assert "search_similar_code" in errors(msgs)[0]
    assert "línea 2" in errors(msgs)[0]


def test_include_que_no_existe_falla(tmp_path: Path) -> None:
    kit = make_kit(tmp_path, tools=BASIC, instruction="x\n")
    (kit / "prompts" / "system.md").unlink()
    ok, msgs = check_tool_references(kit)
    assert ok is False
    assert "no existe" in errors(msgs)[0]


def test_include_que_sale_del_envio_falla(tmp_path: Path) -> None:
    kit = make_kit(tmp_path / "kit", tools=BASIC, instruction="x\n")
    _write(tmp_path / "fuera.md", "Usa `search_similar_code`.\n")
    _write(
        kit / "agent.yaml",
        "name: a\ninstruction: !include ../fuera.md\ntools:\n  - read_file\n",
    )
    ok, msgs = check_tool_references(kit)
    assert ok is False
    assert "fuera del envío" in errors(msgs)[0]


def test_instruccion_en_linea_y_en_bloque(tmp_path: Path) -> None:
    kit = make_kit(tmp_path, tools=BASIC, instruction="x\n")
    _write(
        kit / "agent.yaml",
        "name: a\ninstruction: Usa `get_status` y get_code_subgraph.\ntools: [read_file, get_status]\n",
    )
    ok, msgs = check_tool_references(kit)
    assert ok is False
    assert "get_code_subgraph" in errors(msgs)[0]
    _write(
        kit / "agent.yaml",
        "name: a\ninstruction: |\n  Primera línea.\n  Usa get_code_neighbors.\ntools:\n  - read_file\n",
    )
    ok, msgs = check_tool_references(kit)
    assert ok is False
    assert "get_code_neighbors" in errors(msgs)[0]
    assert "línea 2" in errors(msgs)[0]


def test_tools_con_forma_ilegible_falla_en_vez_de_aprobar(tmp_path: Path) -> None:
    kit = make_kit(tmp_path, tools=BASIC, instruction="Usa `search_similar_code`.\n")
    _write(
        kit / "agent.yaml", "name: a\ninstruction: !include prompts/system.md\ntools: !include tools.yaml\n"
    )
    ok, msgs = check_tool_references(kit)
    assert ok is False
    assert "no sabe leer" in errors(msgs)[0]


def test_comentarios_en_la_lista_no_son_herramientas(tmp_path: Path) -> None:
    kit = make_kit(tmp_path, tools=BASIC, instruction="Usa `read_file`.\n")
    _write(
        kit / "agent.yaml",
        "name: a\ninstruction: !include prompts/system.md\ntools:\n  - read_file  # sola\n  # - edit_file\n",
    )
    ok, _ = check_tool_references(kit)
    assert ok is True
    _write(kit / "prompts" / "system.md", "Usa `edit_file`.\n")
    ok, _ = check_tool_references(kit)
    assert ok is False


# --- subagentes con su propia lista -------------------------------------------------------------


def test_la_instruccion_del_subagente_se_compara_con_su_lista(tmp_path: Path) -> None:
    # `edit_file` está en la lista del principal pero no en la del subagente
    kit = make_kit(
        tmp_path,
        tools=BASIC,
        instruction="Usa `read_file`.\n",
        sub_tools=["read_file"],
        sub_instruction="Corrige con `edit_file`.\n",
    )
    ok, msgs = check_tool_references(kit)
    assert ok is False
    assert len(errors(msgs)) == 1
    assert "agente_analizador" in errors(msgs)[0]
    assert "edit_file" in errors(msgs)[0]


def test_una_herramienta_del_subagente_no_cuenta_como_presente_en_el_principal(tmp_path: Path) -> None:
    kit = make_kit(
        tmp_path,
        tools=BASIC,
        instruction="Pide a la subtarea que use `get_code_neighbors`.\n",
        sub_tools=["read_file", "get_code_neighbors"],
    )
    ok, msgs = check_tool_references(kit)
    assert ok is False
    assert "agente_principal" in errors(msgs)[0]
    assert "get_code_neighbors" in errors(msgs)[0]


def test_subagente_con_instruccion_y_lista_coherentes_pasa(tmp_path: Path) -> None:
    kit = make_kit(
        tmp_path,
        tools=BASIC,
        instruction="Delega en `agente_analizador` si hace falta.\n",
        sub_tools=["read_file", "get_code_neighbors"],
        sub_instruction="Usa `get_code_neighbors` y `read_file`.\n",
    )
    ok, msgs = check_tool_references(kit)
    assert ok is True, msgs


def test_nombrar_al_subagente_sin_declararlo_falla(tmp_path: Path) -> None:
    kit = make_kit(
        tmp_path,
        tools=BASIC,
        instruction="Delega en `agente_analizador`.\n",
        sub_tools=["read_file"],
        sub_listed=False,  # el archivo del subagente queda, pero agent.yaml ya no lo declara
    )
    ok, msgs = check_tool_references(kit)
    assert ok is False
    assert "agente_analizador" in errors(msgs)[0]


def test_subagente_que_no_existe_falla(tmp_path: Path) -> None:
    kit = make_kit(tmp_path, tools=BASIC, instruction="x\n", sub_tools=["read_file"])
    (kit / "sub_agents" / "analizador.yaml").unlink()
    ok, msgs = check_tool_references(kit)
    assert ok is False
    assert "no existe dentro del envío" in errors(msgs)[0]


def test_un_agente_puede_nombrar_su_propio_nombre(tmp_path: Path) -> None:
    kit = make_kit(tmp_path, tools=BASIC, instruction="Eres agente_principal.\n")
    ok, msgs = check_tool_references(kit)
    assert ok is True, msgs


# --- regla 2: aviso por herramientas sin resultados ---------------------------------------------


def test_sin_resultados_avisa_y_no_falla(tmp_path: Path) -> None:
    kit = make_kit(
        tmp_path,
        tools=[*BASIC, "search_similar_code"],
        instruction="Localiza con `search_similar_code`.\n",
    )
    ok, msgs = check_tool_references(kit, frozenset({"search_similar_code"}))
    assert ok is True
    assert len(warnings(msgs)) == 1
    assert "search_similar_code" in warnings(msgs)[0]
    assert "su instrucción la nombra" in warnings(msgs)[0]


def test_aviso_sin_que_la_instruccion_la_nombre(tmp_path: Path) -> None:
    kit = make_kit(tmp_path, tools=[*BASIC, "get_code_subgraph"], instruction="Edita.\n")
    ok, msgs = check_tool_references(kit, frozenset({"get_code_subgraph"}))
    assert ok is True
    assert len(warnings(msgs)) == 1
    assert "su instrucción la nombra" not in warnings(msgs)[0]


def test_sin_el_parametro_no_avisa_y_lo_dice(tmp_path: Path) -> None:
    kit = make_kit(tmp_path, tools=[*BASIC, "search_similar_code"], instruction="Edita.\n")
    ok, msgs = check_tool_references(kit)
    assert ok is True
    assert warnings(msgs) == []
    assert any("Sin --sin-resultados" in m for m in msgs)


def test_aviso_solo_de_las_herramientas_de_la_lista_de_cada_agente(tmp_path: Path) -> None:
    kit = make_kit(
        tmp_path,
        tools=BASIC,
        instruction="Edita.\n",
        sub_tools=["read_file", "search_similar_code"],
        sub_instruction="Busca con `search_similar_code`.\n",
    )
    ok, msgs = check_tool_references(kit, frozenset({"search_similar_code"}))
    assert ok is True
    assert len(warnings(msgs)) == 1
    assert "agente_analizador" in warnings(msgs)[0]


def test_herramienta_marcada_que_el_kit_no_ofrece_no_avisa(tmp_path: Path) -> None:
    kit = make_kit(tmp_path, tools=BASIC, instruction="Edita.\n")
    ok, msgs = check_tool_references(kit, frozenset({"search_similar_code"}))
    assert ok is True
    assert warnings(msgs) == []


def test_nombre_desconocido_en_sin_resultados_falla(tmp_path: Path) -> None:
    kit = make_kit(tmp_path, tools=BASIC, instruction="Edita.\n")
    ok, msgs = check_tool_references(kit, frozenset({"search_simlar_code"}))
    assert ok is False
    assert "search_simlar_code" in errors(msgs)[0]


def test_sin_resultados_acepta_el_nombre_de_un_subagente_declarado(tmp_path: Path) -> None:
    kit = make_kit(tmp_path, tools=BASIC, instruction="Edita.\n", sub_tools=["read_file"])
    ok, msgs = check_tool_references(kit, frozenset({"agente_analizador"}))
    assert ok is True, msgs
    assert len(warnings(msgs)) == 1


def test_parse_sin_resultados_lista_y_json(tmp_path: Path) -> None:
    assert parse_sin_resultados("Search_Similar_Code, get_code_subgraph ,") == frozenset(
        {"search_similar_code", "get_code_subgraph"}
    )
    plain = tmp_path / "lista.json"
    plain.write_text(json.dumps(["read_file"]), encoding="utf-8")
    assert parse_sin_resultados(str(plain)) == frozenset({"read_file"})
    wrapped = tmp_path / "objeto.json"
    wrapped.write_text(json.dumps({"sin_resultados": ["edit_file"]}), encoding="utf-8")
    assert parse_sin_resultados(str(wrapped)) == frozenset({"edit_file"})
    bad = tmp_path / "mal.json"
    bad.write_text(json.dumps({"otra_clave": []}), encoding="utf-8")
    with pytest.raises(ValueError):
        parse_sin_resultados(str(bad))


# --- integración con validate / verify / CLI / compilador --------------------------------------


@pytest.fixture
def compiler_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(kaggle_submission, "compile_with_adk", lambda _dir: (True, "compilador simulado"))


@pytest.mark.usefixtures("compiler_ok")
def test_validate_y_verify_fallan_con_el_defecto_aunque_el_compilador_apruebe(tmp_path: Path) -> None:
    kit = make_kit(tmp_path / "kit", tools=BASIC, instruction="Localiza con `search_similar_code`.\n")
    ok, msgs = validate_submission_dir(kit)
    assert ok is False
    assert any("search_similar_code" in m for m in errors(msgs))
    with pytest.raises(ValueError):
        pack_submission(kit, tmp_path / "malo.zip")

    # el mismo kit sin el defecto empaqueta, y su zip se verifica
    _write(kit / "prompts" / "system.md", "Localiza con `read_file`.\n")
    zip_path = tmp_path / "bueno.zip"
    pack_submission(kit, zip_path)
    ok, msgs, _, _ = verify_zip_submission(zip_path)
    assert ok is True, msgs


@pytest.mark.usefixtures("compiler_ok")
def test_verify_del_zip_detecta_el_defecto(tmp_path: Path) -> None:
    import zipfile

    kit = make_kit(tmp_path / "kit", tools=BASIC, instruction="Localiza con `read_file`.\n")
    zip_path = tmp_path / "x.zip"
    pack_submission(kit, zip_path)
    bad = tmp_path / "malo.zip"
    with zipfile.ZipFile(zip_path) as src, zipfile.ZipFile(bad, "w") as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "prompts/system.md":
                data = b"Localiza con `search_similar_code`.\n"
            dst.writestr(info, data)
    ok, msgs, _, _ = verify_zip_submission(bad)
    assert ok is False
    assert any("search_similar_code" in m for m in errors(msgs))


@pytest.mark.usefixtures("compiler_ok")
def test_cli_verify_codigos_de_salida_y_avisos(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    kit = make_kit(
        tmp_path / "kit",
        tools=[*BASIC, "search_similar_code"],
        instruction="Localiza con `search_similar_code`.\n",
    )
    zip_path = tmp_path / "k.zip"
    pack_submission(kit, zip_path)

    assert main(["verify", str(zip_path)]) == EXIT_OK
    out = capsys.readouterr().out
    assert "[AVISO]" not in out
    assert "Sin --sin-resultados" in out

    assert main(["verify", str(zip_path), "--sin-resultados", "search_similar_code"]) == EXIT_OK
    out = capsys.readouterr().out
    assert "[AVISO]" in out
    assert "Resultado: VÁLIDO" in out

    assert main(["verify", str(zip_path), "--sin-resultados", "no_existe"]) == EXIT_INVALID
    capsys.readouterr()

    mal = tmp_path / "mal.json"
    mal.write_text("{no es json", encoding="utf-8")
    assert main(["verify", str(zip_path), "--sin-resultados", str(mal)]) == EXIT_INPUTS


def test_el_kit_de_prueba_sin_herramientas_ni_instruccion_pasa(tmp_path: Path) -> None:
    # igual que el kit mínimo de test_kaggle_submission: agent.yaml sin `instruction` ni `tools`
    _write(tmp_path / "agent.yaml", "model: m\nadapter: null\n")
    _write(tmp_path / "eval_config.yaml", "timeout: 1\n")
    _write(tmp_path / "prompts" / "system.md", "Usa `search_similar_code`.\n")
    ok, msgs = check_tool_references(tmp_path)
    assert ok is True, msgs


def test_compile_with_adk_registra_exactamente_la_lista_compartida(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    registered: list[str] = []

    class FakeRegistry:
        def register(self, name: str, _fn: object) -> None:
            registered.append(name)

    adk = types.ModuleType("adk_submission")
    adk.ToolRegistry = FakeRegistry  # type: ignore[attr-defined]
    adk.compile_submission = lambda **_kw: "agente"  # type: ignore[attr-defined]
    swe = types.ModuleType("swegemma")
    models = types.ModuleType("swegemma.models")
    models.setup_gemma_model_registry = lambda: object()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "adk_submission", adk)
    monkeypatch.setitem(sys.modules, "swegemma", swe)
    monkeypatch.setitem(sys.modules, "swegemma.models", models)

    ok, _ = kaggle_submission.compile_with_adk(tmp_path)
    assert ok is True
    assert registered == list(HARNESS_TOOLS)
    assert len(set(HARNESS_TOOLS)) == len(HARNESS_TOOLS) == 9


# --- formas de dar la instrucción y de declarar subagentes que no son las del kit A -------------


def test_instruccion_en_varias_lineas_sin_barra_vertical(tmp_path: Path) -> None:
    kit = make_kit(tmp_path, tools=BASIC, instruction="x\n")
    _write(
        kit / "agent.yaml",
        'name: a\ninstruction: "Primera línea\n  y luego get_code_subgraph."\ntools: [read_file]\n',
    )
    ok, msgs = check_tool_references(kit)
    assert ok is False
    assert "get_code_subgraph" in errors(msgs)[0]


def test_subagente_declarado_con_sub_agents_tambien_se_comprueba(tmp_path: Path) -> None:
    kit = make_kit(tmp_path, tools=BASIC, instruction="Transfiere a `agente_analizador` si hace falta.\n")
    _write(
        kit / "agent.yaml",
        "name: agente_principal\ninstruction: !include prompts/system.md\n"
        "tools: [read_file]\nsub_agents:\n  - config_path: sub_agents/analizador.yaml\n",
    )
    _write(
        kit / "sub_agents" / "analizador.yaml",
        "name: agente_analizador\ninstruction: !include ../prompts/analizador.md\ntools: [read_file]\n",
    )
    _write(kit / "prompts" / "analizador.md", "Busca con `search_similar_code`.\n")
    ok, msgs = check_tool_references(kit)
    assert ok is False
    assert len(errors(msgs)) == 1
    assert "agente_analizador" in errors(msgs)[0]
    assert "search_similar_code" in errors(msgs)[0]
    # nombrar al subagente en el principal no es un error: lo declara con sub_agents
    assert "agente_principal" not in errors(msgs)[0]


# --- límites conocidos: lo que la regla NO detecta (documentados en el código) -----------------


@pytest.mark.parametrize(
    "texto",
    [
        "Busca con search similar code.",  # nombre partido en palabras
        "Busca con search_similar\\_code.",  # escape de Markdown
        "Busca con search-similar-code.",  # guiones en vez de guion bajo
    ],
)
def test_limite_conocido_variantes_del_nombre_no_se_detectan(tmp_path: Path, texto: str) -> None:
    kit = make_kit(tmp_path, tools=BASIC, instruction=texto + "\n")
    ok, _ = check_tool_references(kit)
    assert ok is True  # si alguna vez se detecta, esta prueba debe cambiar a ok is False


def test_limite_conocido_la_descripcion_de_un_subagente_no_se_lee(tmp_path: Path) -> None:
    # `description` llega al agente que llama al subagente, pero el esquema del organizador no lo trata como
    # instrucción y esta regla solo lee `instruction`.
    kit = make_kit(tmp_path, tools=BASIC, instruction="Edita.\n", sub_tools=["read_file"])
    path = kit / "sub_agents" / "analizador.yaml"
    path.write_text(
        path.read_text(encoding="utf-8") + "description: Usa search_similar_code.\n", encoding="utf-8"
    )
    ok, _ = check_tool_references(kit)
    assert ok is True
