# Runbook — operating the Bedrock Guardrail

Resource: `fnol-voice-agent-guardrail`, id `zl5ppnyorwd2`, region `us-west-2`.
Managed by `infra/terraform/stacks/guardrails/` (local state in Phase 7; migrated to the remote backend
in Phase 8). `$0.00/mo at rest` — only evaluations bill.

---

## ⚠ 1. Editing a guardrail does not publish a new version

**Read this before changing any policy in `main.tf`.** The failure is silent **in both directions**: the
configuration looks correct and the behaviour is stale.

`aws_bedrock_guardrail_version` depends on the guardrail's **ARN**, and the ARN does not change when the
policy does. So a plain `terraform apply` after a policy edit:

- **updates DRAFT** — the console shows your change, `terraform plan` is clean, `terraform state show`
  shows the new value;
- **leaves every published version pointing at the old configuration**;
- and any caller pinned to `guardrailVersion = "1"` keeps getting the **pre-edit** behaviour.

Nothing errors. Nothing warns. This is exactly how it was found in Phase 7 Stage 5: a denied topic was
narrowed to fix a `C1` breach, the apply succeeded, and a measurement against version 1 would have
reported the **pre-fix** behaviour while every artifact in the repo said the fix was live. Same shape as
`ADR-013`'s moto bug — a call that returns, against the wrong thing, looking like it worked.

**The stack already guards this:**

```hcl
lifecycle {
  replace_triggered_by = [aws_bedrock_guardrail.fnol]
}
```

**Do not remove that block.** It is the only thing making a policy edit produce a new immutable version.

### After any policy change

1. `terraform apply` and **read the version output** — it must have incremented.
   ```
   terraform -chdir=infra/terraform/stacks/guardrails output guardrail_version
   ```
2. **Update every pinned caller** to the new version. `BedrockGuardrailClient` takes
   `guardrail_version` as a required argument with no default, so a stale pin is a wrong number rather
   than a crash — nothing will tell you.
3. **Re-run the safety interference measurement** (§2). A policy edit can block injury phrasings from any
   policy, not only the one you touched.

### Never point production at `DRAFT`

`ApplyGuardrail` accepts `DRAFT`, and it moves whenever anyone edits the resource. A red-team or eval
result measured against `DRAFT` is unattributable to a configuration — the same problem the eval ledger's
config fingerprint solves for the router. Always pin a published version, and record it in the report.

---

## 2. The one measurement that must be re-run after any guardrail change

```bash
PYTHONPATH=. .venv/bin/python scripts/measure_guardrail_safety_interference.py \
    --guardrail-id zl5ppnyorwd2 --guardrail-version <NEW> --set tuning
```

**Why this and not the red-team suite:** the input guardrail sits **upstream of L2**. `ADR-010` sequences
L1 first, so a block cannot pre-empt L1 — but a blocked turn never reaches the router, and roughly 73% of
indirect injury phrasing is L2's to catch. A guardrail block is therefore a recall defect that `C1` cannot
see and no detector test will catch.

Phase 7's pre-fix configuration blocked **10 of 26** injury phrasings on the independent set. All ten came
from a denied topic written for an unrelated purpose, not from the violence filter. **Any policy edit can
reintroduce this**, including one that looks entirely unrelated to safety.

Use `--set tuning` for iteration. `--set independent` is a **declared verification run**: it appends to
`evals/holdout_ledger.json`, and the count of distinct fingerprints there is published in `RESULTS.md`.
Spend it deliberately, not while debugging.

---

## 3. Teardown and rebuild

```bash
terraform -chdir=infra/terraform/stacks/guardrails destroy   # $0 either way; nothing accrues at rest
terraform -chdir=infra/terraform/stacks/guardrails apply
```

`make destroy` removes this stack. It does **not** touch `stacks/telephony` (the protected DID).

**If the local state file is lost**, the guardrail is orphaned but costs `$0.00/mo` and is findable by
name (`fnol-voice-agent-guardrail`). Re-import rather than recreating, or you will have two:

```bash
terraform -chdir=infra/terraform/stacks/guardrails import aws_bedrock_guardrail.fnol <guardrail-id>
```

---

## 4. Known gaps, so nobody rediscovers them

- **A blocked turn promises a transfer the graph does not perform.** `guardrail_blocked_response` says
  *"let me connect you with someone who can"* and goes to `END` — no `initiate_escalation()`, no
  `EscalationRecord`, no retry-ladder entry. Contradicts `D18`. See `docs/phase7/NOT-FIXED.md`.
- **The denied topic is narrower than its own examples.** *"I need to claim on my husband's life insurance
  policy"* is a configured example and is **not** blocked by the current definition. Narrowing it to stop
  blocking injury descriptions cost some coverage, and that trade is real rather than rounded away.
- **Topic definitions are capped at 200 characters.** Exceeding it fails the apply with a
  `ValidationException` that does not name the offending topic.
