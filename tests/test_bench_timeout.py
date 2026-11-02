"""The role time limit is applied by the harness wait_for only; model text that mentions TimeoutError is kept as is."""
import asyncio
import unittest

from scripts import bench


class RoleCallTimeout(unittest.TestCase):
    def test_harness_limit_is_labelled_with_the_limit(self):
        async def slow(*a, **k):
            await asyncio.sleep(1)
            return "late"
        real = bench.server.dispatch_task
        bench.server.dispatch_task = slow
        try:
            r = asyncio.run(bench.role_call("a", "t", 0.05))
        finally:
            bench.server.dispatch_task = real
        self.assertEqual(r, "FAILED TimeoutError after 0.05s")

    def test_model_reply_mentioning_timeout_is_not_relabelled(self):
        async def reply(*a, **k):
            return "TimeoutError: read operation"
        real = bench.server.dispatch_task
        bench.server.dispatch_task = reply
        try:
            r = asyncio.run(bench.role_call("a", "t", 600))
        finally:
            bench.server.dispatch_task = real
        self.assertEqual(r, "TimeoutError: read operation")
        self.assertNotIn("after 600", r)


if __name__ == "__main__":
    unittest.main()
