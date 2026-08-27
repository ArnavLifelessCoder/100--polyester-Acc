# ControlPlane.ai

Consequence-Aware AI Intervention Layer for Enterprise Deployments.

ControlPlane converts LLM outputs from artifacts to observe into proposals to adjudicate. Every response passes through a consequence-aware decision function that selects an optimal action from a graded 5-tier spectrum before the output can produce an enterprise outcome.

**Documentation**

- [ARCHITECTURE.md](ARCHITECTURE.md): decision arithmetic, severity ladder,
  abstention, ledger integrity, and an explicit list of what is not implemented
- [API_REFERENCE.md](API_REFERENCE.md): every endpoint, with payloads captured
  from a running instance

---

## Quick Start

```bash
# 1. Install dependencies and run the suite (189 tests)
pip install -r requirements.txt
pytest -q

# 2. Seed the ledger with 3,000 adjudicated interactions and a 20% audit sample
python -m sim.seed_data

# 3. Start the gateway. It serves the built dashboard at the same origin.
uvicorn controlplane.api:app --host 127.0.0.1 --port 8000
```

Open `http://localhost:8000` and start at **Screen 0**.

For dashboard development with hot reload, run `cd dashboard && npm install &&
npm run dev` in a second terminal and use `http://localhost:5173`.

The first run downloads the NLI grounding model (~70MB) and caches it. To skip
it and use the lexical fallback, set `CONTROLPLANE_DISABLE_NLI=1`.

**Optional, for a live model.** Screen 0 replays recorded responses unless a
provider is configured, and labels which it used either way:

```bash
export CONTROLPLANE_API_KEY=sk-...       # or OPENAI_API_KEY
export CONTROLPLANE_MODEL=gpt-4o-mini    # optional
export CONTROLPLANE_BASE_URL=...         # optional, any OpenAI-compatible endpoint
```

---

## Core Problem and Value Proposition

Enterprise LLM deployments fail when confident but defective outputs reach an external user or action API before verification. Post-hoc observability is fundamentally late:
- Signal arrives after the enterprise outcome occurred. Retraction carries brand and financial damage.
- Sampled human review (1% to 5%) misses rare high-consequence edge cases.
- Traditional guardrails use binary pass/fail filters with static global thresholds, forcing a destructive tradeoff between high false alarms (unnecessary friction) and escaped defects (liability).

ControlPlane solves this by:
1. **Graded Action Spectrum:** Five distinct actions (ALLOW, HOLD, CONSTRAIN, ESCALATE, BLOCK) replace blunt binary blocking.
2. **Constrained Expected Loss Minimisation:** Derived per-workflow thresholds calibrate interventions against financial liability, reversibility, and detector precision.
3. **Abstention Substitution:** Replaces ungrounded claims with shadow-mode empirical priors without hardcoded branching.
4. **Multi-Turn Session Compounding:** Tracks context risk drift across conversation turns.
5. **Cryptographic Audit Ledger:** SHA-256 hash-chained immutable record of all decisions, including clean passes.

---

## The 5-Action Spectrum

| Action | Meaning | Operational Mechanism | Residual Risk $\rho(a)$ | Friction $F(a)$ | Utility Loss $U(a)$ |
| :--- | :--- | :--- | :---: | :---: | :---: |
| **ALLOW** | Clean Passthrough | Immediate delivery to user or execution tool | 1.00 | INR 0 | 0 |
| **HOLD** | Async Quarantine | Release with soft flag or secondary queue for batch review | 0.50 | INR 5 | 20 |
| **CONSTRAIN** | Capability Strip | Redact PII, strip dangerous tool permissions, enforce schema | 0.30 | INR 15 | 80 |
| **ESCALATE** | Synchronous Review | Route interaction to human supervisor with SLA | 0.10 | INR 120 | 40 |
| **BLOCK** | Circuit Break | Drop candidate response, return policy fallback | 0.00 | INR 50 | 200 |


Escalation carries a utility loss of 40 against blocking's 200 because review
delays a response while a block destroys it. Setting them equal, as an earlier
version did, makes

    L(ESCALATE) - L(BLOCK) = 0.1 * p * C * iota + 70

positive for every p, so BLOCK dominates ESCALATE unconditionally and the
argmin can never route to a human. Escalation must cost less utility than a
block or the human-review tier is decorative.

