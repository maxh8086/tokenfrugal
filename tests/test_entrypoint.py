import asyncio
import tomllib
import unittest
from pathlib import Path
from unittest import mock

from router import server, store


ROOT = Path(__file__).resolve().parents[1]


class EntrypointTest(unittest.TestCase):
    def test_main_is_project_script_target(self):
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertTrue(callable(server.main))
        self.assertEqual(project["project"]["scripts"]["tokenfrugal-router"], "router.server:main")

    def test_dependencies_are_pinned(self):
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertTrue(project["project"]["dependencies"])
        for dependency in project["project"]["dependencies"]:
            self.assertIn("==", dependency, dependency)

    def test_requirements_pins_equal_pyproject_pins(self):
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        pins = {line.strip() for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines() if line.strip()}
        self.assertEqual(pins, set(project["project"]["dependencies"]))

    def test_package_data_globs_match_files(self):
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        for pattern in project["tool"]["setuptools"]["package-data"]["router"]:
            self.assertTrue(list((ROOT / "router").glob(pattern)), pattern)

    def test_empty_task_is_refused_without_creating_a_row(self):
        with mock.patch.object(store, "create") as create:
            reply = asyncio.run(server.dispatch_task(agent="builder", task=" \t ", task_type="fix bug"))
        self.assertEqual(reply, "task is empty: send the task text")
        create.assert_not_called()

    def test_docs_register_the_installed_router_command(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        claude = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertIn("pip install -e .", readme)
        self.assertIn("python scripts/doctor.py", readme)
        self.assertIn('command = "tokenfrugal-router"', readme)
        self.assertIn('"command": "tokenfrugal-router"', readme)
        self.assertIn('"command": "tokenfrugal-router"', claude)
        for text in (readme, claude):
            self.assertNotIn('"-m", "router.server"', text)
            self.assertNotIn('"command": "python"', text)


if __name__ == "__main__":
    unittest.main()
