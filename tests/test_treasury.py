"""Tests for the treasury sweep module (app/treasury) and its pipeline wiring."""

import pytest

from app.models import Dispute
from app.pipeline import Pipeline
from app.treasury import RecoveryEvent, SweepExecutor, SweepPolicy, plan_sweep

POLICY = SweepPolicy(
    operating_minimum=250.0, home_currency="USD", fx_convert_threshold=0.90
)


def event(**overrides) -> RecoveryEvent:
    base = dict(
        source="dispute_won", reference="dst_won", amount=200.0, currency="USD"
    )
    base.update(overrides)
    return RecoveryEvent(**base)


# --- policy engine -----------------------------------------------------------


def test_balance_at_or_below_minimum_sweeps_nothing():
    plan = plan_sweep(event(amount=100.0), settlement_balance=100.0, policy=POLICY)
    assert plan.action == "none"
    assert plan.amount == 0.0
    assert plan.balance_after_recovery == 200.0


def test_home_currency_excess_is_swept():
    plan = plan_sweep(event(amount=200.0), settlement_balance=300.0, policy=POLICY)
    assert plan.action == "sweep"
    assert plan.amount == 250.0  # (300 + 200) - 250 minimum
    assert plan.target_currency == "USD"


def test_foreign_recovery_converts_when_rate_meets_threshold():
    plan = plan_sweep(
        event(currency="EUR", amount=400.0),
        settlement_balance=100.0,
        fx_rates={"EUR": 1.08},
        policy=POLICY,
    )
    assert plan.action == "convert_and_sweep"
    assert plan.amount == 250.0
    assert plan.target_currency == "USD"


def test_foreign_recovery_sweeps_unconverted_below_threshold():
    plan = plan_sweep(
        event(currency="EUR", amount=400.0),
        settlement_balance=100.0,
        fx_rates={"EUR": 0.80},
        policy=POLICY,
    )
    assert plan.action == "sweep"
    assert plan.target_currency == "EUR"  # held, not sold at a bad rate


def test_negative_recovery_is_rejected():
    with pytest.raises(ValueError):
        plan_sweep(event(amount=-1.0), settlement_balance=0.0, policy=POLICY)


# --- executor (dry-run stub) ---------------------------------------------------


def test_executor_records_intents_and_never_claims_execution():
    plan = plan_sweep(event(amount=200.0), settlement_balance=300.0, policy=POLICY)
    executor = SweepExecutor(policy=POLICY)
    result = executor.execute(plan)
    assert result["executed"] is False
    assert result["dry_run"] is True
    assert [i["kind"] for i in result["intents"]] == ["transfer"]
    assert len(executor.intents) == 1


def test_executor_convert_plan_records_fx_then_transfer():
    plan = plan_sweep(
        event(currency="EUR", amount=400.0),
        settlement_balance=100.0,
        fx_rates={"EUR": 1.08},
        policy=POLICY,
    )
    result = SweepExecutor(policy=POLICY).execute(plan)
    assert [i["kind"] for i in result["intents"]] == ["fx_convert", "transfer"]


# --- pipeline wiring -----------------------------------------------------------


def test_pipeline_recovery_sweeps_and_ledgers():
    pipe = Pipeline.demo()
    outcome = pipe.handle_recovery(
        RecoveryEvent(
            source="dispute_won", reference="dst_won", amount=600.0, currency="USD"
        ),
        settlement_balance=100.0,
    )
    assert outcome["plan"]["action"] == "sweep"
    assert outcome["plan"]["amount"] == 450.0  # (100 + 600) - 250 default minimum
    assert outcome["authorization"]["verdict"] == "allow"
    assert outcome["execution"]["executed"] is False  # dry-run
    assert pipe.ledger.verify() is True


def test_pipeline_big_recovery_is_held_for_human_cosign():
    pipe = Pipeline.demo()
    outcome = pipe.handle_recovery(
        RecoveryEvent(
            source="dispute_won",
            reference="dst_whale",
            amount=50_000.0,
            currency="USD",
        ),
        settlement_balance=0.0,
    )
    assert outcome["plan"]["action"] == "sweep"
    assert outcome["authorization"]["verdict"] == "require_escalation"
    assert outcome["execution"]["intents"] == []  # held at the gate
    assert pipe.ledger.verify() is True
