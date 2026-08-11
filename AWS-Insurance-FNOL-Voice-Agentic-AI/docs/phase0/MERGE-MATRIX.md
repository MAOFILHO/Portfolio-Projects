# Merge Matrix — Phase 0

Eight source repositories under `/Users/marco/K21/Temp/CallCenter/AWS` (**read-only**; never modified).
Default verdict is **DISCARD**. A module earns KEEP or REFACTOR only if it does something we would otherwise
have to build, and does it better than a from-scratch implementation.

**Licenses: all eight are MIT-0 (MIT No Attribution).** No license incompatibility, no attribution burden,
no copyleft exposure. Repo 3 declares it machine-readably (`SpdxLicenseId: MIT-0`, `template.yaml:9`); the
others were verified by confirming the LICENSE text omits the "above copyright notice shall be included"
clause.

Verdict meanings:
- **KEEP** — used substantially as found (possibly as a spec, fixture, or reference rather than imported code).
- **REFACTOR** — the logic or shape is right; adapt it to Python 3.12 / Lambda / Terraform / our schema.
- **REWRITE** — the *pattern* transfers, the code does not. Counted with discards for code purposes.
- **DISCARD** — not carried forward in any form.

---

## Discard rate — reported, with the caveat that the denominator matters

| Verdict | Modules | Share |
|---|---|---|
| KEEP | 20 | 20% |
| REFACTOR | 22 | 22% |
| REWRITE (pattern only, code discarded) | 5 | 5% |
| DISCARD | 53 | 53% |
| **Total meaningful modules assessed** | **100** | |

**By module count: 53% discarded outright, 58% if REWRITE is counted as discarding the code.**

**By lines of code the figure is roughly 97%**, and that is the more honest number. The discards include
repo 7's ~23,400 LOC of Python plus its EKS/Karpenka Terraform, repo 5's 1,271-line CDK monolith and its
entire React SPA, repo 6's EKS + Java/Fargate settlement service and CRA frontend, repo 8's 805-line
`App.js` and a 223 MB generated-evidence blob. The KEEPs, by contrast, are small: a Pydantic schema file, a
system prompt, a 61-line triage function, a 22-item entity list, six text transcripts, and several JSON
fragments retained as fixtures or specs.

Both framings are given deliberately. A module-count rate flatters the discards' size; a LOC rate flatters
the KEEPs' concision. Per-row justification below is the substance — the percentages are summary only.

