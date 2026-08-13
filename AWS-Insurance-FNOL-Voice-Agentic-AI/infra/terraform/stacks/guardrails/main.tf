/*
 * The Bedrock Guardrail — Phase 7 Stage 5, the phase's only provisioned resource.
 *
 * WHY THIS IS TERRAFORM AND NOT A boto3 SCRIPT
 *   CLAUDE.md: "Zero portal clicks. 100% IaC." A create-guardrail script is neither a portal click nor
 *   IaC, and `make redteam` measuring our own mock rule engine would be the "stubbed out and labelled
 *   production-would-do-X" failure the same document forbids outright.
 *
 * STATE -- MIGRATED TO THE REMOTE BACKEND, PHASE 8 STAGE 0 (2026-08-12)
 *   Phase 7 ran this stack on local state as an explicitly approved, explicitly temporary debt. The
 *   residual risk was stated at the time as "lose the local state file and the guardrail is orphaned --
 *   a $0/mo orphan, findable by name (`fnol-voice-agent-guardrail`), and `scripts/verify_billable.py`
 *   looks for it." That debt is now paid: state lives in the bucket created by `infra/terraform/
 *   bootstrap`, versioned and locked. Phase 8 criterion 10.
 *
 * COST
 *   The guardrail RESOURCE is free at rest -- there is no hourly or monthly charge for its existence.
 *   Only evaluations bill, at $0.15/1k text units (content filters, denied topics) and $0.10/1k (PII,
 *   contextual grounding). `make destroy` removes it. This is why it can be gated separately from the
 *   inference standing approval (`D3`) without anyone worrying about a forgotten teardown.
 *
 * WHAT IS DELIBERATELY ABSENT
 *   - No `contextual_grounding_policy_config`. It scores a model answer against a source passage, which
 *     is `evals/tier_b.py`'s judge's job in this project, and paying twice to measure the same property
 *     with a less transparent instrument is not an improvement.
 *   - No Automated Reasoning checks. `CLAUDE.md` records their pricing unit as unconfirmed, and this
 *     phase does not use them, so the unconfirmed line does not bind.
 *   - No `blockedInputMessaging` cleverness: the graph decides what a caller hears (`D17` -- almost every
 *     spoken line is a fixed string), so the guardrail's own message text never reaches a caller.
 */

terraform {
  # 1.10 rather than the project-wide 1.9 floor, for the same reason as the bootstrap stack:
  # `use_lockfile` does not exist before it, and silently running unlocked is worse than failing init.
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # A backend block cannot interpolate variables or locals -- these must be literals, which is why the
  # bucket name is duplicated here rather than referenced. `terraform output -raw state_bucket` in
  # infra/terraform/bootstrap is the authority; `make verify-backend` compares the two so the
  # duplication is checked rather than trusted.
  #
  # `use_lockfile` is native S3 state locking (Terraform >= 1.10). It replaces the DynamoDB lock table,
  # which was a billable resource this project has no use for at one operator.
  backend "s3" {
    bucket       = "fnol-voice-agent-tfstate-759316130780-us-west-2"
    key          = "stacks/guardrails/terraform.tfstate"
    region       = "us-west-2"
    encrypt      = true
    use_lockfile = true
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project = "AWS-Insurance-FNOL-Voice-Agentic-AI"
      Owner   = "marcos"
      Phase   = "7"
      Managed = "terraform"
    }
  }
}

