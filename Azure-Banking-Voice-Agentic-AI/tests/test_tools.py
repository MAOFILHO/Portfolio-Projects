"""Tool declaration and dispatch tests.

Split out of the Phase 1 relay's test file by the Phase 2.1 restructure (issue #17). Repointed at
the injected core-banking client by Phase 3 (issue #28) -- the cases that were about an in-memory
dict are now about what the dispatcher does with each of CONTEXT.md's outcomes.

The gate is patched open throughout so these cases don't depend on B1 policy (empty until Phase 4;
see tests/test_gate.py for the gate itself).
"""
import dataclasses
import json
import typing
import unittest
from unittest.mock import patch

from azbank_voice_agent.call_records.fake import FakeCallRecordStore
from azbank_voice_agent.core_banking import CoreBankingUnavailable, Transaction, UnknownAccountError
from azbank_voice_agent.core_banking.fake import FakeCoreBankingClient
from azbank_voice_agent.dispatch import gate, tools


class DispatchCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.core_banking = FakeCoreBankingClient()
        self.call_records = FakeCallRecordStore()
        self.scope = tools.CallScope(
            core_banking=self.core_banking,
            call_records=self.call_records,
            idempotency_key="idem_aaaaaaaa",
            correlation_id="corr-test",
        )
        self._gate_patcher = patch.object(gate, "is_allowed", return_value=True)
        self._gate_patcher.start()
        self.addCleanup(self._gate_patcher.stop)

    async def dispatch(self, name, arguments_json):
        return json.loads(await tools.dispatch_tool_call(
            name, arguments_json, scope=self.scope
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


class ATimedOutTransferIsAnUnknownOutcome(DispatchCase):
    """"I can't check that" is the whole truth for a read, and a false claim for a transfer.

    A `transfer` that raises unavailable may already have committed at the service -- that is the
    entire reason `client.py` never retries it. Telling the caller the bank could not be reached
    asserts that nothing happened, and a caller who believes that retries, which is the
    double-spend the no-retry rule exists to prevent. Issue #25 user story 6 and #27: "a timed-out
    transfer is reported as an unknown outcome" (/code-review, 2026-09-09, spec axis).
    """

    async def test_a_transfer_does_not_claim_that_nothing_happened(self):
        self.core_banking.fail_with = CoreBankingUnavailable("timed out")
        out = await self.dispatch(
            "transfer", '{"from_account": "chequing", "to_account": "savings", "amount": 150.0}'
        )
        self.assertEqual(out, {"error": tools.TRANSFER_UNCONFIRMED})
        self.assertNotEqual(out["error"], tools.UNAVAILABLE)

    async def test_a_read_still_says_plainly_that_it_could_not_check(self):
        self.core_banking.fail_with = CoreBankingUnavailable("timed out")
        out = await self.dispatch("get_balance", '{"account": "chequing"}')
        self.assertEqual(out, {"error": tools.UNAVAILABLE})

    async def test_neither_sentence_carries_a_figure(self):
        # CLAUDE.md's silent-fallback exclusion holds for both: an unreachable backend is never
        # answered with a remembered, cached or defaulted number.
        for sentence in (tools.UNAVAILABLE, tools.TRANSFER_UNCONFIRMED):
            with self.subTest(sentence=sentence):
                self.assertFalse(any(character.isdigit() for character in sentence))


class ArgumentsTheModelCanActuallyEmit(DispatchCase):
    """The model writes these arguments, not a type checker.

    `arguments_json` is whatever the model emitted, and the schema in TOOLS is a request, not a
    guarantee: a `"number"` field arrives as the string "100" often enough to be ordinary, and
    `true`, `null` and an object all fit through the same hole. Every one of them used to end
    somewhere it should not (probe, 2026-09-09): a string or null amount raised TypeError straight
    out of `dispatch_tool_call` -- which its own docstring says never raises -- and killed the call
    from `run_call`; `true` silently moved a dollar; an unparseable payload spoke the JSON parser's
    own message to the caller.
    """

    async def dispatch_raw(self, name, arguments_json):
        # Not json.loads()'d: these cases are about what comes back, including when it comes back
        # from a payload that is not JSON at all.
        return json.loads(await tools.dispatch_tool_call(
            name, arguments_json, scope=self.scope
        ))

    async def test_a_string_amount_is_refused_and_moves_no_money(self):
        out = await self.dispatch_raw(
            "transfer", '{"from_account": "chequing", "to_account": "savings", "amount": "100"}'
        )
        self.assertEqual(out, {"error": tools.MALFORMED})
        self.assertEqual(self.core_banking.accounts["chequing"], 2400.0)

    async def test_a_boolean_amount_moves_no_money(self):
        # `True * 100 == 100`, so this completed a $1.00 transfer and told the caller "Done".
        # db.py rejects a bool at the system of record; the conversion in to_cents turned it into a
        # perfectly ordinary 100 cents before that guard could ever see it.
        out = await self.dispatch_raw(
            "transfer", '{"from_account": "chequing", "to_account": "savings", "amount": true}'
        )
        self.assertEqual(out, {"error": tools.MALFORMED})
        self.assertEqual(self.core_banking.accounts["chequing"], 2400.0)

    async def test_a_null_amount_is_refused(self):
        out = await self.dispatch_raw(
            "transfer", '{"from_account": "chequing", "to_account": "savings", "amount": null}'
        )
        self.assertEqual(out, {"error": tools.MALFORMED})

    async def test_a_non_finite_amount_is_refused(self):
        # json.loads accepts NaN and Infinity, so the model can put either on this path.
        for literal in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(amount=literal):
                out = await self.dispatch_raw(
                    "transfer",
                    '{"from_account": "chequing", "to_account": "savings", "amount": ' + literal + '}',
                )
                self.assertEqual(out, {"error": tools.MALFORMED})

    async def test_an_account_that_is_not_a_string_is_refused(self):
        for literal in ("123", '{"name": "chequing"}', "null", "true", "[]"):
            with self.subTest(account=literal):
                out = await self.dispatch_raw("get_balance", '{"account": ' + literal + '}')
                self.assertEqual(out, {"error": tools.MALFORMED})

    async def test_an_empty_account_name_is_refused(self):
        # It names no account and addresses no resource. Against the real service it produced a
        # redirect whose empty body then became a spoken JSON parser error.
        for literal in ('""', '"   "'):
            with self.subTest(account=literal):
                out = await self.dispatch_raw("get_balance", '{"account": ' + literal + '}')
                self.assertEqual(out, {"error": tools.MALFORMED})

    # A name that cannot address a resource -- "../health", a trailing slash -- is deliberately
    # *not* asserted here. The dispatcher passes such names to the system of record (the slash rule
    # was considered and rejected 2026-09-09), and what comes back depends on a URL and an HTTP
    # status that this fake has neither of: it answers both from a dict lookup. Pinned in
    # tests/test_core_banking_live.py, against the real service, where the answer is real.

    async def test_an_unparseable_arguments_payload_is_refused(self):
        out = await self.dispatch_raw("get_balance", "not json at all")
        self.assertEqual(out, {"error": tools.MALFORMED})

    async def test_no_refusal_ever_speaks_an_internal_message(self):
        # The general form of /code-review's finding 3 and of this round's own: whatever goes wrong
        # with a tool call, what the caller hears is composed here. The exception's own text is for
        # the log.
        internal = ("Expecting value", "__round__", "balance_cents", "NoneType", "unsupported "
                    "operand", "unhashable", "float NaN", "'account'")
        cases = [
            ("get_balance", "not json at all"),
            ("get_balance", "{}"),
            ("get_balance", '{"account": null}'),
            ("get_balance", '{"account": {"name": "chequing"}}'),
            ("transfer", '{"from_account": "chequing", "to_account": "savings", "amount": "100"}'),
            ("transfer", '{"from_account": "chequing", "to_account": "savings", "amount": NaN}'),
            ("delete_account", "{}"),
        ]
        for name, arguments in cases:
            with self.subTest(tool=name, arguments=arguments):
                out = await self.dispatch_raw(name, arguments)
                for phrase in internal:
                    self.assertNotIn(phrase, out["error"])

    async def test_the_spoken_amount_is_the_one_that_moved(self):
        # Not the one that was asked for. The two part company at the half cent, in both
        # directions: 2.675 dollars is 268 cents once rounded to whole cents, and "%.2f" of the
        # request says $2.67 (probe, 2026-09-09). Same rule as the balance figure -- what the
        # caller hears is what the system did, not what the model typed.
        before = self.core_banking.accounts["savings"]
        out = await self.dispatch_raw(
            "transfer", '{"from_account": "chequing", "to_account": "savings", "amount": 2.675}'
        )
        self.assertIn("$2.68", out["result"])
        self.assertNotIn("$2.67", out["result"])
        self.assertEqual(round(self.core_banking.accounts["savings"] - before, 2), 2.68)

    async def test_a_refused_tool_call_is_logged_with_its_diagnosis(self):
        # The detail does not vanish -- it moves to the log, which is the half of finding 3 that
        # makes the composed sentence acceptable rather than merely quieter.
        with self.assertLogs("dispatch", level="WARNING") as cm:
            await self.dispatch_raw(
                "transfer", '{"from_account": "chequing", "to_account": "savings", "amount": "100"}'
            )
        self.assertTrue(any("transfer" in line for line in cm.output))


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
        # `scope` since issue #48 -- the call-scoped collaborators became an object once there
        # were four of them rather than one. The rule it is pinned for is unchanged: forgetting it
        # is a TypeError at the call site, not a None that fails somewhere later.
        parameter = inspect.signature(tools.dispatch_tool_call).parameters["scope"]
        self.assertIs(parameter.default, inspect.Parameter.empty)
        self.assertIs(parameter.kind, inspect.Parameter.KEYWORD_ONLY)


class TheDefaultsAreTheLeastPrivilegedOnes(unittest.IsolatedAsyncioTestCase):
    """B1. The docstring has always claimed both defaults are least-privileged; the agent one was
    not (/code-review, 2026-09-11).

    `BANKING_AGENT` is the row granting all five banking tools. It was harmless only because the
    *paired* default was `ANONYMOUS`, which grants nothing to anybody -- so the claim held by
    coincidence of the pair rather than by either value being least-privileged. A caller that
    passed an auth_state and forgot the agent got the most privileged identity in the table, which
    is the fail-open direction on the one constraint whose whole point is failing closed.

    The gate is **not** patched open here, unlike `DispatchCase` -- the refusal is the assertion.
    """

    def setUp(self):
        self.core_banking = FakeCoreBankingClient()
        self.scope = tools.CallScope(
            core_banking=self.core_banking,
            call_records=FakeCallRecordStore(),
            idempotency_key="idem_aaaaaaaa",
            correlation_id="corr-test",
        )

    async def test_omitting_the_agent_refuses_a_banking_tool_even_when_authenticated(self):
        # The exact latent case: auth_state supplied, agent forgotten. Under the old default this
        # returned a real balance read off the system of record.
        answer = json.loads(await tools.dispatch_tool_call(
            "get_balance", '{"account": "chequing"}',
            auth_state=gate.AUTHENTICATED, scope=self.scope,
        ))
        self.assertEqual(answer, {"error": gate.REFUSAL})

    async def test_the_default_agent_is_least_privileged_in_every_auth_state(self):
        """The default agent grants no more than any other agent would, in any auth state.

        **This assertion replaces one that did not fail when the fix was reverted**
        (/code-review, 2026-09-11). The first version compared the default row's grants to the
        smallest row's *by value* -- and `(banking, anonymous)` and `(triage, anonymous)` are both
        exactly `{escalate_to_human}`, so it passed happily with `BANKING_AGENT` restored. It
        tested the pair that was already innocent and never looked at the authenticated row, which
        is the one where the two agents differ and the only place the defect could bite.

        Quantifying over every auth state is what closes that. `BANKING_AGENT` fails it on
        `AUTHENTICATED`, where it grants all five banking tools and `TRIAGE_AGENT` grants one.
        Still read off the table rather than restating it, so it survives the table moving -- the
        anonymous corollary already moved once this phase.
        """
        import inspect
        default_agent = inspect.signature(tools.dispatch_tool_call).parameters["agent"].default
        agents = {agent for agent, _ in gate.PERMISSIONS}
        auth_states = {auth_state for _, auth_state in gate.PERMISSIONS}

        # Indexing `PERMISSIONS` for every pair also asserts the table is total. A missing row
        # raises `KeyError` here rather than quietly narrowing what this test covers -- loud, and
        # deliberate, because the previous version could not have noticed one (/code-review,
        # 2026-09-11).
        for auth_state in auth_states:
            mine = gate.PERMISSIONS[(default_agent, auth_state)]
            for other in agents:
                with self.subTest(auth_state=auth_state, other=other):
                    self.assertLessEqual(
                        mine, gate.PERMISSIONS[(other, auth_state)],
                        f"default agent {default_agent!r} grants more than {other!r} "
                        f"when {auth_state!r}: {sorted(mine - gate.PERMISSIONS[(other, auth_state)])}",
                    )

    async def test_the_default_auth_state_is_the_unauthenticated_one(self):
        """The other half of the pair, which briefly had no test at all.

        The assertion this class replaced read both defaults; the replacement read only `agent`,
        so for one commit nothing anywhere pinned `auth_state=ANONYMOUS` -- while this class's own
        docstring went on claiming both were covered. Strengthening one half by dropping the other
        is not strengthening (/code-review, 2026-09-11).

        Stated as identity rather than as a permission comparison on purpose: `ANONYMOUS` is not
        merely the least-granting state, it is the state a call *starts* in and the one B1's whole
        definition is written against. A future table where some other state granted less must not
        silently become the default.
        """
        import inspect
        default = inspect.signature(tools.dispatch_tool_call).parameters["auth_state"].default
        self.assertEqual(default, gate.ANONYMOUS)


class ToolsMatchDispatch(unittest.TestCase):
    def test_every_declared_tool_is_dispatchable_and_vice_versa(self):
        # TOOLS is what the model sees; _DISPATCH is what actually runs. If they drift, the model
        # calls something that doesn't exist and the call fails mid-conversation.
        declared = {tool["name"] for tool in tools.TOOLS}
        self.assertEqual(declared, set(tools._DISPATCH))

    #: Parameters whose value set genuinely is fixed, named one by one. `escalate_to_human`'s reason
    #: is a fixed set by design (docs/PLAN.md decision 17): the record exists so somebody can query
    #: it, and a reason the model phrased its own way is not queryable. Listed by `(tool, parameter)`
    #: rather than skipped by type, so a future account parameter cannot join the exemption by
    #: accident.
    ENUMERATED_ON_PURPOSE: typing.ClassVar = {("escalate_to_human", "reason")}

    def test_no_tool_schema_enumerates_account_names(self):
        # Issue #28: the system of record decides which accounts exist, not the tool schema. An
        # enum here would put a second, staler copy of that answer in front of the model -- and it
        # is what made Phase 1's "unknown account" behaviour a matter of the model reasoning about
        # a schema rather than the service answering.
        for tool in tools.TOOLS:
            for name, parameter in tool["parameters"]["properties"].items():
                if (tool["name"], name) in self.ENUMERATED_ON_PURPOSE:
                    continue
                with self.subTest(tool=tool["name"], parameter=name):
                    self.assertNotIn("enum", parameter)

    def test_the_only_enumerated_parameter_is_the_one_that_is_meant_to_be(self):
        # The other direction: an enum appearing anywhere else turns the test above red, and this
        # turns red if the exemption above outlives the parameter it was written for.
        enumerated = {
            (tool["name"], name)
            for tool in tools.TOOLS
            for name, parameter in tool["parameters"]["properties"].items()
            if "enum" in parameter
        }
        self.assertEqual(enumerated, self.ENUMERATED_ON_PURPOSE)

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


class ListingTransactionsAtTheDispatcher(DispatchCase):
    """What the caller is told about their history, and what they are never told (issue #46).

    The sentence lives here rather than at the whole-call seam because the fake's `fail_with` is
    whole-client: arranging an outage there would fail the PIN check too, and the call would never
    reach an authenticated state to be refused from. The whole-call seam proves the tool is
    genuinely in the path; this proves what each outcome says.
    """

    async def test_a_history_comes_back_as_data_not_a_sentence(self):
        result = (await self.dispatch("list_transactions", '{"account": "chequing"}'))["result"]
        self.assertIsInstance(result, list)
        self.assertEqual(
            sorted(result[0]), ["amount", "counterparty", "kind", "occurred_at"]
        )

    async def test_an_unreachable_service_carries_no_figure_of_any_kind(self):
        # CLAUDE.md's silent-fallback exclusion, applied to the newest read: never a remembered,
        # cached or defaulted history, and never a partial one.
        self.core_banking.fail_with = CoreBankingUnavailable("down")
        answer = await self.dispatch("list_transactions", '{"account": "chequing"}')
        self.assertEqual(answer, {"error": tools.UNAVAILABLE})

    async def test_it_gets_the_read_sentence_and_not_the_transfer_one(self):
        # TRANSFER_UNCONFIRMED exists because a timed-out write may already have committed. A read
        # that did not happen simply did not happen, and telling a caller to go and check their
        # balance after a failed history lookup would be nonsense.
        self.core_banking.fail_with = CoreBankingUnavailable("down")
        answer = await self.dispatch("list_transactions", '{"account": "chequing"}')
        self.assertNotEqual(answer["error"], tools.TRANSFER_UNCONFIRMED)

    async def test_an_unknown_account_names_the_account(self):
        answer = await self.dispatch("list_transactions", '{"account": "bitcoin"}')
        self.assertEqual(answer, {"error": "There's no bitcoin account on this profile."})

    async def test_an_account_name_that_is_not_a_name_is_malformed(self):
        for arguments in ('{"account": null}', '{"account": ""}', '{"account": 7}',
                          '{"account": {"$ne": null}}', "{}"):
            with self.subTest(arguments=arguments):
                answer = await self.dispatch("list_transactions", arguments)
                self.assertEqual(answer, {"error": tools.MALFORMED})

    async def test_a_field_added_to_the_record_reaches_the_model_without_a_second_list(self):
        """`dataclasses.asdict`, not a hand-written dict.

        Asserted by comparing what the model receives against the record's own fields, so a field
        added to `Transaction` and forgotten here fails rather than silently never arriving.
        """
        result = (await self.dispatch("list_transactions", '{"account": "chequing"}'))["result"]
        expected = [f.name for f in dataclasses.fields(Transaction)]
        self.assertEqual(sorted(result[0]), sorted(expected))


class EscalationHandlesAMissingStore(unittest.IsolatedAsyncioTestCase):
    """A `CallScope` with no `call_records` at all -- distinct from one whose store raises.

    `call_records` is `None`-able on `CallScope` (its own docstring: "a missing client matters to
    four" tools). Reaching for `.record_escalation` on `None` is an `AttributeError`, and
    `dispatch_tool_call`'s except clauses do not name it -- so before this fix it escaped the
    "never raises" contract and dropped the call on the one tool anonymous callers are told to
    reach for when everything else has failed.

    Never live in production, where `app.py` always builds a real store before either `run_call` or
    `run_closed_call` is entered -- caught reading this file cold (/code-review, 2026-09-12), the
    same way the `BANKING_AGENT` default was: harmless only because nothing legitimate reaches the
    gap, not because the gap wasn't there.
    """

    def setUp(self):
        self.core_banking = FakeCoreBankingClient()
        self.scope = tools.CallScope(core_banking=self.core_banking, call_records=None)
        self._gate_patcher = patch.object(gate, "is_allowed", return_value=True)
        self._gate_patcher.start()
        self.addCleanup(self._gate_patcher.stop)

    async def dispatch(self):
        return await tools.dispatch_tool_call(
            "escalate_to_human", json.dumps({"reason": "not_understood"}), scope=self.scope,
        )

    async def test_dispatch_tool_call_does_not_raise(self):
        # The assertion is that this line completes at all. Before the fix it raised AttributeError,
        # which is not one of dispatch_tool_call's declared exceptions -- so this test failing means
        # a raise made it out of an `await`, not an assertion below not matching.
        await self.dispatch()

    async def test_the_caller_is_still_escalated(self):
        answer = json.loads(await self.dispatch())
        self.assertEqual(answer, {"result": tools.ESCALATED})

    async def test_the_missing_store_is_logged_loudly(self):
        with self.assertLogs("dispatch", level="ERROR") as cm:
            await self.dispatch()
        self.assertTrue(any("escalation record NOT written" in line for line in cm.output))
