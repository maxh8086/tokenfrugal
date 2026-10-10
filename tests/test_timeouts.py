import asyncio
import unittest
from unittest import mock

from gateway import loop


class TaskTimeout(unittest.TestCase):
    def test_task_timeout_becomes_loop_error_with_msgs(self):
        async def hang(*a, **k):
            await asyncio.sleep(30)

        role = {"role": "builder", "model": "m", "tools": [], "max_steps": 1}
        with mock.patch.object(loop, "_run", hang), mock.patch.object(loop, "TASK_TIMEOUT", 0.05):
            with self.assertRaises(loop.LoopError) as cm:
                asyncio.run(loop.run("a", role, "do it"))
        self.assertIn("timed out", str(cm.exception))
        self.assertTrue(cm.exception.msgs)


if __name__ == "__main__":
    unittest.main()
