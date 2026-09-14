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
import logging
import os
import tempfile
import unittest

from azbank_core_banking import db
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
        # The same invariant as test_db.py's, asserted over HTTP: the body must agree with a
        # re-read. See db.transfer for why a self-transfer is the input that tells it apart.
        client = self.client()
        response = client.post("/transfers", json={
            "from_account": "chequing", "to_account": "chequing", "amount_cents": 15000,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["from_balance_cents"], 240000)
        self.assertEqual(client.get("/accounts/chequing").json()["balance_cents"], 240000)


class CredentialChecks(ServiceCase):
    """Creating a credential check: 200 with an outcome, whichever way the answer goes (issue #34).

    A **rejected credential** is deliberately not a 4xx. It is a working system saying no -- the
    same standing a **declined** transfer already has -- and a 4xx would file it alongside
    **unknown account**, which is a different thing entirely.
    """

    def test_the_right_pin_is_accepted_with_200(self):
        response = self.client().post("/credential-checks", json={"pin": db.DEMO_PIN})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"outcome": "accepted"})

    def test_a_wrong_pin_is_rejected_with_200(self):
        response = self.client().post("/credential-checks", json={"pin": "9999"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"outcome": "rejected"})

    def test_a_rejection_says_nothing_beyond_the_outcome(self):
        # No attempt count, no hint about length, no echo of what was sent. The caller hears that
        # it was wrong and nothing more, for the same reason a refusal explains nothing -- and
        # anything extra here would be a probing oracle handed out over HTTP.
        body = self.client().post("/credential-checks", json={"pin": "9999"}).json()
        self.assertEqual(list(body), ["outcome"])

    def test_a_malformed_check_is_a_422_with_the_field_named(self):
        for body in ({}, {"pin": "123"}, {"pin": "12345"}, {"pin": "abcd"}, {"pin": 1234}):
            with self.subTest(shape=sorted(body)):
                response = self.client().post("/credential-checks", json=body)
                self.assertEqual(response.status_code, 422)
                self.assertEqual(
                    response.json(), {"error": "malformed_request", "fields": ["body.pin"]}
                )

    def test_the_submitted_value_never_comes_back_in_a_response(self):
        """B2 at this service's only outward-facing surface.

        The 422 is the case that bites: FastAPI's own validation body carries an `input` field
        holding the value that failed, so the default handler would answer a malformed PIN by
        quoting it. The handler that strips pydantic's prose is what keeps it out, which makes that
        handler load-bearing for B2 rather than merely tidy.
        """
        submitted = "5678"
        for body in ({"pin": submitted}, {"pin": submitted + "9"}, {"pin": submitted[:3]}):
            with self.subTest(length=len(body["pin"])):
                response = self.client().post("/credential-checks", json=body)
                self.assertNotIn(submitted[:3], response.text)

    def test_the_service_logs_no_digit_of_a_submitted_pin(self):
        # The service's own loggers, for the whole request cycle. B2's run-wide capture lives in
        # the voice agent's suite; this is the same claim made where this service can break it
        # alone, since a shared-nothing deployable's suite has to stand up without that one.
        # The malformed submission carries its own distinctive value, because the 422 is the path
        # that can leak one: the framework's validation error holds the input that failed, so a
        # handler or a logger that renders that error renders the PIN with it.
        malformed = "56789"
        with self.assertLogs(level="DEBUG") as captured:
            logging.getLogger("mock-core-banking-test").info("a record, so assertLogs has one")
            client = self.client()
            client.post("/credential-checks", json={"pin": db.DEMO_PIN})
            client.post("/credential-checks", json={"pin": "9999"})
            client.post("/credential-checks", json={"pin": malformed})
        for record in captured.records:
            with self.subTest(logger=record.name):
                for secret in (db.DEMO_PIN, malformed):
                    self.assertNotIn(secret, record.getMessage())
                    self.assertNotIn(secret, repr(record.args))


