"""The HTTP contract: REST-resource routes and the status mapping the client depends on.

The status mapping is load-bearing (issue #25, #26) and is the reason these tests assert on codes
as carefully as on bodies:

    unknown account            -> 404   (client raises; T-UNKNOWN-ACCT)
    declined (business rule)   -> 200   (a normal outcome of a working system, not an error)
    malformed request          -> 422   (a bug in the caller, not a decline)

Mapping a decline to 4xx would put it in the same bucket as unknown-account and blur
T-UNKNOWN-ACCT -- which is exactly what these tests exist to prevent regressing.
"""
import contextlib
import unittest

from azbank_core_banking.app import build_app
from fastapi.testclient import TestClient


class ServiceCase(unittest.TestCase):
    """Base for anything needing a running service.

    `client()` enters the TestClient as a context manager, which is what actually runs the app's
    lifespan -- and therefore what closes the database connection on teardown. Without entering it,
    every test leaks a connection and the suite emits ResourceWarnings.
    """

    def client(self):
        """A TestClient over a fresh in-memory database -- no file, no shared state."""
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        return stack.enter_context(TestClient(build_app(database=":memory:")))


class Health(ServiceCase):
    def test_health_is_ok(self):
        self.assertEqual(self.client().get("/health").status_code, 200)


class Accounts(ServiceCase):
    def test_list_accounts(self):
        response = self.client().get("/accounts")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"accounts": [
                {"name": "chequing", "balance_cents": 240000},
                {"name": "savings", "balance_cents": 50000},
            ]},
        )

    def test_get_one_account(self):
        response = self.client().get("/accounts/chequing")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"name": "chequing", "balance_cents": 240000})

    def test_unknown_account_is_404(self):
        self.assertEqual(self.client().get("/accounts/bitcoin").status_code, 404)


class Transfers(ServiceCase):
    def test_completed_transfer_is_200(self):
        client = self.client()
        response = client.post("/transfers", json={
            "from_account": "chequing", "to_account": "savings", "amount_cents": 15000,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["outcome"], "completed")
        self.assertEqual(response.json()["from_balance_cents"], 225000)

    def test_declined_transfer_is_200_with_the_real_available_amount(self):
        response = self.client().post("/transfers", json={
            "from_account": "chequing", "to_account": "savings", "amount_cents": 300000,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "outcome": "declined", "reason": "insufficient_funds", "available_cents": 240000,
        })

    def test_declined_transfer_mutates_nothing(self):
        client = self.client()
        client.post("/transfers", json={
            "from_account": "chequing", "to_account": "savings", "amount_cents": 300000,
        })
        self.assertEqual(client.get("/accounts/chequing").json()["balance_cents"], 240000)

    def test_unknown_account_in_a_transfer_is_404(self):
        response = self.client().post("/transfers", json={
            "from_account": "bitcoin", "to_account": "savings", "amount_cents": 100,
        })
        self.assertEqual(response.status_code, 404)

    def test_non_positive_amount_is_rejected_as_malformed(self):
        response = self.client().post("/transfers", json={
            "from_account": "chequing", "to_account": "savings", "amount_cents": 0,
        })
        self.assertEqual(response.status_code, 422)

    def test_a_transfer_reports_the_balance_the_service_actually_holds(self):
        # Over HTTP, on the input that tells reported-from-storage apart from reported-from-
        # arithmetic: a self-transfer nets to zero, so the body must say 240000 and agree with a
        # re-read. Reporting `available - amount_cents` said 225000 here, and the voice agent read
        # that to the caller as fact (/code-review, 2026-09-08).
        client = self.client()
        response = client.post("/transfers", json={
            "from_account": "chequing", "to_account": "chequing", "amount_cents": 15000,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["from_balance_cents"], 240000)
        self.assertEqual(client.get("/accounts/chequing").json()["balance_cents"], 240000)


class NoCallerFacingProse(ServiceCase):
    """The service returns data and outcome codes -- never a sentence.

    All caller-facing phrasing lives in the voice agent (issue #25). This is asserted
    mechanically rather than trusted, because the module this service replaces got it wrong:
    `accounts.transfer()` returned a ready-made apology sentence from what was, in effect, the
    system of record. Reason codes are snake_case tokens and account names are single words, so
    a space in any string value means prose has leaked back in.
    """

    def _assert_no_prose(self, value):
        if isinstance(value, str):
            self.assertNotIn(" ", value, f"caller-facing prose leaked into a response: {value!r}")
        elif isinstance(value, dict):
            for item in value.values():
                self._assert_no_prose(item)
        elif isinstance(value, list):
            for item in value:
                self._assert_no_prose(item)

    def test_no_response_body_contains_a_sentence(self):
        client = self.client()
        responses = [
            client.get("/accounts"),
            client.get("/accounts/chequing"),
            client.post("/transfers", json={
                "from_account": "chequing", "to_account": "savings", "amount_cents": 15000,
            }),
            client.post("/transfers", json={
                "from_account": "chequing", "to_account": "savings", "amount_cents": 900000,
            }),
        ]
        for response in responses:
            self._assert_no_prose(response.json())


if __name__ == "__main__":
    unittest.main()
