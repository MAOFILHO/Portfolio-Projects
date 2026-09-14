#!/usr/bin/env bash
# Provisions workspace-based Application Insights (infra/modules/app-insights.bicep) and wires its
# connection string into the voice agent's Container App -- issue #62, follow-up to #61.
#
# ============================================================================================
# DO NOT RUN THIS AUTOMATICALLY. Written for Marco to read and run himself, or to approve line by
# line -- not for an agent session to execute. CLAUDE.md: "Never auto-accept a diff that provisions
# a billable resource... no matter how mechanical." This script provisions one (Application
# Insights) and mutates a live Container App revision (ca-azbank-echo-p0). Both are exactly the
# category of change that gets a human look first.
#
# `APPROVED: Phase 6` is already on record (PROJECT_STATE.md, typed 2026-09-12) -- that covers the
# billable-resource gate. It does not cover skipping the review this script's own existence is
# structured around: read it before running it.
# ============================================================================================
#
# What this does, in order:
#   1. Confirms the az CLI is on the right subscription.
#   2. Deploys infra/modules/app-insights.bicep into the existing resource group, bound to the one
#      Log Analytics workspace proven to deliver rows (`...1D`) -- never the other two.
#   3. Reads the deployment's connectionString output.
#   4. Sets that connection string as a Container App secret on ca-azbank-echo-p0 (never printed to
#      the terminal in full -- see the redaction note at that step) and points
#      APPLICATIONINSIGHTS_CONNECTION_STRING/AZURE_MONITOR_AUTH at it, forcing a new revision so the
#      env vars are actually read (secretRef env vars are read at container start only -- the same
#      "placeholder race" `docs/phase0/findings.md` documents for APP_BASE_URL applies here).
#
# What this deliberately does NOT do:
#   - Assign any IAM role. D10's Entra-authenticated identity path needs a role that is still an
#     open `/research` question (docs/phase6/exit-criteria.md D10; infra/modules/app-insights.bicep's
#     own header). Guessing one was explicitly out of scope for the session that wrote this script.
#     This script wires the NAMED FALLBACK instead: connection-string auth
#     (AZURE_MONITOR_AUTH=connection_string), which telemetry.py's span_exporter_from_env /
#     metric_reader_from_env both already support. That carries a Phase 7 debt (D10) to move to the
#     identity path once the role is known -- tracked there, not solved here.
#   - Make the D16 smoke call, or query `...1D` for its rows. See docs/phase6/smoke-call-runbook.md
#     for that -- it needs a human on the phone.
#   - Touch the phone number, in any way, at any step.
#   - Touch the two other Log Analytics workspaces (`...aiCS`, `...aixC`).
#
# Idempotency: `az deployment group create` on the same template/parameters is a no-op ARM diff if
# nothing changed. The Container App secret-set + update steps mirror docs/phase0/wizard/
# 01-provision.sh's own re-run-safe pattern (secret set explicitly, then a forced --revision-suffix)
# rather than relying on --set-env-vars alone to trigger a new revision.

set -euo pipefail

# --- Fixed identifiers, matching PROJECT_STATE.md's "Live Azure state" and the other wizard
#     scripts' own hardcoded values (docs/phase0/wizard/01-provision.sh:202-204) -- not re-derived
#     here, and not meant to be overridden by environment variables, on purpose: this script targets
#     one specific subscription, resource group and workspace, never whatever happens to be current.
SUBSCRIPTION_ID="960936b9-ecde-465b-be8d-776ca077dcd0"
LOCATION="canadacentral"
RESOURCE_GROUP="rg-azure-banking-voice-agentic-ai"
WORKSPACE_NAME="workspace-rgazurebankingvoiceagenticai1D"
APP_INSIGHTS_NAME="appi-azure-banking-voice"
CONTAINERAPP_NAME="ca-azbank-echo-p0"
BICEP_MODULE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/modules/app-insights.bicep"

say() { printf '\n[provision-app-insights] %s\n' "$1"; }
err() { printf '\n[provision-app-insights] ERROR: %s\n' "$1" >&2; }

say "Target: Application Insights '$APP_INSIGHTS_NAME' in $RESOURCE_GROUP ($LOCATION),"
say "workspace-based on '$WORKSPACE_NAME'. Wiring target: Container App '$CONTAINERAPP_NAME'."
say "This has NOT been validated with 'az bicep build' -- see infra/modules/app-insights.bicep's"
say "own header. Consider running that first, separately, before this script's deployment step."

read -r -p "Type APPLY to continue, anything else to abort: " CONFIRM
if [[ "$CONFIRM" != "APPLY" ]]; then
  err "aborted -- confirmation not given."
  exit 1
fi

# --- Step 1: subscription check --------------------------------------------------------------
CURRENT_SUB="$(az account show --query id -o tsv)"
if [[ "$CURRENT_SUB" != "$SUBSCRIPTION_ID" ]]; then
  err "az is on subscription $CURRENT_SUB, expected $SUBSCRIPTION_ID. Run:"
  err "  az account set --subscription $SUBSCRIPTION_ID"
  exit 1
