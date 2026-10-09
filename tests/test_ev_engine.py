"""Unit tests for the EV scoring engine (app/ev_engine.py)."""

import pytest

from app.ev_engine import (
    Decision,
    Policy,
    completeness_score,
    estimate_win_probability,
    score_dispute,
)
from app.models import EvidenceItem, EvidenceKind, EvidencePackage

H = EvidenceItem.hash_bytes


def package(*kinds: EvidenceKind) -> EvidencePackage:
    return EvidencePackage(
        dispute_id="dst_test",
        items=[
            EvidenceItem(kind=k, label=k.value, sha256=H(k.value.encode()))
            for k in kinds
        ],
    )


FULL = package(
    EvidenceKind.RECEIPT,
    EvidenceKind.DELIVERY_PROOF,
    EvidenceKind.TERMS_ACCEPTANCE,
    EvidenceKind.CUSTOMER_COMMS,
    EvidenceKind.SERVICE_PROOF,
    EvidenceKind.REFUND_PROOF,
)
EMPTY = package()


def test_completeness_full_and_empty():
    assert completeness_score(FULL) == 1.0
    assert completeness_score(EMPTY) == 0.0


def test_completeness_weights():
    # receipt 0.25 + delivery proof 0.25 = 0.50
    assert completeness_score(package(EvidenceKind.RECEIPT, EvidenceKind.DELIVERY_PROOF)) == 0.5


def test_win_probability_blend_and_clamps():
    # FRAUDULENT base 0.45, completeness 1.0 -> 0.45 + 0.5 * 0.6 = 0.75
    assert estimate_win_probability("FRAUDULENT", 1.0) == 0.75
    # completeness 0.0 -> 0.45 - 0.3 = 0.15
    assert estimate_win_probability("FRAUDULENT", 0.0) == 0.15
    # unknown reason type falls back to the default base rate 0.40
    assert estimate_win_probability("SOMETHING_NEW", 0.5) == 0.40
    # clamps: DUPLICATE base 0.70 with full evidence -> 1.00 clamped to 0.97
    assert estimate_win_probability("DUPLICATE", 1.0) == 0.97
    # lower clamp 0.02
    assert estimate_win_probability("PRODUCT_UNACCEPTABLE", 0.0) == 0.05  # 0.35-0.30


def test_ev_math_and_challenge_decision():
    # amount 200, p = 0.75 -> EV = 150 - 15 = 135 -> CHALLENGE
    result = score_dispute(200.0, "FRAUDULENT", FULL)
    assert result.win_probability == 0.75
    assert result.expected_value == 135.0
    assert result.decision == Decision.CHALLENGE


def test_accept_when_ev_clearly_negative():
    # DUPLICATE with no evidence: p = 0.70 - 0.30 = 0.40; amount 10 ->
    # EV = 4 - 15 = -11 -> outside the ±10 band on the low side -> ACCEPT.
    # Use PRODUCT_UNACCEPTABLE to also exercise a low base rate.
    result = score_dispute(10.0, "PRODUCT_NOT_RECEIVED", EMPTY)
    # base 0.55, completeness 0 -> p = 0.25; EV = 2.5 - 15 = -12.5 -> ACCEPT
    assert result.win_probability == 0.25
    assert result.expected_value == -12.5
    assert result.decision == Decision.ACCEPT


def test_escalate_inside_band():
    # amount 40, FRAUDULENT, receipt only: completeness 0.25 ->
    # p = 0.45 + (0.25-0.5)*0.6 = 0.30; EV = 12 - 15 = -3 -> inside band -> ESCALATE
    result = score_dispute(40.0, "FRAUDULENT", package(EvidenceKind.RECEIPT))
    assert result.win_probability == 0.30
    assert result.expected_value == -3.0
    assert result.decision == Decision.ESCALATE


def test_low_probability_floor_forces_accept():
    # p below the 0.25 floor -> ACCEPT regardless of amount size.
    # PRODUCT_UNACCEPTABLE, no evidence: p = 0.05
    result = score_dispute(10_000.0, "PRODUCT_UNACCEPTABLE", EMPTY)
    assert result.win_probability == 0.05
    assert result.decision == Decision.ACCEPT


def test_custom_policy_changes_bands():
    strict = Policy(response_cost=15.0, escalate_band=200.0, min_win_probability=0.10)
    result = score_dispute(200.0, "FRAUDULENT", FULL, policy=strict)
    # EV 135 is inside a ±200 band -> ESCALATE under the strict policy
    assert result.decision == Decision.ESCALATE


def test_negative_amount_rejected():
    with pytest.raises(ValueError):
        score_dispute(-5.0, "GENERAL", EMPTY)
