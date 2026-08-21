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

