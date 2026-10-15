import importlib.util
import sys
import unittest
from pathlib import Path

SRC = (Path(__file__).resolve().parent.parent / "Benchmark" / "script" / "run_benchmark.py").read_text(encoding="utf-8")


def _mount_ok():
    ns = {}
    start = SRC.index("def mount_ok")
    exec(SRC[start:SRC.index("def preflight")], ns)
    return ns["mount_ok"]


class MountCheck(unittest.TestCase):
    def test_match_and_mismatch(self):
        f = _mount_ok()
        self.assertTrue(f(r"- C:\Users\v\Projects:/workspace:rw", "C:/Users/v/Projects"))
        self.assertFalse(f(r"- C:\Users\v\Projects\Market-Scanner:/workspace:rw", "C:/Users/v/Projects"))


if __name__ == "__main__":
    unittest.main()
