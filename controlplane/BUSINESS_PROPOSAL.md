# ControlPlane.ai

## Business Proposal, Accenture Innovation Challenge Round 2

**Track 1, ControlPlane.ai. A consequence-aware AI intervention layer.**

> **Placeholders.** Items marked `[DECIDE]` need a call from the team before
> submission. Everything else is either measured from the prototype or derived
> from a stated assumption, and every figure in the business case is reproducible
> from the repository.

---

## 1. The problem

An enterprise does not run one AI system. It runs several, and they are not
alike. A customer support assistant, an internal copilot, and a decision support
tool embedded in a regulated workflow differ by more than tone. They differ by
what a mistake costs.

Using this challenge's own reference parameters, a mid-sized enterprise running
roughly 130,000 AI interactions per month faces this:

| Workflow | Volume/month | Defect rate | Acted on | Cost per defect | Exposure/month |
| :--- | ---: | ---: | ---: | ---: | ---: |
| Support chatbot | 70,000 | 2.5% | 40% | ₹3,000 | ₹12,60,000 |
| Internal copilot | 45,000 | 3.0% | 25% | ₹800 | ₹54,000 |
| Decision support | 15,000 | 1.5% | 60% | ₹50,000 | ₹60,75,000 |
| **Total** | **130,000** | | | | **₹73,89,000** |

Sampled human review catches roughly 8% of this. Residual exposure is
**₹67,97,880 per month, about ₹8.2 crore per year**.

Note where the money is. Decision support is 11% of traffic and 82% of
exposure. The copilot is 35% of traffic and less than 1% of exposure.

### Why current approaches do not solve it

**A single global threshold cannot be right for both.** Set it where the copilot
is comfortable and decision support leaks. Set it where decision support is safe
and the copilot drowns in false alarms. Every team that ships a guardrail
discovers this and then tunes the threshold by hand, forever.

**Binary blocking destroys utility.** A pass or fail filter has one response to
uncertainty, and it is the most expensive one available.

**Post-hoc observability is structurally late.** The signal arrives after the
refund was issued or the claim was approved. Retraction costs more than
prevention.

**Overlapping risks resist clean categorisation.** A fabricated detail about a
named person is a hallucination and a privacy incident at the same time.
Counting it once under either heading understates it.

**No ground truth is available at request time.** The same knowledge gaps that
cause hallucination make automated verification hard. Systems that treat
"could not verify" as "verified fine" fail silently and confidently.

---

## 2. Solution design

ControlPlane sits between the model and anything that acts on its output. It
converts a model response from an artifact to observe into a **proposal to
adjudicate**.

### 2.1 The core mechanism

For every response, the engine estimates the probability it is defective and
what a defect would cost in this specific workflow, then selects the action
that minimises expected loss:

```
L(a) = ρ(a) · P_eff · C_eff · ι  +  F(a)  +  (1 − P_eff) · U(a)
       residual risk left behind    friction   utility destroyed
                                              by a false alarm
```

The action taken is `argmin L(a)` over five graded options, not two:

| Action | Meaning | Residual risk | Friction | Utility loss |
| :--- | :--- | ---: | ---: | ---: |
| ALLOW | deliver as-is | 1.0 | ₹0 | 0 |
| HOLD | deliver, queue for batch review | 0.5 | ₹5 | 20 |
| CONSTRAIN | re-prompt under a narrower contract | 0.3 | ₹15 | 80 |
| ESCALATE | route to a human before delivery | 0.1 | ₹120 | 40 |
| BLOCK | drop, return policy fallback | 0.0 | ₹50 | 200 |

**Thresholds are derived, not tuned.** Because the loss function is linear in
probability, each workflow's switching points fall out of its own consequence
model:

| Workflow | first HOLD | first CONSTRAIN | first ESCALATE | first BLOCK |
| :--- | ---: | ---: | ---: | ---: |
| Decision support | 0.0011 | never | 0.0075 | 0.0193 |
| Support chatbot | 0.0272 | 0.1667 | 0.2031 | 0.2647 |
| Internal copilot | 0.2500 | 0.7609 | never | 0.9226 |

Nobody chose those numbers. They are what the consequence model implies. The
copilot never escalates because a ₹120 human review does not pay against an
₹800 consequence, and that is the correct answer rather than a gap.

