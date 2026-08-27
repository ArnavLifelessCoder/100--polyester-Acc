# ControlPlane.ai - Round 2 Technical Annex

Team 100% Polyester. Supersedes `controlplane_technical_annex.md`, which was written before the Round 2 brief was released.

Round 2 asks for three things: a detailed business proposal, a working prototype of the core mechanism, and a pitch presentation. This document is the proposal and the prototype spec. Section 6 is the build order.

Assumptions are labelled `A1`, `A2` and so on so a reviewer can attack the assumption rather than the arithmetic. Currency is INR.

---

## 0. What changed from Round 1, and why

Read this section first if you already know the Round 1 material. Five things moved.

| Change | Cause | Where |
|---|---|---|
| Volume recalibrated from 1M/month to 130k/month across three workflows | Brief says tens of thousands of interactions per week combined | 1.3 |
| Loss model rebuilt per workflow instead of one blended pool | Brief says each use case carries a different risk signature | 1.3 |
| Risk dimensions are now overlapping tags, not a partition | Brief: a fabricated detail about a person is both a hallucination and a privacy concern | 3.4 |
| Abstention path added for unverifiable claims | Brief: often no reliable real-time ground truth to check against | 3.5 |
| Multi-turn and agentic compounding promoted from backlog to core | Brief: one questionable output can shape several downstream decisions | 3.6 |
| Representation-level detection deleted | Brief confirms enterprises consume models via API, so internals are out of reach. That door is now closed, not deferred | removed |

The Round 1 core survives intact: a consequence-aware decision function, severity bounded by detector precision, and a graded action spectrum. The brief's own complexity list reads as a validation of that framing, particularly the line about deliberately tuning the over-flagging tradeoff rather than solving it away.

---

## 1. Problem Statement

### 1.1 The failure mode

An enterprise LLM deployment produces a response that is fluent, confident, and defective. The defect carries one or more of three risk tags:

| Tag | Defect | Why it survives review |
|---|---|---|
| Performance | Confidently wrong, unsupported, fabricated | Fluency is uncorrelated with correctness. Self-reported confidence is poorly calibrated |
| Cost | Excess tokens, retry loops, oversized model for the task, repeated agent calls | No single response looks expensive. Cost is visible only in monthly aggregate |
| Responsibility | Bias, unsafe content, PII or PHI leakage, policy violation | Requires workflow context the reviewer does not have at read time |

These look like three problems. Structurally they are one: **the response reached a decision point before anything decided it was allowed to.**

### 1.2 Why observability is structurally, not incidentally, late

Observability is a read path. It produces a record after the write has already happened. Three properties make it insufficient regardless of tooling quality:

1. **Temporal.** The signal arrives after the action. Once a customer has been told they qualify for a refund, the enterprise position has changed. Retraction is a second, costlier event.
2. **Sampling.** Review of production traffic is sampled, typically at single-digit percentages, because full review costs more than generation. Coverage of a rare defect is poor by construction.
3. **No actuator.** A dashboard has no control surface. It informs a decision that something else must then make and execute, and in most deployments that something else does not exist.

### 1.3 Quantified impact model, recalibrated to the brief

The brief's reference parameters: an enterprise running multiple AI use cases at once, tens of thousands of interactions per week combined, mixed data governance quality. Modelled as three workflows because the brief is explicit that risk signature varies by use case.

**Assumptions**

- `A1` 130,000 responses per month across three workflows (support chatbot 70k, internal copilot 45k, regulated decision support 15k). Roughly 30k per week, matching the brief.
- `A2` Defect rates differ by workflow: 2.5% support, 3.0% copilot (loosely governed internal data sources, per the brief), 1.5% decision support (better governed, narrower scope).
- `A3` Action conversion differs by workflow: 40% support, 25% copilot, 60% decision support. Decision support is highest because its output exists specifically to be acted on.
- `A4` Consequence per acted-on defect `C_w`: ₹3,000 support (rework, credit, escalation), ₹800 copilot (wasted employee time, rework), ₹50,000 decision support (remediation, notification, regulatory exposure, amortised severe tail).
- `A5` Post-hoc review catches 8% before action, which is generous for sampled review.

**Monthly expected loss**

| Workflow | Volume | Defects | Escaped to action | `C_w` | Monthly loss |
|---|---|---|---|---|---|
| Support chatbot | 70,000 | 1,750 | 644 | ₹3,000 | ₹19.32 lakh |
| Internal copilot | 45,000 | 1,350 | 311 | ₹800 | ₹2.48 lakh |
| Decision support | 15,000 | 225 | 124 | ₹50,000 | ₹62.10 lakh |
| **Total** | **130,000** | **3,325** | **1,079** | | **₹83.90 lakh** |

Escaped Defect Rate: **83 per 10,000 responses.**

Three things fall out that matter more than the headline:

- **The smallest workflow carries 74% of the loss.** Decision support is 11.5% of volume and ₹62 lakh of ₹84 lakh. A control layer with one global threshold spends its budget on the support chatbot, which is where the traffic is and not where the money is. This is the quantitative case for per-workflow policy, and it is the brief's first listed complexity.
- **Cost defects do not justify the product.** They are cheap per event. But they are almost free to detect (token accounting, no model call), so they subsidise the layer's own overhead. One sentence in the pitch, never a slide.
- **The result is sensitive to `A4`.** If ₹50,000 is off by 5x downward, total loss falls to roughly ₹32 lakh/month and the case rests on the support workflow. Volunteer this before a judge finds it. The honest framing: the economics are strongest exactly where deployment is currently most blocked.

