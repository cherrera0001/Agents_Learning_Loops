# Experiment 1 protocol (software-learning-v1)

## Question and interpretation

We are testing whether prior task evidence changes decisions and outcomes on
new related software tasks. Storage, retrieval, use and utility are distinct.
The first implementation tests a **bounded strategy-selection mechanism** on
real code, not autonomous discovery of new repair algorithms. The no-memory
prior is a seeded permutation of three generic repair operators. This is a weak,
explicit baseline: a stronger static analyzer might choose correctly without
memory. Reflection text and its confidence (0.6) are templated, not an LLM
diagnosis or calibrated posterior.

## Fixed initial protocol

Six tasks only. EXP-01/02/03 are training; EXP-04/05/06 are transfer. No evaluation
receipt can be admitted to training memory. Distances are intended author
annotations: AUTH L3 (causal), READINESS L4 (worker -> report -> database), CONFIG
L5 (configuration experience transferred to a reporting component). They are
not independent evidence of depth or generality. The complete taxonomy is
L0 exact, L1 paraphrase, L2 semantic, L3 causal, L4 multi-hop, L5 transfer.

The fixed six-task campaign (task set `v1`, the CLI default) is unchanged by
later extensions; its annotations in `benchmark/private/tasks.json` are pinned
by the published receipts.

Reference campaign: seeds 7, 11, 23; two exact replications each; three strategy
attempts per task; 20-second timeout per test invocation; all three conditions.
Mode order is shuffled per seed. Each task gets a fresh agent and defective
workspace. Each strategy starts from the same defective source. Only memory
carries across tasks; patches, tests, interpreter state and filesystem do not.
Transfer uses frozen training snapshots. A successful run requires acceptance
and business regression tests to exit 0; reproducing the original failure is
mandatory. Baseline reproduction tests are logged but excluded from repair
iterations and failure-rate denominators. Tests execute in separate processes.

## Misleading tasks without lexical cues (task set `misleading-v1`, #45)

The original negative pair (EXP-01 AUTH training vs EXP-05 CONFIG transfer)
did not mislead: EXP-05's text ("without explicit environment configuration",
"AttributeError") is lexically closest to its *correct* lesson EXP-02, so it
cannot distinguish causal transfer from lexical disambiguation. It is kept
unchanged as the lexical-disambiguation control.

`misleading-v1` = `v1` + three transfer tasks, one per true family. Their public
title and context reuse the vocabulary of a **decoy** family's training issue
and avoid the vocabulary of the true family; only the source code reveals the
cause. Every public statement remains true of the injected defect.

| Task | Public symptom | Decoy (training issue) | True family | Injected defect | Repairing operator |
|---|---|---|---|---|---|
| EXP-07 | some `/tasks` calls raise TypeError right after startup | READINESS (EXP-03) | AUTH | `authorize` guards `token is None`, not the looked-up principal | `validate_optional_identity` |
| EXP-08 | summary request returns a blank label | AUTH (EXP-01) | CONFIG | report label falls back to `""`, not `DEFAULT_LABEL` | `normalize_environment` |
| EXP-09 | summary fails to load in a clean environment | CONFIG (EXP-02) | READINESS | worker references `database.initialize` without calling it | `initialize_storage` |

Each family is the true family once and the decoy once. The application code
is untouched (adding components would change every v1 workspace); defects are
new mutations of existing components through the same injection mechanism, and
each is repaired by exactly one existing operator. Annotations live in
`benchmark/private/tasks_misleading.json` (`family`, `hidden_cause_id`,
`split: transfer`, `relevant_training_tasks`, `distance`, `decoy_family`,
`decoy_training_tasks`); `pairs.json` lists the correct pair as `positive` and
the decoy pair as `negative` with `kind: misleading-no-lexical-cue`.

