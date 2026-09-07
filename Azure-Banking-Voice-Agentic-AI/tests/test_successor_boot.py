"""T-B3-SUCCESSOR-BOOT — the documented successor model boots and completes one turn.

Named test case, added to docs/PLAN.md alongside decision 14's active-pin/successor restructure.
It exists so that migrating when the active pin approaches retirement is a short check against
something already proven to work, rather than a model evaluation run under deadline pressure. It
can only exist now because this is the first phase where a fake realtime server exists to boot
anything against (issue #18).

**Skipped by default**, because it exercises a model this project has not deployed. Run it
deliberately:

    AZBANK_RUN_SUCCESSOR_BOOT=1 python -m unittest tests.test_successor_boot -v

When it is run deliberately it must FAIL on a misconfigured successor, never skip -- a rehearsal
that silently declines to run is worse than no rehearsal, because it reads green.

What this proves and what it does not: the boot guard admits the successor identity with the
required warning, and once admitted, a full call completes -- proved as one sequence, since
model identity is a boot-time property this project's wire protocol never touches again mid-call
(nothing here would distinguish a call running on the successor from one running on the active
pin except that the guard was asked about the successor first). It does NOT prove the successor
is deployable in this subscription or priced as expected -- those need a real deployment, which is
billable and out of scope here.
"""
import asyncio
import json
import os
import unittest
from unittest.mock import patch

from azbank_voice_agent import accounts, boot
from azbank_voice_agent.dispatch import gate
from azbank_voice_agent.realtime.fake import (
    FakeRealtimeServer,
    audio_delta,
    function_call,
    response_done,
)
from azbank_voice_agent.realtime.session import run_call
from azbank_voice_agent.transport.fake import FakeTransport, audio_frame

RUN_FLAG = "AZBANK_RUN_SUCCESSOR_BOOT"

_skip_unless_deliberate = unittest.skipUnless(
    os.environ.get(RUN_FLAG) == "1",
    f"successor-boot rehearsal is skip-by-default; set {RUN_FLAG}=1 to run it",
)


@_skip_unless_deliberate
class SuccessorBootRehearsal(unittest.TestCase):
    def setUp(self):
        accounts.ACCOUNTS.clear()
        accounts.ACCOUNTS.update({"chequing": 2400.0, "savings": 500.0})
        # This rehearsal proves the call *completes* on the successor, independent of B1 gate
        # policy (empty until Phase 4) -- patched open so the two concerns don't conflate.
        self._gate_patcher = patch.object(gate, "is_allowed", return_value=True)
        self._gate_patcher.start()
        self.addCleanup(self._gate_patcher.stop)

    def test_the_boot_guard_admits_the_successor_and_says_so(self):
        name, version = boot.SUCCESSOR_REALTIME_MODEL
        self.assertTrue(name and version, "successor pin is not configured")

        with self.assertLogs(boot.log, level="WARNING") as cm:
            live = boot.assert_boot_safety(
                reader=lambda deployment: boot.SUCCESSOR_REALTIME_MODEL,
                env={"AOAI_DEPLOYMENT": name},
            )

        self.assertEqual(live, boot.SUCCESSOR_REALTIME_MODEL)
        self.assertTrue(
            any("deliberate migration" in line for line in cm.output),
            "booting on the successor must warn -- a silent migration is the thing B3 prevents",
        )

    def test_a_full_turn_completes_once_the_guard_has_admitted_the_successor(self):
        # A full turn, by itself, proves nothing successor-specific: run_call is deployment-
        # agnostic by design (model identity is a boot-time property, checked once in app.py's
        # lifespan, before any call -- the relay never touches it again, and neither does the
        # wire protocol FakeRealtimeServer replays). An earlier version of this test ran a call
        # scripted with "successor-*" strings but never went through the guard at all -- it would
        # have passed identically under the active pin, proving nothing (caught by /code-review
        # of Phase 2, 2026-09-07). What T-B3-SUCCESSOR-BOOT actually claims, given that
        # architecture, is sequential: the guard admits the successor, and only *given that*
        # admission, a full turn completes -- so this test performs both steps in order, not one
        # in isolation.
        name, _ = boot.SUCCESSOR_REALTIME_MODEL
        live = boot.assert_boot_safety(
            reader=lambda deployment: boot.SUCCESSOR_REALTIME_MODEL,
            env={"AOAI_DEPLOYMENT": name},
        )
        self.assertEqual(live, boot.SUCCESSOR_REALTIME_MODEL, "guard did not admit the successor")

        transport = FakeTransport(frames=[audio_frame("caller-on-successor")], hang=True)
        realtime = FakeRealtimeServer(
            events=[
                audio_delta("successor-greeting"),
                function_call("get_balance", '{"account": "chequing"}'),
                audio_delta("successor-answers"),
                response_done(),
            ],
            respond_after_appends=1,
        )

        asyncio.run(run_call(transport, realtime))

        self.assertEqual(
            transport.sent_audio_payloads, ["successor-greeting", "successor-answers"]
        )
        _, output = realtime.tool_outputs[0]
        self.assertEqual(json.loads(output), {"result": 2400.0})

    def test_the_successor_is_distinct_from_the_active_pin(self):
        # If these ever collapse to the same value, the rehearsal is testing nothing and the
        # migration path has quietly stopped existing.
        self.assertNotEqual(boot.ACTIVE_REALTIME_MODEL, boot.SUCCESSOR_REALTIME_MODEL)
        self.assertIn(boot.SUCCESSOR_REALTIME_MODEL, boot.ALLOWED_REALTIME_MODELS)


class RehearsalIsWiredCorrectly(unittest.TestCase):
    """Runs always -- proving the skip is deliberate and reversible, not an accident that would
    leave the rehearsal permanently dead."""

    def test_the_run_flag_is_the_only_thing_gating_the_rehearsal(self):
        self.assertEqual(RUN_FLAG, "AZBANK_RUN_SUCCESSOR_BOOT")
        expected_skipped = os.environ.get(RUN_FLAG) != "1"
        self.assertEqual(
            getattr(SuccessorBootRehearsal, "__unittest_skip__", False), expected_skipped
        )


if __name__ == "__main__":
    unittest.main()
