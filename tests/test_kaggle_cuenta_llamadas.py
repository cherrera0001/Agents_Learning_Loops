"""Tests de `scripts/kaggle_cuenta_llamadas.py`. Trazas sintéticas, pequeñas y definidas aquí: no usan la red,
ni los datos reales, ni los episodios."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any

import pytest

from scripts import kaggle_cuenta_llamadas as kc
from scripts import kaggle_rescate_y_cuenta as ryc

P = kc.PRINCIPAL
S = kc.SUBAGENTE
ID_DE_TAREA = "proyecto_1234"  # con la forma de un identificador de tarea; no debe salir en el agregado


def ok(**kw: Any) -> str:
    return json.dumps({"status": "ok", **kw})


def llamada(nombre: str, args: dict[str, Any], obs: str | None, autor: str = P) -> dict[str, Any]:
    return {"nombre": nombre, "args": args, "obs": obs, "autor": autor}


def paso(nombre: str, args: dict[str, Any], obs: str | None, autor: str = P, id_: int = 3) -> dict[str, Any]:
    p: dict[str, Any] = {
        "step_id": id_,
        "source": "agent",
        "tool_calls": [{"function_name": nombre, "arguments": args, "extra": {"author": autor}}],
    }
    if obs is not None:
        p["observation"] = {"content": obs, "extra": {"tool_name": nombre, "author": autor}}
    return p


def traza(pasos: list[dict[str, Any]], minutos: float = 4.0, tope: int = 40) -> dict[str, Any]:
    enunciado = (
        f"Enunciado.\n## Task Budget\n- Time allowance: {minutos} minutes\n"
        f"- Tool calls allowance: {tope} calls\n- Max loop iterations: 100 turns\n"
    )
    return {
        "steps": [
            {"step_id": 1, "source": "system", "message": "x", "extra": {"event_type": "system_instruction"}},
            {"step_id": 2, "source": "user", "message": enunciado, "extra": {"event_type": "task_prompt"}},
            *pasos,
        ]
    }


def resultado(**kw: Any) -> dict[str, Any]:
    base = {
        "task_id": ID_DE_TAREA,
        "resolved": False,
        "duration_seconds": 30.0,
        "error_message": None,
        "tool_calls": 0,
    }
    return {**base, **kw}


LEER = ok(filepath="a.py", content="x", is_truncated=False)


# ---------------------------------------------------------------------------
# Qué devolvió cada llamada
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("nombre", "obs", "clase"),
    [
        ("read_file", LEER, "con_contenido"),
        ("read_file", ok(filepath="a.py", content="x", is_truncated=True), "lectura_truncada"),
        ("read_file", None, "sin_observacion"),
        (
            "edit_file",
            json.dumps({"error": "Missing mandatory input parameters: old_string"}),
            "rechazada_por_esquema",
        ),
        (
            "run_command",
            json.dumps({"status": "error", "error_type": "BudgetExceeded"}),
            "rechazada_por_presupuesto",
        ),
        (
            "run_command",
            json.dumps({"status": "error", "error_type": "CommandError", "details": {}}),
            "error",
        ),
        ("run_command", ok(stdout="", stderr="", exit_code=0), "orden_sin_salida"),
        ("run_command", ok(stdout="hola", stderr="", exit_code=0), "con_contenido"),
        ("search_similar_code", ok(query="q", results=[], count=0), "vacia"),
        ("search_similar_code", ok(query="q", results=["n1"], count=1), "con_contenido"),
        ("get_code_neighbors", ok(node="n", neighbors=[], count=0), "vacia"),
        (
            "search_similar_code",
            json.dumps({"status": "error", "error_type": "X", "error_message": "m"}),
            "error",
        ),
    ],
)
def test_clase_de_lo_que_devolvio_cada_llamada(nombre: str, obs: str | None, clase: str) -> None:
    assert kc.clase_de(llamada(nombre, {}, obs)) == clase


def test_una_busqueda_con_error_no_cuenta_como_vacia() -> None:
    sesion = kc.contar_sesion(
        traza(
            [
                paso("search_similar_code", {"query": "a"}, ok(results=[], count=0), id_=3),
                paso(
                    "search_similar_code",
                    {"query": "b"},
                    json.dumps({"status": "error", "error_type": "E"}),
                    id_=4,
                ),
            ]
        ),
        resultado(),
        None,
    )
    assert sesion["busquedas_por_similitud_principal"] == 2
    assert sesion["busquedas_por_similitud_vacias_principal"] == 1


def test_emparejamiento_la_observacion_es_de_la_llamada_con_su_nombre() -> None:
    delegacion = {"function_name": S, "arguments": {}, "extra": {"author": P}}
    busqueda = {"function_name": "search_similar_code", "arguments": {"query": "q"}, "extra": {"author": S}}
    el_paso = {
        "source": "agent",
        "tool_calls": [delegacion, busqueda],
        "observation": {
            "content": ok(results=[], count=0),
            "extra": {"tool_name": "search_similar_code", "author": S},
        },
    }
    ll = kc.llamadas_de({"steps": [el_paso]})
    assert [x["nombre"] for x in ll] == [S, "search_similar_code"]
    assert ll[0]["obs"] is None  # la delegación quedó sin respuesta
    assert ll[1]["obs"] is not None and kc.clase_de(ll[1]) == "vacia"
    assert kc.clase_de(ll[0]) == "sin_observacion"


def test_el_autor_sale_de_la_llamada_y_no_del_paso() -> None:
    delegacion = {"function_name": S, "arguments": {}, "extra": {"author": P}}
    busqueda = {"function_name": "search_similar_code", "arguments": {}, "extra": {"author": S}}
    el_paso = {"source": "agent", "extra": {"author": P}, "tool_calls": [delegacion, busqueda]}
    sesion = kc.contar_sesion({"steps": [el_paso]}, resultado(), None)
    assert sesion["registradas_principal"] == 1
    assert sesion["registradas_subagente"] == 1


# ---------------------------------------------------------------------------
# Registradas y contadas
# ---------------------------------------------------------------------------


def test_registradas_y_contadas_por_el_arnes() -> None:
    pasos = [
        paso("read_file", {"filepath": "a.py"}, LEER, id_=3),  # cuenta
        paso("submit_patch", {}, ok(patch_size=1), id_=4),  # no cuenta
        paso("get_status", {}, ok(), id_=5),  # no cuenta
        paso(S, {}, None, id_=6),  # delegación: no cuenta
        paso("search_similar_code", {"query": "q"}, ok(results=[], count=0), autor=S, id_=7),  # cuenta
        paso(
            "edit_file",
            {"filepath": "a.py", "bad": 1},
            json.dumps({"error": "mandatory input parameters"}),
            id_=8,
        ),
        paso(
            "run_command",
            {"command": "ls"},
            json.dumps({"status": "error", "error_type": "BudgetExceeded"}),
            id_=9,
        ),
        paso("run_command", {"command": "ls"}, ok(stdout="x", stderr="", exit_code=0), id_=10),  # cuenta
    ]
    s = kc.contar_sesion(traza(pasos), resultado(tool_calls=3), None)
    assert s["registradas_principal"] == 7
    assert s["registradas_subagente"] == 1
    assert s["contadas"] == 3
    assert s["contadas_segun_el_arnes"] == 3
    assert s["rechazadas_sin_ejecutar"] == 2
    assert s["por_salida_principal"]["rechazada_por_esquema"] == 1
    assert s["por_salida_principal"]["rechazada_por_presupuesto"] == 1
    assert s["por_salida_subagente"]["vacia"] == 1
    assert s["ediciones_rechazadas_por_esquema"] == 1


def test_una_llamada_del_subagente_no_se_cuenta_como_del_principal() -> None:
    pasos = [
        paso("read_file", {"filepath": "a.py"}, LEER, id_=3),
        paso("search_similar_code", {"query": "q"}, ok(results=[], count=0), autor=S, id_=4),
    ]
    s = kc.contar_sesion(traza(pasos), resultado(), None)
    assert (s["registradas_principal"], s["registradas_subagente"]) == (1, 1)
    assert s["busquedas_por_similitud_principal"] == 0
    assert s["busquedas_por_similitud_subagente"] == 1
    assert s["busquedas_por_similitud_vacias_subagente"] == 1


# ---------------------------------------------------------------------------
# Argumento mal formado
# ---------------------------------------------------------------------------


def test_lecturas_y_ediciones_con_argumento_mal_formado() -> None:
    pasos = [
        paso("read_file", {"filepath": "a.py", "start_line": 1, "end_line": 5}, LEER, id_=3),  # bien
        paso(
            "read_file", {"filepath": "a.py", 'start_line"': 1, "end_line": 5}, LEER, id_=4
        ),  # mal, ya pedido
        paso("read_file", {"filepath": "a.py", 'start_line"': 1, "end_line": 5}, LEER, id_=5),  # mal, repite
        paso("read_file", {"filepath": "b.py", 'start_line"': 7}, LEER, id_=6),  # mal, rango nuevo
        paso("edit_file", {"filepath": "a.py", "old_string": "a", 'new_string"': "b"}, ok(), id_=7),  # mal
        paso("edit_file", {"filepath": "a.py", "old_string": "a", "new_string": "b"}, ok(), id_=8),  # bien
    ]
    s = kc.contar_sesion(traza(pasos), resultado(), None)
    assert s["lecturas_con_argumento_mal_formado"] == 3
    assert s["lecturas_con_argumento_mal_formado_que_repiten_un_rango"] == 2
    assert s["ediciones_con_argumento_mal_formado"] == 1


def test_el_subagente_no_suma_a_las_lecturas_mal_formadas_del_principal() -> None:
    pasos = [paso("read_file", {"filepath": "a.py", "mal": 1}, LEER, autor=S)]
    s = kc.contar_sesion(traza(pasos), resultado(), None)
    assert s["lecturas_con_argumento_mal_formado"] == 0
    assert s["lecturas_con_argumento_mal_formado_subagente"] == 1


# ---------------------------------------------------------------------------
# Repetidas: tres definiciones
# ---------------------------------------------------------------------------

EDITA = ok(filepath="a.py", strategy="exact")


def test_repetida_cada_definicion_con_su_nombre() -> None:
    pasos = [
        paso("run_command", {"command": "A"}, ok(stdout="1", stderr="", exit_code=0), id_=3),
        paso(
            "run_command", {"command": "A"}, ok(stdout="2", stderr="", exit_code=0), id_=4
        ),  # repite, otra salida
        paso("edit_file", {"filepath": "a.py", "old_string": "x", "new_string": "y"}, EDITA, id_=5),
        paso(
            "run_command", {"command": "A"}, ok(stdout="1", stderr="", exit_code=0), id_=6
        ),  # tras la edición
        paso(
            "run_command", {"command": "B"}, ok(stdout="1", stderr="", exit_code=0), id_=7
        ),  # otro argumento
    ]
    s = kc.contar_sesion(traza(pasos), resultado(), None)
    assert s["repetida_por_nombre_y_argumentos"] == 2  # las llamadas 2 y 4
    assert s["repetida_sin_edicion_entre_medias"] == 1  # la 4 ya no: hubo una edición
    assert s["repetida_con_la_misma_salida"] == 1  # solo la 4 repite también su salida ("1")


def test_repetida_distingue_los_argumentos_y_el_nombre() -> None:
    pasos = [
        paso("read_file", {"filepath": "a.py"}, LEER, id_=3),
        paso("read_file", {"filepath": "b.py"}, LEER, id_=4),
        paso("read_file", {"filepath": "a.py", "start_line": 1}, LEER, id_=5),
        paso("run_command", {"filepath": "a.py"}, ok(stdout="x", stderr="", exit_code=0), id_=6),
    ]
    s = kc.contar_sesion(traza(pasos), resultado(), None)
    assert s["repetida_por_nombre_y_argumentos"] == 0


def test_repetida_solo_contadas_y_con_subagente() -> None:
    pasos = [
        paso("get_status", {}, ok(), id_=3),
        paso("get_status", {}, ok(), id_=4),  # repetida, pero no cuenta contra el tope
        paso("run_command", {"command": "A"}, ok(stdout="x", stderr="", exit_code=0), id_=5),
        paso("run_command", {"command": "A"}, ok(stdout="x", stderr="", exit_code=0), autor=S, id_=6),
    ]
    s = kc.contar_sesion(traza(pasos), resultado(), None)
    assert s["repetida_por_nombre_y_argumentos"] == 1  # solo get_status: la segunda A es del subagente
    assert s["repetida_por_nombre_y_argumentos_solo_contadas"] == 0
    assert s["repetida_por_nombre_y_argumentos_con_subagente"] == 2


def test_la_edicion_rechazada_no_olvida_lo_visto() -> None:
    rechazada = json.dumps({"error": "mandatory input parameters"})
    pasos = [
        paso("run_command", {"command": "A"}, ok(stdout="x", stderr="", exit_code=0), id_=3),
        paso("edit_file", {"filepath": "a.py"}, rechazada, id_=4),
        paso("run_command", {"command": "A"}, ok(stdout="x", stderr="", exit_code=0), id_=5),
    ]
    assert kc.contar_sesion(traza(pasos), resultado(), None)["repetida_sin_edicion_entre_medias"] == 1


# ---------------------------------------------------------------------------
# Edición de fuente, aviso y parche final
# ---------------------------------------------------------------------------


def parche(*archivos: tuple[str, bool]) -> str:
    nuevo_modo = "new file mode 100644\n"
    return "".join(
        f"diff --git a/{r} b/{r}\n{nuevo_modo if nuevo else ''}index 1..2\n@@ -1 +1 @@\n-x\n+y\n"
        for r, nuevo in archivos
    )


@pytest.mark.parametrize(
    ("archivos", "sin_edicion"),
    [
        ([], True),  # parche vacío
        ([("tests/test_a.py", False)], True),  # solo prueba
        ([("pkg/nuevo.py", True)], True),  # solo archivo nuevo
        ([("conftest.py", False)], True),
        ([("pkg/a.py", False)], False),
        ([("tests/test_a.py", False), ("pkg/a.py", False)], False),
    ],
)
def test_sin_edicion_de_fuente_se_cuenta_por_el_parche_final(
    archivos: list[tuple[str, bool]], sin_edicion: bool
) -> None:
    # Aunque el agente editó con éxito durante la sesión, manda el parche final.
    pasos = [paso("edit_file", {"filepath": "pkg/a.py", "old_string": "x", "new_string": "y"}, EDITA)]
    s = kc.contar_sesion(traza(pasos), resultado(), parche(*archivos))
    assert s["sin_edicion_de_fuente"] is sin_edicion
    assert s["parche_vacio"] is (not archivos)


def test_llamadas_antes_de_la_primera_edicion_de_fuente_y_despues_del_aviso() -> None:
    aviso = json.dumps(
        {"status": "ok", "stdout": "x", "stderr": "", "budget_warning": "Only 10 call(s) remaining"}
    )
    pasos = [
        paso("read_file", {"filepath": "pkg/a.py"}, LEER, id_=3),
        paso("submit_patch", {}, ok(patch_size=0), id_=4),  # no cuenta
        paso(
            "edit_file", {"filepath": "tests/test_a.py", "old_string": "x", "new_string": "y"}, EDITA, id_=5
        ),
        paso(
            "edit_file",
            {"filepath": "/workspace/pkg/a.py", "old_string": "x", "new_string": "y"},
            EDITA,
            id_=6,
        ),
        paso("run_command", {"command": "pytest"}, aviso, id_=7),
        paso("read_file", {"filepath": "pkg/a.py"}, LEER, id_=8),
        paso("read_file", {"filepath": "pkg/b.py"}, LEER, id_=9),
    ]
    s = kc.contar_sesion(traza(pasos), resultado(), parche(("pkg/a.py", False)))
    assert (
        s["antes_de_la_primera_edicion_de_fuente"] == 3
    )  # lectura, edición de prueba y la edición de fuente
    assert s["aviso_de_presupuesto_en_la_llamada"] == 4
    assert s["despues_del_aviso"] == 2
    assert s["registradas_tras_el_aviso"] == 2
    assert s["ediciones_ejecutadas"] == 2
    assert s["llamadas_antes_de_la_primera_edicion_ejecutada"] == 2  # la entrega sí está registrada


def test_sesion_sin_edicion_ejecutada_cuenta_todas_sus_llamadas() -> None:
    pasos = [paso("read_file", {"filepath": "a.py"}, LEER, id_=3), paso("get_status", {}, ok(), id_=4)]
    s = kc.contar_sesion(traza(pasos), resultado(), None)
    assert s["sin_edicion_ejecutada"] is True
    assert s["llamadas_antes_de_la_primera_edicion_ejecutada"] == 2
    assert s["antes_de_la_primera_edicion_de_fuente"] is None
    assert s["aviso_de_presupuesto_en_la_llamada"] is None


# ---------------------------------------------------------------------------
# Sin avance
# ---------------------------------------------------------------------------


def test_sin_avance_es_una_union_sin_doble_conteo() -> None:
    pasos = [
        paso("run_command", {"command": "A"}, ok(stdout="x", stderr="", exit_code=0), id_=3),  # útil
        paso("run_command", {"command": "A"}, ok(stdout="x", stderr="", exit_code=0), id_=4),  # repetida
        paso("search_similar_code", {"query": "q"}, ok(results=[], count=0), id_=5),  # vacía
        paso("search_similar_code", {"query": "q"}, ok(results=[], count=0), id_=6),  # vacía Y repetida
        paso("read_file", {"filepath": "a.py", "mal": 1}, LEER, id_=7),  # lectura mal formada
        paso(
            "search_similar_code", {"query": "z"}, ok(results=[], count=0), autor=S, id_=8
        ),  # subagente y vacía
        paso("edit_file", {"filepath": "a.py"}, json.dumps({"error": "mandatory input parameters"}), id_=9),
        paso("submit_patch", {}, ok(), id_=10),
        paso("submit_patch", {}, ok(), id_=11),  # la entrega repetida no es sin avance
        paso("read_file", {"filepath": "z.py"}, LEER, autor=S, id_=12),  # del subagente, con contenido
    ]
    s = kc.contar_sesion(traza(pasos), resultado(), None)
    # 2.ª A, 2 búsquedas del principal, lectura mal formada, 2 llamadas del subagente, rechazada
    assert s["sin_avance_sobre_la_traza"] == 7
    assert s["sin_avance_sobre_las_contadas"] == 6  # sin la rechazada


# ---------------------------------------------------------------------------
# Cortes
# ---------------------------------------------------------------------------


def test_limites_se_leen_del_enunciado_de_la_traza() -> None:
    assert kc.limites_de(traza([], minutos=4.5, tope=60)) == (270.0, 60)
    assert kc.limites_de({"steps": []}) == (None, None)


@pytest.mark.parametrize(
    ("mensaje", "marca"),
    [
        (None, ""),
        ("Agent exceeded session timeout (4 min)", "tiempo"),
        ("Agent exceeded tool call budget (40 calls)", "llamadas"),
        ("Sandbox execution error: ContextWindowExceededError", "contexto"),
        ("otra cosa", "otra"),
    ],
)
def test_marca_de_corte_del_arnes(mensaje: str | None, marca: str) -> None:
    assert kc.marca_de_corte(mensaje) == marca


def test_cortes_marca_duracion_y_tope_sin_entrega() -> None:
    uno = [paso("read_file", {"filepath": "a.py"}, LEER)]
    con_marca = kc.contar_sesion(
        traza(uno), resultado(error_message="Agent exceeded session timeout (4 min)"), None
    )
    assert con_marca["marca_de_corte"] == "tiempo" and con_marca["corte"] is True
    # una tarea resuelta pierde la marca (verification.py:556) pero pasó el límite: es un corte
    resuelta_larga = kc.contar_sesion(traza(uno), resultado(resolved=True, duration_seconds=241.0), None)
    assert resuelta_larga["marca_de_corte"] == ""
    assert resuelta_larga["paso_el_limite_de_tiempo"] is True and resuelta_larga["corte"] is True
    en_el_limite = kc.contar_sesion(traza(uno), resultado(duration_seconds=239.9), None)
    assert en_el_limite["corte"] is False
    justo = kc.contar_sesion(traza(uno), resultado(duration_seconds=240.0), None)
    assert justo["paso_el_limite_de_tiempo"] is True  # «mayor o igual que el límite»
    pasos = [paso("read_file", {"filepath": f"{i}.py"}, LEER, id_=3 + i) for i in range(3)]
    sin_entrega = kc.contar_sesion(traza(pasos, tope=3), resultado(), None)
    assert sin_entrega["llego_al_tope_sin_entrega"] is True and sin_entrega["corte"] is True
    con_entrega = kc.contar_sesion(
        traza([*pasos, paso("submit_patch", {}, ok(), id_=9)], tope=3), resultado(), None
    )
    assert con_entrega["llego_al_tope_sin_entrega"] is False and con_entrega["corte"] is False


# ---------------------------------------------------------------------------
# Parche
# ---------------------------------------------------------------------------


def test_archivos_del_parche_distingue_nuevos_y_pruebas() -> None:
    texto = parche(("pkg/a.py", False), ("pkg/b.py", True), ("tests/test_a.py", False), ("x_test.py", False))
    assert kc.archivos_del_parche(texto) == [
        ("pkg/a.py", False),
        ("pkg/b.py", True),
        ("tests/test_a.py", False),
        ("x_test.py", False),
    ]
    assert kc.fuente_modificada(texto) == ["pkg/a.py"]
    assert kc.fuente_modificada(None) == []


# ---------------------------------------------------------------------------
# Rescate completo: agregado sin identificadores, por tope, códigos de salida
# ---------------------------------------------------------------------------


def hacer_zip(ruta: Path, tareas: dict[str, tuple[dict[str, Any], dict[str, Any], str]]) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ruta, "w") as z:
        z.writestr("task_results.jsonl", "\n".join(json.dumps(r) for _, r, _ in tareas.values()) + "\n")
        for tarea, (t, _, p) in tareas.items():
            z.writestr(f"traces/trace_{tarea}.json", json.dumps(t))
            z.writestr(f"patches/{tarea}.patch", p)


def rescate_de_juguete(raiz: Path) -> Path:
    nb = raiz / "notebooks"
    t1 = [
        paso("run_command", {"command": "A"}, ok(stdout="x", stderr="", exit_code=0), id_=3 + i)
        for i in range(2)
    ]
    hacer_zip(
        nb / "uno" / "salida__crudo_a.zip",
        {"proyecto_1234": (traza(t1, 4.0, 40), resultado(task_id="proyecto_1234", tool_calls=2), "")},
    )
    t2 = [paso("search_similar_code", {"query": "q"}, ok(results=[], count=0))]
    hacer_zip(
        nb / "dos" / "salida__crudo_b.zip",
        {
            "proyecto_5678": (
                traza(t2, 4.5, 60),
                resultado(task_id="proyecto_5678", resolved=True, tool_calls=1),
                "",
            )
        },
    )
    return raiz


def test_el_agregado_no_lleva_identificadores_ni_texto_de_la_competencia(tmp_path: Path) -> None:
    rescate_de_juguete(tmp_path)
    agregado, detalle, _ = kc.cuenta_rescate(tmp_path)
    texto = json.dumps(agregado, ensure_ascii=False)
    for prohibido in (
        "proyecto_1234",
        "proyecto_5678",
        "proyecto",
        "a.py",
        "query",
        "Enunciado",
        "uno",
        "dos",
    ):
        assert prohibido not in texto
    assert {d["tarea"] for d in detalle} == {"proyecto_1234", "proyecto_5678"}  # el detalle sí los lleva
    assert agregado["sesiones"] == 2 and agregado["tareas"] == 2 and agregado["resueltas"] == 1


def test_el_agregado_va_tambien_separado_por_tope(tmp_path: Path) -> None:
    rescate_de_juguete(tmp_path)
    agregado, _, _ = kc.cuenta_rescate(tmp_path)
    assert sorted(agregado["por_tope_de_llamadas"]) == ["40", "60"]
    assert (
        agregado["por_tope_de_llamadas"]["40"]["repetidas_del_principal"]["repetida_por_nombre_y_argumentos"]
        == 1
    )
    assert (
        agregado["por_tope_de_llamadas"]["60"]["repetidas_del_principal"]["repetida_por_nombre_y_argumentos"]
        == 0
    )
    assert agregado["por_tope_de_llamadas"]["60"]["busquedas_por_similitud"]["vacias_principal"] == 1
    assert agregado["busquedas_por_similitud"]["vacias_principal"] == 1
    assert "traza" in agregado["fuente_del_conteo"] and "no se usan" in agregado["fuente_del_conteo"]


def test_salida_0_y_archivos_escritos(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rescate_de_juguete(tmp_path)
    assert kc.main(["--rescate", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out)["sesiones"] == 2
    assert json.loads((tmp_path / "cuenta_llamadas.json").read_text(encoding="utf-8"))["sesiones"] == 2
    detalle = json.loads((tmp_path / "cuenta_llamadas_detalle.json").read_text(encoding="utf-8"))
    assert len(detalle) == 2


def test_rescate_anidado_y_salida_2_sin_zips(tmp_path: Path) -> None:
    rescate_de_juguete(tmp_path / "2026-10-09T1342Z")
    assert kc.main(["--rescate", str(tmp_path)]) == 0  # una sola subcarpeta con notebooks/
    vacio = tmp_path / "vacio"
    (vacio / "notebooks" / "x").mkdir(parents=True)
    assert kc.main(["--rescate", str(vacio)]) == 5  # rescate válido sin trazas: nada que contar
    assert kc.main(["--rescate", str(tmp_path / "no_existe")]) == 2  # no hay rescate: entrada inválida


def test_un_zip_ilegible_da_salida_4(tmp_path: Path) -> None:
    rescate_de_juguete(tmp_path)
    (tmp_path / "notebooks" / "uno" / "salida__crudo_roto.zip").write_bytes(b"no es un zip")
    assert kc.main(["--rescate", str(tmp_path)]) == 4


def test_una_sesion_sin_traza_se_cuenta_y_da_salida_4(tmp_path: Path) -> None:
    ruta = tmp_path / "notebooks" / "uno" / "salida__crudo_a.zip"
    ruta.parent.mkdir(parents=True)
    with zipfile.ZipFile(ruta, "w") as z:
        z.writestr("task_results.jsonl", json.dumps(resultado(task_id="proyecto_1234")) + "\n")
    assert kc.main(["--rescate", str(tmp_path)]) == 4
    agregado = json.loads((tmp_path / "cuenta_llamadas.json").read_text(encoding="utf-8"))
    assert agregado["sesiones"] == 1 and agregado["sesiones_sin_traza"] == 1


def test_el_detalle_se_niega_a_quedar_en_una_carpeta_versionable(tmp_path: Path) -> None:
    rescate_de_juguete(tmp_path)
    versionable = Path(__file__).resolve().parent.parent / "docs" / "cuenta_de_prueba_detalle.json"
    try:
        assert kc.main(["--rescate", str(tmp_path), "--detalle", str(versionable)]) == 2
        assert not versionable.exists()
    finally:
        versionable.unlink(missing_ok=True)  # si la guarda fallara, no dejar el archivo en el árbol


def test_el_guion_de_rescate_y_cuenta_une_las_dos_ordenes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    carpeta = rescate_de_juguete(tmp_path / "2026-10-09T1342Z")

    def falso_rescate(argv: list[str] | None = None) -> int:
        print(json.dumps({"directorio": str(carpeta)}))
        return 4  # un rescate con faltantes sigue contando

    monkeypatch.setattr(ryc.kaggle_rescate, "main", falso_rescate)
    assert ryc.main(["--destino", "x"]) == 4
    assert "CUENTA POR LLAMADA" in capsys.readouterr().out
    assert (carpeta / "cuenta_llamadas.json").is_file()
    monkeypatch.setattr(ryc.kaggle_rescate, "main", lambda argv=None: 3)
    assert ryc.main(["--destino", "x"]) == 3  # Kaggle no respondió: no se cuenta


def test_los_zips_se_leen_en_memoria_y_no_se_extraen(tmp_path: Path) -> None:
    rescate_de_juguete(tmp_path)
    antes = sorted(p.name for p in tmp_path.rglob("*"))
    kc.cuenta_rescate(tmp_path)
    assert sorted(p.name for p in tmp_path.rglob("*")) == antes


# ---------------------------------------------------------------------------
# Revisión: contadores del agregado y ramas que no tenían prueba
# ---------------------------------------------------------------------------

UNA = [paso("read_file", {"filepath": "a.py"}, LEER)]


def test_resueltas_que_pasaron_el_limite_cuenta_solo_las_resueltas() -> None:
    larga = kc.contar_sesion(traza(UNA), resultado(resolved=True, duration_seconds=250.0), None)
    no_resuelta = kc.contar_sesion(traza(UNA), resultado(resolved=False, duration_seconds=250.0), None)
    corta = kc.contar_sesion(traza(UNA), resultado(resolved=True, duration_seconds=10.0), None)
    cortes = kc.agregar([larga, no_resuelta, corta], 1)["cortes"]
    assert cortes["resueltas_que_pasaron_el_limite"] == 1
    assert cortes["no_resueltas_sin_marca_que_pasaron_el_limite"] == 1
    assert cortes["con_marca_del_arnes"] == 0


def test_sin_edicion_de_fuente_de_ellas_resueltas() -> None:
    resuelta = kc.contar_sesion(traza(UNA), resultado(resolved=True), "")
    no_resuelta = kc.contar_sesion(traza(UNA), resultado(resolved=False), "")
    con_fuente = kc.contar_sesion(traza(UNA), resultado(resolved=True), parche(("pkg/a.py", False)))
    bloque = kc.agregar([resuelta, no_resuelta, con_fuente], 1)["sin_edicion_de_fuente"]
    assert bloque == {"por_el_parche_final": 2, "de_ellas_con_parche_vacio": 2, "de_ellas_resueltas": 1}


def test_sesiones_con_lecturas_mal_formadas_no_es_el_total_de_lecturas() -> None:
    mala = [paso("read_file", {"filepath": f"{i}.py", "mal": 1}, LEER, id_=3 + i) for i in range(3)]
    con_tres = kc.contar_sesion(traza(mala), resultado(), None)
    sin_ninguna = kc.contar_sesion(traza(UNA), resultado(), None)
    bloque = kc.agregar([con_tres, sin_ninguna], 1)["argumento_mal_formado"]
    assert (bloque["lecturas"], bloque["sesiones_con_lecturas"]) == (3, 1)


def test_el_estado_repetido_no_es_un_gasto_sin_avance() -> None:
    pasos = [
        paso("get_status", {}, ok(tool_calls_used=1), id_=3),
        paso("get_status", {}, ok(tool_calls_used=1), id_=4),
    ]
    s = kc.contar_sesion(traza(pasos), resultado(), None)
    assert s["repetida_por_nombre_y_argumentos"] == 1  # sí es repetida por nombre...
    assert s["sin_avance_sobre_la_traza"] == 0  # ...pero la entrega y el estado no cuentan como sin avance


def test_vacia_tambien_si_results_esta_vacio_y_no_hay_count() -> None:
    assert kc.clase_de(llamada("search_similar_code", {}, ok(query="q", results=[]))) == "vacia"
    assert kc.clase_de(llamada("search_similar_code", {}, ok(query="q", results=["n"]))) == "con_contenido"
    assert kc.clase_de(llamada("get_code_subgraph", {}, ok(nodes=[], results=[]))) == "vacia"
    # fuera de las herramientas de grafo, un resultado vacío no es «vacía»
    assert kc.clase_de(llamada("read_file", {}, ok(content="", results=[]))) == "con_contenido"


def _paso_con_dos(
    nombres_y_autores: list[tuple[str, str]], obs_nombre: str, obs_autor: str
) -> dict[str, Any]:
    return {
        "source": "agent",
        "tool_calls": [
            {"function_name": n, "arguments": {"i": i}, "extra": {"author": a}}
            for i, (n, a) in enumerate(nombres_y_autores)
        ],
        "observation": {"content": ok(r="x"), "extra": {"tool_name": obs_nombre, "author": obs_autor}},
    }


def test_emparejamiento_con_dos_llamadas_del_mismo_nombre_gana_la_del_autor_de_la_observacion() -> None:
    dos = [("read_file", P), ("read_file", S)]
    de_s = kc.llamadas_de({"steps": [_paso_con_dos(dos, "read_file", S)]})
    assert [x["obs"] is not None for x in de_s] == [False, True]
    de_p = kc.llamadas_de({"steps": [_paso_con_dos(dos, "read_file", P)]})
    assert [x["obs"] is not None for x in de_p] == [True, False]


def test_emparejamiento_sin_desempate_por_autor_gana_la_primera_candidata() -> None:
    dos = [("read_file", P), ("read_file", P)]
    ll = kc.llamadas_de({"steps": [_paso_con_dos(dos, "read_file", P)]})
    assert [x["obs"] is not None for x in ll] == [True, False]
    # un autor que ninguna tiene: se queda con la primera por nombre
    ll = kc.llamadas_de({"steps": [_paso_con_dos(dos, "read_file", "otro")]})
    assert [x["obs"] is not None for x in ll] == [True, False]
    # un nombre que ninguna tiene: la observación no se asigna
    ll = kc.llamadas_de({"steps": [_paso_con_dos(dos, "run_command", P)]})
    assert [x["obs"] for x in ll] == [None, None]


def test_new_file_mode_solo_cuenta_en_la_cabecera_del_bloque() -> None:
    # un archivo existente cuyo texto añadido contiene la frase no es un archivo nuevo
    texto = (
        "diff --git a/pkg/a.py b/pkg/a.py\nindex 1..2\n@@ -1 +1 @@\n-x\n+new file mode 100644\n"
        "diff --git a/pkg/b.py b/pkg/b.py\nnew file mode 100644\nindex 0..2\n@@ -0,0 +1 @@\n+y\n"
    )
    assert kc.archivos_del_parche(texto) == [("pkg/a.py", False), ("pkg/b.py", True)]
    assert kc.fuente_modificada(texto) == ["pkg/a.py"]


def test_un_miembro_del_zip_mas_grande_que_el_tope_no_se_lee(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rescate_de_juguete(tmp_path)
    monkeypatch.setattr(kc, "TOPE_MIEMBRO_BYTES", 200)  # la traza de juguete pesa más; task_results no
    agregado, detalle, _ = kc.cuenta_rescate(tmp_path)
    assert agregado["sesiones"] == 2 and agregado["sesiones_sin_traza"] == 2
    assert all(d["tiene_traza"] is False and d["registradas_principal"] == 0 for d in detalle)
    monkeypatch.setattr(kc, "TOPE_MIEMBRO_BYTES", 0)  # ni task_results.jsonl cabe: el zip no se puede leer
    agregado, _, problemas = kc.cuenta_rescate(tmp_path)
    assert problemas["zips_ilegibles"] == 2 and agregado["sesiones"] == 0


def test_la_salida_de_la_cuenta_se_fuerza_a_utf8(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rescate_de_juguete(tmp_path)
    visto: list[tuple[str, str]] = []

    class Consola:
        def reconfigure(self, encoding: str, errors: str) -> None:
            visto.append((encoding, errors))

        def write(self, s: str) -> int:
            return len(s)

        def flush(self) -> None:
            pass

    monkeypatch.setattr(kc.sys, "stdout", Consola())
    assert kc.main(["--rescate", str(tmp_path)]) == 0
    assert visto == [("utf-8", "replace")]


# --- la orden unida -------------------------------------------------------------------------------------


def test_la_orden_unida_distingue_no_pude_contar_de_nada_que_contar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    carpeta = rescate_de_juguete(tmp_path / "2026-10-09T1342Z")
    monkeypatch.setattr(
        ryc.kaggle_rescate, "main", lambda argv=None: print(json.dumps({"directorio": str(carpeta)})) or 0
    )
    # la cuenta sale 2 (no pudo escribir / carpeta versionable): código propio, no el del rescate
    monkeypatch.setattr(ryc.kaggle_cuenta_llamadas, "main", lambda argv=None: 2)
    assert ryc.main(["--destino", "x"]) == ryc.EXIT_NO_PUDO_CONTAR == 6
    assert "no pude contar (salida 2" in capsys.readouterr().err
    # la cuenta sale 5 (nada que contar): se devuelve el del rescate y se dice que no había trazas
    monkeypatch.setattr(ryc.kaggle_cuenta_llamadas, "main", lambda argv=None: 5)
    assert ryc.main(["--destino", "x"]) == 0
    assert "nada que contar" in capsys.readouterr().err
    # la cuenta sale 4 (leyó con problemas): 4
    monkeypatch.setattr(ryc.kaggle_cuenta_llamadas, "main", lambda argv=None: 4)
    assert ryc.main(["--destino", "x"]) == 4


def test_la_orden_unida_muestra_lo_que_el_rescate_imprimio_aunque_el_rescate_lance(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def rescate_que_lanza(argv: list[str] | None = None) -> int:
        print("llegué a imprimir esto")
        raise RuntimeError("se cayó")

    monkeypatch.setattr(ryc.kaggle_rescate, "main", rescate_que_lanza)
    with pytest.raises(RuntimeError):
        ryc.main(["--destino", "x"])
    assert "llegué a imprimir esto" in capsys.readouterr().out


def test_la_orden_unida_sin_carpeta_en_la_salida_del_rescate(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(ryc.kaggle_rescate, "main", lambda argv=None: print("no es json") or 0)
    assert ryc.main(["--destino", "x"]) == ryc.EXIT_NO_PUDO_CONTAR
    assert "no dijo su carpeta" in capsys.readouterr().err