### 2.2 Four mechanisms that make it trustworthy

**Precision-bounded severity.** An expected-loss calculation will happily block
on a weak signal if the consequence is large enough. ControlPlane caps action
severity at what the detector's measured precision can support. A detector at
71% precision can demand a human but can never silence the model alone. When the
engine wants to block and the evidence will not support it, the record shows
both, and a reviewer can see the disagreement.

**Abstention instead of silence.** When there is no source to check a claim
against, the grounding detector reports `verifiable = false` and the engine
substitutes the workflow's own prior rather than zero. Not being able to check
something is not the same as it being fine. The same unverifiable input causes
decision support to intervene and the copilot to allow, with no branching on
workflow name anywhere in the code.

**Compounding across turns.** Risk allowed through at turn 2 contaminates the
context that turn 4 conditions on. Session risk carries and decays, so three
individually acceptable turns can together cross a threshold none of them
crossed alone.

**Consequence by reachability.** For agents, a step is worth what it can cause,
not what it says. A reasoning step wired to a refund API is adjudicated at the
refund's consequence even though it is only text. In the prototype the same
sentence is ALLOWed as a draft and escalated to a human when the step can reach
the refund tool.

### 2.3 Governance

Every decision is written to an append-only, hash-chained ledger, including the
ones that allowed. A ledger of interventions only is not an audit trail.
Verification recomputes each row's hash from its stored contents, so an edited
decision is caught rather than just a broken link.

Policy is YAML, versioned, validated at load time, and separate from code. Risk
appetite is set by the people accountable for it, not by whoever last touched
the detector.

**The calibration gate.** A policy may not move from advisory to enforcing until
its detectors are honest. Measured on held-out adjudicated data, the prototype's
detector reports a mean probability of 0.073 against a true base rate of 0.013,
roughly 5.6x overconfident, and Expected Calibration Error is 0.073 against a
gate of 0.05. **The system currently refuses to let itself enforce.** That is the
gate working, and it is the strongest evidence we can offer that the governance
layer is real rather than decorative.

---

## 3. Target users

`[DECIDE]` Confirm the beachhead segment before submission. The design assumes a
regulated Indian enterprise running several AI workloads, since the shipped
policies declare `jurisdiction: IN` and the bias vocabulary follows Articles 15
and 16. Financial services and insurance fit best: high consequence per defect,
existing model risk governance, and regulators who already expect an audit trail.

| Persona | What they need | What they get |
| :--- | :--- | :--- |
| **Economic buyer** `[DECIDE]` Head of AI Governance, CRO, or VP Platform | Evidence that AI exposure is bounded and auditable | Quantified residual exposure, and a gate that blocks unsafe rollout |
| **Platform engineering** | Something that drops in without rewriting applications | OpenAI-compatible proxy, one header selects the policy |
| **Risk and compliance** | Control over behaviour without filing an engineering ticket | Versioned YAML policy per workflow and jurisdiction |
| **Reviewers** | Few, high-value escalations rather than alert spam | Derived thresholds plus calibration cut unnecessary interventions by 98% |
| **Internal audit and regulators** | Proof of what was decided and why | Tamper-evident ledger with per-claim evidence and reason codes |

---

## 4. Business case

### 4.1 Value

Residual exposure today is ₹67,97,880 per month. Value depends on how much of
it ControlPlane catches, which is the honest uncertainty in this model:

| Catch rate | Avoided per month | Avoided per year |
| ---: | ---: | ---: |
| 40% | ₹27,19,152 | ₹3.26 crore |
| 60% | ₹40,78,728 | ₹4.89 crore |
| 75% | ₹50,98,410 | ₹6.12 crore |

We present a range rather than a single number because catch rate is a property
of the detectors, and detector quality is exactly what we refuse to assert
without measurement. Phase 0 of the roadmap exists to measure it.

### 4.2 Cost

Measured from the prototype, extrapolated to 130,000 interactions per month:

| Line | Uncalibrated | Calibrated |
| :--- | ---: | ---: |
| Interventions per month | 64,155 (49.4%) | 2,964 (2.3%) |
| Human escalations | 642 | 296 |
| Intervention friction | ₹5,22,863 | ₹57,798 |
| Inference overhead | ₹1,687 | ₹1,687 |
| **Total running cost** | **₹5,24,551** | **₹59,485** |

