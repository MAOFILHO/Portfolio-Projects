"""The descriptor every demo exposes, and the contract `app.main` mounts.

Each demo is a self-contained package under `app/demos/` that exports a single
`demo: Demo`. Adding a fifth demo means writing the package and appending it to
`DEMOS` — no changes to `main.py`, and the frontend nav picks it up from
`GET /api/demos` without a code change either.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import APIRouter


@dataclass(frozen=True)
class Demo:
    """One showcase app, and the framework mechanism it exists to demonstrate."""

    id: str
    """URL-safe identifier: the API prefix (`/api/{id}`), the frontend module
    name (`static/demos/{id}.js`), and the location hash used to deep-link it."""

    title: str
    mechanism: str
    """The Pydantic AI feature this demo is built to show off. Rendered in the
    nav, because the point of the collection is the mechanisms, not the apps."""

    blurb: str
    router: APIRouter

    def summary(self) -> dict[str, str]:
        """The JSON shape `GET /api/demos` returns for the nav to render."""
        return {
            "id": self.id,
            "title": self.title,
            "mechanism": self.mechanism,
            "blurb": self.blurb,
        }
