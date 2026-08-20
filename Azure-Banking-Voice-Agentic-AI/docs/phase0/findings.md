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