The absence of lexical cues is enforced by `tests/test_experiment_misleading.py`,
not by intent: (1) no public text field contains a token that only the true
family's training lesson carries, nor a listed mechanism word of that family;
(2) under the TEXT_HISTORY ranking `cosine(title + context, symptom + rule)` the
decoy training lesson scores highest and more than twice the correct one;
(3) the only ASSOCIATIVE_MEMORY lexical seeds (>= 0.12) belong to the decoy
lesson; (4) with real training receipts both memory conditions rank the decoy
lesson first. The public text deliberately does not quote the exception
message where it would name the true mechanism (EXP-09 says "raises an
exception"). The bounded agent never reads test output, so this affects
retrieval only.

Task publication: the protocol treats GitHub issues as tasks, but no new issue
is created for EXP-07..09. They are published in the repository only
(`benchmark/public/`, `benchmark/issue-proposals/EXP-0x.md`), tracked by #45;
`benchmark/issues.json` has no entry for them and their receipts carry
`issue: null` (the runner already treats the link as optional).
`scripts/publish_experiment_issues.py` skips them.

Run: `python -m experiments run --task-set misleading-v1 --seeds 1 4 5 6 7 9
--replicates 1 --evidence-dir evidence/pilot/misleading-v1`. The six seeds
cover the six permutations of the no-memory prior exactly once.

## Conditions

- A `NO_MEMORY`: no retrieval and no consolidation; a fresh seeded strategy prior.
- B `TEXT_HISTORY`: all previously verified lessons in chronological order;
  the same agent ranks that text by lexical similarity to the current issue.
- C `ASSOCIATIVE_MEMORY`: lexical seeding over symptoms, components and lessons;
  the existing Experiment 0 refractory spreading engine produces top-1 recall
  and paths. No semantic embedding model is used in this condition.

All share the same operators, budgets, acceptance tests and source hashes.
We do not implement VECTOR_MEMORY or HYBRID_MEMORY conditions. Experiment 0's
pre-existing optional embeddings remain available and unchanged.

## Execution and receipts

`run_experiment(task, agent, memory_mode, seed)` returns a receipt path.
The checked phase transition table enforces ISSUE -> RETRIEVE -> INSPECT ->
HYPOTHESIZE -> CHANGE -> TEST -> OBSERVE; failure can repeat INSPECT; terminal
observation continues DIAGNOSE -> REFLECT -> CONSOLIDATE. The bounded agent
proposes a strategy ordering before inspection, then parses actual source and
proposes a concrete patch in INSPECT. It does not generate new algorithms.

Task receipts include public issue data, initial source text/hash, acceptance
hash, source manifest, environment description, seed, agent version, eligible
memory snapshot, retrieval paths, considered and selected strategies, inspection
order and file hashes, unified patches, actual test command/stdout/stderr/exit
code, iterations, wall time, diagnosis and structured reflection.

Each file is atomically published by hard-linking a flushed temporary file to a
new UUID filename. Existing receipts are never replaced. SHA-256 detects later
alteration; this is **not** a digital signature, WORM storage, or protection
against a privileged author rewriting both payload and hash. Filesystems must
support hard links; an unsupported filesystem fails rather than silently
overwriting. Harness errors also create receipts and invalidate aggregation.

Reflection is an interpretation with evidence references, not evidence itself.
ADD is admitted only after verified failing reproduction, nonempty patch and
passing final tests consistent with the claimed strategy. A separate immutable
`memory_update` receipt records the actual before/after graph and changes. This
avoids retroactively rewriting the task receipt after consolidation. Publication
failure leaves the caller's memory unchanged. IGNORE is implemented. UPDATE,
MERGE and DEPRECATE are representable but explicitly rejected until implemented.

## Schemas and existing architecture

Experiment 0 remains a NetworkX MultiDiGraph with Pydantic validated nodes and
edges, logical time, contextual valence, EMA/Hebbian reinforcement, decay, pruning
and `GraphDocument` version 2. It already migrates version 1 documents. Its APIs,
`specs/memory_schema.json` and old serialized memories are unchanged.

Experiment 1 uses a separate `software-learning-memory/v1` namespace with
Task, Experience, Symptom, Cause, Strategy, Evidence, Lesson, Component and Skill.
Relations include caused_by, solved_by, contradicts, evidence_for, related_to,
applies_to and promoted_to_skill. Only the evidence-backed subset is emitted;
Skill promotion and contradiction resolution remain future work. An ephemeral
projection maps typed nodes into legacy Concepts solely for spreading. It does
not rewrite or ambiguously reinterpret old graph files. Export with
`python -m scripts.export_experiment_schema`; check with `--check`.

## Leakage boundary

`benchmark/public/` holds one issue description and acceptance test per task.
`benchmark/private/` holds splits, causal labels, relevance annotations and
defect injections. The solver receives only PublicTask, current application
source and condition-eligible lessons. It never receives hidden_cause_id,
future issues, the mutation recipe, a golden patch, relevance labels or other
condition results. Public GitHub issue bodies also exclude causal labels.

The controller copies app files, business tests and only the current acceptance
test. Agent edits are allowlisted to existing app files; tests are protected.
Subprocesses receive only allowlisted OS variables, no inherited configuration,
Python paths or credentials. The current solver is audited local code with a
restricted data interface. **This is not an OS sandbox for a hostile plugin or
arbitrary LLM-generated Python.** Such an adapter needs process/container and
network/filesystem isolation before use. Private files are public in the research
repository for audit; never grant a future solver the whole repository checkout.

## Metrics and falsification

The evaluator reads sealed receipts, validates paired hashes and memory ancestry,
and applies private relevance labels only after execution. It rejects missing or
mismatched no-memory pairs and changed causal annotations.

- TaskSuccessRate: successful transfer runs / transfer runs.
- FirstAttemptSuccessRate: first repair test passes / transfer runs.
- IterationsPerTask: repair attempts / transfer runs.
- RepeatedFailureRate: known-cause failed attempts / all failed repair attempts.
  A cause is known if a prior training run in that condition succeeded with the
  evaluator's same cause label; an attempt is attributed only if its final
  exception signature matches reproduction. This conservative proxy cannot
  reliably classify new assertion failures or multiple simultaneous causes.
- MemoryRetrievalRecall: relevant training lessons retrieved / eligible relevant
  training lessons (one per transfer task in this initial campaign).
- MemoryRetrievalPrecision: relevant retrieved lessons / all retrieved lessons.
- MemoryUseRate: runs citing memory in selection / runs with retrieval. Use may
  confirm the existing selection; `decision_changed` is reported separately.
- MemoryUtilityRate: retrieved memory changed first strategy and action and
  improved success, or reduced iterations among successful paired runs / runs
  with retrieval. UUIDs never serve as evidence of decision changes.
- FalseRetrievalRate: irrelevant retrieved lessons / all retrieved lessons.
- LearningGain: metric(memory) minus metric(no_memory), preserving direction:
  negative iterations are favorable, positive failure rates are unfavorable.

Per-task breakdown (`task_breakdown.json` / `.md`, written next to
`experiment1.json`, which keeps its published shape): for each task and
condition, runs, success, first-attempt success, iterations, mean iteration
delta against the paired NO_MEMORY run, first strategy, and lessons exposed
and cited by source task and family. "Cited" lessons are those named by the
selection (`decision.memory_ids`: the top-ranked lesson, ranked by the agent in
TEXT_HISTORY and by propagation in ASSOCIATIVE_MEMORY); "exposed" lessons are
all handed to the solver (`retrieval.memories`).

- MisleadingRetrievalRate: cited lessons from the task's `decoy_family` / all
  cited lessons, over tasks annotated with `decoy_family`. Null if nothing was
  cited (always for NO_MEMORY). Counts are reported with the rate.
- CorrectFamilyRetrievalRate: cited lessons from the true family / all cited
  lessons on those tasks.
- MisleadingExposureRate: exposed decoy lessons / exposed lessons on those
  tasks; TEXT_HISTORY exposes every lesson, so it is 1/3 there by construction.

Undefined denominators are null, not zero. The negative AUTH->CONFIG pair is
included in private pairs.json; history necessarily exposes irrelevant lessons,
so precision is not directly equivalent to decision quality. We also test a
misleading-memory condition with a one-attempt budget: it must retain failure.
No harness test requires a positive aggregate learning gain.

UUIDs and measured times differ on rerun. Replication compares a declared
semantic projection: source/test hashes, retrieval task IDs, decisions, actions,
patches, inspections, test exits and outcomes. Same-seed replications check
determinism, not independent samples; three transfer tasks cannot support broad
statistical claims. Report negative, equal and improved pairs together.
