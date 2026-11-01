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


COMFY_PIN = """pins:
  comfyui:
    repo: https://example.invalid/ComfyUI.git
    sha: {sha}
    tree_sha: {tree}
    image: tokenfrugal/comfyui:1
    dockerfile: docker/comfyui/Dockerfile
    context: folder
    lockfile: docker/comfyui/requirements.lock
    base_image: nvidia/cuda:12.6.3-runtime-ubuntu24.04@sha256:<resolve-at-first-build>
    nodes:
      - repo: https://example.invalid/node.git
        node_sha: {nsha}
        tree_sha: <written by the first build>
        folder: ComfyUI-Test
"""
GOOD = "a" * 40


def _pins_file(d, text):
    f = Path(d) / "p.yaml"
    f.write_text(text, encoding="utf-8")
    return f


class NodeListParsingTest(unittest.TestCase):
    def test_shipped_comfyui_nodes_parse(self):
        pins = pb.load_pins(pb.ROOT / "docker" / "pins.yaml")
        nodes = pins["comfyui"]["nodes"]
        self.assertEqual([n["folder"] for n in nodes], ["ComfyUI-LTXVideo", "ComfyUI-GGUF"])
        self.assertEqual(nodes[0]["node_sha"], "220e1d45aa0469f518e982102fca4dca92a61862")
        self.assertEqual(nodes[1]["node_sha"], "6ea2651e7df66d7585f6ffee804b20e92fb38b8a")
        self.assertIn("forwarder", pins)
        self.assertTrue((pb.ROOT / "docker" / "comfyui" / "requirements.lock").exists())
        self.assertTrue((pb.ROOT / "docker" / "comfyui" / "extra_model_paths.yaml").exists())

    def test_placeholder_tree_sha_is_accepted_at_parse_time(self):
        with tempfile.TemporaryDirectory() as d:
            pins = pb.load_pins(_pins_file(d, COMFY_PIN.format(sha=GOOD, tree="<written by the first build>", nsha=GOOD)))
        self.assertEqual(pins["comfyui"]["nodes"][0]["tree_sha"], pb.PLACEHOLDER)

    def test_rejects_bad_node_sha(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError, "node_sha"):
                pb.load_pins(_pins_file(d, COMFY_PIN.format(sha=GOOD, tree=GOOD, nsha="abc123")))

    def test_rejects_node_missing_tree_sha(self):
        text = COMFY_PIN.format(sha=GOOD, tree=GOOD, nsha=GOOD).replace("        tree_sha: <written by the first build>\n", "")
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError, "missing"):
                pb.load_pins(_pins_file(d, text))

    def test_rejects_nested_node_folder(self):
        text = COMFY_PIN.format(sha=GOOD, tree=GOOD, nsha=GOOD).replace("folder: ComfyUI-Test", "folder: ../x")
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError, "plain folder name"):
                pb.load_pins(_pins_file(d, text))

    def test_forwarder_base_only_pin_needs_no_repo(self):
        text = ("pins:\n  forwarder:\n    image: tokenfrugal/forwarder:1\n    dockerfile: docker/forwarder/Dockerfile\n"
                "    context: folder\n    base_image: alpine:3.20@sha256:<resolve-at-first-build>\n")
        with tempfile.TemporaryDirectory() as d:
            self.assertIn("forwarder", pb.load_pins(_pins_file(d, text)))


class TreeHashTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.src = Path(self.tmp.name) / "src"
        self.src.mkdir()
        _git(self.src, "init", "-q")
        _git(self.src, "config", "user.email", "t@example.com")
        _git(self.src, "config", "user.name", "t")
        (self.src / "node.py").write_text("print(1)")
        _git(self.src, "add", "."); _git(self.src, "commit", "-qm", "one")
        self.sha = _git(self.src, "rev-parse", "HEAD")
        self.tree = _git(self.src, "rev-parse", "HEAD^{tree}")

    def _clone(self):
        dest = Path(self.tmp.name) / "dest"
        pb.clone_at(str(self.src), self.sha, dest)
        return dest

    def test_matching_tree_passes(self):
        pb.verify_tree(self._clone(), self.tree, "node")

    def test_altered_pin_fails(self):
        altered = ("0" if self.tree[0] != "0" else "1") + self.tree[1:]
        with self.assertRaisesRegex(RuntimeError, "does not match pinned tree_sha"):
            pb.verify_tree(self._clone(), altered, "node")

    def test_placeholder_fails_and_prints_computed_value(self):
        with self.assertRaisesRegex(RuntimeError, "tree_sha: " + self.tree):
            pb.verify_tree(self._clone(), pb.PLACEHOLDER, "node")


class LockfileCoverageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.lock = self.dir / "requirements.lock"
        self.lock.write_text("# header\n--extra-index-url https://download.pytorch.org/whl/cu126\n"
                             "numpy==2.1.0 \\\n    --hash=sha256:" + "0" * 64 + "\n"
                             "Pillow==11.0.0 \\\n    --hash=sha256:" + "1" * 64 + "\n", encoding="utf-8")
        self.node_dir = self.dir / "custom_nodes" / "ComfyUI-Test"
        self.node_dir.mkdir(parents=True)
        self.req = self.node_dir / "requirements.txt"

    def test_covered_requirements_pass(self):
        self.req.write_text("numpy>=1.26  # comment\npillow; python_version >= '3.10'\n", encoding="utf-8")
        pb.check_lockfile_coverage(self.lock, [self.req])

    def test_missing_package_fails(self):
        self.req.write_text("numpy\nsome-extra-pkg>=1.0\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "some-extra-pkg"):
            pb.check_lockfile_coverage(self.lock, [self.req])

    def test_url_requirement_fails(self):
        self.req.write_text("git+https://example.invalid/x.git\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "unsupported requirement"):
            pb.check_lockfile_coverage(self.lock, [self.req])

    def test_lockfile_without_hashes_fails(self):
        self.lock.write_text("torch\nnumpy\n", encoding="utf-8")
        self.req.write_text("numpy\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "no hashes"):
            pb.check_lockfile_coverage(self.lock, [self.req])

    def test_shipped_lockfile_refuses_to_build(self):
        with self.assertRaisesRegex(RuntimeError, "no hashes"):
            pb.check_lockfile_coverage(pb.ROOT / "docker" / "comfyui" / "requirements.lock", [])

    def test_name_normalisation(self):
        self.assertEqual(pb.lock_names("Foo_Bar.baz==1.0 \\\n    --hash=sha256:x\n"), {"foo-bar-baz"})


if __name__ == "__main__":
    unittest.main()
