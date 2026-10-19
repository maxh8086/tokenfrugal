import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import haiku_run as h


def resp(content, tin=10, tout=5):
    return {"content": content, "usage": {"input_tokens": tin, "output_tokens": tout}}


class HaikuRun(unittest.TestCase):
    def test_tool_loop_sums_tokens_and_returns_text(self):
        seq = iter([resp([{"type": "tool_use", "id": "1", "name": "read_file", "input": {"path": "x"}}]),
                    resp([{"type": "text", "text": "done"}])])
        seen = []
        text, tin, tout, steps = h.run_case("t", lambda p: next(seq), lambda n, a: seen.append(n) or "ok")
        self.assertEqual((text, tin, tout, steps, seen), ("done", 20, 10, 2, ["read_file"]))

    def test_step_limit(self):
        use = resp([{"type": "tool_use", "id": "1", "name": "list_directory", "input": {"path": "."}}])
        *_, steps = h.run_case("t", lambda p: use, lambda n, a: "x")
        self.assertEqual(steps, h.MAX_STEPS)

    def test_file_tools(self):
        d = Path(tempfile.mkdtemp()) / "f.txt"
        self.assertEqual(h.run_tool("write_file", {"path": str(d), "content": "a b"}), "ok")
        self.assertEqual(h.run_tool("edit_file", {"path": str(d), "old": "a", "new": "z"}), "ok")
        self.assertEqual(h.run_tool("read_file", {"path": str(d)}), "z b")
        self.assertTrue(h.run_tool("edit_file", {"path": str(d), "old": "q", "new": "r"}).startswith("error"))

    def test_unavailable_case_is_na_without_calls(self):
        call = mock.Mock()
        case = ("role_tracker", "a", mock.Mock(), "t", mock.Mock())
        self.assertEqual(h.one(case, call)["status"], "n/a")
        call.assert_not_called()

    def test_one_scores_with_check(self):
        case = ("c", "a", lambda: None, "t", lambda ans: (ans == "yes", "n"))
        r = h.one(case, lambda p: resp([{"type": "text", "text": "yes"}]))
        self.assertEqual((r["verified"], r["status"]), (1, "ok"))

    def test_one_cleans_scratch_before_setup(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(h.b, "SCRATCH", Path(d)):
            (Path(d) / "stale.py").write_text("x")
            seen = []
            case = ("c", "a", lambda: seen.append(sorted(p.name for p in Path(d).iterdir())), "t",
                    lambda ans: (True, ""))
            h.one(case, lambda p: resp([{"type": "text", "text": "ok"}]))
            self.assertEqual(seen, [[]])

    def test_main_honours_bench_suite(self):
        with mock.patch.dict("os.environ", {"BENCH_SUITE": "coding"}):
            ids = [c[0] for c in h.b.active_cases()]
        self.assertTrue(all(i.startswith("code_") for i in ids))

    def test_localize_rewrites_workspace_paths(self):
        self.assertNotIn("/workspace/", h.localize(f"{h.b.WS}/a.py"))


if __name__ == "__main__":
    unittest.main()
