"""Expected-value scoring engine — Verity's decision core.

This module is *working code*, not a stub: the math below is the exact math
the unit tests in ``tests/test_ev_engine.py`` verify.

Model
-----
When a dispute arrives, the disputed amount has already been pulled from the
merchant. Two moves matter:

* **Accept** — the money stays gone. Baseline value: ``0`` (relative to the
  moment the dispute lands; the amount is already lost).
* **Challenge (representment)** — pay a response cost ``C`` (staff/agent time,
  tooling). With probability ``p`` the issuer reverses the dispute and the
  amount ``A`` comes back; with probability ``1 - p`` it doesn't.

    EV(challenge) = p * A - C

Verity challenges when EV is clearly positive, accepts when it is clearly
negative, and **escalates to a human** inside an uncertainty band around zero
(or below a minimum win-probability floor) — the cases where the model is
least confident are exactly the cases a person should eyeball.

Win probability
---------------
``p`` combines a per-reason-type base rate with the assembled evidence's
completeness score::

    p = clamp(base_rate + (completeness - 0.5) * sensitivity, 0.02, 0.97)

The base rates are *starting heuristics* (documented as such — they are not
measured issuer statistics) that the build window will calibrate against the
sandbox and any historical dispute data the merchant can share.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .models import EvidenceKind, EvidencePackage

# --- Heuristic base rates by Airwallex reason `type` ------------------------
# Starting points only. Unknown types fall back to DEFAULT_BASE_RATE.
BASE_RATES: dict[str, float] = {
    "FRAUDULENT": 0.45,  # strong delivery/IP evidence often wins these
    "PRODUCT_NOT_RECEIVED": 0.55,  # tracking + POD is decisive when present
    "PRODUCT_UNACCEPTABLE": 0.35,  # subjective — harder to win
    "DUPLICATE": 0.70,  # provable from records when true
    "SUBSCRIPTION_CANCELED": 0.50,
    "UNRECOGNIZABLE": 0.55,
    "CREDIT_NOT_PROCESSED": 0.40,
    "GENERAL": 0.40,
}
DEFAULT_BASE_RATE = 0.40

# Weight of each evidence kind toward package completeness (sums to 1.0).
EVIDENCE_WEIGHTS: dict[EvidenceKind, float] = {
    EvidenceKind.RECEIPT: 0.25,
    EvidenceKind.DELIVERY_PROOF: 0.25,
    EvidenceKind.TERMS_ACCEPTANCE: 0.15,
    EvidenceKind.CUSTOMER_COMMS: 0.15,
    EvidenceKind.SERVICE_PROOF: 0.10,
    EvidenceKind.REFUND_PROOF: 0.10,
    EvidenceKind.OTHER: 0.0,
}

SENSITIVITY = 0.6  # how far completeness can move p away from the base rate
P_MIN = 0.02
P_MAX = 0.97


class Decision(str, Enum):
    CHALLENGE = "challenge"
    ACCEPT = "accept"
    ESCALATE = "escalate"  # borderline — a human decides


@dataclass(frozen=True)
class Policy:
    """Tunables for the challenge / accept / escalate bands."""

    response_cost: float = 15.00  # fully-loaded cost of one response, in the
    #                                 dispute currency's major unit
    escalate_band: float = 10.00  # |EV| below this → human review
    min_win_probability: float = 0.25  # never auto-challenge below this p


@dataclass(frozen=True)
class ScoreResult:
    decision: Decision
    expected_value: float
    win_probability: float
    completeness: float
    base_rate: float
    rationale: str


def completeness_score(package: EvidencePackage) -> float:
    """Weighted completeness of an evidence package, 0.0–1.0."""
    present = package.kinds_present
    return round(sum(w for k, w in EVIDENCE_WEIGHTS.items() if k in present), 4)


def estimate_win_probability(reason_type: str, completeness: float) -> float:
    """Blend the reason base rate with evidence completeness."""
    base = BASE_RATES.get(reason_type.upper(), DEFAULT_BASE_RATE)
    p = base + (completeness - 0.5) * SENSITIVITY
    return round(min(P_MAX, max(P_MIN, p)), 4)


def score_dispute(
    amount: float,
    reason_type: str,
    package: EvidencePackage,
    policy: Policy = Policy(),
) -> ScoreResult:
    """Score one dispute and return a challenge / accept / escalate call."""
    if amount < 0:
        raise ValueError("dispute amount cannot be negative")

    completeness = completeness_score(package)
    p = estimate_win_probability(reason_type, completeness)
    base = BASE_RATES.get(reason_type.upper(), DEFAULT_BASE_RATE)
    ev = round(p * amount - policy.response_cost, 2)

    if p < policy.min_win_probability:
        decision = Decision.ACCEPT
        why = (
            f"win probability {p:.0%} is below the {policy.min_win_probability:.0%} "
            "auto-challenge floor"
        )
    elif ev > policy.escalate_band:
        decision = Decision.CHALLENGE
        why = f"EV {ev:.2f} is clearly positive (band ±{policy.escalate_band:.2f})"
    elif ev < -policy.escalate_band:
        decision = Decision.ACCEPT
        why = f"EV {ev:.2f} is clearly negative (band ±{policy.escalate_band:.2f})"
    else:
        decision = Decision.ESCALATE
        why = f"EV {ev:.2f} sits inside the ±{policy.escalate_band:.2f} human-review band"

    return ScoreResult(
        decision=decision,
        expected_value=ev,
        win_probability=p,
        completeness=completeness,
        base_rate=base,
        rationale=why,
    )
