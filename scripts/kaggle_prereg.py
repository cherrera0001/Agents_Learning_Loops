"""Parametros del pre-registro de la linea base A (issue #103, experimento Kaggle Gemma 4).

Lee ``experiments/gemma_developer_agent/preregistro/linea_base_a.json`` y hace tres cosas, todas
sin modelo, sin GPU y sin datos de la competencia (solo biblioteca estandar):

* ``comprobar``: valida el archivo y dice que parametros siguen abiertos. Es la compuerta del primer
  recibo: mientras no salga con 0 no se corre ninguna replica.
* ``presupuesto``: aplica la formula del presupuesto de tiempo por tarea.
* ``computo``: aplica la escalera de reduccion y da las horas de GPU de cada escalon.

El archivo tiene dos bloques. ``fijos`` son las decisiones del pre-registro: no cambian despues del
commit que las introduce. ``abiertos`` son datos que todavia no existen; cada uno trae la regla que
lo determina y quien lo cierra, y se cierra rellenando ``valor`` en un commit propio. Un parametro
cerrado se comprueba contra su regla: el presupuesto contra la formula, el repositorio reservado y
el numero de replicas contra la escalera, y cada archivo citado contra su SHA-256.

Codigos de salida de ``comprobar``:

* 0  archivo valido y sin parametros abiertos.
* 1  archivo valido, pero quedan parametros abiertos (se listan). No hay primer recibo.
* 2  archivo invalido, ilegible o con un valor cerrado que contradice su regla. «No pude leer» nunca
  equivale a «todo cerrado».
* 3  error inesperado del propio script.

El documento del pre-registro es ``docs/preregistration/kaggle-baseline-a.md``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "kaggle-baseline-prereg/1"
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PARAMS = REPO_ROOT / "experiments/gemma_developer_agent/preregistro/linea_base_a.json"

EXIT_OK = 0
EXIT_OPEN = 1
EXIT_INVALID = 2
EXIT_UNEXPECTED = 3

SHA_RE = re.compile(r"^[0-9a-f]{64}$")
FECHA_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
ORIGEN_EXCLUSIONES = "calibracion:tareas_invalidas"
BACKENDS = ("docker", "subprocess")
REPETICIONES_INFRA = ("replica_completa", "tarea")
CLAVES_EVAL_CONFIG = ("max_time_minutes", "max_tool_calls", "max_turns", "timeout_seconds")


class PreregError(ValueError):
    """Archivo de parametros invalido o valor cerrado que contradice su regla."""


# ---------------------------------------------------------------------------
# Formulas (las mismas que describe el documento)
# ---------------------------------------------------------------------------


def _frac(x: object) -> Fraction:
    """Fraccion exacta de un numero JSON (0.1 se lee como 1/10, no como su binario)."""
    if isinstance(x, bool) or not isinstance(x, int | float):
        raise PreregError(f"Se esperaba un numero, no {x!r}.")
    return Fraction(str(x))


def slot_minutes(fijos: dict[str, Any]) -> Fraction:
    """Minutos de reloj por tarea que deja el limite del envio: ``T * (1 - reserva) / N``."""
    return _frac(fijos["limite_envio_minutos"]) * (1 - _frac(fijos["reserva"])) / _frac(fijos["tareas_envio"])


def budget_minutes(
    fijos: dict[str, Any], concurrencia: int, carga_modelo: object, montaje_por_tarea: object
) -> int:
    """Presupuesto de tiempo del agente por tarea, en minutos enteros.

    ``b = min(tope, floor(c * (T - m) * (1 - reserva) / N - s))``. Con ``c`` tareas en paralelo y
    todas agotando ``b``, las ``N`` tareas del envio mas la carga del modelo caben en ``T * (1 -
    reserva)``. Lanza ``PreregError`` si el resultado queda por debajo del minimo: el presupuesto no
    se rebaja a mano.
    """
    if isinstance(concurrencia, bool) or not isinstance(concurrencia, int) or concurrencia < 1:
        raise PreregError(f"La concurrencia debe ser un entero >= 1, no {concurrencia!r}.")
    m, s = _frac(carga_modelo), _frac(montaje_por_tarea)
    if m < 0 or s < 0:
        raise PreregError("La carga del modelo y el montaje por tarea no pueden ser negativos.")
    limite, tareas = _frac(fijos["limite_envio_minutos"]), _frac(fijos["tareas_envio"])
    bruto = concurrencia * (limite - m) * (1 - _frac(fijos["reserva"])) / tareas - s
    b = min(int(fijos["tope_max_time_minutes"]), math.floor(bruto))
    if b < int(fijos["minimo_max_time_minutes"]):
        raise PreregError(
            f"La formula da {b} min por tarea, menos que el minimo de {fijos['minimo_max_time_minutes']}: "
            "el presupuesto no se fija; decide el dueno (ver el pre-registro, seccion D)."
        )
    return b


def plan_slots(fijos: dict[str, Any], n_test: int, n_train: int, replicas: int, por_condicion: int) -> int:
    """Corridas de tarea de un escalon: linea base mas la campana de referencia para el calculo."""
    slots = replicas * n_test
    if por_condicion > 0:
        slots += int(fijos["pases_entrenamiento"]) * n_train
        slots += int(fijos["condiciones_nuevas"]) * por_condicion * n_test
    return slots


def plan_hours(fijos: dict[str, Any], slots: int) -> Fraction:
    """Cota de horas de L4x4 de ``slots`` corridas de tarea (sin carga del modelo ni verificacion)."""
    return slots * slot_minutes(fijos) / 60


def usable_hours(fijos: dict[str, Any], cuota_semanal: object, semanas: int) -> Fraction:
    """Horas de L4x4 utilizables: ``fraccion * (cuota / factor) * semanas``."""
    return (
        _frac(fijos["fraccion_utilizable"])
        * _frac(cuota_semanal)
        / _frac(fijos["factor_cuota_l4x4"])
        * semanas
    )


@dataclass(frozen=True)
class Escalon:
    """Un escalon de la escalera de reduccion, evaluado con los conteos de tareas validas."""

    repo: str
    replicas: int
    por_condicion: int
    n_test: int
    n_train: int
    slots: int
    horas: Fraction
    apto: bool  # el repositorio tiene al menos ``min_tareas_prueba`` tareas validas


def ladder(fijos: dict[str, Any], validas_por_repo: dict[str, int]) -> list[Escalon]:
    """Evalua cada escalon de ``fijos['escalera']`` con las tareas validas por repositorio."""
    total = sum(validas_por_repo.values())
    out: list[Escalon] = []
    for repo, replicas, por_condicion in fijos["escalera"]:
        n_test = validas_por_repo.get(repo, 0)
        slots = plan_slots(fijos, n_test, total - n_test, replicas, por_condicion)
        out.append(
            Escalon(
                repo=repo,
                replicas=replicas,
                por_condicion=por_condicion,
                n_test=n_test,
                n_train=total - n_test,
                slots=slots,
                horas=plan_hours(fijos, slots),
                apto=n_test >= int(fijos["min_tareas_prueba"]),
            )
        )
    return out


def choose_step(escalones: Sequence[Escalon], horas_utilizables: Fraction) -> Escalon | None:
    """Primer escalon apto cuya cota de horas cabe en las horas utilizables; ``None`` si ninguno."""
    for e in escalones:
        if e.apto and e.horas <= horas_utilizables:
            return e
    return None


# ---------------------------------------------------------------------------
# Lectura y validacion
# ---------------------------------------------------------------------------


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        if k in out:
            raise ValueError(f"clave repetida: {k!r}")
        out[k] = v
    return out


def loads_strict(text: str) -> Any:
    """``json.loads`` que rechaza claves repetidas dentro de un objeto."""
    return json.loads(text, object_pairs_hook=_no_duplicates)


def sha256_file(path: Path) -> str:
    """SHA-256 de los bytes de un archivo."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fijos_digest(fijos: dict[str, Any]) -> str:
    """SHA-256 del bloque ``fijos`` en JSON canonico: cambia si cambia cualquier decision fijada."""
    canon = json.dumps(fijos, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _is_int(v: object, minimum: int) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v >= minimum


def _is_num(v: object, minimum: float, *, strict: bool = False) -> bool:
    if isinstance(v, bool) or not isinstance(v, int | float) or not math.isfinite(v):
        return False
    return v > minimum if strict else v >= minimum


def _is_sha(v: object) -> bool:
    return isinstance(v, str) and bool(SHA_RE.fullmatch(v))


def _is_text(v: object) -> bool:
    return isinstance(v, str) and bool(v.strip())


def _check_escalera(v: object) -> bool:
    return (
        isinstance(v, list)
        and bool(v)
        and all(
            isinstance(e, list) and len(e) == 3 and _is_text(e[0]) and _is_int(e[1], 2) and _is_int(e[2], 0)
            for e in v
        )
    )


FIJOS: dict[str, Callable[[Any], bool]] = {
    "limite_envio_minutos": lambda v: _is_int(v, 1),
    "tareas_envio": lambda v: _is_int(v, 1),
    "reserva": lambda v: _is_num(v, 0) and v < 1,
    "tope_max_time_minutes": lambda v: _is_int(v, 1),
    "minimo_max_time_minutes": lambda v: _is_int(v, 1),
    "max_tool_calls": lambda v: _is_int(v, 1),
    "max_turns": lambda v: _is_int(v, 1),
    "timeout_seconds": lambda v: _is_int(v, 1),
    "max_output_tokens_candidatos": lambda v: (
        isinstance(v, list) and bool(v) and all(_is_int(x, 1) for x in v)
    ),
    "alfa": lambda v: _is_num(v, 0, strict=True) and v < 1,
    "replicas_minimo": lambda v: _is_int(v, 2),
    "regla_particion": lambda v: v == "leave_one_repo_out",
    "min_tareas_prueba": lambda v: _is_int(v, 1),
    "factor_cuota_l4x4": lambda v: _is_num(v, 0, strict=True),
    "fraccion_utilizable": lambda v: _is_num(v, 0, strict=True) and v <= 1,
    "pases_entrenamiento": lambda v: _is_int(v, 1),
    "condiciones_nuevas": lambda v: _is_int(v, 1),
    "escalera": _check_escalera,
    "fecha_corte_campana": lambda v: isinstance(v, str) and bool(FECHA_RE.fullmatch(v)),
    "umbral_ruido_bajo": lambda v: _is_num(v, 0, strict=True) and v < 1,
    "umbral_ruido_dominante": lambda v: _is_num(v, 0, strict=True) and v < 1,
    "tasks_sha256": _is_sha,
}


def _shape(spec: dict[str, Callable[[Any], bool]]) -> Callable[[Any], bool]:
    """Validador de un objeto con exactamente las claves de ``spec``."""
    return lambda v: isinstance(v, dict) and set(v) == set(spec) and all(f(v[k]) for k, f in spec.items())


ABIERTOS: dict[str, Callable[[Any], bool]] = {
    "entorno_sandbox": _shape(
        {
            "backend": lambda v: v in BACKENDS,
            "imagen": _is_text,
            "version_arnes": _is_text,
            "declaracion_ruta": _is_text,
            "declaracion_sha256": _is_sha,
        }
    ),
    "validez_tareas": _shape({"ruta": _is_text, "sha256": _is_sha}),
    "cuota": _shape(
        {
            "gpu_semanal_horas": lambda v: _is_num(v, 0, strict=True),
            "semanas": lambda v: _is_int(v, 1),
            "sesion_max_horas": lambda v: _is_num(v, 0, strict=True),
        }
    ),
    "subconjunto": _shape({"ruta": _is_text, "sha256": _is_sha}),
    "replicas": lambda v: _is_int(v, 2),
    "piloto": _shape(
        {
            "concurrencia": lambda v: _is_int(v, 1),
            "fuente_concurrencia": _is_text,
            "carga_modelo_minutos": lambda v: _is_num(v, 0),
            "montaje_por_tarea_minutos": lambda v: _is_num(v, 0),
            "max_output_tokens": lambda v: _is_int(v, 1),
            "registro_ruta": _is_text,
            "registro_sha256": _is_sha,
        }
    ),
    "presupuesto": _shape(
        {
            "max_time_minutes": lambda v: _is_int(v, 1),
            "eval_config_ruta": _is_text,
            "eval_config_sha256": _is_sha,
            "envio_sha256": _is_sha,
        }
    ),
    "repeticion_infra": lambda v: v in REPETICIONES_INFRA,
}


def load_params(path: Path) -> dict[str, Any]:
    """Lee el archivo de parametros; ilegible o mal formado lanza ``PreregError``."""
    if not path.is_file():
        raise PreregError(f"Archivo de parametros no encontrado: {path}")
    try:
        data = loads_strict(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PreregError(f"No se pudo leer {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise PreregError(f"{path} debe ser un objeto JSON.")
    return data


def check_structure(data: dict[str, Any]) -> list[str]:
    """Problemas de forma del archivo (lista vacia = bien formado)."""
    problems: list[str] = []
    if set(data) != {"schema_version", "fijos", "abiertos"}:
        return [f"Claves de primer nivel: se esperaban schema_version, fijos y abiertos; hay {sorted(data)}."]
    if data["schema_version"] != SCHEMA_VERSION:
        problems.append(f"schema_version {data['schema_version']!r}, se esperaba {SCHEMA_VERSION!r}.")
    fijos, abiertos = data["fijos"], data["abiertos"]
    if not isinstance(fijos, dict) or set(fijos) != set(FIJOS):
        claves = sorted(fijos) if isinstance(fijos, dict) else fijos
        problems.append(f"'fijos' debe tener exactamente las claves {sorted(FIJOS)}; tiene {claves}.")
    else:
        problems.extend(
            f"fijos.{k}: valor invalido {fijos[k]!r}." for k, ok in FIJOS.items() if not ok(fijos[k])
        )
        if not problems and fijos["minimo_max_time_minutes"] > fijos["tope_max_time_minutes"]:
            problems.append("fijos: el minimo del presupuesto supera al tope.")
        if not problems and fijos["umbral_ruido_bajo"] >= fijos["umbral_ruido_dominante"]:
            problems.append("fijos: umbral_ruido_bajo debe ser menor que umbral_ruido_dominante.")
    if not isinstance(abiertos, dict) or set(abiertos) != set(ABIERTOS):
        claves = sorted(abiertos) if isinstance(abiertos, dict) else abiertos
        problems.append(f"'abiertos' debe tener exactamente las claves {sorted(ABIERTOS)}; tiene {claves}.")
        return problems
    for nombre, ok in ABIERTOS.items():
        entrada = abiertos[nombre]
        if not isinstance(entrada, dict) or set(entrada) != {"valor", "regla", "cierra"}:
            problems.append(f"abiertos.{nombre}: se esperan exactamente valor, regla y cierra.")
            continue
        if not _is_text(entrada["regla"]) or not _is_text(entrada["cierra"]):
            problems.append(f"abiertos.{nombre}: 'regla' y 'cierra' deben ser texto no vacio.")
        if entrada["valor"] is not None and not ok(entrada["valor"]):
            problems.append(f"abiertos.{nombre}: valor cerrado con forma invalida: {entrada['valor']!r}.")
    return problems


def open_parameters(data: dict[str, Any]) -> list[str]:
    """Nombres de los parametros que siguen abiertos (``valor`` nulo), en orden."""
    return [k for k in ABIERTOS if data["abiertos"][k]["valor"] is None]


def _hashed_file(raiz: Path, ruta: str, sha: str, nombre: str) -> Path:
    """Ruta de un archivo citado, tras comprobar que existe y que su SHA-256 es el declarado."""
    path = raiz / ruta
    if not path.is_file():
        raise PreregError(f"{nombre}: no existe el archivo {ruta}.")
    real = sha256_file(path)
    if real != sha:
        raise PreregError(f"{nombre}: el SHA-256 de {ruta} es {real}, no el declarado {sha}.")
    return path


def _read_hashed_json(raiz: Path, ruta: str, sha: str, nombre: str) -> dict[str, Any]:
    path = _hashed_file(raiz, ruta, sha, nombre)
    try:
        obj = loads_strict(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise PreregError(f"{nombre}: {ruta} no es JSON valido: {exc}") from exc
    if not isinstance(obj, dict):
        raise PreregError(f"{nombre}: {ruta} debe ser un objeto JSON.")
    return obj


def parse_eval_config(text: str) -> dict[str, float]:
    """Lee los numeros bajo ``evaluation:`` de un ``eval_config.yaml`` sencillo (sin anidar mas)."""
    valores: dict[str, float] = {}
    dentro = False
    for cruda in text.splitlines():
        linea = cruda.split("#", 1)[0].rstrip()
        if not linea.strip():
            continue
        if not linea.startswith((" ", "\t")):
            dentro = linea.strip() == "evaluation:"
            continue
        if not dentro:
            continue
        clave, sep, valor = linea.strip().partition(":")
        try:
            numero = float(valor)
        except ValueError:
            numero = math.nan
        if not sep or clave in valores or not math.isfinite(numero):
            raise PreregError(f"eval_config: linea no reconocida o repetida: {cruda!r}")
        valores[clave] = numero
    return valores


def _valid_counts(subset: dict[str, Any]) -> dict[str, int]:
    try:
        by_repo = subset["counts"]["by_repo"]
        counts = {repo: fila["total_valid"] for repo, fila in by_repo.items()}
    except (KeyError, TypeError, AttributeError) as exc:
        raise PreregError("subconjunto: falta counts.by_repo[*].total_valid.") from exc
    if not counts or not all(isinstance(r, str) and _is_int(n, 0) for r, n in counts.items()):
        raise PreregError("subconjunto: counts.by_repo debe dar un entero >= 0 por repositorio.")
    return counts


def check_closed(data: dict[str, Any], raiz: Path) -> list[str]:
    """Contrasta cada parametro cerrado con su regla. Supone ``check_structure`` sin problemas."""
    fijos = data["fijos"]
    valor = {k: data["abiertos"][k]["valor"] for k in ABIERTOS}
    problems: list[str] = []

    def falta(nombre: str, *requisitos: str) -> bool:
        abiertos = [r for r in requisitos if valor[r] is None]
        if abiertos:
            problems.append(f"{nombre}: no puede cerrarse antes que {', '.join(abiertos)}.")
        return bool(abiertos)

    def intenta(fn: Callable[[], None]) -> None:
        try:
            fn()
        except PreregError as exc:
            problems.append(str(exc))

    validez: dict[str, Any] = {}

    def _validez() -> None:
        v = valor["validez_tareas"]
        validez.update(_read_hashed_json(raiz, v["ruta"], v["sha256"], "validez_tareas"))
        invalidas = validez.get("tareas_invalidas")
        if not isinstance(invalidas, list) or not all(
            isinstance(x, dict) and isinstance(x.get("instance_id"), str) for x in invalidas
        ):
            raise PreregError(
                "validez_tareas: falta la lista 'tareas_invalidas' con un instance_id por elemento."
            )
        if validez.get("sha256_tasks") != fijos["tasks_sha256"]:
            raise PreregError("validez_tareas: 'sha256_tasks' no es el tasks_sha256 del pre-registro.")

    elegido: list[Escalon] = []

    def _subconjunto() -> None:
        v = valor["subconjunto"]
        sub = _read_hashed_json(raiz, v["ruta"], v["sha256"], "subconjunto")
        regla = sub.get("rule") if isinstance(sub.get("rule"), dict) else {}
        if regla.get("name") != fijos["regla_particion"]:
            raise PreregError(
                f"subconjunto: la regla es {regla.get('name')!r}, no {fijos['regla_particion']!r}."
            )
        if sub.get("sha256_tasks") != fijos["tasks_sha256"]:
            raise PreregError("subconjunto: 'sha256_tasks' no es el tasks_sha256 del pre-registro.")
        if regla.get("exclusiones_origen") != ORIGEN_EXCLUSIONES:
            raise PreregError(
                f"subconjunto: exclusiones_origen es {regla.get('exclusiones_origen')!r}; las exclusiones "
                f"deben salir del archivo de validez ({ORIGEN_EXCLUSIONES!r})."
            )
        invalidas = sorted(x["instance_id"] for x in validez["tareas_invalidas"])
        if regla.get("excluded_instance_ids") != invalidas:
            raise PreregError(
                "subconjunto: las tareas excluidas no son las 'tareas_invalidas' de la validez."
            )
        if regla.get("excluded_ids_inexistentes"):
            raise PreregError("subconjunto: hay exclusiones que no existen en tasks.jsonl.")
        counts = _valid_counts(sub)
        horas = usable_hours(fijos, valor["cuota"]["gpu_semanal_horas"], valor["cuota"]["semanas"])
        paso = choose_step(ladder(fijos, counts), horas)
        if paso is None:
            raise PreregError(
                f"subconjunto: ningun escalon cabe en {float(horas):.2f} h utilizables de L4x4; "
                "no hay subconjunto que fijar: decide el dueno."
            )
        if regla.get("held_out_repo") != paso.repo:
            raise PreregError(
                f"subconjunto: el repositorio reservado es {regla.get('held_out_repo')!r}; "
                f"la escalera da {paso.repo!r}."
            )
        test = sub.get("test")
        if not isinstance(test, list) or len(test) != paso.n_test:
            raise PreregError(
                "subconjunto: la lista 'test' no tiene las tareas validas del repositorio reservado."
            )
        elegido.append(paso)

    def _replicas() -> None:
        if elegido and valor["replicas"] != elegido[0].replicas:
            raise PreregError(
                f"replicas: se declaran {valor['replicas']}; la escalera da {elegido[0].replicas}."
            )

    def _entorno() -> None:
        v = valor["entorno_sandbox"]
        _hashed_file(raiz, v["declaracion_ruta"], v["declaracion_sha256"], "entorno_sandbox")

    def _piloto() -> None:
        v = valor["piloto"]
        _hashed_file(raiz, v["registro_ruta"], v["registro_sha256"], "piloto")
        if v["max_output_tokens"] not in fijos["max_output_tokens_candidatos"]:
            raise PreregError(
                f"piloto: max_output_tokens debe ser uno de {fijos['max_output_tokens_candidatos']}."
            )

    def _presupuesto() -> None:
        v, p = valor["presupuesto"], valor["piloto"]
        esperado = budget_minutes(
            fijos, p["concurrencia"], p["carga_modelo_minutos"], p["montaje_por_tarea_minutos"]
        )
        if v["max_time_minutes"] != esperado:
            raise PreregError(
                f"presupuesto: se declaran {v['max_time_minutes']} min; la formula da {esperado}."
            )
        path = _hashed_file(raiz, v["eval_config_ruta"], v["eval_config_sha256"], "presupuesto")
        leido = parse_eval_config(path.read_text(encoding="utf-8"))
        debe = {"max_time_minutes": esperado, **{k: fijos[k] for k in CLAVES_EVAL_CONFIG[1:]}}
        if leido != debe:
            raise PreregError(f"presupuesto: {v['eval_config_ruta']} dice {leido}; debe decir {debe}.")

    if valor["entorno_sandbox"] is not None:
        intenta(_entorno)
    if valor["validez_tareas"] is not None and not falta("validez_tareas", "entorno_sandbox"):
        intenta(_validez)
    if (
        valor["subconjunto"] is not None
        and not falta("subconjunto", "validez_tareas", "cuota")
        and not problems
    ):
        intenta(_subconjunto)
    if valor["replicas"] is not None and not falta("replicas", "subconjunto"):
        intenta(_replicas)
    if valor["piloto"] is not None and not falta("piloto", "subconjunto"):
        intenta(_piloto)
    if valor["presupuesto"] is not None and not falta("presupuesto", "piloto"):
        intenta(_presupuesto)
    return problems


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _h(x: Fraction) -> str:
    return f"{float(x):.2f}"


def _cmd_comprobar(args: argparse.Namespace) -> int:
    data = load_params(args.parametros)
    problems = check_structure(data)
    if not problems:
        problems = check_closed(data, args.raiz)
    if problems:
        raise PreregError("Parametros del pre-registro:\n- " + "\n- ".join(problems))
    print(f"fijos_sha256: {fijos_digest(data['fijos'])}")
    abiertos = open_parameters(data)
    for nombre in ABIERTOS:
        print(f"{'ABIERTO' if nombre in abiertos else 'cerrado'}  {nombre}")
    if abiertos:
        print(
            f"Quedan {len(abiertos)} parametros abiertos: no se corre ninguna replica ni se escribe "
            "ningun recibo.",
            file=sys.stderr,
        )
        for nombre in abiertos:
            print(f"- {nombre}: cierra {data['abiertos'][nombre]['cierra']}", file=sys.stderr)
        return EXIT_OPEN
    print("Todos los parametros estan cerrados y coinciden con sus reglas.")
    return EXIT_OK


def _cmd_presupuesto(args: argparse.Namespace) -> int:
    fijos = _fijos_validos(args.parametros)
    print(f"minutos de reloj por tarea que deja el envio: {float(slot_minutes(fijos)):.2f}")
    print("concurrencia  carga_modelo_min  montaje_min  max_time_minutes")
    for c in args.concurrencia:
        for m in args.carga_modelo:
            for s in args.montaje:
                try:
                    b = str(budget_minutes(fijos, c, m, s))
                except PreregError:
                    b = f"< {fijos['minimo_max_time_minutes']} (no se fija)"
                print(f"{c:>12}  {m:>16}  {s:>11}  {b}")
    return EXIT_OK


def _cmd_computo(args: argparse.Namespace) -> int:
    fijos = _fijos_validos(args.parametros)
    validas: dict[str, int] = {}
    for item in args.validas:
        repo, sep, n = item.rpartition("=")
        if not sep or not repo or not n.isdigit():
            raise PreregError(f"--validas espera repositorio=numero, no {item!r}.")
        validas[repo] = int(n)
    escalones = ladder(fijos, validas)
    if (args.cuota is None) != (args.semanas is None):
        raise PreregError("--cuota y --semanas van juntos.")
    horas = usable_hours(fijos, args.cuota, args.semanas) if args.cuota is not None else None
    factor = _frac(fijos["factor_cuota_l4x4"])
    print("escalon  repositorio  replicas_A  por_condicion  prueba  entrenamiento  corridas  h_L4x4  h_cuota")
    for i, e in enumerate(escalones, start=1):
        nota = "" if e.apto else f"  (menos de {fijos['min_tareas_prueba']} tareas de prueba: no apto)"
        print(
            f"{i:>7}  {e.repo}  {e.replicas:>10}  {e.por_condicion:>13}  {e.n_test:>6}  {e.n_train:>13}  "
            f"{e.slots:>8}  {_h(e.horas):>6}  {_h(e.horas * factor):>7}{nota}"
        )
    if horas is not None:
        paso = choose_step(escalones, horas)
        print(f"horas utilizables de L4x4: {_h(horas)}")
        if paso is None:
            print("ningun escalon cabe: decide el dueno")
        else:
            print(
                f"escalon elegido: {escalones.index(paso) + 1} ({paso.repo}, {paso.replicas} replicas de A)"
            )
    return EXIT_OK


def _fijos_validos(path: Path) -> dict[str, Any]:
    data = load_params(path)
    problems = check_structure(data)
    if problems:
        raise PreregError("Parametros del pre-registro:\n- " + "\n- ".join(problems))
    fijos: dict[str, Any] = data["fijos"]
    return fijos


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada: ``comprobar``, ``presupuesto`` o ``computo``."""
    parser = argparse.ArgumentParser(description="Parametros del pre-registro de la linea base A (#103).")
    sub = parser.add_subparsers(dest="comando", required=True)

    def comun(p: argparse.ArgumentParser) -> None:
        p.add_argument("--parametros", type=Path, default=DEFAULT_PARAMS, help="Archivo de parametros.")

    c = sub.add_parser("comprobar", help="Valida el archivo y lista los parametros abiertos.")
    comun(c)
    c.add_argument("--raiz", type=Path, default=REPO_ROOT, help="Raiz para resolver las rutas citadas.")
    c.set_defaults(func=_cmd_comprobar)

    p = sub.add_parser("presupuesto", help="Formula del presupuesto de tiempo por tarea.")
    comun(p)
    p.add_argument("--concurrencia", type=int, nargs="+", default=[1, 2, 4])
    p.add_argument("--carga-modelo", type=float, nargs="+", default=[0, 15, 30], help="Minutos.")
    p.add_argument("--montaje", type=float, nargs="+", default=[0, 1, 2], help="Minutos por tarea.")
    p.set_defaults(func=_cmd_presupuesto)

    k = sub.add_parser("computo", help="Escalera de reduccion con sus horas de GPU.")
    comun(k)
    k.add_argument("--validas", nargs="+", required=True, help="repositorio=numero de tareas validas.")
    k.add_argument("--cuota", type=float, default=None, help="Cuota semanal de GPU, en horas.")
    k.add_argument("--semanas", type=int, default=None, help="Semanas de cuota hasta la fecha de corte.")
    k.set_defaults(func=_cmd_computo)

    args = parser.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")
    try:
        return int(args.func(args))
    except (PreregError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_INVALID
    except Exception as exc:  # error del propio script: nunca se confunde con «cerrado»
        print(f"ERROR INESPERADO: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_UNEXPECTED


if __name__ == "__main__":
    sys.exit(main())
