"""Authorization policy gate.

Before any Verity action can be signed, it is checked against an
:class:`ActionPolicy`: per-action autonomous-execution limits, in the
action currency's major units.

* At or below the limit → ``ALLOW`` (the action may be signed and executed
  autonomously).
* Above the limit → ``REQUIRE_ESCALATION`` — not a denial: autonomous
  authority is *bounded*, and a human co-signs the big moves. The pipeline
  routes these to the escalation queue.
* Malformed actions (negative amounts) → ``DENY``.

Escalation itself moves no money and is always permitted. An action type
with no configured limit gets no autonomous authority (fail closed).

This module is working code, verified by ``tests/test_authz.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ActionType(str, Enum):
    SUBMIT_CHALLENGE = "submit_challenge"  # representment via the dispute API
    ACCEPT_DISPUTE = "accept_dispute"  # concede a dispute
    REFUND_ON_ACCEPT = "refund_on_accept"  # refund leg when accepting
    ESCALATE = "escalate"  # hand the case to a human (moves no money)
    TREASURY_SWEEP = "treasury_sweep"  # move recovered funds per sweep policy
    FX_CONVERT = "fx_convert"  # convert swept funds to the home currency


class Verdict(str, Enum):
    ALLOW = "allow"
    REQUIRE_ESCALATION = "require_escalation"
    DENY = "deny"


@dataclass(frozen=True)
class AgentAction:
    """One action the agent wants to take, before authorization."""

    action_type: ActionType
    amount: float  # value at stake (0 for ESCALATE)
    currency: str
    reference: str  # dispute id / sweep reference the action belongs to
    detail: str = ""  # human-readable note, sealed into the envelope


@dataclass(frozen=True)
class ActionPolicy:
    """Autonomous-execution limits per action type.

    A limit of ``None`` (or a missing entry) means the action may never
    execute autonomously — it always needs a human co-sign.
    """

    auto_limits: dict[ActionType, float | None] = field(
        default_factory=lambda: {
            ActionType.SUBMIT_CHALLENGE: 1_000.00,
            ActionType.ACCEPT_DISPUTE: 500.00,
            ActionType.REFUND_ON_ACCEPT: 500.00,
            ActionType.TREASURY_SWEEP: 5_000.00,
            ActionType.FX_CONVERT: 5_000.00,
        }
    )


@dataclass(frozen=True)
class PolicyDecision:
    verdict: Verdict
    reason: str


def check_policy(
    action: AgentAction, policy: ActionPolicy = ActionPolicy()
) -> PolicyDecision:
    """Decide whether ``action`` may execute autonomously under ``policy``."""
    if action.amount < 0:
        return PolicyDecision(Verdict.DENY, "action amount cannot be negative")
    if action.action_type == ActionType.ESCALATE:
        return PolicyDecision(
            Verdict.ALLOW, "escalation moves no money and is always permitted"
        )
    limit = policy.auto_limits.get(action.action_type)
    if limit is None:
        return PolicyDecision(
            Verdict.REQUIRE_ESCALATION,
            f"no autonomous limit configured for {action.action_type.value}; "
            "a human must co-sign",
        )
    if action.amount <= limit:
        return PolicyDecision(
            Verdict.ALLOW,
            f"{action.amount:.2f} {action.currency} is within the autonomous "
            f"limit of {limit:.2f} for {action.action_type.value}",
        )
    return PolicyDecision(
        Verdict.REQUIRE_ESCALATION,
        f"{action.amount:.2f} {action.currency} exceeds the autonomous limit "
        f"of {limit:.2f} for {action.action_type.value}; a human must co-sign",
    )
