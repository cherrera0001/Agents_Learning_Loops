# How Much Can a Difference Be Trusted? Task Validity and Run-to-Run Variation in an Exploratory Evaluation of a Gemma 4 Coding Agent

**Subtitle:** Seven conditions, no established improvement, and one tool failure that disappeared without changing which tasks were resolved.

Cristóbal Herrera Jara

## Abstract

We tuned the configuration of a Gemma 4 coding agent for the Gemma 4 Developer Agent competition and report, in aggregate counts, what we measured to read our own comparisons. Across seven conditions we did not establish an improvement; no observed increase was replicated, and this is not evidence of no effect. In the competition notebook, 71 of the 129 public tasks separate the reference patch from no patch, and 103 after installing three test-only packages. Between identical runs, 1 to 2 individual tasks changed result while the total changed by 0 to 1 within each pair. The edit tool was called without a mandatory argument in 107 of 134 and 49 of 75 calls in two baseline runs and in 0 of 26 with one added instruction line, yet the resolved tasks were the same 7 of 30 as in the second baseline run. Of 23 tasks never resolved in three runs, a retrospective review judged 12 solvable from the issue text and the repository; 10 of those did not reach a relevant edit in at least two of three runs. With reasoning on and a larger budget, 9 of 19 tasks were resolved against 6, 7 and 7, below the 10 set in advance to keep the change. A preregistered offline calibration of three memory-retrieval parameters over 97 replayed episodes did not beat the defaults (validation 57.3% against 56.4%, decision threshold 5 percentage points) and the defaults were kept. The first fingerprint-verified replica of a competition condition resolved 4 of 20 tasks; in 13 of its 16 failures the relevant file was reached within three calls, and 12 of the 16 hit the 4.5-minute wall without a submitted patch: the dominant failure converts a located file into an edit inside the budget, not search.

## 1. Introduction

A participant in this competition submits a configuration for a fixed model and harness and receives the fraction of hidden tasks whose patch passes hidden tests. Development happens on 129 public tasks. With a few dozen tasks per run, a change of 1 or 2 resolved tasks is both the effect one hopes for and the effect chance produces.

We ask one question:

> In this setting, what difference between two agent configurations can be told apart from repeating the same configuration?

We report four measurements:

1. Which public tasks discriminate in the notebook environment, with the cause confirmed by intervention for 31 of the 58 that do not (§ 4.1).
2. The run-to-run variation of a fixed configuration, in task results, totals and failure categories (§ 4.2).
3. Seven conditions with predictions logged before each run, including one where a failure mechanism disappeared while the resolved tasks stayed the same (§ 4.3).
4. Where the agent is lost on the tasks it never resolved, with a retrospective judgement of how many were solvable (§ 4.4).

The evidence has three sources, kept apart: controls without the model (§ 4.1), runs of the agent (§ 4.2 to § 4.4), and a reviewer's judgement (§ 4.4).

## 2. Related work

SWE-bench poses real GitHub issues whose solution is a patch to the codebase (Jimenez et al., 2024). Later audits of it report solutions given in the issue report or its comments and weak test cases (Aleithan et al., 2024), and patches counted as correct that fail the developer-written test suite (Wang et al., 2026). Zhu et al. (2025) report that many agentic benchmarks have problems in how tasks are set up or outcomes are rewarded. Two public notebooks audited this competition's public tasks before us: Xodarev (2026) reports 119 of 129 sound tasks with a re-implemented grader and rebuilt environments, and Gluzdov (2026) reports 114 after dependency-only repairs, with the official scoring logic unchanged. We did not reproduce them; the three counts differ in environment, control criterion and evaluator.

On SWE-bench Verified, single-run pass rates varied by 2.2 to 6.0 percentage points depending on the run selected, across three models and two scaffolds (Bjarnason et al., 2026). Writing predictions before the data is in the spirit of preregistration (Nosek et al., 2018).

One intervention adds instruction text. Gloaguen et al. (2026) found that repository-level context files did not generally improve task success, although agents followed their instructions.

## 3. Setting and method

**Model and harness.** The competition fixes the model, `gemma-4-31b-it-qat-w4a16-ct`, and a harness with tools to run commands, read, search and edit files, and submit a patch. The hidden set has about 120 tasks from private repositories; the 129 public tasks come from four open-source repositories.

