"""Step 8g replay report tests. Fixture corpora and results live in temporary folders: no model, Docker, network or real .env."""
import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts import replay_report as rr

IDS = [f"fb-{i:03d}" for i in range(1, 11)] + [f"rw-{i:03d}" for i in range(11, 21)]
GATE_LINE = "GATE: {verdict} base=base candidate=s2 results=Benchmark/replay/results/s2-20261127.jsonl " \
            "passed={k}/20 false_successes={n} accept_failed_share={share}"


def rec(task, arm="s2", run=1, outcome="done", status="done", stop=None, check_ok=True, scope_ok=True,
        secs=10.0, saved=5, attempt=1, result=None):
    if result is None:
        ended = outcome if outcome is not None else status
        result = "pass" if ended in ("done", "satisfied") and check_ok and scope_ok else "fail"
    return {"id": task, "arm": arm, "run": run, "result": result, "outcome": outcome, "status": status,
            "stop": stop, "check_ok": check_ok, "scope_ok": scope_ok, "secs": secs, "steps": 3,
            "peak_ctx": 100, "model_tag": "m", "est_saved_tokens": saved, "attempt": attempt}


def infra(task, arm="s2", run=1, attempt=1):
    return rec(task, arm, run, outcome=None, status=None, stop="gpu_busy", check_ok=False, result="infra",
               attempt=attempt)


def failed(task, arm="s2", run=1, stop="accept_failed"):
    return rec(task, arm, run, outcome="failed", status="failed", stop=stop, check_ok=False, result="fail")


class SignTestTest(unittest.TestCase):
    def test_known_values(self):
        self.assertAlmostEqual(rr.sign_test_p(5, 0), 1 / 32)
        self.assertAlmostEqual(rr.sign_test_p(4, 0), 1 / 16)
        self.assertAlmostEqual(rr.sign_test_p(6, 0), 1 / 64)
        self.assertAlmostEqual(rr.sign_test_p(10, 0), 1 / 1024)
        self.assertAlmostEqual(rr.sign_test_p(5, 5), 638 / 1024)
        self.assertAlmostEqual(rr.sign_test_p(0, 0), 1.0)

    def test_five_of_five_is_the_first_significant_count(self):
        self.assertGreater(rr.sign_test_p(4, 0), 0.05)
        self.assertLess(rr.sign_test_p(5, 0), 0.05)


class TaskRuleTest(unittest.TestCase):
    def test_single_run_passes_only_when_done_with_checks_and_scope(self):
        self.assertTrue(rr.task_passes([rec("fb-001")]))
        self.assertFalse(rr.task_passes([failed("fb-001")]))
        self.assertFalse(rr.task_passes([rec("fb-001", check_ok=False)]))
        self.assertFalse(rr.task_passes([rec("fb-001", scope_ok=False)]))

    def test_old_checkout_uses_status_when_outcome_is_null(self):
        self.assertTrue(rr.task_passes([rec("fb-001", outcome=None, status="satisfied")]))
        self.assertFalse(rr.task_passes([rec("fb-001", outcome=None, status="failed")]))

    def test_three_runs_pass_when_two_pass(self):
        ok = [rec("fb-001", run=1), rec("fb-001", run=2, outcome="failed", check_ok=False, stop="checker"),
              rec("fb-001", run=3)]
        self.assertTrue(rr.task_passes(ok))
        bad = [failed("fb-001", run=1), failed("fb-001", run=2), rec("fb-001", run=3)]
        self.assertFalse(rr.task_passes(bad))

    def test_infra_rows_are_ignored(self):
        self.assertTrue(rr.task_passes([infra("fb-001"), rec("fb-001", attempt=2)]))
        self.assertFalse(rr.task_passes([infra("fb-001")]))


class ReportTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(os.path.realpath(tempfile.mkdtemp()))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.corpus = self.root / "Benchmark" / "replay"
        self.results = self.corpus / "results"
        self.results.mkdir(parents=True)
        for name in IDS:
            (self.corpus / name).mkdir()
            (self.corpus / name / "task.toml").write_text("agent = 'coding-l2'\n", encoding="utf-8")
        self.write("base", [rec(t, "base", outcome=None, status="done") for t in IDS])

    def write(self, arm, records, day="20261127"):
        path = self.results / f"{arm}-{day}.jsonl"
        with path.open("w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record, sort_keys=True) + "\n")
        return path

    def run_main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = rr.main(list(argv), root=self.root)
        return code, out.getvalue(), err.getvalue()

    def report(self):
        return self.run_main("--base", "base", "--candidate", "s2")


class GateTest(ReportTest):
    def test_twenty_of_twenty_with_a_false_success_fails(self):
        records = [rec(t) for t in IDS]
        records += [rec("fb-001", run=2), rec("fb-001", run=3, scope_ok=False)]
        self.write("s2", records)
        code, out, _ = self.report()
        self.assertEqual(code, 0)
        self.assertIn(GATE_LINE.format(verdict="FAIL", k=20, n=1, share="0.00"), out)

    def test_sixteen_of_twenty_passes_and_fifteen_fails(self):
        self.write("s2", [rec(t) for t in IDS[:16]] + [failed(t) for t in IDS[16:]])
        _, out, _ = self.report()
        self.assertIn("GATE: PASS base=base candidate=s2", out)
        self.assertIn("passed=16/20 false_successes=0", out)
        self.write("s3", [rec(t, "s3") for t in IDS[:15]] + [failed(t, "s3") for t in IDS[15:]])
        _, out, _ = self.run_main("--base", "base", "--candidate", "s3")
        self.assertIn("GATE: FAIL base=base candidate=s3", out)
        self.assertIn("passed=15/20", out)

    def test_done_run_with_scope_false_is_a_false_success(self):
        self.write("s2", [rec(t) for t in IDS[:19]] + [rec(IDS[19], scope_ok=False)])
        _, out, _ = self.report()
        self.assertIn("GATE: FAIL", out)
        self.assertIn("false_successes=1", out)

    def test_infra_rows_never_count(self):
        self.write("s2", [rec(t) for t in IDS] + [infra("fb-002"), infra("rw-015")])
        _, out, _ = self.report()
        self.assertIn(GATE_LINE.format(verdict="PASS", k=20, n=0, share="0.00"), out)

    def test_missing_candidate_task_is_counted_and_named(self):
        self.write("s2", [rec(t) for t in IDS if t != "fb-005"])
        _, out, _ = self.report()
        self.assertIn("passed=19/20", out)
        self.assertIn("fb-005", out)

    def test_fb_and_rw_are_reported_apart(self):
        self.write("s2", [rec(t) for t in IDS])
        _, out, _ = self.report()
        self.assertIn("FB tasks: candidate 10/10", out)
        self.assertIn("rw tasks: candidate 10/10", out)


class AcceptFailedShareTest(ReportTest):
    def test_share_above_half_gives_build(self):
        stops = ["accept_failed", "accept_failed", "accept_failed", "checker"]
        records = [rec(t) for t in IDS[:16]] + [failed(t, stop=s) for t, s in zip(IDS[16:], stops)]
        self.write("s2", records)
        _, out, _ = self.report()
        self.assertIn("GATE: PASS", out)
        self.assertIn("accept_failed_share=0.75", out)
        self.assertIn("S3 decision: build", out)

    def test_share_of_exactly_half_gives_skip(self):
        stops = ["accept_failed", "accept_failed", "checker", "checker"]
        records = [rec(t) for t in IDS[:16]] + [failed(t, stop=s) for t, s in zip(IDS[16:], stops)]
        self.write("s2", records)
        _, out, _ = self.report()
        self.assertIn("accept_failed_share=0.50", out)
        self.assertIn("S3 decision: skip", out)

    def test_gate_failure_always_gives_build(self):
        self.write("s2", [rec(t) for t in IDS[:10]] + [failed(t, stop="checker") for t in IDS[10:]])
        _, out, _ = self.report()
        self.assertIn("GATE: FAIL", out)
        self.assertIn("S3 decision: build", out)


class SignLineAndTimingTest(ReportTest):
    def test_gate_pass_with_too_few_discordant_tasks_says_noise(self):
        self.write("base", [rec(t, "base", outcome=None, status="done") for t in IDS[4:]] +
                   [failed(t, "base", stop="checker") for t in IDS[:4]])
        self.write("s2", [rec(t) for t in IDS])
        _, out, _ = self.report()
        self.assertIn("GATE: PASS", out)
        self.assertIn("one-sided p=0.0625", out)
        self.assertIn("cannot be told apart from noise", out)

    def test_many_discordant_tasks_are_distinguishable(self):
        self.write("base", [failed(t, "base", stop="checker") for t in IDS])
        self.write("s2", [rec(t) for t in IDS])
        _, out, _ = self.report()
        self.assertIn("distinguishable from noise", out)

    def test_p90_seconds_and_estimated_tokens_per_task(self):
        self.write("base", [rec(t, "base", outcome=None, status="done", secs=10.0) for t in IDS])
        self.write("s2", [rec(t, secs=float(i + 1), saved=7 if t == "fb-001" else 5) for i, t in enumerate(IDS)])
        _, out, _ = self.report()
        self.assertIn("90th percentile run seconds: base=10.0 candidate=18.0", out)
        self.assertIn("fb-001: estimated tokens spared 7", out)
        self.assertIn("estimated tokens spared", out)


class VerifyRecordTest(ReportTest):
    def setUp(self):
        super().setUp()
        self.write("s2", [rec(t) for t in IDS])
        _, out, _ = self.report()
        self.md = self.root / "RESULTS.md"
        self.md.write_text(out, encoding="utf-8")

    def test_matching_record_verifies(self):
        code, _, _ = self.run_main("--verify-record", str(self.md), "--base", "base", "--candidate", "s2")
        self.assertEqual(code, 0)

    def test_edited_gate_line_fails(self):
        self.md.write_text(self.md.read_text(encoding="utf-8").replace("passed=20/20", "passed=19/20"),
                           encoding="utf-8")
        code, _, _ = self.run_main("--verify-record", str(self.md), "--base", "base", "--candidate", "s2")
        self.assertNotEqual(code, 0)

    def test_record_for_another_pair_fails(self):
        code, _, _ = self.run_main("--verify-record", str(self.md), "--base", "base", "--candidate", "s3")
        self.assertNotEqual(code, 0)

    def test_missing_decision_line_fails(self):
        kept = [x for x in self.md.read_text(encoding="utf-8").splitlines(True) if not x.startswith("S3 decision:")]
        self.md.write_text("".join(kept), encoding="utf-8")
        code, _, _ = self.run_main("--verify-record", str(self.md), "--base", "base", "--candidate", "s2")
        self.assertNotEqual(code, 0)

    def test_decision_must_be_the_next_line_of_its_own_gate_record(self):
        lines = self.md.read_text(encoding="utf-8").splitlines()
        gate = next(x for x in lines if x.startswith("GATE: "))
        s3 = next(x for x in lines if x.startswith("S3 decision:"))
        other = "GATE: PASS base=base candidate=s3 results=Benchmark/replay/results/s3-20261127.jsonl passed=20/20 " \
                "false_successes=0 accept_failed_share=0.00"
        self.md.write_text("\n".join([gate, "note", other, s3]) + "\n", encoding="utf-8")
        code, _, err = self.run_main("--verify-record", str(self.md), "--base", "base", "--candidate", "s2")
        self.assertNotEqual(code, 0)
        self.assertIn("S3 decision", err)

    def test_blank_lines_between_gate_and_its_decision_are_skipped(self):
        lines = self.md.read_text(encoding="utf-8").splitlines()
        gate = next(x for x in lines if x.startswith("GATE: "))
        s3 = next(x for x in lines if x.startswith("S3 decision:"))
        self.md.write_text("\n".join([gate, "", s3]) + "\n", encoding="utf-8")
        code, _, _ = self.run_main("--verify-record", str(self.md), "--base", "base", "--candidate", "s2")
        self.assertEqual(code, 0)

    def test_missing_results_file_fails_with_a_clear_message(self):
        (self.results / "s2-20261127.jsonl").unlink()
        code, _, err = self.run_main("--verify-record", str(self.md), "--base", "base", "--candidate", "s2")
        self.assertNotEqual(code, 0)
        self.assertIn("not found", err)


if __name__ == "__main__":
    unittest.main()
