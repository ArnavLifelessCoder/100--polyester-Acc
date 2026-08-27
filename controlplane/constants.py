"""
Assumption-tagged constants from controlplane_round2_annex.md.

Every value here corresponds to a named assumption (A1-A13) in the annex.
If a value appears in engine code without being traced here, it is a bug.
"""

from __future__ import annotations

# A6: economic parameters for threshold derivation
UTILITY_LOSS_BLOCK: float = 200.0  # U -- utility destroyed when blocking a fine response
FRICTION_BLOCK: float = 50.0       # F_b -- fixed cost of executing a block
HUMAN_REVIEW_COST: float = 120.0   # H -- all-in cost of a human escalation
HUMAN_CATCH_RATE: float = 0.9      # a_h -- fraction of true defects a human reviewer catches

# A6a: utility loss of an escalation, corrected.
#
# The original A6 table set U(ESCALATE) = U(BLOCK) = 200. That made ESCALATE
# strictly dominated by BLOCK for every p and every workflow, because
#   L(ESCALATE) - L(BLOCK) = 0.1 * p * C * iota + (F_e - F_b) + (1-p) * (U_e - U_b)
# collapses to 0.1 * p * C * iota + 70 > 0 when U_e == U_b.
# ESCALATE could therefore never be the argmin, and the seeded ledger contained
# zero escalations across 3,011 decisions.
#
# Escalation delays a response pending human review, it does not destroy it.
# A blocked response is gone and the user gets a fallback; an escalated response
# is delivered late. The utility loss of a delay is a fraction of the utility
# loss of a drop.
UTILITY_LOSS_ESCALATE: float = 40.0  # U_e -- utility lost to review delay, not destruction

# A8: tag independence factors (kappa)
DEFAULT_KAPPA_PERF_RESP: float = 0.4   # performance-responsibility pair
DEFAULT_KAPPA_PERF_COST: float = 0.9   # performance-cost pair
DEFAULT_KAPPA_COST_RESP: float = 0.9   # cost-responsibility pair

# A9: joint consequence discount
DEFAULT_LAMBDA: float = 0.3

# A10: session risk decay per turn
GAMMA: float = 0.85

# A11: session carry blending factor
BETA: float = 0.50

# A12: default irreversibility by action type
IOTA_PAYMENTS: float = 1.0
IOTA_RECORD_WRITE: float = 0.6
IOTA_DRAFT: float = 0.2

# A13: cascade routing defaults
DEFAULT_Q1: float = 0.08   # fraction routed to tier 1
DEFAULT_Q2: float = 0.015  # fraction routed to tier 2

# Tier latency budgets (ms) from annex 3.9
TIER0_LATENCY_MS: float = 12.0
TIER1_LATENCY_MS: float = 90.0
TIER2_LATENCY_MS: float = 450.0

# Tier cost as fraction of one generation
TIER0_COST_FRAC: float = 0.001
TIER1_COST_FRAC: float = 0.02
TIER2_COST_FRAC: float = 0.35

# Severity cap precision thresholds (annex 3.3)
PRECISION_BLOCK: float = 0.95
PRECISION_ESCALATE: float = 0.70
PRECISION_CONSTRAIN: float = 0.40

# C_eff trigger threshold -- tags below this p_hat do not add consequence
CEFF_TRIGGER_THRESHOLD: float = 0.05

# Token anomaly detector logistic midpoint (annex 6.2)
TOKEN_ANOMALY_MIDPOINT: float = 2.5

# Workflow baseline token statistics for the rolling z-score.
#
# These are the defaults used when a caller supplies no rolling statistics.
# The previous defaults (mu=0, sigma=1) made z equal the raw token count, so a
# 30-token response scored z=30 and the cost tag saturated at p_hat=1.0. That
# pinned P_def at 1.0 on every demo screen and made the consequence model
# invisible. Any caller with real traffic statistics should pass its own.
TOKEN_BASELINE_MU: float = 50.0
TOKEN_BASELINE_SIGMA: float = 20.0

# EWMA alpha for token statistics
EWMA_ALPHA: float = 0.1

# Retry loop cosine similarity threshold
RETRY_LOOP_COSINE_THRESHOLD: float = 0.95

# Simulated traffic target counts (A1)
SIM_SUPPORT_COUNT: int = 1615   # ~70k/130k * 3000
SIM_COPILOT_COUNT: int = 1038   # ~45k/130k * 3000
SIM_DECISION_COUNT: int = 347   # ~15k/130k * 3000

# A2: defect rates by workflow
DEFECT_RATE_SUPPORT: float = 0.025
DEFECT_RATE_COPILOT: float = 0.030
DEFECT_RATE_DECISION: float = 0.015

# Seed for deterministic simulation
GLOBAL_SEED: int = 42
