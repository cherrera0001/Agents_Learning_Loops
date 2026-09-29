## Context

Starting the application health check in a clean environment raises AttributeError instead of returning a title. Explicit environment configuration works.

## Expected

Missing or empty LEDGER_TITLE uses Task Ledger. An explicit title is preserved.

## Observed

Starting the application health check in a clean environment raises AttributeError instead of returning a title. Explicit environment configuration works.

## Reproduction

On the experiment/software-learning-v02 branch, install `pip install -e '.[dev]'`, then:

```sh
python -m experiments reproduce EXP-02
```

The injected fixture should fail before repair.

## Acceptance criteria

Missing or empty LEDGER_TITLE uses Task Ledger. An explicit title is preserved. Business regression tests must also pass.

## Experimental metadata

```yaml
experiment: software-learning-v1
task_id: EXP-02
```

Family, difficulty, split and hidden_cause_id are evaluator-only metadata in benchmark/private/tasks.json. They are excluded from the solver context. No solution is included here. This issue is a task, not learned memory.