`[DECIDE]` Inference overhead assumes ₹0.40 per model generation. Adjust for
your actual model and token profile. It is 3.2% of one generation per decision,
measured, and is negligible either way.

**Calibration is a cost story as well as a safety story.** Correcting the
probability, without touching a single threshold, cuts running cost by roughly
9x. The dominant cost of a guardrail is not compute, it is the human time that
false alarms consume.

### 4.3 Return

| Catch rate | Avoided/month | Cost/month | Ratio |
| ---: | ---: | ---: | ---: |
| 40% | ₹27,19,152 | ₹59,485 | **45.7x** |
| 60% | ₹40,78,728 | ₹59,485 | **68.6x** |
| 75% | ₹50,98,410 | ₹59,485 | **85.7x** |

Even at the pessimistic end the layer returns more than forty times its running
cost, because the asymmetry it exploits is real: a ₹50,000 defect and a ₹5 hold
are four orders of magnitude apart.

`[DECIDE]` Pricing model. The economics above are the customer's operating
economics, not our revenue. Options: per-decision usage, platform subscription
tiered by workflow count, or value share against measured avoided exposure. Per
workflow subscription is the simplest to sell into an existing platform budget.

### 4.4 Non-financial value

- **Faster approval for new AI use cases.** The gate gives a risk committee a
  defensible answer to "how do you know this is safe enough to ship?"
- **Reduced reviewer attrition.** Alert fatigue is why guardrails get bypassed.
- **Regulatory readiness.** An immutable, queryable record of every decision and
  the evidence behind it.

---

## 5. Phased roadmap

`[DECIDE]` Calendar dates and staffing. Durations below are estimates for a
`[DECIDE: team size]` team.

### Phase 0, Shadow (weeks 1 to 4)

Deploy inline, adjudicate everything, **execute nothing**. Every decision is
logged with `shadow = true`.

- Measure real defect base rates per workflow, replacing assumption A2
- Measure detector precision on adjudicated samples
- Calibrate the consequence model with finance and risk, replacing A4
- Exit criterion: 500+ adjudicated decisions per workflow

Deliverable: the first honest measurement of AI exposure the organisation has
had. This phase has value even if the project stops here.

### Phase 1, Advisory (weeks 5 to 10)

Surface recommended actions to reviewers. Still no automatic enforcement.

- Fit and validate calibration on held-out data
- Tune the consequence model against reviewer disagreement
- Exit criterion: **held-out ECE below 0.05** and reviewer override rate stable

This is the gate. A workflow that cannot pass it does not proceed, and the
prototype demonstrates the gate refusing.

### Phase 2, Enforcing on one workflow (weeks 11 to 16)

Turn on enforcement for the highest-consequence workflow only, which is where
the value is concentrated.

- Start with ESCALATE and CONSTRAIN enabled, BLOCK disabled
- Enable BLOCK only for checksum-verified detectors such as PII
- Exit criterion: measured EDR and UIR both inside agreed bounds for 4 weeks

### Phase 3, Fleet rollout (months 5 to 8)

Extend to remaining workflows. Each gets its own policy, its own calibration,
and its own gate. Add jurisdiction variants as the footprint expands.

### Phase 4, Agentic coverage (months 9 to 12)

Extend reachability adjudication to production tool graphs, so agent steps are
governed by what they can cause. The mechanism is built and tested; this phase
is integration with real tool registries.

---

## 6. Key risks and mitigations

