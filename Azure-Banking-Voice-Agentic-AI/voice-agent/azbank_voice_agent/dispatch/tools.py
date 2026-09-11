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
import dataclasses
import json
import logging

from ..call_records import (
    REASONS,
    CallRecordStore,
    CallRecordStoreUnavailable,
    EscalationRecord,
)
from ..core_banking import (
    ALREADY_BLOCKED,
    CoreBankingClient,
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

#: What the caller hears when a **transfer** could not be confirmed. Deliberately not UNAVAILABLE:
#: for a read, "I can't check that" is the whole truth, but a transfer that raised unavailable may
#: already have committed at the service -- which is precisely why client.py never retries it. "I
#: can't reach the banking system" asserts that nothing happened, and a caller who believes that
#: retries, which is the double-spend the no-retry rule exists to prevent (issue #25 user story 6,
#: #27; /code-review 2026-09-09).
#:
#: Said even when the request never left this process (an open circuit, a connection refused),
#: where nothing did happen: the dispatcher cannot tell those apart from a timeout, and of the two
#: possible wrong answers this is the safe one. Being told to check a balance that has not changed
#: costs a caller a moment; being told nothing happened when something did costs them the money.
TRANSFER_UNCONFIRMED = (
    "I couldn't confirm whether that transfer went through, so please check the balance before "
    "trying it again."
)

#: What the caller hears when a tool call could not be run at all -- a bad amount, an account name
#: that names nothing, a tool this agent does not have, an arguments payload that is not JSON.
#: Composed here like every other caller-facing sentence: the service's own wording for the amount
#: case ("core banking rejected the request with 422") is diagnostic text for a log, and it was
#: reaching the caller verbatim before /code-review caught it (2026-09-08).
MALFORMED = "I can't do that with those details -- could you say that again?"

#: What the caller hears when they are escalated. **Honest about there being nobody to transfer them
#: to** (docs/PLAN.md decision 17): a real transfer needs a real second number and a real person,
#: neither of which exists in this prototype. Saying "putting you through" and then hanging up would
#: be a lie the caller finds out about a second later.
#:
#: Composed here, like every other outcome sentence. The model is told to apologise too, in the
#: tool's own description -- and the two are not redundant: the model speaks before the tool runs,
#: this is what the tool call comes back with, and a call that ends must not depend on the model
#: having chosen good words on the turn before.
ESCALATED = (
    "I'm sorry I couldn't help with that. There's nobody I can put you through to on this line, so "
    "I'll end the call here -- I've made a note that you called and why."
)

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
    {
        "type": "function",
        "name": "list_transactions",
        # The description carries the reading instructions, because the result is data and the
        # sentence is the model's -- the same division `list_accounts` already uses. What it must
        # not do is invite the model to ask for more: the bound is the service's, there is no
        # argument for it, and a description hinting otherwise would have the model apologise for
        # a limit it cannot lift.
        #
        # The empty case is named explicitly. A caller who has never used an account must be told
        # so plainly rather than left to read silence as a failure, and "say there is nothing yet"
        # is phrasing guidance, which lives on this side of the seam.
        "description": (
            "List recent activity on one of the caller's accounts, newest first. The list is "
            "already limited to the few most recent items -- read them out, and don't offer to "
            "fetch more. A negative amount is money that left the account and a positive amount "
            "is money that arrived, so say which it was and which account it was with. If the "
            "list is empty, say plainly that nothing has happened on that account yet."
        ),
        "parameters": {
            "type": "object",
            "properties": {"account": _ACCOUNT},
            "required": ["account"],
        },
    },
    {
        "type": "function",
        "name": "block_card",
        # **No idempotency-key parameter.** The key is generated by the relay and scoped to the
        # call; a model that could choose its own key could defeat the mechanism by choosing a new
        # one each time, which is the whole thing the key exists to prevent. A tool with no
        # arguments also cannot be called with a malformed one.
        #
        # The confirmation instruction is repeated from the Cards agent's own instructions
        # deliberately: the model sees the tool list on every turn and the instructions once per
        # session.update, and this is the one operation in the product that cannot be undone.
        "description": (
            "Block the caller's card because it is lost or stolen. Confirm with the caller "
            "first, telling them it cannot be undone on this line. It is safe to call this more "
            "than once on a call: a repeat will not block anything twice, and will tell you if "
            "the card was already blocked."
        ),
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "type": "function",
        "name": "escalate_to_human",
        # **The reason is an enum, not a string.** The record exists so that whoever picks this up
        # can query it, and a reason the model phrased its own way is not queryable. The schema is
        # a request rather than a guarantee -- the model can send anything -- which is why the
        # handler checks the value again rather than trusting this.
        #
        # The description says the call ends, because the model composes what the caller hears
        # immediately before it does. A model that thought it was queuing a transfer would say
        # something that is about to become untrue.
        "description": (
            "Hand the caller to a person. Use this when you cannot help them, when they ask for a "
            "person, or when they cannot get through the PIN check. Apologise and tell them the "
            "call is ending -- there is nobody to transfer them to on this line, so this ends the "
            "call and records that they called and why."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "enum": list(REASONS),
                    "description": "Why the caller is being escalated.",
                },
            },
            "required": ["reason"],
        },
    },
]


