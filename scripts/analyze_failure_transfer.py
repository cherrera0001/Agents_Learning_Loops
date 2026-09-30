"""Análisis pre-registrado de la transferencia y contaminación de la memoria de fallos (H7, #65).

Implementa ``docs/preregistration/failure-transfer.md``, secciones 5 a 7 (commit ``b1565bf``): campaña,
métricas, denominadores y reglas de decisión fijados **antes** de la campaña. Lee los recibos directamente,
sin importar el paquete ``experiments``: verifica el sello SHA-256 de cada recibo con la biblioteca
estándar, cita ``generated_from`` y valida la forma exacta de la campaña declarada antes de calcular
cualquier veredicto. Rechaza (``ValueError``) campañas incompletas, duplicados, semillas o condiciones
inesperadas, réplicas que difieran en comportamiento, registros de fallo que no deriven de un intento
fallido anterior de su celda, registros en las bases A y C y registros aplicados con origen en la misma
tarea. ``python -m experiments evaluate`` verifica además la repetición de cada decisión desde su recibo
(τ y placebo incluidos, con el coseno de ``TEXT_HISTORY``) y las anotaciones privadas.

Uso::

    python -m scripts.analyze_failure_transfer --evidence evidence/failure-transfer-v1
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
# Orden de STRATEGIES en experiments/agent.py (un test comprueba que coincide): la rotación del placebo.
STRATEGIES = ("validate_optional_identity", "normalize_environment", "initialize_storage")
ROTATION = {s: STRATEGIES[(i + 1) % len(STRATEGIES)] for i, s in enumerate(STRATEGIES)}
# Pre-registro, secciones 3 a 5: umbrales, bases y variantes.
TAUS = {"50": 0.5, "25": 0.25, "10": 0.1, "00": 0.0}
BASES = {"A": "NO_MEMORY", "C": "ASSOCIATIVE_MEMORY"}
VARIANTS = {"R": False, "P": True}
VARIANT_LABELS = {False: "real", True: "placebo"}


def _conditions() -> dict[str, tuple[str, bool, float | None, bool]]:
    """Condición → (modo de lecciones, memoria de fallos, τ, placebo): la tabla de la sección 5, en orden."""
    table: dict[str, tuple[str, bool, float | None, bool]] = {}
    for base, mode in BASES.items():
        table[base] = (mode, False, None, False)
        for variant, placebo in VARIANTS.items():
            for suffix, tau in TAUS.items():
                table[f"{base}_{variant}{suffix}"] = (mode, True, tau, placebo)
    return table


CONDITIONS = _conditions()
AGENT = "bounded-ast-repair-v1+diagnostic-v1+failure-memory-v1+failure-transfer-v1"
POLICY = "failure-transfer/v1"
STORE = "failure-memory/v1"
# Campaña declarada (experiments.benchmark.FAILURE_TRANSFER_CAMPAIGN); un test comprueba que coinciden.
TASKS = tuple(f"EXP-{i:02d}" for i in range(1, 10))
TRAIN, TRANSFER = TASKS[:3], TASKS[3:]
ORIGINAL, MISLEADING = TRANSFER[:3], TRANSFER[3:]  # check_splits exige que las anotaciones coincidan
KIND_TASKS = {"original": ORIGINAL, "misleading": MISLEADING}
SEEDS = (1, 4, 5, 6, 7, 9)
REPLICATES = 2
KIND_SIZES = {"train": 3, "original": 3, "misleading": 3}
RECEIPT_SCHEMA = "software-learning-receipt/v2"
NORMALIZATION = "lf/v1"
# Margen de H4, #58 y H6 (sección 7): 3 pares de 18. Criterio exploratorio, no significancia.
MARGIN = 3
PAIRS_PER_CELL = len(SEEDS) * KIND_SIZES["original"]
KINDS = ("original", "misleading")
RECORD_KEYS = ("condition", "failure_scope_tau", "placebo", "failure_memory_input", "failure_origins")
DECISION_KEYS = (
    "plan_without_failures",
    "failure_scope",
    "failure_ids",
    "failure_strategies",
    "failure_effect",
    "failure_scope_tau",
    "failure_placebo",
    "failure_recorded_strategies",
)
EFFECTS = ("none", "no_change", "changed_first")
SAME_TASK, OTHER_TASK = "same_task", "other_task"
EXPOSED, NOT_EXPOSED = "con exposición", "sin exposición"


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


def kind_of(r: Receipt, private: dict[str, dict[str, Any]]) -> str:
    if r["split"] == "train":
        return "train"
    return "misleading" if private[r["task"]["id"]].get("decoy_family") else "original"


def position(r: Receipt) -> int:
    """Orden temporal declarado en una (lote, semilla, condición): una sola pasada, orden de la tarea."""
    return TASKS.index(r["task"]["id"])


def failed(r: Receipt) -> list[int]:
    """Índices ``i ≥ 1`` de los intentos de reparación cuyo test falló."""
    return [i for i, t in enumerate(r["tests"]) if i >= 1 and t["returncode"] != 0]


def refs(r: Receipt) -> list[str]:
    return [f"{r['run_id']}#{r['tests'][i]['id']}" for i in failed(r)]


def ordered(strategies: set[str]) -> list[str]:
    return [s for s in STRATEGIES if s in strategies]


def check_runs(runs: list[Receipt]) -> None:
    for r in runs:
        if (r["agent"], r["decision"].get("policy")) != (AGENT, POLICY):
            raise ValueError(f"solo recibos de la transferencia de fallos; {r['run_id']} no lo es")
        if r["result"] not in ("PASS", "FAIL"):
            raise ValueError(f"ejecución con resultado {r['result']}: {r['run_id']}")
        if not set(RECORD_KEYS) <= r.keys() or not set(DECISION_KEYS) <= r["decision"].keys():
            raise ValueError(f"recibo sin los campos de la transferencia de fallos: {r['run_id']}")
        if "pass" in r:
            raise ValueError(f"la transferencia tiene una sola pasada; {r['run_id']} declara una")
        if r["condition"] not in CONDITIONS or CONDITIONS[r["condition"]][0] != r["memory_mode"]:
            raise ValueError(f"condición desconocida o que no concuerda con el modo: {r['run_id']}")
        _, _, tau, placebo = CONDITIONS[r["condition"]]
        decision = r["decision"]
        if (r["failure_scope_tau"], r["placebo"]) != (tau, placebo) or (
            decision["failure_scope_tau"],
            decision["failure_placebo"],
        ) != (tau, placebo):
            raise ValueError(f"alcance τ o placebo distintos de los de su condición: {r['run_id']}")
        if decision["failure_effect"] not in EFFECTS:
            raise ValueError(f"efecto de la memoria de fallos no previsto: {r['run_id']}")


def check_shape(runs: list[Receipt]) -> list[str]:
    keys = [(r["batch_id"], r["seed"], r["task"]["id"], r["condition"]) for r in runs]
    if len(set(keys)) != len(keys):
        raise ValueError("celda duplicada (lote, semilla, tarea, condición)")
    batches = sorted({batch for batch, *_ in keys})
    if len(batches) != REPLICATES:
        raise ValueError(f"se esperaban {REPLICATES} réplicas (lotes) completas; hay {len(batches)}")
    expected = set(itertools.product(SEEDS, TASKS, CONDITIONS))
    for batch in batches:
        found = {(seed, task, cond) for b, seed, task, cond in keys if b == batch}
        if found != expected:
            raise ValueError(
                f"el lote {batch} no es la campaña declarada: faltan {len(expected - found)} celdas "
                f"y sobran {len(found - expected)}"
            )
    return batches


def check_splits(runs: list[Receipt], private: dict[str, dict[str, Any]]) -> None:
    splits: dict[str, set[str]] = defaultdict(set)
    for r in runs:
        splits[r["task"]["id"]].add(r["split"])
    if any(len(s) != 1 for s in splits.values()):
        raise ValueError("una tarea tiene particiones distintas entre ejecuciones")
    kinds = [kind_of({"split": next(iter(splits[t])), "task": {"id": t}}, private) for t in TASKS]
    declared = ["train"] * len(TRAIN) + ["original"] * len(ORIGINAL) + ["misleading"] * len(MISLEADING)
    if Counter(kinds) != Counter(KIND_SIZES) or kinds != declared:
        raise ValueError(
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
    """Lecciones en línea solo en entrenamiento y congeladas después (igual que #58 y H6), por condición."""
    for items in cells_of(runs).values():
        for r in items:
            lessons = (r["memory_input"] or {}).get("lessons", [])
            exposed = {m["id"] for m in r["retrieval"]["memories"]}
            if r["memory_mode"] == BASES["A"]:
                if lessons or exposed:
                    raise ValueError(f"{r['condition']} con lecciones: {r['run_id']}")
                continue
            earlier = {
                t["run_id"]: t
                for t in items
                if t["split"] == "train" and t["result"] == "PASS" and position(t) < position(r)
            }
            if {lesson["run_id"] for lesson in lessons} != set(earlier) or any(
                earlier[lesson["run_id"]]["receipt_sha256"] != lesson["receipt_sha256"] for lesson in lessons
            ):
                raise ValueError(
                    f"lección fuera de procedencia, de otra condición o no congelada en {r['run_id']}"
                )
            if (
                not exposed <= {lesson["id"] for lesson in lessons}
                or not set(r["decision"]["memory_ids"]) <= exposed
            ):
                raise ValueError(f"recuperación fuera de la memoria elegible en {r['run_id']}")
    trained = sorted(
        r["run_id"] + ".json" for r in runs if r["split"] == "train" and r["memory_mode"] != BASES["A"]
    )
    if sorted(u["source_receipt"] for u in updates) != trained:
        raise ValueError(
            "los memory_update de lecciones no corresponden uno a uno con el entrenamiento de las bases C"
        )


def check_decision(r: Receipt, inputs: list[Receipt]) -> None:
    """La decisión es coherente con su alcance y su placebo (lo verificable sin el coseno, que el
    evaluador recalcula): un elemento de ``failure_scope`` por registro, firma idéntica leída de D,
    ``applies`` = firma idéntica y similitud ≥ τ, lo que baja cada registro (rotado en el placebo) y el
    efecto sobre el primer intento."""
    decision = r["decision"]
    _, _, tau, placebo = CONDITIONS[r["condition"]]
    scope = decision["failure_scope"]
    if len(scope) != len(inputs):
        raise ValueError(f"alcance sin un elemento por registro en {r['run_id']}")
    applied, demoted, recorded = [], set(), set()
    signature = decision["diagnostic"]["features"]
    for record, item in zip(inputs, scope, strict=True):
        demotes = ROTATION[record["strategy"]] if placebo else record["strategy"]
        match = record["signature"] == signature
        if (
            item.get("strategy") != record["strategy"]
            or item.get("signature_match") is not match
            or item.get("applies") is not (match and tau is not None and item["similarity"] >= tau)
            or item.get("demotes") != demotes
        ):
            raise ValueError(f"alcance o placebo incoherentes con el registro en {r['run_id']}")
        if item["applies"]:
            applied.append(record["id"])
            demoted.add(demotes)
            recorded.add(record["strategy"])
    plan, without = decision["plan"], decision["plan_without_failures"]
    effect = "none" if not applied else "no_change" if plan[0] == without[0] else "changed_first"
    if (
        decision["failure_ids"] != applied
        or decision["failure_strategies"] != ordered(demoted)
        or decision["failure_recorded_strategies"] != ordered(recorded)
        or decision["failure_effect"] != effect
    ):
        raise ValueError(f"decisión incoherente con su alcance o su placebo en {r['run_id']}")


def check_failure_records(runs: list[Receipt], updates: list[Receipt]) -> None:
    """Cada registro de fallo cita un test fallido real de un recibo sellado anterior de su celda.

    La memoria que recibe cada ejecución es exactamente la de los intentos fallidos anteriores de su
    (lote, semilla, condición), en orden (vacía en A y C); la decisión es coherente con su alcance y su
    placebo; ningún registro aplicado tiene origen en la misma tarea y los orígenes anotados coinciden con
    sus recibos; y hay un ``memory_update`` separado por ejecución de una variante con intentos fallidos, y
    ninguno más. El origen en la misma tarea se comprueba primero y contra toda la campaña, para que un
    registro de la misma ejecución o de la misma tarea en otra condición se rechace por ese motivo.
    """
    everywhere = {r["run_id"]: r for r in runs}
    for (_, _, condition), items in cells_of(runs).items():
        enabled = CONDITIONS[condition][1]
        by_id = {r["run_id"]: r for r in items}
        written: list[str] = []
        for r in items:
            inputs = r["failure_memory_input"]
            if not enabled and (inputs or r["decision"]["failure_ids"] or r["failure_origins"]):
                raise ValueError(f"la base {condition} con memoria de fallos: {r['run_id']}")
            cited = {x.get("id"): str(x.get("evidence", "")).partition("#")[0] for x in inputs}
            if any(
                everywhere.get(cited.get(i, ""), {}).get("task", {}).get("id") == r["task"]["id"]
                for i in r["decision"]["failure_ids"]
            ) or any(o.get("origin") != OTHER_TASK for o in r["failure_origins"]):
                raise ValueError(f"registro aplicado con origen en la misma tarea en {r['run_id']}")
            for record in inputs:
                source_id, _, test_id = str(record.get("evidence", "")).partition("#")
                source = by_id.get(source_id)
                if source is None or position(source) >= position(r):
                    raise ValueError(
                        f"registro de fallo de otra celda o de una ejecución no anterior en {r['run_id']}"
                    )
                ids = [t["id"] for t in source["tests"]]
                index = ids.index(test_id) if test_id in ids else 0
                if index < 1 or source["tests"][index]["returncode"] == 0:
                    raise ValueError(f"registro de fallo que no cita un intento fallido en {r['run_id']}")
                task = source["task"]
                if (
                    record.get("id") != "failure:" + record["evidence"]
                    or record.get("strategy") != source["actions"][index - 1]["strategy"]
                    or record.get("signature") != source["decision"]["diagnostic"]["features"]
                    or record.get("query") != task["title"] + " " + task["context"]
                    or record.get("receipt_sha256") != source["receipt_sha256"]
                ):
                    raise ValueError(f"registro de fallo que no coincide con su recibo en {r['run_id']}")
            if [record["evidence"] for record in inputs] != written:
                raise ValueError(
                    f"la memoria de fallos no es la de los intentos fallidos anteriores en {r['run_id']}"
                )
            check_decision(r, inputs)
            applied = r["decision"]["failure_ids"]
            if r["failure_origins"] != [{"id": i, "origin": OTHER_TASK} for i in applied]:
                raise ValueError(f"orígenes de los registros aplicados que no coinciden en {r['run_id']}")
            if enabled:
                written += refs(r)
    expected = sorted(r["run_id"] + ".json" for r in runs if CONDITIONS[r["condition"]][1] and failed(r))
    if sorted(u["source_receipt"] for u in updates) != expected:
        raise ValueError(
            "los memory_update de fallos no corresponden a los intentos fallidos de las variantes"
        )
    by_name = {r["run_id"] + ".json": r for r in runs}
    for u in updates:
        if [c["evidence"] for c in u["memory_changes"]] != refs(by_name[u["source_receipt"]]):
            raise ValueError(f"memory_update de fallos que no deriva de su recibo: {u['run_id']}")


def validate_campaign(receipts: list[Receipt], private: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Validación cerrada de la campaña declarada (pre-registro, secciones 2 a 5), antes de cualquier
    veredicto. Cualquier desvío es un ``ValueError``."""
    runs = [r for r in receipts if r["kind"] == "task_run"]
    updates = [r for r in receipts if r["kind"] == "memory_update"]
    if len(runs) + len(updates) != len(receipts):
        raise ValueError("recibos de un tipo no previsto")
    lesson_updates = [u for u in updates if "memory_store" not in u]
    failure_updates = [u for u in updates if u.get("memory_store") == STORE]
    if len(lesson_updates) + len(failure_updates) != len(updates):
        raise ValueError("memory_update de una memoria no prevista")
    check_runs(runs)
    batches = check_shape(runs)
    check_splits(runs, private)
    check_lessons(runs, lesson_updates)
    check_failure_records(runs, failure_updates)
    return {
        "task_runs": len(runs),
        "lesson_memory_updates": len(lesson_updates),
        "failure_memory_updates": len(failure_updates),
        "batches": batches,
        "primary_batch": batches[0],
    }


def source_tasks(r: Receipt, by_id: dict[str, Receipt]) -> list[str]:
    """Tarea de origen de cada registro aplicado, en orden (leída del recibo citado)."""
    evidence = {x["id"]: x["evidence"].partition("#")[0] for x in r["failure_memory_input"]}
    return [by_id[evidence[i]]["task"]["id"] for i in r["decision"]["failure_ids"]]


def behaviour(r: Receipt, by_id: dict[str, Receipt]) -> str:
    """Comportamiento sin UUID ni tiempos: lo que debe coincidir entre réplicas."""
    decision = {k: v for k, v in r["decision"].items() if k not in ("memory_ids", "failure_ids")}
    cited = {m["id"]: m["task"] for m in r["retrieval"]["memories"]}
    return json.dumps(
        [
            decision,
            r["outcome"],
            [a["strategy"] for a in r["actions"]],
            [t["returncode"] for t in r["tests"]],
            [m["task"] for m in r["retrieval"]["memories"]],
            [cited[i] for i in r["decision"]["memory_ids"]],
            source_tasks(r, by_id),
            [o["origin"] for o in r["failure_origins"]],
        ],
        sort_keys=True,
    )


def replicates(runs: list[Receipt], batches: list[str]) -> list[Receipt]:
    """Réplica 1 = el primer lote por ``batch_id``, el mismo para toda celda. La otra réplica debe ser
    idéntica en comportamiento celda a celda; si no, la campaña se rechaza."""
    by_id = {r["run_id"]: r for r in runs}
    cells = {(r["batch_id"], r["seed"], r["task"]["id"], r["condition"]): r for r in runs}
    primary, other = batches
    chosen = [r for r in runs if r["batch_id"] == primary]
    for r in chosen:
        twin = cells[(other, r["seed"], r["task"]["id"], r["condition"])]
        if behaviour(r, by_id) != behaviour(twin, by_id):
            raise ValueError(
                f"las réplicas difieren en comportamiento: semilla {r['seed']}, {r['task']['id']}, "
                f"{r['condition']}"
            )
    return chosen


def ratio(num: int, den: int) -> dict[str, Any]:
    return {"value": None if den == 0 else num / den, "numerator": num, "denominator": den}


def first_ok(r: Receipt) -> bool:
    return bool(r["outcome"]["first_attempt_success"])


def cell(variant: list[Receipt], base: list[Receipt]) -> dict[str, Any]:
    """Métricas de la sección 6 sobre los pares (semilla, tarea) de una celda, réplica 1."""
    n = len(variant)
    exposure = sum(bool(v["decision"]["failure_ids"]) for v in variant)
    changed = sum(v["decision"]["failure_effect"] == "changed_first" for v in variant)
    helped = sum(first_ok(v) and not first_ok(x) for v, x in zip(variant, base, strict=True))
    hurt = sum(first_ok(x) and not first_ok(v) for v, x in zip(variant, base, strict=True))
    unchanged = [
        (v, x)
        for v, x in zip(variant, base, strict=True)
        if v["decision"]["failure_effect"] != "changed_first"
    ]
    return {
        "pairs": n,
        "Exposure": ratio(exposure, n),
        "Changed": ratio(changed, n),
        "helped": ratio(helped, n),
        "hurt": ratio(hurt, n),
        "NetTransfer": helped - hurt,
        "FA_variant": ratio(sum(first_ok(v) for v in variant), n),
        "FA_base": ratio(sum(first_ok(x) for x in base), n),
        "exposure": EXPOSED if changed >= MARGIN else NOT_EXPOSED,
        # Descriptivo: la sección 6 afirma que helped y hurt solo ocurren si Changed. Se cuentan los pares
        # que lo contradirían y los pares cuyo plan sin memoria de fallos no es el plan de la base.
        "helped_or_hurt_without_changed": sum(first_ok(v) != first_ok(x) for v, x in unchanged),
        "base_plan_equal": sum(
            v["decision"]["plan_without_failures"] == x["decision"]["plan"]
            for v, x in zip(variant, base, strict=True)
        ),
    }


def exposed(c: dict[str, Any]) -> bool:
    return bool(c["exposure"] == EXPOSED)


def h7a(cells: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """«contamina» si hurt ≥ 3 en alguna celda con exposición (sección 7)."""
    readable = [k for k in KINDS if exposed(cells[k])]
    if not readable:
        verdict = NOT_EXPOSED
    elif any(cells[k]["hurt"]["numerator"] >= MARGIN for k in readable):
        verdict = "contamina"
    else:
        verdict = "no contamina"
    return {"kinds_with_exposure": readable, "verdict": verdict}


def h7b(cells: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Transferencia sin contaminar (sección 7), para un τ, una base y una variante.

    Una celda sin exposición no se lee: no aporta ``helped ≥ 3`` ni ``hurt ≥ 3``, y cumple ``hurt = 0`` por
    construcción, marcado en ``hurt_zero_by_construction`` (no cuenta como evidencia de no contaminar).
    """
    kinds = {}
    for k in KINDS:
        readable = exposed(cells[k])
        kinds[k] = {
            "with_exposure": readable,
            "helped_at_least_margin": readable and cells[k]["helped"]["numerator"] >= MARGIN,
            "hurt_at_least_margin": readable and cells[k]["hurt"]["numerator"] >= MARGIN,
            "hurt_zero": (not readable) or cells[k]["hurt"]["numerator"] == 0,
            "hurt_zero_by_construction": not readable,
        }
    if not any(v["with_exposure"] for v in kinds.values()):
        verdict = NOT_EXPOSED
    elif any(v["hurt_at_least_margin"] for v in kinds.values()):
        verdict = "contamina"
    elif any(v["helped_at_least_margin"] for v in kinds.values()) and all(
        v["hurt_zero"] for v in kinds.values()
    ):
        verdict = "transfiere sin contaminar"
    else:
        verdict = "neutral"
    return {"kinds": kinds, "verdict": verdict}


def h7c(real: dict[str, Any], placebo: dict[str, Any]) -> dict[str, Any]:
    """Contenido frente a placebo en una celda (sección 7): ``NetTransfer(real) − NetTransfer(placebo)``."""
    difference = real["NetTransfer"] - placebo["NetTransfer"]
    if not (exposed(real) or exposed(placebo)):
        verdict = NOT_EXPOSED
    elif difference >= MARGIN:
        verdict = "el contenido importa"
    elif difference <= -MARGIN:
        verdict = "peor que placebo"
    else:
        verdict = "indistinguible del placebo"
    return {
        "NetTransfer_real": real["NetTransfer"],
        "NetTransfer_placebo": placebo["NetTransfer"],
        "difference": difference,
        "verdict": verdict,
    }


def tau_label(tau: float) -> str:
    return str(tau)


CONCLUSION_BASE = "C"  # sección 7: la conclusión es solo sobre la base C; A se reporta sin entrar


def conclusion(rules: dict[str, Any], base: str = CONCLUSION_BASE) -> dict[str, Any]:
    """Conclusión de H7 sobre una base (la C) y la variante real (sección 7).

    «Transfiere sin contaminar» exige, en un mismo τ, H7b = «transfiere sin contaminar» y H7c = «el contenido
    importa» en un tipo donde transfiere (con exposición y ``helped ≥ 3``).
    """
    transfers, contaminates = [], []
    for tau in map(tau_label, TAUS.values()):
        b, a, c = rules["H7b"][base][tau]["real"], rules["H7a"][base][tau]["real"], rules["H7c"][base][tau]
        where = [k for k, v in b["kinds"].items() if v["helped_at_least_margin"]]
        if b["verdict"] == "transfiere sin contaminar" and any(
            c[k]["verdict"] == "el contenido importa" for k in where
        ):
            transfers.append(tau)
        if a["verdict"] == "contamina":
            contaminates.append(tau)
    if transfers:
        verdict = "la memoria de fallos transfiere sin contaminar"
    elif contaminates:
        verdict = "contamina"
    else:
        verdict = "sin evidencia de transferencia"
    return {"verdict": verdict, "transfers_at_tau": transfers, "contaminates_at_tau": contaminates}


def descriptive(selected: list[Receipt], by_id: dict[str, Receipt]) -> dict[str, Any]:
    """Conteos por tarea (réplica 1), orígenes de los registros aplicados y estado de D (PT1 y PT3)."""
    by_task: dict[str, dict[str, dict[str, int]]] = defaultdict(dict)
    sources: dict[str, Counter[str]] = defaultdict(Counter)
    for r in selected:
        if r["split"] != "transfer" or not CONDITIONS[r["condition"]][1]:
            continue
        counts = by_task[r["condition"]].setdefault(r["task"]["id"], {"Exposure": 0, "Changed": 0})
        counts["Exposure"] += bool(r["decision"]["failure_ids"])
        counts["Changed"] += r["decision"]["failure_effect"] == "changed_first"
        for source in source_tasks(r, by_id):
            sources[r["condition"]][f"{source} -> {r['task']['id']}"] += 1
    status = {
        r["task"]["id"]: r["decision"]["diagnostic"]["status"]
        for r in selected
        if r["condition"] == "A" and r["seed"] == SEEDS[0]
    }
    return {
        "diagnostic_status": {t: status[t] for t in TASKS},
        "by_task": {c: dict(sorted(by_task[c].items())) for c in CONDITIONS if CONDITIONS[c][1]},
        "applied_record_sources": {
            c: dict(sorted(sources[c].items())) for c in CONDITIONS if CONDITIONS[c][1]
        },
    }


def analyze(receipts: list[Receipt], private: dict[str, dict[str, Any]]) -> dict[str, Any]:
    campaign = validate_campaign(receipts, private)  # antes de cualquier veredicto
    runs = [r for r in receipts if r["kind"] == "task_run"]
    selected = replicates(runs, campaign["batches"])
    by_id = {r["run_id"]: r for r in runs}
    index = {(r["condition"], r["seed"], r["task"]["id"]): r for r in selected}

    def members(condition: str, kind: str) -> list[Receipt]:
        return [index[(condition, s, t)] for s, t in itertools.product(SEEDS, KIND_TASKS[kind])]

    cells: dict[str, Any] = {}
    for base in BASES:
        cells[base] = {}
        for suffix, tau in TAUS.items():
            cells[base][tau_label(tau)] = {
                VARIANT_LABELS[placebo]: {
                    kind: cell(members(f"{base}_{variant}{suffix}", kind), members(base, kind))
                    for kind in KINDS
                }
                for variant, placebo in VARIANTS.items()
            }
    if any(
        c["pairs"] != PAIRS_PER_CELL
        for taus in cells.values()
        for variants in taus.values()
        for kinds in variants.values()
        for c in kinds.values()
    ):
        raise ValueError("una celda no tiene los 18 pares declarados")
    rules: dict[str, Any] = {"H7a": {}, "H7b": {}, "H7c": {}}
    for base, taus in cells.items():
        for name in rules:
            rules[name][base] = {}
        for tau, variants in taus.items():
            rules["H7a"][base][tau] = {label: h7a(variants[label]) for label in VARIANT_LABELS.values()}
            rules["H7b"][base][tau] = {label: h7b(variants[label]) for label in VARIANT_LABELS.values()}
            rules["H7c"][base][tau] = {
                kind: h7c(variants["real"][kind], variants["placebo"][kind]) for kind in KINDS
            }
    return {
        "campaign": campaign,
        "replicates_consistent": True,
        "margin_pairs": MARGIN,
        "pairs_per_cell": PAIRS_PER_CELL,
        "cells": cells,
        "rules": rules,
        "conclusion": conclusion(rules),
        "descriptive": descriptive(selected, by_id),
    }


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--evidence", required=True)
    args = parser.parse_args()
    receipts, generated_from = load(args.root / args.evidence)
    report = analyze(receipts, annotations(args.root))
    report["generated_from"] = generated_from
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
