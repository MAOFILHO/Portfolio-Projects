#!/usr/bin/env bash
#
# Phase 0 wizard, script 3 of 4 — 24h Cost Analysis check.
#
# WHAT ONLY YOU CAN DO HERE: wait. Azure Cost Analysis has a real ingestion lag — running this less
# than ~24h after 02-test-calls.sh will likely show incomplete or zero data. Everything else here
# (querying Cost Management, comparing against docs/PLAN.md's estimate) is automated.

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
step() { printf '  %s•%s %s\n' "$BLUE" "$RESET" "$1"; }
note() { printf '  %s%s%s\n' "$DIM" "$1" "$RESET"; }
warn() { printf '  %s⚠ %s%s\n' "$YELLOW" "$1" "$RESET"; }
ok()   { printf '  %s✓ %s%s\n' "$GREEN" "$1" "$RESET"; }
pause() { printf '  %s%s%s ' "$DIM" "${1:-Press Enter to continue}" "$RESET"; read -r _ || true; }
open_url() {
  local url="$1"
  printf '  %s↗ opening%s %s\n' "$GREEN" "$RESET" "$url"
  { if   command -v wslview     >/dev/null 2>&1; then wslview "$url"
    elif command -v explorer.exe >/dev/null 2>&1; then explorer.exe "$url"
    elif command -v xdg-open    >/dev/null 2>&1; then xdg-open "$url"
    elif command -v open        >/dev/null 2>&1; then open "$url"
    else warn "couldn't open a browser — visit it manually: $url"; fi
  } >/dev/null 2>&1 || warn "couldn't open a browser — visit it manually: $url"
}
confirm() { local reply=""; printf '  %s? %s [y/N] ' "$YELLOW" "$1"; read -r reply || true; [[ "$reply" =~ ^[Yy] ]]; }
# Three-way prompt for the free-tier portal check. Sets FREETIER_CLEAN directly as a real shell
# variable (to "yes" / "no" / "unknown") -- NOT only via write_env, which only persists to
# $ENV_FILE and does not populate the running process's variable. Same shape as the DATAZONE_OK
# bug in 01-provision.sh: a value that's only ever written to the env file is unbound under
# `set -u` for the rest of *this* run, and crashes the first time something reads it directly.
ask_freetier_state() {
  local reply=""
  while true; do
    printf '  %s? Free-tier coverage check%s — was the portal check performed, and what did it show?\n' "$YELLOW" "$RESET"
    printf '      [c] clean       — confirmed: none of ACS / Azure OpenAI / Container Apps are covered\n'
    printf '      [v] covered     — confirmed: at least one of them IS free-tier-covered\n'
    printf '      [u] unverifiable — could not perform the check at all (e.g. blade broken/404)\n'
    printf '  > '
    read -r reply || reply=""
    case "$reply" in
      [Cc]*) FREETIER_CLEAN="yes"; return 0 ;;
      [Vv]*) FREETIER_CLEAN="no"; return 0 ;;
      [Uu]*) FREETIER_CLEAN="unknown"; return 0 ;;
      *) printf '  %splease answer c, v, or u%s\n' "$YELLOW" "$RESET" ;;
    esac
  done
}
write_env() { local key="$1" value="$2" tmp; touch "$ENV_FILE"; tmp=$(mktemp); grep -vE "^${key}=" "$ENV_FILE" > "$tmp" || true; printf '%s=%s\n' "$key" "$value" >> "$tmp"; mv "$tmp" "$ENV_FILE"; WRITTEN_ENV+=("$key"); printf '  %s✓ wrote%s %s → %s\n' "$GREEN" "$RESET" "$key" "$ENV_FILE"; }
finish() { _clear; printf '\n%s%s  ✓ Script complete%s\n' "$BOLD" "$GREEN" "$RESET"; (( ${#WRITTEN_ENV[@]} )) && note "wrote ${#WRITTEN_ENV[@]} value(s) to $ENV_FILE: ${WRITTEN_ENV[*]}"; printf '\n'; }

if [[ ! -f "$ENV_FILE" ]]; then
  printf 'No %s found — run 01-provision.sh (and 02-test-calls.sh) first.\n' "$ENV_FILE"
  exit 1
fi
# shellcheck source=/dev/null
set -a; source "$ENV_FILE"; set +a

FINDINGS_FILE="$SCRIPT_DIR/../findings.md"
COSTS_FILE="$(cd "$SCRIPT_DIR/../../.." && pwd)/COSTS.md"

TOTAL_STAGES=3
banner "Azure-Banking-Voice-Agentic-AI — Phase 0, script 3/4: 24h Cost Analysis check"

if [[ -z "${CALL3_TIME:-}" ]]; then
  warn "CALL3_TIME isn't in $ENV_FILE — did 02-test-calls.sh run? Continuing anyway."
else
  ELAPSED_H=$(( ( $(date -u +%s) - $(date -u -d "$CALL3_TIME" +%s 2>/dev/null || date -u -j -f "%Y-%m-%dT%H:%M:%SZ" "$CALL3_TIME" +%s) ) / 3600 ))
  if (( ELAPSED_H < 24 )); then
    warn "only ~${ELAPSED_H}h since the last test call — Cost Analysis may be incomplete this early."
    confirm "Run anyway?" || { note "come back later — re-run this script, nothing here is destructive."; exit 0; }
  else
    ok "~${ELAPSED_H}h elapsed since the last test call"
  fi
fi

# ── Stage 1: Free Services portal check — human-only, no public API exists ──
stage "Confirm none of this project's resources are free-tier-covered"
say "COSTS.md's \"Free-tier promotion\" section: this subscription has an active freetier promotion"
say "until 2027-02-28. If any of ACS, Azure OpenAI, or Container Apps are covered by it, Cost"
say "Management won't discount their cost — it OMITS unbilled usage entirely (Microsoft's own docs,"
say "quoted in COSTS.md), so the numbers below could read as \$0 or low for a reason that has nothing"
say "to do with the real rate. This is portal-only — no documented REST API exposes it, so it can't"
say "be scripted; this is a genuine human-only check, not laziness."
# The old direct blade (#view/Microsoft_Azure_GTM/ModernFreeServicesBlade) 404s --
# "ErrorLoadingExtensionAndDefinition", confirmed retired 2026-08-22, not a transient glitch. Current
# Microsoft doc (https://learn.microsoft.com/en-us/azure/cost-management-billing/manage/check-free-service-usage)
# no longer references that blade at all. Opening the Subscriptions list instead -- a stable,
# well-known blade ID -- rather than guessing at an unverified direct deep-link to the Overview page's
# "Top free services by usage" tile itself.
open_url "https://portal.azure.com/#view/Microsoft_Azure_Billing/SubscriptionsBlade"
step "Select this subscription, then on its Overview page find the \"Top free services by usage\""
step "tile and click \"View all free services\" -- this opens the \"Free services for 12 months\""
step "table. Confirmed 2026-08-22 that this table DOES show up for this PayAsYouGo subscription"
step "(the doc's \"only for Free-Account subscriptions\" caveat did not gate it out here)."
step "Look for Azure Communication Services, Azure OpenAI / Cognitive Services, or Container Apps"
step "anywhere in that table with a status other than \"Not in use\". Note the meter name if so."
ask_freetier_state
case "$FREETIER_CLEAN" in
  yes)
    ok "confirmed clean — Cost Analysis numbers below can be trusted at face value"
    ;;
  no)
    warn "at least one is covered — the dollar figures below are NOT reliable for that meter."
    warn "Use the fallback in COSTS.md: measured usage quantity × PLAN.md's list rate, not this"
    warn "script's dollar total, for whichever meter you found covered."
    ;;
  unknown)
    warn "could not verify — the portal check itself did not run (blade unreachable/broken)."
    warn "This is NOT the same as \"clean\": an absent/suppressed meter below is indistinguishable"
    warn "from free-tier coverage until this check can actually run. Treat the numbers with the"
    warn "same suspicion as the \"covered\" case, not as reassurance."
    ;;
esac
write_env "FREETIER_CLEAN" "$FREETIER_CLEAN"
{
  echo ""
  echo "## Free Services portal check (Stage 1, 03-cost-check-24h.sh, $(date -u +%Y-%m-%dT%H:%M:%SZ))"
  echo ""
  case "$FREETIER_CLEAN" in
    yes)     echo "Confirmed clean (no ACS/Azure OpenAI/Container Apps free-tier coverage): yes" ;;
    no)      echo "Confirmed clean (no ACS/Azure OpenAI/Container Apps free-tier coverage): no — at least one resource is free-tier-covered" ;;
    unknown) echo "Confirmed clean (no ACS/Azure OpenAI/Container Apps free-tier coverage): could-not-verify — the Free Services blade could not be checked" ;;
  esac
  echo ""
} >> "$COSTS_FILE"

