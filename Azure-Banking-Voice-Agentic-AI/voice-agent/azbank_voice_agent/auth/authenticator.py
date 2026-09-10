"""The keypad, as a per-call state machine that knows nothing about calls, sockets or models.

**Constructed per call**, inside the relay where the call's auth state already lives, taking the
injected core-banking client. No module-level state of any kind: two calls in the same process hold
two of these, and neither can see the other's progress or spend the other's attempts.

**Buffer transitions are pure and synchronous. The only await is the submission.** Feeding a key
either accumulates a digit, clears the buffer, is ignored, or completes an entry -- and only the
last of those touches I/O. That split is what makes the keypad's rules testable with no client, no
socket and no model, and it keeps "pure state machine" honest for the part that is one.

**Agent-independent.** It sees digits, not agents, so a caller may key the PIN whether the call is
still on triage or already handed off. The moment a caller may authenticate is not allowed to
depend on routing they cannot see.

**How many digits have arrived is private to this object.** The gate's key space is two agents by
two states, and it stays that way because the digit count never leaves here -- the auth state is
binary, and partial progress is not a third value of it.

**No timer of any kind.** No inter-digit timeout, deliberately cut at Phase 4 kickoff as the only
piece of the phase that would put a timer on the audio event loop. A partial entry stays partial
for as long as the caller leaves it, and the call's own B4 caps are what bound that.

**Verification goes through the core-banking client the relay already has**, which is why an
unreachable service fails authentication closed for free: the timeout, the single-attempt path and
the circuit breaker are inherited rather than reimplemented here where they could disagree.
"""
import logging

from ..core_banking import CoreBankingUnavailable
from . import outcomes

log = logging.getLogger("auth")

#: Four digits, submitted automatically on the fourth. A fixed length is what makes a terminator
#: unnecessary, which is why POUND below does nothing.
PIN_LENGTH = 4

#: Three rejected credentials end the call. An attempt is a *completed* check that came back
#: rejected (CONTEXT.md), so a cleared entry and an unanswered check both cost nothing.
MAX_ATTEMPTS = 3

#: Star clears. A caller who mis-keys a digit needs a way out that does not cost an attempt.
CLEAR = "*"

#: Pound is ignored rather than treated as a terminator: a fixed-length entry has no use for one,
#: and a caller who keys it mid-entry must not lose the digits already keyed.
POUND = "#"

#: What the caller hears, composed here and never in the service. The same inversion rule Phase 3
#: established for mock-core-banking, restated for the second module that owns caller-facing prose:
#: the system of record returns outcome tokens, and every sentence a caller hears is written on
#: this side.
#:
#: **No sentence carries a digit or an attempt count.** Same reasoning as the gate's refusal: an
#: explanation of how many tries are left, or of which part was wrong, is a probing oracle for
#: whoever found the phone. The caller is told it was wrong and nothing more.
SENTENCES = {
    outcomes.AUTHENTICATED: "Thank you, you're verified.",
    outcomes.REJECTED: "That PIN wasn't right. Please key it again.",
    outcomes.EXHAUSTED: (
        "That PIN wasn't right. For your security I'm ending the call here."
    ),
    outcomes.UNAVAILABLE: (
        "I can't check your PIN just now. Please key it again in a moment."
    ),
}


def sentence_for(outcome):
    """The sentence for an outcome, or None when there is nothing to say.

    None for the three outcomes that mean the caller is still keying. Saying something there would
    talk over a caller partway through an entry, which is the one thing a prompt for a PIN cannot
    afford to do.
    """
    return SENTENCES.get(outcome)


class Authenticator:
    """One call's keypad and its attempts. Not shared, not reused, not reset."""

    def __init__(self, core_banking):
        self._core_banking = core_banking
        self._buffer = ""
        self._attempts = 0
        self._authenticated = False
        # Set once the third rejection lands. Kept separate from `_authenticated` because they are
        # different facts: one means the caller got in, the other means they will not.
        self._settled = False

    @property
    def is_authenticated(self):
        """Whether this call has passed a PIN check. The only thing the relay reads off here.

        One-way within a call: nothing sets this back to False, and there is no path that returns
        the call to anonymous.
        """
        return self._authenticated

    def end_call(self):
        """Zero the buffer, whatever the outcome. Called from the relay's cleanup.

        The third of the three points a buffer is zeroed at, after submit and clear -- so no digit
        outlives the moment it was needed. Safe to call more than once and safe to call on a call
        that never keyed anything, because the relay's cleanup runs on every path out.
        """
        self._buffer = ""
        self._settled = True

    async def key(self, key):
        """Feed one keyed digit. Returns one of `outcomes`.

        The only entry point. Everything before the submission is the pure transition below; the
        submission is the one await.
        """
        outcome, submission = self._press(key)
        if submission is None:
            return outcome
        return await self._submit(submission)

    # --- the pure part ------------------------------------------------------------------------

    def _press(self, key):
        """The whole keypad protocol, and the only thing that touches the buffer.

        Pure and synchronous: no I/O, no clock, no randomness. Returns `(outcome, submission)`,
        where `submission` is the completed entry when the fourth digit has just arrived and None
        otherwise -- in which case `outcome` is already the final answer.
        """
        if self._authenticated or self._settled:
            # One-way. A digit after the question is settled does nothing at all: it must not open
            # a second check, and it must not be able to undo the first.
            return outcomes.IGNORED, None
        if key == CLEAR:
            self._buffer = ""
            return outcomes.CLEARED, None
        if key == POUND or not _is_digit(key):
            return outcomes.IGNORED, None
        self._buffer += key
        if len(self._buffer) < PIN_LENGTH:
            return outcomes.ACCUMULATING, None
        submission, self._buffer = self._buffer, ""
        return None, submission

    # --- the one await ------------------------------------------------------------------------

    async def _submit(self, submission):
        """Ask the system of record, and turn its answer into an outcome.

        Fails closed by construction: the only branch that sets `_authenticated` is the one where
        the client returned an accepted verdict, and the client's own contract is that no failure
        path can produce one.
        """
        try:
            accepted = await self._core_banking.verify_pin(submission)
        except CoreBankingUnavailable:
            # No verdict, so none is inferred and none is counted. A caller must not have their
            # three tries spent by somebody else's outage -- CONTEXT.md's Attempt entry says a
            # check the bank never answered is not an attempt.
            log.warning("PIN check could not be completed; no attempt consumed")
            return outcomes.UNAVAILABLE
        if accepted:
            self._authenticated = True
            log.info("caller authenticated")
            return outcomes.AUTHENTICATED
        self._attempts += 1
        # The attempt number and nothing else. A failure here is either an attack or a bug, and
        # both are worth seeing -- the same reasoning the gate already applies to refusals. The
        # digits are not in the message and not in the arguments (B2).
        log.warning("PIN check rejected (attempt %d of %d)", self._attempts, MAX_ATTEMPTS)
        if self._attempts >= MAX_ATTEMPTS:
            self._settled = True
            return outcomes.EXHAUSTED
        return outcomes.REJECTED


def _is_digit(key):
    """One ASCII digit, and nothing else.

    `str.isdigit` is not this test: it is True for superscripts and other Unicode digit forms,
    none of which a keypad produces and none of which the system of record would accept.
    """
    return isinstance(key, str) and len(key) == 1 and key in "0123456789"
