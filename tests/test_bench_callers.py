"""Guard: scripts/bench.py must read per-role tasks through first_task(), not ROLE_TASKS["<role>"].

Reads the source as text so bench.py is never imported (importing it loads the router).
"""
import os
import re
import unittest

BENCH_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "bench.py")

# A literal-string subscript such as ROLE_TASKS["builder"] or ROLE_TASKS['builder'].
# Variable-key lookups (ROLE_TASKS[r]) and membership/iteration uses are deliberately not matched.
LITERAL_SUBSCRIPT = re.compile(r"""ROLE_TASKS\[\s*["']""")


class BenchCallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(BENCH_PATH, encoding="utf-8") as f:
            cls.lines = f.read().splitlines()

    def test_first_task_defined(self):
        self.assertTrue(any(line.lstrip().startswith("def first_task") for line in self.lines),
                        "def first_task is missing from scripts/bench.py")

    def test_no_literal_role_subscripts_outside_definition(self):
        offenders = []
        in_definition = False
        for no, line in enumerate(self.lines, start=1):
            stripped = line.lstrip()
            if stripped.startswith("def first_task"):
                in_definition = True
                continue
            if in_definition:
                # the definition body is indented; a non-indented non-blank line ends it
                if line.strip() and not line.startswith((" ", "\t")):
                    in_definition = False
                else:
                    continue
            if LITERAL_SUBSCRIPT.search(line):
                offenders.append(f"line {no}: {line.strip()}")
        self.assertEqual(offenders, [], "direct ROLE_TASKS[\"<role>\"] subscripts remain:\n" + "\n".join(offenders))


if __name__ == "__main__":
    unittest.main()
