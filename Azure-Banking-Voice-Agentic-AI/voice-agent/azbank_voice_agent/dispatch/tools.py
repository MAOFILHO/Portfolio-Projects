"""Tool declarations and the dispatcher that runs them.

Moved out of the Phase 1 relay module unchanged (Phase 2.1 restructure, issue #17).

B1 note: there is no gate here yet. `dispatch/gate.py` -- deny-all-by-default, every tool
refused unless explicitly allowlisted for the current (agent, auth_state) pair -- is issue
#19's deliverable and lands beside this module, in front of `dispatch_tool_call`. Until then
every declared tool executes unconditionally, which is only survivable because `accounts` is
an in-memory dict with nothing real behind it (docs/PLAN.md Phase 1, "Out of scope").
"""
import json

from .. import accounts

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


def dispatch_tool_call(name, arguments_json):
    """Run one tool call, returning the JSON string for a function_call_output. Never raises --
    an unknown tool name, a missing argument, or an accounts error (bad account, non-positive
    amount) all come back as {"error": "..."} so the model can say something sensible instead of
    the call going silent."""
    try:
        args = json.loads(arguments_json) if arguments_json else {}
        result = _DISPATCH[name](args)
    except (KeyError, ValueError) as e:
        return json.dumps({"error": str(e) or f"unknown tool: {name}"})
    return json.dumps({"result": result})
