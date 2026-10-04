"""Hipótesis Zorzal: perfil de una sesión del agente y reglas de decisión, sobre conteos.

Un zorzal busca, oye, observa, espera y acierta una vez. Este módulo convierte esos cinco rasgos en
comprobaciones sobre los conteos que el notebook de medición guarda por tarea, y aplica las reglas con las que
se leerán las hipótesis H-Z1, H-Z2, H-Z3 y H-O. Los umbrales no están aquí: se leen de
``experiments/gemma_developer_agent/zorzal/umbrales.json``, que se congeló antes de leer ningún resultado.

Solo usa conteos. No lee enunciados, parches ni pruebas, y rechaza un registro que traiga texto.

Uso:
    python -m scripts.zorzal_perfil evaluar <resultados.json> --validas <ids.json> --leido-en <ISO> \\
        --limite A=40 --limite R=60 [--base A --candidata R]
    python -m scripts.zorzal_perfil informe <informe.md>
    python -m scripts.zorzal_perfil operacion <bitacora.json>

Salida: 0 si se evaluó, 2 si la entrada es inválida.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

UMBRALES = Path(__file__).resolve().parents[1] / "experiments/gemma_developer_agent/zorzal/umbrales.json"
RASGOS = ("busca", "oye", "observa", "espera", "acierta")
HERRAMIENTAS_DE_EDICION = ("edit_file", "write_file")
CAMPOS_DE_ANATOMIA = frozenset(
    {
        "herramientas",
        "errores_de_herramienta",
        "llamada_de_la_primera_edicion",
        "segundos_hasta_la_primera_edicion",
        "comandos_con_pytest",
        "llamadas_repetidas",
        "repetidas_tras_fallo",
        "comandos_con_salida_distinta_de_cero",
        "entregas",
        "empujones_del_arnes",
        "tokens_de_entrada",
        "tokens_generados",
    }
)
LARGO_MAXIMO_DE_NOMBRE = 40
SECCIONES_DEL_INFORME = ("Qué oí", "Qué vi", "Qué falta por oír", "La única acción")
SIN_ACCION = "todavía nada"


class EntradaInvalida(ValueError):
    """La entrada no cumple lo que el módulo exige para evaluar."""


def cargar_umbrales(ruta: Path = UMBRALES) -> dict[str, Any]:
    return json.loads(ruta.read_text(encoding="utf-8"))


def huella_de_umbrales(ruta: Path = UMBRALES) -> str:
    """SHA-256 del archivo de umbrales con saltos de línea normalizados."""
    return hashlib.sha256(ruta.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def validar_anatomia(anatomia: Mapping[str, Any]) -> None:
    """Exige que el registro traiga solo conteos: ningún campo desconocido ni texto largo."""
    if "sin_traza" in anatomia:
        raise EntradaInvalida("la tarea no tiene traza")
    desconocidos = set(anatomia) - CAMPOS_DE_ANATOMIA
    if desconocidos:
        raise EntradaInvalida(f"campos no permitidos: {sorted(desconocidos)}")
    for campo in ("herramientas", "errores_de_herramienta"):
        tabla = anatomia.get(campo) or {}
        for nombre, veces in tabla.items():
            if len(str(nombre)) > LARGO_MAXIMO_DE_NOMBRE or not isinstance(veces, int):
                raise EntradaInvalida(f"{campo} debe ser nombre corto y conteo")
    for campo, valor in anatomia.items():
        if isinstance(valor, str):
            raise EntradaInvalida(f"{campo} trae texto; solo se admiten conteos")


def rasgos(anatomia: Mapping[str, Any], limite_llamadas: int, umbrales: Mapping[str, Any]) -> dict[str, bool]:
    """Los cinco rasgos de una sesión, cada uno cumplido o no."""
    validar_anatomia(anatomia)
    r = umbrales["rasgos"]
    usadas = anatomia.get("herramientas") or {}
    llamadas = sum(usadas.values())
    ediciones = sum(usadas.get(h, 0) for h in HERRAMIENTAS_DE_EDICION)
    primera = anatomia.get("llamada_de_la_primera_edicion")
    a = r["acierta"]
    return {
        "busca": primera is not None and primera >= r["busca"]["minimo"],
        "oye": (anatomia.get("comandos_con_pytest") or 0) >= r["oye"]["minimo"],
        "observa": (anatomia.get("repetidas_tras_fallo") or 0) <= r["observa"]["maximo"],
        "espera": llamadas <= limite_llamadas - r["espera"]["margen_bajo_el_limite"],
        "acierta": a["ediciones_minimo"] <= ediciones <= a["ediciones_maximo"]
        and (anatomia.get("entregas") or 0) <= a["entregas_maximo"],
    }


def perfil_primario(umbrales: Mapping[str, Any]) -> str:
    """Qué perfil manda: el completo, o el que deja fuera «oye» mientras su medida sea incompleta."""
    oye = umbrales["rasgos"]["oye"]
    if umbrales["version"] <= oye.get("medida_incompleta_hasta_version", 0):
        return umbrales["perfil"]["primario_mientras_oye_sea_incompleto"]
    return "completo"


def tiene_perfil(cumplidos: Mapping[str, bool], umbrales: Mapping[str, Any], cual: str | None = None) -> bool:
    return all(cumplidos[x] for x in umbrales["perfil"][cual or perfil_primario(umbrales)])


def sesiones(
    corrida: Mapping[str, Any], validas: set[str], limite: int, umbrales: Mapping[str, Any]
) -> list[dict]:
    """Las sesiones de una pasada, solo de tareas válidas, con su perfil."""
    filas = []
    for fila in corrida["tareas"]:
        if fila["instance_id"] not in validas:
            continue
        cumplidos = rasgos(fila["anatomia"], limite, umbrales)
        filas.append(
            {
                "resuelta": bool(fila["resuelta"]),
                "tiempo_agotado": str(fila.get("clase", "")).startswith("tiempo_agotado"),
                "rasgos": cumplidos,
                "perfil": tiene_perfil(cumplidos, umbrales),
            }
        )
    return filas


def veredicto_hz1(filas: Sequence[Mapping[str, Any]], umbrales: Mapping[str, Any]) -> dict[str, Any]:
    """H-Z1: las sesiones con perfil zorzal se resuelven con más frecuencia que las demás."""
    con = [f for f in filas if f["perfil"]]
    sin = [f for f in filas if not f["perfil"]]
    minimo = umbrales["decision"]["grupo_minimo_para_hz1"]
    conteos = {
        "con_perfil": len(con),
        "resueltas_con_perfil": sum(f["resuelta"] for f in con),
        "sin_perfil": len(sin),
        "resueltas_sin_perfil": sum(f["resuelta"] for f in sin),
    }
    if len(con) < minimo or len(sin) < minimo:
        return {**conteos, "veredicto": "no evaluable"}
    apoyada = conteos["resueltas_con_perfil"] / len(con) > conteos["resueltas_sin_perfil"] / len(sin)
    return {**conteos, "veredicto": "apoyada" if apoyada else "refutada"}


def ruido(pasada_1: Sequence[Mapping[str, Any]], pasada_2: Sequence[Mapping[str, Any]]) -> int:
    """Tareas que cambian de resultado entre dos pasadas iguales."""
    if len(pasada_1) != len(pasada_2):
        raise EntradaInvalida("las dos pasadas iguales deben cubrir las mismas tareas")
    return sum(a["resuelta"] != b["resuelta"] for a, b in zip(pasada_1, pasada_2, strict=True))


def ventaja_exigida(d: int, umbrales: Mapping[str, Any]) -> int:
    regla = umbrales["decision"]
    return max(regla["ventaja_minima_tareas"], d + regla["ventaja_sobre_ruido"])


def veredicto_hz2(
    base_1: Sequence[Mapping[str, Any]],
    base_2: Sequence[Mapping[str, Any]],
    candidata: Sequence[Mapping[str, Any]],
    relleno: Sequence[Mapping[str, Any]] | None,
    umbrales: Mapping[str, Any],
) -> dict[str, Any]:
    """H-Z2: inducir el perfil sube el resultado más que el ruido y más que un relleno."""
    d = ruido(base_1, base_2)
    exigida = ventaja_exigida(d, umbrales)
    resueltas = lambda filas: sum(f["resuelta"] for f in filas)  # noqa: E731
    con_perfil = lambda filas: sum(f["perfil"] for f in filas)  # noqa: E731
    mejor_base = max(resueltas(base_1), resueltas(base_2))
    aumento = con_perfil(candidata) - max(con_perfil(base_1), con_perfil(base_2))
    salida = {
        "ruido": d,
        "ventaja_exigida": exigida,
        "ventaja_sobre_base": resueltas(candidata) - mejor_base,
        "ventaja_sobre_relleno": None if relleno is None else resueltas(candidata) - resueltas(relleno),
        "aumento_de_sesiones_con_perfil": aumento,
    }
    if aumento < umbrales["decision"]["aumento_minimo_de_sesiones_con_perfil"]:
        return {**salida, "veredicto": "no puesta a prueba"}
    if relleno is None:
        return {**salida, "veredicto": "no evaluable sin relleno"}
    apoyada = salida["ventaja_sobre_base"] >= exigida and salida["ventaja_sobre_relleno"] >= exigida
    return {**salida, "veredicto": "apoyada" if apoyada else "refutada"}


def veredicto_hz3(
    base_1: Sequence[Mapping[str, Any]],
    base_2: Sequence[Mapping[str, Any]],
    candidata: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """H-Z3: con la configuración candidata no aumentan las tareas cortadas por tiempo."""
    cortadas = lambda filas: sum(f["tiempo_agotado"] for f in filas)  # noqa: E731
    tope = max(cortadas(base_1), cortadas(base_2))
    return {
        "cortadas_base": tope,
        "cortadas_candidata": cortadas(candidata),
        "veredicto": "apoyada" if cortadas(candidata) <= tope else "refutada",
    }


def veredicto_ho(bitacora: Mapping[str, Any], umbrales: Mapping[str, Any]) -> dict[str, Any]:
    """H-O: una subida por resultado útil y ninguna corrida perdida por una causa visible en local."""
    regla = umbrales["operacion"]
    desde, hasta = regla["ventana"]
    subidas = [s for s in bitacora["subidas"] if desde <= s["fecha"][:10] <= hasta]
    utiles = sum(bool(s["resultado_util"]) for s in subidas)
    visibles = sum(bool(s["fallo_visible_en_local"]) for s in subidas)
    salida = {"subidas": len(subidas), "resultados_utiles": utiles, "fallos_visibles_en_local": visibles}
    if not subidas:
        return {**salida, "veredicto": "no evaluable"}
    cumple = (
        utiles > 0
        and len(subidas) / utiles <= regla["subidas_por_resultado_util_maximo"]
        and visibles <= regla["fallos_visibles_en_local_maximo"]
    )
    return {**salida, "veredicto": "apoyada" if cumple else "refutada"}


def validar_informe(texto: str) -> list[str]:
    """Problemas de un informe zorzal: las cuatro partes, y una sola acción o «todavía nada»."""
    problemas = []
    partes = {}
    for titulo in SECCIONES_DEL_INFORME:
        m = re.search(rf"^#+\s*{re.escape(titulo)}[^\n]*\n(.*?)(?=^#+\s|\Z)", texto, re.M | re.S)
        if not m or not m.group(1).strip():
            problemas.append(f"falta la parte «{titulo}»")
        else:
            partes[titulo] = m.group(1).strip()
    accion = partes.get("La única acción")
    if accion and SIN_ACCION not in accion.lower():
        acciones = [linea for linea in accion.splitlines() if re.match(r"\s*(?:[-*]|\d+\.)\s+", linea)]
        if len(acciones) > 1:
            problemas.append(f"propone {len(acciones)} acciones; un zorzal propone una")
    oido = partes.get("Qué oí")
    if oido and "fuente" not in oido.lower():
        problemas.append("«Qué oí» no nombra la fuente de cada señal")
    return problemas


def evaluar(
    resultados: Mapping[str, Any],
    validas: set[str],
    limites: Mapping[str, int],
    leido_en: str,
    umbrales: Mapping[str, Any],
    base: str | None = None,
    candidata: str | None = None,
    relleno: str | None = None,
) -> dict[str, Any]:
    """Lee un archivo de resultados con las reglas congeladas. Se niega si se leyó antes de congelarlas."""
    congelado = datetime.fromisoformat(umbrales["congelado_en"].replace("Z", "+00:00"))
    if datetime.fromisoformat(leido_en.replace("Z", "+00:00")) < congelado:
        raise EntradaInvalida("los resultados se leyeron antes de congelar los umbrales")
    por_condicion: dict[str, list[list[dict]]] = {}
    for corrida in resultados["corridas"].values():
        condicion = corrida["condicion"]
        if condicion not in limites:
            raise EntradaInvalida(f"falta el límite de llamadas de la condición {condicion}")
        por_condicion.setdefault(condicion, []).append(
            sesiones(corrida, validas, limites[condicion], umbrales)
        )
    salida: dict[str, Any] = {
        "perfil_usado": perfil_primario(umbrales),
        "oye_incompleto": perfil_primario(umbrales) != "completo",
        "por_condicion": {
            c: {
                "pasadas": len(p),
                "sesiones": sum(len(x) for x in p),
                "resueltas": [sum(f["resuelta"] for f in x) for x in p],
                "con_perfil": [sum(f["perfil"] for f in x) for x in p],
                "rasgos": {r: sum(f["rasgos"][r] for x in p for f in x) for r in RASGOS},
                "hz1": veredicto_hz1([f for x in p for f in x], umbrales),
            }
            for c, p in por_condicion.items()
        },
    }
    if base and candidata:
        pasadas = por_condicion.get(base, [])
        if len(pasadas) < 2 or candidata not in por_condicion:
            raise EntradaInvalida("la comparación necesita dos pasadas de la base y una de la candidata")
        cand = por_condicion[candidata][0]
        rell = por_condicion[relleno][0] if relleno else None
        salida["hz2"] = veredicto_hz2(pasadas[0], pasadas[1], cand, rell, umbrales)
        salida["hz3"] = veredicto_hz3(pasadas[0], pasadas[1], cand)
    return salida


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="orden", required=True)
    ev = sub.add_parser("evaluar")
    ev.add_argument("resultados", type=Path)
    ev.add_argument("--validas", type=Path, required=True)
    ev.add_argument("--leido-en", required=True)
    ev.add_argument("--limite", action="append", default=[], metavar="CONDICION=LLAMADAS")
    ev.add_argument("--base")
    ev.add_argument("--candidata")
    ev.add_argument("--relleno")
    inf = sub.add_parser("informe")
    inf.add_argument("informe", type=Path)
    op = sub.add_parser("operacion")
    op.add_argument("bitacora", type=Path)
    args = parser.parse_args(argv)
    umbrales = cargar_umbrales()
    try:
        if args.orden == "informe":
            problemas = validar_informe(args.informe.read_text(encoding="utf-8"))
            print(json.dumps({"valido": not problemas, "problemas": problemas}, ensure_ascii=False, indent=1))
            return 0 if not problemas else 2
        if args.orden == "operacion":
            bitacora = json.loads(args.bitacora.read_text(encoding="utf-8"))
            print(json.dumps(veredicto_ho(bitacora, umbrales), ensure_ascii=False, indent=1))
            return 0
        limites = {k: int(v) for k, v in (x.split("=", 1) for x in args.limite)}
        salida = evaluar(
            json.loads(args.resultados.read_text(encoding="utf-8")),
            set(json.loads(args.validas.read_text(encoding="utf-8"))),
            limites,
            args.leido_en,
            umbrales,
            args.base,
            args.candidata,
            args.relleno,
        )
    except (EntradaInvalida, KeyError, ValueError, OSError) as exc:
        print(f"entrada inválida: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(salida, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
