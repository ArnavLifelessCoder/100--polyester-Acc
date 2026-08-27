# ControlPlane.ai - Build Guide

Implementation spec for a coding agent. Read this file completely before writing any code. The design rationale lives in `controlplane_round2_annex.md`; this file is the contract. Where they disagree, this file wins for implementation details and the annex wins for intent.

**What you are building:** a working prototype of a consequence-aware AI intervention layer. The core mechanism is the decision engine, not the detectors. Detector quality is explicitly simulatable. Do not spend effort making detectors good; spend it making the decision arithmetic correct, visible, and demonstrable.

---

## 0. Rules for the agent

1. **Test as you write.** Every module in section 8 has an acceptance test listed with it. Write the test in the same commit as the module and run it before moving on. Do not batch testing to the end.
2. **The golden vectors in section 7 are non-negotiable.** If your implementation disagrees with them, your implementation is wrong. Do not adjust the vectors.
3. **No hidden magic numbers.** Every constant lives in a policy YAML or in `constants.py` with a comment naming its assumption ID from the annex (`A6`, `A8`, and so on).
4. **Commits:** do not add yourself, Claude, Gemini, or any AI tool as author, co-author, or contributor. No AI attribution in commit messages, code comments, README, or PR bodies. Write commit messages in plain imperative present tense.
5. **Docs and UI copy:** no em-dashes. Plain sentences.
6. **Fail loudly in the engine, gracefully at the edges.** An invalid policy should raise at load time. A detector timeout should degrade per section 5.4, never silently return zero.
7. **If a spec here is ambiguous, stop and ask** rather than guessing. Guessed semantics in the decision engine are worse than a delay.
8. **Determinism.** Seed every random source. The demo must produce identical output on repeat runs.

---

## 1. Stack

| Layer | Choice | Notes |
|---|---|---|
| Language | Python 3.11 | Type hints everywhere, `from __future__ import annotations` |
| API | FastAPI + uvicorn | This is the product surface, an OpenAI-compatible proxy |
| Models | Pydantic v2 | All schemas in section 3 are pydantic models |
| Ledger | SQLite via `sqlite3`, WAL mode | Append-only by convention plus a hash chain |
| Numerics | numpy | No pandas in the engine, pandas is fine in analysis scripts |
| PII | `presidio-analyzer` if it installs cleanly, else regex-only fallback | Do not block the build on presidio |
| NLI / classifier | `transformers` with small models, or stubs | Optional, see 5.5 |
| Dashboard | Vite + React + TypeScript + Tailwind + Recharts | Separate `dashboard/` folder, talks to the API over HTTP |
| Tests | pytest | `pytest -q` must pass at every commit |
| Config | PyYAML | Policies are YAML, never Python |

**Fallback if time is short:** replace the React dashboard with Streamlit in `dashboard_st.py`. Everything else stays. Do not degrade the engine to save time.

---

## 2. Repo layout

```
controlplane/
  README.md
  requirements.txt
  pyproject.toml
  constants.py                  # assumption-tagged defaults
  policies/
    support_chatbot.yaml
    internal_copilot.yaml
    decision_support.yaml
  controlplane/
    __init__.py
    schemas.py                  # section 3
    policy.py                   # loader, validation, immutable snapshots
    engine/
      __init__.py
      overlap.py                # P_def, C_eff
      thresholds.py             # p*_esc, p*_block, derived reference values
      severity.py               # severity ladder and caps
      session.py                # session risk state
      reachability.py           # agentic consequence
      decide.py                 # argmin L(a), the entry point
    detectors/
      __init__.py
      base.py                   # Detector protocol
      tier0.py                  # regex, PII, schema, token z-score
      tier1.py                  # toxicity, grounding
      tier2.py                  # LLM judge, self-consistency
      simulated.py              # dial-controlled detector, section 5.5
    cascade.py                  # routing, timing, budget accounting
    ledger.py                   # append-only hash-chained store
    calibration.py              # isotonic fit, ECE, kappa/lambda estimation
    api.py                      # FastAPI app
  sim/
    generator.py                # labelled traffic
    scenarios.py                # the four demo scenarios
    seed_data.py                # CLI: writes sim traffic + runs it through the engine
  tests/
    test_overlap.py
    test_thresholds.py
    test_decide_golden.py
    test_session.py
    test_severity.py
    test_ledger.py
    test_abstention.py
    test_cascade_budget.py
    test_end_to_end.py
  dashboard/
    ...
```

