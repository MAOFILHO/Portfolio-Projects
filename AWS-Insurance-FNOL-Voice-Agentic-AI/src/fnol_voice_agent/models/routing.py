"""The merged router+L2 safety-classification output schema. Field-for-field match to
`docs/phase4/PROMPT-REGISTRY.md` §1.1's `classify_turn` tool JSON schema -- this model IS that schema,
expressed once, so Stage 4's Bedrock router (aws/bedrock_router.py) validates the forced tool-use response
against it directly rather than maintaining a second, hand-written JSON schema dict that could drift from
this one.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .enums import CoverageQuestionType, Intent


class TurnClassification(BaseModel):
    safety_flag: bool
    intent: Intent
    intent_confidence: float = Field(ge=0, le=1)
    coverage_question_type: CoverageQuestionType = CoverageQuestionType.NOT_APPLICABLE


# --- The split (`ADR-014`, Phase 7 Stage 3) -------------------------------------------------------
#
# Two single-purpose schemas rather than one object with four fields. The schema split is the
# mechanism, not a formality: `RESULTS.md` §3.2 measured `safety_flag` and `intent` agreeing 27/28
# times, and a model asked to fill one structured object makes that object's fields consistent with
# each other. Two objects produced by two calls cannot be made consistent by the model, because
# neither call can see the other's answer.


class InjuryVerdict(BaseModel):
    """The single-purpose detector's entire output. One required boolean and nothing else.

    Deliberately has no `confidence` field. A confidence score on a recall-biased safety detector
    invites a threshold, a threshold invites tuning it upward when false escalation is embarrassing,
    and that is the exact trade `C1` forbids. The detector answers the question it was asked.
    """

    injury_indicated: bool


class IntentClassification(BaseModel):
    """The classifier's output, with no safety field at all.

    `safety_flag` is absent rather than optional. An optional safety field would let this call
    express a safety opinion that the combiner would then have to decide whether to honour, which
    reintroduces the coupling the split exists to remove -- and would make `I3` (the detector cannot
    be vetoed) a runtime rule instead of a structural one.
    """

    intent: Intent
    intent_confidence: float = Field(ge=0, le=1)
    coverage_question_type: CoverageQuestionType = CoverageQuestionType.NOT_APPLICABLE
