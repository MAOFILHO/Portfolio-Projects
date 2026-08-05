---
name: git-repo-to-python-project
description: "Use this skill when I want to transform a cloned Git repo into a brand new, fully automated, production-grade Python project with zero cloud portal clicks, observability, smoke tests, frontend, cost-guarded cloud provisioning, and GitHub-ready structure. Works for Azure and AWS projects. Triggers: 'automate this repo', 'convert this project', 'make this production-grade', 'zero portal clicks'."
---

# SKILL: git-repo-to-python-project

Transform any cloned Git repository into a production-grade, fully automated
Python project. Follow these phases in strict order. Never skip a phase gate.
**Never provision a paid cloud resource without an approved cost estimate.**

---

## PHASE 1 — EXPLORE & UNDERSTAND
*(Do not write any code in this phase)*

### Documentation discovery (in priority order)
1. If a Project Guide PDF is attached — read it first
2. Otherwise read: `README.md`, then all `*.md` files in the repo root and subfolders
3. Then read all config files: `pyproject.toml`, `setup.py`, `requirements*.txt`,
   `package.json`, `docker-compose.yml`, `.env.example`, `Makefile`, etc.
4. Read all notebook files (`.ipynb`) if present
5. Read all source files to understand the full codebase structure

### Detect and report
1. **Architecture overview** — components, data flow, file dependencies
2. **Cloud provider** — Is this Azure, AWS, GCP, or cloud-agnostic?
   Detect from: imports, config files, SDK references, service names
3. **Python version** — Read `pyproject.toml`, `.python-version`, `runtime.txt`,
   or `requirements.txt` to determine the minimum required version.
   Use that version. Do NOT assume 3.12 unless confirmed or no constraint exists.
4. **Frontend stack** — Does the project already have a frontend?
   (React, Vue, Flask, FastAPI with templates, Streamlit, Gradio, etc.)
   If yes: identify it. If no: flag it as missing.
5. **External APIs and accounts required** — flag anything the user must obtain
6. **Every billable cloud resource implied by the codebase** — list each one
   explicitly (e.g. Azure AI Search, Azure OpenAI, Cosmos DB, AKS, App Service,
   AWS OpenSearch, Bedrock, DynamoDB, ECS/Fargate, SageMaker, etc.). This list
   feeds directly into the mandatory cost estimate in Phase 2 — do not omit
   anything, including resources only referenced in config or IaC files.
7. **Gaps, risks, or broken dependencies** in the original codebase
8. **Recommended project folder name** (naming convention: tech-stack-first,
   e.g. AzureRAG-ClinicalDecision, LangGraph-Compliance-Pipeline,
   AWS-Bedrock-CustomerSupport)

---

## PHASE 2 — PLAN, COST ESTIMATE & AWAIT APPROVAL
*(Present the plan. Write zero code and provision zero resources until the
user explicitly approves — including approving the cost estimate.)*

Design the new project applying these rules:

### Language & Python Version
- Detect the required Python version from the original project (see Phase 1 step 3)
- If no version is specified, default to Python 3.12
- Create `.venv` using the detected version: `python3.X -m venv .venv`
- All secrets via `.env` file (never hardcoded, always in `.gitignore`)
- Portable and renameable — no hardcoded folder names or absolute paths

### Cloud Provider & CLI Automation
Detect the cloud provider from the original codebase and automate accordingly:

**If Azure:**
- Zero Azure Portal clicks — all provisioning via `az` CLI only
- All `az` commands include `--output json` for scripting compatibility
- Region and subscription set via `az configure` — never hardcoded in code
- Provision script uses Azure CLI: `az group create`, `az cognitiveservices create`, etc.

**If AWS:**
- Zero AWS Console clicks — all provisioning via `aws` CLI + boto3 only
- All `aws` commands use `--output json` and `--region` from environment variable
- Region set via `AWS_DEFAULT_REGION` env var — never hardcoded in code
- Provision script uses AWS CLI: `aws s3 mb`, `aws bedrock`, `aws iam`, etc.

**If multi-cloud or cloud-agnostic:**
- Provision scripts separated per provider: `provision_azure.py`, `provision_aws.py`
- Shared pipeline logic stays cloud-agnostic
- If a service exists on both clouds, the cost comparison below decides which
  cloud is actually used unless the user has a hard requirement to stay on one

### 💰 COST ESTIMATE & CHEAPEST-SKU SELECTION (mandatory, non-negotiable)

**This is a hard gate. No resource may be provisioned in Phase 3 that was not
listed, costed, and approved here.**

**1. Default to the cheapest SKU/tier that satisfies the functional requirement.**
Never choose a "production-grade" or enterprise SKU by default. Rules of thumb:

