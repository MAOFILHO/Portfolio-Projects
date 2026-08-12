"""Refuses to hand out a real-AWS client while moto is patching botocore -- `ADR-013`.

The bug this exists to prevent, verbatim from Phase 5 Stage 8: a real Bedrock `Converse` call
made inside a `with mock_aws():` block (opened to seed a moto DynamoDB table) was intercepted
by moto and answered with a fabricated 404, "Not yet implemented". The call never reached AWS.
Nothing raised. The verification script would have happily reported on the fabricated response.

That is a **false-verification** pattern rather than an ordinary bug, and the reason it earns a
guard rather than a convention is the direction it fails in: silently, toward looking like it
worked. A test that wrongly fails gets fixed within minutes. A test that wrongly passes can sit
in the suite for the life of the project.

## Why this guards Bedrock and deliberately does not guard DynamoDB

The rule is not "never mix moto and real clients" -- it is narrower and more useful than that:

* moto **implements DynamoDB faithfully.** A DynamoDB call answered by moto is a deliberate,
  correct substitution: the whole point of `DynamoVectorStore(..., endpoint_url=None)` under
  `mock_aws()`, of `build_test_checkpointer`, and of every table this project touches in tests.
  Guarding those would break a pattern that is working exactly as intended.
* moto **does not implement Bedrock.** It has just enough of a `bedrock-runtime` backend to
  intercept the request and return an error that looks like it came from AWS. There is no
  scenario in this project where a moto-answered Bedrock call is the intended behaviour.

So the guard goes on the clients for services this project only ever calls *for real*, and the
dual-mode DynamoDB paths are left alone and documented as dual-mode. See
`docs/TESTING-CONVENTIONS.md` for the rule as it applies to test authorship.

## No escape hatch, on purpose

There is no `allow_inside_mock=True`, no environment variable, no `# noqa`-style opt-out. The
correct remedy for tripping this guard is always the same one that actually fixed Stage 8:
**narrow the mock scope** so the real call happens outside it. An escape hatch would be reached
for first and understood second, which is how the guard would come to certify the exact pattern
it was written to stop.

## Mechanism, and how it fails if moto moves

`moto.core.models.botocore_stubber` is a module-level singleton whose `.enabled` flag is set
True by `mock_aws.__enter__` and False by the outermost `__exit__` -- verified empirically
against moto 5.0.28 for the context-manager form, the decorator form, and nesting.

It is a moto internal, not a documented public API, so it can move between versions. The
failure mode of a moved internal is `moto_is_patching()` silently returning False forever --
which would disable the guard without a single test going red. `tests/unit/test_mock_guard.py`
therefore contains a **canary test** that asserts the flag actually flips inside a real
`mock_aws()` block. If moto relocates the internal, that test fails loudly on the next upgrade
instead of the guard quietly ceasing to guard. moto is pinned, and the canary is the thing that
makes the pin's expiry visible.

## Observers

Real-client construction is the natural place for other layers to notice that this process has
started making real calls, so `assert_real_aws_allowed` also notifies registered observers and
keeps a count. Deliberately generic: this module knows nothing about who is listening or why,
and `src/` gains no dependency on `evals/`. The eval harness's independent-set guard
(`evals/holdout_ledger.py`) is the only current subscriber, and it both registers an observer
*and* reads the count at import, so it cannot be defeated by construction order.
"""

from __future__ import annotations

from collections.abc import Callable


class RealAWSCallInsideMockError(RuntimeError):
    """A real-AWS client was requested while moto was patching botocore (`ADR-013`)."""


_observers: list[Callable[[str], None]] = []
_real_client_count = 0


def register_real_client_observer(observer: Callable[[str], None]) -> None:
    """Called for every subsequent real-client construction, with the `what` label."""
    _observers.append(observer)


def real_client_count() -> int:
    """How many real AWS clients this process has constructed. Lets a late-importing observer
    discover that construction already happened, instead of only seeing what comes next."""
    return _real_client_count


def moto_is_patching() -> bool:
    """True when a `mock_aws()` scope is currently active anywhere in this process.

    Returns False when moto is not installed at all -- it is a dev dependency, so in any
    deployed environment the import fails and there is by definition no mock to collide with.
    """
    try:
        from moto.core.models import botocore_stubber
    except ImportError:  # pragma: no cover - exercised only where moto is absent
        return False
    return bool(botocore_stubber.enabled)


def assert_real_aws_allowed(what: str) -> None:
    """Raises `RealAWSCallInsideMockError` if a `mock_aws()` scope is active.

    `what` names the client being constructed, so the traceback says which real call was about
    to be swallowed rather than leaving the reader to work it out.
    """
    if moto_is_patching():
        raise RealAWSCallInsideMockError(
            f"Refusing to construct a real AWS client ({what}) while moto is patching "
            f"botocore: the call would be intercepted and answered with a fabricated "
            f"response instead of reaching AWS, and would look like it succeeded. "
            f"Close the mock_aws() scope before making real calls -- see ADR-013 and "
            f"docs/TESTING-CONVENTIONS.md. There is deliberately no override."
        )
    global _real_client_count
    _real_client_count += 1
    # After the moto check, so a refused construction is not counted as one that happened.
    for observer in _observers:
        observer(what)
