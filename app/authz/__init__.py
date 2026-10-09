"""Authorization layer — Visa TAP-style agent identity & policy gating.

Every money-moving action Verity takes (submitting a challenge, accepting a
dispute, sweeping recovered funds, converting currency) must first pass the
policy gate in :mod:`app.authz.policy` and be sealed in a signed envelope
(:mod:`app.authz.envelope`) bound to the decision ledger's current head.
The submitter refuses anything else — see :mod:`app.authz.gateway`.

This is the *design + local implementation* of a Visa Trusted Access
Protocol (TAP) style flow. TAP is Visa's framework for giving AI agents a
verifiable identity and scoped, signed authority to act. The exact TAP
integration — agent identity registration with Visa, Visa's signature
scheme, partner endpoints and keys — requires Visa's partner documentation
and credentials and is a build-window TODO, labelled as such everywhere it
appears. What is implemented and tested here is the authorization
discipline itself: policy check → canonical signed envelope → verification
at execution time.
"""

from .envelope import ActionEnvelope, sign_action, verify_envelope
from .gateway import (
    AuthorizationError,
    AuthorizationGateway,
    AuthorizedRepresentmentSubmitter,
    InvalidEnvelopeError,
    PolicyDeniedError,
    RequiresEscalationError,
    UnsignedActionError,
)
from .policy import (
    ActionPolicy,
    ActionType,
    AgentAction,
    PolicyDecision,
    Verdict,
    check_policy,
)

__all__ = [
    "ActionEnvelope",
    "ActionPolicy",
    "ActionType",
    "AgentAction",
    "AuthorizationError",
    "AuthorizationGateway",
    "AuthorizedRepresentmentSubmitter",
    "InvalidEnvelopeError",
    "PolicyDecision",
    "PolicyDeniedError",
    "RequiresEscalationError",
    "UnsignedActionError",
    "Verdict",
    "check_policy",
    "sign_action",
    "verify_envelope",
]
