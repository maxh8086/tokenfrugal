"""Approved templates: manual approval, matching order, the 2-template and 1500-token budget, and placement before the task."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from router import store


class TemplatesTest(unittest.TestCase):
    def setUp(self):
        self.patch = mock.patch.object(store, "DB_PATH", Path(tempfile.mkdtemp()) / "t.db")
        self.patch.start()

    def tearDown(self):
        self.patch.stop()

    def add(self, role="builder", title="rename helper", body="Use the rename rule.", tags=("rename",), task_type=""):
        return store.add_template(role, title, body, approved_by="vaibh", task_type=task_type, tags=list(tags))

    def test_add_needs_manual_approval(self):
        with self.assertRaises(ValueError):
            store.add_template("builder", "t", "b", approved_by="  ")

    def test_other_role_templates_never_match(self):
        self.add(role="reviewer", title="rename helper", tags=["rename"])
        self.assertEqual(store.pick_templates("builder", "rename the helper"), [])
        self.assertEqual(len(store.pick_templates("reviewer", "rename the helper")), 1)

    def test_retired_templates_never_match(self):
        self.add(role="builder", title="rename helper", tags=["rename"])
        with store._db() as c:
            c.execute("UPDATE templates SET status='retired'")
        self.assertEqual(store.pick_templates("builder", "rename the helper"), [])

    def test_tag_overlap_beats_title_keywords(self):
        self.add(title="helper notes", body="by title", tags=[])
        self.add(title="other", body="by tag", tags=["rename"])
        picked = store.pick_templates("builder", "rename the helper")
        self.assertEqual(picked[0]["body"], "by tag")

    def test_no_match_no_template(self):
        self.add(title="rename helper", tags=["rename"])
        self.assertEqual(store.pick_templates("builder", "write a parser"), [])
        self.assertEqual(store.with_templates("builder", "write a parser"), "write a parser")

    def test_at_most_two_templates(self):
        for n in range(4):
            self.add(title=f"rename {n}", body=f"rule {n}", tags=["rename"])
        self.assertEqual(len(store.pick_templates("builder", "rename it")), store.TEMPLATE_MAX)

    def test_budget_skips_templates_that_do_not_fit(self):
        self.add(title="big", body="x" * 6000, tags=["rename"])  # about 1500 tokens: fills the budget alone
        self.add(title="small", body="short rule", tags=["rename"])
        picked = store.pick_templates("builder", "rename it", budget=100)
        self.assertEqual([p["title"] for p in picked], ["small"])

    def test_body_can_be_a_file_path(self):
        path = Path(tempfile.mkdtemp()) / "rule.md"
        path.write_text("rule from a file", encoding="utf-8")
        self.add(title="file rule", body=str(path), tags=["rename"])
        self.assertEqual(store.pick_templates("builder", "rename it")[0]["body"], "rule from a file")

    def test_with_templates_puts_templates_before_task(self):
        self.add(title="rename helper", body="Use the rename rule.", tags=["rename"])
        prompt = store.with_templates("builder", "rename the helper")
        self.assertTrue(prompt.startswith("[template: rename helper]\nUse the rename rule."))
        self.assertTrue(prompt.endswith("[task]\nrename the helper"))

    def test_use_is_counted(self):
        self.add(title="rename helper", tags=["rename"])
        store.pick_templates("builder", "rename it")
        with store._db() as c:
            (uses,) = c.execute("SELECT uses FROM templates").fetchone()
        self.assertEqual(uses, 1)


if __name__ == "__main__":
    unittest.main()
