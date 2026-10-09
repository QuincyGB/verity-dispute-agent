"""Metal L1 anchoring — STUB for the build window (the Metal Award angle).

Design (implemented in the build window):

* The decision ledger (``app/ledger.py``) is a SHA-256 hash chain. Anchoring
  the current head hash to Metal L1 commits to the entire history: any later
  edit to any entry changes the head hash and is detectable by anyone holding
  the anchored value.
* Anchors are written on a cadence (e.g. hourly, and immediately after every
  representment submission), carrying the payload produced by
  ``DecisionLedger.anchor_payload()``.
* Verification is public: recompute the chain from the exported ledger and
  compare the head hash against the anchored value on Metal L1.

This module intentionally contains no chain interaction yet — no wallet, no
RPC calls, no fabricated transaction ids.
"""

from __future__ import annotations

from .ledger import DecisionLedger


class MetalAnchor:
    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled

    def anchor(self, ledger: DecisionLedger) -> dict:
        payload = ledger.anchor_payload()
        if not self.enabled:
            return {"anchored": False, "reason": "anchoring disabled (skeleton default)", "payload": payload}
        raise NotImplementedError(
            "Metal L1 anchor submission is a build-window TODO."
        )
