"""Tests for the TAP-style authorization layer (app/authz)."""

from dataclasses import replace

import pytest

from app.airwallex_client import AirwallexClient
from app.authz import (
    ActionType,
    AgentAction,
    AuthorizationGateway,
    AuthorizedRepresentmentSubmitter,
    InvalidEnvelopeError,
    PolicyDeniedError,
    RequiresEscalationError,
    UnsignedActionError,
    Verdict,
    check_policy,
    sign_action,
    verify_envelope,
)
from app.config import Settings
from app.ev_engine import Policy as EVPolicy
from app.ev_engine import score_dispute
from app.ledger import DecisionLedger
from app.models import Dispute, EvidencePackage
from app.representment import RepresentmentSubmitter


def action(**overrides) -> AgentAction:
    base = dict(
        action_type=ActionType.SUBMIT_CHALLENGE,
        amount=200.0,
        currency="USD",
        reference="dst_test",
        detail="representment per EV decision",
    )
    base.update(overrides)
    return AgentAction(**base)


# --- policy gate ------------------------------------------------------------


def test_challenge_within_limit_is_allowed():
    decision = check_policy(action(amount=200.0))
    assert decision.verdict is Verdict.ALLOW


def test_challenge_above_limit_requires_escalation():
    decision = check_policy(action(amount=5_000.0))
    assert decision.verdict is Verdict.REQUIRE_ESCALATION
    assert "exceeds the autonomous limit" in decision.reason


def test_negative_amount_is_denied():
    decision = check_policy(action(amount=-1.0))
    assert decision.verdict is Verdict.DENY


def test_escalation_action_is_always_allowed():
    decision = check_policy(action(action_type=ActionType.ESCALATE, amount=0.0))
    assert decision.verdict is Verdict.ALLOW


def test_gateway_authorize_raises_for_over_limit_and_denied():
    gateway = AuthorizationGateway(ledger=DecisionLedger())
    with pytest.raises(RequiresEscalationError):
        gateway.authorize(action(amount=5_000.0))
    with pytest.raises(PolicyDeniedError):
        gateway.authorize(action(amount=-5.0))


# --- envelopes ---------------------------------------------------------------


def test_signed_envelope_verifies_against_signing_head():
    ledger = DecisionLedger()
    gateway = AuthorizationGateway(ledger=ledger)
    envelope = gateway.authorize(action())
    assert verify_envelope(envelope, current_ledger_head=ledger.head_hash)
    assert gateway.verify_for_execution(envelope) is envelope


def test_tampered_envelope_fails_verification():
    envelope = sign_action(action(), agent_id="verity-agent", ledger_head="abc")
    tampered = replace(envelope, amount=999_999.0)
    assert not verify_envelope(tampered, current_ledger_head="abc")
    forged = replace(envelope, signature="0" * 64)
    assert not verify_envelope(forged, current_ledger_head="abc")


def test_envelope_goes_stale_when_ledger_advances():
    ledger = DecisionLedger()
    gateway = AuthorizationGateway(ledger=ledger)
    envelope = gateway.authorize(action())
    ledger.append("dst_other", "challenge", {"note": "unrelated decision"})
    with pytest.raises(InvalidEnvelopeError):
        gateway.verify_for_execution(envelope)


# --- execution enforcement ---------------------------------------------------


def _dispute_package_score():
    dispute = Dispute.model_validate(
        {
            "id": "dst_test",
            "amount": 200.0,
            "currency": "USD",
            "stage": "CHARGEBACK",
            "status": "REQUIRES_RESPONSE",
            "reason": {"type": "FRAUDULENT"},
        }
    )
    package = EvidencePackage(dispute_id=dispute.id)
    score = score_dispute(200.0, "FRAUDULENT", package, EVPolicy())
    return dispute, package, score


def test_unsigned_challenge_is_rejected_before_the_client_is_touched():
    client = AirwallexClient(settings=Settings())
    gateway = AuthorizationGateway(ledger=DecisionLedger())
    submitter = AuthorizedRepresentmentSubmitter(
        RepresentmentSubmitter(client), gateway
    )
    dispute, package, score = _dispute_package_score()
    with pytest.raises(UnsignedActionError):
        submitter.submit(None, dispute, package, score)
    assert client.recorded_calls == []  # refusal happened before any API call


def test_authorized_challenge_reaches_the_submitter():
    client = AirwallexClient(settings=Settings())
    ledger = DecisionLedger()
    gateway = AuthorizationGateway(ledger=ledger)
    submitter = AuthorizedRepresentmentSubmitter(
        RepresentmentSubmitter(client), gateway
    )
    dispute, package, score = _dispute_package_score()
    envelope = gateway.authorize(action())
    result = submitter.submit(envelope, dispute, package, score)
    assert result.dry_run is True
    assert result.submitted is False  # dry-run honesty survives the gate


# --- pipeline wiring -----------------------------------------------------------


def _pipeline_dispute(**overrides) -> Dispute:
    base = {
        "id": "dst_gate",
        "amount": 200.0,
        "currency": "USD",
        "stage": "CHARGEBACK",
        "status": "REQUIRES_RESPONSE",
        "reason": {"description": "Other Fraud", "original_code": "10.4", "type": "FRAUDULENT"},
        "merchant_order_id": "demo-order-1",  # full evidence in DemoRecords
    }
    base.update(overrides)
    return Dispute.model_validate(base)


def test_pipeline_challenge_carries_a_signed_envelope():
    from app.pipeline import Pipeline

    pipe = Pipeline.demo()
    outcome = pipe.handle_dispute(_pipeline_dispute())
    assert outcome["decision"] == "challenge"
    assert outcome["authorization"]["verdict"] == "allow"
    envelope = outcome["authorization"]["envelope"]
    assert envelope["action_type"] == "submit_challenge"
    assert envelope["signature"]  # sealed
    assert pipe.ledger.verify() is True


def test_pipeline_over_limit_challenge_is_rerouted_to_a_human():
    from app.pipeline import Pipeline

    pipe = Pipeline.demo()
    outcome = pipe.handle_dispute(_pipeline_dispute(id="dst_big", amount=5_000.0))
    # The EV engine wants to fight, but 5,000 exceeds the 1,000 autonomous
    # challenge limit — the gate sends it to a human instead of executing.
    assert outcome["decision"] == "escalate"
    assert outcome["authorization"]["verdict"] == "require_escalation"
    assert len(pipe.escalations) == 1
    assert "submission" not in outcome  # nothing reached the submitter
    assert pipe.ledger.verify() is True
