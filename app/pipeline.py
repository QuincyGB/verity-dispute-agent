"""Pipeline — wires intake -> evidence -> EV score -> action -> ledger.

One pass through :meth:`Pipeline.handle_dispute` performs the Verity loop:

1. assemble the evidence package,
2. score the dispute with the EV engine,
3. act: submit representment (CHALLENGE), record an accept (ACCEPT), or
   enqueue a human summary (ESCALATE),
4. append the decision + evidence manifest hash to the hash-chained ledger,
5. return the outcome (and refresh the Metal L1 anchor payload).

Disputes Airwallex auto-handles itself are skipped per its documented rules
(full-refunded disputes are auto-defended; pre-chargebacks under 60 USD are
auto-accepted) — Verity never double-responds.
"""

from __future__ import annotations

from dataclasses import dataclass

from .airwallex_client import AirwallexClient
from .config import Settings, get_settings
from .escalation import EscalationQueue
from .evidence import DemoRecords, EvidenceAssembler
from .ev_engine import Decision, Policy, score_dispute
from .ledger import DecisionLedger
from .metal_anchor import MetalAnchor
from .models import Dispute, DisputeStage
from .representment import RepresentmentSubmitter

AUTO_ACCEPT_PRECHARGEBACK_USD = 60.0  # Airwallex's documented auto-accept threshold


@dataclass
class Pipeline:
    settings: Settings
    assembler: EvidenceAssembler
    client: AirwallexClient
    ledger: DecisionLedger
    escalations: EscalationQueue
    policy: Policy = Policy()
    anchor: MetalAnchor | None = None

    @classmethod
    def demo(cls) -> "Pipeline":
        """Pipeline wired with demo records + dry-run client (skeleton demo)."""
        settings = get_settings()
        client = AirwallexClient(settings=settings)
        return cls(
            settings=settings,
            assembler=EvidenceAssembler(DemoRecords()),
            client=client,
            ledger=DecisionLedger(),
            escalations=EscalationQueue(),
            anchor=MetalAnchor(enabled=settings.metal_anchor_enabled),
        )

    def _skip_reason(self, dispute: Dispute) -> str | None:
        if (
            dispute.stage == DisputeStage.PRE_CHARGEBACK
            and dispute.currency == "USD"
            and dispute.amount < AUTO_ACCEPT_PRECHARGEBACK_USD
        ):
            return "Airwallex auto-accepts pre-chargebacks under 60 USD"
        return None

    def handle_dispute(self, dispute: Dispute) -> dict:
        skip = self._skip_reason(dispute)
        if skip:
            entry = self.ledger.append(
                dispute.id, "skip", {"reason": skip, "amount": dispute.amount}
            )
            return {"action": "skip", "reason": skip, "ledger_seq": entry.seq}

        package = self.assembler.assemble(dispute)
        score = score_dispute(
            amount=dispute.amount,
            reason_type=dispute.reason.type,
            package=package,
            policy=self.policy,
        )

        outcome: dict = {
            "decision": score.decision.value,
            "expected_value": score.expected_value,
            "win_probability": score.win_probability,
            "completeness": score.completeness,
        }

        if score.decision == Decision.CHALLENGE:
            submitter = RepresentmentSubmitter(self.client)
            result = submitter.submit(dispute, package, score)
            outcome["submission"] = {
                "submitted": result.submitted,
                "dry_run": result.dry_run,
                "detail": result.detail,
            }
        elif score.decision == Decision.ESCALATE:
            case = self.escalations.enqueue(dispute, package, score)
            outcome["escalation_summary"] = case.summary
        else:  # ACCEPT — recorded; the actual accept call is client-side TODO
            outcome["submission"] = {"submitted": False, "detail": "accept recorded in ledger"}

        entry = self.ledger.append(
            dispute.id,
            score.decision.value,
            {
                # Copy: the caller-visible outcome dict gains ledger fields
                # after this append, and the ledger payload must be immutable
                # or the hash chain breaks.
                "score": dict(outcome),
                "evidence_manifest_hash": package.manifest_hash(),
                "amount": dispute.amount,
                "currency": dispute.currency,
                "reason_type": dispute.reason.type,
            },
        )
        outcome["ledger_seq"] = entry.seq
        outcome["ledger_head_hash"] = self.ledger.head_hash
        return outcome