resource "aws_bedrock_guardrail" "fnol" {
  name                      = var.guardrail_name
  description               = "FNOL voice agent input/output guardrail. Invoked via standalone ApplyGuardrail (ADR-010), never bolted onto a model call."
  blocked_input_messaging   = "BLOCKED_INPUT"
  blocked_outputs_messaging = "BLOCKED_OUTPUT"

  /*
   * Content filters.
   *
   * INPUT strength is deliberately LOW for VIOLENCE and NONE for the rest, and this is the single most
   * consequential choice in this file. A caller describing a collision -- "he went through the
   * windscreen", "there's blood everywhere" -- is producing exactly the input a violence filter is built
   * to catch, and blocking it would silence the utterances the safety detector exists to hear. `ADR-010`
   * already sequences L1 strictly before this call so a block cannot pre-empt escalation; the filter
   * strength is the second layer of that same defence, because a guard that relies solely on ordering
   * fails the moment someone reorders it.
   *
   * OUTPUT strength is HIGH across the board. The system's own speech has no legitimate reason to
   * contain any of this, and `D17`/`D20` mean only two prompts generate at all -- so a HIGH output filter
   * constrains a very small surface and cannot accidentally gag a fixed string.
   */
  content_policy_config {
    filters_config {
      type            = "VIOLENCE"
      input_strength  = "LOW"
      output_strength = "HIGH"
    }
    filters_config {
      type            = "SEXUAL"
      input_strength  = "NONE"
      output_strength = "HIGH"
    }
    filters_config {
      type            = "HATE"
      input_strength  = "NONE"
      output_strength = "HIGH"
    }
    filters_config {
      type            = "INSULTS"
      input_strength  = "NONE"
      output_strength = "HIGH"
    }
    filters_config {
      type            = "MISCONDUCT"
      input_strength  = "NONE"
      output_strength = "HIGH"
    }
    /*
     * The one filter this project actually needs on INPUT. A caller pasting policy text that instructs
     * the assistant to waive a deductible is a real item in the golden set (`adv-*`), and it is the
     * threat model's named injection channel alongside retrieved KB chunks and tool responses.
     */
    filters_config {
      type            = "PROMPT_ATTACK"
      input_strength  = "HIGH"
      output_strength = "NONE" # PROMPT_ATTACK is an input-only filter; NONE is required here.
    }
  }

  /*
   * Denied topics. Scoped to what is genuinely out of scope for a P&C auto FNOL line, not to everything
   * unpleasant. CLAUDE.md puts health and life claims explicitly out of scope, and the golden set's
   * out-of-scope conversations are exactly these.
   */
  topic_policy_config {
    /*
     * NARROWED 2026-08-12, after measurement. The first definition read "Questions about health,
     * medical, dental, disability or life insurance policies, claims, coverage or benefits" and it
     * blocked **10 of 26 injury phrasings on the independent held-out set** -- "I can't feel my
     * legs", "we lost her", "I'm doing CPR right now, please just send someone". Bedrock's topic
     * classifier keyed on *medical subject matter*, not on whether an insurance product was being
     * asked about, and a caller describing a medical emergency is saturated with medical language.
     *
     * That was a C1 breach sitting upstream of L2: a blocked turn never reaches the detector, and 6
     * of the 10 were phrasings L1 provably misses. Every other setting in this file was individually
     * defensible; the composition was not. `RESULTS.md` §3.9.
     *
     * The definition now requires a question about **an insurance product other than auto**, and
     * says so in terms of the product rather than the subject matter. The examples are all
     * unambiguous product questions, and the definition states the exclusion explicitly because the
     * classifier reads the definition text.
     */
    topics_config {
      name       = "non_auto_insurance_products"
      type       = "DENY"
      definition = "Questions about a NON-AUTO insurance product: health, dental, disability, life, home or travel coverage, benefits or claims. Describing injury or death after a car crash is NOT this topic."
      examples = [
        "Does my health plan cover this hospital stay?",
        "I need to make a claim on my husband's life insurance policy.",
        "Is my dental work covered under my benefits?",
        "How much is the premium on my travel insurance?",
      ]
    }
    topics_config {
      name       = "legal_and_medical_advice"
      type       = "DENY"
      definition = "Requests for legal advice about liability, litigation or settlement strategy, or for medical advice about injuries or treatment. The agent takes a first notice of loss; it does not advise."
      examples = [
        "Should I sue the other driver?",
        "Do I need to see a doctor for this or will it heal on its own?",
        "What's the most I could get if I take them to court?",
      ]
    }
  }

  /*
   * PII. ANONYMIZE rather than BLOCK on every entity.
   *
   * ⚠ THIS POLICY IS OUTPUT-ONLY, AND THAT IS BEDROCK'S BEHAVIOUR, NOT A CHOICE MADE HERE. Verified
   * live at Stage 8: on `source="INPUT"` an email, a phone number and a `PY####` policy number all
   * returned `sensitiveInformationPolicyUnits: 0` and `action: NONE`; the same strings masked correctly
   * on `source="OUTPUT"`. Until Stage 8 the comment here claimed input-side "defence in depth on the
   * same boundary" and justified ANONYMIZE over BLOCK with "a caller who says their phone number
   * mid-sentence must not have the turn rejected". The reasoning was sound and the mechanism was
   * absent -- a documented capability that does not run, which `CLAUDE.md` forbids as plainly as a stub.
   * `ADR-011`/`D16`'s redaction before persistence is `guardrails/pii.py`'s, and always was.
   *
   * What remains here is what the AGENT might say. Each entity below is one the system has no
   * legitimate reason to speak aloud, so masking it costs nothing and catches a generation defect.
   *
   * NAME is deliberately absent. The FNOL record needs the claimant's name, redacting it here would
   * strip the field the call exists to capture, and `guardrails/pii.py` owns the transcript-side
   * treatment where it belongs.
   */
  sensitive_information_policy_config {
    dynamic "pii_entities_config" {
      for_each = toset([
        "EMAIL",
        "PHONE",
        "CREDIT_DEBIT_CARD_NUMBER",
        "US_SOCIAL_SECURITY_NUMBER",
        "CA_SOCIAL_INSURANCE_NUMBER",
        "DRIVER_ID",
        "PASSWORD",
      ])
      content {
        type   = pii_entities_config.value
        action = "ANONYMIZE"
      }
    }

    /*
     * NO `regexes_config`, REMOVED 2026-08-12 (v2 -> v3), Marco-approved: "the guardrail masking a
     * caller's own claim number, policy number and plate back to the caller who owns them is a defect
     * with no upside." `docs/phase7/NOT-FIXED.md` #8, `RESULTS.md` §5.3.
     *
     * Four regexes lived here -- `policy_number`, `claim_number`, `licence_plate`, `vin` -- added under
     * `D16` because Phase 0 archaeology found the upstream PII taxonomy had none of them and they are
     * precisely the identifiers this domain leaks. The requirement was real. The BOUNDARY was wrong.
     *
     * Bedrock evaluates this policy on OUTPUT only, and on OUTPUT these four match the agent's own
     * speech -- so the shipped system masked `CLM-2608-00042-4` out of the claim-status readback and,
     * with `blocked` conflating mask and block, replaced the whole line with a refusal. Four settings
     * each individually defensible; a composition that broke one of the six in-scope intents.
     *
     * Transcript-side redaction of these identifiers is `guardrails/pii.py`'s and is unaffected --
     * `D16`'s requirement is still met, at the boundary `ADR-011` put it at. Nothing was weakened here;
     * a duplicate was removed from a boundary that could not host it correctly.
     */
  }
}

