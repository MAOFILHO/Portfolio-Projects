# Security Findings — Phase 0

Findings from reading the eight source repositories. **None of these are defects in this project** — nothing
has been carried forward. They are recorded so that (a) the do-not-propagate list is explicit and greppable,
and (b) the Phase 2 threat model starts from observed failure modes rather than a generic checklist.

---

## Do-not-propagate list

CI greps for every literal in this section (Phase 10). Any hit fails the build.

⚠ **Implementation note for the Phase 10 scan.** These literals necessarily appear *in this document* (and a
few in `CLAUDE.md` and `MERGE-MATRIX.md`) in order to be documented at all. The forbidden-string scan must
therefore exclude `docs/phase0/SECURITY-FINDINGS.md`, `docs/phase0/MERGE-MATRIX.md` and `CLAUDE.md` by path,
and the exclusion list must be narrow and explicit rather than a broad `docs/**` skip — otherwise the scan
stops protecting the tree it exists to protect. A sibling project in this monorepo has already shipped a fix
for exactly this class of bug (`fix(ci): exclude generated egg-info from the forbidden-string scan`), so the
failure mode is known: an over-broad exclusion that silently neuters the check.

### Hard exclusions — three named artifacts

| # | Artifact | Where | Why excluded |
|---|---|---|---|
| 1 | **AWS account ID `482186147085`** | Repo 5, inside `source/Amazon Lex/GP-FSI-Claims-Processing.zip` → `BotLocales/en_US/Intents/GetClaimsFAQ/Intent.json`, as `bedrockKnowledgeBaseArn` | Someone's **real** account. This is why the Lex export zip is discarded and the bot is hand-authored |
| 2 | **VIN `1HGCF86461A130849`** | Repo 6 — `README.md:197`, `voice-fnol-agent/app/tools/get_customer_info.py:56`, `react-claims/src/Signup.js:106` | A **structurally valid** Honda VIN (WMI `1HG`, correct length, plausible check digit) that may correspond to a real vehicle. We generate our own with a **deliberately invalid check digit** |
| 3 | **`dl_AZ.jpg`, `dl_MA.jpg`, `dl_OH.jpg`** | Repo 6 `react-claims/src/DL/` | DMV specimen driver's licences containing **real human face photographs**. Not customer PII, but a likeness we have no right to redistribute |

### Blanket rule — no images

**No image, video or audio file is vendored from any source repo.** Rationale: redaction and console
screenshots are a classic accidental-PII vector, and several image sets were not visually verified:

- Repo 3 `images/redacted-sensitive.png` — a screenshot of a redaction UI, i.e. the worst case
- Repo 2 `lab*/images/` — ~40 console captures of a live Connect instance
- Repo 8 `utils/generated_evidence/` — 65 Nova-generated PNG/MP4/WAV files, synthetic by construction but **not individually inspected**

Only the 6 `.txt` transcripts from repo 8 are carried forward. Our own fixtures are generated via the Polly
recipe (see `DOMAIN-ARTIFACTS.md` §9).

### Other literals that must never appear

| Literal | Source | Kind |
|---|---|---|
| `117026838272` | Repo 2, ×4, with real Connect instance/queue/Lambda GUIDs | Real AWS account ID |
| `123255318457` | Repo 7 — `scripts/demo.sh:20`, `build-docker-images.sh:18`, `deploy-kubernetes.sh:18` | Real AWS account ID (ECR registry default) |
| `insurance_db_password123` | Repo 7 `load-sample-data.sh:25` | Plaintext password, committed |
| `Test@1234` | Repo 5 `loadsamples.py:588` | Hardcoded seed credential |
| `999999` (as an OTP comparison) | Repo 5 `filenewclaim.py:282` | Auth-bypass backdoor |
| `cert_reqs='CERT_NONE'`, `assert_hostname=False` | Repo 5 SQS-3P integration Lambda | Disabled TLS verification |
| `webhook.site/a991642a-…`, `webhook.site/fae02cbf-…` | Repo 6 `lib/config.ts` | Live third-party exfiltration endpoints |
| `BlogClaimsRecordingBrowser-eloI1ikCZE` | Repo 8 `full_automation/browser_id.txt` | Committed live AWS resource identifier |
| `pinNumber: '1234'` | Repo 2 `myPersonalBanker_v{1,2}.js:6-14` | Hardcoded credential |

