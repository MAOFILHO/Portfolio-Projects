# Azure-Banking-Voice-Agentic-AI

A prototype phone-banking IVR: a caller dials a real Canadian number and speaks to a voice agent
backed by a realtime speech-to-speech model. This file is the glossary — what the words mean here,
not how anything is built. Scope, architecture, and the phase plan live in `docs/PLAN.md`; the
operating rules live in `CLAUDE.md`.

## Language

### The call

**Call**:
One inbound phone conversation, from answer to hangup. The unit that cost caps and latency are
measured against.
_Avoid_: session (means the realtime session, below), conversation

**Caller**:
The person on the phone. Never assumed to be who they claim to be until authenticated.
_Avoid_: user, customer, client

**Turn**:
One caller utterance and the agent's spoken reply to it. The unit `B5` latency is measured in — a
latency figure always states how many turns back it.
_Avoid_: exchange, round trip

**Realtime session**:
The single model connection held open for the duration of a call. One per call — an agent change
reconfigures this session rather than opening a second one.
_Avoid_: connection, socket

### The agent

**Agent**:
One named conversational role, defined by its own instructions and the tools it is shown. Two exist:
triage and banking.
_Avoid_: assistant, bot, persona

**Triage agent**:
The agent a call opens on. Greets the caller, works out what they need, and hands off. Has no
banking tools of its own.

**Banking agent**:
The agent that handles balance and money requests, reached by handoff from triage.
_Avoid_: specialist, accounts agent

**Handoff**:
Moving a call from one agent to another. Routing, not a banking action — a handoff is never gated.
_Avoid_: transfer (means moving money, below), escalation (means routing to a human)

**Tool call**:
The model's request to run one named function. An attempt, not an outcome — whether it succeeds is
the gate's decision alone.
_Avoid_: function call, action, intent

### Authorization

**Auth gate**:
The single control that decides whether a tool call is permitted, given the calling agent and the
call's auth state. The only thing that decides whether a tool call succeeds; everything else that
narrows what the model might attempt is defence in depth, not the control.
_Avoid_: guard, permission check, authorization layer

**Auth state**:
Whether the caller on this call has been authenticated. Either anonymous or authenticated; nothing
in between.
_Avoid_: logged in, verified, session state

**Refusal**:
What the caller hears when the gate declines a tool call. Deliberately uninformative about why — an
explanation of what *would* have been permitted is a probing oracle.
_Avoid_: denial, rejection (means a declined transfer, below), error

### Banking

**Core banking**:
The system of record for accounts and balances. This project never talks to a real one.

**mock-core-banking**:
The stand-in for core banking that this project builds and runs: its own service, reached over a
real network hop, holding the account state a real core-banking system would hold. "Mock" describes
what it stands in for, not a test double — the voice agent talks to it the same way in tests and in
production.
_Avoid_: fake backend, stub service, accounts service

**Account**:
One of the caller's holdings of money, named (chequing, savings) and carrying a balance. Named, not
numbered — this prototype has no account numbers.

**Balance**:
The money currently in one account.

**Transfer**:
Moving money between two of the caller's own accounts. Never between callers, never outbound.
_Avoid_: payment, transaction, handoff (means moving a call, above)

### Outcomes

The four ways a tool call can fail to give the caller what they asked for. They are genuinely
different things, get genuinely different spoken responses, and are never collapsed into one:

**Unknown account**:
The named account does not exist. Always raises — never resolves to a default, a zero, or any other
account's balance. The single behaviour this project's hard exclusions name by example.
_Avoid_: not found, missing account

**Declined**:
The account exists and the request is understood, but business rules refuse it — an overdrawing
transfer, for instance. A normal outcome of a working system, not a failure of one. The caller is
told the real reason and the real number behind it.
_Avoid_: rejected, failed, error

**Unavailable**:
mock-core-banking could not be reached, or did not answer in time. The caller is told the truth —
that the information can't be reached right now — and never given a remembered, cached, or guessed
figure in its place.
_Avoid_: down, offline, error

**Malformed**:
The request itself was not well-formed, so the service never got as far as an opinion about it — an
amount of zero or less, or one that rounds to less than a cent. The caller of the API has a bug;
nobody has been refused anything, which is what separates this from **declined**. The service
answers `422`, the client raises `CoreBankingRequestError`, and the caller hears a request to say
it again. Validated at the request body, so it outranks **unknown account**: a bad amount is
malformed whether or not the accounts exist.
_Avoid_: invalid, bad request, declined
