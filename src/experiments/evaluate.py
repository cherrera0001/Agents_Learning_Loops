"""Generate metrics exclusively from sealed receipts plus evaluator annotations."""

import json
import re
from collections import defaultdict
from pathlib import Path

from .agent import BoundedRepairAgent
from .benchmark import (
    TASK_SETS,
    check_extra_annotations,
    private_metadata,
    write_breakdown,
    write_family_breakdown,
)
from .diagnostic import AGENT_NAME as DIAGNOSTIC_AGENT
from .diagnostic import DECISION_INPUTS, failure_features, replay_decision
from .diagnostic import POLICY as DIAGNOSTIC_POLICY
from .evidence import (
    SOURCE_HASH_NORMALIZATION,
    digest,
    hash_normalization,
    normalize_source,
    read_receipt,
    source_sha256,
)
from .failure_memory import AGENT_NAME as FAILURE_AGENT
from .failure_memory import CONDITIONS, PASSES, STORE, query_of
from .failure_memory import DECISION_INPUTS as FAILURE_DECISION_INPUTS
from .failure_memory import POLICY as FAILURE_POLICY
from .failure_memory import replay_decision as replay_failure_decision
from .failure_transfer import AGENT_NAME as TRANSFER_AGENT
from .failure_transfer import BASES, TAUS, VARIANTS
from .failure_transfer import CONDITIONS as TRANSFER_CONDITIONS
from .failure_transfer import DECISION_INPUTS as TRANSFER_DECISION_INPUTS
from .failure_transfer import POLICY as TRANSFER_POLICY
from .failure_transfer import replay_decision as replay_transfer_decision
from .nonlexical_seed import AGENT_NAME as SEED_AGENT
from .nonlexical_seed import CONDITIONS as SEED_CONDITIONS
from .nonlexical_seed import DECISION_INPUTS as SEED_DECISION_INPUTS
from .nonlexical_seed import TRACE as TRACE_SIGNAL
from .nonlexical_seed import replay_context, replay_retrieval
from .nonlexical_seed import replay_decision as replay_seed_decision
from .runner import ROOT, source_manifest
from .trace_seed import POLICY as SEED_POLICY
from .trace_seed import SEED_NODE_TYPE, trace_weights

# Decision policy each known agent must declare (#58); None = the default decision, without policy.
AGENT_POLICIES = {
    BoundedRepairAgent.name: None,
    DIAGNOSTIC_AGENT: DIAGNOSTIC_POLICY,
    FAILURE_AGENT: FAILURE_POLICY,
    TRANSFER_AGENT: TRANSFER_POLICY,
    SEED_AGENT: SEED_POLICY,
}
# Agentes que llevan los campos de la memoria de fallos: el de H6 (#63) y el de H7 (#65), que la extiende.
FAILURE_AGENTS = frozenset({FAILURE_AGENT, TRANSFER_AGENT})
DIAGNOSTIC_FIELDS = frozenset(
    {"policy", "diagnostic", "plan_without_memory", "memory_proposal", "memory_effect"}
)
# Memoria de fallos (#63): campos aditivos de la decisión y del recibo, solo de su agente.
FAILURE_FIELDS = frozenset(
    {"plan_without_failures", "failure_scope", "failure_ids", "failure_strategies", "failure_effect"}
)
FAILURE_RECORD_FIELDS = frozenset({"condition", "pass", "failure_memory_input", "failure_origins"})
# Transferencia de fallos (#65): campos aditivos de la decisión y del recibo, solo de su agente. Sus
# recibos llevan los de H6 salvo ``pass`` (una sola pasada), más el alcance y el placebo declarados.
TRANSFER_FIELDS = frozenset({"failure_scope_tau", "failure_placebo", "failure_recorded_strategies"})
TRANSFER_RECORD_FIELDS = frozenset({"failure_scope_tau", "placebo"})
TRANSFER_RUN_FIELDS = (FAILURE_RECORD_FIELDS - {"pass"}) | TRANSFER_RECORD_FIELDS
# Siembra de la recuperación (H8, #98): su agente declara ``condition`` sin memoria de fallos, y solo sus
# recibos llevan el bloque ``retrieval.seeding``.
SEED_RECORD_FIELDS = frozenset({"condition"})
SEED_RETRIEVAL_FIELD = "seeding"
# Anotaciones privadas cuyo valor nombra la causa o la familia: ninguno puede aparecer en una siembra.
CAUSAL_ANNOTATIONS = ("family", "decoy_family", "hidden_cause_id")
PRIVATE_PATH = "benchmark/private"
_TOKEN = re.compile(r"[^\w\-]+")
# Orden temporal declarado de la secuencia de H6 dentro de una (lote, semilla, condición).
TASK_ORDER = TASK_SETS["misleading-v1"]


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def signature(test):
    matches = re.findall(r"^(?:\w+\.)*\w*(?:Error|Exception): .+$", test["stderr"], flags=re.MULTILINE)
    return matches[-1] if matches else None


def comparable(baseline, treatment):
    return (
        all(
            baseline[k] == treatment[k]
            for k in (
                "seed",
                "agent",
                "budget",
                "initial_source_sha256",
                "acceptance_sha256",
            )
        )
        and baseline["provenance"] == treatment["provenance"]
    )


def semantic(record):
    """Explicit reproducibility projection, excluding UUIDs, time and OS paths.

    Source/test hashes are only comparable between receipts that share a
    normalization scheme; callers must enforce that with ``single_scheme``.
    """
    return {
        "hash_normalization": hash_normalization(record),
        "task": record["task"]["id"],
        "seed": record["seed"],
        "mode": record["memory_mode"],
        "source": record["initial_source_sha256"],
        "tests": record["acceptance_sha256"],
        "result": record["result"],
        "iterations": record["iterations"],
        "retrieved_tasks": [m["task"] for m in record["retrieval"]["memories"]],
        "decision": {k: v for k, v in record["decision"].items() if k not in ("memory_ids", "failure_ids")},
        "actions": [{k: v for k, v in a.items() if k != "memory_ids"} for a in record["actions"]],
        "test_exit_codes": [t["returncode"] for t in record["tests"]],
    }