---

## 3. Core schemas

All in `controlplane/schemas.py`.

```python
RiskTag = Literal["performance", "cost", "responsibility"]
Action  = Literal["ALLOW", "HOLD", "CONSTRAIN", "ESCALATE", "BLOCK"]

class DetectorOutput(BaseModel):
    detector_id: str
    tag: RiskTag
    p_hat: float                  # [0,1], calibrated probability the tag applies
    verifiable: bool              # False when no ground truth was available
    measured_precision: float     # detector precision on this workflow's recent adjudicated data
    tier: int                     # 0, 1, 2
    latency_ms: float
    evidence: dict[str, Any]      # spans, matched rules, scores. Shown in the ledger UI

class RiskVector(BaseModel):
    per_tag: dict[RiskTag, DetectorOutput]   # highest p_hat wins per tag
    unverifiable_tags: list[RiskTag]

class ConsequenceModel(BaseModel):
    performance: float
    cost: float
    responsibility: float

class Policy(BaseModel):
    workflow_id: str
    version: str
    jurisdiction: str
    consequence: ConsequenceModel
    irreversibility: float        # iota, (0,1]
    latency_budget_ms: int
    intervention_mode: Literal["gated", "buffered", "monitored"]
    fail_mode: Literal["open", "closed"]
    prior: dict[RiskTag, float]   # pi_w, from shadow mode
    kappa: dict[str, float]       # pair key "performance|responsibility" -> value
    lam: float                    # lambda, joint consequence discount
    stage: Literal["shadow", "advisory", "enforcing"]
    routing: dict[str, float]     # {"q1": 0.08, "q2": 0.015}
    friction: dict[Action, float] # F(a)
    utility_loss: dict[Action, float]  # U(a)
    residual: dict[Action, float] # rho(a)

class Decision(BaseModel):
    decision_id: str
    request_id: str
    session_id: str | None
    workflow_id: str
    policy_version: str
    action: Action
    p_def: float
    p_def_effective: float        # after session carry
    c_eff: float
    losses: dict[Action, float]   # L(a) for every action, for the UI
    unconstrained_action: Action  # argmin before the severity cap
    severity_cap: Action          # the ceiling that applied
    cap_reason: str | None        # "low_precision" | "unverifiable" | None
    reason_codes: list[str]
    risk_vector: RiskVector
    session_risk_before: float
    session_risk_after: float
    tiers_run: list[int]
    total_latency_ms: float
    estimated_cost_units: float
    shadow: bool                  # True when stage != enforcing
    timestamp: datetime
```

---

## 4. Policy files

Three files, matching the Round 2 brief's own examples. Values from annex `A1` to `A6`, `A8`, `A9`, `A12`.

`policies/decision_support.yaml`:
```yaml
workflow_id: decision_support
version: v1
jurisdiction: IN
consequence:
  performance: 50000
  cost: 400
  responsibility: 50000
irreversibility: 0.9          # A12
latency_budget_ms: 2000
intervention_mode: gated
fail_mode: closed
prior:                        # A2, shadow-mode base rates
  performance: 0.009
  cost: 0.003
  responsibility: 0.003
kappa:                        # A8
  performance|responsibility: 0.4
  performance|cost: 0.9
  cost|responsibility: 0.9
lam: 0.3                      # A9
stage: enforcing
routing: {q1: 0.20, q2: 0.05}
friction:   {ALLOW: 0,   HOLD: 5,  CONSTRAIN: 15, ESCALATE: 120, BLOCK: 50}
utility_loss: {ALLOW: 0, HOLD: 20, CONSTRAIN: 80, ESCALATE: 200, BLOCK: 200}
residual:   {ALLOW: 1.0, HOLD: 0.5, CONSTRAIN: 0.3, ESCALATE: 0.1, BLOCK: 0.0}
```

