"""El análisis pre-registrado de H4 debe poder llegar a cada conclusión (#46)."""

from scripts.analyze_h4 import analyze

PRIVATE = {
    "EXP-01": {"family": "authentication"},
    "EXP-02": {"family": "configuration"},
    "EXP-07": {"family": "authentication", "decoy_family": "configuration"},
}


def run(mode, task, seed, *, first, split="transfer", memories=(), batch="B1", selected="s"):
    return {
        "kind": "task_run",
        "memory_mode": mode,
        "task": {"id": task},
        "seed": seed,
        "split": split,
        "batch_id": batch,
        "decision": {"selected": selected, "plan": [selected]},
        "outcome": {"first_attempt_success": first, "iterations": 1 if first else 2, "success": True},
        "retrieval": {"memories": [{"task": t} for t in memories]},
    }


def campaign(b_first, c_first, seeds=range(6), b_train_first=True, c_train_first=True):
    runs = []
    for s in seeds:
        runs.append(run("NO_MEMORY", "EXP-07", s, first=False))
        runs.append(run("TEXT_HISTORY", "EXP-07", s, first=b_first(s), memories=["EXP-02"]))
        runs.append(run("ASSOCIATIVE_MEMORY", "EXP-07", s, first=c_first(s), memories=["EXP-01"]))
        runs.append(run("NO_MEMORY", "EXP-02", s, first=True, split="train"))
        runs.append(run("TEXT_HISTORY", "EXP-02", s, first=b_train_first, split="train", memories=["EXP-01"]))
        runs.append(
            run("ASSOCIATIVE_MEMORY", "EXP-02", s, first=c_train_first, split="train", memories=["EXP-01"])
        )
    return runs


def test_h4a_supported_when_c_beats_b_by_the_registered_margin():
    r = analyze(campaign(lambda s: False, lambda s: s < 3), PRIVATE)
    assert r["decision"]["H4a"] == "apoyada"
    assert r["decision"]["H4a_difference_runs_C_minus_B"] == 3


def test_h4a_no_difference_below_margin_and_refuted_when_c_is_worse():
    assert analyze(campaign(lambda s: False, lambda s: s < 2), PRIVATE)["decision"]["H4a"] == "sin diferencia"
    assert analyze(campaign(lambda s: s < 1, lambda s: False), PRIVATE)["decision"]["H4a"] == "refutada"


def test_misleading_retrieval_rate_counts_decoy_family_lessons():
    r = analyze(campaign(lambda s: False, lambda s: False), PRIVATE)
    assert r["conditions"]["TEXT_HISTORY"]["MisleadingRetrievalRate"]["value"] == 1.0  # EXP-02 = señuelo
    assert r["conditions"]["ASSOCIATIVE_MEMORY"]["MisleadingRetrievalRate"]["value"] == 0.0  # EXP-01 = real
    assert r["conditions"]["NO_MEMORY"]["MisleadingRetrievalRate"]["value"] is None  # denominador 0 → null


def test_negative_transfer_is_paired_against_no_memory():
    r = analyze(campaign(lambda s: False, lambda s: False, b_train_first=False), PRIVATE)
    assert r["conditions"]["TEXT_HISTORY"]["NegativeTransferRate_train"]["numerator"] == 6
    assert r["conditions"]["ASSOCIATIVE_MEMORY"]["NegativeTransferRate_train"]["numerator"] == 0
    assert r["decision"]["H4b"] == "apoyada"


def test_inconsistent_replicates_are_flagged():
    runs = campaign(lambda s: False, lambda s: False)
    runs.append(
        run("TEXT_HISTORY", "EXP-07", 0, first=True, memories=["EXP-02"], batch="B2", selected="otra")
    )
    assert analyze(runs, PRIVATE)["replicates_consistent"] is False
    assert analyze(campaign(lambda s: False, lambda s: False), PRIVATE)["replicates_consistent"] is True
