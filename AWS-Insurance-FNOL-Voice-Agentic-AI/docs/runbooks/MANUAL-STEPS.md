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
- **Console path** (from the AWS doc above, "How to switch to Customer Basic"):
  1. Log in to the AWS Management Console.
  2. In the console search box, type **Connect Customer**. Choose **Connect Customer**.
  3. On the **Connect Customer virtual contact center instances** page, choose the instance alias
     **`marcos-ivr-demo`**.
  4. In the navigation pane, choose **Connect Customer**.
  5. In the **Enable Connect Customer across your entire instance** section, confirm the status is
     **enabled** (it is — this is the current default state).
  6. Choose **Disable**.
  7. A confirmation dialog appears asking to confirm the switch to Customer Basic. Choose **Disable** to
     confirm.
- **Rollback:** the same page's toggle re-enables Connect Customer (**Enable** button) if this needs to be
  reversed — no data loss expected either direction since this project's flows never reference any
  Connect-Customer-only feature (`ADR-001`), so the documented "may encounter runtime errors if these
  features are configured in contact flows" warning does not apply here.
- **Post-switch verification:** confirm the instance's Connect Customer status reads "Not enabled" /
  Customer Basic in the console, and place one test call through the existing sample flow to confirm inbound
  calls and Lex association still function unchanged (the switch only removes bundled-AI capabilities this
  project never wired in).

## Executing this step

I (Claude Code) do not have AWS Management Console/browser access — no MCP tool in this session provides
interactive console UI actions, only the SigV4 API surface via `aws-mcp`, which (per `docs/phase2/COST-MODEL.md`'s
research) does not expose this particular toggle. **Marco needs to perform the six console steps above
directly.** This is consistent with Marco's own stated preference to "do it myself on a protected resource."
