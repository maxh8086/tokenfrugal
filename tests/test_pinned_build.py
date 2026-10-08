import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import pinned_build as pb


def _git(cwd, *a):
    return subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


class PinsFileTest(unittest.TestCase):
    def test_shipped_pins_are_valid(self):
        pins = pb.load_pins(pb.ROOT / "docker" / "pins.yaml")
        self.assertTrue(pins)
        for p in pins.values():
            self.assertTrue((pb.ROOT / p["dockerfile"]).exists())

    def test_rejects_short_sha(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "p.yaml"
            f.write_text("pins:\n  x: {repo: r, sha: abc123, image: i, dockerfile: d}\n")
            with self.assertRaises(ValueError):
                pb.load_pins(f)


class CloneTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.src = Path(self.tmp.name) / "src"
        self.src.mkdir()
        _git(self.src, "init", "-q")
        _git(self.src, "config", "user.email", "t@example.com")
        _git(self.src, "config", "user.name", "t")
        _git(self.src, "config", "uploadpack.allowAnySHA1InWant", "true")
        (self.src / "f.txt").write_text("one")
        _git(self.src, "add", "."); _git(self.src, "commit", "-qm", "one")
        self.first = _git(self.src, "rev-parse", "HEAD")
        (self.src / "f.txt").write_text("two")
        _git(self.src, "commit", "-qam", "two")

    def test_clone_lands_on_pinned_commit_not_head(self):
        dest = Path(self.tmp.name) / "dest"
        pb.clone_at(str(self.src), self.first, dest)
        self.assertEqual((dest / "f.txt").read_text(), "one")
        self.assertEqual(_git(dest, "rev-parse", "HEAD"), self.first)

    def test_build_cleans_up_and_calls_docker(self):
        p = {"repo": str(self.src), "sha": self.first, "image": "x/y:1", "dockerfile": "docker/pins.yaml"}
        real = pb.subprocess.run

        def fake(cmd, *a, **k):
            return mock.Mock(returncode=0) if cmd[0] == "docker" else real(cmd, *a, **k)

        with mock.patch.object(pb.subprocess, "run", side_effect=fake) as run:
            pb.build("t", p)
        dockers = [c.args[0] for c in run.call_args_list if c.args[0][0] == "docker"]
        self.assertEqual(len(dockers), 1)
        self.assertIn("x/y:1", dockers[0])

    def test_unknown_name_returns_2(self):
        self.assertEqual(pb.main(["nope"]), 2)


if __name__ == "__main__":
    unittest.main()
