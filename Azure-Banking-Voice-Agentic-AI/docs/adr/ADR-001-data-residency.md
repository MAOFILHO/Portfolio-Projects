# ADR-001 — Data residency

Status: Accepted
Date: 2026-08-20

## Context

**R-06 result: DataZoneStandard is confirmed NOT offered for `gpt-realtime-mini` version `2025-10-06`, as of 2026-08-20 — an empirical deployment attempt, not an assumption.** Exact error returned by the account-deployment PUT call against `aoai-azure-banking-voice-cc`:

```
ERROR: (InvalidResourceProperties) The specified SKU 'DataZoneStandard' of account deployment is not supported by the model 'gpt-realtime-mini' version: '2025-10-06'.
Code: InvalidResourceProperties
Message: The specified SKU 'DataZoneStandard' of account deployment is not supported by the model 'gpt-realtime-mini' version: '2025-10-06'.
```

Explicit and unambiguous — a SKU-not-supported error for this model+version, not a quota or permission
error that might resolve differently under other conditions.

Full record: `docs/phase0/findings.md`, "R-06 — DataZoneStandard deployment probe".

## Decision

Every resource this project provisions (ACS, Azure OpenAI, Container Apps, Table Storage) is created in
a single Canadian jurisdiction (Canada Central / `dataLocation: Canada`). Data **at rest** stays in
that geography.

Quotable, from the Foundry data-privacy page:

> For any deployment type labeled 'Global,' prompts and responses may be processed in any geography
> where the relevant model sold by Azure is deployed. [...] any data stored at rest [...] is stored in
> the customer-designated geography. Only the location of processing is affected.

**This project's resource footprint is entirely Canadian, but that does not make its processing
Canadian-only — the two claims are separate and neither should be conflated with the other.** The
`gpt-realtime-mini` deployment used here is `GlobalStandard`, the only SKU R-06
confirmed is actually offered for this model. Global deployment type means inference may run in any of
the six Global Standard regions (canadacentral, centralus, eastus2, francecentral, swedencentral,
southindia) — spanning the US, EU, and India, not just Canada — regardless of where the resource itself
is deployed. A real Canadian bank under strict data-residency requirements would need a Standard
(single-region) deployment type instead of Global to close that gap — Data Zone is not available as that
alternative for this model, per R-06 above.

## Consequences

- At-rest data (ACS call artifacts, Table Storage, App Insights) is provably single-jurisdiction
  Canadian — this claim is fully supported and should be stated without hedging.
- Processing (the realtime model call itself) is not single-jurisdiction — this is disclosed, not
  hidden, and should never be stated as "processed only in Canada" anywhere in this project's docs or
  portfolio write-up. That would overstate the residency guarantee this architecture actually provides.
- Retention figures: do not cite a "30 days" abuse-monitoring retention figure anywhere in this
  project's documentation — it does not appear in current Microsoft documentation as of the scoping pass
  that produced `docs/PLAN.md`, and using it would be citing a number nobody re-confirmed. Cite the DPA
  directly, or state that retention is not independently verified, rather than repeating an unconfirmed
  figure.
