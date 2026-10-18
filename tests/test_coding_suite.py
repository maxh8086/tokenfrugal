import os
import unittest
from pathlib import Path

from router import config
from scripts import bench_real


class CodingSuite(unittest.TestCase):
    def test_six_levels_each_own_role(self):
        cases = bench_real.coding_cases()
        self.assertEqual([c[1] for c in cases], [f"coding-l{i}" for i in range(1, 7)])
        cfg = config.load_tf_roles()
        for _cid, agent, _seed, task, _check in cases:
            role = config.resolve_role(agent, cfg)
            self.assertIn("run_tests", role["tools"])
            self.assertLessEqual(len(role["tools"]), 6)
            self.assertIn("Do not edit the test files", task)

    def test_active_cases_switch(self):
        old = os.environ.get("BENCH_SUITE")
        os.environ["BENCH_SUITE"] = "coding"
        try:
            self.assertEqual(bench_real.active_cases()[0][0], "code_l1_clamp")
        finally:
            if old is None:
                os.environ.pop("BENCH_SUITE")
            else:
                os.environ["BENCH_SUITE"] = old


if __name__ == "__main__":
    unittest.main()


class LevelSkillTests(unittest.TestCase):
    def test_each_level_has_a_skill_file_and_role_entry(self):
        from pathlib import Path
        cfg = config.load_tf_roles()
        for n in range(1, 7):
            role = config.resolve_role(f"coding-l{n}", cfg)
            self.assertIn(f"code-l{n}", role["skills"])
            path = Path("router/skills") / f"code-l{n}" / "SKILL.md"
            self.assertTrue(path.exists(), path)
            self.assertLess(len(path.read_text(encoding="utf-8")), 1200)


class RoleSkillTests(unittest.TestCase):
    ROLES = ["builder", "data-engineer", "db-postgres-dev", "db-postgres-admin", "db-mongo-dev-l1", "db-redis-admin-l1", "db-elastic-dev", "analyzer", "security", "reviewer", "debugger", "docs",
             "designer", "browser", "github-read", "github-actions-read", "devops",
             "finance", "research"]

    def test_every_role_has_an_existing_short_skill(self):
        cfg = config.load_tf_roles()
        root = Path(__file__).resolve().parent.parent / "router" / "skills"
        for role in self.ROLES:
            skills = cfg["roles"][role].get("skills") or []
            self.assertTrue(skills, role)
            for name in skills:
                path = root / name / "SKILL.md"
                self.assertTrue(path.exists(), f"{role}:{name}")
                self.assertLess(len(path.read_text(encoding="utf-8")), 1200, name)
