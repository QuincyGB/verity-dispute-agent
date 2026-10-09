"""Webhook intake.

Airwallex delivers dispute events as signed webhook POSTs. Event names
verified from Airwallex's public dispute docs include:

    payment_dispute.requires_response   <- the trigger Verity acts on
    payment_dispute.challenged / accepted / reversed / won / lost / expired
    payment_dispute.pending_closure / pending_decision

Payload shape (from the docs' sample): a top-level ``name`` plus
``data.object`` holding the dispute object.

SIGNATURE VERIFICATION IS A PLACEHOLDER. Airwallex signs webhooks and the
signature must be verified against the webhook secret before any payload is
trusted; that check is a build-window TODO and is clearly marked below.
Until then this intake must not be exposed to the public internet.
"""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request

from .models import Dispute

# Events that mean "a dispute needs the merchant's response".
ACTIONABLE_EVENTS = {"payment_dispute.requires_response"}


def verify_signature(raw_body: bytes, signature: str | None, secret: str | None) -> bool:
    """TODO (build window): verify the Airwallex webhook signature.

    Placeholder behaviour: refuse when a secret is configured but no
    signature header arrived; otherwise accept (local demo only).
    """
    if secret and not signature:
        return False
    return True


def parse_dispute_event(payload: dict) -> tuple[str, Dispute]:
    """Extract (event_name, Dispute) from an Airwallex webhook payload."""
    name = payload.get("name", "")
    obj = (payload.get("data") or {}).get("object") or {}
    return name, Dispute.model_validate(obj)


def build_router(pipeline) -> APIRouter:
    router = APIRouter()

    @router.post("/webhooks/airwallex")
    async def airwallex_webhook(
        request: Request,
        x_signature: str | None = Header(default=None),
    ):
        raw = await request.body()
        # NOTE: header name for the signature is confirmed in the build
        # window against the webhook docs; see verify_signature().
        if not verify_signature(raw, x_signature, pipeline.settings.webhook_secret):
            raise HTTPException(status_code=401, detail="signature verification failed")

        payload = await request.json()
        name, dispute = parse_dispute_event(payload)
        if name not in ACTIONABLE_EVENTS:
            return {"received": True, "action": "ignored", "event": name}

        result = pipeline.handle_dispute(dispute)
        return {"received": True, "event": name, **result}

    return router
