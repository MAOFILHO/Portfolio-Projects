#!/bin/bash
# First-boot provisioning script for the Azure demo VM. Passed as raw
# custom-data to the VM (see ../infra/main.bicep) -- Ubuntu's default
# cloud-init recognizes a customData payload starting with `#!` as a
# user-data script and runs it once during the cloud-final boot stage, no
# cloud-config YAML wrapper needed.
#
# Nothing here is templated: everything that would otherwise need to be
# baked in ahead of time (the VM's own public IP) is instead self-discovered
# at boot via Azure's Instance Metadata Service, so this file is the same
# for every deploy regardless of the resolved resource-name suffix.
#
# Progress/failure is signaled via marker files under $APP_DIR that the
# deploy CLI's s04_bootstrap_stack step polls for over SSH/run-command:
#   .ready   -- stack is up and (best-effort) healthy
#   .failed  -- something went wrong; contents are the error
set -euo pipefail

REPO_URL="https://github.com/MAOFILHO/Portfolio-Projects.git"
APP_DIR="/opt/app"
PROJECT_DIR="$APP_DIR/Portfolio-Projects/Event-Driven-ML-Forecasting-Platform"
COMPOSE_DIR="$PROJECT_DIR/cloud/docker"
LOG="/var/log/forecasting-bootstrap.log"

exec > >(tee -a "$LOG") 2>&1

fail() {
    echo "$1" | tee "$APP_DIR/.failed"
    exit 1
}

trap 'fail "bootstrap.sh exited unexpectedly at line $LINENO (see '"$LOG"')"' ERR

mkdir -p "$APP_DIR"
echo "=== $(date -u --iso-8601=seconds) starting bootstrap ==="

echo "--- installing docker, compose plugin, git ---"
apt-get update -qq
apt-get install -y -qq ca-certificates curl git jq openssl
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
apt-get update -qq
apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker

echo "--- cloning $REPO_URL (public repo, no credentials needed) ---"
rm -rf "$APP_DIR/Portfolio-Projects"
git clone --depth 1 "$REPO_URL" "$APP_DIR/Portfolio-Projects" \
    || fail "git clone failed"

cd "$COMPOSE_DIR" || fail "compose dir $COMPOSE_DIR not found after clone"

echo "--- resolving own public IP via Azure Instance Metadata Service ---"
PUBLIC_IP=$(curl -s -H "Metadata:true" --noproxy "*" \
    "http://169.254.169.254/metadata/instance/network/interface/0/ipv4/ipAddress/0/publicIpAddress?api-version=2021-02-01&format=text")
[ -n "$PUBLIC_IP" ] || fail "could not resolve public IP from IMDS"
echo "resolved public IP: $PUBLIC_IP"

echo "--- generating secrets (never committed, never hardcoded) ---"
AIRFLOW_ADMIN_PASSWORD=$(openssl rand -base64 12)
AIRFLOW_SECRET_KEY=$(openssl rand -hex 32)

cat > "$COMPOSE_DIR/.env" <<EOF
VITE_API_BASE_URL=http://${PUBLIC_IP}
API_CORS_ORIGIN=http://${PUBLIC_IP}
AIRFLOW_ADMIN_PASSWORD=${AIRFLOW_ADMIN_PASSWORD}
AIRFLOW_SECRET_KEY=${AIRFLOW_SECRET_KEY}
AIRFLOW_UID=50000
LSTM_EPOCHS=10
LSTM_RETRAIN=false
KAFKA_TOPIC=temperature-telemetry
KAFKA_PRODUCER_RATE=500
EOF

# Credentials the deploy CLI fetches after boot (via `az vm run-command
# invoke`) to print to the operator -- world-unreadable, root-owned.
cat > "$APP_DIR/.cloud-credentials" <<EOF
PUBLIC_IP=${PUBLIC_IP}
DASHBOARD_URL=http://${PUBLIC_IP}
AIRFLOW_URL=http://${PUBLIC_IP}:8081
AIRFLOW_ADMIN_USER=admin
AIRFLOW_ADMIN_PASSWORD=${AIRFLOW_ADMIN_PASSWORD}
EOF
chmod 600 "$APP_DIR/.cloud-credentials"

echo "--- building images (slow: ~15-20 min for the Airflow + backend images) ---"
docker compose build || fail "docker compose build failed"

echo "--- starting the stack ---"
docker compose up -d || fail "docker compose up failed"

echo "--- waiting for backend/frontend/airflow-webserver to report healthy ---"
DEADLINE=$((SECONDS + 900))
while [ $SECONDS -lt $DEADLINE ]; do
    STATUSES=$(docker compose ps --format '{{.Service}} {{.Health}}' 2>/dev/null || true)
    if echo "$STATUSES" | grep -q '^backend healthy' \
        && echo "$STATUSES" | grep -q '^frontend healthy' \
        && echo "$STATUSES" | grep -q '^airflow-webserver healthy'; then
        echo "=== stack healthy ==="
        touch "$APP_DIR/.ready"
        echo "=== $(date -u --iso-8601=seconds) bootstrap complete ==="
        exit 0
    fi
    sleep 10
done

fail "timed out after 15 min waiting for backend/frontend/airflow-webserver to become healthy -- see 'docker compose ps' and $LOG on the VM"
