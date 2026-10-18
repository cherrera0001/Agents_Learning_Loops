# Learning to Fix Issues under a Global Budget: A Measurement-First Campaign in the Gemma 4 Developer Agent Competition

**Subtitle (working):** Sealed predictions, clean A/Bs, and a five-role council — what actually moved the score, and what didn't.

> Borrador del Paper Track (deadline 2026-11-12, 3.000 palabras máx., Writeup o PDF arXiv-ready —
> requisitos verificados el 2026-10-17 en `data/foro_kaggle/2026-10-18/paginas_paper/`). Idioma: inglés
> (coincide con el manuscrito del repo; cambiable). Regla de redacción: solo cifras verificadas;
> todo lo que dependa del lunes 2026-10-19 va con `[PENDIENTE — lunes]`. Presupuesto del esquema en
> `paper_track_outline.md`; esta versión ~1.500 palabras reales + placeholders.

## Abstract (180/250)

We report a measurement-first campaign for a declarative-only SWE agent competition: every
intervention is a single-variable configuration change, every score is compared against a sealed
prediction and an explicit noise band, and a five-role council of measurement roles re-counts each
decision-bearing number before the owner decides. In three weeks the campaign moved a public score
from 0.05–0.13 to 0.17, and the strongest effect was not a prompt but a budget: raising the per-task
wall from 4.5 to 5.0 minutes in a clean A/B (same kit, one key changed) added +0.07, outside the
instrument noise band. We show which popular beliefs did not survive verification — a widely
cited "5.5-minute per-task rule" turned out to be participant arithmetic, and the public 0.24
"baselines" are not supported by the leaderboard — and we publish our noise band, our measurable
set, and our failure taxonomy so that every number in this paper is reproducible from the
repository. `[PENDIENTE — lunes: una línea con el resultado del contraste de brazos.]`

## 1. Introduction (350)

Agents that repair real issues are usually improved by changing the model or the prompt. In a
competition where the submission is a declarative bundle (system prompt, tool list, sampling and
budget configuration) compiled against a fixed harness, and where scoring costs one submission
slot per day on a shared queue, the scarce resource is not ideas but **measurement**. This paper
is about running that constraint as a method rather than an inconvenience.

Contributions: (i) a pre-registered measurement protocol (sealed predictions, clean A/Bs, an
explicit noise band from repeated identical runs, a non-empty-patch counting metric); (ii) a
negative-result-rich account of which levers moved the score and which did not; (iii) a public
audit of two widespread community beliefs (the "5.5-minute wall" and the "0.24 baseline"); (iv)
an open replication package — every configuration is fingerprinted and recomputable from the
repository.

## 2. Method: the measure → propose → decide loop (500)

The campaign runs a fixed loop. **Measure**: each experiment is a run of the competition harness
on a fixed task set, with per-task outcomes and patch hashes recorded. **Propose**: a five-role
council (data analyst, harness forensics, trajectory QA, AI architect, and — after cross-review —
a method auditor whose re-count overrules the others) measures the question in parallel over the
same files, each delivering measured / inferred / unmeasured separately, plus what would refute
their conclusion. Cross-review uses an unsigned dossier so roles cannot defer to the organizer's
hypothesis. **Decide**: the owner decides; the loop records estimate and outcome per episode in a
devlog, so the next recall retrieves how similar issues were estimated and how they ended.

Two protocol details mattered. First, **sealed predictions**: before any submission, a dated
prediction row (point + interval + reasoning) is written to a sealed CSV; the score is later
compared against it (the 0.17 result falsified its own prediction by exceeding the interval —
which is information, and it is reported as such). Second, **clean A/Bs by construction**: kits
are built by copying a verified base and changing exactly the keys under test; configuration
fingerprints (SHA-256 over the sorted base64 of the bundle files) are recomputed before any run
and asserted in the notebook before the GPU spins up. A worked example is the fifth council
session (vuelta 49), whose re-count corrected five decision-bearing numbers in the campaign's own
analysis, including an overstated wall-death count and a mislabelled patch metric.

## 3. Setup: contract, harness, data boundary (400)

