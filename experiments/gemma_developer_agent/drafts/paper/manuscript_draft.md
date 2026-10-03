> **Draft of 2026-10-02. Superseded in part; not rewritten.** It has no related work or citations, which the Paper Track requires, and it states as fact
> claims that are not measured. It is superseded by the
> [baseline pre-registration](../../../../docs/preregistration/kaggle-baseline-a.md), by the entry document
> [`../../README.md`](../../README.md) and, for the final text, by issue #105. In particular: the 60-minute,
> 100-call and 500-turn limits are defaults, not rules (the rule is 12 hours for all tasks); the tasks are
> not SWE-bench tasks; condition A already has the graph tools; and no result with the model exists.

# Agents Learning Loops (ALL): Offline Bounded Memory Consolidation, Structural Anchors, and Declarative Skills for Open-Weights Software Engineering Agents

**Track:** Kaggle Gemma 4 Developer Agent Paper Track  
**Author:** Cristóbal Herrera (Agents Learning Loops Project)  
**Date:** October 2026  
**Artifact Repository:** `github.com/cherrera0001/Agents_Learning_Loops`  

---

## Abstract

Autonomous software engineering agents frequently exhibit what we define as the **stochastic retry pattern**: repeatedly modifying code and re-running test suites until execution succeeds by chance. In open-weights models such as Google’s Gemma 4 running under isolated sandbox environments, multi-turn trial-and-error risks context saturation and tool-call stagnation within finite operational budgets.

To address these challenges, we present an adaptation of **Agents Learning Loops (ALL)** tailored to the hermetic constraints of the `swegemma` evaluation harness:
1. **Offline Learning and Skill Compilation ($k \to 1$):** Because evaluation tasks run in isolated, air-gapped containers with no persistent state between tasks, ALL's associative learning operates *offline*. The agent executes over training task distributions, logs structured episodes, and compiles recurring, validated repair patterns ($\ge 3$ independent confirmations) into declarative ADK procedural skills (`SKILL.md`).
2. **Causal Taxonomy (L0–L5) and the NRNE Hypothesis:** We formalize the **NRNE (No Recuerdo $\neq$ No Encuentro)** theoretical dilemma, where syntax-level retrieval struggles across non-lexical, causal distances (L3–L5).
3. **Structural Execution Anchors (Hypothesis H8):** Addressing our verified negative empirical baseline (Hypothesis H4, where lexical memory induced negative transfer under misleading problem statements: 0/18 vs. 6/18 without memory), we propose seeding retrieval on deterministic execution artifacts: pytest exception tracebacks and AST dependency neighbors (`get_code_neighbors`) provided by the competition harness.

We outline a pre-registered experimental design (A/B/C/D) evaluating offline-consolidated skills against cold-start and placebo baselines on SWE-bench tasks, embracing negative boundaries and verifiable receipts to advance disciplined autonomous engineering.

---

## 1. Introduction: The Limits of Stochastic Retries

In standard benchmark settings (e.g., SWE-bench), autonomous coding agents frequently operate in an open-ended trial-and-error cycle:
$$\text{Analyze} \longrightarrow \text{Edit Code} \longrightarrow \text{Run Tests} \longrightarrow \text{Observe Failure} \longrightarrow \text{Retry}$$

When a solution is reached on a later turn, it is often difficult to distinguish structured learning from stochastic exploration of the search space. Under the evaluation rules of the Google Gemma 4 Developer Agent Competition (`swegemma`), each task is allotted a strict budget: 60 minutes, 100 tool calls, and 500 reasoning turns in an air-gapped container (`network_mode="none"`) on 4x NVIDIA L4 GPUs serving `gemma-4-31b-it-qat-w4a16-ct`.

Under these constraints, unguided retries incur two primary failure modes:
1. **Tool Budget Exhaustion:** Fumbling through unconstrained directory searches rapidly depletes the 100 tool-call allocation.
2. **Cross-Session Amnesia:** Because the harness wipes the workspace between tasks, any knowledge gained during an execution is lost unless systematically captured beforehand.

In human software engineering organizations, knowledge is not re-derived from scratch on every ticket. Teams document post-mortems, establish playbooks, and encode recurring patterns into linting rules and reusable scripts. ALL brings this lifecycle to autonomous agents.

