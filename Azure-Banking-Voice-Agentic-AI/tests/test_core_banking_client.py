"""The core-banking client's own behaviour: the three outcomes, and resilience.

Every failure here is produced by `httpx.MockTransport` -- in-process, no sockets, no sleeps beyond
the ones under test. That is deliberate (issue #27): the deterministic failure suite lives here, and
exactly one test in the whole project uses a real network hop (tests/test_core_banking_live.py).
The breaker's clock is injected for the same reason -- proving a 30-second open window must not
take 30 seconds.

The load-bearing cases, in the order they'd hurt if they regressed:

  * a timed-out `transfer` reaches the service exactly ONCE -- retrying a non-idempotent POST that
    may already have committed is a double-spend
  * no failure mode ever produces a balance figure -- CLAUDE.md's silent-fallback exclusion applied
    to the failure modes this phase introduces
  * a 404 raises rather than resolving to anything -- T-UNKNOWN-ACCT
"""
import unittest

import httpx
from azbank_voice_agent.core_banking import client as cb


class FakeClock:
    """A monotonic clock that only moves when a test moves it."""

    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class Recorder:
    """Counts requests and replies with whatever the test scripted for each one in turn."""

    def __init__(self, *responses):
        self.requests = []
        self._responses = list(responses)

    def __call__(self, request):
        self.requests.append(request)
        reply = self._responses.pop(0) if self._responses else self._responses_exhausted()
        if isinstance(reply, Exception):
            raise reply
        return reply

    def _responses_exhausted(self):
        raise AssertionError("client made more requests than the test scripted")

    @property
    def count(self):
        return len(self.requests)


def _client(recorder, clock=None):
    return cb.HttpCoreBankingClient(
        base_url="http://core-banking.test",
        transport=httpx.MockTransport(recorder),
        clock=clock or FakeClock(),
    )


def _json(payload, status=200):
    return httpx.Response(status, json=payload)


_ACCOUNTS = _json({"accounts": [
    {"name": "chequing", "balance_cents": 240000},
    {"name": "savings", "balance_cents": 50000},
]})
_CHEQUING = _json({"name": "chequing", "balance_cents": 240000})


class HappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_get_balance_returns_dollars_not_cents(self):
        # The service stores and speaks integer cents; the model needs a number it can say out
        # loud. That conversion happens here, once, at the presentation boundary -- and nowhere
        # near persistence.
        balance = await _client(Recorder(_CHEQUING)).get_balance("chequing")
        self.assertEqual(balance, 2400.00)

    async def test_list_accounts_returns_dollars(self):
        accounts = await _client(Recorder(_ACCOUNTS)).list_accounts()
        self.assertEqual(accounts, {"chequing": 2400.00, "savings": 500.00})

    async def test_completed_transfer(self):
        response = _json({
            "outcome": "completed", "from_balance_cents": 225000, "to_balance_cents": 65000,
        })
        result = await _client(Recorder(response)).transfer("chequing", "savings", 150.00)
        self.assertEqual(result.outcome, "completed")
        self.assertEqual(result.from_balance, 2250.00)

    async def test_transfer_sends_cents_not_dollars(self):
        recorder = Recorder(_json({"outcome": "completed", "from_balance_cents": 1, "to_balance_cents": 1}))
        await _client(recorder).transfer("chequing", "savings", 150.00)
        self.assertIn(b'"amount_cents":15000', recorder.requests[0].content.replace(b" ", b""))


class DeclinedIsNotAnError(unittest.IsolatedAsyncioTestCase):
    async def test_declined_transfer_comes_back_as_an_outcome(self):
        # A decline is a normal outcome of a working system (CONTEXT.md). It must not raise, and it
        # must carry the real available amount so the caller can be told what they *can* do.
        response = _json({
            "outcome": "declined", "reason": "insufficient_funds", "available_cents": 240000,
        })
        result = await _client(Recorder(response)).transfer("chequing", "savings", 3000.00)
        self.assertEqual(result.outcome, "declined")
        self.assertEqual(result.reason, "insufficient_funds")
        self.assertEqual(result.available, 2400.00)


