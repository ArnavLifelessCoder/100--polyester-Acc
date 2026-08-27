"""
CLI: generate simulated traffic and run it through the engine.

Usage: python -m sim.seed_data

Populates a fresh ledger with 3,000 decisions in under 60 seconds,
deterministically. From build guide section 11.
"""

from __future__ import annotations

import sys
import time

import numpy as np
from pathlib import Path

# Ensure repo root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from controlplane.policy import load_all_policies
from controlplane.engine.decide import decide, get_session_store
from controlplane.cascade import DetectorCascade
from controlplane.ledger import Ledger
from controlplane.schemas import DetectionContext
from sim.generator import generate_traffic
from constants import GLOBAL_SEED

# Fraction of seeded decisions that receive a human verdict. Enterprises
# adjudicate a sample, not everything; 20% keeps the calibration estimate
# usable while staying honest about how labels actually arrive.
ADJUDICATION_SAMPLE_RATE: float = 0.20


def main() -> None:
    print("ControlPlane seed_data: generating 3,000 labelled decisions...")
    start = time.time()

    policies_dir = Path(__file__).resolve().parent.parent / "policies"
    policies = load_all_policies(policies_dir)

    db_path = Path(__file__).resolve().parent.parent / "controlplane.db"
    if db_path.exists():
        db_path.unlink()
    ledger = Ledger(db_path)

    # Seeded with the simulated tier 1 and tier 2 detectors, at their configured
    # TPR and FPR. Tier 0 stays real, so the PII path and its BLOCK-eligible
    # precision still appear in the ledger.
    #
    # Tier 1 and 2 are simulated here on purpose. The generator now pairs each
    # response with the context that supports it, so the real grounding
    # detector does discriminate against this traffic, but it discriminates
    # almost perfectly: the lexical stub scores clean responses at 0.0 and
    # defective ones at 0.98. A ledger seeded from a near-perfect detector
    # makes every downstream quality number look excellent for the wrong
    # reason. The simulated detector runs at a declared TPR and FPR, which is
    # what makes the calibration and EDR/UIR figures worth reading.
    cascade = DetectorCascade(use_real_detectors=False, seed=GLOBAL_SEED)
    get_session_store().clear()

    traffic = generate_traffic(n_total=3000, seed=GLOBAL_SEED)

    label_rng = np.random.default_rng(GLOBAL_SEED + 1)
    label_count = 0

    action_counts: dict[str, int] = {}
    workflow_counts: dict[str, int] = {}
    defect_counts: dict[str, int] = {}

    for i, sample in enumerate(traffic):
        if sample.workflow_id not in policies:
            continue

        policy = policies[sample.workflow_id]
        ctx = sample.to_detection_context()

        risk, tiers_run, latency_ms, cost_units = cascade.run(
            sample.request, sample.response, ctx, policy
        )

        decision = decide(
            risk, policy,
            session_id=sample.session_id,
            tiers_run=tiers_run,
            total_latency_ms=latency_ms,
            estimated_cost_units=cost_units,
        )

        ledger.append(decision)

        # A random audit sample gets a human verdict, so a fresh install has
        # something for EDR, UIR and calibration to read. The sample is random
        # rather than "everything we flagged", because labelling only the
        # interventions would leave escaped defects permanently invisible and
        # bias the calibration fit toward the flagged tail.
        if float(label_rng.random()) < ADJUDICATION_SAMPLE_RATE:
            ledger.add_label(
                decision.decision_id,
                actually_defective=sample.is_defective,
                note="seeded audit sample",
            )
            label_count += 1

        action_counts[decision.action] = action_counts.get(decision.action, 0) + 1
        workflow_counts[sample.workflow_id] = workflow_counts.get(sample.workflow_id, 0) + 1
        if sample.is_defective:
            defect_counts[sample.workflow_id] = defect_counts.get(sample.workflow_id, 0) + 1

        if (i + 1) % 500 == 0:
            print(f"  processed {i + 1}/{len(traffic)}...")

    elapsed = time.time() - start

    # Verify chain
    valid, checked = ledger.verify_chain()

    print(f"\nDone in {elapsed:.1f}s")
    print(f"Total decisions: {ledger.count()}")
    print(f"Hash chain: {'valid' if valid else 'BROKEN'} ({checked} rows)")
    print(f"Human-adjudicated sample: {label_count} decisions "
          f"({ADJUDICATION_SAMPLE_RATE:.0%} audit rate)")
    print(f"\nAction distribution:")
    for action, count in sorted(action_counts.items()):
        print(f"  {action}: {count} ({count/len(traffic)*100:.1f}%)")
    print(f"\nWorkflow distribution:")
    for wid, count in sorted(workflow_counts.items()):
        defects = defect_counts.get(wid, 0)
        print(f"  {wid}: {count} ({defects} defects, {defects/count*100:.1f}%)")

    ledger.close()


if __name__ == "__main__":
    main()
