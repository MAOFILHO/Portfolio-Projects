"""Phase 11 Stage C -- `observability/log_redaction.py`.

Every test uses its own fresh `logging.Logger` (never the real root logger) with `propagate=False`, so
these tests cannot leak filter state into each other or into pytest's own log capture.
"""

from __future__ import annotations

import logging
import uuid

import pytest

from fnol_voice_agent.observability.log_redaction import (
    PIIRedactionLogFilter,
    install_pii_log_filter,
)

_SYNTHETIC_PHONE = "555-0142"  # this project's synthetic exchange convention, not a real number
_SYNTHETIC_EMAIL = "marked-synthetic-pii@example.invalid"


class _CapturingHandler(logging.Handler):
    """Records each formatted line it emits, so a test can assert on exactly what left the logger."""

    def __init__(self) -> None:
        super().__init__()
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(self.format(record))


@pytest.fixture
def logger_and_handler() -> tuple[logging.Logger, _CapturingHandler]:
    logger = logging.getLogger(f"test-log-redaction-{uuid.uuid4()}")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    handler = _CapturingHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    return logger, handler


def test_message_with_no_args_is_redacted(
    logger_and_handler: tuple[logging.Logger, _CapturingHandler],
) -> None:
    logger, handler = logger_and_handler
    install_pii_log_filter(logger)

    logger.info(f"caller phone on file is {_SYNTHETIC_PHONE}")

    assert _SYNTHETIC_PHONE not in handler.lines[0]
    assert "[REDACTED:PHONE]" in handler.lines[0]


def test_percent_style_args_are_redacted(
    logger_and_handler: tuple[logging.Logger, _CapturingHandler],
) -> None:
    logger, handler = logger_and_handler
    install_pii_log_filter(logger)

    logger.info("caller email is %s", _SYNTHETIC_EMAIL)

    assert _SYNTHETIC_EMAIL not in handler.lines[0]
    assert "[REDACTED:EMAIL]" in handler.lines[0]


def test_without_the_filter_pii_reaches_the_sink_unredacted(
    logger_and_handler: tuple[logging.Logger, _CapturingHandler],
) -> None:
    """The pre-filter half of the positive control: proves the synthetic PII would otherwise reach the
    sink, so the post-filter absence in the tests above is evidence of redaction and not just an artifact
    of PII-shaped text never appearing in the first place."""
    logger, handler = logger_and_handler
    # Deliberately NOT calling install_pii_log_filter here.

    logger.info("caller email is %s", _SYNTHETIC_EMAIL)

    assert _SYNTHETIC_EMAIL in handler.lines[0]


def test_operational_fields_pass_through_unchanged(
    logger_and_handler: tuple[logging.Logger, _CapturingHandler],
) -> None:
    """The negative case: the four fields the real escalation log lines carry
    (`lex_codehook.py`'s `_escalate`/`_respond_from_graph_result`) must not be altered by the filter --
    a redactor that destroys diagnostic value fails differently but still fails."""
    logger, handler = logger_and_handler
    install_pii_log_filter(logger)

    contact_id = "8f14e45f-ceea-4b57-9b5e-3c6c6c6c6c6c"
    triggering_layer = "L1"
    route = 1
    escalation_reason = "detection-pregraph"

    logger.info(
        "escalating contact %s on layer %s route %s reason %s",
        contact_id,
        triggering_layer,
        route,
        escalation_reason,
    )

    line = handler.lines[0]
    assert contact_id in line
    assert triggering_layer in line
    assert str(route) in line
    assert escalation_reason in line
    assert "[REDACTED:" not in line


def test_non_string_arg_is_not_stringified(
    logger_and_handler: tuple[logging.Logger, _CapturingHandler],
) -> None:
    logger, handler = logger_and_handler
    filt = install_pii_log_filter(logger)
    record = logging.LogRecord(
        name=logger.name,
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="route %s",
        args=(3,),
        exc_info=None,
    )
    filt.filter(record)
    assert record.args == (3,)
    assert isinstance(record.args[0], int)