---

## Critical findings, by severity

### 🔴 Authentication bypass — repo 5

```python
if OTP == OTP_Entered or OTP_Entered == "999999":
```
`source/lambda/gp-fsi-claimprocessing-filenewclaim/…py:282`

Any caller bypasses identity verification with a fixed literal. It is also **documented in the UI**
(`InitiateClaim.tsx:422`), so it is a deliberate demo shortcut rather than an oversight — which makes it more
dangerous, because it reads as intended behaviour.

**Our position:** identity verification is a real control. Any test-mode bypass must be gated by a feature
flag that is off by default, absent in production configuration, and asserted absent by a test.

### 🔴 Disabled TLS verification with credentials in flight — repo 5

```python
urllib3.PoolManager(cert_reqs='CERT_NONE', assert_hostname=False)
urllib3.disable_warnings(InsecureRequestWarning)
```

Used for the Guidewire core-system call, **with Basic Auth credentials sent over it**. Both certificate
validation and hostname checking are off, and the warning that would surface it is suppressed.

**Our position:** TLS verification is never disabled. Outbound calls to the mock CRM use the default
verified path.

### 🔴 Live third-party exfiltration endpoints — repo 6

`lib/config.ts` ships two live `webhook.site` URLs as the "color detect" and "damage detect" APIs. Anything
posted there goes to a third party and is retained by them. The file is legacy (superseded by a Bedrock call)
but still present and importable.

**Our position:** `lib/config.ts` is discarded, not adapted. **Never execute that file.** No external
endpoint is called without being declared in the threat model.

### 🔴 Credential exfiltration into the process environment — repo 8

`utils/generate_claim_evidence.py:21-51` shells out to `aws sts get-caller-identity`, then writes
`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` and `AWS_SESSION_TOKEN` into `os.environ`.
`utils/set_aws_env.sh` does the same in shell.

This leaks secrets to every child process and into crash dumps, and defeats the credential-provider chain
that would otherwise handle rotation.

**Our position:** always use the default credential chain. Local development uses a named profile; CI uses
**OIDC with no long-lived keys** (Phase 10). No script writes credentials into the environment.

### 🔴 Long-lived IAM keys as command-line arguments — repo 4

```python
s3_client = boto3.client('s3', aws_access_key_id=access_key,
                         aws_secret_access_key=secret_key, region_name=region)
```

Documented in that repo's README as the intended usage (`--access_key MYACCESSKEY --secret_key MYSECRETKEY`).
Credentials land in shell history and in `ps` output visible to other users on the host.

**Our position:** one of several reasons repo 4 is discarded entirely.

### 🔴 Browser-side privileged AWS access — repo 5

A Cognito **Identity Pool** grants the SPA direct `PutItem`/`GetItem` on the claims table and `SendMessage`
on SQS. Any authenticated user can write arbitrary claim records, bypassing every server-side rule —
including the policy-period and licence-match validation the backend performs.

**Our position:** the dashboard is read-mostly and talks to API Gateway + Lambda. No browser credential ever
holds a data-plane permission. Authorisation is enforced server-side.

### 🔴 A permanent unredacted-PII artifact — repo 3

The redaction pipeline deletes the source transcript and writes a `.backup` object containing the
**unredacted** original, in the same bucket, with:

- no `BucketEncryption` and no `ServerSideEncryption` on any `put_object`/`copy_object`
- no lifecycle rule, so it persists indefinitely
- no KMS CMK anywhere in the template