The submission contract is declarative-only: `agent.yaml` (one model variant per submission),
prompts, `configs/sampling.yaml`, an optional `eval_config.yaml` (timeout_seconds,
max_tool_calls, max_time_minutes, max_turns), and optional LoRA adapters. The harness (swegemma
0.2.11, adk-submission 0.2.13) runs tasks sequentially in a sandbox; scoring applies the patch in
a fresh container and runs hermetic pytest; **the only global wall is 12 hours including sandbox
setup and excluding patch validation — verified from the official pages and the host's forum
answers on 2026-10-17** (an earlier belief in a ~5.5-minute per-task wall was refuted: it was
participant arithmetic, not a rule).

Data boundary: per-task traces and repository content are never published; only aggregates,
fingerprints, and hashes. The public practice set has 129 tasks; we built all 129 snapshots from
the published base commits and ran the **gold-patch check locally**: 77 of 129 pass with the
reference patch in our sandbox (rich 39/48, fastapi 35/67, requests 3/13, httpx 0/1). The host
confirmed the hidden test set is filtered so that gold passes at 100% — i.e., the 52 local
gold-failures are a public-set calibration floor (missing test dependencies, a pytest-8/httpbin
fixture recursion in requests, version-gated tests), not scorer behaviour. Local measurements are
therefore normalized by this measurable set.

## 4. Results (800; `[PENDIENTE — lunes]` en 4.2-4.4)

**4.1 The budget wall (measured).** The campaign's largest effect was not textual. Replica runs
showed 13 of 20 tasks hitting the 4.5-minute wall; a token-level time model fitted on 499
requests (Δt = 4.5 s + 28.8 ms per output token, R² = 0.89) showed output tokens are ~80% of the
wall clock, and reasoning (thinking budget 4096) dominates them. Raising max_time_minutes from
4.5 to 5.0 — one key, everything else byte-identical — moved the public score from 0.10 to 0.17
(+0.07, outside the instrument noise band of ±0.041 estimated from repeated identical
submissions). A public-ablation figure (23 vs 48 resolved with thinking disabled, single run)
motivated a faithful thinking-off arm (`thinking_budget: 0`; the compiler only honours zero,
not the documented `include_thoughts: false` switch) `[PENDIENTE — lunes: resultado sub-020]`.

**4.2 Noise band.** `[PENDIENTE — lunes: réplicas 2-3 de la condición; flips por tarea; banda]`

**4.3 Arm contrast.** `[PENDIENTE — lunes: presupuesto / thinking / forrajeo / híbrido 8-min
sobre las 20 rich, normalizado por el conjunto medible; regla Δ>banda]`

**4.4 Community audits.** The public "0.24 baselines" are not supported by the leaderboard: of
their authors, none scores above 0.20 (best team 0.24 belongs to unrelated teams with 7-15
submissions); the family sits at 0.18-0.20 and its recipe (8 minutes, 28 tool calls, 240 s
command timeout, edit-by-call-12) fits the verified 12-hour envelope. The 12B model variant is
permitted by the rules but failed to score for three teams at submission time.

## 5. Threats to validity (450)

(i) Small n: 20-task local set (13 measurable-and-winnable), 58-task public split — wide
intervals on every local rate. (ii) One observation per arm on the leaderboard; the public score
itself carries ±0.04 noise. (iii) The substitute task set is not the original 19-task set
(irrecoverable); local comparisons are within-set only. (iv) The thinking-off arm is not a clean
A/B against the 0.17 submission (different prompt lineage); it isolates the budget only against
the 4.5-minute condition. (v) Local calibration floor: a third of public fastapi tasks and most
requests tasks cannot pass even with the gold patch in a local sandbox; the hidden set is cleaner
by construction, so local rates are pessimistic. (vi) The public/private 50-50 split means the
public rank is a sample, not the outcome. (vii) Self-reported model identity and effort in
episodes. (viii) The campaign is a single team, single model variant (31B). (ix) Timestamped
forum evidence can change: rules were re-verified on 2026-10-17 and may move again.

## 6. Conclusion (300)

Under a one-submission-per-day constraint, the winning move is not a better prompt but a better
instrument: sealed predictions, clean A/Bs, a measured noise band, and a council that re-counts
its own analysis. The budget wall — not search, not tool count — was the measured bottleneck, and
partial relief of it bought +0.07 with one key. `[PENDIENTE — lunes: cierre con el resultado del
contraste y la decisión de selecciones finales.]`

## References (a completar)

Repository (method, fingerprints, registry, sealed predictions): github.com/cherrera0001/Agents_Learning_Loops
· Competition pages and forum threads (timestamped captures in the replication package).
