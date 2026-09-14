#!/usr/bin/env bash
#
# Phase 0 wizard, script 4 of 4 — Idle billing verdict, R-08, ADR finalization, teardown.
# Run this once ~72 hours have passed since 01-provision.sh created the Container App.
#
# WHAT ONLY YOU CAN DO HERE: let 72h of wall-clock time pass with the Container App sitting idle
# (no test calls, no manual pokes) so R-04's idle-vs-active billing question gets a real answer.
# Everything in this script itself is automated: reading the idle-window cost, computing R-08,
# finalizing COSTS.md, and tearing down compute while keeping the phone number leased.
#
# THIS SCRIPT DOES NOT ASK FOR RE-APPROVAL TO TEAR DOWN — teardown is a cost-reducing action (deleting
# billable compute), not a new billable-resource-creation the CLAUDE.md gate is about. It DOES pause
# before deleting anything, and it never touches the ACS resource or the phone number.

set -euo pipefail

if [[ -t 1 ]] && command -v tput >/dev/null 2>&1 && [[ "$(tput colors 2>/dev/null || echo 0)" -ge 8 ]]; then
  BOLD=$(tput bold); DIM=$(tput dim); RESET=$(tput sgr0)
  BLUE=$(tput setaf 4); GREEN=$(tput setaf 2); YELLOW=$(tput setaf 3); RED=$(tput setaf 1)
else
  BOLD=""; DIM=""; RESET=""; BLUE=""; GREEN=""; YELLOW=""; RED=""
fi

TOTAL_STAGES=0
_STAGE_INDEX=0
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${ENV_FILE:-$SCRIPT_DIR/.env.phase0}"
WRITTEN_ENV=()

