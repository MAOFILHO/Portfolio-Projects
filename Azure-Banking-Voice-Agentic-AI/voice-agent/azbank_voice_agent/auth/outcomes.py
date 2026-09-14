"""What one keypress can result in. The authenticator's whole vocabulary, in one place.

Seven, in two groups. The first three are the caller still keying: nothing has been decided, and
the relay says nothing at all in response to them -- speaking over a caller mid-entry is how a
prompt for a PIN turns into a caller who cannot finish keying one.

    ACCUMULATING   a digit landed in the buffer, and the entry is not complete
    CLEARED        star wiped the buffer, and no check ran (so this costs no attempt)
    IGNORED        nothing happened: pound, an unrecognised key, or a key after the call's
                   authentication question has already been settled one way or the other

The last four are verdicts, and are the ones the relay acts on:

    AUTHENTICATED  the system of record accepted the PIN; the call's auth state flips, once
    REJECTED       a rejected credential, and one spent attempt
    EXHAUSTED      the third rejected credential; the call ends after the caller is told
    UNAVAILABLE    no verdict was produced, so none may be inferred -- and no attempt is spent,
                   because CONTEXT.md defines an attempt as a check that *completed*

**REJECTED and UNAVAILABLE are the pair worth keeping apart.** One is the system saying no, the
other is the system saying nothing, and collapsing them would either spend a caller's attempts on
somebody else's outage or let an outage look like a wrong PIN.
"""
ACCUMULATING = "accumulating"
CLEARED = "cleared"
IGNORED = "ignored"

AUTHENTICATED = "authenticated"
REJECTED = "rejected_credential"
EXHAUSTED = "attempts_exhausted"
UNAVAILABLE = "unavailable"

#: The ones the relay acts on. Everything else is the caller still keying.
SPOKEN = (AUTHENTICATED, REJECTED, EXHAUSTED, UNAVAILABLE)

#: The ones that mean "say nothing" -- named so a reader does not have to derive the complement.
SILENT = (ACCUMULATING, CLEARED, IGNORED)