### Action thresholds

The switching points below are the engine's own, derived from the same L(a) it
minimises. The annex closed forms `p*_esc = H/(a_h*C)` and
`p*_block = (F_b+U)/(C+U)` omit both iota and the utility-loss term, so they do
not predict what the engine does and are kept only as reference. For
support_chatbot the closed form puts the block point at 0.078 where the engine
actually blocks at 0.265.

| Workflow | first HOLD | first CONSTRAIN | first ESCALATE | first BLOCK |
| :--- | ---: | ---: | ---: | ---: |
| decision_support | 0.0011 | never | 0.0075 | 0.0193 |
| support_chatbot | 0.0272 | 0.1667 | 0.2031 | 0.2647 |
| internal_copilot | 0.2500 | 0.7609 | never | 0.9226 |

internal_copilot never escalates at any p. A 120-unit human review does not pay
against an 800-unit consequence discounted by iota=0.2, so the copilot
constrains instead. That is the consequence model working, not a gap.

Run `python -c "from controlplane.engine.thresholds import action_thresholds"`
against a policy to regenerate this table; `tests/test_action_spectrum.py`
asserts the engine agrees with it.


### Metrics and the calibration gate

`GET /v1/metrics` separates two things that used to be mixed:

- `traffic` is everything the engine did: action mix, tier fire rates,
  abstention rate, cap bind rate, latency percentiles, cost per decision.
  Always available.
- `quality` is whether it was right: EDR, UIR, override rate. These need human
  labels and are `null` until decisions have been adjudicated. An unlabelled
  system does not have an EDR of zero, it has an unknown EDR, and reporting the
  former claims a perfect record on no evidence.

EDR is escaped defects per 10,000 (truly defective, allowed through). UIR is
unnecessary interventions per 10,000 (truly clean, intervened on). Neither is
ever returned without the other.

Latency is modelled from the annex tier budgets, not wall clock. Wall clock on
in-process stub detectors reads about 0.05ms and is not a number anyone can
plan capacity from; the modelled figure is on `latency_source`.

`GET /v1/calibration` scores the reported probabilities against human labels
and reports ECE, Brier, and what an isotonic fit would reduce them to. A policy
may not move from advisory to enforcing until ECE is under 0.05. On the seeded
ledger it currently reads:

| Metric | Whole set (`/v1/calibration`) | Held out (`/demo/screen5`) |
| :--- | ---: | ---: |
| ECE, as reported | 0.0733 | 0.0726 |
| ECE, after isotonic | 0.000 | 0.0005 |
| Brier, as reported | 0.0283 | 0.0249 |
| Base rate | 0.013 | 0.013 |
| Mean reported probability | 0.0864 | 0.0726 |
| Passes enforcing gate | **no** | **no** |

Two columns because they answer different questions. `/v1/calibration` scores
the whole labelled set, so its post-isotonic ECE is near zero by construction
and is a diagnostic only. `/demo/screen5` fits on a training split and scores on
data the map has never seen, which is the number worth quoting.

The detector reports a mean probability around 5.6 times the true base rate.
Under a 50,000 consequence that overconfidence is enough to hold traffic that
should pass, which is exactly what the unnecessary intervention rate shows. The
gate is doing its job by refusing to let this policy enforce.

### Agentic consequence

An agent step is adjudicated at the consequence of what it can reach, not what
it says. Pass a `tool_graph` and a `step` to `POST /v1/adjudicate` and the
reachable terminal actions override the policy consequence:

    C_eff(step) = max over reachable terminals of C(tool) * P(reach) * iota(tool)

The same copilot text that is ALLOWed on its own becomes a BLOCK when the step
can reach a refund API, because the consequence in play is the refund's.

### Feedback loop

`POST /v1/decisions/{id}/adjudicate` records a human verdict. Verdicts live in
their own table: a decision row is append-only and hash-chained, so a label
must never modify the record it refers to. `python -m sim.seed_data` writes a
20% random audit sample so a fresh install has something for EDR, UIR and
calibration to read. The sample is random rather than "everything we flagged",
because labelling only interventions leaves escaped defects permanently
invisible and biases the calibration fit toward the flagged tail.


## 3-Tier Detection Cascade

Detectors run in tiered stages so that expensive judgement is spent only where a
cheap signal already justifies it.

