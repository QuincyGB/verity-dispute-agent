"""Evidence assembler.

Given a dispute, pull together everything the merchant's systems hold about
the underlying transaction: the receipt, delivery proof, customer
communications, and terms-acceptance record.

The assembler works against a :class:`MerchantRecords` protocol so the build
window can plug in real data sources (order system, helpdesk, Airwallex-held
transaction data). :class:`DemoRecords` is an in-memory provider used by the
demo and tests — it holds *sample* data only and says so.
"""

from __future__ import annotations

from typing import Protocol

from .models import Dispute, EvidenceItem, EvidenceKind, EvidencePackage

# Evidence that matters most per dispute reason type (aligns with Airwallex's
# published "compelling evidence" guidance at a capability level).
REASON_PRIORITIES: dict[str, list[EvidenceKind]] = {
    "FRAUDULENT": [EvidenceKind.DELIVERY_PROOF, EvidenceKind.RECEIPT, EvidenceKind.TERMS_ACCEPTANCE],
    "PRODUCT_NOT_RECEIVED": [EvidenceKind.DELIVERY_PROOF, EvidenceKind.CUSTOMER_COMMS],
    "DUPLICATE": [EvidenceKind.RECEIPT, EvidenceKind.REFUND_PROOF],
    "CREDIT_NOT_PROCESSED": [EvidenceKind.REFUND_PROOF, EvidenceKind.RECEIPT],
}


class MerchantRecords(Protocol):
    """Where Verity fetches a merchant's transaction artefacts."""

    def fetch(self, dispute: Dispute) -> list[EvidenceItem]:
        ...


class DemoRecords:
    """Sample in-memory records for the sandbox demo (labelled demo data).

    Returns a full package for order "demo-order-1" and a partial package
    for anything else, so both the challenge and escalate paths can be shown.
    """

    def fetch(self, dispute: Dispute) -> list[EvidenceItem]:
        h = EvidenceItem.hash_bytes
        if dispute.merchant_order_id == "demo-order-1":
            return [
                EvidenceItem(kind=EvidenceKind.RECEIPT, label="Invoice INV-1001 (PDF)",
                             sha256=h(b"demo-invoice-1001")),
                EvidenceItem(kind=EvidenceKind.DELIVERY_PROOF, label="Carrier tracking + signed POD",
                             sha256=h(b"demo-pod-1001")),
                EvidenceItem(kind=EvidenceKind.TERMS_ACCEPTANCE, label="Checkout T&Cs acceptance log",
                             sha256=h(b"demo-terms-1001")),
                EvidenceItem(kind=EvidenceKind.CUSTOMER_COMMS, label="Support thread, 3 messages",
                             sha256=h(b"demo-comms-1001")),
            ]
        return [
            EvidenceItem(kind=EvidenceKind.RECEIPT, label="Invoice (PDF)",
                         sha256=h(f"demo-invoice-{dispute.id}".encode())),
        ]


class EvidenceAssembler:
    def __init__(self, records: MerchantRecords) -> None:
        self.records = records

    def assemble(self, dispute: Dispute) -> EvidencePackage:
        items = self.records.fetch(dispute)
        package = EvidencePackage(dispute_id=dispute.id, items=items)

        wanted = REASON_PRIORITIES.get(dispute.reason.type.upper(), [])
        for kind in wanted:
            if kind not in package.kinds_present:
                package.notes.append(
                    f"missing priority evidence for {dispute.reason.type}: {kind.value}"
                )
        return package
