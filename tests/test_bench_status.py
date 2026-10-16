"""Offline tests for per-case benchmark status (scripts/bench_real.py, scripts/bench_csv.py).
Docker is mocked; no model, router or container is contacted."""
import ast
import asyncio
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import bench_csv, bench_real


def _load_run_verdict():
    """run_benchmark.py parses argv at import time, so pull only run_verdict out of its source."""
    src = (Path(__file__).resolve().parent.parent / "Benchmark" / "script" / "run_benchmark.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "run_verdict")
    ns = {}
    exec(compile(ast.Module([fn], []), "run_benchmark.py", "exec"), ns)
    return ns["run_verdict"]


run_verdict = _load_run_verdict()
UP = (True, "2026-10-16T04:26:23Z")

HEALTHY = {"Running": True, "ExitCode": 0, "OOMKilled": False, "StartedAt": "2026-10-16T04:26:23Z", "FinishedAt": "0001-01-01T00:00:00Z"}
RESTARTED = dict(HEALTHY, StartedAt="2026-10-16T05:00:00Z")
DOWN = {"Running": False, "ExitCode": 137, "OOMKilled": False, "StartedAt": "2026-10-16T04:26:23Z", "FinishedAt": "2026-10-16T04:50:00Z"}


def ok(r):
    return "FAILED" not in r[:60] and not r.startswith(("EXC", "plan task"))


def failure_mode(r):
    i = r.find("FAILED")
    return r[i:i + 110] if i >= 0 else r[:110]


def stats(times):
    return {"mean": round(sum(times) / len(times), 1)} if times else {}


def fake_timed(r, dt=1.0):
    async def timed(coro):
        try:
            out = await coro
        except Exception as e:  # noqa: BLE001
            out = f"EXC {type(e).__name__}: {e}"
        return dt, out
    return timed


class RunCase(unittest.IsolatedAsyncioTestCase):
    """Drives bench_real.run for one synaptree case with docker and dispatch mocked."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        patches = [
            mock.patch.object(bench_real, "SCRATCH", Path(self.tmp.name)),
            mock.patch.dict(os.environ, {"BENCH_CASES": "find_symbol"}),
            mock.patch.object(bench_real, "container_logs", return_value="LOGTAIL"),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.tmp_cleanup = self.tmp.cleanup
        self.addCleanup(self.tmp_cleanup)

    async def run_case(self, states, reply=None, side_effect=None, timed=None, case="find_symbol"):
        disp = mock.AsyncMock(return_value=reply, side_effect=side_effect)
        with mock.patch.dict(os.environ, {"BENCH_CASES": case}), \
                mock.patch.object(bench_real, "container_state", side_effect=states) as cs, \
                mock.patch.object(bench_real.server, "dispatch_task", disp):
            res = await bench_real.run(1, timed or fake_timed(None), ok, failure_mode, stats)
        return res[case], disp, cs

    async def test_container_down_is_infra_and_case_not_run(self):
        case, disp, _ = await self.run_case(states=[DOWN], reply="unused")
        disp.assert_not_called()
        self.assertEqual(case["status"], "infra")
        run = case["runs"][0]
        self.assertEqual(run["status"], "infra")
        self.assertFalse(run["dispatched"])
        self.assertEqual(run["error"], "synaptree container not running")
        self.assertIn("start", run)
        self.assertIn("end", run)
        self.assertEqual(run["container_logs"], "LOGTAIL")
        self.assertFalse(run["container_state"]["Running"])
        self.assertIsNone(case["s"])

    async def test_unknown_agent_is_infra_not_model_fault(self):
        reply = "[t1] FAILED (x/y): unknown agent 'engineering-backend-architect'"
        case, _, _ = await self.run_case(states=[HEALTHY, HEALTHY], reply=reply)
        self.assertEqual(case["runs"][0]["status"], "infra")

    async def test_connection_closed_with_restart_is_infra(self):
        reply = "[t1] FAILED (engineering-backend-architect/x): Connection closed"
        case, disp, _ = await self.run_case(states=[HEALTHY, RESTARTED], reply=reply)
        disp.assert_called_once()
        run = case["runs"][0]
        self.assertEqual(run["status"], "infra")
        self.assertTrue(run["dispatched"])
        self.assertEqual(run["error"], reply)
        self.assertEqual(run["container_state"]["StartedAt"], "2026-10-16T05:00:00Z")
        self.assertEqual(run["container_logs"], "LOGTAIL")
        self.assertEqual(case["infra_runs"], 1)
        self.assertEqual(case["status"], "infra")

    async def test_loop_error_with_healthy_container_is_valid(self):
        reply = "[t2] FAILED (engineering-backend-architect/x): no final answer in 8 steps"
        case, _, _ = await self.run_case(states=[HEALTHY, HEALTHY], reply=reply)
        run = case["runs"][0]
        self.assertEqual(run["status"], "valid")
        self.assertFalse(run["ok"])
        self.assertEqual(run["container_state"]["Running"], True)
        self.assertEqual(case["status"], "valid")

    async def test_timeout_classified_as_timeout(self):
        case, _, _ = await self.run_case(states=[HEALTHY, HEALTHY],
                                         side_effect=TimeoutError("task timed out after 3600s"))
        run = case["runs"][0]
        self.assertEqual(run["status"], "timeout")
        self.assertIn("TimeoutError", run["error"])
        self.assertEqual(case["status"], "timeout")

    async def test_non_synaptree_case_never_checks_container(self):
        with mock.patch.dict(os.environ, {"BENCH_CASES": "summarize_readme"}), \
                mock.patch.object(bench_real, "container_state") as cs, \
                mock.patch.object(bench_real.server, "dispatch_task",
                                  mock.AsyncMock(return_value="[t3] FAILED (x/y): boom")):
            res = await bench_real.run(1, fake_timed(None), ok, failure_mode, stats)
        # no pre-run gate for non-synaptree cases: container_state is only captured after the failed repeat
        self.assertEqual(cs.call_count, 1)
        self.assertEqual(res["summarize_readme"]["runs"][0]["status"], "valid")


HEX = "abcdef0123"
CONN_TRAIL = [{"kind": "tool", "name": "search_graph", "args": "{}"},
              {"kind": "tool_error", "name": "search_graph", "error": "tool error: Connection closed"}]


class TrailChecks(unittest.IsolatedAsyncioTestCase):
    setUp = RunCase.setUp  # same temp scratch dir, BENCH_CASES and container_logs patches
    run_case = RunCase.run_case

    async def test_connection_error_in_trail_is_infra_even_when_reply_is_answer(self):
        reply = f"[{HEX}] resolve_role is defined in router/config.py"
        with mock.patch.object(bench_real.store, "get", return_value={"trail": CONN_TRAIL}):
            case, _, _ = await self.run_case(states=[HEALTHY, HEALTHY], reply=reply)
        run = case["runs"][0]
        self.assertTrue(run["ok"])
        self.assertEqual(run["status"], "infra")
        self.assertEqual(run["trail_tools"], ["search_graph"])
        self.assertEqual(case["status"], "infra")

    async def test_required_tool_missing_from_trail_is_not_verified(self):
        reply = f"[{HEX}] Plan has 3 tasks, 1 done, 2 open."
        trail = [{"kind": "tool", "name": "list_directory", "args": "{}"}]
        with mock.patch.object(bench_real.store, "get", return_value={"trail": trail}):
            case, _, cs = await self.run_case(states=[], reply=reply, case="role_tracker")
        run = case["runs"][0]
        self.assertTrue(run["ok"])
        self.assertFalse(run["verified"])
        self.assertEqual(run["note"], "tool plan_status not called")
        self.assertEqual(run["status"], "valid")
        self.assertEqual(run["trail_tools"], ["list_directory"])
        cs.assert_not_called()

    async def test_required_tool_called_keeps_verified(self):
        reply = f"[{HEX}] Plan has 3 tasks, 1 done, 2 open."
        trail = [{"kind": "tool", "name": "plan_status", "args": "{}"}]
        with mock.patch.object(bench_real.store, "get", return_value={"trail": trail}):
            case, _, _ = await self.run_case(states=[], reply=reply, case="role_tracker")
        self.assertTrue(case["runs"][0]["verified"])

    async def test_empty_trail_leaves_verified_unchanged(self):
        reply = f"[{HEX}] Plan has 3 tasks, 1 done, 2 open."
        with mock.patch.object(bench_real.store, "get", return_value=None):
            case, _, _ = await self.run_case(states=[], reply=reply, case="role_tracker")
        self.assertTrue(case["runs"][0]["verified"])
        self.assertEqual(case["runs"][0]["trail_tools"], [])


class TrailHelpers(unittest.TestCase):
    def test_tid_of_and_strip_tid(self):
        self.assertEqual(bench_real.tid_of(f"[{HEX}] hi"), HEX)
        self.assertEqual(bench_real.strip_tid(f"[{HEX}] hi"), "hi")
        self.assertIsNone(bench_real.tid_of("no prefix"))
        self.assertIsNone(bench_real.tid_of("[XYZ] x"))
        self.assertIsNone(bench_real.tid_of("[t1] FAILED"))

    def test_trail_conn_error(self):
        self.assertTrue(bench_real.trail_conn_error(CONN_TRAIL))
        self.assertFalse(bench_real.trail_conn_error([{"kind": "tool", "name": "x", "args": ""}]))
        # a connection marker in a non-error event does not count
        self.assertFalse(bench_real.trail_conn_error([{"kind": "say", "error": "Connection closed"}]))
        self.assertFalse(bench_real.trail_conn_error([{"kind": "tool_error", "name": "x", "error": "tool error: boom"}]))

    def test_trail_of(self):
        with mock.patch.object(bench_real.store, "get", return_value={"trail": CONN_TRAIL}) as get:
            self.assertEqual(bench_real.trail_of(f"[{HEX}] x"), CONN_TRAIL)
            get.assert_called_once_with(HEX)
            self.assertEqual(bench_real.trail_of("no prefix"), [])
            self.assertEqual(get.call_count, 1)  # no lookup without a task id
        with mock.patch.object(bench_real.store, "get", return_value=None):
            self.assertEqual(bench_real.trail_of(f"[{HEX}] x"), [])
        with mock.patch.object(bench_real.store, "get", side_effect=RuntimeError("db locked")):
            self.assertEqual(bench_real.trail_of(f"[{HEX}] x"), [])


class Scoring(unittest.TestCase):
    def test_status_rules(self):
        self.assertEqual(bench_real.case_status(["valid", "valid"]), "valid")
        self.assertEqual(bench_real.case_status(["infra", "infra"]), "infra")
        self.assertEqual(bench_real.case_status(["infra", "valid"]), "valid")
        self.assertEqual(bench_real.case_status(["timeout", "timeout"]), "timeout")
        self.assertEqual(bench_real.case_status(["valid", "timeout"]), "partial")

    def test_classify(self):
        self.assertEqual(bench_real.classify(False, "x", True, True), "infra")
        self.assertEqual(bench_real.classify(False, "EXC TimeoutError: t", False, False), "timeout")
        self.assertEqual(bench_real.classify(False, "no final answer", True, False), "valid")

    def test_valid_count_and_mean_exclude_infra(self):
        cases = {
            "a": {"status": "valid", "s": {"mean": 10.0}},
            "b": {"status": "infra", "s": None},
            "c": {"status": "valid", "s": {"mean": 20.0}},
            "d": {"status": "timeout", "s": {"mean": 30.0}},
        }
        valid, infra, mean = bench_csv.status_scores(cases)
        self.assertEqual((valid, infra), (3, 1))
        self.assertEqual(mean, 20.0)

    def test_all_infra_gives_blank_mean(self):
        self.assertEqual(bench_csv.status_scores({"a": {"status": "infra", "s": None}}), (0, 1, ""))

    def test_total_seconds_includes_timeouts_and_infra_runs(self):
        cases = {
            "a": {"status": "valid", "runs": [{"s": 10.4}, {"s": 20.2}]},
            "b": {"status": "infra", "runs": [{"s": 0.0}, {"s": 5.5}]},  # dispatched infra repeat still took time
            "c": {"status": "timeout", "runs": [{"s": 600.0}]},
            "err": {"error": "no result after 100s (section watchdog)"},  # section-level entry, skipped
        }
        self.assertEqual(bench_csv.total_seconds(cases), 636)  # 10.4+20.2+5.5+600.0 = 636.1

    def test_total_seconds_empty_is_zero(self):
        self.assertEqual(bench_csv.total_seconds({}), 0)
        self.assertEqual(bench_csv.total_seconds({"realworld": {"error": "x"}}), 0)


def _load_section_timeout():
    """bench.py imports the whole router at module level, so pull only section_timeout and its constants."""
    src = (Path(__file__).resolve().parent.parent / "scripts" / "bench.py").read_text(encoding="utf-8")
    body = [n for n in ast.parse(src).body
            if (isinstance(n, ast.FunctionDef) and n.name == "section_timeout")
            or (isinstance(n, ast.Assign) and any(getattr(t, "id", None) in ("REALWORLD_CASES", "SECTION_MARGIN")
                                                  for t in n.targets))]
    ns = {"os": os, "bench_real": bench_real}
    exec(compile(ast.Module(body, []), "bench.py", "exec"), ns)
    return ns["section_timeout"]


class SectionTimeout(unittest.TestCase):
    def setUp(self):
        self.section_timeout = _load_section_timeout()
        env = {k: v for k, v in os.environ.items() if k != "BENCH_SECTION_TIMEOUT"}
        patch = mock.patch.dict(os.environ, env, clear=True)
        patch.start()
        self.addCleanup(patch.stop)

    def test_derived_from_n_cases_and_case_timeout(self):
        self.assertEqual(self.section_timeout(5), 16 * 5 * bench_real.CASE_TIMEOUT + 600)
        self.assertEqual(self.section_timeout(1), 16 * bench_real.CASE_TIMEOUT + 600)

    def test_env_override_wins(self):
        with mock.patch.dict(os.environ, {"BENCH_SECTION_TIMEOUT": "123"}):
            self.assertEqual(self.section_timeout(5), 123.0)

    def test_case_timeout_default_is_600(self):
        if "BENCH_CASE_TIMEOUT" not in os.environ:
            self.assertEqual(bench_real.CASE_TIMEOUT, 600.0)


class RunVerdict(unittest.TestCase):
    def test_container_changed_and_nonzero_exit_reports_container(self):
        msg = run_verdict(UP, (True, "2026-10-16T05:00:00Z"), 1)
        self.assertIn("container", msg)
        self.assertNotIn("exit code", msg)

    def test_container_fine_and_nonzero_exit_reports_exit_code(self):
        msg = run_verdict(UP, UP, 2)
        self.assertIn("exited with code 2", msg)
        self.assertNotIn("container", msg)

    def test_all_fine_is_none(self):
        self.assertIsNone(run_verdict(UP, UP, 0))


class CheckFunctions(unittest.TestCase):
    def test_all_has_needs_every_word(self):
        f = bench_real._all_has("aaa", "bbb")
        self.assertTrue(f("AAA and bbb")[0])
        self.assertFalse(f("only aaa")[0])

    def test_debug_ok_needs_exception_and_cause(self):
        self.assertTrue(bench_real._debug_ok("ZeroDivisionError: list is empty")[0])
        self.assertFalse(bench_real._debug_ok("ZeroDivisionError")[0])
        self.assertFalse(bench_real._debug_ok("the list is empty")[0])

    def test_tracker_ok_needs_number_and_word(self):
        self.assertTrue(bench_real._tracker_ok("Plan 3: 2 tasks done")[0])
        self.assertFalse(bench_real._tracker_ok("task status unknown")[0])
        self.assertFalse(bench_real._tracker_ok("42")[0])

    def test_trail_tools_lists_tool_events(self):
        t = [{"kind": "step"}, {"kind": "tool", "name": "a"}, {"kind": "tool_error", "name": "b"}]
        self.assertEqual(bench_real.trail_tools(t), ["a"])

    def test_readme_ok_passes_short_reply_with_mcp_and_keyword(self):
        self.assertTrue(bench_real._readme_ok("The MCP router runs local models. It returns short summaries.")[0])

    def test_readme_ok_rejects_too_many_sentences(self):
        reply = " ".join(f"Local MCP sentence {i}." for i in range(7))  # 7 sentences
        self.assertFalse(bench_real._readme_ok(reply)[0])
        ok6 = " ".join(f"Local MCP sentence {i}." for i in range(6))  # 6 is the limit
        self.assertTrue(bench_real._readme_ok(ok6)[0])

    def test_readme_ok_rejects_missing_mcp(self):
        self.assertFalse(bench_real._readme_ok("The router runs local models.")[0])

    def test_readme_ok_rejects_overlong_reply(self):
        reply = "Local MCP router. " + "word " * 300  # two sentences, but over 1200 chars
        self.assertGreater(len(reply), 1200)
        self.assertFalse(bench_real._readme_ok(reply)[0])


class RoleBrowserCase(unittest.TestCase):
    def test_role_browser_targets_synaptree_ui(self):
        self.assertIn("role_browser", bench_real.SYNAPTREE_CASES)
        self.assertEqual(bench_real.REQUIRED_TOOLS["role_browser"], "navigate_page")
        case = next(c for c in bench_real.cases() if c[0] == "role_browser")
        self.assertIn("host.docker.internal:8787/ui/", case[3])
        self.assertIn("navigate_page", case[3])
        self.assertTrue(case[4]("synaptree trace")[0])
        self.assertFalse(case[4]("synaptree only")[0])


class ScratchCleanup(unittest.IsolatedAsyncioTestCase):
    setUp = RunCase.setUp  # same temp scratch dir, BENCH_CASES and container_logs patches
    run_case = RunCase.run_case

    async def test_stray_scratch_content_removed_before_case(self):
        scratch = Path(self.tmp.name)
        (scratch / "stray.txt").write_text("left over", encoding="utf-8")
        (scratch / "stray_dir").mkdir()
        (scratch / "stray_dir" / "inner.py").write_text("x", encoding="utf-8")
        reply = f"[{HEX}] resolve_role is defined in router/config.py"
        with mock.patch.object(bench_real.store, "get", return_value=None):
            await self.run_case(states=[HEALTHY, HEALTHY], reply=reply)
        self.assertFalse((scratch / "stray.txt").exists())
        self.assertFalse((scratch / "stray_dir").exists())
        self.assertTrue(scratch.is_dir())  # SCRATCH itself is kept


if __name__ == "__main__":
    unittest.main()
