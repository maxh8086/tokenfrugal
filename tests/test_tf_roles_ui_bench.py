import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import tf_roles_ui


class BenchSummaryTest(unittest.TestCase):
    def test_summary_sums_realworld(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "bench" / "m").mkdir(parents=True)
            data = {"results": {"realworld": {
                "a": {"verified": 2, "ran": 2, "s": {"p50": 4.0}},
                "b": {"verified": 1, "ran": 2, "s": {"p50": 6.0}}}}}
            (root / "bench" / "m" / "r.json").write_text(json.dumps(data))
            with mock.patch.object(tf_roles_ui.config, "ROOT", root):
                s = tf_roles_ui.bench_summary("m")
                self.assertEqual((s["verified"], s["ran"], s["cases"], s["pct"]), (3, 4, 2, 75))
                self.assertEqual(s["s_per_case"], 5.0)
                self.assertIsNone(tf_roles_ui.bench_summary("missing"))


class BenchStartTest(unittest.TestCase):
    def setUp(self):
        tf_roles_ui.JOB.update(running=False, log=[], summary=None)

    def test_needs_exactly_one_target(self):
        with self.assertRaises(ValueError):
            tf_roles_ui.bench_start({})
        with self.assertRaises(ValueError):
            tf_roles_ui.bench_start({"model": "x", "url": "http://a"})

    def test_url_scheme_checked(self):
        with self.assertRaises(ValueError):
            tf_roles_ui.bench_start({"url": "ftp://a"})

    def test_rejects_concurrent_and_clamps_n(self):
        with mock.patch.object(tf_roles_ui.threading, "Thread") as th:
            tf_roles_ui.bench_start({"model": "llama3.2:3b", "n": 99})
            cmd = th.call_args.kwargs["args"][0]
            self.assertEqual(cmd[cmd.index("--n") + 1], "10")
            with self.assertRaises(ValueError):
                tf_roles_ui.bench_start({"model": "y"})


if __name__ == "__main__":
    unittest.main()