**Baseline.** The official starter kit with no adapters, 8,192 output tokens, model reasoning off, and a per-task budget of 4 minutes, 40 tool calls, 100 turns and 60 seconds per command. Sampling uses temperature 0.2 with no seed.

**Runs.** One *run* is one pass of one configuration over a fixed task list, in a Kaggle notebook with four L4 GPUs. The measurement set has 30 tasks: 15 from one repository (rich), used throughout development, and 15 from another (fastapi). The fastapi tasks were unseen only in the first of the three 30-task runs. Earlier sessions used those 15 rich tasks, or a 16-task set containing them. All 30 discriminate (§ 4.1).

**Loop rule.** Before each run we logged a prediction in counts and the outcome that would refute it. Changes in § 4.3 alter one thing each, except the two-stage design and the seventh, which alters three. As an operating rule, a change counted as an improvement only with a net gain of at least three resolved tasks; this rule has no statistical test or power analysis behind it.

**Competition contract.** The submission is a declarative agent, not a program: a directory of YAML compiled by a sandboxed compiler (`compile_submission`), with no Python entrypoints, closed host registries for tools, models, skills and callbacks, `!include` directives restricted against path traversal, a 3 GiB unpacked cap, and an allowlist of extensions (.yaml, .md, .txt, .py for skill scripts, .json, .safetensors). Per-task budgets (tool calls, turns, minutes, per-command timeout) are data in an optional `eval_config.yaml`; container setup is excluded from the agent's time budget. The competition totals imply about six minutes per task (12 hours of evaluation over about 120 hidden tasks). Two tools are free of the tool-call budget: `submit_patch()` and `get_status()`, the latter reporting live consumption and remaining time. If a session ends by timeout or budget without a `submit_patch()` call, the harness still extracts `git diff` against the baseline and evaluates any non-empty patch. Before the hidden tests run, the harness forcefully resets any test files or test-runner configuration the agent's patch touched. One consequence we relied on: a submission cannot change the task environment — there is no dependency or environment hook in the contract, so candidate changes are confined to instructions, budgets, adapters and sampling parameters. (All contract facts from the harness documentation, swegemma Evaluation Harness & Competitor Guide, HARNESS_README.)

**Deviations, declared.** We preregistered a different design: hold out one repository and compare repeated runs with McNemar's test (Dietterich, 1998). We never ran it: the held-out repository was used for development, and variation was measured by counting tasks. All results are therefore exploratory. The prediction log was kept outside version control during this period, and five entries carry estimated times.

## 4. Results

### 4.1 The instrument: which public tasks can measure anything

A task *discriminates* if its tests fail without a patch and pass with the reference patch. We ran both controls on all 129 public tasks in the notebook sandbox, without the model (Table 1).

**Table 1**

*Public Tasks That Discriminate, by Repository and Environment*

| Repository | Tasks | As shipped | With three test packages installed |
|---|---|---|---|
| fastapi | 67 | 29 | 60 |
| rich | 48 | 42 | 43 |
| requests and httpx | 14 | 0 | 0 |
| Total | 129 | 71 | 103 |

*Note.* Each cell counts tasks whose tests fail without a patch and pass with the reference patch. One control run per cell; no model.

As shipped, 58 tasks do not discriminate: in 55 the reference patch does not pass, and 3 pass with no patch. In 34 of the 55 the tests never ran because a package used only by the tests was missing. With the packages installed, 31 of those 34 discriminate. One further rich task changed with no identified cause, and none of the original 71 was lost. Twenty-six tasks still do not discriminate: 23 fail with the reference patch, cause unexamined, and 3 pass without a patch.

Thirty-one of those 58 tasks reflect a gap in the environment: failing to discriminate in this sandbox does not make a task invalid.

### 4.2 Variation of an unchanged configuration

**Table 2**

*Two Runs of the Same Configuration on the Same Tasks*

| Task set | Resolved, run 1 and run 2 | Net change in total | Tasks that change result | Tasks that change failure category |
|---|---|---|---|---|
| 16 rich tasks | 4 and 4 | 0 | 2 | — |
| 15 rich tasks | 3 and 3 | 0 | 2 | 6 |
| 30 tasks (rich and fastapi) | 6 and 7 | 1 | 1 | 13 |

*Note.* One pair of runs per row; denominators are the tasks in the set. A dash means the category was not recorded.

