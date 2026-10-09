"""Treasury sweep policy engine.

Pure, deterministic policy logic — no I/O, no randomness:

* A recovery lands (dispute won / refund settled) in the settlement balance.
* Everything above the per-currency operating minimum is excess.
* Excess in the home currency → sweep to the operating account.
* Excess in a foreign currency → convert-then-sweep **only** when the
  current rate (home-currency units per 1 unit of foreign) meets the policy
  threshold; otherwise sweep unconverted — Verity does not sell currency at
  a rate the merchant's policy calls bad just because cash arrived.

Working code, verified by ``tests/test_treasury.py``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RecoveryEvent:
    """Funds that just landed in the settlement balance."""

    source: str  # "dispute_won" | "refund_settled"
    reference: str  # dispute id the recovery belongs to
    amount: float  # in `currency` major units
    currency: str


@dataclass(frozen=True)
class SweepPolicy:
    operating_minimum: float = 250.00  # floor kept in the settlement balance
    home_currency: str = "USD"
    fx_convert_threshold: float | None = None  # min acceptable rate to convert
    settlement_account: str = "settlement"
    operating_account: str = "operating"


@dataclass(frozen=True)
class SweepPlan:
    action: str  # "none" | "sweep" | "convert_and_sweep"
    amount: float  # amount to move (0.0 when action == "none")
    currency: str  # currency the amount starts in
    target_currency: str  # currency it ends in after the plan
    balance_after_recovery: float  # settlement balance incl. the recovery
    rationale: str

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "amount": self.amount,
            "currency": self.currency,
            "target_currency": self.target_currency,
            "balance_after_recovery": self.balance_after_recovery,
            "rationale": self.rationale,
        }


def plan_sweep(
    event: RecoveryEvent,
    *,
    settlement_balance: float,
    fx_rates: dict[str, float] | None = None,
    policy: SweepPolicy = SweepPolicy(),
) -> SweepPlan:
    """Plan the sweep for one recovery.

    ``settlement_balance`` is the balance *before* the recovery lands;
    ``fx_rates`` maps a foreign currency to home-currency units per 1 unit
    of that currency.
    """
    if event.amount < 0:
        raise ValueError("recovery amount cannot be negative")

    after = round(settlement_balance + event.amount, 2)
    excess = round(after - policy.operating_minimum, 2)

    if excess <= 0:
        return SweepPlan(
            action="none",
            amount=0.0,
            currency=event.currency,
            target_currency=event.currency,
            balance_after_recovery=after,
            rationale=(
                f"balance after recovery is {after:.2f} {event.currency}, at or "
                f"below the operating minimum of {policy.operating_minimum:.2f}; "
                "nothing to sweep"
            ),
        )

    if event.currency == policy.home_currency:
        return SweepPlan(
            action="sweep",
            amount=excess,
            currency=event.currency,
            target_currency=policy.home_currency,
            balance_after_recovery=after,
            rationale=(
                f"{excess:.2f} {event.currency} sits above the operating "
                f"minimum of {policy.operating_minimum:.2f}; sweep to the "
                "operating account"
            ),
        )

    rate = (fx_rates or {}).get(event.currency)
    threshold = policy.fx_convert_threshold
    if threshold is not None and rate is not None and rate >= threshold:
        return SweepPlan(
            action="convert_and_sweep",
            amount=excess,
            currency=event.currency,
            target_currency=policy.home_currency,
            balance_after_recovery=after,
            rationale=(
                f"rate {rate} {policy.home_currency}/{event.currency} meets the "
                f"policy threshold of {threshold}; convert {excess:.2f} "
                f"{event.currency} and sweep to the operating account"
            ),
        )

    why = (
        f"rate {rate} is below the policy threshold of {threshold}"
        if (rate is not None and threshold is not None)
        else "no acceptable conversion rate available"
    )
    return SweepPlan(
        action="sweep",
        amount=excess,
        currency=event.currency,
        target_currency=event.currency,
        balance_after_recovery=after,
        rationale=(
            f"{excess:.2f} {event.currency} is above the operating minimum but "
            f"{why}; sweep unconverted and convert later"
        ),
    )