class MoneyRoutesAreUnchanged(ServiceCase):
    """Issue #34 asks for the money routes and their bodies to be untouched by the credential work.

    Asserted rather than assumed: the transfer route and the credential route now share a request
    model shape and an exception handler, so a change to one has a path to the other.
    """

    def test_the_account_and_transfer_bodies_are_what_they_were(self):
        client = self.client()
        self.assertEqual(
            client.get("/accounts").json(),
            {"accounts": [
                {"name": "chequing", "balance_cents": 240000},
                {"name": "savings", "balance_cents": 50000},
            ]},
        )
        self.assertEqual(
            client.post("/transfers", json={
                "from_account": "chequing", "to_account": "savings", "amount_cents": 15000,
            }).json(),
            {
                "outcome": "completed", "from_balance_cents": 225000,
                "to_balance_cents": 65000, "moved_cents": 15000,
            },
        )

    def test_a_credential_check_moves_no_money(self):
        client = self.client()
        client.post("/credential-checks", json={"pin": db.DEMO_PIN})
        client.post("/credential-checks", json={"pin": "9999"})
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
            client.get("/accounts/bitcoin"),                     # 404
            client.post("/transfers", json={
                "from_account": "chequing", "to_account": "savings", "amount_cents": 15000,
            }),
            client.post("/transfers", json={
                "from_account": "chequing", "to_account": "savings", "amount_cents": 900000,
            }),
            # 422s. The status this list used to skip -- and the only one that was leaking:
            # FastAPI's default validation body is pydantic's English ("Input should be greater
            # than 0"), which is a caller-facing sentence sitting in the system of record's own
            # response (/code-review, 2026-09-09, spec axis, against #26's criterion 8).
            client.post("/transfers", json={
                "from_account": "chequing", "to_account": "savings", "amount_cents": 0,
            }),
            client.post("/transfers", json={"from_account": "chequing"}),
            client.post("/transfers", json={
                "from_account": "chequing", "to_account": "savings", "amount_cents": "lots",
            }),
            # The credential route, all three of its shapes (issue #34 criterion 6). Its outcomes
            # are snake_case tokens like every other outcome this service returns.
            client.post("/credential-checks", json={"pin": db.DEMO_PIN}),
            client.post("/credential-checks", json={"pin": "9999"}),
            client.post("/credential-checks", json={"pin": "abcd"}),   # 422
            # The history route (issue #44). Its `kind` and `counterparty` are tokens for the same
            # reason every outcome here is one: the sentence a caller hears about a transaction is
            # composed in the voice agent. A `description` column would have put prose back in the
            # system of record through a route nobody was watching.
            client.get("/accounts/chequing/transactions"),
            client.get("/accounts/bitcoin/transactions"),             # 404
            # The block route (issue #45), all three of its shapes. Both its outcomes are
            # snake_case tokens; the sentence a caller hears about a card is the voice agent's.
            client.post("/card-blocks", json={"idempotency_key": "block_aaaaaaaa"}),
            client.post("/card-blocks", json={"idempotency_key": "block_bbbbbbbb"}),
            client.post("/card-blocks", json={"idempotency_key": "nope"}),   # 422
        ]
        for response in responses:
            with self.subTest(url=str(response.url), status=response.status_code):
                self._assert_no_prose(response.json())

    def test_a_malformed_request_is_still_a_422_with_the_fields_named(self):
        # Structured, not silent: the fields are what a log needs to diagnose our own bug, and a
        # field name is a token rather than prose.
        response = self.client().post("/transfers", json={
            "from_account": "chequing", "to_account": "savings", "amount_cents": 0,
        })
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json(), {
            "error": "malformed_request", "fields": ["body.amount_cents"],
        })


if __name__ == "__main__":
    unittest.main()


class TransactionsRoute(ServiceCase):
    """The history route (issue #44). Same status mapping as the balance route, no new branch.

        unknown account    -> 404, naming the account
        no transactions    -> 200, empty list
        found              -> 200, bounded, newest first
    """

    def test_a_fresh_service_has_a_seeded_history(self):
        response = self.client().get("/accounts/chequing/transactions")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["transactions"])

    def test_an_unknown_account_is_404_naming_the_account(self):
        response = self.client().get("/accounts/bitcoin/transactions")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"]["account"], "bitcoin")

    def test_an_account_with_no_history_is_200_and_empty(self):
        """Not a 404 and not an error: "nothing has happened yet" is a normal answer.

        Both seeded accounts have a seeded history, so this needs an account that genuinely has
        none -- which means a database this test arranges rather than the shared in-memory one.
        An earlier version asserted only that the body was a list, which is a test whose name
        outran what it checked.
        """
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        directory = stack.enter_context(tempfile.TemporaryDirectory())
        path = os.path.join(directory, "core-banking.sqlite3")
        with contextlib.closing(db.connect(path)) as conn:
            conn.execute("INSERT INTO accounts (name, balance_cents) VALUES ('tfsa', 0)")
            conn.commit()
        client = stack.enter_context(TestClient(build_app(database=path)))

        response = client.get("/accounts/tfsa/transactions")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["transactions"], [])

    def test_a_transfer_shows_up_on_both_accounts(self):
        client = self.client()
        client.post("/transfers", json={
            "from_account": "chequing", "to_account": "savings", "amount_cents": 15000,
        })
        debit = client.get("/accounts/chequing/transactions").json()["transactions"][0]
        credit = client.get("/accounts/savings/transactions").json()["transactions"][0]
        self.assertEqual(debit["amount_cents"], -15000)
        self.assertEqual(debit["counterparty"], "savings")
        self.assertEqual(credit["amount_cents"], 15000)
        self.assertEqual(credit["counterparty"], "chequing")

    def test_the_route_is_bounded_and_takes_no_limit_from_the_caller(self):
        """The bound is the service's. A `limit` the caller could raise would not be a bound.

        Asserted by asking for more and getting the service's number anyway -- FastAPI ignores an
        unknown query parameter, so a route that later grew one would fail this rather than
        silently start honouring it.
        """
        client = self.client()
        for _ in range(db.TRANSACTION_LIST_LIMIT + 4):
            client.post("/transfers", json={
                "from_account": "chequing", "to_account": "savings", "amount_cents": 100,
            })
        body = client.get("/accounts/chequing/transactions?limit=500").json()
        self.assertEqual(len(body["transactions"]), db.TRANSACTION_LIST_LIMIT)

    def test_the_route_is_newest_first(self):
        client = self.client()
        client.post("/transfers", json={
            "from_account": "chequing", "to_account": "savings", "amount_cents": 111,
        })
        newest = client.get("/accounts/chequing/transactions").json()["transactions"][0]
        self.assertEqual(newest["amount_cents"], -111)

    def test_a_declined_transfer_adds_no_line(self):
        client = self.client()
        before = client.get("/accounts/chequing/transactions").json()["transactions"]
        client.post("/transfers", json={
            "from_account": "chequing", "to_account": "savings", "amount_cents": 900000,
        })
        after = client.get("/accounts/chequing/transactions").json()["transactions"]
        self.assertEqual(before, after)

    def test_every_amount_on_the_wire_is_integer_cents(self):
        body = self.client().get("/accounts/chequing/transactions").json()
        for transaction in body["transactions"]:
            self.assertIsInstance(transaction["amount_cents"], int)


