import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from router import config, workspace


class WorkspaceTest(unittest.TestCase):
    def test_override_precedence_and_list_joining(self):
        environ = {"CC_WORKSPACE": "dotenv"}
        config._apply_overrides({"workspace": "dashboard", "host_accept_paths": ["one", "two"],
                                 "accept_env_passthrough": ["A", "B"]}, {"CC_WORKSPACE"}, environ)
        self.assertEqual(environ["CC_WORKSPACE"], "dotenv")
        self.assertEqual(environ["TOKENFRUGAL_HOST_ACCEPT_PATHS"], "one" + os.pathsep + "two")
        self.assertEqual(environ["TOKENFRUGAL_ACCEPT_ENV_PASSTHROUGH"], "A,B")

    def test_parse_host_accept_drops_missing_path_and_warns(self):
        with tempfile.TemporaryDirectory() as root:
            paths, warnings = config._parse_host_accept(root + os.pathsep + os.path.join(root, "missing"))
            self.assertEqual(paths, frozenset({os.path.normcase(os.path.realpath(root))}))
            self.assertEqual(len(warnings), 1)

    def test_host_accept_exact_root_and_protected_files(self):
        with tempfile.TemporaryDirectory() as root:
            key = os.path.normcase(os.path.realpath(root))
            with mock.patch.object(config, "HOST_ACCEPT_PATHS", frozenset({key})):
                ws = workspace.load_workspace(root)
            self.assertTrue(ws.host_accept)
            self.assertFalse(workspace.denied("ordinary.py", set(), ws))
            with mock.patch.object(workspace, "PROTECTED_ALWAYS", frozenset({os.path.normcase(os.path.realpath(Path(root)/".env"))})):
                self.assertTrue(workspace.denied(".env", set(), ws))

    def test_to_rel_and_env(self):
        with tempfile.TemporaryDirectory() as root:
            with mock.patch.dict(os.environ, {"TF_TEST_PASSTHROUGH": "secret"}):
                ws = workspace.Workspace(root, os.path.normcase(os.path.realpath(root)), False,
                                         ("TF_TEST_PASSTHROUGH",), None)
                env = workspace.accept_env(ws, {})
            self.assertEqual(workspace.to_rel(ws, "/workspace/a.py"), "a.py")
            self.assertEqual(workspace.to_rel(ws, str(Path(root) / "a.py")), "a.py")
            self.assertEqual(env["TF_TEST_PASSTHROUGH"], "secret")

    def test_child_of_allowed_workspace_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as root:
            key = os.path.normcase(os.path.realpath(root))
            child = Path(root) / "child"
            child.mkdir()
            with mock.patch.object(config, "HOST_ACCEPT_PATHS", frozenset({key})):
                self.assertFalse(workspace.load_workspace(str(child)).host_accept)

    def test_legacy_task_files_keeps_declared_new_module_and_skips_prose_tokens(self):
        with tempfile.TemporaryDirectory() as root:
            ws = workspace.load_workspace(root)
            files = workspace.legacy_task_files(ws, "Create newmod.py; mention e.g. and version 1.2.")
            self.assertEqual(files, ("newmod.py",))


if __name__ == "__main__":
    unittest.main()
