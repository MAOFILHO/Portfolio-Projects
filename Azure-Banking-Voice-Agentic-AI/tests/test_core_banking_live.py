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

try:
    # `make test` runs `unittest discover -s tests`, which puts this directory on sys.path.
    from test_core_banking_fake import EXPECTED_ERRORS
except ImportError:
    # `python -m unittest tests.test_core_banking_live` does not, and running one file that way is
    # the ordinary thing to do while iterating.
    from tests.test_core_banking_fake import EXPECTED_ERRORS

_STARTUP_TIMEOUT_SECONDS = 20.0


def _free_port():
    """Ask the OS for a port nobody is using, rather than hardcoding one that CI might hold."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class RealNetworkHop(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls.port = _free_port()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.process = subprocess.Popen(
            [
                sys.executable, "-m", "uvicorn",
                "azbank_core_banking.app:build_app", "--factory",
                "--host", "127.0.0.1", "--port", str(cls.port),
                "--log-level", "warning",
            ],
            env={
                **os.environ,
                # Its own database file, thrown away with the test -- never the default path, so a
                # test run can never touch whatever a local dev instance is holding.
                "CORE_BANKING_DB": os.path.join(cls._tmpdir.name, "core-banking.sqlite3"),
            },
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        cls._wait_until_healthy()

    @classmethod
    def _wait_until_healthy(cls):
        """Poll /health until the service answers, rather than sleeping a guessed interval.

        A fixed sleep is the usual source of flakiness in a test like this: too short on a loaded
        CI box, wasted time everywhere else.
        """
        deadline = time.monotonic() + _STARTUP_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            if cls.process.poll() is not None:
                raise AssertionError(
                    f"mock-core-banking exited during startup with code {cls.process.returncode}"
                )
            try:
                if httpx.get(f"{cls.base_url}/health", timeout=0.5).status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(0.05)
        cls.process.kill()
        raise AssertionError(
            f"mock-core-banking did not become healthy within {_STARTUP_TIMEOUT_SECONDS}s"
        )

    @classmethod
    def tearDownClass(cls):
        cls.process.terminate()
        try:
            cls.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            cls.process.kill()
            cls.process.wait(timeout=10)
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

        # Nothing above moved money, and the service is still answering.
        self.assertEqual(await self.client.get_balance("chequing"), 2250.00)


if __name__ == "__main__":
    unittest.main()
