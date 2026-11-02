import tempfile
import unittest
from pathlib import Path
from unittest import mock

from router import media_briefing_mcp as mb

OK_TEXT = "Small teams lose hours to handoffs. One intake step routes each request to its owner."


class Validate(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.render = Path(tmp.name)

    def check(self, **over):
        args = dict(text=OK_TEXT, length_target_s=25, music=False, out_name="film_one", render_dir=self.render)
        args.update(over)
        return mb.validate(**args)

    def test_valid_brief_is_normalised(self):
        got = self.check(text="  spaced   out   text  ")
        self.assertEqual(got["text"], "spaced out text")
        self.assertEqual(got["out_name"], "film_one")
        self.assertFalse(got["music"])

    def test_empty_text(self):
        with self.assertRaisesRegex(mb.BriefError, r"^error: text is empty$"):
            self.check(text="   ")

    def test_text_over_ninety_words(self):
        with self.assertRaisesRegex(mb.BriefError, r"^error: text over 90 words \(91\)$"):
            self.check(text=" ".join(["word"] * 91))

    def test_ninety_words_is_allowed(self):
        self.check(text=" ".join(["word"] * 90))

    def test_length_bounds(self):
        msg = "error: length_target_s must be 20 to 30"
        for bad in (19.9, 30.1, 0, "25", True):
            with self.subTest(bad=bad), self.assertRaisesRegex(mb.BriefError, msg):
                self.check(length_target_s=bad)
        self.check(length_target_s=20)
        self.check(length_target_s=30)

    def test_music_must_be_bool(self):
        with self.assertRaisesRegex(mb.BriefError, r"^error: music must be true or false$"):
            self.check(music="yes")

    def test_bad_out_name(self):
        for bad in ("", "../x", "a/b", "-lead", "x" * 121):
            with self.subTest(bad=bad), self.assertRaisesRegex(mb.BriefError, r"^error: bad output name$"):
                self.check(out_name=bad)

    def test_existing_output_is_refused(self):
        (self.render / "film_one.mp4").write_bytes(b"x")
        with self.assertRaisesRegex(mb.BriefError, r"^error: out_name_exists$"):
            self.check()

    def test_existing_run_folder_is_refused(self):
        (self.render / "film_one.run").mkdir()
        with self.assertRaisesRegex(mb.BriefError, r"^error: out_name_exists$"):
            self.check()


class Tool(unittest.TestCase):
    def test_invalid_brief_returns_error_line(self):
        self.assertEqual(mb.brief(text="", out_name="x"), "error: text is empty")

    def test_valid_brief_is_not_built_yet(self):
        with mock.patch.object(mb, "media_dir", return_value=Path(tempfile.gettempdir())):
            self.assertEqual(mb.brief(text=OK_TEXT, out_name="stub_check_only"), "error: not built yet")


if __name__ == "__main__":
    unittest.main()
