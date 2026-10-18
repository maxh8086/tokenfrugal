"""Offline tests for router/mcp_reap.py. Docker is mocked."""
import unittest
from unittest import mock

from router import mcp_reap


class ReapTests(unittest.TestCase):
    def setUp(self):
        mcp_reap._active, mcp_reap._before = 0, set()

    def run_with(self, snapshots):
        calls, snaps = [], iter(snapshots)

        def fake(args, docker="docker"):
            calls.append(args)
            return (0, next(snaps)) if args[0] == "ps" else (0, "")
        return calls, mock.patch.object(mcp_reap, "_docker", fake)

    def test_removes_only_containers_new_since_enter(self):
        calls, p = self.run_with(["old\n", "old\nnew1\nnew2\n"])
        with p:
            mcp_reap.enter()
            self.assertEqual(mcp_reap.leave(), 2)
        self.assertEqual(calls[-1], ["rm", "-f", "new1", "new2"])

    def test_nested_gateways_reap_when_last_closes(self):
        calls, p = self.run_with(["", "a\n"])
        with p:
            mcp_reap.enter()
            mcp_reap.enter()
            self.assertEqual(mcp_reap.leave(), 0)
            self.assertEqual(mcp_reap.leave(), 1)
        self.assertEqual(calls[-1], ["rm", "-f", "a"])

    def test_nothing_new_means_no_rm(self):
        calls, p = self.run_with(["x\n", "x\n"])
        with p:
            mcp_reap.enter()
            self.assertEqual(mcp_reap.leave(), 0)
        self.assertNotIn("rm", [c[0] for c in calls])