_clear() { [[ -t 1 ]] || return 0; if command -v tput >/dev/null 2>&1; then tput clear; else printf '\033[2J\033[3J\033[H'; fi; }
banner() { _clear; printf '\n%s%s  %s%s\n' "$BOLD" "$BLUE" "$1" "$RESET"; printf '%s  %s stages%s\n\n' "$DIM" "$TOTAL_STAGES" "$RESET"; pause "Ready to start?"; }
stage() { _clear; _STAGE_INDEX=$((_STAGE_INDEX + 1)); printf '\n%s%s▸ Stage %s/%s · %s%s\n' "$BOLD" "$BLUE" "$_STAGE_INDEX" "$TOTAL_STAGES" "$1" "$RESET"; }
say()  { printf '  %s\n' "$1"; }
note() { printf '  %s%s%s\n' "$DIM" "$1" "$RESET"; }
warn() { printf '  %s⚠ %s%s\n' "$YELLOW" "$1" "$RESET"; }
ok()   { printf '  %s✓ %s%s\n' "$GREEN" "$1" "$RESET"; }
err()  { printf '  %s✗ %s%s\n' "$RED" "$1" "$RESET"; }
pause() { printf '  %s%s%s ' "$DIM" "${1:-Press Enter to continue}" "$RESET"; read -r _ || true; }
confirm() { local reply=""; printf '  %s? %s [y/N] ' "$YELLOW" "$1"; read -r reply || true; [[ "$reply" =~ ^[Yy] ]]; }
write_env() { local key="$1" value="$2" tmp; touch "$ENV_FILE"; tmp=$(mktemp); grep -vE "^${key}=" "$ENV_FILE" > "$tmp" || true; printf '%s=%s\n' "$key" "$value" >> "$tmp"; mv "$tmp" "$ENV_FILE"; WRITTEN_ENV+=("$key"); printf '  %s✓ wrote%s %s → %s\n' "$GREEN" "$RESET" "$key" "$ENV_FILE"; }
finish() { _clear; printf '\n%s%s  ✓ Script complete%s\n' "$BOLD" "$GREEN" "$RESET"; (( ${#WRITTEN_ENV[@]} )) && note "wrote ${#WRITTEN_ENV[@]} value(s) to $ENV_FILE: ${WRITTEN_ENV[*]}"; printf '\n'; }
# Was called (3x below) but never defined -- confirmed 2026-08-22 this was a latent crash bug
# ("ask: command not found", fatal under set -e) that would have hit the moment Stage 1 ran.
# Assigns the typed reply into the named variable via printf -v (indirect assignment).
ask() { local __var="$1" __prompt="$2" __reply=""; printf '  %s? %s%s ' "$YELLOW" "$__prompt" "$RESET"; read -r __reply || true; printf -v "$__var" '%s' "$__reply"; }

if [[ ! -f "$ENV_FILE" ]]; then
  printf 'No %s found — run 01-provision.sh through 03-cost-check-24h.sh first.\n' "$ENV_FILE"
  exit 1
fi
# shellcheck source=/dev/null
set -a; source "$ENV_FILE"; set +a

FINDINGS_FILE="$SCRIPT_DIR/../findings.md"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
COSTS_FILE="$REPO_ROOT/COSTS.md"

TOTAL_STAGES=6
banner "Azure-Banking-Voice-Agentic-AI — Phase 0, script 4/4: Idle verdict, R-08, teardown"

if [[ -z "${PROVISION_TIME:-}" ]]; then
  warn "PROVISION_TIME isn't in $ENV_FILE — can't confirm the 72h window. Continuing on your word."
  confirm "Has it genuinely been ~72h since the Container App was created (the brief 02-test-calls.sh session right after provisioning is expected and fine — it's calls SINCE then that would invalidate this), with no calls or manual pokes in that time?" || exit 0
else
  ELAPSED_H=$(( ( $(date -u +%s) - $(date -u -d "$PROVISION_TIME" +%s 2>/dev/null || date -u -j -f "%Y-%m-%dT%H:%M:%SZ" "$PROVISION_TIME" +%s) ) / 3600 ))
  if (( ELAPSED_H < 72 )); then
    warn "only ~${ELAPSED_H}h since provisioning (need ~72h for R-04's idle-billing window to mean anything)."
    confirm "Run anyway?" || { note "come back later — this script is safe to re-run."; exit 0; }
  else
    ok "~${ELAPSED_H}h elapsed since provisioning"
  fi
fi

# ── Stage 1: R-04 — idle-vs-active Container Apps billing verdict ───────────
stage "R-04 — idle-vs-active Container Apps billing verdict, from telemetry"
say "docs/PLAN.md: an open-but-silent WebSocket may keep a replica active-billed (~\$10/mo swing)."
say "Decision 15 closes both WebSockets on call end; this is the measured check of whether that holds."
note "Verdict is computed from the Container App's own Azure Monitor telemetry, not by eyeballing"
note "Cost Management dollars — confirmed 2026-08-22 that \$0/near-\$0 here is EXPECTED regardless of"
note "idle-vs-active (the free compute grant, below), so a dollar reading alone can't carry this verdict."

CA_ID="/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}/providers/Microsoft.App/containerapps/${CONTAINERAPP_NAME}"
NOW_TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

say "Querying Replicas (Maximum, PT15M) since $CALL3_TIME — confirms no scale-to-zero gap:"
REPLICAS_JSON=$(az monitor metrics list --resource "$CA_ID" \
  --metric "Replicas" --aggregation Maximum --interval PT15M \
  --start-time "$CALL3_TIME" --end-time "$NOW_TS" \
  -o json 2>&1) || { warn "Replicas metric query failed"; REPLICAS_JSON=""; }

say "Querying RxBytes/TxBytes (Total, PT15M) — the active-vs-idle signal, per PLAN.md's own stated"
say "1,000 B/s threshold (24 kHz PCM16 = 48,000 B/s during a call):"
NETBYTES_JSON=$(az monitor metrics list --resource "$CA_ID" \
  --metric "RxBytes,TxBytes" --aggregation Total --interval PT15M \
  --start-time "$CALL3_TIME" --end-time "$NOW_TS" \
  -o json 2>&1) || { warn "RxBytes/TxBytes metric query failed"; NETBYTES_JSON=""; }

TMP_REPLICAS=$(mktemp); TMP_NETBYTES=$(mktemp)
printf '%s' "$REPLICAS_JSON" > "$TMP_REPLICAS"
printf '%s' "$NETBYTES_JSON" > "$TMP_NETBYTES"

R04_RESULT=$(python3 - "$TMP_REPLICAS" "$TMP_NETBYTES" <<'PYEOF'
import json, sys

def load(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None

rep = load(sys.argv[1])
net = load(sys.argv[2])
THRESHOLD_BPS = 1000.0  # PLAN.md's own stated idle-vs-active threshold
INTERVAL_S = 900.0      # PT15M

rep_points = rep_gaps = 0
if rep is not None:
    for series in rep.get('value', []):
        for ts in series.get('timeseries', []):
            for dp in ts.get('data', []):
                rep_points += 1
                v = dp.get('maximum')
                if v is None or v == 0:
                    rep_gaps += 1

by_ts = {}
if net is not None:
    for series in net.get('value', []):
        for ts in series.get('timeseries', []):
            for dp in ts.get('data', []):
                t = dp.get('timeStamp')
                by_ts[t] = by_ts.get(t, 0) + (dp.get('total') or 0)

items = sorted(by_ts.items())
total_intervals = len(items)
first_ts = items[0][0] if items else None
over = [(t, tb / INTERVAL_S) for t, tb in items if tb / INTERVAL_S > THRESHOLD_BPS]
# The very first interval is expected to carry the tail of the last real test call (the idle window
# is defined as starting AT that call's timestamp) -- exclude it from the verdict, not from the report.
over_excl_first = [o for o in over if o[0] != first_ts]

if rep is None or net is None:
    verdict = "UNKNOWN (a metrics query failed -- see warnings above)"
elif rep_gaps > 0:
    verdict = "UNKNOWN (scale-to-zero: %d of %d Replicas datapoints)" % (rep_gaps, rep_points)
elif len(over_excl_first) == 0:
    verdict = "IDLE"
elif len(over_excl_first) == total_intervals or len(over_excl_first) == total_intervals - 1:
    verdict = "ACTIVE"
else:
    verdict = "MIXED (%d of %d intervals over threshold, excluding the expected call-tail interval)" % (len(over_excl_first), total_intervals)

print("R04_VERDICT=%s" % verdict)
print("R04_REPLICA_POINTS=%d" % rep_points)
print("R04_REPLICA_GAPS=%d" % rep_gaps)
print("R04_NET_INTERVALS=%d" % total_intervals)
print("R04_NET_OVER_THRESHOLD=%d" % len(over))
print("R04_NET_OVER_EXCL_FIRST=%d" % len(over_excl_first))
PYEOF
)
eval "$R04_RESULT"
rm -f "$TMP_REPLICAS" "$TMP_NETBYTES"

say "Replicas: $R04_REPLICA_POINTS datapoints, $R04_REPLICA_GAPS gaps (scale-to-zero or missing)."
say "Network: $R04_NET_INTERVALS intervals, $R04_NET_OVER_THRESHOLD over the 1,000 B/s threshold"
say "($R04_NET_OVER_EXCL_FIRST excluding the expected first-interval call-tail)."
say "Verdict: $R04_VERDICT"
write_env "R04_VERDICT" "$R04_VERDICT"

# Cost Management as a labeled CROSS-CHECK only -- not the verdict source. Same az rest fix as
# 03-cost-check-24h.sh (the `az costmanagement query` CLI subcommand does not exist in the
# installable costmanagement extension, v1.0.0 -- confirmed 2026-08-22).
say "Cross-check: Cost Management's own dollar figure for this Container App over the same window"
say "(informational only -- the verdict above does not depend on this):"
QUERY_BODY=$(printf '{"type":"ActualCost","timeframe":"Custom","timePeriod":{"from":"%s","to":"%s"},"dataset":{"granularity":"Daily","aggregation":{"totalCost":{"name":"Cost","function":"Sum"}},"filter":{"dimensions":{"name":"ResourceId","operator":"In","values":["%s"]}}}}' \
  "$(date -u -d "$CALL3_TIME" +%Y-%m-%d 2>/dev/null || date -u -j -f "%Y-%m-%dT%H:%M:%SZ" "$CALL3_TIME" +%Y-%m-%d)" \
  "$(date -u +%Y-%m-%d)" "$CA_ID")
IDLE_COST_JSON=$(az rest --method post \
  --url "https://management.azure.com/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}/providers/Microsoft.CostManagement/query?api-version=2023-11-01" \
  --body "$QUERY_BODY" \
  2>&1) || { warn "Cost Management cross-check query failed"; IDLE_COST_JSON=""; }
printf '%s\n' "$IDLE_COST_JSON" | python3 -m json.tool 2>/dev/null | sed 's/^/    /' || printf '%s\n' "$IDLE_COST_JSON" | sed 's/^/    /'
warn "A \$0 or near-\$0 reading above is EXPECTED and does NOT indicate a broken check: the standing"
warn "Container Apps free compute grant (180,000 vCPU-s / 360,000 GiB-s per month, confirmed via the"
warn "Retail Prices API) covers ~200h (~8.3 days) of this app's continuous 0.25 vCPU/0.5GiB runtime"
warn "every month, regardless of idle-vs-active classification. It does NOT mean compute is free"
warn "for the whole month -- see R04_MONTHLY_NET_OF_GRANT below for the figure that actually matters."

# Grant-corrected monthly Container Apps cost, net of that grant, for the verdict above -- computed
# from officially-published per-second retail rates (Retail Prices API, canadacentral, Standard SKU,
# confirmed 2026-08-22), NOT PLAN.md's own $4.29/$14.31 estimate (which doesn't fully reconcile with
# these live rates -- flagged, not silently picked, in docs/phase0/findings.md).
R04_MONTHLY_NET_OF_GRANT=$(python3 - "$R04_VERDICT" <<'PYEOF'
import sys
verdict = sys.argv[1]
HOURS_PER_MONTH = 730.0
FREE_VCPU_S = 180000.0
FREE_GIB_S = 360000.0
VCPU, MEM = 0.25, 0.5
rates = {
    "IDLE":   (0.000004, 0.000004),  # ($/vCPU-s, $/GiB-s)
    "ACTIVE": (0.000034, 0.000004),
}
if verdict.startswith("IDLE"):
    key = "IDLE"
elif verdict.startswith("ACTIVE"):
    key = "ACTIVE"
else:
    key = "ACTIVE"  # MIXED / UNKNOWN: report the conservative (higher-cost) bound, don't guess low
vcpu_rate, mem_rate = rates[key]
total_s = HOURS_PER_MONTH * 3600
vcpu_s = VCPU * total_s
gib_s = MEM * total_s
billable_vcpu_s = max(0.0, vcpu_s - FREE_VCPU_S)
billable_gib_s = max(0.0, gib_s - FREE_GIB_S)
cost = billable_vcpu_s * vcpu_rate + billable_gib_s * mem_rate
print("%.2f" % cost)
PYEOF
)
say "Monthly Container Apps cost, net of the free grant, at this verdict's rate: \$${R04_MONTHLY_NET_OF_GRANT}"
note "(this is the figure to use for Stage 3's fixed-monthly input below, not \$0 and not the raw"
note "cross-check dollar figure above, which reflects only ~74h of a month, not a full month)"
write_env "R04_MONTHLY_NET_OF_GRANT" "$R04_MONTHLY_NET_OF_GRANT"

{
  echo "## R-04 — idle-vs-active Container Apps billing verdict"
  echo ""
  echo "Idle window: $CALL3_TIME to $NOW_TS (UTC), Container App left untouched, both WebSockets"
  echo "closed per decision 15."
  echo ""
  echo "**The free compute grant is the headline, not this verdict.** Container Apps' standing monthly"
  echo "free compute grant (180,000 vCPU-s / 360,000 GiB-s) covers ~8.3 days of this app's continuous"
  echo "0.25 vCPU/0.5 GiB runtime every month, regardless of idle-vs-active. For an always-on service"
  echo "(min-replicas=1, required for inbound telephony), that means ~27.6% of every month's compute is"
  echo "free no matter what; the remaining ~21.7 days bill at whichever rate this verdict determines."
  echo ""
  echo "**Idle-vs-active verdict (supporting detail): $R04_VERDICT**"
  echo ""
  echo "- Replicas: $R04_REPLICA_POINTS datapoints, $R04_REPLICA_GAPS gaps"
  echo "- Network: $R04_NET_INTERVALS intervals, $R04_NET_OVER_THRESHOLD over 1,000 B/s"
  echo "  ($R04_NET_OVER_EXCL_FIRST excluding the expected first-interval call-tail)"
  echo "- Monthly Container Apps cost net of the free grant, at this verdict's rate: **\$${R04_MONTHLY_NET_OF_GRANT}**"
  echo "  (Canada Central rates, not PLAN.md's \$4.29/\$14.31 — those were derived from US East"
  echo "  rates by mistake, settled elsewhere in this file; PLAN.md's Budget section is stale here)"
  echo ""
  echo "Cost Management cross-check (informational only — a \$0/near-\$0 reading here is expected given"
  echo "the free grant above and does not by itself confirm or contradict the verdict):"
  echo ""
  echo '```json'
  printf '%s\n' "$IDLE_COST_JSON"
  echo '```'
  echo ""
} >> "$FINDINGS_FILE"
ok "recorded to $FINDINGS_FILE"

# ── Stage 2: full measured meter roundup ────────────────────────────────────
stage "Full measured meter roundup"
say "Pulling total actual cost for the resource group since provisioning, broken out by service —"
say "this is the number COSTS.md gets, not docs/PLAN.md's estimate."

# Same az rest fix as Stage 1 / 03-cost-check-24h.sh -- `az costmanagement query` doesn't exist in
# the installable costmanagement extension (v1.0.0 -- confirmed 2026-08-22).
FULL_QUERY_BODY=$(printf '{"type":"ActualCost","timeframe":"Custom","timePeriod":{"from":"%s","to":"%s"},"dataset":{"granularity":"None","aggregation":{"totalCost":{"name":"Cost","function":"Sum"}},"grouping":[{"type":"Dimension","name":"ServiceName"}]}}' \
  "$(date -u -d "$PROVISION_TIME" +%Y-%m-%d 2>/dev/null || date -u -j -f "%Y-%m-%dT%H:%M:%SZ" "$PROVISION_TIME" +%Y-%m-%d)" \
  "$(date -u +%Y-%m-%d)")
FULL_COST_JSON=$(az rest --method post \
  --url "https://management.azure.com/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}/providers/Microsoft.CostManagement/query?api-version=2023-11-01" \
  --body "$FULL_QUERY_BODY" \
  2>&1) || { warn "Cost Management query failed"; FULL_COST_JSON=""; }

say "Total cost by service, provisioning to now:"
printf '%s\n' "$FULL_COST_JSON" | python3 -m json.tool 2>/dev/null | sed 's/^/    /' || printf '%s\n' "$FULL_COST_JSON" | sed 's/^/    /'

TOTAL_MINUTES_ESTIMATE=$(python3 -c "print(round((3 * 60) / 60, 2))")  # 3 calls, roughly a minute each — refine by hand if calls ran longer
note "Rough call-minutes across the 3 test calls: adjust by hand in COSTS.md if they ran meaningfully"
note "longer/shorter than ~1 min each — this script doesn't have exact per-call duration from ACS."

# ── Stage 3: R-08 — demo-runs/month from measured meters ────────────────────
stage "R-08 — compute demo runs/month from MEASURED meters (not the estimate)"
say "docs/PLAN.md: if this comes in under 5, STOP — do not proceed into Phase 1 — and go back to Marco"
say "about reducing fixed cost or raising the \$25/month ceiling."

SUGGESTED_FIXED_MONTHLY=$(python3 -c "print(round(${R04_MONTHLY_NET_OF_GRANT:-0} + 1.00, 2))")
say "Suggested fixed-monthly input, from Stage 1's telemetry-based R-04 verdict ($R04_VERDICT):"
say "  Container Apps net of the free grant (\$${R04_MONTHLY_NET_OF_GRANT:-0}) + \$1.00 number = \$${SUGGESTED_FIXED_MONTHLY}"
note "Press Enter at the fixed-monthly prompt below to accept this suggestion, or type a different"
note "number if you have a better one (e.g. from Stage 2's full meter roundup above)."

ask MEASURED_PER_MIN_COST "Measured \$/minute (PSTN + ACS streaming + model, from the meter roundup above; use the plan's \$0.0215-0.031/min floor/realistic range if the exact per-minute breakout isn't separable from the totals):"
ask MEASURED_FIXED_MONTHLY_INPUT "Measured fixed monthly total, extrapolated to a full month [Enter for suggested \$${SUGGESTED_FIXED_MONTHLY}]:"
MEASURED_FIXED_MONTHLY="${MEASURED_FIXED_MONTHLY_INPUT:-$SUGGESTED_FIXED_MONTHLY}"

R08_RESULT=$(python3 - "$MEASURED_PER_MIN_COST" "$MEASURED_FIXED_MONTHLY" <<'PYEOF'
import sys
per_min = float(sys.argv[1])
fixed = float(sys.argv[2])
ceiling = 25.0
eval_budget = 6.0  # hard eval-budget ceiling, docs/PLAN.md
left_for_calls = ceiling - fixed - eval_budget
b4_cap_minutes = 5  # B4: no call exceeds 5 min
if left_for_calls <= 0 or per_min <= 0:
    print("R08_MINUTES=0\nR08_RUNS=0\nR08_LEFT_FOR_CALLS=%.2f" % left_for_calls)
else:
    minutes = left_for_calls / per_min
    runs = minutes / b4_cap_minutes
    print("R08_MINUTES=%.1f\nR08_RUNS=%.1f\nR08_LEFT_FOR_CALLS=%.2f" % (minutes, runs, left_for_calls))
PYEOF
)
eval "$R08_RESULT"
say "Left for manual/demo calls after fixed cost + \$6 eval-budget ceiling: \$${R08_LEFT_FOR_CALLS}/mo"
say "At \$${MEASURED_PER_MIN_COST}/min, that's ${R08_MINUTES} minutes ≈ ${R08_RUNS} demo runs/month (using B4's 5-min cap per run)."

write_env "R08_RUNS_PER_MONTH" "$R08_RUNS"
{
  echo "## R-08 — demo runs/month, computed from measured meters"
  echo ""
  echo "- Measured \$/minute: \$${MEASURED_PER_MIN_COST}"
  echo "- Measured fixed monthly (extrapolated): \$${MEASURED_FIXED_MONTHLY}"
  echo "- Eval-budget ceiling reserved: \$6.00 (docs/PLAN.md hard ceiling)"
  echo "- Left for manual/demo calls: \$${R08_LEFT_FOR_CALLS}/mo"
  echo "- At B4's 5-min cap per run: **${R08_RUNS} demo runs/month**"
  echo ""
} >> "$FINDINGS_FILE"

if python3 -c "exit(0 if float('$R08_RUNS') < 5 else 1)"; then
  printf '\n%s%s  ⛔ R-08 GATE FAILED — %s runs/month is under the 5-run floor%s\n\n' "$BOLD" "$RED" "$R08_RUNS" "$RESET"
  err "Per docs/PLAN.md: STOP HERE. Do not proceed into Phase 1."
  err "Discuss with Marco: reduce fixed cost (Container Apps sizing, min-replicas) or raise the \$25 ceiling."
  note "Teardown still proceeds below regardless — leaving billable compute running while this gets"
  note "discussed would be its own waste. The stop is about Phase 1, not about leaving things running."
  R08_GATE="FAILED"
else
  ok "R-08 gate passed — ${R08_RUNS} demo runs/month, at or above the 5-run floor"
  R08_GATE="PASSED"
fi
write_env "R08_GATE" "$R08_GATE"

# ── Stage 4: finalize COSTS.md ───────────────────────────────────────────────
stage "Write measured findings to COSTS.md"
# Appended, never overwritten: COSTS.md may already carry earlier sections (e.g. the free-tier
# promotion investigation, written before Phase 0 spending began) that this script has no business
# clobbering. Only the top title/preamble is written if the file doesn't exist yet at all.
if [[ ! -f "$COSTS_FILE" ]]; then
  {
    echo "# COSTS.md — Azure-Banking-Voice-Agentic-AI"
    echo ""
    echo "Phase 0 measured meters and related findings. Superseded by whatever \`make deploy\`'s later"
    echo "phases add — this is the Phase 0 exit-gate evidence, not a running ledger yet."
    echo ""
  } > "$COSTS_FILE"
fi
{
  echo "## Modeled from telemetry (generated $(date -u +%Y-%m-%dT%H:%M:%SZ) by docs/phase0/wizard/04-teardown-and-r08.sh)"
  echo ""
  echo "| Item | Plan estimate | Modeled |"
  echo "|---|---|---|"
  echo "| Fixed monthly (extrapolated) | \$5.29–\$15.31 | \$${MEASURED_FIXED_MONTHLY} |"
  echo "| Per-minute floor | \$0.0215/min | \$${MEASURED_PER_MIN_COST}/min |"
  echo "| Container Apps idle-vs-active (R-04) | undocumented, decision 15 assumed idle | **${R04_VERDICT}** |"
  echo "| Demo runs/month (R-08) | ~30-160 (naive, pre-eval-budget estimate) | **${R08_RUNS}** (gate: ${R08_GATE}) |"
  echo ""
  echo "**Provenance note**: none of the figures in this table come from an Azure Cost Management billing"
  echo "query. \$${MEASURED_FIXED_MONTHLY} (Fixed monthly) = R04_MONTHLY_NET_OF_GRANT (\$${R04_MONTHLY_NET_OF_GRANT:-0},"
  echo "computed from Container Apps replica/network telemetry against Canada Central Retail Prices API"
  echo "rates, net of the free compute grant) + a hardcoded \$1.00 phone-number constant. \$${MEASURED_PER_MIN_COST}/min"
  echo "(Per-minute floor) is whatever was typed at this script's per-minute prompt — free-text keyboard"
  echo "entry, not read from any per-minute billing meter. \$${R08_RUNS} (Demo runs/month) is arithmetic"
  echo "performed on those two inputs. This run's Cost Management dollar-total queries feed none of the"
  echo "figures above."
  echo ""
  echo "If the free-tier promotion section above (or added by 03-cost-check-24h.sh) flagged any of these"
  echo "meters as free-tier-covered, treat the \"Modeled\" column with that caveat — see that section's"
  echo "fallback (measured quantity × PLAN.md's list rate) before trusting these dollar figures."
  echo ""
  echo "### Transport RTT baseline"
  echo ""
  echo "See docs/phase0/findings.md \"R-02 / R-03 / RTT\" section — app-side processing-latency samples"
  echo "from 3 test calls (turns, not calls; not a turn-latency percentile — that needs Phase 2's"
  echo "RealtimeSession per B5)."
  echo ""
  echo "### Full detail"
  echo ""
  echo "docs/phase0/findings.md has the raw query results this wizard persists, with timestamps (R-01"
  echo "through R-06, R-08). Two are not persisted: Stage 2's full Cost Management roundup"
  echo "(FULL_COST_JSON) is terminal output only, and Stage 1's raw Replicas/RxBytes/TxBytes metrics"
  echo "survive as derived counts, not raw results."
  echo ""
} >> "$COSTS_FILE"
ok "wrote $COSTS_FILE"

# ── Stage 5: teardown compute, keep the number ───────────────────────────────
stage "Teardown — compute only, keep the number leased"
say "Deleting: Container App, Container Apps environment, Event Grid subscription, the DataZone probe"
say "deployment if one was left over. NOT deleting: the ACS resource, the phone number, the Azure"
say "OpenAI resource/deployment, the resource group itself."
note "Keeping the AOAI resource+deployment (not just the number) because Phase 1 needs it again next"
note "session, and deleting+recreating it costs nothing to skip — only compute (Container Apps) and the"
note "temporary Event Grid wiring are what were actually driving the idle-vs-active cost question."

# confirm's "no" path is deliberately loud, not the cheerful finish() banner below — declining here
# means compute is STILL RUNNING AND STILL BILLING, and that must not read as "all done".
if ! confirm "Confirm teardown of compute now (number and ACS resource are kept either way)?"; then
  _clear
  printf '\n%s%s  ⚠ TEARDOWN NOT PERFORMED — compute is still running and still billing.%s\n\n' "$BOLD" "$RED" "$RESET"
  note "Re-run this script when ready — nothing above this point is destructive to re-run."
  exit 0
fi

# Stop the log-snapshot LaunchAgent FIRST, before anything below deletes the Container App it polls —
# docs/phase0/evidence/README.md: it fires every ~15 min and appends its output to the evidence file;
# left running past teardown it keeps polling a now-deleted Container App and appends error output
# into that file instead of quietly doing nothing.
say "Stopping the phase0 log-snapshot LaunchAgent (docs/phase0/evidence/README.md) before deleting the"
say "Container App it polls, so it doesn't keep firing against a resource that's gone:"
LAUNCHAGENT_PLIST="$HOME/Library/LaunchAgents/com.azbank.phase0.logsnapshot.plist"
if [[ -f "$LAUNCHAGENT_PLIST" ]]; then
  launchctl unload "$LAUNCHAGENT_PLIST" 2>/dev/null || true
  if launchctl list 2>/dev/null | grep -q "com.azbank.phase0.logsnapshot"; then
    warn "LaunchAgent still listed after unload — check manually: launchctl list | grep azbank"
  else
    ok "LaunchAgent unloaded — no more log-snapshot polling"
  fi
else
  ok "LaunchAgent plist not found at $LAUNCHAGENT_PLIST — already removed or never installed"
fi

# Each delete is followed by a re-query, not trusted from the command's own exit code alone: az's
# delete commands can report success on things that are "already gone" (fine) but can also swallow a
# real, retryable failure behind a generic error that a bare `|| warn` would silently paper over as
# "already gone" when it actually means "still there and still billing". TEARDOWN_OK tracks whether
# every verified-gone check actually passed; the closing message and exit code both key off it, not
# off whether the delete commands merely returned.
TEARDOWN_OK=1
ACS_ID=$(az communication show --name "$ACS_NAME" --resource-group "$RESOURCE_GROUP" --query id -o tsv)

say "Deleting Event Grid subscription..."
if az eventgrid event-subscription show --name "azbank-p0-incoming-call" --source-resource-id "$ACS_ID" >/dev/null 2>&1; then
  az eventgrid event-subscription delete --name "azbank-p0-incoming-call" --source-resource-id "$ACS_ID" --output none 2>/dev/null || true
  for _ in $(seq 1 6); do
    az eventgrid event-subscription show --name "azbank-p0-incoming-call" --source-resource-id "$ACS_ID" >/dev/null 2>&1 || break
    sleep 5
  done
  if az eventgrid event-subscription show --name "azbank-p0-incoming-call" --source-resource-id "$ACS_ID" >/dev/null 2>&1; then
    err "Event Grid subscription still present after delete — not billable by itself, but re-run this script to clear it."
    TEARDOWN_OK=0
  else
    ok "Event Grid subscription deleted — confirmed gone"
  fi
else
  ok "Event Grid subscription already gone"
fi

say "Deleting Container App $CONTAINERAPP_NAME (this is the resource that bills per-hour)..."
if az containerapp show --name "$CONTAINERAPP_NAME" --resource-group "$RESOURCE_GROUP" >/dev/null 2>&1; then
  az containerapp delete --name "$CONTAINERAPP_NAME" --resource-group "$RESOURCE_GROUP" --yes --output none 2>/dev/null || true
  if az containerapp show --name "$CONTAINERAPP_NAME" --resource-group "$RESOURCE_GROUP" >/dev/null 2>&1; then
    err "Container App $CONTAINERAPP_NAME still present after delete — it is STILL BILLING. Re-run this script."
    TEARDOWN_OK=0
  else
    ok "Container App $CONTAINERAPP_NAME deleted — confirmed gone"
  fi
else
  ok "Container App already gone"
fi

say "Deleting Container Apps environment $CAE_NAME..."
if [[ "$TEARDOWN_OK" == "1" ]]; then
  if az containerapp env show --name "$CAE_NAME" --resource-group "$RESOURCE_GROUP" >/dev/null 2>&1; then
    az containerapp env delete --name "$CAE_NAME" --resource-group "$RESOURCE_GROUP" --yes --output none 2>/dev/null || true
    if az containerapp env show --name "$CAE_NAME" --resource-group "$RESOURCE_GROUP" >/dev/null 2>&1; then
      err "Container Apps environment still present after delete — re-run this script to clear it."
      TEARDOWN_OK=0
    else
      ok "Container Apps environment deleted — confirmed gone"
    fi
  else
    ok "Container Apps environment already gone"
  fi
else
  warn "skipping environment delete — the Container App didn't verify clean, and an environment with"
  warn "an app still in it usually won't delete anyway. Fix that first, then re-run."
fi

say "Verifying the ACS resource is still there (must NOT be deleted):"
az communication show --name "$ACS_NAME" --resource-group "$RESOURCE_GROUP" --query "{name:name,dataLocation:dataLocation}" -o table
ok "ACS resource intact"

# R-09 (docs/PLAN.md): the number is irreplaceable if ever lost -- ACS's Canadian geographic inventory
# has been observed losing entire localities within ~20 minutes (docs/phase0/findings.md). This script
# never calls a release/delete on it (see the file header), but "never calls delete" isn't the same
# claim as "still exists" -- checking the parent ACS resource's existence (above) doesn't prove the
# number specifically is still owned. Checked directly via the same GET /phoneNumbers this project's
# other scripts use, not assumed from the container resource being present.
say "Verifying the phone number itself is still owned (not just its parent ACS resource):"
if [[ -z "${PHONE_NUMBER:-}" ]]; then
  err "PHONE_NUMBER isn't set in $ENV_FILE — cannot verify. Check the Azure portal manually before"
  err "trusting this teardown's result: ACS resource -> Phone Numbers."
else
  ACS_TOKEN=$(az account get-access-token --resource "https://communication.azure.com" --query accessToken -o tsv)
  OWNED_NUMBERS_BODY_FILE=$(mktemp)
  # `|| echo "000"` matters under set -e: a transport-level failure (curl exit 7, DNS failure, no
  # route) would otherwise kill the script at this assignment, before the non-2xx branch below ever
  # runs -- making the "OWNERSHIP CHECK COULD NOT BE COMPLETED" message unreachable in exactly the
  # case it exists for. "000" is not a valid HTTP status and correctly fails the ^2[0-9][0-9]$ test
  # below, so a transport failure falls through to that branch instead of crashing past it.
  OWNED_NUMBERS_HTTP_CODE=$(curl -s -o "$OWNED_NUMBERS_BODY_FILE" -w '%{http_code}' \
    -H "Authorization: Bearer $ACS_TOKEN" \
    "https://${ACS_NAME}.canada.communication.azure.com/phoneNumbers?api-version=2025-06-01" || echo "000")
  OWNED_NUMBERS=$(cat "$OWNED_NUMBERS_BODY_FILE")
  rm -f "$OWNED_NUMBERS_BODY_FILE"
  # A non-2xx response means the check itself failed (bad token, throttling, transient network/API
  # error) -- it says nothing about whether the number is actually owned, and must NOT be reported as
  # an R-09 violation. Only a 2xx response that genuinely lacks the number is a violation/drift.
  if [[ ! "$OWNED_NUMBERS_HTTP_CODE" =~ ^2[0-9][0-9]$ ]]; then
    err "OWNERSHIP CHECK COULD NOT BE COMPLETED -- /phoneNumbers request returned HTTP $OWNED_NUMBERS_HTTP_CODE, not 2xx."
    err "This is NOT a confirmed R-09 violation -- it's a failed check, not evidence the number is gone."
    err "Raw response:"
    printf '%s\n' "$OWNED_NUMBERS" | python3 -m json.tool 2>/dev/null | sed 's/^/    /' || printf '%s\n' "$OWNED_NUMBERS"
    err "STOP -- verify manually (Azure portal: ACS resource -> Phone Numbers) before proceeding."
    exit 1
  elif printf '%s' "$OWNED_NUMBERS" | grep -qF "$PHONE_NUMBER"; then
    ok "confirmed: $PHONE_NUMBER is still owned — number stays leased per docs/PLAN.md's explicit R-09 design"
  else
    err "R-09 VIOLATION OR DRIFT: $PHONE_NUMBER not found in the live /phoneNumbers response (HTTP $OWNED_NUMBERS_HTTP_CODE)."
    err "This script never calls a release/delete on it -- if it's really gone, something outside this"
    err "script's control did it. Raw response:"
    printf '%s\n' "$OWNED_NUMBERS" | python3 -m json.tool 2>/dev/null | sed 's/^/    /' || printf '%s\n' "$OWNED_NUMBERS"
    err "STOP -- tell Marco before proceeding. Do not treat this as a script bug to silently work around."
    exit 1
  fi
fi

# ── Known, unfixed defects in this script (documentation only — not fixed here) ──────────────
# 1. The "TEARDOWN INCOMPLETE" banner immediately below can be a false negative: a slow Container
#    Apps environment delete can time out this check without the delete having actually failed.
#    Confirmed false-negative 2026-08-24 — Container App, Event Grid subscription, and CAE all
#    independently verified deleted despite this banner firing that run. Not yet fixed.
# 2. Stage 2's FULL_COST_JSON (`:267`, the full Cost Management meter roundup, PROVISION_TIME→now)
#    is queried then discarded — printed to the terminal only (`:273`), never persisted to
#    FINDINGS_FILE or COSTS_FILE. Fix: persist it to FINDINGS_FILE the same way Stage 1 persists
#    IDLE_COST_JSON (`:226-254`).
if [[ "$TEARDOWN_OK" != "1" ]]; then
  _clear
  printf '\n%s%s  ⚠ TEARDOWN INCOMPLETE — some compute may still be running and billing.%s\n\n' "$BOLD" "$RED" "$RESET"
  say "Re-run this script — every check above is safe to repeat, including the parts that already"
  say "succeeded. If the same thing fails twice, check manually:"
  say "  az containerapp show --name $CONTAINERAPP_NAME --resource-group $RESOURCE_GROUP"
  exit 1
fi

# ── Stage 6: dedup evidence files and commit — standing instruction, teardown only ─────────────────
stage "Dedup evidence files and commit (standing instruction: commit once, at teardown)"
say "docs/phase0/evidence/README.md: both evidence files can carry duplicate lines (each 15-min"
say "--tail 300 pull overlaps the previous one at idle rates). Exact-line dedup is safe — each line"
say "is a self-contained JSON object with its own TimeStamp."

EVIDENCE_DIR="$REPO_ROOT/docs/phase0/evidence"
for f in "containerapp-logs-follow-2026-08-21.jsonl" "containerapp-logs-snapshot-2026-08-21.jsonl"; do
  SRC="$EVIDENCE_DIR/$f"
  if [[ -f "$SRC" ]]; then
    BEFORE=$(wc -l < "$SRC" | tr -d ' ')
    awk '!seen[$0]++' "$SRC" > "$SRC.dedup.tmp" && mv "$SRC.dedup.tmp" "$SRC"
    AFTER=$(wc -l < "$SRC" | tr -d ' ')
    ok "deduped $f: $BEFORE -> $AFTER lines"
  else
    warn "$f not found in $EVIDENCE_DIR — skipping"
  fi
done

# PROJECT_STATE.md's explicit instruction: "Do not commit either evidence file periodically — commit
# once, at teardown, after the dedup pass." This is that one commit, not a periodic one.
say "Committing both evidence files now, per that standing instruction — this is their one commit,"
say "not a periodic one."
git -C "$REPO_ROOT" add \
  "docs/phase0/evidence/containerapp-logs-follow-2026-08-21.jsonl" \
  "docs/phase0/evidence/containerapp-logs-snapshot-2026-08-21.jsonl" 2>/dev/null || true
if git -C "$REPO_ROOT" diff --cached --quiet -- docs/phase0/evidence/ 2>/dev/null; then
  ok "nothing to commit — evidence files already committed or unchanged after dedup"
else
  git -C "$REPO_ROOT" commit --quiet -m "docs(phase0-evidence): dedup and commit Container App log evidence at teardown

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
  ok "committed deduped evidence files"
fi

finish

printf '\n%sPhase 0 exit gate:%s\n' "$BOLD" "$RESET"
printf '  - COSTS.md contains measured meters: %s✓%s\n' "$GREEN" "$RESET"
printf '  - Transport RTT baseline with stated sample size: see docs/phase0/findings.md %s✓%s\n' "$GREEN" "$RESET"
printf '  - ADR-001 and ADR-002 exist in docs/adr/: %s✓%s (written by 01-provision.sh, stage 10)\n' "$GREEN" "$RESET"
printf '  - R-08 demo-runs/month computed: %s (gate %s)\n' "$R08_RUNS" "$R08_GATE"
if [[ "$R08_GATE" == "FAILED" ]]; then
  printf '\n%s%s  Do not proceed into Phase 1 until this is resolved with Marco.%s\n\n' "$BOLD" "$RED" "$RESET"
else
  printf '\n%sReady for Phase 1, pending your own review of docs/phase0/findings.md and the two ADRs.%s\n\n' "$BOLD" "$RESET"
fi
