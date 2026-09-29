# Controller / evaluator only

Task split, causal labels, mutation recipe, distance annotations and retrieval
ground truth live here. Nothing in this directory is copied to agent workspaces
or included in AgentView. Public GitHub Issues omit hidden_cause_id and family
metadata; those fields remain here to avoid disclosing the answer.

These labels are author annotations, not observed diagnoses. Evaluation uses
them only after receipts have been sealed. The six tasks include a negative
retrieval pair (AUTH training vs CONFIG transfer) without increasing task count.
L3/L4/L5 are intended distances, not independently validated classifications.

## Misleading tasks without lexical cues (#45)

`tasks_misleading.json` annotates EXP-07..09 (task set `misleading-v1`). They
are kept out of `tasks.json` on purpose: the published receipts pin the hash
of `tasks.json`, and the evaluator rejects any change to it. Besides the usual
fields each entry records:

- `decoy_family` / `decoy_training_tasks`: the family (and training issue) that
  the public title and context point to lexically. It is never the true family.
- `decoy_reason`: which shared vocabulary misleads, and what the code reveals.
- `lexical_cue_for_true_family: false`, enforced by
  `tests/test_experiment_misleading.py` with the retrieval similarity itself.

| Task | Public symptom | Decoy family (training issue) | True family | Defect | Operator |
|---|---|---|---|---|---|
| EXP-07 | some `/tasks` calls raise TypeError right after startup | readiness (EXP-03) | authentication | `authorize` guards `token is None` instead of `principal is None` | `validate_optional_identity` |
| EXP-08 | summary request returns a blank label | authentication (EXP-01) | configuration | report label falls back to `""` instead of `DEFAULT_LABEL` | `normalize_environment` |
| EXP-09 | summary fails to load in a clean environment | configuration (EXP-02) | readiness | worker references `database.initialize` without calling it | `initialize_storage` |

`pairs.json` lists each as a `positive` pair with its correct training task and
as a `negative` pair (`kind: misleading-no-lexical-cue`) with its decoy. The
original EXP-01/EXP-05 negative pair is kept unchanged as the lexical
disambiguation control: its text is lexically closest to its correct lesson.
