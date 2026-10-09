"""Smoke tests for the wired pipeline (demo records, dry-run client)."""

from app.models import Dispute
from app.pipeline import Pipeline


def dispute(**overrides) -> Dispute:
    base = {
        "id": "dst_smoke",
        "amount": 200.0,
        "currency": "USD",
        "stage": "CHARGEBACK",
        "status": "REQUIRES_RESPONSE",
        "reason": {"description": "Other Fraud", "original_code": "10.4", "type": "FRAUDULENT"},
        "merchant_order_id": "demo-order-1",
    }
    base.update(overrides)
    return Dispute.model_validate(base)


def test_full_evidence_dispute_challenges_in_dry_run():
    pipe = Pipeline.demo()
    outcome = pipe.handle_dispute(dispute())
    assert outcome["decision"] == "challenge"
    assert outcome["submission"]["dry_run"] is True
    assert outcome["submission"]["submitted"] is False  # dry runs never fake a send
    assert pipe.ledger.verify() is True


def test_thin_evidence_dispute_escalates():
    pipe = Pipeline.demo()
    outcome = pipe.handle_dispute(dispute(id="dst_thin", amount=40.0, merchant_order_id="other"))
    assert outcome["decision"] == "escalate"
    assert len(pipe.escalations) == 1
    assert "ESCALATION" in outcome["escalation_summary"]


def test_small_prechargeback_is_skipped_for_airwallex_auto_accept():
    pipe = Pipeline.demo()
    outcome = pipe.handle_dispute(dispute(stage="PRE_CHARGEBACK", amount=25.0))
    assert outcome["action"] == "skip"
