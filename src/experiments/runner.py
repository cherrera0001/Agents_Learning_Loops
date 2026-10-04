"""Controller: immutable evidence from real subprocess tests in fresh copies."""

import copy
import difflib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from importlib.metadata import version
from itertools import pairwise
from pathlib import Path

from .agent import RULES, AgentView, BoundedRepairAgent
from .benchmark import ALL_TASKS, private_metadata
from .diagnostic import DECISION_INPUTS, DiagnosticView
from .evidence import (
    RECEIPT_SCHEMA,
    SOURCE_HASH_NORMALIZATION,
    digest,
    normalize_source,
    publish,
    source_sha256,
    sources_digest,
)
from .failure_memory import CONDITIONS, PASSES, STORE, FailureView
from .failure_memory import DECISION_INPUTS as FAILURE_DECISION_INPUTS
from .failure_transfer import CONDITIONS as TRANSFER_CONDITIONS
from .failure_transfer import DECISION_INPUTS as TRANSFER_DECISION_INPUTS
from .failure_transfer import TransferView
from .memory import EvidenceMemory
from .models import MemoryMode, PublicTask, Reflection
from .nonlexical_seed import CONDITIONS as SEED_CONDITIONS
from .nonlexical_seed import DECISION_INPUTS as SEED_DECISION_INPUTS
from .nonlexical_seed import retrieval_inputs
from .nonlexical_seed import retrieve as seeded_retrieve

ROOT = Path(__file__).resolve().parents[2]
PHASES = (
    "ISSUE",
    "RETRIEVE",
    "INSPECT",
    "HYPOTHESIZE",
    "CHANGE",
    "TEST",
    "OBSERVE",
    "DIAGNOSE",
    "REFLECT",
    "CONSOLIDATE",
    "MEMORY_UPDATE",
)
TRANSITIONS = {a: {b} for a, b in pairwise(PHASES)}
TRANSITIONS["OBSERVE"].add("INSPECT")


def advance(record, phase):
    previous = record["phases"][-1]
    if phase not in TRANSITIONS.get(previous, set()):
        raise ValueError(f"illegal experiment transition: {previous} -> {phase}")
    record["phases"].append(phase)


def source_manifest(root=ROOT):
    paths = []
    for folder in ("src", "benchmark", "experiments/software_project"):
        paths.extend(
            p
            for p in (root / folder).rglob("*")
            if p.is_file()
            and "__pycache__" not in p.parts
            and not any(part.endswith(".egg-info") for part in p.parts)
        )
    # Hashes of normalized text (normalize_source): identical for CRLF and LF checkouts.
    return {p.relative_to(root).as_posix(): source_sha256(p.read_bytes()) for p in sorted(paths)}


def git_commit(root=ROOT):
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root).decode().strip()


def load_task(task, root=ROOT):
    if not isinstance(task, str) or task not in ALL_TASKS:
        raise ValueError("unknown benchmark task")
    return PublicTask.model_validate_json((root / "benchmark/public" / f"{task}.json").read_text("utf-8"))


