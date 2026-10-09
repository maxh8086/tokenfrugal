import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

os.environ["GATEWAY_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")

from gateway import store  # noqa: E402
from gateway.config import load_personas, resolve_role  # noqa: E402
from gateway.loop import coerce_args, parse_text_calls, slop_check  # noqa: E402
from gateway.mcp_client import Router, to_openai_tools  # noqa: E402
from gateway.summarize import hard_trim, tokens  # noqa: E402

CFG = load_personas()


class Roles(unittest.TestCase):
    def test_division_default(self):
        self.assertEqual(resolve_role("engineering-backend-architect", CFG)["role"], "builder")

    def test_override_wins(self):
        self.assertEqual(resolve_role("engineering-sre", CFG)["role"], "debugger")

    def test_longest_prefix(self):
        self.assertEqual(resolve_role("game-development-unity", CFG)["role"], "builder")

    def test_unknown_defaults_builder(self):
        self.assertEqual(resolve_role("zzz-unknown", CFG)["role"], "builder")

    def test_only_two_models_and_tool_cap(self):
        self.assertEqual(set(CFG["models"].values()), {"qwen2.5-coder-yarn:3b", "llama3.2:3b-16k"})
        for name, r in CFG["roles"].items():
            self.assertLessEqual(len(r["tools"]), 6, name)
            self.assertIn(r["model"], CFG["models"], name)

    def test_division_and_override_roles_exist(self):
        for v in list(CFG["divisions"].values()) + list(CFG["overrides"].values()):
            self.assertIn(v, CFG["roles"])


class Catalogue(unittest.TestCase):
    """Every agency-agents slug (tests/agent_slugs.txt) must map explicitly, not via the builder fallback."""

    def test_every_slug_has_explicit_mapping(self):
        slugs = (Path(__file__).parent / "agent_slugs.txt").read_text().split()
        self.assertGreaterEqual(len(slugs), 282)
        members = {s for v in CFG["members"].values() for s in v}
        unmapped = [s for s in slugs if s not in members and s not in CFG["overrides"]
                    and not any(s.startswith(d + "-") for d in CFG["divisions"])]
        self.assertEqual(unmapped, [])
        for s in slugs:
            self.assertIn(resolve_role(s, CFG)["role"], CFG["roles"])

    def test_non_prefixed_resolve(self):
        self.assertEqual(resolve_role("godot-shader-developer", CFG)["role"], "builder")
        self.assertEqual(resolve_role("zk-steward", CFG)["role"], "docs")
        self.assertEqual(resolve_role("security-penetration-tester", CFG)["role"], "security")


class Summary(unittest.TestCase):
    def test_hard_trim_caps(self):
        self.assertLessEqual(tokens(hard_trim("word. " * 1000)), 300)

    def test_short_untouched(self):
        self.assertEqual(hard_trim("ok"), "ok")


class Slop(unittest.TestCase):
    def test_empty(self):
        self.assertIsNotNone(slop_check("  "))

    def test_tool_call_as_text(self):
        self.assertIn("tool call", slop_check('{"name": "read_file", "arguments": {}}'))

    def test_filler(self):
        self.assertIsNotNone(slop_check("As an AI I cannot"))

    def test_ok(self):
        self.assertIsNone(slop_check("Found 3 issues in a.py"))


class TextCalls(unittest.TestCase):
    N = {"edit_file", "read_file"}
    FENCE = "`" * 3 + "json" + chr(10) + '{"name": "edit_file", "arguments": {"path": "/a"}}' + chr(10) + "`" * 3

    def test_fenced_call_is_slop(self):
        self.assertIn("tool call", slop_check(self.FENCE))

    def test_fenced_call_parsed(self):
        self.assertEqual([x.function.name for x in parse_text_calls(self.FENCE, self.N)], ["edit_file"])

    def test_missing_closing_brace_repaired(self):
        c = parse_text_calls('{"name": "edit_file", "arguments": {"path": "/a", "edits": [{"oldText": "x"}]}', self.N)
        self.assertEqual(len(c), 1)

    def test_unknown_tool_ignored(self):
        self.assertEqual(parse_text_calls('{"name": "rm", "arguments": {}}', self.N), [])


