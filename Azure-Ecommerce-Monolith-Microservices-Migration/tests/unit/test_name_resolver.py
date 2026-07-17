"""Unit tests for infra/name_resolver.py using mocked checkers — no real
Azure calls (the real-Azure verification for this logic was run manually
against a throwaway ACR during development; see CLAUDE.md)."""
from name_resolver import _candidate_names, resolve_name


def test_candidate_names_hyphenated():
    names = list(_get_first_n(_candidate_names("base"), 3))
    assert names == ["base", "base-2", "base-3"]


def test_candidate_names_alphanumeric_only():
    names = list(_get_first_n(_candidate_names("base", alphanumeric_only=True), 3))
    assert names == ["base", "base2", "base3"]


def test_resolve_name_returns_base_when_free():
    assert resolve_name("myacr", lambda n: False) == "myacr"


def test_resolve_name_increments_on_collision():
    taken = {"myacr"}
    resolved = resolve_name("myacr", lambda n: n in taken)
    assert resolved == "myacr-2"


def test_resolve_name_increments_multiple_times():
    taken = {"myacr", "myacr-2", "myacr-3"}
    resolved = resolve_name("myacr", lambda n: n in taken)
    assert resolved == "myacr-4"


def test_resolve_name_alphanumeric_suffix():
    taken = {"myacr"}
    resolved = resolve_name("myacr", lambda n: n in taken, alphanumeric_only=True)
    assert resolved == "myacr2"


def _get_first_n(generator, n):
    for _ in range(n):
        yield next(generator)
