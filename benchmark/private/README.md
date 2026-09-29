# Controller / evaluator only

Task split, causal labels, mutation recipe, distance annotations and retrieval
ground truth live here. Nothing in this directory is copied to agent workspaces
or included in AgentView. Public GitHub Issues omit hidden_cause_id and family
metadata; those fields remain here to avoid disclosing the answer.

These labels are author annotations, not observed diagnoses. Evaluation uses
them only after receipts have been sealed. The six tasks include a negative
retrieval pair (AUTH training vs CONFIG transfer) without increasing task count.
L3/L4/L5 are intended distances, not independently validated classifications.
