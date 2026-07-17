# Changelog

## v0.1.3 — Cloud-native live migration: Azure by default, local optional

The flagship experience is now Azure-hosted: `make provision` deploys **only** the monolith (plus
the BFF and foundation resources) — the microservices' Container Apps do not exist yet. Clicking
**Start Migration** makes the BFF create each one for real, live, via the Azure SDK, using its own
scoped managed identity — the wow-factor being watching real Azure resources appear as the
migration runs, not a pre-provisioned stack where migration just flips a switch. Local dev remains
fully supported and unchanged.

- **`infra/bicep/main.bicep`** trimmed to deploy only the foundation (ACR, Container Apps
  Environment, MySQL Flexible Server, Static Web App, Log Analytics) plus the `monolith` and `bff`
  Container Apps. The `bff` Container App now gets a system-assigned managed identity.
- **`infra/provision.py`**: still pre-builds all 5 service images via `az acr build` up front (so
  the live migration only has to create Container Apps, not build images on camera), grants the
  bff's managed identity `Contributor` scoped to just the one resource group, and persists ACR/MySQL
  secrets to the gitignored `infra/.state.json` for human/teardown reference (the running bff itself
  gets these via its own env vars, injected directly by Bicep — it never reads that file, since it
  doesn't exist inside the container).
- **`bff/app/azure_traffic.py`**: rewritten from "scale an existing Container App" to "create a
  microservice's Container App for the first time" (`azure.mgmt.appcontainers` SDK,
  `begin_create_or_update`), reading every value it needs from its own env vars rather than a state
  file. Also exposes `scale_monolith()` for the local-mirroring "restart monolith" undo path.
- **`bff/app/migration_engine.py`**: extraction steps now create Container Apps and update a new
  runtime URL registry (`config.RUNTIME_BASE_URLS`) instead of assuming a pre-existing one to scale;
  `snapshot()` now reports `mode: "local" | "azure"` so the frontend can adapt.
- **`bff/app/config.py`** / **`bff/app/routers/shop.py`**: added `RUNTIME_BASE_URLS`, a mutable
  registry the shop proxy reads from instead of static constants — in azure mode the microservices'
  URLs don't exist until the migration creates them.
- **New `GET /api/services`** endpoint reports the BFF's live registry; **`scripts/benchmark.py`**
  now fetches its target URLs from there (falling back to localhost defaults if the BFF isn't
  reachable) instead of hardcoding ports, so the same script works unmodified against Azure.
- **Frontend**: Shop hides the Monolith/Microservices toggle in azure mode and follows
  `migration.active_backend` automatically (no side-by-side view in the cloud, unlike local
  `make run-all`); Migrate hides the local/azure mode selector once running in Azure and adapts its
  copy to describe the on-demand creation story.
- **7 new bff unit tests** covering the on-demand creation wiring and registry updates (Azure SDK
  calls are mocked — these are unit tests of the wiring, not integration tests against real Azure).
- `cost_estimate.md` and `README.md` updated: the actual SKUs/pricing are unchanged from the
  original approval (~$19.51/mo if left running), only the timing of when each Container App gets
  created changed. New line item: a Contributor role assignment (free, control-plane only).

## v0.1.2 — Product catalog seeding, migration UX, and benchmark data hygiene

- **Product catalog seeding** (`monolith/app/seed.py`, `microservices/product-service/application/seed.py`):
  both backends now auto-seed a 24-product Contoso catalog (mugs, apparel, desk accessories, etc.)
  on first local startup — idempotent, only inserts when the table is empty — so the Shop page has
  a realistic, varied catalog immediately instead of requiring a manual "Add sample products" click.
- **Registering an already-taken username crashed with a raw Werkzeug debugger page** (500) instead
  of a friendly error, in both the monolith and user-service. Now caught (`IntegrityError`) and
  returned as a clean 409 "Username or email is already taken".
- **Clicking into the Monolith tab after a migration decommissioned it showed a scary raw
  `TypeError: Failed to fetch`** with no explanation and no way back. Shop now disables the
  Monolith toggle and explains what happened once the migration's "Decommission" step completes;
  added a real "Restart monolith" action (both in Shop and on the Migrate page) that respawns the
  process (local) — the existing "Reset" button now does the same restart instead of just resetting
  UI state while leaving the process dead.
- **Benchmark runs polluted the shared product catalog** (`scripts/benchmark.py`): every
  `create_product` benchmark left its throwaway `bench-*` rows in the database permanently — after
  enough runs, the Shop catalog had 200+ junk products. Added a `DELETE /api/product/<slug>`
  endpoint to both the monolith and product-service, and `benchmark.py` now cleans up every product
  it creates immediately after measuring it.

## v0.1.1 — Hardening from real end-to-end usage

Found and fixed while actually clicking through the running app in a browser (not just via
automated tests) — each of these is a real bug, not a hypothetical:

- **CORS origin mismatch** (`bff/app/config.py`, `bff/app/main.py`): browsers treat `localhost`
  and `127.0.0.1` as different origins even though they're the same machine. The BFF only
  whitelisted `127.0.0.1:5173`, so visiting via `localhost:5173` made every fetch fail with a
  generic `TypeError: Failed to fetch` and no indication it was CORS. Now both are allowed by
  default in local dev (an explicit `FRONTEND_ORIGIN` override still locks it to exactly one
  origin, e.g. for a real Azure Static Web Apps hostname).