### 1.4 Why now

- **Agentic deployment.** When output is a tool call or a payment instruction, the gap between generation and action is zero. There is no user in the loop to catch it, so the decision boundary has to be machine-executed.
- **Regulatory.** EU AI Act Article 14 requires human oversight that is *exercisable*, not merely recorded. NIST AI RMF and ISO/IEC 42001 require demonstrable controls. An immutable decision ledger is the artifact these frameworks actually ask for. The brief's note that regulation differs by geography and keeps evolving is why policy must be versioned data, never hard-coded rules (5.2).
- **Model heterogeneity.** Enterprises run multiple providers and swap them quarterly. Controls inside any one model do not survive the swap.

---

## 2. Solution Overview

### 2.1 Core idea

ControlPlane converts model output from an *artifact to be observed* into a *proposal to be adjudicated*. Every response passes through a decision function that selects an action from a graded spectrum before the response can become an enterprise outcome.

```
┌──────────────┐      ┌──────────────────┐      ┌────────────────┐
│ AI generates │ ───▶ │ ControlPlane     │ ───▶ │ Enterprise     │
│ (any model)  │      │ decides          │      │ outcome        │
└──────────────┘      └────────┬─────────┘      └────────────────┘
                               │
   Risk tags × Consequence × Uncertainty × Irreversibility × Latency budget
                               │
   ALLOW ──▶ HOLD ──▶ CONSTRAIN ──▶ ESCALATE ──▶ BLOCK
   └──────────────── LOG (audit substrate) ─────────────────┘
```

### 2.2 The action spectrum

A monotonic spectrum of increasing intervention cost and increasing utility destruction, not six equal buttons.

| Action | What happens | Latency added | Utility destroyed if the response was fine | Precision required |
|---|---|---|---|---|
| ALLOW | Response passes | 0 | 0 | n/a |
| HOLD | Withheld pending one named check: retrieval verification, policy lookup, a second sampled generation, or human confirmation | 100 ms to 2 s | Low, delay only | Low |
| CONSTRAIN | Restricted to verified content. Unsupported claims are refused rather than rewritten. Model re-prompted with a narrower contract | One extra generation | Low to medium | Low to medium |
| ESCALATE | Routed to a human with risk evidence attached | Seconds to minutes | Medium, human time consumed | Medium |
| BLOCK | Suppressed, fallback served | 0 to one fallback generation | High, user gets nothing | Very high |
| LOG | Not an intervention. The immutable record that a decision was made, with reason codes | Async | 0 | n/a |

**Design decision: no inline rewriting.** The brief lists "edit" as a tiered response option, and we deliberately exclude it. Editing output produces text that no model generated and no human approved, then presents it as the model's answer. In a regulated workflow that is an audit problem, sometimes worse than escalation. CONSTRAIN keeps the useful behaviour, shaping what the system is willing to say, without the provenance liability of silently changing what it said. **Be ready to defend this, since the brief explicitly offers "edit" and a judge may read the omission as an oversight rather than a choice.**

### 2.3 Comparison to alternatives

| Capability | Observability (Langfuse, Arize) | Guardrail libraries (NeMo, Llama Guard) | Human review | ControlPlane |
|---|---|---|---|---|
| Intervenes before action | No | Yes, binary | Yes, slow and sampled | Yes, graded |
| Action space | None | Pass or fail | Approve or reject | Five graded actions |
| Overlapping risk tags | Metrics only | Independent classifiers | Reviewer judgement | Explicit correlation model |
| Consequence-aware thresholds | No | One global threshold | Implicit, inconsistent | Derived per workflow |
| Handles unverifiable claims | n/a | Passes them | Flags uncertainty | Explicit abstention path |
| Multi-turn / agentic risk | Trace view only | Per-call | Impractical | Session risk state |
| Calibrated routing | No | No | No | Per workflow, ECE-gated |
| Model-agnostic | Yes | Mostly | Yes | Yes, API level |
| Decision ledger | Partial | No | Partial | Primary artifact |

**Honest positioning.** A tiered guardrail cascade is not novel and should not be claimed as such. The differentiator is the layer above it: a decision function that selects action severity from consequence and detector precision jointly, under an explicit correlation and abstention model.

---

## 3. Technical Deep Dive

### 3.1 The decision function

A response `r` in workflow `w` produces a risk vector from the detector stack:

```
p̂ = (p̂_perf, p̂_cost, p̂_resp),   each p̂_d ∈ [0,1], a calibrated probability that tag d applies
```

Each workflow carries a consequence vector `C_w = (C_perf, C_cost, C_resp)` and an irreversibility factor `ι ∈ (0,1]` describing how much of the harm is unrecoverable once the action is taken.

For each candidate action `a`:

- `ρ(a) ∈ [0,1]` residual harm multiplier, the fraction of harm still landing if `a` is taken and the response really was defective
- `F(a)` friction cost of taking `a`
- `U(a)` utility destroyed if `a` is taken and the response was actually fine

**Expected loss:**

```
L(a) = ρ(a) · P_def(p̂) · C_eff(p̂) · ι  +  F(a)  +  (1 − P_def(p̂)) · U(a)

a* = argmin_a L(a)   subject to   severity(a) ≤ severity_max(precision, verifiability)
```

`P_def` and `C_eff` are defined in 3.4 and handle the overlap problem. The Round 1 version summed independently over dimensions, which double-counts correlated defects.

Three properties worth stating in Q&A:

