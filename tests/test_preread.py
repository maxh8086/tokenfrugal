"""Tests for 2B: the router pre-runs the first read of paths named in the task. Written before the code."""
import json
import unittest

from router.loop import named_paths, preread_messages


class NamedPaths(unittest.TestCase):
    def test_extracts_in_order_unique(self):
        t = "Compare /workspace/a.py with /workspace/b.py and /workspace/a.py again."
        self.assertEqual(named_paths(t), ["/workspace/a.py", "/workspace/b.py"])

    def test_strips_trailing_punctuation(self):
        self.assertEqual(named_paths("Read /workspace/x/y.py."), ["/workspace/x/y.py"])
        self.assertEqual(named_paths("(see /workspace/x.md)"), ["/workspace/x.md"])

    def test_capped(self):
        t = " ".join(f"/workspace/f{i}.py" for i in range(6))
        self.assertEqual(len(named_paths(t)), 2)
        self.assertEqual(len(named_paths(t, limit=3)), 3)

    def test_none(self):
        self.assertEqual(named_paths("Summarise the repo"), [])
        self.assertEqual(named_paths(""), [])
        self.assertEqual(named_paths(None), [])


class PrereadMessages(unittest.TestCase):
    def test_pair_shape(self):
        m = preread_messages("/workspace/a.py", "print(1)", 1)
        self.assertEqual(len(m), 2)
        a, t = m
        self.assertEqual(a["role"], "assistant")
        call = a["tool_calls"][0]
        self.assertEqual(call["function"]["name"], "read_file")
        self.assertEqual(json.loads(call["function"]["arguments"]), {"path": "/workspace/a.py"})
        self.assertEqual(t["role"], "tool")
        self.assertEqual(t["tool_call_id"], call["id"])
        self.assertEqual(t["content"], "print(1)")

    def test_ids_unique_per_index(self):
        a = preread_messages("/workspace/a.py", "x", 1)[0]["tool_calls"][0]["id"]
        b = preread_messages("/workspace/a.py", "x", 2)[0]["tool_calls"][0]["id"]
        self.assertNotEqual(a, b)


if __name__ == "__main__":
    unittest.main()
