# HackerEarth submission checklist — Verity (Airwallex Agentic Banking Hackathon)

Entry: **Verity — Autonomous Dispute Response Agent**, Track 4 (Dispute Response Agent starter kit), solo team "Quincy's Team".
Registered on HackerEarth under the owner's account on 2026-10-06; the idea description is already published.
Repo: https://github.com/QuincyGB/verity-dispute-agent (public, MIT).

## How the phases actually work (verified on the live entry, 2026-10-08)

- The **Registration & Idea Phase** form contains only Title + Description — there is **no Repository URL field** in this phase, and no "may not be considered" warning on the entry.
- **Oct 23, 2026, 2:29 PM Toronto (6:29 PM UTC)** = idea-phase close + shortlisting. Nothing about the repo is due at this point.
- **Accepted teams are notified Oct 25, 2026**; the **Build Phase** opens Oct 25 (12:30 AM Toronto). The repository link is part of the **Build Phase submission**, alongside the working demo and the video walkthrough.
- **Build Phase deadline: Nov 13, 2026, 1:29 PM Toronto.** Finalists Nov 15; Demo Day Nov 19 (San Francisco, remote participation optional).
- Build Phase submission = working demo + **video walkthrough under 5 minutes** + repository link with setup instructions.

## Timeline

| Item | Due | Status |
|---|---|---|
| Idea phase closes / shortlisting | Oct 23, 2026, 2:29 PM Toronto | ✅ Idea published Oct 6 |
| Accepted teams notified; build phase opens | Oct 25, 2026 | ⬜ |
| Build window | Oct 25 – Nov 13, 2026 | ⬜ |
| Final submission (demo + video < 5 min + repo link) | Nov 13, 2026, 1:29 PM Toronto | ⬜ |
| Finalists / Demo Day | Nov 15 / Nov 19, 2026 | ⬜ |

## Prize strategy ($80K cash + sponsor credits; "$100K" headline includes credits)

| Prize | Angle | What has to be true by Nov 13 |
|---|---|---|
| **Founder's Choice — $30,000** | Open category, no specific requirements. Verity's pitch: the decision layer for disputes — an agent that decides *and* executes, with bounded signed authority. | A demo that makes judges *feel* the decision: the EV math on screen, a deliberate accept, an over-limit case rerouted to a human. |
| **Judges Choice — $20,000** | Open category. Depth of Airwallex API usage + full-lifecycle autonomy on the standard APIs. | Live sandbox loop end-to-end (webhook → decision → challenge → outcome → sweep), all five stages represented in the rehearsal. |
| **Visa Award — $15,000** | "Requires use of Visa and Airwallex tooling." Verity's claim: the TAP-style authorization layer — policy-gated, signed agent actions (Visa TAP = agent identity + scoped authority). | TAP integration as far as partner docs/keys allow in the window; at minimum the implemented gate + envelope layer demoed explicitly, with the integration state stated honestly. Written up as a deliberate design pillar, not a footnote. |
| **Metal Award — $15,000** | "Requires use of Metal and Airwallex tooling." Verity's claim: decision-ledger head hashes anchored to Metal L1; third-party-verifiable audit trail. | Anchor submission live (wallet + anchoring cadence) + a verification walkthrough a judge can re-run. |

Multi-prize stacking is neither prohibited nor confirmed publicly — the write-up addresses each prize's angle explicitly so nothing depends on stacking being allowed.

Supporting credits noted on the event page: Claude Credits $10K, AWS Credits $50K, Base44 Credits $16K.

## How Verity differs from Airwallex AI Dispute Automation (submission mirror)

The sponsor already sells AI dispute automation — the entry must read as better, never a reskin. The five deltas (full table in the README):

1. **Decides and executes, including deliberately accepting** — explicit EV math (`p × amount − cost`) chooses challenge / accept / escalate; accepting a negative-EV fight is a first-class executed outcome (refund leg included). The sponsor product suggests actions and is built to defend. *Status: Implemented (decision + dry-run execution); live accept call: Stub.*
2. **Full-lifecycle coverage** — RFI → pre-chargeback → chargeback → pre-arbitration → arbitration under one agent. *Status: Implemented (stage model + pipeline); per-stage playbooks: Design.*
3. **Standard public APIs only** — no gated access; their AI Client API is limited to selected merchants via a rep. *Status: Implemented; live auth: Stub.*
4. **Policy-gated, signed actions (Visa TAP-style)** — autonomous limits, human co-sign above them, signed envelopes verified at execution. *Status: gate + envelopes Implemented/tested; real TAP integration: Stub.*
5. **Recovery + audit** — won funds swept by the treasury policy engine; every decision hash-chained and Metal-anchored. *Status: sweep engine + ledger Implemented/tested; transfer/FX execution and Metal anchor submission: Stub.*

## Before Oct 23 (idea phase)

- [x] Repo public under QuincyGB (`verity-dispute-agent`), MIT license, README aligned with the upgraded pitch.
- [ ] Confirm the entry still shows Track 4 / "Quincy's Team" and the published Verity idea.
- [ ] Optional (owner decision): append a clearly-labelled repository line to the published idea description — the only way to put the URL in front of shortlisting judges, since this phase has no repo field.

## Build window (Oct 25 – Nov 13)

- [ ] Airwallex sandbox account + API keys in env (never in git) — self-serve at demo.airwallex.com, no KYB for sandbox.
- [ ] Live: API-key auth, dispute retrieve/list, evidence upload, challenge submit (replace client TODOs).
- [ ] Webhook signature verification implemented and tested.
- [ ] Visa TAP: pursue partner docs/keys; integrate real agent identity + signature as far as access allows; keep the placeholder clearly labelled wherever it remains.
- [ ] Treasury: live balance reads; wire transfer + FX conversion calls for the sweep executor.
- [ ] Merchant-records connector beyond the demo provider.
- [ ] Metal L1 anchor submission live (head-hash anchoring) + verification walkthrough.
- [ ] Ledger persistence (SQLite) + export for judges.
- [ ] Full sandbox dress rehearsal on the deterministic dispute-simulation cards: dispute in → decision → signed action → outcome → recovery sweep → anchored ledger.

## Submission package (by Nov 13, 1:29 PM Toronto)

- [ ] Demo video (under 5 min): one dispute handled end-to-end and autonomously (intake → evidence → EV decision → signed authorization → representment), one deliberate accept, one over-limit escalation, a recovery sweep, and ledger verification + Metal anchor. Slow pacing, single scenario, per owner's standing video standard.
- [ ] README updated: sandbox run instructions, architecture, what is live vs stubbed (honesty section refreshed), differentiation table intact.
- [ ] Build Phase form: repository link, demo link, video link, description aligned with the published idea and the prize strategy above.
