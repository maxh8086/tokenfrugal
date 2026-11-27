import os
import tempfile
import unittest
from unittest import mock
from pathlib import Path
from router import config, workspace


class DenylistTest(unittest.TestCase):
    def test_denylist_only_when_trusted_except_protected(self):
        with tempfile.TemporaryDirectory() as root:
            key = os.path.normcase(os.path.realpath(root))
            with mock.patch.object(config, "HOST_ACCEPT_PATHS", frozenset({key})):
                ws = workspace.load_workspace(root)
            self.assertTrue(workspace.denied(".github/workflows/a.yml", set(), ws))
            self.assertFalse(workspace.denied(".github/workflows/a.yml", set(), workspace.Workspace(root, key, False, (), None)))
            with mock.patch.object(workspace, "PROTECTED_ALWAYS", frozenset({os.path.normcase(os.path.realpath(os.path.join(root, "router", "config_overrides.json")))})):
                self.assertTrue(workspace.denied("router/config_overrides.json", set(), ws))

    def test_all_denylisted_dirs_and_names_and_allowed_exception(self):
        with tempfile.TemporaryDirectory() as root:
            key = os.path.normcase(os.path.realpath(root))
            with mock.patch.object(config, "HOST_ACCEPT_PATHS", frozenset({key})):
                ws = workspace.load_workspace(root)
            for path in (".git/config", ".venv/x", "venv/x", "node_modules/.bin/tool", ".github/workflows/check.yml",
                         "conftest.py", "sitecustomize.py", "usercustomize.py", "x.pth", "setup.py", "setup.cfg",
                         "pyproject.toml", "pytest.ini", "tox.ini", "noxfile.py", "package.json", ".npmrc", "Makefile", ".envrc"):
                with self.subTest(path=path):
                    self.assertTrue(workspace.denied(path, set(), ws))
                    self.assertFalse(workspace.denied(path, {path}, ws))

    def test_nested_and_indirect_denylist_paths_and_normal_nested_file(self):
        with tempfile.TemporaryDirectory() as root:
            key = os.path.normcase(os.path.realpath(root))
            with mock.patch.object(config, "HOST_ACCEPT_PATHS", frozenset({key})):
                ws = workspace.load_workspace(root)
            for path in ("sub/.git/config", "pkg/node_modules/.bin/x", "a/.github/workflows/x.yml",
                         "x/../.git/hooks/pre-commit"):
                with self.subTest(path=path):
                    self.assertTrue(workspace.denied(path, set(), ws))
            self.assertFalse(workspace.denied("sub/ordinary.py", set(), ws))
            try:
                (Path(root) / ".git").mkdir()
                (Path(root) / "sub").symlink_to(Path(root) / ".git", target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"directory symlinks unavailable: {exc}")
            self.assertTrue(workspace.denied("sub/config", set(), ws))


if __name__ == "__main__":
    unittest.main()
