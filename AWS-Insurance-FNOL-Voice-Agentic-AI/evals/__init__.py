"""Phase 6 evaluation harness: golden set, component and conversation evals, judge rubrics.

Top-level rather than a subpackage of `src/fnol_voice_agent/` on purpose, per `TARGET-LAYOUT.md`: the
golden corpus is *data the harness reads to grade the agent*, not library code that ships inside the
agent's wheel. Keeping it out of the package also makes it structurally impossible for application code
to import a test expectation by accident.
"""
