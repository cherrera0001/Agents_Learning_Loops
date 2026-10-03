"""Parametros del pre-registro de la linea base A (issue #103, experimento Kaggle Gemma 4).

Lee ``experiments/gemma_developer_agent/preregistro/linea_base_a.json`` y hace cuatro cosas, todas
sin modelo, sin GPU y sin leer el contenido de las tareas (solo biblioteca estandar):

* ``comprobar``: valida el archivo y dice que falta. Es la compuerta del primer recibo: mientras no
  salga con 0 no se corre ninguna replica.
* ``presupuesto``: aplica la formula del presupuesto de tiempo por tarea.
* ``computo``: aplica la escalera de reduccion y da las horas de GPU de cada escalon.
* ``ruido``: dice en que caso de ruido (bajo, intermedio, dominante) cae cada numero de pares
  discordantes observados, para un numero de tareas.

El archivo tiene tres bloques. ``fijos`` son las decisiones del pre-registro; su resumen SHA-256 debe
ser ``FIJOS_SHA256`` y solo cambia con una enmienda declarada. ``abiertos`` son datos que todavia no
existen; cada uno trae la regla que lo determina y quien lo cierra, y se cierra rellenando ``valor``
en un commit propio. ``enmiendas`` es la lista de cambios declarados del pre-registro.

Un parametro cerrado no se cree: se contrasta. Cada archivo citado se comprueba contra su SHA-256 y
contra su esquema; lo que se puede derivar (presupuesto, repositorio reservado, replicas, partes,
``max_output_tokens``, ``eval_config.yaml``) se deriva de los registros y se compara. Ningun archivo
YAML se interpreta: el ``eval_config.yaml`` debe tener exactamente los bytes canonicos.

Codigos de salida de ``comprobar``:

* 0  todo cerrado, coherente y comprobado por completo (con ``--tasks``, con ``--envio`` y con git).
* 1  valido hasta donde se pudo comprobar, pero falta algo: parametros abiertos, o una comprobacion
  que no se hizo (sin ``--tasks``, sin ``--envio`` o con ``--sin-git``). No hay primer recibo.
* 2  archivo invalido, ilegible, con un valor cerrado que contradice su regla, o con una condicion
  que impide abrir la compuerta. «No pude leer» nunca equivale a «todo cerrado».
* 3  error inesperado del propio script.

El documento del pre-registro es ``docs/preregistration/kaggle-baseline-a.md``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from fractions import Fraction
from pathlib import Path, PurePosixPath
from typing import Any

from scripts import kaggle_replicas, kaggle_split

SCHEMA_VERSION = "kaggle-baseline-prereg/2"
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PARAMS = REPO_ROOT / "experiments/gemma_developer_agent/preregistro/linea_base_a.json"
# Resumen del bloque ``fijos`` registrado en el pre-registro. Cambiarlo es una enmienda: exige una
# entrada en ``enmiendas`` y el mismo valor en el documento.
FIJOS_SHA256 = "65afd0bc880a7314d874aeedf8712856038700ee93d6ae367e4754d484c2181c"

EXIT_OK = 0
EXIT_OPEN = 1
EXIT_INVALID = 2
EXIT_UNEXPECTED = 3

SHA_RE = re.compile(r"^[0-9a-f]{64}$")
FECHA_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
ORIGEN_EXCLUSIONES = "calibracion:tareas_invalidas"
BACKENDS = ("docker", "subprocess")
CLASES_VALIDEZ = ("discrimina", "pasa_sin_parche", "dorado_falla", "inestable", "no_medible")
FUENTES_CONCURRENCIA = ("supuesto", "pagina_oficial", "respuesta_organizadores")
OPCIONES_QUE_SIGUEN = ("seguir_excluyendo", "seguir_solo_linea_base")
ESQUEMA_ENSAYO = "kaggle-notebook-trial/1"
ESQUEMA_ENTORNO = "kaggle-sandbox-env/1"
ESQUEMA_VALIDEZ = "kaggle-task-validity/1"
ESQUEMA_PILOTO = "kaggle-pilot/1"
MEDIDAS_TERCILES = ("parche_lineas", "enunciado_caracteres")


class PreregError(ValueError):
    """Archivo de parametros invalido o valor cerrado que contradice su regla."""


# ---------------------------------------------------------------------------
# Formulas (las mismas que describe el documento)
# ---------------------------------------------------------------------------


def _frac(x: object) -> Fraction:
    """Fraccion exacta de un numero JSON (0.1 se lee como 1/10, no como su binario)."""
    if isinstance(x, Fraction):
        return x
    if isinstance(x, bool) or not isinstance(x, int | float) or not math.isfinite(x):
        raise PreregError(f"Se esperaba un numero finito, no {x!r}.")
    return Fraction(str(x))


def slot_minutes(fijos: dict[str, Any]) -> Fraction:
    """Minutos de reloj por tarea que deja el limite del envio: ``T * (1 - reserva) / N``."""
    return _frac(fijos["limite_envio_minutos"]) * (1 - _frac(fijos["reserva"])) / _frac(fijos["tareas_envio"])


def budget_minutes(
    fijos: dict[str, Any], concurrencia: object, carga_modelo: object, montaje_por_tarea: object
) -> int:
    """Presupuesto de tiempo del agente por tarea, en minutos enteros.

    ``b = min(tope, floor(c * (T * (1 - reserva) - m) / N - s))``. Con ``c`` tareas en paralelo y
    todas agotando ``b``, la carga del modelo mas las ``N`` tareas del envio ocupan como mucho
    ``T * (1 - reserva)``. Lanza ``PreregError`` si el resultado queda por debajo del minimo: el
    presupuesto no se rebaja ni se sube a mano.
    """
    if isinstance(concurrencia, bool) or not isinstance(concurrencia, int) or concurrencia < 1:
        raise PreregError(f"La concurrencia debe ser un entero >= 1, no {concurrencia!r}.")
    m, s = _frac(carga_modelo), _frac(montaje_por_tarea)
    if m < 0 or s < 0:
        raise PreregError("La carga del modelo y el montaje por tarea no pueden ser negativos.")
    limite, tareas = _frac(fijos["limite_envio_minutos"]), _frac(fijos["tareas_envio"])
    bruto = concurrencia * (limite * (1 - _frac(fijos["reserva"])) - m) / tareas - s
    b = min(int(fijos["tope_max_time_minutes"]), math.floor(bruto))
    if b < int(fijos["minimo_max_time_minutes"]):
        raise PreregError(
            f"La formula da {b} min por tarea, menos que el minimo de {fijos['minimo_max_time_minutes']}: "
            "el presupuesto no se fija y la compuerta no se abre (decision 'presupuesto_bajo_minimo')."
        )
    return b


def eval_config_bytes(fijos: dict[str, Any], max_time_minutes: int) -> bytes:
    """Bytes canonicos del ``eval_config.yaml`` de la linea base; el archivo debe ser exactamente esto."""
    return (
        "evaluation:\n"
        f"  timeout_seconds: {int(fijos['timeout_seconds'])}\n"
        f"  max_tool_calls: {int(fijos['max_tool_calls'])}\n"
        f"  max_time_minutes: {int(max_time_minutes)}\n"
        f"  max_turns: {int(fijos['max_turns'])}\n"
    ).encode("ascii")


def plan_slots(fijos: dict[str, Any], n_test: int, n_train: int, replicas: int, por_condicion: int) -> int:
    """Corridas de tarea de un escalon: linea base, replicas extra y campana de referencia."""
    slots = (replicas + int(fijos["replicas_extra_maximo"])) * n_test
    if por_condicion > 0:
        slots += int(fijos["pases_entrenamiento"]) * n_train
        slots += int(fijos["condiciones_nuevas"]) * por_condicion * n_test
    return slots


def plan_hours(fijos: dict[str, Any], slots: int) -> Fraction:
    """Cota de horas de L4x4 de ``slots`` corridas de tarea (sin carga del modelo ni verificacion)."""
    return slots * slot_minutes(fijos) / 60


def parse_date(text: object, nombre: str) -> date:
    """Fecha ``AAAA-MM-DD`` real; otra cosa lanza ``PreregError``."""
    if not isinstance(text, str) or not FECHA_RE.fullmatch(text):
        raise PreregError(f"{nombre}: se esperaba una fecha AAAA-MM-DD, no {text!r}.")
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise PreregError(f"{nombre}: {text!r} no es una fecha real.") from exc


def quota_resets(inicio: date, fin: date, dia_reinicio: int) -> int:
    """Reinicios de cuota (dia ISO 1 = lunes ... 7 = domingo) entre ``inicio`` y ``fin``, inclusive."""
    if not 1 <= dia_reinicio <= 7:
        raise PreregError(f"dia_reinicio debe estar entre 1 y 7, no {dia_reinicio!r}.")
    return sum(
        1
        for i in range(max(0, (fin - inicio).days + 1))
        if (inicio + timedelta(days=i)).isoweekday() == dia_reinicio
    )


def usable_hours(fijos: dict[str, Any], cuota_semanal: object, factor: object, reinicios: int) -> Fraction:
    """Horas de L4x4 utilizables: ``fraccion * (cuota / factor) * reinicios``."""
    f = _frac(factor)
    if f <= 0:
        raise PreregError("El factor de cuota debe ser mayor que 0.")
    return _frac(fijos["fraccion_utilizable"]) * _frac(cuota_semanal) / f * reinicios


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
    if any(isinstance(n, bool) or not isinstance(n, int) or n < 0 for n in validas_por_repo.values()):
        raise PreregError("Los conteos de tareas validas deben ser enteros >= 0.")
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


def session_parts(
    n_test: int, concurrencia: int, b: int, m: object, s: object, sesion_max_horas: object
) -> int:
    """Partes en que se divide una replica: 1 salvo que no quepa en una sesion.

    Duracion de la replica en el caso peor: ``m + n * (b + 2 * s) / c`` minutos (montaje y verificacion
    cuestan ``s`` cada uno). Partes = ``ceil(duracion / sesion_max)``.
    """
    minutos = _frac(m) + Fraction(n_test, concurrencia) * (b + 2 * _frac(s))
    sesion = _frac(sesion_max_horas) * 60
    if sesion <= 0:
        raise PreregError("La duracion maxima de sesion debe ser mayor que 0.")
    return max(1, math.ceil(minutos / sesion))


def noise_case(fijos: dict[str, Any], n: int, diferencia_pares: int | None) -> str:
    """Caso de la regla G2 con ``M* = max(suelo, diferencia minima)`` en pares, comparado con enteros."""
    pares = max(int(fijos["suelo_pares"]), diferencia_pares or 0)
    num_b, den_b = fijos["umbral_ruido_bajo"]
    num_d, den_d = fijos["umbral_ruido_dominante"]
    if pares * den_b <= num_b * n:
        return "bajo"
    return "dominante" if pares * den_d > num_d * n else "intermedio"


def noise_case_for_observed(fijos: dict[str, Any], n: int, discordantes: int) -> str:
    """Caso de G2 si el peor par tiene ``discordantes`` de ``n`` (mismo calculo que el analisis)."""
    par = {"comparables": n, "discordantes": discordantes, "replicas": [1, 2]}
    margen = kaggle_replicas._margin([par], [], float(fijos["alfa"]))
    pares = [x["diferencia_pares"] for x in margen["por_discordantes"] if x["alcanzable"]]
    return noise_case(fijos, n, max(pares) if pares else None)


# ---------------------------------------------------------------------------
# Lectura y validacion de forma
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


def sha256_bytes(data: bytes) -> str:
    """SHA-256 de unos bytes."""
    return hashlib.sha256(data).hexdigest()


def fijos_digest(fijos: dict[str, Any]) -> str:
    """SHA-256 del bloque ``fijos`` en JSON canonico: cambia si cambia cualquier decision fijada."""
    canon = json.dumps(fijos, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return sha256_bytes(canon.encode("utf-8"))


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


def _is_date(v: object) -> bool:
    try:
        parse_date(v, "fecha")
    except PreregError:
        return False
    return True


def _is_path(v: object) -> bool:
    """Ruta relativa en formato POSIX, dentro del repositorio: sin ``..``, sin raiz y sin ``\\``."""
    if not isinstance(v, str) or not v or "\\" in v or ":" in v:
        return False
    p = PurePosixPath(v)
    return not p.is_absolute() and ".." not in p.parts and str(p) == v


def _is_fraction_pair(v: object) -> bool:
    return isinstance(v, list) and len(v) == 2 and _is_int(v[0], 1) and _is_int(v[1], 1) and v[0] < v[1]


def _check_escalera(v: object) -> bool:
    return (
        isinstance(v, list)
        and bool(v)
        and all(
            isinstance(e, list) and len(e) == 3 and _is_text(e[0]) and _is_int(e[1], 2) and _is_int(e[2], 0)
            for e in v
        )
    )


def _check_decisiones(v: object) -> bool:
    return (
        isinstance(v, dict)
        and bool(v)
        and all(
            _is_text(k) and isinstance(ops, list) and bool(ops) and all(_is_text(o) for o in ops)
            for k, ops in v.items()
        )
    )


def _check_terciles(v: object) -> bool:
    return (
        isinstance(v, dict)
        and set(v) == set(MEDIDAS_TERCILES)
        and all(
            isinstance(c, list) and len(c) == 2 and _is_int(c[0], 0) and _is_int(c[1], 0) and c[0] <= c[1]
            for c in v.values()
        )
    )


Validador = Callable[[Any], bool]


def _shape(spec: dict[str, Validador], *, extra: bool = False) -> Validador:
    """Validador de un objeto con las claves de ``spec`` (exactamente esas, salvo ``extra``)."""

    def ok(v: Any) -> bool:
        if not isinstance(v, dict):
            return False
        if (set(v) != set(spec)) if not extra else not set(spec) <= set(v):
            return False
        return all(f(v[k]) for k, f in spec.items())

    return ok


FIJOS: dict[str, Validador] = {
    "limite_envio_minutos": lambda v: _is_int(v, 1),
    "tareas_envio": lambda v: _is_int(v, 1),
    "tareas_publicas": lambda v: _is_int(v, 1),
    "reserva": lambda v: _is_num(v, 0) and v < 1,
    "tope_max_time_minutes": lambda v: _is_int(v, 1),
    "minimo_max_time_minutes": lambda v: _is_int(v, 1),
    "max_tool_calls": lambda v: _is_int(v, 1),
    "max_turns": lambda v: _is_int(v, 1),
    "timeout_seconds": lambda v: _is_int(v, 1),
    "max_output_tokens_candidatos": lambda v: (
        isinstance(v, list) and bool(v) and all(_is_int(x, 1) for x in v)
    ),
    "viabilidad_turnos_minimos": lambda v: _is_int(v, 1),
    "pilotos_maximo": lambda v: _is_int(v, 1),
    "piloto_tareas_maximo": lambda v: _is_int(v, 1),
    "alfa": lambda v: _is_num(v, 0, strict=True) and v < 1,
    "suelo_pares": lambda v: _is_int(v, 1),
    "replicas_minimo": lambda v: _is_int(v, 2),
    "replicas_extra_maximo": lambda v: _is_int(v, 0),
    "regla_particion": lambda v: v == "leave_one_repo_out",
    "min_tareas_prueba": lambda v: _is_int(v, 1),
    "factor_cuota_l4x4_publicado": lambda v: _is_num(v, 0, strict=True),
    "fraccion_utilizable": lambda v: _is_num(v, 0, strict=True) and v <= 1,
    "pases_entrenamiento": lambda v: _is_int(v, 1),
    "condiciones_nuevas": lambda v: _is_int(v, 1),
    "escalera": _check_escalera,
    "fecha_minima_compuerta": _is_date,
    "fecha_limite_compuerta": _is_date,
    "fecha_limite_recibos": _is_date,
    "fecha_corte_campana": _is_date,
    "fecha_cierre_paper": _is_date,
    "umbral_ruido_bajo": _is_fraction_pair,
    "umbral_ruido_dominante": _is_fraction_pair,
    "umbral_predominio": _is_fraction_pair,
    "terciles": _check_terciles,
    "decisiones": _check_decisiones,
    "tasks_sha256": _is_sha,
}

_ARCHIVO: dict[str, Validador] = {"ruta": _is_path, "sha256": _is_sha}

ABIERTOS: dict[str, Validador] = {
    "ensayo_notebook": _shape(_ARCHIVO),
    "entorno_sandbox": _shape(_ARCHIVO),
    "validez_tareas": _shape(_ARCHIVO),
    "cuota": _shape(
        {
            "gpu_semanal_horas": lambda v: _is_num(v, 0, strict=True),
            "factor_l4x4": lambda v: _is_num(v, 0, strict=True),
            "dia_reinicio": lambda v: _is_int(v, 1) and v <= 7,
            "fuente": _is_text,
            "fecha_lectura": _is_date,
        }
    ),
    "subconjunto": _shape(_ARCHIVO),
    "piloto": _shape(_ARCHIVO),
    "presupuesto": _shape(
        {"eval_config_ruta": _is_path, "eval_config_sha256": _is_sha, "envio_sha256": _is_sha}
    ),
    "corrida": _shape(
        {"replicas": lambda v: _is_int(v, 2), "partes": lambda v: _is_int(v, 1), "fecha_compuerta": _is_date}
    ),
    "decisiones_dueno": lambda v: (
        isinstance(v, list)
        and all(
            _shape({"decision": _is_text, "opcion": _is_text, "fecha": _is_date, "referencia": _is_text})(x)
            for x in v
        )
    ),
}
# Cada parametro solo puede cerrarse cuando estos otros ya estan cerrados.
REQUISITOS: dict[str, tuple[str, ...]] = {
    "ensayo_notebook": (),
    "entorno_sandbox": ("ensayo_notebook",),
    "validez_tareas": ("entorno_sandbox",),
    "cuota": (),
    "subconjunto": ("validez_tareas", "cuota"),
    "piloto": ("subconjunto",),
    "presupuesto": ("piloto",),
    "corrida": ("presupuesto",),
    "decisiones_dueno": (),  # una decision se puede versionar en cuanto se toma
}

ENSAYO: dict[str, Validador] = {
    "schema_version": lambda v: v == ESQUEMA_ENSAYO,
    "fecha": _is_date,
    "notebook": _is_text,
    "modelo": _is_text,
    "guion_servidor_sha256": _is_sha,
    "docker_disponible": lambda v: isinstance(v, bool),
    "backend": lambda v: v in BACKENDS,
    "servidor_arranca": lambda v: isinstance(v, bool),
    "envio_compila": lambda v: isinstance(v, bool),
    "carga_modelo_segundos": lambda v: _is_num(v, 0),
    "sesion_max_horas": lambda v: _is_num(v, 0, strict=True),
    "tokens_por_segundo": lambda v: _is_num(v, 0),
    "max_time_minutes_ensayo": lambda v: _is_int(v, 1),
    "turnos_por_tarea": lambda v: isinstance(v, list) and bool(v) and all(_is_int(x, 0) for x in v),
    "peticiones_al_modelo": lambda v: _is_int(v, 0),
    "rechazos_por_contexto": lambda v: (
        isinstance(v, dict) and bool(v) and all(k.isdigit() and _is_int(n, 0) for k, n in v.items())
    ),
}
ENTORNO: dict[str, Validador] = {
    "schema_version": lambda v: v == ESQUEMA_ENTORNO,
    "ensayo_sha256": _is_sha,
    "backend": lambda v: v in BACKENDS,
    "imagen": _is_text,
    "version_arnes": _is_text,
    "ruedas_sha256": _is_sha,
    "arreglos": lambda v: isinstance(v, list) and all(_is_text(x) for x in v),
}
TAREA_VALIDEZ: dict[str, Validador] = {
    "instance_id": _is_text,
    "repo": _is_text,
    "clase": lambda v: v in CLASES_VALIDEZ,
    "sin_parche_segundos": lambda v: isinstance(v, list) and all(_is_num(x, 0) for x in v),
}
VALIDEZ: dict[str, Validador] = {
    "schema_version": lambda v: v == ESQUEMA_VALIDEZ,
    "sha256_tasks": _is_sha,
    "entorno_sha256": _is_sha,
    "tareas": lambda v: isinstance(v, list) and all(_shape(TAREA_VALIDEZ, extra=True)(x) for x in v),
    "tareas_invalidas": lambda v: (
        isinstance(v, list) and all(_shape({"instance_id": _is_text, "clase": _is_text})(x) for x in v)
    ),
}
PILOTO: dict[str, Validador] = {
    "schema_version": lambda v: v == ESQUEMA_PILOTO,
    "fecha": _is_date,
    "numero": lambda v: _is_int(v, 1),
    "subconjunto_sha256": _is_sha,
    "tareas": lambda v: _is_int(v, 1),
    "degenerado": lambda v: isinstance(v, bool),
    "concurrencia": lambda v: _is_int(v, 1),
    "fuente_concurrencia": _shape({"tipo": lambda v: v in FUENTES_CONCURRENCIA, "referencia": _is_text}),
    "carga_modelo_segundos": lambda v: _is_num(v, 0),
    "prompt_muestra_presupuesto": lambda v: isinstance(v, bool),
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
    if set(data) != {"schema_version", "fijos", "abiertos", "enmiendas"}:
        return [
            f"Primer nivel: se esperaban schema_version, fijos, abiertos y enmiendas; hay {sorted(data)}."
        ]
    if data["schema_version"] != SCHEMA_VERSION:
        problems.append(f"schema_version {data['schema_version']!r}, se esperaba {SCHEMA_VERSION!r}.")
    fijos, abiertos, enmiendas = data["fijos"], data["abiertos"], data["enmiendas"]
    if not isinstance(fijos, dict) or set(fijos) != set(FIJOS):
        claves = sorted(fijos) if isinstance(fijos, dict) else fijos
        problems.append(f"'fijos' debe tener exactamente las claves {sorted(FIJOS)}; tiene {claves}.")
    else:
        problems.extend(
            f"fijos.{k}: valor invalido {fijos[k]!r}." for k, ok in FIJOS.items() if not ok(fijos[k])
        )
        if not problems:
            problems.extend(_check_fijos_coherentes(fijos))
    ok_enmienda = _shape({"fecha": _is_date, "motivo": _is_text, "commit": _is_text})
    if not isinstance(enmiendas, list) or not all(ok_enmienda(x) for x in enmiendas):
        problems.append("'enmiendas' debe ser una lista de objetos con fecha, motivo y commit.")
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


def _check_fijos_coherentes(fijos: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    if fijos["minimo_max_time_minutes"] > fijos["tope_max_time_minutes"]:
        problems.append("fijos: el minimo del presupuesto supera al tope.")
    bajo, dominante = (Fraction(*fijos[k]) for k in ("umbral_ruido_bajo", "umbral_ruido_dominante"))
    if bajo >= dominante:
        problems.append("fijos: umbral_ruido_bajo debe ser menor que umbral_ruido_dominante.")
    fechas = [
        parse_date(fijos[k], k)
        for k in (
            "fecha_minima_compuerta",
            "fecha_limite_compuerta",
            "fecha_limite_recibos",
            "fecha_corte_campana",
            "fecha_cierre_paper",
        )
    ]
    minima, lim_compuerta, lim_recibos, corte, cierre = fechas
    if not (minima <= lim_compuerta < lim_recibos < corte < cierre):
        problems.append("fijos: fechas: minima <= limite de compuerta < limite de recibos < corte < cierre.")
    repos = {e[0] for e in fijos["escalera"]}
    if len({tuple(e) for e in fijos["escalera"]}) != len(fijos["escalera"]):
        problems.append("fijos: la escalera repite un escalon.")
    if any(e[1] < fijos["replicas_minimo"] for e in fijos["escalera"]):
        problems.append("fijos: la escalera tiene un escalon con menos replicas que el minimo.")
    for repo in sorted(repos):
        if not any(e[0] == repo and e[2] == 0 for e in fijos["escalera"]):
            problems.append(f"fijos: la escalera no tiene el escalon sin campana de {repo!r}.")
    return problems


def open_parameters(data: dict[str, Any]) -> list[str]:
    """Nombres de los parametros que siguen abiertos (``valor`` nulo), en orden."""
    return [k for k in ABIERTOS if data["abiertos"][k]["valor"] is None]


# ---------------------------------------------------------------------------
# Contraste de los parametros cerrados
# ---------------------------------------------------------------------------


def _read_cited(raiz: Path, ruta: str, sha: str, nombre: str) -> bytes:
    """Bytes de un archivo citado, tras comprobar que existe y que su SHA-256 es el declarado."""
    path = raiz / ruta
    if not path.is_file():
        raise PreregError(f"{nombre}: no existe el archivo {ruta}.")
    data = path.read_bytes()
    real = sha256_bytes(data)
    if real != sha:
        raise PreregError(f"{nombre}: el SHA-256 de {ruta} es {real}, no el declarado {sha}.")
    return data


def _read_record(
    raiz: Path, valor: dict[str, Any], nombre: str, esquema: dict[str, Validador]
) -> dict[str, Any]:
    """Registro JSON citado: hash, JSON estricto y esquema (claves exactas y valores validos)."""
    data = _read_cited(raiz, valor["ruta"], valor["sha256"], nombre)
    try:
        obj = loads_strict(data.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise PreregError(f"{nombre}: {valor['ruta']} no es JSON valido: {exc}") from exc
    if not isinstance(obj, dict):
        raise PreregError(f"{nombre}: {valor['ruta']} debe ser un objeto JSON.")
    if set(obj) != set(esquema):
        raise PreregError(
            f"{nombre}: {valor['ruta']} debe tener las claves {sorted(esquema)}; tiene {sorted(obj)}."
        )
    malos = sorted(k for k, ok in esquema.items() if not ok(obj[k]))
    if malos:
        raise PreregError(f"{nombre}: valores invalidos en {valor['ruta']}: {malos}.")
    return obj


def cited_paths(data: dict[str, Any]) -> dict[str, str]:
    """Ruta citada por cada parametro cerrado que cita un archivo: ``{papel: ruta}``."""
    out: dict[str, str] = {}
    for nombre in ABIERTOS:
        v = data["abiertos"][nombre]["valor"]
        if isinstance(v, dict):
            for clave in ("ruta", "eval_config_ruta"):
                if clave in v:
                    out[nombre] = v[clave]
    return out


def git_problems(raiz: Path, rutas: Sequence[str]) -> list[str]:
    """Archivos citados que no estan commiteados tal cual en el repositorio de ``raiz``."""
    problems: list[str] = []
    for ruta in rutas:
        try:
            seguido = subprocess.run(
                ["git", "ls-files", "--error-unmatch", "--", ruta], cwd=raiz, capture_output=True, text=True
            )
            estado = subprocess.run(
                ["git", "status", "--porcelain", "--", ruta], cwd=raiz, capture_output=True, text=True
            )
        except OSError as exc:
            return [f"No se pudo ejecutar git en {raiz}: {exc}"]
        if seguido.returncode != 0 or estado.returncode != 0:
            problems.append(f"{ruta}: no esta versionado en git.")
        elif estado.stdout.strip():
            problems.append(f"{ruta}: tiene cambios sin commitear.")
    return problems


def _ceil_minutes(segundos: object, paso: Fraction) -> Fraction:
    """Minutos, redondeados hacia arriba al multiplo de ``paso``."""
    return math.ceil(_frac(segundos) / 60 / paso) * paso


def setup_minutes(validez: dict[str, Any]) -> Fraction:
    """``s``: media de la verificacion sin parche de las tareas ``discrimina``, hacia arriba a 0,1 min."""
    medias = [
        Fraction(sum(_frac(x) for x in t["sin_parche_segundos"]), len(t["sin_parche_segundos"]))
        for t in validez["tareas"]
        if t["clase"] == "discrimina" and t["sin_parche_segundos"]
    ]
    if not medias:
        raise PreregError("validez_tareas: ninguna tarea 'discrimina' tiene duracion sin parche.")
    return _ceil_minutes(sum(medias) / len(medias), Fraction(1, 10))


def output_tokens(fijos: dict[str, Any], ensayo: dict[str, Any]) -> int:
    """``max_output_tokens``: el primer candidato sin rechazos por contexto en el ensayo."""
    for candidato in fijos["max_output_tokens_candidatos"]:
        rechazos = ensayo["rechazos_por_contexto"].get(str(candidato))
        if rechazos is None:
            raise PreregError(
                f"ensayo_notebook: falta el conteo de rechazos con {candidato} tokens de salida."
            )
        if rechazos == 0:
            return int(candidato)
    raise PreregError(
        "ensayo_notebook: hay rechazos por contexto con todos los candidatos de max_output_tokens: la "
        "compuerta no se abre (decision 'rechazos_con_todos_los_candidatos')."
    )


def regenerated_subset(tasks_path: Path, repo: str, invalidas: set[str]) -> str:
    """Texto que escribiria ``scripts/kaggle_split.py`` para esa particion (mismo formato que su CLI)."""
    try:
        tasks = kaggle_split._read_tasks(tasks_path)
        result = kaggle_split.split_leave_one_repo_out(
            tasks=tasks,
            held_out_repo=repo,
            excluded_ids=invalidas,
            sha256_tasks=kaggle_split.compute_sha256(tasks_path),
        )
    except (OSError, kaggle_split.ParticionError) as exc:
        raise PreregError(f"subconjunto: no se pudo regenerar la particion: {exc}") from exc
    result["rule"]["exclusiones_origen"] = ORIGEN_EXCLUSIONES
    return json.dumps(result, indent=2, ensure_ascii=False)


@dataclass
class Resultado:
    """Lo que encontro ``check_closed``: problemas (salida 2) y comprobaciones no hechas (salida 1)."""

    problemas: list[str]
    pendientes: list[str]


def check_closed(
    data: dict[str, Any],
    raiz: Path,
    *,
    tasks: Path | None = None,
    envio: Path | None = None,
    git: bool = False,
) -> Resultado:
    """Contrasta cada parametro cerrado con su regla. Supone ``check_structure`` sin problemas."""
    fijos: dict[str, Any] = data["fijos"]
    valor: dict[str, Any] = {k: data["abiertos"][k]["valor"] for k in ABIERTOS}
    res = Resultado([], [])
    if fijos_digest(fijos) != FIJOS_SHA256:
        res.problemas.append(
            f"El resumen de 'fijos' es {fijos_digest(fijos)}, no el registrado {FIJOS_SHA256}: cambiar una "
            "decision fijada exige una enmienda declarada."
        )
    rutas = cited_paths(data)
    if len(set(rutas.values())) != len(rutas):
        res.problemas.append(f"Un mismo archivo se cita en dos papeles: {sorted(rutas.values())}.")
    for nombre, requisitos in REQUISITOS.items():
        if valor[nombre] is not None:
            faltan = [r for r in requisitos if valor[r] is None]
            if faltan:
                res.problemas.append(f"{nombre}: no puede cerrarse antes que {', '.join(faltan)}.")
    if res.problemas:
        return res
    try:
        _contrastar(fijos, valor, raiz, tasks, envio, res)
    except PreregError as exc:
        res.problemas.append(str(exc))
    if git:
        res.problemas.extend(git_problems(raiz, sorted(rutas.values())))
    elif rutas:
        res.pendientes.append("no se comprobo que los archivos citados esten commiteados (--sin-git)")
    return res


def _contrastar(
    fijos: dict[str, Any],
    valor: dict[str, Any],
    raiz: Path,
    tasks: Path | None,
    envio: Path | None,
    res: Resultado,
) -> None:
    """Deriva y compara, en el orden de cierre. La primera contradiccion lanza ``PreregError``."""
    necesarias: dict[str, str] = {}  # decision -> opcion que permite seguir
    if valor["ensayo_notebook"] is None:
        return
    ensayo = _read_record(raiz, valor["ensayo_notebook"], "ensayo_notebook", ENSAYO)
    turnos = ensayo["turnos_por_tarea"]
    viables = sum(1 for t in turnos if t >= fijos["viabilidad_turnos_minimos"])
    if not (ensayo["servidor_arranca"] and ensayo["envio_compila"]) or 2 * viables < len(turnos):
        raise PreregError(
            "ensayo_notebook: el ensayo no es viable (el servidor no arranca, el envio no compila o el "
            "agente no completa "
            f"{fijos['viabilidad_turnos_minimos']} turnos en al menos la mitad de las tareas): la compuerta "
            "no se abre (decision 'ensayo_no_viable')."
        )
    if ensayo["backend"] == "docker" and not ensayo["docker_disponible"]:
        raise PreregError("ensayo_notebook: el backend es docker pero el notebook no tiene Docker.")
    output_tokens(fijos, ensayo)  # lanza si hay rechazos por contexto con todos los candidatos

    if valor["entorno_sandbox"] is None:
        return
    entorno = _read_record(raiz, valor["entorno_sandbox"], "entorno_sandbox", ENTORNO)
    if entorno["ensayo_sha256"] != valor["ensayo_notebook"]["sha256"]:
        raise PreregError("entorno_sandbox: 'ensayo_sha256' no es el del ensayo de notebook declarado.")
    if entorno["backend"] != ensayo["backend"]:
        raise PreregError("entorno_sandbox: el backend no es el que fijo el ensayo de notebook.")

    if valor["validez_tareas"] is None:
        return
    validez = _read_record(raiz, valor["validez_tareas"], "validez_tareas", VALIDEZ)
    if validez["sha256_tasks"] != fijos["tasks_sha256"]:
        raise PreregError("validez_tareas: 'sha256_tasks' no es el tasks_sha256 del pre-registro.")
    if validez["entorno_sha256"] != valor["entorno_sandbox"]["sha256"]:
        raise PreregError("validez_tareas: 'entorno_sha256' no es el del entorno declarado.")
    ids = [t["instance_id"] for t in validez["tareas"]]
    if len(ids) != fijos["tareas_publicas"] or len(set(ids)) != len(ids):
        raise PreregError(
            f"validez_tareas: debe haber {fijos['tareas_publicas']} tareas distintas; hay {len(ids)} "
            f"({len(set(ids))} distintas)."
        )
    invalidas = {t["instance_id"]: t["clase"] for t in validez["tareas"] if t["clase"] != "discrimina"}
    if {x["instance_id"]: x["clase"] for x in validez["tareas_invalidas"]} != invalidas or len(
        validez["tareas_invalidas"]
    ) != len(invalidas):
        raise PreregError(
            "validez_tareas: 'tareas_invalidas' no es la lista de tareas cuya clase no es 'discrimina'."
        )
    por_repo: dict[str, list[str]] = {}
    for t in validez["tareas"]:
        por_repo.setdefault(t["repo"], []).append(t["clase"])
    if any(len(c) >= 10 and 2 * sum(1 for x in c if x != "discrimina") > len(c) for c in por_repo.values()):
        necesarias["entorno_sin_arreglo"] = "seguir_excluyendo"
    validas = {repo: sum(1 for x in c if x == "discrimina") for repo, c in por_repo.items()}
    escalones = ladder(fijos, validas)

    if valor["subconjunto"] is None:
        return
    cuota = valor["cuota"]
    corte = parse_date(fijos["fecha_corte_campana"], "fecha_corte_campana")
    minima = parse_date(fijos["fecha_minima_compuerta"], "fecha_minima_compuerta")
    if parse_date(cuota["fecha_lectura"], "cuota.fecha_lectura") > corte:
        raise PreregError("cuota: la fecha de lectura es posterior al corte de la campana.")
    horas_c4 = usable_hours(
        fijos,
        cuota["gpu_semanal_horas"],
        cuota["factor_l4x4"],
        quota_resets(minima, corte, cuota["dia_reinicio"]),
    )
    paso = choose_step(escalones, horas_c4)
    if paso is None:
        raise PreregError(
            f"subconjunto: ningun escalon apto cabe en {float(horas_c4):.2f} h utilizables de L4x4: no hay "
            "subconjunto que fijar y la compuerta no se abre (decision 'sin_escalon')."
        )
    texto = _read_cited(raiz, valor["subconjunto"]["ruta"], valor["subconjunto"]["sha256"], "subconjunto")
    sub = _parse_subset(texto, fijos, paso, set(invalidas), validas)
    if tasks is None:
        res.pendientes.append("no se regenero la particion desde tasks.jsonl (--tasks)")
    else:
        if kaggle_split.compute_sha256(tasks) != fijos["tasks_sha256"]:
            raise PreregError("subconjunto: el archivo de --tasks no tiene el tasks_sha256 del pre-registro.")
        if regenerated_subset(tasks, paso.repo, set(invalidas)).encode("utf-8") != texto:
            raise PreregError(
                "subconjunto: el archivo no coincide byte a byte con lo que genera scripts/kaggle_split.py."
            )

    if valor["piloto"] is None:
        return
    piloto = _read_record(raiz, valor["piloto"], "piloto", PILOTO)
    if piloto["subconjunto_sha256"] != valor["subconjunto"]["sha256"]:
        raise PreregError("piloto: 'subconjunto_sha256' no es el del subconjunto declarado.")
    if piloto["numero"] > fijos["pilotos_maximo"] or piloto["tareas"] > fijos["piloto_tareas_maximo"]:
        raise PreregError("piloto: supera el numero maximo de pilotos o de tareas por piloto.")
    if piloto["degenerado"] or not piloto["prompt_muestra_presupuesto"]:
        raise PreregError(
            "piloto: el piloto es degenerado o el prompt no muestra el presupuesto pasado: la compuerta "
            "no se abre (decision 'piloto_degenerado')."
        )
    c = piloto["concurrencia"]
    if c > 1 and piloto["fuente_concurrencia"]["tipo"] == "supuesto":
        raise PreregError("piloto: una concurrencia mayor que 1 exige una fuente oficial; sin fuente, c = 1.")
    m = _ceil_minutes(piloto["carga_modelo_segundos"], Fraction(1))
    s = setup_minutes(validez)
    b = budget_minutes(fijos, c, m, s)

    if valor["presupuesto"] is None:
        return
    pre = valor["presupuesto"]
    if _read_cited(
        raiz, pre["eval_config_ruta"], pre["eval_config_sha256"], "presupuesto"
    ) != eval_config_bytes(fijos, b):
        raise PreregError(
            f"presupuesto: {pre['eval_config_ruta']} no tiene exactamente los bytes canonicos para "
            f"max_time_minutes = {b} (la formula) y los limites fijados."
        )
    if envio is None:
        res.pendientes.append("no se recalculo el hash del envio (--envio)")
    else:
        try:
            real = kaggle_replicas.sha256_directory(envio)
        except kaggle_replicas.ReplicasError as exc:
            raise PreregError(f"presupuesto: {exc}") from exc
        if real != pre["envio_sha256"]:
            raise PreregError(
                f"presupuesto: el hash del envio es {real}, no el declarado {pre['envio_sha256']}."
            )
        if (envio / "eval_config.yaml").read_bytes() != eval_config_bytes(fijos, b):
            raise PreregError("presupuesto: el eval_config.yaml del envio no es el canonico.")

    if valor["corrida"] is None:
        return
    corrida = valor["corrida"]
    fecha = parse_date(corrida["fecha_compuerta"], "corrida.fecha_compuerta")
    if fecha > parse_date(fijos["fecha_limite_recibos"], "fecha_limite_recibos"):
        raise PreregError("corrida: la compuerta es posterior al limite de recibos de la linea base.")
    if fecha > parse_date(fijos["fecha_limite_compuerta"], "fecha_limite_compuerta"):
        necesarias["compuerta_tardia"] = "seguir_solo_linea_base"
    horas_c5 = usable_hours(
        fijos,
        cuota["gpu_semanal_horas"],
        cuota["factor_l4x4"],
        quota_resets(fecha, corte, cuota["dia_reinicio"]),
    )
    final = choose_step([e for e in escalones if e.repo == paso.repo], horas_c5)
    if final is None:
        raise PreregError(
            f"corrida: ni la linea base sola de {paso.repo!r} cabe en {float(horas_c5):.2f} h utilizables: "
            "la compuerta no se abre (decision 'sin_escalon')."
        )
    if final.por_condicion == 0:
        necesarias["campana_no_cabe"] = "seguir_solo_linea_base"
    if corrida["replicas"] != final.replicas:
        raise PreregError(
            f"corrida: se declaran {corrida['replicas']} replicas; la escalera da {final.replicas}."
        )
    partes = session_parts(len(sub["test"]), c, b, m, s, ensayo["sesion_max_horas"])
    if corrida["partes"] != partes:
        raise PreregError(
            f"corrida: se declaran {corrida['partes']} partes por replica; la regla da {partes}."
        )

    if valor["decisiones_dueno"] is None:
        return
    tomadas: dict[str, str] = {}
    for d in valor["decisiones_dueno"]:
        if d["decision"] not in fijos["decisiones"] or d["opcion"] not in fijos["decisiones"][d["decision"]]:
            raise PreregError(
                f"decisiones_dueno: {d['decision']!r} = {d['opcion']!r} no esta entre las opciones."
            )
        if d["decision"] in tomadas:
            raise PreregError(f"decisiones_dueno: la decision {d['decision']!r} aparece dos veces.")
        tomadas[d["decision"]] = d["opcion"]
    for decision, opcion in tomadas.items():
        if opcion not in OPCIONES_QUE_SIGUEN:
            raise PreregError(f"decisiones_dueno: {decision!r} = {opcion!r}: la compuerta no se abre.")
        if decision not in necesarias:
            raise PreregError(f"decisiones_dueno: {decision!r} no corresponde a ninguna condicion presente.")
    faltan = sorted(set(necesarias) - set(tomadas))
    if faltan:
        raise PreregError(f"decisiones_dueno: faltan las decisiones versionadas {faltan}.")


def _parse_subset(
    texto: bytes, fijos: dict[str, Any], paso: Escalon, invalidas: set[str], validas: dict[str, int]
) -> dict[str, Any]:
    """Contrasta el subconjunto con la regla, con la validez y consigo mismo."""
    try:
        sub = loads_strict(texto.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise PreregError(f"subconjunto: no es JSON valido: {exc}") from exc
    regla = sub.get("rule") if isinstance(sub, dict) else None
    if not isinstance(sub, dict) or not isinstance(regla, dict):
        raise PreregError("subconjunto: debe ser un objeto JSON con 'rule'.")
    if regla.get("name") != fijos["regla_particion"]:
        raise PreregError(f"subconjunto: la regla es {regla.get('name')!r}, no {fijos['regla_particion']!r}.")
    if sub.get("sha256_tasks") != fijos["tasks_sha256"]:
        raise PreregError("subconjunto: 'sha256_tasks' no es el tasks_sha256 del pre-registro.")
    if regla.get("exclusiones_origen") != ORIGEN_EXCLUSIONES:
        raise PreregError(
            f"subconjunto: exclusiones_origen es {regla.get('exclusiones_origen')!r}; las exclusiones deben "
            f"salir del archivo de validez ({ORIGEN_EXCLUSIONES!r})."
        )
    if regla.get("excluded_instance_ids") != sorted(invalidas):
        raise PreregError("subconjunto: las tareas excluidas no son las 'tareas_invalidas' de la validez.")
    if regla.get("excluded_ids_inexistentes"):
        raise PreregError("subconjunto: hay exclusiones que no existen en tasks.jsonl.")
    if regla.get("held_out_repo") != paso.repo:
        raise PreregError(
            f"subconjunto: el repositorio reservado es {regla.get('held_out_repo')!r}; "
            f"la escalera da {paso.repo!r}."
        )
    test, train, counts = sub.get("test"), sub.get("train"), sub.get("counts")
    if not all(isinstance(x, list) and all(isinstance(i, str) for i in x) for x in (test, train)):
        raise PreregError("subconjunto: 'test' y 'train' deben ser listas de identificadores.")
    assert isinstance(test, list) and isinstance(train, list)
    if len(set(test)) != len(test) or len(set(train)) != len(train):
        raise PreregError("subconjunto: hay identificadores repetidos en 'test' o en 'train'.")
    if set(test) & set(train) or (set(test) | set(train)) & invalidas:
        raise PreregError("subconjunto: 'test', 'train' y las excluidas deben ser disjuntas.")
    if len(test) != paso.n_test or len(train) != paso.n_train:
        raise PreregError(
            f"subconjunto: se esperaban {paso.n_test} tareas de prueba y {paso.n_train} de entrenamiento; "
            f"hay {len(test)} y {len(train)}."
        )
    if not isinstance(counts, dict):
        raise PreregError("subconjunto: faltan los conteos de 'counts'.")
    try:
        declarados = {repo: fila["total_valid"] for repo, fila in counts["by_repo"].items()}
        totales = (
            counts["total_validas"],
            counts["total_test"],
            counts["total_train"],
            counts["total_excluidas"],
        )
    except (KeyError, TypeError, AttributeError) as exc:
        raise PreregError("subconjunto: faltan los conteos de 'counts'.") from exc
    if declarados != validas or totales != (sum(validas.values()), len(test), len(train), len(invalidas)):
        raise PreregError("subconjunto: 'counts' no coincide con las listas ni con la validez.")
    return sub


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _h(x: Fraction) -> str:
    return f"{float(x):.2f}"


def _valid(path: Path) -> dict[str, Any]:
    data = load_params(path)
    problems = check_structure(data)
    if problems:
        raise PreregError("Parametros del pre-registro:\n- " + "\n- ".join(problems))
    return data


def _cmd_comprobar(args: argparse.Namespace) -> int:
    data = _valid(args.parametros)
    res = check_closed(data, args.raiz, tasks=args.tasks, envio=args.envio, git=not args.sin_git)
    if res.problemas:
        raise PreregError("Parametros del pre-registro:\n- " + "\n- ".join(res.problemas))
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
    if res.pendientes:
        print("Comprobacion parcial; la compuerta no se abre hasta completarla:", file=sys.stderr)
        for p in res.pendientes:
            print(f"- {p}", file=sys.stderr)
        return EXIT_OPEN
    print("Todos los parametros estan cerrados, coinciden con sus reglas y estan commiteados.")
    return EXIT_OK


def _cmd_presupuesto(args: argparse.Namespace) -> int:
    fijos = _valid(args.parametros)["fijos"]
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
    fijos = _valid(args.parametros)["fijos"]
    validas: dict[str, int] = {}
    for item in args.validas:
        repo, sep, n = item.rpartition("=")
        if not sep or not repo or not n.isdigit():
            raise PreregError(f"--validas espera repositorio=numero, no {item!r}.")
        validas[repo] = int(n)
    escalones = ladder(fijos, validas)
    dados = [x is not None for x in (args.cuota, args.dia_reinicio, args.desde)]
    if any(dados) and not all(dados):
        raise PreregError("--cuota, --dia-reinicio y --desde van juntos.")
    factor = args.factor if args.factor is not None else fijos["factor_cuota_l4x4_publicado"]
    print("escalon  repositorio  replicas_A  por_condicion  prueba  entrenamiento  corridas  h_L4x4  h_cuota")
    for i, e in enumerate(escalones, start=1):
        nota = "" if e.apto else f"  (menos de {fijos['min_tareas_prueba']} tareas de prueba: no apto)"
        print(
            f"{i:>7}  {e.repo}  {e.replicas:>10}  {e.por_condicion:>13}  {e.n_test:>6}  {e.n_train:>13}  "
            f"{e.slots:>8}  {_h(e.horas):>6}  {_h(e.horas * _frac(factor)):>7}{nota}"
        )
    if all(dados):
        corte = parse_date(fijos["fecha_corte_campana"], "fecha_corte_campana")
        reinicios = quota_resets(parse_date(args.desde, "--desde"), corte, args.dia_reinicio)
        horas = usable_hours(fijos, args.cuota, factor, reinicios)
        paso = choose_step(escalones, horas)
        print(f"reinicios de cuota hasta el corte: {reinicios}; horas utilizables de L4x4: {_h(horas)}")
        if paso is None:
            print("ningun escalon cabe: la compuerta no se abre")
        else:
            print(
                f"escalon elegido: {escalones.index(paso) + 1} ({paso.repo}, {paso.replicas} replicas de A)"
            )
    return EXIT_OK


def _cmd_ruido(args: argparse.Namespace) -> int:
    fijos = _valid(args.parametros)["fijos"]
    print("tareas  suelo  max_discordantes_ruido_bajo  max_discordantes_ruido_intermedio")
    for n in args.tareas:
        if n < fijos["suelo_pares"]:
            raise PreregError(f"Con {n} tareas el suelo de {fijos['suelo_pares']} pares no es alcanzable.")
        casos = [noise_case_for_observed(fijos, n, d) for d in range(n + 1)]
        bajo = max((d for d, caso in enumerate(casos) if caso == "bajo"), default=None)
        medio = max((d for d, caso in enumerate(casos) if caso != "dominante"), default=None)
        print(f"{n:>6}  {fijos['suelo_pares']}/{n}  {bajo!s:>27}  {medio!s:>33}")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada: ``comprobar``, ``presupuesto``, ``computo`` o ``ruido``."""
    parser = argparse.ArgumentParser(description="Parametros del pre-registro de la linea base A (#103).")
    sub = parser.add_subparsers(dest="comando", required=True)

    def comun(p: argparse.ArgumentParser) -> None:
        p.add_argument("--parametros", type=Path, default=DEFAULT_PARAMS, help="Archivo de parametros.")

    c = sub.add_parser("comprobar", help="Valida el archivo y dice que falta para abrir la compuerta.")
    comun(c)
    c.add_argument("--raiz", type=Path, default=REPO_ROOT, help="Raiz para resolver las rutas citadas.")
    c.add_argument("--tasks", type=Path, default=None, help="tasks.jsonl: regenera la particion y compara.")
    c.add_argument("--envio", type=Path, default=None, help="Directorio del envio: recalcula su hash.")
    c.add_argument("--sin-git", action="store_true", help="No comprobar que los archivos esten commiteados.")
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
    k.add_argument("--factor", type=float, default=None, help="Factor de consumo de L4x4 leido con la cuota.")
    k.add_argument("--dia-reinicio", type=int, default=None, help="Dia ISO del reinicio (1 = lunes).")
    k.add_argument("--desde", default=None, help="Fecha AAAA-MM-DD desde la que se cuentan los reinicios.")
    k.set_defaults(func=_cmd_computo)

    r = sub.add_parser("ruido", help="Discordantes observados que admite cada caso de ruido.")
    comun(r)
    r.add_argument("--tareas", type=int, nargs="+", required=True)
    r.set_defaults(func=_cmd_ruido)

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
