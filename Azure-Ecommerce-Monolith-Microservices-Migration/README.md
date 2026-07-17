# Azure-Ecommerce-Monolith-Microservices-Migration
### A live Strangler Fig cutover — not an animation


![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.1-000000?logo=flask&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript&logoColor=white)
![Azure](https://img.shields.io/badge/Azure-Container_Apps-0078D4?logo=microsoftazure&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

The same e-commerce application, running two ways: as a **monolith** (one Flask process, one
shared database) and as **three independently deployable microservices** (user, product, order —
each owning its own database). Click **Migrate** and watch a real strangler-fig cutover happen
live — not an animation. Compare real before/after performance numbers. Read the architectural
reasoning behind it all.


## The Problem

Teams inherit monoliths that "just work" until they don't: every deploy risks the whole app, one
noisy feature (say, checkout under Black Friday load) forces scaling the entire system, and a
schema change in one domain can silently break another. The textbook answer is "migrate to
microservices" — but most explanations are diagrams, not code you can run.

| Monolith pain point | Microservices answer |
|---|---|
| One bug can take down the whole app | Fault isolation — a failing service doesn't crash the others |
| Scaling means scaling everything | Independent scaling per service |
| One team's schema change can break another's code | Each service owns its own database |
| Slow, risky "big bang" deploys | Small, independent deploys per service |
| Hard to reason about a large shared codebase | Smaller, focused codebases per bounded context |

This project makes that transition **tangible**: the same registration/login, product catalog,
and cart/checkout flow, provably working identically on both sides (see `tests/smoke/test_post_run.py`),
with a real (not simulated) migration process you can trigger and watch.



## Architecture — Before (Monolith)

```
Browser → BFF (proxy) →  ┌─────────────────────────────┐
                         │   monolith (Flask, :6000)   │
                         │   ├── auth blueprint        │
                         │   ├── catalog blueprint     │
                         │   └── orders blueprint      │
                         │   one shared database       │  ← "Shared Persistence"
                         └─────────────────────────────┘
```




## Architecture — After (Microservices)

```
                          ┌──────────────────────┐
                    ┌────►│ user-service  :5001  │──► user_db
                    │     └──────────────────────┘
Browser → BFF ──────┤     ┌──────────────────────┐
 (proxy, :8000)     ├────►│ product-service :5002│──► product_db
                    │     └──────────────────────┘
                    │     ┌──────────────────────┐
                    └────►│ order-service  :5003 │──► order_db
                          └──────────┬───────────┘
                                     │ HTTP (Anti-Corruption Layer)
                                     ▼
                          user-service :5001 (validates api_key)
```


Note the key architectural difference the migration introduces: in the monolith, order logic
queries the `User` table directly in the same database session. In the microservices version,
`order-service` has **no access** to the user database at all — it validates the caller by making
a real HTTP call to `user-service` (`microservices/order-service/application/order_api/api/UserClient.py`).
That's the Anti-Corruption Layer pattern in actual code, not just a diagram.



## What you get

- **`monolith/`** — the BEFORE state, modernized to Flask 3.1 / SQLAlchemy 2.0 / Python 3.12
- **`microservices/{user,product,order}-service/`** — the AFTER state, same business logic, three
  independent Flask services, each with its own database
- **`bff/`** — a FastAPI backend-for-frontend that proxies the React app to either backend, drives
  the live migration, serves Learn content, and runs the benchmark
- **`frontend/`** — React + TypeScript + Vite, Contoso theme, with Home / Shop / Migrate / Learn /
  Metrics pages
- **Zero Docker Desktop, zero local containers** — local dev is 100% plain Python/Node processes.
  Containers exist *only* on Azure, built via `az acr build` (cloud-side, no local Docker daemon)
- **Azure-hosted by default, local dev optional** — `make provision` deploys only the monolith;
  the microservices' Container Apps get created for real, live, when you trigger the migration from
  the browser (see "Deploying to Azure" below). Prefer to stay entirely local and free? `make setup
  && make run-all` does that too, with the same code.



## The Migrate page — a real cutover, not an animation

Clicking **Start Migration** in **local** mode:
1. Actually starts the `user-service`, `product-service`, and `order-service` Python processes
   (they aren't running until you do this — the "before" state genuinely only has the monolith up)
2. Polls their real `/health` endpoints before advancing
3. Actually stops the monolith process in the final "Decommission" step
4. Streams progress to the UI in real time (SSE), one step per Strangler Fig phase (domain
   assessment → proxy layer → extraction → ACL → traffic redirection → decommission)

In **azure** mode, it's the same idea but with real cloud infrastructure: `make provision` deploys
**only** the monolith (plus the BFF and the foundation — ACR, Container Apps Environment, MySQL,
Static Web App). The `user-service`, `product-service`, and `order-service` Container Apps do not
exist yet. Clicking **Start Migration** makes the BFF itself — using its own scoped Azure managed
identity — call the `azure-mgmt-appcontainers` SDK to create each one for real, one at a time,
waiting for each to answer its real `/health` endpoint before moving to the next step. The final
"Decommission" step scales the monolith Container App to zero replicas. Nothing about this is
pre-provisioned or simulated: run `az containerapp list --resource-group <rg> -o table` in another
terminal during the migration and watch `user-service`, then `product-service`, then
`order-service` appear one by one as the timeline advances.

Verified for real during development in local mode: clicked through the full migration in a
browser, confirmed via direct port checks that the monolith was truly stopped and all three
microservices were truly running afterward, then ran the full register→login→create
product→add to cart→checkout flow against the post-migration microservices stack.

<img width="1428" height="976" alt="Screenshot 2026-07-16 at 8 55 57 PM" src="https://github.com/user-attachments/assets/7dae2caa-ceef-4a1c-917d-9e6b18b656b9" />

<img width="100%" height="1" alt="" src="https://github.com/user-attachments/assets/f2af28ee-a373-4488-89e5-2b84d5da9620" />
<br><br>
<img width="1456" height="986" alt="Screenshot 2026-07-16 at 8 18 11 PM" src="https://github.com/user-attachments/assets/39e90fdd-3262-41e5-8a87-7872d3523da0" />

<img width="100%" height="1" alt="" src="https://github.com/user-attachments/assets/f2af28ee-a373-4488-89e5-2b84d5da9620" />
<br><br>
<img width="884" height="981" alt="Screenshot 2026-07-16 at 8 18 39 PM" src="https://github.com/user-attachments/assets/eb6cbcdf-d6bc-46e7-8b23-56e4a93847b7" />



## The Metrics page — real numbers, not fabricated ones

`scripts/benchmark.py` hits the monolith and product-service **directly** (ports 6000 and 5002),
bypassing the BFF entirely, so the comparison stays apples-to-apples: both sides are Flask +
identical route/serialization code — the only variable is "one process/one DB" vs. "three
processes/three DBs," not an extra proxy hop or a different framework. Results are saved to
`results/benchmark_*.json` and rendered as p95 latency and throughput comparison charts.

> **FastAPI is only used for the BFF** — the orchestration/proxy layer in front of both stacks,
> not part of either side being measured. Both the monolith and all three microservices are Flask.



<img width="1393" height="674" alt="Screenshot 2026-07-17 at 4 32 10 PM" src="https://github.com/user-attachments/assets/ec0c1348-4810-49d8-9216-ace347fbb435" />

<img width="100%" height="1" alt="" src="https://github.com/user-attachments/assets/f2af28ee-a373-4488-89e5-2b84d5da9620" />
<br><br>
<img width="1419" height="613" alt="Screenshot 2026-07-16 at 10 01 46 PM" src="https://github.com/user-attachments/assets/0bf95023-8d4e-4da7-9998-d3f62599fafe" />


## Tech stack

| Layer | Technology |
|---|---|
| Monolith & microservices | Flask 3.1, Flask-SQLAlchemy 3.1, Flask-Migrate 4.0, Flask-Login 0.6, SQLAlchemy 2.0 |
| Validation | **Pydantic 2.10** everywhere — FastAPI-native in the BFF, a shared `validate_form()` helper in every Flask app |
| BFF | FastAPI 0.115, Uvicorn, httpx, SSE (`sse-starlette`), `azure-mgmt-appcontainers` |
| Frontend | React 18, TypeScript 5, Vite 5, `recharts`, `react-router-dom` |
| Local database | SQLite (one file per service, auto-created in dev) |
| Azure database | Azure Database for MySQL Flexible Server (Burstable B1ms, 4 logical DBs) |
| Infra-as-code | Bicep (`infra/bicep/`) + a thin Python orchestrator (`infra/provision.py`) |
| Containers | Built exclusively via `az acr build` — no local Docker daemon anywhere in this project |
| Testing | pytest (38 unit tests across 6 suites) + smoke tests (pre-setup/post-setup/post-run/post-teardown) |



## Prerequisites

- **Python 3.12** (required — the original repo pinned Flask 1.1.1/Werkzeug 1.0.1 from 2020, which
  breaks on Python 3.10+; this project modernizes every pin)
- **Node.js 18+** and npm (for the React frontend)
- **Azure CLI** (`az`) — only needed if you use `make provision` / `make teardown`
- No Docker, no Docker Desktop, no other accounts or API keys required



## Two ways to run this — pick one

| | **Local** (free, no Azure) | **Azure** (the flagship demo) |
|---|---|---|
| Command | `make setup` then `make run-all` | `az login`, then `make provision BUDGET_EMAIL=you@example.com` — **`make setup` is not required for this path** |
| What it needs | Python 3.12 + Node.js only | Azure CLI logged in to a subscription — that's it |
| Why | `make setup` creates the 5 local Python venvs + frontend npm deps that `make run` / `make run-all` / `make test` run against | `infra/provision.py` has zero third-party dependencies (stdlib only) and builds every container image remotely via `az acr build` — it never touches the local venvs, so skipping `make setup` is fine if you're going straight to Azure |
| Cost | $0 | ~$0.21 for an 8-hour session, ~$19.51/mo if left running — see the cost table below. Run `make teardown` when done. |

Doing both (local first, then Azure) is completely fine too — the two paths don't conflict — but
**neither is a prerequisite for the other.** If you only care about the Azure demo, you can skip
straight to `git clone` → `az login` → `make provision` below without ever running `make setup`.



## Setup & running locally (optional — 100% local, zero cost)

```bash
git clone <your-fork-url> flask-monolith-to-microservices   # or any folder name you like
cd flask-monolith-to-microservices
cp .env.example .env      # optional — sensible defaults work out of the box

make setup                 # creates 5 Python 3.12 venvs + installs frontend npm deps
make run-all                # starts monolith + all 3 microservices + bff + frontend together
```

<img width="1059" height="711" alt="Screenshot 2026-07-15 at 4 27 57 PM" src="https://github.com/user-attachments/assets/1792d204-d6a4-411c-b147-a1a5bc0952ba" />



Open **http://127.0.0.1:5173**.

> Use `make run-all` (not plain `make run`) if you plan to run the benchmark: the benchmark needs
> the monolith and product-service reachable *at the same time*, and `make run` alone only starts
> the monolith (the guided Migrate flow starts the microservices but also stops the monolith in
> its last step, so the two are never both up together on that path). `make run-all` starts
> everything at once with nothing auto-stopped, so both the walkthrough below and a real fresh
> Migrate demo both work from the same starting point.

<img width="1424" height="699" alt="Screenshot 2026-07-16 at 9 19 20 AM" src="https://github.com/user-attachments/assets/dfc83ddb-0f29-401f-9b95-7ed03a5d38e0" />



### Suggested first walkthrough

Go in this order the first time:

1. **Shop (Monolith tab)** — click "Add sample products", register an account, add items to the
   cart, and check out. This proves the "before" state fully works end-to-end.
2. **Metrics — click "Run Benchmark"** — hits the monolith and product-service directly and
   renders real p95 latency/throughput comparison charts. Results are saved to `results/`, so the
   Metrics page keeps showing them even after later steps stop the monolith.
3. **Migrate — click "Start Migration"** — since the microservices are already running (from
   `make run-all`), the extraction steps just confirm they're healthy; the final "Decommission"
   step still genuinely stops the monolith process. Not an animation — you can `curl
   http://127.0.0.1:5001/health` in another terminal to watch it stay alive, or `curl
   http://127.0.0.1:6000/health` afterward to see the monolith actually go down.
4. **Shop (Microservices tab)** — repeat step 1 against the new backend. You'll need to register
   again (separate database — your monolith account doesn't carry over, which is the point).
5. **Learn** — a quieter read: the Strangler Fig pattern, anti-patterns to avoid, and glossary,
   sourced from the study guides that shaped this build.

Other useful commands:

```bash
make run             # starts only monolith + bff + frontend — microservices stay down until you
                      # trigger a migration from the Migrate page (the purest "before" starting point)
make test             # 38 unit tests across 6 suites
make smoke             # pre-setup/post-setup/post-run/post-teardown smoke tests
make benchmark         # same benchmark the Metrics page runs, from the CLI (needs monolith + product-service up)
make clean             # removes local SQLite files, __pycache__, and benchmark results
```

Local dev self-heals from leftover processes: if a previous run is still holding a port, `make run`
(or `make run-all`) detects it (by checking that process's own command line and working directory against this
project), stops it cleanly, and proceeds — verified for real, including the case where a leftover
process's command line is a generic `python run.py` with no repo path in it at all (this project
launches every service with `cwd=<service_dir>`, so cwd is checked in addition to the command line).



## Environment variables

| Variable | Purpose | Default |
|---|---|---|
| `RUN_MODE` | `local` (SQLite, plain processes) or `azure` (MySQL, Container Apps) | `local` |
| `SECRET_KEY` | Flask session secret | dev placeholder — set a real value for any shared use |
| `MONOLITH_PORT` / `USER_SERVICE_PORT` / `PRODUCT_SERVICE_PORT` / `ORDER_SERVICE_PORT` / `BFF_PORT` / `FRONTEND_PORT` | Local service ports | 6000 / 5001 / 5002 / 5003 / 8000 / 5173 |
| `AZURE_MYSQL_HOST` / `AZURE_MYSQL_ADMIN_USER` / `AZURE_MYSQL_ADMIN_PASSWORD` | Populated automatically by `infra/provision.py` — never set manually | — |
| `AZURE_LOCATION` / `AZURE_RESOURCE_GROUP` / `AZURE_BUDGET_CEILING_USD` | Azure provisioning defaults — `AZURE_LOCATION` is never hardcoded in code, `infra/provision.py` reads it from `.env` first (falling back to `az config get defaults.location`, then `eastus`) | `eastus` / `rg-flask-monolith-microservices` / `25` |

No third-party API keys are required anywhere in this project.



## Deploying to Azure (the flagship demo — costs money while resources are live)

This is the intended way to experience the migration story: **only the monolith goes live at
first**, and the microservices get created for real, in front of you, when you trigger the
migration from the browser. Nothing runs side-by-side in the cloud the way `make run-all` does
locally — the cloud story is strictly sequential (deploy monolith → migrate live → compare
before/after), which is what makes watching the migration actually happen feel real.

> **You do not need to run `make setup` first.** `infra/provision.py` has zero third-party
> dependencies and never touches the local Python venvs — the only prerequisite is being logged
> into the Azure CLI (`az login`). Clone the repo and go straight to the command below.

```bash
git clone <your-fork-url> flask-monolith-to-microservices
cd flask-monolith-to-microservices
az login
az account set --subscription "<subscription-id-or-name>"   # if you have more than one

make provision BUDGET_EMAIL=you@example.com
```

<img width="1063" height="708" alt="Screenshot 2026-07-17 at 4 07 55 PM" src="https://github.com/user-attachments/assets/7aadfd09-8311-4f78-915f-383eaeb10625" />

<img width="100%" height="1" alt="" src="https://github.com/user-attachments/assets/f2af28ee-a373-4488-89e5-2b84d5da9620" />
<br><br>
<img width="1060" height="709" alt="Screenshot 2026-07-17 at 4 08 21 PM" src="https://github.com/user-attachments/assets/312b48fc-5fbf-42d7-8595-3f6203be2589" />

<img width="100%" height="1" alt="" src="https://github.com/user-attachments/assets/f2af28ee-a373-4488-89e5-2b84d5da9620" />
<br><br>
<img width="1064" height="715" alt="Screenshot 2026-07-17 at 4 09 06 PM" src="https://github.com/user-attachments/assets/63dbe9f9-f25a-41f1-bae0-d6cf50ca704c" />

<img width="100%" height="1" alt="" src="https://github.com/user-attachments/assets/f2af28ee-a373-4488-89e5-2b84d5da9620" />
<br><br>
<img width="1064" height="659" alt="Screenshot 2026-07-17 at 4 25 21 PM" src="https://github.com/user-attachments/assets/43883ac7-90e2-4427-91ab-443f7f32969c" />

<img width="100%" height="1" alt="" src="https://github.com/user-attachments/assets/f2af28ee-a373-4488-89e5-2b84d5da9620" />
<br><br>
<img width="843" height="590" alt="Screenshot 2026-07-17 at 4 20 49 PM" src="https://github.com/user-attachments/assets/4bd7c1fc-c686-43f5-a6f0-c1152c2683f0" />

This deploys the foundation (ACR, Container Apps Environment, MySQL Flexible Server, Static Web
App, Log Analytics, budget alert) plus exactly **two** Container Apps: `monolith` and `bff`. The
bff Container App gets a system-assigned managed identity with `Contributor` scoped to just this
one resource group — that's what lets it create the microservices' Container Apps itself later,
without you running any command for that step.

**The demo sequence:**
1. Open the Static Web App URL printed at the end of `make provision`. Shop works fully against
   the monolith — register, add to cart, checkout — running on real Azure MySQL.
2. Go to **Metrics**, run a benchmark now. This is your durable "before" number.
3. Go to **Migrate**, click **Start Migration**. Watch `user-service`, then `product-service`, then
   `order-service` Container Apps get created live (confirm in another terminal with `az
   containerapp list --resource-group <rg> -o table` if you want to see it from both sides), then
   the monolith scale to zero.
4. Shop automatically switches to serving from the microservices — no toggle to click.
5. Run the benchmark again on **Metrics** for your "after" number.
6. `make teardown` when you're done recording.

```bash
make teardown
make verify     # polls until every resource is confirmed deleted
```

<img width="1053" height="167" alt="Screenshot 2026-07-17 at 3 25 45 PM" src="https://github.com/user-attachments/assets/d4b896fe-4b16-4e32-88fd-a02d02ee5d43" />

<img width="100%" height="1" alt="" src="https://github.com/user-attachments/assets/f2af28ee-a373-4488-89e5-2b84d5da9620" />
<br><br>
<img width="1061" height="127" alt="Screenshot 2026-07-17 at 5 22 42 PM" src="https://github.com/user-attachments/assets/04847204-720e-412e-a33f-fa6d4320731c" />


`provision.py` resolves collision-safe resource names (auto-incrementing on any naming collision
— tested for real against a live throwaway Azure Container Registry during development, including
discovering and fixing an ACR-specific naming-rule edge case), deploys the trimmed
`infra/bicep/main.bicep` with the exact approved SKUs, builds every service image via `az acr
build` up front (no local Docker) so the live migration only has to create Container Apps from
already-pushed images — fast and demo-safe instead of a slow image build happening on camera —
and creates a Cost Management budget alert **before** any billable resource exists.

### Cost estimate (full detail in `cost_estimate.md`)

| Resource | SKU | Free tier? | 8-hr test session | 30 days if left running |
|---|---|---|---|---|
| Azure Container Registry | Basic | No — cheapest tier | $0.06 | $5.01 |
| Container Apps (monolith + bff upfront; microservices created live by the migration), scale-to-zero | Consumption | Yes, effectively (large monthly free grant) | ~$0 | ~$0 |
| Azure Database for MySQL Flexible Server | Burstable B1ms | No — cheapest tier | $0.15 | **$14.50** |
| Static Web Apps (frontend) | Free | Yes | $0 | $0 |
| Contributor role assignment (bff's identity, scoped to this resource group) | n/a | Free (control-plane only) | $0 | $0 |
| **Total** | | | **~$0.21** | **~$19.51** |

No resource exceeds the $50/30-day threshold. ACR and MySQL Flexible Server are the only two
resources here with no free tier anywhere in Azure — everything else is already Free/scale-to-zero.
**MySQL Flexible Server is the one resource that bills whether idle or not** — run `make teardown`
when you're done testing.

### Local development (optional, zero cost)

Everything above also runs entirely locally with no Azure involved at all — see the section below.



## Project structure

```
monolith/                    BEFORE — single Flask app, one shared schema
microservices/{user,product,order}-service/   AFTER — 3 independent Flask apps
bff/                          FastAPI: shop proxy, live migration engine, benchmark, Learn content
frontend/                     React + TypeScript + Vite, Contoso theme
infra/                        Bicep templates, provision.py, teardown.py, verify_teardown.py
scripts/                      setup.py, run_local.py (+ port self-heal), benchmark.py
tests/                        smoke/ (HTTP-based) + unit/ (name_resolver, migration_engine, procutil)
monolith/tests/, microservices/*/tests/, bff/tests/   per-service unit tests
```


## Running tests

```bash
make test       # unit tests — no services need to be running
make smoke      # smoke tests — pre-setup checks always run; post-setup/post-run/post-teardown
                # checks skip gracefully if their prerequisite (make setup / make run / an Azure
                # deployment) hasn't happened yet, rather than failing
```
<img width="1067" height="706" alt="Screenshot 2026-07-17 at 3 29 31 PM" src="https://github.com/user-attachments/assets/714b12bd-ccd9-4883-9bfd-ff72b94342f0" />


## Key engineering decisions

| Challenge | Solution |
|---|---|
| Original repo pinned Flask 1.1.1 (2020, breaks on Python 3.10+) | Modernized to Flask 3.1 / SQLAlchemy 2.0 / Python 3.12 throughout |
| No Docker Desktop allowed | Containers exist only on Azure, built via `az acr build`; local dev is plain processes |
| Benchmark fairness (Flask vs. FastAPI would be an unfair comparison) | Benchmark hits the monolith and a microservice directly, bypassing the FastAPI BFF |
| ACR names are alphanumeric-only (no hyphens) | Discovered via a real collision test — the resolver uses a hyphen-free increment scheme for ACR specifically |
| Flask's dev reloader spawns a child process sharing the parent's port | Port-collision cleanup snapshots every PID's identity before killing any, so a cascade-killed child isn't mistaken for a foreign process |
| `psutil.net_connections()` requires root on macOS | Switched to per-process `Process.net_connections()`, which doesn't — caught for real when the "Decommission" migration step hung forever |
| Leftover processes have a generic `python run.py` command line with no repo path in it | Ownership check also verifies the process's working directory, not just its command line — caught for real against the actual invocation pattern this project uses |
| `monolith/config.py` originally wrote its SQLite file to the repo root instead of `monolith/instance/` | Path-joining bug fixed; verified the file lands in the right place |



## Teardown

```bash
make teardown    # deletes every Azure resource
make verify      # confirms deletion completed (polls — resource group deletion is asynchronous)
```
<img width="1053" height="167" alt="Screenshot 2026-07-17 at 3 25 45 PM" src="https://github.com/user-attachments/assets/d4b896fe-4b16-4e32-88fd-a02d02ee5d43" />

`make teardown` is a no-op if nothing was ever provisioned (checks for `infra/.state.json` first).

## E-commerce Web App Screenshots

<img width="1469" height="828" alt="Screenshot 2026-07-16 at 8 51 10 PM" src="https://github.com/user-attachments/assets/7289cd89-6e2d-4643-9340-eb9225ff03df" />

<img width="100%" height="1" alt="" src="https://github.com/user-attachments/assets/f2af28ee-a373-4488-89e5-2b84d5da9620" />
<br><br>
<img width="1424" height="699" alt="Screenshot 2026-07-16 at 9 19 20 AM" src="https://github.com/user-attachments/assets/dfc83ddb-0f29-401f-9b95-7ed03a5d38e0" />

<img width="100%" height="1" alt="" src="https://github.com/user-attachments/assets/f2af28ee-a373-4488-89e5-2b84d5da9620" />
<br><br>
<img width="1451" height="871" alt="Screenshot 2026-07-16 at 8 53 08 PM" src="https://github.com/user-attachments/assets/e120982f-3c5a-4c77-969b-d314fbc924cb" />

<img width="100%" height="1" alt="" src="https://github.com/user-attachments/assets/f2af28ee-a373-4488-89e5-2b84d5da9620" />
<br><br>
<img width="1453" height="874" alt="Screenshot 2026-07-16 at 8 55 41 PM" src="https://github.com/user-attachments/assets/21a3924c-1a10-42d9-bac5-d91ecbed7fa5" />

<img width="100%" height="1" alt="" src="https://github.com/user-attachments/assets/f2af28ee-a373-4488-89e5-2b84d5da9620" />
<br><br>
<img width="867" height="394" alt="Screenshot 2026-07-16 at 8 55 27 PM" src="https://github.com/user-attachments/assets/e3ce6232-8f14-440d-8c78-4cfbf257e492" />

<img width="100%" height="1" alt="" src="https://github.com/user-attachments/assets/f2af28ee-a373-4488-89e5-2b84d5da9620" />
<br><br>
<img width="1450" height="983" alt="Screenshot 2026-07-16 at 8 19 08 PM" src="https://github.com/user-attachments/assets/f7b35522-8570-41a9-8f94-6ab789e8046b" />

<img width="100%" height="1" alt="" src="https://github.com/user-attachments/assets/f2af28ee-a373-4488-89e5-2b84d5da9620" />
<br><br>
<img width="1457" height="984" alt="Screenshot 2026-07-16 at 8 23 31 PM" src="https://github.com/user-attachments/assets/9f9e6d00-f69c-4972-9baa-63b2827d3125" />

<img width="100%" height="1" alt="" src="https://github.com/user-attachments/assets/f2af28ee-a373-4488-89e5-2b84d5da9620" />
<br><br>
<img width="1456" height="986" alt="Screenshot 2026-07-16 at 8 18 11 PM" src="https://github.com/user-attachments/assets/1f24690b-f969-43f4-af10-25299730949c" />

<img width="100%" height="1" alt="" src="https://github.com/user-attachments/assets/f2af28ee-a373-4488-89e5-2b84d5da9620" />
<br><br>
<img width="1419" height="613" alt="Screenshot 2026-07-16 at 10 01 46 PM" src="https://github.com/user-attachments/assets/ff847e47-7a3e-4977-a68c-b814ef130a94" />

<img width="100%" height="1" alt="" src="https://github.com/user-attachments/assets/f2af28ee-a373-4488-89e5-2b84d5da9620" />
<br><br>
<img width="892" height="701" alt="Screenshot 2026-07-16 at 10 01 57 PM" src="https://github.com/user-attachments/assets/241ad6ee-342f-4f88-bfbc-9a5b1a737948" />



## Author

**Marcos Oliveira** — [LinkedIn](https://www.linkedin.com/in/mfilho1/) | [GitHub](https://github.com/MAOFILHO)