def single_scheme(receipts):
    """Refuse to compare source/test hashes across normalization schemes.

    A v1 (checkout-bytes/v0) and a v2 (lf/v1) receipt of the same tree may carry
    different hashes for identical content; comparing them would report a false
    difference, so mixing is an explicit error instead.
    """
    schemes = {hash_normalization(r) for r in receipts}
    if len(schemes) > 1:
        raise ValueError(
            "cannot compare source/test hashes across normalization schemes: " + ", ".join(sorted(schemes))
        )
    return schemes.pop() if schemes else None


def decision_policy(record):
    """(agent, policy) of a receipt, requiring both to agree in both directions (#58).

    The default agent declares no policy and carries no diagnostic-baseline field; the
    diagnostic agent declares exactly its policy. Any other agent is unknown: renaming
    the agent or dropping the policy cannot move a receipt out of the diagnostic checks.
    """
    agent = record["agent"]
    if agent not in AGENT_POLICIES:
        raise ValueError(f"unknown agent: {agent!r}")
    expected = AGENT_POLICIES[agent]
    decision = record["decision"]
    if expected is None:
        if DIAGNOSTIC_FIELDS & decision.keys() or "decision_inputs" in record:
            raise ValueError("default-agent receipt carries diagnostic-baseline fields")
    elif decision.get("policy") != expected:
        raise ValueError("agent and decision policy disagree")
    # H8 (#98): su agente declara ``condition`` sin ser de memoria de fallos; ningún otro campo se le exime.
    carried = record.keys() - SEED_RECORD_FIELDS if agent == SEED_AGENT else record.keys()
    if agent not in FAILURE_AGENTS and (FAILURE_FIELDS & decision.keys() or FAILURE_RECORD_FIELDS & carried):
        raise ValueError("un recibo ajeno a la memoria de fallos lleva campos de memoria de fallos")
    if agent != TRANSFER_AGENT and (
        TRANSFER_FIELDS & decision.keys() or TRANSFER_RECORD_FIELDS & record.keys()
    ):
        raise ValueError("un recibo ajeno a la transferencia de fallos lleva campos de transferencia (H7)")
    if agent != SEED_AGENT and SEED_RETRIEVAL_FIELD in record.get("retrieval", {}):
        raise ValueError("un recibo ajeno a la siembra de la recuperación lleva campos de siembra (H8)")
    return agent, expected


def single_policy(runs):
    """Refuse to pair or pool runs produced by different agents or decision policies.

    Two campaigns in one directory would otherwise be paired inside each batch
    and summed silently (#58).
    """
    policies = {decision_policy(r) for r in runs}
    if len(policies) > 1:
        raise ValueError(
            "cannot evaluate a mix of agents or decision policies: "
            + ", ".join(sorted(f"{agent}/{policy}" for agent, policy in policies))
        )
    return policies.pop() if policies else None


def check_diagnostic(runs):
    """Diagnostic-baseline receipts (#58), after ``single_policy``.

    Each receipt must declare exactly the prior reproduction (``DECISION_INPUTS``),
    whose test-0 failed; the decision must be consistent with what the receipt
    recorded (task, eligible lessons, seed and test-0); and every condition of a cell
    must have received the same diagnosis. The replay proves consistency, not that
    nothing else was consulted: the order is enforced by the runner and tested there.
    """
    diagnoses = defaultdict(set)
    for r in runs:
        if r["agent"] != DIAGNOSTIC_AGENT:
            continue
        tests = r["tests"]
        if (
            r.get("decision_inputs") != DECISION_INPUTS
            or [t["id"] for t in tests] != [f"test-{i}" for i in range(len(tests))]
            or tests[0]["returncode"] == 0
        ):
            raise ValueError("diagnostic decision without the declared prior reproduction (failing test-0)")
        if r["decision"] != replay_decision(r):
            raise ValueError("diagnostic decision does not replay from its receipt")
        diagnoses[(r["batch_id"], r["seed"], r["task"]["id"])].add(digest(r["decision"]["diagnostic"]))
    if any(len(found) > 1 for found in diagnoses.values()):
        raise ValueError("conditions of one cell received different diagnoses")


def sequence_index(record):
    """Posición declarada de una ejecución de H6 en su secuencia: (pasada, orden de la tarea)."""
    return record["pass"], TASK_ORDER.index(record["task"]["id"])


def failed_attempts(record):
    """Índices ``i ≥ 1`` de los intentos de reparación cuyo test falló."""
    return [i for i, test in enumerate(record["tests"]) if i >= 1 and test["returncode"] != 0]


def expected_failure_record(source, index):
    """El registro que debe derivarse del intento ``index`` de ``source``, recalculado aquí."""
    evidence = source["run_id"] + "#" + source["tests"][index]["id"]
    return {
        "id": "failure:" + evidence,
        "strategy": source["actions"][index - 1]["strategy"],
        "query": query_of(source["task"]),
        "signature": failure_features(source["tests"][0]["stderr"]),
        "evidence": evidence,
        "receipt_sha256": source["receipt_sha256"],
    }


def check_failure_record(record, run, by_id, position):
    """Un registro de fallo cita un test fallido real de un recibo sellado anterior de su celda."""
    source_id, _, test_id = str(record.get("evidence", "")).partition("#")
    if source_id not in position:
        raise ValueError(
            "el registro de fallo no cita una ejecución sellada de su (lote, semilla, condición)"
        )
    if position[source_id] >= position[run["run_id"]]:
        raise ValueError("el registro de fallo proviene de la misma ejecución o de una posterior")
    source = by_id[source_id]
    tests = {t["id"]: (i, t) for i, t in enumerate(source["tests"])}
    index, test = tests.get(test_id, (0, None))
    if index < 1 or test["returncode"] == 0:
        raise ValueError("el registro de fallo no cita un intento de reparación fallido")
    if record != expected_failure_record(source, index):
        raise ValueError("el registro de fallo no coincide con su recibo")


