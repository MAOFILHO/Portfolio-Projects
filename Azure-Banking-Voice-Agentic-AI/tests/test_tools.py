"""Tool declaration and dispatch tests.

Split out of the Phase 1 relay's test file by the Phase 2.1 restructure (issue #17). Repointed at
the injected core-banking client by Phase 3 (issue #28) -- the cases that were about an in-memory
dict are now about what the dispatcher does with each of CONTEXT.md's outcomes.

The gate is patched open throughout so these cases don't depend on B1 policy (empty until Phase 4;
see tests/test_gate.py for the gate itself).
"""
import json
import unittest
from unittest.mock import patch

from azbank_voice_agent.core_banking import CoreBankingUnavailable, UnknownAccountError
from azbank_voice_agent.core_banking.fake import FakeCoreBankingClient
from azbank_voice_agent.dispatch import gate, tools


class DispatchCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.core_banking = FakeCoreBankingClient()
        self._gate_patcher = patch.object(gate, "is_allowed", return_value=True)
        self._gate_patcher.start()
        self.addCleanup(self._gate_patcher.stop)

    async def dispatch(self, name, arguments_json):
        return json.loads(await tools.dispatch_tool_call(
            name, arguments_json, core_banking=self.core_banking
        ))


class DispatchToolCall(DispatchCase):
    async def test_get_balance_returns_result(self):
        self.assertEqual(await self.dispatch("get_balance", '{"account": "chequing"}'),
                         {"result": 2400.0})

    async def test_transfer_mutates_and_returns_confirmation(self):
        out = await self.dispatch(
            "transfer", '{"from_account": "chequing", "to_account": "savings", "amount": 150.0}'
        )
        self.assertIn("150", out["result"])
        self.assertEqual(self.core_banking.accounts["chequing"], 2250.0)

    async def test_list_accounts_returns_result(self):
        self.assertEqual(await self.dispatch("list_accounts", "{}"),
                         {"result": {"chequing": 2400.0, "savings": 500.0}})

    async def test_unknown_tool_name_comes_back_as_error_not_exception(self):
        self.assertIn("error", await self.dispatch("delete_account", "{}"))

    async def test_missing_argument_comes_back_as_error_not_exception(self):
        self.assertIn("error", await self.dispatch("get_balance", "{}"))

    async def test_non_positive_amount_comes_back_as_error_not_exception(self):
        out = await self.dispatch(
            "transfer", '{"from_account": "chequing", "to_account": "savings", "amount": -500.0}'
        )
        self.assertIn("error", out)

    async def test_the_spoken_balance_is_the_one_core_banking_holds(self):
        # The no-fabrication rule where the caller actually hears it (CLAUDE.md's silent-fallback
        # exclusion): the spoken figure must be the one the backend holds. See db.transfer for why
        # a self-transfer is the input that tells that apart from a computed one.
        out = await self.dispatch(
            "transfer", '{"from_account": "chequing", "to_account": "chequing", "amount": 150.0}'
        )
        self.assertIn(f"${self.core_banking.accounts['chequing']:.2f}", out["result"])
        self.assertEqual(self.core_banking.accounts["chequing"], 2400.0)

    async def test_a_malformed_request_never_speaks_the_services_own_wording(self):
        # The service answers a bad amount with a 422 and the client's message for it is
        # "core banking rejected the request with 422" -- diagnostic text for a log, which was
        # reaching the caller verbatim (/code-review, 2026-09-08).
        out = await self.dispatch(
            "transfer", '{"from_account": "chequing", "to_account": "savings", "amount": -500.0}'
        )
        self.assertEqual(out, {"error": tools.MALFORMED})
        for internal in ("422", "core banking", "rejected"):
            self.assertNotIn(internal, out["error"])


