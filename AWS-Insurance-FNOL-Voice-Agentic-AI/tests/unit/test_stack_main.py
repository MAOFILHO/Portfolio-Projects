"""Static checks on `infra/terraform/stacks/main` — the ones a `terraform plan` cannot make.

Phase 8 Stage 3. Every assertion here is about a fact that is stated in two places and must agree, or
about a resource whose *absence* is the requirement. `terraform validate` checks that the configuration
is well-formed; nothing in Terraform checks that a default in `variables.tf` still matches a constant in
Python, or that nobody added a create-instance resource to the stack that must never create one.

No AWS calls, no credentials, no plan. This runs in `make test`.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from fnol_voice_agent.knowledge.ingest import DEFAULT_TABLE_NAME

REPO_ROOT = Path(__file__).resolve().parents[2]
STACK = REPO_ROOT / "infra/terraform/stacks/main"

#: `SLOT-DESIGN.md` §1.1's elicitation priority order, restated here so a reordering in the template has
#: to disagree with something. The order is a conversation-design decision (`ADR-007` residual gap R1),
#: and the bot is downstream of it — not the other way round.
EXPECTED_SLOT_ORDER = [
    "injuries_present",
    "policy_number",
    "insured_vehicle_vin",
    "loss_datetime",
    "loss_location",
    "loss_type",
    "damage_description",
    "other_party_involved",
    "police_report_filed",
    "police_report_number",
    "driver_name",
    # `D78`, Stage 4: the graph/codehook's own confirm-then-file step, no Lex slot behind it before now
    # -- see `bot.yaml.tftpl`'s comment at this exact entry.
    "confirm_file_claim",
]

#: `CLAUDE.md`: exactly six, no additions. `FallbackIntent` is required by the service and is not one.
EXPECTED_INTENTS = {
    "FileAutoClaim",
    "CheckClaimStatus",
    "CoverageQuestion",
    "RentalTowingEntitlement",
    "UpdateContactInfo",
    "InjuryEscalation",
}

#: `D70`. Identifier- and PII-bearing slots carry `DefaultObfuscation`. `loss_datetime` is deliberately
#: absent — `DOMAIN-ARTIFACTS.md`'s taxonomy correction forbids blanket-redacting loss date/time.
EXPECTED_OBFUSCATED = {
    "policy_number",
    "insured_vehicle_vin",
    "loss_location",
    "damage_description",
    "police_report_number",
    "driver_name",
    # `D78`: one name now, not two -- `claim_number` is declared independently by both CheckClaimStatus
    # and RentalTowingEntitlement (renamed from `entitlement_claim_number`), both obfuscated, and this
    # set is built from a regex scan across the whole template, not per-intent, so the two collapse into
    # one entry the same way `policy_number` already did across FileAutoClaim and UpdateContactInfo.
    "claim_number",
    "new_value",
}


def strip_yaml_comments(text: str) -> str:
    """Drop whole-line `#` comments.

    Needed because several assertions below are substring checks for a setting that must be ABSENT, and
    this repository's templates explain at length why each of those settings is absent. Matching the
    explanation instead of the configuration is the §3.5 mistake in miniature: it would check the prose
    and report on the resource.

    Only whole-line comments are dropped. An inline `#` inside a quoted YAML value is not a comment, and
    stripping it would corrupt a prompt string.
    """
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))


def strip_hcl_comments(text: str) -> str:
    """Drop `/* */` blocks and `#` / `//` line comments. Same reason as above."""
    without_blocks = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return "\n".join(
        line for line in without_blocks.splitlines() if not line.lstrip().startswith(("#", "//"))
    )


@pytest.fixture(scope="module")
def bot_template() -> str:
    """The bot definition with commentary removed — see `strip_yaml_comments`."""
    return strip_yaml_comments((STACK / "bot.yaml.tftpl").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def intents_section(bot_template: str) -> str:
    """Only the `Intents:` block.

    Slot TYPES sit at the same indentation as intents, so an indentation-anchored regex over the whole
    template counts `LossTypeValues` as a seventh intent — which would make the "exactly six" assertion
    fail for a reason that has nothing to do with intents.
    """
    return bot_template[bot_template.index("          Intents:") :]


@pytest.fixture(scope="module")
def terraform_source() -> str:
    return strip_hcl_comments(
        "\n".join(p.read_text(encoding="utf-8") for p in sorted(STACK.glob("*.tf")))
    )


# ---------------------------------------------------------------------------------------------------
# Constraint 16 — the instance is consumed, never created
# ---------------------------------------------------------------------------------------------------


def test_the_stack_declares_no_connect_instance_resource(terraform_source: str) -> None:
    """The single most expensive line that could be added to this directory.

    A `resource "aws_connect_instance"` would create a second contact centre on the next apply, and
    `make destroy` would then be able to delete one. The data source is fine and is what the stack uses;
    this asserts the resource form is absent, which `terraform validate` has no opinion about.
    """
    assert re.search(r'^resource\s+"aws_connect_instance"', terraform_source, re.M) is None


def test_the_stack_declares_no_phone_number_resource(terraform_source: str) -> None:
    """Constraint 16's other half. Releasing a claimed DID risks a 180-day block, and the number lives in
    `stacks/telephony` behind `prevent_destroy` and separate state."""
    assert re.search(r'^resource\s+"aws_connect_phone_number"', terraform_source, re.M) is None


def test_the_stack_does_not_read_the_protected_stacks_state(terraform_source: str) -> None:
    """Stage 3 does not point the DID at a flow, so it has no reason to know the number at all.

    Asserted rather than left to habit: the moment this stack has an edge into the protected stack is the
    moment a routine apply has a path toward it, and Stage 4 should add that edge deliberately.
    """
    assert "stacks/telephony/terraform.tfstate" not in terraform_source


# ---------------------------------------------------------------------------------------------------
# Two literals, one fact
# ---------------------------------------------------------------------------------------------------


def test_the_vector_table_default_matches_the_ingest_constant() -> None:
    """`make ingest` writes to `DEFAULT_TABLE_NAME`; this stack creates the table it writes to.

    If they drift, `make ingest` creates a second table on the fly — `DynamoVectorStore.ensure_table`
    does exactly that — and the deployed agent then queries an empty one. Nothing errors. The agent
    simply cannot answer a coverage question, and the corpus looks like the problem.
    """
    variables = (STACK / "variables.tf").read_text(encoding="utf-8")
    match = re.search(
        r'variable\s+"vector_table_name"\s*\{.*?default\s*=\s*"([^"]+)"', variables, re.S
    )

    assert match is not None
    assert match.group(1) == DEFAULT_TABLE_NAME


def test_the_lambda_handler_names_a_function_that_exists() -> None:
    """`handler = "fnol_voice_agent.api.lex_codehook.handler"` is a string in HCL. A rename in Python
    produces a runtime `Unable to import module` on the first call, which on this system means on a
    live phone call."""
    lambda_tf = (STACK / "lambda.tf").read_text(encoding="utf-8")
    match = re.search(r'handler\s*=\s*"([^"]+)"', lambda_tf)

    assert match is not None
    module_path, _, function_name = match.group(1).rpartition(".")

    module = __import__(module_path, fromlist=[function_name])
    assert callable(getattr(module, function_name))


def test_the_lex_session_timeout_matches_the_bot_idle_ttl() -> None:
    """Connect and Lex each hold their own idea of when the session is over. If Connect's is longer, the
    caller keeps talking to a bot that has already forgotten them."""
    variables = (STACK / "variables.tf").read_text(encoding="utf-8")

    def default_of(name: str) -> str:
        match = re.search(rf'variable\s+"{name}"\s*\{{.*?default\s*=\s*(\S+)', variables, re.S)
        assert match is not None, name
        return match.group(1)

    assert default_of("lex_session_timeout_seconds") == default_of("idle_session_ttl_seconds")


# ---------------------------------------------------------------------------------------------------
# The bot definition against the conversation design
# ---------------------------------------------------------------------------------------------------


def test_the_slot_priority_order_is_the_designed_order(bot_template: str) -> None:
    block = re.search(r"SlotPriorities:(.*?)\n\s{14}Slots:", bot_template, re.S)
    assert block is not None

    assert re.findall(r"SlotName:\s*(\w+)", block.group(1)) == EXPECTED_SLOT_ORDER


def test_the_bot_declares_exactly_the_six_intents(intents_section: str) -> None:
    declared = set(re.findall(r'^\s{12}- Name:\s*"(\w+)"', intents_section, re.M))

    assert declared == EXPECTED_INTENTS | {"FallbackIntent"}


def test_there_is_no_seventh_intent_for_the_agent_override(bot_template: str) -> None:
    """L3 — the hard "agent"/"human" override — is deliberately NOT a Lex intent.

    Mid-slot-elicitation an utterance is matched against the active slot type, so a caller saying "agent"
    while `policy_number` is being elicited produces a no-match rather than an intent switch. An intent
    would be reachable from most states and would look reachable from all of them. L3 belongs in the
    codehook alongside L1.
    """
    for forbidden in ("AgentEscalation", "TalkToHuman", "RequestAgent", "HumanHandoff"):
        assert forbidden not in bot_template


def test_the_fallback_intent_reaches_the_codehook(bot_template: str) -> None:
    """Load-bearing, not tidiness: this is what makes L1 and L3 reachable on a no-match turn, which is
    the only kind of turn they cannot afford to miss."""
    fallback = bot_template[bot_template.index('- Name: "FallbackIntent"') :]

    assert "DialogCodeHook" in fallback
    assert "Enabled: true" in fallback


def test_every_product_intent_reaches_the_codehook(intents_section: str) -> None:
    """`ADR-010`'s per-turn pipeline runs in the codehook. An intent without a dialog code hook is an
    intent whose turns never reach L1."""
    blocks = re.split(r'^\s{12}- Name:\s*"', intents_section, flags=re.M)[1:]

    for block in blocks:
        name = block.split('"', 1)[0]
        if name == "FallbackIntent":
            continue
        assert "DialogCodeHook:" in block, name
        assert "FulfillmentCodeHook:" in block, name


def test_the_obfuscated_slots_are_the_decided_set(bot_template: str) -> None:
    """`D70` as a checked fact rather than a preference.

    Two directions matter. A missing entry is an identifier that would reach a log unmasked the day
    logging is switched on; an unexpected extra is a value someone decided to hide without deciding it
    in the schema — and `loss_datetime` is the specific slot that must NOT be here.
    """
    obfuscated = {
        name
        for name, tail in re.findall(
            r'- Name: "(\w+)"\n(.*?)(?=\n\s{16}- Name: "|\Z)', bot_template, re.S
        )
        if "ObfuscationSetting:" in tail
    }

    assert obfuscated == EXPECTED_OBFUSCATED
    assert "loss_datetime" not in obfuscated


def test_sentiment_detection_is_off_everywhere(bot_template: str) -> None:
    """`DetectSentiment: true` is what AWS's own reference example ships, and it bills a Comprehend call
    per utterance — Phase 0's cost-hazard list."""
    assert "DetectSentiment: true" not in bot_template
    assert bot_template.count("DetectSentiment: false") >= 1


