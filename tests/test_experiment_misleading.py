"""Misleading transfer tasks without lexical cues (#45).

These tests pin the *design* of EXP-07..09: each defect reproduces, the healthy
application passes, the operator of the true family repairs it, and the public
text is lexically closer to a decoy training issue than to the correct one
under the very similarity the memory conditions use. They do not require any
memory condition to win or lose.
"""

import json

import pytest

from associative_agent_loop.memory.text import cosine_similarity, tokenize
from experiments.agent import RULES, AgentView, BoundedRepairAgent
from experiments.benchmark import TASK_SETS, private_metadata, task_breakdown
from experiments.evaluate import evaluate
from experiments.evidence import read_receipt
from experiments.memory import EvidenceMemory
from experiments.models import PublicTask
from experiments.runner import (
    ROOT,
    app_files,
    execute_tests,
    load_task,
    prepare,
    run_experiment,
    update_memory,
)

MISLEADING = ("EXP-07", "EXP-08", "EXP-09")
TRAINING = ("EXP-01", "EXP-02", "EXP-03")
STRATEGY = {
    "authentication": "validate_optional_identity",
    "configuration": "normalize_environment",
    "readiness": "initialize_storage",
}
# Vocabulary that names a family's mechanism even when it is absent from the
# training issues. The public text of a misleading task must avoid the terms
# of its *true* family (in addition to that family's training-only tokens).
SEMANTIC = {
    "authentication": {
        "401",
        "403",
        "auth",
        "authentication",
        "authenticate",
        "authorization",
        "authorize",
        "credential",
        "credentials",
        "identity",
        "identities",
        "login",
        "optional",
        "permission",
        "principal",
        "profile",
        "token",
        "tokens",
        "unauthorized",
        "user",
        "users",
        "valid",
        "validate",
    },
    "configuration": {
        "attributeerror",
        "config",
        "configuration",
        "configured",
        "default",
        "defaults",
        "empty",
        "env",
        "environ",
        "environment",
        "getenv",
        "ledger_report_label",
        "ledger_title",
        "missing",
        "normalize",
        "title",
        "unset",
        "variable",
    },
    "readiness": {
        "background",
        "connection",
        "connectionerror",
        "database",
        "db",
        "initialise",
        "initialize",
        "initialized",
        "ready",
        "readiness",
        "refused",
        "schema",
        "sqlite",
        "start",
        "startup",
        "storage",
        "table",
        "worker",
    },
}
# memory.EvidenceMemory.retrieve seeds Symptom/Component/Lesson nodes at >= 0.12.
SEED_THRESHOLD = 0.12

METADATA = private_metadata(ROOT)


def public(task_id):
    return json.loads((ROOT / "benchmark/public" / f"{task_id}.json").read_text("utf-8"))


def lesson_texts(train_id):
    """The texts a lesson learned on ``train_id`` exposes to lexical retrieval."""
    task = PublicTask.model_validate(public(train_id))
    strategy = STRATEGY[METADATA[train_id]["family"]]
    symptom = task.title + " " + task.context  # EvidenceMemory.consolidate
    return {
        "history": symptom + " " + RULES[strategy],  # BoundedRepairAgent.plan (TEXT_HISTORY)
        "Symptom": symptom,
        "Component": METADATA[train_id]["mutation"]["path"],  # file changed by the verified patch
        "Lesson": RULES[strategy],
    }


def training_of(family):
    return next(t for t in TRAINING if METADATA[t]["family"] == family)


def test_task_set_and_private_annotations():
    assert TASK_SETS["v1"] == tuple(f"EXP-{i:02d}" for i in range(1, 7))
    assert TASK_SETS["misleading-v1"] == (*TASK_SETS["v1"], *MISLEADING)
    pairs = json.loads((ROOT / "benchmark/private/pairs.json").read_text("utf-8"))
    families = {METADATA[t]["family"] for t in MISLEADING}
    decoys = {METADATA[t]["decoy_family"] for t in MISLEADING}
    assert families == decoys == set(STRATEGY)  # one task per true family; each family is a decoy once
    for task_id in MISLEADING:
        meta = METADATA[task_id]
        assert meta["split"] == "transfer"
        assert meta["decoy_family"] != meta["family"]
        assert meta["relevant_training_tasks"] == [training_of(meta["family"])]
        assert meta["decoy_training_tasks"] == [training_of(meta["decoy_family"])]
        assert meta["hidden_cause_id"] == METADATA[training_of(meta["family"])]["hidden_cause_id"]
        assert {"train": meta["decoy_training_tasks"][0], "transfer": task_id} in [
            {k: p[k] for k in ("train", "transfer")} for p in pairs["negative"]
        ]
        assert {"train": meta["relevant_training_tasks"][0], "transfer": task_id} in [
            {k: p[k] for k in ("train", "transfer")} for p in pairs["positive"]
        ]


