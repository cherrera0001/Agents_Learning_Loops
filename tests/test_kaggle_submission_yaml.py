"""Pruebas de la lectura con PyYAML de la comprobación de herramientas (issue #173, correcciones de revisión).

Cubre las diez formas de YAML válido que la primera versión (expresiones regulares línea a línea)
dejaba pasar,
los falsos positivos que volvían INVÁLIDO un kit que el compilador acepta, la mención en negativo, los errores
de entrada y las pruebas que faltaban. Todos los kits son inventados.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import kaggle_submission
from scripts.kaggle_submission import (
    EXIT_INPUTS,
    EXIT_INVALID,
    EXIT_OK,
    check_tool_references,
    main,
    pack_submission,
    parse_sin_resultados,
    validate_submission_dir,
    verify_zip_submission,
)

BAD = "Localiza con `search_similar_code` y edita.\n"
CLEAN = "Lee con `read_file` y edita.\n"


def _write(path: Path, text: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(text, bytes):
        path.write_bytes(text)
    else:
        path.write_text(text, encoding="utf-8")


def errors(messages: list[str]) -> list[str]:
    return [m for m in messages if m.startswith("[ERROR]")]


def kit(root: Path, agent_yaml: str | bytes, files: dict[str, str | bytes] | None = None) -> Path:
    _write(root / "agent.yaml", agent_yaml)
    _write(root / "eval_config.yaml", "timeout: 10\n")
    for rel, content in (files or {}).items():
        _write(root / rel, content)
    return root


def assert_falla_por_search(root: Path) -> None:
    ok, msgs = check_tool_references(root)
    assert ok is False, msgs
    assert any("search_similar_code" in e for e in errors(msgs)), msgs


def assert_pasa(root: Path) -> None:
    ok, msgs = check_tool_references(root)
    assert ok is True, msgs
    assert errors(msgs) == []


SUB_BAD = "name: helper\ninstruction: !include ../p/h.md\ntools: [read_file]\n"

# --- las diez formas de YAML válido que la regla dejaba pasar ----------
# Todas: `tools` solo `read_file`, y la orden de `search_similar_code` en la instrucción.

EVASIONES: dict[str, tuple[str | bytes, dict[str, str | bytes]]] = {
    "bom": (
        b"\xef\xbb\xbfinstruction: !include p.md\nname: a\ntools: [read_file]\n",
        {"p.md": BAD},
    ),
    "clave_entrecomillada": (
        'name: a\n"instruction": !include p.md\ntools: [read_file]\n',
        {"p.md": BAD},
    ),
    "todas_las_claves_sangradas": (
        "  name: a\n  instruction: !include p.md\n  tools: [read_file]\n",
        {"p.md": BAD},
    ),
    "include_en_la_linea_siguiente": (
        "name: a\ninstruction:\n  !include p.md\ntools: [read_file]\n",
        {"p.md": BAD},
    ),
    "alias": (
        'name: a\ndescription: &d "Localiza con search_similar_code."\ninstruction: *d\ntools: [read_file]\n',
        {},
    ),
    "subagente_como_mapa_en_flujo": (
        "name: a\ninstruction: ok\ntools:\n  - read_file\n"
        "  - {agent_tool: {config_path: sub_agents/h.yaml}}\n",
        {
            "sub_agents/h.yaml": "name: helper\ninstruction: !include ../p/h.md\ntools: [read_file]\n",
            "p/h.md": BAD,
        },
    ),
    "espacio_antes_de_los_dos_puntos": (
        "name: a\ninstruction : !include p.md\ntools: [read_file]\n",
        {"p.md": BAD},
    ),
    "documento_entero_en_flujo": (
        '{name: a, instruction: "Localiza con search_similar_code.", tools: [read_file]}\n',
        {},
    ),
    "sub_agents_con_include": (
        "name: a\ninstruction: ok\ntools: [read_file]\nsub_agents: !include subs.yaml\n",
        {
            "subs.yaml": "- config_path: sub_agents/h.yaml\n",
            "sub_agents/h.yaml": "name: helper\ninstruction: !include ../p/h.md\ntools: [read_file]\n",
            "p/h.md": BAD,
        },
    ),
    "clave_compleja": (
        'name: a\n? instruction\n: "Localiza con search_similar_code."\ntools: [read_file]\n',
        {},
    ),
}


@pytest.mark.parametrize("caso", sorted(EVASIONES))
def test_las_diez_evasiones_ahora_fallan(tmp_path: Path, caso: str) -> None:
    agent_yaml, files = EVASIONES[caso]
    assert_falla_por_search(kit(tmp_path, agent_yaml, files))


def test_las_diez_evasiones_son_diez() -> None:
    assert len(EVASIONES) == 10


# --- falsos positivos: kits que el compilador acepta y la regla rechazaba ----------

FALSOS_POSITIVOS: dict[str, tuple[str | bytes, dict[str, str | bytes]]] = {
    "tools_nulo": (
        "name: a\ninstruction: !include p.md\ntools: ~\n",
        {"p.md": "Lee el código y corrige.\n"},
    ),
    "include_entrecomillado": (
        'name: a\ninstruction: !include "p.md"\ntools: [read_file]\n',
        {"p.md": CLEAN},
    ),
    "comentario_en_columna_0_dentro_de_tools": (
        "name: a\ninstruction: !include p.md\ntools:\n  - read_file\n# comentario\n  - edit_file\n",
        {"p.md": "Usa read_file y edit_file.\n"},
    ),
    "lista_en_flujo_partida": (
        "name: a\ninstruction: !include p.md\ntools: [read_file,\n  edit_file]\n",
        {"p.md": "Usa read_file y edit_file.\n"},
    ),
    "tools_con_include": (
        "name: a\ninstruction: !include p.md\ntools: !include t.yaml\n",
        {"p.md": CLEAN, "t.yaml": "- read_file\n- edit_file\n"},
    ),
    "comentario_con_apostrofo": (
        "name: a\ninstruction: !include p.md\ntools:\n  - read_file  # el modelo no debe usar 'otra'\n",
        {"p.md": CLEAN},
    ),
    "ancla_en_un_item": (
        "name: a\ninstruction: !include p.md\ntools:\n  - &r read_file\n  - *r\n",
        {"p.md": CLEAN},
    ),
    "config_path_con_espacio": (
        "name: a\ninstruction: !include p.md\ntools:\n  - agent_tool:\n"
        '      config_path: "sub_agents/mi ayudante.yaml"\n',
        {
            "p.md": "Delega el trabajo.\n",
            "sub_agents/mi ayudante.yaml": "name: ayudante\ninstruction: ok\ntools: [read_file]\n",
        },
    ),
    "archivo_huerfano_con_nombre_corriente": (
        "name: a\ninstruction: Haz un plan y edita.\ntools: [read_file]\n",
        {"sub_agents/viejo.yaml": "name: plan\ninstruction: z\ntools: [read_file]\n"},
    ),
    "subagentes_pares_se_nombran": (
        "name: a\ninstruction: ok\ntools: [read_file]\nsub_agents:\n"
        "  - config_path: sub_agents/uno.yaml\n  - config_path: sub_agents/dos.yaml\n",
        {
            "sub_agents/uno.yaml": "name: uno\ninstruction: Pasa a dos.\ntools: [read_file]\n",
            "sub_agents/dos.yaml": "name: dos\ninstruction: Pasa a uno.\ntools: [read_file]\n",
        },
    ),
}


@pytest.mark.parametrize("caso", sorted(FALSOS_POSITIVOS))
def test_falsos_positivos_ya_no_se_rechazan(tmp_path: Path, caso: str) -> None:
    agent_yaml, files = FALSOS_POSITIVOS[caso]
    assert_pasa(kit(tmp_path, agent_yaml, files))


def test_los_falsos_positivos_son_diez() -> None:
    assert len(FALSOS_POSITIVOS) == 10


def test_los_pares_de_sub_agents_no_se_extienden_a_quien_no_comparte_lista(tmp_path: Path) -> None:
    # `dos` está en otra rama (la declara `uno` con agent_tool): no es par de `tres`, que cuelga del principal
    root = kit(
        tmp_path,
        "name: a\ninstruction: ok\ntools: [read_file]\nsub_agents:\n  - config_path: sub_agents/tres.yaml\n"
        "  - config_path: sub_agents/uno.yaml\n",
        {
            "sub_agents/uno.yaml": "name: uno\ninstruction: ok\ntools:\n  - agent_tool:\n"
            "      config_path: sub_agents/dos.yaml\n",
            "sub_agents/dos.yaml": "name: dos\ninstruction: ok\ntools: [read_file]\n",
            "sub_agents/tres.yaml": "name: tres\ninstruction: Transfiere a dos.\ntools: [read_file]\n",
        },
    )
    ok, msgs = check_tool_references(root)
    assert ok is False
    assert "dos" in errors(msgs)[0]


# --- skills ----------


def test_el_skill_md_de_una_skill_declarada_se_lee(tmp_path: Path) -> None:
    root = kit(
        tmp_path,
        "name: a\ninstruction: ok\ntools: [read_file]\nskills:\n  - skills/buscar\n",
        {"skills/buscar/SKILL.md": "---\nname: buscar\ndescription: d\n---\nUsa search_similar_code.\n"},
    )
    ok, msgs = check_tool_references(root)
    assert ok is False
    assert len(errors(msgs)) == 1
    assert "SKILL.md" in errors(msgs)[0] and "skills/buscar" in errors(msgs)[0]
    assert "línea 5" in errors(msgs)[0]


def test_skill_limpia_pasa_y_skill_inexistente_falla(tmp_path: Path) -> None:
    root = kit(
        tmp_path,
        "name: a\ninstruction: ok\ntools: [read_file]\nskills:\n  - skills/buscar\n",
        {"skills/buscar/SKILL.md": "Usa read_file.\n"},
    )
    assert_pasa(root)
    (root / "skills" / "buscar" / "SKILL.md").unlink()
    ok, msgs = check_tool_references(root)
    assert ok is False
    assert "SKILL.md" in errors(msgs)[0]


def test_limite_conocido_otros_archivos_de_la_skill_no_se_leen(tmp_path: Path) -> None:
    root = kit(
        tmp_path,
        "name: a\ninstruction: ok\ntools: [read_file]\nskills:\n  - skills/buscar\n",
        {
            "skills/buscar/SKILL.md": "Usa read_file.\n",
            "skills/buscar/references/guia.md": "Usa search_similar_code.\n",
        },
    )
    assert_pasa(root)  # si alguna vez se leen, esta prueba debe cambiar


# --- falla cerrado ----------


def test_sin_pyyaml_la_comprobacion_falla_y_lo_dice(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = kit(tmp_path, "name: a\ninstruction: ok\ntools: [read_file]\n")
    monkeypatch.setattr(kaggle_submission, "_yaml", None)
    ok, msgs = check_tool_references(root)
    assert ok is False
    assert len(errors(msgs)) == 1 and "PyYAML" in errors(msgs)[0] and "no pudo correr" in errors(msgs)[0]


@pytest.mark.parametrize(
    "contenido",
    [
        "name: a\ninstruction: [sin cerrar\n",  # YAML mal formado
        "- name: a\n- name: b\n",  # no es un mapa
        "name: a\ninstruction: !include falta.md\n",  # include inexistente
        "name: a\ninstruction: {x: 1}\ntools: [read_file]\n",  # instruction no es texto
        "name: a\ntools: [read_file]\n",  # agente LlmAgent sin instruction
        "name: a\ninstruction: ok\ntools: read_file\n",  # tools no es lista
        "name: a\ninstruction: ok\ntools: [{no_es: agente}]\n",  # elemento de tools que no se sabe leer
        "name: a\nagent_class: AgenteRaro\ninstruction: ok\n",  # clase desconocida
        "name: a\ninstruction: ok\nsub_agents: [{otra: cosa}]\n",  # sub_agents sin config_path
    ],
)
def test_lo_que_no_se_puede_interpretar_es_error_y_no_un_pase(tmp_path: Path, contenido: str) -> None:
    root = kit(tmp_path, contenido)
    ok, msgs = check_tool_references(root)
    assert ok is False, msgs
    assert errors(msgs), msgs


def test_agentes_de_flujo_de_trabajo_no_necesitan_instruccion(tmp_path: Path) -> None:
    root = kit(
        tmp_path,
        "name: a\nagent_class: SequentialAgent\nsub_agents:\n  - config_path: sub_agents/h.yaml\n",
        {"sub_agents/h.yaml": "name: h\ninstruction: Lee con read_file.\ntools: [read_file]\n"},
    )
    assert_pasa(root)
    for clase in ("ParallelAgent", "LoopAgent"):
        (root / "agent.yaml").write_text(
            f"name: a\nagent_class: {clase}\nsub_agents:\n  - config_path: sub_agents/h.yaml\n",
            encoding="utf-8",
        )
        assert_pasa(root)


def test_un_agent_yaml_que_no_es_utf8_es_error_en_todas_las_vias(tmp_path: Path) -> None:
    root = kit(tmp_path / "kit", b"name: a\ninstruction: caf\xe9\ntools: [read_file]\n")
    ok, msgs = check_tool_references(root)
    assert ok is False
    assert "no es UTF-8" in errors(msgs)[0]
    ok, msgs = validate_submission_dir(root)  # no lanza UnicodeDecodeError
    assert ok is False
    assert any("no es UTF-8" in m for m in errors(msgs))

    import zipfile

    zpath = tmp_path / "x.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("agent.yaml", b"name: a\ninstruction: caf\xe9\n")
        zf.writestr("eval_config.yaml", "timeout: 1\n")
    ok, msgs, _, _ = verify_zip_submission(zpath)
    assert ok is False
    assert any("no es UTF-8" in m for m in errors(msgs))
    assert main(["verify", str(zpath)]) == EXIT_INVALID


# --- mención en negativo ----------


NEGATIVA = "La búsqueda por similitud (`search_similar_code`) no está disponible: usa `read_file`.\n"


def test_la_mencion_en_negativo_sigue_siendo_error_por_defecto(tmp_path: Path) -> None:
    # Decisión: la regla es estricta. Nombrar una herramienta ausente, aunque sea para negarla, es un riesgo
    # (el modelo puede intentarla), y detectar negaciones por el lenguaje no es fiable.
    root = kit(tmp_path, "name: a\ninstruction: !include p.md\ntools: [read_file]\n", {"p.md": NEGATIVA})
    ok, msgs = check_tool_references(root)
    assert ok is False
    assert len(errors(msgs)) == 1
    assert "--permitir-mencion" in errors(msgs)[0]  # y el mensaje dice cómo declararlo


def test_permitir_mencion_lo_deja_pasar_con_aviso_por_aparicion(tmp_path: Path) -> None:
    root = kit(
        tmp_path,
        "name: a\ninstruction: !include p.md\ntools: [read_file]\n",
        {"p.md": NEGATIVA + "Tampoco uses search_similar_code.\n"},
    )
    ok, msgs = check_tool_references(root, permitir_mencion=frozenset({"search_similar_code"}))
    assert ok is True, msgs
    assert errors(msgs) == []
    avisos = [m for m in msgs if m.startswith("[AVISO]") and "--permitir-mencion" in m]
    assert len(avisos) == 2  # una por cada línea donde aparece el nombre
    assert "línea 1" in avisos[0] and "línea 2" in avisos[1]
    assert not any(m.startswith("[OK]") for m in msgs)  # con menciones permitidas no se da por limpio


def test_permitir_mencion_solo_exime_a_la_herramienta_nombrada(tmp_path: Path) -> None:
    root = kit(
        tmp_path,
        "name: a\ninstruction: !include p.md\ntools: [read_file]\n",
        {"p.md": NEGATIVA + "Usa get_code_subgraph.\n"},
    )
    ok, msgs = check_tool_references(root, permitir_mencion=frozenset({"search_similar_code"}))
    assert ok is False
    assert len(errors(msgs)) == 1 and "get_code_subgraph" in errors(msgs)[0]


def test_permitir_mencion_con_un_nombre_desconocido_falla(tmp_path: Path) -> None:
    root = kit(tmp_path, "name: a\ninstruction: ok\ntools: [read_file]\n")
    ok, msgs = check_tool_references(root, permitir_mencion=frozenset({"inventada"}))
    assert ok is False
    assert "--permitir-mencion" in errors(msgs)[0]


def test_cli_permitir_mencion(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(kaggle_submission, "compile_with_adk", lambda _d: (True, "simulado"))
    root = kit(
        tmp_path / "k", "name: a\ninstruction: !include p.md\ntools: [read_file]\n", {"p.md": NEGATIVA}
    )
    zpath = tmp_path / "k.zip"
    # el kit con la mención no empaqueta (la regla es estricta); se arma el zip a mano
    import zipfile

    with zipfile.ZipFile(zpath, "w") as zf:
        for f in root.rglob("*"):
            if f.is_file():
                zf.write(f, f.relative_to(root).as_posix())
    assert main(["verify", str(zpath)]) == EXIT_INVALID
    assert main(["verify", str(zpath), "--permitir-mencion", "search_similar_code"]) == EXIT_OK
    assert main(["verify", str(zpath), "--permitir-mencion", "inventada"]) == EXIT_INVALID
    assert main(["verify", str(zpath), "--permitir-mencion", " , "]) == EXIT_INPUTS
    with pytest.raises(ValueError):
        pack_submission(root, tmp_path / "no.zip")


# --- errores de entrada de --sin-resultados ----------


def test_sin_resultados_con_una_ruta_inexistente_es_error_de_entrada(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(kaggle_submission, "compile_with_adk", lambda _d: (True, "simulado"))
    root = kit(tmp_path / "k", "name: a\ninstruction: ok\ntools: [read_file]\n")
    zpath = tmp_path / "k.zip"
    pack_submission(root, zpath)
    for valor in ("no_existe.json", "carpeta/no_existe", "C:\\nada\\no_existe.json", ""):
        assert main(["verify", str(zpath), "--sin-resultados", valor]) == EXIT_INPUTS, valor
    with pytest.raises(FileNotFoundError):
        parse_sin_resultados("no_existe.json")


def test_json_con_lista_vacia_se_distingue_de_no_poder_leer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(kaggle_submission, "compile_with_adk", lambda _d: (True, "simulado"))
    root = kit(tmp_path / "k", "name: a\ninstruction: ok\ntools: [read_file]\n")
    zpath = tmp_path / "k.zip"
    pack_submission(root, zpath)
    vacio = tmp_path / "vacio.json"
    vacio.write_text(json.dumps({"sin_resultados": []}), encoding="utf-8")
    assert parse_sin_resultados(str(vacio)) == frozenset()
    assert main(["verify", str(zpath), "--sin-resultados", str(vacio)]) == EXIT_OK
    out = capsys.readouterr().out
    assert "lista vacía" in out and "Sin --sin-resultados" not in out
    # sin el parámetro, otro mensaje; con un JSON ilegible, error de entrada
    assert main(["verify", str(zpath)]) == EXIT_OK
    assert "Sin --sin-resultados" in capsys.readouterr().out
    roto = tmp_path / "roto.json"
    roto.write_text("{no es json", encoding="utf-8")
    assert main(["verify", str(zpath), "--sin-resultados", str(roto)]) == EXIT_INPUTS


# --- pruebas que faltaban ----------


def test_el_nombre_propio_de_un_subagente_en_su_instruccion_no_es_error(tmp_path: Path) -> None:
    root = kit(
        tmp_path,
        "name: a\ninstruction: ok\ntools:\n  - agent_tool:\n      config_path: sub_agents/h.yaml\n",
        {"sub_agents/h.yaml": "name: helper\ninstruction: Eres helper.\ntools: [read_file]\n"},
    )
    assert_pasa(root)


def test_lista_en_flujo_cuenta_cada_error_y_cada_herramienta(tmp_path: Path) -> None:
    root = kit(
        tmp_path,
        "name: a\ninstruction: !include p.md\ntools: [read_file, edit_file]\n",
        {"p.md": "Usa search_similar_code, get_code_subgraph y get_code_neighbors.\n"},
    )
    ok, msgs = check_tool_references(root)
    assert ok is False
    assert len(errors(msgs)) == 3
    root2 = kit(
        tmp_path / "otro",
        "name: a\ninstruction: !include p.md\ntools: [read_file, edit_file]\n",
        {"p.md": "Usa edit_file y read_file.\n"},
    )
    assert_pasa(root2)


def test_agent_tool_sin_config_path_es_error(tmp_path: Path) -> None:
    root = kit(
        tmp_path, "name: a\ninstruction: ok\ntools:\n  - agent_tool:\n      skip_summarization: true\n"
    )
    ok, msgs = check_tool_references(root)
    assert ok is False
    assert "config_path" in errors(msgs)[0]


def test_subagente_que_cita_a_otro_con_ruta_relativa_a_la_raiz(tmp_path: Path) -> None:
    root = kit(
        tmp_path,
        "name: a\ninstruction: ok\ntools:\n  - agent_tool:\n      config_path: sub_agents/uno.yaml\n",
        {
            "sub_agents/uno.yaml": "name: uno\ninstruction: ok\ntools:\n  - agent_tool:\n"
            "      config_path: sub_agents/otros/dos.yaml\n",
            "sub_agents/otros/dos.yaml": "name: dos\ninstruction: Localiza con search_similar_code.\n"
            "tools: [read_file]\n",
        },
    )
    assert_falla_por_search(root)  # alcanzó al nieto citado desde la raíz del envío


def test_config_path_con_traversal_o_absoluto_es_error(tmp_path: Path) -> None:
    for cfg in ("../fuera.yaml", "/abs/h.yaml", "C:/abs/h.yaml"):
        root = kit(
            tmp_path / cfg.replace("/", "_").replace(":", "_").replace(".", "_"),
            f'name: a\ninstruction: ok\ntools:\n  - agent_tool:\n      config_path: "{cfg}"\n',
        )
        ok, msgs = check_tool_references(root)
        assert ok is False, cfg
        assert "sale del envío" in errors(msgs)[0]


def test_item_de_tools_entre_comillas(tmp_path: Path) -> None:
    root = kit(
        tmp_path,
        "name: a\ninstruction: !include p.md\ntools:\n  - \"read_file\"\n  - 'edit_file'\n",
        {"p.md": "Usa read_file y edit_file.\n"},
    )
    assert_pasa(root)
    (root / "p.md").write_text("Usa submit_patch.\n", encoding="utf-8")
    ok, msgs = check_tool_references(root)
    assert ok is False and "submit_patch" in errors(msgs)[0]


def test_la_linea_del_error_es_la_de_la_primera_aparicion_en_el_texto(tmp_path: Path) -> None:
    # con PyYAML el número de línea es el del texto de la instrucción (no el del YAML), y se mantiene
    root = kit(
        tmp_path,
        "name: a\ninstruction: !include p.md\ntools: [read_file]\n",
        {"p.md": "Uno.\nDos con search_similar_code.\nTres con search_similar_code otra vez.\n"},
    )
    ok, msgs = check_tool_references(root)
    assert ok is False
    assert len(errors(msgs)) == 1
    assert "línea 2" in errors(msgs)[0]


def test_dos_includes_anidados_y_include_con_extension_no_permitida(tmp_path: Path) -> None:
    root = kit(
        tmp_path,
        "name: a\ninstruction: !include p.md\ntools: [read_file]\n",
        {"p.md": CLEAN},
    )
    assert_pasa(root)
    _write(root / "agent.yaml", "name: a\ninstruction: !include datos.json\ntools: [read_file]\n")
    _write(root / "datos.json", "{}")
    ok, msgs = check_tool_references(root)
    assert ok is False
    assert ".md, .txt, .yaml y .yml" in errors(msgs)[0]
    # un .yaml incluido se interpreta como YAML: su instrucción incluida se sigue
    _write(root / "agent.yaml", "name: a\ninstruction: !include cuerpo.yaml\ntools: [read_file]\n")
    _write(root / "cuerpo.yaml", "!include p.md\n")
    assert_pasa(root)


# --- issue #177: el permiso no tapa órdenes, padres, y pruebas que faltaban ----------

TRES_MENCIONES = (
    "La búsqueda `search_similar_code` no está disponible.\nUsa read_file.\n\n"
    "Llama a search_similar_code con la consulta.\nLuego search_similar_code otra vez.\n"
)


def test_permitir_mencion_avisa_por_cada_linea_y_no_imprime_ok(tmp_path: Path) -> None:
    root = kit(
        tmp_path, "name: a\ninstruction: !include p.md\ntools: [read_file]\n", {"p.md": TRES_MENCIONES}
    )
    ok, msgs = check_tool_references(root, permitir_mencion=frozenset({"search_similar_code"}))
    assert ok is True, msgs
    avisos = [m for m in msgs if m.startswith("[AVISO]") and "--permitir-mencion" in m]
    assert [("línea 1" in m, "línea 4" in m, "línea 5" in m) for m in avisos] == [
        (True, False, False),
        (False, True, False),
        (False, False, True),
    ]
    assert not any(m.startswith("[OK]") and "'a'" in m for m in msgs)


PADRE_Y_TIO = {
    "sub_agents/padre.yaml": "name: padre\ninstruction: ok\ntools: [read_file]\nsub_agents:\n"
    "  - config_path: sub_agents/hijo.yaml\n",
    "sub_agents/tio.yaml": "name: tio\ninstruction: ok\ntools: [read_file]\n",
}
RAIZ_PADRE_Y_TIO = (
    "name: raiz\ninstruction: ok\ntools: [read_file]\nsub_agents:\n"
    "  - config_path: sub_agents/padre.yaml\n  - config_path: sub_agents/tio.yaml\n"
)


def test_un_hijo_puede_nombrar_al_padre_que_lo_declara(tmp_path: Path) -> None:
    files = {
        **PADRE_Y_TIO,
        "sub_agents/hijo.yaml": "name: hijo\ninstruction: Vuelve a padre.\ntools: [read_file]\n",
    }
    assert_pasa(kit(tmp_path, RAIZ_PADRE_Y_TIO, files))


def test_un_nieto_no_puede_nombrar_a_un_tio(tmp_path: Path) -> None:
    files = {
        **PADRE_Y_TIO,
        "sub_agents/hijo.yaml": "name: hijo\ninstruction: Pasa a tio.\ntools: [read_file]\n",
    }
    ok, msgs = check_tool_references(kit(tmp_path, RAIZ_PADRE_Y_TIO, files))
    assert ok is False
    assert "tio" in errors(msgs)[0]


def test_validate_submission_dir_pasa_el_permiso(tmp_path: Path) -> None:
    root = kit(tmp_path, "name: a\ninstruction: !include p.md\ntools: [read_file]\n", {"p.md": NEGATIVA})
    ok, _ = validate_submission_dir(root)
    assert ok is False
    ok, msgs = validate_submission_dir(root, permitir_mencion=frozenset({"search_similar_code"}))
    assert errors(msgs) == [], msgs
    assert any(m.startswith("[AVISO]") and "--permitir-mencion" in m for m in msgs)


def test_instruction_numerica_sin_name_es_error(tmp_path: Path) -> None:
    root = kit(tmp_path, "instruction: 5\ntools: [read_file]\n")
    ok, msgs = check_tool_references(root)
    assert ok is False
    assert "sin `instruction` de texto" in errors(msgs)[0]


def test_config_path_con_puntos_que_queda_dentro_del_envio_es_error(tmp_path: Path) -> None:
    # difiere del compilador, que lo aceptaría: la regla lo rechaza por estricta
    root = kit(
        tmp_path,
        'name: a\ninstruction: ok\ntools:\n  - agent_tool:\n      config_path: "sub_agents/../h.yaml"\n',
        {"h.yaml": "name: h\ninstruction: ok\ntools: [read_file]\n"},
    )
    ok, msgs = check_tool_references(root)
    assert ok is False
    assert "sale del envío" in errors(msgs)[0]


def test_enlaces_simbolicos_son_error(tmp_path: Path) -> None:
    real = tmp_path / "real.yaml"
    real.write_text("name: h\ninstruction: ok\ntools: [read_file]\n", encoding="utf-8")
    root = kit(
        tmp_path / "kit",
        "name: a\ninstruction: ok\ntools:\n  - agent_tool:\n      config_path: enlace.yaml\n",
    )
    try:
        (root / "enlace.yaml").symlink_to(real)
    except (OSError, NotImplementedError):
        pytest.skip("este sistema no permite crear enlaces simbólicos")
    ok, msgs = check_tool_references(root)
    assert ok is False
    assert "sale del envío" in errors(msgs)[0]
