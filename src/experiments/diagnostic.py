"""Public diagnostic baseline D and its opt-in agent (#58).

D reads only the stderr of the public reproduction (``test-0``), before any
decision or patch, and maps the terminal exception class of each failing test
to the operators whose public rule addresses that failure mode. It uses Python
and standard-library names only: no task identifiers, paths, test names,
application identifiers, private annotations or later test output. D never
removes an operator; the joint policy only reorders the three of them.

Specification: ``docs/preregistration/diagnostic-baseline.md``. The default
``BoundedRepairAgent`` and its behaviour are unchanged.
"""

import builtins
import re
from dataclasses import dataclass

from .agent import RULES, STRATEGIES, AgentView, BoundedRepairAgent
from .evidence import digest, normalize_source

POLICY = "diagnostic-baseline/v1"
RULES_ID = "diagnostic-rules/v1"
AGENT_NAME = BoundedRepairAgent.name + "+diagnostic-v1"
STORAGE_MODULES = ("sqlite3",)
FAILURE_MODES = {
    "storage_unavailable": ("initialize_storage",),
    "missing_value": ("validate_optional_identity", "normalize_environment"),
    "contract_violated": STRATEGIES,
    "other": STRATEGIES,
}
RULES_SHA256 = digest({"id": RULES_ID, "modes": FAILURE_MODES, "storage_modules": STORAGE_MODULES})
# Exact declaration written by the runner in every receipt of this agent. The order
# itself is enforced by the runner code (and tested by call order); the evaluator
# requires this exact value and a failing test-0.
DECISION_INPUTS = {"order": ["RETRIEVE", "test-0", "plan"], "reproduction": "test-0"}

_SEPARATOR = re.compile(r"^={20,}$", re.MULTILINE)
_HEADER = re.compile(r"^(ERROR|FAIL): ")
_FRAME = re.compile(r'^\s+File ".*", line \d+, in .+$')
_DASHES = re.compile(r"^-{20,}$")
_QUALIFIED = re.compile(r"^[A-Za-z_][\w.]*$")
_NONE = re.compile(r"\bNoneType\b")


def failure_features(stderr):
    """Canonical, deduplicated features of each unittest failure block."""
    text = normalize_source(stderr or "")
    features = set()
    for chunk in _SEPARATOR.split(text):
        lines = chunk.lstrip("\n").split("\n")
        header = _HEADER.match(lines[0])
        if header is None:
            continue
        body = lines[1:]
        for i in range(1, len(body)):
            if body[i].startswith("Ran ") and _DASHES.match(body[i - 1]):
                body = body[: i - 1]
                break
        frames = [i for i, line in enumerate(body) if _FRAME.match(line)]
        terminal = None
        if frames:
            terminal = next(
                (line for line in body[frames[-1] + 1 :] if line.strip() and not line[0].isspace()),
                None,
            )
        name = terminal.split(":", 1)[0].strip() if terminal else None
        exception = name if name and _QUALIFIED.match(name) else None
        none_marker = bool(terminal and _NONE.search(terminal))
        features.add((header.group(1), exception, none_marker))
    return [
        {"outcome": outcome, "exception": exception, "none_marker": marker}
        for outcome, exception, marker in sorted(features, key=lambda f: (f[0], f[1] or "", f[2]))
    ]


def failure_mode(feature):
    """Failure mode of one block, from Python and standard-library names only."""
    name = feature["exception"]
    if name is None:
        return "other"
    module, _, class_name = name.rpartition(".")
    if module.split(".")[0] in STORAGE_MODULES:
        return "storage_unavailable"
    cls = getattr(builtins, class_name, None) if not module else None
    if not (isinstance(cls, type) and issubclass(cls, BaseException)):
        return "other"
    if issubclass(cls, ConnectionError):
        return "storage_unavailable"
    if issubclass(cls, (TypeError, AttributeError)) and feature["none_marker"]:
        return "missing_value"
    if issubclass(cls, AssertionError):
        return "contract_violated"
    return "other"


def diagnose(stderr):
    """D: candidate operators and status from the reproduction stderr alone."""
    features = failure_features(stderr)
    modes = [failure_mode(f) for f in features]
    allowed = set(STRATEGIES)
    for mode in modes:
        allowed &= set(FAILURE_MODES[mode])
    reason = None
    if not features:
        reason = "no_failure_block"
    elif not allowed:
        reason = "conflict"
    elif len(allowed) == len(STRATEGIES):
        reason = "no_discrimination"
    if reason is not None:
        status, allowed = "ambiguous", set(STRATEGIES)
    else:
        status = "decisive" if len(allowed) == 1 else "partial"
    return {
        "rules": RULES_ID,
        "rules_sha256": RULES_SHA256,
        "features": features,
        "modes": modes,
        "candidates": [s for s in STRATEGIES if s in allowed],
        "status": status,
        "reason": reason,
    }


def joint_plan(prior, candidates, proposal):
    """Diagnosis narrows, memory orders within it, the seeded prior breaks ties.

    With all three candidates this is exactly the default plan of the condition.
    """
    prior = list(prior)
    plan = sorted(STRATEGIES, key=lambda op: (op not in candidates, op != proposal, prior.index(op)))
    without_memory = sorted(STRATEGIES, key=lambda op: (op not in candidates, prior.index(op)))
    return plan, without_memory


def memory_effect(diagnosis, proposal, without_memory):
    if proposal is None:
        return "no_proposal"
    if diagnosis["status"] != "ambiguous" and proposal not in diagnosis["candidates"]:
        return "vetoed"
    return "confirmed" if proposal == without_memory[0] else "changed_first"


@dataclass(frozen=True)
class DiagnosticView(AgentView):
    """AgentView plus the public reproduction: {"returncode", "stderr"} of test-0."""

    reproduction: dict | None = None


class DiagnosticRepairAgent(BoundedRepairAgent):
    """Same operators and patches; the plan also uses the public diagnosis D."""

    name = AGENT_NAME
    reads_reproduction = True

    def plan(self, view):
        base = super().plan(view)  # memory ranking and citation exactly as in the default agent
        proposal = base["plan"][0] if base["memory_ids"] else None
        reproduction = getattr(view, "reproduction", None) or {}
        diagnosis = diagnose(reproduction.get("stderr"))
        plan, without_memory = joint_plan(base["considered"], diagnosis["candidates"], proposal)
        return {
            **base,
            "selected": plan[0],
            "plan": plan,
            "without_memory": without_memory[0],
            "influenced_by_memory": plan != without_memory,
            "initial_hypothesis": RULES[plan[0]],
            "policy": POLICY,
            "diagnostic": diagnosis,
            "plan_without_memory": without_memory,
            "memory_proposal": proposal,
            "memory_effect": memory_effect(diagnosis, proposal, without_memory),
        }


def replay_decision(record):
    """Recompute a diagnostic decision from what its receipt recorded (evaluator side)."""
    view = DiagnosticView(
        record["task"],
        dict(record["initial_source"]),
        tuple(record["retrieval"]["memories"]),
        record["memory_mode"],
        record["seed"],
        reproduction={"returncode": record["tests"][0]["returncode"], "stderr": record["tests"][0]["stderr"]},
    )
    return DiagnosticRepairAgent().plan(view)