@pytest.mark.parametrize("task_id", MISLEADING)
def test_public_text_has_no_lexical_cue_for_true_family(task_id):
    meta = METADATA[task_id]
    true_train, decoy_train = meta["relevant_training_tasks"][0], meta["decoy_training_tasks"][0]
    task = public(task_id)
    text_fields = ("title", "context", "expected", "observed", "acceptance_criteria")
    tokens = set(tokenize(" ".join(task[k] for k in text_fields)))
    # Tokens that only the true family's training lesson carries.
    own = set(tokenize(" ".join(lesson_texts(true_train)[k] for k in ("history", "Component"))))
    others = set()
    for t in TRAINING:
        if t != true_train:
            others |= set(tokenize(" ".join(lesson_texts(t)[k] for k in ("history", "Component"))))
    characteristic = (own - others) | SEMANTIC[meta["family"]]
    assert tokens & characteristic == set()

    # TEXT_HISTORY: the agent ranks lessons by cosine(query, symptom + rule).
    query = PublicTask.model_validate(task).query()
    history = {t: cosine_similarity(query, lesson_texts(t)["history"]) for t in TRAINING}
    assert max(history, key=history.__getitem__) == decoy_train
    assert history[decoy_train] > 2 * history[true_train]

    # ASSOCIATIVE_MEMORY: lexical seeds may only come from the decoy lesson.
    seeded = {
        t
        for t in TRAINING
        for kind in ("Symptom", "Component", "Lesson")
        if cosine_similarity(query, lesson_texts(t)[kind]) >= SEED_THRESHOLD
    }
    assert seeded == {decoy_train}


@pytest.mark.parametrize("task_id", MISLEADING)
def test_in_repository_issue_matches_public_task(task_id):
    body = (ROOT / "benchmark/issue-proposals" / f"{task_id}.md").read_text("utf-8")
    task = public(task_id)
    for field in ("context", "expected", "observed", "acceptance_criteria", "reproduction"):
        assert task[field] in body
    assert "#45" in body and "hidden_cause_id:" not in body


def test_original_misleading_pair_had_a_lexical_cue():
    """Documents #45: EXP-05's text is lexically closest to its *correct* lesson."""
    query = load_task("EXP-05").query()
    history = {t: cosine_similarity(query, lesson_texts(t)["history"]) for t in TRAINING}
    assert max(history, key=history.__getitem__) == "EXP-02"


@pytest.mark.parametrize("task_id", MISLEADING)
def test_defect_reproduces_and_healthy_app_passes(task_id, tmp_path):
    task = load_task(task_id)
    prepare(task, tmp_path)
    assert execute_tests(tmp_path, 0)["returncode"] != 0
    relative = METADATA[task_id]["mutation"]["path"]
    (tmp_path / relative).write_bytes((ROOT / "experiments/software_project" / relative).read_bytes())
    healthy = execute_tests(tmp_path, 1)
    assert healthy["returncode"] == 0
    assert "test_create_and_list" in healthy["stderr"]  # business regression test ran too


@pytest.mark.parametrize("task_id", MISLEADING)
def test_only_the_true_family_operator_repairs(task_id, tmp_path):
    meta = METADATA[task_id]
    prepare(load_task(task_id), tmp_path)
    initial = app_files(tmp_path)
    agent = BoundedRepairAgent()
    outcomes = {}
    for strategy in RULES:
        for name, content in initial.items():
            (tmp_path / name).write_text(content, encoding="utf-8")
        path, replacement, _ = agent.change(dict(initial), strategy, 7)
        if path is not None:
            (tmp_path / path).write_text(replacement, encoding="utf-8")
        outcomes[strategy] = (path, execute_tests(tmp_path, 1)["returncode"] == 0)
    true_strategy = STRATEGY[meta["family"]]
    assert outcomes[true_strategy] == (meta["mutation"]["path"], True)
    assert not any(ok for s, (_, ok) in outcomes.items() if s != true_strategy)
    assert not outcomes[STRATEGY[meta["decoy_family"]]][1]


@pytest.mark.parametrize("task_id", MISLEADING)
def test_agent_boundary_excludes_private_data(task_id, tmp_path):
    task = load_task(task_id)
    prepare(task, tmp_path)
    names = [p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file()]
    assert all(n.startswith(("app/", "tests/")) for n in names)
    assert len([n for n in names if n.startswith("tests/")]) == 2
    view = AgentView(task.model_dump(), app_files(tmp_path), (), "NO_MEMORY", 7)
    serialized = json.dumps(view.__dict__)
    meta = METADATA[task_id]
    for forbidden in (
        "hidden_cause_id",
        "relevant_training_tasks",
        "decoy_family",
        "decoy_training_tasks",
        "decoy_reason",
        "golden_patch",
        "AUTH-01",
        "CONFIG-01",
        "READY-01",
        *(t for t in TASK_SETS["misleading-v1"] if t != task_id),
    ):
        assert forbidden not in serialized
    assert meta["mutation"]["before"] not in json.dumps(view.files)