def check_failure_update(found, inputs, new):
    """El ``memory_update`` de memoria de fallos de una ejecución: separado, sellado y derivado de ella."""
    if len(found) != 1:
        raise ValueError("cada ejecución de A_N o C_N con intentos fallidos exige un único memory_update")
    update = found[0]
    if (
        update["memory_store"] != STORE
        or update["phases"] != ["MEMORY_UPDATE"]
        or update["memory_before"] != {"schema_id": STORE, "records": inputs}
        or update["memory_after"] != {"schema_id": STORE, "records": [*inputs, *new]}
        or update["memory_changes"]
        != [{"action": "ADD", "memory": x["id"], "evidence": x["evidence"]} for x in new]
    ):
        raise ValueError("el memory_update de memoria de fallos no deriva de su recibo")


def check_failure_memory(runs, receipts):
    """Recibos de memoria de fallos (#63), después de ``single_policy``.

    Cada recibo declara exactamente ``FAILURE_DECISION_INPUTS``, un ``test-0`` fallido, una condición y
    una pasada coherentes con su modo, y una decisión que se repite desde lo registrado (tarea, lecciones,
    semilla, ``test-0`` y ``failure_memory_input``). D es el mismo en todas las condiciones y pasadas de
    cada (lote, semilla, tarea). En el orden temporal declarado de cada (lote, semilla, condición), la
    memoria de fallos que recibió cada ejecución es exactamente la de los intentos fallidos de las
    ejecuciones selladas anteriores (vacía en A y C), cada registro cita un test fallido real, los
    orígenes anotados coinciden con los recibos, y hay un único ``memory_update`` separado por ejecución
    de A_N o C_N con intentos fallidos, y ninguno más.
    """
    failure_runs = [r for r in runs if r["agent"] == FAILURE_AGENT]
    stores = [u for u in receipts if u["kind"] == "memory_update" and "memory_store" in u]
    by_id = {r["run_id"]: r for r in failure_runs}
    cells, diagnoses = defaultdict(list), defaultdict(set)
    for r in failure_runs:
        tests = r["tests"]
        if (
            r.get("decision_inputs") != FAILURE_DECISION_INPUTS
            or [t["id"] for t in tests] != [f"test-{i}" for i in range(len(tests))]
            or not tests[0]["returncode"]
        ):
            raise ValueError(
                "decisión de memoria de fallos sin la reproducción previa declarada (test-0 fallido)"
            )
        if (
            not r.keys() >= FAILURE_RECORD_FIELDS
            or r["condition"] not in CONDITIONS
            or r["pass"] not in PASSES
            or (r["split"] == "train" and r["pass"] != 1)
            or r["task"]["id"] not in TASK_ORDER
        ):
            raise ValueError("recibo de memoria de fallos sin condición, pasada o tarea declaradas")
        if CONDITIONS[r["condition"]][0] != r["memory_mode"]:
            raise ValueError("la condición y el modo de memoria no concuerdan")
        if r["decision"] != replay_failure_decision(r):
            raise ValueError("la decisión de memoria de fallos no se repite desde su recibo")
        cells[(r["batch_id"], r["seed"], r["condition"])].append(r)
        diagnoses[(r["batch_id"], r["seed"], r["task"]["id"])].add(digest(r["decision"]["diagnostic"]))
    if any(len(found) != 1 for found in diagnoses.values()):
        raise ValueError("las condiciones o pasadas de una celda recibieron diagnósticos distintos")
    check_failure_chain(cells, by_id, stores, sequence_index, lambda condition: CONDITIONS[condition][1])


def check_failure_chain(cells, by_id, stores, index_of, enabled_of):
    """La cadena de registros de fallo de cada (lote, semilla, condición), en su orden temporal declarado
    (``index_of``): común a H6 (#63) y H7 (#65). ``enabled_of(condición)`` dice si la condición tiene
    memoria de fallos; ``stores`` son todos los ``memory_update`` de memoria de fallos del directorio."""
    updates = defaultdict(list)
    for update in stores:
        updates[update["source_receipt"]].append(update)
    expected_updates = set()
    for items in cells.values():
        items.sort(key=index_of)
        position = {r["run_id"]: index_of(r) for r in items}
        if len(set(position.values())) != len(items):
            raise ValueError("ejecución repetida en una secuencia de memoria de fallos")
        enabled = enabled_of(items[0]["condition"])
        written = []
        for r in items:
            inputs = r["failure_memory_input"]
            for record in inputs:
                check_failure_record(record, r, by_id, position)
            if inputs != [expected_failure_record(by_id[source], i) for source, i in written]:
                raise ValueError(
                    "la memoria de fallos no es exactamente la de los intentos fallidos anteriores"
                )
            origin_of = {x["id"]: by_id[x["evidence"].partition("#")[0]]["task"]["id"] for x in inputs}
            origins = [
                {"id": i, "origin": "same_task" if origin_of[i] == r["task"]["id"] else "other_task"}
                for i in r["decision"]["failure_ids"]
            ]
            if r["failure_origins"] != origins:
                raise ValueError("los orígenes de los registros aplicados no coinciden con sus recibos")
            failed = failed_attempts(r)
            if enabled and failed:
                name = r["run_id"] + ".json"
                expected_updates.add(name)
                new = [expected_failure_record(r, i) for i in failed]
                check_failure_update(updates.get(name, []), inputs, new)
                written += [(r["run_id"], i) for i in failed]
    if set(updates) != expected_updates:
        raise ValueError(
            "los memory_update de memoria de fallos no corresponden a los intentos fallidos de A_N y C_N"
        )


