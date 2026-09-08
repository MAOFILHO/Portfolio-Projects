"""Tool declarations and the dispatcher that runs them.

Moved out of the Phase 1 relay module unchanged (Phase 2.1 restructure, issue #17). Phase 3 (issue
#28) repointed it from an in-memory dict to a real network call against mock-core-banking.

B1: `dispatch_tool_call` is the single choke point -- the only path from "the model asked for a
tool" to "the tool ran" -- and the first thing it does is consult the gate. There is deliberately
no second path: nothing else in this package calls into `_DISPATCH`, and tests/test_gate.py proves
that tool by tool, driven off the declared tool list rather than a hand-maintained one.

**Async since Phase 3.** The dispatcher does real network I/O now, and the relay that calls it is
asyncio: a synchronous call here would block the event loop for the client's whole timeout budget,
stalling audio in *both* directions and killing barge-in while it waited. The gate itself stays a
pure synchronous function -- it is simply awaited around, and B1's premise is untouched.

**All caller-facing phrasing lives here**, never in the service. mock-core-banking returns data and
outcome codes; the sentences the caller hears are composed in this module. That corrects an
inversion the Phase 1 module carried: `accounts.transfer()` returned a ready-made apology sentence
from what was, in effect, the system of record.
"""
import json
import logging

from ..core_banking import (
    CoreBankingRequestError,
    CoreBankingUnavailable,
    UnknownAccountError,
)
from . import gate

log = logging.getLogger("dispatch")

#: What the caller hears when mock-core-banking cannot be reached. Honest about the situation and
#: carrying no figure of any kind -- the failure mode this phase introduces must never be answered
#: with a remembered, cached, or defaulted balance (CLAUDE.md's silent-fallback exclusion).
UNAVAILABLE = "I can't reach the banking system right now, so I can't check that."

#: What the caller hears when the request itself was malformed -- a bad amount, a field the service
#: rejected. Composed here like every other caller-facing sentence: the service's own wording for
#: this ("core banking rejected the request with 422") is diagnostic text for a log, and it was
#: reaching the caller verbatim before /code-review caught it (2026-09-08).
MALFORMED = "I can't do that with those details -- could you say that again?"

# No account enum. Phase 1 built one from the in-memory dict at import time, which made the *tool
# schema* the authority on which accounts exist -- and meant the model refused an unknown account
# from its own reasoning rather than from anything authoritative (Phase 1's exit row 6 passed
# exactly that way, which is a weaker guarantee than it looked). mock-core-banking is the system of
# record now; `list_accounts` is how you find out what it holds, and asking for something that
# isn't there is answered by the service, not guessed at from a schema.
# The description names no accounts either. Dropping the enum but leaving "e.g. chequing or
# savings" in the description would put the same stale answer back in front of the model in prose
# form (/code-review, 2026-09-08) -- list_accounts is how the model finds out what exists.
_ACCOUNT = {
    "type": "string",
    "description": "The account name. Call list_accounts first if you don't already know it.",
}

TOOLS = [
    {
        "type": "function",
        "name": "get_balance",
        "description": "Get the current balance of one of the caller's accounts.",
        "parameters": {
            "type": "object",
            "properties": {"account": _ACCOUNT},
            "required": ["account"],
        },
    },
    {
        "type": "function",
        "name": "transfer",
        "description": "Transfer money between the caller's accounts.",
        "parameters": {
            "type": "object",
            "properties": {
                "from_account": _ACCOUNT,
                "to_account": _ACCOUNT,
                "amount": {"type": "number", "description": "Amount in dollars."},
            },
            "required": ["from_account", "to_account", "amount"],
        },
    },
    {
        "type": "function",
        "name": "list_accounts",
        "description": "List the caller's accounts and their balances.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
]


async def _get_balance(core_banking, args):
    return await core_banking.get_balance(args["account"])


async def _transfer(core_banking, args):
    from_account, to_account = args["from_account"], args["to_account"]
    amount = args["amount"]
    result = await core_banking.transfer(from_account, to_account, amount)
    if result.outcome == "declined":
        return f"I can't do that -- you have ${result.available:.2f} available in {from_account}."
    return (
        f"Done -- transferred ${amount:.2f} from {from_account} to {to_account}. "
        f"New {from_account} balance: ${result.from_balance:.2f}."
    )


async def _list_accounts(core_banking, args):
    return await core_banking.list_accounts()


_DISPATCH = {
    "get_balance": _get_balance,
    "transfer": _transfer,
    "list_accounts": _list_accounts,
}


async def dispatch_tool_call(
    name, arguments_json, agent=gate.BANKING_AGENT, auth_state=gate.ANONYMOUS, *, core_banking
):
    """Run one tool call, returning the JSON string for a function_call_output. Never raises --
    an unknown tool name, a missing argument, an unknown account, a malformed request, or an
    unreachable backend all come back as {"error": "..."} so the model can say something sensible
    instead of the call going silent.

    Every call passes the gate first (B1). A refusal comes back in the same {"error": ...} shape,
    so the caller hears a spoken refusal rather than silence.

    The agent/auth_state defaults are the *least* privileged values on purpose: a caller that
    forgets to pass an auth_state gets ANONYMOUS, so forgetting fails closed rather than open.
    `core_banking` is keyword-only and has **no default** for the same reason -- forgetting it is a
    TypeError at the call site, not a None that fails somewhere later.
    """
    if not gate.is_allowed(agent, auth_state, name):
        # Logged at warning: a refusal is either an attack or a bug, and both are worth seeing.
        # The tool name is safe to log; arguments are not logged here -- they can carry account
        # identifiers, and Phase 4 puts PIN-adjacent data on this path (B2).
        log.warning("gate refused tool %r for (agent=%s, auth_state=%s)", name, agent, auth_state)
        return json.dumps({"error": gate.REFUSAL})
    try:
        args = json.loads(arguments_json) if arguments_json else {}
        result = await _DISPATCH[name](core_banking, args)
    except UnknownAccountError as e:
        # Caught before KeyError below: UnknownAccountError is a LookupError, and so is KeyError.
        # Order matters here -- an unknown account is a real answer to give the caller, not the
        # same thing as a malformed tool call.
        #
        # The name comes from the service, which is the only thing that knows which account was
        # unknown, and it can be absent. Absent means a sentence that names no account -- never a
        # fallback to whatever else happens to be on the exception, which is how the first version
        # of this ended up speaking the service's internal URL to a caller (/code-review,
        # 2026-09-08).
        account = e.args[0] if e.args else None
        return json.dumps({"error": (
            f"There's no {account} account on this profile." if account
            else "I can't find that account on this profile."
        )})
    except CoreBankingRequestError as e:
        # The exception's own message is diagnostic and internal -- log it, never speak it.
        log.warning("core banking rejected tool %r as malformed: %s", name, e)
        return json.dumps({"error": MALFORMED})
    except CoreBankingUnavailable:
        # Deliberately no figure of any kind in this branch. Never a cached balance, never a
        # default, never a "last known" number.
        log.warning("core banking unavailable for tool %r", name)
        return json.dumps({"error": UNAVAILABLE})
    except (KeyError, ValueError) as e:
        return json.dumps({"error": str(e) or f"unknown tool: {name}"})
    return json.dumps({"result": result})