| Service | Default cheap choice | Avoid unless user asks for production scale |
|---|---|---|
| Azure AI Search | Free (F0) for dev/test; Basic only if F0 index limits are hit | Standard S1+ tiers (~$250–$5,000+/mo) |
| Azure OpenAI / Cognitive Services | Pay-as-you-go (token/call-based, no idle cost) | Provisioned Throughput Units (PTUs) |
| Azure Cosmos DB | Serverless mode | Provisioned throughput (RU/s) |
| Azure compute | Container Apps / Functions (consumption, scale-to-zero) | AKS (has an always-on cost floor) |
| Azure App Service | Free (F1) or Basic (B1) | Premium (P1v3+) |
| AWS OpenSearch | Smallest single-node dev instance, or use Bedrock Knowledge Bases native vector store instead | Multi-node production domains |
| AWS Bedrock | Pay-per-token, on-demand | Provisioned Throughput |
| AWS DynamoDB | On-demand capacity mode | Provisioned capacity |
| AWS compute | Lambda (pay-per-invocation) | ECS/Fargate always-on, EC2 always-on |
| AWS SageMaker | Serverless inference or local/notebook-only during dev | Real-time endpoints left running |

- If the repo's original code hardcodes an expensive SKU (e.g. Azure AI Search
  Standard), **override it to the cheapest viable tier** for a dev/test build
  and flag the substitution explicitly in the plan — do not silently keep it.
- If the user's stated goal genuinely requires a paid/production tier (e.g.
  index size or throughput exceeds the free tier), say so explicitly, explain
  why, and still pick the *cheapest* SKU that clears the requirement — never
  the highest or "safest" one by default.

**2. Build a cost table for every resource identified in Phase 1**, using
current public pricing (web search current Azure/AWS pricing pages — do not
rely on memorized/training-data prices, they go stale):

| Resource | SKU/Tier chosen | Reason | Est. cost/hour if running | Est. cost for a 1-night test (~8 hrs) | Est. cost if left running 30 days | Cheaper alternative, if any |
|---|---|---|---|---|---|---|

- Sum and clearly bold: **Total estimated cost for this test session** and
  **Total estimated cost if resources are accidentally left running for 30 days**.