def transfer_index(record):
    """Posición declarada de una ejecución de H7 en su secuencia: una sola pasada, orden de la tarea."""
    return TASK_ORDER.index(record["task"]["id"])


def check_failure_transfer(runs, receipts):
    """Recibos de transferencia de fallos (H7, #65), después de ``single_policy``.

    Además de lo que exige H6 a cada recibo (``decision_inputs`` exacto, ``test-0`` fallido, condición
    coherente con el modo, la misma D en todas las condiciones de cada (lote, semilla, tarea)), el alcance τ
    y el placebo registrados deben ser los de su condición, y la decisión se repite desde el recibo con ese τ
    y ese placebo. Las bases A y C no tienen registros de fallo, y ningún registro aplicado tiene origen en la
    misma tarea (una sola pasada: por construcción, todo registro aplicado viene de otra tarea). Después,
    la misma cadena de registros que H6, en el orden de la única pasada.
    """
    transfer_runs = [r for r in runs if r["agent"] == TRANSFER_AGENT]
    stores = [u for u in receipts if u["kind"] == "memory_update" and "memory_store" in u]
    by_id = {r["run_id"]: r for r in transfer_runs}
    cells, diagnoses = defaultdict(list), defaultdict(set)
    for r in transfer_runs:
        tests = r["tests"]
        if (
            r.get("decision_inputs") != TRANSFER_DECISION_INPUTS
            or [t["id"] for t in tests] != [f"test-{i}" for i in range(len(tests))]
            or not tests[0]["returncode"]
        ):
            raise ValueError(
                "decisión de transferencia de fallos sin la reproducción previa declarada (test-0 fallido)"
            )
        if (
            not r.keys() >= TRANSFER_RUN_FIELDS
            or "pass" in r
            or r["condition"] not in TRANSFER_CONDITIONS
            or r["task"]["id"] not in TASK_ORDER
        ):
            raise ValueError(
                "recibo de transferencia de fallos sin condición, alcance o tarea declarados, o con pasada"
            )
        mode, enabled, tau, placebo = TRANSFER_CONDITIONS[r["condition"]]
        if mode != r["memory_mode"] or r["failure_scope_tau"] != tau or r["placebo"] is not placebo:
            raise ValueError("la condición no concuerda con el modo de memoria, el alcance τ o el placebo")
        if not enabled and (
            r["failure_memory_input"] or r["decision"]["failure_ids"] or r["failure_origins"]
        ):
            raise ValueError("las bases A y C no admiten registros de fallo")
        if r["decision"] != replay_transfer_decision(r):
            raise ValueError("la decisión de transferencia de fallos no se repite desde su recibo")
        cells[(r["batch_id"], r["seed"], r["condition"])].append(r)
        diagnoses[(r["batch_id"], r["seed"], r["task"]["id"])].add(digest(r["decision"]["diagnostic"]))
    if any(len(found) != 1 for found in diagnoses.values()):
        raise ValueError("las condiciones de una celda recibieron diagnósticos distintos")
    for r in transfer_runs:
        inputs = {x.get("id"): x for x in r["failure_memory_input"]}
        sources = [
            by_id.get(str(inputs.get(i, {}).get("evidence", "")).partition("#")[0])
            for i in r["decision"]["failure_ids"]
        ]
        if any(s is not None and s["task"]["id"] == r["task"]["id"] for s in sources) or any(
            o.get("origin") != "other_task" for o in r["failure_origins"]
        ):
            raise ValueError("registro de fallo aplicado con origen en la misma tarea")
    check_failure_chain(
        cells, by_id, stores, transfer_index, lambda condition: TRANSFER_CONDITIONS[condition][1]
    )


