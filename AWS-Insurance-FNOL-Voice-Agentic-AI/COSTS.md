# Costs — per-run log

Every real (non-mock, non-`local`) AWS call this project makes gets a row here, per `CLAUDE.md`'s standing
Bedrock approval ("$5 total across Phases 3–7, logged per-run"). Provisioned resources remain individually
gated regardless of this log.

| Date | Phase | What ran | Real AWS call? | Tokens | Est. cost | Running total |
|---|---|---|---|---|---|---|
| — | 3 | `make ingest` (default: mock embeddings + local moto table) | No — `--embeddings mock`, `--vector-store local`, both zero-cost/zero-credential defaults (`src/fnol_voice_agent/knowledge/ingest.py`) | 0 | $0.00 | $0.00 |
| 2026-08-11 | 3 | **First real spend.** One real `InvokeModel` call, `amazon.titan-embed-text-v2:0`, `us-west-2`, one chunk (`example-mutual-oap-policy-wording.md`'s DCPD section) — cost-gate approved by Marco explicitly, ahead of Phase 4, to verify the manifest's asserted model ID/dimension against an observed response rather than an untested assumption | **Yes** | 515 input | $0.0000103 (515 × $0.02 / 1,000,000) | $0.0000103 |
| 2026-08-11 | 4 | **Closing verification.** Five real `Converse` calls, `us-west-2`, against the exact system prompts drafted in `docs/phase4/PROMPT-REGISTRY.md` — cost-gate approved by Marco explicitly, to check the length-discipline specs against real model output rather than assert them. Breakdown: (1) `us.amazon.nova-micro-v1:0`, forced tool-use `classify_turn`, 751 in / 42 out → $0.0000322; (2) `us.amazon.nova-micro-v1:0`, unconstrained tight-turn generation (ambiguity clarifier), 77 in / 24 out → $0.0000061; (3) `us.amazon.nova-lite-v1:0`, `CoverageQuestion` mandatory (DCPD), 243 in / 13 out → $0.0000177; (4) `us.amazon.nova-lite-v1:0`, `CoverageQuestion` optional (IRB), 270 in / 38 out → $0.0000253; (5) `us.amazon.nova-lite-v1:0`, `RentalTowingEntitlement` compound, 265 in / 36 out → $0.0000245 | **Yes** | 1,606 input / 153 output | $0.0001058 | $0.0001161 |
| 2026-08-11 | 5 (Stage 8) | **Real-call verification of the actual shipped `aws/bedrock_router.py` code path** (not a script reimplementing the API) — cost-gate approved by Marco, scoped to: one `classify_turn` call driven through the real, assembled graph (`build_graph()`, a `CheckClaimStatus` turn); `CoverageQuestion`'s optional-election generation path (real policyholder `PY4821`, real IRB passage); `RentalTowingEntitlement`'s compound generation path (real claim `CLM-2608-00042-4`); and `CF3` — 5 real Nova Micro tight-turn samples (not the n=1 Phase 4 left as a smoke test), drawn from `INTENT-TAXONOMY.md` §2.3's real ambiguous utterances. **Run twice** — the first pass (before a cost-logging wrapper was added mid-verification) made the same 8 real calls without exact per-call token capture; the second pass, fully instrumented, is the one itemized below. Combined total is an estimate for that reason, stated as such rather than presented with false precision. Second-pass breakdown: `us.amazon.nova-micro-v1:0` classify_turn 940 in / 48 out → $0.0000396; `us.amazon.nova-lite-v1:0` CoverageQuestion-optional 270 in / 41 out → $0.0000260; `us.amazon.nova-lite-v1:0` RentalTowingEntitlement 287 in / 60 out → $0.0000316; 5× `us.amazon.nova-micro-v1:0` CF3 samples (71/21, 71/21, 72/21, 81/14, 80/13 in/out) → $0.0000230 combined | **Yes** | Second pass: 1,602 in / 199 out, $0.00012301 exact. First (uninstrumented) pass: same 8 calls, ≈$0.00012 estimated from the second pass's near-identical prompts, not separately measured | ≈$0.00025 combined (both passes) | ≈$0.00037 |
| 2026-08-12 | 6 (Stage 6) | **L2 recall measurement — the layered-detector question.** 22 real `Converse` calls, `us.amazon.nova-micro-v1:0`, `us-west-2`, through the real shipped `classify_turn` path. Scoped to exactly the question Marco posed at Phase 6 approval: does L2 catch what L1 misses. Two named golden cases (`inj-004`, `inj-010`) plus the **19 phrasings on the independently-generated held-out set that L1 still misses after the Stage 5 polarity fix**, plus one control (the surviving L1 false positive, which must NOT escalate). Result: **L2 caught 19/19**, union recall 26/26, control correctly cleared — see `docs/RESULTS.md` §1 | **Yes** | 20,421 in / 978 out | $0.000852 | ≈$0.00122 |
| 2026-08-12 | 6 (Stages 5–6) | **Embedding fixture + full Tier B.** (a) `amazon.titan-embed-text-v2:0` × 62 calls across two fixture builds (regenerated once after two gold labels were found to name text absent from the corpus) → $0.000274; (b) intent classification, real `us.amazon.nova-micro-v1:0` through the shipped `classify_turn` path, first turn of all 73 labelled conversations; (c) 9 generation trials on `us.amazon.nova-lite-v1:0` (3 cases × 3, discharging CF3's repeated-sampling requirement) each judged by `us.anthropic.claude-haiku-4-5` — 96 calls → $0.010945; (d) **L2 false-escalation over 34 must-not-escalate cases** → $0.001326, the measurement that corrected the layered-design conclusion. Results in `docs/RESULTS.md` | **Yes** | 214 calls total | $0.012545 | ≈$0.01376 |
| 2026-08-12 | 7 (Stage 0) | **Forensics on `D25`, closing a gap Phase 6's harness created.** 78 real `Converse` calls, `us.amazon.nova-micro-v1:0`, `us-west-2`, through the shipped `classify_turn` path — the first turn of all 78 labelled golden conversations, storing the **whole** `TurnClassification` rather than only `.intent`. Phase 6's Tier B run discarded the `safety_flag` that came back in the same response, then paid for 34 further calls to recover part of it; this run makes the joint distribution measurable and answers Marco's Stage 0 refutation condition. `scripts/stage0_forensics.py --live` | **Yes** | 72,403 in / 3,549 out | $0.00303096 | ≈$0.01679 |
| 2026-08-12 | 7 (Stage 0.5) | **Quantifying `D27` before fixing it**, per Marco's decision. 780 real `Converse` calls, `us.amazon.nova-micro-v1:0`, `us-west-2` — **k=5 runs over all 78 labelled golden first turns at each of two settings**: the shipped default (no `temperature` key, so Nova applies 0.7) and `temperature=0.0`. Result: 0.7 gives macro-F1 0.488–0.551 with **35/78 turns unstable in intent and 13/78 in `safety_flag`**; 0.0 gives 0.518 on all five runs with **0/78 unstable**. Reproducibility, not accuracy — 0.518 sits inside the 0.7 range. **0 dropped `safety_flag` events in 780 attempts**, against a pre-registered expectation of 0.3–1%. An earlier aborted run (~1 event in ~250 attempts) is included in the phase total below but was not separately itemised. `scripts/measure_temperature_variance.py` | **Yes** | 724,030 in / 35,195 out | $0.03026835 | ≈$0.04706 |

| 2026-08-12 | 7 (Stage 2) | **The k-sampled union baseline — the number `C1` attaches to.** 215 real `Converse` calls, `us.amazon.nova-micro-v1:0`, `us-west-2`, through the shipped `classify_turn` path at the now-pinned `temperature=0.0`: **all 43 items of the independent held-out set × k=5**, scored any-sample-miss. Measured against the **unchanged merged configuration**, deliberately before any candidate existed to be flattered by the comparison. Result: **union recall 1.000 (26/26) holds under repetition — no correction to Phase 6 owed** — with **0 of 43 items varying across five samples**, and union false-escalation reproduced at **0.529 (9/17) on a complete rule-based denominator** versus the original 0.529 over a partly hand-picked one. Ledger entry #1, fingerprint `889cb0bc0c8a011b`. `scripts/measure_union_baseline.py` | **Yes** | 199,435 in / 9,565 out | $0.00831932 | ≈$0.05538 |

| 2026-08-12 | 7 (Stage 4) | **The ablation ladder, rungs A–D**, `us.amazon.nova-micro-v1:0`, `temperature=0.0`, against `ADR-014` §4's pre-committed decision rule. Logged as two runs because the first was re-run after the discard bug (`319f354`): a classifier failure was discarding an already-resolved detector verdict, shrinking the false-escalation denominator 35→31. First run $0.162649 (`evals/baselines/ablation_ladder_20260812.json`); C and D re-run on the corrected full denominator $0.101777 (`..._CD_fixed_20260812.json`). **The ladder selected nothing** — D fails `C1` at recall 0.956, C fails criterion 2, B fails criterion 1. `scripts/run_ablation_ladder.py` | **Yes** | exact per-call counts in both baseline files | $0.264426 | ≈$0.31981 |
| 2026-08-12 | 7 (Stage 5) **[guardrail]** | **`ApplyGuardrail` safety-interference measurement**, guardrail `zl5ppnyorwd2` — the whole-configuration check that found the `C1` breach (**10 of 26 injury phrasings blocked at the input filter**, all from a denied topic, none from the VIOLENCE filter), plus the post-fix re-verification on the tuning set. ⚠ **Cost is an estimate, not a measurement**: `scripts/measure_guardrail_safety_interference.py` does not capture text-unit counts, so this is derived from ~4 passes over 43 short items ≈ 172 text units at $0.15/1k (content + denied topics) and $0.10/1k (PII), and is the one row in this log without exact instrumentation behind it. Fixing that instrumentation is carried, not done | **Yes** | ≈172 text units (est.) | **≈$0.043 (estimated)** | ≈$0.36281 |
| 2026-08-12 | 7 (Stage 6) | **Red-team suite, both runs.** Run 1 (9/11 defended, two live prompt injections) and run 2 after `ADR-015` (11/11): 7 real `Converse` calls each, $0.0001176 per run. Most attacks resolve at L1 or the input guardrail before generation, which is why the suite is nearly free. `redteam/run.py` | **Yes** | 2,848 in / 268 out | $0.0002352 | ≈$0.36305 |
| 2026-08-12 | 7 (Stage 6) | **`ADR-015` authority-check measurement**, `us.amazon.nova-lite-v1:0` through the real generation path against the real corpus. Three runs of 20 calls: dev set first pass ($0.00092826, **recall 0.0** — the run that showed the check did not work), dev re-verify ($0.0009273), and the **held-out set, run once** ($0.000729 — 0/12 false positives, 3/4 recall). `scripts/measure_authority_check.py` | **Yes** | 38,228 in / 1,212 out | $0.00258456 | ≈$0.36563 |

| 2026-08-12 | 7 (Stage 7) | **Paired-prompt bias check, text-level only.** 43 real `Converse` calls through the shipped `classify_turn` path plus 8 through the real generation path (`us.amazon.nova-micro-v1:0` + `us.amazon.nova-lite-v1:0`, `temperature=0.0`), over 13 base contents rendered in 2–5 surface variants differing only in caller name origin, register, or disfluency. Result: **escalation invariant and correct on all 43 turns** across all three axes; **2 of 5 register groups differ in routed intent**, one of them favouring the nonstandard variants. L1 fired 0/43, so every escalation decision was L2's. `scripts/measure_bias_pairs.py` | **Yes** | 45,842 in / 2,127 out | $0.00206153 | ≈$0.36769 |
| 2026-08-12 | 7 (Stage R) | **Retrieval — diagnosis only, no re-embedding.** ⚠ **$0.00, zero model calls.** The two `recall@5` misses were diagnosed offline against the committed Titan fixture; `cq-008` turned out to be a mislabelled gold (the retriever was returning the correct passage at rank 1) and was repaired through the new `--labels-only` path, which rewrites labels without touching a vector. `cq-005` is a genuine miss and was deliberately **not** tuned against. Logged with a zero because a stage that spent nothing still has to show it did | **No** | 0 | **$0.00** | ≈$0.36769 |

| 2026-08-12 | 7 (Stage 8) **[guardrail]** | **The composed-pipeline verification — the third and final independent-set fingerprint.** `L1 → ApplyGuardrail(INPUT) v2 → L2` over all 43 items of the independent held-out set at k=5: **215 real `Converse` calls** on `us.amazon.nova-micro-v1:0` at `temperature=0.0` ($0.00831932, 199,435 in / 9,565 out) plus **43 real `ApplyGuardrail` calls** on guardrail `zl5ppnyorwd2` v2. Result: **composed escalation recall 1.000 (26/26) — `C1` holds on the shipped system**; 0 blocked, 0 masked, 0 of 43 items varying across five samples. Ledger entry #4, fingerprint `55b7054762da8ae2`, live guardrail config sha `4f42baaf29042046`. **The ledger now publishes 3 distinct configurations.** `scripts/measure_composed_pipeline.py` | **Yes** | 199,435 in / 9,565 out; **86 guardrail text units, measured** (43 topic + 43 content; sensitive-information units 0 — Bedrock does not evaluate that policy on INPUT) | **$0.02121932** exact — $0.00831932 inference + **$0.01290 guardrail** | ≈$0.38891 |
| 2026-08-12 | 7 (Stage 8) | **`CF5`'s tuning pass — the `RentalTowingEntitlement` redundancy defect at temperature 0.0.** Three runs of 6 real calls each against the shipped `rental_towing_entitlement` node (`us.amazon.nova-micro-v1:0` routing where applicable + `us.amazon.nova-lite-v1:0` generation): a first pass through the whole graph that turned out to be measuring the router's no-match line ($0.00023625 — kept in the total, and the finding it produced is real: the router calls `rte-001`'s own first turn `Ambiguous` at 0.95), then two node-level passes ($0.00043344, $0.00041784). Result: **redundancy 0/3 at 0.0 and 0/3 at 0.7 — did not reproduce, and that is not a retirement**; general-mechanics leak 1/3 at 0.7 and 0/3 at 0.0; and **2–3 distinct answers per 3 identical calls at temperature 0.0**, which qualifies `D32`'s reproducibility claim. `scripts/measure_cf5_redundancy.py` | **Yes** | 17,958 in / 745 out across 18 calls | $0.00108753 | ≈$0.39000 |

| 2026-08-12 | 7 (Stage 8, post-approval) **[guardrail]** | **Guardrail v2 → v3 and the composed re-verification.** Marco typed `APPROVED` to drop the four `D16` regexes (`policy_number`, `claim_number`, `licence_plate`, `vin`) from `main.tf` — they masked the caller's own identifiers back to them on the OUTPUT path and broke the claim-status readback. `terraform apply`: **$0.00**, the guardrail resource is free at rest and only the policy set and the published version changed. Then the composition was **re-measured rather than inferred**, on Marco's instruction that *"a defensible per-setting change can move the composition"*: 215 real `Converse` calls + 43 real `ApplyGuardrail` calls against **v3**. Result: **composed escalation recall 1.000 (26/26), identical to v2** — 0 blocked, 0 masked, 0 unstable. Ledger entry #5, fingerprint `cec0cfcba5dd133c`, live config sha `8405563f3d54692d`. **The ledger publishes 4.** | **Yes** | 199,435 in / 9,565 out; **86 guardrail text units, measured** | **$0.02121932** exact — $0.00831932 inference + $0.01290 guardrail | ≈$0.41122 |

⚠ **`D46` is discharged for new runs only.** `GuardrailResult` now captures the `usage` block Bedrock
returns on every `ApplyGuardrail` call, so the Stage 8 guardrail figure above is the first in this log
measured to the text unit rather than estimated. **The Stage 5 row is not retro-fitted** — those calls
are gone and the units were never captured, so its ≈$0.043 stays labelled as an estimate. A number that
was estimated does not become measured by a later run being instrumented.

**Bedrock standing-approval cap consumed to date: ≈$0.411 of $5.00** (includes ≈$0.0013 for the aborted first Stage 0.5 run, which made ~250 real calls before a `ValidationError` ended it — the crash that became the dropped-field finding). Phase 6 closed at **$0.0134 of its $1.00
sub-budget**. **Phase 7 final: ≈$0.397 of its $1.25 sub-budget** — the $0.90 stop-and-report threshold was never reached, and the ablation ladder is 70% of the phase's spend. The phase's own estimate was ≈$0.30 against a $1.25 request, so the request was roughly 4× the outturn; recorded because a sub-budget that is routinely 4× the spend is a number nobody is really checking.

⚠ **This log fell behind its own rule.** Stages 4, 5 and 6 ran without being logged per-run as `D3`
requires, and the four rows above were reconstructed in one batch at the end of the phase from run
artifacts. Three of the four have exact per-call token counts recorded by the runs themselves; the
guardrail row does not, and is estimated. The running total was understated by ≈$0.31 for the duration.
Recorded rather than quietly corrected, because "logged per-run" is the control and a backfill is not
the same control.

**Phase 7 carries a named exception to `D3`:** the Bedrock Guardrail is a *provisioned resource*, not
on-demand inference, and `ApplyGuardrail` text units are not inference either. Both were approved explicitly
at Phase 7 sign-off rather than treated as covered by the standing approval — Marco: *"I want that distinction
preserved rather than blurred."* Guardrail rows in this log are tagged **[guardrail]** so the two kinds of
spend stay separable. See `PROJECT_STATE.md`'s 2026-08-11 session log for what each phase's calls verified, including
Stage 8's real-vs-fake divergence findings.

---

## Phase 8 — telephony and infrastructure as code

Three **separate** authorisations, kept separate in this log because Marco granted them separately:

| Line | Authorisation | Spent to date |
|---|---|---|
| **A. Provisioned resources** | `APPROVED: Phase 8`, **under $2** | **$0.00** |
| **B. Real inbound calls** | **20 calls, ≈$4** — a distinct line from the Phases 3–7 Bedrock cap. Marco: *"different resource class, different authorization"* | **$0.00** — 0 of 20 calls used |
| **C. `AWS::Lex::Bot` POC (Stage 2)** | Approved separately and on condition. Marco: *"A resource created to test whether we can create resources is exactly the thing that gets folded in silently and then never accounted for."* **Must be destroyed once the `ADR-007` gate resolves, pass or fail — it has no purpose after that** | **$0.00825** — ✅ **created, gate discharged, DESTROYED 2026-08-13** |
| **D. Stage 4's deployed `C1` re-verification** | `APPROVED: Stage 4`, 2026-08-13. Outside both the Bedrock standing cap and line B (no telephony minutes) — real `lexv2-runtime` requests plus the Bedrock/guardrail calls they trigger. Estimated **≤$0.09** before running, per Marco's condition | **$0.00** — 0 of 43 items run yet |

| Date | Stage | What ran | Real AWS call? | Units | Est. cost | Line |
|---|---|---|---|---|---|---|
| 2026-08-12 | 0 | **`Project` cost allocation tag activated.** `ce update-cost-allocation-tags-status`. No portal click, no resource | Yes (control plane) | 1 request | **$0.00** | — |
| 2026-08-12 | 0 | **State backend created.** `infra/terraform/bootstrap` — one S3 bucket + versioning, SSE-S3, public-access block, lifecycle, TLS-only policy. 6 resources. Deliberately **not** reached by `make destroy`, and `prevent_destroy` on the bucket | Yes | ~10 KB of objects | **$0.00** — kilobytes against a 5 GB account-age-independent allowance | A |
| 2026-08-12 | 0 | **Guardrail stack migrated off local state**, `terraform init -migrate-state`. Verified by a **no-change plan** against the migrated state, not by init reporting success. Phase 7's knowingly-taken debt, paid. Criterion 10 | Yes | — | **$0.00** | A |
| 2026-08-12 | 0 | **Cost attribution audit.** ~10 `ce:GetCostAndUsage` / `ce:ListCostAllocationTags` requests establishing the Canada DID rate, the credit-offset finding, and the per-line-item tag propagation table. `docs/phase8/COST-ATTRIBUTION-AUDIT.md` | Yes | ~10 CE requests | **≈$0.10** — the Cost Explorer API bills **$0.01/request**; see below | A |

| 2026-08-12 | 0.5 | **Application inference profiles created** — `infra/terraform/stacks/inference`, 4 profiles (`router`, `generation`, `judge`, `embedding`), `ADR-016`. Open decision A, approved by Marco. Routing/tagging records, not capacity | Yes | 4 resources | **$0.00 at rest** | A |
| 2026-08-12 | 0.5 | **One real `Converse` through the `router` profile ARN** — the check that the ARN is a working invocation path and not merely a well-formed resource. `us.amazon.nova-micro-v1:0` via `application-inference-profile/e55shbc6xaks` | Yes | 7 in / 2 out | **$0.00000053** | Bedrock standing cap |
| 2026-08-12 | 0.5 | **`GetInferenceProfile` region-set verification**, Marco's condition on `ADR-016`. Control-plane reads, no model calls. All three cross-region wrappers report `us-east-1, us-east-2, us-west-2` — the region set is inherited, not collapsed | Yes | control plane | **$0.00** | — |

| 2026-08-12 | 1 | **Protected telephony stack — DID imported.** `1 imported, 0 added, 0 changed, 0 destroyed`. No resource created, no tag modified. The number was already billing at $0.06/day since 2026-08-11 and continues to; importing it changes nothing about that | Yes | 1 import | **$0.00** | A |
| 2026-08-12 | 1 | **Import-guard and `prevent_destroy` demonstrations.** Scratch-copy plans against a wrong number ID and against an unsatisfiable tag condition, plus `terraform plan -destroy` on the real stack. Plans only — no apply, no resource touched | Yes (plan/read) | 3 plans | **$0.00** | — |

| 2026-08-12 | 2 | **`ADR-007` POC bot created** — `infra/terraform/stacks/lexpoc`. One `AWS::Lex::Bot` (11-slot intent, custom slot type, prompt-attempt + DTMF specs) inside `aws_cloudformation_stack`, plus an IAM role and inline policy. **Lex bills per request only** — no charge for storing a bot, for a locale build, or for any `lexv2-models` control-plane call | Yes | 3 resources | **$0.00 at rest** | **C** |
| 2026-08-12 | 2 | **Second apply — the gate itself.** Prompt string and DTMF `endTimeoutMs` changed together; both took, at definition *and* runtime, with the control field held still | Yes | 1 update | **$0.00** | C |
| 2026-08-13 | 2 | **Third apply — deletion.** A message group removed from the template stopped being served. The update replaces, it does not merge | Yes | 1 update | **$0.00** | C |
| 2026-08-13 | 2 | **`RecognizeText` runtime probes.** 3 per snapshot × 3 snapshots, plus 2 ad-hoc during the stale-window check. The only billable part of the whole gate, and the only instrument that could tell a current definition from a stale build | Yes | **11 text requests** @ $0.00075 | **$0.00825** | **C** |
| 2026-08-13 | 2 | **POC destroyed.** `0 added, 0 changed, 3 destroyed`. Residue verified rather than assumed: `list-bots` empty, `list-stacks` empty, `get-role fnol-lexpoc-runtime` → `NoSuchEntity`. Criterion 15 | Yes | 3 destroyed | **$0.00** | C |

| 2026-08-13 | 2 | **Tag-propagation probe (open item G).** Two `ce:GetCostAndUsage` calls grouped by `SERVICE` × `TAG:Project`. Every line reads `Project$` — untagged — including the AMCS-sold DID. **Inconclusive, not negative:** cost allocation tags are not retroactive and `Project` was activated during 08-12, so 08-11/08-12 would read untagged regardless. Re-check on 08-13's settled data | Yes | 2 CE requests | **$0.02** | A |

| 2026-08-13 | 3 | **`stacks/main` written, `terraform init` + `validate` + `plan`.** 23 resources: the six-intent Lex bot and its published version/alias (2 nested CFN stacks), the Connect↔Lex integration association, an inbound contact flow, hours of operation, the escalation queue, the codehook Lambda + log group + 2 permissions + Connect association, 2 IAM roles and policies, 2 DynamoDB tables, the artifacts bucket and its 4 configuration resources, 2 `terraform_data` markers. Plan only at first — the harness's permission layer initially declined the apply | Plan/read only | 23 planned | **$0.00** | A |
| 2026-08-13 | 3 | **`stacks/main` applied — 23 of 23.** Six defects surfaced and fixed against the live service along the way (`D76`, `D77`, `Synonyms` double-wrap, `CoverageQuestion` illegal utterance, `ConnectInstanceId` ARN shape, `BotAliasTags` array shape, `TagContact` missing `Errors` transition) — none visible to `plan`/`validate`. `terraform plan` reports no changes post-apply; `make verify-lex` passes against the live alias. Every read used to verify was a control-plane call (`Describe*`/`List*`/`GetTemplate`) — **no `RecognizeText`, no billable runtime request** | Yes | 23 created | **$0.00 at rest** | A |

✅ **Stage 3's delta is $0.00/month at rest, applied and verified 2026-08-13.** Retroactively correcting
this log's own previous row, which described a plan rather than the apply — this is the row criterion 13
asks for, late by one session because the apply itself ran past the point this file was last touched. Why
$0.00: **Lex bills per runtime request and not for storing a bot** (measured at Stage 2, not assumed);
Connect **contact flows, queues and hours of operation are not billed at all**; Lambda, DynamoDB on-demand,
S3 and CloudWatch are inside always-free allowances at this volume. Nothing in this stage placed a phone
call, and a phone call is the only thing here that costs money. Line A stays at **$0.12 of $2** — the $0.10
audit and the $0.02 probe, both Cost Explorer, neither a provisioned resource; the apply itself added
resources, not spend.

**Line C is closed at $0.00825.** The bot was free; the eleven sentences said to it were not. Everything
this POC found is in `docs/phase8/LEXPOC-GATE.md`, which outlives the resource.

### Line D — Stage 4's deployed `C1` re-verification, estimated before it runs

**`APPROVED: Stage 4`, 2026-08-13.** Marco's condition: *"approved as its own cost line, outside both the
Bedrock standing cap and the telephony allowance. Estimate it before running and log it separately."*

Stage 4 exit criterion 9 re-measures composed escalation recall (`C1`) against the **deployed** Lex alias
and Lambda — `D52`'s local run ($0.0212, 43 items × k=5) does not stand in for this, because this is the
first point `_FINGERPRINT_SOURCES` moves on a deployed resource rather than a local one.

**Protocol REJECTED by Marco, 2026-08-13, before any spend — the k=1 reasoning above does not hold.**
Verbatim: *"D32's qualification, in the boxed warning at the head of RESULTS.md, records that temperature
0.0 did NOT make the generation path reproducible — 2 to 3 different answers from 3 identical calls. The
router held; the generation path did not. And k on a deployed path is not measuring model stochasticity.
It is measuring cold starts, Lambda concurrency, Lex session handling, and timeouts — the variables that
do not exist locally and are precisely what this criterion exists to catch. k=1 cannot distinguish a
sound deployment from one that worked once."* Left the paragraph above unedited rather than rewritten —
the wrong reasoning is the record, same as the recording-behavior amendment in `CLAUDE.md` constraint 18.

**Protocol actually run, per Marco's instruction:** k=3 on the 26 must-escalate items only (not all 43;
criterion 9's own text gates on the 1.000 (26/26) recall figure, which is a statement about the
positives, and false-escalation on the negatives is not what this criterion checks). 78 base
`RecognizeText` calls. Path attribution (L1 pre-graph short-circuit vs. the graph's guardrail+L2 path) is
read back from the Lambda's own CloudWatch log line (`"escalating contact %s on layer %s route %s"`) for
each call, not assumed from `D52`'s local 7-L1/19-L2 split — that split is what local measurement saw;
whether the deployed Lambda's L1 lexicon fires identically is one of the exact things criterion 9 exists
to check, so it is read per call, not carried over as a given. The per-call dollar rate applied to
graph-path calls (guardrail 2 units + one L2 sample, $0.0003387) is still `D52`'s measured rate — Bedrock
itself was not re-instrumented for this run; only the path counts are exact.

| Component | Basis | Units | Est. cost |
|---|---|---|---|
| `lexv2-runtime:RecognizeText`, 26 must-escalate items, k=3 | $0.00075/text request | 78 requests | **$0.0585** |
| Bedrock (router + guardrail), graph-path calls only | `D52`'s per-call rate, applied to `D52`'s observed 19/26 L2-dependent ratio as a planning assumption — the real run reads this per call, see above | ≈57 of 78 calls | **≈$0.0193** |
| Lambda invocations | 1M req / 400k GB-s free tier, ≤102 invocations, arm64, low memory | ≤102 invocations | **$0.00** |
| Contingency: any item whose 3 samples are not unanimous gets 4 more samples, budgeted for up to 6 of the 26 items | Same per-call rates as above, worst case assumes all extra calls are graph-path | ≤24 requests | **≤$0.0299** |
| **Total, worst case** | | | **≈$0.107** |

**Estimate: ≈$0.078 expected, ≈$0.107 worst case.** Both inside Marco's "roughly double" expectation
(the original k=1/43-item line was ≈$0.05/≤$0.09) and, per his instruction, reported rather than trimmed
to fit — still 5.4% of the $2 provisioned line and 0.4% of the $25 hard ceiling. Logged here before the
run; the actual figure lands in the row below once criterion 9 executes, per criterion 13's per-run
discipline.

**RAN 2026-08-13. Result: no measurement obtained; run invalid (`D80`). `C1` is UNVERIFIED on the deployed
system, not failed** — corrected 2026-08-13 after Marco's review: *"0/26 is not a measurement. The
instrument returned nothing; it did not return zero."* He is right. The harness (`D81`, filed separately
below and in `RESULTS.md` §11) had no channel to distinguish "asked and did not escalate" from "never
executed," and silently scored a `Runtime.ImportModuleError` as 26 missed escalations. **`C1`'s status:
unverified on any deployed build, and unverified end-to-end on the current Lambda-wrapped configuration
at all** — the last build on which `C1` passed end-to-end was the LOCAL graph composition at fingerprint
`cec0cfcba5dd133c` (2026-08-13T01:56 UTC, recall 1.000/26/26, "Stage 8 re-verification after the
guardrail v2 → v3 change"), and that fingerprint predates `api/lex_codehook.py`, `agents/l3_lexicon.py`
and `aws/checkpointer.py` entirely — those files did not exist in the six-file set it hashed. **No build,
local or deployed, has ever verified `C1` end-to-end through the code that is now shipped.**
`scripts/measure_composed_pipeline_deployed.py`, result (corrected in place, raw value preserved under
`composed_recall_deployed_RAW_UNSCORED` rather than deleted) at
`evals/baselines/composed_pipeline_deployed_k3_20260813.json`.

Diagnosed the same way the flow-content bug was, earlier this stage: a real API probe, not a guess.
`aws cloudwatch get-metric-statistics` on `fnol-codehook` for the run's exact window shows **78
invocations, 78 errors — 100%**, not a partial or stochastic failure. `aws logs filter-log-events` on the
same window gives the actual cause: `"errorType": "Runtime.ImportModuleError", "errorMessage": "Unable to
import module 'fnol_voice_agent.api.lex_codehook': No module named 'pydantic'"`, on `platform.initStart`
— the crash is at **cold-start import time**, before `handler()` is ever entered, so `handler()`'s own
fail-open/fail-closed split (Stage 4's whole design for a graph failure) never runs either; there is no
code left to fail open or closed with.

Root cause, found in `infra/terraform/stacks/main/lambda.tf`: **the file's own header comment says
*"Stage 4's langgraph/boto3 requirements land as a Lambda layer, which is the change that makes package
size a real number"* — and no such layer, or any other dependency-bundling mechanism, exists in the
file.** `data.archive_file.codehook` zips `src/` only. `pyproject.toml`'s runtime dependencies —
`pydantic`, `langgraph`, `langgraph-checkpoint-aws`, `mcp`, `numpy`, `openfeature-sdk`, `python-dateutil`,
`PyYAML` — ship in none of them. `pydantic` surfaces first only because
`api/lex_codehook.py` imports `mcp.escalation_server` at module level (line 85) and that module imports
`pydantic` at ITS module level; every other undeclared dependency is equally absent and would fail the
same way the moment the import order reached it. **The deployed system has never once executed
successfully — not "broke," there is no prior working deployed state.** Stage 3's Lambda was a pure-stdlib
stub with nothing to import and nothing to verify; the first code that needed these dependencies is the
code that has failed 100% of its invocations (79/79, confirmed via CloudWatch) for the entire time it has
been live — every ordinary intent (`FileAutoClaim`, `CoverageQuestion`, all six), not only the safety
path. None of this was caught by the D77 read-back (`LastUpdateStatus:
Successful`, `State: Active`, `CodeSha256` match): that check verified the
right bytes were deployed and the function was schedulable, not that the function could execute past its
own import statements. Same shape as `RESULTS.md` §3.5's family — a check that is correct about what it
inspected and silent about the one layer up.

**Actual cost, exact, and lower than either estimate above:** because every one of the 78 run calls (plus
1 earlier diagnostic probe, same session) crashed at import time, **zero** reached Bedrock or the
guardrail — the conservative $0.0264 Bedrock line never happened. Cost is Lex-only: 79 `RecognizeText`
requests × $0.00075 = **$0.05925 exact**, no estimation involved on either side of it.

### Line E — criterion 9's re-run, post-`D83`, estimated before it runs

**Closed 2026-08-14 — ran clean, first time, actual $0.097668, inside the worst-case band below.** The
estimate that follows is left as originally written, pre-spend; the actual row is in the table above,
keyed `E`.

`scripts/measure_composed_pipeline_deployed.py`'s own header already names this destination —
`"COSTS.md Line D (invalidated) / Line E (this protocol)"` — written before `D80`/`D81`/`D82`/`D83` were
even found. Line D was never a valid measurement (`D80`); the `D82`/`D83` re-attempts were
`make verify-lambda-execution`'s smaller diagnostic gate, not this script, and both of those ran invalid
too (layer structure, then the timeout). **This script itself has never once completed.** The run this
line is estimated for is genuinely the first time it will, on a build where all four defects are fixed.

**Protocol is unchanged from Line D's** (k=3 on the 26 must-escalate items, k=1 on all 17 negatives,
contingency up to 6 items to k=7), so Line D's own estimate table is the applicable one, carried forward
rather than recomputed: **≈$0.078 expected, ≈$0.107 worst case.** A deliberately-forced cold invocation
(open question to Marco as of this entry — see the cold/warm question this line was written to answer)
does not change this figure: Lambda invocation count stays inside the always-free tier regardless of
container temperature (Line D's own table already prices that row at $0.00), and cold vs. warm changes
wall-clock init time, not which billed API each call makes or how many of them there are.

**Logged here, before any spend, per the same discipline Marco set for Line D:** *"approved as its own
cost line ... estimate it before running and log it separately."* The actual figure lands in a new row in
the table below, keyed `E`, once this run executes — not blended into Line D's row, which stays as the
record of the invalid run it actually was.

| Date | Stage | What ran | Real AWS call? | Units | Actual cost | Line |
|---|---|---|---|---|---|---|
| 2026-08-13 | 4 | **Criterion 9, deployed `C1` re-verification. No measurement obtained; run invalid (`D80`/`D81`).** `C1` is unverified on the deployed system, not failed. 79 `RecognizeText` calls (78 run + 1 diagnostic probe), 0 reached Bedrock. `scripts/measure_composed_pipeline_deployed.py` | **Yes** | 79 `RecognizeText` requests, 0 Bedrock calls | **$0.05925 exact** | **D** |
| 2026-08-13 | 4 | **`D80`/`D81` layer fix, `terraform apply` — `APPROVED` by Marco.** `2 added, 1 changed, 0 destroyed`: `aws_lambda_layer_version.codehook_deps`, `aws_s3_object.codehook_deps_layer` (41.8 MB), `aws_lambda_function.codehook` updated. Layer/S3 storage at this size is within the always-free tier region-wide; nothing here is a per-request cost until invoked | Yes | 3 resources | **$0.00 at rest** | — |
| 2026-08-13 | 4 | **`make verify-lambda-execution`, first real run (`D82` found it).** Estimated ~$0.0018 (6 of 9 events reach Bedrock). **Actual: $0.00** — every one of the 9 `lambda:Invoke` calls crashed at cold-start import (`D82`, the layer zip's missing `python/` prefix) before reaching the guardrail or router, the identical shape `RESULTS.md` §11.3 already named: cost-below-estimate as a liveness signal, confirmed a second time by a different instrument | Yes | 9 `lambda:Invoke` calls, 0 Bedrock calls | **$0.00 exact** | — |
| 2026-08-14 | 4 | **`D84` fix apply + `make verify-lambda-execution` re-run, both clean.** `terraform apply "d84.tfplan"`: `source_code_hash` change only, `CodeSha256` read back and confirmed (`u9iIy/DRjnv0Pd4lfkrXGo19O2hXM3L/UDPZ3Ud1ZYE=`). Gate: 9/9 events passed, ~$0.0018 estimated/actual (6 of 9 reach Bedrock) | Yes | 3 resources updated + 9 `lambda:Invoke` calls | **≈$0.0018** | — |
| 2026-08-14 | 4 | **Criterion 9, Line E, completed — first successful run of this script.** `scripts/measure_composed_pipeline_deployed.py` against `CodeSha256 u9iIy...` (post-`D84`): composed recall 1.000 (26/26), zero `invalid`, zero `fail-closed`, 95 real `RecognizeText` calls (78 positive-path + 17 negative). `RESULTS.md` §11.7 | **Yes** | 95 `RecognizeText` requests, 78 graph-path Bedrock/guardrail calls (cost basis, per script docstring) | **$0.097668** (lex $0.07125 + bedrock $0.026418) | **E** |
| 2026-08-14 | 4 | **Forced-cold probe (existence proof, 1 of 19), Terraform-managed.** `cold_probe_marker` bump + apply (config-only, same `CodeSha256`) invalidates warm environments in place of an out-of-band touch; `'we lost her'` sent as the first invocation after. Cold confirmed via `platform.report`'s `initDurationMs: 429.888`; escalated, `detection-graph`; `_get_graph()` construction 10.337s. `RESULTS.md` §11.7 | **Yes** | 1 `RecognizeText` request, 1 graph-path Bedrock/guardrail call | **≈$0.00109** (lex $0.00075 + bedrock ≈$0.00034) | — |
| 2026-08-15 | 11 | **Stage C `stacks/main` redeploy + `make verify-lambda-execution` re-run.** `terraform apply "stagec_redeploy.tfplan"`: `0 added, 2 changed, 0 destroyed` — `aws_lambda_function.codehook` (`CodeSha256` `u9iIy...`→`otOV3s1EXv/sK7XCW+85SrWvqmSYJE/FkUC6+Gikk68=`, confirmed live via `get-function-configuration`, plus an unrelated `FNOL_COLD_PROBE_MARKER`→`null` reversion, `RESULTS.md` §24), `aws_s3_object.codehook_deps_layer` (cosmetic etag only). Gate: 9/9 events passed, ~$0.0018 estimated (6 of 9 reach Bedrock) — actual not separately itemized from estimate, same shape as the two prior runs of this gate | Yes | 2 resources updated + 9 `lambda:Invoke` calls | **≈$0.0018** | — |
| 2026-08-15 | 11 | **`C1` re-verification against `CodeSha256 otOV3...`, `scripts/measure_composed_pipeline_deployed.py`, full protocol.** Composed recall **1.000 (26/26)**, 0 contingency items, 0 unstable items — same result as the prior build (`u9iIy...`), no per-item divergence. 9/17 negatives false-escalated (0.529, matching the exact figure on record from every prior run of this instrument — not a new finding). `RESULTS.md` §25 | **Yes** | 95 `RecognizeText` requests (78 positive-path + 17 negative), graph-path Bedrock/guardrail calls per the script's own cost basis | **$0.099023** (lex $0.07125 + bedrock $0.027773) | — |
| 2026-08-16 | 11 | **Stage B1 `stacks/main` + `stacks/observability` applies, then `make verify-lambda-execution` re-run.** `CodeSha256` `otOV3...`→`Wf84ZeuAj2ZGGxhiSIHm/NF7qfF97hhwb3mT+Bo5+RA=`, confirmed live via `get-function-configuration`, not the plan's claim. `codehook_deps_layer`'s etag also "changed" — the pre-existing multipart-ETag phantom diff, `OI3`, not a real content change. Gate: 9/9 events passed, ~$0.0018 | Yes | 3 resources updated (main) + 1 added (observability) + 9 `lambda:Invoke` calls | **≈$0.0018** | — |
| 2026-08-16 | 11 | **`C1` re-verification against `CodeSha256 Wf84ZeuA...`, `scripts/measure_composed_pipeline_deployed.py`, full protocol.** Composed recall **1.000 (26/26)**, 0 contingency items, 0 unstable items — no per-item divergence from `otOV3...`'s prior result. 9/17 negatives false-escalated (0.529, same figure as every prior run — not new). `RESULTS.md` §28 | **Yes** | 95 `RecognizeText` requests (78 positive-path + 17 negative), graph-path Bedrock/guardrail calls per the script's own cost basis | **$0.097668** (lex $0.07125 + bedrock $0.026418) | — |
| 2026-08-16 | 11 | **The single live invoke (`scripts/verify_stage_b1_live_invoke.py`), claims (a)/(b)/(c).** 1 `lambda:Invoke`, 1 real `ApplyGuardrail` INPUT call (1 `topicPolicyUnits` + 1 `contentPolicyUnits`) — the OUTPUT-side call was never reached (`D87` crash inside `check_claim_status`). Estimated ~$0.0007; actual lower because only the INPUT half of the estimated calls happened | Yes | 1 `lambda:Invoke`, 1 guardrail INPUT call, 1 Nova Micro router call | **≈$0.0004** (below estimate — explained by where the crash landed, not unexplained) | — |
| 2026-08-16 | 11 | **`D87` scope resolution (`scripts/verify_d87_scope.py`).** 2 real `lambda:Invoke` calls: `UpdateContactInfo` (all 4 slots pre-filled — confirmed broken, same shape as `claims_server.py`) and `CoverageQuestion` (election-fact-shaped turn — retrieval abstention fired before the gated branch, unreachable by this test). Estimated ~$0.001 | Yes | 2 `lambda:Invoke`, 2 guardrail INPUT calls, 1 guardrail OUTPUT call (CoverageQuestion reached `Close`), 2 router calls | **≈$0.0009** | — |
| 2026-08-16 | 11 | **`D87` Option A — scoped regression test (`verify_lambda_execution.py` events 10-11), run RED against the still-live pre-fix build (`Wf84ZeuA...`), per Marco's red-green requirement.** 11 events, 8 reach Bedrock (guardrail+router); the 2 new events failed with the exact `D87` `Delegate` signature, as predicted, before any fix was applied. `terraform plan` for the fix itself was run and reviewed (read-only, apply hard-denied) — **no apply this row, $0 for the plan itself.** `RESULTS.md` §31 | Yes | 11 `lambda:Invoke` (8 Bedrock-reaching) | **≈$0.0024** | — |
| 2026-08-16 | 11 | **`D87` Option A applied (Marco); `make verify-lambda-execution` GREEN re-run against `CodeSha256 8Ch4kDuL...`.** 11 events, 10/11 pass (`UpdateContactInfo` regression event fully green; `CheckClaimStatus` regression event reaches real fulfillment but fails a separate masking assertion — filed as `D88`, not a `D87` regression). `RESULTS.md` §32 | Yes | 11 `lambda:Invoke` (8 Bedrock-reaching) | **≈$0.0024** | — |
| 2026-08-16 | 11 | **`C1` re-verification against `CodeSha256 8Ch4kDuL...`, `scripts/measure_composed_pipeline_deployed.py`, full protocol — restores `C1` to VERIFIED post-`D87`-fix.** Composed recall **1.000 (26/26)**, 0 contingency, 0 unstable, no per-item divergence from prior builds. 9/17 negatives false-escalated (0.529, same figure as every prior run). `RESULTS.md` §32 | Yes | 95 `RecognizeText` requests (78 positive-path + 17 negative), graph-path Bedrock/guardrail calls per the script's own cost basis | **$0.097668** (lex $0.07125 + bedrock $0.026418) | — |
| 2026-08-16 | 11 | **`make verify-lambda-execution`, 13 events (11->13, `FileAutoClaim`/`RentalTowingEntitlement` events 12-13 added, tightening `D87`'s closure per Marco).** Against `CodeSha256 8Ch4kDuL...`, unchanged from the prior row. **10/13 pass** — 2 of the 3 failures are `D88` (already filed) and the new `D89`; event 13 (`RentalTowingEntitlement`) failed before its real `generate_response` call would have fired (misrouted to `CoverageQuestion`'s first-turn `ElicitSlot`), so the estimated generation-call cost was not actually incurred this run. `RESULTS.md` §33 §3 | Yes | 13 `lambda:Invoke` (10 Bedrock-reaching: 9 guardrail+router, 0 of the 1 budgeted generation calls actually fired) | **≈$0.0030** (printed estimate ~$0.0032 assumed the generation call would fire; it did not) | — |
| 2026-08-16 | 11 | **Diagnosis of `D89`/`D90` — 3 real, direct `ApplyGuardrail` INPUT calls + 1 real, direct `lambda:Invoke` (ad-hoc alternate-phrasing probe for `RentalTowingEntitlement`).** Guardrail calls: `"yes, go ahead and file it"` (BLOCKED, `legal_and_medical_advice`), `"yes, please submit that"` (NONE), `"yes that's correct, go ahead"` (NONE) — isolates the false-positive to the word "file". Lambda call: `"how many rental car days do I have left on my claim"` — reached `Close`/`Fulfilled` but via `CheckClaimStatus`, not `RentalTowingEntitlement` (silent misroute, `D90`). `RESULTS.md` §33 §3 | Yes | 3 `ApplyGuardrail` (2 policy units each) + 1 `lambda:Invoke` (guardrail+router, no generation call since it routed to a templated node) | **≈$0.0013** ($0.0009 guardrail calls + ~$0.0004 the invoke) | — |
| 2026-08-16 | 11 | **`D90` option B (`executed_node_intent` field) applied — `terraform apply "d90.tfplan"`, Marco.** `0 added, 2 changed, 0 destroyed`: `aws_lambda_function.codehook` (`CodeSha256` `8Ch4kDuL...`→`51JN903edLEVaSjP5zoEWQir4VLC+lQEVHA56b/5CUc=`, confirmed live via `get-function`), `aws_s3_object.codehook_deps_layer` (etag "changed" — `OI3`'s known phantom diff, confirmed this row to be a real re-upload of identical bytes to the same key, versioning off, no content change — see `OI3`'s corrected entry). `RESULTS.md` §36 | Yes | 2 resources updated (Lambda `UpdateFunctionCode` + S3 `PutObject`, 43.8MB, identical content) | **≈$0.00** (sub-cent; both operations are free-tier/negligible at this volume) | — |
| 2026-08-16 | 11 | **`make verify-lambda-execution`, pre-tightening sanity re-run against `CodeSha256 51JN903e...` (step 6 of the post-apply sequence).** 13 events, **10/13 pass** — same 3 failures as the prior build, for the same reasons (`D88`, `D89`, `D90` part 1's misroute); no deviation from the predicted set. `RESULTS.md` §36 | Yes | 13 `lambda:Invoke` (9 Bedrock-reaching: the event-13 generation call did not fire, misrouted before reaching it, same as the prior run of this gate) | **≈$0.0030** | — |
| 2026-08-16 | 11 | **Full `C1` harness (step 7), `scripts/measure_composed_pipeline_deployed.py`, against `CodeSha256 51JN903e...`.** Composed recall **1.000 (26/26)**, 0 contingency, 0 unstable, no per-item divergence from every prior build. 9/17 negatives false-escalated (same figure as every prior run — not new). **`C1` restored to VERIFIED.** `RESULTS.md` §36 | Yes | 95 `RecognizeText` requests (78 positive-path + 17 negative), graph-path Bedrock/guardrail calls per the script's own cost basis | **$0.097668** (lex $0.07125 + bedrock $0.026418) | — |
| 2026-08-16 | 11 | **Step 8 smoke tests — 3 direct `lambda:Invoke` calls confirming `executed_node_intent`'s presence/absence design.** ElicitSlot (fresh `FileAutoClaim`): field present, agrees with `intent.name`. Ordinary `Close` (`CheckClaimStatus`, slot pre-filled): field present, agrees. Pre-graph L1 escalation (`"my passenger isn't moving"`): field correctly ABSENT. `RESULTS.md` §36 | Yes | 3 `lambda:Invoke` (2 Bedrock-reaching, 1 pre-graph) | **≈$0.0006** | — |
| 2026-08-16 | 11 | **Step 10 confirmation probes — 2 direct `lambda:Invoke` calls re-checking events 10/11's exact construction**, to confirm (not infer) the node-identity check passed silently rather than reasoning from the gate's pass/fail line alone. `RESULTS.md` §36 | Yes | 2 `lambda:Invoke` (both Bedrock-reaching) | **≈$0.0006** | — |
| 2026-08-16 | 11 | **`make verify-lambda-execution`, post-tightening re-run (step 10) — events 10-13 now assert `executed_node_intent` directly.** 13 events, **10/13 pass, same count as pre-tightening but 2 events pass/fail for structurally different reasons now**: event 11 now passes via the structural field, not the message-template proxy; event 12 (`D89`) now fails with a direct "`executed_node_intent` absent" message instead of a template mismatch; event 10 still fails on the unrelated, pre-existing `D88` masking assertion (structural check now silently confirmed first); event 13 unchanged, same reason, same message (`D90` part 1 untouched by this fix). `RESULTS.md` §36 | Yes | 13 `lambda:Invoke` (9 Bedrock-reaching) | **≈$0.0030** | — |

⚠ **The Cost Explorer API is not free, and that is worth a line of its own.** `ce:GetCostAndUsage` bills
**$0.01 per request**. It is trivial next to a $25 ceiling, but it inverts the usual assumption that
*looking* at spend is free: an automated poller over Cost Explorer would be a genuinely stupid way to
breach the budget. The `AWS Cost Explorer` service line is already visible in this account's August usage
at $0.0100. Batch the queries; do not poll.

## Phase 9 — latency investigation, real-call experiments

`RESULTS.md` §11.15–§11.20 are `C14` latency-attribution work; the great majority is $0 read-only
(CloudWatch/Bedrock/Guardrails control-plane, AWS documentation search). This table covers the one item that
spent real money.

| Date | What ran | Real AWS call? | Units | Actual cost | Est. before running |
|---|---|---|---|---|---|
| 2026-08-14 | **Schema-strip pilot, `APPROVED: Phase 9 — schema-strip latency test, ~$0.10 ceiling`.** `scripts/measure_router_schema_latency.py`, 50 paired real `classify_turn` calls (unstripped tool schema vs. `title`/`$defs`-description-stripped variant), `us.amazon.nova-micro-v1:0`. Found 32% classification disagreement (16/50), including 4 dropped `safety_flag` verdicts — pre-registered pilot stop rule (`RESULTS.md` §11.19) triggered; main n=500 run never started. `RESULTS.md` §11.20 | **Yes** | 100 calls, 84,956 in / 4,263 out | **$0.00357028 exact** | ≈$0.004 (pilot) / ≈$0.10 (pilot + main, main not spent) |

Standing Bedrock approval (`CLAUDE.md`) is stated for Phases 3–7; this spend needed, and got, separate
explicit approval for Phase 9 rather than being assumed covered by that clause.

### The Canada DID, now measured rather than estimated

**`USW2-CA-did-numbers` = $0.06/day = $1.83/month.** Filed under
`Contact Center Telecommunications (service sold by AMCS, LLC)`, **not** under Amazon Connect — which is
why Phase 0 through Phase 7 all searched for it and found nothing. Confirmed on two independent days
(2026-08-11: 0.8388 days → $0.05033; 2026-08-12: 0.1667 days → $0.01000), so it is a measurement, not a
division of one number by another.

This is the project's **only always-on cost**, it started on 2026-08-11, it survives `make destroy` by
design, and at 7.3% of the monthly ceiling it is the single largest committed line in the project. The
**per-minute inbound** rate remains unmeasured and needs a real call to establish.

### Standing corrections to earlier figures in this log

🔴 **This account is on credits that currently offset 100% of usage**, contradicting `CLAUDE.md`'s
"assume no promotional credits." August gross usage is $2.5955 and net is **−$0.0000005646**. Every
figure in this log is a *gross* estimate and should stay that way; the credit balance is an unknown
buffer with no public API, not a budget.

### ✅ The Bedrock discrepancy, resolved 2026-08-12 by a third instrument

Marco: *"If our own logged token counts are right, one known call's cost is arithmetic — the question is
whether CE is missing data or the log is inventing it."* Exactly the right cut, and it did not need a new
call. **CloudWatch `AWS/Bedrock` publishes `InputTokenCount` / `OutputTokenCount` / `Invocations` per
`ModelId`, free, immediately, and counted by AWS rather than by us.** August, `us-west-2`:

| Model | Invocations | Input tok | Output tok | Cost at our rates |
|---|---|---|---|---|
| `us.amazon.nova-micro-v1:0` | 14,642 | 12,692,659 | 490,588 | $0.51293 |
| `us.amazon.nova-lite-v1:0` | 110 | 63,159 | 2,680 | $0.00443 |
| `amazon.titan-embed-text-v2:0` | 65 | 14,391 | — | $0.00029 |
| `us.anthropic.claude-haiku-4-5` | 10 | 3,571 | 837 | $0.00776 |
| **Total** | | | | **$0.52540** |

| Instrument | Figure | Verdict |
|---|---|---|
| This log (self-reported) | ≈$0.411 | **under-reports by 22%** |
| CloudWatch (AWS's count) | **$0.52540** | the reference |
| Cost Explorer | $0.00124 | **0.24% of actual — CE is missing data** |

**Cost Explorer is missing the data; the log is not inventing it.** Almost all of this project's Bedrock
usage landed on 2026-08-12, inside Cost Explorer's 24–48h settling window. The service was answering
honestly about a period it had not finished ingesting.

⚠ **And the direction is the opposite of what §6.2 of the audit guessed.** That section listed
"`COSTS.md` over-estimates" as the plausible candidate and reasoned that 11.4M Nova Micro input tokens
were implausible for this project's volume. **The real figure is 12.7M.** The estimate was not too high;
the volume was larger than assumed, and the log is 22% *low*. Recorded rather than quietly amended,
because the wrong guess and the reasoning behind it are the interesting part: the arithmetic was checked
against an intuition about volume, and the intuition was the weaker of the two.

**Corrected standing-cap position: ≈$0.525 of $5.00 consumed, not ≈$0.411.** Still comfortable. Every
per-run row above stays as written — they are what each run measured — but the phase totals derived from
them are floors, not totals.

The residual 22% is unattributed and is a real gap in this log. 14,642 Nova Micro invocations is more than
the itemised rows account for. Candidates: the ablation ladder's true call count (logged by dollar value,
not by call count), the aborted Stage 0.5 run (~250 calls, credited at ≈$0.0013), Phase 5's uninstrumented
first pass, and retries. Not chased further, because the reconciliation instrument now exists.

🔑 **The instrument lesson, which outlives the number.** This log is written by the code that makes the
calls — an instrument reporting on itself, which is `RESULTS.md` §3.10's failure shape applied to
accounting. CloudWatch has been counting the same calls independently, for free, all along, and nothing in
Phases 3–7 ever looked. **Criterion 13's per-run logging should be reconciled against
`AWS/Bedrock` token metrics from here on** — it costs nothing, it needs no code, and it is the only figure
in this project's cost accounting that we do not produce ourselves.

For context on the tag filter this phase depends on: the sibling fine-tuning project's
`USW2-Llama3-3-70B-Customization-Training` cost **$0.84935** on 2026-08-10, which is **99.86%** of the
account's August Bedrock spend.

---

**Correction, 2026-08-15 — the 2026-08-12 "Stages 5–6" row's item (c) is mislabeled.** Item (c) ("9
generation trials on `us.amazon.nova-lite-v1:0` (3 cases × 3, discharging CF3's repeated-sampling
requirement)") does not describe `CF3`. `CF3` is the Nova **Micro** tight-turn-path repeated-sampling
requirement (`PROJECT_STATE.md`); this line item is 3×3 Nova **Lite** generation trials judged for
redundancy, the same run `RESULTS.md` §5.1 describes as "Nova Lite judging Nova Lite... 3 trials × 3
cases" — `CF5`'s tuning work, not `CF3`'s. The dollar figure and call count are unaffected (both are part
of the same real, billed run, correctly totalled); only the parenthetical's *label* is wrong. Row left as
written, per this file's own standing convention ("every per-run row above stays as written... recorded
rather than quietly amended") — corrected here rather than by editing the 2026-08-12 entry. Full account:
`docs/RESULTS.md` §12.5.

---

## Phase 11 — `D90` part 1 (Option 1) build, latency measurement, and the `D97` gate re-run

**Logging gap, named rather than fixed here**: this is the first Phase 11 entry in this file. The phase's
substantial earlier real spend (the `D89` investigation's 33 `ApplyGuardrail` probes across `RESULTS.md`
§41/§43, the `verify-lambda-execution` gate's several prior runs, the Stage A/criterion-1 `ce` calls already
logged in the Non-Bedrock section below) was tracked inline in `RESULTS.md`'s own per-entry "Real spend"
lines but not ported here. Not backfilled retroactively this entry — flagged to Marco as a gap, not silently
left unmentioned.

| Date | What ran | Real AWS call? | Units | Actual cost |
|---|---|---|---|---|
| 2026-08-16 | **`D90` part 1, Option 1 latency smoke test.** `scripts/measure_router_context_latency.py --n-pairs 3`, paired real `classify_turn` calls (session-context-enriched vs. bare), `us.amazon.nova-micro-v1:0`, before the full run | **Yes** | 6 calls, 5,602 in / 272 out | **$0.00023415** |
| 2026-08-16 | **`D90` part 1, Option 1 latency measurement, full run.** Same script, `--n-pairs 141` — every real turn in `evals/golden/*.yaml`, paired and interleaved, bootstrap CI on delta-p95. Result: delta_p95 = +38.7ms, 95% CI [-51.3, +157.9]. `RESULTS.md` §45 §2 | **Yes** | 282 calls, 265,222 in / 12,777 out | **$0.01107155** |
| 2026-08-16 | **`verify-lambda-execution`, live re-run to re-confirm event 13 before writing the `D90` part 1 report.** This is the run that surfaced `D97`/`OI14` (live guardrail-version outage) — 10 of 13 events reached the real, now-failing `ApplyGuardrail` call before erroring; a `ValidationException` on a nonexistent identifier/version is very likely billed at $0 policy units (not independently confirmed against a `usage` block, since the error response carries none) | **Yes** | 10 events attempted `ApplyGuardrail`, all `ValidationException` | **$0.0032 (script's own pre-call estimate; likely an overstatement given the error path, not corrected down without a real `usage` block to confirm it)** |
| 2026-08-16 | **`verify-lambda-execution`, post-`stacks/main`-apply re-run confirming `D97`/`OI14` resolved.** 10/13, zero outage-shaped failures; 10 events reach real `ApplyGuardrail`/router calls, 1 (event 13) also makes a real generation call (`RESULTS.md` §52 §2) | **Yes** | ~10 guardrail+router events + 1 generation call | **$0.0032 (same pre-call estimate basis as the row above)** |
| 2026-08-16 | **Event 13 local repro** — one real `classify_turn` call against the exact `AgentState` `verify-lambda-execution`'s event 13 produces, confirming directly whether Option 1's context reaches the classifier (`RESULTS.md` §52 §3) | **Yes** | 1 call, small prompt | **~$0.0003 (estimate, not separately metered)** |
| 2026-08-16 | **Full `C1` harness, `scripts/measure_composed_pipeline_deployed.py`, against `CodeSha256 /4FFnR9Q7...`** — the post-batched-apply re-verification. Composed recall **1.000 (26/26)**, 0 contingency, 0 unstable, no per-item divergence. `C1` restored to VERIFIED. `RESULTS.md` §52 §4 | **Yes** | 95 `RecognizeText` requests (78 positive-path + 17 negative), graph-path Bedrock/guardrail calls per the script's own cost basis | **$0.097668** |

**Phase 11 running total, this table:** $0.01454570 + $0.0032 + $0.0003 + $0.097668 ≈ **$0.1157**.

**Approval basis, stated plainly rather than assumed:** `CLAUDE.md`'s standing Bedrock approval is scoped to
Phases 3–7. Phase 9's own precedent (above) needed, and got, a separate explicit `APPROVED: Phase 9 — ...`
line rather than being read as covered by that clause. **No equivalent `APPROVED: Phase 11 — ...` phrase was
typed for this entry.** What was given is Marco's explicit, current-turn instruction — *"Measure the latency
delta... I want the number before the apply, not after"* — read as authorization for this specific, small,
bounded, non-provisioning measurement, consistent with how the live diagnostic gate re-run earlier this
session was treated. Flagged here rather than silently treated as equivalent to a typed `APPROVED:` line, so
Marco can correct the convention if this reading was wrong.

## Non-Bedrock real spend — outside the $5.00 standing cap

Everything above is scoped to `CLAUDE.md`'s Bedrock standing approval. This section is for real AWS spend
this project incurs that is **not** Bedrock inference — a different budget line, tracked here so it isn't
silently absorbed into or confused with the cap above.

| Date | Phase | What ran | Real AWS call? | Est. cost | Running total (this section) |
|---|---|---|---|---|---|
| 2026-08-15 | 11 (Stage A) | **`ce get-cost-and-usage`, one real call** — MTD gross usage (`RECORD_TYPE=Usage`, `2026-08-01`–`2026-08-16`, `MONTHLY`, `UnblendedCost`), run to set Stage A's synthetic-breach test threshold against a re-verified real number rather than the stale ≈$2.60 figure `CLAUDE.md` had on record. Result: **$3.7828941608** (`Estimated: true` — CE's normal settling lag, not a defect). Doubles as the independent reference figure criterion 2's own liveness check will compare the dashboard's Lambda-pulled figure against, once that Lambda has run once — the comparison itself has not happened yet, only this call has. `RESULTS.md` §17.4, §19 | **Yes** | $0.01 exact (flat per-request rate, no free tier) | **$0.01** |
| 2026-08-16 | 11 (Stage A) | **Criterion 1 diagnostic — tag filter finding, `RESULTS.md` §39.** Marco declared one `$0.01` call; **two were actually spent**, an operator error, not a design choice: the first invocation went through `rtk`'s default filtering and returned truncated group data, so it was re-run via `rtk proxy` to get the full JSON — the same query, twice, because the first result was unusable rather than because a second measurement was needed. One `ce get-cost-and-usage` call, `RECORD_TYPE=Usage` filter, `GroupBy Type=TAG,Key=Project`, MTD `2026-08-01`–`2026-08-17`, us-east-1 (a single request returning a per-tag-value breakdown, chosen specifically so "tagged vs. untagged" needed only one call, not two — the duplication was execution error, not the query design). Also read (both free, no Budgets/SNS API charge): `budgets describe-budget` (`CalculatedSpend.ActualSpend = $0.48`) and `describe-notifications-for-budget` (all three `NotificationState: OK`), plus `sns list-subscriptions-by-topic` (subscription still `Confirmed`, real `SubscriptionArn`, not `PendingConfirmation`) | **Yes** | $0.01 × 2 (should have been 1) | **$0.03** |
| 2026-08-16 | 11 (Stage D93/OI10) | **`D93`/`OI10` threshold re-derivation — one `ce get-cost-and-usage` call**, `RECORD_TYPE=Usage`, `GroupBy Type=TAG,Key=Project`, MTD, us-east-1. Result: **$0.4795457178** tagged spend, used to lower `test_breach_threshold_usd` from $2.00 to $0.25. **Backfilled into this table now** — the call itself was made and reported to Marco in real time; this line was never added at the time, found and fixed while logging criterion 2's cost row below, not folded in silently | **Yes** | $0.01 | **$0.04** |
| 2026-08-16 | 11 (criterion 2) | **Criterion 2's cross-check — one `ce get-cost-and-usage` call**, `RECORD_TYPE=Usage`, `MONTHLY`, no tag filter (same shape as `ce_pull.py`), MTD `2026-08-01`–`2026-08-17`, us-east-1. Result: **$4.3355138372** (`Estimated: true`), compared against the dashboard's one existing Lambda-pulled datapoint ($3.7828941608, 2026-08-14) — `RESULTS.md` §75 | **Yes** | $0.01 | **$0.05** |

**Recurring, once Stage A applies (not yet incurred):** the weekly CE-pull Lambda backing criterion 2's cost
dashboard, ≈4–5 calls/month × $0.01 ≈ **$0.04–0.05/month, forever, by design** — this is the one Phase 11
line item with genuine non-zero recurring cost and does not zero out on `make destroy` unless the
schedule/Lambda are explicitly torn down. To be added to this table's running total once the apply that
creates it actually runs (`RESULTS.md` §17.2), and cross-referenced from `PROJECT_STATE.md`'s existing
"Pre-existing accrual" line (currently the Canada DID only) so it doesn't fall out of the project's ongoing-
cost picture the way a phase-scoped table would let it.
