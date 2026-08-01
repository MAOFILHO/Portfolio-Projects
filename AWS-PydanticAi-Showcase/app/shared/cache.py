"""A tiny exact-match result cache, shared by every demo.

Demos get shown repeatedly with the same handful of inputs, and every miss is
a real (paid, slow) model call. Normalizing whitespace and case means "SQL vs
NoSQL?" and "  sql VS nosql? " share an entry.

Deliberately process-local and TTL-less: the app runs as a single Fargate task,
and a demo doesn't need cache invalidation semantics. Anything longer-lived
should reach for a real cache with an eviction policy instead.
"""

from __future__ import annotations

from typing import Generic, TypeVar

T = TypeVar("T")


def normalize(text: str) -> str:
    return " ".join(text.split()).lower()


class DemoCache(Generic[T]):
    def __init__(self) -> None:
        self._entries: dict[str, T] = {}

    def get(self, key: str) -> T | None:
        return self._entries.get(normalize(key))

    def set(self, key: str, value: T) -> None:
        self._entries[normalize(key)] = value

    def clear(self) -> None:
        """Used by tests, which would otherwise leak cache hits between cases."""
        self._entries.clear()
