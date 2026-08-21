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

## R-06 — DataZoneStandard deployment probe

NOT OFFERED — confirmed empirically. Attempt failed with:
ERROR: (InvalidResourceProperties) The specified SKU 'DataZoneStandard' of account deployment is not supported by the model 'gpt-realtime-mini' version: '2025-10-06'.
Code: InvalidResourceProperties
Message: The specified SKU 'DataZoneStandard' of account deployment is not supported by the model 'gpt-realtime-mini' version: '2025-10-06'.

Queried 2026-08-20, resource aoai-azure-banking-voice-cc, resource group
rg-azure-banking-voice-agentic-ai, location canadacentral. Matches docs/PLAN.md's prediction
(availability tables list realtime under Global Standard only, zero rows under Data Zone Standard) —
now confirmed by a live deployment attempt, not just the pricing/availability table reading. Settles
R-06 for ADR-001: DataZoneStandard is not a fallback option for this model, full stop, error is
explicit and unambiguous (SKU not supported for this model+version), not a quota or permission error
that might resolve differently under other conditions.

## B3 end-to-end check — deployed reality vs. code's expectation, 2026-08-20

Live deployment (fresh `az cognitiveservices account deployment show`, not reused from an earlier
call this session):

```json
{
  "deploymentName": "gpt-realtime-mini",
  "modelName": "gpt-realtime-mini",
  "modelVersion": "2025-10-06",
  "provisioningState": "Succeeded",
  "sku": "GlobalStandard",
  "state": "Running",
  "versionUpgradeOption": "NoAutoUpgrade"
}
```

Matches `docs/PLAN.md` decision 14 exactly: model `gpt-realtime-mini`, version `2025-10-06`,
`GlobalStandard`, `NoAutoUpgrade`.

**Code side does not exist yet.** Searched the full repo tree: no `voice-agent/`, no `infra/`, no
`.py` or `.bicep` files anywhere outside `scripts/` (the pre-commit scope hook). B3's startup guard
(`assert_boot_safety`, `docs/PLAN.md` lines 140-167) is documented design only — it ships in Phase 2
("control ships here" per the phase plan), consistent with Phase 0 being provisioning-only. This is
not a Phase 0 gap; it's the plan working as sequenced.

**Honest gap worth naming for Phase 2's implementation, found by reading the documented guard
literally**: `ALLOWED_REALTIME_MODELS = frozenset({ACTIVE_REALTIME_MODEL, SUCCESSOR_REALTIME_MODEL})`
is a set of **deployment-name strings** (`"gpt-realtime-mini"`, `"gpt-realtime-1-5"`), and the guard
checks `settings.realtime_deployment not in ALLOWED_REALTIME_MODELS` — a name comparison. The version
pin (`2025-10-06`) is carried only in an adjacent comment, not in the compared value. R-01 already
proved two different model *versions* can share the same name (`gpt-realtime-mini` 2025-10-06 vs.
2025-12-15, different retirement dates, different rate limits). So as currently documented, the
startup guard would not by itself catch a redeploy of the `gpt-realtime-mini` deployment name onto a
different version — e.g. an operator (or IaC drift) repointing it at `2025-12-15` would still pass
`assert_boot_safety()` unchanged, silently. Today, version correctness rests entirely on (a) what's
actually deployed in Azure (verified above, correct) and (b) the human "Model pin review" process at
every phase gate (`CLAUDE.md`), not a runtime assertion. Worth Phase 2 deciding deliberately whether
`ALLOWED_REALTIME_MODELS` should key on `(name, version)` pairs instead of name alone — not fixed here,
since the guard doesn't exist as code yet to fix; flagged so it isn't rediscovered as a surprise once
it does.

**Verdict: B3 holds today** — the one deployment that exists matches the pin exactly, and nothing else
can reach it (no application code exists yet to reach it wrongly). The gap identified is a
forward-looking design note for Phase 2, not a live violation.

## R-05 — live Toronto-area area-code inventory, 2026-08-20

**Endpoint/api-version correction**: the wizard script's original call used
`api-version=2022-01-11-preview2`, which returned `400 UnsupportedApiVersion` live. Verified current
version via Microsoft Learn (List Area Codes REST reference, GA `2025-06-01`,
https://learn.microsoft.com/en-us/rest/api/communication/phonenumbers/phone-numbers/list-area-codes?view=rest-communication-phonenumbers-2025-06-01)
— query parameters (`phoneNumberType`, `assignmentType`, `locality`, `administrativeDivision`)
unchanged, only the version string moved. `01-provision.sh` should be corrected before this stage is
relied on again (not yet fixed — flagging for a follow-up commit).

**Direct query, locality=Toronto, administrativeDivision=ON, phoneNumberType=geographic,
assignmentType=application, api-version=2025-06-01:**
```json
{"error":{"code":"NotFound","message":"No area codes were found for the given parameters"}}
```
HTTP 404. Reproduced with `assignmentType=person` and with `assignmentType` omitted entirely — same
404 in all three cases. Not an assignmentType artifact.

**Root-caused via List Available Localities** (`/availablePhoneNumbers/countries/CA/localities`,
same api-version), which is what List Area Codes actually validates `locality` against. Two calls:

`administrativeDivision=ON` (all localities in Ontario, no more pages — `nextLink: null`):
```json
{
  "phoneNumberLocalities": [
    {"localizedName": "Brockville", "administrativeDivision": {"localizedName": "ON", "abbreviatedName": "ON"}},
    {"localizedName": "Guelph", "administrativeDivision": {"localizedName": "ON", "abbreviatedName": "ON"}},
    {"localizedName": "North Bay", "administrativeDivision": {"localizedName": "ON", "abbreviatedName": "ON"}},
    {"localizedName": "Sault Sainte Marie", "administrativeDivision": {"localizedName": "ON", "abbreviatedName": "ON"}},
    {"localizedName": "Thunder Bay", "administrativeDivision": {"localizedName": "ON", "abbreviatedName": "ON"}}
  ],
  "nextLink": null
}
```
(`administrativeDivision=Ontario`, full name instead of abbreviation, returned `404 NotFound` — `ON`
is the only accepted form.)

All of Canada, no filter, `maxPageSize=100`, one page (`nextLink: null`) — **10 localities total in
the entire country**:
```
Brockville, Guelph, North Bay, Sault Sainte Marie, Thunder Bay (all ON),
Chicoutimi, Montreal, Thetford Mines (QC), Biggar, Lanigan (SK)
```
**Toronto is not present. No GTA-adjacent locality is present. None of 416/647/437/905/289 are
reachable through this API at all** — not "available but taken", genuinely absent from ACS's
geographic-number locality inventory for Canada as of this query.

**Sanity check that the endpoint itself works** (not a broken call): queried a locality that *is* in
the list — `locality=Guelph, administrativeDivision=ON` — got a clean `200` with a real area code:
```json
{"areaCodes": [{"areaCode": "226"}], "nextLink": null}
```
Confirms the 404 for Toronto is real inventory absence, not a malformed request.

**Does ACS `dataLocation` constrain this?** This ACS resource was created with `dataLocation: Canada`.
`docs/PLAN.md` ADR-002 already established (pre-Phase-0 research) that number purchase is gated only
by subscription billing address, never by `dataLocation` — this result is consistent with that: the
constraint isn't a dataLocation filter narrowing an otherwise-larger Toronto inventory, it's that
Toronto/GTA doesn't appear in the country-wide, unfiltered locality list at all. Not ruled out
without testing a second ACS resource on a different `dataLocation`, which hasn't been done (would be
a second resource created solely to test this — not done without asking first).

**Consequence for decision 13 (`docs/PLAN.md`): "Canada local geographic, Toronto area
(416/647/437/905/289)" cannot be fulfilled as written against current ACS inventory.** This needs
Marco's decision, not a silent substitution — options on the table, not yet chosen: (a) a different
Canadian geographic locality from the 10 available (none are Toronto-area — nearest is Guelph, ON,
~100km from Toronto, area code 226, not 416/647/437/905/289), (b) a Canada toll-free number instead of
geographic, (c) re-check at purchase time in case ACS's Canadian geographic inventory has changed
(unlikely to shift quickly, but not verified as static). No option chosen or acted on — Stage 9 (number
purchase) has not run.

## R-05 supplemental — decision 13 revision, live purchasable number, inventory volatility, 2026-08-20

