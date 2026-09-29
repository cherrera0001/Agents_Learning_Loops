## Context

Requests to /tasks with an unknown identity fail with TypeError before the middleware can return 401. A valid token succeeds.

## Expected

Missing and unknown identities receive 401. A valid editor receives a task list.

## Observed

Requests to /tasks with an unknown identity fail with TypeError before the middleware can return 401. A valid token succeeds.

## Reproduction

On the experiment/software-learning-v02 branch, install `pip install -e '.[dev]'`, then:

```sh
python -m experiments reproduce EXP-04
```

The injected fixture should fail before repair.

## Acceptance criteria

Missing and unknown identities receive 401. A valid editor receives a task list. Business regression tests must also pass.

## Experimental metadata

```yaml
experiment: software-learning-v1
task_id: EXP-04
```

Family, difficulty, split and hidden_cause_id are evaluator-only metadata in benchmark/private/tasks.json. They are excluded from the solver context. No solution is included here. This issue is a task, not learned memory.
