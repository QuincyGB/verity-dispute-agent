"""Escalation queue — borderline cases, packaged for a 60-second human call.

When the EV engine returns ESCALATE, Verity does not guess: it enqueues the
case with a one-page summary (dispute facts, EV math, evidence present and
missing, deadline) so a human can decide in under a minute.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .ev_engine import ScoreResult
from .models import Dispute, EvidencePackage


@dataclass
class EscalationCase:
    dispute: Dispute
    package: EvidencePackage
    score: ScoreResult
    summary: str


@dataclass
class EscalationQueue:
    cases: list[EscalationCase] = field(default_factory=list)

    def enqueue(self, dispute: Dispute, package: EvidencePackage, score: ScoreResult) -> EscalationCase:
        case = EscalationCase(
            dispute=dispute,
            package=package,
            score=score,
            summary=render_summary(dispute, package, score),
        )
        self.cases.append(case)
        return case

    def __len__(self) -> int:
        return len(self.cases)


def render_summary(dispute: Dispute, package: EvidencePackage, score: ScoreResult) -> str:
    """The one-page summary a human reviewer sees."""
    present = ", ".join(sorted(k.value for k in package.kinds_present)) or "none"
    missing = "; ".join(package.notes) or "none"
    due = dispute.due_at.isoformat() if dispute.due_at else "unknown"
    lines = [
        f"ESCALATION — dispute {dispute.id}",
        f"Amount: {dispute.amount:.2f} {dispute.currency}   Stage: {dispute.stage.value}",
        f"Reason: {dispute.reason.description or dispute.reason.type} ({dispute.reason.original_code})",
        f"Respond by: {due}",
        "",
        f"EV of challenging: {score.expected_value:.2f} "
        f"(win probability {score.win_probability:.0%}, completeness {score.completeness:.0%})",
        f"Engine note: {score.rationale}",
        "",
        f"Evidence present: {present}",
        f"Evidence gaps: {missing}",
        "",
        "Decision needed: CHALLENGE or ACCEPT.",
    ]
    return "\n".join(lines)
