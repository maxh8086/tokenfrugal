import json
import unittest

from gateway.loop import parse_text_calls, text_tool_prompt, text_view

TOOLS = [{"type": "function", "function": {"name": "read_file", "description": "Read a file",
                                           "parameters": {"properties": {"path": {"type": "string"}}}}}]


class TextToolTests(unittest.TestCase):
    def test_prompt_lists_tools_with_types(self):
        p = text_tool_prompt(TOOLS)
        self.assertIn("read_file(path: string)", p)
        self.assertIn('"name": "read_file"', p)

    def test_prompt_has_one_shot_write_example(self):
        p = text_tool_prompt(TOOLS)
        self.assertIn("One-shot example", p)
        self.assertIn('"name": "write_file"', p)
        self.assertIn("edit_file", p)

    def test_write_file_with_raw_newline_in_content_parses(self):
        raw = '{"name": "write_file", "arguments": {"path": "/workspace/a.py", "content": "x = 1\n\ny = 2\n"}}'
        calls = parse_text_calls(raw, {"write_file"})
        self.assertEqual(len(calls), 1)
        self.assertEqual(json.loads(calls[0].function.arguments)["content"], "x = 1\n\ny = 2\n")

    def test_view_converts_calls_and_results(self):
        msgs = [{"role": "user", "content": "go"},
                {"role": "assistant", "content": "", "tool_calls": [
                    {"id": "1", "type": "function", "function": {"name": "read_file", "arguments": '{"path": "/workspace/a"}'}}]},
                {"role": "tool", "tool_call_id": "1", "content": "hello"}]
        v = text_view(msgs)
        self.assertEqual([m["role"] for m in v], ["user", "assistant", "user"])
        self.assertEqual(json.loads(v[1]["content"]), {"name": "read_file", "arguments": {"path": "/workspace/a"}})
        self.assertTrue(v[2]["content"].endswith("hello"))
        calls = parse_text_calls(v[1]["content"], {"read_file"})
        self.assertEqual(calls[0].function.name, "read_file")

    def test_repairs_missing_closers_and_ignores_unknown_tools(self):
        c = parse_text_calls('{"name": "read_file", "arguments": {"path": "/workspace/a"}', {"read_file"})
        self.assertEqual(json.loads(c[0].function.arguments), {"path": "/workspace/a"})
        self.assertEqual(parse_text_calls('{"name": "nope", "arguments": {}}', {"read_file"}), [])


if __name__ == "__main__":
    unittest.main()
