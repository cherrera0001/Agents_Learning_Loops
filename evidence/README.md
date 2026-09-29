# Evidence, not conclusions

- `baseline/`: original ca853fd source hashes and benchmark; packaged/main
  baseline tests and repeated synthetic benchmark output.
- `pilot/`: exploratory pre-freeze runs retained for audit; excluded from final
  results. They predate the final source commit and are not replication claims.
- `runs/`: fixed-protocol immutable task and memory-update receipts. Raw failures
  stay in these files. `python -m experiments evaluate` regenerates results.
- `validation/`: captured development/check outputs, separate from task evidence.

Hashes detect changes. Never hand-edit a receipt to fix a finding. Correct the
code, retain the old evidence and run a new explicitly identified campaign.
Task receipts contain initial source and patches; the source manifest and commit
identify the matching harness, private annotations and acceptance tests.
