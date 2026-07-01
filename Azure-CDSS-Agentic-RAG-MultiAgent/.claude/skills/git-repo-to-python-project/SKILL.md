---
name: git-repo-to-python-project
description: "Use this skill when I want to transform a cloned Git repo into a brand new, fully automated, production-grade Python project with zero cloud portal clicks, observability, smoke tests, frontend, and GitHub-ready structure. Works for Azure and AWS projects. Triggers: 'automate this repo', 'convert this project', 'make this production-grade', 'zero portal clicks'."
---

# SKILL: git-repo-to-python-project

Transform any cloned Git repository into a production-grade, fully automated 
Python project. Follow these phases in strict order. Never skip a phase gate.

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
6. **Cloud resources that need to be provisioned**
7. **Gaps, risks, or broken dependencies** in the original codebase
8. **Recommended project folder name** (naming convention: tech-stack-first,
   e.g. AzureRAG-ClinicalDecision, LangGraph-Compliance-Pipeline,
   AWS-Bedrock-CustomerSupport)

---

## PHASE 2 — PLAN & AWAIT APPROVAL
*(Present the plan. Write zero code until the user explicitly approves.)*

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

### Pipeline Structure
Each stage is a distinct script or Makefile target:
- `setup.py` / `make setup` — install deps, validate env vars, run pre-smoke-test
- `provision.py` / `make provision` — create all cloud resources via CLI only
- `run.py` / `make run` — execute pipeline with verbose step-by-step terminal output
- `teardown.py` / `make teardown` — destroy all provisioned cloud resources

### Smoke Tests (non-optional)
- **Pre-setup**: Python version ✓, cloud CLI login ✓, required env vars ✓
- **Post-setup**: All cloud resources live and reachable ✓
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
  env var reference table + teardown instructions
- `CLAUDE.md` — project re-entry context for future Claude Code sessions
  (stack, folder map, detected Python version, cloud provider, how to run,
  what's been done, what's pending)
- `CHANGELOG.md` — initialized with v0.1.0 entry
- Inline comments throughout all Python files

---

## PHASE 2 DELIVERABLE (for user review)
Present:
1. Detected Python version and source of that detection
2. Detected cloud provider and evidence (which files/imports confirmed it)
3. Frontend decision: existing stack kept OR Streamlit recommended (with reason)
4. Proposed folder/file tree
5. `requirements.txt` with all packages and pinned versions
6. List of cloud resources + exact CLI commands to provision them
7. List of APIs/accounts the user must obtain before proceeding
8. Any assumptions being made
9. Estimated number of files to be created

**Hard stop. Await explicit approval before Phase 3.**

---

## PHASE 3 — BUILD
*(Only after user approves the Phase 2 plan)*

- Reuse and refactor the existing codebase — do not rewrite from scratch
- Build each pipeline stage in order: setup → provision → run → teardown
- Wire observability first (before pipeline logic) so every step is traced
- Create or integrate frontend last (depends on pipeline being stable)
- Generate all documentation files

---

## PHASE 4 — VALIDATE
1. Run pre-smoke-tests — report pass/fail per check
2. Execute `make setup` and `make provision` — show terminal output
3. Run post-setup smoke tests
4. Execute `make run` — confirm pipeline completes end-to-end
5. Run post-run smoke tests
6. Confirm frontend launches locally

---

## PHASE 5 — PACKAGE & HANDOFF
1. Verify `.gitignore` excludes: `.env`, `.venv/`, `__pycache__/`,
   `*.pyc`, `.azure/`, `.aws/`, any credential or token files
2. Confirm no secrets are present anywhere in committed files
3. Confirm project folder is self-contained and renameable
4. Confirm `CLAUDE.md` is complete for future re-entry
5. Inform user: "Project is GitHub-ready. Run `git init && git add . && git commit -m 'Initial commit'` to push."

---

## OUTPUT CHECKLIST (every project must have all of these)
- [ ] `.venv` setup with detected Python version (default 3.12 if unspecified)
- [ ] `.env.example` with all required keys (no values)
- [ ] `.gitignore`
- [ ] `requirements.txt` with pinned versions
- [ ] `Makefile` with: setup, provision, run, teardown, test targets
- [ ] `Dockerfile` + `docker-compose.yml`
- [ ] `setup.py` with pre-smoke-tests
- [ ] `provision.py` using cloud CLI only (az or aws — no portal)
- [ ] `run.py` with verbose terminal output
- [ ] `teardown.py`
- [ ] `tests/` folder with smoke test scripts
- [ ] Frontend: existing stack kept OR new Streamlit app (decision logged in CLAUDE.md)
- [ ] `README.md`
- [ ] `CLAUDE.md`
- [ ] `CHANGELOG.md`
- [ ] Observability wired (cloud-appropriate stack, always on)
