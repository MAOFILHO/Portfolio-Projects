import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "voice-agent"))

import accounts  # noqa: E402
import bridge  # noqa: E402


class DispatchToolCall(unittest.TestCase):
    def setUp(self):
        accounts.ACCOUNTS.clear()
        accounts.ACCOUNTS.update({"chequing": 2400.0, "savings": 500.0})

    def test_get_balance_returns_result(self):
        out = json.loads(bridge.dispatch_tool_call("get_balance", '{"account": "chequing"}'))
        self.assertEqual(out, {"result": 2400.0})

    def test_transfer_mutates_and_returns_confirmation(self):
        out = json.loads(bridge.dispatch_tool_call(
            "transfer", '{"from_account": "chequing", "to_account": "savings", "amount": 150.0}'
        ))
        self.assertIn("150", out["result"])
        self.assertEqual(accounts.get_balance("chequing"), 2250.0)

    def test_list_accounts_returns_result(self):
        out = json.loads(bridge.dispatch_tool_call("list_accounts", "{}"))
        self.assertEqual(out, {"result": {"chequing": 2400.0, "savings": 500.0}})

    def test_unknown_account_comes_back_as_error_not_exception(self):
        out = json.loads(bridge.dispatch_tool_call("get_balance", '{"account": "bitcoin"}'))
        self.assertIn("error", out)

    def test_non_positive_amount_comes_back_as_error_not_exception(self):
        out = json.loads(bridge.dispatch_tool_call(
            "transfer", '{"from_account": "chequing", "to_account": "savings", "amount": -500.0}'
        ))
        self.assertIn("error", out)

    def test_unknown_tool_name_comes_back_as_error_not_exception(self):
        out = json.loads(bridge.dispatch_tool_call("delete_account", "{}"))
        self.assertIn("error", out)

    def test_missing_argument_comes_back_as_error_not_exception(self):
        out = json.loads(bridge.dispatch_tool_call("get_balance", "{}"))
        self.assertIn("error", out)


class ToolsMatchDispatch(unittest.TestCase):
    def test_every_declared_tool_is_dispatchable_and_vice_versa(self):
        # TOOLS is what the model sees; _DISPATCH is what actually runs. If they drift, the model
        # calls something that doesn't exist and the call fails mid-conversation.
        declared = {tool["name"] for tool in bridge.TOOLS}
        dispatchable = set(bridge._DISPATCH)
        self.assertEqual(declared, dispatchable)