Table 2 holds two measures. Task-level, 1 or 2 tasks changed result between identical runs; the total of resolved tasks changed by 0, 0 and 1. Three pairs do not establish a minimum detectable difference for either. Across sessions, seven runs on the 15 shared rich tasks, three of them baseline, resolved 2 to 4, and no two differed in more than 2 tasks. The failure category of a task changed in 13 of 30 tasks, against 1 of 30 for the result: a failure table from one run was not a stable guide to what to fix.

On the public leaderboard, the same local archive submitted twice scored 0.06 and 0.05. We could not verify that the two stored files are identical, so this is not a controlled replicate. Read as truncated fractions of a 58-task table, the smallest size consistent with published scores, they are 4 and 3 tasks; that reading is ours.

After the data cut-off the situation repeated with a different archive, the configuration with reasoning on: submitted twice on October 7, 2026, it scored 0.08 and 0.13. The second submission was still marked with a system error more than a day later and received its score afterwards; the leaderboard stores different sizes for the two (79,355 and 72,108 bytes). This is not a controlled replicate either. Under the same 58-task reading they are 5 and 8 tasks. Scores read on October 9, 2026, 17:41 UTC. A later diagnosis confirmed the error status was the Kaggle platform's, not a defect of the archive: both submissions carry scores, 0.08 (id 56895202) and 0.13 (id 56916129).

### 4.3 Seven conditions, no established improvement

**Table 3**

*Each Change Against the Baseline on the Same Tasks*

| Change | Prediction logged before the run | Resolved: baseline, change | Verdict on the prediction |
|---|---|---|---|
| Reasoning on, 4-minute limit | No gain | 4 and 4, 3 of 16 | Held, for that budget |
| 100 tool calls instead of 40 | More tasks resolved | 3 and 3, 2 of 15 | Refuted |
| Public two-stage design (read-only locator, then editor) | More tasks resolved | 3 and 3, 3 of 15 | Refuted |
| 20 tool calls | At least 2 resolved | 2, 2 of 15 | Held |
| Written rule against repeated calls | Does not make the first edit earlier | 2, 4 of 15 | Held; net gain of two, not replicated |
| One-line rule for the edit tool | Trapped sessions drop to 1 or fewer | 6 and 7, 7 of 30 | Held on the mechanism; same tasks resolved |
| Reasoning on, 60 tool calls, 4.5 minutes | Keep with 10 or more of 19; discard with 8 or fewer | 6, 7 and 7, 9 of 19 | Undecided |

*Note.* One run per change. Baseline counts are from one to three runs; in row 7 the third is the run of row 6. "Trapped" means three or more consecutive malformed edit calls.

No row of Table 3 establishes an improvement, which is not evidence of no effect: the largest net increases (+2 of 15; +2 to +3 of 19 selected tasks) were single runs. With reasoning on and a 4-minute limit, 11 of 13 unresolved sessions ran out of time; that row describes reasoning under that budget only. The seventh condition was run on 19 tasks: the 12 judged solvable in § 4.4 and the 7 resolved before. It resolved 9, against 6, 7 and 7 in the three earlier runs on the same tasks: 3 tasks never resolved before (0 of 3 sessions each), with 1 of the 7 lost to a context-length rejection that discarded its patch. Nine of its 10 failures hit the time limit and none reached 60 calls. By the threshold logged beforehand this does not decide.

The sixth row separates a mechanism from an outcome. The agent called the edit tool without its mandatory argument in 107 of 134 calls in one baseline run and 49 of 75 in the other, then repeated the identical failing call: 3 of 30 sessions were trapped in each run. A synthetic call whose string argument is closed with the wrong delimiter reproduces the same malformed arguments in the public parser of the model server; the raw model output was not stored. In the single run with one added instruction line the failure did not occur (0 of 26 calls, 0 trapped sessions). The resolved tasks were the same 7 as in the second baseline run, 6 of them also resolved in the first. The tasks trapped in one baseline run were not resolved in the other, although 2 of the 3 were not trapped there.

Of the 40 predictions logged, 31 were evaluated: 20 held and 11 were refuted. Three fell between their own thresholds, four could not be evaluated or were never run, and two were pending at the cut-off.

### 4.4 Where the agent is lost

Twenty-three of the 30 tasks were never resolved in three runs (69 sessions). Fifteen have an issue text shorter than 250 characters: a title and, in most, a reference to an external issue. With reasoning off, no short-statement task was resolved: 0 of 15 in each 30-task run, and 0 of 16 counting one more from the earlier 16-task set; the seventh condition resolved 2 of the 7 it ran. The threshold was chosen after seeing the rich data and held in a prediction logged before the fastapi tasks were first run (0 of 6 short, 3 of 9 long).

