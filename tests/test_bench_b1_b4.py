"""Offline tests for the shared timeout classification (B1) and the connection-closed abort helper (B4).

scripts/bench_real.py: classify() and connection_closed(). Benchmark/script/run_benchmark.py parses argv at import
time, so run_failure_kind() is pulled out of its source (same approach as tests/test_bench_status.py).
"""
import ast
import unittest
from pathlib import Path

from scripts import bench_real

ROOT = Path(__file__).resolve().parent.parent


def _load_run_failure_kind():
    src = (ROOT / "Benchmark" / "script" / "run_benchmark.py").read_text(encoding="utf-8")
    nodes = [n for n in ast.parse(src).body
             if (isinstance(n, ast.FunctionDef) and n.name == "run_failure_kind")
             or (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "INFRA_MARKERS" for t in n.targets))]
    ns = {}
    exec(compile(ast.Module(nodes, []), "run_benchmark.py", "exec"), ns)
    return ns["run_failure_kind"]


run_failure_kind = _load_run_failure_kind()


class TimeoutClassification(unittest.TestCase):
    def test_exception_name_is_timeout(self):
        self.assertEqual(bench_real.classify(False, "EXC TimeoutError: slow", False, False), "timeout")

    def test_task_timed_out_is_timeout(self):
        self.assertEqual(bench_real.classify(False, "[abc] FAILED task timed out after 600s", False, False), "timeout")

    def test_watchdog_is_timeout(self):
        self.assertEqual(bench_real.classify(False, "watchdog fired after 630s", False, False), "timeout")

    def test_missing_model_404_stays_infra(self):
        err = "EXC NotFoundError: model 'x' not found. Error code: 404"
        self.assertEqual(bench_real.classify(False, err, False, False), "infra")

    def test_ran_repeat_is_not_timeout(self):
        self.assertEqual(bench_real.classify(True, "a final answer", False, False), "valid")

    def test_run_failure_kind_apitimeouterror_is_timeout(self):
        run = {"verified": False, "ok": False, "status": "valid", "error": "EXC APITimeoutError: Request timed out.", "note": ""}
        self.assertEqual(run_failure_kind(run), "timeout")

    def test_run_failure_kind_infra_still_wins(self):
        run = {"verified": False, "ok": False, "error": "EXC NotFoundError: Error code: 404 TimeoutError", "note": ""}
        self.assertEqual(run_failure_kind(run), "infra")


class ConnectionClosed(unittest.TestCase):
    def test_connection_closed_text_is_true(self):
        self.assertTrue(bench_real.connection_closed("[abc] FAILED Connection closed by the gateway", []))

    def test_case_insensitive(self):
        self.assertTrue(bench_real.connection_closed("[abc] FAILED: CONNECTION CLOSED unexpectedly", []))

    def test_normal_answer_is_false(self):
        self.assertFalse(bench_real.connection_closed("The function returns the slug in lower case.", []))

    def test_broken_pipe_or_not_running_in_a_failed_reply_does_not_abort(self):
        # tightened: only the exact "connection closed" phrase aborts the section
        self.assertFalse(bench_real.connection_closed("[abc] FAILED reason: broken pipe", []))
        self.assertFalse(bench_real.connection_closed("[abc] FAILED: container is not running", []))
        self.assertFalse(bench_real.connection_closed("the answer says connection closed is a status", []))

    def test_trail_connection_error_is_true(self):
        trail = [{"kind": "tool_error", "name": "x", "error": "Connection closed"}]
        self.assertTrue(bench_real.connection_closed("a normal answer", trail))


class StripTidTest(unittest.TestCase):
    def test_router_trailer_lines_are_removed_from_the_checked_body(self):
        reply = ("[0123456789] Weekly notes were summarised. Two sentences here.\n"
                 "Checks: files_changed ok (x.py).\n"
                 "files_changed: x.py\n"
                 "status=done role=summariser model=m calls=2 elapsed=3.1s")
        body = bench_real.strip_tid(reply)
        self.assertEqual(body, "Weekly notes were summarised. Two sentences here.\nChecks: files_changed ok (x.py).")
        self.assertNotIn("status=", body)
        self.assertNotIn("files_changed:", body)


if __name__ == "__main__":
    unittest.main()
