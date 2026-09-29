## Context

The background worker cannot produce its report: the report service fails when querying SQLite. Running the report on an already available database succeeds.

## Expected

A fresh background summary returns label Open tasks and count 0 without manual setup.

## Observed

The background worker cannot produce its report: the report service fails when querying SQLite. Running the report on an already available database succeeds.

## Reproduction

On the experiment/software-learning-v02 branch, install `pip install -e '.[dev]'`, then:

```sh
python -m experiments reproduce EXP-06
```

The injected fixture should fail before repair.

## Acceptance criteria

A fresh background summary returns label Open tasks and count 0 without manual setup. Business regression tests must also pass.

## Experimental metadata

```yaml
experiment: software-learning-v1
task_id: EXP-06
```

Family, difficulty, split and hidden_cause_id are evaluator-only metadata in benchmark/private/tasks.json. They are excluded from the solver context. No solution is included here. This issue is a task, not learned memory.