A reviewer read the issue, reference patch, hidden tests and surrounding code of all 23 tasks and judged 12 solvable from the issue text and the repository, 9 solvable only by guessing an unstated name, message or value, and 2 not solvable. This judgement is retrospective, made with access to the reference patch and hidden tests, not an independent measure of difficulty.

**Table 4**

*Furthest Stage Reached in at Least Two of Three Runs*

| Furthest stage | 23 never resolved | of which 12 judged solvable | 7 resolved |
|---|---|---|---|
| Does not read the file that had to change | 10 | 6 | 0 |
| Reads it, does not edit it | 6 | 4 | 0 |
| Edits another region of it | 2 | 0 | 0 |
| Reaches the right region | 5 | 2 | 7 |

*Note.* Columns count tasks, placed at the highest stage reached in two or more of three runs.

Ten of the 12 tasks judged solvable did not reach a relevant edit in at least two of three runs (Table 4). Of the 69 sessions on never-resolved tasks, 25 never attempted an edit; in the 44 that did, the first attempt came after a median of 65% of the tool-call budget, against 26% in the 20 resolved sessions. Half of their calls (1,267 of 2,532) repeated an identical earlier call, and 36 of the 69 sessions made 40 or more tool calls, while 5 ended with the harness's session-timeout error (3 of them among the 36). Two tool defects waste calls: the file-reading tool lost its line range in 344 of 851 calls across the three runs, in resolved and failed sessions alike, and the similarity search returned nothing in all 221 calls.

When a patch exists it is rarely close: of the 41 of those sessions with a patch, 16 contain only debugging scripts, the agent's own tests or documentation, and in 23 of the other 25 the agent passes none of the target tests. No verification failure was caused by the environment.

### 4.5 A verified replica of the seventh condition

After the data cut-off we replicated the seventh condition (reasoning on, 60 tool calls, 4.5 minutes) end-to-end on the competition infrastructure. The original 19 task identifiers of the ninth-of-19 run could not be recovered from any retained record, so the replica used a fixed substitute set of 20 rich tasks, declared as a deviation; the configuration itself is byte-identical to the submitted archive, a fingerprint asserted in the notebook before the model loads. One run completed on October 16, 2026 with no session cutoff (5,563 s of a 9,000 s cap) and resolved 4 of 20; all 16 failures were labelled sin_parche ("no patch") by the run's aggregate. Two further replicas to measure run-to-run variation were prepared but could not start: the account's weekly GPU quota was exhausted. [PENDING — Monday: two more replicas, then the noise-band report.]

### 4.6 What the sixteen failures are, with a corrected premise

The label sin_parche does not mean "no patch". The run's classifier reads a non-existent result attribute (generated_patch; the harness field is agent_patch), so every unresolved task that did not exhaust its budget was recorded as "no patch" regardless of whether a patch existed. Reading the per-task traces against the harness log corrects the premise: four of the 16 failures submitted a patch that grading rejected (patch sizes 465 to 1,248 bytes, one of them including a scratch reproduction script); the other 12 hit the 4.5-minute wall without a submitted patch, 10 of them without any edit to the repository — one looping on identical re-reads, one never reaching the file that had to change — and two with real edits in the working tree that were never submitted, one of them after the agent had verified the fix and started reverting it to demonstrate the bug. The 4-of-20 count does not undercount graded patches; the failure label does undercount patches, and the classifier fix is pending. [PENDING — Monday: classifier fix and re-classification of replicas 2-3.]

Across all 16 failures, the code-intelligence tools were never called, and in 13 of 16 the relevant file was reached within the first three calls. The bottleneck is converting a located file into an edit inside the budget, not search. Three changes that answer this reading were prepared but not run: a navigation-first procedure (fingerprint af8cca829561), a budget-awareness rule set (fingerprint 52ba08ceac25), and short, silent reasoning with thinking budget 1,024 and no visible thoughts (fingerprint 9d0db7b946e7), each changing only instructions or sampling. [PENDING — Monday: run the three variants and the foraging arm (§ 4.8) against the same 20 tasks — seven runs in total including two noise replicas of the condition (≈10.9 GPU-hours of the 30 h weekly quota); the decision rule is fixed before the runs — an arm counts only if it beats the condition by more than the run-to-run noise band.]

