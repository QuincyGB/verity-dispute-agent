"""Representment submitter.

Turns a scored, evidence-backed CHALLENGE decision into an Airwallex
submission: upload any evidence files that are not already on Airwallex,
then call the Challenge Dispute endpoint before the dispute's ``due_at``
deadline.

In dry-run mode (the default in this skeleton) it records exactly what would
be sent and reports ``submitted: False`` — Verity never pretends a dry run
reached Airwallex.
"""

from __future__ import annotations

from dataclasses import dataclass

from .airwallex_client import AirwallexClient
from .ev_engine import ScoreResult
from .models import Dispute, EvidencePackage


@dataclass
class SubmissionResult:
    dispute_id: str
    submitted: bool
    dry_run: bool
    file_ids: list[str]
    detail: str


class RepresentmentSubmitter:
    def __init__(self, client: AirwallexClient) -> None:
        self.client = client

    def build_narrative(self, dispute: Dispute, package: EvidencePackage, score: ScoreResult) -> str:
        """One-paragraph defence narrative shipped with the challenge.

        Deliberately template-based in the skeleton; the build window swaps
        in the LLM-drafted, scheme-aware narrative generator.
        """
        kinds = ", ".join(sorted(k.value for k in package.kinds_present)) or "none"
        return (
            f"Dispute {dispute.id} ({dispute.reason.description or dispute.reason.type}) "
            f"for {dispute.amount:.2f} {dispute.currency}. "
            f"Evidence provided: {kinds}. "
            f"Verity assessment: estimated win probability {score.win_probability:.0%}, "
            f"EV {score.expected_value:.2f}. Submitted before the response deadline."
        )

    def submit(self, dispute: Dispute, package: EvidencePackage, score: ScoreResult) -> SubmissionResult:
        file_ids: list[str] = []
        for item in package.items:
            if item.file_id:
                file_ids.append(item.file_id)
            # TODO (build window): upload real file bytes via
            # client.upload_evidence_file once the records provider returns
            # content, not just hashes.

        narrative = self.build_narrative(dispute, package, score)
        response = self.client.challenge_dispute(dispute.id, file_ids, narrative)
        dry = bool(response.get("dry_run"))
        return SubmissionResult(
            dispute_id=dispute.id,
            submitted=bool(response.get("submitted")) and not dry,
            dry_run=dry,
            file_ids=file_ids,
            detail="dry-run: challenge recorded, not sent" if dry else "challenge sent",
        )
