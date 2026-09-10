"""The one test in this project that uses a real network hop.

Spawns mock-core-banking as a real process and drives the real `HttpCoreBankingClient` against it
over a real socket -- proving the protocol between the two deployables rather than assuming it.
Everything else about the client (every failure path, the retry policy, the circuit breaker) is
covered in tests/test_core_banking_client.py against `httpx.MockTransport`, in-process, with no
sockets at all.

**Deliberately exactly one test** (issue #30). The genuinely-networked surface is a single case
rather than a tax on every failure path: sockets and subprocesses are where flakiness comes from,
and a suite that pays that cost per failure mode ends up slow *and* untrustworthy.

Still L1, not a new tier: L1's contract is "deterministic, every pull request, zero cloud
dependency", and a locally-spawned service meets all three. There is no Azure here, no credential,
and no spend.
"""
import os
import pathlib
import socket
import subprocess
import sys
import tempfile
import time
import unittest

import httpx
from azbank_voice_agent.core_banking import (
    CoreBankingUnavailable,
    HttpCoreBankingClient,
    UnknownAccountError,
)
from azbank_voice_agent.core_banking.fake import DEFAULT_PIN

try:
    # `make test` runs `unittest discover -s tests`, which puts this directory on sys.path.
    from test_core_banking_fake import EXPECTED_ERRORS, EXPECTED_VERIFICATIONS
except ImportError:
    # `python -m unittest tests.test_core_banking_live` does not, and running one file that way is
    # the ordinary thing to do while iterating.
    from tests.test_core_banking_fake import EXPECTED_ERRORS, EXPECTED_VERIFICATIONS

_STARTUP_TIMEOUT_SECONDS = 20.0

#: How many times a start is attempted, each on its own fresh port. Both shapes of flakiness this
#: test has are per-attempt and independent -- a port stolen between asking and binding, and a
#: startup that misses the deadline because the machine was busy -- so a second attempt clears
#: either one, while a service that genuinely cannot start still fails all three the same way.
#: See `TheStartupRetry` at the foot of this module, and docs/phase4/findings.md.
_STARTUP_ATTEMPTS = 3

#: How much of the spawned service's own output a failed start reports. Its startup errors are the
#: last thing it writes, and the whole file would bury them.
_OUTPUT_TAIL_LINES = 20


def _free_port():
    """Ask the OS for a port nobody is using, rather than hardcoding one that CI might hold.

    The socket is closed before `uvicorn` binds it, which leaves a window another process can take
    it in. That race is why the caller retries rather than why this function is cleverer.
    """
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_until_healthy(start_one, attempts=_STARTUP_ATTEMPTS):
    """Call `start_one` until it answers, and carry every reason if none of them does.

    `start_one` raises `AssertionError` for a start that did not come up and is responsible for
    cleaning up whatever it spawned. Nothing here inspects the reason: a port collision and a
    missed deadline are both retried, because distinguishing them by message text would be a
    guess, and a real failure exhausts the attempts either way.

    **The reasons are kept.** The open finding in docs/phase4/findings.md could not be settled
    because the run's output named nothing; a retry that swallowed its attempts would rebuild that
    same problem one layer down.
    """
    reasons = []
    for attempt in range(1, attempts + 1):
        try:
            return start_one()
        except AssertionError as refused:
            reasons.append(f"attempt {attempt}: {refused}")
    raise AssertionError(
        f"mock-core-banking never became healthy in {attempts} attempts:\n" + "\n".join(reasons)
    )


def _wait_until_healthy(process, base_url, output_path):
    """Poll /health until the service answers, rather than sleeping a guessed interval.

    A fixed sleep is the usual source of flakiness in a test like this: too short on a loaded
    CI box, wasted time everywhere else.
    """
    deadline = time.monotonic() + _STARTUP_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError(
                f"exited during startup with code {process.returncode}"
                f"{_output_tail(output_path)}"
            )
        try:
            if httpx.get(f"{base_url}/health", timeout=0.5).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.05)
    raise AssertionError(
        f"did not become healthy within {_STARTUP_TIMEOUT_SECONDS}s{_output_tail(output_path)}"
    )


def _output_tail(output_path):
    """The end of what the spawned service said, for a start that failed.

    This used to go to `DEVNULL`, which left an exit code and nothing to read it with -- a port
    collision and a broken import both arrive as "exited with code 1".
    """
    try:
        lines = pathlib.Path(output_path).read_text(errors="replace").splitlines()
    except OSError as unreadable:
        return f" (its output could not be read: {unreadable})"
    if not lines:
        return " (it said nothing)"
    return "\n  " + "\n  ".join(lines[-_OUTPUT_TAIL_LINES:])


