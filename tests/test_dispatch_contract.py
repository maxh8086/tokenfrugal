"""dispatch_task needs a task_type, and list_roles shows approved templates for display only."""
import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from router import server, store


class TaskTypeRequiredTest(unittest.TestCase):
    def setUp(self):
        self.patch = mock.patch.object(store, "DB_PATH", Path(tempfile.mkdtemp()) / "t.db")
        self.patch.start()

    def tearDown(self):
        self.patch.stop()

    def test_missing_or_blank_task_type_is_refused_before_any_work(self):
        for task_type in ("", "   "):
            reply = asyncio.run(server.dispatch_task(agent="engineering-code-reviewer", task="x", task_type=task_type))
            self.assertIn("give task_type", reply)
        self.assertEqual(store.list_templates(), [])


class ListRolesTemplatesTest(unittest.TestCase):
    def setUp(self):
        self.patch = mock.patch.object(store, "DB_PATH", Path(tempfile.mkdtemp()) / "t.db")
        self.patch.start()

    def tearDown(self):
        self.patch.stop()

    def test_none_when_no_templates_approved(self):
        self.assertTrue(server.list_roles().endswith("approved templates (applied only when a dispatch_task task_type and wording match):\n  none"))

    def test_approved_template_is_listed_but_not_applied(self):
        store.add_template("builder", "rename helper", "Use the rename rule.", approved_by="vaibh", task_type="rename", tags=["rename"])
        text = server.list_roles()
        self.assertIn("#1 builder: rename helper | task_type rename | uses 0", text)
        self.assertEqual(store.list_templates()[0]["uses"], 0)  # display does not count as a use


if __name__ == "__main__":
    unittest.main()
