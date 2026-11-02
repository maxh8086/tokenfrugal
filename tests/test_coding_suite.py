import unittest
from pathlib import Path

from router import config


class LevelSkillTests(unittest.TestCase):
    def test_each_level_has_a_skill_file_and_role_entry(self):
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


if __name__ == "__main__":
    unittest.main()