1. The third term is the false positive penalty. It is what stops the system converging on BLOCK.
2. Nothing here needs a single scalar risk score. The scalar is an output of the argmin, not an input.
3. `ι` separates *how bad* from *how permanent*. A wrong draft email and a wrong payment instruction can share a consequence estimate and still deserve different actions.

### 3.2 Deriving thresholds instead of guessing them

**ALLOW versus BLOCK.** With `ρ(ALLOW)=1`, `ρ(BLOCK)=0`, `F(BLOCK)=F_b`, `U(BLOCK)=U`:

```
L(ALLOW) = p·C
L(BLOCK) = F_b + (1−p)·U

p·C = F_b + (1−p)·U
p(C + U) = F_b + U
                    p*_block = (F_b + U) / (C + U)
```

**ALLOW versus ESCALATE.** Human review costs `H` all-in and catches a fraction `a_h`:

```
H + p(1−a_h)C = p·C
H = p·a_h·C
                    p*_esc = H / (a_h · C)
```

**Worked example on the three brief workflows.** `A6`: `U = ₹200`, `F_b = ₹50`, `H = ₹120`, `a_h = 0.9`.

| Workflow | `C_w` | `p*_esc` | `p*_block` |
|---|---|---|---|
| Internal copilot | ₹800 | 16.67% | 25.00% |
| Support chatbot | ₹3,000 | 4.44% | 7.81% |
| Decision support | ₹50,000 | 0.27% | 0.50% |

This is the brief's first complexity ("very different risk tolerance, one-size-fits-all rarely works") made arithmetic. The same detector reading `p̂ = 0.05` allows in the copilot, escalates in support, and blocks in decision support. **Nothing is hand-tuned.** Note also that `p*_esc < p*_block` in every row, which is not a design choice but a consequence of escalation destroying less utility than blocking. The spectrum is what minimising expected loss produces.

### 3.3 Precision-bounded severity: the crux

Everything routes on `p̂`, so the honest question is how much survives a mediocre detector.

**Base rate arithmetic.** Take the support workflow at 2.5% defect rate and a plausible mid-quality detector, TPR 0.80, FPR 0.05:

```
Precision = (0.80 × 0.025) / (0.80 × 0.025 + 0.05 × 0.975)
          = 0.020 / 0.0688
          = 29.1%
```

**Roughly seven of ten blocks would be wrong.** A layer behaving that way is switched off inside a week, which is exactly the alert fatigue and bypass behaviour the brief describes.

Inverting for the precision blocking actually needs, at 90% precision:

```
0.020 / (0.020 + FPR × 0.975) ≥ 0.90
FPR ≤ 0.228%
```

Almost no probabilistic hallucination detector reaches that. Deterministic ones do: regex plus checksum on a formatted account number, a hard policy-list violation, a schema failure.

**The design rule that carries the pitch:**

> Action severity is bounded by detector precision, not just by risk magnitude.

```
Detector precision (measured per workflow)  →  Maximum permitted action
  > 0.95  (deterministic)                   →  BLOCK
  0.70 - 0.95                               →  ESCALATE
  0.40 - 0.70                               →  CONSTRAIN or HOLD
  < 0.40                                    →  LOG only
```

This is the answer to the brief's "over-flagging versus under-flagging must be deliberately tuned rather than solved away". We do not tune one threshold. We bound the *severity* by the evidence quality, so the system degrades toward logging as detectors weaken rather than becoming either dangerous or unusable.

### 3.4 Overlapping risk categories

The brief: a fabricated detail about a person is simultaneously a hallucination and a privacy concern, making clean categorization harder than it appears. Two consequences.

**Probability.** Tags are not mutually exclusive, so summing or maxing both mislead. Let `m = argmax_d p̂_d`:

```
P_def = p̂_m + (1 − p̂_m) · [ 1 − Π_{d≠m} (1 − κ · p̂_d) ]
```

`κ ∈ [0,1]` is the independence factor. At `κ = 0` the tags are fully nested and `P_def = max_d p̂_d`. At `κ = 1` they are independent and the expression reduces exactly to `1 − Π_d(1 − p̂_d)`. Real tags sit in between.

`κ` is estimated from the ledger, not assumed:

```
κ̂ = clip( observed co-occurrence rate / co-occurrence expected under independence , 0, 1 )
```

`A8`: initial `κ = 0.4` for the performance-responsibility pair (fabrication about a person is the common case), `κ = 0.9` for cost against either other tag (a retry loop is largely independent of whether the content is unsafe).

**Consequence.** A single incident with two tags does not cost the sum of two incidents. Remediation largely coincides: one response, one correction, one notification. But it is not free either.

```
C_eff = C_m + λ · Σ_{d≠m, triggered} C_d,        λ ≈ 0.3
```

`A9`: `λ = 0.3`. At `λ = 0` the incident costs only its worst dimension, at `λ = 1` you are back to the naive sum. `λ` is estimated from adjudicated incident costs once the ledger has enough joint events.

**Why this matters practically:** the naive sum inflates `P_def` and `C_eff` for exactly the joint cases that are most common, which pushes the system toward over-blocking precisely where it is most visible. The overlap model is not accounting hygiene, it is a false positive control.

### 3.5 No ground truth: the abstention path

The brief's sharpest point is that the same knowledge gaps causing hallucination also block automated verification. A detector that cannot verify must not report `p̂ = 0`.

Every detector emits a pair, not a scalar:

```
(p̂_d , verifiable_d ∈ {true, false})
```