`support_chatbot.yaml`: consequence `{performance: 3000, cost: 400, responsibility: 3000}`, `irreversibility: 0.6`, `latency_budget_ms: 800`, `intervention_mode: buffered`, `fail_mode: open`, prior `{0.015, 0.006, 0.004}`, `routing {q1: 0.08, q2: 0.015}`, same friction/utility/residual.

`internal_copilot.yaml`: consequence `{performance: 800, cost: 400, responsibility: 800}`, `irreversibility: 0.2`, `latency_budget_ms: 400`, `intervention_mode: monitored`, `fail_mode: open`, prior `{0.018, 0.008, 0.004}`, `routing {q1: 0.05, q2: 0.008}`, same friction/utility/residual.

Friction and utility values encode annex `A6` (`U = 200`, `F_b = 50`, `H = 120`). Keep them identical across workflows so the demo's differences come from consequence alone. That is the point of screen 1.

Policy loading must validate: `0 < irreversibility <= 1`, all `p` and `kappa` and `lam` in `[0,1]`, every `Action` key present in friction/utility/residual, residual monotonically non-increasing across the spectrum order. Raise `PolicyError` at load time on any violation.

---

## 5. Engine specification

### 5.1 Overlap model (`engine/overlap.py`)

```python
def p_def(p_hats: dict[RiskTag, float], kappa: dict[str, float]) -> float:
    """
    m = argmax tag
    P = p_m + (1 - p_m) * (1 - prod over d != m of (1 - kappa(m,d) * p_d))
    kappa lookup is order-independent: key is "|".join(sorted([m, d]))
    Returns p_m exactly when all kappa are 0.
    Reduces to 1 - prod(1 - p_d) when all kappa are 1.
    """

def c_eff(p_hats, consequence: ConsequenceModel, lam: float,
          trigger_threshold: float = 0.05) -> float:
    """
    m = argmax tag
    C = C_m + lam * sum(C_d for d != m where p_hat[d] > trigger_threshold)
    trigger_threshold prevents a near-zero tag from adding consequence.
    """
```

### 5.2 Thresholds (`engine/thresholds.py`)

These are reference values for the UI and for tests. **The engine does not route on them**, it routes on the argmin in 5.6. They must agree, and `test_thresholds.py` asserts that they do.

```python
def p_star_escalate(C: float, H: float, a_h: float = 0.9) -> float:
    return H / (a_h * C)

def p_star_block(C: float, F_b: float, U: float) -> float:
    return (F_b + U) / (C + U)
```

### 5.3 Severity cap (`engine/severity.py`)

```python
SEVERITY_ORDER = ["ALLOW", "HOLD", "CONSTRAIN", "ESCALATE", "BLOCK"]  # index = severity

def severity_max(measured_precision: float, verifiable: bool) -> tuple[Action, str | None]:
    """
    If not verifiable -> ("CONSTRAIN", "unverifiable")
    precision > 0.95  -> ("BLOCK", None)
    0.70 - 0.95       -> ("ESCALATE", "low_precision")
    0.40 - 0.70       -> ("CONSTRAIN", "low_precision")
    < 0.40            -> ("HOLD", "low_precision")
    """
```

The cap that applies to a decision is the **cap of the tag that drove the decision**, meaning the argmax tag. Take the minimum severity across caps if two tags both exceed their escalation threshold.

Note the ladder in the annex says "LOG only" below 0.40. In the implementation that is `HOLD` for the top action plus a log entry, because every decision is logged regardless. Do not add LOG as an `Action`.

