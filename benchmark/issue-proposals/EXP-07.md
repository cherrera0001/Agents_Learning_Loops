## Context

Immediately after Application.start, some calls to /tasks raise TypeError and cannot be served, even though the database connection is up and other calls to /tasks are served.

## Expected

After Application.start every call to /tasks is answered. A call carrying an unrecognised header value receives the same rejection status as a call carrying no header; the recognised header value still receives the task list.

## Observed

Immediately after Application.start, some calls to /tasks raise TypeError and cannot be served, even though the database connection is up and other calls to /tasks are served.

## Reproduction

Install `pip install -e '.[dev]'`, then:

```sh
python -m experiments reproduce EXP-07
```

The injected fixture should fail before repair.

## Acceptance criteria

After Application.start every call to /tasks is answered. A call carrying an unrecognised header value receives the same rejection status as a call carrying no header; the recognised header value still receives the task list. Business regression tests must also pass.

## Experimental metadata

```yaml
experiment: software-learning-v1
task_set: misleading-v1
task_id: EXP-07
```

Published in the repository only; tracked by #45, no dedicated GitHub issue.
Family, difficulty, split and hidden_cause_id are evaluator-only metadata in benchmark/private/tasks_misleading.json. They are excluded from the solver context. No solution is included here. This issue is a task, not learned memory.
