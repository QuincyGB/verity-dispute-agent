"""Unit tests for the hash-chained decision ledger (app/ledger.py)."""

import json
from datetime import datetime, timezone

from app.ledger import GENESIS_HASH, DecisionLedger

TS = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)


def make_ledger(n: int = 3) -> DecisionLedger:
    ledger = DecisionLedger()
    for i in range(n):
        ledger.append(
            f"dst_{i}",
            "challenge",
            {"expected_value": 10.0 * i, "evidence_manifest_hash": f"m{i}"},
            timestamp=TS,
        )
    return ledger


def test_empty_chain():
    ledger = DecisionLedger()
    assert len(ledger) == 0
    assert ledger.head_hash == GENESIS_HASH
    assert ledger.verify() is True


def test_chain_links_and_verifies():
    ledger = make_ledger()
    assert len(ledger) == 3
    assert ledger.verify() is True
    rows = json.loads(ledger.export_json())
    assert rows[0]["prev_hash"] == GENESIS_HASH
    assert rows[1]["prev_hash"] == rows[0]["entry_hash"]
    assert rows[2]["prev_hash"] == rows[1]["entry_hash"]


def test_tamper_detection():
    ledger = make_ledger()
    rows = json.loads(ledger.export_json())
    rows[1]["payload"]["expected_value"] = 999999.0  # rewrite history
    forged = DecisionLedger.from_dicts(rows)
    assert forged.verify() is False


def test_deletion_detection():
    ledger = make_ledger()
    rows = json.loads(ledger.export_json())
    del rows[0]  # drop the genesis entry
    forged = DecisionLedger.from_dicts(rows)
    assert forged.verify() is False


def test_export_import_roundtrip():
    ledger = make_ledger(5)
    restored = DecisionLedger.from_dicts(json.loads(ledger.export_json()))
    assert restored.verify() is True
    assert restored.head_hash == ledger.head_hash


def test_anchor_payload_commits_to_head():
    ledger = make_ledger(2)
    payload = ledger.anchor_payload()
    assert payload["head_hash"] == ledger.head_hash
    assert payload["entries"] == 2
    ledger.append("dst_late", "accept", {}, timestamp=TS)
    # After a new entry, the old anchor no longer matches the head.
    assert ledger.anchor_payload()["head_hash"] != payload["head_hash"]
