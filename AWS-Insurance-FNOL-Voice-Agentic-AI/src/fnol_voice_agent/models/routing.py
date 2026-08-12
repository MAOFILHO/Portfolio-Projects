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