def prepare(task: PublicTask, workspace: Path, root=ROOT):
    """Private controller state never enters the workspace or AgentView."""
    metadata = private_metadata(root)[task.id]
    project = root / "experiments/software_project"
    shutil.copytree(
        project / "app",
        workspace / "app",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    (workspace / "tests").mkdir()
    shutil.copyfile(project / "tests/test_business.py", workspace / "tests/test_business.py")
    shutil.copyfile(root / "benchmark/public" / task.test_file, workspace / "tests/test_contract.py")
    mutation = metadata["mutation"]
    target = workspace / mutation["path"]
    source = target.read_text("utf-8")
    if source.count(mutation["before"]) != 1:
        raise ValueError("defect precondition no longer matches the application")
    target.write_text(source.replace(mutation["before"], mutation["after"]), encoding="utf-8", newline="\n")
    return metadata["split"]


def app_files(workspace):
    """Normalized application text: what the agent sees, what is hashed and recorded."""
    return {
        p.relative_to(workspace).as_posix(): normalize_source(p.read_bytes())
        for p in sorted((workspace / "app").rglob("*.py"))
    }


def protected_files(workspace):
    """Raw bytes of the protected tests, used to detect tampering during a run."""
    return {p.name: p.read_bytes() for p in sorted((workspace / "tests").glob("*.py"))}


def execute_tests(workspace, index, timeout=20):
    # -I removes ambient Python paths/site customizations; explicitly add only
    # this workspace. Acceptance tests and business tests are controlled inputs.
    code = (
        "import sys,os,unittest; sys.path.insert(0,os.getcwd()); "
        "r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover('tests')); "
        "sys.exit(0 if r.wasSuccessful() and r.testsRun >= 2 else 1)"
    )
    command = [sys.executable, "-I", "-B", "-c", code]
    environ = {k: v for k, v in os.environ.items() if k.upper() in {"SYSTEMROOT", "WINDIR", "TEMP", "TMP"}}
    started = time.perf_counter()
    try:
        result = subprocess.run(
            command,
            cwd=workspace,
            env=environ,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        stdout, stderr = (
            result.stdout.decode("utf-8", "replace"),
            result.stderr.decode("utf-8", "replace"),
        )
        status = result.returncode
    except subprocess.TimeoutExpired as error:
        stdout = (error.stdout or b"").decode("utf-8", "replace")
        stderr = (error.stderr or b"").decode("utf-8", "replace") + "\nTEST TIMEOUT"
        status = 124
    return {
        "id": f"test-{index}",
        "command": command,
        "returncode": status,
        "stdout": stdout.replace(str(workspace), "<workspace>"),
        "stderr": stderr.replace(str(workspace), "<workspace>"),
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
    }


def reproduce(workspace, record):
    """test-0: the public reproduction on the untouched defective workspace."""
    result = execute_tests(workspace, 0)
    record["tests"].append(result)
    if result["returncode"] == 0:
        raise ValueError("invalid fixture: defect did not reproduce")
    return result


def run_experiment(
    task,
    agent=None,
    memory_mode=MemoryMode.NO_MEMORY,
    seed=7,
    *,
    memory=None,
    evidence_dir=None,
    batch_id="adhoc",
    root=ROOT,
    max_iterations=3,
    failures=None,
    condition=None,
    pass_number=None,
):
    mode = MemoryMode(memory_mode).value
    if not 1 <= max_iterations <= 3:
        raise ValueError("iteration budget must be 1..3")
    task = load_task(task, root)
    agent = agent or BoundedRepairAgent()
    # Memoria de fallos opt-in (#63): solo su agente declara condición y pasada, y solo A_N y C_N
    # reciben una memoria de fallos. Las demás recetas no pasan estos argumentos.
    reads_failures = getattr(agent, "reads_failures", False)
    # Siembra de la recuperación opt-in (H8, #98): su agente declara una de sus cuatro condiciones, sin
    # memoria de fallos ni pasada. La condición de las demás recetas sigue siendo la de la memoria de fallos.
    seeded = getattr(agent, "seeds_retrieval", False)
    if seeded and (
        condition not in SEED_CONDITIONS
        or SEED_CONDITIONS[condition][0] != mode
        or failures is not None
        or pass_number is not None
    ):
        raise ValueError("la siembra de la recuperación exige una de sus condiciones, con su modo de memoria")
    failure_condition = None if seeded else condition
    if reads_failures != (failure_condition is not None):
        raise ValueError("la memoria de fallos exige su agente y una condición declarada, y solo ellos")
    # Transferencia de fallos opt-in (#65): condiciones propias, con τ y placebo, y una sola pasada.
    transfer = getattr(agent, "failure_transfer", False)
    if (
        failure_condition is not None
        and not transfer
        and (
            condition not in CONDITIONS
            or CONDITIONS[condition] != (mode, failures is not None)
            or pass_number not in PASSES
        )
    ):
        raise ValueError("condición, modo de memoria, memoria de fallos y pasada no concuerdan")
    if transfer and (
        condition not in TRANSFER_CONDITIONS
        or TRANSFER_CONDITIONS[condition][:2] != (mode, failures is not None)
        or pass_number is not None
    ):
        raise ValueError("condición, modo de memoria, memoria de fallos y pasada no concuerdan")
    memory = memory or EvidenceMemory()
    evidence_dir = Path(evidence_dir or root / "evidence/runs")
    started = time.perf_counter()
    run = "RUN-" + uuid.uuid4().hex
    links_path = root / "benchmark/issues.json"
    links = json.loads(links_path.read_text("utf-8")) if links_path.exists() else {}
    record = {
        "schema_id": RECEIPT_SCHEMA,
        "source_hash_normalization": SOURCE_HASH_NORMALIZATION,
        "kind": "task_run",
        "run_id": run,
        "batch_id": batch_id,
        "experiment": "software-learning-v1",
        "issue": links.get(task.id),
        "task": task.model_dump(),
        "memory_mode": mode,
        "seed": seed,
        "agent": agent.name,
        "budget": max_iterations,
        "phases": ["ISSUE"],
        "tests": [],
        "actions": [],
        "memory_changes": [],
        "result": "ERROR",
        "iterations": 0,
        "memory_before_sha256": memory.fingerprint(),
        "memory_input": memory.snapshot() if mode != "NO_MEMORY" else None,
        "provenance": {
            "source_manifest": source_manifest(root),
            "git_commit": git_commit(root),
            "python": sys.version,
            "platform": platform.platform(),
            "dependencies": {name: version(name) for name in ("networkx", "pydantic")},
            "test_environment": "allowlisted OS variables only",
        },
    }
    if condition is not None:
        record["condition"] = condition
        if transfer:
            # H7 (#65): el alcance y el placebo declarados de la condición; una sola pasada, sin ``pass``.
            _, _, scope_tau, placebo = TRANSFER_CONDITIONS[condition]
            record["failure_scope_tau"] = scope_tau
            record["placebo"] = placebo
        elif not seeded:
            record["pass"] = pass_number
    try:
        with tempfile.TemporaryDirectory(prefix="aal-task-") as directory:
            workspace = Path(directory)
            record["split"] = prepare(task, workspace, root)
            initial = app_files(workspace)
            protected = protected_files(workspace)
            record["initial_source"] = initial
            # Every source/test hash goes through normalize_source (lf/v1).
            record["initial_source_sha256"] = sources_digest(initial)
            record["acceptance_sha256"] = sources_digest(protected)
            if seeded:
                # H8 (#98): la reproducción pública precede a la recuperación, en las cuatro condiciones.
                # Solo C_S la usa para sembrar. Debe dejar intacto lo que el solver verá después.
                seed_stderr = reproduce(workspace, record)["stderr"]
                if app_files(workspace) != initial or protected_files(workspace) != protected:
                    raise ValueError("la reproducción previa modificó el workspace observable")
            advance(record, "RETRIEVE")
            if seeded:
                memories, paths, seeding = seeded_retrieve(
                    memory, condition, task.query(), seed_stderr, tuple(initial)
                )
                record["retrieval"] = {"memories": memories, "paths": paths, "seeding": seeding}
                record["decision_inputs"] = copy.deepcopy(SEED_DECISION_INPUTS)
            else:
                memories, paths = memory.retrieve(task.query(), mode)
                record["retrieval"] = {"memories": memories, "paths": paths}
            record["retrieved_memories"] = [m["id"] for m in memories]
            if failure_condition is not None:
                failure_input = failures.snapshot()["records"] if failures is not None else []
                record["failure_memory_input"] = failure_input
            context = {
                "task": task.model_dump(),
                "files": {k: normalize_source(v) for k, v in initial.items()},
                "memories": memories,
            }
            if seeded:
                # El contexto hasheado cubre también lo que recibió la recuperación.
                context["retrieval"] = retrieval_inputs(
                    condition, task.query(), seed_stderr, tuple(initial), record["memory_before_sha256"]
                )
            if getattr(agent, "reads_reproduction", False):
                # Opt-in diagnostic baseline (#58): the public reproduction precedes
                # the decision; later test output never reaches the agent.
                reproduction = reproduce(workspace, record)
                public = {"returncode": reproduction["returncode"], "stderr": reproduction["stderr"]}
                view = DiagnosticView(task.model_dump(), dict(initial), tuple(memories), mode, seed, public)
                context["reproduction"] = public
                record["decision_inputs"] = copy.deepcopy(DECISION_INPUTS)
                if reads_failures:
                    # Memoria de fallos (#63): registros de ejecuciones selladas anteriores, nunca
                    # los tests de esta ejecución.
                    view = FailureView(
                        task.model_dump(),
                        dict(initial),
                        tuple(memories),
                        mode,
                        seed,
                        public,
                        failures=tuple(copy.deepcopy(failure_input)),
                    )
                    context["failures"] = failure_input
                    record["decision_inputs"] = copy.deepcopy(FAILURE_DECISION_INPUTS)
                    if transfer:
                        # H7 (#65): el agente recibe también el alcance y el placebo de su condición.
                        view = TransferView(**vars(view), scope_tau=scope_tau, placebo=placebo)
                        context["failure_policy"] = {"failure_scope_tau": scope_tau, "placebo": placebo}
                        record["decision_inputs"] = copy.deepcopy(TRANSFER_DECISION_INPUTS)
            else:
                view = AgentView(task.model_dump(), dict(initial), tuple(memories), mode, seed)
            record["agent_context_sha256"] = digest(context)
            decision = agent.plan(view)
            record["decision"] = decision
            record["initial_hypothesis"] = decision["initial_hypothesis"]
            if failure_condition is not None:
                # Lado del controlador, después de decidir: el origen de cada registro aplicado se
                # lee de su recibo sellado y nunca llega al agente.
                record["failure_origins"] = [
                    {"id": i, "origin": failures.origin(i, task.id)} for i in decision["failure_ids"]
                ]
            if not record["tests"]:
                reproduce(workspace, record)
            successful = None
            for index, strategy in enumerate(decision["plan"][:max_iterations], 1):
                advance(record, "INSPECT")
                path, replacement, inspected = agent.change(dict(initial), strategy, seed)
                advance(record, "HYPOTHESIZE")
                advance(record, "CHANGE")
                # Each strategy is an independent intervention on the same bug.
                for filename, content in initial.items():
                    (workspace / filename).write_text(content, encoding="utf-8", newline="\n")
                patch = ""
                if path is not None:
                    if path not in initial:
                        raise ValueError("agent may edit only allowlisted app files")
                    patch = "".join(
                        difflib.unified_diff(
                            initial[path].splitlines(True),
                            replacement.splitlines(True),
                            fromfile=path,
                            tofile=path,
                        )
                    )
                    (workspace / path).write_text(replacement, encoding="utf-8", newline="\n")
                record["actions"].append(
                    {
                        "iteration": index,
                        "strategy": strategy,
                        "inspected": inspected,
                        "hypothesis": RULES[strategy],
                        "inspection_sha256": {p: digest(normalize_source(initial[p])) for p in inspected},
                        "changed_files": [path] if path else [],
                        "patch": patch,
                        "memory_ids": decision["memory_ids"] if index == 1 else [],
                    }
                )
                if protected != protected_files(workspace):
                    raise ValueError("acceptance tests modified")
                advance(record, "TEST")
                result = execute_tests(workspace, index)
                record["tests"].append(result)
                record["iterations"] = index
                advance(record, "OBSERVE")
                if result["returncode"] == 0:
                    successful = strategy
                    break
            record["result"] = "PASS" if successful else "FAIL"
            record["outcome"] = {
                "success": bool(successful),
                "iterations": record["iterations"],
                "failed_attempts": sum(t["returncode"] != 0 for t in record["tests"][1:]),
                "first_attempt_success": bool(successful and record["iterations"] == 1),
            }
            advance(record, "DIAGNOSE")
            advance(record, "REFLECT")
            reflection = Reflection(
                goal=task.title,
                expected=task.expected,
                observed="Acceptance and business tests passed"
                if successful
                else "Budget exhausted with failing tests",
                root_cause=("Candidate mechanism supported by repair: " + RULES[successful])
                if successful
                else None,
                evidence=[t["id"] for t in record["tests"]],
                failed_strategy=[
                    a["strategy"]
                    for a, t in zip(record["actions"], record["tests"][1:], strict=True)
                    if t["returncode"] != 0
                ],
                successful_strategy=successful,
                generalizable_rule=RULES.get(successful),
                confidence=0.6 if successful else 0.0,
                memory_action="ADD"
                if successful and record["split"] == "train" and mode != "NO_MEMORY"
                else "IGNORE",
            )
            record["reflection"] = reflection.model_dump()
            advance(record, "CONSOLIDATE")
            record["consolidation"] = (
                "pending separate memory_update receipt" if reflection.memory_action == "ADD" else "IGNORE"
            )
    except Exception as error:
        record["error"] = {"type": type(error).__name__, "message": str(error)}
        record["result"] = "ERROR"
    record["duration_ms"] = round((time.perf_counter() - started) * 1000, 3)
    record["memory_after_sha256"] = memory.fingerprint()
    path = publish(evidence_dir, record)
    return path


def update_memory(memory, receipt_path, evidence_dir):
    before = memory.snapshot()
    # Transactional: validate and compute on a copy, seal the memory-update
    # receipt, then swap. A failed publication cannot change the caller's memory.
    candidate = EvidenceMemory(before)
    changes = candidate.consolidate(receipt_path)
    record = {
        "run_id": "RUN-" + uuid.uuid4().hex,
        "kind": "memory_update",
        "schema_id": RECEIPT_SCHEMA,
        "source_hash_normalization": SOURCE_HASH_NORMALIZATION,
        "source_receipt": receipt_path.name,
        "phases": ["MEMORY_UPDATE"],
        "memory_before": before,
        "memory_after": candidate.snapshot(),
        "memory_changes": changes,
    }
    path = publish(Path(evidence_dir), record)
    memory.document = candidate.document
    return path


def update_failure_memory(failures, receipt_path, evidence_dir):
    """Memoria de fallos (#63): un ``memory_update`` sellado y separado por ejecución con intentos fallidos.

    Transaccional como ``update_memory``: los registros se derivan del ``task_run`` sellado sobre una
    copia, se publica el recibo y solo entonces se reemplaza la memoria. Una ejecución sin intentos
    fallidos no escribe nada y devuelve None.
    """
    candidate = failures.copy()
    changes = candidate.consolidate(receipt_path)
    if not changes:
        return None
    record = {
        "run_id": "RUN-" + uuid.uuid4().hex,
        "kind": "memory_update",
        "schema_id": RECEIPT_SCHEMA,
        "source_hash_normalization": SOURCE_HASH_NORMALIZATION,
        "memory_store": STORE,
        "source_receipt": receipt_path.name,
        "phases": ["MEMORY_UPDATE"],
        "memory_before": failures.snapshot(),
        "memory_after": candidate.snapshot(),
        "memory_changes": changes,
    }
    path = publish(Path(evidence_dir), record)
    failures.records, failures.origins, failures.cell = candidate.records, candidate.origins, candidate.cell
    return path