- **Shop page had no register/login/cart/checkout UI at all** (`frontend/src/pages/Shop.tsx`,
  `frontend/src/api/bffClient.ts`): it only ever listed products read-only, even though the
  underlying APIs and smoke tests for the full flow already existed. Rebuilt with register/login
  forms, add-to-cart, a cart view, and checkout — verified end-to-end in a real browser on both
  the monolith and the microservices backends.
- **No total shown anywhere in the cart or checkout** — a real e-commerce gap, not a cosmetic one.
  Added per-line subtotals and a running total, shown both in the cart and on the Checkout button
  itself (e.g. "Checkout — $37.98").
- **Benchmark was all-or-nothing** (`scripts/benchmark.py`, `bff/app/schemas.py`,
  `bff/app/routers/metrics.py`, `frontend/src/pages/Metrics.tsx`): it refused to run unless both
  the monolith and product-service were reachable, even though "only the monolith is up" (before
  migrating) and "only the microservices are up" (after migrating) are both completely legitimate
  states to measure. Now measures whichever backend(s) are actually running and records which ones
  in a `measured` field; the Metrics page only renders bars for what was actually measured, with an
  explicit note when a comparison is partial. Also hardened the `/api/metrics/latest` endpoint to
  skip old-format result files instead of crashing with a validation error.
- **`scripts/setup.py` didn't create the root-level dev venv** that `make test`/`make smoke`/
  `make benchmark` actually depend on — only the 5 per-service venvs. Fixed, and verified for real
  by wiping every venv and running `make setup` from a totally fresh state.
- **`scripts/setup.py` trusted `sys.executable`** for venv creation instead of resolving an
  explicit `python3.12` binary — now explicitly resolves and prints the exact `python3.12` path
  used (with Homebrew-path fallbacks) and prints the literal `python3.12 -m venv <path>` command
  for every venv it creates.
- **The "Decommission" migration step hung forever** (`bff/app/migration_engine.py`):
  `psutil.net_connections()` requires root on macOS and raised `AccessDenied`, which wasn't caught
  anywhere, silently escaping the step loop and leaving it stuck in "running" forever. Fixed by
  switching to per-process `Process.net_connections()` (doesn't need root) and by wrapping every
  step in `run()` with exception handling so any failure always resolves the step's status instead
  of hanging.
- **Port-collision self-heal didn't recognize this project's own leftover processes under their
  real invocation pattern** (`scripts/_procutil.py`): every service in this project is launched
  with `cwd=<service_dir>` and a bare `run.py`/`uvicorn ...` command line — no repo path in the
  command line at all. The original ownership check only looked at the command line, so it failed
  to recognize a genuine leftover instance of this project and would have wrongly treated it as
  foreign. Now also checks the process's working directory via `lsof -d cwd`.
- **`monolith/config.py` wrote its SQLite file to the repo root** instead of `monolith/instance/`
  (a `Path(...).name` bug that discarded the subdirectory). Fixed; verified the file lands in the
  right place.
- **Local SQLite tables didn't exist until a migration was run manually** — added automatic
  `db.create_all()` for `RUN_MODE=local` in the monolith and all three microservices, so `make run`
  just works without requiring `flask db upgrade` first (Azure/MySQL deploys still use proper
  Flask-Migrate migrations, unaffected).

## v0.1.0 — Initial release

- Monolith (`monolith/`): single Flask 3.1 app combining auth, catalog, and order logic in one
  shared schema — the "before" state, modernized from the original 4-project course repo.
- Microservices (`microservices/`): user-service, product-service, order-service — each an
  independently deployable Flask 3.1 app with its own database, order-service calling
  user-service over HTTP (Anti-Corruption Layer) instead of joining a shared schema.
- FastAPI BFF (`bff/`): proxies the frontend to either backend, drives a real (not simulated)
  strangler-fig migration — local mode starts/stops actual Python processes; Azure mode shifts
  real Container Apps traffic — serves Learn content and benchmark metrics.
- React + TypeScript frontend (`frontend/`): Contoso-themed, with Home, Shop, Migrate, Learn, and
  Metrics pages.
- Local dev: zero Docker, zero cloud, zero cost — plain Python/Node processes with SQLite,
  self-healing against leftover processes on their ports.
- Azure infra (`infra/`): Bicep templates + `provision.py`/`teardown.py`, cheapest SKUs
  (Consumption Container Apps scale-to-zero, MySQL Burstable B1ms, ACR Basic, Static Web Apps
  Free), naming-collision auto-increment tested against real Azure, Cost Management budget alert.
- Pydantic request/response validation across every service (Flask apps via a shared
  `validate_form` helper, BFF natively via FastAPI).
- Benchmark harness (`scripts/benchmark.py`): real before/after latency/throughput comparison,
  hitting the monolith and a microservice directly (bypassing the BFF) for a fair, apples-to-apples
  measurement.
- Unit tests (38, across 6 suites) + smoke tests (pre-setup, post-setup, post-run,
  post-teardown), all passing.