**Barrie/705 checked, per Marco's request.** `locality=Barrie, administrativeDivision=ON` → `404
NotFound`, same as Toronto. "Barrie" is not an ACS-recognized locality name (consistent with it not
appearing in the earlier full 10-locality nationwide dump). **But the 705 area code itself is live** —
reachable via `locality=North Bay` or `locality=Sault Sainte Marie` (both ON, both returned `areaCode:
705`). Area code, not city name, is what determines the number's dial-in prefix; North Bay/Sault Ste
Marie share the 705 numbering plan area with Barrie.

**Guelph disappeared from the inventory between two checks in this same session** — a genuine
volatility finding, not a query artifact:
- First check (Stage 8, earlier this session): `locality=Guelph` → `200`, `areaCode: 226`. Full
  nationwide dump: 10 localities, Guelph included.
- Second check (~20 minutes later, same query, retried 3x to rule out a fluke): `locality=Guelph` →
  `404 NotFound`, all 3 attempts. Full nationwide dump re-run: **8 localities**, Guelph and Biggar both
  gone (`Brockville, North Bay, Sault Sainte Marie, Thunder Bay` [ON], `Chicoutimi, Montreal, Thetford
  Mines` [QC], `Lanigan` [SK]).
- **Consequence**: a `List Area Codes`/`List Localities` 200 response is a point-in-time snapshot, not
  a purchase guarantee — confirmed empirically, not just as a theoretical caveat. Any purchase must
  re-verify with `Search Available Phone Numbers` immediately beforehand, not rely on an
  earlier-in-session check, however recent.

**Actual purchasable-number check, per Marco's explicit request** (a locality/area-code 200 is not the
same as confirmed inventory) — used `Search Available Phone Numbers`
(`POST .../availablePhoneNumbers/countries/CA/:search?api-version=2025-06-01`, current GA version,
confirmed via the `api-supported-versions` response header). Request:
```json
{
  "phoneNumberType": "geographic",
  "assignmentType": "application",
  "capabilities": {"calling": "inbound", "sms": "none"},
  "areaCode": "705",
  "quantity": 1
}
```
Result (polled from the `Location` header after `202 Accepted`):
```json
{
  "searchId": "6ee7c101-2c3d-490a-8b15-0f5f4c38c485",
  "phoneNumbers": ["+17054829832"],
  "phoneNumberType": "geographic",
  "assignmentType": "application",
  "capabilities": {"calling": "inbound", "sms": "none"},
  "cost": {"amount": 1.0, "currencyCode": "USD", "billingFrequency": "monthly"},
  "searchExpiresBy": "2026-08-20T21:42:44.5980893+00:00",
  "isAgreementToNotResellRequired": false,
  "error": "NoError"
}
```
Confirmed real, purchasable, correctly capabilitied (inbound-only, no SMS, matching decision 17's
scope), $1.00/mo — matches `COSTS.md`. This search hold itself is non-billable and expires in <15min
(per Microsoft's documented behavior) — it does not commit to a purchase; nothing has been bought.
**This specific searchId will very likely be expired by the time Stage 9 actually runs — a fresh
search is required at purchase time regardless, same discipline as the Toronto re-check below.**

**Toronto re-checked once more, as requested** (in case inventory had shifted by the time of this
supplemental check): still `404 NotFound`. No change — did not need to stop and flag.

**Per-minute inbound rate — confirmed unaffected by locality choice.** Checked whether Canada PSTN
pricing varies by region/area code (relevant since the number moved from a hypothetical Toronto
listing to a confirmed North Bay one). Microsoft's own PSTN pricing doc
(`articles/communication-services/concepts/pstn-pricing.md`) states a single national table for
Canada, no regional/city/area-code breakdown:

| Number type | Lease | Inbound | Outbound (starting at) |
|---|---|---|---|
| Geographic | $1.00/mo | $0.0085/min | $0.0130/min |
| Toll-free | $2.00/mo | $0.0220/min | $0.0130/min |

Confirms `COSTS.md`'s existing $0.0085/min figure is unchanged for a 705 number — **no COSTS.md edit
needed, no R-08 recomputation triggered**, since the input that feeds R-08 didn't move. Also confirms
the toll-free rejection reasoning in decision 13: 2.6x the inbound per-minute rate, 2x the monthly
lease — both real costs against R-08's already-tight budget, not toll-free's often-cited "free to
caller" upside (irrelevant here — the caller is Marco's own mobile, not a cost-sensitive third party).

**Decision: proceed with 705 (North Bay, ON)**, per Marco's own stated conditional (705 first, Guelph
as fallback) — 705 turned out to be the one that's actually live, while the originally-planned
fallback (Guelph) evaporated during this same session. `docs/PLAN.md` decision 13 updated accordingly.
**Not yet purchased** — Stage 9 has not run; a fresh `Search Available Phone Numbers` call is required
immediately before it does, per the volatility finding above.

## ACS Canadian phone number inventory is genuinely volatile, not just thin (R-05/R-09), 2026-08-20

Standalone write-up — the raw queries live in "R-05" and "R-05 supplemental" above; this consolidates
what they show into one finding, because it's a real operational characteristic of the platform, not
documented anywhere Microsoft publishes, and it drove a hard rule (R-09, `docs/PLAN.md`).

**What was measured, not assumed:**

| Check | Time | Result |
|---|---|---|
| `List Localities`, all Canada, unfiltered | Stage 8, first pass | 10 localities: Brockville, Guelph, North Bay, Sault Sainte Marie, Thunder Bay (ON); Chicoutimi, Montreal, Thetford Mines (QC); Biggar, Lanigan (SK) |
| `List Area Codes`, `locality=Guelph` | Stage 8, first pass | `200`, `areaCode: 226` |
| `List Area Codes`, `locality=Guelph` | ~20 min later, retried 3x | `404 NotFound`, every attempt |
| `List Localities`, all Canada, unfiltered | ~20 min later | 8 localities: Guelph **and** Biggar both gone; the other 8 unchanged |

**Why this isn't a query bug, an auth issue, or a fluke:**
- Retried the failing query 3 separate times, 2 seconds apart — consistent `404` every time, not
  intermittent.
- Ran a control query against a locality that *did* still return results (Brockville, North Bay,
  Sault Sainte Marie, Thunder Bay all returned clean `200`s with real area codes in the same window) —
  proves the endpoint, token, and query shape all still work correctly; the absence is data, not error.
- The unfiltered, whole-country locality dump (no `locality`/`administrativeDivision` filter at all)
  independently corroborates the drop — not just one filtered query changing behavior, the actual
  inventory list shrank.

**What this means in practice, beyond the Toronto/705 decision it drove:**
1. A `200` from `List Area Codes` or `List Localities` is a point-in-time snapshot with **no stated
   TTL** anywhere in Microsoft's documentation — it is not a purchase guarantee, and the gap between
   "confirmed available" and "gone" was observed to be as short as ~20 minutes in this project's own
   usage, not a hypothetical edge case.
2. Canada's ACS geographic-number inventory is **thin in absolute terms** (single digits to low tens
   of localities nationwide, not hundreds) *and* **actively changing**, which is a materially different
   risk profile than "thin but stable." A capacity-planning assumption based on one inventory check
   would already be stale by the time a second engineer reads it.
3. This has no documented explanation from Microsoft (not a rate limit, not a permissions scope, not
   an API version issue — all ruled out above). The most likely explanation is real-time competition
   for a small shared pool of numbers across all ACS customers purchasing in the same localities, but
   that's inference, not confirmed — stated as inference, not fact.
4. **Operational consequence, now a hard rule (R-09, `docs/PLAN.md`; also a `CLAUDE.md` stop
   condition)**: any number this project owns is treated as irreplaceable once purchased. No teardown
   script may ever release it, and every purchase-adjacent script must re-verify actual inventory
   (`Search Available Phone Numbers`, not `List Area Codes`/`List Localities` — those only prove a
   *locality* is server-side recognized, not that a number is currently reservable) immediately before
   acting, never from an earlier check in the same session.

This is the kind of platform behavior that only surfaces from actually operating against live ACS
inventory across a working session, not from reading Microsoft's docs or pricing pages — worth keeping
in the Phase 8 write-up as evidence of hands-on platform experience, not just planning.

## Stage 9 — number purchased, 2026-08-20

`+17059100383` purchased (705, North Bay/Sault Ste Marie, ON numbering plan area), per decision 13's
revision. Full purchase sequence:

1. Fresh `Search Available Phone Numbers` (the earlier session's hold had expired): `searchId
   22028db4-cd04-4ed5-96d5-b1cf4ff1c862`, candidate `+17059100383`, `cost: {amount: 1.0,
   currencyCode: USD, billingFrequency: monthly}`, `searchExpiresBy: 2026-08-20T21:59:56Z`.
2. Toronto re-checked once more immediately before purchase (per Marco's standing instruction) — still
   `404 NotFound`, no change.
3. `POST /availablePhoneNumbers/:purchase` with that `searchId` → `202 Accepted`, `operation-id
   purchase_22028db4-cd04-4ed5-96d5-b1cf4ff1c862`.
4. Polled `GET /phoneNumbers/operations/{operationId}` — `notStarted` x3, then `status: succeeded`
   (~20s total).
5. **Confirmed from the live owned-numbers list, not the purchase response** (per Marco's explicit
   instruction — an operation reporting `succeeded` is not itself proof, per the same discipline this
   session already applied to Stage 7's `NoAutoUpgrade`): `GET /phoneNumbers` returned the number with
   `purchaseDate: 2026-08-20T21:46:17.2076119+00:00`, `cost: {amount: 1.0, currencyCode: USD,
   billingFrequency: monthly}`, `capabilities: {calling: inbound, sms: none}` — matches the search
   result exactly, matches decision 17's scope exactly.
6. Checked `GET /phoneNumbers/{number}` (Get By Number) for any additional billing-cycle field —
   returns the same fields as the list endpoint, no next-bill-date or cycle-anchor field exposed by
   either. First actual billing date is therefore **not confirmed by the API**; will be settled by
   Cost Analysis in script 3 (~24h check). Recorded honestly as unconfirmed in `COSTS.md` rather than
   inferred.

`docs/phase0/wizard/.env.phase0` updated: `PHONE_NUMBER=+17059100383`. Full detail and the R-09 policy
this purchase falls under: `COSTS.md`, "First billable resource purchased."

## `az` CLI stale `defaults.location` — resource-enumeration blind spot (B4), 2026-08-21

A resume-discipline live-state check (`az resource list -g rg-azure-banking-voice-agentic-ai`) returned
`[]` on a resource group independently confirmed populated (`az cognitiveservices account show`, `az
communication list`, `az communication phonenumber list` all returned the expected AOAI resource, ACS
resource, and phone number). Root-caused rather than dismissed as CLI flakiness, per Marco's explicit
instruction not to assert "unreliable" without finding the mechanism.

**Root cause**: `~/.azure/config` (machine-level, `/Users/marco/.azure/config`, not project-scoped, not
version-controlled) has `[defaults] location = eastus` — leftover from some other project/session, not
this one. `az config get` confirms it's the *only* `defaults.*` key set on this machine (no other
default, no `AZURE_*` environment variable adding a second override layer). `az resource list -g <rg>`
silently folds that default into a server-side OData filter — confirmed via `--debug`:

```
GET .../resources?$filter=resourceGroup eq 'rg-azure-banking-voice-agentic-ai' and location eq 'eastus'&...
```

This project's resource group is `canadacentral` (AOAI) / `global` (ACS) — neither matches `eastus`,
so the filtered query legitimately, silently returns empty. Confirmed the fix: `az resource list -g
<rg> --location ""` cancels the filter and correctly returns both resources.

**Audited every `az ... create` call site in `01-provision.sh` for the same exposure** (a create
silently landing in the wrong region would be a data-residency break, not just a display bug):

| Call site | `--location` passed? | Exposed? |
|---|---|---|
| `az group create` (:407) | explicit `"$LOCATION"` | No |
| `az cognitiveservices account create` (:413, AOAI) | explicit `"$LOCATION"` | No |
| `az cognitiveservices account deployment create` (:434, :474) | command has no `--location` param at all (confirmed via `--help`) — scoped to the parent account | No — architecturally immune |
| `az communication create` (:520, ACS) | explicit `"global"` | No, **but** `--help` confirms this command *does* fall back to `defaults.location` when omitted — safe today only because the flag is present; flagged for a guarding comment |
| `az containerapp env create` (:1041) | explicit `"$LOCATION"` | No |
| `az containerapp create` (:1051, Stage 12) | command has no `--location` param at all (confirmed via full `--help` param dump) — a Container App's region is fixed by its `--environment`, not settable per-app | No — architecturally immune |
| `az eventgrid event-subscription create` (:1101) | command has no `--location` param — scoped to `--source-resource-id` | No — architecturally immune |

`$LOCATION` itself is a hardcoded literal (`LOCATION="canadacentral"`, :203), not derived from any CLI
default, so it isn't a second exposure path. **Conclusion: no `create` call site in this script is
exposed to the stale default** — Stage 12's two creates (env + app) are both clean, one explicit, one
architecturally immune.

**What *is* exposed, and matters for B4**: `01-provision.sh:234` and `02-test-calls.sh:66`, both inside
their scripts' `on_error` traps, call the vulnerable form
(`az resource list --resource-group "$RESOURCE_GROUP" --output table`, no `--location` override) to
show Marco what exists/bills at the moment a script fails. On a machine with this stale default, that
display silently prints empty even while the Container App is up and billing. The actual delete-offer
logic immediately below it (`az containerapp show --name "$CONTAINERAPP_NAME" ...`) is a scoped direct
GET, unaffected by the location filter, so **the automated safety mechanism itself still fires
correctly** — it's the human-facing "here's what exists" table that's silently wrong, at exactly the
moment a human needs to trust it.

**Fix identified, not yet applied** (per Marco's instruction — shown as a diff, pending sign-off):
add `--location ""` to both `az resource list` call sites to unconditionally cancel any machine-level
default, regardless of what `~/.azure/config` says on whatever machine runs this script next; and a
guarding comment on the `az communication create` call site noting it must keep an explicit
`--location` because that command (unlike the ones proven architecturally immune above) does honor the
stale default when omitted. `~/.azure/config` itself deliberately left untouched — a machine-level fix
there would be invisible to this repo and could affect the FNOL project sharing this machine in ways
not evaluated here.

## Why `min-replicas=1`, not `0` — checked, partially confirmed, 2026-08-21

Marco's read: ACS's inbound webhook can't absorb a cold start on `IncomingCall`. Checked against
`docs/PLAN.md` rather than answering from memory. What's actually there (line 348): "`min-replicas=0`
is **disqualifying** for inbound telephony (cold start seconds→30s)" — this confirms the *conclusion*
(scale-to-zero is out) and the *magnitude* (up to 30s), sourced to "decision 15," but **does not spell
out the specific failure mechanism**. Searched `docs/PLAN.md`, `docs/adr/`, and this file for a
separate "decision 15" entry defining that mechanism — found only two citations (lines 348, 476), no
standalone definition. So: Marco's read is directionally consistent with the stated conclusion (a
30-second gap before a cold container answers is not viable for a live inbound call either way — the
caller experience fails regardless of which specific layer times out first) but the precise mechanism
(Event Grid webhook delivery timeout vs. ACS's own call-answer timeout vs. plain caller-perceived dead
air/ring delay) isn't confirmed by any text found in this repo. **Mechanism unconfirmed, logged as an
open Phase 2 question — does not change the setting.** `min-replicas` stays `1` either way; the
unconfirmed mechanism affects only how the reason gets written up later, not what Stage 12 does. No
`/research` pass on this — Marco's explicit call.

## Stage 12 abort path — `PROVISION_TIME` / R-04 window, verified from script logic, 2026-08-21

Not yet observed live (Stage 12 hasn't run) — verified by reading `01-provision.sh`'s actual control
flow, not by running it.

- `PROVISION_TIME` is written at line 1105 (was 1096 before this session's edits), **strictly after**
  the health-check success branch. The failure branch (`HEALTHY != 1` after 2 minutes, line 1098) logs
  recent container logs and calls `on_error 1` (line 1102), which — per its own definition (line
  228ff) — reports what exists in `$RESOURCE_GROUP`, offers to delete the Container App + environment,
  and `exit`s. **`PROVISION_TIME` is never reached on that path.** So: a failed first attempt does not
  start R-04's window — there is no window to "abandon," because none was ever opened.
- Re-running `01-provision.sh` after a failed attempt: `az containerapp show` (line 1054) finds the
  already-created Container App and takes the "update existing" branch (`az containerapp update
  --image`, not `create`) rather than re-provisioning from scratch. The healthz wait re-runs regardless
  of which branch was taken; `PROVISION_TIME` is written on whichever attempt is the first to actually
  pass health — that attempt's timestamp is what anchors the window, not the first attempt overall.
- **Separate from window validity**: a failed attempt that isn't cleaned up (Marco declines `on_error`'s
  delete offer, to fix-and-retry quickly) still leaves the Container App + environment billing hourly
  (`min-replicas=1`) from whenever `az containerapp create` ran, independent of whether healthz ever
  passed or `PROVISION_TIME` was ever written. That spend is real and unanchored to any R-04 window —
  the `on_error` cleanup offer is what stops it, not `PROVISION_TIME`'s absence.

**Marco's standing decision, 2026-08-21**: if healthz never goes green, **accept `on_error`'s delete
offer.** Tear down the Container App and its environment rather than leave either billing while
debugging — don't fix-and-retry against a live, still-billing resource. Confirmed the offer actually
covers both, not just the app (`01-provision.sh:246-247`):
```
az containerapp delete --name "$CONTAINERAPP_NAME" --resource-group "$RESOURCE_GROUP" --yes --output none 2>/dev/null || true
az containerapp env delete --name "$CAE_NAME" --resource-group "$RESOURCE_GROUP" --yes --output none 2>/dev/null || true
```
Both calls fire on a single "Delete it now?" confirmation — app first, then its environment. Next
attempt after accepting is always a fresh `az containerapp create` (line 1060), never the `update`
branch, since `az containerapp show` finds nothing once both are gone.

**Revision-swap deferral, reasoning corrected 2026-08-21**: an earlier chat-only note said the revision-
swap rollout-mechanics question (does an `update` health-gate the new replica before killing the old
one, or leave a gap — unresolved, `/research`-worthy per the Docker Hub token turn) "only matters if
something touches the app after Stage 12." That's wrong on its own terms — this section's own finding
is that a failed-healthz retry (before the standing decision above existed) takes the `az containerapp
update --image` branch (line 1056), which **is** a revision swap, and that can happen before Stage 12
ever finishes. The actual reason it doesn't block: no R-04 window is open pre-healthz regardless (per
`PROVISION_TIME`'s placement, above) — the deferral is safe because it's scoped by whether the window
is open, not by whether a revision swap could occur at all. Corrected here so it doesn't read as
settled later.

**`update`'s config scope, verified against `--help`, not observed live**: `az containerapp update`
has **no** `--registry-server`/`--registry-username`/`--registry-password`/`--secrets`/`--target-port`/
`--ingress` parameters — confirmed by grepping the full parameter list, zero matches. These aren't
"left unspecified and therefore preserved," they're **structurally absent from the command** — there is
no way to change registry credentials, secrets, target port, or ingress via `az containerapp update` at
all, which means a retry cannot accidentally clear or diverge them from whatever the original `create`
set. `--min-replicas`/`--max-replicas`/`--cpu`/`--memory` do exist as `update` params but aren't passed
by the script's call; Microsoft's own canonical example for this command (`az containerapp update -n
... --image myregistry.azurecr.io/my-app:v2.0`, nothing else) matches the script's exact pattern and
documents that existing settings are preserved when omitted, not reset. **Caveat**: this is verified
from `--help`'s documented parameter surface, not from watching a real retry happen — no Container App
has existed this session to observe. In practice this whole question is moot now: the standing decision
above means the `update` branch never fires on a failed-healthz retry — every retry after a delete is a
fresh `create` with full config. It would only matter for some *other* re-run that reaches Stage 12 with
the app already existing and healthy (e.g., re-running the script after a successful prior run to push
an unrelated fix) — a different scenario than the abort path this section is about.
## R-01 — Models API deprecation-date check

Queried 2026-08-21T16:01:13Z against location=canadacentral.
```json
[
  {
    "version": "2025-10-06",
    "deprecationDate": {
      "inference": "2027-04-06T00:00:00Z"
    },
    "raw": {
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
    }
  },
  {
    "version": "2025-12-15",
    "deprecationDate": {
      "inference": "2026-12-15T00:00:00Z"
    },
    "raw": {
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
    }
  },
  {
    "version": "2025-10-06",
    "deprecationDate": {
      "inference": "2027-04-06T00:00:00Z"
    },
    "raw": {
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
    }
  },
  {
    "version": "2025-12-15",
    "deprecationDate": {
      "inference": "2026-12-15T00:00:00Z"
    },
    "raw": {
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
    }
  }
]
```

## R-05 — live Toronto-area area-code inventory

Query: locality=Toronto, administrativeDivision=ON, phoneNumberType=geographic,
assignmentType=application, api-version=2025-06-01
```json
{"areaCodes":[{"areaCode":"647"}],"nextLink":null}
```

All Canada-wide geographic localities in ACS's inventory (unfiltered, maxPageSize=100):
```json
{"phoneNumberLocalities":[{"localizedName":"Calgary","administrativeDivision":{"localizedName":"AB","abbreviatedName":"AB"}},{"localizedName":"White Rock","administrativeDivision":{"localizedName":"BC","abbreviatedName":"BC"}},{"localizedName":"Halifax","administrativeDivision":{"localizedName":"NS","abbreviatedName":"NS"}},{"localizedName":"Brockville","administrativeDivision":{"localizedName":"ON","abbreviatedName":"ON"}},{"localizedName":"Cooksville","administrativeDivision":{"localizedName":"ON","abbreviatedName":"ON"}},{"localizedName":"North Bay","administrativeDivision":{"localizedName":"ON","abbreviatedName":"ON"}},{"localizedName":"Ottawa","administrativeDivision":{"localizedName":"ON","abbreviatedName":"ON"}},{"localizedName":"Ottawa-Hull","administrativeDivision":{"localizedName":"ON","abbreviatedName":"ON"}},{"localizedName":"Thunder Bay","administrativeDivision":{"localizedName":"ON","abbreviatedName":"ON"}},{"localizedName":"Toronto","administrativeDivision":{"localizedName":"ON","abbreviatedName":"ON"}},{"localizedName":"Chicoutimi","administrativeDivision":{"localizedName":"QC","abbreviatedName":"QC"}},{"localizedName":"Gatineau","administrativeDivision":{"localizedName":"QC","abbreviatedName":"QC"}},{"localizedName":"Montreal","administrativeDivision":{"localizedName":"QC","abbreviatedName":"QC"}},{"localizedName":"Sherbrooke","administrativeDivision":{"localizedName":"QC","abbreviatedName":"QC"}},{"localizedName":"Thetford Mines","administrativeDivision":{"localizedName":"QC","abbreviatedName":"QC"}},{"localizedName":"Victoriaville","administrativeDivision":{"localizedName":"QC","abbreviatedName":"QC"}},{"localizedName":"Lanigan","administrativeDivision":{"localizedName":"SK","abbreviatedName":"SK"}}],"nextLink":null}
```

## Stage 12 — ECHO_DIR misdirection (root cause) and linux/amd64 arch mismatch (symptom), 2026-08-21

**Symptom Marco hit at `az containerapp create`:**
```
Field 'template.containers.ca-azbank-echo-p0.image' is invalid: no child with
platform linux/amd64 in index docker.io/maofilho/azbank-echo-p0:latest
```
Expected on Apple Silicon: `docker build` with the classic builder produces a single-arch
`arm64` image by default; Container Apps requires `linux/amd64`.

**What the arch error was masking.** `01-provision.sh` computes
`ECHO_DIR="$SCRIPT_DIR/../echo-app"` (line 897), and `SCRIPT_DIR` is the wizard script's own
directory, `docs/phase0/wizard`. That resolves to **`docs/phase0/echo-app`** —
not `docs/echo-app`, the git-tracked directory this session actually edited, tested
(`py_compile`), and committed at `1004d54` with the SDK-version fix, the DTMF/B2 gating, and
the `pip freeze` build assertion.

`docs/phase0/echo-app/` is untracked (`git log` for it: empty; `git check-ignore`: not
ignored either, exit 1) and its `app.py` mtime (12:02:05) postdates `docs/echo-app/app.py`'s
last session edit (10:57:44) — it was written by this run's own Stage 11, from the *original,
unfixed* heredoc template, because the Stage 11 guard added this session checks
`$ECHO_DIR/app.py` (correctly, per its own logic) but `$ECHO_DIR` was never the directory this
session had been fixing. Contents confirmed by direct diff against the committed
`docs/echo-app/`: SDK pin back at `azure-communication-callautomation==1.2.*` (no media
streaming support at all — see `## R-01`/Stage 11 commit above), `azure-identity==1.19.*`
still present, `MediaStreamingTransportType` (wrong class name), no `enable_dtmf_tones`,
**no B2 gating block at all** — its DTMF handler logs `msg.get("dtmfData", {}).get("data")`
unconditionally, every digit, no `PHASE0_LOG_DTMF_VALUES` check — and its Dockerfile has no
`pip freeze`/`test -s` build assertion line, which directly answers item 3: the assertion
genuinely never existed in the image that got built, not because it was dropped, but because
the build never read the Dockerfile that has it.

