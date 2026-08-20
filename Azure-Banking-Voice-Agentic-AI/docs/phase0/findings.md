## R-01 — Models API deprecation-date check

Queried 2026-08-20T02:53:04Z, location=canadacentral, api-version=2023-05-01 (confirmed valid — 200 OK).

**Resolved**: version 2025-10-06 -> deprecationDate 2027-04-06. Version 2025-12-15 (the GA
version decision 14 pins to, isDefaultVersion=true) -> deprecationDate **2026-12-15** — the
pessimistic one of the two conflicting dates PLAN.md recorded, now confirmed as the real one.
As of this query (2026-08-20), that is ~4 months out, not the mid-2027 optimistic case.

New data point, not yet interpreted: version 2025-12-15's GlobalStandard SKU has a lower
request-rate limit (3/60s) than 2025-10-06's (10/60s), despite a higher token limit
(10000/60s vs 5000/60s). Unclear whether 'request' here bounds realtime turns or something
else (session creation, deployment ops) — flagged for Phase 2 to actually determine.

```json
[
  {
    "kind": "OpenAI",
    "model": {
      "capabilities": {
        "assistants": "false",
        "chatCompletion": "false",
        "completion": "false",
        "realtime": "true"
      },
      "deprecation": {
        "inference": "2027-04-06T00:00:00Z"
      },
      "format": "OpenAI",
      "isDefaultVersion": false,
      "lifecycleStatus": "GenerallyAvailable",
      "maxCapacity": 3,
      "name": "gpt-realtime-mini",
      "skus": [
        {
          "capacity": {
            "default": 100,
            "maximum": 30000
          },
          "deprecationDate": "2027-04-06T00:00:00Z",
          "name": "GlobalStandard",
          "rateLimits": [
            {
              "count": 10,
              "key": "request",
              "renewalPeriod": 60
            },
            {
              "count": 5000,
              "key": "token",
              "renewalPeriod": 60
            }
          ],
          "usageName": "OpenAI.GlobalStandard.gpt-realtime-mini"
        }
      ],
      "systemData": {
        "createdAt": "2025-10-06T00:00:00Z",
        "createdBy": "Microsoft",
        "createdByType": "Application",
        "lastModifiedAt": "2025-10-06T00:00:00Z",
        "lastModifiedBy": "Microsoft",
        "lastModifiedByType": "Application"
      },
      "version": "2025-10-06"
    },
    "skuName": "S0"
  },
  {
    "kind": "OpenAI",
    "model": {
      "capabilities": {
        "assistants": "false",
        "chatCompletion": "false",
        "completion": "false",
        "realtime": "true"
      },
      "deprecation": {
        "inference": "2026-12-15T00:00:00Z"
      },
      "format": "OpenAI",
      "isDefaultVersion": true,
      "lifecycleStatus": "GenerallyAvailable",
      "maxCapacity": 3,
      "name": "gpt-realtime-mini",
      "skus": [
        {
          "capacity": {
            "default": 100,
            "maximum": 30000
          },
          "deprecationDate": "2026-12-15T00:00:00Z",
          "name": "GlobalStandard",
          "rateLimits": [
            {
              "count": 3,
              "key": "request",
              "renewalPeriod": 60
            },
            {
              "count": 10000,
              "key": "token",
              "renewalPeriod": 60
            }
          ],
          "usageName": "OpenAI.GlobalStandard.gpt-realtime-mini"
        }
      ],
      "systemData": {
        "createdAt": "2025-12-11T00:00:00Z",
        "createdBy": "Microsoft",
        "createdByType": "Application",
        "lastModifiedAt": "2025-12-11T00:00:00Z",
        "lastModifiedBy": "Microsoft",
        "lastModifiedByType": "Application"
      },
      "version": "2025-12-15"
    },
    "skuName": "S0"
  },
  {
    "kind": "AIServices",
    "model": {
      "capabilities": {
        "assistants": "false",
        "chatCompletion": "false",
        "completion": "false",
        "realtime": "true"
      },
      "deprecation": {
        "inference": "2027-04-06T00:00:00Z"
      },
      "format": "OpenAI",
      "isDefaultVersion": false,
      "lifecycleStatus": "GenerallyAvailable",
      "maxCapacity": 3,
      "name": "gpt-realtime-mini",
      "skus": [
        {
          "capacity": {
            "default": 100,
            "maximum": 30000
          },
          "deprecationDate": "2027-04-06T00:00:00Z",
          "name": "GlobalStandard",
          "rateLimits": [
            {
              "count": 10,
              "key": "request",
              "renewalPeriod": 60
            },
            {
              "count": 5000,
              "key": "token",
              "renewalPeriod": 60
            }
          ],
          "usageName": "OpenAI.GlobalStandard.gpt-realtime-mini"
        }
      ],
      "systemData": {
        "createdAt": "2025-10-06T00:00:00Z",
        "createdBy": "Microsoft",
        "createdByType": "Application",
        "lastModifiedAt": "2025-10-06T00:00:00Z",
        "lastModifiedBy": "Microsoft",
        "lastModifiedByType": "Application"
      },
      "version": "2025-10-06"
    },
    "skuName": "S0"
  },
  {
    "kind": "AIServices",
    "model": {
      "capabilities": {
        "assistants": "false",
        "chatCompletion": "false",
        "completion": "false",
        "realtime": "true"
      },
      "deprecation": {
        "inference": "2026-12-15T00:00:00Z"
      },
      "format": "OpenAI",
      "isDefaultVersion": true,
      "lifecycleStatus": "GenerallyAvailable",
      "maxCapacity": 3,
      "name": "gpt-realtime-mini",
      "skus": [
        {
          "capacity": {
            "default": 100,
            "maximum": 30000
          },
          "deprecationDate": "2026-12-15T00:00:00Z",
          "name": "GlobalStandard",
          "rateLimits": [
            {
              "count": 3,
              "key": "request",
              "renewalPeriod": 60
            },
            {
              "count": 10000,
              "key": "token",
              "renewalPeriod": 60
            }
          ],
          "usageName": "OpenAI.GlobalStandard.gpt-realtime-mini"
        }
      ],
      "systemData": {
        "createdAt": "2025-12-11T00:00:00Z",
        "createdBy": "Microsoft",
        "createdByType": "Application",
        "lastModifiedAt": "2025-12-11T00:00:00Z",
        "lastModifiedBy": "Microsoft",
        "lastModifiedByType": "Application"
      },
      "version": "2025-12-15"
    },
    "skuName": "S0"
  }
]
```


