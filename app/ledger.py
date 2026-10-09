"""Decision ledger — an append-only, hash-chained audit trail.

Every Verity decision (challenge / accept / escalate, plus its evidence
manifest) is appended as an entry whose SHA-256 hash covers the previous
entry's hash and the canonical JSON of the entry payload. Editing or deleting
any historical entry breaks the chain, and :meth:`DecisionLedger.verify`
detects it.

This is *working code*, verified by ``tests/test_ledger.py``.

Metal L1 anchoring (build window): periodically, the current chain head hash
is anchored to Metal L1 so the trail is provable to a third party without
trusting Verity's own database. :meth:`DecisionLedger.anchor_payload` already
produces the exact payload to anchor; the on-chain submission itself is a
TODO in ``app/metal_anchor.py``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

GENESIS_HASH = "0" * 64


def _canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


@dataclass
class LedgerEntry:
    seq: int
    timestamp: str  # ISO-8601 UTC
    dispute_id: str
    decision: str
    payload: dict  # score details + evidence manifest hash
    prev_hash: str
    entry_hash: str = field(default="")

    def compute_hash(self) -> str:
        body = {
            "seq": self.seq,
            "timestamp": self.timestamp,
            "dispute_id": self.dispute_id,
            "decision": self.decision,
            "payload": self.payload,
            "prev_hash": self.prev_hash,
        }
        return hashlib.sha256(_canonical(body)).hexdigest()

    def to_dict(self) -> dict:
        return {
            "seq": self.seq,
            "timestamp": self.timestamp,
            "dispute_id": self.dispute_id,
            "decision": self.decision,
            "payload": self.payload,
            "prev_hash": self.prev_hash,
            "entry_hash": self.entry_hash,
        }


class DecisionLedger:
    """In-memory chain with JSON export/import.

    Persistence (SQLite/Postgres) lands in the build window; the hash-chain
    logic here is persistence-agnostic.
    """

    def __init__(self) -> None:
        self._entries: list[LedgerEntry] = []

    def __len__(self) -> int:
        return len(self._entries)

    @property
    def head_hash(self) -> str:
        return self._entries[-1].entry_hash if self._entries else GENESIS_HASH

    def append(
        self,
        dispute_id: str,
        decision: str,
        payload: dict,
        timestamp: datetime | None = None,
    ) -> LedgerEntry:
        ts = (timestamp or datetime.now(timezone.utc)).isoformat()
        entry = LedgerEntry(
            seq=len(self._entries) + 1,
            timestamp=ts,
            dispute_id=dispute_id,
            decision=decision,
            payload=payload,
            prev_hash=self.head_hash,
        )
        entry.entry_hash = entry.compute_hash()
        self._entries.append(entry)
        return entry

    def verify(self) -> bool:
        """Recompute the whole chain; False on any tampering or gap."""
        prev = GENESIS_HASH
        for expected_seq, entry in enumerate(self._entries, start=1):
            if entry.seq != expected_seq or entry.prev_hash != prev:
                return False
            if entry.entry_hash != entry.compute_hash():
                return False
            prev = entry.entry_hash
        return True

    def anchor_payload(self) -> dict:
        """The payload to anchor to Metal L1 (build window).

        Anchoring the head hash commits to every entry before it, because
        each entry's hash covers its predecessor.
        """
        return {
            "type": "verity.decision_ledger.anchor",
            "head_hash": self.head_hash,
            "entries": len(self._entries),
        }

    def export_json(self) -> str:
        return json.dumps([e.to_dict() for e in self._entries], indent=2)

    @classmethod
    def from_dicts(cls, rows: list[dict]) -> "DecisionLedger":
        ledger = cls()
        for row in rows:
            entry = LedgerEntry(
                seq=row["seq"],
                timestamp=row["timestamp"],
                dispute_id=row["dispute_id"],
                decision=row["decision"],
                payload=row["payload"],
                prev_hash=row["prev_hash"],
                entry_hash=row["entry_hash"],
            )
            ledger._entries.append(entry)
        return ledger
