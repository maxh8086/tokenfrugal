import hashlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import fetch_media_assets as fma

DATA = b"RIFF0000WAVEfmt test-bytes"
GOOD_SHA = hashlib.sha256(DATA).hexdigest()
LAYOUT = {"Raw", "Music", "Render"}


def entry(**overrides):
    base = {"url": "https://example.invalid/bed.wav", "sha256": GOOD_SHA, "dest": "Music/bed.wav"}
    base.update(overrides)
    return base


class Validate(unittest.TestCase):
    def test_accepts_a_good_entry(self):
        self.assertEqual(fma.validate(entry(), LAYOUT), ("https://example.invalid/bed.wav", GOOD_SHA, "Music/bed.wav"))

    def test_rejects_http(self):
        with self.assertRaises(fma.AssetError):
            fma.validate(entry(url="http://example.invalid/bed.wav"), LAYOUT)

    def test_rejects_bad_sha(self):
        for bad in ("abc", "z" * 64, ""):
            with self.subTest(sha=bad), self.assertRaises(fma.AssetError):
                fma.validate(entry(sha256=bad), LAYOUT)

    def test_rejects_escaping_or_absolute_dest(self):
        for bad in ("Music/../../x.wav", "../x.wav", "/etc/x.wav", "Music\\..\\x.wav", ""):
            with self.subTest(dest=bad), self.assertRaises(fma.AssetError):
                fma.validate(entry(dest=bad), LAYOUT)

    def test_rejects_folder_outside_layout(self):
        with self.assertRaises(fma.AssetError):
            fma.validate(entry(dest="Secrets/bed.wav"), LAYOUT)

    def test_rejects_file_at_root_level(self):
        with self.assertRaises(fma.AssetError):
            fma.validate(entry(dest="bed.wav"), LAYOUT)


class Fetch(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "video-editor"
        self.root.mkdir()

    def test_places_file_when_sha_matches(self):
        target = self.root / "Music" / "bed.wav"
        with mock.patch("urllib.request.urlopen", return_value=io.BytesIO(DATA)):
            fma.fetch("https://example.invalid/bed.wav", GOOD_SHA, target)
        self.assertEqual(target.read_bytes(), DATA)
        self.assertEqual([p.name for p in target.parent.iterdir()], ["bed.wav"])

    def test_sha_mismatch_leaves_nothing_behind(self):
        target = self.root / "Music" / "bed.wav"
        with mock.patch("urllib.request.urlopen", return_value=io.BytesIO(b"other")):
            with self.assertRaises(fma.AssetError):
                fma.fetch("https://example.invalid/bed.wav", GOOD_SHA, target)
        self.assertFalse(target.exists())
        self.assertEqual(list(target.parent.iterdir()), [])


class Main(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.root = self.tmp / "video-editor"
        self.env = mock.patch.dict(os.environ, {
            "VIDEO_EDITOR_DIR": str(self.root),
            "VIDEO_EDITOR_LAYOUT": "Raw,Music",
            "VIDEO_EDITOR_RENDER_DIR": "Render",
        })
        self.env.start()
        self.addCleanup(self.env.stop)

    def write_manifest(self, assets):
        path = self.tmp / "assets.json"
        path.write_text(json.dumps({"assets": assets}), encoding="utf-8")
        return mock.patch.object(fma, "MANIFEST", path)

    def test_empty_manifest_is_a_no_op(self):
        with self.write_manifest([]):
            self.assertEqual(fma.main([]), 0)
        self.assertFalse(self.root.exists())

    def test_creates_layout_and_fetches_missing_asset(self):
        with self.write_manifest([entry()]), \
                mock.patch("urllib.request.urlopen", return_value=io.BytesIO(DATA)):
            self.assertEqual(fma.main([]), 0)
        self.assertEqual((self.root / "Music" / "bed.wav").read_bytes(), DATA)
        self.assertTrue((self.root / "Render").is_dir())

    def test_present_asset_with_good_sha_is_not_refetched(self):
        (self.root / "Music").mkdir(parents=True)
        (self.root / "Music" / "bed.wav").write_bytes(DATA)
        with self.write_manifest([entry()]), mock.patch("urllib.request.urlopen") as opened:
            self.assertEqual(fma.main([]), 0)
        opened.assert_not_called()

    def test_dry_run_changes_nothing(self):
        with self.write_manifest([entry()]), mock.patch("urllib.request.urlopen") as opened:
            self.assertEqual(fma.main(["--dry-run"]), 0)
        opened.assert_not_called()
        self.assertFalse(self.root.exists())

    def test_stops_at_first_failure(self):
        second = entry(url="https://example.invalid/two.wav", dest="Music/two.wav")
        with self.write_manifest([entry(sha256="0" * 64), second]), \
                mock.patch("urllib.request.urlopen", return_value=io.BytesIO(DATA)) as opened:
            self.assertEqual(fma.main([]), 1)
        self.assertEqual(opened.call_count, 1)
        self.assertFalse((self.root / "Music" / "two.wav").exists())


if __name__ == "__main__":
    unittest.main()
