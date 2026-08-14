variable "region" {
  description = "AWS region. Constraint 17 fixes this at us-west-2 for every stack in this project."
  type        = string
  default     = "us-west-2"
}

variable "project_tag" {
  description = "Value of the Project cost allocation tag. Must match the budget alarm's filter exactly."
  type        = string
  default     = "AWS-Insurance-FNOL-Voice-Agentic-AI"
}

variable "environment" {
  description = <<-EOT
    Value of the `Env` contact tag, per `docs/phase8/CONTACT-TAG-SCHEMA.md`.

    Its only job is to separate the 20 approved real calls from later throwaway testing in the one report
    where they would otherwise merge. `demo` is the default because that is what the approved calls are.
  EOT
  type        = string
  default     = "demo"

  validation {
    condition     = contains(["demo", "dev"], var.environment)
    error_message = "Env is one of demo|dev. The tag schema fixes the vocabulary; a free-form value would make the cost report unsummarisable."
  }
}

# ---------------------------------------------------------------------------------------------------
# Pre-existing infrastructure. Consumed, never created. Constraint 16.
# ---------------------------------------------------------------------------------------------------

variable "connect_instance_id" {
  description = "ID of the PRE-EXISTING Connect instance. Read as a data source; never created by this project."
  type        = string
  default     = "eba56246-0368-4f1c-8b97-e2ab3b0e8246"
}

variable "connect_instance_alias" {
  description = <<-EOT
    Alias the instance must report. Checked in a postcondition in `main.tf`, not trusted.

    This is the guard against a correct-looking instance id that points somewhere else -- the same shape
    as `stacks/telephony`'s `Protected=true` assertion, one resource over.
  EOT
  type        = string
  default     = "marcos-ivr-demo"
}

# ---------------------------------------------------------------------------------------------------
# Lex
# ---------------------------------------------------------------------------------------------------

variable "bot_name" {
  description = "Name of the FNOL bot."
  type        = string
  default     = "fnol-voice-agent"

  validation {
    condition     = can(regex("^([0-9a-zA-Z][_-]?)+$", var.bot_name))
    error_message = "Lex enforces ^([0-9a-zA-Z][_-]?)+$ on bot names and rejects the request outright otherwise."
  }
}

variable "bot_alias_name" {
  description = <<-EOT
    Alias Connect is associated with. STABLE by design -- the version behind it moves, the name does not.

    That is the whole purpose of an alias, and it is also what keeps the Connect integration ARN stable
    across bot changes so a prompt edit does not churn the contact centre association.
  EOT
  type        = string
  default     = "live"

  validation {
    condition     = can(regex("^([0-9a-zA-Z][_-]?)+$", var.bot_alias_name))
    error_message = "Lex enforces the same name pattern on aliases as on bots."
  }
}

variable "bot_description" {
  description = "Bot description, rendered into the CFN template so it is part of the definition hash."
  type        = string
  default     = "FNOL voice agent. Six intents, en_US. Phase 8."
}

variable "policy_number_prompt" {
  description = <<-EOT
    First-attempt elicitation prompt for `policy_number`.

    `SLOT-DESIGN.md` §1.2's canonical form is "What's your policy number?"; the deployed wording adds the
    `PY` hint, because Stage 2's live probe showed the bare question inviting the caller to read back a
    claim number instead. Templated rather than inline so `make verify-lex` can compare what Terraform
    declared against what Lex actually serves, from one source of truth — an echoed copy could drift.
  EOT
  type        = string
  default     = "Okay. What is your policy number? It starts with P Y."
}

variable "dtmf_end_timeout_ms" {
  description = <<-EOT
    How long Lex waits after the last keypress before treating DTMF entry as finished.

    3000 ms. Stage 2 moved this value from 5000 as the integer half of `ADR-007`'s gate and it stayed;
    5 s of silence after a caller has finished typing reads as the system having hung. `#` still ends
    entry immediately, so this bound is only reached by callers who do not press it.
  EOT
  type        = number
  default     = 3000
}

variable "nlu_confidence_threshold" {
  description = <<-EOT
    Below this, Lex routes the utterance to `AMAZON.FallbackIntent` instead of an intent.

    0.40 is Lex's own default and is kept deliberately rather than tuned here: `INTENT-TAXONOMY.md` §3
    puts disambiguation in the agent (one targeted clarifying question, never a silent pick), so a higher
    threshold would move a decision the design placed in the graph back into the bot, where it cannot be
    evaluated by Phase 6's harness.
  EOT
  type        = number
  default     = 0.40

  validation {
    condition     = var.nlu_confidence_threshold >= 0.0 && var.nlu_confidence_threshold <= 1.0
    error_message = "NluConfidenceThreshold is a probability."
  }
}

variable "idle_session_ttl_seconds" {
  description = "How long Lex keeps session state after the last turn. 300 s covers a caller pausing to find a document."
  type        = number
  default     = 300
}

variable "voice_id" {
  description = <<-EOT
    Polly voice. `PERSONA.md` picks a neutral North American English voice for a Canadian DID.

    Neural rather than standard is a Polly-side setting, not a bot-side one, and Lex uses the engine
    Connect requests; there is no cost decision hiding in this variable.
  EOT
  type        = string
  default     = "Joanna"
}

variable "lex_build_timeout_seconds" {
  description = <<-EOT
    How long to wait for the `en_US` locale to reach `Built` after CloudFormation reports success.

    Stage 2 measured the gap at ~16 s on three consecutive applies (`LEXPOC-GATE.md` §4.1). 600 s is
    generous by nearly two orders of magnitude on purpose: the failure this bound exists for is a build
    that has genuinely stalled, and a bound tight enough to trip on a slow day would train whoever hits
    it to raise the number rather than read the error.
  EOT
  type        = number
  default     = 600
}

