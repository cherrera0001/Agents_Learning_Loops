## Context

A summary request without arguments returns count 0 with a blank label instead of Open tasks; no error is raised and the count is correct.

## Expected

A summary produced without arguments reports the label Open tasks together with the correct count.

## Observed

A summary request without arguments returns count 0 with a blank label instead of Open tasks; no error is raised and the count is correct.

## Reproduction

Install `pip install -e '.[dev]'`, then:

```sh
python -m experiments reproduce EXP-08
```

The injected fixture should fail before repair.

## Acceptance criteria

A summary produced without arguments reports the label Open tasks together with the correct count. Business regression tests must also pass.

## Experimental metadata

```yaml
experiment: software-learning-v1
task_set: misleading-v1
task_id: EXP-08
```

Published in the repository only; tracked by #45, no dedicated GitHub issue.
Family, difficulty, split and hidden_cause_id are evaluator-only metadata in benchmark/private/tasks_misleading.json. They are excluded from the solver context. No solution is included here. This issue is a task, not learned memory.