def _account_name(args, key):
    """The account the model asked about, as a name -- or a malformed request.

    `arguments_json` is model output, and the schema in TOOLS is a request rather than a guarantee:
    this field arrives as a number, an object, `null` or an empty string as readily as a name. None
    of those can name an account, and each one used to fail somewhere further in (probe,
    2026-09-09) -- an object raised TypeError inside the fake and ended the call, `null` had the
    real service asked about an account literally called "None" and the caller told so by name, and
    an empty name addressed no resource at all, drawing a redirect whose empty body then became a
    spoken JSON parser error.

    Refused here, once, rather than in each client: it is a fact about the model's arguments, not a
    rule of core banking, and the two clients had already drifted on it. The amount's own rule
    lives at the dollars-to-cents boundary instead (`client.to_cents`), because that one *is* about
    money and both clients pass through it.
    """
    value = args[key]
    if not isinstance(value, str) or not value.strip():
        raise CoreBankingRequestError(f"{key} must be a non-empty account name, got {value!r}")
    return value


@dataclasses.dataclass(frozen=True)
class CallScope:
    """Everything a tool may need that belongs to the call rather than to the tool call.

    Handed to every handler, including the handlers that use none of it. **A dispatcher that
    special-cased one tool's signature would be a dispatcher with a branch in the one place B1
    depends on there being none**, and the alternative -- five positional arguments on six handlers,
    four of them unused -- is not smaller, only longer.

    `core_banking` is the system of record. `call_records` is the store this phase added, which holds
    facts about calls rather than about money. `idempotency_key` is generated once per call by the
    relay. `correlation_id` is ACS's own id for the call, handed in rather than fetched.

    Frozen, because nothing a tool does may change what the call is.
    """

    # **The protocols, not `object`.** Both fields carried `object` until 2026-09-11, in a package
    # that defines `CoreBankingClient` and `CallRecordStore` for exactly this -- so the one object
    # every tool reaches through told a reader nothing about what it holds, and mypy (non-strict
    # here) had nothing to check the tool bodies against (/code-review, 2026-09-11). Structural
    # Protocols, so the fakes satisfy them by shape and nothing needs to inherit anything.
    core_banking: CoreBankingClient
    call_records: CallRecordStore | None = None
    idempotency_key: str | None = None
    correlation_id: str | None = None


async def _get_balance(scope, args):
    return await scope.core_banking.get_balance(_account_name(args, "account"))


