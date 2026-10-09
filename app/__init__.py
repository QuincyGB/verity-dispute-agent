"""Verity — Autonomous Dispute Response Agent.

Receives Airwallex payment-dispute events, assembles evidence, scores each
dispute with expected-value math, submits representment for winnable cases,
escalates borderline cases to a human, and hash-chains every decision into an
auditable ledger (anchored to Metal L1 during the build window).
"""

__version__ = "0.1.0"
