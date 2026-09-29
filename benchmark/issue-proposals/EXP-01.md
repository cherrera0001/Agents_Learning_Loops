## Context

A request to /profile without a token returns an internal error. The identity API works with demo-token.

## Expected

Requests without a token or with an unknown token return 401; valid identities return 200.

## Observed

A request to /profile without a token returns an internal error. The identity API works with demo-token.

## Reproduction

On the experiment/software-learning-v02 branch, install `pip install -e '.[dev]'`, then:

```sh
python -m experiments reproduce EXP-01
```

The injected fixture should fail before repair.

## Acceptance criteria

Requests without a token or with an unknown token return 401; valid identities return 200. Business regression tests must also pass.

## Experimental metadata

```yaml
experiment: software-learning-v1
task_id: EXP-01
```

Family, difficulty, split and hidden_cause_id are evaluator-only metadata in benchmark/private/tasks.json. They are excluded from the solver context. No solution is included here. This issue is a task, not learned memory.