fi
say "subscription confirmed: $SUBSCRIPTION_ID"

# --- Step 2: pre-flight reads, no writes ------------------------------------------------------
# Confirm the one workspace this must bind to actually exists before spending an ARM call on a
# deployment that would fail anyway, and confirm the OTHER two are not what gets touched by mistake
# (belt-and-suspenders alongside the Bicep module's own @allowed constraint).
if ! az monitor log-analytics workspace show \
    --resource-group "$RESOURCE_GROUP" --workspace-name "$WORKSPACE_NAME" \
    --query customerId -o tsv >/dev/null 2>&1; then
  err "workspace $WORKSPACE_NAME not found in $RESOURCE_GROUP -- stopping before deployment."
  exit 1
fi
say "workspace $WORKSPACE_NAME confirmed present."

if ! az containerapp show --name "$CONTAINERAPP_NAME" --resource-group "$RESOURCE_GROUP" \
    >/dev/null 2>&1; then
  err "container app $CONTAINERAPP_NAME not found in $RESOURCE_GROUP -- stopping before deployment."
  exit 1
fi
say "container app $CONTAINERAPP_NAME confirmed present."

# --- Step 3: the actual provisioning step -- BILLABLE, though R-08's recompute (COSTS.md) prices
#     it at $0.00/mo added at this project's volume, before it is a measurement rather than a bound.
DEPLOYMENT_NAME="app-insights-$(date -u +%Y%m%d%H%M%S)"
say "deploying $BICEP_MODULE as deployment '$DEPLOYMENT_NAME'..."
az deployment group create \
  --name "$DEPLOYMENT_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --template-file "$BICEP_MODULE" \
  --parameters location="$LOCATION" name="$APP_INSIGHTS_NAME" logAnalyticsWorkspaceName="$WORKSPACE_NAME" \
  --output none
say "deployment '$DEPLOYMENT_NAME' submitted and returned. Per CLAUDE.md: this proves creation, not"
say "delivery -- the smoke call and queried row (docs/phase6/smoke-call-runbook.md) prove delivery."

# --- Step 4: read the connection string back, without ever echoing it in full ------------------
# NOT via the deployment's own output, even though the Bicep module declares one: ARM redacts
# @secure() outputs from deployment history unconditionally -- `az deployment group show/create`
# always returns an empty value for a SecureString output, by design, precisely so a secret can't be
# read back out of deployment metadata after the fact. Confirmed live 2026-09-14 (first run of this
# script hit exactly this: deployment succeeded, appInsightsId/instrumentationKey outputs came back
# populated, connectionString's `value` key was simply absent). The Bicep output stays -- it is still
# the documented, discoverable place a future reader looks for this value -- but this script reads
# the live resource directly instead, which is not subject to that redaction.
CONNECTION_STRING="$(az monitor app-insights component show \
  --app "$APP_INSIGHTS_NAME" --resource-group "$RESOURCE_GROUP" \
  --query connectionString -o tsv)"
if [[ -z "$CONNECTION_STRING" ]]; then
  err "component exists but returned an empty connection string -- stopping before wiring."
  exit 1
fi
# Redacted echo: confirms something non-empty came back without putting the credential in scrollback
# or any log this script's own output might end up in -- the same discipline B2 already applies to
# the PIN, extended here to a different bearer credential on principle, not because B2 itself covers
# it (D7 named exactly two literals; this isn't one of them).
say "connection string retrieved (${#CONNECTION_STRING} chars, not printed)."

# --- Step 5: wire it into the Container App, forcing a new revision ----------------------------
# Mirrors docs/phase0/wizard/01-provision.sh's own secret-set-then-forced-revision pattern
# (01-provision.sh:1160-1179) exactly, for the exact reason recorded there: --set-env-vars alone
# does not guarantee a new revision, and secretRef env vars are only read at container start.
say "setting Container App secret and forcing a new revision on $CONTAINERAPP_NAME..."
az containerapp secret set \
  --name "$CONTAINERAPP_NAME" --resource-group "$RESOURCE_GROUP" \
  --secrets "appinsights-conn=$CONNECTION_STRING" \
  --output none

az containerapp update \
  --name "$CONTAINERAPP_NAME" --resource-group "$RESOURCE_GROUP" \
  --revision-suffix "obs$(date -u +%Y%m%d%H%M%S)" \
  --set-env-vars \
    "APPLICATIONINSIGHTS_CONNECTION_STRING=secretref:appinsights-conn" \
    "AZURE_MONITOR_AUTH=connection_string" \
  --output none

say "done. $CONTAINERAPP_NAME now has a new revision with telemetry configured via the"
say "connection-string fallback (AZURE_MONITOR_AUTH=connection_string) -- NOT the identity path,"
say "because the IAM role that path needs is still an open /research question (D10)."
say ""
say "Next: make the D16 smoke call (docs/phase6/smoke-call-runbook.md) and query '$WORKSPACE_NAME'"
say "for its rows. An ARM 200 OK here proves creation, not delivery."
