# HackerEarth submission checklist — Verity (Airwallex Agentic Banking Hackathon)

Entry: **Verity — Autonomous Dispute Response Agent**, Track 4, solo team "Quincy's Team".
Registered on HackerEarth under the owner's account on 2026-10-06; the idea description is already published.

## Hard deadlines

| Item | Due | Status |
|---|---|---|
| Repository URL added to the HackerEarth entry | **Oct 23, 2026, 6:29 PM UTC** — entry "may not be considered" without it | ⬜ Repo created + pushed; URL still to be pasted into the entry |
| Build window | Oct 25 – Nov 13, 2026 | ⬜ |
| Demo video | With final submission (by Nov 13) | ⬜ |
| Final submission on HackerEarth | Nov 13, 2026 (end of build window; confirm exact cut-off on the event page) | ⬜ |

## Before Oct 23

- [ ] Push this repo publicly under QuincyGB (`verity-dispute-agent`), MIT license — done when the URL resolves.
- [ ] Paste the repo URL into the HackerEarth entry (owner's logged-in session) and save.
- [ ] Confirm the entry still shows Track 4 / "Quincy's Team" and the published Verity idea.

## Build window (Oct 25 – Nov 13)

- [ ] Airwallex sandbox account + API keys in env (never in git).
- [ ] Live: API-key auth, dispute retrieve/list, evidence upload, challenge submit (replace client TODOs).
- [ ] Webhook signature verification implemented and tested.
- [ ] Merchant-records connector beyond the demo provider.
- [ ] Metal L1 anchor submission live (head-hash anchoring) + verification walkthrough.
- [ ] Ledger persistence (SQLite) + export for judges.
- [ ] Full sandbox dress rehearsal: dispute webhook in → representment out → ledger anchored.

## Submission package

- [ ] Demo video: end-to-end dispute handled autonomously (intake → evidence → EV score → representment), one escalation shown, ledger verification + Metal anchor shown. Slow pacing, single scenario, per owner's standing video standard.
- [ ] README updated: sandbox run instructions, architecture, what is live vs stubbed (honesty section refreshed).
- [ ] Final HackerEarth form: repo URL, video link, description aligned with the published idea.
- [ ] Prize angles addressed explicitly in the write-up: Founder's/Judges Choice (autonomous agent on Airwallex rails) and the Metal Award (Metal L1 decision anchoring).
