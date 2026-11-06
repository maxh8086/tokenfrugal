"""scripts/content_pipeline.py: dry plan output, the --confirm gate and slug validation. No model is called."""
import contextlib
import io
import unittest
from unittest import mock

from router import store
from scripts import content_pipeline as cp


class DryPlanTests(unittest.TestCase):
    def run_cli(self, argv, last=None):
        out = io.StringIO()
        with mock.patch.object(store, "last_for", return_value=last), \
                mock.patch.object(cp, "run_pipeline") as run, \
                contextlib.redirect_stdout(out):
            rc = cp.main(argv)
        return rc, out.getvalue(), run

    def test_dry_plan_lists_seven_stages_in_order_and_calls_nothing(self):
        rc, text, run = self.run_cli(["ai-banking-2026", "--topic", "AI in banking"])
        self.assertEqual(rc, 0)
        run.assert_not_called()
        self.assertIn("Dry run: no model was called", text)
        order = [text.index(f" {slug} ") for _, slug in cp.STAGES]
        self.assertEqual(order, sorted(order))
        self.assertIn("content/ai-banking-2026/", text)

    def test_dry_plan_shows_role_and_model_per_stage(self):
        _, text, _ = self.run_cli(["ai-banking-2026", "--topic", "x"])
        for _, slug in cp.STAGES:
            self.assertIn(slug, text)
        self.assertIn("content-editor", text)  # factcheck maps to the editor role
        self.assertIn("ts-llama3-1-8b-65536:latest", text)
        self.assertIn("ts-hf-co-bandtor-gemma-4-E4B-it-GGUF-65536:latest", text)

    def test_dry_plan_marks_resume_and_skip_states(self):
        def last_of(agent, slug=None):  # last_for(agent, slug): the dry plan passes the slug it was given
            self.assertEqual(slug, "ai-banking-2026")
            if agent == "content-outline":
                return {"id": "abc123", "status": "done"}
            if agent == "content-factcheck":
                return {"id": "def456", "status": "failed"}
            return None
        out = io.StringIO()
        with mock.patch.object(store, "last_for", side_effect=last_of), contextlib.redirect_stdout(out):
            cp.main(["ai-banking-2026", "--topic", "x"])
        text = out.getvalue()
        self.assertIn("done, skipped", text)
        self.assertIn("resume task def456 (failed)", text)
        self.assertIn("new run", text)

    def test_confirm_flag_starts_the_pipeline(self):
        with mock.patch.object(cp, "run_pipeline", return_value=0) as run, contextlib.redirect_stdout(io.StringIO()):
            rc = cp.main(["ai-banking-2026", "--topic", "x", "--confirm"])
        self.assertEqual(rc, 0)
        run.assert_called_once_with("ai-banking-2026", "x")

    def test_invalid_slug_is_rejected_before_any_run(self):
        err = io.StringIO()
        with mock.patch.object(cp, "run_pipeline") as run, contextlib.redirect_stderr(err), \
                contextlib.redirect_stdout(io.StringIO()):
            rc = cp.main(["../etc", "--topic", "x", "--confirm"])
        self.assertEqual(rc, 2)
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
