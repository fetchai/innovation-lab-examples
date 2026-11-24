"""Offline tests: stub transport, no network.

Run:  python -m pytest tests/ -q
"""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import ValidationError

from battle_training_tools import BattleTrainingClient, build_tools, flatten_result
from battle_training_tools.tools import (
    CreateBotArgs,
    ListMatchesArgs,
    ScrimmageArgs,
    SetPayoutWalletArgs,
    UploadVersionArgs,
)


class StubTransport:
    """Records calls and returns canned MCP results."""

    def __init__(self):
        self.calls = []

    def __call__(self, method, params):
        self.calls.append((method, params))
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({"ok": True, "tool": params["name"]}),
                }
            ]
        }


def make_tools(key=None):
    stub = StubTransport()
    client = BattleTrainingClient(key=key, transport=stub)
    return {t.name: t for t in build_tools(client)}, stub


class TestCatalog(unittest.TestCase):
    def test_all_21_tools_present(self):
        tools, _ = make_tools()
        self.assertEqual(len(tools), 21)
        for expected in (
            "battle_training_get_ladder",
            "battle_training_upload_version",
            "battle_training_scrimmage",
        ):
            self.assertIn(expected, tools)


class TestForwarding(unittest.TestCase):
    def test_read_tool_forwards_validated_args(self):
        tools, stub = make_tools()
        out = tools["battle_training_list_matches"].invoke(
            {"bot": "cobalt-vanguard", "limit": 5}
        )
        self.assertIn('"ok":true', out)
        method, params = stub.calls[-1]
        self.assertEqual(method, "tools/call")
        self.assertEqual(
            params,
            {
                "name": "list_matches",
                "arguments": {"bot": "cobalt-vanguard", "limit": 5},
            },
        )

    def test_none_args_are_omitted(self):
        tools, stub = make_tools()
        tools["battle_training_get_rules"].invoke({})
        _, params = stub.calls[-1]
        self.assertEqual(params["arguments"], {})

    def test_key_is_never_a_tool_argument(self):
        tools, stub = make_tools(key="secret-key")
        tools["battle_training_create_bot"].invoke({"name": "cobalt-vanguard"})
        _, params = stub.calls[-1]
        self.assertNotIn("key", params["arguments"])
        self.assertNotIn("secret-key", json.dumps(params))


class TestValidation(unittest.TestCase):
    def test_theater_enum(self):
        with self.assertRaises(ValidationError):
            ListMatchesArgs(bot="x")  # sanity: valid model elsewhere
            from battle_training_tools.tools import ControllerApiArgs

            ControllerApiArgs(theater="space")

    def test_limit_bounds(self):
        with self.assertRaises(ValidationError):
            ListMatchesArgs(limit=0)
        with self.assertRaises(ValidationError):
            ListMatchesArgs(limit=201)
        with self.assertRaises(ValidationError):
            ListMatchesArgs(limit=1.5)

    def test_create_bot_name_length(self):
        with self.assertRaises(ValidationError):
            CreateBotArgs(name="ab")
        with self.assertRaises(ValidationError):
            CreateBotArgs(name="x" * 33)
        self.assertEqual(CreateBotArgs(name="cobalt-vanguard").name, "cobalt-vanguard")

    def test_upload_version_caps(self):
        with self.assertRaises(ValidationError):
            UploadVersionArgs(bot="b", label="v" * 33, source="x")
        with self.assertRaises(ValidationError):
            UploadVersionArgs(bot="b", label="v1", source="")
        with self.assertRaises(ValidationError):
            UploadVersionArgs(bot="b", label="v1", source="x", notes="n" * 501)

    def test_payout_wallet_pattern(self):
        good = "0x" + "a1" * 20
        self.assertEqual(SetPayoutWalletArgs(address=good).address, good)
        self.assertIsNone(SetPayoutWalletArgs(address=None).address)
        with self.assertRaises(ValidationError):
            SetPayoutWalletArgs(address="0x1234")
        with self.assertRaises(ValidationError):
            SetPayoutWalletArgs(address="a1" * 20)

    def test_scrimmage_seed_pool_exclusive(self):
        with self.assertRaises(ValidationError):
            ScrimmageArgs(
                bot="b", vs="house:random", seed=7, pool="bench-public", index=1
            )

    def test_scrimmage_pool_needs_index(self):
        with self.assertRaises(ValidationError):
            ScrimmageArgs(bot="b", vs="R1", pool="bench-public")
        ok = ScrimmageArgs(bot="b", vs="R1", pool="bench-public", index=3)
        self.assertEqual(ok.index, 3)

    def test_scrimmage_seed_range(self):
        with self.assertRaises(ValidationError):
            ScrimmageArgs(bot="b", vs="house:random", seed=4294967296)
        with self.assertRaises(ValidationError):
            ScrimmageArgs(bot="b", vs="house:random", seed=-1)

    def test_extra_args_forbidden(self):
        with self.assertRaises(ValidationError):
            ListMatchesArgs(limit=5, bogus=True)


class TestKeyGuard(unittest.TestCase):
    def test_write_tool_without_key_fails_locally(self):
        tools, stub = make_tools(key=None)
        with self.assertRaises(Exception) as ctx:
            tools["battle_training_create_bot"].invoke({"name": "cobalt-vanguard"})
        self.assertIn("account key", str(ctx.exception))
        self.assertEqual(stub.calls, [])  # nothing was forwarded

    def test_read_tool_without_key_works(self):
        tools, _ = make_tools(key=None)
        out = tools["battle_training_get_ladder"].invoke({})
        self.assertIn('"ok":true', out)


class TestFlatten(unittest.TestCase):
    def test_json_text_block_is_compacted(self):
        result = {"content": [{"type": "text", "text": '{ "a": 1 }'}]}
        self.assertEqual(flatten_result(result), '{"a":1}')

    def test_plain_text_passes_through(self):
        result = {"content": [{"type": "text", "text": "hello"}]}
        self.assertEqual(flatten_result(result), "hello")

    def test_error_flag_prefixes(self):
        result = {"content": [{"type": "text", "text": "boom"}], "isError": True}
        self.assertEqual(flatten_result(result), "ERROR: boom")


if __name__ == "__main__":
    unittest.main()
