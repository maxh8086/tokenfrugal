import asyncio
import contextlib
import unittest
from types import SimpleNamespace
from unittest import mock

from gateway import loop

PARAMS = {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}


def _reply(content=None, tool_call=None):
    calls = [tool_call] if tool_call else None
    msg = SimpleNamespace(content=content, tool_calls=calls, reasoning_content=None, reasoning=None)
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=None)


def _call(i):
    fn = SimpleNamespace(name="read_file", arguments='{"path": "/workspace/a.py"}')
    return SimpleNamespace(id=f"c{i}", function=fn)


class _Session:
    async def list_tools(self):
        return SimpleNamespace(tools=[])

    async def call_tool(self, name, args):
        return SimpleNamespace(isError=False, content=[])


@contextlib.asynccontextmanager
async def _open_role(*a, **k):
    yield _Session()


@contextlib.asynccontextmanager
async def _no_backends(*a, **k):
    yield


class ForcedFinalAnswer(unittest.TestCase):
    def _run_loop(self, replies, max_steps):
        role = {"role": "reviewer", "model": "m", "tools": ["read_file"], "max_steps": max_steps}
        tools = [{"type": "function", "function": {"name": "read_file", "parameters": PARAMS}}]
        create = mock.Mock(side_effect=replies)
        patches = [
            mock.patch.object(loop, "backends", _no_backends),
            mock.patch.object(loop, "open_role", _open_role),
            mock.patch.object(loop, "to_openai_tools", lambda *a, **k: tools),
            mock.patch.object(loop, "result_text", lambda res: "file body"),
            mock.patch.object(loop, "_count", lambda *a, **k: None),
            mock.patch.object(loop.events, "emit", lambda *a, **k: None),
            mock.patch.object(loop._client.chat.completions, "create", create),
        ]
        for p in patches:
            p.start()
        try:
            out = asyncio.run(loop._run("reviewer", role, [{"role": "user", "content": "check"}], "t1"))
        finally:
            for p in patches:
                p.stop()
        return out, create

    def test_last_step_has_no_tools_and_asks_for_answer(self):
        replies = [_reply(tool_call=_call(1)), _reply(tool_call=_call(2)), _reply(content="Final: file is fine.")]
        (content, _), create = self._run_loop(replies, max_steps=3)
        self.assertEqual(content, "Final: file is fine.")
        self.assertEqual(create.call_count, 3)
        first, last = create.call_args_list[0].kwargs, create.call_args_list[2].kwargs
        self.assertTrue(first["tools"])
        self.assertIsNone(last["tools"])
        self.assertNotIn("tool_choice", last)
        forced = [m for m in last["messages"] if m.get("content", "").startswith("Step limit reached")]
        self.assertEqual(len(forced), 1)

    def test_no_forcing_without_a_successful_tool_result(self):
        replies = [_reply(content="I cannot read files.")] * 3
        with self.assertRaises(loop.LoopError):
            self._run_loop(replies, max_steps=2)


if __name__ == "__main__":
    unittest.main()