**Where a KEEP might look generous, the build-vs-borrow reasoning is stated in the row.** The strongest
cases are `claim_schema.py` (a correct Pydantic v2 FNOL model set is a day's careful work), the KABCO
injury scale (a real NHTSA MMUCC standard we would otherwise invent badly), and the verified recording-block
JSON (a CI check written against real schema rather than a guess).

---

## Repo 1 — `amazon-connect-with-amazon-lex-genai-capabilities`

CloudFormation (raw, no SAM) · Python 3.10 container Lambda · Bedrock as NLU booster behind Lex FallbackIntent
· ~1,250 LOC · last commit 2024-03-24 · **no tests, no lint/type config, no CI**.

| Module | Verdict | Reason |
|---|---|---|
| `contactflowsample/samplecontactflow.json` | **KEEP** (schema reference) | The only modern (2019-10-30) flow exemplar in the entire corpus. Harvest `Type` strings and the `Transitions.{NextAction,Conditions,Errors}` grammar, then author FNOL content fresh |
| Lex `dialogAction` `Delegate`/`Close` snippets (`lambda_function.py:128-155`) | **KEEP** | Correct, minimal Lex V2 response contract — half of the codehook contract we need |
| `IntegrationAssociation` + scoped `Lambda::Permission` (`template.yaml:303-308`) | **KEEP** | Correctly scoped (`Principal: lexv2.amazonaws.com` + `SourceAccount` + `SourceArn`); direct Terraform analogue |
| `available_intents` session-attribute pattern (`:198-232`) | **REFACTOR** | Genuinely clever: the contact flow tells the model which intents are legal *at this point in the call*, narrowing classification per turn. Reimplement without the LangChain/global-cache baggage |
| `AWS::Lex::Bot` intent/slot/prompt YAML | **REFACTOR** | Correct field names and nesting; this is the shape our CFN-wrapped bot uses. Must add the barge-in/DTMF specs it lacks |
| `lambda_function.py` LLM classifier | **REWRITE** | `langchain==0.0.309` uses the removed `langchain.llms.bedrock` API; class-level mutable cache shared across warm invocations; unpaginated `list_intents`; `KeyError` when the model hallucinates an intent id; blocking call = dead air for the caller |
| `AWS::Connect::Instance` + `AWS::Connect::PhoneNumber` | **DISCARD** | Violates the hard "never create instance or DID" constraint |
| `ContactLens: true` instance attribute (`:287`) | **DISCARD** | Banned |
| `Dockerfile` + ECR + `scripts/*.sh` | **DISCARD** | Container Lambda shipping ~1 GB of never-imported `pandas`/`transformers`; ECR storage burns budget. Use a zip Lambda on py3.12 |
| `SentimentAnalysisSettings: DetectSentiment: true` | **DISCARD** | Per-utterance Comprehend charge for no FNOL value |
| `dependencies/requirements.txt` | **DISCARD** | Dead pins; see `DEPENDENCY-CONFLICTS.md` |

Known defect worth copying as a *negative* test: one flow condition operand is `" manifest"` with a leading
space, so that branch can never fire. Our CI asserts every `Operands[0]` equals its own `strip()` and is a
member of the Lex intent-name set.

---

## Repo 2 — `amazon-lex-v2-connect-workshop`

**No IaC at all** — console click-through workshop. Node.js 14.x (EOL), `aws-sdk` v2 (EOL), `$LATEST` bot
alias, us-east-1 hardcoded · last commit 2023-01-21 · **no tests, no package.json, no CI**.

| Module | Verdict | Reason |
|---|---|---|
| `SetRecordingBehavior` block JSON | **KEEP** (CI fixture) | The exact negative fixture the constraint-18 recording guard must reject. Vendored verbatim into the test suite |
| `myPersonalBanker_v2.js` `ElicitSlot` / `Close` / `messages[]` literals | **KEEP** | Completes the Lex V2 response contract repo 1 only half-shows; also the V2 slot read path `slots.X.value.interpretedValue` and `sessionId` replacing v1's `userId` |
| `Advanced_Workflow` `InvokeExternalResource` / `SetAttributes` / `CheckAttribute` shapes | **REFACTOR** | Correct block grammar, but legacy `modules[]` schema — translate to modern `Type`/`Parameters`/`Transitions` before use |
| `myPersonalResponder_v1.js` Connect↔Lambda contract | **REFACTOR** | `event.Details.Parameters.<key>` in, flat one-level map out, surfaced as `$.External.<key>` — worth keeping. The array lookup is not |
| `Simple_Workflow`, `Lex_WorkFlow` flow bodies | **DISCARD** | Legacy schema, recording enabled on the happy path, real account ARNs, us-east-1, `$LATEST` alias |
| `myPersonalBanker_v1.js` | **DISCARD** | Lex V1 contract; gone |
| Lab READMEs | **DISCARD** | nodejs14.x, console-only, and a date-of-birth-as-authentication anti-pattern we must not copy |
| `lab*/images/` (~40 console screenshots) | **DISCARD** | Per D7, no images are vendored |

⚠ Flow files here have **no file extension** — CI must glob flow definitions by content (presence of an
`Actions` or `modules` key), not by `*.json`.

---

## Repo 3 — `amazon-connect-chat-redaction`

AWS SAM · **`Runtime: python3.8` ×5 (EOL; function creation blocked since Feb 2025 — will not deploy as-is)**
· async batch Comprehend + Step Functions poll loop · last commit 2022-09-01 · **no tests, no lint, no CI**.

| Module | Verdict | Reason |
|---|---|---|
| `PII_ENTITY_TYPES` list + `REPLACE_WITH_PII_ENTITY_TYPE` (`template.yaml:189-190`) | **KEEP** (taxonomy) | The one genuinely valuable artifact — a 22-type entity vocabulary and a masking-strategy name. Adopt minus `DATE_TIME`/`ALL`, plus `VIN`/`LICENSE_PLATE`/`POLICY_NUMBER`/`CLAIM_NUMBER` |
| README prose on Contact Lens / chat-vs-voice | **KEEP** (documentation) | Cite in the Phase 2 ADR justifying custom-Lambda redaction over the banned Contact Lens |
| `submitComprehendJob.py` + `checkComprehendJobStatus.py` | **REWRITE** | Async batch Comprehend with a 240 s poll is architecturally wrong for a live call. Reimplement as synchronous in-Lambda regex plus optional `detect_pii_entities` with offsets |
| `connect-transcript-redaction-workflow.asl.json` | **DISCARD** | Whole poll-loop shape is obsolete once redaction is synchronous; unbounded loop, no `Catch`, no max-iteration guard; Standard-workflow transitions are needless spend |
| `loadTranscript.py` / `storeRedactedTranscript.py` | **DISCARD** | Chat-transcript-schema specific. Deletes the source transcript then leaves a permanent **unredacted-PII `.backup`** with no encryption and no lifecycle rule — a manufactured liability |
| `invokeRedactionStateMachine.py` | **DISCARD** | S3-batch trigger model irrelevant; the metadata-marker idempotency idea is one line |
| All IAM roles | **DISCARD** | Comprehend on `Resource: "*"`, `logs:*` scoped across all Lambdas rather than its own |
| `template.yaml` as a whole | **DISCARD** | python3.8 ×5 = undeployable; SAR packaging irrelevant to our Terraform stack |
| `images/redacted-sensitive.png` | **DISCARD** | Per D7 — a redaction-demo screenshot is a classic accidental-PII vector |

Note: Contact Lens is **not a code dependency** here — this repo exists to *replace* it on the chat channel.
The real blockers are that it operates on chat transcripts, not voice, and that it presupposes recording is on.

---

## Repo 4 — `amazon-lex-bot-recommendation-integration`

Three standalone CLI ETL scripts, 492 LOC total. No IaC, no tests, no requirements file, no package.

| Module | Verdict | Reason |
|---|---|---|
| `transcribe_call_analytics_to_lex_transcripts.py` | **DISCARD** | See below |
| `connect_chat_to_lex_transcripts.py` | **DISCARD** | See below |
| `stitch_conversation_logs_and_contact_lens_transcripts.py` | **DISCARD** | See below |
| Lex/Contact-Lens transcript envelope schema | **DISCARD** (recorded as a domain note instead) | The `ContentMetadata`/`Participants`/`Transcript` envelope is documented in `DOMAIN-ARTIFACTS.md` for reference; it is not a dependency |

**Repo 4 is discarded entirely.** It never calls the bot-recommendation API — it only prepares *input* files
for it. That feature (Automated Chatbot Designer) mines historical transcripts to suggest intents, a
design-time activity for teams migrating an existing IVR corpus; we are greenfield with no call history. Two
of the three scripts are built around the **banned Contact Lens**. And all three accept **long-lived IAM
access keys as command-line arguments**, landing credentials in shell history and `ps` output — an
anti-pattern to avoid, not adopt.

---

## Repo 5 — `guidance-for-omnichannel-claims-processing…` (richest domain source)

CDK v2 Python, 1,271-line monolithic stack · React 18 CRA + Cloudscape · **`bedrock.VectorKnowledgeBase` →
OpenSearch Serverless (banned, ~$350–700/mo alone)** · **no tests, no lint, no typing, no CI**.

| Module | Verdict | Reason |
|---|---|---|
| Lex export slot script + prompts (`GP-FSI-Claims-Processing.zip`) | **KEEP** (as spec, not imported) | A real 9-slot FNOL elicitation sequence with verbatim prompts and slot priorities: `Policy_VIN → CommPref → OTP → CarMake_Model → LossDate → LossLocation → Details → DriverName → IncidentReport`. Plus 12 verbatim human-escalation utterances. **Read as spec; the zip itself is never imported** (see below) |
| `Knowledgebase/SampleRepairCost.docx` | **KEEP** | **The single best domain artifact in the corpus.** The real NHTSA MMUCC **KABCO** injury scale (K/A/B/C/O), the vehicle damage-extent enum (None/Minor/Functional/**Disabling → requires towing**), repair-cost bands and a 4-tier labour formula. Regulatory grounding we would otherwise invent badly |
| `AmazonConnect/ContactFlow/GP-FSI-ClaimsProcessing.json` | **REFACTOR** | 12-action flow; useful as the *shape* reference for `ConnectParticipantWithLexBot` + `UpdateContactAttributes` + `InvokeLambdaFunction` + `TransferContactToQueue`. Only ~40 lines are meaningful |
| Guidewire ClaimCenter + Socotra FNOL API sequences | **REFACTOR** (domain reference) | The actual composite-API call order for a real core-system FNOL push. Valuable as a realistic mock-CRM contract; the client code is not |
| `VehiclePricing` parts price table | **REFACTOR** | 10-part price table across 3 vehicles — raw material for synthetic repair estimates |
| `Image_prompt` / `Summary_prompt` + DynamoDB prompt-registry pattern | **REFACTOR** | Storing prompts in DynamoDB for hot-swap is a good pattern worth adapting. The "CRITICAL MISMATCH: reported vehicle ≠ imaged vehicle → hard stop" rule is a genuinely useful fraud check |
| `filenewclaim.py` FNOL dialog state machine | **REWRITE** | Slot-sequencing logic is domain-correct but implemented as `if/elif` over `transcriptions[0].resolvedSlots` with a **module-scope mutable `vehicles = []`** — a Lambda concurrency bug |
| `claimsprocessing.py` (CDK stack) | **DISCARD** | OpenSearch Serverless KB, monolithic, wildcard IAM with the comment *"Using * to ensure full access"* |
| `loadsamples.py` | **DISCARD** | Imperative post-deploy script; hardcoded seed credential `Test@1234`; permanent `localhost:3000` CORS allowance |
| All 6 Lambdas as code | **DISCARD** | Includes the **`999999` OTP auth-bypass backdoor** and **TLS verification disabled** on the Guidewire call |
| `ReactApp/` | **DISCARD** | CRA + Cloudscape + browser-side AWS SDK with a Cognito Identity Pool granting the SPA direct `PutItem` on the claims table. Our stack is Vite/TS |
| `deploy.sh` / `destroy.sh` / `cdk.context.json` | **DISCARD** | Irrelevant to our Terraform stack |
| The Lex export zip itself | **DISCARD** | Contains a **real AWS account ID `482186147085`** in a hardcoded KB ARN, plus `anthropic.claude-v2` settings and a Kendra-backed QnA intent |

Gap: repo 5 has **no rental reimbursement and no towing/roadside coverage** anywhere, despite being the
richest domain source. Two of our six intents depend on those. See `DOMAIN-ARTIFACTS.md`.

---

## Repo 6 — `serverless-eda-insurance-claims-processing`

CDK v2 TypeScript, **cdk-nag enabled** (best governance posture of the eight, though with ~25 blanket
suppressions) · Python 3.13 voice agent on Strands + Nova Sonic + AgentCore · **EKS v1.34 with
`natGateways: 1`** and a Java 17 Fargate+ALB settlement service (both banned) · thin but real tests
(~25–30% line coverage of the voice `app/`, **0% of its business logic**).

| Module | Verdict | Reason |
|---|---|---|
| `voice-fnol-agent/app/models/claim_schema.py` | **KEEP** | **Best single code file in the corpus.** Complete Pydantic **v2** FNOL model set (`Location, Incident, Policy, PersonalInformation, PoliceReport, OtherParty, FNOLPayload, ConversationContext`) with `alias` + `populate_by_name` for camelCase↔snake_case. A correct FNOL schema is a day's careful work; this one is done |
| `voice-fnol-agent/app/agent.py:117-188` SYSTEM_PROMPT | **KEEP** (prose) | The best voice-FNOL artifact anywhere in the corpus: safety-before-data ladder, **"do not ask a distressed caller for information already in our system"**, one-question-at-a-time, confirm-before-submit, and an empathy phrase bank. Port the prose; discard the Strands wiring |
| `app/tools/safety_check.py` | **KEEP** | 61 lines, priority-ordered triage: medical > unsafe location > police recommendation, with verbatim guidance strings. Note it *recommends* rather than blocks on police contact |
| `app/tools/validate_fields.py` | **KEEP** | Required-field validator with the conditional rule `policeFiled == True ⇒ policeReceipt required` |
| `app/tools/extract_claim.py` | **KEEP** | `dateutil.parser.parse(fuzzy=True)` for "yesterday at 3pm" — exactly the voice date problem; and `identify_missing_required_fields()` returning human-readable names ("whether you were driving") for TTS readback |
| `event-catalog/events/*/schema.json` | **KEEP** | 14-event contract set (`Claim.Requested/Accepted/Rejected`, `Fraud.Detected`, `Settlement.Finalized`…) — a coherent event vocabulary even though we run far fewer services |
| `agent-skills/VOICE_AGENT_SKILL.md` | **KEEP** (documentation) | Its "Common Pitfalls" section applies regardless of framework — notably that speech models need an explicit `inputSchema` because docstrings are insufficient, and the audio-scheduling trap |
| `claims/app/handlers/claimsProcessing.js` acceptance rules | **REFACTOR** | Policy-period rule (`start < incident < end`) and DL-match rule with verbatim rejection messages. Right logic, wrong language/style |
| `fraud/app/handlers/fraudDetection.js` | **REFACTOR** | Three concrete flags: name-vs-DL mismatch, vehicle-colour-vs-policy mismatch, and "no damage detected" on a damage claim |
| `documents/app/handlers/analyzeCarImage.js` | **REFACTOR** | **Forced tool use** (`toolChoice: {tool:{name:…}}`) for structured output — strictly better than the JSON-by-prompting used elsewhere in the corpus. Adopt the technique |
| `react-claims/src/components/VoiceClaim/ClaimFieldsDisplay.js` | **REFACTOR** | Live "fields collected so far" panel, 4 sections, updated-field highlighting, "Not yet provided" empty state. Excellent dashboard UX pattern; rewrite in TS |
| `VoiceClaim/{AudioCapture,AudioPlayback}.js` + audio worklets | **DISCARD** | Solves 16 kHz Float32→Int16 capture and gapless 24 kHz playback — genuinely non-trivial, but our channel is Connect telephony, not browser audio. Revisit only if browser voice is ever added |
| `app/context.py` session store | **DISCARD** | In-memory, single-container. We need DynamoDB with TTL keyed on the Connect contact ID |
| `services/vendor/infra/vendor-service.ts` | **DISCARD** | **EKS v1.34 + `natGateways: 1`** — banned, ~$150+/mo |
| `services/settlement/**` (Java 17) | **DISCARD** | Always-on Fargate + ALB — banned. Also its settlement logic is a hardcoded `$100.00` stub |
| `voice-fnol-agent/infra/**` | **DISCARD** | AgentCore `CfnRuntime` — we use Connect + Lex |
| `lib/config.ts` | **DISCARD** | Ships **live `webhook.site` URLs** as "detection APIs". Never run this file |
| `react-claims/` app shell | **DISCARD** | CRA + Amplify v5 + class components, with a 10-entry `resolutions` block papering over CRA's transitive CVEs |
| `react-claims/src/DL/*.jpg` | **DISCARD** | DMV specimen licences containing **real human face photographs** |
| `lib/cleanup/**`, `lib/observability/**`, `event-catalog/` app shell | **DISCARD** | Demo-reset scripts and a Dockerised eventcatalog site; only the event data files are kept |

---

## Repo 7 — `sample-agentic-insurance-claims-processing-eks` (nominal "richest agentic source")

Terraform + raw k8s YAML, EKS with Karpenter **GPU nodepools** · ~23,400 LOC Python · **coverage 0%** (pytest
declared, never used; `tests/` holds curl demos and a print-out script) · no lint/type config, no CI.

### 🔴 Two findings that reframe this repo

**1. There is no Bedrock in it, at all.** Exhaustive grep for `bedrock|langchain_aws|ChatBedrock|anthropic|claude`
returns **zero hits**. The LLM layer is a **self-hosted Ollama pod on GPU Karpenter nodes** (`ChatOllama`,
`ChatOpenAI` fallback). So it supplies *no* Bedrock material: no model IDs, no `us.*` inference profiles, no
`ChatBedrockConverse`, no streaming, no throttle/retry handling. All of that is greenfield for us.

**2. The LangGraph code is demo-grade and partly non-functional.** Five graphs, of which three are strictly
linear pipelines; **two conditional edges total** across the repo; `@tool` used decoratively with **the LLM
never selecting a tool** (tools are invoked imperatively inside node bodies); `ToolNode` imported and never
used; checkpointers instantiated but **never keyed by `thread_id`**, so nothing resumes; the Redis
checkpointer physically cannot load (dependency undeclared, wrong constructor) and silently degrades to
`MemorySaver`; the "autonomous learning / self-evolution" methods raise `AttributeError` on first call
because four attributes are never initialised; `dynamic_workflow_engine` returns the **string** `"END"`
instead of the sentinel and has a stubbed method whose body is a comment; structured output is
JSON-by-prompting with regex recovery; and decisions are extracted with
`if "high priority" in llm_response.lower()`. Four files are byte-identical duplicates across two paths, and
two of those have already diverged.

The value here is the **pattern and the domain model**, not the code.

| Module | Verdict | Reason |
|---|---|---|
| `src/human_workflow_manager.py` | **KEEP** (logic) | Ironically the best insurance code in the repo, and it contains no LangGraph. Real claims-org structure: a `ClaimsRole` enum including **`FNOL_SPECIALIST`**, a populated authority-limit matrix (FNOL specialist: $0 settlement, $5k reserve, cannot deny, always needs supervisor), regulatory deadlines (**FNOL 24 h**, coverage decision 30 d, fraud reporting 10 d), an `audit_trail`, and `bad_faith_prevention_notes` — a real compliance concept we would not invent by accident. Its `create_ai_recommendation` returning `{ai_recommendation_only: True, human_decision_required: True}` is the right principle: **AI advises, licensed human decides** |
| `src/enhanced_models.py` | **REFACTOR** | Solid Pydantic-v2 P&C taxonomy (`LineOfBusiness`, `ClaimType`, `ClaimStatus`, `AdjudicationStatus`, `PolicyStatus`). Cut ~70% (life/commercial/rider), modernise `class Config` → `ConfigDict` |
| `src/langgraph_policy_agent.py` — `check_coverage_limits`, `validate_claim_type_coverage` | **REFACTOR** (2 functions) | Deductible/peril/exclusion arithmetic is reusable: `covered = min(amount − deductible, limit)`. Keep the two functions, drop the linear graph — and note `validate_policy_existence` determines validity by `len(policy_number) > 5` |
| `shared/observability.py` | **REFACTOR** | Keep the structlog JSON config and the `AgentMetrics`/`WorkflowEvent`/`AgentInteraction` dataclass taxonomy plus correlation-ID discipline. Drop `threading.local()`, `patch_all()` and the buffered background CloudWatch thread — wrong concurrency model for Lambda; use Powertools Logger/Tracer/Metrics (EMF) |
| `shared/authentic_llm_integration.py` | **REFACTOR** | Cleanest code here: a `ChatPromptTemplate` registry with a domain→template mapping and context prep. Swap `ChatOllama`/`ChatOpenAI` → `ChatBedrockConverse`, replace JSON-by-prompting with tool-use structured output, and **rewrite every prompt for a voice register** — these are paragraph-shaped and wrong for speech |
| `data/sample_claims.json`, `data/fraud_patterns.json` | **REFACTOR** | Useful seed shapes and four named fraud patterns with human-readable indicator rules. Keep the auto records, drop home/water-damage |
| `docs/**` (13 files) | **REFACTOR** (read-only) | `LANGGRAPH_AGENTIC_README.md` and `ARCHITECTURE.md` are useful narrative for our own design doc — **read sceptically; they describe a system more capable than the code** |
| `src/langgraph_agentic_coordinator.py` | **REWRITE** (pattern) | Supervisor→specialist→aggregate→human-routing *shape* and the `create_ai_recommendation` routing thresholds are the prize. But Ollama-bound, cluster-DNS-bound, four uninitialised attributes, an undeclared state key, and substring parsing |
| `src/langgraph_fraud_agent.py` | **REWRITE** (pattern) | Contains the only genuine conditional edge in the repo — copy that idiom. Everything else is stubbed; no checkpointer; fraud scoring is out of FNOL-intake scope anyway |
| `src/langgraph_shared_memory.py` | **DISCARD** (steal one idea) | `compile(checkpointer=…)` is the DynamoDB injection seam — that is one line of insight. The rest is Redis plus a hardcoded literal list masquerading as similarity search |
| `src/langgraph_investigation_agent.py` | **DISCARD** | 7-node straight line, zero branching, post-intake scope |
| `shared/dynamic_workflow_engine.py` | **DISCARD** | Non-functional: stubbed `_add_end_edges`, `"END"` string bug, untyped `StateGraph(dict)` |
| `shared/agent_negotiation_protocol.py` | **DISCARD** | 635 lines of invented bidding protocol, demo-only, no voice relevance |
| `src/external_integrations/*` (~1,900 LOC) | **DISCARD** | ISO ClaimSearch / Carfax / NHTSA / weather wrappers for services we will not buy |
| `src/analytics/actuarial_models.py` | **DISCARD** | 762 LOC of sklearn/xgboost/statsmodels — won't fit a Lambda layer, won't fit $25, not intake |
| `src/persona_web_interface.py`, `web_interface.py`, `templates/`, `static/` | **DISCARD** | ~2,100 LOC of server-rendered dashboards with inline CSS |
| `src/database_models.py`, `data_loader.py` | **DISCARD** | Motor/MongoDB DAL; we are on DynamoDB |
| `src/real_time_claims_simulator.py` | **DISCARD** | Fake claim stream for their demo |
| `infrastructure/terraform/**` | **DISCARD** | EKS + Karpenter + GPU nodepools + ACM + VPC. Banned, and would incinerate $25 in hours |
| `infrastructure/kubernetes/**`, 12 Dockerfiles, `scripts/*.sh` | **DISCARD** | k8s/ECR/always-on containers; also where the leaked account ID and the plaintext Mongo password live |
| `tests/**` | **DISCARD** | Shell curl demos plus a narration script with no assertions |

---

## Repo 8 — `sample-browser-automation-with-agentcore-for-insurance-fnol-claims-queue`

FastAPI + React CRA on **Fargate + ALB + CloudFront + WAF** (all banned; that entire cost structure exists
only to give the AgentCore browser agent a public URL) · Python 3.12, **fully pinned backend requirements**
(the only such file in the corpus) · **tests are a fully commented-out stub that passes vacuously**.

| Module | Verdict | Reason |
|---|---|---|
| `backend/complexity_analyzer.py` — thresholds + weighted score + fallback | **KEEP** (rubric) | A ready-made numeric triage rubric: damage-amount bands ($30k/$15k), evidence-volume bands (10/5 items), high-complexity subtypes, and a **weighted evidence score** (severe +4, fraud indicators +6, credible −2, floored at 0 → high/medium/low/minimal). Routing `Complex → Needs Review` (human) / `Simple → Resolved`. Crucially it includes a **deterministic non-LLM fallback** (`damage > $20k OR evidence > 8 → Complex`) and a conservative-bias rule — exactly right for a $25 budget |
| `backend/evidence_analyzer.py` — transcript tag taxonomy | **KEEP** (taxonomy) | `emotional_state` / `story_consistency` / `fraud_risk` / `information_quality` / `credibility` maps 1:1 onto voice post-call analysis. The image and video taxonomies are kept as secondary reference |
| `utils/generated_evidence/CLM_00*_transcript_*.txt` (6 files) | **KEEP** (fixtures) | Natural, unstructured FNOL call transcripts that state fields out of order, volunteer unasked-for information, and mention injury status, police report numbers and photos. Ideal Lex/Connect utterance fixtures — `CLM_002` (rear-end collision) and `CLM_004` (vehicle theft) are the auto-relevant ones |
| `utils/generate_claim_evidence.py` — transcript + Polly path only | **REFACTOR** | The synthetic-transcript prompt plus Polly neural → PCM → **WAV 16 kHz mono 16-bit** matches Lex/Connect input format exactly, and is the only budget-compatible test-data recipe in the corpus. **The Nova Canvas/Reel image and video paths are discarded — Nova Reel at ~$0.08/s would blow the budget outright** |
| `backend/main.py` — async-analyze-then-poll API design | **REFACTOR** (design only) | `status: processing → completed \| error` with a polling GET lets a short Lambda kick off work instead of holding a connection. Good fit for our budget |
| `cdk/lib/claims-processing-stack.ts:110-130` DynamoDB/S3 IAM statements | **REFACTOR** | The **best IAM scoping example in the corpus** — properly ARN-scoped (only Bedrock is wildcarded) |
| `frontend/src/App.js` claims-queue UX concepts | **REFACTOR** (concepts) | Per-claim expandable card with four evidence tabs, per-tab analyze button and processing state, status-to-CSS-class pattern, and an `analyzedClaims` set preventing re-analysis. Concepts only |
| `backend/main.py` as code | **DISCARD** | Unbounded `table.scan()`, **no authentication on any `/api/*` route**, deprecated `@app.on_event`, `datetime.utcnow()`, bare `except:` |
| `backend/seed_data.py` | **DISCARD** | Demo seeding; `import sys` twice |
| `frontend/` | **DISCARD** | CRA with an 805-line single `App.js` |
| `cdk/**` | **DISCARD** | Fargate + ALB + VPC + CloudFront + WAF (~$45–60/mo minimum, plus ~$6–10/mo WAF) |
| `full_automation/**` | **DISCARD** | AgentCore Browser Tool + Nova Act — out of scope and billable. Also creates an S3 bucket for **session recordings of PII-bearing claim screens**, an IAM role trusting two service principals, and commits a live browser resource id |
| `Dockerfile`, `deploy.sh`, `utils/set_aws_env.sh` | **DISCARD** | `set_aws_env.sh` and `generate_claim_evidence.py:21-51` **write `AWS_SECRET_ACCESS_KEY`/`AWS_SESSION_TOKEN` into `os.environ`** — leaks secrets to child processes and crash dumps, and defeats the credential-provider chain |
| `utils/generated_evidence/` binary blob (65 of 71 files) | **DISCARD** | Hundreds of MB of Nova-generated PNG/MP4/WAV. Per D7 no images are vendored; only the 6 `.txt` transcripts are kept |
| `cdk/test/cdk.test.ts` | **DISCARD** | A fully commented-out stub containing an empty `test('SQS Queue Created', () => {})` that passes vacuously — worth noting as an example of coverage theatre |

---

## What no repo provides — see `DOMAIN-ARTIFACTS.md`

Five domain gaps (speakable claim number, deductible logic, **rental/towing coverage**, total-loss rule,
injury-severity→coverage mapping) and five engineering gaps (barge-in/DTMF/timeout config, streaming and
interim audio fillers, all Bedrock integration, DynamoDB checkpointing, guardrails/PII/RAG/evals/MCP —
**no repo uses MCP at all**).
