"""Phase 11 Stage B1 -- the guardrail-usage emitter. Criterion 3's live source for the operational
dashboard's guardrail-usage panel.

**Why this module exists, stated plainly rather than left implicit.** `RESULTS.md` §16.1 rechecked
`GuardrailResult.usage`'s parsing code (`guardrails/client.py`'s `_parse_response`) and found it unchanged
since Phase 7 Stage 8's live verification -- sufficient to build a panel on, per that section. What Stage 0
also found, and what this module fixes: `agents/nodes/guardrails_nodes.py` calls `apply_guardrail()` on
every turn, both directions, and discards `.usage` completely. A panel over a metric nothing writes is not
a panel, it is a placeholder -- the exact defect criterion 3's own liveness requirement exists to catch. This
module is the write side that finding was missing.

**Emission mechanism: a structured JSON log line, not `cloudwatch:PutMetricData`.** Two reasons, not one:
1. The main Lambda's IAM role (`infra/terraform/stacks/main/lambda.tf`'s `codehook` policy document) grants
   only `logs:CreateLogStream`/`logs:PutLogEvents` today. `PutMetricData` would need a new IAM statement for
   a change whose entire point is observability, not new privilege.
2. This project is already at 1 of 10 always-free CloudWatch custom metrics (the cost dashboard's MTD-usage
   metric) and 1 of 3 free custom dashboards. A real `ApplyGuardrail` response carries five to seven distinct
   `usage` keys (`topicPolicyUnits`, `contentPolicyUnits`, `sensitiveInformationPolicyUnits`,
   `wordPolicyUnits`, `contextualGroundingPolicyUnits`, plus their `...FreeUnits` counterparts) -- turning
   each into its own custom metric, times two sources (INPUT/OUTPUT), would burn through the free-tier
   allowance for a demo-scale project. A CloudWatch Logs Insights **log widget**, reading these lines
   directly out of the codehook Lambda's already-provisioned log group, gets the same panel for $0 new
   IAM surface and $0 new metric-quota consumption -- Logs Insights query cost ($0.005/GB scanned) is the
   only real, and at this project's log volume negligible, line item.

**The `usage={}` case is emitted, not skipped.** `MockGuardrailClient` (every local/test run) never sets
`usage` -- it defaults to `{}` via the dataclass field, in every branch: clean, masked, and blocked alike.
Skipping emission on an empty dict would make "a real call happened, no policy units accrued" indistinguishable
from "the emitter never ran" -- precisely the "zero errors vs. emitter dead" failure this project's own
liveness requirement (Phase 11 criteria table, criterion 3) names by name. So `emit_guardrail_usage` always
logs one line, with `"units": {}` when there is nothing to report, never a silent no-op.

**This line passes through Stage C's `PIIRedactionLogFilter`, deliberately and harmlessly.** It propagates
through the same root-logger handler chain `install_pii_log_filter()` attaches to
(`observability/log_redaction.py`). The payload is `source` (a two-value enum string), `blocked`/`masked`
(booleans), and `units` (a dict of small integers) -- none of `redact_for_transcript`'s patterns
(policy/claim/VIN/plate/licence/phone/email/address/date-time/location) match an enum string or a bare
integer, so this line is expected to reach the sink unchanged. Not re-verified against a live redaction run
in this module's own tests -- `log_redaction`'s own suite already proves operational fields of this same
shape (`contact_id`, `route`, `escalation_reason`) pass through unaltered, and re-proving that here would be
testing the filter a second time rather than testing this module.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping

from fnol_voice_agent.guardrails.client import GuardrailSource

logger = logging.getLogger(__name__)


def emit_guardrail_usage(
    source: GuardrailSource,
    usage: Mapping[str, int],
    *,
    blocked: bool,
    masked: bool = False,
) -> None:
    """Logs one structured line per `apply_guardrail()` call, real or mocked.

    `dict(usage)` copies out of whatever `Mapping` `GuardrailResult.usage` holds (a plain `dict` in
    practice, but the type is only a `Mapping`) so `json.dumps` never has to special-case the container
    type. `sort_keys=True` so the same event always serialises identically -- useful for exact-match
    proofs in tests and for eyeballing a CloudWatch Logs Insights result without keys reshuffling call to
    call.
    """
    payload = {
        "metric": "guardrail_usage",
        "source": source,
        "blocked": blocked,
        "masked": masked,
        "units": dict(usage),
    }
    logger.info("guardrail_usage %s", json.dumps(payload, sort_keys=True))


__all__ = ["emit_guardrail_usage"]
