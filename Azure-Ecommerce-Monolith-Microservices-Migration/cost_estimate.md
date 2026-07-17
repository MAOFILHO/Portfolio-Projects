# Cost Estimate — Approved Record

This is the permanent record of the Azure cost estimate approved before any resource was
provisioned. Pricing was live-checked against public Azure pricing pages on 2026-07-15; verify
current pricing on the [Azure Pricing Calculator](https://azure.microsoft.com/en-us/pricing/calculator/)
before provisioning, since prices drift over time.

**Nothing here bills unless you run `make provision`.** By default this project runs entirely
locally (plain Python/Node processes, SQLite, zero Docker, zero Azure) at **$0 cost**.

## Cost table

| Resource | SKU/Tier chosen | Reason | Est. cost/hour if running | Est. cost for an 8-hr test session | Est. cost if left running 30 days | Cheaper alternative |
|---|---|---|---|---|---|---|
| Resource Group | n/a | Free container | $0 | $0 | $0 | — |
| Azure Container Registry | **Basic** | Cheapest tier (no free tier exists for ACR), 10GB storage included, supports `az acr build` (cloud-side image builds, no local Docker needed) | $0.007 | $0.06 | **$5.01** | None cheaper — Basic is the floor |
| Container Apps Environment + Container Apps (monolith + bff at `make provision`; user-, product-, order-service created live by the migration itself) | **Consumption plan, minReplicas=0 (scale-to-zero)** | First 180,000 vCPU-s + 360,000 GiB-s + 2M requests/mo are free — effectively the "free tier" for this resource type; scale-to-zero means $0 idle cost | ~$0 idle | ~$0 | **~$0** (if `keepWarm` is never set to true) | N/A — this is already the cheapest option |
| Azure Database for MySQL Flexible Server | **Burstable B1ms** (1 vCore/2GiB), single server hosting 4 logical databases (monolith_db, user_db, product_db, order_db) provisioned upfront | Cheapest managed MySQL tier (no free tier exists for managed MySQL); sharing one server across 4 logical DBs avoids paying for 4 separate servers (documented tradeoff: less isolation than 4 servers, acceptable for a demo) | $0.019 (compute) | $0.15 | **~$14.50** (compute + 20GB storage) | SQLite (already used for local dev; not used in Azure to keep the "real MySQL in prod" story) |
| Azure Static Web Apps | **Free tier** | 100GB bandwidth/mo, 1GB storage, free SSL | $0 | $0 | **$0** | N/A — already free |
| Application Insights / Log Analytics | Pay-as-you-go, workspace-based | First 5GB/day ingestion free; demo-scale traffic stays inside this | $0 | $0 | **~$0** | N/A |
| Cost Management budget alert | n/a | Free, created by `provision.py` before any billable resource | $0 | $0 | $0 | — |
| Contributor role assignment (bff's managed identity, scoped to this one resource group only) | n/a | Free — control-plane only, lets the bff create the microservices' Container Apps itself during a live migration | $0 | $0 | $0 | — |

**Total estimated cost for an 8-hour test session: ~$0.21**
**Total estimated cost if resources are accidentally left running for 30 days: ~$19.51**

These figures are **unchanged** from the original estimate — the only thing that changed is *when*
each Container App gets created (monolith + bff at `make provision`; user-/product-/order-service
created live during the migration itself instead of all five upfront), not the SKUs or pricing.
ACR and MySQL Flexible Server are the only two resources in this whole stack with no free tier
anywhere in Azure; everything else is already on its Free or scale-to-zero tier. No single
resource exceeds $50/30-days — no red flag. **Azure Database for MySQL Flexible Server is the one
resource that bills whether idle or not** (Container Apps scale to zero; MySQL does not). Run
`make teardown` when you're done — this is called out again in `provision.py`'s output and in the
README.

## Budget ceiling

Approved ceiling: **$25/month** (default; pass a different value via `--budget-ceiling` to
`infra/provision.py`). A Cost Management budget alert is created via `az consumption budget
create` before any billable resource, notifying `--budget-email` at 80% and 100% of this ceiling.

## Naming-collision handling (tested for real)

ACR, MySQL Flexible Server, and Static Web App names were verified against real Azure during
development: a throwaway ACR was created with a fixed name, `infra/name_resolver.py` was proven to
detect the collision (`az acr check-name`) and resolve to an auto-incremented alternate name, then
the throwaway resource was deleted. See `CLAUDE.md` for details. Note: ACR names must be
alphanumeric only (no hyphens) — the resolver uses a hyphen-free increment scheme (`name2`,
`name3`, ...) for ACR specifically, and a hyphenated scheme (`name-2`, `name-3`, ...) for
hyphen-tolerant resource types (MySQL server name, Static Web App name).

## Assumptions

- Region: set via `AZURE_LOCATION` in `.env` (defaults to `eastus` in `.env.example`) — never
  hardcoded in code. Falls back to `az config get defaults.location`, then to `eastus`, only if
  `.env` doesn't set it.
- Pricing assumes pay-as-you-go rates in USD; regional/currency variance applies.
- The 30-day figures assume the Container Apps stay at scale-to-zero (`keepWarm=false`, the
  default) — if you deliberately set `minReplicas>=1` to avoid cold starts during a live demo, get
  a fresh estimate from the Azure Pricing Calculator before leaving it running.