```
                      ┌───────────────────────────┐
                      │  Candidate model output   │
                      └─────────────┬─────────────┘
                                    ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│ Tier 0: deterministic, in-process (12ms modelled, 100% of traffic)            │
│ PII regex + Luhn/PAN/Aadhaar, JSON schema, token z-score, deny list,          │
│ protected-attribute conditioning                                              │
└───────────────────────────────────┬───────────────────────────────────────────┘
                                    ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│ Tier 1 VERIFICATION: NLI grounding (90ms modelled, 100% of traffic)           │
│ Claim-by-claim entailment against the retrieved source. Always runs.          │
└───────────────────────────────────┬───────────────────────────────────────────┘
                            max p_hat >= 0.20
                                    ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│ Tier 1 JUDGEMENT: toxicity (gated)                                            │
└───────────────────────────────────┬───────────────────────────────────────────┘
                            max p_hat >= 0.35
                                    ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│ Tier 2: LLM judge, self-consistency, counterfactual bias (450ms, ~9%)         │
└───────────────────────────────────┬───────────────────────────────────────────┘
                                    ▼
                      ┌───────────────────────────┐
                      │   RiskVector -> decide()  │
                      └───────────────────────────┘
```

**Verification always runs; only judgement is gated.** Putting grounding behind a
tier 0 score means only claims that already look suspicious get checked against
a source, which is backwards. It is also the abstention entry point, so gating
it removes the system's ability to notice it cannot verify something.

Latencies are the modelled annex tier budgets, not wall clock. See
[ARCHITECTURE.md](ARCHITECTURE.md) section 1.1 for why `q1` and `q2` are not
used as gates.

---

### What actually detects, and what is simulated

Say this plainly, because a reviewer will ask.

| Detector | Tier | Real? | Precision |
| :--- | :--- | :--- | ---: |
| PII (regex + Luhn + PAN + Aadhaar) | 0 | real, deterministic | 0.97 / 0.72 |
| Schema contract | 0 | real, deterministic | 0.99 |
| Policy deny list | 0 | real, deterministic | 0.95 |
| Token anomaly (rolling z-score) | 0 | real, deterministic | 0.85 |
| Protected attribute conditioning | 0 | real, deterministic | 0.71 |
| Grounding (entailment) | 1 | **real model**, `cross-encoder/nli-deberta-v3-xsmall` | 0.82 |
| Toxicity | 1 | simulated | dial |
| Self-consistency, LLM judge | 2 | simulated | dial |
| Counterfactual bias | 2 | **real**, needs a model provider | 0.88 |

Every simulated component is labelled as simulated in the UI. Tier 1 and 2
judgement detectors are dialled rather than trained on purpose: the thesis is
about the decision arithmetic, and a detector whose TPR and FPR are known
quantities is what makes the threshold study on screen 2 measurable at all.

### Hallucination detection

`GroundingDetector` splits a response into claims and runs natural language
inference against the retrieved source, one claim at a time. Three outcomes per
claim, and the difference matters:

- **entailed** the source supports it
- **contradicted** the source refutes it. Weighted more heavily, and one refuted
  claim raises the floor on the whole response
- **unsupported** the source is silent. The claim may be true; nothing here can
  establish that

The evidence names the offending sentence, which is what makes it actionable. A
score alone tells a reviewer something is wrong somewhere in a paragraph.

With no retrieval context, or with no model loaded, the detector abstains
(`verifiable=False`) and the engine substitutes the workflow prior. A verifier
that could not run has not verified anything.

### Bias detection

The brief names bias first, and separately notes that enterprises consume models
through an API, which puts weights and activations out of reach. Every
representation-level fairness method assumes access this deployment does not
have, so both detectors work from the outside.

**Protected attribute conditioning** (tier 0) flags a decision made next to a
protected attribute. Categories follow the Indian constitutional grounds
(Articles 15 and 16) plus the usual lending and employment grounds, because the
shipped policies declare jurisdiction IN. Caste and religion matter here in a
way a US or EU list would miss.

Negated mentions are suppressed: "we never consider religion when we approve an
application" describes a safeguard, not a bias, and flagging it teaches
reviewers to ignore the detector. Bare pronouns are excluded from the gender
vocabulary for the same reason, since they appear in almost any sentence about a
person.

