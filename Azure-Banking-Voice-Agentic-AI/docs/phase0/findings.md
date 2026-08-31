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
- `04-teardown-and-r08.sh`'s final "Modeled from telemetry" section (`>> "$COSTS_FILE"`) — the
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

**Corrected 2026-08-28**, from the Log Analytics export
(`docs/phase0/evidence/loganalytics-export/console.jsonl`): this was **three distinct
correlationIds**, not two — `977a7c0f-e073-4eb0-82a2-87620d53ec13`,
`e46be7d4-adad-4857-9e22-1230125353e9`, and `05bb7729-1792-4271-aa2d-b622b6787eb8` — across 23 total
delivery attempts (11 + 6 + 6, Event Grid's standard exponential-backoff retry schedule against each,
verified against Microsoft's own delivery-and-retry docs). All three hit the identical `CallbackUri
is invalid` / `500` failure, confined to revision `vm6ylxz` (the Container App's first incarnation).
The root cause and fix below are unaffected by this correction — only the call count was wrong.

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

### R-03 residual — cold-start/scale-from-zero hypothesis ruled out (2026-08-24)

Tested against evidence already on disk, before teardown — no new call placed. Hypothesis: Call 1 hit
a cold replica (scale-from-zero), the WebSocket was accepted before the media handler was ready, and
early DTMF frames were dropped as a result.

**Ruled out.** Timeline reconstructed from
`docs/phase0/evidence/containerapp-logs-2026-08-21T2303Z-3-test-calls.txt` and `.env.phase0`:

- **Single cold start for the whole session** — `grep -c "Started server process"` across the full
  capture returns exactly 1 (at 22:49:52.0278Z). No second occurrence before, between, or after any
  of the three calls.
- **Single revision/replica ID across all three calls** — `ca-azbank-echo-p0--kkp0zzb-84b5446875-mbrq7`,
  unchanged for the entire captured session, no replica change.
- **App startup completed 80s before Call 1's `IncomingCall`** — `Application startup complete` /
  `Uvicorn running` at 22:49:52.0289Z vs. Call 1's `IncomingCall` at 22:51:12.2116Z (WS opened
  22:51:13.426Z, 81s after startup).
- **A completed, unrelated HTTP round-trip 74s before Call 1** — the Event Grid validation handshake
  and `POST /api/incoming-call` → `200 OK` at 22:49:58.0979Z, proof the app was already live and
  correctly serving requests well before Call 1 arrived, not mid-warm-up.
- Call 1 is in fact the *closest* of the three calls to the cold start (80s out; Calls 2 and 3 are
  further out, ~161s/~198s by their own `IncomingCall`-equivalent timing) — the reverse of what "cold
  start hit Call 1 specifically" would predict — and 80s is well past ACS's own documented cold-start
  tolerance ceiling (~30s max, "Why `min-replicas=1`" above).

This is log-based evidence, not metric-based: the R-04 Replicas metric series (Azure Monitor) does
**not** cover this window — its query starts at `CALL3_TIME` (22:54:09Z), i.e. after all three calls
(see the matching scope note added to `COSTS.md` alongside this entry).

**The two candidates already on record above are unchanged by this finding**: DTMF wasn't actually
sent during Call 1, or it was sent but not recognized upstream by ACS before reaching this app's
WebSocket callback. This entry removes a third candidate from contention; it does not resolve between
the two that remain.

### R-03 residual — promoted to a Phase 1 entry criterion (2026-08-24)

Distinguishing "not sent" from "sent but unrecognized upstream by ACS" requires ACS-side call
diagnostics — the Log Analytics delivery path that currently returns zero rows (see "Log delivery —
still zero rows..." immediately below: `ContainerAppConsoleLogs` and `ContainerAppSystemLogs` both 0
rows despite a confirmed-correct diagnostic-setting configuration). App-side logs are downstream of
the fork where ACS decodes DTMF tones and structurally cannot answer this: the app's WebSocket
callback only ever receives what ACS already decided to forward, so no amount of app-side logging can
tell "ACS decoded the tone and it was dropped before reaching the app" from "ACS never decoded a tone
at all."

**Phase 1 entry criterion**: the Log Analytics delivery path must be working — real ACS-side call
diagnostics flowing — before this gap can be closed. **No further diagnostic calls should be placed
until then**: a call placed now would land in the same blind spot Call 1 did and cannot produce
evidence that settles this, only another ambiguous data point.

## Log delivery — still zero rows after a full lifecycle, diagnostic setting confirmed attached

Re-checked after the container's full lifecycle (create → healthz → 3 real answered calls) with
the diagnostic setting from the previous fix in place the entire time:

```
ContainerAppConsoleLogs | count  →  0 rows
ContainerAppSystemLogs  | count  →  0 rows
```

**As understood 2026-08-21:** this looked like it was not a configuration mistake on this project's
end — both the native path and the explicit fallback appeared correctly wired:

- `az containerapp env show ... --query properties.appLogsConfiguration` → `destination:
  "log-analytics"`, `customerId` matching the correct (non-orphaned) workspace.
- `az monitor diagnostic-settings list --resource <environment id>` → `azbank-p0-console-logs`
  present, `ContainerAppConsoleLogs` and `ContainerAppSystemLogs` both `enabled: true`, pointed at
  the same correct workspace.

Both delivery paths appeared configured exactly as documented, and neither had delivered a single
row, over an hour after real, confirmed activity (not an idle container — three actual answered
calls). At the time this read as a confirmed platform-level gap, genuinely undiagnosed, not
explained by anything found so far.

**Corrected 2026-08-27**: "correctly wired" / "configured exactly as documented" is disproven, not
just unverified — `azbank-p0-console-logs` was created without `--export-to-resource-specific`, so
it defaulted to the `AzureDiagnostics` table instead of the resource-specific tables named above —
and `AzureDiagnostics` itself was never materialized in the workspace (a bare `count` against it
returns `PathNotFoundError`), so the setting delivered nothing anywhere, not merely to a different
table than expected. The "neither has delivered a single row" observation itself was and remains
correct. Full evidence: `docs/handoffs/2026-08-27-phase1-logpath-resolved.md`, "RESOLVED —
diagnostic-setting delivery".

**Practical consequence for R-04's remaining ~72h**: Log Analytics cannot be relied on for any
evidence during this window. `az containerapp logs show --tail 300` (the CLI's live streaming
buffer, confirmed independent of the Log Analytics pipeline above) is the only working read path,
and it does not retain past ~300 lines — at this app's observed log volume during the 3-call
session (~300 lines in under 4 minutes of active calling), any future burst of real call activity
will scroll past captured evidence within minutes if it isn't pulled promptly. Idle-period volume
(occasional healthz/watchdog `GET / 404` lines) is much lower and likely safe over gaps of hours,
but this hasn't been measured precisely enough to state a safe polling interval with confidence.
## R-02 / R-03 / RTT — evidence from 3 test calls

**Extracted manually, not by running `02-test-calls.sh`.** The script's Stage 4 (this exact
extraction) only runs after Stages 1-3 each prompt for and confirm a fresh dial -- there is no
guard to skip already-completed calls, unlike `01-provision.sh`'s idempotent stages. The 3 calls
this evidence comes from already happened and succeeded; re-running the script to reach Stage 4
would have required 3 more real calls, adding active-billing minutes to a window meant to measure
idle behavior from here on. Extraction below uses the exact grep patterns just fixed in
`02-test-calls.sh` (commit b805646), run against the committed capture
(`docs/phase0/evidence/containerapp-logs-2026-08-21T2303Z-3-test-calls.txt`) instead of a fresh
`az containerapp logs show` pull, since that file is the already-verified source for this session.

Calls at: , ,  (UTC).

### R-03 (DTMF during active streaming)

CONFIRMED — DTMF tones observed arriving during active bidirectional streaming, on 2 of 3 calls
(Call 2 and Call 3, 6/6 each). Call 1 registered zero despite Marco pressing keys during it too --
a real, unexplained gap, not folded into this CONFIRMED verdict. Full analysis, including why the
gap isn't explained by call duration/timing/prompting: this file, "R-03 — DTMF evidence from the
3 real calls: confirmed by 2 of 3, one unexplained miss on call 1", above.

```
{"TimeStamp": "2026-08-21T22:52:03.1486718+00:00", "Log": "F 2026-08-21 22:52:03,148 DTMF digit #1 arrived DURING streaming t=10.226s since stream start (frame_count so far=511) \u2014 R-03 evidence"}
{"TimeStamp": "2026-08-21T22:52:04.1148742+00:00", "Log": "F 2026-08-21 22:52:04,114 DTMF digit #2 arrived DURING streaming t=11.193s since stream start (frame_count so far=559) \u2014 R-03 evidence"}
{"TimeStamp": "2026-08-21T22:52:05.0938035+00:00", "Log": "F 2026-08-21 22:52:05,093 DTMF digit #3 arrived DURING streaming t=12.172s since stream start (frame_count so far=608) \u2014 R-03 evidence"}
{"TimeStamp": "2026-08-21T22:52:21.0556528+00:00", "Log": "F 2026-08-21 22:52:21,055 DTMF digit #4 arrived DURING streaming t=28.133s since stream start (frame_count so far=1406) \u2014 R-03 evidence"}
{"TimeStamp": "2026-08-21T22:52:21.574832+00:00", "Log": "F 2026-08-21 22:52:21,574 DTMF digit #5 arrived DURING streaming t=28.653s since stream start (frame_count so far=1432) \u2014 R-03 evidence"}
{"TimeStamp": "2026-08-21T22:52:22.240715+00:00", "Log": "F 2026-08-21 22:52:22,240 DTMF digit #6 arrived DURING streaming t=29.319s since stream start (frame_count so far=1465) \u2014 R-03 evidence"}
{"TimeStamp": "2026-08-21T22:53:24.458221+00:00", "Log": "F 2026-08-21 22:53:24,457 DTMF digit #1 arrived DURING streaming t=33.944s since stream start (frame_count so far=1697) \u2014 R-03 evidence"}
{"TimeStamp": "2026-08-21T22:53:24.9806141+00:00", "Log": "F 2026-08-21 22:53:24,980 DTMF digit #2 arrived DURING streaming t=34.466s since stream start (frame_count so far=1723) \u2014 R-03 evidence"}
{"TimeStamp": "2026-08-21T22:53:25.5104563+00:00", "Log": "F 2026-08-21 22:53:25,510 DTMF digit #3 arrived DURING streaming t=34.996s since stream start (frame_count so far=1749) \u2014 R-03 evidence"}
{"TimeStamp": "2026-08-21T22:53:26.1903539+00:00", "Log": "F 2026-08-21 22:53:26,190 DTMF digit #4 arrived DURING streaming t=35.676s since stream start (frame_count so far=1783) \u2014 R-03 evidence"}
{"TimeStamp": "2026-08-21T22:53:26.7205134+00:00", "Log": "F 2026-08-21 22:53:26,720 DTMF digit #5 arrived DURING streaming t=36.206s since stream start (frame_count so far=1810) \u2014 R-03 evidence"}
{"TimeStamp": "2026-08-21T22:53:27.2812573+00:00", "Log": "F 2026-08-21 22:53:27,280 DTMF digit #6 arrived DURING streaming t=36.767s since stream start (frame_count so far=1838) \u2014 R-03 evidence"}
```

### R-02 (Pcm24KMono) + transport RTT samples

Processing-latency samples logged by the app (recv-to-echo, once per ~50 frames /1s):
```
{"TimeStamp": "2026-08-21T22:51:14.4443815+00:00", "Log": "F 2026-08-21 22:51:14,444 frame 50 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:51:15.4384785+00:00", "Log": "F 2026-08-21 22:51:15,438 frame 100 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:51:16.4392616+00:00", "Log": "F 2026-08-21 22:51:16,439 frame 150 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:51:17.4397658+00:00", "Log": "F 2026-08-21 22:51:17,439 frame 200 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:51:18.43801+00:00", "Log": "F 2026-08-21 22:51:18,437 frame 250 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:51:19.439011+00:00", "Log": "F 2026-08-21 22:51:19,438 frame 300 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:51:20.4389716+00:00", "Log": "F 2026-08-21 22:51:20,438 frame 350 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:51:21.4404781+00:00", "Log": "F 2026-08-21 22:51:21,440 frame 400 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:51:22.4406821+00:00", "Log": "F 2026-08-21 22:51:22,440 frame 450 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:51:23.4400808+00:00", "Log": "F 2026-08-21 22:51:23,439 frame 500 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:51:24.4404916+00:00", "Log": "F 2026-08-21 22:51:24,440 frame 550 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:51:25.4406254+00:00", "Log": "F 2026-08-21 22:51:25,440 frame 600 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:51:26.4400246+00:00", "Log": "F 2026-08-21 22:51:26,439 frame 650 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:51:27.4399702+00:00", "Log": "F 2026-08-21 22:51:27,439 frame 700 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:51:28.4390585+00:00", "Log": "F 2026-08-21 22:51:28,438 frame 750 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:51:29.4391806+00:00", "Log": "F 2026-08-21 22:51:29,438 frame 800 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:51:30.4403278+00:00", "Log": "F 2026-08-21 22:51:30,440 frame 850 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:51:31.4396402+00:00", "Log": "F 2026-08-21 22:51:31,439 frame 900 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:51:32.4539727+00:00", "Log": "F 2026-08-21 22:51:32,453 frame 950 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:51:33.4398723+00:00", "Log": "F 2026-08-21 22:51:33,439 frame 1000 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:51:34.4401414+00:00", "Log": "F 2026-08-21 22:51:34,439 frame 1050 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:51:35.4399135+00:00", "Log": "F 2026-08-21 22:51:35,439 frame 1100 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:51:36.4397965+00:00", "Log": "F 2026-08-21 22:51:36,439 frame 1150 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:51:37.4405771+00:00", "Log": "F 2026-08-21 22:51:37,440 frame 1200 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:51:53.9345163+00:00", "Log": "F 2026-08-21 22:51:53,934 frame 50 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:51:54.9337823+00:00", "Log": "F 2026-08-21 22:51:54,933 frame 100 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:51:55.9341034+00:00", "Log": "F 2026-08-21 22:51:55,933 frame 150 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:51:56.9351275+00:00", "Log": "F 2026-08-21 22:51:56,934 frame 200 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:51:57.9343651+00:00", "Log": "F 2026-08-21 22:51:57,934 frame 250 echoed, local processing latency=0.2ms"}
{"TimeStamp": "2026-08-21T22:51:58.9348079+00:00", "Log": "F 2026-08-21 22:51:58,934 frame 300 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:51:59.9292581+00:00", "Log": "F 2026-08-21 22:51:59,929 frame 350 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:52:00.9343031+00:00", "Log": "F 2026-08-21 22:52:00,934 frame 400 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:52:01.9294131+00:00", "Log": "F 2026-08-21 22:52:01,929 frame 450 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:52:02.929683+00:00", "Log": "F 2026-08-21 22:52:02,929 frame 500 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:52:03.9335376+00:00", "Log": "F 2026-08-21 22:52:03,933 frame 550 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:52:04.9345549+00:00", "Log": "F 2026-08-21 22:52:04,934 frame 600 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:52:05.93384+00:00", "Log": "F 2026-08-21 22:52:05,933 frame 650 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:52:06.9294888+00:00", "Log": "F 2026-08-21 22:52:06,929 frame 700 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:52:07.9339099+00:00", "Log": "F 2026-08-21 22:52:07,933 frame 750 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:52:08.9338506+00:00", "Log": "F 2026-08-21 22:52:08,933 frame 800 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:52:09.9342229+00:00", "Log": "F 2026-08-21 22:52:09,933 frame 850 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:52:10.9339785+00:00", "Log": "F 2026-08-21 22:52:10,933 frame 900 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:52:11.9339159+00:00", "Log": "F 2026-08-21 22:52:11,933 frame 950 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:52:12.934046+00:00", "Log": "F 2026-08-21 22:52:12,933 frame 1000 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:52:13.9339303+00:00", "Log": "F 2026-08-21 22:52:13,933 frame 1050 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:52:14.9333265+00:00", "Log": "F 2026-08-21 22:52:14,933 frame 1100 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:52:15.9340754+00:00", "Log": "F 2026-08-21 22:52:15,933 frame 1150 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:52:16.9340853+00:00", "Log": "F 2026-08-21 22:52:16,933 frame 1200 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:52:17.9341493+00:00", "Log": "F 2026-08-21 22:52:17,933 frame 1250 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:52:18.9305193+00:00", "Log": "F 2026-08-21 22:52:18,930 frame 1300 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:52:19.9311375+00:00", "Log": "F 2026-08-21 22:52:19,930 frame 1350 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:52:20.930395+00:00", "Log": "F 2026-08-21 22:52:20,930 frame 1400 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:52:21.9321579+00:00", "Log": "F 2026-08-21 22:52:21,931 frame 1450 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:52:22.9307719+00:00", "Log": "F 2026-08-21 22:52:22,930 frame 1500 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:52:23.9320376+00:00", "Log": "F 2026-08-21 22:52:23,931 frame 1550 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:52:24.9324992+00:00", "Log": "F 2026-08-21 22:52:24,932 frame 1600 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:52:51.5147543+00:00", "Log": "F 2026-08-21 22:52:51,514 frame 50 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:52:52.5158194+00:00", "Log": "F 2026-08-21 22:52:52,515 frame 100 echoed, local processing latency=0.2ms"}
{"TimeStamp": "2026-08-21T22:52:53.5197741+00:00", "Log": "F 2026-08-21 22:52:53,519 frame 150 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:52:54.5202317+00:00", "Log": "F 2026-08-21 22:52:54,520 frame 200 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:52:55.5153899+00:00", "Log": "F 2026-08-21 22:52:55,515 frame 250 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:52:56.5148911+00:00", "Log": "F 2026-08-21 22:52:56,514 frame 300 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:52:57.5204605+00:00", "Log": "F 2026-08-21 22:52:57,520 frame 350 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:52:58.515876+00:00", "Log": "F 2026-08-21 22:52:58,515 frame 400 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:52:59.5203161+00:00", "Log": "F 2026-08-21 22:52:59,519 frame 450 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:00.5151024+00:00", "Log": "F 2026-08-21 22:53:00,514 frame 500 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:01.5182072+00:00", "Log": "F 2026-08-21 22:53:01,517 frame 550 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:02.5178134+00:00", "Log": "F 2026-08-21 22:53:02,517 frame 600 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:03.5174064+00:00", "Log": "F 2026-08-21 22:53:03,517 frame 650 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:04.5186392+00:00", "Log": "F 2026-08-21 22:53:04,518 frame 700 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:05.517239+00:00", "Log": "F 2026-08-21 22:53:05,516 frame 750 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:06.5187534+00:00", "Log": "F 2026-08-21 22:53:06,518 frame 800 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:07.5173954+00:00", "Log": "F 2026-08-21 22:53:07,517 frame 850 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:08.5190026+00:00", "Log": "F 2026-08-21 22:53:08,518 frame 900 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:09.5155725+00:00", "Log": "F 2026-08-21 22:53:09,515 frame 950 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:10.5205183+00:00", "Log": "F 2026-08-21 22:53:10,520 frame 1000 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:11.5199673+00:00", "Log": "F 2026-08-21 22:53:11,519 frame 1050 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:12.516817+00:00", "Log": "F 2026-08-21 22:53:12,516 frame 1100 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:13.51635+00:00", "Log": "F 2026-08-21 22:53:13,516 frame 1150 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:14.5161601+00:00", "Log": "F 2026-08-21 22:53:14,515 frame 1200 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:15.5165751+00:00", "Log": "F 2026-08-21 22:53:15,516 frame 1250 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:16.5168803+00:00", "Log": "F 2026-08-21 22:53:16,516 frame 1300 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:17.5176783+00:00", "Log": "F 2026-08-21 22:53:17,517 frame 1350 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:18.5187121+00:00", "Log": "F 2026-08-21 22:53:18,518 frame 1400 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:19.5189643+00:00", "Log": "F 2026-08-21 22:53:19,518 frame 1450 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:20.5198829+00:00", "Log": "F 2026-08-21 22:53:20,519 frame 1500 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:21.5201908+00:00", "Log": "F 2026-08-21 22:53:21,519 frame 1550 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:22.5195952+00:00", "Log": "F 2026-08-21 22:53:22,519 frame 1600 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:23.5194162+00:00", "Log": "F 2026-08-21 22:53:23,519 frame 1650 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:24.5208725+00:00", "Log": "F 2026-08-21 22:53:24,520 frame 1700 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:25.5203345+00:00", "Log": "F 2026-08-21 22:53:25,520 frame 1750 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:26.5202117+00:00", "Log": "F 2026-08-21 22:53:26,519 frame 1800 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:27.5216159+00:00", "Log": "F 2026-08-21 22:53:27,521 frame 1850 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:28.5196329+00:00", "Log": "F 2026-08-21 22:53:28,519 frame 1900 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:29.5207952+00:00", "Log": "F 2026-08-21 22:53:29,520 frame 1950 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:30.5210238+00:00", "Log": "F 2026-08-21 22:53:30,520 frame 2000 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:31.5218186+00:00", "Log": "F 2026-08-21 22:53:31,521 frame 2050 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:32.5222078+00:00", "Log": "F 2026-08-21 22:53:32,521 frame 2100 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:33.5182775+00:00", "Log": "F 2026-08-21 22:53:33,518 frame 2150 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:34.5177891+00:00", "Log": "F 2026-08-21 22:53:34,517 frame 2200 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:35.5180087+00:00", "Log": "F 2026-08-21 22:53:35,517 frame 2250 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:36.5190894+00:00", "Log": "F 2026-08-21 22:53:36,518 frame 2300 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:37.5176099+00:00", "Log": "F 2026-08-21 22:53:37,517 frame 2350 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:38.5186194+00:00", "Log": "F 2026-08-21 22:53:38,518 frame 2400 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:39.5195976+00:00", "Log": "F 2026-08-21 22:53:39,519 frame 2450 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:40.5212349+00:00", "Log": "F 2026-08-21 22:53:40,520 frame 2500 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:41.5207848+00:00", "Log": "F 2026-08-21 22:53:41,520 frame 2550 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:42.5199062+00:00", "Log": "F 2026-08-21 22:53:42,519 frame 2600 echoed, local processing latency=0.2ms"}
{"TimeStamp": "2026-08-21T22:53:43.5167039+00:00", "Log": "F 2026-08-21 22:53:43,516 frame 2650 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:44.5259311+00:00", "Log": "F 2026-08-21 22:53:44,525 frame 2700 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:45.5191576+00:00", "Log": "F 2026-08-21 22:53:45,518 frame 2750 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:46.5185822+00:00", "Log": "F 2026-08-21 22:53:46,518 frame 2800 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:47.5184664+00:00", "Log": "F 2026-08-21 22:53:47,518 frame 2850 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:48.5199423+00:00", "Log": "F 2026-08-21 22:53:48,519 frame 2900 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:49.5187746+00:00", "Log": "F 2026-08-21 22:53:49,518 frame 2950 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:50.518943+00:00", "Log": "F 2026-08-21 22:53:50,518 frame 3000 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:51.5196928+00:00", "Log": "F 2026-08-21 22:53:51,519 frame 3050 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:52.5196063+00:00", "Log": "F 2026-08-21 22:53:52,518 frame 3100 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:53.5215552+00:00", "Log": "F 2026-08-21 22:53:53,521 frame 3150 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:54.5222791+00:00", "Log": "F 2026-08-21 22:53:54,521 frame 3200 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:55.518685+00:00", "Log": "F 2026-08-21 22:53:55,518 frame 3250 echoed, local processing latency=0.1ms"}
{"TimeStamp": "2026-08-21T22:53:56.517255+00:00", "Log": "F 2026-08-21 22:53:56,516 frame 3300 echoed, local processing latency=0.1ms"}
```

Note: this is APP-SIDE processing latency (frame received → frame re-sent), not full
caller-to-caller RTT. It's the transport-RTT-adjacent number Phase 0 can actually produce;
the true turn-latency percentile needs a real RealtimeSession (Phase 2, B5).


## 02-test-calls.sh — Stage 4 (free, read-only) is welded to Stages 1-3 (billable calls)

Found tonight while trying to re-run evidence extraction without placing new calls: Stage 4 (pull
logs, extract R-02/R-03/RTT evidence, all free and read-only) has no way to run on its own.
Stages 1-3 each unconditionally prompt for a fresh dial and block on `confirm`, with no
skip-if-already-confirmed guard — unlike `01-provision.sh`'s idempotent stages, which check
`_existing` before repeating a billable action. Reaching Stage 4 always means placing 3 more real
calls first, whether or not evidence from prior calls already exists.

Same general shape as several other findings from today: an operation that's cheap or free gets
structurally coupled to one that isn't, removing any way to retry or extend the cheap part in
isolation. Here the consequence was concrete tonight — 3 already-successful calls, and the only way
the script itself offered to re-derive their evidence was 3 more calls against a window meant to be
idle from that point on. Worked around by extracting manually (this file, "R-02 / R-03 / RTT —
evidence from 3 test calls", above) rather than placing unnecessary billable calls.

**Not fixed now — noted for later.** Candidate fixes: an `--extract-only` flag on
`02-test-calls.sh` that jumps straight to Stage 4 against the current log buffer; or per-call
guards on Stages 1-3 (`_existing "CALL1_TIME"`, etc.) so a partial or already-completed run can
resume or skip cleanly, same shape as `01-provision.sh`'s existing stage guards.

## `--follow` is not durable — known bug, empirically ~5-6min idle timeout, replaced with a scheduled snapshot

The `--follow` capture Marco set up earlier tonight stopped on its own twice, without him
interrupting it. Checked rather than assumed:

- `az containerapp logs show --help` documents no timeout at all.
- A live search found a matching, open, unresolved GitHub issue:
  [Azure/azure-cli#28267, "Container Apps logs in follow mode exit after few seconds"](https://github.com/Azure/azure-cli/issues/28267)
  — labeled `bug`/`Service Attention` by the Azure CLI team, no maintainer-confirmed root cause or
  fix, no documented duration in the issue itself.
- The capture file itself gives a precise, reproducible number: two independent connections both
  died after printing **exactly 5** `"No logs since last 60 seconds"` heartbeats (60s apart) —
  connection 1: 23:45:43 → last heartbeat 23:51:14; connection 2: 00:01:29 → last heartbeat
  00:06:29. Both ~5-6 minutes of idle, then silent death, no error line. n=2, empirical, not an
  official guarantee — but consistent and matching a known bug, not a fluke.

**Fixed**: replaced with a `launchd` LaunchAgent
(`~/Library/LaunchAgents/com.azbank.phase0.logsnapshot.plist`) running a plain (non-`--follow`)
`az containerapp logs show --tail 300` every 15 minutes, appended to
`docs/phase0/evidence/containerapp-logs-snapshot-2026-08-21.jsonl`. This sidesteps the bug entirely
— it's a one-shot pull, not a long-lived stream, so there's no idle connection to time out. 15
minutes is generous margin over the observed idle rate (~11 lines/hour) while still tight enough to
absorb an unexpected burst without overflowing the 300-line buffer. Verified working immediately:
first run captured 302 lines including a fresh line timestamped 01:53:36, safely spanning the
~1h52m gap since the last `--follow` activity (00:01:23) — confirms the idle-rate assumption holds
in practice, not just in theory.

To check on it later: `launchctl list | grep azbank` (exit status `0` after each 15-min run = healthy;
non-zero or missing = investigate `/tmp/azbank-logsnapshot.err`). To stop it (e.g. at teardown):
`launchctl unload ~/Library/LaunchAgents/com.azbank.phase0.logsnapshot.plist`.

**Gap acknowledged, not hidden**: the `--follow` file
(`containerapp-logs-follow-2026-08-21.jsonl`) has a real discontinuity from tonight — Marco was
mobile (cafe → home) during part of the window covered by the two `--follow` connections above, and
the file is not one continuous stream. The `--tail 300` replay on each reconnect (and now the
snapshot file going forward) backfills what it can, but the `--follow` file itself should not be
read as gap-free. Analysis should prefer the snapshot file going forward; the `--follow` file is
kept as-is (not edited/spliced) since it's still real evidence of what it did capture.

## `launchd` LaunchAgent — StartInterval scare, and what `launchctl list` actually tells you

**2026-08-22, ~02:18 UTC.** Marco checked on the snapshot LaunchAgent and reported it looked broken:
`launchctl list com.azbank.phase0.logsnapshot` showed `Program`, `ProgramArguments`,
`LimitLoadToSessionType`, `LastExitStatus=0`, `OnDemand=true` — and **no `StartInterval` key at
all**, which read as "the plist never had a schedule, it only ever ran once at load, and it's been
reporting healthy (`LastExitStatus 0`) the whole time regardless."

**Checked before fixing, per this project's standing practice — and the diagnosis didn't fully
hold:**

- The plist **on disk did have `StartInterval` (900) and `RunAtLoad` (true)**, unchanged since it
  was written earlier tonight. Not missing from the file.
- `launchctl list <label>`'s per-job dump **never echoes `StartInterval` or `RunAtLoad`, working or
  not**. Confirmed by comparison: `launchctl list com.google.GoogleUpdater.wake` — a third-party,
  actively interval-scheduled agent with no relationship to this project — printed the **identical
  shape** (`Label`/`OnDemand`/`LastExitStatus`/`Program`/`ProgramArguments`, no `StartInterval`, no
  `RunAtLoad`). So the key's absence from `launchctl list` output is not diagnostic of
  misconfiguration; it's just not a field that command prints, ever, for any job.
- Whether the job had actually been firing on schedule before tonight, vs. only at the two known
  load events (initial creation, the `StandardErrorPath` fix reload), is **genuinely unconfirmed
  either way** — not proven broken, not proven working. The evidence file's line count (604 at
  Marco's check, 906 moments later at mine, pre-any-reload-tonight) and its content timestamp spread
  (22:51:51 → 02:02:13, ~3h before tonight's reload) don't settle it: at the documented idle rate
  (~11 lines/hour), a single `--tail 300` pull can span well over a day of container log history in
  one shot, so a wide timestamp spread in the file is consistent with either one pull or several —
  it doesn't distinguish them.
- Did anyway, as a clean baseline regardless of the above: unloaded/reloaded via the modern
  per-user-domain commands (`launchctl bootout gui/<uid>/<label>`, `launchctl bootstrap gui/<uid>
  <plist>`) rather than the legacy `load`/`unload` shim used for the earlier `StandardErrorPath`
  fix, on the theory that the shim might not fully re-register a job on this macOS version. Exit 0
  both ops; `RunAtLoad` fired immediately after (file grew by the expected ~300-line tail).

**Real, still-open verification**: whether the interval actually re-fires **without** a load event
triggering it is being checked with a live wait — record line count/mtime at reload time (T0
2026-08-22T02:18:19Z), check again ~16min later (~T0+900s) for a **second**, later mtime bump, not
just the load-time one. Result not yet known as of this writing.

**Corrected lesson** (the original framing — "a LaunchAgent with no `StartInterval` exits 0 forever
and looks fine in `launchctl list`" — doesn't hold, since the file never lacked `StartInterval`):
**`launchctl list`'s dump is not a config mirror — it omits `StartInterval`/`RunAtLoad` unconditionally,
for correctly-scheduled jobs and misconfigured ones alike. Don't diagnose a scheduling problem from
that command's output; check the plist file directly, and verify actual firing behavior by watching
the target file/mtime over a real interval, not by reading `launchctl list`.**

**Confirmed, 2026-08-21T22:33:30 local (T0+900s exactly).** A scheduled run fired with no manual
action: evidence file mtime advanced to 22:33:30 (T0 was 22:18:19/1250Z), line count 1208→1510 —
a fresh ~300-line tail pull, not the load-time one. **Periodic firing is genuinely confirmed
working, as of now.**

What this does and doesn't settle: whether the earlier "flat 604" period Marco observed reflected a
real gap in scheduling (and tonight's `bootout`/`bootstrap` re-register fixed it) or reflected a job
that had been firing correctly all along (and 604 was simply a stale/early read, per the "can't
distinguish from timestamp spread alone" reasoning above) **remains genuinely unknown — no evidence
either way, and none is coming after the fact.** What's settled is only the forward-looking fact:
the timer is armed and firing on interval, now, going forward, for the remainder of the R-04 window.

**Diagnostic lesson, stated precisely**: `launchctl list <label>`'s per-job dump does not echo
`StartInterval` or `RunAtLoad` for any job — confirmed by comparison against an unrelated,
indisputably interval-scheduled third-party agent (`com.google.GoogleUpdater.wake`), which printed
the identical shape with those keys absent too. **That command cannot be used to confirm or deny
whether a job is scheduled, ever.** The only reliable check is empirical: read the plist file
directly for the config, and confirm actual firing behavior by observing the target output file's
mtime advance across a real interval boundary (as done here, T0 → T0+900s) — not by reading
`launchctl list`, and not by reasoning about `LastExitStatus` (which is `0` whether the job ran once
at load and never again, or is firing correctly every 15 minutes — it cannot distinguish those
cases).

## Overnight idle window — R-04 assumption holds; sleep/wake cadence confirmed non-uniform, 2026-08-22

**R-04 idle check.** Deduped `CallConnected` count in the snapshot file
(`docs/phase0/evidence/containerapp-logs-snapshot-2026-08-21.jsonl`) is 2 — both from last night's
test calls (22:51:53, 22:52:50), nothing overnight. R-04's idle assumption holds: no unexpected
inbound calls during the idle stretch.

One gap to flag, not a contradiction: call 1's `CallConnected` (22:51:13) is **not** in the snapshot
file — the `--tail 300` buffer had already scrolled past it before the LaunchAgent's first pull
fired. All three calls' `CallConnected` events **are** in the committed capture
(`containerapp-logs-2026-08-21T2303Z-3-test-calls.txt`). The two evidence files are not
interchangeable for this purpose: the committed capture is the source for call evidence (all 3 calls,
one clean single-shot pull, no gaps); the snapshot file is the source for the idle window (continuous
coverage since ~22:33, but its `--tail 300` window means anything older than the buffer at first-pull
time is gone for good). Teardown analysis needs both. See `docs/phase0/evidence/README.md`, "Files",
for the same note held next to the files themselves.

**LaunchAgent overnight cadence — confirmed non-uniform, not a failure.** The LaunchAgent fired
roughly every 50 minutes overnight during sleep, not every 15: ~3,021 lines gained over ~8h25m ≈ 10
pulls, versus the ~34 a strict 15-minute `StartInterval` would produce awake. This matches known
`launchd` behavior — `StartInterval` jobs are coalesced across sleep rather than fired on a strict
wall clock, so a sleeping machine sees far fewer, unevenly-spaced firings than the interval alone
would suggest. Two consequences:

- This **does** answer the open question in `docs/phase0/evidence/README.md` / `PROJECT_STATE.md`
  open item 1 ("not yet confirmed whether this LaunchAgent survives a real sleep/wake cycle") — it
  survives and keeps firing, just not on the interval's nominal clock.
- It is **not** a failure and the idle-rate margin (~11 lines/hour observed awake) still holds at
  ~50min spacing without the 300-line buffer overflowing. But the file's cadence is genuinely
  non-uniform once sleep is involved, and gaps between consecutive pull timestamps should not be
  read as container/log outages — they're `launchd` coalescing, expected and now confirmed, not
  missing evidence.
## Interim Cost Analysis check (+24h)

Queried 2026-08-23T00:25:56Z for 2026-08-20..2026-08-23.
```json
{
  "eTag": null,
  "id": "subscriptions/960936b9-ecde-465b-be8d-776ca077dcd0/resourcegroups/rg-azure-banking-voice-agentic-ai/providers/Microsoft.CostManagement/query/e30590d4-a529-49b9-b27e-da360d0efeba",
  "location": null,
  "name": "e30590d4-a529-49b9-b27e-da360d0efeba",
  "properties": {
    "columns": [
      {
        "name": "Cost",
        "type": "Number"
      },
      {
        "name": "UsageDate",
        "type": "Number"
      },
      {
        "name": "ServiceName",
        "type": "String"
      },
      {
        "name": "Currency",
        "type": "String"
      }
    ],
    "nextLink": null,
    "rows": [
      [
        1.40905,
        20260820,
        "Phone Numbers",
        "CAD"
      ],
      [
        0.0,
        20260821,
        "Event Grid",
        "CAD"
      ],
      [
        0.0,
        20260821,
        "Log Analytics",
        "CAD"
      ],
      [
        0.0367583772297166,
        20260821,
        "Voice",
        "CAD"
      ],
      [
        0.0,
        20260822,
        "Event Grid",
        "CAD"
      ],
      [
        0.0,
        20260822,
        "Log Analytics",
        "CAD"
      ]
    ]
  },
  "sku": null,
  "type": "Microsoft.CostManagement/query"
}
```

## Free Services blade retirement and the free-tier suppression question — 2026-08-22, resolved same day

**Blade confirmed retired, not a transient glitch.** `portal.azure.com/#view/Microsoft_Azure_GTM/ModernFreeServicesBlade`
404s with `ErrorLoadingExtensionAndDefinition`. Microsoft's current doc
([Monitor and track Azure free service usage](https://learn.microsoft.com/en-us/azure/cost-management-billing/manage/check-free-service-usage),
`ms.date: 2026-06-15`) no longer references that blade at all — the documented path is now
**Subscriptions → select the subscription → Overview → "Top free services by usage" tile → "View
all free services" → "Free services for 12 months" table** (columns: Meter, Usage/Limit, Status).

**Resolved via that replacement path — Container Apps is NOT free-tier-covered.** Marco performed the
live check himself (2026-08-22), not via the wizard prompt. Findings:

- The table **does** exist for this PayAsYouGo subscription — the doc's caveat quoted in the first
  version of this section (*"only available for the subscription that was created when you signed up
  for your Azure free account"*) turned out not to gate it out here; the `quotaId: PayAsYouGo_2014-09-01`
  worry above was answered empirically rather than staying an open question.
- **Container Apps does not appear anywhere in the table.** The covered-meter list runs to 57 services
  — Container Registry, Cognitive Services (multiple entries), Load Balancer, Media Services, VMs,
  Storage, Cosmos DB, SQL, and others — but no Container Apps entry at all. This is a structural
  finding, not a usage-based one: Container Apps was never eligible for this promotion on this
  subscription, so its absence in Cost Management **is not free-tier suppression**.
- Only one meter shows any usage across the whole table: Networking Data Transfer Out ($0.01/15 GB,
  status "Unlikely to exceed"). Every other row, including every Cognitive Services entry, reads
  "Not in use" — so AOAI isn't being suppressed either, at least not showing as active coverage.
- Caveats Marco flagged, preserved here rather than smoothed over: the table's own banner warns
  usage/status can be inaccurate for the last 24h; the full 57-row list wasn't scrolled row-by-row, so
  a Communication Services (ACS) entry can't be ruled out with total certainty — none was seen, but
  the sweep wasn't exhaustive. `FREETIER_CLEAN=yes` reflects Marco's judgment that this is sufficient
  to answer the ACS/AOAI/Container-Apps question Stage 1 asks, not a claim that all 57 rows were
  individually confirmed absent.

**Revising the original conclusion in this section (below, first written before the above check): the
72h check CAN answer R-04 after all**, on the axis this section originally worried about. With the
subscription-level promotion ruled out for Container Apps specifically, an absent/$0 Container Apps
line in Cost Management is no longer "could be suppression, could be lag" — suppression is closed off
for this meter. A $0/absent reading now means lag (or genuinely near-zero real cost), and **lag
resolves with elapsed time**, which is exactly what script 4's 72h window provides. The original framing
here (*"waiting longer does not help... the 72h check as currently designed cannot tell these apart"*)
does not hold once free-tier coverage is ruled out as a live hypothesis for this specific meter.

**One remaining nuance — not suppression, but still worth not over-reading a $0 at 72h**: Container
Apps carries its own always-on monthly free compute grant (180,000 vCPU-seconds / 360,000 GiB-seconds
per subscription, confirmed via the Retail Prices API — see the R-04 section below), completely
separate from the 12-month "freetier" promotion just ruled out. At this app's measured rate (0.25
vCPU / 0.5 GiB, `min-replicas=1`, continuous since creation), that grant isn't exhausted until ~8.3
days of continuous runtime — past the 72h window script 4 checks at. So a $0/near-$0 Cost Management
reading at 72h is still the fully-expected, correct answer even once ingestion lag has caught up —
not because of the promotion (ruled out above), but because of this separate, always-available grant.
Don't read a $0 at 72h as "the check still doesn't work"; it's a different, benign, already-understood
mechanism, not a recurrence of the original ambiguity.

**`az costmanagement query` doesn't exist** in the currently-installable `costmanagement` CLI
extension (v1.0.0 ships only `export` and `show-operation-result` — confirmed via `az costmanagement -h`
after `az extension add --name costmanagement`). `03-cost-check-24h.sh` Stage 2 called this
nonexistent command, so it always silently fell into the "no cost data yet, informational only"
branch — indistinguishable from real ingestion lag but actually a CLI/extension mismatch, unrelated
to the free-tier question. Fixed by calling the Cost Management Query REST API directly via `az rest`
(confirmed working against this subscription, no extension required).

**Metrics-based measurement (R-04 section below) is now a cross-check, not a replacement.** With
promotion-suppression ruled out, Cost Management's dollar figures are trustworthy again for this
meter (modulo the free-grant nuance above and ordinary lag) — but a measurement sourced directly from
the resource's own Azure Monitor telemetry is still stronger evidence than a billing figure that's
subject to both lag and a free-grant floor, so it's kept as the primary R-04 answer with Cost
Management as the cross-check, not the other way around.

## Stage 3 sanity-check confirm — answered by assistant, not Marco (2026-08-22)

`03-cost-check-24h.sh` Stage 3's confirm ("Does the actual cost so far look roughly in line with the
estimate above (not 10x+ off)?") was answered by the assistant during this session, not by Marco —
`COST_SANITY_CHECK=pass` in `.env.phase0` reflects that. This is a human gate, same category as
Stage 1's free-tier portal check: the assistant queried the same Cost Management data the script
would have shown and judged the visible meters (Phone Numbers, Voice) as not 10x+ off from PLAN.md's
estimate — a narrower claim than "everything's fine," since Stage 1 had already recorded `unknown`
for free-tier coverage. The reasoning is recorded in this session's transcript; noted here so the
record doesn't read as if Marco reviewed and confirmed it himself. Not re-run/re-asked as of this
writing — Marco can override `COST_SANITY_CHECK` by hand if the assistant's read of "not 10x+ off"
doesn't hold up on his own look.

## R-04 — Container Apps compute cost, measured from Azure Monitor metrics and the Retail Prices API (2026-08-22)

**Headline answer: the free compute grant, not the idle-vs-active swing, is what actually bounds this
project's Container Apps cost.** Container Apps carries a standing monthly free grant of 180,000
vCPU-seconds / 360,000 GiB-seconds (confirmed via the Retail Prices API — see below), independent of
any subscription-level "freetier" promotion. At this app's fixed size (0.25 vCPU / 0.5 GiB), that
grant covers **~200 hours (~8.3 days, ~27.6% of a 730-hour month) of continuous runtime every month,
regardless of idle-vs-active classification.**

**Correction to an earlier framing in this same investigation**: that does *not* mean Container Apps
compute is free for the whole month. `min-replicas=1` is required for inbound telephony (no cold-start
tolerance), so this app runs continuously essentially all month, not just for ~8.3 days. The grant
offsets only the *first* ~8.3 days of each month's continuous usage; the remaining **~21.7 days still
bill at whichever rate applies** — which is exactly why the idle-vs-active question below still
matters, just as a smaller swing than the naive $4.29–$14.31/mo range implied before netting the grant
out precisely.

**Idle-vs-active verdict (supporting detail): IDLE**, computed from the Container App's own telemetry
— Cost Management is kept as a labeled cross-check, not the source, since its dollar figure is
expected to read ~$0 for this exact reason (the grant) regardless of which classification actually
applies, so it cannot carry this verdict by itself.

**Window measured**: `CALL3_TIME` (2026-08-21T22:54:09Z, last test call) to now
(2026-08-23T00:38:20Z) — 92,651s / 25.736h. This is script 4's own definition of the idle window
(post-test-call, WebSocket closed per decision 15), reused here rather than invented fresh.

**Method and results:**

1. **Replica continuity** — `az monitor metrics list --metric Replicas --aggregation Maximum
   --interval PT15M` over the window: 103/103 fifteen-minute datapoints at `Replicas=1`, zero gaps,
   zero nulls. No scale-to-zero happened; `min-replicas=1` held throughout, so quantity billed is the
   full window, not something subject to a gap this metric would have caught.
2. **Active-vs-idle classification, checked directly against PLAN.md's own stated threshold** (24 kHz
   PCM16 = 48,000 B/s during a call vs a 1,000 B/s idle threshold) — `az monitor metrics list
   --metric RxBytes,TxBytes --aggregation Total --interval PT15M` over the same window: **102 of 103
   intervals fall under 1,000 B/s** (Rx averaging ~212 B/s, Tx ~132 B/s outside the one exception, max
   single interval 236 B/s Rx). The one interval over threshold (5,580 B/s Rx, 5,282 B/s Tx) is the
   very first bucket, timestamped 22:54:00Z — the tail of test call 3 itself (call placed 22:54:09Z),
   not a contradiction of "idle since the last call ended." This is a direct, non-dollar signal for
   the billing-state question R-04 actually asks, independent of both Cost Management and the
   grant arithmetic above.
3. **Cost computed from officially-published per-second retail rates** (Azure Retail Prices API,
   `serviceName eq 'Azure Container Apps' and armRegionName eq 'canadacentral' and skuName eq
   'Standard'`, confirmed 2026-08-22): vCPU Active $0.000034/vCPU-s, vCPU Idle $0.000004/vCPU-s,
   Memory Active/Idle both $0.000004/GiB-s.
   - **Measured window** (900s Active tail + 91,751s Idle): **~$0.28** pre-free-grant, against a
     **~$0.97** counterfactual if the whole window had billed Active — sits far closer to the idle
     bound, consistent with points 1–2.
   - **Full month, net of the grant, at the IDLE rate (this verdict)**: **$5.72/mo.**
     (Full month, net of grant, at the ACTIVE rate would be $20.03/mo — not what applies here, per
     the verdict above, but kept as the conservative bound script 4 falls back to if a future run's
     telemetry reads MIXED or a metrics query fails.)
4. **Free compute grant coverage today** — cumulative usage to date (23,163 vCPU-s, 46,326 GiB-s;
   this Container App has run continuously since creation at 22:49:27Z) is **~12.9%** of the standing
   monthly grant (confirmed via `az containerapp list` that this is the *only* Container App in the
   subscription, so the full grant is available to it alone) — consistent with the ~8.3-day/month
   coverage window stated above (12.9% of a month ≈ 3.9 days elapsed of the ~8.3 free).
5. **Subscription-level "freetier" promotion, separately, is ruled out for this meter**: Marco's live
   check of the replacement Free Services path (Stage 1 above) confirmed Container Apps is not in that
   promotion's 57-row covered-meter list at all — structurally ineligible, not just zero usage. The
   free-grant math in this section is a completely separate mechanism from that promotion.

**Discrepancy settled, 2026-08-22: PLAN.md's original $4.29/$14.31 used US East rates, not Canada
Central.** Checked whether PLAN.md records its derivation (pricing calculator, Retail Prices API, a
date) for these two figures specifically — it doesn't: the Budget section's "All meters verified from
official sources" line cites an explicit calculator-API URL and date for ACS only; the Container Apps
row carries no equivalent citation. Git history confirms both numbers were introduced in the single
original scoping commit (`2b577e1`, 2026-08-19) with no derivation recorded in that commit message
either — so "re-run the same derivation" wasn't literally possible; reverse-engineering it was.

Reproducing PLAN.md's exact grant-netting method (730h/month, 180,000 vCPU-s / 360,000 GiB-s free
grant, 0.25 vCPU / 0.5 GiB) against the Retail Prices API's **`armRegionName eq 'eastus'`** rates
(vCPU Active $0.000024, vCPU Idle $0.000003, Memory Active/Idle both $0.000003 — all effective since
2022-06-01, i.e. not a recent change) reproduces **$4.29 idle and $14.31 active exactly, to the cent**.
Canada Central's own rates (armRegionName eq 'canadacentral', confirmed 2026-08-22, also effective
since 2022-06-01 — so not a rate change over the 3 days since PLAN.md was written either) are
genuinely higher across the board: $0.000004 idle vCPU/memory (vs US East's $0.000003) and $0.000034
active vCPU (vs US East's $0.000024). Checked the regional spread directly: 26 of 61 regions,
including US East, sit at the $0.000003 idle-vCPU floor; Canada Central is one of the higher-priced
regions at $0.000004 — a genuine, stable regional difference, not noise.

**This project's resources all live in Canada Central** (ADR-001, decision 12 — data residency). The
$4.29/$14.31 figures were computed against the wrong region from the start; **Canada Central's rates
($5.72/mo idle, $20.03/mo active, this section) are the ones that actually apply and should be treated
as correct.** Not a rate change, not a stale calculator snapshot with a since-corrected number — a
region mismatch present since the original estimate (2026-08-19), just never checked against a live,
region-scoped source until this session.

**Consequence for PLAN.md**: its Budget section (the $4.29/$14.31 row, the derived $0.00588/$0.0196
hourly-equivalents in COSTS.md, and the "honest result including evals" table's $11.29/$21.31/$13.71/
$3.69 figures, all of which chain from the same US-East-derived numbers) is stale and should be
corrected to the Canada Central figures in a future approved PLAN.md edit — not done here, since
`docs/PLAN.md` stays out of scope for this session per Marco's own standing instruction this round.
Flagging it here is what makes that correction findable rather than rediscovered from scratch.

## R-08 — demo runs/month, recomputed on the corrected R-04 basis (2026-08-22)

The original PLAN.md estimate ("2 to 10.6 hours/month," ~30–160 demo runs depending on idle/active)
was built on the *naive* $4.29–$14.31/mo Container Apps range, with no free-grant netting. That
assumption no longer holds now that R-04 has both (a) a real verdict (IDLE, not a range) and (b) a
grant-corrected dollar figure. Recomputed here rather than left for Monday:

| Input | Value |
|---|---|
| Container Apps, net of free grant, IDLE rate (measured, this section) | $5.72/mo |
| Phone number | $1.00/mo |
| **Fixed monthly subtotal** | **$6.72/mo** |
| Eval-budget ceiling (hard cap, PLAN.md) | $6.00/mo |
| **Fixed + eval** | **$12.72/mo** |
| **Left for manual/demo calls** (of the $25/mo ceiling) | **$12.28/mo** |

| Per-minute rate | Minutes/mo | **Demo runs/mo** (B4's 5-min cap per run) |
|---|---|---|
| Floor ($0.0215/min) | 571.2 | **114.2** |
| Realistic ($0.031/min) | 396.1 | **79.2** |

**R-08: ~79–114 demo runs/month. Gate PASSES** (comfortably above the 5-run floor) — computed, verified
against the extracted computation in `04-teardown-and-r08.sh` itself (both the grant-cost and R-08
arithmetic blocks were pulled out of the script and re-run against this session's actual inputs — R-04's
telemetry-measured grant-cost figure ($5.72/mo, genuinely measured) and PLAN.md's own floor/realistic
per-minute rates ($0.0215/$0.031, its estimate, not a billing read) — before being trusted here).

The free grant is real and matters (it's
the difference between $5.72/mo and the $7.78/mo pre-grant idle figure this section's rates would
otherwise imply for a full month) — but because this app must run continuously all month for real
telephony service, the grant only ever offsets ~27.6% of a month's compute, not all of it. The
corrected R-08 range (~79–114 runs/mo) is *similar in order of magnitude* to PLAN.md's original naive
idle-scenario figures (~128–160 runs off its $13.71/mo left-for-calls), modestly lower because
PLAN.md's original estimate used US East rates rather than Canada Central (settled, not just flagged,
above) — not because compute turned out to be free. R-08 remains meaningfully bounded by
Container Apps' (now precisely measured) idle cost plus the eval budget, same as originally designed,
just with a verdict and a number instead of a range and an assumption.

## R-04 — idle-vs-active Container Apps billing verdict

Idle window: 2026-08-21T22:54:09Z to 2026-08-25T01:25:45Z (UTC), Container App left untouched, both WebSockets
closed per decision 15.

**The free compute grant is the headline, not this verdict.** Container Apps' standing monthly
free compute grant (180,000 vCPU-s / 360,000 GiB-s) covers ~8.3 days of this app's continuous
0.25 vCPU/0.5 GiB runtime every month, regardless of idle-vs-active. For an always-on service
(min-replicas=1, required for inbound telephony), that means ~27.6% of every month's compute is
free no matter what; the remaining ~21.7 days bill at whichever rate this verdict determines.

**Idle-vs-active verdict (supporting detail): IDLE**

- Replicas: 299 datapoints, 0 gaps
- Network: 299 intervals, 1 over 1,000 B/s
  (0 excluding the expected first-interval call-tail)
- Monthly Container Apps cost net of the free grant, at this verdict's rate: **$5.72**
  (Canada Central rates, not PLAN.md's $4.29/$14.31 — those were derived from US East
  rates by mistake, settled elsewhere in this file; PLAN.md's Budget section is stale here)

Cost Management cross-check (informational only — a $0/near-$0 reading here is expected given
the free grant above and does not by itself confirm or contradict the verdict):

```json

```

## R-08 — demo runs/month, computed from telemetry + hand-entered inputs

- Modeled $/minute: $0.031
- Modeled fixed monthly (extrapolated): $6.72
- Eval-budget ceiling reserved: $6.00 (docs/PLAN.md hard ceiling)
- Left for manual/demo calls: $12.28/mo
- At B4's 5-min cap per run: **79.2 demo runs/month**

**Provenance note**: none of the figures above come from an Azure Cost Management billing query.
`$6.72` (Fixed monthly) = `R04_MONTHLY_NET_OF_GRANT` (`$5.72`, computed from Container Apps
replica/network telemetry against Canada Central Retail Prices API rates, net of the free compute
grant) + a hardcoded `$1.00` phone-number constant — and matches `04-teardown-and-r08.sh`'s own
unmodified suggested default for that prompt exactly (`04:284`). `$0.031/min` (Per-minute floor) was
free-text keyboard entry at that script's `ask` prompt, matching the upper end of the fallback range
the prompt itself suggests typing (`04:290`) — not read from any per-minute billing meter. `79.2`
(Demo runs/month) is arithmetic performed on those two inputs (`04:294-309`). This run's three Cost
Management dollar-total queries (`COST_JSON`, `IDLE_COST_JSON`, `FULL_COST_JSON`) feed none of the
figures above.

**Open question, not resolved**: unlike `03-cost-check-24h.sh` Stage 3's sanity confirm (explicitly
attributed above — "answered by the assistant during this session, not by Marco"), no equivalent
disclosure exists anywhere in this file for who answered `04-teardown-and-r08.sh`'s two prompts
(`04:290-291`, `MEASURED_PER_MIN_COST` / `MEASURED_FIXED_MONTHLY_INPUT`) that produced `$0.031` and
`$6.72`. Who answered them is unknown from any tracked record.

## Stage 9 gap — PHONE_NUMBER skip check trusted a gitignored, machine-local file, 2026-08-31

Found by testing the guard's failure modes against a clean tree, not by reading the code and
assuming it was safe — same discipline as the ACS inventory volatility finding above.

**What was wrong**: Stage 9's skip check gated the entire search+purchase flow on `_existing
"PHONE_NUMBER"` — a read from `docs/phase0/wizard/.env.phase0`. That file is gitignored (`.env.*`,
confirmed via `git check-ignore -v`) and untracked (`git ls-files` returns nothing for it) — it
exists only on whichever machine ran the wizard, never travels with the repo. Stages 5, 6, 7, and 8
all gate their own idempotency on live Azure state instead (`az cognitiveservices account show`, a
`## R-06` marker in this file, `az cognitiveservices account deployment show`, `az communication
list`) — Stage 9 was the one stage in the sequence whose only guard against re-provisioning pointed
at a file, not at Azure.

**Why it mattered**: R-09 (`docs/PLAN.md`, `CLAUDE.md`) makes a second phone-number purchase
permanent and irreversible — no teardown path may ever release either number. A fresh clone, a
different machine, or a deleted/corrupted `.env.phase0` would silently defeat the only check
standing between a re-run and a second, permanent purchase, while the ACS resource genuinely still
owned the first number the whole time. Confirmed live on this machine, 2026-08-31: `.env.phase0`
currently does have `PHONE_NUMBER=+17059100383` set, so the gap wasn't live-exploitable here today —
but that safety net is exactly the file the gap depended on being present, which is the dependency
the fix below removes.

**Fix**: `b438cd5`, "Phase 1: Stage 9 checks Azure for owned numbers, not local env file." Stage 9
now queries `az communication phonenumber list --connection-string ...` (Azure CLI `communication`
extension; verified live against this project's own ACS resource before writing the fix — returns a
flat JSON array, each entry carrying a `phoneNumber` field) unconditionally on every run, and treats
that as the sole authority: if Azure reports an owned number, the stage skips regardless of what the
local file says, and self-heals `.env.phase0` to match Azure rather than trusting it. If Azure
reports none *and* the local file claims one, that's now a real discrepancy (`on_error 1`, stop and
investigate) rather than silently proceeding. The local file can no longer gate the purchase path in
either direction.

## Stage 9 gap — the fix's own JSON parse swallowed errors, 2026-08-31

Also found by testing, not reading: the first version of the fix above closed the local-file gap but
introduced a narrower one of its own in the process, caught only by feeding it deliberately
malformed input before treating it as safe.

**What was wrong**: `az communication phonenumber list`'s own exit-code failure was handled
correctly (`on_error 1`). But the two `python3 -c` calls parsing its JSON output used `2>/dev/null ||
echo 0` / `2>/dev/null || true` — any parse failure was silently coerced into "zero numbers owned"
rather than surfaced. Tested against four shapes locally (no Azure calls):

| stdin | `OWNED_COUNT` | `OWNED_NUMBER` |
|---|---|---|
| flat array, 1 entry (the real, verified shape) | `1` | `+17059100383` |
| `[]` (genuinely empty) | `0` | `''` |
| garbage / non-JSON | `0` | `''` |
| `{"value": [{"phoneNumber": "+17059100383"}]}` — object-wrapped | `1` *(coincidence — counts dict keys, not numbers)* | `''` |

The last case is the real finding: valid JSON, no exception reaches the `az`-call exit-code guard
(that guard only checks whether the command itself succeeded, not the shape of what it printed), yet
the number lookup silently swallows a `KeyError` and comes back empty — indistinguishable from
"Azure genuinely owns nothing." Not hypothetical: `az communication phonenumber list` is still
flagged preview by Azure itself (`WARNING: This command group is in preview and under development`,
printed on every invocation), and object-wrapped results (`"value": [...]`, `"phoneNumbers": [...]`)
are already the norm for the ACS REST endpoints this same script calls elsewhere (search, purchase,
list-owned-post-purchase). Combined with an absent local file — the exact scenario the fix above
exists to handle — this would have silently fallen through to the purchase flow with Azure already
owning a number.

**Fix**: folded into the same commit (`b438cd5`, amended before it was ever pushed or reviewed as
final — no separate commit for the intermediate, narrower-buggy version exists in history). The two
separate parses were replaced with one `python3` call that explicitly asserts the top-level JSON is
a list (exits nonzero with a message if not) before indexing into it; a nonzero exit is now treated
exactly like the `az` command's own failure — `on_error 1`, not a default. Re-tested against the
same four shapes: the two genuine shapes (flat array, empty array) parse identically to before; both
bad shapes (garbage, object-wrapped) now stop the script with a clear diagnostic instead of reading
as "zero owned."

