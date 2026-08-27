"""
Demo scenarios matching Section 6.3 and Section 10 of the build guide.

Exposes functions to execute and print the 4 demo scenarios directly.
"""

from __future__ import annotations

from pathlib import Path

from controlplane.policy import load_all_policies
from controlplane.engine.decide import decide, get_session_store
from controlplane.cascade import DetectorCascade
from controlplane.schemas import DetectionContext, DetectorOutput, RiskVector


POLICIES_DIR = Path(__file__).resolve().parent.parent / "policies"


def run_screen1_demo():
    """Demo Screen 1: Same response, three workflows."""
    policies = load_all_policies(POLICIES_DIR)
    get_session_store().clear()
    cascade = DetectorCascade(use_real_detectors=True)

    response = (
        "Based on my analysis, the patient should be prescribed 500mg of the medication. "
        "The patient's PAN card ABCDE1234F confirms their identity. "
        "I recommend immediate approval of the claim."
    )

    print("=== Demo Screen 1: Same Response, Three Workflows ===")
    for wid in ["internal_copilot", "support_chatbot", "decision_support"]:
        policy = policies[wid]
        ctx = DetectionContext(
            retrieval_context="Patient records indicate standard dosage is 250mg.",
            token_usage={"completion_tokens": len(response.split())},
        )
        risk, tiers, lat, cost = cascade.run("Analyze patient case", response, ctx, policy)
        d = decide(risk, policy, session_id=None, tiers_run=tiers, total_latency_ms=lat)
        print(f"\nWorkflow: {wid}")
        print(f"  Action: {d.action} (unconstrained={d.unconstrained_action}, cap={d.severity_cap})")
        print(f"  P_def: {d.p_def:.4f}, C_eff: INR {d.c_eff:.2f}")
        print(f"  Losses: {d.losses}")


def run_screen3_demo():
    """Demo Screen 3: Abstention."""
    policies = load_all_policies(POLICIES_DIR)
    get_session_store().clear()
    cascade = DetectorCascade(use_real_detectors=True)

    response = "The quarterly earnings show a 15% increase in revenue, driven by strong performance in the Asia-Pacific region."

    print("\n=== Demo Screen 3: Abstention Path ===")
    for has_context in [True, False]:
        status = "WITH retrieval context" if has_context else "WITHOUT retrieval context"
        print(f"\n--- {status} ---")
        ctx = DetectionContext(
            retrieval_context="Q3 earnings: revenue up 15%, APAC region drove growth." if has_context else None,
            token_usage={"completion_tokens": len(response.split())},
        )
        for wid in ["decision_support", "internal_copilot"]:
            policy = policies[wid]
            risk, tiers, lat, cost = cascade.run("earnings query", response, ctx, policy)
            d = decide(risk, policy, session_id=None, tiers_run=tiers, total_latency_ms=lat)
            print(f"  {wid}: Action={d.action}, P_def={d.p_def:.4f}, ReasonCodes={d.reason_codes}")


def run_screen4_demo():
    """Demo Screen 4: 4-turn compounding in internal_copilot."""
    policies = load_all_policies(POLICIES_DIR)
    get_session_store().clear()
    copilot_policy = policies["internal_copilot"]
    session_id = "demo-compounding-cli"

    print("\n=== Demo Screen 4: Multi-Turn Risk Compounding ===")
    turns = [
        "Summarize Q3 report",
        "Competitor market share",
        "Q4 projected growth",
        "R&D expansion recommendation",
    ]

    for i, req in enumerate(turns):
        risk = RiskVector(
            per_tag={
                "performance": DetectorOutput(
                    detector_id="sim", tag="performance", p_hat=0.10,
                    verifiable=True, measured_precision=0.80, tier=1, latency_ms=10.0,
                ),
                "cost": DetectorOutput(
                    detector_id="sim", tag="cost", p_hat=0.01,
                    verifiable=True, measured_precision=0.85, tier=0, latency_ms=2.0,
                ),
                "responsibility": DetectorOutput(
                    detector_id="sim", tag="responsibility", p_hat=0.01,
                    verifiable=True, measured_precision=0.90, tier=0, latency_ms=1.0,
                ),
            },
        )
        d = decide(risk, copilot_policy, session_id=session_id)
        print(f"  Turn {i+1}: '{req}' -> Action={d.action} (s_t={d.session_risk_after:.4f}, P_eff={d.p_def_effective:.4f})")


if __name__ == "__main__":
    run_screen1_demo()
    run_screen3_demo()
    run_screen4_demo()