Precision is 0.71, which by the severity ladder means this detector can demand a
human but can never silence the model on its own. That is deliberate.

**Counterfactual invariance** (tier 2) asks the harder question: would the model
have answered differently if the protected attribute changed and nothing else?
It rewrites the request swapping the attribute within its category, regenerates,
and compares answers by embedding cosine distance so that harmless rewording
does not register while a reversed recommendation does. It costs one model call
per variant, so it sits behind the tier 2 gate, and it abstains when it has no
way to generate the variants.

### Live model

Set `CONTROLPLANE_API_KEY` (or `OPENAI_API_KEY`) and optionally
`CONTROLPLANE_MODEL` and `CONTROLPLANE_BASE_URL` for any OpenAI-compatible
endpoint. Screen 0 then generates a real answer and adjudicates it. With no key
it replays a recorded answer and says so, in the payload and on screen. A custom
typed question with no provider is refused rather than answered from a
recording.

---

## Repository Structure

```
controlplane/
├── constants.py                       # Annex assumption-tagged parameters (A1-A13, A6a)
├── requirements.txt
├── controlplane.db                    # SQLite ledger, WAL mode
├── policies/
│   ├── decision_support.yaml          # High consequence (INR 50,000, iota 0.9)
│   ├── support_chatbot.yaml           # Medium consequence (INR 3,000, iota 0.6)
│   └── internal_copilot.yaml          # Low consequence (INR 800, iota 0.2)
├── controlplane/
│   ├── schemas.py                     # Pydantic v2 core models
│   ├── policy.py                      # Loader, validation, immutable snapshots
│   ├── cascade.py                     # Tier routing, latency and cost accounting
│   ├── ledger.py                      # Hash-chained audit ledger + labels table
│   ├── calibration.py                 # ECE, Brier, isotonic fit, kappa estimation
│   ├── providers.py                   # Model provider adapter (OpenAI-compatible)
│   ├── api.py                         # FastAPI app, proxy, demo and admin endpoints
│   ├── engine/
│   │   ├── overlap.py                 # P_def and C_eff joint risk aggregation
│   │   ├── thresholds.py              # Exact action bands from the engine's own L(a)
│   │   ├── severity.py                # Precision-bounded severity ladder
│   │   ├── session.py                 # Multi-turn compounding state
│   │   ├── reachability.py            # Agentic tool-graph consequence
│   │   └── decide.py                  # argmin L(a), the entry point
│   └── detectors/
│       ├── base.py                    # Detector protocol
│       ├── nli.py                     # Shared entailment model loading
│       ├── tier0.py                   # PII, schema, token anomaly, deny list
│       ├── tier1.py                   # NLI grounding with abstention, toxicity
│       ├── tier2.py                   # Self-consistency, LLM judge
│       ├── bias.py                    # Protected attribute + counterfactual bias
│       └── simulated.py               # TPR/FPR dial detector
├── sim/
│   ├── generator.py                   # 3,000 labelled responses, context-paired
│   ├── scenarios.py                   # CLI scenario runner
│   └── seed_data.py                   # Ledger seeding + 20% audit sample
├── dashboard/src/components/
│   ├── Screen0LiveCatch.tsx           # The catch: real model, real hallucination
│   ├── Screen1Verdicts.tsx            # Same response, three verdicts
│   ├── Screen2ThresholdSlider.tsx     # Global vs derived frontier
│   ├── Screen3Abstention.tsx          # Grounding abstention
│   ├── Screen4CompoundingDial.tsx     # Session carry + detector dial
│   ├── LedgerView.tsx                 # Audit ledger inspector
│   ├── LivePlayground.tsx             # Free-form adjudication console
│   ├── TelemetryStrip.tsx             # Traffic and quality banner
│   ├── LandingPage.tsx
│   └── Sidebar.tsx
└── tests/
    ├── test_decide_golden.py          # The golden decision, section 7
    ├── test_action_spectrum.py        # No action dominated; bands match the engine
    ├── test_demo_screens.py           # Each screen still demonstrates its claim
    ├── test_real_detectors.py         # NLI grounding, both bias detectors, live catch
    ├── test_feedback_loop.py          # Labels, metrics, calibration, reachability
    ├── test_ledger.py                 # Tamper detection per column, concurrency
    └── ...                            # overlap, thresholds, severity, session, abstention
```

---