# ── Stage 2: query Cost Management ──────────────────────────────────────────
stage "Query actual Cost Analysis for the resource group"
say "Reading real per-service cost for $RESOURCE_GROUP since provisioning — not the plan's estimate."

TODAY=$(date -u +%Y-%m-%d)
START=$(date -u -d '3 days ago' +%Y-%m-%d 2>/dev/null || date -u -v-3d +%Y-%m-%d)

# `az costmanagement query` (the CLI subcommand) does not exist in the currently-installable
# `costmanagement` extension (v1.0.0 ships only `export` and `show-operation-result` -- confirmed
# 2026-08-22, `az costmanagement -h`). That command always failed here, silently, into the "no cost
# data yet" branch below -- indistinguishable from real ingestion lag but actually a CLI/extension
# mismatch. Calling the same Cost Management Query REST API directly via `az rest` instead, which
# needs no extension and is confirmed working against this subscription.
QUERY_BODY=$(printf '{"type":"ActualCost","timeframe":"Custom","timePeriod":{"from":"%s","to":"%s"},"dataset":{"granularity":"Daily","aggregation":{"totalCost":{"name":"Cost","function":"Sum"}},"grouping":[{"type":"Dimension","name":"ServiceName"}]}}' "$START" "$TODAY")
COST_JSON=$(az rest --method post \
  --url "https://management.azure.com/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}/providers/Microsoft.CostManagement/query?api-version=2023-11-01" \
  --body "$QUERY_BODY" \
  2>&1) || { warn "Cost Management query failed — Cost Analysis can lag >24h for very new resource groups."; COST_JSON=""; }

