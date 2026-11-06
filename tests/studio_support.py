"""Shared setup for the Studio tests: a temporary task database, a temporary Studio folder, no GPU check,
no event log writes, and a fake stage runner in place of the real model call."""
import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from router import events, gpu_lease, server, store, studio

STAGE_AGENTS = [
    "content-outline", "content-factcheck", "content-draft", "content-critic",
    "content-humanize", "content-antislop", "content-executive",
]


class StudioEnv(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)  # sqlite may still hold the file on Windows
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.swap(store, "DB_PATH", self.root / "tasks.db")
        self.swap(studio, "STUDIO_DIR", self.root / "studio")
        self.emitted = self.swap(events, "emit", mock.MagicMock())
        self.swap(gpu_lease, "check_for_ollama", lambda *a, **k: None)
        self.calls = []  # agent slugs in the order the fake stage runner ran them
        self.outcomes = {}  # agent slug -> status the fake returns; default "done"
        self.on_call = None  # optional hook(agent) called before the fake sets the status
        self.swap(server, "_execute", self._fake_execute)

    def swap(self, target, attr, value):
        patcher = mock.patch.object(target, attr, value)
        started = patcher.start()
        self.addCleanup(patcher.stop)
        return started

    async def _fake_execute(self, tid, agent, role, prompt, messages):
        self.calls.append(agent)
        if self.on_call:
            self.on_call(agent)
        status = self.outcomes.get(agent, "done")
        store.update(tid, status=status, summary="fake stage", error="" if status == "done" else "fake failure")
