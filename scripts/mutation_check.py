"""Verificación por mutación de las propiedades y de las salvaguardas del Experimento 1.

Inyecta un defecto conocido por vez en el código, ejecuta la propiedad que
debería detectarlo y restaura el archivo byte a byte. Si alguna mutación
**sobrevive**, la propiedad es débil (o tautológica) y el script falla.

Uso::

    python -m scripts.mutation_check
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MEMORY = ROOT / "src" / "associative_agent_loop" / "memory"
EXPERIMENTS = ROOT / "src" / "experiments"
PROPERTIES = "tests/unit/test_properties.py"
EXPERIMENT_TESTS = ["tests/test_experiment_harness.py", "tests/test_experiment_guards.py"]
# Línea base de diagnóstico (#58): trazas sintéticas (rápido) y conexión con runner/evaluador.
DIAGNOSTIC_TESTS = ["tests/test_experiment_diagnostic.py"]
DIAGNOSTIC_HARNESS = ["tests/test_experiment_diagnostic_harness.py"]
DIAGNOSTIC_ANALYSIS = ["tests/unit/test_analyze_diagnostic_baseline.py"]
# Memoria de fallos (#63): política y registros sintéticos, conexión con runner/evaluador y análisis.
FAILURE_TESTS = ["tests/test_experiment_failure_memory.py"]
FAILURE_HARNESS = ["tests/test_experiment_failure_memory_harness.py"]
FAILURE_ANALYSIS = ["tests/unit/test_analyze_failure_memory.py"]
# Transferencia de fallos (#65): alcance τ y placebo sintéticos, conexión con runner/evaluador y análisis.
TRANSFER_TESTS = ["tests/test_experiment_failure_transfer.py"]
TRANSFER_HARNESS = ["tests/test_experiment_failure_transfer_harness.py"]
TRANSFER_ANALYSIS = ["tests/unit/test_analyze_failure_transfer.py"]
# Recuperación sembrada (H8, #98): trazas y memorias sintéticas, conexión con runner/evaluador y análisis.
SEED_TESTS = ["tests/test_experiment_trace_seed.py"]
SEED_HARNESS = ["tests/test_experiment_trace_seed_harness.py"]
SEED_ANALYSIS = ["tests/unit/test_analyze_h8.py"]
CONTROLS = (
    [PROPERTIES],
    EXPERIMENT_TESTS,
    DIAGNOSTIC_TESTS,
    DIAGNOSTIC_HARNESS,
    DIAGNOSTIC_ANALYSIS,
    FAILURE_TESTS,
    FAILURE_HARNESS,
    FAILURE_ANALYSIS,
    TRANSFER_TESTS,
    TRANSFER_HARNESS,
    TRANSFER_ANALYSIS,
    SEED_TESTS,
    SEED_HARNESS,
    SEED_ANALYSIS,
)
FAILURE_SCRIPT = ROOT / "scripts" / "analyze_failure_memory.py"
TRANSFER_SCRIPT = ROOT / "scripts" / "analyze_failure_transfer.py"
SEED_SCRIPT = ROOT / "scripts" / "analyze_h8.py"

# (nombre, archivo, original, mutación, destino de pytest que debe detectarla)
# El destino es una lista de argumentos de pytest propia de cada mutación.
MUTATIONS = [
    (
        "sin saturación en 1.0",
        MEMORY / "associative.py",
        "activation[n] = min(1.0, activation.get(n, 0.0) + a)",
        "activation[n] = activation.get(n, 0.0) + a",
        [PROPERTIES, "-k", "test_activation_is_bounded_and_respects_threshold"],
    ),
    (
        "ranking no estable",
        MEMORY / "associative.py",
        "ranked = sorted(scored, key=lambda s: -s.score)",
        "ranked = sorted(scored, key=lambda s: s.action)",
        [PROPERTIES, "-k", "test_empty_memory_preserves_candidate_order"],
    ),
    (
        "decaimiento invertido",
        MEMORY / "graph.py",
        "math.exp(-edge.decay_factor * max(age, 0))",
        "math.exp(edge.decay_factor * max(age, 0))",
        [PROPERTIES, "-k", "test_effective_weight_never_increases_with_time"],
    ),
    (
        "valencia contextual sin normalizar",
        MEMORY / "associative.py",
        "return conf * (signed / mass) + (1 - conf) * global_val",
        "return signed + global_val",
        [PROPERTIES, "-k", "test_contextual_valence_is_bounded"],
    ),
    (
        "se pierde embedding_model al cargar",
        MEMORY / "graph.py",
        "mg.embedding_model = doc.embedding_model",
        "mg.embedding_model = None",
        [PROPERTIES, "-k", "test_serialization_roundtrip_for_any_history"],
    ),
    # Experimento 1 (grafo tipado software-learning-memory/v1)
    (
        "E1: esquema de memoria desconocido aceptado",
        EXPERIMENTS / "models.py",
        'schema_id: Literal["software-learning-memory/v1"] = ',
        "schema_id: str = ",
        EXPERIMENT_TESTS,
    ),
    (
        "E1: arista colgante aceptada",
        EXPERIMENTS / "models.py",
        'raise ValueError("dangling edge")',
        "pass",
        EXPERIMENT_TESTS,
    ),
    (
        "E1: ids de nodo duplicados aceptados",
        EXPERIMENTS / "models.py",
        'raise ValueError("duplicate node ids")',
        "pass",
        EXPERIMENT_TESTS,
    ),
    (
        "E1: reflexión sin evidencia aceptada",
        EXPERIMENTS / "models.py",
        'raise ValueError("A reflection is not evidence: references are required")',
        "pass",
        EXPERIMENT_TESTS,
    ),
    (
        "E1: memoria de evaluación admitida",
        EXPERIMENTS / "memory.py",
        'raise ValueError("evaluation memory is frozen")',
        "pass",
        EXPERIMENT_TESTS,
    ),
    (
        "E1: UPDATE/MERGE/DEPRECATE se vuelven ADD",
        EXPERIMENTS / "memory.py",
        "raise NotImplementedError(reflection.memory_action)",
        "pass",
        EXPERIMENT_TESTS,
    ),
    (
        "E1: hash de recibo no verificado",
        EXPERIMENTS / "evidence.py",
        'raise ValueError(f"receipt integrity failure: {path}")',
        "pass",
        EXPERIMENT_TESTS,
    ),
    (
        "E1: publicación sobrescribe",
        EXPERIMENTS / "evidence.py",
        "os.link(temporary, target)",
        "os.replace(temporary, target)",
        EXPERIMENT_TESTS,
    ),
    # Línea base de diagnóstico (#58)
    (
        "D: candidatos por unión, no intersección",
        EXPERIMENTS / "diagnostic.py",
        "allowed &= set(FAILURE_MODES[mode])",
        "allowed |= set(FAILURE_MODES[mode])",
        DIAGNOSTIC_TESTS,
    ),
    (
        "D: la memoria precede al diagnóstico",
        EXPERIMENTS / "diagnostic.py",
        "key=lambda op: (op not in candidates, op != proposal, prior.index(op))",
        "key=lambda op: (op != proposal, op not in candidates, prior.index(op))",
        DIAGNOSTIC_TESTS,
    ),
    (
        "D: marcador NoneType ignorado",
        EXPERIMENTS / "diagnostic.py",
        'issubclass(cls, (TypeError, AttributeError)) and feature["none_marker"]',
        "issubclass(cls, (TypeError, AttributeError))",
        DIAGNOSTIC_TESTS,
    ),
    (
        "D: fallback ambiguo distinto de DEFAULT",
        EXPERIMENTS / "diagnostic.py",
        'status, allowed = "ambiguous", set(STRATEGIES)',
        'status, allowed = "ambiguous", {"initialize_storage"}',
        DIAGNOSTIC_TESTS,
    ),
    (
        "D: el agente ignora la reproducción",
        EXPERIMENTS / "diagnostic.py",
        'diagnosis = diagnose(reproduction.get("stderr"))',
        "diagnosis = diagnose(None)",
        DIAGNOSTIC_TESTS,
    ),
    (
        "D: la reproducción llega después de decidir",
        EXPERIMENTS / "runner.py",
        'if getattr(agent, "reads_reproduction", False):',
        "if False:",
        DIAGNOSTIC_HARNESS,
    ),
    (
        "D: evaluador no repite la decisión",
        EXPERIMENTS / "evaluate.py",
        'raise ValueError("diagnostic decision does not replay from its receipt")',
        "pass",
        DIAGNOSTIC_HARNESS,
    ),
    (
        "D: evaluador acepta mezcla de políticas",
        EXPERIMENTS / "evaluate.py",
        "if len(policies) > 1:",
        "if len(policies) > 9:",
        DIAGNOSTIC_HARNESS,
    ),
    (
        "D: evaluador acepta diagnósticos distintos por celda",
        EXPERIMENTS / "evaluate.py",
        "if any(len(found) > 1 for found in diagnoses.values()):",
        "if False:",
        DIAGNOSTIC_HARNESS,
    ),
    (
        "D: evaluador no exige test-0 como primera prueba",
        EXPERIMENTS / "evaluate.py",
        'or [t["id"] for t in tests] != [f"test-{i}" for i in range(len(tests))]',
        "or False",
        DIAGNOSTIC_HARNESS,
    ),
    (
        "D: análisis con margen estricto",
        ROOT / "scripts" / "analyze_diagnostic_baseline.py",
        "if difference >= MARGIN:",
        "if difference > MARGIN:",
        DIAGNOSTIC_ANALYSIS,
    ),
    (
        "D: decision_inputs solo por existencia",
        EXPERIMENTS / "evaluate.py",
        'r.get("decision_inputs") != DECISION_INPUTS',
        '"decision_inputs" not in r',
        DIAGNOSTIC_HARNESS,
    ),
    (
        "D: reproducción que no falla aceptada",
        EXPERIMENTS / "evaluate.py",
        'or tests[0]["returncode"] == 0',
        "or False",
        DIAGNOSTIC_HARNESS,
    ),
    (
        "D: agente de diagnóstico sin su política aceptado",
        EXPERIMENTS / "evaluate.py",
        'elif decision.get("policy") != expected:',
        "elif False:",
        DIAGNOSTIC_HARNESS,
    ),
    (
        "D: agente desconocido aceptado sin política",
        EXPERIMENTS / "evaluate.py",
        'raise ValueError(f"unknown agent: {agent!r}")',
        "return agent, None",
        DIAGNOSTIC_HARNESS,
    ),
    (
        "D: agente por defecto con campos de diagnóstico",
        EXPERIMENTS / "evaluate.py",
        'if DIAGNOSTIC_FIELDS & decision.keys() or "decision_inputs" in record:',
        "if False:",
        DIAGNOSTIC_HARNESS,
    ),
    (
        "D: análisis acepta una sola réplica",
        ROOT / "scripts" / "analyze_diagnostic_baseline.py",
        "if len(batches) != REPLICATES:",
        "if len(batches) > REPLICATES:",
        DIAGNOSTIC_ANALYSIS,
    ),
    (
        "D: análisis acepta lotes incompletos",
        ROOT / "scripts" / "analyze_diagnostic_baseline.py",
        "if found != expected:",
        "if not found <= expected:",
        DIAGNOSTIC_ANALYSIS,
    ),
    (
        "D: análisis acepta entrenamiento futuro",
        ROOT / "scripts" / "analyze_diagnostic_baseline.py",
        'or order[prior["task"]["id"]] >= order[r["task"]["id"]]',
        "or False",
        DIAGNOSTIC_ANALYSIS,
    ),
    (
        "D: análisis sin verificar el sello",
        ROOT / "scripts" / "analyze_diagnostic_baseline.py",
        "if checksum is None or hashlib.sha256(canonical(record)).hexdigest() != checksum:",
        "if checksum is None:",
        DIAGNOSTIC_ANALYSIS,
    ),
    # Memoria de fallos con revisión (#63)
    (
        "H6: la memoria de fallos precede al diagnóstico",
        EXPERIMENTS / "failure_memory.py",
        "key=lambda op: (op not in candidates, op in failed, op != proposal, prior.index(op)),",
        "key=lambda op: (op in failed, op not in candidates, op != proposal, prior.index(op)),",
        FAILURE_TESTS,
    ),
    (
        "H6: la lección precede a la memoria de fallos",
        EXPERIMENTS / "failure_memory.py",
        "key=lambda op: (op not in candidates, op in failed, op != proposal, prior.index(op)),",
        "key=lambda op: (op not in candidates, op != proposal, op in failed, prior.index(op)),",
        FAILURE_TESTS,
    ),
    (
        "H6: alcance sin firma idéntica",
        EXPERIMENTS / "failure_memory.py",
        "applies = same and similarity >= tau",
        "applies = similarity >= tau",
        FAILURE_TESTS,
    ),
    (
        "H6: umbral de similitud estricto",
        EXPERIMENTS / "failure_memory.py",
        "applies = same and similarity >= tau",
        "applies = same and similarity > tau",
        FAILURE_TESTS,
    ),
    (
        "H6: registro de un intento que pasó",
        EXPERIMENTS / "failure_memory.py",
        'if test["returncode"] == 0:',
        "if False:",
        FAILURE_TESTS,
    ),
    (
        "H6: registros escritos desde A o C",
        EXPERIMENTS / "failure_memory.py",
        'raise ValueError("la memoria de fallos solo se escribe desde recibos de A_N y C_N")',
        "pass",
        FAILURE_TESTS,
    ),
    (
        "H6: el agente no recibe la memoria de fallos",
        EXPERIMENTS / "runner.py",
        "failures=tuple(copy.deepcopy(failure_input)),",
        "failures=(),",
        FAILURE_HARNESS,
    ),
    (
        "H6: origen anotado sin leer el recibo",
        EXPERIMENTS / "runner.py",
        '{"id": i, "origin": failures.origin(i, task.id)}',
        '{"id": i, "origin": "other_task"}',
        FAILURE_HARNESS,
    ),
    (
        "H6: evaluador no repite la decisión",
        EXPERIMENTS / "evaluate.py",
        'if r["decision"] != replay_failure_decision(r):',
        "if False:",
        FAILURE_HARNESS,
    ),
    (
        "H6: evaluador acepta una memoria incompleta",
        EXPERIMENTS / "evaluate.py",
        "if inputs != [expected_failure_record(by_id[source], i) for source, i in written]:",
        "if False:",
        FAILURE_HARNESS,
    ),
    (
        "H6: evaluador acepta un registro posterior",
        EXPERIMENTS / "evaluate.py",
        'if position[source_id] >= position[run["run_id"]]:',
        "if False:",
        FAILURE_HARNESS,
    ),
    (
        "H6: evaluador acepta un registro de un test que pasó",
        EXPERIMENTS / "evaluate.py",
        'if index < 1 or test["returncode"] == 0:',
        "if index < 1:",
        FAILURE_HARNESS,
    ),
    (
        "H6: evaluador acepta campos de H6 en otros agentes",
        EXPERIMENTS / "evaluate.py",
        "if agent not in FAILURE_AGENTS and (FAILURE_FIELDS & decision.keys() or FAILURE_RECORD_FIELDS"
        " & carried):",
        "if False:",
        FAILURE_HARNESS,
    ),
    (
        "H6: evaluador acepta lecciones de otra condición",
        EXPERIMENTS / "evaluate.py",
        'or prior.get("condition") != r.get("condition")',
        "or False",
        FAILURE_HARNESS,
    ),
    (
        "H6: análisis acepta una sola réplica",
        FAILURE_SCRIPT,
        "if len(batches) != REPLICATES:",
        "if len(batches) > REPLICATES:",
        FAILURE_ANALYSIS,
    ),
    (
        "H6: análisis acepta lotes incompletos",
        FAILURE_SCRIPT,
        "if found != expected:",
        "if not found <= expected:",
        FAILURE_ANALYSIS,
    ),
    (
        "H6: análisis acepta registros en A o C",
        FAILURE_SCRIPT,
        'if not enabled and (inputs or r["decision"]["failure_ids"] or r["failure_origins"]):',
        "if False:",
        FAILURE_ANALYSIS,
    ),
    (
        "H6: análisis acepta registros posteriores",
        FAILURE_SCRIPT,
        "if source is None or position(source) >= position(r):",
        "if source is None:",
        FAILURE_ANALYSIS,
    ),
    (
        "H6: análisis acepta registros de un test que pasó",
        FAILURE_SCRIPT,
        'if index < 1 or source["tests"][index]["returncode"] == 0:',
        "if index < 1:",
        FAILURE_ANALYSIS,
    ),
    (
        "H6: repetición contada al revés",
        FAILURE_SCRIPT,
        'r["actions"][0]["strategy"] in earlier_failures',
        'r["actions"][0]["strategy"] not in earlier_failures',
        FAILURE_ANALYSIS,
    ),
    (
        "H6a: holgura estricta",
        FAILURE_SCRIPT,
        'headroom = rx["numerator"] >= MARGIN',
        'headroom = rx["numerator"] > MARGIN',
        FAILURE_ANALYSIS,
    ),
    (
        "H6a: celda con holgura sin margen",
        FAILURE_SCRIPT,
        'limit = rx["numerator"] - MARGIN if headroom else rx["numerator"]',
        'limit = rx["numerator"]',
        FAILURE_ANALYSIS,
    ),
    (
        "H6b: hurt nunca contado",
        FAILURE_SCRIPT,
        "if target_ok and not new_ok:",
        "if False:",
        FAILURE_ANALYSIS,
    ),
    (
        "H6: control de determinismo ignorado",
        FAILURE_SCRIPT,
        "valid = consistent and control and denominators",
        "valid = consistent and denominators",
        FAILURE_ANALYSIS,
    ),
    # Transferencia y contaminación de la memoria de fallos (#65)
    (
        "H7: el alcance ignora τ (siempre 0.5)",
        EXPERIMENTS / "failure_transfer.py",
        "decision = self.failure_decision(view, 0.0 if tau is None else tau, demote)",
        "decision = self.failure_decision(view, 0.5, demote)",
        TRANSFER_TESTS,
    ),
    (
        "H7: scope() no recibe el τ parametrizado",
        EXPERIMENTS / "failure_memory.py",
        "item = scope(record, signature, query, tau)",
        "item = scope(record, signature, query)",
        TRANSFER_TESTS,
    ),
    (
        "H7: placebo sin rotación",
        EXPERIMENTS / "failure_transfer.py",
        "demote = rotate if placebo else unchanged",
        "demote = unchanged",
        TRANSFER_TESTS,
    ),
    (
        "H7: rotación del placebo al revés",
        EXPERIMENTS / "failure_transfer.py",
        "STRATEGIES[(i + 1) % len(STRATEGIES)]",
        "STRATEGIES[(i - 1) % len(STRATEGIES)]",
        TRANSFER_TESTS,
    ),
    (
        "H7: F con la estrategia registrada en el placebo",
        EXPERIMENTS / "failure_memory.py",
        'failed.add(demote(record["strategy"]))',
        'failed.add(record["strategy"])',
        TRANSFER_TESTS,
    ),
    (
        "H7: runner sin validar la condición de transferencia",
        EXPERIMENTS / "runner.py",
        "or TRANSFER_CONDITIONS[condition][:2] != (mode, failures is not None)",
        "or False",
        TRANSFER_TESTS,
    ),
    (
        "H7: el agente no recibe τ ni placebo",
        EXPERIMENTS / "runner.py",
        "view = TransferView(**vars(view), scope_tau=scope_tau, placebo=placebo)",
        "view = TransferView(**vars(view), scope_tau=0.5)",
        TRANSFER_HARNESS,
    ),
    (
        "H7: recibo con un τ distinto del de su condición",
        EXPERIMENTS / "runner.py",
        'record["failure_scope_tau"] = scope_tau',
        'record["failure_scope_tau"] = 0.5',
        TRANSFER_HARNESS,
    ),
    (
        "H7: evaluador no repite la decisión",
        EXPERIMENTS / "evaluate.py",
        'if r["decision"] != replay_transfer_decision(r):',
        "if False:",
        TRANSFER_HARNESS,
    ),
    (
        "H7: evaluador acepta τ o placebo distintos de la condición",
        EXPERIMENTS / "evaluate.py",
        'if mode != r["memory_mode"] or r["failure_scope_tau"] != tau or r["placebo"] is not placebo:',
        'if mode != r["memory_mode"]:',
        TRANSFER_HARNESS,
    ),
    (
        "H7: evaluador acepta registros en A y C",
        EXPERIMENTS / "evaluate.py",
        'raise ValueError("las bases A y C no admiten registros de fallo")',
        "pass",
        TRANSFER_HARNESS,
    ),
    (
        "H7: evaluador acepta un registro aplicado de la misma tarea",
        EXPERIMENTS / "evaluate.py",
        'raise ValueError("registro de fallo aplicado con origen en la misma tarea")',
        "pass",
        TRANSFER_HARNESS,
    ),
    (
        "H7: evaluador sin la cadena de registros de H6",
        EXPERIMENTS / "evaluate.py",
        "    check_failure_chain(\n"
        "        cells, by_id, stores, transfer_index, lambda condition: TRANSFER_CONDITIONS[condition][1]\n"
        "    )",
        "    pass",
        TRANSFER_HARNESS,
    ),
    (
        "H7: evaluador acepta campos de H7 en otros agentes",
        EXPERIMENTS / "evaluate.py",
        "if agent != TRANSFER_AGENT and (",
        "if False and (",
        TRANSFER_HARNESS,
    ),
    (
        "H7: análisis acepta una sola réplica",
        TRANSFER_SCRIPT,
        "if len(batches) != REPLICATES:",
        "if len(batches) > REPLICATES:",
        TRANSFER_ANALYSIS,
    ),
    (
        "H7: análisis acepta lotes incompletos",
        TRANSFER_SCRIPT,
        "if found != expected:",
        "if not found <= expected:",
        TRANSFER_ANALYSIS,
    ),
    (
        "H7: análisis acepta réplicas distintas",
        TRANSFER_SCRIPT,
        "if behaviour(r, by_id) != behaviour(twin, by_id):",
        "if False:",
        TRANSFER_ANALYSIS,
    ),
    (
        "H7: análisis acepta registros en las bases",
        TRANSFER_SCRIPT,
        'if not enabled and (inputs or r["decision"]["failure_ids"] or r["failure_origins"]):',
        "if False:",
        TRANSFER_ANALYSIS,
    ),
    (
        "H7: análisis acepta un registro aplicado de la misma tarea",
        TRANSFER_SCRIPT,
        "raise ValueError(f\"registro aplicado con origen en la misma tarea en {r['run_id']}\")",
        "pass",
        TRANSFER_ANALYSIS,
    ),
    (
        "H7: análisis verifica el placebo sin rotar",
        TRANSFER_SCRIPT,
        'demotes = ROTATION[record["strategy"]] if placebo else record["strategy"]',
        'demotes = record["strategy"]',
        TRANSFER_ANALYSIS,
    ),
    (
        "H7: análisis no compara la similitud con τ",
        TRANSFER_SCRIPT,
        'or item.get("applies") is not (match and tau is not None and item["similarity"] >= tau)',
        'or item.get("applies") is not (match and tau is not None)',
        TRANSFER_ANALYSIS,
    ),
    (
        "H7: exposición con margen estricto",
        TRANSFER_SCRIPT,
        '"exposure": EXPOSED if changed >= MARGIN else NOT_EXPOSED,',
        '"exposure": EXPOSED if changed > MARGIN else NOT_EXPOSED,',
        TRANSFER_ANALYSIS,
    ),
    (
        "H7: helped sin parear con la base",
        TRANSFER_SCRIPT,
        "helped = sum(first_ok(v) and not first_ok(x) for v, x in zip(variant, base, strict=True))",
        "helped = sum(first_ok(v) for v, x in zip(variant, base, strict=True))",
        TRANSFER_ANALYSIS,
    ),
    (
        "H7: hurt nunca contado",
        TRANSFER_SCRIPT,
        "hurt = sum(first_ok(x) and not first_ok(v) for v, x in zip(variant, base, strict=True))",
        "hurt = 0",
        TRANSFER_ANALYSIS,
    ),
    (
        "H7a: lee celdas sin exposición",
        TRANSFER_SCRIPT,
        "readable = [k for k in KINDS if exposed(cells[k])]",
        "readable = list(KINDS)",
        TRANSFER_ANALYSIS,
    ),
    (
        "H7b: un tipo sin exposición debe tener hurt = 0 observado",
        TRANSFER_SCRIPT,
        '"hurt_zero": (not readable) or cells[k]["hurt"]["numerator"] == 0,',
        '"hurt_zero": cells[k]["hurt"]["numerator"] == 0,',
        TRANSFER_ANALYSIS,
    ),
    (
        "H7b: exige helped ≥ 3 en los dos tipos",
        TRANSFER_SCRIPT,
        'elif any(v["helped_at_least_margin"] for v in kinds.values()) and all(',
        'elif all(v["helped_at_least_margin"] for v in kinds.values()) and all(',
        TRANSFER_ANALYSIS,
    ),
    (
        "H7c: margen estricto",
        TRANSFER_SCRIPT,
        "elif difference >= MARGIN:",
        "elif difference > MARGIN:",
        TRANSFER_ANALYSIS,
    ),
    (
        "H7c: signo invertido",
        TRANSFER_SCRIPT,
        'difference = real["NetTransfer"] - placebo["NetTransfer"]',
        'difference = placebo["NetTransfer"] - real["NetTransfer"]',
        TRANSFER_ANALYSIS,
    ),
    (
        "H7: conclusión sobre la base A",
        TRANSFER_SCRIPT,
        'CONCLUSION_BASE = "C"',
        'CONCLUSION_BASE = "A"',
        TRANSFER_ANALYSIS,
    ),
    (
        "H7: conclusión sin exigir el contraste con el placebo",
        TRANSFER_SCRIPT,
        'c[k]["verdict"] == "el contenido importa" for k in where',
        "True for k in where",
        TRANSFER_ANALYSIS,
    ),
    # Recuperación sembrada con los componentes de la traza (H8, #98)
    (
        "H8: se usa la primera traza del bloque",
        EXPERIMENTS / "trace_seed.py",
        "for line in block[starts[-1] + 1 :]:",
        "for line in block[starts[0] + 1 :]:",
        SEED_TESTS,
    ),
    (
        "H8: peso sin distancia a la excepción",
        EXPERIMENTS / "trace_seed.py",
        "weights[component] = max(weights.get(component, 0.0), 1 / (1 + distance))",
        "weights[component] = max(weights.get(component, 0.0), 1.0)",
        SEED_TESTS,
    ),
    (
        "H8: cuenta la aparición más externa",
        EXPERIMENTS / "trace_seed.py",
        "for i, component in enumerate(chain, 1)}",
        "for i, component in reversed(list(enumerate(chain, 1)))}",
        SEED_TESTS,
    ),
    (
        "H8: mínimo entre bloques",
        EXPERIMENTS / "trace_seed.py",
        "weights[component] = max(weights.get(component, 0.0), 1 / (1 + distance))",
        "weights[component] = min(weights.get(component, 1.0), 1 / (1 + distance))",
        SEED_TESTS,
    ),
    (
        "H8: marco sin exigir el separador de ruta",
        EXPERIMENTS / "trace_seed.py",
        'path.endswith("/" + k)',
        "path.endswith(k)",
        SEED_TESTS,
    ),
    (
        "H8: resumen final sin cortar",
        EXPERIMENTS / "trace_seed.py",
        "body = body[: i - 1]",
        "pass",
        SEED_TESTS,
    ),
    (
        "H8: se siembran nodos que no son Component",
        EXPERIMENTS / "trace_seed.py",
        'if node["type"] != SEED_NODE_TYPE:',
        "if False:",
        SEED_TESTS,
    ),
    (
        "H8: el empate se resuelve por orden",
        EXPERIMENTS / "trace_seed.py",
        "if len(leaders) > 1:",
        "if False:",
        SEED_TESTS,
    ),
    (
        "H8: corte de activación ignorado",
        EXPERIMENTS / "trace_seed.py",
        ">= ACTIVATION_CUT][:1]",
        ">= 0][:1]",
        SEED_TESTS,
    ),
    (
        "H8: C_S con la siembra léxica de H4",
        EXPERIMENTS / "nonlexical_seed.py",
        "    if signal == TRACE:\n        memories, paths, block = seeded_retrieval(",
        "    if False:\n        memories, paths, block = seeded_retrieval(",
        SEED_TESTS,
    ),
    (
        "H8: el agente no declara su política",
        EXPERIMENTS / "nonlexical_seed.py",
        'return {**super().plan(view), "policy": POLICY}',
        "return {**super().plan(view)}",
        SEED_TESTS,
    ),
    (
        "H8: la reproducción no precede a la recuperación",
        EXPERIMENTS / "runner.py",
        'seed_stderr = reproduce(workspace, record)["stderr"]',
        'seed_stderr = ""',
        SEED_HARNESS,
    ),
    (
        "H8: reproducción que altera el workspace aceptada",
        EXPERIMENTS / "runner.py",
        'raise ValueError("la reproducción previa modificó el workspace observable")',
        "pass",
        SEED_HARNESS,
    ),
    (
        "H8: runner sin validar el modo de la condición",
        EXPERIMENTS / "runner.py",
        "or SEED_CONDITIONS[condition][0] != mode",
        "or False",
        SEED_HARNESS,
    ),
    (
        "H8: el contexto hasheado no cubre la traza",
        EXPERIMENTS / "nonlexical_seed.py",
        'inputs["stderr"] = stderr',
        "pass",
        SEED_HARNESS,
    ),
    (
        "H8: evaluador no repite la recuperación",
        EXPERIMENTS / "evaluate.py",
        'raise ValueError("la recuperación sembrada no se repite desde su recibo")',
        "pass",
        SEED_HARNESS,
    ),
    (
        "H8: evaluador no repite la decisión",
        EXPERIMENTS / "evaluate.py",
        'raise ValueError("la decisión de la recuperación sembrada no se repite desde su recibo")',
        "pass",
        SEED_HARNESS,
    ),
    (
        "H8: evaluador acepta una semilla fuera de Component",
        EXPERIMENTS / "evaluate.py",
        'raise ValueError("semilla en un nodo que no es Component")',
        "continue",
        SEED_HARNESS,
    ),
    (
        "H8: evaluador acepta una puntuación que no sale de la traza",
        EXPERIMENTS / "evaluate.py",
        'raise ValueError("puntuación de siembra que no sale de la traza registrada")',
        "pass",
        SEED_HARNESS,
    ),
    (
        "H8: evaluador acepta material privado o causal",
        EXPERIMENTS / "evaluate.py",
        'raise ValueError("la siembra o el contexto del agente contienen material privado o causal")',
        "pass",
        SEED_HARNESS,
    ),
    (
        "H8: material privado buscado solo como ruta",
        EXPERIMENTS / "evaluate.py",
        "or tokens & forbidden:",
        "or False:",
        SEED_HARNESS,
    ),
    (
        "H8: decision_inputs solo por existencia",
        EXPERIMENTS / "evaluate.py",
        'r.get("decision_inputs") != SEED_DECISION_INPUTS',
        '"decision_inputs" not in r',
        SEED_HARNESS,
    ),
    (
        "H8: reproducción que no falla aceptada",
        EXPERIMENTS / "evaluate.py",
        'reproduced = bool(tests) and tests[0]["returncode"] != 0',
        "reproduced = True",
        SEED_HARNESS,
    ),
    (
        "H8: evaluador no exige test-0 como primera prueba",
        EXPERIMENTS / "evaluate.py",
        'consecutive = [t["id"] for t in tests] == [f"test-{i}" for i in range(len(tests))]',
        "consecutive = True",
        SEED_HARNESS,
    ),
    (
        "H8: evaluador acepta una condición incoherente con su siembra",
        EXPERIMENTS / "evaluate.py",
        'if mode != r["memory_mode"] or block.get("policy") != SEED_POLICY or block.get("signal") != signal:',
        "if False:",
        SEED_HARNESS,
    ),
    (
        "H8: evaluador acepta señales distintas por celda",
        EXPERIMENTS / "evaluate.py",
        "if any(len(found) != 1 for found in signals.values()):",
        "if False:",
        SEED_HARNESS,
    ),
    (
        "H8: evaluador acepta un contexto que no cubre la recuperación",
        EXPERIMENTS / "evaluate.py",
        'raise ValueError("el contexto del agente no cubre lo que recibió la recuperación")',
        "pass",
        SEED_HARNESS,
    ),
    (
        "H8: evaluador acepta campos de H8 en otros agentes",
        EXPERIMENTS / "evaluate.py",
        'if agent != SEED_AGENT and SEED_RETRIEVAL_FIELD in record.get("retrieval", {}):',
        "if False:",
        SEED_HARNESS,
    ),
    (
        "H8: el agente de siembra queda exento de los campos de H6",
        EXPERIMENTS / "evaluate.py",
        "carried = record.keys() - SEED_RECORD_FIELDS if agent == SEED_AGENT else record.keys()",
        "carried = record.keys() - FAILURE_RECORD_FIELDS if agent == SEED_AGENT else record.keys()",
        SEED_HARNESS,
    ),
    (
        "H8: análisis con margen estricto frente a los controles",
        SEED_SCRIPT,
        "if delta_ctrl < MARGIN:",
        "if delta_ctrl <= MARGIN:",
        SEED_ANALYSIS,
    ),
    (
        "H8: «mejora» con margen estricto frente a A",
        SEED_SCRIPT,
        "if delta_a >= MARGIN:",
        "if delta_a > MARGIN:",
        SEED_ANALYSIS,
    ),
    (
        "H8: «peor que sin memoria» con margen estricto",
        SEED_SCRIPT,
        "if delta_a <= -MARGIN:",
        "if delta_a < -MARGIN:",
        SEED_ANALYSIS,
    ),
    (
        "H8: selección cumplida con S = 3",
        SEED_SCRIPT,
        "return decoy_cited < MARGIN",
        "return decoy_cited <= MARGIN",
        SEED_ANALYSIS,
    ),
    (
        "H8: Δ_ctrl con el control más favorable",
        SEED_SCRIPT,
        "delta_ctrl = min(delta_b, delta_l)",
        "delta_ctrl = max(delta_b, delta_l)",
        SEED_ANALYSIS,
    ),
    (
        "H8: «apoyada» sin exigir la selección",
        SEED_SCRIPT,
        '(IMPROVES, False): "no apoyada: mejora, pero sigue citando el señuelo",',
        "(IMPROVES, False): SUPPORTED,",
        SEED_ANALYSIS,
    ),
    (
        "H8: marca «sin exposición» con margen estricto",
        SEED_SCRIPT,
        "silent = cited_runs < MARGIN",
        "silent = cited_runs <= MARGIN",
        SEED_ANALYSIS,
    ),
    (
        "H8: coste en las originales con margen estricto",
        SEED_SCRIPT,
        "WITH_COST if delta_orig <= -MARGIN",
        "WITH_COST if delta_orig < -MARGIN",
        SEED_ANALYSIS,
    ),
    (
        "H8: señuelo y otra lección confundidos",
        SEED_SCRIPT,
        'return (DECOY if family == target.get("decoy_family") else OTHER), cited[0]',
        'return (OTHER if family == target.get("decoy_family") else DECOY), cited[0]',
        SEED_ANALYSIS,
    ),
    (
        "H8: análisis acepta réplicas distintas",
        SEED_SCRIPT,
        "if behaviour(r) != behaviour(twin):",
        "if False:",
        SEED_ANALYSIS,
    ),
    (
        "H8: análisis sin comparar los controles con la referencia",
        SEED_SCRIPT,
        'and behaviour(r) != behaviour(cells[(r["memory_mode"], r["task"]["id"], r["seed"])])',
        "and False",
        SEED_ANALYSIS,
    ),
    (
        "H8: análisis acepta una sola réplica",
        SEED_SCRIPT,
        "if len(batches) != REPLICATES:",
        "if len(batches) > REPLICATES:",
        SEED_ANALYSIS,
    ),
    (
        "H8: análisis acepta lotes incompletos",
        SEED_SCRIPT,
        "if found != expected:",
        "if not found <= expected:",
        SEED_ANALYSIS,
    ),
    (
        "H8: análisis acepta un recibo ERROR",
        SEED_SCRIPT,
        'if r.get("result") not in ("PASS", "FAIL"):',
        "if False:",
        SEED_ANALYSIS,
    ),
    (
        "H8: análisis sin verificar el sello",
        SEED_SCRIPT,
        "if checksum is None or hashlib.sha256(canonical(record)).hexdigest() != checksum:",
        "if checksum is None:",
        SEED_ANALYSIS,
    ),
]


def pytest_run(targets: list[str]) -> subprocess.CompletedProcess[str]:
    pytest = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-x"]
    return subprocess.run([*pytest, *targets], cwd=ROOT, capture_output=True, text=True)


def control() -> bool:
    """Ejecución sin mutar: si falla, los resultados de mutación serían inválidos."""
    ok = True
    for targets in CONTROLS:
        result = pytest_run(targets)
        status = "VERDE " if result.returncode == 0 else "ROJO  "
        print(f"CONTROL {status} {' '.join(targets)}")
        if result.returncode != 0:
            print(result.stdout[-2000:])
            ok = False
    return ok


def run() -> bool:
    if not control():
        print("ERROR   el control sin mutación falla: los resultados serían inválidos")
        return False
    all_killed = True
    for name, path, original, mutant, targets in MUTATIONS:
        raw = path.read_bytes()
        source = raw.decode("utf-8")
        if original not in source:
            print(f"ERROR   {name}: el código original ya no existe; actualiza la mutación")
            all_killed = False
            continue
        path.write_bytes(source.replace(original, mutant, 1).encode("utf-8"))
        try:
            result = pytest_run(targets)
        finally:
            path.write_bytes(raw)  # restauración exacta (sin tocar fin de línea)
        killed = result.returncode != 0
        all_killed &= killed
        print(f"{'DETECTADA ' if killed else 'SOBREVIVE!'}  {name:46s} → {' '.join(targets)}")
    return all_killed


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(0 if run() else 1)


if __name__ == "__main__":
    main()
