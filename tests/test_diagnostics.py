"""Tests for failure reason classes shown to the orchestrator on a failed dispatch. Written before the code."""
import unittest

from router.loop import failure_reason


class Reason(unittest.TestCase):
    def assertReason(self, text, label):
        self.assertEqual(failure_reason(text), label, text)

    def test_infra(self):
        for m in ("Error code: 500 - internal error", "InternalServerError: boom",
                  "llama runner process has terminated", "runner stopped unexpectedly",
                  "infra: something broke", "INFRA: upper"):
            self.assertReason(m, "infra")

    def test_connection(self):
        for m in ("MCPError: Connection closed", "container ts-fs is not running",
                  "Error response from daemon: container abc is not running", "BrokenPipeError",
                  "Broken pipe"):
            self.assertReason(m, "connection")

    def test_timeout(self):
        self.assertReason("task timed out after 300s", "timeout")

    def test_no_tool_call(self):
        self.assertReason("you answered without calling any tool; call a tool to read real data first", "no-tool-call")

    def test_malformed_tool_call(self):
        for m in ("that tool call could not be run: it is malformed JSON or names an unknown tool.",
                  "you wrote a tool call as text; use the tool-calling interface or give the final answer",
                  "malformed tool call arguments"):
            self.assertReason(m, "malformed-tool-call")

    def test_out_of_steps(self):
        self.assertReason("no final answer in 12 steps", "out-of-steps")

    def test_bad_answer(self):
        self.assertReason("empty answer", "bad-answer")
        self.assertReason("answer contains filler/placeholder text; redo with concrete content", "bad-answer")

    def test_unknown(self):
        self.assertReason("ValueError: something else entirely", "unknown")
        self.assertReason("", "unknown")

    def test_infra_wins_over_timeout_and_connection(self):
        self.assertReason("infra: task timed out after 5s, Connection closed", "infra")


class FailureMessage(unittest.TestCase):
    def test_reason_in_reply_and_hint_per_class(self):
        from router.server import failure_message
        role = {"role": "analyze", "model": "qwen2.5-coder-yarn:3b"}
        cases = {
            "connection": "Call resume_task('t1') to retry.",
            "infra": "Call resume_task('t1') to retry.",
            "timeout": "Call resume_task('t1') to retry.",
            "no-tool-call": "Re-scope the task smaller and dispatch again; resume_task will repeat the same failure.",
            "malformed-tool-call": "Re-scope the task smaller and dispatch again; resume_task will repeat the same failure.",
            "bad-answer": "Re-scope the task smaller and dispatch again; resume_task will repeat the same failure.",
            "out-of-steps": "Re-scope the task smaller and dispatch again; resume_task will repeat the same failure.",
            "unknown": "Call resume_task('t1') once, then re-scope.",
        }
        for reason, hint in cases.items():
            msg = failure_message("t1", role, "ValueError: x", reason)
            self.assertIn(f"reason={reason}", msg)
            self.assertIn("FAILED (analyze/qwen2.5-coder-yarn:3b) reason=", msg)
            self.assertIn("ValueError: x", msg)
            self.assertTrue(msg.endswith(hint), msg)
            self.assertLess(len(msg), 300)


if __name__ == "__main__":
    unittest.main()
