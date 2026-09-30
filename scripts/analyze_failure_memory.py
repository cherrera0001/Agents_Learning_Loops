"""Análisis pre-registrado de la memoria de fallos con revisión (H6, #63).

Implementa ``docs/preregistration/failure-memory.md``, secciones 4 a 6 (commit ``87c5941``): campaña,
métricas, denominadores y reglas de decisión fijados **antes** de la campaña. Lee los recibos directamente,
sin importar el paquete ``experiments``: verifica el sello SHA-256 de cada recibo con la biblioteca
estándar, cita ``generated_from`` y valida la forma exacta de la campaña declarada antes de calcular
cualquier veredicto (lección de la revisión de #58). ``python -m experiments evaluate`` verifica además la
repetición de cada decisión desde su recibo, el mismo diagnóstico en todas las condiciones y pasadas, la
derivación exacta de cada registro de fallo y las anotaciones privadas.

Uso::

    python -m scripts.analyze_failure_memory --evidence evidence/failure-memory-v1
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
A, A_N, C, C_N = "A", "A_N", "C", "C_N"
# Condición → (modo de lecciones, memoria de fallos). Tabla del pre-registro.
CONDITIONS = {
    A: ("NO_MEMORY", False),
    A_N: ("NO_MEMORY", True),
    C: ("ASSOCIATIVE_MEMORY", False),
    C_N: ("ASSOCIATIVE_MEMORY", True),
}
PAIRS = ((A, A_N), (C, C_N))  # sección 6: A_N frente a A y C_N frente a C
AGENT = "bounded-ast-repair-v1+diagnostic-v1+failure-memory-v1"
POLICY = "failure-memory/v1"
STORE = "failure-memory/v1"
# Campaña declarada (experiments.benchmark.FAILURE_MEMORY_CAMPAIGN); un test comprueba que coinciden.
TASKS = tuple(f"EXP-{i:02d}" for i in range(1, 10))
TRAIN, TRANSFER = TASKS[:3], TASKS[3:]
ORIGINAL, MISLEADING = TRANSFER[:3], TRANSFER[3:]  # check_splits exige que las anotaciones coincidan
SEEDS = (1, 4, 5, 6, 7, 9)
REPLICATES = 2
PASSES = (1, 2)
KIND_SIZES = {"train": 3, "original": 3, "misleading": 3}
RECEIPT_SCHEMA = "software-learning-receipt/v2"
NORMALIZATION = "lf/v1"
# Margen de #58 (sección 6): 3 de 18 ejecuciones. Criterio exploratorio, no significancia.
MARGIN = 3
RUNS_PER_CELL = len(SEEDS) * KIND_SIZES["original"]
PRIMARY_KINDS = ("original", "misleading")
RECORD_KEYS = ("condition", "pass", "failure_memory_input", "failure_origins")
DECISION_KEYS = (
    "plan_without_failures",
    "failure_scope",
    "failure_ids",
    "failure_strategies",
    "failure_effect",
)
EFFECTS = ("none", "no_change", "changed_first")
SAME_TASK, OTHER_TASK = "same_task", "other_task"
INVALID = "inválido"


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


def position(r: Receipt) -> tuple[int, int]:
    """Orden temporal declarado dentro de una (lote, semilla, condición): pasada y orden de la tarea."""
    return r["pass"], TASKS.index(r["task"]["id"])


def failed(r: Receipt) -> list[int]:
    """Índices ``i ≥ 1`` de los intentos de reparación cuyo test falló."""
    return [i for i, t in enumerate(r["tests"]) if i >= 1 and t["returncode"] != 0]


def refs(r: Receipt) -> list[str]:
    return [f"{r['run_id']}#{r['tests'][i]['id']}" for i in failed(r)]


def check_runs(runs: list[Receipt]) -> None:
    for r in runs:
        if (r["agent"], r["decision"].get("policy")) != (AGENT, POLICY):
            raise ValueError(f"solo recibos de la memoria de fallos; {r['run_id']} no lo es")
        if r["result"] not in ("PASS", "FAIL"):
            raise ValueError(f"ejecución con resultado {r['result']}: {r['run_id']}")
        if not set(RECORD_KEYS) <= r.keys() or not set(DECISION_KEYS) <= r["decision"].keys():
            raise ValueError(f"recibo sin los campos de la memoria de fallos: {r['run_id']}")
        if r["condition"] not in CONDITIONS or CONDITIONS[r["condition"]][0] != r["memory_mode"]:
            raise ValueError(f"condición desconocida o que no concuerda con el modo: {r['run_id']}")
        if r["pass"] not in PASSES or r["decision"]["failure_effect"] not in EFFECTS:
            raise ValueError(f"pasada o efecto de la memoria de fallos no previstos: {r['run_id']}")


def check_shape(runs: list[Receipt]) -> list[str]:
    keys = [(r["batch_id"], r["seed"], r["task"]["id"], r["condition"], r["pass"]) for r in runs]
    if len(set(keys)) != len(keys):
        raise ValueError("celda duplicada (lote, semilla, tarea, condición, pasada)")
    batches = sorted({batch for batch, *_ in keys})
    if len(batches) != REPLICATES:
        raise ValueError(f"se esperaban {REPLICATES} réplicas (lotes) completas; hay {len(batches)}")
    expected = {(s, t, c, 1) for s, t, c in itertools.product(SEEDS, TASKS, CONDITIONS)}
    expected |= {(s, t, c, 2) for s, t, c in itertools.product(SEEDS, TRANSFER, CONDITIONS)}
    for batch in batches:
        found = {(seed, task, cond, number) for b, seed, task, cond, number in keys if b == batch}
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
    """Lecciones en línea solo en entrenamiento y congeladas después (igual que #58), por condición."""
    for items in cells_of(runs).values():
        for r in items:
            lessons = (r["memory_input"] or {}).get("lessons", [])
            exposed = {m["id"] for m in r["retrieval"]["memories"]}
            if r["memory_mode"] == CONDITIONS[A][0]:
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
        r["run_id"] + ".json" for r in runs if r["split"] == "train" and r["memory_mode"] != CONDITIONS[A][0]
    )
    if sorted(u["source_receipt"] for u in updates) != trained:
        raise ValueError(
            "los memory_update de lecciones no corresponden uno a uno con el entrenamiento de C y C_N"
        )


