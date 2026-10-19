"""Offline tests for the opt-in hard thinker suite (BENCH_SUITE=hard, scripts/bench_real.py).
Each case's answer check must accept a correct sample answer and reject an empty or a wrong one.
No model, router or container is contacted."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import bench_real

GOOD = {
    "hard_multifile_bug": "The root cause is in money.py: to_cents uses int(amount * 100), which truncates "
                          "float values such as 19.99 to 1998. Fix it by rounding, round(amount * 100).",
    "hard_two_vulns": "Two vulnerabilities. First, SQL injection in find_user: the name is concatenated into the "
                      "query. Second, command injection in backup: shell=True with a concatenated path.",
    "hard_ambiguous_trace": "The exception is a TypeError. The real root cause is that the retries value is the "
                            "string '3', not an int, so adding 1 to it fails in load_retries.",
    "hard_long_summary": "The cache now runs on Redis. The timeout was raised from 5 to 12 seconds. Retries use "
                         "exponential backoff with jitter. The legacy admin page was removed.",
    "hard_compare_functions": "dedupe_a preserves the original order but is quadratic because of the list membership "
                              "check. dedupe_b uses set, so it is unordered and faster on average.",
}
WRONG = {
    "hard_multifile_bug": "The problem is in report.py formatting.",
    "hard_two_vulns": "Only one issue: SQL injection in find_user.",
    "hard_ambiguous_trace": "It is a ZeroDivisionError in run.",
    "hard_long_summary": "The project moved to a new logo and changed its colours.",
    "hard_compare_functions": "The two functions return identical results with the same complexity.",
}


class HardSuiteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p = mock.patch.object(bench_real, "SCRATCH", Path(self.tmp.name))
        p.start()
        self.addCleanup(p.stop)

    def test_five_cases_with_unique_ids(self):
        cases = bench_real.hard_cases()
        ids = [c[0] for c in cases]
        self.assertEqual(len(cases), 5)
        self.assertEqual(len(set(ids)), 5)
        self.assertTrue(all(i.startswith("hard_") for i in ids))
        self.assertEqual(set(ids), set(GOOD))

    def test_suite_selection_defaults_to_standard_cases(self):
        env = {k: v for k, v in os.environ.items() if k != "BENCH_SUITE"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(len(bench_real.active_cases()), 16)
            self.assertEqual([c[0] for c in bench_real.active_cases()], [c[0] for c in bench_real.cases()])

    def test_suite_env_selects_hard(self):
        with mock.patch.dict(os.environ, {"BENCH_SUITE": "hard"}):
            self.assertEqual([c[0] for c in bench_real.active_cases()], [c[0] for c in bench_real.hard_cases()])

    def test_correct_sample_answers_pass(self):
        for cid, agent, setup, task, check in bench_real.hard_cases():
            with self.subTest(case=cid):
                setup()
                good, note = check(GOOD[cid])
                self.assertTrue(good, note)

    def test_empty_answers_fail(self):
        for cid, agent, setup, task, check in bench_real.hard_cases():
            with self.subTest(case=cid):
                setup()
                good, _ = check("")
                self.assertFalse(good)

    def test_wrong_answers_fail(self):
        for cid, agent, setup, task, check in bench_real.hard_cases():
            with self.subTest(case=cid):
                setup()
                good, _ = check(WRONG[cid])
                self.assertFalse(good)

    def test_agents_are_thinker_roles(self):
        agents = {c[0]: c[1] for c in bench_real.hard_cases()}
        self.assertEqual(agents["hard_long_summary"], "engineering-technical-writer")
        self.assertEqual(agents["hard_two_vulns"], "testing-code-reviewer")
        self.assertEqual(agents["hard_multifile_bug"], "engineering-sre")


if __name__ == "__main__":
    unittest.main()
