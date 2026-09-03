"""Contact domain -- `UpdateContactInfo`'s write path (`docs/phase4/DIALOGUE-POLICIES.md` §4,
`docs/phase4/SLOT-DESIGN.md` §2; `docs/phase5/BUILD-PLAN.md` Stage 2).

Same ADR-012 shape as `policy_server.py`: everything above `main()` is plain, transport-agnostic
Python; nothing above `main()` imports the `mcp` package. See `policy_server.py`'s module docstring
for the full rationale.

**No real persistence layer yet** -- this is Phase 5 Stage 2 scope, not Phase 8's. The "write" mutates
an in-memory dict seeded once (per process) from Phase 3's synthetic
`data/synthetic/policyholders/policyholders.json`. That is explicitly fine at this stage per this
project's own instructions; what is *not* fine, and what this module is careful about regardless, is a
**partial** write (`PROBLEM-FRAMING.md`: "a silent partial write is the worst outcome") -- the mutation
is a single dict-key assignment, so there is no intermediate state in which the record has been read
back as changed for one caller and not another, or in which some sub-part of the record has moved and
another hasn't.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator

from fnol_voice_agent.models import ContactField
from fnol_voice_agent.models.policy import POLICY_NUMBER_PATTERN
from fnol_voice_agent.observability import tracing
from fnol_voice_agent.validation.identifiers import normalize_policy_number

from ._paths import POLICYHOLDERS_PATH


class PolicyNotFoundError(LookupError):
    """Raised when `policy_number` doesn't match any record in the synthetic policyholder corpus.

    A separate class from `policy_server.PolicyNotFoundError` -- this domain owns its own backing
    store (in a real deployment, contact info would live in its own service/table, not literally the
    same process-local dict `policy_server` reads), so it raises its own exception rather than
    importing one from a sibling domain module.
    """


class InvalidUpdateContactInfoError(ValueError):
    """Raised when `policy_number` fails its format, or `new_value` is empty/whitespace-only. Closes
    `docs/phase2/THREAT-MODEL.md`'s "MCP argument validation not yet built" residual risk for this tool.
    """


# `ContactField`'s slot names (`SLOT-DESIGN.md` §2) don't all match `Policyholder`'s record field names
# 1:1 -- `ContactField.MAILING_ADDRESS` is the string "mailing_address", but the synthetic corpus (and
# Stage 1's `Policyholder` model) call the same field `address`. Mapped explicitly here rather than
# assumed equal; discovered while wiring this handler against the real synthetic record, not designed
# in from a paraphrase.
_FIELD_TO_RECORD_KEY: dict[ContactField, str] = {
    ContactField.PHONE: "phone",
    ContactField.EMAIL: "email",
    ContactField.MAILING_ADDRESS: "address",
}


class UpdateContactInfoArgs(BaseModel):
    """Input schema for `update_contact_info` -- defined once, imported by nothing else (one adapter
    pair per tool)."""

    policy_number: str = Field(pattern=POLICY_NUMBER_PATTERN)
    field: ContactField
    new_value: str = Field(min_length=1)

    @field_validator("new_value")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("new_value must not be blank/whitespace-only")
        return value


class UpdateContactInfoResult(BaseModel):
    """Output schema -- defined once, returned unchanged by both adapters."""

    policy_number: str
    field: ContactField
    previous_value: str
    new_value: str
    updated: bool = True


_store: dict[str, dict[str, Any]] | None = None


def _get_store() -> dict[str, dict[str, Any]]:
    """Lazily seeds the in-memory store from the synthetic corpus, once per process. Both adapters call
    only `update_contact_info` (and, indirectly, this loader through it) -- neither one reads or
    mutates `_store` directly, so there is no side channel around the handler's own signature
    (`ADR-012`'s "no shared state reaching around the interface").
    """
    global _store
    if _store is None:
        payload = json.loads(POLICYHOLDERS_PATH.read_text())
        _store = {record["policy_number"]: dict(record) for record in payload["policyholders"]}
    return _store


@tracing.traced_mcp_tool("UpdateContactInfo", "contact")
def update_contact_info(
    policy_number: str, field: ContactField, new_value: str
) -> UpdateContactInfoResult:
    """Writes `new_value` to the one contact field named by `field`, for the policyholder identified by
    `policy_number`. Single atomic operation: the lookup and the mutation happen as one dict-key
    assignment, with no partially-applied intermediate state (see module docstring).

    Raises:
        InvalidUpdateContactInfoError: `policy_number` fails its format, or `new_value` is blank.
        PolicyNotFoundError: `policy_number` is well-formed but matches no record.
    """
    store = _get_store()
    # `AMAZON.AlphaNumeric` lowercases `policy_number`'s interpretedValue (confirmed live). Normalized
    # before `UpdateContactInfoArgs` is built: its pattern field is uppercase-only, so a raw "py4821"
    # fails validation before the dict lookup below is ever reached.
    #
    # `D207`/`OI125` follow-up, live evidence 2026-09-02: ASR also mis-hears the leading letter(s)
    # ("py4821" arrives as "uy4821"/"ty4821"), which uppercasing alone cannot fix. `normalize_
    # policy_number` tries a digits-only match against the real corpus first; if that resolves to
    # exactly one policy it returns the corrected value, otherwise it returns the uppercased original
    # unchanged, so a value it can't resolve reaches the format/not-found handling below exactly as it
    # would have before this fallback existed.
    policy_number = normalize_policy_number(policy_number, store)
    try:
        args = UpdateContactInfoArgs(policy_number=policy_number, field=field, new_value=new_value)
    except ValidationError as exc:
        raise InvalidUpdateContactInfoError(str(exc)) from exc

    record = store.get(args.policy_number)
    if record is None:
        raise PolicyNotFoundError(f"no policyholder found for policy_number={args.policy_number!r}")

    record_key = _FIELD_TO_RECORD_KEY[args.field]
    previous_value = str(record[record_key])
    record[record_key] = (
        args.new_value
    )  # single key assignment -- atomic, no partial state observable
    return UpdateContactInfoResult(
        policy_number=args.policy_number,
        field=args.field,
        previous_value=previous_value,
        new_value=args.new_value,
    )


def main() -> None:
    """MCP-server adapter: registers `update_contact_info` as a tool and serves it over stdio."""
    from mcp.server.mcpserver import MCPServer  # local import -- see policy_server.py's docstring

    server = MCPServer("fnol-contact-server", instructions=__doc__)
    server.add_tool(update_contact_info)
    server.run()


if __name__ == "__main__":
    main()
