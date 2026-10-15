import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from router import profile_sync


class ResolveWorkspace(unittest.TestCase):
    def test_real_env_wins(self):
        self.assertEqual(profile_sync.resolve_workspace("/env", "/cwd", "/dotenv", "/root"), "/env")

    def test_cwd_repo_beats_dotenv(self):
        self.assertEqual(profile_sync.resolve_workspace(None, "/cwd", "/dotenv", "/root"), "/cwd")

    def test_dotenv_when_cwd_is_not_a_repo(self):
        self.assertEqual(profile_sync.resolve_workspace(None, None, "/dotenv", "/root"), "/dotenv")

    def test_root_is_last_resort(self):
        self.assertEqual(profile_sync.resolve_workspace(None, None, None, "/root"), "/root")


class EnsureProfiles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.marker = Path(self.tmp.name) / "marker.json"
        self.pdir = Path(self.tmp.name) / "profiles"
        self.pdir.mkdir()
        (self.pdir / "build.yaml").write_text("volume: __WORKSPACE__:/w\n", encoding="utf-8")
        (self.pdir / "analyze.yaml").write_text("volume: __WORKSPACE__:/w\n", encoding="utf-8")

    def _run(self, ws, rc=0):
        calls = []

        def fake(argv, **kw):
            calls.append(argv)
            return mock.Mock(returncode=rc, stdout="", stderr="boom" if rc else "")

        changed = profile_sync.ensure_profiles(ws, marker=self.marker, profiles_dir=self.pdir, run=fake)
        return changed, calls

    def test_first_run_installs_and_records(self):
        changed, calls = self._run("C:/a")
        self.assertTrue(changed)
        self.assertEqual(sum(1 for c in calls if c[:4] == ["docker", "mcp", "profile", "import"]), 2)
        self.assertEqual(json.loads(self.marker.read_text())["workspace"], "C:/a")

    def test_same_workspace_is_a_noop(self):
        self._run("C:/a")
        changed, calls = self._run("C:/a")
        self.assertFalse(changed)
        self.assertEqual(calls, [])

    def test_new_workspace_reinstalls(self):
        self._run("C:/a")
        changed, calls = self._run("C:/b")
        self.assertTrue(changed)
        self.assertEqual(json.loads(self.marker.read_text())["workspace"], "C:/b")

    def test_failure_keeps_old_marker_and_does_not_raise(self):
        self._run("C:/a")
        changed, _ = self._run("C:/b", rc=1)
        self.assertFalse(changed)
        self.assertEqual(json.loads(self.marker.read_text())["workspace"], "C:/a")

    def test_docker_missing_does_not_raise(self):
        def boom(argv, **kw):
            raise FileNotFoundError("docker")
        self.assertFalse(profile_sync.ensure_profiles("C:/a", marker=self.marker, profiles_dir=self.pdir, run=boom))


if __name__ == "__main__":
    unittest.main()
