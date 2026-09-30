# Evidence, not conclusions

«Harness» aquí es el harness de experimento, definido en [`docs/entorno/harness.md`](../docs/entorno/harness.md).

- `baseline/`: original ca853fd source hashes and benchmark; packaged/main
  baseline tests and repeated synthetic benchmark output.
- `pilot/`: exploratory pre-freeze runs retained for audit; excluded from final
  results. They predate the final source commit and are not replication claims.
- `pilot/misleading-v1/`: pilot campaign of task set `misleading-v1` (EXP-01..09,
  misleading tasks without lexical cues, #45); seeds 1 4 5 6 7 9, one
  replicate. Evaluated in `results/pilot/misleading-v1/`. Not part of
  `results/experiment1.json`.
- `reference-v2/`: reference campaign v2 (#44): seeds 1 4 5 6 7 9 (all 6
  permutations of the no-memory prior), task set `misleading-v1`, two replicates,
  receipt schema v2. Run with `python -m experiments run --campaign reference-v2`;
  evaluated in `results/reference-v2/`. The historical `runs/` (seeds 7 11 23) is
  unchanged.
- `diagnostic-baseline-v1/`: opt-in diagnostic-baseline campaign (#58): agent
  `bounded-ast-repair-v1+diagnostic-v1`, same seeds, task set, replicates and
  receipt schema as `reference-v2/`; 324 task runs + 72 memory updates, produced
  by commit `0d90edc`. Run with `python -m experiments run --campaign
  diagnostic-baseline-v1`; evaluated in `results/diagnostic-baseline-v1/`, read in
  `docs/results/diagnostic-baseline.md`. Pre-registration:
  `docs/preregistration/diagnostic-baseline.md`.
- `runs/`: fixed-protocol immutable task and memory-update receipts. Raw failures
  stay in these files. `python -m experiments evaluate` regenerates results.
- `validation/`: captured development/check outputs, separate from task evidence.
- `reference-lf-v1/`: small cross-platform reference campaign (`--seeds 7
  --replicates 1`, receipt schema v2, `source_hash_normalization: lf/v1`)
  generated on Windows. CI reruns it on Ubuntu and requires
  `python -m experiments compare` to find identical projections, hashes
  included (#42). `runs/` stays v1 (`checkout-bytes/v0`) and is not comparable
  with it at hash level.

Hashes detect changes. Never hand-edit a receipt to fix a finding. Correct the
code, retain the old evidence and run a new explicitly identified campaign.
Task receipts contain initial source and patches; the source manifest and commit
identify the matching harness, private annotations and acceptance tests.
