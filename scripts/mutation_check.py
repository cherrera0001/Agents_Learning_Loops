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
CONTROLS = ([PROPERTIES], EXPERIMENT_TESTS, DIAGNOSTIC_TESTS, DIAGNOSTIC_HARNESS, DIAGNOSTIC_ANALYSIS)

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
        "D: evaluador no exige la reproducción previa",
        EXPERIMENTS / "evaluate.py",
        'if r["tests"][0]["id"] != "test-0" or "decision_inputs" not in r:',
        "if False:",
        DIAGNOSTIC_HARNESS,
    ),
    (
        "D: análisis con margen estricto",
        ROOT / "scripts" / "analyze_diagnostic_baseline.py",
        "if difference >= MARGIN:",
        "if difference > MARGIN:",
        DIAGNOSTIC_ANALYSIS,
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
