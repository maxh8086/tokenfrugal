import asyncio
import gc
import os
import sqlite3
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from router import server, store


class WorkspaceClaimTests(unittest.TestCase):
    def setUp(self):
        tmp = self.enterContext(tempfile.TemporaryDirectory())
        self.addCleanup(gc.collect)  # Release legacy sqlite connections before Windows removes the DB.
        self.workspace = os.path.normcase(os.path.realpath(tmp))
        self.db = Path(tmp) / "tasks.db"
        self.enterContext(patch.object(store, "DB_PATH", self.db))
        self.fields = dict(agent="worker", role="builder", prompt="edit", kind="edit",
                           contract_json={"goal": "café"})

    def claim(self, resume_of=None):
        return store.create_claimed(self.fields, os.path.join(self.workspace, "."), resume_of)

    def race(self, resume_of=None):
        start = threading.Barrier(2, timeout=2)

        def contender():
            start.wait()
            return self.claim(resume_of)

        with ThreadPoolExecutor(2) as pool:
            futures = [pool.submit(contender) for _ in range(2)]
            return [future.result(timeout=2) for future in futures]

    def ids(self):
        with sqlite3.connect(self.db) as conn:
            return [row[0] for row in conn.execute("SELECT id FROM tasks")]

    def test_concurrent_claims_insert_one_row(self):
        results = self.race()
        winner, = self.ids()
        self.assertCountEqual(results, [(winner, None), (None, winner)])
        row = store.get(winner)
        self.assertEqual(row["workspace"], self.workspace)
        self.assertEqual(row["contract_json"], self.fields["contract_json"])

    def test_live_legacy_edit_refuses_without_inserting(self):
        holder = store.create(**self.fields, workspace=self.workspace)
        self.assertEqual(self.claim(), (None, holder))
        self.assertEqual(self.ids(), [holder])

    def test_live_edit_in_other_workspace_does_not_block(self):
        other = os.path.join(self.workspace, "elsewhere")
        store.create(**self.fields, workspace=other)
        tid, holder = self.claim()
        self.assertIsNotNone(tid)
        self.assertIsNone(holder)
        self.assertEqual(len(self.ids()), 2)

    def test_legacy_analyze_does_not_block(self):
        store.create("worker", "reviewer", "read", kind="analyze", workspace=self.workspace)
        tid, holder = self.claim()
        self.assertIsNotNone(tid)
        self.assertIsNone(holder)

    def test_stale_edit_allows_takeover(self):
        old = store.create(**self.fields, workspace=self.workspace)
        store.update(old, heartbeat=time.time() - 61)
        tid, holder = self.claim()
        self.assertIsNotNone(tid)
        self.assertNotEqual(tid, old)
        self.assertIsNone(holder)

    def test_resume_updates_existing_task(self):
        tid, _ = self.claim()
        store.update(tid, status="failed", heartbeat=0)
        self.assertEqual(self.claim(tid), (tid, None))
        self.assertEqual(self.ids(), [tid])
        row = store.get(tid)
        self.assertEqual(row["status"], "running")
        self.assertGreater(row["heartbeat"], time.time() - 60)

    def test_concurrent_resumes_have_one_winner(self):
        tid = store.create(**self.fields, workspace=self.workspace)
        store.update(tid, status="done")
        self.assertCountEqual(self.race(tid), [(tid, None), (None, "")])
        self.assertEqual(self.ids(), [tid])

    def test_resumed_legacy_edit_blocks_claim_before_first_beat(self):
        tid = store.create("worker", "builder", "edit", kind="edit", workspace=self.workspace)
        store.update(tid, status="done", heartbeat=0)
        resumed_at = time.time()

        async def fake_run(*args, **kwargs):
            row = store.get(tid)
            self.assertEqual(row["status"], "running")
            self.assertGreaterEqual(row["heartbeat"], resumed_at)
            self.assertEqual(self.claim(), (None, tid))
            return "finished", []

        role = dict(role="builder", model="test", max_steps=1)
        with patch.object(server, "WORKSPACE", self.workspace), patch.object(server, "run", fake_run), \
             patch.object(server.events, "emit"), patch.object(server.gpu_lease, "guard_ollama"), \
             patch.object(store, "HEARTBEAT_EVERY", 60):
            task = server._execute(tid, "worker", role, "edit", checks=False)
            asyncio.run(asyncio.wait_for(task, timeout=2))
        row = store.get(tid)
        self.assertEqual(row["status"], "done", row.get("error"))

    def test_backend_wait_keeps_claim_alive(self):
        tid = store.create(**self.fields, workspace=self.workspace)
        store.update(tid, heartbeat=0)
        interval = 0.1

        async def backend_wait(name):
            await asyncio.sleep(interval * 2.5)
            self.assertGreater(store.get(tid)["heartbeat"], time.time() - 2 * interval)
            self.assertEqual(self.claim(), (None, tid))
            return "offline"

        role = dict(native=["test"], role="builder", model="test")
        with patch.object(store, "HEARTBEAT_EVERY", interval), patch.object(server, "WORKSPACE", self.workspace), \
             patch.object(server, "NATIVE_BACKENDS", {"test"}), patch.object(server, "backend_state", backend_wait), \
             patch.object(server.events, "emit"):
            asyncio.run(server._execute(tid, "worker", role, "edit"))
        self.assertEqual(store.get(tid)["status"], "failed")
