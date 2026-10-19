import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "Benchmark" / "script"))
import csvstore  # noqa: E402

COLS = ["tag", "score", "date"]


def write(p, rows):
    with open(p, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)


class CsvStoreTest(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.csv = self.d / "b.csv"
        self.log = self.d / "runs.jsonl"

    def rows(self):
        return list(csv.DictReader(self.csv.open(encoding="utf-8")))

    def test_new_file(self):
        self.assertIsNone(csvstore.append_row(self.csv, COLS, {"tag": "a", "score": "1"}, self.log))
        self.assertEqual(self.rows()[0]["tag"], "a")

    def test_append_backs_up_and_logs(self):
        csvstore.append_row(self.csv, COLS, {"tag": "a"}, self.log)
        b = csvstore.append_row(self.csv, COLS, {"tag": "b"}, self.log)
        self.assertTrue(b.exists())
        self.assertEqual([r["tag"] for r in self.rows()], ["a", "b"])
        self.assertEqual(len(self.log.read_text().splitlines()), 2)
        self.assertEqual(json.loads(self.log.read_text().splitlines()[1])["tag"], "b")

    def test_narrow_header_migrates_by_name(self):
        write(self.csv, [["tag", "score"], ["a", "5"]])
        csvstore.append_row(self.csv, COLS, {"tag": "b", "date": "d"}, self.log)
        r = self.rows()
        self.assertEqual((r[0]["tag"], r[0]["score"], r[0]["date"]), ("a", "5", ""))

    def test_duplicate_header_refused_and_untouched(self):
        write(self.csv, [["tag", "tag", "score"], ["a", "x", "5"]])
        before = self.csv.read_text()
        with self.assertRaises(csvstore.CsvSchemaError):
            csvstore.append_row(self.csv, COLS, {"tag": "b"}, self.log)
        self.assertEqual(self.csv.read_text(), before)
        self.assertEqual(len(self.log.read_text().splitlines()), 1)  # run still logged

    def test_unknown_column_refused(self):
        write(self.csv, [["tag", "mystery"], ["a", "x"]])
        with self.assertRaises(csvstore.CsvSchemaError):
            csvstore.append_row(self.csv, COLS, {"tag": "b"}, self.log)

    def test_shifted_row_refused(self):
        write(self.csv, [["tag", "score", "date"], ["a", "5"]])
        with self.assertRaises(csvstore.CsvSchemaError):
            csvstore.append_row(self.csv, COLS, {"tag": "b"}, self.log)


if __name__ == "__main__":
    unittest.main()


class OllamaParamsTest(unittest.TestCase):
    def test_rows_prefer_ollama_figure_over_tag(self):
        from scripts import bench_csv
        case = {"verified": "1/1", "ran": "1/1", "s": {"mean": 2.0}}
        res = {cid: case for cid, _, _ in bench_csv.LAYOUT}
        data = {"tag": "x-4b", "results": {"realworld": res}, "model_params": {"builder": "3.8B"}}
        self.assertEqual(bench_csv.rows(data)[0][1], "3.8B")
        del data["model_params"]
        self.assertEqual(bench_csv.rows(data)[0][1], "4B")

    def test_unreachable_endpoint_gives_blank(self):
        from scripts import bench_csv
        self.assertEqual(bench_csv.ollama_params("m", "http://127.0.0.1:1"), "")
