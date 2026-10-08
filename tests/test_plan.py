import unittest
from unittest import mock

from gateway import compose, plan


class PlanTest(unittest.TestCase):
    def test_parse_auth(self):
        self.assertEqual(plan.parse_auth("neo4j/abc/def"), ("neo4j", "abc/def"))
        for bad in (None, "", "nopassword"):
            with self.assertRaises(plan.PlanError):
                plan.parse_auth(bad)

    def test_evidence_run(self):
        with mock.patch.object(plan.store, "get", return_value={"status": "done"}):
            self.assertEqual(plan.check_evidence("abc123xyz"), "run")
        with mock.patch.object(plan.store, "get", return_value={"status": "failed"}):
            with self.assertRaises(plan.PlanError):
                plan.check_evidence("abc123xyz")
        with self.assertRaises(plan.PlanError):
            plan.check_evidence("")

    def test_evidence_commit(self):
        sha = "a" * 40
        with mock.patch.object(plan.subprocess, "run", return_value=mock.Mock(returncode=0)):
            self.assertEqual(plan.check_evidence(sha), "commit")
        with mock.patch.object(plan.subprocess, "run", return_value=mock.Mock(returncode=1)):
            with self.assertRaises(plan.PlanError):
                plan.check_evidence(sha)


class PlanEvidenceRegressionTest(unittest.TestCase):
    def test_hex_gateway_id_is_run_not_commit(self):
        """A finished gateway id that also looks like a short sha must count as a run and never reach git."""
        with mock.patch.object(plan.store, "get", return_value={"status": "done"}),                 mock.patch.object(plan.subprocess, "run") as git:
            self.assertEqual(plan.check_evidence("deadbeef01"), "run")
        git.assert_not_called()

    def test_unfinished_hex_id_falls_through_to_commit_check(self):
        with mock.patch.object(plan.store, "get", return_value={"status": "running"}),                 mock.patch.object(plan.subprocess, "run", return_value=mock.Mock(returncode=1)):
            with self.assertRaises(plan.PlanError):
                plan.check_evidence("deadbeef01")


class PruneCheckpointTest(unittest.TestCase):
    def test_prune_off_when_days_not_positive(self):
        with mock.patch.object(plan, "_q") as q:
            self.assertEqual(plan.prune(0), "retention off")
        q.assert_not_called()

    def test_prune_reports_count_and_passes_cutoff(self):
        with mock.patch.object(plan, "_q", return_value=[{"n": 3}]) as q:
            self.assertEqual(plan.prune(7), "pruned 3 task(s) older than 7d")
        cypher = q.call_args.args[0]
        self.assertIn("'done','cancelled'", cypher)
        self.assertIn("DEPENDS_ON", cypher)  # open dependents protect a task
        self.assertRegex(q.call_args.kwargs["cut"], r"^\d{4}-\d\d-\d\dT")

    def test_prune_defaults_to_retention_days(self):
        with mock.patch.object(plan, "RETENTION_DAYS", 11), mock.patch.object(plan, "_q", return_value=[]):
            self.assertEqual(plan.prune(), "pruned 0 task(s) older than 11d")

    def test_checkpoint_prunes_only_when_all_finished(self):
        with mock.patch.object(plan, "_q", return_value=[{"n": 2}]), mock.patch.object(plan, "prune") as pr:
            self.assertEqual(plan.checkpoint("t"), "open tasks remain")
        pr.assert_not_called()
        with mock.patch.object(plan, "_q", return_value=[{"n": 0}]),                 mock.patch.object(plan, "prune", return_value="pruned 1 task(s) older than 30d") as pr:
            self.assertEqual(plan.checkpoint("t"), "pruned 1 task(s) older than 30d")
        pr.assert_called_once()


class ShutdownTest(unittest.TestCase):
    def test_neo4j_persistent(self):
        self.assertIn("neo4j", compose.PERSISTENT)

    def test_stop_all_stops_project_containers(self):
        calls = []

        def fake(cmd, **kw):
            calls.append(cmd)
            return mock.Mock(stdout="c1 c2\n")

        with mock.patch.object(compose.subprocess, "run", side_effect=fake):
            compose.stop_all_sync()
        self.assertEqual(calls[0][1], "ps")
        self.assertEqual(calls[1][1:], ["stop", "c1", "c2"])

    def test_release_only_last_gateway_stops(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d, mock.patch.object(compose, "REGISTRY", Path(d)),                 mock.patch.object(compose, "stop_all_sync") as stop:
            (Path(d) / "999999").write_text("")
            with mock.patch.object(compose, "_alive", return_value=True):
                compose.register()
                self.assertFalse(compose.release())   # another live gateway remains
            stop.assert_not_called()
            with mock.patch.object(compose, "_alive", return_value=False):
                self.assertTrue(compose.release())    # stale entries pruned, last one out
            stop.assert_called_once()


if __name__ == "__main__":
    unittest.main()