class UnknownAccountRaises(unittest.IsolatedAsyncioTestCase):
    """T-UNKNOWN-ACCT. Never a default, never a zero, never another account's balance."""

    async def test_404_on_a_balance_raises(self):
        with self.assertRaises(cb.UnknownAccountError):
            await _client(Recorder(_json({"detail": "unknown_account"}, status=404))).get_balance("bitcoin")

    async def test_404_on_a_transfer_raises(self):
        with self.assertRaises(cb.UnknownAccountError):
            await _client(Recorder(_json({"detail": "unknown_account"}, status=404))).transfer(
                "bitcoin", "savings", 10.00
            )

    async def test_unknown_account_is_not_reported_as_unavailable(self):
        # The two must stay distinguishable: "that account doesn't exist" and "the bank is
        # unreachable" get different spoken responses.
        recorder = Recorder(_json({"detail": "unknown_account"}, status=404))
        with self.assertRaises(cb.UnknownAccountError):
            await _client(recorder).get_balance("bitcoin")


class NothingInternalReachesTheCaller(unittest.IsolatedAsyncioTestCase):
    """A caller hears whatever ends up on the exception. Nothing internal may end up there.

    The first version of this client raised UnknownAccountError with `response.request.url`, so a
    caller heard the service's internal hostname read out loud by the agent (/code-review,
    2026-09-08). The account name now comes from the service's own 404 body -- the system of record
    is the only thing that knows *which* of a transfer's two accounts was the bad one.
    """

    def _404(self, body):
        return _json(body, status=404)

    async def test_the_account_name_comes_from_the_service_body(self):
        recorder = Recorder(self._404({"detail": {"error": "unknown_account", "account": "bitcoin"}}))
        with self.assertRaises(cb.UnknownAccountError) as caught:
            await _client(recorder).get_balance("bitcoin")
        self.assertEqual(caught.exception.args[0], "bitcoin")

    async def test_the_request_url_never_reaches_the_exception(self):
        for body in (
            {"detail": {"error": "unknown_account", "account": "bitcoin"}},
            {"detail": "unknown_account"},          # older/plain shape: no name available
            {"nothing": "recognisable"},
        ):
            with self.subTest(body=body):
                recorder = Recorder(self._404(body))
                with self.assertRaises(cb.UnknownAccountError) as caught:
                    await _client(recorder).get_balance("bitcoin")
                self.assertNotIn("core-banking.test", str(caught.exception.args))
                self.assertNotIn("http", str(caught.exception.args))

    async def test_an_unparseable_404_body_yields_no_name_rather_than_a_guess(self):
        recorder = Recorder(httpx.Response(404, content=b"not json at all"))
        with self.assertRaises(cb.UnknownAccountError) as caught:
            await _client(recorder).get_balance("bitcoin")
        self.assertIsNone(caught.exception.args[0])


class RetryPolicy(unittest.IsolatedAsyncioTestCase):
    async def test_a_read_is_retried_once_and_succeeds(self):
        recorder = Recorder(httpx.ReadTimeout("too slow"), _CHEQUING)
        balance = await _client(recorder).get_balance("chequing")
        self.assertEqual(balance, 2400.00)
        self.assertEqual(recorder.count, 2)

    async def test_a_read_that_fails_twice_is_unavailable(self):
        recorder = Recorder(httpx.ReadTimeout("too slow"), httpx.ReadTimeout("too slow"))
        with self.assertRaises(cb.CoreBankingUnavailable):
            await _client(recorder).get_balance("chequing")
        self.assertEqual(recorder.count, 2)

    async def test_a_timed_out_transfer_is_sent_exactly_once(self):
        # The double-spend guard. `transfer` is not idempotent: a POST that timed out may already
        # have committed at the service, so a retry can move the money twice. Idempotency keys are
        # Phase 5's, which is why this is a hard no rather than a tuning parameter.
        recorder = Recorder(httpx.ReadTimeout("too slow"))
        with self.assertRaises(cb.CoreBankingUnavailable):
            await _client(recorder).transfer("chequing", "savings", 150.00)
        self.assertEqual(recorder.count, 1)

    async def test_a_5xx_read_is_retried_once(self):
        recorder = Recorder(_json({"detail": "boom"}, status=503), _CHEQUING)
        self.assertEqual(await _client(recorder).get_balance("chequing"), 2400.00)
        self.assertEqual(recorder.count, 2)

    async def test_a_5xx_transfer_is_not_retried(self):
        recorder = Recorder(_json({"detail": "boom"}, status=503))
        with self.assertRaises(cb.CoreBankingUnavailable):
            await _client(recorder).transfer("chequing", "savings", 150.00)
        self.assertEqual(recorder.count, 1)