def test_the_lex_runtime_role_cannot_call_comprehend(terraform_source: str) -> None:
    """The permission half of the setting above. A grant for a call that should never happen is how a
    cost hazard gets switched on later without anything failing."""
    assert "comprehend" not in terraform_source.lower()


# ---------------------------------------------------------------------------------------------------
# The release stack's staleness fix
# ---------------------------------------------------------------------------------------------------


def test_the_bot_version_logical_id_carries_the_definition_hash() -> None:
    """`AWS::Lex::BotVersion` has no property that changes when the bot's definition changes, and AWS
    documents that an unchanged DRAFT yields the previous version rather than a new one. The logical ID
    is the only lever that forces a republish — `RESULTS.md` §3.5.1 instance 1, in a second service.
    """
    release = (STACK / "release.yaml.tftpl").read_text(encoding="utf-8")

    assert re.search(r"^\s{2}BotVersion\$\{definition_hash\}:", release, re.M) is not None


def test_the_alias_declares_no_conversation_logs() -> None:
    """`D70`. Slot obfuscation does not cover missed utterances or values read back in responses, and
    this design does both."""
    release = (STACK / "release.yaml.tftpl").read_text(encoding="utf-8")

    assert "ConversationLogSettings:" not in release


def test_the_release_waits_on_the_build_rather_than_on_the_apply() -> None:
    """Stage 2 finding 4.1. Without the explicit dependency Terraform infers only the `BotId` edge, which
    is satisfied the moment the bot stack returns — 16 seconds too early."""
    lex_tf = (STACK / "lex.tf").read_text(encoding="utf-8")
    release_block = lex_tf[lex_tf.index('resource "aws_cloudformation_stack" "release"') :]

    assert "terraform_data.bot_built" in release_block


