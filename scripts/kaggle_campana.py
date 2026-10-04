"""Reglas ya fijadas de la campana A/B/C/D (issue #104) y la comprobacion de fuga.

No corre el modelo, no lee tasks.jsonl y no rellena los parametros abiertos. Esos siguen
en null hasta que la linea base (#103) tenga un reporte de replicas con salida 0.

* ``comprobar`` sale con 1 mientras falte un abierto, con 2 si el archivo contradice
  este modulo, y con 0 solo cuando los tres abiertos tienen valor.
* ``fuga`` busca instance_id de prueba dentro de episodios o skills. Salida 2 si hay
  alguno. Es la comprobacion automatica que el pre-registro exige antes de la campana.
* ``desenlace`` aplica la regla de las tres lecturas sobre conteos ya resumidos.

El documento es ``docs/preregistration/kaggle-campaign-abcd.md``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections.abc import Iterable, Sequence
from fractions import Fraction
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "kaggle-campaign-prereg/1"
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PARAMS = REPO_ROOT / "experiments/gemma_developer_agent/preregistro/campana_abcd.json"

EXIT_OK = 0
EXIT_OPEN = 1
EXIT_INVALID = 2
EXIT_UNEXPECTED = 3

INSTRUCCION_D = (
    "Before you apply any skill, locate the code with the graph tools. "
    "Take a symbol that appears in the failing test name or in the traceback and call "
    "get_code_neighbors, search_similar_code, or get_code_subgraph on that symbol. "
    "Read the tool result. Only then follow a skill."
)
FRASE_PLACEBO = "Este párrafo no indica ningún cambio de código."
HERRAMIENTAS_GRAFO = ("get_code_neighbors", "search_similar_code", "get_code_subgraph")
ABIERTOS = ("variacion_a", "subconjunto", "corridas_por_condicion")

_SKIP_DIRS = {".git", "__pycache__", ".venv", "node_modules"}


class CampanaError(Exception):
    """El archivo o los argumentos no cumplen la regla fijada."""


def resuelve_mayoria_estricta(corridas: Sequence[bool]) -> bool:
    """Una tarea queda resuelta si hay mas corridas resueltas que no resueltas.

    Con una corrida, manda esa. Con dos, hacen falta las dos. Un empate no resuelve.
    """

    if not corridas:
        raise CampanaError("mayoria estricta: la tarea no tiene corridas.")
    return sum(corridas) * 2 > len(corridas)


def supera_umbral(diferencia: int, n: int, m_star: Fraction) -> bool:
    """True si ``diferencia / n`` es mayor que ``m_star``. La igualdad no supera."""

    if n <= 0:
        raise CampanaError("el denominador de la tasa tiene que ser positivo.")
    if m_star < 0:
        raise CampanaError("M* no es negativo.")
    return Fraction(diferencia, n) > m_star


def desenlace(diferencia: int, n: int, m_star: Fraction) -> str:
    """``apoyada``, ``sin_diferencia`` o ``refutada``.

    ``diferencia`` es resueltas de la primera condicion menos resueltas de la segunda,
    sobre las mismas ``n`` tareas. Los tres nombres cubren todos los enteros: la
    igualdad con ``M*`` cae en ``sin_diferencia``.
    """

    if supera_umbral(diferencia, n, m_star):
        return "apoyada"
    if supera_umbral(-diferencia, n, m_star):
        return "refutada"
    return "sin_diferencia"


def ids_senuelo(test_ids: Sequence[str], paso: int = 5) -> list[str]:
    """Uno de cada ``paso`` identificadores, en orden lexicografico, empezando por el primero."""

    if paso < 1:
        raise CampanaError("el paso de los senuelos es un entero mayor que cero.")
    return sorted(test_ids)[::paso]


def corridas_d_g6(corridas_disponibles: int, minimo_g2: int) -> int:
    """Aplica G6: reserva B/C al mínimo G2; D sale primero si no cabe todo."""
    if type(corridas_disponibles) is not int or corridas_disponibles < 0:
        raise CampanaError("G6 necesita un entero no negativo de corridas disponibles.")
    if type(minimo_g2) is not int or minimo_g2 < 1:
        raise CampanaError("G6 necesita un mínimo G2 positivo.")
    if corridas_disponibles < 2 * minimo_g2:
        raise CampanaError("G6: no caben los mínimos de B y C; la campaña no se corre.")
    return minimo_g2 if corridas_disponibles >= 3 * minimo_g2 else 0


def texto_placebo(longitud: int, frase: str = FRASE_PLACEBO) -> str:
    """Texto de exactamente ``longitud`` caracteres. No nombra las herramientas de grafo."""

    if longitud < 0:
        raise CampanaError("la longitud del placebo no es negativa.")
    if not frase:
        raise CampanaError("la frase del placebo esta vacia.")
    if any(nombre in frase for nombre in HERRAMIENTAS_GRAFO):
        raise CampanaError("la frase del placebo nombra una herramienta de grafo.")
    repeticiones = longitud // len(frase)
    resto = longitud % len(frase)
    return frase * repeticiones + (" " * resto)


def load_params(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise CampanaError(f"no pude leer {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise CampanaError(f"{path} no es un objeto JSON.")
    return data


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"clave JSON duplicada: {key}")
        result[key] = value
    return result


def validar_fijos(data: dict[str, Any]) -> None:
    if set(data) != {"schema_version", "fijos", "abiertos"}:
        raise CampanaError("el objeto de parametros debe contener solo schema_version, fijos y abiertos.")
    if data.get("schema_version") != SCHEMA_VERSION:
        raise CampanaError(f"schema_version distinto de {SCHEMA_VERSION}.")
    fijos = data.get("fijos")
    if not isinstance(fijos, dict):
        raise CampanaError("falta el bloque fijos.")
    claves_fijas = {
        "particion",
        "hereda_particion",
        "estimador",
        "alfa",
        "exitos_independientes",
        "pases_entrenamiento",
        "redactor_skills",
        "redactor_placebo",
        "frase_placebo",
        "redactor_senuelos",
        "paso_senuelos",
        "minimo_senuelos_para_lectura",
        "instruccion_d",
        "prediccion",
        "orden_reduccion",
    }
    if set(fijos) != claves_fijas:
        raise CampanaError("fijos no tiene exactamente las claves pre-registradas.")
    if type(fijos.get("alfa")) not in (int, float) or fijos["alfa"] != 0.05:
        raise CampanaError("alfa debe ser el número pre-registrado 0.05.")
    for clave in (
        "exitos_independientes",
        "pases_entrenamiento",
        "paso_senuelos",
        "minimo_senuelos_para_lectura",
    ):
        if type(fijos.get(clave)) is not int or fijos[clave] <= 0:
            raise CampanaError(f"{clave} debe ser un entero positivo.")
    for clave in ("hereda_particion", "redactor_skills", "redactor_placebo", "redactor_senuelos"):
        if not isinstance(fijos.get(clave), str) or not fijos[clave]:
            raise CampanaError(f"{clave} debe ser texto no vacío.")
    if fijos.get("orden_reduccion") != ["D", "no_bajar_de_G2"]:
        raise CampanaError("orden_reduccion debe conservar el orden fijado por G6.")
    if fijos.get("particion") != "leave_one_repo_out":
        raise CampanaError("la particion fijada es leave_one_repo_out.")
    if fijos.get("estimador") != "mayoria_estricta":
        raise CampanaError("el estimador fijado es mayoria_estricta.")
    if fijos.get("instruccion_d") != INSTRUCCION_D:
        raise CampanaError("instruccion_d no coincide con el texto de este modulo.")
    if any(nombre not in INSTRUCCION_D for nombre in HERRAMIENTAS_GRAFO):
        raise CampanaError("la instruccion de D no nombra las tres herramientas de grafo.")
    if fijos.get("frase_placebo") != FRASE_PLACEBO:
        raise CampanaError("frase_placebo no coincide con el texto de este modulo.")
    if fijos.get("prediccion") != "H(C, A) no queda apoyada":
        raise CampanaError("la prediccion fijada es una: H(C, A) no queda apoyada.")
    if fijos.get("exitos_independientes") != 3:
        raise CampanaError("hacen falta tres exitos independientes.")
    abiertos = data.get("abiertos")
    if not isinstance(abiertos, dict) or set(abiertos) != set(ABIERTOS):
        raise CampanaError("faltan abiertos: variacion_a, subconjunto, corridas_por_condicion.")


def abiertos_pendientes(data: dict[str, Any]) -> list[str]:
    pendientes = []
    cited_report: dict[str, Any] | None = None
    cited_subset: dict[str, Any] | None = None
    for nombre in ABIERTOS:
        entrada = data["abiertos"][nombre]
        if not isinstance(entrada, dict) or "valor" not in entrada:
            raise CampanaError(f"el abierto {nombre} no tiene valor.")
        if (
            set(entrada) != {"valor", "regla"}
            or not isinstance(entrada["regla"], str)
            or not entrada["regla"]
        ):
            raise CampanaError(f"el abierto {nombre} debe conservar solo valor y regla textual.")
        valor = entrada["valor"]
        if valor is None:
            pendientes.append(nombre)
        elif nombre == "variacion_a":
            if not isinstance(valor, dict) or set(valor) != {"ruta", "sha256"}:
                raise CampanaError("variacion_a debe citar ruta y SHA-256 del reporte A.")
            _validar_cita(valor, "variacion_a")
            reporte = load_params(_repo_path(valor["ruta"]))
            if (
                reporte.get("version_reporte") != "kaggle-replica-analysis/3"
                or reporte.get("completo") is not True
            ):
                raise CampanaError("variacion_a no cita un reporte completo kaggle-replica-analysis/3.")
            if not isinstance(reporte.get("margen"), dict) or reporte["margen"].get("alfa") != 0.05:
                raise CampanaError("variacion_a no conserva el alfa del análisis de réplicas.")
            entrada = reporte.get("entrada")
            margen = reporte["margen"]
            if not isinstance(entrada, dict) or entrada.get("condicion") != "A":
                raise CampanaError("variacion_a no acredita que el reporte corresponde a A.")
            if not isinstance(entrada.get("tareas_subconjunto"), int) or not isinstance(
                margen.get("por_discordantes"), list
            ):
                raise CampanaError("variacion_a carece de tamaño de subconjunto o tabla G2.")
            cited_report = reporte
        elif nombre == "subconjunto":
            if not isinstance(valor, dict) or set(valor) != {"ruta", "sha256"}:
                raise CampanaError("subconjunto debe citar ruta y SHA-256 del archivo versionado.")
            _validar_cita(valor, "subconjunto")
            sub = load_params(_repo_path(valor["ruta"]))
            test_ids_de_subconjunto(sub)
            if (
                not isinstance(sub.get("train"), list)
                or not all(isinstance(i, str) and i for i in sub["train"])
                or len(set(sub["train"])) != len(sub["train"])
                or not isinstance(sub.get("rule"), dict)
            ):
                raise CampanaError("subconjunto debe tener train y regla de partición con procedencia.")
            if sub["rule"].get("name") != "leave_one_repo_out" or not isinstance(
                sub.get("sha256_tasks"), str
            ):
                raise CampanaError("subconjunto no acredita leave_one_repo_out y sha256_tasks.")
            if set(sub["test"]) & set(sub["train"]) or not re.fullmatch(r"[0-9a-f]{64}", sub["sha256_tasks"]):
                raise CampanaError("subconjunto mezcla train/test o tiene sha256_tasks inválido.")
            tasks_path = REPO_ROOT / "experiments/gemma_developer_agent/data/tasks.jsonl"
            _assert_tracked_clean(tasks_path, "tasks.jsonl")
            try:
                tasks_bytes = tasks_path.read_bytes()
            except OSError as exc:
                raise CampanaError(
                    f"no se puede validar la partición sin tasks.jsonl público: {exc}"
                ) from exc
            if hashlib.sha256(tasks_bytes).hexdigest() != sub["sha256_tasks"]:
                raise CampanaError(
                    "subconjunto sha256_tasks no coincide con el tasks.jsonl público versionado."
                )
            source_tasks = cargar_tareas_publicas(tasks_path)
            excluded = sub["rule"].get("excluded_instance_ids")
            if (
                not isinstance(excluded, list)
                or not all(isinstance(i, str) and i for i in excluded)
                or len(set(excluded)) != len(excluded)
                or sub["rule"].get("exclusiones_origen") != "calibracion:tareas_invalidas"
            ):
                raise CampanaError(
                    "la regla debe declarar exclusiones únicas desde calibracion:tareas_invalidas."
                )
            if sub["rule"].get("excluded_ids_inexistentes") != []:
                raise CampanaError("la partición declara exclusiones inexistentes en tasks.jsonl.")
            if set(sub["test"]) | set(sub["train"]) | set(excluded) != set(source_tasks):
                raise CampanaError(
                    "train/test/exclusiones no particionan exactamente los IDs de tasks.jsonl."
                )
            if set(excluded) & (set(sub["test"]) | set(sub["train"])):
                raise CampanaError("las tareas excluidas aparecen también en train o test.")
            calibration_path = (
                REPO_ROOT / "experiments/gemma_developer_agent/calibracion/validez_tareas_v1.json"
            )
            _assert_tracked_clean(calibration_path, "calibración de validez")
            calibration = load_params(calibration_path)
            if (
                calibration.get("schema_version") != "kaggle-task-validity/1"
                or calibration.get("sha256_tasks") != sub["sha256_tasks"]
            ):
                raise CampanaError(
                    "la calibración de validez no acredita el esquema y tasks.jsonl del subconjunto."
                )
            validity_tasks = calibration.get("tareas")
            invalid_rows = calibration.get("tareas_invalidas")
            if not isinstance(validity_tasks, list) or not isinstance(invalid_rows, list):
                raise CampanaError("la calibración de validez no contiene tareas y tareas_invalidas.")
            declared_invalid = {row.get("instance_id") for row in invalid_rows if isinstance(row, dict)}
            calculated_invalid = {
                row.get("instance_id")
                for row in validity_tasks
                if isinstance(row, dict) and row.get("clase") != "discrimina"
            }
            if declared_invalid != calculated_invalid or declared_invalid != set(excluded):
                raise CampanaError(
                    "las exclusiones no coinciden con tareas_invalidas de la calibración versionada."
                )
            if (
                sub["rule"].get("exclusiones_pedidas") != len(excluded)
                or sub["rule"].get("exclusiones_aplicadas") != len(excluded)
                or sub["rule"].get("n_test_efectivo") != len(sub["test"])
                or sub["rule"].get("n_train_efectivo") != len(sub["train"])
            ):
                raise CampanaError(
                    "los conteos de la regla no coinciden con las listas train/test/exclusiones."
                )
            heldout = sub["rule"].get("held_out_repo")
            if not isinstance(heldout, str) or not heldout:
                raise CampanaError("la regla del subconjunto debe nombrar held_out_repo.")
            if any(source_tasks[iid] != heldout for iid in sub["test"]):
                raise CampanaError(
                    "test no pertenece por completo al repositorio leave-one-repo-out declarado."
                )
            if any(source_tasks[iid] == heldout for iid in sub["train"]):
                raise CampanaError("train contiene tareas del repositorio reservado.")
            cited_subset = sub
        else:
            if not isinstance(valor, dict) or set(valor) != {
                "B",
                "C",
                "D",
                "variacion_a_sha256",
                "subconjunto_sha256",
                "g6",
            }:
                raise CampanaError("corridas_por_condicion requiere B/C/D, hashes fuente y cita G6.")
            if cited_report is None or cited_subset is None:
                raise CampanaError(
                    "corridas_por_condicion no puede cerrarse sin A y subconjunto verificados antes."
                )
            expected_a = data["abiertos"]["variacion_a"]["valor"]["sha256"]
            expected_subset = data["abiertos"]["subconjunto"]["valor"]["sha256"]
            if valor["variacion_a_sha256"] != expected_a or valor["subconjunto_sha256"] != expected_subset:
                raise CampanaError(
                    "corridas_por_condicion no está vinculada a las fuentes verificadas de A y subset."
                )
            if cited_report["entrada"].get("subconjunto_sha256") != expected_subset:
                raise CampanaError("el reporte A y el subconjunto citado tienen hashes distintos.")
            if cited_report["entrada"].get("tasks_sha256") != cited_subset.get("sha256_tasks"):
                raise CampanaError("el reporte A y el subconjunto citan distintos tasks.jsonl.")
            baseline_path = REPO_ROOT / "experiments/gemma_developer_agent/preregistro/linea_base_a.json"
            baseline_rel = "experiments/gemma_developer_agent/preregistro/linea_base_a.json"
            g6 = valor["g6"]
            if not isinstance(g6, dict) or set(g6) != {"ruta", "sha256"} or g6.get("ruta") != baseline_rel:
                raise CampanaError("G6 debe citar la linea_base_a.json versionada como fuente del cómputo.")
            _validar_cita(g6, "G6 línea base")
            _assert_tracked_clean(baseline_path, "parámetros de presupuesto de la línea base")
            try:
                from scripts import kaggle_prereg

                baseline = load_params(baseline_path)
                structure_errors = kaggle_prereg.check_structure(baseline)
                if structure_errors:
                    raise CampanaError("pre-registro de línea base inválido: " + "; ".join(structure_errors))
                open_baseline = kaggle_prereg.open_parameters(baseline)
                if open_baseline:
                    raise CampanaError(
                        "G6 sigue bloqueado: línea base sin cerrar " + ", ".join(open_baseline)
                    )
                base_check = kaggle_prereg.check_closed(
                    baseline,
                    REPO_ROOT,
                    tasks=REPO_ROOT / "experiments/gemma_developer_agent/data/tasks.jsonl",
                    envio=REPO_ROOT / "experiments/gemma_developer_agent/conditions/a_linea_base",
                    git=True,
                    parametros=baseline_rel,
                )
                if base_check.problemas or base_check.pendientes:
                    raise CampanaError(
                        "G6 no puede usar una línea base no verificada: "
                        + "; ".join(base_check.problemas + base_check.pendientes)
                    )
                n = cited_report["margen"]["comparables"]
                table = cited_report["margen"]["por_discordantes"]
                if type(n) is not int or n <= 0 or n != cited_report["entrada"]["tareas_subconjunto"]:
                    raise CampanaError("G2 comparables no coincide con el tamaño del subconjunto A.")
                differences = [x["diferencia_pares"] for x in table if x.get("alcanzable") is True]
                case = kaggle_prereg.noise_case(
                    baseline["fijos"], n, max(differences) if differences else None
                )
                replicas = cited_report.get("por_replica")
                if not isinstance(replicas, list) or not replicas:
                    raise CampanaError("el reporte A no contiene resultados por réplica para aplicar G3.")
                if any(
                    not isinstance(r, dict)
                    or type(r.get("resueltas")) is not int
                    or type(r.get("no_resueltas")) is not int
                    or r["resueltas"] + r["no_resueltas"] != cited_report["entrada"]["tareas_subconjunto"]
                    for r in replicas
                ):
                    raise CampanaError("alguna réplica A no tiene desenlace completo para todas las tareas.")
                minimum_unresolved = min(r["no_resueltas"] for r in replicas)
                base_values = {k: baseline["abiertos"][k]["valor"] for k in kaggle_prereg.ABIERTOS}
                base_subset = load_params(_repo_path(base_values["subconjunto"]["ruta"]))
                if base_values["subconjunto"]["sha256"] != expected_subset:
                    raise CampanaError("el pre-registro #103 y #104 no comparten el subconjunto cerrado.")
                heldout_repo = base_subset["rule"]["held_out_repo"]
                validez = load_params(_repo_path(base_values["validez_tareas"]["ruta"]))
                validas_por_repo: dict[str, int] = {}
                for task in validez["tareas"]:
                    if task["clase"] == "discrimina":
                        validas_por_repo[task["repo"]] = validas_por_repo.get(task["repo"], 0) + 1
                corrida = base_values["corrida"]
                cuota = base_values["cuota"]
                corte = kaggle_prereg.parse_date(
                    baseline["fijos"]["fecha_corte_campana"], "fecha_corte_campana"
                )
                fecha = kaggle_prereg.parse_date(corrida["fecha_compuerta"], "fecha_compuerta")
                hours = kaggle_prereg.usable_hours(
                    baseline["fijos"],
                    cuota["gpu_semanal_horas"],
                    cuota["factor_l4x4"],
                    kaggle_prereg.quota_resets(fecha, corte, cuota["dia_reinicio"]),
                )
                steps = [
                    step
                    for step in kaggle_prereg.ladder(baseline["fijos"], validas_por_repo)
                    if step.repo == heldout_repo
                ]
                step = kaggle_prereg.choose_step(steps, hours)
                if step is None:
                    raise CampanaError(
                        "G6: el escalón de línea base cerrado no cabe en el cómputo disponible."
                    )
            except (KeyError, TypeError, ValueError, OSError, CampanaError) as exc:
                raise CampanaError(f"no se pudo derivar G2 desde el reporte A: {exc}") from exc
            if case == "dominante":
                raise CampanaError(
                    "G2 es ruido dominante: el preregistro prohíbe cerrar corridas de campaña."
                )
            if case not in {"bajo", "intermedio"}:
                raise CampanaError("G2 no produjo una clase admisible para esta campaña.")
            if minimum_unresolved < 6:
                raise CampanaError(
                    "G3 techo: A deja menos de seis tareas sin resolver; no se corre campaña de mejora."
                )
            b, c, d = (valor[k] for k in ("B", "C", "D"))
            minimum_g2 = 1 if case == "bajo" else 2
            if step.por_condicion < minimum_g2:
                raise CampanaError("G6: no caben los mínimos B/C que exige G2; la campaña no se corre.")
            single_condition_hours = kaggle_prereg.plan_hours(baseline["fijos"], step.n_test)
            extra_runs = int((hours - step.horas) / single_condition_hours)
            available_total = 2 * step.por_condicion + extra_runs
            expected_d = corridas_d_g6(available_total, step.por_condicion)
            if type(b) is not int or b != step.por_condicion or type(c) is not int or c != step.por_condicion:
                raise CampanaError(
                    "corridas B/C no coinciden con la escalera G6 derivada del presupuesto #103."
                )
            if type(d) is not int or d != expected_d:
                raise CampanaError("corridas D contradicen la reducción G6 derivada del presupuesto #103.")
    return pendientes


def _validar_cita(value: dict[str, Any], nombre: str) -> None:
    ruta, digest = value["ruta"], value["sha256"]
    if (
        not isinstance(ruta, str)
        or not ruta
        or Path(ruta).is_absolute()
        or ".." in Path(ruta).parts
        or "\\" in ruta
    ):
        raise CampanaError(f"{nombre}: ruta debe ser relativa al repositorio y no escapar de él.")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise CampanaError(f"{nombre}: sha256 debe tener 64 dígitos hexadecimales minúsculos.")
    path = _repo_path(ruta)
    _assert_tracked_clean(path, nombre)
    try:
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise CampanaError(f"{nombre}: no se pudo leer la fuente citada: {exc}") from exc
    if actual != digest:
        raise CampanaError(f"{nombre}: SHA-256 no coincide con la fuente citada.")


def _assert_tracked_clean(path: Path, nombre: str) -> None:
    relative = path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    try:
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", relative],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--", relative],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise CampanaError(f"{nombre}: no se pudo verificar procedencia Git: {exc}") from exc
    if tracked.returncode != 0 or not tracked.stdout.strip() or dirty.returncode != 0 or dirty.stdout.strip():
        raise CampanaError(f"{nombre}: la fuente debe estar versionada y limpia en Git.")


def _repo_path(ruta: str) -> Path:
    path = (REPO_ROOT / ruta).resolve()
    if REPO_ROOT.resolve() not in path.parents:
        raise CampanaError("la fuente citada escapa del repositorio.")
    return path


def test_ids_de_subconjunto(data: dict[str, Any]) -> list[str]:
    crudos = data.get("test")
    if (
        not isinstance(crudos, list)
        or not crudos
        or not all(isinstance(item, str) and item for item in crudos)
    ):
        raise CampanaError("el subconjunto necesita una lista 'test' de instance_id no vacios.")
    if len(set(crudos)) != len(crudos):
        raise CampanaError("hay instance_id de prueba repetidos.")
    train = data.get("train")
    if train is not None:
        if not isinstance(train, list) or not all(isinstance(item, str) and item for item in train):
            raise CampanaError("el subconjunto necesita una lista 'train' de instance_id no vacíos.")
        if len(set(train)) != len(train):
            raise CampanaError("hay instance_id de entrenamiento repetidos.")
        comunes = sorted(set(crudos) & set(train))
        if comunes:
            raise CampanaError(f"un instance_id esta en train y en test: {comunes[0]}")
    return list(crudos)


def cargar_tareas_publicas(path: Path) -> dict[str, str]:
    """Carga instance_id→repo con el mismo esquema mínimo exigido por kaggle_split."""
    repos: dict[str, str] = {}
    try:
        with path.open(encoding="utf-8") as stream:
            for number, line in enumerate(stream, start=1):
                try:
                    task = json.loads(line, object_pairs_hook=_unique_object)
                except (json.JSONDecodeError, ValueError) as exc:
                    raise CampanaError(f"tasks.jsonl línea {number} no es JSON válido: {exc}") from exc
                if not isinstance(task, dict):
                    raise CampanaError(f"tasks.jsonl línea {number} no es un objeto.")
                iid, repo = task.get("instance_id"), task.get("repo")
                if not isinstance(iid, str) or not iid or not isinstance(repo, str) or not repo:
                    raise CampanaError(f"tasks.jsonl línea {number} carece de instance_id/repo textual.")
                if iid in repos:
                    raise CampanaError(f"tasks.jsonl repite instance_id {iid}.")
                repos[iid] = repo
    except (OSError, UnicodeError) as exc:
        raise CampanaError(f"no se pudo leer tasks.jsonl: {exc}") from exc
    if not repos:
        raise CampanaError("tasks.jsonl público está vacío.")
    return repos


def _normaliza(texto: str) -> str:
    return " ".join(texto.casefold().split())


def cargar_textos_test(path: Path, test_ids: Sequence[str]) -> dict[str, str]:
    """Lee task statements para detectar copias literales aun si omiten el ID."""
    wanted = set(test_ids)
    found: dict[str, str] = {}
    try:
        with path.open(encoding="utf-8") as stream:
            for number, line in enumerate(stream, start=1):
                try:
                    task = json.loads(line, object_pairs_hook=_unique_object)
                except (json.JSONDecodeError, ValueError) as exc:
                    raise CampanaError(f"tasks.jsonl línea {number} no es JSON válido: {exc}") from exc
                if not isinstance(task, dict):
                    raise CampanaError(f"tasks.jsonl línea {number} no es un objeto.")
                iid = task.get("instance_id")
                if iid not in wanted:
                    continue
                if iid in found:
                    raise CampanaError(f"tasks.jsonl repite instance_id de prueba {iid}.")
                statement = task.get("problem_statement")
                if not isinstance(statement, str) or not _normaliza(statement):
                    raise CampanaError(f"tasks.jsonl no tiene problem_statement para {iid}.")
                found[iid] = statement
    except (OSError, UnicodeError) as exc:
        raise CampanaError(f"no se pudo leer el archivo de tareas {path}: {exc}") from exc
    missing = wanted - set(found)
    if missing:
        raise CampanaError(f"tasks.jsonl no contiene todos los IDs de prueba; falta {sorted(missing)[0]}.")
    return found


def buscar_fuga(
    test_ids: Iterable[str], raices: Sequence[Path], textos_test: dict[str, str] | None = None
) -> list[tuple[str, str]]:
    """Detecta IDs y copias literales normalizadas de enunciados de prueba."""

    ids = tuple(test_ids)
    if not ids:
        raise CampanaError("no hay instance_id de prueba que buscar.")
    hallados: list[tuple[str, str]] = []
    for raiz in raices:
        if not raiz.exists():
            raise CampanaError(f"no existe {raiz}.")
        if not raiz.is_file() and not raiz.is_dir():
            raise CampanaError(f"no es archivo ni directorio: {raiz}.")
        archivos = [raiz] if raiz.is_file() else sorted(path for path in raiz.rglob("*") if path.is_file())
        for path in archivos:
            if any(parte in _SKIP_DIRS for parte in path.parts):
                continue
            try:
                texto = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                raise CampanaError(f"no se pudo revisar {path}: {exc}") from exc
            normalizado = _normaliza(texto)
            for iid in ids:
                if iid in texto:
                    hallados.append((iid, path.as_posix()))
                    continue
                if textos_test is None:
                    continue
                statement = _normaliza(textos_test[iid])
                # A full statement or an exact paragraph of at least 80 characters is a
                # specific literal-copy signal; short generic phrases are ignored.
                fragments = [statement, *(_normaliza(p) for p in re.split(r"\n\s*\n", textos_test[iid]))]
                if any(len(fragment) >= 80 and fragment in normalizado for fragment in fragments):
                    hallados.append((iid, path.as_posix()))
    return hallados


def _cmd_comprobar(args: argparse.Namespace) -> int:
    data = load_params(args.parametros)
    validar_fijos(data)
    pendientes = abiertos_pendientes(data)
    if pendientes:
        print("abiertos: " + ", ".join(pendientes))
        print("la campana de prueba no empieza")
        return EXIT_OPEN
    print("parametros de la campana cerrados")
    return EXIT_OK


def _cmd_fuga(args: argparse.Namespace) -> int:
    subconjunto = load_params(args.subconjunto)
    ids = test_ids_de_subconjunto(subconjunto)
    textos = cargar_textos_test(args.tasks, ids)
    hallados = buscar_fuga(ids, [Path(ruta) for ruta in args.raiz], textos)
    if hallados:
        for iid, ruta in hallados:
            print(f"{iid}\t{ruta}")
        return EXIT_INVALID
    print(f"sin copia literal detectada: {len(ids)} instance_id de prueba revisados")
    return EXIT_OK


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pre-registro de la campana A/B/C/D (#104).")
    sub = parser.add_subparsers(dest="comando", required=True)

    comprobar = sub.add_parser("comprobar")
    comprobar.add_argument("--parametros", type=Path, default=DEFAULT_PARAMS)
    comprobar.set_defaults(func=_cmd_comprobar)

    fuga = sub.add_parser("fuga")
    fuga.add_argument("--subconjunto", type=Path, required=True)
    fuga.add_argument(
        "--tasks", type=Path, required=True, help="tasks.jsonl público para revisar enunciados."
    )
    fuga.add_argument("--raiz", type=Path, action="append", required=True)
    fuga.set_defaults(func=_cmd_fuga)

    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except CampanaError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_INVALID


if __name__ == "__main__":
    raise SystemExit(main())