Compounding it: **all five Lambdas wrap their bodies in `try/except Exception` and return `None`**, so Step
Functions never observes a failure. The `Retry` blocks and the `Job Failed` state are largely unreachable, and
because `loadTranscript.py` has already deleted the source, a silent failure loses the transcript from the
Connect UI with only that unencrypted `.backup` behind.

**Our position:** redaction is **synchronous and in-process**; the unredacted transcript is never persisted at
all, not even transiently. There is no `.backup`. Exceptions propagate. Encryption and a lifecycle policy are
mandatory on every bucket.

### 🔴 No guardrails and no PII redaction — repo 7

Grep for `guardrail|redact|pii|mask|anonymi|sanitiz` across ~23,400 LOC returns **one hit, and it is the word
"guardrail" inside a synthetic crash description**.

Claimant name, phone, email and address are modelled as first-class fields and interpolated **raw** into LLM
prompts. Worse, decisions are extracted from free-text model output by substring matching:

```python
if "high priority" in llm_response.lower():
```

That is directly prompt-injectable: any claim description containing the phrase steers the decision.

**Our position:** this is precisely what constraints 10–11 exist to prevent — Guardrails on input *and*
output, PII redaction before persistence or logging, prompt-injection defence on retrieved documents and tool
responses, and **structured output via tool use rather than string parsing**.

### 🔴 Unauthenticated API — repo 8

No authentication on any `/api/*` route; the app relies solely on being behind an ALB + CloudFront + WAF.
Claim listing uses an unbounded `table.scan()` with no pagination.

**Our position:** API Gateway with an authorizer; no unbounded scans (GSI-backed queries with pagination).

---

## 🟠 Medium findings

| Finding | Repo | Detail |
|---|---|---|
| IAM wildcards | 5 | `Resource: "*"` at `claimsprocessing.py:117` with the comment *"Using * to ensure full access.. you can limit the access to specific resources"*, plus `:477`, `:716`, `:793` |
| IAM wildcards | 3 | `comprehend:StartPiiEntitiesDetectionJob` / `Describe…` on `Resource: "*"` in two roles; `logs:*` scoped to `log-group:/aws/lambda/*` (all functions, not just its own); an unused role holding S3 write + Comprehend permissions |
| IAM wildcards | 1 | `Resource: "*"` for `lex:ListSlotTypes|DescribeIntent|ListIntents|ListSlots`; also a **malformed action string** `- polly:SynthesizeSpeech,` with a stray trailing comma |
| IAM wildcards | 6 | `resources: ["*"]` in the voice-agent stack and transaction-search construct, suppressed with *"Will refine these permissions in next version."* |
| IAM wildcards | 8 | `bedrock:InvokeModel*` on `resources: ['*']` — though its DynamoDB and S3 statements **are** properly ARN-scoped, the best IAM example in the corpus |
| Over-broad trust policy | 8 | An IAM role trusting **both** `bedrock-agentcore.amazonaws.com` and `bedrock.amazonaws.com` |
| Recordings of PII-bearing screens | 8 | `full_automation/setup_browser_environment.py` auto-creates an S3 bucket for **browser session recordings of claim screens** |
| Unprotected bucket creation | 8 | `self.s3.create_bucket(Bucket=f"claims-evidence-{random 5 digits}")` — no encryption, no public-access block, no versioning; deleted on the happy path only, so a crash leaves it behind. Only ~90k possible names, so collision/squatting is realistic |
| Full PII payloads to CloudWatch | 6 | `console.log(JSON.stringify(event))` at the top of every handler logs the whole FNOL payload — driver's licence number, address, DOB — in plaintext |
| cdk-nag suppressions | 6 | ~25 blanket suppressions disabling S3 access logging, DynamoDB PITR, API GW auth, WAF, Cognito authorizer, SQS DLQ, Step Functions logging and X-Ray, VPC flow logs, ECS Container Insights, ALB logging, security-group egress. Best governance posture of the eight, and still a demo posture |
| Permissive CORS | 5, 6 | `AllowedHeaders: ['*']` with `http://localhost:3000` permanently allowed (5); `access-control-allow-origin: "*"` (6) |
| `RemovalPolicy.DESTROY` everywhere, no PITR, no KMS CMK | 5, 6, 8 | Only `S3_MANAGED` encryption where any is set |
| `--disable-rollback` | 1 | `scripts/deploy.sh` leaves half-built stacks on failure |
| Default VPC in production path | 6 | Suppressed as *"Default VPC is used for demo purposes."* |
| Recording enabled on the happy path | 2 | `SetRecordingBehavior` with `RecordingBehaviorOption: "Enable"`, `RecordingParticipantOption: "Both"` as **module #2** in all three flows — i.e. on by default before anything else happens |
| Contact Lens enabled | 1 | `ContactLens: true` on the created Connect instance |
| `$LATEST` bot alias | 2 | Never appropriate outside a scratch test |
| End-of-life runtimes | 2, 3 | `nodejs14.x`; `python3.8` ×5 (the latter makes that template undeployable today) |