class CircuitBreaker(unittest.IsolatedAsyncioTestCase):
    """One breaker per process, for the whole service (issue #25, Q23).

    Not per-endpoint: the failure modes a breaker catches here are service-level -- down,
    saturated, timing out -- and a healthy read path must not be able to mask a service that is
    failing its writes.
    """

    def setUp(self):
        self.clock = FakeClock()

    async def _fail_until_open(self, client, recorder):
        """Drive the client to the failure threshold using transfers (one request each, so the
        request count is the failure count)."""
        for _ in range(cb.BREAKER_FAILURE_THRESHOLD):
            with self.assertRaises(cb.CoreBankingUnavailable):
                await client.transfer("chequing", "savings", 1.00)
        return recorder.count

    async def test_opens_after_the_threshold_and_then_fails_fast(self):
        recorder = Recorder(*[httpx.ConnectError("refused")] * cb.BREAKER_FAILURE_THRESHOLD)
        client = _client(recorder, self.clock)
        requests_before = await self._fail_until_open(client, recorder)
        self.assertEqual(requests_before, cb.BREAKER_FAILURE_THRESHOLD)

        # The next call must not reach the service at all -- that is the entire point of a breaker.
        # `Recorder` is exhausted, so any request would fail the test loudly.
        with self.assertRaises(cb.CoreBankingUnavailable):
            await client.get_balance("chequing")
        self.assertEqual(recorder.count, requests_before)

    async def test_a_success_before_the_threshold_resets_the_count(self):
        # "5 consecutive failures", not "5 failures ever".
        recorder = Recorder(
            *[httpx.ConnectError("refused")] * (cb.BREAKER_FAILURE_THRESHOLD - 1),
            _CHEQUING,
            *[httpx.ConnectError("refused")] * (cb.BREAKER_FAILURE_THRESHOLD - 1),
            _CHEQUING,
        )
        client = _client(recorder, self.clock)
        for _ in range(cb.BREAKER_FAILURE_THRESHOLD - 1):
            with self.assertRaises(cb.CoreBankingUnavailable):
                await client.transfer("chequing", "savings", 1.00)
        self.assertEqual(await client.get_balance("chequing"), 2400.00)
        for _ in range(cb.BREAKER_FAILURE_THRESHOLD - 1):
            with self.assertRaises(cb.CoreBankingUnavailable):
                await client.transfer("chequing", "savings", 1.00)
        # Still closed: the success in the middle broke the run.
        self.assertEqual(await client.get_balance("chequing"), 2400.00)

    async def test_half_open_probe_succeeds_and_closes_the_breaker(self):
        recorder = Recorder(
            *[httpx.ConnectError("refused")] * cb.BREAKER_FAILURE_THRESHOLD,
            _CHEQUING,   # the probe
            _CHEQUING,   # a normal call once closed again
        )
        client = _client(recorder, self.clock)
        await self._fail_until_open(client, recorder)

        self.clock.advance(cb.BREAKER_OPEN_SECONDS + 1)
        self.assertEqual(await client.get_balance("chequing"), 2400.00)
        self.assertEqual(await client.get_balance("chequing"), 2400.00)

    async def test_half_open_probe_fails_and_reopens_the_breaker(self):
        recorder = Recorder(
            *[httpx.ConnectError("refused")] * cb.BREAKER_FAILURE_THRESHOLD,
            httpx.ConnectError("refused"),  # the probe, one request only (transfer: no retry)
        )
        client = _client(recorder, self.clock)
        await self._fail_until_open(client, recorder)

        self.clock.advance(cb.BREAKER_OPEN_SECONDS + 1)
        with self.assertRaises(cb.CoreBankingUnavailable):
            await client.transfer("chequing", "savings", 1.00)

        # Re-opened: the next call fails fast without reaching the exhausted recorder.
        with self.assertRaises(cb.CoreBankingUnavailable):
            await client.transfer("chequing", "savings", 1.00)

    async def test_the_open_window_is_respected(self):
        recorder = Recorder(*[httpx.ConnectError("refused")] * cb.BREAKER_FAILURE_THRESHOLD)
        client = _client(recorder, self.clock)
        await self._fail_until_open(client, recorder)

        self.clock.advance(cb.BREAKER_OPEN_SECONDS - 1)
        with self.assertRaises(cb.CoreBankingUnavailable):
            await client.get_balance("chequing")
        self.assertEqual(recorder.count, cb.BREAKER_FAILURE_THRESHOLD)  # still no probe issued


