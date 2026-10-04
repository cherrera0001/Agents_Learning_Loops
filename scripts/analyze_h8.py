"""Análisis pre-registrado de H8 (#98): recuperación sembrada con una señal no léxica frente al señuelo.

Implementa ``docs/preregistration/h8-nonlexical-seed.md``, secciones 4 y 5 (C0 ``6034512``): métricas,
denominadores y reglas de decisión fijados **antes** de la campaña. Lee los recibos directamente, sin importar
el paquete ``experiments``: verifica el sello SHA-256 de cada recibo con la biblioteca estándar y cita
``generated_from``.

Antes de cualquier veredicto comprueba la validez (sección 5). La campaña es **inválida**, y la salida lo dice
con su motivo y sin veredicto, si no tiene la forma declarada (2 réplicas × 6 semillas × 4 condiciones × 9
tareas), si hay un recibo ``ERROR``, si la réplica 2 difiere de la 1 en comportamiento, o si A, B o C_L no
reproducen la réplica 1 de la campaña de referencia en alguna de sus 162 celdas. ``python -m experiments
evaluate`` verifica además la repetición de cada siembra y de cada decisión desde su recibo y el rechazo de
material privado: si rechaza el directorio, la campaña también es inválida.

Uso::

    python -m scripts.analyze_h8 --evidence evidence/nonlexical-seed-v1

La salida es JSON por la salida estándar; el código de salida es 1 si la campaña es inválida.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

Receipt = dict[str, Any]
ASSOCIATIVE = "ASSOCIATIVE_MEMORY"
# Condición → (modo de memoria, señal de siembra): tabla de la sección 3. Un test comprueba que coincide con
# ``experiments.nonlexical_seed.CONDITIONS``.
CONDITIONS: dict[str, tuple[str, str | None]] = {
    "A": ("NO_MEMORY", None),
    "B": ("TEXT_HISTORY", None),
    "C_L": (ASSOCIATIVE, "lexical-title-context"),
    "C_S": (ASSOCIATIVE, "trace-components"),
}
NEW = "C_S"  # la condición nueva; las otras tres son la referencia y los controles
CONTROLS = ("A", "B", "C_L")
AGENT = "bounded-ast-repair-v1+trace-seed-v1"
POLICY = "trace-component-seed/v1"
REFERENCE_AGENT = "bounded-ast-repair-v1"
DECISION_INPUTS = {"order": ["test-0", "RETRIEVE", "plan"], "reproduction": "test-0"}
# La decisión lleva los campos del agente por defecto y ``policy``, y ningún campo del diagnóstico D.
DECISION_KEYS = frozenset(
    {
        "considered",
        "selected",
        "plan",
        "without_memory",
        "influenced_by_memory",
        "memory_ids",
        "initial_hypothesis",
        "policy",
    }
)
SEEDED, TIE, EMPTY = "seeded", "tie", "empty"
STATES = (SEEDED, TIE, EMPTY)
# Campaña declarada (experiments.benchmark.NONLEXICAL_SEED_CAMPAIGN); un test comprueba que coinciden.
TASKS = tuple(f"EXP-{i:02d}" for i in range(1, 10))
TRAIN, ORIGINAL, MISLEADING = TASKS[:3], TASKS[3:6], TASKS[6:]  # check_splits exige que coincidan
KIND_TASKS = {"train": TRAIN, "original": ORIGINAL, "misleading": MISLEADING}
SEEDS = (1, 4, 5, 6, 7, 9)
REPLICATES = 2
RECEIPT_SCHEMA = "software-learning-receipt/v2"
NORMALIZATION = "lf/v1"
# Margen de H4, #58, H6 y H7 (sección 5): 3 ejecuciones de 18. Conteos exactos, sin inferencia estadística.
MARGIN = 3
RUNS_PER_KIND = len(SEEDS) * len(MISLEADING)
REFERENCE_CELLS = len(CONTROLS) * len(TASKS) * len(SEEDS)
# Clases de la lección citada en una tarea engañosa (sección 4).
CORRECT, DECOY, OTHER, NONE = "correcta", "señuelo", "otra", "ninguna"
CLASSES = (CORRECT, DECOY, OTHER, NONE)
# Lecturas del primer intento y veredictos (sección 5).
IMPROVES, NO_DIFFERENCE = "mejora", "sin diferencia"
WORSE, NOT_ABOVE_CONTROLS = "peor que sin memoria", "no supera a los controles"
SUPPORTED, REFUTED, INVALID = "apoyada", "refutada", "inválida"
VERDICTS = {
    (IMPROVES, True): SUPPORTED,
    (IMPROVES, False): "no apoyada: mejora, pero sigue citando el señuelo",
    (NO_DIFFERENCE, True): NO_DIFFERENCE,
    (NO_DIFFERENCE, False): "sin diferencia, y sigue citando el señuelo",
    (WORSE, True): "no apoyada: peor que no usar memoria",
    (WORSE, False): "no apoyada: peor que no usar memoria",
    (NOT_ABOVE_CONTROLS, True): REFUTED,
    (NOT_ABOVE_CONTROLS, False): REFUTED,
}
NO_EXPOSURE = "sin exposición"
WITH_COST, WITHOUT_COST = "con coste", "sin coste"
# Predicción escrita antes de implementar (sección 6).
PREDICTION = {
    "verdict": VERDICTS[(NO_DIFFERENCE, False)],
    "secondary": WITH_COST,
    "FA_C_S_misleading": 4,
    "S": 6,
}


class InvalidCampaign(ValueError):
    """La campaña no cumple una condición de validez de la sección 5: no hay veredicto."""


def canonical(value: Any) -> bytes:
    """El mismo JSON canónico que sella los recibos (``experiments.evidence.canonical``)."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def load(directory: Path) -> tuple[list[Receipt], dict[str, str]]:
    """Recibos con su sello verificado, y ``generated_from`` (archivo → sello) para trazabilidad."""
    receipts, generated_from = [], {}
    for path in sorted(directory.glob("RUN-*.json")):
        record = json.loads(path.read_text("utf-8"))
        checksum = record.pop("receipt_sha256", None)
        if checksum is None or hashlib.sha256(canonical(record)).hexdigest() != checksum:
            raise ValueError(f"sello del recibo ausente o que no coincide: {path.name}")
        if (record.get("schema_id"), record.get("source_hash_normalization")) != (
            RECEIPT_SCHEMA,
            NORMALIZATION,
        ):
            raise ValueError(f"esquema o normalización no previstos en {path.name}")
        if path.stem != record.get("run_id"):
            raise ValueError(f"el nombre del archivo no es el run_id sellado: {path.name}")
        record["receipt_sha256"] = checksum
        receipts.append(record)
        generated_from[path.name] = checksum
    return receipts, generated_from