/*
 * A published version. `ApplyGuardrail` can target DRAFT, but DRAFT moves when the resource is edited,
 * which would make a red-team result unattributable to a configuration -- the same problem the eval
 * ledger's config fingerprint solves for the router. The version number goes in the report.
 */
resource "aws_bedrock_guardrail_version" "fnol" {
  guardrail_arn = aws_bedrock_guardrail.fnol.guardrail_arn
  description   = "Phase 7 Stage 5"

  lifecycle {
    create_before_destroy = true

    /*
     * WITHOUT THIS, EDITING THE GUARDRAIL DOES NOT PUBLISH A NEW VERSION.
     *
     * Found the hard way. Narrowing the denied topic updated DRAFT and left version 1 pointing at the
     * old configuration, so a measurement against version 1 would have reported the *pre-fix*
     * behaviour while every artifact said the fix was applied. That is the same false-verification
     * shape as `ADR-013`'s moto bug: a call that returns, against the wrong thing, looking like it
     * worked.
     *
     * `aws_bedrock_guardrail_version` has no implicit dependency on the guardrail's *content* -- only
     * on its ARN, which does not change when the policy does. This makes the dependency explicit, so
     * a policy edit always produces a new immutable version to pin measurements to.
     */
    replace_triggered_by = [aws_bedrock_guardrail.fnol]
  }
}
