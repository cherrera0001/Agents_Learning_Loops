# Agents Learning Loops

An evidence-first laboratory for memory and cross-task software repair.
**We are testing whether prior experience changes decisions and improves outcomes
on new related tasks.** We do not yet claim autonomous software-engineering learning.

## What we are testing

Can a software agent use evidence from previous tasks to change its strategy on
a different task with a related cause? Storage is not retrieval; retrieval is not
learning. The required chain is:

```text
Experience -> Evidence -> Reflection -> Memory
    -> Retrieve(new task) -> Decision change -> Action change -> Outcome change
```

GitHub Issues are tasks. Test outputs, source snapshots and patches are evidence.
The memory graph is internal knowledge derived from evidence. Reflection is an
interpretation that must cite evidence, never a substitute for it.

## What is already demonstrated

Experiment 0 demonstrates **associative action reuse under controlled simulated
conditions**. Its original deterministic scenarios and graph mechanisms remain
intact. Original commits, environments, tests and JSON outputs are preserved in
[evidence/baseline](evidence/baseline/).

Experiment 1 supplies real Python/SQLite execution, six reproducible defects,
isolated task copies, three memory conditions, explicit reflection, append-only
receipts and generated comparisons. Read the [results](results/README.md) before
interpreting gain.

## What is not demonstrated yet

Autonomous software-engineering learning; discovery of new repair algorithms;
statistically significant improvement across independent repositories; superiority
of associative memory over text history; calibrated causal diagnosis; LLM-agent
transfer. The initial agent has three handwritten generic repair operators and
a seeded ordering prior. These constraints limit the interpretation.

## Experiment 0  Synthetic

**Synthetic Associative Retrieval**, preserved as the **Synthetic Associative
Memory Baseline**. `weather_scenario`, `flaky_scenario`, `MemoryGraph`, spreading
activation, reinforcement, decay and pruning retain their APIs. The logical
clock, optional embeddings, serialization migration and tests remain.

```sh
python -m associative_agent_loop.main --json
aal-benchmark --json
```

The prior packaging change moved `src.agent` to `associative_agent_loop.agent`;
this layer introduces no further break. See the [historical technical reference](docs/experiment0-reference.md)
and [original loop protocol](specs/loop_protocol.md). Coverage is mainly L0 exact
reuse, L1 paraphrase and L2 semantic retrieval.

## Experiment 1  Software engineering transfer

[Task Ledger](experiments/software_project/) is a small WSGI application with
authentication, middleware, configuration, SQLite storage, business services and
a worker. It uses standard-library dependencies and actual subprocess tests.
The healthy project is copied and exactly one defect is injected per task.