### 5.4 Abstention (`engine/decide.py`, applied before argmin)

For any tag where `verifiable is False`:
- replace `p_hat` with `policy.prior[tag]`
- add the tag to `risk_vector.unverifiable_tags`
- add reason code `ABSTAIN_<TAG>`
- feed `verifiable=False` into `severity_max`

**Never substitute zero.** `test_abstention.py` asserts that the same unverifiable input escalates under `decision_support` and allows under `internal_copilot` with no branching on workflow name anywhere in the code path.

### 5.5 Session state (`engine/session.py`)

```python
GAMMA = 0.85   # A10
BETA  = 0.50   # A11

def effective_p(p_def_now: float, s_prev: float, beta: float = BETA) -> float:
    return 1 - (1 - p_def_now) * (1 - beta * s_prev)

def update_session(s_prev: float, rho_action: float, p_eff: float,
                   gamma: float = GAMMA) -> float:
    return 1 - (1 - gamma * s_prev) * (1 - rho_action * p_eff)
```

Session state is keyed by `session_id` in memory (a dict is fine for the prototype) and mirrored into the ledger so the dashboard can replay a conversation.

### 5.6 The decision (`engine/decide.py`)

```python
def decide(risk: RiskVector, policy: Policy, session_id: str | None) -> Decision:
    # 1. abstention substitution (5.4)
    # 2. P_def   = overlap.p_def(p_hats, policy.kappa)
    # 3. C_eff   = overlap.c_eff(p_hats, policy.consequence, policy.lam)
    # 4. s_prev  = session.get(session_id)
    #    P_eff   = session.effective_p(P_def, s_prev)
    # 5. for each action a:
    #        L[a] = residual[a] * P_eff * C_eff * iota
    #             + friction[a]
    #             + (1 - P_eff) * utility_loss[a]
    # 6. unconstrained = argmin(L)
    # 7. cap, cap_reason = severity.severity_max(driving_precision, driving_verifiable)
    # 8. action = min(unconstrained, cap) by SEVERITY_ORDER index
    # 9. update session with residual[action] and P_eff
    # 10. if policy.stage != "enforcing": mark shadow=True, actuator must not execute
    # 11. build reason codes, return Decision
```

Ties in the argmin resolve to the **lower** severity. Reason codes are machine-readable strings: `TAG_PERFORMANCE_HIGH`, `ABSTAIN_PERFORMANCE`, `CAP_LOW_PRECISION`, `SESSION_CARRY`, `IRREVERSIBLE_ACTION`, `POLICY_<workflow>_<version>`.

### 5.7 Reachability, for agentic requests (`engine/reachability.py`)

Only applies when the request declares a tool graph.

```python
def consequence_by_reachability(tool_graph, step, policy) -> float:
    """
    C_eff(step) = max over reachable terminal tools of
                  C(tool) * P(reach) * iota(tool)
    Tool graph is a declared dict: {tool_name: {"consequence": float,
                                                "iota": float,
                                                "reachable_from": [step_ids],
                                                "p_reach": float}}
    Returns policy consequence unchanged when no tool graph is supplied.
    """
```

When this returns a value, it **overrides** the policy consequence for that step. A reasoning step that can reach a refund tool is adjudicated at the refund's consequence.

---

## 6. Detectors

### 6.1 Protocol (`detectors/base.py`)

```python
class Detector(Protocol):
    detector_id: str
    tag: RiskTag
    tier: int
    def run(self, request: str, response: str, ctx: DetectionContext) -> DetectorOutput: ...
```

`DetectionContext` carries retrieval context (may be `None`), token usage, model tier, prior turns, and the workflow's rolling token statistics.

### 6.2 Tier 0, real, deterministic

