# Per-task breakdown

Generated with `python -m experiments evaluate`. Do not edit by hand.

## MisleadingRetrievalRate

| Condition | MisleadingRetrievalRate | decoy cited / cited | CorrectFamilyRetrievalRate |
|---|---|---|---|
| ASSOCIATIVE_MEMORY | 1.0 | 18 / 18 | 0.0 |
| NO_MEMORY | None | 0 / 0 | None |
| TEXT_HISTORY | 1.0 | 18 / 18 | 0.0 |

## Tasks

| Task | Split | Family | Decoy | Condition | Runs | Success | First attempt | Iterations | Delta vs A | Cited lessons by source task |
|---|---|---|---|---|---|---|---|---|---|---|
| EXP-01 | train | authentication |  | ASSOCIATIVE_MEMORY | 6 | 1.0 | 0.3333333333333333 | 2.0 | 0.0 | {} |
| EXP-01 | train | authentication |  | NO_MEMORY | 6 | 1.0 | 0.3333333333333333 | 2.0 | None | {} |
| EXP-01 | train | authentication |  | TEXT_HISTORY | 6 | 1.0 | 0.3333333333333333 | 2.0 | 0.0 | {} |
| EXP-02 | train | configuration |  | ASSOCIATIVE_MEMORY | 6 | 1.0 | 0.3333333333333333 | 2.0 | 0.0 | {} |
| EXP-02 | train | configuration |  | NO_MEMORY | 6 | 1.0 | 0.3333333333333333 | 2.0 | None | {} |
| EXP-02 | train | configuration |  | TEXT_HISTORY | 6 | 1.0 | 0.0 | 2.5 | 0.5 | {"EXP-01": 6} |
| EXP-03 | train | readiness |  | ASSOCIATIVE_MEMORY | 6 | 1.0 | 0.0 | 2.5 | 0.5 | {"EXP-02": 6} |
| EXP-03 | train | readiness |  | NO_MEMORY | 6 | 1.0 | 0.3333333333333333 | 2.0 | None | {} |
| EXP-03 | train | readiness |  | TEXT_HISTORY | 6 | 1.0 | 0.0 | 2.5 | 0.5 | {"EXP-02": 6} |
| EXP-04 | transfer | authentication |  | ASSOCIATIVE_MEMORY | 6 | 1.0 | 1.0 | 1.0 | -1.0 | {"EXP-01": 6} |
| EXP-04 | transfer | authentication |  | NO_MEMORY | 6 | 1.0 | 0.3333333333333333 | 2.0 | None | {} |
| EXP-04 | transfer | authentication |  | TEXT_HISTORY | 6 | 1.0 | 1.0 | 1.0 | -1.0 | {"EXP-01": 6} |
| EXP-05 | transfer | configuration |  | ASSOCIATIVE_MEMORY | 6 | 1.0 | 1.0 | 1.0 | -1.0 | {"EXP-02": 6} |
| EXP-05 | transfer | configuration |  | NO_MEMORY | 6 | 1.0 | 0.3333333333333333 | 2.0 | None | {} |
| EXP-05 | transfer | configuration |  | TEXT_HISTORY | 6 | 1.0 | 1.0 | 1.0 | -1.0 | {"EXP-02": 6} |
| EXP-06 | transfer | readiness |  | ASSOCIATIVE_MEMORY | 6 | 1.0 | 1.0 | 1.0 | -1.0 | {"EXP-03": 6} |
| EXP-06 | transfer | readiness |  | NO_MEMORY | 6 | 1.0 | 0.3333333333333333 | 2.0 | None | {} |
| EXP-06 | transfer | readiness |  | TEXT_HISTORY | 6 | 1.0 | 1.0 | 1.0 | -1.0 | {"EXP-03": 6} |
| EXP-07 | transfer | authentication | readiness | ASSOCIATIVE_MEMORY | 6 | 1.0 | 0.0 | 2.5 | 0.5 | {"EXP-03": 6} |
| EXP-07 | transfer | authentication | readiness | NO_MEMORY | 6 | 1.0 | 0.3333333333333333 | 2.0 | None | {} |
| EXP-07 | transfer | authentication | readiness | TEXT_HISTORY | 6 | 1.0 | 0.0 | 2.5 | 0.5 | {"EXP-03": 6} |
| EXP-08 | transfer | configuration | authentication | ASSOCIATIVE_MEMORY | 6 | 1.0 | 0.0 | 2.5 | 0.5 | {"EXP-01": 6} |
| EXP-08 | transfer | configuration | authentication | NO_MEMORY | 6 | 1.0 | 0.3333333333333333 | 2.0 | None | {} |
| EXP-08 | transfer | configuration | authentication | TEXT_HISTORY | 6 | 1.0 | 0.0 | 2.5 | 0.5 | {"EXP-01": 6} |
| EXP-09 | transfer | readiness | configuration | ASSOCIATIVE_MEMORY | 6 | 1.0 | 0.0 | 2.5 | 0.5 | {"EXP-02": 6} |
| EXP-09 | transfer | readiness | configuration | NO_MEMORY | 6 | 1.0 | 0.3333333333333333 | 2.0 | None | {} |
| EXP-09 | transfer | readiness | configuration | TEXT_HISTORY | 6 | 1.0 | 0.0 | 2.5 | 0.5 | {"EXP-02": 6} |
