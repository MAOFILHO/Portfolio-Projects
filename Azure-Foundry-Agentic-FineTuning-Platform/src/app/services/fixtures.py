"""Mock-mode data source.

Serves the recorded fixtures built by `data/build_fixtures.py`, whose values are
transcribed from the lab guides. This is what makes `DEMO_MODE=mock` a faithful
rehearsal of the live run rather than a hollow stub.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from app.config import FIXTURES_DIR
from app.schemas.catalog import Leaderboard, ModelCard, ModelComparison
from app.schemas.evaluation import EvaluationRun, SyntheticDataset
from app.schemas.finetune import FineTuneJob


@lru_cache
def _load(name: str) -> Any:
    path = FIXTURES_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"fixture {name!r} missing. Run: python data/build_fixtures.py")
    return json.loads(path.read_text(encoding="utf-8"))


def get_model_cards() -> list[ModelCard]:
    return [ModelCard.model_validate(c) for c in _load("model_cards.json")]


def get_model_card(name: str) -> ModelCard:
    for card in get_model_cards():
        if card.name == name:
            return card
    known = ", ".join(c.name for c in get_model_cards())
    raise KeyError(f"unknown model {name!r}; fixtures contain: {known}")


def get_leaderboard() -> Leaderboard:
    return Leaderboard.model_validate(_load("leaderboard.json"))


def get_model_comparison() -> ModelComparison:
    return ModelComparison.model_validate(_load("model_comparison.json"))


def get_finetune_job() -> FineTuneJob:
    return FineTuneJob.model_validate(_load("finetune_job.json"))


def get_synthetic_dataset() -> SyntheticDataset:
    return SyntheticDataset.model_validate(_load("synthetic_dataset.json"))


def get_evaluation_run() -> EvaluationRun:
    return EvaluationRun.model_validate(_load("evaluation_run.json"))


def get_chat_response(prompt: str, fine_tuned: bool) -> str:
    """Canned reply for one of the guide's five canonical prompts.

    Falls back to a generic reply in the appropriate register so that arbitrary
    user prompts still demonstrate the behavioural difference.
    """
    responses = _load("chat_responses.json")
    bucket = responses["fine_tuned" if fine_tuned else "baseline"]
    if prompt in bucket:
        return bucket[prompt]

    # Normalise whitespace before giving up — the guides wrap prompts across lines.
    squashed = " ".join(prompt.split())
    for key, value in bucket.items():
        if " ".join(key.split()) == squashed:
            return value

    if fine_tuned:
        return (
            "What an adventure you're planning! There's so much to discover once you "
            "know where to look, and the best moments are usually the unplanned ones. "
            "What kind of experiences are you hoping for on this trip?"
        )
    return (
        "There are several factors to consider. Availability, cost, and timing all "
        "vary by season and destination. Reviewing official guidance before you "
        "travel is advisable."
    )
