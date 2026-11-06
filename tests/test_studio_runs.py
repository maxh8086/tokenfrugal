"""Studio run backend: pipeline runs per slug, resume after a kill, cancel at a stage boundary, status.
The stage runner is faked (tests/studio_support.py); no model is called."""
import asyncio
import time

from router import store, studio
from scripts import content_pipeline as cp
from tests.studio_support import STAGE_AGENTS, StudioEnv


class PipelineRunTests(StudioEnv):
    def test_second_slug_runs_all_seven_stages(self):
        asyncio.run(cp.run_pipeline("slug-a", "topic a"))
        self.assertEqual(self.calls, STAGE_AGENTS)
        self.calls.clear()
        asyncio.run(cp.run_pipeline("slug-b", "topic b"))
        self.assertEqual(self.calls, STAGE_AGENTS)  # slug-a's finished stages are not reused

    def test_last_for_only_sees_rows_of_the_same_slug(self):
        ra = store.create_run("slug-a", "pipeline")
        rb = store.create_run("slug-b", "pipeline")
        ta = store.create("content-outline", "content-outline", "x", run_id=ra)
        tb = store.create("content-outline", "content-outline", "x", run_id=rb)
        self.assertEqual(store.last_for("content-outline", "slug-a")["id"], ta)
        self.assertEqual(store.last_for("content-outline", "slug-b")["id"], tb)
        self.assertIsNone(store.last_for("content-outline", "slug-c"))

    def test_failed_stage_resumes_under_the_same_task(self):
        self.outcomes["content-factcheck"] = "failed"
        self.assertEqual(asyncio.run(cp.run_pipeline("slug-a", "t")), 1)
        first = store.last_for("content-factcheck", "slug-a")
        self.assertEqual(first["status"], "failed")
        self.calls.clear()
        self.outcomes.clear()
        self.assertEqual(asyncio.run(cp.run_pipeline("slug-a", "t")), 0)
        self.assertEqual(self.calls, STAGE_AGENTS[1:])  # outline is done, so it is skipped
        self.assertEqual(store.last_for("content-factcheck", "slug-a")["id"], first["id"])

    def test_killed_run_resumes_at_the_stage_it_was_on(self):
        # Mirrors a router that died mid-stage: the run and the factcheck row stop heartbeating.
        rid = store.create_run("slug-a", "pipeline", {"topic": "t"})
        outline = store.create("content-outline", "content-outline", "x", run_id=rid)
        store.update(outline, status="done")
        factcheck = store.create("content-factcheck", "content-editor", "x", run_id=rid)
        long_ago = time.time() - 10 * store.STALE_AFTER
        store.update(factcheck, heartbeat=long_ago)
        store.set_run(rid, status="running", stage="factcheck", heartbeat=long_ago)
        self.assertIsNone(store.active_run())
        store.sweep_stale("router stopped")
        self.assertEqual(store.get_run(rid)["status"], "failed")
        self.assertEqual(store.get(factcheck)["status"], "failed")
        self.assertEqual(asyncio.run(cp.run_pipeline("slug-a", "t")), 0)
        self.assertEqual(self.calls, STAGE_AGENTS[1:])
        self.assertEqual(store.last_for("content-factcheck", "slug-a")["id"], factcheck)

    def test_cancel_stops_at_the_next_stage_boundary(self):
        def cancel_after_outline(agent):
            if agent == "content-outline":
                store.request_cancel(store.list_runs(1)[0]["id"])

        self.on_call = cancel_after_outline
        self.assertEqual(asyncio.run(cp.run_pipeline("slug-a", "t")), 1)
        self.assertEqual(self.calls, ["content-outline"])
        self.assertEqual(store.list_runs(1)[0]["status"], "cancelled")


class StudioExecuteTests(StudioEnv):
    def test_queued_pipeline_request_runs_to_done(self):
        self.assertTrue(studio.enqueue("pipeline", {"slug": "slug-a", "topic": "t"})["ok"])
        rid, action, params = studio.claim_once()
        self.assertEqual(asyncio.run(studio.execute(rid, action, params)), 0)
        self.assertEqual(store.get_run(rid)["status"], "done")
        self.assertEqual(self.calls, STAGE_AGENTS)

    def test_status_reports_the_recent_run(self):
        rid = store.create_run("slug-a", "pipeline")
        store.finish_run(rid, "done")
        st = studio.status()
        self.assertIsNone(st["active"])
        text = studio.format_status(st)
        self.assertIn(f"run {rid} pipeline slug-a done", text)
        self.assertIn("active: none", text)

    def test_cancel_request_reports_the_active_run(self):
        rid = store.create_run("slug-a", "pipeline")
        self.assertIn("will stop at its next stage boundary", studio.start("cancel"))
        self.assertTrue(store.cancel_requested(rid))


if __name__ == "__main__":
    import unittest
    unittest.main()
