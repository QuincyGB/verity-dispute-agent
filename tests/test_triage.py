"""Tests for the triage EV function (app/triage.py) — the spec-required test."""

import pytest

from app.ev_engine import Decision
from app.triage import expected_value, triage_decision


def test_expected_value_math():
    # p * A - C = 0.75 * 200 - 15 = 135
    assert expected_value(0.75, 200.0, 15.0) == 135.0
    # A coin-flip on a small dispute does not cover the cost of fighting.
    assert expected_value(0.50, 20.0, 15.0) == -5.0
    # Zero win probability: EV is exactly the (negative) cost.
    assert expected_value(0.0, 500.0, 15.0) == -15.0


def test_expected_value_rejects_bad_inputs():
    with pytest.raises(ValueError):
        expected_value(1.5, 100.0, 15.0)
    with pytest.raises(ValueError):
        expected_value(0.5, -100.0, 15.0)


def test_triage_decision_bands():
    # Clearly positive EV -> challenge.
    assert triage_decision(0.75, 200.0) == Decision.CHALLENGE
    # Clearly negative EV -> accept.
    assert triage_decision(0.40, 10.0) == Decision.ACCEPT
    # EV inside the ±10 band (-3.0) -> escalate to a human.
    assert triage_decision(0.30, 40.0) == Decision.ESCALATE
    # Below the win-probability floor -> accept, however large the amount.
    assert triage_decision(0.10, 10_000.0) == Decision.ACCEPT
