"""Offline tests for scripts/youtube_trends/store.py (fake Cypher runner, no Neo4j)."""

import unittest

from scripts.youtube_trends import store


class FakeRun:
    def __init__(self, known_ids=()):
        self.known_ids = set(known_ids)
        self.calls = []

    def __call__(self, cypher, **params):
        self.calls.append((cypher, params))
        if "RETURN v.video_id AS id" in cypher:
            return [{"id": i} for i in params["ids"] if i in self.known_ids]
        return []


def item(vid, views=10, likes=1):
    return {"video_id": vid, "title": f"t-{vid}", "channel_id": "c1",
            "channel_title": "Chan", "published_at": "2026-11-01T00:00:00Z",
            "views": views, "likes": likes}


class StoreTests(unittest.TestCase):
    def test_init_creates_constraint_and_index(self):
        fake = FakeRun()
        store.init(fake)
        joined = " ".join(c for c, _ in fake.calls)
        self.assertIn("CONSTRAINT yt_video_id", joined)
        self.assertIn("INDEX yt_run_id", joined)

    def test_seen_ids_returns_only_known(self):
        fake = FakeRun(known_ids={"a"})
        self.assertEqual(store.seen_ids(fake, ["a", "b"]), {"a"})

    def test_seen_ids_empty_input_makes_no_call(self):
        fake = FakeRun()
        self.assertEqual(store.seen_ids(fake, []), set())
        self.assertEqual(fake.calls, [])

    def test_record_run_counts_new_and_seen(self):
        fake = FakeRun(known_ids={"a"})
        result = store.record_run(fake, "run-1", "US", [item("a"), item("b"), item("c")])
        self.assertEqual(result, {"new": 2, "seen": 1})

    def test_record_run_writes_views_and_region(self):
        fake = FakeRun()
        store.record_run(fake, "run-1", "US", [item("a", views=99, likes=7)])
        run_calls = [p for c, p in fake.calls if "MERGE (r:YtRun" in c]
        self.assertEqual(run_calls[0]["region"], "US")
        write = [p for c, p in fake.calls if "UNWIND $rows" in c][0]
        self.assertEqual(write["rows"][0]["views"], 99)
        self.assertEqual(write["rows"][0]["likes"], 7)
        self.assertEqual(write["run_id"], "run-1")

    def test_record_run_skips_items_without_id(self):
        fake = FakeRun()
        result = store.record_run(fake, "run-2", "US", [{"title": "no id"}])
        self.assertEqual(result, {"new": 0, "seen": 0})
        self.assertFalse(any("UNWIND $rows" in c for c, _ in fake.calls))

    def test_run_summary_orders_by_views(self):
        fake = FakeRun()
        store.run_summary(fake, "run-1")
        cypher, params = fake.calls[-1]
        self.assertIn("ORDER BY s.views DESC", cypher)
        self.assertEqual(params, {"run_id": "run-1"})


if __name__ == "__main__":
    unittest.main()
