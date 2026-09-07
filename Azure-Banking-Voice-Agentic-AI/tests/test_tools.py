"""Tool declaration and dispatch tests.

Split out of the Phase 1 relay's test file by the Phase 2.1 restructure (issue #17), following
the code they cover into dispatch/. Intent unchanged from Phase 1 -- same cases, same assertions.
"""
import json
import unittest

from azbank_voice_agent import accounts
from azbank_voice_agent.dispatch import tools


class DispatchToolCall(unittest.TestCase):
    def setUp(self):
        accounts.ACCOUNTS.clear()
        accounts.ACCOUNTS.update({"chequing": 2400.0, "savings": 500.0})

    def test_get_balance_returns_result(self):
        out = json.loads(tools.dispatch_tool_call("get_balance", '{"account": "chequing"}'))
        self.assertEqual(out, {"result": 2400.0})

    def test_transfer_mutates_and_returns_confirmation(self):
        out = json.loads(tools.dispatch_tool_call(
            "transfer", '{"from_account": "chequing", "to_account": "savings", "amount": 150.0}'
        ))
        self.assertIn("150", out["result"])
        self.assertEqual(accounts.get_balance("chequing"), 2250.0)

    def test_list_accounts_returns_result(self):
        out = json.loads(tools.dispatch_tool_call("list_accounts", "{}"))
        self.assertEqual(out, {"result": {"chequing": 2400.0, "savings": 500.0}})

    def test_unknown_account_comes_back_as_error_not_exception(self):
        out = json.loads(tools.dispatch_tool_call("get_balance", '{"account": "bitcoin"}'))
        self.assertIn("error", out)

    def test_non_positive_amount_comes_back_as_error_not_exception(self):
        out = json.loads(tools.dispatch_tool_call(
            "transfer", '{"from_account": "chequing", "to_account": "savings", "amount": -500.0}'
        ))
        self.assertIn("error", out)

    def test_unknown_tool_name_comes_back_as_error_not_exception(self):
        out = json.loads(tools.dispatch_tool_call("delete_account", "{}"))
        self.assertIn("error", out)

    def test_missing_argument_comes_back_as_error_not_exception(self):
        out = json.loads(tools.dispatch_tool_call("get_balance", "{}"))
        self.assertIn("error", out)


class ToolsMatchDispatch(unittest.TestCase):
    def test_every_declared_tool_is_dispatchable_and_vice_versa(self):
        # TOOLS is what the model sees; _DISPATCH is what actually runs. If they drift, the model
        # calls something that doesn't exist and the call fails mid-conversation.
        declared = {tool["name"] for tool in tools.TOOLS}
        dispatchable = set(tools._DISPATCH)
        self.assertEqual(declared, dispatchable)


if __name__ == "__main__":
    unittest.main()