def annotations(root: Path) -> dict[str, dict[str, Any]]:
    private = json.loads((root / "benchmark/private/tasks.json").read_text("utf-8"))
    extra = root / "benchmark/private/tasks_misleading.json"
    if extra.exists():
        private.update(json.loads(extra.read_text("utf-8")))
    return private


def position(r: Receipt) -> int:
    """Orden temporal declarado en una (lote, semilla, condición): el orden de la tarea."""
    return TASKS.index(r["task"]["id"])


def check_runs(runs: list[Receipt]) -> None:
    for r in runs:
        if r.get("result") not in ("PASS", "FAIL"):
            raise InvalidCampaign(f"ejecución con resultado {r.get('result')}: {r['run_id']}")
        if (r["agent"], r["decision"].get("policy")) != (AGENT, POLICY):
            raise InvalidCampaign(f"solo recibos de la recuperación sembrada; {r['run_id']} no lo es")
        if r["decision"].keys() != DECISION_KEYS:
            raise InvalidCampaign(
                f"decisión con campos distintos de los del agente por defecto: {r['run_id']}"
            )
        if r.get("decision_inputs") != DECISION_INPUTS or "pass" in r:
            raise InvalidCampaign(f"recibo sin el orden test-0, RETRIEVE, plan declarado: {r['run_id']}")
        block = r["retrieval"].get("seeding")
        if r.get("condition") not in CONDITIONS or not isinstance(block, dict):
            raise InvalidCampaign(f"recibo sin condición o bloque de siembra: {r['run_id']}")
        mode, signal = CONDITIONS[r["condition"]]
        if mode != r["memory_mode"] or (block.get("policy"), block.get("signal")) != (POLICY, signal):
            raise InvalidCampaign(f"condición que no concuerda con el modo o con la siembra: {r['run_id']}")
        exposed = [m["id"] for m in r["retrieval"]["memories"]]
        if r["condition"] == NEW:
            expected = [block.get("lesson")] if block.get("state") == SEEDED else []
            if block.get("state") not in STATES or exposed != expected:
                raise InvalidCampaign(f"estado de la siembra incoherente con lo expuesto: {r['run_id']}")
        elif (block.get("state"), block.get("seeds"), block.get("lesson")) != (None, None, None):
            raise InvalidCampaign(f"una condición sin siembra de la traza declara semillas: {r['run_id']}")


