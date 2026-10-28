"""Offline tests for scripts/bench.py ok(): harness and tool-auth errors must not count as passes."""
import unittest

from scripts.bench import ok


class OkGuard(unittest.TestCase):
    def test_normal_answer_passes(self):
        self.assertTrue(ok("[abc] The function returns the slug in lower case."))

    def test_harness_error_fails(self):
        self.assertFalse(ok("[abc] task names /workspace/x but x is not in the workspace"))

    def test_tool_auth_401_reply_fails(self):
        reply = "[d15b67d041] unable to read the file due to tool authorization errors (401 Unauthorized)"
        self.assertFalse(ok(reply))

    def test_auth_marker_is_case_insensitive(self):
        self.assertFalse(ok("[abc] Tool Authorization Error while reading the file"))

    def test_failed_prefix_still_fails(self):
        self.assertFalse(ok("[abc] FAILED reason=timeout"))


if __name__ == "__main__":
    unittest.main()
