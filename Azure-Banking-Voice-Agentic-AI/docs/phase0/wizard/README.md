# Phase 0 wizard — Azure-Banking-Voice-Agentic-AI

Four scripts, run on their own days, because Phase 0 (`docs/PLAN.md`) has real-world waits a single
sitting can't absorb. State hands forward between them via `docs/phase0/wizard/.env.phase0`
(git-ignored — add it to `.gitignore` before first commit if it isn't already covered).

| Script | When | What only you can do | What's automated |
|---|---|---|---|
| `01-provision.sh` | Today | Type `APPROVED: Phase 0` at the hard gate; pick an area code; provide Docker Hub credentials | Everything else — pre-checks, R-01, the gate itself, provider registration, all resource creation, R-06 probe, number purchase, ADR-001/002, echo app build+deploy |
| `02-test-calls.sh` | Today, right after 01 | **Dial the number from your mobile, 3 times** (plain echo, DTMF-during-streaming, sustained call) | Pulling Container App logs afterward and extracting R-02/R-03/RTT evidence |
| `03-cost-check-24h.sh` | Tomorrow (~24h later) | Wait — Cost Analysis has real ingestion lag | Querying Cost Management, sanity-checking against the plan's estimate |
| `04-teardown-and-r08.sh` | ~72h after `01` | Wait, and don't poke the idle Container App during that window | R-04 idle-billing verdict, R-08 demo-runs/month computation, `COSTS.md`, teardown (keeps the number) |

## Running

```bash
cd docs/phase0/wizard
./01-provision.sh
# ...dial the number 3 times as instructed...
./02-test-calls.sh
# ...wait ~24h...
./03-cost-check-24h.sh
# ...wait until ~72h total have passed since 01 ran...
./04-teardown-and-r08.sh
```

Each script is safe to re-run (idempotent where the underlying `az` commands are; explicitly confirms
before anything destructive). Ctrl-C anywhere is safe — nothing past the hard gate in `01` executes
until you've explicitly confirmed it.

## The hard gate

`01-provision.sh` runs two free, read-only stages (tool/subscription pre-flight, the R-01 Models API
check), then stops and requires you to type `APPROVED: Phase 0` exactly before anything that creates or
spends. This mirrors `CLAUDE.md`'s stop condition verbatim — restated on-screen at that gate, not just
in this README.

## Known verification items

Flagged inline in `01-provision.sh` and worth reading before you run it:

1. The Models API `api-version` used for the R-01 deprecation-date check.
2. The List Area Codes / phone-number search REST paths and `api-version` (Communication Services'
   phone-number APIs move fast).
3. The exact `azure-communication-callautomation` SDK parameter/enum names in the generated echo app
   (`docs/phase0/echo-app/app.py`) — written from `docs/PLAN.md`'s verified protocol facts, not
   independently re-checked against the currently-installed SDK version.

None of these are guesses dressed up as certainty — each is called out at the point it's used, per this
project's "verify, don't assume" rule (R-01 already burned it once on an unverified regional claim).

## What this wizard writes

- `docs/phase0/wizard/.env.phase0` — captured values (resource names, the phone number, timestamps).
- `docs/phase0/findings.md` — every raw R-01/R-02/R-03/R-04/R-05/R-06/R-08 result, appended as each
  script produces it.
- `docs/phase0/echo-app/` — the throwaway echo WebSocket app (`app.py`, `Dockerfile`, `requirements.txt`).
- `docs/adr/ADR-001-data-residency.md`, `docs/adr/ADR-002-geography-knobs.md` — written by `01`, using
  the R-05/R-06 results measured in that same run.
- `COSTS.md` (project root) — finalized by `04`, with the exit-gate table `docs/PLAN.md` requires.

## Unbudgeted-cost note

`01-provision.sh` deliberately avoids `az containerapp up --source`'s auto-provisioned Azure Container
Registry (~\$5/mo Basic tier) — that's real fixed cost `docs/PLAN.md`'s budget table never accounted
for. It builds locally and pushes to Docker Hub's free tier instead.