## Model pin reconsideration — widened R-01 query, 2026-08-20

Triggered by: the original R-01 finding pinned to the `isDefaultVersion` (`2025-12-15`) without
checking whether other GA options had longer runway. Widened the Models API query in canadacentral
from a name filter (`gpt-realtime-mini` only) to every model with `capabilities.realtime == "true"`.

### Every realtime-capable model found in canadacentral (raw catalog, api-version=2023-05-01)

Full raw response saved to this session's transcript; summarized here with the fields that mattered:

| Model | Version | Lifecycle | Deprecation (inference) | Req/60s | Tok/60s |
|---|---|---|---|---|---|
| gpt-realtime-mini | 2025-10-06 | GA | 2027-04-06 | 10 | 5000 |
| gpt-realtime-mini | 2025-12-15 (isDefaultVersion) | GA | 2026-12-15 | 3 | 10000 |
| gpt-realtime | 2025-08-28 | GA | 2027-03-02 | 20 | 10000 |
| gpt-realtime-1.5 | 2026-02-23 | GA | 2027-08-24 | 20 | 10000 |
| gpt-realtime-2 | 2026-05-06 | **Preview** | 2026-08-31 | 20 | 10000 |
| gpt-realtime-2.1 | 2026-07-07 | **Preview** | 2026-10-15 | 20 | 10000 |
| gpt-realtime-2.1-mini | 2026-07-07 | **Preview** | 2026-10-15 | 20 | 10000 |

Plus 3 transcribe-only (STT, not speech-to-speech) models not relevant to decision 6's architecture:
gpt-4o-transcribe, gpt-4o-mini-transcribe, gpt-transcribe.

**Note on the premise that prompted this query**: `gpt-realtime-2.1-mini` does exist in canadacentral
at the cited $10/$20-per-1M pricing, but it is **Preview**, not GA, and retires **2026-10-15** — the
*shortest* runway of any mini-tier option found, not a 2027+ date. The "if it exists with a 2027+ date
this question goes away" premise doesn't hold; it exists with the worst date on the list.

