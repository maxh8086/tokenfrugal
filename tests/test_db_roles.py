import unittest
from pathlib import Path

from router import config
from scripts import gen_db_profiles as g

ROOT = Path(__file__).resolve().parent.parent


class DbRoleTests(unittest.TestCase):
    def setUp(self):
        self.cfg = config.load_tf_roles()

    def test_every_generated_profile_is_a_role_with_a_profile_file(self):
        for pid, (_engine, kind, tools) in g.ROLES.items():
            role = self.cfg["roles"][pid]
            self.assertEqual(role["profile"], pid)
            self.assertEqual(role["model"], "builder" if kind == "dev" else "thinker")
            self.assertEqual(role["tools"], tools)
            self.assertTrue((ROOT / "profiles" / f"{pid}.yaml").exists(), pid)

    def test_allowlists_are_capped_and_never_destructive(self):
        for pid, role in self.cfg["roles"].items():
            if not pid.startswith("db-"):
                continue
            self.assertLessEqual(len(role["tools"]), g.MAX_TOOLS, pid)
            for tool in role["tools"]:
                for bad in g.FORBIDDEN:
                    self.assertNotIn(bad, tool, f"{pid}:{tool}")

    def test_admin_sql_toml_is_readonly(self):
        for engine in g.DSN:
            self.assertIn("readonly = true", g.toml_for(engine, "admin"))
            self.assertIn("readonly = false", g.toml_for(engine, "dev"))

    def test_scratch_roles_start_their_container(self):
        for pid, role in self.cfg["roles"].items():
            if pid.startswith("db-") and "oracle" not in pid:
                self.assertEqual(role["compose"], [f"db-{g.ROLES[pid][0]}"], pid)

    def test_slugs_resolve(self):
        for slug in ("db-postgres-dev", "db-redis-dev-l3", "engineering-data-engineer"):
            self.assertIn("tools", config.resolve_role(slug, self.cfg))


if __name__ == "__main__":
    unittest.main()
