# Runbook — Permitted manual steps

This project is zero-portal-clicks / 100% IaC by default (`CLAUDE.md`, Engineering constraints). The
handful of exceptions are enumerated here, each with what it is, why it's manual, and — where applicable —
the exact console path. Nothing outside this list is a permitted manual step; a new one requires updating
this file and `CLAUDE.md`'s "Only permitted manual steps" line together, in the same commit, with Marco's
named approval.

---

## 1. The Connect instance

- **What:** `marcos-ivr-demo`, `eba56246-0368-4f1c-8b97-e2ab3b0e8246`, ACTIVE, `CONNECT_MANAGED`, inbound-only.
- **Why manual:** pre-provisioned before this project started; the STOP CONDITIONS forbid ever creating a
  second one. Terraform consumes it via data source/import (`infra/terraform/stacks/telephony`), never
  `create-instance`.
- **Console path:** N/A — already done, not repeated.

## 2. The admin user

- **What:** the AWS Connect admin user on the instance.
- **Why manual:** pre-provisioned alongside the instance, same rationale as #1.
- **Console path:** N/A — already done, not repeated.

## 3. The DID

- **What:** `+14169871547`, `PhoneNumberCountryCode: CA`, id `55cba0a6-3f67-4982-b3d8-6943d3b07054`, CLAIMED,
  tagged `Protected=true`.
- **Why manual:** already claimed before this project started; releasing and re-claiming a number risks a
  **180-day claim block**, so Terraform never touches its lifecycle (`prevent_destroy = true`, separate
  state, `stacks/telephony`'s import guard asserts `Protected=true` before proceeding).
- **Console path:** N/A — already done, not repeated.

## 4. Connect Customer → Connect Customer Basic instance-tier switch

- **What:** switching the existing instance's billing/feature tier from **Connect Customer** ($0.038/min,
  the default on all new instances, including ours) to **Connect Customer Basic** (~$0.0202/min).
- **Why manual:** confirmed 2026-08-11 against `docs.aws.amazon.com/connect/latest/adminguide/enable-nextgeneration-amazonconnect.html`
  that this is an instance-level toggle, not fixed at creation — so it does **not** require a new instance
  and carries **no DID risk**. But it is **console-only**: neither the Connect `UpdateInstanceAttribute` API's
  documented attribute types nor Terraform's `aws_connect_instance` resource expose this toggle. No IaC path
  exists as of this writing.
- **Why this project takes it:** this project's architecture (`ADR-001`) deliberately does not use any of
  Connect Customer's bundled AI (agentic voice/chat, ACXD no-code canvas, AI agent observability, generative
  speech, forecasting) — it uses Lex V2 for turn management and its own Bedrock/LangGraph stack for
  everything else. Connect Customer Basic matches what this project actually uses; the bundled-AI tier was
  never a deliberate choice, only the default a newly created instance ships with. See `docs/phase2/COST-MODEL.md`
  for the recalculated worst-case cost this switch creates.
