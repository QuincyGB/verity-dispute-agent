"""Treasury sweep executor — STUB for the build window.

Dry-run only, following the same honesty rule as the rest of the skeleton:
executing a plan records the intents it *would* place with Airwallex (a
transfer from the settlement to the operating account, preceded by an FX
conversion when the plan says so) and reports ``executed: False``. The
Airwallex Transfers and FX surfaces are documented capabilities (balances,
quotes, conversions, transfers with idempotency keys); wiring the exact
calls against the sandbox is build-window work, so no endpoint paths are
asserted here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .engine import SweepPlan, SweepPolicy


@dataclass
class SweepExecutor:
    policy: SweepPolicy = SweepPolicy()
    intents: list[dict] = field(default_factory=list)  # recorded, never sent

    def execute(self, plan: SweepPlan) -> dict:
        if plan.action == "none":
            return {
                "executed": False,
                "dry_run": True,
                "intents": [],
                "detail": plan.rationale,
            }

        placed: list[dict] = []
        if plan.action == "convert_and_sweep":
            placed.append(
                {
                    "kind": "fx_convert",
                    "amount": plan.amount,
                    "from_currency": plan.currency,
                    "to_currency": plan.target_currency,
                    "status": "TODO-build-window: Airwallex FX conversion call",
                }
            )
        placed.append(
            {
                "kind": "transfer",
                "amount": plan.amount,
                "currency": plan.target_currency,
                "from_account": self.policy.settlement_account,
                "to_account": self.policy.operating_account,
                "status": "TODO-build-window: Airwallex transfer call",
            }
        )
        self.intents.extend(placed)
        return {
            "executed": False,
            "dry_run": True,
            "intents": placed,
            "detail": "dry-run: sweep intents recorded, not sent",
        }
