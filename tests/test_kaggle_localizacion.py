"""Pruebas de scripts/kaggle_localizacion.py con un grafo sintético inventado.

Ningún dato de la competencia: nodos, enunciados y parches son de un taller que no existe.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from associative_agent_loop.memory.associative import RetrievalConfig
from scripts import kaggle_localizacion as kl


def grafo() -> kl.GrafoCodigo:
    """Grafo pequeño: ``Motor.arrancar`` llama a ``_encender``, que llama a ``chispa``; dos nodos sueltos.

    ``tienda.pagos.cobrar`` y ``tienda.envios.cobrar`` comparten el último componente.
    """
    textos = {
        "taller.motor.Motor": "class Motor:\n    None",
        "taller.motor.Motor.arrancar": "def arrancar(self):\n    return _encender(self.llave)",
        "taller.motor._encender": "def _encender(llave):\n    valor = chispa(llave)\n    return valor",
        "taller.bujia.chispa": "def chispa(llave):\n    return llave * 2",
        "taller.bujia.limpiar": "def limpiar():\n    return None",
        "tienda.pagos.cobrar": "def cobrar(monto):\n    return monto",
        "tienda.envios.cobrar": "def cobrar(peso):\n    return peso",
        "tests.test_motor.test_arrancar": "def test_arrancar():\n    assert Motor().arrancar()",
    }
    aristas = [
        ("taller.motor.Motor.arrancar", "taller.motor._encender"),
        ("taller.motor._encender", "taller.bujia.chispa"),
        ("tests.test_motor.test_arrancar", "taller.motor.Motor.arrancar"),
    ]
    return kl.GrafoCodigo(textos, aristas)


PARCHE_CHISPA = "\n".join(
    [
        "--- a/taller/bujia.py",
        "+++ b/taller/bujia.py",
        "@@ -1,2 +1,2 @@",
        " def chispa(llave):",
        "-    return llave * 2",
        "+    return llave * 3",
    ]
)


# --------------------------------------------------------------------------- lectura y adaptador
def test_leer_grafo_descarta_aristas_a_nodos_que_no_existen(tmp_path: Path) -> None:
    datos = {
        "nodes": [{"id": "a.f", "text": "def f(): pass"}, {"id": "a.g", "text": None}],
        "edges": [
            {"source": "a.f", "target": "a.g", "type": "calls"},
            {"source": "a.f", "target": "no.esta"},
        ],
    }
    ruta = tmp_path / "g.json"
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    leido = kl.leer_grafo(ruta)
    assert leido.textos == {"a.f": "def f(): pass", "a.g": ""}
    assert leido.aristas == [("a.f", "a.g")]


def test_leer_grafo_admite_la_clave_links(tmp_path: Path) -> None:
    datos = {"nodes": [{"id": "a"}, {"id": "b"}], "links": [{"source": "a", "target": "b"}]}
    ruta = tmp_path / "g.json"
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    assert kl.leer_grafo(ruta).aristas == [("a", "b")]


def test_el_adaptador_conserva_nodos_y_aristas_y_omite_lazos() -> None:
    g = kl.GrafoCodigo({"a.f": "", "a.g": ""}, [("a.f", "a.g"), ("a.f", "a.f")])
    mg = kl.grafo_de_memoria(g)
    assert sorted(n.id for n in mg.nodes()) == ["concept:code:a.f", "concept:code:a.g"]
    aristas = [(e.source, e.target, e.relation.value, e.weight) for e in mg.edges()]
    assert aristas == [("concept:code:a.f", "concept:code:a.g", "ASSOCIATED_WITH", 1.0)]


# --------------------------------------------------------------------------- símbolos y semillas
def test_simbolos_amplios_toman_identificadores_y_nombres_con_puntos() -> None:
    texto = "El motor no arranca: Motor.arrancar() falla con la llave. Ver https://ejemplo.org"
    assert kl.simbolos_del_enunciado(texto) == [
        "motor",
        "arranca",
        "Motor.arrancar",
        "Motor",
        "arrancar",
        "falla",
        "llave",
        "Ver",
        "https",
        "ejemplo.org",
        "ejemplo",
        "org",
    ]


def test_simbolos_estrictos_solo_lo_escrito_como_codigo() -> None:
    texto = "El motor falla en `chispa` y en limpiar_todo; ArrancaMotor(x) y a.b tambien, 123 no."
    assert kl.simbolos_del_enunciado(texto, estrictos=True) == [
        "chispa",
        "limpiar_todo",
        "ArrancaMotor",
        "a.b",
    ]


def test_resolver_prefiere_el_sufijo_mas_largo_y_cae_a_mayusculas_y_guion_bajo() -> None:
    g = grafo()
    assert kl.resolver("Motor.arrancar", g) == ["taller.motor.Motor.arrancar"]
    assert kl.resolver("otro.modulo.chispa", g) == ["taller.bujia.chispa"]
    assert kl.resolver("motor", g) == ["taller.motor.Motor"]
    assert kl.resolver("encender", g) == ["taller.motor._encender"]
    assert kl.resolver("cobrar", g) == ["tienda.pagos.cobrar", "tienda.envios.cobrar"]
    assert kl.resolver("inexistente", g) == []


def test_semillas_reparten_el_peso_del_simbolo_y_no_cuentan_dos_veces() -> None:
    g = grafo()
    sem = kl.semillas(["cobrar", "chispa", "bujia.chispa", "nada"], g)
    assert sem == {"tienda.pagos.cobrar": 0.5, "tienda.envios.cobrar": 0.5, "taller.bujia.chispa": 1.0}
    # «Cobrar» nombra los mismos dos nodos que «cobrar»: no los siembra otra vez.
    assert kl.semillas(["cobrar", "Cobrar"], g) == {"tienda.pagos.cobrar": 0.5, "tienda.envios.cobrar": 0.5}


# --------------------------------------------------------------------------- clasificaciones
def test_distancias_no_siguen_la_direccion_y_respetan_el_tope() -> None:
    g = grafo()
    ady = g.vecinos()
    assert kl.distancias(["taller.bujia.chispa"], ady, tope=2) == {
        "taller.bujia.chispa": 0,
        "taller.motor._encender": 1,
        "taller.motor.Motor.arrancar": 2,
    }
    assert "tests.test_motor.test_arrancar" in kl.distancias(["taller.bujia.chispa"], ady, tope=3)


def test_vecinos_ordenan_semillas_despues_anillos() -> None:
    sem = {"s": 0.5}
    dist = {"s": 0, "a": 1, "b": 2}
    assert kl.puntajes_vecinos(sem, dist, 1) == {"s": 2.5, "a": 1.0}
    assert kl.puntajes_vecinos(sem, dist, 2) == {"s": 3.5, "a": 2.0, "b": 1.0}


def test_la_activacion_usa_el_mecanismo_del_repositorio_y_decae_con_los_saltos() -> None:
    g = grafo()
    act = kl.puntajes_activacion({"taller.bujia.chispa": 1.0}, kl.grafo_de_memoria(g), RetrievalConfig())
    # δ = 0,7 y fan-out «sqrt»: chispa (grado 1) pasa 0,7; _encender (grado 2) pasa 0,7 · 0,7 / √2.
    assert act["taller.bujia.chispa"] == 1.0
    assert act["taller.motor._encender"] == pytest.approx(0.7)
    assert act["taller.motor.Motor.arrancar"] == pytest.approx(0.7 * 0.7 / math.sqrt(2))
    assert act["taller.motor.Motor.arrancar"] > act["tests.test_motor.test_arrancar"] > 0
    assert "taller.bujia.limpiar" not in act
    assert "tienda.pagos.cobrar" not in act


def test_la_activacion_respeta_max_hops() -> None:
    g = grafo()
    corta = RetrievalConfig(max_hops=1)
    act = kl.puntajes_activacion({"taller.bujia.chispa": 1.0}, kl.grafo_de_memoria(g), corta)
    assert set(act) == {"taller.bujia.chispa", "taller.motor._encender"}


def test_palabras_puntuan_por_coseno_con_nombre_y_texto() -> None:
    g = grafo()
    p = kl.puntajes_palabras("chispa llave", g)
    assert max(p, key=p.__getitem__) == "taller.bujia.chispa"
    assert "taller.bujia.limpiar" not in p
    assert kl.puntajes_palabras("", g) == {}


# --------------------------------------------------------------------------- probabilidad de acierto
def test_prob_acierto_sin_empates_es_cero_o_uno() -> None:
    p = {"a": 3.0, "b": 2.0, "c": 1.0}
    assert kl.prob_acierto(p, {"b"}, total=10, k=1) == 0.0
    assert kl.prob_acierto(p, {"b"}, total=10, k=2) == 1.0


def test_prob_acierto_del_azar_es_k_entre_n() -> None:
    assert kl.prob_acierto({}, {"x"}, total=20, k=5) == pytest.approx(5 / 20)
    # Dos sitios: 1 − C(18, 5) / C(20, 5).
    assert kl.prob_acierto({}, {"x", "y"}, total=20, k=5) == pytest.approx(
        1 - math.comb(18, 5) / math.comb(20, 5)
    )


def test_prob_acierto_con_empate_reparte_las_plazas_que_quedan() -> None:
    p = {"a": 2.0, "b": 1.0, "c": 1.0, "d": 1.0, "e": 1.0}
    # «a» ocupa una plaza; de las 2 restantes entre 4 empatados, el sitio «b» entra con 2/4.
    assert kl.prob_acierto(p, {"b"}, total=50, k=3) == pytest.approx(0.5)
    assert kl.prob_acierto(p, {"b"}, total=50, k=1) == 0.0
    assert kl.prob_acierto(p, {"b"}, total=50, k=5) == 1.0


def test_prob_acierto_de_un_sitio_sin_puntaje_cuenta_los_no_puntuados() -> None:
    p = {"a": 2.0, "b": 1.0}
    # Quedan 3 plazas para los 8 nodos sin puntaje.
    assert kl.prob_acierto(p, {"z"}, total=10, k=5) == pytest.approx(3 / 8)
    assert kl.prob_acierto(p, {"z"}, total=10, k=2) == 0.0
    assert kl.prob_acierto(p, set(), total=10, k=5) == 0.0


# --------------------------------------------------------------------------- sitio de referencia
def test_modulo_de_quita_carpetas_y_reconoce_paquetes() -> None:
    g = kl.GrafoCodigo({"paq.mod.f": "", "paq.Clase": "", "guia.ejemplo.g": ""}, [])
    assert kl.modulo_de("src/paq/mod.py", g) == "paq.mod"
    assert kl.modulo_de("paq/__init__.py", g) == "paq"
    assert kl.modulo_de("docs_src/guia/ejemplo.py", g) == "guia.ejemplo"
    assert kl.modulo_de("otra/cosa.py", g) is None
    assert kl.modulo_de("paq/mod.txt", g) is None


def test_sitio_de_una_linea_quitada_dentro_de_una_funcion() -> None:
    assert kl.sitios_de_referencia(PARCHE_CHISPA, grafo()) == {"taller.bujia.chispa"}


def test_sitio_por_la_cabecera_del_trozo_cuando_la_definicion_no_se_ve() -> None:
    parche = "\n".join(
        [
            "--- a/taller/motor.py",
            "+++ b/taller/motor.py",
            "@@ -8,3 +8,3 @@ def _encender(llave):",
            "     valor = chispa(llave)",
            "-    return valor",
            "+    return valor or 0",
        ]
    )
    assert kl.sitios_de_referencia(parche, grafo()) == {"taller.motor._encender"}


def test_sitio_de_un_metodo_usa_la_clase_que_lo_encierra() -> None:
    parche = "\n".join(
        [
            "--- a/taller/motor.py",
            "+++ b/taller/motor.py",
            "@@ -1,4 +1,4 @@",
            " class Motor:",
            "     def arrancar(self):",
            "-        return _encender(self.llave)",
            "+        return _encender(self.llave, True)",
        ]
    )
    assert kl.sitios_de_referencia(parche, grafo()) == {"taller.motor.Motor.arrancar"}


def test_un_metodo_nuevo_apunta_a_la_clase_y_no_al_metodo_anterior() -> None:
    parche = "\n".join(
        [
            "--- a/taller/motor.py",
            "+++ b/taller/motor.py",
            "@@ -1,3 +1,6 @@",
            " class Motor:",
            "     def arrancar(self):",
            "         return _encender(self.llave)",
            "+",
            "+    def parar(self):",
            "+        return None",
        ]
    )
    assert kl.sitios_de_referencia(parche, grafo()) == {"taller.motor.Motor"}


def test_nombres_repetidos_se_distinguen_por_el_archivo() -> None:
    parche = "\n".join(
        [
            "--- a/tienda/envios.py",
            "+++ b/tienda/envios.py",
            "@@ -1,2 +1,2 @@",
            " def cobrar(peso):",
            "-    return peso",
            "+    return peso * 2",
        ]
    )
    assert kl.sitios_de_referencia(parche, grafo()) == {"tienda.envios.cobrar"}


def test_lineas_identicas_se_distinguen_por_la_cabecera_y_por_el_archivo() -> None:
    igual = "def {}():\n    return 1"
    g = kl.GrafoCodigo({n: igual.format(n[-1]) for n in ("a.f", "a.g", "b.f", "b.g")}, [])
    parche = "\n".join(
        ["--- a/b.py", "+++ b/b.py", "@@ -5,1 +5,1 @@ def g():", "-    return 1", "+    return 2"]
    )
    assert kl.sitios_de_referencia(parche, g) == {"b.g"}


def test_un_archivo_fuera_del_grafo_o_un_cambio_de_modulo_no_dan_sitio() -> None:
    fuera = PARCHE_CHISPA.replace("taller/bujia.py", "docs/guia.py")
    assert kl.sitios_de_referencia(fuera, grafo()) == set()
    modulo = "\n".join(
        ["--- a/taller/bujia.py", "+++ b/taller/bujia.py", "@@ -1,1 +1,1 @@", "-import os", "+import sys"]
    )
    assert kl.sitios_de_referencia(modulo, grafo()) == set()


# --------------------------------------------------------------------------- medida y agregado
def test_medir_tarea_la_activacion_alcanza_un_sitio_que_las_semillas_no_nombran() -> None:
    # El enunciado nombra el método; la edición está dos saltos más allá, en ``chispa``.
    m = kl.medir_tarea("org/taller", "Falla arrancar al girar", PARCHE_CHISPA, grafo())
    assert m is not None
    assert (m.repo, m.nodos, m.sitios, m.simbolos, m.semillas, m.distancia) == ("org/taller", 8, 1, 1, 1, 2)
    assert m.aciertos[kl.AZAR][1] == pytest.approx(1 / 8)
    assert m.aciertos[kl.SEMILLAS][1] == 0.0
    assert m.aciertos[kl.VECINOS_1][5] == pytest.approx(2 / 5)  # 3 plazas ocupadas, 2 para 5 sin puntaje
    assert m.aciertos[kl.VECINOS_2][5] == 1.0
    assert m.aciertos[kl.ACTIVACION][5] == 1.0
    assert m.aciertos[kl.ACTIVACION][1] == 0.0


def test_medir_tarea_sin_sitio_en_el_grafo_devuelve_none() -> None:
    fuera = PARCHE_CHISPA.replace("taller/bujia.py", "docs/guia.py")
    assert kl.medir_tarea("org/taller", "Falla Motor.arrancar", fuera, grafo()) is None


def test_las_clasificaciones_no_dependen_del_parche() -> None:
    """Frontera de fuga: con otro parche cambian los aciertos, no lo que se clasifica."""
    vistos: list[tuple[str, tuple[str, ...]]] = []

    def espia(enunciado: str, simbolos: object, _g: kl.GrafoCodigo) -> dict[str, float]:
        vistos.append((enunciado, tuple(simbolos)))  # type: ignore[arg-type]
        return {}

    otro = PARCHE_CHISPA.replace("taller/bujia.py", "tienda/pagos.py").replace(
        "chispa(llave)", "cobrar(monto)"
    )
    otro = otro.replace("llave * 2", "monto").replace("llave * 3", "monto + 1")
    a = kl.medir_tarea("org/taller", "Falla Motor.arrancar", PARCHE_CHISPA, grafo(), extra={"espia": espia})
    b = kl.medir_tarea("org/taller", "Falla Motor.arrancar", otro, grafo(), extra={"espia": espia})
    assert a is not None and b is not None
    assert vistos[0] == vistos[1] == ("Falla Motor.arrancar", ("Motor.arrancar", "Motor", "arrancar"))
    assert a.semillas == b.semillas
    assert a.aciertos[kl.ACTIVACION][5] == 1.0
    assert b.aciertos[kl.ACTIVACION][5] < 1.0


def test_agregar_promedia_por_repositorio_y_total() -> None:
    def medida(repo: str, valor: float, distancia: int | None) -> kl.Medida:
        return kl.Medida(repo, 10, 1, 1, 1, distancia, {kl.AZAR: dict.fromkeys(kl.CORTES, valor)})

    ag = kl.agregar([medida("a/x", 1.0, 0), medida("a/x", 0.0, None), medida("b/y", 0.5, 3)])
    assert list(ag) == ["a/x", "b/y", "total"]
    assert ag["a/x"]["tareas"] == 2
    assert ag["a/x"]["metodos"][kl.AZAR]["5"] == 50.0
    assert ag["a/x"]["sitio_a_2_saltos_o_menos_de_una_semilla"] == 1
    assert ag["total"]["tareas"] == 3
    assert ag["total"]["metodos"][kl.AZAR]["1"] == 50.0
    tabla = kl.tabla_markdown(ag)
    assert "| total | 3 | azar | 50,0 % | 50,0 % | 50,0 % | 50,0 % |" in tabla


def test_main_escribe_solo_agregados(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    g = grafo()
    grafos = tmp_path / "graphs"
    grafos.mkdir()
    datos = {
        "nodes": [{"id": n, "text": t} for n, t in g.textos.items()],
        "edges": [{"source": a, "target": b, "type": "calls"} for a, b in g.aristas],
    }
    (grafos / "taller_abc123.json").write_text(json.dumps(datos), encoding="utf-8")
    tareas = [
        {
            "instance_id": "tarea_secreta_1",
            "repo": "org/taller",
            "base_commit": "abc123",
            "problem_statement": "Falla Motor.arrancar al girar",
            "hints_text": "",
            "patch": PARCHE_CHISPA,
        },
        {
            "instance_id": "tarea_secreta_2",
            "repo": "org/taller",
            "base_commit": "sin_grafo",
            "problem_statement": "x",
            "hints_text": "",
            "patch": PARCHE_CHISPA,
        },
    ]
    ruta = tmp_path / "tasks.jsonl"
    ruta.write_text("\n".join(json.dumps(t) for t in tareas), encoding="utf-8")
    salida = tmp_path / "agregado.json"
    assert kl.main(["--tareas", str(ruta), "--grafos", str(grafos), "--salida", str(salida)]) == 0
    informe = json.loads(salida.read_text(encoding="utf-8"))
    assert (informe["tareas_leidas"], informe["sin_grafo"], informe["tareas_medidas"]) == (2, 1, 1)
    assert informe["agregado"]["total"]["metodos"][kl.ACTIVACION]["5"] == 100.0
    publicado = salida.read_text(encoding="utf-8") + capsys.readouterr().out
    for prohibido in ("tarea_secreta", "Falla Motor", "llave * 3", "abc123"):
        assert prohibido not in publicado


def test_cruce_con_resultados_cuenta_sin_identificadores() -> None:
    def medida(valor: float) -> kl.Medida:
        return kl.Medida("a/x", 10, 1, 1, 1, 0, {kl.ACTIVACION: dict.fromkeys(kl.CORTES, valor)})

    medidas = {"t1": medida(1.0), "t2": medida(0.4), "t3": medida(1.0), "t4": medida(1.0)}
    cruce = kl.cruce_con_resultados(medidas, {"t1": False, "t2": False, "t3": True})
    assert cruce["nunca_resueltas"]["tareas_medidas"] == 2
    assert cruce["nunca_resueltas"]["metodos"][kl.ACTIVACION] == {"esperadas": 1.4, "seguras": 1}
    assert cruce["resueltas_alguna_vez"]["tareas_medidas"] == 1
    assert "t1" not in json.dumps(cruce)