`verifiable = false` when there is no retrieval context, no policy match, the claim is about a novel entity, or the claim type is outside the detector's competence.

When unverifiable, three things happen:

1. `p̂_d` falls back to the workflow prior `π_w,d`, the shadow-mode base rate. Not zero.
2. Precision for that detector on that response is undefined, so `severity_max` drops to HOLD or CONSTRAIN. The system may not block on an unverifiable signal.
3. The decision function runs normally on the prior.

**The useful part is that the arithmetic already does the right thing.** In decision support, `π_w = 0.015` against `p*_esc = 0.0027`, so an unverifiable claim escalates to a human automatically. In the copilot, `π_w = 0.030` against `p*_esc = 0.167`, so the same unverifiable claim is allowed and logged. **Same input, opposite outcome, no special-case code.** That is worth saying out loud in the pitch: abstention is not a separate subsystem, it is the prior flowing through the same decision function.

Reported as a first-class metric: **Abstention Rate**, the fraction of responses where at least one detector could not verify. A rising abstention rate is the early warning that the knowledge base has drifted away from what the model is being asked.

### 3.6 Multi-turn and agentic compounding

The brief: one questionable output can shape several downstream decisions. Round 1 adjudicated single responses, which is insufficient. Two mechanisms.

**Session risk state.** Risk allowed through at turn `t` does not disappear, it contaminates the context that later turns condition on.

```
s_t = 1 − (1 − γ · s_{t−1}) · (1 − ρ(a_t) · P_def,t)
```

`s_t` is the carried risk after turn `t`, `γ ∈ [0,1]` a per-turn relevance decay (`A10`: `γ = 0.85`), and `ρ(a_t)` the residual multiplier of the action actually taken. An ALLOWed risky turn contributes fully. A CONSTRAINed one contributes its residual. A BLOCKed one contributes nothing.

The decision function then uses an effective probability that includes carried context:

```
P_def,eff = 1 − (1 − P_def,t) · (1 − β · s_{t−1}),     A11: β = 0.5
```

Practical effect: three marginal turns that each individually clear the threshold will together push the fourth over it. **A conversation can be escalated even when no single turn deserved it**, which is exactly the compounding the brief describes.

**Consequence by reachability, for agents.** An agent step's consequence is not what it says, it is what it can cause.

```
C_eff(step) = max over reachable terminal actions  ( C(action) · P(reach) · ι(action) )
```

A retrieval step feeding only a summary carries low `C`. A reasoning step that can emit a refund API call carries the refund's consequence, even though it is only text. `P(reach)` comes from the agent's declared tool graph, which the enterprise already has because it wrote the agent.

Irreversibility `ι` matters most here. `A12`: `ι = 1.0` for payments and external communications, `0.6` for record writes with an undo path, `0.2` for drafts and internal recommendations. **A tool call that cannot be undone gets adjudicated at the terminal action's consequence, one step before it fires.**

### 3.7 Calibration, and why AUROC is the wrong metric

Thresholds in 3.2 are probabilities. A detector that ranks well but reports badly calibrated probabilities thresholds in the wrong place. AUROC is invariant to any monotone transform of the score, so it cannot tell you whether a threshold is safe.

```
ECE = Σ_b (n_b / N) · | acc(b) − conf(b) |
BS  = (1/N) Σ_i (p̂_i − y_i)²
```

A well-calibrated detector at AUROC 0.75 is more useful for routing than an overconfident one at AUROC 0.88. Calibration is fitted per workflow with isotonic regression on adjudicated ledger data, and refitted on model version change, because a provider swap invalidates calibration even when it improves the model.

Gate: `ECE < 0.05` per workflow before a policy may move from advisory to enforcing.

### 3.8 Detection methods by tag

Black box only. No weights, no activations, per the brief's API-consumption constraint.

**Performance**

- *Grounding check.* Decompose into atomic claims, run entailment against retrieved context. `G = supported claims / total claims`. Cheap where retrieval context already exists. Emits `verifiable = false` when context is absent, which is the 3.5 path.
- *Self-consistency / semantic entropy.* Sample `k = 5` generations, cluster by bidirectional entailment with a small NLI model, take entropy over meaning clusters rather than token strings: `H_sem = −Σ_c p(c) log p(c)`. High entropy with high stated confidence is the confidently-wrong signature. Tier 2 only, since it costs `k` extra generations.
- *Schema and format validation.* Deterministic, near-zero cost, near-perfect precision. Tier 0.

**Cost.** Deterministic accounting, no model calls.

- Rolling z-score on tokens per resolved task, `z = (x − μ_w)/σ_w`, EWMA for drift.
- Retry and loop detection in agent traces, flagging repeated near-identical tool calls.
- Model-tier mismatch: lightweight complexity classifier on the request versus the model tier serving it. A frontier model answering a routing question is a cost defect even when the answer is right.

**Responsibility**

- PII and PHI: regex plus NER plus checksum validation (Luhn, PAN and Aadhaar format checks). High precision, so this is the one family that earns BLOCK.
- Safety and toxicity classifiers: small model, Tier 1.
- Bias via counterfactual invariance. Perturb a protected attribute `a → a'`, regenerate, measure decision flip rate `CFR = (1/N) Σ 1[decision(x) ≠ decision(x')]`. Too expensive per response. **Runs as an offline sampled audit feeding policy tightening, not live routing.** A judge will ask how you check bias in 20 ms and the honest answer is that you do not.

### 3.9 The cascade, and its budget

```
E[Δt]   = Σ_i ( Π_{j<i} q_j ) · t_i
E[cost] = Σ_i ( Π_{j<i} q_j ) · c_i
```

