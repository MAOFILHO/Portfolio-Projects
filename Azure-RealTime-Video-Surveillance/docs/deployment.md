# Deployment Guide

## Prerequisites

See the [README prerequisites table](../README.md#prerequisites). Confirm everything is installed with:

```bash
surveil-deploy smoke-test --stage pre
```

## 1. Configure

```bash
cp .env.example .env
```

At minimum, set `AZURE_SUBSCRIPTION_ID`. Everything else has a cost-minimal default. If you want email alerts, also set `ALERT_EMAIL_TO`.

### Email alerting (Azure Communication Services)

The Bicep deployment provisions an ACS resource with an **Azure-managed email domain** automatically — no manual domain verification needed. `ACS_SENDER_EMAIL` is auto-filled from that domain's `DoNotReply@<generated>.azurecomm.net` address if you leave it blank in `.env`.

### SMS alerting (optional, manual step)

SMS requires purchasing an ACS phone number, which is a billing action this pipeline does not automate (to avoid an unexpected charge as part of `deploy`). After deployment, if you want SMS:

```bash
az communication phonenumber list --connection-string "<ACS connection string from Azure Portal or `az communication list-key`>"
az communication phonenumber purchase-phonenumbers ... # provisioning flow — see Azure docs
```

Then set `ACS_SMS_FROM` and `ALERT_SMS_TO` in `.env` and re-run `surveil-deploy deploy` (the Container App / Function env vars will pick up the new values; no infra changes needed).

## 2. Deploy

```bash
surveil-deploy deploy
```

This runs all 12 stages (see the [README stage table](../README.md#stage-details)), streaming every underlying `az`/`func`/`npm` command it runs. Typical time: 10-20 minutes, dominated by the ACR cloud build and Bicep provisioning.

If it fails partway through, fix the reported issue and re-run the same command — completed steps are skipped (see `deployment_state.json`, gitignored).

```bash
surveil-deploy deploy --fresh    # ignore prior state, start over
surveil-deploy status            # see which steps have completed
```

## 3. Validate

```bash
surveil-deploy smoke-test --stage post
```

This re-runs the health check and E2E validation (steps s09-s10) without re-provisioning anything.

## 4. Use it

Open the dashboard URL printed at the end of `deploy`. Grant camera permission, click **Start**, and watch the **Event History** panel populate as frames are analyzed. If a watched tag (default: `person`) is detected above the confidence threshold, an alert card appears instantly in the **Live Alerts** panel and (if configured) an email/SMS goes out.

## 5. Tear down

```bash
surveil-deploy teardown
```

See the [README teardown section](../README.md#teardown--cleanup) for the `--purge` option.

## Local development (without deploying)

**Backend:**
```bash
make install
cp .env.example .env   # fill in a real Vision endpoint + storage account if testing against Azure
make backend-dev        # uvicorn on :8000
```

**Function:**
```bash
cd function
cp local.settings.json.example local.settings.json   # fill in real values
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ../shared -r requirements.txt
func start
```

**Frontend:**
```bash
cd frontend
cp .env.example .env
make frontend-dev       # vite dev server on :5173, proxies to localhost:8000
```
