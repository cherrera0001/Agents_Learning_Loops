## Context

The report service raises AttributeError on a None value, resembling the earlier profile crash. This occurs only without explicit environment configuration; the database is available.

## Expected

Missing or empty LEDGER_REPORT_LABEL uses Open tasks. Configured labels are preserved and count is correct.

## Observed

The report service raises AttributeError on a None value, resembling the earlier profile crash. This occurs only without explicit environment configuration; the database is available.

## Reproduction

On the experiment/software-learning-v02 branch, install `pip install -e '.[dev]'`, then:

```sh
python -m experiments reproduce EXP-05
```

The injected fixture should fail before repair.

## Acceptance criteria

Missing or empty LEDGER_REPORT_LABEL uses Open tasks. Configured labels are preserved and count is correct. Business regression tests must also pass.

## Experimental metadata

```yaml
experiment: software-learning-v1
task_id: EXP-05
```

Family, difficulty, split and hidden_cause_id are evaluator-only metadata in benchmark/private/tasks.json. They are excluded from the solver context. No solution is included here. This issue is a task, not learned memory.
