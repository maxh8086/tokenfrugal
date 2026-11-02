import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import tf_roles_ui


class BenchSummaryTest(unittest.TestCase):
    def test_summary_sums_roles(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "bench" / "m").mkdir(parents=True)
            data = {"results": {"roles": {
                # role a: two live passes, mean 3.0 s
                "a": {"runs": [{"ok": True, "infra": False, "s": 4.0}, {"ok": True, "infra": False, "s": 2.0}]},
                # role b: one live fail at 6.0 s; its infra run (marked ok) must count in neither total
                "b": {"runs": [{"ok": False, "infra": False, "s": 6.0}, {"ok": True, "infra": True, "s": 0.0}]}}}}
            (root / "bench" / "m" / "r.json").write_text(json.dumps(data))
            with mock.patch.object(tf_roles_ui.config, "ROOT", root):
                s = tf_roles_ui.bench_summary("m")
                self.assertEqual((s["verified"], s["ran"], s["cases"], s["pct"]), (2, 3, 2, 67))
                self.assertEqual(s["s_per_case"], 4.5)
                self.assertIsNone(tf_roles_ui.bench_summary("missing"))

    def test_summary_failed_roles_section_counts_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "bench" / "m").mkdir(parents=True)
            data = {"results": {"roles": {"error": "no result after 600s (section watchdog)"}}}
            (root / "bench" / "m" / "r.json").write_text(json.dumps(data))
            with mock.patch.object(tf_roles_ui.config, "ROOT", root):
                s = tf_roles_ui.bench_summary("m")
                self.assertEqual((s["verified"], s["ran"], s["cases"], s["pct"], s["s_per_case"]), (0, 0, 0, 0, None))


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
