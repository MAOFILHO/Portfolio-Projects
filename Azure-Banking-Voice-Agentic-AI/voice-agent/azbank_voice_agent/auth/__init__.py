"""The auth seam: the keypad's rules, and the sentences the caller hears about them.

A package alongside dispatch/, transport/, realtime/ and core_banking/, holding the state machine
and nothing else. It has no client of its own: verification goes through the core-banking client
the relay already injects, which is what makes an unreachable service fail authentication closed
for free.
"""
from . import outcomes
from .authenticator import (
    MAX_ATTEMPTS,
    PIN_LENGTH,
    SENTENCES,
    AttemptsExhausted,
    Authenticator,
    sentence_for,
)

__all__ = [
    "MAX_ATTEMPTS",
    "PIN_LENGTH",
    "SENTENCES",
    "AttemptsExhausted",
    "Authenticator",
    "outcomes",
    "sentence_for",
]
