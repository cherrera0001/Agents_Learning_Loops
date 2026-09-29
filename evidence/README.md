# Evidence, not conclusions

- `baseline/`: original ca853fd source hashes and benchmark; packaged/main
  baseline tests and repeated synthetic benchmark output.
- `pilot/`: exploratory pre-freeze runs retained for audit; excluded from final
  results. They predate the final source commit and are not replication claims.
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
