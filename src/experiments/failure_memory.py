"""Memoria de fallos con revisión (H6, #63) sobre el agente de diagnóstico de #58.

Especificación: ``docs/preregistration/failure-memory.md`` (secciones 2 a 4). Un **registro de fallo**
nace de cada intento de reparación fallido (``tests[i]``, ``i ≥ 1``, ``returncode ≠ 0``) de un recibo
``task_run`` sellado de A_N o C_N. Guarda solo la estrategia, la clave pública de recuperación
(``title + " " + context``), la firma que D extrae de ``test-0`` y la referencia ``RUN-…#test-i``. Nunca
usa anotaciones privadas, el id de la tarea como clave, parches dorados ni tests posteriores a la decisión.

La política extiende la de #58 con una clave entre D y la lección::

    plan = sorted(STRATEGIES, key=λop: (op ∉ S, op ∈ F, op ≠ p, prior.index(op)))

Con ``F`` vacío, la decisión es exactamente la de #58. El agente por defecto y el de #58 no cambian.
"""

import copy
from dataclasses import dataclass

from associative_agent_loop.memory.text import cosine_similarity

from .agent import RULES, STRATEGIES
from .diagnostic import DiagnosticRepairAgent, DiagnosticView, failure_features
from .evidence import read_receipt

POLICY = "failure-memory/v1"
AGENT_NAME = DiagnosticRepairAgent.name + "+failure-memory-v1"
STORE = "failure-memory/v1"
TAU = 0.5
# Condición → (modo de lecciones, memoria de fallos activa). A y C son los de #58 con este agente.
CONDITIONS = {
    "A": ("NO_MEMORY", False),
    "A_N": ("NO_MEMORY", True),
    "C": ("ASSOCIATIVE_MEMORY", False),
    "C_N": ("ASSOCIATIVE_MEMORY", True),
}
PASSES = (1, 2)
# Declaración exacta que escribe el runner en cada recibo de este agente: la de #58 y, además, la
# instantánea de la memoria de fallos que recibió el agente (``failure_memory_input``).
DECISION_INPUTS = {
    "order": ["RETRIEVE", "test-0", "plan"],
    "reproduction": "test-0",
    "failures": "failure_memory_input",
}
SAME_TASK, OTHER_TASK = "same_task", "other_task"


def failure_enabled(condition):
    """Si la condición declarada tiene memoria de fallos; ``ValueError`` si no es una condición de H6."""
    if condition not in CONDITIONS:
        raise ValueError(f"condición de memoria de fallos desconocida: {condition!r}")
    return CONDITIONS[condition][1]


def query_of(task):
    """La misma clave pública que usa la recuperación de lecciones (``PublicTask.query``)."""
    return task["title"] + " " + task["context"]


def scope(record, signature, query):
    """Alcance de un registro: firma idéntica y similitud de la clave ≥ τ (pre-registro, sección 3)."""
    same = record["signature"] == signature
    similarity = cosine_similarity(query, record["query"])
    applies = same and similarity >= TAU
    return {
        "strategy": record["strategy"],
        "signature_match": same,
        "similarity": similarity,
        "applies": applies,
    }


def failure_plan(prior, candidates, proposal, failed):
    """D acota, la memoria de fallos baja lo que ya falló, la lección ordena el resto, el prior desempata."""
    prior = list(prior)
    return sorted(
        STRATEGIES,
        key=lambda op: (op not in candidates, op in failed, op != proposal, prior.index(op)),
    )


def failure_effect(applied, plan, plan_without_failures):
    if not applied:
        return "none"
    return "no_change" if plan[0] == plan_without_failures[0] else "changed_first"


@dataclass(frozen=True)
class FailureView(DiagnosticView):
    """DiagnosticView más los registros de fallo de la condición (vacío en A y C)."""

    failures: tuple[dict, ...] = ()


