"""Pure helpers behind the reply contract: failure kinds, the status line, the changed-file manifest, the accept
argument, kind hints and the required_tool preflight. No model, Docker or git call is made."""
import unittest

from router import checker, loop, preflight, server
from router.config import ROOT


class FailureKinds(unittest.TestCase):
    def test_timeout_error_text_is_a_timeout(self):
        self.assertEqual(loop.failure_reason("TimeoutError: read operation"), "timeout")
        self.assertEqual(loop.error_kind("TimeoutError: read operation"), "request_timeout")

    def test_api_timeout_error_text_is_a_timeout(self):
        self.assertEqual(loop.failure_reason("APITimeoutError: Request"), "timeout")

    def test_infra_text_is_infra_kind(self):
        text = "infra: backend containers for synaptree are not running or healthy"
        self.assertEqual(loop.failure_reason(text), "infra")
        self.assertEqual(loop.error_kind(text), "infra")
        self.assertEqual(loop.error_kind("LoopError: infra: Error code: 500 - internal error"), "infra")


class StatusLine(unittest.TestCase):
    def test_format(self):
        self.assertEqual(server.status_line("done", "builder", "m", 3, 12.34),
                         "status=done role=builder model=m calls=3 elapsed=12.3s")

    def test_failed_zero_calls(self):
        self.assertEqual(server.status_line("failed", "reviewer", "t", 0, 0.0),
                         "status=failed role=reviewer model=t calls=0 elapsed=0.0s")


class Manifest(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(checker.manifest(set(), set()), "files_changed: none")

    def test_only_files_already_changed_before_are_not_listed(self):
        self.assertEqual(checker.manifest({"a.py"}, {"a.py"}), "files_changed: none")

    def test_one_new_file(self):
        self.assertEqual(checker.manifest({"a.py"}, {"a.py", "b.py"}), "files_changed: b.py")

    def test_several_files_sorted(self):
        self.assertEqual(checker.manifest(set(), {"b.py", "a.py"}), "files_changed: a.py, b.py")

    def test_over_cap_adds_count(self):
        after = {f"f{i:02d}.py" for i in range(25)}
        expected = "files_changed: " + ", ".join(sorted(after)[:20]) + " (+5 more)"
        self.assertEqual(checker.manifest(set(), after, cap=20), expected)


class AcceptCommand(unittest.TestCase):
    def test_accept_line_is_split_on_spaces(self):
        self.assertEqual(server.accept_cmd("Accept: python -m unittest"), ["python", "-m", "unittest"])

    def test_no_accept_line_is_none(self):
        self.assertIsNone(server.accept_cmd("no accept line"))


class KindHints(unittest.TestCase):
    def test_infra_hint(self):
        self.assertEqual(server.kind_hint("infra", 0),
                         "The backend containers did not start. Do not resume_task; check Docker, then dispatch again.")

    def test_no_tool_call_without_required_tool(self):
        self.assertEqual(server.kind_hint("no_tool_call", 0),
                         "The model answered without calling a tool. Name the exact tool and path in the task.")

    def test_no_tool_call_with_required_tool(self):
        self.assertEqual(server.kind_hint("no_tool_call", 0, "write_file"),
                         "The model answered without calling a tool. Call write_file with the exact path in the task.")

    def test_correction_names_required_tool(self):
        msg = loop.first_call_hint("fix /workspace/a.py", {"read_file", "write_file"}, "write_file")
        self.assertEqual(msg, "You have not called write_file yet. Call write_file with path=/workspace/a.py now, "
                              "then answer from its result.")

    def test_correction_without_required_tool_is_unchanged(self):
        msg = loop.first_call_hint("read /workspace/a.py", {"read_file"})
        self.assertEqual(msg, "You have not read anything yet. Call read_file with path=/workspace/a.py now, "
                              "then answer from its result.")


class RequiredToolPreflight(unittest.TestCase):
    def test_required_tool_missing_from_tools_is_an_error(self):
        roles = {"bad": {"model": "builder", "tools": ["read_file"], "required_tool": "write_file"}}
        probs = preflight.role_errors(roles, ROOT).get("bad", [])
        self.assertTrue(any("required_tool 'write_file'" in p for p in probs), probs)

    def test_required_tool_in_tools_is_not_reported(self):
        roles = {"good": {"model": "builder", "tools": ["read_file", "write_file"], "required_tool": "write_file"}}
        probs = preflight.role_errors(roles, ROOT).get("good", [])
        self.assertFalse(any("required_tool" in p for p in probs), probs)


if __name__ == "__main__":
    unittest.main()
