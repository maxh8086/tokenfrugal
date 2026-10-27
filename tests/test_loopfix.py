"""Tests for the fix-first loop changes (handoff.md, "Fix-first plan"). Written before the code."""
import json
import unittest

from router.loop import first_call_hint, infra_error, parse_text_calls, think_extra, wrapup_due

N = {"read_file", "write_file"}


class SalvageParser(unittest.TestCase):
    def test_function_tag_format(self):
        raw = "<tool_call>\n<function=read_file>\n<parameter=path>\n/workspace/a.py\n</parameter>\n</function>\n</tool_call>"
        c = parse_text_calls(raw, N)
        self.assertEqual(len(c), 1)
        self.assertEqual(c[0].function.name, "read_file")
        self.assertEqual(json.loads(c[0].function.arguments), {"path": "/workspace/a.py"})

    def test_function_tag_multi_param(self):
        raw = "<tool_call><function=write_file><parameter=path>/w/x</parameter><parameter=content>hi\nthere</parameter></function></tool_call>"
        a = json.loads(parse_text_calls(raw, N)[0].function.arguments)
        self.assertEqual(a, {"path": "/w/x", "content": "hi\nthere"})

    def test_function_tag_unknown_tool_ignored(self):
        self.assertEqual(parse_text_calls("<tool_call><function=rm><parameter=path>/x</parameter></function></tool_call>", N), [])

    def test_json_still_works(self):
        c = parse_text_calls('{"name": "read_file", "arguments": {"path": "/a"}}', N)
        self.assertEqual([x.function.name for x in c], ["read_file"])

    def test_plain_prose_is_not_a_call(self):
        self.assertEqual(parse_text_calls("The function read_file reads a file.", N), [])


class FirstCallHint(unittest.TestCase):
    def test_names_path_and_tool(self):
        h = first_call_hint("Fix the bug in /workspace/app/util.py please", N)
        self.assertIn("read_file", h)
        self.assertIn("/workspace/app/util.py", h)

    def test_no_path_no_hint_but_names_tool(self):
        h = first_call_hint("Summarise the repo", N)
        self.assertIn("read_file", h)

    def test_no_read_tool(self):
        self.assertIsNone(first_call_hint("do it /workspace/a.py", {"write_file"}))


class WrapUp(unittest.TestCase):
    def test_due_at_70_percent(self):
        self.assertFalse(wrapup_due(6, 10, 3))
        self.assertTrue(wrapup_due(7, 10, 3))
        self.assertTrue(wrapup_due(9, 10, 1))

    def test_not_due_without_results_or_on_last_step(self):
        self.assertFalse(wrapup_due(8, 10, 0))
        self.assertFalse(wrapup_due(10, 10, 3))  # force_answer owns the last step


class InfraError(unittest.TestCase):
    def test_500(self):
        self.assertTrue(infra_error(Exception("Error code: 500 - InternalServerError: model runner stopped")))
        self.assertTrue(infra_error(Exception("llama runner process has terminated")))

    def test_other(self):
        self.assertFalse(infra_error(Exception("Error code: 400 - does not support tools")))
        self.assertFalse(infra_error(Exception("temperature unsupported")))


class ThinkExtra(unittest.TestCase):
    def test_off_for_thinking_role(self):
        self.assertEqual(think_extra({"thinking": True}), {"extra_body": {"think": False}})

    def test_empty_otherwise(self):
        self.assertEqual(think_extra({}), {})


if __name__ == "__main__":
    unittest.main()
