# CLAUDE.md — re-entry context

## What this project is
A portfolio piece showing a real before/after microservices migration: the exact same
e-commerce app (register/login, product catalog, cart, checkout) running two ways —
`monolith/` (one Flask process, one shared DB) and `microservices/` (three independently
deployable Flask services, each with its own DB). A React/TypeScript frontend (Contoso theme)
lets a visitor click "Migrate" and watch a **real** strangler-fig cutover happen (local mode
actually starts/stops Python processes; Azure mode shifts real Container Apps traffic), see
real before/after performance metrics, and read Learn content sourced from the migration study
guides that informed this build.

Built from `python-flask-microservices` (an old CloudAcademy Flask/Docker course repo) via the
`git-repo-to-python-project` skill.

## Stack & versions
- **Python 3.12** everywhere (monolith, all 3 microservices, bff, scripts, tests) — the original
  repo pinned Flask 1.1.1/Werkzeug 1.0.1 (2020-era, incompatible with Python 3.10+); this was a
  deliberate modernization to Flask 3.1 / SQLAlchemy 2.0, flagged explicitly during planning.
- **Node 18+** for the frontend (React 18, TypeScript 5, Vite 5).
- **Both the monolith and the microservices are Flask** — FastAPI is used *only* for the BFF, a
  separate orchestration/proxy layer, not part of either side being compared. This matters for
  the benchmark: `scripts/benchmark.py` hits the monolith and product-service *directly* (ports
  6000 and 5002), bypassing the BFF, so the comparison stays apples-to-apples (Flask vs. Flask,
  one process/DB vs. three).
- **Pydantic** everywhere: FastAPI natively in the BFF (`bff/app/schemas.py`); a shared
  `validate_form()` helper in each Flask app's `schemas.py`/`validation.py` (no framework-native
  support in Flask, so it's done explicitly).
- **No Docker Desktop / no local containers, ever.** Dockerfiles exist per service but are only
  built via `az acr build` (cloud-side). Local dev/run is 100% plain Python/Node processes.
- Local DB = SQLite (per service, in its own `instance/` dir, auto-created via `db.create_all()`
  when `RUN_MODE=local`). Azure DB = Azure Database for MySQL Flexible Server (Burstable B1ms,
  one server, 4 logical databases) — proper Flask-Migrate migrations apply there instead.

## Folder map
```
monolith/                    BEFORE — single Flask app (app/{auth,catalog,orders})
microservices/{user,product,order}-service/   AFTER — 3 independent Flask apps (application/)
bff/                          FastAPI orchestration: shop proxy, migration_engine, benchmark, learn content
frontend/                     React+TS+Vite, Contoso theme, pages: Home/Shop/Migrate/Learn/Metrics
infra/                        Bicep templates + provision.py/teardown.py/verify_teardown.py/name_resolver.py
scripts/                      setup.py, run_local.py (+ _procutil.py port self-heal), benchmark.py
tests/                        smoke/ (HTTP-based, repo-root venv) + unit/ (name_resolver, migration_engine, procutil)
monolith/tests/, microservices/*/tests/, bff/tests/   per-service unit tests, run with that service's OWN venv
```

**Important collision note**: `monolith/app/` and `bff/app/` are both top-level packages named
`app` (and every Flask service has its own top-level `config.py`). This is fine when each runs in
its own process/venv, but breaks if you ever try to put multiple service directories on
`sys.path` in one Python process — `tests/conftest.py` deliberately only adds `infra/`,
`scripts/`, and `bff/` (never `monolith/` or the microservices) for exactly this reason.

## Cloud provider & cost
Azure, chosen by the user for the live-demo deployment (not detected from the original repo,
which was cloud-agnostic Docker Compose). See `cost_estimate.md` for the full approved cost
table: **~$0.21 for an 8-hr test session, ~$19.51/mo if left running** (MySQL Flexible Server is
the only resource that bills while idle — Container Apps default to scale-to-zero). Budget
ceiling: $25/mo, enforced via an `az consumption budget` alert created in `provision.py` before
any billable resource.

**As of this writing, nothing has been deployed live to Azure** — the user chose to have
`provision.py`/`teardown.py` fully built and tested, but not run for a live stand-up. The one
real Azure action taken during this build was a throwaway ACR (created, collision-tested,
deleted within ~2 minutes) to verify `infra/name_resolver.py`'s auto-increment logic actually
works — see below.

## Known-tricky things already solved here
- **ACR names are alphanumeric-only (no hyphens).** `name_resolver.py`'s `_candidate_names()`
  takes an `alphanumeric_only` flag for exactly this — verified for real: a throwaway ACR was
  created, the collision check correctly reported it unavailable, and the first hyphenated
  increment attempt (`name-2`) was *also* rejected by Azure as `Invalid` (not `Taken`), which
  originally caused the resolver to exhaust all 20 attempts. Fixed by switching ACR's suffix
  scheme to `name2`, `name3`, ... (no separator).
- **Flask's dev reloader spawns a child process on the same port.** The port-collision
  self-heal in `scripts/_procutil.py` snapshots every PID's cmdline *before* killing any of
  them — killing the parent can cascade-kill the child, and checking cmdlines lazily one-by-one
  would see an empty cmdline for the already-dead child and wrongly treat it as an unrecognized
  foreign process.
- **`monolith/config.py` originally placed its SQLite file at the repo root** instead of
  `monolith/instance/` (a `Path(...).name` bug that discarded the subdirectory). Fixed; verified
  by checking the file actually lands in `monolith/instance/monolith.sqlite3`.
- **Benchmark fairness**: must hit ports 6000 (monolith) / 5002 (product-service) directly, never
  through the BFF (port 8000) — the BFF is infrastructure, not part of what's being measured.

## How to run
```bash
make setup          # installs everything (5 Python venvs + frontend npm deps), zero Docker
make run             # monolith + bff + frontend (microservices start live via the Migrate page)
make run-all         # same, but also starts all 3 microservices immediately
make test            # 38 unit tests across 6 suites (repo-root, monolith, 3 microservices, bff)
make smoke           # pre-setup/post-setup/post-run/post-teardown smoke tests (skip gracefully if not applicable)
make benchmark       # real before/after perf comparison (monolith vs. product-service)
make provision BUDGET_EMAIL=you@example.com    # stands up the Azure stack — costs money, see cost_estimate.md
make teardown        # deletes everything
make verify           # polls until the resource group is confirmed fully deleted
```

## What's pending / not done
- Live Azure deployment has never been run end-to-end (by user's choice) — `provision.py` is
  built and its naming-collision logic is proven against real Azure, but the full Bicep
  deployment (`az deployment group create`) has not itself been executed for real. If picking
  this up: run `make provision` once, watch for the first real end-to-end deployment issues
  (Bicep syntax validated with `az bicep build`, but never applied), then `make teardown` +
  `make verify` right after.
- Frontend has not been opened in a real browser yet in this session — only `curl`/`httpx`
  smoke-tested. Worth a manual click-through before considering the UI fully done.