def test_the_wait_is_not_a_sleep(terraform_source: str) -> None:
    """A fixed sleep encodes the 16 s that happened to be measured once, and fails downstream when it is
    wrong — in `CreateBotVersion`, with an error about the version rather than about the build."""
    lex_tf = (STACK / "lex.tf").read_text(encoding="utf-8")

    assert "time_sleep" not in terraform_source
    assert "wait_for_lex_build.py" in lex_tf


# ---------------------------------------------------------------------------------------------------
# The flow's rollback story
# ---------------------------------------------------------------------------------------------------


def test_the_flow_is_replaced_rather_than_updated_in_place() -> None:
    """The unique name is necessary and not sufficient.

    `aws_connect_contact_flow` treats both `name` and `content` as updatable — the provider calls
    `UpdateContactFlowName` and `UpdateContactFlowContent`. Without `replace_triggered_by` plus
    `create_before_destroy`, a content change renames and overwrites the live flow in place, which is
    exactly what the unique name was supposed to prevent while looking like it had been prevented.
    """
    connect_tf = (STACK / "connect.tf").read_text(encoding="utf-8")
    block = connect_tf[connect_tf.index('resource "aws_connect_contact_flow" "inbound"') :]

    assert "create_before_destroy = true" in block
    assert "replace_triggered_by" in block


