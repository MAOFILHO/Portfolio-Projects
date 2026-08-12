"""Real-AWS-touching wrappers. See docs/phase5/BUILD-PLAN.md Stage 4.

`bedrock_router.py` is the only module here today: the merged router+L2 safety call and
the feature-flagged generation call (`ADR-004`), both against Bedrock's `Converse` API.
"""