**Severity note, not just a build nuisance:** Phase 0 has no PIN/auth path yet, so this
specific near-miss carries no live PIN-confidentiality breach — but it is the shape of a B2
violation (unconditional raw-value logging on the exact DTMF path), shipped from an untracked
file nobody reviewed, caught only because an unrelated architecture mismatch happened to fail
first. `az containerapp create` failing loudly on `image` is why this wasn't discovered by a
green healthz check instead.

**Fix (pending Marco's confirmation, not yet applied — Stage 11/12 script edits are
DTMF/PIN-path-adjacent per `CLAUDE.md`'s B2 stop condition):** point `ECHO_DIR` at
`docs/echo-app` (`$SCRIPT_DIR/../../echo-app`, verified by path arithmetic:
`docs/phase0/wizard/../../echo-app` = `docs/echo-app`), and treat `docs/phase0/echo-app/` as
contaminated scratch — never commit it, recommend deleting it once Marco says so.

**Gotcha for anyone rebuilding on Apple Silicon** (item 4, independent of the above): the
classic `docker build` builder targets the host architecture by default. `docker buildx`
(confirmed present locally, `v0.35.0-desktop.2`) supports `--platform linux/amd64` and can
build+push in one step; a manifest check between push and `containerapp create`/`update`
(`docker buildx imagetools inspect "$IMAGE"`, checked for `linux/amd64` in its platform list)
is the proposed fail-loud gate, same shape as the Dockerfile's own `pip freeze && test -s`
assertion — catch it before the billable step, not after.

**The finding worth remembering isn't the architecture mismatch — it's what it accidentally
prevented.** Had this been built on amd64 hardware, `az containerapp create` would have
succeeded on the first try, deploying an image whose DTMF handler logs raw tone values
unconditionally, with no `PHASE0_LOG_DTMF_VALUES` gate at all. Nothing in the wizard's own
flow would have caught that: `/healthz` would have gone green, Stage 12 would have reported
success, and the next 72 hours would have been spent measuring R-04/R-08 against a container
that was, the whole time, logging exactly the class of value B2 exists to keep out of any log
line. The architecture mismatch is the only reason this was caught — not a guard, not a
review, not a test. That's the gap this session's fix (git-root-anchored `ECHO_DIR` plus a
hard exist-and-git-tracked assertion, `01-provision.sh` Stage 11) is meant to close
structurally, so the next near-miss doesn't need an unrelated failure to get noticed.

**RESOLVED 2026-08-21**: `ECHO_DIR` now resolves via `git -C "$SCRIPT_DIR" rev-parse
--show-toplevel` rather than a relative `../..` chain, points at the git-tracked
`docs/echo-app/`, and Stage 11 asserts the target exists and is git-tracked before Stage 12
can run — no template-regeneration fallback remains in the script. `docs/phase0/echo-app/`
(the orphaned, untracked directory) has been deleted. Every other `$SCRIPT_DIR/..`-relative
path in the four wizard scripts (`REPO_ROOT`, `FINDINGS_FILE` ×4, `COSTS_FILE`) was audited
and confirmed correct by direct execution (`cd ... && pwd`, `realpath`), not by counting `..`
— `ECHO_DIR` was the only one that was wrong, and it was wrong by intent, not by arithmetic:
the path always resolved exactly where its own math said it would, to a directory that turned
out to hold the wrong content.

## Stage 10 regression, and the pattern behind three separate findings today

A live run of `01-provision.sh` (before the Stage 10 guard existed) regenerated
`docs/adr/ADR-002-geography-knobs.md` from its in-script heredoc template, using that run's own
live variable state. The committed file correctly reads `+17059100383` (the real, purchased
number); the regenerated working-tree copy read `<pending>` — a real content regression, not
cosmetic (`ADR-001`'s regeneration only bumped a date). Caught before commit by inspecting
`git diff` rather than assuming Stage 10's overwrite was harmless because it had been flagged as
"low-risk" earlier in the session. Reverted via `git checkout --`, confirmed clean
(`+17059100383` present, `<pending>` absent).

**This is the third instance of the same pattern in one session**, not three unrelated bugs:

1. **Stage 11** regenerated `docs/echo-app/`'s equivalent from a frozen template on every
   re-run, until guarded.
2. **The `ECHO_DIR` misdirection itself** was this same pattern one level removed: the guard
   added for #1 was correct in form but pointed at the wrong directory, so it faithfully
   protected the *wrong* file from regeneration while the *real* reviewed file
   (`docs/echo-app/`) was never wired to the script at all.
3. **Stage 10**, this entry — regenerated committed, human-relevant ADR content from a
   template, unguarded, the moment a real run reached it for a second time.

**The general principle, stated once rather than left implicit three times**: any wizard
stage that writes a file it doesn't exclusively own is a regression risk from the moment that
file has been read, reviewed, hand-edited, or committed by a human — regardless of whether the
stage's own guard logic is otherwise correct. A guard that checks the right condition against
the wrong path (#2) is exactly as dangerous as no guard at all (#1, #3 before their fixes). See
the full remaining-risk audit below.

## Full audit: every remaining file-write in all four wizard scripts, 2026-08-21

Requested after the Stage 10 finding above — not just the one path that broke, every write
site. Two write patterns exist in these scripts, and they carry different risk shapes:

**Heredocs (`cat > file <<...`) — whole-file regeneration from a template.** This is the
dangerous shape (#1–#3 above). Full inventory: exactly two remain, both `docs/adr/` writes,
both now guarded (skip if both ADR files already exist) as part of this same fix. **Zero
unguarded heredocs remain in any of the four scripts** — Stage 11's was removed entirely
rather than guarded.

**`write_env` calls — surgical single-key upsert into `.env.phase0`.** Structurally different
and lower-risk by construction: `write_env` rewrites only the one line matching `^key=`,
leaving every other line (including any a human hand-edited) untouched. Not the heredoc
pattern. Of the ~20 call sites across all four scripts:
- Most write fixed naming constants (`RESOURCE_GROUP`, `CONTAINERAPP_NAME`, `CAE_NAME`, …),
  freshly-queried live Azure state (`AOAI_ENDPOINT`, `APP_BASE_URL`), or a value the human just
  typed interactively that same run (`DOCKERHUB_USERNAME`) — safe by nature, same class as
  Stage 2/8's deliberate free re-verification.
- `PHONE_NUMBER` (Stage 9) and `R06_ANSWER_SHORT` (Stage 6) are protected transitively by
  their enclosing stage guards added earlier this session.
- **`PROVISION_TIME` (`01-provision.sh`, after the healthz check, Stage 12) — one real,
  currently-latent finding.** Unconditional every time execution reaches that line with a
  healthy container, regardless of whether the `create` or `update` branch fired above it.
  Not triggered by any run so far — `containerapp create` has never actually succeeded yet
  (every attempt failed before completion: first the arch mismatch, now fixed), so the next
  successful run will be genuinely first-time. But a *future* re-run of this script after a
  successful deploy — for an unrelated fix, say — would silently reset this timestamp, and
  R-04's 72-hour idle-billing window is anchored on it. Flagged, not guarded, matching how
  Stage 10's ADR risk was originally handled before it fired for real. Marco's call whether to
  guard it now or accept the risk until it's closer to mattering.

**`COSTS.md` appends — two unguarded duplicate-append sites, lower severity (additive, not
destructive, but still a re-run hazard):**
- `03-cost-check-24h.sh` Stage 1 (`>> "$COSTS_FILE"`, the Free Services portal check section)
  — no guard against re-appending an identical section on a re-run.
- `04-teardown-and-r08.sh`'s final "Measured, not estimated" section (`>> "$COSTS_FILE"`) — the
  file-creation preamble above it *is* guarded (`if [[ ! -f "$COSTS_FILE" ]]`), but the actual
  R-04/R-08 results block that follows is not; a re-run would duplicate-append rather than
  overwrite the earlier measurement.

Both `COSTS.md` sites are the same shape as the original (now-fixed) Stage 2/Stage 6
`findings.md` duplicate-append risk, just in a different file. Not fixed as part of this
commit — reported per the audit request, Marco's call on priority.

## Re-run guards verified live, 2026-08-21

A real re-run of `01-provision.sh` (after the `ECHO_DIR`/buildx/Stage-10/`PROVISION_TIME`
fixes above) reached Stage 12 and failed at `docker login` (unauthorized — token issue, not a
script bug). Before that failure, **Stages 6, 9, 10, and 11 all skipped as designed**: no
duplicate R-06 probe, no second phone-number purchase attempt (R-09's number, `+17059100383`,
untouched), no ADR regeneration, no echo-app regeneration. Nothing billable was created by
this run. First real evidence these guards work under an actual re-run, not just `bash -n` and
inspection — recorded as verified, not just written.

**Same run, one gap found**: the `docker login` failure surfaced as raw `registry-1.docker.io`
daemon output, not a wizard-framed message. Fixed — wrapped with the same `on_error` pattern as
every other Stage 12 check, framed toward the most likely cause (wrong/expired token, or
missing Read & Write scope) rather than requiring the operator to parse registry error text.

## APP_BASE_URL placeholder race — the call that reached the app and still failed

First real test call: rang ~60s, nobody answered, despite `/healthz` returning `{"status":"ok"}`
from a browser and Event Grid delivering `Microsoft.Communication.IncomingCall` correctly
(`provisioningState: Succeeded`, endpoint matched the live FQDN exactly). Container App logs
showed the actual failure: `answer_call()` raised `HttpResponseError: (400) Invalid request —
The field CallbackUri is invalid`, on two separate `IncomingCall` deliveries, both producing a
`500` back to Event Grid.

Root cause, confirmed by direct inspection, not assumed: Stage 12 created the Container App with
`app-base-url` secret literally set to the string `"placeholder"` (the real FQDN doesn't exist
until after `containerapp create` returns), then queried the live FQDN and patched the secret
*afterward* via `containerapp secret set` + `containerapp update --set-env-vars`. `az containerapp
revision list` showed exactly **one** revision, from container start to failure — the later patch
never created a new revision, and Container Apps injects `secretRef` env vars as literal OS
environment variables at container start, not a live-refreshed value. `app.py` reads
`APP_BASE_URL` once at import time (`APP_BASE_URL = os.environ["APP_BASE_URL"]`), so the running
process almost certainly held `APP_BASE_URL="placeholder"` the entire time, making
`CALLBACK_URL = "placeholder/api/callbacks"` — exactly what "The field CallbackUri is invalid"
describes. Could not directly confirm via the process's live environment (no read-only path
found — see below); confirmed instead by fixing the root cause and verifying the FQDN was
knowable before creation, which the diagnosis didn't strictly require but strengthens it.

**Fixed 2026-08-21**: `az containerapp env show --query properties.defaultDomain`, queried
*before* `containerapp create`, reproduces the real FQDN exactly (`{app-name}.{defaultDomain}` —
verified live against the actual running app: `ca-azbank-echo-p0.livelybay-0fe80dd3.
canadacentral.azurecontainerapps.io`). The environment already exists by the point Stage 12
creates the app, so the true `APP_BASE_URL` is computable up front. No more placeholder, no more
post-create secret/env patch, no revision-forcing needed — the first (and only) revision now
starts with the correct value. A post-create assertion checks the computed value against the
live FQDN and fails loudly (before Event Grid is wired) if the `defaultDomain` formula and
reality ever diverge.

**Two options considered and rejected**, for the record:
- *Force a new revision after patching the secret* (`--revision-suffix`) — works, but still ships
  a broken first revision and depends on an unverified assumption that the flag actually forces
  recreation. Strictly worse than not creating the placeholder at all.
- *Read `APP_BASE_URL` lazily per-request in `app.py`* — does not work. Container Apps'
  `secretRef` env vars are fixed for a process's entire lifetime once it starts; re-reading
  `os.environ` more often doesn't produce a different value without an actual new container start.

**No read-only way found to directly confirm the live process's environment.** Checked two paths:
`az containerapp logs show --tail 300` only retains back to a few minutes before the check (never
reached the container's actual `21:56:37Z` start), and the Log Analytics workspace nominally
linked to the environment had zero rows in `ContainerAppConsoleLogs` (see next section — a real,
separate gap). Only `exec` would have read `os.environ` directly; not used, per the read-only
constraint in place at diagnosis time.

## healthz-as-window-gate — the design flaw, more interesting than the bug that triggered it

`PROVISION_TIME` (R-04's 72h idle-billing anchor) was written by `01-provision.sh` immediately
after `/healthz` returned `200`. Today's failure showed exactly why that's the wrong gate: the
container was genuinely healthy — serving HTTP, responding to `/healthz`, receiving and even
correctly routing `IncomingCall` events from Event Grid — and still could not perform the one
thing this whole project exists to do: answer a phone call. **A green health check is evidence a
process is running, not evidence the system it's part of works.** R-04's 72h window had already
been open for the two prior failed-answer attempts and would have stayed anchored to that moment
regardless of whether a call ever succeeded, silently measuring idle-vs-active billing behavior
against a container that had never demonstrated it could do its job.

**Fix (designed, not yet applied — pending Marco's sign-off on the diff)**: `PROVISION_TIME`'s
write moves out of `01-provision.sh` entirely, into `02-test-calls.sh`, gated on a specific,
verifiable signal — a `Microsoft.Communication.CallConnected` event observed in the Container
App's own logs, not a healthz check and not an operator confirming a prompt. If no such event is
found, `PROVISION_TIME` stays unset and the script exits non-zero rather than silently completing.
`04-teardown-and-r08.sh` needs no changes — it reads `PROVISION_TIME` generically from
`.env.phase0` with no assumption about which script wrote it.

## Log Analytics: two workspaces, neither delivering

Found while investigating why boot-log lines (`PHASE0_LOG_DTMF_VALUES`, `installed-versions.txt`)
couldn't be recovered after the log-streaming buffer scrolled past container start. Two separate
auto-created Log Analytics workspaces exist in the resource group —
`workspace-rgazurebankingvoiceagenticaixC` (found and documented in an earlier session, unused)
and `workspace-rgazurebankingvoiceagenticaiCS` (the one actually linked to the current Container
Apps environment via `appLogsConfiguration`) — almost certainly the result of the environment
having been created more than once across today's several partial Stage-12 attempts. Querying
the *correctly*-linked workspace's `ContainerAppConsoleLogs` table still returned **zero rows**,
over an hour after a running, actively-logging container — the native
`appLogsConfiguration`-based log forwarding is configured but not delivering, for reasons not
diagnosed. No classic Diagnostic Settings resource existed on the environment as a fallback path
(`az monitor diagnostic-settings list` returned empty).

**Fixed 2026-08-21**: added an explicit `az monitor diagnostic-settings create` targeting the
environment resource, routing `ContainerAppConsoleLogs` and `ContainerAppSystemLogs` to the
correctly-linked workspace. Whether this resolves the delivery gap or the native path was simply
slow needs confirming after the next redeploy — not assumed either way. The orphaned second
workspace is left in place (harmless, $0, not touched) rather than deleted without asking.

## Stage 12 — auto-created Log Analytics workspace, cost verified

`az containerapp env create` (line 1086, no `--logs-workspace-id`/`--logs-destination`
flags) always auto-provisions a fresh Log Analytics workspace when none is passed in;
`04-teardown-and-r08.sh` only calls `az containerapp env delete` and never references the
workspace, matching Marco's observation that it survives teardown. Live workspace, queried
directly rather than assumed:
```json
{
  "dailyQuotaGb": -1.0,
  "name": "workspace-rgazurebankingvoiceagenticaixC",
  "provisioningState": "Succeeded",
  "retentionInDays": 30,
  "sku": "PerGB2018"
}
```
`dailyQuotaGb: -1` = no cap set; `PerGB2018` = standard consumption SKU, not a locked
free-tier SKU. Azure Retail Prices API, `armRegionName eq 'canadacentral'`, queried live
(not from memory):
- **Ingestion** (`Analytics Logs Data Ingestion` meter): `$0`/GB for the first pricing tier
  (`tierMinimumUnits: 0`), `$2.76`/GB for the tier above `tierMinimumUnits: 5`.
- **Retention** (`Analytics Logs Data Retention` meter): `$0.12`/GB-month for data held
  past the workspace's included retention window.

At this project's actual log volume (one throwaway Phase 0 echo app, console logs only, a
few hours of a handful of test calls) both meters round to $0 in practice — this is not a
hidden-cost finding. The actual **B4 blind spot** is structural, not financial: this is an
auto-provisioned resource, unaccounted for by name in `COSTS.md`/`docs/PLAN.md`, with no
teardown check verifying its state, that would keep accruing under these same consumption
meters indefinitely if a later phase's log volume ever grew past the free tier — nothing
in this project's cost tooling would currently notice. `az containerapp env create` can
avoid creating it at all (`--logs-destination none`) or point at a pre-existing workspace
(`--logs-workspace-id`/`--logs-workspace-key`, confirmed via `--help`); neither is used
today.

## R-01 — Models API deprecation-date check

Queried 2026-08-21T21:37:07Z against location=canadacentral.
```json
[
  {
    "version": "2025-10-06",
    "deprecationDate": {
      "inference": "2027-04-06T00:00:00Z"
    },
    "raw": {
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
    }
  },
  {
    "version": "2025-12-15",
    "deprecationDate": {
      "inference": "2026-12-15T00:00:00Z"
    },
    "raw": {
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
    }
  },
  {
    "version": "2025-10-06",
    "deprecationDate": {
      "inference": "2027-04-06T00:00:00Z"
    },
    "raw": {
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
    }
  },
  {
    "version": "2025-12-15",
    "deprecationDate": {
      "inference": "2026-12-15T00:00:00Z"
    },
    "raw": {
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
    }
  }
]
```

## R-05 — live Toronto-area area-code inventory

Query: locality=Toronto, administrativeDivision=ON, phoneNumberType=geographic,
assignmentType=application, api-version=2025-06-01
```json
{"error":{"code":"NotFound","message":"No area codes were found for the given parameters"}}
```

All Canada-wide geographic localities in ACS's inventory (unfiltered, maxPageSize=100):
```json
{"phoneNumberLocalities":[{"localizedName":"Calgary","administrativeDivision":{"localizedName":"AB","abbreviatedName":"AB"}},{"localizedName":"Brockville","administrativeDivision":{"localizedName":"ON","abbreviatedName":"ON"}},{"localizedName":"North Bay","administrativeDivision":{"localizedName":"ON","abbreviatedName":"ON"}},{"localizedName":"Thunder Bay","administrativeDivision":{"localizedName":"ON","abbreviatedName":"ON"}},{"localizedName":"Chicoutimi","administrativeDivision":{"localizedName":"QC","abbreviatedName":"QC"}},{"localizedName":"Montreal","administrativeDivision":{"localizedName":"QC","abbreviatedName":"QC"}},{"localizedName":"Sherbrooke","administrativeDivision":{"localizedName":"QC","abbreviatedName":"QC"}},{"localizedName":"Thetford Mines","administrativeDivision":{"localizedName":"QC","abbreviatedName":"QC"}},{"localizedName":"Lanigan","administrativeDivision":{"localizedName":"SK","abbreviatedName":"SK"}}],"nextLink":null}
```

## R-01 — Models API deprecation-date check

Queried 2026-08-21T21:49:09Z against location=canadacentral.
```json
[
  {
    "version": "2025-10-06",
    "deprecationDate": {
      "inference": "2027-04-06T00:00:00Z"
    },
    "raw": {
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
    }
  },
  {
    "version": "2025-12-15",
    "deprecationDate": {
      "inference": "2026-12-15T00:00:00Z"
    },
    "raw": {
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
    }
  },
  {
    "version": "2025-10-06",
    "deprecationDate": {
      "inference": "2027-04-06T00:00:00Z"
    },
    "raw": {
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
    }
  },
  {
    "version": "2025-12-15",
    "deprecationDate": {
      "inference": "2026-12-15T00:00:00Z"
    },
    "raw": {
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
    }
  }
]
```

## R-05 — live Toronto-area area-code inventory

Query: locality=Toronto, administrativeDivision=ON, phoneNumberType=geographic,
assignmentType=application, api-version=2025-06-01
```json
{"error":{"code":"NotFound","message":"No area codes were found for the given parameters"}}
```

All Canada-wide geographic localities in ACS's inventory (unfiltered, maxPageSize=100):
```json
{"phoneNumberLocalities":[{"localizedName":"Calgary","administrativeDivision":{"localizedName":"AB","abbreviatedName":"AB"}},{"localizedName":"Brockville","administrativeDivision":{"localizedName":"ON","abbreviatedName":"ON"}},{"localizedName":"North Bay","administrativeDivision":{"localizedName":"ON","abbreviatedName":"ON"}},{"localizedName":"Thunder Bay","administrativeDivision":{"localizedName":"ON","abbreviatedName":"ON"}},{"localizedName":"Chicoutimi","administrativeDivision":{"localizedName":"QC","abbreviatedName":"QC"}},{"localizedName":"Montreal","administrativeDivision":{"localizedName":"QC","abbreviatedName":"QC"}},{"localizedName":"Sherbrooke","administrativeDivision":{"localizedName":"QC","abbreviatedName":"QC"}},{"localizedName":"Thetford Mines","administrativeDivision":{"localizedName":"QC","abbreviatedName":"QC"}},{"localizedName":"Lanigan","administrativeDivision":{"localizedName":"SK","abbreviatedName":"SK"}}],"nextLink":null}
```

## R-01 — Models API deprecation-date check

Queried 2026-08-21T22:47:45Z against location=canadacentral.
```json
[
  {
    "version": "2025-10-06",
    "deprecationDate": {
      "inference": "2027-04-06T00:00:00Z"
    },
    "raw": {
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
    }
  },
  {
    "version": "2025-12-15",
    "deprecationDate": {
      "inference": "2026-12-15T00:00:00Z"
    },
    "raw": {
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
    }
  },
  {
    "version": "2025-10-06",
    "deprecationDate": {
      "inference": "2027-04-06T00:00:00Z"
    },
    "raw": {
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
    }
  },
  {
    "version": "2025-12-15",
    "deprecationDate": {
      "inference": "2026-12-15T00:00:00Z"
    },
    "raw": {
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
    }
  }
]
```

## R-05 — live Toronto-area area-code inventory

Query: locality=Toronto, administrativeDivision=ON, phoneNumberType=geographic,
assignmentType=application, api-version=2025-06-01
```json
{"error":{"code":"NotFound","message":"No area codes were found for the given parameters"}}
```

All Canada-wide geographic localities in ACS's inventory (unfiltered, maxPageSize=100):
```json
{"phoneNumberLocalities":[{"localizedName":"Brockville","administrativeDivision":{"localizedName":"ON","abbreviatedName":"ON"}},{"localizedName":"North Bay","administrativeDivision":{"localizedName":"ON","abbreviatedName":"ON"}},{"localizedName":"Thunder Bay","administrativeDivision":{"localizedName":"ON","abbreviatedName":"ON"}},{"localizedName":"Chicoutimi","administrativeDivision":{"localizedName":"QC","abbreviatedName":"QC"}},{"localizedName":"Montreal","administrativeDivision":{"localizedName":"QC","abbreviatedName":"QC"}},{"localizedName":"Sherbrooke","administrativeDivision":{"localizedName":"QC","abbreviatedName":"QC"}},{"localizedName":"Thetford Mines","administrativeDivision":{"localizedName":"QC","abbreviatedName":"QC"}},{"localizedName":"Lanigan","administrativeDivision":{"localizedName":"SK","abbreviatedName":"SK"}}],"nextLink":null}
```


## 02-test-calls.sh Stage 4 — `--tail 500` always failed, silently, all session

The 3 real test calls placed 2026-08-21 (~22:51–22:53 UTC) all worked — first ring, clear echo,
DTMF registered. `02-test-calls.sh` still exited 0 and printed "wait 24 hours" as if nothing had
been recorded, and `PROVISION_TIME` (moved to this script in the previous fix, gated on a
confirmed `CallConnected` event) was never written.

Root cause, verified live: Stage 4 called `az containerapp logs show --tail 500`. The CLI hard-caps
`--tail` at 300:

```
$ az containerapp logs show --name ca-azbank-echo-p0 --resource-group rg-azure-banking-voice-agentic-ai --type console --tail 500
ERROR: --tail must be between 0 and 300.
```

The old code was `LOGS=$(az containerapp logs show ... --tail 500 2>/dev/null || echo "")` — the
`2>/dev/null` discarded that error, and `|| echo ""` produced `LOGS=""` on any failure. This is not
a flush-timing race (the first hypothesis, based on the script's own "may need a moment to flush"
message) — it is a hardcoded, deterministic bug that has **never once succeeded**, on any run, this
entire session. Confirmed by absence: no `## R-02 / R-03 / RTT` section exists anywhere in this
file prior to this entry, meaning the evidence-extraction `else` branch (and the `CallConnected`
gate inside it) had literally never executed.

**Fixed**: `--tail 300` (the real max). The command's exit code is now captured explicitly and
distinguished from "succeeded but genuinely empty" — both cases `exit 1` with a message identifying
which, rather than the old warn-and-continue that let the script reach `finish` and report success
with nothing gathered and no window opened. Same silent-failure shape as the `on_error` empty-table
ambiguity Marco flagged separately — fixed here where it was live and had already cost real time.

Also caught and fixed while touching this code: every message in this block (both the new ones and
the `CallConnected` gate committed earlier tonight) called `err()`, which `02-test-calls.sh` —
unlike `01-provision.sh` — never defines. Under `set -u` this would have failed with "command not
found" at exactly the moment a clear failure message mattered most. Switched to `warn()`, the
function this file actually has.

## PROVISION_TIME — set manually, not by the normal path

Because of the `--tail` bug above, `02-test-calls.sh`'s `CallConnected` gate never got the chance
to fire against real, successful evidence. `PROVISION_TIME` was set by hand on 2026-08-21, **not**
via `write_env` inside either wizard script, to `2026-08-21T22:49:35Z` — the active Container App
revision's `properties.createdTime` (`az containerapp revision list`), not `CALL1_TIME`
(`22:51:43Z`) and not the time this diagnosis finished.

Reasoning: R-04 measures idle-vs-active *billing*, and on the Consumption plan this app bills from
the moment its replica exists, not from the moment someone first dials it. The ~2m16s between the
container's `createdTime` and `CALL1_TIME` is itself idle-billing time and belongs inside the
measurement window — anchoring to `CALL1_TIME` instead would exclude it and understate the window
relative to the resource's actual billed lifetime (the same failure mode the original
`01-provision.sh` Stage-1 comment already flagged for writing `PROVISION_TIME` too early, mirrored
here in the other direction). `systemData.createdAt` on the Container App resource itself reads
`2026-08-21T22:49:27Z`, 8 seconds earlier than the revision's `createdTime` — immaterial at 72h
scale; the revision timestamp was used as the more direct proxy for when compute was actually
scheduled and started billing.

Recorded here so it's unambiguous later: this value did **not** come from either script's guard
logic. If R-04's teardown math ever looks off by a few minutes against what `02-test-calls.sh`
would have produced on its own, this is why.

## R-03 — DTMF evidence from the 3 real calls: confirmed by 2 of 3, one unexplained miss on call 1

From the captured log (`docs/phase0/evidence/containerapp-logs-2026-08-21T2303Z-3-test-calls.txt`):

| Call | WS open→close | frames | dtmf_tones |
|---|---|---|---|
| 1 | 22:51:13.426 → 22:51:37.860 (~24s) | 1218 | **0** |
| 2 | 22:51:52.921 → 22:52:25.767 (~33s) | 1641 | **6** |
| 3 | 22:52:50.514 → 22:53:57.344 (~67s) | 3341 | **6** |

Marco pressed DTMF keys on all three calls. An earlier version of this entry reasoned that Call 3
(not explicitly prompted by the script) registering 6/6 tones was evidence the app captures DTMF
reliably "even unprompted," and used that to wave off Call 1's zero as probably a prompting
artifact. **That reasoning was wrong and has been corrected here.** If only Call 2 was scripted,
then Calls 1 *and* 3 were equally unprompted — one got 6, the other got 0. That's an inconsistency
between two calls in the same condition, not a pattern explained by prompting. Caught by Marco, not
found independently.

**R-03 is confirmed by Calls 2 and 3** — 6/6 tones registered on two independent calls,
per-digit timestamps landing cleanly mid-stream (e.g. call 2's digit #1 at t=10.226s into a
~33s-total call, frame_count=511 at that point — squarely mid-call, not at the edges).

**Call 1's zero is a real, unexplained gap — not reasoned away.** Full log block for Call 1
(`IncomingCall` 22:51:12.212 → `WS closed` 22:51:37.861) shows: `CallConnected` at 22:51:13.864,
1218 frames echoed steadily at ~1/sec for the full ~24s duration, `MediaStreamingStopped` then `WS
closed frames=1218 dtmf_tones=0` — **zero `DtmfData` websocket messages arrived at any point**.
Nothing in the log distinguishes Call 1's shape from Calls 2/3: it's shorter (24s vs. 33s/67s) but
not short — comparable to Call 2's DTMF press landing at t=10s into a similarly-lengthed call, so
there was ample active-streaming window for a mid-call press to land, same as the other two. No
technical factor in the captured evidence (timing, frame count, event ordering) explains why DTMF
didn't arrive on Call 1 specifically. Two explanations remain open and neither can be ruled in or
out from the app's own logs: DTMF wasn't actually sent during that call, or it was sent but not
recognized upstream (ACS's telephony-layer tone recognition happens before the app's WS callback
ever fires, so a tone pressed but not decoded upstream is indistinguishable, from inside this app,
from a tone never sent). Recorded as an open gap, not resolved, not smoothed over.

**Separate bug found while investigating this**: `02-test-calls.sh`'s `DTMF_LINES` extraction
(`grep -i "DTMF tone="`) never matches anything the app actually logs. The real per-digit evidence
line is `"DTMF digit #%d arrived DURING streaming t=...s since stream start ... — R-03 evidence"`
(`docs/echo-app/app.py:149`); `"DTMF tone="` only appears in the B2-gated raw-value line (off by
default). Confirmed against the capture file: 12 real DTMF lines present, zero matches for the
script's pattern. This means the automated R-02/R-03 findings.md write has been reporting
`R03_RESULT="UNCONFIRMED THIS RUN"` every single run regardless of what actually happened on the
call — a second silent-failure bug in the same evidence path as the `--tail 500` one above, caught
in the same pass. Fixed alongside the DTMF-prompt-on-all-3-calls fix below.

## Log delivery — still zero rows after a full lifecycle, diagnostic setting confirmed attached

Re-checked after the container's full lifecycle (create → healthz → 3 real answered calls) with
the diagnostic setting from the previous fix in place the entire time:

```
ContainerAppConsoleLogs | count  →  0 rows
ContainerAppSystemLogs  | count  →  0 rows
```

Confirmed this is not a configuration mistake on this project's end — both the native path and the
explicit fallback are correctly wired:

- `az containerapp env show ... --query properties.appLogsConfiguration` → `destination:
  "log-analytics"`, `customerId` matching the correct (non-orphaned) workspace.
- `az monitor diagnostic-settings list --resource <environment id>` → `azbank-p0-console-logs`
  present, `ContainerAppConsoleLogs` and `ContainerAppSystemLogs` both `enabled: true`, pointed at
  the same correct workspace.

Both delivery paths are configured exactly as documented and neither has delivered a single row,
over an hour after real, confirmed activity (not an idle container — three actual answered calls).
This is now a confirmed platform-level gap, not a "give it more time" situation — genuinely
undiagnosed, not explained by anything found so far.

**Practical consequence for R-04's remaining ~72h**: Log Analytics cannot be relied on for any
evidence during this window. `az containerapp logs show --tail 300` (the CLI's live streaming
buffer, confirmed independent of the Log Analytics pipeline above) is the only working read path,
and it does not retain past ~300 lines — at this app's observed log volume during the 3-call
session (~300 lines in under 4 minutes of active calling), any future burst of real call activity
will scroll past captured evidence within minutes if it isn't pulled promptly. Idle-period volume
(occasional healthz/watchdog `GET / 404` lines) is much lower and likely safe over gaps of hours,
but this hasn't been measured precisely enough to state a safe polling interval with confidence.
