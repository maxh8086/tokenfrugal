import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "Benchmark" / "script"))
import ranking  # noqa: E402


def _write(d, name, model, verified, p50):
    case = {"verified": verified, "s": {"p50": p50}}
    data = {"meta": {"thinker": model}, "results": {"realworld": {"hard_two_vulns": case}}}
    (Path(d) / name).write_text(json.dumps(data), encoding="utf-8")


class HardResults(unittest.TestCase):
    def test_latest_run_wins_and_bad_files_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "20260101-a.json", "m1", "1/3", 10)
            _write(d, "20260102-a.json", "m1", "3/3", 20)
            (Path(d) / "broken.json").write_text("{", encoding="utf-8")
            res = ranking.hard_results(d)
        self.assertEqual(list(res), ["m1"])
        self.assertEqual((res["m1"]["a"], res["m1"]["n"]), (3, 3))
        self.assertEqual(res["m1"]["cases"]["hard_two_vulns"], (3, 3))

    def test_md_empty_and_filled(self):
        self.assertIn("No hard-suite", ranking.hard_md({}))
        with tempfile.TemporaryDirectory() as d:
            _write(d, "x.json", "m2", "2/3", 12)
            self.assertIn("| `m2` | 2/3 |", ranking.hard_md(ranking.hard_results(d)))


if __name__ == "__main__":
    unittest.main()