def _stop(process):
    """Ask the service to stop, and insist if it does not."""
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


class RealNetworkHop(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        # Named here rather than inline below, because B2's artifact scan needs the same path the
        # service is told to write to.
        cls.database_path = os.path.join(cls._tmpdir.name, "core-banking.sqlite3")
        cls.process, cls.port = _start_until_healthy(cls._spawn_on_a_fresh_port)
        cls.base_url = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def _spawn_on_a_fresh_port(cls):
        """One attempt: a port nobody held a moment ago, a process, and a wait for /health."""
        port = _free_port()
        base_url = f"http://127.0.0.1:{port}"
        # Kept rather than discarded, and per-port so one attempt cannot overwrite another's
        # reason. Thrown away with the temporary directory either way.
        output_path = os.path.join(cls._tmpdir.name, f"uvicorn-{port}.log")
        with open(output_path, "wb") as output:
            process = subprocess.Popen(
                [
                    sys.executable, "-m", "uvicorn",
                    "azbank_core_banking.app:build_app", "--factory",
                    "--host", "127.0.0.1", "--port", str(port),
                    "--log-level", "warning",
                ],
                env={
                    **os.environ,
                    # Its own database file, thrown away with the test -- never the default path,
                    # so a test run can never touch whatever a local dev instance is holding.
                    "CORE_BANKING_DB": cls.database_path,
                },
                stdout=output,
                stderr=subprocess.STDOUT,
            )
        try:
            _wait_until_healthy(process, base_url, output_path)
        except AssertionError:
            # This attempt's process never answered, and the next attempt gets its own port. Left
            # running, it would hold whatever it did manage to bind.
            _stop(process)
            raise
        return process, port

    @classmethod
    def tearDownClass(cls):
        _stop(cls.process)
        cls._tmpdir.cleanup()

    async def asyncSetUp(self):
        self.client = HttpCoreBankingClient(base_url=self.base_url)
        self.addAsyncCleanup(self.client.aclose)

    async def test_a_real_call_reads_transfers_and_reads_back(self):
        # One test, one sequence: the whole contract in the order a call would exercise it.
        self.assertEqual(await self.client.list_accounts(), {"chequing": 2400.00, "savings": 500.00})
        self.assertEqual(await self.client.get_balance("chequing"), 2400.00)

        result = await self.client.transfer("chequing", "savings", 150.00)
        self.assertEqual(result.outcome, "completed")
        # What the service moved, which is what the agent then speaks -- not the dollars asked for.
        self.assertEqual(result.moved, 150.00)

        # The read-back is the part that matters: it proves the transfer actually mutated state in
        # another process, over a socket -- not that a dict in this one changed.
        self.assertEqual(await self.client.get_balance("chequing"), 2250.00)
        self.assertEqual(await self.client.get_balance("savings"), 650.00)

        # T-UNKNOWN-ACCT over the real hop: a 404 from the real service, raised by the real client.
        with self.assertRaises(UnknownAccountError):
            await self.client.get_balance("bitcoin")

        # And a decline over the real hop stays a decline -- 200 with the real available amount,
        # not an error, and nothing moves.
        declined = await self.client.transfer("chequing", "savings", 99999.00)
        self.assertEqual(declined.outcome, "declined")
        self.assertEqual(declined.available, 2250.00)
        self.assertEqual(await self.client.get_balance("chequing"), 2250.00)

        # The refusal table the fake is pinned against, driven here against the real thing. Without
        # this the fake's parity tests would be checking it against a constant somebody typed --
        # green forever, including on the day the service starts answering differently. Kept inside
        # this test rather than given its own: issue #30's "exactly one test" is about how many
        # services get spawned, and this spawns none of its own.
        for args, expected in EXPECTED_ERRORS:
            with self.subTest(args=args):
                with self.assertRaises(expected):
                    await self.client.transfer(*args)
        self.assertEqual(await self.client.get_balance("chequing"), 2250.00)

        # An account name that cannot address a resource. The dispatcher was briefly given a rule
        # refusing a name containing "/" as malformed; that was rejected 2026-09-09 -- the system of
        # record decides which names exist -- so these names reach the service, and what it does
        # with them can only be pinned here. Both are percent-encoded on the way out, which is what
        # keeps the first from reaching /health, whose 200 body has no balance in it.
        with self.assertRaises(UnknownAccountError) as caught:
            await self.client.get_balance("../health")
        # A clean 404 the service does not name, so the caller hears the no-name sentence rather
        # than "There's no ../health account on this profile."
        self.assertIsNone(caught.exception.args[0])

        # A trailing slash is the one that costs something: uvicorn decodes %2F before routing, so
        # it arrives as "/accounts/chequing/" and draws a redirect, which is not a result. The
        # caller is told the bank could not be reached for an account that simply does not exist,
        # and the operation counts against the circuit breaker. Asserted rather than merely noted,
        # because it is the accepted price of leaving the decision with the system of record.
        with self.assertRaises(CoreBankingUnavailable):
            await self.client.get_balance("chequing/")

        # Verification over the same real hop, driven off the same shared table the fake is pinned
        # against (issue #35). Without this the fake's parity tests would be checking it against a
        # constant somebody typed -- green forever, including on the day the service starts
        # answering differently. This is Trap 2 from Phase 3, which found fake/real divergences in
        # three separate review rounds.
        for index, (pin, expected) in enumerate(EXPECTED_VERIFICATIONS):
            # By index, never by value: a subTest label is printed on failure, and one of these
            # rows is the demo PIN.
            with self.subTest(case=index):
                if isinstance(expected, type) and issubclass(expected, Exception):
                    with self.assertRaises(expected):
                        await self.client.verify_pin(pin)
                else:
                    self.assertIs(await self.client.verify_pin(pin), expected)

        # Nothing above moved money, and the service is still answering.
        self.assertEqual(await self.client.get_balance("chequing"), 2250.00)

    async def test_the_database_file_holds_no_plaintext_pin(self):
        """B2's artifact scan, on a file a real service really wrote (issues #34 and #39).

        This test controls its own data, so the scan looks for the demo PIN itself rather than for
        any four-digit string a balance might coincidentally contain. It is possible with no
        carve-out precisely because what the service stores is a digest -- a scan that had to skip
        a column would be a scan that could be made to pass by moving the leak into it.

        Ordered after the sequence above by name, and deliberately does its own submissions anyway:
        a scan that only passed because nothing had ever been submitted would prove nothing.
        """
        await self.client.verify_pin(DEFAULT_PIN)
        await self.client.verify_pin("9999")
        database = pathlib.Path(self.database_path)
        self.assertTrue(database.exists(), "the spawned service wrote no database file")
        self.assertNotIn(DEFAULT_PIN.encode(), database.read_bytes())


class TheStartupRetry(unittest.TestCase):
    """The retry loop above, driven against a stub rather than a real service.

    Spawns nothing, which is what keeps it inside issue #30's rule -- that rule counts services
    started, not `TestCase` classes, and this class starts none.

    **Why it exists.** `docs/phase4/findings.md` "Open: one unreproduced test failure" names two
    ordinary shapes of flakiness in the class above, both about spawning a real service on a real
    socket: the free port is closed before `uvicorn` binds it, so another process can take it in
    between, and a loaded machine can miss a fixed startup deadline. Retrying on a fresh port tells
    both of those from a service that genuinely cannot start, which fails every attempt for the
    same reason -- and the reasons are carried into the final message so the difference is
    readable rather than guessed at afterwards.
    """

    def test_a_service_that_answers_is_returned_without_a_second_attempt(self):
        attempts = []

        def start_one():
            attempts.append("started")
            return "the service"

        self.assertEqual(_start_until_healthy(start_one, attempts=3), "the service")
        self.assertEqual(len(attempts), 1, "a healthy start was retried anyway")

    def test_a_port_taken_between_asking_and_binding_is_retried_on_a_fresh_one(self):
        attempts = []

        def start_one():
            attempts.append("started")
            if len(attempts) < 2:
                raise AssertionError("exited during startup with code 1")
            return "the service"

        self.assertEqual(_start_until_healthy(start_one, attempts=3), "the service")
        self.assertEqual(len(attempts), 2)

    def test_a_service_that_never_starts_fails_carrying_every_reason(self):
        """The failure this test can still produce says why, three times over.

        The open finding could not be settled because the run's output named nothing. A retry that
        swallowed its attempts' reasons would rebuild exactly that problem one layer down.
        """
        def start_one():
            raise AssertionError("did not become healthy within 20.0s: Address already in use")

        with self.assertRaises(AssertionError) as refused:
            _start_until_healthy(start_one, attempts=3)

        message = str(refused.exception)
        self.assertIn("3 attempts", message)
        for attempt in (1, 2, 3):
            with self.subTest(attempt=attempt):
                self.assertIn(f"attempt {attempt}", message)
        self.assertIn("Address already in use", message)


if __name__ == "__main__":
    unittest.main()
