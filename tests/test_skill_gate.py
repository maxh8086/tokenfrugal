import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import skill_gate as g

OK_TESTS = lambda: (True, "OK")
OK_BENCH = lambda s, t, lv: {"n": 3, "candidate": 1.0, "baseline": 0.67}


class Gate(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        for name in ("SKILLS", "CANDIDATES", "REVIEWS"):
            p = mock.patch.object(g, name, self.tmp / name.lower())
            p.start()
            self.addCleanup(p.stop)
        (g.SKILLS / "code-l2").mkdir(parents=True)

    def prepare(self, text="short", tests=OK_TESTS, bench=OK_BENCH, skill="code-l2"):
        return g.prepare(skill, text, tests, bench)

    def write_verdict(self, text, **fields):
        digest = g.sha256(text)
        body = {"candidate_sha256": digest, "skill": "code-l2", "approved": True, "reason": "fine",
                "reviewer_tool": "claude-code", "reviewer_model": "claude-sonnet-5-5"}
        body.update(fields)
        g.review_paths("code-l2", digest)["verdict"].write_text(json.dumps(body), encoding="utf-8")

    def live(self):
        return (g.SKILLS / "code-l2" / "SKILL.md")

    # stage 1: prepare
    def test_passing_candidate_waits_for_review_and_writes_no_skill(self):
        v = self.prepare()
        self.assertEqual((v.passed, v.gate), (None, "awaiting_review"))
        self.assertFalse(self.live().exists())
        request = g.review_paths("code-l2", g.sha256("short"))["request"]
        self.assertTrue(request.exists())
        self.assertIn(g.sha256("short"), request.read_text(encoding="utf-8"))

    def test_length_rejected_first_and_nothing_else_runs(self):
        boom = mock.Mock(side_effect=AssertionError)
        v = self.prepare("x" * 1200, tests=boom, bench=boom)
        self.assertEqual((v.passed, v.gate), (False, "length"))
        boom.assert_not_called()

    def test_tests_before_bench(self):
        bench = mock.Mock()
        v = self.prepare(tests=lambda: (False, "1 failed"), bench=bench)
        self.assertEqual(v.gate, "tests")
        bench.assert_not_called()

    def test_rejected_candidate_is_still_stored(self):
        self.prepare("x" * 1200)
        stored = list((g.CANDIDATES / "code-l2").glob("*.md"))
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].read_text(), "x" * 1200)

    def test_regression_and_small_n(self):
        v = self.prepare(bench=lambda s, t, lv: {"n": 3, "candidate": 0.33, "baseline": 0.67})
        self.assertEqual(v.gate, "regression")
        v = self.prepare(bench=lambda s, t, lv: {"n": 2, "candidate": 1, "baseline": 0})
        self.assertEqual(v.gate, "regression")
        self.assertIn("n=2", v.reason)

    def test_tie_is_not_an_improvement(self):
        v = self.prepare(bench=lambda s, t, lv: {"n": 3, "candidate": 0.67, "baseline": 0.67})
        self.assertEqual((v.passed, v.gate), (False, "regression"))

    def test_floor_tie_is_skipped_not_regression(self):
        v = self.prepare(bench=lambda s, t, lv: {"n": 3, "candidate": 0.0, "baseline": 0.0})
        self.assertEqual(v.gate, "floor")
        self.assertIn("skill gate skipped", v.reason)

    def test_partial_credit_is_reported(self):
        v = self.prepare(bench=lambda s, t, lv: {"n": 3, "candidate": 0.33, "baseline": 0.67,
                                                 "tests_passed": 2, "tests_total": 3, "tool_errors": 1})
        self.assertIn("tests_passed=2", v.reason)
        self.assertIn("tool_errors=1", v.reason)

    def test_non_coding_skill_rejected(self):
        with self.assertRaises(ValueError):
            self.prepare(skill="role-builder")

    def test_save_candidate_path(self):
        p = g.save_candidate("code-l2", "x", ts="T1")
        self.assertEqual(p, g.CANDIDATES / "code-l2" / "T1.md")
        self.assertEqual(p.read_text(), "x")

    # stage 3: finish
    def test_finish_without_prepare_is_an_error(self):
        with self.assertRaises(FileNotFoundError):
            g.finish("code-l2")

    def test_no_verdict_yet_is_still_waiting(self):
        self.prepare()
        v = g.finish("code-l2")
        self.assertEqual((v.passed, v.gate), (None, "awaiting_review"))

    def test_approved_verdict_applies_skill(self):
        self.prepare()
        self.write_verdict("short")
        v = g.finish("code-l2")
        self.assertEqual((v.passed, v.gate), (True, "ok"))
        self.assertEqual(self.live().read_text(), "short")

    def test_approved_verdict_without_apply_only_reports(self):
        self.prepare()
        self.write_verdict("short")
        v = g.finish("code-l2", apply=False)
        self.assertTrue(v.passed)
        self.assertFalse(self.live().exists())

    def test_rejected_verdict_writes_nothing(self):
        self.prepare()
        self.write_verdict("short", approved=False, reason="vague")
        v = g.finish("code-l2")
        self.assertEqual((v.gate, v.reason), ("review", "vague"))
        self.assertFalse(self.live().exists())

    def test_verdict_for_another_candidate_is_refused(self):
        self.prepare()
        self.write_verdict("short", candidate_sha256="0" * 64)
        v = g.finish("code-l2")
        self.assertEqual((v.passed, v.gate), (False, "verdict"))
        self.assertFalse(self.live().exists())

    def test_changed_candidate_file_is_refused(self):
        self.prepare()
        self.write_verdict("short")
        path = next((g.CANDIDATES / "code-l2").glob("*.md"))
        path.write_text("edited", encoding="utf-8")
        v = g.finish("code-l2")
        self.assertEqual((v.passed, v.gate), (False, "verdict"))

    def test_reviewer_outside_allowlist_is_refused(self):
        self.prepare()
        self.write_verdict("short", reviewer_tool="codex", reviewer_model="gpt-5-codex")
        v = g.finish("code-l2")
        self.assertEqual((v.passed, v.gate), (False, "verdict"))
        self.assertIn("gpt-5-codex", v.reason)
        self.assertFalse(self.live().exists())

    def test_both_allowed_reviewers_are_accepted(self):
        for model in g.REVIEWER_MODELS:
            self.prepare()
            self.write_verdict("short", reviewer_model=model)
            self.assertTrue(g.finish("code-l2", apply=False).passed, model)

    def test_approved_must_be_boolean(self):
        self.prepare()
        self.write_verdict("short", approved="yes")
        v = g.finish("code-l2")
        self.assertEqual((v.passed, v.gate), (False, "verdict"))

    def test_invalid_json_verdict_is_refused(self):
        self.prepare()
        g.review_paths("code-l2", g.sha256("short"))["verdict"].write_text("{not json", encoding="utf-8")
        v = g.finish("code-l2")
        self.assertEqual((v.passed, v.gate), (False, "verdict"))

    def test_request_names_the_suggested_reviewer_by_level(self):
        self.assertEqual(g.SUGGESTED["low"], "claude-sonnet-5-5")
        self.assertEqual(g.SUGGESTED["high"], "claude-opus-5-5")
        text = g.request_text("code-l4", "abc", "body", 4)
        self.assertIn("claude-opus-5-5", text)
        self.assertIn("candidate_sha256: abc", text)


if __name__ == "__main__":
    unittest.main()
