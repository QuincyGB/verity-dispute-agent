"""Signed action envelopes.

An authorized action is sealed into an :class:`ActionEnvelope`:

* the canonical action payload (type, amount, currency, reference, detail),
* a SHA-256 ``payload_hash`` over that payload,
* the decision ledger's head hash at signing time — the envelope is bound
  to the exact audit state it was authorized under, so if the ledger
  advances before execution, the envelope is stale and refused, and
* a ``signature`` over (payload hash + ledger binding + issue time).

SIGNATURE HONESTY: Visa TAP's real signature scheme, agent identity
registration, and partner keys require Visa's partner documentation and are
a build-window TODO. The signer here uses clearly-labelled placeholder
material so the envelope *discipline* — canonicalization, binding,
verification, tamper evidence — is real, working, and unit-tested today,
while the cryptographic identity itself is a stand-in. Nothing in this
module is a credential, and the placeholder must never be presented as a
Visa-issued signature.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone

from .policy import ActionType, AgentAction

ENVELOPE_VERSION = "verity.authz/1"

# NOT a credential. Stand-in key material so the placeholder signature is
# deterministic and testable until real TAP key material exists. If this
# string ever looks like a secret, something has gone wrong.
PLACEHOLDER_SIGNING_MATERIAL = "verity-tap-placeholder-not-a-credential"


def _canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def _action_payload(action: AgentAction) -> dict:
    return {
        "action_type": action.action_type.value,
        "amount": action.amount,
        "currency": action.currency,
        "reference": action.reference,
        "detail": action.detail,
    }


def _signature(payload_hash: str, ledger_head: str, issued_at: str) -> str:
    body = {
        "material": PLACEHOLDER_SIGNING_MATERIAL,
        "payload_hash": payload_hash,
        "ledger_head": ledger_head,
        "issued_at": issued_at,
    }
    return hashlib.sha256(_canonical(body)).hexdigest()


@dataclass(frozen=True)
class ActionEnvelope:
    version: str
    agent_id: str
    action_type: str
    amount: float
    currency: str
    reference: str
    detail: str
    payload_hash: str
    ledger_head: str  # decision-ledger head the envelope is bound to
    issued_at: str  # ISO-8601 UTC
    signature: str

    def action(self) -> AgentAction:
        return AgentAction(
            action_type=ActionType(self.action_type),
            amount=self.amount,
            currency=self.currency,
            reference=self.reference,
            detail=self.detail,
        )

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "agent_id": self.agent_id,
            "action_type": self.action_type,
            "amount": self.amount,
            "currency": self.currency,
            "reference": self.reference,
            "detail": self.detail,
            "payload_hash": self.payload_hash,
            "ledger_head": self.ledger_head,
            "issued_at": self.issued_at,
            "signature": self.signature,
        }


def sign_action(
    action: AgentAction,
    *,
    agent_id: str,
    ledger_head: str,
    issued_at: datetime | None = None,
) -> ActionEnvelope:
    """Seal ``action`` into a signed envelope bound to ``ledger_head``."""
    ts = (issued_at or datetime.now(timezone.utc)).isoformat()
    payload_hash = hashlib.sha256(_canonical(_action_payload(action))).hexdigest()
    return ActionEnvelope(
        version=ENVELOPE_VERSION,
        agent_id=agent_id,
        action_type=action.action_type.value,
        amount=action.amount,
        currency=action.currency,
        reference=action.reference,
        detail=action.detail,
        payload_hash=payload_hash,
        ledger_head=ledger_head,
        issued_at=ts,
        signature=_signature(payload_hash, ledger_head, ts),
    )


def verify_envelope(envelope: ActionEnvelope, *, current_ledger_head: str) -> bool:
    """Pure verification: payload integrity, signature, and fresh binding.

    Returns False if the action fields were tampered with, the signature
    does not match, or the ledger has advanced since signing (stale
    binding — the authorization no longer reflects current audit state).
    """
    expected_hash = hashlib.sha256(
        _canonical(_action_payload(envelope.action()))
    ).hexdigest()
    if envelope.payload_hash != expected_hash:
        return False
    expected_sig = _signature(
        envelope.payload_hash, envelope.ledger_head, envelope.issued_at
    )
    if envelope.signature != expected_sig:
        return False
    return envelope.ledger_head == current_ledger_head
