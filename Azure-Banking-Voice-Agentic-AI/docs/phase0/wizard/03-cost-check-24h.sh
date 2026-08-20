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
open_url "https://portal.azure.com/#view/Microsoft_Azure_GTM/ModernFreeServicesBlade"
step "Look for Azure Communication Services, Azure OpenAI / Cognitive Services, or Container Apps"
step "anywhere in the free-tier-covered list. Note the resource name if you see any of them."
if confirm "Confirmed: none of ACS / Azure OpenAI / Container Apps appear as free-tier-covered?"; then
  ok "confirmed clean — Cost Analysis numbers below can be trusted at face value"
  write_env "FREETIER_CLEAN" "yes"
else
  warn "at least one is covered — the dollar figures below are NOT reliable for that meter."
  warn "Use the fallback in COSTS.md: measured usage quantity × PLAN.md's list rate, not this"
  warn "script's dollar total, for whichever meter you found covered."
  write_env "FREETIER_CLEAN" "no"
fi
{
  echo ""
  echo "## Free Services portal check (Stage 1, 03-cost-check-24h.sh, $(date -u +%Y-%m-%dT%H:%M:%SZ))"
  echo ""
  echo "Confirmed clean (no ACS/Azure OpenAI/Container Apps free-tier coverage): ${FREETIER_CLEAN}"
  echo ""
} >> "$COSTS_FILE"

# ── Stage 2: query Cost Management ──────────────────────────────────────────
stage "Query actual Cost Analysis for the resource group"
say "Reading real per-service cost for $RESOURCE_GROUP since provisioning — not the plan's estimate."

TODAY=$(date -u +%Y-%m-%d)
START=$(date -u -d '3 days ago' +%Y-%m-%d 2>/dev/null || date -u -v-3d +%Y-%m-%d)

COST_JSON=$(az costmanagement query \
  --type ActualCost \
  --timeframe Custom \
  --time-period from="${START}" to="${TODAY}" \
  --dataset-granularity Daily \
  --dataset-aggregation '{"totalCost":{"name":"Cost","function":"Sum"}}' \
  --dataset-grouping name=ServiceName type=Dimension \
  --scope "/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}" \
  2>&1) || { warn "costmanagement query failed — Cost Analysis can lag >24h for very new resource groups."; COST_JSON=""; }

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
if [[ "${FREETIER_CLEAN:-yes}" == "no" ]]; then
  warn "Stage 1 flagged free-tier coverage — a number reading as much LOWER than the estimate (not"
  warn "higher) is exactly the suppression pattern to expect, not reassurance that costs are low."
fi

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
