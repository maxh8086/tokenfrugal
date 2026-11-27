import asyncio
from types import SimpleNamespace
import unittest
from unittest import mock

from router import loop, server


class CorrectionPromptTest(unittest.TestCase):
    def test_fix_prompt_is_contract_text(self):
        verdict = {"items": [
            {"name": "accept", "passed": False, "detail": "failed"},
            {"name": "lint", "passed": False, "detail": "also failed"},
        ]}
        self.assertEqual(
            server._fix_prompt(verdict, {"tools": ["write_file"]}),
            "Checks failed: accept: failed. Fix it with edit_file or write_file. "
            "The checks run again after your reply.",
        )

    def test_strip_nudges_removes_only_loop_nudges(self):
        msgs = [
            {"role": "user", "content": "Stop calling tools. Give the final answer now."},
            {"role": "user", "content": "Step limit reached. Do not call any more tools. Answer now using only the tool results above."},
            {"role": "user", "content": "first call hint"},
            {"role": "user", "content": "every tool call failed; fix the arguments and call the tool again before answering"},
            {"role": "user", "content": "slop retry"},
        ]
        self.assertEqual(server.strip_nudges(msgs), msgs[2:])

    def test_loop_receives_fix_once_without_nudges(self):
        fix = "Checks failed: accept: failed. Fix it with edit_file or write_file. The checks run again after your reply."
        msgs = [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "task"},
            {"role": "assistant", "content": "done"},
            {"role": "user", "content": loop.NUDGE_WRAP},
            {"role": "user", "content": loop.NUDGE_FINAL},
            {"role": "user", "content": "first call hint"},
            {"role": "user", "content": "every tool call failed; retry"},
            {"role": "user", "content": "slop retry"},
        ]
        recorded = []

        class Session:
            async def list_tools(self):
                return SimpleNamespace(tools=[])

        class AsyncContext:
            async def __aenter__(self):
                return Session()

            async def __aexit__(self, *exc):
                return False

        def complete(**kwargs):
            recorded.append(kwargs["messages"])
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="done", tool_calls=None))])

        fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=complete)))
        passed = server.strip_nudges(msgs) + [{"role": "user", "content": fix}]
        with mock.patch.object(loop, "backends", return_value=AsyncContext()), \
                mock.patch.object(loop, "open_role", return_value=AsyncContext()), \
                mock.patch.object(loop, "_client", fake_client):
            asyncio.run(loop.run("agent", {"role": "builder", "model": "m", "tools": [],
                                            "max_steps": 1, "skills": []}, "", passed, "test"))
        sent = recorded[0]
        user_turns = [m for m in sent if m.get("role") == "user"]
        self.assertEqual(user_turns[-1]["content"], fix)
        self.assertEqual(sum(m.get("content") == fix for m in user_turns), 1)
        self.assertFalse(any(m.get("content") in (loop.NUDGE_WRAP, loop.NUDGE_FINAL) for m in sent))


if __name__ == "__main__":
    unittest.main()
