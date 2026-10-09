# Verity — Architecture

Verity is an autonomous agent that responds to Airwallex payment disputes
(chargebacks) before their response deadlines expire.

## Components

| Component | Module | Responsibility |
|---|---|---|
| Webhook intake | `app/webhooks.py`, `app/main.py` | Receives Airwallex dispute events (`POST /webhooks/airwallex`), checks the signature (placeholder — build-window TODO), parses `data.object` into a `Dispute`. Health check at `GET /health`. |
| Domain models | `app/models.py` | `Dispute`, `DisputeReason`, `EvidenceItem`, `EvidencePackage` — field names mirror the Airwallex dispute object. |
| Evidence assembly | `app/evidence.py` | Pulls the transaction record for a dispute — receipt, delivery proof / proof of delivery, terms-acceptance log, customer communications, refund / service proof — into an `EvidencePackage`, and notes gaps per reason type. Works against a `MerchantRecords` protocol; `DemoRecords` is labelled sample data for the demo/tests. |
| Triage / EV engine | `app/triage.py`, `app/ev_engine.py` | Estimates win probability from reason-type base rate + evidence completeness, runs the EV math (below), and returns CHALLENGE / ACCEPT / ESCALATE. |
| Representment | `app/representment.py`, `app/airwallex_client.py` | Uploads evidence files to Airwallex and submits the challenge (representment) with a defence narrative. Dry-run by default in the skeleton: it records what *would* be sent and never fakes a submission. Live API calls are build-window TODOs. |
| Human escalation | `app/escalation.py` | Queue of borderline cases, each with a one-page summary (facts, EV math, evidence present/missing, deadline) so a human can decide in under a minute. Exposed at `GET /escalations`. |
| Decision ledger | `app/ledger.py` | Append-only, SHA-256 hash-chained log of every decision plus its evidence-manifest hash. Any later edit breaks the chain; `verify()` detects it. Exposed at `GET /ledger`. |
| Metal L1 anchor | `app/metal_anchor.py` | Periodically anchors the ledger head hash to Metal L1 (stub in the skeleton — no wallet, no RPC, no fabricated transaction ids). |
| Pipeline | `app/pipeline.py` | Wires intake → evidence → score → action → ledger in one pass. Skips disputes Airwallex auto-handles itself (e.g. pre-chargebacks under 60 USD are auto-accepted) so Verity never double-responds. |
| Config | `app/config.py` | Environment-driven settings (dry-run flag, webhook secret, Metal anchoring flag). No credentials are committed. |

## Data flow

```
Airwallex ──webhook: payment_dispute.requires_response──▶ Webhook intake
                                                              │ parse Dispute
                                                              ▼
Merchant records ───────────────────────────────▶ Evidence assembly
 (order system, carrier, helpdesk)                      │ EvidencePackage
                                                              ▼
                                                    Triage / EV engine
                                                    p(win), completeness, EV
                                          ┌───────────────┼────────────────┐
                                          ▼               ▼                ▼
                                      CHALLENGE        ACCEPT          ESCALATE
                                          │               │                │
                                          ▼               │                ▼
                              Representment submitter     │         Human queue
                              (upload evidence files,     │         (one-page
                               challenge dispute via      │          summary)
                               Airwallex API)             │                │
                                          └───────────────┴────────────────┘
                                                              ▼
                                                    Decision ledger (hash chain)
                                                              ▼
                                              Metal L1 anchor (head hash, periodic)
```

Every path — challenge, accept, escalate, and skip — ends in the ledger,
so the audit trail is complete, not just a log of the cases Verity fought.

## The EV decision formula

When a dispute lands, the disputed amount has already been pulled from the
merchant. Relative to that moment:

- **Accept** — the money stays gone. Baseline value: `0`.
- **Challenge (representment)** — pay a response cost `C` (agent/staff time
  and tooling). With probability `p` the issuer reverses the dispute and
  the amount `A` comes back; with probability `1 − p` it does not.

```
EV(challenge) = p × A − C
```

Decision bands (defaults in `app/ev_engine.Policy`, tunable):

| Condition | Decision |
|---|---|
| `p < 0.25` (win-probability floor) | ACCEPT — never auto-fight a near-hopeless case |
| `EV > +$10` | CHALLENGE — clearly positive expected value |
| `EV < −$10` | ACCEPT — fighting costs more than it returns |
| `|EV| ≤ $10` | ESCALATE — inside the uncertainty band; a human decides |

Win probability is estimated from the dispute reason and the evidence:

```
completeness = Σ weights of evidence kinds present     (receipt 0.25,
               delivery proof 0.25, terms 0.15, comms 0.15,
               service proof 0.10, refund proof 0.10)

p = clamp(base_rate[reason_type] + (completeness − 0.5) × 0.6, 0.02, 0.97)
```

Base rates are starting heuristics per Airwallex reason `type`
(e.g. FRAUDULENT 0.45, DUPLICATE 0.70, PRODUCT_UNACCEPTABLE 0.35),
documented as such in `app/ev_engine.py` — they are **not** measured issuer
statistics. Calibrating them against sandbox outcomes and real merchant
history is a build-window task.

Worked example: a $200 FRAUDULENT dispute with a complete evidence package
— completeness 1.0, `p = 0.45 + 0.5 × 0.6 = 0.75`,
`EV = 0.75 × 200 − 15 = $135` → CHALLENGE.

## Metal L1 decision hashing

1. Each decision is appended to the ledger as an entry whose SHA-256 hash
   covers the previous entry's hash and the canonical JSON of the entry
   (dispute id, decision, score details, evidence-manifest hash).
2. The chain head hash therefore commits to the entire history: editing or
   deleting any earlier entry changes every subsequent hash.
3. On a cadence (hourly, and immediately after each representment), Verity
   anchors the payload from `DecisionLedger.anchor_payload()`
   (`{type, head_hash, entries}`) to Metal L1.
4. Anyone can verify independently: export the ledger, recompute the chain,
   and compare the head hash with the anchored value on Metal L1 — no trust
   in Verity's own database required.

The on-chain submission itself is a build-window TODO (`app/metal_anchor.py`
is an honest stub in this skeleton).

## Status / honesty notes

- Working today: models, evidence assembly (demo provider), EV engine,
  escalation summaries, hash-chained ledger, pipeline, FastAPI health /
  webhook / ledger / escalations endpoints — all covered by tests.
- Stubs / TODOs: Airwallex authentication and live API calls, webhook
  signature verification, real merchant-records providers, LLM-drafted
  narratives, ledger persistence, and the Metal L1 anchor submission.
  Stubs raise `NotImplementedError` in live mode or report `dry_run`
  explicitly — nothing fabricates an external response.
