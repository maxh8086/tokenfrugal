import os
import tempfile
import unittest
from unittest import mock

from router import sandbox_mcp as s
from router import media_generator_mcp as v


class SandboxTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict(os.environ, {"CC_WORKSPACE": self.tmp.name})
        self.env.start()
        os.makedirs(os.path.join(self.tmp.name, "proj"))

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_outside_workspace_refused(self):
        self.assertIn("outside the workspace", s.run_tests(".."))

    def test_bad_test_file_refused(self):
        self.assertIn("bad test_file", s.run_tests("proj", "x; rm -rf /"))

    def test_argv_is_isolated(self):
        argv = s._docker_argv(s.Path(self.tmp.name), ["-m", "unittest"])
        for flag in ("--network", "none", "--rm", "no-new-privileges"):
            self.assertIn(flag, argv)
        self.assertTrue(any(a.endswith(":/work:ro") for a in argv))

    def test_discover_and_module_args(self):
        with mock.patch.object(s.subprocess, "run") as run:
            run.return_value = mock.Mock(returncode=0, stdout="OK", stderr="")
            self.assertTrue(s.run_tests("proj").startswith("exit=0"))
            self.assertIn("discover", run.call_args[0][0])
            s.run_tests("proj", "test_m.py")
            self.assertEqual(run.call_args[0][0][-1], "test_m")


if __name__ == "__main__":
    unittest.main()


class VideoEditorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict(os.environ, {"VIDEO_EDITOR_DIR": self.tmp.name})
        self.env.start()
        # mgen tests check argv and validation, not the model cache: skip the model pull.
        self.models = mock.patch.object(v, "ensure_models", return_value="")
        self.models.start()
        os.makedirs(os.path.join(self.tmp.name, "Raw"))

    def tearDown(self):
        self.models.stop()
        self.env.stop()
        self.tmp.cleanup()

    def test_model_pull_not_attempted_for_missing_clip(self):
        with mock.patch.object(v, "ensure_models", return_value="") as pull, \
                mock.patch.object(v.subprocess, "run") as run:
            self.assertEqual(v.mgen("nope.mp4"), "error: clip not found in Raw")
            pull.assert_not_called()
            run.assert_not_called()

    def test_path_like_names_refused_without_docker(self):
        with mock.patch.object(v.subprocess, "run") as run:
            for bad in ("../x.mp4", "a/b.mp4", "a\\b.mp4", "x..y.mp4", "-x.mp4", ""):
                self.assertTrue(v.mgen(bad).startswith("error: bad clip name"), bad)
            self.assertTrue(v.mgen("ok.mp4", out_name="../o").startswith("error: bad output name"))
            run.assert_not_called()

    def test_missing_clip_refused_without_docker(self):
        with mock.patch.object(v.subprocess, "run") as run:
            self.assertEqual(v.mgen("nope.mp4"), "error: clip not found in Raw")
            run.assert_not_called()

    def test_runs_compose_mgen_with_options(self):
        open(os.path.join(self.tmp.name, "Raw", "talk.mp4"), "w").close()
        with mock.patch.object(v.subprocess, "run") as run:
            run.return_value = mock.Mock(returncode=0, stdout="done\n", stderr="")
            out = v.mgen("talk.mp4", out_name="short", no_music=True)
        argv = run.call_args[0][0]
        self.assertEqual(argv[-7:], ["mgen", "talk.mp4", "--captions", "auto", "--out", "short", "--no-music"])
        self.assertIn("media-generator", argv)
        self.assertEqual(run.call_args[1]["timeout"], 900)
        self.assertTrue(out.startswith("exit=0"))
        self.assertIn("Saved:", out)

    def test_list_raw_and_renders(self):
        open(os.path.join(self.tmp.name, "Raw", "a.mp4"), "w").close()
        self.assertEqual(v.list_raw(), "a.mp4")
        self.assertEqual(v.list_renders(), "no files in Render")

    def test_captions_flag_defaults_to_auto_and_rejects_bad_values(self):
        open(os.path.join(self.tmp.name, "Raw", "talk.mp4"), "w").close()
        with mock.patch.object(v.subprocess, "run") as run:
            run.return_value = mock.Mock(returncode=0, stdout="done\n", stderr="")
            v.mgen("talk.mp4")
            argv = run.call_args[0][0]
            self.assertEqual(argv[argv.index("--captions") + 1], "auto")
            v.mgen("talk.mp4", captions="off")
            argv = run.call_args[0][0]
            self.assertEqual(argv[argv.index("--captions") + 1], "off")
            out = v.mgen("talk.mp4", captions="loud")
            self.assertTrue(out.startswith("error: bad captions value"), out)
            self.assertEqual(run.call_count, 2)