---

## 2. The Theoretical Bottleneck: Causal Distance (L0–L5) and the NRNE Dilemma

A key theoretical contribution of ALL is distinguishing between syntax-level similarity and causal depth. We formalize the **NRNE Dilemma** (*No Recuerdo $\neq$ No Encuentro*): a solution exists in the knowledge base, but surface symptoms fail to retrieve it.

Consider a distributed failure:
* **Incident A:** Low-level socket error: `ECONNREFUSED 127.0.0.1:5432`.
* **Incident B:** JavaScript harness error: `Jest test run timed out after 5000ms`.

Both stem from an identical root cause: *the PostgreSQL container exposes its network socket before the engine finishes internal initialization*.

If an agent relies on symptom keywords, the phrase `"Jest test run timed out"` shares minimal textual or semantic overlap with `"ECONNREFUSED"`. The agent risks concluding that no prior experience applies.

To formalize this, ALL defines the **Taxonomy of Causal Distances (L0 to L5)**:

* **L0 (Exact):** Identical syntax and matching stack trace.
* **L1 (Paraphrase):** Same defect described with different wording.
* **L2 (Domain Semantic):** Related concepts within the same library or framework.
* **L3 (Causal):** Divergent symptoms originating from an identical root cause.
* **L4 (Multi-Hop):** Causality requiring deduction across multiple intermediate layers or services.
* **L5 (Transfer):** Architectural patterns that translate across disjoint programming languages or ecosystems.

In L3–L5, retrieval must traverse causal relationships rather than relying on natural language descriptions alone.

---

## 3. Architecture of ALL in the `swegemma` Competition Ecosystem

The official competition harness (`adk-submission`) imposes a declarative security contract: competitors submit declarative YAML configurations (`agent.yaml`), markdown instructions, and ADK skills. Arbitrary Python agent loops cannot be executed in the evaluation environment.

Consequently, the ALL learning loop operates in two distinct phases:

```text
OFFLINE PHASE (Development & Training)
[Training Issues] ──> [swegemma Local Harness] ──> [Execution Receipts (evidence/)]
                                                           │
                                                           ▼
[Declarative SKILL.md] <── [Pattern Mining (≥3x)] <── [ALL MemoryGraph]
         │
         ▼
ONLINE PHASE (Hermetic Competition Submission)
[submission.zip (agent.yaml + skills/)] ──> [4x L4 GPUs (Gemma 31B)] ──> [Resolution Rate]
```

### 3.1 The MemoryGraph and Association Topology
During offline training, execution traces are structured into a directed graph $G = (V, E)$:
* **Symptoms ($V_S$):** Normalized exception classes, failing assertion locations, and target AST nodes.
* **Root Causes ($V_C$):** Defect classifications.
* **Repairs ($V_R$):** Verified patch strategies.

Edges represent semantic associations: $e(V_S, V_C) = \text{caused\_by}$, $e(V_C, V_R) = \text{solved\_by}$, and $e(V_R, V_S) = \text{contradicts}$. Activation accumulates across paths, attenuating with fan-out and edge distance.

### 3.2 Epistemic Skill Promotion
In the baseline ALL protocol, skill promotion was conceptualized as future work. For the Kaggle Gemma 4 challenge, we implement this mechanism offline:
$$\text{Event} \longrightarrow \text{Episode} \longrightarrow \text{Pattern} \longrightarrow \text{Validated Rule} \longrightarrow \text{ADK Skill}$$

When a repair strategy resolves problems sharing the same causal structure across $\ge 3$ independent tasks without contradictory outcomes, the pattern is compiled into a standalone `skills/<name>/SKILL.md` directory. In the submission, Gemma 4 accesses these skills directly, bypassing exploratory fumbling.

---

## 4. Empirical Baseline, Negative Results, and Structural Anchors (H8)

