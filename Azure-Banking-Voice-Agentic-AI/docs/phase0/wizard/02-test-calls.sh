#!/usr/bin/env bash
#
# Phase 0 wizard, script 2 of 4 — Test calls.
# Run this today, right after 01-provision.sh succeeds.
#
# WHAT ONLY YOU CAN DO HERE: dial a real phone number from your mobile, three times. Nothing in this
# script can do that for you. Everything else (pulling logs, extracting the meter/latency/DTMF
# evidence afterward) is automated.

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
banner() {
  _clear
  printf '\n%s%s  %s%s\n' "$BOLD" "$BLUE" "$1" "$RESET"
  printf '%s  %s stages%s\n\n' "$DIM" "$TOTAL_STAGES" "$RESET"
  pause "Ready to start?"
}
stage() { _clear; _STAGE_INDEX=$((_STAGE_INDEX + 1)); printf '\n%s%s▸ Stage %s/%s · %s%s\n' "$BOLD" "$BLUE" "$_STAGE_INDEX" "$TOTAL_STAGES" "$1" "$RESET"; }
say()  { printf '  %s\n' "$1"; }
step() { printf '  %s•%s %s\n' "$BLUE" "$RESET" "$1"; }
note() { printf '  %s%s%s\n' "$DIM" "$1" "$RESET"; }
warn() { printf '  %s⚠ %s%s\n' "$YELLOW" "$1" "$RESET"; }
ok()   { printf '  %s✓ %s%s\n' "$GREEN" "$1" "$RESET"; }
pause() { printf '  %s%s%s ' "$DIM" "${1:-Press Enter to continue}" "$RESET"; read -r _ || true; }
confirm() { local reply=""; printf '  %s? %s [y/N] ' "$YELLOW" "$1"; read -r reply || true; [[ "$reply" =~ ^[Yy] ]]; }
_existing() { [[ -f "$ENV_FILE" ]] || return 1; local line; line=$(grep -E "^${1}=" "$ENV_FILE" | tail -n1) || return 1; printf '%s' "${line#*=}"; }
ask() { local key="$1" prompt="$2" current input; current=$(_existing "$key" || true); if [[ -n "$current" ]]; then printf '  %s%s%s %s[Enter keeps current: %s]%s ' "$BOLD" "$prompt" "$RESET" "$DIM" "$current" "$RESET"; else printf '  %s%s%s ' "$BOLD" "$prompt" "$RESET"; fi; read -r input || true; [[ -z "$input" && -n "$current" ]] && input="$current"; printf -v "$key" '%s' "$input"; }
write_env() { local key="$1" value="$2" tmp; touch "$ENV_FILE"; tmp=$(mktemp); grep -vE "^${key}=" "$ENV_FILE" > "$tmp" || true; printf '%s=%s\n' "$key" "$value" >> "$tmp"; mv "$tmp" "$ENV_FILE"; WRITTEN_ENV+=("$key"); printf '  %s✓ wrote%s %s → %s\n' "$GREEN" "$RESET" "$key" "$ENV_FILE"; }
finish() { _clear; printf '\n%s%s  ✓ Script complete%s\n' "$BOLD" "$GREEN" "$RESET"; (( ${#WRITTEN_ENV[@]} )) && note "wrote ${#WRITTEN_ENV[@]} value(s) to $ENV_FILE: ${WRITTEN_ENV[*]}"; printf '\n'; }

if [[ ! -f "$ENV_FILE" ]]; then
  printf 'No %s found — run 01-provision.sh first.\n' "$ENV_FILE"
  exit 1
fi
# shellcheck source=/dev/null
set -a; source "$ENV_FILE"; set +a

FINDINGS_FILE="$SCRIPT_DIR/../findings.md"

# on_error — this script doesn't provision anything itself, but by the time it runs the Container
# App from 01-provision.sh is live and billing per-hour, same as 01's own trap guards against. A
# failure here (a bad `date` parse, a log-pull that errors, you closing the terminal mid-stage)
# would otherwise die silently with no reminder that compute is still running. Matches 01's
# report-and-offer-cleanup shape rather than remind-only, upgraded 2026-08-20 — one keypress to stop
# billing beats copying a command by hand.
on_error() {
  local exit_code="${1:-$?}"
  _clear
  printf '\n%s%s  ✗ 02-test-calls.sh failed at stage %s/%s (exit %s)%s\n\n' \
    "$BOLD" "$RED" "$_STAGE_INDEX" "$TOTAL_STAGES" "$exit_code" "$RESET"
  say "Resources that exist in $RESOURCE_GROUP right now:"
  # --location "" overrides any stale `az config`/`~/.azure/config` defaults.location — see
  # docs/phase0/findings.md and 01-provision.sh's on_error trap for the same fix/rationale.
  az resource list --resource-group "$RESOURCE_GROUP" --location "" --output table 2>/dev/null \
    || note "(resource group query failed — check manually before assuming nothing's billing)"
  printf '\n'
  if az containerapp show --name "$CONTAINERAPP_NAME" --resource-group "$RESOURCE_GROUP" >/dev/null 2>&1; then
    warn "Container App $CONTAINERAPP_NAME exists and is billing right now."
    warn "Deleting it now ends this test-call session — remaining calls can't be placed until"
    warn "01-provision.sh is re-run to redeploy. Only delete if you're stopping for a while, not if"
    warn "you're about to fix a small thing and immediately retry a call."
    if confirm "Delete it now?"; then
      az containerapp delete --name "$CONTAINERAPP_NAME" --resource-group "$RESOURCE_GROUP" --yes --output none 2>/dev/null || true
      az containerapp env delete --name "$CAE_NAME" --resource-group "$RESOURCE_GROUP" --yes --output none 2>/dev/null || true
      ok "deleted — re-run 01-provision.sh from the top once you've fixed the cause above"
    else
      warn "left running — it is billing until you delete it or finish the test calls."
      note "Manual escape hatch: az containerapp delete --name $CONTAINERAPP_NAME --resource-group $RESOURCE_GROUP --yes"
    fi
  else
    ok "no Container App exists — nothing here is billing beyond the number (by design)"
  fi
  note "04-teardown-and-r08.sh is still the proper verified teardown once Phase 0 completes — this"
  note "is the mid-session escape hatch, not a substitute for it."
  exit "$exit_code"
}
trap 'on_error $?' ERR

TOTAL_STAGES=4
banner "Azure-Banking-Voice-Agentic-AI — Phase 0, script 2/4: Test calls"

if [[ -z "${PHONE_NUMBER:-}" ]]; then
  warn "PHONE_NUMBER isn't set in $ENV_FILE — script 1 may not have confirmed the purchase."
  ask PHONE_NUMBER "Enter the purchased number manually (E.164, e.g. +14165551234):"
  write_env "PHONE_NUMBER" "$PHONE_NUMBER"
fi

# DTMF is now requested on all three calls, not just Call 2. Found live 2026-08-21: with only Call 2
# prompted, Call 1 and Call 3 were both technically "unprompted" -- Call 3 registered 6/6 tones
# anyway (Marco pressed keys on all three regardless of what the script asked), Call 1 registered
# zero, with nothing in the logs explaining the difference. A single-call R-03 test can't tell a real
# gap from a fluke; asking on all three gets three independent data points instead of one, and stops
# conflating "the script didn't ask" with "nothing was pressed" when a caller presses anyway. See
# docs/phase0/findings.md, "R-03 -- DTMF evidence from the 3 real calls: confirmed by 2 of 3...".

# ── Stage 1: call 1 — plain echo + DTMF ─────────────────────────────────────
stage "Call 1/3 — plain echo test + DTMF"
say "Dial ${BOLD}${PHONE_NUMBER}${RESET} from your mobile now."
step "Speak a few words after it connects and confirm you hear your own voice echoed back."
step "While the echo is actively going (mid-call, not right at connect and not right before you hang"
step "up), press a few DTMF digits, e.g. 1  2  3. Keep listening for a few seconds after."
step "Stay on for ~20 seconds total, then hang up."
confirm "Did you complete the call, hear the echo, and press DTMF mid-call?" || warn "recorded as not confirmed — you can redial before moving on."
CALL1_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)
write_env "CALL1_TIME" "$CALL1_TIME"

# ── Stage 2: call 2 — DTMF during active streaming (R-03) ──────────────────
stage "Call 2/3 — DTMF during active bidirectional streaming (R-03)"
say "This call specifically tests R-03: docs/PLAN.md records DtmfData-during-streaming as"
say "\"documented and used in all four language pivots; narrowed but unproven\" until measured here."
step "Dial ${BOLD}${PHONE_NUMBER}${RESET} again."
step "While the echo is actively going (i.e. mid-call, audio still flowing both ways — not before"
step "the call connects, not after you'd normally hang up), press a few DTMF digits, e.g. 1  2  3."
step "Keep talking/listening for a few more seconds after the tones, then hang up."
confirm "Did you press DTMF tones mid-call and confirm the echo kept working after?" || warn "recorded as not confirmed."
CALL2_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)
write_env "CALL2_TIME" "$CALL2_TIME"

# ── Stage 3: call 3 — sustained call for RTT sampling + DTMF ────────────────
stage "Call 3/3 — sustained call for a transport RTT baseline + DTMF"
say "A longer call gives more echoed frames to sample for the RTT baseline (turns, not calls —"
say "B5 in docs/PLAN.md: this is transport RTT only, not a turn-latency percentile; that's Phase 2's job)."
step "Dial ${BOLD}${PHONE_NUMBER}${RESET} once more and stay on for at least 60 seconds, talking"
step "intermittently so there's real audio (not silence) flowing both ways."
step "Also press a few DTMF digits at some point mid-call, same as calls 1 and 2 -- a third"
step "independent data point for R-03, on a call with a much longer active-streaming window."
confirm "Completed the sustained call and pressed DTMF mid-call?" || warn "recorded as not confirmed."
CALL3_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)
write_env "CALL3_TIME" "$CALL3_TIME"

# ── Stage 4: pull logs and extract evidence ─────────────────────────────────
stage "Pull Container App logs and extract R-02 / R-03 / RTT evidence"
say "Reading application logs written by the echo app (docs/echo-app/app.py) since call 1."

# --tail 300, not 500: the CLI hard-caps this flag at 300 ("--tail must be between 0 and 300") and
# rejects anything higher with a non-zero exit. Found live 2026-08-21 -- --tail 500 had been failing
# on every single run of this stage, every time, silently: the old `2>/dev/null || echo ""` swallowed
# that error and always produced LOGS="", so the entire evidence-extraction block below (and the
# PROVISION_TIME gate inside it) had never actually executed once this whole session. A real call
# session (3 confirmed CallConnected events, DTMF, frame-echo) went unrecorded and R-04's window
# never opened, and the script still exited 0 saying "wait 24 hours" as if nothing were wrong.
# docs/phase0/findings.md, "02-test-calls.sh Stage 4 -- --tail 500 always failed, silently".
LOGS_STDERR_FILE=$(mktemp)
LOGS=$(az containerapp logs show \
  --name "$CONTAINERAPP_NAME" --resource-group "$RESOURCE_GROUP" \
  --type console --tail 300 2>"$LOGS_STDERR_FILE")
LOGS_EXIT=$?
LOGS_STDERR=$(cat "$LOGS_STDERR_FILE" 2>/dev/null || true)
rm -f "$LOGS_STDERR_FILE"

# The old check couldn't tell "the command itself failed" from "it succeeded but there's genuinely
# nothing yet" -- both looked like an empty $LOGS, and both were treated as a soft warn-and-continue,
# which is exactly how the --tail bug above went unnoticed all session. Distinguished explicitly now,
# and both cases exit non-zero rather than let the script reach `finish` and report success with no
# evidence gathered and no window opened.
if [[ $LOGS_EXIT -ne 0 ]]; then
  warn "az containerapp logs show FAILED (exit $LOGS_EXIT) -- a command error, not \"no logs yet\"."
  warn "Raw stderr:"
  sed 's/^/    /' <<<"$LOGS_STDERR"
  warn "Fix the command above and re-run this script. No evidence was evaluated; PROVISION_TIME was"
  warn "not touched."
  exit 1
elif [[ -z "$LOGS" ]]; then
  warn "az containerapp logs show succeeded (exit 0) but returned zero lines -- genuinely no logs yet,"
  warn "not a command failure. Retry the pull directly first, before re-running the whole script (a"
  warn "full re-run means 3 fresh phone calls, not just a retried log pull):"
  warn "  az containerapp logs show --name $CONTAINERAPP_NAME --resource-group $RESOURCE_GROUP --type console --tail 300"
  warn "PROVISION_TIME was not touched."
  exit 1
else
  # "DTMF tone=" never matched anything the app actually logs -- the real per-digit evidence line is
  # "DTMF digit #N arrived DURING streaming ... -- R-03 evidence" (docs/echo-app/app.py:149);
  # "DTMF tone=" only appears in the B2-gated raw-value line, off by default. Found live 2026-08-21:
  # this meant R03_RESULT below had been reporting UNCONFIRMED every run regardless of what the call
  # actually did. docs/phase0/findings.md, "R-03 -- ... Separate bug found while investigating this".
  DTMF_LINES=$(printf '%s\n' "$LOGS" | grep -i "DTMF digit #.*arrived DURING streaming" || true)
  FRAME_LINES=$(printf '%s\n' "$LOGS" | grep -i "frame .* echoed" || true)
  WS_LINES=$(printf '%s\n' "$LOGS" | grep -i "WS open\|WS closed" || true)
  CALLCONNECTED_LINES=$(printf '%s\n' "$LOGS" | grep "callback event: Microsoft.Communication.CallConnected" || true)

  say "WebSocket open/close events:"
  printf '%s\n' "$WS_LINES" | sed 's/^/    /'
  say "DTMF evidence (R-03):"
  if [[ -n "$DTMF_LINES" ]]; then
    printf '%s\n' "$DTMF_LINES" | sed 's/^/    /'
    ok "R-03 confirmed: DTMF tones logged arriving during active streaming (frame_count > 0 alongside them)"
    R03_RESULT="CONFIRMED — DTMF tones observed arriving during active bidirectional streaming. See raw log lines below."
  else
    warn "no DTMF log lines found — either call 2's tones weren't sent, or logs haven't flushed yet."
    R03_RESULT="UNCONFIRMED THIS RUN — no DTMF log lines captured. Re-run this stage, or redo call 2."
  fi
  say "Frame-echo / processing-latency samples (R-02 + RTT):"
  printf '%s\n' "$FRAME_LINES" | tail -20 | sed 's/^/    /'

  {
    echo "## R-02 / R-03 / RTT — evidence from 3 test calls"
    echo ""
    echo "Calls at: $CALL1_TIME, $CALL2_TIME, $CALL3_TIME (UTC)."
    echo ""
    echo "### R-03 (DTMF during active streaming)"
    echo ""
    echo "$R03_RESULT"
    echo ""
    echo '```'
    printf '%s\n' "$DTMF_LINES"
    echo '```'
    echo ""
    echo "### R-02 (Pcm24KMono) + transport RTT samples"
    echo ""
    echo "Processing-latency samples logged by the app (recv-to-echo, once per ~50 frames /1s):"
    echo '```'
    printf '%s\n' "$FRAME_LINES"
    echo '```'
    echo ""
    echo "Note: this is APP-SIDE processing latency (frame received → frame re-sent), not full"
    echo "caller-to-caller RTT. It's the transport-RTT-adjacent number Phase 0 can actually produce;"
    echo "the true turn-latency percentile needs a real RealtimeSession (Phase 2, B5)."
    echo ""
  } >> "$FINDINGS_FILE"
  ok "recorded to $FINDINGS_FILE"

  # R-04's 72h window opens HERE, not in 01-provision.sh, and only on this specific evidence -- a
  # passing /healthz check proved the container was up, not that it could answer a real phone call
  # (docs/phase0/findings.md, "healthz-as-window-gate"). Same guard shape as 01's old Stage 9/12
  # guards: read directly from ENV_FILE via _existing, never overwrite an already-anchored window.
  # Placed after the evidence block above, not before it: whatever DTMF/frame/WS evidence a call
  # produced is recorded to findings.md regardless of whether CallConnected itself is found -- a
  # partially-working call still deserves its evidence captured before the script exits.
  if [[ -n "$(_existing "PROVISION_TIME" || true)" ]]; then
    ok "PROVISION_TIME already set: $(_existing "PROVISION_TIME") -- R-04's window is already anchored, not resetting it"
  elif [[ -n "${CALLCONNECTED_LINES:-}" ]]; then
    write_env "PROVISION_TIME" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    ok "R-04's 72h window opens now -- anchored on a confirmed CallConnected event, not just a healthy container:"
    printf '%s\n' "$CALLCONNECTED_LINES" | sed 's/^/    /'
  else
    warn "no Microsoft.Communication.CallConnected event found in Container App logs -- no call has been"
    warn "confirmed answered. PROVISION_TIME NOT written; R-04's window has not opened."
    warn "Fix whatever's blocking the app from answering, then re-run this script -- safe to re-run,"
    warn "PROVISION_TIME only gets written once real evidence exists. Evidence above (if any) is"
    warn "already recorded to $FINDINGS_FILE regardless of this exit."
    exit 1
  fi
fi

say "Real ACS Audio Streaming meter (list price \$0.004/min) is a billing-side number, not a log —"
say "script 3 (after 24h) reads it from actual Cost Analysis, not an estimate."

finish
printf '\n%sNext:%s wait 24 hours for Cost Analysis to populate, then run %s03-cost-check-24h.sh%s.\n\n' \
  "$BOLD" "$RESET" "$BLUE" "$RESET"