@pytest.fixture(scope="module")
def pilot(tmp_path_factory):
    """Real training (ASSOCIATIVE_MEMORY) plus paired misleading transfer runs."""
    evidence = tmp_path_factory.mktemp("misleading-evidence")
    memory = EvidenceMemory()
    for task_id in TRAINING:
        path = run_experiment(
            task_id, memory_mode="ASSOCIATIVE_MEMORY", seed=7, memory=memory, evidence_dir=evidence
        )
        update_memory(memory, path, evidence)
    receipts = {}
    for task_id in MISLEADING:
        for mode in ("NO_MEMORY", "ASSOCIATIVE_MEMORY"):
            path = run_experiment(task_id, memory_mode=mode, seed=7, memory=memory, evidence_dir=evidence)
            receipts[task_id, mode] = read_receipt(path)
    return evidence, memory, receipts


@pytest.mark.parametrize("task_id", MISLEADING)
def test_both_memory_conditions_rank_the_decoy_lesson_first(pilot, task_id):
    _, memory, receipts = pilot
    decoy = METADATA[task_id]["decoy_training_tasks"][0]
    task = load_task(task_id)
    ranked, paths = memory.retrieve(task.query(), "ASSOCIATIVE_MEMORY")
    assert [m["task"] for m in ranked] == [decoy]
    assert paths and paths[0]["memory"] == ranked[0]["id"]
    history, _ = memory.retrieve(task.query(), "TEXT_HISTORY")
    decision = BoundedRepairAgent().plan(AgentView(task.model_dump(), {}, tuple(history), "TEXT_HISTORY", 7))
    cited = {m["id"]: m["task"] for m in history}
    assert [cited[m] for m in decision["memory_ids"]] == [decoy]
    receipt = receipts[task_id, "ASSOCIATIVE_MEMORY"]
    assert receipt["result"] == "PASS"  # three operators, budget three: still repaired
    assert receipt["decision"]["selected"] == STRATEGY[METADATA[task_id]["decoy_family"]]


def test_breakdown_reports_misleading_retrieval_with_denominators(pilot, tmp_path):
    evidence, _, receipts = pilot
    evaluate(evidence, tmp_path)
    breakdown = json.loads((tmp_path / "task_breakdown.json").read_text("utf-8"))
    assert breakdown["misleading_tasks"] == list(MISLEADING)
    assert (tmp_path / "task_breakdown.md").exists()
    row = breakdown["MisleadingRetrievalRate"]["ASSOCIATIVE_MEMORY"]
    assert row["counts"]["cited"] == 3 == row["counts"]["decoy_cited"]
    assert row["MisleadingRetrievalRate"] == 1.0
    assert row["CorrectFamilyRetrievalRate"] == 0.0
    none = breakdown["MisleadingRetrievalRate"]["NO_MEMORY"]
    assert none["counts"]["cited"] == 0 and none["MisleadingRetrievalRate"] is None
    for task_id in MISLEADING:
        cell = breakdown["tasks"][task_id]["ASSOCIATIVE_MEMORY"]
        expected = receipts[task_id, "ASSOCIATIVE_MEMORY"]["iterations"]
        assert cell["IterationsPerTask"] == expected
        assert cell["IterationDeltaVsNoMemory"] == expected - receipts[task_id, "NO_MEMORY"]["iterations"]
        assert breakdown["tasks"][task_id]["NO_MEMORY"]["IterationDeltaVsNoMemory"] is None


def test_changed_misleading_annotation_is_rejected_only_where_used(pilot, tmp_path):
    """Control: changing EXP-07's causal label must invalidate evidence that ran
    EXP-07, while the published v1 campaign (which never used the file) stays valid."""
    import shutil

    evidence, _, _ = pilot
    root = tmp_path / "root"
    for folder in ("src", "benchmark", "experiments/software_project"):
        shutil.copytree(ROOT / folder, root / folder, ignore=shutil.ignore_patterns("__pycache__"))
    evaluate(evidence, root=root)  # unchanged copy: accepted
    path = root / "benchmark/private/tasks_misleading.json"
    annotations = json.loads(path.read_text("utf-8"))
    annotations["EXP-07"]["hidden_cause_id"] = "READY-01"
    path.write_text(json.dumps(annotations, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="private annotations differ"):
        evaluate(evidence, root=root)
    published = json.loads((ROOT / "results/experiment1.json").read_text("utf-8"))
    assert evaluate(ROOT / "evidence/runs", root=root) == published


def test_task_breakdown_is_null_without_misleading_tasks():
    assert task_breakdown([], METADATA)["MisleadingRetrievalRate"] == {}


def test_published_campaign_evaluation_is_unchanged():
    published = json.loads((ROOT / "results/experiment1.json").read_text("utf-8"))
    assert evaluate(ROOT / "evidence/runs") == published
