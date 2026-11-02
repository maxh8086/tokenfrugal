import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import check_pins as cp

# A ComfyUI pin with one tagged node (tag_regex) and one base-image-only pin (no repo).
PINS_TEXT = """pins:
  comfyui:
    repo: https://example.invalid/c.git
    tag_regex: '^v(\\d+)\\.(\\d+)\\.(\\d+)$'
    sha: 423cbd20511becb1f16122ab518e92e58bfa03d9
    tree_sha: <written by the first build>
    image: tokenfrugal/comfyui:1
    dockerfile: docker/comfyui/Dockerfile
    base_image: nvidia/cuda:12.6.3-runtime-ubuntu24.04@sha256:<resolve-at-first-build>
    nodes:
      - repo: https://example.invalid/n.git
        node_sha: 220e1d45aa0469f518e982102fca4dca92a61862
        tree_sha: <written by the first build>
        folder: ComfyUI-LTXVideo
        tag_regex: '^v(\\d+)\\.(\\d+)\\.(\\d+)$'
  forwarder:
    image: tokenfrugal/forwarder:1
    dockerfile: docker/forwarder/Dockerfile
    base_image: alpine:3.20@sha256:<resolve-at-first-build>
"""

LS = (
    "aaa\trefs/tags/2.9.0\n"
    "bbb\trefs/tags/2.10.0\n"
    "ccc\trefs/tags/2.10.0^{}\n"
    "ddd\trefs/tags/2.11.0-RC1\n"
)


class CheckPinsTest(unittest.TestCase):
    def test_latest_uses_numeric_order_and_peeled_sha(self):
        with mock.patch.object(cp.subprocess, "run", return_value=mock.Mock(stdout=LS)):
            self.assertEqual(cp.latest("r", r"^(\d+)\.(\d+)\.(\d+)$"), ("2.10.0", "ccc"))

    def test_no_match(self):
        with mock.patch.object(cp.subprocess, "run", return_value=mock.Mock(stdout=LS)):
            self.assertEqual(cp.latest("r", r"^x(\d+)\.(\d+)\.(\d+)$"), (None, None))

    def test_node_drift_is_reported_and_node_pin_never_rewritten(self):
        def fake_latest(repo, regex):
            return ("v1.2.0", "b" * 40) if "n.git" in repo else (None, None)

        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "pins.yaml"
            f.write_text(PINS_TEXT, encoding="utf-8")
            out = io.StringIO()
            with mock.patch.object(cp, "PINS", f), mock.patch.object(cp, "latest", side_effect=fake_latest) as lat, \
                    contextlib.redirect_stdout(out):
                self.assertEqual(cp.main(["--write"]), 0)
            self.assertEqual(f.read_text(encoding="utf-8"), PINS_TEXT)
        self.assertIn("ComfyUI-LTXVideo", out.getvalue())
        self.assertIn("220e1d45aa04 -> bbbbbbbbbbbb (v1.2.0)", out.getvalue())
        # the forwarder has no repo, so only ComfyUI and its tagged node are queried
        self.assertEqual(sorted(c.args[0] for c in lat.call_args_list),
                         ["https://example.invalid/c.git", "https://example.invalid/n.git"])


if __name__ == "__main__":
    unittest.main()
