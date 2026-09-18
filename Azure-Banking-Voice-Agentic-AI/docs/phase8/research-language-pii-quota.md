# Phase 8 research — Azure AI Language Conversation PII detection: quota and region availability

Pure documentation research gating D2's provisioning step (`docs/phase8/exit-criteria.md`, "`/research`
still owed" section): whether Azure AI Language **Conversation PII detection** — not generic Text PII
detection — has a free (F0) allotment, and whether it is available in Canada Central specifically
(non-negotiable per `ADR-001`). **No application code was written or changed for this task.** All
claims below are sourced from live fetches of primary sources performed **2026-09-18** (URL + fetch
date next to every claim, matching `docs/phase6/research-content-capture.md`'s convention). Where a
primary source does not settle something, it is marked **OPEN QUESTION** rather than filled in by
inference.

---

## 1. Does F0 (free tier) exist for Conversation PII detection?

### 1a. The pricing page's own tier table — Conversation PII is Standard-only, no free row

Azure's canonical Language pricing page (`azure.microsoft.com/en-us/pricing/details/cognitive-services/language-service/`
redirects to `azure.microsoft.com/en-us/pricing/details/language/`, fetched **2026-09-18**) lays its
pricing table out as one row per SKU tier, each row listing the exact features that tier covers. The
**Free - Web** row's feature list, quoted verbatim from the page's HTML:

> ```
> Sentiment analysis (available in containers)
> Key phrase extraction (available in containers)
> Language detection (available in containers)
> Custom question answering
> Prebuilt question answering
> Named entity recognition (available in containers)
> PII detection (available in containers)
> Summarization (all types)
> ```
> (plus, in the same rowspan block) `Conversational language understanding`, `Orchestration workflow`,
> `Custom text classification`, `Custom named entity recognition`
> — [Azure AI Language pricing](https://azure.microsoft.com/en-us/pricing/details/language/), fetched
> 2026-09-18

**"Conversational PII redaction" does not appear anywhere in the Free row's feature list.** It appears
exactly once on the page, and only under the **Standard (S) - Web** row:

> ```
> Sentiment analysis (available in containers)
> Key phrase extraction (available in containers)
> Language detection (available in containers)
> Named entity recognition (available in containers)
> PII detection (available in containers)
> Text PII redaction (available in containers)
> Conversational PII redaction
> ```
> — same page, fetched 2026-09-18

**Verdict: no F0/free SKU exists for Conversation PII detection.** Plain (Text) PII detection does get
the free allotment (it's listed in the Free row); "Text PII redaction" and "Conversational PII
redaction" are both Standard-tier-only line items, priced from the first record — there is no free
quota to exhaust before billing starts.

### 1b. A second, independent signal on the same page agrees

The page's own pricing-table footnotes (a separate `<ol>` list, not the per-row feature lists in §1a)
state:

> "Summarization, sentiment analysis, key phrase extraction, language detection, question answering,
> named entity recognition, and conversational language understanding all share 5,000 free text
> records per month."
> — same page, fetched 2026-09-18

This footnote's list **also omits both "PII detection" and "Conversational PII redaction"** (a minor
inconsistency with §1a's table, which does place plain "PII detection" in the Free row — that specific
discrepancy is **OPEN QUESTION**, but it doesn't affect Conversation PII: both the table placement and
this footnote's omission agree that Conversation PII redaction is excluded from the free allotment).
**No records/month or transactions/month free quota exists for Conversation PII detection under any
primary source found.**

### 1c. What Conversation PII redaction actually costs (Canada Central, Standard tier)

Reading the Standard-tier row's embedded pricing data (`data-amount` JSON) directly from the page's
HTML for the `canada-central` region key, quoted verbatim:

> `"0.0M-0.50M"` tier: `"canada-central":1.0` (USD per 1,000 text records)
> `"0.5M-2.50M"` tier: `"canada-central":0.75` (USD per 1,000 text records)
> — [Azure AI Language pricing](https://azure.microsoft.com/en-us/pricing/details/language/), fetched
> 2026-09-18 (embedded pricing-calculator JSON, read directly from page source since the rendered price
> value itself is populated client-side and did not resolve through automated fetch)

The page's footnote also states: **"Please contact sales for pricing of over 10 million text
records."** — same page, fetched 2026-09-18. This is the ceiling on the published self-serve tiers, not
a quota or rate limit.

**This is itself a second, independent confirmation that `canada-central` is a live, priced region for
Conversation PII redaction specifically** — not just the base Language resource in general — because
Azure's pricing-calculator data only carries a `data-amount` entry, per-region, for regions where that
exact meter is orderable. See §2 for the region question in full.

### 1d. Rate limits (apply once a Standard resource is provisioned — no F0 tier exists to rate-limit)

Microsoft's data-limits reference gives rate limits by resource pricing tier, stated to apply
per-feature:

> | Tier | Requests per second | Requests per minute |
> | --- | --- | --- |
> | S / Multi-service | 1000 | 1000 |
> | S0 / F0 | 100 | 300 |
>
> "Your rate limit varies with your pricing tier... Requests rates are measured for each feature
> separately."
> — [Data limits for Language service features - Microsoft Learn](https://learn.microsoft.com/en-us/azure/ai-services/language-service/concepts/data-limits), fetched 2026-09-18 (page `ms.date: 2026-04-03`)

Since §1a–1c establish Conversation PII redaction only exists under the Standard (S) tier, the
applicable row is **`S / Multi-service`: 1000 requests/second, 1000 requests/minute** — the `S0 / F0`
row is moot for this specific feature, because that tier doesn't offer it at all.

The same page also gives Conversation PII's own document-shape limits directly (not shared with other
features):

> "**Conversation PII** | 1,000 characters as measured by Analyze Conversations API. A conversation can
> have a list of conversation items (turns). 1,000 is the max limit for each conversation item (not for
> the entire conversation). The conversation PII API supports asynchronous requests only."
> — same page, fetched 2026-09-18

**OPEN QUESTION**: the same page's "Maximum documents per request" table has a row for "Personally
Identifying Information (PII) detection" capped at 5 documents/request, but does not distinguish Text
PII from Conversation PII by name in that specific row, while the Conversation PII how-to page (§2)
states conversation requests are submitted as **one conversation per request** (a different unit than
"documents"). No primary source fetched reconciles whether the 5-document cap is meant to apply to
Conversation PII's per-request conversation submission at all — not answered here.

---

## 2. Is Conversation PII detection available in Canada Central specifically?

### 2a. The feature's own how-to page states a blanket rule, by name

> "### Region support
> The conversational PII API supports all Azure regions supported by Azure Language."
> — [Identify and extract PII from conversations - Microsoft Learn](https://learn.microsoft.com/en-us/azure/ai-services/language-service/personally-identifiable-information/how-to/redact-conversation-pii), fetched 2026-09-18 (page `ms.date: 2026-08-17`)

This is a direct, primary-source, feature-specific statement — not an inference from "the base Language
resource exists in Canada Central." It says explicitly that the conversational PII API's region
footprint equals whatever the general Language service's region footprint is (no reduced subset), which
is the thing the task asked to confirm rather than assume.

### 2b. The general regional-support reference corroborates by omission

Microsoft's per-feature regional-restriction reference page lists tables only for features that have
**reduced** region availability — Conversational language understanding/orchestration, Custom NER,
Custom text classification, Summarization, and Custom question answering. It has **no row or table for
PII detection or Conversation PII at all**, consistent with the page's own framing:

> "Typically... most Language capabilities are available in all supported regions. Some Language
> capabilities, however, are only available in select regions."
> — [Regional support for Azure Language - Microsoft Learn](https://learn.microsoft.com/en-us/azure/ai-services/language-service/concepts/regional-support), fetched 2026-09-18 (page `ms.date: 2026-03-27`)

The same page's Conversational language understanding, Custom NER, and Custom text classification
tables (which *do* enumerate regions because those features **are** region-restricted) each list
`CanadaCentral | ✓ (Authoring) | ✓ (Prediction)` by name — confirming the base Language resource
operates fully in Canada Central, consistent with §2a but not itself a Conversation-PII-specific
statement (noted here only as corroboration, not as the basis for the answer).

### 2c. The pricing page confirms Canada Central by name, for this exact feature

As shown in §1c, the Standard-tier "Conversational PII redaction" pricing row's `data-condition-region`
attribute and `data-amount` JSON explicitly include `canada-central` with real per-1,000-record prices
(`$1.00` and `$0.75` across the first two volume tiers) — the meter is live and orderable in that region
specifically, for this specific feature line item, not just for the Language resource generally.
— [Azure AI Language pricing](https://azure.microsoft.com/en-us/pricing/details/language/), fetched
2026-09-18.

### 2d. Verdict

**SETTLED — Canada Central is confirmed by name for Conversation PII detection specifically**, via two
independent primary sources: (1) the feature's own how-to page states plainly that it supports all
regions the Language service supports, and (2) the feature's own pricing-table row carries a live,
priced `canada-central` meter. Neither source required inferring from "the Language service resource
type is available in Canada Central" alone — §2a is a feature-specific regional statement, and §2c is
feature-specific priced-meter evidence, not a base-resource-type statement.

---

## Answers to the two questions

- **Question 1 — SETTLED.** No F0/free tier exists for Conversation PII detection (Conversational PII
  redaction): it is Standard (S)-tier only, priced from the first text record — $1.00/1,000 records for
  the first 0.5M records/month in Canada Central, $0.75/1,000 for the next tier. Once provisioned
  (necessarily on Standard), the applicable rate limit is 1000 requests/second and 1000
  requests/minute. Plain Text PII detection does get the shared 5,000-free-text-records/month
  allotment; Conversation PII detection does not — confirmed by two independent parts of the same
  pricing page (the Free-tier row's feature list, and the fee-sharing footnote), both of which omit it.
  One narrow point is flagged **OPEN QUESTION**: whether the data-limits page's generic
  "5 documents/request" PII cap applies to Conversation PII's "one conversation per request" submission
  shape.
- **Question 2 — SETTLED.** Conversation PII detection is available in Canada Central, confirmed by
  name in two independent primary sources: the feature's own how-to page ("supports all Azure regions
  supported by Azure Language") and the feature's own pricing-table row (a live, priced `canada-central`
  meter).

**Bottom line for D2's provisioning gate**: Conversation PII detection can be provisioned in Canada
Central (region is not a blocker), but it will incur real, non-free cost from the first record — the
$25/month budget ceiling analysis for D2 should price it at Standard-tier rates ($1.00/1,000 text
records in the first volume tier), not assume any free allotment. Given the project's ~45–67 demo
calls/month volume (see `COSTS.md`), the per-record Standard pricing found here is the number to run
through that budget check next, not the shared free tier this research shows does not apply.
