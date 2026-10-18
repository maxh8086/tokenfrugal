"""Offline tests for the leaked-gateway-container sweep (scripts/bench_real.py). Docker is mocked."""
import unittest
from datetime import datetime, timezone
from unittest import mock

from scripts import bench_real

NOW = datetime(2026, 10, 18, 12, 0, 0, tzinfo=timezone.utc)


def fake_docker(ps_out, inspect_out, calls):
    def run(args):
        calls.append(args)
        if args[0] == "ps":
            return 0, ps_out
        if args[0] == "inspect":
            return 0, inspect_out
        return 0, ""
    return run


class SweepTests(unittest.TestCase):
    def test_only_old_containers_are_stale(self):
        inspect = "old1 2026-10-18T10:00:00.123Z\nnew1 2026-10-18T11:59:30.000Z\n"
        with mock.patch.object(bench_real, "_docker", fake_docker("old1\nnew1\n", inspect, [])):
            self.assertEqual(bench_real.stale_mcp_containers(900, NOW), ["old1"])

    def test_no_containers_means_no_inspect_or_rm(self):
        calls = []
        with mock.patch.object(bench_real, "_docker", fake_docker("", "", calls)):
            self.assertEqual(bench_real.sweep_stale_mcp(), 0)
        self.assertEqual([c[0] for c in calls], ["ps"])

    def test_sweep_removes_stale(self):
        calls = []
        inspect = "old1 2020-01-01T00:00:00Z\n"
        with mock.patch.object(bench_real, "_docker", fake_docker("old1\n", inspect, calls)):
            self.assertEqual(bench_real.sweep_stale_mcp(900), 1)
        self.assertEqual(calls[-1], ["rm", "-f", "old1"])


if __name__ == "__main__":
    unittest.main()