if [[ -n "$COST_JSON" ]]; then
  say "Raw per-service daily cost, $START to $TODAY:"
  printf '%s\n' "$COST_JSON" | python3 -m json.tool 2>/dev/null | sed 's/^/    /' | head -60 || printf '%s\n' "$COST_JSON" | sed 's/^/    /'
  {
    echo "## Interim Cost Analysis check (+24h)"
    echo ""
    echo "Queried $(date -u +%Y-%m-%dT%H:%M:%SZ) for $START..$TODAY."
    echo '```json'
    printf '%s\n' "$COST_JSON"
    echo '```'
    echo ""
  } >> "$FINDINGS_FILE"
  ok "recorded to $FINDINGS_FILE"
else
  warn "no cost data yet — this is informational only; script 4 (+72h) is the one the exit gate"
  warn "actually depends on, so a gap here isn't blocking."
fi

# ── Stage 3: sanity-check against the plan's estimate ───────────────────────
stage "Compare against docs/PLAN.md's estimate"
say "Plan's per-minute floor: \$0.0215/min (PSTN \$0.0085 + ACS streaming \$0.004 + model \$0.009)."
say "Plan's fixed monthly subtotal: \$5.29 (idle) to \$15.31 (active) Container Apps + \$1.00 number."
note "This is a sanity check, not the final verdict — R-04 (idle-vs-active Container Apps billing) and"
note "R-08 (demo-runs/month) both need the fuller 72h window script 4 observes. Don't treat a mismatch"
note "here as final; do treat a WILDLY off number (10x+) as worth investigating before script 4."
case "${FREETIER_CLEAN:-unknown}" in
  no)
    warn "Stage 1 flagged free-tier coverage — a number reading as much LOWER than the estimate (not"
    warn "higher) is exactly the suppression pattern to expect, not reassurance that costs are low."
    ;;
  unknown)
    warn "Stage 1 could not verify free-tier coverage at all — a number reading much LOWER than the"
    warn "estimate is exactly what unverified/suppressed coverage would also look like. Don't read a"
    warn "low number here as reassurance; it's as consistent with \"we don't know\" as with \"it's clean\"."
    ;;
esac

if confirm "Does the actual cost so far look roughly in line with the estimate above (not 10x+ off)?"; then
  ok "sanity check passed — recorded"
  write_env "COST_SANITY_CHECK" "pass"
else
  warn "flagged as off — worth digging into which meter before the 72h window closes, since script 4's"
  warn "R-08 computation inherits whatever's actually being billed."
  write_env "COST_SANITY_CHECK" "flagged"
fi

finish
printf '\n%sNext:%s once ~72h have passed since 01-provision.sh created the Container App, run %s04-teardown-and-r08.sh%s.\n\n' \
  "$BOLD" "$RESET" "$BLUE" "$RESET"
