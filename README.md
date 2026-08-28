# ControlPlane.ai

**Accenture Innovation Challenge, Round 2. Problem Track 1.**

A consequence-aware AI intervention layer. It does not try to be a better
detector. It answers the question above detection: given an imperfect signal,
what is the right thing to do about it, in this workflow, at this cost, with
this quality of evidence?

---

## The three deliverables

| Round 2 asks for | Where it is |
| :--- | :--- |
| **Detailed business proposal** | [controlplane/BUSINESS_PROPOSAL.md](controlplane/BUSINESS_PROPOSAL.md) |
| **Working prototype** | [controlplane/](controlplane/), see Run it below |
| **Pitch presentation** | [controlplane/PITCH_DECK.html](controlplane/PITCH_DECK.html), open in a browser |

The deck prints to a landscape PDF, one slide per page, via Ctrl+P with
background graphics enabled.

---

## Run it

```bash
cd controlplane
pip install -r requirements.txt
pytest -q                      # 221 tests
python -m sim.seed_data        # 3,000 decisions, 20% audit sample
uvicorn controlplane.api:app --port 8000
```

Open `http://localhost:8000` and start at **Screen 0**.

First run downloads a 70MB entailment model and caches it. To skip it and use
the lexical fallback instead, set `CONTROLPLANE_DISABLE_NLI=1`.

Live model generation is optional. Copy `controlplane/.env.example` to
`.env.local` and paste a key; presets are included for OpenAI, OpenRouter, Groq,
Cerebras and a fully local Ollama. Without one, the demo replays recorded
responses and labels them as recorded on screen.

---

## What it does

An enterprise does not run one AI system. It runs several, and a mistake in each
costs a different amount. A defect in a decision support tool costs roughly 60
times what the same defect costs in an internal copilot, so a single global
threshold is necessarily wrong about one of them.

ControlPlane prices that difference and acts on it. Every response is scored,
then the action that minimises expected loss is chosen from five graded options
rather than two:

```
L(a) = rho(a) * P_eff * C_eff * iota  +  F(a)  +  (1 - P_eff) * U(a)
```

Thresholds are derived from each workflow's own consequence model rather than
hand-tuned. Four mechanisms keep it honest: a precision cap so action severity
never exceeds what the evidence supports, abstention when nothing can be
verified, risk compounding across conversation turns, and consequence by
reachability for agents that can take actions.

Every decision, including the ones that allowed, is written to a hash-chained
ledger that detects edits rather than only reordering.

---

## Seven demo screens

| | Screen | Demonstrates |
| :--- | :--- | :--- |
| 0 | The Catch | A real model's answer checked claim by claim, with the failing sentence named |
| 1 | Three Verdicts | One risk vector, three consequence models, three different actions |
| 2 | Threshold Frontier | EDR against UIR over 3,000 labelled responses |
| 3 | Abstention | Same claim with and without a source. Decision support intervenes, the copilot allows |
| 4 | Compounding and Dial | Constant per-turn risk, changing action. Detector quality slider |
| 5 | Calibration Gate | The system measuring itself and refusing to enforce |
| 6 | Agentic Consequence | One sentence, three verdicts, based only on what the step can reach |

Plus a filterable audit ledger and a Live Playground where you can type your own
prompt and response, or load your own policy document, and adjudicate it.

---

## Documentation

- [controlplane/README.md](controlplane/README.md), how to run it, and exactly
  which detectors are real versus simulated
- [controlplane/ARCHITECTURE.md](controlplane/ARCHITECTURE.md), the decision
  arithmetic, ledger integrity, and an explicit list of what is not implemented
- [controlplane/API_REFERENCE.md](controlplane/API_REFERENCE.md), every
  endpoint with payloads captured from a running instance

## Design notes

`controlplane_build_guide.md` and `controlplane_round2_annex.md` are the
original design documents: the implementation contract and the reasoning behind
the assumptions. They predate the prototype, and the prototype disagrees with
them in three places that are documented where they occur, most importantly the
escalation utility loss in annex A6 and the closed-form thresholds in section
3.2. Where they differ, the code and `ARCHITECTURE.md` are correct.

`6a882073d90c9_..._final.pdf` is the challenge brief.
