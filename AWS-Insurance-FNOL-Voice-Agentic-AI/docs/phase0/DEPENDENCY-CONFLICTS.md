# Dependency Conflict Report — Phase 0

Surfaced now rather than at first install. Version strings are quoted verbatim from the source repos.

## Summary of the resolution

We inherit **no dependency tree**. Every conflict below resolves to "discard and start clean," because the
merge matrix keeps only small artifacts (a Pydantic schema, prompts, taxonomies, JSON fixtures) rather than
any repo's runtime. The value of this report is therefore mostly **negative knowledge** — the traps to avoid
when we write our own pins.

**Our baseline:**

```toml
requires-python = ">=3.12,<3.13"
```

- Exact pins, no unbounded `>=`, plus a committed lockfile.
- Pydantic **v2** with `ConfigDict` (never `class Config`).
- `langchain-core` 0.3.x + `langgraph` 0.6.x, **with upper bounds** (see C2).
- Every import declared — no reliance on the Lambda-provided or ambient `boto3`.

---

## Language runtime floors

| Repo | Declared runtime | Verdict |
|---|---|---|
| 1 | `FROM public.ecr.aws/lambda/python:3.10` (README says "3.9 or later") | Below our floor |
| 2 | **`nodejs14.x`** (prose only, `lab1 README:94`) | **EOL 2023-12-04; no longer creatable** |
| 3 | **`Runtime: python3.8`** ×5 (`template.yaml` lines 46, 173, 184, 198, 209) | **EOL 2024-10-14; creation blocked since Feb 2025 — this template cannot deploy today** |
| 4 | None declared | — |
| 5 | None declared (no `python_requires`, no pyproject) | — |
| 6 | `FROM python:3.13-slim`; skill doc says "Python 3.12+", "Node.js 22.x", "CDK 2.235+" | Above our ceiling |
| 7 | `FROM python:3.11-slim` only; `numpy>=2.3.0` implies ≥3.11 | Below our floor |
| 8 | `python:3.12-slim` (Dockerfile); frontend implies Node 18 | Matches |

**Resolution:** Python 3.12 everywhere; Node 22 for the Vite frontend. No repo's runtime is adopted.

---

## C1 — Repo 1's LangChain is pre-0.1 and uses removed APIs

```
boto3==1.28.60
langchain==0.0.309
transformers==4.34.0
pandas==2.1.1
```

`langchain==0.0.309` predates the 0.1 restructuring and depends on `langchain.llms.bedrock.Bedrock` with
`bedrock.predict()`, plus `langchain.pydantic_v1` — all **removed**. There is no upgrade path; the calling
code must be rewritten regardless.

Also: `transformers` and `pandas` are declared and **never imported** — roughly 1 GB of container image for
nothing, on top of the ECR storage cost.

**Resolution:** discard. Start clean on `langchain-core` 0.3.x + `langgraph` 0.6.x.

---

## C2 — Repo 7 pins everything as an unbounded floor, with no lockfile

Verbatim from `requirements-production.txt` (excerpt):

```
langgraph>=0.6.7
langchain>=0.3.27
langchain-core>=0.3.75
langchain-community>=0.3.29
langchain-experimental>=0.3.4
langchain-openai>=0.3.32
langchain-ollama>=0.3.7
langchain-postgres>=0.0.15
langchain-redis>=0.2.3
langchain-text-splitters>=0.3.11
langsmith>=0.4.27
pydantic>=2.10.0
fastapi>=0.115.0
```

Every one of ~35 entries is `>=` with **no upper bound and no lockfile**, so `pip install` resolves to
whatever is newest. Given the LangGraph 0.6 → 1.x API churn this is a live breakage risk, not a theoretical
one.

Note also that `langchain-postgres`, `langchain-redis` and `langchain-text-splitters` are **declared and
never imported** — there is no retrieval or vector store in that repo at all.

**Resolution:** pin exact versions with upper bounds on the LangGraph/LangChain family specifically, since
that is where the churn is. Commit a lockfile.

---

## C3 — Repo 7's two requirements files are mutually unsatisfiable

`requirements-production.txt` vs `requirements-analytics.txt`:

| Package | production | analytics | Conflict |
|---|---|---|---|
| `numpy` | `>=2.3.0` | `==1.24.3` | **Direct contradiction** |
| `pandas` | `>=2.2.3` | `==2.0.3` | **Direct contradiction** |
| `torch` / `torchvision` | — | `torch>=2.8.0` + `torchvision==0.15.2` | **Incompatible pair** — 0.15.2 pairs with torch 2.0 |
| `pmdarima` | — | `==2.0.3` | Requires `numpy<2`, contradicting `numpy>=2.3.0` |

These two files cannot be installed into the same environment.

**Resolution:** discard both. `actuarial_models.py`, the only consumer of the analytics tree, is discarded
(762 LOC of sklearn/xgboost/statsmodels — won't fit a Lambda layer or the budget).

---

## C4 — Imported but undeclared (deploy-time crashes)

Repo 7 imports modules absent from all three of its requirements files:

| Import | Where | Consequence |
|---|---|---|
| `boto3` | `shared/observability.py:15` | Relies on ambient install |
| `aws_xray_sdk` (+ `patch_all()` at module import) | `shared/observability.py:16-17,41` | **Any module importing observability crashes on import** |
| `langgraph-checkpoint-redis` | `langgraph_shared_memory.py:21-22`, in a `try/except ImportError` | `RedisSaver is None` always → silent degradation to `MemorySaver`. Even if installed, `RedisSaver(self.redis_client)` is the wrong constructor. **The "durable Redis checkpointer" never runs** |

Repo 3 has **no `requirements.txt` at all** across five Lambdas, relying on the Lambda-provided boto3
(unpinned, implicit). Repo 5 declares `boto3` with no version.

**Resolution:** declare every import explicitly with a pin. Treat "works because the runtime happens to
provide it" as a defect.

---

## C5 — Pydantic v1 vs v2 — good news

| Repo | Version | Note |
|---|---|---|
| 6 | `pydantic>=2.5.0` | **v2** ✅ — and `claim_schema.py` (a KEEP) is idiomatic v2 with `alias` + `populate_by_name` |
| 7 | `pydantic>=2.10.0` | **v2** ✅ but `enhanced_models.py:146` uses the deprecated v1-style `class Config: use_enum_values = True` |
| 8 | `pydantic==2.11.7` | **v2** ✅, exactly pinned |
| 1, 2, 3, 4, 5 | Not used | — |

**No v1/v2 split exists in this corpus.** The one carry-forward schema file is already v2.

**Resolution:** v2 throughout; convert repo 7's `class Config` to `model_config = ConfigDict(...)` when
refactoring `enhanced_models.py`.

---

## C6 — boto3 / botocore floors

| Repo | Pin |
|---|---|
| 1 | `boto3==1.28.60` (Sep 2023 — predates Bedrock Converse API and current inference-profile support) |
| 5 | `boto3` (unpinned) |
| 6 | `boto3>=1.34.0`, `botocore>=1.34.0` |
| 7 | **undeclared** despite `import boto3` |
| 8 | `boto3==1.42.4` |
| 3 | undeclared (Lambda-provided) |

**Resolution:** pin a recent boto3 explicitly. This matters more than it looks: we depend on
`bedrock-runtime` **Converse** plus **cross-region inference profiles** (`us.*`), which repo 1's 1.28.60
would not support. The Lambda-provided boto3 also lags, so we ship our own.

---

## C7 — Agent framework divergence (not a conflict, but decisive)

**No repo uses LangChain or LangGraph on the voice path.**

| Repo | Agent framework |
|---|---|
| 6 | `strands-agents>=0.2.19` + `strands-agents[bidi-all]` + `bedrock-agentcore` (Nova Sonic bidirectional) |
| 8 | `strands-agents==1.5.0` + `bedrock-agentcore` |
| 7 | LangGraph 0.6.x — but against **self-hosted Ollama**, not Bedrock, and largely non-functional |

**And no repo uses MCP at all** — zero references across all eight.

**Resolution:** not a version conflict; it confirms that the entire agentic layer (LangGraph graph, Bedrock
integration, DynamoDB checkpointer, MCP servers) is greenfield. Strands is not adopted — LangGraph is
specified, and its explicit inspectable state is the point.

---

## C8 — Known-vulnerable and malformed pins to avoid

| Item | Repo | Issue |
|---|---|---|
| `requests==2.31.0` | 8 (`full_automation`) | **CVE-2024-35195, CVE-2024-47081** — fixed in 2.32.0+ |
| `aws-sdk` `^2.1692.0` | 5 (React) | AWS SDK for JS **v2 is EOL**; also dead weight alongside `@aws-sdk/*` v3 |
| `aws-amplify ^5.3.20` | 6 (React) | v5 while v6 is current |
| `@aws-sdk/{protocol-http,signature-v4} ^3.370.0` | 6 | Deprecated in favour of `@smithy/*` |
| `aws-sdk` v2 (`require('aws-sdk')`) | 2 | EOL, and imported-but-unused |
| `prompt-toolkit` | 6 | **Wrong package name** — the real package is `prompt_toolkit`. A supply-chain smell |
| `"install": "^0.13.0"`, `"npm": "^10.9.2"`, `"uninstall": "0.0.0"` | 6 (root `package.json`) | **Cargo-culted typo packages** — three unrelated packages that do nothing here. A genuine supply-chain smell |
| `react-scripts 5.0.1` + a 10-entry `resolutions` block (`nth-check`, `postcss`, `loader-utils`, `semver`, `cross-spawn`, `minimatch`, `terser`, `shell-quote`, `node-forge`, `tough-cookie`) | 6 | The authors knew CRA's transitive tree was full of CVEs and papered over it. We use Vite, which avoids the whole tree |
| `constructs>=10.0.0`, duplicated line | 5 | Missing upper bound for a CDK v2 project; also a literal duplicate entry |
| `scikit-learn`, `pandas`, `numpy` unpinned and **entirely unused** by the backend | 8 | ~300 MB of dead image weight |

**Resolution:** none of these enter our tree. Pre-commit runs `detect-secrets` and `gitleaks`; dependency
scanning runs in CI (Phase 10).

---

## C9 — Frontend toolchain

All three frontends are **Create React App** (`react-scripts 5.0.1`), variously with Cloudscape (repo 5),
Amplify v5 + class components (repo 6), or a single 805-line `App.js` (repo 8).

**Resolution:** discard all three. We use **React + TypeScript + Vite** per the engineering constraints,
which also sidesteps CRA's transitive CVE tree entirely (C8).

---

## C10 — IaC tooling divergence

| Repo | IaC |
|---|---|
| 1 | Raw CloudFormation + bash (`--disable-rollback`, which leaves half-built stacks) |
| 2 | **None** — console click-through only |
| 3 | AWS SAM (published to SAR) |
| 4 | None |
| 5 | CDK v2 **Python** |
| 6 | CDK v2 **TypeScript** (with cdk-nag) |
| 7 | Terraform + raw Kubernetes YAML |
| 8 | CDK v2 **TypeScript** |

Five different approaches across eight repos; nothing to inherit.

**Resolution:** **Terraform ≥1.9, single tool** (constraint 6). Mixing is forbidden.

⚠ **One exception is proposed, and it is not a mix.** Terraform's `aws_lexv2models_*` resources carry open
bugs precisely where we need them — `prompt_specification` updates silently dropped
([#42147](https://github.com/hashicorp/terraform-provider-aws/issues/42147)),
`prompt_attempts_specification` / `message_selection_strategy` returning "inconsistent result after apply"
([#36845](https://github.com/hashicorp/terraform-provider-aws/issues/36845)), and an **intent↔slot circular
dependency via `slot_priority`**
([#39948](https://github.com/hashicorp/terraform-provider-aws/issues/39948)). Those are exactly our
barge-in/DTMF configuration and our 9-slot FNOL intent.

The proposal (Phase 2 ADR) is to define the bot as a **single nested CloudFormation `AWS::Lex::Bot`
resource** — which structurally cannot hit the intent↔slot cycle — wrapped by Terraform's
`aws_cloudformation_stack`. Terraform remains the only IaC tool we run; CloudFormation is a resource *inside*
it, not a parallel toolchain. Repo 1 demonstrates the `AWS::Lex::Bot` shape works.