class FailureMemoryRepairAgent(DiagnosticRepairAgent):
    """Mismos operadores, parches y diagnóstico que #58; el plan también baja lo que ya falló."""

    name = AGENT_NAME
    reads_failures = True

    def plan(self, view):
        base = super().plan(view)  # la decisión de #58, exactamente
        signature = base["diagnostic"]["features"]
        query = query_of(view.task)
        scopes, applied, failed = [], [], set()
        for record in getattr(view, "failures", ()):
            item = scope(record, signature, query)
            scopes.append(item)
            if item["applies"]:
                applied.append(record["id"])
                failed.add(record["strategy"])
        plan = failure_plan(
            base["considered"], base["diagnostic"]["candidates"], base["memory_proposal"], failed
        )
        return {
            **base,
            "policy": POLICY,
            "selected": plan[0],
            "plan": plan,
            "initial_hypothesis": RULES[plan[0]],
            "plan_without_failures": base["plan"],
            "failure_scope": scopes,
            "failure_ids": applied,
            "failure_strategies": [s for s in STRATEGIES if s in failed],
            "failure_effect": failure_effect(applied, plan, base["plan"]),
        }


def replay_decision(record):
    """Recalcula la decisión desde lo que registró el recibo (lado del evaluador)."""
    test0 = record["tests"][0]
    view = FailureView(
        record["task"],
        dict(record["initial_source"]),
        tuple(record["retrieval"]["memories"]),
        record["memory_mode"],
        record["seed"],
        reproduction={"returncode": test0["returncode"], "stderr": test0["stderr"]},
        failures=tuple(record["failure_memory_input"]),
    )
    return FailureMemoryRepairAgent().plan(view)


def failure_records(receipt):
    """Registros de un recibo ``task_run`` sellado: uno por intento fallido ``tests[i]``, ``i ≥ 1``."""
    tests, actions = receipt["tests"], receipt["actions"]
    if (
        receipt.get("kind") != "task_run"
        or receipt.get("result") not in ("PASS", "FAIL")
        or [t["id"] for t in tests] != [f"test-{i}" for i in range(len(tests))]
        or tests[0]["returncode"] == 0
        or len(actions) != len(tests) - 1
    ):
        raise ValueError("el recibo no tiene una reproducción fallida y un test por intento")
    signature = failure_features(tests[0]["stderr"])
    query = query_of(receipt["task"])
    records = []
    for index, (action, test) in enumerate(zip(actions, tests[1:], strict=True), 1):
        if action["iteration"] != index:
            raise ValueError("intento y test no se corresponden en el recibo")
        if test["returncode"] == 0:
            continue
        evidence = receipt["run_id"] + "#" + test["id"]
        records.append(
            {
                "id": "failure:" + evidence,
                "strategy": action["strategy"],
                "query": query,
                "signature": signature,
                "evidence": evidence,
                "receipt_sha256": receipt["receipt_sha256"],
            }
        )
    return records


class FailureMemory:
    """Memoria de fallos de una (lote, semilla, condición), actualizada en línea tras cada ejecución.

    ``records`` es lo único que ve el agente. ``origins`` (registro → tarea de origen) lo lee el
    controlador del recibo sellado para anotar el origen de los registros aplicados, después de decidir.
    """

    def __init__(self, records=(), origins=None, cell=None):
        self.records = [dict(r) for r in records]
        self.origins = dict(origins or {})
        self.cell = cell

    def copy(self):
        return FailureMemory(copy.deepcopy(self.records), self.origins, self.cell)

    def snapshot(self):
        return {"schema_id": STORE, "records": copy.deepcopy(self.records)}

    def consolidate(self, receipt_path):
        receipt = read_receipt(receipt_path)
        if receipt.get("agent") != AGENT_NAME or not failure_enabled(receipt.get("condition")):
            raise ValueError("la memoria de fallos solo se escribe desde recibos de A_N y C_N")
        cell = (receipt["batch_id"], receipt["seed"], receipt["condition"])
        if self.cell is not None and self.cell != cell:
            raise ValueError("el recibo es de otra (lote, semilla, condición)")
        known = {r["id"] for r in self.records}
        new = [r for r in failure_records(receipt) if r["id"] not in known]
        self.cell = cell
        self.records.extend(new)
        self.origins.update({r["id"]: receipt["task"]["id"] for r in new})
        return [{"action": "ADD", "memory": r["id"], "evidence": r["evidence"]} for r in new]

    def origin(self, record_id, task_id):
        return SAME_TASK if self.origins[record_id] == task_id else OTHER_TASK
