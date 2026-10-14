"""Step (a): scripts/smoke.py must run from any cwd without PYTHONPATH=. (it bootstraps sys.path itself)."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SMOKE = ROOT / "scripts" / "smoke.py"


class SmokePathTests(unittest.TestCase):
    # TODO(step a): remove @expectedFailure once smoke.py bootstraps sys.path and supports --list.
    @unittest.expectedFailure
    def test_list_runs_without_pythonpath(self):
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        with tempfile.TemporaryDirectory() as cwd:  # neither the repo root nor PYTHONPATH can help
            p = subprocess.run([sys.executable, str(SMOKE), "--list"], cwd=cwd, env=env,
                               capture_output=True, text=True, timeout=60)
        self.assertNotIn("ModuleNotFoundError", p.stderr)
        self.assertEqual(p.returncode, 0, p.stderr[-500:])
        for role in ("builder", "docs", "security", "browser", "tracker"):
            self.assertIn(role, p.stdout)


if __name__ == "__main__":
    unittest.main()
