"""Policy domain -- `GetPolicyholderElections` (`docs/phase4/DIALOGUE-POLICIES.md` §2's named forward
requirement; `docs/phase5/BUILD-PLAN.md` Stage 2).

**ADR-012 compliance, concretely**: everything above `main()` is plain, transport-agnostic Python --
it reads Phase 3's synthetic `data/synthetic/policyholders/policyholders.json` and returns Stage 1's
`Policyholder` model. Nothing above `main()` imports the `mcp` package. `main()` is the only place
that import happens, and only when this module is actually executed as a server
(`python -m fnol_voice_agent.mcp.policy_server`) -- importing this module in-process, the way a Stage 6
LangGraph node will, never touches the `mcp` transport SDK at all.

Two adapters, one handler, per ADR-012:
  - **In-process adapter**: `get_policyholder_elections` itself, imported and called directly.
  - **MCP-server adapter**: `main()`, which registers that same function as a tool and serves it over
    stdio -- the command `.claude/mcp.json` runs, and the same command
    `tests/unit/test_mcp_wire_protocol.py` launches as a real subprocess.
"""

from __future__ import annotations

import json

from pydantic import BaseModel, Field, ValidationError

from fnol_voice_agent.models import Policyholder
from fnol_voice_agent.models.policy import POLICY_NUMBER_PATTERN

from ._paths import POLICYHOLDERS_PATH


class PolicyNotFoundError(LookupError):
    """Raised when `policy_number` doesn't match any record in the synthetic policyholder corpus."""


class InvalidPolicyNumberError(ValueError):
    """Raised when `policy_number` doesn't match the `PY####` format (`docs/phase3/DATA-CONTRACTS.md` §2)
    -- distinct from `PolicyNotFoundError` so a caller (or the MCP client, or a test) can tell a
    malformed argument apart from a well-formed one that simply isn't on file. Closes
    `docs/phase2/THREAT-MODEL.md`'s named "MCP argument validation not yet built" residual risk for
    this tool.
    """


class GetPolicyholderElectionsArgs(BaseModel):
    """The one input schema this domain defines -- defined once here, imported by nothing else (there
    is only one adapter pair for this tool), and the sole place `policy_number`'s format is enforced
    before a lookup is attempted.
    """

    policy_number: str = Field(pattern=POLICY_NUMBER_PATTERN)


def _load_policyholders() -> dict[str, Policyholder]:
    payload = json.loads(POLICYHOLDERS_PATH.read_text())
    return {
        record["policy_number"]: Policyholder.model_validate(record)
        for record in payload["policyholders"]
    }


def get_policyholder_elections(policy_number: str) -> Policyholder:
    """Returns the policyholder record for `policy_number`, keyed exactly as
    `DIALOGUE-POLICIES.md` §2 requires for the election-fact/optional-benefit branch of
    `CoverageQuestion` (`elected_benefits`-shaped fields -- `accident_benefits_elections`, `dcpd`,
    `loss_or_damage_coverage`, `rental_endorsement` -- all live on `Policyholder` already).

    Returns the full `Policyholder` record rather than a narrower elections-only view: Stage 1's
    `Policyholder` model already *is* exactly the shape `data/synthetic/policyholders/policyholders.json`
    models, and DIALOGUE-POLICIES.md's dialogue policy only ever reads the election subset of it -- a
    second, narrower schema would just be the same fields redefined a second time, which
    `ADR-012`'s "schemas defined separately from handlers... never redefined twice" reasoning argues
    against, not for.

    Raises:
        InvalidPolicyNumberError: `policy_number` doesn't match the `PY####` format.
        PolicyNotFoundError: `policy_number` is well-formed but matches no record.
    """
    try:
        args = GetPolicyholderElectionsArgs(policy_number=policy_number)
    except ValidationError as exc:
        raise InvalidPolicyNumberError(
            f"policy_number={policy_number!r} does not match the PY#### format"
        ) from exc

    policyholders = _load_policyholders()
    try:
        return policyholders[args.policy_number]
    except KeyError:
        raise PolicyNotFoundError(
            f"no policyholder found for policy_number={args.policy_number!r}"
        ) from None


def main() -> None:
    """MCP-server adapter: registers `get_policyholder_elections` as a tool and serves it over stdio."""
    from mcp.server.mcpserver import MCPServer  # local import -- see module docstring

    server = MCPServer("fnol-policy-server", instructions=__doc__)
    server.add_tool(get_policyholder_elections)
    server.run()


if __name__ == "__main__":
    main()