- `SchemaDetector`: JSON or format contract validation. `measured_precision = 0.99`.
- `PIIDetector`: regex plus presidio NER plus checksum (Luhn for cards, PAN format `[A-Z]{5}[0-9]{4}[A-Z]`, Aadhaar Verhoeff). `measured_precision = 0.97` when a checksum passes, `0.72` on regex-only match. **This is the only detector permitted to reach BLOCK**, and that fact should be visible in the demo.
- `PolicyListDetector`: exact and fuzzy match against a configured deny list. `measured_precision = 0.95`.
- `TokenAnomalyDetector`: rolling z-score `z = (tokens - mu_w) / sigma_w`, EWMA with alpha 0.1. Map to probability with a logistic: `p = 1 / (1 + exp(-(z - 2.5)))`. `measured_precision = 0.85`.
- `RetryLoopDetector`: cosine similarity over consecutive tool calls in an agent trace, threshold 0.95.

### 6.3 Tier 1, small models or stubs

- `ToxicityDetector`: a small classifier if `transformers` is available, else `SimulatedDetector`.
- `GroundingDetector`: split response into sentences, run NLI entailment against retrieval context, `G = supported / total`, `p_hat = 1 - G`. **If `ctx.retrieval_context is None`, return `verifiable=False` and `p_hat=0.0`**, letting 5.4 substitute the prior. This is the abstention entry point and the most important detector behaviour in the whole prototype.

### 6.4 Tier 2

- `SelfConsistencyDetector`: `k=5` samples, cluster by embedding cosine at 0.85 (a proxy for bidirectional entailment; note the simplification in the code comment), `H_sem = -sum(p_c log p_c)`, normalise by `log k`. Costs `k` generations, so budget accounting must reflect that.
- `LLMJudgeDetector`: single call, structured JSON verdict. Prompt it to return `{"defective": bool, "confidence": float, "tag": str, "reason": str}` and nothing else. Strip markdown fences before parsing. Wrap in try/except and fall back to `verifiable=False` on parse failure.

### 6.5 The simulated detector (`detectors/simulated.py`)

**Build this first**, before any real detector. Everything downstream can be developed against it.

```python
class SimulatedDetector:
    """
    Reads the injected ground-truth label on the simulated response and emits a
    probability consistent with configurable TPR and FPR. Used for demo screen 4.
      tpr, fpr set at construction or via the /admin/detector_dial endpoint.
      If label is True:  p_hat ~ Beta shaped to give P(p_hat > 0.5) = tpr
      If label is False: p_hat ~ Beta shaped to give P(p_hat > 0.5) = fpr
      measured_precision computed analytically from (tpr, fpr, workflow base rate)
    """
```

The dashboard must expose `tpr` and `fpr` sliders. Dialling detector quality down and watching the system slide toward HOLD and logging, rather than breaking, is a required demo beat.

---

## 7. Golden test vectors

Hard-code these in `tests/`. All verified. Do not change them.

**Overlap, `p_hats = {performance: 0.4, responsibility: 0.3}`:**

| kappa | expected `P_def` |
|---|---|
| 0.0 | 0.4000 |
| 0.4 | 0.4720 |
| 1.0 | 0.5800 |

At kappa 1.0 it must equal `1 - (1-0.4)(1-0.3) = 0.58` to 6 decimal places.

**Thresholds** with `H=120`, `a_h=0.9`, `F_b=50`, `U=200`:

| Workflow | `C` | `p*_esc` | `p*_block` |
|---|---|---|---|
| internal_copilot | 800 | 0.166667 | 0.250000 |
| support_chatbot | 3000 | 0.044444 | 0.078125 |
| decision_support | 50000 | 0.002667 | 0.004980 |

**Session compounding**, `internal_copilot`, four turns each with `P_def = 0.10`, `gamma=0.85`, `beta=0.5`:

| Turn | `s_prev` | `P_eff` | Action |
|---|---|---|---|
| 1 | 0.0000 | 0.1000 | ALLOW |
| 2 | 0.1000 | 0.1450 | ALLOW |
| 3 | 0.2177 | 0.1980 | ESCALATE |