### 4.7 Offline calibration of the memory loop, preregistered and negative

The same repository develops an associative-memory loop whose retrieval is governed by three parameters (η_h, α and τ_seed; defaults 0.3, 0.7 and 0.25). We preregistered an offline calibration (committed before any run): replay the 97 recorded development episodes, split temporally (first ~70% to calibrate, last ~30% to validate), search a 3×3×3 grid, and change the defaults only if the best configuration reduced the repeated-failure rate by at least 5 percentage points on validation, with the calibration-window rate of the winner reported beside its validation rate.

The grid collapsed to three distinct behaviors. With the lexical embedder, α is exactly inert (both channels of the hybrid seeding compute the same cosine, verified numerically), η_h did not move the metric in this replay, and only τ_seed mattered. The calibration winner (τ_seed = 0.4, 51.9% against the default's 56.9% on the calibration window) reversed on validation (57.3% against 56.4%; Δ = −0.9 pp, paired bootstrap CI95 [−10.7, +9.3]), while the best validation rate belonged to a different value (τ_seed = 0.1, 53.0%). Per-window denominators: 160 known-cause failures in calibration (46 unclassified, 21.6%) and 117 in validation (27, 18.8%). Under the preregistered rule the defaults were kept, and this negative result is reported as measured. The calibration window would have crowned a configuration the validation window rejects; the split did the work a single window would not have.

### 4.8 Discussion: Levels of autonomy, biological precedent

A fifth intervention arm was designed from a research summary on autonomous worms (the owner’s reading of the open literature to October 13, 2026, unpublished), as an explicit analogical transfer. That literature grades autonomy into four engineering levels — an external script driving actuators, a physical oscillator sustaining the gait, onboard compute with the sequence still written, and action changed by an onboard sensor — over an organizational sense (the organism maintained far from equilibrium by its own activity) that only the living animal meets (Bechtel & Bich, 2023). The swegemma agent is level four by construction (tool observations feed the multi-turn loop), so the arm varies only the policy layer, the instruction file. The mapping that produced it:

| Worm level (source) | Harness counterpart | Our arm |
|---|---|---|
| Roaming/dwelling bistable states, minute-long bouts (Flavell et al., 2020; Haley & Chalasani, 2024) | One instruction file held for the whole task | Foraging: local-first “dwelling”, clock-scheduled “roaming” |
| Local search ≈15 min, then global (fixed off-food sequence) | Budget-clocked escalation; `get_status()` is free | Foraging: escalate at ~⅓ of the 4.5 min |
| Pirouette + dorsoventral bias when the gradient falls; the reorient decision sits in the network (AVA), not the sensor (AWC) | Reorientation after two unproductive retrievals, decided by the policy text, not the search tool | Navigation-first + foraging reorient rule |
| Habituation: massed taps do not retain; four spaced blocks give 24 h memory, GLR-1-dependent (Ardiel & Rankin, 2010; Rose & Rankin, 2001) | Failure memory consolidated across spaced episodes; within a task, change the action after two identical failures | Foraging habituation rule; the repository’s learning loop |
| “Connectivity alone is insufficient”: the connectome lacks synaptic sign and neuromodulation; anatomy underpredicts activity (Izquierdo & Beer, 2016; Cook et al., 2019) | A fully connected retrieval graph whose governance parameters are inert (§ 4.7) | Offline calibration, negative |

The biological precedent justifies the measurement discipline directly. BAAIWorm, the most direct closed-loop claim in that literature (136 of 302 neurons), reproduces the experimental zigzag “extremely similarly” when driven by a periodic signal without feedback, and becomes *less* regular than the animal when the sensory current depends on the body’s position (Zhao et al., 2024): adding a mechanism — even the biologically faithful one — moved the model away from its measured baseline. That is the worm-shaped version of our measure-before-submit rule: an arm is compared offline against the same fixed task set, with a pre-established noise band, before it can cost any of the competition’s evaluation budget.

One correspondence is worth stating with its epistemic label attached. Our preregistered calibration found two governance parameters of a completely connected retrieval graph exactly inert (α inert by construction under the lexical embedder; η_h moving nothing), with only the seeding threshold reaching the criterion window — the same shape, in our domain, as the claim that connectivity without electrophysiology and neuromodulation cannot determine behaviour. We present this as **analogical framing, not evidence**: it constrains nothing about biological networks; it supports only the methodological moral that structural completeness is no substitute for measuring what actually moves the metric.

The foraging arm (fingerprint `fb8175c0e74e`) changes only the instruction file, adding a 298-word “Foraging Policy” whose five rules carry HTML comments naming the biological source of each (dwelling, escalation, pirouette, habituation, acting). [PENDING — Monday: run with the other arms.]

## 5. Threats to validity

- **Small sample.** Thirty tasks, two repositories, three runs; one run each for the edit-tool rule and the seventh condition.
- **Exploratory.** The preregistered design was not run, development tasks were reused, and the operating rule has no test or power analysis.
- **Judgement.** Solvability is one retrospective reading. The trace, test and solvability analyses were produced by LLM-based assistants under the author's direction, not independently replicated.
- **Public is not hidden.** The organisers state that the hidden tasks were curated separately; nothing here predicts the hidden score.
- **One replica, substitute set.** § 4.5 is a single run on 20 substitute tasks, not the 19 original ones; the noise band and any variant contrast are pending.
- **Deterministic replay.** § 4.7 replays recorded episodes rather than observing new ones; two runs of the same code give the same bytes, not independent observations. The repeated-failure metric is a proxy for class-level visibility, not outcome, and with 117 known-cause failures in validation the interval on the difference (±10 pp) cannot detect small effects.
- **Post-cut-off material.** § 4.5 to § 4.7 and the platform-error confirmation were produced after the data cut-off by the same analysis pipeline; the trace and solvability analyses remain LLM-assisted (§ 5, Judgement).

## 6. Reproducibility and data use

Data cut-off: October 7, 2026, 02:30 UTC; post-cut-off additions: October 16–17, 2026 (§ 4.5 to § 4.8). The baseline configuration has fingerprint `3b0e87556166`, the edit-tool variant `7e2082197834` and the seventh condition `0f52de0b84cb`: the first 12 hexadecimal digits of the SHA-256 of the base64 encodings of the six configuration files, sorted as strings and concatenated with no names or separators. The replica and four instruction variants (navigation-first `af8cca829561`, budget-awareness `52ba08ceac25`, short-silent-thinking `9d0db7b946e7`, foraging `fb8175c0e74e`) are fingerprinted with the same formula; the variants are prepared but not run. The validity scripts and leaderboard reader are public: https://github.com/cherrera0001/Agents_Learning_Loops. The competition forbids redistributing task content, so per-task results and traces are not published.

## 7. Conclusion

Between identical runs, 1 or 2 tasks changed result, the total changed by at most one within a pair, and the failure category changed in 13 of 30 tasks; we did not read differences of that size as effects, and we claim no detection threshold. Fifty-eight of 129 public tasks could not measure anything in the environment as shipped. Across seven conditions we did not establish an improvement. In one run, a tool failure did not occur and the resolved tasks were the same 7 as in the second baseline run. In 16 of the 23 tasks never resolved, the agent did not edit the file that had to change in at least two of three runs. With reasoning and a larger budget, one run resolved 3 of the 12 tasks judged solvable that it ran; 9 of its 10 failures ran out of time. A second run is needed. The first verified replica of that condition resolved 4 of 20, and its corrected failure taxonomy shows twelve of sixteen failures dying at the time wall without a submitted patch while the file that had to change was usually reached within three calls — an instruction-level intervention was prepared to target that conversion and awaits its run. A preregistered offline calibration of the memory loop's retrieval parameters produced no improvement over the defaults and they were kept.

## References

Aleithan, R., Xue, H., Mohajer, M. M., Nnorom, E., Uddin, G., & Wang, S. (2024). *SWE-Bench+: Enhanced coding benchmark for LLMs*. arXiv. https://doi.org/10.48550/arXiv.2410.06992

Ardiel, E. L., & Rankin, C. H. (2010). An elegant mind: Learning and memory in *Caenorhabditis elegans*. *Learning & Memory, 17*(4), 191–201. https://doi.org/10.1101/lm.960510

Bechtel, W., & Bich, L. (2023). *C. elegans* as a model of autonomy and its development. *BioSystems, 232*, 105017. https://doi.org/10.1016/j.biosystems.2023.105017

Bjarnason, B. H., Silva, A., & Monperrus, M. (2026). *On randomness in agentic evals*. arXiv. https://doi.org/10.48550/arXiv.2602.07150

Cook, S. J., Jarrell, T. A., Brittin, C. A., Wang, M., Bloniarz, A. E., Yakovlev, M. A., Nguyen, K. C. Q., Tang, L.-T. H., Bayer, E. A., Duerr, J. S., Bülow, H. E., Hobert, O., Hall, D. H., & Emmons, S. W. (2019). Whole-animal connectomes of both *Caenorhabditis elegans* sexes by musical assignment of synapses. *Nature, 571*, 63–71. https://doi.org/10.1038/s41586-019-1352-7

Dietterich, T. G. (1998). Approximate statistical tests for comparing supervised classification learning algorithms. *Neural Computation, 10*(7), 1895–1923. https://doi.org/10.1162/089976698300017197

Flavell, S. W., Raizen, D. M., & You, Y.-J. (2020). Behavioral states. *Current Biology*. https://pmc.ncbi.nlm.nih.gov/articles/PMC7536859/

Gloaguen, T., Mündler-Sasahara, N., Müller, M. N., Raychev, V., & Vechev, M. (2026). *Evaluating AGENTS.md: Are repository-level context files helpful for coding agents?* arXiv. https://doi.org/10.48550/arXiv.2602.11988

Gluzdov, D. (2026). *Gemma 4: Measure before you tune* (Version 7, last run October 1, 2026) [Computational notebook]. Kaggle. Retrieved October 4, 2026, from https://www.kaggle.com/code/dmitriigluzdov/gemma-4-measure-before-you-tune

Haley, J. A., & Chalasani, S. H. (2024). Neural circuit mechanisms underlying *C. elegans* foraging strategies. *Cellular and Molecular Life Sciences, 81*, 277. https://doi.org/10.1007/s00018-024-05223-1

Izquierdo, E. J., & Beer, R. D. (2016). Connecting a connectome to behavior: An ensemble of neuroanatomical models of *C. elegans* klinotaxis. *Current Opinion in Neurobiology, 40*, 153–163. https://www.sciencedirect.com/science/article/abs/pii/S0959438816300691

Jimenez, C. E., Yang, J., Wettig, A., Yao, S., Pei, K., Press, O., & Narasimhan, K. (2024). SWE-bench: Can language models resolve real-world GitHub issues? In *The Twelfth International Conference on Learning Representations*. https://openreview.net/forum?id=VTF8yNQM66

Nosek, B. A., Ebersole, C. R., DeHaven, A. C., & Mellor, D. T. (2018). The preregistration revolution. *Proceedings of the National Academy of Sciences, 115*(11), 2600–2606. https://doi.org/10.1073/pnas.1708274114

Rose, J. K., & Rankin, C. H. (2001). Analyses of habituation in *Caenorhabditis elegans*. *Learning & Memory, 8*(2), 63–69. https://doi.org/10.1101/lm.37801

Wang, Y., Pradel, M., & Liu, Z. (2026). Are "solved issues" in SWE-bench really solved correctly? An empirical study. In *Proceedings of the 2026 IEEE/ACM 48th International Conference on Software Engineering* (pp. 169–181). Association for Computing Machinery. https://doi.org/10.1145/3744916.3764576

Xodarev, A. (2026). *119 of 129 sound: The Gemma 4 grader, rebuilt* (Version 22, last run October 1, 2026) [Computational notebook]. Kaggle. Retrieved October 4, 2026, from https://www.kaggle.com/code/busyaprime/119-of-129-sound-the-gemma-4-grader-rebuilt

Zhao, F., et al. (2024). Whole-brain modelling of the nervous system of *Caenorhabditis elegans*. *Nature Computational Science, 4*, 1127–1139. https://doi.org/10.1038/s43588-024-00738-w

Zhu, Y., Jin, T., Pruksachatkun, Y., Zhang, A., Liu, S., Cui, S., Kapoor, S., Longpre, S., Meng, K., Weiss, R., Barez, F., Gupta, R., Dhamala, J., Merizian, J., Giulianelli, M., Coppock, H., Ududec, C., Kellermann, A., Sekhon, J., . . . Kang, D. (2025). Establishing best practices in building rigorous agentic benchmarks. In *Advances in Neural Information Processing Systems 38* (pp. 184435–184475). Neural Information Processing Systems Foundation. https://doi.org/10.52202/085713-5547
