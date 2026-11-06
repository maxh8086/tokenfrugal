"""studio_run 'store': today's collector files are written once each, through a fake Neo4j write."""
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from router import studio, studio_store
from router.studio_store import EMBED_DIMS, StoreRefused
from tests.studio_support import StudioEnv


def fake_embed(texts):
    return [[0.5] * EMBED_DIMS for _ in texts]


class StoreRunTests(StudioEnv):
    def setUp(self):
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.media = Path(self._tmp.name)
        self.raw = self.media / "content" / "trends" / "raw"
        self.raw.mkdir(parents=True)
        self.day = date.today().isoformat()
        self.patches = [
            mock.patch.object(studio.media_workspace, "media_dir", return_value=self.media),
            mock.patch.object(studio_store, "embed", side_effect=fake_embed),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self._tmp.cleanup()
        super().tearDown()

    def write_raw(self, name, items):
        (self.raw / f"{self.day}-{name}.json").write_text(json.dumps(items), encoding="utf-8")

    def run_store(self):
        rid = studio.store.create_run("trends", "store", {})
        with mock.patch.object(studio_store, "neo4j_write", side_effect=self.fake_write) as w:
            rc = studio.store_collected(rid)
        return rid, rc, w

    def fake_write(self, cypher, params):
        self.written = getattr(self, "written", {})
        for it in params["items"]:
            self.written.setdefault(it["key"], it)
        return len(params["items"])

    def test_stores_each_item_once_when_run_twice(self):
        self.write_raw("reddit-hn", [{"title": "A", "url": "https://www.reddit.com/r/x/a"}])
        self.write_raw("rss", [{"title": "B", "url": "https://example.com/b", "body": "text"}])
        rid, rc, _ = self.run_store()
        self.assertEqual(rc, 0)
        self.assertEqual(len(self.written), 2)
        self.assertEqual(sorted(self.written), sorted(["reddit|" + studio_store.item_id_for("https://www.reddit.com/r/x/a"), "rss|" + studio_store.item_id_for("https://example.com/b")]))
        rid2, rc2, _ = self.run_store()
        self.assertEqual(rc2, 0)
        self.assertEqual(len(self.written), 2)  # the fake keeps the first copy, as MERGE does

    def test_a_refused_file_fails_the_run_without_writing(self):
        self.write_raw("reddit-hn", [{"title": "no url, no id"}])
        rid, rc, w = self.run_store()
        self.assertEqual(rc, 1)
        w.assert_not_called()
        self.assertEqual(studio.store.get_run(rid)["status"], "failed")
        self.assertNotIn("no url, no id", studio.store.get_run(rid)["error"] or "")

    def test_no_files_is_a_clean_empty_run(self):
        rid, rc, w = self.run_store()
        self.assertEqual(rc, 0)
        w.assert_not_called()

    def test_missing_fastembed_refuses_before_any_write(self):
        self.write_raw("rss", [{"title": "A", "url": "https://example.com/a"}])
        with mock.patch.object(studio_store, "embed", side_effect=StoreRefused("embedding model not installed: pip install fastembed")):
            rid, rc, w = self.run_store()
        self.assertEqual(rc, 1)
        w.assert_not_called()

    def test_source_comes_from_the_host_when_the_item_has_none(self):
        self.assertEqual(studio_store._source_from_url("https://news.ycombinator.com/item?id=1"), "hn")
        self.assertIsNone(studio_store._source_from_url("https://example.com/a"))

    def test_item_id_is_stable_for_a_url(self):
        self.assertEqual(studio_store.item_id_for("https://example.com/a"), studio_store.item_id_for("https://example.com/a"))
        self.assertEqual(len(studio_store.item_id_for("https://example.com/a")), 24)


if __name__ == "__main__":
    unittest.main()