class TheOutcomesStayDistinct(DispatchCase):
    """CONTEXT.md's unknown-account, declined and unavailable outcomes, at the dispatcher. Each
    gets its own spoken answer -- the whole reason Phase 3 stopped collapsing them into one error
    shape. Malformed, the fourth, is covered above in DispatchToolCall."""

    async def test_unknown_account_names_the_account_and_does_not_claim_a_failure(self):
        out = await self.dispatch("get_balance", '{"account": "bitcoin"}')
        # The EXACT sentence, not a substring. This assertion used to be
        # `assertIn("bitcoin", out["error"])`, which passed happily while the caller was actually
        # being told "There's no http://core-banking.internal:8001/accounts/bitcoin account on
        # this profile." -- the URL contains the account name, so the substring check could not
        # tell the two apart (/code-review, 2026-09-08).
        self.assertEqual(out, {"error": "There's no bitcoin account on this profile."})

    async def test_an_unknown_account_the_service_did_not_name_still_reads_as_a_sentence(self):
        # The client returns None when the service's 404 carries no account name. The fallback has
        # to be a sentence, not "There's no None account on this profile."
        self.core_banking.fail_with = UnknownAccountError()
        out = await self.dispatch("get_balance", '{"account": "bitcoin"}')
        self.assertEqual(out, {"error": "I can't find that account on this profile."})

    async def test_declined_transfer_states_the_real_available_amount(self):
        out = await self.dispatch(
            "transfer", '{"from_account": "chequing", "to_account": "savings", "amount": 3000.0}'
        )
        # A decline is a normal outcome, so it comes back as a result the agent speaks -- not an
        # error, and carrying what the caller *can* do.
        self.assertIn("2400.00", out["result"])
        self.assertEqual(self.core_banking.accounts["chequing"], 2400.0)  # nothing moved

    async def test_unavailable_backend_produces_no_figure_at_all(self):
        # CLAUDE.md's silent-fallback exclusion, at the dispatcher: an unreachable backend must
        # never be answered with a remembered, cached, or defaulted balance.
        self.core_banking.fail_with = CoreBankingUnavailable("down")
        out = await self.dispatch("get_balance", '{"account": "chequing"}')
        self.assertEqual(out, {"error": tools.UNAVAILABLE})
        self.assertNotIn("2400", out["error"])

    async def test_unavailable_is_distinguishable_from_unknown_account(self):
        unknown = await self.dispatch("get_balance", '{"account": "bitcoin"}')
        self.core_banking.fail_with = CoreBankingUnavailable("down")
        unavailable = await self.dispatch("get_balance", '{"account": "chequing"}')
        self.assertNotEqual(unknown["error"], unavailable["error"])

    async def test_an_unavailable_backend_is_logged(self):
        self.core_banking.fail_with = CoreBankingUnavailable("down")
        with self.assertLogs("dispatch", level="WARNING") as cm:
            await self.dispatch("get_balance", '{"account": "chequing"}')
        self.assertTrue(any("unavailable" in line for line in cm.output))


class TheDispatcherIsAsync(unittest.TestCase):
    def test_dispatch_tool_call_is_a_coroutine_function(self):
        # Issue #28: the relay awaits this. If it ever goes back to being synchronous, a network
        # call inside it would block the audio event loop for the client's whole timeout budget.
        import inspect
        self.assertTrue(inspect.iscoroutinefunction(tools.dispatch_tool_call))

    def test_core_banking_has_no_default(self):
        # Keyword-only and required: forgetting it is a TypeError at the call site, not a None
        # that fails somewhere later. Same fail-closed reasoning as the agent/auth_state defaults,
        # which deliberately default to the *least* privileged values.
        import inspect
        parameter = inspect.signature(tools.dispatch_tool_call).parameters["core_banking"]
        self.assertIs(parameter.default, inspect.Parameter.empty)
        self.assertIs(parameter.kind, inspect.Parameter.KEYWORD_ONLY)


class ToolsMatchDispatch(unittest.TestCase):
    def test_every_declared_tool_is_dispatchable_and_vice_versa(self):
        # TOOLS is what the model sees; _DISPATCH is what actually runs. If they drift, the model
        # calls something that doesn't exist and the call fails mid-conversation.
        declared = {tool["name"] for tool in tools.TOOLS}
        self.assertEqual(declared, set(tools._DISPATCH))

    def test_no_tool_schema_enumerates_account_names(self):
        # Issue #28: the system of record decides which accounts exist, not the tool schema. An
        # enum here would put a second, staler copy of that answer in front of the model -- and it
        # is what made Phase 1's "unknown account" behaviour a matter of the model reasoning about
        # a schema rather than the service answering.
        for tool in tools.TOOLS:
            for parameter in tool["parameters"]["properties"].values():
                with self.subTest(tool=tool["name"]):
                    self.assertNotIn("enum", parameter)

    def test_no_tool_schema_names_an_account_in_prose_either(self):
        # Dropping the enum but leaving "e.g. chequing or savings" in the description puts the same
        # stale answer back in front of the model in prose form (/code-review, 2026-09-08). The
        # seeded account names are the ones that would drift, so they are the ones asserted on.
        schema = json.dumps(tools.TOOLS).lower()
        for account in ("chequing", "savings"):
            with self.subTest(account=account):
                self.assertNotIn(account, schema)


if __name__ == "__main__":
    unittest.main()
