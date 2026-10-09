"""Compara dos pasadas del notebook de la iteración 08 par a par (#179, punto 11).

    python -m scripts.kaggle_comparar_pasadas --base <salida> [--base <salida> ...]
        --otra <salida> [--otra <salida> ...] [--lista <acta del sorteo>]

Cada lado es una pasada, o una pasada repartida en varias salidas que juntas cubren la misma lista de tareas
(las porciones de un brazo). Cada ``--base`` y ``--otra`` es la carpeta de salida de un notebook (la del
rescate, con prefijo ``salida__``, o la del núcleo) o el JSON de la pasada; el registro se busca en su
carpeta. De cada salida se leen dos cosas: el JSON de la pasada (qué tarea quedó resuelta) y su registro
(``scripts.kaggle_registro``: si la sesión es de fiar y qué tareas cortó el tope por tarea).

Lo que hace, en este orden:

1. Quita los pares cuya tarea sea un par faltante en **cualquiera** de los dos lados: está en
   ``sesion.pares_faltantes`` del registro, o su fila del JSON trae ``par_faltante: true`` o
   ``clase: tarea_colgada``. Dice cuántos quitó y cuáles quedan.
2. Con los pares que quedan cuenta concordantes (las dos resueltas, ninguna resuelta) y discordantes en cada
   sentido (solo la base, solo la otra), y da la prueba exacta de McNemar de
   ``scripts.kaggle_replicas.mcnemar_exact_p``.
3. Dice si la comparación está completa. **Una pasada con una tarea colgada no cuenta como completa**: la
   cuenta se escribe igual, pero la orden sale con un código distinto de 0 y el JSON dice por qué.

Una tarea que está en un solo lado es un hueco, no un par: se lista y la comparación no es completa. Con
``--lista`` (el ``lista`` del acta de ``kaggle_registro sortear``), cada lado debe cubrir exactamente esa
lista; sin ella, los dos lados deben cubrir las mismas tareas.

Solo mira las corridas del JSON con ``cuenta_para_resueltas: true``. Una tarea repetida dentro de un lado es
una entrada inválida.

Salida:
    0  comparación completa: ninguna tarea excluida, los dos lados cubren las mismas tareas, registros
       fiables y sesiones completas
    2  entrada inválida o ilegible (carpeta sin JSON o sin registro, JSON roto, tarea repetida en un lado)
    3  hay tareas colgadas (pares excluidos) y nada más está mal
    4  la comparación no es completa por otra causa (registro no fiable, sesión cortada o muerta, JSON que
       dice ``completo: false``, huecos de cobertura, el JSON y el registro no coinciden en las colgadas);
       gana al 3
No hay ningún código que diga «sin hallazgos» para una comparación con pares excluidos.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from scripts.kaggle_registro import (
    EXIT_CON_COLGADAS,
    EXIT_OK,
    RegistroError,
    cargar_salida,
    codigo_de,
    diagnosticar,
)
from scripts.kaggle_replicas import mcnemar_exact_p

EXIT_ENTRADA = 2
EXIT_COLGADAS = 3
EXIT_INCOMPLETA = 4

CLASE_COLGADA = "tarea_colgada"
PATRONES_JSON = ("iteracion_*.json", "salida__iteracion_*.json")


class CompararError(ValueError):
    """Entrada inválida o ilegible."""


# ---------------------------------------------------------------------------
# Lectura de un lado
# ---------------------------------------------------------------------------


def _json_de_la_pasada(ruta: Path) -> tuple[Path, Path]:
    """(archivo JSON de la pasada, carpeta de la salida). Acepta la carpeta o el propio JSON."""
    if ruta.is_file():
        if ruta.suffix != ".json":
            raise CompararError(f"{ruta.name}: se esperaba una carpeta de salida o el JSON de la pasada.")
        return ruta, ruta.parent
    if not ruta.is_dir():
        raise CompararError(f"No existe la salida {ruta}.")
    halladas = sorted({p for patron in PATRONES_JSON for p in ruta.glob(patron)})
    if len(halladas) != 1:
        raise CompararError(
            f"{ruta.name}: se esperaba un solo JSON de pasada (iteracion_*.json) y hay {len(halladas)}."
        )
    return halladas[0], ruta


def _filas_de_la_pasada(archivo: Path) -> tuple[bool | None, dict[str, dict[str, Any]]]:
    """``completo`` del JSON y las filas por tarea de sus corridas que cuentan para las resueltas."""
    try:
        datos = json.loads(archivo.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CompararError(f"{archivo.name}: JSON ilegible ({type(exc).__name__}).") from exc
    corridas = datos.get("corridas") if isinstance(datos, dict) else None
    if not isinstance(corridas, dict):
        raise CompararError(f"{archivo.name}: no trae el objeto «corridas».")
    filas: dict[str, dict[str, Any]] = {}
    contadas = 0
    for nombre, corrida in corridas.items():
        if not isinstance(corrida, dict) or corrida.get("cuenta_para_resueltas") is not True:
            continue
        contadas += 1
        tareas = corrida.get("tareas")
        if not isinstance(tareas, list):
            raise CompararError(f"{archivo.name}: la corrida {nombre} no trae la lista «tareas».")
        for fila in tareas:
            if not isinstance(fila, dict) or not isinstance(fila.get("instance_id"), str):
                raise CompararError(f"{archivo.name}: una fila de {nombre} no trae «instance_id» de texto.")
            if not isinstance(fila.get("resuelta"), bool):
                raise CompararError(
                    f"{archivo.name}: la fila de {fila['instance_id']} no trae «resuelta» booleano."
                )
            if fila["instance_id"] in filas:
                raise CompararError(f"{archivo.name}: la tarea {fila['instance_id']} aparece dos veces.")
            filas[fila["instance_id"]] = fila
    if contadas == 0:
        raise CompararError(f"{archivo.name}: ninguna corrida trae cuenta_para_resueltas: true.")
    completo = datos.get("completo")
    return (completo if isinstance(completo, bool) else None), filas


def _es_colgada_en_json(fila: dict[str, Any]) -> bool:
    return fila.get("par_faltante") is True or fila.get("clase") == CLASE_COLGADA


def leer_salida(ruta: Path) -> dict[str, Any]:
    """Una salida: sus filas, sus tareas colgadas según el JSON y según el registro, y su estado."""
    archivo, carpeta = _json_de_la_pasada(ruta)
    completo, filas = _filas_de_la_pasada(archivo)
    try:
        datos = cargar_salida(carpeta)
        informe = diagnosticar(datos["eventos"], datos["latidos"])
    except RegistroError as exc:
        raise CompararError(f"{carpeta.name}: {exc}") from exc
    sesion = informe["sesion"]
    return {
        "salida": carpeta.name,
        "filas": filas,
        "json_completo": completo,
        "colgadas_json": sorted(t for t, f in filas.items() if _es_colgada_en_json(f)),
        "colgadas_registro": sorted(str(t) for t in sesion["pares_faltantes"]),
        "estado": sesion["estado"],
        "registro_fiable": sesion["registro_fiable"],
        "codigo_registro": codigo_de(informe),
        "veredicto": sesion["veredicto"],
    }


def leer_lado(rutas: list[Path]) -> dict[str, Any]:
    """Un lado: una o varias salidas que juntas dan sus filas. Una tarea no puede estar en dos salidas."""
    if not rutas:
        raise CompararError("Cada lado necesita al menos una salida.")
    salidas = [leer_salida(r) for r in rutas]
    filas: dict[str, dict[str, Any]] = {}
    for s in salidas:
        repetidas = sorted(set(filas) & set(s["filas"]))
        if repetidas:
            raise CompararError(
                f"{len(repetidas)} tareas están en más de una salida del mismo lado (p. ej. {repetidas[0]})."
            )
        filas.update(s["filas"])
    return {"salidas": salidas, "filas": filas}


# ---------------------------------------------------------------------------
# Comparación
# ---------------------------------------------------------------------------


def _colgadas_del_lado(lado: dict[str, Any]) -> set[str]:
    return {t for s in lado["salidas"] for t in (*s["colgadas_json"], *s["colgadas_registro"])}


def _motivos_del_lado(nombre: str, lado: dict[str, Any]) -> tuple[list[str], list[str]]:
    """(motivos de «tarea colgada», motivos de otra incompletitud) de un lado."""
    colgadas: list[str] = []
    otros: list[str] = []
    for s in lado["salidas"]:
        etiqueta = f"{nombre} ({s['salida']})"
        if s["colgadas_json"] or s["colgadas_registro"]:
            colgadas.append(
                f"{etiqueta}: tiene {len(set(s['colgadas_json']) | set(s['colgadas_registro']))} tareas "
                "colgadas; una pasada con una tarea colgada no cuenta como completa"
            )
        if s["colgadas_json"] != s["colgadas_registro"]:
            otros.append(f"{etiqueta}: el JSON y el registro no coinciden en las tareas colgadas")
        if s["json_completo"] is not True and not (s["colgadas_json"] or s["colgadas_registro"]):
            otros.append(f"{etiqueta}: el JSON de la pasada no dice completo: true")
        # El 7 es la sesión que terminó con colgadas: ya lo dice el motivo de arriba.
        if s["codigo_registro"] not in (EXIT_OK, EXIT_CON_COLGADAS) or not s["registro_fiable"]:
            otros.append(f"{etiqueta}: el registro dice «{s['veredicto']}» (código {s['codigo_registro']})")
    return colgadas, otros


def comparar(
    base: dict[str, Any], otra: dict[str, Any], lista: list[str] | None = None
) -> tuple[dict[str, Any], int]:
    """El resultado de la comparación y su código de salida."""
    filas_a, filas_b = base["filas"], otra["filas"]
    esperadas = set(lista) if lista is not None else None
    huecos: dict[str, list[str]] = {}
    if esperadas is not None:
        huecos["base_sin"] = sorted(esperadas - set(filas_a))
        huecos["otra_sin"] = sorted(esperadas - set(filas_b))
        huecos["base_de_mas"] = sorted(set(filas_a) - esperadas)
        huecos["otra_de_mas"] = sorted(set(filas_b) - esperadas)
    else:
        huecos["base_sin"] = sorted(set(filas_b) - set(filas_a))
        huecos["otra_sin"] = sorted(set(filas_a) - set(filas_b))
    huecos = {k: v for k, v in huecos.items() if v}

    colgadas = _colgadas_del_lado(base) | _colgadas_del_lado(otra)
    comunes = sorted(
        set(filas_a) & set(filas_b) if esperadas is None else esperadas & set(filas_a) & set(filas_b)
    )
    excluidos = [t for t in comunes if t in colgadas]
    quedan = [t for t in comunes if t not in colgadas]
    # Una tarea colgada que no está en la lista común (porque falta del otro lado) también se dice.
    colgadas_fuera_de_pares = sorted(colgadas - set(comunes))

    solo_base = [t for t in quedan if filas_a[t]["resuelta"] and not filas_b[t]["resuelta"]]
    solo_otra = [t for t in quedan if filas_b[t]["resuelta"] and not filas_a[t]["resuelta"]]
    ambas = sum(1 for t in quedan if filas_a[t]["resuelta"] and filas_b[t]["resuelta"])
    ninguna = len(quedan) - ambas - len(solo_base) - len(solo_otra)

    colgadas_a, otros_a = _motivos_del_lado("base", base)
    colgadas_b, otros_b = _motivos_del_lado("otra", otra)
    motivos_colgadas = [*colgadas_a, *colgadas_b]
    motivos_otros = [*otros_a, *otros_b]
    if huecos:
        motivos_otros.append(
            "las dos pasadas no cubren las mismas tareas: "
            + "; ".join(f"{k} {len(v)}" for k, v in huecos.items())
        )

    codigo = EXIT_OK
    if motivos_otros:
        codigo = EXIT_INCOMPLETA
    elif motivos_colgadas:
        codigo = EXIT_COLGADAS
    informe = {
        "completa": codigo == EXIT_OK,
        "codigo": codigo,
        "motivos": [*motivos_otros, *motivos_colgadas],
        "lados": {
            nombre: {
                "salidas": [
                    {k: s[k] for k in ("salida", "estado", "registro_fiable", "json_completo", "veredicto")}
                    for s in lado["salidas"]
                ],
                "tareas": len(lado["filas"]),
                "resueltas": sum(f["resuelta"] for f in lado["filas"].values()),
                "tareas_colgadas": sorted(_colgadas_del_lado(lado)),
            }
            for nombre, lado in (("base", base), ("otra", otra))
        },
        "pares": {
            "comparables_antes_de_excluir": len(comunes),
            "excluidos": len(excluidos),
            "tareas_excluidas": excluidos,
            "colgadas_sin_par": colgadas_fuera_de_pares,
            "que_quedan": len(quedan),
            "tareas_que_quedan": quedan,
        },
        "huecos_de_cobertura": huecos,
        "tabla": {
            "concordantes": {"ambas_resueltas": ambas, "ninguna_resuelta": ninguna},
            "discordantes": {
                "solo_base": len(solo_base),
                "solo_otra": len(solo_otra),
                "tareas_solo_base": solo_base,
                "tareas_solo_otra": solo_otra,
            },
            "mcnemar_p_exacto": round(mcnemar_exact_p(len(solo_base), len(solo_otra)), 6) if quedan else None,
        },
    }
    return informe, codigo


def _cargar_lista(ruta: Path) -> list[str]:
    try:
        lista = json.loads(ruta.read_text(encoding="utf-8"))["lista"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise CompararError(f"La lista de tareas no se puede leer ({type(exc).__name__}).") from exc
    if (
        not isinstance(lista, list)
        or not all(isinstance(t, str) for t in lista)
        or len(set(lista)) != len(lista)
    ):
        raise CompararError("La «lista» del acta debe ser una lista de textos sin repetidos.")
    return [str(t) for t in lista]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m scripts.kaggle_comparar_pasadas", description=__doc__.split("\n")[0]
    )
    p.add_argument(
        "--base", action="append", type=Path, required=True, help="Salida del lado base; se repite"
    )
    p.add_argument(
        "--otra", action="append", type=Path, required=True, help="Salida del otro lado; se repite"
    )
    p.add_argument(
        "--lista", type=Path, default=None, help="Acta del sorteo: la lista que cada lado debe cubrir"
    )
    args = p.parse_args(argv)
    try:
        lista = None if args.lista is None else _cargar_lista(args.lista)
        informe, codigo = comparar(leer_lado(args.base), leer_lado(args.otra), lista)
    except (CompararError, RegistroError) as exc:
        print(f"ENTRADA INVÁLIDA: {exc}", file=sys.stderr)
        return EXIT_ENTRADA
    print(json.dumps(informe, ensure_ascii=False, indent=1))
    if codigo != EXIT_OK:
        print("COMPARACIÓN NO COMPLETA: " + " | ".join(informe["motivos"]), file=sys.stderr)
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
