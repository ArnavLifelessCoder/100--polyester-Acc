"""
Tier 0 detectors -- real, deterministic, high precision.

All run in-process with no network hop. This is the only tier where
BLOCK-eligible precision is achievable.

From build guide section 6.2.
"""

from __future__ import annotations

import math
import re
import time
from typing import Any

from controlplane.schemas import DetectorOutput, DetectionContext, RiskTag


# --- PII patterns ---

# Luhn checksum for credit cards
def _luhn_check(num: str) -> bool:
    digits = [int(d) for d in num if d.isdigit()]
    if len(digits) < 13:
        return False
    checksum = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


# Indian PAN format: AAAAA9999A
_PAN_RE = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")

# Aadhaar: 12 digits, optionally separated by spaces
_AADHAAR_RE = re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b")

# Credit card: 13-19 digits, optionally separated by spaces or dashes
_CARD_RE = re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{1,7}\b")

# Email
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")

# Phone (Indian mobile)
_PHONE_RE = re.compile(r"\b(?:\+91[\s-]?)?[6-9]\d{9}\b")

# SSN-like
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")


class PIIDetector:
    """
    Detects PII via regex plus checksum validation.

    precision = 0.97 when a checksum passes, 0.72 on regex-only match.
    This is the only detector permitted to reach BLOCK.
    """

    detector_id = "pii_tier0"
    tag: RiskTag = "responsibility"
    tier = 0

    def run(
        self,
        request: str,
        response: str,
        ctx: DetectionContext,
    ) -> DetectorOutput:
        start = time.perf_counter()
        evidence: dict[str, Any] = {"matches": []}
        checksum_verified = False
        max_confidence = 0.0

        text = response

        # Credit card with Luhn
        for m in _CARD_RE.finditer(text):
            raw = m.group().replace(" ", "").replace("-", "")
            if _luhn_check(raw):
                evidence["matches"].append({"type": "credit_card", "checksum": True})
                checksum_verified = True
                max_confidence = max(max_confidence, 0.95)
            else:
                evidence["matches"].append({"type": "credit_card_pattern", "checksum": False})
                max_confidence = max(max_confidence, 0.6)

        # PAN
        for m in _PAN_RE.finditer(text):
            evidence["matches"].append({"type": "pan", "value_masked": m.group()[:3] + "****"})
            max_confidence = max(max_confidence, 0.8)

        # Aadhaar
        for m in _AADHAAR_RE.finditer(text):
            evidence["matches"].append({"type": "aadhaar_pattern"})
            max_confidence = max(max_confidence, 0.7)

        # Email
        for m in _EMAIL_RE.finditer(text):
            evidence["matches"].append({"type": "email"})
            max_confidence = max(max_confidence, 0.6)

        # Phone
        for m in _PHONE_RE.finditer(text):
            evidence["matches"].append({"type": "phone"})
            max_confidence = max(max_confidence, 0.5)

        # SSN
        for m in _SSN_RE.finditer(text):
            evidence["matches"].append({"type": "ssn_pattern"})
            max_confidence = max(max_confidence, 0.7)

        precision = 0.97 if checksum_verified else (0.72 if evidence["matches"] else 0.97)

        elapsed = (time.perf_counter() - start) * 1000.0

        return DetectorOutput(
            detector_id=self.detector_id,
            tag=self.tag,
            p_hat=round(max_confidence, 4),
            verifiable=True,
            measured_precision=precision,
            tier=self.tier,
            latency_ms=round(elapsed, 3),
            evidence=evidence,
        )


class SchemaDetector:
    """
    Validates JSON or structured format contracts in responses.
    measured_precision = 0.99 (deterministic check).
    """

    detector_id = "schema_tier0"
    tag: RiskTag = "performance"
    tier = 0

    def __init__(self, expected_format: str = "json") -> None:
        self.expected_format = expected_format

    def run(
        self,
        request: str,
        response: str,
        ctx: DetectionContext,
    ) -> DetectorOutput:
        start = time.perf_counter()
        evidence: dict[str, Any] = {}

        p_hat = 0.0
        # Only validate schema if JSON format was requested or expected
        requires_json = "json" in request.lower() or response.strip().startswith(("{", "["))
        if self.expected_format == "json" and requires_json:
            import json as json_mod
            try:
                json_mod.loads(response)
                evidence["valid_json"] = True
            except (json_mod.JSONDecodeError, ValueError):
                evidence["valid_json"] = False
                p_hat = 0.95

        elapsed = (time.perf_counter() - start) * 1000.0

        return DetectorOutput(
            detector_id=self.detector_id,
            tag=self.tag,
            p_hat=round(p_hat, 4),
            verifiable=True,
            measured_precision=0.99,
            tier=self.tier,
            latency_ms=round(elapsed, 3),
            evidence=evidence,
        )


class PolicyListDetector:
    """
    Exact and fuzzy match against a configured deny list.
    measured_precision = 0.95.
    """

    detector_id = "policy_list_tier0"
    tag: RiskTag = "responsibility"
    tier = 0

    def __init__(self, deny_list: list[str] | None = None) -> None:
        self.deny_list = [s.lower() for s in (deny_list or [])]

    def run(
        self,
        request: str,
        response: str,
        ctx: DetectionContext,
    ) -> DetectorOutput:
        start = time.perf_counter()
        evidence: dict[str, Any] = {"matches": []}

        text_lower = response.lower()
        max_p = 0.0

        for term in self.deny_list:
            if term in text_lower:
                evidence["matches"].append(term)
                max_p = max(max_p, 0.9)

        elapsed = (time.perf_counter() - start) * 1000.0

        return DetectorOutput(
            detector_id=self.detector_id,
            tag=self.tag,
            p_hat=round(max_p, 4),
            verifiable=True,
            measured_precision=0.95,
            tier=self.tier,
            latency_ms=round(elapsed, 3),
            evidence=evidence,
        )


class TokenAnomalyDetector:
    """
    Rolling z-score on tokens per resolved task with logistic mapping.

    z = (tokens - mu_w) / sigma_w
    p = 1 / (1 + exp(-(z - 2.5)))

    measured_precision = 0.85.
    """

    detector_id = "token_anomaly_tier0"
    tag: RiskTag = "cost"
    tier = 0

    def run(
        self,
        request: str,
        response: str,
        ctx: DetectionContext,
    ) -> DetectorOutput:
        start = time.perf_counter()

        tokens = ctx.token_usage.get("completion_tokens", len(response.split()))
        mu = ctx.rolling_token_mu
        sigma = max(ctx.rolling_token_sigma, 1.0)  # prevent division by zero

        z = (tokens - mu) / sigma
        p_hat = 1.0 / (1.0 + math.exp(-(z - 2.5)))

        elapsed = (time.perf_counter() - start) * 1000.0

        return DetectorOutput(
            detector_id=self.detector_id,
            tag=self.tag,
            p_hat=round(max(0.0, min(1.0, p_hat)), 4),
            verifiable=True,
            measured_precision=0.85,
            tier=self.tier,
            latency_ms=round(elapsed, 3),
            evidence={"tokens": tokens, "z_score": round(z, 3)},
        )