def check_failure_records(runs: list[Receipt], updates: list[Receipt]) -> None:
    """Cada registro de fallo cita un test fallido real de un recibo sellado anterior de su celda.

    La memoria que recibe cada ejecución es exactamente la de los intentos fallidos anteriores de su
    (lote, semilla, condición), en orden (vacía en A y C); los orígenes anotados de los registros
    aplicados coinciden con sus recibos; y hay un ``memory_update`` separado por ejecución de A_N o C_N
    con intentos fallidos, y ninguno más.
    """
    for (_, _, condition), items in cells_of(runs).items():
        enabled = CONDITIONS[condition][1]
        by_id = {r["run_id"]: r for r in items}
        written: list[str] = []
        for r in items:
            inputs = r["failure_memory_input"]
            if not enabled and (inputs or r["decision"]["failure_ids"] or r["failure_origins"]):
                raise ValueError(f"{condition} con memoria de fallos: {r['run_id']}")
            source_task = {}
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
                source_task[record["id"]] = task["id"]
            if [record["evidence"] for record in inputs] != written:
                raise ValueError(
                    f"la memoria de fallos no es la de los intentos fallidos anteriores en {r['run_id']}"
                )
            applied = r["decision"]["failure_ids"]
            if not set(applied) <= set(source_task) or r["failure_origins"] != [
                {"id": i, "origin": SAME_TASK if source_task[i] == r["task"]["id"] else OTHER_TASK}
                for i in applied
            ]:
                raise ValueError(f"orígenes de los registros aplicados que no coinciden en {r['run_id']}")
            if enabled:
                written += refs(r)
    expected = sorted(r["run_id"] + ".json" for r in runs if CONDITIONS[r["condition"]][1] and failed(r))
    if sorted(u["source_receipt"] for u in updates) != expected:
        raise ValueError("los memory_update de fallos no corresponden a los intentos fallidos de A_N y C_N")
    by_name = {r["run_id"] + ".json": r for r in runs}
    for u in updates:
        if [c["evidence"] for c in u["memory_changes"]] != refs(by_name[u["source_receipt"]]):
            raise ValueError(f"memory_update de fallos que no deriva de su recibo: {u['run_id']}")


