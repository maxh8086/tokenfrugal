import asyncio
import contextlib
import unittest
from types import SimpleNamespace
from unittest import mock

from gateway import loop

PARAMS = {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}
SERVER_ERROR = "MCP error -32602: unknown argument 'fields'"


def _reply(content=None, tool_call=None):
    calls = [tool_call] if tool_call else None
    msg = SimpleNamespace(content=content, tool_calls=calls, reasoning_content=None, reasoning=None)
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=None)


def _call(i):
    fn = SimpleNamespace(name="read_file", arguments='{"path": "/workspace/a.py"}')
    return SimpleNamespace(id=f"c{i}", function=fn)


class _FailingSession:
    async def list_tools(self):
        return SimpleNamespace(tools=[])

    async def call_tool(self, name, args):
        return SimpleNamespace(isError=True, content=[])


@contextlib.asynccontextmanager
async def _open_role(*a, **k):
    yield _FailingSession()


@contextlib.asynccontextmanager
async def _no_backends(*a, **k):
    yield


class ToolErrorTrail(unittest.TestCase):
    def test_server_error_text_reaches_the_trail(self):
        role = {"role": "github-read", "model": "m", "tools": ["read_file"], "max_steps": 2}
        tools = [{"type": "function", "function": {"name": "read_file", "parameters": PARAMS}}]
        replies = [_reply(tool_call=_call(1)), _reply(tool_call=_call(2))]
        emitted = []
        patches = [
            mock.patch.object(loop, "backends", _no_backends),
            mock.patch.object(loop, "open_role", _open_role),
            mock.patch.object(loop, "to_openai_tools", lambda *a, **k: tools),
            mock.patch.object(loop, "result_text", lambda res: SERVER_ERROR),
            mock.patch.object(loop, "_count", lambda *a, **k: None),
            mock.patch.object(loop.events, "emit", lambda kind, **k: emitted.append((kind, k))),
            mock.patch.object(loop._client.chat.completions, "create", mock.Mock(side_effect=replies)),
        ]
        for p in patches:
            p.start()
        try:
            with self.assertRaises(loop.LoopError):  # every call fails, so no answer is possible
                asyncio.run(loop._run("github-ops", role, [{"role": "user", "content": "list PRs"}], "t1"))
        finally:
            for p in patches:
                p.stop()
        errors = [k for kind, k in emitted if kind == "tool_error"]
        self.assertEqual(len(errors), 2)  # one per failed call
        for e in errors:
            self.assertIn(SERVER_ERROR, e["error"])
            self.assertEqual(e["name"], "read_file")


if __name__ == "__main__":
    unittest.main()