---

## PII gate — ruling

**No real customer, policyholder, policy or claim PII was found in any of the eight repositories.**

Evidence: all personal names are `Doe` / `Smith` / `Sample` / `Fname LName` / `Maria Garcia`; emails are
`@example.com` or `@email.com`; phone numbers are NANP-reserved `555-…` or `+11234567891`; addresses are
`123 Main St`-class; no SSNs appear; claim and policy numbers are repeating-digit or sequential fakes. Repo 7
declares `faker` as a dependency and generates records programmatically. The DMV specimen cards carry
`SAMPLE` as the surname, "NOT FOR FEDERAL IDENTIFICATION", and in the MA case a `SAMPLE` watermark across the
card.

**Three artifacts are excluded anyway** — see the hard-exclusion table above. Two are not customer PII at all
(an AWS account ID; a likeness), and the third (the VIN) is excluded on the precautionary principle because it
is structurally valid rather than obviously synthetic.

**Residual uncertainty, stated plainly:** the ~105 image/video/audio files across repos 2, 3 and 8 were **not
individually inspected**. The no-images rule makes that moot — nothing binary is carried forward — but the
gate is "excluded", not "verified clean", and this document should not be read as claiming otherwise.

---

## Input to the Phase 2 threat model

Observed failure modes, mapped to the threat classes the Phase 2 model must cover:

| Threat class | Observed instance to design against |
|---|---|
| **Prompt injection** | Repo 7's `if "high priority" in llm_response.lower()` decision extraction, and raw claimant PII interpolated into prompts. Our defence: structured output via tool use, plus injection screening on retrieved documents *and* tool responses |
| **Tool abuse** | Repo 5's browser-side `PutItem` on the claims table. Our defence: server-side authorisation only; MCP tools validate arguments against a schema and enforce authority limits |
| **PII leakage** | Repo 3's unencrypted unredacted `.backup`; repo 6 logging whole FNOL payloads to CloudWatch. Our defence: synchronous redaction before persistence *or* logging; the unredacted transcript is never written |
| **Denial of wallet** | Repo 5's OpenSearch Serverless KB (~$350–700/mo), repo 6's EKS + NAT (~$150+/mo), repo 8's Nova Reel video generation (~$0.08/s). Our defence: the banned-services list, the cost gate, a hard budget alarm shipped day one, and simulator-first testing |
| **Toll fraud** | No repo addresses it. Inbound-only DID (already configured — `OutboundCallsEnabled: false`), plus concurrency limits and alarms |
| **Auth bypass** | Repo 5's `999999` OTP literal. Our defence: any test bypass is flag-gated off by default and asserted absent by a test |
| **Supply chain** | `requests==2.31.0` (known CVEs), the `prompt-toolkit` misspelling, and the `install`/`npm`/`uninstall` cargo-cult dependencies. Our defence: exact pins, a committed lockfile, `detect-secrets` + `gitleaks` pre-commit, dependency scanning in CI |
