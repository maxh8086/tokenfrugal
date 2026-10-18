import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import skill_gate as g

OK_TESTS = lambda: (True, "OK")
OK_BENCH = lambda s, t, lv: {"n": 3, "candidate": 1.0, "baseline": 0.67}
OK_REVIEW = lambda m, s, t: (True, "fine")


class Gate(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        for name in ("SKILLS", "CANDIDATES"):
            p = mock.patch.object(g, name, self.tmp / name.lower())
            p.start()
            self.addCleanup(p.stop)
        (g.SKILLS / "code-l2").mkdir(parents=True)

    def run_gate(self, text="short", tests=OK_TESTS, bench=OK_BENCH, review=OK_REVIEW, skill="code-l2"):
        return g.gate(skill, text, tests, bench, review)

    def test_pass_writes_skill(self):
        v = self.run_gate()
        self.assertTrue(v.passed)
        self.assertEqual((g.SKILLS / "code-l2" / "SKILL.md").read_text(), "short")

    def test_length_rejected_first_and_nothing_else_runs(self):
        boom = mock.Mock(side_effect=AssertionError)
        v = self.run_gate("x" * 1200, tests=boom, bench=boom, review=boom)
        self.assertEqual((v.passed, v.gate), (False, "length"))
        boom.assert_not_called()

    def test_tests_before_bench(self):
        bench = mock.Mock()
        v = self.run_gate(tests=lambda: (False, "1 failed"), bench=bench)
        self.assertEqual(v.gate, "tests")
        bench.assert_not_called()

    def test_regression_and_small_n(self):
        v = self.run_gate(bench=lambda s, t, lv: {"n": 3, "candidate": 0.33, "baseline": 0.67})
        self.assertEqual(v.gate, "regression")
        v = self.run_gate(bench=lambda s, t, lv: {"n": 2, "candidate": 1, "baseline": 0})
        self.assertEqual(v.gate, "regression")
        self.assertIn("n=2", v.reason)

    def test_review_rejection_writes_nothing(self):
        v = self.run_gate(review=lambda m, s, t: (False, "vague"))
        self.assertEqual((v.gate, v.reason), ("review", "vague"))
        self.assertFalse((g.SKILLS / "code-l2" / "SKILL.md").exists())

    def test_reviewer_by_level(self):
        seen = []
        for skill in ("code-l3", "code-l4"):
            (g.SKILLS / skill).mkdir(exist_ok=True)
            self.run_gate(skill=skill, review=lambda m, s, t: (seen.append(m) or True, ""))
        self.assertEqual(seen, ["claude-sonnet-5-5", "claude-opus-5-5"])

    def test_non_coding_skill_rejected(self):
        with self.assertRaises(ValueError):
            self.run_gate(skill="role-builder")

    def test_save_candidate_path(self):
        p = g.save_candidate("code-l2", "x", ts="T1")
        self.assertEqual(p, g.CANDIDATES / "code-l2" / "T1.md")
        self.assertEqual(p.read_text(), "x")


if __name__ == "__main__":
    unittest.main()