- **Approval:** Marco approved this switch by name, 2026-08-11 ("Approved — switch the instance to Connect
  Customer Basic via the console").
- **Console path** — ⚠ **corrected 2026-08-11 against Marco's actual screenshot; the AWS doc page cited
  above uses different labels than the live console.** Two corrections: the left-nav item reads **"Customer"**,
  not "Connect Customer"; the action is a **"Change"** button on a **"Confirm Amazon Connect Customer"** card,
  not a "Disable" button. Confirmed path:
  1. Log in to the AWS Management Console.
  2. In the console search box, type **Connect Customer**. Choose **Connect Customer** (this part matched —
     it's the landing search, not an in-instance label).
  3. On the **Connect Customer virtual contact center instances** page, choose the instance alias
     **`marcos-ivr-demo`**.
  4. In the left navigation pane, choose **Customer** (breadcrumb reads *Amazon Connect › marcos-ivr-demo ›
     Customer*).
  5. On the **Customer** page, scroll to the **Confirm Amazon Connect Customer** card.
  6. Choose **Change**.
  7. *(Not directly observed — the post-switch screenshot doesn't show this step. Expect a tier-selection
     prompt at this point; select **Amazon Connect Customer Basic** and confirm.)*
  8. Confirmed done: the page now shows a green banner — **"This instance is now Amazon Connect Customer
     Basic - some capabilities may no longer be available"** — and the **Confirm Amazon Connect Customer**
     card shows **Amazon Connect Customer Basic** selected.
- **Rollback:** the same **Change** button on the **Confirm Amazon Connect Customer** card should offer the
  reverse selection if this needs to be undone — not directly observed either, same caveat as step 7 above.
  No data loss expected either direction since this project's flows never reference any Connect-Customer-only
  feature (`ADR-001`), so the documented "may encounter runtime errors if these features are configured in
  contact flows" warning does not apply here.
- **Post-switch verification:** ✅ the green confirmation banner and the card's selected state are the
  console's own verification, both captured in Marco's screenshot. Placing one test call through the sample
  flow to confirm inbound calls and Lex association still function unchanged is optional additional
  verification, not yet separately done.

## Executing this step

I (Claude Code) do not have AWS Management Console/browser access — no MCP tool in this session provides
interactive console UI actions, only the SigV4 API surface via `aws-mcp`, which (per `docs/phase2/COST-MODEL.md`'s
research) does not expose this particular toggle. **Marco needs to perform the six console steps above
directly.** This is consistent with Marco's own stated preference to "do it myself on a protected resource."

### ✅ Done — 2026-08-11

Marco performed the switch via the console and confirmed with a screenshot: the instance's Customer page
shows the banner **"This instance is now Amazon Connect Customer Basic - some capabilities may no longer be
available"** and the **Confirm Amazon Connect Customer** section shows **Amazon Connect Customer Basic**
selected, on the `marcos-ivr-demo` instance. No contact-flow runtime errors expected or reported — this
project's flows never reference a Connect-Customer-only feature (`ADR-001`), consistent with the pre-switch
assessment. Post-switch verification (one test call through the sample flow) not yet separately confirmed —
note if that's still outstanding.

---

## 5. Required-status-check branch protection for the eval gate

- **What:** marking the `AWS-Insurance-FNOL-Voice-Agentic-AI Eval Gate` workflow's `eval-gate` job as a
  **required status check** on `main` in `MAOFILHO/Portfolio-Projects`'s GitHub repo settings, so a red run
  actually blocks a merge instead of only reporting one.
- **Why manual:** a GitHub branch-protection rule is a repo setting, not a resource either Terraform or
  this project's own IaC can reach — same category as item 4 above, a real toggle with no API surface this
  project's tooling touches.
- **Why this is its own step, not bundled with landing the workflow:** confirmed 2026-08-14 — `main` on
  `MAOFILHO/Portfolio-Projects` currently has **no branch protection at all**
  (`gh api repos/MAOFILHO/Portfolio-Projects/branches/main/protection` → 404, "Branch not protected"). Once
  the workflow file lands at the monorepo root (Phase 10 criterion 3, its own go/no-go), it will **run and
  report a status but not block anything** until this step is done separately. Marco's instruction,
  2026-08-14: land the workflow, confirm it runs green on a real push, *then* add this setting — not as a
  side effect of the copy.
- **Console path:** repo **Settings → Branches → Add branch protection rule** (or **Rulesets**, GitHub's
  newer equivalent) on `main`, enabling **"Require status checks to pass before merging"** and selecting
  the `eval-gate` job once it has run at least once (GitHub only offers a check as selectable after it has
  reported at least one status).
- **Status:** ✅ **Done — 2026-08-16.** Update 2026-08-14: Phase 10 criterion 3 (the workflow copy) is
  **landed** — `/Users/marco/K21/Real-world/.github/workflows/aws-insurance-fnol-voice-agentic-ai-
  eval-gate.yml`, Marco-approved by absolute path, byte-identical to the authored source (sha256 verified).
  Update 2026-08-15: Marco pushed `origin/main` to `c08184c` from a terminal outside the working session;
  the first real run — `31887876709`, event `push`, `head_sha c08184c5`, `2026-08-15T13:41:24Z`,
  `conclusion: success` — now exists (verified against the remote via `git fetch` + `gh api`, not local
  state; `docs/RESULTS.md` §14). GitHub then offered `eval-gate` as a selectable required status check.
  **Update 2026-08-16: the console click itself done.** Classic branch-protection rule (not a ruleset) on
  `main`, "Require status checks to pass before merging" enabled, `eval-gate` selected; "Require a pull
  request before merging" and "Require branches to be up to date" both deliberately left unchecked, so a
  direct push to `main` still bypasses the check entirely — recorded, not an oversight. `docs/RESULTS.md`
  §40. **Scoped narrowly to this file's own "What" above** — the console click only. Phase 11 criterion 6
  (`PROJECT_STATE.md`) adds a separate negative-control requirement on top of this step, tracked there, not
  here; this item's own completion does not by itself close that criterion.
