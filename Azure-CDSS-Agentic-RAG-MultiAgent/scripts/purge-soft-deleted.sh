#!/bin/bash
# ============================================================================
# Purge soft-deleted Azure resources from a previous teardown
# Run BEFORE re-deploying to avoid name conflicts
# ============================================================================
set -euo pipefail

LOCATION="${1:-}"
if [[ -z "$LOCATION" ]]; then
  echo "Usage: $0 <location> [resource-prefix]"
  echo "Example: $0 westus2 cdss"
  exit 1
fi
RESOURCE_PREFIX="${2:-cdss}"
PURGE_TIMEOUT=30

log_info()  { echo "[INFO]  $1"; }
log_warn()  { echo "[WARN]  $1"; }
log_ok()    { echo "[OK]    $1"; }
log_error() { echo "[ERROR] $1"; }

run_with_timeout() {
    local cmd=("$@")
    "${cmd[@]}" &
    local pid=$!
    local elapsed=0
    while kill -0 "$pid" 2>/dev/null; do
        if (( elapsed >= PURGE_TIMEOUT )); then
            kill "$pid" 2>/dev/null
            wait "$pid" 2>/dev/null
            return 1
        fi
        sleep 1
        ((elapsed++))
    done
    wait "$pid"
}

echo ""
echo "======================================"
echo "  Purge Soft-Deleted Azure Resources  "
echo "======================================"
echo "  Location: ${LOCATION}"
echo "  Filter:   ${RESOURCE_PREFIX}*"
echo "======================================"
echo ""

# --- Cognitive Services (OpenAI + Document Intelligence) ---
log_info "Checking for soft-deleted Cognitive Services accounts..."
DELETED_ACCOUNTS=$(az cognitiveservices account list-deleted --query "[?location=='${LOCATION}' && starts_with(name, '${RESOURCE_PREFIX}')].{name:name, resourceGroup:resourceGroup, kind:kind}" -o tsv 2>/dev/null || echo "")

if [[ -n "$DELETED_ACCOUNTS" ]]; then
    while IFS=$'\t' read -r name rg kind; do
        log_warn "Found soft-deleted: ${name} (${kind}) in ${rg}"
        log_info "Purging ${name} (${PURGE_TIMEOUT}s timeout)..."
        if run_with_timeout az cognitiveservices account purge -g "${rg}" -n "${name}" -l "${LOCATION}" 2>/dev/null; then
            log_ok "Purged: ${name}"
        else
            log_warn "Skipped: ${name} (timed out or failed — deploy will attempt restore)"
        fi
    done <<< "$DELETED_ACCOUNTS"
else
    log_ok "No soft-deleted Cognitive Services accounts found in ${LOCATION}"
fi

# --- Key Vaults ---
log_info "Checking for soft-deleted Key Vaults..."
DELETED_VAULTS=$(az keyvault list-deleted --query "[?properties.location=='${LOCATION}' && starts_with(name, '${RESOURCE_PREFIX}')].name" -o tsv 2>/dev/null || echo "")

if [[ -n "$DELETED_VAULTS" ]]; then
    while IFS= read -r vault_name; do
        [[ -z "$vault_name" ]] && continue
        log_warn "Found soft-deleted Key Vault: ${vault_name}"
        log_info "Purging ${vault_name} (${PURGE_TIMEOUT}s timeout)..."
        if run_with_timeout az keyvault purge --name "${vault_name}" 2>/dev/null; then
            log_ok "Purged: ${vault_name}"
        else
            log_warn "Skipped: ${vault_name} (timed out or purge-protected — deploy will attempt restore)"
        fi
    done <<< "$DELETED_VAULTS"
else
    log_ok "No soft-deleted Key Vaults found in ${LOCATION}"
fi

# --- API Management (if applicable) ---
log_info "Checking for soft-deleted API Management services..."
DELETED_APIM=$(az apim deletedservice list --query "[?location=='${LOCATION}'].{name:name, serviceId:serviceId}" -o tsv 2>/dev/null || echo "")

if [[ -n "$DELETED_APIM" ]]; then
    while IFS=$'\t' read -r name service_id; do
        [[ -z "$name" ]] && continue
        log_warn "Found soft-deleted API Management: ${name}"
        log_info "Purging ${name} (${PURGE_TIMEOUT}s timeout)..."
        if run_with_timeout az apim deletedservice purge --service-name "${name}" --location "${LOCATION}" 2>/dev/null; then
            log_ok "Purged: ${name}"
        else
            log_warn "Skipped: ${name} (timed out or failed)"
        fi
    done <<< "$DELETED_APIM"
else
    log_ok "No soft-deleted API Management services found"
fi

echo ""
log_ok "Purge scan complete. Safe to proceed with deployment."
echo ""
