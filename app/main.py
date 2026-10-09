"""FastAPI entrypoint.

Run locally (sandbox demo):

    uvicorn app.main:app --reload

Endpoints:
    GET  /health                 liveness
    POST /webhooks/airwallex     dispute event intake (signature check is a
                                 build-window TODO — do not expose publicly yet)
    GET  /ledger                 exported hash-chained decision ledger
    GET  /escalations            borderline cases awaiting a human
"""

from __future__ import annotations

from fastapi import FastAPI

from .pipeline import Pipeline
from .webhooks import build_router

app = FastAPI(title="Verity — Autonomous Dispute Response Agent", version="0.1.0")

pipeline = Pipeline.demo()

app.include_router(build_router(pipeline))


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "verity", "dry_run": pipeline.settings.dry_run}


@app.get("/ledger")
def ledger() -> dict:
    return {
        "entries": len(pipeline.ledger),
        "head_hash": pipeline.ledger.head_hash,
        "chain_valid": pipeline.ledger.verify(),
        "anchor_payload": pipeline.ledger.anchor_payload(),
    }


@app.get("/escalations")
def escalations() -> dict:
    return {
        "pending": len(pipeline.escalations),
        "summaries": [c.summary for c in pipeline.escalations.cases],
    }