def strings_of(value):
    """Todas las claves y cadenas de una estructura JSON, en profundidad."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from strings_of(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings_of(item)
    elif isinstance(value, str):
        yield value


def private_tokens(metadata):
    """Claves de las anotaciones privadas y sus valores causales (``CAUSAL_ANNOTATIONS``), como tokens."""
    keys = {key for annotation in metadata.values() for key in annotation}
    values = {
        annotation[name]
        for annotation in metadata.values()
        for name in CAUSAL_ANNOTATIONS
        if isinstance(annotation.get(name), str)
    }
    return keys | values


def check_seed_material(record, block, forbidden):
    """Rechazo de una siembra con material privado o causal (H8, sección 8, punto 6).

    En C_S toda semilla está en un nodo ``Component`` de ``memory_input`` y su puntuación sale de la traza
    registrada en ``tests[0]``. Además, ni el bloque de siembra ni las rutas del contexto del agente
    contienen una ruta de ``benchmark/private/``, una clave de las anotaciones privadas o uno de sus valores
    causales. La búsqueda es por token exacto y solo ahí: el código fuente y el texto de la tarea tienen
    palabras públicas que coinciden con nombres de familia.
    """
    paths = list(record["initial_source"])
    found = [*strings_of(block), *paths]
    tokens = {token for text in found for token in (text, *_TOKEN.split(text))}
    if any(PRIVATE_PATH in text.replace("\\", "/") for text in found) or tokens & forbidden:
        raise ValueError("la siembra o el contexto del agente contienen material privado o causal")
    if block.get("signal") != TRACE_SIGNAL:
        return
    nodes = {n["id"]: n for n in (record["memory_input"] or {}).get("nodes", [])}
    weights = trace_weights(record["tests"][0]["stderr"], paths)
    for seed in block.get("seeds") or []:
        node = nodes.get(seed.get("node"))
        if node is None or node["type"] != SEED_NODE_TYPE:
            raise ValueError("semilla en un nodo que no es Component")
        score = max((weights.get(path, 0.0) for path in node["label"].split()), default=0.0)
        if score <= 0 or seed.get("score") != score:
            raise ValueError("puntuación de siembra que no sale de la traza registrada")


def check_trace_seed(runs, metadata):
    """Recibos de la recuperación sembrada (H8, #98), después de ``single_policy``.

    Cada recibo declara exactamente ``SEED_DECISION_INPUTS`` con un ``test-0`` fallido, y una condición
    coherente con su modo de memoria y con su señal de siembra. La siembra no usa material privado ni causal
    (``check_seed_material``). La recuperación se repite solo con ``tests[0].stderr``, las claves de
    ``initial_source`` y ``memory_input`` (más ``title + context`` en C_L) y debe coincidir con la registrada:
    componentes, puntuaciones, estado y lección expuesta. El contexto hasheado es el que cubre esas entradas,
    y la decisión se repite con el ``plan()`` por defecto. La señal extraída es la misma en las cuatro
    condiciones de cada (lote, semilla, tarea). La repetición prueba coherencia con lo registrado, no que no
    se consultó nada más: eso lo cubren la auditoría del módulo de siembra y el test de invariancia.
    """
    seed_runs = [r for r in runs if r["agent"] == SEED_AGENT]
    if not seed_runs:
        return
    forbidden = private_tokens(metadata)
    signals = defaultdict(set)
    for r in seed_runs:
        tests = r["tests"]
        consecutive = [t["id"] for t in tests] == [f"test-{i}" for i in range(len(tests))]
        reproduced = bool(tests) and tests[0]["returncode"] != 0
        if r.get("decision_inputs") != SEED_DECISION_INPUTS or not consecutive or not reproduced:
            raise ValueError("recuperación sembrada sin la reproducción previa declarada (test-0 fallido)")
        block = r["retrieval"].get(SEED_RETRIEVAL_FIELD)
        if r.get("condition") not in SEED_CONDITIONS or not isinstance(block, dict):
            raise ValueError("recibo de siembra sin condición o bloque de siembra declarados")
        mode, signal = SEED_CONDITIONS[r["condition"]]
        if mode != r["memory_mode"] or block.get("policy") != SEED_POLICY or block.get("signal") != signal:
            raise ValueError("la condición no concuerda con el modo de memoria o con la política de siembra")
        if r["memory_input"] is not None and digest(r["memory_input"]) != r["memory_before_sha256"]:
            raise ValueError("la memoria de entrada no es la que declara su huella")
        check_seed_material(r, block, forbidden)
        memories, paths, expected = replay_retrieval(r)
        if r["retrieval"] != {"memories": memories, "paths": paths, SEED_RETRIEVAL_FIELD: expected} or r[
            "retrieved_memories"
        ] != [m["id"] for m in memories]:
            raise ValueError("la recuperación sembrada no se repite desde su recibo")
        if r["agent_context_sha256"] != digest(replay_context(r)):
            raise ValueError("el contexto del agente no cubre lo que recibió la recuperación")
        if r["decision"] != replay_seed_decision(r):
            raise ValueError("la decisión de la recuperación sembrada no se repite desde su recibo")
        signals[(r["batch_id"], r["seed"], r["task"]["id"])].add(digest(block["components"]))
    if any(len(found) != 1 for found in signals.values()):
        raise ValueError("las condiciones de una celda recibieron señales distintas")


def seed_slices(runs):
    """Cortes del informe genérico de H8: A y B con cada una de las dos asociativas (C_L o C_S).

    Cada corte tiene como mucho una ejecución por (lote, semilla, tarea, modo), así que el emparejamiento
    con NO_MEMORY y las métricas genéricas no mezclan las dos siembras.
    """
    return {
        name: [r for r in runs if r["condition"] in ("A", "B", associative)]
        for name, associative in (("lexical-seed", "C_L"), ("trace-seed", "C_S"))
    }


def transfer_slices(runs):
    """Cortes del informe genérico de H7: sin memoria de fallos (A y C) y cada variante real o placebo por τ.

    Cada corte tiene las dos bases de una variante (A_x y C_x) con su entrenamiento y su única pasada: como
    mucho una ejecución por (lote, semilla, tarea, modo), así que el emparejamiento con NO_MEMORY no mezcla
    condiciones (A_x se empareja consigo mismo y C_x con A_x).
    """
    names = {"without-failure-memory": ""}
    for variant, placebo in VARIANTS.items():
        for suffix, tau in TAUS.items():
            names[f"{'placebo' if placebo else 'real'}-tau-{tau}"] = f"_{variant}{suffix}"
    return {
        name: [r for r in runs if r["condition"] in {base + suffix for base in BASES}]
        for name, suffix in names.items()
    }


def failure_slices(runs):
    """Cortes del informe genérico de H6: sin o con memoria de fallos, por pasada.

    Cada corte tiene como mucho una ejecución por (lote, semilla, tarea, modo): el entrenamiento de sus
    dos condiciones y la transferencia de una pasada. Así el emparejamiento con NO_MEMORY y las métricas
    genéricas no mezclan condiciones ni pasadas (A_N se empareja consigo mismo y C_N con A_N).
    """
    slices = {}
    for enabled, label in ((False, "without-failure-memory"), (True, "with-failure-memory")):
        for number in PASSES:
            slices[f"{label}-pass-{number}"] = [
                r
                for r in runs
                if CONDITIONS[r["condition"]][1] == enabled and (r["split"] == "train" or r["pass"] == number)
            ]
    return slices


def load_runs(evidence_dir):
    paths = sorted(Path(evidence_dir).glob("RUN-*.json"))
    receipts = [read_receipt(p) for p in paths]
    runs = [r for r in receipts if r["kind"] == "task_run"]
    # Fail closed. Excluding errors from denominator would bias the report.
    errors = [r["run_id"] for r in runs if r["result"] == "ERROR"]
    if errors:
        raise ValueError(f"Harness ERROR receipts require investigation; not a valid campaign: {errors}")
    return paths, receipts, runs


def evaluate(evidence_dir=None, output=None, root=ROOT):
    evidence_dir = Path(evidence_dir or root / "evidence/runs")
    paths, receipts, runs = load_runs(evidence_dir)
    single_scheme(receipts)
    single_policy(runs)
    check_diagnostic(runs)
    metadata = private_metadata(root)
    by_id = {r["run_id"]: r for r in runs}
    # Same normalization as the runner's source manifest. For v1 receipts it is
    # equivalent (universal-newline text) unless the file starts with a BOM.
    metadata_hash = source_sha256((root / "benchmark/private/tasks.json").read_bytes())
    for r in runs:
        if r["provenance"]["source_manifest"]["benchmark/private/tasks.json"] != metadata_hash:
            raise ValueError("private annotations differ from the executed benchmark")
        if digest(r["initial_source"]) != r["initial_source_sha256"]:
            raise ValueError("source snapshot mismatch")
        if hash_normalization(r) == SOURCE_HASH_NORMALIZATION and any(
            normalize_source(text) != text for text in r["initial_source"].values()
        ):
            raise ValueError("source snapshot is not normalized as declared")
        if r["memory_mode"] == "NO_MEMORY" and (r["retrieved_memories"] or r["memory_input"]):
            raise ValueError("no-memory contamination")
        for lesson in (r["memory_input"] or {}).get("lessons", []):
            prior = by_id.get(lesson["run_id"])
            if (
                prior is None
                or prior["split"] != "train"
                or prior["result"] != "PASS"
                or any(prior[k] != r[k] for k in ("batch_id", "seed", "memory_mode"))
                or prior.get("condition") != r.get("condition")  # H6 (#63): C y C_N no comparten lecciones
                or prior["receipt_sha256"] != lesson["receipt_sha256"]
            ):
                raise ValueError("memory provenance/leakage violation")
            refs = {prior["run_id"] + "#" + t["id"] for t in prior["tests"]}
            if not lesson["evidence"] or not set(lesson["evidence"]) <= refs:
                raise ValueError("unresolvable memory evidence")
    transfer = any(r["agent"] == TRANSFER_AGENT for r in runs)
    if transfer:
        check_failure_transfer(runs, receipts)
    else:
        check_failure_memory(runs, receipts)
    check_trace_seed(runs, metadata)
    check_extra_annotations(runs, root, source_manifest(root))
    generated_from = {p.name: r["receipt_sha256"] for p, r in zip(paths, receipts, strict=True)}
    if any(r["agent"] == FAILURE_AGENT for r in runs):
        return failure_memory_report(runs, metadata, generated_from, output)
    if transfer:
        return failure_transfer_report(runs, metadata, generated_from, output)
    if any(r["agent"] == SEED_AGENT for r in runs):
        return seed_report(runs, metadata, generated_from, output)
    comparisons, metrics, gains = paired(runs, metadata)
    return campaign_report(runs, metadata, generated_from, comparisons, metrics, gains, output)


def paired(runs, metadata):
    """Transfer runs paired with their NO_MEMORY baseline, per-mode metrics and LearningGain."""
    index = {}
    for r in runs:
        key = (r["batch_id"], r["seed"], r["task"]["id"], r["memory_mode"])
        if key in index:
            raise ValueError("duplicate condition in batch; use distinct batch IDs")
        index[key] = r
    groups = defaultdict(list)
    comparisons = []
    for r in runs:
        if r["split"] != "transfer":
            continue
        groups[r["memory_mode"]].append(r)
        baseline = index.get((r["batch_id"], r["seed"], r["task"]["id"], "NO_MEMORY"))
        if baseline is None or not comparable(baseline, r):
            raise ValueError("missing or mismatched paired no-memory baseline")
        selected_changed = baseline["decision"]["selected"] != r["decision"]["selected"]
        action_changed = baseline["actions"][0]["strategy"] != r["actions"][0]["strategy"]
        influenced = bool(r["decision"]["influenced_by_memory"] and r["decision"]["memory_ids"])
        improved = (r["outcome"]["success"] and not baseline["outcome"]["success"]) or (
            r["outcome"]["success"]
            and baseline["outcome"]["success"]
            and r["iterations"] < baseline["iterations"]
        )
        relevant = set(metadata[r["task"]["id"]]["relevant_training_tasks"])
        retrieved = {m["id"]: m["task"] for m in r["retrieval"]["memories"]}
        used_relevant = any(retrieved.get(mid) in relevant for mid in r["decision"]["memory_ids"])

        def details(item):
            inspected = item["actions"][0]["inspected"]
            relevant_file = metadata[item["task"]["id"]]["mutation"]["path"]
            return {
                "success": item["outcome"]["success"],
                "first_hypothesis": item["initial_hypothesis"],
                "first_file_inspected": inspected[0] if inspected else None,
                "first_relevant_file_inspected": relevant_file if relevant_file in inspected else None,
                "relevant_file_position": inspected.index(relevant_file) + 1
                if relevant_file in inspected
                else None,
                "iterations": item["iterations"],
                "failed_attempts": item["outcome"]["failed_attempts"],
                "tests_executed": len(item["tests"]),
                "duration_ms": item["duration_ms"],
                "retrieved_tasks": [m["task"] for m in item["retrieval"]["memories"]],
            }

        comparisons.append(
            {
                "baseline": baseline["run_id"],
                "treatment": r["run_id"],
                "task": r["task"]["id"],
                "mode": r["memory_mode"],
                "seed": r["seed"],
                "batch_id": r["batch_id"],
                "memory_available": bool(retrieved),
                "memory_used": bool(r["decision"]["memory_ids"]),
                "decision_changed": selected_changed,
                "action_changed": action_changed,
                "outcome_improved": improved,
                "memory_useful": bool(
                    retrieved and influenced and selected_changed and action_changed and improved
                ),
                "causally_relevant_memory_used": used_relevant,
                "causal_chain_supported": bool(
                    used_relevant and influenced and selected_changed and action_changed and improved
                ),
                "baseline_observations": details(baseline),
                "treatment_observations": details(r),
            }
        )
    metrics = {}
    for mode, items in sorted(groups.items()):
        matched = [p for p in comparisons if p["mode"] == mode]
        retrieved_count = relevant_count = possible = failures = repeated = retrieved_runs = 0
        for r in items:
            relevant = set(metadata[r["task"]["id"]]["relevant_training_tasks"])
            retrieved = [m["task"] for m in r["retrieval"]["memories"]]
            possible += len(relevant)
            retrieved_count += len(retrieved)
            relevant_count += len(set(retrieved) & relevant)
            retrieved_runs += bool(retrieved)
            known = any(
                t["result"] == "PASS"
                and t["split"] == "train"
                and t["batch_id"] == r["batch_id"]
                and t["seed"] == r["seed"]
                and t["memory_mode"] == mode
                and metadata[t["task"]["id"]]["hidden_cause_id"]
                == metadata[r["task"]["id"]]["hidden_cause_id"]
                for t in runs
            )
            for test in r["tests"][1:]:
                if test["returncode"] != 0:
                    failures += 1
                    repeated += bool(
                        known and signature(test) and signature(test) == signature(r["tests"][0])
                    )
        metrics[mode] = {
            "runs": len(items),
            "TaskSuccessRate": ratio(sum(r["outcome"]["success"] for r in items), len(items)),
            "FirstAttemptSuccessRate": ratio(
                sum(r["outcome"]["first_attempt_success"] for r in items), len(items)
            ),
            "IterationsPerTask": ratio(sum(r["iterations"] for r in items), len(items)),
            "RepeatedFailureRate": ratio(repeated, failures),
            "MemoryRetrievalRecall": ratio(relevant_count, possible),
            "MemoryRetrievalPrecision": ratio(relevant_count, retrieved_count),
            "MemoryUseRate": ratio(sum(p["memory_used"] for p in matched), retrieved_runs),
            "MemoryUtilityRate": ratio(sum(p["memory_useful"] for p in matched), retrieved_runs),
            "FalseRetrievalRate": ratio(retrieved_count - relevant_count, retrieved_count),
            "counts": {
                "retrieved": retrieved_count,
                "relevant_retrieved": relevant_count,
                "relevant_possible": possible,
                "runs_with_retrieval": retrieved_runs,
                "failures": failures,
                "repeated_known_cause_failures": repeated,
            },
        }
    baseline_metrics = metrics.get("NO_MEMORY", {})
    gains = {
        mode: {
            k: (v - baseline_metrics[k] if v is not None and baseline_metrics.get(k) is not None else None)
            for k, v in row.items()
            if k not in ("runs", "counts")
        }
        for mode, row in metrics.items()
        if mode != "NO_MEMORY"
    }
    return comparisons, metrics, gains


def replication(runs):
    replicas = {key: [digest(p) for p in items] for key, items in projections(runs).items()}
    return {
        "groups": len(replicas),
        "replicated_groups": sum(len(v) > 1 for v in replicas.values()),
        "all_semantic_projections_equal": all(len(set(v)) == 1 for v in replicas.values()),
    }


INTERPRETATION = (
    "Descriptive bounded-agent experiment. No statistical significance "
    "or autonomous software-engineering learning claim."
)
DEFINITIONS = {
    "RepeatedFailureRate": (
        "same reproduced exception signature and previously successful training cause "
        "/ all failed repair attempts; reproduction probes excluded"
    ),
    "MemoryUseRate": "runs explicitly citing memory in selection / runs with retrieval",
    "MemoryUtilityRate": (
        "retrieval changed first strategy and action and improved success or iterations "
        "vs paired baseline / runs with retrieval"
    ),
    "LearningGain": (
        "metric(memory) - metric(NO_MEMORY); negative IterationsPerTask is favorable; null means undefined"
    ),
    "time": "wall time is recorded but never used as proof of improvement",
    "replication": "same-seed determinism checks, not independent scientific samples",
}


def failure_memory_report(runs, metadata, generated_from, output):
    """Informe genérico de una campaña de memoria de fallos (#63), por corte (``failure_slices``).

    Misma forma que el informe de una campaña, con ``metrics``, ``LearningGain``, ``comparisons`` y
    ``replication`` indexados por corte. El análisis pre-registrado de H6 es
    ``scripts/analyze_failure_memory.py``; este informe sirve para la auditoría genérica.
    """
    return sliced_report(
        runs,
        metadata,
        generated_from,
        output,
        campaign="failure-memory-v1",
        slices=failure_slices(runs),
        definition=(
            "without/with failure memory (A+C / A_N+C_N) x transfer pass; each slice holds its "
            "training runs and one transfer pass, so pairs and metrics never mix conditions or passes"
        ),
        title="failure memory (#63)",
        analysis="Pre-registered H6 analysis: `python -m scripts.analyze_failure_memory`.",
    )


def failure_transfer_report(runs, metadata, generated_from, output):
    """Informe genérico de una campaña de transferencia de fallos (H7, #65), por corte (``transfer_slices``).

    El análisis pre-registrado de H7 es ``scripts/analyze_failure_transfer.py``; este informe sirve para la
    auditoría genérica.
    """
    return sliced_report(
        runs,
        metadata,
        generated_from,
        output,
        campaign="failure-transfer-v1",
        slices=transfer_slices(runs),
        definition=(
            "without failure memory (A+C) and each real or placebo variant by scope tau (A_x+C_x); each "
            "slice holds its training runs and its single transfer pass, so pairs and metrics never mix "
            "conditions"
        ),
        title="failure transfer (#65)",
        analysis="Pre-registered H7 analysis: `python -m scripts.analyze_failure_transfer`.",
    )


def seed_report(runs, metadata, generated_from, output):
    """Informe genérico de una campaña de recuperación sembrada (H8, #98), por corte (``seed_slices``).

    El análisis pre-registrado de H8 es ``scripts/analyze_h8.py``; este informe sirve para la auditoría
    genérica.
    """
    return sliced_report(
        runs,
        metadata,
        generated_from,
        output,
        campaign="nonlexical-seed-v1",
        slices=seed_slices(runs),
        definition=(
            "A and B with each associative condition (C_L lexical seed / C_S trace-component seed); each "
            "slice holds at most one run per batch, seed, task and memory mode, so pairs and metrics never "
            "mix the two seeding policies"
        ),
        title="non-lexical seed (#98)",
        analysis="Pre-registered H8 analysis: `python -m scripts.analyze_h8`.",
    )


def sliced_report(runs, metadata, generated_from, output, *, campaign, slices, definition, title, analysis):
    """Informe genérico por corte, común a H6 (#63) y H7 (#65)."""
    report = {
        "schema_id": "software-learning-results/v1",
        "campaign": campaign,
        "generated_from": generated_from,
        "metrics": {},
        "LearningGain": {},
        "comparisons": {},
        "replication": {},
        "interpretation": INTERPRETATION,
        "definitions": {**DEFINITIONS, "slices": definition},
    }
    for name, members in slices.items():
        comparisons, metrics, gains = paired(members, metadata)
        report["metrics"][name] = metrics
        report["LearningGain"][name] = gains
        report["comparisons"][name] = comparisons
        report["replication"][name] = replication(members)
    if output is not None:
        output = Path(output)
        output.mkdir(parents=True, exist_ok=True)
        (output / "experiment1.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        lines = [
            f"# Generated Experiment 1 results · {title}",
            "",
            report["interpretation"],
            "",
            f"Generated with `python -m experiments evaluate`. Do not edit by hand. {analysis}",
            "",
        ]
        for name, metrics in report["metrics"].items():
            for mode, row in metrics.items():
                lines.append(f"## {name} · {mode}\n")
                lines.extend(f"- {k}: {v}" for k, v in row.items())
                lines.append("")
        lines.extend(["## Replication", "", json.dumps(report["replication"]), ""])
        (output / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        for name, members in slices.items():
            write_breakdown(output / name, members, metadata)
            write_family_breakdown(output / name, members, metadata)
    return report


def campaign_report(runs, metadata, generated_from, comparisons, metrics, gains, output):
    report = {
        "schema_id": "software-learning-results/v1",
        "generated_from": generated_from,
        "metrics": metrics,
        "LearningGain": gains,
        "comparisons": comparisons,
        "replication": replication(runs),
        "interpretation": INTERPRETATION,
        "definitions": DEFINITIONS,
    }
    if output is not None:
        output = Path(output)
        output.mkdir(parents=True, exist_ok=True)
        (output / "experiment1.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        lines = [
            "# Generated Experiment 1 results",
            "",
            report["interpretation"],
            "",
            "Generated with `python -m experiments evaluate`. Do not edit by hand.",
            "",
        ]
        for mode, row in metrics.items():
            lines.append(f"## {mode}\n")
            lines.extend(f"- {k}: {v}" for k, v in row.items())
            lines.append("")
        lines.extend(
            [
                "## Replication",
                "",
                json.dumps(report["replication"]),
                "",
                "Full paired comparisons, denominators, receipt hashes and LearningGain: "
                "[experiment1.json](experiment1.json).",
            ]
        )
        (output / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        # Separate files so experiment1.json of the published campaign is unchanged (#45).
        write_breakdown(output, runs, metadata)
        write_family_breakdown(output, runs, metadata)
    return report


def projections(runs):
    """Semantic projections grouped by condition (seed, task, memory mode).

    Failure-memory receipts (#63) are also grouped by their declared condition and pass.
    """
    single_scheme(runs)
    groups = defaultdict(list)
    for r in runs:
        extra = (r["condition"], r.get("pass")) if "condition" in r else ()  # H7 (#65): sin pasada
        groups[(r["seed"], r["task"]["id"], r["memory_mode"], *extra)].append(semantic(r))
    return groups


def compare(reference_dir, candidate_dir):
    """Compare two campaigns' semantic projections, source/test hashes included.

    Both directories must use one and the same normalization scheme (otherwise
    ValueError). Each condition must be internally deterministic and present in
    both campaigns with an identical projection.
    """
    _, _, reference_runs = load_runs(reference_dir)
    _, _, candidate_runs = load_runs(candidate_dir)
    if not reference_runs or not candidate_runs:
        raise ValueError("both campaigns must contain task_run receipts")
    scheme = single_scheme([*reference_runs, *candidate_runs])

    def unique(groups, label):
        out, unstable = {}, []
        for key, items in sorted(groups.items()):
            distinct = {digest(p): p for p in items}
            if len(distinct) > 1:
                unstable.append(f"{label}:{key[1]}/{key[2]}/seed={key[0]}")
            out[key] = next(iter(distinct.values()))
        return out, unstable

    reference, unstable_ref = unique(projections(reference_runs), "reference")
    candidate, unstable_cand = unique(projections(candidate_runs), "candidate")
    differences = []
    for key in sorted(reference.keys() & candidate.keys()):
        a, b = reference[key], candidate[key]
        fields = sorted(k for k in a.keys() | b.keys() if a.get(k) != b.get(k))
        if fields:
            differences.append({"seed": key[0], "task": key[1], "mode": key[2], "fields": fields})

    def fmt(keys):
        return [f"{k[1]}/{k[2]}/seed={k[0]}" for k in sorted(keys)]

    report = {
        "hash_normalization": scheme,
        "reference_groups": len(reference),
        "candidate_groups": len(candidate),
        "missing_in_candidate": fmt(reference.keys() - candidate.keys()),
        "extra_in_candidate": fmt(candidate.keys() - reference.keys()),
        "nondeterministic_groups": unstable_ref + unstable_cand,
        "differences": differences,
    }
    report["identical"] = not (
        report["missing_in_candidate"]
        or report["extra_in_candidate"]
        or report["nondeterministic_groups"]
        or differences
    )
    return report
