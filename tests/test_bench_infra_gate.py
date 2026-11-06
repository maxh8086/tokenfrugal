"""Offline tests for the team runner's infra gate (scripts/bench.py bench_roles, scripts/bench_checks.py).

No docker, router or model is contacted: docker calls are patched at scripts.bench_checks._docker or at
container_state, and dispatch is replaced by a fake role_call."""
import asyncio
import json
import os
import unittest
from unittest import mock

from router.config import load_tf_roles
from scripts import bench, bench_checks
from scripts.bench_team_tasks import TEAM_REQUIRED_TOOLS, TEAM_TASKS, synaptree_dependent_roles

STARTED = "2026-11-01T10:00:00Z"
RUNNING = {"Running": True, "ExitCode": 0, "OOMKilled": False, "StartedAt": STARTED, "FinishedAt": "0001-01-01T00:00:00Z"}
RESTARTED = dict(RUNNING, StartedAt="2026-11-02T08:00:00Z")
STOPPED = {"Running": False, "ExitCode": 137, "OOMKilled": True, "StartedAt": STARTED, "FinishedAt": "2026-11-01T11:00:00Z"}
LONG_REPLY = "[0123456789] The reply is long enough to pass the reply length check here."


def run_role(role, tasks, reply=LONG_REPLY, states=None, trail=(), n=1):
    """Run bench.bench_roles for one role with a fake dispatch. Returns (runs, dispatch agents)."""
    calls = []

    async def fake_call(agent, task, timeout):
        calls.append(agent)
        return reply

    cs = mock.Mock(side_effect=list(states)) if states is not None else mock.Mock(return_value=RUNNING)
    patches = [
        mock.patch.object(bench, "ROLE_TASKS", {role: tasks}),
        mock.patch.object(bench, "role_call", fake_call),
        mock.patch.object(bench_checks, "scratch_ready", return_value=""),
        mock.patch.object(bench_checks, "sweep_stale_mcp", return_value=0),
        mock.patch.object(bench_checks, "container_state", new=cs),
        mock.patch.object(bench_checks, "trail_of", return_value=list(trail)),
        mock.patch.dict(os.environ, {"BENCH_ROLES": ""}),
    ]
    for p in patches:
        p.start()
    try:
        res = asyncio.run(bench.bench_roles(n, only=[role]))
    finally:
        for p in patches:
            p.stop()
    return res[role]["runs"], calls


BUILDER_TASK = [("engineering-backend-architect", "Use search_graph to find the symbol named summarize.", "reply_ok")]
DESIGNER_TASK = [("design-ui-designer", "Call high_level_overview and report what it returns, or the exact error.", "designer_tools")]


class SynaptreeDownTests(unittest.TestCase):
    def test_running_unchanged_container_is_clean(self):
        self.assertEqual(bench_checks.synaptree_down(RUNNING), "")
        self.assertEqual(bench_checks.synaptree_down(RUNNING, STARTED), "")

    def test_stopped_container_gives_reason(self):
        reason = bench_checks.synaptree_down(STOPPED)
        self.assertIn("not running", reason)
        self.assertIn("137", reason)
        self.assertIn("OOMKilled", reason)

    def test_restarted_container_gives_reason(self):
        reason = bench_checks.synaptree_down(RESTARTED, STARTED)
        self.assertIn("restarted", reason)
        self.assertIn(STARTED, reason)

    def test_missing_container_reports_inspect_error(self):
        with mock.patch.object(bench_checks, "_docker", return_value=(1, "Error: No such object: synaptree-synaptree-1")):
            state = bench_checks.container_state()
        self.assertFalse(state["Running"])
        self.assertIn("No such", bench_checks.synaptree_down(state))

    def test_container_state_reads_inspect_json(self):
        payload = json.dumps({"Running": True, "ExitCode": 0, "OOMKilled": False, "StartedAt": STARTED, "FinishedAt": "x"})
        with mock.patch.object(bench_checks, "_docker", return_value=(0, payload)):
            state = bench_checks.container_state()
        self.assertEqual(state["StartedAt"], STARTED)
        self.assertEqual(bench_checks.synaptree_down(state, STARTED), "")


class PreDispatchGateTests(unittest.TestCase):
    def test_dispatch_skipped_when_container_down(self):
        runs, calls = run_role("builder", BUILDER_TASK, states=[STOPPED])
        self.assertEqual(calls, [], "nothing may be dispatched while the synaptree container is down")
        self.assertEqual(len(runs), 1)
        self.assertTrue(runs[0]["infra"])
        self.assertFalse(runs[0]["ok"])
        self.assertIn("not running", runs[0]["out"])

    def test_dispatch_runs_when_container_up(self):
        runs, calls = run_role("builder", BUILDER_TASK, states=[RUNNING])
        self.assertEqual(len(calls), 1)
        self.assertFalse(runs[0]["infra"])
        self.assertTrue(runs[0]["ok"])

    def test_non_synaptree_role_never_checks_container(self):
        runs, calls = run_role("designer", DESIGNER_TASK, reply="[0123456789] Penpot design tools are available.",
                               states=[])  # an empty list: any container_state call would raise StopIteration
        self.assertEqual(len(calls), 1)
        self.assertFalse(runs[0]["infra"])


