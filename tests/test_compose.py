import asyncio
import unittest
from unittest import mock

from router import compose


class BackendsTest(unittest.TestCase):
    def run_cm(self, side_effect=None, **kw):
        calls = []

        async def fake(*a, timeout):
            calls.append(a)
            if side_effect and a[0] == "up":
                raise side_effect

        async def go():
            async with compose.backends(["crawl4ai"], **kw):
                calls.append(("body",))

        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d, mock.patch.object(compose, "LEASES", Path(d)),                 mock.patch.object(compose, "_compose", fake):
            try:
                asyncio.run(go())
            except compose.ComposeError:
                calls.append(("error",))
        return [c[0] for c in calls]

    def run_cm(self, side_effect=None, **kw):
        calls = []

        async def fake(*a, timeout):
            calls.append(a)
            if side_effect and a[0] == "up":
                raise side_effect

        async def go():
            async with compose.backends(["crawl4ai"], **kw):
                calls.append(("body",))
            # the idle stop runs IDLE_S later; with IDLE_S patched to 0 it is due at once
            await asyncio.gather(*list(compose._idle.values()), return_exceptions=True)

        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d, mock.patch.object(compose, "LEASES", Path(d)),                 mock.patch.object(compose, "IDLE_S", 0), mock.patch.object(compose, "_compose", fake):
            try:
                asyncio.run(go())
            except compose.ComposeError:
                calls.append(("error",))
        return [c[0] for c in calls]

    def test_up_then_idle_stop(self):
        self.assertEqual(self.run_cm(), ["up", "body", "stop"])

    def test_keep_alive_skips_stop(self):
        self.assertEqual(self.run_cm(keep_alive=True), ["up", "body"])

    def test_start_failure_stops_and_raises(self):
        self.assertEqual(self.run_cm(compose.ComposeError("x")), ["up", "stop", "error"])

    def test_reuse_inside_idle_window_cancels_the_stop(self):
        calls = []

        async def fake(*a, timeout):
            calls.append(a[0])

        async def go():
            async with compose.backends(["crawl4ai"]):
                pass
            first = compose._idle["crawl4ai"]
            async with compose.backends(["crawl4ai"]):  # second task arrives inside the window
                self.assertTrue(first.cancelled() or first.cancelling(), "first idle stop cancelled")
            await asyncio.gather(*list(compose._idle.values()), return_exceptions=True)  # clean up the new window

        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d, mock.patch.object(compose, "LEASES", Path(d)),                 mock.patch.object(compose, "IDLE_S", 0.2), mock.patch.object(compose, "_compose", fake):
            asyncio.run(go())
        self.assertEqual(calls, ["up", "up", "stop"])  # one stop, after the second task's own idle window

    def test_live_peer_blocks_idle_stop(self):
        import tempfile
        from pathlib import Path
        calls = []

        async def fake(*a, timeout):
            calls.append(a[0])

        async def go():
            async with compose.backends(["crawl4ai"]):
                pass
            await asyncio.gather(*list(compose._idle.values()), return_exceptions=True)

        with tempfile.TemporaryDirectory() as d, mock.patch.object(compose, "LEASES", Path(d)),                 mock.patch.object(compose, "IDLE_S", 0), mock.patch.object(compose, "_compose", fake),                 mock.patch.object(compose, "_has_live_lease", lambda s: True):
            asyncio.run(go())
        self.assertEqual(calls, ["up"])  # another router still uses it: no stop


class LeaseTest(unittest.TestCase):
    """Cross-process leases: a backend is stopped only when no other live router still uses it."""

    def setUp(self):
        import tempfile
        from pathlib import Path
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p = mock.patch.object(compose, "LEASES", Path(self.tmp.name))
        p.start()
        self.addCleanup(p.stop)

    def test_sole_user_gets_idle(self):
        t = compose.lease_acquire(["crawl4ai"])
        self.assertEqual(compose.lease_release(t), ["crawl4ai"])

    def test_live_peer_blocks_stop(self):
        mine = compose.lease_acquire(["crawl4ai"])
        (compose.LEASES / "crawl4ai.99999.peer").write_text("")
        with mock.patch.object(compose, "_alive", lambda pid: pid == 99999 or pid == __import__("os").getpid()):
            self.assertEqual(compose.lease_release(mine), [])

    def test_dead_peer_is_pruned(self):
        mine = compose.lease_acquire(["crawl4ai"])
        (compose.LEASES / "crawl4ai.99999.peer").write_text("")
        with mock.patch.object(compose, "_alive", lambda pid: pid != 99999):
            self.assertEqual(compose.lease_release(mine), ["crawl4ai"])
        self.assertFalse((compose.LEASES / "crawl4ai.99999.peer").exists())


if __name__ == "__main__":
    unittest.main()