`A13`, routing rates and per-tier costs (`c_i` as a fraction of one generation's cost):

| Tier | Contents | Fires on | `t_i` | `c_i` |
|---|---|---|---|---|
| 0 | Schema, regex, PII, token accounting, policy list | 100% | 12 ms | 0.001 |
| 1 | Small classifier: safety, grounding on existing context | 8% | 90 ms | 0.02 |
| 2 | LLM judge, self-consistency at k=5 | 1.5% | 450 ms | 0.35 |
| 3 | Human | 0.2% | out of band | n/a |

```
E[Δt]   = 12 + 0.08(90) + 0.015(450)       ≈ 26 ms
E[cost] = 0.001 + 0.08(0.02) + 0.015(0.35) ≈ 0.8% of inference spend
p50 ≈ 12 ms      p95 ≈ 102 ms      p99 ≈ 552 ms
```

Report the tails. The mean flatters the design and a judge who works in production will ask.

**Be honest about scale.** At 130,000 responses/month the average load is 0.05 requests per second and Tier 2 fires about 65 times per day. The cascade is not required at this volume, it is required for the brief's explicit ask that the design generalize for broader adoption. Say that rather than pretending 130k/month needs an optimised funnel.

Routing rates are per-workflow knobs, not global. Raising `q_1` from 8% to 20% adds about 11 ms to the mean and moves p95 materially, buying recall in the middle band. Decision support runs high `q_1`, the copilot runs low.

### 3.10 The streaming constraint

Displayed tokens cannot be retracted. That is a UI fact, not an engineering problem to solve. At 40 tokens/second:

```
Buffer of 8 tokens  →  200 ms added time-to-first-token
Full sentence (~25) →  625 ms added TTFT
```

| Mode | Mechanism | Suitable for | Cost |
|---|---|---|---|
| Gated | Full response withheld until decision | Agentic actions, tool calls, decision support | Loses streaming |
| Buffered | Rolling n-token buffer, decision on the buffer | Support chat, moderate TTFT budget | 200 to 600 ms TTFT |
| Monitored | Streams freely, interrupt mid-generation and annotate | Internal copilot | Partial output already visible |

The judge's question is whether the product still has a market once streaming workflows are excluded. **The constraint binds tightest where consequence is lowest and loosest where it is highest**, because agent output goes to an API rather than to a user's eyes. That structure is fortunate and worth saying out loud.

---

## 4. System Architecture

### 4.1 Block diagram

```
┌───────────┐   request    ┌────────────────────────────────────────┐
│ Enterprise│ ────────────▶│  ControlPlane Gateway (proxy / SDK)    │
│ application│◀────────────│  drop-in, OpenAI-compatible surface    │
└───────────┘   decision   └───────┬────────────────────────────────┘
                                   │ forwards
                                   ▼
                          ┌──────────────────┐
                          │  Any model API   │
                          └────────┬─────────┘
                                   │ response + usage metadata
                                   ▼
   ┌───────────────────────────────────────────────────────────┐
   │ SIGNAL LAYER (cascade, parallel within each tier)          │
   │  Tier 0 deterministic ─▶ Tier 1 classifier ─▶ Tier 2 judge │
   └───────────────┬───────────────────────────────────────────┘
                   │ per tag: (p̂_d, verifiable_d, measured precision_d)
                   ▼
   ┌───────────────────────────────────────────────────────────┐
   │ DECISION ENGINE                                            │
   │  overlap model (κ, λ) ─▶ session state (γ, β) ─▶ argmin L  │
   │  subject to severity ≤ severity_max(precision, verifiable) │
   │  policy inputs: C_w, ι, latency budget, mode, jurisdiction │
   └───────────────┬───────────────────────────────────────────┘
                   │ action + reason codes
                   ▼
   ┌────────────────────────┐        ┌──────────────────────────┐
   │ ACTUATOR               │───────▶│ DECISION LEDGER          │
   │ allow / hold /constrain│        │ append-only, hash-chained│
   │ escalate / block       │        │ every decision incl ALLOW│
   └───────┬────────────────┘        └────────────┬─────────────┘
           │                                       │ adjudicated labels
           ▼                                       ▼
   ┌────────────────┐                   ┌────────────────────────┐
   │ Human console  │──────────────────▶│ LEARNING LOOP (offline)│
   │ (escalations,  │   overrides       │ calibration, κ, λ,     │
   │  overrides)    │                   │ threshold proposals    │
   └────────────────┘                   └────────────────────────┘
                                                    │
                                                    ▼
                                        ┌────────────────────────┐
                                        │ POLICY STORE (versioned│
                                        │ per workflow × region) │
                                        └────────────────────────┘
```

### 4.2 Data flow

1. Application calls ControlPlane's endpoint instead of the provider's. Integration is a base URL change.
2. Gateway attaches workflow ID, session ID, and jurisdiction, resolves the policy snapshot.
3. Response returns with usage metadata. Tier 0 runs in-process inside 12 ms.
4. Routing to Tier 1 or 2 only if Tier 0 signals cross the workflow's routing thresholds.
5. Signal layer emits, for each tag, a probability, a verifiability flag, and the detector's **measured precision on that workflow's recent adjudicated data**. The precision figure is what bounds severity, so it is a runtime input, not a config constant.
6. Decision engine applies the overlap model, folds in session state, solves the constrained argmin, emits an action plus machine-readable reason codes.
7. Actuator executes. Ledger records every decision including ALLOWs, because a ledger of interventions only is not an audit trail.
8. Human adjudications and overrides flow back as labels, feeding recalibration, `κ` and `λ` re-estimation, and threshold proposals.

### 4.3 Governance and the policy layer

The brief asks for configurable behaviour by use case, geography, and risk appetite, and notes that rigid hard-coded rules age quickly. Policy is data, versioned in git, never code:

```yaml
workflow: decision_support_v3
jurisdiction: IN                 # selects the applicable rule pack
consequence:
  performance: 50000
  cost: 400
  responsibility: 50000
irreversibility: 0.9
latency_budget_ms: 2000
intervention_mode: gated
fail_mode: closed
required_tags: [pii, phi, policy_violation]
retention_days: 2555             # jurisdiction-driven
```

The engine reads an immutable snapshot per request, so every ledger entry is replayable against the exact policy that produced it. Regulation changes become a policy version bump plus a rule-pack update, not a code deploy.

### 4.4 Failure modes

| Dependency | Failure | Design response |
|---|---|---|
| Model provider API | Latency spike or outage | Signal-layer timeout defaults to the workflow's configured fail mode |
| Tier 2 judge | Outage or slow | Degrade to Tier 1, cap severity at CONSTRAIN, flag degraded mode in ledger |
| Retrieval context | Missing | `verifiable = false`, prior substituted, severity capped (3.5) |
| Human queue | Backlog | SLA breach triggers workflow fallback: auto-block for high `C`, auto-allow with ledger flag for low `C` |
| Policy store | Unreachable | Serve last known snapshot, alert. Never fail into no-policy |

**Fail-open versus fail-closed is per workflow, never global.** Decision support fails closed. The copilot fails open. Getting this wrong in either direction is how control layers get removed.

---

## 5. Implementation

### 5.1 Rollout

No workflow starts enforcing.

| Stage | What runs | Produces | Exit criterion |
|---|---|---|---|
| 1. Shadow | Full signal layer, decisions computed never executed | Base rates `π_w`, detector precision, `κ`, latency profile | 2 weeks or 50,000 responses, `ECE < 0.05` |
| 2. Advisory | Decisions surfaced, humans choose whether to act | Adjudicated labels, engine-human disagreement rate | Agreement > 85% on sampled review |
| 3. Enforcing | Actuator live, severity capped by measured precision | EDR reduction, UIR | Ongoing, automatic demotion to advisory if UIR breaches ceiling |

**This is the answer to "who writes the policies?"**, which the consequence matrix quietly hands to the customer. Nobody writes them from scratch. Shadow mode measures base rates and precision. The customer supplies `C_w` and `ι` per workflow, which are business estimates they can actually produce. Thresholds are derived from 3.2. Policy authoring is one business input plus arithmetic, not a config file with forty numbers.

### 5.2 Technology choices

| Component | Choice | Reasoning |
|---|---|---|
| Gateway | FastAPI for the prototype, Envoy or Rust proxy in production | OpenAI-compatible schema means no application rewrite |
| Tier 0 | Compiled regex (RE2), Presidio NER, in-process | No network hop. RE2 gives linear-time guarantees, no catastrophic backtracking on adversarial input |
| Tier 1 | Distilled encoder classifier ~100M params, CPU-quantised | 90 ms budget is achievable and it is small enough to fine-tune per tenant |
| Tier 2 | LLM judge, provider-agnostic, plus NLI model for entailment clustering | 1.5% of traffic, so the cost is affordable |
| Ledger | Append-only, hash-chained, WORM-backed object storage | Audit requirement is tamper evidence, not just retention |
| Policy store | Versioned, git-backed, immutable snapshot per request | Every ledger entry must be replayable against the policy that produced it |
| Calibration | Isotonic regression per workflow-detector pair, nightly | Non-parametric, handles non-monotone miscalibration that Platt scaling misses |

### 5.3 Performance considerations

- **Tier 0 must be in-process.** A network hop costs more than the entire Tier 0 budget. Single most important implementation constraint.
- **Parallel within a tier.** Tier latency is `max(t_detector)`, not the sum. The brief explicitly asks how checks run in parallel to protect latency, so this belongs on a slide.
- **Speculative Tier 1.** In gated mode, Tier 1 can start on partial output while generation continues, hiding most of its 90 ms. Only safe for prefix-stable checks, so PII and toxicity yes, grounding no.
- **Policy snapshot caching.** Resolving a policy must never touch a database. Snapshot in memory, invalidate on version bump.
- **Backpressure.** If Tier 2 saturates, shed to Tier 1 rather than queueing. A queued decision in a gated workflow is indistinguishable from an outage.

---

## 6. Prototype Specification

The brief wants a working demonstration of the core mechanism on simulated data, not production grade. **The core mechanism is the decision engine, not the detectors.** Detectors can be partly stubbed with injected ground truth, as long as the routing, overlap, abstention, and severity capping are real.

### 6.1 Scope

Three workflows matching the brief's own examples: support chatbot, internal knowledge copilot, regulated decision support. Simulated traffic, roughly 3,000 responses with labelled ground truth so precision and EDR are computable.

### 6.2 Build order

| # | Component | Proves | Effort |
|---|---|---|---|
| 1 | Policy store, three YAML workflows | Configurability by use case and geography | S |
| 2 | Decision engine: `L(a)`, derived thresholds, severity cap | The core mechanism | M |
| 3 | Ledger: append-only, hash-chained, reason codes | Audit trail behind every decision | S |
| 4 | Tier 0 detectors, real: regex, Presidio PII, schema, token z-score | High-precision path that earns BLOCK | M |
| 5 | Tier 1 and 2, real but small: toxicity classifier, NLI grounding, LLM judge | Cascade routing under a latency budget | M |
| 6 | Simulated traffic generator with labelled defects, including joint tags | Overlap model has something to chew on | M |
| 7 | Overlap model, `κ` and `λ` estimated from the ledger | The brief's categorization complexity | S |
| 8 | Abstention path: strip retrieval context from a slice | Behaviour with no ground truth | S |
| 9 | Session risk state over multi-turn transcripts | Compounding risk | M |
| 10 | Dashboard | Everything above, visible | M |

### 6.3 The demo, four screens

1. **Same response, three workflows.** One risky response, three verdicts (allow, escalate, block) with the arithmetic shown. This is the pitch in one screen.
2. **The threshold slider.** Drag a global threshold and watch EDR fall while UIR rises, live. Then switch to derived per-workflow thresholds and show both improving simultaneously. **This single interaction is the strongest thing in the prototype**, because it makes the brief's over-flagging tradeoff physical instead of rhetorical.
3. **Abstention.** Strip the retrieval context from a claim. Show the same input escalating in decision support and passing with a log in the copilot, with no special-case code.
4. **Compounding.** A four-turn conversation where every turn individually clears threshold and the session escalates at turn four.

Plus a ledger view, since the brief asks for a clear audit trail behind every decision, and runtime telemetry (latency per tier, model calls, token usage, estimated cost per decision).

### 6.4 What to stub, and say so

Tier 1 and Tier 2 detector quality is not what is being demonstrated, and pretending otherwise invites a fair attack. Where detector performance is simulated, the prototype should say so on screen and let the reviewer set TPR and FPR directly. **Being able to dial detector quality down and show the system degrading toward logging rather than breaking is a better demo than a detector that appears to work perfectly.**

---

## 7. Impact and Validation

### 7.1 KPIs

| KPI | Definition | Baseline | Target |
|---|---|---|---|
| Escaped Defect Rate | Defects becoming actions per 10,000 responses | 83.0 | < 25 |
| Unnecessary Intervention Rate | Interventions on responses later adjudicated fine, per 10,000 | n/a | < 30 |
| Abstention Rate | Responses with at least one unverifiable detector | n/a | Tracked, not targeted |
| p95 added latency | Gateway-measured, gated mode | n/a | < 120 ms |
| Control overhead | Control compute as % of inference spend | n/a | < 1.5% |
| Calibration error | ECE per workflow-detector pair | n/a | < 0.05 |
| Ledger completeness | Decisions recorded / responses served | n/a | 100% |
| Override rate | Human reversals of engine decisions | n/a | < 15%, trending down |

**EDR and UIR are a deliberate pair and must always be reported together.** Reporting either alone is how control products lie about themselves, since any team can drive EDR to zero by blocking everything. The brief asks how you would report trustworthiness to a skeptical stakeholder, and this pairing plus the ledger is the answer.

### 7.2 Projected impact

Reduction rates differ by workflow because thresholds do: decision support runs aggressive escalation at `p*_esc = 0.27%`, the copilot barely intervenes.

| Workflow | Before | Reduction | After | Delta |
|---|---|---|---|---|
| Support chatbot | ₹19.32 L | 65% | ₹6.76 L | ₹12.56 L |
| Internal copilot | ₹2.48 L | 55% | ₹1.12 L | ₹1.36 L |
| Decision support | ₹62.10 L | 80% | ₹12.42 L | ₹49.68 L |
| **Total** | **₹83.90 L** | | **₹20.30 L** | **₹63.60 L** |

```
Gross benefit                        ₹63.60 lakh / month
Unnecessary intervention cost        ₹0.78 lakh   (30/10k × 130k × ₹200)
Human escalation cost                ₹0.31 lakh   (0.2% × 130k × ₹120)
Control compute                      ₹0.02 lakh   (0.8% of inference spend)
                                     -------------------
Net                                  ₹62.50 lakh / month  ≈  ₹7.5 crore / year
```

State the sensitivity: the result is dominated by `A4`'s ₹50,000 decision-support consequence. At 5x lower it becomes roughly ₹19 lakh/month, still positive, no longer dramatic. Volunteering the weakest assumption is what makes the rest believable.

### 7.3 Validation design

| Method | Purpose | Design |
|---|---|---|
| Retrospective replay | Zero-risk first estimate | Signal layer over 90 days of logged traffic, decisions compared to known incidents |
| Shadow A/B | Measure without exposure | 100% shadow, decisions logged not executed, 2 weeks |
| Injected defect set | Recall on rare classes where natural base rates are too thin | 500 synthetic defects per tag, stratified by severity, blind-mixed into live traffic. Includes joint-tag defects to test `κ` |
| Human-adjudicated gold set | Ground truth for calibration and precision | N = 2,000 stratified, two independent annotators, Cohen's kappa reported |
| Interrupted time series | Post-deployment causal estimate | EDR before and after enforcement, shadow period as counterfactual |

**Named limitation:** at N = 2,000 and a 2% base rate you get about 40 positives, which is thin for estimating precision in the block-eligible band. Rare-class precision estimation is the real bottleneck on how fast a workflow reaches enforcing stage, and stratified oversampling only partly fixes it. Name this rather than hide it.

---

## 8. Business Proposal

### 8.1 Target users

| Buyer | Trigger | What they measure |
|---|---|---|
| Head of AI / platform engineering | Wants to ship AI into workflows that legal has blocked | Workflows cleared for production, p95 latency |
| Risk and compliance | Needs an exercisable control, not a dashboard, for audit | EDR, ledger completeness, override rate |
| CFO / FinOps | AI spend growing faster than AI value | Control overhead, cost-tag detections |

Entry point is almost always a single blocked high-consequence workflow, not a platform-wide rollout. Land there, expand by policy cloning.

### 8.2 Roadmap

| Phase | Duration | Deliverable | Gate |
|---|---|---|---|
| 0. Prototype | Now | Sections 6.2 and 6.3 on simulated traffic | Round 2 demo |
| 1. Design partner | 3 months | Gateway plus Tier 0 and 1, shadow mode on one real workflow | Measured base rates, ECE < 0.05 |
| 2. Advisory | 3 months | Human console, ledger, calibration loop | Engine-human agreement > 85% |
| 3. Enforcing | 3 months | Actuator live on the highest-`C` workflow | EDR reduction demonstrated, UIR under ceiling |
| 4. Multi-workflow | 6 months | Policy cloning, cross-workflow calibration transfer, jurisdiction rule packs | Third workflow onboarded in under 2 weeks |
| 5. Agentic | 6 months | Tool-graph reachability, session state at scale, pre-action gating on tool calls | Adjudicating trajectories, not responses |

### 8.3 Risks and mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Detector precision too low for any useful action | Medium | High | Severity capping (3.3). Degrades to logging, not to unsafe or unusable |
| Alert fatigue, customer disables the layer | Medium | High | UIR is a first-class KPI with an automatic demotion trigger. Enforcing is revocable per workflow |
| No ground truth available for a domain | High | Medium | Abstention path (3.5). Prior substituted, severity capped, abstention rate reported |
| Latency breaches workflow budget | Medium | Medium | Per-workflow routing rates. Shed to lower tier under load, never queue |
| Accountability when a block is wrong | High | Medium | ControlPlane owns correct execution and complete logging. Customer owns `C_w` and the policy. Ledger makes both auditable |
| Adversarial evasion of Tier 0 patterns | Medium | Medium | Tier 0 failure routes upward rather than passing. Deterministic checks are a floor, not a ceiling |
| Provider swap invalidates calibration | High | Medium | Version-pinned calibration, automatic demotion to advisory on detected version change |
| Regulation changes faster than the product | High | Medium | Policy as versioned data with jurisdiction rule packs, not hard-coded rules |
| Policy sprawl across many workflows | Medium | Medium | Policies derived from `C_w` and `ι` plus measured base rates, not hand-authored |

---

## 9. Objections, with answers

| Objection | Answer |
|---|---|
| Why can't NeMo Guardrails or Llama Guard already do this? | They classify, they do not decide. One global threshold into a binary action, no consequence model, no precision-bounded severity, no per-workflow calibration. The cascade is not the product, the decision function above it is |
| The brief lists "edit" as an option and you dropped it | Deliberate. Inline rewriting produces text no model generated and no human approved, presented as the model's answer. That is an audit problem in a regulated workflow. CONSTRAIN keeps the behaviour without the provenance liability |
| Who writes the policies? | Nobody from scratch. Shadow mode measures base rates and precision, the customer supplies `C_w` and `ι`, thresholds are derived (3.2, 5.1) |
| The categories overlap, so your dimensions are fiction | Correct, which is why they are non-exclusive tags with an estimated correlation `κ` and a discounted joint consequence `λ`, both fitted from ledger co-occurrence (3.4) |
| What do you do with no ground truth? | Substitute the workflow prior, cap severity, report abstention. The same input then escalates in decision support and passes in the copilot with no special-case code (3.5) |
| Multi-turn risk compounds and you adjudicate single responses | Not any more. Session risk state with decay, plus consequence assigned by tool-graph reachability for agents (3.6) |
| When a block is wrong, who owns it? | ControlPlane owns correct execution and complete logging. The customer owns the consequence model and policy. The layer does not absorb liability that previously sat with the model provider |
| What if the acceptable overhead is 50 ms? | Tier 0 at 12 ms fits. Tier 1 fits at reduced routing rate. Tier 2 moves out of the synchronous path, which caps severity at ESCALATE for that workflow. The concept survives, the operating point moves |
| What if the detector is mediocre? | Section 3.3. Severity is capped by measured precision, so weak detectors produce logs and holds rather than wrong blocks |
| Isn't this an LLM judge with extra steps? | A judge produces a score. This produces an action, under a latency budget, with a consequence model, an overlap model, and an audit record. The judge is one detector inside Tier 2 |
| At 130k responses/month you don't need a cascade | Correct at that volume. The cascade exists because the brief asks the design to generalize for broader adoption. Tier 2 fires 65 times a day here |

---

## 10. Deliberately deferred

- **Representation-level detection.** Removed, not deferred. The brief confirms API-level consumption, so model internals are out of reach by construction.
- **Learning `C_w` from realised outcomes.** Currently a business input. With enough adjudicated incidents it can be estimated from realised remediation costs, closing the loop. Phase 4.
- **Cross-workflow calibration transfer.** A detector calibrated on one workflow is a prior for a similar one, shortening the shadow period for workflow number twenty. Phase 4.
- **Cost-tag routing before generation.** If the layer detects model-tier mismatch after the fact, the next step is routing the request to a cheaper model before generation. Attractive, but it turns a control layer into a serving layer and changes the liability story. Deliberately out of scope for now.