### Pricing (Azure Retail Prices API was missing gpt-realtime-mini/gpt-realtime/gpt-realtime-1.5
entirely — same gap docs/PLAN.md already found for ACS. Resolved via the pricing calculator API's
`offers` structure, `azure.microsoft.com/api/v3/pricing/openai-service/calculator`):

| Model family | Audio input | Audio output |
|---|---|---|
| gpt-realtime-mini (both versions) | $10 / 1M tokens | $20 / 1M tokens |
| gpt-realtime-2.1-mini | $10 / 1M tokens | $20 / 1M tokens |
| gpt-realtime (2025-08-28) | $32 / 1M tokens | $64 / 1M tokens |
| gpt-realtime-1.5 | $32 / 1M tokens | $64 / 1M tokens |
| gpt-realtime-2 | $32 / 1M tokens | $64 / 1M tokens |
| gpt-realtime-2.1 | $32 / 1M tokens | $64 / 1M tokens |

**Pricing is flat within a tier across every dated snapshot found** — mini tier is always $10/$20,
full tier is always $32/$64. So "which dated version" doesn't trade against cost at all; only
"which tier" (4x cost difference) and "GA vs Preview + specific retirement date" actually vary.

### Decision: re-pin to gpt-realtime-mini 2025-10-06 (docs/PLAN.md decision 14, revised)

Longest-runway GA option in the mini tier, identical cost to the version it replaces, and a *better*
request-rate limit (10/60s vs 3/60s) despite half the token-rate limit (5000/60s vs 10000/60s — both
comfortably clear the ~1200 tokens/min this project's own turn-rate estimate needs). Named successor
for B3: `gpt-realtime-1.5` (2026-02-23, GA, retires 2027-08-24, ~3.2x cost) — held in reserve, not
adopted now, since taking it today would roughly double the per-minute budget floor and cut into
R-08's demo-runs/month headroom for no immediate benefit.

**Honest gap, stated rather than rounded up**: `2025-10-06` retires 2027-04-06 — real runway for a
demo six months from now (safely before retirement, ~1.5 months of margin), but not comfortably into
"mid-2027" as originally hoped at zero extra cost. `gpt-realtime-1.5` reaches 2027-08-24 but at
~3.2x the model-token cost. No option in the current catalog satisfies both "mid-2027" and "no cost
increase" simultaneously. The expected resolution path: `gpt-realtime-2.1-mini` (or whatever succeeds
it) graduating from Preview to GA with its own fresh multi-year date before April 2027 — plausible
given Microsoft's realtime-model refresh cadence (~6 months apart in this catalog), but not
guaranteed, which is exactly why CLAUDE.md now requires the pin reviewed at every phase gate rather
than trusted as settled.

### Rate-limit interpretation (item 5) — partially resolved, gap stated honestly

Token-rate reasoning confirmed: even the tighter limit (5000 tokens/60s, the pinned version) is ~4x
this project's own estimated need (~10 tok/s/direction, ~1200/min with context growth). Not a
constraint under either version.

Request-rate limit ("3" or "10" per 60s, from the Models API's per-deployment `rateLimits` field) does
**not** reconcile cleanly against Microsoft's separately-documented subscription-level Quota Tier
table (`learn.microsoft.com/.../quotas-limits`) — that table shows flat RPM/TPM figures per tier
(e.g. `gpt-realtime`: 200 RPM / 100,000 TPM at Tier 1) that are a different order of magnitude and
doesn't list `gpt-realtime-mini` by name at all. Two quota layers, not obviously the same number.

What's well-supported, not exactly quoted: Microsoft's own realtime-audio doc frames limits as "for
audio tokens and **concurrent sessions**" (not per-turn), and the architecture itself (decision 6: one
persistent WebSocket per call, turns as streamed events on an open connection, not discrete HTTP
requests) makes "request = new session/connection" the much more plausible reading than "request =
turn". A live IVR call opens one session; unless more than 3 calls try to connect within the same 60s
window, this shouldn't bite production. **Not confirmed by an exact documentation quote** — recommend
checking the Foundry portal's Quota page directly once the Phase 0 AOAI deployment exists (cheap,
~30s), and Phase 2's actual usage will settle it empirically regardless.

**Action for L3's eval design** (20 batched runs): pace new session-starts at ≤3/60s as safe insurance
under the worst-case reading. Costs nothing — eval runs aren't latency-sensitive to a few seconds of
pacing — and sidesteps the ambiguity rather than resolving it under time pressure later.
