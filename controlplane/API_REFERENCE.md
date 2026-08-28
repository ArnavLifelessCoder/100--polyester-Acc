# ControlPlane.ai API Reference

Base URL: `http://127.0.0.1:8000`
Interactive OpenAPI docs: `http://127.0.0.1:8000/docs`

Every payload below was captured from a running instance seeded with
`python -m sim.seed_data`. Numbers will differ on your data; shapes will not.

**Contents**

1. [Gateway and adjudication](#1-gateway-and-adjudication)
2. [Audit ledger](#2-audit-ledger)
3. [Metrics and calibration](#3-metrics-and-calibration)
4. [Demo endpoints](#4-demo-endpoints)
5. [Administration](#5-administration)
6. [Reason codes](#6-reason-codes)
7. [Configuration](#7-configuration)

---

## 1. Gateway and adjudication

### 1.1 `POST /v1/chat/completions`

OpenAI-compatible proxy. The candidate completion is adjudicated before it is
returned, and the verdict travels in response headers so a caller can audit the
gate without a second request.

> **Prototype note.** With no model provider configured this endpoint
> synthesises its own completion text rather than calling a model. Configure a
> provider (section 7) to proxy a real one.

#### Request headers

| Header | Required | Description |
| :--- | :---: | :--- |
| `X-ControlPlane-Workflow` | No | Policy id: `internal_copilot`, `support_chatbot`, `decision_support`. Defaults to `support_chatbot` |
| `X-ControlPlane-Session` | No | Session id. Supplying one enables multi-turn risk compounding |

#### Request body

```json
{
  "model": "gpt-4o",
  "messages": [
    { "role": "user", "content": "What is the recommended dosage for patient X?" }
  ],
  "temperature": 0.7
}
```

#### Response headers

| Header | Example | Description |
| :--- | :--- | :--- |
| `X-ControlPlane-Decision` | `cea34f35-6d8a-...` | Decision id, resolvable at `/v1/decisions/{id}` |
| `X-ControlPlane-Action` | `ALLOW` | Action actually taken |
| `X-ControlPlane-Unconstrained` | `BLOCK` | Action before the severity cap. Differs from `Action` when the cap bound |
| `X-ControlPlane-Peff` | `0.025954` | Effective defect probability after session carry |
| `X-ControlPlane-Ceff` | `400.00` | Effective consequence, INR |
| `X-ControlPlane-Latency` | `102.0` | Modelled adjudication latency, ms. See section 3.1 |
| `X-ControlPlane-Shadow` | `false` | `true` when the policy stage is not `enforcing`, meaning the action must not be executed |

On `BLOCK` the body carries the policy fallback text and
`finish_reason: "content_filter"`. Every other action returns
`finish_reason: "stop"`.

---

### 1.2 `POST /v1/adjudicate`

Runs the full cascade and decision engine on a request/response pair without
calling a model. This is what the dashboard and the simulator use.

#### Request body

| Field | Type | Required | Description |
| :--- | :--- | :---: | :--- |
| `request` | string | yes | The prompt |
| `response` | string | yes | The candidate response to adjudicate |
| `workflow_id` | string | yes | Policy to adjudicate under |
| `session_id` | string | no | Enables session compounding across calls |
| `retrieval_context` | string | no | Source document. **Omitting it triggers abstention**, it does not mean "clean" |
| `tool_graph` | object | no | Declared agent tool graph, see below |
| `step` | string | no | Which step in that graph this response is |

**Tool graph.** When supplied with a `step`, the consequence of the step is what
it can reach rather than what it says:

```
C_eff(step) = max over reachable terminals of C(tool) * P(reach) * iota(tool)
```

```json
{
  "tool_graph": {
    "refund_api": {
      "consequence": 250000.0,
      "iota": 1.0,
      "p_reach": 0.6,
      "reachable_from": ["plan_step"]
    }
  },
  "step": "plan_step"
}
```

A copilot step that would otherwise be `ALLOW` at `C_eff = 800` becomes `BLOCK`
at `C_eff = 150000` once it can reach the refund API. Reason codes
`REACHABILITY_CONSEQUENCE` and `REACHABLE_TOOL_DOMINATES` mark it.

#### Response

```json
{
  "decision_id": "0b3f5c21-9a44-4f0e-b6d2-7c1e8a9f4d33",
  "action": "ESCALATE",
  "p_def": 1.0,
  "p_def_effective": 1.0,
  "c_eff": 65000.0,
  "losses": {
    "ALLOW": 58500.0,
    "HOLD": 29255.0,
    "CONSTRAIN": 17565.0,
    "ESCALATE": 5970.0,
    "BLOCK": 50.0
  },
  "unconstrained_action": "BLOCK",
  "severity_cap": "ESCALATE",
  "cap_reason": "low_precision",
  "reason_codes": [
    "POLICY_decision_support_v1",
    "CAP_LOW_PRECISION",
    "TAG_PERFORMANCE_HIGH",
    "TAG_RESPONSIBILITY_HIGH",
    "IRREVERSIBLE_ACTION"
  ],
  "session_risk_before": 0.0,
  "session_risk_after": 0.1,
  "shadow": false,
  "tiers_run": [0, 1, 2],
  "total_latency_ms": 552.0
}
```

`unconstrained_action` is the argmin of expected loss; `action` is what
survived the severity cap. When they differ, the engine wanted a more severe
intervention than detector precision could justify. That gap is the product.

`GET /v1/decisions/{id}` returns the same decision with full detector evidence
attached, including per-claim entailment scores.

---

## 2. Audit ledger

### 2.1 `GET /v1/decisions`

Paged read over the append-only ledger. Every decision is recorded, including
`ALLOW`. A ledger of interventions only is not an audit trail.

| Parameter | Default | Description |
| :--- | :--- | :--- |
| `limit` | 100 | Max 1000 |
| `offset` | 0 | Pagination offset |
| `workflow_id` | none | Filter by workflow |
| `action` | none | Filter by action taken |
| `session_id` | none | Filter to one conversation |
| `since` | none | ISO timestamp lower bound |

### 2.2 `GET /v1/decisions/{id}`

The complete decision: every `L(a)`, all detector evidence, the reason codes,
and the row's `prev_hash` and `row_hash`.

### 2.3 `POST /v1/decisions/{id}/adjudicate`

Records a human verdict. This is the feedback loop's entry point, and the only
source of EDR, UIR, override rate and calibration.

```json
{ "actually_defective": false, "note": "reviewed by compliance, 2026-08-27" }
```

Response names the outcome so the reviewer sees what they just recorded:

```json
{
  "status": "labelled",
  "decision_id": "0b3f5c21-...",
  "actually_defective": false,
  "action_taken": "ESCALATE",
  "outcome": "unnecessary_intervention",
  "total_labelled": 615
}
```

`outcome` is one of `escaped_defect`, `unnecessary_intervention`,
`correct_intervention`, `correct_allow`.

Verdicts are stored in a separate table. A decision row is append-only and
hash-chained, so a label must never modify the record it refers to. Writing
one does not disturb the chain.

### 2.4 `GET /v1/chain/verify`

```json
{ "valid": true, "rows_checked": 3000 }
```

Two things are checked per row: that `prev_hash` matches the previous row's
`row_hash`, **and** that `row_hash` recomputes from the row's own stored
content. The second check is the one that catches an edited decision. Verifying
only the links proves the rows are in write order, not that any of them still
says what it said.

On failure, `rows_checked` is the index of the first bad row.

---

## 3. Metrics and calibration

### 3.1 `GET /v1/metrics`

Two groups with different sources, deliberately kept apart.

```json
{
  "traffic": {
    "total_decisions": 3000,
    "action_distribution": { "ALLOW": 1334, "HOLD": 1602, "CONSTRAIN": 63, "ESCALATE": 1 },
    "intervention_rate": 0.5553,
    "abstention_rate": 0.148,
    "cap_bind_rate": 0.1933,
    "shadow_rate": 0.0,
    "tier_fire_rate": { "tier0": 1.0, "tier1": 1.0, "tier2": 0.085 },
    "estimated_cost_units_total": 97.35,
    "estimated_cost_units_per_decision": 0.03245,
    "p50_latency_ms": 102.0,
    "p95_latency_ms": 552.0,
    "p99_latency_ms": 552.0,
    "latency_source": "modelled_tier_budgets"
  },
  "quality": {
    "edr": 0.0,
    "uir": 5439.7,
    "override_rate": 0.544,
    "labelled_count": 614,
    "escaped_defects": 0,
    "unnecessary_interventions": 334,
    "caught_defects": 8,
    "defects_labelled": 8
  },
  "per_workflow": { "decision_support": { "traffic": {}, "quality": {} } }
}
```

**`traffic`** describes everything the engine did and is always available.

**`quality`** describes whether it was right, and requires human labels.

- `edr`: escaped defects per 10,000, truly defective and allowed through
- `uir`: unnecessary interventions per 10,000, truly clean and intervened on
- `override_rate`: fraction of labelled decisions where the human verdict
  contradicts the action taken

With no labels these are `null`, not `0.0`, and `labelled_count` is `0`. An
unlabelled system does not have a perfect EDR, it has an unknown one. EDR and
UIR are never returned one without the other.

**Latency is modelled**, from the annex tier budgets (12 / 90 / 450 ms), not
wall clock. Wall clock over in-process detectors reads about 0.05ms, which is
not a number anyone can plan capacity from. `latency_source` says which you are
looking at.

### 3.2 `GET /v1/calibration`

Optional `?workflow_id=` to scope it.

```json
{
  "labelled_count": 614,
  "sufficient": true,
  "ece_raw": 0.0733,
  "ece_isotonic": 0.0,
  "brier_raw": 0.0283,
  "brier_isotonic": 0.0023,
  "ece_gate": 0.05,
  "passes_enforcing_gate": false,
  "isotonic_improves": true,
  "base_rate": 0.013,
  "mean_reported_probability": 0.0864
}
```

A policy may not move from advisory to enforcing until ECE is under 0.05. The
decision arithmetic is only as trustworthy as the probabilities fed into it: a
detector reporting a mean probability of 0.086 against a base rate of 0.013 is
overconfident by roughly seven times, and under a ₹50,000 consequence that is
enough to hold traffic that should pass.

Below 50 labels the endpoint returns `sufficient: false` and omits the scores
rather than reporting an estimate it cannot support.

The isotonic fit here is **reported, not applied**, and it is scored on the
whole labelled set rather than a held-out split, so `ece_isotonic` reads near
zero by construction. Treat it as a diagnostic only. For the honest number, use
`/demo/screen5`, which fits on a training split and scores on data the map has
not seen. On the same ledger that reports 0.0733 here, the held-out figure is
0.0726 before correction and 0.0005 after.

---

## 4. Demo endpoints

### 4.1 `GET /demo/live/scenarios` and `POST /demo/live`

Screen 0, the live catch. Generates an answer, adjudicates it, and names the
claim that failed.

```json
{ "scenario": "lending_decision" }
```

Or override entirely: `request`, `retrieval_context`, `workflow_id`.

Returns the standard decision payload plus:

```json
{
  "generated_response": "Given the applicant is a 58-year-old Muslim woman, I would treat this as a higher risk profile and recommend we decline the loan application.",
  "generation": { "source": "recorded", "model": null },
  "grounding": {
    "method": "nli",
    "supported": 0,
    "sentences": 2,
    "failed_claims": [
      {
        "sentence": "Given the applicant is a 58-year-old Muslim woman, ...",
        "verdict": "unsupported",
        "entailment": 0.001,
        "contradiction": 0.057
      }
    ]
  },
  "bias": {
    "categories": ["age", "gender", "religion"],
    "findings": [
      { "category": "religion", "attribute_term": "muslim", "decision_term": "risk", "distance_words": 9 }
    ]
  }
}
```

`generation.source` is `live_model` or `recorded` and is **always** present. A
recording presented as a live call is the fastest way to lose a room. A custom
typed question with no provider configured returns **503** rather than being
answered from a recording.

`verdict` is `entailed`, `contradicted` (the source refutes the claim) or
`unsupported` (the source is silent). The distinction matters and is preserved.

### 4.2 `GET /demo/screen1`

One risk vector, produced once by the real cascade, adjudicated under all three
policies. Returns `columns` keyed by workflow, plus each workflow at the top
level for convenience, plus `distinct_actions` and the shared risk vector.

The detector output is identical across columns; only the consequence model
varies. If this ever returns one distinct action it is demonstrating nothing,
and `tests/test_demo_screens.py` fails.

### 4.3 `GET /demo/screen2?global_threshold=0.08`

EDR and UIR measured over the 3,000-response labelled set, using P_def as the
real cascade computed it and the action the real engine chose.

Returns the frontier `curve`, the `global_operating_point` at your threshold,
an `edr_matched_global_point` for a like-for-like comparison, the
`derived_operating_point`, and a `per_workflow` breakdown.

Also returns `finding` and `caveat`. Read them. At matched EDR the derived
thresholds cut the copilot's unnecessary interventions and raise decision
support's. That reallocation is the mechanism, and aggregate EDR and UIR cannot
show it because both count a copilot defect and a decision-support defect as one
defect each. Scored with the simulated detectors so detector quality is a known
quantity; `detectors: "simulated"` says so.

### 4.4 `GET /demo/screen3`

The same claim adjudicated with and without retrieval context, across all three
workflows. Without context the grounding detector reports `verifiable=false`,
the engine substitutes the workflow prior, and the cap drops to `CONSTRAIN`.

Build guide 5.3 caps every unverifiable signal at `CONSTRAIN`, so an abstaining
input can never produce a final `ESCALATE`. The escalation still appears as
`unconstrained_action`: the engine wanted a human, the evidence quality would
not support one.

### 4.5 `GET /demo/screen4`

Two conversation tracks. Per-turn `P_def` is held constant, so any change in
action comes purely from carried session risk.

```
support_chatbot   ALLOW, ALLOW, HOLD, HOLD          crossing at turn 3
decision_support  HOLD,  HOLD,  ESCALATE, ESCALATE  crossing at turn 3
```

This deliberately does not reproduce the annex section 7 table, which asserts an
`ESCALATE` at `p_eff=0.198` under `internal_copilot`. That follows from the
simplified `p*_esc = H/(a_h*C)` closed form, which omits both `iota` and the
utility-loss term that `L(a)` actually contains. Under the engine's own
arithmetic `internal_copilot` never escalates at any p, because a 120-unit human
review does not pay against an 800-unit consequence discounted by `iota=0.2`.
The compounding claim is real; the workflow the table attached it to was wrong.

### 4.6 `GET /demo/screen5`

Calibration and the enforcing gate. Returns the reliability curve as reported
and after correction, the held-out fit summary, EDR and UIR before and after
correction, a per-workflow breakdown, and the shadow/advisory/enforcing ladder.

All quality figures come from the held-out split. Reading this endpoint does
**not** activate the map; inspecting a diagnostic must not change what the live
engine does.

### 4.7 `GET /demo/detector_quality?tpr=&fpr=`

Re-scores the labelled set at a given detector operating point and returns the
measured precision, the resulting severity cap, the action distribution, and
EDR/UIR. Results are cached per operating point.

This is what the Screen 4 dial calls. The dial previously POSTed to
`/admin/detector_dial` and changed nothing any screen displayed, because the
compounding demo builds its risk vectors from fixed values. A control that moves
and changes nothing is worse than no control.

As quality falls, precision falls, the cap steps down BLOCK to ESCALATE to
CONSTRAIN to HOLD, and the action mix slides toward HOLD. The system degrades
into logging rather than into wrong blocks.

### 4.8 `GET /demo/screen6`

Agentic consequence. The same response adjudicated three ways: as plain text, as
a step reaching low-consequence tools, and as a step reaching a refund API. The
risk vector is identical in all three; only `c_eff` moves.

---

## 5. Administration

### 5.1 `POST /admin/detector_dial`

```json
{ "detector_id": "sim_perf_t1", "tpr": 0.85, "fpr": 0.04 }
```

Applies only to simulated detectors. Returns 404 for a detector that is real or
not adjustable.

### 5.1a `POST /admin/calibration/fit` and `POST /admin/calibration/clear`

Fit the calibration map on adjudicated decisions and activate it, or deactivate
it. Optional `test_fraction` (default 0.3) and `seed`.

Fitting is on a training split and scoring on a held-out split. Isotonic
regression evaluated on its own training data reports an error near zero by
construction, which would be a meaningless number to put on a slide.

Returns 400 when there are fewer than 50 labels, or when the labels contain only
one class, in which case there is nothing for a monotone map to learn.

While active, `decide()` corrects `P_def` before the loss arithmetic and adds
the `CALIBRATED` reason code. The thresholds are untouched: moving them to
compensate for an overconfident detector would break the consequence model that
derives them. The input is what is wrong, so the input is what gets fixed.

### 5.2 `GET /admin/policy/{workflow_id}` and `GET /admin/policies`

The active immutable policy snapshot, or all of them.

### 5.3 `POST /admin/threshold_mode`

> **Not implemented.** Accepts a body and returns `status: updated` without
> changing engine behaviour. Screen 2 compares the two modes directly rather
> than switching a global one. Listed here so nobody builds on it.

---

## 6. Reason codes

| Code | Category | Fires when |
| :--- | :--- | :--- |
| `POLICY_<wf>_<ver>` | Context | Always. Names the policy snapshot applied |
| `TAG_PERFORMANCE_HIGH` | Risk tag | `p_hat > 0.1` for the performance tag |
| `TAG_COST_HIGH` | Risk tag | `p_hat > 0.1` for the cost tag |
| `TAG_RESPONSIBILITY_HIGH` | Risk tag | `p_hat > 0.1` for the responsibility tag |
| `ABSTAIN_<TAG>` | Abstention | A detector for that tag returned `verifiable=false`; the workflow prior was substituted, never zero |
| `CAP_LOW_PRECISION` | Severity cap | The cap bound and the reason was detector precision |
| `CAP_UNVERIFIABLE` | Severity cap | The cap bound at `CONSTRAIN` because a signal was unverifiable |
| `SESSION_CARRY` | Compounding | Session risk from prior turns was carried into this decision |
| `IRREVERSIBLE_ACTION` | Consequence | Workflow `iota >= 0.8` |
| `CALIBRATED` | Calibration | An active calibration map changed the reported `P_def` before the loss arithmetic |
| `REACHABILITY_CONSEQUENCE` | Agentic | A tool graph was supplied and the reachable consequence replaced the policy consequence |
| `REACHABLE_TOOL_DOMINATES` | Agentic | That reachable consequence was **higher** than the policy's own |

A `CAP_*` code appears only when the cap actually changed the action. Compare
`action` against `unconstrained_action` to see the gap.

---

## 7. Configuration

Settings come from three places. Highest precedence first:

1. **The real environment.** A shell export, a CI secret, or the test suite's
   own override always wins, so a stray file on one laptop can never quietly
   redirect a pipeline.
2. **`.env.local`**, which holds real keys and is gitignored.
3. **`.env`**, if the project ever adds shared non-secret defaults.

```bash
cp .env.example .env.local     # then paste a key into it
```

`.env.example` is tracked and carries ready presets for OpenAI, OpenRouter,
Groq, and a fully local Ollama. `.env.local` is not tracked and never should be.
Loading happens in `controlplane/__init__.py`, before any module reads
`os.environ`, because `providers.py` and `detectors/nli.py` both resolve their
configuration at import time. `python-dotenv` is optional: without it the files
are skipped and everything falls back to the real environment.

| Variable | Default | Effect |
| :--- | :--- | :--- |
| `CONTROLPLANE_API_KEY` / `OPENAI_API_KEY` | unset | Enables live generation on `/demo/live` and the counterfactual bias detector. Without it, recorded responses and abstention |
| `CONTROLPLANE_MODEL` | `gpt-4o-mini` | Model id |
| `CONTROLPLANE_BASE_URL` | unset | Any OpenAI-compatible endpoint |
| `CONTROLPLANE_TEMPERATURE` | `0.7` | Sampling temperature |
| `CONTROLPLANE_TIMEOUT_S` | `30` | Provider request timeout |
| `CONTROLPLANE_NLI_MODEL` | `cross-encoder/nli-deberta-v3-xsmall` | Entailment model for grounding |
| `CONTROLPLANE_DISABLE_NLI` | unset | Set to `1` to force the lexical grounding fallback. The fallback reports its own lower precision and flags `method: lexical_overlap_fallback` |
| `CONTROLPLANE_DB` | `controlplane.db` | Ledger location. The test suite points this at a throwaway copy so runs never mutate the seeded database |

An empty `CONTROLPLANE_API_KEY` reads as unconfigured, which is a valid working
setup rather than a broken one. A placeholder string would be worse: the client
would construct successfully and then fail with an auth error at demo time.

Every model is optional. Nothing silently degrades: a detector that cannot run
abstains, which routes through the workflow prior rather than reporting a clean
result it did not establish. The entailment model is loaded at startup rather
than on first use, so the first request after a cold start cannot race it and
quietly take the lexical path.

Check what actually took effect with `GET /demo/live/scenarios`, which reports
both the provider and the NLI model status:

```json
{
  "configured": true,
  "model": "gpt-oss-120b",
  "base_url": "https://api.cerebras.ai/v1",
  "client_error": null,
  "last_call_error": "APIStatusError: Error code: 402 - payment required"
}
```

`configured` only means a key is present. `client_error` covers setup failures,
and `last_call_error` covers the far more common case of a key that constructs a
client fine and is then rejected on the first request. The three failures worth
recognising:

| Symptom | Cause |
| :--- | :--- |
| `AuthenticationError: 401` | A provider-specific key sent to the default OpenAI endpoint. Set `CONTROLPLANE_BASE_URL` |
| `NotFoundError: 404 model_not_found` | The model is not on your account. List what is with `client.models.list()` |
| `APIStatusError: 402` | The key and endpoint are right; the account has no quota |

Errors are recorded with the API key redacted. When generation fails,
`/demo/live` returns 503 and names the failure rather than quietly serving a
recorded answer to a question the user typed.
