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
CONTROLS = (
    [PROPERTIES],
    EXPERIMENT_TESTS,
    DIAGNOSTIC_TESTS,
    DIAGNOSTIC_HARNESS,
    DIAGNOSTIC_ANALYSIS,
    FAILURE_TESTS,
    FAILURE_HARNESS,
    FAILURE_ANALYSIS,
)
FAILURE_SCRIPT = ROOT / "scripts" / "analyze_failure_memory.py"

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
        "applies = same and similarity >= TAU",
        "applies = similarity >= TAU",
        FAILURE_TESTS,
    ),
    (
        "H6: umbral de similitud estricto",
        EXPERIMENTS / "failure_memory.py",
        "applies = same and similarity >= TAU",
        "applies = same and similarity > TAU",
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
        "if agent != FAILURE_AGENT and ("
        "FAILURE_FIELDS & decision.keys() or FAILURE_RECORD_FIELDS & record.keys()):",
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