Turns 1 and 2 are individually below the copilot's 16.67% escalation threshold. Turn 3 crosses it purely from carried risk. **This is demo screen 4 and it must reproduce exactly.**

**The golden decision.** Workflow `support_chatbot`, `p_hats = {performance: 0.30, cost: 0.02, responsibility: 0.10}`, `kappa=0.4` on the performance-responsibility pair, `lam=0.3`, `iota=0.6`, no session carry.

```
P_def = 0.3334
C_eff = 3900.0      (3000 + 0.3 * 3000, cost tag below the 0.05 trigger)

L(ALLOW)     = 780.10
L(HOLD)      = 408.38
L(CONSTRAIN) = 302.36
L(ESCALATE)  = 331.33
L(BLOCK)     = 183.32

unconstrained_action = BLOCK
```

Now apply the cap. The driving tag is `performance`, whose detector has `measured_precision = 0.55`, so `severity_max = CONSTRAIN`.

```
action = CONSTRAIN
cap_reason = "low_precision"
```

**This single test carries the entire thesis.** Unconstrained expected-loss minimisation wants to block, and the precision cap refuses because the evidence does not support it. `test_decide_golden.py` must assert every number above, and the dashboard must be able to display this exact case on demand.

---

## 8. Build order

Each step lists its acceptance test. Run it before starting the next step.

| # | Step | Acceptance |
|---|---|---|
| 1 | `schemas.py`, `constants.py`, `policy.py`, three YAML policies | `test_policy.py`: all three load, an invalid policy raises `PolicyError` |
| 2 | `engine/overlap.py` | `test_overlap.py`: the three kappa vectors in section 7, plus kappa=1 equals the independence product |
| 3 | `engine/thresholds.py` | `test_thresholds.py`: the three-workflow table to 6 dp |
| 4 | `engine/severity.py` | `test_severity.py`: each precision band maps to the right cap, unverifiable always caps at CONSTRAIN |
| 5 | `engine/session.py` | `test_session.py`: the four-turn table |
| 6 | `engine/decide.py` | `test_decide_golden.py`: the golden decision, all five `L(a)` values and the cap |
| 7 | `detectors/simulated.py` | `test_detectors.py`: over 10,000 samples, empirical TPR and FPR are within 0.02 of the dial |
| 8 | `ledger.py` | `test_ledger.py`: hash chain verifies, tampering with a row is detected, ALLOW decisions are present |
| 9 | `detectors/tier0.py` | PII detector catches a seeded PAN and card number, checksum path reports precision 0.97 |
| 10 | `cascade.py` | `test_cascade_budget.py`: over 10,000 simulated requests, mean added latency is within 20% of `E[dt]` from annex 3.9, and tier-2 fire rate matches `q2` within 0.3pp |
| 11 | `sim/generator.py` | 3,000 labelled responses across three workflows, defect rates within 0.3pp of `A2`, includes joint-tag defects and a no-retrieval-context slice |
| 12 | `detectors/tier1.py` grounding, with the abstention path | `test_abstention.py`: identical unverifiable input escalates in decision_support, allows in internal_copilot, no workflow-name branching in the code path |
| 13 | `api.py` | `test_end_to_end.py`: POST a completion, get a decision, find it in the ledger |
| 14 | `calibration.py` | ECE computed on the sim set, isotonic fit reduces it, kappa estimated from ledger co-occurrence lands near the seeded value |
| 15 | Dashboard screens 1 to 4 | Manual, per section 10 |
| 16 | `detectors/tier2.py` | Optional. Skip if time is short and leave the simulated detector in place |

Steps 1 to 8 are the product. If everything after step 12 is cut, the demo still works.

---

## 9. API

