"""Triage — the expected-value (EV) decision step.

This is the module named in the project spec: given a dispute amount, an
estimated win probability, and the cost of fighting, decide whether Verity
should fight (challenge / representment), accept, or escalate to a human.

The full scoring engine lives in :mod:`app.ev_engine` — it derives the win
probability from the dispute reason type and the completeness of the
assembled evidence package. This module exposes the plain EV math in
isolation (so it can be unit-tested without any models) and a thin
:func:`triage_dispute` wrapper that delegates to that engine.

Formula
-------
::

    EV(challenge) = p(win) * amount - cost_of_fighting

    EV >  +band   -> CHALLENGE   (fight: clearly positive expected value)
    EV <  -band   -> ACCEPT      (let it go: fighting costs more than it returns)
    |EV| <= band  -> ESCALATE    (too close to call — a human decides)

Accepting is the baseline (value ``0`` relative to the moment the dispute
lands, because the disputed amount has already been pulled from the
merchant). See ``docs/architecture.md`` for the full derivation.
"""

from __future__ import annotations

from .ev_engine import Decision, Policy, ScoreResult, score_dispute
from .models import EvidencePackage

__all__ = [
    "Decision",
    "expected_value",
    "triage_decision",
    "triage_dispute",
]


def expected_value(win_probability: float, amount: float, cost: float) -> float:
    """Return the expected value of challenging a dispute.

    Args:
        win_probability: Probability ``p`` (0.0–1.0) that a representment
            reverses the dispute and the amount is returned.
        amount: Disputed amount ``A``, in the dispute currency's major unit.
        cost: Fully-loaded cost ``C`` of preparing and filing one response.

    Returns:
        ``p * A - C``, rounded to 2 decimal places.

    Raises:
        ValueError: If ``win_probability`` is outside [0, 1] or ``amount``
            or ``cost`` is negative.
    """
    if not 0.0 <= win_probability <= 1.0:
        raise ValueError("win_probability must be between 0.0 and 1.0")
    if amount < 0:
        raise ValueError("amount cannot be negative")
    if cost < 0:
        raise ValueError("cost cannot be negative")
    return round(win_probability * amount - cost, 2)


def triage_decision(
    win_probability: float,
    amount: float,
    cost: float = 15.00,
    escalate_band: float = 10.00,
    min_win_probability: float = 0.25,
) -> Decision:
    """Map an EV computation to a CHALLENGE / ACCEPT / ESCALATE decision.

    A win probability below ``min_win_probability`` is never auto-challenged,
    no matter how large the amount — the model's estimate is too unreliable
    in that range, so the safe default is to accept rather than spend.

    TODO (build window): calibrate ``cost``, ``escalate_band``, and
    ``min_win_probability`` against Airwallex sandbox outcomes and any
    historical dispute data a merchant partner can share.
    """
    if win_probability < min_win_probability:
        return Decision.ACCEPT
    ev = expected_value(win_probability, amount, cost)
    if ev > escalate_band:
        return Decision.CHALLENGE
    if ev < -escalate_band:
        return Decision.ACCEPT
    return Decision.ESCALATE


def triage_dispute(
    amount: float,
    reason_type: str,
    package: EvidencePackage,
    policy: Policy = Policy(),
) -> ScoreResult:
    """Score a full dispute (reason type + evidence package) end to end.

    This delegates to :func:`app.ev_engine.score_dispute`, which estimates
    the win probability from the reason base rate and evidence completeness
    and then applies the same EV math as :func:`expected_value`.
    """
    return score_dispute(
        amount=amount, reason_type=reason_type, package=package, policy=policy
    )
