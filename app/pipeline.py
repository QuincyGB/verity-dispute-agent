"""Pipeline — wires intake -> evidence -> EV score -> authorize -> act -> ledger.

One pass through :meth:`Pipeline.handle_dispute` performs the Verity loop:

1. assemble the evidence package,
2. score the dispute with the EV engine (challenge / accept / escalate),
3. authorize the resulting action through the TAP-style authorization
   layer (``app/authz``): policy gate first, then a signed envelope bound
   to the ledger head. Actions above the autonomous limit are rerouted to
   the human escalation queue — the agent's authority is bounded,
4. act: submit representment (CHALLENGE), record an accept (ACCEPT), or
   enqueue a human summary (ESCALATE),
5. append the decision, its signed envelope (when one was issued), and the
   evidence manifest hash to the hash-chained ledger.

:meth:`Pipeline.handle_recovery` closes the loop on outcomes: when a
dispute is won (or a refund-on-accept settles), the treasury sweep engine
(``app/treasury``) plans what happens to the recovered funds, the sweep
itself is authorized through the same gateway, and the plan is ledgered.

Disputes Airwallex auto-handles itself are skipped per its documented rules
(full-refunded disputes are auto-defended; pre-chargebacks under 60 USD are
auto-accepted) — Verity never double-responds.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .airwallex_client import AirwallexClient
from .authz import (
    ActionType,
    AgentAction,
    AuthorizationGateway,
    AuthorizedRepresentmentSubmitter,
    RequiresEscalationError,
)
from .authz.envelope import ActionEnvelope
from .config import Settings, get_settings
from .escalation import EscalationQueue
from .evidence import DemoRecords, EvidenceAssembler
from .ev_engine import Decision, Policy, ScoreResult, score_dispute
from .ledger import DecisionLedger
from .metal_anchor import MetalAnchor
from .models import Dispute, DisputeStage, EvidencePackage
from .representment import RepresentmentSubmitter
from .treasury import RecoveryEvent, SweepExecutor, SweepPolicy, plan_sweep

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
    gateway: AuthorizationGateway | None = None
    sweep_policy: SweepPolicy = field(default_factory=SweepPolicy)
    sweep_executor: SweepExecutor | None = None

    @classmethod
    def demo(cls) -> "Pipeline":
        """Pipeline wired with demo records + dry-run client (skeleton demo)."""
        settings = get_settings()
        client = AirwallexClient(settings=settings)
        ledger = DecisionLedger()
        return cls(
            settings=settings,
            assembler=EvidenceAssembler(DemoRecords()),
            client=client,
            ledger=ledger,
            escalations=EscalationQueue(),
            anchor=MetalAnchor(enabled=settings.metal_anchor_enabled),
            gateway=AuthorizationGateway(ledger=ledger, agent_id=settings.agent_id),
            sweep_executor=SweepExecutor(),
        )

    def _gateway(self) -> AuthorizationGateway:
        if self.gateway is None:
            self.gateway = AuthorizationGateway(
                ledger=self.ledger, agent_id=self.settings.agent_id
            )
        return self.gateway

    def _skip_reason(self, dispute: Dispute) -> str | None:
        if (
            dispute.stage == DisputeStage.PRE_CHARGEBACK
            and dispute.currency == "USD"
            and dispute.amount < AUTO_ACCEPT_PRECHARGEBACK_USD
        ):
            return "Airwallex auto-accepts pre-chargebacks under 60 USD"
        return None

    def _authorize_or_escalate(
        self,
        action: AgentAction,
        dispute: Dispute,
        package: EvidencePackage,
        score: ScoreResult,
        outcome: dict,
    ) -> ActionEnvelope | None:
        """Run the policy gate for ``action``.

        Returns the signed envelope when the action is within autonomous
        authority. When the gate demands a human co-sign, the case is
        rerouted to the escalation queue, the outcome is rewritten to an
        escalation, and None is returned — the action does not execute.
        """
        gateway = self._gateway()
        try:
            envelope = gateway.authorize(action)
        except RequiresEscalationError as exc:
            case = self.escalations.enqueue(dispute, package, score)
            outcome["decision"] = Decision.ESCALATE.value
            outcome["escalation_summary"] = case.summary
            outcome["authorization"] = {
                "verdict": "require_escalation",
                "reason": exc.decision.reason,
            }
            return None
        outcome["authorization"] = {
            "verdict": "allow",
            "envelope": envelope.to_dict(),
        }
        return envelope

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
            envelope = self._authorize_or_escalate(
                AgentAction(
                    action_type=ActionType.SUBMIT_CHALLENGE,
                    amount=dispute.amount,
                    currency=dispute.currency,
                    reference=dispute.id,
                    detail="representment per EV decision",
                ),
                dispute,
                package,
                score,
                outcome,
            )
            if envelope is not None:
                submitter = AuthorizedRepresentmentSubmitter(
                    RepresentmentSubmitter(self.client), self._gateway()
                )
                result = submitter.submit(envelope, dispute, package, score)
                outcome["submission"] = {
                    "submitted": result.submitted,
                    "dry_run": result.dry_run,
                    "detail": result.detail,
                }
        elif score.decision == Decision.ACCEPT:
            envelope = self._authorize_or_escalate(
                AgentAction(
                    action_type=ActionType.ACCEPT_DISPUTE,
                    amount=dispute.amount,
                    currency=dispute.currency,
                    reference=dispute.id,
                    detail="accept per EV decision (negative-EV fight)",
                ),
                dispute,
                package,
                score,
                outcome,
            )
            if envelope is not None:
                # Recorded; the actual accept call is client-side TODO.
                outcome["submission"] = {
                    "submitted": False,
                    "detail": "accept recorded in ledger",
                }
        else:  # ESCALATE — the engine's own call; moves no money, no envelope
            case = self.escalations.enqueue(dispute, package, score)
            outcome["escalation_summary"] = case.summary

        entry = self.ledger.append(
            dispute.id,
            outcome["decision"],
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

    def handle_recovery(
        self,
        event: RecoveryEvent,
        *,
        settlement_balance: float,
        fx_rates: dict[str, float] | None = None,
    ) -> dict:
        """Plan + authorize + record the sweep of recovered funds.

        Called when a dispute outcome returns money (won) or a
        refund-on-accept settles. The sweep is a money-moving action, so it
        goes through the same authorization gateway as a challenge: above
        the autonomous limit it is recorded as requiring a human co-sign
        and does not execute.
        """
        plan = plan_sweep(
            event,
            settlement_balance=settlement_balance,
            fx_rates=fx_rates,
            policy=self.sweep_policy,
        )

        authorization: dict = {"verdict": "not_required", "reason": "no sweep planned"}
        execution: dict = {
            "executed": False,
            "dry_run": True,
            "intents": [],
            "detail": "no sweep planned",
        }

        if plan.action != "none":
            action = AgentAction(
                action_type=(
                    ActionType.FX_CONVERT
                    if plan.action == "convert_and_sweep"
                    else ActionType.TREASURY_SWEEP
                ),
                amount=plan.amount,
                currency=plan.currency,
                reference=event.reference,
                detail=f"treasury sweep after {event.source}",
            )
            try:
                envelope = self._gateway().authorize(action)
            except RequiresEscalationError as exc:
                authorization = {
                    "verdict": "require_escalation",
                    "reason": exc.decision.reason,
                }
                execution = {
                    "executed": False,
                    "dry_run": True,
                    "intents": [],
                    "detail": "sweep held for human co-sign (authorization gate)",
                }
            else:
                authorization = {"verdict": "allow", "envelope": envelope.to_dict()}
                executor = self.sweep_executor or SweepExecutor(
                    policy=self.sweep_policy
                )
                self.sweep_executor = executor
                execution = executor.execute(plan)

        entry = self.ledger.append(
            event.reference,
            "treasury_sweep",
            {
                "source": event.source,
                "recovered": event.amount,
                "currency": event.currency,
                "plan": plan.to_dict(),
                "authorization": authorization,
                "execution": execution,
            },
        )
        return {
            "plan": plan.to_dict(),
            "authorization": authorization,
            "execution": execution,
            "ledger_seq": entry.seq,
            "ledger_head_hash": self.ledger.head_hash,
        }
