## Context

Running the summary in a clean environment raises an exception instead of returning the Open tasks label and a count. No explicit configuration is set.

## Expected

In a clean environment a summary returns the label Open tasks and count 0.

## Observed

Running the summary in a clean environment raises an exception instead of returning the Open tasks label and a count. No explicit configuration is set.

## Reproduction

Install `pip install -e '.[dev]'`, then:

```sh
python -m experiments reproduce EXP-09
```

The injected fixture should fail before repair.

## Acceptance criteria

In a clean environment a summary returns the label Open tasks and count 0. Business regression tests must also pass.

## Experimental metadata

```yaml
experiment: software-learning-v1
task_set: misleading-v1
task_id: EXP-09
```

Published in the repository only; tracked by #45, no dedicated GitHub issue.
Family, difficulty, split and hidden_cause_id are evaluator-only metadata in benchmark/private/tasks_misleading.json. They are excluded from the solver context. No solution is included here. This issue is a task, not learned memory.