- Train: [AUTH #24](https://github.com/cherrera0001/Agents_Learning_Loops/issues/24),
  [CONFIG #25](https://github.com/cherrera0001/Agents_Learning_Loops/issues/25),
  [READINESS #26](https://github.com/cherrera0001/Agents_Learning_Loops/issues/26).
- Transfer: [AUTH #27](https://github.com/cherrera0001/Agents_Learning_Loops/issues/27),
  [CONFIG #28](https://github.com/cherrera0001/Agents_Learning_Loops/issues/28),
  [READINESS #29](https://github.com/cherrera0001/Agents_Learning_Loops/issues/29).

Intended pair distances are L3 causal, L5 transfer to another component and L4
multi-hop respectively. These are author annotations, not demonstrated levels
of intelligence. AUTH training and CONFIG transfer share misleading symptoms
but different causes, providing a false-retrieval control within six tasks.

Public issues contain observations and acceptance criteria. Causal labels and
injections live in `benchmark/private/`, outside `AgentView`. The solver receives
only its task, current source and condition-eligible lessons. The controller,
solver and evaluator are separate. See the [complete protocol](specs/software_learning_protocol.md).

## Hypotheses

- Prior relevant evidence reduces repeated failures on related tasks.
- Recall can change the first strategy and inspected file.
- Some recalled lessons are irrelevant, unused or do not improve the outcome.
- Associative memory may or may not outperform textual history.

Equal outcomes and negative transfer are valid findings. Scientific proposals:
[hypothesis #30](https://github.com/cherrera0001/Agents_Learning_Loops/issues/30),
[Experiment 0 #31](https://github.com/cherrera0001/Agents_Learning_Loops/issues/31),
[Experiment 1 #32](https://github.com/cherrera0001/Agents_Learning_Loops/issues/32),
[benchmark #33](https://github.com/cherrera0001/Agents_Learning_Loops/issues/33),
[schema #34](https://github.com/cherrera0001/Agents_Learning_Loops/issues/34),
[receipts #35](https://github.com/cherrera0001/Agents_Learning_Loops/issues/35),
[evaluation #36](https://github.com/cherrera0001/Agents_Learning_Loops/issues/36).

## Experimental conditions

- A `NO_MEMORY`: fresh agent with a seeded strategy order.
- B `TEXT_HISTORY`: the same agent with all verified training lessons as text.
- C `ASSOCIATIVE_MEMORY`: the same agent with top-1 graph recall and paths.

Training starts empty per condition/seed; evaluation freezes the resulting memory.
Source, tests, operators and attempt budgets are identical across paired modes.
Seeds 7, 11 and 23 each run twice. Vector/hybrid conditions are not implemented.
Experiment 1 requires no API key or model download. The bounded agent is named
explicitly in receipts; its strategy vocabulary is not itself learned.

## Metrics

TaskSuccessRate, FirstAttemptSuccessRate, IterationsPerTask, RepeatedFailureRate,
MemoryRetrievalRecall, MemoryRetrievalPrecision, MemoryUseRate, MemoryUtilityRate
and FalseRetrievalRate are generated from receipts. LearningGain is
`metric(memory) - metric(no_memory)`; lower iterations are better.

Utility requires recall to change strategy and action and improve the paired
outcome. Retrieval alone is insufficient. Undefined denominators are `null`.
Paired reports include hypotheses, file inspection order, iterations, failed
attempts, tests, wall time and memories. See [metric definitions and limits](specs/software_learning_protocol.md#metrics-and-falsification).

## Reproduce

From a repository checkout (Python >=3.11; recorded environment 3.14):

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate
# POSIX: source .venv/bin/activate
pip install -e ".[dev]"
# Optional exact reference dependencies, where compatible with your interpreter:
pip install -r requirements-experiment.lock
python -m pytest
python -m scripts.export_schema --check
python -m scripts.export_experiment_schema --check
python -m associative_agent_loop.main --json
```

Reproduce a defect (a nonzero exit is expected before repair):

```sh
python -m experiments reproduce EXP-04
```

Execute A/B/C and reconstruct all aggregates:

```sh
python -m experiments run --seeds 7 11 23 --replicates 2 --evidence-dir evidence/replication
python -m experiments evaluate --evidence-dir evidence/replication --output results/replication
# Reconstruct published results from the original receipts:
python -m experiments evaluate --evidence-dir evidence/runs --output results
```

New runs get new IDs and never replace receipts. Wall times differ; replication
compares a declared semantic projection. Tests validate the harness, while
experiments evaluate the hypothesis. Original semantic embedding tests skip
without the optional `.[embeddings]` extra.

## Current results

Aggregates are generated, never edited by hand: [summary](results/README.md),
[paired comparisons and metrics](results/experiment1.json), [receipts](evidence/runs/).
[Pilot receipts](evidence/pilot/) remain separate from the fixed campaign.

These are descriptive results for a bounded agent. Reduced attempts here do not
establish significant learning or autonomous engineering competence. Equal and
negative pairs remain in the generated report.

## Limitations

Three transfer tasks, one authored application, fixed operators, templated
reflections and uncalibrated confidence. The seeded baseline may be weaker than
static analysis, and shared vocabulary can help retrieval. Same-seed repetitions
are determinism checks, not independent scientific observations.

The graph stores claims with evidence but does not prove causes. Memory v1
implements ADD/IGNORE; unsupported actions fail explicitly. Skill promotion is
future work. Existing Experiment 0 version-2 memories are never silently rewritten.
The audited solver interface is not an OS sandbox for an untrusted agent: future
adapters must not receive the whole repository. Receipt hashes detect alteration,
not malicious forgery by a privileged author.

## Roadmap

Independently replicate and challenge the six-task result; strengthen the
no-memory baseline; add independently authored held-out tasks and blinded causal
annotations; introduce an isolated LLM adapter; test negative transfer. Only then
expand to vector/hybrid conditions, contradiction handling, merge/deprecation
and promotion to skills.

## Related work

[Reflexion](https://arxiv.org/abs/2303.11366) studies verbal feedback for agents;
[SWE-bench](https://arxiv.org/abs/2310.06770) evaluates code changes against real
GitHub issues; [Voyager](https://arxiv.org/abs/2305.16291) studies an open-ended
agent with a skill library. These motivate reflection, task-grounded evaluation
and reusable knowledge. This small bounded harness is not a replication of those
systems or a comparable benchmark score.

MIT licensed. Existing development memory remains in [learning/](learning/).
Experimental dogfooding candidates are assessed separately before admission.