class CardBlockRoute(ServiceCase):
    """Creating a card block (issue #45). `200` for both outcomes; neither is an error.

        blocked          -> 200   this request is what stopped the card
        already_blocked  -> 200   a working system saying it was already stopped
        malformed key    -> 422   the caller has a bug

    `already_blocked` is deliberately not a `409`. Nobody has been refused anything and the request
    was not malformed -- it is the same standing a declined transfer has, and a `4xx` would file it
    alongside unknown-account.
    """

    KEY = "block_aaaaaaaa"
    OTHER_KEY = "block_bbbbbbbb"

    def test_a_first_block_is_200_and_blocked(self):
        response = self.client().post("/card-blocks", json={"idempotency_key": self.KEY})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"outcome": db.BLOCKED})

    def test_a_replayed_key_is_200_and_the_same_outcome(self):
        client = self.client()
        client.post("/card-blocks", json={"idempotency_key": self.KEY})
        response = client.post("/card-blocks", json={"idempotency_key": self.KEY})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"outcome": db.BLOCKED})

    def test_a_fresh_key_against_a_blocked_card_is_already_blocked(self):
        client = self.client()
        client.post("/card-blocks", json={"idempotency_key": self.KEY})
        response = client.post("/card-blocks", json={"idempotency_key": self.OTHER_KEY})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"outcome": db.ALREADY_BLOCKED})

    def test_a_missing_or_malformed_key_is_a_422_with_the_field_named(self):
        for body in ({}, {"idempotency_key": ""}, {"idempotency_key": "short"},
                     {"idempotency_key": "has spaces in it"}, {"idempotency_key": 1234},
                     {"idempotency_key": "x" * 65}):
            with self.subTest(shape=sorted(body)):
                response = self.client().post("/card-blocks", json=body)
                self.assertEqual(response.status_code, 422)
                self.assertEqual(
                    response.json(),
                    {"error": "malformed_request", "fields": ["body.idempotency_key"]},
                )

    def test_a_malformed_request_blocks_nothing(self):
        client = self.client()
        client.post("/card-blocks", json={"idempotency_key": ""})
        # The card is still active, proved the only way the product offers: by blocking it and
        # getting `blocked` rather than `already_blocked`.
        response = client.post("/card-blocks", json={"idempotency_key": self.KEY})
        self.assertEqual(response.json()["outcome"], db.BLOCKED)

    def test_there_is_no_unblock_route_and_no_status_route(self):
        """Nothing reverses a block, and nothing reports card status.

        Asserted as "does not succeed" rather than as a specific code: `DELETE /card-blocks`
        answers `405` because the path exists for `POST`, while an unknown path answers `404`.
        Pinning either number would be pinning FastAPI's routing table rather than the property,
        which is that none of these does anything.
        """
        client = self.client()
        for method, path in (("post", "/card-unblocks"), ("delete", "/card-blocks"),
                             ("get", "/card"), ("get", "/cards")):
            with self.subTest(route=f"{method} {path}"):
                self.assertGreaterEqual(getattr(client, method)(path).status_code, 400)

    def test_blocking_a_card_moves_no_money(self):
        client = self.client()
        client.post("/card-blocks", json={"idempotency_key": self.KEY})
        self.assertEqual(
            client.get("/accounts").json(),
            {"accounts": [
                {"name": "chequing", "balance_cents": 240000},
                {"name": "savings", "balance_cents": 50000},
            ]},
        )

    def test_blocking_a_card_writes_no_transaction(self):
        # A block is not money moving, so it has no place in an account's history.
        client = self.client()
        before = client.get("/accounts/chequing/transactions").json()["transactions"]
        client.post("/card-blocks", json={"idempotency_key": self.KEY})
        after = client.get("/accounts/chequing/transactions").json()["transactions"]
        self.assertEqual(before, after)