class NeverFabricatesABalance(unittest.IsolatedAsyncioTestCase):
    """CLAUDE.md's silent-fallback exclusion, applied to the failure modes this phase introduces.

    The reference repo this project was seeded from returned a fixed $1,000.00 for any unknown
    account. The equivalent defect here would be returning a remembered, cached, or defaulted
    balance when the backend can't be reached -- so every failure mode is asserted to raise rather
    than to produce a number.
    """

    async def test_no_failure_mode_returns_a_balance(self):
        failures = {
            "timeout": httpx.ReadTimeout("too slow"),
            "connect refused": httpx.ConnectError("refused"),
            "server error": _json({"detail": "boom"}, status=503),
        }
        for label, failure in failures.items():
            with self.subTest(failure=label):
                recorder = Recorder(failure, failure)
                with self.assertRaises(cb.CoreBankingUnavailable):
                    await _client(recorder).get_balance("chequing")

    async def test_an_open_circuit_returns_no_balance_either(self):
        clock = FakeClock()
        recorder = Recorder(*[httpx.ConnectError("refused")] * cb.BREAKER_FAILURE_THRESHOLD)
        client = _client(recorder, clock)
        for _ in range(cb.BREAKER_FAILURE_THRESHOLD):
            with self.assertRaises(cb.CoreBankingUnavailable):
                await client.transfer("chequing", "savings", 1.00)
        with self.assertRaises(cb.CoreBankingUnavailable):
            await client.get_balance("chequing")

    async def test_a_cached_success_is_not_replayed_on_a_later_failure(self):
        # A read that succeeded once must not be remembered and served when the next one fails.
        recorder = Recorder(_CHEQUING, httpx.ConnectError("refused"), httpx.ConnectError("refused"))
        client = _client(recorder)
        self.assertEqual(await client.get_balance("chequing"), 2400.00)
        with self.assertRaises(cb.CoreBankingUnavailable):
            await client.get_balance("chequing")


class BudgetsArePinned(unittest.TestCase):
    """These numbers were decided at Phase 3 kickoff and are asserted so they cannot drift
    silently before Phase 5, which freezes B5 with tool calls in the hot path."""

    def test_per_attempt_timeout_is_one_second(self):
        self.assertEqual(cb.TIMEOUT_SECONDS, 1.0)

    def test_reads_get_exactly_one_retry(self):
        self.assertEqual(cb.READ_RETRIES, 1)

    def test_breaker_thresholds(self):
        self.assertEqual(cb.BREAKER_FAILURE_THRESHOLD, 5)
        self.assertEqual(cb.BREAKER_OPEN_SECONDS, 30.0)

    def test_worst_case_added_latency_stays_within_budget(self):
        # One retry on a read, both attempts timing out, is the worst a single tool call can add.
        # B5's provisional p95 is 932ms without tool calls in the path; this keeps the tool leg's
        # own ceiling at 2s rather than something a caller would hear as a dropped call.
        worst_case = cb.TIMEOUT_SECONDS * (cb.READ_RETRIES + 1)
        self.assertLessEqual(worst_case, 2.0)


if __name__ == "__main__":
    unittest.main()
