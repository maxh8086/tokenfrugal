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