def test_the_flow_name_carries_the_content_hash() -> None:
    connect_tf = (STACK / "connect.tf").read_text(encoding="utf-8")

    assert 'name        = "${local.name_prefix}-inbound-${local.flow_version}"' in connect_tf


def test_the_flow_version_tag_and_the_flow_name_use_one_hash() -> None:
    """`CONTACT-TAG-SCHEMA.md` consequence 2: one source, two uses. Two independently computed hashes
    would let the billing tag and the deployed flow disagree about which version ran."""
    connect_tf = (STACK / "connect.tf").read_text(encoding="utf-8")

    assert connect_tf.count("local.flow_version") >= 3
    assert "flow_version = local.flow_version" in connect_tf


# ---------------------------------------------------------------------------------------------------
# `D43`, Stage 4 — the real transfer
# ---------------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def flow_document() -> dict[str, Any]:
    """Parses the shipped flow template exactly the way `scripts/check_flows.py` does -- placeholders
    substituted with a marker, not resolved by a real `terraform console` call, so this stays as fast and
    dependency-free as the rest of this file."""
    from scripts.check_flows import parse_flow

    text = (STACK / "flows" / "fnol-inbound.json.tftpl").read_text(encoding="utf-8")
    document = parse_flow(text)
    assert document is not None
    return document


def test_the_queue_id_passed_to_the_flow_is_the_real_escalation_queue() -> None:
    """Not a second queue, not a hardcoded ID -- the same resource `aws_connect_queue.escalation`
    declares, so a caller who is transferred reaches the queue this stack actually provisions."""
    connect_tf = (STACK / "connect.tf").read_text(encoding="utf-8")

    assert "escalation_queue_id = aws_connect_queue.escalation.queue_id" in connect_tf


def test_the_flow_checks_the_escalate_attribute_and_transfers_on_it(
    flow_document: dict[str, Any],
) -> None:
    actions = {a["Identifier"]: a for a in flow_document["Actions"]}

    check = actions["CheckEscalation"]
    assert check["Type"] == "Compare"
    assert check["Parameters"]["ComparisonValue"] == "$.Attributes.escalate"
    condition_targets = {c["NextAction"] for c in check["Transitions"].get("Conditions", [])}
    assert "TransferToQueue" in condition_targets

    transfer = actions["TransferToQueue"]
    assert transfer["Type"] == "TransferContactToQueue"
    # `parse_flow` substitutes every `${...}` with a marker (see its own docstring), so the variable
    # NAME has to be checked against the raw template text instead.
    assert transfer["Parameters"]["QueueId"] == "TEMPLATED"
    raw_text = (STACK / "flows" / "fnol-inbound.json.tftpl").read_text(encoding="utf-8")
    queue_id_line = next(line for line in raw_text.splitlines() if '"QueueId"' in line)
    assert "escalation_queue_id" in queue_id_line


def test_a_normal_call_that_never_escalates_still_reaches_goodbye(
    flow_document: dict[str, Any],
) -> None:
    """`CheckEscalation`'s un-matched path (the overwhelming majority of calls) must still end the call
    normally -- a `Compare` action with no fallback would strand every non-escalated caller."""
    actions = {a["Identifier"]: a for a in flow_document["Actions"]}

    assert actions["CheckEscalation"]["Transitions"]["NextAction"] == "Goodbye"


def test_the_greeting_now_names_the_agent_override() -> None:
    """`D75`: this line is only true once `D43`'s real transfer and L3 both exist, which is why it was
    withheld until this exact commit rather than at Stage 3."""
    variables_tf = (STACK / "variables.tf").read_text(encoding="utf-8")
    block = variables_tf[variables_tf.index('variable "greeting"') :]
    default_line = next(line for line in block.splitlines() if line.strip().startswith("default"))

    assert "agent" in default_line.lower()
    # `templatefile()` does plain string substitution with no JSON-escaping step -- a literal `"`
    # anywhere inside the value would break `fnol-inbound.json.tftpl`'s own "Text": "${greeting}" syntax.
    # The line is `default = "...value..."`, so exactly two `"` characters are expected: the delimiters.
    assert default_line.count('"') == 2, default_line