| Risk | Why it matters | Mitigation |
| :--- | :--- | :--- |
| **Detectors are not good enough** | The whole layer rests on the probability being meaningful | The calibration gate blocks enforcement until ECE is under 0.05. Severity caps mean a weak detector degrades into logging, never into wrong blocks. Both are built and demonstrable |
| **Alert fatigue drives bypass** | The historical failure mode of every guardrail | Derived per-workflow thresholds plus applied calibration cut unnecessary interventions by 98% in measurement. Reviewers see a small, high-value queue |
| **Consequence estimates are wrong** | Thresholds are derived from them, so errors propagate | Consequence is policy, versioned and owned by risk rather than engineering. Phase 0 calibrates it against real incidents before anything enforces |
| **Latency budget breach** | A gate that slows the product gets removed | Tiered cascade with modelled p50 of 102ms and p99 of 552ms. Tier 2 is skipped when the budget is nearly spent. Per-detector timeouts are `[NOT BUILT]`, see section 7 |
| **Model or vendor changes underneath** | Recalibrates every base rate silently | Continuous adjudication sampling. A drift in measured ECE reopens the gate and returns the policy to advisory |
| **Regulatory divergence by geography** | Rigid rules age quickly | Jurisdiction is a policy field. `[NOT BUILT]` It is validated but not yet consumed by the engine, see section 7 |
| **Over-reliance on the layer** | Teams stop thinking about safety because a system is watching | Ledger and metrics are deliberately visible. EDR and UIR are always reported together so neither can be optimised alone |
| **Prototype to production gap** | Simulated components create false confidence | Every simulated component is labelled as simulated in the UI and in the docs. Section 7 lists what is not built |

---

## 7. What is built, and what is not

Stating this plainly is a deliberate choice. A reviewer who discovers an
unimplemented feature themselves discounts everything else in the proposal.

### Built and demonstrable

Decision engine and derived thresholds. Precision-bounded severity caps.
Abstention with prior substitution. Multi-turn compounding. Agentic reachability.
Real natural language inference grounding, claim by claim, that names the
offending sentence. Protected-attribute and counterfactual bias detection.
Hash-chained tamper-evident ledger with concurrency-safe appends. Human
adjudication feedback loop. Applied isotonic calibration with a held-out enforcing
gate. OpenAI-compatible proxy. Seven demo screens, 221 automated tests.

### Deliberately not built

Inline rewriting of responses, representation-level detection which the API
consumption model puts out of reach, streaming, authentication, and
multi-tenancy.

### Not yet built

`fail_mode` open and closed behaviour is validated but not consumed.
Per-detector timeouts do not exist. Policy `routing` fractions are declared but
not used as gates. Tier 2 cost accounting understates self-consistency. Tier 1
and tier 2 judgement detectors are dial-controlled simulations, deliberately, so
that detector quality is a known quantity in the threshold measurements.

---

## 8. Why this wins

Most responses to this brief will build a better classifier. The detection
problem is genuinely hard and genuinely crowded, and a marginally better
hallucination detector does not change how an enterprise governs AI.

ControlPlane treats detection as an input and solves the layer above it: given
an imperfect signal, what is the right thing to do about it, in this workflow,
at this cost, with this quality of evidence? That layer does not exist in the
market, it is where the money actually is, and it keeps working as detectors
improve.

The clearest evidence that the mechanism is real is that it caught a flaw in its
own detector and refused to let itself go live.

---

## Appendix A, Assumptions

| ID | Parameter | Value | Source |
| :--- | :--- | :--- | :--- |
| A1 | Monthly volume | 130,000 | Challenge reference parameters |
| A2 | Defect rates | 2.5%, 3.0%, 1.5% | Assumption, measured in Phase 0 |
| A3 | Action conversion | 40%, 25%, 60% | Assumption |
| A4 | Consequence per defect | ₹3,000 / ₹800 / ₹50,000 | Assumption, calibrated in Phase 0 |
| A5 | Post-hoc review catch rate | 8% | Industry range for sampled review |
| A6 | Intervention economics | U=200, F_b=50, H=120 | Assumption |
| A6a | Escalation utility loss | 40 | Corrected: review delays, a block destroys |
| A10, A11 | Session decay, coupling | 0.85, 0.50 | Assumption |
| A12 | Irreversibility | 0.2 / 0.6 / 0.9 | Assumption |

Measured from the prototype, not assumed: p50 and p99 latency, inference
overhead per decision, tier fire rates, intervention rates before and after
calibration, ECE before and after correction, and all derived action bands.

## Appendix B, Reproducing the business case

```bash
pip install -r requirements.txt
pytest -q                      # 221 tests
python -m sim.seed_data        # 3,000 decisions, 20% audit sample
uvicorn controlplane.api:app --port 8000
```

Then `GET /v1/metrics` for cost and latency, and `GET /demo/screen5` for the
calibration figures used in section 4.2.
