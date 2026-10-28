import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "Benchmark" / "script"))
import ranking  # noqa: E402

FIELDS = ["run_id", "date", "model", "case", "verified", "s_p50", "superseded"]


def _rows(d, name, rows):
    """Write hard_test.csv-style detail rows; hard_results reads these, not per-run JSON."""
    with open(Path(d) / name, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for run_id, model, verified, p50, superseded in rows:
            stamp = run_id.split("-")[0]  # run_id starts with YYYYMMDD
            w.writerow({"run_id": run_id, "date": f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}", "model": model,
                        "case": "hard_two_vulns", "verified": verified, "s_p50": p50, "superseded": superseded})


class HardResults(unittest.TestCase):
    def test_latest_run_wins_and_bad_rows_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            _rows(d, "hard_test.csv", [
                ("20260101-a", "m1", "1/3", 10, ""),
                ("20260102-a", "m1", "3/3", 20, ""),
                ("20260103-a", "m1", "2/3", 5, "yes"),  # superseded: ignored
                ("20260104-a", "m2", "x/3", 5, ""),     # malformed verified: skipped
            ])
            res = ranking.hard_results(Path(d) / "hard_test.csv")
        self.assertEqual(list(res), ["m1"])
        self.assertEqual((res["m1"]["a"], res["m1"]["n"]), (3, 3))
        self.assertEqual(res["m1"]["cases"]["hard_two_vulns"], (3, 3))
        self.assertEqual(res["m1"]["s"], 20)

    def test_missing_file_is_empty(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(ranking.hard_results(Path(d) / "absent.csv"), {})

    def test_md_empty_and_filled(self):
        self.assertIn("No hard-suite", ranking.hard_md({}))
        with tempfile.TemporaryDirectory() as d:
            _rows(d, "hard_test.csv", [("20260101-a", "m2", "2/3", 12, "")])
            out = ranking.hard_md(ranking.hard_results(Path(d) / "hard_test.csv"))
            self.assertIn('id="hd"', out)  # the table is drawn by the page from PASS_DATA
            self.assertEqual(ranking.PASS_DATA["hd"]["rows"][0]["model"], "m2")
            self.assertEqual((ranking.PASS_DATA["hd"]["rows"][0]["a"], ranking.PASS_DATA["hd"]["rows"][0]["n"]), (2, 3))


if __name__ == "__main__":
    unittest.main()