def validate_campaign(receipts: list[Receipt], private: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Validación cerrada de la campaña declarada (pre-registro, secciones 2 a 4), antes de cualquier
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


def cited_tasks(r: Receipt) -> list[str]:
    source = {m["id"]: m["task"] for m in r["retrieval"]["memories"]}
    return [source[i] for i in r["decision"]["memory_ids"]]


def behaviour(r: Receipt) -> str:
    """Comportamiento sin UUID ni tiempos: lo que debe coincidir entre réplicas (y entre pasadas en A y C)."""
    decision = {k: v for k, v in r["decision"].items() if k not in ("memory_ids", "failure_ids")}
    return json.dumps(
        [
            decision,
            r["outcome"],
            [a["strategy"] for a in r["actions"]],
            [t["returncode"] for t in r["tests"]],
            [m["task"] for m in r["retrieval"]["memories"]],
            cited_tasks(r),
            [o["origin"] for o in r["failure_origins"]],
        ],
        sort_keys=True,
    )


def replicates(runs: list[Receipt], batches: list[str]) -> tuple[list[Receipt], bool]:
    """Réplica 1 = el primer lote por ``batch_id``, el mismo para toda celda. La otra réplica debe ser
    idéntica en comportamiento celda a celda; si no, el análisis es inválido (sección 4)."""
    cells = {(r["batch_id"], r["seed"], r["task"]["id"], r["condition"], r["pass"]): r for r in runs}
    primary, other = batches
    chosen = [r for r in runs if r["batch_id"] == primary]
    consistent = all(
        behaviour(r) == behaviour(cells[(other, r["seed"], r["task"]["id"], r["condition"], r["pass"])])
        for r in chosen
    )
    return chosen, consistent


def determinism_control(selected: list[Receipt]) -> bool:
    """En A y C la pasada 2 no tiene memoria nueva: debe reproducir la pasada 1 (sección 4)."""
    cells = {(r["seed"], r["task"]["id"], r["condition"], r["pass"]): r for r in selected}
    return all(
        behaviour(cells[(seed, task, cond, 1)]) == behaviour(cells[(seed, task, cond, 2)])
        for seed, task, cond in itertools.product(SEEDS, TRANSFER, (A, C))
    )


def ratio(num: int, den: int) -> dict[str, Any]:
    return {"value": None if den == 0 else num / den, "numerator": num, "denominator": den}


def displaced(r: Receipt) -> tuple[str, bool]:
    """``helped``/``hurt``/``neutral`` de un primer intento cambiado, y la marca ``untested``.

    Se comparan el resultado observado del nuevo primer intento y el del intento desplazado
    (``plan_without_failures[0]``) en la misma ejecución (sección 5). Si el desplazado no llegó a probarse
    es ``neutral`` con ``untested``: ocurre siempre que el nuevo primer intento tiene éxito, porque la
    ejecución termina, así que ``helped`` no es observable con esta regla.
    """
    new_ok = r["tests"][1]["returncode"] == 0
    tried = [a["strategy"] for a in r["actions"]]
    target = r["decision"]["plan_without_failures"][0]
    if target not in tried:
        return "neutral", True
    target_ok = r["tests"][tried.index(target) + 1]["returncode"] == 0
    if new_ok and not target_ok:
        return "helped", False
    if target_ok and not new_ok:
        return "hurt", False
    return "neutral", False


def cross_task_effect(rs: list[Receipt]) -> dict[str, Any]:
    """Primeros intentos cambiados por al menos un registro aplicado de **otra** tarea, sobre las
    ejecuciones con ``failure_effect = changed_first``. ``mixed`` cuenta los que también aplicaron un
    registro de la misma tarea; ``same_task_only``, los cambiados solo por registros de la misma tarea."""
    changed = [r for r in rs if r["decision"]["failure_effect"] == "changed_first"]
    counts: Counter[str] = Counter()
    for r in changed:
        origins = {o["origin"] for o in r["failure_origins"]}
        if OTHER_TASK not in origins:
            counts["same_task_only"] += 1
            continue
        counts["mixed"] += SAME_TASK in origins
        label, untested = displaced(r)
        counts[label] += 1
        counts["untested"] += untested
    cross = sum(counts[k] for k in ("helped", "hurt", "neutral"))
    return {
        "changed_first": len(changed),
        "cross_task": ratio(cross, len(changed)),
        "helped": counts["helped"],
        "hurt": counts["hurt"],
        "neutral": counts["neutral"],
        "untested": counts["untested"],
        "mixed": counts["mixed"],
        "same_task_only": counts["same_task_only"],
    }


def summary(rs: list[Receipt], earlier_failures: dict[tuple[int, str], set[str]] | None) -> dict[str, Any]:
    n = len(rs)
    out: dict[str, Any] = {
        "runs": n,
        "FirstAttemptSuccess": ratio(sum(r["outcome"]["first_attempt_success"] for r in rs), n),
        "IterationsPerTask": ratio(sum(r["iterations"] for r in rs), n),
        "failure_effect": {e: sum(r["decision"]["failure_effect"] == e for r in rs) for e in EFFECTS},
        "applied_records": {
            o: sum(x["origin"] == o for r in rs for x in r["failure_origins"])
            for o in (SAME_TASK, OTHER_TASK)
        },
        "CrossTaskEffect": cross_task_effect(rs),
    }
    if earlier_failures is not None:
        repeated = sum(
            r["actions"][0]["strategy"] in earlier_failures[(r["seed"], r["task"]["id"])] for r in rs
        )
        out["RepeatedFirstFailure"] = ratio(repeated, n)
    return out


def h6a(passes: dict[str, Any], valid: bool) -> dict[str, Any]:
    cells = {}
    for x, xn in PAIRS:
        for kind in PRIMARY_KINDS:
            rx = passes["pass-2"][kind][x]["RepeatedFirstFailure"]
            rxn = passes["pass-2"][kind][xn]["RepeatedFirstFailure"]
            headroom = rx["numerator"] >= MARGIN
            limit = rx["numerator"] - MARGIN if headroom else rx["numerator"]
            cells[f"{xn} vs {x} / {kind}"] = {
                "R_X": rx,
                "R_X_N": rxn,
                "headroom": headroom,
                "required_max_R_X_N": limit,
                "satisfied": rxn["numerator"] <= limit,
                "null_by_construction": not headroom,
            }
    if not valid:
        verdict = INVALID
    elif not all(c["satisfied"] for c in cells.values()):
        verdict = "refutada"
    elif not any(c["headroom"] for c in cells.values()):
        verdict = "sin holgura"
    else:
        verdict = "apoyada"
    return {"cells": cells, "verdict": verdict}


def h6b(passes: dict[str, Any], valid: bool) -> dict[str, Any]:
    first = {
        p: {
            "FA_C_N": passes[p]["original"][C_N]["FirstAttemptSuccess"],
            "FA_C": passes[p]["original"][C]["FirstAttemptSuccess"],
        }
        for p in passes
    }
    for cell in first.values():
        cell["satisfied"] = cell["FA_C_N"]["numerator"] >= cell["FA_C"]["numerator"]
    hurt = {
        f"{cond} / {p} / {kind}": passes[p][kind][cond]["CrossTaskEffect"]["hurt"]
        for cond in (A_N, C_N)
        for p in passes
        for kind in PRIMARY_KINDS
    }
    supported = all(c["satisfied"] for c in first.values()) and not any(hurt.values())
    verdict = INVALID if not valid else "apoyada" if supported else "refutada"
    return {"FirstAttemptSuccess_original": first, "CrossTaskEffect_hurt": hurt, "verdict": verdict}


def h6c(passes: dict[str, Any], valid: bool) -> dict[str, Any]:
    cn = passes["pass-2"]["misleading"][C_N]["FirstAttemptSuccess"]
    c = passes["pass-2"]["misleading"][C]["FirstAttemptSuccess"]
    difference = cn["numerator"] - c["numerator"]
    if not valid:
        verdict = INVALID
    elif difference >= MARGIN:
        verdict = "aporta"
    elif difference <= -MARGIN:
        verdict = "perjudica"
    else:
        verdict = "sin diferencia"
    return {"FA_C_N": cn, "FA_C": c, "difference_runs": difference, "verdict": verdict}


def conclusion(rules: dict[str, Any], valid: bool) -> dict[str, Any]:
    if not valid:
        return {"verdict": INVALID, "failing": {}}
    failing = [name for name in ("H6a", "H6b") if rules[name]["verdict"] != "apoyada"]
    verdict = "aprendió de su error sin contaminar" if not failing else "no concluye"
    return {"verdict": verdict, "failing": {name: rules[name]["verdict"] for name in failing}}


def analyze(receipts: list[Receipt], private: dict[str, dict[str, Any]]) -> dict[str, Any]:
    campaign = validate_campaign(receipts, private)  # antes de cualquier veredicto
    runs = [r for r in receipts if r["kind"] == "task_run"]
    selected, consistent = replicates(runs, campaign["batches"])
    control = determinism_control(selected)
    earlier: dict[str, dict[tuple[int, str], set[str]]] = defaultdict(lambda: defaultdict(set))
    for r in selected:
        if r["pass"] == 1 and r["split"] == "transfer":
            earlier[r["condition"]][(r["seed"], r["task"]["id"])] |= {
                r["actions"][i - 1]["strategy"] for i in failed(r)
            }
    groups: dict[tuple[str, str, str], list[Receipt]] = defaultdict(list)
    for r in selected:
        kind = kind_of(r, private)
        groups[(f"pass-{r['pass']}" if kind != "train" else "train", kind, r["condition"])].append(r)
    passes: dict[str, Any] = {
        f"pass-{p}": {
            kind: {
                cond: summary(groups[(f"pass-{p}", kind, cond)], earlier[cond] if p == 2 else None)
                for cond in CONDITIONS
            }
            for kind in PRIMARY_KINDS
        }
        for p in PASSES
    }
    denominators = all(
        cell["runs"] == RUNS_PER_CELL
        for kinds in passes.values()
        for conds in kinds.values()
        for cell in conds.values()
    )
    valid = consistent and control and denominators
    # Descriptivo (PF4, sección 7): pares (semilla, tarea) de la pasada 1 con el mismo plan en X_N y en X.
    plans = {(r["condition"], r["pass"], r["seed"], r["task"]["id"]): r["decision"]["plan"] for r in selected}
    pass1_identical = {
        f"{xn} vs {x} / {kind}": sum(
            plans[(xn, 1, seed, task)] == plans[(x, 1, seed, task)]
            for seed, task in itertools.product(SEEDS, ORIGINAL if kind == "original" else MISLEADING)
        )
        for x, xn in PAIRS
        for kind in PRIMARY_KINDS
    }
    rules = {"H6a": h6a(passes, valid), "H6b": h6b(passes, valid), "H6c": h6c(passes, valid)}
    return {
        "campaign": campaign,
        "replicates_consistent": consistent,
        "determinism_control": control,
        "valid": valid,
        "margin_runs": MARGIN,
        "runs_per_cell": RUNS_PER_CELL,
        "passes": passes,
        "train": {cond: summary(groups[("train", "train", cond)], None) for cond in CONDITIONS},
        "pass1_plans_identical_to_baseline": pass1_identical,
        "rules": rules,
        "conclusion": conclusion(rules, valid),
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
