"""Verificación por mutación de las propiedades (``tests/unit/test_properties.py``).

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
PROPERTIES = "tests/unit/test_properties.py"

# (nombre, archivo, original, mutación, propiedad que debe detectarla)
MUTATIONS = [
    (
        "sin saturación en 1.0",
        MEMORY / "associative.py",
        "activation[n] = min(1.0, activation.get(n, 0.0) + a)",
        "activation[n] = activation.get(n, 0.0) + a",
        "test_activation_is_bounded_and_respects_threshold",
    ),
    (
        "ranking no estable",
        MEMORY / "associative.py",
        "ranked = sorted(scored, key=lambda s: -s.score)",
        "ranked = sorted(scored, key=lambda s: s.action)",
        "test_empty_memory_preserves_candidate_order",
    ),
    (
        "decaimiento invertido",
        MEMORY / "graph.py",
        "math.exp(-edge.decay_factor * max(age, 0))",
        "math.exp(edge.decay_factor * max(age, 0))",
        "test_effective_weight_never_increases_with_time",
    ),
    (
        "valencia contextual sin normalizar",
        MEMORY / "associative.py",
        "return conf * (signed / mass) + (1 - conf) * global_val",
        "return signed + global_val",
        "test_contextual_valence_is_bounded",
    ),
    (
        "se pierde embedding_model al cargar",
        MEMORY / "graph.py",
        "mg.embedding_model = doc.embedding_model",
        "mg.embedding_model = None",
        "test_serialization_roundtrip_for_any_history",
    ),
]


def run() -> bool:
    all_killed = True
    for name, path, original, mutant, test in MUTATIONS:
        raw = path.read_bytes()
        source = raw.decode("utf-8")
        if original not in source:
            print(f"ERROR   {name}: el código original ya no existe; actualiza la mutación")
            all_killed = False
            continue
        path.write_bytes(source.replace(original, mutant, 1).encode("utf-8"))
        try:
            pytest = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-x"]
            result = subprocess.run(
                [*pytest, PROPERTIES, "-k", test],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
        finally:
            path.write_bytes(raw)  # restauración exacta (sin tocar fin de línea)
        killed = result.returncode != 0
        all_killed &= killed
        print(f"{'DETECTADA ' if killed else 'SOBREVIVE!'}  {name:38s} → {test}")
    return all_killed


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(0 if run() else 1)


if __name__ == "__main__":
    main()