def check_shape(runs: list[Receipt]) -> list[str]:
    keys = [(r["batch_id"], r["seed"], r["task"]["id"], r["condition"]) for r in runs]
    if len(set(keys)) != len(keys):
        raise InvalidCampaign("celda duplicada (lote, semilla, tarea, condición)")
    batches = sorted({batch for batch, *_ in keys})
    if len(batches) != REPLICATES:
        raise InvalidCampaign(f"se esperaban {REPLICATES} réplicas (lotes) completas; hay {len(batches)}")
    expected = set(itertools.product(SEEDS, TASKS, CONDITIONS))
    for batch in batches:
        found = {(seed, task, cond) for b, seed, task, cond in keys if b == batch}
        if found != expected:
            raise InvalidCampaign(
                f"el lote {batch} no es la campaña declarada: faltan {len(expected - found)} celdas "
                f"y sobran {len(found - expected)}"
            )
    return batches


def check_splits(runs: list[Receipt], private: dict[str, dict[str, Any]]) -> None:
    splits: dict[str, set[str]] = defaultdict(set)
    for r in runs:
        splits[r["task"]["id"]].add(r["split"])
    declared = {
        **dict.fromkeys(TRAIN, ("train", False)),
        **dict.fromkeys(ORIGINAL, ("transfer", False)),
        **dict.fromkeys(MISLEADING, ("transfer", True)),
    }
    for task, (split, decoy) in declared.items():
        if splits[task] != {split} or bool(private[task].get("decoy_family")) is not decoy:
            raise InvalidCampaign(
                "las particiones no son EXP-01..03 de entrenamiento, 04..06 originales y 07..09 engañosas"
            )


def cells_of(runs: list[Receipt]) -> dict[tuple[str, int, str], list[Receipt]]:
    cells: dict[tuple[str, int, str], list[Receipt]] = defaultdict(list)
    for r in runs:
        cells[(r["batch_id"], r["seed"], r["condition"])].append(r)
    for items in cells.values():
        items.sort(key=position)
    return cells


def check_lessons(runs: list[Receipt], updates: list[Receipt]) -> None:
    """Lecciones solo del entrenamiento verificado de la misma (lote, semilla, condición), congeladas
    después; C_L y C_S no comparten lecciones. Un ``memory_update`` por entrenamiento con ``ADD``."""
    for items in cells_of(runs).values():
        for r in items:
            lessons = (r["memory_input"] or {}).get("lessons", [])
            exposed = {m["id"] for m in r["retrieval"]["memories"]}
            if r["memory_mode"] == CONDITIONS["A"][0]:
                if lessons or exposed:
                    raise InvalidCampaign(f"{r['condition']} con lecciones: {r['run_id']}")
                continue
            earlier = {
                t["run_id"]: t
                for t in items
                if t["split"] == "train" and t["result"] == "PASS" and position(t) < position(r)
            }
            if {lesson["run_id"] for lesson in lessons} != set(earlier) or any(
                earlier[lesson["run_id"]]["receipt_sha256"] != lesson["receipt_sha256"] for lesson in lessons
            ):
                raise InvalidCampaign(
                    f"lección fuera de procedencia, de otra condición o no congelada en {r['run_id']}"
                )
            if (
                not exposed <= {lesson["id"] for lesson in lessons}
                or not set(r["decision"]["memory_ids"]) <= exposed
            ):
                raise InvalidCampaign(f"recuperación fuera de la memoria elegible en {r['run_id']}")
    trained = sorted(
        r["run_id"] + ".json"
        for r in runs
        if r["split"] == "train" and r["result"] == "PASS" and r["memory_mode"] != CONDITIONS["A"][0]
    )
    if sorted(u["source_receipt"] for u in updates) != trained:
        raise InvalidCampaign(
            "los memory_update no corresponden uno a uno con el entrenamiento verificado de B, C_L y C_S"
        )


