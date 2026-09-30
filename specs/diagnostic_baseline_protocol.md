# Supplement: diagnostic baseline (#58)

Supplements [`software_learning_protocol.md`](software_learning_protocol.md) for one opt-in agent. It does
not change that protocol, the default agent or any published campaign. Design, analysis and predictions are
pre-registered in [`docs/preregistration/diagnostic-baseline.md`](../docs/preregistration/diagnostic-baseline.md).

## Scope

The agent `bounded-ast-repair-v1+diagnostic-v1` (`experiments.diagnostic.DiagnosticRepairAgent`) has the same
three operators and the same patches as `bounded-ast-repair-v1`. It is run only by
`python -m experiments run --campaign diagnostic-baseline-v1`, whose receipts go to
`evidence/diagnostic-baseline-v1/` by default. Any other recipe runs the default agent exactly as before.

## Extended solver input

Besides PublicTask, current application source and condition-eligible lessons, this agent receives the
public reproduction `test-0` (`returncode` and `stderr` only). This is the run of the public acceptance and
business tests on the defective workspace. For this agent, the controller runs `test-0` after RETRIEVE and
before the decision (`decision_inputs` in the receipt); the default agent keeps its order (decision, then
`test-0`). The statement "the bounded agent never reads test output" in the protocol describes the default
agent.

The agent never receives private annotations, task identity as a lookup key, mutation recipes, golden
patches, other conditions' results or the output of repair attempts (`tests[1:]`). It decides once.

## Diagnosis and joint policy

D (`diagnose`) keeps only the terminal exception class and a `NoneType` marker of each failing test, and
maps Python and standard-library names to operators (`diagnostic-rules/v1`). It narrows and reorders: every
plan is a permutation of the three operators. If D is ambiguous, the plan is exactly the default plan of the
condition. The retrieval key (`title + context`) and memory content are unchanged.

## Receipts and evaluation

- Same schema (`software-learning-receipt/v2`) and hash normalization (`lf/v1`).
- Additive fields, written only by this agent: `decision.policy`, `decision.diagnostic`,
  `decision.plan_without_memory`, `decision.memory_proposal`, `decision.memory_effect`, and the record field
  `decision_inputs`. The hashed agent context also covers the reproduction the agent received.
- `python -m experiments evaluate` requires agent and policy to agree in both directions: the default
  agent declares no policy and carries no diagnostic-baseline field, the diagnostic agent declares exactly
  `diagnostic-baseline/v1`, and any other agent name is rejected. It rejects a directory that mixes agents
  or policies. For diagnostic receipts it requires exactly
  `decision_inputs = {"order": ["RETRIEVE", "test-0", "plan"], "reproduction": "test-0"}`, sequential test
  IDs and a failing `test-0`; it recomputes each decision from the receipt (task, eligible lessons, seed and
  `test-0`) and requires the same diagnosis in the three conditions of each (batch, seed, task). The replay
  proves consistency with the recorded inputs, not that nothing else was consulted: the order is enforced
  by the runner and tested by call order. Reports of published campaigns are unchanged.
- The pre-registered analysis is `python -m scripts.analyze_diagnostic_baseline --evidence <dir>`. It
  verifies each receipt seal with the standard library, cites `generated_from`, and rejects anything but
  the declared campaign (2 batches × 6 seeds × 9 tasks × 3 conditions, no duplicates, lessons only from
  earlier training of the same batch, seed and condition, one `memory_update` per B/C training run)
  before any verdict. Pairs never mix batches.
