import asyncio
import unittest
from unittest import mock

from gateway import compose


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

        with mock.patch.object(compose, "_compose", fake):
            try:
                asyncio.run(go())
            except compose.ComposeError:
                calls.append(("error",))
        return [c[0] for c in calls]

    def test_up_then_stop(self):
        self.assertEqual(self.run_cm(), ["up", "body", "stop"])

    def test_keep_alive_skips_stop(self):
        self.assertEqual(self.run_cm(keep_alive=True), ["up", "body"])

    def test_start_failure_stops_and_raises(self):
        self.assertEqual(self.run_cm(compose.ComposeError("x")), ["up", "stop", "error"])


if __name__ == "__main__":
    unittest.main()
