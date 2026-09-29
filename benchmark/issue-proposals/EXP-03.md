## Context

Application startup raises ConnectionError: database connection refused. The health endpoint cannot be served.

## Expected

Application.start completes and /health returns 200 with status ready.

## Observed

Application startup raises ConnectionError: database connection refused. The health endpoint cannot be served.

## Reproduction

On the experiment/software-learning-v02 branch, install `pip install -e '.[dev]'`, then:

```sh
python -m experiments reproduce EXP-03
```

The injected fixture should fail before repair.

## Acceptance criteria

Application.start completes and /health returns 200 with status ready. Business regression tests must also pass.

## Experimental metadata

```yaml
experiment: software-learning-v1
task_id: EXP-03
```

Family, difficulty, split and hidden_cause_id are evaluator-only metadata in benchmark/private/tasks.json. They are excluded from the solver context. No solution is included here. This issue is a task, not learned memory.
