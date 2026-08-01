"""The demo registry — the single list `app.main` mounts and the nav renders.

Ordered deliberately: Research Analyst first (the most substantial pipeline),
then the three that each isolate one other framework mechanism.
"""

from __future__ import annotations

from .base import Demo
from .research import demo as research_demo
from .review import demo as review_demo
from .travel import demo as travel_demo
from .triage import demo as triage_demo

DEMOS: tuple[Demo, ...] = (research_demo, triage_demo, review_demo, travel_demo)

__all__ = ["DEMOS", "Demo"]