## Interactive Dashboard Screens

0. **Screen 0: The Catch**
   A model answers a question it tends to get wrong. The answer is checked claim
   by claim against the source by a real entailment model, and screened for
   decisions conditioned on protected attributes. The failing sentence is named.
   With a provider configured this is a live generation; without one it replays a
   recorded answer and **says so on screen**. A typed custom question with no
   provider is refused rather than answered from a recording.

1. **Screen 1: Three Verdicts**
   One risk vector, produced once by the real cascade, adjudicated under all
   three policies. The detector output is identical across columns; only the
   consequence model varies. Current verdicts: `ESCALATE` for decision support
   (the engine wanted BLOCK, the precision cap refused), `HOLD` for the support
   chatbot, `ALLOW` for the copilot.

2. **Screen 2: Threshold Frontier**
   EDR against UIR over the 3,000-response labelled set, using P_def as the real
   cascade computed it and the action the real engine chose.

   Read the per-workflow table, not the aggregate. At matched EDR, derived
   thresholds **reallocate** friction: the copilot's unnecessary interventions
   fall, decision support's rise. Aggregate EDR and UIR cannot show this, because
   both count a copilot defect and a decision-support defect as one defect each,
   which is exactly the assumption the consequence model exists to reject. The
   endpoint returns `finding` and `caveat` fields stating this.

3. **Screen 3: The Abstention Path**
   The same claim with and without retrieval context. Without it the grounding
   detector emits `verifiable=false`, the engine substitutes the workflow prior
   $\pi_w$ rather than zero, and the cap drops to CONSTRAIN. Decision support
   intervenes; the copilot allows. Same input, no branching on workflow name.

4. **Screen 4: Compounding and the Detector Dial**
   Two tracks with per-turn `P_def` held constant, so any change in action comes
   purely from carried session risk:

   ```
   support_chatbot   ALLOW, ALLOW, HOLD, HOLD          crossing at turn 3
   decision_support  HOLD,  HOLD,  ESCALATE, ESCALATE  crossing at turn 3
   ```

   Plus TPR and FPR sliders showing severity degrade as detector quality drops.

5. **Screen 5: Calibration and the Enforcing Gate**
   Everything the engine does rests on P_def being an honest probability. This
   screen measures whether it is, and shows what correcting it does.

   A reliability diagram plots what the detector claimed against what actually
   happened. Points above the diagonal mean it claimed more risk than the data
   contained, and that is what buys unnecessary interventions.

   On the seeded ledger, 614 adjudicated decisions are split 430 train and 184
   held out. On the held-out split the detector reports a mean probability of
   0.073 against a base rate of 0.013, roughly 5.6x overconfident, and ECE is
   0.073 against a gate of 0.05. The policy is therefore **not permitted to
   enforce**.

   Applying the correction takes held-out ECE to 0.0005 and removes about 98%
   of unnecessary interventions, 4,805 to 114 per 10,000, at the cost of one
   escaped defect in 614. Per workflow:

   | Workflow | UIR before | UIR after |
   | :--- | ---: | ---: |
   | decision_support | 10,000 | 179 |
   | support_chatbot | 6,146 | 135 |
   | internal_copilot | 588 | 54 |

   The thresholds never move. Moving them to compensate for an overconfident
   detector would break the consequence model that derives them. The input is
   what is wrong, so the input is what gets fixed.

6. **Screen 6: Agentic Consequence**
   The same sentence adjudicated three ways: as plain text, as a step that can
   reach a CRM note, and as a step that can reach a refund API. P_def is
   identical in all three. Only what the step can reach changes, and that alone
   takes the response from ALLOW to a human review.

7. **Cryptographic Audit Ledger**
   Immutable decision records with SHA-256 chaining and full evidence payloads.
   Verification recomputes each row hash from its stored content, so an edited
   decision is caught, not just a broken link.

---

## Verification

```bash
python -m pytest -q
```

Expected: `189 passed`, in roughly 40 seconds. The first run downloads the NLI
model (~70MB); subsequent runs use the cache. Set `CONTROLPLANE_DISABLE_NLI=1`
to skip it and exercise the lexical fallback instead.

The suite asserts every golden vector in the annex, plus the claims each demo
screen exists to make. A screen that runs without error but no longer
demonstrates its point fails the suite rather than the pitch.