def test_list_arg_elements_are_redacted_when_pii_shaped(
    logger_and_handler: tuple[logging.Logger, _CapturingHandler],
) -> None:
    """`_log_turn_observability` (`api/lex_codehook.py`) passes two `list[str]` args -- slot-key lists --
    the first non-`str` args this codebase has ever logged. The filter must walk INTO a list arg and
    redact each string element the same way it redacts a bare string arg, not skip the whole list because
    the top-level value isn't a `str`."""
    logger, handler = logger_and_handler
    install_pii_log_filter(logger)

    logger.info("slot keys %s", [_SYNTHETIC_EMAIL, "policy_number"])

    line = handler.lines[0]
    assert _SYNTHETIC_EMAIL not in line
    assert "[REDACTED:EMAIL]" in line
    assert "policy_number" in line


def test_list_arg_non_pii_elements_pass_through_unchanged(
    logger_and_handler: tuple[logging.Logger, _CapturingHandler],
) -> None:
    """The negative case paired with the test above: ordinary slot-key-shaped strings in a list must not
    be altered -- a redactor that mangles non-PII list contents fails differently but still fails.
    """
    logger, handler = logger_and_handler
    install_pii_log_filter(logger)

    logger.info("slot keys %s", ["policy_number", "loss_datetime"])

    line = handler.lines[0]
    assert "policy_number" in line
    assert "loss_datetime" in line
    assert "[REDACTED:" not in line


def test_install_is_idempotent_per_handler(
    logger_and_handler: tuple[logging.Logger, _CapturingHandler],
) -> None:
    logger, handler = logger_and_handler
    install_pii_log_filter(logger)
    install_pii_log_filter(logger)
    install_pii_log_filter(logger)

    assert sum(isinstance(f, PIIRedactionLogFilter) for f in handler.filters) == 1


def test_filter_never_suppresses_a_record(
    logger_and_handler: tuple[logging.Logger, _CapturingHandler],
) -> None:
    logger, handler = logger_and_handler
    install_pii_log_filter(logger)

    logger.info("no PII here at all")

    assert len(handler.lines) == 1


@pytest.fixture
def install_report_handler() -> _CapturingHandler:
    """Captures `install_pii_log_filter()`'s self-report line.

    That line is logged through THIS module's own logger (`fnol_voice_agent.observability.log_redaction`),
    not through whichever `logger` argument was passed in for attachment -- so a test that wants to read
    the report has to listen on the module's logger, separately from the target logger under test. Handler
    is removed in teardown so this doesn't leak into other tests.
    """
    module_logger = logging.getLogger("fnol_voice_agent.observability.log_redaction")
    module_logger.setLevel(logging.INFO)
    handler = _CapturingHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    module_logger.addHandler(handler)
    yield handler
    module_logger.removeHandler(handler)


def test_install_self_reports_handlers_attached(
    logger_and_handler: tuple[logging.Logger, _CapturingHandler],
    install_report_handler: _CapturingHandler,
) -> None:
    """Marco's option (c): proving the filter is attached should not need a diagnostic branch in
    `handler()` or a full re-verification cycle to check -- the install call reports on itself, every
    time, permanently."""
    logger, _handler = logger_and_handler

    install_pii_log_filter(logger)

    assert install_report_handler.lines[-1] == "pii_log_filter_installed handlers=1"


def test_install_self_reports_zero_on_idempotent_reinstall(
    logger_and_handler: tuple[logging.Logger, _CapturingHandler],
    install_report_handler: _CapturingHandler,
) -> None:
    """`handlers=0` is the silent-no-op signal make visible -- a cold start where the target logger had
    no handlers to attach to reports the same `handlers=0` line, which is exactly the failure mode the
    local proof script (`verify_log_redaction.py`) could not distinguish from success on its own."""
    logger, _handler = logger_and_handler

    install_pii_log_filter(logger)
    install_pii_log_filter(logger)

    assert install_report_handler.lines[0] == "pii_log_filter_installed handlers=1"
    assert install_report_handler.lines[1] == "pii_log_filter_installed handlers=0"


def test_install_self_reports_zero_when_target_has_no_handlers(
    install_report_handler: _CapturingHandler,
) -> None:
    logger = logging.getLogger(f"test-log-redaction-no-handlers-{uuid.uuid4()}")
    logger.propagate = False

    install_pii_log_filter(logger)

    assert install_report_handler.lines[-1] == "pii_log_filter_installed handlers=0"
