"""Offline tests for benchmark scoring (scripts/bench_csv.py) and the team section timeout (scripts/bench.py).
No model, router or container is contacted."""
import ast
import os
import unittest
from pathlib import Path
from unittest import mock

from scripts import bench_csv
from scripts.bench_team_tasks import TEAM_TASKS

ROOT = Path(__file__).resolve().parent.parent


def _load_section_timeout():
    """scripts/bench.py imports the whole router at module level, so pull only section_timeout and its constants."""
    src = (ROOT / "scripts" / "bench.py").read_text(encoding="utf-8")
    body = [n for n in ast.parse(src).body
            if (isinstance(n, ast.FunctionDef) and n.name == "section_timeout")
            or (isinstance(n, ast.Assign) and any(getattr(t, "id", None) in ("SECTION_MARGIN", "CASE_TIMEOUT")
                                                  for t in n.targets))]
    ns = {"os": os, "TEAM_TASKS": TEAM_TASKS}
    exec(compile(ast.Module(body, []), "bench.py", "exec"), ns)
    return ns


class Scoring(unittest.TestCase):
    def test_valid_count_and_mean_exclude_infra(self):
        cases = {
            "a": {"status": "valid", "s": {"mean": 10.0}},
            "b": {"status": "infra", "s": None},
            "c": {"status": "valid", "s": {"mean": 20.0}},
            "d": {"status": "timeout", "s": {"mean": 30.0}},
        }
        valid, infra, mean = bench_csv.status_scores(cases)
        self.assertEqual((valid, infra), (3, 1))
        self.assertEqual(mean, 20.0)

    def test_all_infra_gives_blank_mean(self):
        self.assertEqual(bench_csv.status_scores({"a": {"status": "infra", "s": None}}), (0, 1, ""))

    def test_total_seconds_includes_timeouts_and_infra_runs(self):
        cases = {
            "a": {"status": "valid", "runs": [{"s": 10.4}, {"s": 20.2}]},
            "b": {"status": "infra", "runs": [{"s": 0.0}, {"s": 5.5}]},  # dispatched infra repeat still took time
            "c": {"status": "timeout", "runs": [{"s": 600.0}]},
            "err": {"error": "no result after 100s (section watchdog)"},  # section-level entry, skipped
        }
        self.assertEqual(bench_csv.total_seconds(cases), 636)  # 10.4+20.2+5.5+600.0 = 636.1

    def test_total_seconds_empty_is_zero(self):
        self.assertEqual(bench_csv.total_seconds({}), 0)
        self.assertEqual(bench_csv.total_seconds({"roles": {"error": "x"}}), 0)


class SectionTimeout(unittest.TestCase):
    def setUp(self):
        self.ns = _load_section_timeout()
        env = {k: v for k, v in os.environ.items() if k != "BENCH_SECTION_TIMEOUT"}
        patch = mock.patch.dict(os.environ, env, clear=True)
        patch.start()
        self.addCleanup(patch.stop)

    def test_derived_from_team_tasks_and_case_timeout(self):
        total_tasks = sum(len(tasks) for tasks in TEAM_TASKS.values())
        case_timeout, margin = self.ns["CASE_TIMEOUT"], self.ns["SECTION_MARGIN"]
        self.assertEqual(self.ns["section_timeout"](5), total_tasks * 5 * case_timeout + margin)
        self.assertEqual(self.ns["section_timeout"](1), total_tasks * case_timeout + margin)

    def test_env_override_wins(self):
        with mock.patch.dict(os.environ, {"BENCH_SECTION_TIMEOUT": "123"}):
            self.assertEqual(self.ns["section_timeout"](5), 123.0)

    def test_case_timeout_default_is_600(self):
        if "BENCH_CASE_TIMEOUT" not in os.environ:
            self.assertEqual(self.ns["CASE_TIMEOUT"], 600.0)


if __name__ == "__main__":
    unittest.main()
