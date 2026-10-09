"""Domain models for Verity.

Field names on :class:`Dispute` mirror the dispute object in Airwallex's
public webhook payloads and dispute APIs (see README "Airwallex API surface").
Only the fields Verity actually uses are modelled.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class DisputeStage(str, Enum):
    """Stages documented in Airwallex's dispute flow."""

    RFI = "RFI"
    PRE_CHARGEBACK = "PRE_CHARGEBACK"
    CHARGEBACK = "CHARGEBACK"
    PRE_ARBITRATION = "PRE_ARBITRATION"
    ARBITRATION = "ARBITRATION"


class DisputeStatus(str, Enum):
    REQUIRES_RESPONSE = "REQUIRES_RESPONSE"
    CHALLENGED = "CHALLENGED"
    ACCEPTED = "ACCEPTED"
    REVERSED = "REVERSED"
    WON = "WON"
    LOST = "LOST"
    EXPIRED = "EXPIRED"
    PENDING_CLOSURE = "PENDING_CLOSURE"
    PENDING_DECISION = "PENDING_DECISION"


class DisputeReason(BaseModel):
    description: str = ""
    original_code: str = ""
    type: str = ""


class Dispute(BaseModel):
    """A payment dispute as delivered by Airwallex webhooks / dispute APIs."""

    id: str  # e.g. "dst_..." — the key identifier for all dispute API calls
    amount: float = Field(ge=0)
    currency: str
    stage: DisputeStage
    status: DisputeStatus
    reason: DisputeReason = DisputeReason()
    payment_intent_id: str | None = None
    merchant_order_id: str | None = None
    acquirer_reference_number: str | None = None
    due_at: datetime | None = None  # response deadline — the clock Verity races
    created_at: datetime | None = None
    updated_at: datetime | None = None


class EvidenceKind(str, Enum):
    RECEIPT = "receipt"  # invoice / payment receipt
    DELIVERY_PROOF = "delivery_proof"  # tracking + proof of delivery
    CUSTOMER_COMMS = "customer_comms"  # emails / chat with the shopper
    TERMS_ACCEPTANCE = "terms_acceptance"  # proof shopper accepted T&Cs / policy
    REFUND_PROOF = "refund_proof"  # proof a refund was already issued
    SERVICE_PROOF = "service_proof"  # proof a digital service was delivered/used
    OTHER = "other"


class EvidenceItem(BaseModel):
    """One piece of evidence in an assembled package."""

    kind: EvidenceKind
    label: str
    sha256: str  # content hash — goes into the evidence manifest
    file_id: str | None = None  # Airwallex File ID once uploaded (build window)

    @staticmethod
    def hash_bytes(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()


class EvidencePackage(BaseModel):
    """Everything Verity assembled for one dispute."""

    dispute_id: str
    items: list[EvidenceItem] = []
    notes: list[str] = []  # gaps the assembler could not fill

    @property
    def kinds_present(self) -> set[EvidenceKind]:
        return {item.kind for item in self.items}

    def manifest(self) -> dict:
        """Deterministic manifest of the package (used by the ledger)."""
        return {
            "dispute_id": self.dispute_id,
            "items": [
                {"kind": i.kind.value, "label": i.label, "sha256": i.sha256}
                for i in sorted(self.items, key=lambda x: (x.kind.value, x.sha256))
            ],
        }

    def manifest_hash(self) -> str:
        import json

        blob = json.dumps(self.manifest(), sort_keys=True).encode()
        return hashlib.sha256(blob).hexdigest()
