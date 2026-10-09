"""Authorization gateway — the only door to execution.

Flow for every money-moving action:

1. :meth:`AuthorizationGateway.authorize` runs the policy gate. ``DENY``
   raises :class:`PolicyDeniedError`; ``REQUIRE_ESCALATION`` raises
   :class:`RequiresEscalationError` (the pipeline routes the case to a
   human instead); ``ALLOW`` returns a signed envelope bound to the
   ledger's current head.
2. The executor (e.g. :class:`AuthorizedRepresentmentSubmitter`) calls
   :meth:`AuthorizationGateway.verify_for_execution` with the envelope
   immediately before acting. A missing envelope raises
   :class:`UnsignedActionError`; a tampered or stale one raises
   :class:`InvalidEnvelopeError`. The inner submitter — and therefore the
   Airwallex API — is never touched without a valid envelope.

Working code, verified by ``tests/test_authz.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..ledger import DecisionLedger
from ..models import Dispute, EvidencePackage
from ..ev_engine import ScoreResult
from ..representment import RepresentmentSubmitter, SubmissionResult
from .envelope import ActionEnvelope, sign_action, verify_envelope
from .policy import ActionPolicy, AgentAction, PolicyDecision, Verdict, check_policy


class AuthorizationError(Exception):
    """Base class for authorization failures."""


class UnsignedActionError(AuthorizationError):
    """Execution was attempted with no signed envelope at all."""


class InvalidEnvelopeError(AuthorizationError):
    """The envelope is tampered with, mis-signed, or stale."""


class PolicyDeniedError(AuthorizationError):
    def __init__(self, action: AgentAction, decision: PolicyDecision) -> None:
        super().__init__(
            f"policy denied {action.action_type.value} for {action.reference}: "
            f"{decision.reason}"
        )
        self.action = action
        self.decision = decision


class RequiresEscalationError(AuthorizationError):
    def __init__(self, action: AgentAction, decision: PolicyDecision) -> None:
        super().__init__(
            f"{action.action_type.value} for {action.reference} exceeds "
            f"autonomous authority: {decision.reason}"
        )
        self.action = action
        self.decision = decision


@dataclass
class AuthorizationGateway:
    ledger: DecisionLedger
    policy: ActionPolicy = field(default_factory=ActionPolicy)
    agent_id: str = "verity-agent"

    def authorize(self, action: AgentAction) -> ActionEnvelope:
        """Policy-check ``action`` and, if allowed, return its envelope."""
        decision = check_policy(action, self.policy)
        if decision.verdict is Verdict.DENY:
            raise PolicyDeniedError(action, decision)
        if decision.verdict is Verdict.REQUIRE_ESCALATION:
            raise RequiresEscalationError(action, decision)
        return sign_action(
            action, agent_id=self.agent_id, ledger_head=self.ledger.head_hash
        )

    def verify_for_execution(self, envelope: ActionEnvelope | None) -> ActionEnvelope:
        """The execution-time check. Refuses unsigned/tampered/stale input."""
        if envelope is None:
            raise UnsignedActionError(
                "no signed envelope presented — action refused before execution"
            )
        if not verify_envelope(envelope, current_ledger_head=self.ledger.head_hash):
            raise InvalidEnvelopeError(
                "envelope failed verification (tampered payload/signature or "
                "stale ledger binding) — action refused before execution"
            )
        return envelope


class AuthorizedRepresentmentSubmitter:
    """Representment submitter behind the authorization gateway.

    Wraps :class:`RepresentmentSubmitter`; the challenge is only built and
    sent after the envelope verifies. This is the enforcement point the
    pipeline uses, so an unsigned challenge cannot reach the client.
    """

    def __init__(
        self, inner: RepresentmentSubmitter, gateway: AuthorizationGateway
    ) -> None:
        self.inner = inner
        self.gateway = gateway

    def submit(
        self,
        envelope: ActionEnvelope | None,
        dispute: Dispute,
        package: EvidencePackage,
        score: ScoreResult,
    ) -> SubmissionResult:
        self.gateway.verify_for_execution(envelope)
        return self.inner.submit(dispute, package, score)
