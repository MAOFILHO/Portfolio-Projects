"""Tool declarations and the dispatcher that runs them.

Moved out of the Phase 1 relay module unchanged (Phase 2.1 restructure, issue #17).

B1: `dispatch_tool_call` is the single choke point -- the only path from "the model asked for a
tool" to "the tool ran" -- and the first thing it does is consult the gate. There is deliberately
no second path: nothing else in this package calls into `_DISPATCH`, and tests/test_gate.py proves
that tool by tool, driven off the declared tool list rather than a hand-maintained one.
"""
import json
import logging

from .. import accounts
from . import gate

log = logging.getLogger("dispatch")

_ACCOUNT_ENUM = {"type": "string", "enum": list(accounts.ACCOUNTS)}

TOOLS = [
    {
        "type": "function",
        "name": "get_balance",
        "description": "Get the current balance of one of the caller's accounts.",
        "parameters": {
            "type": "object",
            "properties": {"account": _ACCOUNT_ENUM},
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
                "from_account": _ACCOUNT_ENUM,
                "to_account": _ACCOUNT_ENUM,
                "amount": {"type": "number"},
            },
            "required": ["from_account", "to_account", "amount"],
        },
    },
    {
        "type": "function",
        "name": "list_accounts",
        "description": "List the caller's accounts.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
]

_DISPATCH = {
    "get_balance": lambda args: accounts.get_balance(args["account"]),
    "transfer": lambda args: accounts.transfer(
        args["from_account"], args["to_account"], args["amount"]
    ),
    "list_accounts": lambda args: accounts.list_accounts(),
}


def dispatch_tool_call(name, arguments_json, agent=gate.BANKING_AGENT, auth_state=gate.ANONYMOUS):
    """Run one tool call, returning the JSON string for a function_call_output. Never raises --
    an unknown tool name, a missing argument, or an accounts error (bad account, non-positive
    amount) all come back as {"error": "..."} so the model can say something sensible instead of
    the call going silent.

    Every call passes the gate first (B1). A refusal comes back in the same {"error": ...} shape,
    so the caller hears a spoken refusal rather than silence.

    The defaults are the *least* privileged values on purpose: a caller that forgets to pass an
    auth_state gets ANONYMOUS, so forgetting fails closed rather than open.
    """
    if not gate.is_allowed(agent, auth_state, name):
        # Logged at warning: a refusal is either an attack or a bug, and both are worth seeing.
        # The tool name is safe to log; arguments are not logged here -- they can carry account
        # identifiers, and Phase 4 puts PIN-adjacent data on this path (B2).
        log.warning("gate refused tool %r for (agent=%s, auth_state=%s)", name, agent, auth_state)
        return json.dumps({"error": gate.REFUSAL})
    try:
        args = json.loads(arguments_json) if arguments_json else {}
        result = _DISPATCH[name](args)
    except (KeyError, ValueError) as e:
        return json.dumps({"error": str(e) or f"unknown tool: {name}"})
    return json.dumps({"result": result})
