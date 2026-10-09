"""Treasury sweep — what happens to money Verity wins back.

Deliberately *thin*: when a dispute is won (or a refund-on-accept settles),
recovered funds land in the merchant's settlement balance and would
otherwise sit idle. The sweep policy engine (:mod:`app.treasury.engine`)
decides — deterministically, with the reasoning recorded — how much moves
to the operating account, keeping an operating minimum behind, and whether
a foreign-currency recovery is converted now (rate at/above a policy
threshold) or swept unconverted to convert later.

The engine is working, tested code. Moving the money is not:
:mod:`app.treasury.executor` is a dry-run stub that records the Airwallex
transfer / FX intents it *would* place and reports ``executed: False``.
"""

from .engine import RecoveryEvent, SweepPlan, SweepPolicy, plan_sweep
from .executor import SweepExecutor

__all__ = [
    "RecoveryEvent",
    "SweepExecutor",
    "SweepPlan",
    "SweepPolicy",
    "plan_sweep",
]
