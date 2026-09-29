## Question

Can each claim be reconstructed from actual execution?

## Hypothesis

Append-only receipts with source hashes, patches, test outputs, decisions and separate memory-update events provide an auditable chain.

## Method

Atomic no-clobber publication, canonical SHA-256 verification, error receipts and tests for overwrite, tampering, and failed publication.

## Evidence

Receipts: evidence/runs/. Initial audit: evidence/baseline/. Implementation and reproducible commands will be linked through the experiment PR.

## Result

Pending sealed experiment campaign; no learning-gain conclusion yet.

## Limitations

Six authored tasks, one bounded deterministic agent, handwritten generic repair operators, and no untrusted-agent OS sandbox. Same-seed repetition tests reproducibility, not independent statistical significance.

## Next action

Review infrastructure, seal receipts, regenerate results, inspect misleading retrievals and replicate independently. Keep this issue open.
