import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from router import docker_mcp, media_workspace as mw, profile_sync, media_generator_mcp as v
from scripts import ensure_media_workspace as emw
from scripts import install_profiles as ip

ROOT = Path(__file__).resolve().parent.parent


class ResolutionOrder(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.od = self.tmp / "onedrive"

    def test_env_var_wins_over_onedrive_and_home(self):
        env = {"VIDEO_EDITOR_DIR": str(self.tmp / "custom"), "OneDrive": str(self.od)}
        self.assertEqual(mw.media_dir(env, self.home), Path(os.path.abspath(self.tmp / "custom")))

    def test_empty_env_var_is_ignored(self):
        env = {"VIDEO_EDITOR_DIR": "", "OneDrive": str(self.od)}
        self.assertEqual(mw.media_dir(env, self.home), self.od / "Videos" / "video-editor")

    def test_onedrive_env_used_without_checking_folder(self):
        self.assertFalse(self.od.exists())
        self.assertEqual(mw.media_dir({"OneDrive": str(self.od)}, self.home), self.od / "Videos" / "video-editor")

    def test_profile_onedrive_folder_used_when_it_exists(self):
        (self.home / "OneDrive").mkdir()
        self.assertEqual(mw.media_dir({}, self.home), self.home / "OneDrive" / "Videos" / "video-editor")

    def test_plain_home_when_no_onedrive(self):
        self.assertEqual(mw.media_dir({}, self.home), self.home / "Videos" / "video-editor")

    def test_default_reads_process_environment(self):
        custom = self.tmp / "custom"
        with mock.patch.dict(os.environ, {"VIDEO_EDITOR_DIR": str(custom)}):
            self.assertEqual(mw.media_dir(), Path(os.path.abspath(custom)))

    def test_resolving_creates_nothing(self):
        mw.media_dir({}, self.home)
        self.assertFalse((self.home / "Videos").exists())


class RenderAndLayoutConfig(unittest.TestCase):
    def test_defaults_when_unset(self):
        with mock.patch.dict(os.environ, {"VIDEO_EDITOR_LAYOUT": "", "VIDEO_EDITOR_RENDER_DIR": ""}):
            self.assertEqual(mw.render_name(), "Render")
            self.assertEqual(mw.layout(), ("Raw", "References", "Render", "content", "analyst", "analyst/daily"))

    def test_env_sets_render_name_and_layout(self):
        env = {"VIDEO_EDITOR_RENDER_DIR": "Final", "VIDEO_EDITOR_LAYOUT": "Raw, Work/tmp ,"}
        with mock.patch.dict(os.environ, env):
            self.assertEqual(mw.render_name(), "Final")
            self.assertEqual(mw.layout(), ("Raw", "Work/tmp", "Final"))
            self.assertEqual(mw.render_dir(Path("ws")), Path("ws") / "Final")
            self.assertEqual(mw.raw_dir(Path("ws")), Path("ws") / "Raw")

    def test_render_folder_is_always_created(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name) / "ws"
        with mock.patch.dict(os.environ, {"VIDEO_EDITOR_RENDER_DIR": "Final", "VIDEO_EDITOR_LAYOUT": "Raw"}):
            mw.ensure_tree(root)
        self.assertTrue((root / "Final").is_dir())
        self.assertFalse((root / "Render").exists())


class Tree(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "ws"
        patcher = mock.patch.dict(os.environ, {"VIDEO_EDITOR_LAYOUT": "", "VIDEO_EDITOR_RENDER_DIR": ""})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_ensure_creates_layout_then_is_idempotent(self):
        first = mw.ensure_tree(self.root)
        self.assertEqual([rel for rel, _ in first], ["."] + list(mw.layout()))
        self.assertTrue(all(status == "CREATED" for _, status in first))
        for rel in mw.layout():
            self.assertTrue((self.root / rel).is_dir(), rel)
        second = mw.ensure_tree(self.root)
        self.assertTrue(all(status == "OK" for _, status in second))

    def test_ensure_creates_no_files(self):
        mw.ensure_tree(self.root)
        self.assertEqual([p for p in self.root.rglob("*") if p.is_file()], [])

    def test_check_tree_creates_nothing(self):
        self.assertTrue(all(not ok for _, ok in mw.check_tree(self.root)))
        self.assertFalse(self.root.exists())


class ScriptCli(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "ws"
        patcher = mock.patch.dict(os.environ, {"VIDEO_EDITOR_DIR": str(self.root), "VIDEO_EDITOR_LAYOUT": "",
                                               "VIDEO_EDITOR_RENDER_DIR": ""})
        patcher.start()
        self.addCleanup(patcher.stop)

    def _run(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = emw.run(argv)
        return rc, out.getvalue()

    def test_check_on_missing_folder_exits_1_and_creates_nothing(self):
        rc, _ = self._run(["--check"])
        self.assertEqual(rc, 1)
        self.assertFalse(self.root.exists())

    def test_check_on_partial_tree_exits_1_and_adds_nothing(self):
        (self.root / "Raw").mkdir(parents=True)
        rc, out = self._run(["--check"])
        self.assertEqual(rc, 1)
        self.assertIn("MISSING", out)
        self.assertFalse((self.root / "Render").exists())

    def test_check_on_complete_tree_exits_0(self):
        self._run([])
        rc, out = self._run(["--check"])
        self.assertEqual(rc, 0)
        self.assertNotIn("MISSING", out)

    def test_default_run_creates_and_reports_created(self):
        rc, out = self._run([])
        self.assertEqual(rc, 0)
        self.assertIn("CREATED", out)
        self.assertIn(str(self.root), out)
        self.assertTrue((self.root / "analyst" / "daily").is_dir())

    def test_second_default_run_is_idempotent(self):
        self._run([])
        rc, out = self._run([])
        self.assertEqual(rc, 0)
        self.assertNotIn("CREATED", out)

    def test_print_path_prints_only_the_path_and_creates_nothing(self):
        rc, out = self._run(["--print-path"])
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), str(self.root))
        self.assertFalse(self.root.exists())

    def test_unusable_path_returns_2(self):
        self.root.parent.mkdir(parents=True, exist_ok=True)
        self.root.write_text("a file, not a folder", encoding="utf-8")
        rc, _ = self._run([])
        self.assertEqual(rc, 2)


class ProfilePlaceholders(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)

    def test_install_fill_replaces_media_workspace_and_repo(self):
        out = ip.fill("a: __MEDIA__:/workspace:rw\nb: __WORKSPACE__:/w\nc: __REPO__\n", "C:/ws", "C:/m")
        self.assertIn("C:/m:/workspace:rw", out)
        self.assertIn("C:/ws:/w", out)
        self.assertNotIn("__MEDIA__", out)
        self.assertNotIn("__WORKSPACE__", out)

    def test_media_roles_mount_the_media_folder_read_write(self):
        for name in ("content-writer", "content-analyst", "media-generator"):
            text = (ROOT / "profiles" / f"{name}.yaml").read_text(encoding="utf-8")
            self.assertIn("__MEDIA__:/workspace:rw", text, name)
            self.assertNotIn("__WORKSPACE__", text, name)

    def test_docker_mcp_profile_text_fills_media(self):
        p = self.tmp / "p.yaml"
        p.write_text("- __MEDIA__:/workspace:rw\n", encoding="utf-8")
        with mock.patch.dict(os.environ, {"VIDEO_EDITOR_DIR": str(self.tmp / "m")}):
            text = docker_mcp.profile_text(p, "C:/ws")
        self.assertIn((self.tmp / "m").as_posix() + ":/workspace:rw", text)

    def test_profile_sync_fills_media_and_records_it(self):
        pdir = self.tmp / "profiles"
        pdir.mkdir()
        (pdir / "media-generator.yaml").write_text("- __MEDIA__:/workspace:rw\n", encoding="utf-8")
        marker = self.tmp / "marker.json"
        seen = []

        def fake(argv, **kw):
            if argv[:4] == ["docker", "mcp", "profile", "import"]:
                seen.append(Path(argv[4]).read_text(encoding="utf-8"))
            return mock.Mock(returncode=0, stdout="", stderr="")

        changed = profile_sync.ensure_profiles("C:/ws", marker=marker, profiles_dir=pdir, run=fake, media="C:/media")
        self.assertTrue(changed)
        self.assertEqual(seen, ["- C:/media:/workspace:rw\n"])
        self.assertEqual(json.loads(marker.read_text(encoding="utf-8")), {"workspace": "C:/ws", "media": "C:/media"})

    def test_media_path_change_triggers_reimport(self):
        pdir = self.tmp / "profiles"
        pdir.mkdir()
        (pdir / "build.yaml").write_text("x: __WORKSPACE__\n", encoding="utf-8")
        marker = self.tmp / "marker.json"
        ok = mock.Mock(returncode=0, stdout="", stderr="")

        def run(argv, **kw):
            return ok

        self.assertTrue(profile_sync.ensure_profiles("C:/ws", marker=marker, profiles_dir=pdir, run=run, media="C:/m1"))
        self.assertFalse(profile_sync.ensure_profiles("C:/ws", marker=marker, profiles_dir=pdir, run=run, media="C:/m1"))
        self.assertTrue(profile_sync.ensure_profiles("C:/ws", marker=marker, profiles_dir=pdir, run=run, media="C:/m2"))


class VeditExportsResolvedFolder(unittest.TestCase):
    def test_mgen_passes_the_resolved_folder_to_compose(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        ws = Path(tmp.name)
        (ws / "Raw").mkdir()
        (ws / "Raw" / "clip.mp4").write_bytes(b"x")
        with mock.patch.dict(os.environ, {"VIDEO_EDITOR_DIR": str(ws)}), \
             mock.patch.object(v.subprocess, "run") as run:
            run.return_value = mock.Mock(returncode=0, stdout="", stderr="")
            v.mgen("clip.mp4")
        self.assertEqual(run.call_args.kwargs["env"]["VIDEO_EDITOR_DIR"], str(ws))


if __name__ == "__main__":
    unittest.main()
