"""Studio request folder: one active run, one waiting request, single claimer, GPU wait, expiry, validation."""
import asyncio
import os
import time
from unittest import mock

from router import gpu_lease, store, studio
from tests.studio_support import StudioEnv


class QueueTests(StudioEnv):
    def test_second_start_is_refused_while_a_run_is_active(self):
        store.create_run("slug-a", "pipeline", {"topic": "t"})  # queued with a fresh heartbeat counts as active
        result = studio.enqueue("collect", {})
        self.assertFalse(result["ok"])
        self.assertIn("wait or cancel", result["message"])

    def test_second_request_waits_behind_the_first(self):
        self.assertTrue(studio.enqueue("collect", {})["ok"])
        second = studio.enqueue("collect", {})
        self.assertFalse(second["ok"])
        self.assertIn("already waiting", second["message"])

    def test_only_one_claimer_wins_a_request(self):
        studio.enqueue("collect", {})
        self.assertIsNotNone(studio.claim_once())
        self.assertIsNone(studio.claim_once())

    def test_claim_skips_a_request_another_claimer_moved_first(self):
        studio.enqueue("collect", {})
        real_replace = os.replace
        lost = []

        def lose_once(src, dst):
            if not lost:
                lost.append(src)
                raise FileNotFoundError(src)  # the other claimer's os.replace won
            return real_replace(src, dst)

        with mock.patch.object(studio.os, "replace", side_effect=lose_once):
            self.assertIsNone(studio.claim_once())
        self.assertIsNotNone(studio.claim_once())  # the request is still there for the next claim

    def test_run_shows_waiting_gpu_while_the_lease_is_held(self):
        rid = store.create_run("slug-a", "pipeline", {"topic": "t"})
        seen = []
        n = {"calls": 0}

        def lease(*a, **k):
            seen.append(store.get_run(rid)["status"])
            n["calls"] += 1
            if n["calls"] == 1:
                raise gpu_lease.GpuBusy("held")

        self.swap(gpu_lease, "check_for_ollama", lease)
        with mock.patch.object(studio, "GPU_POLL_SECONDS", 0):
            self.assertTrue(asyncio.run(studio._wait_for_gpu(rid)))
        self.assertEqual(seen, ["queued", "waiting_gpu"])

    def test_unclaimed_request_expires(self):
        studio.enqueue("collect", {})
        with mock.patch.object(studio, "STUDIO_CLAIM_TIMEOUT", 60):
            self.assertIsNone(studio.claim_once(now=time.time() + 3600))
        self.assertEqual(list(studio._requests_dir().glob("*.json")), [])
        kinds = [c.args[0] for c in self.emitted.call_args_list]
        self.assertIn("studio_request_expired", kinds)

    def test_refuses_store_bad_slugs_and_blank_topics(self):
        self.assertFalse(studio.enqueue("store", {})["ok"])
        self.assertFalse(studio.enqueue("pipeline", {"slug": "../etc", "topic": "t"})["ok"])
        self.assertFalse(studio.enqueue("pipeline", {"slug": "ok-slug", "topic": "  "})["ok"])
        self.assertEqual(list(studio._requests_dir().glob("*.json")), [])


if __name__ == "__main__":
    import unittest
    unittest.main()