async def _transfer(scope, args):
    from_account = _account_name(args, "from_account")
    to_account = _account_name(args, "to_account")
    amount = args["amount"]
    result = await scope.core_banking.transfer(from_account, to_account, amount)
    if result.outcome == "declined":
        return f"I can't do that -- you have ${result.available:.2f} available in {from_account}."
    # `result.moved`, not `amount`: dollars become whole cents on the way to the service, and at
    # the half cent the requested figure and the moved one differ ($2.675 asked for moves $2.68,
    # and "%.2f" of the request says $2.67 -- probe, 2026-09-09). Same rule as the balance beside
    # it: the caller hears what the system did.
    return (
        f"Done -- transferred ${result.moved:.2f} from {from_account} to {to_account}. "
        f"New {from_account} balance: ${result.from_balance:.2f}."
    )


async def _list_accounts(scope, args):
    return await scope.core_banking.list_accounts()


async def _list_transactions(scope, args):
    """The account's history as data, not as a sentence.

    Returned in the same spirit as `_list_accounts`: dictionaries of figures and tokens that the
    model reads out, rather than prose composed here. The two tools that return *outcomes* --
    `transfer` and every error branch below -- get composed sentences, because there the wording
    carries a decision the model must not restate its own way.

    `dataclasses.asdict` rather than a hand-written dict: a field added to `Transaction` should
    reach the model without a second place to remember to update it.
    """
    transactions = await scope.core_banking.list_transactions(_account_name(args, "account"))
    return [dataclasses.asdict(transaction) for transaction in transactions]


async def _block_card(scope, args):
    """Stop the card, and say which of the two things happened.

    **The two outcomes get different sentences**, because "I have stopped it" and "it was already
    stopped" are different facts and a caller who asked twice deserves the second. Collapsing them
    into one reassuring sentence would be the same species of defect as answering an unavailable
    read with a remembered balance: comfortable, and not what happened.

    A composed sentence rather than data, unlike the two list tools -- this is an outcome, and the
    wording carries a decision the model must not restate its own way. The irreversibility is said
    here as well as before the tool is called, because the sentence the caller hears at the end of
    the operation is the one they will remember it by.
    """
    outcome = await scope.core_banking.block_card(scope.idempotency_key)
    if outcome == ALREADY_BLOCKED:
        return "That card was already blocked, so there was nothing more to stop."
    return "Done -- that card is blocked now, and it can't be unblocked on this line."


async def _escalate_to_human(scope, args):
    """Write the escalation record, and say the sentence that ends the call.

    **This handler does not end the call itself.** It returns a normal result, the relay sends it as
    a function_call_output and asks for a response, and only then does the relay raise. That ordering
    is the whole reason the caller hears an apology rather than a dropped line.

    **A failed record still escalates** (docs/phase5/exit-criteria.md criterion 9). Reaching a person
    matters more than recording that somebody asked to, so a store that raises is logged loudly and
    the caller hears the same sentence. This is the one place in the phase where the store failing is
    not fail-closed, and it is deliberate rather than an oversight -- the alternative is a caller who
    is refused a human because a table was unreachable.

    **It never touches the core-banking client.** That is what keeps B1 untouched by a tool that is
    reachable while anonymous: escalation is not a banking operation and reaches nothing that holds
    money. `core_banking` is in the signature because every handler has the same one.
    """
    reason = args.get("reason")
    if reason not in REASONS:
        # The schema's enum is a request, not a guarantee -- the model can send anything, including
        # a reason it invented that reads perfectly well. Checked here so the fixed set is enforced
        # where the record is made rather than where it is declared.
        raise CoreBankingRequestError(f"escalation reason must be one of {REASONS}, got {reason!r}")
    try:
        await scope.call_records.record_escalation(
            EscalationRecord.now(scope.correlation_id, reason)
        )
    except CallRecordStoreUnavailable as e:
        # Loudly: this is the one durable trace that a caller asked for a person, and losing it is
        # worth an error line even though it is not worth refusing them.
        log.error("escalation record NOT written, the call is ending anyway: %r", e)
    return ESCALATED


