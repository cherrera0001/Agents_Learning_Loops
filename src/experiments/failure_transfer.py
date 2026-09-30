"""Transferencia y contaminación de la memoria de fallos (H7, #65) sobre la memoria de fallos de H6.

Especificación: ``docs/preregistration/failure-transfer.md`` (secciones 2 a 5). Mismo agente de
diagnóstico de #58, mismo registro de fallo, misma firma, misma clave ``title + " " + context`` y misma
política de H6 (#63)::

    plan = sorted(STRATEGIES, key=λop: (op ∉ S, op ∈ F, op ≠ p, prior.index(op)))

Cambian dos cosas, declaradas por condición y registradas en cada recibo:

- **alcance** τ ∈ {0.5, 0.25, 0.1, 0}: un registro aplica si su firma es idéntica a la de ``test-0`` y
  ``cosine_similarity(query, registro.query) ≥ τ``. Con τ = 0 basta la firma. τ = 0.5 es el alcance de H6;
- **placebo**: el mismo registro con el mismo alcance, salvo que al construir ``F`` su estrategia se rota
  ``STRATEGIES[i] → STRATEGIES[(i + 1) mod 3]``. El registro no cambia: solo lo que baja.

Con τ = 0.5 y sin placebo, la decisión es exactamente la de H6 (salvo ``policy`` y los campos aditivos).
El agente por defecto, el de #58 y el de H6 no cambian.
"""

from dataclasses import dataclass

from .agent import STRATEGIES
from .failure_memory import AGENT_NAME as FAILURE_AGENT_NAME
from .failure_memory import DECISION_INPUTS as FAILURE_DECISION_INPUTS
from .failure_memory import FailureMemory, FailureMemoryRepairAgent, FailureView

POLICY = "failure-transfer/v1"
AGENT_NAME = FAILURE_AGENT_NAME + "+failure-transfer-v1"
# Umbrales pre-registrados (sección 3), con el sufijo de su condición.
TAUS = {"50": 0.5, "25": 0.25, "10": 0.1, "00": 0.0}
BASES = {"A": "NO_MEMORY", "C": "ASSOCIATIVE_MEMORY"}
VARIANTS = {"R": False, "P": True}  # real, placebo


def _conditions():
    """Condición → (modo de lecciones, memoria de fallos activa, τ, placebo).

    Tabla de la sección 5, en su orden: por base, sin memoria de fallos, real τ = 0.5 / 0.25 / 0.1 / 0 y
    placebo τ = 0.5 / 0.25 / 0.1 / 0.
    """
    table = {}
    for base, mode in BASES.items():
        table[base] = (mode, False, None, False)
        for variant, placebo in VARIANTS.items():
            for suffix, tau in TAUS.items():
                table[f"{base}_{variant}{suffix}"] = (mode, True, tau, placebo)
    return table


CONDITIONS = _conditions()
# Declaración exacta que escribe el runner en cada recibo de este agente: la de H6 y, además, el alcance y
# el placebo declarados de la condición, que también recibe el agente.
DECISION_INPUTS = {
    **FAILURE_DECISION_INPUTS,
    "failure_scope_tau": "failure_scope_tau",
    "placebo": "placebo",
}
# Placebo (sección 4): rotación determinista sobre el orden de STRATEGIES en agent.py.
ROTATION = {s: STRATEGIES[(i + 1) % len(STRATEGIES)] for i, s in enumerate(STRATEGIES)}


def condition_of(condition):
    """(modo, memoria de fallos, τ, placebo) de una condición de H7; ``ValueError`` si no lo es."""
    if condition not in CONDITIONS:
        raise ValueError(f"condición de transferencia de fallos desconocida: {condition!r}")
    return CONDITIONS[condition]


def rotate(strategy):
    """La estrategia que baja un registro placebo: la siguiente en ``STRATEGIES``, circularmente."""
    return ROTATION[strategy]


def unchanged(strategy):
    return strategy


@dataclass(frozen=True)
class TransferView(FailureView):
    """FailureView más el alcance τ y el placebo de la condición (τ = None en A y C, sin registros)."""

    scope_tau: float | None = None
    placebo: bool = False


class FailureTransferRepairAgent(FailureMemoryRepairAgent):
    """El agente de H6 con el alcance τ y el placebo que declara su condición."""

    name = AGENT_NAME
    failure_transfer = True

    def plan(self, view):
        tau, placebo = getattr(view, "scope_tau", None), getattr(view, "placebo", False)
        failures = tuple(getattr(view, "failures", ()))
        if tau is None and (failures or placebo):
            raise ValueError("una condición sin alcance declarado no admite registros de fallo ni placebo")
        demote = rotate if placebo else unchanged
        decision = self.failure_decision(view, 0.0 if tau is None else tau, demote)
        applied = set(decision["failure_ids"])
        recorded = {r["strategy"] for r in failures if r["id"] in applied}
        return {
            **decision,
            "policy": POLICY,
            "failure_scope": [
                {**item, "demotes": demote(record["strategy"])}
                for item, record in zip(decision["failure_scope"], failures, strict=True)
            ],
            "failure_scope_tau": tau,
            "failure_placebo": placebo,
            "failure_recorded_strategies": [s for s in STRATEGIES if s in recorded],
        }


def replay_decision(record):
    """Recalcula la decisión desde lo que registró el recibo, τ y placebo incluidos (lado del evaluador)."""
    test0 = record["tests"][0]
    view = TransferView(
        record["task"],
        dict(record["initial_source"]),
        tuple(record["retrieval"]["memories"]),
        record["memory_mode"],
        record["seed"],
        reproduction={"returncode": test0["returncode"], "stderr": test0["stderr"]},
        failures=tuple(record["failure_memory_input"]),
        scope_tau=record["failure_scope_tau"],
        placebo=record["placebo"],
    )
    return FailureTransferRepairAgent().plan(view)


class TransferFailureMemory(FailureMemory):
    """Memoria de fallos de una (lote, semilla, condición) de H7: mismos registros que H6, otra fuente."""

    def check_source(self, receipt):
        if receipt.get("agent") != AGENT_NAME or not condition_of(receipt.get("condition"))[1]:
            raise ValueError(
                "la memoria de fallos de H7 solo se escribe desde recibos de sus variantes real y placebo"
            )