### 4.1 Prior Verified Campaigns and Honest Limitations
In earlier deterministic benchmarks (Experiment 1, Task Ledger repository, documented in `results/reference-v2/`):
* In recurring tasks with clear lexical clues, memory reduced repair attempts from 2.0 (stateless) to 1.0.
* Associative memory retrieved 18/18 relevant lessons compared to 18/54 in flat history baselines.
* **However, limitations were explicit:** The proxy metric `RepeatedFailureRate` remained at 1.0 across all conditions (54/54), indicating that memory did not eliminate all repeated failure modes. In transfer experiments (H7), failure memory with $\tau = 0.1$ removed the correct first attempt in 3 of 18 pairs, demonstrating that cross-task memory can contaminate future decisions.

### 4.2 The Critical Negative Result: Hypothesis H4
In pre-registered experiment H4 (`docs/results/h4-associative-vs-history.md`), we introduced **lexical decoys**: issues whose text pointed toward an incorrect subsystem (e.g., authentication wording in a configuration bug).
* **Crucial Context:** Experiment 1 and Hypothesis H4 were evaluated strictly on a **deterministic, non-LLM bounded solver with three hand-written repair operators** (`src/experiments/agent.py`), not a language model. The results represent an architectural baseline of memory retrieval over fixed operators, and have not yet been observed in Gemma 4.
* **Outcome:** Both flat textual history and associative memory achieved **0/18 (0.00)** first-attempt resolution, whereas the stateless baseline (no memory) achieved **6/18 (0.33)**.
* **Conclusion:** When memory retrieval is seeded by natural language keywords, misleading cues induce severe **negative transfer**.

### 4.3 Structural Anchors via Code Intelligence Tools (Hypothesis H8)
To address the vulnerability identified in H4 without relying on fragile keyword matching, ALL formulates **Hypothesis H8**: retrieval must be anchored in deterministic execution artifacts and AST relationships. This hypothesis is currently an open proposal without experimental data.

The `swegemma` harness natively provides three code-intelligence tools backed by pre-computed NetworkX graphs:
* `get_code_neighbors(node, edge_type)`
* `search_similar_code(query, k)`
* `get_code_subgraph(nodes)`

Under H8, the agent does not retrieve skills based on problem statement keywords. Instead, it runs an initial targeted test via `run_command`, extracts the exception traceback, and queries `get_code_neighbors` to identify the structural neighborhood. Whether this structural grounding successfully mitigates lexical decoys in Gemma 4 remains an empirical question to be tested.

---

## 5. Pre-Registered Experimental Design (A / B / C / D)

To rigorously evaluate this architecture on SWE-bench tasks within `swegemma`, we define four pre-registered conditions:

| Condition | Agent Architecture | Skills Configuration | Retrieval Anchor |
|---|---|---|---|
| **A (Baseline)** | `gemma-4-31b-it-qat-w4a16-ct` Starter Kit | No skills | None |
| **B (Placebo)** | Identical Gemma 31B agent | Hand-written skills (no empirical training) | Issue text |
| **C (ALL Offline)** | Identical Gemma 31B agent | Offline ALL-consolidated skills ($\ge 3$ verified episodes) | Issue text |
| **D (ALL + H8)** | Identical Gemma 31B agent | Offline ALL-consolidated skills | AST Graph (`get_code_neighbors`) + Traceback |

### 5.1 Protocol & Falsification Rules
1. **Leakage Boundary:** Training tasks and evaluation tasks are disjoint. No evaluation task contributes to skill compilation.
2. **Deceptive Tasks:** The evaluation set includes deliberately misleading problem descriptions to test resilience against negative transfer.
3. **Primary Metric:** Resolution Rate ($PASS / Total$).
4. **Secondary Metrics:** Mean tool calls per resolved task; time-to-submission.
5. **Pre-Registered Prediction:** Consistent with our pre-registration, we predict little to no difference between Condition A and Condition C ($RR(C) \approx RR(A)$) on standard tasks, as prior experiments (H4, H7) show that software repair experience transfers poorly between tasks of a software project. On deceptive tasks, we predict Condition C will degrade performance relative to A (negative transfer), while Condition D is hypothesized to maintain baseline resolution by grounding navigation in the AST graph.

---

## 6. Conclusion

Autonomous software engineering agents require structured, verifiable methodologies rather than unconstrained trial-and-error loops. By compiling empirical execution experiences into declarative ADK skills offline and anchoring their retrieval in the structural topology of the code graph, Agents Learning Loops provides a principled, reproducible path toward disciplined software repair with open-weights models.