#: Name -> handler. Every handler takes `(scope, args)` -- see CallScope for why uniform beats
#: clever here.
_DISPATCH = {
    "get_balance": _get_balance,
    "transfer": _transfer,
    "list_accounts": _list_accounts,
    "list_transactions": _list_transactions,
    "block_card": _block_card,
    "escalate_to_human": _escalate_to_human,
}


async def dispatch_tool_call(
    name, arguments_json, agent=gate.BANKING_AGENT, auth_state=gate.ANONYMOUS, *, scope,
):
    """Run one tool call, returning the JSON string for a function_call_output. Never raises --
    an unknown tool name, a missing or wrongly-typed argument, an unknown account, a malformed
    request, or an unreachable backend all come back as {"error": "..."} so the model can say
    something sensible instead of the call going silent. "Never raises" is load-bearing rather than
    tidy: run_call re-raises whatever escapes here, which drops the call.

    Every call passes the gate first (B1). A refusal comes back in the same {"error": ...} shape,
    so the caller hears a spoken refusal rather than silence.

    The agent/auth_state defaults are the *least* privileged values on purpose: a caller that
    forgets to pass an auth_state gets ANONYMOUS, so forgetting fails closed rather than open.
    `scope` is keyword-only and has **no default** for the same reason -- forgetting it is a
    TypeError at the call site, not a None that fails somewhere later. What is inside it may be
    absent (see CallScope), because a missing idempotency key matters to one tool and a missing
    client matters to four; failing at the tool that needs the thing beats failing at all of them.
    """
    if not gate.is_allowed(agent, auth_state, name):
        # Logged at warning: a refusal is either an attack or a bug, and both are worth seeing.
        # The tool name is safe to log; the arguments are not logged as a blob, because Phase 4
        # puts PIN-adjacent data on this path and a blob would carry it (B2).
        #
        # Not a claim that an account name never reaches a log: `client._send` logs the request
        # path, and for a balance read that path contains the account name. That is deliberate --
        # it is the one field that makes a failed request diagnosable -- and an account name is not
        # B2 data, which is the PIN and only the PIN. Said explicitly because the two modules
        # otherwise read as asserting opposite rules about the same value (/code-review,
        # 2026-09-09, standards axis).
        log.warning("gate refused tool %r for (agent=%s, auth_state=%s)", name, agent, auth_state)
        return json.dumps({"error": gate.REFUSAL})
    try:
        args = json.loads(arguments_json) if arguments_json else {}
        result = await _DISPATCH[name](scope, args)
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
        #
        # A write and a read get different sentences because they are different facts: an
        # unavailable read simply did not happen, while an unavailable transfer has an outcome
        # nobody knows. See TRANSFER_UNCONFIRMED.
        log.warning("core banking unavailable for tool %r", name)
        unknown_outcome = name == "transfer"
        return json.dumps({"error": TRANSFER_UNCONFIRMED if unknown_outcome else UNAVAILABLE})
    except (KeyError, TypeError, ValueError) as e:
        # Everything else that can go wrong with a tool call: an unknown tool name, a missing
        # argument, an arguments payload that is not JSON. The diagnosis goes to the log and the
        # caller hears a composed sentence -- `str(e)` used to be spoken, which put the JSON
        # parser's own message ("Expecting value: line 1 column 1 (char 0)") and internal field
        # names in front of a caller (probe, 2026-09-09). Same defect as /code-review's finding 3,
        # reached through the generic branch instead of the 422 one.
        #
        # TypeError is caught as well as raised-from-nowhere insurance: this function's docstring
        # promises it never raises, and a raise here does not merely spoil one answer -- run_call
        # re-raises it and the call drops mid-sentence.
        log.warning("tool %r could not be run: %s: %s", name, type(e).__name__, e)
        return json.dumps({"error": MALFORMED})
    return json.dumps({"result": result})