- Bold-flag, in red-flag language, any single resource whose 30-day cost
  exceeds **$50 USD** (or the user's stated threshold — ask if unknown).
- If pricing can't be verified live, say so explicitly and mark the figures
  as estimates the user should confirm on the Azure Pricing Calculator or
  AWS Pricing Calculator before approving.

**3. Ask for a budget ceiling before proceeding**, if not already known:
"What's your maximum acceptable spend for this build/test session, and do
you want a hard cloud budget alert set at that amount?"

**4. Mandatory teardown safety net.** For every resource that bills while
idle or running (not pure pay-per-call), the plan must include:
- An automated cloud budget/cost alert (Azure Cost Management budget alert
  via `az consumption budget create`, or AWS Budgets via `aws budgets
  create-budget`) set at the user's approved ceiling, created during
  `provision.py` — not a manual portal step.
- A conspicuous reminder in `run.py` output and in `README.md`: *"Run `make
  teardown` when you're done testing — these resources bill while running."*

### Pipeline Structure
Each stage is a distinct script or Makefile target:
- `setup.py` / `make setup` — install deps, validate env vars, run pre-smoke-test
- `provision.py` / `make provision` — create all cloud resources via CLI only,
  using the exact SKUs approved in the cost estimate (never silently upgrade
  a SKU during build), and creates the budget alert described above
- `run.py` / `make run` — execute pipeline with verbose step-by-step terminal output
- `teardown.py` / `make teardown` — destroy all provisioned cloud resources

### Smoke Tests (non-optional)
- **Pre-setup**: Python version ✓, cloud CLI login ✓, required env vars ✓
- **Post-setup**: All cloud resources live, reachable, and confirmed to be
  the approved (cheap) SKU — not silently defaulted to a pricier tier ✓
- **Post-run**: Expected outputs exist and are non-empty ✓

### Frontend
- **If the original project has a frontend**: keep the existing stack.
  Do not replace React with Streamlit, or Flask with FastAPI, etc.
  Refactor and automate the existing frontend as-is.
- **If no frontend exists**: recommend and implement Streamlit with
  username/password login (streamlit-authenticator). Display pipeline
  status, run logs, and results.
- Always flag the frontend decision explicitly in the Phase 2 plan.

### Observability (always on, never optional)
All traces must be visible in the terminal during execution, not just in cloud portals.

**If Azure:**
- **Infra layer**: Azure Application Insights via opentelemetry-sdk +
  azure-monitor-opentelemetry exporter
- **LLM/agent layer**: Azure AI Foundry Tracing (OpenTelemetry-based) —
  captures prompt→response, token counts, retrieval scores, agent loop steps

**If AWS:**
- **Infra layer**: AWS CloudWatch via opentelemetry-sdk + AWS distro for OTel
- **LLM/agent layer**: LangSmith or Langfuse for LLM/agent tracing

**If cloud-agnostic or no cloud:**
- Default to Langfuse (open-source, self-hostable, works with any LLM stack)

### Docker
- Include `Dockerfile` and `docker-compose.yml` for local dev
- Assume Docker Desktop is running on Mac

### Documentation
Every project must include:
- `README.md` — business case (from Project Guide or original README) +
  architecture diagram (ASCII) + prerequisites + quickstart +
  env var reference table + **cost table from the approved estimate** +
  teardown instructions. At the end of the README, add this section:
  "## Author **Marcos Oliveira** — [LinkedIn](https://www.linkedin.com/in/mfilho1/) | [GitHub](https://github.com/MAOFILHO)"
- `CLAUDE.md` — project re-entry context for future Claude Code sessions
  (stack, folder map, detected Python version, cloud provider, SKUs
  provisioned and their approved cost, how to run, what's been done,
  what's pending)
- `CHANGELOG.md` — initialized with v0.1.0 entry
- `cost_estimate.md` — the full cost table and assumptions from Phase 2,
  kept as a permanent record of what was approved
- Inline comments throughout all Python files

---

## PHASE 2 DELIVERABLE (for user review)
Present:
1. Detected Python version and source of that detection
2. Detected cloud provider and evidence (which files/imports confirmed it)
3. Frontend decision: existing stack kept OR Streamlit recommended (with reason)
4. Proposed folder/file tree
5. `requirements.txt` with all packages and pinned versions
6. **Full cost table** (resource, SKU, reason, hourly/test-session/30-day cost,
   cheaper alternatives) **with a bolded total and any >$50/mo flags**
7. Proposed budget ceiling and whether a cloud budget alert will be created
8. List of cloud resources + exact CLI commands to provision them
9. List of APIs/accounts the user must obtain before proceeding
10. Any assumptions being made (including any pricing assumptions)
11. Estimated number of files to be created

**Hard stop. Await explicit approval of BOTH the technical plan AND the cost
estimate before Phase 3. If the user only approves the plan but not a budget
ceiling, ask for the ceiling before provisioning anything.**

---

## PHASE 3 — BUILD
*(Only after user approves the Phase 2 plan and cost estimate)*

- Reuse and refactor the existing codebase — do not rewrite from scratch
- Build each pipeline stage in order: setup → provision → run → teardown
- `provision.py` must provision exactly the SKUs approved in Phase 2 — if a
  CLI command would default to a pricier SKU when a flag is omitted, the
  flag must be explicit in the script (e.g. always pass `--sku free` /
  `--sku basic`, never rely on the CLI's own default)
- `provision.py` creates the cloud budget alert at the approved ceiling
  before creating any billable resource
- Wire observability first (before pipeline logic) so every step is traced
- Create or integrate frontend last (depends on pipeline being stable)
- Generate all documentation files, including `cost_estimate.md`

---

## PHASE 4 — VALIDATE
1. Run pre-smoke-tests — report pass/fail per check
2. Execute `make setup` and `make provision` — show terminal output,
   including confirmation that each resource was created at the approved SKU
3. Run post-setup smoke tests
4. Execute `make run` — confirm pipeline completes end-to-end
5. Run post-run smoke tests
6. Confirm frontend launches locally
7. Remind the user out loud: *"Resources are live and billing. Run `make
   teardown` when you're done testing."*

---

## PHASE 5 — PACKAGE & HANDOFF
1. Verify `.gitignore` excludes: `.env`, `.venv/`, `__pycache__/`,
   `*.pyc`, `.azure/`, `.aws/`, any credential or token files
2. Confirm no secrets are present anywhere in committed files
3. Confirm project folder is self-contained and renameable
4. Confirm `CLAUDE.md` and `cost_estimate.md` are complete for future re-entry
5. Remind the user one final time to run `make teardown` if resources are
   still live and no longer needed
6. Inform user: "Project is GitHub-ready. Run `git init && git add . && git commit -m 'Initial commit'` to push."

---

## OUTPUT CHECKLIST (every project must have all of these)
- [ ] `.venv` setup with detected Python version (default 3.12 if unspecified)
- [ ] `.env.example` with all required keys (no values)
- [ ] `.gitignore`
- [ ] `requirements.txt` with pinned versions
- [ ] `Makefile` with: setup, provision, run, teardown, test targets
- [ ] `Dockerfile` + `docker-compose.yml`
- [ ] `setup.py` with pre-smoke-tests
- [ ] `provision.py` using cloud CLI only (az or aws — no portal), explicit
      cheap SKU flags, and automated budget alert creation
- [ ] `run.py` with verbose terminal output and a teardown reminder
- [ ] `teardown.py`
- [ ] `tests/` folder with smoke test scripts
- [ ] Frontend: existing stack kept OR new Streamlit app (decision logged in CLAUDE.md)
- [ ] `README.md` (includes cost table)
- [ ] `CLAUDE.md`
- [ ] `CHANGELOG.md`
- [ ] `cost_estimate.md` — approved cost table, kept as permanent record
- [ ] Cloud budget/cost alert created at approved ceiling
- [ ] Observability wired (cloud-appropriate stack, always on)
