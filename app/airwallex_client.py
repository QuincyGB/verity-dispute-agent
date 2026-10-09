"""Airwallex API client — STUB for the build window.

The endpoint paths below are verified against Airwallex's public docs page
"Handle disputes using our APIs" (airwallex.com/docs):

    GET  /api/v1/pa/payment_disputes/{dispute_id}          retrieve a dispute
    GET  /api/v1/pa/payment_disputes?...                   list disputes
    POST /api/v1/files/upload/{file_path}                  upload evidence -> file_id
    POST /api/v1/pa/payment_disputes/{dispute_id}/challenge  submit representment

Authentication (API-key -> bearer token exchange) and the accept-dispute
endpoint are TODOs for the build window, once sandbox credentials exist.
Nothing in this module fabricates API responses: in dry-run mode the client
records the request it *would* send and raises/returns accordingly; in live
mode it raises NotImplementedError rather than pretending.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .config import Settings
from .models import Dispute


@dataclass
class RecordedCall:
    method: str
    path: str
    json_body: dict | None = None


@dataclass
class AirwallexClient:
    settings: Settings
    recorded_calls: list[RecordedCall] = field(default_factory=list)

    # -- helpers ------------------------------------------------------------
    def _record(self, method: str, path: str, json_body: dict | None = None) -> None:
        self.recorded_calls.append(RecordedCall(method, path, json_body))

    def _not_live(self) -> None:
        if not self.settings.dry_run:
            raise NotImplementedError(
                "Live Airwallex calls are a build-window TODO "
                "(auth token exchange not yet implemented)."
            )

    # -- dispute retrieval ---------------------------------------------------
    def retrieve_dispute(self, dispute_id: str) -> Dispute:
        self._record("GET", f"/api/v1/pa/payment_disputes/{dispute_id}")
        self._not_live()
        raise NotImplementedError(
            "Dry-run: retrieve_dispute returns disputes via the webhook "
            "payload instead of an API round-trip."
        )

    def list_disputes(self, stage: str | None = None, status: str | None = None) -> list[Dispute]:
        params = []
        if stage:
            params.append(f"stage={stage}")
        if status:
            params.append(f"status={status}")
        query = ("?" + "&".join(params)) if params else ""
        self._record("GET", f"/api/v1/pa/payment_disputes{query}")
        self._not_live()
        return []

    # -- evidence upload ------------------------------------------------------
    def upload_evidence_file(self, file_path: str, data: bytes) -> str:
        """Upload one evidence file; returns the Airwallex ``file_id``.

        Verified endpoint: ``POST /api/v1/files/upload/{file_path}``.
        """
        self._record("POST", f"/api/v1/files/upload/{file_path}")
        self._not_live()
        # Dry-run only: a deterministic placeholder id, clearly not a real
        # Airwallex File ID (real ones are issued by the API).
        import hashlib

        return "dryrun_file_" + hashlib.sha256(data).hexdigest()[:16]

    # -- representment --------------------------------------------------------
    def challenge_dispute(self, dispute_id: str, file_ids: list[str], narrative: str) -> dict:
        """Submit representment for a dispute.

        Verified endpoint: ``POST /api/v1/pa/payment_disputes/{dispute_id}/challenge``.
        Request-body field names are confirmed against the API reference in
        the build window.
        """
        body = {"file_ids": file_ids, "narrative": narrative}
        self._record(
            "POST", f"/api/v1/pa/payment_disputes/{dispute_id}/challenge", body
        )
        self._not_live()
        return {"dry_run": True, "dispute_id": dispute_id, "submitted": False}

    # -- accept ----------------------------------------------------------------
    def accept_dispute(self, dispute_id: str, accept_reason: str) -> dict:
        """Accept a dispute (merchant concedes; refund handled separately).

        TODO (build window): confirm the exact accept endpoint path in the
        Airwallex API reference — the docs' validation examples reference an
        ``accept_reason`` field, but the path is not quoted here because it
        has not been verified from the public guide page yet.
        """
        self._record("POST", f"/api/v1/pa/payment_disputes/{dispute_id}/accept(TODO-verify-path)")
        self._not_live()
        return {"dry_run": True, "dispute_id": dispute_id, "submitted": False}