def check_signal(runs: list[Receipt]) -> None:
    """La señal de ``test-0`` es la misma en las cuatro condiciones de cada (lote, semilla, tarea)."""
    signals: dict[tuple[str, int, str], set[str]] = defaultdict(set)
    for r in runs:
        components = json.dumps(r["retrieval"]["seeding"].get("components"), sort_keys=True)
        signals[(r["batch_id"], r["seed"], r["task"]["id"])].add(components)
    if any(len(found) != 1 for found in signals.values()):
        raise InvalidCampaign("las condiciones de una celda registran señales distintas")


def validate_campaign(receipts: list[Receipt], private: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Forma declarada de la campaña (pre-registro, secciones 3 y 9), antes de cualquier veredicto."""
    runs = [r for r in receipts if r["kind"] == "task_run"]
    updates = [r for r in receipts if r["kind"] == "memory_update"]
    if len(runs) + len(updates) != len(receipts) or any("memory_store" in u for u in updates):
        raise InvalidCampaign("recibos de un tipo o de una memoria no previstos")
    check_runs(runs)
    batches = check_shape(runs)
    check_splits(runs, private)
    check_lessons(runs, updates)
    check_signal(runs)
    return {
        "task_runs": len(runs),
        "memory_updates": len(updates),
        "batches": batches,
        "primary_batch": batches[0],
    }


def behaviour(r: Receipt) -> str:
    """Lo que debe coincidir entre réplicas y con la referencia (sección 5): plan, lecciones expuestas y
    citadas por su tarea de origen, resultado e intentos. Sin UUID ni tiempos."""
    origin = {m["id"]: m["task"] for m in r["retrieval"]["memories"]}
    return json.dumps(
        [
            r["decision"]["plan"],
            [m["task"] for m in r["retrieval"]["memories"]],
            [origin[i] for i in r["decision"]["memory_ids"]],
            r["result"],
            r["iterations"],
        ]
    )


def replicates(runs: list[Receipt], batches: list[str]) -> list[Receipt]:
    """Réplica 1 = el primer lote por ``batch_id``. La otra debe ser idéntica en comportamiento celda a
    celda; si no, la campaña es inválida."""
    cells = {(r["batch_id"], r["seed"], r["task"]["id"], r["condition"]): r for r in runs}
    primary, other = batches
    chosen = [r for r in runs if r["batch_id"] == primary]
    for r in chosen:
        twin = cells[(other, r["seed"], r["task"]["id"], r["condition"])]
        if behaviour(r) != behaviour(twin):
            raise InvalidCampaign(
                f"las réplicas difieren en comportamiento: semilla {r['seed']}, {r['task']['id']}, "
                f"{r['condition']}"
            )
    return chosen


def check_controls(selected: list[Receipt], reference: list[Receipt]) -> dict[str, Any]:
    """A, B y C_L reproducen la réplica 1 de la campaña de referencia en sus 162 celdas (sección 5): es el
    control de que solo cambió la siembra."""
    runs = [r for r in reference if r["kind"] == "task_run"]
    if any(r.get("result") not in ("PASS", "FAIL") or r["agent"] != REFERENCE_AGENT for r in runs):
        raise InvalidCampaign("la referencia tiene recibos con error o de otro agente")
    batches = sorted({r["batch_id"] for r in runs})
    if not batches:
        raise InvalidCampaign("la referencia no tiene ejecuciones")
    primary = [r for r in runs if r["batch_id"] == batches[0]]
    cells = {(r["memory_mode"], r["task"]["id"], r["seed"]): r for r in primary}
    expected = set(itertools.product([CONDITIONS[c][0] for c in CONTROLS], TASKS, SEEDS))
    if len(cells) != len(primary) or set(cells) != expected:
        raise InvalidCampaign(
            f"la réplica 1 de la referencia no tiene las {REFERENCE_CELLS} celdas declaradas"
        )
    different = [
        f"{r['condition']}/{r['task']['id']}/semilla {r['seed']}"
        for r in selected
        if r["condition"] in CONTROLS
        and behaviour(r) != behaviour(cells[(r["memory_mode"], r["task"]["id"], r["seed"])])
    ]
    if different:
        raise InvalidCampaign(
            f"los controles no reproducen la referencia en {len(different)} de {REFERENCE_CELLS} celdas: "
            + ", ".join(sorted(different)[:10])
        )
    return {"cells": REFERENCE_CELLS, "reference_primary_batch": batches[0]}


def ratio(num: int, den: int) -> dict[str, Any]:
    return {"value": None if den == 0 else num / den, "numerator": num, "denominator": den}


def first_ok(r: Receipt) -> bool:
    return bool(r["outcome"]["first_attempt_success"])


def measures(items: list[Receipt]) -> dict[str, Any]:
    """``FA`` e ``Iter`` de la sección 4, con numerador y denominador."""
    return {
        "FA": ratio(sum(first_ok(r) for r in items), len(items)),
        "Iter": ratio(sum(r["iterations"] for r in items), len(items)),
    }


def cited_class(r: Receipt, private: dict[str, dict[str, Any]]) -> tuple[str, str | None]:
    """Clase de la lección citada en una ejecución engañosa y su tarea de origen (lado del evaluador: la
    familia de una lección es la de su tarea de origen, leída de las anotaciones)."""
    origin = {m["id"]: m["task"] for m in r["retrieval"]["memories"]}
    cited = [origin[i] for i in r["decision"]["memory_ids"]]
    if not cited:
        return NONE, None
    family = private[cited[0]]["family"]
    target = private[r["task"]["id"]]
    if family == target["family"]:
        return CORRECT, cited[0]
    return (DECOY if family == target.get("decoy_family") else OTHER), cited[0]


def citations(items: list[Receipt], private: dict[str, dict[str, Any]]) -> dict[str, Any]:
    classes: Counter[str] = Counter()
    sources: Counter[str] = Counter()
    for r in items:
        name, source = cited_class(r, private)
        classes[name] += 1
        if source is not None:
            sources[source] += 1
    return {
        "runs": len(items),
        "classes": {name: classes[name] for name in CLASSES},
        "source_tasks": dict(sorted(sources.items())),
    }


def first_attempt_reading(delta_ctrl: int, delta_a: int) -> str:
    """Tabla «Primer intento» de la sección 5: cubre todos los enteros y no se solapa."""
    if delta_ctrl < MARGIN:
        return NOT_ABOVE_CONTROLS
    if delta_a <= -MARGIN:
        return WORSE
    if delta_a >= MARGIN:
        return IMPROVES
    return NO_DIFFERENCE


def selection_met(decoy_cited: int) -> bool:
    """La selección se cumple si C_S cita el señuelo en 2 ejecuciones engañosas o menos (``S ≤ 2``)."""
    return decoy_cited < MARGIN


def decide(
    fa: dict[str, int], decoy_cited: int, cited_runs: int, fa_original: dict[str, int]
) -> dict[str, Any]:
    """Veredicto de H8 (sección 5) desde los conteos de las 18 ejecuciones engañosas de cada condición."""
    delta_b, delta_l, delta_a = fa[NEW] - fa["B"], fa[NEW] - fa["C_L"], fa[NEW] - fa["A"]
    delta_ctrl = min(delta_b, delta_l)
    delta_orig = fa_original[NEW] - fa_original["C_L"]
    first = first_attempt_reading(delta_ctrl, delta_a)
    met = selection_met(decoy_cited)
    silent = cited_runs < MARGIN  # la señal no llegó a actuar: menos de 3 de 18 ejecuciones citan algo
    return {
        "delta_B": delta_b,
        "delta_L": delta_l,
        "delta_A": delta_a,
        "delta_ctrl": delta_ctrl,
        "delta_orig": delta_orig,
        "S": decoy_cited,
        "selection_met": met,
        "first_attempt": first,
        "verdict": VERDICTS[(first, met)],
        "cited_runs": cited_runs,
        "no_exposure": silent,
        "mark": NO_EXPOSURE if silent else None,
        "secondary": WITH_COST if delta_orig <= -MARGIN else WITHOUT_COST,
    }


def prediction(decision: dict[str, Any], fa_new: int) -> dict[str, Any]:
    """La predicción de la sección 6 se da por cumplida solo con el veredicto y la regla secundaria; los dos
    números son la estimación puntual y se reporta cuánto se apartó el resultado."""
    return {
        "predicted": PREDICTION,
        "fulfilled": (decision["verdict"], decision["secondary"])
        == (PREDICTION["verdict"], PREDICTION["secondary"]),
        "FA_C_S_misleading_minus_predicted": fa_new - PREDICTION["FA_C_S_misleading"],
        "S_minus_predicted": decision["S"] - PREDICTION["S"],
    }


def analyze(
    receipts: list[Receipt], private: dict[str, dict[str, Any]], reference: list[Receipt]
) -> dict[str, Any]:
    try:
        campaign = validate_campaign(receipts, private)  # antes de cualquier veredicto
        runs = [r for r in receipts if r["kind"] == "task_run"]
        selected = replicates(runs, campaign["batches"])
        controls = check_controls(selected, reference)
    except InvalidCampaign as error:
        return {"valid": False, "verdict": INVALID, "invalid_reason": str(error)}
    index = {(r["condition"], r["seed"], r["task"]["id"]): r for r in selected}

    def members(condition: str, tasks: tuple[str, ...]) -> list[Receipt]:
        return [index[(condition, s, t)] for s, t in itertools.product(SEEDS, tasks)]

    metrics = {
        condition: {
            "by_kind": {kind: measures(members(condition, tasks)) for kind, tasks in KIND_TASKS.items()},
            "by_task": {task: measures(members(condition, (task,))) for task in TASKS},
        }
        for condition in CONDITIONS
    }
    cited = {
        condition: {
            **citations(members(condition, MISLEADING), private),
            "by_task": {task: citations(members(condition, (task,)), private) for task in MISLEADING},
        }
        for condition in CONDITIONS
    }
    states = {
        task: {
            state: sum(r["retrieval"]["seeding"]["state"] == state for r in members(NEW, (task,)))
            for state in STATES
        }
        for task in TASKS
    }

    def fa(kind: str) -> dict[str, int]:
        return {c: metrics[c]["by_kind"][kind]["FA"]["numerator"] for c in CONDITIONS}

    classes = cited[NEW]["classes"]
    decision = decide(fa("misleading"), classes[DECOY], RUNS_PER_KIND - classes[NONE], fa("original"))
    return {
        "valid": True,
        "campaign": campaign,
        "replicates_consistent": True,
        "controls_reproduce_reference": controls,
        "margin_runs": MARGIN,
        "runs_per_kind": RUNS_PER_KIND,
        "metrics": metrics,
        "cited_lesson_misleading": cited,
        "seed_state_C_S": states,
        "decision": decision,
        "verdict": decision["verdict"],
        "prediction": prediction(decision, fa("misleading")[NEW]),
    }


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--reference", default="evidence/reference-v2")
    args = parser.parse_args()
    receipts, generated_from = load(args.root / args.evidence)
    reference, reference_from = load(args.root / args.reference)
    report = analyze(receipts, annotations(args.root), reference)
    report["generated_from"] = generated_from
    report["reference"] = {"directory": args.reference, "generated_from": reference_from}
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not report["valid"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