```
POST /v1/chat/completions        OpenAI-compatible. Header X-ControlPlane-Workflow
                                 selects the policy. Optional X-ControlPlane-Session.
                                 Returns the completion plus an X-ControlPlane-Decision
                                 header carrying the decision_id.
                                 On BLOCK, returns the policy fallback text and
                                 finish_reason "content_filter".

POST /v1/adjudicate              Body: {request, response, workflow_id, session_id,
                                 tool_graph?}. Runs the full pipeline without calling
                                 a model. This is what the dashboard and the sim use.

GET  /v1/decisions               Paged ledger read. Filters: workflow_id, action,
                                 session_id, since.
GET  /v1/decisions/{id}          Full decision including every L(a) and the evidence.
POST /v1/decisions/{id}/adjudicate   Body: {actually_defective: bool, note: str}.
                                 Writes the human label, feeds calibration.

GET  /v1/metrics                 EDR, UIR, abstention rate, override rate, p50/p95/p99
                                 latency, cost units, per workflow and overall.
POST /admin/detector_dial        Body: {detector_id, tpr, fpr}. Demo screen 4.
POST /admin/threshold_mode       Body: {mode: "global"|"derived", global_threshold?}.
                                 Demo screen 2.
GET  /admin/policy/{workflow_id} Returns the active snapshot and version.
```

Every request gets a `request_id`. Every decision is written to the ledger **including ALLOW**, because a ledger of interventions only is not an audit trail.

---

## 10. Dashboard, four screens

Build in this order. Screen 2 is the one that wins the pitch, so do not leave it last.

**Screen 1, Same response, three verdicts.** One risky response, adjudicated under all three policies side by side. Each column shows: the risk vector, `P_def`, `C_eff`, all five `L(a)` values as a small bar chart with the minimum highlighted, the severity cap, and the final action. A caption states that the only difference between columns is the consequence model.

**Screen 2, The threshold slider.** A single control switching between global-threshold mode and derived-per-workflow mode, plus a slider for the global threshold. Live-recompute EDR and UIR over the 3,000-response sim set and plot both as the slider moves. In global mode the two curves trade against each other. Switching to derived mode moves both down at once. Show the two operating points on the same axes so the improvement is visible in one glance.

**Screen 3, Abstention.** A toggle stripping retrieval context from a claim. Show side by side: with context, grounding verifies and the response allows; without context, `verifiable=False`, the prior substitutes, severity caps, and decision support escalates while the copilot allows. Display the reason codes.

**Screen 4, Compounding, plus the detector dial.** The four-turn conversation from section 7 with `s_t` plotted per turn and the threshold line drawn across it. Below it, TPR and FPR sliders that re-run the sim set live, with a readout showing precision, the resulting severity cap, and the action distribution shifting toward HOLD and CONSTRAIN as quality drops.

Plus a **ledger view**: filterable decision table, click through to full evidence, and a hash-chain verification badge. And a **telemetry strip**: p50/p95/p99 added latency, tier fire rates, model calls, token usage, estimated cost per decision. The brief asks for runtime telemetry explicitly.

---

## 11. Definition of done

- `pytest -q` passes, every golden vector in section 7 asserted.
- `python -m sim.seed_data` populates a fresh ledger with 3,000 decisions in under 60 seconds, deterministically.
- All four dashboard screens work from a cold start with one command.
- The README explains how to run it in under ten lines, with no AI attribution anywhere.
- `/v1/metrics` reports EDR and UIR together. Neither is ever displayed alone, in the API or the UI.
- Every simulated component is labelled as simulated in the UI. Do not let a reviewer mistake a stub for a working detector.

---

## 12. Things to deliberately not build

Cutting these is a decision, not an oversight. If asked, say so.

- **Inline rewriting of responses.** CONSTRAIN re-prompts with a narrower contract, it never edits output. See annex 2.2.
- **Representation or activation-level detection.** The brief confirms API-level model consumption, so internals are out of reach.
- **Real authentication, multi-tenancy, or a production datastore.** Prototype scope.
- **Streaming.** Adjudicate complete responses. Section 3.10 of the annex explains the modes; demonstrating them is a slide, not code.
- **Training any model.** Calibration fits isotonic regression on outputs. Nothing else is trained.