# ---------------------------------------------------------------------------------------------------
# Lambda
# ---------------------------------------------------------------------------------------------------

variable "lambda_memory_mb" {
  description = <<-EOT
    Memory, which on Lambda also sets CPU share and therefore cold-start duration.

    512 MB, not tuned. `ADR-009` puts the cold-start measurement in Phase 9 and this project does not
    have a measured number yet; picking one here and calling it optimal would be exactly the invented
    figure `CLAUDE.md` forbids. Phase 9 moves it with evidence.
  EOT
  type        = number
  default     = 512
}

variable "lambda_timeout_seconds" {
  description = <<-EOT
    TEMPORARILY 60s for `D83` diagnosis (Marco-approved 2026-08-13) -- the steady-state value is 8s;
    see below. `Sandbox.Timedout` at exactly 8.00s with zero application log output is consistent with
    an in-flight retry loop that has not yet errored, not with a genuine indefinite hang -- at 60s the
    call either completes or throws a real boto3 exception naming an endpoint, which is the diagnosis
    this raise exists to get. This is not a workaround for the underlying defect and MUST be reverted
    to 8 once D83 is diagnosed.

    Steady-state rationale (restore this default when reverting): 8 s. Lex's own codehook timeout is
    30 s, but constraint 14's budget is 1,800 ms p95 end to end, so a codehook still running at 8 s has
    already failed the caller and should fail fast enough for the fallback to speak. A 30 s timeout
    would turn a hung turn into half a minute of silence.
  EOT
  type        = number
  default     = 60
}

variable "log_retention_days" {
  description = <<-EOT
    CloudWatch Logs retention. 14 days.

    Two reasons, and the second is the binding one. Cost: the free tier covers 5 GB of ingest, and
    indefinite retention is how a free log group becomes a billed one months after anyone looked.
    `ADR-011`: a transcript fragment that reaches a log is inside this project's redaction boundary only
    if something redacted it, and a bounded retention limits the blast radius of the case where nothing
    did.
  EOT
  type        = number
  default     = 14
}

# ---------------------------------------------------------------------------------------------------
# Connect
# ---------------------------------------------------------------------------------------------------

variable "hours_time_zone" {
  description = <<-EOT
    Time zone for the hours of operation. `America/Toronto` — the DID is Canadian and Ontario-area.

    Functionally near-irrelevant while the hours are 24/7, and set correctly anyway because the day it
    stops being 24/7 is the day nobody will re-derive which zone the number is in.
  EOT
  type        = string
  default     = "America/Toronto"
}

variable "greeting" {
  description = <<-EOT
    First thing the caller hears. Carries the AI disclosure `CLAUDE.md`'s Responsible AI section requires.

    **Now advertises the "say agent" override (`D75`), because it is true.** Route L3
    (`agents/l3_lexicon.py`) is implemented in the codehook, and the real Connect transfer (`D43`) is
    wired into this flow's `CheckEscalation`/`TransferToQueue` actions -- both landed in the same Stage 4
    commit as this default's change, not before it. Stage 3's default deliberately withheld this line for
    exactly the reason `NOT-FIXED.md` #2 states: *"a record with no transfer behind it is a different
    lie, not a smaller one."* The flow's content hash makes this change a new flow, not an edit to the one
    that was serving.
  EOT
  type        = string
  # No double quotes in the value -- this string is interpolated directly into fnol-inbound.json.tftpl's
  # "Text": "${greeting}" with no JSON-escaping step in between (templatefile() does plain string
  # substitution), so a literal `"` here would terminate the JSON string early and break the flow's own
  # syntax. Single quotes around the spoken word instead of double quotes, deliberately.
  default = "Thanks for calling claims. Just so you know, you're speaking with an automated assistant, not a person. If you'd like to speak with a person at any point, just say 'agent'."
}

variable "opening_question" {
  description = "Spoken by the Lex block as it starts listening. Kept open so the caller can lead."
  type        = string
  default     = "How can I help you today?"
}

variable "trouble_message" {
  description = <<-EOT
    Played when the Lex block itself errors out (`NoMatchingError`/timeout at the flow level, not an
    escalation -- an escalation now routes through `CheckEscalation`/`TransferToQueue`, `D43`, wired at
    Stage 4). This branch still promises nothing it cannot deliver: it tells the caller to call back,
    which costs nothing to be true.
  EOT
  type        = string
  default     = "I'm sorry, I'm having trouble on my end. Please call back and we'll try again."
}

variable "lex_session_timeout_seconds" {
  description = "How long Connect keeps the Lex session open. Matches the bot's own idle TTL so the two cannot disagree."
  type        = number
  default     = 300
}

# ---------------------------------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------------------------------

variable "checkpoint_table_name" {
  description = "LangGraph checkpointer table, `ADR-005`. Key schema is fixed by langgraph-checkpoint-aws: PK/SK, both String."
  type        = string
  default     = "fnol-agent-checkpoints"
}

variable "vector_table_name" {
  description = <<-EOT
    Knowledge-chunk vector store, `ADR-002`.

    The default MUST match `DEFAULT_TABLE_NAME` in `src/fnol_voice_agent/knowledge/ingest.py`, because
    `make ingest` writes to that name and this stack creates it. They are two literals for one fact and
    `tests/unit/test_stack_main.py` fails if they drift.
  EOT
  type        = string
  default     = "fnol-knowledge-chunks"
}

variable "artifact_retention_days" {
  description = <<-EOT
    Lifecycle expiry on the artifacts bucket.

    30 days. `ADR-011` puts redaction at the transcript boundary; retention is the control for what
    happens if a redaction pass is ever wrong, and an unbounded bucket has no such control at all.
  EOT
  type        = number
  default     = 30
}