class Store(unittest.TestCase):
    def test_roundtrip(self):
        tid = store.create("a", "builder", "p")
        store.update(tid, status="done", messages=[{"role": "user", "content": "x"}])
        t = store.get(tid)
        self.assertEqual(t["status"], "done")
        self.assertEqual(t["messages"][0]["content"], "x")
        self.assertIsNone(store.get("nope"))


class Tools(unittest.TestCase):
    def test_allowlist_and_project_hidden(self):
        t = SimpleNamespace(name="search_graph", description="d", input_schema={
            "type": "object", "properties": {"project": {}, "q": {}}, "required": ["project", "q"]})
        u = SimpleNamespace(name="other", description="", input_schema={})
        out = to_openai_tools([t, u], ["search_graph"])
        self.assertEqual(len(out), 1)
        p = out[0]["function"]["parameters"]
        self.assertNotIn("project", p["properties"])
        self.assertEqual(p["required"], ["q"])

    def test_router_injects_project(self):
        calls = []

        class S:
            async def list_tools(self):
                return SimpleNamespace(tools=[SimpleNamespace(
                    name="search_graph", input_schema={"properties": {"project": {}}})])

            async def call_tool(self, n, a):
                calls.append(a)

        import asyncio
        s = S()
        r = Router([s], {s})

        async def go():
            await r.list_tools()
            await r.call_tool("search_graph", {"q": 1})
        asyncio.run(go())
        self.assertIn("project", calls[0])

class SynaptreeProject(unittest.TestCase):
    def test_project_defaults_to_checkout_folder_name(self):
        from gateway import config
        if not os.getenv('SYNAPTREE_PROJECT'):
            self.assertEqual(config.SYNAPTREE_PROJECT, Path(config.__file__).resolve().parent.parent.name)
        self.assertIn('synaptree', config.NATIVE_SERVERS)


if __name__ == "__main__":
    unittest.main()


class TextCalls(unittest.TestCase):
    def test_parse(self):
        from gateway.loop import parse_text_calls
        c = parse_text_calls('<tool_call>{"name": "read_file", "arguments": {"path": "a"}}</tool_call>', {"read_file"})
        self.assertEqual(c[0].function.name, "read_file")
        self.assertEqual(parse_text_calls('{"name": "nope", "arguments": {}}', {"read_file"}), [])


class SavedTokensTest(unittest.TestCase):
    def test_saved_is_work_minus_summary_and_never_negative(self):
        from gateway.summarize import saved_tokens
        msgs = [{"role": "user", "content": "x" * 400}, {"role": "tool", "content": "y" * 4000}]
        self.assertEqual(saved_tokens(msgs, "z" * 40), 1100 - 10)
        self.assertEqual(saved_tokens([], "z" * 40), 0)
        self.assertEqual(saved_tokens([{"content": None}], "z" * 400), 0)


class Coerce(unittest.TestCase):
    SCHEMA = {"properties": {"pageId": {"type": "integer"}, "verbose": {"type": "boolean"},
                             "ratio": {"type": "number"}, "url": {"type": "string"}}}

    def test_strings_become_typed(self):
        out = coerce_args({"pageId": "1", "verbose": "false", "ratio": "0.5", "url": "x"}, self.SCHEMA)
        self.assertEqual(out, {"pageId": 1, "verbose": False, "ratio": 0.5, "url": "x"})

    def test_bad_values_left_alone(self):
        self.assertEqual(coerce_args({"pageId": "abc", "other": "1"}, self.SCHEMA), {"pageId": "abc", "other": "1"})


class Lint(unittest.TestCase):
    def test_missing_import_flagged(self):
        from gateway.lint import check_python
        self.assertIn("re", check_python("def f(s):\n    return re.sub('a', 'b', s)\n"))

    def test_valid_code_clean(self):
        from gateway.lint import check_python
        self.assertIsNone(check_python("import re\n\n\ndef f(s, *a):\n    try:\n        return [x for x in re.findall('a', s)]\n    except ValueError as e:\n        return e\n"))

    def test_syntax_error(self):
        from gateway.lint import check_python
        self.assertIn("syntax error", check_python("def f(:\n"))

    def test_star_import_skipped(self):
        from gateway.lint import check_python
        self.assertIsNone(check_python("from os.path import *\njoin('a')\n"))


class Refusal(unittest.TestCase):
    def test_refusal_is_slop(self):
        self.assertIsNotNone(slop_check("I'm sorry, but I'm not able to assist with that request."))
