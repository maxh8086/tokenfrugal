"""Studio store: one node per (source, item_id) however often the same batch is stored.

Uses a fake Neo4j transaction that applies the same MERGE rule as WRITE_CYPHER (create once, keep the first copy).
The live check against the real Neo4j is separate and is not run here.
"""
import unittest
from unittest import mock

from router import studio_store
from router.studio_store import EMBED_DIMS, StoreRefused, WRITE_CYPHER, write_items


class FakeNeo4j:
    """Applies the MERGE/ON CREATE rule of WRITE_CYPHER in memory."""

    def __init__(self):
        self.nodes = {}
        self.calls = 0

    def __call__(self, cypher, params):
        self.calls += 1
        assert cypher == WRITE_CYPHER
        for it in params["items"]:
            if it["key"] not in self.nodes:  # ON CREATE only
                self.nodes[it["key"]] = dict(it, run_id=params["run_id"])
        return len(params["items"])


def item(item_id="a1", source="reddit", title="A title", body="body text", url="https://example.com/a1", vec=0.1):
    return {"source": source, "item_id": item_id, "title": title, "body": body, "url": url,
            "embedding": [vec] * EMBED_DIMS}


class IdempotenceTests(unittest.TestCase):
    def test_storing_the_same_batch_twice_leaves_one_node_per_item(self):
        db = FakeNeo4j()
        batch = [item("a1"), item("b2", source="hn")]
        write_items(db, batch, run_id=1)
        write_items(db, batch, run_id=2)
        self.assertEqual(sorted(db.nodes), ["hn|b2", "reddit|a1"])
        self.assertEqual(db.calls, 2)

    def test_a_repeat_store_does_not_overwrite_the_first_copy(self):
        db = FakeNeo4j()
        write_items(db, [item("a1", title="first")], run_id=1)
        write_items(db, [item("a1", title="changed")], run_id=2)
        self.assertEqual(db.nodes["reddit|a1"]["title"], "first")
        self.assertEqual(db.nodes["reddit|a1"]["run_id"], 1)

    def test_the_same_item_id_under_two_sources_is_two_nodes(self):
        db = FakeNeo4j()
        write_items(db, [item("x1", source="reddit"), item("x1", source="hn")], run_id=1)
        self.assertEqual(sorted(db.nodes), ["hn|x1", "reddit|x1"])


class RefusalTests(unittest.TestCase):
    def assert_refused_without_write(self, batch, fragment):
        db = FakeNeo4j()
        with self.assertRaises(StoreRefused) as ctx:
            write_items(db, batch, run_id=1)
        self.assertIn(fragment, str(ctx.exception))
        self.assertEqual(db.calls, 0, "a refused batch must not reach the database")
        self.assertEqual(db.nodes, {})

    def test_empty_batch_is_refused(self):
        self.assert_refused_without_write([], "non-empty")

    def test_one_bad_item_refuses_the_whole_batch(self):
        self.assert_refused_without_write([item("a1"), item("b2", source="myspace")], "item 1: unknown source")

    def test_unknown_source(self):
        self.assert_refused_without_write([item(source="twitter")], "unknown source")

    def test_missing_or_blank_item_id(self):
        self.assert_refused_without_write([item(item_id="   ")], "item_id missing")

    def test_title_over_limit_and_empty_title(self):
        self.assert_refused_without_write([item(title="x" * 501)], "title is over 500")
        self.assert_refused_without_write([item(title="  ")], "title is empty")

    def test_body_over_limit(self):
        self.assert_refused_without_write([item(body="y" * 20001)], "body is over 20000")

    def test_embedding_wrong_length_or_not_numbers(self):
        short = item()
        short["embedding"] = [0.1] * 10
        self.assert_refused_without_write([short], "embedding must have 384 numbers")
        text = item()
        text["embedding"] = ["0.1"] * EMBED_DIMS
        self.assert_refused_without_write([text], "embedding has a non-number")

    def test_duplicate_item_in_one_batch(self):
        self.assert_refused_without_write([item("a1"), item("a1")], "same item twice")

    def test_batch_over_the_limit(self):
        with mock.patch.object(studio_store, "MAX_ITEMS", 2):
            self.assert_refused_without_write([item("a1"), item("b2"), item("c3")], "at most 2 items")

    def test_refusal_names_the_index_and_rule_but_not_the_content(self):
        secret = "PRIVATE-BODY-TEXT"
        bad = item("zz", title="x" * 600)
        bad["body"] = secret
        with self.assertRaises(StoreRefused) as ctx:
            studio_store.validate_items([item("a1"), bad])
        msg = str(ctx.exception)
        self.assertIn("item 1", msg)
        self.assertNotIn(secret, msg)
        self.assertNotIn("zz", msg)


if __name__ == "__main__":
    unittest.main()
