# Cost

See the [README cost table](../README.md#cost-estimates) for the headline numbers. This page covers the knobs and what drives cost.

## Always-on costs: Container Registry, and (if enabled) the Nest ingestor

By default, every compute resource except Container Registry scales to zero when idle. **Azure Container Registry (Basic SKU)** does not — it's a flat ~$5/month (~$0.17/day) regardless of usage, because it's needed to host the backend image for `az acr build` / Container Apps pulls. If you tear down between demo sessions (`surveil-deploy teardown`), this cost only accrues while the environment exists.

**If you enable the Nest doorbell ingestor** (`NEST_INGESTOR_ENABLED=true`), a second always-on cost is added: its Container App is fixed at `minReplicas: 1` (it holds a persistent Pub/Sub connection and must never scale to zero), at the smallest workload size (0.25 vCPU / 0.5Gi). Running continuously for a full month, that's roughly **$10-15/month** at current Azure Container Apps consumption pricing (0.25 vCPU × ~2.6M seconds/month + 0.5Gi × ~2.6M seconds/month, after the monthly free grant) — check the [Azure Container Apps pricing page](https://azure.microsoft.com/pricing/details/container-apps/) for the exact current rate, since it changes over time. This is the one part of the system that keeps costing money even when nothing is happening at your front door, unlike everything else described below.

## Vision SKU: F0 vs S1

- `VISION_SKU=S1` (default): pay-per-call, no rate limit. Cost scales with how many frames you actually analyze.
- `VISION_SKU=F0`: free tier, but **limited to one F0 Cognitive Services resource per subscription** across *all* Cognitive Services kinds, and capped at 20 calls/minute. Fine for a light demo (e.g. one camera at a 3-10s capture interval); switch to S1 if you hit the rate limit or already have another F0 resource in the subscription.

## Storage SKU

`STORAGE_SKU_NAME=Standard_LRS` (default) is the cheapest option. `Standard_ZRS`/`Standard_GRS` add redundancy at extra cost and are not necessary for a demo system with no durability SLA.

## Reducing cost further

- Increase `CAPTURE_INTERVAL_SECONDS` (fewer frames -> fewer Vision calls).
- Tear down (`surveil-deploy teardown`) between sessions rather than leaving the environment provisioned — Container Apps/Functions cost ~$0 idle, but ACR and Storage still accrue small amounts.
- Skip ACS entirely (leave `ALERT_EMAIL_TO`/`ALERT_SMS_TO` empty) if you only need the in-app WebSocket alert feed — the ACS resource itself is free to provision; cost is per-message sent.

## Estimating your own usage

Rough formula for Vision cost at S1: `frames_analyzed_per_month × price_per_1000_transactions / 1000`. Check current [Azure AI Vision pricing](https://azure.microsoft.com/pricing/details/cognitive-services/computer-vision/) for the exact per-transaction rate in your region, since it changes over time.