class PostDispatchGateTests(unittest.TestCase):
    def test_model_fail_with_healthy_container_stays_a_fail(self):
        runs, _ = run_role("builder", BUILDER_TASK, reply="[0123456789] FAILED LoopError: the model stalled", states=[RUNNING, RUNNING])
        self.assertFalse(runs[0]["ok"])
        self.assertFalse(runs[0]["infra"])

    def test_failed_run_with_container_restart_is_infra(self):
        runs, _ = run_role("builder", BUILDER_TASK, reply="[0123456789] FAILED LoopError: the model stalled", states=[RUNNING, RESTARTED])
        self.assertTrue(runs[0]["infra"])
        self.assertFalse(runs[0]["ok"])
        self.assertIn("restarted", runs[0]["out"])

    def test_failed_run_with_container_down_is_infra(self):
        runs, _ = run_role("builder", BUILDER_TASK, reply="[0123456789] FAILED TimeoutError after 600s", states=[RUNNING, STOPPED])
        self.assertTrue(runs[0]["infra"])
        self.assertIn("not running", runs[0]["out"])

    def test_connection_closed_in_trail_with_container_down_is_infra(self):
        trail = [{"kind": "tool_error", "error": "Connection closed"}]
        runs, _ = run_role("builder", BUILDER_TASK, states=[RUNNING, STOPPED], trail=trail)
        self.assertTrue(runs[0]["infra"])
        self.assertFalse(runs[0]["ok"])

    def test_connection_error_with_healthy_container_is_not_infra(self):
        trail = [{"kind": "tool_error", "error": "Connection closed"}]
        runs, _ = run_role("builder", BUILDER_TASK, states=[RUNNING, RUNNING], trail=trail)
        self.assertFalse(runs[0]["infra"])
        self.assertTrue(runs[0]["ok"])  # the reply itself passed its check


class NotExposedToolTests(unittest.TestCase):
    def test_not_exposed_in_reply_is_infra(self):
        reply = "[0123456789] I could not run it: high_level_overview is not exposed by profile design."
        runs, _ = run_role("designer", DESIGNER_TASK, reply=reply)
        self.assertTrue(runs[0]["infra"])
        self.assertFalse(runs[0]["ok"])
        self.assertIn("not exposed by profile", runs[0]["out"])

    def test_not_exposed_in_trail_is_infra(self):
        trail = [{"kind": "tool_error", "name": "high_level_overview", "error": "Error: tool not exposed by profile design"}]
        runs, _ = run_role("designer", DESIGNER_TASK, reply="[0123456789] Nothing useful came back here at all.", trail=trail)
        self.assertTrue(runs[0]["infra"])
        self.assertFalse(runs[0]["ok"])

    def test_plain_model_fail_on_required_tool_role_stays_a_fail(self):
        runs, _ = run_role("designer", DESIGNER_TASK, reply="[0123456789] Nothing useful came back here at all.")
        self.assertFalse(runs[0]["ok"])
        self.assertFalse(runs[0]["infra"])


class TeamConfigTests(unittest.TestCase):
    def setUp(self):
        self.cfg = load_tf_roles()

    def test_team_required_tools_exist_in_yaml_roles(self):
        for role, tool in TEAM_REQUIRED_TOOLS.items():
            with self.subTest(role=role):
                self.assertIn(role, self.cfg["roles"], f"{role} is not a role in router/tf-roles.yaml")
                self.assertIn(tool, self.cfg["roles"][role]["tools"], f"{tool} is not a tool of {role}")
                self.assertIn(role, TEAM_TASKS)

    def test_synaptree_dependent_roles_come_from_yaml_native_lists(self):
        dep = synaptree_dependent_roles(self.cfg)
        for role in ("builder", "analyzer", "reviewer", "debugger", "browser"):
            self.assertIn(role, dep)
        for role in ("tracker", "designer"):
            self.assertNotIn(role, dep)

    def test_browser_is_synaptree_dependent_without_yaml_native(self):
        cfg = {"roles": {"browser": {"tools": ["navigate_page"], "native": []},
                         "builder": {"tools": [], "native": ["synaptree"]}}}
        dep = synaptree_dependent_roles(cfg)
        self.assertIn("browser", dep)
        self.assertIn("builder", dep)


if __name__ == "__main__":
    unittest.main()
