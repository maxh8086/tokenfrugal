import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "Benchmark" / "script"))

import merge_legacy_coding as m  # noqa: E402
import store  # noqa: E402


class LegacyCoding(unittest.TestCase):
    # results/coding/ was deleted 2026-10-28 after its 28 runs were merged into coder.csv as history.
    # These checks need that folder, so they skip when it is absent.
    def setUp(self):
        if not (m.RESULTS / "coding").exists():
            self.skipTest("results/coding/ removed; legacy history already in coder.csv")

    def test_legacy_rows_are_history_only(self):
        rows = m.legacy_rows()
        self.assertEqual(len(rows), 28 * 6)
        self.assertTrue(all(r["superseded"] == "yes" for r in rows))
        self.assertTrue(all(r["suite"] == "coding" and r["role"] == "builder" for r in rows))

    def test_legacy_rows_do_not_change_summary(self):
        # Adding the superseded history must leave every summary value unchanged.
        current = store._read(m.RESULTS / store.TESTS["coding"]["file"], store.ROLE_COLS)
        builders = [r for r in current if r["role"] == "builder" and r["superseded"] != "yes"]
        model = builders[0]["model"]
        models = {"builder": model, "thinker": ""}
        without = store.summarize(models, current)
        with_legacy = store.summarize(models, current + m.legacy_rows())
        self.assertEqual(without, with_legacy)


if __name__ == "__main__":
    unittest.main()
