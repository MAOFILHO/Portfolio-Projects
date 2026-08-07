# Troubleshooting

Every issue below was hit and resolved during real local runs and a real Azure deployment of this
project — these aren't hypothetical. Each entry states the symptom, the root cause, and whether it's
already fixed in the repo or something you need to act on.

← Back to the [README](../README.md)

## Local

**Airflow `train_arima` fails with `Py4JNetworkError` / `ConnectionRefusedError`**
Transient Spark JVM contention: each of the 5 parallel training tasks builds its own SparkSession/JVM
(the singleton in `spark_session.py` is per-process, not shared), and on a memory-constrained Docker
VM one occasionally loses the race to open its Arrow-collection socket. **Fixed** —
`forecasting_pipeline_dag.py` sets `retries=2, retry_delay=30s` on each training task, so this costs a
30-second retry rather than a manual re-trigger.

**`uvicorn --reload` restarts endlessly and the API is unreachable**
`--reload` watches all of `backend/` including `.venv/`; `.pyc` writes inside `site-packages` retrigger
it. Use `--reload-dir api --reload-dir src` (as in step 4), or drop `--reload` entirely.

**Port already in use (8080, 5173, 8000)**
Airflow's webserver is mapped to **8081** (not 8080) precisely because 8080 is commonly occupied. If
Vite or the backend collide too, set `API_CORS_ORIGIN` (backend) and `VITE_API_BASE_URL` (frontend) to
match whatever ports you actually end up on — a mismatch here surfaces as a CORS error, not a port
error.

**Live Telemetry page stops updating**
Expected: the Kafka producer is a one-shot replay that exits after sending its batch. Re-run it for a
fresh burst.

**DAG shows `upstream_failed` on everything downstream of `run_pyspark_etl`**
Check the actual `run_pyspark_etl` log — a failure there cascades. In the cloud deploy this was a
`PermissionError` writing plot PNGs (see below).

## Cloud deploy

**`QuotaExceeded` on `LowPriorityCores`**
Spot VMs draw from a separate, often very small quota (default was **3 cores** — not enough for a
4-vCPU VM). Either request an increase, use a smaller Spot size, or use regular (non-Spot) pricing.

**`SkuNotAvailable` — "Capacity Restrictions"**
The Spot capacity pool for that specific SKU/region is exhausted right now. This is transient and
independent of your quota. Try another region, another SKU, or regular pricing.

**`QuotaExceeded` with `Current Limit: 0` on a v5-family VM**
Some subscriptions have **zero** quota for newer VM generations while older ones have headroom.
`az vm list-usage --location <region> -o table` shows the real picture. This project defaults to
`Standard_D4s_v3` for exactly this reason.

**`docker compose` builds the wrong stack / only Kafka starts**
Compose walks *up* parent directories looking for a default-named `docker-compose.yml` when it can't
find one in the working directory — silently picking up the repo root's Kafka-only file instead of
`docker-compose.cloud.yml`. **Fixed** — `bootstrap.sh` exports `COMPOSE_FILE` explicitly.

**`Unable to locate package openjdk-17-jdk-headless`**
The floating `python:3.12-slim` tag drifted to Debian trixie, which doesn't carry JDK 17. **Fixed** —
pinned to `python:3.12-slim-bookworm`.

**`PermissionError` writing to `backend/outputs/`**
`git clone` on the VM runs as root, so committed output files are root-owned — but Airflow's
containers run as UID 50000 and can't overwrite them. **Fixed** — `bootstrap.sh` runs
`chmod -R a+rwX` on `outputs/` after cloning.

**IMDS returns an empty public IP right after VM creation**
Azure's Instance Metadata Service doesn't immediately reflect a freshly-attached public IP, even
though the NIC association is already correct. **Fixed** — Bicep now substitutes the address into
`cloud-init` at deploy time instead of having the VM query for it.

**`az resource list --tag` fails with "cannot use '--tag' with '--location'"**
An Azure CLI argument-validation quirk that triggers on any machine with a default location set via
`az configure`. **Fixed** — the teardown verifier lists resources unfiltered and filters by tag
client-side.



